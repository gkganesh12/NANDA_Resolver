"""Tamper-attack demo.

1. Resolve a chosen handle — show ✓ VERIFIED.
2. Modify the AgentFacts file on disk (swap the endpoint to an attacker URL).
3. Resolve the same handle again — show ✗ verification failure.
4. Restore the original facts so the index is clean again.

Run after `nanda serve` is up.
"""
from __future__ import annotations

import json
import shutil
import sys
import time
from pathlib import Path

import httpx

from nanda.config import base_url, facts_dir

GREEN = "\033[32m"
RED = "\033[31m"
DIM = "\033[2m"
BOLD = "\033[1m"
RESET = "\033[0m"

DEFAULT_HANDLE = "@acme:support/billing-bot"
DEFAULT_AGENT_ID = "acme-billing-bot"


def banner(text: str) -> None:
    bar = "─" * (len(text) + 2)
    print(f"\n{BOLD}┌{bar}┐\n│ {text} │\n└{bar}┘{RESET}")


def call_resolve(handle: str) -> tuple[int, dict]:
    r = httpx.get(f"{base_url()}/resolve/{handle}", timeout=10.0)
    return r.status_code, r.json()


def print_result(status: int, body: dict) -> None:
    if status == 200 and body.get("verified"):
        ep = body["endpoints"][0]["endpointUrl"]
        print(f"  {GREEN}✓ VERIFIED{RESET}  endpoint = {ep}")
    else:
        detail = body.get("detail", body)
        print(f"  {RED}✗ REJECTED{RESET}  status={status}  detail={detail}")


def main() -> None:
    handle = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_HANDLE
    agent_id = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_AGENT_ID

    facts_path: Path = facts_dir() / f"{agent_id}.jsonld"
    backup_path: Path = facts_path.with_suffix(".jsonld.bak")

    if not facts_path.exists():
        print(f"{RED}AgentFacts not found: {facts_path}{RESET}")
        print("Did you run `python -m scripts.seed` and `nanda serve`?")
        sys.exit(2)

    try:
        httpx.get(f"{base_url()}/healthz", timeout=2.0)
    except httpx.ConnectError:
        print(f"{RED}Cannot reach {base_url()} — start the server first:{RESET}  nanda serve")
        sys.exit(2)

    # 1. Clean resolve
    banner(f"STEP 1  resolve {handle}  (untampered)")
    print_result(*call_resolve(handle))
    time.sleep(0.6)

    # 2. Tamper
    banner("STEP 2  attacker rewrites the endpoint in the signed facts file")
    shutil.copy(facts_path, backup_path)
    doc = json.loads(facts_path.read_text())
    original = doc["endpoints"][0]["endpointUrl"]
    doc["endpoints"][0]["endpointUrl"] = "https://attacker.example/steal-billing-data"
    facts_path.write_text(json.dumps(doc, indent=2) + "\n")
    print(f"  {DIM}endpoint:{RESET} {original}")
    print(f"  {DIM}    -->  {RESET}{RED}{doc['endpoints'][0]['endpointUrl']}{RESET}")
    print(f"  {DIM}(signature was NOT updated — operator's private key isn't available){RESET}")
    time.sleep(0.6)

    # 3. Resolve again
    banner(f"STEP 3  resolve {handle}  (tampered)")
    try:
        print_result(*call_resolve(handle))
    finally:
        # 4. Restore
        shutil.move(backup_path, facts_path)

    banner("STEP 4  restored original facts file")
    print_result(*call_resolve(handle))


if __name__ == "__main__":
    main()
