"""
core/platform_adapter.py — Unified Platform Abstraction Layer for LUCY.

Encapsulates OS-specific behavior across Windows, macOS (Darwin), and Linux:
  • OS identification and capability detection
  • Desktop path resolution (OneDrive on Windows, XDG on Linux, standard on macOS)
  • System shortcut creation (.lnk on Windows, .app on macOS, .desktop on Linux)
  • Auto-start configuration (Registry on Windows, LaunchAgents on macOS, autostart desktop on Linux)
  • Display/Audio/System controls with platform-safe fallbacks
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

_SYSTEM = platform.system()  # "Windows" | "Darwin" | "Linux"


def get_os_name() -> str:
    """Return normalized OS identifier: 'windows', 'mac', or 'linux'."""
    return {"Windows": "windows", "Darwin": "mac", "Linux": "linux"}.get(_SYSTEM, "linux")


def is_windows() -> bool:
    return _SYSTEM == "Windows"


def is_mac() -> bool:
    return _SYSTEM == "Darwin"


def is_linux() -> bool:
    return _SYSTEM == "Linux"


def get_desktop_dir() -> Path:
    """
    Resolve the real desktop directory across platforms.
    Handles OneDrive redirection on Windows and XDG user-dirs on Linux.
    """
    home = Path.home()

    if is_windows():
        # 1. Try SHGetKnownFolderPath (FOLDERID_Desktop)
        try:
            import ctypes
            from ctypes import wintypes

            class _GUID(ctypes.Structure):
                _fields_ = [
                    ("Data1", wintypes.DWORD),
                    ("Data2", wintypes.WORD),
                    ("Data3", wintypes.WORD),
                    ("Data4", ctypes.c_ubyte * 8),
                ]

            fid = _GUID(
                0xB4BFCC3A,
                0xDB2C,
                0x424C,
                (ctypes.c_ubyte * 8)(0xB0, 0x29, 0x7F, 0xE9, 0x9A, 0x87, 0xC6, 0x41),
            )
            buf = ctypes.c_wchar_p()
            if ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(fid), 0, None, ctypes.byref(buf)) == 0:
                p = Path(buf.value)
                ctypes.windll.ole32.CoTaskMemFree(buf)
                if p.is_dir():
                    return p
        except Exception:
            pass

        # 2. Try Registry User Shell Folders
        try:
            import winreg
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders",
            ) as key:
                val, _ = winreg.QueryValueEx(key, "Desktop")
            p = Path(os.path.expandvars(val))
            if p.is_dir():
                return p
        except Exception:
            pass

    elif is_linux():
        # Try xdg-user-dir
        try:
            out = subprocess.run(["xdg-user-dir", "DESKTOP"], capture_output=True, text=True, timeout=5)
            p = Path(out.stdout.strip())
            if p.is_dir():
                return p
        except Exception:
            pass

        # Try user-dirs.dirs
        try:
            cfg = home / ".config" / "user-dirs.dirs"
            if cfg.exists():
                for line in cfg.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line.startswith("XDG_DESKTOP_DIR"):
                        val = line.split("=", 1)[1].strip().strip('"')
                        p = Path(val.replace("$HOME", str(home)))
                        if p.is_dir():
                            return p
        except Exception:
            pass

    return home / "Desktop"


def show_notification(title: str, message: str, timeout: int = 10) -> bool:
    """Send a native desktop notification on any platform."""
    if is_windows():
        try:
            from win10toast import ToastNotifier
            ToastNotifier().show_toast(title, message, duration=timeout, threaded=True)
            return True
        except Exception:
            pass
        try:
            subprocess.run(["msg", "*", f"/TIME:{timeout}", message], check=False, creationflags=0x08000000)
            return True
        except Exception:
            pass

    elif is_mac():
        try:
            safe_msg = message.replace('"', '\\"')
            safe_title = title.replace('"', '\\"')
            script = f'display notification "{safe_msg}" with title "{safe_title}"'
            subprocess.run(["osascript", "-e", script], check=False, timeout=5)
            return True
        except Exception:
            pass

    else:  # Linux
        try:
            subprocess.run(["notify-send", "--expire-time", str(timeout * 1000), title, message], check=False, timeout=5)
            return True
        except Exception:
            pass

    return False


def get_platform_capabilities() -> dict[str, bool]:
    """Report features natively supported on this operating system."""
    return {
        "audio_input": True,
        "audio_output": True,
        "ai_chat": True,
        "holographic_hud": True,
        "particle_visualizer": True,
        "memory_manager": True,
        "browser_automation": True,
        "desktop_automation": True,
        "global_hotkey": is_windows(),  # Global keyhook without extra permissions
        "hardware_volume_control": True,
        "hardware_brightness_control": is_windows() or is_linux(),
        "dark_mode_toggle": is_windows() or is_mac() or is_linux(),
        "native_app_shortcuts": True,
        "autostart": True,
    }
