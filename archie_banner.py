"""
archie_banner.py - the picture strip in Archie's header.

Pictures come from the Banners folder (drop in any .jpg / .png / .webp). The strip:
- crossfades to the next picture every few minutes (click it to skip),
- fades into the black header at both ends,
- is tinted by the time of day (warm morning, sunset evening, blue night with stars
  and a small lime moon),
- and shows the focus timer (a lime line along the bottom and the time) while it runs.

banners.json in the folder can say where to aim the crop for each picture:
{"harbor.jpg": [55, 38]}  (percent across, percent down).
"""

import datetime
import json
import os
import random

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

EXT = (".jpg", ".jpeg", ".png", ".webp", ".bmp")
BG = (10, 10, 10)
LIME = (198, 244, 50)


def list_pictures(folder):
    try:
        names = sorted(n for n in os.listdir(folder) if n.lower().endswith(EXT))
    except OSError:
        return []
    return [os.path.join(folder, n) for n in names]


def load_focus(folder):
    try:
        with open(os.path.join(folder, "banners.json"), encoding="utf-8") as f:
            data = json.load(f)
        return {k.lower(): (float(v[0]), float(v[1])) for k, v in data.items()}
    except (OSError, ValueError, TypeError, IndexError):
        return {}


def time_of_day(now=None):
    h = (now or datetime.datetime.now()).hour
    if 5 <= h < 10:
        return "morning"
    if 10 <= h < 17:
        return "day"
    if 17 <= h < 20:
        return "evening"
    return "night"


_cache = {}


def cover(path, W, H, focus=(50.0, 55.0)):
    """The picture scaled to fill W x H, cropped around `focus` (percent)."""
    key = (path, W, H, focus)
    if key in _cache:
        return _cache[key]
    with Image.open(path) as im:
        im = im.convert("RGB")
        iw, ih = im.size
        s = max(W / iw, H / ih)
        nw, nh = max(W, int(round(iw * s))), max(H, int(round(ih * s)))
        im = im.resize((nw, nh), Image.LANCZOS)
    fx, fy = focus[0] / 100.0, focus[1] / 100.0
    x = int(min(max(0, fx * nw - W / 2), nw - W))
    y = int(min(max(0, fy * nh - H / 2), nh - H))
    out = im.crop((x, y, x + W, y + H))
    if len(_cache) > 40:
        _cache.clear()
    _cache[key] = out
    return out


def _tint(img, tod, moon_left=False):
    if tod == "morning":      # soft gold haze
        out = Image.blend(img, ImageChops.multiply(img, Image.new("RGB", img.size, (255, 198, 140))), 0.6)
        return Image.blend(out, Image.new("RGB", img.size, (255, 222, 170)), 0.12)
    if tod == "evening":      # sunset orange, a bit darker
        out = Image.blend(img, ImageChops.multiply(img, Image.new("RGB", img.size, (255, 118, 70))), 0.75)
        return Image.blend(out, Image.new("RGB", img.size, (255, 140, 80)), 0.10)
    if tod == "night":
        out = Image.blend(img, Image.new("RGB", img.size, (8, 16, 48)), 0.62)
        d = ImageDraw.Draw(out)
        W, H = img.size
        rnd = random.Random(7)                           # the same stars every time
        for _ in range(max(6, W // 45)):
            x, y = rnd.random() * W, rnd.random() * H * 0.55
            r = 1 if rnd.random() < 0.7 else 1.5
            d.ellipse([x - r, y - r, x + r, y + r], fill=(255, 255, 255))
        cx, cy, r = W * (0.22 if moon_left else 0.82), H * 0.26, max(4, H * 0.12)  # a small lime moon
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=LIME)
        d.ellipse([cx - r + r * 0.55, cy - r - r * 0.35, cx + r + r * 0.55, cy + r - r * 0.35], fill=(8, 16, 48))
        return out
    return img


def _shape_mask(W, H, radius, fade):
    """Alpha: fade at both ends, rounded bottom corners (square top: flush with the window)."""
    ss = 3
    m = Image.new("L", (W * ss, H * ss), 0)
    d = ImageDraw.Draw(m)
    r = radius * ss
    d.rounded_rectangle([0, 0, W * ss - 1, H * ss - 1], radius=r, fill=255)
    d.rectangle([0, 0, W * ss - 1, H * ss - 1 - r], fill=255)
    m = m.resize((W, H), Image.LANCZOS)
    if fade:
        edge = max(1, int(W * 0.16))
        ramp = Image.new("L", (W, 1), 255)
        px = ramp.load()
        for x in range(edge):
            v = int(255 * (x / edge))
            px[x, 0] = v
            px[W - 1 - x, 0] = v
        m = ImageChops.multiply(m, ramp.resize((W, H)))
    return m


def compose(path, W, H, focus=(50.0, 55.0), tod="day", timer=None, font_path=None, scale=1.0,
            radius=12, fade=True, clock=None, clock_font=None):
    """One frame of the strip, already blended onto the header's black.
    timer = (fraction done 0..1, "18:42") while the focus timer runs, else None."""
    W, H = max(8, int(W)), max(8, int(H))
    img = _tint(cover(path, W, H, focus).copy(), tod, moon_left=bool(timer))
    if timer:
        frac, text = timer
        d = ImageDraw.Draw(img)
        bh = max(2, int(round(3 * scale)))
        d.rectangle([0, H - bh, W, H], fill=(10, 10, 10))
        d.rectangle([0, H - bh, int(W * max(0.0, min(1.0, frac))), H], fill=LIME)
        try:
            font = ImageFont.truetype(font_path, max(9, int(12 * scale))) if font_path else ImageFont.load_default()
        except OSError:
            font = ImageFont.load_default()
        tw = d.textlength(text, font=font)
        ph = int(18 * scale)
        pw = tw + int(16 * scale)
        x1 = W - int(W * 0.16) - int(4 * scale)        # just inside the faded edge
        x0 = x1 - pw
        y0 = (H - ph) / 2
        d.rounded_rectangle([x0, y0, x1, y0 + ph], radius=ph / 2, fill=LIME)
        d.text(((x0 + x1) / 2, y0 + ph / 2), text, font=font, fill=BG, anchor="mm")
    if clock:              # the time, bottom left (Micro 5 pixel font, small, dark outline)
        try:
            cf = ImageFont.truetype(clock_font or font_path, max(12, int(round(17 * scale))))
        except (OSError, TypeError, AttributeError):
            cf = ImageFont.load_default()
        x = int(W * 0.05)
        y = H - int(6 * scale) - (int(3 * scale) if timer else 0)
        glow = Image.new("L", (W, H), 0)                 # soft dark halo so it reads on bright skies
        ImageDraw.Draw(glow).text((x, y), clock, font=cf, fill=255, anchor="ls")
        glow = glow.filter(ImageFilter.GaussianBlur(max(1.0, 1.5 * scale))).point(lambda v: int(v * 0.7))
        img.paste((0, 0, 0), (0, 0), glow)
        d = ImageDraw.Draw(img)
        o = max(1, int(round(scale)))
        d.text((x + o, y + o), clock, font=cf, fill=(0, 0, 0), anchor="ls")
        d.text((x, y), clock, font=cf, fill=(240, 240, 232), anchor="ls")
    base = Image.new("RGB", (W, H), BG)
    base.paste(img, (0, 0), _shape_mask(W, H, int(radius * scale), fade))
    return base
