"""archie_cool.py - keeps Archie easy on the PC when it runs all day.

Every 15 seconds it looks at three things and the rest of Archie asks it before doing anything heavy:

  game mode   a full-screen app that isn't Archie, a browser or the desktop (a game, mostly) has been in front for
              30 seconds: Archie's model is unloaded from the graphics card and background AI (World's news
              translation, exam prep, accent chapters, the keep-warm ping) waits until the game is closed.
  idle        no mouse or keyboard for 20 minutes and no class coming up: the model is unloaded once, so the card
              cools down. It loads again the moment you ask Archie something.
  night       1-7 am: big background jobs (World's lawmaking downloads) only run at night or while you're away.

And once a day, between 7 and 10 am, when you've been away for 20 minutes, Archie hasn't been restarted for 6
hours and isn't busy: Archie restarts itself (Restart Archie.bat), so nothing builds up over days of running.
"""
import ctypes
import datetime
import json
import os
import subprocess
import sys
import threading
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
STATE_P = os.path.join(HERE, "cool.json")
IDLE_UNLOAD = 20 * 60
NOT_GAMES = {"explorer.exe", "python.exe", "pythonw.exe", "pyw.exe", "chrome.exe", "msedge.exe", "firefox.exe",
             "brave.exe", "opera.exe", "applicationframehost.exe", "searchhost.exe", "shellexperiencehost.exe",
             "startmenuexperiencehost.exe", "lockapp.exe", "obsidian.exe", "code.exe", "windowsterminal.exe",
             "taskmgr.exe", "textinputhost.exe"}

STATE = {"game": False, "game_app": "", "idle": 0.0, "since": time.time(), "talk": False}
_BUSY = [lambda: False]


def busy():
    """True while talk is open or Archie is answering: background AI waits, so talk stays smooth."""
    try:
        return bool(STATE.get("talk") or _BUSY[0]())
    except Exception:
        return False


def game():
    """True while a game (or other full-screen app) has the screen."""
    return STATE["game"]


def idle_s():
    return STATE["idle"]


def night():
    return 1 <= datetime.datetime.now().hour < 7


def ok_heavy():
    """Big background jobs: at night, or while you're away, and never during a game."""
    return not STATE["game"] and (night() or STATE["idle"] >= IDLE_UNLOAD)


def _idle_now():
    if os.name != "nt":
        return 0.0
    class LII(ctypes.Structure):
        _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]
    li = LII(ctypes.sizeof(LII), 0)
    if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(li)):
        return 0.0
    return max(0.0, (ctypes.windll.kernel32.GetTickCount() - li.dwTime) / 1000.0)


def _fullscreen_app():
    """The exe name of the foreground window when it covers its whole monitor, else ''."""
    if os.name != "nt":
        return ""
    u = ctypes.windll.user32
    hwnd = u.GetForegroundWindow()
    if not hwnd or hwnd in (u.GetDesktopWindow(), u.GetShellWindow()):
        return ""
    class RECT(ctypes.Structure):
        _fields_ = [("l", ctypes.c_long), ("t", ctypes.c_long), ("r", ctypes.c_long), ("b", ctypes.c_long)]
    class MI(ctypes.Structure):
        _fields_ = [("cbSize", ctypes.c_ulong), ("rcMonitor", RECT), ("rcWork", RECT), ("dwFlags", ctypes.c_ulong)]
    r = RECT()
    if not u.GetWindowRect(hwnd, ctypes.byref(r)):
        return ""
    mon = u.MonitorFromWindow(hwnd, 2)
    mi = MI()
    mi.cbSize = ctypes.sizeof(MI)
    if not u.GetMonitorInfoW(mon, ctypes.byref(mi)):
        return ""
    m = mi.rcMonitor
    if not (r.l <= m.l and r.t <= m.t and r.r >= m.r and r.b >= m.b):
        return ""
    pid = ctypes.c_ulong()
    u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    k = ctypes.windll.kernel32
    h = k.OpenProcess(0x1000, False, pid.value)   # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(520)
        n = ctypes.c_ulong(520)
        if not k.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(n)):
            return ""
        exe = os.path.basename(buf.value).lower()
    finally:
        k.CloseHandle(h)
    return "" if exe in NOT_GAMES else exe


class Cool:
    def __init__(self, ollama_url, in_class, busy, report=lambda m: None):
        self.url = ollama_url.rstrip("/")
        self.in_class = in_class          # callable -> True around a class on the calendar
        self.busy = busy                  # callable -> True while you're chatting, talking or recording
        self.report = report
        _BUSY[0] = busy
        self._fs_hits = 0
        self._fs_miss = 0
        self._idle_done = False

    # ----- the graphics card ------------------------------------------------------------------------------------
    def unload(self):
        """Take every loaded Ollama model off the graphics card now."""
        try:
            with urllib.request.urlopen(self.url + "/api/ps", timeout=5) as r:
                models = [m.get("name") or m.get("model") for m in (json.load(r).get("models") or [])]
        except Exception:
            return 0
        n = 0
        for m in models:
            if not m:
                continue
            try:
                body = json.dumps({"model": m, "keep_alive": 0}).encode()
                req = urllib.request.Request(self.url + "/api/generate", data=body, headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=30) as r:
                    r.read()
                n += 1
            except Exception:
                pass
        return n

    # ----- the daily restart ------------------------------------------------------------------------------------
    def _state(self):
        try:
            return json.load(open(STATE_P, encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def _maybe_restart(self):
        now = datetime.datetime.now()
        if not (7 <= now.hour < 10) or STATE["idle"] < 20 * 60 or time.time() - STATE["since"] < 6 * 3600:
            return
        if STATE["game"] or self.busy():
            return
        st = self._state()
        today = now.date().isoformat()
        if st.get("restarted") == today:
            return
        bat = os.path.join(HERE, "Restart Archie.bat")
        if not os.path.exists(bat):
            return
        st["restarted"] = today
        try:
            json.dump(st, open(STATE_P, "w", encoding="utf-8"))
        except OSError:
            return
        flags = 0x00000008 | 0x00000200 | 0x08000000 if os.name == "nt" else 0   # detached, own group, no window
        subprocess.Popen(["cmd", "/c", bat], cwd=HERE, creationflags=flags, close_fds=True)

    # ----- every 15 seconds -------------------------------------------------------------------------------------
    def tick(self):
        STATE["idle"] = _idle_now()
        app = _fullscreen_app()
        if app:
            self._fs_hits, self._fs_miss = self._fs_hits + 1, 0
        else:
            self._fs_miss, self._fs_hits = self._fs_miss + 1, 0
        if not STATE["game"] and self._fs_hits >= 2:
            STATE["game"], STATE["game_app"] = True, app
            if self.unload():
                self.report(f"Game mode: Archie stepped off the graphics card for {app.rsplit('.', 1)[0]}.")
        elif STATE["game"] and self._fs_miss >= 4:
            STATE["game"], STATE["game_app"] = False, ""
        if STATE["idle"] >= IDLE_UNLOAD and not STATE["game"]:
            if not self._idle_done and not self.in_class() and not self.busy():
                self._idle_done = True
                self.unload()
        elif STATE["idle"] < 60:
            self._idle_done = False
        self._maybe_restart()

    def loop(self):
        time.sleep(20)
        while True:
            try:
                self.tick()
            except Exception:
                pass
            time.sleep(15)

    def start(self):
        threading.Thread(target=self.loop, daemon=True, name="cool").start()
        return self
