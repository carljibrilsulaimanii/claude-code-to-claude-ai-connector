<!--
  README.md -- claude-code-to-claude-ai-connector
  Author:  Jibril Sulaiman (with Claude Code)
  Date:    2026-11-25
  What:    Setup guide for a local MCP server that lets Claude Code read your claude.ai
           chats, projects and memory, plus the Claude Code skill that installs it.
  Why:     claude.ai has no API for your own chat history, so Claude Code could only
           reach it by driving a browser.
-->

# Claude Code to claude.ai connector

A small local MCP server, `claude-ai`, that gives Claude Code read access to your own
claude.ai **chats, projects and memory**. You sign in by exporting your claude.ai cookies
with a Chrome extension. A Claude Code skill in this repo walks Claude through setup,
testing and repair.

> ⚠️ **Unofficial.** This calls claude.ai's private web API, the same one the claude.ai
> website uses. Anthropic doesn't document or support it for this. It can change or
> break without notice, the cookie expires, and automated use may conflict with
> claude.ai's Terms. Use it only on your own account, read-only, and at your own risk.

## Why it exists

You want Claude Code to answer "find the chat where I worked out X" or "use the
instructions from my Y project". Here is what's available without this repo:

1. **There's no claude.ai API for your own data.** The Anthropic API runs models; it can't
   list your claude.ai conversations, projects or memory.
2. **The official data export works but goes stale.** *Settings → Privacy → Export data*
   emails a zip. It's a snapshot, so every new chat means another export.
3. **Browser automation is slow.** Claude in Chrome can open claude.ai and read chats one
   screen at a time. That costs many tool calls and tokens for each search.
4. **claude.ai connectors run the other way.** They let claude.ai reach your tools (Drive,
   Gmail). Nothing lets Claude Code reach claude.ai.

This connector makes claude.ai a live, searchable source in Claude Code: one tool call
lists chats, and a local full-text index searches all of them in milliseconds.

## How it works

```
Chrome ──(Get cookies.txt LOCALLY: Export As)──► BRIDGE/claude.ai_cookies.txt
                                                       │ read at startup
Claude Code ◄──stdio MCP──► server.py ──HTTPS (Chrome TLS fingerprint)──► claude.ai/api/...
                               │
                               └── cache.sqlite (FTS5 index of synced chats)
```

`server.py` loads the claude.ai cookies from the newest `*cookies*.txt` in its folder and
calls claude.ai with a Chrome-like TLS fingerprint through `curl_cffi`. It serves the
results to Claude Code as MCP tools. `sync_chats` copies changed chats into a local
SQLite full-text index, and `search_chats` searches that index.

## What's in this repo

| Path | What it is | Where it goes |
|---|---|---|
| [`claude-ai-connector/`](claude-ai-connector/) | The Claude Code skill: [`SKILL.md`](claude-ai-connector/SKILL.md) and its scripts | Copy to `~/.claude/skills/claude-ai-connector/` |
| [`claude-ai-connector/scripts/`](claude-ai-connector/scripts/) | The MCP server, the registration script and the smoke test | `server.py` is copied into your bridge folder |
| [`requirements.txt`](requirements.txt) | Python packages | Installed into the bridge's virtual environment |
| [`.env.example`](.env.example) | Optional settings (manual cookie, org override) | Copied to `BRIDGE/.env` if you need it |
| [`.gitignore`](.gitignore) | Keeps cookies, `.env` and the chat cache out of git | Repo root |

## Table of contents

