import subprocess
import sys
import os

def main():
    print("Building Project 6700 Executable...")
    try:
        import PyInstaller
    except ImportError:
        print("Installing PyInstaller...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
    
    # Run PyInstaller
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--clean",
        "--onefile",
        "--name", "project6700",
        "--hidden-import", "fitz",
        "--exclude-module", "torch",
        "--exclude-module", "transformers",
        "--exclude-module", "accelerate",
        "--exclude-module", "huggingface_hub",
        "main.py"
    ]
    
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    
    if result.returncode == 0:
        exe_ext = ".exe" if os.name == "nt" else ""
        print(f"\nBuild successful! Binary is located at: {os.path.join('dist', 'project6700' + exe_ext)}")
        print("Note: The binary contains the CLI. Make sure the system has python installed dependencies like huggingface configured if they must be lazy-loaded, or use it per the instructions in README.")
    else:
        print(f"\nBuild failed with exit code {result.returncode}")
        sys.exit(result.returncode)

if __name__ == "__main__":
    main()
