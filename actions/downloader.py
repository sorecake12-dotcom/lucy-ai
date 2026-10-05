"""
download_file — fetch a file from a URL onto this machine.

Until now the only thing LUCY could ever bring back from the web was text:
search results, page contents, transcripts. A "download this" request had no
tool behind it, so the model could only mime one. This gives the request a
real handler.

Design notes:
  * Streams to a temp file first, then moves into place — a half-downloaded
    file never sits under its final name.
  * Reuses file_controller's path resolution and home-root safety check, so a
    download can only land where every other file action can write: inside the
    user's profile. One source of truth for that rule, not two.
  * Undo removes the downloaded file only — the URL is never touched.
  * A generous hard cap guards against a runaway download filling the disk.
    2 GB covers anything a voice command reasonably fetches; past it the
    transfer is aborted, the temp file removed, and the user told why.
"""

from __future__ import annotations

import tempfile
import time
import uuid
from pathlib import Path

import requests

from actions.file_controller import _is_safe_path, _resolve_path
from core.undo import push_undo

_MAX_BYTES = 2_000_000_000          # 2 GB
_TIMEOUT   = (15, 300)              # (connect, read) seconds


def _filename_from_url(url: str, current_name: str) -> str:
    """Explicit name wins; otherwise take the last URL segment, or a timestamp."""
    if current_name:
        return current_name
    tail = url.split("?", 1)[0].split("#", 1)[0].rstrip("/").split("/")[-1]
    tail = tail.replace("\\", "_").replace("/", "_").strip() or ""
    if tail and not tail.startswith("."):
        return tail[:150]
    return f"download_{time.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"


def download_file(
    parameters=None,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    params = parameters or {}
    url    = str(params.get("url", "")).strip()
    if not url.lower().startswith(("http://", "https://")):
        return "download_file needs a URL starting with http:// or https://."

    try:
        base = _resolve_path(str(params.get("path", "") or "downloads"))
    except Exception:
        base = Path.home() / "Downloads"
    name     = _filename_from_url(url, str(params.get("name", "")).strip())
    target   = base / name

    if not _is_safe_path(target):
        return f"Access denied: {target}"

    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and not str(params.get("overwrite", "")).lower() in ("1", "true", "yes"):
        return f"File already exists: {target}. Call again with overwrite=true to replace it."

    # Stream to a temp file beside the destination, then move — the final name
    # only ever holds a complete file, whatever happens to the connection.
    tmp = target.parent / f".lucy_dl_{uuid.uuid4().hex}.part"
    try:
        with requests.get(url, stream=True, timeout=_TIMEOUT,
                          headers={"User-Agent": "Mozilla/5.0"}) as r:
            r.raise_for_status()
            done = 0
            with open(tmp, "wb") as f:
                for chunk in r.iter_content(chunk_size=1 << 16):
                    if chunk:
                        done += len(chunk)
                        if done > _MAX_BYTES:
                            raise RuntimeError(
                                f"larger than the {_MAX_BYTES // (1 << 30)} GB safety limit")
                        f.write(chunk)
        tmp.replace(target)
    except Exception as e:
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass
        return f"Download failed: {e}"

    size = target.stat().st_size
    undo = target
    def _undo_download():
        if undo.exists():
            undo.unlink()
            return f"Removed the downloaded '{undo.name}'."
        return f"'{undo.name}' is already gone."
    push_undo(f"downloaded {target.name} to {target.parent.name}/", _undo_download)

    if player:
        try:
            player.write_log(f"[download] {target.name} ({size:,} bytes)")
        except Exception:
            pass
    return f"Downloaded: {target} ({size:,} bytes)"


# ── Tool declaration (auto-discovered by core/action_loader.py) ──────────────
TOOL = {
    "name": "download_file",
    "description": (
        "Downloads a file from a URL to this computer. Use when the user asks to "
        "download, fetch, save a file from the web (PDF, image, zip, installer, "
        "dataset, anything binary or text). Saves into Downloads by default."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "url": {
                "type": "STRING",
                "description": "Direct URL of the file to download"
            },
            "path": {
                "type": "STRING",
                "description": "Destination folder or shortcut (desktop, downloads, documents...). Default: downloads"
            },
            "name": {
                "type": "STRING",
                "description": "File name to save as. Default: taken from the URL"
            },
            "overwrite": {
                "type": "BOOLEAN",
                "description": "Replace the file if it already exists (default: false)"
            },
        },
        "required": ["url"],
    },
    "handler": download_file,
}
