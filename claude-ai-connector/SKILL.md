---
name: claude-ai-connector
description: Set up, repair or refresh the Claude Code to claude.ai connector, a local MCP server ("claude-ai") that reads the user's claude.ai chats, projects and memory through claude.ai's private web API using cookies exported by the "Get cookies.txt LOCALLY" Chrome extension. Use whenever the user wants Claude Code to see claude.ai chats, projects or memory, asks to connect Claude Code to claude.ai, says the claude-ai tools are missing or return 401/403, says the cookie expired, wants this set up on a new computer, or signs in with a second claude.ai account and wants a server for it too. Not for the official claude.ai connectors (Drive, Gmail, etc.) or the Anthropic API.
---

# Claude Code to claude.ai connector

claude.ai has no official API for chats, projects or memory. This connector is a
local MCP server that calls claude.ai's private web API with the user's own browser
cookies. It's **unofficial**: endpoints can change without notice, cookies expire,
and using it may conflict with claude.ai's Terms. Tell the user that once before
building it.

Install location: ask the user, or default to `~/claude-ai-bridge` (call it BRIDGE
below). Keep it out of synced folders (OneDrive, Google Drive, Dropbox). This skill's
`scripts/` holds everything needed. On macOS/Linux the venv Python is
`BRIDGE/.venv/bin/python` instead of `BRIDGE/.venv/Scripts/python.exe`.

## Hard rule: the cookie is the user's to handle

