from __future__ import annotations

import json
import pathlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping

_REGISTRY_PATH = pathlib.Path(__file__).resolve().parent / "registry.json"
_REGISTRY = json.loads(_REGISTRY_PATH.read_text(encoding="utf-8"))["providers"]

_DURATION_RE = re.compile(r"(\d+(?:\.\d+)?)(ms|s|m|h|d)")
_IETF_PARAM_RE = re.compile(r"\b([a-z]+)=(\d+)")


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


def _parse_reset(raw: str | None, reset_format: str, now_ms: int) -> tuple[int | None, str | None]:
    if not raw or reset_format == "none":
        return None, None
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
        retry_sec = _parse_int(norm.get("retry-after"))
        is_limited = status == 429
        return RateLimitResult(
            provider=pid,
            is_limited=is_limited,
            retry_after_ms=retry_sec * 1000 if (is_limited and retry_sec is not None) else (5000 if is_limited else None),
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
    retry_after_raw = norm.get(retry_header)
    retry_after_ms: int | None = None
    if retry_after_raw is not None:
        try:
            retry_after_ms = max(0, int(round(float(retry_after_raw) * 1000)))
        except ValueError:
            retry_after_ms = None

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
