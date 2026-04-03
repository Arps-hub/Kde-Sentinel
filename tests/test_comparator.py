"""Tests for src/comparator.py — one test per function."""

import os
import pytest
import yaml

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")

# Minimal KDE dicts used across tests
DOC1 = {
    "encryption": {"name": "encryption", "requirements": ["Use AES-256.", "Use TLS 1.2."]},
    "authentication": {"name": "authentication", "requirements": ["Use MFA."]},
    "access_control": {"name": "access_control", "requirements": ["Restrict to RBAC."]},
}

DOC2 = {
    "encryption": {"name": "encryption", "requirements": ["Use AES-256."]},  # missing req
    "authentication": {"name": "authentication", "requirements": ["Use MFA."]},
    "network_security": {"name": "network_security", "requirements": ["Use firewall."]},
}


def _write_yaml(path: str, data: dict) -> None:
    with open(path, "w") as f:
        yaml.dump(data, f)


# ---------------------------------------------------------------------------
# 1. load_and_validate_yaml
# ---------------------------------------------------------------------------

def test_load_and_validate_yaml_valid(tmp_path):
    """load_and_validate_yaml returns the correct dict for a valid file."""
    from src.comparator import load_and_validate_yaml
    path = str(tmp_path / "test.yaml")
    _write_yaml(path, DOC1)
    result = load_and_validate_yaml(path)
    assert result == DOC1


def test_load_and_validate_yaml_not_dict(tmp_path):
    """load_and_validate_yaml raises ValueError when top-level is a list."""
    from src.comparator import load_and_validate_yaml
    path = str(tmp_path / "bad.yaml")
    with open(path, "w") as f:
        f.write("- item1\n- item2\n")
    with pytest.raises(ValueError):
        load_and_validate_yaml(path)


# ---------------------------------------------------------------------------
# 2. diff_element_names
# ---------------------------------------------------------------------------

def test_diff_element_names_no_diff():
    """diff_element_names returns an empty list when both dicts have same keys."""
    from src.comparator import diff_element_names
    result = diff_element_names(DOC1, DOC1)
    assert result == []


def test_diff_element_names_missing_key():
    """diff_element_names reports keys exclusive to one of the dicts."""
    from src.comparator import diff_element_names
    result = diff_element_names(DOC1, DOC2)
    assert "access_control" in result   # only in DOC1
    assert "network_security" in result  # only in DOC2
    assert "encryption" not in result   # shared


# ---------------------------------------------------------------------------
# 3. diff_requirements
# ---------------------------------------------------------------------------

def test_diff_requirements_identical():
    """diff_requirements returns empty list for identical dicts."""
    from src.comparator import diff_requirements
    result = diff_requirements(DOC1, DOC1)
    assert result == []


def test_diff_requirements_extra_req():
    """diff_requirements catches a requirement present in only one document."""
    from src.comparator import diff_requirements
    result = diff_requirements(DOC1, DOC2)
    # DOC1.encryption has "Use TLS 1.2." but DOC2.encryption does not
    names = [t[0] for t in result]
    reqs = [t[1] for t in result]
    assert "encryption" in names
    assert "Use TLS 1.2." in reqs


# ---------------------------------------------------------------------------
# 4. write_differing_elements
# ---------------------------------------------------------------------------

def test_write_differing_elements_content(tmp_path):
    """write_differing_elements writes element names, one per line."""
    from src.comparator import write_differing_elements
    path = str(tmp_path / "elements.txt")
    write_differing_elements(["access_control", "network_security"], path)
    with open(path) as f:
        lines = [l.strip() for l in f.readlines() if l.strip()]
    assert "access_control" in lines
    assert "network_security" in lines


def test_write_differing_elements_no_diff(tmp_path):
    """write_differing_elements writes the sentinel string when list is empty."""
    from src.comparator import write_differing_elements
    path = str(tmp_path / "elements.txt")
    write_differing_elements([], path)
    with open(path) as f:
        content = f.read()
    assert "NO DIFFERENCES IN REGARDS TO ELEMENT NAMES" in content


# ---------------------------------------------------------------------------
# 5. write_differing_requirements
# ---------------------------------------------------------------------------

def test_write_differing_requirements_format(tmp_path):
    """write_differing_requirements writes 'NAME,REQU' formatted lines."""
    from src.comparator import write_differing_requirements
    path = str(tmp_path / "reqs.txt")
    write_differing_requirements([("encryption", "Use TLS 1.2.")], path)
    with open(path) as f:
        content = f.read()
    assert "encryption,Use TLS 1.2." in content


def test_write_differing_requirements_no_diff(tmp_path):
    """write_differing_requirements writes sentinel when no differences."""
    from src.comparator import write_differing_requirements
    path = str(tmp_path / "reqs.txt")
    write_differing_requirements([], path)
    with open(path) as f:
        content = f.read()
    assert "NO DIFFERENCES IN REGARDS TO ELEMENT REQUIREMENTS" in content


# ---------------------------------------------------------------------------
# 6. run_comparison (orchestrator)
# ---------------------------------------------------------------------------

def test_run_comparison_integration(tmp_path):
    """run_comparison creates both output TEXT files from two YAML inputs."""
    from src.comparator import run_comparison

    yaml1 = str(tmp_path / "doc1.yaml")
    yaml2 = str(tmp_path / "doc2.yaml")
    out_elem = str(tmp_path / "elements.txt")
    out_req = str(tmp_path / "reqs.txt")

    _write_yaml(yaml1, DOC1)
    _write_yaml(yaml2, DOC2)

    run_comparison(yaml1, yaml2, out_elem, out_req)

    assert os.path.isfile(out_elem)
    assert os.path.isfile(out_req)

    with open(out_elem) as f:
        elem_content = f.read()
    with open(out_req) as f:
        req_content = f.read()

    # DOC1 vs DOC2 have different element names and different requirements
    assert "NO DIFFERENCES" not in elem_content or "NO DIFFERENCES" not in req_content
