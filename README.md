# Open RateLimit Registry

A community-maintained, machine-readable YAML registry of HTTP API rate-limit headers, reset formats, and `429` retry rules — bundled with zero-dependency **JavaScript** and **Python** parsers.

Stop hardcoding `x-ratelimit-*`, `anthropic-ratelimit-*`, `X-Shopify-Shop-Api-Call-Limit`, and IETF `RateLimit` header quirks in every project.

## Quick Start

### Python (zero dependencies)
```python
from open_ratelimit_registry import parse_rate_limit

result = parse_rate_limit("anthropic", response.headers, status=response.status_code)
if result.is_limited:
    print(f"Retry after {result.retry_after_ms} ms ({result.strategy})")
```

### JavaScript / Node.js (zero dependencies)
```js
import { parseRateLimit } from "open-ratelimit-registry";

const result = parseRateLimit("shopify", res.headers, res.status);
console.log(result.remaining, result.limit, result.retryAfterMs);
```

## Supported Formats
- **Triplet headers:** `limit` / `remaining` / `reset` (RFC 3339, Unix epoch seconds, delta seconds, or duration strings like `1m30s`)
- **Multi-bucket APIs:** Separate `requests`, `tokens`, `input_tokens`, `output_tokens` buckets (e.g. Anthropic, OpenAI, HubSpot)
- **Ratio headers:** `used/limit` format (e.g. Shopify `X-Shopify-Shop-Api-Call-Limit: 10/40`)
- **IETF Structured Fields:** `RateLimit` and `RateLimit-Policy`

## Contributing (5-Minute PR)
Want to add your favorite API? Read [CONTRIBUTING.md](CONTRIBUTING.md) and open a PR with a single `providers/<name>.yaml` file!