- [Prerequisites and dependencies](#prerequisites-and-dependencies)
- [Step 1: Install the Chrome extension](#step-1-install-the-chrome-extension)
- [Step 2: Build the server](#step-2-build-the-server)
- [Step 3: Register it with Claude Code](#step-3-register-it-with-claude-code)
- [Step 4: Export your claude.ai cookies](#step-4-export-your-claudeai-cookies)
- [Step 5: Test it](#step-5-test-it)
- [Step 6: Restart and use it](#step-6-restart-and-use-it)
- [Step 7 (optional): Install the skill](#step-7-optional-install-the-skill)
- [Step 8 (optional): Add a second claude.ai login](#step-8-optional-add-a-second-claudeai-login)
- [Tools](#tools)
- [Refreshing an expired cookie](#refreshing-an-expired-cookie)
- [What happens if you sign out](#what-happens-if-you-sign-out)
- [Troubleshooting](#troubleshooting)
- [Limits](#limits)
- [Security](#security)

## Prerequisites and dependencies

**Accounts and plans**

| What | Version or plan | Why | Check it's ready |
|---|---|---|---|
| claude.ai account | Any plan with chats; tested on Max | The data source | You can open https://claude.ai signed in |
| Claude Code | Desktop app or CLI | Runs the MCP server and its tools | `claude --version`, or the Code tab in the desktop app |

**Tools**

| What | Version | Why | Check it's ready |
|---|---|---|---|
| Python | 3.10+ (tested 3.13) | Runs the server | `python --version` |
| `mcp` package | 2.x (`mcp[cli]`) | MCP server SDK. 2.x renamed `FastMCP` to `MCPServer` | Installed in Step 2 |
| `curl_cffi` | 0.17+ | HTTPS with a Chrome TLS fingerprint. Plain `requests` is blocked by Cloudflare on claude.ai | Installed in Step 2 |
| Google Chrome | Current | Where you're signed in to claude.ai | — |
| **Get cookies.txt LOCALLY** extension | Current | Exports your claude.ai cookies to a file without uploading them anywhere | Its icon in the Chrome toolbar |
| Git | Any | Clone this repo | `git --version` |

**Permissions and secrets**

| What | Why | Notes |
|---|---|---|
| Your claude.ai cookies (`sessionKey` and the rest) | The only sign-in the private API accepts | It's a full login. You export it yourself; it stays in your bridge folder. |
| Write access to `~/.claude.json` | Registers the MCP server at user scope | `register.py` backs it up first |

**Claude Code integrations**

| What | Used for | Can't do | Check |
|---|---|---|---|
| The `claude-ai` MCP server (this repo) | Reading chats, projects and memory | Write anything to claude.ai. Every tool is a read (GET) | ToolSearch `+claude-ai` in a new session lists 9 tools |
| The `claude-ai-connector` skill (optional) | Lets Claude run Steps 2, 3 and 5 and fix problems | Export your cookies. It's written never to touch them | Appears in the skills list |

You can do the whole setup by hand without the skill.

## Step 1: Install the Chrome extension

About 2 minutes.

**1a.** In Chrome, open **Get cookies.txt LOCALLY** in the Chrome Web Store:
https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc
Click **Add to Chrome**.

Extensions are per Chrome profile. Install it in the profile that's signed in to
claude.ai.

> ⚠️ **Don't install the older extension named just "Get cookies.txt".** Google removed
> it from the store for sending people's cookies to an outside server. The "LOCALLY" one
> is open source and saves to your disk only.

**1b.** Click the puzzle-piece icon in the toolbar and pin the extension.

✅ **Check:** the extension's icon sits in the toolbar.

## Step 2: Build the server

About 5 minutes. Pick a folder for the bridge, called BRIDGE from here on, e.g.
`C:\Users\you\claude-ai-bridge`. Keep it **out of** OneDrive, Google Drive and Dropbox,
because it will hold your login.

**2a.** Clone this repo and copy the server in:

```powershell
git clone https://github.com/carljibrilsulaimanii/claude-code-to-claude-ai-connector
New-Item -ItemType Directory -Force $HOME\claude-ai-bridge
Copy-Item claude-code-to-claude-ai-connector\claude-ai-connector\scripts\server.py $HOME\claude-ai-bridge\
```

Copies [`claude-ai-connector/scripts/server.py`](claude-ai-connector/scripts/server.py).

**2b.** Create a virtual environment and install the packages from
[`requirements.txt`](requirements.txt):

```powershell
python -m venv $HOME\claude-ai-bridge\.venv
& $HOME\claude-ai-bridge\.venv\Scripts\python.exe -m pip install -r claude-code-to-claude-ai-connector\requirements.txt
```

On macOS or Linux the Python is `~/claude-ai-bridge/.venv/bin/python`.

> ⚠️ **`No module named 'mcp.server.fastmcp'`** means you have `mcp` 2.x and old code. This
> repo's server already uses the 2.x import (`from mcp.server.mcpserver import MCPServer`).
> If you pin `mcp<2`, change it back to `from mcp.server.fastmcp import FastMCP`.

✅ **Check:** this prints `ok`:

```powershell
& $HOME\claude-ai-bridge\.venv\Scripts\python.exe -c "import mcp, curl_cffi; print('ok')"
```

## Step 3: Register it with Claude Code

About 1 minute.

**3a.** Run [`claude-ai-connector/scripts/register.py`](claude-ai-connector/scripts/register.py)
with the bridge folder:

```powershell
& $HOME\claude-ai-bridge\.venv\Scripts\python.exe claude-code-to-claude-ai-connector\claude-ai-connector\scripts\register.py $HOME\claude-ai-bridge
```

It backs up `~/.claude.json` to `~/.claude.json.bak-claude-ai-bridge`, then adds a
user-scope `mcpServers.claude-ai` entry that runs the venv Python on `server.py`.
Success looks like:

```
Registered claude-ai -> C:\Users\you\claude-ai-bridge\.venv\Scripts\python.exe C:\Users\you\claude-ai-bridge\server.py
User MCP servers: [..., 'claude-ai']
```

If the `claude` CLI is on your PATH, this does the same thing:

```powershell
claude mcp add --scope user claude-ai -- $HOME\claude-ai-bridge\.venv\Scripts\python.exe $HOME\claude-ai-bridge\server.py
```

> ⚠️ **Inline Python in PowerShell loses its quotes.** `python -c @'...'@` with
> `"~/.claude.json"` inside arrives as `~/.claude.json` and fails with a syntax error.
> Use the script file, not an inline one-liner.

✅ **Check:** `~/.claude.json` has a `"claude-ai"` key under `"mcpServers"`.

## Step 4: Export your claude.ai cookies

About 1 minute. **You** do this step. Don't ask Claude to copy the cookie for you.

**4a.** Open https://claude.ai in Chrome, signed in.

**4b.** Click the **Get cookies.txt LOCALLY** icon. A panel opens titled
**Get cookies.txt for https://claude.ai/...**, with a table of claude.ai cookies
(including `sessionKey`).

**4c.** Leave **Export Format:** on **Netscape**. Click **Export As**, not **Export**, so
you can choose the folder.

**4d.** Save into BRIDGE. The name must contain `cookies` and end in `.txt`, e.g.
`claude.ai_cookies.txt`.

The server reads the **newest** `*cookies*.txt` in BRIDGE and sends every claude.ai cookie
in it. Sending the full set looks more like a real browser than `sessionKey` alone.

> ⚠️ **`document.cookie` won't show it.** `sessionKey` is HttpOnly, so the DevTools
> Console can't read it. To copy it by hand instead of exporting: **F12 → Application →
> Cookies → https://claude.ai**, filter `sessionKey`, copy the **Value** (starts with
> `sk-ant-sid`). Put it in `BRIDGE/.env` as `CLAUDE_SESSION_KEY=...`; see
> [`.env.example`](.env.example). A value in `.env` overrides the file.

> ⚠️ **Save the file.** If you paste into `.env` and the test still says
> *"No sessionKey"*, the file wasn't saved. Check its modified time.

✅ **Check:** `BRIDGE` contains `claude.ai_cookies.txt` with today's time.

## Step 5: Test it

About 2 minutes, plus the first sync.

**5a.** Run [`claude-ai-connector/scripts/test_bridge.py`](claude-ai-connector/scripts/test_bridge.py).
It prints counts and titles, **never cookie values**:

```powershell
& $HOME\claude-ai-bridge\.venv\Scripts\python.exe claude-code-to-claude-ai-connector\claude-ai-connector\scripts\test_bridge.py $HOME\claude-ai-bridge
```

Success looks like this:

```
cookies.txt cookies: 27 | sessionKey present: True
ORG <your org> | in use: True | ['chat', 'claude_max']
CHAT 2026-11-25 <your newest chat title>
...
chats: 147 | projects: 17
memory: {'memory': '**Work context** ... ...
PASS
```

**5b. (Optional)** Build the search index and run a sample search:

```powershell
& $HOME\claude-ai-bridge\.venv\Scripts\python.exe claude-code-to-claude-ai-connector\claude-ai-connector\scripts\test_bridge.py $HOME\claude-ai-bridge --sync --query turkey
```

The first full sync takes about 90 seconds per 150 chats. After that, only changed chats
are downloaded.

| You got | Cause | Fix |
|---|---|---|
| `No sessionKey` | No cookies file in BRIDGE, or `.env` still says `PASTE_HERE` | Redo [Step 4](#step-4-export-your-claudeai-cookies) |
| `claude.ai refused the request (401)` or `(403)` | Cookie expired, or you signed out | Export a fresh cookies file |
| `chats: 0`, or only a few chats on a Team login | It picked the wrong org (see 5c) | Set `CLAUDE_ORG_ID` (5c) |

**5c. Check it's reading the right org.** With no `CLAUDE_ORG_ID`, the server uses the
**first** org that has chats. On a Team or Enterprise login that's often your near-empty
individual org, not the team's. The test prints every org (`ORG ... | in use: True/False`);
Team orgs list `raven` among their capabilities. If the org in use isn't where your chats
are:

1. Get the right org's uuid: in a new Claude Code session, ask Claude to run the
   `list_orgs` tool. It prints each org's name, uuid and capabilities.
2. Copy [`.env.example`](.env.example) to `BRIDGE/.env` (if you haven't) and set
   `CLAUDE_ORG_ID=<uuid>`. Leave `CLAUDE_SESSION_KEY=PASTE_HERE` if you use the cookies
   file.
3. Delete `BRIDGE/cache.sqlite`. It still holds the other org's chats.
4. Rerun 5b with `--sync`.

✅ **Check:** the last line is `PASS`, the org marked `in use: True` is the one you want,
and the chat count matches what you see on claude.ai.

## Step 6: Restart and use it

**6a.** MCP servers load when a session starts. Open a **new** Claude Code session, or fully
quit and reopen the desktop app. A session that was already open won't see the tools.

**6b.** Ask something like *"Search my claude.ai chats for the one about X"*. Claude calls
`sync_chats`, then `search_chats`, then `get_chat`.

✅ **Check:** in the new session the `claude-ai` tools appear (ToolSearch `+claude-ai`).

## Step 7 (optional): Install the skill

Copy [`claude-ai-connector/`](claude-ai-connector/) to `~/.claude/skills/claude-ai-connector/`:

```powershell
Copy-Item -Recurse claude-code-to-claude-ai-connector\claude-ai-connector $HOME\.claude\skills\
```

With the skill installed, Claude can run Steps 2, 3 and 5 for you, rebuild the bridge on a
new computer, and diagnose 401s or missing tools. You still do Steps 1 and 4.

## Step 8 (optional): Add a second claude.ai login

**Skip this unless you sign in to claude.ai with more than one account**, e.g. a work
login next to a personal one. One server reads one login. Each extra login gets its own
server, folder and name. About 10 minutes.

**8a.** Make a second folder, e.g. `$HOME\claude-ai-bridge-work`, and copy
[`claude-ai-connector/scripts/server.py`](claude-ai-connector/scripts/server.py) into it as
in [Step 2](#step-2-build-the-server).

**8b.** Rename the server inside the copy. Open `server.py` in the new folder and change
this line:

```python
mcp = MCPServer("claude-ai")
```

to:

```python
mcp = MCPServer("claude-ai-work")
```

**8c.** Give the folder its own virtual environment (Step 2b, with the new path). Don't
point it at the first bridge's `.venv`; deleting one folder would break the other.

**8d.** Register it **with a name**, the second argument to
[`register.py`](claude-ai-connector/scripts/register.py):

```powershell
& $HOME\claude-ai-bridge-work\.venv\Scripts\python.exe claude-code-to-claude-ai-connector\claude-ai-connector\scripts\register.py $HOME\claude-ai-bridge-work claude-ai-work
```

> ⚠️ **Leave off the name and you overwrite your first server.** Without it, `register.py`
> writes the entry `claude-ai`, which now points at the new folder. Fix it by rerunning
> Step 3 for the first folder, then 8d with the name.

**8e.** Export the second account's cookies ([Step 4](#step-4-export-your-claudeai-cookies))
into the new folder. Use a **separate Chrome profile** signed in to that account, with the
extension installed there too.

> ⚠️ **Don't switch accounts in one profile.** Signing out of claude.ai to sign in as the
> other account cancels the first account's cookie, and the first server stops working.

**8f.** Test the new folder ([Step 5](#step-5-test-it), including 5c; work logins are the
usual case where the team org isn't first), then open a new session.

✅ **Check:** `~/.claude.json` has both `claude-ai` and `claude-ai-work` under
`mcpServers`, each pointing at its own folder, and a new session lists tools for both
(ToolSearch `+claude-ai`).

## Tools

| Tool | Does |
|---|---|
| `list_orgs` | Orgs your cookie can see, and which one is in use |
| `list_chats(limit, offset, title_contains)` | Chats newest first, with links |
| `get_chat(uuid, max_chars)` | A full transcript with speaker and time per message, including tool calls and attachment text |
| `sync_chats(full)` | Downloads changed chats into `BRIDGE/cache.sqlite` |
| `search_chats(query, limit)` | Full-text search of synced chats: words, `"exact phrase"`, `OR`, `NOT`, `prefix*` |
| `list_projects` | Projects with descriptions and dates |
| `get_project(uuid, include_docs)` | A project's custom instructions and knowledge docs |
| `get_memory` | Your claude.ai memory |
| `api_get(path)` | Raw GET for any other `/api/...` endpoint. `{org}` is filled in |

## Refreshing an expired cookie

When a tool says the request was refused (401/403), export the cookies again
([Step 4](#step-4-export-your-claudeai-cookies)) into BRIDGE, then start a new session.
The newest file wins, so you can delete the old one.

## What happens if you sign out

Signing out of claude.ai ends that login on claude.ai's side. The exported cookies file
is a copy of that login, so it stops working too, even though it's still in BRIDGE.

| | After you sign out |
|---|---|
| `list_chats`, `get_chat`, `sync_chats`, `list_projects`, `get_project`, `get_memory`, `api_get` | Fail with *claude.ai refused the request (401)* or *(403)* |
| `search_chats` | **Still works** on chats already synced. It reads only the local index (`BRIDGE/cache.sqlite`), so it finds nothing newer than the last sync |

**To turn it back on:**

1. Sign back in to claude.ai in the same Chrome profile.
2. Export the cookies again ([Step 4](#step-4-export-your-claudeai-cookies)) into the same
   BRIDGE folder. The newest file wins; delete the old one.
3. Start a new Claude Code session. The server keeps the cookie it loaded at startup, so a
   session that's already open still uses the dead one.

**What doesn't turn it off:**

- Closing Chrome or shutting down the computer. That doesn't sign you out, so the cookie
  keeps working until claude.ai expires it on its own.
- Signing out of a different claude.ai account. With two servers
  ([Step 8](#step-8-optional-add-a-second-claudeai-login)), each stops only when its own
  account signs out. That's why each login gets its own Chrome profile: switching accounts
  in one profile signs the other one out.

**Signing out on purpose** is the quickest way to cut off a cookies file that was shared or
copied by mistake. **Log out of all devices** in claude.ai's settings does it for every copy
at once. See also [Security](#security).

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Tools missing in Claude Code | The session started before registration | [Step 6](#step-6-restart-and-use-it) |
| Tools missing in a **new** session | Wrong paths in `~/.claude.json` | Rerun [Step 3](#step-3-register-it-with-claude-code); check that the venv Python and `server.py` exist |
| `No sessionKey` | Cookie file missing or misnamed, or `.env` unsaved | [Step 4](#step-4-export-your-claudeai-cookies) |
| 401 / 403 | Cookie expired or signed out | [Refreshing an expired cookie](#refreshing-an-expired-cookie) |
| 401 / 403 right after you signed out, but search still finds old chats | Sign-out ended the login; search reads the local index | [What happens if you sign out](#what-happens-if-you-sign-out) |
| 403 with a Cloudflare page while the cookie is fresh | The request didn't look like a browser | Keep `curl_cffi` with `impersonate="chrome"`; update `curl_cffi` |
| An endpoint returns 404 | claude.ai changed its private API | Probe with `api_get`, then update `server.py` |
| `get_memory` returns `No memory endpoint answered` | Memory moved, or is off for the account | Check memory is on in claude.ai settings; probe with `api_get` |
| `No module named 'mcp.server.fastmcp'` | `mcp` 2.x | See [Step 2](#step-2-build-the-server) |
| Only a few chats on a Team login | It's reading your individual org | [Step 5c](#step-5-test-it) |
| Your first server now shows the second account's chats | `register.py` ran without a name for the second login | Rerun [Step 3](#step-3-register-it-with-claude-code), then [8d](#step-8-optional-add-a-second-claudeai-login) with a name |

## Limits

- **Read-only.** No tool creates, edits or deletes anything on claude.ai.
- **One login and one org per server.** By default it uses the first org with the `chat`
  capability; set `CLAUDE_ORG_ID` to choose ([Step 5c](#step-5-test-it)). A second login
  needs a second server ([Step 8](#step-8-optional-add-a-second-claudeai-login)).
- **Search covers synced chats only.** Run `sync_chats` first. Chats deleted on claude.ai
  stay in the local index until you delete `cache.sqlite`.
- **Unofficial endpoints** (`/api/organizations`, `.../chat_conversations`, `.../projects`,
  `.../projects/{id}/docs`, `.../memory`) can change at any time.
- `get_chat` truncates at `max_chars` (default 60,000); raise it for very long chats.

## Security

- **The cookies file and `.env` are a full claude.ai login.** Anyone with them can use your
  account. Keep BRIDGE out of synced folders and git. This repo's
  [`.gitignore`](.gitignore) excludes `*cookies*.txt`, `.env` and `cache.sqlite`.
- `cache.sqlite` holds the text of every synced chat. Treat it like the chats themselves.
- **To revoke access**, sign out of claude.ai in that browser. The exported cookie stops
  working.
- The skill tells Claude never to read, print, copy or type the cookie. The test script
  prints only whether one is present.

Built by [Jibril Sulaiman](https://github.com/carljibrilsulaimanii).
