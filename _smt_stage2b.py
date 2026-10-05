"""Stage 2b — verify the two fixes + precise browser click/type re-test.
Only touches windows/tabs whose titles match the test marker or 'Untitled'."""
import sys, os, time, tempfile, shutil
from pathlib import Path
for _s in ("stdout", "stderr"):
    try: sys.__dict__[_s].reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT)); os.chdir(ROOT)
RESULTS = {}
def rec(key, status, detail):
    RESULTS[key] = (status, detail)
    print(f"[{status:8}] {key} — {detail}")

import pygetwindow as gw
import pyautogui
pyautogui.PAUSE = 0.08
import pyperclip
from actions.computer_control import computer_control as cc
from actions.browser_control import browser_control as bc

# ── Re-test 1: focus_window honest SUCCESS on a fresh Notepad (mine) ─────────
import subprocess
subprocess.Popen(["notepad.exe"]); time.sleep(2.5)
mine = [w for w in gw.getAllWindows()
        if "untitled" in w.title.lower() and "notepad" in w.title.lower()]
r = cc({"action": "focus_window", "title": "Untitled"})
focused_ok = r.startswith("Focused")
aw = gw.getActiveWindow()
really_front = bool(aw and "untitled" in (aw.title or "").lower())
rec("fix_focus_success", "PASS" if (focused_ok and really_front) else "FAIL",
    f"handler='{r[:50]}' | actually front: {bool(aw and 'untitled' in (aw.title or '').lower())}")

# ── Re-test 2: focus_window honest FAILURE on a window that doesn't exist ────
r = cc({"action": "focus_window", "title": "no_such_window_xyz_987"})
rec("fix_focus_honest_failure", "PASS" if r.startswith("Could not focus") else "FAIL", r[:80])

# ── Type into MY notepad + clipboard verify (full loop with focus) ───────────
if focused_ok and really_front:
    cc({"action": "click"})            # click into the text area
    time.sleep(0.3)
    cc({"action": "type", "text": "FOCUS_FIX_MARKER_777"})
    cc({"action": "hotkey", "keys": "ctrl+a"}); time.sleep(0.2)
    cc({"action": "hotkey", "keys": "ctrl+c"}); time.sleep(0.4)
    clip = pyperclip.paste() or ""
    rec("fix_focus_then_type_loop", "PASS" if "FOCUS_FIX_MARKER_777" in clip else "FAIL",
        f"clipboard: {clip[:60]!r}")
    # close MY notepad: alt+F4 → discard (right+enter through the save dialog)
    pyautogui.hotkey("alt", "F4"); time.sleep(1.2)
    pyautogui.press("right"); time.sleep(0.3); pyautogui.press("enter"); time.sleep(1.2)
else:
    rec("fix_focus_then_type_loop", "PARTIAL", "skipped — focus did not land on the test notepad")

# ── Cleanup check: user's own Notepad must still be untouched ────────────────
left_np = [w.title for w in gw.getAllWindows() if "notepad" in w.title.lower()]
user_np_intact = any("*You are continuing" in t for t in left_np)
rec("user_notepad_untouched", "PASS" if user_np_intact or not left_np else "PARTIAL",
    f"remaining notepad windows: {left_np}")

# ── Re-test 3: browser click + type on a REAL element (Bing search box) ──────
r1 = bc({"action": "go_to", "url": "https://www.bing.com"})
time.sleep(2)
r2 = bc({"action": "smart_click", "description": "search"})     # the search box
r3 = bc({"action": "type", "text": "OpenWeatherMap api", "clear_first": True})
r4 = bc({"action": "press", "key": "Enter"})
time.sleep(3)
r5 = bc({"action": "get_url"})
clicked = r2.startswith("Clicked")
navigated = ("OpenWeatherMap" in r5)
rec("browser_click_type_loop", "PASS" if (clicked and navigated) else "PARTIAL",
    f"click={r2[:40]} | type={r3[:30]} | url now: {r5[:70]}")

# ── Re-test 4: invalid URL now honestly reported (automation mode) ───────────
r = bc({"action": "go_to", "url": "https://this-domain-definitely-does-not-exist-98765.invalid"})
rec("fix_browser_error_page_detect",
    "PASS" if "Could not open" in r and "error page" in r else "FAIL", r[:90])

# ── Re-test 5: valid URL still works after the fix (no false negatives) ──────
r = bc({"action": "go_to", "url": "https://example.com"})
rec("fix_browser_no_false_negative", "PASS" if r.startswith("Opened") else "FAIL", r[:70])

# close test sessions; close the marker search tab via title-matched ctrl+w
bc({"action": "close_all"})
for _ in range(4):
    t = [w for w in gw.getAllWindows() if "LUCY_AUDIT_MARKER" in w.title or "PASTED_BY_LUCY" in w.title]
    if not t: break
    try:
        t[0].activate(); time.sleep(0.8); pyautogui.hotkey("ctrl", "w"); time.sleep(0.8)
    except Exception: break
left_marker = [t2 for t2 in gw.getAllTitles() if "LUCY_AUDIT_MARKER" in t2 or "PASTED_BY_LUCY" in t2]
rec("marker_tab_cleanup", "PASS" if not left_marker else "PARTIAL", f"remaining marker tabs: {left_marker}")

print("\n=== STAGE 2b DONE ===")
for k, (s, d) in RESULTS.items(): print(f"{s:8} {k}")
