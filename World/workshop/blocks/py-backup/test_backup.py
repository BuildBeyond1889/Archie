import os, tempfile
from lib.backup import make_backup, restore, list_backups
d = tempfile.mkdtemp(); data = os.path.join(d, "data"); os.makedirs(data)
open(os.path.join(data, "a.json"), "w").write("1")
b = make_backup(data, os.path.join(d, "bk"))
open(os.path.join(data, "a.json"), "w").write("2")
restore(b, data); assert open(os.path.join(data, "a.json")).read() == "1"
assert list_backups(os.path.join(d, "bk"), "data") == [b]
assert list_backups(os.path.join(d, "before-restore"))
print("backup ok")
