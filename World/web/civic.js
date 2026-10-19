/* Archie World: lawmaking. Lives inside the governments screen (tabs: lawmaking · calendar · my reps).
   Bills and where they stand, every recorded vote and who cast it, each lawmaker's record, campaign money (US),
   executive actions (US), the political calendar, and your own representatives. The public record only:
   no scores, no ratings, no labels on anyone. */
/* Party colors: each party's own customary color where well known (US: Democrats blue, Republicans red). */
window.archiePartyColor = (function () {
  var L = [
    // names that would otherwise be caught by a broader pattern below (checked first)
    [/unión demócrata independiente|^udi$/i, "#29348e"], [/partido republicano( de chile)?$/i, "#0b2e59"], [/renovación nacional/i, "#0e5aa7"], [/evópoli|evolución política/i, "#00a0d6"],
    [/partido comunista/i, "#b71c1c"], [/frente amplio/i, "#6a2c91"], [/partido por la democracia/i, "#e6a800"], [/demócrata cristiano/i, "#2f7bbf"], [/nacional libertario/i, "#c9a800"],
    [/social cristiano/i, "#5aa0d8"], [/partido radical/i, "#c62828"], [/^partido socialista/i, "#e4002b"],
    [/^liberal party$|liberal party of australia/i, "#1c4f9c"], [/australian labor/i, "#de3533"], [/australian greens/i, "#10c25b"], [/^national party$|nationals/i, "#006644"], [/one nation/i, "#f36c21"],
    [/^fratelli d'italia$/i, "#03386a"], [/^partito democratico$/i, "#e2001a"], [/movimento 5 stelle/i, "#e6c200"], [/^lega$/i, "#008a3d"], [/^forza italia$/i, "#0087dc"],
    [/alleanza verdi e sinistra/i, "#5aa02c"], [/^azione$/i, "#2d3e8c"], [/^italia viva$/i, "#d63c7e"], [/^noi moderati$/i, "#1b75bb"], [/gruppo misto|mišri seimo|позафракційні/i, "#8d927f"],
    [/socialdemokratų/i, "#e3001b"], [/tėvynės sąjunga/i, "#1f6fb5"], [/liberalų sąjūdis/i, "#f7a800"], [/valstiečių/i, "#009f3c"], [/vardan lietuvos/i, "#7a1e48"], [/nemuno aušra/i, "#8d5a2b"],
    [/слуга народу/i, "#237a3b"], [/європейська солідарність/i, "#b01e4f"], [/батьківщина/i, "#d7262c"], [/^голос$/i, "#ef7d00"], [/платформа за життя/i, "#2b5d9b"], [/довіра/i, "#4f6fa8"],
    [/за майбутнє/i, "#6a1b9a"], [/відновлення україни/i, "#3d6fb6"],
    [/^ano\b|ano 2011/i, "#261060"], [/^ods$|občanská demokratická/i, "#004494"], [/^stan$|starostové/i, "#2e8b57"], [/kdu-čsl/i, "#f0ab00"], [/top ?09/i, "#7b1fa2"], [/^spd$|svoboda a přímá/i, "#7a5a00"], [/piráti/i, "#505050"], [/motoristé/i, "#d32f2f"],
    [/^(d|dem|democrat|democratic)\b|democratic party|democratic-farmer|^dfl$/i, "#2f6fd6"], [/^(r|rep|gop)$|republican/i, "#d93a3a"],
    [/^(i|ind)$|independent|non-?affiliated|crossbench|non-inscrits|^ni$/i, "#8d927f"],
    [/^lab(our)?\b|labour party|^lab$/i, "#e4003b"], [/conservative and unionist|^con$|^conservative$/i, "#0087dc"], [/liberal democrat|^ld$/i, "#faa61a"],
    [/scottish national|^snp$/i, "#e8d84a"], [/reform uk|^ref$/i, "#12b6cf"], [/^green|green party|greens\/efa|grüne|bündnis 90/i, "#4caf50"],
    [/plaid/i, "#008142"], [/^dup$|democratic unionist/i, "#d46a4c"], [/sinn f[eé]in|^sf$/i, "#2e8b57"], [/fianna f[aá]il|^ff$/i, "#66bb66"], [/fine gael|^fg$/i, "#6699ff"],
    [/^liberal$|liberal party of canada|^lib$/i, "#d71920"], [/conservative party of canada/i, "#1a4782"], [/new democratic|^ndp$/i, "#f37021"], [/bloc qu[eé]b[eé]cois/i, "#33b2cc"],
    [/^cdu|^csu|cdu\/csu|union/i, "#6b6b6b"], [/^spd\b|social democratic party of germany/i, "#e3000f"], [/^afd\b|alternative für deutschland/i, "#009ee0"], [/^fdp\b/i, "#e6c800"], [/linke/i, "#be3075"], [/^bsw\b/i, "#7d254f"],
    [/^epp$|european people/i, "#3399ff"], [/^s&d$|socialists and democrats/i, "#ff3b3b"], [/^pfe$|patriots for europe/i, "#283593"], [/^ecr$|european conservatives/i, "#0054a5"],
    [/^renew\b/i, "#e6b800"], [/^the left$|^gue/i, "#990000"], [/^esn$|sovereign nations/i, "#5d4037"],
    [/^rn$|rassemblement national|national rally/i, "#283593"], [/^epr$|renaissance|ensemble/i, "#e6b800"], [/^lfi|france insoumise/i, "#cc2443"], [/^soc$|socialiste|^ps$/i, "#ff6680"], [/^dr$|r[eé]publicains/i, "#0066cc"],
    [/^pis$|prawo i sprawiedliwo/i, "#263778"], [/^ko$|koalicja obywatelska/i, "#f68f2d"], [/^psoe$|^gs$|socialista/i, "#e30613"], [/^gp$|^pp$|popular/i, "#1d84ce"], [/^vox|^gvox/i, "#63be21"], [/sumar/i, "#e6007e"],
    [/^pt$|trabalhadores/i, "#cc0000"], [/^pl$|liberal brazil|partido liberal/i, "#1f3f8f"],
    [/^vvd$/i, "#ff7f0e"], [/^pvv$/i, "#1e3a8a"], [/^sp$/i, "#e53935"], [/gl-?pvda|groenlinks/i, "#4caf50"], [/^d66$/i, "#00a651"], [/^cda$/i, "#2e7d32"],
    [/socialdemokrat|^s$/i, "#e4002b"], [/venstre|^v$/i, "#1e3a8a"], [/^kok$|kokoomus/i, "#2a5d9f"], [/^ps$|perussuomalaiset/i, "#e6c800"], [/^sd$|suomen sosialidemokraattinen/i, "#e4002b"],
    [/reform party|reformierakond/i, "#ffd200"],
    [/^moderaterna$/i, "#1b49dd"], [/sverigedemokraterna/i, "#dddd00"], [/vänsterpartiet/i, "#af0000"], [/centerpartiet/i, "#009933"], [/kristdemokraterna/i, "#000077"],
    [/miljöpartiet/i, "#83cf39"], [/^liberalerna$/i, "#6ab2e7"], [/^socialdemokraterna$/i, "#e8112d"],
    [/arbeiderpartiet/i, "#e4202c"], [/^høyre$/i, "#0065f1"], [/fremskrittspartiet/i, "#004f80"], [/senterpartiet/i, "#00843d"], [/sosialistisk venstreparti/i, "#eb4040"],
    [/^rødt$/i, "#7a0000"], [/^venstre$/i, "#00807b"], [/kristelig folkeparti/i, "#fcd34d"], [/miljøpartiet de grønne/i, "#6a9325"],
    [/samfylkingin/i, "#ea0038"], [/sjálfstæðisflokkur/i, "#00adef"], [/viðreisn/i, "#ff7d14"], [/flokkur fólksins/i, "#ffca3e"], [/framsókn/i, "#00683f"], [/miðflokkur/i, "#199094"], [/vinstri/i, "#4b8a3f"], [/píratar/i, "#7d2e8e"]
  ];
  return function (name, fallback) {
    var n = String(name || "").trim();
    for (var i = 0; i < L.length; i++) if (L[i][0].test(n)) return L[i][1];
    return fallback || null;
  };
})();
window.ArchieCivic = function (ctx) {
  "use strict";
  var esc = ctx.esc, api = ctx.api;
  // yes/no colors are deliberately not party colors (blue/red), so a party's "no" never looks like the other party
  var POS = { Y: ["yes", "#1fa67a"], N: ["no", "#9085e9"], A: ["abstain", "#8d927f"], X: ["didn't vote", "#3b4033"], O: ["other", "#5e6352"] };
  var PIE = ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#9085e9"], OTHER = "#4a4f44";
  var STAGES = ["Introduced", "In committee / debate", "Out of committee", "Passed one chamber", "Passed both", "Sent for signature", "Law"];
  var ov = null, cc = "US", sub = "bills", q = "", chamber = "", stage = "", offset = 0, root = null, drawer = null, filtRec = "all", moneyCycle = 0, execKind = "";
  var CCNAME = {};
  var MORE3 = null;  // part three (civic3.js): debates, UK money, state votes, election night
  function more3() {
    if (!MORE3 && window.ArchieCivicExtra) MORE3 = window.ArchieCivicExtra({ esc: esc, api: api, sec: sec, loading: loading, fmtDate: fmtDate, usd: usd, pct: pct, PIE: PIE, OTHER: OTHER, flag: flag,
      pie: pie, legend: legend, openDrawer: openDrawer, openMember: openMember, openVote: openVote,
      setQ: function (v) { var bd = root && root.querySelector(".cv-main"); if (!bd) return; q = v; offset = 0; var i = bd.querySelector("#cv-q"); if (i) i.value = v; list(bd.parentNode); } });
    return MORE3;
  }
  var MORE4 = null;  // part five (civic4.js): local government, bill versions side by side
  function more4() {
    if (!MORE4 && window.ArchieCivicLocal) MORE4 = window.ArchieCivicLocal({ esc: esc, api: api, sec: sec, loading: loading, fmtDate: fmtDate, openDrawer: openDrawer, explainBtn: explainBtn, wireExplain: wireExplain });
    return MORE4;
  }
  var MORE = null;   // part two (civic2.js): courts, committees, lobbying, stock trades
  function more2() {
    if (!MORE && window.ArchieCivicMore) MORE = window.ArchieCivicMore({ esc: esc, api: api, sec: sec, loading: loading, fmtDate: fmtDate, usd: usd, pct: pct, PIE: PIE, OTHER: OTHER,
      flag: flag, nice: nice, stageDots: stageDots, partyLetter: partyLetter, openDrawer: openDrawer, watchBtn: watchBtn, wireWatch: wireWatch, explainBtn: explainBtn, wireExplain: wireExplain,
      openBill: openBill, openMember: openMember, openVote: openVote, sources: sources, more: function (n, per) { return more(n, per); },
      pager: function (L) { L.querySelectorAll(".cv-more").forEach(function (b) { b.onclick = function () { offset = Math.max(0, offset + (+b.dataset.d) * 100); var bd = root && root.querySelector(".cv-main"); if (bd) list(bd.parentNode); }; }); },
      setQ: function (v) { var bd = root && root.querySelector(".cv-main"); if (!bd) return; q = v; offset = 0; var i = bd.querySelector("#cv-q"); if (i) i.value = v; list(bd.parentNode); } });
    return MORE;
  }

  /* ---------- helpers ---------- */
  function flag(c, big) { return '<img class="gv-flag' + (big ? " big" : "") + '" src="/web/flags/' + c + '.svg" alt="" onerror="this.style.visibility=\'hidden\'">'; }
  function fmtDate(d) { if (!d) return ""; var t = /^\d{4}-\d\d-\d\d$/.test(d) ? new Date(d + "T12:00:00") : new Date(d); return isNaN(t) ? d : t.toLocaleDateString([], { month: "short", day: "numeric", year: "numeric" }); }
  function usd(v) { if (v == null) return "—"; var a = Math.abs(v); return "$" + (a >= 1e9 ? (v / 1e9).toFixed(2) + "B" : a >= 1e6 ? (v / 1e6).toFixed(a >= 1e7 ? 1 : 2) + "M" : a >= 1e3 ? (v / 1e3).toFixed(a >= 1e4 ? 0 : 1) + "K" : Math.round(v)); }
  function pct(a, b) { return b ? Math.round(100 * a / b) + "%" : "—"; }
  var ACR = /^(PAC|PACS|USA|MAGA|US|AFL|CIO|AFSCME|SEIU|UAW|NEA|AFT|IBEW|NRA|AIPAC|UDP|DCCC|NRCC|DSCC|NRSC|DNC|RNC|II|III|IV|LCV|ECU|NAR|AT&T|LLC|LLP|PLLC|LP|CWA|UFCW|IAFF|ATA|AMA|AHA|ABA|NEA|CTA|BIPAC|NFIB)$/;
  function nice(n) {   // FEC names are ALL CAPS: "THE BOEING COMPANY" -> "The Boeing Company"
    n = (n || "").replace(/\s+/g, " ").trim();
    if (n !== n.toUpperCase()) return n;
    return n.split(" ").map(function (w, i) {
      var core = w.replace(/[^A-Z0-9&]/g, "");
      if (ACR.test(core) || /^\(.*\)$/.test(w)) return w;
      if (i > 0 && /^(OF|AND|THE|FOR|TO|IN|ON|AT|BY)$/.test(w)) return w.toLowerCase();
      return w.charAt(0) + w.slice(1).toLowerCase();
    }).join(" ").replace(/'S\b/g, "'s");
  }
  function stageDots(s, compact) {
    if (s === -1) return '<span class="cv-dead">stopped</span>';
    var h = '<span class="cv-pipe' + (compact ? " sm" : "") + '" title="' + esc(STAGES[Math.max(0, s)]) + '">';
    for (var i = 0; i < 7; i++) h += '<i class="' + (i < s ? "done" : i === s ? "now" : "") + '"></i>';
    return h + "</span>";
  }
  function tally(v, wide) {
    var tot = (v.yes || 0) + (v.no || 0) + (v.abstain || 0) + (v.absent || 0);
    if (!tot) return '<span class="cv-small">' + (v.kind === "symbolic" ? "symbolic vote: no names recorded" : v.kind === "assent" ? "agreed by assent" : "no tally") + "</span>";
    var seg = function (n, k) { return n ? '<i style="width:' + (100 * n / tot) + "%;background:" + POS[k][1] + '" title="' + POS[k][0] + ": " + n + '"></i>' : ""; };
    return '<span class="cv-tally' + (wide ? " wide" : "") + '">' + seg(v.yes, "Y") + seg(v.no, "N") + seg(v.abstain, "A") + seg(v.absent, "X") + "</span>" +
      '<span class="cv-tnum"><b style="color:' + POS.Y[1] + '">' + (v.yes || 0) + '</b>–<b style="color:' + POS.N[1] + '">' + (v.no || 0) + "</b>" + (v.abstain ? " · " + v.abstain + " abst." : "") + "</span>";
  }
  function resBadge(r) {
    if (!r) return "";
    var ok = /pass|agreed|adopt|confirm|approv|ayes had|contents had|carried|won/i.test(r) && !/not agreed|failed|reject/i.test(r);
    var no = /fail|reject|not agreed|lost|defeat|noes had|not-contents had/i.test(r);
    return '<span class="cv-res ' + (ok ? "ok" : no ? "no" : "") + '">' + esc(r) + "</span>";
  }
  function sec(title, body) { return '<div class="cv-sec"><div class="cv-h">' + title + "</div>" + body + "</div>"; }
  function loading(t) { return '<div class="cv-small cv-pad">' + esc(t || "Loading…") + "</div>"; }
  function partyLetter(p) { var m = { Democrat: "D", Democratic: "D", Republican: "R", Independent: "I" }; return m[p] || p || ""; }

  /* ---------- entry ---------- */
  function render(body, screen, opt, gvroot) {
    root = gvroot;
    if (!drawer) { drawer = document.createElement("div"); drawer.className = "cv-drawer"; drawer.hidden = true; gvroot.appendChild(drawer); }
    opt = opt || {};
    if (opt.cc) { cc = opt.cc; sub = opt.sub || sub; offset = 0; }
    if (/^(bills|votes|people|exec|watching|courts|committees|lobbying|trades|debates)$/.test(opt.open || "")) { sub = opt.open; opt.open = ""; q = ""; }
    if (/^find:/.test(opt.open || "")) { sub = "people"; q = decodeURIComponent(opt.open.slice(5)).replace(/\+/g, " "); opt.open = ""; }
    var go = function () {
      if (screen === "law") law(body);
      else if (screen === "cal") calendar(body, opt.govs);
      else if (screen === "reps") reps(body);
      else if (screen === "elec" && more3()) more3().elections(body);
      else if (screen === "local" && more4()) { more4().local(body, opt.open || ""); return; }
      if (opt.open) openThing(opt.open);
    };
    if (ov && Date.now() - (ov._at || 0) < 60000) go(); else { body.innerHTML = loading("Loading the public record…"); api("/api/civic/overview").then(function (d) { ov = d; ov._at = Date.now(); (ov.countries || []).forEach(function (c) { CCNAME[c.cc] = c.name; }); go(); }).catch(function () { body.innerHTML = '<div class="cv-small cv-pad">Couldn\'t reach Archie\'s lawmaking data.</div>'; }); }
  }
  function openThing(t) {   // "bill:ID" / "vote:ID" / "member:KEY" / "exec:ID"
    var i = t.indexOf(":"), k = t.slice(0, i), id = t.slice(i + 1);
    if (k === "bill") openBill(id); else if (k === "vote") openVote(id); else if (k === "member") openMember(id); else if (k === "exec") openExec(id);
    else if (k === "elec" && more3()) more3().openElection(id);
    else if (more2()) more2().open(k, id);
  }

  /* ---------- lawmaking ---------- */
  function law(body) {
    var C = (ov.countries || []).filter(function (c) { return c.votes || c.bills; });
    if (!C.length) C = ov.countries || [];
    var cur = (ov.countries || []).find(function (c) { return c.cc === cc; }) || C[0];
    if (cur) cc = cur.cc;
    var subs = [["bills", "bills", cur && cur.bills], ["votes", "votes", cur && cur.votes], ["people", "people", 1], ["exec", "executive actions", cur && cur.exec]]
      .concat(cc === "US" && more2() ? more2().subs.map(function (s) { return [s[0], s[1], 1]; }) : []).concat((cc === "US" || cc === "GB") && more3() ? [["debates", "what was said", 1]] : []).concat([["watching", "★ watching", 1]]).filter(function (s) { return s[2] || s[0] === "bills" && cc === "US"; });
    if (!subs.some(function (s) { return s[0] === sub; })) sub = subs[0] ? subs[0][0] : "votes";
    body.innerHTML = '<div class="gv-left cv-left"><div class="cv-lh">PARLIAMENTS WITH A PUBLIC VOTING RECORD</div><div class="gv-list" id="cv-cl"></div>' +
      '<div class="cv-lfoot">Only some countries publish how each lawmaker votes. Most of the world\'s parliaments vote by voice or show of hands, or don\'t publish names, so they aren\'t here. ' +
      '<a href="#" id="cv-src">data sources and status</a></div></div>' +
      '<div class="cv-main"><div class="cv-top">' + (cur ? flag(cur.cc) + "<b>" + esc(cur.name) + "</b>" : "") +
      '<div class="gv-tabs small" id="cv-subs">' + subs.map(function (s) { return '<button data-s="' + s[0] + '" class="' + (s[0] === sub ? "on" : "") + '">' + s[1] + "</button>"; }).join("") + "</div>" +
      '<input id="cv-q" placeholder="' + ((sub === "debates" && "search what was said: a word, phrase or name…") || (more2() && more2().has(sub) && more2().placeholder(sub)) || (sub === "people" ? "find a lawmaker, party or place…" : sub === "exec" ? "search titles and agencies…" : "search titles, numbers, sponsors…")) + '" value="' + esc(q) + '" autocomplete="off"' + (more2() && more2().has(sub) && !more2().placeholder(sub) ? ' style="visibility:hidden"' : "") + '>' +
      (cur ? '<span class="cv-note">' + esc(cur.note) + "</span>" : "") + '</div><div class="cv-filters" id="cv-f"></div><div class="cv-list" id="cv-list">' + loading() + "</div></div>";
    var cl = body.querySelector("#cv-cl");
    cl.innerHTML = (ov.countries || []).map(function (c) {
      var empty = !c.votes && !c.bills;
      return '<button class="gv-row' + (c.cc === cc ? " on" : "") + (empty ? " cv-empty" : "") + '" data-c="' + c.cc + '">' + flag(c.cc) + "<b>" + esc(c.name) + "</b><i>" +
        (empty ? "waiting for the first download" : [c.votes ? c.votes.toLocaleString() + (c.votes === 1 ? " vote" : " votes") : "", c.bills ? c.bills.toLocaleString() + (c.bills === 1 ? " bill" : " bills") : "", c.money ? "campaign money" : ""].filter(Boolean).join(" · ")) + "</i></button>";
    }).join("");
    cl.querySelectorAll(".gv-row").forEach(function (b) { b.onclick = function () { cc = b.dataset.c; q = ""; chamber = ""; stage = ""; offset = 0; law(body); }; });
    body.querySelector("#cv-src").onclick = function (e) { e.preventDefault(); sources(); };
    body.querySelectorAll("#cv-subs button").forEach(function (b) { b.onclick = function () { sub = b.dataset.s; q = ""; stage = ""; offset = 0; law(body); }; });
    var t = null;
    body.querySelector("#cv-q").oninput = function () { var v = this.value.trim(); clearTimeout(t); t = setTimeout(function () { q = v; offset = 0; list(body); }, 250); };
    list(body);
  }
  function list(body) {
    var L = body.querySelector("#cv-list"), F = body.querySelector("#cv-f"), cur = (ov.countries || []).find(function (c) { return c.cc === cc; }) || {};
    var chips = function (items, val, cb) { return items.map(function (x) { return '<button data-v="' + esc(x[0]) + '" class="' + (String(val) === String(x[0]) ? "on" : "") + '">' + x[1] + "</button>"; }).join(""); };
    var chs = Object.keys(cur.chambers || {});
    if (sub === "bills") {
      api("/api/civic/bills?cc=" + cc + "&q=" + encodeURIComponent(q) + "&stage=" + stage + "&offset=" + offset).then(function (d) {
        var n = d.counts || {}, tot = Object.keys(n).reduce(function (a, k) { return a + n[k]; }, 0);
        F.innerHTML = '<div class="cv-funnel">' + STAGES.map(function (s, i) { return '<button data-v="' + i + '" class="' + (String(stage) === String(i) ? "on" : "") + '"><b>' + (n[i] || 0).toLocaleString() + "</b><span>" + s + "</span></button>"; }).join('<i class="cv-arr">›</i>') +
          '<button data-v="-1" class="dead' + (stage === "-1" ? " on" : "") + '"><b>' + (n[-1] || 0).toLocaleString() + "</b><span>stopped</span></button></div>" +
          '<div class="cv-chips"><button data-v="" class="' + (stage === "" ? "on" : "") + '">all ' + tot.toLocaleString() + '</button><button data-v="moving" class="' + (stage === "moving" ? "on" : "") + '">moving (past committee, not yet law)</button></div>';
        F.querySelectorAll("button").forEach(function (b) { b.onclick = function () { stage = stage === b.dataset.v ? "" : b.dataset.v; offset = 0; list(body); }; });
        if (!d.bills.length) { L.innerHTML = '<div class="cv-small cv-pad">' + (tot ? "No bills match." : "No bills have reached Archie for " + esc(cur.name) + " yet. " + (cc === "US" ? "The first download is about 50 MB; it runs in the background while Archie is online." : "It checks a few times a day while online.")) + "</div>"; return; }
        L.innerHTML = d.bills.map(function (b) {
          return '<button class="cv-row bill" data-id="' + esc(b.id) + '"><span class="cv-num">' + esc(b.num || "") + "</span><span class=\"cv-t\"><b>" + esc(b.title || "(untitled)") + "</b><i>" +
            [b.sponsor ? esc(b.sponsor) + (b.party ? " (" + esc(partyLetter(b.party)) + ")" : "") : "", b.subject ? esc(b.subject) : "", b.latest_text ? esc(b.latest_text.slice(0, 140)) : ""].filter(Boolean).join(" · ") + "</i></span>" +
            '<span class="cv-st">' + stageDots(b.stage, true) + "<i>" + esc(b.stage_text || "") + "</i></span><span class=\"cv-d\">" + esc(fmtDate(b.latest_date)) + "</span></button>";
        }).join("") + more(d.bills.length, 80);
        L.querySelectorAll(".cv-row").forEach(function (r) { r.onclick = function () { openBill(r.dataset.id); }; });
        pager(body, L);
      });
    } else if (sub === "votes") {
      F.innerHTML = chs.length > 1 ? '<div class="cv-chips"><button data-v="" class="' + (!chamber ? "on" : "") + '">both chambers</button>' + chs.map(function (k) { return '<button data-v="' + k + '" class="' + (chamber === k ? "on" : "") + '">' + esc(cur.chambers[k]) + "</button>"; }).join("") + "</div>" : "";
      F.querySelectorAll("button").forEach(function (b) { b.onclick = function () { chamber = b.dataset.v; offset = 0; list(body); }; });
      api("/api/civic/votes?cc=" + cc + "&chamber=" + chamber + "&q=" + encodeURIComponent(q) + "&offset=" + offset).then(function (d) {
        if (!d.votes.length) { L.innerHTML = '<div class="cv-small cv-pad">' + (q ? "No votes match." : "No votes have reached Archie for " + esc(cur.name) + " yet. It checks a few times a day while online.") + "</div>"; return; }
        L.innerHTML = d.votes.map(function (v) {
          return '<button class="cv-row vote" data-id="' + esc(v.id) + '"><span class="cv-d">' + esc(fmtDate(v.date)) + "<i>" + esc((cur.chambers || {})[v.chamber] || "") + '</i></span><span class="cv-t"><b>' + esc(v.title || v.question || "(no title)") + "</b><i>" +
            esc(v.question && v.title ? v.question : "") + "</i></span><span class=\"cv-vr\">" + resBadge(v.result) + tally(v) + "</span></button>";
        }).join("") + more(d.votes.length, 60);
        L.querySelectorAll(".cv-row").forEach(function (r) { r.onclick = function () { openVote(r.dataset.id); }; });
        pager(body, L);
      });
    } else if (sub === "people") {
      F.innerHTML = chs.length > 1 ? '<div class="cv-chips"><button data-v="" class="' + (!chamber ? "on" : "") + '">everyone</button>' + chs.map(function (k) { return '<button data-v="' + k + '" class="' + (chamber === k ? "on" : "") + '">' + esc(cur.chambers[k]) + "</button>"; }).join("") + "</div>" : "";
      F.querySelectorAll("button").forEach(function (b) { b.onclick = function () { chamber = b.dataset.v; list(body); }; });
      api("/api/civic/members?cc=" + cc + "&chamber=" + chamber + "&q=" + encodeURIComponent(q)).then(function (d) {
        var M = d.members || [];
        if (!M.length) { L.innerHTML = '<div class="cv-small cv-pad">' + (q ? "Nobody matches." : "Lawmakers show up here once their first votes have reached Archie.") + "</div>"; return; }
        var groups = {};
        M.forEach(function (m) { (groups[m.party || "—"] = groups[m.party || "—"] || []).push(m); });
        var keys = Object.keys(groups).sort(function (a, b) { return groups[b].length - groups[a].length; });
        L.innerHTML = '<div class="cv-small cv-pad">' + M.length.toLocaleString() + " " + (cc === "NL" ? "parties (the Dutch record shows how each party voted)" : "lawmakers") + ". Pick anyone to see how they've voted" + (cc === "US" ? " and who funds their campaigns" : "") + ".</div>" +
          keys.map(function (k) {
            return '<div class="cv-pgroup"><div class="cv-pg"><i class="cv-sw" style="background:' + window.archiePartyColor(k, "#5e6352") + '"></i>' + esc(k) + " · " + groups[k].length + '</div><div class="cv-people">' + groups[k].map(function (m) {
              return '<button class="cv-person" data-k="' + esc(m.key) + '"><b>' + esc(m.name) + "</b><i>" + esc([(cur.chambers || {})[m.chamber] || "", m.area].filter(Boolean).join(" · ")) + "</i></button>";
            }).join("") + "</div></div>";
          }).join("");
        L.querySelectorAll(".cv-person").forEach(function (r) { r.onclick = function () { openMember(r.dataset.k); }; });
      });
    } else if (sub === "watching") {
      F.innerHTML = "";
      watchList(L);
    } else if (sub === "debates" && more3()) {
      more3().debatesList(cc, L, F, q);
    } else if (more2() && more2().has(sub)) {
      more2().list(sub, L, F, q, offset, function () { law(body); });
    } else if (sub === "exec") {
      F.innerHTML = '<div class="cv-chips">' + [["", "everything"], ["eo", "executive orders"], ["other", "proclamations, memos & notices"], ["rules", "major agency rules"]].map(function (x) { return '<button data-v="' + x[0] + '" class="' + (execKind === x[0] ? "on" : "") + '">' + x[1] + "</button>"; }).join("") +
        '</div><div class="cv-small">What the President signs, and the biggest new rules from federal agencies, as published in the Federal Register. These take effect without a vote in Congress.</div>';
      F.querySelectorAll("button").forEach(function (b) { b.onclick = function () { execKind = b.dataset.v; offset = 0; list(body); }; });
      api("/api/civic/exec?kind=" + execKind + "&q=" + encodeURIComponent(q) + "&offset=" + offset).then(function (d) {
        if (!d.items.length) { L.innerHTML = '<div class="cv-small cv-pad">Nothing yet. Archie checks the Federal Register every few hours while online.</div>'; return; }
        L.innerHTML = d.items.map(function (e) {
          return '<button class="cv-row exec" data-id="' + esc(e.id) + '"><span class="cv-d">' + esc(fmtDate(e.signed || e.date)) + '<i>' + (e.signed ? "signed" : "published") + '</i></span><span class="cv-t"><b>' + esc(e.title) + "</b><i>" + esc(e.agency || "") + "</i></span><span class=\"cv-kind\">" + esc(e.kind) + (e.number ? " " + esc(e.number) : "") + "</span></button>";
        }).join("") + more(d.items.length, 80);
        L.querySelectorAll(".cv-row").forEach(function (r) { r.onclick = function () { openExec(r.dataset.id); }; });
        pager(body, L);
      });
    }
  }
  function more(n, per) { return (offset ? '<button class="cv-more" data-d="-1">‹ newer</button>' : "") + (n >= per ? '<button class="cv-more" data-d="1">older ›</button>' : ""); }
  function pager(body, L) {
    var per = sub === "votes" ? 60 : 80;
    L.querySelectorAll(".cv-more").forEach(function (b) { b.onclick = function () { offset = Math.max(0, offset + (+b.dataset.d) * per); list(body); L.scrollTop = 0; }; });
  }

  /* ---------- watchlist ---------- */
  function watchBtn(kind, id, label, cc) {
    return '<button class="cv-watch" data-wk="' + kind + '" data-wid="' + esc(id) + '" data-wl="' + esc(label || "") + '" data-wc="' + esc(cc || "") + '">☆ watch</button>';
  }
  function wireWatch(el) {
    el.querySelectorAll(".cv-watch").forEach(function (b) {
      var set = function (on) { b.classList.toggle("on", on); b.textContent = on ? "★ watching" : "☆ watch"; b.title = on ? "Archie tells you when this changes. Click to stop." : "Get a notification when this changes"; };
      api("/api/civic/watch?kind=" + b.dataset.wk + "&id=" + encodeURIComponent(b.dataset.wid)).then(function (d) { set(!!d.watching); });
      b.onclick = function (e) {
        e.stopPropagation();
        var on = !b.classList.contains("on");
        api("/api/civic/watch", { kind: b.dataset.wk, id: b.dataset.wid, label: b.dataset.wl, cc: b.dataset.wc, on: on }).then(function () { set(on); });
      };
    });
  }
  function watchList(L) {
    L.innerHTML = loading();
    api("/api/civic/watch").then(function (d) {
      var I = d.items || [], E = d.events || [];
      if (!I.length) { L.innerHTML = '<div class="cv-small cv-pad">Nothing pinned yet. Open any bill, lawmaker, committee or Supreme Court case and click <b>☆ watch</b>. Archie checks every half hour and sends you a notification when a bill moves, a lawmaker casts a new recorded vote or reports a stock trade, a committee gets a new bill or hearing, or the Court schedules or decides a case. Changes also show up in the news brief.</div>'; return; }
      var row = function (w) {
        if ((w.kind === "case" || w.kind === "committee") && more2()) return more2().watchRow(w);
        if (w.kind === "bill") {
          var b = w.now || {};
          return '<button class="cv-row bill" data-bill="' + esc(w.id) + '"><span class="cv-num">' + flag(w.cc) + " " + esc(b.num || "") + '</span><span class="cv-t"><b>' + esc(b.title || w.label) + "</b><i>" + esc(b.latest_text || "") + '</i></span><span class="cv-st">' + stageDots(b.stage, true) + "<i>" + esc(b.stage_text || "") + '</i></span><span class="cv-d">' + esc(fmtDate(b.latest_date)) + "</span></button>";
        }
        var r = (w.recent || [])[0];
        return '<button class="cv-row bill" data-mem="' + esc(w.id) + '"><span class="cv-num">' + flag(w.cc) + ' lawmaker</span><span class="cv-t"><b>' + esc(w.label) + "</b><i>" + (r ? "last vote: " + esc(POS[r.pos] ? POS[r.pos][0] : r.pos) + " on " + esc(r.title || r.question || "") : "no recorded votes yet") + '</i></span><span class="cv-st"><i>' + (w.now ? w.now.n + " recorded votes" : "") + '</i></span><span class="cv-d">' + esc(fmtDate(r && r.date)) + "</span></button>";
      };
      L.innerHTML = (E.length ? '<div class="cv-mh">WHAT CHANGED' + (d.unseen ? " · " + d.unseen + " new" : "") + '</div><div class="cv-evlist">' + E.slice(0, 30).map(function (e) {
        return '<button class="cv-wev' + (e.seen ? "" : " new") + '" data-link="' + esc(e.link) + '"><span class="cv-d">' + esc(new Date(e.at * 1000).toLocaleDateString([], { month: "short", day: "numeric" })) + '</span><span class="cv-t"><b>' + esc(e.label) + "</b><i>" + esc(e.detail) + "</i></span></button>";
      }).join("") + "</div>" : "") +
        '<div class="cv-mh">PINNED · ' + I.length + '</div>' + I.map(row).join("") +
        '<div class="cv-small">Archie compares each one with what it last saw every half hour, using data it has already downloaded, so watching costs nothing extra. Bills update as often as their parliament\'s data does (US every 6 hours).</div>';
      L.querySelectorAll("[data-bill]").forEach(function (b) { b.onclick = function () { openBill(b.dataset.bill); }; });
      L.querySelectorAll("[data-mem]").forEach(function (b) { b.onclick = function () { openMember(b.dataset.mem); }; });
      L.querySelectorAll("[data-link]").forEach(function (b) { b.onclick = function () { var m = b.dataset.link.match(/:(bill|member|case|cmte):(.+)$/); if (m) openThing(m[1] + ":" + m[2]); }; });
      if (more2()) more2().wireWatchRows(L);
      if (d.unseen) api("/api/civic/watch_seen", {});
    });
  }

  /* ---------- drawer ---------- */
  function openDrawer(html) {
    drawer.innerHTML = '<button class="cv-dx" title="close">✕</button><div class="cv-dbody">' + html + "</div>";
    drawer.hidden = false;
    drawer.querySelector(".cv-dx").onclick = function () { drawer.hidden = true; };
    drawer.querySelector(".cv-dbody").scrollTop = 0;
    return drawer.querySelector(".cv-dbody");
  }
  document.addEventListener("keydown", function (e) { if (drawer && !drawer.hidden && e.key === "Escape") { drawer.hidden = true; e.stopPropagation(); } }, true);
  function explainBtn(kind, id, have, label) {
    return '<div class="cv-explain" data-k="' + kind + '" data-id="' + esc(id) + '">' + (have ? '<div class="cv-plain"><b>In plain English</b> <em>written by Archie\'s own AI from the official text; check the source for anything important</em><p>' + esc(have) + "</p></div>"
      : '<button class="cv-btn">' + esc(label || "explain this in plain English") + '</button><span class="cv-small">Archie\'s own AI reads the official text and explains it neutrally. It runs on this PC and can take a minute.</span>') + "</div>";
  }
  function wireExplain(el) {
    el.querySelectorAll(".cv-explain .cv-btn").forEach(function (b) {
      b.onclick = function () {
        var box = b.parentNode; b.disabled = true; b.textContent = "reading the text…";
        api("/api/civic/summary", { kind: box.dataset.k, id: box.dataset.id }).then(function (d) {
          box.innerHTML = d.error ? '<div class="cv-small">' + esc(d.error) + "</div>" : '<div class="cv-plain"><b>In plain English</b> <em>written by Archie\'s own AI from the official text; check the source for anything important</em><p>' + esc(d.text) + "</p></div>";
        }).catch(function () { box.innerHTML = '<div class="cv-small">Couldn\'t reach Archie\'s model.</div>'; });
      };
    });
  }

  function openBill(id) {
    var el = openDrawer(loading());
    api("/api/civic/bill?id=" + encodeURIComponent(id)).then(function (b) {
      if (b.error) { el.innerHTML = '<div class="cv-small">That bill isn\'t in Archie\'s records.</div>'; return; }
      var ex = b.extra || {}, acts = (ex.actions || []).slice().reverse();
      var pipe = b.stage === -1 ? '<div class="cv-dead big">' + esc(b.stage_text) + "</div>" :
        '<div class="cv-bigpipe">' + STAGES.map(function (s, i) { return '<div class="' + (i < b.stage ? "done" : i === b.stage ? "now" : "") + '"><i></i><span>' + s + "</span></div>"; }).join("") + "</div>";
      var crs = b.cc === "US" && b.summary;
      el.innerHTML = '<div class="cv-kicker">' + flag(b.cc) + " " + esc(CCNAME[b.cc] || b.cc) + " · BILL" + (b.num ? " · " + esc(b.num) : "") + watchBtn("bill", b.id, (b.num ? b.num + " " : "") + b.title, b.cc) + "</div><h2>" + esc(b.title) + "</h2>" +
        '<div class="cv-meta">' + [b.sponsor ? "Sponsor: <b>" + (b.sponsor_key ? '<a href="#" data-m="' + esc(b.sponsor_key) + '">' + esc(b.sponsor) + "</a>" : esc(b.sponsor)) + "</b>" + (b.party ? " (" + esc(b.party) + ")" : "") : "",
          ex.cosponsors ? ex.cosponsors + " co-sponsors" : "", b.introduced ? "introduced " + esc(fmtDate(b.introduced)) : "", b.subject ? esc(b.subject) : "", b.enacted ? "<b>" + esc(b.enacted) + "</b>" : ""].filter(Boolean).join(" · ") + "</div>" +
        sec("WHERE IT STANDS", pipe + '<div class="cv-now">' + esc(b.stage_text || "") + (b.latest_date ? ' <span class="cv-small">· latest: ' + esc(fmtDate(b.latest_date)) + "</span>" : "") + "</div>" + (b.latest_text ? '<div class="cv-small">' + esc(b.latest_text) + "</div>" : "")) +
        sec("WHAT IT DOES", (crs ? '<div class="cv-crs"><div class="cv-small">Summary by the Congressional Research Service (nonpartisan, part of the Library of Congress)' + (ex.summary_version ? ", " + esc(ex.summary_version.toLowerCase()) : "") + ":</div><p>" + esc(b.summary.slice(0, 2600)) + (b.summary.length > 2600 ? "…" : "") + "</p></div>"
          : b.summary ? '<div class="cv-crs"><div class="cv-small">Official description:</div><p>' + esc(b.summary.slice(0, 1800)) + "</p></div>" : (ex.long_title ? '<p class="cv-p">' + esc(ex.long_title) + "</p>" : '<div class="cv-small">No official summary yet.</div>')) +
          explainBtn("bill", b.id, b.plain, crs ? "make this simpler" : "explain this in plain English")) +
        (b.votes && b.votes.length ? sec("RECORDED VOTES ON IT · " + b.votes.length, b.votes.map(function (v) { return '<button class="cv-row vote mini" data-v="' + esc(v.id) + '"><span class="cv-d">' + esc(fmtDate(v.date)) + '</span><span class="cv-t"><b>' + esc(v.question || "vote") + "</b></span><span class=\"cv-vr\">" + resBadge(v.result) + tally(v) + "</span></button>"; }).join("")) : "") +
        (acts.length ? sec("TIMELINE", '<div class="cv-tl">' + acts.slice(0, 40).map(function (a) { return "<div><span>" + esc(fmtDate(a[0])) + "</span><p>" + esc(a[1]) + "</p></div>"; }).join("") + "</div>" + (acts.length > 40 ? '<div class="cv-small">…and ' + (acts.length - 40) + " earlier steps.</div>" : "")) : "") +
        (b.cc === "US" && more2() ? '<div id="cv-billmore"></div>' : ex.committees && ex.committees.length ? sec("COMMITTEES", '<div class="gv-parties">' + ex.committees.map(function (c) { return "<span>" + esc(c) + "</span>"; }).join("") + "</div>") : "") +
        '<div class="cv-foot"><a href="' + esc(b.url) + '" target="_blank" rel="noopener">official page ↗</a></div>';
      el.querySelectorAll("[data-v]").forEach(function (x) { x.onclick = function () { openVote(x.dataset.v); }; });
      el.querySelectorAll("[data-m]").forEach(function (x) { x.onclick = function (e) { e.preventDefault(); openMember(x.dataset.m); }; });
      wireExplain(el); wireWatch(el);
      if (b.cc === "US" && more2()) more2().billExtras(el, b);
      if (b.cc === "US" && more4()) more4().billVersions(el, b);
    });
  }

  function openVote(id) {
    var el = openDrawer(loading("Loading who voted how…"));
    api("/api/civic/vote?id=" + encodeURIComponent(id)).then(function (v) {
      if (v.error) { el.innerHTML = '<div class="cv-small">That vote isn\'t in Archie\'s records.</div>'; return; }
      var bp = v.by_party || {}, parties = Object.keys(bp).sort(function (a, b) { var s = function (x) { var o = bp[x]; return (o.Y || 0) + (o.N || 0) + (o.A || 0) + (o.X || 0); }; return s(b) - s(a); });
      var partyTable = parties.length ? '<table class="cv-ptab"><tr><th>' + (v.cc === "NL" ? "party" : "party / group") + "</th><th>yes</th><th>no</th><th>abstain</th><th>didn't vote</th><th></th></tr>" + parties.map(function (p) {
        var o = bp[p], t = (o.Y || 0) + (o.N || 0) + (o.A || 0) + (o.X || 0) || 1;
        var pcol = window.archiePartyColor(p, "#5e6352");
        return '<tr><td><i class="cv-sw" style="background:' + pcol + '"></i>' + esc(p) + "</td><td>" + (o.Y || 0) + "</td><td>" + (o.N || 0) + "</td><td>" + (o.A || 0) + "</td><td>" + (o.X || 0) + '</td><td class="cv-pbar">' +
          ["Y", "N", "A", "X"].map(function (k) { return o[k] ? '<i style="width:' + (100 * o[k] / t) + "%;background:" + POS[k][1] + '"></i>' : ""; }).join("") + "</td></tr>";
      }).join("") + "</table>" : "";
      var M = v.members || [], byPos = { Y: [], N: [], A: [], X: [], O: [] };
      M.forEach(function (m) { (byPos[m.pos] || byPos.O).push(m); });
      var names = M.length ? '<input class="cv-mq" placeholder="find a name…"><div class="cv-poscols">' + ["Y", "N", "A", "X", "O"].filter(function (k) { return byPos[k].length; }).map(function (k) {
        return '<div><div class="cv-posh" style="border-color:' + POS[k][1] + '">' + POS[k][0].toUpperCase() + " · " + byPos[k].length + "</div>" + byPos[k].map(function (m) {
          return '<button class="cv-nm" data-k="' + esc(m.member) + '" data-s="' + esc((m.name + " " + m.party).toLowerCase()) + '">' + esc(m.name) + " <i>" + esc(m.party || "") + "</i></button>";
        }).join("") + "</div>";
      }).join("") + "</div>" : '<div class="cv-small">' + (v.kind === "symbolic" ? "This was a symbolic vote: the chamber decided without recording individual names." : v.kind === "assent" ? "Agreed by assent, with no individual votes recorded." : "Names for this vote haven't been downloaded yet.") + "</div>";
      var ex = v.extra || {};
      var foreign = ["US", "GB", "IE", "CA", "EU"].indexOf(v.cc) < 0;
      el.innerHTML = '<div class="cv-kicker">' + flag(v.cc) + " " + esc(v.country) + " · " + esc(v.chamber_name || "") + " · VOTE · " + esc(fmtDate(v.date)) + "</div><h2>" + esc(v.title || "(no title)") + "</h2>" +
        (v.question ? '<div class="cv-meta">' + esc(v.question) + "</div>" : "") +
        sec("RESULT", '<div class="cv-bigres">' + resBadge(v.result) + tally(v, true) + "</div>" + (ex.needs ? '<div class="cv-small">Needed: ' + esc(ex.needs === "1/2" ? "a simple majority" : ex.needs === "3/5" ? "three-fifths (60 senators)" : ex.needs === "2/3" ? "two-thirds" : ex.needs) + "</div>" : "") +
          (ex.note ? '<div class="cv-small">' + esc(ex.note) + "</div>" : "") + (ex.party_votes ? '<div class="cv-small">Dutch votes are usually cast by party: each party\'s seats are counted together.</div>' : "")) +
        (v.bill_info ? sec("THE BILL", '<button class="cv-row bill mini" data-b="' + esc(v.bill_info.id) + '"><span class="cv-num">' + esc(v.bill_info.num) + '</span><span class="cv-t"><b>' + esc(v.bill_info.title) + "</b></span><span class=\"cv-st\">" + stageDots(v.bill_info.stage, true) + "<i>" + esc(v.bill_info.stage_text) + "</i></span></button>") : "") +
        (ex.intro ? sec("WHAT IT WAS ABOUT", '<p class="cv-p">' + esc(ex.intro.slice(0, 1200)) + "</p>") : ex.summary ? sec("WHAT IT WAS ABOUT", '<p class="cv-p">' + esc(ex.summary.slice(0, 1200)) + "</p>") : "") +
        (foreign || !v.bill_info ? sec("IN PLAIN ENGLISH", explainBtn("vote", v.id, "", foreign ? "translate and explain this vote" : "explain what this vote was about")) : "") +
        (partyTable ? sec("HOW EACH PARTY VOTED", partyTable) : "") +
        sec("WHO VOTED HOW" + (M.length ? " · " + M.length : ""), names) +
        '<div class="cv-foot"><a href="' + esc(v.url) + '" target="_blank" rel="noopener">official record ↗</a></div>';
      var mq = el.querySelector(".cv-mq");
      if (mq) mq.oninput = function () { var s = this.value.trim().toLowerCase(); el.querySelectorAll(".cv-nm").forEach(function (b) { b.style.display = !s || b.dataset.s.indexOf(s) >= 0 ? "" : "none"; }); };
      el.querySelectorAll(".cv-nm").forEach(function (b) { b.onclick = function () { openMember(b.dataset.k); }; });
      el.querySelectorAll("[data-b]").forEach(function (b) { b.onclick = function () { openBill(b.dataset.b); }; });
      wireExplain(el);
    });
  }

  function openMember(key) { memberInto(openDrawer(loading("Loading their record…")), key); }
  function memberInto(el, key, intro, after) {
    api("/api/civic/member?key=" + encodeURIComponent(key)).then(function (m) {
      var st = m.stats || {}, cast = st.votes - st.missed;
      var isUS = m.cc === "US", isParty = /^NL:party:/.test(key);
      var title = isUS ? (m.chamber === "S" ? "U.S. Senator for " + esc(m.state_name) : "U.S. Representative for " + esc(m.state_name) + (m.district ? ", district " + m.district : " (at large)")) :
        esc([/^US-/.test(m.cc) ? "" : CCNAME[m.cc] || m.cc, m.area].filter(Boolean).join(" · "));
      var rec = m.record || [];
      var recHTML = function () {
        var R = rec.filter(function (r) { return filtRec === "all" || (filtRec === "against" && r.party_pos && (r.pos === "Y" || r.pos === "N") && r.pos !== r.party_pos) || (filtRec === "missed" && r.pos === "X"); });
        return R.length ? R.map(function (r) {
          return '<button class="cv-rec" data-v="' + esc(r.id) + '"><span class="cv-d">' + esc(fmtDate(r.date)) + '</span><span class="cv-t"><b>' + esc(r.title || r.question) + "</b><i>" + esc(r.question && r.title ? r.question : "") + (r.result ? " · " + esc(r.result) : "") + '</i></span><span class="cv-pos" style="background:' + POS[r.pos][1] + '">' + POS[r.pos][0] + "</span>" +
            (r.party_pos && (r.pos === "Y" || r.pos === "N") && r.pos !== r.party_pos ? '<span class="cv-brk" title="Most of their party voted ' + POS[r.party_pos][0] + '">≠ party</span>' : "<span></span>") + "</button>";
        }).join("") : '<div class="cv-small">Nothing in this view.</div>';
      };
      var stats = st.votes ? '<div class="gv-nums cv-stats"><div class="gv-num"><div class="h">RECORDED VOTES</div><div class="v">' + st.votes.toLocaleString() + '</div></div><div class="gv-num"><div class="h">DIDN\'T VOTE</div><div class="v">' + st.missed + ' <span class="gv-yr">' + pct(st.missed, st.votes) + "</span></div></div>" +
        (st.counted && !isParty ? '<div class="gv-num"><div class="h">VOTED WITH THEIR PARTY</div><div class="v">' + pct(st.with_party, st.counted) + ' <span class="gv-yr">of ' + st.counted + "</span></div></div>" +
          '<div class="gv-num"><div class="h">BROKE WITH THEIR PARTY</div><div class="v">' + st.against_party + ' <span class="gv-yr">times</span></div></div>' : "") + "</div>" +
        '<div class="cv-small">Counted from the ' + st.votes.toLocaleString() + " recorded votes Archie has (" + esc(fmtDate(st.first)) + " – " + esc(fmtDate(st.last)) + "). \"With their party\" means they voted the same way as most of their party on that vote.</div>" : '<div class="cv-small">No recorded votes from this person have reached Archie yet.</div>';
      el.innerHTML = (intro || "") + '<div class="cv-kicker">' + flag(m.cc) + " " + (isParty ? "PARTY RECORD" : "LAWMAKER") + watchBtn("member", key, m.name || key, m.cc) + "</div><h2>" + esc(m.name || key) + (m.party && !isParty ? ' <span class="cv-party">' + esc(m.party) + "</span>" : "") + "</h2>" +
        '<div class="cv-meta">' + title + (isUS ? [m.since ? " · in Congress since " + esc(fmtDate(m.since)) : "", m.term_end ? " · current term ends " + esc(fmtDate(m.term_end)) : "", m.phone ? " · " + esc(m.phone) : ""].join("") : "") + (m.url ? ' · <a href="' + esc(m.url) + '" target="_blank" rel="noopener">official site ↗</a>' : "") + "</div>" +
        sec("THEIR VOTING RECORD", stats + (rec.length ? '<div class="cv-chips" id="cv-rf">' + [["all", "every vote"], ["against", "broke with their party"], ["missed", "didn't vote"]].map(function (x) { return '<button data-v="' + x[0] + '" class="' + (filtRec === x[0] ? "on" : "") + '">' + x[1] + "</button>"; }).join("") + '</div><div id="cv-rec">' + recHTML() + "</div>" + (rec.length >= 150 ? '<div class="cv-small">Showing the latest 150.</div>' : "") : "")) +
        (isUS ? sec("WHO FUNDS THEIR CAMPAIGNS", '<div id="cv-money">' + loading("Loading FEC filings…") + "</div>") : "") +
        (isUS && more2() ? '<div id="cv-more"></div>' : "") +
        (m.cc === "GB" && !isParty && more3() ? sec("MONEY AND INTERESTS", '<div id="cv-ukm"></div>') : "") +
        ((isUS || m.cc === "GB") && !isParty && more3() ? sec(isUS ? "WHAT THEY SAID ON THE FLOOR" : "WHAT THEY SAID IN PARLIAMENT", '<div id="cv-said"></div>') : "") +
        (m.sponsored && m.sponsored.length ? sec("BILLS THEY SPONSORED · " + m.sponsored.length, m.sponsored.map(function (b) { return '<button class="cv-row bill mini" data-b="' + esc(b.id) + '"><span class="cv-num">' + esc(b.num || "") + '</span><span class="cv-t"><b>' + esc(b.title) + '</b></span><span class="cv-st">' + stageDots(b.stage, true) + "<i>" + esc(b.stage_text) + "</i></span></button>"; }).join("")) : "");
      var wire = function () {
        el.querySelectorAll(".cv-rec").forEach(function (b) { b.onclick = function () { openVote(b.dataset.v); }; });
      };
      el.querySelectorAll("#cv-rf button").forEach(function (b) { b.onclick = function () { filtRec = b.dataset.v; el.querySelectorAll("#cv-rf button").forEach(function (x) { x.classList.toggle("on", x === b); }); el.querySelector("#cv-rec").innerHTML = recHTML(); wire(); }; });
      el.querySelectorAll("[data-b]").forEach(function (b) { b.onclick = function () { openBill(b.dataset.b); }; });
      wire();
      wireWatch(el);
      if (isUS) money(key.slice(3), el.querySelector("#cv-money"), m.name);
      if (isUS && more2()) more2().memberExtras(el, m, key);
      if (more3() && m.cc === "GB" && el.querySelector("#cv-ukm")) more3().ukMoney(el.querySelector("#cv-ukm"), key);
      if (more3() && el.querySelector("#cv-said")) more3().saidInto(el.querySelector("#cv-said"), m.cc, key);
      if (after) after();
    });
  }

  /* ---------- a person from the directory (side panel next to the briefing) ---------- */
  function person(el, cc, name, title, since) {
    el.innerHTML = loading("Looking up " + name + " in the record…");
    api("/api/civic/person?cc=" + encodeURIComponent(cc) + "&name=" + encodeURIComponent(name) + "&title=" + encodeURIComponent(title || "")).then(function (d) {
      var head = '<div class="cv-kicker">' + flag(cc) + " " + esc((CCNAME[cc] || cc).toUpperCase()) + "</div><h2>" + esc(name) + '</h2><div class="cv-meta">' + esc(title || "") + (since ? " · " + esc(since) : "") + "</div>";
      var extra = "";
      if (d.confirm && d.confirm.length) extra += sec("SENATE CONFIRMATION", '<div class="cv-small">The Senate votes to approve the President\'s picks for cabinet jobs and other top posts.</div>' + d.confirm.map(function (v) {
        return '<button class="cv-row vote mini" data-v="' + esc(v.id) + '"><span class="cv-d">' + esc(fmtDate(v.date)) + '</span><span class="cv-t"><b>' + esc((v.title || "").replace(/^[^:]*:\s*/, "")) + "</b><i>" + esc([v.question, v.result].filter(Boolean).join(" · ")) + '</i></span><span class="cv-vr">' + tally(v) + "</span></button>";
      }).join(""));
      if (d.laws && d.laws.length) extra += sec("LAWS SIGNED (THIS CONGRESS) · " + d.laws.length, d.laws.map(function (b) {
        return '<button class="cv-row bill mini" data-b="' + esc(b.id) + '"><span class="cv-num">' + esc(b.num) + '</span><span class="cv-t"><b>' + esc(b.title) + "</b><i>" + esc(b.enacted || "") + '</i></span><span class="cv-d">' + esc(fmtDate(b.latest_date)) + "</span></button>";
      }).join(""));
      if (d.execs && d.execs.length) extra += sec((d.role === "president" ? "SIGNED AS PRESIDENT: ORDERS, PROCLAMATIONS, MEMOS" : "MAJOR RULES FROM THE " + esc((d.dept || "").toUpperCase())) + " · " + d.execs.length, d.execs.map(function (e) {
        return '<button class="cv-row exec mini" data-e="' + esc(e.id) + '"><span class="cv-d">' + esc(fmtDate(e.signed || e.date)) + '</span><span class="cv-t"><b>' + esc(e.title) + "</b><i>" + esc(e.kind + (e.number ? " " + e.number : "")) + "</i></span></button>";
      }).join(""));
      var wire = function () {
        el.querySelectorAll("[data-v]").forEach(function (x) { x.onclick = function () { openVote(x.dataset.v); }; });
        el.querySelectorAll("[data-b]").forEach(function (x) { x.onclick = function () { openBill(x.dataset.b); }; });
        el.querySelectorAll("[data-e]").forEach(function (x) { x.onclick = function () { openExec(x.dataset.e); }; });
      };
      if (d.member) {
        memberInto(el, d.member, extra ? '<div class="cv-side-extra">' + extra + "</div>" : "", wire);
        return;
      }
      if (d.justice && more2()) { el.innerHTML = loading(); more2().justiceInto(el, d.justice, ""); return; }
      var why = cc === "US" && !extra ? esc(name) + " isn't a member of Congress, so there's no voting record." : !d.in_record ? esc(CCNAME[cc] || "This country") + " doesn't publish how individual lawmakers vote, so there's no voting record to show."
        : (extra ? "" : esc(name) + " isn't a member of " + (cc === "US" ? "Congress" : "parliament") + ", so there's no voting record or sponsored bills. Ministers who also sit in parliament do have one; their record shows up here once their votes have reached Archie.");
      el.innerHTML = head + (why ? '<div class="cv-small cv-pad">' + why + "</div>" : "") + extra +
        (cc === "US" ? sec("CAMPAIGN MONEY AND DONATIONS", '<div id="cv-money"></div>') : "");
      wire();
      if (cc === "US") money({ name: name }, el.querySelector("#cv-money"), name);
    }).catch(function () { el.innerHTML = '<div class="cv-small">Couldn\'t look that up right now.</div>'; });
  }
  function sideHome(el, cc, cname) {
    var has = ["US", "GB", "EU", "CA", "IE", "FR", "DE", "ES", "PL", "BR", "CH", "FI", "DK", "NL", "EE", "SE", "NO", "IS", "IT", "LT", "UA", "CL", "CZ", "AU"].indexOf(cc) >= 0;
    el.innerHTML = '<div class="cv-kicker">QUICK RECORD</div><div class="cv-small">Click anyone in the briefing (the leaders, or anyone in the org chart) to see their record here: how they vote, the bills they sponsor, campaign money for US lawmakers, and what presidents sign.</div>' +
      (has ? '<div id="cv-sidev">' + loading() + "</div>" : '<div class="cv-small">' + esc(cname) + " doesn't publish how individual lawmakers vote, so Archie can't show voting records here.</div>");
    if (!has) return;
    api("/api/civic/votes?cc=" + cc).then(function (d) {
      var box = el.querySelector("#cv-sidev"); if (!box) return;
      var V = (d.votes || []).slice(0, 12);
      box.innerHTML = V.length ? sec("LATEST VOTES IN " + esc(cname.toUpperCase()), V.map(function (v) {
        return '<button class="cv-row vote side" data-v="' + esc(v.id) + '"><span class="cv-d">' + esc(fmtDate(v.date)) + '</span><span class="cv-t"><b>' + esc(v.title || v.question) + '</b></span><span class="cv-vr">' + tally(v) + "</span></button>";
      }).join("")) : '<div class="cv-small">No votes have reached Archie for ' + esc(cname) + " yet.</div>";
      box.querySelectorAll("[data-v]").forEach(function (x) { x.onclick = function () { openVote(x.dataset.v); }; });
    });
  }

  /* ---------- campaign money ---------- */
  function pie(slices, size) {
    var tot = slices.reduce(function (a, s) { return a + s.v; }, 0); if (!tot) return "";
    var r = size / 2, a0 = -Math.PI / 2, out = '<svg class="cv-pie" width="' + size + '" height="' + size + '" viewBox="0 0 ' + size + " " + size + '">';
    slices.forEach(function (s) {
      if (s.v <= 0) return;
      var a1 = a0 + 2 * Math.PI * s.v / tot, big = a1 - a0 > Math.PI ? 1 : 0;
      var p = s.v >= tot * 0.9999 ? '<circle cx="' + r + '" cy="' + r + '" r="' + (r - 1) + '" fill="' + s.c + '"/>' :
        '<path d="M' + r + "," + r + " L" + (r + (r - 1) * Math.cos(a0)) + "," + (r + (r - 1) * Math.sin(a0)) + " A" + (r - 1) + "," + (r - 1) + " 0 " + big + " 1 " + (r + (r - 1) * Math.cos(a1)) + "," + (r + (r - 1) * Math.sin(a1)) + ' Z" fill="' + s.c + '" stroke="#0b0e09" stroke-width="2"/>';
      out += '<g class="cv-sl"><title>' + esc(s.label + ": " + usd(s.v) + " (" + pct(s.v, tot) + ")") + "</title>" + p + "</g>";
      a0 = a1;
    });
    return out + "</svg>";
  }
  function legend(slices) {
    var tot = slices.reduce(function (a, s) { return a + s.v; }, 0);
    return '<div class="cv-leg">' + slices.filter(function (s) { return s.v > 0; }).map(function (s) {
      return '<div><i style="background:' + s.c + '"></i><span>' + esc(s.label) + (s.sub ? '<em>' + esc(s.sub) + "</em>" : "") + "</span><b>" + usd(s.v) + '</b><u>' + pct(s.v, tot) + "</u></div>";
    }).join("") + "</div>";
  }
  function money(who, box, personName) {
    // who: a bioguide id (member of Congress) or {name: "..."} for anyone else
    var url = typeof who === "string" ? "/api/civic/money?bio=" + encodeURIComponent(who) : "/api/civic/money?name=" + encodeURIComponent(who.name);
    personName = personName || (typeof who === "string" ? "" : who.name);
    box.innerHTML = '<div id="cv-camp">' + loading("Loading FEC filings…") + '</div><div class="cv-mh">THEIR OWN POLITICAL DONATIONS</div><div id="cv-don"></div>';
    var don = box.querySelector("#cv-don");
    api(url).then(function (d) {
      var campBox = box.querySelector("#cv-camp");
      personName = personName || d.name;
      if (d.error) { campBox.innerHTML = '<div class="cv-small">' + esc(d.error) + "</div>"; donations(personName, don, false); return; }
      var C = d.cycles || [];
      if (!C.length) {
        campBox.innerHTML = '<div class="cv-small">' + (d.not_candidate ? (d.loaded ? esc(personName) + " hasn't run for Congress or President in the last eight years, so there are no campaign funds to show. What they've given to campaigns themselves is below."
          : "The FEC's files haven't finished downloading yet (once a week, about 120 MB the first time). Campaign funding shows up here once they have.") : "The FEC's files haven't finished downloading yet (once a week, about 120 MB the first time).") + "</div>";
        donations(personName, don, !!(d.not_candidate && d.loaded));
        return;
      }
      donations(personName, don, false);
      if (!C[moneyCycle]) moneyCycle = 0;
      var draw = function () {
        var c = C[moneyCycle], s = c.sources;
        var srcSl = s ? [{ label: "Individual donors", v: s.individuals || 0, c: PIE[0], sub: "people giving directly (includes money bundled by groups, see below)" }, { label: "PACs and other committees", v: s.pacs || 0, c: PIE[1] },
          { label: "Party committees", v: s.party || 0, c: PIE[2] }, { label: "The candidate's own money", v: s.self || 0, c: PIE[3], sub: "contributions and loans" }, { label: "Other", v: s.other || 0, c: OTHER, sub: "interest, refunds, other receipts" }] : [];
        var D = c.donors || [], top = D.slice(0, 6), rest = D.slice(6).reduce(function (a, x) { return a + x.total; }, 0);
        var dSl = top.map(function (x, i) { return { label: nice(x.name), v: x.total, c: PIE[i], sub: x.earmarked ? usd(x.direct) + " given directly + " + usd(x.earmarked) + " collected from its members and passed on" : "" }; });
        if (rest > 0) dSl.push({ label: (D.length - 6) + " other groups", v: rest, c: OTHER });
        var O = c.outside || [];
        campBox.innerHTML = (C.length > 1 ? '<div class="cv-chips" id="cv-cyc">' + C.map(function (x, i) { return '<button data-i="' + i + '" class="' + (i === moneyCycle ? "on" : "") + '">' + (x.cycle - 1) + "–" + x.cycle + " election</button>"; }).join("") + "</div>" : "") +
          (c.receipts != null ? '<div class="gv-nums"><div class="gv-num"><div class="h">RAISED</div><div class="v">' + usd(c.receipts) + '</div></div><div class="gv-num"><div class="h">SPENT</div><div class="v">' + usd(c.spent) + '</div></div><div class="gv-num"><div class="h">CASH ON HAND</div><div class="v">' + usd(c.cash) + '</div></div><div class="gv-num"><div class="h">THROUGH</div><div class="v cv-sm">' + esc(c.through || "—") + "</div></div></div>" : "") +
          (srcSl.length ? '<div class="cv-mh">Where the money came from</div><div class="cv-pierow">' + pie(srcSl, 150) + legend(srcSl) + "</div>" : "") +
          (dSl.length ? '<div class="cv-mh">Biggest organized donors</div><div class="cv-small">PACs, unions, companies\' PACs and advocacy groups. Each total adds what the group gave itself to what it collected from its members and passed on as "earmarked" donations (bundling).</div><div class="cv-pierow">' + pie(dSl, 150) + legend(dSl) + "</div>" +
            (D.length > 6 ? '<details class="gv-sub"><summary>All ' + D.length + " groups</summary>" + '<table class="cv-ptab money"><tr><th>group</th><th>gave directly</th><th>passed on (bundled)</th><th>total</th></tr>' + D.map(function (x) { return "<tr><td>" + esc(nice(x.name)) + "</td><td>" + usd(x.direct) + "</td><td>" + (x.earmarked ? usd(x.earmarked) : "—") + "</td><td><b>" + usd(x.total) + "</b></td></tr>"; }).join("") + "</table></details>" : "") : "") +
          (O.length ? '<div class="cv-mh">Outside spending (super PACs and other groups, spent without the campaign)</div><table class="cv-ptab money"><tr><th>spender</th><th>to help them</th><th>to defeat them</th></tr>' + O.map(function (o) { return "<tr><td>" + esc(nice(o.name)) + "</td><td>" + (o["for"] ? usd(o["for"]) : "—") + "</td><td>" + (o.against ? usd(o.against) : "—") + "</td></tr>"; }).join("") + "</table>" : "") +
          '<div class="cv-mh">Where their individual donors work</div><div id="cv-emp"><button class="cv-btn" id="cv-empb">show top employers</button><span class="cv-small">like OpenSecrets\' top contributors; uses the FEC\'s live search</span></div>' +
          (d.matched && d.matched.length ? '<div class="cv-small">Matched in the FEC\'s candidate list: ' + d.matched.map(function (m) { return esc(m.fec_name) + " (" + esc(m.office + (m.state ? ", " + m.state : "")) + ")"; }).join("; ") + ".</div>" : "") +
          '<div class="cv-small">From the Federal Election Commission\'s public filings. Donations from individuals of $200 or less aren\'t itemized by the FEC, so they count toward "individual donors" without a name. Bundled (earmarked) totals cover ' +
          "a set of groups across the spectrum that bundle donations (AIPAC, J Street, Club for Growth, NORPAC, EMILY's List, the NRA, LCV and others); ActBlue and WinRed are left out because they carry everyone's donations. " +
          (d.key ? "" : "Bundled totals fill in a few groups an hour on the FEC's free demo key; a free personal key (api.data.gov) makes it much faster: add it in Lawmaking › data sources. ") + "</div>";
        campBox.querySelectorAll("#cv-cyc button").forEach(function (b) { b.onclick = function () { moneyCycle = +b.dataset.i; draw(); }; });
        var eb = campBox.querySelector("#cv-empb");
        if (eb) eb.onclick = function () { employers(c.cand_ids[0], c.cycle, campBox.querySelector("#cv-emp")); };
      };
      draw();
    });
  }
  function bars(rows, max) {
    return '<div class="cv-bars">' + rows.map(function (r) { return '<div><span>' + esc(r.label) + '</span><i><b style="width:' + Math.max(1, 100 * r.v / (max || 1)) + '%"></b></i><u>' + usd(r.v) + "</u></div>"; }).join("") + "</div>";
  }
  function employers(cand, cycle, el) {
    el.innerHTML = loading("Asking the FEC…");
    api("/api/civic/employers?cand=" + encodeURIComponent(cand) + "&cycle=" + cycle).then(function (d) {
      if (d.error) { el.innerHTML = '<div class="cv-small">' + esc(d.error) + "</div>"; return; }
      var E = d.employers || [];
      el.innerHTML = E.length ? bars(E.slice(0, 15).map(function (x) { return { label: nice(x.name), v: x.total }; }), E[0].total) +
        '<div class="cv-small">Donations of more than $200 from people who listed each employer (the employees gave, not the company). Retired, self-employed and not-employed donors (' + usd(d.skipped) + ") are left out.</div>" : '<div class="cv-small">No employer totals for that cycle.</div>';
    });
  }
  function donations(name, el, auto) {
    var run = function () {
      el.innerHTML = loading("Searching the FEC for donations by " + name + "…");
      api("/api/civic/donations?name=" + encodeURIComponent(name)).then(function (d) {
        if (d.error) { el.innerHTML = '<div class="cv-small">' + esc(d.error) + "</div>"; return; }
        if (!d.count) { el.innerHTML = '<div class="cv-small">No federal donations over $200 under the name ' + esc(d.searched) + " in " + (d.cycles[d.cycles.length - 1] - 1) + "–" + d.cycles[0] + ".</div>"; return; }
        var P = d.parties || {}, pc = { Republican: PIE[1], Democratic: PIE[0], "No party listed": OTHER };
        var pSl = Object.keys(P).sort(function (a, b) { return P[b] - P[a]; }).map(function (k) { return { label: "To " + (k === "No party listed" ? "groups with no party listed (PACs, causes)" : k + " committees and candidates"), v: P[k], c: pc[k] || OTHER }; });
        var T = d.to || [], top = T.slice(0, 6), rest = T.slice(6).reduce(function (a, x) { return a + x.amount; }, 0);
        var tSl = top.map(function (x, i) { return { label: nice(x.name), v: x.amount, c: PIE[i], sub: x.n + (x.n === 1 ? " donation" : " donations") }; });
        if (rest > 0) tSl.push({ label: (T.length - 6) + " others", v: rest, c: OTHER });
        el.innerHTML = '<div class="gv-nums"><div class="gv-num"><div class="h">GIVEN</div><div class="v">' + usd(d.total) + '</div></div><div class="gv-num"><div class="h">DONATIONS</div><div class="v">' + d.count + '</div></div><div class="gv-num"><div class="h">YEARS</div><div class="v cv-sm">' + (d.cycles[d.cycles.length - 1] - 1) + "–" + d.cycles[0] + "</div></div></div>" +
          '<div class="cv-mh">By party</div><div class="cv-pierow">' + pie(pSl, 130) + legend(pSl) + "</div>" +
          '<div class="cv-mh">Who they gave to</div><div class="cv-pierow">' + pie(tSl, 130) + legend(tSl) + "</div>" +
          '<div class="cv-small">From FEC filings: donations over $200 from anyone named ' + esc(d.searched) + (d.employers.length ? " (employers listed: " + esc(d.employers.map(nice).join(", ")) + ")" : "") +
          ". Someone else with the same name can show up here, so check the employers. Gifts through ActBlue and WinRed are counted where the money landed." + (d.partial ? " Some years couldn't be fetched this time." : "") + "</div>";
      });
    };
    if (auto) run(); else { el.innerHTML = '<button class="cv-btn">show what ' + esc(name) + ' has given to campaigns</button><span class="cv-small">uses the FEC\'s live search</span>'; el.querySelector(".cv-btn").onclick = run; }
  }

  function openExec(id) {
    var el = openDrawer(loading());
    api("/api/civic/exec?id=" + encodeURIComponent(id)).then(function (d) {
      var e = (d.items || [])[0];
      if (!e) { el.innerHTML = '<div class="cv-small">Not found.</div>'; return; }
      el.innerHTML = '<div class="cv-kicker">' + flag("US") + " UNITED STATES · " + esc(e.kind.toUpperCase()) + (e.number ? " " + esc(e.number) : "") + "</div><h2>" + esc(e.title) + "</h2>" +
        '<div class="cv-meta">' + [e.signed ? "signed " + esc(fmtDate(e.signed)) : "", "published " + esc(fmtDate(e.date)), esc(e.agency || "")].filter(Boolean).join(" · ") + "</div>" +
        (e.abstract ? sec("OFFICIAL SUMMARY", '<p class="cv-p">' + esc(e.abstract) + "</p>") : "") +
        sec("IN PLAIN ENGLISH", explainBtn("exec", e.id, "", "explain what this does")) +
        '<div class="cv-foot"><a href="' + esc(e.url) + '" target="_blank" rel="noopener">full text in the Federal Register ↗</a></div>';
      wireExplain(el);
    });
  }

  function sources() {
    api("/api/civic/overview").then(function (d) { ov = d; ov._at = Date.now(); sourcesDraw(); });
  }
  function sourcesDraw() {
    var st = ov.status || {}, keys = Object.keys(st).sort();
    var el = openDrawer('<div class="cv-kicker">LAWMAKING · DATA</div><h2>Where this comes from</h2>' +
      '<p class="cv-p">Everything here is the public record, downloaded to this PC so it works offline: official parliament data where it exists, and a few trusted open-data projects that republish it (HowTheyVote.eu for the European Parliament, openparliament.ca for Canada, abgeordnetenwatch.de for Germany, Open States for US state legislatures). Archie adds no ratings or scores.</p>' +
      (ov.working_on ? '<div class="cv-plain"><b>Working on now:</b> ' + esc(ov.working_on.job) + ' <em>started ' + ctx.ago(Math.max(0, Math.round((Date.now() / 1000 - ov.working_on.since) / 60))) + "</em></div>" : "") +
      sec("STATUS", keys.length ? '<table class="cv-ptab">' + keys.map(function (k) { var s = st[k]; return "<tr><td>" + esc(k) + '</td><td style="color:' + (s.ok ? "#9fd36a" : "#e9c46a") + '">' + (s.ok ? "ok" : "problem") + "</td><td>" + esc(s.note || "") + "</td><td>" + (s.at ? ctx.ago(Math.round((Date.now() / 1000 - s.at) / 60)) : "") + "</td></tr>"; }).join("") + "</table>" : '<div class="cv-small">Nothing has finished yet. Downloads begin about a minute after Archie starts, while online, one source at a time.</div>') +
      sec("OPTIONAL FREE KEYS", '<div class="cv-small">None of these are needed. A free FEC key (from api.data.gov, takes a minute by email) makes the bundled-donations totals fill in much faster than the shared demo key.</div>' +
        '<div class="cv-keyrow"><label>FEC / api.data.gov key</label><input id="cv-fec" placeholder="' + (ov.keys && ov.keys.fec ? "saved; paste a new one to replace it" : "paste your key") + '"><button class="cv-btn" id="cv-savekey">save</button></div><div class="cv-small" id="cv-keymsg"></div>'));
    if (more2()) more2().sourcesExtra(el, ov);
    if (more3()) more3().sourcesExtra(el, ov);
    el.querySelector("#cv-savekey").onclick = function () {
      var v = el.querySelector("#cv-fec").value.trim(); if (!v) return;
      api("/api/civic/settings", { fec_key: v }).then(function (d) { el.querySelector("#cv-keymsg").textContent = d.ok ? "Saved on this PC." : "Couldn't save."; ov.keys = { fec: d.fec_key }; });
    };
  }

  /* ---------- calendar ---------- */
  function parseElection(text) {   // Factbook phrasing -> a date when day and month are given
    var m = (text || "").match(/(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(20\d\d)/i);
    if (m) return new Date(m[2] + " " + m[1] + ", " + m[3] + " 12:00");
    m = (text || "").match(/(January|February|March|April|May|June|July|August|September|October|November|December)\s+(20\d\d)/i);
    if (m) return { month: m[1], year: +m[2] };
    return null;
  }
  function calendar(body, govs) {
    body.innerHTML = '<div class="cv-cal" id="cv-cal">' + loading("Loading the calendar…") + "</div>";
    api("/api/civic/calendar").then(function (d) {
      var isoOf = {}; (govs || []).forEach(function (c) { isoOf[c.name.toLowerCase()] = c.iso2; if (c.long) isoOf[c.long.toLowerCase()] = c.iso2; });
      var iso = function (w) { w = (w || "").toLowerCase(); return isoOf[w] || (w.indexOf("bosnia") >= 0 ? "BA" : w.indexOf("congo") >= 0 ? "CD" : ""); };
      var ev = (d.events || []).map(function (e) { return { date: e.date, time: e.time, title: e.title, kind: e.kind, body: e.body, url: e.url, cc: e.cc }; });
      var now = new Date(), soon = new Date(Date.now() + 400 * 86400000), monthOnly = [], have = {};
      (d.elections || []).forEach(function (e) {
        var cc = iso(e.where);
        ev.push({ date: e.date, title: e.title, kind: "Election", body: e.where, url: e.url, cc: cc || "" });
        if (cc) have[cc] = 1;
      });
      (govs || []).forEach(function (c) {   // the Factbook's schedule fills in countries the live calendar doesn't have yet
        if (have[c.iso2]) return;
        [["single", "national legislature"], ["lower", "lower house"], ["upper", "upper house"]].forEach(function (k) {
          var ch = c.leg && c.leg[k[0]]; if (!ch || !ch.next) return;
          var p = parseElection(ch.next);
          if (p instanceof Date && p > now && p < soon) ev.push({ date: p.toISOString().slice(0, 10), title: c.name + ": " + (ch.name || k[1]) + " election", kind: "Election", body: "date from the CIA World Factbook's last edition", cc: c.iso2 });
          else if (p && p.year && p.year <= soon.getFullYear() && (p.year > now.getFullYear() || (p.year === now.getFullYear() && new Date(p.month + " 1, 2000").getMonth() >= now.getMonth()))) monthOnly.push({ m: p.month + " " + p.year, t: c.name + ": " + (ch.name || k[1]), cc: c.iso2, y: p.year, mi: new Date(p.month + " 1, 2000").getMonth() });
        });
      });
      var days = {}; ev.forEach(function (e) { if (e.date) (days[e.date] = days[e.date] || []).push(e); });
      var keys = Object.keys(days).sort();
      monthOnly.sort(function (a, b) { return a.y - b.y || a.mi - b.mi; });
      var ccs = {}; ev.forEach(function (e) { ccs[e.cc || "?"] = 1; });
      var row = function (e) {
        return '<div class="cv-ev' + (e.kind === "Election" ? " elec" : "") + '">' + (e.cc ? flag(e.cc) : "<span></span>") + '<span class="cv-evt">' + esc(e.time || "") + '</span><div><b>' + esc(e.title) + "</b><i>" + esc([e.kind, e.body].filter(Boolean).join(" · ")) + "</i></div>" + (e.url ? '<a href="' + esc(e.url) + '" target="_blank" rel="noopener">↗</a>' : "") + "</div>";
      };
      var box = body.querySelector("#cv-cal");
      box.innerHTML = '<div class="cv-calhead"><h2>What\'s coming up</h2><div class="cv-small">National elections around the world, sitting days for the European Parliament and Poland\'s Sejm, US Senate committee hearings and House floor business, and the UK Parliament\'s full schedule. ' +
        "Most other parliaments don't publish their agendas in a form Archie can read. The US Congress is often away campaigning before an election, so its list can be short then.</div></div>" +
        (keys.length ? keys.map(function (k) {
          var L = days[k].slice().sort(function (a, b) { return (a.kind === "Election" ? 0 : 1) - (b.kind === "Election" ? 0 : 1) || (a.cc || "").localeCompare(b.cc || "") || (a.time || "").localeCompare(b.time || ""); });
          var by = {}; L.forEach(function (e) { (by[e.cc || "?"] = by[e.cc || "?"] || []).push(e); });
          var html = Object.keys(by).map(function (c) {
            var E = by[c];
            if (E.length <= 4) return E.map(row).join("");
            return E.slice(0, 3).map(row).join("") + '<details class="cv-more-ev"><summary>' + (c !== "?" ? flag(c) : "") + " " + (E.length - 3) + " more from " + esc(CCNAME[c] || (E[0].body || "").split(" · ")[0] || c) + "</summary>" + E.slice(3).map(row).join("") + "</details>";
          }).join("");
          return '<div class="cv-day"><div class="cv-dayh">' + esc(new Date(k + "T12:00:00").toLocaleDateString([], { weekday: "long", month: "long", day: "numeric", year: "numeric" })) + "</div>" + html + "</div>";
        }).join("") : '<div class="cv-small cv-pad">Nothing scheduled has reached Archie yet. It checks every few hours while online.</div>') +
        (monthOnly.length ? '<div class="cv-day"><div class="cv-dayh">Elections expected (month known, exact day not yet set)</div>' + monthOnly.slice(0, 60).map(function (e) { return '<div class="cv-ev elec">' + flag(e.cc) + '<span class="cv-evt">' + esc(e.m) + "</span><div><b>" + esc(e.t) + "</b></div></div>"; }).join("") + "</div>" : "");
    });
  }

  /* ---------- my representatives ---------- */
  function reps(body) {
    body.innerHTML = '<div class="cv-cal" id="cv-reps">' + loading() + "</div>";
    api("/api/civic/myreps").then(function (d) { drawReps(body.querySelector("#cv-reps"), d); });
  }
  function drawReps(box, d) {
    var h = d.home || {}, S = d.states || {};
    var form = '<div class="cv-repform"><div class="cv-small">Type your US street address and Archie asks the US Census Bureau which districts it\'s in. The address is used for that one lookup and isn\'t stored; only the district numbers are kept, on this PC.</div>' +
      '<div class="cv-keyrow"><input id="cv-addr" placeholder="street address, town, state ZIP"><button class="cv-btn" id="cv-find">find my representatives</button></div>' +
      '<details class="gv-sub"><summary>or pick your districts yourself</summary><div class="cv-keyrow"><select id="cv-st"><option value="">state…</option>' + Object.keys(S).map(function (k) { return '<option value="' + k + '"' + (h.state === k ? " selected" : "") + ">" + esc(S[k]) + "</option>"; }).join("") + "</select>" +
      '<input id="cv-cd" placeholder="US House district #" value="' + esc(h.cd || "") + '" size="8"><input id="cv-up" placeholder="state senate #" value="' + esc(h.upper || "") + '" size="8"><input id="cv-lo" placeholder="state house / assembly #" value="' + esc(h.lower || "") + '" size="10"><button class="cv-btn" id="cv-set">set</button></div></details><div class="cv-small" id="cv-msg"></div></div>';
    if (!h.state) { box.innerHTML = '<div class="cv-calhead"><h2>Your representatives</h2></div>' + form; wireReps(box); return; }
    var card = function (p, fed) {
      return '<div class="cv-rep' + (fed ? " fed" : " st") + '"' + (fed ? ' data-k="' + esc(p.key) + '"' : ' data-sn="' + esc(p.name) + '" data-sd="' + esc(p.district) + '" data-sc="' + esc(p.chamber) + '"') + '><div class="cv-rh">' + esc(fed ? p.office : (p.chamber === "upper" ? "State Senator" : "State Representative / Assembly Member") + ", district " + p.district) + "</div><b>" + esc(p.name) + '</b> <span class="cv-party">' + esc(p.party || "") + "</span>" +
        '<div class="cv-small">' + [p.phone ? esc(p.phone) : "", p.email ? '<a href="mailto:' + esc(p.email) + '">' + esc(p.email) + "</a>" : "", p.url ? '<a href="' + esc(p.url) + '" target="_blank" rel="noopener">website ↗</a>' : "", fed && p.term_end ? "term ends " + esc(fmtDate(p.term_end)) : ""].filter(Boolean).join(" · ") + "</div>" +
        '<div class="cv-go">' + (fed ? "their votes and campaign money ›" : "their votes in the state capitol ›") + "</div></div>";
    };
    box.innerHTML = '<div class="cv-calhead"><h2>Your representatives</h2><div class="cv-small">' + esc(d.state_name) + (h.cd ? " · US House district " + esc(h.cd) : "") + (h.upper ? " · state senate district " + esc(h.upper) : "") + (h.lower ? " · state house/assembly district " + esc(h.lower) : "") + (d.matched ? " · matched: " + esc(d.matched) : "") + "</div></div>" +
      '<div class="cv-mh">IN WASHINGTON</div><div class="cv-reps">' + ((d.federal || []).map(function (p) { return card(p, true); }).join("") || '<div class="cv-small">No match in the list of current members.</div>') + "</div>" +
      '<div class="cv-mh">IN YOUR STATE CAPITAL</div><div class="cv-reps">' + ((d.state || []).map(function (p) { return card(p, false); }).join("") || '<div class="cv-small">No state legislators matched those district numbers.</div>') + "</div>" +
      '<div id="cv-statev"></div><div class="cv-small">State legislators and how they vote: Open States (a free, nonpartisan project that collects every state\'s records). Click either one for their votes.</div>' +
      '<details class="gv-sub"><summary>change address or districts</summary>' + form + "</details>";
    box.querySelectorAll(".cv-rep.fed").forEach(function (c) { c.onclick = function () { openMember(c.dataset.k); }; });
    box.querySelectorAll(".cv-rep.st").forEach(function (c) {
      c.onclick = function (e) {
        if (e.target.closest("a")) return;
        var el = openDrawer(loading("Looking up their votes…"));
        api("/api/civic/state_member?state=" + encodeURIComponent(h.state) + "&name=" + encodeURIComponent(c.dataset.sn)).then(function (r) {
          if (r.key) { memberInto(el, r.key); return; }
          el.innerHTML = '<div class="cv-kicker">' + esc((d.state_name || h.state).toUpperCase()) + " · STATE LAWMAKER</div><h2>" + esc(c.dataset.sn) + '</h2><div class="cv-meta">' + esc((c.dataset.sc === "upper" ? "State Senator" : "State Representative / Assembly Member") + ", district " + c.dataset.sd) + "</div>" +
            '<div class="cv-small cv-pad">' + (ov && ov.keys && ov.keys.openstates ? "None of their recorded votes have reached Archie yet. Archie downloads your state's votes from Open States every few hours while online; once one of their votes is in, their full record shows here." :
              "Their voting record comes from Open States, which needs a free key: sign up at open.pluralpolicy.com, copy the API key from your profile, and paste it under Lawmaking › data sources and status.") + "</div>";
        });
      };
    });
    if (more3() && box.querySelector("#cv-statev")) more3().stateVotes(box.querySelector("#cv-statev"));
    wireReps(box);
  }
  function wireReps(box) {
    var msg = box.querySelector("#cv-msg");
    var find = box.querySelector("#cv-find");
    if (find) find.onclick = function () {
      var a = box.querySelector("#cv-addr").value.trim(); if (!a) return;
      msg.textContent = "Asking the Census Bureau…";
      api("/api/civic/myreps", { address: a }).then(function (d) { if (d.error) { msg.textContent = d.error; return; } drawReps(box, d); });
    };
    var set = box.querySelector("#cv-set");
    if (set) set.onclick = function () {
      var st = box.querySelector("#cv-st").value; if (!st) { msg.textContent = "Pick a state first."; return; }
      api("/api/civic/myreps", { state: st, cd: box.querySelector("#cv-cd").value.trim(), upper: box.querySelector("#cv-up").value.trim(), lower: box.querySelector("#cv-lo").value.trim() }).then(function (d) { drawReps(box, d); });
    };
  }

  function ensure(gvroot, cb) {
    root = gvroot;
    if (!drawer) { drawer = document.createElement("div"); drawer.className = "cv-drawer"; drawer.hidden = true; gvroot.appendChild(drawer); }
    if (ov) return cb();
    api("/api/civic/overview").then(function (d) { ov = d; ov._at = Date.now(); (ov.countries || []).forEach(function (c) { CCNAME[c.cc] = c.name; }); cb(); }).catch(cb);
  }
  return { render: render, open: openThing,
           memberInto: function (gvroot, el, key) { ensure(gvroot, function () { el.innerHTML = loading(); memberInto(el, key); }); },
           find: function (q) { return api("/api/civic/find?q=" + encodeURIComponent(q)); },
           person: function (gvroot, el, cc, name, title, since) { ensure(gvroot, function () { person(el, cc, name, title, since); }); },
           sideHome: function (gvroot, el, cc, cname) { ensure(gvroot, function () { CCNAME[cc] = CCNAME[cc] || cname; sideHome(el, cc, cname); }); }, has: function (iso) { return !!(ov && (ov.countries || []).some(function (c) { return c.cc === iso; })); },
           justices: function () { return api("/api/civic/scotus"); },
           countries: function () { return ["US", "GB", "EU", "CA", "IE", "FR", "DE", "ES", "PL", "BR", "CH", "FI", "DK", "NL", "EE", "SE", "NO", "IS", "IT", "LT", "UA", "CL", "CZ", "AU"]; } };
};
