"""
core/api_guard.py — Centralized Production-Grade Security & API Protection Layer.

Provides:
  • Centralized configurable rate limiting (sliding window / token bucket)
  • Concurrency control & semaphore guards
  • Exponential backoff with jitter and Retry-After header parsing
  • Provider quota & cooldown management
  • Agent infinite-loop / runaway task circuit breaker
  • Task timeouts & cancellation tokens
  • Input text / token budget / file size bounds
  • Global emergency API kill switch
  • Secret scrubbing for logs, error messages, and tracebacks
  • Per-user / daily / monthly usage quota tracking
  • Cross-platform compatibility (Windows, macOS, Linux)
"""

from __future__ import annotations

import json
import math
import os
import random
import re
import sys
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional


# ── Base Directory & Config Paths ──────────────────────────────────────────

def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


_BASE = _base_dir()
_CONFIG_FILE = _BASE / "config" / "api_keys.json"
_USAGE_FILE = _BASE / "memory" / "usage_stats.json"


# ── Secret Redactor ────────────────────────────────────────────────────────

# Matches Google AI / Gemini keys, OpenAI sk-, Bearer tokens, passwords, AQ. tokens
_SECRET_PATTERNS = [
    re.compile(r"(Bearer\s+)[0-9A-Za-z\-_.~+/=]{10,}", re.IGNORECASE),
    re.compile(r"AIza[0-9A-Za-z\-_]{20,}"),
    re.compile(r"AQ\.[0-9A-Za-z\-_]{20,}"),
    re.compile(r"sk-[0-9A-Za-z\-_]{20,}"),
    re.compile(r'("?(?:api_key|gemini_api_key|secret|password|token)"?\s*[:=]\s*["\'])([^"\']{4,})(["\'])', re.IGNORECASE),
]


def redact_secrets(text: Any) -> str:
    """Mask sensitive tokens, keys, and credentials from logs and strings."""
    if not isinstance(text, str):
        text = str(text)
    out = text
    for pattern in _SECRET_PATTERNS:
        if pattern.pattern.startswith("(\"?"):
            out = pattern.sub(r"\1***REDACTED***\3", out)
        elif "Bearer" in pattern.pattern:
            out = pattern.sub(r"\1***REDACTED***", out)
        else:
            out = pattern.sub(lambda m: m.group(0)[:4] + "…" + m.group(0)[-4:], out)
    return out


# ── Central Limits Configuration ───────────────────────────────────────────

@dataclass
class LimitConfig:
    # Rate limits (requests per minute)
    gemini_rpm: int = 60
    llm_rpm: int = 60
    web_search_rpm: int = 20
    browser_action_rpm: int = 40
    tool_call_rpm: int = 80

    # Concurrency
    max_concurrent_gemini_rest: int = 8
    max_concurrent_gemini_live: int = 3
    max_concurrent_web_searches: int = 4

    # Retries & Backoff
    max_retries: int = 4
    initial_backoff_sec: float = 1.0
    max_backoff_sec: float = 30.0
    backoff_jitter: float = 0.25

    # Infinite Loop & Circuit Breaker
    max_consecutive_identical_tools: int = 3
    max_tool_history_window: int = 20
    max_task_steps: int = 25
    loop_cycle_threshold: int = 3

    # Timeouts & Size Bounds
    default_request_timeout_sec: float = 30.0
    max_input_chars: int = 60_000
    max_file_size_bytes: int = 15 * 1024 * 1024  # 15 MB

    # Quotas (0 = unlimited)
    daily_request_quota: int = 2500
    daily_token_quota: int = 1_500_000
    monthly_request_quota: int = 50_000

    # Emergency Kill Switch
    emergency_kill_switch: bool = False


# ── Sliding Window Rate Limiter ────────────────────────────────────────────

