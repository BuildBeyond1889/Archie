from lib.forms import validate
F = [{"name": "crop", "type": "choice", "choices": ["maize"], "required": True},
     {"name": "kg", "type": "number", "min": 0, "required": True}, {"name": "date", "type": "date"},
     {"name": "tel", "type": "phone"}, {"name": "note", "maxlen": 5}]
v, e = validate(F, {"crop": "maize", "kg": "4", "date": "31/3/2026", "tel": "+254 712 345678", "note": "ok"})
assert not e and v["kg"] == 4 and v["date"] == "2026-03-31" and v["tel"] == "+254712345678", (v, e)
v, e = validate(F, {"crop": "rice", "kg": "-1", "date": "soon", "tel": "12", "note": "toolong"})
assert set(e) == {"crop", "kg", "date", "tel", "note"}, e
v, e = validate(F, {"kg": "2,5"}); assert v["kg"] == 2.5 and "crop" in e
print("forms ok")
