"""
archie_voiced.py - Archie's voice, as a small helper program.

Archie starts this with the voice's own Python (Voice\\kokoro\\env), so the voice's
add-ons never touch the ones the rest of Archie uses. It reads one JSON command per
line on stdin and writes one JSON event per line on stdout:

  {"op": "say", "gen": 3, "id": "a1", "text": "...", "voice": {...}, "speed": 0.95, "room": true}
  {"op": "stop", "gen": 4}          drop everything older than gen 4, silence now
  {"op": "file", "text": "...", "voice": {...}, "speed": 1, "path": "out.wav"}   write a .wav instead
  {"op": "quit"}

  events: {"ev": "ready", "voices": [...]}, {"ev": "start", "id", "dur"}, {"ev": "end", "id"},
          {"ev": "idle"}, {"ev": "file", "path"}, {"ev": "error", "msg"}

Sentences are made one ahead of the one playing, so there are no gaps, and
"stop" takes effect within a tenth of a second.
"""

import json
import os
import queue
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
KDIR = os.environ.get("ARCHIE_KOKORO_DIR") or os.path.join(HERE, "Voice", "kokoro")
OUT_LOCK = threading.Lock()


def emit(**ev):
    with OUT_LOCK:
        sys.stdout.write(json.dumps(ev) + "\n")
        sys.stdout.flush()


def room(audio, sr):
    """A light 'speaker in the room' finish: trim the rumble, a hint of early reflection."""
    import numpy as np
    a = audio.astype("float32")
    # one-pole high-pass at ~80 Hz
    rc = 1.0 / (2 * 3.14159 * 80.0)
    alpha = rc / (rc + 1.0 / sr)
    y = np.empty_like(a)
    prev_x = prev_y = 0.0
    for i in range(len(a)):          # numpy has no recursive filter; this is fast enough for a sentence
        prev_y = alpha * (prev_y + a[i] - prev_x)
        prev_x = a[i]
        y[i] = prev_y
    d = int(sr * 0.022)
    out = y.copy()
    out[d:] += 0.12 * y[:-d]
    peak = float(np.max(np.abs(out)) or 1.0)
    return (out / max(1.0, peak / 0.95)).astype("float32")


