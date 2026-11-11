"""
archie_sync.py - lets Archie Lite on your laptop sync with Archie on this PC (2026-11-08).

  * Listens on your home network only (private addresses), and only the paired laptop can talk to it:
    every message is sealed with the pairing key (see archie_lite_proto.py).
  * The laptop sends the changes it made (calendar, to-dos, deadlines, followed topics, saved
    articles); this PC applies each one by itself, then sends back a fresh copy of everything:
    calendar, to-dos, deadlines, the news brief and your saved articles.
  * Item by item: an edit to one calendar entry never touches another. If the same entry was
    changed on both machines, both versions are kept (the laptop's is marked "(laptop)").
  * Chat: the laptop's questions are answered here, by your PC's model.
  * Updates (2026-11-09): every sync tells the laptop which Archie Lite files this PC has
    (D:\\ArchieLite\\app and web). If the laptop's differ, it asks for just those files and
    installs them itself, so you only need the stick for the first install.
  * Notes and drops (2026-11-09): notes typed on the laptop and files dropped on the owl land in
    your Obsidian vault: in Lectures\\<class> when it was during a class on your calendar, otherwise
    in "Archie Lite". Each dropped file gets its own note. Recordings go where Archie already turns
    them into lecture notes or voice notes. Files arrive in encrypted pieces, checked by hash.
  * Offline reading: the laptop keeps the text of your saved articles.
  * The laptop reports its version and health; Archie Doctor shows it.
  * Phone (2026-11-09): archie_phone.py serves the phone app through Tailscale and uses these same
    requests; "quick_add" changes (one line of text) are read here with Archie Lite's lite_quick.py.
    Every device (laptops, Surface, phone) shows separately in Archie Doctor.
  * World (1.3, like Feather): the laptop gets every story from the last 3 days, the news feed list
    (so it can refresh the news itself, anywhere with internet), every country's leaders and
    cabinet, and flags as it needs them.

First start makes the pairing key and writes the laptop's pairing file to ArchieLite\\data.
"""

import base64
import datetime
import gzip
import hashlib
import ipaddress
import json
import os
import re
import shutil
import socket
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import archie_lite_proto as proto

HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, "lite_sync.json")
LITE_DIR = os.path.join(os.path.dirname(HERE), "ArchieLite")
CAL_FIELDS = ("title", "date", "time", "kind", "notes", "repeat", "until")
TAILSCALE = ipaddress.ip_network("100.64.0.0/10")     # a Tailscale link counts as home too
INBOX = os.path.join(HERE, "lite_inbox")              # pieces of files on their way from the laptop
AUDIO_EXT = {".mp3", ".mp4", ".m4a", ".m4b", ".m4v", ".mka", ".aac", ".ogg", ".oga", ".opus", ".webm", ".wav", ".flac",
             ".wma", ".3gp", ".amr"}
MATERIAL_EXT = {".pdf", ".pptx", ".ppt", ".docx", ".doc", ".rtf", ".key", ".odp"}   # the professor's files
PAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}   # photos of handouts (board photos stay in Files)
TEXT_EXT = {".txt", ".md", ".csv", ".log"}
EMBED_EXT = {".pdf", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg", ".mp4", ".webm", ".mov", ".mp3", ".m4a",
             ".wav", ".ogg"}
UPDATE_DIRS = ("app", "web")
UPDATE_EXT = (".py", ".png", ".html", ".css", ".js", ".ttf", ".txt", ".ico", ".svg", ".json")


def _safe(s, fallback="Note"):
    s = re.sub(r'[<>:"/\\|?*#^\[\]\x00-\x1f]', " ", str(s or "")).strip(" .")
    return re.sub(r"\s{2,}", " ", s)[:80] or fallback


def _unique(path):
    stem, ext = os.path.splitext(path)
    n = 2
    while os.path.exists(path):
        path = f"{stem} ({n}){ext}"
        n += 1
    return path


def _home_ip(ip):
    try:
        a = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return (a.is_private or a in TAILSCALE) and not a.is_loopback


def lite_manifest(root=None, _cache={}):
    """{"app/lite.py": sha256, ...} for the Archie Lite files the laptop should have."""
    root = root or LITE_DIR
    out = {}
    for top in UPDATE_DIRS:
        base = os.path.join(root, top)
        for dirpath, dirs, files in os.walk(base):
            dirs[:] = [d for d in dirs if not d.startswith((".", "__"))]
            for fn in files:
                if not fn.lower().endswith(UPDATE_EXT) or fn.startswith("."):
                    continue
                full = os.path.join(dirpath, fn)
                rel = os.path.relpath(full, root).replace(os.sep, "/")
                try:
                    st = os.stat(full)
                except OSError:
                    continue
                key = (full, st.st_size, st.st_mtime_ns)
                h = _cache.get(key)
                if h is None:
                    with open(full, "rb") as f:
                        h = hashlib.sha256(f.read()).hexdigest()
                    _cache[key] = h
                out[rel] = h
    return out


