"""Archie's mail watcher: checks your Gmail (your Outlook forwards into it) and turns the mail that matters into a card.

Read-only: Archie opens the inbox read-only and reads with BODY.PEEK, so nothing is marked read, moved or deleted, and it
never sends anything. The Gmail app password is stored on this PC encrypted with Windows (DPAPI): only your Windows
account on this PC can unlock it. Set it up with Tools\\Connect Gmail.bat (you type the password there yourself).

A card for:
  - mail from school (any .edu address, plus the domains/addresses you add): your professors, the school
  - mail with attachments (files, not signature logos), from people (not newsletters)
  - mail that mentions a date with a due / exam / deadline / interview / shift kind of word
Skipped: newsletters and promotions (Gmail's Promotions/Social/Updates tabs) unless they're from school.
Quiet hours 11 PM - 7 AM: cards wait until morning, except mail from your professors.
"""
import base64
import datetime
import email
import email.header
import email.utils
import html
import imaplib
import json
import os
import re
import sys
import threading
import time
import urllib.parse

HOST = "imap.gmail.com"
CHECK_EVERY = 180            # seconds
QUIET = (23, 7)              # 11 PM to 7 AM
KEEP_ALERTS = 15
MIN_ATTACH = 30 * 1024       # smaller images are signature logos
DATE_WORDS = re.compile(r"\b(due|deadline|exam|midterm|final|quiz|test|assignment|submit|interview|appointment|"
                        r"shift|schedule|meeting|office hours|reschedul\w*|cancel\w*|class is)\b", re.I)
DATE_LIKE = re.compile(r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s+\d{1,2}\b|\b\d{1,2}/\d{1,2}\b|"
                       r"\b(?:mon|tues|wednes|thurs|fri|satur|sun)day\b|\btomorrow\b|\btonight\b|\bnext week\b", re.I)
NOREPLY = re.compile(r"no-?reply|donotreply|do-not-reply|notifications?@|mailer|bounce", re.I)


# ---- the password, encrypted with Windows (DPAPI) ------------------------------------------------------
if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    class _Blob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    def _blob(b):
        buf = ctypes.create_string_buffer(b, len(b))
        return _Blob(len(b), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char))), buf

    def protect(data):
        src, _keep = _blob(data)
        out = _Blob()
        if not ctypes.windll.crypt32.CryptProtectData(ctypes.byref(src), "Archie Gmail", None, None, None, 0x1, ctypes.byref(out)):
            raise OSError("Windows couldn't encrypt the password")
        try:
            return ctypes.string_at(out.pbData, out.cbData)
        finally:
            ctypes.windll.kernel32.LocalFree(out.pbData)

    def unprotect(data):
        src, _keep = _blob(data)
        out = _Blob()
        if not ctypes.windll.crypt32.CryptUnprotectData(ctypes.byref(src), None, None, None, None, 0x1, ctypes.byref(out)):
            raise OSError("Windows couldn't unlock the saved password (was it saved by another Windows account?)")
        try:
            return ctypes.string_at(out.pbData, out.cbData)
        finally:
            ctypes.windll.kernel32.LocalFree(out.pbData)
else:                                   # tests on other systems only; Archie itself runs on Windows
    def protect(data):
        return b"TEST" + base64.b64encode(data)

    def unprotect(data):
        return base64.b64decode(data[4:])


def _dec(v):
    try:
        return str(email.header.make_header(email.header.decode_header(v or "")))
    except Exception:
        return str(v or "")


def _text(msg):
    """The readable text of a message (plain part, or the HTML part with tags stripped)."""
    plain, htm = [], []
    for part in msg.walk() if msg.is_multipart() else [msg]:
        if part.get_content_maintype() == "multipart" or part.get_filename():
            continue
        ct = part.get_content_type()
        try:
            payload = part.get_payload(decode=True) or b""
            s = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
        except Exception:
            continue
        (plain if ct == "text/plain" else htm if ct == "text/html" else []).append(s)
    if plain:
        return "\n".join(plain).strip()
    s = "\n".join(htm)
    s = re.sub(r"(?is)<(script|style).*?</\1>", " ", s)
    s = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</tr>", "\n", s)
    s = html.unescape(re.sub(r"<[^>]+>", " ", s))
    return re.sub(r"[ \t]+", " ", re.sub(r"\n\s*\n+", "\n\n", s)).strip()


