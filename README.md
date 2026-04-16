# KDE Sentinel

Security requirements change detection for CIS-style PDF documents with targeted Kubernetes compliance scanning.

This project compares two security requirements documents, extracts key requirements with an LLM, identifies the differences, maps those differences to Kubescape controls, and produces a CSV scan report.

## Course Project

- Course: `COMP 5700/6700`
- Institution: `Auburn University`
- Team: `Ayush Patel`, `Ryan Lunsford`, `Jim cha`

## What The Project Does

1. Extracts Key Data Elements (KDEs) from each PDF using `google/gemma-3-1b-it`
2. Saves the extracted requirements as YAML
3. Compares the two YAML outputs for changed elements and changed requirements
4. Maps detected changes to Kubescape controls
5. Runs a compliance scan and exports the results to CSV

## Pipeline Overview

```text
PDF 1 --> extractor --> YAML 1 --+
                                 +--> comparator --> controls --> Kubescape --> CSV
PDF 2 --> extractor --> YAML 2 --+
```

## Repository Layout

```text
kde-sentinel/
|-- .github/workflows/     CI configuration
|-- assets/                Scan input assets such as project-yamls.zip
|-- src/                   Application modules
|-- tests/                 Unit tests and fixtures
|-- cis-r1.pdf             Sample input PDF
|-- cis-r2.pdf             Sample input PDF
|-- cis-r3.pdf             Sample input PDF
|-- cis-r4.pdf             Sample input PDF
|-- main.py                CLI entry point
|-- run_all_combinations.py
|-- build_executable.py
|-- generate_report.py
|-- PROMPT.md
|-- requirements.txt
`-- README.md
```

## Why The PDFs Are In The Root Folder

The four `cis-r*.pdf` files are included at the repository root intentionally so the required CLI commands remain simple and match the project instructions exactly:

```bash
python main.py cis-r1.pdf cis-r2.pdf
```

## Quick Start

```bash
# 1. Create and activate a virtual environment
python -m venv venv

# Windows
venv\Scripts\activate

# Linux or macOS
source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Authenticate with Hugging Face
hf auth login

# 4. Install Kubescape
# Windows:
winget install kubescape

# 5. Run the project
python main.py cis-r1.pdf cis-r2.pdf
```

## Command-Line Usage

```text
python main.py <pdf1> <pdf2>
               [--prompt-strategy {zero_shot,few_shot,chain_of_thought}]
               [--zip assets/project-yamls.zip]
               [--output-dir outputs/]
               [--kubescape-path C:\full\path\to\kubescape.exe]
```

## Running All Required Input Combinations

```bash
python run_all_combinations.py
```

This creates per-combination output folders under `outputs/`.

## Tests

```bash
pytest tests/ -v
```

The test suite covers the extractor, comparator, executor, and shared fixtures. LLM and Kubescape interactions are mocked for fast local runs and CI execution.

## Output Files

The application writes the following files to `outputs/`:

| File | Purpose |
|---|---|
| `<stem>-kdes.yaml` | Extracted KDE data for each PDF |
| `llm_outputs.txt` | Logged prompts and model outputs |
| `differing_elements.txt` | KDE names present in one document but not the other |
| `differing_requirements.txt` | Requirement-level differences |
| `controls.txt` | Kubescape controls selected for the scan |
| `kubescape_results.csv` | Final scan results |

## Building The Executable

```bash
python build_executable.py
```

## Notes

- The Gemma model is gated and requires a valid Hugging Face login.
- The first model run may download model artifacts locally.
- Kubescape can be passed explicitly with `--kubescape-path` if it is installed but not available on `PATH`.
