"""Register the claude-ai bridge as a user-scope MCP server in ~/.claude.json.
Usage: python register.py <BRIDGE folder> [server name, default claude-ai]
A second account gets its own folder and its own name, e.g. claude-ai-work.
Without a name this writes "claude-ai" and replaces any existing entry with that name."""
import json, os, shutil, sys
from pathlib import Path

if len(sys.argv) < 2:
    sys.exit("Usage: python register.py <BRIDGE folder> [server name]")
bridge = Path(sys.argv[1]).resolve()
name = sys.argv[2] if len(sys.argv) > 2 else "claude-ai"
py = bridge / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
for p in (py, bridge / "server.py"):
    if not p.exists():
        sys.exit(f"Missing {p}. Build the server first (skill step 2).")
cfg = Path.home() / ".claude.json"
data = json.loads(cfg.read_text(encoding="utf-8")) if cfg.exists() else {}
if cfg.exists():
    shutil.copy(cfg, str(cfg) + ".bak-claude-ai-bridge")
data.setdefault("mcpServers", {})[name] = {
    "type": "stdio", "command": str(py), "args": [str(bridge / "server.py")], "env": {}}
cfg.write_text(json.dumps(data, indent=2), encoding="utf-8")
print(f"Registered {name} ->", py, bridge / "server.py")
print("User MCP servers:", list(data["mcpServers"]))
