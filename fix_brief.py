"""One-time fix (2026-11-08): removes the empty news-brief edition that hides the refresh button.
Backs up world.db first and touches nothing unless the saved edition really has no stories."""
import json, os, sqlite3, sys

here = os.path.dirname(os.path.abspath(__file__))
db = os.path.join(here, "World", "world.db")
bak = os.path.join(here, "World", "world.db.bak-2026-11-08")

if not os.path.exists(db):
    sys.exit("Can't find World\\world.db next to this script. Nothing was changed.")

con = sqlite3.connect(db, timeout=30)
row = con.execute("SELECT value FROM kv WHERE key='news_edition'").fetchone()
if not row:
    sys.exit("There's no saved edition at all, so there's nothing to remove. Nothing was changed.")
ed = json.loads(row[0])
n = len(ed.get("global") or []) + len(ed.get("home") or [])
print(f"Saved edition: day {ed.get('day')}, kind {ed.get('kind')}, {n} stories.")
if n:
    sys.exit("This edition has stories in it, so it isn't the broken one. Nothing was changed.")

if not os.path.exists(bak):
    print("Backing up world.db ...")
    out = sqlite3.connect(bak)
    con.backup(out)
    out.close()
print("Backup:", bak)

con.execute("DELETE FROM kv WHERE key='news_edition'")
con.commit()
left = con.execute("SELECT COUNT(*) FROM kv WHERE key='news_edition'").fetchone()[0]
con.close()
print("Removed the empty edition." if left == 0 else "Something went wrong; the backup is untouched.")
