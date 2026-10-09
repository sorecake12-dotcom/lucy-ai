"""
core/self_healing_control.py — Safe Self-Healing Automation and Computer Control Layer.

Provides:
  • Failure detection & automated diagnosis:
      - STALE_HANDLE (invalid or closed window handle)
      - LOST_FOCUS (window minimized, backgrounded, or behind another app)
      - DISCONNECTED_AUTOMATION (IPC / automation worker failure)
      - FAILED_INPUT_BACKEND (display lock, PyAutoGUI failsafe, clipboard lock)
      - TEMP_PROCESS_FAILURE (application temporarily hung or unresponsive)
      - PERMISSION_PROBLEM (elevated UAC window or accessibility permission denied)
      - APP_SPECIFIC_FAILURE (application crashed or not running)
  • Automatic re-acquisition, window un-minimizing (SW_RESTORE), and focus recovery
  • Bounded retries with exponential backoff (max 3 retries)
  • Safe application closing with graceful WM_CLOSE fallback
  • Cross-platform support (Windows, macOS, Linux) without modifying system drivers
"""

from __future__ import annotations

from dataclasses import dataclass
import enum
import os
import platform
import shutil
import subprocess
import sys
import time
from typing import Any, Callable, Optional

_SYSTEM = platform.system()  # "Windows" | "Darwin" | "Linux"

if _SYSTEM == "Windows":
    _WIN_HIDE: dict = {"creationflags": subprocess.CREATE_NO_WINDOW}
else:
    _WIN_HIDE: dict = {}


class FailureCategory(enum.Enum):
    NONE = "none"
    STALE_HANDLE = "stale_window_handle"
    LOST_FOCUS = "lost_focus"
    DISCONNECTED_AUTOMATION = "disconnected_automation_layer"
    FAILED_INPUT_BACKEND = "failed_input_backend"
    TEMP_PROCESS_FAILURE = "temporary_process_failure"
    PERMISSION_PROBLEM = "permission_problem"
    APP_SPECIFIC_FAILURE = "application_specific_failure"


@dataclass
class HealingResult:
    success: bool
    category: FailureCategory
    attempts: int
    message: str
    detail: str = ""


# ── Native Window Management (Windows, macOS, Linux) ───────────────────────

