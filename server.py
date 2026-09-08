"""MCP server that identifies animal species from a DNA barcode (COI gene)
sequence by locally aligning it against a curated reference database.

Speaks JSON-RPC 2.0 directly over stdio — no MCP SDK. Each message is one
line of JSON terminated by '\\n', per the MCP stdio transport spec.
"""

import json
import os
import sys

from alignment import clean_sequence, parse_fasta, smith_waterman

REFERENCE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reference_sequences.fasta")
REFERENCE_RECORDS = parse_fasta(REFERENCE_PATH)

PROTOCOL_VERSION = "2025-11-25"

# Congeneric species (e.g. lion vs. tiger) can score >99% COI identity on a
# short barcode fragment, well above the usual ~97% species cutoff cited in
# DNA barcoding literature, so the "same species" threshold is set high to
# avoid misclassifying a close relative as the same species.
SAME_SPECIES_THRESHOLD = 99.0
RELATED_SPECIES_THRESHOLD = 90.0


def _interpret(identity_percent: float) -> str:
    if identity_percent >= SAME_SPECIES_THRESHOLD:
        return "same species"
    if identity_percent >= RELATED_SPECIES_THRESHOLD:
        return "closely related species (possible same genus)"
    return "different species"


def _list_reference_species(_arguments: dict) -> list[dict]:
    return [
        {"species": header.split("|")[0], "accession": header.split("|")[1]}
        for header, _ in REFERENCE_RECORDS
    ]


def _identify_sequence(arguments: dict) -> dict:
    query = clean_sequence(arguments["sequence"])
    top_n = arguments.get("top_n", 3)

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


def _compare_sequences(arguments: dict) -> dict:
    clean_a = clean_sequence(arguments["sequence_a"])
    clean_b = clean_sequence(arguments["sequence_b"])
    alignment = smith_waterman(clean_a, clean_b)

    return {
        "identity_percent": alignment["identity_percent"],
        "alignment_length": alignment["alignment_length"],
        "score": alignment["score"],
        "interpretation": _interpret(alignment["identity_percent"]),
        "aligned_sequence_a": alignment["aligned_query"],
        "aligned_sequence_b": alignment["aligned_reference"],
    }


TOOLS = {
    "list_reference_species": {
        "description": "Lists the species available in the reference COI barcode database.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": _list_reference_species,
    },
    "identify_sequence": {
        "description": (
            "Identifies the most likely species for a DNA barcode sequence by aligning "
            "it against every reference sequence and ranking by percent identity of the "
            "best local alignment."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "sequence": {
                    "type": "string",
                    "description": "raw DNA sequence (FASTA or plain), IUPAC bases A/C/G/T/N.",
                },
                "top_n": {
                    "type": "integer",
                    "description": "how many top matches to return (default 3).",
                },
            },
            "required": ["sequence"],
        },
        "handler": _identify_sequence,
    },
    "compare_sequences": {
        "description": (
            "Compares two arbitrary DNA barcode sequences directly against each other "
            "and reports their percent identity."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "sequence_a": {"type": "string", "description": "first raw DNA sequence."},
                "sequence_b": {"type": "string", "description": "second raw DNA sequence."},
            },
            "required": ["sequence_a", "sequence_b"],
        },
        "handler": _compare_sequences,
    },
}


def _write(message: dict) -> None:
    sys.stdout.write(json.dumps(message) + "\n")
    sys.stdout.flush()


def _handle_request(method: str, params: dict):
    if method == "initialize":
        return {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "dna-species-id", "version": "1.0.0"},
        }
    if method == "tools/list":
        return {
            "tools": [
                {
                    "name": name,
                    "description": tool["description"],
                    "inputSchema": tool["inputSchema"],
                }
                for name, tool in TOOLS.items()
            ]
        }
    if method == "tools/call":
        name = params["name"]
        arguments = params.get("arguments") or {}
        tool = TOOLS.get(name)
        if tool is None:
            raise ValueError(f"Unknown tool: {name}")
        try:
            result = tool["handler"](arguments)
            return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}
        except Exception as exc:  # noqa: BLE001 — surfaced to the client as a tool error
            return {"content": [{"type": "text", "text": str(exc)}], "isError": True}
    raise ValueError(f"Unknown method: {method}")


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            continue

        method = message.get("method")
        msg_id = message.get("id")
        params = message.get("params") or {}

        if method == "notifications/initialized":
            continue  # notifications never get a response

        try:
            result = _handle_request(method, params)
            if msg_id is not None:
                _write({"jsonrpc": "2.0", "id": msg_id, "result": result})
        except Exception as exc:  # noqa: BLE001 — reported back as a JSON-RPC error
            if msg_id is not None:
                _write({"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32603, "message": str(exc)}})


if __name__ == "__main__":
    main()
