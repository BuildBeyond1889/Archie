// Farm log: harvests, plantings and costs. Built from Archie's blocks: Store, makeForm, makeTable, barChart,
// downloadCSV, printReport, T (languages) and addAccessButtons.
(function () {
  T.add({
    en: { title: "Farm log", harvest: "Harvest", planting: "Planting", expense: "Expense", crop: "Crop", kg: "Kg", plot: "Plot / field",
      cost: "Cost (KSh)", what: "What for", note: "Note", entries: "Entries", byCrop: "Kg by crop", report: "Report", backup: "Backup", restore: "Restore",
      kind: "Type", sure: "Delete this entry?", restored: "Backup restored." },
    sw: { title: "Daftari la shamba", harvest: "Mavuno", planting: "Kupanda", expense: "Gharama", crop: "Zao", kg: "Kilo", plot: "Shamba / kipande",
      cost: "Gharama (KSh)", what: "Kwa ajili ya", note: "Maelezo", entries: "Kumbukumbu", byCrop: "Kilo kwa zao", report: "Ripoti", backup: "Hifadhi nakala", restore: "Rejesha",
      kind: "Aina", sure: "Futa kumbukumbu hii?", restored: "Nakala imerejeshwa." },
  });
  const CROPS = ["maize", "beans", "sukuma wiki", "tomatoes", "potatoes", "kale", "cabbage", "onions", "bananas", "avocado", "coffee", "tea", "other"];
  const FORMS = {
    harvest: [{ name: "date", label: "date", type: "date", required: true }, { name: "crop", label: "crop", type: "choice", choices: CROPS, required: true },
      { name: "kg", label: "kg", type: "number", min: 0, required: true }, { name: "plot", label: "plot" }, { name: "note", label: "note", maxlen: 200 }],
    planting: [{ name: "date", label: "date", type: "date", required: true }, { name: "crop", label: "crop", type: "choice", choices: CROPS, required: true },
      { name: "plot", label: "plot" }, { name: "note", label: "note", maxlen: 200 }],
    expense: [{ name: "date", label: "date", type: "date", required: true }, { name: "what", label: "what", required: true },
      { name: "cost", label: "cost", type: "number", min: 0, required: true }, { name: "note", label: "note", maxlen: 200 }],
  };
  const db = new Store("farm-log");
  let kind = "harvest";
  const app = document.getElementById("app");
  document.title = T("title");
  document.getElementById("title").textContent = T("title");
  addAccessButtons(document.querySelector(".bar"));

  app.innerHTML =
    "<div class='row'>" + ["harvest", "planting", "expense"].map((k) => "<button class='secondary' data-k='" + k + "' data-t='" + k + "'></button>").join("") +
    "<select id='lang'><option value='en'>English</option><option value='sw'>Kiswahili</option></select></div>" +
    "<div class='card' id='form'></div>" +
    "<h2 data-t='entries'></h2><div id='list'></div>" +
    "<h2 data-t='byCrop'></h2><canvas id='chart' style='width:100%;height:220px'></canvas>" +
    "<div class='row' style='margin-top:12px'><button id='rep' data-t='report'></button><button id='csv' class='secondary' data-t='export'></button>" +
    "<button id='bk' class='secondary' data-t='backup'></button><label style='cursor:pointer;padding:.5rem .7rem;border-radius:8px;background:#e9eef2;min-height:44px;display:inline-flex;align-items:center'><span data-t='restore'></span>" +
    "<input type='file' id='rs' accept='.json' style='display:none'></label></div>";

  const lang = document.getElementById("lang");
  lang.value = T.lang();
  lang.onchange = () => { T.setLang(lang.value); render(); };

  function labelled(fields) { return fields.map((f) => Object.assign({}, f, { label: T(f.label) })); }
  function cols() {
    const c = [{ key: "date", label: T("date") }];
    if (kind === "expense") c.push({ key: "what", label: T("what") }, { key: "cost", label: T("cost"), num: true });
    else c.push({ key: "crop", label: T("crop") }, { key: "plot", label: T("plot") });
    if (kind === "harvest") c.push({ key: "kg", label: T("kg"), num: true });
    return c;
  }
  function render() {
    T.apply();
    document.title = document.getElementById("title").textContent = T("title");
    document.querySelectorAll("[data-k]").forEach((b) => b.className = b.dataset.k === kind ? "" : "secondary");
    makeForm(document.getElementById("form"), labelled(FORMS[kind]), (v) => { db.add(kind, v); render(); }, T("save"));
    const rows = db.list(kind).sort((a, b) => (a.date < b.date ? 1 : -1));
    makeTable(document.getElementById("list"), cols(), {
      totals: kind === "harvest" ? ["kg"] : kind === "expense" ? ["cost"] : null, searchLabel: T("search"),
      onRow: (r) => { if (confirm(T("sure") + "\n" + r.date + " " + (r.crop || r.what))) { db.remove(kind, r.id); render(); } },
    }).show(rows);
    const s = sumBy(db.list("harvest"), "crop", "kg");
    barChart(document.getElementById("chart"), s.labels, s.values, { title: T("byCrop") });
  }
  document.querySelectorAll("[data-k]").forEach((b) => b.onclick = () => { kind = b.dataset.k; render(); });
  document.getElementById("csv").onclick = () => downloadCSV(kind + ".csv", db.list(kind));
  document.getElementById("bk").onclick = () => db.exportFile();
  document.getElementById("rs").onchange = (e) => e.target.files[0] && db.importFile(e.target.files[0]).then(() => { alert(T("restored")); render(); }).catch((err) => alert(err.message));
  document.getElementById("rep").onclick = () => {
    const month = new Date().toISOString().slice(0, 7);
    const h = db.list("harvest").filter((r) => (r.date || "").startsWith(month));
    const x = db.list("expense").filter((r) => (r.date || "").startsWith(month));
    printReport(T("title") + " " + month, [
      { heading: T("harvest") }, { table: h, cols: [{ key: "date", label: T("date") }, { key: "crop", label: T("crop") }, { key: "kg", label: T("kg") }], totals: ["kg"] },
      { heading: T("expense") }, { table: x, cols: [{ key: "date", label: T("date") }, { key: "what", label: T("what") }, { key: "cost", label: T("cost") }], totals: ["cost"] },
    ]);
  };

  const net = document.getElementById("net");
  function showNet() { net.textContent = T(navigator.onLine ? "online" : "offline"); }
  addEventListener("online", showNet); addEventListener("offline", showNet); showNet();
  if ("serviceWorker" in navigator && location.protocol !== "file:") navigator.serviceWorker.register("sw.js").catch(() => {});
  render();
})();
