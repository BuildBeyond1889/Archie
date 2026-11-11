"""Archie keeps himself up to date, once a day, at the first quiet stretch.

What it does (only when the PC is online, you've been away from the keyboard and mouse for a while, and Archie
isn't chatting, recording, typing up a recording or making a picture):
  1. Ollama: if Ollama has already downloaded a new version of itself, install it (the same thing its tray
     icon's "Restart to update" does), then make sure Ollama is running again.
  2. Models: re-download every model you have. Ollama only fetches the parts that changed, so a model that
     hasn't changed costs a few seconds.
  3. Health check: ask the main brain a one-word question. If it doesn't answer, say so.
  4. Once a month: note new models on ollama.com that might be worth trying (never installed on its own).
The result goes to autoupdate.json; the morning brief shows one line about it, once.

Never touched: the Python add-ons (image maker, voice, etc.). Updating those has broken things before.
"""
import datetime
import json
import os
import re
import subprocess
import sys
import threading
import time
import urllib.request

IDLE_MINUTES = 15          # away from keyboard and mouse at least this long
CHECK_EVERY = 5 * 60       # how often to look for a quiet stretch
NEW_MODELS_EVERY_DAYS = 30


def _idle_seconds():
    """Seconds since the last key press or mouse move (Windows). Elsewhere: treat as idle."""
    if sys.platform != "win32":
        return 10 ** 9
    try:
        import ctypes

        class LII(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]
        lii = LII()
        lii.cbSize = ctypes.sizeof(LII)
        if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii)):
            return 0
        return (ctypes.windll.kernel32.GetTickCount() - lii.dwTime) / 1000.0
    except Exception:
        return 0


def _vkey(v):
    return tuple(int(x) for x in re.findall(r"\d+", v or "")[:4]) or (0,)


