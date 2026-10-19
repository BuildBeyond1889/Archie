/* Archie World: lawmaking, part five. Local government anywhere in the US (pick a state and county; follow the county,
   towns, cities and villages; Archie watches the pages where each posts agendas and minutes, reads them, pulls out the
   motions and votes, and explains them), and US bill versions side by side. Mixed into civic.js.
   Public record only: no scores, ratings or labels on anyone. */
window.ArchieCivicLocal = function (K) {
  "use strict";
  var esc = K.esc, api = K.api, sec = K.sec, loading = K.loading, fmtDate = K.fmtDate;
  var STATES = { AL: "Alabama", AK: "Alaska", AZ: "Arizona", AR: "Arkansas", CA: "California", CO: "Colorado", CT: "Connecticut", DE: "Delaware", DC: "District of Columbia", FL: "Florida", GA: "Georgia",
    HI: "Hawaii", ID: "Idaho", IL: "Illinois", IN: "Indiana", IA: "Iowa", KS: "Kansas", KY: "Kentucky", LA: "Louisiana", ME: "Maine", MD: "Maryland", MA: "Massachusetts", MI: "Michigan", MN: "Minnesota",
    MS: "Mississippi", MO: "Missouri", MT: "Montana", NE: "Nebraska", NV: "Nevada", NH: "New Hampshire", NJ: "New Jersey", NM: "New Mexico", NY: "New York", NC: "North Carolina", ND: "North Dakota",
    OH: "Ohio", OK: "Oklahoma", OR: "Oregon", PA: "Pennsylvania", RI: "Rhode Island", SC: "South Carolina", SD: "South Dakota", TN: "Tennessee", TX: "Texas", UT: "Utah", VT: "Vermont", VA: "Virginia",
    WA: "Washington", WV: "West Virginia", WI: "Wisconsin", WY: "Wyoming" };
  var COUNTIES = null, cur = { st: "", fips: "", body: "" }, places = null;
  var KC = { agenda: "#7ec8ff", minutes: "#c5f05a", resolution: "#ffc85a", document: "#a9b0a0" };
  function store(k, v) { try { if (v === undefined) return localStorage.getItem(k); localStorage.setItem(k, v); } catch (e) { return null; } }
  function ago(ts) { if (!ts) return "never"; var m = Math.round((Date.now() / 1000 - ts) / 60); return m < 1 ? "just now" : m < 60 ? m + " min ago" : m < 1440 ? Math.round(m / 60) + " h ago" : Math.round(m / 1440) + " days ago"; }
  function kindChip(k) { return '<span class="lc-k" style="color:' + (KC[k] || KC.document) + ";border-color:" + (KC[k] || KC.document) + '">' + esc(k || "document") + "</span>"; }
  function counties() { return COUNTIES ? Promise.resolve(COUNTIES) : fetch("/web/data/us_counties.json").then(function (r) { return r.json(); }).then(function (d) { COUNTIES = d; return d; }); }

  /* ================================================================ the local screen */
  function local(body, open) {
    body.innerHTML = '<div class="gv-left cv-left lc-left"><div class="cv-lh">LOCAL GOVERNMENT</div><div class="lc-pick"><select id="lc-st"><option value="">state…</option>' +
      Object.keys(STATES).sort(function (a, b) { return STATES[a].localeCompare(STATES[b]); }).map(function (k) { return '<option value="' + k + '">' + esc(STATES[k]) + "</option>"; }).join("") +
      '</select><select id="lc-co"><option value="">county…</option></select></div><div class="gv-list" id="lc-pl"></div>' +
      '<div class="cv-lfoot">Counties, towns, cities and villages from Wikidata. Follow the ones you care about and Archie checks where each posts its agendas and minutes twice a day.</div></div>' +
      '<div class="cv-main"><div class="cv-top"><b id="lc-title">Your places</b><input id="lc-q" placeholder="search the agendas and minutes Archie has read…"><span class="cv-note" id="lc-note"></span></div><div class="cv-list lc-main" id="lc-body"></div></div>';
    var st = body.querySelector("#lc-st"), co = body.querySelector("#lc-co");
    var pick = function (s, f) {
      cur.st = s; store("archieLocalSt", s);
      return counties().then(function (C) {
        var L = C[s] || [];
        co.innerHTML = '<option value="">county… (' + L.length + ")</option>" + L.map(function (c) { return '<option value="' + c[0] + '">' + esc(c[1]) + "</option>"; }).join("");
        if (f && L.some(function (c) { return c[0] === f; })) { co.value = f; loadPlaces(body, f); } else body.querySelector("#lc-pl").innerHTML = '<div class="cv-small cv-pad">Pick a county.</div>';
      });
    };
    st.onchange = function () { pick(st.value, ""); };
    co.onchange = function () { if (co.value) { store("archieLocalFips", co.value); loadPlaces(body, co.value); } };
    var qi = body.querySelector("#lc-q"), qt = null;
    qi.oninput = function () { clearTimeout(qt); qt = setTimeout(function () { if (qi.value.trim().length >= 3) search(body, qi.value.trim()); else if (!qi.value.trim()) feed(body); }, 350); };
    var s0 = store("archieLocalSt") || "", f0 = store("archieLocalFips") || "";
    var start = function (s) { if (s) { st.value = s; pick(s, f0); } else body.querySelector("#lc-pl").innerHTML = '<div class="cv-small cv-pad">Pick a state, then a county.</div>'; };
    if (s0) start(s0); else api("/api/civic/myreps").then(function (d) { start(((d && d.home) || {}).state || ""); }).catch(function () { start(""); });
    if (open) openBody(body, open); else feed(body);
  }
  function loadPlaces(body, fips, refresh) {
    cur.fips = fips;
    var L = body.querySelector("#lc-pl"); L.innerHTML = loading("Asking Wikidata for the towns and cities…");
    api("/api/civic/local_places?fips=" + fips + (refresh ? "&refresh=1" : "")).then(function (d) {
      if (d.error) { L.innerHTML = '<div class="cv-small cv-pad">' + esc(d.error) + "</div>"; return; }
      places = d;
      var P = d.places.slice().sort(function (a, b) { return (b.followed - a.followed) || (a.kind === "county" ? -1 : b.kind === "county" ? 1 : 0); });
      L.innerHTML = P.map(function (p) {
        return '<button class="gv-row lc-place' + (p.followed ? " on" : "") + '" data-id="' + esc(p.id) + '"><span class="lc-star">' + (p.followed ? "★" : "☆") + "</span><div><b>" + esc(p.kind === "county" ? p.name : p.name) + "</b><span>" +
          esc([p.kind === "county" ? "county government" : p.kind, p.pop ? p.pop.toLocaleString() + " people" : "", p.followed ? (p.found ? p.found + " documents" : p.note ? "needs a hand" : "checking…") : ""].filter(Boolean).join(" · ")) + "</span></div></button>";
      }).join("") + '<div class="lc-add"><details><summary>+ add a board yourself (school board, fire district, planning board…)</summary><div class="cv-keyrow"><input id="lc-an" placeholder="name, e.g. Lincoln High school board"><input id="lc-au" placeholder="page where it posts agendas or minutes (https://…)"><button class="cv-btn" id="lc-ab">add</button></div></details>' +
        '<a href="#" id="lc-rf" class="cv-small">refresh this list</a></div>';
      L.querySelectorAll(".lc-place").forEach(function (b) { b.onclick = function () { openBody(body, b.dataset.id); }; });
      L.querySelector("#lc-rf").onclick = function (e) { e.preventDefault(); loadPlaces(body, fips, true); };
      L.querySelector("#lc-ab").onclick = function () {
        var n = L.querySelector("#lc-an").value.trim(), u = L.querySelector("#lc-au").value.trim(); if (!n || !u) return;
        api("/api/civic/local_follow", { custom_name: n, meetings_url: u, website: u, fips: fips, st: d.st, kind: "board", on: true }).then(function (r) { if (r.error) { alertBox(body, r.error); return; } loadPlaces(body, fips); openBody(body, r.id); });
      };
    });
  }
  function alertBox(body, t) { var n = body.querySelector("#lc-note"); if (n) n.textContent = t; }
  function placeOf(id) { return places && places.places.find(function (p) { return p.id === id; }); }

  function feed(body) {
    cur.body = "";
    body.querySelector("#lc-title").textContent = "Your places";
    var B = body.querySelector("#lc-body"); B.innerHTML = loading();
    api("/api/civic/local_feed").then(function (d) {
      if (!d.bodies.length) { B.innerHTML = '<div class="lc-empty"><h3>Follow your county, town or village</h3><p class="cv-small">Pick a state and county on the left, then click a place and press <b>☆ follow</b>. Archie finds the page on its website where it posts meeting agendas and minutes, checks it twice a day, and lets you know when something new goes up. It reads the documents and pulls out the motions and votes recorded in the minutes.</p><p class="cv-small">Small towns mostly post PDFs on their own websites, so Archie has to find the right page. If it can\'t, you can paste the page in yourself.</p></div>'; return; }
      B.innerHTML = sec("FOLLOWING · " + d.bodies.length, '<div class="lc-fol">' + d.bodies.map(function (b) { return '<button class="lc-chip" data-id="' + esc(b.id) + '"><b>' + esc(b.name) + "</b><span>" + (b.found ? b.found + " documents" : b.note ? "needs a hand" : "checking…") + " · checked " + esc(ago(b.checked)) + "</span></button>"; }).join("") + "</div>") +
        sec("LATEST AGENDAS AND MINUTES", d.docs.length ? docRows(d.docs, true) : '<div class="cv-small">Nothing found yet. Archie checks a few minutes after you follow a place.</div>');
      B.querySelectorAll(".lc-chip").forEach(function (b) { b.onclick = function () { openBody(body, b.dataset.id); }; });
      wireDocs(B);
    });
  }
  function docRows(D, withBody) {
    return D.map(function (x) {
      return '<button class="cv-row lc-doc" data-d="' + esc(x.id) + '"><span class="cv-d">' + esc(x.date ? fmtDate(x.date) : x.posted ? "posted " + fmtDate(x.posted) : "date?") + "</span><span class=\"cv-t\"><b>" + esc(x.title) + "</b>" +
        (withBody ? "<i>" + esc(x.body_name || "") + "</i>" : "") + "</span>" + kindChip(x.kind) + "</button>";
    }).join("");
  }
  function wireDocs(el) { el.querySelectorAll(".lc-doc").forEach(function (b) { b.onclick = function () { openDoc(b.dataset.d); }; }); }

  function search(body, q) {
    var B = body.querySelector("#lc-body"); B.innerHTML = loading("Searching…");
    body.querySelector("#lc-title").textContent = "Search";
    api("/api/civic/local_search?q=" + encodeURIComponent(q)).then(function (d) {
      var I = d.items || [];
      B.innerHTML = '<div class="cv-small cv-pad">Searches the documents Archie has opened and read (open one to read it).</div>' + (I.length ? I.map(function (x) {
        return '<button class="cv-row lc-doc" data-d="' + esc(x.id) + '"><span class="cv-d">' + esc(fmtDate(x.date)) + '</span><span class="cv-t"><b>' + esc(x.title) + "</b><i>" + esc(x.body_name) + "</i>" + (x.snip ? '<em class="lc-snip">…' + esc(x.snip) + "…</em>" : "") + "</span>" + kindChip(x.kind) + "</button>";
      }).join("") : '<div class="cv-small cv-pad">Nothing found.</div>');
      wireDocs(B);
    });
  }

  function openBody(body, id, quiet) {
    cur.body = id;
    var B = body.querySelector("#lc-body"), p = placeOf(id) || {};
    body.querySelectorAll(".lc-place").forEach(function (x) { x.classList.toggle("sel", x.dataset.id === id); });
    if (!quiet) B.innerHTML = loading();
    api("/api/civic/local_body?id=" + encodeURIComponent(id)).then(function (b) {
      var followed = !b.error && b.followed;
      var name = b.name || p.name || id, web = (b.error ? p.web : b.website) || "";
      body.querySelector("#lc-title").textContent = name;
      var docs = b.docs || [];
      var groups = {};
      docs.forEach(function (x) { var k = (x.date || x.posted || "").slice(0, 7) || "date unknown"; (groups[k] = groups[k] || []).push(x); });
      var gk = Object.keys(groups).sort().reverse();
      var plat = b.platform ? Object.keys(b.platform) : [];
      B.innerHTML = '<div class="lc-head"><div><div class="cv-small">' + esc((p.kind === "county" || b.kind === "county") ? "county government" : (b.kind || p.kind || "")) + (p.pop ? " · " + p.pop.toLocaleString() + " people" : "") + "</div><h2>" + esc(name) + "</h2></div>" +
        '<button class="cv-btn lc-follow">' + (followed ? "★ following" : "☆ follow") + "</button></div>" +
        sec("WHERE ARCHIE LOOKS", '<div class="cv-keyrow"><label>website</label><input id="lc-web" value="' + esc(web) + '" placeholder="https://…"></div>' +
          '<div class="cv-keyrow"><label>agendas &amp; minutes page</label><input id="lc-mu" value="' + esc(b.meetings_url || "") + '" placeholder="optional: paste the page where they post them"><button class="cv-btn" id="lc-save">' + (followed ? "save and check now" : "follow") + "</button></div>" +
          '<div class="lc-warn" id="lc-err" hidden></div>' +
          (b.scanning ? '<div class="lc-busy"><i></i>Looking through their website for agendas and minutes… this can take a minute. You can leave this page; it keeps going.</div>' : "") +
          (followed ? '<div class="cv-small">' + (b.pages && b.pages.length ? "Found them on: " + b.pages.map(function (u) { return '<a href="' + esc(u) + '" target="_blank" rel="noopener">' + esc(u.replace(/^https?:\/\/(www\.)?/, "").slice(0, 70)) + "</a>"; }).join(" · ") : "") +
            (plat.length ? " · agenda system: " + esc(plat.join(", ")) : "") + " · checked " + esc(ago(b.checked)) + ' · <a href="#" id="lc-now">check now</a></div>' + (b.note ? '<div class="lc-warn">' + esc(b.note) + "</div>" : "") :
            '<div class="cv-small">Follow it and Archie looks for its agendas and minutes right away (it takes up to a minute). The website comes from Wikidata; if it\'s out of date, fix it above.</div>')) +
        (docs.length ? sec("AGENDAS AND MINUTES · " + docs.length, gk.map(function (k) { return '<div class="lc-month">' + esc(k === "date unknown" ? k : new Date(k + "-15T12:00:00").toLocaleDateString([], { month: "long", year: "numeric" })) + "</div>" + docRows(groups[k]); }).join("")) : "");
      var save = function (scan) {
        var btn = B.querySelector("#lc-save"); if (btn) { btn.disabled = true; btn.textContent = "looking for their agendas…"; }
        api("/api/civic/local_follow", { id: id, name: name, kind: b.kind || p.kind, st: b.st || (places && places.st) || "", fips: b.fips || cur.fips, website: B.querySelector("#lc-web").value.trim(), meetings_url: B.querySelector("#lc-mu").value.trim(), on: true, scan_now: scan }).then(function (r) {
          if (r.error) { var er = B.querySelector("#lc-err"); if (er) { er.hidden = false; er.textContent = r.error; } if (btn) { btn.disabled = false; btn.textContent = followed ? "save and check now" : "follow"; } return; }
          if (cur.fips) loadPlaces(body, cur.fips);
          openBody(body, id);
        });
      };
      B.querySelector("#lc-save").onclick = function () { save(true); };
      B.querySelector(".lc-follow").onclick = function () {
        if (followed) api("/api/civic/local_follow", { id: id, on: false }).then(function () { if (cur.fips) loadPlaces(body, cur.fips); openBody(body, id); });
        else save(true);
      };
      var now = B.querySelector("#lc-now"); if (now) now.onclick = function (e) { e.preventDefault(); now.textContent = "checking…"; api("/api/civic/local_scan", { id: id }).then(function () { openBody(body, id); }); };
      if (b.scanning) setTimeout(function () { if (cur.body === id && document.body.contains(B)) { openBody(body, id, true); } }, 4000);
      else if (cur.fips && b.followed && placeOf(id) && placeOf(id).found !== (b.found || 0)) loadPlaces(body, cur.fips);
      wireDocs(B);
    });
  }

  function openDoc(id) {
    var el = K.openDrawer(loading("Opening the document…"));
    api("/api/civic/local_doc?id=" + encodeURIComponent(id)).then(function (d) {
      if (d.error) { el.innerHTML = '<div class="cv-small">' + esc(d.error) + "</div>"; return; }
      var M = d.motions || [];
      var mot = M.length ? M.map(function (m) {
        var t = m.tally || {}, tl = [t.ayes != null ? "ayes " + t.ayes : "", t.nays != null ? "nays " + t.nays : "", t.abstain != null ? "abstain " + t.abstain : "", t.absent != null ? "absent " + t.absent : ""].filter(Boolean).join(" · ");
        var nm = ["ayes", "nays", "abstain", "absent"].filter(function (k) { return t[k + "_names"]; }).map(function (k) { return k + ": " + t[k + "_names"].join(", "); }).join(" · ");
        return '<div class="lc-mot">' + (m.outcome ? '<span class="cv-res ' + (/carried|adopted|approved|passed|unanimously/.test(m.outcome) ? "ok" : /denied|defeated|failed|rejected/.test(m.outcome) ? "no" : "") + '">' + esc(m.outcome) + "</span> " : "") +
          (tl ? '<span class="cv-small">' + esc(tl) + "</span>" : "") + "<p>" + esc(m.text) + "</p>" + (nm ? '<div class="cv-small">' + esc(nm) + "</div>" : "") + "</div>";
      }).join("") : "";
      el.innerHTML = '<div class="cv-kicker">' + esc(d.body_name) + " · " + esc((d.kind || "document").toUpperCase()) + (d.date ? " · " + esc(fmtDate(d.date)) : "") + "</div><h2>" + esc(d.title) + "</h2>" +
        (d.note ? '<div class="lc-warn">' + esc(d.note) + "</div>" : "") +
        (d.chars ? K.explainBtn("localdoc", d.id, null, d.kind === "agenda" ? "what's on this agenda, in plain English" : "what was decided, in plain English") : "") +
        (M.length ? sec("MOTIONS AND VOTES IN THIS DOCUMENT · " + M.length, '<div class="cv-small">As the minutes word them. Archie picks these out by looking for motions, resolutions and vote counts, so check the full text for anything important.</div>' + mot) :
          d.kind === "minutes" && d.chars ? sec("MOTIONS AND VOTES", '<div class="cv-small">Archie didn\'t spot any motions or votes written in a way it recognizes. The full text is below.</div>') : "") +
        (d.chars ? sec("FULL TEXT", '<input class="cv-mq" id="lc-find" placeholder="find in this document…"><pre class="lc-text" id="lc-text">' + esc(d.text) + "</pre>" + (d.chars > d.text.length ? '<div class="cv-small">…the rest is in the original.</div>' : "")) : "") +
        '<div class="cv-foot"><a href="' + esc(d.url) + '" target="_blank" rel="noopener">the original document ↗</a></div>';
      K.wireExplain(el);
      var f = el.querySelector("#lc-find"), pre = el.querySelector("#lc-text");
      if (f) f.oninput = function () {
        var v = f.value.trim(); if (!v) { pre.innerHTML = esc(d.text); return; }
        var re; try { re = new RegExp(v.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "gi"); } catch (e) { return; }
        pre.innerHTML = esc(d.text).replace(re, function (x) { return "<mark>" + x + "</mark>"; });
        var mk = pre.querySelector("mark"); if (mk) mk.scrollIntoView({ block: "center" });
      };
    });
  }

  /* ================================================================ bill versions side by side */
  function billVersions(el, b) {
    var box = document.createElement("div"); box.className = "lc-bv";
    box.innerHTML = sec("VERSIONS OF THE TEXT", loading("Asking govinfo.gov for every printed version…"));
    var foot = el.querySelector(".cv-foot"); if (foot) el.insertBefore(box, foot); else el.appendChild(box);
    api("/api/civic/bill_versions?id=" + encodeURIComponent(b.id)).then(function (d) {
      var V = d.versions || [];
      if (d.error || !V.length) { box.innerHTML = sec("VERSIONS OF THE TEXT", '<div class="cv-small">' + esc(d.error || "No printed text yet. The Government Publishing Office usually posts it a few days after a bill is introduced.") + "</div>"); return; }
      var opt = function (sel) { return V.map(function (v, i) { return '<option value="' + i + '"' + (i === sel ? " selected" : "") + ">" + esc(v.label + " · " + fmtDate(v.date)) + "</option>"; }).join(""); };
      box.innerHTML = sec("VERSIONS OF THE TEXT · " + V.length, '<div class="lc-vers">' + V.map(function (v) { return '<a href="https://www.govinfo.gov/app/details/' + esc(v.pkg) + '" target="_blank" rel="noopener"><b>' + esc(v.label) + "</b><span>" + esc(fmtDate(v.date)) + "</span></a>"; }).join('<i>→</i>') + "</div>" +
        (V.length > 1 ? '<div class="cv-keyrow"><label>compare</label><select id="bv-a">' + opt(V.length - 2) + '</select><label>with</label><select id="bv-b">' + opt(V.length - 1) + '</select><button class="cv-btn" id="bv-go">show what changed</button></div><div id="bv-out"></div>'
          : '<div class="cv-small">Only one version so far. Once it\'s changed in committee or on the floor, Archie can show exactly what was changed.</div>'));
      var go = box.querySelector("#bv-go"); if (!go) return;
      go.onclick = function () { var a = V[+box.querySelector("#bv-a").value], c = V[+box.querySelector("#bv-b").value]; if (a === c) return; diff(box.querySelector("#bv-out"), a, c, 0); };
    });
  }
  function diff(out, a, b, offset) {
    out.innerHTML = loading("Downloading both versions and comparing them word by word (big bills take a minute)…");
    api("/api/civic/bill_diff?a=" + encodeURIComponent(a.pkg) + "&b=" + encodeURIComponent(b.pkg) + "&offset=" + offset).then(function (d) {
      if (d.error) { out.innerHTML = '<div class="cv-small">' + esc(d.error) + "</div>"; return; }
      var s = d.stats || {};
      out.innerHTML = '<div class="lc-dstat"><b>' + (s.changes || 0).toLocaleString() + "</b> places changed · <ins>+" + (s.added || 0).toLocaleString() + " words</ins> · <del>−" + (s.removed || 0).toLocaleString() + " words</del>" +
        '<span class="cv-small"> from “' + esc(a.label) + "” to “" + esc(b.label) + "”</span></div>" +
        (d.total ? "" : '<div class="cv-small">The two versions read the same.</div>') +
        d.hunks.map(function (h, i) { return '<div class="lc-hunk"><div class="lc-where">' + (d.offset + i + 1) + ". " + esc(h.where || "near the start") + '</div><div class="lc-dtxt">' + h.html + "</div></div>"; }).join("") +
        (d.total > d.offset + d.hunks.length || d.offset ? '<div class="cv-keyrow">' + (d.offset ? '<button class="cv-btn" data-o="' + (d.offset - 40) + '">◂ earlier</button>' : "") + '<span class="cv-small">' + (d.offset + 1) + "–" + (d.offset + d.hunks.length) + " of " + d.total + "</span>" + (d.total > d.offset + d.hunks.length ? '<button class="cv-btn" data-o="' + (d.offset + 40) + '">later ▸</button>' : "") + "</div>" : "") +
        '<div class="cv-small"><del>Struck text</del> was taken out; <ins>underlined text</ins> was put in. Official text from the Government Publishing Office (govinfo.gov).</div>';
      out.querySelectorAll("[data-o]").forEach(function (x) { x.onclick = function () { diff(out, a, b, +x.dataset.o); out.scrollIntoView({ block: "start" }); }; });
    });
  }

  return { local: local, openBody: function (body, id) { local(body, id); }, openDoc: openDoc, billVersions: billVersions };
};
