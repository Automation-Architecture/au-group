#!/usr/bin/env python3
"""Re-parse documents with null bankruptcy_id when case_number is in s3_key path."""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
from uuid import UUID

import httpx

CASE_IN_KEY = re.compile(r"raw-documents/([^/]+)/", re.I)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()

    base = os.environ.get("SUPABASE_URL", "").rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    parser_url = os.environ.get("DOCUMENT_PARSER_URL", "http://localhost:8001").rstrip("/")
    api_key = os.environ.get("API_KEY", "")

    if not base or not key:
        print("Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY", file=sys.stderr)
        return 1
    if not api_key and not args.dry_run:
        print("Set API_KEY for document-parser", file=sys.stderr)
        return 1

    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
    }
    with httpx.Client(timeout=60.0) as client:
        docs = client.get(
            f"{base}/rest/v1/documents",
            headers=headers,
            params={
                "select": "id,s3_key,filing_type",
                "bankruptcy_id": "is.null",
                "limit": str(args.limit),
            },
        ).json()

        bankruptcies = client.get(
            f"{base}/rest/v1/bankruptcies",
            headers=headers,
            params={"select": "id,case_number"},
        ).json()
        by_case = {b["case_number"]: b["id"] for b in bankruptcies}

        for doc in docs:
            s3_key = doc.get("s3_key") or ""
            bankruptcy_id = None
            case_number = None

            reviews = client.get(
                f"{base}/rest/v1/manual_review_queue",
                headers=headers,
                params={
                    "select": "bankruptcy_id",
                    "document_id": f"eq.{doc['id']}",
                    "bankruptcy_id": "not.is.null",
                    "limit": "1",
                },
            ).json()
            if reviews and reviews[0].get("bankruptcy_id"):
                bankruptcy_id = reviews[0]["bankruptcy_id"]

            match = CASE_IN_KEY.search(s3_key)
            if match:
                case_number = match.group(1)
                bankruptcy_id = bankruptcy_id or by_case.get(case_number)

            if not bankruptcy_id:
                print(f"skip {doc['id']}: no bankruptcy link for s3_key {s3_key}")
                continue
            if not case_number:
                for cn, bid in by_case.items():
                    if bid == bankruptcy_id:
                        case_number = cn
                        break

            hint = doc.get("filing_type") or "UNKNOWN"
            print(f"{'[dry-run] ' if args.dry_run else ''}reparse {doc['id']} -> {bankruptcy_id} ({hint})")

            if args.dry_run:
                continue

            client.post(
                f"{base}/rest/v1/rpc/au_group_link_document_bankruptcy",
                headers={**headers, "Content-Type": "application/json"},
                json={
                    "p_document_id": doc["id"],
                    "p_bankruptcy_id": bankruptcy_id,
                },
            ).raise_for_status()

            docket_hint = hint if hint in {"FORM_201", "CREDITOR_MATRIX", "SCHEDULE", "SOFA"} else "UNKNOWN"
            resp = client.post(
                f"{parser_url}/api/v1/parse/document",
                headers={"X-API-Key": api_key, "Content-Type": "application/json"},
                json={
                    "bankruptcy_id": bankruptcy_id,
                    "s3_key": s3_key,
                    "docket_hint": docket_hint,
                    "force": True,
                },
            )
            print(f"  parser status={resp.status_code}")
            if resp.status_code >= 400:
                print(resp.text, file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
