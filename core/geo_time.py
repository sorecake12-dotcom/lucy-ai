"""
core/geo_time.py — Real-Time Date, Time, Timezone, and Geolocation Resolution.

Separates and resolves:
  1. System Local Time & Date (from host OS timezone)
  2. Timezone & UTC Offset (e.g. Asia/Kolkata, UTC+05:30)
  3. Location Resolution:
       - Auto (OS/Network geolocation with 2s timeout and 1-hour memory cache)
       - Configured City (New Delhi, India | Kolkata, India | Custom)
       - Safe default fallback (New Delhi, India / Asia/Kolkata) with honest attribution
"""

from __future__ import annotations

import json
import os
import platform
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


_BASE = _base_dir()
_CONFIG_FILE = _BASE / "config" / "api_keys.json"

# In-memory cache for auto network geolocation to prevent rate limiting
_GEO_CACHE: dict[str, Any] = {}
_GEO_CACHE_EXPIRY: float = 0.0
_GEO_LOCK = threading.Lock()


def get_system_timezone_info() -> dict[str, str]:
    """
    Detect operating system's actual local timezone, name, and UTC offset.
    Supports Asia/Kolkata and UTC+05:30.
    """
    now = datetime.now().astimezone()
    tz = now.tzinfo

    # Calculate UTC offset (+HH:MM or -HH:MM)
    offset = now.utcoffset()
    if offset is not None:
        total_seconds = int(offset.total_seconds())
        sign = "+" if total_seconds >= 0 else "-"
        abs_seconds = abs(total_seconds)
        hours = abs_seconds // 3600
        minutes = (abs_seconds % 3600) // 60
        utc_offset_str = f"UTC{sign}{hours:02d}:{minutes:02d}"
    else:
        utc_offset_str = "UTC+00:00"

    tz_name = now.tzname() or "Local"

    # Normalize tz identifier
    tz_identifier = "Local"
    if hasattr(tz, "key"):
        tz_identifier = getattr(tz, "key")
    elif "IST" in tz_name or utc_offset_str == "UTC+05:30":
        tz_identifier = "Asia/Kolkata"
    else:
        tz_identifier = tz_name

    return {
        "timezone_name": tz_name,
        "timezone_identifier": tz_identifier,
        "utc_offset": utc_offset_str,
    }


def _load_location_config() -> dict[str, str]:
    if not _CONFIG_FILE.exists():
        return {
            "location_mode": "auto",
            "fallback_city": "New Delhi",
            "fallback_country": "India",
            "custom_city": "",
            "custom_country": "",
        }
    try:
        data = json.loads(_CONFIG_FILE.read_text(encoding="utf-8"))
        settings = data.get("location_settings", {})
        if not isinstance(settings, dict):
            settings = {}
        mode = settings.get("mode") or data.get("location_mode", "auto")
        fallback_str = settings.get("fallback_city") or data.get("fallback_city", "New Delhi, India")
        fb_parts = [p.strip() for p in str(fallback_str).split(",") if p.strip()]
        fb_city = fb_parts[0] if fb_parts else "New Delhi"
        fb_country = fb_parts[1] if len(fb_parts) > 1 else str(data.get("fallback_country", "India"))
        return {
            "location_mode": str(mode).lower(),
            "fallback_city": fb_city,
            "fallback_country": fb_country,
            "custom_city": str(data.get("custom_city", "")),
            "custom_country": str(data.get("custom_country", "")),
        }
    except Exception:
        return {
            "location_mode": "auto",
            "fallback_city": "New Delhi",
            "fallback_country": "India",
            "custom_city": "",
            "custom_country": "",
        }


