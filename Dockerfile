# No dependencies to install: server.py uses only the Python standard
# library (no MCP SDK, no third-party packages) — see requirements.txt.
FROM python:3.11-slim

WORKDIR /app
COPY server.py alignment.py reference_sequences.fasta ./

# MCP speaks JSON-RPC over stdin/stdout — run this with `docker run -i`
# (interactive stdin, no pseudo-TTY) so a host process can pipe JSON-RPC
# messages in and read responses out, exactly like a local subprocess.
ENTRYPOINT ["python3", "-u", "server.py"]
