"""
lite_core.py - Archie Lite's data and syncing (no windows here, so it can be tested anywhere).

  * Everything you see lives in data\\lite.json on this laptop, so it all works offline.
  * Every change you make is applied right away AND queued as one small change (add this entry,
    tick that task...). When the PC is reachable on your Wi-Fi, the queue goes over, the PC applies
    each change on its own, and sends back a fresh copy of everything.
  * Changes still waiting are re-applied on top of that fresh copy, so nothing you did disappears.
  * Updates (2026-11-09): the PC lists its Archie Lite files on every sync. If any differ from
    this laptop's, they're fetched (encrypted, checked by hash) into data\\update and installed
    by lite.py the next time the panel is closed. The old files go to data\\update_backup.
  * Notes and drops (v1.2): notes you type and files you drop are saved on this laptop
    (Documents\\Archie Lite) and sent to the PC in encrypted pieces, where they go into Obsidian.
    Saved articles are kept here as text for reading offline. Chat questions asked while the PC
    can't be reached wait here and are answered at the next sync.
"""

import base64
import copy
import datetime
import hashlib
import py_compile
import shutil
import json
import os
import re
import socket
import threading
import time
import urllib.error
import urllib.request

import lite_cal
import lite_proto as proto
import lite_world

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
STORE = os.path.join(DATA, "lite.json")
PAIRING = os.path.join(DATA, "pairing.json")
VERSION = "1.4.5"
UPDATE_DIRS = ("app", "web")
UPDATE_EXT = (".py", ".png", ".html", ".css", ".js", ".ttf", ".txt", ".ico", ".svg", ".json")
SYNC_EVERY = 120          # seconds between syncs while the PC is reachable
SYNC_BATTERY = 600        # ...and while running on battery
CHUNK = 2 * 1024 * 1024   # dropped files travel in 2 MB pieces
MAX_DROP = 1024 * 1024 * 1024
AUTO = object()            # drop_file: file it under the class picked in the panel, else the class on now
REC_STALE = 300            # a recording with no word from the panel for this long is saved as it is
RETRY = ("file_drop", "note_save")   # changes the PC couldn't apply yet are tried again (5 times)
CLASS_KINDS = ("class", "lab")
RETRY_AWAY = 300          # seconds between tries while away from home

EMPTY = {"calendar": [], "tasks": [], "deadlines": [], "brief": None, "saved": [], "follow": [], "at": None,
         "pc": None, "model": None}


def manifest(root=ROOT):
    """Same rules as lite_manifest() in archie_sync.py on the PC."""
    out = {}
    for top in UPDATE_DIRS:
        for dirpath, dirs, files in os.walk(os.path.join(root, top)):
            dirs[:] = [d for d in dirs if not d.startswith((".", "__"))]
            for fn in files:
                if not fn.lower().endswith(UPDATE_EXT) or fn.startswith("."):
                    continue
                full = os.path.join(dirpath, fn)
                try:
                    with open(full, "rb") as f:
                        out[os.path.relpath(full, root).replace(os.sep, "/")] = hashlib.sha256(f.read()).hexdigest()
                except OSError:
                    pass
    return out


def safe_rel(rel):
    parts = str(rel).split("/")
    return (len(parts) >= 2 and parts[0] in UPDATE_DIRS and all(p and p not in (".", "..") and ":" not in p
            and "\\" not in p for p in parts) and rel.lower().endswith(UPDATE_EXT))


def on_battery():
    """True when a Windows laptop is running on battery."""
    if os.name != "nt":
        return False
    try:
        import ctypes

        class PS(ctypes.Structure):
            _fields_ = [("ac", ctypes.c_ubyte), ("flag", ctypes.c_ubyte), ("pct", ctypes.c_ubyte),
                        ("saver", ctypes.c_ubyte), ("life", ctypes.c_ulong), ("full", ctypes.c_ulong)]
        ps = PS()
        if ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(ps)):
            return ps.ac == 0
    except Exception:
        pass
    return False


def safe_name(s, fallback="Note"):
    import re
    s = re.sub(r'[<>:"/\\|?*#^\[\]\x00-\x1f]', " ", str(s or "")).strip(" .")
    return re.sub(r"\s{2,}", " ", s)[:80] or fallback


def unique_path(path):
    stem, ext = os.path.splitext(path)
    n = 2
    while os.path.exists(path):
        path = f"{stem} ({n}){ext}"
        n += 1
    return path


class _MemCal(lite_cal.Calendar):
    """Archie's calendar logic (weekly classes etc.) over the laptop's copy."""
    def __init__(self, events):
        self.events = events

    def load(self):
        return list(self.events)


def occurrences(events, start, end):
    try:
        return _MemCal(events).between(start, end)
    except Exception:
        return []


def at(e):
    """datetime an occurrence starts, or None if it has no time."""
    if not e.get("time"):
        return None
    try:
        h, m = map(int, e["time"].split(":"))
        return datetime.datetime.combine(datetime.date.fromisoformat(e["date"]), datetime.time(h, m))
    except (ValueError, KeyError):
        return None


def new_id():
    return os.urandom(5).hex()


def apply_local(snap, op):
    """Show a change at once, before the PC has it. Returns the snapshot (changed in place)."""
    t = op["type"]
    if t == "cal_add":
        if not any(e["id"] == op["id"] for e in snap["calendar"]):
            snap["calendar"].append(dict(op["item"], id=op["id"]))
    elif t == "cal_edit":
        for e in snap["calendar"]:
            if e["id"] == op["id"]:
                e.update(op["item"])
    elif t == "cal_del":
        snap["calendar"] = [e for e in snap["calendar"] if e["id"] != op["id"]]
    elif t == "task_add":
        if not any(x["text"].lower() == op["text"].lower() and not x["done"] for x in snap["tasks"]):
            snap["tasks"].append({"text": op["text"], "done": False, "due": op.get("due")})
    elif t == "task_done":
        for x in snap["tasks"]:
            if x["text"].lower() == op["text"].lower():
                x["done"] = bool(op["done"])
                break
    elif t == "deadline_add":
        snap["deadlines"].append({"date": op["date"], "what": op["what"]})
        snap["deadlines"].sort(key=lambda d: d["date"])
    elif t == "follow_add":
        if op["topic"].lower() not in [f.lower() for f in snap["follow"]]:
            snap["follow"].append(op["topic"])
    elif t == "follow_remove":
        snap["follow"] = [f for f in snap["follow"] if f.lower() != op["topic"].lower()]
    elif t == "save_story":
        if not any(s.get("name") == op["title"] for s in snap["saved"]):
            snap["saved"].insert(0, {"name": op["title"], "time": int(time.time()), "pending": True})
    return snap


