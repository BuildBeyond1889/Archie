/* Archie World: governments. Two screens: a country directory with a full briefing, and a world map.
   How each country is set up comes from the CIA World Factbook's final edition (bundled, data/govs.json);
   who holds office now comes from Wikidata (checked daily); economy numbers from the World Bank (weekly). */
window.ArchieGov = function (ctx) {
  "use strict";
  var $ = ctx.$, esc = ctx.esc, api = ctx.api;
  var CAT = {
    pres: ["presidential republic", "#4fa3ff", "Voters choose a president who both leads the country and runs the government. Parliament can't remove the president except by impeachment, and the president can't dissolve parliament."],
    parl: ["parliamentary republic", "#7ad9b0", "Voters elect a parliament. The leader who can win a majority there becomes prime minister and runs the government, and parliament can vote them out. The president, where there is one, is mostly a ceremonial head of state."],
    semi: ["semi-presidential republic", "#b38cff", "Power is split. An elected president handles the big picture (often foreign policy and defense), while a prime minister who answers to parliament runs day-to-day government."],
    cmon: ["constitutional monarchy", "#e9c46a", "A king, queen or emperor is head of state, with a mostly ceremonial role set by the constitution. An elected parliament and a prime minister run the government."],
    amon: ["monarchy where the monarch governs", "#ff9f43", "The monarch (or ruling family) holds real power: they make the key decisions and appoint the government. National elections don't decide who rules."],
    one: ["one-party state", "#ff5d5d", "The constitution gives one party the leading role. Its leaders hold the top state jobs, and other parties can't compete for power."],
    theo: ["theocracy", "#e07ab8", "Religious leaders hold the highest authority. Any elected bodies work under them."],
    dir: ["directorial republic", "#5fd0d8", "A seven-member council runs the government together; the presidency rotates every year and is mostly a chairing role."],
    supra: ["union of countries", "#d6e2ff", "Not a country: 27 member states pool some of their powers (trade, a single market, a shared currency for most) in shared institutions."],
    mil: ["military or transitional government", "#9a9a9a", "The normal constitution isn't fully in force. A military or temporary government is in charge, usually promising a new constitution or elections."]
  };
  var BIG = ["US", "CN", "RU", "EU", "IN", "GB", "JP", "DE", "FR", "BR"];
  var GLOSS = {
    "bicameral": "two chambers (like a House and a Senate) that both have to pass laws",
    "unicameral": "a single chamber",
    "plurality/majority": "in each district, whoever gets the most votes wins the seat",
    "proportional representation": "seats are shared out by each party's share of the national vote",
    "mixed system": "some seats are won district by district, the rest are shared out by party vote",
    "full renewal": "every seat is up at each election",
    "partial renewal": "only some seats are up at each election (terms are staggered)",
    "Commonwealth realm": "a country that shares the British monarch as its own head of state",
    "absolute majority": "more than half of all votes",
    "chief of state": "the head of state: represents the country, signs laws, and in some systems holds real power",
    "head of government": "the person who actually runs the government day to day",
    "impeach": "to formally charge an official so they can be removed",
    "suffrage": "who is allowed to vote"
  };
  var holdSide = false, root = null, data = null, live = null, byIso = {}, sel = null, screen = "list", filter = "all", q = "", mapMode = "now", hoverEl = null, civic = null, civOpt = {};
  var LAW = ["US", "GB", "EU", "CA", "IE", "FR", "DE", "ES", "PL", "BR", "CH", "FI", "DK", "NL", "EE", "SE", "NO", "IS", "IT", "LT", "UA", "CL", "CZ", "AU"];   // countries with a public voting record in Archie
  function civ() { if (!civic && window.ArchieCivic) civic = window.ArchieCivic(ctx); return civic; }

  /* ---------- small helpers ---------- */
  function gloss(t) {
    t = esc(t || "");
    Object.keys(GLOSS).forEach(function (k) {
      var re = new RegExp("\\b(" + k.replace(/[\/]/g, "\\/") + ")\\b", "i");
      t = t.replace(re, '<abbr title="' + esc(GLOSS[k]) + '">$1</abbr>');
    });
    return t;
  }
  function flag(c, big) {
    return '<img class="gv-flag' + (big ? " big" : "") + '" src="/web/flags/' + c.iso2 + '.svg" alt="" title="' + esc(c.name) + '" onerror="this.outerHTML=\'<span class=&quot;gv-flag none' + (big ? " big" : "") + '&quot;>' + esc(c.iso2) + '</span>\'">';
  }
  function day(d) { return /^\d{4}-\d\d-\d\d$/.test(d) ? new Date(d + "T12:00:00") : new Date(d); }
  function yearsSince(d) { if (!d) return null; var t = day(d).getTime(); if (isNaN(t)) return null; return (Date.now() - t) / (365.25 * 86400000); }
  function fmtSince(d) { if (!d) return ""; var t = day(d); if (isNaN(t)) return ""; var y = yearsSince(d); return "since " + t.toLocaleDateString([], { month: "short", day: "numeric", year: "numeric" }) + (y != null ? " · " + (y < 1 ? Math.max(1, Math.round(y * 12)) + " months" : y.toFixed(y < 10 ? 1 : 0) + " years") : ""); }
  function money(v) { if (v == null) return "—"; var a = Math.abs(v); return (a >= 1e12 ? (v / 1e12).toFixed(2) + " trillion" : a >= 1e9 ? (v / 1e9).toFixed(1) + " billion" : a >= 1e6 ? (v / 1e6).toFixed(0) + " million" : Math.round(v).toLocaleString()); }
  function catOf(c) { return c.status && c.status.length && c.cat !== "supra" ? "mil" : c.cat; }
  function people(c) {   // live names first (Wikidata), the Factbook's as a fallback
    var L = live && live.live && live.live[c.iso2];
    var fb = function (t) {
      if (!t) return null;
      var m = t.match(/^(.*?)\s*\(since ([^)]+)\)/), raw = (m ? m[1] : t.split(/;|\n/)[0]).trim(), nm = splitName(raw);
      return { name: nm[1], office: nm[0], since: m ? m[2] : "", src: "fb" };
    };
    var okName = function (x) { return x && x.name && !/^Q\d+$/.test(x.name); };
    if (L) { L = Object.assign({}, L, { hos: (L.hos || []).filter(okName), hog: (L.hog || []).filter(okName) }); }
    var hos = L && L.hos && L.hos.length ? L.hos.map(function (x) { return { name: x.name, since: x.since, src: "wd" }; }) : [fb(c.exec.cos)].filter(Boolean);
    var hog = L && L.hog && L.hog.length ? L.hog.map(function (x) { return { name: x.name, since: x.since, src: "wd" }; }) : [fb(c.exec.hog)].filter(Boolean);
    return { hos: hos, hog: hog, hosOffice: (L && L.hosOffice) || (hos[0] && hos[0].office) || "", hogOffice: (L && L.hogOffice) || (hog[0] && hog[0].office) || "" };
  }
  var TITLE = /^(president|prime|minister|king|queen|chairman|chairperson|chancellor|emperor|sultan|amir|emir|supreme|leader|governor-general|general|gen\.|col\.|capt\.|lt\.|maj\.|sr\.|interim|acting|transitional|transition|pope|grand|duke|prince|princess|head|state|council|federal|taoiseach|premier|sheikh|shaykh|crown|of|the|and|sir|dr\.|mr\.|mrs\.|ms\.|vice|first|deputy|co-prince|captain|captains|regent|regents|commander-in-chief|overall|taliban|sovereign|presidential|leadership|affairs|commission|cabinet|ministers|national)$/i;
  function splitName(raw) {   // "President Donald J. TRUMP" -> ["President", "Donald J. Trump"]; "President XI Jinping" -> ["President", "Xi Jinping"]
    var w = raw.split(/\s+/), ci = -1, CONN = /^(da|de|dos|das|do|van|von|der|bin|bint|al|el|la|le|du|di|del|y|ibn|ben)$/;
    var isCaps = function (x) { return /^[A-Z][A-Z'\-]+,?$/.test(x) || /-[A-Z]{2,},?$/.test(x); };
    for (var i = 0; i < w.length; i++) if (isCaps(w[i])) { ci = i; break; }
    if (ci < 0) return ["", raw];
    var st = ci; while (st > 0 && /^[A-Z]/.test(w[st - 1]) && !TITLE.test(w[st - 1])) st--;
    var en = ci + 1; while (en < w.length && ((/^[A-Z]/.test(w[en]) && !TITLE.test(w[en])) || /^(al|el|ad|as|an|bin|ibn)-[A-Z]/.test(w[en]) || (CONN.test(w[en]) && en + 1 < w.length && /^[A-Z]/.test(w[en + 1])))) en++;
    var tc = function (x) {
      if (/^[IVX]+$/.test(x) && x.length > 1 && x !== "XI") return x;
      return x.split("-").map(function (part) { return /^[A-Z][A-Z']+,?$/.test(part) ? part.charAt(0) + part.slice(1).toLowerCase() : part; }).join("-");
    };
    return [w.slice(0, st).join(" "), w.slice(st, en).map(tc).join(" ")];
  }
  function samePerson(p) { return p.hos[0] && p.hog[0] && (p.hos[0].name === p.hog[0].name || (p.hog[0].name || "").indexOf(p.hos[0].name) >= 0); }
  function nextVote(c) {
    var t = [c.leg.lower && c.leg.lower.next, c.leg.upper && c.leg.upper.next, c.leg.single && c.leg.single.next].filter(Boolean)
      .concat((c.exec.process + " " + c.exec.note).match(/next to be held[^;.)]*/gi) || []);
    var best = null;
    t.forEach(function (s) { var y = (s.match(/20\d\d/) || [])[0]; if (y && +y >= new Date().getFullYear() && (!best || y < best.y)) best = { y: y, text: s.replace(/^next to be held (in|on)?\s*/i, "") }; });
    return best;
  }
  function seats(text) {   // "Republican Party (220); Democratic Party (215)" -> [[party, n], ...]
    var out = [];
    (text || "").split(/;|\n/).forEach(function (p) { var m = p.match(/^\s*([^()]+?)\s*\((\d+)\)\s*$/); if (m) out.push([m[1], +m[2]]); });
    return out;
  }
  var PCOL = ["#4fa3ff", "#ff6b6b", "#7ad9b0", "#e9c46a", "#b38cff", "#ff9f43", "#5fd0d8", "#e07ab8", "#9fe7c4", "#c9cfe8"];
  var OFFICE = [
    [/foreign|external affairs|secretary of state$|international relations/i, "relations with other countries: embassies, treaties, visas", "sec"],
    [/defen[cs]e|war\b|armed forces|military/i, "the armed forces", "sec"],
    [/secretary of the interior/i, "federal lands, national parks, and Native American affairs", "home"],
    [/interior|home affairs|home secretary|homeland|internal affairs|public security/i, "police, borders and internal security", "sec"],
    [/justice|attorney general|legal affairs/i, "the courts system, prosecutors and law enforcement policy", "sec"],
    [/intelligence|cia\b|security service/i, "spy agencies and secret intelligence", "sec"],
    [/veteran/i, "care and benefits for former soldiers", "sec"],
    [/finance|treasury|exchequer|economy|economic|budget|revenue|tax/i, "the government's money: taxes, spending and debt", "eco"],
    [/trade|commerce|industry|business/i, "business, industry and trade deals", "eco"],
    [/labou?r|employment|work\b/i, "jobs, workplaces and workers' rights", "eco"],
    [/agricultur|farm|fisher|food/i, "farming, fishing and food supply", "eco"],
    [/energy|oil|petroleum|mines|mining/i, "power, fuel and natural resources", "eco"],
    [/health|human services/i, "hospitals, public health and medicines", "home"],
    [/education|schools|universit/i, "schools and universities", "home"],
    [/housing|urban/i, "housing and cities", "home"],
    [/transport/i, "roads, rail, airports and shipping", "home"],
    [/environment|climate|water|forest|natural resources|ecology/i, "nature, pollution and climate", "home"],
    [/culture|sport|tourism|heritage|arts/i, "culture, sport and tourism", "home"],
    [/social|welfare|family|women|children|pension/i, "welfare, pensions and family support", "home"],
    [/digital|telecom|communication|information|science|technology|research/i, "technology, science and communications", "home"]
  ];
  function officeInfo(o) { for (var i = 0; i < OFFICE.length; i++) if (OFFICE[i][0].test(o)) return OFFICE[i]; return [null, "", "other"]; }

  /* ---------- build ---------- */
  function open(iso) {
    if (!root) make();
    root.hidden = false; document.body.classList.add("gov-open");
    var go = function () {
      // "law:US", "law:US:bill:ID", "law:US:member:US:X", "cal", "reps", or a country
      var m = (iso || "").match(/^(law|cal|reps|elec|local)(?::([A-Z]{2})(?=:|$))?(?::(.+))?$/);
      if (m) { screen = m[1]; civOpt = { cc: m[2] || "", open: m[3] || "" }; render(); return; }
      if (iso) { var c = byIso[iso.toUpperCase()] || data.find(function (x) { return ctx.slug(x.name) === ctx.slug(iso); }); if (c) { sel = c; screen = "list"; } }
      render();
    };
    if (data) go(); else load().then(go);
  }
  function close() { if (root) root.hidden = true; document.body.classList.remove("gov-open"); }
  function load() {
    return Promise.all([fetch("/web/data/govs.json").then(function (r) { return r.json(); }), api("/api/govs").catch(function () { return {}; })]).then(function (r) {
      data = r[0].sort(function (a, b) { return a.name.localeCompare(b.name); }); live = r[1] || {};
      data.forEach(function (c) { byIso[c.iso2] = c; });
      if (!sel) sel = byIso.US;
    });
  }
  function make() {
    root = document.createElement("div"); root.className = "gov"; root.hidden = true;
    root.innerHTML = '<div class="gv-bar"><b>GOVERNMENTS</b><div class="gv-tabs"><button data-s="list">directory</button><button data-s="map">map</button><button data-s="law">lawmaking</button><button data-s="cal">calendar</button><button data-s="elec">elections</button><button data-s="local">local</button><button data-s="reps">my reps</button></div>' +
      '<input id="gv-q" placeholder="find a country, leader or lawmaker…" autocomplete="off"><span class="gv-src">the public record: official sources, no ratings</span><button class="gv-x" title="close">✕</button></div>' +
      '<div class="gv-body"></div><div class="gv-tip" hidden></div>';
    document.body.appendChild(root);
    root.querySelector(".gv-x").onclick = close;
    root.querySelectorAll(".gv-bar .gv-tabs button").forEach(function (b) { b.onclick = function () { screen = b.dataset.s; civOpt = {}; render(); }; });
    $("gv-q").oninput = function () { q = this.value.trim().toLowerCase(); if (screen !== "list") screen = "list"; render(true); };
    document.addEventListener("keydown", function (e) { if (!root.hidden && e.key === "Escape" && !document.activeElement.matches("input, select") && !(root.querySelector(".cv-drawer") && !root.querySelector(".cv-drawer").hidden)) close(); });
  }
  function render(keepBrief) {
    root.querySelectorAll(".gv-bar .gv-tabs button").forEach(function (b) { b.classList.toggle("on", b.dataset.s === screen); });
    var body = root.querySelector(".gv-body");
    $("gv-q").style.display = screen === "list" || screen === "map" ? "" : "none";
    var dr = root.querySelector(".cv-drawer"); if (dr && !civOpt.open) dr.hidden = true;
    if (screen === "law" || screen === "cal" || screen === "reps" || screen === "elec" || screen === "local") {
      if (!civ()) { body.innerHTML = '<div class="gv-none">The lawmaking screens didn\'t load.</div>'; return; }
      civ().render(body, screen, Object.assign({ govs: data }, civOpt), root); civOpt = {}; return;
    }
    if (screen === "map") { body.innerHTML = '<div class="gv-map" id="gv-map"></div>'; drawMap(); return; }
    if (!body.querySelector(".gv-list") || !keepBrief) body.innerHTML = '<div class="gv-left"><div class="gv-chips"></div><div class="gv-big"></div><div class="gv-list"></div></div><div class="gv-brief" id="gv-brief"></div><div class="gv-side" id="gv-side"></div>';
    listPane(); if (!keepBrief) brief(sel);
  }

  /* ---------- directory ---------- */
  function listPane() {
    var counts = {}; data.forEach(function (c) { var k = catOf(c); counts[k] = (counts[k] || 0) + 1; });
    var ch = root.querySelector(".gv-chips");
    ch.innerHTML = '<button data-f="all" class="' + (filter === "all" ? "on" : "") + '">all · ' + data.length + "</button>" + Object.keys(CAT).filter(function (k) { return counts[k]; }).map(function (k) {
      return '<button data-f="' + k + '" class="' + (filter === k ? "on" : "") + '"><i style="background:' + CAT[k][1] + '"></i>' + esc(CAT[k][0]) + " · " + counts[k] + "</button>";
    }).join("");
    ch.querySelectorAll("button").forEach(function (b) { b.onclick = function () { filter = b.dataset.f; listPane(); }; });
    root.querySelector(".gv-big").innerHTML = "<span>BIG PLAYERS</span>" + BIG.map(function (i) { var c = byIso[i]; return c ? '<button data-i="' + i + '" title="' + esc(c.name) + '">' + flag(c) + "</button>" : ""; }).join("");
    root.querySelectorAll(".gv-big button").forEach(function (b) { b.onclick = function () { pick(byIso[b.dataset.i]); }; });
    var L = data.filter(function (c) {
      if (filter !== "all" && catOf(c) !== filter) return false;
      if (!q) return true;
      var p = people(c), hay = (c.name + " " + c.long + " " + c.capital + " " + p.hos.concat(p.hog).map(function (x) { return x.name; }).join(" ")).toLowerCase();
      return hay.indexOf(q) >= 0;
    });
    var list = root.querySelector(".gv-list");
    list.innerHTML = L.map(function (c) {
      var p = people(c), lead = p.hog[0] || p.hos[0];
      return '<button class="gv-row' + (sel === c ? " on" : "") + '" data-i="' + c.iso2 + '">' + flag(c) + "<b>" + esc(c.name) + '</b><i><em style="color:' + CAT[catOf(c)][1] + '">' + esc(CAT[catOf(c)][0]) + "</em>" + (lead ? " · " + esc(lead.name) : "") + "</i></button>";
    }).join("") || '<div class="gv-none">Nothing matches "' + esc(q) + '".</div>';
    list.querySelectorAll(".gv-row[data-i]").forEach(function (b) { b.onclick = function () { pick(byIso[b.dataset.i]); }; });
    if (q.length >= 3 && civ()) {      // lawmakers by name, from every parliament with a voting record
      var asked = q;
      civ().find(q).then(function (d) {
        if (asked !== q) return;
        var P = (d && d.people) || []; if (!P.length) return;
        var h = '<div class="gv-lawh">LAWMAKERS</div>' + P.map(function (p) {
          var c = byIso[p.cc];
          return '<button class="gv-row law" data-k="' + esc(p.key) + '" data-c="' + esc(p.cc) + '">' + (c ? flag(c) : '<span class="gv-flag none">' + esc(p.cc) + "</span>") + "<b>" + esc(p.name) + "</b><i>" + esc([p.party, p.area].filter(Boolean).join(" · ")) + "</i></button>";
        }).join("");
        if (list.querySelector(".gv-none")) list.innerHTML = "";
        list.insertAdjacentHTML("beforeend", h);
        list.querySelectorAll(".gv-row.law").forEach(function (b) { b.onclick = function () {
          var c = byIso[b.dataset.c]; if (c) { sel = c; screen = "list"; holdSide = true; render(true); brief(c); holdSide = false; }
          var sd = $("gv-side"); if (sd) { civ().memberInto(root, sd, b.dataset.k); sd.scrollTop = 0; }
        }; });
      });
    }
  }
  function pick(c) { if (!c) return; sel = c; screen = "list"; render(); var r = root.querySelector('.gv-row[data-i="' + c.iso2 + '"]'); if (r) r.scrollIntoView({ block: "nearest" }); }

  function sec(n, title, plain, body, open) {
    return '<details class="gv-sec"' + (open ? " open" : "") + "><summary><span class=\"gv-n\">" + n + "</span>" + esc(title) + "</summary>" + (plain ? '<div class="gv-plain"><b>In plain terms:</b> ' + plain + "</div>" : "") + body + "</details>";
  }
  function kv(rows) { return '<dl class="gv-kv">' + rows.filter(function (r) { return r[1]; }).map(function (r) { return "<dt>" + esc(r[0]) + "</dt><dd>" + (r[2] ? r[1] : gloss(r[1])) + "</dd>"; }).join("") + "</dl>"; }
  function chamberHTML(ch, label) {
    if (!ch || !ch.name) return "";
    var S = seats(ch.parties), tot = S.reduce(function (a, s) { return a + s[1]; }, 0), seatsN = parseInt(ch.seats, 10) || tot;
    var used = {}, colOf = function (name, i) {
      var c = window.archiePartyColor ? window.archiePartyColor(name) : null;
      if (c && !used[c]) { used[c] = 1; return c; }
      for (var k = 0; k < PCOL.length; k++) { var x = PCOL[(i + k) % PCOL.length]; if (!used[x]) { used[x] = 1; return x; } }
      return PCOL[i % PCOL.length];
    };
    var SC = S.map(function (s, i) { return colOf(s[0], i); });
    var bar = S.length ? '<div class="gv-seat">' + S.map(function (s, i) { return '<i style="width:' + (100 * s[1] / Math.max(seatsN, tot)) + "%;background:" + SC[i] + '" title="' + esc(s[0] + ": " + s[1]) + '"></i>'; }).join("") + '<b style="left:50%"></b></div>' +
      '<div class="gv-seatkey">' + S.map(function (s, i) { return '<span><i style="background:' + SC[i] + '"></i>' + esc(s[0]) + " " + s[1] + "</span>"; }).join("") + "</div>" +
      (seatsN && tot < seatsN * 0.9 ? '<div class="gv-small">Seat counts above are for the seats up at the last election (' + tot + " of " + seatsN + ").</div>" : "") : "";
    return '<div class="gv-ch"><div class="gv-chh">' + esc(label ? label + ": " : "") + esc(ch.name) + "</div>" + bar +
      kv([["Seats", ch.seats], ["How they're elected", ch.system], ["Term", ch.term], ["Each election", ch.scope], ["Last election", ch.last], ["Next election", ch.next], ["Women", ch.women]]) + "</div>";
  }
  function brief(c) {
    var el = $("gv-brief"); if (!el || !c) return;
    var k = catOf(c), p = people(c), nv = nextVote(c), wb = (live && live.wb && live.wb[c.iso2]) || {}, trans = c.status && c.status.length;
    var leader = p.hog[0] || p.hos[0], both = samePerson(p);
    var wbv = function (key, f) { var v = wb[key]; return v ? f(v[0]) + ' <span class="gv-yr">' + v[1] + "</span>" : null; };
    // bottom line
    var bl = [];
    if (c.cat === "supra") bl.push("The EU is a union of 27 countries, not a country. Laws are proposed by the European Commission and passed by the elected European Parliament together with the Council of member-state ministers.");
    else {
      bl.push("<b>Who's in charge:</b> " + (leader ? esc(leader.name) + " " + (both ? "is both head of state and head of government" : "runs the government" + (p.hos[0] && p.hos[0] !== leader ? "; " + esc(p.hos[0].name) + " is head of state" : "")) : "not recorded") + ".");
      bl.push("<b>" + (trans ? "How it's meant to work (on paper):" : "How the system works:") + "</b> " + esc(CAT[c.cat] ? CAT[c.cat][2] : ""));
      if (trans) {
        var tn = (c.exec.note || c.label).replace(/^note( \d)?:\s*/i, "").split(/\n/)[0];
        if (tn.length > 320) tn = tn.slice(0, 320).replace(/[;,]?\s+\S*$/, "") + "…";
        bl.push("<b>Right now:</b> the normal setup isn't fully running. " + esc(tn.charAt(0).toUpperCase() + tn.slice(1)));
      }
      bl.push("<b>Next national vote:</b> " + (nv ? esc(nv.text) : "none scheduled in the Factbook's last edition") + ".");
    }
    var cab = '<div id="gv-cab"><div class="gv-small">Loading the administration…</div></div>';
    var news = (ctx.news ? ctx.news(c) : []).slice(0, 8);
    var econ = [["Economy (GDP)", wbv("gdp", function (v) { return "$" + money(v); }), 1], ["Per person", wbv("percap", function (v) { return "$" + Math.round(v).toLocaleString(); }), 1],
      ["Growth", wbv("growth", function (v) { return v.toFixed(1) + "%"; }), 1], ["Inflation", wbv("inflation", function (v) { return v.toFixed(1) + "%"; }), 1],
      ["Unemployment", wbv("unemp", function (v) { return v.toFixed(1) + "%"; }), 1], ["Government debt", wbv("debt", function (v) { return v.toFixed(0) + "% of GDP"; }), 1],
      ["Trade", wbv("trade", function (v) { return v.toFixed(0) + "% of GDP"; }), 1], ["Population", wbv("pop", function (v) { return money(v); }), 1]].filter(function (r) { return r[1]; });
    var orgs = (c.orgs || "").split(/,\s*/).filter(Boolean), KEY = /^(UN|NATO|EU|G-7|G-20|BRICS|ASEAN|AU|OPEC|SCO|C|OAS|Arab League|GCC|CSTO|EAEU|OECD|WTO|IMF)$/;
    var who = '<div class="gv-who">' + [["HEAD OF STATE", p.hos, p.hosOffice], ["HEAD OF GOVERNMENT", p.hog, p.hogOffice]].map(function (r) {
      return '<div class="gv-tile"><div class="h">' + r[0] + (r[2] && r[2].toLowerCase() !== r[0].toLowerCase() ? " · " + esc(r[2]) : "") + "</div>" + (r[1].length ? r[1].map(function (x) { return '<div class="n" data-pn="' + esc(x.name) + '" data-pt="' + esc(r[2] || r[0].toLowerCase()) + '" data-ps="' + esc(x.since || "") + '" title="see their record">' + esc(x.name) + '</div><div class="s">' + esc(fmtSince(x.since) || (x.since ? "since " + x.since : "")) + "</div>"; }).join("") : '<div class="n">—</div>') + "</div>";
    }).join("") + "</div>";
    el.innerHTML =
      '<div class="gv-head">' + flag(c, true) + '<div><div class="gv-class">COUNTRY BRIEFING · ' + new Date().toLocaleDateString([], { day: "numeric", month: "short", year: "numeric" }).toUpperCase() + "</div><h1>" + esc(c.name) + '</h1><div class="gv-long">' + esc(c.long || "") + (c.capital ? " · capital " + esc(c.capital) : "") + "</div>" +
      '<div class="gv-tags"><span class="gv-tag" style="border-color:' + CAT[c.cat][1] + ";color:" + CAT[c.cat][1] + '">' + esc(CAT[c.cat][0]) + "</span>" + (trans ? '<span class="gv-tag warn">NOT RUNNING NORMALLY</span>' : "") + "</div></div></div>" +
      '<div class="gv-blf"><div class="h">BOTTOM LINE</div><ul>' + bl.map(function (x) { return "<li>" + x + "</li>"; }).join("") + "</ul></div>" +
      sec(1, "Leadership", c.cat === "supra" ? "" : esc(both ? "One person is both the face of the country and the one running the government." : "The head of state represents the country; the head of government is the one running things day to day."),
        who + kv([["Per the Factbook", (c.exec.cos ? "Chief of state: " + c.exec.cos : "") + (c.exec.hog ? "\nHead of government: " + c.exec.hog : "")], ["Note", c.exec.note]]), true) +
      sec(2, "The administration: who runs what", "The leaders at the top set direction; each minister below runs one part of the government. " + esc(c.exec.cabinet ? "Here: " + c.exec.cabinet.replace(/^cabinet:?\s*/i, "") + "." : ""), cab, true) +
      sec(3, "The legislature: who makes the laws", c.leg.structure ? gloss((c.leg.name || "Parliament") + " is " + c.leg.structure + ".") : "",
        (LAW.indexOf(c.iso2) >= 0 ? '<button class="gv-lawbtn" data-law="' + c.iso2 + '">See its bills and how each lawmaker votes ›</button>' : "") +
        chamberHTML(c.leg.single, "") + chamberHTML(c.leg.lower, "Lower house") + chamberHTML(c.leg.upper, "Upper house") + (c.leg.note ? '<div class="gv-small">' + gloss(c.leg.note.replace(/^note:?\s*/i, "")) + (c.leg.note.length >= 400 ? "…" : "") + "</div>" : "")) +
      sec(4, "The courts", "The top court has the final say on what the law means" + (/life|until age/i.test(c.jud.select) ? "; its judges serve for life or until a set age" : "") + ".",
        (c.iso2 === "US" ? '<button class="gv-lawbtn" data-law="US" data-lsub="courts">See every justice\'s votes, the cases and upcoming arguments ›</button><div class="gv-just" id="gv-justices"></div>' : "") +
        kv([["Top court", c.jud.top], ["How judges are chosen", c.jud.select], ["Lower courts", c.jud.lower], ["Legal system", c.legal]])) +
      sec(5, "Elections and how power changes hands", "", kv([["How leaders are chosen", c.exec.process], ["Last national vote", c.exec.lastvote], ["Next national vote", nv ? nv.text : ""], ["Who can vote", c.suffrage], ["Constitution", c.constitution], ["Changing the constitution", c.amend]]) +
        (c.exec.results ? '<div class="gv-res">' + c.exec.results.split(/\n+/).filter(Boolean).slice(0, 3).map(function (r) { return "<div>" + esc(r) + "</div>"; }).join("") + "</div>" : "")) +
      sec(6, "Political parties", "", '<div class="gv-parties">' + (c.parties || []).map(function (x) { return "<span>" + esc(x) + "</span>"; }).join("") + "</div>") +
      sec(7, "Economy", c.econ.overview ? esc(c.econ.overview.replace(/\.$/, "")) + "." : "", (econ.length ? '<div class="gv-nums">' + econ.map(function (r) { return '<div class="gv-num"><div class="h">' + esc(r[0]).toUpperCase() + '</div><div class="v">' + r[1] + "</div></div>"; }).join("") + "</div>" : "") +
        kv([["Main industries", c.econ.industries], ["Sells most to", c.econ.exp_partners], ["Main exports", c.econ.exp_goods], ["Buys most from", c.econ.imp_partners]])) +
      sec(8, "Security and the military", "", kv([["Armed forces", c.mil.forces], ["Military spending", (wb.milgdp ? wb.milgdp[0].toFixed(1) + "% of GDP (" + wb.milgdp[1] + ", World Bank)" : "") + (c.mil.spend ? (wb.milgdp ? "; Factbook: " : "") + c.mil.spend : "")], ["Who serves", c.mil.age]])) +
      sec(9, "International ties", "", '<div class="gv-parties">' + orgs.map(function (o) { return "<span" + (KEY.test(o.trim()) ? ' class="key"' : "") + ">" + esc(o) + "</span>"; }).join("") + '</div><div class="gv-small">Highlighted: the big ones (UN, NATO, EU, G-7, G-20, BRICS, ASEAN, African Union, OPEC, SCO, the Commonwealth and others).</div>') +
      sec(10, "In the news this week", "", news.length ? '<div class="gv-news">' + news.map(function (n) { return '<button data-id="' + esc(n.id) + '"><b>' + esc(n.t) + "</b><span>" + esc(n.when || "") + "</span></button>"; }).join("") + "</div>" : '<div class="gv-small">Nothing in Archie\'s feed about ' + esc(c.name) + " in the last few days.</div>") +
      sec(11, "Background", "", '<div class="gv-text">' + esc(c.intro) + "</div>" + kv([["Independence", c.independence], ["The Factbook's own label", c.label]])) +
      '<div class="gv-foot">Who holds office: Wikidata, checked ' + (live && live.at < 1e9 ? ctx.ago(Math.round(live.at / 60)) : "when Archie is next online") + ' (volunteers keep it current; a change can take a few days to show). How the country is set up, its history and parliament: the CIA World Factbook\'s final edition (the CIA ended it in February 2026; this is the archived copy). Economy numbers: World Bank, latest year each. Labels on this page describe how power is organized, not how good or bad a government is.</div>';
    el.scrollTop = 0;
    el.querySelectorAll(".gv-news button").forEach(function (b) { b.onclick = function () { close(); ctx.openItem(b.dataset.id); }; });
    el.querySelectorAll(".gv-lawbtn").forEach(function (b) { b.onclick = function (e) { e.stopPropagation(); screen = "law"; civOpt = { cc: b.dataset.law, sub: b.dataset.lsub || "votes" }; render(); }; });
    var jbox = el.querySelector("#gv-justices");
    if (jbox && civ() && civ().justices) civ().justices().then(function (d) {
      var J = (d && d.justices) || [];
      jbox.innerHTML = J.map(function (j) { return '<div><div class="n" data-jn="' + esc(j.name) + '" title="see their votes and disclosures">' + esc(j.name) + '</div><div class="s">' + esc((/Chief/.test(j.role || "") ? "Chief Justice" : "Associate Justice") + (j.start ? " since " + j.start.slice(0, 4) : "") + (j.appointed_by ? " · appointed by " + j.appointed_by : "")) + "</div></div>"; }).join("");
      jbox.querySelectorAll("[data-jn]").forEach(function (t) { t.onclick = function () { showPerson(c, t.dataset.jn, "Supreme Court justice", ""); }; });
    }).catch(function () {});
    if (!holdSide) sideHome(c);
    el.querySelectorAll(".gv-tile .n[data-pn]").forEach(function (t) { t.onclick = function () { showPerson(c, t.dataset.pn, t.dataset.pt, t.dataset.ps); }; });
    if (c.iso2 !== "EU") loadCabinet(c); else $("gv-cab").innerHTML = '<div class="gv-small">The EU has a Commission (one commissioner per country) rather than a cabinet.</div>';
  }
  function sideHome(c) { var sd = $("gv-side"); if (sd && civ()) civ().sideHome(root, sd, c.iso2, c.name); }
  function showPerson(c, name, title, since) {
    var sd = $("gv-side"); if (!sd || !civ()) return;
    root.querySelectorAll(".gv-pc.sel, .gv-tile .n.sel").forEach(function (x) { x.classList.remove("sel"); });
    civ().person(root, sd, c.iso2, fixName(name), title, since ? fmtSince(since) : "");
    sd.scrollTop = 0;
  }
  var cabView = "chart";
  var LEAD = /^((first|executive|deputy|vice|senior)\s+)*(president|prime minister|premier|chancellor|king|queen|emperor|amir|emir|sultan|crown prince|supreme leader|chief executive|governor-general|taoiseach|tanaiste|grand duke|prince|co-prince|captain regent|state councilor|chief of staff|head of state)\b/i;
  var NOTLEAD = /court|bank|assembly|senate|parliament|chamber|congress|national council|legislative|of the (national|people)/i;
  var BANKDIP = /ambassador|permanent representative|central bank|reserve bank|national bank|bank of |monetary/i;
  function fixName(n) {
    return (n || "").split(/\s+/).map(function (x) {
      if (/^[IVX]+$/.test(x) && x !== "XI" && x.length > 1) return x;
      return x.split("-").map(function (p) { return /^[A-Z][A-Z'’]{1,}[,]?$/.test(p) ? p.charAt(0) + p.slice(1).toLowerCase() : p; }).join("-");
    }).join(" ");
  }
  function personCard(m, lead) {
    var info = officeInfo(m.title)[1];
    var meta = [m.hon, m.party, m.since ? fmtSince(m.since) : ""].filter(Boolean).join(" · ");
    return '<div class="gv-pc' + (lead ? " lead" : "") + (m.vacant ? " vacant" : "") + '" data-pn="' + esc(m.vacant ? "" : m.name) + '" data-pt="' + esc(m.title) + '" data-ps="' + esc(m.since || "") + '" title="' + esc((info ? m.title + ": runs " + info : m.title) + (m.vacant ? "" : " · click for their record")) + '">' +
      "<b>" + (m.vacant ? "vacant" : esc(fixName(m.name))) + (m.acting ? '<em class="gv-acting">ACTING</em>' : "") + "</b><span>" + esc(m.title) + "</span>" +
      (meta ? "<i>" + esc(meta) + "</i>" : "") + (info && !lead ? '<i class="gv-runs">runs ' + esc(info) + "</i>" : "") + "</div>";
  }
  function loadCabinet(c) {
    api("/api/gov_cabinet?iso=" + c.iso2 + "&gec=" + c.gec).then(function (d) {
      if (sel !== c) return;
      var box = $("gv-cab"); if (!box) return;
      var groups = (d && d.groups) || ((d && d.ministers) ? [{ label: "", people: d.ministers.map(function (m) { return { title: m.office, name: m.name, party: m.party, since: m.since }; }) }] : []);
      if (!groups.length || !groups[0].people.length) { box.innerHTML = '<div class="gv-small">' + esc((d && d.error) || "No cabinet list has reached Archie for " + c.name + " yet (it checks weekly while online).") + "</div>"; return; }
      var main = groups[0].people, lead = [], cols = { sec: [], eco: [], home: [], other: [], bank: [] };
      main.forEach(function (m) {
        if (LEAD.test(m.title) && !NOTLEAD.test(m.title) || (/^state council/i.test(m.title))) lead.push(m);
        else if (BANKDIP.test(m.title)) cols.bank.push(m);
        else cols[officeInfo(m.title)[2]].push(m);
      });
      var P = people(c), inList = function (n) { var k = (n || "").toLowerCase().split(/\s+/).pop(); return main.some(function (m) { return (m.name || "").toLowerCase().indexOf(k) >= 0; }); };
      [[P.hog[0], P.hogOffice || "head of government"], [P.hos[0], P.hosOffice || "head of state"]].forEach(function (x, i) {
        if (x[0] && x[0].name && !inList(x[0].name) && !(i === 1 && P.hog[0] && P.hog[0].name === x[0].name)) lead.unshift({ title: x[1], name: x[0].name, since: x[0].since });
      });
      var COLN = { sec: "SECURITY & FOREIGN POLICY", eco: "ECONOMY & MONEY", home: "HOME & SERVICES", other: "OTHER OFFICES", bank: "CENTRAL BANK & DIPLOMATS" };
      var src = d.source === "Wikidata" ? "From Wikidata" + (d.at ? ", checked " + ctx.ago(Math.round((Date.now() / 1000 - d.at) / 60)) : "") + " (the CIA's directory hasn't reached Archie yet, so this list may be incomplete)."
        : "From " + esc(d.source) + (d.updated ? ", last updated " + esc(new Date(d.updated + "T12:00:00").toLocaleDateString([], { month: "short", day: "numeric", year: "numeric" })) : "") + '. <a href="' + esc(d.url || "#") + '" target="_blank" rel="noopener">source page</a>';
      var old = d.updated && (Date.now() - Date.parse(d.updated)) > 365 * 86400000;
      var toggle = '<div class="gv-cabtop"><span class="gv-cabn">' + main.length + " officials</span><div class=\"gv-tabs small\"><button data-v=\"chart\" class=\"" + (cabView === "chart" ? "on" : "") + '">chart</button><button data-v="list" class="' + (cabView === "list" ? "on" : "") + '">list</button></div></div>';
      var body;
      if (cabView === "chart") {
        body = '<div class="gv-org"><div class="gv-org-top">' + (lead.length ? lead.map(function (m) { return personCard(m, true); }).join("") : '<div class="gv-small">leadership not listed separately</div>') + "</div>" +
          '<div class="gv-org-cols">' + Object.keys(cols).filter(function (k) { return cols[k].length; }).map(function (k) {
            return '<div class="gv-org-col"><div class="gv-org-h">' + COLN[k] + " · " + cols[k].length + "</div>" + cols[k].map(function (m) { return personCard(m); }).join("") + "</div>";
          }).join("") + "</div></div>";
      } else {
        body = '<table class="gv-ctab"><tr><th>Office</th><th>Who</th></tr>' + main.map(function (m) { return '<tr data-pn="' + esc(m.vacant ? "" : m.name) + '" data-pt="' + esc(m.title) + '"><td>' + esc(m.title) + "</td><td><b>" + (m.vacant ? "vacant" : esc(fixName(m.name))) + "</b>" + (m.acting ? ' <em class="gv-acting">ACTING</em>' : "") + (m.hon ? " <i>" + esc(m.hon) + "</i>" : "") + "</td></tr>"; }).join("") + "</table>";
      }
      var extra = groups.slice(1).map(function (g) {
        return '<details class="gv-sub"><summary>' + esc(g.label || "More officials") + " · " + g.people.length + '</summary><div class="gv-mins">' + g.people.map(function (m) { return personCard(m); }).join("") + "</div></details>";
      }).join("");
      box.innerHTML = toggle + (d.caveat ? '<div class="gv-small">' + esc(d.caveat) + "</div>" : "") + (groups[0].label ? '<div class="gv-gh">' + esc(groups[0].label).toUpperCase() + "</div>" : "") + body + extra +
        '<div class="gv-small">' + src + (old ? " This country's list hasn't been updated in over a year, so some names may have changed." : "") + " Hover anyone for what their office runs.</div>";
      box.querySelectorAll(".gv-cabtop button").forEach(function (b) { b.onclick = function () { cabView = b.dataset.v; loadCabinet(c); }; });
      box.querySelectorAll(".gv-pc[data-pn]").forEach(function (pc) { if (!pc.dataset.pn) return; pc.onclick = function () { showPerson(c, pc.dataset.pn, pc.dataset.pt, pc.dataset.ps); pc.classList.add("sel"); }; });
      box.querySelectorAll(".gv-ctab tr[data-pn]").forEach(function (tr) { tr.onclick = function () { showPerson(c, tr.dataset.pn, tr.dataset.pt, ""); }; });
    }).catch(function () { var b = $("gv-cab"); if (b) b.innerHTML = '<div class="gv-small">Couldn\'t load the cabinet right now.</div>'; });
  }

  /* ---------- map ---------- */
  var MODES = {
    now: ["how it's run today", function (c) { var k = catOf(c); return [CAT[k][1], CAT[k][0]]; }, function () { return Object.keys(CAT).filter(function (k) { return k !== "supra"; }).map(function (k) { return [CAT[k][1], CAT[k][0]]; }); }],
    paper: ["how it's set up on paper", function (c) { return [CAT[c.cat][1], CAT[c.cat][0]]; }, function () { return Object.keys(CAT).filter(function (k) { return k !== "supra" && k !== "mil"; }).map(function (k) { return [CAT[k][1], CAT[k][0]]; }); }],
    vote: ["next national vote", function (c) {
      var nv = nextVote(c), y = nv ? +nv.y : null, now = new Date().getFullYear();
      return y == null ? ["#2a2f24", "none scheduled / unknown"] : y <= now ? ["#c6f432", "this year"] : y === now + 1 ? ["#8fd14f", "next year"] : y === now + 2 ? ["#4f9a52", "in 2 years"] : ["#2e5e3a", "later"];
    }, function () { return [["#c6f432", "this year"], ["#8fd14f", "next year"], ["#4f9a52", "in 2 years"], ["#2e5e3a", "later"], ["#2a2f24", "none scheduled / unknown"]]; }],
    since: ["leader in office for", function (c) {
      var p = people(c), lead = p.hog[0] || p.hos[0], y = lead ? yearsSince(lead.since) : null;
      return y == null ? ["#2a2f24", "unknown"] : y < 1 ? ["#9fe7c4", "under 1 year"] : y < 4 ? ["#5fd0d8", "1–4 years"] : y < 10 ? ["#4f7bd1", "4–10 years"] : y < 20 ? ["#7b4fd1", "10–20 years"] : ["#c44fd1", "20+ years"];
    }, function () { return [["#9fe7c4", "under 1 year"], ["#5fd0d8", "1–4 years"], ["#4f7bd1", "4–10 years"], ["#7b4fd1", "10–20 years"], ["#c44fd1", "20+ years"], ["#2a2f24", "unknown"]]; }]
  };
  var NAME_FIX = { "Kosovo": "XK", "Taiwan": "TW", "Palestine": "PS", "Somaliland": "SO", "N. Cyprus": "CY", "W. Sahara": "EH" };
  function drawMap() {
    var box = $("gv-map"), W = box.clientWidth, H = box.clientHeight;
    var byNum = {}; data.forEach(function (c) { if (c.num) byNum[String(+c.num)] = c; });
    var M = MODES[mapMode];
    box.innerHTML = '<div class="gv-modes">' + Object.keys(MODES).map(function (k) { return '<button data-m="' + k + '" class="' + (k === mapMode ? "on" : "") + '">' + esc(MODES[k][0]) + "</button>"; }).join("") + "</div>" +
      '<div class="gv-legend"><div class="h">' + esc(MODES[mapMode][0]).toUpperCase() + "</div>" + M[2]().map(function (l) { return '<div><i style="background:' + l[0] + '"></i>' + esc(l[1]) + "</div>"; }).join("") + '<div class="gv-small">click a country for its briefing</div></div>' +
      '<div class="gv-big map"><span>BIG PLAYERS</span>' + BIG.map(function (i) { var c = byIso[i]; return c ? '<button data-i="' + i + '" title="' + esc(c.name) + '">' + flag(c) + "</button>" : ""; }).join("") + "</div>";
    box.querySelectorAll(".gv-modes button").forEach(function (b) { b.onclick = function () { mapMode = b.dataset.m; drawMap(); }; });
    box.querySelectorAll(".gv-big button").forEach(function (b) { b.onclick = function () { pick(byIso[b.dataset.i]); }; });
    var W110 = ctx.world && ctx.world();
    var go = function (w) {
      var feats = topojson.feature(w, w.objects.countries).features.filter(function (f) { return f.properties.name !== "Antarctica"; });
      var pr = d3.geoNaturalEarth1().fitExtent([[20, 60], [W - 20, H - 20]], { type: "FeatureCollection", features: feats }), pa = d3.geoPath(pr);
      var svg = d3.select(box).insert("svg", ":first-child").attr("width", W).attr("height", H);
      var tip = root.querySelector(".gv-tip");
      svg.selectAll("path").data(feats).enter().append("path").attr("d", pa).attr("class", "gv-land")
        .each(function (f) { f.c = byNum[String(+f.id)] || byIso[NAME_FIX[f.properties.name]] || data.find(function (x) { return x.name === f.properties.name; }); })
        .attr("fill", function (f) { return f.c ? M[1](f.c)[0] : "#15180f"; })
        .on("mousemove", function (e, f) {
          if (!f.c) { tip.hidden = true; return; }
          var p = people(f.c), lead = p.hog[0] || p.hos[0];
          tip.innerHTML = flag(f.c) + "<b>" + esc(f.c.name) + "</b><span>" + esc(M[1](f.c)[1]) + "</span>" + (lead ? "<i>" + esc(lead.name) + "</i>" : "");
          tip.style.left = (e.clientX + 14) + "px"; tip.style.top = (e.clientY + 12) + "px"; tip.hidden = false;
        })
        .on("mouseleave", function () { tip.hidden = true; })
        .on("click", function (e, f) { tip.hidden = true; if (f.c) pick(f.c); });
    };
    if (W110) go(W110); else fetch("/web/data/countries-110m.json").then(function (r) { return r.json(); }).then(go);
  }

  return { open: open, close: close, toggle: function () { if (root && !root.hidden) close(); else open(); } };
};
