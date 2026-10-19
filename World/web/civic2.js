/* Archie World: lawmaking, part two (US). The Supreme Court and federal judges, congressional committees,
   lobbying, and stock trades reported by members of Congress. Mixed into civic.js (window.ArchieCivic).
   Public record only: no scores, ratings or labels on anyone. */
window.ArchieCivicMore = function (K) {
  "use strict";
  var esc = K.esc, api = K.api, sec = K.sec, loading = K.loading, fmtDate = K.fmtDate, usd = K.usd, pct = K.pct;
  var PIE = K.PIE, OTHER = K.OTHER;
  var courtView = "sc", scTerm = "", judgeScope = "", cmteCh = "", lobYear = "", lobIssue = "", trTx = "", trDays = "", issueNames = {};
  var BUY = "#3987e5", SELL = "#d95926";
  var VALUE = { J: "$15,000 or less", K: "$15,001–$50,000", L: "$50,001–$100,000", M: "$100,001–$250,000", N: "$250,001–$500,000", O: "$500,001–$1M", P1: "$1M–$5M", P2: "$5M–$25M", P3: "$25M–$50M", P4: "over $50M" };
  var INCOME = { A: "$1,000 or less", B: "$1,001–$2,500", C: "$2,501–$5,000", D: "$5,001–$15,000", E: "$15,001–$50,000", F: "$50,001–$100,000", G: "$100,001–$1M", H1: "$1M–$5M", H2: "over $5M" };
  var ATYPE = { ST: "stock", OP: "options", GS: "government bond", CS: "corporate bond", EF: "fund (ETF)", MF: "mutual fund", PS: "private stock", CT: "crypto", OT: "other", AB: "partnership", HN: "hedge fund", OI: "private fund", RE: "real estate", "5P": "529 plan", BA: "bank account", DB: "bond" };
  var SUBS = [["courts", "supreme court & judges"], ["committees", "committees"], ["lobbying", "lobbying"], ["trades", "stock trades"]];

  function pc(p) { return window.archiePartyColor(p, "#8d927f"); }
  function sw(p) { return '<i class="cv-sw" style="background:' + pc(p) + '"></i>'; }
  function last(n) { n = String(n || "").replace(/,?\s+(Jr|Sr)\.?$/, ""); var p = n.split(/\s+/); return p[p.length - 1]; }
  function seatBar(split) {
    var k = Object.keys(split || {}).sort(function (a, b) { return split[b] - split[a]; }), t = k.reduce(function (a, x) { return a + split[x]; }, 0);
    if (!t) return "";
    return '<span class="cv-seat" title="' + esc(k.map(function (x) { return x + ": " + split[x]; }).join(", ")) + '">' + k.map(function (x) { return '<i style="width:' + (100 * split[x] / t) + "%;background:" + pc(x) + '"></i>'; }).join("") + "</span>" +
      '<span class="cv-small cv-seatn">' + k.map(function (x) { return esc(x.replace(/^Democrat$/, "Democrats").replace(/^Republican$/, "Republicans").replace(/^Independent$/, "Independents")) + " " + split[x]; }).join(" · ") + "</span>";
  }
  function hbars(rows, max, fmt) {
    return '<div class="cv-bars">' + rows.map(function (r) {
      return '<div' + (r.attr || "") + '><span>' + esc(r.label) + '</span><i><b style="width:' + Math.max(1, 100 * r.v / (max || 1)) + "%" + (r.c ? ";background:" + r.c : "") + '"></b></i><u>' + (fmt ? fmt(r.v) : usd(r.v)) + "</u></div>";
    }).join("") + "</div>";
  }
  function chips(items, val, attr) { return '<div class="cv-chips">' + items.map(function (x) { return '<button ' + (attr || "data-v") + '="' + esc(x[0]) + '" class="' + (String(val) === String(x[0]) ? "on" : "") + '">' + x[1] + "</button>"; }).join("") + "</div>"; }
  function termLabel(t) { return t + " term (Oct " + t + " – Jun " + (+t + 1) + ")"; }
  function split(c) { return c.maj || c.min ? (c.min ? c.maj + "–" + c.min : "unanimous " + c.maj + "–0") : ""; }

  /* ================================================================ list views */
  function list(sub, L, F, q, offset, redraw) {
    if (sub === "courts") courts(L, F, q, redraw);
    else if (sub === "committees") committees(L, F, q, redraw);
    else if (sub === "lobbying") lobbying(L, F, q, redraw);
    else if (sub === "trades") trades(L, F, q, offset, redraw);
  }

  /* ---------- the Supreme Court and federal judges ---------- */
  function courts(L, F, q, redraw) {
    F.innerHTML = chips([["sc", "the Supreme Court"], ["judges", "federal judges' financial disclosures"]], courtView);
    F.querySelectorAll("button").forEach(function (b) { b.onclick = function () { courtView = b.dataset.v; redraw(); }; });
    if (courtView === "judges") return judges(L, F, q, redraw);
    L.innerHTML = loading("Loading the Court's record…");
    api("/api/civic/scotus?term=" + scTerm).then(function (d) {
      if (!d.loaded) { L.innerHTML = '<div class="cv-small cv-pad">The Supreme Court\'s cases haven\'t reached Archie yet. It downloads them from Oyez (a free project of Cornell\'s Legal Information Institute and Justia) a few minutes after starting, while online.</div>'; return; }
      F.insertAdjacentHTML("beforeend", chips(d.terms.map(function (t) { return [t, termLabel(t)]; }), d.term, "data-t"));
      F.querySelectorAll("[data-t]").forEach(function (b) { b.onclick = function () { scTerm = b.dataset.t; redraw(); }; });
      var S = d.stats || {}, J = d.justices || [], C = d.cases || [];
      var close = C.filter(function (c) { return c.n_votes && c.min && c.maj - c.min === 1; }).length;
      var tiles = '<div class="gv-nums"><div class="gv-num"><div class="h">DECIDED THIS TERM</div><div class="v">' + d.decided + '</div></div><div class="gv-num"><div class="h">UNANIMOUS</div><div class="v">' + d.unanimous + ' <span class="gv-yr">' + pct(d.unanimous, C.filter(function (c) { return c.n_votes; }).length) + '</span></div></div>' +
        '<div class="gv-num"><div class="h">DECIDED BY ONE VOTE (5–4)</div><div class="v">' + close + '</div></div><div class="gv-num"><div class="h">ARGUMENTS COMING UP</div><div class="v">' + (d.upcoming || []).length + "</div></div></div>";
      var cards = '<div class="cv-jcards">' + J.map(function (j) {
        var s = S[j.name] || {};
        return '<button class="cv-jcard" data-j="' + esc(j.name) + '"><b>' + esc(j.name) + "</b><i>" + esc(/Chief/.test(j.role || "") ? "Chief Justice" : "Associate Justice") + (j.start ? " since " + esc(j.start.slice(0, 4)) : "") + (j.appointed_by ? " · appointed by " + esc(j.appointed_by) : "") + "</i>" +
          (s.cases ? '<span class="cv-jst"><em>in the majority</em> ' + s.majority + " of " + s.cases + '</span><span class="cv-jst"><em>wrote</em> ' + s.wrote_majority + " majority · " + s.concur + " concurring · " + s.wrote_dissent + " dissenting</span>" : '<span class="cv-jst"><em>no decided cases this term yet</em></span>') + "</button>";
      }).join("") + "</div>";
      var names = J.map(function (j) { return j.name; });
      var M = d.matrix || {}, cell = function (a, b) { if (a === b) return '<td class="self"></td>'; var k = a < b ? a + "|" + b : b + "|" + a, v = M[k]; if (!v) return "<td>—</td>"; var p = v[0] / v[1]; return '<td style="background:rgba(57,135,229,' + (0.08 + 0.8 * p * p).toFixed(2) + ')" title="' + esc(a + " and " + b + ": same side in " + v[0] + " of " + v[1] + " cases") + '">' + Math.round(100 * p) + "</td>"; };
      var matrix = names.length && Object.keys(M).length ? '<div class="cv-mxwrap"><table class="cv-mx"><tr><th></th>' + names.map(function (n) { return "<th>" + esc(last(n)) + "</th>"; }).join("") + "</tr>" +
        names.map(function (a) { return "<tr><th>" + esc(last(a)) + "</th>" + names.map(function (b) { return cell(a, b); }).join("") + "</tr>"; }).join("") + "</table></div>" +
        '<div class="cv-small">Percent of this term\'s decided cases in which each pair of justices ended up on the same side (both in the majority, or both dissenting). Hover a square for the count. Opinions that agree in part and disagree in part are counted the way Oyez records them.</div>' : '<div class="cv-small">Once cases are decided, this shows how often each pair of justices voted the same way.</div>';
      var caseRow = function (c, when) {
        return '<button class="cv-row bill" data-case="' + esc(c.id) + '"><span class="cv-num">No. ' + esc(c.docket) + '</span><span class="cv-t"><b>' + esc(c.name) + "</b><i>" + esc((c.question || c.description || "").slice(0, 180)) + '</i></span><span class="cv-st"><i>' + esc(split(c) || (c.argued ? "argued, waiting for a decision" : c.arg_next ? "argument set" : "accepted, not yet argued")) + '</i></span><span class="cv-d">' + esc(fmtDate(when || c.decided || c.argued || c.arg_next || c.granted)) + "</span></button>";
      };
      var up = d.upcoming || [], pend = d.pending || [];
      L.innerHTML = '<div class="cv-pad2">' + sec("THE COURT · " + esc(termLabel(d.term).toUpperCase()), tiles) +
        sec("THE JUSTICES", cards + '<div class="cv-small">Click a justice for every vote they cast, the opinions they wrote, and their financial disclosures. Counts are from the cases Archie has for this term.</div>') +
        (up.length ? sec("COMING UP: ORAL ARGUMENTS", up.map(function (c) { return caseRow(c, c.arg_next); }).join("") + '<div class="cv-small">From the Court\'s argument calendar. Arguments start at 10 a.m. Eastern; the Court posts audio the same week.</div>') : "") +
        sec("HOW OFTEN THEY AGREE", matrix) +
        sec("CASES · " + C.length, C.map(function (c) { return caseRow(c); }).join("") || '<div class="cv-small">None yet.</div>') +
        (pend.length ? sec("ACCEPTED OR ARGUED, NO DECISION YET", pend.map(function (c) { return caseRow(c, c.argued || c.granted); }).join("")) : "") +
        '<div class="cv-small">Cases, votes and opinions: Oyez (a free law project of Cornell\'s Legal Information Institute, Justia and Chicago-Kent College of Law). Argument dates: the Supreme Court\'s own calendar.</div></div>';
      L.querySelectorAll("[data-j]").forEach(function (b) { b.onclick = function () { openJustice(b.dataset.j); }; });
      L.querySelectorAll("[data-case]").forEach(function (b) { b.onclick = function () { openCase(b.dataset.case); }; });
    });
  }
  function judges(L, F, q, redraw) {
    F.insertAdjacentHTML("beforeend", chips([["", "everyone with a report"], ["active", "serving now"]], judgeScope, "data-js"));
    F.querySelectorAll("[data-js]").forEach(function (b) { b.onclick = function () { judgeScope = b.dataset.js; redraw(); }; });
    F.querySelectorAll("button[data-v]").forEach(function (b) { b.onclick = function () { courtView = b.dataset.v; redraw(); }; });
    L.innerHTML = loading();
    api("/api/civic/judges?q=" + encodeURIComponent(q) + "&scope=" + judgeScope).then(function (d) {
      if (!d.total) { L.innerHTML = '<div class="cv-small cv-pad">Judges\' financial disclosures haven\'t reached Archie yet. Once a month it downloads the Free Law Project\'s collection (about 50 MB), while online.</div>'; return; }
      L.innerHTML = '<div class="cv-small cv-pad">' + d.total.toLocaleString() + " federal judges and justices with financial disclosure reports" + (d.as_of ? " (collection as of " + esc(fmtDate(d.as_of)) + ")" : "") + ". Search by name or court. Every federal judge files one each year: gifts, paid travel, outside income, positions, debts and (for the justices here) investments.</div>" +
        (d.judges || []).map(function (j) {
          return '<button class="cv-row bill" data-jd="' + j.id + '"><span class="cv-num">' + (j.scotus ? "Supreme Court" : esc(j.court || "")) + '</span><span class="cv-t"><b>' + esc(j.name) + "</b><i>" + esc(j.title || "") + (j.active ? "" : " · no longer serving") + '</i></span><span class="cv-st"><i>' + j.n + " report" + (j.n === 1 ? "" : "s") + '</i></span><span class="cv-d">' + (j.last || "") + "</span></button>";
        }).join("");
      L.querySelectorAll("[data-jd]").forEach(function (b) { b.onclick = function () { openJudge(b.dataset.jd); }; });
    });
  }
  function openCase(id) {
    var el = K.openDrawer(loading());
    api("/api/civic/case?id=" + encodeURIComponent(id)).then(function (c) {
      if (c.error) { el.innerHTML = '<div class="cv-small">Not found.</div>'; return; }
      var V = c.votes || [], maj = V.filter(function (v) { return v.side === "majority"; }), min = V.filter(function (v) { return v.side === "minority"; }), oth = V.filter(function (v) { return v.side !== "majority" && v.side !== "minority"; });
      var opn = function (v) { var o = (v.op || "").toLowerCase(); return o === "majority" ? "wrote the majority opinion" : o === "plurality" ? "wrote the plurality opinion" : /concurr/.test(o) ? "wrote a concurring opinion" : /dissent/.test(o) ? "wrote a dissent" : (v.joining && v.joining.length ? "joined " + v.joining.map(last).join(", ") : ""); };
      var col = function (title, L2, color) { return L2.length ? '<div><div class="cv-posh" style="border-color:' + color + '">' + title + " · " + L2.length + "</div>" + L2.map(function (v) { return '<button class="cv-nm" data-j="' + esc(v.name) + '">' + esc(v.name) + " <i>" + esc(opn(v)) + "</i></button>"; }).join("") + "</div>" : ""; };
      el.innerHTML = '<div class="cv-kicker">' + K.flag("US") + " SUPREME COURT · NO. " + esc(c.docket) + " · " + esc(termLabel(c.term).toUpperCase()) + K.watchBtn("case", c.id, c.name, "US") + "</div><h2>" + esc(c.name) + "</h2>" +
        '<div class="cv-meta">' + [c.granted ? "accepted " + esc(fmtDate(c.granted)) : "", c.arg_next && !c.argued ? "<b>argument " + esc(fmtDate(c.arg_next)) + "</b>" : "", c.argued ? "argued " + esc(fmtDate(c.argued)) : "", c.decided ? "<b>decided " + esc(fmtDate(c.decided)) + "</b>" : "", c.lower ? "from the " + esc(c.lower) : ""].filter(Boolean).join(" · ") + "</div>" +
        (c.decided && V.length ? sec("RESULT", '<div class="cv-bigres"><span class="cv-res ok">' + esc(split(c)) + "</span>" + (c.winner ? ' <span class="cv-small">decided for ' + esc(c.winner) + "</span>" : "") + "</div>") : "") +
        (c.question ? sec("THE QUESTION", '<p class="cv-p">' + esc(c.question) + "</p>") : "") +
        (c.facts ? sec("THE FACTS", '<p class="cv-p">' + esc(c.facts.slice(0, 2400)) + "</p>") : "") +
        (c.conclusion ? sec("WHAT THE COURT DECIDED", '<p class="cv-p">' + esc(c.conclusion.slice(0, 3000)) + "</p>") : "") +
        sec("IN PLAIN ENGLISH", K.explainBtn("case", c.id, c.plain, "explain this case simply")) +
        (V.length ? sec("HOW EACH JUSTICE VOTED", '<div class="cv-poscols">' + col("MAJORITY", maj, "#1fa67a") + col("DISSENT", min, "#9085e9") + col("OTHER", oth, "#8d927f") + "</div>") : "") +
        '<div class="cv-foot">' + (c.href ? '<a href="' + esc(c.href.replace("api.oyez.org", "www.oyez.org")) + '" target="_blank" rel="noopener">Oyez (audio, opinions) ↗</a> · ' : "") + (c.justia ? '<a href="' + esc(c.justia) + '" target="_blank" rel="noopener">full opinion at Justia ↗</a> · ' : "") +
        '<a href="https://www.supremecourt.gov/docket/docketfiles/html/public/' + esc(c.docket) + '.html" target="_blank" rel="noopener">the Court\'s docket ↗</a></div>';
      el.querySelectorAll("[data-j]").forEach(function (b) { b.onclick = function () { openJustice(b.dataset.j); }; });
      K.wireExplain(el); K.wireWatch(el);
    });
  }
  function justiceInto(el, name, intro) {
    api("/api/civic/justice?name=" + encodeURIComponent(name)).then(function (j) {
      if (j.error) { el.innerHTML = (intro || "") + '<div class="cv-small">Not in Archie\'s records yet.</div>'; return; }
      var R = j.record || [], maj = R.filter(function (r) { return r.side === "majority"; }).length, dis = R.filter(function (r) { return r.side === "minority"; }).length;
      var ops = { m: 0, c: 0, d: 0 }; R.forEach(function (r) { var o = (r.op || "").toLowerCase(); if (o === "majority" || o === "plurality") ops.m++; else if (/concurr/.test(o)) ops.c++; else if (/dissent/.test(o)) ops.d++; });
      el.innerHTML = (intro || "") + '<div class="cv-kicker">' + K.flag("US") + " SUPREME COURT · JUSTICE</div><h2>" + esc(j.name) + '</h2><div class="cv-meta">' + esc(j.role || "") + (j.appointed_by ? " · appointed by " + esc(j.appointed_by) : "") + (j.start ? " · on the Court since " + esc(fmtDate(j.start)) : "") + "</div>" +
        sec("THEIR VOTES", '<div class="gv-nums"><div class="gv-num"><div class="h">CASES</div><div class="v">' + R.length + '</div></div><div class="gv-num"><div class="h">IN THE MAJORITY</div><div class="v">' + maj + ' <span class="gv-yr">of ' + (maj + dis) + " (" + pct(maj, maj + dis) + ")" + '</span></div></div><div class="gv-num"><div class="h">DISSENTED</div><div class="v">' + dis + '</div></div><div class="gv-num"><div class="h">WROTE FOR THE COURT</div><div class="v">' + ops.m + "</div></div></div>" +
          '<div class="cv-small">Opinions written: ' + ops.m + " for the majority, " + ops.c + " concurring, " + ops.d + " dissenting. From the cases Archie has downloaded (the last three terms).</div>" +
          R.slice(0, 120).map(function (r) {
            var o = (r.op || "").toLowerCase();
            return '<button class="cv-rec" data-case="' + esc(r.id) + '"><span class="cv-d">' + esc(fmtDate(r.decided)) + '</span><span class="cv-t"><b>' + esc(r.name) + "</b><i>" + esc((r.min ? r.maj + "–" + r.min : "unanimous") + (o && o !== "none" ? " · wrote " + (o === "majority" ? "the majority opinion" : /concurr/.test(o) ? "a concurrence" : /dissent/.test(o) ? "a dissent" : o) : r.joining.length ? " · joined " + r.joining.map(last).join(", ") : "")) + '</i></span><span class="cv-pos" style="background:' + (r.side === "majority" ? "#1fa67a" : "#9085e9") + '">' + (r.side === "majority" ? "majority" : r.side === "minority" ? "dissent" : esc(r.side)) + "</span><span></span></button>";
          }).join("")) +
        sec("FINANCIAL DISCLOSURES", '<div id="cv-jdisc">' + (j.disclosure_person ? loading() : '<div class="cv-small">Their annual financial disclosure reports haven\'t reached Archie yet (they come from the Free Law Project\'s monthly collection).</div>') + "</div>");
      el.querySelectorAll("[data-case]").forEach(function (b) { b.onclick = function () { openCase(b.dataset.case); }; });
      if (j.disclosure_person) api("/api/civic/judge?id=" + j.disclosure_person).then(function (p) { reports(el.querySelector("#cv-jdisc"), p); });
    });
  }
  function openJustice(name) { justiceInto(K.openDrawer(loading()), name); }
  function openJudge(id) {
    var el = K.openDrawer(loading());
    api("/api/civic/judge?id=" + encodeURIComponent(id)).then(function (p) {
      if (p.error) { el.innerHTML = '<div class="cv-small">Not found.</div>'; return; }
      el.innerHTML = '<div class="cv-kicker">' + K.flag("US") + " FEDERAL JUDGE · FINANCIAL DISCLOSURES</div><h2>" + esc(p.name) + '</h2><div class="cv-meta">' + esc([p.title, p.court].filter(Boolean).join(", ")) + (p.active ? "" : " · no longer serving") + "</div>" + '<div id="cv-jdisc"></div>';
      reports(el.querySelector("#cv-jdisc"), p);
    });
  }
  function reports(box, p) {
    var R = p.reports || [];
    if (!R.length) { box.innerHTML = '<div class="cv-small">No reports in the collection.</div>'; return; }
    var tab = function (head, rows) { return '<table class="cv-ptab money"><tr>' + head.map(function (h) { return "<th>" + h + "</th>"; }).join("") + "</tr>" + rows.map(function (r) { return "<tr>" + r.map(function (c) { return "<td>" + esc(c || "—") + "</td>"; }).join("") + "</tr>"; }).join("") + "</table>"; };
    var part = function (title, rows) { return rows ? '<div class="cv-mh">' + title + "</div>" + rows : ""; };
    box.innerHTML = '<div class="cv-small">Every federal judge files a report each year (covering the year before). Values are given in ranges, as the forms require. Read by the Free Law Project from the scanned forms, so check the original for anything important. Their collection currently runs through the reports filed in 2022; newer ones are in the federal courts\' own database (free sign-up): <a href="https://www.uscourts.gov/administration-policies/judiciary-financial-disclosure-reports" target="_blank" rel="noopener">judiciary financial disclosure reports ↗</a>.</div>' +
      R.map(function (r, i) {
        var I = r.items || {};
        var n = Object.keys(I).reduce(function (a, k) { return a + I[k].length; }, 0);
        var body = part("GIFTS", I.gift && tab(["from", "what", "value"], I.gift.map(function (x) { return [x[0], x[1], x[2]]; }))) +
          part("PAID TRAVEL AND EXPENSES (REIMBURSEMENTS)", I.reimb && tab(["paid by", "when", "where", "why", "what was covered"], I.reimb)) +
          part("OUTSIDE INCOME (NOT FROM INVESTMENTS)", I.income && tab(["when", "source", "amount"], I.income.map(function (x) { return [x[0], x[1], x[2]]; }))) +
          part("SPOUSE'S INCOME (SOURCE ONLY; THE FORM DOESN'T ASK FOR AMOUNTS)", I.spouse && tab(["source", "when"], I.spouse.map(function (x) { return [x[0], x[1]]; }))) +
          part("OUTSIDE POSITIONS", I.position && tab(["position", "organization"], I.position.map(function (x) { return [x[0], x[1]]; }))) +
          part("AGREEMENTS (BOOK DEALS, FUTURE JOBS, PENSIONS)", I.agreement && tab(["when", "parties and terms"], I.agreement.map(function (x) { return [x[0], x[1]]; }))) +
          part("DEBTS", I.debt && tab(["owed to", "what", "value"], I.debt.map(function (x) { return [x[0], x[1], VALUE[x[2]] || x[2]]; }))) +
          part("INVESTMENTS", I.invest && tab(["holding", "value", "income", "bought / sold"], I.invest.map(function (x) {
            var inc = (x[2] || "").split("|"), tr = (x[3] || "").split("|");
            return [x[0], VALUE[x[1]] || x[1], [INCOME[inc[0]] || inc[0], inc[1]].filter(Boolean).join(" "), [tr[0], tr[1], VALUE[tr[2]] || tr[2]].filter(Boolean).join(" ")];
          })));
        return '<details class="gv-sub"' + (i === 0 ? " open" : "") + "><summary>" + r.year + " report" + (r.amended ? " (amended)" : "") + " · " + (n ? n + " entries" : "nothing itemized in the collection") + "</summary>" + (body || '<div class="cv-small">Nothing itemized; see the original.</div>') +
          (r.url ? '<div class="cv-foot"><a href="' + esc(r.url) + '" target="_blank" rel="noopener">original report (PDF) ↗</a></div>' : "") + "</details>";
      }).join("") + (p.as_of ? '<div class="cv-small">Collection as of ' + esc(fmtDate(p.as_of)) + ". Free Law Project (CourtListener).</div>" : "");
  }

  /* ---------- committees ---------- */
  function committees(L, F, q) {
    F.innerHTML = chips([["", "all"], ["House", "House"], ["Senate", "Senate"], ["Joint", "joint"]], cmteCh);
    F.querySelectorAll("button").forEach(function (b) { b.onclick = function () { cmteCh = b.dataset.v; committees(L, F, q); }; });
    L.innerHTML = loading();
    api("/api/civic/committees").then(function (d) {
      var C = (d.committees || []).filter(function (c) { return (!cmteCh || c.chamber === cmteCh) && (!q || (c.name + " " + (c.chair ? c.chair.name : "")).toLowerCase().indexOf(q.toLowerCase()) >= 0); });
      if (!d.loaded) { L.innerHTML = '<div class="cv-small cv-pad">The committee lists haven\'t loaded yet.</div>'; return; }
      var card = function (c) {
        return '<button class="cv-ccard' + (c.key ? " key" : "") + '" data-cm="' + esc(c.code) + '"><span class="cv-cch">' + esc(c.chamber.toUpperCase()) + "</span><b>" + esc(c.short) + "</b>" + (c.role ? "<em>" + esc(c.role) + "</em>" : "") +
          '<span class="cv-cline">' + (c.chair ? "Chair: " + sw(c.chair.party) + esc(c.chair.name) : "") + (c.ranking ? " · " + esc(/vice/i.test(c.ranking.title) ? "Vice chair" : "Ranking member") + ": " + sw(c.ranking.party) + esc(c.ranking.name) : "") + "</span>" +
          seatBar(c.split) + '<span class="cv-cline cv-small">' + c.n + " members" + (c.subs ? " · " + c.subs + " subcommittees" : "") + (c.bills ? " · " + c.bills.toLocaleString() + " bills sent to it, " + c.moved.toLocaleString() + " sent on" : "") + "</span></button>";
      };
      var key = C.filter(function (c) { return c.key; }), rest = C.filter(function (c) { return !c.key; });
      L.innerHTML = '<div class="cv-pad2"><p class="cv-p">Most of Congress\'s work happens in committees. A bill goes to one or more of them first; most never leave. Committees hold hearings, rewrite bills ("markup") and vote on whether to send them to the full House or Senate. The party with the majority in each chamber holds the chair and most seats.</p>' +
        (key.length ? sec("WHERE MUCH OF THE POWER SITS", '<div class="cv-ccards">' + key.map(card).join("") + "</div>") : "") +
        sec((cmteCh ? cmteCh.toUpperCase() + " " : "") + "COMMITTEES · " + rest.length, '<div class="cv-ccards">' + rest.map(card).join("") + "</div>") +
        '<div class="cv-small">Members and roles: the congress-legislators project (public domain). Bills sent to each committee: the official bill records (govinfo). "Sent on" means the committee reported the bill or it moved past committee.</div></div>';
      L.querySelectorAll("[data-cm]").forEach(function (b) { b.onclick = function () { openCmte(b.dataset.cm); }; });
    });
  }
  function openCmte(code) {
    var el = K.openDrawer(loading());
    api("/api/civic/committee?code=" + encodeURIComponent(code)).then(function (c) {
      if (c.error) { el.innerHTML = '<div class="cv-small">Not found.</div>'; return; }
      var M = c.members || [], maj = M.filter(function (m) { return m.side === "majority"; }), min = M.filter(function (m) { return m.side !== "majority"; });
      var mcol = function (title, L2) { return '<div><div class="cv-posh">' + title + " · " + L2.length + "</div>" + L2.map(function (m) { return '<button class="cv-nm" data-m="' + esc(m.key) + '">' + sw(m.party) + esc(m.name) + " <i>" + esc([m.title, m.state ? m.state + (m.chamber === "H" && m.district != null ? "-" + m.district : "") : ""].filter(Boolean).join(" · ")) + "</i></button>"; }).join("") + "</div>"; };
      var st = c.stages || {}, B = c.bills || [];
      var ST = ["introduced", "in committee", "sent on by committee", "passed one chamber", "passed both", "sent for signature", "law"];
      el.innerHTML = '<div class="cv-kicker">' + K.flag("US") + " " + esc(c.chamber.toUpperCase()) + (c.parent ? " · SUBCOMMITTEE" : " · COMMITTEE") + K.watchBtn("committee", c.code, c.name, "US") + "</div><h2>" + esc(c.name) + "</h2>" +
        (c.parent ? '<div class="cv-meta">part of the <a href="#" data-cm="' + esc(c.parent) + '">' + esc(c.parent_name) + "</a></div>" : "") +
        sec("WHAT IT'S FOR", (c.role ? '<p class="cv-p"><b>' + esc(c.role) + "</b></p>" : "") + (c.about ? '<div class="cv-crs"><div class="cv-small">In the committee\'s own words:</div><p>' + esc(c.about) + "</p></div>" : (c.role ? "" : '<div class="cv-small">No description published.</div>'))) +
        sec("WHO SITS ON IT · " + M.length, seatBar(c.split) + '<div class="cv-poscols">' + mcol("MAJORITY SIDE", maj) + mcol("MINORITY SIDE", min) + "</div>") +
        (c.subs && c.subs.length ? sec("SUBCOMMITTEES · " + c.subs.length, c.subs.map(function (s) { return '<button class="cv-row bill mini" data-cm="' + esc(s.code) + '"><span class="cv-t"><b>' + esc(s.name) + "</b><i>" + (s.chair ? "Chair: " + esc(s.chair) + " · " : "") + s.n + " members</i></span></button>"; }).join("")) : "") +
        ((c.hearings || []).length ? sec("UPCOMING HEARINGS", c.hearings.map(function (h) { return '<div class="cv-ev"><span></span><span class="cv-evt">' + esc(fmtDate(h.date)) + " " + esc(h.time || "") + "</span><div><b>" + esc(h.title) + "</b><i>" + esc(h.body || "") + "</i></div></div>"; }).join("")) : "") +
        sec("WHAT IT'S WORKING ON", (Object.keys(st).length ? '<div class="cv-small">Bills sent to it this Congress, by where they are now: ' + Object.keys(st).sort().map(function (k) { return "<b>" + st[k] + "</b> " + esc(+k === -1 ? "stopped" : ST[+k] || k); }).join(" · ") + "</div>" : "") +
          (B.length ? B.map(function (b) { return '<button class="cv-row bill mini" data-b="' + esc(b.id) + '"><span class="cv-num">' + esc(b.num) + '</span><span class="cv-t"><b>' + esc(b.title) + "</b><i>" + esc([b.sponsor ? b.sponsor + (b.party ? " (" + K.partyLetter(b.party) + ")" : "") : "", b.latest_text ? b.latest_text.slice(0, 120) : ""].filter(Boolean).join(" · ")) + '</i></span><span class="cv-st">' + K.stageDots(b.stage, true) + "<i>" + esc(b.stage_text) + '</i></span><span class="cv-d">' + esc(fmtDate(b.latest_date)) + "</span></button>"; }).join("") +
            (B.length >= 80 ? '<div class="cv-small">Latest 80 shown.</div>' : "") : '<div class="cv-small">' + (c.chamber === "Joint" ? "Joint committees study and report; bills aren't sent to them." : "No bills on record for it yet (they fill in as the official bill records load).") + "</div>")) +
        ((c.lobbied || []).length ? sec("MOST-LOBBIED BILLS IN ITS HANDS", c.lobbied.map(function (b) { return '<button class="cv-row bill mini" data-b="' + esc(b.id) + '"><span class="cv-num">' + esc(b.num) + '</span><span class="cv-t"><b>' + esc(b.title) + '</b></span><span class="cv-st"><i>' + b.clients + (b.clients === 1 ? " organization" : " organizations") + " lobbied on it</i></span></button>"; }).join("")) : "") +
        (c.url ? '<div class="cv-foot"><a href="' + esc(c.url) + '" target="_blank" rel="noopener">committee website ↗</a></div>' : "");
      el.querySelectorAll("[data-m]").forEach(function (b) { b.onclick = function () { if (b.dataset.m) K.openMember(b.dataset.m); }; });
      el.querySelectorAll("[data-b]").forEach(function (b) { b.onclick = function () { K.openBill(b.dataset.b); }; });
      el.querySelectorAll("[data-cm]").forEach(function (b) { b.onclick = function (e) { e.preventDefault(); openCmte(b.dataset.cm); }; });
      K.wireWatch(el);
    });
  }

  /* ---------- lobbying ---------- */
  function lobbying(L, F, q) {
    L.innerHTML = loading();
    api("/api/civic/lobbying?year=" + lobYear + "&issue=" + lobIssue + "&q=" + encodeURIComponent(q)).then(function (d) {
      issueNames = d.issue_names || {};
      var T = d.total || {};
      F.innerHTML = (d.years.length > 1 ? chips(d.years.map(function (y) { return [y, y]; }), d.year, "data-y") : "") +
        '<div class="cv-chips"><select id="cv-iss"><option value="">every issue</option>' + Object.keys(issueNames).sort(function (a, b) { return issueNames[a].localeCompare(issueNames[b]); }).map(function (k) { return '<option value="' + k + '"' + (lobIssue === k ? " selected" : "") + ">" + esc(issueNames[k]) + "</option>"; }).join("") + "</select></div>";
      F.querySelectorAll("[data-y]").forEach(function (b) { b.onclick = function () { lobYear = b.dataset.y; lobbying(L, F, q); }; });
      F.querySelector("#cv-iss").onchange = function () { lobIssue = this.value; lobbying(L, F, q); };
      if (!T.n) { L.innerHTML = '<div class="cv-small cv-pad">' + (lobIssue || q ? "No reports match." : "Lobbying reports haven't reached Archie yet. It reads them from lda.gov a few hundred an hour (the free, no-key limit), newest year first; a full year is about 45,000 reports, so this fills in over a day or two of Archie being online.") + "</div>"; return; }
      var C = d.clients || [], Fi = d.firms || [], I = (d.issues || []).slice(0, 15), B = d.bills || [];
      var prog = d.progress || {}, pend = Object.keys(prog).filter(function (k) { return !prog[k].done && prog[k].total; });
      L.innerHTML = '<div class="cv-pad2">' +
        '<div class="gv-nums"><div class="gv-num"><div class="h">REPORTED SPENDING</div><div class="v">' + usd(T.amt) + '</div></div><div class="gv-num"><div class="h">REPORTS</div><div class="v">' + T.n.toLocaleString() + '</div></div><div class="gv-num"><div class="h">CLIENTS</div><div class="v">' + T.clients.toLocaleString() + '</div></div><div class="gv-num"><div class="h">LOBBYING FIRMS AND GROUPS</div><div class="v">' + T.firms.toLocaleString() + '</div></div>' +
        '<div class="gv-num"><div class="h">LOBBYIST LISTINGS WITH A PAST GOVERNMENT JOB</div><div class="v">' + (d.revolving || 0).toLocaleString() + "</div></div></div>" +
        (pend.length ? '<div class="cv-small">Still loading: ' + pend.map(function (k) { return esc(k.slice(0, 4) + " " + k.slice(4)) + " (" + Math.min(100, Math.round(100 * (prog[k].page * 25) / prog[k].total)) + "%)"; }).join(", ") + ". Totals grow as it goes.</div>" : "") +
        sec("WHO SPENT THE MOST", hbars(C.map(function (c) { return { label: K.nice(c.client), v: c.amt || 0, attr: ' class="cv-click" data-cl="' + c.client_id + '"' }; }), C.length ? C[0].amt : 1) + '<div class="cv-small">Click any name for its reports: which bills and issues, which firms it hired, and the lobbyists who worked on it.</div>') +
        (Fi.length ? sec("BIGGEST LOBBYING FIRMS (BY INCOME FROM CLIENTS)", hbars(Fi.map(function (f) { return { label: K.nice(f.firm) + " · " + f.clients + " clients", v: f.amt || 0 }; }), Fi[0].amt)) : "") +
        sec("WHAT THEY LOBBIED ABOUT (NUMBER OF REPORTS)", hbars(I.map(function (x, i) { return { label: issueNames[x[0]] || x[0], v: x[1], attr: ' class="cv-click" data-is="' + x[0] + '"' }; }), I.length ? I[0][1] : 1, function (v) { return v.toLocaleString(); }) + '<div class="cv-small">Each report lists one or more issue areas; click one to filter everything above.</div>') +
        (B.length ? sec("MOST-LOBBIED BILLS", B.map(function (b) { return '<button class="cv-row bill mini" data-b="' + esc(b.bill) + '"><span class="cv-num">' + esc(b.num || b.bill.replace(/^US-\d+-/, "")) + '</span><span class="cv-t"><b>' + esc(b.title || "(not in Archie's bill list)") + '</b></span><span class="cv-st">' + (b.stage != null ? K.stageDots(b.stage, true) : "") + "<i>" + b.clients + (b.clients === 1 ? " organization · " : " organizations · ") + b.n + (b.n === 1 ? " report" : " reports") + "</i></span></button>"; }).join("") + '<div class="cv-small">Counted from bill numbers written in the reports\' descriptions; reports that only describe a topic aren\'t counted.</div>') : "") +
        '<div class="cv-small">From the reports lobbyists must file each quarter under the Lobbying Disclosure Act (lda.gov, run by the Secretary of the Senate and the Clerk of the House). Organizations that lobby for themselves report their own lobbying costs; firms report what each client paid them. One report\'s amount covers everything on it, so it can\'t be split between bills. Amounts are as filed.</div></div>';
      L.querySelectorAll("[data-cl]").forEach(function (b) { b.onclick = function () { openClient(b.dataset.cl); }; });
      L.querySelectorAll("[data-is]").forEach(function (b) { b.onclick = function () { lobIssue = b.dataset.is; lobbying(L, F, q); }; });
      L.querySelectorAll("[data-b]").forEach(function (b) { b.onclick = function () { K.openBill(b.dataset.b); }; });
    });
  }
  function openClient(id) {
    var el = K.openDrawer(loading());
    api("/api/civic/lobby_client?id=" + encodeURIComponent(id)).then(function (c) {
      if (c.error) { el.innerHTML = '<div class="cv-small">Not found.</div>'; return; }
      issueNames = c.issue_names || issueNames;
      var Fl = c.filings || [], firms = {};
      Fl.forEach(function (f) { if (!f.inhouse) firms[f.registrant] = (firms[f.registrant] || 0) + (f.amount || 0); });
      var fk = Object.keys(firms).sort(function (a, b) { return firms[b] - firms[a]; });
      var per = function (p) { return { first_quarter: "Jan–Mar", second_quarter: "Apr–Jun", third_quarter: "Jul–Sep", fourth_quarter: "Oct–Dec" }[p] || p; };
      el.innerHTML = '<div class="cv-kicker">' + K.flag("US") + " LOBBYING CLIENT</div><h2>" + esc(K.nice(c.client)) + '</h2><div class="cv-meta">' + esc(c.about || "") + "</div>" +
        '<div class="gv-nums"><div class="gv-num"><div class="h">REPORTED</div><div class="v">' + usd(c.total) + '</div></div><div class="gv-num"><div class="h">REPORTS</div><div class="v">' + Fl.length + '</div></div><div class="gv-num"><div class="h">FIRMS HIRED</div><div class="v">' + fk.length + "</div></div></div>" +
        (fk.length ? sec("FIRMS IT PAID", hbars(fk.map(function (k) { return { label: K.nice(k), v: firms[k] }; }), firms[fk[0]])) : "") +
        ((c.bills || []).length ? sec("BILLS NAMED IN ITS REPORTS", c.bills.map(function (b) { return '<button class="cv-row bill mini" data-b="' + esc(b.bill) + '"><span class="cv-num">' + esc(b.num || b.bill.replace(/^US-\d+-/, "")) + '</span><span class="cv-t"><b>' + esc(b.title || "") + '</b></span><span class="cv-st">' + (b.stage != null ? K.stageDots(b.stage, true) : "") + "<i>" + b.n + " reports</i></span></button>"; }).join("")) : "") +
        sec("REPORTS", Fl.slice(0, 40).map(function (f) {
          return '<details class="gv-sub"><summary>' + f.year + " " + per(f.period) + " · " + esc(f.inhouse ? "its own lobbying" : K.nice(f.registrant)) + " · <b>" + (f.amount != null ? usd(f.amount) : "no amount") + "</b> · " + esc((f.issues || "").split(",").map(function (x) { return issueNames[x] || x; }).join(", ")) + "</summary>" +
            '<p class="cv-p">' + esc(f.text.replace(/ \|\| /g, " · ")) + "</p>" + (f.gov ? '<div class="cv-small">Contacted: ' + esc(f.gov) + "</div>" : "") +
            (f.lobbyists.length ? '<div class="cv-small">Lobbyists: ' + f.lobbyists.map(function (l) { return esc(l[0]) + (l[1] ? " (formerly " + esc(l[1]) + ")" : ""); }).join("; ") + "</div>" : "") +
            (f.url ? '<div class="cv-foot"><a href="' + esc(f.url) + '" target="_blank" rel="noopener">the report ↗</a></div>' : "") + "</details>";
        }).join("")) +
        '<div class="cv-small">"Formerly" is the past government job each lobbyist listed, as the law requires for jobs in the last 20 years.</div>';
      el.querySelectorAll("[data-b]").forEach(function (b) { b.onclick = function () { K.openBill(b.dataset.b); }; });
    });
  }

  /* ---------- stock trades ---------- */
  function trades(L, F, q, offset, redraw) {
    F.innerHTML = chips([["", "buys and sells"], ["buy", "purchases"], ["sell", "sales"]], trTx) + chips([["", "any time"], ["30", "traded in the last 30 days"], ["90", "90 days"], ["365", "a year"]], trDays, "data-dd");
    F.querySelectorAll("[data-v]").forEach(function (b) { b.onclick = function () { trTx = b.dataset.v; redraw(); }; });
    F.querySelectorAll("[data-dd]").forEach(function (b) { b.onclick = function () { trDays = b.dataset.dd; redraw(); }; });
    L.innerHTML = loading();
    api("/api/civic/trades?q=" + encodeURIComponent(q) + "&tx=" + trTx + "&days=" + trDays + "&offset=" + offset).then(function (d) {
      var T = d.trades || [], docs = d.docs || {};
      if (!d.total) { L.innerHTML = '<div class="cv-small cv-pad">' + (docs.paper || docs["new"] ? "Archie has the list of reports and is reading them now (a few dozen every few hours, so the PC stays cool)." : "Stock trade reports haven't reached Archie yet. It checks the House Clerk's disclosure site every few hours while online.") + (d.senate ? "" : ' Senators\' reports are off; turn them on in <a href="#" class="cv-src2">data sources</a>.') + "</div>"; wireSrc(L); return; }
      var top = d.top || [], act = d.active || [];
      L.innerHTML = '<div class="cv-pad2"><div class="cv-small">Members of Congress must report any stock, bond or option trade over $1,000 by them, their spouse or dependent children within 45 days (the STOCK Act). Amounts are reported only as ranges. ' +
        (d.senate ? "" : 'Senators\' reports are off; turn them on in <a href="#" class="cv-src2">data sources</a>. ') + "</div>" +
        '<div class="gv-nums"><div class="gv-num"><div class="h">TRADES IN ARCHIE</div><div class="v">' + d.total.toLocaleString() + '</div></div><div class="gv-num"><div class="h">REPORTS READ</div><div class="v">' + (docs.ok || 0).toLocaleString() + '</div></div><div class="gv-num"><div class="h">STILL TO READ</div><div class="v">' + (docs["new"] || 0) + '</div></div><div class="gv-num"><div class="h">FILED ON PAPER</div><div class="v">' + (docs.paper || 0) + ' <span class="gv-yr">scanned; open the PDF</span></div></div></div>' +
        (top.length && !offset ? '<div class="cv-two">' + sec("MOST TRADED, LAST 90 DAYS (NUMBER OF TRADES)", hbars(top.map(function (t) { return { label: t.ticker + " · " + K.nice(t.asset).replace(/\s*\([A-Z.\-]+\)\s*$/, "").slice(0, 40), v: t.n, attr: ' class="cv-click" data-tk="' + esc(t.ticker) + '"' }; }), top[0].n, function (v) { return String(v); })) +
          sec("MOST ACTIVE, LAST 90 DAYS", act.map(function (a) { return '<button class="cv-row bill mini" ' + (a.who ? 'data-m="' + esc(a.who) + '"' : "") + '><span class="cv-t"><b>' + sw(a.party) + esc(a.name) + "</b><i>" + (a.chamber === "S" ? "Senate" : "House") + '</i></span><span class="cv-st"><i>' + a.n + " trades</i></span></button>"; }).join("")) + "</div>" : "") +
        sec("TRADES" + (q ? " MATCHING " + esc(q.toUpperCase()) : "") + " · NEWEST REPORTS FIRST", '<table class="cv-ptab cv-trades"><tr><th>traded</th><th>who</th><th>whose</th><th>what</th><th></th><th>amount</th><th>reported</th></tr>' + T.map(function (t) {
          var lag = t.tx_date && t.filed ? Math.round((new Date(t.filed) - new Date(t.tx_date)) / 86400000) : null;
          return "<tr><td>" + esc(fmtDate(t.tx_date)) + '</td><td><a href="#" ' + (t.who ? 'data-m="' + esc(t.who) + '"' : "") + ">" + sw(t.party) + esc(t.label) + "</a></td><td>" + esc(t.owner || "self") + "</td><td><b>" + esc(t.ticker || "") + "</b> " + esc(t.asset.replace(/\s*\([A-Z.\-]+\)\s*$/, "").slice(0, 60)) + (t.atype ? ' <i class="cv-small">' + esc(ATYPE[t.atype] || t.atype) + "</i>" : "") +
            '</td><td><span class="cv-tx" style="background:' + (t.tx === "purchase" ? BUY : /sale/.test(t.tx) ? SELL : OTHER) + '">' + esc(t.tx) + "</span></td><td>" + esc(t.amount) + "</td><td>" + esc(fmtDate(t.filed)) + (lag != null && lag >= 0 ? ' <i class="cv-small">' + lag + " days later</i>" : "") + "</td></tr>";
        }).join("") + "</table>" + K.more(T.length, 100)) +
        '<div class="cv-small">From the Periodic Transaction Reports on the House Clerk\'s disclosure site' + (d.senate ? " and the Senate\'s eFD site" : "") + ". Archie reads the electronically filed reports; paper filings are scanned images, so they're listed with a link instead. \"Whose\" is who owned the asset: the member, their spouse, a dependent child, or jointly.</div></div>";
      L.querySelectorAll("[data-m]").forEach(function (b) { b.onclick = function (e) { e.preventDefault(); K.openMember(b.dataset.m); }; });
      L.querySelectorAll("[data-tk]").forEach(function (b) { b.onclick = function () { K.setQ(b.dataset.tk); }; });
      K.pager(L);
      wireSrc(L);
    });
  }
  function wireSrc(el) { el.querySelectorAll(".cv-src2").forEach(function (a) { a.onclick = function (e) { e.preventDefault(); K.sources(); }; }); }

  /* ================================================================ extras on existing drawers */
  function memberExtras(el, m, key) {
    var box = el.querySelector("#cv-more");
    if (!box) return;
    api("/api/civic/member_more?key=" + encodeURIComponent(key)).then(function (d) {
      var C = d.committees || [], T = d.trades || [], tk = d.tickers || [];
      var top = C.filter(function (c) { return !c.sub; }), sub = C.filter(function (c) { return c.sub; });
      var cm = C.length ? sec("COMMITTEES THEY SIT ON", '<div class="cv-cmlist">' + top.map(function (c) { return '<button class="cv-cmchip" data-cm="' + esc(c.code) + '">' + esc(c.name) + (c.title ? " <b>" + esc(c.title) + "</b>" : "") + "</button>"; }).join("") + "</div>" +
        (sub.length ? '<details class="gv-sub"><summary>' + sub.length + " subcommittees</summary>" + '<div class="cv-cmlist">' + sub.map(function (c) { return '<button class="cv-cmchip" data-cm="' + esc(c.code) + '">' + esc(c.name) + (c.title ? " <b>" + esc(c.title) + "</b>" : "") + "</button>"; }).join("") + "</div></details>" : "")) : "";
      var buys = T.filter(function (t) { return t.tx === "purchase"; }).length, sells = T.filter(function (t) { return /sale/.test(t.tx); }).length;
      var paper = (d.docs || []).filter(function (x) { return x.status === "paper"; });
      var tr = sec("STOCK TRADES THEY REPORTED" + (T.length ? " · " + T.length : ""), d.senate_off ? '<div class="cv-small">Senators\' trade reports are off in Archie; turn them on in <a href="#" class="cv-src2">data sources</a>.</div>' :
        (T.length ? '<div class="gv-nums"><div class="gv-num"><div class="h">PURCHASES</div><div class="v">' + buys + '</div></div><div class="gv-num"><div class="h">SALES</div><div class="v">' + sells + '</div></div><div class="gv-num"><div class="h">LATEST</div><div class="v cv-sm">' + esc(fmtDate(T[0].tx_date)) + "</div></div></div>" +
          (tk.length ? '<div class="cv-mh">Most traded (number of trades)</div>' + hbars(tk.slice(0, 8).map(function (t) { return { label: t.ticker + " · " + t.buys + " bought, " + t.sells + " sold", v: t.n, c: PIE[0] }; }), tk[0].n, function (v) { return String(v); }) : "") +
          '<table class="cv-ptab cv-trades"><tr><th>traded</th><th>whose</th><th>what</th><th></th><th>amount</th></tr>' + T.slice(0, 40).map(function (t) {
            return "<tr><td>" + esc(fmtDate(t.tx_date)) + "</td><td>" + esc(t.owner || "self") + "</td><td><b>" + esc(t.ticker) + "</b> " + esc(t.asset.replace(/\s*\([A-Z.\-]+\)\s*$/, "").slice(0, 50)) + (t.note ? '<div class="cv-small">' + esc(t.note.slice(0, 160)) + "</div>" : "") + '</td><td><span class="cv-tx" style="background:' + (t.tx === "purchase" ? BUY : /sale/.test(t.tx) ? SELL : OTHER) + '">' + esc(t.tx) + "</span></td><td>" + esc(t.amount) + "</td></tr>";
          }).join("") + "</table>" + (T.length > 40 ? '<div class="cv-small">Latest 40 of ' + T.length + '. All of them are in the stock trades tab.</div>' : "")
          : '<div class="cv-small">No trade reports from them in the reports Archie has read (this year and last).</div>') +
        (paper.length ? '<div class="cv-small">' + paper.length + " report" + (paper.length === 1 ? " was" : "s were") + " filed on paper: " + paper.slice(0, 6).map(function (p) { return '<a href="' + esc(p.url) + '" target="_blank" rel="noopener">' + esc(fmtDate(p.filed)) + " ↗</a>"; }).join(", ") + "</div>" : ""));
      var gifts = sec("DONATIONS FROM LOBBYISTS", '<div id="cv-ld203"><button class="cv-btn">show what lobbyists reported giving them</button><span class="cv-small">asks lda.gov; lobbyists and their groups\' PACs must report political donations twice a year</span></div>');
      box.innerHTML = cm + tr + gifts;
      box.querySelectorAll("[data-cm]").forEach(function (b) { b.onclick = function () { openCmte(b.dataset.cm); }; });
      wireSrc(box);
      var gb = box.querySelector("#cv-ld203 .cv-btn");
      gb.onclick = function () {
        var g = box.querySelector("#cv-ld203"); g.innerHTML = loading("Asking lda.gov…");
        api("/api/civic/lobby_gifts?key=" + encodeURIComponent(key)).then(function (r) {
          if (r.error) { g.innerHTML = '<div class="cv-small">' + esc(r.error) + "</div>"; return; }
          if (!r.n) { g.innerHTML = '<div class="cv-small">No donations to them in lobbyists\' ' + r.years.join(" and ") + " reports" + (r.partial ? " (lda.gov didn't answer every request; try again later)" : "") + ".</div>"; return; }
          g.innerHTML = '<div class="gv-nums"><div class="gv-num"><div class="h">REPORTED</div><div class="v">' + usd(r.total) + '</div></div><div class="gv-num"><div class="h">DONATIONS</div><div class="v">' + r.n + '</div></div><div class="gv-num"><div class="h">YEARS</div><div class="v cv-sm">' + r.years.slice().reverse().join("–") + "</div></div></div>" +
            '<div class="cv-mh">From (lobbyists and PACs)</div>' + hbars(r.from.slice(0, 12).map(function (x) { return { label: K.nice(x[0]), v: x[1] }; }), r.from[0][1]) +
            '<div class="cv-mh">By lobbying firm or group</div>' + hbars(r.firms.slice(0, 10).map(function (x) { return { label: K.nice(x[0]), v: x[1] }; }), r.firms[0][1]) +
            '<div class="cv-small">From LD-203 reports: donations to their campaign, leadership PAC or events honoring them. These overlap with the FEC figures above; they show which donations came from people and groups registered to lobby.' + (r.partial ? " Some pages didn't load; try again later." : "") + "</div>";
        });
      };
    });
  }
  function billExtras(el, b) {
    var box = el.querySelector("#cv-billmore");
    if (!box) return;
    api("/api/civic/bill_lobbying?id=" + encodeURIComponent(b.id)).then(function (d) {
      var C = d.clients || [], cm = d.committees || [];
      var cmh = cm.length ? sec("COMMITTEES IT WAS SENT TO", '<div class="cv-cmlist">' + cm.map(function (c) { return '<button class="cv-cmchip" data-cm="' + esc(c.code) + '">' + esc(c.name) + (c.date ? ' <i>' + esc(fmtDate(c.date)) + "</i>" : "") + "</button>"; }).join("") + "</div>") : "";
      var lob = sec("WHO LOBBIED ON IT" + (C.length ? " · " + C.length : ""), C.length ? hbars(C.slice(0, 12).map(function (c) { return { label: K.nice(c.client) + (c.firms.length ? " (via " + c.firms.slice(0, 2).map(K.nice).join(", ") + ")" : ""), v: c.amount, attr: ' class="cv-click" data-cl="' + c.client_id + '"' }; }), C[0].amount || 1) +
        (C.some(function (c) { return c.quote; }) ? '<details class="gv-sub"><summary>what their reports say about it</summary>' + C.filter(function (c) { return c.quote; }).slice(0, 15).map(function (c) { return '<div class="cv-quote"><b>' + esc(K.nice(c.client)) + ":</b> “" + esc(c.quote) + "”</div>"; }).join("") + "</details>" : "") +
        '<div class="cv-small">Organizations whose lobbying reports name this bill. Amounts are each report\'s total, which covers everything else on it too, so they show how big the lobbying effort was, not what was spent on this bill alone.' + (d.loading ? " Archie is still loading this year's reports, so this list will grow." : "") + "</div>"
        : '<div class="cv-small">No lobbying reports in Archie name this bill' + (d.loading ? " yet (it's still loading this year's reports)" : "") + ".</div>");
      box.innerHTML = cmh + lob;
      box.querySelectorAll("[data-cm]").forEach(function (x) { x.onclick = function () { openCmte(x.dataset.cm); }; });
      box.querySelectorAll("[data-cl]").forEach(function (x) { x.onclick = function () { openClient(x.dataset.cl); }; });
    });
  }
  function watchRow(w) {
    var n = w.now || {};
    if (w.kind === "case") return '<button class="cv-row bill" data-case="' + esc(w.id) + '"><span class="cv-num">' + K.flag("US") + ' Supreme Court</span><span class="cv-t"><b>' + esc(n.name || w.label) + "</b><i>No. " + esc(n.docket || "") + '</i></span><span class="cv-st"><i>' + esc(n.decided ? "decided " + (n.min ? n.maj + "–" + n.min : "unanimously") : n.argued ? "argued, waiting for a decision" : n.arg_next ? "argument " + fmtDate(n.arg_next) : "accepted") + '</i></span><span class="cv-d">' + esc(fmtDate(n.decided || n.argued || n.arg_next)) + "</span></button>";
    return '<button class="cv-row bill" data-cm="' + esc(w.id) + '"><span class="cv-num">' + K.flag("US") + " " + esc((n.chamber || "") + " committee") + '</span><span class="cv-t"><b>' + esc(n.name || w.label) + '</b></span><span class="cv-st"></span><span class="cv-d"></span></button>';
  }
  function wireWatchRows(L) {
    L.querySelectorAll("[data-case]").forEach(function (b) { b.onclick = function () { openCase(b.dataset.case); }; });
    L.querySelectorAll("[data-cm]").forEach(function (b) { b.onclick = function () { openCmte(b.dataset.cm); }; });
  }
  function sourcesExtra(el, ov) {
    var m = (ov && ov.more) || {};
    var box = document.createElement("div");
    box.innerHTML = sec("SENATORS' STOCK TRADES", '<div class="cv-small">Senators file their trade reports on the Senate\'s eFD site, which asks every visitor to accept its terms first: the reports can\'t be used for any unlawful purpose, for commercial purposes (other than news), to judge anyone\'s credit, or to solicit money. If you turn this on, Archie accepts those terms on your behalf each time it checks, and uses the reports only to show them to you here.</div>' +
      '<label class="cv-tog"><input type="checkbox" id="cv-efd"' + (m.senate_efd ? " checked" : "") + "> read senators' trade reports from efdsearch.senate.gov</label><div class=\"cv-small\" id=\"cv-efdmsg\"></div>") +
      sec("LOBBYING: OPTIONAL FREE KEY", '<div class="cv-small">Without a key, lda.gov lets Archie read about 15 pages a minute, so a year of reports takes a day or two to load. A free key from lda.gov (register, then "API key") makes it several times faster.</div>' +
        '<div class="cv-keyrow"><label>lda.gov API key</label><input id="cv-lda" placeholder="' + (m.lda_key ? "saved; paste a new one to replace it" : "paste your key") + '"><button class="cv-btn" id="cv-ldasave">save</button></div><div class="cv-small" id="cv-ldamsg"></div>');
    el.appendChild(box);
    box.querySelector("#cv-efd").onchange = function () { var on = this.checked; api("/api/civic/settings", { senate_efd: on }).then(function (d) { box.querySelector("#cv-efdmsg").textContent = d.senate_efd ? "On. Archie starts reading senators' reports at its next check (every few hours)." : "Off."; }); };
    box.querySelector("#cv-ldasave").onclick = function () { var v = box.querySelector("#cv-lda").value.trim(); if (!v) return; api("/api/civic/settings", { lda_key: v }).then(function (d) { box.querySelector("#cv-ldamsg").textContent = d.lda_key ? "Saved on this PC." : "Couldn't save."; }); };
  }
  function open(kind, id) {
    if (kind === "case") openCase(id); else if (kind === "justice") openJustice(id); else if (kind === "judge") openJudge(id); else if (kind === "cmte") openCmte(id); else if (kind === "client") openClient(id); else return false;
    return true;
  }
  return { subs: SUBS, has: function (s) { return SUBS.some(function (x) { return x[0] === s; }); }, list: list, open: open, memberExtras: memberExtras, billExtras: billExtras,
           justiceInto: justiceInto, watchRow: watchRow, wireWatchRows: wireWatchRows, sourcesExtra: sourcesExtra,
           placeholder: function (s) { return { courts: courtView === "judges" ? "find a judge or court…" : "", committees: "find a committee or chair…", lobbying: "search clients, firms, bill numbers…", trades: "find a ticker, company or person…" }[s] || ""; } };
};
