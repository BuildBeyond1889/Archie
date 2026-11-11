"""
archie_lite_proto.py - the sealed envelope Archie (PC) and Archie Lite (laptop) talk in.

Every message is JSON, encrypted and signed with AES-256-GCM under the pairing key that only
the PC and the paired laptop hold. A message carries its send time and a random id, so an old
message replayed later, or the same one sent twice, is turned away. The same file lives in
D:\\Archie (as archie_lite_proto.py) and in ArchieLite\\app (as lite_proto.py): keep them identical.
"""

import base64
import hashlib
import hmac
import json
import os
import threading
import time

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

AAD = b"archie-lite-v1"
PORT = 47321            # the PC's sync server (TCP)
DISCOVER_PORT = 47322   # the PC answers "where are you?" here (UDP)
MAX_AGE = 300           # seconds a message stays valid (clocks may differ a little)


class ProtoError(Exception):
    pass


def new_key():
    return base64.b64encode(os.urandom(32)).decode()


def _key(key_b64):
    k = base64.b64decode(key_b64)
    if len(k) != 32:
        raise ProtoError("bad pairing key")
    return k


def seal(key_b64, obj):
    body = dict(obj, _t=time.time(), _id=base64.b64encode(os.urandom(12)).decode())
    nonce = os.urandom(12)
    ct = AESGCM(_key(key_b64)).encrypt(nonce, json.dumps(body, ensure_ascii=False).encode("utf-8"), AAD)
    return json.dumps({"v": 1, "n": base64.b64encode(nonce).decode(), "c": base64.b64encode(ct).decode()}).encode()


class Opener:
    """Opens envelopes, refusing tampered, stale or repeated ones."""

    def __init__(self, key_b64, max_age=MAX_AGE):
        self.key = _key(key_b64)
        self.max_age = max_age
        self.seen = {}
        self.lock = threading.Lock()

    def open(self, raw):
        try:
            env = json.loads(raw)
            nonce, ct = base64.b64decode(env["n"]), base64.b64decode(env["c"])
            body = json.loads(AESGCM(self.key).decrypt(nonce, ct, AAD).decode("utf-8"))
        except Exception:
            raise ProtoError("not from the paired device")
        t, mid = body.pop("_t", 0), body.pop("_id", "")
        now = time.time()
        if abs(now - t) > self.max_age:
            raise ProtoError("message too old (are both clocks right?)")
        with self.lock:
            for k in [k for k, v in self.seen.items() if now - v > 2 * self.max_age]:
                del self.seen[k]
            if mid in self.seen:
                raise ProtoError("message repeated")
            self.seen[mid] = now
        return body


def proof(key_b64, challenge):
    """For discovery: the PC proves it holds the key without sending anything secret."""
    return hmac.new(_key(key_b64), b"archie-lite-hello:" + challenge.encode(), hashlib.sha256).hexdigest()
