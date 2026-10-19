"""
archie_voice.py - voice notes, fully offline.

  Recorder     records the microphone straight to a .wav file (so even a
               2-hour lecture doesn't fill up memory, and nothing is lost if
               something crashes).
  Transcriber  turns the recording into text with Whisper (faster-whisper),
               running on your own PC. The model is downloaded once by
               Get Voice.bat; after that no internet is needed.
"""

import datetime
import os
import sys
import threading
import time
import wave

RATE = 16000                      # what Whisper listens at
DEFAULT_MODEL = "small.en"        # ~480 MB, good accuracy, quick on a normal CPU


class VoiceError(Exception):
    """A problem with a plain-language explanation."""


# ---------------------------------------------------------------------------
# Recording
# ---------------------------------------------------------------------------

class Recorder:
    def __init__(self, folder):
        self.folder = folder
        self.stream = None
        self.wav = None
        self.path = None
        self.frames = 0
        self.level = 0.0          # 0..1, how loud right now (for the button)
        self.paused = False       # while paused, nothing is written (the evening recap's pause)
        self.error = None
        self._lock = threading.Lock()

    @property
    def recording(self):
        return self.stream is not None

    def seconds(self):
        return self.frames / RATE

    def start(self):
        try:
            import sounddevice as sd
        except ImportError:
            raise VoiceError("Voice notes need a couple of extra pieces. Run Get Voice.bat "
                             "(once, while online), then restart Archie.")
        except OSError:
            raise VoiceError("Couldn't load the audio system. Run Get Voice.bat again.")
        os.makedirs(self.folder, exist_ok=True)
        stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
        self.path = os.path.join(self.folder, f"Voice {stamp}.wav")
        self.wav = wave.open(self.path, "wb")
        self.wav.setnchannels(1)
        self.wav.setsampwidth(2)
        self.wav.setframerate(RATE)
        self.frames, self.error = 0, None

        def callback(indata, frames, _time, status):
            if self.paused:
                self.level = 0.0
                return
            data = bytes(indata)
            with self._lock:
                if self.wav:
                    self.wav.writeframes(data)
                    self.frames += frames
            try:
                import numpy as np
                a = np.frombuffer(data, dtype=np.int16).astype(np.float32)
                self.level = min(1.0, float(np.sqrt(np.mean(a * a))) / 6000.0) if a.size else 0.0
            except Exception:
                pass

        try:
            self.stream = sd.RawInputStream(samplerate=RATE, channels=1, dtype="int16",
                                            blocksize=RATE // 10, callback=callback)
            self.stream.start()
        except Exception as e:
            self._close()
            try:
                os.remove(self.path)
            except OSError:
                pass
            self.stream = None
            raise VoiceError(f"Couldn't use the microphone ({e}). Check it's plugged in, and that "
                             "Windows Settings > Privacy & security > Microphone > \"Let desktop "
                             "apps access your microphone\" is on.")

    def _close(self):
        with self._lock:
            if self.wav:
                self.wav.close()
                self.wav = None

    def stop(self):
        """Stop and return (path, seconds). Very short recordings are thrown away."""
        if self.stream:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception:
                pass
            self.stream = None
        self._close()
        secs = self.seconds()
        if secs < 1.0:
            try:
                os.remove(self.path)
            except OSError:
                pass
            return None, secs
        return self.path, secs


# ---------------------------------------------------------------------------
# Transcribing
# ---------------------------------------------------------------------------

def _add_cuda_dlls():
    """GPU mode on Windows: make the pip-installed NVIDIA libraries findable."""
    if sys.platform != "win32":
        return
    import site
    for base in site.getsitepackages() + [site.getusersitepackages()]:
        for sub in ("cublas", "cudnn"):
            d = os.path.join(base, "nvidia", sub, "bin")
            if os.path.isdir(d):
                try:
                    os.add_dll_directory(d)
                except OSError:
                    pass
                os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")


class Transcriber:
    def __init__(self, models_dir, name=DEFAULT_MODEL, device="cpu"):
        self.models_dir = models_dir
        self.name = name or DEFAULT_MODEL
        self.device = device or "cpu"
        self._model = None
        self._lock = threading.Lock()

    def _load(self):
        if self._model is not None:
            return self._model
        os.environ.setdefault("HF_HUB_OFFLINE", "1")           # never go online from here
        os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
        try:
            if self.device == "cuda":
                _add_cuda_dlls()
            from faster_whisper import WhisperModel
        except ImportError:
            raise VoiceError("Voice notes need Whisper. Run Get Voice.bat (once, while online), "
                             "then restart Archie.")
        # use the model you picked; if it isn't here but another one is, use that
        have = [d[len("models--Systran--faster-whisper-"):] for d in
                (os.listdir(self.models_dir) if os.path.isdir(self.models_dir) else [])
                if d.startswith("models--Systran--faster-whisper-")]
        if self.name not in have:
            if not have:
                raise VoiceError("The speech model isn't downloaded yet. Quit Archie, run "
                                 "Get Voice.bat once while online, then start Archie again.")
            self.name = next((h for h in ("medium.en", "small.en", "base.en") if h in have), have[0])
        attempts = [(self.device, "float16" if self.device == "cuda" else "int8")]
        if self.device != "cpu":
            attempts.append(("cpu", "int8"))
        last = None
        for device, ctype in attempts:
            try:
                self._model = WhisperModel(self.name, device=device, compute_type=ctype,
                                           download_root=self.models_dir, local_files_only=True)
                self.device = device
                return self._model
            except Exception as e:
                last = e
        raise VoiceError(f"Couldn't start the speech model ({self.name}): {last}. "
                         "Try running Get Voice.bat again.")

    def transcribe(self, audio, progress=lambda frac: None, stop=None, pause=None, timed=None):
        """audio = a file path (any common format) or 16 kHz samples. Returns the text.
        progress(0..1) is called as it goes; pause() returning True makes it wait.
        Pass a list as `timed` to also get every piece as (start, end, text) in seconds."""
        with self._lock:
            model = self._load()
            english_only = self.name.endswith(".en")
            segments, info = model.transcribe(
                audio, language="en" if english_only else None, beam_size=5,
                vad_filter=True, vad_parameters={"min_silence_duration_ms": 700},
                condition_on_previous_text=True)
            total = float(getattr(info, "duration", 0) or 0)
            paras, cur, last_end = [], [], 0.0
            for seg in segments:
                if stop is not None and stop.is_set():
                    break
                while pause is not None and pause():
                    time.sleep(1.0)
                text = seg.text.strip()
                if not text:
                    continue
                if cur and seg.start - last_end > 2.0:          # a long pause = new paragraph
                    paras.append(" ".join(cur))
                    cur = []
                cur.append(text)
                if timed is not None:
                    timed.append((float(seg.start), float(seg.end), text))
                last_end = seg.end
                if total:
                    progress(min(1.0, seg.end / total))
            if cur:
                paras.append(" ".join(cur))
            return "\n\n".join(paras).strip()


def audio_info(path):
    """(duration in seconds, [(title, start, end), ...chapters]) using PyAV (comes with Whisper)."""
    import av
    with av.open(path) as c:
        dur = float(c.duration / av.time_base) if c.duration else 0.0
        chapters = []
        try:
            for ch in c.chapters():
                tb = float(ch["time_base"])
                title = (ch.get("metadata") or {}).get("title", "")
                chapters.append((title, ch["start"] * tb, ch["end"] * tb))
        except Exception:
            chapters = []
    return dur, chapters


def decode_range(path, start, end, rate=RATE):
    """Just one stretch of a long audiobook, as 16 kHz samples (so a 20-hour book
    never has to fit in memory at once)."""
    import av
    import numpy as np
    out, first_t = [], None
    with av.open(path) as c:
        stream = c.streams.audio[0]
        if start > 0:
            c.seek(int(start * av.time_base), backward=True, any_frame=False)
        res = av.AudioResampler(format="s16", layout="mono", rate=rate)
        for frame in c.decode(stream):
            t = float(frame.pts * frame.time_base) if frame.pts is not None else None
            if t is not None:
                if t + frame.samples / float(frame.sample_rate) < start:
                    continue
                if t >= end:
                    break
                if first_t is None:
                    first_t = t
            for f in res.resample(frame):
                out.append(f.to_ndarray().reshape(-1))
        for f in res.resample(None):
            out.append(f.to_ndarray().reshape(-1))
    if not out:
        return np.zeros(0, dtype=np.float32)
    a = np.concatenate(out).astype(np.float32) / 32768.0
    skip = int(max(0.0, start - (first_t or start)) * rate)
    keep = int((end - start) * rate) if end < float("inf") else len(a)
    return a[skip:skip + keep]


def fmt_time(secs):
    secs = int(round(secs))
    h, rem = divmod(secs, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


TIDY_PROMPT = """Below is a transcript of something the user said out loud (a voice note, \
lecture, or brainstorm). Turn it into clean, well-organized notes in Markdown:
- short headings for the main topics, bullet points under them
- fix obvious speech-to-text mistakes and remove filler ("um", repeats)
- keep ALL the information and their own wording and ideas; do NOT add facts
- output only the notes, no introduction

Transcript:
"""


def tidy(quick_chat, model, text, progress=lambda frac: None, chunk=12000):
    """Tidy a transcript into notes with the local chat model (long ones in pieces)."""
    pieces, buf = [], ""
    for para in text.split("\n\n"):
        if buf and len(buf) + len(para) > chunk:
            pieces.append(buf)
            buf = ""
        buf += ("\n\n" if buf else "") + para
    if buf:
        pieces.append(buf)
    out = []
    for i, p in enumerate(pieces, 1):
        progress((i - 1) / len(pieces))
        out.append(quick_chat(model, TIDY_PROMPT + p, max_tokens=4096, timeout=900,
                              num_ctx=16384, temperature=0.2))
    progress(1.0)
    return "\n\n".join(o.strip() for o in out if o and o.strip())