class Lite:
    def __init__(self, data_dir=DATA):
        self.data_dir = data_dir
        self.store_path = os.path.join(data_dir, "lite.json")
        self.pair_path = os.path.join(data_dir, "pairing.json")
        os.makedirs(data_dir, exist_ok=True)
        self.lock = threading.RLock()
        self.wake = threading.Event()
        self.stop = threading.Event()
        self.d = self._load()
        self.pair = self._load_pair()
        self.opener = proto.Opener(self.pair["key"]) if self.pair else None
        self.status = {"state": "starting", "pc": None, "addr": None, "at": None, "msg": ""}
        self.on_change = lambda: None
        self.on_answer = lambda text: None
        self.on_mail = lambda alert: None
        self.battery = False
        self.root = os.path.dirname(os.path.abspath(data_dir))
        self.art_dir = os.path.join(data_dir, "articles")
        lite_world.setup(data_dir)
        self.update_dir = os.path.join(data_dir, "update")

    # ----- storage -------------------------------------------------------------------------
    def _load(self):
        try:
            with open(self.store_path, encoding="utf-8") as f:
                d = json.load(f)
        except (OSError, ValueError):
            d = {}
        d.setdefault("snapshot", copy.deepcopy(EMPTY))
        d.setdefault("pending", [])
        d.setdefault("last_ok", None)
        d.setdefault("addr", None)
        # 1.1 kept the PC's sync notes under "notes" (a list); 1.2 keeps your notes there (a dict)
        for key, kind in (("settings", dict), ("notes", dict), ("chat", list), ("articles", dict), ("drops", list),
                          ("notified", dict), ("pending", list)):
            if not isinstance(d.get(key), kind):
                d[key] = kind()
        for k, v in EMPTY.items():
            d["snapshot"].setdefault(k, copy.deepcopy(v))
        return d

    def save(self):
        with self.lock:
            tmp = self.store_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.d, f, ensure_ascii=False)
            os.replace(tmp, self.store_path)

    def _load_pair(self):
        try:
            with open(self.pair_path, encoding="utf-8") as f:
                p = json.load(f)
            return p if p.get("key") else None
        except (OSError, ValueError):
            return None

    def setting(self, key, default=None):
        return self.d["settings"].get(key, default)

    def set_setting(self, key, value):
        with self.lock:
            self.d["settings"][key] = value
            self.save()

    # ----- what the page sees ---------------------------------------------------------------
    def view(self):
        with self.lock:
            notes = sorted(self.d["notes"].values(), key=lambda n: -n.get("updated", 0))
            drops = [dict(x, state="sent") for x in self.d["drops"][-40:]][::-1]
            sending = [{"name": c["name"], "klass": c.get("klass"), "local": c.get("local"), "at": c.get("at"),
                        "state": "sending", "done": c.get("sent", 0), "n": c.get("n", 1)}
                       for c in self.d["pending"] if c.get("type") == "file_drop"][::-1]
            cur = self.current_class()
            return {"snapshot": self.d["snapshot"], "pending": len(self.d["pending"]),
                    "last_ok": self.d["last_ok"], "status": dict(self.status), "paired": bool(self.pair),
                    "now": time.time(), "version": VERSION, "notes": notes, "drops": sending + drops,
                    "chat": self.d["chat"][-60:], "articles": sorted(self.d["articles"]),
                    "klass": cur, "classes": self.class_names(), "battery": self.battery,
                    "files_dir": self.files_dir(), "owl_hidden": bool(self.setting("owl_hidden", False)),
                    "drop_klass": self.drop_target(), "drop_pick": self.drop_pick(), "rec": self.rec_view(),
                    "drafts": self.drafts_view(),
                    "staged": self.staged_view(), "kinds": self.INBOX_KINDS, "big": self.BIG,
                    "pending_notes": [c.get("nid") for c in self.d["pending"] if c.get("type") == "note_save"]}

    def change(self, op):
        """One change from the page: shown now, sent to the PC at the next sync."""
        if op.get("type") == "note_quick":
            return self.note_quick(op.get("text") or "")
        op = {k: v for k, v in op.items() if k in ("type", "id", "item", "base", "text", "due", "done", "date",
                                                    "what", "topic", "title", "url", "publisher", "author", "time")}
        t = op.get("type")
        with self.lock:
            snap = self.d["snapshot"]
            if t == "cal_add":
                op["id"] = op.get("id") or new_id()
            if t in ("cal_edit", "cal_del"):
                cur = next((e for e in snap["calendar"] if e["id"] == op.get("id")), None)
                if cur is None:
                    return {"ok": False, "error": "no such entry"}
                op["base"] = {k: cur.get(k) for k in ("title", "date", "time", "kind", "notes", "repeat", "until")}
            if t in ("task_add", "task_done") and not (op.get("text") or "").strip():
                return {"ok": False, "error": "empty"}
            op["oid"] = new_id() + new_id()
            apply_local(snap, op)
            self.d["pending"].append(op)
            self.save()
        self.wake.set()
        self.on_change()
        return {"ok": True}

    # ----- finding the PC -------------------------------------------------------------------
    def _discover(self, timeout=1.5):
        if not self.pair:
            return None
        ch = os.urandom(12).hex()
        want = proto.proof(self.pair["key"], ch)
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            s.settimeout(timeout)
            msg = ("ARCHIE-LITE-HELLO " + ch).encode()
            port = int(self.pair.get("discover_port") or proto.DISCOVER_PORT)
            for target in ["255.255.255.255"] + list(self.pair.get("addresses") or []):
                try:
                    s.sendto(msg, (target, port))
                except OSError:
                    pass
            end = time.time() + timeout
            while time.time() < end:
                try:
                    data, addr = s.recvfrom(1024)
                except socket.timeout:
                    break
                try:
                    r = json.loads(data)
                except ValueError:
                    continue
                if r.get("proof") == want:
                    return f"{addr[0]}:{int(r.get('port') or proto.PORT)}"
        finally:
            s.close()
        return None

    def _post(self, addr, body, timeout):
        req = urllib.request.Request(f"http://{addr}/lite", data=proto.seal(self.pair["key"], body), method="POST",
                                     headers={"Content-Type": "application/octet-stream"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return self.opener.open(r.read())

    @staticmethod
    def _reachable(addr, wait=2.5):
        """Quick check so a dead address costs seconds, not the whole request timeout."""
        host, _, port = addr.rpartition(":")
        try:
            socket.create_connection((host, int(port)), timeout=wait).close()
            return True
        except (OSError, ValueError):
            return False

    def _call(self, body, timeout=15):
        """Send to the PC at its last address, the addresses it told us, its name (Tailscale), then any
        it was paired at, then wherever it answers on this network."""
        tried, why = [], []
        port = self.pair.get("port") or proto.PORT
        name = str(self.pair.get("pc") or "").strip().lower()
        known = list(self.d.get("pc_addresses") or []) + ([name] if name else []) + list(self.pair.get("addresses") or [])
        for addr in [self.d.get("addr")] + [f"{a}:{port}" for a in known]:
            if addr and addr not in tried:
                tried.append(addr)
                if not self._reachable(addr):
                    why.append(f"{addr} didn't answer")
                    continue
                try:
                    out = self._post(addr, body, timeout)
                    self.d["addr"] = addr
                    return out
                except urllib.error.HTTPError as e:
                    why.append(f"{addr} answered but refused this laptop ({e.code}): pairing key doesn't match"
                               if e.code == 401 else f"{addr} answered with an error ({e.code})")
                except (OSError, urllib.error.URLError, proto.ProtoError) as e:
                    why.append(f"{addr} didn't answer")
        addr = self._discover()
        if addr:
            out = self._post(addr, body, timeout)
            self.d["addr"] = addr
            return out
        pc = self.pair.get("pc") or "your PC"
        raise OSError(f"Can't reach {pc}: " + ("; ".join(why) or "no answer") + ". Is Archie running on it, on the same "
                      "Wi-Fi or Tailscale? If so, run 'Allow Archie Lite.bat' in the Archie folder on the PC (Windows Firewall).")

    # ----- syncing ----------------------------------------------------------------------------
    def client_info(self):
        if not getattr(self, "_build", None):
            try:
                self._build = hashlib.sha256(json.dumps(manifest(self.root), sort_keys=True).encode()).hexdigest()
            except Exception:
                self._build = None
        p = self.d["pending"]
        return {"version": VERSION, "host": socket.gethostname(), "battery": self.battery,
                "pending": len([c for c in p if c.get("type") != "file_drop"]),
                "files_waiting": len([c for c in p if c.get("type") == "file_drop"]),
                "chat_waiting": len([m for m in self.d["chat"] if m.get("queued")]),
                "update_error": self.d.get("update_error"), "build": self._build, "files_dir": self.files_dir()}

    def sync_once(self):
        if not self.pair:
            self.status.update(state="unpaired", msg="not paired with a PC yet")
            return False
        try:
            self._upload_files()
            self.d.pop("upload_error", None)
        except Exception as e:                 # files wait for the next round; everything else still syncs
            self.d["upload_error"] = str(e)[:300]
        with self.lock:
            sending = [c for c in self.d["pending"]
                       if c.get("type") != "file_drop" or c.get("sent", 0) >= c.get("n", 1)]
            wire = [{k: v for k, v in c.items() if k not in ("local", "sent", "tries", "at")} for c in sending]
            files = any(c.get("type") == "file_drop" for c in sending)
        try:
            res = self._call({"op": "sync", "changes": wire, "client": self.client_info()}, timeout=180 if files else 30)
        except Exception as e:
            self.status.update(state="away", msg=str(e)[:400])
            self.on_change()
            return False
        if not res.get("ok"):
            self.status.update(state="error", msg=str(res.get("error"))[:120])
            return False
        sent = {c["oid"] for c in sending}
        results = {r.get("oid"): r for r in res.get("results", [])}
        with self.lock:
            retry = []
            for c in sending:
                r = results.get(c["oid"]) or {}
                if not r.get("ok") and c.get("type") in RETRY and (c.get("tries", 0) < 5 or "unknown" in str(r.get("note"))):
                    if "unknown" not in str(r.get("note")):      # an older Archie on the PC: wait for its restart
                        c["tries"] = c.get("tries", 0) + 1
                    if c.get("type") == "file_drop":
                        c["sent"] = 0              # send the pieces again
                    retry.append(c)
                elif c.get("type") == "file_drop":
                    self.d["drops"].append({"name": c["name"], "klass": c.get("klass"), "local": c.get("local"),
                                            "at": c.get("at"), "ok": bool(r.get("ok")), "note": r.get("note"),
                                            "sha": c.get("sha")})
                    self.d["drops"] = self.d["drops"][-200:]
            left = retry + [c for c in self.d["pending"] if c["oid"] not in sent]
            snap = res["snapshot"]
            for k, v in EMPTY.items():
                snap.setdefault(k, copy.deepcopy(v))
            for c in left:
                apply_local(snap, c)
            self.d["snapshot"] = snap
            self.d["pending"] = left
            self.d["last_ok"] = time.time()
            self.d["notes_from_pc"] = [r for r in res.get("results", []) if not r.get("ok") or "both" in str(r.get("note"))][-20:]
            pcs = [a for a in (snap.get("addresses") or []) if isinstance(a, str) and len(a) < 40]
            if pcs:
                self.d["pc_addresses"] = pcs[:8]
            want_files = snap.pop("lite_files", None)
            mail = [a for a in snap.pop("mail_alerts", None) or [] if isinstance(a, dict) and a.get("id")]
            seen = self.d.get("mail_seen")
            fresh = [] if seen is None else [a for a in mail if a["id"] not in seen and time.time() - (a.get("at") or 0) < 6 * 3600]
            self.d["mail_seen"] = [a["id"] for a in mail][-30:]     # the first sync only remembers (no pile of old ones)
            self.save()
        self.status.update(state="home", pc=snap.get("pc"), addr=self.d.get("addr"), at=time.time(), msg="")
        self.on_change()
        for a in fresh[-4:]:                       # new mail the PC made a card for: a toast here too
            try:
                self.on_mail(a)
            except Exception:
                pass
        for job in (lambda: self.fetch_update(want_files) if want_files else None,
                    lambda: self._fetch_articles(snap.get("saved") or []),
                    self._fetch_world,
                    self._drain_chat):
            try:
                job()
            except Exception as e:
                if job is not None:
                    self.d["after_sync_error"] = f"{type(e).__name__}: {e}"[:300]
                    self.save()
        return True

    # ----- files you drop on the owl or the panel -------------------------------------------------
    def files_dir(self):
        return self.setting("files_dir") or os.path.join(os.path.expanduser("~"), "Documents", "Archie Lite")

    def _upload_files(self):
        """Send dropped files to the PC in pieces before the sync that delivers them."""
        with self.lock:
            todo = [c for c in self.d["pending"] if c.get("type") == "file_drop" and c.get("sent", 0) < c.get("n", 1)]
        for c in todo:
            local = c.get("local")
            if not local or not os.path.isfile(local):
                with self.lock:
                    self.d["pending"] = [x for x in self.d["pending"] if x is not c]
                    self.d["drops"].append({"name": c["name"], "klass": c.get("klass"), "local": local, "at": c.get("at"),
                                            "ok": False, "note": "the laptop's copy was deleted before it was sent"})
                    self.save()
                continue
            with open(local, "rb") as f:
                while c.get("sent", 0) < c["n"]:
                    i = c.get("sent", 0)
                    f.seek(i * CHUNK)
                    data = f.read(CHUNK)
                    r = self._call({"op": "file_chunk", "fid": c["fid"], "i": i, "n": c["n"],
                                    "b64": base64.b64encode(data).decode("ascii")}, timeout=120)
                    if not r.get("ok"):
                        if "unknown" in str(r.get("error")):
                            raise OSError("Restart Archie on your PC to receive files from the laptop.")
                        raise OSError("the PC didn't take a piece of " + c["name"] + ": " + str(r.get("error")))
                    with self.lock:
                        c["sent"] = i + 1
                        self.save()
                    self.on_change()

    def drop_pick(self):
        """The class picked in the panel for dropped files ({"klass": ...}), good until midnight."""
        p = self.setting("drop_pick")
        return p if isinstance(p, dict) and p.get("day") == datetime.date.today().isoformat() else None

    def set_drop_pick(self, klass):
        """klass: a class name, "" for no class, None to go back to "the class on now"."""
        self.set_setting("drop_pick", None if klass is None else
                         {"klass": (klass or "").strip() or None, "day": datetime.date.today().isoformat()})
        return {"ok": True, "drop_klass": self.drop_target()}

    def drop_target(self):
        p = self.drop_pick()
        if p:
            return p.get("klass")
        cur = self.current_class()
        return cur["title"] if cur else None

    def drop_file(self, path=None, data=None, name=None, mtime=None, klass=AUTO, extra=None):
        """A file dropped on the owl or the panel: kept on this laptop, then sent to the PC."""
        if path and os.path.isdir(path):
            return {"ok": False, "error": "That's a folder. Drop the files inside it."}
        name = safe_name(name or os.path.basename(path or "") or "file", "file")
        size = os.path.getsize(path) if path else len(data or b"")
        if size > MAX_DROP:
            return {"ok": False, "error": f"{name} is over 1 GB; too big to send."}
        klass = self.drop_target() if klass is AUTO else ((klass or "").strip() or None)
        base = self.files_dir()
        folder = os.path.join(base, "Lectures", safe_name(klass, "Other"), "Files") if klass else os.path.join(base, "Files")
        os.makedirs(folder, exist_ok=True)
        dest = unique_path(os.path.join(folder, name))
        if path:
            shutil.copy2(path, dest)
            mtime = mtime or os.path.getmtime(path)
        else:
            with open(dest, "wb") as f:
                f.write(data or b"")
        h = hashlib.sha256()
        with open(dest, "rb") as f:
            for b in iter(lambda: f.read(1 << 20), b""):
                h.update(b)
        op = {"type": "file_drop", "oid": new_id() + new_id(), "fid": new_id() + new_id(), "name": os.path.basename(dest),
              "klass": klass, "sha": h.hexdigest(), "size": size, "mtime": mtime or time.time(),
              "date": datetime.date.today().isoformat(), "n": max(1, -(-size // CHUNK)), "sent": 0, "local": dest,
              "at": time.time()}
        op.update(extra or {})
        with self.lock:
            self.d["pending"].append(op)
            self.save()
        self.wake.set()
        self.on_change()
        return {"ok": True, "name": op["name"], "klass": klass, "local": dest}

    # ----- the inbox card: a dropped file waits for "what is it / which class / name" before it's sent ----------
    # (same kinds and the same filing rules as Archie's card on the PC; the PC does the filing)
    INBOX_KINDS = ["slides / handout", "reading", "syllabus", "assignment", "board photo", "my notes", "recording", "idea", "other"]
    BIG = 50 * 1024 * 1024

    @staticmethod
    def guess_kind(name, klass):
        low, ext = name.lower(), os.path.splitext(name)[1].lower()
        if "syllabus" in low:
            return "syllabus"
        if ext in (".mp3", ".m4a", ".wav", ".webm", ".ogg", ".opus", ".aac", ".flac", ".mp4", ".mov", ".mkv"):
            return "recording" if re.search(r"^Recording\b|\(20\d\d-\d\d-\d\d", name) or not klass else "slides / handout"
        if ext in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".heic", ".bmp"):
            return "board photo" if (re.search(r"\bboard\b", low) or klass) else "other"
        if re.search(r"assign|homework|\bhw\d*\b|worksheet|lab report|problem set|pset|due", low):
            return "assignment"
        if ext in (".ppt", ".pptx", ".key", ".odp"):
            return "slides / handout"
        if re.search(r"chapter|\bch\.? ?\d|reading|article|paper", low):
            return "reading"
        if ext in (".md", ".txt"):
            return "my notes"
        if klass and ext in (".pdf", ".doc", ".docx", ".rtf", ".odt"):
            return "slides / handout"
        return "other"

    @staticmethod
    def renamed(original, new_stem):
        """Your new name; a date and time in the original name stays on the end (the lecture review uses it)."""
        stem, ext = os.path.splitext(os.path.basename(original))
        new_stem = safe_name((new_stem or "").strip(), "")
        if not new_stem or new_stem == stem:
            return safe_name(os.path.basename(original), "file")
        m = re.search(r"\((?:[A-Za-z]+ )?(20\d\d-\d\d-\d\d[^)]*)\)", stem)
        if m and m.group(1) not in new_stem:
            label = "Board " if re.search(r"\bboard\b", stem, re.I) else ""
            new_stem = f"{new_stem} ({label}{m.group(1)})"
        return new_stem + ext

    def stage(self, path, name=None, mtime=None, owned=False):
        """Hold a dropped file for its card. owned: our own temporary copy (deleted once it's sent or skipped)."""
        name = safe_name(name or os.path.basename(path), "file")
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for b in iter(lambda: f.read(1 << 20), b""):
                h.update(b)
        sha = h.hexdigest()
        with self.lock:
            seen = [c for c in self.d["pending"] if c.get("sha") == sha] + \
                   [x for x in self.d["drops"] if x.get("sha") == sha and x.get("ok")]
            klass = self.drop_target()
            item = {"id": new_id(), "path": path, "owned": owned, "name": name, "size": os.path.getsize(path),
                    "mtime": mtime or os.path.getmtime(path), "sha": sha, "klass": klass,
                    "kind": self.guess_kind(name, klass), "at": time.time(),
                    "dup": (seen[0].get("name") + (" (sending)" if seen[0] in self.d["pending"] else "")) if seen else None}
            self.d.setdefault("staged", []).append(item)
            self.save()
        self.on_change()
        return {"ok": True, "id": item["id"], "name": name}

    def staged_view(self):
        return [{k: x.get(k) for k in ("id", "name", "size", "klass", "kind", "dup")} for x in self.d.get("staged", [])]

    def stage_save(self, sid, name=None, kind=None, klass=AUTO):
        with self.lock:
            item = next((x for x in self.d.get("staged", []) if x["id"] == sid), None)
        if not item:
            return {"ok": False, "error": "That file isn't waiting any more."}
        kind = kind if kind in self.INBOX_KINDS else item["kind"]
        final = self.renamed(item["name"], name) if name else item["name"]
        r = self.drop_file(path=item["path"], name=final, mtime=item["mtime"],
                           klass=item["klass"] if klass is AUTO else klass,
                           extra={"kind": kind, **({"folder": "ideas"} if kind == "idea" else {})})
        if r.get("ok"):
            self._unstage(item)
        return r

    def stage_drop(self, sid):
        with self.lock:
            item = next((x for x in self.d.get("staged", []) if x["id"] == sid), None)
        if item:
            self._unstage(item)
        return {"ok": True}

    def _unstage(self, item):
        with self.lock:
            self.d["staged"] = [x for x in self.d.get("staged", []) if x["id"] != item["id"]]
            self.save()
        if item.get("owned"):
            try:
                os.remove(item["path"])
            except OSError:
                pass
        self.on_change()

    # ----- recording a lecture on this laptop ------------------------------------------------------------
    # The panel records (Edge, the laptop's microphone) and hands over a piece every 10 seconds; the pieces are
    # kept here on disk, so closing the panel by mistake keeps everything up to then. Stop joins them into
    # "Recording <date><time>.webm" and sends it like a dropped file, filed under the class.
    def _rec_dir(self, rid):
        return os.path.join(self.data_dir, "rec", "".join(ch for ch in rid if ch in "0123456789abcdef")[:32])

    def rec_view(self):
        r = self.d.get("rec")
        if not r:
            return None
        return {"id": r["id"], "klass": r.get("klass"), "started": r["started"], "elapsed": self.rec_elapsed(),
                "paused": bool(r.get("paused")), "marks": len(r.get("marks") or []), "pieces": r.get("pieces", 0),
                "bytes": r.get("bytes", 0), "seen": r.get("seen")}

    def drafts_view(self):
        return [{"id": x["id"], "klass": x.get("klass"), "label": x.get("label", ""), "started": x["started"],
                 "duration": x.get("duration", 0), "marks": len(x.get("marks") or []), "bytes": x.get("bytes", 0),
                 "name": self._draft_name(x), "why": x.get("why", "")} for x in self.d.get("rec_drafts") or []]

    @staticmethod
    def _draft_name(x):
        st = datetime.datetime.fromtimestamp(x["started"])
        lab = " ".join(safe_name(x.get("label") or "", "").replace("(", " ").replace(")", " ").replace(";", " ").split())
        h = st.hour % 12 or 12
        return f"{lab or 'Recording'} ({st:%Y-%m-%d} {h}.{st:%M} {'AM' if st.hour < 12 else 'PM'}).webm"

    def rec_elapsed(self):
        r = self.d.get("rec")
        if not r:
            return 0
        return r.get("elapsed", 0) + (0 if r.get("paused") else max(0, time.time() - r.get("elapsed_at", time.time())))

    def rec_start(self, klass=AUTO):
        with self.lock:
            if self.d.get("rec"):
                return {"ok": True, "rec": self.rec_view(), "already": True}
            klass = self.drop_target() if klass is AUTO else ((klass or "").strip() or None)
            rid = new_id() + new_id()
            os.makedirs(self._rec_dir(rid), exist_ok=True)
            now = time.time()
            self.d["rec"] = {"id": rid, "klass": klass, "started": now, "pieces": 0, "bytes": 0, "marks": [],
                             "paused": False, "elapsed": 0, "elapsed_at": now, "seen": now}
            self.save()
        self.on_change()
        return {"ok": True, "rec": self.rec_view()}

    def _rec_mine(self, rid):
        r = self.d.get("rec")
        return r if r and r["id"] == rid else None

    def rec_piece(self, rid, i, data):
        with self.lock:
            r = self._rec_mine(rid)
            if not r:
                return {"ok": False, "error": "that recording already ended"}
            with open(os.path.join(self._rec_dir(rid), f"{int(i):06d}.part"), "wb") as f:
                f.write(data)
            r["pieces"] = max(r.get("pieces", 0), int(i) + 1)
            r["bytes"] = r.get("bytes", 0) + len(data)
            r["seen"] = time.time()
            if int(i) % 6 == 0:
                self.save()
        return {"ok": True}

    def rec_seen(self, rid):
        r = self._rec_mine(rid or "")
        if r:
            r["seen"] = time.time()

    def rec_set(self, rid, paused=None, elapsed=None, mark=None):
        with self.lock:
            r = self._rec_mine(rid)
            if not r:
                return {"ok": False, "error": "no such recording"}
            now = time.time()
            if elapsed is not None:
                r["elapsed"], r["elapsed_at"] = float(elapsed), now
            if paused is not None and bool(paused) != bool(r.get("paused")):
                if paused:
                    r["elapsed"] = self.rec_elapsed()
                r["paused"], r["elapsed_at"] = bool(paused), now
            if mark is not None:
                r["marks"].append({"t": float(mark.get("t", self.rec_elapsed())), "label": str(mark.get("label") or "")[:200]})
            r["seen"] = now
            self.save()
        self.on_change()
        return {"ok": True, "rec": self.rec_view()}

    def rec_stop(self, rid=None, elapsed=None, why=""):
        """Stop: join the pieces into one recording and keep it as a draft. Nothing is sent until you press
        send (you can name it and change its class first). Also used for a recording the panel stopped
        talking about (closed by mistake, or Archie Lite restarted)."""
        with self.lock:
            r = self.d.get("rec")
            if not r or (rid and r["id"] != rid):
                return {"ok": False, "error": "no recording"}
            self.d["rec"] = None
            self.save()
        dur = float(elapsed) if elapsed else (r.get("elapsed", 0) + (0 if r.get("paused") else
                                              max(0, min(r.get("seen", 0), time.time()) - r.get("elapsed_at", 0))))
        folder = self._rec_dir(r["id"])
        parts = sorted(f for f in os.listdir(folder) if f.endswith(".part")) if os.path.isdir(folder) else []
        self.on_change()
        if not parts:
            shutil.rmtree(folder, ignore_errors=True)
            return {"ok": False, "error": "nothing was recorded"}
        whole = os.path.join(folder, "whole.webm")
        with open(whole, "wb") as out:
            for p in parts:
                with open(os.path.join(folder, p), "rb") as f:
                    shutil.copyfileobj(f, out)
        for p in parts:
            try:
                os.remove(os.path.join(folder, p))
            except OSError:
                pass
        draft = {"id": r["id"], "klass": r.get("klass"), "label": "", "started": r["started"], "duration": dur,
                 "marks": r.get("marks") or [], "whole": whole, "bytes": os.path.getsize(whole), "why": why}
        with self.lock:
            self.d.setdefault("rec_drafts", []).append(draft)
            self.save()
        self.on_change()
        return {"ok": True, "draft": draft["id"], "duration": dur, "klass": draft["klass"]}

    def _draft(self, did):
        return next((x for x in self.d.get("rec_drafts") or [] if x["id"] == did), None)

    def draft_set(self, did, label=None, klass=AUTO):
        with self.lock:
            x = self._draft(did)
            if not x:
                return {"ok": False, "error": "no such recording"}
            if label is not None:
                x["label"] = str(label)[:80]
            if klass is not AUTO:
                x["klass"] = (klass or "").strip() or None
            self.save()
        return {"ok": True, "name": self._draft_name(x)}

    def draft_send(self, did):
        with self.lock:
            x = self._draft(did)
        if not x:
            return {"ok": False, "error": "no such recording"}
        name = self._draft_name(x)
        res = self.drop_file(path=x["whole"], name=name, mtime=x["started"] + x.get("duration", 0),
                             klass=x.get("klass") or "", extra={"own": True})
        if not res.get("ok"):
            return res
        marks = x.get("marks") or []
        if marks:
            st = datetime.datetime.fromtimestamp(x["started"])
            mm = lambda t: f"{int(t) // 3600}:{int(t) % 3600 // 60:02d}:{int(t) % 60:02d}" if t >= 3600 else f"{int(t) // 60:02d}:{int(t) % 60:02d}"
            lines = [f"- **{mm(m['t'])}** {m['label'] or 'marked'}" for m in marks]
            self.note_save(None, f"{x.get('klass') or 'Lecture'} · {st:%b} {st.day} marks", x.get("klass"), st.date().isoformat(),
                           f"Recording: [[{res['name']}]] ({mm(x.get('duration', 0))}).\n\n## Marked moments\n\n" + "\n".join(lines) + "\n")
        with self.lock:
            self.d["rec_drafts"] = [y for y in self.d.get("rec_drafts") or [] if y["id"] != did]
            self.save()
        shutil.rmtree(self._rec_dir(did), ignore_errors=True)
        self.on_change()
        return dict(res, ok=True, klass=x.get("klass"))

    def draft_discard(self, did):
        with self.lock:
            if not self._draft(did):
                return {"ok": False, "error": "no such recording"}
            self.d["rec_drafts"] = [y for y in self.d.get("rec_drafts") or [] if y["id"] != did]
            self.save()
        shutil.rmtree(self._rec_dir(did), ignore_errors=True)
        self.on_change()
        return {"ok": True}

    def rec_check(self):
        """A recording the panel stopped talking about for 5 minutes is saved as it is."""
        r = self.d.get("rec")
        if r and time.time() - (r.get("seen") or 0) > REC_STALE:
            return self.rec_stop(r["id"], why="the panel was closed while recording")
        return None

    # ----- notes ------------------------------------------------------------------------------------
    def note_save(self, nid=None, title="", klass=None, date=None, text=""):
        nid = "".join(ch for ch in str(nid or "") if ch in "0123456789abcdef")[:24] or (new_id() + new_id())
        title = (title or "").strip()[:120] or (text.strip().splitlines() or ["Untitled"])[0][:60] or "Untitled"
        klass = (klass or "").strip() or None
        date = (date or datetime.date.today().isoformat())[:10]
        with self.lock:
            n = self.d["notes"].get(nid) or {"nid": nid, "created": time.time()}
            n.update(title=title, klass=klass, date=date, text=text, updated=time.time())
            base = self.files_dir()
            folder = os.path.join(base, "Lectures", safe_name(klass, "Other")) if klass else os.path.join(base, "Notes")
            want = os.path.join(folder, f"{date} {safe_name(title)}.md")
            try:
                os.makedirs(folder, exist_ok=True)
                old = n.get("local")
                if old and os.path.normcase(old) != os.path.normcase(want):
                    if os.path.exists(want):
                        want = unique_path(want)
                    if os.path.exists(old):
                        os.replace(old, want)
                with open(want + ".tmp", "w", encoding="utf-8") as f:
                    f.write(f"# {title}\n\n{text.rstrip()}\n")
                os.replace(want + ".tmp", want)
                n["local"] = want
            except OSError as e:
                n["local_error"] = str(e)
            self.d["notes"][nid] = n
            self.d["pending"] = [c for c in self.d["pending"] if not (c.get("type") == "note_save" and c.get("nid") == nid)]
            self.d["pending"].append({"type": "note_save", "oid": new_id() + new_id(), "nid": nid, "title": title,
                                      "klass": klass, "date": date, "text": text})
            self.save()
        t = getattr(self, "_note_timer", None)
        if t:
            t.cancel()
        self._note_timer = threading.Timer(20, self.wake.set)     # sync once you stop typing for a bit
        self._note_timer.daemon = True
        self._note_timer.start()
        self.on_change()
        return {"ok": True, "nid": nid}

    def note_hide(self, nid):
        """Take a note off this laptop's list. Obsidian keeps it; so does the .md copy in the Archie Lite folder."""
        with self.lock:
            if any(c.get("type") == "note_save" and c.get("nid") == nid for c in self.d["pending"]):
                return {"ok": False, "error": "It's still sending; try again once it says in Obsidian."}
            if self.d["notes"].pop(nid, None) is None:
                return {"ok": False, "error": "That note isn't here any more."}
            self.save()
        self.on_change()
        return {"ok": True}

    def note_quick(self, text):
        text = (text or "").strip()
        if not text:
            return {"ok": False, "error": "empty"}
        cur = self.current_class()
        first = text.splitlines()[0]
        title = " ".join(first.split()[:8])
        return self.note_save(None, title, cur["title"] if cur else None, None, text)

    # ----- the calendar, read on the laptop ---------------------------------------------------------
    def class_names(self):
        seen = []
        for e in self.d["snapshot"].get("calendar") or []:
            if e.get("kind") in CLASS_KINDS and e.get("title") and e["title"] not in seen:
                seen.append(e["title"])
        return sorted(seen, key=str.lower)

    def current_class(self, now=None):
        """The class or lab happening now (from 20 min before to 30 min after), or None."""
        now = now or datetime.datetime.now()
        best = None
        for e in occurrences(self.d["snapshot"].get("calendar") or [], now.date(), now.date()):
            t0 = at(e)
            if e.get("kind") not in CLASS_KINDS or not t0:
                continue
            mins = lite_cal.DURATION.get(e["kind"], 75)
            if t0 - datetime.timedelta(minutes=20) <= now <= t0 + datetime.timedelta(minutes=mins + 30):
                gap = abs((now - t0).total_seconds())
                if best is None or gap < best[0]:
                    best = (gap, {"title": e["title"], "kind": e["kind"], "time": e["time"],
                                  "until": (t0 + datetime.timedelta(minutes=mins)).strftime("%H:%M")})
        return best[1] if best else None

    def next_event(self, now=None):
        now = now or datetime.datetime.now()
        for e in occurrences(self.d["snapshot"].get("calendar") or [], now.date(), now.date() + datetime.timedelta(days=1)):
            t0 = at(e)
            if t0 and t0 >= now:
                return e, t0
        return None, None

    def due_today(self, today=None):
        today = (today or datetime.date.today()).isoformat()
        S = self.d["snapshot"]
        tasks = [t["text"] for t in S.get("tasks") or [] if not t.get("done") and t.get("due") == today]
        dls = [x["what"] for x in S.get("deadlines") or [] if x.get("date") == today]
        return tasks, dls

    def reminders(self, now=None):
        """Pop-ups that are due now: [(title, body)]. Each is shown once."""
        now = now or datetime.datetime.now()
        out = []
        with self.lock:
            seen = self.d["notified"]
            for k in [k for k, v in seen.items() if v < time.time() - 4 * 86400]:
                del seen[k]
            for e in occurrences(self.d["snapshot"].get("calendar") or [], now.date(), now.date()):
                t0 = at(e)
                if not t0:
                    continue
                lead = 15 if e.get("kind") in ("class", "lab", "exam", "test", "quiz") else 30
                key = f"ev:{e.get('id')}:{e['date']}:{e['time']}"
                if t0 - datetime.timedelta(minutes=lead) <= now < t0 + datetime.timedelta(minutes=2) and key not in seen:
                    seen[key] = time.time()
                    mins = max(0, int((t0 - now).total_seconds() // 60))
                    label = lite_cal.KINDS.get(e.get("kind"), ("Event",))[0]
                    out.append((f"{e['title']} {'now' if mins == 0 else f'in {mins} min'}",
                                f"{label} · {lite_cal.fmt_time(e['time'])}" + (" · drop files on the owl" if e.get("kind") in CLASS_KINDS else "")))
            key = "day:" + now.date().isoformat()
            if now.hour >= 8 and key not in seen:
                seen[key] = time.time()
                tomorrow = (now.date() + datetime.timedelta(days=1)).isoformat()
                S = self.d["snapshot"]
                lines = []
                tasks, dls = self.due_today(now.date())
                lines += [f"Due today: {w}" for w in dls]
                lines += [f"Due tomorrow: {x['what']}" for x in S.get("deadlines") or [] if x.get("date") == tomorrow]
                lines += [f"{lite_cal.KINDS.get(e['kind'], ('Event',))[0]} tomorrow: {e['title']}"
                          for e in occurrences(S.get("calendar") or [], now.date() + datetime.timedelta(days=1), now.date() + datetime.timedelta(days=1))
                          if e.get("kind") in ("exam", "test", "quiz")]
                if tasks:
                    lines.append(f"{len(tasks)} to-do{'s' if len(tasks) != 1 else ''} due today: " + ", ".join(tasks[:3]))
                if lines:
                    out.append(("Today", "\n".join(lines[:5])))
            if out:
                self.save()
        return out

    # ----- saved articles, for reading offline ------------------------------------------------------
    def _fetch_articles(self, saved):
        rels = [s["md"] for s in saved if s.get("md")][:60]
        missing = [r for r in rels if r not in self.d["articles"]][:25]
        os.makedirs(self.art_dir, exist_ok=True)
        if missing:
            res = self._call({"op": "articles", "want": missing}, timeout=90)
            for rel, txt in (res.get("articles") or {}).items():
                fn = hashlib.sha1(rel.encode()).hexdigest()[:20] + ".md"
                with open(os.path.join(self.art_dir, fn), "w", encoding="utf-8") as f:
                    f.write(txt)
                self.d["articles"][rel] = fn
        if rels:
            for rel in [r for r in self.d["articles"] if r not in rels]:
                try:
                    os.remove(os.path.join(self.art_dir, self.d["articles"].pop(rel)))
                except OSError:
                    pass
        self.save()

    # ----- World: news and governments (like Feather) --------------------------------------------
    def _fetch_world(self):
        force = self.__dict__.pop("_world_force", False)
        age, gage = lite_world.ages()
        if not force and age is not None and age < 1800:
            return
        want_govs = gage is None or gage > (6 * 3600 if force else 86400)
        r = self._call({"op": "world", "govs": want_govs}, timeout=120)
        if r.get("ok") and r.get("gz"):
            lite_world.save_pack(base64.b64decode(r["gz"]))
            self.on_change()

    def world_refresh(self):
        """The News refresh button: pull the feeds live here, and get the PC's latest if it's reachable."""
        started = lite_world.refresh(on_done=self.on_change)
        self._world_force = True
        self.wake.set()
        return {"started": started}

    def flag_svg(self, iso):
        p = lite_world.flag_path(iso)
        if not p:
            return None
        if os.path.exists(p):
            with open(p, "rb") as f:
                return f.read()
        if not self.pair or self.status.get("state") != "home":
            return None
        try:
            r = self._call({"op": "flag", "iso": iso}, timeout=6)
        except Exception:
            return None
        if not r.get("ok"):
            return None
        data = r["svg"].encode("utf-8")
        with open(p, "wb") as f:
            f.write(data)
        return data

    def article_text(self, rel):
        fn = self.d["articles"].get(rel)
        if not fn:
            return None
        try:
            with open(os.path.join(self.art_dir, fn), encoding="utf-8") as f:
                return f.read()
        except OSError:
            return None

    # ----- updates from the PC ---------------------------------------------------------------
    def update_ready(self):
        """The fetched update waiting in data\\update, or None."""
        try:
            with open(os.path.join(self.update_dir, "update.json"), encoding="utf-8") as f:
                u = json.load(f)
            return u if u.get("files") else None
        except (OSError, ValueError):
            return None

    def fetch_update(self, pc_files):
        """Fetch the files that differ from the PC's copy into data\\update (nothing installed yet)."""
        if not isinstance(pc_files, dict) or not pc_files:
            return False
        target = hashlib.sha256(json.dumps(pc_files, sort_keys=True).encode()).hexdigest()
        if target in (self.d.get("update_done"), (self.update_ready() or {}).get("target")):
            return False                 # already installed (or already waiting)
        mine = manifest(self.root)
        want = [r for r, h in pc_files.items() if safe_rel(r) and mine.get(r) != h]
        if not want:
            self.d["update_done"] = target
            self.save()
            return False
        res = self._call({"op": "lite_update", "want": want}, timeout=60)
        got = res.get("files") or {}
        shutil.rmtree(self.update_dir, ignore_errors=True)
        os.makedirs(self.update_dir)
        files = {}
        for rel in want:
            g = got.get(rel)
            if not g:
                continue
            data = base64.b64decode(g["b64"])
            if hashlib.sha256(data).hexdigest() != pc_files[rel]:
                continue
            dst = os.path.join(self.update_dir, *rel.split("/"))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(dst, "wb") as f:
                f.write(data)
            if rel.endswith(".py"):
                py_compile.compile(dst, cfile=dst + "c", doraise=True)    # broken code never gets installed
                os.remove(dst + "c")
            files[rel] = pc_files[rel]
        if len(files) != len(want):
            shutil.rmtree(self.update_dir, ignore_errors=True)
            raise RuntimeError(f"update incomplete ({len(files)} of {len(want)} files); trying again next sync")
        with open(os.path.join(self.update_dir, "update.json"), "w", encoding="utf-8") as f:
            json.dump({"target": target, "files": files, "at": time.time()}, f)
        self.d.pop("update_error", None)
        self.save()
        return True

    def install_update(self):
        """Copy the waiting update over the app (old files kept in data\\update_backup). True if installed."""
        u = self.update_ready()
        if not u:
            return False
        backup = os.path.join(self.data_dir, "update_backup")
        shutil.rmtree(backup, ignore_errors=True)
        done = []
        try:
            for rel in u["files"]:
                src = os.path.join(self.update_dir, *rel.split("/"))
                dst = os.path.join(self.root, *rel.split("/"))
                if os.path.exists(dst):
                    b = os.path.join(backup, *rel.split("/"))
                    os.makedirs(os.path.dirname(b), exist_ok=True)
                    shutil.copy2(dst, b)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copyfile(src, dst + ".new")
                os.replace(dst + ".new", dst)
                done.append(rel)
        except OSError:
            for rel in done:                 # put back what we already replaced
                b = os.path.join(backup, *rel.split("/"))
                dst = os.path.join(self.root, *rel.split("/"))
                try:
                    if os.path.exists(b):
                        shutil.copyfile(b, dst)
                    else:
                        os.remove(dst)
                except OSError:
                    pass
            raise
        with self.lock:
            self.d["update_done"] = u["target"]
            self.d["updated_at"] = time.time()
            self.d["updated_files"] = sorted(u["files"])[:50]
            self.save()
        shutil.rmtree(self.update_dir, ignore_errors=True)
        return True

    def run(self):
        """The background loop: sync now, then every couple of minutes, or right after a change."""
        while not self.stop.is_set():
            ok = self.sync_once()
            self.wake.clear()
            self.battery = on_battery()
            wait = (SYNC_BATTERY if self.battery else SYNC_EVERY) if ok else RETRY_AWAY
            if self.wake.wait(wait):
                time.sleep(2)          # let a burst of changes collect
            if self.stop.is_set():
                return

    def start(self):
        if self.d.get("rec"):                  # recording when Archie Lite last closed: save what there is
            threading.Thread(target=lambda: self.rec_stop(self.d["rec"]["id"], why="Archie Lite closed while recording") if self.d.get("rec") else None,
                             daemon=True, name="lite-rec-save").start()
        threading.Thread(target=self.run, daemon=True, name="lite-sync").start()
        return self

    # ----- chat: answered by the PC; questions wait here when it can't be reached ---------------------
    def _history(self):
        return [{"role": m["role"], "text": m["text"]} for m in self.d["chat"] if not m.get("queued")][-6:]

    def ask(self, q):
        q = (q or "").strip()[:3000]
        if not q:
            return {"ok": False, "error": "empty"}
        with self.lock:
            hist = self._history()
            msg = {"role": "user", "text": q, "at": time.time(), "qid": new_id()}
            self.d["chat"].append(msg)
            self.save()
        self.on_change()
        if not self.pair:
            msg["queued"] = True
            self.save()
            return {"ok": True, "queued": True}
        try:
            r = self._call({"op": "chat", "q": q, "history": hist}, timeout=200)
        except Exception:
            with self.lock:
                msg["queued"] = True
                self.save()
            self.on_change()
            return {"ok": True, "queued": True}
        self._answer(msg, r)
        return {"ok": True}

    def _answer(self, msg, r):
        text = (r.get("answer") or "").strip() if r.get("ok") else "(Archie couldn't answer: " + str(r.get("error")) + ")"
        with self.lock:
            msg.pop("queued", None)
            self.d["chat"].append({"role": "archie", "text": text or "(no answer)", "at": time.time(),
                                   "model": r.get("model"), "re": msg.get("qid")})
            self.d["chat"] = self.d["chat"][-200:]
            self.save()
        self.on_change()
        return text

    def _drain_chat(self):
        lock = self.__dict__.setdefault("_chat_lock", threading.Lock())
        if not lock.acquire(blocking=False):
            return
        try:
            for m in [m for m in self.d["chat"] if m.get("queued")]:
                with self.lock:
                    i = self.d["chat"].index(m)
                    hist = [{"role": x["role"], "text": x["text"]} for x in self.d["chat"][:i] if not x.get("queued")][-6:]
                r = self._call({"op": "chat", "q": m["text"], "history": hist}, timeout=200)
                text = self._answer(m, r)
                try:
                    self.on_answer(text)
                except Exception:
                    pass
        finally:
            lock.release()

    def clear_chat(self):
        with self.lock:
            self.d["chat"] = [m for m in self.d["chat"] if m.get("queued")]
            self.save()
        return {"ok": True}
