"""
Serious Mode engine — the autonomous execution layer behind actions/serious_mode.py.

WHAT THIS IS
    LUCY's existing actions are one command each: open this, search that, save
    this. Serious Mode adds the layer above them: the user states an OBJECTIVE
    ("research the latest AI developments") and this engine turns it into a
    task plan, executes it with the existing actions, collects and verifies
    evidence, organises it into a workspace, and produces a final report —
    without asking the user what to do next at every step.

WHAT THIS IS NOT
    It is not a second browser, a second search backend, a second file system
    or a second PDF writer. Every real action goes through the existing
    modules: web_search, browser_control, open_app, download_file, save_pdf,
    file_processor, screen_processor. This file only sequences them.

DESIGN NOTES
  * One task at a time. A module-level singleton holds the state machine
    (IDLE / PLANNING / RESEARCHING / COLLECTING / PROCESSING / REPORTING /
    COMPLETED / STOPPED / FAILED); a second start() while a task runs is
    refused with the current status, never interleaved.
  * The task runs on its own daemon thread, because a tool call in main.py
    must return quickly or the Live session stalls waiting for it. Progress
    goes out through channels wired by main.py (speech into the session, HUD
    log, content panel), so this module knows nothing about either.
  * Bounded by design. Every loop honours the limits from
    memory.config_manager.get_serious_limits() — searches, sources,
    screenshots, PDFs, failures, steps and a wall-clock budget — so no
    objective can turn into an infinite crawl.
  * Interruptible. stop() sets a flag checked between every step; the ESC
    interrupt and a voice "stop serious mode" both land there. Files already
    collected are kept; the workspace is never deleted on stop.
  * Safety. File writes are confined to the task's own workspace under
    Documents/LUCY/Serious_Mode/. Objectives asking for purchases, messages,
    account or security changes, or file deletion outside the workspace are
    refused before anything runs, and a planned step whose tool is not on the
    whitelist is skipped and recorded.
  * Failure recovery. One failed page, download or app never aborts the task
    — the engine moves to the next source and records the failure for the
    final report. Only breaching the failure budget (or the time budget)
    ends the task early, and even then the evidence so far is reported.
"""

from __future__ import annotations

import html
import json
import re
import shutil
import threading
import time
import traceback
import unicodedata
from datetime import datetime
from pathlib import Path

from core import gemini
from core.undo import push_undo
from memory.config_manager import get_serious_limits

# The existing actions this engine orchestrates. Imported directly (the same
# handlers the action registry holds) so a Serious Mode task behaves exactly
# like the equivalent manual command, whatever thread it runs on.
from actions.web_search        import web_search as _web_search, _ddg_search
from actions.browser_control   import browser_control as _browser_control
from actions.downloader        import download_file as _download_file
from actions.pdf_writer        import save_pdf as _save_pdf
from actions.file_processor    import file_processor as _file_processor
from actions.open_app          import open_app as _open_app
from actions.screen_processor  import _capture_screen

# ── Workspace location ────────────────────────────────────────────────────────
# Documents is where research output belongs (visible, backed up, inside the
# same home-root sandbox file_controller enforces for every other action).

def _base_dir() -> Path:
    return Path.home() / "Documents" / "LUCY" / "Serious_Mode"


# ── Text helpers ──────────────────────────────────────────────────────────────

_URL_RE = re.compile(r"https?://[^\s<>\"')\]]+", re.IGNORECASE)
# A search-results page is a pointer, not a source.
_SKIP_URL_RE = re.compile(
    r"(?:google|bing|duckduckgo|yandex|search)\.[a-z.]+/(?:search|news|q)", re.I)


def _slugify(text: str, maxlen: int = 40) -> str:
    """Filesystem-safe, lowercase, ASCII slug for file and folder names."""
    text = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode()
    text = re.sub(r"[^\w\s-]", "", text).strip().lower()
    text = re.sub(r"[\s_-]+", "-", text)
    return text[:maxlen].strip("-") or "task"


def _harvest_urls(text: str, limit: int = 20) -> list[str]:
    """Pull candidate source URLs out of a web_search result text."""
    seen: set[str] = set()
    out: list[str] = []
    for raw in _URL_RE.findall(text or ""):
        url = raw.rstrip(".,;:")
        if _SKIP_URL_RE.search(url):
            continue
        if url in seen:
            continue
        seen.add(url)
        out.append(url)
        if len(out) >= limit:
            break
    return out


def _overlap_hits(text: str, keywords: set[str]) -> int:
    low = text.lower()
    return sum(1 for k in keywords if k in low)


