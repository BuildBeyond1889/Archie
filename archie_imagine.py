"""
archie_imagine.py - pictures made on your own graphics card (Stable Diffusion XL).

No internet and no datacenter: the model (downloaded once by Get Image Maker.bat)
runs on the RTX 2080. It runs in its own helper process, so it can't slow down
or crash the chat, and it closes itself after 10 idle minutes to give your
memory back.

    python archie_imagine.py --worker      (Archie starts this itself)
"""

import datetime
import json
import os
import queue
import random
import re
import subprocess
import sys
import threading
import time

APP_DIR = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(APP_DIR, "Images", "models")
BASE = "stabilityai/stable-diffusion-xl-base-1.0"
VAE = "madebyollin/sdxl-vae-fp16-fix"          # stops SDXL making black images in half precision
BASE_FILES = ["model_index.json", "scheduler/*", "tokenizer/*", "tokenizer_2/*",
              "text_encoder/config.json", "text_encoder/model.fp16.safetensors",
              "text_encoder_2/config.json", "text_encoder_2/model.fp16.safetensors",
              "unet/config.json", "unet/diffusion_pytorch_model.fp16.safetensors",
              "vae/config.json", "vae/diffusion_pytorch_model.fp16.safetensors"]
VAE_FILES = ["config.json", "diffusion_pytorch_model.safetensors"]
SHAPES = {"square": (1024, 1024), "wide": (1216, 832), "tall": (832, 1216)}
SKETCH = "TencentARC/t2i-adapter-sketch-sdxl-1.0"      # reads the lines of your sketch (about 150 MB)
SKETCH_FILES = ["config.json", "diffusion_pytorch_model.fp16.safetensors"]
# how closely to follow the sketch: (how strongly, for what share of the painting)
FOLLOW = {"loose": (0.55, 0.7), "balanced": (0.8, 0.9), "strict": (1.0, 1.0)}
STYLES = {
    "concept art": "digital concept art, painterly, dramatic lighting, detailed design",
    "cinematic still": "cinematic film still, 35mm photograph, realistic lighting, shallow depth of field, color graded",
    "anime": "anime key visual, clean line art, cel shading, vibrant colors",
    "cel-shaded game art": "cel-shaded stylized 3D game art, hard-edged shadows, clean shapes",
    "comic book": "comic book art, bold ink outlines, flat colors, halftone dots",
    "graphic novel noir": "black and white graphic novel ink art, high contrast, heavy shadows, single red accent color",
    "painterly": "painterly illustration, visible brush strokes, soft edges, rich color",
    "oil painting": "oil painting on canvas, thick impasto brushwork",
    "watercolor": "watercolor painting, soft washes, paper texture",
    "ink and wash": "ink and wash illustration, expressive brush ink lines, gray washes",
    "charcoal": "charcoal drawing, smudged, dramatic black and white",
    "storyboard": "storyboard frame, rough gray-tone marker rendering, clear staging",
    "character sheet": "character design sheet, full body, plain light background, clean rendering",
    "matte painting": "epic matte painting, vast detailed environment, film backdrop",
    "dark fantasy": "dark fantasy art, gothic, moody, heavy shadows",
    "sci-fi": "science fiction concept art, hard-surface design, glowing technology",
    "3D render": "3D render, smooth materials, studio lighting, high detail",
    "low poly": "low poly 3D art, faceted geometry, flat shaded colors",
    "pixel art": "pixel art, retro 16-bit game style, limited palette",
    "clay / stop motion": "claymation stop-motion, handmade clay figures, miniature set",
}
SKETCH_NEGATIVE = ("blurry, low quality, deformed hands, extra fingers, extra limbs, watermark, text, "
                   "signature, pencil lines, paper texture, sketch")
IDLE_EXIT = 600

