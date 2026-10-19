/* Archie World: lawmaking, part three. What was said on the floor (UK Hansard, the US Congressional Record), UK money
   (donations register, Register of Interests), your state legislature's votes, and election night.
   Mixed into civic.js. Public record only: no scores, ratings or labels on anyone. */
window.ArchieCivicExtra = function (K) {
  "use strict";
  var esc = K.esc, api = K.api, sec = K.sec, loading = K.loading, fmtDate = K.fmtDate, usd = K.usd, pct = K.pct;
  var PIE = K.PIE, OTHER = K.OTHER;
  var elTimer = null;
  function gbp(v) { if (v == null) return "—"; var a = Math.abs(v); return "£" + (a >= 1e6 ? (v / 1e6).toFixed(2) + "M" : a >= 1e3 ? (v / 1e3).toFixed(a >= 1e4 ? 0 : 1) + "K" : Math.round(v)); }
  function hl(text, q) {
    var t = esc(text || "");
    if (!q) return t;
    try { return t.replace(new RegExp("(" + q.replace(/[.*+?^${}()|[\]\\]/g, "\\$&").replace(/\s+/g, "\\s+") + ")", "gi"), "<mark>$1</mark>"); } catch (e) { return t; }
  }
  function ago(ts) { if (!ts) return ""; var m = Math.round((Date.now() / 1000 - ts) / 60); return m < 1 ? "just now" : m < 60 ? m + " min ago" : m < 1440 ? Math.round(m / 60) + " h ago" : Math.round(m / 1440) + " days ago"; }

  /* ================================================================ debates */
  function debatesList(cc, L, F, q) {
    var ex = cc === "GB" ? ["cost of living", "Ukraine", "NHS waiting lists", "small boats", "steel"] : ["tariffs", "border", "Social Security", "artificial intelligence", "farm bill"];
    F.innerHTML = '<div class="cv-small">' + (cc === "GB" ? "Everything said in the Commons and the Lords, word for word, from Hansard (the official record)." : "Everything said on the House and Senate floors, from the Congressional Record (published by the Government Publishing Office).") +
      " Type in the search box above, or try: " + ex.map(function (x) { return '<a href="#" class="cv-ex">' + esc(x) + "</a>"; }).join(" · ") + "</div>";
    F.querySelectorAll(".cv-ex").forEach(function (a) { a.onclick = function (e) { e.preventDefault(); K.setQ(a.textContent); }; });
    if (!q) { L.innerHTML = ""; return; }
    L.innerHTML = loading("Searching " + (cc === "GB" ? "Hansard" : "the Congressional Record") + "…");
    api("/api/civic/debates?cc=" + cc + "&q=" + encodeURIComponent(q)).then(function (d) { drawDebates(L, d, cc, q); });
  }
  function drawDebates(L, d, cc, q, compact) {
    if (d.error) { L.innerHTML = '<div class="cv-small cv-pad">' + esc(d.error) + "</div>"; return; }
    var I = d.items || [];
    if (!I.length) { L.innerHTML = '<div class="cv-small cv-pad">Nothing found.</div>'; return; }
    L.innerHTML = (compact ? "" : '<div class="cv-small cv-pad">' + (d.total || I.length).toLocaleString() + " results, newest first, from " + esc(d.source || "") + ".</div>") +
      I.map(function (r, i) {
        return '<div class="cv-speech"><div class="cv-sph"><span class="cv-d">' + esc(fmtDate(r.date)) + "</span>" + (r.who ? (r.member ? '<a href="#" data-m="' + esc(r.member) + '"><b>' + esc(r.who) + "</b></a>" : "<b>" + esc(r.who) + "</b>") : "") +
          '<i>' + esc([r.house, r.where, r.section].filter(Boolean).join(" · ")) + '</i><a href="' + esc(r.url) + '" target="_blank" rel="noopener" class="cv-ext">↗</a></div>' +
          (r.text ? '<p class="cv-p">' + hl(r.text.length > 700 ? r.text.slice(0, 700) + "…" : r.text, q) + "</p>" : '<button class="cv-btn" data-g="' + i + '">show what was said</button>') + "</div>";
      }).join("");
    L.querySelectorAll("[data-m]").forEach(function (a) { a.onclick = function (e) { e.preventDefault(); K.openMember(a.dataset.m); }; });
    L.querySelectorAll("[data-g]").forEach(function (b) {
      b.onclick = function () {
        var r = I[+b.dataset.g]; b.disabled = true; b.textContent = "loading…";
        api("/api/civic/debate_text?package=" + encodeURIComponent(r.package) + "&granule=" + encodeURIComponent(r.granule) + "&q=" + encodeURIComponent(q || "")).then(function (t) {
          var p = document.createElement("div");
          p.innerHTML = t.error ? '<div class="cv-small">' + esc(t.error) + "</div>" : (t.speakers && t.speakers.length ? '<div class="cv-small">Speakers: ' + esc(t.speakers.join(", ")) + "</div>" : "") + '<p class="cv-p">' + (t.from ? "…" : "") + hl(t.text, q) + (t.length > t.from + 2400 ? "…" : "") + "</p>";
          b.replaceWith(p);
        });
      };
    });
  }
  function saidInto(box, cc, key) {
    box.innerHTML = '<button class="cv-btn">show their latest speeches</button><span class="cv-small">' + (cc === "GB" ? "from Hansard" : "from the Congressional Record") + "</span>";
    box.querySelector(".cv-btn").onclick = function () {
      box.innerHTML = loading();
      api("/api/civic/debates?cc=" + cc + "&key=" + encodeURIComponent(key)).then(function (d) {
        var inner = document.createElement("div"); box.innerHTML = ""; box.appendChild(inner);
        if (d.items) d.items = d.items.slice(0, 12);
        drawDebates(inner, d, cc, "", true);
        if (d.total > 12) box.insertAdjacentHTML("beforeend", '<div class="cv-small">Latest 12 of ' + d.total.toLocaleString() + ". Search everything in the <b>what was said</b> tab.</div>");
      });
    };
  }

  /* ================================================================ UK money */
  function ukMoney(box, key) {
    box.innerHTML = loading("Asking the Electoral Commission and the Register of Interests…");
    api("/api/civic/uk_money?key=" + encodeURIComponent(key)).then(function (d) {
      if (d.error) { box.innerHTML = '<div class="cv-small">' + esc(d.error) + "</div>"; return; }
      var D = d.donations || [], tot = D.reduce(function (a, x) { return a + (x.value || 0); }, 0), by = {};
      D.forEach(function (x) { by[x.donor] = (by[x.donor] || 0) + (x.value || 0); });
      var keys = Object.keys(by).sort(function (a, b) { return by[b] - by[a]; });
      var sl = keys.slice(0, 6).map(function (k, i) { return { label: k, v: by[k], c: PIE[i] }; });
      var rest = keys.slice(6).reduce(function (a, k) { return a + by[k]; }, 0);
      if (rest > 0) sl.push({ label: (keys.length - 6) + " other donors", v: rest, c: OTHER });
      var I = d.interests || [], cats = {};
      I.forEach(function (x) { (cats[x.category] = cats[x.category] || []).push(x); });
      box.innerHTML = '<div class="cv-mh">DONATIONS REPORTED TO THE ELECTORAL COMMISSION</div>' +
        (D.length ? '<div class="gv-nums"><div class="gv-num"><div class="h">TOTAL</div><div class="v">' + gbp(tot) + '</div></div><div class="gv-num"><div class="h">DONATIONS</div><div class="v">' + D.length + '</div></div><div class="gv-num"><div class="h">DONORS</div><div class="v">' + keys.length + "</div></div></div>" +
          '<div class="cv-pierow">' + K.pie(sl.map(function (s) { return { label: s.label, v: s.v, c: s.c }; }), 140) + K.legend(sl.map(function (s) { return { label: s.label, v: s.v, c: s.c }; })).replace(/\$/g, "£") + "</div>" +
          '<details class="gv-sub"><summary>every donation</summary><table class="cv-ptab money"><tr><th>date</th><th>donor</th><th>what</th><th>value</th></tr>' + D.map(function (x) { return "<tr><td>" + esc(fmtDate(x.date)) + "</td><td>" + esc(x.donor) + ' <i class="cv-small">' + esc(x.status) + "</i></td><td>" + esc([x.type, x.nature].filter(Boolean).join(": ")) + "</td><td>" + gbp(x.value) + "</td></tr>"; }).join("") + "</table></details>"
          : '<div class="cv-small">No donations to them in the register.</div>') +
        '<div class="cv-mh">REGISTER OF MEMBERS\' INTERESTS</div>' +
        (I.length ? Object.keys(cats).map(function (c) {
          return '<details class="gv-sub"><summary>' + esc(c) + " · " + cats[c].length + "</summary>" + cats[c].map(function (x) {
            return '<div class="cv-int"><b>' + esc(x.summary) + "</b>" + (x.registered ? ' <i class="cv-small">registered ' + esc(fmtDate(x.registered)) + "</i>" : "") +
              (x.fields.length ? '<div class="cv-small">' + x.fields.map(function (f) { return esc(f[0]) + ": " + esc(f[1]); }).join("<br>") + "</div>" : "") + "</div>";
          }).join("") + "</details>";
        }).join("") : '<div class="cv-small">Nothing registered (peers use a separate register that isn\'t in this feed yet).</div>') +
        '<div class="cv-small">Donations: the Electoral Commission\'s register (gifts over £500 to MPs and parties must be reported). Interests: the House of Commons Register of Members\' Financial Interests (paid jobs, gifts, trips abroad, shareholdings, property). Matched by name, so check the details.' + (d.errors && d.errors.length ? " Some of it didn't load: " + esc(d.errors.join("; ")) : "") + "</div>";
    });
  }

  /* ================================================================ my state legislature */
  function stateVotes(box) {
    api("/api/civic/state_votes").then(function (d) {
      if (!d.state) { box.innerHTML = ""; return; }
      if (!d.key) { box.innerHTML = '<div class="cv-small">How your state lawmakers vote comes from Open States, which needs a free key: sign up at open.pluralpolicy.com (Open States\' home), copy your API key from your profile page, and paste it under Lawmaking › data sources and status.</div>'; return; }
      var V = d.votes || [];
      if (!V.length) { box.innerHTML = '<div class="cv-small">No recorded votes from the ' + esc(d.state) + " legislature have reached Archie yet. It checks every few hours while online.</div>"; return; }
      var P = { Y: ["yes", "#1fa67a"], N: ["no", "#9085e9"], A: ["abstain", "#8d927f"], X: ["absent", "#3b4033"], O: ["other", "#5e6352"] };
      box.innerHTML = '<div class="cv-mh">RECENT VOTES IN YOUR STATE CAPITOL</div>' + V.slice(0, 25).map(function (v) {
        return '<button class="cv-row vote mini" data-v="' + esc(v.id) + '"><span class="cv-d">' + esc(fmtDate(v.date)) + '</span><span class="cv-t"><b>' + esc(v.title) + "</b><i>" + esc([v.question, v.result].filter(Boolean).join(" · ")) + "</i></span><span class=\"cv-vr\">" +
          v.mine.map(function (m) { var p = P[m.pos] || P.O; return '<span class="cv-pos" style="background:' + p[1] + '" title="' + esc(m.name) + '">' + esc(m.name.split(" ").slice(-1)[0]) + ": " + p[0] + "</span>"; }).join(" ") +
          '<span class="cv-tnum">' + (v.yes || 0) + "–" + (v.no || 0) + "</span></span></button>";
      }).join("") + '<div class="cv-small">From Open States. Your two state lawmakers\' votes are shown on each line when they voted.</div>';
      box.querySelectorAll("[data-v]").forEach(function (b) { b.onclick = function () { K.openVote(b.dataset.v); }; });
    });
  }

  /* ================================================================ election night */
  // English party names as Wikipedia writes them, by family. Only the US uses the US party colors, so a
  // "Social Democratic Party" in Sweden isn't painted like the US Democrats.
  var EN = [[/social democrat|labour|socialist|workers'? party|arbeider/i, "#e4002b"], [/sweden democrats|danish people|finns party|national rally|freedom party|reform uk|alternative for/i, "#1f3f8f"],
    [/moderate party|conservative|christian democratic union|people's party|republicans \(france\)|national party/i, "#1d84ce"], [/green|ecolog/i, "#4caf50"], [/left party|left alliance|die linke|communist/i, "#a3172b"],
    [/centre party|center party|agrarian/i, "#00843d"], [/christian democrat/i, "#26326e"], [/liberal|free democratic/i, "#f0b323"], [/progress party/i, "#004f80"], [/pirate/i, "#7d2e8e"], [/independent/i, "#8d927f"]];
  var CUR_CC = "";
  function colorOf(r, i) {
    var n = r.party || r.candidate || "";
    if (/^[0-9a-f]{6}$/i.test(r.color || "")) return "#" + r.color;
    var c = window.archiePartyColor(n, null);
    if (c && (CUR_CC === "US" || !/democrat|republican/i.test(n))) return c;
    for (var k = 0; k < EN.length; k++) if (EN[k][0].test(n)) return EN[k][1];
    return PIE[i % PIE.length];
  }
  function resultBar(data) {
    var R = (data.rows || []).filter(function (r) { return r.seats != null || r.electoral != null || r.pct != null; });
    if (!R.length) return "";
    var useSeats = R.some(function (r) { return r.seats != null; }), useEv = !useSeats && R.some(function (r) { return r.electoral != null; });
    var val = function (r) { return useSeats ? (r.seats || 0) : useEv ? (r.electoral || 0) : (r.pct || 0); };
    var tot = useSeats && data.seats_total ? Math.max(data.seats_total, R.reduce(function (a, r) { return a + val(r); }, 0)) : R.reduce(function (a, r) { return a + val(r); }, 0) || 1;
    var maj = useSeats && data.majority ? data.majority : null;
    return '<div class="el-bar">' + R.map(function (r, i) { var v = val(r); return v ? '<i style="width:' + (100 * v / tot) + "%;background:" + colorOf(r, i) + '" title="' + esc((r.party || r.candidate) + ": " + v + (useSeats ? " seats" : useEv ? " electoral votes" : "%")) + '"></i>' : ""; }).join("") +
      (maj ? '<b class="el-maj" style="left:' + (100 * maj / tot) + '%" title="majority: ' + maj + '"></b>' : "") + "</div>" +
      '<div class="cv-small">' + (useSeats ? "Seats" + (data.seats_total ? " out of " + data.seats_total : "") + (maj ? "; " + maj + " for a majority (the line)" : "") : useEv ? "Electoral votes" : "Share of the vote") + "</div>";
  }
  function blocs(data) {
    var B = {}, any = false;
    (data.rows || []).forEach(function (r) { if (r.bloc) { any = true; B[r.bloc] = (B[r.bloc] || 0) + (r.seats || 0); } });
    if (!any) return "";
    var keys = Object.keys(B).sort(function (a, b) { return B[b] - B[a]; });
    return '<div class="cv-small"><b>Sides (alliances, as Wikipedia lists them):</b> ' + keys.map(function (k) { return esc(k) + " " + B[k] + (data.majority ? (B[k] >= data.majority ? " (majority)" : "") : ""); }).join(" · ") + "</div>";
  }
  function table(data) {
    var R = data.rows || [];
    if (!R.length) return "";
    var hasSeats = R.some(function (r) { return r.seats != null; }), hasEv = R.some(function (r) { return r.electoral != null; }), hasV = R.some(function (r) { return r.votes != null; }), hasP = R.some(function (r) { return r.pct != null; });
    var sg = function (n, suf) { return n == null ? "" : ' <i class="' + (n > 0 ? "el-up" : n < 0 ? "el-dn" : "") + '">' + (n > 0 ? "+" : n < 0 ? "−" : "±") + Math.abs(n) + (suf || "") + "</i>"; };
    return '<table class="cv-ptab el-tab"><tr><th>party / candidate</th>' + (hasSeats ? "<th>seats</th>" : "") + (hasEv ? "<th>electoral votes</th>" : "") + (hasV ? "<th>votes</th>" : "") + (hasP ? "<th>%</th>" : "") + "</tr>" +
      R.map(function (r, i) {
        return "<tr><td><i class=\"cv-sw\" style=\"background:" + colorOf(r, i) + '"></i>' + esc(r.party || r.candidate) + (r.candidate && r.party ? ' <span class="cv-small">' + esc(r.candidate) + "</span>" : r.leader ? ' <span class="cv-small">' + esc(r.leader) + "</span>" : "") + (r.bloc ? ' <span class="cv-small">· ' + esc(r.bloc) + "</span>" : "") + "</td>" +
          (hasSeats ? "<td>" + (r.seats != null ? r.seats : "—") + sg(r.change) + "</td>" : "") + (hasEv ? "<td>" + (r.electoral != null ? r.electoral : "—") + "</td>" : "") +
          (hasV ? "<td>" + (r.votes != null ? r.votes.toLocaleString() : "—") + "</td>" : "") + (hasP ? "<td>" + (r.pct != null ? r.pct + "%" : "—") + sg(r.swing, "") + "</td>" : "") + "</tr>";
      }).join("") + "</table>";
  }
  function elections(body) {
    body.innerHTML = '<div class="cv-cal" id="el-box">' + loading("Loading elections…") + "</div>";
    var draw = function () {
      var box = body.querySelector("#el-box"); if (!box) { clearInterval(elTimer); return; }
      api("/api/civic/elections").then(function (d) {
        var E = d.elections || [];
        var now = E.filter(function (e) { return e.age != null && e.age >= -1 && e.age <= 4; }), past = E.filter(function (e) { return e.age > 4; }).reverse(), next = E.filter(function (e) { return e.age < -1; });
        var card = function (e) {
          var T = e.top || []; CUR_CC = e.cc || "";
          return '<button class="el-card" data-e="' + esc(e.id) + '">' + (e.cc ? K.flag(e.cc) : "") + "<b>" + esc(e.title) + '</b><i>' + esc(fmtDate(e.date)) + (e.age === 0 ? " · today" : e.age === -1 ? " · tomorrow" : "") + "</i>" +
            (e.results ? '<span class="el-top">' + T.map(function (r, i) { return '<span><i class="cv-sw" style="background:' + colorOf(r, i) + '"></i>' + esc(r.party || r.candidate) + " <b>" + (r.seats != null ? r.seats : r.electoral != null ? r.electoral : r.pct + "%") + "</b></span>"; }).join("") + "</span>"
              : '<span class="cv-small">' + (e.age != null && e.age >= 0 ? "no results posted yet" : "results show here once counting starts") + "</span>") + "</button>";
        };
        box.innerHTML = '<div class="cv-calhead"><h2>Election night</h2><div class="cv-small">National elections around the world, with results as they come in. Results come from each election\'s Wikipedia article, which volunteers update from the official count, usually within minutes; Archie checks every 10 minutes from election day until a few days after. Always check the official results for anything important.</div></div>' +
          (now.length ? '<div class="cv-mh">HAPPENING NOW OR JUST HAPPENED</div><div class="el-cards">' + now.map(card).join("") + "</div>" : "") +
          (next.length ? '<div class="cv-mh">COMING UP</div><div class="el-cards">' + next.slice(0, 40).map(card).join("") + "</div>" : "") +
          (past.length ? '<div class="cv-mh">RECENT RESULTS (LAST TWO MONTHS)</div><div class="el-cards">' + past.map(card).join("") + "</div>" : "") +
          (!E.length ? '<div class="cv-small cv-pad">The list of elections hasn\'t downloaded yet. It comes from Wikidata a minute or two after Archie starts, while online.</div>' : "");
        box.querySelectorAll("[data-e]").forEach(function (b) { b.onclick = function () { openElection(b.dataset.e); }; });
      });
    };
    draw();
    clearInterval(elTimer); elTimer = setInterval(draw, 120000);
  }
  function openElection(id) {
    var el = K.openDrawer(loading("Getting the latest count…"));
    api("/api/civic/elections?id=" + encodeURIComponent(id)).then(function (e) {
      if (e.error) { el.innerHTML = '<div class="cv-small">Not found.</div>'; return; }
      var d = e.data || {}; CUR_CC = e.cc || "";
      el.innerHTML = '<div class="cv-kicker">' + (e.cc ? K.flag(e.cc) : "") + " " + esc((e.country || "").toUpperCase()) + " · ELECTION · " + esc(fmtDate(e.date)) + "</div><h2>" + esc(e.title) + "</h2>" +
        '<div class="cv-meta">' + [d.type, d.turnout ? "turnout " + esc(d.turnout) : "", "updated " + ago(e.at)].filter(Boolean).join(" · ") + "</div>" +
        (d.results ? sec("THE RESULT SO FAR", resultBar(d) + blocs(d) + table(d) + (d.after ? '<div class="cv-small">' + esc((d.title_after || "Leader") + " after the election: " + d.after) + "</div>" : "")) :
          sec("WHO'S RUNNING", table(d) || '<div class="cv-small">No line-up posted yet.</div>') + '<div class="cv-small">Results show here once counting starts.</div>') +
        '<div class="cv-small">From Wikipedia\'s article on this election, kept up to date by volunteers from the official count. Changes are shown against the last election.</div>' +
        '<div class="cv-foot"><a href="' + esc(e.url) + '" target="_blank" rel="noopener">the full article ↗</a></div>';
    });
  }

  /* ================================================================ data sources: Open States key */
  function sourcesExtra(el, ov) {
    var k = (ov && ov.keys) || {};
    var box = document.createElement("div");
    box.innerHTML = sec("YOUR STATE LEGISLATURE: FREE KEY", '<div class="cv-small">How your state senator and representative vote comes from Open States (a free, nonpartisan project). It needs a free key: sign up at open.pluralpolicy.com, then copy the API key from your profile page. Archie only asks about your own state (set in my reps).</div>' +
      '<div class="cv-keyrow"><label>Open States API key</label><input id="cv-os" placeholder="' + (k.openstates ? "saved; paste a new one to replace it" : "paste your key") + '"><button class="cv-btn" id="cv-ossave">save</button></div><div class="cv-small" id="cv-osmsg"></div>');
    box.innerHTML += sec("AUSTRALIA: FREE KEY", '<div class="cv-small">How Australia\'s MPs and senators vote comes from They Vote For You (a nonpartisan project by the OpenAustralia Foundation, built on the official Hansard records). It needs a free key: sign up at theyvoteforyou.org.au, then open "API" from your account page and copy the key. Archie only uses its plain vote records, not its policy summaries.</div>' +
      '<div class="cv-keyrow"><label>They Vote For You key</label><input id="cv-au" placeholder="' + (k.tvfy ? "saved; paste a new one to replace it" : "paste your key") + '"><button class="cv-btn" id="cv-ausave">save</button></div><div class="cv-small" id="cv-aumsg"></div>');
    el.appendChild(box);
    box.querySelector("#cv-ausave").onclick = function () { var v = box.querySelector("#cv-au").value.trim(); if (!v) return; api("/api/civic/settings", { tvfy_key: v }).then(function (d) { box.querySelector("#cv-aumsg").textContent = d.tvfy_key ? "Saved on this PC. Australia's votes start loading at the next check (within a few hours)." : "Couldn't save."; }); };
    box.querySelector("#cv-ossave").onclick = function () { var v = box.querySelector("#cv-os").value.trim(); if (!v) return; api("/api/civic/settings", { openstates_key: v }).then(function (d) { box.querySelector("#cv-osmsg").textContent = d.openstates_key ? "Saved on this PC. Your state's votes start loading at the next check (within a few hours)." : "Couldn't save."; }); };
  }

  return { debatesList: debatesList, saidInto: saidInto, ukMoney: ukMoney, stateVotes: stateVotes, elections: elections, openElection: openElection, sourcesExtra: sourcesExtra };
};
