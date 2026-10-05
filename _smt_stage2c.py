"""Stage 2c — verify the corrected browser fixes."""
import sys, os, time
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

from actions.browser_control import browser_control as bc

# invalid URL → must honestly fail now (automation session active)
r1 = bc({"action": "go_to", "url": "https://www.bing.com"})
r2 = bc({"action": "go_to", "url": "https://this-domain-definitely-does-not-exist-98765.invalid"})
rec("fix_invalid_url_honest", "PASS" if r2.startswith("Could not open") else "FAIL", f"{r2[:90]}")

# valid URL after an error — must still work (no stuck state)
r3 = bc({"action": "go_to", "url": "https://example.com"})
rec("valid_after_error", "PASS" if r3.startswith("Opened") else "FAIL", r3[:70])

# click + smart_type loop on a real element (Bing search box)
bc({"action": "go_to", "url": "https://www.bing.com"}); time.sleep(2)
rc = bc({"action": "smart_click", "description": "search"})
rt = bc({"action": "smart_type", "description": "search", "text": "OpenWeatherMap api"})
rp = bc({"action": "press", "key": "Enter"}); time.sleep(3)
ru = bc({"action": "get_url"})
rec("browser_click_type_loop",
    "PASS" if (rc.startswith("Clicked") and "OpenWeatherMap" in ru) else "PARTIAL",
    f"click={rc[:40]} | type={rt[:20]} | url: {ru[:70]}")

# plain type action now types into a focused non-clearable element too
bc({"action": "go_to", "url": "https://example.com"}); time.sleep(2)
rt2 = bc({"action": "type", "text": "x"})
rec("fix_type_into_focus", "PASS" if rt2 == "Text typed." else "FAIL", f"{rt2[:50]}")

bc({"action": "close_all"})
print("\n=== STAGE 2c DONE ===")
for k, (s, d) in RESULTS.items(): print(f"{s:8} {k}")
