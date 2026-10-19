from lib.report import Report
r = Report("Harvest <test>").text("Total: 3").table([{"crop": "maize", "kg": 2}, {"crop": "beans", "kg": 1}], totals=["kg"])
h = r.html()
assert "&lt;test&gt;" in h and "<th>3</th>" in h and 'class="n">2<' in h
p = r.save(); assert open(p, encoding="utf-8").read().startswith("<!DOCTYPE html>")
print("report ok")
