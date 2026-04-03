"""Entry point for the security requirements change detector.

Usage
-----
python main.py doc1.pdf doc2.pdf [options]

Or, after building with PyInstaller:
    ./project6700 doc1.pdf doc2.pdf [options]
"""

import argparse
import os
import sys

from src.utils import ensure_dir
from src.extractor import run_extraction, zero_shot_prompt, few_shot_prompt, chain_of_thought_prompt
from src.comparator import run_comparison
from src.executor import run_executor


PROMPT_STRATEGIES = {
    "zero_shot": (zero_shot_prompt, "zero-shot"),
    "few_shot": (few_shot_prompt, "few-shot"),
    "chain_of_thought": (chain_of_thought_prompt, "chain-of-thought"),
}


def parse_args():
    parser = argparse.ArgumentParser(
        description="Detect security requirements changes and run Kubescape."
    )
    parser.add_argument("pdf1", help="Path to the first PDF document.")
    parser.add_argument("pdf2", help="Path to the second PDF document.")
    parser.add_argument(
        "--prompt-strategy",
        choices=list(PROMPT_STRATEGIES.keys()),
        default="zero_shot",
        help="Prompt strategy for the LLM (default: zero_shot).",
    )
    parser.add_argument(
        "--zip",
        default=os.path.join("assets", "project-yamls.zip"),
        help="Path to project-yamls.zip for Kubescape scanning.",
    )
    parser.add_argument(
        "--output-dir",
        default="outputs",
        help="Directory for all output files (default: outputs/).",
    )
    return parser.parse_args()


def _stem(pdf_path: str) -> str:
    """Return the filename stem (no extension) of a PDF path."""
    return os.path.splitext(os.path.basename(pdf_path))[0]


def main():
    args = parse_args()
    ensure_dir(args.output_dir)

    prompt_fn, prompt_type = PROMPT_STRATEGIES[args.prompt_strategy]

    stem1 = _stem(args.pdf1)
    stem2 = _stem(args.pdf2)

    yaml1 = os.path.join(args.output_dir, f"{stem1}-kdes.yaml")
    yaml2 = os.path.join(args.output_dir, f"{stem2}-kdes.yaml")
    llm_log = os.path.join(args.output_dir, "llm_outputs.txt")
    elements_txt = os.path.join(args.output_dir, "differing_elements.txt")
    reqs_txt = os.path.join(args.output_dir, "differing_requirements.txt")
    controls_txt = os.path.join(args.output_dir, "controls.txt")
    out_csv = os.path.join(args.output_dir, "kubescape_results.csv")

    if os.path.isfile(yaml1):
        print(f"[1/5] KDEs for '{args.pdf1}' already extracted, skipping.")
        print(f"      -> {yaml1}")
    else:
        print(f"[1/5] Extracting KDEs from '{args.pdf1}' ...")
        run_extraction(args.pdf1, prompt_fn, prompt_type, yaml1, llm_log)
        print(f"      -> {yaml1}")

    if os.path.isfile(yaml2):
        print(f"[2/5] KDEs for '{args.pdf2}' already extracted, skipping.")
        print(f"      -> {yaml2}")
    else:
        print(f"[2/5] Extracting KDEs from '{args.pdf2}' ...")
        run_extraction(args.pdf2, prompt_fn, prompt_type, yaml2, llm_log)
        print(f"      -> {yaml2}")

    print("[3/5] Comparing YAML files ...")
    run_comparison(yaml1, yaml2, elements_txt, reqs_txt)
    print(f"      -> {elements_txt}")
    print(f"      -> {reqs_txt}")

    print("[4/5] Mapping differences to Kubescape controls ...")
    try:
        df = run_executor(
            elements_txt=elements_txt,
            reqs_txt=reqs_txt,
            zip_path=args.zip,
            out_csv=out_csv,
            controls_txt=controls_txt,
        )
        print(f"      -> {out_csv}")
    except RuntimeError as exc:
        print(f"[WARNING] Kubescape step failed: {exc}", file=sys.stderr)
        print("          Skipping scan. Install Kubescape to enable this step.")
        df = None

    print("[5/5] Done.")
    if df is not None:
        print(f"\nScan summary ({len(df)} rows):")
        print(df.to_string(index=False))


if __name__ == "__main__":
    main()
