"""
save_pdf — turn text or HTML into a real PDF file on disk.

Reading PDFs was always covered (file_processor: summarize / extract_text).
Creating one was not: no reportlab, no print-to-PDF anywhere — so "save that
as a PDF", "make me a one-page report", "put this research into a PDF" had no
tool behind them. This fills the gap using what the project already ships:
Playwright's Chromium, which prints HTML to PDF headlessly. No new dependency.

Design notes:
  * Plain text is escaped and wrapped into paragraphs; content that starts
    with '<' is treated as HTML and passed through as-is, so the model can
    style a report when it wants to.
  * Output path goes through file_controller's resolution and home-root safety
    check, like every other file action.
  * Undo deletes the produced file only. Nothing on the web is touched.
  * A fresh headless Chromium is launched per call and stopped before
    returning — no browser session is left running, and the sync API is used
    strictly inside this one executor thread.
"""

from __future__ import annotations

import html
import tempfile
import uuid
from pathlib import Path

from actions.file_controller import _is_safe_path, _resolve_path
from core.undo import push_undo


def _wrap_as_html(content: str, title: str) -> str:
    """Escape plain text into a clean printable page; pass HTML through."""
    if content.lstrip().lower().startswith("<!doctype") or content.lstrip().startswith("<"):
        body = content
    else:
        # One <p> per blank-line-separated block; single newlines become <br>.
        body = "\n".join(
            f"<p>{html.escape(p).replace(chr(10), '<br>')}</p>"
            for p in content.replace("\r\n", "\n").split("\n\n")
        )
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>{html.escape(title)}</title><style>"
        "body{font-family:Segoe UI,Arial,sans-serif;margin:2.2cm;"
        "font-size:11pt;line-height:1.45;color:#111}"
        "h1{font-size:17pt;margin:0 0 .6em}p{margin:.35em 0}"
        "</style></head><body>"
        + (f"<h1>{html.escape(title)}</h1>" if title else "")
        + body
        + "</body></html>"
    )


def save_pdf(
    parameters=None,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    params  = parameters or {}
    content = str(params.get("content", "")).strip()
    title   = str(params.get("title", "")).strip()
    if not content:
        return "save_pdf needs 'content' — the text or HTML to put in the PDF."

    try:
        base = _resolve_path(str(params.get("path", "") or "documents"))
    except Exception:
        base = Path.home() / "Documents"
    name = (str(params.get("name", "")).strip()
            or (title.replace(" ", "_")[:80] if title else "document")
            + ".pdf")
    if not name.lower().endswith(".pdf"):
        name += ".pdf"
    target = base / name

    if not _is_safe_path(target):
        return f"Access denied: {target}"
    target.parent.mkdir(parents=True, exist_ok=True)

    page_html = _wrap_as_html(content, title)
    tmp = Path(tempfile.gettempdir()) / f"lucy_pdf_{uuid.uuid4().hex}.pdf"
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.set_content(page_html, wait_until="load")
                page.pdf(path=str(tmp), format=params.get("format", "A4"))
            finally:
                browser.close()
        tmp.replace(target)
    except Exception as e:
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass
        msg = str(e)
        if "Executable doesn't exist" in msg or "browserType.launch" in msg:
            msg = ("Chromium for Playwright is not installed. Run: "
                   "playwright install chromium")
        return f"Could not create PDF: {msg}"

    size = target.stat().st_size
    undo = target
    def _undo_pdf():
        if undo.exists():
            undo.unlink()
            return f"Removed the PDF '{undo.name}'."
        return f"'{undo.name}' is already gone."
    push_undo(f"created PDF {target.name}", _undo_pdf)

    if player:
        try:
            player.write_log(f"[pdf] {target.name} ({size:,} bytes)")
        except Exception:
            pass
    return f"PDF saved: {target} ({size:,} bytes)"


# ── Tool declaration (auto-discovered by core/action_loader.py) ──────────────
TOOL = {
    "name": "save_pdf",
    "description": (
        "Creates a PDF file from text or HTML content. Use when the user asks "
        "to save something as a PDF, produce a PDF report, document or summary, "
        "or put gathered research/news into a PDF. Saves into Documents by default."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "content": {
                "type": "STRING",
                "description": "The text or HTML to render into the PDF"
            },
            "title": {
                "type": "STRING",
                "description": "Document title shown as a heading and used for the file name"
            },
            "path": {
                "type": "STRING",
                "description": "Destination folder or shortcut (desktop, downloads, documents...). Default: documents"
            },
            "name": {
                "type": "STRING",
                "description": "File name to save as (a .pdf is added if missing). Default: from title"
            },
            "format": {
                "type": "STRING",
                "description": "Paper size: A4 (default) or Letter"
            },
        },
        "required": ["content"],
    },
    "handler": save_pdf,
}