def _safe(s, fallback="mail"):
    s = re.sub(r'[<>:"/\\|?*\x00-\x1f]', " ", str(s or "")).strip().strip(".")
    return re.sub(r"\s+", " ", s)[:70] or fallback


class Mail:
    def __init__(self, app_dir, on_card=lambda m: None, push=lambda title, body, prof: None, report=lambda m: None, now=None):
        self.app_dir = app_dir
        self.state_path = os.path.join(app_dir, "mail_state.json")
        self.secret_path = os.path.join(app_dir, "mail_secret.bin")
        self.folder = os.path.join(app_dir, "Mail")
        self.on_card = on_card              # (message dict) -> shows the card on the PC (called from this thread)
        self.push = push                    # phone notification
        self.report = report
        self.now = now or datetime.datetime.now
        self.lock = threading.Lock()
        self.error = None
        self.last_check = 0

    # ---- settings ---------------------------------------------------------------------------------------
    def state(self):
        try:
            with open(self.state_path, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return {}

    def _save(self, st):
        with open(self.state_path + ".tmp", "w", encoding="utf-8") as f:
            json.dump(st, f, indent=1)
        os.replace(self.state_path + ".tmp", self.state_path)

    def configured(self):
        return os.path.exists(self.secret_path) and bool(self.state().get("address"))

    def save_login(self, address, password, school=None, professors=None):
        with self.lock:
            st = self.state()
            if st.get("address", "").lower() != address.lower():
                st.pop("uidvalidity", None)
                st.pop("last_uid", None)
            st["address"] = address.strip()
            if school is not None:
                st["school"] = school
            if professors is not None:
                st["professors"] = professors
            with open(self.secret_path + ".tmp", "wb") as f:
                f.write(protect(password.replace(" ", "").encode()))
            os.replace(self.secret_path + ".tmp", self.secret_path)
            self._save(st)

    def save_settings(self, school=None, professors=None):
        """Change the school domains / professors without touching the saved password."""
        with self.lock:
            st = self.state()
            if school is not None:
                st["school"] = school
            if professors is not None:
                st["professors"] = professors
            self._save(st)

    def forget(self):
        for p in (self.secret_path,):
            try:
                os.remove(p)
            except OSError:
                pass

    def _password(self):
        with open(self.secret_path, "rb") as f:
            return unprotect(f.read()).decode()

    # ---- who counts ------------------------------------------------------------------------------------------
    def is_school(self, addr, st=None):
        st = st or self.state()
        a = (addr or "").lower()
        dom = a.rsplit("@", 1)[-1]
        if dom.endswith(".edu"):
            return True
        for s in st.get("school") or []:
            s = s.lower().strip().lstrip("@")
            if s and (a == s or dom == s or dom.endswith("." + s)):
                return True
        return False

    def is_professor(self, addr, st=None):
        st = st or self.state()
        a = (addr or "").lower()
        if a in [p.lower().strip() for p in st.get("professors") or []]:
            return True
        return self.is_school(a, st) and not NOREPLY.search(a)

    def quiet(self, now=None):
        h = (now or self.now()).hour
        return h >= QUIET[0] or h < QUIET[1]

    # ---- reading one message -----------------------------------------------------------------------------
    def judge(self, raw, primary=True, uid=0):
        """The card for this message, or None if it doesn't need one."""
        msg = email.message_from_bytes(raw)
        st = self.state()
        name, addr = email.utils.parseaddr(_dec(msg.get("From")))
        subject = _dec(msg.get("Subject")).strip() or "(no subject)"
        text = _text(msg)
        mine = [st.get("address", "").lower()] + [a.lower() for a in st.get("mine") or []]
        fwd = re.match(r"\s*(fw|fwd)\s*:", subject, re.I) or addr.lower() in mine or msg.get("X-Forwarded-For")
        if fwd:                             # forwarded from Outlook: the real sender is in the forwarded header
            m = re.search(r"^\s*\*?From:\*?\s*(.+)$", text, re.M | re.I)
            if m:
                n2, a2 = email.utils.parseaddr(m.group(1).replace("mailto:", ""))
                if "@" in a2:
                    name, addr = n2 or name, a2
        bulk = bool(msg.get("List-Unsubscribe")) or (msg.get("Precedence") or "").lower() in ("bulk", "list")
        school, prof = self.is_school(addr, st), self.is_professor(addr, st)
        files = []
        for part in msg.walk():
            fn = part.get_filename()
            if not fn or part.get_content_maintype() == "multipart":
                continue
            data = part.get_payload(decode=True) or b""
            if part.get_content_maintype() == "image" and len(data) < MIN_ATTACH:
                continue                   # a logo in someone's signature
            files.append((_safe(_dec(fn), "attachment"), data))
        dated = bool(DATE_WORDS.search(subject + " " + text[:4000]) and DATE_LIKE.search(subject + " " + text[:4000]))
        why = []
        if prof:
            why.append("from your professor" if not NOREPLY.search(addr) else "from school")
        elif school:
            why.append("from school")
        if files and (not bulk or school):
            why.append(f"{len(files)} attachment" + ("s" if len(files) != 1 else ""))
        if dated and (not bulk or school):
            why.append("mentions a date")
        if not why or (not primary and not school):
            return None
        when = email.utils.parsedate_to_datetime(msg.get("Date")) if msg.get("Date") else None
        try:
            when = when.astimezone().replace(tzinfo=None) if when else self.now()
        except (ValueError, OverflowError):
            when = self.now()
        return {"uid": uid, "from": name or addr, "addr": addr, "subject": subject, "date": when.isoformat(timespec="minutes"),
                "why": why, "prof": prof, "school": school, "text": text[:20000],
                "snippet": re.sub(r"\s+", " ", text)[:280], "files": files,
                "msgid": (msg.get("Message-ID") or "").strip()}

    def keep(self, m):
        """Save the attachments and the text under Archie\\Mail\\<date> <subject>\\ (so the inbox card can file them)."""
        d = datetime.datetime.fromisoformat(m["date"])
        folder = os.path.join(self.folder, f"{d:%Y-%m-%d} {_safe(m['subject'])}")
        os.makedirs(folder, exist_ok=True)
        paths = []
        for fn, data in m.pop("files", []):
            p = os.path.join(folder, fn)
            stem, ext = os.path.splitext(p)
            i = 2
            while os.path.exists(p):
                p = f"{stem} ({i}){ext}"
                i += 1
            with open(p, "wb") as f:
                f.write(data)
            ts = d.timestamp()
            os.utime(p, (ts, ts))           # the file keeps the email's date (the lecture review uses it)
            paths.append(p)
        body = os.path.join(folder, "email.txt")
        with open(body, "w", encoding="utf-8") as f:
            f.write(f"From: {m['from']} <{m['addr']}>\nSubject: {m['subject']}\nDate: {m['date']}\n\n{m['text']}\n")
        m["attachments"] = paths
        m["body_path"] = body
        m["link"] = ("https://mail.google.com/mail/u/0/#search/" + urllib.parse.quote("rfc822msgid:" + m["msgid"].strip("<>"))
                     if m.get("msgid") else "https://mail.google.com/mail/u/0/#inbox")
        return m

    # ---- checking -----------------------------------------------------------------------------------------
    def _connect(self):
        st = self.state()
        im = imaplib.IMAP4_SSL(HOST, 993, timeout=60)
        try:
            im.login(st["address"], self._password())
        except imaplib.IMAP4.error as e:
            raise PermissionError("Gmail said no to the app password (" + str(e)[:80] + "). Run Tools\\Connect Gmail.bat again.")
        return im

    def test(self, address, password):
        im = imaplib.IMAP4_SSL(HOST, 993, timeout=30)
        try:
            im.login(address, password.replace(" ", ""))
            im.select("INBOX", readonly=True)
        finally:
            try:
                im.logout()
            except Exception:
                pass
        return True

    def check(self):
        """New mail since last time -> cards. The first check only remembers where the inbox is (no flood of old mail)."""
        if not self.configured():
            return []
        st = self.state()
        im = self._connect()
        out = []
        try:
            typ, _ = im.select("INBOX", readonly=True)
            uv = (im.untagged_responses.get("UIDVALIDITY") or [b"0"])[0]
            uv = int(uv.decode() if isinstance(uv, bytes) else uv)
            typ, data = im.uid("SEARCH", None, "ALL")
            uids = [int(x) for x in (data[0] or b"").split()]
            top = max(uids) if uids else 0
            if st.get("uidvalidity") != uv or "last_uid" not in st:
                st.update(uidvalidity=uv, last_uid=top, since=self.now().isoformat(timespec="minutes"))
                with self.lock:
                    cur = self.state()
                    cur.update(uidvalidity=uv, last_uid=top, since=st["since"])
                    self._save(cur)
                return []
            new = [u for u in uids if u > st["last_uid"]][:40]
            if not new:
                return []
            primary = set(new)
            try:                            # Gmail's Primary tab only (promotions, social and updates are skipped)
                typ, data = im.uid("SEARCH", None, f"UID {new[0]}:{new[-1]}", "X-GM-RAW", '"category:primary"')
                if typ == "OK":
                    got = {int(x) for x in (data[0] or b"").split()}
                    primary = got or primary     # no tabs in this Gmail: newsletters are still skipped by their headers
            except Exception:
                pass
            for u in new:
                typ, data = im.uid("FETCH", str(u), "(RFC822.SIZE BODY.PEEK[])")
                raw = next((p[1] for p in data if isinstance(p, tuple)), None)
                if not raw:
                    continue
                m = self.judge(raw, primary=u in primary, uid=u)
                if m:
                    out.append(self.keep(m))
            with self.lock:
                cur = self.state()
                cur["last_uid"] = max(new)
                self._save(cur)
        finally:
            try:
                im.logout()
            except Exception:
                pass
        return out

    def deliver(self, cards):
        """Show the cards (or hold them through quiet hours), and push them to the phone and laptop."""
        held = []
        with self.lock:
            st = self.state()
            if not self.quiet():
                held, st["held"] = st.get("held") or [], []
            for m in cards:
                if self.quiet() and not m["prof"]:
                    st.setdefault("held", []).append(m)
                else:
                    held.append(m)
            alerts = st.setdefault("alerts", [])
            cards = st.setdefault("cards", [])
            for m in held:
                mid = f"{st.get('uidvalidity', 0)}-{m['uid']}"
                m["id"] = mid
                alerts.append({"id": mid, "at": time.time(),
                               "title": f"✉ {m['from']}", "body": m["subject"] + " · " + ", ".join(m["why"])})
                cards.append({"id": mid, "at": time.time(), "from": m.get("from"), "addr": m.get("addr"),
                              "subject": m.get("subject"), "snippet": m.get("snippet"), "why": m.get("why"),
                              "date": m.get("date"), "prof": m.get("prof"), "link": m.get("link"),
                              "attachments": m.get("attachments") or [], "body_path": m.get("body_path"),
                              "filed": {}, "done": False})
            st["alerts"] = alerts[-KEEP_ALERTS:]
            st["cards"] = cards[-40:]
            self._save(st)
        for m in held:
            try:
                self.on_card(m)
            except Exception:
                pass
            try:
                self.push(f"✉ {m['from']}", m["subject"] + " · " + ", ".join(m["why"]), m)
            except Exception:
                pass
        return held

    # ---- the email cards on the phone (its attachments are already on this PC) ---------------------
    def card(self, mid):
        return next((c for c in self.state().get("cards") or [] if c.get("id") == mid), None)

    def mark(self, mid, **kv):
        with self.lock:
            st = self.state()
            for c in st.get("cards") or []:
                if c.get("id") == mid:
                    for k, v in kv.items():
                        if k == "filed":
                            c.setdefault("filed", {}).update(v)
                        else:
                            c[k] = v
            self._save(st)

    def phone_cards(self, days=14):
        """The cards for the phone: no paths, just what it shows (newest first)."""
        out, cut = [], time.time() - days * 86400
        for c in reversed(self.state().get("cards") or []):
            if c.get("done") or (c.get("at") or 0) < cut:
                continue
            files = []
            for n, p in enumerate(c.get("attachments") or []):
                try:
                    size = os.path.getsize(p)
                except OSError:
                    continue
                files.append({"n": n, "name": os.path.basename(p), "size": size, "filed": (c.get("filed") or {}).get(str(n))})
            row = {k: c.get(k) for k in ("id", "from", "subject", "snippet", "why", "date", "prof", "link")}
            row.update(files=files, body=bool(c.get("body_path")))
            out.append(row)
        return out

    def alerts(self):
        return self.state().get("alerts") or []

    def loop(self):
        time.sleep(20)
        while True:
            try:
                if self.configured():
                    self.deliver(self.check())
                    self.error = None
                    self.last_check = time.time()
            except Exception as e:
                self.error = str(e)[:200]
            time.sleep(CHECK_EVERY)

    def start(self):
        threading.Thread(target=self.loop, daemon=True, name="mail").start()
        return self


# ---- the Windows notification on the PC -------------------------------------------------------------------
AUMID = "Archie.Mail"


def _register(icon):
    """Lets Windows show the notification as "Archie" with its owl (a per-user entry, like any installed app has)."""
    import winreg
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, "Software\\Classes\\AppUserModelId\\" + AUMID) as k:
        winreg.SetValueEx(k, "DisplayName", 0, winreg.REG_SZ, "Archie")
        if icon and os.path.exists(icon):
            winreg.SetValueEx(k, "IconUri", 0, winreg.REG_SZ, icon)


