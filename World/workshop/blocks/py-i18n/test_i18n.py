from lib.i18n import Strings
T = Strings({"en": {"hello": "Hello, {name}", "only_en": "E"}, "sw": {"hello": "Habari, {name}"}})
assert T("save") == "Save"; T.lang = "sw"
assert T("save") == "Hifadhi" and T("hello", name="Juma") == "Habari, Juma" and T("only_en") == "E" and T("nope") == "nope"
assert "only_en" in T.missing("sw") and "sw" in T.languages()
print("i18n ok")
