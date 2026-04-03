"""Task-1: PDF extraction, prompt construction, LLM-based KDE identification."""

import os
import re
from typing import Callable

import yaml

from src.utils import (
    validate_file_exists,
    validate_extension,
    save_yaml,
    append_text,
    ensure_dir,
)

# Key Data Elements that the LLM is asked to identify in the documents
KDE_NAMES = [
    "access_control",
    "authentication",
    "authorization",
    "data_protection",
    "encryption",
    "logging_and_monitoring",
    "network_security",
    "patch_management",
    "privileged_access",
    "vulnerability_management",
]

# Maximum characters of document text to send per prompt (to stay within context)
_MAX_TEXT_CHARS = 3000

_MODEL_ID = "google/gemma-3-1b-it"

_pipeline = None  # module-level lazy singleton


# ---------------------------------------------------------------------------
# 1. Document loader
# ---------------------------------------------------------------------------

def load_pdf(path: str) -> str:
    """Load a PDF and return all text as a single string.

    Parameters
    ----------
    path : str
        Absolute or relative path to the PDF file.

    Returns
    -------
    str
        Concatenated text from all pages.

    Raises
    ------
    FileNotFoundError
        If the file does not exist.
    ValueError
        If the file is not a PDF.
    RuntimeError
        If PyMuPDF cannot open the file.
    """
    validate_file_exists(path)
    validate_extension(path, ".pdf")

    try:
        import fitz  # PyMuPDF
    except ImportError as exc:
        raise ImportError(
            "PyMuPDF is required: pip install PyMuPDF"
        ) from exc

    try:
        doc = fitz.open(path)
    except Exception as exc:
        raise RuntimeError(f"Could not open PDF '{path}': {exc}") from exc

    pages = []
    for page in doc:
        pages.append(page.get_text())
    doc.close()
    return "\n".join(pages)


# ---------------------------------------------------------------------------
# 2. Prompt constructors
# ---------------------------------------------------------------------------

def zero_shot_prompt(text: str, element_name: str) -> str:
    """Construct a zero-shot prompt for identifying KDE requirements.

    Parameters
    ----------
    text : str
        Document text (or excerpt).
    element_name : str
        The key data element to search for.

    Returns
    -------
    str
        The formatted prompt string.
    """
    snippet = text[:_MAX_TEXT_CHARS]
    return (
        f"You are a security analyst. Read the following document excerpt and list "
        f"all security requirements related to '{element_name}'. "
        f"Return only a numbered list of requirements. "
        f"If none are found, return 'NONE'.\n\n"
        f"Document:\n{snippet}\n\n"
        f"Requirements for '{element_name}':"
    )


def few_shot_prompt(text: str, element_name: str) -> str:
    """Construct a few-shot prompt for identifying KDE requirements.

    Parameters
    ----------
    text : str
        Document text (or excerpt).
    element_name : str
        The key data element to search for.

    Returns
    -------
    str
        The formatted prompt string including examples.
    """
    snippet = text[:_MAX_TEXT_CHARS]
    return (
        f"You are a security analyst extracting requirements from security documents.\n\n"
        f"Example 1:\n"
        f"Element: encryption\n"
        f"Document: 'All data at rest must be encrypted using AES-256. "
        f"Data in transit must use TLS 1.2 or higher.'\n"
        f"Requirements:\n"
        f"1. Data at rest must be encrypted using AES-256.\n"
        f"2. Data in transit must use TLS 1.2 or higher.\n\n"
        f"Example 2:\n"
        f"Element: authentication\n"
        f"Document: 'Users must authenticate using multi-factor authentication. "
        f"Passwords must be at least 12 characters.'\n"
        f"Requirements:\n"
        f"1. Users must authenticate using multi-factor authentication.\n"
        f"2. Passwords must be at least 12 characters.\n\n"
        f"Example 3:\n"
        f"Element: logging_and_monitoring\n"
        f"Document: 'All access to sensitive data must be logged.'\n"
        f"Requirements:\n"
        f"1. All access to sensitive data must be logged.\n\n"
        f"Now extract requirements for '{element_name}' from the following document:\n\n"
        f"Document:\n{snippet}\n\n"
        f"Requirements for '{element_name}':"
    )


def chain_of_thought_prompt(text: str, element_name: str) -> str:
    """Construct a chain-of-thought prompt for identifying KDE requirements.

    Parameters
    ----------
    text : str
        Document text (or excerpt).
    element_name : str
        The key data element to search for.

    Returns
    -------
    str
        The formatted prompt string with step-by-step reasoning instructions.
    """
    snippet = text[:_MAX_TEXT_CHARS]
    return (
        f"You are a security analyst. Use step-by-step reasoning to identify "
        f"security requirements related to '{element_name}' in the document below.\n\n"
        f"Step 1: Read the document carefully.\n"
        f"Step 2: Identify all sentences or clauses that mention '{element_name}' "
        f"or closely related concepts.\n"
        f"Step 3: For each identified sentence, determine whether it states a "
        f"requirement (obligation, prohibition, or recommendation).\n"
        f"Step 4: List only the requirements, numbered.\n"
        f"Step 5: If no requirements are found, write 'NONE'.\n\n"
        f"Document:\n{snippet}\n\n"
        f"Now apply the steps above.\n"
        f"Requirements for '{element_name}':"
    )