def _same(a, b):
    a, b = a or {}, b or {}
    return all((a.get(k) or None) == (b.get(k) or None) for k in CAL_FIELDS)


class SyncService:
    def __init__(self, app):
        self.app = app
        self.state = self._load_state()
        self.opener = proto.Opener(self.state["key"])
        self.lock = threading.Lock()
        self.httpd = None
        self.udp = None
        self.last_seen = None
        self.error = ""

    # ----- pairing ---------------------------------------------------------------------
    def _load_state(self):
        try:
            with open(STATE, encoding="utf-8") as f:
                st = json.load(f)
            if st.get("key"):
                st.setdefault("applied", [])
                st.setdefault("notes", {})
                st.setdefault("client", {})
                st.setdefault("clients", {})
                return st
        except (OSError, ValueError):
            pass
        st = {"key": proto.new_key(), "created": time.time(), "applied": [], "notes": {}, "client": {}}
        self._save_state(st)
        return st

    def _save_state(self, st=None):
        st = st or self.state
        tmp = STATE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(st, f, indent=1)
        os.replace(tmp, STATE)

    def write_pairing(self, folder=None):
        """The file the laptop needs: the key, this PC's name and where to find it."""
        folder = folder or os.path.join(LITE_DIR, "data")
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, "pairing.json")
        info = {"key": self.state["key"], "pc": socket.gethostname(), "port": proto.PORT,
                "discover_port": proto.DISCOVER_PORT, "addresses": self.addresses(), "made": time.time()}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(info, f, indent=1)
        return path

    @staticmethod
    def addresses():
        out = set()
        try:
            for fam, _, _, _, sa in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
                if _home_ip(sa[0]):
                    out.add(sa[0])
        except OSError:
            pass
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("10.255.255.255", 1))
            ip = s.getsockname()[0]
            s.close()
            if ipaddress.ip_address(ip).is_private:
                out.add(ip)
        except OSError:
            pass
        return sorted(out)

    # ----- start / stop ----------------------------------------------------------------
    def start(self):
        if not os.path.exists(os.path.join(LITE_DIR, "data", "pairing.json")) and os.path.isdir(LITE_DIR):
            try:
                self.write_pairing()
            except OSError:
                pass
        svc = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_POST(self):
                try:
                    if not _home_ip(self.client_address[0]):
                        return self._raw(403, b"")
                    n = int(self.headers.get("Content-Length") or 0)
                    if n <= 0 or n > 8 * 1024 * 1024:
                        return self._raw(400, b"")
                    try:
                        msg = svc.opener.open(self.rfile.read(n))
                    except proto.ProtoError as e:
                        return self._raw(401, str(e).encode())
                    svc.last_seen = (self.client_address[0], time.time())
                    svc._hook_world()
                    out = svc.handle(msg)
                    return self._raw(200, proto.seal(svc.state["key"], out))
                except Exception as e:
                    svc.error = f"{type(e).__name__}: {e}"
                    return self._raw(500, b"")

            def _raw(self, code, body):
                self.send_response(code)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self._hook_world()
        try:
            import archie_phone
            self.phone = archie_phone.PhoneService(self).start()
        except Exception as e:                  # the phone is extra: the laptops still sync without it
            self.phone = None
            self._phone_err = f"{type(e).__name__}: {e}"
        self.httpd = ThreadingHTTPServer(("0.0.0.0", proto.PORT), Handler)
        self.httpd.daemon_threads = True
        threading.Thread(target=self.httpd.serve_forever, daemon=True, name="lite-sync").start()
        threading.Thread(target=self._discovery, daemon=True, name="lite-discover").start()
        return self

    def stop(self):
        if self.httpd:
            self.httpd.shutdown()
        if self.udp:
            try:
                self.udp.close()
            except OSError:
                pass

    def _discovery(self):
        """Answer the laptop's "where are you?" broadcast, proving we hold the key."""
        try:
            self.udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.udp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.udp.bind(("0.0.0.0", proto.DISCOVER_PORT))
        except OSError as e:
            self.error = f"discovery: {e}"
            return
        while True:
            try:
                data, addr = self.udp.recvfrom(512)
            except OSError:
                return
            try:
                if not _home_ip(addr[0]):
                    continue
                txt = data.decode("ascii", "replace")
                if txt.startswith("ARCHIE-LITE-HELLO "):
                    ch = txt.split(" ", 1)[1][:64]
                    reply = json.dumps({"pc": socket.gethostname(), "port": proto.PORT,
                                        "proof": proto.proof(self.state["key"], ch)}).encode()
                    self.udp.sendto(reply, addr)
            except Exception:
                continue

    # ----- requests ----------------------------------------------------------------------
    def handle(self, msg):
        op = msg.get("op")
        if op == "sync":
            with self.lock:
                host = str((msg.get("client") or {}).get("host") or "") if isinstance(msg.get("client"), dict) else ""
                self._device = "phone" if host == "Phone" else (host or "laptop")
                results = [self._apply(c) for c in (msg.get("changes") or [])[:500]]
                if isinstance(msg.get("client"), dict):
                    cl = {k: msg["client"].get(k) for k in ("version", "host", "pending", "battery", "update_error",
                                                             "files_waiting", "chat_waiting", "build", "files_dir")}
                    cl["seen"] = time.time()
                    cl["ip"] = self.last_seen[0] if self.last_seen else None
                    self.state["client"] = cl
                    self.state.setdefault("clients", {})[str(cl.get("host") or "device")[:60]] = cl
                self._save_state()
            return {"ok": True, "results": results, "snapshot": self.snapshot()}
        if op == "chat":
            return self.chat(msg.get("q") or "", msg.get("history") or [])
        if op == "ping":
            return {"ok": True, "pc": socket.gethostname()}
        if op == "lite_update":
            return self.lite_files(msg.get("want") or [])
        if op == "file_chunk":
            return self.file_chunk(msg)
        if op == "articles":
            return self.articles(msg.get("want") or [])
        if op == "world":
            return self.world_pack(bool(msg.get("govs")))
        if op == "flag":
            return self.flag(str(msg.get("iso") or ""))
        return {"ok": False, "error": "unknown request"}

    def _apply(self, c):
        oid = str(c.get("oid") or "")
        if oid and oid in self.state["applied"]:
            return {"oid": oid, "ok": True, "note": "already applied"}
        try:
            note = self._apply_one(c)
            ok = True
        except Exception as e:
            ok, note = False, f"{type(e).__name__}: {e}"
        if oid and ok:
            self.state["applied"] = (self.state["applied"] + [oid])[-2000:]
        return {"oid": oid, "ok": ok, "note": note}

    def _apply_one(self, c):
        kind = c.get("type")
        app = self.app
        if kind in ("cal_add", "cal_edit", "cal_del"):
            cal = app.calendar
            events = cal.load()
            by_id = {e["id"]: e for e in events}
            item = {k: (c.get("item") or {}).get(k) for k in CAL_FIELDS}
            if kind == "cal_add":
                if not item["title"] or not item["date"]:
                    return "skipped: no title or date"
                eid = str(c.get("id") or "")[:20] or os.urandom(5).hex()
                if eid in by_id:
                    return "already there"
                events.append(dict(item, id=eid, kind=item["kind"] or "event", notes=item["notes"] or ""))
                cal._save(events)
                return "added"
            eid = str(c.get("id") or "")
            cur = by_id.get(eid)
            if kind == "cal_del":
                if cur is None:
                    return "already gone"
                if not _same(cur, c.get("base")):
                    return "kept: it was changed on the PC too"
                cal._save([e for e in events if e["id"] != eid])
                return "deleted"
            if cur is None:
                return "skipped: it was deleted on the PC"
            if _same(cur, c.get("base")):
                cur.update(item)
                cal._save(events)
                return "updated"
            events.append(dict(item, id=os.urandom(5).hex(), title=(item["title"] or "") + " (laptop)",
                               kind=item["kind"] or "event", notes=item["notes"] or ""))
            cal._save(events)
            return "changed on both: kept both"
        if kind in ("mail_file", "mail_dates", "mail_done"):     # the email card on the phone
            mail = getattr(app, "mail", None)
            card = mail.card(str(c.get("id") or "")) if mail else None
            if not card:
                return "skipped: that email isn't on the PC any more"
            if kind == "mail_done":
                mail.mark(card["id"], done=True)
                return "done"
            if kind == "mail_dates":
                if not card.get("body_path") or not os.path.exists(card["body_path"]) or not app.inbox:
                    return "skipped: no text to read"
                app.inbox.queue_dates(card["body_path"], None)
                return "its dates are waiting on the PC to tick"
            try:
                n = int(c.get("n"))
                path = card["attachments"][n]
            except (TypeError, ValueError, IndexError, KeyError):
                return "skipped: no such attachment"
            if not os.path.exists(path) or not app.inbox:
                return "skipped: the file isn't on the PC any more"
            dup = app.inbox.already(path)
            if dup:
                mail.mark(card["id"], filed={str(n): app.inbox.rel(dup["dest"])})
                return f"already saved {dup.get('date', '')} → {app.inbox.rel(dup['dest'])}"
            kindf = c.get("kind") if c.get("kind") in app.inbox.KINDS else "other"
            klass = (c.get("klass") or "").strip() or None
            dest, _uid = app.inbox.save(path, kindf, klass, source=getattr(self, "_device", "phone"),
                                        new_name=(c.get("name") or "").strip() or None)
            mail.mark(card["id"], filed={str(n): app.inbox.rel(dest)})
            if kindf == "syllabus":
                app.inbox.queue_dates(dest, klass)
            return f"saved to {app.inbox.rel(dest)}"
        if kind == "task_add":
            text = (c.get("text") or "").strip().replace("\n", " ")[:300]
            if not text:
                return "skipped: empty"
            if any(t["text"].lower() == text.lower() and not t["done"] for t in app.tasks.load()):
                return "already there"
            due = c.get("due")
            app.tasks.add(text, datetime.date.fromisoformat(due) if due else None)
            return "added"
        if kind == "task_done":
            text = (c.get("text") or "").strip().lower()
            t = next((t for t in app.tasks.load() if t["text"].lower() == text), None)
            if t is None:
                return "skipped: no such task on the PC"
            if t["done"] != bool(c.get("done")):
                app.tasks.set_done(t, bool(c.get("done")))
            return "done" if c.get("done") else "reopened"
        if kind == "deadline_add":
            when, what = c.get("date"), (c.get("what") or "").strip()
            if not when or not what:
                return "skipped"
            d = datetime.date.fromisoformat(when)
            if any(x == d and w.lower() == what.lower() for x, w in app.deadlines.load()):
                return "already there"
            app.deadlines.add(d, what)
            return "added"
        if kind in ("follow_add", "follow_remove"):
            w = app.world
            if not w:
                raise RuntimeError("Archie World isn't running")
            topic = (c.get("topic") or "").strip()
            fol = list(w.watch.get("follow", []))
            if kind == "follow_add" and topic and topic.lower() not in [f.lower() for f in fol]:
                fol.append(topic)
            elif kind == "follow_remove":
                fol = [f for f in fol if f.lower() != topic.lower()]
            w.save_watch({"follow": fol})
            return "ok"
        if kind == "note_save":
            return self._note_save(c)
        if kind == "quick_add":
            return self._quick_add(c)
        if kind == "file_drop":
            return self._file_drop(c)
        if kind == "save_story":
            w = app.world
            if not w:
                raise RuntimeError("Archie World isn't running")
            payload = {k: c.get(k) for k in ("title", "url", "publisher", "author", "time")}
            threading.Thread(target=w.save_article, args=(payload,), daemon=True).start()
            return "saving"
        raise ValueError(f"unknown change {kind!r}")

    # ----- notes and dropped files ---------------------------------------------------------
    def _base(self):
        v = None
        try:
            v = self.app.vault()
        except Exception:
            pass
        if v and os.path.isdir(v):
            return v
        return os.path.join(HERE, "Notes")

    def _folder(self, klass, folder=None):
        base = self._base()
        if folder == "ideas":
            return os.path.join(base, "Ideas")
        return os.path.join(base, "Lectures", _safe(klass, "Other")) if klass else os.path.join(base, "Archie Lite")

    def _note_save(self, c):
        nid = re.sub(r"[^0-9a-f]", "", str(c.get("nid") or ""))[:24]
        if not nid:
            return "skipped: no id"
        klass = (c.get("klass") or "").strip() or None
        title = _safe(c.get("title") or "Note")
        day = str(c.get("date") or datetime.date.today().isoformat())[:10]
        folder = self._folder(klass, c.get("folder"))
        os.makedirs(folder, exist_ok=True)
        want = os.path.join(folder, f"{day} {title}.md")
        rec = self.state["notes"].get(nid) or {}
        cur = rec.get("path")
        note = "written"
        if cur and os.path.exists(cur):
            try:
                edited_here = abs(os.path.getmtime(cur) - (rec.get("mtime") or 0)) > 2
            except OSError:
                edited_here = False
            if edited_here:                      # changed in Obsidian on the PC: keep that, write the laptop's beside it
                want = _unique(os.path.join(folder, f"{day} {title} (laptop).md"))
                note = "changed on both: kept both"
            elif os.path.normcase(cur) != os.path.normcase(want):
                if os.path.exists(want):
                    want = _unique(want)
                os.replace(cur, want)
                note = "renamed"
        elif os.path.exists(want):
            want = _unique(want)
        tags = "idea, archie-lite" if c.get("folder") == "ideas" else "lecture-notes, archie-lite" if klass else "note, archie-lite"
        fm = ["---", f"tags: [{tags}]"] + ([f'class: "{klass}"'] if klass else []) + [
            f"date: {day}", f"source: Archie Lite ({getattr(self, '_device', 'laptop')})", "---", "", f"# {title}", ""]
        body = str(c.get("text") or "").replace("\r\n", "\n")
        tmp = want + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write("\n".join(fm) + body.rstrip() + "\n")
        os.replace(tmp, want)
        self.state["notes"][nid] = {"path": want, "mtime": os.path.getmtime(want)}
        return note

    def _quick_add(self, c):
        """One line from the phone's add box, read the same way Archie Lite reads it on the laptop."""
        app_dir = os.path.join(LITE_DIR, "app")
        if app_dir not in sys.path:
            sys.path.append(app_dir)
        import lite_quick
        op, msg = lite_quick.classify(c.get("text") or "")
        if not op:
            return "skipped: " + msg
        if op["type"] == "note_quick":
            text = op.get("text") or ""
            self._note_save({"nid": os.urandom(10).hex(), "title": " ".join(text.split()[:8]) or "Note",
                             "klass": c.get("klass"), "date": datetime.date.today().isoformat(), "text": text})
            return "Note saved"
        if op["type"] == "cal_add":
            op["id"] = os.urandom(5).hex()
        self._apply_one(op)
        return msg

    def file_chunk(self, msg):
        fid = re.sub(r"[^0-9a-f]", "", str(msg.get("fid") or ""))[:24]
        i, n = int(msg.get("i", -1)), int(msg.get("n", 0))
        if not fid or not (0 < n <= 2000 and 0 <= i < n):
            return {"ok": False, "error": "bad piece"}
        folder = os.path.join(INBOX, fid)
        os.makedirs(folder, exist_ok=True)
        data = base64.b64decode(msg.get("b64") or "")
        tmp = os.path.join(folder, f"{i}.part.tmp")
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, os.path.join(folder, f"{i}.part"))
        return {"ok": True, "i": i}

    def _file_drop(self, c):
        fid = re.sub(r"[^0-9a-f]", "", str(c.get("fid") or ""))[:24]
        n = int(c.get("n") or 0)
        folder = os.path.join(INBOX, fid)
        missing = [i for i in range(n) if not os.path.exists(os.path.join(folder, f"{i}.part"))]
        if not fid or n <= 0 or missing:
            raise RuntimeError(f"pieces missing: {missing[:20]}")
        name = _safe(c.get("name") or "file", "file")
        ext = os.path.splitext(name)[1].lower()
        klass = (c.get("klass") or "").strip() or None
        day = str(c.get("date") or datetime.date.today().isoformat())[:10]
        h = hashlib.sha256()
        assembled = os.path.join(folder, "whole")
        with open(assembled, "wb") as out:
            for i in range(n):
                with open(os.path.join(folder, f"{i}.part"), "rb") as f:
                    b = f.read()
                h.update(b)
                out.write(b)
        if h.hexdigest() != c.get("sha"):
            shutil.rmtree(folder, ignore_errors=True)
            raise RuntimeError("file didn't arrive whole; sending it again")
        inbox = getattr(self.app, "inbox", None)
        if inbox:
            try:                                   # the same file saved before (from any device): don't make a copy
                dup = inbox.already(assembled)
            except Exception:
                dup = None
            if dup:
                shutil.rmtree(folder, ignore_errors=True)
                return f"already saved {dup.get('date', '')} → {inbox.rel(dup.get('dest', ''))}"
        if inbox and c.get("kind") in getattr(inbox, "KINDS", ()):
            # sent from an inbox card (laptop or phone): filed by the card's kind, class and name, with the same rules
            # as the PC's card (archie_inbox), so the lecture review finds it
            named = os.path.join(folder, _safe(c.get("name") or "file", "file"))
            os.replace(assembled, named)
            mt = c.get("mtime")
            if mt:
                try:
                    os.utime(named, (float(mt), float(mt)))
                except (OSError, ValueError):
                    pass
            dest, _ = inbox.save(named, c["kind"], (c.get("klass") or "").strip() or None,
                                 source=getattr(self, "_device", "laptop"))
            shutil.rmtree(folder, ignore_errors=True)
            if c["kind"] == "syllabus":                 # its dates show up on the PC to tick (nothing added on its own)
                try:
                    inbox.queue_dates(dest, (c.get("klass") or "").strip() or None)
                except Exception:
                    pass
            return f"saved to {inbox.rel(dest)}" + ("; Archie types it out" if c["kind"] == "recording"
                                                     else "; its dates are waiting on the PC to tick" if c["kind"] == "syllabus" else "")
        ideas = c.get("folder") == "ideas"
        base_folder = self._folder(klass, c.get("folder"))
        own = bool(c.get("own")) or bool(re.search(r"Recording \d{14}|\b20\d{6} \d{6}\.|\(20\d\d-\d\d-\d\d \d{1,2}\.\d\d ?[AP]M\)\.\w+$", name))
        board = bool(re.search(r"\bboard \(?20\d\d", name, re.I))
        # The professor's files for a class (slides, PDFs, handouts, their recordings) go in Materials,
        # where the lecture review lines them up with your recording. Your own recordings are named
        # "Recording <date><time>"; any other audio filed under a class is the professor's.
        material = bool(klass) and not ideas and (ext in MATERIAL_EXT or (ext in AUDIO_EXT and not own)
                                                  or (ext in PAGE_EXT and not board and not own))
        if material:
            dest_dir = os.path.join(base_folder, "Materials")
        elif ideas:
            dest_dir = base_folder                # Ideas: the recording, photos and notes side by side
        elif ext in AUDIO_EXT:
            # Archie's listener turns recordings in Lectures\<class> into lecture notes, and ones in a
            # "Voice inbox" into voice notes, so the recording goes there and the note comes from that.
            dest_dir = base_folder if klass else os.path.join(base_folder, "Voice inbox")
        elif ext == ".md":
            dest_dir = base_folder
        else:
            dest_dir = os.path.join(base_folder, "Files")
        os.makedirs(dest_dir, exist_ok=True)
        dest = _unique(os.path.join(dest_dir, name if ext != ".md" else f"{day} {name}"))
        shutil.move(assembled, dest)
        mt = c.get("mtime")
        if mt:
            try:
                os.utime(dest, (float(mt), float(mt)))
            except (OSError, ValueError):
                pass
        shutil.rmtree(folder, ignore_errors=True)
        if inbox:
            try:
                inbox.remember(dest, "file", klass)
            except Exception:
                pass
        if ext in AUDIO_EXT and not material:
            return "saved; Archie will type it out"
        if ext == ".md":
            return "saved as a note"
        stem = os.path.splitext(name)[0]
        note_path = _unique(os.path.join(base_folder, f"{day} {_safe(stem, 'File')}.md"))
        fname = os.path.basename(dest)
        size = os.path.getsize(dest)
        tags = "lecture-file, archie-lite" if klass else "file, archie-lite"
        lines = ["---", f"tags: [{tags}]"] + ([f'class: "{klass}"'] if klass else []) + [
            f"date: {day}", f'file: "[[{fname}]]"', f"source: Archie Lite ({getattr(self, '_device', 'laptop')})", "---", "", f"# {stem}", "",
            f"- **File:** [[{fname}]] ({size / 1048576:.1f} MB)" if size >= 1048576 else f"- **File:** [[{fname}]] ({max(1, size // 1024)} KB)",
            f"- **Class:** {klass}" if klass else "", f"- **Dropped:** {day}, from the {getattr(self, '_device', 'laptop')}",
            "- **Lecture review:** Archie lines this up with the lecture it belongs to" if material else "", ""]
        if ext in EMBED_EXT:
            lines += [f"![[{fname}]]", ""]
        if ext in TEXT_EXT:
            try:
                with open(dest, encoding="utf-8", errors="replace") as f:
                    txt = f.read(200_000)
                lines += ["## Text", "", txt]
            except OSError:
                pass
        with open(note_path, "w", encoding="utf-8") as f:
            f.write("\n".join(l for l in lines if l is not None) + "\n")
        if material:
            return "saved to the class's materials, with a note; Archie adds it to the lecture review"
        return "saved with a note"

    def _saved_dir(self):
        w = self.app.world
        mod = sys.modules.get(type(w).__module__) if w else None
        return getattr(mod, "SAVED_DIR", None)

    def articles(self, want):
        """The saved articles' text, for reading offline on the laptop."""
        root = self._saved_dir()
        out, total = {}, 0
        if not root:
            return {"ok": False, "error": "Archie World isn't running"}
        real = os.path.realpath(root)
        for rel in list(want)[:30]:
            p = os.path.realpath(os.path.join(root, *str(rel).split("/")))
            if not p.startswith(real + os.sep) or not p.endswith(".md") or not os.path.isfile(p):
                continue
            with open(p, encoding="utf-8", errors="replace") as f:
                txt = f.read(300_000)
            out[rel] = txt
            total += len(txt)
            if total > 3_000_000:
                break
        return {"ok": True, "articles": out}

    # ----- World for the laptop (news + governments, the same as Feather's snapshot) ----------------
    def world_pack(self, want_govs):
        w = self.app.world
        if not w:
            return {"ok": False, "error": "Archie World isn't running"}
        st = w.store
        stories = []
        for c in st.q("SELECT * FROM clusters WHERE last>? ORDER BY n_sources DESC, last DESC LIMIT 250",
                      (time.time() - 72 * 3600,)):
            its = st.q("SELECT source,title,title_en,summary,url,published FROM items WHERE cluster=? "
                       "ORDER BY published DESC LIMIT 6", (c["id"],))
            seen, items = set(), []
            for i in its:
                if i["source"] in seen:
                    continue
                seen.add(i["source"])
                items.append({"source": i["source"], "title": i["title_en"] or i["title"], "summary": (i["summary"] or "")[:240],
                              "url": i["url"], "t": i["published"]})
            stories.append({"title": c["title"], "place": c["place"], "cc": c["cc"], "region": c["region"],
                            "topic": c["topic"], "first": c["first"], "last": c["last"],
                            "n": max(c["n_sources"] or 1, len(items)), "items": items})
        rss = [r for r in (getattr(w, "sources", {}) or {}).get("rss", []) if r.get("url") and not r.get("off")]
        pack = {"at": int(time.time()), "stories": stories,
                "sources": [{"name": r.get("name"), "url": r.get("url")} for r in rss]}
        if want_govs:
            pack["govs"] = self._govs(w)
        raw = gzip.compress(json.dumps(pack, ensure_ascii=False).encode("utf-8"), 6)
        return {"ok": True, "gz": base64.b64encode(raw).decode("ascii"), "stories": len(stories),
                "govs": len(pack.get("govs") or [])}

    def _govs(self, w):
        mod = sys.modules.get(type(w).__module__)
        web = os.path.join(getattr(mod, "WORLD_DIR", os.path.join(HERE, "World")), "web")
        live, cia, us = w.store.kv_get("govs_live") or {}, w.store.kv_get("cia_leaders") or {}, w.store.kv_get("us_cabinet") or {}
        try:
            with open(os.path.join(web, "data", "govs.json"), encoding="utf-8") as f:
                static = json.load(f)
        except (OSError, ValueError):
            static = []
        out = []
        for g in static:
            iso, L = g.get("iso2"), live.get(g.get("iso2")) or {}
            cab = us if iso == "US" else cia.get(g.get("gec")) or {}
            name = g.get("name") if (g.get("name") or "none").lower() != "none" else (g.get("long") or iso)
            out.append({"iso2": iso, "name": name, "long": g.get("long"), "label": g.get("label"), "capital": g.get("capital"),
                        "intro": (g.get("intro") or "")[:1800], "hos": L.get("hos") or [], "hog": L.get("hog") or [],
                        "hosOffice": L.get("hosOffice"), "hogOffice": L.get("hogOffice"),
                        "cabinet": [{"label": gr.get("label", ""), "people": [{"title": p.get("title"), "name": p.get("name")}
                                                                            for p in (gr.get("people") or [])[:80]]}
                                    for gr in (cab.get("groups") or [])],
                        "cabinet_source": cab.get("source"), "cabinet_updated": cab.get("updated")})
        return out

    def flag(self, iso):
        if not re.fullmatch(r"[A-Z]{2}", iso):
            return {"ok": False}
        w = self.app.world
        mod = sys.modules.get(type(w).__module__) if w else None
        p = os.path.join(getattr(mod, "WORLD_DIR", os.path.join(HERE, "World")), "web", "flags", iso + ".svg")
        try:
            with open(p, encoding="utf-8") as f:
                return {"ok": True, "svg": f.read(300_000)}
        except OSError:
            return {"ok": False}

    # ----- Archie Doctor ------------------------------------------------------------------------
    def _hook_world(self):
        w = getattr(self.app, "world", None)
        if w is not None and getattr(w, "lite_status", None) != self.lite_status:
            try:
                w.lite_status = self.lite_status
            except Exception:
                pass

    def lite_status(self):
        cl = dict(self.state.get("client") or {})
        try:
            man = lite_manifest() if os.path.isdir(LITE_DIR) else {}
            build = hashlib.sha256(json.dumps(man, sort_keys=True).encode()).hexdigest() if man else None
        except Exception:
            build = None
        inbox = 0
        try:
            inbox = len([d for d in os.listdir(INBOX) if os.path.isdir(os.path.join(INBOX, d))])
        except OSError:
            pass
        clients = []
        for c in sorted((self.state.get("clients") or {}).values(), key=lambda c: -(c.get("seen") or 0)):
            c = dict(c)
            c["up_to_date"] = bool(build and c.get("build") == build) if c.get("build") else None
            clients.append(c)
        phone = getattr(self, "phone", None)
        return {"paired": True, "client": cl or None, "up_to_date": bool(build and cl.get("build") == build),
                "server_error": self.error, "files_arriving": inbox, "port": proto.PORT, "clients": clients,
                "phone": phone.status() if phone else {"error": getattr(self, "_phone_err", "not started")}}

    def lite_files(self, want):
        """The Archie Lite files the laptop asked for (only ones listed in the manifest)."""
        man = lite_manifest()
        files = {}
        for rel in list(want)[:200]:
            rel = str(rel)
            if rel not in man:
                continue
            with open(os.path.join(LITE_DIR, *rel.split("/")), "rb") as f:
                data = f.read()
            if hashlib.sha256(data).hexdigest() != man[rel]:
                continue                     # changed while we read it; next sync gets it
            files[rel] = {"sha": man[rel], "b64": base64.b64encode(data).decode("ascii")}
        return {"ok": True, "files": files}

    def activity(self, days=7):
        """Things that happened on the PC lately, for the phone's "since you last opened" box."""
        app, out, cut = self.app, [], time.time() - days * 86400
        try:
            for c in (app.mail.state().get("cards") or []) if getattr(app, "mail", None) else []:
                if (c.get("at") or 0) >= cut:
                    out.append({"at": c["at"], "kind": "mail", "text": f"{c.get('from')}: {c.get('subject')}", "go": "mail"})
        except Exception:
            pass
        try:
            for r in app.inbox.recent(days) if getattr(app, "inbox", None) else []:
                where = r.get("klass") or os.path.basename(os.path.dirname(r["dest"]))
                out.append({"at": r["at"], "kind": "filed", "text": f"{os.path.basename(r['dest'])} filed to {where}"})
        except Exception:
            pass
        try:                                       # lecture reviews that got written (the lecture is typed up and lined up)
            lec = os.path.join(self._base(), "Lectures")
            for dp, _, fns in os.walk(lec) if os.path.isdir(lec) else []:
                for fn in fns:
                    if fn.endswith("(review).md"):
                        mt = os.path.getmtime(os.path.join(dp, fn))
                        if mt >= cut:
                            out.append({"at": mt, "kind": "lecture", "text": fn[:-len(" (review).md")] + " is typed up"})
        except Exception:
            pass
        return sorted(out, key=lambda a: a["at"])[-40:]

    def snapshot(self):
        app = self.app
        today = datetime.date.today()
        tasks = [{"text": t["text"], "done": t["done"], "due": t["due"].isoformat() if t["due"] else None}
                 for t in app.tasks.load()]
        deadlines = [{"date": d.isoformat(), "what": w} for d, w in app.deadlines.load()]
        try:                                   # exams, tests and quizzes count down on the phone and laptop too
            import archie_examprep
            have = {(x["date"], x["what"].lower()) for x in deadlines}
            deadlines += [x for x in archie_examprep.countdowns(app.calendar) if (x["date"], x["what"].lower()) not in have]
            deadlines.sort(key=lambda x: x["date"])
        except Exception:
            pass
        out = {"at": time.time(), "pc": socket.gethostname(), "today": today.isoformat(),
               "calendar": app.calendar.load(), "tasks": tasks, "deadlines": deadlines,
               "brief": None, "saved": [], "follow": [], "model": app.cfg.get("model"),
               "addresses": self.addresses()}
        try:                                       # mail that got a card on the PC: the laptop shows it too
            out["mail_alerts"] = app.mail.alerts() if getattr(app, "mail", None) else []
            out["mail_cards"] = app.mail.phone_cards() if getattr(app, "mail", None) else []
            out["activity"] = self.activity()
        except Exception:
            out["mail_alerts"] = []
            out["mail_cards"] = []
        try:
            out["lite_files"] = lite_manifest() if os.path.isdir(LITE_DIR) else {}
        except Exception as e:
            out["lite_files"] = {}
            out["lite_files_error"] = str(e)
        w = app.world
        if w:
            try:
                b = w.news_brief()
                if not b.get("error"):
                    keep = ("now", "take", "coming", "global", "home", "local", "edition", "outlets", "follow",
                            "following", "big_new")
                    out["brief"] = {k: b.get(k) for k in keep}
            except Exception as e:
                out["brief_error"] = str(e)
            out["follow"] = list(w.watch.get("follow", []))
            try:
                out["saved"] = [{"name": s["name"], "time": s["time"],
                                 "md": s["png"][:-4] + ".md" if s.get("png", "").endswith(".png") else None}
                                for s in w.saved_list()[:60]]
            except Exception:
                pass
        return out

    def chat(self, q, history):
        from archie_brain import quick_chat
        app = self.app
        today = datetime.date.today()
        try:                                       # "move X to 6pm", "cancel Y": change the calendar for real
            import archie_calchat
            done = archie_calchat.handle(q, app.calendar, lambda p: quick_chat(
                app.cfg["model"], p, max_tokens=200, timeout=120, json_mode=True, temperature=0.1))
            if done:
                return {"ok": True, "answer": done, "model": app.cfg["model"]}
        except Exception:
            pass
        ctx = [f"Today is {today:%A %B %d, %Y}. The user is asking from their laptop (Archie Lite)."]
        ctx.append("You can't change the calendar or the to-do list from this chat; never say you did. To change an "
                   "event, the user says e.g. 'move <event> to <day> <time>'.")
        todo = [t["text"] + (f" (due {t['due']})" if t["due"] else "") for t in app.tasks.load() if not t["done"]]
        if todo:
            ctx.append("Open to-dos: " + "; ".join(todo[:12]))
        dl = [f"{w} on {d:%b %d}" for d, w in app.deadlines.load() if d >= today][:5]
        if dl:
            ctx.append("Deadlines: " + "; ".join(dl))
        try:
            ev = app.calendar.between(today, today + datetime.timedelta(days=14))[:15]
            if ev:
                ctx.append("Calendar, next two weeks: " + "; ".join(
                    f"{e['date']} {e.get('time') or ''} {e['title']}".replace("  ", " ") for e in ev))
        except Exception:
            pass
        lines = []
        for m in history[-6:]:
            who = "User" if m.get("role") == "user" else "Archie"
            lines.append(f"{who}: {str(m.get('text', ''))[:1500]}")
        prompt = "\n".join(ctx) + "\n\n" + "\n".join(lines + [f"User: {q[:3000]}", "Archie:"])
        try:
            a = quick_chat(app.cfg["model"], prompt, max_tokens=700, timeout=180,
                           system=app.cfg.get("system_prompt"), num_ctx=app.cfg.get("context_tokens"))
            return {"ok": True, "answer": (a or "").strip(), "model": app.cfg["model"]}
        except Exception as e:
            return {"ok": False, "error": str(e)}