EXPAND_PROMPT = """Turn the user's request into a strong prompt for the Stable Diffusion XL image model.
{about}
Request: {request}

Write:
- "prompt": one detailed paragraph (40-80 words): the subject, setting, composition and \
camera/framing, lighting, colors and mood, then the medium/style (e.g. "digital concept art", \
"character design sheet", "cinematic film still", "pencil storyboard sketch", "3D render"). \
Concrete visual words only; no instructions to the AI and no text/lettering unless asked.
- "negative": things to avoid, comma separated (always include: blurry, low quality, \
deformed hands, extra fingers, watermark, text, signature).
- "shape": "square", "wide" (landscapes, scenes, storyboards) or "tall" (characters, posters).

Return JSON only: {{"prompt": "...", "negative": "...", "shape": "..."}}"""

_DRAW = re.compile(r"^\s*(?:hey\s+)?(?:archie[,:]?\s+)?(?:can you\s+|could you\s+|please\s+)?"
                   r"(?:draw|paint|imagine|illustrate|render|visuali[sz]e|sketch|picture)\b\s*(?:me\s+)?(?P<a>.+)$"
                   r"|\b(?:make|create|generate|design|give me|do)\b\s+(?:me\s+)?(?:an?|some|\d+)?\s*"
                   r"(?:new\s+)?(?:image|images|picture|pictures|pic|drawing|illustration|concept art|artwork|"
                   r"painting|render|poster|wallpaper|character design|storyboard frame)s?\b\s*(?:of|for|showing|with)?\s*(?P<b>.*)$",
                   re.I)


def parse_draw(text):
    """The thing to draw, or None. 'image: ...' means use the words exactly."""
    t = text.strip()
    if t.lower().startswith(("image:", "img:", "prompt:")):
        return {"raw": True, "what": t.split(":", 1)[1].strip(), "n": 1}
    m = _DRAW.search(t)
    if not m:
        return None
    what = (m.group("a") or m.group("b") or "").strip(" .!?")
    if re.match(r"(if|that|what|how|why|you|we|i)\b", what, re.I):
        return None
    if m.group("a") is not None and re.match(r"(a |an )?(conclusion|comparison|line|graph|chart|diagram)\b", what, re.I):
        return None
    n = re.search(r"\b([1-4]|one|two|three|four)\s+(?:new\s+)?(?:images|pictures|pics|versions|variations|options|drawings)\b", t, re.I)
    n = {"one": 1, "two": 2, "three": 3, "four": 4}.get(n.group(1).lower(), None) if n and not n.group(1).isdigit() \
        else (int(n.group(1)) if n else 1)
    return {"raw": False, "what": what or t, "n": n}


def local_path(repo):
    """The downloaded folder for a model, so loading never asks the internet (or checks
    for files we deliberately didn't download)."""
    root = os.path.join(MODELS_DIR, "models--" + repo.replace("/", "--"))
    try:
        with open(os.path.join(root, "refs", "main")) as f:
            snap = os.path.join(root, "snapshots", f.read().strip())
        if os.path.isdir(snap):
            return snap
    except OSError:
        pass
    snaps = os.path.join(root, "snapshots")
    if os.path.isdir(snaps):
        for d in sorted(os.listdir(snaps)):
            if os.path.isfile(os.path.join(snaps, d, "model_index.json")) or \
               os.path.isfile(os.path.join(snaps, d, "config.json")):
                return os.path.join(snaps, d)
    return repo


def _takes(fn, name):
    import inspect
    try:
        return name in inspect.signature(fn.__call__).parameters
    except (TypeError, ValueError):
        return False


