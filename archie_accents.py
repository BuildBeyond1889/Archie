"""
archie_accents.py - Archie's accent voices (voice plan step 2), run with the clone voice's own Python
(Archie\\Voice\\clone\\env: torch + chatterbox-tts, from Tools\\Get Accent Voices.bat).

  fetch   reference recordings from the VCTK corpus (CC BY 4.0, University of Edinburgh): only the chosen
          speakers' files, read out of the big zip over the internet (no 11 GB download when the server allows it),
          a ~12 s reference per speaker, then the same Archie line in every candidate voice (Voice\\accents\\audition)
  serve   for archie_voiced.py: one JSON line in {"id", "text", "ref"}, one line out {"id", "sr", "pcm": base64 float32}

Only real people who recorded for an open, licensed corpus: never a celebrity's voice.
"""

import base64
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
VOICE = os.path.join(HERE, "Voice")
ACC = os.path.join(VOICE, "accents")
VCTK_URL = "https://datashare.is.ed.ac.uk/bitstream/handle/10283/3443/VCTK-Corpus-0.92.zip"
LINE = "Hi, it's Archie. I've had a look at your notes, and I think we can finish this chapter before dinner."

# which VCTK speakers can stand in for each accent voice (picked from the corpus's own speaker list)
WANT = {
    "irish_woman": {"accent": ("irish",), "gender": "F", "n": 3},
    "irish_man": {"accent": ("irish",), "gender": "M", "n": 3},
    "londoner": {"accent": ("english",), "gender": "M", "n": 3, "region": ("london",), "oldest": True},
}


def say(*a):
    print(*a, flush=True)


def open_zip(local=None):
    if local and os.path.exists(local):
        import zipfile
        return zipfile.ZipFile(local)
    from remotezip import RemoteZip
    return RemoteZip(VCTK_URL, timeout=60)


def speakers(z):
    name = next(n for n in z.namelist() if n.endswith("speaker-info.txt"))
    out = []
    for line in z.read(name).decode("utf-8", "replace").splitlines()[1:]:
        p = line.split()
        if len(p) >= 4 and p[0].startswith("p"):
            out.append({"sp": p[0], "age": int(p[1]) if p[1].isdigit() else 0, "gender": p[2], "accent": p[3],
                        "region": " ".join(p[4:])})
    return out


def choose(sps):
    picks = {}
    for vid, w in WANT.items():
        pool = [s for s in sps if s["accent"].lower() in w["accent"] and (not w["gender"] or s["gender"] == w["gender"])]
        near = lambda s: any(r in s["region"].lower() for r in w.get("region") or ())
        pool.sort(key=lambda s: (not near(s), -s["age"] if w.get("oldest") else 0))
        picks[vid] = pool[: w["n"]]
    return picks


def make_ref(z, sp, dest):
    """About 12 seconds of one speaker: a few of their sentences joined, 24 kHz mono."""
    import numpy as np
    import soundfile as sf
    import librosa
    names = sorted(n for n in z.namelist() if f"/{sp}/" in n and n.endswith("_mic1.flac"))[2:16]
    parts, total = [], 0.0
    for n in names:
        a, sr = sf.read(io.BytesIO(z.read(n)), dtype="float32")
        if a.ndim > 1:
            a = a.mean(axis=1)
        a = librosa.resample(a, orig_sr=sr, target_sr=24000)
        parts += [a, np.zeros(int(0.25 * 24000), dtype="float32")]
        total += len(a) / 24000
        if total >= 12:
            break
    if total < 6:
        raise RuntimeError(f"{sp}: not enough audio")
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    sf.write(dest, np.concatenate(parts), 24000)


def load_model():
    import torch
    from chatterbox.tts_turbo import ChatterboxTurboTTS
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    return ChatterboxTurboTTS.from_pretrained(device=dev), dev


def fetch(local=None):
    import soundfile as sf
    say("[1/3] Reading the VCTK speaker list…")
    z = open_zip(local)
    picks = choose(speakers(z))
    say("[2/3] Reference recordings (a few sentences from each speaker)…")
    out = {}
    for vid, sps in picks.items():
        for s in sps:
            ref = os.path.join(ACC, vid, s["sp"], "ref.wav")
            if not os.path.exists(ref):
                try:
                    make_ref(z, s["sp"], ref)
                except Exception as e:
                    say("   skipped", s["sp"], e)
                    continue
            say(f"   {vid}: {s['sp']} ({s['gender']}, {s['age']}, {s['region'] or s['accent']})")
            out.setdefault(vid, []).append(dict(s, ref=os.path.relpath(ref, ACC).replace("\\", "/")))
    say("[3/3] Archie saying hello in each voice (the first time downloads the voice model, about 1.5 GB)…")
    model, dev = load_model()
    say("   running on", dev)
    os.makedirs(os.path.join(ACC, "audition"), exist_ok=True)
    for vid, cands in out.items():
        for c in cands:
            wav = os.path.join(ACC, "audition", f"{vid}_{c['sp']}.wav")
            if not os.path.exists(wav):
                a = model.generate(LINE, audio_prompt_path=os.path.join(ACC, c["ref"]))
                sf.write(wav, a.squeeze(0).cpu().numpy(), model.sr)
            c["wav"] = os.path.relpath(wav, ACC).replace("\\", "/")
    json.dump({"candidates": out, "line": LINE, "source": "VCTK Corpus 0.92, CSTR, University of Edinburgh (CC BY 4.0)"},
              open(os.path.join(ACC, "accents.json"), "w", encoding="utf-8"), indent=1)
    open(os.path.join(ACC, "CREDITS.txt"), "w", encoding="utf-8").write(
        "Reference voices: CSTR VCTK Corpus 0.92, Centre for Speech Technology Research, University of Edinburgh.\n"
        "Licence: Creative Commons Attribution 4.0 (https://creativecommons.org/licenses/by/4.0/). Used here to make Archie's accent voices.\n")
    say("Done:", sum(len(v) for v in out.values()), "voices to audition.")


