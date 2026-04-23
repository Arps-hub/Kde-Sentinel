"""Task-3: Map KDE differences to Kubescape controls and run the scanner."""

import json
import os
import re
import shutil
import subprocess

import pandas as pd

from src.utils import (
    NO_ELEMENT_DIFF,
    NO_REQ_DIFF,
    validate_file_exists,
    validate_path_exists,
    write_text,
)

# ---------------------------------------------------------------------------
# Kubescape control mapping
# Maps KDE element names / keywords to Kubescape control IDs.
# Full control list: https://kubescape.io/docs/controls/
# ---------------------------------------------------------------------------
KUBESCAPE_CONTROL_MAP: dict = {
    "access_control": ["C-0036", "C-0056", "C-0058"],
    "authentication": ["C-0036", "C-0057", "C-0221"],
    "authorization": ["C-0036", "C-0056", "C-0041"],
    "data_protection": ["C-0034", "C-0087"],
    "encryption": ["C-0034", "C-0087", "C-0096"],
    "logging_and_monitoring": ["C-0009", "C-0015", "C-0048"],
    "network_security": ["C-0044", "C-0065", "C-0260"],
    "patch_management": ["C-0078", "C-0086"],
    "privileged_access": ["C-0036", "C-0042", "C-0055"],
    "vulnerability_management": ["C-0078", "C-0080", "C-0086"],
}

KUBESCAPE_KEYWORD_CONTROL_MAP: dict = {
    r"\b(audit|log|logging|monitor|alert)\b": ["C-0009", "C-0015", "C-0048"],
    r"\b(rbac|role|cluster_admin|service_account|service_accounts|permission|privilege|privileged|wildcard|bind|impersonate|escalate|authorization|access)\b": ["C-0036", "C-0056", "C-0058"],
    r"\b(secret|secrets|encrypt|encrypted|encryption|kms|tls|https|certificate|certificates)\b": ["C-0034", "C-0087", "C-0096"],
    r"\b(network|endpoint|public|private|cidr|firewall|metadata|imds|port|ports)\b": ["C-0044", "C-0065", "C-0260"],
    r"\b(vulnerability|vulnerabilities|image|images|container|registry|ecr|scan|patch|update)\b": ["C-0078", "C-0080", "C-0086"],
    r"\b(kubelet|kubeconfig|config_file|configuration_file|ownership|permissions|anonymous|client_ca|read_only|kernel|iptables)\b": ["C-0036", "C-0042", "C-0055"],
}

KUBESCAPE_PATH_ENV_VAR = "KUBESCAPE_PATH"


# ---------------------------------------------------------------------------
# 1. Readers
# ---------------------------------------------------------------------------

def read_differing_elements(path: str) -> list:
    """Read the element-names diff TEXT file from Task-2."""
    validate_file_exists(path)
    with open(path, "r", encoding="utf-8") as f:
        content = f.read().strip()
    if content == NO_ELEMENT_DIFF:
        return []
    return [line.strip() for line in content.splitlines() if line.strip()]


