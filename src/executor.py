"""Task-3: Map KDE differences to Kubescape controls and run the scanner."""

import json
import os
import subprocess

import pandas as pd

from src.utils import (
    write_text,
    validate_file_exists,
    validate_path_exists,
    NO_ELEMENT_DIFF,
    NO_REQ_DIFF,
)

# ---------------------------------------------------------------------------
# Kubescape control mapping
# Maps KDE element names / keywords to Kubescape control IDs.
# Full control list: https://kubescape.io/docs/controls/
# ---------------------------------------------------------------------------
KUBESCAPE_CONTROL_MAP: dict = {
    "access_control":         ["C-0036", "C-0056", "C-0058"],
    "authentication":         ["C-0036", "C-0057", "C-0221"],
    "authorization":          ["C-0036", "C-0056", "C-0041"],
    "data_protection":        ["C-0034", "C-0087"],
    "encryption":             ["C-0034", "C-0087", "C-0096"],
    "logging_and_monitoring": ["C-0009", "C-0015", "C-0048"],
    "network_security":       ["C-0044", "C-0065", "C-0260"],
    "patch_management":       ["C-0078", "C-0086"],
    "privileged_access":      ["C-0036", "C-0042", "C-0055"],
    "vulnerability_management": ["C-0078", "C-0080", "C-0086"],
}


# ---------------------------------------------------------------------------
# 1. Readers
# ---------------------------------------------------------------------------

def read_differing_elements(path: str) -> list:
    """Read the element-names diff TEXT file from Task-2.

    Parameters
    ----------
    path : str
        Path to the file written by comparator.write_differing_elements().

    Returns
    -------
    list[str]
        List of differing element names, or an empty list when the file
        contains the "NO DIFFERENCES" sentinel.
    """
    validate_file_exists(path)
    with open(path, "r", encoding="utf-8") as f:
        content = f.read().strip()
    if content == NO_ELEMENT_DIFF:
        return []
    return [line.strip() for line in content.splitlines() if line.strip()]


def read_differing_requirements(path: str) -> list:
    """Read the requirements diff TEXT file from Task-2.

    Parameters
    ----------
    path : str
        Path to the file written by comparator.write_differing_requirements().

    Returns
    -------
    list[tuple[str, str]]
        List of (element_name, requirement_text) tuples.
    """
    validate_file_exists(path)
    with open(path, "r", encoding="utf-8") as f:
        content = f.read().strip()
    if content == NO_REQ_DIFF:
        return []
    result = []
    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue
        idx = line.index(",") if "," in line else -1
        if idx == -1:
            result.append((line, ""))
        else:
            result.append((line[:idx], line[idx + 1:]))
    return result


# ---------------------------------------------------------------------------
# 2. Control mapper
# ---------------------------------------------------------------------------

def map_to_controls(elements: list) -> list:
    """Map differing element names to Kubescape control IDs.

    Parameters
    ----------
    elements : list[str]
        List of element names (from read_differing_elements or derived from
        read_differing_requirements).

    Returns
    -------
    list[str]
        Deduplicated, sorted list of Kubescape control IDs.
    """
    controls = set()
    for elem in elements:
        key = elem.strip().lower().replace(" ", "_").replace("-", "_")
        mapped = KUBESCAPE_CONTROL_MAP.get(key)
        if mapped:
            controls.update(mapped)
        else:
            # Fuzzy fallback: partial match on known keys
            for k, v in KUBESCAPE_CONTROL_MAP.items():
                if k in key or key in k:
                    controls.update(v)
    return sorted(controls)


# ---------------------------------------------------------------------------
# 3. Kubescape runner
# ---------------------------------------------------------------------------

