"""
archie_theme.py - the look of Archie (the "Graphite x Terminal" design).

Colors, fonts, crisp anti-aliased shapes and icons drawn with Pillow,
a slim scrollbar, and rounded window corners on Windows.
"""

import math
import os
import sys
import tkinter as tk
import tkinter.font as tkfont

try:
    from PIL import Image, ImageDraw, ImageTk
except Exception:          # Pillow missing: Archie still runs, just plainer
    Image = None

# ---------------------------------------------------------------------------
# Colors
# ---------------------------------------------------------------------------

BG = "#0a0a0a"          # window background
SURFACE = "#141414"     # cards, tab bar, owl fill
RAISED = "#1a1a1a"      # your message bubbles, hover
BORDER = "#262626"      # hairlines and outlines
LINE = "#1f1f1f"        # divider above the input
TEXT = "#e8e8e3"
BODY = "#d9d9d4"        # Archie's answer text
MUTED = "#8a8a85"
DIM = "#a3a3a3"         # bottom-row buttons
ACCENT = "#c6f432"      # lime
ACCENT_HI = "#dcff6b"
ON_ACCENT = "#0a0a0a"   # text drawn on top of lime

SS = 4                  # supersampling for smooth edges

# ---------------------------------------------------------------------------
# Fonts (bundled in the fonts folder, loaded just for Archie)
# ---------------------------------------------------------------------------

SANS, SANS_SEMI, MONO = "Segoe UI", "Segoe UI Semibold", "Consolas"


def load_private_fonts(folder):
    """Make the bundled .ttf files usable by Archie only (nothing is installed)."""
    if sys.platform != "win32" or not os.path.isdir(folder):
        return
    try:
        import ctypes
        add = ctypes.windll.gdi32.AddFontResourceExW
        for name in os.listdir(folder):
            if name.lower().endswith(".ttf"):
                add(os.path.join(folder, name), 0x10, 0)   # FR_PRIVATE
    except Exception:
        pass


def pick_fonts(root):
    global SANS, SANS_SEMI, MONO
    fams = set(tkfont.families(root))
    if "Geist" in fams:
        SANS = "Geist"
        SANS_SEMI = "Geist SemiBold" if "Geist SemiBold" in fams else "Geist"
    elif sys.platform != "win32":
        SANS = SANS_SEMI = "Helvetica"
    for m in ("JetBrains Mono", "Cascadia Mono", "Consolas", "DejaVu Sans Mono", "Courier"):
        if m in fams:
            MONO = m
            break
    return SANS, SANS_SEMI, MONO


# ---------------------------------------------------------------------------
# Shapes
# ---------------------------------------------------------------------------