def serve():
    import numpy as np
    out = sys.stdout
    sys.stdout = sys.stderr          # anything the libraries print goes to the log, never into Archie's replies
    model, dev = load_model()
    cur = {}
    out.write(json.dumps({"ev": "ready", "dev": dev}) + "\n")
    out.flush()
    for line in sys.stdin:
        try:
            c = json.loads(line)
        except ValueError:
            continue
        if c.get("op") == "quit":
            break
        try:
            import torch
            if c["ref"] != cur.get("ref"):           # study the speaker once, not every sentence
                model.prepare_conditionals(c["ref"])
                cur["ref"] = c["ref"]
            with torch.inference_mode():
                if dev == "cuda" and not cur.get("fp32"):
                    try:                              # half precision: much quicker on the graphics card
                        with torch.autocast("cuda", dtype=torch.float16):
                            a = model.generate(c["text"])
                    except Exception:
                        cur["fp32"] = True            # this card/model doesn't like it: full precision from now on
                        a = model.generate(c["text"])
                else:
                    a = model.generate(c["text"])
                a = a.squeeze(0).float().cpu().numpy().astype("float32")
            out = {"id": c.get("id"), "sr": model.sr, "pcm": base64.b64encode(np.ascontiguousarray(a).tobytes()).decode("ascii")}
        except Exception as e:
            out = {"id": c.get("id"), "error": f"{type(e).__name__}: {e}"}
        sys.__stdout__.write(json.dumps(out) + "\n")
        sys.__stdout__.flush()


def chapter():
    """Feather's chapter audio in an accent voice, made overnight by the hub. stdin {"paras", "ref"};
    stdout {"ok", "mp3": base64, "paras": [{"t0", "dur", "w": [[char, ms]]}]} like sonia_render.py (w = sentence starts)."""
    import re
    import subprocess
    import numpy as np
    try:
        import lameenc
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "lameenc"], stdout=sys.stderr, stderr=sys.stderr)
        import lameenc
    out = sys.stdout
    sys.stdout = sys.stderr
    req = json.loads(sys.stdin.read())
    paras, ref = [str(p) for p in req.get("paras") or []], req["ref"]
    import torch
    model, dev = load_model()
    model.prepare_conditionals(ref)
    sr = model.sr
    gap = np.zeros(int(0.35 * sr), dtype="float32")
    pcm, info, t = [], [], 0.0
    for i, p in enumerate(paras):
        text = p.strip()
        if not text:
            info.append({"t0": round(t), "dur": 0, "w": []})
            continue
        lead = len(p) - len(p.lstrip())
        starts = [lead] + [lead + m.end() for m in re.finditer(r"(?<=[.!?\u2026])[\"\u201d')\]]*\s+", text)]
        keep = [starts[0]]
        for st in starts[1:]:                       # no tiny pieces ("Mr." "Yes!"): join them to the next sentence
            if st - keep[-1] >= 16 and not re.search(r"\b(Mr|Mrs|Ms|Dr|St|Prof|Rev|Capt|Col|Gen|Lt|Sgt|Jr|Sr|vs|etc|No|[A-Z])\.[\"\u201d')\]]*\s*$", text[keep[-1] - lead:st - lead]):
                keep.append(st)
        starts = keep
        bits = [text[a - lead:b - lead].strip() for a, b in zip(starts, starts[1:] + [lead + len(text)])]
        w, t0 = [], t
        for st, bit in zip(starts, bits):
            if not bit:
                continue
            with torch.inference_mode():
                try:
                    with torch.autocast("cuda", dtype=torch.float16, enabled=dev == "cuda"):
                        a = model.generate(bit)
                except Exception:
                    a = model.generate(bit)
            a = a.squeeze(0).float().cpu().numpy().astype("float32")
            w.append([st, round(t - t0)])
            pcm.append(a)
            t += len(a) * 1000.0 / sr
        pcm.append(gap)
        t += len(gap) * 1000.0 / sr
        info.append({"t0": round(t0), "dur": round(t - t0), "w": w})
        sys.stderr.write(f"p {i + 1} {len(paras)}\n")
        sys.stderr.flush()
    allpcm = (np.clip(np.concatenate(pcm) if pcm else np.zeros(1, "float32"), -1, 1) * 32767).astype("<i2")
    enc = lameenc.Encoder()
    enc.set_bit_rate(48)
    enc.set_in_sample_rate(sr)
    enc.set_channels(1)
    enc.set_quality(5)
    mp3 = enc.encode(allpcm.tobytes()) + enc.flush()
    out.write(json.dumps({"ok": True, "mp3": base64.b64encode(bytes(mp3)).decode("ascii"), "paras": info}) + "\n")
    out.flush()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "chapter":
        try:
            chapter()
        except Exception as e:
            sys.__stdout__.write(json.dumps({"ok": False, "why": f"accent voice: {type(e).__name__}: {e}"}) + "\n")
        sys.exit(0)
    if len(sys.argv) > 1 and sys.argv[1] == "fetch":
        fetch(sys.argv[2] if len(sys.argv) > 2 else None)
    elif len(sys.argv) > 1 and sys.argv[1] == "serve":
        serve()
    else:
        say("usage: archie_accents.py fetch [VCTK zip] | serve")
