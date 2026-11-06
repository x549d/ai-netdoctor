"""Console entry point."""

import argparse
import json
import math

from . import __version__
from .core import TARGETS, diagnose, parse_proxy


def positive_timeout(value):
    try:
        number = float(value)
        if not math.isfinite(number) or number <= 0:
            raise ValueError
        return number
    except ValueError:
        raise argparse.ArgumentTypeError("timeout must be a finite positive number") from None


def main(argv=None):
    parser = argparse.ArgumentParser(description="Diagnose AI API DNS, TCP, HTTPS and HTTP proxy connectivity.")
    parser.add_argument("--version", action="version", version=f"AI NetDoctor {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("check", help="Check one provider or all three")
    check.add_argument("provider", nargs="?", choices=tuple(TARGETS))
    check.add_argument("--all", action="store_true", help="Check all providers sequentially")
    check.add_argument("--proxy", help="Explicit HTTP(S) proxy, e.g. http://127.0.0.1:7897")
    check.add_argument("--timeout", type=positive_timeout, default=5.0, help="Per-stage/HTTP operation timeout in seconds (default: 5)")
    check.add_argument("--json", action="store_true", dest="as_json", help="Print one JSON object with a results array")
    args = parser.parse_args(argv)
    if args.all and args.provider:
        parser.error("choose a provider or --all, not both")
    if not args.all and not args.provider:
        parser.error("check requires a provider or --all")
    try:
        parse_proxy(args.proxy)
    except ValueError as exc:
        parser.error(str(exc))
    providers = tuple(TARGETS) if args.all else (args.provider,)
    try:
        reports = [diagnose(provider, args.proxy, args.timeout) for provider in providers]
    except KeyboardInterrupt:
        return 130
    if args.as_json:
        print(json.dumps({"version": __version__, "results": reports}, ensure_ascii=True, indent=2))
    else:
        print(f"AI NetDoctor v{__version__}")
        for report in reports:
            print(f"\nTarget: {report['target']}\nProxy: {report['proxy'] or 'direct (environment proxies disabled)'}")
            print(f"DNS/TCP scope: {report['probe_scope']} ({report['probe_host']}:{report['probe_port']})")
            for step in report["steps"]:
                label = "PASS" if step["ok"] else "FAIL"
                print(f"[{label}] {step['stage'].upper()}: {step['message']} ({step['elapsed_ms']} ms)")
                if step["stage"] == "https" and "retry_after" in report:
                    print(f"  Retry-After: {report['retry_after']}")
                if step.get("explanation"):
                    print(f"  Explanation: {step['explanation']}")
                for cause in step.get("possible_causes", []):
                    print(f"  Possible cause: {cause}")
                for index, action in enumerate(step.get("recommended_actions", []), start=1):
                    print(f"  Suggested action {index}: {action}")
            print("Result: " + report["result"])
    return 0 if all(report["reachable"] for report in reports) else 1
