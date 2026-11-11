"""
lite.py - Archie Lite on the laptop: the owl, the hotkey and the panel.

  * A small owl floats over your desktop (drag it anywhere; it remembers where).
    Click it, or press Ctrl+Alt+A, to slide the panel in or out. Right-click for the menu.
  * The panel is an Edge app window showing Today, Calendar, To-do, Saved and Chat.
  * Data and syncing: lite_core.py. Nothing heavy runs here: no AI, no news downloading.
  * Updates from the PC are installed while the panel is closed, then Archie Lite restarts itself
    (about two seconds; the owl blinks out and back).
  * v1.2: drop files on the owl (or the panel) to keep them and send them to Obsidian on the PC;
    Ctrl+Alt+Space opens the quick-add bar; pop-ups before classes and for what's due; hover the
    owl for a status line.

Run with pythonw (no console): Start Archie Lite.bat does that.
"""

import datetime
import json
import mimetypes
import os
import secrets
import socket
import subprocess
import sys
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import lite_core  # noqa: E402
import lite_quick  # noqa: E402
import lite_world  # noqa: E402

ROOT = lite_core.ROOT
WEB = os.path.join(ROOT, "web")
TITLE = "Archie Lite"
KEY = "#ff00fe"                  # painted color Windows makes see-through
PANEL_PORT = 47331               # the panel's address on this laptop (127.0.0.1 only)
REC_RED = "#ff4d4d"
LOCK_PORT = 47323                # only one Archie Lite at a time
WIN = sys.platform == "win32"


# ----- the page's server (this laptop only) ---------------------------------------------------
def serve(lite, token, ui):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, body, ctype="application/json"):
            if not isinstance(body, (bytes, bytearray)):
                body = json.dumps(body, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _ok(self):
            if self.client_address[0] != "127.0.0.1":
                return False
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            return secrets.compare_digest(self.headers.get("X-Lite-Token") or (q.get("t") or [""])[0], token)

        def do_GET(self):
            path = urllib.parse.urlparse(self.path).path
            if path.startswith("/api/"):
                if not self._ok():
                    return self._send(403, {"error": "not allowed"})
                if path == "/api/state":
                    try:
                        if self.headers.get("X-Rec"):
                            lite.rec_seen(self.headers.get("X-Rec"))
                        return self._send(200, dict(lite.view(), hint=ui.hint()))
                    except Exception as e:          # show it on the page instead of hanging on "starting"
                        return self._send(500, {"error": f"{type(e).__name__}: {e}"})
                if path.startswith("/api/world/"):
                    q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                    arg = (q.get("region") or q.get("iso") or [""])[0]
                    if path == "/api/world/news":
                        return self._send(200, lite_world.news(arg))
                    if path == "/api/world/govs":
                        return self._send(200, lite_world.govs())
                    if path == "/api/world/country":
                        return self._send(200, lite_world.country(arg) or {"error": "not found"})
                    return self._send(404, {"error": "unknown"})
                if path.startswith("/api/flag/"):
                    svg = lite.flag_svg(path[10:12].upper())
                    if svg is None:
                        return self._send(404, b"", "image/svg+xml")
                    self.send_response(200)
                    self.send_header("Content-Type", "image/svg+xml")
                    self.send_header("Content-Length", str(len(svg)))
                    self.send_header("Cache-Control", "max-age=86400")
                    self.end_headers()
                    return self.wfile.write(svg)
                if path == "/api/article":
                    rel = (urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get("rel") or [""])[0]
                    txt = lite.article_text(rel)
                    return self._send(200 if txt is not None else 404, {"text": txt})
                return self._send(404, {"error": "unknown"})
            if path == "/":
                path = "/index.html"
            full = os.path.normpath(os.path.join(WEB, path.lstrip("/")))
            if not full.startswith(os.path.normpath(WEB) + os.sep) or not os.path.isfile(full):
                return self._send(404, b"not found", "text/plain")
            with open(full, "rb") as f:
                body = f.read()
            if path == "/index.html":
                body = body.replace(b"__TOKEN__", token.encode())
            ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
            if ctype.startswith("text/") or ctype.endswith("javascript"):
                ctype += "; charset=utf-8"
            return self._send(200, body, ctype)

        def do_POST(self):
            if not self._ok():
                return self._send(403, {"error": "not allowed"})
            n = int(self.headers.get("Content-Length") or 0)
            if urllib.parse.urlparse(self.path).path == "/api/rec/piece":   # 10 s of the recording (raw bytes)
                if n > 50 * 1024 * 1024:
                    return self._send(200, {"ok": False, "error": "piece too big"})
                data = self.rfile.read(n)
                try:
                    i = int(self.headers.get("X-I") or 0)
                except ValueError:
                    return self._send(200, {"ok": False, "error": "bad piece"})
                return self._send(200, lite.rec_piece(self.headers.get("X-Rec") or "", i, data))
            if urllib.parse.urlparse(self.path).path == "/api/drop":     # a file dropped on the panel (raw bytes)
                name = urllib.parse.unquote(self.headers.get("X-Name") or "file")
                if n > lite_core.MAX_DROP:
                    return self._send(200, {"ok": False, "error": name + " is over 1 GB; too big to send."})
                tmp_dir = os.path.join(lite.data_dir, "incoming")
                os.makedirs(tmp_dir, exist_ok=True)
                tmp = os.path.join(tmp_dir, secrets.token_hex(8))
                left = n
                with open(tmp, "wb") as f:
                    while left > 0:
                        b = self.rfile.read(min(left, 1 << 20))
                        if not b:
                            break
                        f.write(b)
                        left -= len(b)
                try:
                    mt = float(self.headers.get("X-Mtime") or 0) / 1000 or None
                    kh = self.headers.get("X-Klass")
                    kl = lite_core.AUTO if kh is None or kh == "__auto__" else urllib.parse.unquote(kh)
                    if left == 0 and self.headers.get("X-Card") == "1":     # wait for its inbox card
                        r = lite.stage(tmp, name=name, mtime=mt, owned=True)
                        tmp = None
                    else:
                        r = lite.drop_file(path=tmp, name=name, mtime=mt, klass=kl) if left == 0 else {"ok": False, "error": "upload cut off"}
                finally:
                    try:
                        if tmp:
                            os.remove(tmp)
                    except OSError:
                        pass
                if r.get("ok") and "id" not in r:
                    ui.call(lambda: ui.dropped_toast([r]))
                return self._send(200, r)
            try:
                b = json.loads(self.rfile.read(n) or b"{}") if 0 < n < 2_000_000 else {}
            except ValueError:
                b = {}
            path = urllib.parse.urlparse(self.path).path
            if path == "/api/change":
                r = lite.change(b)
                return self._send(200, dict(lite.view(), result=r))
            if path == "/api/sync":
                lite.sync_once()
                return self._send(200, lite.view())
            if path == "/api/chat":
                return self._send(200, dict(lite.ask(str(b.get("q") or "")), chat=lite.d["chat"][-60:]))
            if path == "/api/chat_clear":
                return self._send(200, lite.clear_chat())
            if path == "/api/world/refresh":
                return self._send(200, lite.world_refresh())
            if path == "/api/note":
                return self._send(200, lite.note_save(b.get("nid"), str(b.get("title") or ""), b.get("klass"),
                                                      b.get("date"), str(b.get("text") or "")))
            if path == "/api/note_hide":             # the x on a note: off this laptop's list (Obsidian keeps it)
                lite.note_hide(str(b.get("nid") or ""))
                return self._send(200, lite.view())
            if path == "/api/quick":
                return self._send(200, ui.quick_apply(str(b.get("text") or "")))
            if path == "/api/open":
                return self._send(200, ui.open_path(str(b.get("path") or "")))
            if path == "/api/hide":
                ui.call(ui.hide_panel)
                return self._send(200, {"ok": True})
            if path == "/api/rec/start":
                r = lite.rec_start(lite_core.AUTO if b.get("klass") is None else b.get("klass"))
                ui.call(ui.rec_tick)
                return self._send(200, r)
            if path == "/api/rec/set":
                return self._send(200, lite.rec_set(str(b.get("id") or ""), b.get("paused"), b.get("elapsed"), b.get("mark")))
            if path == "/api/rec/stop":
                r = lite.rec_stop(str(b.get("id") or ""), b.get("elapsed"))
                ui.call(ui.rec_tick)
                return self._send(200, r)
            if path == "/api/draft/set":
                return self._send(200, lite.draft_set(str(b.get("id") or ""), b.get("label"),
                                                      lite_core.AUTO if "klass" not in b else b.get("klass")))
            if path == "/api/draft/send":
                r = lite.draft_send(str(b.get("id") or ""))
                ui.call(ui.rec_tick)
                if r.get("ok"):
                    ui.call(lambda: ui.toast("Recording sent", f"{r.get('name')} · " + (f"filed under {r['klass']}" if r.get("klass") else "no class")
                                             + " · on its way to your PC, where Archie makes the notes", tab="notes", secs=8))
                return self._send(200, r)
            if path == "/api/draft/discard":
                r = lite.draft_discard(str(b.get("id") or ""))
                ui.call(ui.rec_tick)
                return self._send(200, r)
            if path == "/api/stage_save":            # the inbox card's Save
                r = lite.stage_save(str(b.get("id") or ""), name=b.get("name"), kind=b.get("kind"),
                                    klass=lite_core.AUTO if "klass" not in b else b.get("klass"))
                if r.get("ok"):
                    ui.call(lambda: ui.dropped_toast([r]))
                return self._send(200, dict(lite.view(), result=r))
            if path == "/api/stage_drop":            # the inbox card's Not now
                lite.stage_drop(str(b.get("id") or ""))
                return self._send(200, lite.view())
            if path == "/api/drop_klass":
                return self._send(200, lite.set_drop_pick(b.get("klass")))
            if path == "/api/owl":
                hidden = not bool(lite.setting("owl_hidden", False))
                ui.call(lambda: ui.toggle_owl(hidden))
                return self._send(200, {"ok": True, "hidden": hidden})
            return self._send(404, {"error": "unknown"})

    try:                    # the same address every time, so Edge remembers "allow the microphone"
        httpd = ThreadingHTTPServer(("127.0.0.1", PANEL_PORT), H)
    except OSError:
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), H)
    httpd.request_queue_size = 32
    httpd.daemon_threads = True
    threading.Thread(target=httpd.serve_forever, daemon=True, name="lite-web").start()
    return httpd.server_address[1]


