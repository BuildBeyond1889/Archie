import tempfile, os
from lib.db import DB
db = DB(os.path.join(tempfile.mkdtemp(), "t.db"))
p = db.table("people", name="text", age="int")
a = p.add(name="Amina", age=12); p.add(name="Baraka", age=14)
assert p.count() == 2 and p.get(a)["name"] == "Amina"
assert [r["name"] for r in p.search("bar")] == ["Baraka"]
p.update(a, age=13); assert p.find(name="Amina")[0]["age"] == 13
assert p.all("-age")[0]["name"] == "Baraka"
p2 = db.table("people", name="text", age="int", village="text")   # new field on an old table
p2.add(name="C", village="Kisumu"); assert p2.find(village="Kisumu")
p.delete(a); assert p.count() == 2
try: p.add(nope=1); raise SystemExit("should fail")
except KeyError: pass
print("db ok")