The sessionKey is effectively the user's claude.ai login. Claude **never** copies it
out of the browser, reads it aloud, prints it, or types it into a file. The user
exports it; the server reads the file. When testing, print only counts and
`bool(present)`, never values. Never use `document.cookie` or browser tools to get it
(it's HttpOnly anyway).

## Step 1. Chrome extension (the user does this)

1. In Chrome, install **Get cookies.txt LOCALLY** from the Chrome Web Store
   (open source, exports locally). **Always give the user this full link**, not just
   the name:
   https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc
   **Don't** install the old extension named plain "Get cookies.txt": Google removed it
   as malware for uploading cookies.
2. Pin it: puzzle-piece icon → pin.
3. Extensions are per Chrome profile. Install it in the profile that's signed in to the
   claude.ai account being connected.

## Step 2. Build the server (Claude does this)

```bash
mkdir -p BRIDGE
cp <skill>/scripts/server.py BRIDGE/
python -m venv BRIDGE/.venv
BRIDGE/.venv/Scripts/python.exe -m pip install -q "mcp[cli]" curl_cffi
```

- `mcp` 2.x renamed FastMCP to `MCPServer` (`from mcp.server.mcpserver import MCPServer`).
  server.py already uses the 2.x name. If pip installs 1.x, change the import back to
  `from mcp.server.fastmcp import FastMCP`.
- `curl_cffi` with `impersonate="chrome"` matters: plain `requests` gets blocked by
  Cloudflare on claude.ai.
- Optional `.env` in BRIDGE: `CLAUDE_SESSION_KEY=` (overrides the file; user pastes it)
  and `CLAUDE_ORG_ID=` (forces an org; blank = first org with the `chat` capability).

## Step 3. Register it with Claude Code (Claude does this)

```bash
BRIDGE/.venv/Scripts/python.exe <skill>/scripts/register.py BRIDGE
```

This backs up `~/.claude.json` to `~/.claude.json.bak-claude-ai-bridge` and adds a
user-scope `mcpServers.claude-ai` entry. If the `claude` CLI is on PATH,
`claude mcp add --scope user claude-ai -- BRIDGE/.venv/Scripts/python.exe BRIDGE/server.py`
does the same.

## Step 4. Export the cookies (the user does this)

1. Open https://claude.ai in Chrome, signed in.
2. Click the **Get cookies.txt LOCALLY** icon.
3. Export Format: **Netscape**. Click **Export As**.
4. Save into BRIDGE. The name must contain `cookies` and end in `.txt`,
   e.g. `claude.ai_cookies.txt`.

The server loads every claude.ai cookie from the newest `*cookies*.txt` in BRIDGE,
including `sessionKey`. Sending the full set looks more like the real browser.

Alternative without the extension: DevTools (F12) → Application → Cookies →
https://claude.ai → `sessionKey` → copy Value into `.env` as `CLAUDE_SESSION_KEY=...`.

## Step 5. Test (Claude does this)

```bash
BRIDGE/.venv/Scripts/python.exe <skill>/scripts/test_bridge.py BRIDGE
```

It prints orgs, the latest 3 chat titles, chat/project counts, and the start of the
memory. Add `--sync` to also build the search index and run a sample search (first full
sync is about 90 seconds per 150 chats). Report the counts to the user.

## Step 6. Restart

The `claude-ai` tools load only in **sessions started after registration**. The user
must open a new session (or fully quit and reopen the desktop app). Check with
ToolSearch `+claude-ai`. A session started before then can still call the
server directly through its Python functions.

## Step 7. Check the org (Claude does this)

With no `CLAUDE_ORG_ID`, the server uses the **first** org with the `chat` capability.
On a Team or Enterprise login that's often the user's near-empty individual org, not
the team. Count chats per org before calling setup done:

```python
# for each org from list_orgs(): set srv._org = uuid, then
# len(api_get("/api/organizations/{org}/chat_conversations?limit=1000"))
```

Team orgs show the `raven` capability. If another org has the real history, put
`CLAUDE_ORG_ID=<uuid>` in BRIDGE/.env, **delete BRIDGE/cache.sqlite** (it holds the
other org's chats), and rerun the test with `--sync`. One server reads one org.

## Optional: a second claude.ai login

**Skip this unless the user signs in to claude.ai with more than one account** (e.g. a
work login next to a personal one). Most people have one login and need one server.
Don't offer it during a normal setup.

One bridge = one login. For each extra login, build a separate server. Never reuse the
first folder.

1. **New folder**, named for the account: `BRIDGE2`. Same rules: not a synced folder.
2. **Copy server.py and rename the server inside it:**
   `sed -i 's/^mcp = MCPServer("claude-ai")/mcp = MCPServer("claude-ai-<name>")/' BRIDGE2/server.py`
   Then grep to confirm the line changed.
3. **Own venv** in BRIDGE2 (Step 2). Don't point it at the first bridge's venv; deleting
   one folder would break the other.
4. **Register with a name:** `register.py BRIDGE2 claude-ai-<name>`.
   ⚠️ Without the second argument, register.py writes `claude-ai` and **overwrites the
   first server's entry** (fix: rerun
   `register.py BRIDGE claude-ai`). After registering, print both entries' `args` from
   `~/.claude.json` and confirm each points at its own folder.
5. **The user exports cookies from a Chrome profile signed in to the second account**
   (Step 4), saved into BRIDGE2. Tell them to use a **separate Chrome profile**: signing
   out of claude.ai in the shared profile to switch accounts invalidates the first
   bridge's cookie. Give the extension link again; it's per profile.
6. Before testing, confirm the file landed and has a sessionKey, without printing it:
   `grep -q $'\tsessionKey\t' "$(ls -t BRIDGE2/*cookies*.txt | head -1)" && echo yes`.
7. Test (Step 5 with `--sync`), then do Step 7 (check the org). A work login is the
   case where the team org usually isn't first.

Tools appear as `mcp__claude-ai-<name>__*` in sessions started after registration.

## Tools it provides

| Tool | Does |
|---|---|
| `list_orgs` | Orgs the cookie sees, and which is in use |
| `list_chats(limit, offset, title_contains)` | Chats newest first, with URLs |
| `get_chat(uuid, max_chars)` | Full transcript, speaker and time per message |
| `sync_chats(full)` | Downloads changed chats into BRIDGE/cache.sqlite (FTS5) |
| `search_chats(query, limit)` | Full-text search of the synced chats (words, "phrase", OR, NOT, prefix*) |
| `list_projects` / `get_project(uuid)` | Projects, their instructions and knowledge docs |
| `get_memory` | The account's claude.ai memory |
| `api_get(path)` | Raw GET; `{org}` is replaced with the org uuid |

To find a past chat: `sync_chats` → `search_chats` with several word groups →
`get_chat` on the hits.

## Troubleshooting

| Symptom | Fix |
|---|---|
| "No sessionKey" | No `*cookies*.txt` in BRIDGE with a claude.ai sessionKey, and `.env` still says PASTE_HERE. Check the file's save time with `ls -la`; the user may have saved it elsewhere or exported the wrong site. |
| 401 / 403 | Cookie expired or signed out. The user exports a fresh cookies.txt into BRIDGE (newest wins). No restart needed if the server hasn't loaded a session yet; otherwise restart the session. |
| Tools missing in Claude Code | The session started before registration: open a new one. Confirm `~/.claude.json` has `mcpServers.claude-ai` and that the paths exist. |
| Wrong org (no chats, or only a few on a Team login) | Step 7: set `CLAUDE_ORG_ID` in `.env`, delete `cache.sqlite`, resync. |
| Second server's tools missing, or the first server now shows the second account | register.py ran without a name and overwrote `claude-ai`. Rerun it for each folder with its own name. |
| An endpoint 404s | claude.ai changed its private API. Probe with `api_get` (e.g. `/api/organizations/{org}/...`), then fix server.py. |
| `No module named mcp.server.fastmcp` | mcp 2.x: use `from mcp.server.mcpserver import MCPServer`. |

## Security notes for the user

- The cookies.txt and `.env` files are a full login. Keep BRIDGE out of synced
  folders (OneDrive, Google Drive), never commit it, and delete old exports.
- Signing out of claude.ai in Chrome invalidates the cookie, which is a quick way to
  revoke the bridge.
