# Contributing to Open RateLimit Registry

Adding a new API provider takes about 5 minutes and requires **only 1 YAML file**.

## Step-by-Step

1. Copy any existing file in `providers/` (for example, `providers/github.yaml`) to `providers/<your-provider>.yaml`.
2. Fill in all fields using **official vendor documentation**:
   - `id`: lowercase slug matching the filename (`^[a-z0-9-]+$`)
   - `source_url`: direct `https://` link to the provider's official rate-limit docs
   - `last_verified`: today's date (`YYYY-MM-DD`)
   - `detect_headers`: only vendor-specific headers unique to this API (leave `[]` if headers are generic)
   - `buckets` & `retry`: exact header names, `reset_format`, and `status_codes`
   - `examples`: at least 1 realistic example header map + `expected` output
3. Validate schema, rebuild bundles + README table, and run all tests:
   ```bash
   pip install pyyaml jsonschema
   python3 scripts/build_registry.py
   python3 -m unittest discover -s packages/python/tests -v
   node --test packages/js/test/parser.test.mjs
   python3 scripts/verify_parity.py
   ```
4. Open a Pull Request!