def windows_toast(m, icon=None, silent=False):
    """A Windows notification that stays on screen until you deal with it: Open in Gmail opens that exact email.
    Returns True if Windows showed it."""
    if sys.platform != "win32":
        return False
    import subprocess
    try:
        _register(icon)
    except OSError:
        pass
    x = lambda s: html.escape(str(s or ""), quote=True)
    link = m.get("link") or "https://mail.google.com/"
    xml = (f'<toast scenario="reminder" activationType="protocol" launch="{x(link)}">'
           f'<visual><binding template="ToastGeneric"><text>{x("✉ " + (m.get("from") or ""))}</text>'
           f'<text>{x(m.get("subject"))}</text><text>{x(", ".join(m.get("why") or []))}</text></binding></visual>'
           f'<actions><action content="Open in Gmail" activationType="protocol" arguments="{x(link)}"/>'
           f'<action content="Dismiss" activationType="system" arguments="dismiss"/></actions>'
           + ('<audio silent="true"/>' if silent else '<audio src="ms-winsoundevent:Notification.Mail"/>') + '</toast>')
    b64 = base64.b64encode(xml.encode("utf-8")).decode()
    ps = ("[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null;"
          "[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null;"
          f"$x = New-Object Windows.Data.Xml.Dom.XmlDocument; $x.LoadXml([Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('{b64}')));"
          f"[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('{AUMID}').Show([Windows.UI.Notifications.ToastNotification]::new($x))")
    r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden", "-Command", ps],
                       capture_output=True, timeout=30, creationflags=0x08000000)
    return r.returncode == 0


