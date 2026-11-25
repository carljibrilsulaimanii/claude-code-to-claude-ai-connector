"""claude.ai bridge: a local MCP server that reads your own claude.ai chats,
projects and memory through claude.ai's private web API, using your sessionKey
cookie from .env. Unofficial: the endpoints can change without notice."""

import json
import os
import sqlite3
import time
from pathlib import Path

from curl_cffi import requests
from mcp.server.mcpserver import MCPServer

HERE = Path(__file__).parent
DB_PATH = HERE / "cache.sqlite"
BASE = "https://claude.ai"


def load_env():
    env_file = HERE / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


load_env()
mcp = MCPServer("claude-ai")
_session = None
_org = None


def cookies_from_file():
    """Read claude.ai cookies from a Netscape cookies.txt (e.g. the 'Get cookies.txt'
    extension's Export) saved in this folder. Picks the newest claude.ai*cookies*.txt."""
    files = sorted(list(HERE.glob("*cookies*.txt")), key=lambda p: p.stat().st_mtime, reverse=True)
    for f in files:
        jar = {}
        for line in f.read_text(encoding="utf-8", errors="ignore").splitlines():
            if line.startswith("#HttpOnly_"):
                line = line[len("#HttpOnly_"):]
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) >= 7 and parts[0].lstrip(".").endswith("claude.ai"):
                jar[parts[5]] = parts[6].strip()
        if jar.get("sessionKey"):
            return jar
    return {}


def session():
    global _session
    if _session is None:
        jar = cookies_from_file()
        key = os.environ.get("CLAUDE_SESSION_KEY", "")
        if key and not key.startswith("PASTE"):
            jar["sessionKey"] = key
        if not jar.get("sessionKey"):
            raise RuntimeError(
                f"No sessionKey. Export claude.ai cookies.txt into {HERE} (or put "
                f"CLAUDE_SESSION_KEY=sk-ant-sid... in {HERE / '.env'}) and restart Claude Code."
            )
        _session = requests.Session(impersonate="chrome")
        for name, value in jar.items():
            _session.cookies.set(name, value, domain="claude.ai")
        _session.headers.update({"Accept": "application/json", "Referer": BASE + "/"})
    return _session


def get(path, **params):
    r = session().get(BASE + path, params=params or None, timeout=60)
    if r.status_code in (401, 403):
        raise RuntimeError(
            f"claude.ai refused the request ({r.status_code}). The sessionKey has "
            "probably expired: export a fresh cookies.txt into the bridge folder "
            "and restart Claude Code."
        )
    r.raise_for_status()
    return r.json()


def org_id():
    global _org
    if _org is None:
        _org = os.environ.get("CLAUDE_ORG_ID") or None
        if not _org:
            orgs = get("/api/organizations")
            chat_orgs = [o for o in orgs if "chat" in (o.get("capabilities") or [])]
            _org = (chat_orgs or orgs)[0]["uuid"]
    return _org


def msg_text(m):
    parts = []
    for block in m.get("content") or []:
        t = block.get("type")
        if t == "text":
            parts.append(block.get("text", ""))
        elif t == "tool_use":
            parts.append(f"[tool_use {block.get('name')}: {json.dumps(block.get('input'))[:500]}]")
        elif t == "tool_result":
            inner = block.get("content")
            if isinstance(inner, list):
                inner = " ".join(c.get("text", "") for c in inner if isinstance(c, dict))
            parts.append(f"[tool_result: {str(inner)[:500]}]")
    if not parts and m.get("text"):
        parts.append(m["text"])
    for a in m.get("attachments") or []:
        parts.append(f"[attachment {a.get('file_name')}]\n{(a.get('extracted_content') or '')[:2000]}")
    return "\n".join(parts)


def fetch_chat(cid):
    return get(
        f"/api/organizations/{org_id()}/chat_conversations/{cid}",
        tree="True", rendering_mode="messages", render_all_tools="true",
    )


def db():
    con = sqlite3.connect(DB_PATH)
    con.execute(
        "CREATE TABLE IF NOT EXISTS chats(uuid TEXT PRIMARY KEY, name TEXT, "
        "updated_at TEXT, created_at TEXT, project TEXT, body TEXT)"
    )
    con.execute(
        "CREATE VIRTUAL TABLE IF NOT EXISTS chats_fts USING fts5("
        "uuid UNINDEXED, name, body, tokenize='porter unicode61')"
    )
    return con


@mcp.tool()
def list_orgs() -> list:
    """List the claude.ai organizations this sessionKey can see, and which one is in use."""
    orgs = get("/api/organizations")
    current = org_id()
    return [
        {"uuid": o["uuid"], "name": o.get("name"), "capabilities": o.get("capabilities"),
         "in_use": o["uuid"] == current}
        for o in orgs
    ]


@mcp.tool()
def list_chats(limit: int = 50, offset: int = 0, title_contains: str = "") -> list:
    """List claude.ai conversations, newest first: uuid, title, dates, project.
    title_contains filters by title (case-insensitive)."""
    chats = get(f"/api/organizations/{org_id()}/chat_conversations")
    chats.sort(key=lambda c: c.get("updated_at") or "", reverse=True)
    if title_contains:
        chats = [c for c in chats if title_contains.lower() in (c.get("name") or "").lower()]
    return [
        {"uuid": c["uuid"], "name": c.get("name"), "updated_at": c.get("updated_at"),
         "created_at": c.get("created_at"),
         "project": (c.get("project") or {}).get("name") if c.get("project") else c.get("project_uuid"),
         "url": f"{BASE}/chat/{c['uuid']}"}
        for c in chats[offset: offset + limit]
    ]


