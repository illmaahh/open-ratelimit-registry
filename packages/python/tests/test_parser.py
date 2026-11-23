import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "packages" / "python"))

from open_ratelimit_registry import detect_provider, list_providers, parse_rate_limit


class TestRegistryExamples(unittest.TestCase):
    def test_all_provider_examples(self):
        reg_path = ROOT / "packages" / "python" / "open_ratelimit_registry" / "registry.json"
        providers = json.loads(reg_path.read_text(encoding="utf-8"))["providers"]
        self.assertGreaterEqual(len(providers), 8)

        for pid, spec in providers.items():
            for idx, ex in enumerate(spec["examples"]):
                with self.subTest(provider=pid, example=idx):
                    res = parse_rate_limit(pid, ex["headers"], status=ex["status"], now_ms=1795443500000)
                    exp = ex["expected"]
                    self.assertEqual(res.is_limited, exp["is_limited"])
                    self.assertEqual(res.limit, exp.get("limit"))
                    self.assertEqual(res.remaining, exp.get("remaining"))
                    self.assertEqual(res.retry_after_ms, exp.get("retry_after_ms"))

    def test_detect_provider(self):
        self.assertEqual(detect_provider({"Anthropic-RateLimit-Requests-Remaining": "10"}), "anthropic")
        self.assertEqual(detect_provider({"X-Shopify-Shop-Api-Call-Limit": "1/40"}), "shopify")
        self.assertIn("github", list_providers())


if __name__ == "__main__":
    unittest.main()