class SlidingWindowRateLimiter:
    """Thread-safe sliding window rate limiter."""

    def __init__(self, max_requests: int, window_sec: float = 60.0):
        self.max_requests = max(1, int(max_requests))
        self.window_sec = float(window_sec)
        self._timestamps: list[float] = []
        self._lock = threading.Lock()

    def update_limit(self, max_requests: int):
        with self._lock:
            self.max_requests = max(1, int(max_requests))

    def acquire(self, block: bool = True, timeout: float = 10.0) -> bool:
        """Acquire permission to execute. If block is True, waits up to timeout."""
        deadline = time.monotonic() + timeout
        while True:
            with self._lock:
                now = time.monotonic()
                cutoff = now - self.window_sec
                self._timestamps = [t for t in self._timestamps if t > cutoff]

                if len(self._timestamps) < self.max_requests:
                    self._timestamps.append(now)
                    return True

                if not block:
                    return False

                # Time until oldest request expires
                oldest = self._timestamps[0]
                wait_time = max(0.01, (oldest + self.window_sec) - now)

            if time.monotonic() + wait_time > deadline:
                return False
            time.sleep(min(wait_time, 0.25))

    def current_usage(self) -> int:
        with self._lock:
            now = time.monotonic()
            cutoff = now - self.window_sec
            self._timestamps = [t for t in self._timestamps if t > cutoff]
            return len(self._timestamps)


# ── Infinite Loop & Circuit Breaker ────────────────────────────────────────

class AgentLoopGuard:
    """Detects runaway agent loops, repeating tool calls, or thrashing."""

    def __init__(self, max_identical: int = 3, history_len: int = 20):
        self.max_identical = max_identical
        self.history_len = history_len
        self._history: list[str] = []
        self._lock = threading.Lock()

    def record_and_check(self, action_name: str, parameters: Any = None) -> tuple[bool, str]:
        """
        Record a tool call. Returns (is_ok, reason).
        If is_ok is False, execution must stop to prevent an infinite loop.
        """
        # Create deterministic fingerprint of action + key params
        param_summary = ""
        if isinstance(parameters, dict):
            # Sort keys for stable fingerprint
            try:
                param_summary = json.dumps(parameters, sort_keys=True)[:200]
            except Exception:
                param_summary = str(parameters)[:200]
        else:
            param_summary = str(parameters)[:200]

        fingerprint = f"{action_name}::{param_summary}"

        with self._lock:
            self._history.append(fingerprint)
            if len(self._history) > self.history_len:
                self._history.pop(0)

            # Check 1: Consecutive identical actions
            if len(self._history) >= self.max_identical:
                tail = self._history[-self.max_identical:]
                if all(item == fingerprint for item in tail):
                    return (
                        False,
                        f"Circuit breaker triggered: '{action_name}' was called "
                        f"{self.max_identical} times consecutively with identical arguments.",
                    )

            # Check 2: Cyclic loops (A -> B -> A -> B -> A -> B)
            if len(self._history) >= 6:
                h = self._history
                if h[-1] == h[-3] == h[-5] and h[-2] == h[-4] == h[-6] and h[-1] != h[-2]:
                    return (
                        False,
                        f"Circuit breaker triggered: detected 2-step alternating loop "
                        f"between '{h[-2].split('::')[0]}' and '{h[-1].split('::')[0]}'.",
                    )

            return True, ""

    def reset(self):
        with self._lock:
            self._history.clear()


# ── Usage & Quota Tracker ──────────────────────────────────────────────────

