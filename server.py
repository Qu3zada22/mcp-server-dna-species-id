"""MCP server that identifies animal species from a DNA barcode (COI gene)
sequence by locally aligning it against a curated reference database."""

import os

from mcp.server.fastmcp import FastMCP

from alignment import clean_sequence, parse_fasta, smith_waterman

REFERENCE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reference_sequences.fasta")
REFERENCE_RECORDS = parse_fasta(REFERENCE_PATH)

# Congeneric species (e.g. lion vs. tiger) can score >99% COI identity on a
# short barcode fragment, well above the usual ~97% species cutoff cited in
# DNA barcoding literature, so the "same species" threshold is set high to
# avoid misclassifying a close relative as the same species.
SAME_SPECIES_THRESHOLD = 99.0
RELATED_SPECIES_THRESHOLD = 90.0

mcp = FastMCP(
    name="dna-species-id",
    instructions=(
        "Identifies animal species from a DNA barcode (COI gene) sequence by "
        "local sequence alignment (Smith-Waterman) against a reference database."
    ),
)


def _interpret(identity_percent: float) -> str:
    if identity_percent >= SAME_SPECIES_THRESHOLD:
        return "same species"
    if identity_percent >= RELATED_SPECIES_THRESHOLD:
        return "closely related species (possible same genus)"
    return "different species"


@mcp.tool()
def list_reference_species() -> list[dict]:
    """Lists the species available in the reference COI barcode database."""
    return [
        {"species": header.split("|")[0], "accession": header.split("|")[1]}
        for header, _ in REFERENCE_RECORDS
    ]


@mcp.tool()
def identify_sequence(sequence: str, top_n: int = 3) -> dict:
    """Identifies the most likely species for a DNA barcode sequence by
    aligning it against every reference sequence and ranking by percent
    identity of the best local alignment.

    Args:
        sequence: raw DNA sequence (FASTA or plain), IUPAC bases A/C/G/T/N.
        top_n: how many top matches to return (default 3).
    """
    query = clean_sequence(sequence)

    results = []
    for header, reference_seq in REFERENCE_RECORDS:
        species, accession = header.split("|", 1)
        alignment = smith_waterman(query, reference_seq)
        results.append(
            {
                "species": species,
                "accession": accession,
                "identity_percent": alignment["identity_percent"],
                "alignment_length": alignment["alignment_length"],
                "score": alignment["score"],
            }
        )

    results.sort(key=lambda r: r["identity_percent"], reverse=True)
    top_matches = results[:top_n]
    best = top_matches[0] if top_matches else None

    return {
        "query_length": len(query),
        "best_match": best,
        "interpretation": _interpret(best["identity_percent"]) if best else "no reference data",
        "top_matches": top_matches,
    }


@mcp.tool()
def compare_sequences(sequence_a: str, sequence_b: str) -> dict:
    """Compares two arbitrary DNA barcode sequences directly against each
    other and reports their percent identity and a same/related/different
    species interpretation.

    Args:
        sequence_a: first raw DNA sequence.
        sequence_b: second raw DNA sequence.
    """
    clean_a = clean_sequence(sequence_a)
    clean_b = clean_sequence(sequence_b)
    alignment = smith_waterman(clean_a, clean_b)

    return {
        "identity_percent": alignment["identity_percent"],
        "alignment_length": alignment["alignment_length"],
        "score": alignment["score"],
        "interpretation": _interpret(alignment["identity_percent"]),
        "aligned_sequence_a": alignment["aligned_query"],
        "aligned_sequence_b": alignment["aligned_reference"],
    }


if __name__ == "__main__":
    mcp.run(transport="stdio")