# ---- Tools\Connect Gmail.bat: the setup window (you type the app password here; it never leaves this PC) ----
def setup_window(app_dir):
    import tkinter as tk
    mail = Mail(app_dir)
    st = mail.state()
    root = tk.Tk()
    root.title("Connect Gmail to Archie")
    root.configure(bg="#0a0a0a")
    root.resizable(False, False)
    f = tk.Frame(root, bg="#0a0a0a", padx=24, pady=20)
    f.pack()
    L = lambda t, **k: tk.Label(f, text=t, bg="#0a0a0a", fg=k.pop("fg", "#d4d4cf"), anchor="w", justify="left",
                                 font=k.pop("font", ("Segoe UI", 10)), wraplength=420, **k)
    L("Connect Gmail", fg="#c6f432", font=("Segoe UI Semibold", 15)).pack(anchor="w")
    L("Archie only reads (it never marks mail read, moves, deletes or sends anything). The app password is "
      "encrypted with your Windows account and stays on this PC.", fg="#8f8f8a", font=("Segoe UI", 9)).pack(anchor="w", pady=(4, 14))

    def field(label, value="", show=None):
        L(label, font=("Segoe UI", 9), fg="#8f8f8a").pack(anchor="w")
        e = tk.Entry(f, width=48, bg="#1a1a1a", fg="#f2f2ec", insertbackground="#c6f432", relief="flat",
                     font=("Segoe UI", 11), highlightthickness=1, highlightbackground="#2a2a2a", highlightcolor="#c6f432")
        if show:
            e.configure(show=show)
        e.insert(0, value)
        e.pack(anchor="w", ipady=5, pady=(2, 10))
        return e
    addr = field("Gmail address", st.get("address", ""))
    pw = field("App password (the 16 letters Google showed you)" + ("; leave empty to keep the saved one" if mail.configured() else ""), show="•")
    school = field("Your school's email domain (optional; any .edu already counts)", ", ".join(st.get("school") or []))
    profs = field("Professors' addresses that aren't .edu (optional, comma-separated)", ", ".join(st.get("professors") or []))
    msg = L("", font=("Segoe UI", 9))
    msg.pack(anchor="w", pady=(0, 8))

    split = lambda s: [x.strip() for x in s.replace(";", ",").replace("\n", ",").split(",") if x.strip()]

    def go():
        a, p = addr.get().strip(), pw.get().strip()
        if not p and mail.configured() and a.lower() == (mail.state().get("address") or "").lower():
            mail.save_settings(split(school.get()), split(profs.get()))      # just the lists: the password stays as it is
            msg.configure(text="✓ Saved. Archie uses it from the next check (within 3 minutes).", fg="#c6f432")
            return
        if "@" not in a or len(p.replace(" ", "")) < 16:
            msg.configure(text="Type your Gmail address and the 16-letter app password.", fg="#f5a524")
            return
        msg.configure(text="Checking with Gmail…", fg="#8f8f8a")
        root.update()
        try:
            mail.test(a, p)
        except Exception as e:
            msg.configure(text=f"Gmail said no: {str(e)[:160]}\nCheck the address and make a new app password.", fg="#ff8a80")
            return
        mail.save_login(a, p, split(school.get()), split(profs.get()))
        pw.delete(0, "end")
        msg.configure(text="✓ Connected. Archie checks every 3 minutes (new mail from now on). You can close this.", fg="#c6f432")
        btn.configure(text="Save changes")

    btn = tk.Button(f, text="Save changes" if mail.configured() else "Connect", command=go, bg="#c6f432", fg="#0a0a0a", activebackground="#d9f08a", relief="flat",
                    font=("Consolas", 10, "bold"), padx=18, pady=6, cursor="hand2")
    btn.pack(anchor="w")
    if mail.configured():
        def off():
            mail.forget()
            msg.configure(text="Disconnected: the saved password is deleted. Archie stops checking.", fg="#8f8f8a")
        tk.Button(f, text="Disconnect", command=off, bg="#1a1a1a", fg="#d4d4cf", relief="flat", font=("Consolas", 9),
                  padx=12, pady=4, cursor="hand2").pack(anchor="w", pady=(10, 0))
    pw.focus_set()
    root.bind("<Return>", lambda e: go())
    root.mainloop()


if __name__ == "__main__":
    if "--setup" in sys.argv:
        setup_window(os.path.dirname(os.path.abspath(__file__)))