def _rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _mask(W, H, radii, inset):
    """White rounded-rectangle mask. radii = (top-left, top-right, bottom-right, bottom-left)."""
    m = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(m)
    x0, y0, x1, y1 = inset, inset, W - 1 - inset, H - 1 - inset
    if x1 <= x0 or y1 <= y0:
        return m
    d.rectangle([x0, y0, x1, y1], 255)
    tl, tr, br, bl = [max(0, min(r - inset, (x1 - x0) // 2, (y1 - y0) // 2)) for r in radii]
    for r, sx, sy in ((tl, 0, 0), (tr, 1, 0), (br, 1, 1), (bl, 0, 1)):
        if r <= 0:
            continue
        ex0 = x1 - 2 * r if sx else x0          # the corner's circle
        ey0 = y1 - 2 * r if sy else y0
        qx0 = x1 - r if sx else x0              # the corner square to cut away
        qy0 = y1 - r if sy else y0
        d.rectangle([qx0, qy0, qx0 + r, qy0 + r], 0)
        d.ellipse([ex0, ey0, ex0 + 2 * r, ey0 + 2 * r], 255)
    return m


def rounded(w, h, radius, fill, outline=None, bg=BG, border=1, dots=()):
    """A smooth rounded rectangle as a PhotoImage (w, h in real pixels).
    radius can be a number or (tl, tr, br, bl). dots = [(x, y, r, color)]."""
    w, h = max(2, int(w)), max(2, int(h))
    radii = radius if isinstance(radius, (tuple, list)) else (radius,) * 4
    radii = [int(r * SS) for r in radii]
    W, H = w * SS, h * SS
    img = Image.new("RGB", (W, H), _rgb(bg))
    if outline:
        img.paste(_rgb(outline), (0, 0, W, H), _mask(W, H, radii, 0))
        img.paste(_rgb(fill), (0, 0, W, H), _mask(W, H, radii, int(border * SS)))
    else:
        img.paste(_rgb(fill), (0, 0, W, H), _mask(W, H, radii, 0))
    d = ImageDraw.Draw(img)
    for x, y, r, color in dots:
        d.ellipse([(x - r) * SS, (y - r) * SS, (x + r) * SS, (y + r) * SS], fill=_rgb(color))
    return ImageTk.PhotoImage(img.resize((w, h), Image.LANCZOS))


# ---------------------------------------------------------------------------
# Line drawing helpers (round caps and joins, like the SVG designs)
# ---------------------------------------------------------------------------

def _stroke(d, pts, width, color, closed=False):
    if closed:
        pts = list(pts) + [pts[0]]
    for a, b in zip(pts, pts[1:]):
        d.line([a, b], fill=color, width=int(round(width)))
    r = width / 2
    for x, y in pts:
        d.ellipse([x - r, y - r, x + r, y + r], fill=color)


def _finish(img, size, bg):
    img = img.resize((size, size), Image.LANCZOS)
    if bg is not None:
        base = Image.new("RGBA", img.size, _rgb(bg) + (255,))
        base.alpha_composite(img)
        img = base.convert("RGB")
    return img


# ----- icons (24x24 design grid, same shapes as the mockup) -----------------

def _arc(cx, cy, r, a0, a1, steps=40):
    return [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * i / steps)),
             cy + r * math.sin(math.radians(a0 + (a1 - a0) * i / steps)))
            for i in range(steps + 1)]


ICONS = {
    "history": [(_arc(12, 12, 9, 180, -131.8), False), ([(6, 5.3), (3, 8)], False),
                ([(3, 3), (3, 8), (8, 8)], False), ([(12, 7), (12, 12), (15, 14)], False)],
    "plus": [([(12, 5), (12, 19)], False), ([(5, 12), (19, 12)], False)],
    "close": [([(6, 6), (18, 18)], False), ([(18, 6), (6, 18)], False)],
    "shrink": [([(6, 6), (17, 17)], False), ([(17, 10), (17, 17), (10, 17)], False)],
    "brief": [(_arc(12, 12, 4, 0, 360, 36), True)] + [
        ([(12 + 7 * math.cos(math.radians(a)), 12 + 7 * math.sin(math.radians(a))),
          (12 + 9.5 * math.cos(math.radians(a)), 12 + 9.5 * math.sin(math.radians(a)))], False)
        for a in range(0, 360, 45)],
}


def icon(name, size, color, bg=BG, hover_bg=None, box=None, stroke=1.8):
    """A line icon centred in a box x box square (optionally on a rounded hover tile)."""
    box = box or size
    S = box * SS
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if hover_bg:
        d.rounded_rectangle([0, 0, S - 1, S - 1], radius=int(S * 0.3), fill=_rgb(hover_bg) + (255,))
    k = size * SS / 24.0
    off = (S - size * SS) / 2
    for pts, closed in ICONS[name]:
        _stroke(d, [(x * k + off, y * k + off) for x, y in pts], stroke * k,
                _rgb(color) + (255,), closed)
    return ImageTk.PhotoImage(_finish(img, box, bg))


# ----- the owl --------------------------------------------------------------

OWL_HEAD = [(28, 26), (48, 40), (72, 40), (92, 26), (92, 76), (60, 106), (28, 76)]
OWL_BEAK = [(55, 83), (60, 91), (65, 83)]


def _hexagon(cx, cy, r):
    return [(cx + r * math.cos(math.radians(90 + 60 * k)),
             cy + r * math.sin(math.radians(90 + 60 * k))) for k in range(6)]