def load_sketch_pipe(torch, base):
    """The sketch-following version of the image model. It shares the big model already
    loaded (no second 7 GB copy) and adds the small sketch reader."""
    import inspect
    from diffusers import T2IAdapter, StableDiffusionXLAdapterPipeline
    path = local_path(SKETCH)
    if path == SKETCH:
        raise RuntimeError("The sketch reader isn't downloaded yet. Quit Archie and run Get Sketch Model.bat.")
    try:
        adapter = T2IAdapter.from_pretrained(path, torch_dtype=torch.float16, variant="fp16")
    except (OSError, ValueError, EnvironmentError):
        adapter = T2IAdapter.from_pretrained(path, torch_dtype=torch.float16)
    accepted = inspect.signature(StableDiffusionXLAdapterPipeline.__init__).parameters
    parts = {k: v for k, v in base.components.items() if k in accepted}
    sp = StableDiffusionXLAdapterPipeline(adapter=adapter, **parts)
    sp.set_progress_bar_config(disable=True)
    return sp


def load_pipe(torch):
    from diffusers import AutoencoderKL, StableDiffusionXLPipeline
    vae = AutoencoderKL.from_pretrained(local_path(VAE), torch_dtype=torch.float16)
    return StableDiffusionXLPipeline.from_pretrained(
        local_path(BASE), vae=vae, torch_dtype=torch.float16, variant="fp16", use_safetensors=True)


def sketch_installed():
    return os.path.isdir(os.path.join(MODELS_DIR, "models--" + SKETCH.replace("/", "--")))


def sketch_shape(path):
    """square / wide / tall, from the sketch's proportions."""
    from PIL import Image, ImageOps
    with Image.open(path) as im:
        im = ImageOps.exif_transpose(im)
        w, h = im.size
    r = w / float(h or 1)
    return "wide" if r > 1.2 else "tall" if r < 0.83 else "square"


def _component_sizes(a):
    """Label 8-connected blobs of True pixels -> (label grid, size of each label).
    Uses SciPy when it's there, otherwise a small union-find over the lit pixels."""
    import numpy as np
    try:
        from scipy import ndimage
        lab, n = ndimage.label(a, structure=np.ones((3, 3), bool))
        return lab, np.bincount(lab.ravel(), minlength=n + 1)
    except ImportError:
        pass
    H, W = a.shape
    ys, xs = np.nonzero(a)
    n = len(ys)
    idx = -np.ones((H + 1, W + 2), dtype=np.int64)       # padded so neighbours never wrap
    idx[ys, xs + 1] = np.arange(n)
    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for k in range(n):
        y, x = ys[k], xs[k] + 1
        for j in (idx[y, x - 1], idx[y - 1, x - 1], idx[y - 1, x], idx[y - 1, x + 1]):
            if j >= 0:
                ri, rj = find(k), find(int(j))
                if ri != rj:
                    parent[ri] = rj
    roots = np.fromiter((find(k) for k in range(n)), dtype=np.int64, count=n)
    _, inv, counts = np.unique(roots, return_inverse=True, return_counts=True)
    lab = np.zeros((H, W), dtype=np.int64)
    lab[ys, xs] = inv + 1
    return lab, np.concatenate([[0], counts])


def _despeckle(lines):
    """Drop the tiny specks that pencil smudges and paper grain leave behind (they turn into
    glowing dots in the painting), keeping every real stroke, however thin."""
    import numpy as np
    from PIL import Image
    a = np.asarray(lines) > 127
    if not a.any():
        return lines
    try:
        lab, sizes = _component_sizes(a)
    except Exception:
        return lines
    min_px = max(12, int(a.size * 0.000016))                 # about 24 px on a 1400 px photo
    keep = sizes >= min_px
    keep[0] = False
    return Image.fromarray((keep[lab] * 255).astype(np.uint8))