_STOPWORDS = {
    "the", "and", "for", "with", "about", "latest", "find", "everything",
    "this", "week", "research", "important", "new", "all", "how", "what",
    "when", "where", "who", "why", "into", "from", "that", "have",
}


def _objective_keywords(objective: str) -> set[str]:
    toks = re.findall(r"[a-z0-9]{3,}", objective.lower())
    return {t for t in toks if t not in _STOPWORDS} or set(toks)


# Objectives that are never executed autonomously. They are not "risky, ask
# first" — they are outside what this engine is for, and LUCY's ordinary
# conversation (with its confirmation gate) is where they belong.
_REFUSE_RE = re.compile(
    r"\b(delete|remove|wipe|format)\b.{0,30}\b"
    r"(files?|folders?|directory|directories|disks?|drives?|photos?|"
    r"documents?|desktop|everything|data)\b"
    r"|\b(send|compose)\b.{0,20}\b(email|message|whatsapp|sms)\b"
    r"|\b(purchase|buy|checkout|pay|payment|transfer)\b"
    r"|\b(password|pin|passcode)\b"
    r"|\b(disable|turn off)\b.{0,25}\b(antivirus|defender|firewall|security)\b"
    r"|\b(install|uninstall)\b.{0,30}\b(software|program|app)\b"
    r"|\b(change|modify)\b.{0,25}\b(security|privacy|settings)\b",
    re.IGNORECASE)


# Tools a planned (non-research) step may call, and where it may write.
_ALLOWED_STEP_TOOLS = {
    "open_app", "web_search", "browser_control", "computer_control",
    "download_file", "save_pdf", "file_controller",
}


def _md_inline(s: str) -> str:
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<i>\1</i>", s)
    return s


def _md_to_html(md: str) -> str:
    """Minimal markdown → HTML for the report PDF.

    save_pdf passes HTML through untouched when content starts with '<', so
    the report renders with real headings and lists instead of literal '#'
    characters. Enough fidelity for a report: headings, ordered/unordered
    lists, bold, italic, paragraphs. Everything else becomes plain text.
    """
    lines_out: list[str] = []
    list_tag: str | None = None          # "ul" or "ol" while inside one

    def _close_list():
        nonlocal list_tag
        if list_tag:
            lines_out.append(f"</{list_tag}>")
            list_tag = None

    # The PDF gets its own <h1> from save_pdf's title, so a leading markdown
    # H1 is dropped here to avoid a doubled title.
    md_lines = md.replace("\r\n", "\n").split("\n")
    if md_lines and md_lines[0].lstrip().startswith("# "):
        md_lines = md_lines[1:]

    for raw in md_lines:
        line = raw.rstrip()
        if not line.strip():
            _close_list()
            continue
        esc = html.escape(line.strip())
        m = re.match(r"^(#{1,6})\s+(.*)$", esc)
        if m:
            _close_list()
            level = min(3, len(m.group(1)) + 1)          # h2..h3 — h1 is the PDF title
            lines_out.append(f"<h{level}>{_md_inline(m.group(2))}</h{level}>")
            continue
        m = re.match(r"^[-*]\s+(.*)$", esc)
        if m:
            if list_tag != "ul":
                _close_list()
                lines_out.append("<ul>")
                list_tag = "ul"
            lines_out.append(f"<li>{_md_inline(m.group(1))}</li>")
            continue
        m = re.match(r"^\d+[.)]\s+(.*)$", esc)
        if m:
            if list_tag != "ol":
                _close_list()
                lines_out.append("<ol>")
                list_tag = "ol"
            lines_out.append(f"<li>{_md_inline(m.group(1))}</li>")
            continue
        _close_list()
        lines_out.append(f"<p>{_md_inline(esc)}</p>")

    _close_list()
    return "\n".join(lines_out)


class _Stopped(Exception):
    """Raised inside the task loop when the user interrupted Serious Mode."""


