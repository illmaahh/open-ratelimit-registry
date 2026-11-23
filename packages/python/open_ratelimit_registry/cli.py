import argparse
import json
import sys

from . import __version__
from .parser import get_provider, list_providers, parse_http_headers_text, parse_rate_limit


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="open-ratelimit",
        description="Inspect HTTP API rate-limit headers from curl output or files.",
    )
    parser.add_argument("--version", action="version", version=f"open-ratelimit {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="List all supported API provider IDs")

    p_show = sub.add_parser("show", help="Show the full JSON spec for a provider")
    p_show.add_argument("provider", help="Provider ID (e.g. anthropic, github, linear)")

    p_inspect = sub.add_parser("inspect", help="Parse raw HTTP response headers from stdin or a file")
    p_inspect.add_argument("--provider", default=None, help="Explicit provider ID (auto-detected if omitted)")
    p_inspect.add_argument("--status", type=int, default=None, help="Override HTTP status code")
    p_inspect.add_argument("--file", default=None, help="Read raw HTTP headers from file instead of stdin")
    p_inspect.add_argument("--json", action="store_true", dest="as_json", help="Output JSON")

    args = parser.parse_args(argv)

    if args.command == "list":
        for pid in list_providers():
            print(pid)
        return 0

    if args.command == "show":
        spec = get_provider(args.provider)
        if spec is None:
            print(f"Unknown provider: {args.provider}", file=sys.stderr)
            return 1
        print(json.dumps(spec, indent=2))
        return 0

    if args.command == "inspect":
        raw = open(args.file, encoding="utf-8").read() if args.file else sys.stdin.read()
        detected_status, headers = parse_http_headers_text(raw)
        status = args.status if args.status is not None else detected_status
        result = parse_rate_limit(args.provider, headers, status=status)
        if args.as_json:
            print(json.dumps(result.to_dict(), indent=2))
        else:
            print(f"Provider   : {result.provider or 'unknown'}")
            print(f"Limited    : {'YES' if result.is_limited else 'no'} (HTTP {status})")
            print(f"Quota      : {result.remaining} / {result.limit}")
            if result.reset_at:
                print(f"Reset At   : {result.reset_at} ({result.reset_after_ms} ms)")
            if result.retry_after_ms is not None:
                print(f"Retry After: {result.retry_after_ms} ms ({result.strategy})")
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
