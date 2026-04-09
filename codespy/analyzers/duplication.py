"""Code duplication detection via block hashing + similarity matching."""

import hashlib
import re
from difflib import SequenceMatcher
from ..models import DuplicationResult, DuplicatePair

WINDOW_SIZE = 6
SIMILARITY_THRESHOLD = 0.85


def _normalize_line(line: str) -> str:
    """Strip whitespace and normalize for comparison."""
    return re.sub(r'\s+', ' ', line.strip()).lower()


def _hash_block(block: list[str]) -> str:
    normalized = "\n".join(_normalize_line(l) for l in block)
    return hashlib.md5(normalized.encode()).hexdigest()


def _block_similarity(lines_a: list[str], lines_b: list[str]) -> float:
    norm_a = [_normalize_line(l) for l in lines_a]
    norm_b = [_normalize_line(l) for l in lines_b]
    return SequenceMatcher(None, norm_a, norm_b).ratio()


def analyze(
    file_paths: list[str],
    source_map: dict[str, list[str]],
) -> DuplicationResult:
    """Find duplicate blocks across all files."""
    # Build hash → list of (file_path, start_line_0indexed) index
    hash_index: dict[str, list[tuple[str, int]]] = {}

    for path in file_paths:
        lines = source_map.get(path, [])
        if len(lines) < WINDOW_SIZE:
            continue
        for i in range(len(lines) - WINDOW_SIZE + 1):
            block = lines[i:i + WINDOW_SIZE]
            # Skip blocks that are mostly blank/comment
            non_empty = [l for l in block if l.strip()]
            if len(non_empty) < WINDOW_SIZE // 2:
                continue
            h = _hash_block(block)
            if h not in hash_index:
                hash_index[h] = []
            hash_index[h].append((path, i))

    # Collect candidate pairs (same hash, different files or different locations)
    candidate_pairs: set[tuple[str, int, str, int]] = set()
    for h, locations in hash_index.items():
        if len(locations) < 2:
            continue
        for i in range(len(locations)):
            for j in range(i + 1, len(locations)):
                pa, la = locations[i]
                pb, lb = locations[j]
                if pa == pb and abs(la - lb) < WINDOW_SIZE:
                    continue  # overlapping in same file
                # Canonical order
                key = (pa, la, pb, lb) if (pa, la) < (pb, lb) else (pb, lb, pa, la)
                candidate_pairs.add(key)

    # Merge overlapping windows into extended blocks and check similarity
    pairs: list[DuplicatePair] = []
    seen: set[tuple[str, str, int, int]] = set()

    for pa, la, pb, lb in candidate_pairs:
        dedup_key = (pa, pb, la, lb)
        if dedup_key in seen:
            continue
        seen.add(dedup_key)

        lines_a = source_map.get(pa, [])
        lines_b = source_map.get(pb, [])

        # Extend the matching block forward
        end_a, end_b = la + WINDOW_SIZE, lb + WINDOW_SIZE
        while (end_a < len(lines_a) and end_b < len(lines_b) and
               _normalize_line(lines_a[end_a]) == _normalize_line(lines_b[end_b])):
            end_a += 1
            end_b += 1

        block_a = lines_a[la:end_a]
        block_b = lines_b[lb:end_b]

        sim = _block_similarity(block_a, block_b)
        if sim >= SIMILARITY_THRESHOLD:
            pairs.append(DuplicatePair(
                file_a=pa,
                file_b=pb,
                lines_a=[la + 1, end_a],  # 1-indexed
                lines_b=[lb + 1, end_b],
                similarity=round(sim, 3),
            ))

    # Deduplicate: keep the longest match per file-pair region
    pairs = _deduplicate_pairs(pairs)

    # Count unique (file, line_number) tuples so a file shared with N partners
    # only contributes its own lines once, not N times.
    dup_line_set: set[tuple[str, int]] = set()
    for p in pairs:
        for ln in range(p.lines_a[0], p.lines_a[1] + 1):
            dup_line_set.add((p.file_a, ln))
        for ln in range(p.lines_b[0], p.lines_b[1] + 1):
            dup_line_set.add((p.file_b, ln))
    total_dup_lines = len(dup_line_set)

    total_code_lines = sum(
        len([l for l in source_map.get(f, []) if l.strip()])
        for f in file_paths
    )
    dup_percent = (total_dup_lines / max(total_code_lines, 1)) * 100

    return DuplicationResult(
        duplicate_pairs=len(pairs),
        duplicated_lines=total_dup_lines,
        duplication_percent=round(dup_percent, 2),
        pairs=pairs[:50],  # cap output
    )


def _deduplicate_pairs(pairs: list[DuplicatePair]) -> list[DuplicatePair]:
    """Remove pairs that are subsets of larger pairs."""
    pairs.sort(key=lambda p: -(p.lines_a[1] - p.lines_a[0]))
    kept: list[DuplicatePair] = []
    for p in pairs:
        dominated = False
        for k in kept:
            if (k.file_a == p.file_a and k.file_b == p.file_b and
                    k.lines_a[0] <= p.lines_a[0] and k.lines_a[1] >= p.lines_a[1]):
                dominated = True
                break
        if not dominated:
            kept.append(p)
    return kept