def owl_rgba(size, color=ACCENT, fill=SURFACE, eyes="open", view=(15, 21, 90)):
    """The Faceted owl, lines only, as in the chat window's top corner.
    view = (x, y, side) of the 120-unit design grid to show."""
    vx, vy, side = view
    S = size * SS
    k = S / side
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    def P(seq):
        return [((x - vx) * k, (y - vy) * k) for x, y in seq]

    c = _rgb(color) + (255,)
    w = 6 * k
    d.polygon(P(OWL_HEAD), fill=_rgb(fill) + (255,))
    _stroke(d, P(OWL_HEAD), w, c, closed=True)
    for cx in (46, 74):
        hexa = _hexagon(cx, 62, 14)
        if eyes == "open":
            _stroke(d, P(hexa), w, c, closed=True)
        else:   # blinking: just the lower lid
            _stroke(d, P([hexa[1], hexa[0], hexa[5]]), w, c)
    _stroke(d, P(OWL_BEAK), w, c)
    return img.resize((size, size), Image.LANCZOS)


def owl_photo(size, bg=BG, **kw):
    img = owl_rgba(size, **kw)
    base = Image.new("RGBA", img.size, _rgb(bg) + (255,))
    base.alpha_composite(img)
    return ImageTk.PhotoImage(base.convert("RGB"))


def owl_keyed(size, key, matte=BG, **kw):
    """Owl for the floating bubble: see-through around it (Windows paints `key`
    as transparent), soft edges blended onto a dark matte so there's no fringe."""
    img = owl_rgba(size, **kw)
    base = Image.new("RGBA", img.size, _rgb(matte) + (255,))
    base.alpha_composite(img)
    out = base.convert("RGB")
    alpha = img.getchannel("A").point(lambda a: 255 if a >= 90 else 0)
    keyed = Image.new("RGB", img.size, _rgb(key))
    keyed.paste(out, (0, 0), alpha)
    return ImageTk.PhotoImage(keyed)


# ----- the owl in flight (the focus timer) ----------------------------------
# Same design grid as the timer mockup: x -40..160, y 0..128. The head is the
# owl above, scaled 0.78; six feathers per wing unfold with the session, and a
# fanned tail sits behind the body.

FLIGHT_W, FLIGHT_H = 200.0, 128.0
PULSE_HI = "#f4ffd0"


def _ease(q):
    return 2 * q * q if q < 0.5 else 1 - (-2 * q + 2) ** 2 / 2


def _mix(c1, c2, k):
    a, b = _rgb(c1), _rgb(c2)
    return "#%02x%02x%02x" % tuple(int(a[i] + (b[i] - a[i]) * k) for i in range(3))


def flight_feathers(p):
    """[(points in design units, is_open)] back to front: tail, then wings."""
    def place(pts, px_, py_, side, ang):
        c, s_ = math.cos(math.radians(ang)), math.sin(math.radians(ang))
        return [(px_ + side * (u * c - v * s_), py_ + u * s_ + v * c) for u, v in pts]
    out = []
    for k in (0, 4, 1, 3, 2):                       # the tail: always fanned out
        off = k - 2
        L = 34 - abs(off) * 3.5
        shape = [(0, 0), (9, -4.2), (L, 0), (9, 4.2)]
        out.append((place(shape, 60, 84, 1, 90 + off * 17), True, shape, (60, 84, 1, 90 + off * 17)))
    wings = []
    for side in (-1, 1):
        px_ = 38 if side < 0 else 82
        for i in range(6):
            L = 64 - i * 5.6
            spread, folded = -38 + i * 17, 84 + i * 1.5
            q = _ease(max(0.0, min(1.0, (p - i * 0.13) / 0.35)))
            a = folded + (spread - folded) * q
            shape = [(0, 0), (11, -4.6), (L, 0), (11, 4.6)]
            wings.append((place(shape, px_, 60, side, a), q > 0.02, shape, (px_, 60, side, a)))
    return out + wings[::-1]


def _sub_polyline(pts, f0, f1):
    """The part of a polyline between fractions f0..f1 of its length."""
    segs = [math.dist(a, b) for a, b in zip(pts, pts[1:])]
    total = sum(segs) or 1
    a0, a1 = max(0.0, f0) * total, min(1.0, f1) * total
    if a1 <= a0:
        return []
    res, run = [], 0.0
    for (x0, y0), (x1, y1), L in zip(pts, pts[1:], segs):
        s0, s1 = max(a0, run), min(a1, run + L)
        if s1 > s0 and L > 0:
            t0, t1 = (s0 - run) / L, (s1 - run) / L
            pa = (x0 + (x1 - x0) * t0, y0 + (y1 - y0) * t0)
            pb = (x0 + (x1 - x0) * t1, y0 + (y1 - y0) * t1)
            if not res:
                res.append(pa)
            res.append(pb)
        run += L
    return res