class SeriousEngine:
    """One autonomous Serious Mode task at a time. See the module docstring."""

    def __init__(self):
        self._lock = threading.RLock()
        self._thread: threading.Thread | None = None
        self._mode_active = False        # execution mode flag (vs task state)
        self._state = "IDLE"
        self._objective = ""
        self._stop_flag = threading.Event()
        self._started_at = 0.0
        self._limits: dict = get_serious_limits()

        # Task artifacts
        self._workspace: Path | None = None
        self._plan: dict | None = None
        self._sources: list[dict] = []   # {url, title, where, status}
        self._docs: list[dict] = []      # {url, title, text, file}
        self._errors: list[str] = []
        self._counters = {"searches": 0, "screenshots": 0, "pdfs": 0}

        # Channels, wired by main.py. Defaults keep the engine usable in
        # standalone tests with no session and no HUD.
        self._notify_cb = lambda msg: print(f"[Serious] {msg}")
        self._log_cb = lambda msg: print(f"[Serious:log] {msg}")
        self._content_cb = None
        self._state_cb = None
        self._restore_cb = None

    # ── Channels ─────────────────────────────────────────────────────────────

    def set_channels(self, notify=None, log=None, content=None,
                     state=None, restore=None) -> None:
        """Wire the HUD + live-session hooks. Called once from main.py.

        notify  — short progress sentence, spoken through the live session
        log     — a line in the HUD activity log (not spoken)
        content — (title, text) shown in the content panel
        state   — HUD state during a step (e.g. "PROCESSING")
        restore — called when a task ends, returns the HUD to normal
        """
        if notify is not None:
            self._notify_cb = notify
        if log is not None:
            self._log_cb = log
        if content is not None:
            self._content_cb = content
        if state is not None:
            self._state_cb = state
        if restore is not None:
            self._restore_cb = restore

    def _notify(self, msg: str) -> None:
        try:
            self._notify_cb(str(msg)[:300])
        except Exception:
            pass

    def _log(self, msg: str) -> None:
        try:
            self._log_cb(f"SERIOUS: {str(msg)[:180]}")
        except Exception:
            pass

    def _content(self, title: str, text: str) -> None:
        if self._content_cb:
            try:
                self._content_cb(str(title)[:48], str(text)[:4000])
            except Exception:
                pass

    def _hud_step(self) -> None:
        if self._state_cb:
            try:
                self._state_cb("PROCESSING")
            except Exception:
                pass

    # ── State machine ────────────────────────────────────────────────────────

    def _set_state(self, state: str) -> None:
        with self._lock:
            self._state = state
        self._log(f"state → {state}")

    # ── Public API (called from the serious_mode tool) ──────────────────────

    def activate(self) -> str:
        with self._lock:
            self._mode_active = True
        self._log("Serious Mode activated.")
        return 'Say exactly: "Serious mode activated. What task do I need to do, boss?"'

    def deactivate(self) -> None:
        with self._lock:
            self._mode_active = False

    def is_busy(self) -> bool:
        with self._lock:
            return bool(self._thread and self._thread.is_alive()
                        and self._state not in ("COMPLETED", "STOPPED", "FAILED"))

    def describe(self) -> str:
        with self._lock:
            src = len(self._sources)
            docs = len(self._docs)
            ws = self._workspace.name if self._workspace else "-"
            return (f"state={self._state} objective={self._objective[:80]!r} "
                    f"sources={src} documents_saved={docs} workspace={ws} "
                    f"errors={len(self._errors)}")

    def start(self, objective: str) -> str:
        objective = (objective or "").strip()
        if not objective:
            return ("[SERIOUS_MODE_NEEDS_OBJECTIVE] Serious Mode is active but no "
                    "objective was given. Ask the user what task they need, in one "
                    "short sentence.")
        if _REFUSE_RE.search(objective):
            self._log(f"Refused objective (outside safety boundaries): {objective[:80]}")
            return ("[SERIOUS_MODE_REFUSED] This objective is outside Serious Mode's "
                    "safety boundaries (deleting files, sending messages, purchases, "
                    "account or security changes). Do NOT perform any part of it. "
                    "Tell the user Serious Mode cannot take this on, in one short "
                    "sentence, and suggest they handle it directly.")

        with self._lock:
            if self.is_busy():
                return ("[SERIOUS_MODE_BUSY] A Serious Mode task is already running "
                        f"({self.describe()}). Tell the user in one short sentence; "
                        "they can say 'stop serious mode' first.")
            self._objective = objective
            self._state = "IDLE"
            self._stop_flag.clear()
            self._started_at = time.monotonic()
            self._limits = get_serious_limits()       # fresh limits per task
            self._sources, self._docs, self._errors = [], [], []
            self._counters = {"searches": 0, "screenshots": 0, "pdfs": 0}
            self._plan = None
            self._thread = threading.Thread(
                target=self._task_guard, name="serious-mode", daemon=True)
            self._thread.start()
        return ("[SERIOUS_MODE_STARTED] The task is running in the background. "
                "Tell the user in ONE short sentence that you have started working "
                "on it. Progress updates will arrive on their own; do not ask what "
                "to do next.")

    def stop(self, reason: str = "user request") -> bool:
        """Signal the running task to stop. Returns True if something stopped."""
        with self._lock:
            running = self.is_busy()
            self._stop_flag.set()
        if running:
            self._log(f"Stop requested ({reason}).")
        return running

    # ── Task scaffolding ─────────────────────────────────────────────────────

    def _check_stop(self) -> None:
        if self._stop_flag.is_set():
            raise _Stopped()

    def _timed_out(self) -> bool:
        budget = float(self._limits.get("time_budget_minutes", 12)) * 60.0
        return (time.monotonic() - self._started_at) > budget

    def _budget_left(self) -> bool:
        if self._timed_out():
            self._log("Time budget reached — finishing with what was collected.")
            return False
        if self._failures_exceeded():
            return False
        return True

    def _failures_exceeded(self) -> bool:
        return len(self._errors) >= int(self._limits.get("max_failures", 5))

    def _task_guard(self):
        """Thread body: never lets an exception escape into the void."""
        try:
            self._execute_objective()
        except _Stopped:
            self._set_state("STOPPED")
            self._notify("Serious Mode stopped. Files collected so far are kept.")
            self._finish_hud()
        except Exception as e:
            traceback.print_exc()
            self._errors.append(f"Task error: {e}")
            self._set_state("FAILED")
            self._notify("Serious Mode hit a problem and stopped early. "
                         "Everything collected so far is saved.")
            self._finish_hud()

    def _finish_hud(self) -> None:
        if self._restore_cb:
            try:
                self._restore_cb()
            except Exception:
                pass

    def _close_browser(self) -> None:
        """Close automation browser sessions opened during collection.
        The user's own browser windows are left alone."""
        try:
            _browser_control({"action": "close_all"})
            self._log("Automation browser sessions closed.")
        except Exception as e:
            self._log(f"Browser cleanup skipped: {e}")

    def _make_workspace(self) -> Path:
        base = _base_dir()
        base.mkdir(parents=True, exist_ok=True)
        name = f"{_slugify(self._objective, 40)}_{datetime.now():%Y-%m-%d}"
        ws = base / name
        n = 2
        while ws.exists():
            ws = base / f"{name}_{n}"        # never overwrite a previous session
            n += 1
        for sub in ("Screenshots", "PDFs", "Articles", "Sources", "Notes"):
            (ws / sub).mkdir(parents=True, exist_ok=True)

        undo_ws = ws
        def _undo_workspace():
            shutil.rmtree(undo_ws, ignore_errors=True)
            return f"Removed Serious Mode workspace '{undo_ws.name}'."
        push_undo(f"created Serious Mode workspace {ws.name}", _undo_workspace)

        self._log(f"Workspace: {ws}")
        return ws

    # ── Planning ─────────────────────────────────────────────────────────────

    def _plan_task(self) -> dict:
        self._set_state("PLANNING")
        self._hud_step()
        plan = gemini.as_json(
            "You are the task planner of a desktop assistant's Serious Mode. "
            "The user gives an objective; decide how to execute it.\n"
            "For research objectives return {\"type\": \"research\", \"title\": \"...\", "
            "\"queries\": [3-6 focused web-search queries covering different angles, "
            "recent news, official sources]}.\n"
            "For a concrete non-research computer task return {\"type\": \"steps\", "
            "\"title\": \"...\", \"steps\": [{\"tool\": \"open_app|web_search|"
            "browser_control|computer_control|download_file|save_pdf|file_controller\", "
            "\"args\": {...}, \"why\": \"...\"}]} — at most 10 steps, no destructive "
            "actions, no messages, no purchases.\n"
            "Return ONLY the JSON.\n\nOBJECTIVE: " + self._objective,
            tier=gemini.FAST, timeout_ms=20_000,
        )
        if not isinstance(plan, dict) or not plan.get("type"):
            # Deterministic fallback: a single-query research task. Planning is
            # an optimisation, never a dependency.
            plan = {"type": "research", "title": self._objective[:60],
                    "queries": [self._objective]}
        plan.setdefault("title", self._objective[:60])
        self._plan = plan
        try:
            (self._workspace / "Notes" / "plan.json").write_text(
                json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass

        if plan["type"] == "research":
            qs = plan.get("queries") or [self._objective]
            self._notify(f"Plan ready — {len(qs)} research angles. Starting research.")
        else:
            self._notify(f"Plan ready — {len(plan.get('steps', []))} steps. Starting.")
        return plan

    # ── Research pipeline ────────────────────────────────────────────────────

    def _research_pipeline(self) -> None:
        self._notify("Starting research.")

        # 1. Search — RESEARCHING
        self._set_state("RESEARCHING")
        queries = (self._plan or {}).get("queries") or [self._objective]
        max_searches = int(self._limits["max_searches"])
        keywords = _objective_keywords(self._objective)
        for i, q in enumerate(queries[:max_searches], 1):
            self._check_stop()
            if not self._budget_left():
                break
            self._hud_step()
            self._notify(f"I'm searching for reliable sources ({i}/{min(len(queries), max_searches)}).")
            try:
                result = _web_search({"query": q, "mode": "news" if "news" in q.lower() else "search"})
            except Exception as e:
                result = f"Search failed: {e}"
            self._counters["searches"] += 1
            ok = result and not result.startswith(("No results", "No news", "Search failed", "Please provide"))
            self._log(f"Search {i}/{max_searches}: {'ok' if ok else 'failed'} — {q[:60]}")
            if not ok:
                self._errors.append(f"Search failed: {q}")
                continue
            # Evidence: the search result text itself is worth keeping.
            note_body = result
            # URLs from the result text. Gemini-grounded answers often carry
            # none, so fall back to the structured DDG results that
            # web_search itself uses — same backend, no second search system.
            urls = _harvest_urls(result)
            titles: dict[str, str] = {}
            if not urls:
                try:
                    ddg = _ddg_search(q, max_results=4)
                except Exception:
                    ddg = []
                if ddg:
                    urls = [d["url"] for d in ddg if d.get("url")]
                    titles = {d["url"]: (d.get("title") or "") for d in ddg
                              if d.get("url")}
                    links = [""] + [f"- {d.get('title', '')} — {d.get('snippet', '')[:160]} {d['url']}"
                                    for d in ddg if d.get("url")]
                    note_body = result + "\nRELATED LINKS:\n" + "\n".join(links)
            self._save_note(f"search_{i:02d}_{_slugify(q, 30)}.txt",
                            f"QUERY: {q}\nSAVED: {datetime.now():%Y-%m-%d %H:%M}\n\n{note_body}")
            for url in urls:
                if all(u != url for u in (s["url"] for s in self._sources)):
                    self._sources.append({"url": url, "title": titles.get(url, ""),
                                          "where": "search", "status": "pending"})

        if not self._budget_left() and not self._sources:
            self._errors.append("No sources found before the budget ran out.")

        # 2. Collect — COLLECTING
        self._set_state("COLLECTING")
        good = [s for s in self._sources if s["status"] == "pending"]
        max_sources = int(self._limits["max_sources"])
        if good:
            self._notify(f"I found {min(len(good), max_sources)} relevant sources.")
        for i, src in enumerate(good[:max_sources], 1):
            self._check_stop()
            if not self._budget_left():
                break
            self._hud_step()
            self._notify(f"I'm collecting supporting evidence ({i}/{min(len(good), max_sources)}).")
            self._collect_source(src)

        # 3. Cross-check — PROCESSING
        self._set_state("PROCESSING")
        self._hud_step()
        verification = self._verify()

        # 4. Organise + report — REPORTING
        self._check_stop()
        self._set_state("REPORTING")
        self._notify("I'm organizing the research.")
        self._write_sources_md()
        self._hud_step()
        self._notify("Final report is being generated.")
        report_path = self._generate_report(verification)

        self._set_state("COMPLETED")
        n_docs = len(self._docs)
        summary = (f"Research complete. {n_docs} sources saved"
                   + (f", {self._counters['pdfs']} PDFs" if self._counters["pdfs"] else "")
                   + (f", {self._counters['screenshots']} screenshots" if self._counters["screenshots"] else "")
                   + (f", {len(self._errors)} issues noted" if self._errors else "")
                   + f". The report is at {report_path.name if report_path else 'the workspace'}.")
        self._notify(summary)
        self._content(f"SERIOUS — {(self._plan or {}).get('title', '')[:40]}", summary)
        self._finish_hud()

    # ── Source collection ────────────────────────────────────────────────────

    def _collect_source(self, src: dict) -> None:
        url = src["url"]
        try:
            if url.lower().split("?")[0].endswith(".pdf"):
                self._collect_pdf(src)
                return

            opened = _browser_control({"action": "go_to", "url": url})
            if not str(opened).startswith("Opened"):
                raise RuntimeError(f"could not open page: {str(opened)[:80]}")

            text = str(_browser_control({"action": "get_text"}))
            if (text.startswith(("Could not", "Browser error", "Browser action", "Unknown"))
                    or len(text) < int(self._limits["min_article_chars"])):
                raise RuntimeError("page text unreadable or too short")

            if not _overlap_hits(text[:4000], _objective_keywords(self._objective)) and len(self._docs) >= 2:
                # Not obviously on-topic and we already have evidence: skip
                # rather than save everything blindly.
                src["status"] = "skipped (off-topic)"
                self._log(f"Skipped (off-topic): {url[:70]}")
                return

            text = text[:20000]
            file = self._save_article(url, src.get("title") or "", text, "webpage")
            src["status"] = "saved"
            self._docs.append({"url": url, "title": src.get("title") or url,
                               "text": text, "file": file})

            if self._counters["screenshots"] < int(self._limits["max_screenshots"]) \
                    and len(self._docs) <= int(self._limits["max_screenshots"]):
                self._save_screenshot(url)
        except Exception as e:
            src["status"] = f"failed ({str(e)[:60]})"
            self._errors.append(f"{url[:70]}: {e}")
            self._log(f"Source failed, moving on: {str(e)[:80]}")

    def _collect_pdf(self, src: dict) -> None:
        if self._counters["pdfs"] >= int(self._limits["max_pdf_downloads"]):
            src["status"] = "skipped (PDF budget)"
            return
        url = src["url"]
        name = _slugify(src.get("title") or url.split("/")[-1] or "document", 40) + ".pdf"
        res = _download_file({"url": url, "path": str(self._workspace / "PDFs"),
                              "name": name})
        if not str(res).startswith("Downloaded"):
            raise RuntimeError(f"download failed: {str(res)[:80]}")
        self._counters["pdfs"] += 1
        pdf_path = self._workspace / "PDFs" / name
        extract = ""
        try:
            extract = str(_file_processor({"file_path": str(pdf_path),
                                           "action": "extract_text"}))
            if extract.startswith(("Processing failed", "Unsupported", "No file")):
                extract = ""
        except Exception:
            extract = ""
        if extract:
            file = self._save_article(url, name, extract[:20000], "pdf")
            self._docs.append({"url": url, "title": name, "text": extract[:20000],
                               "file": file})
        src["status"] = "saved (pdf)" if extract else "downloaded (text extraction failed)"

    def _save_note(self, name: str, content: str) -> None:
        try:
            (self._workspace / "Notes" / name).write_text(content, encoding="utf-8")
        except Exception as e:
            self._log(f"Could not save note {name}: {e}")

    def _save_article(self, url: str, title: str, text: str, kind: str) -> Path:
        n = len(self._docs) + 1
        fname = f"{n:02d}_{_slugify(title or url, 40)}.txt"
        path = self._workspace / "Articles" / fname
        header = (f"URL: {url}\nTITLE: {title}\nSAVED: {datetime.now():%Y-%m-%d %H:%M}\n"
                  f"TYPE: {kind}\n\n{'-' * 60}\n\n")
        path.write_text(header + text, encoding="utf-8")
        return path

    def _save_screenshot(self, url: str) -> None:
        try:
            img, mime = _capture_screen()
            ext = ".jpg" if "jpeg" in (mime or "") else ".png"
            n = self._counters["screenshots"] + 1
            path = self._workspace / "Screenshots" / f"{n:02d}_{_slugify(url, 30)}{ext}"
            path.write_bytes(img)
            self._counters["screenshots"] += 1
            self._log(f"Screenshot saved: {path.name}")
        except Exception as e:
            self._log(f"Screenshot failed (non-fatal): {e}")

    def _write_sources_md(self) -> None:
        lines = [f"# Sources — {self._objective}", "",
                 f"Collected: {datetime.now():%Y-%m-%d %H:%M}", ""]
        for i, s in enumerate(self._sources, 1):
            lines.append(f"{i}. {s.get('title') or '(untitled)'}")
            lines.append(f"   URL: {s['url']}")
            lines.append(f"   Status: {s['status']}   Saved: {datetime.now():%Y-%m-%d %H:%M}")
            lines.append("")
        try:
            (self._workspace / "Sources" / "sources.md").write_text(
                "\n".join(lines), encoding="utf-8")
        except Exception as e:
            self._log(f"Could not write sources.md: {e}")

    # ── Verification & report ────────────────────────────────────────────────

    def _verify(self) -> dict:
        """Cross-check the collected evidence. Returns {} on any failure —
        verification is a quality step, never a dependency."""
        if len(self._docs) < 2:
            return {}
        try:
            evidence = "\n\n".join(
                f"[{i + 1}] {d['title']} ({d['url']})\n{d['text'][:2500]}"
                for i, d in enumerate(self._docs[:8]))
            out = gemini.as_json(
                "You are cross-checking research evidence collected from several "
                "web sources. Identify: claims that CONFLICT between sources, "
                "points that remain UNCERTAIN or single-sourced, and IMPORTANT "
                "DATES mentioned. Return ONLY JSON: {\"conflicts\": [\"...\"], "
                "\"uncertainties\": [\"...\"], \"dates\": [\"...\"]}\n\n"
                "OBJECTIVE: " + self._objective + "\n\nEVIDENCE:\n" + evidence,
                tier=gemini.SMART, timeout_ms=45_000,
            )
            if isinstance(out, dict):
                try:
                    (self._workspace / "Notes" / "verification.json").write_text(
                        json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
                except Exception:
                    pass
                return out
        except Exception as e:
            self._log(f"Cross-check failed (non-fatal): {e}")
        return {}

    def _generate_report(self, verification: dict) -> Path | None:
        md = ""
        try:
            evidence = "\n\n".join(
                f"[{i + 1}] {d['title']} ({d['url']})\n{d['text'][:2500]}"
                for i, d in enumerate(self._docs[:8]))
            search_notes = ""
            try:
                notes = sorted((self._workspace / "Notes").glob("search_*.txt"))
                search_notes = "\n".join(
                    f"--- {p.name} ---\n{p.read_text(encoding='utf-8')[:1500]}"
                    for p in notes[:6])
            except Exception:
                pass
            sections = ("TITLE, OBJECTIVE, EXECUTIVE SUMMARY, KEY FINDINGS, "
                        "IMPORTANT DETAILS, SOURCE-BY-SOURCE INFORMATION, "
                        "CONFLICTING INFORMATION / UNCERTAINTY, IMPORTANT DATES, "
                        "SOURCE LINKS, CONCLUSION")
            md = gemini.text(
                "Write the final research report in markdown using EXACTLY these "
                f"sections, in this order, as headings: {sections}.\n"
                "Base every claim ONLY on the evidence below; where evidence is "
                "thin or conflicting, say so in CONFLICTING INFORMATION / "
                "UNCERTAINTY. List every source URL under SOURCE LINKS. Be "
                "concrete: numbers, dates, names.\n\n"
                "OBJECTIVE: " + self._objective
                + "\n\nCROSS-CHECK NOTES (may be empty):\n"
                + json.dumps(verification, ensure_ascii=False)[:2000]
                + "\n\nARTICLE EVIDENCE:\n" + (evidence or "(none — searches only)")
                + "\n\nSEARCH RESULT NOTES:\n" + (search_notes or "(none)"),
                tier=gemini.SMART, timeout_ms=60_000,
            )
        except Exception as e:
            self._errors.append(f"Report generation error: {e}")
            self._log(f"Report synthesis failed: {e}")

        if not md:
            # Never leave the user without a report: assemble the raw evidence
            # deterministically if the model could not produce one.
            md = (f"# {self._objective}\n\n"
                  "The synthesis model was unavailable; raw evidence is included "
                  "below and in the Articles folder.\n\n"
                  + "\n\n".join(f"## {d['title']}\nSource: {d['url']}\n\n{d['text'][:3000]}"
                                for d in self._docs))

        if self._errors:
            md += "\n\n## ISSUES ENCOUNTERED\n" + "\n".join(f"- {e}" for e in self._errors)

        try:
            (self._workspace / "Notes" / "report_source.md").write_text(
                md, encoding="utf-8")
        except Exception as e:
            self._log(f"Could not save report markdown: {e}")

        try:
            res = _save_pdf({
                "content": "<!doctype html><html><head><meta charset='utf-8'>"
                           "<style>body{font-family:Segoe UI,Arial,sans-serif;"
                           "margin:2.2cm;font-size:11pt;line-height:1.45;color:#111}"
                           "h1{font-size:17pt;margin:0 0 .6em}h2{font-size:14pt;"
                           "margin:1em 0 .3em}h3{font-size:12pt}p{margin:.35em 0}"
                           "li{margin:.15em 0}</style></head><body>"
                           + _md_to_html(md) + "</body></html>",
                "title": f"Final Report — {(self._plan or {}).get('title', '')[:70]}",
                "path": str(self._workspace),
                "name": "Final_Report.pdf",
            })
            if str(res).startswith("PDF saved"):
                self._log(f"Final report: {res}")
                return self._workspace / "Final_Report.pdf"
            self._errors.append(f"PDF report failed: {res}")
        except Exception as e:
            self._errors.append(f"PDF report failed: {e}")
        return None

    # ── Non-research objectives ──────────────────────────────────────────────

    def _steps_pipeline(self, plan: dict) -> None:
        steps = [s for s in (plan.get("steps") or [])
                 if isinstance(s, dict) and s.get("tool") in _ALLOWED_STEP_TOOLS]
        skipped = len(plan.get("steps") or []) - len(steps)
        if skipped:
            self._errors.append(f"{skipped} planned step(s) outside the safe tool "
                                "whitelist were not executed.")
        max_steps = int(self._limits["max_steps"])
        results: list[str] = []
        for i, step in enumerate(steps[:max_steps], 1):
            self._check_stop()
            if not self._budget_left():
                break
            self._hud_step()
            tool, args = step["tool"], dict(step.get("args") or {})
            self._log(f"Step {i}/{min(len(steps), max_steps)}: {tool} "
                      f"{json.dumps(args, ensure_ascii=False)[:80]}")
            try:
                result = self._run_step(tool, args)
                results.append(f"[{i}] {tool}: {str(result)[:400]}")
            except Exception as e:
                self._errors.append(f"Step {i} ({tool}) failed: {e}")
                results.append(f"[{i}] {tool}: FAILED — {e}")
                if self._failures_exceeded():
                    self._log("Failure budget reached — stopping the step list.")
                    break

        self._write_sources_md()
        self._save_note("steps_log.md",
                        f"# Steps — {self._objective}\n\n" + "\n\n".join(results))
        self._set_state("COMPLETED")
        done = sum(1 for r in results if "FAILED" not in r)
        summary = (f"Task finished: {done}/{len(results)} steps completed"
                   + (f", {len(self._errors)} issues noted" if self._errors else "")
                   + f". Everything is saved in '{self._workspace.name}'.")
        self._notify(summary)
        self._content("SERIOUS — " + (plan.get("title") or "")[:40], summary)
        self._finish_hud()

    def _run_step(self, tool: str, args: dict) -> str:
        """Execute one planned step with workspace confinement where it matters."""
        if tool == "open_app":
            return str(_open_app(args))
        if tool == "web_search":
            return str(_web_search(args))
        if tool == "browser_control":
            # Reading and navigation are fine; block actions that would type or
            # click into the user's accounts unsupervised.
            if args.get("action", "").lower() in ("click", "type", "smart_type",
                                                  "fill_form", "press"):
                return "Blocked: interactive typing/clicking is not autonomous in Serious Mode."
            return str(_browser_control(args))
        if tool == "computer_control":
            if args.get("action", "").lower() == "screenshot":
                self._save_screenshot(str(args.get("path", "screen")))
                return "Screenshot saved to the workspace."
            return "Blocked: only screenshots are allowed via computer_control in Serious Mode."
        if tool == "download_file":
            args.setdefault("path", str(self._workspace / "PDFs"))
            return str(_download_file(args))
        if tool == "save_pdf":
            args.setdefault("path", str(self._workspace))
            return str(_save_pdf(args))
        if tool == "file_controller":
            action = str(args.get("action", "")).lower()
            target = str(args.get("path", ""))
            inside = _is_inside(self._workspace, target)
            if action in ("delete", "move", "rename", "copy") and not inside:
                return "Blocked: Serious Mode only modifies files inside its own workspace."
            return str(_file_controller_step(args))
        return f"Unknown tool: {tool}"

    # ── Objective entry point ────────────────────────────────────────────────

    def _execute_objective(self) -> None:
        self._workspace = self._make_workspace()
        plan = self._plan_task()
        if plan["type"] == "steps":
            self._steps_pipeline(plan)
        else:
            self._research_pipeline()
        self._close_browser()


def _is_inside(base: Path, target: str) -> bool:
    try:
        t = Path(target).expanduser().resolve()
        return str(t).startswith(str(base.resolve()))
    except Exception:
        return False


def _file_controller_step(args: dict) -> str:
    """file_controller handler, imported lazily to keep the module import graph
    light (it is only needed for non-research objectives)."""
    from actions.file_controller import file_controller as _fc
    return str(_fc(args))


# ── Module-level singleton + public helpers ──────────────────────────────────

_ENGINE = SeriousEngine()
_ENGINE_LOCK = threading.Lock()


def get_engine() -> SeriousEngine:
    return _ENGINE


def wire(**channels) -> None:
    """main.py calls this once at startup (see SeriousEngine.set_channels)."""
    _ENGINE.set_channels(**channels)


def request_stop(reason: str = "user request") -> bool:
    """Stop the active task. Used by the ESC interrupt and the voice command."""
    return _ENGINE.stop(reason)


def is_active() -> bool:
    return _ENGINE.is_busy()
