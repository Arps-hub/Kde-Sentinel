"""Tests for src/extractor.py — one test per function."""

import os
import yaml
import pytest
from unittest.mock import patch, MagicMock

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
SAMPLE_PDF = os.path.join(FIXTURES_DIR, "sample.pdf")

SAMPLE_TEXT = (
    "All data at rest must be encrypted using AES-256. "
    "Users must authenticate using multi-factor authentication. "
    "All access to sensitive data must be logged."
)

# ---------------------------------------------------------------------------
# Fake pipeline factory
# ---------------------------------------------------------------------------

def _make_fake_pipeline(response: str = "1. Some requirement."):
    """Return a callable that mimics a HuggingFace text-generation pipeline."""
    mock = MagicMock()
    mock.return_value = [{"generated_text": response}]
    return mock


# ---------------------------------------------------------------------------
# 1. load_pdf
# ---------------------------------------------------------------------------

def test_load_pdf_valid():
    """load_pdf returns a non-empty string for a valid PDF."""
    from src.extractor import load_pdf
    text = load_pdf(SAMPLE_PDF)
    assert isinstance(text, str)
    assert len(text) > 0


def test_load_pdf_missing():
    """load_pdf raises FileNotFoundError for a non-existent path."""
    from src.extractor import load_pdf
    with pytest.raises(FileNotFoundError):
        load_pdf("/nonexistent/path/file.pdf")


def test_load_pdf_wrong_ext(tmp_path):
    """load_pdf raises ValueError when the file is not a PDF."""
    from src.extractor import load_pdf
    txt_file = tmp_path / "doc.txt"
    txt_file.write_text("hello")
    with pytest.raises(ValueError):
        load_pdf(str(txt_file))


# ---------------------------------------------------------------------------
# 2. zero_shot_prompt
# ---------------------------------------------------------------------------

def test_zero_shot_prompt_returns_str():
    """zero_shot_prompt returns a non-empty string."""
    from src.extractor import zero_shot_prompt
    result = zero_shot_prompt(SAMPLE_TEXT, "encryption")
    assert isinstance(result, str)
    assert len(result) > 0
    assert "encryption" in result


# ---------------------------------------------------------------------------
# 3. few_shot_prompt
# ---------------------------------------------------------------------------

def test_few_shot_prompt_has_examples():
    """few_shot_prompt output contains 'Example' indicating few-shot structure."""
    from src.extractor import few_shot_prompt
    result = few_shot_prompt(SAMPLE_TEXT, "authentication")
    assert "Example" in result
    assert "authentication" in result


# ---------------------------------------------------------------------------
# 4. chain_of_thought_prompt
# ---------------------------------------------------------------------------

def test_chain_of_thought_prompt_has_steps():
    """chain_of_thought_prompt output contains step-by-step reasoning markers."""
    from src.extractor import chain_of_thought_prompt
    result = chain_of_thought_prompt(SAMPLE_TEXT, "logging_and_monitoring")
    assert "Step" in result
    assert "logging_and_monitoring" in result


# ---------------------------------------------------------------------------
# 5. extract_kdes
# ---------------------------------------------------------------------------

def test_extract_kdes_structure():
    """extract_kdes returns a nested dict with 'name' and 'requirements' keys."""
    from src.extractor import extract_kdes, zero_shot_prompt, KDE_NAMES

    fake_pipe = _make_fake_pipeline("1. Encrypt all data at rest.")
    with patch("src.extractor.get_llm_pipeline", return_value=fake_pipe):
        result = extract_kdes(SAMPLE_TEXT, zero_shot_prompt)

    assert isinstance(result, dict)
    assert len(result) == len(KDE_NAMES)
    for key, val in result.items():
        assert "name" in val
        assert "requirements" in val
        assert isinstance(val["requirements"], list)


# ---------------------------------------------------------------------------
# 6. collect_llm_output
# ---------------------------------------------------------------------------

def test_collect_llm_output_appends(tmp_path):
    """collect_llm_output writes a formatted entry to the log file."""
    from src.extractor import collect_llm_output
    log_path = str(tmp_path / "llm_log.txt")

    collect_llm_output(
        llm_name="google/gemma-3-1b-it",
        prompt="What are the encryption requirements?",
        prompt_type="zero-shot",
        llm_output="1. Use AES-256.",
        log_path=log_path,
    )

    with open(log_path) as f:
        content = f.read()

    assert "*LLM Name*" in content
    assert "google/gemma-3-1b-it" in content
    assert "*Prompt Used*" in content
    assert "*Prompt Type*" in content
    assert "zero-shot" in content
    assert "*LLM Output*" in content
    assert "1. Use AES-256." in content


# ---------------------------------------------------------------------------
# 6b. run_extraction (orchestrator)
# ---------------------------------------------------------------------------

def test_run_extraction_writes_yaml(tmp_path):
    """run_extraction creates a YAML file containing KDE data."""
    from src.extractor import run_extraction, zero_shot_prompt

    yaml_out = str(tmp_path / "output.yaml")
    log_out = str(tmp_path / "llm.txt")

    fake_pipe = _make_fake_pipeline("1. Encrypt all data at rest.")

    with patch("src.extractor.get_llm_pipeline", return_value=fake_pipe):
        result = run_extraction(
            pdf_path=SAMPLE_PDF,
            prompt_fn=zero_shot_prompt,
            prompt_type="zero-shot",
            output_yaml=yaml_out,
            log_txt=log_out,
        )

    assert os.path.isfile(yaml_out)
    with open(yaml_out) as f:
        loaded = yaml.safe_load(f)
    assert isinstance(loaded, dict)
    assert len(loaded) > 0
