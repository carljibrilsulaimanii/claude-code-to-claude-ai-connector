"""Smoke-test the claude-ai bridge without printing any cookie values.
Usage: python test_bridge.py <BRIDGE folder> [--sync] [--query WORD]"""
import sys, time
from pathlib import Path

args = sys.argv[1:]
bridge = Path(next((a for a in args if not a.startswith("--")), "."))
sys.path.insert(0, str(bridge))
import server  # noqa: E402

jar = server.cookies_from_file()
print("cookies.txt cookies:", len(jar), "| sessionKey present:", bool(jar.get("sessionKey")))
try:
    for o in server.list_orgs():
        print("ORG", o["name"], "| in use:", o["in_use"], "|", o["capabilities"])
    for c in server.list_chats(limit=3):
        print("CHAT", c["updated_at"][:10], c["name"])
    print("chats:", len(server.list_chats(limit=10**6)), "| projects:", len(server.list_projects()))
    print("memory:", str(server.get_memory())[:200].replace("\n", " "), "...")
    if "--sync" in args:
        t = time.time()
        print(server.sync_chats(), f"({round(time.time() - t)}s)")
        q = args[args.index("--query") + 1] if "--query" in args else "the"
        for r in server.search_chats(q, limit=3):
            print("HIT", r["name"])
    print("PASS")
except Exception as e:
    print("FAIL", type(e).__name__, str(e)[:500])
    sys.exit(1)
