import os, sys, tempfile
from lib.applog import setup
d = tempfile.mkdtemp(); log = setup("t", folder=d); log.info("hello %s", 1)
try: 1 / 0
except ZeroDivisionError: sys.excepthook(*sys.exc_info())
for h in log.handlers: h.flush()
assert "hello 1" in open(os.path.join(d, "t.log"), encoding="utf-8").read()
assert any(f.startswith("crash-") for f in os.listdir(d))
print("log ok")
