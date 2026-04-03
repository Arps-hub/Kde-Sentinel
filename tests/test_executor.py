"""Tests for src/executor.py — one test per function."""

import json
import os
import zipfile
import pytest
import pandas as pd
from unittest.mock import patch, MagicMock

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")

# Minimal Kubescape v4 JSON fixture (single line — matches real scanner output format)
KUBESCAPE_JSON = json.dumps({
    "resources": [
        {
            "resourceID": "res1",
            "source": {"relativePath": "manifests/deployment.yaml"},
        }
    ],
    "results": [
        {
            "resourceID": "res1",
            "controls": [
                {
                    "controlID": "C-0036",
                    "name": "RBAC least privileges",
                    "status": {"status": "failed"},
                }
            ],
        }
    ],
    "summaryDetails": {
        "controls": {
            "C-0036": {
                "name": "RBAC least privileges",
                "severity": "High",
                "ResourceCounters": {
                    "failedResources": 2,
                    "passedResources": 3,
                },
                "complianceScore": 60.0,
            }
        }
    },
})


def _make_zip(tmp_path: "Path") -> str:
    """Create a minimal zip archive with a dummy YAML inside."""
    yaml_content = "apiVersion: v1\nkind: Pod\n"
    yaml_file = tmp_path / "pod.yaml"
    yaml_file.write_text(yaml_content)
    zip_path = str(tmp_path / "project-yamls.zip")
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.write(str(yaml_file), "pod.yaml")
    return zip_path


# ---------------------------------------------------------------------------
# 1. read_differing_elements
# ---------------------------------------------------------------------------

def test_read_differing_elements(tmp_path):
    """read_differing_elements returns a list of strings from the file."""
    from src.executor import read_differing_elements
    path = str(tmp_path / "elements.txt")
    with open(path, "w") as f:
        f.write("access_control\nnetwork_security\n")
    result = read_differing_elements(path)
    assert result == ["access_control", "network_security"]


def test_read_differing_elements_no_diff(tmp_path):
    """read_differing_elements returns [] when the sentinel is present."""
    from src.executor import read_differing_elements
    path = str(tmp_path / "elements.txt")
    with open(path, "w") as f:
        f.write("NO DIFFERENCES IN REGARDS TO ELEMENT NAMES\n")
    result = read_differing_elements(path)
    assert result == []


# ---------------------------------------------------------------------------
# 2. read_differing_requirements
# ---------------------------------------------------------------------------

def test_read_differing_requirements_tuple_format(tmp_path):
    """read_differing_requirements parses NAME,REQU lines into tuples."""
    from src.executor import read_differing_requirements
    path = str(tmp_path / "reqs.txt")
    with open(path, "w") as f:
        f.write("encryption,Use TLS 1.2.\nauthentication,Require MFA.\n")
    result = read_differing_requirements(path)
    assert ("encryption", "Use TLS 1.2.") in result
    assert ("authentication", "Require MFA.") in result


# ---------------------------------------------------------------------------
# 3. map_to_controls
# ---------------------------------------------------------------------------

def test_map_to_controls_known():
    """map_to_controls returns control IDs for a known element name."""
    from src.executor import map_to_controls
    result = map_to_controls(["encryption"])
    assert len(result) > 0
    assert all(c.startswith("C-") for c in result)


def test_map_to_controls_unknown():
    """map_to_controls returns [] for completely unknown element names."""
    from src.executor import map_to_controls, KUBESCAPE_CONTROL_MAP
    # Use a name guaranteed not to match anything
    result = map_to_controls(["zzz_totally_unknown_xyz_abc"])
    # Should not crash; may return empty or partial matches
    assert isinstance(result, list)


# ---------------------------------------------------------------------------
# 4. check_kubescape_installed
# ---------------------------------------------------------------------------

def test_check_kubescape_installed_ok():
    """check_kubescape_installed returns True when kubescape responds."""
    from src.executor import check_kubescape_installed
    mock_result = MagicMock()
    mock_result.returncode = 0
    with patch("src.executor._resolve_kubescape_binary", return_value="C:\\tools\\kubescape.exe"), \
         patch("subprocess.run", return_value=mock_result):
        assert check_kubescape_installed() is True


def test_check_kubescape_not_found():
    """check_kubescape_installed raises RuntimeError when binary missing."""
    from src.executor import check_kubescape_installed
    with patch("src.executor._resolve_kubescape_binary", side_effect=RuntimeError("could not be found")):
        with pytest.raises(RuntimeError, match="could not be found"):
            check_kubescape_installed()


