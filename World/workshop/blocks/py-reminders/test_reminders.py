import os, tempfile, datetime as dt
from lib.reminders import Reminders
r = Reminders(os.path.join(tempfile.mkdtemp(), "r.json"))
r.add("2026-01-31 08:00", "monthly", repeat="monthly"); r.add("2026-01-01 08:00", "once")
d = r.due(dt.datetime(2026, 1, 31, 9, 0)); assert sorted(i["text"] for i in d) == ["monthly", "once"]
assert [i["when"] for i in r.upcoming()] == ["2026-02-28 08:00"]
assert r.due(dt.datetime(2026, 2, 1)) == []
r.add("2026-01-01 07:00", "daily", repeat="daily"); r.due(dt.datetime(2026, 1, 5, 8, 0))
assert any(i["when"] == "2026-01-06 07:00" for i in Reminders(r.path).items)
print("reminders ok")