def _find_kubescape_binary() -> str:
    """Return the path to the kubescape binary.

    Search order:
    1. System PATH
    2. Project root directory (place kubescape / kubescape.exe next to main.py)
    3. WinGet packages directory — scans all sub-folders named *kubescape* so it
       works regardless of the package hash suffix in the folder name.
    """
    import shutil

    # 1. Check PATH
    found = shutil.which("kubescape")
    if found:
        return found

    # 2. Check project root
    project_root = os.path.dirname(os.path.dirname(__file__))
    for name in ("kubescape", "kubescape.exe"):
        local = os.path.join(project_root, name)
        if os.path.isfile(local):
            return local

    # 3. WinGet packages directory (Windows) — dynamic scan, no hardcoded hash
    winget_base = os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages")
    if os.path.isdir(winget_base):
        for entry in os.listdir(winget_base):
            if "kubescape" in entry.lower():
                candidate = os.path.join(winget_base, entry, "kubescape.exe")
                if os.path.isfile(candidate):
                    return candidate

    return "kubescape"  # fall back — will fail with a clear error message


def check_kubescape_installed() -> bool:
    """Return True if the kubescape binary is on PATH and responds to version.

    Raises
    ------
    RuntimeError
        If kubescape is not found or does not respond.
    """
    binary = _find_kubescape_binary()
    try:
        result = subprocess.run(
            [binary, "version"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode == 0:
            return True
        raise RuntimeError(
            f"kubescape returned exit code {result.returncode}: {result.stderr}"
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            "Kubescape is not installed or not on PATH.\n"
            "Install on Linux/Mac: "
            "curl -s https://raw.githubusercontent.com/kubescape/kubescape/master/install.sh | /bin/bash\n"
            "Install on Windows: winget install kubescape  OR  choco install kubescape"
        ) from exc


def _resolve_scan_path(zip_path: str) -> str:
    """If zip_path is a .zip, extract it and return the path to scan."""
    import zipfile
    if not zip_path.lower().endswith(".zip"):
        return zip_path
    extract_dir = zip_path[:-4]  # strip .zip
    if not os.path.isdir(extract_dir):
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(extract_dir)
    return extract_dir


def run_kubescape(zip_path: str, controls: list) -> str:
    """Execute Kubescape and return the raw JSON output string.

    Parameters
    ----------
    zip_path : str
        Path to project-yamls.zip (or an unpacked directory).
    controls : list[str]
        List of control IDs to scan. If empty, all controls are scanned.

    Returns
    -------
    str
        Raw JSON string from kubescape stdout.

    Raises
    ------
    RuntimeError
        If Kubescape fails or is not installed.
    """
    check_kubescape_installed()
    validate_path_exists(zip_path)
    binary = _find_kubescape_binary()
    scan_path = _resolve_scan_path(zip_path)

    if controls:
        cmd = [binary, "scan", "control"] + controls + [
            scan_path, "--format", "json", "--logger", "warning"
        ]
    else:
        cmd = [binary, "scan", scan_path, "--format", "json", "--logger", "warning"]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=300,
    )

    if result.returncode not in (0, 1):  # kubescape exits 1 when controls fail
        raise RuntimeError(
            f"Kubescape exited with code {result.returncode}.\n"
            f"stderr: {result.stderr}"
        )

    # Kubescape v4 outputs one JSON line followed by a plain-text summary line.
    # Extract only the first line that starts with '{'.
    json_line = ""
    for line in result.stdout.splitlines():
        line = line.strip()
        if line.startswith("{"):
            json_line = line
            break
    if not json_line:
        raise RuntimeError(
            "Kubescape produced no JSON output.\n"
            f"stdout: {result.stdout[:500]}\nstderr: {result.stderr[:500]}"
        )
    return json_line


# ---------------------------------------------------------------------------
# 4. Output parser
# ---------------------------------------------------------------------------

def parse_kubescape_output(raw_json: str) -> pd.DataFrame:
    """Parse Kubescape v4 JSON output into a pandas DataFrame.

    Parameters
    ----------
    raw_json : str
        JSON string returned by run_kubescape().

    Returns
    -------
    pd.DataFrame
        Columns: FilePath, Severity, Control name,
                 Failed resources, All Resources, Compliance score.
    """
    # Kubescape v4 may emit one JSON object per line; take the first valid one.
    data = None
    for line in raw_json.splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                data = json.loads(line)
                break
            except json.JSONDecodeError:
                continue
    if data is None:
        data = json.loads(raw_json)  # fallback: try full string

    rows = []

    # Build resource_id → file_path lookup from top-level "resources"
    resource_path: dict = {}
    for res in data.get("resources", []):
        rid = res.get("resourceID", "")
        rel = res.get("source", {}).get("relativePath", "")
        if rid and rel:
            resource_path[rid] = rel

    # Build per-control summary from summaryDetails.controls
    summary_controls: dict = data.get("summaryDetails", {}).get("controls", {})

    # results: list of {resourceID, controls: [{controlID, name, status, severity}]}
    results = data.get("results", [])

    # Index failed resource paths by control ID
    from collections import defaultdict
    failed_paths: dict = defaultdict(list)
    for entry in results:
        rid = entry.get("resourceID", "")
        fpath = resource_path.get(rid, rid)
        for ctrl in entry.get("controls", []):
            status = ctrl.get("status", {})
            if isinstance(status, dict):
                status_val = status.get("status", "")
            else:
                status_val = str(status)
            if status_val == "failed":
                failed_paths[ctrl.get("controlID", "")].append(fpath)

    # One row per (control, failed file)
    for ctrl_id, ctrl_info in summary_controls.items():
        control_name = ctrl_info.get("name", ctrl_id)
        severity = ctrl_info.get("severity", "")
        counters = ctrl_info.get("ResourceCounters", {})
        failed_count = counters.get("failedResources", 0)
        all_count = counters.get("passedResources", 0) + failed_count
        compliance = ctrl_info.get("complianceScore", 0.0)

        paths = failed_paths.get(ctrl_id, [])
        if paths:
            for fp in paths:
                rows.append({
                    "FilePath": fp,
                    "Severity": severity,
                    "Control name": control_name,
                    "Failed resources": failed_count,
                    "All Resources": all_count,
                    "Compliance score": compliance,
                })
        else:
            rows.append({
                "FilePath": "",
                "Severity": severity,
                "Control name": control_name,
                "Failed resources": failed_count,
                "All Resources": all_count,
                "Compliance score": compliance,
            })

    if not rows:
        rows.append({
            "FilePath": "",
            "Severity": "",
            "Control name": "",
            "Failed resources": 0,
            "All Resources": 0,
            "Compliance score": 0.0,
        })

    df = pd.DataFrame(
        rows,
        columns=[
            "FilePath",
            "Severity",
            "Control name",
            "Failed resources",
            "All Resources",
            "Compliance score",
        ],
    )
    return df


# ---------------------------------------------------------------------------
# 5. CSV writer
# ---------------------------------------------------------------------------

def save_results_csv(df: pd.DataFrame, path: str) -> None:
    """Write the scan results DataFrame to a CSV file.

    Parameters
    ----------
    df : pd.DataFrame
        Output of parse_kubescape_output().
    path : str
        Destination CSV file path.
    """
    from src.utils import ensure_dir
    ensure_dir(os.path.dirname(path) or ".")
    df.to_csv(path, index=False)


# ---------------------------------------------------------------------------
# 6. Orchestrator
# ---------------------------------------------------------------------------

def run_executor(
    elements_txt: str,
    reqs_txt: str,
    zip_path: str,
    out_csv: str,
    controls_txt: str = None,
) -> pd.DataFrame:
    """Full Task-3 pipeline: read diffs → map controls → scan → save CSV.

    Parameters
    ----------
    elements_txt : str
        Path to the element-names diff TEXT file (Task-2 output).
    reqs_txt : str
        Path to the requirements diff TEXT file (Task-2 output).
    zip_path : str
        Path to project-yamls.zip.
    out_csv : str
        Destination CSV path.
    controls_txt : str, optional
        Path where the resolved control IDs will be written (TEXT file).

    Returns
    -------
    pd.DataFrame
        Scan results.
    """
    elements = read_differing_elements(elements_txt)
    req_tuples = read_differing_requirements(reqs_txt)

    # Combine element names from both sources
    all_elements = list(set(elements + [t[0] for t in req_tuples]))
    controls = map_to_controls(all_elements)

    # Write controls TEXT file
    if controls_txt:
        if not controls:
            write_text("NO DIFFERENCES FOUND\n", controls_txt)
        else:
            write_text("\n".join(controls) + "\n", controls_txt)

    raw_json = run_kubescape(zip_path, controls)
    df = parse_kubescape_output(raw_json)
    save_results_csv(df, out_csv)
    return df
