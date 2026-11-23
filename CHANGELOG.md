# Changelog

All notable changes to this project will be documented in this file.

## [2.0.0] - 2026-11-23
### Added
- Expanded registry to **25 verified API providers** (added Vercel, Figma, Zendesk, Sentry, Supabase, Airtable, Google Gemini, Discord, Linear, Resend, GitLab, Cloudflare, Notion, Twilio, Spotify, Reddit, and X API v2).
- Added `RateLimitTracker` proactive throttling class to both Python and JavaScript/TypeScript packages.
- Added RFC 9110 HTTP-date `Retry-After` parsing and `computeBackoffMs` / `compute_backoff_ms` jittered exponential backoff engine.
- Added `open-ratelimit` CLI (`list`, `show`, `inspect` with `curl -si` stdin piping and `--json`).
- Added TypeScript `.d.ts` definitions and `epoch_milliseconds` reset format support.
- Added cross-language Python/JS parity verification script (`scripts/verify_parity.py`) and automated README table generation.
- Added `.gitattributes`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, and automated tag-based release workflow.

## [0.1.0] - 2026-11-23
### Added
- Initial YAML provider schema, 8 core API providers, and zero-dependency Python & JS parsers.
