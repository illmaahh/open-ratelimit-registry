from __future__ import annotations

import email.utils
import json
import pathlib
import random
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Mapping

_REGISTRY_PATH = pathlib.Path(__file__).resolve().parent / "registry.json"
_REGISTRY = json.loads(_REGISTRY_PATH.read_text(encoding="utf-8"))["providers"]

_DURATION_RE = re.compile(r"(\d+(?:\.\d+)?)(ms|s|m|h|d)")
_IETF_PARAM_RE = re.compile(r"\b([a-z]+)=(\d+)")
_HTTP_STATUS_RE = re.compile(r"^HTTP/\d(?:\.\d)?\s+(\d{3})\b", re.IGNORECASE)


@dataclass
class RateLimitBucketState:
    name: str
    unit: str
    limit: int | None = None
    remaining: int | None = None
    used: int | None = None
    reset_after_ms: int | None = None
    reset_at: str | None = None


@dataclass
class RateLimitResult:
    provider: str | None
    is_limited: bool
    limit: int | None = None
    remaining: int | None = None
    reset_after_ms: int | None = None
    reset_at: str | None = None
    retry_after_ms: int | None = None
    strategy: str = "exponential_backoff_jitter"
    buckets: dict[str, RateLimitBucketState] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def list_providers() -> list[str]:
    return sorted(_REGISTRY.keys())


def get_provider(provider_id: str) -> dict[str, Any] | None:
    return _REGISTRY.get(provider_id.lower())


def _normalize_headers(headers: Mapping[str, Any]) -> dict[str, str]:
    return {str(k).lower(): str(v).strip() for k, v in headers.items() if v is not None}


def _parse_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(float(value))
    except ValueError:
        return None


def _parse_duration_ms(value: str) -> int | None:
    total_ms = 0.0
    matched = False
    for amount_str, unit in _DURATION_RE.findall(value.lower()):
        matched = True
        amount = float(amount_str)
        if unit == "ms":
            total_ms += amount
        elif unit == "s":
            total_ms += amount * 1000
        elif unit == "m":
            total_ms += amount * 60_000
        elif unit == "h":
            total_ms += amount * 3_600_000
        elif unit == "d":
            total_ms += amount * 86_400_000
    return int(round(total_ms)) if matched else None


