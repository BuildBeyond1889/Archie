"""
lite_world.py - World on the laptop (1.3): news and governments, the way Feather does it.

  * The snapshot (data\\world\\snapshot.json.gz) comes from Archie World on your PC when they sync:
    every story from the last 3 days, the news feed list, and every country's leaders and cabinet.
  * Refresh pulls the same news feeds live, from this laptop (anywhere with internet), and groups
    matching headlines. Nothing here needs the PC.
  * Flags are fetched from the PC the first time each one is shown, then kept.
"""
import email.utils
import gzip
import html
import json
import os
import re
import threading
import time
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor

_snap = {"mtime": 0, "data": None}
_live = {"at": 0, "items": [], "state": "idle", "ok": 0, "failed": 0}
_lock = threading.Lock()
WDIR = SNAP = LIVE = FLAGS = None


def setup(data_dir):
    global WDIR, SNAP, LIVE, FLAGS
    WDIR = os.path.join(data_dir, "world")
    SNAP = os.path.join(WDIR, "snapshot.json.gz")
    LIVE = os.path.join(WDIR, "live.json")
    FLAGS = os.path.join(WDIR, "flags")
    os.makedirs(FLAGS, exist_ok=True)


def snapshot():
    try:
        m = os.path.getmtime(SNAP)
    except (OSError, TypeError):
        return None
    if m != _snap["mtime"]:
        try:
            with gzip.open(SNAP, "rt", encoding="utf-8") as f:
                _snap["data"] = json.load(f)
            _snap["mtime"] = m
        except (OSError, ValueError, EOFError):
            return _snap["data"]
    return _snap["data"]


def save_pack(raw_gz):
    """A pack from the PC. Without governments in it, the ones already here are kept."""
    new = json.loads(gzip.decompress(raw_gz).decode("utf-8"))
    old = snapshot() or {}
    if "govs" not in new and old.get("govs"):
        new["govs"], new["govs_at"] = old["govs"], old.get("govs_at", old.get("at"))
    elif "govs" in new:
        new["govs_at"] = new.get("at")
    tmp = SNAP + ".tmp"
    with gzip.open(tmp, "wt", encoding="utf-8") as f:
        json.dump(new, f, ensure_ascii=False)
    os.replace(tmp, SNAP)
    return new


def ages():
    s = snapshot() or {}
    now = time.time()
    return (now - s["at"]) if s.get("at") else None, (now - s["govs_at"]) if s.get("govs_at") else None


def _load_live():
    if not _live["at"] and LIVE and os.path.exists(LIVE):
        try:
            with open(LIVE, encoding="utf-8") as f:
                _live.update(json.load(f))
            _live["state"] = "idle"
        except Exception:
            pass


# ---------- live feeds (same as Feather) ----------
def _txt(el, *names):
    for n in names:
        x = el.find(n)
        if x is not None and (x.text or "").strip():
            return x.text.strip()
    return ""


