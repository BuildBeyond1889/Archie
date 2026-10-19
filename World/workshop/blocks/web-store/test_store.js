const Store = require("./js/store.js");
const mem = { d: {}, getItem(k) { return this.d[k] || null; }, setItem(k, v) { this.d[k] = String(v); } };
const s = new Store("t", mem);
const a = s.add("h", { crop: "maize" }), b = s.add("h", { crop: "beans" });
if (a.id !== 1 || b.id !== 2) throw "ids";
s.update("h", 2, { kg: 5 }); if (new Store("t", mem).list("h")[1].kg !== 5) throw "update";
if (!s.remove("h", 1) || s.list("h").length !== 1) throw "remove";
const j = s.toJSON(); const s2 = new Store("u", mem); s2.fromJSON(j); if (s2.list("h")[0].crop !== "beans") throw "backup";
try { s2.fromJSON("{}"); throw "bad import accepted"; } catch (e) { if (e === "bad import accepted") throw e; }
console.log("web store ok");