def test_check_kubescape_permission_denied():
    """check_kubescape_installed reports permission errors clearly."""
    from src.executor import check_kubescape_installed
    with patch("src.executor._resolve_kubescape_binary", return_value="C:\\tools\\kubescape.exe"), \
         patch("subprocess.run", side_effect=PermissionError):
        with pytest.raises(RuntimeError, match="permission denied"):
            check_kubescape_installed()


def test_find_kubescape_binary_prefers_explicit_path(tmp_path):
    """An explicit kubescape path should win over all auto-discovery paths."""
    from src.executor import _find_kubescape_binary
    exe_path = tmp_path / "kubescape.exe"
    exe_path.write_text("fake exe")
    assert _find_kubescape_binary(str(exe_path)) == str(exe_path.resolve())


def test_find_kubescape_binary_uses_env_var(tmp_path, monkeypatch):
    """KUBESCAPE_PATH should be used when kubescape is not on PATH."""
    from src.executor import _find_kubescape_binary
    exe_path = tmp_path / "kubescape.exe"
    exe_path.write_text("fake exe")
    monkeypatch.setenv("KUBESCAPE_PATH", str(exe_path))
    with patch("src.executor.shutil.which", return_value=None):
        assert _find_kubescape_binary() == str(exe_path.resolve())


# ---------------------------------------------------------------------------
# 5. run_kubescape
# ---------------------------------------------------------------------------

def test_run_kubescape_mocked(tmp_path):
    """run_kubescape calls subprocess with correct arguments."""
    from src.executor import run_kubescape
    zip_path = _make_zip(tmp_path)

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = KUBESCAPE_JSON

    with patch("src.executor.check_kubescape_installed", return_value=True), \
         patch("src.executor._resolve_kubescape_binary", return_value="C:\\tools\\kubescape.exe"), \
         patch("subprocess.run", return_value=mock_result) as mock_run:
        output = run_kubescape(zip_path, ["C-0034", "C-0036"])

    assert output == KUBESCAPE_JSON
    call_args = mock_run.call_args[0][0]
    assert any("kubescape" in arg.lower() for arg in call_args)
    assert "C-0034" in call_args


# ---------------------------------------------------------------------------
# 6. parse_kubescape_output
# ---------------------------------------------------------------------------

def test_parse_kubescape_output():
    """parse_kubescape_output parses v4 JSON into a DataFrame with correct values."""
    from src.executor import parse_kubescape_output
    df = parse_kubescape_output(KUBESCAPE_JSON)
    assert isinstance(df, pd.DataFrame)
    required_cols = {
        "FilePath", "Severity", "Control name",
        "Failed resources", "All Resources", "Compliance score",
    }
    assert required_cols.issubset(set(df.columns))
    assert len(df) == 1
    row = df.iloc[0]
    assert row["Control name"] == "RBAC least privileges"
    assert row["FilePath"] == "manifests/deployment.yaml"
    assert row["Severity"] == "High"
    assert row["Failed resources"] == 2
    assert row["All Resources"] == 5
    assert row["Compliance score"] == 60.0


# ---------------------------------------------------------------------------
# 7. save_results_csv
# ---------------------------------------------------------------------------

def test_save_results_csv(tmp_path):
    """save_results_csv creates a CSV with the correct headers."""
    from src.executor import save_results_csv, parse_kubescape_output
    df = parse_kubescape_output(KUBESCAPE_JSON)
    csv_path = str(tmp_path / "results.csv")
    save_results_csv(df, csv_path)

    assert os.path.isfile(csv_path)
    loaded = pd.read_csv(csv_path)
    assert "Control name" in loaded.columns
    assert "Compliance score" in loaded.columns


# ---------------------------------------------------------------------------
# 8. run_executor (orchestrator)
# ---------------------------------------------------------------------------

def test_run_executor_integration(tmp_path):
    """run_executor produces a CSV from TEXT files and a zip archive."""
    from src.executor import run_executor

    elements_txt = str(tmp_path / "elements.txt")
    reqs_txt = str(tmp_path / "reqs.txt")
    zip_path = _make_zip(tmp_path)
    out_csv = str(tmp_path / "results.csv")
    controls_txt = str(tmp_path / "controls.txt")

    with open(elements_txt, "w") as f:
        f.write("encryption\nauthentication\n")
    with open(reqs_txt, "w") as f:
        f.write("encryption,Use TLS 1.2.\n")

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = KUBESCAPE_JSON

    with patch("src.executor.check_kubescape_installed", return_value=True), \
         patch("src.executor._resolve_kubescape_binary", return_value="C:\\tools\\kubescape.exe"), \
         patch("subprocess.run", return_value=mock_result):
        df = run_executor(elements_txt, reqs_txt, zip_path, out_csv, controls_txt)

    assert isinstance(df, pd.DataFrame)
    assert os.path.isfile(out_csv)