def _parse_retry_after_ms(raw: str | None, now_ms: int) -> int | None:
    if not raw:
        return None
    try:
        return max(0, int(round(float(raw) * 1000)))
    except ValueError:
        pass
    try:
        dt = email.utils.parsedate_to_datetime(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        target_ms = int(dt.timestamp() * 1000)
        return max(0, target_ms - now_ms)
    except (TypeError, ValueError):
        return None


def _parse_reset(raw: str | None, reset_format: str, now_ms: int) -> tuple[int | None, str | None]:
    if not raw or reset_format == "none":
        return None, None
    if reset_format == "epoch_milliseconds":
        ms = _parse_int(raw)
        if ms is None:
            return None, None
        iso = datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat().replace("+00:00", "Z")
        return max(0, ms - now_ms), iso
    if reset_format == "epoch_seconds":
        sec = _parse_int(raw)
        if sec is None:
            return None, None
        target_ms = sec * 1000
        iso = datetime.fromtimestamp(sec, tz=timezone.utc).isoformat().replace("+00:00", "Z")
        return max(0, target_ms - now_ms), iso
    if reset_format == "delta_seconds":
        sec = _parse_int(raw)
        if sec is None:
            return None, None
        ms = max(0, sec * 1000)
        iso = datetime.fromtimestamp((now_ms + ms) / 1000, tz=timezone.utc).isoformat().replace("+00:00", "Z")
        return ms, iso
    if reset_format == "rfc3339":
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            target_ms = int(dt.timestamp() * 1000)
            return max(0, target_ms - now_ms), dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        except ValueError:
            return None, None
    if reset_format == "duration_string":
        ms = _parse_duration_ms(raw)
        if ms is None:
            return None, None
        iso = datetime.fromtimestamp((now_ms + ms) / 1000, tz=timezone.utc).isoformat().replace("+00:00", "Z")
        return ms, iso
    return None, None


def detect_provider(headers: Mapping[str, Any]) -> str | None:
    norm = _normalize_headers(headers)
    for pid, spec in _REGISTRY.items():
        for hint in spec.get("detect_headers", []):
            if hint.lower() in norm:
                return pid
    return None


def parse_http_headers_text(raw_text: str) -> tuple[int, dict[str, str]]:
    """Parse raw HTTP response headers (e.g. from `curl -si`) into (status, headers)."""
    status = 200
    headers: dict[str, str] = {}
    for line in raw_text.splitlines():
        stripped = line.strip()
        if not stripped:
            if headers:
                break
            continue
        m = _HTTP_STATUS_RE.match(stripped)
        if m:
            status = int(m.group(1))
            continue
        if ":" in stripped:
            k, v = stripped.split(":", 1)
            headers[k.strip().lower()] = v.strip()
    return status, headers


def compute_backoff_ms(
    attempt: int,
    base_ms: int = 1000,
    max_ms: int = 60_000,
    jitter: str = "full",
    rng: Callable[[], float] = random.random,
) -> int:
    """Compute exponential backoff delay in milliseconds with optional full/equal jitter."""
    cap = min(max_ms, base_ms * (2 ** max(0, attempt)))
    if jitter == "none":
        return int(cap)
    if jitter == "equal":
        return int(round((cap / 2.0) + (rng() * (cap / 2.0))))
    return int(round(rng() * cap))


def parse_rate_limit(
    provider: str | None,
    headers: Mapping[str, Any],
    status: int = 200,
    now_ms: int | None = None,
) -> RateLimitResult:
    norm = _normalize_headers(headers)
    now = int(datetime.now(tz=timezone.utc).timestamp() * 1000) if now_ms is None else now_ms
    pid = provider.lower() if provider else detect_provider(norm)
    spec = _REGISTRY.get(pid) if pid else None

    if spec is None:
        retry_ms = _parse_retry_after_ms(norm.get("retry-after"), now)
        is_limited = status == 429
        return RateLimitResult(
            provider=pid,
            is_limited=is_limited,
            retry_after_ms=retry_ms if (is_limited and retry_ms is not None) else (5000 if is_limited else None),
        )

    parsed_buckets: dict[str, RateLimitBucketState] = {}
    primary_limit: int | None = None
    primary_remaining: int | None = None
    primary_reset_ms: int | None = None
    primary_reset_at: str | None = None

    for b in spec.get("buckets", []):
        fmt = b["format"]
        state = RateLimitBucketState(name=b["name"], unit=b["unit"])

        if fmt == "triplet":
            state.limit = _parse_int(norm.get(b.get("limit_header", "").lower()))
            state.remaining = _parse_int(norm.get(b.get("remaining_header", "").lower()))
            if state.limit is not None and state.remaining is not None:
                state.used = max(0, state.limit - state.remaining)
            reset_raw = norm.get(b.get("reset_header", "").lower())
            state.reset_after_ms, state.reset_at = _parse_reset(reset_raw, b.get("reset_format", "none"), now)

        elif fmt == "ratio":
            raw_ratio = norm.get(b.get("ratio_header", "").lower(), "")
            if "/" in raw_ratio:
                used_s, limit_s = raw_ratio.split("/", 1)
                used = _parse_int(used_s)
                limit = _parse_int(limit_s)
                if used is not None and limit is not None:
                    state.used = used
                    state.limit = limit
                    state.remaining = max(0, limit - used)

        elif fmt == "ietf_structured":
            rl_raw = norm.get(b.get("structured_header", "").lower(), "")
            pol_raw = norm.get(b.get("policy_header", "").lower(), "")
            rl_params = dict(_IETF_PARAM_RE.findall(rl_raw))
            pol_params = dict(_IETF_PARAM_RE.findall(pol_raw))
            state.remaining = _parse_int(rl_params.get("r"))
            state.limit = _parse_int(pol_params.get("q"))
            if state.limit is not None and state.remaining is not None:
                state.used = max(0, state.limit - state.remaining)
            if "t" in rl_params:
                state.reset_after_ms, state.reset_at = _parse_reset(rl_params["t"], "delta_seconds", now)

        if any(v is not None for v in (state.limit, state.remaining, state.reset_after_ms)):
            parsed_buckets[b["name"]] = state
            if primary_limit is None and state.limit is not None:
                primary_limit = state.limit
            if primary_remaining is None and state.remaining is not None:
                primary_remaining = state.remaining
            if primary_reset_ms is None and state.reset_after_ms is not None:
                primary_reset_ms = state.reset_after_ms
                primary_reset_at = state.reset_at

    retry_cfg = spec["retry"]
    retry_header = retry_cfg.get("retry_after_header", "retry-after").lower()
    retry_after_ms = _parse_retry_after_ms(norm.get(retry_header), now)

    is_limited = status in retry_cfg["status_codes"]
    if pid == "github" and status == 403:
        is_limited = (primary_remaining == 0) or (retry_after_ms is not None)

    if is_limited and retry_after_ms is None:
        if retry_cfg["strategy"] == "wait_until_reset" and primary_reset_ms is not None:
            retry_after_ms = primary_reset_ms
        else:
            retry_after_ms = retry_cfg.get("default_backoff_ms", 1000)

    return RateLimitResult(
        provider=pid,
        is_limited=is_limited,
        limit=primary_limit,
        remaining=primary_remaining,
        reset_after_ms=primary_reset_ms,
        reset_at=primary_reset_at,
        retry_after_ms=retry_after_ms if is_limited else None,
        strategy=retry_cfg["strategy"],
        buckets=parsed_buckets,
    )


class RateLimitTracker:
    """In-memory proactive rate-limit tracker across providers and keys."""

    def __init__(self, clock_ms: Callable[[], int] | None = None):
        self._clock_ms = clock_ms or (lambda: int(datetime.now(tz=timezone.utc).timestamp() * 1000))
        self._state: dict[str, tuple[int, RateLimitResult]] = {}

    def update(
        self,
        provider: str | None,
        headers: Mapping[str, Any],
        status: int = 200,
        key: str | None = None,
    ) -> RateLimitResult:
        now = self._clock_ms()
        result = parse_rate_limit(provider, headers, status=status, now_ms=now)
        slot = key or result.provider or "default"
        self._state[slot] = (now, result)
        return result

    def get_delay_ms(self, key: str, min_remaining: int = 1) -> int:
        entry = self._state.get(key)
        if not entry:
            return 0
        recorded_ms, result = entry
        elapsed = max(0, self._clock_ms() - recorded_ms)
        if result.is_limited and result.retry_after_ms is not None:
            return max(0, result.retry_after_ms - elapsed)
        if result.remaining is not None and result.remaining < min_remaining:
            if result.reset_after_ms is not None:
                return max(0, result.reset_after_ms - elapsed)
        return 0

    def clear(self, key: str | None = None) -> None:
        if key is None:
            self._state.clear()
        else:
            self._state.pop(key, None)

    def snapshot(self) -> dict[str, dict[str, Any]]:
        return {k: v[1].to_dict() for k, v in self._state.items()}


def request_with_rate_limit(
    request_fn: Callable[[], Any],
    provider: str | None = None,
    max_retries: int = 3,
    max_wait_ms: int = 60_000,
    sleep_fn: Callable[[float], None] = time.sleep,
    rng: Callable[[], float] = random.random,
) -> tuple[Any, RateLimitResult]:
    """Execute request_fn() and automatically retry on rate-limited responses."""
    last_response = None
    last_result = RateLimitResult(provider=provider, is_limited=False)
    for attempt in range(max_retries + 1):
        response = request_fn()
        status = getattr(response, "status_code", getattr(response, "status", 200))
        headers = getattr(response, "headers", {})
        result = parse_rate_limit(provider, headers, status=status)
        last_response, last_result = response, result
        if not result.is_limited or attempt == max_retries:
            return response, result
        if result.strategy == "exponential_backoff_jitter" and result.retry_after_ms is not None:
            wait_ms = compute_backoff_ms(attempt, base_ms=result.retry_after_ms, max_ms=max_wait_ms, rng=rng)
        else:
            wait_ms = min(result.retry_after_ms or 1000, max_wait_ms)
        sleep_fn(wait_ms / 1000.0)
    return last_response, last_result