class WindowManager:
    """Platform-independent window discovery, focus, and state recovery."""

    @staticmethod
    def list_windows() -> list[str]:
        """Return titles of currently open, visible windows."""
        titles: list[str] = []

        if _SYSTEM == "Windows":
            try:
                import pygetwindow as gw
                for w in gw.getAllWindows():
                    t = (w.title or "").strip()
                    if t and w.visible:
                        titles.append(t)
                return titles
            except Exception:
                pass

            # Ctypes fallback
            try:
                import ctypes
                user32 = ctypes.windll.user32

                def enum_handler(hwnd, _extra):
                    if user32.IsWindowVisible(hwnd):
                        length = user32.GetWindowTextLengthW(hwnd)
                        if length > 0:
                            buff = ctypes.create_unicode_buffer(length + 1)
                            user32.GetWindowTextW(hwnd, buff, length + 1)
                            title = buff.value.strip()
                            if title:
                                titles.append(title)
                    return True

                WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
                user32.EnumWindows(WNDENUMPROC(enum_handler), 0)
                return titles
            except Exception:
                return []

        elif _SYSTEM == "Darwin":
            try:
                script = 'tell application "System Events" to get name of every process whose visible is true'
                res = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=3)
                if res.returncode == 0:
                    return [p.strip() for p in res.stdout.split(",") if p.strip()]
            except Exception:
                pass

        elif _SYSTEM == "Linux":
            try:
                res = subprocess.run(["wmctrl", "-l"], capture_output=True, text=True, timeout=3)
                if res.returncode == 0:
                    for line in res.stdout.splitlines():
                        parts = line.split(maxsplit=3)
                        if len(parts) >= 4:
                            titles.append(parts[3].strip())
                    return titles
            except Exception:
                pass

        return titles

    @staticmethod
    def get_active_window_title() -> str:
        """Get the title of the window currently in the foreground."""
        if _SYSTEM == "Windows":
            try:
                import pygetwindow as gw
                w = gw.getActiveWindow()
                if w and w.title:
                    return w.title.strip()
            except Exception:
                pass
            try:
                import ctypes
                user32 = ctypes.windll.user32
                hwnd = user32.GetForegroundWindow()
                if hwnd:
                    length = user32.GetWindowTextLengthW(hwnd)
                    if length > 0:
                        buff = ctypes.create_unicode_buffer(length + 1)
                        user32.GetWindowTextW(hwnd, buff, length + 1)
                        return buff.value.strip()
            except Exception:
                pass

        elif _SYSTEM == "Darwin":
            try:
                script = 'tell application "System Events" to get name of first application process whose frontmost is true'
                res = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=2)
                if res.returncode == 0:
                    return res.stdout.strip()
            except Exception:
                pass

        elif _SYSTEM == "Linux":
            try:
                res = subprocess.run(["xdotool", "getactivewindow", "getwindowname"], capture_output=True, text=True, timeout=2)
                if res.returncode == 0:
                    return res.stdout.strip()
            except Exception:
                pass

        return ""

    @staticmethod
    def acquire_and_focus(target_title: str) -> bool:
        """
        Locate window by substring, restore it if minimized, and bring to foreground.
        Returns True if the target window is verified in foreground.
        """
        if not target_title:
            return False

        needle = target_title.lower().strip()

        if _SYSTEM == "Windows":
            # 1. Try PyGetWindow with SW_RESTORE
            try:
                import pygetwindow as gw
                matches = [w for w in gw.getAllWindows() if needle in (w.title or "").lower()]
                if matches:
                    win = matches[0]
                    if win.isMinimized:
                        win.restore()
                        time.sleep(0.15)
                    win.activate()
                    time.sleep(0.2)
                    active = gw.getActiveWindow()
                    if active and needle in (active.title or "").lower():
                        return True
            except Exception:
                pass

            # 2. Ctypes ShowWindow(hwnd, SW_RESTORE=9) & SetForegroundWindow
            try:
                import ctypes
                user32 = ctypes.windll.user32
                SW_RESTORE = 9

                found_hwnd = None

                def enum_proc(hwnd, _):
                    nonlocal found_hwnd
                    if user32.IsWindowVisible(hwnd):
                        length = user32.GetWindowTextLengthW(hwnd)
                        if length > 0:
                            buff = ctypes.create_unicode_buffer(length + 1)
                            user32.GetWindowTextW(hwnd, buff, length + 1)
                            if needle in buff.value.lower():
                                found_hwnd = hwnd
                                return False  # Stop enumeration
                    return True

                WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
                user32.EnumWindows(WNDENUMPROC(enum_proc), 0)

                if found_hwnd:
                    # If iconic (minimized), restore it
                    if user32.IsIconic(found_hwnd):
                        user32.ShowWindow(found_hwnd, SW_RESTORE)
                        time.sleep(0.15)
                    user32.BringWindowToTop(found_hwnd)
                    user32.SetForegroundWindow(found_hwnd)
                    time.sleep(0.25)
                    fg = user32.GetForegroundWindow()
                    length = user32.GetWindowTextLengthW(fg)
                    buff = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(fg, buff, length + 1)
                    if needle in buff.value.lower():
                        return True
            except Exception:
                pass

            # 3. PowerShell AppActivate fallback
            try:
                script = f'(New-Object -ComObject WScript.Shell).AppActivate("{target_title}")'
                subprocess.run(
                    ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                    capture_output=True, timeout=4, **_WIN_HIDE,
                )
                time.sleep(0.25)
                active = WindowManager.get_active_window_title()
                return needle in active.lower()
            except Exception:
                pass

        elif _SYSTEM == "Darwin":
            script = (
                f'tell application "System Events" to '
                f'set frontmost of (first process whose name contains "{target_title}") to true'
            )
            try:
                subprocess.run(["osascript", "-e", script], capture_output=True, timeout=4)
                time.sleep(0.3)
                active = WindowManager.get_active_window_title()
                return needle in active.lower()
            except Exception:
                pass

        elif _SYSTEM == "Linux":
            try:
                subprocess.run(["wmctrl", "-a", target_title], capture_output=True, timeout=3)
                time.sleep(0.3)
                active = WindowManager.get_active_window_title()
                if needle in active.lower():
                    return True
            except Exception:
                pass
            try:
                subprocess.run(["xdotool", "search", "--name", target_title, "windowactivate"], capture_output=True, timeout=3)
                time.sleep(0.3)
                active = WindowManager.get_active_window_title()
                return needle in active.lower()
            except Exception:
                pass

        return False


