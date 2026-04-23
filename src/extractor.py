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

# Chunking parameters: prevents the extractor from only seeing the first
# _MAX_TEXT_CHARS of a long PDF (which is where most of the hallucinated
# boilerplate in the old output came from — the model was asked about KDEs
# that never appeared in the truncated window).
_CHUNK_CHARS = 2500
_CHUNK_OVERLAP = 250
_MAX_CHUNKS_PER_KDE = 3  # cap LLM calls per KDE for runtime
_MIN_GROUND_WORDS = 2    # min content-word overlap between requirement and source chunk

# Stem-based keyword hints so e.g. "encryption" matches chunks containing
# "encrypted" / "encrypt". A chunk that mentions none of these is skipped
# for that KDE — the model is not prompted to invent requirements for a
# concept the document does not discuss.
_KDE_KEYWORDS = {
    "access_control": ["access", "permission", "rbac", "role"],
    "authentication": ["authentic", "credential", "password", "mfa", "identity"],
    "authorization": ["authoriz", "permission", "privileg", "rbac"],
    "data_protection": ["data", "privacy", "confidential", "sensitive"],
    "encryption": ["encrypt", "tls", "ssl", "cipher"],
    "logging_and_monitoring": ["log", "audit", "monitor", "alert"],
    "network_security": ["network", "firewall", "ingress", "egress"],
    "patch_management": ["patch", "update", "upgrade"],
    "privileged_access": ["privileg", "admin", "root", "sudo"],
    "vulnerability_management": ["vulnerab", "cve", "exploit"],
}

_STOPWORDS = {
    "the", "a", "an", "is", "are", "be", "to", "of", "for", "and", "or",
    "in", "on", "at", "by", "with", "from", "that", "this", "these", "those",
    "must", "should", "shall", "may", "will", "can", "not", "no", "it", "its",
    "as", "all", "any", "some", "each", "system", "user", "users", "provide",
    "mechanism", "able", "have", "has", "had", "their", "there", "when",
    "where", "which", "who", "what", "why", "how", "also", "such", "via",
    "based", "other", "over", "into", "than", "then", "so", "if", "but",
    "only", "been", "being", "was", "were", "do", "does", "did",
}

_TRUNCATED_TAIL_RE = re.compile(
    r"\b(?:to|be|and|or|with|for|of|in|on|by|from|as|related|including|based|regarding)\.?$",
    re.IGNORECASE,
)

_LEAKAGE_PREFIXES = (
    "final answer",
    "requirements for",
    "llm name",
    "prompt used",
    "prompt type",
    "llm output",
)

_MODEL_ID = "google/gemma-3-1b-it"

_pipeline = None  # module-level lazy singleton

_RECOMMENDATION_STATUS_RE = re.compile(r"\((?:Automated|Manual)\)", re.IGNORECASE)
_RECOMMENDATION_HEADING_RE = re.compile(r"^(\d+(?:\.\d+)+)\s+(.+)$")
_RECOMMENDATION_ACTION_RE = re.compile(
    r"\b(ensure|enable|disable|minimize|avoid|limit|prefer|consider|restrict|manage|rotate|use)\b",
    re.IGNORECASE,
)
_FIELD_ORDER = [
    "Profile Applicability:",
    "Description:",
    "Rationale:",
    "Impact:",
    "Audit:",
    "Remediation:",
    "Default Value:",
    "References:",
    "CIS Controls:",
]


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


def _sanitize_requirement_text(requirement: str) -> str | None:
    """Return cleaned requirement text, or None if it is malformed/noise.

    This removes prompt-leakage tokens (e.g. "Final Answer"), pure-number
    list debris, and visibly truncated sentence fragments.
    """
    req = _clean_text(requirement).strip("'\" ")
    if not req:
        return None

    lower = req.lower().strip()
    if lower in {"none", "n/a", "na"}:
        return None
    if any(lower.startswith(prefix) for prefix in _LEAKAGE_PREFIXES):
        return None
    if re.fullmatch(r"\d+[\.]?", lower):
        return None
    if re.fullmatch(r"[\W_]+", lower):
        return None
    if len(req) < 12:
        return None
    if not re.search(r"[.!?]$", req) and len(req.split()) <= 6:
        return None
    if req.endswith(":"):
        return None
    if _TRUNCATED_TAIL_RE.search(req):
        return None
    if re.search(r"\b(final answer|step \d+|requirements for)\b", lower):
        return None
    if not re.search(r"[a-zA-Z]", req):
        return None
    return req


