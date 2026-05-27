"""FR-3.5 / KD-40: fuzzy creditor deduplication within a single filing.

Scores normalized name+address (stricter than name-only). Union-Find clusters pairs
at or above the threshold; if A~B and B~C both match, A/B/C merge even when A~C
is below threshold (transitive closure by design). Pairwise scan is O(n^2); typical
creditor matrices are small; very large filings may need blocking in a follow-up.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass

from rapidfuzz import fuzz

from app.models.schemas import CreditorRow

_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)
_WS_RE = re.compile(r"\s+")


def normalize_creditor_key(name: str, address: str | None) -> str:
    """Normalize name + address for fuzzy comparison."""
    parts: list[str] = []
    for raw in (name, address or ""):
        cleaned = _PUNCT_RE.sub(" ", raw.lower())
        cleaned = _WS_RE.sub(" ", cleaned).strip()
        if cleaned:
            parts.append(cleaned)
    return " ".join(parts)


@dataclass(frozen=True)
class DedupStats:
    original_count: int
    deduped_count: int

    @property
    def duplicates_removed(self) -> int:
        return self.original_count - self.deduped_count


class _UnionFind:
    def __init__(self, n: int) -> None:
        self.parent = list(range(n))

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra


def _similarity(a: CreditorRow, b: CreditorRow) -> float:
    key_a = normalize_creditor_key(a.creditor_name, a.address)
    key_b = normalize_creditor_key(b.creditor_name, b.address)
    if not key_a or not key_b:
        return 0.0
    return float(fuzz.token_set_ratio(key_a, key_b))


def _sum_claim_amounts(amounts: list[float | None]) -> float | None:
    if not amounts:
        return None
    if all(a is None for a in amounts):
        return None
    return sum(a or 0.0 for a in amounts)


def _union_line_numbers(rows: list[CreditorRow]) -> list[int]:
    seen: set[int] = set()
    ordered: list[int] = []
    for row in rows:
        for line in row.source_line_numbers or []:
            if line not in seen:
                seen.add(line)
                ordered.append(line)
    return sorted(ordered)


def _pick_canonical_index(indices: list[int], rows: list[CreditorRow]) -> int:
    def sort_key(i: int) -> tuple[float, int, int]:
        conf = rows[i].confidence_score
        return (
            -(conf if conf is not None else -1.0),
            -len(rows[i].creditor_name),
            i,
        )

    return min(indices, key=sort_key)


def _merge_group(indices: list[int], rows: list[CreditorRow]) -> CreditorRow:
    group = [rows[i] for i in indices]
    canonical_idx = _pick_canonical_index(indices, rows)
    canonical = rows[canonical_idx]
    merged_names = sorted(
        {r.creditor_name for r in group},
        key=lambda n: (n != canonical.creditor_name, n.lower()),
    )
    all_amounts = [r.claim_amount for r in group]
    line_numbers = _union_line_numbers(group)
    dedup_audit: dict[str, object] | None = None
    if len(group) > 1:
        dedup_audit = {
            "dedup_group_id": str(uuid.uuid4()),
            "merged_names": merged_names,
            "source_line_numbers": line_numbers,
            "duplicate_count": len(group),
        }

    return CreditorRow(
        creditor_name=canonical.creditor_name,
        address=canonical.address,
        claim_amount=_sum_claim_amounts(all_amounts),
        entity_type=canonical.entity_type,
        original_name=canonical.original_name or canonical.creditor_name,
        confidence_score=max(
            (r.confidence_score for r in group if r.confidence_score is not None),
            default=canonical.confidence_score,
        ),
        source_line_numbers=line_numbers,
        dedup_audit=dedup_audit,
    )


def deduplicate_creditors(
    rows: list[CreditorRow],
    *,
    threshold: int = 85,
) -> tuple[list[CreditorRow], DedupStats]:
    """Consolidate fuzzy duplicate creditors; sum claims; preserve line audit."""
    original_count = len(rows)
    if original_count <= 1:
        stats = DedupStats(original_count=original_count, deduped_count=original_count)
        return list(rows), stats

    uf = _UnionFind(original_count)
    for i in range(original_count):
        for j in range(i + 1, original_count):
            if _similarity(rows[i], rows[j]) >= threshold:
                uf.union(i, j)

    clusters: dict[int, list[int]] = {}
    for i in range(original_count):
        root = uf.find(i)
        clusters.setdefault(root, []).append(i)

    deduped = [_merge_group(indices, rows) for indices in clusters.values()]
    stats = DedupStats(original_count=original_count, deduped_count=len(deduped))
    return deduped, stats
