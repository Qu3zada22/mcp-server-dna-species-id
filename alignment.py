"""Local sequence alignment (Smith-Waterman) for DNA barcode comparison.

Implemented from scratch (dynamic programming) rather than delegated to a
bioinformatics library, since scoring the alignment ourselves is the core
non-trivial piece of this MCP server.
"""

import re

MATCH_SCORE = 2
MISMATCH_SCORE = -1
GAP_PENALTY = -2

_VALID_BASES = re.compile(r"[^ACGTN]")


def clean_sequence(raw: str) -> str:
    """Normalizes a raw DNA sequence: uppercase, strips whitespace/newlines
    and FASTA headers, and validates it only contains IUPAC ACGTN bases."""
    lines = [line for line in raw.strip().splitlines() if not line.startswith(">")]
    sequence = "".join(lines).upper().replace(" ", "")
    invalid = _VALID_BASES.findall(sequence)
    if invalid:
        raise ValueError(
            f"Sequence contains invalid characters: {sorted(set(invalid))}. "
            "Only A, C, G, T, N are allowed."
        )
    if not sequence:
        raise ValueError("Sequence is empty after cleaning.")
    return sequence


def parse_fasta(path: str) -> list[tuple[str, str]]:
    """Parses a FASTA file into a list of (header, sequence) tuples."""
    records: list[tuple[str, str]] = []
    header = None
    chunks: list[str] = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if line.startswith(">"):
                if header is not None:
                    records.append((header, "".join(chunks)))
                header = line[1:]
                chunks = []
            else:
                chunks.append(line.upper())
    if header is not None:
        records.append((header, "".join(chunks)))
    return records


def smith_waterman(seq_a: str, seq_b: str) -> dict:
    """Local alignment of seq_a against seq_b. Returns the best-scoring local
    alignment: its score, the aligned subsequences, and percent identity."""
    n, m = len(seq_a), len(seq_b)
    h = [[0] * (m + 1) for _ in range(n + 1)]
    max_score = 0
    max_pos = (0, 0)

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            pair_score = MATCH_SCORE if seq_a[i - 1] == seq_b[j - 1] else MISMATCH_SCORE
            score = max(
                0,
                h[i - 1][j - 1] + pair_score,
                h[i - 1][j] + GAP_PENALTY,
                h[i][j - 1] + GAP_PENALTY,
            )
            h[i][j] = score
            if score > max_score:
                max_score = score
                max_pos = (i, j)

    aligned_a: list[str] = []
    aligned_b: list[str] = []
    i, j = max_pos
    while i > 0 and j > 0 and h[i][j] != 0:
        pair_score = MATCH_SCORE if seq_a[i - 1] == seq_b[j - 1] else MISMATCH_SCORE
        if h[i][j] == h[i - 1][j - 1] + pair_score:
            aligned_a.append(seq_a[i - 1])
            aligned_b.append(seq_b[j - 1])
            i -= 1
            j -= 1
        elif h[i][j] == h[i - 1][j] + GAP_PENALTY:
            aligned_a.append(seq_a[i - 1])
            aligned_b.append("-")
            i -= 1
        else:
            aligned_a.append("-")
            aligned_b.append(seq_b[j - 1])
            j -= 1

    aligned_a.reverse()
    aligned_b.reverse()
    aligned_a_str = "".join(aligned_a)
    aligned_b_str = "".join(aligned_b)

    alignment_length = len(aligned_a_str)
    matches = sum(1 for x, y in zip(aligned_a_str, aligned_b_str) if x == y and x != "-")
    identity_percent = round(100 * matches / alignment_length, 2) if alignment_length else 0.0

    return {
        "score": max_score,
        "aligned_query": aligned_a_str,
        "aligned_reference": aligned_b_str,
        "alignment_length": alignment_length,
        "identity_percent": identity_percent,
    }