@mcp.tool()
def get_chat(uuid: str, max_chars: int = 60000) -> str:
    """Return a claude.ai conversation as a readable transcript (speaker, time, text)."""
    c = fetch_chat(uuid)
    lines = [f"# {c.get('name')}  ({c.get('created_at')} -> {c.get('updated_at')})",
             f"{BASE}/chat/{uuid}", ""]
    for m in c.get("chat_messages") or []:
        who = "USER" if m.get("sender") == "human" else "CLAUDE"
        lines.append(f"## {who} {m.get('created_at', '')}\n{msg_text(m)}\n")
    out = "\n".join(lines)
    return out if len(out) <= max_chars else out[:max_chars] + f"\n...[truncated, {len(out)} chars total]"


@mcp.tool()
def sync_chats(full: bool = False) -> str:
    """Download claude.ai conversations into the local search index. Only chats
    updated since the last sync are fetched unless full=True. Run before search_chats."""
    con = db()
    known = dict(con.execute("SELECT uuid, updated_at FROM chats"))
    chats = get(f"/api/organizations/{org_id()}/chat_conversations")
    todo = [c for c in chats if full or known.get(c["uuid"]) != c.get("updated_at")]
    done, failed = 0, []
    for c in todo:
        try:
            full_chat = fetch_chat(c["uuid"])
        except Exception as e:  # keep going; report at the end
            failed.append(f"{c['uuid']}: {e}")
            continue
        body = "\n\n".join(
            ("USER: " if m.get("sender") == "human" else "CLAUDE: ") + msg_text(m)
            for m in full_chat.get("chat_messages") or []
        )
        proj = c.get("project_uuid") or ""
        con.execute("INSERT OR REPLACE INTO chats VALUES (?,?,?,?,?,?)",
                    (c["uuid"], c.get("name"), c.get("updated_at"), c.get("created_at"), proj, body))
        con.execute("DELETE FROM chats_fts WHERE uuid=?", (c["uuid"],))
        con.execute("INSERT INTO chats_fts VALUES (?,?,?)", (c["uuid"], c.get("name"), body))
        done += 1
        if done % 25 == 0:
            con.commit()
        time.sleep(0.25)
    con.commit()
    total = con.execute("SELECT COUNT(*) FROM chats").fetchone()[0]
    msg = f"Synced {done} of {len(todo)} changed chats; {total} chats indexed of {len(chats)} on claude.ai."
    if failed:
        msg += f"\n{len(failed)} failed:\n" + "\n".join(failed[:20])
    return msg


@mcp.tool()
def search_chats(query: str, limit: int = 20) -> list:
    """Full-text search the locally synced claude.ai chats (run sync_chats first).
    Supports FTS5 syntax: words, "exact phrase", OR, NOT, prefix*."""
    con = db()
    rows = con.execute(
        "SELECT f.uuid, c.name, c.updated_at, snippet(chats_fts, 2, '>>', '<<', ' ... ', 24) "
        "FROM chats_fts f JOIN chats c ON c.uuid=f.uuid WHERE chats_fts MATCH ? "
        "ORDER BY rank LIMIT ?", (query, limit)).fetchall()
    return [{"uuid": u, "name": n, "updated_at": d, "snippet": s, "url": f"{BASE}/chat/{u}"}
            for u, n, d, s in rows]


@mcp.tool()
def list_projects() -> list:
    """List claude.ai projects: uuid, name, description, dates."""
    projects = get(f"/api/organizations/{org_id()}/projects")
    return [
        {"uuid": p["uuid"], "name": p.get("name"), "description": p.get("description"),
         "updated_at": p.get("updated_at"), "archived": bool(p.get("archived_at")),
         "url": f"{BASE}/project/{p['uuid']}"}
        for p in projects
    ]


@mcp.tool()
def get_project(uuid: str, include_docs: bool = True, max_doc_chars: int = 20000) -> dict:
    """Return a claude.ai project's custom instructions and (optionally) its knowledge docs."""
    base = f"/api/organizations/{org_id()}/projects/{uuid}"
    p = get(base)
    out = {"name": p.get("name"), "description": p.get("description"),
           "instructions": p.get("prompt_template"), "url": f"{BASE}/project/{uuid}"}
    if include_docs:
        docs = get(base + "/docs")
        out["docs"] = [{"uuid": d.get("uuid"), "file_name": d.get("file_name"),
                        "content": (d.get("content") or "")[:max_doc_chars]} for d in docs]
    return out


@mcp.tool()
def get_memory() -> object:
    """Return the claude.ai memory for this account (and any project memories it lists)."""
    org = org_id()
    errors = []
    for path in (f"/api/organizations/{org}/memory", f"/api/organizations/{org}/memories",
                 f"/api/organizations/{org}/memory/synthesis"):
        try:
            return get(path)
        except Exception as e:
            errors.append(f"{path}: {e}")
    return {"error": "No memory endpoint answered.", "tried": errors}


@mcp.tool()
def api_get(path: str) -> object:
    """Raw GET on claude.ai's web API, for endpoints the other tools don't cover.
    path starts with /api/ ; {org} is replaced with the organization uuid."""
    if not path.startswith("/api/"):
        raise ValueError("path must start with /api/")
    return get(path.replace("{org}", org_id()))


if __name__ == "__main__":
    mcp.run()