def main():
    try:
        import numpy as np
        import sounddevice as sd
        from kokoro_onnx import Kokoro
        try:   # leave a couple of cores free, so Archie's windows and the speech model never stall while it talks
            import onnxruntime as ort
            so = ort.SessionOptions()
            so.intra_op_num_threads = max(2, min(8, (os.cpu_count() or 4) // 2))   # plenty for faster-than-real-time speech
            so.inter_op_num_threads = 1
            try:
                so.add_session_config_entry("session.intra_op.allow_spinning", "0")   # idle threads sleep, not spin
            except Exception:
                pass
            k = Kokoro.from_session(ort.InferenceSession(os.path.join(KDIR, "kokoro-v1.0.onnx"), so,
                                                         providers=["CPUExecutionProvider"]), os.path.join(KDIR, "voices-v1.0.bin"))
        except Exception:
            k = Kokoro(os.path.join(KDIR, "kokoro-v1.0.onnx"), os.path.join(KDIR, "voices-v1.0.bin"))
    except Exception as e:
        emit(ev="error", msg=f"The voice couldn't start: {e}", fatal=True)
        return
    try:
        from scipy.signal import lfilter  # noqa: F401  (optional, faster room finish)
    except Exception:
        pass
    styles = {}
    gen = [0]
    work = queue.Queue()          # say / file commands, in order
    play = queue.Queue()          # (gen, id, audio, sr)
    null_out = os.environ.get("ARCHIE_VOICE_NULL")  # tests: no sound card, write timings only

    def style(spec):
        mix = (spec or {}).get("mix") or [["bm_george", 0.6], ["bm_fable", 0.4]]
        key = json.dumps(mix)
        if key not in styles:
            total = sum(w for _, w in mix) or 1.0
            styles[key] = sum(k.get_voice_style(n) * (w / total) for n, w in mix)
        return styles[key]

    edge = {"down": 0.0, "told": False, "fails": 0}

    def online(host="speech.platform.bing.com"):
        """Is Microsoft's speech service reachable at all? (A quick connect, not a request.)"""
        import socket
        try:
            socket.create_connection((host, 443), timeout=2).close()
            return True
        except OSError:
            return False

    def edge_audio(text, name, speed):
        """Sonia and the other online voices: Microsoft's read-aloud service (needs internet). Mono float32, 24 kHz."""
        import asyncio
        import edge_tts
        import miniaudio
        import numpy as np
        rate = f"{int(round((speed - 1.0) * 100)):+d}%"

        async def go():
            buf = bytearray()
            async for ch in edge_tts.Communicate(text, name, rate=rate).stream():
                if ch.get("type") == "audio":
                    buf += ch["data"]
            return bytes(buf)
        mp3 = asyncio.run(asyncio.wait_for(go(), min(30, 10 + len(text) / 40)))   # long sentences get longer
        if not mp3:
            raise RuntimeError("no audio came back")
        d = miniaudio.decode(mp3, output_format=miniaudio.SampleFormat.FLOAT32, nchannels=1, sample_rate=24000)
        return np.asarray(d.samples, dtype="float32"), 24000

    clone = {"proc": None, "down": 0.0, "told": False, "n": 0}

    def clone_audio(text, ref):
        """An accent voice (Chatterbox, its own Python in Voice\\clone\\env, loaded once and kept running)."""
        import base64
        import subprocess
        import numpy as np
        p = clone["proc"]
        if p is None or p.poll() is not None:
            py = os.path.join(HERE, "Voice", "clone", "env", "Scripts" if os.name == "nt" else "bin", "python.exe" if os.name == "nt" else "python")
            if not os.path.exists(py):
                raise ImportError("clone")
            env = dict(os.environ, PYTHONIOENCODING="utf-8")
            for k2 in ("PYTHONPATH", "PYTHONHOME"):
                env.pop(k2, None)
            p = clone["proc"] = subprocess.Popen([py, "-s", os.path.join(HERE, "archie_accents.py"), "serve"], stdin=subprocess.PIPE,
                                                 stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, encoding="utf-8", bufsize=1,
                                                 cwd=HERE, env=env, creationflags=(0x08000000 | 0x00004000) if os.name == "nt" else 0)
            first = {}
            for _ in range(200):                       # skip anything else it prints while it loads
                line = p.stdout.readline()
                if not line:
                    break
                try:
                    first = json.loads(line)
                except ValueError:
                    continue
                if isinstance(first, dict) and first.get("ev") == "ready":
                    break
            if first.get("ev") != "ready":
                clone["proc"] = None
                raise RuntimeError("the accent voice didn't start")
        clone["n"] += 1
        p.stdin.write(json.dumps({"id": clone["n"], "text": text, "ref": ref}) + "\n")
        p.stdin.flush()
        r = {}
        for _ in range(200):
            line = p.stdout.readline()
            if not line:
                break
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if isinstance(r, dict) and r.get("id") == clone["n"]:
                break
        if r.get("error") or not r.get("pcm"):
            raise RuntimeError(r.get("error") or "no audio")
        clone["last"] = time.time()
        return np.frombuffer(base64.b64decode(r["pcm"]), dtype="float32").copy(), int(r["sr"])

    def clone_reaper():          # the accent voice lets go of the graphics card when it hasn't spoken for a bit
        while True:
            time.sleep(5)
            p = clone["proc"]
            if p is not None and p.poll() is None and time.time() - clone.get("last", 0) > 45:
                try:
                    p.stdin.write('{"op": "quit"}\n')
                    p.stdin.flush()
                    p.wait(5)
                except Exception:
                    try:
                        p.kill()
                    except Exception:
                        pass
                clone["proc"] = None
    threading.Thread(target=clone_reaper, daemon=True).start()

    def synth(c):
        spec = c.get("voice") or {}
        if spec.get("clone"):
            clone["last"] = time.time()
        if spec.get("clone") and time.time() > clone["down"]:
            try:
                audio, sr = clone_audio(c["text"], spec["clone"])
                clone["told"] = False
                return finish(c, audio, sr)
            except Exception as e:
                clone["down"] = time.time() + (3600 if isinstance(e, ImportError) else 120)
                if not clone["told"]:
                    clone["told"] = True
                    emit(ev="error", msg="The accent voice isn't working right now; using Archie's usual voice. (" + str(e)[:80] + ")")
        if spec.get("edge") and time.time() > edge["down"]:
            try:
                try:
                    audio, sr = edge_audio(c["text"], spec["edge"], float(c.get("speed") or 1.0))
                except ImportError:
                    raise
                except Exception:
                    # one hiccup from Microsoft's service is common: ask once more before giving up on this sentence
                    time.sleep(0.3)
                    audio, sr = edge_audio(c["text"], spec["edge"], float(c.get("speed") or 1.0))
                edge["told"], edge["fails"] = False, 0
                return finish(c, audio, sr)
            except ImportError:
                edge["down"] = time.time() + 3600
                if not edge["told"]:
                    edge["told"] = True
                    emit(ev="error", msg="Sonia isn't set up yet: run Tools\\Get Sonia Voice.bat once. Using the offline British woman for now.")
            except Exception:
                # Only this sentence uses the offline voice. Switch for a while only when the internet is really gone,
                # or Sonia has failed three sentences in a row.
                edge["fails"] += 1
                if not online():
                    edge["down"] = time.time() + 60
                elif edge["fails"] >= 3:
                    edge["down"] = time.time() + 20
                if edge["down"] > time.time() and not edge["told"]:
                    edge["told"] = True
                    emit(ev="error", msg="Sonia can't be reached right now. Using the offline voice until she's back.")
        audio, sr = k.create(c["text"], voice=style(spec), speed=float(c.get("speed") or 1.0),
                             lang=spec.get("lang") or "en-gb")
        return finish(c, audio, sr)

    def finish(c, audio, sr):
        vol = max(0.05, min(1.0, float(c.get("vol") or 1.0)))
        if vol < 0.999:
            audio = (audio * vol).astype("float32")
        if c.get("room"):
            try:
                from scipy.signal import lfilter
                import numpy as np
                rc = 1.0 / (2 * 3.14159 * 80.0)
                alpha = rc / (rc + 1.0 / sr)
                y = lfilter([alpha, -alpha], [1, -alpha], audio).astype("float32")
                d = int(sr * 0.022)
                out = y.copy()
                out[d:] += 0.12 * y[:-d]
                peak = float(np.max(np.abs(out)) or 1.0)
                audio = (out / max(1.0, peak / 0.95)).astype("float32")
            except Exception:
                audio = room(audio, sr)
        return audio, sr

    def synth_loop():
        while True:
            c = work.get()
            if c is None:
                play.put(None)
                return
            if c.get("op") == "file":
                try:
                    import wave
                    import numpy as np
                    audio, sr = synth(c)
                    pcm = (np.clip(audio, -1, 1) * 32767).astype("<i2").tobytes()
                    with wave.open(c["path"], "wb") as w:
                        w.setnchannels(1)
                        w.setsampwidth(2)
                        w.setframerate(sr)
                        w.writeframes(pcm)
                    emit(ev="file", path=c["path"], id=c.get("id"))
                except Exception as e:
                    emit(ev="error", msg=f"Couldn't make that audio: {e}", id=c.get("id"))
                continue
            if c.get("gen", 0) < gen[0]:
                continue
            busy[0] = True
            try:
                audio, sr = synth(c)
            except Exception as e:
                emit(ev="error", msg=f"Couldn't say that: {e}", id=c.get("id"))
                continue
            finally:
                busy[0] = False
            if c.get("gen", 0) < gen[0]:
                continue
            buf = bool((c.get("voice") or {}).get("clone")) and not c.get("talk")
            play.put((c.get("gen", 0), c.get("id"), audio, sr, buf))

    def play_loop():
        stream, cur_sr = None, None
        while True:
            try:
                item = play.get(timeout=0.5)
            except queue.Empty:
                if stream is not None and work.empty():
                    try:
                        stream.stop()
                        stream.close()
                    except Exception:
                        pass
                    stream = None
                    emit(ev="idle")
                continue
            if item is None:
                return
            g, sid, audio, sr, buf = item
            if g < gen[0]:
                continue
            if buf and g != last[0]:       # an accent voice reading aloud: let one more sentence get ready first,
                t_wait = time.time() + 10  # so it reads on without a pause after every sentence
                while time.time() < t_wait and play.qsize() < 1 and (busy[0] or not work.empty()) and g >= gen[0]:
                    time.sleep(0.05)
            last[0] = g
            emit(ev="start", id=sid, dur=round(len(audio) / sr, 3))
            if null_out:
                t_end = time.time() + len(audio) / sr / 8.0      # tests run 8x fast
                while time.time() < t_end and g >= gen[0]:
                    time.sleep(0.01)
                emit(ev="end", id=sid, cut=g < gen[0])
                continue
            try:
                if stream is None or cur_sr != sr:
                    if stream is not None:
                        stream.close()
                    stream = sd.OutputStream(samplerate=sr, channels=1, dtype="float32")
                    stream.start()
                    cur_sr = sr
                step = sr // 10
                for i in range(0, len(audio), step):
                    if g < gen[0]:
                        break
                    stream.write(audio[i:i + step].reshape(-1, 1))
            except Exception as e:
                emit(ev="error", msg=f"Sound stopped: {e}")
                stream = None
            emit(ev="end", id=sid, cut=g < gen[0])

    busy, last = [False], [-1]
    threading.Thread(target=synth_loop, daemon=True).start()
    threading.Thread(target=play_loop, daemon=True).start()
    try:
        names = sorted(k.get_voices())
    except Exception:
        names = []
    emit(ev="ready", voices=names)
    for line in sys.stdin:
        try:
            c = json.loads(line)
        except ValueError:
            continue
        op = c.get("op")
        if op == "quit":
            break
        if op == "stop":
            gen[0] = max(gen[0], int(c.get("gen") or gen[0] + 1))   # older sentences are skipped as they come up
            continue
        if op in ("say", "file"):
            work.put(c)
    work.put(None)


def test_sonia():
    """Tools\\Get Sonia Voice.bat: say one line with Sonia, exit 1 if she can't."""
    try:
        import asyncio
        import edge_tts
        import miniaudio
        import numpy as np
        import sounddevice as sd

        async def go():
            buf = bytearray()
            async for ch in edge_tts.Communicate("Hello. This is Sonia. I'll be Archie's voice whenever we're online.",
                                                 "en-GB-SoniaNeural", rate="-5%").stream():
                if ch.get("type") == "audio":
                    buf += ch["data"]
            return bytes(buf)
        mp3 = asyncio.run(asyncio.wait_for(go(), 20))
        d = miniaudio.decode(mp3, output_format=miniaudio.SampleFormat.FLOAT32, nchannels=1, sample_rate=24000)
        sd.play(np.asarray(d.samples, dtype="float32"), 24000)
        sd.wait()
        print("Sonia works.")
        return 0
    except Exception as e:
        print("Sonia didn't work:", repr(e))
        return 1


if __name__ == "__main__":
    if "--test-sonia" in sys.argv:
        sys.exit(test_sonia())
    main()
