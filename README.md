# KDE Sentinel — Security Requirements Change Detector

A command-line tool that automatically detects changes between two CIS security requirements documents and triggers a Kubernetes compliance scan using Kubescape.

Given two PDF documents, it extracts security requirements using an LLM, compares them, maps the differences to Kubescape controls, and produces a CSV compliance report.

## Team Members

| Name | University Email |
|------|-----------------|
| Ayush Patel | ayp0006@auburn.edu |
| Ryan Lunsford | rtl0019@auburn.edu |

**Course:** COMP 5700/6700 — Auburn University

---

## How It Works

```
cis-r1.pdf ──► LLM (Gemma-3-1B) ──► cis-r1-kdes.yaml ──┐
                                                          ├──► diff ──► controls.txt ──► Kubescape ──► results.csv
cis-r2.pdf ──► LLM (Gemma-3-1B) ──► cis-r2-kdes.yaml ──┘
```

1. **Task-1 — Extract:** Loads each PDF with PyMuPDF and prompts `google/gemma-3-1b-it` to identify 10 Key Data Elements (KDEs) — access control, authentication, encryption, etc. Supports zero-shot, few-shot, and chain-of-thought prompting.
2. **Task-2 — Compare:** Diffs the two YAML outputs by element names and requirements text.
3. **Task-3 — Scan:** Maps differing elements to Kubescape control IDs and runs a targeted scan against Kubernetes manifests. If no differences are found, a full scan runs.
4. **Task-4 — Test:** 31 unit tests with mocked LLM and Kubescape. CI runs on every push via GitHub Actions.

---

## Quick Start

```bash
# 1. Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate          # Linux/Mac
# OR: venv\Scripts\activate       # Windows

# 2. Install dependencies
pip install -r requirements.txt

# 3. Authenticate with HuggingFace (Gemma-3 is a gated model)
huggingface-cli login

# 4. Install Kubescape
# Linux/Mac:
curl -s https://raw.githubusercontent.com/kubescape/kubescape/master/install.sh | /bin/bash
# Windows:
winget install kubescape

# 5. Run
python main.py cis-r1.pdf cis-r2.pdf
```

### Options

```
python main.py <pdf1> <pdf2> [--prompt-strategy {zero_shot,few_shot,chain_of_thought}]
                              [--zip assets/project-yamls.zip]
                              [--output-dir outputs/]
```

### Nine Required Input Combinations

```bash
python main.py cis-r1.pdf cis-r1.pdf
python main.py cis-r1.pdf cis-r2.pdf
python main.py cis-r1.pdf cis-r3.pdf
python main.py cis-r1.pdf cis-r4.pdf
python main.py cis-r2.pdf cis-r2.pdf
python main.py cis-r2.pdf cis-r3.pdf
python main.py cis-r2.pdf cis-r4.pdf
python main.py cis-r3.pdf cis-r3.pdf
python main.py cis-r3.pdf cis-r4.pdf
```

Or run all nine at once:

```bash
python run_all_combinations.py
```

Results for each combination are saved to `outputs/<pdf1>_vs_<pdf2>/`.

---

## Running Tests

```bash
pytest tests/ -v
```

31 tests covering all three modules. The LLM pipeline and Kubescape subprocess are mocked so tests run in under a second without GPU or network access.

### Git Hook Setup

```bash
python setup_git_hooks.py
```

Installs a pre-commit hook that runs tests before every commit, and a `git stat` alias that runs tests then prints status.

---

## Output Files

All outputs are written to `outputs/`:

| File | Description |
|------|-------------|
| `<stem>-kdes.yaml` | Extracted KDEs per PDF (cached — reused on re-runs) |
| `llm_outputs.txt` | Every LLM prompt and raw response |
| `differing_elements.txt` | KDE names present in one doc but not the other |
| `differing_requirements.txt` | Requirements that differ, one `NAME,REQU` per line |
| `controls.txt` | Kubescape control IDs selected for scanning |
| `kubescape_results.csv` | FilePath, Severity, Control name, Failed resources, All Resources, Compliance score |

---

## Building a Standalone Binary

```bash
python build_executable.py
# Binary: dist/project6700 (Linux/Mac) or dist/project6700.exe (Windows)
```

> The HuggingFace model (~1 GB) downloads on first run to `~/.cache/huggingface/`.

---

## Project Structure

```
kde-sentinel/
├── src/
│   ├── extractor.py      # Task-1: PDF → LLM → YAML
│   ├── comparator.py     # Task-2: YAML diff → TEXT
│   ├── executor.py       # Task-3: controls mapping → Kubescape → CSV
│   └── utils.py          # Shared I/O helpers and sentinel constants
├── tests/
│   ├── conftest.py
│   ├── test_extractor.py
│   ├── test_comparator.py
│   └── test_executor.py
├── assets/
│   └── project-yamls.zip
├── .github/workflows/ci.yml
├── main.py
├── run_all_combinations.py
├── build_executable.py
├── setup_git_hooks.py
├── PROMPT.md
├── requirements.txt
└── README.md
```
