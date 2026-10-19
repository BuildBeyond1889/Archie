import tempfile, os
from lib.csvio import write_csv, read_csv
p = os.path.join(tempfile.mkdtemp(), "t.csv")
write_csv(p, [{"crop": "mahindi", "kg": 40}, {"crop": "maharagwe", "kg": 12.5, "note": "x"}])
r = read_csv(p)
assert r[0]["kg"] == 40 and r[1]["kg"] == 12.5 and r[1]["note"] == "x", r
open(p, "w", encoding="utf-8").write("a;b\n1;2\n"); assert read_csv(p)[0]["b"] == 2
print("csv ok")
