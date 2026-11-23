# Contributing to Open RateLimit Registry

Adding a new API provider takes about 5–10 minutes and requires **only 1 YAML file** plus rebuilding the bundled JSON.

## Step-by-Step

1. Copy any existing file in `providers/` (for example, `providers/github.yaml`) to `providers/<your-provider>.yaml`.
2. Fill in the fields using **only official API documentation**:
   - `id`: lowercase slug matching the filename (`^[a-z0-9-]+$`)
   - `source_url`: direct `https://` link to the provider's official rate-limit docs
   - `last_verified`: today's date (`YYYY-MM-DD`)
   - `buckets` & `retry`: exact header names, `reset_format`, and `status_codes`
   - `examples`: at least 1 real-world example header map + `expected` output
3. Validate, rebuild, and test:
   ```bash
   pip install pyyaml
   python3 scripts/build_registry.py
   python3 -m unittest discover -s packages/python/tests -v
   node --test packages/js/test/parser.test.mjs
   ```
4. Open a Pull Request!