# ---------------------------------------------------------------------------
# 3. LLM pipeline
# ---------------------------------------------------------------------------

def get_llm_pipeline():
    """Load and return the text-generation pipeline for _MODEL_ID (singleton).

    Returns
    -------
    transformers.Pipeline
        A text-generation pipeline for the model specified by _MODEL_ID.
    """
    global _pipeline
    if _pipeline is not None:
        return _pipeline

    try:
        import torch
        from transformers import pipeline as hf_pipeline
    except ImportError as exc:
        raise ImportError(
            "transformers and torch are required: pip install transformers torch"
        ) from exc

    device = 0 if torch.cuda.is_available() else -1
    _pipeline = hf_pipeline(
        "text-generation",
        model=_MODEL_ID,
        device=device,
        dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
    )
    return _pipeline


# ---------------------------------------------------------------------------
# 4. KDE extraction
# ---------------------------------------------------------------------------

def _parse_requirements_from_output(raw: str) -> list:
    """Parse LLM output into a list of requirement strings.

    Tries numbered/bulleted list format first ("1. ...", "- ...").
    Falls back to treating every non-empty, non-NONE line as a requirement
    so that plain-text LLM responses are not silently discarded.
    """
    lines = raw.strip().splitlines()
    reqs = []
    for line in lines:
        line = line.strip()
        if not line or line.upper() == "NONE":
            continue
        match = re.match(r"^(?:\d+[\.\)]|\-|\*)\s+(.+)$", line)
        if match:
            reqs.append(match.group(1).strip())
        else:
            reqs.append(line)
    return reqs


def extract_kdes(text: str, prompt_fn: Callable[[str, str], str]) -> dict:
    """Use the LLM to extract Key Data Elements from document text.

    Parameters
    ----------
    text : str
        Full document text.
    prompt_fn : callable
        One of zero_shot_prompt, few_shot_prompt, or chain_of_thought_prompt.

    Returns
    -------
    dict
        Nested dict of the form::

            {
              "element1": {"name": "element1", "requirements": ["req1", ...]},
              ...
            }
    """
    pipe = get_llm_pipeline()
    result = {}

    for kde_name in KDE_NAMES:
        prompt = prompt_fn(text, kde_name)
        try:
            outputs = pipe(prompt, max_new_tokens=512, do_sample=False)
            generated = outputs[0]["generated_text"]
            # Strip the prompt prefix if the model echoes it
            if generated.startswith(prompt):
                generated = generated[len(prompt):]
            reqs = _parse_requirements_from_output(generated)
        except Exception:
            reqs = []

        result[kde_name] = {
            "name": kde_name,
            "requirements": reqs,
        }

    return result


# ---------------------------------------------------------------------------
# 5. LLM output collector
# ---------------------------------------------------------------------------

def collect_llm_output(
    llm_name: str,
    prompt: str,
    prompt_type: str,
    llm_output: str,
    log_path: str,
) -> None:
    """Append a formatted LLM interaction record to a text log file.

    Parameters
    ----------
    llm_name : str
        Name of the LLM (e.g. "google/gemma-3-1b-it").
    prompt : str
        The exact prompt that was sent to the LLM.
    prompt_type : str
        One of "zero-shot", "few-shot", "chain-of-thought".
    llm_output : str
        The raw text output from the LLM.
    log_path : str
        Path to the output TEXT file.
    """
    entry = (
        f"*LLM Name*\n{llm_name}\n\n"
        f"*Prompt Used*\n{prompt}\n\n"
        f"*Prompt Type*\n{prompt_type}\n\n"
        f"*LLM Output*\n{llm_output}\n\n"
        f"{'=' * 80}\n\n"
    )
    append_text(entry, log_path)


# ---------------------------------------------------------------------------
# 6. Orchestrator
# ---------------------------------------------------------------------------

def run_extraction(
    pdf_path: str,
    prompt_fn: Callable[[str, str], str],
    prompt_type: str,
    output_yaml: str,
    log_txt: str,
) -> dict:
    """Full Task-1 pipeline: load PDF → extract KDEs → save YAML → log output.

    Parameters
    ----------
    pdf_path : str
        Path to the input PDF.
    prompt_fn : callable
        Prompt constructor function to use.
    prompt_type : str
        Human-readable name for prompt_fn ("zero-shot", "few-shot", "chain-of-thought").
    output_yaml : str
        Path where the YAML output file will be written.
    log_txt : str
        Path to the shared LLM output log TEXT file.

    Returns
    -------
    dict
        The extracted KDE nested dict.
    """
    text = load_pdf(pdf_path)
    kdes = extract_kdes(text, prompt_fn)
    save_yaml(kdes, output_yaml)

    pipe = get_llm_pipeline()
    llm_name = _MODEL_ID

    for kde_name, kde_data in kdes.items():
        prompt = prompt_fn(text, kde_name)
        reqs_text = "\n".join(
            f"{i+1}. {r}" for i, r in enumerate(kde_data.get("requirements", []))
        ) or "NONE"
        collect_llm_output(
            llm_name=llm_name,
            prompt=prompt,
            prompt_type=prompt_type,
            llm_output=reqs_text,
            log_path=log_txt,
        )

    return kdes
