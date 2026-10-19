"""Local AI in your app, through Ollama on the same computer (no internet, nothing leaves the PC).

    if available():
        print(ask("Explain photosynthesis to a 10-year-old in 3 sentences."))
    chat = Chat(system="You are a friendly maths tutor.")
    chat.say("What is a fraction?")
Needs Ollama running with a model pulled (ollama pull qwen2.5:3b runs on modest computers).
"""
import json
import urllib.error
import urllib.request

URL = "http://127.0.0.1:11434"


def _post(path, body, timeout=300):
    req = urllib.request.Request(URL + path, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def models():
    try:
        with urllib.request.urlopen(URL + "/api/tags", timeout=3) as r:
            return [m["name"] for m in json.loads(r.read()).get("models", [])]
    except (OSError, ValueError):
        return []


def available():
    return bool(models())


def pick_model(prefer=("qwen2.5:7b", "qwen2.5:3b", "llama3.2", "qwen2.5")):
    ms = models()
    for p in prefer:
        m = next((x for x in ms if x.startswith(p)), None)
        if m:
            return m
    return next((m for m in ms if "embed" not in m), None)


def ask(prompt, model=None, system=None, temperature=0.4):
    model = model or pick_model()
    if not model:
        return "(No local AI model found. Start Ollama and pull a model.)"
    msgs = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
    try:
        return _post("/api/chat", {"model": model, "messages": msgs, "stream": False, "options": {"temperature": temperature}})["message"]["content"]
    except (OSError, ValueError, KeyError) as e:
        return "(The local AI didn't answer: %s)" % e


class Chat:
    """A conversation that remembers what was said."""
    def __init__(self, system=None, model=None):
        self.model = model or pick_model()
        self.msgs = [{"role": "system", "content": system}] if system else []

    def say(self, text):
        self.msgs.append({"role": "user", "content": text})
        try:
            reply = _post("/api/chat", {"model": self.model, "messages": self.msgs, "stream": False})["message"]["content"]
        except (OSError, ValueError, KeyError, TypeError) as e:
            reply = "(The local AI didn't answer: %s)" % e
        self.msgs.append({"role": "assistant", "content": reply})
        return reply
