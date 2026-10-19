from lib.search import search
R = [{"name": "Amina Odhiambo", "village": "Kisumu"}, {"name": "Aminata", "village": "Nakuru"}, {"name": "José", "village": "Kisii"}]
assert [r["name"] for r in search(R, "amina")][0] == "Amina Odhiambo"
assert [r["name"] for r in search(R, "jose")] == ["José"]
assert [r["name"] for r in search(R, "ami kis")] == ["Amina Odhiambo"]
assert len(search(R, "")) == 3
print("search ok")
