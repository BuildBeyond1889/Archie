"""A PIN lock for apps that hold private information (children's records, money).

    lock = PinLock("data/pin.json")
    if not lock.is_set(): lock.set("4821")
    ok, msg = lock.check("4821")
The PIN itself is never saved, only a salted, slow hash of it (PBKDF2), so reading the file doesn't reveal it.
After 5 wrong tries the lock waits a while before accepting more.
Note: a PIN keeps casual eyes out. For real protection of private files, also keep the computer itself locked.
"""
import hashlib
import hmac
import json
import os
import secrets
import time

ROUNDS = 200_000


def _hash(pin, salt):
    return hashlib.pbkdf2_hmac("sha256", str(pin).encode(), bytes.fromhex(salt), ROUNDS).hex()


class PinLock:
    def __init__(self, path, max_tries=5, wait_s=300):
        self.path, self.max_tries, self.wait_s = path, max_tries, wait_s

    def _load(self):
        try:
            with open(self.path, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return {}

    def _save(self, d):
        os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(d, f)

    def is_set(self):
        return bool(self._load().get("hash"))

    def set(self, pin):
        pin = str(pin)
        if not pin.isdigit() or len(pin) < 4:
            raise ValueError("Use at least 4 digits.")
        salt = secrets.token_hex(16)
        self._save({"salt": salt, "hash": _hash(pin, salt), "fails": 0, "until": 0})

    def check(self, pin):
        d = self._load()
        if not d.get("hash"):
            return True, "No PIN set."
        if time.time() < d.get("until", 0):
            return False, "Too many wrong tries. Wait %d minutes." % max(1, int((d["until"] - time.time()) / 60 + 0.99))
        if hmac.compare_digest(_hash(pin, d["salt"]), d["hash"]):
            d.update(fails=0, until=0)
            self._save(d)
            return True, "Unlocked."
        d["fails"] = d.get("fails", 0) + 1
        if d["fails"] >= self.max_tries:
            d.update(fails=0, until=time.time() + self.wait_s)
        self._save(d)
        return False, "Wrong PIN."
