"""
archie_webpush.py - notifications to the phone (Web Push, RFC 8291 + RFC 8292), with no extra packages
beyond "cryptography" (already used by Archie Lite's sync).

  * Each phone subscribes once; its browser gives an endpoint (Google's push service for Chrome on
    Android) and two keys. Every message is encrypted for that phone only (aes128gcm) and signed with
    this PC's VAPID key, so the push service can't read it and nobody else can send to it.
"""

import base64
import json
import os
import struct
import time
import urllib.error
import urllib.parse
import urllib.request

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.hmac import HMAC


def b64u(b):
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode("ascii")


def unb64u(s):
    s = s.replace(" ", "")
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _hmac(key, data):
    h = HMAC(key, hashes.SHA256())
    h.update(data)
    return h.finalize()


def _hkdf(salt, ikm, info, length):
    prk = _hmac(salt, ikm)                       # extract
    return _hmac(prk, info + b"\x01")[:length]   # expand (one block is enough: length <= 32)


def _pub_bytes(key):
    return key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)


def private_from_b64(d_b64):
    return ec.derive_private_key(int.from_bytes(unb64u(d_b64), "big"), ec.SECP256R1())


def encrypt(payload, ua_public_b64, auth_b64, as_private=None, salt=None, rs=4096):
    """The aes128gcm body for one push message (RFC 8291 section 3 + RFC 8188)."""
    ua_public = unb64u(ua_public_b64)
    auth = unb64u(auth_b64)
    as_private = as_private or ec.generate_private_key(ec.SECP256R1())
    as_public = _pub_bytes(as_private)
    salt = salt or os.urandom(16)
    ua_key = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), ua_public)
    ecdh = as_private.exchange(ec.ECDH(), ua_key)
    ikm = _hkdf(auth, ecdh, b"WebPush: info\x00" + ua_public + as_public, 32)
    cek = _hkdf(salt, ikm, b"Content-Encoding: aes128gcm\x00", 16)
    nonce = _hkdf(salt, ikm, b"Content-Encoding: nonce\x00", 12)
    ct = AESGCM(cek).encrypt(nonce, payload + b"\x02", None)     # one record, last-record delimiter
    header = salt + struct.pack(">I", rs) + bytes([len(as_public)]) + as_public
    return header + ct


class Vapid:
    """This PC's signing key for push (made once, kept in the phone state file)."""

    def __init__(self, d_b64=None, subject="mailto:archie@localhost"):
        self.key = private_from_b64(d_b64) if d_b64 else ec.generate_private_key(ec.SECP256R1())
        self.subject = subject

    @property
    def private_b64(self):
        return b64u(self.key.private_numbers().private_value.to_bytes(32, "big"))

    @property
    def public_b64(self):
        return b64u(_pub_bytes(self.key))

    def header(self, endpoint):
        u = urllib.parse.urlparse(endpoint)
        claims = {"aud": f"{u.scheme}://{u.netloc}", "exp": int(time.time()) + 12 * 3600, "sub": self.subject}
        head = b64u(json.dumps({"typ": "JWT", "alg": "ES256"}, separators=(",", ":")).encode())
        body = b64u(json.dumps(claims, separators=(",", ":")).encode())
        r, s = decode_dss_signature(self.key.sign(f"{head}.{body}".encode(), ec.ECDSA(hashes.SHA256())))
        sig = b64u(r.to_bytes(32, "big") + s.to_bytes(32, "big"))
        return f"vapid t={head}.{body}.{sig}, k={self.public_b64}"


def send(sub, payload, vapid, ttl=3600, urgency="high", timeout=20):
    """POST one encrypted message. Returns the HTTP status (201 = accepted; 404/410 = subscription gone)."""
    body = encrypt(json.dumps(payload).encode("utf-8"), sub["keys"]["p256dh"], sub["keys"]["auth"])
    req = urllib.request.Request(sub["endpoint"], data=body, method="POST", headers={
        "Content-Encoding": "aes128gcm", "Content-Type": "application/octet-stream", "TTL": str(ttl),
        "Urgency": urgency, "Authorization": vapid.header(sub["endpoint"])})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