def _strip(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


def _date(s):
    if not s:
        return 0
    try:
        return int(email.utils.parsedate_to_datetime(s).timestamp())
    except Exception:
        pass
    try:
        from datetime import datetime
        return int(datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp())
    except Exception:
        return 0


def parse_feed(text):
    text = re.sub(r"^[^<]+", "", text)
    root = ET.fromstring(text.encode("utf-8"))
    A, R, DC = "{http://www.w3.org/2005/Atom}", "{http://purl.org/rss/1.0/}", "{http://purl.org/dc/elements/1.1/}"
    out = []
    for it in list(root.iter("item")) or list(root.iter(R + "item")):
        out.append({"title": _strip(_txt(it, "title", R + "title")), "url": _txt(it, "link", R + "link", "guid"),
                    "t": _date(_txt(it, "pubDate", DC + "date")), "summary": _strip(_txt(it, "description", R + "description"))[:300]})
    if not out:
        for en in root.iter(A + "entry"):
            link = next((l.get("href", "") for l in en.findall(A + "link") if l.get("rel", "alternate") == "alternate"), "")
            out.append({"title": _strip(_txt(en, A + "title")), "url": link, "t": _date(_txt(en, A + "published", A + "updated")),
                        "summary": _strip(_txt(en, A + "summary", A + "content"))[:300]})
    return [o for o in out if o["title"]]


def _pull(src):
    req = urllib.request.Request(src["url"], headers={"User-Agent": "Mozilla/5.0 (Archie Lite)"})
    with urllib.request.urlopen(req, timeout=12) as r:
        items = parse_feed(r.read().decode("utf-8", "ignore"))
    for i in items:
        i["source"] = src.get("name", "")
    return items


def _safe(s):
    try:
        return _pull(s)
    except Exception:
        return None


def refresh(on_done=lambda: None):
    """Pull the feeds live in the background. Returns at once; poll news()."""
    sources = [s for s in (snapshot() or {}).get("sources", []) if s.get("url")]
    if not sources or _live["state"] == "pulling":
        return False

    def run():
        _live["state"] = "pulling"
        got, ok, bad = [], 0, 0
        try:
            with ThreadPoolExecutor(8) as ex:
                for res in ex.map(_safe, sources):
                    if res is None:
                        bad += 1
                    else:
                        ok += 1
                        got += res
            cut = time.time() - 48 * 3600
            got = [g for g in got if not g["t"] or g["t"] > cut]
            with _lock:
                _live.update({"at": int(time.time()), "items": got, "state": "done", "ok": ok, "failed": bad})
            with open(LIVE + ".tmp", "w", encoding="utf-8") as f:
                json.dump({k: _live[k] for k in ("at", "items", "ok", "failed")}, f)
            os.replace(LIVE + ".tmp", LIVE)
        except Exception:
            _live["state"] = "done"
        on_done()
    threading.Thread(target=run, daemon=True, name="lite-news").start()
    return True


# ---------- grouping (same as Feather) ----------
STOP = set("the a an and or of to in on at for with from by as is are was were be after over amid says say said new us".split())


def toks(t):
    return {w for w in re.findall(r"[a-z0-9']{3,}", t.lower()) if w not in STOP}


def group(items):
    """Headlines that share most of their words become one story; more sources = ranked higher."""
    stories = []
    for it in sorted(items, key=lambda x: -(x["t"] or 0)):
        tk = toks(it["title"])
        best, bs = None, 0.0
        for s in stories:
            j = len(tk & s["tk"]) / (len(tk | s["tk"]) or 1)
            if j > bs:
                best, bs = s, j
        if best and bs >= 0.3:
            if it["source"] not in {x["source"] for x in best["items"]}:
                best["items"].append(it)
            best["tk"] |= tk
        else:
            stories.append({"title": it["title"], "t": it["t"], "items": [it], "tk": set(tk)})
    for s in stories:
        s["n"] = len(s["items"])
        del s["tk"]
    stories.sort(key=lambda s: (-min(s["n"], 6), -(s["t"] or 0)))
    return stories


def news(region=""):
    _load_live()
    snap = snapshot() or {}
    pc = snap.get("stories", [])
    if region:
        pc = [s for s in pc if (s.get("region") or "") == region]
    return {"pc": pc[:150], "pc_at": snap.get("at", 0), "regions": sorted({s.get("region") for s in snap.get("stories", []) if s.get("region")}),
            "live": group(_live["items"])[:80] if _live["items"] else [], "live_at": _live["at"], "state": _live["state"],
            "ok": _live["ok"], "failed": _live["failed"], "has_sources": bool(snap.get("sources"))}


def govs():
    snap = snapshot() or {}
    L = [{k: c.get(k) for k in ("iso2", "name", "label")} | {"leaders": " ".join(p.get("name", "") for p in (c.get("hos") or []) + (c.get("hog") or []))}
         for c in snap.get("govs", []) if c.get("name")]
    return {"at": snap.get("govs_at", 0), "list": sorted(L, key=lambda c: c["name"].lower())}


def country(iso):
    for c in (snapshot() or {}).get("govs", []):
        if c.get("iso2") == iso:
            return c
    return None


def flag_path(iso):
    return os.path.join(FLAGS, iso + ".svg") if re.fullmatch(r"[A-Z]{2}", iso or "") else None