def read_differing_requirements(path: str) -> list:
    """Read the requirements diff TEXT file from Task-2.

    Supports the 4-column rubric format
    ``NAME,ABSENT-IN-<FILE>,PRESENT-IN-<FILE>,REQ`` and returns a list of
    ``(name, absent_in, present_in, req)`` tuples. ``req`` may be the literal
    ``"NA"`` when the whole KDE is missing from one side.
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
        parts = line.split(",", 3)
        if len(parts) == 4:
            result.append((parts[0], parts[1], parts[2], parts[3]))
        elif len(parts) == 2:
            # Backwards-compat: legacy NAME,REQ format
            result.append((parts[0], "", "", parts[1]))
        else:
            result.append((parts[0], "", "", ""))
    return result


# ---------------------------------------------------------------------------
# 2. Control mapper
# ---------------------------------------------------------------------------

def map_to_controls(elements: list) -> list:
    """Map differing element names to Kubescape control IDs."""
    controls = set()
    for elem in elements:
        key = elem.strip().lower().replace(" ", "_").replace("-", "_")
        mapped = KUBESCAPE_CONTROL_MAP.get(key)
        if mapped:
            controls.update(mapped)
        else:
            for known_key, known_controls in KUBESCAPE_CONTROL_MAP.items():
                if known_key in key or key in known_key:
                    controls.update(known_controls)
        for pattern, keyword_controls in KUBESCAPE_KEYWORD_CONTROL_MAP.items():
            if re.search(pattern, key):
                controls.update(keyword_controls)
    return sorted(controls)


# ---------------------------------------------------------------------------
# 3. Kubescape runner
# ---------------------------------------------------------------------------

def _normalize_kubescape_path(path: str) -> str:
    """Return a normalized absolute path for a kubescape candidate."""
    return os.path.abspath(os.path.expandvars(os.path.expanduser(path)))


def _iter_kubescape_candidates(kubescape_path: str = None) -> list[str]:
    """Return unique kubescape candidate paths in lookup order."""
    candidates: list[str] = []

    def add(path: str) -> None:
        if not path:
            return
        normalized = _normalize_kubescape_path(path)
        if normalized not in candidates:
            candidates.append(normalized)

    add(kubescape_path)
    add(os.environ.get(KUBESCAPE_PATH_ENV_VAR))

    found = shutil.which("kubescape")
    if found:
        add(found)

    project_root = os.path.dirname(os.path.dirname(__file__))
    add(os.path.join(project_root, "kubescape.exe"))
    add(os.path.join(project_root, "kubescape"))

    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        add(os.path.join(local_app_data, "Microsoft", "WinGet", "Links", "kubescape.exe"))
        add(os.path.join(local_app_data, "Microsoft", "WindowsApps", "kubescape.exe"))

        winget_base = os.path.join(local_app_data, "Microsoft", "WinGet", "Packages")
        if os.path.isdir(winget_base):
            for entry in os.listdir(winget_base):
                if "kubescape" in entry.lower():
                    add(os.path.join(winget_base, entry, "kubescape.exe"))

    program_files = os.environ.get("ProgramFiles")
    if program_files:
        add(os.path.join(program_files, "Kubescape", "kubescape.exe"))

    return candidates


def _find_kubescape_binary(kubescape_path: str = None) -> str | None:
    """Return the first existing kubescape binary path, if any."""
    for candidate in _iter_kubescape_candidates(kubescape_path):
        if os.path.isfile(candidate):
            return candidate
    return None


def _resolve_kubescape_binary(kubescape_path: str = None) -> str:
    """Resolve kubescape to a concrete executable path or raise a helpful error."""
    binary = _find_kubescape_binary(kubescape_path)
    if binary:
        return binary

    checked = "\n".join(f"  - {path}" for path in _iter_kubescape_candidates(kubescape_path))
    checked_block = f"\nChecked locations:\n{checked}" if checked else ""
    raise RuntimeError(
        "Kubescape executable could not be found.\n"
        "Fix this by either adding kubescape to PATH, passing --kubescape-path, "
        f"or setting {KUBESCAPE_PATH_ENV_VAR}.{checked_block}"
    )


def check_kubescape_installed(kubescape_path: str = None) -> bool:
    """Return True if the kubescape binary responds to `version`."""
    binary = _resolve_kubescape_binary(kubescape_path)
    try:
        result = subprocess.run(
            [binary, "version"],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except PermissionError as exc:
        raise RuntimeError(
            f"Kubescape was found at '{binary}' but could not be executed due to a "
            "permission denied error. Try launching the same executable from a normal "
            "terminal, or pass a different binary with --kubescape-path."
        ) from exc
    except FileNotFoundError as exc:
        raise RuntimeError(
            f"Kubescape was resolved to '{binary}' but the executable could not be "
            "started. Reinstall kubescape or pass a valid binary with --kubescape-path."
        ) from exc

    if result.returncode == 0:
        return True

    raise RuntimeError(
        f"Kubescape was found at '{binary}' but returned exit code {result.returncode}.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )


def _resolve_scan_path(zip_path: str) -> str:
    """If zip_path is a .zip, extract it and return the path to scan."""
    import zipfile

    if not zip_path.lower().endswith(".zip"):
        return zip_path

    extract_dir = zip_path[:-4]
    if not os.path.isdir(extract_dir):
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(extract_dir)
    return extract_dir


def run_kubescape(zip_path: str, controls: list, kubescape_path: str = None) -> str:
    """Execute Kubescape and return the raw JSON output string."""
    check_kubescape_installed(kubescape_path)
    validate_path_exists(zip_path)
    binary = _resolve_kubescape_binary(kubescape_path)
    scan_path = _resolve_scan_path(zip_path)

    if controls:
        cmd = [binary, "scan", "control", ",".join(controls), scan_path] + [
            "--format",
            "json",
            "--logger",
            "warning",
        ]
    else:
        cmd = [binary, "scan", scan_path, "--format", "json", "--logger", "warning"]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=300,
    )

    if result.returncode not in (0, 1):
        raise RuntimeError(
            f"Kubescape exited with code {result.returncode}.\n"
            f"stderr: {result.stderr}"
        )

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
    """Parse Kubescape v4 JSON output into a pandas DataFrame."""
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
        data = json.loads(raw_json)

    rows = []

    resource_path: dict = {}
    for res in data.get("resources", []):
        rid = res.get("resourceID", "")
        rel = res.get("source", {}).get("relativePath", "")
        if rid and rel:
            resource_path[rid] = rel

    summary_controls: dict = data.get("summaryDetails", {}).get("controls", {})
    results = data.get("results", [])

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
                rows.append(
                    {
                        "FilePath": fp,
                        "Severity": severity,
                        "Control name": control_name,
                        "Failed resources": failed_count,
                        "All Resources": all_count,
                        "Compliance score": compliance,
                    }
                )
        else:
            rows.append(
                {
                    "FilePath": "",
                    "Severity": severity,
                    "Control name": control_name,
                    "Failed resources": failed_count,
                    "All Resources": all_count,
                    "Compliance score": compliance,
                }
            )

    if not rows:
        rows.append(
            {
                "FilePath": "",
                "Severity": "",
                "Control name": "",
                "Failed resources": 0,
                "All Resources": 0,
                "Compliance score": 0.0,
            }
        )

    return pd.DataFrame(
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


# ---------------------------------------------------------------------------
# 5. CSV writer
# ---------------------------------------------------------------------------

def save_results_csv(df: pd.DataFrame, path: str) -> None:
    """Write the scan results DataFrame to a CSV file."""
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
    kubescape_path: str = None,
) -> pd.DataFrame:
    """Full Task-3 pipeline: read diffs, map controls, scan, and save CSV."""
    elements = read_differing_elements(elements_txt)
    req_tuples = read_differing_requirements(reqs_txt)

    all_elements = list(set(elements + [item[0] for item in req_tuples]))
    controls = map_to_controls(all_elements)

    if controls_txt:
        if not controls:
            write_text("NO DIFFERENCES FOUND\n", controls_txt)
        else:
            write_text("\n".join(controls) + "\n", controls_txt)

    raw_json = run_kubescape(zip_path, controls, kubescape_path=kubescape_path)
    df = parse_kubescape_output(raw_json)
    save_results_csv(df, out_csv)
    return df