# ----- Windows bits (ctypes, no extra packages) ------------------------------------------------
if WIN:
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    EnumProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def find_windows(title):
        found = []

        def cb(hwnd, _):
            n = user32.GetWindowTextLengthW(hwnd)
            if n:
                buf = ctypes.create_unicode_buffer(n + 1)
                user32.GetWindowTextW(hwnd, buf, n + 1)
                cls = ctypes.create_unicode_buffer(64)
                user32.GetClassNameW(hwnd, cls, 64)
                if buf.value == title and cls.value.startswith("Chrome_WidgetWin"):
                    found.append(hwnd)
            return True
        user32.EnumWindows(EnumProc(cb), 0)
        return found

    def on_top(hwnd):
        """Put a window back above everything (the taskbar included) without stealing focus."""
        user32.SetWindowPos(wintypes.HWND(hwnd), wintypes.HWND(-1), 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010)

    def work_area():
        r = wintypes.RECT()
        user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(r), 0)    # SPI_GETWORKAREA
        return r.left, r.top, r.right, r.bottom

    def hotkey_thread(keys):
        """Global hotkeys: {vk: callback} with Ctrl+Alt (A = panel, Space = quick add)."""
        def run():
            MOD_ALT, MOD_CONTROL, MOD_NOREPEAT = 0x1, 0x2, 0x4000
            ids = {}
            for i, (vk, fn) in enumerate(keys.items(), 1):
                if user32.RegisterHotKey(None, i, MOD_ALT | MOD_CONTROL | MOD_NOREPEAT, vk):
                    ids[i] = fn          # a key another program owns is skipped; the owl still works
            msg = wintypes.MSG()
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
                if msg.message == 0x0312 and msg.wParam in ids:      # WM_HOTKEY
                    ids[msg.wParam]()
        threading.Thread(target=run, daemon=True, name="lite-hotkey").start()

    def accept_drops(widget, on_files):
        """Files dragged from Explorer onto a Tk widget (WM_DROPFILES), with plain ctypes."""
        shell32 = ctypes.windll.shell32
        hwnd = widget.winfo_id()
        LRESULT = ctypes.c_ssize_t
        WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
        setwl = getattr(user32, "SetWindowLongPtrW", None) or user32.SetWindowLongW
        setwl.restype, setwl.argtypes = ctypes.c_void_p, [wintypes.HWND, ctypes.c_int, ctypes.c_void_p]
        callwp = user32.CallWindowProcW
        callwp.restype = LRESULT
        callwp.argtypes = [ctypes.c_void_p, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        dq = shell32.DragQueryFileW
        dq.restype, dq.argtypes = wintypes.UINT, [ctypes.c_void_p, wintypes.UINT, ctypes.c_wchar_p, wintypes.UINT]
        shell32.DragFinish.argtypes = [ctypes.c_void_p]
        state = {}

        def proc(h, msg, wp, lp):
            if msg == 0x0233:                                    # WM_DROPFILES
                files = []
                try:
                    for i in range(dq(wp, 0xFFFFFFFF, None, 0)):
                        n = dq(wp, i, None, 0)
                        buf = ctypes.create_unicode_buffer(n + 1)
                        dq(wp, i, buf, n + 1)
                        files.append(buf.value)
                    shell32.DragFinish(wp)
                except Exception:
                    pass
                if files:
                    on_files(files)
                return 0
            return callwp(state["old"], h, msg, wp, lp)
        cb = WNDPROC(proc)
        state["old"] = setwl(hwnd, -4, ctypes.cast(cb, ctypes.c_void_p))     # GWLP_WNDPROC
        widget._lite_drop_proc = cb                                        # keep it alive
        try:
            for m in (0x0233, 0x004A, 0x0049):     # let drops through even if Python runs as admin
                user32.ChangeWindowMessageFilterEx(wintypes.HWND(hwnd), m, 1, None)
        except Exception:
            pass
        shell32.DragAcceptFiles(wintypes.HWND(hwnd), True)

    def set_foreground(hwnd):
        try:
            top = user32.GetAncestor(wintypes.HWND(hwnd), 2) or hwnd     # GA_ROOT: the real window
            user32.SetForegroundWindow(wintypes.HWND(top))
        except Exception:
            pass

    def autostart(on):
        import winreg
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0,
                           winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE)
        try:
            if on:
                exe = sys.executable.replace("python.exe", "pythonw.exe")
                winreg.SetValueEx(k, "ArchieLite", 0, winreg.REG_SZ, f'"{exe}" "{os.path.abspath(__file__)}"')
            else:
                try:
                    winreg.DeleteValue(k, "ArchieLite")
                except FileNotFoundError:
                    pass
        finally:
            winreg.CloseKey(k)

    SHORTCUT_V = 6      # bump to make every laptop rewrite its Start menu / taskbar shortcut
    AUMID = "Lu.ArchieLite"   # one taskbar identity for the shortcut and the panel window

    # ----- taskbar identity (COM through ctypes) -------------------------------------------
    # The panel is an Edge window, so Windows would pin "Edge". Labelling the window with our own
    # AppUserModelID plus a relaunch command and icon makes "Pin to taskbar" pin Archie Lite, and
    # gives the Start shortcut the same ID so the pin and the open panel share one button.
    class _GUID(ctypes.Structure):
        _fields_ = [("d1", ctypes.c_uint32), ("d2", ctypes.c_uint16), ("d3", ctypes.c_uint16), ("d4", ctypes.c_ubyte * 8)]

    def _guid(text):
        import uuid
        return _GUID.from_buffer_copy(uuid.UUID(text).bytes_le)

    class _PKEY(ctypes.Structure):
        _fields_ = [("fmtid", _GUID), ("pid", ctypes.c_uint32)]

    class _PROPVARIANT(ctypes.Structure):
        _fields_ = [("vt", ctypes.c_ushort), ("r1", ctypes.c_ushort), ("r2", ctypes.c_ushort), ("r3", ctypes.c_ushort),
                    ("val", ctypes.c_void_p), ("pad", ctypes.c_void_p)]

    _AUMID_FMT = "{9F4C2855-9F79-4B39-A8D0-E1D42DE1D5F3}"
    _IID_PROPSTORE = "{886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99}"

    def _vcall(obj, index, restype, *argtypes):
        vtbl = ctypes.cast(obj, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)))[0]
        return ctypes.WINFUNCTYPE(restype, ctypes.c_void_p, *argtypes)(vtbl[index])

    def _set_props(store, values):
        """values: [(pid, text)] on the AppUserModel property set; IPropertyStore SetValue=6, Commit=7."""
        keep = []
        for pid, text in values:
            buf = ctypes.create_unicode_buffer(text)
            keep.append(buf)
            pv = _PROPVARIANT(vt=31, val=ctypes.cast(buf, ctypes.c_void_p))          # VT_LPWSTR
            key = _PKEY(_guid(_AUMID_FMT), pid)
            _vcall(store, 6, ctypes.HRESULT, ctypes.POINTER(_PKEY), ctypes.POINTER(_PROPVARIANT))(store, ctypes.byref(key), ctypes.byref(pv))
            # (S_FALSE and other success codes come back as numbers; real failures raise OSError)
        _vcall(store, 7, ctypes.HRESULT)(store)

    def _get_props(store, pids):
        """{pid: text or None} from the AppUserModel property set; IPropertyStore GetValue=5."""
        out = {}
        for pid in pids:
            pv = _PROPVARIANT()
            key = _PKEY(_guid(_AUMID_FMT), pid)
            try:
                _vcall(store, 5, ctypes.HRESULT, ctypes.POINTER(_PKEY), ctypes.POINTER(_PROPVARIANT))(store, ctypes.byref(key), ctypes.byref(pv))
                out[pid] = ctypes.wstring_at(pv.val) if pv.vt == 31 and pv.val else None
            except OSError:
                out[pid] = None
            finally:
                try:
                    ctypes.windll.ole32.PropVariantClear(ctypes.byref(pv))
                except Exception:
                    pass
        return out

    def _release(obj):
        try:
            _vcall(obj, 2, ctypes.c_ulong)(obj)
        except Exception:
            pass

    def pythonw_exe():
        exe = sys.executable
        if exe.lower().endswith("python.exe") and os.path.exists(exe[:-10] + "pythonw.exe"):
            exe = exe[:-10] + "pythonw.exe"
        return exe

    CONHOST = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "conhost.exe")

    def launch_parts():
        """(program, arguments) for shortcuts, pins and the panel's relaunch command.
        Shortcuts to Microsoft Store Python (a WindowsApps stub) show a blank page on the taskbar, so
        they point at Windows' own conhost.exe, which starts pythonw with no window (--headless).
        1.3.5 used a .vbs file instead, which antivirus can delete; that file is removed here."""
        old = os.path.join(ROOT, "Archie Lite.vbs")
        if os.path.exists(old):
            try:
                os.remove(old)
            except OSError:
                pass
        app = f'"{pythonw_exe()}" "{os.path.abspath(__file__)}" --show'
        if os.path.exists(CONHOST):
            return CONHOST, "--headless " + app
        exe = pythonw_exe()
        return exe, f'"{os.path.abspath(__file__)}" --show'

    def launch_command():
        prog, args = launch_parts()
        return f'"{prog}" {args}'

    def window_props(hwnd):
        ctypes.windll.ole32.CoInitialize(None)
        store = ctypes.c_void_p()
        hr = ctypes.windll.shell32.SHGetPropertyStoreForWindow(wintypes.HWND(hwnd), ctypes.byref(_guid(_IID_PROPSTORE)), ctypes.byref(store))
        if hr or not store:
            raise OSError(f"SHGetPropertyStoreForWindow: {hr}")
        return store

    def wanted_props():
        return {3: os.path.join(HERE, "archie_owl.ico") + ",0", 4: "Archie Lite", 2: launch_command(), 5: AUMID}

    def tag_window(hwnd):
        """Give an Edge panel window Archie Lite's taskbar identity, icon and relaunch command.
        Returns what was on the window before (None if it was already ours)."""
        store = window_props(hwnd)
        try:
            want = wanted_props()
            have = _get_props(store, [3, 4, 2, 5])
            if all(have.get(k) == v for k, v in want.items()):
                return None
            # relaunch details first (3 icon, 4 name, 2 command), then the ID (5), which makes the taskbar re-read them
            _set_props(store, [(3, want[3]), (4, want[4]), (2, want[2]), (5, want[5])])
            return have
        finally:
            _release(store)

    def read_window(hwnd):
        store = window_props(hwnd)
        try:
            return _get_props(store, [5, 2, 3, 4])
        finally:
            _release(store)

    def set_link_id(path):
        """Put the same AppUserModelID on a .lnk shortcut (IShellLink + IPersistFile + IPropertyStore)."""
        ole32 = ctypes.windll.ole32
        ole32.CoInitialize(None)
        pf = ctypes.c_void_p()
        hr = ole32.CoCreateInstance(ctypes.byref(_guid("{00021401-0000-0000-C000-000000000046}")), None, 1,
                                    ctypes.byref(_guid("{0000010B-0000-0000-C000-000000000046}")), ctypes.byref(pf))
        if hr or not pf:
            raise OSError(f"CoCreateInstance: {hr}")
        store = ctypes.c_void_p()
        try:
            _vcall(pf, 5, ctypes.HRESULT, ctypes.c_wchar_p, ctypes.c_ulong)(pf, path, 2)              # Load(STGM_READWRITE)
            _vcall(pf, 0, ctypes.HRESULT, ctypes.POINTER(_GUID), ctypes.POINTER(ctypes.c_void_p))(
                pf, ctypes.byref(_guid(_IID_PROPSTORE)), ctypes.byref(store))                         # QueryInterface
            if not store:
                raise OSError("no property store on the shortcut")
            _set_props(store, [(5, AUMID)])
            _vcall(pf, 6, ctypes.HRESULT, ctypes.c_wchar_p, ctypes.c_int)(pf, None, 1)               # Save(same file)
        finally:
            if store:
                _release(store)
            _release(pf)

    def ensure_shortcuts(lite):
        """The Start menu shortcut (and a pinned taskbar copy, if you pinned it) with the owl icon.
        Opening it shows the panel, even when Archie Lite is already running. Installed copies only."""
        if lite.setting("shortcut_v") == SHORTCUT_V:
            return
        local = os.path.normcase(os.environ.get("LOCALAPPDATA", "") + os.sep)
        if not os.path.normcase(os.path.abspath(__file__)).startswith(local):
            return                     # running from the stick: leave the shortcuts alone
        icon = os.path.join(HERE, "archie_owl.ico")
        prog, args = launch_parts()
        appdata = os.environ.get("APPDATA", "")
        links = [os.path.join(appdata, "Microsoft", "Windows", "Start Menu", "Programs", "Archie Lite.lnk")]
        pinned = os.path.join(appdata, "Microsoft", "Internet Explorer", "Quick Launch", "User Pinned", "TaskBar")
        if os.path.isdir(pinned):
            links += [os.path.join(pinned, f) for f in os.listdir(pinned) if f.lower().startswith("archie lite") and f.lower().endswith(".lnk")]
        q = lambda x: x.replace("'", "''")
        cmd = ";".join(f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{q(l)}');$s.TargetPath='{q(prog)}';"
                       f"$s.Arguments='{q(args)}';$s.WindowStyle=7;$s.WorkingDirectory='{q(ROOT)}';$s.IconLocation='{q(icon)},0';"
                       f"$s.Description='Archie Lite (Ctrl+Alt+A)';$s.Save()" for l in links)
        try:
            r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", cmd],
                               capture_output=True, text=True, timeout=60, creationflags=0x08000000)
            if r.returncode == 0:
                for l in links:
                    try:
                        set_link_id(l)
                    except Exception as e:
                        lite.d["shortcut_error"] = f"id on {os.path.basename(l)}: {e}"[:300]
                lite.set_setting("shortcut_v", SHORTCUT_V)
                subprocess.run(["ie4uinit.exe", "-show"], timeout=30, creationflags=0x08000000)   # refresh icons
            else:
                lite.d["shortcut_error"] = (r.stderr or "")[:300]
        except Exception as e:
            lite.d["shortcut_error"] = str(e)[:300]

    def edge_path():
        for base in (os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles"), os.environ.get("LOCALAPPDATA")):
            if base:
                p = os.path.join(base, "Microsoft", "Edge", "Application", "msedge.exe")
                if os.path.exists(p):
                    return p
        return "msedge.exe"


# ----- the owl and the panel ------------------------------------------------------------------------
class UI:
    def __init__(self, lite, url):
        import tkinter as tk
        self.tk = tk
        self.lite, self.url = lite, url
        self.root = tk.Tk()
        self.root.title(TITLE)
        r = self.root
        r.overrideredirect(True)
        r.attributes("-topmost", True)
        bg = KEY
        try:
            r.attributes("-transparentcolor", KEY)
        except tk.TclError:
            bg = "#0a0a0a"
        dpi = r.winfo_fpixels("1i") / 96.0
        size = 28 if dpi < 1.2 else 36 if dpi < 1.6 else 48     # half the PC owl (2026-11-09)
        self.imgs = {n: tk.PhotoImage(file=os.path.join(HERE, f"owl_{n}_{size}.png")) for n in ("open", "blink")}
        self.size = size
        self.c = tk.Canvas(r, width=size, height=size + 4, bg=bg, highlightthickness=0, bd=0, cursor="hand2")
        self.c.pack()
        self.c.create_image(size // 2, size // 2, image=self.imgs["open"], tags=("owl",))
        d = max(5, size // 6)
        self.c.create_oval(size - d, size - d + 3, size, size + 3, fill="#8f918a", outline="#0a0a0a",
                           width=1, tags=("dot",))
        pos = lite.setting("owl")
        sw, sh = r.winfo_screenwidth(), r.winfo_screenheight()
        if not pos or not (0 <= pos[0] < sw - 20 and 0 <= pos[1] < sh - 20):
            pos = (sw - size - 30, sh - size - 90)
        r.geometry(f"{size}x{size + 4}+{pos[0]}+{pos[1]}")
        self.c.bind("<ButtonPress-1>", self._press)
        self.c.bind("<B1-Motion>", self._drag)
        self.c.bind("<ButtonRelease-1>", self._release)
        self.c.bind("<Button-3>", self._menu)
        self.menu = tk.Menu(r, tearoff=0)
        self.menu.add_command(label="Open / hide  (Ctrl+Alt+A)", command=self.toggle_panel)
        self.menu.add_command(label="Quick add  (Ctrl+Alt+Space)", command=self.quick_add)
        self.menu.add_command(label="Open my Archie Lite files", command=lambda: self.open_path(lite.files_dir()))
        self.menu.add_command(label="Send diagnostics to the PC", command=lambda: threading.Thread(target=self.diagnostics, daemon=True).start())
        self.menu.add_command(label="Sync now", command=lambda: threading.Thread(target=lite.sync_once, daemon=True).start())
        self.auto = tk.BooleanVar(value=bool(lite.setting("autostart", True)))
        self.menu.add_checkbutton(label="Start with Windows", variable=self.auto, command=self._autostart)
        self.top = tk.BooleanVar(value=bool(lite.setting("owl_top", True)))
        self.menu.add_checkbutton(label="Keep owl on top", variable=self.top, command=self._set_top)
        self.menu.add_command(label="Hide owl  (Ctrl+Alt+O brings it back)", command=self.toggle_owl)
        self.menu.add_separator()
        self.menu.add_command(label="Quit Archie Lite", command=self.quit)
        self.edge = None
        self.visible = False
        self.toasts, self._tip, self._tip_job, self._qa, self._hint = [], None, None, None, None
        lite.on_change = lambda: self.call(self._dot)
        lite.on_answer = lambda text: self.call(lambda: self.toast("Archie answered", (text or "")[:180], tab="chat", secs=14))
        lite.on_mail = lambda a: self.call(lambda: self.toast(str(a.get("title") or "New mail")[:80], str(a.get("body") or "")[:180], secs=14))
        self.c.bind("<Enter>", self._tip_soon)
        self.c.bind("<Leave>", self._tip_hide)
        if WIN:
            hotkey_thread({ord("A"): lambda: self.call(self.toggle_panel), 0x20: lambda: self.call(self.quick_add),
                           ord("O"): lambda: self.call(self.toggle_owl)})
            try:
                autostart(self.auto.get())
            except OSError:
                pass
            try:
                accept_drops(self.c, lambda files: threading.Thread(target=self._drop_files, args=(files,), daemon=True).start())
            except Exception as e:
                lite.d["drop_error"] = str(e)
        self.root.after(4000, self._watch)
        self.root.after(1500, self._tag_panels)
        if not lite.setting("owl_top", True):
            self.root.after(300, self._set_top)
        if self.owl_hidden():
            self.root.after(200, self.root.withdraw)
        if WIN:
            threading.Thread(target=ensure_shortcuts, args=(lite,), daemon=True).start()
        if "--show" in sys.argv:
            self.root.after(1200, self.show_panel)
        if WIN and lite.setting("diag_v") != lite_core.VERSION:     # a taskbar report once per version
            lite.set_setting("diag_v", lite_core.VERSION)
            self.root.after(90000, lambda: threading.Thread(target=self.diagnostics, daemon=True).start())
        self._blink()
        self._dot()
        self._rec_on = False
        self.c.bind("<Double-Button-1>", lambda e: None)
        self.root.after(1500, self.rec_tick)
        self._owl_hwnd = None
        self._keep_on_top()
        self.root.after(15000, self._check_update)

    def _check_update(self):
        """Install an update from the PC once the panel is closed, then restart into it."""
        try:
            if self.lite.update_ready() and not self._open_windows() and not self.lite.d.get("rec"):
                if self.lite.install_update():
                    return self.restart()
        except Exception as e:
            self.lite.d["update_error"] = f"install: {type(e).__name__}: {e}"[:300]
            try:
                self.lite.save()
            except OSError:
                pass
        self.root.after(20000, self._check_update)

    def restart(self):
        exe = sys.executable
        if WIN and exe.lower().endswith("python.exe") and os.path.exists(exe[:-10] + "pythonw.exe"):
            exe = exe[:-10] + "pythonw.exe"
        try:
            subprocess.Popen([exe, os.path.abspath(__file__), "--restarted"], cwd=ROOT,
                             creationflags=(0x00000008 | 0x00000200 | 0x08000000) if WIN else 0,
                             close_fds=True)
        except OSError:
            return self.root.after(20000, self._check_update)     # couldn't start the new one: keep running
        self.quit()

    # ----- owl on top, behind other windows, or hidden (each device keeps its own choice) ------------
    def _set_top(self):
        on = bool(self.top.get())
        self.lite.set_setting("owl_top", on)
        try:
            self.root.attributes("-topmost", on)
            if not on:
                self.root.lower()          # step behind the windows that are open now
        except Exception:
            pass

    def owl_hidden(self):
        return bool(self.lite.setting("owl_hidden", False))

    def toggle_owl(self, hidden=None):
        hidden = (not self.owl_hidden()) if hidden is None else bool(hidden)
        self.lite.set_setting("owl_hidden", hidden)
        self._tip_hide()
        if hidden:
            self.root.withdraw()
            self.toast("Owl hidden", "Ctrl+Alt+O, or the owl button in the panel, brings it back. Ctrl+Alt+A still opens the panel.", secs=6)
        else:
            self.root.deiconify()
            self.root.overrideredirect(True)
            self._set_top()

    def _keep_on_top(self):
        """Clicking the taskbar puts it above every other window, owl included; put the owl back each second
        (unless "Keep owl on top" is off, then other windows may cover it)."""
        if WIN and self.lite.setting("owl_top", True) and not self.owl_hidden():
            try:
                if not self._owl_hwnd:
                    self._owl_hwnd = user32.GetAncestor(self.root.winfo_id(), 2) or self.root.winfo_id()   # GA_ROOT
                on_top(self._owl_hwnd)
            except Exception:
                pass
        self.root.after(1000, self._keep_on_top)

    def call(self, fn):
        try:
            self.root.after(0, fn)
        except Exception:
            pass

    # ----- pop-ups (reminders, drops, answers) ---------------------------------------------------
    def hint(self):
        return self._hint

    def set_hint(self, tab):
        self._hint = {"tab": tab, "at": time.time()}

    def _area(self):
        if WIN:
            return work_area()
        return 0, 0, self.root.winfo_screenwidth(), self.root.winfo_screenheight()

    def toast(self, title, body="", tab=None, secs=9):
        tk = self.tk
        while len(self.toasts) >= 4:
            self._close_toast(self.toasts[0])
        w = tk.Toplevel(self.root)
        w.overrideredirect(True)
        w.attributes("-topmost", True)
        outer = tk.Frame(w, bg="#141414", highlightthickness=1, highlightbackground="#3a4a12", cursor="hand2")
        outer.pack(fill="both", expand=True)
        bar = tk.Frame(outer, bg="#c6f432", width=3)
        bar.pack(side="left", fill="y")
        inner = tk.Frame(outer, bg="#141414")
        inner.pack(side="left", fill="both", expand=True, padx=12, pady=9)
        parts = [inner, outer, bar, tk.Label(inner, text=title, bg="#141414", fg="#e8e8e3", font=("Segoe UI Semibold", 10),
                                             anchor="w", justify="left", wraplength=300)]
        parts[-1].pack(fill="x")
        if body:
            parts.append(tk.Label(inner, text=body, bg="#141414", fg="#a3a39e", font=("Segoe UI", 9), anchor="w",
                                  justify="left", wraplength=300))
            parts[-1].pack(fill="x", pady=(2, 0))

        def click(_e=None):
            self._close_toast(w)
            if tab:
                self.set_hint(tab)
                self.show_panel()
        for x in parts:
            x.bind("<Button-1>", click)
        w.update_idletasks()
        w._h = w.winfo_reqheight()
        self.toasts.append(w)
        self._stack()
        w.after(int(secs * 1000), lambda: self._close_toast(w))
        return w

    def _close_toast(self, w):
        if w in self.toasts:
            self.toasts.remove(w)
            try:
                w.destroy()
            except Exception:
                pass
            self._stack()

    def _stack(self):
        left, top, right, bottom = self._area()
        y = bottom - 14
        for w in reversed(self.toasts):
            y -= w._h
            try:
                w.geometry(f"340x{w._h}+{right - 340 - 14}+{y}")
            except Exception:
                pass
            y -= 8

    def _tag_panels(self):
        """Every 2 s: give any new panel window Archie Lite's taskbar identity (see tag_window)."""
        if WIN and not getattr(self, "_tag_off", False) and not getattr(self, "_tag_busy", False):
            hs = [h for h in find_windows(TITLE) if user32.IsWindowVisible(h)]
            if hs:
                self._tag_busy = True

                def run(hs=hs):
                    try:
                        for h in hs:
                            try:
                                before = tag_window(h)
                                if before is not None:
                                    self._tag_sets = getattr(self, "_tag_sets", 0) + 1
                                    if any(before.values()):
                                        self._tag_overwritten = {str(k): v for k, v in before.items()}   # Edge's values
                            except Exception as e:
                                self.lite.d["tag_error"] = str(e)[:300]
                                self._tag_fail = getattr(self, "_tag_fail", 0) + 1
                                if self._tag_fail > 20:
                                    self._tag_off = True      # give up quietly; the panel still works
                    finally:
                        self._tag_busy = False
                threading.Thread(target=run, daemon=True).start()
        self.root.after(3000, self._tag_panels)

    def diagnostics(self):
        """One note per device in the vault (Archie Lite folder) describing the taskbar setup, so
        problems can be seen from the PC. Overwrites itself; nothing personal in it."""
        if not WIN:
            return
        L = self.lite
        lines = [f"version: {lite_core.VERSION}", f"python: {sys.executable}", f"launch: {launch_command()}",
                 f"store python: {'WindowsApps' in sys.executable}", f"app: {os.path.abspath(__file__)}",
                 f"icon: {os.path.join(HERE, 'archie_owl.ico')} exists={os.path.exists(os.path.join(HERE, 'archie_owl.ico'))}",
                 f"shortcut_v: {L.setting('shortcut_v')} (wanted {SHORTCUT_V})", f"shortcut_error: {L.d.get('shortcut_error')}",
                 f"tag_error: {L.d.get('tag_error')}", f"tag sets: {getattr(self, '_tag_sets', 0)} fails: {getattr(self, '_tag_fail', 0)} off: {getattr(self, '_tag_off', False)}",
                 f"edge's own values before ours: {getattr(self, '_tag_overwritten', None)}", ""]
        for h in find_windows(TITLE):
            try:
                lines.append(f"window {h} visible={bool(user32.IsWindowVisible(h))}: {read_window(h)}")
            except Exception as e:
                lines.append(f"window {h}: {e}")
        appdata = os.environ.get("APPDATA", "")
        places = [os.path.join(appdata, "Microsoft", "Windows", "Start Menu", "Programs"),
                  os.path.join(appdata, "Microsoft", "Internet Explorer", "Quick Launch", "User Pinned", "TaskBar")]
        links = []
        for d in places:
            try:
                names = os.listdir(d)
            except OSError as e:
                lines.append(f"{d}: {e}")
                continue
            lines.append(f"{d}: {', '.join(n for n in names if n.lower().endswith('.lnk'))}")
            links += [os.path.join(d, n) for n in names if n.lower().endswith(".lnk") and ("archie" in n.lower() or "edge" in n.lower())]
        if links:
            q = lambda x: x.replace("'", "''")
            cmd = ";".join(f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{q(l)}');"
                           f"'{q(os.path.basename(l))} | ' + $s.TargetPath + ' | ' + $s.Arguments + ' | icon ' + $s.IconLocation" for l in links)
            try:
                r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", cmd],
                                   capture_output=True, text=True, timeout=60, creationflags=0x08000000)
                lines += ["", "shortcuts:"] + r.stdout.strip().splitlines() + ([r.stderr.strip()[:500]] if r.stderr.strip() else [])
            except Exception as e:
                lines.append(f"reading shortcuts: {e}")
        import hashlib
        host = socket.gethostname()
        op = {"type": "note_save", "oid": lite_core.new_id() + lite_core.new_id(),
              "nid": hashlib.sha1(("diag" + host).encode()).hexdigest()[:20], "title": f"Archie Lite diagnostics {host}",
              "klass": None, "date": datetime.date.today().isoformat(),
              "text": "Written by Archie Lite so problems can be looked at from the PC. Safe to delete.\n\n```\n" + "\n".join(lines) + "\n```\n"}
        with L.lock:
            L.d["pending"] = [c for c in L.d["pending"] if c.get("nid") != op["nid"]] + [op]
            L.save()
        L.wake.set()

    def _watch(self):
        """Every 30 s: reminders that are due, and battery/charger changes."""
        try:
            for title, body in self.lite.reminders():
                self.toast(title, body, tab="today", secs=25)
        except Exception as e:
            self.lite.d["reminder_error"] = str(e)
        try:
            b = lite_core.on_battery()
            if b != self.lite.battery:
                self.lite.battery = b
                if not b:
                    self.lite.wake.set()        # plugged back in: catch up now
        except Exception:
            pass
        self.root.after(30000, self._watch)

    # ----- the status line when you hover the owl -------------------------------------------------
    def _tip_soon(self, _e=None):
        self._tip_hide()
        self._tip_job = self.root.after(450, self._tip_show)

    def _tip_hide(self, _e=None):
        if self._tip_job:
            self.root.after_cancel(self._tip_job)
            self._tip_job = None
        if self._tip:
            self._tip.destroy()
            self._tip = None

    def tip_text(self):
        L, now = self.lite, time.time()

        def ago(t):
            if not t:
                return "never"
            s = now - t
            return "just now" if s < 90 else f"{int(s // 60)} min ago" if s < 5400 else f"{int(s // 3600)} h ago" if s < 172800 else f"{int(s // 86400)} days ago"
        st = L.status.get("state")
        n = len(L.d["pending"])
        lines = [("Synced " + ago(L.d["last_ok"]) if st == "home" else "Away · last sync " + ago(L.d["last_ok"]) if L.pair
                  else "Not paired yet") + (f" · {n} waiting" if n else "")]
        tasks, dls = L.due_today()
        k = len(tasks) + len(dls)
        lines.append(f"{k} due today" if k else "Nothing due today")
        cur = L.current_class()
        if cur:
            lines.append(f"Now: {cur['title']} until {lite_core.lite_cal.fmt_time(cur['until'])}")
        else:
            e, t0 = L.next_event()
            if e:
                day = "" if t0.date() == datetime.date.today() else "tomorrow "
                lines.append(f"Next: {e['title']} · {day}{lite_core.lite_cal.fmt_time(e['time'])}")
        rec = L.d.get("rec")
        if rec:
            t = int(L.rec_elapsed())
            lines.insert(0, f"● Recording{' (paused)' if rec.get('paused') else ''} · {t // 60}:{t % 60:02d}"
                         + (f" · {rec['klass']}" if rec.get("klass") else "") + " · click the red bubble to stop")
        elif L.d.get("rec_drafts"):
            n_ = len(L.d["rec_drafts"])
            lines.insert(0, f"● {n_} recording{'s' if n_ > 1 else ''} waiting to send · click the green bubble")
        if L.battery:
            lines.append("On battery · syncing every 10 min")
        lines.append("Drop files here · Ctrl+Alt+Space to add")
        return "\n".join(lines)

    def _tip_show(self):
        self._tip_job = None
        if getattr(self, "_moved", False):
            return
        tk = self.tk
        w = tk.Toplevel(self.root)
        w.overrideredirect(True)
        w.attributes("-topmost", True)
        tk.Label(w, text=self.tip_text(), bg="#141414", fg="#d4d4cf", font=("Consolas", 9), justify="left",
                 padx=10, pady=7, highlightthickness=1, highlightbackground="#262626").pack()
        w.update_idletasks()
        tw, th = w.winfo_reqwidth(), w.winfo_reqheight()
        ox, oy = self.root.winfo_x(), self.root.winfo_y()
        left, top, right, bottom = self._area()
        x = min(max(left + 4, ox + self.size // 2 - tw // 2), right - tw - 4)
        y = oy - th - 6 if oy - th - 6 > top else oy + self.size + 10
        w.geometry(f"+{x}+{y}")
        self._tip = w

    # ----- quick add (Ctrl+Alt+Space) -------------------------------------------------------------
    def quick_apply(self, text):
        op, msg = lite_quick.classify(text)
        if not op:
            return {"ok": False, "error": msg}
        r = self.lite.change(op)
        return {"ok": bool(r.get("ok")), "msg": msg, "error": r.get("error")}

    def quick_add(self):
        tk = self.tk
        if self._qa:
            try:
                self._qa.focus_force()
                return
            except Exception:
                self._qa = None
        w = tk.Toplevel(self.root)
        w.overrideredirect(True)
        w.attributes("-topmost", True)
        box = tk.Frame(w, bg="#141414", highlightthickness=1, highlightbackground="#c6f432")
        box.pack(fill="both", expand=True)
        tk.Label(box, text="ADD TO ARCHIE", bg="#141414", fg="#c6f432", font=("Consolas", 9, "bold"), anchor="w").pack(
            fill="x", padx=16, pady=(12, 4))
        e = tk.Entry(box, bg="#1a1a1a", fg="#e8e8e3", insertbackground="#c6f432", relief="flat", font=("Segoe UI", 14),
                     highlightthickness=1, highlightbackground="#262626", highlightcolor="#c6f432")
        e.pack(fill="x", padx=16, ipady=7)
        msg = tk.Label(box, text="dentist fri 3pm · essay due friday · call mom · a link · note: …\nEnter adds · Esc closes",
                       bg="#141414", fg="#8a8a85", font=("Consolas", 9), anchor="w", justify="left")
        msg.pack(fill="x", padx=16, pady=(6, 12))
        left, top, right, bottom = self._area()
        width = 580
        w.update_idletasks()
        w.geometry(f"{width}x{w.winfo_reqheight()}+{left + (right - left - width) // 2}+{top + (bottom - top) // 4}")

        def close(_e=None):
            if self._qa is w:
                self._qa = None
            try:
                w.destroy()
            except Exception:
                pass

        def submit(_e=None):
            text = e.get().strip()
            if not text:
                return close()
            r = self.quick_apply(text)
            if r.get("ok"):
                close()
                self.toast(r["msg"], "Sent to your PC at the next sync" if self.lite.status.get("state") != "home" else "", tab="today", secs=5)
            else:
                msg.configure(text=r.get("error") or "Couldn't add that.", fg="#ff6b5e")
        e.bind("<Return>", submit)
        e.bind("<Escape>", close)
        w.bind("<FocusOut>", lambda _e: w.after(200, lambda: close() if self._qa is w and w.focus_get() is None else None))
        self._qa = w
        w.after(30, lambda: (set_foreground(w.winfo_id()) if WIN else None, w.focus_force(), e.focus_set()))

    # ----- files dropped on the owl -------------------------------------------------------------------
    def _drop_files(self, files):
        """Files dropped on the owl wait in the panel for their inbox card (what it is, which class, name)."""
        out = []
        for f in files:
            try:
                if os.path.isdir(f):
                    out.append({"ok": False, "error": "That's a folder. Drop the files inside it."})
                    continue
                if os.path.getsize(f) > lite_core.MAX_DROP:
                    out.append({"ok": False, "error": f"{os.path.basename(f)} is over 1 GB; too big to send."})
                    continue
                out.append(self.lite.stage(f))
            except Exception as ex:
                out.append({"ok": False, "error": f"{os.path.basename(f)}: {ex}"})
        bad = [r for r in out if not r.get("ok")]
        if bad:
            self.call(lambda: self.dropped_toast(bad))
        if any(r.get("ok") for r in out):
            self.set_hint("notes")
            self.call(self.show_panel)

    def dropped_toast(self, results):
        ok = [r for r in results if r.get("ok")]
        for r in results:
            if not r.get("ok"):
                self.toast("Couldn't take that", r.get("error") or "", secs=10)
        if ok:
            klass = ok[0].get("klass")
            self.toast((ok[0]["name"] if len(ok) == 1 else f"{len(ok)} files") + " saved",
                       (f"Filed under {klass}" if klass else "Filed in Archie Lite") + " · on this laptop and on its way to Obsidian",
                       tab="notes", secs=7)

    def open_path(self, path):
        base = os.path.realpath(self.lite.files_dir())
        rp = os.path.realpath(path or base)
        if not (rp == base or rp.startswith(base + os.sep)):
            return {"ok": False, "error": "only files in your Archie Lite folder"}
        if rp == base:
            os.makedirs(base, exist_ok=True)
        if not os.path.exists(rp):
            return {"ok": False, "error": "that file isn't there any more"}
        try:
            if WIN:
                os.startfile(rp)
            else:
                subprocess.Popen(["xdg-open", rp])
        except OSError as ex:
            return {"ok": False, "error": str(ex)}
        return {"ok": True}

    def _press(self, e):
        self._tip_hide()
        self._drag0 = (e.x_root, e.y_root, self.root.winfo_x(), self.root.winfo_y())
        self._moved = False

    def _drag(self, e):
        sx, sy, wx, wy = self._drag0
        dx, dy = e.x_root - sx, e.y_root - sy
        if abs(dx) + abs(dy) > 4:
            self._moved = True
        if self._moved:
            self.root.geometry(f"+{wx + dx}+{wy + dy}")

    def _release(self, e):
        if self._moved:
            off = getattr(self, "_rec_off", 0) if self._rec_on else 0
            self.lite.set_setting("owl", [self.root.winfo_x() + off, self.root.winfo_y()])
        elif self._rec_on and e is not None and getattr(e, "y", 0) > self.size + 2:   # red: the recorder; green: send it
            self.set_hint("notes")                 # the red bubble: open the panel at the recorder
            self.show_panel()
        else:
            self.toggle_panel()

    # ----- recording: a red bubble under the owl, with the time ----------------------------------------
    def rec_tick(self):
        """Every second: show or update the red bubble while the laptop is recording."""
        try:
            self._rec_tick()
        except Exception as ex:
            self.lite.d["rec_ui_error"] = str(ex)[:200]
        if not getattr(self, "_rec_job", None):
            def again():
                self._rec_job = None
                self.rec_tick()
            self._rec_job = self.root.after(1000, again)

    def _rec_tick(self):
        rec = self.lite.d.get("rec")
        waiting = (not rec) and bool(self.lite.d.get("rec_drafts"))
        if waiting != getattr(self, "_rec_green", False) and self._rec_on and (rec or waiting):
            self.c.delete("rec")                   # redraw the bubble in the other color
            self._rec_on = False
            self.c.move("owl", -self._rec_off, 0)
            self.c.move("dot", -self._rec_off, 0)
            x0, y0 = self.root.winfo_x(), self.root.winfo_y()
            self.root.geometry(f"{self.size}x{self.size + 4}+{x0 + self._rec_off}+{y0}")
        self._rec_green = waiting
        show = rec or (waiting and {"green": True})
        if rec and time.time() - (rec.get("seen") or 0) > lite_core.REC_STALE and not getattr(self, "_rec_saving", False):
            self._rec_saving = True                # the panel went quiet for 5 minutes: save what there is

            def save():
                try:
                    self.lite.rec_check()
                finally:
                    self._rec_saving = False
            threading.Thread(target=save, daemon=True, name="lite-rec-save").start()
        s = self.size
        bw, bh = max(s + 34, 66), 18
        if show and not self._rec_on:
            self._rec_on = True
            col = "#8fc919" if waiting else REC_RED
            x, y = self.root.winfo_x(), self.root.winfo_y()
            self._rec_off = (bw - s) // 2
            self.c.configure(width=bw, height=s + 4 + bh + 3)
            self.c.move("owl", self._rec_off, 0)
            self.c.move("dot", self._rec_off, 0)
            self.root.geometry(f"{bw}x{s + 4 + bh + 3}+{x - self._rec_off}+{y}")
            r = bh // 2
            top = s + 6
            self.c.create_oval(0, top, bh, top + bh, fill=col, outline="", tags=("rec",))
            self.c.create_oval(bw - bh, top, bw, top + bh, fill=col, outline="", tags=("rec",))
            self.c.create_rectangle(r, top, bw - r, top + bh, fill=col, outline="", tags=("rec",))
            self.c.create_oval(7, top + 6, 13, top + 12, fill="#ffffff", outline="", tags=("rec", "recdot"))
            self.c.create_text(bw // 2 + 5, top + bh // 2, text="", fill="#ffffff", font=("Segoe UI", 8, "bold"),
                               tags=("rec", "rectime"))
            if self.owl_hidden():
                self.root.deiconify()             # hidden owl comes back while recording
                self.root.overrideredirect(True)
        elif not show and self._rec_on:
            self._rec_on = False
            x, y = self.root.winfo_x(), self.root.winfo_y()
            self.c.delete("rec")
            self.c.move("owl", -self._rec_off, 0)
            self.c.move("dot", -self._rec_off, 0)
            self.c.configure(width=s, height=s + 4)
            self.root.geometry(f"{s}x{s + 4}+{x + self._rec_off}+{y}")
            if self.owl_hidden():
                self.root.withdraw()
        if waiting and self._rec_on:
            self.c.itemconfigure("rectime", text="send", fill="#0a0a0a")
            self.c.itemconfigure("recdot", fill="#0a0a0a")
        if rec:
            t = int(self.lite.rec_elapsed())
            txt = (f"{t // 3600}:{t % 3600 // 60:02d}:{t % 60:02d}" if t >= 3600 else f"{t // 60}:{t % 60:02d}")
            self.c.itemconfigure("rectime", text=("❚❚ " if rec.get("paused") else "") + txt)
            on = rec.get("paused") or int(time.time()) % 2 == 0
            self.c.itemconfigure("recdot", fill="#ffffff" if on else REC_RED)

    def _menu(self, e):
        self.menu.tk_popup(e.x_root, e.y_root)

    def _autostart(self):
        self.lite.set_setting("autostart", self.auto.get())
        if WIN:
            try:
                autostart(self.auto.get())
            except OSError:
                pass

    def _dot(self):
        st = self.lite.status.get("state")
        col = "#c6f432" if st == "home" and not self.lite.d["pending"] else "#f5b942" if st in ("home", "away") else "#8f918a"
        self.c.itemconfigure("dot", fill=col)

    def _blink(self):
        self.c.itemconfigure("owl", image=self.imgs["blink"])
        self.root.after(140, lambda: self.c.itemconfigure("owl", image=self.imgs["open"]))
        self.root.after(5000 + int.from_bytes(os.urandom(2), "big") % 9000, self._blink)

    # the panel: an Edge app window we show and hide
    def _open_windows(self):
        """Edge can make several windows titled "Archie Lite"; the panel is the visible, not minimized one."""
        if not WIN:
            return []
        return [h for h in find_windows(TITLE) if user32.IsWindowVisible(h) and not user32.IsIconic(h)]

    def toggle_panel(self):
        if self._open_windows():
            self.hide_panel()
        else:
            self.show_panel()

    def show_panel(self):
        # the window we hid ourselves, else one that was minimized; never Edge's invisible helper windows
        mins = [h for h in find_windows(TITLE) if user32.IsIconic(h)] if WIN else []
        hs = [h for h in [getattr(self, "_hidden", None)] + mins if h]
        for h in hs:
            if WIN and user32.IsWindow(h):
                user32.ShowWindow(h, 9)        # SW_RESTORE
                user32.ShowWindow(h, 5)        # SW_SHOW
                user32.SetForegroundWindow(h)
                self._hidden = None
                return
        w, hgt = 1040, 900
        if WIN:
            left, top, right, bottom = work_area()
            w = min(1040, int((right - left) * 0.62))      # twice the old 520, capped on small screens
            hgt = min(1000, bottom - top - 40)
            x, y = right - w - 20, top + 20
        else:
            x, y = 40, 40
        args = [edge_path() if WIN else "microsoft-edge", f"--app={self.url}",
                f"--user-data-dir={os.path.join(lite_core.DATA, 'edge')}", f"--window-size={w},{hgt}",
                f"--window-position={x},{y}", "--no-first-run", "--no-default-browser-check", "--disable-sync"]
        try:
            self.edge = subprocess.Popen(args, creationflags=0x08000000 if WIN else 0)   # no console window
        except OSError:
            import webbrowser
            webbrowser.open(self.url)

    def hide_panel(self):
        for h in self._open_windows():
            user32.ShowWindow(h, 0)            # SW_HIDE
            self._hidden = h

    def quit(self):
        if self.lite.d.get("rec"):
            try:
                self.lite.rec_stop(self.lite.d["rec"]["id"], why="Archie Lite was closed while recording")   # kept as a draft
            except Exception:
                pass
        self.lite.stop.set()
        for h in (find_windows(TITLE) if WIN else []):
            user32.PostMessageW(h, 0x0010, 0, 0)   # WM_CLOSE
        self.root.destroy()

    def run(self):
        self.root.mainloop()


def main():
    lock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tries = 40 if "--restarted" in sys.argv else 1      # after an update, wait for the old copy to close
    for i in range(tries):
        try:
            lock.bind(("127.0.0.1", LOCK_PORT))   # a second copy can't bind: it just leaves
            break
        except OSError:
            if i == tries - 1:
                if "--show" in sys.argv:          # opened from Start or the taskbar: show the running one's panel
                    try:
                        with socket.create_connection(("127.0.0.1", LOCK_PORT), timeout=3) as c:
                            c.sendall(b"show")
                    except OSError:
                        pass
                return
            time.sleep(0.5)
    lock.listen(4)
    lite = lite_core.Lite().start()
    token = secrets.token_urlsafe(24)
    holder = {}

    class Later:
        """The page server starts before the owl exists; this forwards to it once it does."""
        def call(self, fn):
            holder["ui"].call(fn) if "ui" in holder else None

        def hide_panel(self):
            holder["ui"].hide_panel()

        def toggle_owl(self, hidden=None):
            holder["ui"].toggle_owl(hidden)

        def hint(self):
            return holder["ui"].hint() if "ui" in holder else None

        def dropped_toast(self, results):
            holder["ui"].dropped_toast(results)

        def rec_tick(self):
            if "ui" in holder:
                holder["ui"].rec_tick()

        def toast(self, *a, **k):
            if "ui" in holder:
                holder["ui"].toast(*a, **k)

        def quick_apply(self, text):
            if "ui" in holder:
                return holder["ui"].quick_apply(text)
            op, msg = lite_quick.classify(text)
            return dict(lite.change(op), msg=msg) if op else {"ok": False, "error": msg}

        def open_path(self, path):
            return holder["ui"].open_path(path) if "ui" in holder else {"ok": False, "error": "starting"}
    port = serve(lite, token, Later())
    url = f"http://127.0.0.1:{port}/?t={token}"
    try:
        ui = UI(lite, url)
    except Exception as e:            # no Tk: still serve the panel in the browser
        import webbrowser
        webbrowser.open(url)
        print("Archie Lite running without the owl:", e)
        while True:
            time.sleep(3600)
    holder["ui"] = ui

    def commands():
        while True:
            try:
                c, _ = lock.accept()
                with c:
                    c.settimeout(2)
                    if c.recv(16).startswith(b"show"):
                        ui.call(ui.show_panel)
            except OSError:
                return
    threading.Thread(target=commands, daemon=True, name="lite-commands").start()
    ui.run()


if __name__ == "__main__":
    main()
