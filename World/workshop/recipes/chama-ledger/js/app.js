// Savings group ledger: members, money in (contributions), money out (payouts / loans), totals.
(function () {
  T.add({
    en: { title: "Chama ledger", member: "Member", members: "Members", amount: "Amount (KSh)", type: "Type", "in": "Contribution", out: "Payout", balance: "Group balance",
      paid: "Paid in", received: "Received", statement: "Statement", record: "Record", addMember: "Add member", backup: "Backup", ref: "M-Pesa / receipt no." },
    sw: { title: "Daftari la chama", member: "Mwanachama", members: "Wanachama", amount: "Kiasi (KSh)", type: "Aina", "in": "Mchango", out: "Malipo", balance: "Salio la kikundi",
      paid: "Alicholipa", received: "Alichopokea", statement: "Taarifa", record: "Rekodi", addMember: "Ongeza mwanachama", backup: "Hifadhi nakala", ref: "Namba ya M-Pesa / risiti" },
  });
  const db = new Store("chama");
  const app = document.getElementById("app");
  addAccessButtons(document.querySelector(".bar"));
  app.innerHTML = "<select id='lang'><option value='en'>English</option><option value='sw'>Kiswahili</option></select>" +
    "<div class='card'><b data-t='balance'></b>: <span id='bal' style='font-size:1.4rem'></span></div>" +
    "<div class='row'><input id='nm' style='flex:1'><button id='addm' data-t='addMember'></button></div>" +
    "<div class='card' id='form'></div><h2 data-t='members'></h2><div id='tot'></div>" +
    "<div class='row' style='margin-top:12px'><button id='st' data-t='statement'></button><button id='csv' class='secondary' data-t='export'></button><button id='bk' class='secondary' data-t='backup'></button></div>";
  const lang = document.getElementById("lang"); lang.value = T.lang(); lang.onchange = () => { T.setLang(lang.value); render(); };
  const fmt = (n) => (Math.round(n * 100) / 100).toLocaleString();
  function totals() {
    const tx = db.list("tx");
    return db.list("members").map((m) => {
      const mine = tx.filter((t) => t.member === m.name);
      const paid = mine.filter((t) => t.type === T("in") || t.type === "in").reduce((s, t) => s + t.amount, 0);
      const got = mine.filter((t) => t.type === T("out") || t.type === "out").reduce((s, t) => s + t.amount, 0);
      return { member: m.name, paid, received: got };
    });
  }
  function render() {
    T.apply();
    document.title = document.getElementById("title").textContent = T("title");
    document.getElementById("nm").placeholder = T("name");
    const names = db.list("members").map((m) => m.name).sort();
    makeForm(document.getElementById("form"), [
      { name: "date", label: T("date"), type: "date", required: true, default: new Date().toISOString().slice(0, 10) },
      { name: "member", label: T("member"), type: "choice", choices: names, required: true },
      { name: "type", label: T("type"), type: "choice", choices: [T("in"), T("out")], required: true },
      { name: "amount", label: T("amount"), type: "number", min: 0, required: true }, { name: "ref", label: T("ref") }],
      (v) => { v.type = v.type === T("in") ? "in" : "out"; db.add("tx", v); render(); }, T("record"));
    const t = totals();
    const bal = t.reduce((s, r) => s + r.paid - r.received, 0);
    document.getElementById("bal").textContent = "KSh " + fmt(bal);
    makeTable(document.getElementById("tot"), [{ key: "member", label: T("member") }, { key: "paid", label: T("paid"), num: true }, { key: "received", label: T("received"), num: true }],
      { totals: ["paid", "received"], searchLabel: T("search") }).show(t);
  }
  document.getElementById("addm").onclick = () => { const v = document.getElementById("nm").value.trim(); if (v && !db.list("members").some((m) => m.name === v)) { db.add("members", { name: v }); document.getElementById("nm").value = ""; render(); } };
  document.getElementById("st").onclick = () => printReport(T("statement") + " " + new Date().toISOString().slice(0, 10), [
    { table: totals(), cols: [{ key: "member", label: T("member") }, { key: "paid", label: T("paid") }, { key: "received", label: T("received") }], totals: ["paid", "received"] },
    { heading: T("record") }, { table: db.list("tx").map((x) => Object.assign({}, x, { type: T(x.type) })), cols: [{ key: "date", label: T("date") }, { key: "member", label: T("member") }, { key: "type", label: T("type") }, { key: "amount", label: T("amount") }, { key: "ref", label: T("ref") }] }]);
  document.getElementById("csv").onclick = () => downloadCSV("chama.csv", db.list("tx"));
  document.getElementById("bk").onclick = () => db.exportFile();
  if ("serviceWorker" in navigator && location.protocol !== "file:") navigator.serviceWorker.register("sw.js").catch(() => {});
  render();
})();
