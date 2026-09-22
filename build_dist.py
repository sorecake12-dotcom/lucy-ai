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


def find_python_runtime() -> Path:
    appdata = os.environ.get("APPDATA")
    if appdata:
        uv_py_dir = Path(appdata) / "uv" / "python"
        if uv_py_dir.exists():
            candidates = sorted(uv_py_dir.glob("cpython-3.11*windows-x86_64*"), reverse=True)
            if candidates:
                return candidates[0]

    base_prefix = Path(sys.base_prefix)
    if sys.version_info.major == 3 and sys.version_info.minor == 11 and (base_prefix / "python.exe").exists():
        return base_prefix

    fallback = Path(r"C:\Users\ACER\AppData\Roaming\uv\python\cpython-3.11.15-windows-x86_64-none")
    if fallback.exists():
        return fallback

    raise RuntimeError("Could not find a standalone Python 3.11 runtime on this machine.")


SRC_PYTHON = find_python_runtime()

def step(msg: str):
    print("\n==================================================")
    print(f">> {msg}")
    print("==================================================")

def compile_launcher():
    step("Compiling native LUCY.exe launcher")
    candidates = [
        Path(r"C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe"),
        Path(r"C:\Windows\Microsoft.NET\Framework\v4.0.30319\csc.exe"),
        Path(os.environ.get("SystemRoot", r"C:\Windows")) / r"Microsoft.NET\Framework64\v4.0.30319\csc.exe",
        Path(os.environ.get("SystemRoot", r"C:\Windows")) / r"Microsoft.NET\Framework\v4.0.30319\csc.exe",
    ]
    csc = next((c for c in candidates if c.exists()), None)
    if not csc:
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
    if shutil.which("uv"):
        subprocess.run([
            "uv", "pip", "install",
            "--python", str(python_exe),
            "--break-system-packages",
            "-r", str(HERE / "requirements.txt")
        ], check=True)
    else:
        subprocess.run([
            str(python_exe), "-m", "pip", "install",
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
        "launcher",
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
        # Clear secret key and user details
        data["gemini_api_key"] = ""
        data["user_name"] = "User"
        data["input_device"] = ""
        data["output_device"] = ""
        # Write sanitized config
        with open(api_config_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
        print("  ✓ Sanitized config/api_keys.json (cleared keys and personal info)")
        
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
        for root, _, files in os.walk(LUCY_DIR):
            for file in files:
                file_path = Path(root) / file
                arcname = file_path.relative_to(DIST_DIR)
                zf.write(file_path, arcname)
                
    zip_size_mb = ZIP_PATH.stat().st_size / (1024 * 1024)
    print(f"✓ Created {ZIP_PATH} ({zip_size_mb:.2f} MB)")

def generate_hashes():
    step("Generating SHA-256 Checksums")
    import hashlib
    sums_file = DIST_DIR / "SHA256SUMS.txt"
    lines = []
    
    for target in [HERE / "LUCY.exe", LUCY_DIR / "LUCY.exe", ZIP_PATH]:
        if target.exists():
            h = hashlib.sha256()
            with open(target, "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    h.update(chunk)
            digest = h.hexdigest()
            name = target.relative_to(DIST_DIR) if target.is_relative_to(DIST_DIR) else target.name
            line = f"{digest}  {name}"
            lines.append(line)
            print(f"  {line}")
            
    with open(sums_file, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"✓ Checksums written to {sums_file}")

def main():
    DIST_DIR.mkdir(exist_ok=True)
    LUCY_DIR.mkdir(exist_ok=True)
    
    compile_launcher()
    copy_runtime()
    copy_app_files()
    verify_distribution()
    create_zip()
    generate_hashes()
    
    step("BUILD COMPLETE!")
    print(f"Distribution folder: {LUCY_DIR}")
    print(f"Distribution zip:    {ZIP_PATH}")

if __name__ == "__main__":
    main()