def owl_flight_rgba(width, p=0.0, breath=1.0, pulse_t=None, eyes="open", color=ACCENT,
                    fill=SURFACE, ghost=False, sleepy=False, zzz=False, ss=3):
    """The timer owl as a transparent image `width` pixels wide.
    p: 0 = wings folded .. 1 = fully open. breath: how bright the wings are (0..1).
    pulse_t: 0..1 through the once-a-minute pulse (None = no pulse)."""
    W = int(width)
    H = int(round(W * FLIGHT_H / FLIGHT_W))
    S = W * ss / FLIGHT_W

    def P(pts):
        return [((x + 40) * S, y * S) for x, y in pts]

    col = MUTED if sleepy else color
    feathers = flight_feathers(0.0 if sleepy else p)
    img = Image.new("RGBA", (W * ss, H * ss), (0, 0, 0, 0))
    if ghost and not sleepy:
        d = ImageDraw.Draw(img)
        for pts, _o, shape, (px_, py_, side, _a) in flight_feathers(1.0):
            _stroke(d, P(pts), 1.1 * S, _rgb(BORDER) + (255,), closed=True)
    wings = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(wings)
    for pts, is_open, _shape, _pl in feathers:
        d.polygon(P(pts), fill=_rgb(fill) + (255,))
        _stroke(d, P(pts), 1.8 * S, _rgb(col if is_open else "#3a3a3a") + (255,), closed=True)
    if breath < 0.999:
        a = wings.getchannel("A").point(lambda v: int(v * max(0.0, min(1.0, breath))))
        wings.putalpha(a)
    img.alpha_composite(wings)
    d = ImageDraw.Draw(img)
    head_k = 0.0
    if pulse_t is not None and not sleepy:
        if pulse_t < 0.35:
            head_k = 1 - pulse_t / 0.35
        if 0.12 <= pulse_t < 1:
            pos = (-26 + (pulse_t - 0.12) / 0.88 * 126) / 100.0
            for _pts, is_open, shape, (px_, py_, side, a) in feathers:
                if not is_open:
                    continue
                c, s_ = math.cos(math.radians(a)), math.sin(math.radians(a))
                for edge in (shape[:3], [shape[0], shape[3], shape[2]]):
                    part = _sub_polyline(edge, pos, pos + 0.26)
                    if len(part) >= 2:
                        world = [(px_ + side * (u * c - v * s_), py_ + u * s_ + v * c) for u, v in part]
                        _stroke(d, P(world), 2.6 * S, _rgb(PULSE_HI) + (255,))

    def H_(pts):                                     # the head, scaled 0.78 around (60, 64)
        return P([(60 + (x - 60) * 0.78, 64 + (y - 64) * 0.78) for x, y in pts])
    k = 0.78 * S
    head_col = _mix(col, PULSE_HI, head_k) if head_k else col
    d.polygon(H_(OWL_HEAD), fill=_rgb(fill) + (255,))
    _stroke(d, H_(OWL_HEAD), (3.2 + 1.4 * head_k) * k, _rgb(head_col) + (255,), closed=True)
    c = _rgb(col) + (255,)
    for cx in (46, 74):
        hexa = _hexagon(cx, 62, 14)
        if eyes == "open" and not sleepy:
            _stroke(d, H_(hexa), 2.6 * k, c, closed=True)
            (x, y), = H_([(cx, 63)])
            r = 3 * k
            d.ellipse([x - r, y - r, x + r, y + r], fill=c)
        else:
            _stroke(d, H_([hexa[1], hexa[0], hexa[5]]), 2.6 * k, c)
    _stroke(d, H_(OWL_BEAK), 2.6 * k, c)
    if zzz:
        zc = _rgb(color) + (255,)
        for x, y, s_ in ((100, 26, 5), (110, 14, 7), (123, 2, 9)):
            _stroke(d, P([(x, y), (x + s_, y), (x, y + s_), (x + s_, y + s_)]), 1.6 * S, zc)
    return img.resize((W, H), Image.LANCZOS)


