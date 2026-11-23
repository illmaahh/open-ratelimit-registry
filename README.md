# Open RateLimit Registry

[![Validate & Test Registry](https://github.com/Burakceliks/open-ratelimit-registry/actions/workflows/ci.yml/badge.svg)](https://github.com/Burakceliks/open-ratelimit-registry/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-0F766E.svg)](LICENSE)
[![Zero Dependencies](https://img.shields.io/badge/dependencies-0-1D4ED8.svg)](#quick-start)

A production-ready, community-maintained YAML registry of HTTP API rate-limit headers, reset formats, and `429` retry rules — paired with zero-dependency **JavaScript/TypeScript** and **Python** libraries, a **proactive rate-limit tracker**, and a **`curl`-pipeable CLI**.

Stop hardcoding `anthropic-ratelimit-*` (RFC 3339), GitHub's `403` vs `429` quirks, Linear's epoch milliseconds, OpenAI's `6m0s` duration strings, Shopify's `10/40` ratio header, RFC 9110 HTTP-date `Retry-After`, and IETF `RateLimit` structured fields in every project.

## Highlights (v2.0.0)
- **25 verified API providers** with official documentation links and automated schema + example tests
- **Cross-language parity:** Python and JS/TypeScript parsers are CI-tested to return identical results on every provider
- **Proactive throttling (`RateLimitTracker`):** Slow down workers *before* hitting `429` bans
- **RFC 9110 `Retry-After` HTTP-date & full-jitter exponential backoff** built in
- **Instant CLI:** Pipe `curl -si` output straight into `open-ratelimit inspect`

## Quick Start

### CLI (`curl` pipe)
```bash
# Python CLI
curl -si https://api.github.com/zen | python3 -m open_ratelimit_registry inspect

# Node.js CLI
curl -si https://api.github.com/zen | node packages/js/bin/cli.mjs inspect --json
```

### Python (zero runtime dependencies)
```python
import requests
from open_ratelimit_registry import RateLimitTracker, parse_rate_limit, request_with_rate_limit

# 1) Proactive tracking across requests
tracker = RateLimitTracker()
res = requests.get("https://api.github.com/user", headers={"Authorization": "Bearer ..."})
tracker.update("github", res.headers, status=res.status_code)
delay_ms = tracker.get_delay_ms("github", min_remaining=5)

# 2) Automatic retry on 429 / 529 with provider-specific backoff
res, rl = request_with_rate_limit(
    lambda: requests.post("https://api.anthropic.com/v1/messages", ...),
    provider="anthropic",
    max_retries=3,
)
```

### JavaScript / TypeScript (zero runtime dependencies)
```ts
import { RateLimitTracker, fetchWithRateLimit, parseRateLimit } from "open-ratelimit-registry";

const tracker = new RateLimitTracker();
const { response, rateLimit } = await fetchWithRateLimit(
  "https://api.resend.com/emails",
  { method: "POST", headers: { Authorization: "Bearer ..." } },
  { provider: "resend", maxRetries: 3 }
);
tracker.update("resend", response.headers, response.status);
```

## Supported Providers

<!-- PROVIDERS:START -->
Currently tracking **25 API providers**:

| Provider | ID | Format | Reset Format | Retry Strategy | Docs |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Airtable Web API | `airtable` | `retry-after only` | `retry-after` | `exponential_backoff_jitter` | [Docs](https://airtable.com/developers/web/api/rate-limits) |
| Anthropic Claude API | `anthropic` | `triplet` | `rfc3339` | `honor_retry_after` | [Docs](https://platform.claude.com/docs/en/api/rate-limits) |
| Cloudflare API & Edge | `cloudflare` | `retry-after only` | `retry-after` | `honor_retry_after` | [Docs](https://developers.cloudflare.com/fundamentals/api/reference/limits/) |
| Discord REST API | `discord` | `triplet` | `delta_seconds` | `honor_retry_after` | [Docs](https://docs.discord.com/developers/topics/rate-limits) |
| Figma REST API | `figma` | `retry-after only` | `retry-after` | `honor_retry_after` | [Docs](https://developers.figma.com/docs/rest-api/rate-limits/) |
| Google Gemini API | `gemini` | `retry-after only` | `retry-after` | `exponential_backoff_jitter` | [Docs](https://ai.google.dev/gemini-api/docs/rate-limits) |
| GitHub REST & GraphQL API | `github` | `triplet` | `epoch_seconds` | `honor_retry_after` | [Docs](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api) |
| GitLab REST API | `gitlab` | `triplet` | `epoch_seconds` | `honor_retry_after` | [Docs](https://docs.gitlab.com/user/gitlab_com/rate_limits/) |
| HubSpot API | `hubspot` | `triplet` | `retry-after` | `exponential_backoff_jitter` | [Docs](https://developers.hubspot.com/docs/api/usage-details) |
| IETF RateLimit Structured Fields (Draft) | `ietf-ratelimit` | `ietf_structured` | `delta_seconds` | `wait_until_reset` | [Docs](https://datatracker.ietf.org/doc/draft-ietf-httpapi-ratelimit-headers/) |
| Linear GraphQL API | `linear` | `triplet` | `epoch_milliseconds` | `wait_until_reset` | [Docs](https://linear.app/developers/rate-limiting) |
| Notion API | `notion` | `retry-after only` | `retry-after` | `honor_retry_after` | [Docs](https://developers.notion.com/reference/request-limits) |
| OpenAI API | `openai` | `triplet` | `duration_string` | `wait_until_reset` | [Docs](https://platform.openai.com/docs/guides/rate-limits) |
| Reddit Data API | `reddit` | `triplet` | `delta_seconds` | `wait_until_reset` | [Docs](https://support.reddithelp.com/hc/en-us/articles/16160319875092-Reddit-Data-API-Wiki) |
| Resend Email API | `resend` | `triplet` | `delta_seconds` | `honor_retry_after` | [Docs](https://resend.com/docs/api-reference/rate-limit) |
| Sentry Ingest & REST API | `sentry` | `retry-after only` | `retry-after` | `honor_retry_after` | [Docs](https://docs.sentry.io/concepts/otlp/forwarding/pipelines/sentry-exporter/) |
| Shopify REST Admin API | `shopify` | `ratio` | `retry-after` | `honor_retry_after` | [Docs](https://shopify.dev/docs/api/admin-rest/usage/rate-limits) |
| Slack Web API | `slack` | `retry-after only` | `retry-after` | `honor_retry_after` | [Docs](https://docs.slack.dev/apis/web-api/rate-limits) |
| Spotify Web API | `spotify` | `retry-after only` | `retry-after` | `honor_retry_after` | [Docs](https://developer.spotify.com/documentation/web-api/concepts/rate-limits) |
| Stripe API | `stripe` | `retry-after only` | `retry-after` | `exponential_backoff_jitter` | [Docs](https://docs.stripe.com/rate-limits) |
| Supabase Management API | `supabase` | `retry-after only` | `retry-after` | `honor_retry_after` | [Docs](https://supabase.com/docs/reference/api/introduction) |
| Twilio REST API | `twilio` | `retry-after only` | `retry-after` | `honor_retry_after` | [Docs](https://www.twilio.com/docs/usage/api-limits) |
| Vercel REST API | `vercel` | `triplet` | `epoch_seconds` | `honor_retry_after` | [Docs](https://vercel.com/docs/rest-api) |
| X (Twitter) API v2 | `x-api` | `triplet` | `epoch_seconds` | `wait_until_reset` | [Docs](https://opentweet.io/answers/x-api-rate-limit-429) |
| Zendesk Support API | `zendesk` | `triplet` | `retry-after` | `honor_retry_after` | [Docs](https://developer.zendesk.com/api-reference/introduction/rate-limits/) |
<!-- PROVIDERS:END -->

## Contributing (5-Minute PR)
Missing an API you integrate with? Read [CONTRIBUTING.md](CONTRIBUTING.md) and open a PR with a single `providers/<name>.yaml` file — GitHub Actions validates your schema, checks Python/JS parity, updates the provider table, and runs the full test suite automatically.
