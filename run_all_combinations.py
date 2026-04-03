"""Run all 9 required PDF input combinations and save each result to its own subfolder."""

import os
import shutil
import subprocess
import sys

COMBINATIONS = [
    ("cis-r1.pdf", "cis-r1.pdf"),
    ("cis-r1.pdf", "cis-r2.pdf"),
    ("cis-r1.pdf", "cis-r3.pdf"),
    ("cis-r1.pdf", "cis-r4.pdf"),
    ("cis-r2.pdf", "cis-r2.pdf"),
    ("cis-r2.pdf", "cis-r3.pdf"),
    ("cis-r2.pdf", "cis-r4.pdf"),
    ("cis-r3.pdf", "cis-r3.pdf"),
    ("cis-r3.pdf", "cis-r4.pdf"),
]

OUTPUT_FILES = [
    "differing_elements.txt",
    "differing_requirements.txt",
    "controls.txt",
    "kubescape_results.csv",
]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUTS_DIR = os.path.join(BASE_DIR, "outputs")


def run_combination(pdf1: str, pdf2: str, idx: int) -> bool:
    stem1 = os.path.splitext(pdf1)[0]
    stem2 = os.path.splitext(pdf2)[0]
    combo_name = f"{stem1}_vs_{stem2}"
    combo_dir = os.path.join(OUTPUTS_DIR, combo_name)
    os.makedirs(combo_dir, exist_ok=True)

    # Skip if already completed (all output files present)
    if all(os.path.isfile(os.path.join(combo_dir, f)) for f in OUTPUT_FILES):
        print(f"[{idx}/9] {combo_name} — already done, skipping.")
        return True

    print(f"\n{'='*60}")
    print(f"[{idx}/9] Running: python main.py {pdf1} {pdf2}")
    print(f"{'='*60}")

    pdf1_path = os.path.join(BASE_DIR, pdf1)
    pdf2_path = os.path.join(BASE_DIR, pdf2)

    result = subprocess.run(
        [sys.executable, "main.py", pdf1_path, pdf2_path,
         "--output-dir", OUTPUTS_DIR],
        cwd=BASE_DIR,
    )

    if result.returncode != 0:
        print(f"ERROR: combination {combo_name} failed with exit code {result.returncode}")
        return False

    # Copy outputs to per-combination subfolder
    for fname in OUTPUT_FILES:
        src = os.path.join(OUTPUTS_DIR, fname)
        if os.path.isfile(src):
            shutil.copy2(src, os.path.join(combo_dir, fname))

    print(f"[{idx}/9] Saved to outputs/{combo_name}/")
    return True


def main():
    passed = 0
    failed = []
    for idx, (pdf1, pdf2) in enumerate(COMBINATIONS, start=1):
        ok = run_combination(pdf1, pdf2, idx)
        if ok:
            passed += 1
        else:
            failed.append(f"{pdf1} vs {pdf2}")

    print(f"\n{'='*60}")
    print(f"Done: {passed}/9 combinations completed.")
    if failed:
        print("Failed:")
        for f in failed:
            print(f"  - {f}")
    print(f"Per-combination results saved under outputs/<name>/")


if __name__ == "__main__":
    main()