def keyed_photo(img, key, matte=BG):
    """An RGBA image for a window whose `key` colour Windows paints see-through."""
    base = Image.new("RGBA", img.size, _rgb(matte) + (255,))
    base.alpha_composite(img)
    out = base.convert("RGB")
    alpha = img.getchannel("A").point(lambda a: 255 if a >= 90 else 0)
    keyed = Image.new("RGB", img.size, _rgb(key))
    keyed.paste(out, (0, 0), alpha)
    return ImageTk.PhotoImage(keyed)


def save_icon_files(folder):
    """archie.ico / archie.png / logo files in the new look (used by the shortcut)."""
    v = (12.5, 18.5, 95)     # a little breathing room around the ears
    owl_rgba(512, view=v).save(os.path.join(folder, "archie-logo-large.png"))
    owl_rgba(64, view=v).save(os.path.join(folder, "archie.png"))
    owl_rgba(256, view=v).save(os.path.join(folder, "archie.ico"),
                       sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])


# ---------------------------------------------------------------------------
# Slim scrollbar
# ---------------------------------------------------------------------------

class SlimScrollbar(tk.Canvas):
    """A thin, rounded scrollbar that hides itself when everything fits."""

    def __init__(self, master, target, width=8, **kw):
        super().__init__(master, width=width, bg=BG, highlightthickness=0, bd=0, **kw)
        self.target = target
        self.first, self.last = 0.0, 1.0
        self.hover = False
        self.w = width
        self.bind("<Configure>", lambda e: self._draw())
        self.bind("<Enter>", lambda e: self._set_hover(True))
        self.bind("<Leave>", lambda e: self._set_hover(False))
        self.bind("<ButtonPress-1>", self._press)
        self.bind("<B1-Motion>", self._drag)
        self.on_scroll = None

    def set(self, first, last):
        self.first, self.last = float(first), float(last)
        self._draw()
        if self.on_scroll:
            self.on_scroll()

    def _set_hover(self, on):
        self.hover = on
        self._draw()

    def _draw(self):
        self.delete("all")
        if self.last - self.first >= 0.999:
            return
        h = self.winfo_height()
        y0, y1 = self.first * h, self.last * h
        if y1 - y0 < 24:
            mid = (y0 + y1) / 2
            y0, y1 = max(0, mid - 12), min(h, mid + 12)
        x0, x1 = self.w * 0.25, self.w * 0.75
        color = "#3a3a3a" if self.hover else "#2a2a2a"
        r = (x1 - x0) / 2
        self.create_rectangle(x0, y0 + r, x1, y1 - r, fill=color, width=0)
        self.create_oval(x0, y0, x1, y0 + 2 * r, fill=color, width=0)
        self.create_oval(x0, y1 - 2 * r, x1, y1, fill=color, width=0)

    def _press(self, e):
        h = max(1, self.winfo_height())
        f = e.y / h
        if not (self.first <= f <= self.last):
            self.target.yview_moveto(max(0.0, f - (self.last - self.first) / 2))
        self._grab = (e.y, self.first)

    def _drag(self, e):
        y, f0 = self._grab
        self.target.yview_moveto(f0 + (e.y - y) / max(1, self.winfo_height()))


# ---------------------------------------------------------------------------
# Rounded window corners (Windows 11; falls back to a clipped shape on 10)
# ---------------------------------------------------------------------------

def round_corners(win, radius=14, border=BORDER):
    """Returns True if Windows drew smooth rounded corners and a border for us."""
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        from ctypes import wintypes
        win.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(win.winfo_id()) or win.winfo_id()
        pref = ctypes.c_int(2)                              # DWMWCP_ROUND
        ok = ctypes.windll.dwmapi.DwmSetWindowAttribute(
            wintypes.HWND(hwnd), 33, ctypes.byref(pref), 4) == 0
        if ok:
            r, g, b = _rgb(border)
            col = ctypes.c_uint(r | (g << 8) | (b << 16))
            ctypes.windll.dwmapi.DwmSetWindowAttribute(wintypes.HWND(hwnd), 34,
                                                       ctypes.byref(col), 4)
            return True
        w, h = win.winfo_width(), win.winfo_height()
        rgn = ctypes.windll.gdi32.CreateRoundRectRgn(0, 0, w + 1, h + 1, radius * 2, radius * 2)
        ctypes.windll.user32.SetWindowRgn(wintypes.HWND(hwnd), rgn, True)
    except Exception:
        pass
    return False
