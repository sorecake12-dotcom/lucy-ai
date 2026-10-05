"""Serious-Mode readiness test — Stage 1: Browser control, error recovery, media.
Tests LUCY's real handlers (actions/browser_control.py, actions/youtube_video.py).
Temporary artifacts go to a temp dir; native windows opened are closed after."""
import sys, os, time, tempfile, shutil, json, traceback
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

from actions.browser_control import browser_control
bc = lambda p: browser_control(dict(p))

# ── 1.1 Launch default browser (native open, no URL) ─────────────────────────
r = bc({"action": "go_to", "url": "example.com"})
rec("browser_native_open", "PASS" if r.startswith("Opened") else "FAIL", r[:80])
time.sleep(2)

# ── 1.2 Open a specified URL ─────────────────────────────────────────────────
r = bc({"action": "go_to", "url": "https://www.bing.com"})
rec("browser_open_url", "PASS" if r.startswith("Opened") else "FAIL", r[:80])

# ── 1.3 Web search via browser ───────────────────────────────────────────────
r = bc({"action": "search", "query": "Playwright python documentation"})
rec("browser_search", "PASS" if r.startswith("Opened") else "FAIL", r[:80])

# ── 1.4 Open a search result (smart_click on first result) + read page ───────
r = bc({"action": "smart_click", "description": "Get started"})
clicked = not r.startswith("Could not find")
r2 = bc({"action": "get_url"})
r3 = bc({"action": "get_text"})
got_text = len(r3) > 100
rec("browser_click_result", "PASS" if clicked else "PARTIAL",
    f"click={r[:50]} | url={r2[:60]} | text {len(r3)} chars")

# ── 1.5 Navigate back / forward ──────────────────────────────────────────────
rb = bc({"action": "back"})
rf = bc({"action": "forward"})
ok_nav = rb.startswith("Navigated back") and rf.startswith("Navigated forward")
rec("browser_back_forward", "PASS" if ok_nav else "PARTIAL", f"{rb[:60]} | {rf[:60]}")

# ── 1.6 Detect browser actually opened (window enumeration cross-check) ──────
import pygetwindow as gw
titles = [t for t in gw.getAllTitles() if any(k in t.lower() for k in ("chrome", "edge", "firefox"))]
rec("browser_open_detection", "PASS" if titles else "PARTIAL",
    f"handler reports 'Opened:' + {len(titles)} browser window(s) visible: {titles[:2]}")

# ── 1.7 Close the browser (automation sessions) ──────────────────────────────
r = bc({"action": "close_all"})
rec("browser_close", "PASS" if "closed" in r.lower() else "FAIL", r[:80])

# ── 14a Error recovery: invalid URL ──────────────────────────────────────────
r = bc({"action": "go_to", "url": "https://this-domain-definitely-does-not-exist-98765.invalid"})
handled = ("Could not open" in r) or ("Opened" not in r and r)
rec("recover_invalid_url", "PASS" if handled else "FAIL", f"graceful result: {r[:80]}")

# ── 14b Error recovery: read from closed browser session ─────────────────────
try:
    r = bc({"action": "get_text"})
    rec("recover_closed_browser", "PASS", f"no crash; result: {r[:70]}")
except Exception as e:
    rec("recover_closed_browser", "FAIL", f"raised: {e}")

# ── 12. Media: play a YouTube video via LUCY's youtube_video handler ────────
from actions.youtube_video import youtube_video as yt_handler
r = yt_handler({"action": "play", "query": "lofi hip hop radio"}, player=None)
time.sleep(5)
yt_titles = [t for t in gw.getAllTitles() if "youtube" in t.lower()]
rec("media_play_youtube", "PASS" if (r and yt_titles) else "PARTIAL",
    f"handler opened video; {len(yt_titles)} YouTube window(s) visible")
# get_info (metadata scrape — no media download)
try:
    r = yt_handler({"action": "get_info", "url": "https://www.youtube.com/watch?v=jfKfPfyJRdk"})
    rec("media_get_info", "PASS" if ("title" in r.lower() or "views" in r.lower()) else "PARTIAL", str(r)[:90])
except Exception as e:
    rec("media_get_info", "FAIL", str(e)[:90])
# stop/close: focus the YouTube tab and Ctrl+W it (native tabs need OS-level close)
try:
    win = [w for w in gw.getAllWindows() if "youtube" in w.title.lower()]
    if win:
        w = win[0]; w.activate(); time.sleep(1.2)
        import pyautogui; pyautogui.hotkey("ctrl", "w"); time.sleep(1.5)
        still = [t for t in gw.getAllTitles() if "youtube" in t.lower()]
        rec("media_close", "PASS" if not still else "PARTIAL", f"tab closed via Ctrl+W; remaining: {still[:1]}")
    else:
        rec("media_close", "PARTIAL", "no YouTube window found to close")
except Exception as e:
    rec("media_close", "FAIL", str(e)[:90])

print("\n=== STAGE 1 DONE ===")
for k, (s, d) in RESULTS.items(): print(f"{s:8} {k}")
