// Clinic medicine stock: items with quantity, minimum, expiry; warnings for low stock and expiry.
(function () {
  T.add({
    en: { title: "Medicine stock", item: "Medicine or supply", qty: "Quantity", unit: "Unit", min: "Reorder below", expiry: "Expiry date", batch: "Batch",
      warnings: "Needs attention", low: "Low stock", expiring: "Expires soon", expired: "EXPIRED", stock: "Stock", use: "Use / give out", receive: "Receive",
      howMany: "How many?", sheet: "Stock sheet", none: "Nothing needs attention.", backup: "Backup", sure: "Delete this item?" },
    sw: { title: "Akiba ya dawa", item: "Dawa au kifaa", qty: "Idadi", unit: "Kipimo", min: "Agiza chini ya", expiry: "Tarehe ya kuisha", batch: "Kundi",
      warnings: "Yanahitaji uangalifu", low: "Akiba ndogo", expiring: "Inaisha karibuni", expired: "IMEISHA MUDA", stock: "Akiba", use: "Tumia / toa", receive: "Pokea",
      howMany: "Ngapi?", sheet: "Karatasi ya akiba", none: "Hakuna kinachohitaji uangalifu.", backup: "Hifadhi nakala", sure: "Futa kitu hiki?" },
  });
  const UNITS = ["tablets", "capsules", "bottles", "vials", "sachets", "tubes", "boxes", "pieces", "ml"];
  const FIELDS = [{ name: "item", label: "item", required: true }, { name: "qty", label: "qty", type: "number", min: 0, required: true },
    { name: "unit", label: "unit", type: "choice", choices: UNITS, required: true }, { name: "min", label: "min", type: "number", min: 0 },
    { name: "expiry", label: "expiry", type: "date" }, { name: "batch", label: "batch" }];
  const db = new Store("clinic-stock");
  const app = document.getElementById("app");
  addAccessButtons(document.querySelector(".bar"));
  app.innerHTML = "<select id='lang'><option value='en'>English</option><option value='sw'>Kiswahili</option></select>" +
    "<h2 data-t='warnings'></h2><div id='warn'></div><div class='card' id='form'></div><h2 data-t='stock'></h2><div id='list'></div>" +
    "<div class='row' style='margin-top:12px'><button id='sheet' data-t='sheet'></button><button id='csv' class='secondary' data-t='export'></button><button id='bk' class='secondary' data-t='backup'></button></div>";
  const lang = document.getElementById("lang"); lang.value = T.lang(); lang.onchange = () => { T.setLang(lang.value); render(); };
  const today = () => new Date().toISOString().slice(0, 10);
  function daysLeft(d) { return d ? Math.round((Date.parse(d) - Date.parse(today())) / 86400000) : null; }
  function status(r) {
    const d = daysLeft(r.expiry);
    if (d != null && d < 0) return T("expired");
    if (d != null && d <= 60) return T("expiring") + " (" + d + ")";
    if (r.min != null && r.qty <= r.min) return T("low");
    return "";
  }
  function render() {
    T.apply();
    document.title = document.getElementById("title").textContent = T("title");
    makeForm(document.getElementById("form"), FIELDS.map((f) => Object.assign({}, f, { label: T(f.label) })), (v) => { db.add("items", v); render(); }, T("add"));
    const rows = db.list("items").map((r) => Object.assign({}, r, { status: status(r) }));
    const bad = rows.filter((r) => r.status);
    document.getElementById("warn").innerHTML = bad.length ? bad.map((r) => "<div class='card' style='border-color:#b00020'><b>" +
      r.item.replace(/</g, "&lt;") + "</b>: " + r.status + " · " + r.qty + " " + r.unit + "</div>").join("") : "<p>" + T("none") + "</p>";
    makeTable(document.getElementById("list"), [{ key: "item", label: T("item") }, { key: "qty", label: T("qty"), num: true }, { key: "unit", label: T("unit") },
      { key: "expiry", label: T("expiry") }, { key: "status", label: "" }], { searchLabel: T("search"), onRow: change }).show(rows.sort((a, b) => a.item.localeCompare(b.item)));
  }
  function change(r) {
    const a = prompt(r.item + "\n" + T("use") + ": -5   " + T("receive") + ": +100\n" + T("howMany") + "  (" + T("delete") + ": 0)", "-1");
    if (a == null) return;
    if (a.trim() === "0") { if (confirm(T("sure"))) db.remove("items", r.id); return render(); }
    const n = Number(a.replace(",", "."));
    if (isFinite(n)) { db.update("items", r.id, { qty: Math.max(0, (r.qty || 0) + n) }); db.add("moves", { item: r.id, change: n, date: today() }); }
    render();
  }
  document.getElementById("csv").onclick = () => downloadCSV("stock-" + today() + ".csv", db.list("items"));
  document.getElementById("bk").onclick = () => db.exportFile();
  document.getElementById("sheet").onclick = () => printReport(T("sheet") + " " + today(), [{ table: db.list("items").map((r) => Object.assign({}, r, { status: status(r) })),
    cols: [{ key: "item", label: T("item") }, { key: "qty", label: T("qty") }, { key: "unit", label: T("unit") }, { key: "expiry", label: T("expiry") }, { key: "batch", label: T("batch") }, { key: "status", label: "" }] }]);
  if ("serviceWorker" in navigator && location.protocol !== "file:") navigator.serviceWorker.register("sw.js").catch(() => {});
  render();
})();