class AutoUpdate:
    def __init__(self, app_dir, ollama_url, main_model, busy, report=lambda msg: None, embed_model=None):
        self.app_dir = app_dir
        self.url = ollama_url.rstrip("/")
        self.main_model = main_model          # callable -> name of the main brain
        self.busy = busy                      # callable -> True while Archie is doing something
        self.report = report
        self.state_path = os.path.join(app_dir, "autoupdate.json")
        self.stamp_path = os.path.join(app_dir, "last_update.txt")
        self.working = False

    # ---- state ----------------------------------------------------------------------------------
    def state(self):
        try:
            with open(self.state_path, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return {}

    def _save(self, st):
        tmp = self.state_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(st, f, indent=1)
        os.replace(tmp, self.state_path)

    def brief_line(self):
        """One line for the morning brief about the last update, shown once. None if there's nothing to say."""
        st = self.state()
        last = st.get("last") or {}
        if not last or last.get("shown"):
            return None
        parts, warn = [], False
        if last.get("ollama"):
            parts.append(f"Ollama {last['ollama']}")
        if last.get("models"):
            parts.append(", ".join(last["models"]))
        if last.get("failed"):
            parts.append(f"couldn't update {', '.join(last['failed'])} (the old copy still works)")
            warn = True
        if last.get("health") and last["health"] != "ok":
            parts.append(last["health"])
            warn = True
        if last.get("new_models"):
            parts.append("new on Ollama to try: " + ", ".join(last["new_models"]))
        if not parts:
            return None
        lead = "update check" if warn else "updated"
        tail = "" if warn or not (last.get("ollama") or last.get("models")) else " · all working"
        return f"{lead} {last.get('when', '')}: " + " · ".join(parts) + tail, warn

    def mark_shown(self):
        st = self.state()
        if st.get("last"):
            st["last"]["shown"] = True
            self._save(st)

    # ---- Ollama's web API ----------------------------------------------------------------------
    def _api(self, path, body=None, timeout=20):
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(self.url + path, data=data,
                                     headers={"Content-Type": "application/json"} if data else {})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode() or "{}")

    def _models(self):
        return {m["name"]: m.get("digest", "") for m in self._api("/api/tags").get("models", [])}

    def _version(self):
        try:
            return self._api("/api/version", timeout=5).get("version", "")
        except Exception:
            return ""

    def _online(self):
        try:
            urllib.request.urlopen("https://ollama.com", timeout=15).close()
            return True
        except Exception:
            return False

    def _wait_ollama(self, seconds=120):
        end = time.time() + seconds
        while time.time() < end:
            if self._version():
                return True
            time.sleep(3)
        return False

    # ---- 1. Ollama itself ------------------------------------------------------------------------
    def _ollama_dirs(self):
        la = os.environ.get("LOCALAPPDATA", "")
        return os.path.join(la, "Ollama", "updates"), os.path.join(la, "Programs", "Ollama")

    def _update_ollama(self):
        """Install an update Ollama has already downloaded. Returns 'old → new', or None."""
        if sys.platform != "win32":
            return None
        upd, prog = self._ollama_dirs()
        exe = None
        for u in (upd, upd + "_v2"):              # newer Ollama downloads into "updates_v2"
            for dp, _, fns in os.walk(u) if os.path.isdir(u) else []:
                for fn in fns:
                    if fn.lower().endswith(".exe") and "setup" in fn.lower():
                        exe = os.path.join(dp, fn)
        if not exe:
            return None
        installed = os.path.join(prog, "ollama.exe")
        if os.path.exists(installed) and os.path.getmtime(exe) <= os.path.getmtime(installed):
            return None                       # an old download that's already installed
        before = self._version()
        self.report("updating Ollama ...")
        try:
            subprocess.run([exe, "/SP-", "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NOCANCEL", "/NORESTART",
                            "/CLOSEAPPLICATIONS", "/FORCECLOSEAPPLICATIONS"], timeout=900,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except Exception:
            pass
        if not self._wait_ollama(30):         # the installer usually restarts it; if not, start it
            self._start_ollama()
            self._wait_ollama(120)
        after = self._version()
        if after and _vkey(after) > _vkey(before):
            return f"{before} → {after}" if before else after
        return None

    # ---- 2. models -------------------------------------------------------------------------------
    def _update_models(self):
        changed, failed = [], []
        before = self._models()
        for name in sorted(before):
            if self.busy():                   # you came back mid-way: stop, finish the rest next quiet stretch
                return changed, failed, False
            self.report(f"checking {name} for a newer version ...")
            try:
                self._api("/api/pull", {"model": name, "stream": False}, timeout=6 * 3600)
            except Exception:
                failed.append(name)
                continue
            try:
                if self._models().get(name) != before[name]:
                    changed.append(name)
            except Exception:
                pass
        return changed, failed, True

    # ---- 3. health check -------------------------------------------------------------------------
    def _health(self):
        model = self.main_model()
        try:
            out = self._api("/api/generate", {"model": model, "prompt": "Reply with only the word: ready",
                                              "stream": False, "options": {"num_predict": 8}}, timeout=300)
            if "ready" in (out.get("response") or "").lower():
                return "ok"
            return f"the main brain ({model}) answered oddly after updating; tell Claude"
        except Exception:
            return f"the main brain ({model}) didn't answer after updating; tell Claude"

    # ---- 4. new models worth a look ----------------------------------------------------------------
    def _new_models(self, have):
        try:
            req = urllib.request.Request("https://ollama.com/library?sort=newest", headers={"User-Agent": "Archie"})
            html = urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "replace")
        except Exception:
            return []
        names = []
        for m in re.finditer(r'href="/library/([a-z0-9][a-z0-9._-]*)"', html):
            n = m.group(1)
            if n not in names:
                names.append(n)
        mine = {h.split(":")[0] for h in have}
        # the size tags near each entry: keep the ones that come in a 7-9B size (what fits an 8 GB card)
        fits = []
        for n in names[:40]:
            block = html[html.find(f'/library/{n}"'):][:3000]
            if re.search(r">\s*(7|8|9)(\.\d)?b\s*<", block, re.I) and n not in mine and "embed" not in n:
                fits.append(n)
        return fits[:3]

    # ---- the loop ------------------------------------------------------------------------------
    def due(self):
        return self.state().get("ran") != datetime.date.today().isoformat()

    def quiet(self):
        return _idle_seconds() >= IDLE_MINUTES * 60 and not self.busy()

    def run_once(self):
        self.working = True
        try:
            if not self._online():
                return None
            st = self.state()
            when = datetime.datetime.now().strftime("%a %-I:%M %p" if sys.platform != "win32" else "%a %#I:%M %p")
            res = {"when": when, "ollama": None, "models": [], "failed": [], "health": "ok"}
            res["ollama"] = self._update_ollama()
            changed, failed, finished = self._update_models()
            res["models"], res["failed"] = changed, failed
            if res["ollama"] or changed:
                res["health"] = self._health()
            last_new = st.get("new_models_checked", "")
            if not last_new or (datetime.date.today() - datetime.date.fromisoformat(last_new)).days >= NEW_MODELS_EVERY_DAYS:
                try:
                    res["new_models"] = self._new_models(list(self._models()))
                except Exception:
                    res["new_models"] = []
                st["new_models_checked"] = datetime.date.today().isoformat()
            if finished:
                st["ran"] = datetime.date.today().isoformat()
                try:
                    with open(self.stamp_path, "w", encoding="utf-8") as f:   # the yearly reminder stays quiet
                        f.write(st["ran"])
                except OSError:
                    pass
            if res["ollama"] or res["models"] or res["failed"] or res["health"] != "ok" or res.get("new_models"):
                st["last"] = res
            st.setdefault("history", []).append({k: v for k, v in res.items() if v})
            st["history"] = st["history"][-30:]
            self._save(st)
            msg = []
            if res["ollama"]:
                msg.append(f"Ollama {res['ollama']}")
            if changed:
                msg.append("updated " + ", ".join(changed))
            self.report(("Updates done: " + " · ".join(msg)) if msg else "Everything's up to date.")
            return res
        finally:
            self.working = False

    # ---- self-heal: Ollama stopped (it updated itself and didn't come back, crashed, was closed) -----
    def _start_ollama(self):
        _, prog = self._ollama_dirs()
        app = os.path.join(prog, "ollama app.exe")
        try:
            if os.path.exists(app):
                subprocess.Popen([app], cwd=prog, creationflags=getattr(subprocess, "DETACHED_PROCESS", 0))
            else:
                subprocess.Popen(["ollama", "serve"], creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            return True
        except Exception:
            return False

    def _installing(self):
        """True while an Ollama installer is running (don't start Ollama in the middle of its own update)."""
        if sys.platform != "win32":
            return False
        try:
            out = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True, text=True, timeout=20,
                                 creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout.lower()
        except Exception:
            return False
        return "ollamasetup" in out

    def watchdog(self):
        """Every 45 s: if Ollama isn't answering, start it again (after any update finishes), and say so once."""
        time.sleep(5)
        down_since, tries, quiet_until = None, 0, 0
        while True:
            try:
                if self._version():
                    if down_since and tries:
                        self.report("Ollama had stopped; I started it again. All good.")
                    down_since, tries = None, 0
                elif not self.working and not self._installing() and time.time() >= quiet_until:
                    down_since = down_since or time.time()
                    tries += 1
                    if self._start_ollama() and self._wait_ollama(90):
                        self.report("Ollama had stopped (probably after updating itself); I started it again.")
                        down_since, tries = None, 0
                    elif tries >= 3:
                        self.report("I couldn't restart Ollama. Open the Ollama app from the Start menu.")
                        quiet_until, tries = time.time() + 1800, 0     # try again in 30 minutes
            except Exception:
                pass
            time.sleep(45)

    def loop(self):
        time.sleep(120)
        while True:
            try:
                if self.due() and self.quiet():
                    self.run_once()
            except Exception:
                self.working = False
            time.sleep(CHECK_EVERY)

    def start(self):
        threading.Thread(target=self.loop, daemon=True, name="auto-update").start()
        threading.Thread(target=self.watchdog, daemon=True, name="ollama-watchdog").start()
        return self
