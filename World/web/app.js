/* Archie World: the live page. Data comes from Archie on this PC (/api/state);
   reference data (places, routes, hours) is in static.js. */
(function () {
  "use strict";
  var css = getComputedStyle(document.documentElement);
  var C = function (n) { return css.getPropertyValue(n).trim(); };
  function rgba(hex, a) { var h = hex.replace("#", ""); return "rgba(" + parseInt(h.slice(0, 2), 16) + "," + parseInt(h.slice(2, 4), 16) + "," + parseInt(h.slice(4, 6), 16) + "," + a + ")"; }
  function $(id) { return document.getElementById(id); }
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function api(path, body) {
    return fetch(path, body ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : {})
      .then(function (r) { return r.json(); });
  }
  var TOPIC = { politics: "--t-politics", conflict: "--t-conflict", economy: "--t-economy", science: "--t-science", climate: "--t-climate", health: "--t-health" };

  // markets shown on the board (mirror of archie_world.MARKETS)
  var MK = [
    ["US futures", [["S&P 500 fut.", "ES=F", 0], ["Nasdaq 100 fut.", "NQ=F", 0], ["Dow fut.", "YM=F", 0], ["Russell 2000 fut.", "RTY=F", 0]]],
    ["Europe", [["STOXX 600", "^STOXX", 1], ["DAX", "^GDAXI", 0], ["FTSE 100", "^FTSE", 0], ["CAC 40", "^FCHI", 0]]],
    ["Asia", [["Nikkei 225", "^N225", 0], ["Hang Seng", "^HSI", 0], ["Shanghai", "000001.SS", 0], ["KOSPI", "^KS11", 0], ["Sensex", "^BSESN", 0]]],
    ["FX", [["Dollar index", "DX-Y.NYB", 2], ["EUR/USD", "EURUSD=X", 4], ["USD/JPY", "JPY=X", 2], ["GBP/USD", "GBPUSD=X", 4], ["USD/CNY", "CNY=X", 3], ["USD/MXN", "MXN=X", 2]]],
    ["Commodities", [["WTI crude", "CL=F", 2], ["Brent crude", "BZ=F", 2], ["Natural gas", "NG=F", 2], ["Gold", "GC=F", 0], ["Silver", "SI=F", 2], ["Copper", "HG=F", 2], ["Wheat", "ZW=F", 0]]],
    ["Crypto", [["Bitcoin", "BTC-USD", 0], ["Ethereum", "ETH-USD", 0]]],
    ["Volatility", [["VIX", "^VIX", 1]]]
  ];
  var SECTORS = [["Tech", "XLK"], ["Comm. services", "XLC"], ["Cons. discretionary", "XLY"], ["Financials", "XLF"], ["Health care", "XLV"], ["Industrials", "XLI"], ["Energy", "XLE"], ["Materials", "XLB"], ["Utilities", "XLU"], ["Real estate", "XLRE"], ["Cons. staples", "XLP"]];
  var EXIDX = { NYSE: "^GSPC", NASDAQ: "^NDX", TSX: "^GSPTSE", BMV: "^MXX", B3: "^BVSP", LSE: "^FTSE", EPA: "^FCHI", XETRA: "^GDAXI", SIX: "^SSMI", BIST: "XU100.IS", TASE: "TA35.TA", EGX: "^CASE30", TADAWUL: "^TASI.SR", DFM: "^DFMGI", JSE: "^J203.JO", NSE: "^NSEI", SSE: "000001.SS", HKEX: "^HSI", TSE: "^N225", KRX: "^KS11", TWSE: "^TWII", SGX: "^STI", IDX: "^JKSE", ASX: "^AXJO" };
  var PWKEY = { "Strait of Hormuz": "hormuz", "Strait of Malacca": "malacca", "Suez Canal": "suez", "Bab el-Mandeb": "mandeb", "Panama Canal": "panama", "Turkish Straits": "bospor", "Taiwan Strait": "taiwan", "Strait of Gibraltar": "gibraltar", "Dover Strait": "dover", "Danish Straits": "oresund", "Kerch Strait": "kerch", "Lombok Strait": "lombok", "Sunda Strait": "sunda", "Korea Strait": "korea", "Cape of Good Hope": "good hope", "Mozambique Channel": "mozambique", "Bering Strait": "bering", "Drake Passage": "magellan" };
  var VMIX = [["Tankers", "#f97316"], ["Container", "#3b82f6"], ["Dry bulk", "#a855f7"], ["General cargo", "#22c55e"], ["Ro-ro", "#64748b"]];

  /* ============================ live data ============================ */
  var S = null, NOW = Date.now() / 1000;
  var EVENTS = [], STORIES = [], quakes = [], cyclones = [], floods = [], volcanoes = [], wildfires = [], fires = [], shade = {}, hotspots = [];
  var tEnd = null;           // time slider: null = live, else the unix time being shown
  function refT() { return tEnd || NOW; }
  function minsAgo(ts) { return Math.max(0, Math.round((refT() - ts) / 60)); }
  function inWindow(ts, hours) { var r = refT(); return ts <= r + 60 && ts >= r - hours * 3600; }
  var TYPEMAP = { clash: 1, shelling: 1, drone: 1, missile: 1, blast: 1, fire: 1, alert: 1, aid: 1, protest: 1, politics: 1, economy: 1, ship: 1, police: 1, defense: 1 };
  var KIND = { telegram: "TELEGRAM", gnews: "LOCAL PRESS", rss: "OUTLET" };

  var PAGE_VERSION = "3.23.0";
  function ingest(d) {
    S = d; NOW = d.now;
    if (d.version !== PAGE_VERSION) {
      note('<span class="k" style="color:var(--quake)">RESTART NEEDED</span><span>An older Archie is still running behind this window. Double-click <b>Restart Archie.bat</b> in the Archie folder.</span>', 600000);
    }
    EVENTS = d.events.map(function (e) { e.type = TYPEMAP[e.type] ? e.type : "politics"; e.unconfirmed = !e.confirmed; return e; });
    STORIES = d.stories.map(function (s) {
      s.l = s.src.filter(function (x) { return x.lean === "left"; }).length;
      s.c = s.src.filter(function (x) { return x.lean === "center"; }).length;
      s.r = s.src.filter(function (x) { return x.lean === "right"; }).length;
      s.o = s.src.length - s.l - s.c - s.r;
      s.one = (s.l + s.c + s.r) >= 3 && (s.l === 0 || s.r === 0);
      s.topic = TOPIC[s.topic] ? s.topic : "politics";
      return s;
    });
    var hz = d.hazards || [];
    quakes = hz.filter(function (h) { return h.kind === "quake"; }).map(function (h) { return { id: h.id, lat: h.lat, lng: h.lng, m: h.mag, place: (h.extra && h.extra.place) || h.title, time: h.time, url: h.url, tsunami: !!h.level }; });
    cyclones = hz.filter(function (h) { return h.kind === "cyclone"; });
    STORMS = d.storms || {};
    floods = hz.filter(function (h) { return h.kind === "flood"; });
    volcanoes = hz.filter(function (h) { return h.kind === "volcano"; });
    wildfires = hz.filter(function (h) { return h.kind === "wildfire"; });
    fires = (d.fires || []).map(function (p) { return { lat: p[0], lng: p[1] }; });
    shade = d.shade || {};
    exchanges.forEach(function (x) { var q = (d.quotes || {})[EXIDX[x.name]]; x.chg = q ? q.chg : null; x.q = q || null; });
    buildHotspots();
    var st = $("stamp");
    st.innerHTML = d.online ? '<b>●</b> live · pulled ' + clock(d.last_cycle) + (d.busy ? " · reading " + esc(d.busy) : "") : '<b style="color:var(--muted);animation:none">○</b> offline · showing what was pulled ' + (d.last_cycle ? clock(d.last_cycle) : "last time");
  }
  function clock(ts) { return ts ? new Date(ts * 1000).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }) : "—"; }
  function buildHotspots() {
    var cells = {};
    EVENTS.forEach(function (e) {
      if (e.lat == null || !/clash|shelling|drone|missile|blast/.test(e.type) || !inWindow(e.last, 48)) return;
      var k = Math.round(e.lat / 2) + ":" + Math.round(e.lng / 2);
      (cells[k] = cells[k] || []).push(e);
    });
    hotspots = Object.keys(cells).filter(function (k) { return cells[k].length >= 3; }).map(function (k) {
      var L = cells[k], lat = d3.mean(L, function (e) { return e.lat; }), lng = d3.mean(L, function (e) { return e.lng; });
      var places = d3.rollups(L, function (v) { return v.length; }, function (e) { return e.place || e.country; }).sort(function (a, b) { return b[1] - a[1]; });
      return { lat: lat, lng: lng, n: L.length, name: places[0][0] || "Hotspot", zone: L[0].country || "", region: L[0].region, lvl: L.length >= 12 ? "war" : L.length >= 5 ? "armed" : "unrest", list: L };
    });
  }

  /* ============================ layers ============================ */
  var SATG = [["stations", "Other space stations", "#d9a441", "China's Tiangong and the craft visiting space stations (the ISS has its own switch)"],
    ["visual", "Brightest (seen by eye)", "#f4f4ef", "About 150 satellites bright enough to spot from the ground at dusk or dawn"],
    ["science", "Science (Hubble & co.)", "#a78bfa", "Hubble and other science satellites"],
    ["weather", "Weather satellites", "#38bdf8", "NOAA, GOES, Meteosat and others that take the weather pictures"],
    ["gps", "GPS", "#34d399", "The 31 US GPS satellites, about 12,500 miles up"],
    ["starlink", "Starlink", "#94a3b8", "SpaceX's internet satellites: thousands of them. 3D globe only; the heaviest group"]];
  var SAT_KEY = "archieWorldSats";
  var layers = [
    { head: "Conflict" },
    { id: "zones", name: "Conflict areas", color: C("--war"), on: true },
    { id: "hot", name: "Hotspots", color: C("--armed"), on: true },
    { id: "events", name: "On-the-ground events", color: "#e5484d", on: true },
    { id: "front", name: "Front lines & control", color: C("--war"), on: true, line: true },
    { head: "News" },
    { id: "news", name: "Headlines", color: C("--t-politics"), on: true },
    { head: "Disasters" },
    { id: "quakes", name: "Earthquakes", color: C("--quake"), on: true },
    { id: "cyclones", name: "Cyclones", color: C("--cyclone"), on: true },
    { id: "floods", name: "Floods", color: C("--flood"), on: true },
    { id: "volcanoes", name: "Volcanoes", color: C("--volcano"), on: true },
    { id: "fires", name: "Wildfires", color: C("--fire"), on: true },
    { id: "radar", name: "Weather radar", color: "#38bdf8", on: true },
    { head: "Trade & energy" },
    { id: "chokes", name: "Chokepoints & straits", color: C("--choke"), on: true },
    { id: "oil", name: "Oil pipelines", color: C("--oil"), on: true, line: true },
    { id: "gas", name: "Gas pipelines", color: C("--gas"), on: true, line: true },
    { id: "markets", name: "Financial centers", color: "#34d399", on: true },
    { id: "banks", name: "Central banks", color: "#fbbf24", on: true },
    { id: "mines", name: "Mines", color: "#d6a35c", on: true },
    { head: "Antarctica" },
    { id: "stations", name: "Research stations", color: "#9ec5ff", on: true },
    { head: "Space" },
    { id: "iss", name: "Space station (ISS)", color: "#d9a441", on: true }
  ].concat(SATG.map(function (g) { return { id: "sat:" + g[0], name: g[1], color: g[2], on: satPref(g[0]) }; }));
  var on = function (id) { var l = layers.find(function (l) { return l.id === id; }); return !!(l && l.on); };
  var region = null;
  function count(id) {
    return { zones: Object.keys(shade).length, hot: hotspots.length, events: EVENTS.filter(function (e) { return inWindow(e.last, 24); }).length, front: S && S.front ? "✓" : "–",
      news: STORIES.filter(function (s) { return inWindow(s.last, 24); }).length, quakes: quakes.filter(function (q) { return inWindow(q.time, 24); }).length,
      cyclones: cyclones.length, floods: floods.length, volcanoes: volcanoes.length, fires: fires.length + wildfires.length, radar: radarFrames.length ? "live" : "–",
      chokes: chokes.length, oil: pipes.filter(function (p) { return p.kind === "oil"; }).length, gas: pipes.filter(function (p) { return p.kind === "gas"; }).length,
      markets: exchanges.length, banks: banks.length, iss: issRec ? "live" : "–", mines: MINES.length, stations: STATIONS.length,
      "sat:stations": satCount("stations"), "sat:visual": satCount("visual"), "sat:science": satCount("science"), "sat:weather": satCount("weather"), "sat:gps": satCount("gps"), "sat:starlink": satCount("starlink") }[id];
  }
  function renderLayers() {
    var box = $("layers"); box.innerHTML = "";
    layers.forEach(function (l) {
      if (l.head) { var h = document.createElement("div"); h.className = "grp-h"; h.textContent = l.head; box.appendChild(h); return; }
      var b = document.createElement("button");
      b.className = "layer"; b.setAttribute("aria-pressed", l.on);
      b.innerHTML = '<span class="sw' + (l.line ? " line" : "") + '" style="background:' + l.color + '"></span><span>' + l.name + '</span><span class="n">' + (count(l.id) == null ? "" : count(l.id)) + "</span>";
      b.onclick = function () { l.on = !l.on; if (l.id.indexOf("sat:") === 0) { saveSatPrefs(); if (l.on) loadSats(l.id.slice(4)); } renderLayers(); refresh(); };
      if (l.id.indexOf("sat:") === 0) b.title = SATG.find(function (g) { return "sat:" + g[0] === l.id; })[3];
      box.appendChild(b);
    });
    var rg = $("regions"); rg.innerHTML = "";
    [{ id: null, name: "World" }].concat(REGIONS).forEach(function (R) {
      var b = document.createElement("button"); b.className = "chip"; b.textContent = R.name; b.setAttribute("aria-pressed", region === R.id);
      b.onclick = function () { pickRegion(R.id); }; rg.appendChild(b);
    });
    renderWatch();
  }
  function renderLegend() {
    var items = [["--war", "major war"], ["--armed", "armed conflict"], ["--unrest", "unrest"], ["--oil", "oil pipeline"], ["--gas", "gas pipeline"], ["--choke", "chokepoint / strait"], ["--quake", "earthquake"], ["--cyclone", "cyclone"]];
    $("legend").innerHTML = items.map(function (i) { return '<span><i style="background:var(' + i[0] + ')"></i>' + i[1] + "</span>"; }).join("") +
      '<span><i style="background:#34d399;width:7px;height:7px;border-radius:50%"></i>financial center</span><span><i style="background:#fbbf24;width:7px;height:7px;clip-path:polygon(50% 0,100% 25%,100% 75%,50% 100%,0 75%,0 25%)"></i>central bank</span>' +
      '<span style="width:100%;height:0"></span>' + ["clash", "shelling", "drone", "missile", "alert", "defense", "protest", "politics", "aid"].map(function (k) { return '<span style="display:inline-flex;align-items:center;gap:3px">' + icon(k, 6) + ET[k].name + "</span>"; }).join("");
  }

  /* ============================ helpers ============================ */
  function ago(mins) { return mins < 1 ? "just now" : mins < 60 ? mins + " min ago" : mins < 1440 ? Math.round(mins / 60) + (Math.round(mins / 60) === 1 ? " hour ago" : " hours ago") : Math.round(mins / 1440) + "d ago"; }
  function regionOf(id) { return REGIONS.find(function (R) { return R.id === id; }); }
  function srcLine(ev) {
    var langs = ev.src.map(function (s) { return s.lang; }).filter(function (l, i, a) { return l && l !== "en" && a.indexOf(l) === i; });
    var sides = ev.src.map(function (s) { return s.side; }).filter(function (l, i, a) { return l && a.indexOf(l) === i; });
    return ev.src.slice(0, 3).map(function (s) { return '<span class="src" title="' + esc(s.name) + '">' + esc(short(s.name, 22)) + "</span>"; }).join("") +
      (ev.src.length > 3 ? '<span class="src">+' + (ev.src.length - 3) + "</span>" : "") +
      (sides.length ? '<span style="color:var(--dim)"> ' + esc(sides.join(" · ")) + "</span>" : "") +
      (langs.length ? '<span style="color:var(--dim)"> · from ' + langs.map(function (l) { return LANG[l] || l; }).join(", ") + "</span>" : "");
  }
  function short(s, n) { s = String(s || "").replace(/^Google News: /, "").replace(/^Telegram · /, "@"); return s.length > n ? s.slice(0, n - 1) + "…" : s; }
  function slug(t) { return String(t).toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, ""); }
  function setHash(h) { try { history.replaceState(null, "", "#" + h); } catch (e) { } }
  function copyLink(h) {
    var u = "archie://world#" + h, done = function () { var b = card.querySelector(".cp"); if (b) { b.textContent = "link copied"; setTimeout(function () { b.textContent = "copy link"; }, 1600); } };
    try { navigator.clipboard.writeText(u).then(done, function () { window.prompt("Link to this spot (paste into Obsidian):", u); }); } catch (e) { window.prompt("Link to this spot:", u); }
  }
  function note(msg, ms) {
    var t = $("toast"); t.onclick = null; t.hidden = false; t.style.opacity = 1; t.innerHTML = msg;
    clearTimeout(note.t); clearTimeout(note.h);
    // fade, then really remove it, so an invisible note can't catch clicks meant for the buttons under it
    note.t = setTimeout(function () { t.style.opacity = 0; note.h = setTimeout(function () { t.hidden = true; t.onclick = null; }, 450); }, ms || 5200);
  }

  /* ============================ detail card ============================ */
  var card = $("card");
  $("card-x").onclick = function () { card.hidden = true; };
  function show(kind, color, title, body, extra, actions) {
    card.classList.remove("rich"); $("c-kind").hidden = false; $("c-title").hidden = false;
    var k = $("c-kind"); k.textContent = kind; k.style.color = color;
    $("c-title").textContent = title; $("c-body").textContent = body || ""; $("c-body").hidden = !body;
    $("c-extra").innerHTML = extra || "";
    setActions(actions);
    card.hidden = false;
  }
  function setActions(actions) {
    var act = $("c-actions"); act.innerHTML = "";
    (actions || []).forEach(function (a, i) { var b = document.createElement("button"); b.className = "btn" + (i === 0 ? " primary" : "") + (a[2] ? " " + a[2] : ""); b.textContent = a[0]; if (a[1]) b.onclick = a[1]; act.appendChild(b); });
  }
  function covHTML(s, cls) {
    var tot = s.l + s.c + s.r + (s.o || 0) || 1;
    return '<span class="' + cls + '"><span style="width:' + (s.l / tot * 100) + '%"></span><span style="width:' + (s.c / tot * 100) + '%"></span><span style="width:' + (s.r / tot * 100) + '%"></span><span style="width:' + ((s.o || 0) / tot * 100) + '%;background:#3a3d36"></span></span>';
  }
  function sourcesHTML(list) {
    return '<div class="srcs"><div class="h">Sources · ' + list.length + "</div>" + list.slice(0, 8).map(function (s) {
      var tr = s.trust ? ' · <span title="how often another, separate outlet reported the same event within two days (last 30 days). Not a score for this story or a judgement of the outlet: big outlets publish many stories nobody else covers." style="color:var(--muted, #8a8f98)">matched by others ' + s.trust.rate + "%</span>" : "";
      return '<div class="srow"><span>' + esc(short(s.name, 34)) + (s.lang && s.lang !== "en" ? " · " + (LANG[s.lang] || s.lang) : "") + (s.side ? " · " + esc(s.side) : "") + tr +
        '</span><span>' + ago(minsAgo(s.time)) + (s.url ? ' · <a href="' + esc(s.url) + '" target="_blank" rel="noopener">source ↗</a>' : "") + "</span></div>" +
        (s.lang && s.lang !== "en" && s.title ? '<div class="orig" dir="auto">' + esc(s.title.slice(0, 220)) + "</div>" : "");
    }).join("") + "</div>";
  }
  function showStory(s) {
    setHash("story=" + s.id);
    show(s.topic.toUpperCase() + (s.place ? " · " + s.place.toUpperCase() : ""), C(TOPIC[s.topic]), s.t, ago(minsAgo(s.last)) + " · " + s.n + (s.n === 1 ? " outlet" : " outlets"),
      '<div class="cov">' + covHTML(s, "cov").replace(/^<span class="cov">|<\/span>$/g, "") + '</div><div class="covtxt" style="margin-top:5px">left ' + s.l + " · center " + s.c + " · right " + s.r + " · other " + s.o + (s.one ? ' · <span class="onesided">mostly one side</span>' : "") + "</div>" + sourcesHTML(s.src),
      [["save", function () { saveItem(s, "story"); }], ["catch me up", function () { catchUp(s.id, s.t); }], ["background", function () { explainIt({ title: s.t, text: s.t + ". " + (s.src[0] && s.src[0].title !== s.t ? s.src[0].title : "") }); }], ["teach me", function () { openLesson(s.id, s.t); }], ["ask Archie", function () { askMap(s.t); }], ["copy link", function () { copyLink("story=" + s.id); }, "cp"], ["wrong label?", function () { wrongLabel(s); }, "ghost"]]);
  }
  function showEvent(ev) {
    setHash("event=" + ev.id);
    var R = regionOf(ev.region);
    show((R ? R.name.toUpperCase() : (ev.country || "WORLD").toUpperCase()) + " · " + ET[ev.type].name.toUpperCase() + (ev.unconfirmed ? " · UNCONFIRMED" : " · CONFIRMED"), ET[ev.type].col, ev.t,
      ago(minsAgo(ev.last)) + (ev.place ? " · near " + ev.place : "") + ". " + (ev.unconfirmed ? "Only one source so far. It turns confirmed when a second, separate source reports the same thing." : "Reported by " + ev.n + " separate sources."),
      sourcesHTML(ev.src), [["save", function () { saveItem(ev, "event"); }], ["catch me up", function () { catchUp(ev.id, ev.t); }], ["background", function () { explainIt({ title: ev.t, text: ev.t + (ev.place ? " (near " + ev.place + ")" : "") }); }], ["teach me", function () { openLesson(ev.id, ev.t); }], ["ask Archie", function () { askMap(ev.t); }], ["copy link", function () { copyLink("event=" + ev.id); }, "cp"], ["wrong label?", function () { wrongLabel(ev); }, "ghost"]]);
  }
  function showHot(h) {
    show("HOTSPOT · " + LVL[h.lvl].name.toUpperCase(), C(LVL[h.lvl].v), h.name + (h.zone ? " · " + h.zone : ""), h.n + " military reports here in the last 48 hours.",
      h.list.slice().sort(function (a, b) { return b.last - a.last; }).slice(0, 4).map(function (e) { return '<div class="srow"><span style="color:var(--fg);font-family:var(--body);font-size:11px;white-space:normal">' + esc(e.t) + "</span><span>" + ago(minsAgo(e.last)) + "</span></div>"; }).join(""),
      h.region ? [["open " + regionOf(h.region).name, function () { pickRegion(h.region); }]] : [["zoom in", function () { focus(h.lat, h.lng, 0.6); }]]);
  }
  function showQuake(q) {
    show("EARTHQUAKE · M" + q.m.toFixed(1), C("--quake"), "M" + q.m.toFixed(1) + " " + q.place, ago(minsAgo(q.time)) + ". From the USGS feed." + (q.tsunami ? " USGS set its tsunami flag: check local warnings." : ""),
      headlinesHTML(nearby(q.lat, q.lng, 3)), [["USGS event page", function () { if (q.url) window.open(q.url, "_blank"); }]]);
  }
  function showHazard(h, label, color) {
    var ex = h.extra || {};
    show(label + (h.level ? " · " + h.level.toUpperCase() + " ALERT" : ""), color, h.title, (ex.severity || "") + (ex.country ? " · " + ex.country : "") + ". From " + (h.id.indexOf("gvp") === 0 ? "the Smithsonian's weekly volcano report" : "GDACS (green, orange, red goes by how many people are exposed)") + ".",
      headlinesHTML(nearby(h.lat, h.lng, 4)), [["full report", function () { if (h.url) window.open(h.url, "_blank"); }], ["background", function () { explainIt({ title: h.title, text: h.title }); }]]);
  }

  /* ---------- rich cards (chokepoints, pipelines, exchanges, central banks) ---------- */
  function donut(mix, colors) {
    var tot = d3.sum(mix) || 1, r = 15, L = 2 * Math.PI * r, off = 0;
    var segs = mix.map(function (v, i) { var len = v / tot * L, s = '<circle r="' + r + '" fill="none" stroke="' + colors[i][1] + '" stroke-width="7" stroke-dasharray="' + Math.max(0, len - 1.2) + " " + (L - len + 1.2) + '" stroke-dashoffset="' + (-off) + '" transform="rotate(-90)"/>'; off += len; return s; }).join("");
    return '<svg class="donut" viewBox="-22 -22 44 44" width="46" height="46" aria-hidden="true">' + segs + "</svg>";
  }
  function mentions(words, lat, lng, deg) {
    var out = [];
    STORIES.concat(EVENTS).forEach(function (s) {
      if (!inWindow(s.last, 72)) return;
      var t = (s.t || "").toLowerCase(), hit = words.some(function (w) { return w && t.indexOf(w) >= 0; });
      if (!hit && lat != null && s.lat != null && deg && Math.abs(s.lat - lat) < deg && Math.abs(s.lng - lng) < deg * 1.4 && s.n >= 2) hit = true;
      if (hit) out.push(s);
    });
    return out.sort(function (a, b) { return b.last - a.last; }).slice(0, 4);
  }
  function nearby(lat, lng, deg) { return mentions([], lat, lng, deg); }
  function headlinesHTML(list) {
    return '<div class="rc-sec"><div class="h">In the news</div>' + (list.length ? list.map(function (x) { return '<div class="srow hl" data-id="' + x.id + '"><span style="color:var(--fg);font-family:var(--body);font-size:11px;white-space:normal">' + esc(x.t) + "</span><span>" + ago(minsAgo(x.last)) + "</span></div>"; }).join("") : '<div class="srow"><span>Nothing in the last three days.</span></div>') + "</div>";
  }
  function bindHeadlines() {
    card.querySelectorAll(".srow.hl").forEach(function (r) { r.style.cursor = "pointer"; r.onclick = function () { openById(r.dataset.id); }; });
  }
  function rich(o) {
    card.classList.add("rich");
    $("c-kind").hidden = true; $("c-title").hidden = true; $("c-body").hidden = true;
    var h = '<div class="rc-head"><span class="rc-title" style="color:' + o.color + '">' + esc(o.title) + '</span><span class="rc-badge"><i style="background:' + o.badgeColor + '"></i>' + o.badge + "</span></div>" +
      '<div class="rc-sub">' + esc(o.sub) + "</div>" +
      '<div class="rc-boxes">' + o.boxes.map(function (b) { return '<div class="rc-box"><div class="h">' + b[0] + '</div><div class="rc-v"' + (b[2] ? ' style="color:' + b[2] + '"' : "") + ' title="' + esc(String(b[1]).replace(/<[^>]+>/g, "")) + '">' + b[1] + "</div></div>"; }).join("") + "</div>" +
      (o.sections || []).map(function (sct) { return sct[0] ? '<div class="rc-sec"><div class="h">' + sct[0] + "</div>" + sct[1] + "</div>" : sct[1]; }).join("");
    $("c-extra").innerHTML = h;
    var acts = (o.actions || []).slice();
    if (o.explain) acts.push(["background", function () { explainIt(o.explain); }]);
    if (o.watch) acts.push([isWatched(o.watch[0], o.watch[1]) ? "★ watching" : "☆ watch", function (e) { toggleWatch(o.watch[0], o.watch[1]); e.target.textContent = isWatched(o.watch[0], o.watch[1]) ? "★ watching" : "☆ watch"; }]);
    acts.push(["copy link", function () { copyLink(o.hash); }, "cp"]);
    setActions(acts);
    card.hidden = false; setHash(o.hash);
    bindHeadlines();
    if (o.after) o.after();
  }
  function shipsFor(c) {
    var k = PWKEY[c.name], ships = (S && S.ships) || {};
    if (!k) return null;
    var name = Object.keys(ships).find(function (n) { return n.toLowerCase().indexOf(k) >= 0; });
    return name ? ships[name] : null;
  }
  function stColor(s) { return /disrupt/.test(s) ? C("--down") : /reduc|busier/.test(s) ? C("--quake") : s === "normal" ? C("--up") : C("--muted"); }
  function showChoke(c) {
    var sh = shipsFor(c), st = sh ? sh.status : "no data yet", mix = sh ? sh.mix : null;
    var words = [c.name.toLowerCase().replace(/^strait of |^the /, "").replace(/ (canal|strait|straits|channel|passage)$/, "")];
    if (c.name === "Turkish Straits") words.push("bosporus", "dardanelles");
    if (c.name === "Bab el-Mandeb") words.push("red sea", "houthi");
    rich({
      hash: "choke=" + slug(c.name), color: C("--fire"), title: c.name.toUpperCase(), badge: c.major ? "STRATEGIC" : "REGIONAL", badgeColor: c.major ? C("--quake") : C("--muted"),
      sub: CSUB[c.name] || "Shipping lane", watch: ["choke", c.name], explain: { title: c.name, names: [c.name], kind: "place", text: c.name + ": " + c.what },
      boxes: [["Coordinates", c.lat.toFixed(2) + "°, " + c.lng.toFixed(2) + "°", "#34d399"], ["Status", st, stColor(st)], ["Ships / day", sh ? "~" + Math.round(sh.week_avg) + ' <span style="color:var(--dim);font-weight:400">vs ' + Math.round(sh.year_avg) + "</span>" : "—", "var(--fg)"]],
      sections: [
        mix && d3.sum(mix) ? ["Ships by type · last 30 days", '<div class="mix">' + donut(mix, VMIX) + '<div class="mixl">' + mix.map(function (v, i) { return '<span><i style="background:' + VMIX[i][1] + '"></i>' + VMIX[i][0] + " " + Math.round(v / d3.sum(mix) * 100) + "%</span>"; }).join("") + "</div></div>"] : null,
        [sh ? "Ships per day · last 12 months" : "What it is", (sh ? '<svg class="rc-spark" id="rc-spark"></svg>' : "") + '<div class="rc-note">' + esc(c.what) + (sh ? " Counts from IMF PortWatch (satellite ship tracking)." : " Ship counts come from IMF PortWatch once it answers.") + "</div>"],
        BYPASS[c.name] ? ["Pipelines that bypass it", BYPASS[c.name].map(function (n) { return '<button class="nb rc-pipe" data-p="' + esc(n) + '">' + esc(n) + "</button>"; }).join(" · ")] : null,
        ["Markets that depend on it", '<div class="lk" id="rc-linked"><span class="mut">getting prices…</span></div>'],
        [null, headlinesHTML(mentions(words, c.lat, c.lng, 2.5))]
      ].filter(Boolean),
      actions: [],
      after: function () {
        if (sh) {
          var sv = $("rc-spark"), vals = sh.days.map(function (d) { return d[1]; });
          spark(sv, vals, true, 0, " ships", 300, 34, sh.days.map(function (d) { return d[0]; }));
          sv.querySelector("path:nth-child(2)").setAttribute("stroke", C("--choke")); sv.querySelector("path").setAttribute("fill", C("--choke"));
        }
        card.querySelectorAll(".rc-pipe").forEach(function (b) { b.onclick = function () { var p = pipes.find(function (q) { return q.name === b.dataset.p; }); if (p) { var mid = p.pts[Math.floor(p.pts.length / 2)]; focus(mid[0], mid[1], 1.3); showPipe(p); } }; });
        loadLinked("choke", c.name, "", $("rc-linked"));
      }
    });
  }
  function showPipe(p) {
    var line = { type: "LineString", coordinates: p.pts.map(function (q) { return [q[1], q[0]]; }) };
    var km = Math.round(d3.geoLength(line) * 6371 / 10) * 10;
    var key = p.name.toLowerCase().replace(/ \(.*\)$/, "").split(" (")[0];
    var words = [key].concat(key.indexOf("–") > 0 ? [] : []);
    rich({
      hash: "pipe=" + slug(p.name), color: C("--" + p.kind), title: p.name.toUpperCase(), badge: p.status.toUpperCase(), badgeColor: PST[p.status],
      sub: (p.kind === "oil" ? "Oil" : "Gas") + " pipeline · " + p.from + " → " + p.to, watch: ["pipe", p.name], explain: { title: p.name, names: [p.name.replace(/ \(.*\)$/, "") + " pipeline"], kind: "pipeline", text: p.name + ": " + p.note },
      boxes: [["Flows", esc(p.from.split(" (")[0]) + " → " + esc(p.to.split(" (")[0]), "#34d399"], ["Status", p.status, PST[p.status]], ["Length ≈", km.toLocaleString() + " km", "var(--fg)"]],
      sections: [["What it is", '<div class="rc-note" style="color:var(--fg)">' + esc(p.note) + '</div><div class="rc-note">Route drawn approximately. The status is what Archie knew when it was last updated; anything newer shows in the news below, and a watched pipeline pops up an alert if headlines say it was hit or halted.</div>'],
        ["Markets that depend on it", '<div class="lk" id="rc-linked"><span class="mut">getting prices…</span></div>'],
        [null, headlinesHTML(mentions(words, null, null, 0))]],
      after: function () { loadLinked("pipe", p.name, p.kind, $("rc-linked")); }
    });
  }
  function localTime(tz) { return new Date().toLocaleTimeString("en-US", { timeZone: tz, hour: "numeric", minute: "2-digit" }); }
  function hrs(h) { var H = Math.floor(h), M = Math.round((h - H) * 60); return (H % 12 || 12) + (M ? ":" + String(M).padStart(2, "0") : "") + (H < 12 ? " am" : " pm"); }
  function showEx(x) {
    var o = isOpen(x), q = x.q, up = q ? q.chg >= 0 : true, tierCol = { MAJOR: C("--lime"), DEVELOPED: "#9ec5ff", EMERGING: C("--muted"), FRONTIER: C("--quake") }[x.tier];
    rich({
      hash: "ex=" + x.name, color: "#34d399", title: x.name, badge: x.tier, badgeColor: tierCol, sub: x.full, watch: ["asset", EXIDX[x.name]], explain: { title: x.full, names: [x.full, x.idx], kind: "index" },
      boxes: [["Location", x.city + ", " + x.cc, "#34d399"], ["Local time", localTime(x.tz), "var(--fg)"], ["Status", o ? "● open" : "closed", o ? C("--up") : C("--muted")]],
      sections: [
        [x.idx + " · today", q ? '<div class="rc-big ' + (up ? "up" : "dn") + '">' + (up ? "▲ +" : "▼ −") + Math.abs(q.chg).toFixed(2) + '%</div><svg class="rc-spark" id="rc-spark"></svg>' : '<div class="rc-note">No price yet (delayed quotes come in while online).</div>'],
        ["About", '<div class="rc-note" style="color:var(--fg)">' + esc(x.desc) + '</div><div class="rc-note">Trading hours ' + hrs(x.open[0]) + "–" + hrs(x.open[1]) + " local" + (x.wk[0] === "Fri" ? ", Sunday to Thursday" : ", Monday to Friday") + ".</div>"],
        [null, headlinesHTML(nearby(x.lat, x.lng, 1.5))]
      ],
      actions: [["open the morning note", openNote]],
      after: function () { if (q && q.spark && q.spark.length > 1) spark($("rc-spark"), q.spark, up, 2, "", 300, 34); }
    });
  }
  function showBank(b) {
    var fred = (S && S.fred) || {}, rate = "not in the free feeds";
    if (b.live === "fed" && fred["Fed funds upper"] && fred["Fed funds upper"].now != null) rate = fred["Fed funds lower"].now.toFixed(2) + "–" + fred["Fed funds upper"].now.toFixed(2) + "%";
    if (b.live === "ecb" && fred["ECB deposit rate"] && fred["ECB deposit rate"].now != null) rate = fred["ECB deposit rate"].now.toFixed(2) + "%";
    var kw = { Fed: ["fed ", "fomc", "federal reserve"], ECB: ["ecb", "european central bank"], BoE: ["bank of england"], BoJ: ["bank of japan", "boj"] }[b.short] || [b.name.toLowerCase()];
    var odds = ((S && S.predictions) || []).filter(function (p) { var t = p.q.toLowerCase(); return kw.some(function (k) { return t.indexOf(k.trim()) >= 0; }); }).slice(0, 3);
    rich({
      hash: "cb=" + b.short, color: "#fbbf24", title: b.short.toUpperCase(), badge: "CENTRAL BANK", badgeColor: "#fbbf24", sub: b.name, explain: { title: b.name, names: [b.name], kind: "organization" },
      boxes: [["Location", b.city, "#34d399"], ["Policy rate", rate, "var(--fg)"], ["Source", b.live ? "FRED" : "news", "var(--muted)"]],
      sections: [
        odds.length ? ["Prediction-market odds", odds.map(function (p) { return '<div class="pq" style="padding:0"><span>' + esc(p.q) + '</span><span class="px">' + p.yes + '%</span><div class="meter" style="grid-column:1/-1"><span style="width:' + p.yes + '%"></span></div></div>'; }).join("") + '<div class="rc-note">From Polymarket.</div>'] : null,
        [null, headlinesHTML(mentions(kw, null, null, 0))]
      ].filter(Boolean),
      actions: [["open the morning note", openNote]]
    });
  }

  /* ============================ mines ============================ */
  function mineSVG(col, art) {   // a pickaxe; artisanal sites get a dashed ring
    return '<svg viewBox="-12 -12 24 24" width="17" height="17" aria-hidden="true"><circle r="10" fill="#0b0d09" stroke="' + col + '" stroke-width="' + (art ? 1.6 : 2) + '"' + (art ? ' stroke-dasharray="3 2"' : "") + '/><path d="M-5.5,-3.5 C-2,-6.5 2,-6.5 5.5,-3.5 M0,-5.2 L0,6.5" stroke="' + col + '" stroke-width="2" fill="none" stroke-linecap="round"/></svg>';
  }
  function mineWords(m) { return m[0].replace(/\s*\(.*\)$/, "").toLowerCase().split(/[\s\-]+/).filter(function (w) { return w.length > 4 && ["mines", "fields", "field", "industrial", "artisanal", "north", "western", "mount", "salar", "cobalt", "copper", "lithium", "uranium", "gold", "iron", "earths"].indexOf(w) < 0; }); }
  function showMine(m) {
    var col = mineCol(m), art = m[6] === "artisanal", key = m[0].replace(/\s*\(.*\)$/, "");
    rich({
      hash: "mine=" + slug(m[0]), color: col, title: key.toUpperCase(), badge: art ? "ARTISANAL" : "INDUSTRIAL", badgeColor: art ? C("--quake") : col,
      sub: m[4].charAt(0).toUpperCase() + m[4].slice(1) + " · " + m[3], watch: ["keyword", key],
      boxes: [["Country", esc(m[3]), "#34d399"], ["Mines", esc(m[4].split(",")[0]), col], ["Kind", art ? "artisanal" : "industrial", art ? C("--quake") : "var(--fg)"]],
      sections: [
        [null, '<dl class="facts own"><dt>Run by</dt><dd>' + esc(m[5]) + "</dd><dt>Produces</dt><dd>" + esc(m[4]) + "</dd><dt>Share of world</dt><dd>" + esc(m[7]) + "</dd></dl>"],
        ["About", '<div class="rc-note" style="color:var(--fg)">' + esc(m[8]) + "</div>"],
        ["Why markets care", (m[9] ? '<div class="rc-note" style="color:var(--fg);margin-bottom:6px">' + esc(m[9]) + "</div>" : "") + (m[10].length ? '<div class="lk" id="rc-linked"><span class="mut">getting prices…</span></div>' : '<div class="rc-note">No traded market for this one.</div>')],
        [null, headlinesHTML(mentions(mineWords(m), m[1], m[2], 1.2))],
        [null, '<div class="rc-note">' + (art ? "Artisanal means dug by hand or with simple tools, usually informally. " : "") + "Shares of world supply are rough recent figures. Star it to get an alert if it's in headlines about a halt, attack or accident.</div>"]
      ],
      explain: { title: key, names: [key.indexOf(" ") > 0 || /mine/i.test(key) ? key : key + " mine"], kind: "mine", text: key + " (" + m[4] + ", " + m[3] + ")" },
      after: function () { if (m[10].length) loadLinked("list", m[10].map(function (x) { return x.join("~"); }).join("|"), "", $("rc-linked")); }
    });
  }

  /* ============================ Antarctic stations ============================ */
  var stnSVG = '<svg viewBox="-12 -12 24 24" width="15" height="15" aria-hidden="true"><path d="M-8,6 L-8,-1 L0,-7 L8,-1 L8,6 Z" fill="#0b0d09" stroke="#9ec5ff" stroke-width="2" stroke-linejoin="round"/><rect x="-2" y="1" width="4" height="5" fill="#9ec5ff"/></svg>';
  var WX = { 0: "clear", 1: "mostly clear", 2: "partly cloudy", 3: "overcast", 45: "fog", 48: "freezing fog", 51: "light drizzle", 53: "drizzle", 55: "heavy drizzle", 56: "freezing drizzle", 57: "freezing drizzle", 61: "light rain", 63: "rain", 65: "heavy rain", 66: "freezing rain", 67: "freezing rain", 71: "light snow", 73: "snow", 75: "heavy snow", 77: "snow grains", 80: "rain showers", 81: "rain showers", 82: "heavy showers", 85: "snow showers", 86: "heavy snow showers", 95: "thunderstorm", 96: "thunderstorm", 99: "thunderstorm" };
  function fF(c) { return Math.round(c * 9 / 5 + 32); }
  function showStation(st) {
    rich({
      hash: "station=" + slug(st[0]), color: "#9ec5ff", title: st[0].toUpperCase(), badge: st[6] === "year" ? "YEAR-ROUND" : "SUMMER ONLY", badgeColor: st[6] === "year" ? C("--up") : C("--muted"),
      sub: st[3] + " · " + st[5],
      boxes: [["Opened", String(st[7]), "var(--fg)"], ["Right now", '<span id="stn-t">…</span>', "#9ec5ff"], ["Local time", '<span id="stn-lt">…</span>', "var(--fg)"]],
      sections: [
        ["About", '<div class="rc-note" style="color:var(--fg)">' + esc(st[8]) + "</div>"],
        ["Conditions", '<div class="rc-note" id="stn-wx" style="color:var(--fg)">getting the weather…</div>'],
        [null, headlinesHTML(mentions([st[0].split(" ")[0].toLowerCase().replace(/[^a-zà-ü]/g, "")].filter(function (w) { return w.length > 4; }), st[1], st[2], 3))],
        [null, '<div class="rc-note">' + (st[6] === "year" ? "Staffed all year; the winter crew is usually a few dozen people or fewer." : "Staffed only in the southern summer (about November to February).") + " Weather from Open-Meteo, a weather model, not the station's own instruments.</div>"]
      ],
      actions: st[9] ? [["station webcam", function () { window.open(st[9], "_blank"); }]] : [],
      explain: { title: st[0], names: [st[0]], kind: "research station", text: st[0] + ", " + st[3] + " (Antarctica)" },
      after: function () {
        api("/api/wx?lat=" + st[1] + "&lng=" + st[2]).then(function (w) {
          if (!$("stn-wx")) return;
          if (w.error || w.temp_c == null) { $("stn-wx").textContent = "No weather right now (offline?)."; $("stn-t").textContent = "—"; $("stn-lt").textContent = "—"; return; }
          $("stn-t").textContent = fF(w.temp_c) + "°F";
          var off = w.utc_offset || 0, lt = new Date(Date.now() + off * 1000);
          $("stn-lt").textContent = lt.toLocaleTimeString("en-US", { timeZone: "UTC", hour: "numeric", minute: "2-digit" });
          var dl = w.daylight_s, sun = dl == null ? "" : dl < 60 ? "Polar night: the sun doesn't rise today." : dl > 86000 ? "Midnight sun: the sun doesn't set today." : "About " + Math.round(dl / 3600) + " hours of daylight today.";
          $("stn-wx").innerHTML = esc(fF(w.temp_c) + "°F (" + Math.round(w.temp_c) + "°C), feels like " + fF(w.feels_c) + "°F. " + (WX[w.code] ? WX[w.code].charAt(0).toUpperCase() + WX[w.code].slice(1) + ". " : "") +
            "Wind " + Math.round(w.wind_kmh * 0.6214) + " mph" + (w.gust_kmh ? ", gusts to " + Math.round(w.gust_kmh * 0.6214) + " mph" : "") + ". " + sun);
        }).catch(function () { var e = $("stn-wx"); if (e) e.textContent = "No weather right now (offline?)."; });
      }
    });
  }

  /* ============================ countries ============================ */
  var W110, W50, countries, countries50, land50, nbIdx, byName50 = {}, geoms50;
  var ALIAS = { "Dem. Rep. Congo": "Democratic Republic of the Congo", "Central African Rep.": "Central African Republic", "S. Sudan": "South Sudan", "Bosnia and Herz.": "Bosnia and Herzegovina", "Dominican Rep.": "Dominican Republic", "Eq. Guinea": "Equatorial Guinea", "W. Sahara": "Western Sahara", "Solomon Is.": "Solomon Islands", "Falkland Is.": "Falkland Islands", "Fr. S. Antarctic Lands": "French Southern and Antarctic Lands", "N. Cyprus": "Northern Cyprus", "United States of America": "United States", "Macedonia": "North Macedonia", "eSwatini": "Eswatini" };
  function neighbors(name) {
    var i = geoms50.findIndex(function (g) { return g.properties.name === name; });
    return i < 0 ? [] : nbIdx[i].map(function (j) { return geoms50[j].properties.name; }).filter(function (n) { return n !== "Antarctica"; });
  }
  function flag(a2) { return a2 ? a2.replace(/./g, function (c) { return String.fromCodePoint(127397 + c.charCodeAt(0)); }) : ""; }
  var selCountry = null;
  function showCountry(name) {
    var f = byName50[name] || countries.find(function (c) { return c.properties.name === name; });
    if (!f) return;
    selCountry = name; setHash("country=" + name);
    var lvl = shade[ALIAS[name] || name] || shade[name];
    var inside = function (x) { return x.lat != null && d3.geoContains(f, [x.lng, x.lat]); };
    var evs = EVENTS.filter(function (e) { return inWindow(e.last, 72) && (e.country === (ALIAS[name] || name) || inside(e)); }).sort(function (a, b) { return b.last - a.last; });
    var sts = STORIES.concat(EVENTS).filter(function (s) { return inWindow(s.last, 72) && (s.country === (ALIAS[name] || name) || inside(s) || (s.t || "").indexOf(name) >= 0); }).sort(function (a, b) { return b.last - a.last; });
    var ex = exchanges.filter(inside), qs = quakes.filter(function (q) { return inside(q) && inWindow(q.time, 24); });
    var area = Math.round(d3.geoArea(f) / (4 * Math.PI) * 510.1e6 / 1000) * 1000, nb = neighbors(name);
    var fx = FACTS[name];
    var h = '<div class="cv-top"><button class="back" id="cv-back">‹ feed</button><span style="flex:1"></span>' + (lvl ? '<span class="lvl" style="background:' + C(LVL[lvl].v) + '">' + LVL[lvl].name.toUpperCase() + "</span>" : "") +
      '<button class="back" id="cv-watch">' + (isWatched("country", name) ? "★ watching" : "☆ watch") + "</button></div>";
    h += '<div class="pb"><div class="cv-name" id="cv-name">' + (fx ? flag(fx[0]) + " " : "") + esc(name) + '</div><dl class="facts" id="cv-facts">' +
      (fx ? "<dt>Capital</dt><dd>" + fx[1] + "</dd><dt>People</dt><dd>" + fx[2] + "</dd><dt>Currency</dt><dd>" + fx[3] + "</dd><dt>Language</dt><dd>" + fx[4] + "</dd>" : '<dt>Facts</dt><dd style="color:var(--muted)">loading…</dd>') +
      "</dl><dl class=\"facts\"><dt>Area</dt><dd>≈ " + area.toLocaleString() + " km²</dd><dt>Borders</dt><dd>" + (nb.length ? nb.map(function (n) { return '<button class="nb" data-c="' + esc(n) + '">' + esc(n) + "</button>"; }).join(", ") : "none (island)") + "</dd>" +
      (ex.length ? "<dt>Market</dt><dd>" + ex.map(function (x) { return x.name + (x.chg != null ? ' <span class="' + (x.chg >= 0 ? "up" : "dn") + '">' + (x.chg >= 0 ? "▲ +" : "▼ −") + Math.abs(x.chg).toFixed(2) + "%</span>" : "") + (isOpen(x) ? " · open" : " · closed"); }).join(", ") + "</dd>" : "") + "</dl>";
    h += '<div class="grp-h">Markets tied to ' + esc(name) + '</div><div class="lk" id="cv-linked"><span class="mut">getting prices…</span></div>';
    if (evs.length) { h += '<div class="grp-h" style="color:var(--war)">On the ground · ' + evs.length + "</div>"; evs.slice(0, 12).forEach(function (e) { h += feedItemHTML(e); }); }
    h += '<div class="grp-h">Latest articles · ' + sts.length + "</div>";
    if (!sts.length) h += '<p class="note">No stories about ' + esc(name) + " in the last three days" + (S && S.online ? "." : " (offline).") + "</p>";
    sts.slice(0, 15).forEach(function (s) { h += '<div class="art" data-id="' + s.id + '"><div class="t">' + esc(s.t) + '</div><div class="m">' + esc(short(s.src[0] ? s.src[0].name : "", 30)) + (s.n > 1 ? " +" + (s.n - 1) + " more" : "") + " · " + ago(minsAgo(s.last)) + ' · <a href="#" class="sv">save</a>' + (s.src[0] && s.src[0].url ? ' · <a href="' + esc(s.src[0].url) + '" target="_blank" rel="noopener">read ↗</a>' : "") + "</div></div>"; });
    if (qs.length) h += '<div class="grp-h">Earthquakes</div>' + qs.map(function (q) { return '<div class="art"><div class="t">M' + q.m.toFixed(1) + " " + esc(q.place) + '</div><div class="m">' + ago(minsAgo(q.time)) + " · USGS</div></div>"; }).join("");
    var cal = ((S && S.cal) || []).filter(function (i) { return i.where === (ALIAS[name] || name) || i.where === name || (i.kind === "election" && i.title.indexOf(name) >= 0); }).slice(0, 5);
    if (cal.length) h += '<div class="grp-h">Coming up</div>' + cal.map(function (i) { return '<div class="art"><div class="t">' + esc(i.title) + '</div><div class="m">' + calDate(i) + " · " + esc(i.kind) + "</div></div>"; }).join("");
    h += '<div class="row"><button class="btn primary" id="cv-ask">ask Archie about ' + esc(name) + '</button><button class="btn" id="cv-bg">background</button></div></div>';
    var cv = $("countryview"); cv.innerHTML = h; cv.hidden = false; $("feedview").hidden = true;
    setPane("right", true);
    $("cv-back").onclick = closeCountry;
    $("cv-watch").onclick = function () { toggleWatch("country", name); this.textContent = isWatched("country", name) ? "★ watching" : "☆ watch"; };
    $("cv-ask").onclick = function () { askMap("What's happening in " + name + "?"); };
    $("cv-bg").onclick = function () { explainIt({ title: name, names: [ALIAS[name] || name], kind: "country", text: "The current situation in " + name + (lvl ? " (" + LVL[lvl].name + ")" : "") + "." + (evs[0] ? " Latest: " + evs[0].t : "") }); };
    cv.querySelectorAll(".nb").forEach(function (b) { b.onclick = function () { showCountry(b.dataset.c); flyTo(b.dataset.c); }; });
    loadLinked("country", ALIAS[name] || name, "", $("cv-linked"));
    cv.querySelectorAll(".cf").forEach(bindFeedItem);
    cv.querySelectorAll(".art[data-id]").forEach(function (a) {
      a.querySelector(".t").style.cursor = "pointer"; a.querySelector(".t").onclick = function () { openById(a.dataset.id); };
      var sv = a.querySelector(".sv"); if (sv) sv.onclick = function (e) { e.preventDefault(); var s = STORIES.find(function (x) { return x.id === a.dataset.id; }) || EVENTS.find(function (x) { return x.id === a.dataset.id; }); if (s) saveItem(s, s.type && ET[s.type] && EVENTS.indexOf(s) >= 0 ? "event" : "story"); };
    });
    if (!fx || true) api("/api/country?name=" + encodeURIComponent(ALIAS[name] || name)).then(function (d) {
      if (!d || !d.name || selCountry !== name) return;
      var cur = d.currencies ? Object.values(d.currencies).map(function (c) { return c.name; }).join(", ") : "";
      var lang = d.languages ? Object.values(d.languages).join(", ") : "";
      $("cv-name").textContent = (d.flag ? d.flag + " " : "") + name;
      $("cv-facts").innerHTML = "<dt>Capital</dt><dd>" + esc((d.capital || []).join(", ") || "—") + "</dd><dt>People</dt><dd>" + (d.population ? (d.population / 1e6 >= 1 ? (d.population / 1e6).toFixed(d.population > 1e8 ? 0 : 1) + "M" : Math.round(d.population / 1000) + "K") : "—") +
        "</dd><dt>Currency</dt><dd>" + esc(cur || "—") + "</dd><dt>Language</dt><dd>" + esc(lang || "—") + "</dd><dt>Region</dt><dd>" + esc(d.subregion || d.region || "") + "</dd>";
    }).catch(function () { });
    refreshSelection();
  }
  function closeCountry() { selCountry = null; $("countryview").hidden = true; $("feedview").hidden = false; refreshSelection(); }
  function refreshSelection() { if (view === "globe") G.polygonAltitude(G.polygonAltitude()); else drawMap(); }
  function flyTo(name) { var f = byName50[name]; if (!f) return; var c = d3.geoCentroid(f); focus(c[1], c[0], 1.2); }

  /* ============================ right pane: feeds ============================ */
  function feedItemHTML(e) {
    var R = regionOf(e.region);
    return '<button class="cf' + (e.fresh ? " new" : "") + (isNewItem(e) ? " unseen" : "") + '" data-id="' + e.id + '"><span class="sev" style="background:' + ET[e.type].col + '"></span><span>' +
      '<div class="meta">' + icon(e.type, 7) + (isNewItem(e) ? '<span class="newtag">NEW</span>' : "") + '<span class="zone">' + esc((R ? R.name : e.country || "World").toUpperCase()) + "</span><span>" + ago(minsAgo(e.last)) + "</span>" + (e.unconfirmed ? '<span style="color:var(--quake)">unconfirmed</span>' : '<span style="color:var(--up)">' + e.n + " sources</span>") + "</div>" +
      '<div class="tx">' + esc(e.t) + "</div><div>" + srcLine(e) + "</div></span></button>";
  }
  function bindFeedItem(b) { b.onclick = function () { var e = EVENTS.find(function (x) { return x.id === b.dataset.id; }); if (e) { if (e.lat != null) focus(e.lat, e.lng, 0.5); showEvent(e); } }; }
  var warFilter = "all";
  function renderWar() {
    var list = EVENTS.filter(function (e) { return (!region || e.region === region) && inWindow(e.last, 72) && (warFilter === "all" || (warFilter === "confirmed" ? e.confirmed : !e.confirmed)); }).sort(function (a, b) { return b.last - a.last; });
    $("ct-war").textContent = list.length;
    var R = regionOf(region);
    var head = '<div class="livebar"><b>●</b><span>' + (tEnd ? "AS OF " + new Date(tEnd * 1000).toLocaleString([], { weekday: "short", hour: "numeric", minute: "2-digit" }).toUpperCase() : "LIVE") + " · " + (R ? R.name.toUpperCase() : "ALL REGIONS") + '</span><span style="flex:1"></span>' +
      (R ? '<button class="back" id="w-reg">' + (isWatched("region", R.id) ? "★ watching" : "☆ watch") + "</button>" : "") + "</div>" +
      '<div class="chips" style="margin:0 0 6px">' + ["all", "confirmed", "unconfirmed"].map(function (k) { return '<button class="chip wf" data-k="' + k + '" aria-pressed="' + (warFilter === k) + '">' + k + "</button>"; }).join("") + "</div>";
    if (R && R.sides.length) head += '<div class="note" style="margin:0 2px 6px">Sources from both sides (' + R.sides.join(" and ") + ") are kept and labeled. Nothing is dropped for being one-sided; it's marked.</div>";
    $("p-war").innerHTML = head + (list.length ? list.slice(0, 150).map(feedItemHTML).join("") : '<p class="note">' + (S && S.online ? "Nothing reported here yet in this window." : "Offline, and nothing stored for this window.") + "</p>") +
      '<p class="note">Reports come from public Telegram channels, local papers in their own language, outlets and official statements, translated on this PC. One source = <span style="color:var(--quake)">unconfirmed</span> until a second, separate source matches.</p>';
    $("p-war").querySelectorAll(".cf").forEach(bindFeedItem);
    $("p-war").querySelectorAll(".wf").forEach(function (b) { b.onclick = function () { warFilter = b.dataset.k; renderWar(); }; });
    if ($("w-reg")) $("w-reg").onclick = function () { toggleWatch("region", R.id); renderWar(); };
  }
  function renderNews() {
    var list = STORIES.filter(function (s) { return inWindow(s.last, 36) && (!region || s.region === region); }).sort(function (a, b) { return (b.n - a.n) || (b.last - a.last); });
    $("ct-news").textContent = list.length;
    var box = $("p-news"); box.innerHTML = "";
    list.slice(0, 120).forEach(function (s) {
      var b = document.createElement("button"); b.className = "story" + (isNewItem(s) ? " unseen" : "");
      b.innerHTML = '<span class="bar" style="background:' + C(TOPIC[s.topic]) + '"></span><span><div class="t">' + esc(s.t) + '</div><div class="m">' + covHTML(s, "minicov") + "<span>" + s.n + (s.n === 1 ? " outlet" : " outlets") + (s.place ? " · " + esc(s.place) : "") + " · " + ago(minsAgo(s.last)) + "</span>" + (s.one ? '<span class="onesided">one-sided</span>' : "") + "</div></span>";
      b.onclick = function () { if (s.lat != null) focus(s.lat, s.lng); showStory(s); };
      box.appendChild(b);
    });
    if (!list.length) box.innerHTML = '<p class="note">No stories in this window yet.</p>';
  }
  function setTab(t) {
    ["war", "news", "mk", "saved"].forEach(function (k) { $("tab-" + k).setAttribute("aria-selected", k === t); $("p-" + k).hidden = k !== t; });
    if (t === "saved") renderSaved();
    closeCountry();
  }
  $("tab-war").onclick = function () { setTab("war"); };
  $("tab-news").onclick = function () { setTab("news"); };
  $("tab-mk").onclick = function () { setTab("mk"); };
  $("tab-saved").onclick = function () { setTab("saved"); };

  /* ============================ saving articles ============================ */
  function saveItem(it, kind) {
    var src = it.src.filter(function (s) { return s.url && s.feed !== "telegram"; })[0] || it.src.filter(function (s) { return s.url; })[0] || it.src[0] || {};
    var payload = { title: src.lang && src.lang !== "en" ? it.t : (src.title || it.t), url: src.url || "", publisher: short(src.name, 60), author: src.author || "", time: src.time || it.last,
      place: it.place || it.country || "", hash: kind + "=" + it.id, translated: src.lang && src.lang !== "en" ? it.t : "", others: it.src.slice(1, 8).map(function (s) { return short(s.name, 40); }) };
    note('<span class="k" style="color:var(--lime)">SAVING</span><span>' + esc(payload.title.slice(0, 90)) + "</span>", 3000);
    api("/api/save", payload).then(function (r) {
      if (!r.ok) throw new Error(r.error || "failed");
      note('<span class="k" style="color:var(--lime)">SAVED ✓</span><span>' + esc(payload.title.slice(0, 70)) + '</span><button class="btn" id="sv-show">show in folder</button>', 7000);
      $("sv-show").onclick = function () { api("/api/showfile", { path: r.png }); };
      if (!$("p-saved").hidden) renderSaved();
    }).catch(function (e) { note('<span class="k" style="color:var(--down)">NOT SAVED</span><span>' + esc(String(e.message || e)) + "</span>"); });
  }
  function renderSaved() {
    api("/api/saved").then(function (list) {
      var box = $("p-saved");
      box.innerHTML = '<div class="livebar"><span>SAVED ARTICLES · ' + list.length + '</span></div><p class="note" style="margin:0 2px 8px">Each one is a picture of the headline (publisher, date, author) plus a note with the link and the article text, in World\\Saved Articles on this PC.</p>' +
        list.map(function (s) { return '<button class="sv-item" data-png="' + esc(s.png) + '"><img loading="lazy" src="/saved/' + encodeURI(s.png) + '" alt=""><span>' + esc(s.name.replace(/^\d{4}-\d\d-\d\d - /, "")) + "</span></button>"; }).join("");
      box.querySelectorAll(".sv-item").forEach(function (b) { b.onclick = function () { var m = $("imgmodal"); m.hidden = false; $("imgmodal-img").src = "/saved/" + encodeURI(b.dataset.png); }; });
    });
  }
  $("imgmodal").onclick = function () { this.hidden = true; };

  /* ============================ watchlist ============================ */
  function watchItems() { return (S && S.watch && S.watch.items) || []; }
  function isWatched(kind, id) { return watchItems().some(function (i) { return i.kind === kind && i.id === id; }); }
  function toggleWatch(kind, id, extra) {
    var items = watchItems().slice(), i = items.findIndex(function (x) { return x.kind === kind && x.id === id; });
    if (i >= 0) items.splice(i, 1); else items.push(Object.assign({ kind: kind, id: id }, extra || (kind === "asset" ? { pct: 3 } : {})));
    S.watch.items = items; renderWatch();
    api("/api/watch", { items: items });
  }
  function watchLabel(i) {
    if (i.kind === "region") return (regionOf(i.id) || {}).name || i.id;
    if (i.kind === "asset") { var m = null; MK.forEach(function (g) { g[1].forEach(function (r) { if (r[1] === i.id) m = r[0]; }); }); var ex = Object.keys(EXIDX).find(function (k) { return EXIDX[k] === i.id; }); return (m || ex || i.id) + " ±" + i.pct + "%"; }
    return i.id;
  }
  function renderWatch() {
    var box = $("watch"); if (!box || !S) return;
    var items = watchItems();
    box.innerHTML = items.map(function (i, n) { return '<div class="wi"><span class="wk">' + { region: "area", country: "country", choke: "strait", pipe: "pipe", asset: "price", keyword: "word" }[i.kind] + "</span><span>" + esc(watchLabel(i)) + '</span><button data-n="' + n + '" aria-label="stop watching">×</button></div>'; }).join("") +
      '<div class="wi"><span class="wk">quakes</span><span>M' + (S.watch.quake_min || 6.3) + '+ anywhere</span></div><p class="note" style="margin-top:4px">Archie pops up a note when something confirmed happens in these. Star things on the map to add them. Quiet ' + (S.watch.quiet_hours || [23, 7]).map(function (h) { return hrs(h); }).join("–") + ".</p>";
    box.querySelectorAll("button[data-n]").forEach(function (b) { b.onclick = function () { var it = items[+b.dataset.n]; toggleWatch(it.kind, it.id); }; });
  }

  /* ============================ panes ============================ */
  function setPane(side, open) {
    var p = $("pane-" + side); p.classList.toggle("closed", !open);
    document.body.classList.toggle(side[0] + "-closed", !open);
    $("t-" + side).setAttribute("aria-pressed", open);
  }
  $("t-left").onclick = function () { setPane("left", $("pane-left").classList.contains("closed")); };
  $("t-right").onclick = function () { setPane("right", $("pane-right").classList.contains("closed")); };

  /* ============================ ask the map ============================ */
  var highlight = [];
  function askMap(q) {
    q = (q || $("ask").value || "").trim(); if (!q) return;
    $("ask").value = q;
    var box = $("answer"); box.hidden = false;
    box.innerHTML = '<button class="x" id="ans-x">×</button><div class="h">Asking about the last three days of reports…</div><p class="ans-t">' + esc(q) + "</p>";
    $("ans-x").onclick = function () { box.hidden = true; highlight = []; refresh(); };
    api("/api/ask", { q: q }).then(function (r) {
      var txt = esc(r.answer || "").replace(/\[(\d+)\]/g, '<button class="cite" data-n="$1">$1</button>');
      box.innerHTML = '<button class="x" id="ans-x">×</button><div class="h">Archie · from ' + r.cites.length + ' stored reports</div><p class="ans-t">' + txt + '</p><div class="ans-src">' +
        r.cites.map(function (c) { return '<button class="cite-row" data-n="' + c.n + '"><b>' + c.n + "</b> " + esc(c.title.slice(0, 110)) + "</button>"; }).join("") + "</div>";
      $("ans-x").onclick = function () { box.hidden = true; highlight = []; refresh(); };
      highlight = r.cites.filter(function (c) { return c.lat != null; });
      refresh();
      if (highlight.length) focus(highlight[0].lat, highlight[0].lng, 1.4);
      box.querySelectorAll("[data-n]").forEach(function (b) { b.onclick = function () { var c = r.cites[+b.dataset.n - 1]; if (c) openById(c.id); }; });
    }).catch(function () { box.innerHTML = '<button class="x" onclick="this.parentNode.hidden=true">×</button><p class="ans-t">Couldn\'t ask right now.</p>'; });
  }
  $("ask").addEventListener("keydown", function (e) { if (e.key === "Enter") askMap(); });

  /* ---------- background: what this is and how it got here (offline Wikipedia first) ---------- */
  function explainIt(o) {
    var box = $("answer"); box.hidden = false;
    box.innerHTML = '<button class="x" id="ans-x">×</button><div class="h">Background · ' + esc(o.title || "") + '</div><p class="ans-t mut">Looking it up in Wikipedia and writing it up…</p>';
    $("ans-x").onclick = function () { box.hidden = true; };
    api("/api/explain", { text: o.text || "", names: o.names || [], kind: o.kind || "" }).then(function (r) {
      if (r.error) throw new Error(r.error);
      var src = r.things.filter(function (t) { return t.source; });
      box.innerHTML = '<button class="x" id="ans-x">×</button><div class="h">Background · ' + esc(o.title || "") + "</div>" +
        (r.background ? '<p class="ans-t">' + esc(r.background) + "</p>" : "") +
        (r.why ? '<p class="ans-t"><b style="color:var(--lime);font-weight:500">Why it matters now:</b> ' + esc(r.why) + "</p>" : "") +
        (r.things.length ? '<div class="h" style="margin-top:6px">Who and what</div>' + r.things.map(function (t) {
          return '<details class="bg-thing"><summary><b>' + esc(t.title || t.name) + "</b>" + (t.kind ? ' <span class="mut">' + esc(t.kind) + "</span>" : "") +
            (t.source ? "" : ' <span class="mut">· not found</span>') + "</summary>" + (t.summary ? "<p>" + esc(t.summary) + "…</p>" : "") +
            (t.source ? '<p class="mut">' + esc(t.source) + (t.url ? ' · <a href="' + esc(t.url) + '" target="_blank" rel="noopener">read ↗</a>' : "") + "</p>" : "") + "</details>";
        }).join("") : "") +
        '<p class="note" style="margin-top:8px">Written from ' + (src.length ? src.map(function (t) { return esc(t.source); }).filter(function (v, i, a) { return a.indexOf(v) === i; }).join(" and ") : "the item itself (nothing found in Wikipedia)") + ". Your offline Wikipedia copy is only as new as its download, so anything newer comes from the news itself.</p>";
      $("ans-x").onclick = function () { box.hidden = true; };
    }).catch(function (e) { box.querySelector(".ans-t").textContent = "Couldn't write the background: " + (e.message || e); });
  }
  /* ---------- catch me up: how a story developed, day by day ---------- */
  function tokensOf(t) { return String(t || "").toLowerCase().split(/[^a-z0-9\u0400-\u04ff\u0600-\u06ff]+/).filter(function (w) { return w.length > 2 && ["the", "and", "for", "with", "from", "that", "this", "after", "over", "says"].indexOf(w) < 0; }); }
  function catchUp(id, title) {
    var o = $("catch"); if (o) o.remove();
    o = document.createElement("div"); o.id = "catch"; o.className = "note-wrap";
    o.innerHTML = '<div class="note-card cu-card"><p class="note">Finding everything about this story from the last two weeks…</p></div>';
    document.body.appendChild(o);
    o.addEventListener("click", function (e) { if (e.target === o) o.remove(); });
    api("/api/thread?id=" + encodeURIComponent(id)).then(function (th) {
      if (th.error) throw new Error(th.error);
      var byDay = {};
      th.entries.forEach(function (e) { var d = new Date(e.last * 1000).toDateString(); (byDay[d] = byDay[d] || []).push(e); });
      var dayKeys = Object.keys(byDay).sort(function (a, b) { return new Date(a) - new Date(b); });
      var span = th.entries.length ? Math.max(1, Math.round((th.entries[th.entries.length - 1].last - th.entries[0].first) / 86400)) : 1;
      var h = '<div class="note-card cu-card"><button class="x" id="cu-x" aria-label="Close">×</button>' +
        '<div class="n-top"><span class="brand">CATCH ME <b>UP</b></span><span class="stamp">' + th.entries.length + " reports over " + span + (span === 1 ? " day" : " days") + "</span></div>" +
        '<h2 class="cu-title">' + esc(title || th.title) + "</h2>" +
        '<div class="cu-sum" id="cu-sum"><div class="h">The story so far</div><p class="mut">Archie is reading the timeline…</p></div>' +
        '<div class="h" style="margin-top:6px">Timeline</div><div class="cu-line">' +
        dayKeys.map(function (d) {
          var dt = new Date(d), today = new Date().toDateString() === d, yest = new Date(Date.now() - 86400000).toDateString() === d;
          return '<div class="cu-day"><div class="cu-date">' + (today ? "Today" : yest ? "Yesterday" : dt.toLocaleDateString([], { weekday: "short", month: "short", day: "numeric" })) + "</div>" +
            byDay[d].map(function (e) {
              var col = e.kind === "event" && ET[e.type] ? ET[e.type].col : "var(--muted)";
              return '<button class="cu-item' + (e.self ? " self" : "") + '" data-id="' + e.id + '"><i style="background:' + col + '"></i><span class="cu-time">' +
                new Date(e.last * 1000).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }) + '</span><span class="cu-t">' + esc(e.t) + '</span><span class="cu-n">' + e.n + (e.n === 1 ? " source" : " sources") + (e.place ? " · " + esc(e.place) : "") + "</span></button>";
            }).join("") + "</div>";
        }).join("") + "</div>" +
        '<p class="n-src">Reports are matched by shared names, places and wording over the last 14 days, so an unrelated item can slip in. The summary is written only from these reports.</p></div>';
      o.innerHTML = h;
      $("cu-x").onclick = function () { o.remove(); };
      o.querySelectorAll(".cu-item").forEach(function (b) {
        b.onclick = function () {
          var e = th.entries.find(function (x) { return x.id === b.dataset.id; }); o.remove();
          if (EVENTS.some(function (x) { return x.id === e.id; }) || STORIES.some(function (x) { return x.id === e.id; })) openById(e.id);
          else location.hash = (e.kind === "event" ? "event=" : "story=") + e.id;
        };
      });
      return api("/api/thread_summary?id=" + encodeURIComponent(id));
    }).then(function (sm) {
      var box = $("cu-sum"); if (!box || !sm) return;
      if (sm.error) { box.querySelector("p").textContent = "No summary right now (" + sm.error + "). The timeline below is complete."; return; }
      box.innerHTML = '<div class="h">The story so far</div><p>' + esc(sm.so_far) + "</p>" + (sm.new ? '<div class="h" style="margin-top:8px;color:var(--lime)">New in the last 24 hours</div><p>' + esc(sm.new) + "</p>" : "");
    }).catch(function (e) { var c = o.querySelector(".note"); if (c) c.textContent = "Couldn't build the timeline: " + (e.message || e); });
  }

  function openById(id) {
    var e = EVENTS.find(function (x) { return x.id === id; }), s = STORIES.find(function (x) { return x.id === id; });
    if (e) { if (e.lat != null) focus(e.lat, e.lng, 0.6); showEvent(e); }
    else if (s) { if (s.lat != null) focus(s.lat, s.lng, 1.2); showStory(s); }
  }

  /* ============================ small overlay helper ============================ */
  function overlay(id, cls, inner) {
    var o = $(id); if (o) o.remove();
    o = document.createElement("div"); o.id = id; o.className = "note-wrap";
    o.innerHTML = '<div class="note-card ' + (cls || "") + '">' + inner + "</div>";
    document.body.appendChild(o);
    o.addEventListener("click", function (e) { if (e.target === o) o.remove(); });
    return o;
  }
  function bestMatch(v) {
    var q = tokensOf(v), best = null, bs = 0;
    STORIES.concat(EVENTS).forEach(function (x) { var t = tokensOf(x.t), n = q.filter(function (w) { return t.indexOf(w) >= 0; }).length; var sc = n / Math.max(1, q.length) + Math.min(x.n, 10) / 100; if (n && sc > bs) { bs = sc; best = x; } });
    return best && bs >= 0.5 ? best : null;
  }

  /* ============================ wrong label? ============================ */
  var LABELS = [["fighting", ["clash", "shelling", "drone", "missile", "blast", "alert"]], ["not fighting", ["defense", "politics", "economy", "police", "protest", "aid", "fire", "ship"]]];
  function wrongLabel(it) {
    var ex = $("c-extra"), old = ex.querySelector(".wl");
    if (old) { old.remove(); return; }
    var cur = it.type && ET[it.type] ? it.type : "other", curName = ET[cur] ? ET[cur].name : "news";
    var box = document.createElement("div"); box.className = "wl";
    box.innerHTML = '<div class="h">What is it really? <span class="mut">now: ' + esc(curName) + "</span></div>" +
      LABELS.map(function (g) { return '<div class="wl-g"><span class="wl-gh">' + g[0] + "</span>" + g[1].map(function (k) { return '<button class="wl-k" data-k="' + k + '"' + (k === cur ? " disabled" : "") + ">" + icon(k, 7) + esc(ET[k].name) + "</button>"; }).join("") + "</div>"; }).join("") +
      '<div class="wl-g"><span class="wl-gh">or</span><button class="wl-k" data-k="other"' + (cur === "other" ? " disabled" : "") + ">just news, no icon</button></div>";
    ex.insertBefore(box, ex.firstChild);
    box.querySelectorAll(".wl-k").forEach(function (b) { b.onclick = function () { step2(b.dataset.k); }; });
    function step2(to) {
      var toName = to === "other" ? "just news" : ET[to].name;
      box.innerHTML = '<div class="h">Relabel as ' + esc(toName) + '</div><p class="note" style="margin:2px 0 6px">Want Archie to remember? Pick the word that gives it away. Stories with that word won\'t be labeled <b>' + esc(curName) + "</b> again.</p>" +
        '<div class="wl-words"><span class="mut">finding words…</span></div><div class="row" style="margin-top:8px"><button class="btn" id="wl-once">just fix this one</button><button class="btn" id="wl-cancel">cancel</button></div>';
      api("/api/label_words?id=" + encodeURIComponent(it.id)).then(function (r) {
        var w = box.querySelector(".wl-words"); if (!w) return;
        w.innerHTML = (r.words || []).map(function (x) { return '<button class="nb-chip wl-w" data-w="' + esc(x) + '">' + esc(x) + "</button>"; }).join(" ") || '<span class="mut">no telling words in this one</span>';
        box.querySelectorAll(".wl-w").forEach(function (b) { b.onclick = function () { send(to, b.dataset.w); }; });
      }).catch(function () { });
      $("wl-once").onclick = function () { send(to, ""); };
      $("wl-cancel").onclick = function () { box.remove(); };
    }
    function send(to, word) {
      box.innerHTML = '<p class="note">Fixing…</p>';
      api("/api/relabel", { id: it.id, type: to, word: word }).then(function (r) {
        if (r.error) { box.innerHTML = '<p class="note">Couldn\'t fix it: ' + esc(r.error) + "</p>"; return; }
        note('<span class="k" style="color:var(--lime)">FIXED</span><span>' + (word ? 'Stories with "' + esc(word) + '" won\'t be labeled ' + esc(curName) + " again. You can undo that in Sources." : "Relabeled this one.") + (r.changed > 1 ? " Updated " + r.changed + " reports." : "") + "</span>", 7000);
        card.hidden = true;
        pull().then(function () { openById(it.id); });
      }).catch(function (e) { box.innerHTML = '<p class="note">Couldn\'t reach Archie (' + esc(e.message || e) + ").</p>"; });
    }
  }

  /* ============================ markets tied to places ============================ */
  function loadLinked(kind, name, pk, el) {
    if (!el) return;
    api("/api/linked?kind=" + kind + "&name=" + encodeURIComponent(name) + (pk ? "&pk=" + pk : "")).then(function (r) {
      var its = (r && r.items) || [];
      if (!el.isConnected) return;
      if (!its.length) { el.innerHTML = '<span class="mut">Nothing mapped for this one yet.</span>'; return; }
      var pre = el.id + "-";
      el.innerHTML = its.map(function (i, n) {
        return '<div class="lk-row" title="' + esc(i.sym) + '"><div class="lk-n"><div class="lk-l">' + esc(i.label) + '</div><div class="lk-w">' + esc(i.why) + '</div></div><svg class="lk-sp" id="' + pre + n + '"></svg><div class="lk-v">' +
          (i.price != null ? fmt(i.price, i.price < 20 ? 3 : 2) : "—") + "<br>" + chgTxt(i.chg, 1) + "</div></div>";
      }).join("") + '<div class="rc-note">Delayed prices (Yahoo Finance); change is since the last close.</div>';
      its.forEach(function (i, n) { var sv = $(pre + n); if (sv && i.spark && i.spark.length > 1) spark(sv, i.spark, (i.chg || 0) >= 0, 2, "", 64, 22); });
    }).catch(function () { if (el.isConnected) el.innerHTML = '<span class="mut">No prices right now (offline?).</span>'; });
  }

  /* ============================ new since you last looked ============================ */
  var SEEN_KEY = "archieWorldLastLooked", seenPrev = null;
  function lsGet(k) { try { return window.localStorage.getItem(k); } catch (e) { return null; } }
  function lsSet(k, v) { try { window.localStorage.setItem(k, v); } catch (e) { } }
  seenPrev = +lsGet(SEEN_KEY) || null;           // first visit ever: nothing is "new"
  function nowS() { return Math.floor(Date.now() / 1000); }
  function isNewItem(x) { return seenPrev != null && !tEnd && (x.arrived || x.first || 0) > seenPrev; }
  function newItems() {
    return EVENTS.filter(isNewItem).concat(STORIES.filter(function (s) { return isNewItem(s) && (s.n >= 2 || s.lat != null); }))
      .sort(function (a, b) { return (b.arrived || b.first) - (a.arrived || a.first); });
  }
  function sinceTxt(t) {
    var d = new Date(t * 1000), today = new Date().toDateString() === d.toDateString(), yest = new Date(Date.now() - 86400000).toDateString() === d.toDateString();
    return (today ? "" : yest ? "yesterday " : d.toLocaleDateString([], { weekday: "short" }) + " ") + d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  }
  function renderNewChip() {
    var b = $("t-new"); if (!b) return;
    var n = newItems().length;
    b.hidden = !n;
    if (n) b.textContent = n + " new since " + sinceTxt(seenPrev);
  }
  function lookedNow() { lsSet(SEEN_KEY, String(nowS())); }
  function cameBack() {
    var t = +lsGet(SEEN_KEY);
    if (t && nowS() - t > 600) { seenPrev = t; renderNewChip(); refresh(); if (S) { renderWar(); renderNews(); } }
  }
  document.addEventListener("visibilitychange", function () { if (document.hidden) lookedNow(); else cameBack(); });
  window.addEventListener("blur", lookedNow);
  window.addEventListener("focus", cameBack);
  window.addEventListener("pagehide", lookedNow);
  function markAllSeen() { seenPrev = nowS(); lookedNow(); renderNewChip(); refresh(); renderWar(); renderNews(); }
  function openNewList() {
    var list = newItems(), evs = list.filter(function (x) { return EVENTS.indexOf(x) >= 0; }), sts = list.filter(function (x) { return EVENTS.indexOf(x) < 0; });
    var row = function (x) {
      var isEv = EVENTS.indexOf(x) >= 0, R = regionOf(x.region);
      return '<button class="cu-item" data-id="' + x.id + '"><i style="background:' + (isEv ? ET[x.type].col : C(TOPIC[x.topic])) + '"></i><span class="cu-time">' + clock(x.arrived || x.first) + '</span><span class="cu-t">' + esc(x.t) + '</span><span class="cu-n">' +
        (isEv ? esc(ET[x.type].name) + " · " + esc((R ? R.name : x.country) || "") + (x.unconfirmed ? " · unconfirmed" : " · " + x.n + " sources") : x.n + (x.n === 1 ? " outlet" : " outlets") + (x.place ? " · " + esc(x.place) : "")) + "</span></button>";
    };
    var o = overlay("newlist", "cu-card", '<button class="x" id="nl-x" aria-label="Close">×</button><div class="n-top"><span class="brand">NEW SINCE <b>' + esc(sinceTxt(seenPrev || nowS()).toUpperCase()) + '</b></span><span class="stamp">' + list.length + " things you haven't seen</span></div>" +
      (evs.length ? '<div class="h">On the ground · ' + evs.length + '</div><div class="cu-line">' + evs.slice(0, 40).map(row).join("") + "</div>" : "") +
      (sts.length ? '<div class="h" style="margin-top:10px">Stories · ' + sts.length + '</div><div class="cu-line">' + sts.slice(0, 40).map(row).join("") + "</div>" : "") +
      (list.length ? "" : '<p class="note">Nothing new since you last looked.</p>') +
      '<div class="row" style="margin-top:12px"><button class="btn primary" id="nl-seen">mark all as seen</button></div>' +
      '<p class="n-src">"New" means Archie first picked it up after you last looked away from this window (minimized it, or switched away for 10+ minutes). New things glow lime on the map until you mark them seen.</p>');
    $("nl-x").onclick = function () { o.remove(); };
    $("nl-seen").onclick = function () { markAllSeen(); o.remove(); };
    o.querySelectorAll(".cu-item").forEach(function (b) { b.onclick = function () { o.remove(); openById(b.dataset.id); }; });
  }

  /* ============================ lessons ============================ */
  function openLesson(id, title) {
    var o = overlay("lesson", "cu-card ls-card", '<div class="n-top"><span class="brand">WORLD <b>LESSON</b></span></div><h2 class="cu-title">' + esc(title || "") + '</h2><p class="note">Archie is reading the whole story and looking up the background. This takes a minute or two on your PC; the globe keeps working meanwhile.</p>');
    api("/api/lesson", { id: id }).then(function (L) {
      if (L.error) throw new Error(L.error);
      var sec = function (h, body) { return body ? '<section class="ls-sec"><div class="h">' + h + "</div>" + body + "</section>" : ""; };
      var p = function (t) { return t ? "<p>" + esc(t) + "</p>" : ""; };
      var h = '<button class="x" id="ls-x" aria-label="Close">×</button><div class="n-top"><span class="brand">WORLD <b>LESSON</b></span><span class="stamp">from ' + L.reports + (L.reports === 1 ? " report" : " reports") + (L.refs && L.refs.length ? " + background" : "") + "</span></div>" +
        '<h2 class="cu-title">' + esc(L.title) + '</h2><div class="ls-from">about: ' + esc(L.story) + "</div>" +
        sec("The big picture", p(L.big_picture)) + sec("How it got here", p(L.background)) +
        sec("Who's involved", (L.who || []).length ? '<dl class="ls-dl">' + L.who.map(function (w) { return "<dt>" + esc(w.name) + "</dt><dd>" + esc(w.role || "") + "</dd>"; }).join("") + "</dl>" : "") +
        sec("Why it matters", p(L.why_it_matters)) +
        sec("Words to know", (L.terms || []).length ? '<dl class="ls-dl">' + L.terms.map(function (t) { return "<dt>" + esc(t.term) + "</dt><dd>" + esc(t.meaning || "") + "</dd>"; }).join("") + "</dl>" : "") +
        sec("What to watch", p(L.watch_next)) +
        sec("Check yourself", (L.check || []).map(function (q, i) { return '<div class="ls-q"><div>' + (i + 1) + ". " + esc(q.q) + '</div><button class="ls-a" data-i="' + i + '">show answer</button><div class="ls-ans" hidden>' + esc(q.a || "") + "</div></div>"; }).join("")) +
        (L.refs && L.refs.length ? '<p class="n-src">Background from ' + L.refs.map(function (r) { return r.url ? '<a href="' + esc(r.url) + '" target="_blank" rel="noopener">' + esc(r.title) + "</a> (" + esc(r.source) + ")" : esc(r.title) + " (" + esc(r.source) + ")"; }).join(", ") + ". Written by the model on your PC from those and the news reports; it can still get things wrong.</p>" : '<p class="n-src">Written by the model on your PC from the news reports only (no background article found); it can still get things wrong.</p>') +
        '<div class="row"><button class="btn primary" id="ls-save">save to Obsidian</button><button class="btn" id="ls-cu">catch me up</button><button class="btn" id="ls-quiz">quiz me on the news</button></div>';
      o.querySelector(".note-card").innerHTML = h;
      $("ls-x").onclick = function () { o.remove(); };
      o.querySelectorAll(".ls-a").forEach(function (b) { b.onclick = function () { b.nextElementSibling.hidden = false; b.remove(); }; });
      $("ls-save").onclick = function () { var b = this; api("/api/lesson_save", { lesson: L }).then(function (r) { b.textContent = r.ok ? "saved to Archie/World/Lessons ✓" : "couldn't save: " + r.error; }); };
      $("ls-cu").onclick = function () { o.remove(); catchUp(id, L.story); };
      $("ls-quiz").onclick = function () { o.remove(); openQuiz(); };
    }).catch(function (e) { var n = o.querySelector(".note"); if (n) n.textContent = "Couldn't make the lesson: " + (e.message || e); });
  }

  /* ============================ news quiz ============================ */
  var quizDays = 7;
  function openQuiz() {
    var o = overlay("quiz", "qz-card", "");
    var card0 = o.querySelector(".note-card");
    function start() {
      card0.innerHTML = '<button class="x" id="qz-x" aria-label="Close">×</button><div class="n-top"><span class="brand">NEWS <b>QUIZ</b></span></div>' +
        '<p class="qz-lead">Five questions from the biggest stories Archie has seen. Each answer links back to its story.</p>' +
        '<div class="chips">' + [[1, "last 24 hours"], [3, "last 3 days"], [7, "this week"]].map(function (d) { return '<button class="chip qz-d" data-d="' + d[0] + '" aria-pressed="' + (quizDays === d[0]) + '">' + d[1] + "</button>"; }).join("") + "</div>" +
        '<div class="row" style="margin-top:12px"><button class="btn primary" id="qz-go">make my quiz</button><button class="btn" id="qz-last" hidden>retake the last one</button></div><div id="qz-hist" class="qz-hist"></div>';
      $("qz-x").onclick = function () { o.remove(); };
      o.querySelectorAll(".qz-d").forEach(function (b) { b.onclick = function () { quizDays = +b.dataset.d; o.querySelectorAll(".qz-d").forEach(function (x) { x.setAttribute("aria-pressed", x === b); }); }; });
      $("qz-go").onclick = make;
      api("/api/quiz_last").then(function (q) { if (q && q.questions && q.questions.length && $("qz-last")) { $("qz-last").hidden = false; $("qz-last").textContent = "retake the last one (" + sinceTxt(q.made) + ")"; $("qz-last").onclick = function () { play(q); }; } }).catch(function () { });
    }
    function make() {
      card0.innerHTML = '<div class="n-top"><span class="brand">NEWS <b>QUIZ</b></span></div><p class="note">Archie is writing your quiz from the ' + (quizDays === 1 ? "last day's" : quizDays === 3 ? "last three days'" : "week's") + " biggest stories. This takes a minute or two on your PC.</p>";
      api("/api/quiz", { n: 5, days: quizDays }).then(function (q) { if (q.error) throw new Error(q.error); play(q); })
        .catch(function (e) { card0.innerHTML = '<button class="x" id="qz-x">×</button><p class="note">Couldn\'t make a quiz: ' + esc(e.message || e) + '</p><div class="row"><button class="btn" id="qz-back">back</button></div>'; $("qz-x").onclick = function () { o.remove(); }; $("qz-back").onclick = start; });
    }
    function play(q) {
      var i = 0, score = 0, answered = false;
      function show() {
        var Q = q.questions[i]; answered = false;
        card0.innerHTML = '<button class="x" id="qz-x" aria-label="Close">×</button><div class="n-top"><span class="brand">NEWS <b>QUIZ</b></span><span class="stamp">question ' + (i + 1) + " of " + q.questions.length + " · score " + score + "</span></div>" +
          '<div class="qz-bar"><span style="width:' + (i / q.questions.length * 100) + '%"></span></div><h2 class="cu-title">' + esc(Q.q) + '</h2><div class="qz-opts">' +
          Q.options.map(function (op, k) { return '<button class="qz-o" data-k="' + k + '"><span class="qz-key">' + (k + 1) + "</span>" + esc(op) + "</button>"; }).join("") + '</div><div id="qz-fb"></div>';
        $("qz-x").onclick = function () { o.remove(); };
        o.querySelectorAll(".qz-o").forEach(function (b) { b.onclick = function () { pick(+b.dataset.k); }; });
      }
      function pick(k) {
        if (answered) return; answered = true;
        var Q = q.questions[i], right = k === Q.answer; if (right) score++;
        o.querySelectorAll(".qz-o").forEach(function (b) { var kk = +b.dataset.k; b.disabled = true; if (kk === Q.answer) b.classList.add("ok"); else if (kk === k) b.classList.add("bad"); });
        $("qz-fb").innerHTML = '<div class="qz-why"><b class="' + (right ? "up" : "dn") + '">' + (right ? "Right." : "Not quite.") + "</b> " + esc(Q.why || "") + "</div>" +
          '<div class="row">' + (Q.id ? '<button class="btn" id="qz-story">see the story</button>' : "") + '<button class="btn primary" id="qz-next">' + (i + 1 < q.questions.length ? "next question" : "see my score") + "</button></div>";
        if ($("qz-story")) $("qz-story").onclick = function () { o.remove(); if (EVENTS.some(function (x) { return x.id === Q.id; }) || STORIES.some(function (x) { return x.id === Q.id; })) openById(Q.id); else location.hash = "story=" + Q.id; };
        $("qz-next").onclick = next;
      }
      function next() { i++; if (i < q.questions.length) show(); else done(); }
      function done() {
        var n = q.questions.length;
        card0.innerHTML = '<button class="x" id="qz-x" aria-label="Close">×</button><div class="n-top"><span class="brand">NEWS <b>QUIZ</b></span></div><div class="qz-score">' + score + " / " + n + '</div><p class="qz-lead" style="text-align:center">' +
          (score === n ? "Perfect. You're on top of the news." : score >= n * 0.6 ? "Solid. You're following the big stories." : "A few got past you. The brief and \"catch me up\" help.") + '</p><div id="qz-hist" class="qz-hist"></div><div class="row" style="justify-content:center"><button class="btn primary" id="qz-again">new quiz</button><button class="btn" id="qz-close">close</button></div>';
        $("qz-x").onclick = $("qz-close").onclick = function () { o.remove(); };
        $("qz-again").onclick = start;
        api("/api/quiz_score", { score: score, total: n }).then(function (r) {
          var h = (r && r.history) || [], el = $("qz-hist"); if (!el || h.length < 2) return;
          el.innerHTML = '<div class="h">Your last quizzes</div><div class="qz-dots">' + h.map(function (x) { var pc = x.total ? x.score / x.total : 0; return '<span title="' + new Date(x.t * 1000).toLocaleDateString() + '" style="height:' + Math.max(4, pc * 36) + "px;background:" + (pc >= 0.8 ? "var(--up)" : pc >= 0.5 ? "var(--quake)" : "var(--down)") + '"></span>'; }).join("") + "</div>";
        }).catch(function () { });
      }
      if (o._kd) document.removeEventListener("keydown", o._kd);
      o._kd = function kd(e) {
        if (!o.isConnected) { document.removeEventListener("keydown", kd); return; }
        if (/^[1-4]$/.test(e.key) && !answered && o.querySelector(".qz-o")) pick(+e.key - 1);
        else if (e.key === "Enter" && answered && $("qz-next")) { e.preventDefault(); next(); }
      };
      document.addEventListener("keydown", o._kd);
      show();
    }
    start();
  }

  /* ============================ storms ============================ */
  var STORMS = {};
  function stormOf(c) { return c ? STORMS[c.id] || null : null; }
  function catOf(kt) { if (kt == null || isNaN(kt)) return null; return kt < 34 ? ["TD", "tropical depression"] : kt < 64 ? ["TS", "tropical storm"] : kt < 83 ? ["Cat 1", "category 1"] : kt < 96 ? ["Cat 2", "category 2"] : kt < 113 ? ["Cat 3", "category 3 (major)"] : kt < 137 ? ["Cat 4", "category 4 (major)"] : ["Cat 5", "category 5 (major)"]; }
  var CATCOL = { TD: "#7dd3fc", TS: "#38bdf8", "Cat 1": "#facc15", "Cat 2": "#fb923c", "Cat 3": "#f97316", "Cat 4": "#ef4444", "Cat 5": "#e879f9" };
  function stormCol(st) { var ct = catOf(st && st.wind_kt); return ct ? CATCOL[ct[0]] : C("--cyclone"); }
  function mph(kt) { return Math.round(kt * 1.151); }
  function kmh(kt) { return Math.round(kt * 1.852); }
  function stormName(c, st) {
    var n = String((st && st.name) || c.title || "storm").split(/\.\s|\s+-\s+|:/)[0].trim();   // GDACS sometimes sends a whole sentence
    n = n.replace(/^(tropical cyclone|tropical depression|tropical storm|super typhoon|major hurricane|hurricane|typhoon|cyclone|storm)\s+/i, "").replace(/-\d{2}$/, "").trim();
    if (n.length > 22) n = n.split(/\s+/)[0];
    return n ? n.charAt(0).toUpperCase() + n.slice(1).toLowerCase() : "Storm";
  }
  function stormPast(st) { var p = (st.past || []).map(function (x) { return [x.lat, x.lng]; }); return p.length ? p : (st.past_line || []); }
  function stormSVG(col, px) {   // the weather-map hurricane symbol: an eye with two curled arms
    return '<svg viewBox="-12 -12 24 24" width="' + px + '" height="' + px + '" aria-hidden="true"><path d="M-1,-9.6 C-7.5,-9.4 -10.2,-3.5 -6.2,0.8 M1,9.6 C7.5,9.4 10.2,3.5 6.2,-0.8" stroke="' + col + '" stroke-width="2.6" fill="none" stroke-linecap="round"/><circle r="4.4" fill="#04060a" stroke="' + col + '" stroke-width="2.6"/><circle r="1.4" fill="' + col + '"/></svg>';
  }
  function compass(deg) { return ["north", "north-northeast", "northeast", "east-northeast", "east", "east-southeast", "southeast", "south-southeast", "south", "south-southwest", "southwest", "west-southwest", "west", "west-northwest", "northwest", "north-northwest"][Math.round(((deg % 360) + 360) % 360 / 22.5) % 16]; }
  function compassShort(deg) { return ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"][Math.round(((deg % 360) + 360) % 360 / 22.5) % 16]; }
  function bearing(a, b) { var f1 = a[0] * Math.PI / 180, f2 = b[0] * Math.PI / 180, dl = (b[1] - a[1]) * Math.PI / 180; return (Math.atan2(Math.sin(dl) * Math.cos(f2), Math.cos(f1) * Math.sin(f2) - Math.sin(f1) * Math.cos(f2) * Math.cos(dl)) * 180 / Math.PI + 360) % 360; }
  function showStorm(c) {
    var st = stormOf(c) || {}, ct = catOf(st.wind_kt), col = stormCol(st), name = stormName(c, st);
    var dir = st.move_dir != null && st.move_dir !== "" ? +st.move_dir : st.fcst && st.fcst.length ? bearing([c.lat, c.lng], [st.fcst[0].lat, st.fcst[0].lng]) : null;
    var mv = dir == null ? "—" : compassShort(dir) + (st.move_kt ? " · " + mph(+st.move_kt) + " mph" : "");
    var mvLong = dir == null ? "" : "moving " + compass(dir) + (st.move_kt ? " at " + mph(+st.move_kt) + " mph" : "");
    var fc = st.fcst || [], past = st.past || [];
    var winds = past.filter(function (p) { return p.wind_kt; }).map(function (p) { return p.wind_kt; }).concat(st.wind_kt ? [st.wind_kt] : []);
    var peak = winds.length ? Math.max.apply(null, winds) : null;
    rich({
      hash: "storm=" + c.id, color: col, title: name.toUpperCase(), badge: ct ? ct[1].toUpperCase() : "TROPICAL CYCLONE", badgeColor: col,
      sub: (st.cls || "Tropical cyclone") + (st.wind_kt ? " · " + mph(st.wind_kt) + " mph (" + kmh(st.wind_kt) + " km/h) winds" : "") + (mvLong ? " · " + mvLong : "") + (st.where ? " · " + st.where : ""),
      boxes: [["Winds", st.wind_kt ? mph(st.wind_kt) + " mph" : "—", col], ["Moving", mv, "var(--fg)"], ["Pressure", st.pressure ? st.pressure + " mb" : "—", "var(--fg)"]],
      sections: [
        ["Where it's going", fc.length ? '<div class="sf">' + fc.map(function (p) { var pc = catOf(p.wind_kt); return '<div class="sf-row"><i style="background:' + (pc ? CATCOL[pc[0]] : "#fff") + '"></i><span class="sf-t">' + esc(p.label || "") + '</span><span class="sf-w">' + (p.wind_kt ? mph(p.wind_kt) + " mph" + (pc ? " · " + pc[0] : "") : "") + '</span><span class="sf-p">' + esc(p.where || "") + "</span></div>"; }).join("") + "</div>" : '<div class="rc-note">No forecast track published for this one yet. It appears once the forecasters issue one.</div>'],
        [winds.length > 1 ? "Wind along its path" + (peak ? " · peak " + mph(peak) + " mph" : "") : null, winds.length > 1 ? '<svg class="rc-spark" id="rc-spark"></svg>' : ""],
        [null, '<div class="rc-note">The solid line is where it has been, the white dashes where it\'s forecast to go' + (st.cone && st.cone.length ? ", and the faint outline is the cone: the center could end up anywhere inside it" : "") + '. Storms only jump forward when forecasters publish a new position (every 3 to 6 hours), so they don\'t glide across the map. From ' + esc(st.source || "GDACS") + ".</div>"],
        [null, headlinesHTML(mentions([name.toLowerCase()], c.lat, c.lng, 6))]
      ],
      actions: [["show its whole path", function () { fitStorm(c, st); }]].concat(st.advisory || c.url ? [["official advisory", function () { window.open(st.advisory || c.url, "_blank"); }]] : []),
      explain: { title: name, text: (st.cls || "Tropical cyclone") + " " + name + (st.where ? " " + st.where : ""), names: [], kind: "storm" },
      after: function () { if (winds.length > 1) spark($("rc-spark"), winds.map(mph), true, 0, " mph", 300, 34); }
    });
  }
  function fitStorm(c, st) {
    var all = [[c.lat, c.lng]].concat(stormPast(st), (st.fcst || []).map(function (p) { return [p.lat, p.lng]; }));
    var la = all.map(function (p) { return p[0]; }), lo = all.map(function (p) { return p[1]; });
    var span = Math.max(d3.max(la) - d3.min(la), (d3.max(lo) - d3.min(lo)) * 0.7, 4);
    if (view === "globe") G.pointOfView({ lat: (d3.max(la) + d3.min(la)) / 2, lng: (d3.max(lo) + d3.min(lo)) / 2, altitude: Math.min(2.2, 0.35 + span / 22) }, 1200);
    else fitBox([[d3.min(lo) - 2, d3.min(la) - 2], [d3.max(lo) + 2, d3.max(la) + 2]], 900);
  }

  /* ============================ satellites (switch groups on in the layers panel) ============================ */
  var SATS = {}, satLoading = {}, satOrbit = null;
  function satPref(k) { try { return (JSON.parse(localStorage.getItem(SAT_KEY) || "[]")).indexOf(k) >= 0; } catch (e) { return false; } }
  function saveSatPrefs() { try { localStorage.setItem(SAT_KEY, JSON.stringify(SATG.filter(function (g) { return on("sat:" + g[0]); }).map(function (g) { return g[0]; }))); } catch (e) { } }
  function satCount(k) { return SATS[k] ? SATS[k].length : ""; }
  function satAlt(h) { return 0.02 + 0.25 * Math.log10(1 + h / 400); }   // heights squashed so far-out ones fit on screen
  function loadSats(k) {
    if (SATS[k] || satLoading[k] || !window.satellite) return;
    satLoading[k] = true;
    api("/api/sats?group=" + k).then(function (d) {
      satLoading[k] = false;
      var list = ((d && d.sats) || []).filter(function (x) { return x[1].slice(2, 7) !== "25544"; }).map(function (x) {
        try { var r = satellite.twoline2satrec(x[1], x[2]); return { name: x[0], rec: r, g: k, id: x[1].slice(2, 7).trim() }; } catch (e) { return null; }
      }).filter(Boolean);
      if (!list.length) { note('<span class="k" style="color:var(--quake)">NO DATA YET</span><span>Archie downloads the satellite lists once a day while online. Try again in a few minutes.</span>'); return; }
      SATS[k] = list; moveSats(k); renderLayers(); refresh();
    }).catch(function () { satLoading[k] = false; });
  }
  function moveSats(k) {
    var d = new Date(), gm = satellite.gstime(d);
    (SATS[k] || []).forEach(function (s) {
      var pv; try { pv = satellite.propagate(s.rec, d); } catch (e) { pv = null; }
      if (!pv || !pv.position) { s.lat = null; return; }
      var ge = satellite.eciToGeodetic(pv.position, gm), v = pv.velocity;
      s.lat = satellite.degreesLat(ge.latitude); s.lng = satellite.degreesLong(ge.longitude); s.h = ge.height; s.alt = satAlt(ge.height); s.v = Math.hypot(v.x, v.y, v.z) * 3600;
    });
  }
  function satSets() {
    var out = [];
    SATG.forEach(function (g) {
      if (!on("sat:" + g[0]) || !SATS[g[0]]) return;
      var set = SATS[g[0]].filter(function (s) { return s.lat != null && !isNaN(s.lat); });
      set.col = g[2]; set.size = g[0] === "starlink" ? 1.6 : 3.2;
      out.push(set);
    });
    return out;
  }
  function satsShown(twoD) { var out = []; SATG.forEach(function (g) { if (on("sat:" + g[0]) && SATS[g[0]] && !(twoD && g[0] === "starlink")) out = out.concat(SATS[g[0]]); }); return out; }
  function satNear(cx, cy) {
    var list = satsShown(false); if (!list.length) return null;
    var cam = G.camera().position, best = null, bd = 64;
    for (var i = 0; i < list.length; i++) {
      var s = list[i]; if (s.lat == null) continue;
      var sc = G.getScreenCoords(s.lat, s.lng, s.alt); if (!sc) continue;
      var dx = sc.x - cx, dy = sc.y - cy, dd = dx * dx + dy * dy; if (dd >= bd) continue;
      var P = G.getCoords(s.lat, s.lng, s.alt), D = { x: P.x - cam.x, y: P.y - cam.y, z: P.z - cam.z };   // hidden behind the Earth?
      var t = -(cam.x * D.x + cam.y * D.y + cam.z * D.z) / (D.x * D.x + D.y * D.y + D.z * D.z);
      if (t > 0 && t < 1) { var qx = cam.x + t * D.x, qy = cam.y + t * D.y, qz = cam.z + t * D.z; if (qx * qx + qy * qy + qz * qz < 100 * 100) continue; }
      bd = dd; best = s;
    }
    return best;
  }
  function orbitKind(h) { return h < 2000 ? ["low Earth orbit", "It laps the planet every hour and a half to two hours."] : h < 30000 ? ["medium Earth orbit", "Navigation satellites like GPS live out here, taking about 12 hours per lap."] : h < 40000 ? ["geostationary orbit", "At this height one lap takes exactly a day, so it hangs over the same spot on the equator, turning with the Earth."] : ["high orbit", ""]; }
  function showSat(s) {
    var g = SATG.find(function (x) { return x[0] === s.g; }), col = g ? g[2] : "#f4f4ef";
    var period = 2 * Math.PI / s.rec.no, incl = s.rec.inclo * 180 / Math.PI, ok = orbitKind(s.h);
    var box = function () { return [["Over", esc(overWhat(s.lat, s.lng)), "#34d399"], ["Altitude", Math.round(s.h * 0.6214).toLocaleString() + " miles", "var(--fg)"], ["Speed", Math.round(s.v * 0.6214).toLocaleString() + " mph", col]]; };
    satOrbit = { id: s.id, col: rgba(col.length === 7 ? col : "#f4f4ef", 0.7), pts: [] };
    var n = 140, span = Math.min(period, 1440) * 60000, t0 = Date.now();
    for (var i = 0; i <= n; i++) { var d = new Date(t0 + span * i / n), pv = satellite.propagate(s.rec, d); if (!pv || !pv.position) continue; var ge = satellite.eciToGeodetic(pv.position, satellite.gstime(d)); satOrbit.pts.push([satellite.degreesLat(ge.latitude), satellite.degreesLong(ge.longitude), satAlt(ge.height)]); }
    rich({
      hash: "sat=" + s.id, color: col, title: s.name, badge: g ? g[1].toUpperCase() : "SATELLITE", badgeColor: col, sub: "Satellite #" + s.id + " · " + ok[0],
      boxes: box(),
      sections: [["Who it belongs to", '<div id="sat-own" class="rc-note">looking it up…</div>'], ["Its orbit", '<div class="rc-note" style="color:var(--fg)">One lap takes ' + (period < 120 ? Math.round(period) + " minutes" : (period / 60).toFixed(1) + " hours") + ", tilted " + Math.round(incl) + "° to the equator. " + ok[1] + ' The line on the globe is its next lap.</div><div class="rc-note">Heights on the globe are squashed so the far-out satellites still fit on screen. Orbit data from CelesTrak, positions worked out on your PC.</div>']],
      explain: { title: s.name, names: [s.name.replace(/\s*\(.*\)$/, "").replace(/^HST$/, "Hubble Space Telescope")], kind: "satellite" },
      after: function () {
        api("/api/satinfo?id=" + s.id).then(function (d) {
          var el = $("sat-own"); if (!el) return;
          var rows = [["Country", d.owner], ["Run by", d.operator], ["Launched", [d.launched, d.site].filter(Boolean).join(" from ")], ["What it is", [d.type, d.status].filter(Boolean).join(", ")]].filter(function (r) { return r[1]; });
          el.outerHTML = rows.length ? '<dl class="facts own">' + rows.map(function (r) { return "<dt>" + r[0] + "</dt><dd>" + esc(r[1]) + "</dd>"; }).join("") + "</dl>" : '<div class="rc-note">Not in the catalog Archie can reach right now.</div>';
        }).catch(function () { var el = $("sat-own"); if (el) el.textContent = "Couldn't reach the satellite catalog (offline?)."; });
      }
    });
    refresh();
  }
  (function () {
    var host = $("globe"), lastMove = 0;
    host.addEventListener("click", function (e) {
      if (view !== "globe" || !G || (e.target.closest && e.target.closest(".gm"))) return;   // a marker (ISS, storm, strait) wins
      var r = host.getBoundingClientRect(), s = satNear(e.clientX - r.left, e.clientY - r.top);
      if (s) { e.stopPropagation(); e.preventDefault(); showSat(s); }
    }, true);
    host.addEventListener("mousemove", function (e) {
      if (view !== "globe" || !G || Date.now() - lastMove < 120) return; lastMove = Date.now();
      if (e.target.closest && e.target.closest(".gm")) { if (host._satTip) { hideTip(); host._satTip = false; host.style.cursor = ""; } return; }
      var r = host.getBoundingClientRect(), s = satNear(e.clientX - r.left, e.clientY - r.top);
      if (s) { tipAt(e, s.name + " · " + Math.round(s.h * 0.6214).toLocaleString() + " mi up"); host.style.cursor = "pointer"; host._satTip = true; }
      else if (host._satTip) { hideTip(); host.style.cursor = ""; host._satTip = false; }
    });
  })();
  // move them: every 3 s, Starlink every 12 s, only while the map is awake
  var satTick = 0;
  setInterval(function () {
    if (document.hidden || sleeping || !window.satellite) return;
    satTick++;
    var any = false;
    SATG.forEach(function (g) { if (on("sat:" + g[0]) && SATS[g[0]] && (g[0] !== "starlink" || satTick % 4 === 0)) { moveSats(g[0]); any = true; } });
    if (!any) return;
    if (view === "globe" && G) G.particlesData(satSets());
    else if (view === "map") drawIss2D();
  }, 3000);

  /* ============================ the space station ============================ */
  var issRec = null, issObj = null, issPath = null, issFollow = false, issFollowUntil = 0;
  var issSVG = '<svg viewBox="-21 -10 42 20" width="36" height="17" aria-hidden="true"><g fill="#d9a441" stroke="#1a1204" stroke-width=".5">' +
    '<rect x="-20" y="-9" width="5.5" height="7.5"/><rect x="-20" y="1.5" width="5.5" height="7.5"/><rect x="-13.5" y="-9" width="5.5" height="7.5"/><rect x="-13.5" y="1.5" width="5.5" height="7.5"/>' +
    '<rect x="8" y="-9" width="5.5" height="7.5"/><rect x="8" y="1.5" width="5.5" height="7.5"/><rect x="14.5" y="-9" width="5.5" height="7.5"/><rect x="14.5" y="1.5" width="5.5" height="7.5"/></g>' +
    '<rect x="-15" y="-.7" width="30" height="1.4" fill="#e8e8e3"/><rect x="-1.2" y="-7" width="2.4" height="14" rx=".8" fill="#e8e8e3"/><rect x="-4" y="-2.2" width="8" height="4.4" rx="1.2" fill="#f4f4ef" stroke="#1a1204" stroke-width=".4"/></svg>';
  function issSetup() {
    if (!S || !S.iss || !window.satellite) return;
    if (issRec && issRec._l1 === S.iss.l1) return;
    try { issRec = satellite.twoline2satrec(S.iss.l1, S.iss.l2); issRec._l1 = S.iss.l1; issPath = null; } catch (e) { issRec = null; }
  }
  function issAt(d) {
    if (!issRec) return null;
    var pv = satellite.propagate(issRec, d); if (!pv || !pv.position) return null;
    var ge = satellite.eciToGeodetic(pv.position, satellite.gstime(d)), v = pv.velocity;
    return { lat: satellite.degreesLat(ge.latitude), lng: satellite.degreesLong(ge.longitude), h: ge.height, v: Math.hypot(v.x, v.y, v.z) * 3600 };
  }
  function buildIssPath() {
    if (!issRec) return;
    var t = Date.now(), past = [], fut = [], p;
    for (var m = -45; m <= 0; m += 1) if ((p = issAt(new Date(t + m * 60000)))) past.push(p);
    for (m = 0; m <= 92; m += 1) if ((p = issAt(new Date(t + m * 60000)))) fut.push(p);
    issPath = { past: past, fut: fut, at: t };
  }
  function overWhat(lat, lng) {
    var f = (countries50 || []).find(function (c) { return d3.geoContains(c, [lng, lat]); });
    if (f) return f.properties.name;
    return Math.abs(lat) > 60 ? "polar waters" : lng > -70 && lng < 20 && lat > -60 ? "the Atlantic" : lng >= 20 && lng < 120 && lat < 30 ? "the Indian Ocean" : "the Pacific";
  }
  function issBoxes() {
    var p = issAt(new Date()); if (!p) return null;
    return [["Over", esc(overWhat(p.lat, p.lng)), "#34d399"], ["Altitude", Math.round(p.h * 0.6214) + " miles", "var(--fg)"], ["Speed", Math.round(p.v * 0.6214).toLocaleString() + " mph", "#d9a441"]];
  }
  function showIss() {
    var b = issBoxes(); if (!b) return;
    var age = S.iss && S.iss.at ? Math.round((NOW - S.iss.at) / 3600) : null;
    rich({
      hash: "iss", color: "#d9a441", title: "ISS", badge: "LIVE", badgeColor: C("--up"), sub: "International Space Station",
      boxes: b,
      sections: [["Who it belongs to", '<dl class="facts own"><dt>Countries</dt><dd>United States, Russia, Europe, Japan, Canada</dd><dt>Run by</dt><dd>NASA, Roscosmos, ESA, JAXA and CSA</dd><dt>Launched</dt><dd>first piece in 1998; people aboard since November 2000</dd></dl>'], ["Its orbit", '<div class="rc-note" style="color:var(--fg)">It circles the Earth about every 92 minutes, roughly 16 laps a day, about 250 miles (400 km) up at nearly 5 miles (7.7 km) a second. The bright line is the last 45 minutes; the dashes are the next lap. Because the Earth turns underneath it, each lap passes a bit further west.</div>'],
        [null, '<div class="rc-note">Position worked out on your PC from NASA/NORAD orbit data (CelesTrak)' + (age != null ? ", updated " + (age < 1 ? "within the hour" : age + " h ago") : "") + ". It stays accurate to a few kilometers for about a day.</div>"]],
      actions: [[issFollow ? "stop following" : "follow it", function (e) { issFollow = !issFollow; issFollowUntil = Date.now() + 600000; e.target.textContent = issFollow ? "stop following" : "follow it"; if (issFollow) { var p = issAt(new Date()); focus(p.lat, p.lng, 1.6); } }]],
      explain: { title: "International Space Station", names: ["International Space Station"], kind: "spacecraft" }
    });
  }
  function drawIss2D() {
    gIss.selectAll("*").remove();
    if (!proj) return;
    satsShown(true).forEach(function (st) {
      if (st.lat == null) return;
      var q = proj([st.lng, st.lat]), g0 = SATG.find(function (x) { return x[0] === st.g; });
      gIss.append("circle").attr("cx", q[0]).attr("cy", q[1]).attr("r", 2.4 / zk).attr("fill", g0[2]).attr("stroke", "#04060a").attr("stroke-width", 0.6 / zk).style("cursor", "pointer")
        .on("click", function () { showSat(st); }).on("mousemove", function (e) { tipAt(e, st.name); }).on("mouseleave", hideTip);
    });
    if (!on("iss") || !issRec) return;
    if (!issPath || Date.now() - issPath.at > 300000) buildIssPath();
    var ll = function (p) { return [p.lng, p.lat]; };
    gIss.append("path").attr("d", gpath({ type: "LineString", coordinates: issPath.past.map(ll) })).attr("fill", "none").attr("stroke", "#d9a441").attr("stroke-opacity", 0.8).attr("stroke-width", 1.3).attr("vector-effect", "non-scaling-stroke").style("pointer-events", "none");
    gIss.append("path").attr("d", gpath({ type: "LineString", coordinates: issPath.fut.map(ll) })).attr("fill", "none").attr("stroke", "#d9a441").attr("stroke-opacity", 0.45).attr("stroke-dasharray", "4 4").attr("stroke-width", 1).attr("vector-effect", "non-scaling-stroke").style("pointer-events", "none");
    var p = issAt(new Date()); if (!p) return;
    var xy = proj([p.lng, p.lat]);
    var g = gIss.append("g").attr("class", "mk").attr("transform", "translate(" + xy[0] + "," + xy[1] + ") scale(" + (1 / zk) + ")").style("cursor", "pointer");
    g.append("g").attr("transform", "translate(-18,-8.5) scale(0.86)").html(issSVG.replace(/<svg[^>]*>|<\/svg>/g, "").replace(/^/, '<g transform="translate(21,10)">') + "</g>");
    g.append("text").attr("x", 17).attr("y", 3).attr("font-size", 9).attr("fill", "#d9a441").text("ISS");
    g.on("click", showIss).on("mousemove", function (e) { tipAt(e, "International Space Station · over " + overWhat(p.lat, p.lng)); }).on("mouseleave", hideTip);
  }
  // move the station every 2 seconds (only while the map is awake)
  setInterval(function () {
    if (!issRec || !on("iss") || document.hidden) return;
    if (issFollow && Date.now() > issFollowUntil) issFollow = false;
    if (sleeping && !issFollow) return;
    var p = issAt(new Date()); if (!p) return;
    if (view === "globe" && G && issObj) {
      issObj.lat = p.lat; issObj.lng = p.lng; issObj.alt = p.h / 6371;
      if (issPath && Date.now() - issPath.at > 300000) refresh(); else G.htmlElementsData(G.htmlElementsData());
      if (issFollow) { wake(); G.pointOfView({ lat: p.lat, lng: p.lng }, 1800); }
    } else if (view === "map") { drawIss2D(); if (issFollow) zoomToPoint(p.lng, p.lat, Math.max(zk, 2)); }
    if (!card.hidden && location.hash === "#iss") { var b = issBoxes(); card.querySelectorAll(".rc-box .rc-v").forEach(function (el, i) { if (b[i]) el.innerHTML = b[i][1]; }); }
  }, 2000);
  window.addEventListener("pointerdown", function (e) { if (issFollow && e.target.closest && e.target.closest("#globe, #map")) issFollow = false; }, true);

  /* ============================ the globe ============================ */
  var stage = $("stage");
  function starfield() {
    var c = document.createElement("canvas"); c.width = 2048; c.height = 1024; var x = c.getContext("2d"), r = d3.randomLcg(7);
    x.fillStyle = "#000"; x.fillRect(0, 0, 2048, 1024);
    for (var i = 0; i < 1400; i++) { var a = r(); x.fillStyle = "rgba(255,255,255," + (0.15 + a * a * 0.8) + ")"; var s = a > 0.97 ? 1.6 : 0.8; x.fillRect(r() * 2048, r() * 1024, s, s); }
    return c.toDataURL("image/png");
  }
  var G, hoverC = null, zoomedIn = false, tilesOn = false;
  function makeGlobe() {
    G = Globe({ animateIn: true })($("globe"))
      .globeImageUrl("/web/data/topo.jpg").bumpImageUrl("/web/data/bump.png").backgroundImageUrl(starfield())
      .showAtmosphere(true).atmosphereColor("#7fb2ff").atmosphereAltitude(0.16)
      .polygonsData(countries)
      .polygonAltitude(function (d) { return d.properties.name === selCountry ? 0.007 : d === hoverC ? 0.006 : 0.004; })
      .polygonCapColor(function (d) {
        if (d.properties.name === selCountry) return "rgba(198,244,50,0.22)";
        var l = on("zones") && (shade[ALIAS[d.properties.name] || d.properties.name] || shade[d.properties.name]);
        if (l) return rgba(C(LVL[l].v), d === hoverC ? 0.5 : 0.3);
        return d === hoverC ? "rgba(198,244,50,0.12)" : "rgba(0,0,0,0)";
      })
      .polygonSideColor(function () { return "rgba(0,0,0,0)"; })
      .polygonStrokeColor(function (d) { return d.properties.name === selCountry ? C("--lime") : tilesOn ? "rgba(198,244,50,0.15)" : "rgba(198,244,50,0.3)"; })
      .polygonLabel(function (d) { var n = d.properties.name, l = shade[ALIAS[n] || n] || shade[n], lv = (S && S.shade_live) || {}, c = lv[ALIAS[n] || n] || lv[n]; return "<b>" + esc(n) + "</b>" + (l ? '<br><span style="color:' + C(LVL[l].v) + '">' + LVL[l].name + "</span>" + '<span style="color:#8f918a"> · ' + (c ? c + " military reports this week" : "from conflict datasets") + "</span>" : "") + '<br><span style="color:#8f918a">click for facts & articles</span>'; })
      .onPolygonHover(function (d) { hoverC = d; G.polygonAltitude(G.polygonAltitude()); })
      .onPolygonClick(function (d) { showCountry(d.properties.name); })
      .polygonsTransitionDuration(200)
      .pointLat("lat").pointLng("lng").pointAltitude("alt").pointRadius("rad").pointColor("color").pointsMerge(false)
      .onPointClick(function (d) { d.click && d.click(); })
      .pointLabel(function (d) { return d.label || ""; })
      .ringLat("lat").ringLng("lng").ringColor(function (d) { return function (t) { return rgba(d.hex, (1 - t) * (d.a || 1)); }; })
      .ringMaxRadius("max").ringPropagationSpeed("speed").ringRepeatPeriod("period")
      .pathPoints("pts").pathPointLat(function (p) { return p[0]; }).pathPointLng(function (p) { return p[1]; }).pathPointAlt(function (p) { return p[2] || 0.006; })
      .pathColor("color").pathStroke("stroke").pathDashLength("dash").pathDashGap("gap").pathDashAnimateTime("anim").pathTransitionDuration(0)
      .onPathClick(function (d) { d.click && d.click(); })
      .pathLabel(function (d) { return d.pipe ? pipeTip(d.pipe) : ""; })
      .htmlLat("lat").htmlLng("lng").htmlAltitude("alt").htmlElement(function (d) { return d.el; }).htmlTransitionDuration(0)
      .particleLat("lat").particleLng("lng").particleAltitude("alt").particlesColor(function (set) { return set.col; }).particlesSize(function (set) { return set.size; }).particlesSizeAttenuation(false)
      .onZoom(function (pov) {
        var z = pov.altitude < 1.05; if (z !== zoomedIn) { zoomedIn = z; refresh(); }
        var t = S && S.tiles && pov.altitude < 0.55;
        if (t !== tilesOn) { tilesOn = t; $("attrib").hidden = !t; G.globeTileEngineUrl(t ? function (x, y, l) { return "/tile/street/" + l + "/" + x + "/" + y + ".png"; } : null); G.polygonStrokeColor(G.polygonStrokeColor()); }
      });
    G.controls().autoRotate = false;
    try { G.renderer().setPixelRatio(1); } catch (e) { }
    G.pointOfView({ lat: 30, lng: 25, altitude: 2.1 });
    new ResizeObserver(sizeGlobe).observe(stage);
    sizeGlobe();
  }
  // eco: 1x pixels, stop drawing when hidden, pause after 2 idle minutes
  var idleT = null, sleeping = false;
  function wake() { clearTimeout(idleT); if (sleeping && view === "globe" && !document.hidden) { G.resumeAnimation(); sleeping = false; $("eco").textContent = "eco ●"; } idleT = setTimeout(nap, 120000); }
  function nap() { if (view !== "globe") return; G.pauseAnimation(); sleeping = true; $("eco").textContent = "eco · paused"; }
  ["pointerdown", "pointermove", "wheel", "keydown"].forEach(function (ev) { window.addEventListener(ev, wake, { passive: true }); });
  document.addEventListener("visibilitychange", function () { if (document.hidden) { G.pauseAnimation(); sleeping = true; } else wake(); });

  function sizeGlobe() { G.width(stage.clientWidth).height(stage.clientHeight); if (view === "map") drawMap(); }
  function focus(lat, lng, alt) {
    wake();
    if (view === "globe") G.pointOfView({ lat: lat, lng: lng, altitude: alt || 1.5 }, 1200);
    else zoomToPoint(lng, lat, alt && alt < 1 ? 6 : 3);
  }
  function gm(cls, html, color) { var el = document.createElement("button"); el.className = "gm " + cls; el.innerHTML = html; if (color) el.style.color = color; return el; }
  var triSVG = '<svg viewBox="0 0 20 18"><path d="M10 1.5 L18.8 16.8 H1.2 Z" fill="currentColor" stroke="#0a0a0a" stroke-width="1"/><path d="M9.1 6h1.8l-.3 6h-1.2z M10 13.3a1.1 1.1 0 1 0 .01 0" fill="#0a0a0a"/></svg>';
  var liveRings = [];

  function frontFeatures() {
    var fs = (S && S.front && S.front.features) || [];
    if (!fs._fixed) {        // d3 wants clockwise outer rings; GeoJSON files often wind the other way
      fs.forEach(function (f) {
        if (d3.geoArea(f) > 2 * Math.PI) {
          var g = f.geometry;
          g.coordinates = g.type === "Polygon" ? g.coordinates.map(function (r) { return r.slice().reverse(); }) : g.coordinates.map(function (p) { return p.map(function (r) { return r.slice().reverse(); }); });
        }
      });
      fs._fixed = true;
    }
    return fs;
  }

  function refresh() {
    if (!G || !S) return;
    var pts = [], rings = [], html = [], paths = [];
    var detail = zoomedIn || !!region;
    if (on("news") && !detail) STORIES.forEach(function (s) {
      if (s.lat == null || !inWindow(s.last, 24) || s.n < 2) return;
      var hex = C(TOPIC[s.topic]);
      pts.push({ lat: s.lat, lng: s.lng, alt: 0.016 + s.n / 300, rad: 0.18 + s.n / 40, color: hex, click: function () { showStory(s); } });
      if (isNewItem(s)) { var nd = gm("newdot", ""); nd.title = "new since you last looked · " + s.t; nd.onclick = function () { showStory(s); }; html.push({ lat: s.lat, lng: s.lng, alt: 0.02 + s.n / 300, el: nd }); }
      if (s.n >= 5) rings.push({ lat: s.lat, lng: s.lng, hex: hex, a: 0.6, max: 2 + s.n / 3, speed: 1.3, period: 1800 });
    });
    if (on("quakes")) quakes.forEach(function (q) {
      if (!inWindow(q.time, 24)) return;
      pts.push({ lat: q.lat, lng: q.lng, alt: 0.014 + (q.m - 2.5) * 0.006, rad: 0.14 + (q.m - 2.5) * 0.16, color: C("--quake"), click: function () { showQuake(q); }, label: "<b>M" + q.m.toFixed(1) + "</b> " + esc(q.place) + '<br><span style="color:#8f918a">' + ago(minsAgo(q.time)) + " · click for details</span>" });
      if (q.m >= 4.5) rings.push({ lat: q.lat, lng: q.lng, hex: C("--quake"), max: Math.pow(q.m, 1.6) / 2.2, speed: 1.6 + q.m / 4, period: 2600 - q.m * 200 });
    });
    if (on("cyclones")) cyclones.forEach(function (c) {
      var st = stormOf(c), ct = catOf(st && st.wind_kt), col = stormCol(st), click = function () { showStorm(c); };
      var el = gm("cyc", stormSVG(col, 20) + "<span>" + esc(stormName(c, st)) + (ct ? " · " + ct[0] : "") + "</span>"); el.style.color = col; el.title = stormName(c, st) + " · click for its path"; el.onclick = click;
      html.push({ lat: c.lat, lng: c.lng, alt: 0.02, el: el });
      if (!st) return;
      var past = stormPast(st), fc = (st.fcst || []);
      if (past.length > 1) paths.push({ pts: past.concat([[c.lat, c.lng]]).map(function (p) { return [p[0], p[1], 0.008]; }), color: rgba(col, 0.95), stroke: 1.1, dash: 1, gap: 0, anim: 0, click: click });
      if (fc.length) paths.push({ pts: [[c.lat, c.lng, 0.008]].concat(fc.map(function (p) { return [p.lat, p.lng, 0.008]; })), color: "rgba(255,255,255,0.85)", stroke: 0.8, dash: 0.018, gap: 0.012, anim: 0, click: click });
      if (st.cone && st.cone.length > 3) paths.push({ pts: st.cone.map(function (p) { return [p[0], p[1], 0.006]; }), color: rgba(col, 0.55), stroke: 0.4, dash: 0.008, gap: 0.008, anim: 0, click: click });
      fc.forEach(function (p) { pts.push({ lat: p.lat, lng: p.lng, alt: 0.01, rad: 0.16, color: "#ffffff", click: click, label: "<b>" + esc(stormName(c, st)) + "</b> · forecast<br>" + esc(p.label || "") + (p.wind_kt ? " · " + mph(p.wind_kt) + " mph" : "") + (p.where ? '<br><span style="color:#8f918a">' + esc(p.where) + "</span>" : "") }); });
    });
    if (on("iss") && issRec) {
      if (!issObj) { issObj = { lat: 0, lng: 0, alt: 0.066, el: gm("iss", issSVG + '<span>ISS</span>') }; issObj.el.title = "International Space Station · live"; issObj.el.onclick = showIss; }
      var ip = issAt(new Date()); if (ip) { issObj.lat = ip.lat; issObj.lng = ip.lng; issObj.alt = ip.h / 6371; }
      html.push(issObj);
      if (!issPath || Date.now() - issPath.at > 300000) buildIssPath();
      if (issPath) {
        paths.push({ pts: issPath.past.map(function (p) { return [p.lat, p.lng, p.h / 6371]; }), color: ["rgba(217,164,65,0)", "rgba(217,164,65,0.85)"], stroke: 0.7, dash: 1, gap: 0, anim: 0 });
        paths.push({ pts: issPath.fut.map(function (p) { return [p.lat, p.lng, p.h / 6371]; }), color: "rgba(217,164,65,0.45)", stroke: 0.5, dash: 0.01, gap: 0.01, anim: 0 });
      }
    }
    if (on("floods")) floods.forEach(function (f) { pts.push({ lat: f.lat, lng: f.lng, alt: 0.012, rad: 0.5, color: rgba(C("--flood"), 0.7), click: function () { showHazard(f, "FLOOD", C("--flood")); } }); rings.push({ lat: f.lat, lng: f.lng, hex: C("--flood"), a: 0.6, max: 3, speed: 0.8, period: 2400 }); });
    if (on("volcanoes")) volcanoes.forEach(function (v) { var el = gm("volc", "▲"); el.title = v.title; el.onclick = function () { showHazard(v, "VOLCANO", C("--volcano")); }; html.push({ lat: v.lat, lng: v.lng, alt: 0.012, el: el }); });
    if (on("fires")) {
      wildfires.forEach(function (f) { pts.push({ lat: f.lat, lng: f.lng, alt: 0.012, rad: 0.35, color: C("--fire"), click: function () { showHazard(f, "WILDFIRE", C("--fire")); } }); });
      fires.forEach(function (f) { pts.push({ lat: f.lat, lng: f.lng, alt: 0.003, rad: 0.08, color: C("--fire") }); });
    }
    ["oil", "gas"].forEach(function (k) {
      if (!on(k)) return;
      pipes.filter(function (p) { return p.kind === k; }).forEach(function (p) {
        var col = p.status === "disrupted" ? PST.disrupted : C("--" + k), click = function () { showPipe(p); }, dead = DEAD[p.status];
        paths.push({ pts: p.pts, color: rgba(col, dead ? 0.35 : 0.55), stroke: dead ? 0.6 : 0.9, dash: dead ? 0.015 : 1, gap: dead ? 0.012 : 0, anim: 0, click: click, pipe: p });
        if (!dead) paths.push({ pts: p.pts, color: [rgba(col, 0), col], stroke: 1.2, dash: 0.06, gap: p.status === "flowing" ? 0.12 : 0.3, anim: p.status === "flowing" ? 4000 : 9000, click: click, pipe: p });
      });
    });
    if (on("chokes")) chokes.forEach(function (c) {
      var sh = shipsFor(c), bad = sh && /disrupt|reduc/.test(sh.status);
      var el = gm("choke" + (c.major ? "" : " minor") + (bad ? " bad" : ""), "<i></i><span>" + (c.major || detail ? c.name : "") + "</span>"); el.title = c.name + (sh ? " · " + sh.status : ""); el.onclick = function () { showChoke(c); };
      html.push({ lat: c.lat, lng: c.lng, alt: 0.01, el: el });
    });
    if (on("front")) frontFeatures().forEach(function (f) {
      var polys = f.geometry.type === "Polygon" ? [f.geometry.coordinates] : f.geometry.coordinates;
      polys.forEach(function (poly) { paths.push({ pts: poly[0].map(function (p) { return [p[1], p[0], 0.007]; }), color: rgba(C("--war"), 0.9), stroke: 0.9, dash: 1, gap: 0, anim: 0 }); });
    });
    if (on("hot") && !detail) hotspots.forEach(function (h) { var el = gm("hot", triSVG, C(LVL[h.lvl].v)); el.title = h.name; el.onclick = function () { showHot(h); }; html.push({ lat: h.lat, lng: h.lng, alt: 0.012, el: el }); });
    if (on("events") && detail) EVENTS.forEach(function (e) {
      if (e.lat == null || !inWindow(e.last, 24) || (region && e.region !== region)) return;
      var el = gm("ev" + (e.unconfirmed ? " unc" : "") + (isNewItem(e) ? " isnew" : ""), icon(e.type, 9)); el.title = ago(minsAgo(e.last)) + " · " + e.t; el.onclick = function () { showEvent(e); };
      html.push({ lat: e.lat, lng: e.lng, alt: 0.012, el: el });
    });
    if (on("markets")) exchanges.forEach(function (x) {
      var el = gm("fc", '<i></i><span>' + (x.tier === "MAJOR" || detail ? x.name + (x.chg != null ? (x.chg >= 0 ? " ▲" : " ▼") + Math.abs(x.chg).toFixed(1) + "%" : "") : "") + "</span>"); el.title = x.full; el.onclick = function () { showEx(x); };
      if (!isOpen(x)) el.classList.add("shut");
      html.push({ lat: x.lat, lng: x.lng, alt: 0.012, el: el });
    });
    if (on("banks")) banks.forEach(function (b) { var el = gm("cbk", '<i></i><span>' + (detail ? b.short : "") + "</span>"); el.title = b.name; el.onclick = function () { showBank(b); }; html.push({ lat: b.lat - 0.35, lng: b.lng + 0.45, alt: 0.012, el: el }); });
    if (on("mines")) MINES.forEach(function (m) { var el = gm("mine" + (m[6] === "artisanal" ? " art" : ""), mineSVG(mineCol(m), m[6] === "artisanal") + "<span>" + (detail ? esc(m[0]) : "") + "</span>"); el.title = m[0] + " · " + m[4] + (m[6] === "artisanal" ? " (artisanal)" : ""); el.onclick = function () { showMine(m); }; html.push({ lat: m[1], lng: m[2], alt: 0.012, el: el }); });
    if (on("stations")) STATIONS.forEach(function (st) { var el = gm("stn" + (st[6] === "summer" ? " sum" : ""), stnSVG + "<span>" + (detail ? esc(st[0]) : "") + "</span>"); el.title = st[0] + " · " + st[3]; el.onclick = function () { showStation(st); }; html.push({ lat: st[1], lng: st[2], alt: 0.012, el: el }); });
    highlight.forEach(function (h) { rings.push({ lat: h.lat, lng: h.lng, hex: C("--lime"), max: 6, speed: 2, period: 900 }); });
    G.particlesData(satSets());
    if (satOrbit && !card.hidden) paths.push({ pts: satOrbit.pts, color: satOrbit.col, stroke: 0.6, dash: 1, gap: 0, anim: 0 });
    G.pointsData(pts).ringsData(rings.concat(liveRings)).htmlElementsData(html).pathsData(paths);
    G.polygonCapColor(G.polygonCapColor());
    renderStats();
    if (view === "map") drawMap();
  }

  function renderStats() {
    var wars = Object.keys(shade).filter(function (k) { return shade[k] === "war"; }).length;
    var badShips = chokes.filter(function (c) { var sh = shipsFor(c); return sh && /disrupt|reduc/.test(sh.status); }).length;
    var s = [[C("--war"), wars, "wars"], [C("--armed"), Object.keys(shade).length - wars, "other conflicts"], ["#e5484d", EVENTS.filter(function (e) { return inWindow(e.last, 1); }).length, "reports last hour"],
      [C("--quake"), quakes.filter(function (q) { return q.m >= 4.5 && inWindow(q.time, 24); }).length, "quakes M4.5+"], [C("--cyclone"), cyclones.length, "cyclones"], [C("--choke"), badShips, "shipping alerts"]];
    $("stats").innerHTML = s.map(function (x) { return '<span class="stat"><b style="color:' + x[0] + '">' + x[1] + "</b>" + x[2] + "</span>"; }).join("");
  }

  /* ---------- weather radar on the globe: a see-through sphere painted from RainViewer tiles ---------- */
  var radarFrames = [], radarMesh = null, radarFrame = null;
  function loadRadar() {
    api("/api/radar").then(function (d) { radarFrames = (d && d.frames) || []; renderLayers(); paintRadar(); }).catch(function () { });
  }
  function frameFor() {
    if (!radarFrames.length) return null;
    var t = refT(), best = null;
    radarFrames.forEach(function (f) { if (f.time <= t + 300 && (!best || f.time > best.time)) best = f; });
    if (!best || t - best.time > 1800) return null;         // radar only goes back two hours
    return best;
  }
  function paintRadar() {
    var fr = on("radar") ? frameFor() : null;
    if (view === "map") drawMap();
    if (!G) return;
    if (!fr) { if (radarMesh) radarMesh.visible = false; return; }
    if (radarFrame === fr.time && radarMesh) { radarMesh.visible = true; return; }
    radarFrame = fr.time;
    var z = 2, n = 4, T = 256, merc = document.createElement("canvas"); merc.width = merc.height = n * T;
    var mx = merc.getContext("2d"), left = n * n;
    for (var x = 0; x < n; x++) for (var y = 0; y < n; y++) (function (x, y) {
      var im = new Image(); im.onload = im.onerror = function () { if (im.naturalWidth) mx.drawImage(im, x * T, y * T); if (--left === 0) finish(); };
      im.src = "/tile/radar/" + z + "/" + x + "/" + y + "/" + fr.time + ".png";
    })(x, y);
    function finish() {
      var W = 2048, H = 1024, eq = document.createElement("canvas"); eq.width = W; eq.height = H;
      var ex = eq.getContext("2d"), size = n * T;
      for (var row = 0; row < H; row++) {
        var lat = 90 - (row + 0.5) / H * 180; if (Math.abs(lat) > 85) continue;
        var yy = (1 - Math.log(Math.tan(Math.PI / 4 + lat * Math.PI / 360)) / Math.PI) / 2 * size;
        ex.drawImage(merc, 0, Math.floor(yy), size, 1, 0, row, W, 1);
      }
      var gmat = G.globeMaterial(), globeMesh = null;
      G.scene().traverse(function (o) { if (o.material === gmat) globeMesh = o; });
      if (!globeMesh || !gmat.map) return;
      var Tex = gmat.map.constructor;
      var tex = new Tex(eq); tex.needsUpdate = true; if (gmat.map.colorSpace) tex.colorSpace = gmat.map.colorSpace;
      if (!radarMesh) {
        var geo = new globeMesh.geometry.constructor(G.getGlobeRadius() * 1.004, 128, 64);
        var mat = new gmat.constructor({ map: tex, transparent: true, opacity: 0.8, depthWrite: false });
        radarMesh = new globeMesh.constructor(geo, mat);
        radarMesh.rotation.copy(globeMesh.rotation);
        radarMesh.raycast = function () { };      // clicks go through the radar to what's under it
        globeMesh.parent.add(radarMesh);
      } else { radarMesh.material.map = tex; radarMesh.material.needsUpdate = true; }
      radarMesh.visible = true;
    }
  }

  /* ============================ 2D map (Mercator, zoomable) ============================ */
  var view = "globe", svg = d3.select("#map"), proj = d3.geoMercator(), gpath = d3.geoPath(proj), zk = 1, zoomT = d3.zoomIdentity;
  var defs = svg.append("defs");
  [["oil", C("--oil")], ["gas", C("--gas")], ["bad", "#ff5f57"]].forEach(function (a) {
    defs.append("marker").attr("id", "arr-" + a[0]).attr("viewBox", "0 0 10 10").attr("refX", 5).attr("refY", 5).attr("markerWidth", 7).attr("markerHeight", 7).attr("markerUnits", "userSpaceOnUse").attr("orient", "auto")
      .append("path").attr("d", "M1,1 L9,5 L1,9 z").attr("fill", a[1]);
  });
  var root = svg.append("g"), gLand = root.append("g"), gTiles = root.append("g"), gCtry = root.append("g"), gRadar = root.append("g"), gOver = root.append("g"), gMk = root.append("g"), gIss = root.append("g");
  var tileT = null;
  var zoom = d3.zoom().scaleExtent([1, 60]).on("zoom", function (e) {
    zoomT = e.transform; root.attr("transform", zoomT); defs.selectAll("marker").attr("markerWidth", 7 / zoomT.k).attr("markerHeight", 7 / zoomT.k);
    var was = zk >= 2.6; zk = zoomT.k;
    gMk.selectAll(".mk").attr("transform", function (d) { return "translate(" + d.x + "," + d.y + ") scale(" + (1 / zk) + ")"; });
    if ((zk >= 2.6) !== was) drawMarkers();
    clearTimeout(tileT); tileT = setTimeout(drawTiles, 150);
  });
  svg.call(zoom).on("dblclick.zoom", null);
  var WORLD_BOX = { type: "MultiPoint", coordinates: [[-180, -58], [180, 78]] };
  function drawMap() {
    if (!countries50) return;
    var W = stage.clientWidth, H = stage.clientHeight;
    svg.attr("viewBox", "0 0 " + W + " " + H);
    proj.fitSize([W, H], WORLD_BOX);
    zoom.translateExtent([[-W * 0.2, -H * 0.2], [W * 1.2, H * 1.2]]);
    gLand.selectAll("*").remove(); gCtry.selectAll("*").remove(); gOver.selectAll("*").remove();
    gLand.append("path").attr("d", gpath(d3.geoGraticule10())).attr("class", "grat");
    gLand.append("path").attr("d", gpath(land50)).attr("fill", "#10150e");
    gCtry.selectAll("path").data(countries50).join("path").attr("class", function (d) { return "ctry" + (d.properties.name === selCountry ? " sel" : ""); })
      .attr("d", gpath)
      .attr("fill", function (d) { var n = d.properties.name, l = on("zones") && (shade[ALIAS[n] || n] || shade[n]); return l ? rgba(C(LVL[l].v), region || zk > 4 ? 0.1 : 0.26) : "rgba(0,0,0,0)"; })
      .on("click", function (e, d) { showCountry(d.properties.name); })
      .on("mousemove", function (e, d) { var n = d.properties.name, l = shade[ALIAS[n] || n] || shade[n]; tipAt(e, n + (l ? " · " + LVL[l].name : "")); })
      .on("mouseleave", hideTip);
    if (on("front")) frontFeatures().forEach(function (f) {
      gOver.append("path").attr("d", gpath(f)).attr("fill", rgba(C("--war"), 0.26)).attr("stroke", rgba(C("--war"), 0.8)).attr("stroke-width", 1).attr("vector-effect", "non-scaling-stroke").style("pointer-events", "none");
    });
    ["oil", "gas"].forEach(function (k) {
      if (!on(k)) return;
      pipes.filter(function (p) { return p.kind === k; }).forEach(function (p) {
        var d = gpath({ type: "LineString", coordinates: p.pts.map(function (q) { return [q[1], q[0]]; }) });
        var col = p.status === "disrupted" ? PST.disrupted : C("--" + k), dead = DEAD[p.status];
        gOver.append("path").attr("class", "pipe").attr("d", d).attr("stroke", col).attr("stroke-opacity", dead ? 0.45 : 0.8).attr("stroke-width", 1.6).attr("stroke-dasharray", dead ? "2 3" : null)
          .attr("marker-mid", dead ? null : "url(#arr-" + (p.status === "disrupted" ? "bad" : k) + ")").attr("marker-end", dead ? null : "url(#arr-" + (p.status === "disrupted" ? "bad" : k) + ")");
        gOver.append("path").attr("class", "pipe hit").attr("d", d).attr("stroke", "transparent").attr("stroke-width", 10)
          .on("click", function () { showPipe(p); }).on("mousemove", function (e) { tipAt(e, pipeTip(p), true); }).on("mouseleave", hideTip);
        if (!dead) gOver.append("path").attr("class", "pipe flow" + (p.status === "flowing" ? "" : " slow")).attr("d", d).attr("stroke", col).attr("stroke-width", 2.2);
      });
    });
    if (on("cyclones")) cyclones.forEach(function (c) {
      var st = stormOf(c); if (!st) return;
      var col = stormCol(st), ll = function (p) { return [p[1], p[0]]; }, click = function () { showStorm(c); };
      var coneGeo = st.cone && st.cone.length > 3 ? { type: "Polygon", coordinates: [st.cone.map(ll)] } : null;
      if (coneGeo && d3.geoArea(coneGeo) > 2 * Math.PI) coneGeo.coordinates[0].reverse();   // wound the wrong way = "everything except the cone"
      if (coneGeo) gOver.append("path").attr("d", gpath(coneGeo)).attr("fill", rgba(col, 0.1)).attr("stroke", rgba(col, 0.6)).attr("stroke-dasharray", "3 3").attr("stroke-width", 1).attr("vector-effect", "non-scaling-stroke").on("click", click);
      var past = stormPast(st);
      if (past.length > 1) gOver.append("path").attr("d", gpath({ type: "LineString", coordinates: past.concat([[c.lat, c.lng]]).map(ll) })).attr("fill", "none").attr("stroke", col).attr("stroke-width", 1.8).attr("vector-effect", "non-scaling-stroke").on("click", click);
      if ((st.fcst || []).length) {
        gOver.append("path").attr("d", gpath({ type: "LineString", coordinates: [[c.lng, c.lat]].concat(st.fcst.map(function (p) { return [p.lng, p.lat]; })) })).attr("fill", "none").attr("stroke", "#fff").attr("stroke-opacity", 0.85).attr("stroke-dasharray", "5 4").attr("stroke-width", 1.4).attr("vector-effect", "non-scaling-stroke");
      }
    });
    drawTiles();
    drawMarkers();
    drawIss2D();
  }
  // street-level tiles (zoomed in) and radar tiles, placed in map coordinates
  function tileBox(z, x, y) {
    var n = Math.pow(2, z), lng0 = x / n * 360 - 180, lng1 = (x + 1) / n * 360 - 180;
    var lat0 = Math.atan(Math.sinh(Math.PI * (1 - 2 * y / n))) * 180 / Math.PI, lat1 = Math.atan(Math.sinh(Math.PI * (1 - 2 * (y + 1) / n))) * 180 / Math.PI;
    var a = proj([lng0, lat0]), b = proj([lng1, lat1]);
    return [a[0], a[1], b[0] - a[0], b[1] - a[1]];
  }
  function visibleTiles(z) {
    var W = stage.clientWidth, H = stage.clientHeight, inv = zoomT.invert([0, 0]), inv2 = zoomT.invert([W, H]);
    var p0 = proj.invert(inv), p1 = proj.invert(inv2), n = Math.pow(2, z);
    function tx(lng) { return Math.floor((lng + 180) / 360 * n); }
    function ty(lat) { lat = Math.max(-85, Math.min(85, lat)); var r = lat * Math.PI / 180; return Math.floor((1 - Math.log(Math.tan(r) + 1 / Math.cos(r)) / Math.PI) / 2 * n); }
    var out = [];
    for (var x = Math.max(0, tx(p0[0])); x <= Math.min(n - 1, tx(p1[0])); x++) for (var y = Math.max(0, ty(p0[1])); y <= Math.min(n - 1, ty(p1[1])); y++) out.push([z, x, y]);
    return out.length > 120 ? out.slice(0, 120) : out;
  }
  function drawTiles() {
    if (view !== "map" || !countries50) return;
    var worldPx = (proj([180, 0])[0] - proj([-180, 0])[0]) * zk;
    var zBase = Math.max(0, Math.min(17, Math.round(Math.log2(worldPx / 256))));
    var base = S && S.tiles && zk >= 3 ? visibleTiles(zBase) : [];
    var sel = gTiles.selectAll("image").data(base, function (d) { return d.join("/"); });
    sel.exit().remove();
    sel.enter().append("image").attr("preserveAspectRatio", "none").attr("href", function (d) { return "/tile/street/" + d[0] + "/" + d[1] + "/" + d[2] + ".png"; })
      .each(function (d) { var b = tileBox(d[0], d[1], d[2]); d3.select(this).attr("x", b[0]).attr("y", b[1]).attr("width", b[2] + 0.02).attr("height", b[3] + 0.02); });
    gLand.style("display", base.length ? "none" : null);
    $("attrib").hidden = !base.length && !tilesOn;
    var fr = on("radar") ? frameFor() : null, zr = Math.max(1, Math.min(7, zBase));
    var rad = fr ? visibleTiles(zr) : [];
    var rs = gRadar.selectAll("image").data(rad, function (d) { return d.join("/") + "/" + fr.time; });
    rs.exit().remove();
    rs.enter().append("image").attr("preserveAspectRatio", "none").attr("opacity", 0.75).attr("href", function (d) { return "/tile/radar/" + d[0] + "/" + d[1] + "/" + d[2] + "/" + fr.time + ".png"; })
      .each(function (d) { var b = tileBox(d[0], d[1], d[2]); d3.select(this).attr("x", b[0]).attr("y", b[1]).attr("width", b[2]).attr("height", b[3]); });
  }
  function mk(list) { return list.map(function (d) { var xy = proj([d.lng, d.lat]); d.x = xy[0]; d.y = xy[1]; return d; }); }
  function drawMarkers() {
    if (!S) return;
    var detail = zk >= 2.6 || !!region, M = [];
    if (on("news") && !detail) STORIES.forEach(function (s) { if (s.lat != null && s.n >= 2 && inWindow(s.last, 24)) M.push({ lat: s.lat, lng: s.lng, k: "news", s: s, r: 2 + Math.min(s.n, 20) / 3, col: C(TOPIC[s.topic]) }); });
    if (on("quakes")) quakes.forEach(function (q) { if (inWindow(q.time, 24)) M.push({ lat: q.lat, lng: q.lng, k: "quake", q: q, r: 1.5 + (q.m - 2.5) * 1.4, col: C("--quake") }); });
    if (on("fires")) { fires.forEach(function (f) { M.push({ lat: f.lat, lng: f.lng, k: "fire", r: 1.3, col: C("--fire") }); }); wildfires.forEach(function (f) { M.push({ lat: f.lat, lng: f.lng, k: "hz", h: f, lab: "WILDFIRE", col: C("--fire"), r: 5 }); }); }
    if (on("floods")) floods.forEach(function (f) { M.push({ lat: f.lat, lng: f.lng, k: "hz", h: f, lab: "FLOOD", col: C("--flood"), r: 7 }); });
    if (on("volcanoes")) volcanoes.forEach(function (v) { M.push({ lat: v.lat, lng: v.lng, k: "volc", v: v }); });
    if (on("cyclones")) cyclones.forEach(function (c) { M.push({ lat: c.lat, lng: c.lng, k: "cyc", c: c }); var st = stormOf(c); if (st) (st.fcst || []).forEach(function (p) { M.push({ lat: p.lat, lng: p.lng, k: "fpt", c: c, p: p }); }); });
    if (on("chokes")) chokes.forEach(function (c) { M.push({ lat: c.lat, lng: c.lng, k: "choke", c: c }); });
    if (on("hot") && !detail) hotspots.forEach(function (h) { M.push({ lat: h.lat, lng: h.lng, k: "hot", h: h }); });
    if (detail) {
      var R = regionOf(region);
      if (!(S.tiles && zk >= 3)) (R ? [R] : REGIONS).forEach(function (Rg) { Rg.cities.forEach(function (c) { M.push({ lat: c[2], lng: c[3], k: "city", c: c }); }); });
      if (on("events")) EVENTS.forEach(function (e) { if (e.lat != null && inWindow(e.last, 24) && (!region || e.region === region)) M.push({ lat: e.lat, lng: e.lng, k: "ev", e: e }); });
    }
    if (on("markets")) exchanges.forEach(function (x) { M.push({ lat: x.lat, lng: x.lng, k: "ex", xc: x }); });
    if (on("banks")) banks.forEach(function (b) { M.push({ lat: b.lat - 0.35, lng: b.lng + 0.45, k: "cb", b: b }); });
    if (on("mines")) MINES.forEach(function (m) { M.push({ lat: m[1], lng: m[2], k: "mine", m: m }); });
    if (on("stations")) STATIONS.forEach(function (st) { if (st[1] > -85.5) M.push({ lat: st[1], lng: st[2], k: "stn", st: st }); });
    liveRings.concat(highlight.map(function (h) { return { lat: h.lat, lng: h.lng, hex: C("--lime") }; })).forEach(function (r) { M.push({ lat: r.lat, lng: r.lng, k: "live", col: r.hex }); });
    var order = { cb: 7, city: 0, hz: 1, fire: 2, news: 3, mine: 3, stn: 3, quake: 4, choke: 5, volc: 6, fpt: 6, cyc: 6, ex: 7, hot: 8, ev: 9, live: 10 };
    M.sort(function (a, b) { return order[a.k] - order[b.k]; });
    gMk.selectAll("*").remove();
    var g = gMk.selectAll("g").data(mk(M)).join("g").attr("class", "mk").attr("transform", function (d) { return "translate(" + d.x + "," + d.y + ") scale(" + (1 / zk) + ")"; });
    g.each(function (d) {
      var s = d3.select(this);
      if (d.k === "news" || d.k === "quake" || d.k === "fire") {
        if (d.k === "news" && isNewItem(d.s)) s.append("circle").attr("r", d.r + 3.5).attr("fill", "none").attr("stroke", C("--lime")).attr("stroke-width", 1.6);
        s.append("circle").attr("r", d.r).attr("fill", d.col).attr("stroke", "#04060a").attr("stroke-width", 1);
        if (d.k === "quake" && d.q.m >= 5) s.append("circle").attr("class", "pulse").attr("r", d.r * 2.5).attr("stroke", d.col);
        if (d.k === "fire") s.style("pointer-events", "none");
        s.on("click", function () { if (d.k === "news") showStory(d.s); else if (d.k === "quake") showQuake(d.q); })
          .on("mousemove", function (e) { if (d.k !== "fire") tipAt(e, d.k === "news" ? d.s.t : "M" + d.q.m.toFixed(1) + " " + d.q.place); }).on("mouseleave", hideTip);
      } else if (d.k === "hz") { s.append("circle").attr("r", d.r).attr("fill", rgba(d.col, 0.35)).attr("stroke", d.col); s.on("click", function () { showHazard(d.h, d.lab, d.col); }).on("mousemove", function (e) { tipAt(e, d.h.title); }).on("mouseleave", hideTip); }
      else if (d.k === "volc") { s.append("text").attr("text-anchor", "middle").attr("y", 4).attr("font-size", 12).attr("fill", C("--volcano")).text("▲"); s.on("click", function () { showHazard(d.v, "VOLCANO", C("--volcano")); }).on("mousemove", function (e) { tipAt(e, d.v.title); }).on("mouseleave", hideTip); }
      else if (d.k === "cyc") {
        var stc = stormOf(d.c), colc = stormCol(stc), ctc = catOf(stc && stc.wind_kt);
        s.append("g").attr("transform", "translate(-11,-11)").html(stormSVG(colc, 22).replace(/<svg[^>]*>|<\/svg>/g, "").replace(/^/, '<g transform="translate(11,11) scale(0.92)">') + "</g>");
        s.append("text").attr("x", 13).attr("y", 4).attr("font-size", 9.5).attr("fill", colc).text(stormName(d.c, stc) + (ctc ? " · " + ctc[0] : ""));
        s.on("click", function () { showStorm(d.c); }).on("mousemove", function (e) { tipAt(e, stormName(d.c, stc) + " · click for its path"); }).on("mouseleave", hideTip);
      } else if (d.k === "mine") {
        s.append("g").attr("transform", "translate(-7,-7)").html(mineSVG(mineCol(d.m), d.m[6] === "artisanal").replace(/<svg[^>]*>|<\/svg>/g, "").replace(/^/, '<g transform="translate(7,7) scale(0.58)">') + "</g>");
        if (detail) s.append("text").attr("x", 9).attr("y", 3).attr("font-size", 8.5).attr("fill", mineCol(d.m)).text(d.m[0]);
        s.on("click", function () { showMine(d.m); }).on("mousemove", function (e) { tipAt(e, d.m[0] + " · " + d.m[4] + (d.m[6] === "artisanal" ? " (artisanal)" : "")); }).on("mouseleave", hideTip);
      } else if (d.k === "stn") {
        s.append("g").attr("transform", "translate(-6,-6)").html(stnSVG.replace(/<svg[^>]*>|<\/svg>/g, "").replace(/^/, '<g transform="translate(6,6) scale(0.5)">') + "</g>");
        if (detail) s.append("text").attr("x", 8).attr("y", 3).attr("font-size", 8.5).attr("fill", "#9ec5ff").text(d.st[0]);
        s.on("click", function () { showStation(d.st); }).on("mousemove", function (e) { tipAt(e, d.st[0] + " · " + d.st[3]); }).on("mouseleave", hideTip);
      } else if (d.k === "fpt") {
        s.append("circle").attr("r", 3).attr("fill", "#fff").attr("stroke", "#04060a");
        s.on("click", function () { showStorm(d.c); }).on("mousemove", function (e) { tipAt(e, (d.p.label || "forecast") + (d.p.wind_kt ? " · " + mph(d.p.wind_kt) + " mph" : "") + (d.p.where ? " · " + d.p.where : "")); }).on("mouseleave", hideTip);
      }
      else if (d.k === "choke") {
        var sh = shipsFor(d.c), bad = sh && /disrupt|reduc/.test(sh.status), colc = bad ? C("--down") : C("--choke");
        s.append("rect").attr("x", -3.5).attr("y", -3.5).attr("width", 7).attr("height", 7).attr("transform", "rotate(45)").attr("fill", colc).attr("opacity", d.c.major ? 1 : 0.8);
        if (d.c.major || detail) s.append("text").attr("x", 7).attr("y", 3).attr("font-size", 9).attr("fill", colc).text(d.c.name);
        s.on("click", function () { showChoke(d.c); }).on("mousemove", function (e) { tipAt(e, d.c.name + (sh ? " · " + sh.status : "")); }).on("mouseleave", hideTip);
      } else if (d.k === "hot") {
        var col = C(LVL[d.h.lvl].v);
        s.append("circle").attr("class", "pulse").attr("r", 13).attr("stroke", col);
        s.append("g").attr("transform", "translate(-8,-9)").html(triSVG.replace("<svg", '<svg width="16" height="15"').replace("currentColor", col));
        s.on("click", function () { showHot(d.h); }).on("mousemove", function (e) { tipAt(e, d.h.name + " · " + d.h.n + " reports"); }).on("mouseleave", hideTip);
      } else if (d.k === "city") {
        var capital = d.c[4];
        s.append("circle").attr("r", capital ? 2.6 : 1.8).attr("fill", "#e8e8e3");
        var near = EVENTS.some(function (e) { return e.lat != null && Math.abs(e.lat - d.c[2]) < 0.25 && Math.abs(e.lng - d.c[3]) < 0.25; }), lx = near ? 12 : 5;
        s.append("text").attr("x", lx).attr("y", 3.5).attr("font-size", capital ? 11 : 9.5).attr("fill", capital ? "#e8e8e3" : "#b8bab2").text(d.c[0]);
        if (d.c[1] && zk >= 4) s.append("text").attr("x", lx).attr("y", 13.5).attr("font-size", 8).attr("fill", "#7d8078").text(d.c[1]);
        s.style("pointer-events", "none");
      } else if (d.k === "ev") {
        if (isNewItem(d.e)) s.append("circle").attr("r", 13.5).attr("fill", "none").attr("stroke", C("--lime")).attr("stroke-width", 1.8);
        s.append("g").attr("opacity", d.e.unconfirmed ? 0.75 : 1).html('<g transform="scale(0.95)">' + icon(d.e.type).replace(/<svg[^>]*>|<\/svg>/g, "") + "</g>");
        if (minsAgo(d.e.last) < 30) s.insert("circle", ":first-child").attr("class", "pulse").attr("r", 16).attr("stroke", ET[d.e.type].col);
        s.on("click", function () { showEvent(d.e); }).on("mousemove", function (e) { tipAt(e, ago(minsAgo(d.e.last)) + " · " + d.e.t); }).on("mouseleave", hideTip);
      } else if (d.k === "ex") {
        s.append("circle").attr("r", 3.6).attr("fill", "#34d399").attr("stroke", "#04060a").attr("opacity", isOpen(d.xc) ? 1 : 0.55);
        if (d.xc.tier === "MAJOR" || detail) s.append("text").attr("x", 6).attr("y", -4).attr("font-size", 8.5).attr("fill", "#34d399").text(d.xc.name + (d.xc.chg != null ? (d.xc.chg >= 0 ? " ▲" : " ▼") + Math.abs(d.xc.chg).toFixed(1) + "%" : ""));
        s.on("click", function () { showEx(d.xc); }).on("mousemove", function (e) { tipAt(e, d.xc.full + (isOpen(d.xc) ? " · open" : " · closed")); }).on("mouseleave", hideTip);
      } else if (d.k === "cb") {
        s.append("path").attr("d", "M0,-4.5L3.9,-2.25V2.25L0,4.5L-3.9,2.25V-2.25Z").attr("fill", "#fbbf24").attr("stroke", "#04060a");
        if (detail) s.append("text").attr("x", 6).attr("y", 8).attr("font-size", 8.5).attr("fill", "#fbbf24").text(d.b.short);
        s.on("click", function () { showBank(d.b); }).on("mousemove", function (e) { tipAt(e, d.b.name); }).on("mouseleave", hideTip);
      } else if (d.k === "live") { s.append("circle").attr("class", "pulse").attr("r", 22).attr("stroke", d.col).attr("stroke-width", 2); }
    });
  }
  function fitBox(bb, ms) {
    var W = stage.clientWidth, H = stage.clientHeight, a = proj(bb[0]), b = proj(bb[1]);
    var x0 = Math.min(a[0], b[0]), x1 = Math.max(a[0], b[0]), y0 = Math.min(a[1], b[1]), y1 = Math.max(a[1], b[1]);
    var padL = $("pane-left").classList.contains("closed") ? 20 : 210, padR = $("pane-right").classList.contains("closed") ? 20 : 300;
    var k = Math.min((W - padL - padR) / (x1 - x0), (H - 60) / (y1 - y0));
    svg.transition().duration(ms == null ? 900 : ms).call(zoom.transform, d3.zoomIdentity.translate(padL + (W - padL - padR) / 2 - k * (x0 + x1) / 2, H / 2 + 10 - k * (y0 + y1) / 2).scale(k));
  }
  function zoomToPoint(lng, lat, k) {
    var W = stage.clientWidth, H = stage.clientHeight, xy = proj([lng, lat]);
    svg.transition().duration(900).call(zoom.transform, d3.zoomIdentity.translate(W / 2 - k * xy[0], H / 2 - k * xy[1]).scale(Math.max(k, zk)));
  }
  var tip = $("tip");
  function tipAt(e, t, html) { tip.hidden = false; if (html) tip.innerHTML = t; else tip.textContent = t; tip.style.left = Math.min(e.clientX + 12, innerWidth - 320) + "px"; tip.style.top = (e.clientY - 28) + "px"; }
  function hideTip() { tip.hidden = true; }

  var SOL = null;
  var land110 = null;
  var GOV = null;
  function gov() {
    if (!GOV && window.ArchieGov) GOV = window.ArchieGov({ $: $, esc: esc, api: api, slug: slug, ago: ago, world: function () { return W110; }, openItem: openById,
      news: function (c) {
        var names = [c.name, c.long].concat(c.iso2 === "US" ? ["United States", "USA", "United States of America"] : c.iso2 === "GB" ? ["United Kingdom", "UK", "Britain"] : c.iso2 === "RU" ? ["Russia"] : []).filter(Boolean);
        return STORIES.concat(EVENTS).filter(function (e) { return inWindow(e.last, 168) && (names.indexOf(e.country) >= 0 || names.some(function (n) { return n.length > 3 && (e.t || "").indexOf(n) >= 0; })); })
          .sort(function (a, b) { return b.last - a.last; }).slice(0, 10).map(function (e) { return { id: e.id, t: e.t, when: ago(minsAgo(e.last)) }; });
      } });
    return GOV;
  }
  $("t-gov").onclick = function () { var g = gov(); if (g) g.toggle(); };
  function solar() { if (!SOL) SOL = window.ArchieSolar({ $: $, esc: esc, api: api, rich: rich, slug: slug, ago: ago, setView: setView, note: note, land: function () { if (!land110 && W110 && W110.objects.land) land110 = topojson.feature(W110, W110.objects.land); return land110; } }); return SOL; }
  function setView(v) {
    view = v;
    $("v-globe").setAttribute("aria-pressed", v === "globe"); $("v-map").setAttribute("aria-pressed", v === "map"); $("v-solar").setAttribute("aria-pressed", v === "solar");
    $("globe").hidden = v !== "globe"; $("map").toggleAttribute("hidden", v !== "map");
    stage.classList.toggle("solarmode", v === "solar");
    if (v === "solar") {
      if (!setView.panes) setView.panes = [!$("pane-left").classList.contains("closed"), !$("pane-right").classList.contains("closed")];
      setPane("left", false); setPane("right", false);
      G.pauseAnimation(); card.hidden = true; solar().show(); return;
    }
    if (SOL) SOL.hide();
    if (setView.panes) { setPane("left", setView.panes[0]); setPane("right", setView.panes[1]); setView.panes = null; }
    if (v === "map") { G.pauseAnimation(); drawMap(); if (region) fitBox(regionOf(region).bbox, 0); } else { G.resumeAnimation(); paintRadar(); }
  }
  $("v-globe").onclick = function () { setView("globe"); };
  $("v-map").onclick = function () { setView("map"); };
  $("v-solar").onclick = function () { setView("solar"); };

  function pickRegion(id) {
    region = id; renderLayers(); setTab("war"); renderWar(); renderNews(); card.hidden = true;
    var R = regionOf(id);
    if (!R) { if (view === "map") fitBox([[-180, -58], [180, 78]]); else G.pointOfView({ lat: 30, lng: 25, altitude: 2.1 }, 1200); refresh(); return; }
    setHash("region=" + id);
    if (view === "map") fitBox(R.bbox);
    else { var c = [(R.bbox[0][0] + R.bbox[1][0]) / 2, (R.bbox[0][1] + R.bbox[1][1]) / 2], span = Math.max(R.bbox[1][0] - R.bbox[0][0], R.bbox[1][1] - R.bbox[0][1]); G.pointOfView({ lat: c[1], lng: c[0], altitude: Math.max(0.35, span / 45) }, 1400); }
    refresh();
  }

  /* ============================ time slider ============================ */
  var playT = null;
  function setTime(hoursBack) {
    tEnd = hoursBack >= 0 ? null : NOW + hoursBack * 3600;
    $("trange").value = hoursBack;
    $("tlabel").textContent = tEnd ? new Date(tEnd * 1000).toLocaleString([], { weekday: "short", hour: "numeric", minute: "2-digit" }) : "live";
    document.body.classList.toggle("past", !!tEnd);
    buildHotspots(); renderWar(); renderNews(); refresh(); paintRadar();
  }
  $("trange").addEventListener("input", function () { setTime(+this.value); });
  $("tplay").onclick = function () {
    if (playT) { clearInterval(playT); playT = null; this.textContent = "▶"; return; }
    this.textContent = "❚❚"; var v = +$("trange").value; if (v >= 0) v = -72;
    playT = setInterval(function () { v += 1; if (v >= 0) { clearInterval(playT); playT = null; $("tplay").textContent = "▶"; setTime(0); return; } setTime(v); }, 350);
  };
  $("tlive").onclick = function () { if (playT) $("tplay").click(); setTime(0); };

  /* ============================ markets (tab + morning note) ============================ */
  function fmt(v, dec, unit) { return v == null ? "—" : v.toLocaleString("en-US", { minimumFractionDigits: dec, maximumFractionDigits: dec }) + (unit || ""); }
  function spark(svgEl, vals, up, dec, unit, Wd, Hd, labels) {
    if (!svgEl || !vals || vals.length < 2) return;
    var W = Wd || 200, H = Hd || 16, x = d3.scaleLinear().domain([0, vals.length - 1]).range([1, W - 2]), y = d3.scaleLinear().domain(d3.extent(vals)).range([H - 2, 2]);
    var col = up ? C("--up") : C("--down");
    svgEl.setAttribute("viewBox", "0 0 " + W + " " + H); svgEl.setAttribute("preserveAspectRatio", "none");
    svgEl.innerHTML = '<path d="' + d3.area().x(function (d, i) { return x(i); }).y0(H).y1(y)(vals) + '" fill="' + col + '" fill-opacity="0.08"></path><path d="' + d3.line().x(function (d, i) { return x(i); }).y(y)(vals) + '" fill="none" stroke="' + col + '" stroke-width="1.4" vector-effect="non-scaling-stroke"></path><line class="hair" y1="0" y2="' + H + '" stroke="#62645e" vector-effect="non-scaling-stroke" opacity="0"></line>';
    var hair = svgEl.querySelector(".hair");
    svgEl.addEventListener("pointermove", function (e) {
      var r = svgEl.getBoundingClientRect(), i = Math.max(0, Math.min(vals.length - 1, Math.round(x.invert((e.clientX - r.left) / r.width * W))));
      hair.setAttribute("x1", x(i)); hair.setAttribute("x2", x(i)); hair.setAttribute("opacity", 1);
      tip.hidden = false; tip.textContent = fmt(vals[i], dec, unit) + (labels ? "  ·  " + labels[i] : "");
      tip.style.left = (e.clientX + 12) + "px"; tip.style.top = (e.clientY - 30) + "px";
    });
    svgEl.addEventListener("pointerleave", function () { hideTip(); hair.setAttribute("opacity", 0); });
  }
  function chgTxt(v, dec) { if (v == null || isNaN(v)) return '<span class="mut">—</span>'; return '<span class="' + (v > 0 ? "up" : v < 0 ? "dn" : "") + '">' + (v > 0 ? "▲ +" : v < 0 ? "▼ −" : "· ") + Math.abs(v).toFixed(dec == null ? 2 : dec) + "%</span>"; }
  function bpTxt(v) { if (v == null || isNaN(v)) return '<span class="mut">—</span>'; v = Math.round(v); return '<span style="color:var(--fg)">' + (v > 0 ? "▲ +" : v < 0 ? "▼ −" : "· ") + Math.abs(v) + " bp</span>"; }
  function renderMarketsTab() {
    var box = $("p-mk"), tape = [], quotes = (S && S.quotes) || {};
    box.innerHTML = '<div class="livebar"><span>DELAYED ~15 MIN · YAHOO · FRED</span></div><button class="btn primary" id="open-note" style="width:100%;margin:2px 0 6px">open the morning note</button>';
    MK.forEach(function (grp) {
      var sec = document.createElement("div"); sec.innerHTML = '<div class="grp-h">' + grp[0] + "</div>";
      grp[1].forEach(function (r) {
        var q = quotes[r[1]]; if (!q) return;
        var el = document.createElement("div"); el.className = "mq";
        el.innerHTML = '<span class="nm"><button class="star" title="alert me on big moves">' + (isWatched("asset", r[1]) ? "★" : "☆") + "</button>" + r[0] + '</span><span class="px">' + fmt(q.price, r[2]) + '</span><span class="ch">' + chgTxt(q.chg) + '</span><svg class="spark" aria-label="' + r[0] + ' today"></svg>';
        sec.appendChild(el); spark(el.querySelector("svg"), q.spark, q.chg >= 0, r[2]);
        el.querySelector(".star").onclick = function (e) { e.stopPropagation(); toggleWatch("asset", r[1]); this.textContent = isWatched("asset", r[1]) ? "★" : "☆"; };
        el.querySelector(".nm").style.cursor = "help"; el.querySelector(".nm").title = "background on " + r[0];
        el.querySelector(".nm").onclick = function () { explainIt({ title: r[0], names: [r[0].replace(/ fut\.$/, "")], kind: "index" }); };
        tape.push('<span class="tk"><b>' + r[0] + "</b>" + fmt(q.price, r[2]) + " " + chgTxt(q.chg) + "</span>");
      });
      if (sec.children.length > 1) box.appendChild(sec);
    });
    var c = S && S.curve;
    if (c && c.now) {
      var sec = document.createElement("div"); sec.innerHTML = '<div class="grp-h">US Treasury yields</div>';
      [3, 7, 9].forEach(function (i) {
        if (c.now[i] == null) return;
        var el = document.createElement("div"); el.className = "mq";
        el.innerHTML = '<span class="nm">US ' + c.t[i] + '</span><span class="px">' + c.now[i].toFixed(2) + '%</span><span class="ch">' + bpTxt(c.prev[i] != null ? (c.now[i] - c.prev[i]) * 100 : null) + "</span>";
        sec.appendChild(el);
        tape.push('<span class="tk"><b>US ' + c.t[i] + "</b>" + c.now[i].toFixed(2) + "% " + bpTxt(c.prev[i] != null ? (c.now[i] - c.prev[i]) * 100 : null) + "</span>");
      });
      box.appendChild(sec);
    }
    var pr = (S && S.predictions) || [];
    if (pr.length) {
      var p2 = document.createElement("div");
      p2.innerHTML = '<div class="grp-h">Prediction markets · Polymarket</div>' + pr.map(function (p) { return '<div class="pq"><span>' + esc(p.q) + '</span><span class="px">' + p.yes + '%</span><div class="meter" style="grid-column:1/-1"><span style="width:' + p.yes + '%"></span></div></div>'; }).join("");
      box.appendChild(p2);
    }
    if (!Object.keys(quotes).length) box.insertAdjacentHTML("beforeend", '<p class="note">No prices yet. They come in once Archie is online (every 5 minutes while markets are open).</p>');
    $("tape").innerHTML = tape.length ? tape.join("") + tape.join("") : '<span class="tk"><b>markets</b> waiting for prices…</span>';
    $("open-note").onclick = openNote;
  }

  function openNote() {
    var o = $("note"); if (o) o.remove();
    o = document.createElement("div"); o.id = "note"; o.className = "note-wrap";
    var d = new Date(), quotes = (S && S.quotes) || {}, note = (S && S.note) || {}, c = S && S.curve, fred = (S && S.fred) || {};
    var today = d.toDateString();
    var cal = ((S && S.calendar) || []).filter(function (e) { return new Date(e.time * 1000).toDateString() === today; }).sort(function (a, b) { return a.time - b.time; });
    var imp = { High: 3, Medium: 2, Low: 1 };
    var earn = (S && S.earnings && S.earnings.rows) || [];
    var take = note.take && note.date === d.toISOString().slice(0, 10) ? note.take : (note.take ? note.take + ' <span class="mut">(from ' + note.date + ")</span>" : '<span class="mut">Archie writes this after 6 am once the overnight prices are in. The numbers below are live.</span>');
    var h = '<div class="note-card"><button class="x" id="note-x" aria-label="Close">×</button>' +
      '<div class="n-top"><span class="brand">ARCHIE <b>MORNING NOTE</b></span><span class="stamp">' + d.toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" }) + (note.written ? " · written " + clock(note.written) : "") + " · prices ~15 min delayed</span></div>" +
      '<div class="n-take"><div class="h">The take</div><p>' + esc(take).replace(/&lt;(\/?)span([^&]*)&gt;/g, "<$1span$2>").replace(/&quot;/g, '"') + "</p></div>" +
      '<div class="n-grid"><section class="n-board"><div class="h">Cross-asset board · today · 1 week · year to date · 5 days</div><table class="bt"><tbody id="bt"></tbody></table></section>' +
      '<section class="n-side"><div class="h">S&amp;P 500 sectors · today</div><div class="heat" id="heat"></div><div class="heatkey"><span>▼ −1%</span><i></i><span>+1% ▲</span></div>' +
      '<div class="h" style="margin-top:14px">US Treasury yield curve</div><div class="lg"><span><i style="background:var(--lime)"></i>' + (c && c.date ? c.date : "latest") + '</span><span><i style="background:#8f918a"></i>a month before</span><span id="spr"></span></div><svg id="curve" class="curve"></svg>' +
      '<div class="h" style="margin-top:14px">Rates & credit</div><table class="bt bk"><tbody>' +
      [["Fed funds", fred["Fed funds upper"] && fred["Fed funds upper"].now != null ? fred["Fed funds lower"].now.toFixed(2) + "–" + fred["Fed funds upper"].now.toFixed(2) + "%" : "—"], ["ECB deposit rate", fred["ECB deposit rate"] && fred["ECB deposit rate"].now != null ? fred["ECB deposit rate"].now.toFixed(2) + "%" : "—"],
        ["US high-yield spread", fred["US high-yield spread"] && fred["US high-yield spread"].now != null ? Math.round(fred["US high-yield spread"].now * 100) + " bp" : "—"], ["US inv. grade spread", fred["US inv. grade spread"] && fred["US inv. grade spread"].now != null ? Math.round(fred["US inv. grade spread"].now * 100) + " bp" : "—"]]
        .map(function (r) { return "<tr><td>" + r[0] + '</td><td class="num">' + r[1] + "</td></tr>"; }).join("") + "</tbody></table>" +
      ((S && S.predictions && S.predictions.length) ? '<div class="h" style="margin-top:14px">Odds · Polymarket</div><table class="bt bk"><tbody>' + S.predictions.slice(0, 5).map(function (p) { return "<tr><td style=\"white-space:normal\">" + esc(p.q) + '</td><td class="num">' + p.yes + "%</td></tr>"; }).join("") + "</tbody></table>" : "") +
      "</section>" +
      '<section><div class="h">Today\'s calendar · your time</div><table class="bt cal"><thead><tr><th></th><th></th><th>event</th><th class="num">expected</th><th class="num">last</th><th class="num">actual</th></tr></thead><tbody>' +
      (cal.length ? cal.map(function (e) { var n = imp[e.impact] || 0; return '<tr><td class="mut num">' + new Date(e.time * 1000).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }) + '</td><td class="mut">' + esc(e.cc) + '</td><td><span class="imp">' + "●".repeat(n) + '<span class="mut">' + "●".repeat(3 - n) + "</span></span> " + esc(e.title) + '</td><td class="num">' + esc(e.forecast) + '</td><td class="num mut">' + esc(e.previous) + '</td><td class="num">' + esc(e.actual || "") + "</td></tr>"; }).join("") : '<tr><td colspan="6" class="mut">Nothing scheduled, or the calendar hasn\'t come in yet.</td></tr>') + "</tbody></table></section>" +
      '<section><div class="h">Earnings today' + (S && S.earnings ? " · " + S.earnings.date : "") + '</div><table class="bt"><tbody>' + (earn.length ? earn.map(function (e) { return '<tr><td class="mut">' + esc(e.when) + "</td><td>" + esc(e.name) + ' <span class="mut">' + esc(e.symbol) + '</span></td><td class="num">EPS est. ' + esc(e.eps || "—") + '</td><td class="num mut">' + esc(e.cap) + "</td></tr>"; }).join("") : '<tr><td class="mut">No big names reporting today.</td></tr>') + "</tbody></table>" +
      '<div class="h" style="margin-top:14px">What moved, and why</div><ul class="why">' + ((note.moved || []).map(function (m) { return "<li><b>" + esc(m.what) + "</b> " + esc(m.why) + (m.headline ? ' <a href="#" data-q="' + esc(m.headline) + '">find it</a>' : "") + "</li>"; }).join("") || '<li class="mut">Written with the take.</li>') + "</ul></section>" +
      '</div><p class="n-src">Prices: Yahoo Finance (~15 min delayed). Yields, spreads and policy rates: FRED. Calendar: Forex Factory feed. Earnings: Nasdaq. Odds: Polymarket. Archie writes "the take" only from these numbers and today\'s headlines, and never makes up a figure.</p></div>';
    o.innerHTML = h; document.body.appendChild(o);
    $("note-x").onclick = function () { o.remove(); };
    o.addEventListener("click", function (e) { if (e.target === o) o.remove(); });
    o.querySelectorAll("[data-q]").forEach(function (a) { a.onclick = function (e) { e.preventDefault(); o.remove(); var t = a.dataset.q.toLowerCase(), best = STORIES.find(function (s) { return s.t.toLowerCase() === t; }) || STORIES.find(function (s) { return s.t.toLowerCase().indexOf(t.slice(0, 40)) >= 0; }); if (best) openById(best.id); else askMap(a.dataset.q); }; });
    var tb = $("bt");
    MK.forEach(function (grp) {
      var rows = grp[1].filter(function (r) { return quotes[r[1]]; }); if (!rows.length) return;
      var tr = document.createElement("tr"); tr.className = "gh"; tr.innerHTML = '<td colspan="6">' + grp[0] + "</td>"; tb.appendChild(tr);
      rows.forEach(function (r) {
        var q = quotes[r[1]], neutral = grp[0] === "Volatility";
        var tr2 = document.createElement("tr");
        tr2.innerHTML = "<td>" + r[0] + '</td><td class="num">' + fmt(q.price, r[2]) + '</td><td class="num">' + (neutral ? '<span style="color:var(--fg)">' + (q.chg >= 0 ? "▲ +" : "▼ −") + Math.abs(q.chg).toFixed(1) + "%</span>" : chgTxt(q.chg)) + '</td><td class="num">' + chgTxt(q.w1, 1) + '</td><td class="num">' + chgTxt(q.ytd, 1) + '</td><td class="sp"><svg aria-label="' + r[0] + ' over 5 days"></svg></td>';
        tb.appendChild(tr2);
        var v = q.d5 && q.d5.length > 1 ? q.d5 : q.spark;
        if (v && v.length > 1) { spark(tr2.querySelector("svg"), v, neutral ? true : v[v.length - 1] >= v[0], r[2], "", 90, 18); if (neutral) tr2.querySelector("svg path:nth-child(2)").setAttribute("stroke", "#a3a3a3"); }
      });
    });
    if (c && c.now) {
      var tr = document.createElement("tr"); tr.className = "gh"; tr.innerHTML = '<td colspan="6">US Treasury yields</td>'; tb.appendChild(tr);
      [0, 3, 5, 7, 9].forEach(function (i) {
        if (c.now[i] == null) return;
        var tr2 = document.createElement("tr");
        tr2.innerHTML = "<td>US " + c.t[i] + '</td><td class="num">' + c.now[i].toFixed(2) + '%</td><td class="num">' + bpTxt(c.prev[i] != null ? (c.now[i] - c.prev[i]) * 100 : null) + '</td><td class="num"></td><td class="num">' + (c.ago[i] != null ? '<span class="mut">1 mo </span>' + bpTxt((c.now[i] - c.ago[i]) * 100) : "") + "</td><td></td>";
        tb.appendChild(tr2);
      });
    }
    // sector heatmap: diverging red · gray · lime
    var col = d3.scaleLinear().domain([-1, 0, 1]).range([C("--down"), "#2a2d27", C("--up")]).clamp(true);
    var secs = SECTORS.filter(function (s) { return quotes[s[1]]; }).map(function (s) { return [s[0], quotes[s[1]].chg, quotes[s[1]].ytd]; }).sort(function (a, b) { return b[1] - a[1]; });
    $("heat").innerHTML = secs.length ? secs.map(function (s) {
      var v = s[1], dark = Math.abs(v) > 0.45;
      return '<div class="cell" style="background:' + col(v) + ";color:" + (dark ? "#0a0a0a" : "#e8e8e3") + '" title="' + s[0] + ": " + (v > 0 ? "+" : "") + v.toFixed(2) + "% today" + (s[2] != null ? ", " + s[2].toFixed(1) + "% this year" : "") + '"><span>' + s[0] + "</span><b>" + (v > 0 ? "▲ +" : "▼ −") + Math.abs(v).toFixed(2) + "%</b></div>";
    }).join("") : '<p class="note">Sector prices come in with the rest.</p>';
    // yield curve
    if (c && c.now && c.now.some(function (v) { return v != null; })) {
      var sv = d3.select("#curve"), W = 330, H = 150, m = { l: 34, r: 8, t: 8, b: 20 };
      sv.attr("viewBox", "0 0 " + W + " " + H);
      var all = c.now.concat(c.ago).filter(function (v) { return v != null; });
      var x = d3.scalePoint().domain(c.t).range([m.l, W - m.r]), y = d3.scaleLinear().domain([d3.min(all) - 0.15, d3.max(all) + 0.15]).nice().range([H - m.b, m.t]);
      y.ticks(4).forEach(function (t) { sv.append("line").attr("x1", m.l).attr("x2", W - m.r).attr("y1", y(t)).attr("y2", y(t)).attr("stroke", "#1c2018"); sv.append("text").attr("x", m.l - 5).attr("y", y(t) + 3).attr("text-anchor", "end").attr("class", "ax").text(t.toFixed(1) + "%"); });
      c.t.forEach(function (t) { sv.append("text").attr("x", x(t)).attr("y", H - 5).attr("text-anchor", "middle").attr("class", "ax").text(t); });
      var ln = function (k) { return d3.line().defined(function (d) { return d != null; }).x(function (d, i) { return x(c.t[i]); }).y(function (d) { return y(d); })(c[k]); };
      sv.append("path").attr("d", ln("ago")).attr("fill", "none").attr("stroke", "#8f918a").attr("stroke-width", 1.5).attr("stroke-dasharray", "4 3");
      sv.append("path").attr("d", ln("now")).attr("fill", "none").attr("stroke", C("--lime")).attr("stroke-width", 2);
      c.now.forEach(function (v, i) { if (v != null) sv.append("circle").attr("cx", x(c.t[i])).attr("cy", y(v)).attr("r", 2.5).attr("fill", C("--lime")); });
      var hair = sv.append("line").attr("y1", m.t).attr("y2", H - m.b).attr("stroke", "#62645e").attr("opacity", 0);
      sv.append("rect").attr("x", m.l).attr("y", 0).attr("width", W - m.l - m.r).attr("height", H).attr("fill", "transparent")
        .on("pointermove", function (e) {
          var r = this.getBoundingClientRect(), px = (e.clientX - r.left) / r.width * (W - m.l - m.r) + m.l, i = d3.minIndex(c.t, function (t) { return Math.abs(x(t) - px); });
          hair.attr("x1", x(c.t[i])).attr("x2", x(c.t[i])).attr("opacity", 1);
          tip.hidden = false; tip.textContent = c.t[i] + ": " + fmt(c.now[i], 2, "%") + " · a month before " + fmt(c.ago[i], 2, "%") + (c.now[i] != null && c.ago[i] != null ? " (" + ((c.now[i] - c.ago[i]) * 100 > 0 ? "+" : "") + Math.round((c.now[i] - c.ago[i]) * 100) + " bp)" : "");
          tip.style.left = (e.clientX + 12) + "px"; tip.style.top = (e.clientY - 30) + "px";
        }).on("pointerleave", function () { hideTip(); hair.attr("opacity", 0); });
      if (c.now[7] != null && c.now[3] != null) { var s210 = Math.round((c.now[7] - c.now[3]) * 100); $("spr").innerHTML = '2s10s: <b style="color:var(--fg)">' + (s210 > 0 ? "+" : "") + s210 + " bp</b>"; }
    } else $("curve").outerHTML = '<p class="note">Yields come in from FRED once a day.</p>';
  }
  $("t-note").onclick = openNote;

  /* ============================ news brief ============================ */
  function suggestTopic(st) {
    var words = (st.t || "").replace(/[^A-Za-z0-9' \-]/g, " ").split(/\s+/).filter(function (w) { return w.length > 3 && /^[A-Z]/.test(w); });
    return st.place && st.place !== "Washington" ? st.place : words.slice(0, 2).join(" ");
  }
  function briefRow(st) {
    var m = [st.n + (st.n === 1 ? " outlet" : " outlets") + (st.also ? " (+" + st.also + " similar write-ups folded in)" : ""), st.place || "", ago(minsAgo(st.last))].filter(Boolean).join(" · ");
    var cov = (st.l + st.c + st.r) ? covHTML({ l: st.l, c: st.c, r: st.r, o: 0 }, "minicov") + " " : "";
    return '<div class="nb-story" data-id="' + st.id + '"><button class="nb-t">' + esc(st.t) + '</button>' +
      '<div class="nb-m">' + cov + esc(m) + "</div>" + (st.summary ? '<div class="nb-s">' + esc(st.summary) + "</div>" : "") +
      '<div class="nb-a"><a href="#" data-act="save">save</a><a href="#" data-act="catch">catch me up</a><a href="#" data-act="bg">background</a><a href="#" data-act="follow">follow</a><a href="#" data-act="mute">less like this</a>' +
      (st.src[0] && st.src[0].url ? '<a href="' + esc(st.src[0].url) + '" target="_blank" rel="noopener">read ↗</a>' : "") + "</div></div>";
  }
  function openBrief() {
    var o = $("brief"); if (o) o.remove();
    o = document.createElement("div"); o.id = "brief"; o.className = "note-wrap";
    o.innerHTML = '<div class="note-card"><p class="note">Putting the brief together…</p></div>';
    document.body.appendChild(o);
    o.addEventListener("click", function (e) { if (e.target === o) o.remove(); });
    fetch("/api/brief").then(function (r) {
      if (r.status === 404) throw new Error("the Archie running now is older than this page. Double-click Restart Archie.bat in the Archie folder.");
      return r.json();
    }).then(function (b) {
      if (b.error) throw new Error(b.error);
      renderBrief(o, b);
    }).catch(function (e) { o.querySelector(".note").textContent = "Couldn't load the brief: " + (e.message || e); });
  }
  function renderBrief(o, b) {
    var all = {}; b.global.concat(b.home, b.local, b.big_new || []).forEach(function (s) { all[s.id] = s; });
    b.following.forEach(function (f) { f.stories.forEach(function (s) { all[s.id] = s; }); });
    var d = new Date(), take = b.take || {}, today = d.toISOString().slice(0, 10), ed = b.edition;
    var edTxt = !ed ? "live · last 24 hours from " + b.outlets + " sources" :
      ed.stale ? "yesterday's edition · the next one comes at " + (ed.hour % 12 || 12) + (ed.hour < 12 ? " am" : " pm") :
      (ed.kind === "update" ? "updated " + clock(ed.at) : clock(ed.at) + " edition") + " · " + b.outlets + " sources";
    var big = b.big_new || [];
    var bigBar = big.length ? '<div class="nb-big"><div class="nb-big-h"><b>● ' + big.length + (big.length === 1 ? " big story" : " big stories") + " since this edition</b>" +
      '<button class="btn primary" id="nb-refresh">refresh the brief</button></div><ul>' + big.map(function (x) { return '<li><a href="#" data-big="' + x.id + '">' + esc(x.t) + "</a> <span class=\"mut\">" + x.n + " outlets</span></li>"; }).join("") + "</ul></div>" : "";
    var sec = function (title, list, empty) { return '<section><div class="h">' + title + "</div>" + (list.length ? list.map(briefRow).join("") : '<p class="note">' + empty + "</p>") + "</section>"; };
    var h = '<div class="note-card"><button class="x" id="brief-x" aria-label="Close">×</button>' +
      '<div class="n-top"><span class="brand">ARCHIE <b>NEWS BRIEF</b></span><span class="stamp">' + d.toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" }) + " · " + edTxt + (ed ? ' · <a href="#" id="nb-refresh2" class="nb-link">refresh now</a>' : "") + "</span></div>" + bigBar +
      '<div class="n-take nb-take"><div><div class="h">The world</div><p>' + esc(take.world || (ed ? "Archie is writing this summary…" : "Archie writes this at 6 am once the overnight news is in. The stories below are live until then.")) + (ed && ed.take_pending && take.world ? ' <span class="mut">(rewriting it for the refresh…)</span>' : "") + '</p></div><div><div class="h">At home</div><p>' + esc(take.home || "—") + "</p></div></div>" +
      '<div class="n-grid nb-grid"><div>' + sec("Around the world", b.global, "Nothing big yet.") + sec("At home · United States", b.home, "Nothing big yet.") + sec("Close to home", b.local, "No local stories in the last day (edit the searches in sources.json).") + "</div>" +
      '<div>' + (b.watched && b.watched.length ? '<section><div class="h">Bills and lawmakers you\'re watching</div>' + b.watched.map(function (w) { return '<a href="#" class="nb-watch" data-link="' + esc(w.link) + '"><b>' + esc(w.label) + "</b> " + esc(w.detail) + "</a>"; }).join("") + "</section>" : "") + (b.coming && b.coming.length ? '<section><div class="h">Coming up this week · <a href="#" id="nb-cal" class="nb-link">world calendar</a></div>' + b.coming.map(calRow).join("") + "</section>" : "") + '<section><div class="h">Following</div><div class="nb-chips">' + b.follow.map(function (t, i) { return '<span class="nb-chip">' + esc(t) + '<button data-rm-follow="' + i + '" aria-label="stop following">×</button></span>'; }).join("") +
      '</div><div class="nb-add"><input id="nb-follow" placeholder="follow a topic (e.g. SpaceX, Gaza, housing)"><button class="btn" id="nb-follow-btn">add</button></div>' +
      b.following.map(function (f) { return '<div class="grp-h">' + esc(f.topic) + "</div>" + (f.stories.length ? f.stories.map(briefRow).join("") : '<p class="note" style="margin:2px 0 6px">Nothing in the last 3 days.</p>'); }).join("") +
      '</section><section><div class="h">Muted</div><div class="nb-chips">' + (b.mute.length ? b.mute.map(function (t, i) { return '<span class="nb-chip mute">' + esc(t) + '<button data-rm-mute="' + i + '" aria-label="unmute">×</button></span>'; }).join("") : '<span class="note">Nothing muted. Use "less like this" on a story.</span>') +
      '</div><div class="nb-add"><input id="nb-mute" placeholder="never show stories about…"><button class="btn" id="nb-mute-btn">mute</button></div></section></div></div>' +
      '<p class="n-src">Stories are grouped across outlets; the bar is the left / center / right mix of US outlets that covered it. Topics can be several words separated by commas (any of them counts). Followed topics look back 3 days.</p></div>';
    o.innerHTML = h;
    $("brief-x").onclick = function () { o.remove(); };
    var doRefresh = function (e) { if (e) e.preventDefault(); o.querySelector(".n-top .stamp").textContent = "refreshing…"; api("/api/brief_refresh", {}).then(function (nb) { if (S) S.brief_new = 0; briefBadge(); renderBrief(o, nb); }); };
    if ($("nb-refresh")) $("nb-refresh").onclick = doRefresh;
    if ($("nb-refresh2")) $("nb-refresh2").onclick = doRefresh;
    o.querySelectorAll("[data-big]").forEach(function (a) { a.onclick = function (e) { e.preventDefault(); o.remove(); if (STORIES.some(function (x) { return x.id === a.dataset.big; })) openById(a.dataset.big); else location.hash = "story=" + a.dataset.big; }; });
    clearTimeout(renderBrief.poll);
    if (ed && ed.take_pending) {
      var tries = (renderBrief.tries = (renderBrief.tries || 0) + 1);
      if (tries < 40) renderBrief.poll = setTimeout(function () { if (o.isConnected) api("/api/brief").then(function (nb) { if (o.isConnected && !nb.error) renderBrief(o, nb); }); }, 6000);
    } else renderBrief.tries = 0;
    if ($("nb-cal")) $("nb-cal").onclick = function (e) { e.preventDefault(); o.remove(); openCalendar(); };
    o.querySelectorAll(".nb-watch").forEach(function (x) { x.onclick = function (e) { e.preventDefault(); o.remove(); location.hash = x.dataset.link; }; });
    bindCalRows(o, b.coming || []);
    function save(follow, mute) { api("/api/follow", { follow: follow, mute: mute }).then(function (nb) { if (S && S.watch) { S.watch.follow = nb.follow; S.watch.mute = nb.mute; } renderBrief(o, nb); }); }
    o.querySelectorAll("[data-rm-follow]").forEach(function (x) { x.onclick = function () { var f = b.follow.slice(); f.splice(+x.dataset.rmFollow, 1); save(f, b.mute); }; });
    o.querySelectorAll("[data-rm-mute]").forEach(function (x) { x.onclick = function () { var m = b.mute.slice(); m.splice(+x.dataset.rmMute, 1); save(b.follow, m); }; });
    $("nb-follow-btn").onclick = function () { var v = $("nb-follow").value.trim(); if (v) save(b.follow.concat([v]), b.mute); };
    $("nb-mute-btn").onclick = function () { var v = $("nb-mute").value.trim(); if (v) save(b.follow, b.mute.concat([v])); };
    $("nb-follow").onkeydown = function (e) { if (e.key === "Enter") $("nb-follow-btn").click(); };
    $("nb-mute").onkeydown = function (e) { if (e.key === "Enter") $("nb-mute-btn").click(); };
    o.querySelectorAll(".nb-story").forEach(function (row) {
      var st = all[row.dataset.id]; if (!st) return;
      row.querySelector(".nb-t").onclick = function () {
        var have = STORIES.find(function (x) { return x.id === st.id; }) || EVENTS.find(function (x) { return x.id === st.id; });
        o.remove();
        if (have) openById(st.id); else location.hash = "story=" + st.id;
      };
      row.querySelectorAll("[data-act]").forEach(function (a) {
        a.onclick = function (e) {
          e.preventDefault();
          if (a.dataset.act === "save") { saveItem(st, "story"); a.textContent = "saved ✓"; }
          if (a.dataset.act === "catch") { o.remove(); catchUp(st.id, st.t); }
          if (a.dataset.act === "bg") { o.remove(); explainIt({ title: st.t, text: st.t + ". " + (st.summary || "") }); }
          if (a.dataset.act === "follow") { var t = window.prompt("Follow stories about… (words or names; commas for any of several)", suggestTopic(st)); if (t && t.trim()) save(b.follow.concat([t.trim()]), b.mute); }
          if (a.dataset.act === "mute") { var m = window.prompt("Show fewer stories about…", suggestTopic(st)); if (m && m.trim()) save(b.follow, b.mute.concat([m.trim()])); }
        };
      });
    });
  }
  $("t-brief").onclick = openBrief;
  function briefBadge() {
    var n = (S && S.brief_new) || 0, b = $("t-brief");
    b.innerHTML = "news brief" + (n ? ' <span class="badge" title="big stories since this morning\'s edition">' + n + "</span>" : "");
  }

  /* ============================ world calendar ============================ */
  var CALK = { "election": ["#c084fc", "election"], "central bank": ["#fbbf24", "central bank"], "economy": ["#60a5fa", "economy"], "earnings": ["#34d399", "earnings"], "launch": ["#38bdf8", "launch"] };
  function calDate(i) {
    var d = new Date(i.time ? i.time * 1000 : i.date + "T12:00:00");
    return d.toLocaleDateString([], { weekday: "short", month: "short", day: "numeric" }) + (i.time ? " · " + d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }) : "");
  }
  function calRow(i) {
    var k = CALK[i.kind] || ["#8f918a", i.kind];
    return '<div class="cal-row" data-id="' + i.id + '"><span class="cal-k" style="color:' + k[0] + ';border-color:' + k[0] + '">' + k[1] + '</span><div><div class="cal-t">' + esc(i.title) + '</div><div class="nb-m">' + calDate(i) + (i.where ? " · " + esc(i.where) : "") + (i.detail ? " · " + esc(i.detail) : "") + '</div><div class="nb-a">' +
      (i.lat != null ? '<a href="#" data-cal="globe">on the globe</a>' : "") + '<a href="#" data-cal="add">add to my calendar</a><a href="#" data-cal="bg">background</a>' + (i.url ? '<a href="' + esc(i.url) + '" target="_blank" rel="noopener">source ↗</a>' : "") + "</div></div></div>";
  }
  function bindCalRows(o, list) {
    o.querySelectorAll(".cal-row").forEach(function (row) {
      var it = list.find(function (x) { return x.id === row.dataset.id; }); if (!it) return;
      row.querySelectorAll("[data-cal]").forEach(function (a) {
        a.onclick = function (e) {
          e.preventDefault();
          if (a.dataset.cal === "globe") { o.remove(); focus(it.lat, it.lng, 1.0); highlight = [{ lat: it.lat, lng: it.lng }]; refresh(); setTimeout(function () { highlight = []; refresh(); }, 8000); }
          if (a.dataset.cal === "add") api("/api/calendar_add", it).then(function (r) { a.textContent = r.ok ? "added ✓" : "couldn't add: " + r.error; });
          if (a.dataset.cal === "bg") { o.remove(); explainIt({ title: it.title, text: it.title + " (" + it.date + (it.where ? ", " + it.where : "") + ")" + (it.detail ? " — " + it.detail : ""), names: it.kind === "election" ? [it.title] : [] }); }
        };
      });
    });
  }
  var calFilter = "all";
  function openCalendar() {
    var o = $("calwrap"); if (o) o.remove();
    o = document.createElement("div"); o.id = "calwrap"; o.className = "note-wrap";
    document.body.appendChild(o);
    o.addEventListener("click", function (e) { if (e.target === o) o.remove(); });
    function draw(list) {
      var shown = list.filter(function (i) { return calFilter === "all" || i.kind === calFilter; });
      var days = d3.groups(shown, function (i) { return i.date; });
      o.innerHTML = '<div class="note-card" style="width:min(900px,100%)"><button class="x" id="cal-x">×</button><div class="n-top"><span class="brand">WORLD <b>CALENDAR</b></span><span class="stamp">next 60 days · ' + list.length + ' dates</span></div>' +
        '<div class="chips">' + ["all"].concat(Object.keys(CALK)).map(function (k) { return '<button class="chip calf" data-k="' + k + '" aria-pressed="' + (calFilter === k) + '">' + (k === "all" ? "everything" : ({ economy: "economic data", earnings: "earnings" }[CALK[k][1]] || CALK[k][1] + "s")) + "</button>"; }).join("") + "</div>" +
        (days.length ? days.map(function (g) { return '<div class="grp-h" style="margin-top:12px">' + new Date(g[0] + "T12:00:00").toLocaleDateString([], { weekday: "long", month: "long", day: "numeric" }) + "</div>" + g[1].map(calRow).join(""); }).join("") : '<p class="note">Nothing yet. The calendar fills in once Archie has been online for a bit (elections from Wikidata, central banks and big economic numbers, big earnings, rocket launches).</p>') +
        '<p class="n-src">Elections: Wikidata. Central banks and economic releases: Forex Factory (this week and next) and the Fed\'s published schedule. Earnings: Nasdaq (companies worth $50B+). Launches: The Space Devs. Dates can move; check the source.</p></div>';
      $("cal-x").onclick = function () { o.remove(); };
      o.querySelectorAll(".calf").forEach(function (b) { b.onclick = function () { calFilter = b.dataset.k; draw(list); }; });
      bindCalRows(o, shown);
    }
    o.innerHTML = '<div class="note-card"><p class="note">Loading…</p></div>';
    api("/api/calendar").then(function (r) { S.cal = r.items; draw(r.items); });
  }
  $("t-cal").onclick = openCalendar;
  $("t-quiz").onclick = openQuiz;
  $("t-new").onclick = openNewList;

  /* ============================ sources panel ============================ */
  function openSources() {
    api("/api/sources").then(function (r) {
      var o = document.createElement("div"); o.className = "note-wrap"; o.id = "srcmodal";
      var ok = r.sources.filter(function (s) { return s.ok; }).length;
      o.innerHTML = '<div class="note-card" style="width:min(900px,100%)"><button class="x" onclick="this.closest(\'.note-wrap\').remove()">×</button><div class="n-top"><span class="brand">SOURCES</span><span class="stamp">' + ok + " working · " + (r.sources.length - ok) + " not answering · edit the list in " + esc(r.file) + '</span></div>' +
        '<p class="note" style="margin:0">"Matched by others" = how often a second, separate outlet reported the same event within two days (last 30 days, after 8+ reports). It matches on shared words in the headline and summary, shared names and the same place, not exact wording. Low numbers don\'t mean false: big outlets publish many stories nobody else covers, and some channels are simply first. It\'s most useful for small or unknown sources.</p>' +
        '<table class="bt"><thead><tr><th>source</th><th>kind</th><th>status</th><th class="num">items</th><th class="num">matched by others</th><th>last check</th></tr></thead><tbody>' +
        r.sources.map(function (s) { return "<tr><td>" + esc(s.name) + '</td><td class="mut">' + esc(s.kind) + "</td><td>" + (s.ok ? '<span class="up">● ok</span>' : '<span class="dn" title="' + esc(s.error) + '">● ' + esc((s.error || "failed").slice(0, 40)) + "</span>") + '</td><td class="num">' + (s.count || 0) + '</td><td class="num">' + (s.trust ? '<span style="color:' + (s.trust.rate >= 60 ? "var(--up)" : s.trust.rate >= 35 ? "var(--quake)" : "var(--down)") + '">' + s.trust.rate + "%</span> <span class=\"mut\">of " + s.trust.n + "</span>" : '<span class="mut">—</span>') + '</td><td class="mut">' + clock(s.last) + "</td></tr>"; }).join("") +
        '</tbody></table><div class="row"><button class="btn primary" id="src-refresh">check everything now</button></div></div>';
      document.body.appendChild(o);
      o.addEventListener("click", function (e) { if (e.target === o) o.remove(); });
      $("src-refresh").onclick = function () { api("/api/refresh", {}); this.textContent = "checking in the background…"; };
      var rulesBox = document.createElement("div"); var tbl = o.querySelector(".bt"); tbl.parentNode.insertBefore(rulesBox, tbl);
      function drawRules(rr) {
        var list = (rr && rr.rules) || [];
        rulesBox.innerHTML = '<div class="h" style="margin-top:12px">Your label fixes · ' + list.length + '</div>' + (list.length ? '<table class="bt"><thead><tr><th>word</th><th>was labeled</th><th>now</th><th>from the story</th><th></th></tr></thead><tbody>' +
          list.map(function (r, i) { return '<tr><td><b>' + esc(r.word) + '</b></td><td class="mut">' + esc(ET[r.from] ? ET[r.from].name : r.from) + "</td><td>" + esc(ET[r.to] ? ET[r.to].name : "just news") + '</td><td class="mut">' + esc((r.example || "").slice(0, 70)) + '</td><td><button class="btn rm-rule" data-i="' + i + '">remove</button></td></tr>'; }).join("") + "</tbody></table>" :
          '<p class="note" style="margin:2px 0 4px">None yet. When an icon is wrong, open it and press <b>wrong label?</b>.</p>') + '<div class="h" style="margin-top:12px">Feeds</div>';
        rulesBox.querySelectorAll(".rm-rule").forEach(function (b) { b.onclick = function () { api("/api/rules", { remove: +b.dataset.i }).then(drawRules); }; });
      }
      api("/api/rules").then(drawRules).catch(function () { });
    });
  }
  $("sources-btn").onclick = openSources;

  /* ============================ deep links ============================
     #choke=suez-canal  #ex=EGX  #cb=Fed  #country=Iran  #region=sudan  #event=<id>  #story=<id>  #pipe=druzhba-southern-leg  #at=lat,lng[,alt]  #note */
  function ensure(id) { var l = layers.find(function (x) { return x.id === id; }); if (l && !l.on) { l.on = true; renderLayers(); refresh(); } }
  function goTo(lat, lng, alt, then) { var n = $("note"); if (n) n.remove(); focus(lat, lng, alt); setTimeout(then, view === "globe" ? 1300 : 950); }
  function route() {
    var h = decodeURIComponent(location.hash.slice(1)); if (!h || !S) return;
    var k = h.split("=")[0], v = h.slice(k.length + 1), t;
    if (k === "note") return openNote();
    if (k === "brief") return openBrief();
    if (k === "catchup" || k === "lesson") {
      var best = v ? bestMatch(v) : STORIES.slice().sort(function (a, b) { return b.n - a.n; })[0];
      if (best) return k === "lesson" ? openLesson(best.id, best.t) : catchUp(best.id, best.t);
      return note('<span class="k" style="color:var(--quake)">NOTHING YET</span><span>No stored story matches "' + esc(v) + '". Try other words.</span>');
    }
    if (k === "quiz") return openQuiz();
    if (k === "solar") { setView("solar"); return; }
    if (k === "gov") { var gg = gov(); if (gg) gg.open(v || ""); return; }
    if (k === "merger") { setView("solar"); setTimeout(function () { solar().select("merger", ""); }, 150); return; }
    if (k === "archive") { setView("solar"); setTimeout(function () { solar().select("archive", v.toLowerCase()); }, 150); return; }
    if (k === "galaxy") { setView("solar"); setTimeout(function () { solar().select("galaxy", ""); }, 150); return; }
    if (k === "system") { setView("solar"); setTimeout(function () { solar().select("system", v.toLowerCase()); }, 150); return; }
    if (k === "planet" || k === "craft") { setView("solar"); setTimeout(function () { solar().select(k, v.toLowerCase()); }, 150); return; }
    if (k === "mine" && (t = MINES.find(function (m) { return slug(m[0]) === v; }))) { ensure("mines"); goTo(t[1], t[2], 0.9, function () { showMine(t); }); return; }
    if (k === "station" && (t = STATIONS.find(function (m) { return slug(m[0]) === v; }))) { ensure("stations"); goTo(t[1], t[2], 1.1, function () { showStation(t); }); return; }
    if (k === "sat") { var fs = satsShown(false).find(function (x) { return x.id === v; }); if (fs) { goTo(fs.lat, fs.lng, 2.2, function () { showSat(fs); }); } return; }
    if (k === "iss") { ensure("iss"); var ipos = issRec && issAt(new Date()); if (ipos) goTo(ipos.lat, ipos.lng, 1.6, showIss); return; }
    if (k === "storm" && (t = cyclones.find(function (c) { return c.id === v; }))) { ensure("cyclones"); goTo(t.lat, t.lng, 1.3, function () { showStorm(t); }); return; }
    if (k === "new") return openNewList();
    if (k === "calendar") return openCalendar();
    if (k === "choke" && (t = chokes.find(function (c) { return slug(c.name) === v; }))) { ensure("chokes"); goTo(t.lat, t.lng, 0.95, function () { showChoke(t); }); }
    else if (k === "ex" && (t = exchanges.find(function (x) { return x.name.toLowerCase() === v.toLowerCase(); }))) { ensure("markets"); goTo(t.lat, t.lng, 0.8, function () { showEx(t); }); }
    else if (k === "cb" && (t = banks.find(function (b) { return b.short.toLowerCase() === v.toLowerCase(); }))) { ensure("banks"); goTo(t.lat, t.lng, 0.8, function () { showBank(t); }); }
    else if (k === "pipe" && (t = pipes.find(function (p) { return slug(p.name) === v; }))) { ensure(t.kind); var mid = t.pts[Math.floor(t.pts.length / 2)]; goTo(mid[0], mid[1], 1.3, function () { showPipe(t); }); }
    else if (k === "event" && (t = EVENTS.find(function (e) { return e.id === v; }))) { ensure("events"); if (t.region && region !== t.region) pickRegion(t.region); setTimeout(function () { if (t.lat != null) goTo(t.lat, t.lng, 0.45, function () { showEvent(t); }); else showEvent(t); }, 300); }
    else if (k === "story" && (t = STORIES.find(function (e) { return e.id === v; }))) { if (t.lat != null) goTo(t.lat, t.lng, 1.2, function () { showStory(t); }); else showStory(t); }
    else if (k === "region" && regionOf(v)) pickRegion(v);
    else if (k === "country" && byName50[v]) { flyTo(v); setTimeout(function () { showCountry(v); }, 900); }
    else if (k === "ask") askMap(v);
    else if (k === "at") { var p = v.split(",").map(Number); if (p.length >= 2) { card.hidden = true; highlight = [{ lat: p[0], lng: p[1] }]; refresh(); focus(p[0], p[1], p[2] || 1); setTimeout(function () { highlight = []; refresh(); }, 8000); } }
    else if (k === "event" || k === "story") api("/api/item?id=" + encodeURIComponent(v)).then(function (it) {
      if (!it || !it.id) return note('<span class="k" style="color:var(--quake)">GONE</span><span>That report is no longer stored (Archie keeps 45 days).</span>');
      it.type = TYPEMAP[it.type] ? it.type : "politics"; it.unconfirmed = !it.confirmed; it.l = it.c = it.r = 0; it.o = it.src.length; it.topic = TOPIC[it.topic] ? it.topic : "politics";
      if (it.lat != null) goTo(it.lat, it.lng, 0.6, function () { k === "event" ? showEvent(it) : showStory(it); }); else (k === "event" ? showEvent(it) : showStory(it));
    });
  }
  window.addEventListener("hashchange", route);
  setInterval(function () { api("/api/nav").then(function (r) { if (r && r.hash) { if (location.hash === "#" + r.hash) route(); else location.hash = r.hash; } }).catch(function () { }); }, 1500);

  /* ============================ loading ============================ */
  var knownIds = null;
  function pull(first) {
    return api("/api/state?hours=72").then(function (d) {
      var fresh = [];
      if (knownIds) d.events.forEach(function (e) { if (!knownIds.has(e.id) && e.lat != null) fresh.push(e); });
      knownIds = new Set(d.events.map(function (e) { return e.id; }));
      ingest(d);
      fresh.slice(0, 6).forEach(function (e) { e.fresh = true; var ring = { lat: e.lat, lng: e.lng, hex: ET[e.type].col, max: 8, speed: 3, period: 700 }; liveRings.push(ring); setTimeout(function () { liveRings.splice(liveRings.indexOf(ring), 1); refresh(); }, 9000); });
      if (fresh.length && view !== "solar") { var e = fresh[0]; note('<span class="k" style="color:' + ET[e.type].col + '">● NEW · ' + esc(((regionOf(e.region) || {}).name || e.country || "WORLD").toUpperCase()) + "</span><span>" + esc(e.t) + "</span>"); $("toast").onclick = function () { openById(e.id); }; }
      if (!$("countryview").hidden && selCountry) { /* keep the open country as is */ } else { renderWar(); renderNews(); }
      issSetup(); SATG.forEach(function (g) { if (on("sat:" + g[0])) loadSats(g[0]); });
      renderLayers(); renderMarketsTab(); refresh(); briefBadge(); renderNewChip();
      if (first && location.hash.length > 1) setTimeout(route, 1200);
    });
  }
  Promise.all([fetch("/web/data/countries-110m.json").then(function (r) { return r.json(); }), fetch("/web/data/countries-50m.json").then(function (r) { return r.json(); })]).then(function (w) {
    W110 = w[0]; W50 = w[1];
    countries = topojson.feature(W110, W110.objects.countries).features;
    countries50 = topojson.feature(W50, W50.objects.countries).features.filter(function (f) { return f.properties.name !== "Antarctica"; });
    land50 = topojson.feature(W50, W50.objects.land);
    geoms50 = W50.objects.countries.geometries; nbIdx = topojson.neighbors(geoms50);
    countries50.forEach(function (f) { byName50[f.properties.name] = f; });
    makeGlobe(); renderLegend(); wake();
    return pull(true);
  }).then(function () {
    loadRadar();
    var loadCal = function () { api("/api/calendar").then(function (r) { S.cal = r.items; }).catch(function () { }); };
    loadCal(); setInterval(loadCal, 1800000);
    setInterval(function () { pull(false); }, 60000);
    setInterval(loadRadar, 300000);
    var tick = function () {   // your own time, like the taskbar; world time (UTC) on hover
      var d = new Date(), c = $("clock");
      c.textContent = d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
      c.title = d.toISOString().slice(11, 16) + " UTC (world time, used for news timestamps)";
    };
    setInterval(tick, 15000); tick();
  }).catch(function (e) { $("stamp").textContent = "couldn't load: " + e; });
  window.__archie = { catchUp: catchUp, openCalendar: openCalendar, explainIt: explainIt, openBrief: openBrief, radar: function () { return { frames: radarFrames.length, mesh: !!radarMesh, vis: radarMesh && radarMesh.visible, frame: radarFrame }; }, route: route, pickRegion: pickRegion, setView: setView, openNote: openNote, showCountry: showCountry, askMap: askMap, setTime: setTime, get G() { return G; } };
})();
