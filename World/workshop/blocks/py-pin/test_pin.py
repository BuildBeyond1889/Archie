import os, tempfile
import lib.pin as P
P.ROUNDS = 1000
lock = P.PinLock(os.path.join(tempfile.mkdtemp(), "pin.json"), max_tries=3, wait_s=60)
assert not lock.is_set(); lock.set("4821"); assert lock.is_set()
assert "4821" not in open(lock.path).read()
assert lock.check("4821")[0] and not lock.check("0000")[0]
lock.check("1"); lock.check("2")
ok, msg = lock.check("4821"); assert not ok and "Wait" in msg
try: lock.set("12"); raise SystemExit("short pin accepted")
except ValueError: pass
print("pin ok")