# ── Self-Healing Executor ──────────────────────────────────────────────────

class SelfHealingController:
    """Safe recovery wrapper for all keyboard, mouse, and window automation."""

    MAX_RETRIES = 3

    @classmethod
    def diagnose_failure(cls, err: Exception, target_window: Optional[str] = None) -> FailureCategory:
        """Diagnose root cause of automation failure."""
        msg = str(err).lower()

        # PyAutoGUI failsafe or display lock
        if "failsafe" in msg or "display" in msg or "x11" in msg or "xhost" in msg:
            return FailureCategory.FAILED_INPUT_BACKEND

        # Clipboard lock or access denied
        if "clipboard" in msg or "openclipboard" in msg or "permission denied" in msg:
            return FailureCategory.PERMISSION_PROBLEM

        # Target window lost focus or not in foreground
        if target_window:
            active = WindowManager.get_active_window_title()
            if target_window.lower() not in active.lower():
                all_wins = WindowManager.list_windows()
                if any(target_window.lower() in w.lower() for w in all_wins):
                    return FailureCategory.LOST_FOCUS
                else:
                    return FailureCategory.STALE_HANDLE

        if "not found" in msg or "window not found" in msg or "cannot find" in msg:
            return FailureCategory.STALE_HANDLE

        if "timeout" in msg or "timed out" in msg:
            return FailureCategory.TEMP_PROCESS_FAILURE

        if "access is denied" in msg or "administrator" in msg or "uac" in msg:
            return FailureCategory.PERMISSION_PROBLEM

        return FailureCategory.APP_SPECIFIC_FAILURE

    @classmethod
    def execute_with_healing(
        cls,
        action_name: str,
        action_fn: Callable[[], Any],
        target_window: Optional[str] = None,
        max_retries: int = MAX_RETRIES,
    ) -> tuple[bool, Any, str]:
        """
        Execute an automation action with intelligent self-healing.
        Returns: (success, result, diagnostic_message)
        """
        attempt = 0
        last_category = FailureCategory.NONE
        last_error: Optional[Exception] = None

        while attempt < max_retries:
            attempt += 1

            # 1. Ensure target window has focus before firing input
            if target_window:
                active = WindowManager.get_active_window_title()
                if target_window.lower() not in active.lower():
                    print(f"[SelfHealing] Focus lost (active: '{active}'). Re-acquiring '{target_window}'...")
                    reacquired = WindowManager.acquire_and_focus(target_window)
                    if not reacquired:
                        print(f"[SelfHealing] Attempt {attempt}: Target window '{target_window}' could not be re-acquired.")
                        time.sleep(0.3)
                        # Check if window actually exists
                        all_wins = WindowManager.list_windows()
                        if not any(target_window.lower() in w.lower() for w in all_wins):
                            return (
                                False,
                                None,
                                f"Cannot control '{target_window}': window handle is stale or closed (not found in visible windows).",
                            )

            # 2. Run the actual action
            try:
                res = action_fn()
                # Verify that action returned a non-error string or value
                if isinstance(res, str) and ("failed:" in res.lower() or "error" in res.lower()):
                    raise RuntimeError(res)
                return True, res, f"Action '{action_name}' succeeded on attempt {attempt}."
            except Exception as e:
                last_error = e
                last_category = cls.diagnose_failure(e, target_window)
                print(f"[SelfHealing] Attempt {attempt} failed for '{action_name}': {e} [Diagnosis: {last_category.value}]")

                # Healing strategy per category
                if last_category == FailureCategory.LOST_FOCUS:
                    time.sleep(0.2)
                    if target_window:
                        WindowManager.acquire_and_focus(target_window)

                elif last_category == FailureCategory.FAILED_INPUT_BACKEND:
                    # Release any stuck modifiers and pause
                    cls._release_stuck_keys()
                    time.sleep(0.3)

                elif last_category == FailureCategory.PERMISSION_PROBLEM:
                    time.sleep(0.5)

                elif last_category == FailureCategory.STALE_HANDLE:
                    time.sleep(0.4)

                else:
                    time.sleep(0.2 * (2 ** (attempt - 1)))

        # Bounded stop if all retries exhausted
        diag_msg = (
            f"Control action '{action_name}' failed after {max_retries} self-healing attempts. "
            f"Root cause: {last_category.value}. "
            f"Details: {str(last_error)}"
        )
        return False, None, diag_msg

    @classmethod
    def _release_stuck_keys(cls):
        """Release modifier keys in case a failed hotkey left Ctrl/Alt/Shift held down."""
        try:
            import pyautogui
            for key in ("ctrl", "alt", "shift", "win", "command"):
                try:
                    pyautogui.keyUp(key)
                except Exception:
                    pass
        except Exception:
            pass

    @classmethod
    def close_application_safe(cls, app_name: str) -> tuple[bool, str]:
        """
        Safely terminate or close an application without crashing system drivers.
        First tries graceful WM_CLOSE, then graceful taskkill/SIGTERM.
        """
        if not app_name:
            return False, "No application specified."

        clean_name = app_name.strip()
        print(f"[SelfHealing] Safely closing application: '{clean_name}'")

        # 1. If window is currently open, focus it and attempt graceful close hotkey
        all_wins = WindowManager.list_windows()
        matching = [w for w in all_wins if clean_name.lower() in w.lower()]

        if matching:
            target = matching[0]
            WindowManager.acquire_and_focus(target)
            time.sleep(0.2)
            try:
                import pyautogui
                if _SYSTEM == "Darwin":
                    pyautogui.hotkey("command", "q")
                else:
                    pyautogui.hotkey("alt", "f4")
                time.sleep(0.8)

                # Check if closed
                still_open = [w for w in WindowManager.list_windows() if clean_name.lower() in w.lower()]
                if not still_open:
                    return True, f"Closed '{clean_name}' gracefully."
            except Exception:
                pass

        # 2. Targeted process termination by process image name
        if _SYSTEM == "Windows":
            # Add .exe extension if missing
            exe_name = clean_name if clean_name.lower().endswith(".exe") else f"{clean_name}.exe"
            try:
                # Try graceful termination first (/T without /F)
                res = subprocess.run(
                    ["taskkill", "/IM", exe_name, "/T"],
                    capture_output=True, text=True, timeout=5, **_WIN_HIDE,
                )
                if res.returncode == 0:
                    time.sleep(0.5)
                    return True, f"Closed application process '{exe_name}'."
                # If graceful fails, use forced termination
                res = subprocess.run(
                    ["taskkill", "/F", "/IM", exe_name, "/T"],
                    capture_output=True, text=True, timeout=5, **_WIN_HIDE,
                )
                if res.returncode == 0:
                    return True, f"Terminated process '{exe_name}'."
            except Exception as e:
                return False, f"Failed to close '{clean_name}': {e}"

        elif _SYSTEM == "Darwin":
            try:
                script = f'tell application "{clean_name}" to quit'
                res = subprocess.run(["osascript", "-e", script], capture_output=True, timeout=5)
                if res.returncode == 0:
                    return True, f"Quit application '{clean_name}'."
                # Fallback to killall
                subprocess.run(["killall", clean_name], capture_output=True, timeout=5)
                return True, f"Closed '{clean_name}'."
            except Exception as e:
                return False, f"Failed to close '{clean_name}': {e}"

        elif _SYSTEM == "Linux":
            try:
                res = subprocess.run(["killall", clean_name], capture_output=True, timeout=5)
                if res.returncode == 0:
                    return True, f"Closed '{clean_name}'."
            except Exception as e:
                return False, f"Failed to close '{clean_name}': {e}"

        return False, f"Could not find or close running application '{clean_name}'."
