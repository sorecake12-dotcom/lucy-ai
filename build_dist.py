"""
build_dist.py — Builds the standalone Windows distribution for LUCY.

Creates:
  dist/LUCY/       (Standalone application folder with embedded Python runtime)
  dist/LUCY.zip    (Final distribution archive for end users)
"""
import os
import shutil
import subprocess
import sys
import json
import zipfile
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = Path(__file__).resolve().parent
DIST_DIR = HERE / "dist"
LUCY_DIR = DIST_DIR / "LUCY"
ZIP_PATH = DIST_DIR / "LUCY.zip"
SRC_PYTHON = Path(r"C:\Users\ACER\AppData\Roaming\uv\python\cpython-3.11.15-windows-x86_64-none")

def step(msg: str):
    print(f"\n==================================================")
    print(f">> {msg}")
    print(f"==================================================")

def compile_launcher():
    step("Compiling native LUCY.exe launcher")
    csc = Path(r"C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe")
    if not csc.exists():
        raise RuntimeError("csc.exe not found on system.")
    
    cmd = [
        str(csc),
        "/target:winexe",
        f"/win32icon:{HERE / 'config' / 'logo.ico'}",
        f"/out:{HERE / 'LUCY.exe'}",
        str(HERE / "launcher" / "LUCY_launcher.cs")
    ]
    subprocess.run(cmd, check=True)
    print("✓ LUCY.exe compiled successfully.")

def copy_runtime():
    step("Embedding standalone Python 3.11 runtime")
    dest_runtime = LUCY_DIR / "runtime"
    if dest_runtime.exists():
        print("Cleaning previous runtime...")
        shutil.rmtree(dest_runtime)
        
    print(f"Copying base standalone runtime from {SRC_PYTHON}...")
    shutil.copytree(SRC_PYTHON, dest_runtime, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    
    # Remove EXTERNALLY-MANAGED if present so pip works seamlessly
    ext_managed = dest_runtime / "Lib" / "EXTERNALLY-MANAGED"
    if ext_managed.exists():
        ext_managed.unlink()
        print("Removed EXTERNALLY-MANAGED marker.")
        
    # Install dependencies into the embedded runtime
    print("Installing requirements into embedded runtime...")
    python_exe = dest_runtime / "python.exe"
    subprocess.run([
        "uv", "pip", "install",
        "--python", str(python_exe),
        "--break-system-packages",
        "-r", str(HERE / "requirements.txt")
    ], check=True)
    print("✓ Dependencies installed successfully into embedded runtime.")

def copy_app_files():
    step("Copying LUCY application files")
    
    # Files to copy
    files = [
        "setup.bat",
        "LUCY.exe",
        "main.py",
        "ui.py",
        "requirements.txt",
        "readme.md",
        "LICENSE"
    ]
    for f in files:
        src = HERE / f
        if src.exists():
            shutil.copy2(src, LUCY_DIR / f)
            print(f"  Copied {f}")
            
    # Directories to copy
    dirs = [
        "actions",
        "config",
        "core",
        "dashboard",
        "memory",
        "plugins"
    ]
    for d in dirs:
        src = HERE / d
        dst = LUCY_DIR / d
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(
            src,
            dst,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".git*", "venv", ".venv")
        )
        print(f"  Copied {d}/")
        
    # Ensure logs folder exists
    (LUCY_DIR / "logs").mkdir(exist_ok=True)
    
    # Sanitize config/api_keys.json
    api_config_file = LUCY_DIR / "config" / "api_keys.json"
    if api_config_file.exists():
        try:
            with open(api_config_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
        # Clear secret key
        data["gemini_api_key"] = ""
        # Write sanitized config
        with open(api_config_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
        print("  ✓ Sanitized config/api_keys.json (cleared gemini_api_key)")
        
    # Sanitize memory/long_term.json
    mem_file = LUCY_DIR / "memory" / "long_term.json"
    clean_mem = {
        "identity": {},
        "preferences": {},
        "projects": {},
        "relationships": {},
        "wishes": {},
        "notes": {},
        "sessions": [],
        "monitors": {}
    }
    with open(mem_file, "w", encoding="utf-8") as f:
        json.dump(clean_mem, f, indent=2)
    print("  ✓ Sanitized memory/long_term.json")

def verify_distribution():
    step("Validating packaged distribution")
    python_exe = LUCY_DIR / "runtime" / "python.exe"
    
    # Test importing main from inside the distribution folder
    result = subprocess.run(
        [str(python_exe), "-c", "import main; print('PACKAGE_VALIDATION_SUCCESS')"],
        cwd=str(LUCY_DIR),
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        print("STDERR:\n", result.stderr)
        raise RuntimeError("Validation failed: main cannot be imported in packaged distribution.")
    
    print("✓ Packaged runtime validation passed:", result.stdout.strip())

def create_zip():
    step("Creating final LUCY.zip archive")
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()
        
    print(f"Zipping {LUCY_DIR} into {ZIP_PATH} ... (this may take a minute)")
    
    with zipfile.ZipFile(ZIP_PATH, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(LUCY_DIR):
            for file in files:
                file_path = Path(root) / file
                arcname = file_path.relative_to(DIST_DIR)
                zf.write(file_path, arcname)
                
    zip_size_mb = ZIP_PATH.stat().st_size / (1024 * 1024)
    print(f"✓ Created {ZIP_PATH} ({zip_size_mb:.2f} MB)")

def main():
    DIST_DIR.mkdir(exist_ok=True)
    LUCY_DIR.mkdir(exist_ok=True)
    
    compile_launcher()
    copy_runtime()
    copy_app_files()
    verify_distribution()
    create_zip()
    
    step("BUILD COMPLETE!")
    print(f"Distribution folder: {LUCY_DIR}")
    print(f"Distribution zip:    {ZIP_PATH}")

if __name__ == "__main__":
    main()
