"""
archie_speak.py - Archie talks back, fully offline.

Uses Piper (a small, natural-sounding text-to-speech engine that runs on your
own PC). Answers are spoken sentence by sentence *while* they're still being
written, so Archie starts talking within a second or two.

Get Voice.bat downloads Piper and a voice once; after that no internet.
"""

import os
import queue
import re
import threading

VOICES = {                       # name in settings -> what it sounds like
    "en_GB-alan-medium": "Alan, British man (fits an owl named after Merlin's)",
    "en_US-ryan-high": "Ryan, American man",
    "en_US-lessac-medium": "Lessac, American woman",
    "en_GB-jenny_dioco-medium": "Jenny, British woman",
}
DEFAULT_VOICE = "en_GB-alan-medium"

_SENTENCE_END = re.compile(r"(?<=[.!?:;])[\"')\]]*\s+|\n{2,}|\n(?=\s*(?:[-*•]|\d+[.)])\s)")


def speakable(text):
    """Turn Markdown answer text into something that sounds right out loud."""
    t = re.sub(r"```.*?(```|$)", " (I've put the code on screen.) ", text, flags=re.S)
    t = re.sub(r"`([^`]*)`", r"\1", t)
    t = re.sub(r"!\[\[[^\]]*\]\]|!\[[^\]]*\]\([^)]*\)", " ", t)          # images
    t = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]", r"\1", t)            # [[wiki|links]]
    t = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", t)                      # [text](url)
    t = re.sub(r"https?://\S+", " a link ", t)
    t = re.sub(r"^\s{0,3}#{1,6}\s*", "", t, flags=re.M)                 # headings
    t = re.sub(r"^\s*(?:[-*•+]|\d+[.)])\s+", "", t, flags=re.M)         # bullets
    t = re.sub(r"^\s*>\s?", "", t, flags=re.M)                          # quotes
    t = re.sub(r"\|", ", ", t)                                          # tables
    t = re.sub(r"[*_~]{1,3}([^*_~\n]+)[*_~]{1,3}", r"\1", t)            # bold / italic
    t = re.sub(r"^[-=*_]{3,}\s*$", " ", t, flags=re.M)                  # rules
    t = t.replace("→", " to ").replace("≈", " about ").replace("&", " and ")
    t = re.sub(r"\s*\(\s*\)", "", t)
    return re.sub(r"[ \t]+", " ", t).strip()


class Speaker:
    def __init__(self, voices_dir, voice=DEFAULT_VOICE, speed=1.0, on_error=print):
        self.voices_dir = voices_dir
        self.voice_name = voice or DEFAULT_VOICE
        self.speed = speed or 1.0
        self.on_error = on_error
        self.q = queue.Queue()
        self.buf = ""
        self.in_code = False
        self.stop_evt = threading.Event()
        self.speaking = threading.Event()
        self._voice = None
        self._thread = None
        self._gen = 0              # bumps on stop() so queued sentences are dropped

    # --- what callers use -------------------------------------------------------

    def model_path(self):
        return os.path.join(self.voices_dir, self.voice_name + ".onnx")

    def ready(self):
        """None if Archie can talk, else a plain explanation of what's missing."""
        try:
            import piper  # noqa: F401
            import sounddevice  # noqa: F401
        except ImportError:
            return ("Talking needs a couple of extra pieces. Quit Archie, run Get Voice.bat "
                    "(once, while online), then start Archie again.")
        except OSError:
            return "Couldn't load the audio system. Run Get Voice.bat again."
        if not os.path.exists(self.model_path()):
            return (f"The voice ({self.voice_name}) isn't downloaded yet. Quit Archie and run "
                    "Get Voice.bat once while online.")
        return None

    def say(self, text):
        """Speak a whole piece of text (e.g. 'read aloud')."""
        self.stop()
        self.feed(text)
        self.flush()

    def feed(self, piece):
        """Add streamed answer text; complete sentences start playing right away."""
        self.buf += piece
        while True:
            m = _SENTENCE_END.search(self.buf)
            if not m:
                break
            sentence, self.buf = self.buf[:m.end()], self.buf[m.end():]
            self._queue(sentence)
        if len(self.buf) > 400:                     # a very long run-on: say it anyway
            cut = self.buf.rfind(" ", 0, 300)
            cut = cut if cut > 0 else 300
            self._queue(self.buf[:cut])
            self.buf = self.buf[cut:]

    def flush(self):
        if self.buf.strip():
            self._queue(self.buf)
        self.buf = ""
        self.in_code = False

    def stop(self):
        """Stop talking now and forget anything waiting to be said."""
        self._gen += 1
        self.buf = ""
        self.in_code = False
        self.stop_evt.set()
        try:
            while True:
                self.q.get_nowait()
        except queue.Empty:
            pass

    # --- inside ---------------------------------------------------------------------

    def _queue(self, sentence):
        # skip code blocks that arrive a line at a time while streaming
        fences = sentence.count("```")
        if self.in_code or fences:
            if fences % 2 == 1:
                was = self.in_code
                self.in_code = not self.in_code
                if not was:
                    sentence = sentence.split("```")[0] + " (I've put the code on screen.)"
                else:
                    sentence = sentence.rsplit("```", 1)[-1]
            elif self.in_code:
                return
        text = speakable(sentence)
        if not re.search(r"[A-Za-z0-9]", text):
            return
        self.q.put((self._gen, text))
        if self._thread is None or not self._thread.is_alive():
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()

    def _load(self):
        if self._voice is None:
            from piper import PiperVoice
            self._voice = PiperVoice.load(self.model_path())
        return self._voice

    def _run(self):
        try:
            import sounddevice as sd
            voice = self._load()
            try:
                from piper import SynthesisConfig
                syn = SynthesisConfig(length_scale=1.0 / max(0.5, min(2.0, float(self.speed))))
            except Exception:
                syn = None
            rate = int(getattr(getattr(voice, "config", None), "sample_rate", 22050) or 22050)
        except Exception as e:
            self.on_error(f"I couldn't start talking: {e}")
            return
        stream = None
        try:
            while True:
                try:
                    gen, text = self.q.get(timeout=1.5)
                except queue.Empty:
                    break
                if gen != self._gen:
                    continue
                self.stop_evt.clear()
                self.speaking.set()
                for chunk in voice.synthesize(text, syn):
                    if self.stop_evt.is_set() or gen != self._gen:
                        break
                    sr = int(getattr(chunk, "sample_rate", rate) or rate)
                    if stream is None or stream.samplerate != sr:
                        if stream is not None:
                            stream.close()
                        stream = sd.RawOutputStream(samplerate=sr, channels=1, dtype="int16")
                        stream.start()
                    data = chunk.audio_int16_bytes
                    step = sr // 10 * 2                  # 0.1 s at a time, so Stop is instant
                    for i in range(0, len(data), step):
                        if self.stop_evt.is_set() or gen != self._gen:
                            break
                        stream.write(data[i:i + step])
                self.speaking.clear()
        except Exception as e:
            self.on_error(f"Talking stopped: {e}")
        finally:
            self.speaking.clear()
            if stream is not None:
                try:
                    stream.stop()
                    stream.close()
                except Exception:
                    pass
