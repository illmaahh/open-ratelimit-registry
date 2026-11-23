import json
import pathlib
import sys
import unittest
from types import SimpleNamespace

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "packages" / "python"))

from open_ratelimit_registry import (
    RateLimitTracker,
    compute_backoff_ms,
    detect_provider,
    list_providers,
    parse_http_headers_text,
    parse_rate_limit,
    request_with_rate_limit,
)


class TestV2Registry(unittest.TestCase):
    def test_all_25_provider_examples(self):
        reg_path = ROOT / "packages" / "python" / "open_ratelimit_registry" / "registry.json"
        providers = json.loads(reg_path.read_text(encoding="utf-8"))["providers"]
        self.assertEqual(len(providers), 25)
        for pid, spec in providers.items():
            for idx, ex in enumerate(spec["examples"]):
                with self.subTest(provider=pid, example=idx):
                    res = parse_rate_limit(pid, ex["headers"], status=ex["status"], now_ms=1795443500000)
                    exp = ex["expected"]
                    self.assertEqual(res.is_limited, exp["is_limited"])
                    self.assertEqual(res.limit, exp.get("limit"))
                    self.assertEqual(res.remaining, exp.get("remaining"))
                    self.assertEqual(res.retry_after_ms, exp.get("retry_after_ms"))

    def test_retry_after_http_date(self):
        # 2026-11-23T14:00:10Z = 1795442410000
        now_ms = 1795442400000
        res = parse_rate_limit(
            "slack",
            {"Retry-After": "Mon, 23 Nov 2026 14:00:10 GMT"},
            status=429,
            now_ms=now_ms,
        )
        self.assertTrue(res.is_limited)
        self.assertEqual(res.retry_after_ms, 10000)

    def test_proactive_tracker_and_backoff(self):
        now = [1795443500000]
        tracker = RateLimitTracker(clock_ms=lambda: now[0])
        tracker.update("github", {"x-ratelimit-limit": "5000", "x-ratelimit-remaining": "0", "x-ratelimit-reset": "1795443520"}, status=200)
        self.assertEqual(tracker.get_delay_ms("github", min_remaining=1), 20000)
        now[0] += 5000
        self.assertEqual(tracker.get_delay_ms("github", min_remaining=1), 15000)
        self.assertEqual(compute_backoff_ms(2, base_ms=1000, max_ms=10000, jitter="none"), 4000)

    def test_raw_curl_headers_parse(self):
        raw = "HTTP/2 429\r\nretry-after: 12\r\nanthropic-ratelimit-requests-remaining: 0\r\n\r\n{}"
        status, headers = parse_http_headers_text(raw)
        self.assertEqual(status, 429)
        self.assertEqual(detect_provider(headers), "anthropic")
        res = parse_rate_limit(None, headers, status=status)
        self.assertTrue(res.is_limited)
        self.assertEqual(res.retry_after_ms, 12000)

    def test_request_with_rate_limit(self):
        responses = iter([
            SimpleNamespace(status_code=429, headers={"retry-after": "2"}),
            SimpleNamespace(status_code=200, headers={"ratelimit-limit": "10", "ratelimit-remaining": "9"}),
        ])
        sleeps = []
        resp, rl = request_with_rate_limit(lambda: next(responses), provider="resend", sleep_fn=sleeps.append)
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(rl.is_limited)
        self.assertEqual(sleeps, [2.0])


if __name__ == "__main__":
    unittest.main()
