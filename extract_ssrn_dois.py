#!/usr/bin/env python3
"""
Step 1 of 2: Extract SSRN IDs from SopaDeOtoe + Strategy_lab sources,
             resolve to real DOIs via Crossref API.

SSRN IDs in code (e.g. "SSRN 275161") are internal handles, NOT DOIs.
Crossref maps SSRN pre-print IDs to final DOIs.

Usage:
    cd /Users/nongo/Documents/Patacon/SopaDeOtoe
    ~/.venvs/pydoll/bin/python3.12 extract_ssrn_dois.py
"""

import csv
import re
import urllib.request
import json
from pathlib import Path

# ── Config ───────────────────────────────────────────────────────────────────

SOPA_STRATEGIES    = Path("/Users/nongo/Documents/Patacon/SopaDeOtoe/strategies")
STRATEGY_LAB_FEAT  = Path("/Users/nongo/Documents/Patacon/StrategyParrot/Strategy_lab/features")
OUTPUT_FILE        = Path("/Users/nongo/Documents/Patacon/SopaDeOtoe/ssrn_dois.csv")

SSRN_PAT = re.compile(r"SSRN\s*(\d{6,})", re.IGNORECASE)
CROSSREF_URL = "https://api.crossref.org/works?query=SSRN:{id}&rows=1"

# ── 1. Extract unique SSRN IDs from source files ──────────────────────────────

def extract_ssrn_ids() -> dict[str, list[str]]:
    """{ssrn_id: [relative_source_files]}"""
    results: dict[str, list[str]] = {}

    for directory in [SOPA_STRATEGIES, STRATEGY_LAB_FEAT]:
        base = directory.parent.parent if directory == STRATEGY_LAB_FEAT else directory

        for py_file in directory.glob("*.py"):
            for m in SSRN_PAT.finditer(py_file.read_text()):
                results.setdefault(m.group(1), []).append(
                    str(py_file.relative_to(base))
                )

        for md_file in directory.glob("*.md"):
            for m in SSRN_PAT.finditer(md_file.read_text()):
                results.setdefault(m.group(1), []).append(
                    str(md_file.relative_to(base))
                )

    return results


# ── 2. Resolve SSRN ID → DOI via Crossref ───────────────────────────────────

def resolve_doi(ssrn_id: str) -> str | None:
    url = CROSSREF_URL.format(id=ssrn_id)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "python/3"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.load(resp)
            items = data.get("message", {}).get("items", [])
            if items:
                doi = items[0].get("DOI")
                return doi
    except Exception as e:
        return None
    return None


# ── 3. Main ──────────────────────────────────────────────────────────────────

def main():
    print("[*] Scanning for SSRN IDs...")
    ssrn_map = extract_ssrn_ids()

    if not ssrn_map:
        print("[!] No SSRN IDs found.")
        return

    print(f"[*] Found {len(ssrn_map)} unique SSRN IDs:")
    for ssrn_id, sources in sorted(ssrn_map.items()):
        print(f"    SSRN {ssrn_id} <- {', '.join(sources)}")

    print("\n[*] Resolving via Crossref...")
    rows = []
    for i, (ssrn_id, sources) in enumerate(sorted(ssrn_map.items()), 1):
        print(f"[{i}/{len(ssrn_map)}] SSRN {ssrn_id}...", end=" ", flush=True)
        doi = resolve_doi(ssrn_id)
        status = f"DOI: {doi}" if doi else "No DOI"
        print(status)
        rows.append((ssrn_id, "; ".join(sources), doi or ""))

    with open(OUTPUT_FILE, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["ssrn_id", "source_files", "doi"])
        writer.writerows(rows)

    found = sum(1 for r in rows if r[2])
    print(f"\n[+] {found}/{len(rows)} DOIs resolved -> {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
