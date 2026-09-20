"""
actions/creator_info.py — Creator and Developer Attribution for JARVIS / LUCY.
"""
from __future__ import annotations

import re

CREATOR_NAME = "Soreblitz"

TARGETS = (
    r"(?:you|u|ya|yourself|jarvis|lucy|"
    r"this(?:\s+ai|\s+assistant|\s+app|\s+application|\s+software|\s+system|\s+program|\s+bot)?|"
    r"the(?:\s+ai|\s+assistant|\s+app|\s+application|\s+software|\s+system|\s+program|\s+bot)|"
    r"it)"
)

CREATION_VERBS = (
    r"(?:made|make|created|create|developed|develop|built|build|"
    r"programmed|program|designed|design|coded|code|wrote|write|"
    r"authored|author|invented|invent)"
)

ROLES = (
    r"(?:creator|developer|builder|maker|programmer|designer|author|architect|owner)"
)

_PATTERNS = [
    # "who (made/created/...) (you/jarvis/...)"
    re.compile(rf"\bwho\s+(?:all\s+)?{CREATION_VERBS}\s+{TARGETS}\b", re.IGNORECASE),
    # "who is/are ('s) (your/the) (creator/developer/...)"
    re.compile(rf"\bwho(?:\s+is|\s*'s|\s+are)?\s+(?:the\s+|your\s+)?{ROLES}\b", re.IGNORECASE),
    # "(your/the) (creator/developer) is who"
    re.compile(rf"\b(?:your|the)\s+{ROLES}\s+(?:is\s+who|who)\b", re.IGNORECASE),
    # "who is behind (you/jarvis/...)"
    re.compile(rf"\bwho(?:\s+is|\s*'s|\s+are)?\s+behind\s+{TARGETS}\b", re.IGNORECASE),
    # "who (owns/invented) (you/jarvis/...)"
    re.compile(rf"\bwho\s+(?:owns|invented)\s+{TARGETS}\b", re.IGNORECASE),
    # "who is soreblitz"
    re.compile(r"\bwho(?:\s+is|\s*'s)?\s+sore\s*blitz\b", re.IGNORECASE),
    # "whose (creation|ai|assistant|app|bot|software)"
    re.compile(r"\bwhose\s+(?:creation|ai|assistant|app|application|bot|software)\b", re.IGNORECASE),
]


def is_creator_query(text: str) -> bool:
    """Returns True if the text is asking who created, developed, built, or made the assistant."""
    if not text:
        return False
    t = text.strip()
    return any(p.search(t) for p in _PATTERNS)


def get_creator_response(asst_name: str = "JARVIS") -> str:
    """Returns a natural, authoritative creator attribution response."""
    return f"I was developed by {CREATOR_NAME}."


def get_creator_info(parameters: dict | None = None, player=None, **kwargs) -> str:
    """Action handler called by action registry / Gemini Live tool execution."""
    msg = (
        f"I was developed by {CREATOR_NAME}. "
        f"{CREATOR_NAME} created and built this assistant application."
    )
    if player and hasattr(player, "write_log"):
        try:
            player.write_log(f"SYS: Attribution — Developed by {CREATOR_NAME}")
        except Exception:
            pass
    return msg


TOOL = {
    "name": "get_creator_info",
    "description": (
        "Returns the verified creator and developer attribution for this assistant application. "
        "MUST be called whenever the user asks who made, created, developed, or built the assistant, "
        "who the creator is, who is behind the assistant, or who made this AI / JARVIS / LUCY."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {},
    },
    "handler": get_creator_info,
}
