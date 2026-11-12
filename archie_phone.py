"""
archie_phone.py - Archie on your phone (2026-11-09).

  * A small web server on this PC (127.0.0.1:47330) that only Tailscale reaches: "Set up phone.bat"
    runs `tailscale serve`, which gives the PC a real https address on your tailnet
    (https://<pc>.<tailnet>.ts.net) and passes requests here. Nothing listens on your network or the
    internet. Tailscale tells this server who is asking; only your own Tailscale login gets in.
  * The phone app (D:\\Archie\\phone) installs from Chrome to the home screen, works offline, and
    syncs exactly like Archie Lite on the laptops (it uses the same sync code, archie_sync.py).
  * Notifications: classes 15 minutes ahead, other events 30, a morning summary of what's due, and
    "lecture notes ready" when Archie finishes typing out a recording. Sent with Web Push
    (archie_webpush.py), encrypted for your phone only.
"""

import datetime
import json
import mimetypes
import os
import re
import sys
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import archie_webpush as webpush

HERE = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(HERE, "phone")
STATE = os.path.join(HERE, "phone_state.json")
PORT = 47330
FEATHER_PORT = 47331   # Feather's phone app on its own address (https://<pc>.<tailnet>.ts.net:8443), so it installs as its own app
SYNC_OPS = ("sync", "chat", "articles", "world", "flag", "file_chunk", "ping", "feather", "shelf", "shelf_do")
FEATHER_WEB = os.path.join(os.path.dirname(HERE), "Feather", "phone")          # Feather on the phone: /feather/
FEATHER_FONTS = os.path.join(os.path.dirname(HERE), "Feather", "app", "web", "fonts")
LEAD = {"class": 15, "lab": 15, "exam": 15, "test": 15, "quiz": 15}


