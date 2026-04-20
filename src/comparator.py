"""Task-2: Compare two KDE YAML files and report differences."""

import os

from src.utils import load_yaml, write_text, validate_file_exists, NO_ELEMENT_DIFF, NO_REQ_DIFF


def _label(path: str) -> str:
    """Return the filename (without directory) used in ABSENT-IN/PRESENT-IN labels."""
    return os.path.basename(path) if path else ""


# ---------------------------------------------------------------------------
# 1. YAML loader with validation
# ---------------------------------------------------------------------------

def load_and_validate_yaml(path: str) -> dict:
    """Load a KDE YAML file and validate its structure.

    Parameters
    ----------
    path : str
        Path to the YAML file produced by Task-1.

    Returns
    -------
    dict
        Parsed YAML data.

    Raises
    ------
    FileNotFoundError
        If the file does not exist.
    ValueError
        If the top-level structure is not a dict.
    """
    validate_file_exists(path)
    data = load_yaml(path)
    if not isinstance(data, dict):
        raise ValueError(
            f"Expected a dict at the top level of '{path}', got {type(data).__name__}"
        )
    return data


# ---------------------------------------------------------------------------
# 2. Element-name diff
# ---------------------------------------------------------------------------

def diff_element_names(doc1: dict, doc2: dict) -> list:
    """Return element names that differ between the two KDE dicts.

    An element name is considered "different" when it is present in one
    document but absent in the other.

    Parameters
    ----------
    doc1 : dict
        KDE dict from document 1.
    doc2 : dict
        KDE dict from document 2.

    Returns
    -------
    list[str]
        Sorted list of element names that are exclusive to one of the dicts.
    """
    keys1 = set(doc1.keys())
    keys2 = set(doc2.keys())
    diff = keys1.symmetric_difference(keys2)
    return sorted(diff)


# ---------------------------------------------------------------------------
# 3. Requirements diff
# ---------------------------------------------------------------------------

def diff_requirements(
    doc1: dict,
    doc2: dict,
    file1: str = "file1",
    file2: str = "file2",
) -> list:
    """Return 4-tuples describing every KDE-level and requirement-level difference.

    Each tuple has the form ``(name, absent_in, present_in, req)`` where:

    - ``req`` is the literal string ``"NA"`` when the whole KDE is missing from one file.
    - ``req`` is the specific requirement text when the KDE is shared but the requirement
      is only in one side.
    - ``absent_in`` / ``present_in`` are filenames (basename) of the two YAML inputs.

    Parameters
    ----------
    doc1, doc2 : dict
        KDE dicts to compare.
    file1, file2 : str
        Filenames (or paths) that will appear in the ABSENT-IN / PRESENT-IN columns.

    Returns
    -------
    list[tuple[str, str, str, str]]
    """
    label1 = _label(file1)
    label2 = _label(file2)

    keys1 = set(doc1.keys())
    keys2 = set(doc2.keys())
    diffs = []

    for key in sorted(keys1 - keys2):
        diffs.append((key, label2, label1, "NA"))
    for key in sorted(keys2 - keys1):
        diffs.append((key, label1, label2, "NA"))

    for key in sorted(keys1 & keys2):
        reqs1 = set(doc1[key].get("requirements", []))
        reqs2 = set(doc2[key].get("requirements", []))
        for req in sorted(reqs1 - reqs2):
            diffs.append((key, label2, label1, req))
        for req in sorted(reqs2 - reqs1):
            diffs.append((key, label1, label2, req))

    return diffs


# ---------------------------------------------------------------------------
# 4. Writers
# ---------------------------------------------------------------------------

def write_differing_elements(names: list, path: str) -> None:
    """Write differing element names to a TEXT file.

    Parameters
    ----------
    names : list[str]
        Output of diff_element_names().
    path : str
        Output file path.
    """
    if not names:
        content = NO_ELEMENT_DIFF + "\n"
    else:
        content = "\n".join(names) + "\n"
    write_text(content, path)


def write_differing_requirements(tuples: list, path: str) -> None:
    """Write differing-requirement tuples to a TEXT file.

    Each line is formatted as ``NAME,ABSENT-IN-<FILENAME>,PRESENT-IN-<FILENAME>,REQ``
    per the Task-2 rubric. ``REQ`` is ``NA`` when the whole KDE is missing from
    one side.

    Parameters
    ----------
    tuples : list[tuple[str, str, str, str]]
        Output of diff_requirements().
    path : str
        Output file path.
    """
    if not tuples:
        content = NO_REQ_DIFF + "\n"
    else:
        lines = [
            f"{name},ABSENT-IN-{absent},PRESENT-IN-{present},{req}"
            for name, absent, present, req in tuples
        ]
        content = "\n".join(lines) + "\n"
    write_text(content, path)


# ---------------------------------------------------------------------------
# 5. Orchestrator
# ---------------------------------------------------------------------------

def run_comparison(
    yaml1: str,
    yaml2: str,
    out_elements: str,
    out_reqs: str,
) -> None:
    """Full Task-2 pipeline: load YAMLs → diff → write TEXT files.

    Parameters
    ----------
    yaml1 : str
        Path to the first KDE YAML file.
    yaml2 : str
        Path to the second KDE YAML file.
    out_elements : str
        Path for the element-names diff TEXT file.
    out_reqs : str
        Path for the requirements diff TEXT file.
    """
    doc1 = load_and_validate_yaml(yaml1)
    doc2 = load_and_validate_yaml(yaml2)

    element_diffs = diff_element_names(doc1, doc2)
    req_diffs = diff_requirements(doc1, doc2, yaml1, yaml2)

    write_differing_elements(element_diffs, out_elements)
    write_differing_requirements(req_diffs, out_reqs)