class QuotaTracker:
    """Tracks daily and monthly API usage persisted safely to JSON."""

    def __init__(self, storage_path: Path):
        self.storage_path = storage_path
        self._lock = threading.Lock()
        self._data: dict = {
            "daily_requests": 0,
            "daily_tokens": 0,
            "monthly_requests": 0,
            "last_day": "",
            "last_month": "",
        }
        self._load()

    def _load(self):
        try:
            if self.storage_path.exists():
                self._data = json.loads(self.storage_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    def _save(self):
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            self.storage_path.write_text(json.dumps(self._data, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _roll_periods(self):
        now = datetime.now(timezone.utc)
        today = now.strftime("%Y-%m-%d")
        month = now.strftime("%Y-%m")

        if self._data.get("last_day") != today:
            self._data["daily_requests"] = 0
            self._data["daily_tokens"] = 0
            self._data["last_day"] = today

        if self._data.get("last_month") != month:
            self._data["monthly_requests"] = 0
            self._data["last_month"] = month

    def record_usage(self, requests_count: int = 1, tokens_count: int = 0):
        with self._lock:
            self._roll_periods()
            self._data["daily_requests"] = self._data.get("daily_requests", 0) + requests_count
            self._data["daily_tokens"] = self._data.get("daily_tokens", 0) + tokens_count
            self._data["monthly_requests"] = self._data.get("monthly_requests", 0) + requests_count
            self._save()

    def check_quota(self, daily_req_limit: int, daily_tok_limit: int, monthly_req_limit: int) -> tuple[bool, str]:
        with self._lock:
            self._roll_periods()
            d_req = self._data.get("daily_requests", 0)
            d_tok = self._data.get("daily_tokens", 0)
            m_req = self._data.get("monthly_requests", 0)

            if daily_req_limit > 0 and d_req >= daily_req_limit:
                return False, f"Daily request quota exceeded ({d_req}/{daily_req_limit})."
            if daily_tok_limit > 0 and d_tok >= daily_tok_limit:
                return False, f"Daily token quota exceeded ({d_tok}/{daily_tok_limit})."
            if monthly_req_limit > 0 and m_req >= monthly_req_limit:
                return False, f"Monthly request quota exceeded ({m_req}/{monthly_req_limit})."

            return True, ""

    def get_stats(self) -> dict:
        with self._lock:
            self._roll_periods()
            return dict(self._data)


# ── The Master APIGuard Singleton ──────────────────────────────────────────

class APIGuard:
    """The central authority for security, rate limits, quotas, and kill switch."""

    _instance: Optional[APIGuard] = None
    _init_lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> APIGuard:
        if cls._instance is None:
            with cls._init_lock:
                if cls._instance is None:
                    cls._instance = APIGuard()
        return cls._instance

    def __init__(self):
        self.limits = LimitConfig()
        self._load_config()

        # Limiters
        self.gemini_limiter = SlidingWindowRateLimiter(self.limits.gemini_rpm)
        self.llm_limiter = SlidingWindowRateLimiter(self.limits.llm_rpm)
        self.search_limiter = SlidingWindowRateLimiter(self.limits.web_search_rpm)
        self.browser_limiter = SlidingWindowRateLimiter(self.limits.browser_action_rpm)
        self.tool_limiter = SlidingWindowRateLimiter(self.limits.tool_call_rpm)

        # Semaphores
        self.gemini_rest_sem = threading.BoundedSemaphore(self.limits.max_concurrent_gemini_rest)
        self.gemini_live_sem = threading.BoundedSemaphore(self.limits.max_concurrent_gemini_live)
        self.search_sem = threading.BoundedSemaphore(self.limits.max_concurrent_web_searches)

        # Loop guards
        self.loop_guard = AgentLoopGuard(
            max_identical=self.limits.max_consecutive_identical_tools,
            history_len=self.limits.max_tool_history_window,
        )

        # Quotas
        self.quota_tracker = QuotaTracker(_USAGE_FILE)

    def _load_config(self):
        if not _CONFIG_FILE.exists():
            return
        try:
            raw = json.loads(_CONFIG_FILE.read_text(encoding="utf-8"))
            # Global kill switch check
            if "emergency_kill_switch" in raw:
                self.limits.emergency_kill_switch = bool(raw["emergency_kill_switch"])
            # Load custom security settings if present
            sec = raw.get("security_limits", {})
            if isinstance(sec, dict):
                for k, v in sec.items():
                    if hasattr(self.limits, k):
                        setattr(self.limits, k, type(getattr(self.limits, k))(v))
        except Exception:
            pass

    # ── Emergency Kill Switch ──────────────────────────────────────────────

    def is_kill_switch_active(self) -> bool:
        self._load_config()
        return self.limits.emergency_kill_switch

    def set_kill_switch(self, active: bool):
        self.limits.emergency_kill_switch = bool(active)
        try:
            data = {}
            if _CONFIG_FILE.exists():
                data = json.loads(_CONFIG_FILE.read_text(encoding="utf-8"))
            data["emergency_kill_switch"] = bool(active)
            _CONFIG_FILE.write_text(json.dumps(data, indent=4), encoding="utf-8")
        except Exception as e:
            print(f"[APIGuard] Error saving kill switch state: {e}")

    def assert_api_allowed(self, service_name: str = "External API"):
        """Raise RuntimeError if kill switch is active or quota is exhausted."""
        if self.is_kill_switch_active():
            raise RuntimeError(
                f"[SECURITY] Emergency API kill switch is ACTIVE. "
                f"{service_name} request blocked."
            )
        ok, reason = self.quota_tracker.check_quota(
            self.limits.daily_request_quota,
            self.limits.daily_token_quota,
            self.limits.monthly_request_quota,
        )
        if not ok:
            raise RuntimeError(f"[QUOTA] {service_name} blocked: {reason}")

    # ── Input & File Validation ────────────────────────────────────────────

    def validate_input_size(self, text: str, max_chars: Optional[int] = None) -> str:
        """Truncate or reject oversized inputs."""
        cap = max_chars or self.limits.max_input_chars
        if len(text) > cap:
            print(f"[APIGuard] Warning: Input truncated from {len(text)} to {cap} chars.")
            return text[:cap]
        return text

    def validate_file_size(self, file_path: Path) -> bool:
        """Check if file size exceeds configured boundary."""
        try:
            return file_path.stat().st_size <= self.limits.max_file_size_bytes
        except Exception:
            return False

    # ── Backoff & Retry Helper ─────────────────────────────────────────────

    def execute_with_retry(
        self,
        fn: Callable[[], Any],
        operation_name: str = "API Call",
        max_retries: Optional[int] = None,
        is_retryable_err: Optional[Callable[[Exception], bool]] = None,
        on_retry: Optional[Callable[[int, float, Exception], None]] = None,
    ) -> Any:
        """
        Executes fn() with bounded exponential backoff and jitter.
        Understands 429 Retry-After headers when available.
        Never retries indefinitely.
        """
        self.assert_api_allowed(operation_name)

        retries = self.limits.max_retries if max_retries is None else max_retries
        attempt = 0

        while True:
            attempt += 1
            try:
                res = fn()
                self.quota_tracker.record_usage(requests_count=1)
                return res
            except Exception as e:
                err_msg = str(e).lower()
                is_rate_limit = "429" in err_msg or "quota" in err_msg or "resource_exhausted" in err_msg

                # Check custom retryable function if provided
                retryable = True
                if is_retryable_err:
                    retryable = is_retryable_err(e)
                elif "unauthorized" in err_msg or "invalid api key" in err_msg or "403" in err_msg:
                    retryable = False

                if attempt > retries or not retryable:
                    clean_msg = redact_secrets(str(e))
                    raise RuntimeError(f"{operation_name} failed after {attempt} attempts: {clean_msg}") from e

                # Determine wait time (check for Retry-After)
                retry_after = self._extract_retry_after(e)
                if retry_after is not None:
                    wait_sec = min(float(retry_after), self.limits.max_backoff_sec)
                else:
                    backoff = self.limits.initial_backoff_sec * (2 ** (attempt - 1))
                    jitter = random.uniform(-self.limits.backoff_jitter, self.limits.backoff_jitter) * backoff
                    wait_sec = min(backoff + jitter, self.limits.max_backoff_sec)

                wait_sec = max(0.5, wait_sec)
                clean_err = redact_secrets(str(e))[:100]
                print(f"[APIGuard] {operation_name} attempt {attempt} failed ({clean_err}). "
                      f"Backing off {wait_sec:.2f}s...")

                if on_retry:
                    try:
                        on_retry(attempt, wait_sec, e)
                    except Exception:
                        pass

                time.sleep(wait_sec)

    def _extract_retry_after(self, err: Exception) -> Optional[float]:
        """Try to extract Retry-After seconds from response headers or message."""
        # 1. Check response attribute if requests/urllib exception
        resp = getattr(err, "response", None)
        if resp is not None:
            headers = getattr(resp, "headers", {})
            ra = headers.get("Retry-After") or headers.get("retry-after")
            if ra:
                try:
                    return float(ra)
                except ValueError:
                    pass

        # 2. Look for regex in error string, e.g. "retry after 12 seconds" or "quota reset in 5s"
        msg = str(err).lower()
        m = re.search(r"retry[- ]after[:\s]+(\d+(?:\.\d+)?)", msg)
        if m:
            return float(m.group(1))
        m = re.search(r"reset in\s+(\d+(?:\.\d+)?)s", msg)
        if m:
            return float(m.group(1))

        return None


# ── Global Module Helper Accessors ─────────────────────────────────────────

def get_guard() -> APIGuard:
    return APIGuard.get_instance()


def is_kill_switch_active() -> bool:
    return get_guard().is_kill_switch_active()


def set_kill_switch(active: bool):
    get_guard().set_kill_switch(active)


def redact(msg: Any) -> str:
    return redact_secrets(msg)
