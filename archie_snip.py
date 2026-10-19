"""
archie_snip.py - global hotkeys and the screen-snip tool.

  * GlobalHotkeys: listens for key combos (like Ctrl+Alt+A) anywhere in
    Windows, even when Archie isn't the active window. Uses the Windows
    RegisterHotKey API directly, so there's nothing extra to install.
  * SnipOverlay: dims the whole screen, lets you drag a box around anything,
    and saves that area as an image that gets attached to the chat.
"""

import datetime
import os
import sys
import threading
import tkinter as tk

# ---------------------------------------------------------------------------
# Global hotkeys (Windows)
# ---------------------------------------------------------------------------

MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN, MOD_NOREPEAT = 0x1, 0x2, 0x4, 0x8, 0x4000
WM_HOTKEY, WM_QUIT = 0x0312, 0x0012

NAMED_KEYS = {
    "space": 0x20, "enter": 0x0D, "tab": 0x09, "esc": 0x1B, "escape": 0x1B,
    "backspace": 0x08, "insert": 0x2D, "delete": 0x2E, "home": 0x24, "end": 0x23,
    "pageup": 0x21, "pagedown": 0x22, "up": 0x26, "down": 0x28, "left": 0x25,
    "right": 0x27, "printscreen": 0x2C, "`": 0xC0, "-": 0xBD, "=": 0xBB,
    "[": 0xDB, "]": 0xDD, ";": 0xBA, "'": 0xDE, ",": 0xBC, ".": 0xBE, "/": 0xBF,
    "\\": 0xDC,
}


def parse_combo(combo):
    """'ctrl+alt+a' -> (modifier flags, virtual key code). Raises ValueError."""
    mods, vk = 0, None
    for part in combo.lower().replace(" ", "").split("+"):
        if part in ("ctrl", "control"):
            mods |= MOD_CONTROL
        elif part == "alt":
            mods |= MOD_ALT
        elif part == "shift":
            mods |= MOD_SHIFT
        elif part in ("win", "windows"):
            mods |= MOD_WIN
        elif len(part) == 1 and part.isalnum():
            vk = ord(part.upper())
        elif part.startswith("f") and part[1:].isdigit() and 1 <= int(part[1:]) <= 24:
            vk = 0x70 + int(part[1:]) - 1
        elif part in NAMED_KEYS:
            vk = NAMED_KEYS[part]
        else:
            raise ValueError(f"I don't know the key '{part}'")
    if vk is None:
        raise ValueError("a hotkey needs a normal key, like ctrl+alt+a")
    if not mods:
        raise ValueError("a hotkey needs at least one of ctrl / alt / shift / win")
    return mods, vk


def pretty_combo(combo):
    return "+".join(p.capitalize() if len(p) > 1 else p.upper()
                    for p in combo.lower().replace(" ", "").split("+"))


class GlobalHotkeys:
    """Runs a small Windows message loop in a background thread. When one of
    the hotkeys is pressed it calls on_event(("hotkey", name)). Problems are
    reported as ("hotkey_failed", [(name, combo, reason), ...])."""

    def __init__(self, bindings, on_event):
        self.bindings = dict(bindings)      # {"chat": "ctrl+alt+a", ...}
        self.on_event = on_event
        self.thread_id = None
        self.supported = sys.platform == "win32"

    def start(self):
        if self.supported:
            threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        import ctypes
        from ctypes import wintypes
        user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
        self.thread_id = kernel32.GetCurrentThreadId()
        ids, failed = {}, []
        for i, (name, combo) in enumerate(self.bindings.items(), 1):
            if not combo:
                continue
            try:
                mods, vk = parse_combo(combo)
            except ValueError as e:
                failed.append((name, combo, str(e)))
                continue
            if user32.RegisterHotKey(None, i, mods | MOD_NOREPEAT, vk):
                ids[i] = name
            else:
                failed.append((name, combo, "another program is already using it"))
        if failed:
            self.on_event(("hotkey_failed", failed))
        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == WM_HOTKEY and msg.wParam in ids:
                self.on_event(("hotkey", ids[msg.wParam]))
        for i in ids:
            user32.UnregisterHotKey(None, i)

    def stop(self):
        if self.supported and self.thread_id:
            import ctypes
            ctypes.windll.user32.PostThreadMessageW(self.thread_id, WM_QUIT, 0, 0)


# ---------------------------------------------------------------------------
# Screen snip
# ---------------------------------------------------------------------------

def virtual_screen(root):
    """(left, top, width, height) covering every monitor."""
    if sys.platform == "win32":
        import ctypes
        m = ctypes.windll.user32.GetSystemMetrics
        return m(76), m(77), m(78), m(79)
    return 0, 0, root.winfo_screenwidth(), root.winfo_screenheight()


