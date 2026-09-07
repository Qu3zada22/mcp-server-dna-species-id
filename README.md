# mcp-server-dna-species-id

An MCP (Model Context Protocol) server that identifies animal species from a DNA barcode
(the mitochondrial **COI** gene, the standard genetic "barcode" used for species identification)
by locally aligning the query sequence against a curated reference database. Built for CC3067
Redes (Universidad del Valle de Guatemala) as a custom MCP server for the
[mcp-zoo-chatbot](https://github.com/Qu3zada22/mcp-zoo-chatbot) project.

## How it works

1. A DNA sequence (raw or FASTA) is cleaned and validated (IUPAC bases A/C/G/T/N only).
2. It is locally aligned — using a from-scratch **Smith-Waterman** dynamic-programming
   implementation (`alignment.py`), not a bioinformatics library — against every sequence in
   `reference_sequences.fasta`.
3. Matches are ranked by percent identity of the best local alignment, and the top match is
   interpreted as "same species" / "closely related species" / "different species" based on
   identity thresholds.

The reference database contains real partial COI sequences (500–700 bp) for 8 species, pulled
from NCBI GenBank: lion, tiger, African elephant, giraffe, chimpanzee, giant panda, ostrich, and
Nile crocodile — a reasonable spread of species you'd find at a zoo.

> **Note on thresholds:** congeneric species (e.g. lion vs. tiger) can score above 99% identity on
> a short barcode fragment — well above the ~97% cutoff commonly cited in DNA barcoding literature
> for a full-length barcode — so `SAME_SPECIES_THRESHOLD` in `server.py` is set conservatively high
> (99%) to avoid misclassifying a close relative as the same species. This is a heuristic for a
> class project, not a rigorous "barcoding gap" analysis.

## Tools

### `identify_sequence(sequence: str, top_n: int = 3) -> dict`

Identifies the most likely species for a DNA barcode sequence.

**Returns:**
```json
{
  "query_length": 581,
  "best_match": {
    "species": "Panthera leo",
    "accession": "MN124275.1",
    "identity_percent": 100.0,
    "alignment_length": 581,
    "score": 1162
  },
  "interpretation": "same species",
  "top_matches": ["... up to top_n matches, same shape as best_match ..."]
}
```

### `compare_sequences(sequence_a: str, sequence_b: str) -> dict`

Compares two arbitrary DNA sequences directly against each other (not against the reference
database) and reports their percent identity.

**Returns:**
```json
{
  "identity_percent": 99.14,
  "alignment_length": 581,
  "score": 1105,
  "interpretation": "closely related species (possible same genus)",
  "aligned_sequence_a": "ACTG...",
  "aligned_sequence_b": "ACTG..."
}
```

### `list_reference_species() -> list[dict]`

Lists the species available in the reference database, e.g.
`[{"species": "Panthera leo", "accession": "MN124275.1"}, ...]`.

## Requirements

- Python 3.11+

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Usage

### Standalone (for testing)

```bash
python server.py
```

This starts the server on stdio, waiting for an MCP client to connect (it prints nothing on its
own — it's meant to be driven by a client, not run interactively).

### From an MCP host (e.g. Claude Desktop, or a custom chatbot)

Add it to the host's MCP server configuration, pointing `command`/`args` at this server, e.g.:

```json
{
  "name": "dna-species-id",
  "command": "python3",
  "args": ["/absolute/path/to/mcp-server-dna-species-id/server.py"]
}
```

### Example

Given a query sequence identical to the reference lion sequence:

```
> identify_sequence(sequence="ACTGCTTTCAGTCTCTTAATCCGAGCC...")
{
  "best_match": {"species": "Panthera leo", "identity_percent": 100.0, ...},
  "interpretation": "same species",
  ...
}
```

## Project structure

```
mcp-server-dna-species-id/
├── server.py                  # MCP tools (FastMCP)
├── alignment.py                # Smith-Waterman implementation (from scratch)
├── reference_sequences.fasta   # 8 real COI sequences from NCBI GenBank
├── requirements.txt
└── README.md
```
