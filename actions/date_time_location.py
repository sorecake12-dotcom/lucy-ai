"""
actions/date_time_location.py — Real-time Date, Time, Timezone, and Location Reporting Action.

Allows LUCY to provide real-time, accurate system local time, timezone (e.g. Asia/Kolkata / UTC+05:30),
and verified or configured location (New Delhi, India / Kolkata, India / Auto / Custom).
"""

from __future__ import annotations

import sys
from pathlib import Path

_BASE_DIR = Path(__file__).resolve().parent.parent
if str(_BASE_DIR) not in sys.path:
    sys.path.insert(0, str(_BASE_DIR))

from core.geo_time import get_realtime_datetime_info


def get_date_time_location(parameters: dict = None, player=None, **_ctx) -> str:
    """
    Returns real-time date, time, timezone, and location information.
    """
    info = get_realtime_datetime_info()
    loc_str = f"{info['city']}, {info['country']}".strip(", ")
    msg = (
        f"Right now it is {info['current_time']} on {info['current_date']}. "
        f"Timezone: {info['timezone_identifier']} ({info['utc_offset']}). "
        f"Location: {loc_str} (Source: {info['location_source']})."
    )

    if player and hasattr(player, "write_log"):
        player.write_log(f"[TimeLocation] {info['formatted_full']} | {loc_str}")

    print(f"[DateTimeLocation] {msg}")
    return msg


TOOL = {
    "name": "get_date_time_location",
    "description": (
        "Returns the computer's exact real-time local date, time, timezone, and current location. "
        "Use whenever the user asks 'what time is it?', 'what is the current time?', 'what day is it?', "
        "'what's today's date?', 'where am I?', or 'what timezone am I in?'."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {},
        "required": [],
    },
    "handler": get_date_time_location,
}