def sketch_lines(path, size):
    """Your sketch as clean white lines on black (what the sketch reader expects),
    fitted into `size`. Works for photos of paper (evens out shadows), tablet drawings
    and dark-mode Excalidraw."""
    from PIL import Image, ImageFilter, ImageOps, ImageStat
    W, H = size
    with Image.open(path) as im:
        im = ImageOps.exif_transpose(im)
        if im.mode in ("RGBA", "LA", "P"):
            im = im.convert("RGBA")
            bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
            bg.alpha_composite(im)
            im = bg
        g = im.convert("L")
    g.thumbnail((1400, 1400))
    if ImageStat.Stat(g).mean[0] < 110:          # light lines on a dark background
        g = ImageOps.invert(g)
    import numpy as np
    paper = g.filter(ImageFilter.GaussianBlur(max(8, min(g.size) // 25)))
    ratio = np.asarray(g, dtype=np.float32) / np.maximum(np.asarray(paper, dtype=np.float32), 1.0)
    flat = Image.fromarray(np.clip(ratio * 255.0, 0, 255).astype(np.uint8))   # evens out shadows
    flat = ImageOps.autocontrast(flat, cutoff=1)
    lines = flat.point(lambda v: 255 if v < 170 else 0)          # dark strokes -> white lines
    lines = _despeckle(lines)                                      # paper grain / smudge dots out
    lines = lines.filter(ImageFilter.MaxFilter(3))
    lines.thumbnail((W, H), Image.LANCZOS)
    out = Image.new("L", (W, H), 0)
    out.paste(lines, ((W - lines.width) // 2, (H - lines.height) // 2))
    return out.convert("RGB")


DESCRIBE_SKETCH = """This is the user's rough sketch. They want an image generator to turn it into a finished picture.
{words}
Look at the sketch and write JSON:
- "summary": what's in it, as short phrases separated by " · " (figures and what they're doing, the setting, key objects, where things are). Max 25 words.
- "prompt": one vivid paragraph (35-70 words) describing the finished scene for the image generator: subject and action, setting, composition, lighting, mood, colors. Match the sketch's layout. Don't mention that it's a sketch or drawing, and don't name an art style.
Return JSON only: {{"summary": "...", "prompt": "..."}}"""


def describe_sketch(ollama_url, model, image_b64, words=""):
    """Ask the vision model what the sketch shows -> {'summary', 'prompt'}."""
    import urllib.request
    body = {"model": model, "stream": False, "format": "json",
            "options": {"temperature": 0.3, "num_predict": 300},
            "messages": [{"role": "user", "images": [image_b64],
                          "content": DESCRIBE_SKETCH.format(
                              words=(f"They say: \"{words}\"" if words else ""))}]}
    req = urllib.request.Request(ollama_url + "/api/chat", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=240) as r:
        text = json.load(r).get("message", {}).get("content", "")
    try:
        data = json.loads(text)
    except ValueError:
        m = re.search(r"\{.*\}", text, re.S)
        data = json.loads(m.group(0)) if m else {}
    return {"summary": str(data.get("summary", "")).strip(), "prompt": str(data.get("prompt", "")).strip()}


def installed():
    """None if ready, else a plain explanation of what's missing."""
    try:
        import importlib.util
        for mod in ("torch", "diffusers", "transformers", "accelerate"):
            if importlib.util.find_spec(mod) is None:
                return "not_installed"
    except Exception:
        return "not_installed"
    if not os.path.isdir(os.path.join(MODELS_DIR, "models--" + BASE.replace("/", "--"))):
        return "no_model"
    return None


MESSAGES = {
    "not_installed": "Making images needs a one-time setup. Quit Archie, run Get Image Maker.bat "
                     "(needs the internet once, about 10 GB), then start Archie again.",
    "no_model": "The image model isn't downloaded yet. Quit Archie and run Get Image Maker.bat.",
}


# ---------------------------------------------------------------------------
# The helper process
# ---------------------------------------------------------------------------

def _send(obj):
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


def _heartbeat(state):
    """While something slow happens (first PyTorch import, reading 7 GB off the drive),
    keep telling Archie what's going on so it never looks frozen."""
    start = time.time()
    while state.get("on"):
        time.sleep(5)
        if state.get("on"):
            el = int(time.time() - start)
            _send({"type": "status", "text": f"{state['what']} ({el // 60}:{el % 60:02d})"})


def _unthrottle():
    """Windows treats a windowless process as 'background' and can slow it right down
    (Efficiency mode). Opt out so loading PyTorch runs at full speed."""
    if os.name != "nt":
        return
    try:
        import ctypes
        from ctypes import wintypes

        class PPTS(ctypes.Structure):
            _fields_ = [("Version", wintypes.ULONG), ("ControlMask", wintypes.ULONG),
                        ("StateMask", wintypes.ULONG)]
        k32 = ctypes.windll.kernel32
        k32.GetCurrentProcess.restype = wintypes.HANDLE
        k32.SetProcessInformation.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
        k32.SetPriorityClass.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        h = k32.GetCurrentProcess()
        st = PPTS(1, 0x1 | 0x4, 0)      # execution speed + timer resolution: not throttled
        k32.SetProcessInformation(h, 4, ctypes.byref(st), ctypes.sizeof(st))
        k32.SetPriorityClass(h, 0x00008000)
    except Exception as e:
        sys.stderr.write(f"couldn't turn off throttling: {e}\n")


def _stdin_lines():
    """Archie's requests, one line at a time.

    On Windows a thread sitting in a blocking read on the pipe can freeze another thread
    that's loading a DLL (PyTorch/NumPy check the standard handles while they load), so
    the import hangs until Archie happens to send something. So never block on the pipe:
    peek, and only read what's already there."""
    if os.name != "nt":
        for line in sys.stdin:
            yield line
        return
    import ctypes
    import msvcrt
    from ctypes import wintypes
    k32 = ctypes.windll.kernel32
    k32.PeekNamedPipe.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p,
                                  ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
    fd = sys.stdin.fileno()
    h = msvcrt.get_osfhandle(fd)
    buf = b""
    while True:
        avail = wintypes.DWORD(0)
        if not k32.PeekNamedPipe(h, None, 0, None, ctypes.byref(avail), None):
            break                                   # Archie closed the pipe
        if avail.value:
            chunk = os.read(fd, avail.value)
            if not chunk:
                break
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                yield line.decode("utf-8", "replace") + "\n"
        else:
            time.sleep(0.2)
    if buf.strip():
        yield buf.decode("utf-8", "replace")


def worker():
    _unthrottle()
    _send({"type": "status", "text": "starting the image helper..."})
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
    pipe = None
    sketch_pipe = None
    active = [None]                         # which pipeline currently owns the graphics card
    inbox = queue.Queue()

    def read():
        for line in _stdin_lines():
            inbox.put(line)
        inbox.put(None)
    threading.Thread(target=read, daemon=True).start()
    last = time.time()
    while True:
        try:
            line = inbox.get(timeout=30)
        except queue.Empty:
            if time.time() - last > IDLE_EXIT:
                _send({"type": "bye"})
                return
            continue
        if line is None:
            return
        last = time.time()
        try:
            req = json.loads(line)
        except ValueError:
            continue
        if req.get("cmd") == "quit":
            return
        try:
            hb = {"on": True, "what": "loading PyTorch (the first time after a restart can take a few minutes)"}
            threading.Thread(target=_heartbeat, args=(hb,), daemon=True).start()
            sys.stderr.write(f"{datetime.datetime.now():%H:%M:%S} importing torch\n")
            sys.stderr.flush()
            import faulthandler
            faulthandler.dump_traceback_later(90, repeat=True, file=sys.stderr)   # show where it's stuck
            try:
                import torch
            finally:
                faulthandler.cancel_dump_traceback_later()
            sys.stderr.write(f"{datetime.datetime.now():%H:%M:%S} torch imported\n")
            sys.stderr.flush()
            if pipe is None:
                sys.stderr.write(f"torch {torch.__version__}, cuda build {torch.version.cuda}, "
                                 f"available {torch.cuda.is_available()}\n")
                sys.stderr.flush()
                if not torch.cuda.is_available():
                    raise RuntimeError("PyTorch can't see your NVIDIA graphics card. Run Get Image "
                                       "Maker.bat again (it installs the CUDA version of PyTorch).")
                hb["what"] = "loading the image libraries"
                import diffusers  # noqa: F401
                hb["what"] = "loading the 7 GB image model from D: (only the first time)"
                pipe = load_pipe(torch)
                pipe.enable_model_cpu_offload()      # fits SDXL in 8 GB next to Windows
                try:
                    pipe.vae.enable_tiling()         # newer diffusers (the old name was removed)
                except Exception:
                    try:
                        pipe.enable_vae_tiling()
                    except Exception:
                        pass                          # optional: only saves a little memory
                pipe.set_progress_bar_config(disable=True)
                active[0] = pipe
            run = pipe
            lines_img = None
            if req.get("sketch"):
                if sketch_pipe is None:
                    hb["what"] = "loading the sketch reader (only the first time)"
                    sketch_pipe = load_sketch_pipe(torch, pipe)
                if active[0] is not sketch_pipe:
                    sketch_pipe.enable_model_cpu_offload()
                    active[0] = sketch_pipe
                run = sketch_pipe
            elif active[0] is not pipe:
                pipe.enable_model_cpu_offload()
                active[0] = pipe
            hb["on"] = False
            _send({"type": "status", "text": "painting..."})
            w, h = SHAPES.get(req.get("shape"), SHAPES["square"])
            steps = int(req.get("steps", 30))
            n = max(1, min(4, int(req.get("n", 1))))
            os.makedirs(req["out_dir"], exist_ok=True)
            extra = {}
            if req.get("sketch"):
                lines_img = sketch_lines(req["sketch"], (w, h))
                try:
                    if int(getattr(run.adapter.config, "in_channels", 3)) == 1:
                        lines_img = lines_img.convert("L")
                except Exception:
                    pass
                lp = os.path.join(req["out_dir"], f"{datetime.datetime.now():%H%M%S}_lines.png")
                lines_img.save(lp)
                _send({"type": "lines", "path": lp})
                scale, factor = FOLLOW.get(req.get("follow"), FOLLOW["balanced"])
                extra = {"image": lines_img, "adapter_conditioning_scale": scale,
                         "adapter_conditioning_factor": factor}
            for i in range(n):
                base = req.get("seed")
                seed = int(base) + i if base is not None else random.randint(1, 2 ** 31 - 1)
                gen = torch.Generator("cuda").manual_seed(seed)

                def on_step(_p, step, _t, kw, i=i):
                    _send({"type": "progress", "i": i, "n": n, "step": step + 1, "steps": steps})
                    return kw
                args = dict(prompt=req["prompt"], negative_prompt=req.get("negative") or None,
                            width=w, height=h, num_inference_steps=steps,
                            guidance_scale=float(req.get("cfg", 6.0)), generator=gen, **extra)
                if _takes(run, "callback_on_step_end"):
                    args["callback_on_step_end"] = on_step
                elif _takes(run, "callback"):
                    args["callback"] = lambda step, _t, _lat, i=i: _send(
                        {"type": "progress", "i": i, "n": n, "step": step + 1, "steps": steps})
                    args["callback_steps"] = 1
                img = run(**args).images[0]
                from PIL.PngImagePlugin import PngInfo
                meta = PngInfo()
                meta.add_text("prompt", req["prompt"])
                meta.add_text("negative", req.get("negative") or "")
                meta.add_text("seed", str(seed))
                meta.add_text("made_by", "Archie (Stable Diffusion XL, offline)")
                if req.get("sketch"):
                    meta.add_text("sketch", req["sketch"])
                    meta.add_text("follow", str(req.get("follow")))
                stamp = datetime.datetime.now().strftime("%H%M%S")
                path = os.path.join(req["out_dir"], f"{stamp}_{seed}.png")
                img.save(path, pnginfo=meta)
                _send({"type": "image", "path": path, "seed": seed, "i": i, "n": n})
            torch.cuda.empty_cache()
            _send({"type": "done"})
        except BaseException as e:
            hb["on"] = False
            import traceback
            traceback.print_exc()
            sys.stderr.flush()
            msg = f"{type(e).__name__}: {e}"
            if "out of memory" in msg.lower():
                msg = ("the graphics card ran out of memory. Close games/other GPU apps and try again, "
                       "or pick fewer pictures at once.")
                try:
                    import torch
                    torch.cuda.empty_cache()
                except Exception:
                    pass
            _send({"type": "error", "text": msg})
        last = time.time()


# ---------------------------------------------------------------------------
# Archie's side: talks to the helper
# ---------------------------------------------------------------------------

def _hidden_console():
    """Start the helper with its own console that's just hidden, the same way the test
    .bat runs it (a process with no console at all has been very slow to load PyTorch)."""
    if os.name != "nt":
        return {}
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = 0                                  # SW_HIDE
    return {"startupinfo": si,
            "creationflags": subprocess.CREATE_NEW_CONSOLE | 0x00008000}   # + above-normal priority


class ImageMaker:
    def __init__(self, on_event):
        self.on_event = on_event            # (dict) -> called from a background thread
        self.proc = None
        self.lock = threading.Lock()
        self.working = False                # True while an image is being made (audiobooks wait)

    def _start(self):
        if self.proc and self.proc.poll() is None:
            return
        exe = sys.executable
        if exe.lower().endswith("pythonw.exe"):          # keep it windowless, but able to talk
            alt = exe[:-len("pythonw.exe")] + "python.exe"
            exe = alt if os.path.exists(alt) else exe
        env = dict(os.environ)    # the same setup that works in Test Image Maker.bat
        env["PYTHONUNBUFFERED"] = "1"
        os.makedirs(os.path.join(APP_DIR, "Images"), exist_ok=True)
        self.log_path = os.path.join(APP_DIR, "Images", "image_helper.log")
        log = open(self.log_path, "a", encoding="utf-8")
        log.write(f"\n--- {datetime.datetime.now():%Y-%m-%d %H:%M:%S} starting {exe} ---\n")
        log.flush()
        self.proc = subprocess.Popen(
            [exe, os.path.abspath(__file__), "--worker"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=log, text=True, bufsize=1, cwd=APP_DIR, env=env, **_hidden_console())
        self.last_heard = time.time()
        threading.Thread(target=self._read, args=(self.proc,), daemon=True).start()

    def _read(self, proc):
        for line in proc.stdout:
            self.last_heard = time.time()
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            if ev.get("type") in ("done", "error", "bye"):
                self.working = False
            self.on_event(ev)
        self.working = False
        try:
            code = proc.wait(timeout=10)
        except Exception:
            code = None
        if code not in (0, None):
            self.on_event({"type": "error", "text": "the image helper stopped: " + self.last_error()})

    def last_error(self):
        """The most useful line from the helper's log."""
        try:
            with open(self.log_path, encoding="utf-8", errors="replace") as f:
                lines = [l.strip() for l in f.read().splitlines()[-40:] if l.strip()]
            for l in reversed(lines):
                if re.match(r"\w*(Error|Exception)\b|OSError|ImportError|ModuleNotFoundError|RuntimeError", l):
                    return l[:300]
            return lines[-1][:300] if lines else "no details"
        except OSError:
            return "no details"

    def make(self, prompt, negative, shape, n, steps, out_dir, seed=None, sketch=None, follow=None):
        with self.lock:
            self.working = True
            self._start()
            self.last_heard = time.time()
            self.proc.stdin.write(json.dumps({"prompt": prompt, "negative": negative, "shape": shape,
                                              "n": n, "steps": steps, "out_dir": out_dir,
                                              "seed": seed, "sketch": sketch, "follow": follow}) + "\n")
            self.proc.stdin.flush()

    def stop(self):
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.stdin.write(json.dumps({"cmd": "quit"}) + "\n")
                self.proc.stdin.flush()
                self.proc.wait(timeout=5)
            except Exception:
                self.proc.kill()


def free_ollama_gpu(ollama_url):
    """Ask Ollama to unload chat models so the image model gets the graphics card.
    (They load back in a few seconds the next time you chat.)"""
    import urllib.request
    try:
        with urllib.request.urlopen(ollama_url + "/api/ps", timeout=3) as r:
            loaded = [m["name"] for m in json.load(r).get("models", [])]
    except Exception:
        return
    for name in loaded:
        try:
            req = urllib.request.Request(ollama_url + "/api/generate",
                                         data=json.dumps({"model": name, "keep_alive": 0}).encode(),
                                         headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=10).read()
        except Exception:
            pass


def download():
    """Used by Get Image Maker.bat (online, once)."""
    from huggingface_hub import snapshot_download
    os.makedirs(MODELS_DIR, exist_ok=True)
    print("Downloading the SDXL image model (about 7 GB)...")
    snapshot_download(BASE, allow_patterns=BASE_FILES, cache_dir=MODELS_DIR)
    print("Downloading the colour fix (about 330 MB)...")
    snapshot_download(VAE, allow_patterns=VAE_FILES, cache_dir=MODELS_DIR)
    import torch
    print("Graphics card found:", torch.cuda.get_device_name(0) if torch.cuda.is_available()
          else "NO - PyTorch can't see it (images will not work)")
    print("Image model ready.")


def download_sketch():
    """Used by Get Sketch Model.bat (online, once)."""
    from huggingface_hub import snapshot_download
    os.makedirs(MODELS_DIR, exist_ok=True)
    print("Downloading the sketch reader (T2I-Adapter sketch for SDXL, about 150-300 MB)...")
    try:
        snapshot_download(SKETCH, allow_patterns=SKETCH_FILES, cache_dir=MODELS_DIR)
        snap = local_path(SKETCH)
        if not os.path.exists(os.path.join(snap, "diffusion_pytorch_model.fp16.safetensors")):
            raise FileNotFoundError("no fp16 file")
    except Exception:
        snapshot_download(SKETCH, allow_patterns=["config.json", "diffusion_pytorch_model.safetensors"],
                          cache_dir=MODELS_DIR)
    print("Sketch reader ready.")


def test():
    """Test Image Maker.bat: every step with timings, in a visible window."""
    os.environ["HF_HUB_OFFLINE"] = "1"
    t0 = time.time()

    def step(msg):
        print(f"[{time.time() - t0:6.1f}s] {msg}", flush=True)
    step("importing PyTorch...")
    import torch
    step(f"PyTorch {torch.__version__} (CUDA build {torch.version.cuda})")
    step(f"graphics card visible: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        step(f"card: {torch.cuda.get_device_name(0)}, "
             f"{torch.cuda.get_device_properties(0).total_memory / 2 ** 30:.1f} GB")
    step("importing diffusers...")
    import diffusers
    step(f"diffusers {diffusers.__version__}")
    step("loading the model (7 GB) from " + local_path(BASE))
    pipe = load_pipe(torch)
    pipe.enable_model_cpu_offload()
    step("model loaded. Painting a small test picture (10 steps)...")
    img = pipe("a red apple on a wooden table, photo", num_inference_steps=10, width=768, height=768).images[0]
    out = os.path.join(APP_DIR, "Images", "test.png")
    img.save(out)
    step(f"DONE. Test picture saved: {out}")


if __name__ == "__main__":
    if "--test" in sys.argv:
        try:
            test()
        except BaseException:
            import traceback
            traceback.print_exc()
    elif "--worker" in sys.argv:
        worker()
    elif "--download-sketch" in sys.argv:
        download_sketch()
    elif "--download" in sys.argv:
        download()
