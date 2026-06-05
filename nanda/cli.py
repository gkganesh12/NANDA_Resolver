"""`nanda` CLI — thin wrapper over the HTTP API.

Subcommands:
  serve      Launch the FastAPI app via uvicorn.
  resolve    Resolve a handle to verified endpoint + capabilities.
  discover   Find agents declaring a given capability tag.
  list       List all handles registered in the index.
  seed       Re-run the seed script.
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any

import httpx

from nanda.config import base_url


def _get(path: str) -> Any:
    url = f"{base_url()}{path}"
    try:
        r = httpx.get(url, timeout=10.0)
    except httpx.ConnectError:
        print(
            f"ERROR: Could not connect to {base_url()}. Is the server running?\n"
            f"       Start it with:  nanda serve",
            file=sys.stderr,
        )
        sys.exit(2)
    if r.status_code >= 400:
        try:
            detail = r.json().get("detail", r.text)
        except Exception:
            detail = r.text
        print(f"ERROR {r.status_code}: {detail}", file=sys.stderr)
        sys.exit(1)
    return r.json()


def _cmd_serve(args: argparse.Namespace) -> None:
    import uvicorn

    uvicorn.run("nanda.app:app", host=args.host, port=args.port, reload=args.reload)


def _cmd_resolve(args: argparse.Namespace) -> None:
    result = _get(f"/resolve/{args.handle}")
    if args.json:
        print(json.dumps(result, indent=2))
        return
    print(f"\033[32m✓ VERIFIED\033[0m  {result['handle']}")
    print(f"  Operator:   {result['operator']}")
    print(f"  Endpoints:")
    for e in result["endpoints"]:
        print(f"    - {e['endpointUrl']}  ({e['endpointProtocol']})")
    print(f"  Capabilities:")
    for c in result["capabilities"]:
        print(f"    - {c['capabilityTag']:<28} {c['capabilityDescription']}")
    print(f"  TTL: {result['ttl']}s   Issued: {result['issuedAt']}")


def _cmd_discover(args: argparse.Namespace) -> None:
    result = _get(f"/discover?cap={args.cap}")
    if args.json:
        print(json.dumps(result, indent=2))
        return
    matches = result["matches"]
    print(f"Capability '{args.cap}' — {len(matches)} match(es):")
    for m in matches:
        ep = m["endpoints"][0]["endpointUrl"] if m["endpoints"] else "(none)"
        print(f"  {m['handle']:<45}  {m['operator']:<25}  {ep}")
    if result["rejected"]:
        print(f"\n\033[31m{len(result['rejected'])} handle(s) rejected during scan:\033[0m")
        for r in result["rejected"]:
            print(f"  {r['handle']}: {r['reason']}")


def _cmd_list(args: argparse.Namespace) -> None:
    result = _get("/index/list")
    if args.json:
        print(json.dumps(result, indent=2))
        return
    print(f"{result['count']} registered handle(s):")
    for h in result["handles"]:
        print(f"  {h}")


def _cmd_seed(args: argparse.Namespace) -> None:
    from scripts import seed

    seed.main()


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="nanda", description="NANDA Agent business-card resolver (POC)")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("serve", help="Start the FastAPI app (index + facts + resolver)")
    sp.add_argument("--host", default="127.0.0.1")
    sp.add_argument("--port", type=int, default=8000)
    sp.add_argument("--reload", action="store_true")
    sp.set_defaults(func=_cmd_serve)

    sp = sub.add_parser("resolve", help="Resolve a handle to a verified endpoint + capabilities")
    sp.add_argument("handle")
    sp.add_argument("--json", action="store_true", help="Print raw JSON")
    sp.set_defaults(func=_cmd_resolve)

    sp = sub.add_parser("discover", help="Find all agents declaring a capability tag")
    sp.add_argument("--cap", required=True, help="Capability tag, e.g. summarize-pdf")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=_cmd_discover)

    sp = sub.add_parser("list", help="List all registered handles")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=_cmd_list)

    sp = sub.add_parser("seed", help="Generate sample keys + signed agents + index")
    sp.set_defaults(func=_cmd_seed)

    return p


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