def _query_network_geolocation() -> Optional[dict[str, Any]]:
    """
    Perform a non-intrusive, fast geolocation lookup via public IP API.
    Cached for 1 hour. Never claims GPS precision.
    """
    global _GEO_CACHE, _GEO_CACHE_EXPIRY
    now = time.monotonic()

    with _GEO_LOCK:
        if _GEO_CACHE and now < _GEO_CACHE_EXPIRY:
            return dict(_GEO_CACHE)

    import urllib.request

    url = "https://ipapi.co/json/"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "LUCY-Assistant-GeoResolver/1.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=2.5) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                city = data.get("city")
                country = data.get("country_name") or data.get("country")
                tz = data.get("timezone")
                if city:
                    res = {
                        "city": city,
                        "country": country or "",
                        "timezone": tz or "",
                        "source": "Network IP Geolocation (Approximate)",
                        "is_exact_gps": False,
                    }
                    with _GEO_LOCK:
                        _GEO_CACHE = res
                        _GEO_CACHE_EXPIRY = now + 3600.0  # 1 hour
                    return res
    except Exception:
        pass

    return None


def get_location_info() -> dict[str, Any]:
    """
    Resolve location according to user settings and preferred order:
      1. Configured selection (New Delhi, Kolkata, Custom)
      2. Auto OS / Network location provider
      3. Safe default fallback (New Delhi, India / Asia/Kolkata)
    """
    cfg = _load_location_config()
    mode = cfg.get("location_mode", "auto")

    if mode in ("new delhi", "new delhi, india", "new_delhi"):
        return {
            "city": "New Delhi",
            "country": "India",
            "timezone": "Asia/Kolkata",
            "source": "User Configured City (New Delhi)",
            "is_exact_gps": False,
        }

    if mode in ("kolkata", "kolkata, india"):
        return {
            "city": "Kolkata",
            "country": "India",
            "timezone": "Asia/Kolkata",
            "source": "User Configured City (Kolkata)",
            "is_exact_gps": False,
        }

    if mode == "custom" and cfg.get("custom_city"):
        return {
            "city": cfg["custom_city"],
            "country": cfg.get("custom_country", ""),
            "timezone": "Local",
            "source": "User Custom City",
            "is_exact_gps": False,
        }

    # Auto mode: attempt network/OS geolocation lookup
    net_geo = _query_network_geolocation()
    if net_geo:
        return net_geo

    # Default Fallback: New Delhi, India
    fallback_city = cfg.get("fallback_city") or "New Delhi"
    fallback_country = cfg.get("fallback_country") or "India"
    return {
        "city": fallback_city,
        "country": fallback_country,
        "timezone": "Asia/Kolkata",
        "source": "Default Fallback (Auto-detection unavailable)",
        "is_exact_gps": False,
    }


def get_realtime_datetime_info() -> dict[str, Any]:
    """
    Compile unified real-time date, time, timezone, and location state.
    """
    now = datetime.now().astimezone()
    tz_info = get_system_timezone_info()
    loc_info = get_location_info()

    time_str = now.strftime("%I:%M %p").lstrip("0")
    date_str = now.strftime("%A, %B %d, %Y")
    full_str = f"{date_str} — {time_str}"

    return {
        "current_time": time_str,
        "current_date": date_str,
        "formatted_full": full_str,
        "timezone_name": tz_info["timezone_name"],
        "timezone_identifier": tz_info["timezone_identifier"],
        "utc_offset": tz_info["utc_offset"],
        "city": loc_info["city"],
        "country": loc_info["country"],
        "location_source": loc_info["source"],
        "is_exact_gps": loc_info["is_exact_gps"],
    }


def get_realtime_prompt_context() -> str:
    """
    Returns high-priority system context string for prompt injection.
    """
    info = get_realtime_datetime_info()
    loc_display = f"{info['city']}, {info['country']}".strip(", ")

    return (
        f"[REAL-TIME DATE, TIME & LOCATION]\n"
        f"Right now it is: {info['formatted_full']}\n"
        f"Timezone: {info['timezone_identifier']} ({info['utc_offset']})\n"
        f"Current Location: {loc_display} ({info['location_source']})\n"
        f"CRITICAL RULES:\n"
        f"1. Use this exact date ({info['current_date']}) and time ({info['current_time']}) for any time/date query.\n"
        f"2. For local weather or location queries, use {loc_display}.\n"
        f"3. Do NOT claim exact GPS precision when source is network or fallback.\n\n"
    )