def grab_screen():
    from PIL import ImageGrab
    if sys.platform == "win32":
        return ImageGrab.grab(all_screens=True)
    return ImageGrab.grab()


class SnipOverlay:
    """Full-screen, dimmed picture of the screen. Drag a box; the area inside
    lights up. Release to save it. Esc or right-click cancels."""

    TEAL = "#3fc1b0"

    def __init__(self, root, image, save_dir, on_done, on_cancel):
        from PIL import ImageEnhance, ImageTk
        self.ImageTk = ImageTk
        self.root = root
        self.save_dir = save_dir
        self.on_done = on_done
        self.on_cancel = on_cancel
        self.full = image.convert("RGB")
        x0, y0, w, h = virtual_screen(root)
        # The picture may be bigger than the window if Windows display scaling
        # is on; work out the ratio so the saved crop is full resolution.
        self.sx = self.full.width / max(1, w)
        self.sy = self.full.height / max(1, h)
        shown = self.full if (self.full.width, self.full.height) == (w, h) else self.full.resize((w, h))
        self.bright = shown
        dim = ImageEnhance.Brightness(shown).enhance(0.4)

        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.geometry(f"{w}x{h}+{x0}+{y0}")
        self.c = tk.Canvas(self.win, width=w, height=h, highlightthickness=0, bd=0,
                           cursor="crosshair", bg="black")
        self.c.pack()
        self._dim_img = ImageTk.PhotoImage(dim)
        self.c.create_image(0, 0, image=self._dim_img, anchor="nw")
        self._sel_img = None
        self.sel_item = self.c.create_image(0, 0, anchor="nw")
        self.rect = self.c.create_rectangle(0, 0, 0, 0, outline=self.TEAL, width=2, state="hidden")
        self.size_lbl = self.c.create_text(0, 0, text="", fill=self.TEAL, anchor="sw",
                                           font=("Segoe UI" if sys.platform == "win32" else "Helvetica", 10, "bold"),
                                           state="hidden")
        # hint pill at the top of the main screen
        cx = (-x0 + min(w, root.winfo_screenwidth()) / 2) if x0 < 0 else w / 2
        self.c.create_rectangle(cx - 240, 18, cx + 240, 52, fill="#0f2a2e", outline=self.TEAL)
        self.c.create_text(cx, 35, text="Drag a box around what you want Archie to see  ·  Esc to cancel",
                           fill="#e9fbf7", font=("Segoe UI" if sys.platform == "win32" else "Helvetica", 10))
        self.start = None
        self.c.bind("<ButtonPress-1>", self._press)
        self.c.bind("<B1-Motion>", self._drag)
        self.c.bind("<ButtonRelease-1>", self._release)
        self.c.bind("<Button-3>", lambda e: self.cancel())
        self.win.bind("<Escape>", lambda e: self.cancel())
        self.win.update_idletasks()
        self.win.focus_force()
        try:
            self.win.grab_set()
        except tk.TclError:
            pass

    def _box(self, e):
        x1, y1 = self.start
        return min(x1, e.x), min(y1, e.y), max(x1, e.x), max(y1, e.y)

    def _press(self, e):
        self.start = (e.x, e.y)

    def _drag(self, e):
        if not self.start:
            return
        l, t, r, b = self._box(e)
        if r - l < 2 or b - t < 2:
            return
        self._sel_img = self.ImageTk.PhotoImage(self.bright.crop((l, t, r, b)))
        self.c.itemconfigure(self.sel_item, image=self._sel_img)
        self.c.coords(self.sel_item, l, t)
        self.c.coords(self.rect, l, t, r, b)
        self.c.itemconfigure(self.rect, state="normal")
        self.c.coords(self.size_lbl, l, t - 4 if t > 20 else b + 16)
        self.c.itemconfigure(self.size_lbl, state="normal",
                             text=f"{int((r - l) * self.sx)} x {int((b - t) * self.sy)}")

    def _release(self, e):
        if not self.start:
            return
        l, t, r, b = self._box(e)
        if r - l < 6 or b - t < 6:   # just a click: start over
            self.start = None
            return
        crop = self.full.crop((int(l * self.sx), int(t * self.sy),
                               int(r * self.sx), int(b * self.sy)))
        os.makedirs(self.save_dir, exist_ok=True)
        name = datetime.datetime.now().strftime("snip_%Y-%m-%d_%H%M%S.png")
        path = os.path.join(self.save_dir, name)
        crop.save(path)
        self._close()
        self.on_done(path)

    def cancel(self):
        self._close()
        self.on_cancel()

    def _close(self):
        try:
            self.win.grab_release()
        except tk.TclError:
            pass
        self.win.destroy()
