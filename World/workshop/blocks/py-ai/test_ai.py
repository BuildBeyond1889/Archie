import lib.ai as A
A.URL = "http://127.0.0.1:9"          # nothing listens here: must fail gently, not crash
assert A.models() == [] and not A.available()
assert A.ask("hi").startswith("(No local AI")
assert A.Chat(model="x").say("hi").startswith("(The local AI")
print("ai ok")
