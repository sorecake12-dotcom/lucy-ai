"""
serious_mode — LUCY's autonomous execution mode.

An EXECUTION MODE, not a personality: GF / Assistant / Jarvis stay exactly as
they are, and Serious Mode is the layer that runs a whole OBJECTIVE — plan,
execute, collect, verify, report — instead of one command at a time.

The voice flow:
    "Lucy, go to serious mode."   → action=activate
    "Research the latest AI ..."  → action=run, objective=...
    "Lucy, stop serious mode."    → action=stop
    "What's the status?"          → action=status

Everything real happens in actions/_serious_engine.py, which orchestrates the
existing actions (web_search, browser_control, open_app, download_file,
save_pdf, file_processor, screen_processor). This file is only the tool
surface the Live model calls, plus the wiring point main.py uses to give the
engine its speech / HUD channels.
"""

from __future__ import annotations

from actions._serious_engine import (
    get_engine, request_stop, wire, is_active,
)


def serious_mode(
    parameters: dict = None,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    params  = parameters or {}
    action  = str(params.get("action", "")).lower().strip()
    objective = str(params.get("objective", "")).strip()
    engine  = get_engine()

    if action in ("activate", "start_mode", "on"):
        return engine.activate()

    if action in ("deactivate", "off"):
        request_stop("mode deactivated")
        engine.deactivate()
        return ("[SERIOUS_MODE_OFF] Serious mode is off. Tell the user in one "
                "short sentence, then continue as normal.")

    if action == "run":
        return engine.start(objective)

    if action == "stop":
        was_running = request_stop("voice command")
        engine.deactivate()
        if was_running:
            ws = engine._workspace.name if engine._workspace else "the Serious Mode folder"
            return ("[SERIOUS_MODE_STOPPED] Serious mode was stopped and the task "
                    f"was cancelled. Files already collected are preserved in "
                    f"'{ws}' under Documents/LUCY/Serious_Mode. Tell the user in "
                    "one short sentence. Do not start new actions for this task.")
        engine.deactivate()
        return ("[SERIOUS_MODE_IDLE] Serious mode was not running. Tell the user "
                "it is now off, in one short sentence.")

    if action == "status":
        return f"[SERIOUS_MODE_STATUS] {engine.describe()}"

    return ("serious_mode: unknown action. Use activate | run | stop | status | "
            "deactivate.")


# ── Tool declaration (auto-discovered by core/action_loader.py) ──────────────
TOOL = {
    "name": "serious_mode",
    "description": (
        "Serious Mode: LUCY's autonomous execution mode. When the user says "
        "'go to serious mode' or 'activate serious mode' (in ANY language), "
        "call with action='activate'. While Serious Mode is active, treat the "
        "user's next request as an OBJECTIVE: call with action='run' and the "
        "objective text — LUCY will plan, research, collect evidence, save it "
        "to a workspace and produce a final report on its own. When the user "
        "says 'stop serious mode', call with action='stop'. action='status' "
        "reports the current task. Never call action='run' for objectives "
        "involving deleting files, sending messages, purchases, or security "
        "changes — refuse those."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "activate | run | stop | status | deactivate",
            },
            "objective": {
                "type": "STRING",
                "description": (
                    "The user's objective, verbatim (action='run' only), e.g. "
                    "'Research the latest AI developments'"
                ),
            },
        },
        "required": ["action"],
    },
    "handler": serious_mode,
}
