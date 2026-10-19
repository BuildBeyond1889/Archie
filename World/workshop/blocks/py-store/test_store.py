import os, tempfile
from lib.store import Store
d = tempfile.mkdtemp()
s = Store("t", folder=d)
s.set("name", "Shamba")
a = s.add("h", {"crop": "maize"}); b = s.add("h", {"crop": "beans"})
assert (a["id"], b["id"]) == (1, 2)
s.update("h", 2, kg=5); assert Store("t", folder=d).get("h")[1]["kg"] == 5
assert s.remove("h", 1) and len(s.get("h")) == 1
open(s.path, "w").write("{broken")                 # damaged file -> newest good copy
assert Store("t", folder=d).get("name") == "Shamba"
assert len(os.listdir(os.path.join(d, ".old"))) <= 5
print("store ok")
