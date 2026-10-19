// Save data in the browser (localStorage): survives closing the app and works offline.
//   const db = new Store("farm");
//   db.add("harvests", { crop: "maize", kg: 40 });     // gets an id
//   db.list("harvests"); db.update("harvests", 1, { kg: 42 }); db.remove("harvests", 1);
//   db.exportFile();  db.importFile(file)               // backup to a file and back (USB, WhatsApp...)
(function (root) {
  function Store(name, storage) {
    this.key = "archie-store:" + name;
    this.name = name;
    this.storage = storage || root.localStorage;
    try { this.data = JSON.parse(this.storage.getItem(this.key) || "{}"); } catch (e) { this.data = {}; }
  }
  Store.prototype.save = function () {
    try { this.storage.setItem(this.key, JSON.stringify(this.data)); return true; }
    catch (e) { if (root.alert) root.alert("Couldn't save: the phone's storage for this app is full."); return false; }
  };
  Store.prototype.get = function (k, d) { return k in this.data ? this.data[k] : d; };
  Store.prototype.set = function (k, v) { this.data[k] = v; this.save(); };
  Store.prototype.list = function (k) { return (this.data[k] || []).slice(); };
  Store.prototype.add = function (k, item) {
    const items = this.data[k] || (this.data[k] = []);
    const id = items.reduce((m, i) => Math.max(m, i.id || 0), 0) + 1;
    const rec = Object.assign({}, item, { id: id, added: new Date().toISOString() });
    items.push(rec); this.save(); return rec;
  };
  Store.prototype.update = function (k, id, changes) {
    const it = (this.data[k] || []).find((i) => i.id === id);
    if (!it) return null;
    Object.assign(it, changes); this.save(); return it;
  };
  Store.prototype.remove = function (k, id) {
    const before = (this.data[k] || []).length;
    this.data[k] = (this.data[k] || []).filter((i) => i.id !== id); this.save();
    return this.data[k].length !== before;
  };
  Store.prototype.toJSON = function () { return JSON.stringify({ app: this.name, saved: new Date().toISOString(), data: this.data }, null, 1); };
  Store.prototype.fromJSON = function (text) {
    const o = JSON.parse(text);
    if (!o || typeof o.data !== "object") throw new Error("That isn't a backup from this app.");
    this.data = o.data; this.save(); return true;
  };
  Store.prototype.exportFile = function () {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([this.toJSON()], { type: "application/json" }));
    a.download = this.name + "-backup-" + new Date().toISOString().slice(0, 10) + ".json";
    document.body.appendChild(a); a.click(); a.remove();
  };
  Store.prototype.importFile = function (file) {
    const self = this;
    return file.text().then((t) => self.fromJSON(t));
  };
  if (typeof module !== "undefined") module.exports = Store; else root.Store = Store;
})(typeof window !== "undefined" ? window : globalThis);
