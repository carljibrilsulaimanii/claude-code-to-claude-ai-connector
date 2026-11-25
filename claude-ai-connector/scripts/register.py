"""Register the claude-ai bridge as a user-scope MCP server in ~/.claude.json.
Usage: python register.py <BRIDGE folder>"""
import json, os, shutil, sys
from pathlib import Path

if len(sys.argv) < 2:
    sys.exit("Usage: python register.py <BRIDGE folder>")
bridge = Path(sys.argv[1]).resolve()
py = bridge / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
for p in (py, bridge / "server.py"):
    if not p.exists():
        sys.exit(f"Missing {p}. Build the server first (skill step 2).")
cfg = Path.home() / ".claude.json"
data = json.loads(cfg.read_text(encoding="utf-8")) if cfg.exists() else {}
if cfg.exists():
    shutil.copy(cfg, str(cfg) + ".bak-claude-ai-bridge")
data.setdefault("mcpServers", {})["claude-ai"] = {
    "type": "stdio", "command": str(py), "args": [str(bridge / "server.py")], "env": {}}
cfg.write_text(json.dumps(data, indent=2), encoding="utf-8")
print("Registered claude-ai ->", py, bridge / "server.py")
print("User MCP servers:", list(data["mcpServers"]))