class PhoneService:
    def __init__(self, sync):
        self.sync = sync
        self.app = sync.app
        self.state = self._load()
        self.vapid = webpush.Vapid(self.state.get("vapid"))
        if not self.state.get("vapid"):
            self.state["vapid"] = self.vapid.private_b64
            self._save()
        self.lock = threading.Lock()
        self.httpd = None
        self.error = ""
        self.last_push = None

    # ----- state ------------------------------------------------------------------------------------
    def _load(self):
        try:
            with open(STATE, encoding="utf-8") as f:
                st = json.load(f)
        except (OSError, ValueError):
            st = {}
        for k, v in (("subs", []), ("sent", {}), ("owner", None), ("lectures_seen", {}), ("seen", None)):
            st.setdefault(k, v)
        return st

    def _save(self):
        tmp = STATE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.state, f, indent=1)
        os.replace(tmp, STATE)

    # ----- web server ---------------------------------------------------------------------------------
    def start(self):
        svc = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _send(self, code, body, ctype="application/json", cache="no-cache"):
                if not isinstance(body, (bytes, bytearray)):
                    body = json.dumps(body, ensure_ascii=False).encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", cache)
                self.send_header("X-Content-Type-Options", "nosniff")
                self.end_headers()
                self.wfile.write(body)

            def _who(self):
                """Your Tailscale login (added by `tailscale serve`), "local" for this PC, or None."""
                if self.client_address[0] not in ("127.0.0.1", "::1"):
                    return None
                if self.headers.get("Tailscale-Funnel-Request"):
                    return None                          # never from the public internet
                login = self.headers.get("Tailscale-User-Login")
                if login:
                    return login
                host = (self.headers.get("Host") or "").split(":")[0]
                return "local" if host in ("127.0.0.1", "localhost") else None

            def _allowed(self):
                who = self._who()
                if not who:
                    return False
                if who == "local":
                    return True
                with svc.lock:
                    if not svc.state.get("owner"):
                        svc.state["owner"] = who           # the first Tailscale login to open it owns it
                        svc._save()
                    return who.lower() == str(svc.state["owner"]).lower()

            def do_GET(self):
                if not self._allowed():
                    return self._send(403, b"Archie: not allowed", "text/plain")
                path = urllib.parse.urlparse(self.path).path
                if path == "/feather":
                    self.send_response(301)
                    self.send_header("Location", "/feather/")
                    self.end_headers()
                    return
                if path.startswith("/feather/"):  # Feather's own app: its files, its fonts, its index for its pages
                    rel = path[len("/feather/"):]
                    base = FEATHER_FONTS if rel.startswith("fonts/") else FEATHER_WEB
                    if rel.startswith("fonts/"):
                        rel = rel[len("fonts/"):]
                    full = os.path.normpath(os.path.join(base, urllib.parse.unquote(rel or "index.html")))
                    if not full.startswith(os.path.normpath(base) + os.sep) or not os.path.isfile(full):
                        if os.path.splitext(rel)[1]:
                            return self._send(404, b"not found", "text/plain")
                        full = os.path.join(FEATHER_WEB, "index.html")
                    with open(full, "rb") as f:
                        body = f.read()
                    ctype = {".webmanifest": "application/manifest+json", ".js": "text/javascript", ".woff2": "font/woff2", ".ttf": "font/ttf",
                             ".svg": "image/svg+xml"}.get(os.path.splitext(full)[1]) or mimetypes.guess_type(full)[0] or "application/octet-stream"
                    if ctype.startswith("text/") or ctype.endswith(("javascript", "json")):
                        ctype += "; charset=utf-8"
                    cache = "public, max-age=604800" if "/fonts/" in path or path.endswith(".png") else "no-cache"
                    return self._send(200, body, ctype, cache)
                if path.startswith("/fonts/"):
                    base = os.path.join(os.path.dirname(HERE), "ArchieLite", "web", "fonts")
                    rel = path[len("/fonts/"):]
                else:
                    base, rel = WEB, path.lstrip("/") or "index.html"
                full = os.path.normpath(os.path.join(base, urllib.parse.unquote(rel)))
                if not full.startswith(os.path.normpath(base) + os.sep) or not os.path.isfile(full):
                    full = os.path.join(WEB, "index.html") if not os.path.splitext(rel)[1] else None
                    if not full:
                        return self._send(404, b"not found", "text/plain")
                with open(full, "rb") as f:
                    body = f.read()
                ctype = {".webmanifest": "application/manifest+json", ".js": "text/javascript"}.get(
                    os.path.splitext(full)[1]) or mimetypes.guess_type(full)[0] or "application/octet-stream"
                if ctype.startswith("text/") or ctype.endswith(("javascript", "json")):
                    ctype += "; charset=utf-8"
                cache = "public, max-age=604800" if "/fonts/" in path or path.endswith(".png") else "no-cache"
                return self._send(200, body, ctype, cache)

            def do_POST(self):
                if not self._allowed():
                    return self._send(403, {"ok": False, "error": "not allowed"})
                n = int(self.headers.get("Content-Length") or 0)
                if n <= 0 or n > 12 * 1024 * 1024:
                    return self._send(400, {"ok": False, "error": "bad size"})
                try:
                    msg = json.loads(self.rfile.read(n))
                except ValueError:
                    return self._send(400, {"ok": False, "error": "bad json"})
                try:
                    return self._send(200, svc.handle(msg, self._who()))
                except Exception as e:
                    svc.error = f"{type(e).__name__}: {e}"
                    return self._send(500, {"ok": False, "error": svc.error})

        class FH(H):
            """Feather's own address: only Feather's app and Feather's sync, nothing of Archie's."""
            def do_GET(self):
                path = urllib.parse.urlparse(self.path).path
                if not (path == "/feather" or path.startswith("/feather/")):
                    if not self._allowed():
                        return self._send(403, b"Feather: not allowed", "text/plain")
                    self.send_response(302)
                    self.send_header("Location", "/feather/")
                    self.end_headers()
                    return
                return H.do_GET(self)

            def do_POST(self):
                n = int(self.headers.get("Content-Length") or 0)
                if not self._allowed():
                    return self._send(403, {"ok": False, "error": "not allowed"})
                if n <= 0 or n > 12 * 1024 * 1024:
                    return self._send(400, {"ok": False, "error": "bad size"})
                try:
                    msg = json.loads(self.rfile.read(n))
                except ValueError:
                    return self._send(400, {"ok": False, "error": "bad json"})
                if msg.get("op") != "feather":
                    return self._send(403, {"ok": False, "error": "not here"})
                try:
                    return self._send(200, svc.handle(msg, self._who()))
                except Exception as e:
                    svc.error = f"{type(e).__name__}: {e}"
                    return self._send(500, {"ok": False, "error": svc.error})

        try:
            self.fhttpd = ThreadingHTTPServer(("127.0.0.1", FEATHER_PORT), FH)
            self.fhttpd.daemon_threads = True
            threading.Thread(target=self.fhttpd.serve_forever, daemon=True, name="feather-phone-web").start()
        except OSError as e:
            self.error = f"feather phone address: {e}"
        self.httpd = ThreadingHTTPServer(("127.0.0.1", PORT), H)
        self.httpd.daemon_threads = True
        threading.Thread(target=self.httpd.serve_forever, daemon=True, name="phone-web").start()
        threading.Thread(target=self._notify_loop, daemon=True, name="phone-push").start()
        return self

    # ----- requests ---------------------------------------------------------------------------------------
    def handle(self, msg, who):
        op = msg.get("op")
        self.state["seen"] = time.time()
        if op in SYNC_OPS:
            if op == "sync" and isinstance(msg.get("client"), dict):
                msg["client"].setdefault("host", "Phone")
            return self.sync.handle(msg)
        if op == "push_key":
            return {"ok": True, "key": self.vapid.public_b64}
        if op == "push_subscribe":
            sub = msg.get("sub") or {}
            if not (str(sub.get("endpoint", "")).startswith("https://") and (sub.get("keys") or {}).get("p256dh")):
                return {"ok": False, "error": "bad subscription"}
            with self.lock:
                subs = [s for s in self.state["subs"] if s["endpoint"] != sub["endpoint"]]
                subs.append({"endpoint": sub["endpoint"], "keys": {"p256dh": sub["keys"]["p256dh"], "auth": sub["keys"]["auth"]},
                             "at": time.time(), "label": str(msg.get("label") or "phone")[:60]})
                self.state["subs"] = subs[-5:]
                self._save()
            return {"ok": True, "subs": len(self.state["subs"])}
        if op == "push_unsubscribe":
            with self.lock:
                self.state["subs"] = [s for s in self.state["subs"] if s["endpoint"] != msg.get("endpoint")]
                self._save()
            return {"ok": True}
        if op == "push_test":
            return {"ok": True, "sent": self.push("Archie", "Notifications work. You'll hear from me before class.", "today")}
        if op == "status":
            return {"ok": True, "owner": self.state.get("owner"), "who": who, "subs": len(self.state["subs"]),
                    "pc": self.sync.snapshot().get("pc"), "error": self.error}
        return {"ok": False, "error": "unknown request"}

    # ----- notifications -----------------------------------------------------------------------------------
    def push(self, title, body, tab="today", tag=None, url=None):
        sent = 0
        msg = {"title": title, "body": body, "tab": tab, "tag": tag or title}
        if url:
            msg["url"] = url                    # tapping it opens this link (an email in Gmail) instead of Archie
        for sub in list(self.state["subs"]):
            try:
                code = webpush.send(sub, msg, self.vapid)
            except Exception as e:
                self.error = f"push: {e}"
                continue
            if code in (404, 410):              # the phone dropped this subscription
                with self.lock:
                    self.state["subs"] = [s for s in self.state["subs"] if s["endpoint"] != sub["endpoint"]]
                    self._save()
            elif 200 <= code < 300:
                sent += 1
            else:
                self.error = f"push: HTTP {code}"
        if sent:
            self.last_push = (time.time(), title)
        return sent

    def _once(self, key):
        with self.lock:
            if key in self.state["sent"]:
                return False
            self.state["sent"][key] = time.time()
            cut = time.time() - 5 * 86400
            self.state["sent"] = {k: v for k, v in self.state["sent"].items() if v > cut}
            self._save()
            return True

    def _notify_loop(self):
        time.sleep(20)
        while True:
            try:
                if self.state["subs"]:
                    self.check_reminders()
                    self.check_lectures()
            except Exception as e:
                self.error = f"reminders: {type(e).__name__}: {e}"
            time.sleep(60)

    def check_reminders(self, now=None):
        import archie_calendar as cal
        now = now or datetime.datetime.now()
        app = self.app
        for e in app.calendar.on(now.date()):
            if not e.get("time"):
                continue
            h, m = map(int, e["time"].split(":"))
            t0 = datetime.datetime.combine(now.date(), datetime.time(h, m))
            lead = LEAD.get(e.get("kind"), 30)
            if t0 - datetime.timedelta(minutes=lead) <= now < t0 + datetime.timedelta(minutes=2):
                if self._once(f"ev:{e.get('id')}:{e['date']}:{e['time']}"):
                    mins = max(0, int((t0 - now).total_seconds() // 60))
                    label = cal.KINDS.get(e.get("kind"), ("Event",))[0]
                    extra = " · tap to record" if e.get("kind") in ("class", "lab") else ""
                    self.push(f"{e['title']} {'now' if mins == 0 else f'in {mins} min'}",
                              f"{label} at {cal.fmt_time(e['time'])}{extra}", "class" if extra else "today")
        if now.hour >= 8 and self._once("day:" + now.date().isoformat()):
            today, tomorrow = now.date(), now.date() + datetime.timedelta(days=1)
            lines = [f"Due today: {w}" for d, w in app.deadlines.load() if d == today]
            lines += [f"Due tomorrow: {w}" for d, w in app.deadlines.load() if d == tomorrow]
            lines += [f"{cal.KINDS.get(e['kind'], ('Event',))[0]} tomorrow: {e['title']}" for e in app.calendar.on(tomorrow)
                      if e.get("kind") in ("exam", "test", "quiz")]
            tasks = [t["text"] for t in app.tasks.load() if not t["done"] and t["due"] == today]
            if tasks:
                lines.append(f"{len(tasks)} to-do{'s' if len(tasks) != 1 else ''} due today")
            classes = [e["title"] for e in app.calendar.on(today) if e.get("kind") in ("class", "lab")]
            if classes:
                lines.insert(0, "Classes: " + ", ".join(classes))
            if lines:
                self.push("Today", "\n".join(lines[:5]), "today", "morning")

    def check_lectures(self):
        """A lecture note Archie just wrote (not one of ours from the phone or laptop) -> notification."""
        base = self.sync._base()
        root = os.path.join(base, "Lectures")
        if not os.path.isdir(root):
            return
        ours = {os.path.normcase(r.get("path", "")) for r in self.sync.state.get("notes", {}).values()}
        seen = self.state["lectures_seen"]
        first = not self.state.get("lectures_init")          # the first scan only learns what's already there
        for klass in os.listdir(root):
            d = os.path.join(root, klass)
            if not os.path.isdir(d):
                continue
            for fn in os.listdir(d):
                if not fn.endswith(".md") or fn.endswith("(mind map).md") or not re.match(r"\d{4}-\d\d-\d\d ", fn):
                    continue
                p = os.path.join(d, fn)
                key = os.path.normcase(p)
                if key in seen or key in ours:
                    continue
                try:
                    with open(p, encoding="utf-8", errors="replace") as f:
                        head = f.read(600)
                except OSError:
                    continue
                seen[key] = time.time()
                if first or "source: Archie Lite" in head or time.time() - os.path.getmtime(p) > 6 * 3600:
                    continue                                 # older ones, and our own notes and drops
                if "type: lecture-review" in head:
                    self.push(f"Lecture review ready · {klass}", fn[11:-len(" (review).md")] if fn.endswith(" (review).md") else fn[11:-3],
                              "notes", "review:" + fn)
                    continue
                self.push(f"Lecture notes ready · {klass}", fn[11:-3], "notes", "lecture:" + fn)
        with self.lock:
            self.state["lectures_init"] = True
            self._save()

    def status(self):
        return {"subs": len(self.state["subs"]), "owner": self.state.get("owner"), "seen": self.state.get("seen"),
                "last_push": self.last_push, "error": self.error}
