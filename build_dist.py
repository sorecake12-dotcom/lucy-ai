"""
build_dist.py — Multi-Platform Distribution Builder for LUCY.

Builds platform-specific standalone packages:
  • Windows: dist/LUCY-Windows.zip (with native launcher & setup)
  • Linux:   dist/LUCY-Linux.tar.gz / dist/LUCY-Linux.zip (with lucy.sh & setup.py)
  • macOS:   dist/LUCY-macOS.tar.gz / dist/LUCY-macOS.zip (with lucy.sh & setup.py)
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = Path(__file__).resolve().parent
DIST_DIR = HERE / "dist"
OS_NAME = platform.system()  # "Windows" | "Darwin" | "Linux"

PKG_NAME = {
    "Windows": "LUCY-Windows",
    "Darwin":  "LUCY-macOS",
    "Linux":   "LUCY-Linux",
}.get(OS_NAME, f"LUCY-{OS_NAME}")

TARGET_DIR = DIST_DIR / PKG_NAME


def step(msg: str):
    print("\n==================================================")
    print(f">> {msg}")
    print("==================================================")


def compile_windows_launcher():
    if OS_NAME != "Windows":
        return
    step("Compiling native Windows launcher (LUCY.exe)")
    candidates = [
        Path(r"C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe"),
        Path(r"C:\Windows\Microsoft.NET\Framework\v4.0.30319\csc.exe"),
        Path(os.environ.get("SystemRoot", r"C:\Windows")) / r"Microsoft.NET\Framework64\v4.0.30319\csc.exe",
        Path(os.environ.get("SystemRoot", r"C:\Windows")) / r"Microsoft.NET\Framework\v4.0.30319\csc.exe",
    ]
    csc = next((c for c in candidates if c.exists()), None)
    if not csc:
        print("[WARNING] csc.exe not found on system. Skipping LUCY.exe compile.")
        return

    icon_path = HERE / "config" / "logo.ico"
    if not icon_path.exists():
        icon_path = HERE / "config" / "jarvis.ico"

    out_exe = TARGET_DIR / "LUCY.exe"
    cmd = [
        str(csc),
        "/nologo",
        "/target:winexe",
        f"/win32icon:{icon_path}",
        f"/out:{out_exe}",
        str(HERE / "launcher" / "LUCY_launcher.cs"),
    ]
    try:
        subprocess.run(cmd, check=True)
        print(f"✓ LUCY.exe compiled successfully: {out_exe}")
    except Exception as e:
        print(f"[WARNING] Launcher compile failed: {e}")


def copy_app_files():
    step(f"Assembling package: {PKG_NAME}")
    if TARGET_DIR.exists():
        shutil.rmtree(TARGET_DIR)
    TARGET_DIR.mkdir(parents=True, exist_ok=True)

    # Core source files
    files = [
        "main.py",
        "ui.py",
        "requirements.txt",
        "readme.md",
        "LICENSE",
        "setup.py",
    ]
    if OS_NAME == "Windows":
        files.append("setup.bat")
    else:
        files.append("lucy.sh")

    for f in files:
        src = HERE / f
        if src.exists():
            shutil.copy2(src, TARGET_DIR / f)
            print(f"  Copied {f}")

    # Ensure lucy.sh executable on POSIX
    sh_file = TARGET_DIR / "lucy.sh"
    if sh_file.exists():
        try:
            sh_file.chmod(0o755)
        except Exception:
            pass

    # Core application directories
    dirs = [
        "actions",
        "assets",
        "config",
        "core",
        "dashboard",
        "launcher",
        "memory",
        "plugins",
    ]
    for d in dirs:
        src = HERE / d
        dst = TARGET_DIR / d
        if src.exists():
            shutil.copytree(
                src,
                dst,
                ignore=shutil.ignore_patterns(
                    "__pycache__", "*.pyc", ".git*", "venv", ".venv", "*.key", "runtime"
                ),
            )
            print(f"  Copied {d}/")

    # Ensure logs folder
    (TARGET_DIR / "logs").mkdir(exist_ok=True)

    # Sanitize config/api_keys.json
    api_config = TARGET_DIR / "config" / "api_keys.json"
    if api_config.exists():
        try:
            with open(api_config, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
        data["gemini_api_key"] = ""
        data["user_name"] = ""
        with open(api_config, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
        print("  ✓ Sanitized config/api_keys.json")

    # Sanitize memory/long_term.json
    mem_file = TARGET_DIR / "memory" / "long_term.json"
    if mem_file.exists():
        clean_mem = {
            "identity": {},
            "preferences": {},
            "projects": {},
            "relationships": {},
            "wishes": {},
            "notes": {},
            "sessions": [],
            "monitors": {},
        }
        with open(mem_file, "w", encoding="utf-8") as f:
            json.dump(clean_mem, f, indent=2)
        print("  ✓ Sanitized memory/long_term.json")


def verify_distribution():
    step("Validating packaged distribution")
    # Verify critical imports from within TARGET_DIR
    res = subprocess.run(
        [sys.executable, "-c", "import core.personality, core.animated_shapes, memory.config_manager; print('VERIFY_OK')"],
        cwd=str(TARGET_DIR),
        capture_output=True,
        text=True,
    )
    if res.returncode != 0:
        print("STDERR:\n", res.stderr)
        raise RuntimeError("Validation failed: modules cannot be imported in packaged distribution.")
    print("✓ Package validation passed:", res.stdout.strip())


def create_archives():
    step(f"Creating archives for {PKG_NAME}")
    zip_path = DIST_DIR / f"{PKG_NAME}.zip"
    if zip_path.exists():
        zip_path.unlink()

    print(f"Creating {zip_path}...")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(TARGET_DIR):
            for file in files:
                file_path = Path(root) / file
                arcname = file_path.relative_to(DIST_DIR)
                zf.write(file_path, arcname)

    size_mb = zip_path.stat().st_size / (1024 * 1024)
    print(f"✓ Created {zip_path} ({size_mb:.2f} MB)")

    # On POSIX, also generate tar.gz
    if OS_NAME in ("Linux", "Darwin"):
        tar_path = DIST_DIR / f"{PKG_NAME}.tar.gz"
        if tar_path.exists():
            tar_path.unlink()
        print(f"Creating {tar_path}...")
        with tarfile.open(tar_path, "w:gz") as tf:
            tf.add(TARGET_DIR, arcname=PKG_NAME)
        tar_size = tar_path.stat().st_size / (1024 * 1024)
        print(f"✓ Created {tar_path} ({tar_size:.2f} MB)")

    # Legacy alias on Windows: LUCY.zip
    if OS_NAME == "Windows":
        legacy_zip = DIST_DIR / "LUCY.zip"
        if legacy_zip.exists():
            legacy_zip.unlink()
        shutil.copy2(zip_path, legacy_zip)


def generate_hashes():
    step("Generating SHA-256 Checksums")
    sums_file = DIST_DIR / "SHA256SUMS.txt"
    lines = []

    for item in sorted(DIST_DIR.glob("*")):
        if item.is_file() and item.name != "SHA256SUMS.txt":
            h = hashlib.sha256()
            with open(item, "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    h.update(chunk)
            digest = h.hexdigest()
            line = f"{digest}  {item.name}"
            lines.append(line)
            print(f"  {line}")

    with open(sums_file, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"✓ Checksums written to {sums_file}")


def main():
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    copy_app_files()
    if OS_NAME == "Windows":
        compile_windows_launcher()
    verify_distribution()
    create_archives()
    generate_hashes()
    step(f"BUILD COMPLETE FOR {OS_NAME}!")


if __name__ == "__main__":
    main()