def _canonical_requirement_key(requirement: str) -> str:
    """Build a stable dedup key that ignores punctuation/casing differences."""
    key = re.sub(r"[^a-z0-9]+", " ", requirement.lower())
    key = re.sub(r"\s+", " ", key).strip()
    return key


def _clean_text(text: str) -> str:
    """Normalize whitespace and common PDF extraction artifacts."""
    text = text.replace("\u00a0", " ")
    text = text.replace("•", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\s+\n", "\n", text)
    text = re.sub(r"\n\s+", "\n", text)
    return text.strip()


def _normalize_element_name(title: str) -> str:
    """Create a stable YAML key from a CIS recommendation title."""
    title = _RECOMMENDATION_STATUS_RE.sub("", title)
    title = re.sub(r"^(ensure that|ensure|enable|disable|minimize|avoid|limit|prefer|consider|restrict|manage|use)\s+", "", title, flags=re.I)
    title = re.sub(r"[^a-zA-Z0-9]+", "_", title.lower()).strip("_")
    title = re.sub(r"_+", "_", title)
    return title[:120] or "unnamed_requirement"


def _strip_toc_dots(text: str) -> str:
    """Remove table-of-contents leader dots and trailing page numbers."""
    text = re.sub(r"\.{3,}\s*\d+\s*$", "", text).strip()
    return text


def _looks_like_recommendation(title: str) -> bool:
    """Return True for CIS recommendation headings, not section headings."""
    return bool(_RECOMMENDATION_STATUS_RE.search(title) and _RECOMMENDATION_ACTION_RE.search(title))


def _extract_field(section: str, field: str) -> str:
    """Extract one labelled field from a CIS recommendation section."""
    start = section.find(field)
    if start == -1:
        return ""
    start += len(field)
    end = len(section)
    for marker in _FIELD_ORDER:
        if marker == field:
            continue
        idx = section.find(marker, start)
        if idx != -1:
            end = min(end, idx)
    value = section[start:end]
    value = re.sub(r"\n+", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def _extract_cis_recommendations(text: str) -> list[dict]:
    """Extract recommendation sections from CIS benchmark-style PDFs.

    The project documents are CIS benchmarks, which have consistent numbered
    recommendation headings followed by labelled Description/Rationale/etc.
    Parsing those headings gives much more grounded KDE names than asking a
    small model to invent an element taxonomy from the first few PDF pages.
    """
    lines = _clean_text(text).splitlines()
    candidates: list[dict] = []

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        match = _RECOMMENDATION_HEADING_RE.match(line)
        if not match:
            i += 1
            continue

        number = match.group(1)
        title_parts = [_strip_toc_dots(match.group(2))]
        j = i + 1
        while j < len(lines) and j <= i + 4 and not _RECOMMENDATION_STATUS_RE.search(" ".join(title_parts)):
            nxt = lines[j].strip()
            if not nxt or nxt.startswith("Page "):
                j += 1
                continue
            if _RECOMMENDATION_HEADING_RE.match(nxt):
                break
            title_parts.append(_strip_toc_dots(nxt))
            j += 1

        title = re.sub(r"\s+", " ", " ".join(title_parts)).strip()
        if not _looks_like_recommendation(title):
            i += 1
            continue

        candidates.append({"number": number, "title": title, "line_index": i})
        i = max(j, i + 1)

    # Drop table-of-contents duplicates by keeping the occurrence that has
    # actual labelled recommendation fields after it.
    recommendations: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for idx, item in enumerate(candidates):
        start = item["line_index"]
        end = candidates[idx + 1]["line_index"] if idx + 1 < len(candidates) else len(lines)
        section = "\n".join(lines[start:end])
        if "Description:" not in section and "Rationale:" not in section:
            continue

        key = (item["number"], re.sub(r"\s+", " ", item["title"]).lower())
        if key in seen:
            continue
        seen.add(key)

        recommendations.append(
            {
                "number": item["number"],
                "title": item["title"],
                "description": _extract_field(section, "Description:"),
                "rationale": _extract_field(section, "Rationale:"),
                "remediation": _extract_field(section, "Remediation:"),
            }
        )

    return recommendations


def _requirements_from_recommendation(rec: dict) -> list[str]:
    """Build concise, grounded requirement strings for one recommendation."""
    title = _RECOMMENDATION_STATUS_RE.sub("", rec.get("title", "")).strip()
    title = re.sub(r"\s+", " ", title)
    if title and not title.endswith("."):
        title += "."

    requirements = []
    if title:
        requirements.append(title)
    for field in ("description", "rationale", "remediation"):
        value = rec.get(field, "")
        if value:
            if len(value) > 700:
                value = value[:700].rsplit(" ", 1)[0].strip() + "."
            requirements.append(value)

    deduped = []
    seen = set()
    for req in requirements:
        req = _clean_text(req)
        key = req.lower()
        if req and key not in seen:
            seen.add(key)
            deduped.append(req)
    return deduped


def _extract_kdes_from_cis_text(text: str) -> dict:
    """Return KDEs discovered from CIS recommendation headings."""
    recs = _extract_cis_recommendations(text)
    result = {}
    used_names: dict[str, int] = {}
    for rec in recs:
        base_name = _normalize_element_name(rec["title"])
        occurrence = used_names.get(base_name, 0) + 1
        used_names[base_name] = occurrence
        name = base_name if occurrence == 1 else f"{base_name}_{occurrence}"
        result[name] = {
            "name": name,
            "requirements": _requirements_from_recommendation(rec),
        }
    return result


def _chunk_text(text: str, size: int = _CHUNK_CHARS, overlap: int = _CHUNK_OVERLAP) -> list:
    """Split text into overlapping windows so long documents can be queried in pieces."""
    if not text:
        return []
    chunks = []
    start = 0
    n = len(text)
    step = max(1, size - overlap)
    while start < n:
        chunks.append(text[start:start + size])
        if start + size >= n:
            break
        start += step
    return chunks


def _chunk_matches_kde(chunk: str, kde_name: str) -> bool:
    """Return True when the chunk likely discusses the given KDE."""
    lower = chunk.lower()
    keywords = _KDE_KEYWORDS.get(kde_name, [kde_name.replace("_", " ")])
    return any(kw in lower for kw in keywords)


def _requirement_matches_kde(requirement: str, kde_name: str) -> bool:
    """Keep requirements that mention the KDE or one of its stemmed hints."""
    lower = requirement.lower()
    keywords = _KDE_KEYWORDS.get(kde_name, [kde_name.replace("_", " ")])
    return any(kw in lower for kw in keywords)


def _content_words(text: str) -> set:
    """Return lowercase content words (3+ letters, non-stopword) for grounding checks."""
    words = re.findall(r"[a-zA-Z]{3,}", text.lower())
    return {w for w in words if w not in _STOPWORDS}


def _grounded(requirement: str, source: str, min_overlap: int = _MIN_GROUND_WORDS) -> bool:
    """Drop requirements that share almost no content words with their source chunk.

    Blocks the generic "The system must be able to ..." boilerplate that Gemma-3-1B
    emits when asked about a concept that isn't actually discussed in the chunk.
    """
    req_words = _content_words(requirement)
    if not req_words:
        return False
    src_words = _content_words(source)
    if len(req_words) < min_overlap:
        return bool(req_words & src_words)
    return len(req_words & src_words) >= min_overlap


def extract_kdes(text: str, prompt_fn: Callable[[str, str], str]) -> dict:
    """Extract Key Data Elements from document text.

    For CIS benchmark documents, KDEs are discovered from numbered
    recommendation headings and their labelled Description/Rationale/
    Remediation fields. If the input is not CIS-like, the function falls back
    to the Gemma-3-1B prompt path using default security KDE categories.

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

    chunks = _chunk_text(text) or [text]

    for kde_name in KDE_NAMES:
        relevant = [c for c in chunks if _chunk_matches_kde(c, kde_name)]
        if not relevant:
            result[kde_name] = {"name": kde_name, "requirements": []}
            continue

        relevant = relevant[:_MAX_CHUNKS_PER_KDE]
        seen = set()
        reqs = []
        for chunk in relevant:
            prompt = prompt_fn(chunk, kde_name)
            try:
                outputs = pipe(
                    prompt,
                    max_new_tokens=256,
                    do_sample=False,
                    repetition_penalty=1.3,
                    no_repeat_ngram_size=6,
                )
                generated = outputs[0]["generated_text"]
                if generated.startswith(prompt):
                    generated = generated[len(prompt):]
                parsed = _parse_requirements_from_output(generated)
            except Exception:
                parsed = []

            for req in parsed:
                req = _sanitize_requirement_text(req)
                if not req:
                    continue
                if not _requirement_matches_kde(req, kde_name):
                    continue
                if not _grounded(req, chunk):
                    continue
                key = _canonical_requirement_key(req)
                if key in seen:
                    continue
                seen.add(key)
                reqs.append(req)

        result[kde_name] = {"name": kde_name, "requirements": reqs}

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
