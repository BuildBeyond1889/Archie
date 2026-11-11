/* Archie Lite panel (v1.2). Everything here is drawn from the laptop's own copy (works offline);
   changes go to /api/change and reach the PC at the next sync.
   Tabs: Today (your day), Calendar, To-do, Notes (class notes + dropped files), Saved (readable offline),
   News (the full brief from your PC), Chat (questions wait here when the PC can't be reached). */
(function () {
  "use strict";
  var T = window.LITE_TOKEN, V = null, tab = "today", busy = false, syncing = false, lastHint = 0;
  var editing = null, reading = null, saveTimer = null, noteStatus = "";
  var $ = function (id) { return document.getElementById(id); };
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function api(path, body) {
    return fetch(path, body ? { method: "POST", headers: { "Content-Type": "application/json", "X-Lite-Token": T }, body: JSON.stringify(body) }
      : { headers: { "X-Lite-Token": T } }).then(function (r) { return r.json(); });
  }
  function ago(ts) {
    if (!ts) return "never"; var s = Math.max(0, Date.now() / 1000 - ts);
    if (s < 90) return "just now"; if (s < 5400) return Math.round(s / 60) + " min ago";
    if (s < 129600) return Math.round(s / 3600) + " h ago"; return Math.round(s / 86400) + " days ago";
  }
  function iso(d) { return d.getFullYear() + "-" + ("0" + (d.getMonth() + 1)).slice(-2) + "-" + ("0" + d.getDate()).slice(-2); }
  function dayLabel(s) { var d = new Date(s + "T12:00:00"); return d.toLocaleDateString([], { weekday: "short", month: "short", day: "numeric" }); }
  function clock(hm) { if (!hm) return ""; var p = hm.split(":"), d = new Date(); d.setHours(+p[0], +p[1] || 0); return d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }); }
  function daysTo(s) { var a = new Date(iso(new Date()) + "T12:00:00"), b = new Date(s + "T12:00:00"); return Math.round((b - a) / 86400000); }
  function home() { return V && V.status && V.status.state === "home"; }

  // personal calendar, weekly classes expanded
  function upcoming(days, from) {
    var out = [], today = new Date(iso(from || new Date()) + "T12:00:00"), end = new Date(today.getTime() + days * 86400000);
    (V.snapshot.calendar || []).forEach(function (e) {
      var d0 = new Date(e.date + "T12:00:00");
      if (e.repeat === "weekly") {
        var until = e.until ? new Date(e.until + "T12:00:00") : end, d = new Date(d0);
        while (d < today) d = new Date(d.getTime() + 7 * 86400000);
        for (; d <= end && d <= until; d = new Date(d.getTime() + 7 * 86400000)) out.push({ e: e, date: iso(d) });
      } else if (d0 >= today && d0 <= end) out.push({ e: e, date: e.date });
    });
    return out.sort(function (a, b) { return (a.date + (a.e.time || "99")).localeCompare(b.date + (b.e.time || "99")); });
  }

  // tiny markdown for notes and saved articles
  function md(src) {
    var out = [], list = false;
    String(src || "").replace(/\r/g, "").split("\n").forEach(function (line) {
      if (/^---\s*$/.test(line) || /^!\[\[.*\]\]\s*$/.test(line)) return;
      var h = line.match(/^(#{1,4})\s+(.*)/), li = line.match(/^\s*[-*]\s+(.*)/);
      if (li) { if (!list) { out.push("<ul>"); list = true; } out.push("<li>" + inline(li[1]) + "</li>"); return; }
      if (list) { out.push("</ul>"); list = false; }
      if (h) out.push("<h" + (h[1].length + 1) + ">" + inline(h[2]) + "</h" + (h[1].length + 1) + ">");
      else if (line.trim()) out.push("<p>" + inline(line) + "</p>");
    });
    if (list) out.push("</ul>");
    return out.join("");
  }
  function inline(s) {
    return esc(s).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/\[\[([^\]|]+)(?:\|([^\]]+))?\]\]/g, function (_, a, b) { return "<i>" + (b || a) + "</i>"; })
      .replace(/\[([^\]]+)\]\((https?:[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')
      .replace(/(^|\s)(https?:\/\/[^\s<]+)/g, '$1<a href="$2" target="_blank" rel="noopener">$2</a>');
  }

  function syncLine() {
    var st = V.status || {}, el = $("sync"), n = V.pending;
    el.className = "sync " + (st.state === "home" ? (n ? "wait" : "home") : st.state === "away" ? "away" : "");
    var t;
    if (!V.paired) t = "not paired with your PC yet";
    else if (st.state === "home") t = "synced with " + (st.pc || "your PC") + " · " + ago(V.last_ok) + (n ? " · " + n + " sending" : "");
    else if (st.state === "away") t = "can't reach your PC" + (n ? " · " + n + " waiting" : "") + " · last sync " + ago(V.last_ok);
    else t = "looking for your PC…";
    if (V.battery) t += " · battery";
    $("synctext").textContent = t;
    $("owlbtn").classList.toggle("off", !!V.owl_hidden);
    el.title = st.msg || "";
    $("ask").placeholder = home() ? "Ask Archie… (uses your PC)" : "Ask Archie… (answered when your PC is reachable)";
  }

  function takeHtml(t) {                       // the brief's "- a - b - c" as one line each
    t = String(t || "").trim();
    if (!/^-\s/.test(t)) return esc(t);
    return t.replace(/^-\s+/, "").split(/\s+-\s+(?=\S)/).map(function (x) { return '<div class="tk">' + esc(x) + "</div>"; }).join("");
  }
  function storyRow(s, i) {
    var src = (s.src && s.src[0]) || {}, meta = [s.n + (s.n === 1 ? " outlet" : " outlets"), s.place || "", ago(s.last)].filter(Boolean).join(" · ");
    return '<div class="story"><div class="t">' + esc(s.t) + '</div><div class="m">' + esc(meta) + "</div>" +
      '<div class="a"><button data-save="' + i + '">save</button>' + (src.url ? '<a href="' + esc(src.url) + '" target="_blank" rel="noopener">read ↗</a>' : "") + "</div></div>";
  }
  function whenRow(date, e, extra) {
    return '<div class="when"><span class="d">' + (date ? dayLabel(date) : clock(e.time) || "all day") + '</span><span class="w">' + esc(e.title) +
      (date && e.time ? " · " + clock(e.time) : "") + '</span><span class="k">' + esc(extra || e.kind || "") + "</span></div>";
  }
  // ----- recording a lecture on this laptop --------------------------------------------------------------
  // Edge records; every 10 s a piece goes to Archie Lite, which keeps it on disk. Hide the panel and it keeps
  // going (the owl gets a red bubble). Stop joins the pieces and sends the recording like a dropped file.
  var R = null;               // { id, mr, stream, ctx, an, level, q: [pieces], i, sending, started, acc, since, paused }
  function recElapsed() { if (!R) return V && V.rec ? V.rec.elapsed : 0; return (R.acc + (R.paused ? 0 : Date.now() - R.since)) / 1000; }
  function hms(t) { t = Math.max(0, Math.floor(t)); var h = Math.floor(t / 3600), m = Math.floor(t % 3600 / 60), s = t % 60;
    return (h ? h + ":" + ("0" + m).slice(-2) : m) + ":" + ("0" + s).slice(-2); }
  function classOptions(sel, none) {
    var classes = (V.classes || []).slice(); if (sel && classes.indexOf(sel) < 0) classes.push(sel);
    return '<option value="">' + none + "</option>" + classes.map(function (c) { return "<option" + (c === sel ? " selected" : "") + ">" + esc(c) + "</option>"; }).join("");
  }
  function fileUnder() {
    var pick = V.drop_pick, cur = V.klass ? V.klass.title : "";
    return '<label class="l fileunder">File under<select id="dropklass">' + classOptions(V.drop_klass || "", "no class (Archie Lite)") + "</select>" +
      '<span class="sub">' + (pick ? "picked for today" + (cur && cur !== (pick.klass || "") ? " · class on now: " + esc(cur) : "") + ' · <button class="link" data-dropauto="1">use the class on now</button>'
        : cur ? "the class on now" : "no class on now; pick one to file things under it today") + "</span></label>";
  }
  function recCard() {
    var live = V.rec;
    if (R || live) {
      var who = (R ? R.klass : live.klass) || "no class", paused = R ? R.paused : live.paused;
      return '<div class="reccard on"><div class="rtop"><span class="rdot' + (paused ? " p" : "") + '"></span><b id="rectime">' + hms(recElapsed()) + "</b>" +
        '<span class="sub">' + (paused ? "paused" : "recording") + " · " + esc(who) + "</span></div>" +
        (R ? '<div class="level"><i id="reclevel"></i></div>' : '<p class="note">This panel was closed while recording, so the microphone stopped. Everything up to then is kept.</p><div class="row rbtns"><button class="btn stop" data-rec="stop">save what was recorded</button></div>') +
        (R ? '<div class="row rbtns"><button class="btn ghost" data-rec="mark">mark</button><button class="btn ghost" data-rec="pause">' + (paused ? "resume" : "pause") + '</button><button class="btn stop" data-rec="stop">stop</button></div>' +
          '<form id="markform" class="row" hidden><input id="marktext" placeholder="what was that? (optional)" autocomplete="off"><button class="btn ghost">mark</button></form>' : "") +
        '<p class="note">Hide this panel and keep working: it keeps recording, and the owl shows a red bubble with the time. Stop keeps it here; nothing is sent until you press send.' + (R && R.marks ? " " + R.marks + " mark" + (R.marks === 1 ? "" : "s") + " so far." : "") + "</p></div>" + draftCards();
    }
    if ((V.drafts || []).length) return draftCards();
    return '<div class="reccard"><div class="row"><div><div class="h">Record a lecture</div><div class="sub">filed under <b>' + esc(V.drop_klass || "no class") + "</b> (change it below; drops use it too) · the laptop's microphone</div></div>" +
      '<button class="btn rec" data-rec="start"><span class="rdot"></span>record</button></div></div>';
  }
  function draftCards() {                   // stopped recordings waiting for send: name them, pick the class
    return (V.drafts || []).map(function (d) {
      var when = new Date(d.started * 1000).toLocaleString([], { weekday: "short", month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
      return '<form class="reccard draft" data-draft="' + esc(d.id) + '" onsubmit="return false"><div class="h neonish">Ready to send</div>' +
        '<div class="sub">recorded ' + esc(when) + " · " + hms(d.duration) + (d.marks ? " · " + d.marks + " mark" + (d.marks === 1 ? "" : "s") : "") + (d.why ? " · " + esc(d.why) : "") + "</div>" +
        '<div class="f"><label class="l">Name (optional)<input data-dlabel="' + esc(d.id) + '" value="' + esc(d.label || "") + '" placeholder="e.g. Lecture 9 · enzymes"></label>' +
        '<label class="l" style="flex:0 0 220px">Class<select data-dklass="' + esc(d.id) + '">' + classOptions(d.klass || "", "no class (Voice inbox)") + "</select></label></div>" +
        '<div class="sub" data-dname="' + esc(d.id) + '">' + esc(d.name) + "</div>" +
        '<div class="row rbtns"><button type="button" class="btn ghost" data-dnote="' + esc(d.id) + '">write a note for it</button><button type="button" class="btn send" data-dsend="' + esc(d.id) + '">send</button>' +
        '<button type="button" class="link danger" data-ddiscard="' + esc(d.id) + '">discard</button></div></form>';
    }).join("");
  }
  function recStart() {
    if (!navigator.mediaDevices || !window.MediaRecorder) return alertLine("This window can't record audio.");
    var klass = V.drop_klass || "";
    navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: true } }).then(function (stream) {
      return api("/api/rec/start", { klass: klass }).then(function (r) {
        if (!r.ok) { stream.getTracks().forEach(function (t) { t.stop(); }); return alertLine(r.error || "couldn't start"); }
        var type = MediaRecorder.isTypeSupported("audio/webm;codecs=opus") ? "audio/webm;codecs=opus" : "";
        var mr = new MediaRecorder(stream, type ? { mimeType: type, audioBitsPerSecond: 48000 } : undefined);
        var me = R = { id: r.rec.id, klass: r.rec.klass, mr: mr, stream: stream, q: [], i: 0, sending: false, acc: 0, since: Date.now(), paused: false, marks: 0 };
        mr.ondataavailable = function (e) { if (e.data && e.data.size) { me.q.push({ i: me.i++, blob: e.data }); sendPieces(me); } };
        mr.start(10000);
        try { var ctx = new AudioContext(), an = ctx.createAnalyser(); an.fftSize = 512; ctx.createMediaStreamSource(stream).connect(an); R.ctx = ctx; R.an = an; } catch (e) {}
        V.rec = r.rec; draw(); recTick();
      });
    }).catch(function (e) { alertLine(e && e.name === "NotAllowedError" ? "Allow the microphone for Archie Lite (the icon at the right of the address bar), then press record again." : "Couldn't use the microphone: " + (e.message || e)); });
  }
  function sendPieces(me) {
    if (!me || me.sending || !me.q.length) return;
    var p = me.q[0]; me.sending = true;
    fetch("/api/rec/piece", { method: "POST", headers: { "X-Lite-Token": T, "X-Rec": me.id, "X-I": String(p.i) }, body: p.blob })
      .then(function (r) { return r.json(); }).then(function (r) { if (r.ok) me.q.shift(); else if (/ended/.test(r.error || "")) me.q = []; })
      .catch(function () {}).then(function () { me.sending = false; if (me.q.length) setTimeout(function () { sendPieces(me); }, 300); else if (me.after && me.stopped) { var f = me.after; me.after = null; f(); } });
  }
  function recStop() {
    if (!R) return api("/api/rec/stop", { id: V.rec && V.rec.id }).then(poll);
    var me = R, el = recElapsed();
    me.after = function () { api("/api/rec/stop", { id: me.id, elapsed: el }).then(function (r) { if (!r.ok) alertLine(r.error); poll(); }); };
    me.mr.onstop = function () {                 // the last piece arrives just before this
      me.stopped = true; me.stream.getTracks().forEach(function (t) { t.stop(); }); try { me.ctx && me.ctx.close(); } catch (e) {}
      if (!me.sending && !me.q.length && me.after) { var f = me.after; me.after = null; f(); } else sendPieces(me); };
    me.mr.stop(); R = null; V.rec = null; draw(); alertLine("Stopped. Name it and pick the class, then press send.");
  }
  function recPause() {
    if (!R) return;
    if (R.paused) { R.mr.resume(); R.since = Date.now(); R.paused = false; } else { R.mr.pause(); R.acc += Date.now() - R.since; R.paused = true; }
    api("/api/rec/set", { id: R.id, paused: R.paused, elapsed: recElapsed() }); draw();
  }
  function recMark(label) { if (!R) return; R.marks++; api("/api/rec/set", { id: R.id, mark: { t: recElapsed(), label: label || "" } }); alertLine("Marked " + hms(recElapsed())); draw(); }
  function recTick() {
    var on = !!(R || (V && V.rec)), bar = $("recbar");
    bar.hidden = !on;
    if (on) { $("rectext").textContent = (R && R.paused || (!R && V.rec.paused) ? "paused · " : "recording · ") + hms(recElapsed()) + " · " + ((R ? R.klass : V.rec.klass) || "no class"); }
    var t = $("rectime"); if (t) t.textContent = hms(recElapsed());
    var lv = $("reclevel"); if (lv && R && R.an) { var a = new Uint8Array(R.an.fftSize); R.an.getByteTimeDomainData(a); var m = 0; for (var i = 0; i < a.length; i++) m = Math.max(m, Math.abs(a[i] - 128)); lv.style.width = Math.min(100, m * 1.6) + "%"; }
  }
  setInterval(recTick, 250);
  window.addEventListener("beforeunload", function (e) { if (R) { e.preventDefault(); e.returnValue = "Still recording"; } });

  function classCard() {
    var k = V.klass;
    if (!k) return "";
    return '<div class="now"><div><div class="h" style="color:var(--blue)">' + (k.kind === "lab" ? "Lab" : "Class") + " now</div>" +
      '<div class="nt">' + esc(k.title) + '</div><div class="sub">until ' + clock(k.until) + " · files you drop now are filed under it</div></div>" +
      '<button class="btn" data-newnote="1">take notes</button></div>';
  }

  var NW = { sub: "brief", region: "", news: null, govs: null, iso: "", country: null, q: "" };
  function loadNews() {
    return api("/api/world/news?region=" + encodeURIComponent(NW.region)).then(function (d) {
      NW.news = d; if (tab === "news") draw();
      if (d.state === "pulling") setTimeout(loadNews, 2500);
    }).catch(function () {});
  }
  function loadGovs() { return api("/api/world/govs").then(function (g) { NW.govs = g; if (tab === "news" && NW.sub === "govs") draw(); }); }
  function loadCountry(iso) {
    NW.iso = iso; NW.country = null; draw();
    api("/api/world/country?iso=" + encodeURIComponent(iso)).then(function (c) { if (NW.iso === iso) { NW.country = c; draw(); } });
  }
  function flagImg(iso, h) { return iso ? '<img class="flag" style="height:' + h + 'px" src="/api/flag/' + esc(iso) + "?t=" + encodeURIComponent(T) + '" alt="" onerror="this.style.visibility=\'hidden\'">' : ""; }
  function wstory(s) {
    window._wstories.push(s);
    var it = s.items || [], i = window._wstories.length - 1;
    return '<div class="story"><div class="t">' + esc(s.title) + '</div><div class="m">' + esc([s.n + (s.n === 1 ? " source" : " sources"), s.place || "", (s.last || s.t) ? ago(s.last || s.t) : ""].filter(Boolean).join(" · ")) + "</div>" +
      (it[0] && it[0].summary && it[0].summary !== s.title ? '<div class="sum">' + esc(it[0].summary.slice(0, 240)) + "</div>" : "") +
      '<div class="a">' + it.slice(0, 5).map(function (x) { return x.url ? '<a href="' + esc(x.url) + '" target="_blank" rel="noopener">' + esc(x.source || "read") + " ↗</a>" : "<span>" + esc(x.source) + "</span>"; }).join("") +
      (it[0] && it[0].url ? '<button data-wsave="' + i + '">save</button>' : "") + "</div></div>";
  }
  function briefView() {
    var b = V.snapshot.brief || {}, take = b.take || {}, ed = b.edition, h = "";
    h += '<div class="sub">' + (b.global ? (ed ? (ed.kind === "update" ? "updated " : "edition ") + new Date(ed.at * 1000).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }) + " · from your PC · readable offline" : "live from your PC") : "no brief yet; it comes with the first sync") + "</div>";
    if (take.world) h += '<div><div class="h neon">The world</div><div class="take">' + takeHtml(take.world) + "</div></div>";
    if (take.home) h += '<div><div class="h neon">At home</div><div class="take">' + takeHtml(take.home) + "</div></div>";
    window._stories = [];
    [["Around the world", b.global], ["At home · United States", b.home], ["Close to home", b.local]].forEach(function (sec) {
      if (!sec[1] || !sec[1].length) return;
      h += '<div><div class="h neon">' + sec[0] + "</div>" + sec[1].map(function (s) { window._stories.push(s); return storyRow(s, window._stories.length - 1); }).join("") + "</div>";
    });
    var world = (b.coming || []).slice(0, 8);
    if (world.length) h += '<div><div class="h neon">Coming up in the world</div><div class="col">' + world.map(function (i) { var dd = i.time ? new Date(i.time * 1000) : new Date(i.date + "T12:00:00"); return '<div class="when"><span class="d">' + dd.toLocaleDateString([], { weekday: "short", month: "short", day: "numeric" }) + '</span><span class="w">' + esc(i.title) + '</span><span class="k">' + esc(i.kind) + "</span></div>"; }).join("") + "</div></div>";
    return h;
  }
  function govView() {
    var g = NW.govs;
    if (!g) return '<p class="note">Loading…</p>';
    if (!g.list.length) return '<p class="note">The governments come from your PC with the next sync (Archie World has to be running).</p>';
    var f = NW.q.toLowerCase(), list = g.list.filter(function (c) { return !f || (c.name + " " + (c.leaders || "")).toLowerCase().indexOf(f) >= 0; });
    var c = NW.country, names = function (L) { return (L || []).map(function (p) { return esc(p.name) + (p.since ? ' <span class="dim">since ' + esc(String(p.since).slice(0, 7)) + "</span>" : ""); }).join("<br>") || '<span class="dim">unknown</span>'; };
    var detail = !NW.iso ? '<p class="note" style="padding-top:40px">Pick a country, or search a leader’s name.</p>' : !c ? '<p class="note">Loading…</p>' : c.error ? '<p class="note">Not in the snapshot.</p>' :
      '<div class="row" style="justify-content:flex-start;gap:14px">' + flagImg(c.iso2, 38) + '<div><h1>' + esc(c.name) + '</h1><div class="sub">' + esc(c.label || "") + (c.capital ? " · capital " + esc(c.capital) : "") + "</div></div></div>" +
      '<div class="pair"><div class="card"><div class="h">' + esc(c.hosOffice || "Head of state") + '</div><div class="big">' + names(c.hos) + '</div></div><div class="card"><div class="h">' + esc(c.hogOffice || "Head of government") + '</div><div class="big">' + names(c.hog) + "</div></div></div>" +
      (c.cabinet || []).map(function (gr) { return '<div class="card"><div class="h">' + esc(gr.label || "Cabinet") + "</div>" + (gr.people || []).map(function (p) { return '<div class="cab"><span class="dim">' + esc(p.title || "") + "</span><span>" + esc(p.name || "") + "</span></div>"; }).join("") + "</div>"; }).join("") +
      (c.cabinet_source ? '<div class="sub">Cabinet: ' + esc(c.cabinet_source) + (c.cabinet_updated ? ", updated " + esc(c.cabinet_updated) : "") + ". Leaders: Wikidata.</div>" : "") +
      (c.intro ? '<div class="card"><div class="h">Background</div><div class="intro">' + esc(c.intro).replace(/\n\n/g, "<br><br>") + "</div></div>" : "");
    return '<div class="govs"><div class="glist"><form id="govform" onsubmit="return false"><input id="gq" placeholder="search countries or leaders" value="' + esc(NW.q) + '" aria-label="Search countries or leaders"></form>' +
      '<div class="gl" id="gl">' + list.map(function (x) { return '<button class="gitem' + (x.iso2 === NW.iso ? " on" : "") + '" data-iso="' + esc(x.iso2) + '">' + flagImg(x.iso2, 13) + "<span>" + esc(x.name) + "</span></button>"; }).join("") + "</div>" +
      '<div class="sub">' + (g.at ? "as of " + new Date(g.at * 1000).toLocaleDateString() : "") + " · readable offline</div></div><div class=\"gdetail col\">" + detail + "</div></div>";
  }

  var views = {
    today: function () {
      var S = V.snapshot, b = S.brief || {}, h = "", st = V.status || {}, today = iso(new Date());
      if (!V.paired) h += '<div class="warn"><b>Not paired yet.</b> Run the installer from the stick again, or copy <code>pairing.json</code> from the PC.</div>';
      else if (st.state !== "home" && st.msg && !V.last_ok) h += '<div class="warn">' + esc(st.msg) + "</div>";
      var d = new Date(), hr = d.getHours();
      h += "<div><h1>" + (hr < 12 ? "Good morning" : hr < 18 ? "Good afternoon" : "Good evening") + '</h1><div class="sub">' +
        d.toLocaleDateString([], { weekday: "long", month: "long", day: "numeric" }) + "</div></div>";
      h += classCard();
      var next = (S.deadlines || []).filter(function (x) { return daysTo(x.date) >= 0; })[0];
      if (next) { var n = daysTo(next.date); h += '<div class="count"><span>' + esc(next.what) + "</span><b>" + (n === 0 ? "today" : n === 1 ? "tomorrow" : n + " days") + "</b></div>"; }
      var todays = upcoming(0);
      h += '<div><div class="h">Today</div><div class="col">' + (todays.length ? todays.map(function (x) { return whenRow(null, x.e); }).join("") :
        '<p class="note">Nothing on the calendar today.</p>') + "</div></div>";
      var dueT = (S.tasks || []).filter(function (t) { return !t.done && t.due && t.due <= today; }),
        dls = (S.deadlines || []).filter(function (x) { var n = daysTo(x.date); return n >= 0 && n <= 1; });
      if (dueT.length || dls.length) h += '<div><div class="h">Due</div>' + dls.map(function (x) { return '<div class="when"><span class="d">' + (daysTo(x.date) ? "tomorrow" : "today") + '</span><span class="w">' + esc(x.what) + "</span></div>"; }).join("") + dueT.map(taskRow).join("") + "</div>";
      var open = (S.tasks || []).filter(function (t) { return !t.done && !(t.due && t.due <= today); }).slice(0, 8);
      if (open.length) h += '<div><div class="h">To-do</div>' + open.map(taskRow).join("") + "</div>";
      var soon = upcoming(7, new Date(Date.now() + 86400000)).slice(0, 6);
      if (soon.length) h += '<div><div class="h">This week</div><div class="col">' + soon.map(function (x) { return whenRow(x.date, x.e); }).join("") + "</div></div>";
      var nStories = (b.global || []).length + (b.home || []).length + (b.local || []).length;
      if (nStories) h += '<button class="teaser" data-tab="news"><span class="h" style="margin:0">News</span><span>' + nStories + " stories" +
        (b.edition && b.edition.at ? " · " + new Date(b.edition.at * 1000).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }) : "") + "</span><b>→</b></button>";
      return h;
    },
    news: function () {
      var subs = [["brief", "Brief"], ["live", "Live"], ["all", "All stories"], ["govs", "Governments"]], d = NW.news;
      var status = d ? (d.state === "pulling" ? '<span class="spin"></span> pulling the feeds…' : d.live_at && !d.ok ? "couldn't reach the news feeds: is this laptop online?" :
        d.live_at ? "live " + ago(d.live_at) + " · " + d.ok + " feeds" + (d.failed ? ", " + d.failed + " didn't answer" : "") : d.has_sources ? "refresh pulls the news live, from this laptop" : "the feed list comes with the next sync") : "";
      var h = '<div class="row"><h1>News</h1><div class="wbar"><span class="sub">' + status + '</span><button class="btn" id="wrf"' + (d && d.state === "pulling" ? " disabled" : "") + ">refresh</button></div></div>" +
        '<div class="seg" role="tablist">' + subs.map(function (x) { return '<button role="tab" data-sub="' + x[0] + '" aria-selected="' + (NW.sub === x[0]) + '">' + x[1] + "</button>"; }).join("") + "</div>";
      if (NW.sub === "brief") return h + briefView();
      if (NW.sub === "govs") return h + govView();
      if (!d) return h + '<p class="note">Loading…</p>';
      window._wstories = [];
      if (NW.sub === "live") return h + (d.live.length ? '<div class="col">' + d.live.slice(0, 40).map(wstory).join("") + "</div>" :
        '<p class="note">' + (d.state === "pulling" ? "Pulling the feeds…" : "Press refresh to pull the news live, straight from the outlets. Works anywhere with internet.") + "</p>");
      return h + '<div class="row"><div class="sub">from your PC · ' + (d.pc_at ? "as of " + new Date(d.pc_at * 1000).toLocaleString([], { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }) : "comes with the next sync") +
        ' · last 3 days</div><select id="rg" aria-label="Region"><option value="">all regions</option>' + d.regions.map(function (r) { return "<option" + (r === NW.region ? " selected" : "") + ">" + esc(r) + "</option>"; }).join("") + "</select></div>" +
        '<div class="col">' + (d.pc.map(wstory).join("") || '<p class="note">Nothing here yet.</p>') + "</div>";
    },
    cal: function () {
      var list = upcoming(45), kinds = ["event", "class", "lab", "exam", "test", "quiz", "due"];
      return "<h1>Calendar</h1>" +
        '<form id="calform"><div class="f"><label class="l">What<input name="title" required placeholder="Apartment viewing"></label></div>' +
        '<div class="f"><label class="l">Date<input name="date" type="date" required value="' + iso(new Date()) + '"></label><label class="l">Time<input name="time" type="time"></label></div>' +
        '<div class="f"><label class="l">Kind<select name="kind">' + kinds.map(function (k) { return "<option>" + k + "</option>"; }).join("") + '</select></label><label class="l">Repeats<select name="repeat"><option value="">no</option><option value="weekly">every week</option></select></label></div>' +
        '<button class="btn">add to calendar</button></form>' +
        '<div class="col"><div class="h">Next 45 days</div>' +
        (list.length ? list.map(function (x) { return '<div class="when"><span class="d">' + dayLabel(x.date) + '</span><span class="w">' + esc(x.e.title) + (x.e.time ? " · " + clock(x.e.time) : "") + '</span><span class="k">' + esc(x.e.kind) + (x.e.repeat ? " · weekly" : "") + '</span><button data-del="' + esc(x.e.id) + '" aria-label="Delete ' + esc(x.e.title) + '">✕</button></div>'; }).join("") : '<p class="note">Nothing in the next 45 days.</p>') +
        '</div><p class="note">Tip: Ctrl+Alt+Space adds from anywhere, e.g. "dentist fri 3pm".</p>';
    },
    todo: function () {
      var S = V.snapshot, tasks = S.tasks || [];
      return "<h1>To-do</h1>" +
        '<div>' + (tasks.length ? tasks.filter(function (t) { return !t.done; }).concat(tasks.filter(function (t) { return t.done; }).slice(-5)).map(taskRow).join("") : '<p class="note">No tasks.</p>') + "</div>" +
        '<form id="taskform"><div class="f"><label class="l">New task<input name="text" required placeholder="finish python project"></label><label class="l" style="flex:0 0 150px">Due<input name="due" type="date"></label></div><button class="btn">add task</button></form>' +
        '<div><div class="h">Deadlines</div>' + (S.deadlines || []).filter(function (x) { return daysTo(x.date) >= 0; }).map(function (x) { return '<div class="when"><span class="d">' + dayLabel(x.date) + '</span><span class="w">' + esc(x.what) + '</span><span class="k">' + daysTo(x.date) + " days</span></div>"; }).join("") + "</div>" +
        '<form id="dlform"><div class="f"><label class="l">New deadline<input name="what" required placeholder="portfolio due"></label><label class="l" style="flex:0 0 150px">Date<input name="date" type="date" required></label></div><button class="btn">add deadline</button></form>';
    },
    notes: function () {
      if (editing) return noteEditor();
      var notes = V.notes || [], waiting = V.pending_notes || [], h = "<div class=\"row\"><h1>Notes</h1><button class=\"btn\" data-newnote=\"1\">+ new note</button></div>";
      h += classCard() + recCard() + fileUnder();
      h += '<div class="col">' + (notes.length ? notes.slice(0, 40).map(function (n) {
        var prev = String(n.text || "").replace(/\s+/g, " ").slice(0, 110);
        return '<div class="noteline"><button class="noterow" data-open="' + esc(n.nid) + '"><span class="t">' + esc(n.title) + '</span><span class="m">' +
          esc([n.klass || "no class", dayLabel(n.date), waiting.indexOf(n.nid) >= 0 ? "sending" : "in Obsidian"].join(" · ")) +
          "</span>" + (prev ? '<span class="p">' + esc(prev) + "</span>" : "") + "</button>" +
          (waiting.indexOf(n.nid) >= 0 ? "" : '<button class="notex" data-nhide="' + esc(n.nid) + '" title="Take off this list (Obsidian keeps it)" aria-label="Take ' + esc(n.title) + ' off this list">×</button>') + "</div>";
      }).join("") : '<p class="note">No notes yet. During a class, <b>take notes</b> files them under that class in Obsidian (Lectures).</p>') + "</div>";
      var drops = V.drops || [];
      h += '<div><div class="row"><div class="h">Files</div><button class="link" data-openfolder="1">open folder ↗</button></div>' +
        '<div class="dropzone">Drop files here or on the owl. They\'re kept on this laptop and sent to Obsidian, filed under the class above. Slides, PDFs, handouts and photos of pages go into that class\'s lecture review.</div>' +
        (drops.length ? drops.slice(0, 25).map(function (f) {
          var st = f.state === "sending" ? "sending " + Math.round(100 * (f.done || 0) / (f.n || 1)) + "%" : f.ok === false ? "not sent: " + (f.note || "?") : (f.note || "in Obsidian");
          return '<div class="when"><span class="w">' + esc(f.name) + '</span><span class="k">' + esc((f.klass ? f.klass + " · " : "") + st) + "</span>" +
            (f.local ? '<button data-openfile="' + esc(f.local) + '" aria-label="Open ' + esc(f.name) + '">open</button>' : "") + "</div>";
        }).join("") : "") + "</div>";
      return h;
    },
    saved: function () {
      var S = V.snapshot, have = V.articles || [];
      if (reading) return '<button class="link" data-back="1">← saved articles</button><article class="reader">' + (reading.text ? md(reading.text) : '<p class="note">Loading…</p>') + "</article>";
      return "<h1>Saved articles</h1><div>" + ((S.saved || []).length ? S.saved.slice(0, 40).map(function (s) {
        var off = s.md && have.indexOf(s.md) >= 0;
        return '<div class="story' + (off ? " openable" : "") + '"' + (off ? ' data-read="' + esc(s.md) + '" role="button" tabindex="0"' : "") + '><div class="t">' + esc(String(s.name).replace(/^\d{4}-\d\d-\d\d - /, "")) + '</div><div class="m">' +
          (s.pending ? "saving on your PC at the next sync" : "saved " + new Date(s.time * 1000).toLocaleDateString([], { month: "short", day: "numeric" }) + (off ? " · tap to read (offline)" : " · text comes with the next sync")) + "</div></div>";
      }).join("") : '<p class="note">Nothing saved yet. Use save on any story in News, or paste a link in quick add (Ctrl+Alt+Space).</p>') + "</div>" +
        '<div><div class="h">Following</div><div class="chips">' + (S.follow || []).map(function (f, i) { return '<span class="chip">' + esc(f) + '<button data-unfollow="' + i + '" aria-label="Stop following ' + esc(f) + '">✕</button></span>'; }).join("") + "</div></div>" +
        '<form id="followform"><div class="f"><label class="l">Follow a topic<input name="topic" required placeholder="SpaceX, game studios"></label></div><button class="btn">follow</button></form>';
    },
    chat: function () {
      var chat = V.chat || [], h = '<div class="row"><h1>Ask Archie</h1>' + (chat.length ? '<button class="link" data-clearchat="1">clear</button>' : "") + "</div>";
      if (!home()) h += '<div class="warn">Your PC can\'t be reached right now. Ask anyway: questions wait here and get answered at the next sync (you\'ll get a pop-up).</div>';
      h += '<div class="col" style="gap:10px">' + chat.map(function (m) {
        return '<div class="msg ' + (m.role === "user" ? "me" : "ai") + '">' + esc(m.text) + (m.queued ? '<span class="q">waiting for your PC</span>' : "") + "</div>";
      }).join("") + (busy ? '<div class="thinking">Archie is thinking on ' + esc((V.status && V.status.pc) || "your PC") + "…</div>" : "") + "</div>";
      if (chat.length && V.snapshot.model) h += '<div class="sub">answered by ' + esc(V.snapshot.model) + " on " + esc((V.status && V.status.pc) || "your PC") + "</div>";
      return h;
    }
  };
  function taskRow(t) {
    return '<label class="check' + (t.done ? " done" : "") + '"><input type="checkbox" data-task="' + esc(t.text) + '"' + (t.done ? " checked" : "") + "><span>" + esc(t.text) + "</span>" +
      (t.due ? '<span class="due">' + dayLabel(t.due) + "</span>" : "") + "</label>";
  }
  function noteEditor() {
    var n = editing, classes = V.classes || [];
    if (n.klass && classes.indexOf(n.klass) < 0) classes = classes.concat([n.klass]);
    return '<button class="link" data-back="1">← all notes</button>' +
      '<form id="noteform" class="editor"><input name="title" class="ntitle" placeholder="Title" value="' + esc(n.title) + '" aria-label="Title">' +
      '<div class="f"><label class="l">Class<select name="klass"><option value="">no class</option>' + classes.map(function (c) { return "<option" + (c === n.klass ? " selected" : "") + ">" + esc(c) + "</option>"; }).join("") +
      '</select></label><label class="l" style="flex:0 0 160px">Date<input name="date" type="date" value="' + esc(n.date) + '"></label></div>' +
      '<textarea name="text" placeholder="Type your notes. They save as you type, on this laptop, and go to Obsidian on your PC." aria-label="Notes">' + esc(n.text) + "</textarea>" +
      '<div class="sub" id="notestatus">' + esc(noteStatus || (n.nid ? "saved on this laptop" : "new note")) + "</div></form>";
  }

  // ----- inbox cards: a dropped file waits here: name, what it is, which class, then Save (sent to the PC) -----------
  var CS = {};                                   // per staged file: { name, kind, klass } as picked on its card
  function mb(n) { return n >= 1048576 ? (n / 1048576).toFixed(1) + " MB" : Math.max(1, Math.round(n / 1024)) + " KB"; }
  function splitName(n) { var i = n.lastIndexOf("."); return i > 0 ? [n.slice(0, i), n.slice(i)] : [n, ""]; }
  function destFor(kind, klass) {
    if (kind === "idea") return "Ideas";
    if (!klass) return kind === "recording" ? "Archie Lite/Voice inbox" : "Archie Inbox";
    var c = "Lectures/" + klass;
    return /slides|reading|syllabus/.test(kind) ? c + "/Materials" : kind === "assignment" ? c + "/Assignments"
      : kind === "recording" || kind === "my notes" ? c : c + "/Files";
  }
  function icards() {
    var list = V.staged || [];
    if (!list.length) return "";
    return list.map(function (x) {
      var c = CS[x.id] || (CS[x.id] = { name: splitName(x.name)[0], kind: x.kind, klass: x.klass || "" }), ext = splitName(x.name)[1];
      var classes = (V.classes || []).slice(); if (c.klass && classes.indexOf(c.klass) < 0) classes.unshift(c.klass);
      var big = x.size > (V.big || 52428800);
      return '<form class="icard" data-card="' + esc(x.id) + '" onsubmit="return false">' +
        '<div class="ih">' + esc(x.name) + '<span class="sub"> · ' + mb(x.size) + "</span></div>" +
        (x.dup ? '<div class="iwarn">⚠ already sent from this laptop: ' + esc(x.dup) + "</div>" : "") +
        (big ? '<div class="iwarn">⚠ ' + mb(x.size) + ": a big one. It goes to the PC the next time this laptop syncs.</div>" : "") +
        '<label class="l">Name<span class="iname"><input data-iname="' + esc(x.id) + '" value="' + esc(c.name) + '"><b>' + esc(ext) + "</b></span></label>" +
        '<div class="il">WHAT IS IT</div><div class="ichips">' + (V.kinds || []).map(function (k) {
          return '<button type="button" class="ichip' + (k === c.kind ? " on" : "") + '" data-ikind="' + esc(x.id) + "|" + esc(k) + '">' + esc(k) + "</button>"; }).join("") + "</div>" +
        '<div class="il">CLASS</div><div class="ichips">' + classes.concat([""]).map(function (k) {
          return '<button type="button" class="ichip' + (k === c.klass ? " on" : "") + '" data-iklass="' + esc(x.id) + "|" + esc(k) + '">' + esc(k || "no class") + "</button>"; }).join("") + "</div>" +
        '<div class="il">SAVE TO</div><div class="idest">' + esc(destFor(c.kind, c.klass)) + "</div>" +
        '<div class="row"><button type="button" class="btn" data-isave="' + esc(x.id) + '">' + (big ? "Send " + mb(x.size) : x.dup ? "Send again anyway" : "Save") +
        '</button><button type="button" class="btn ghost" data-iskip="' + esc(x.id) + '">Not now</button></div></form>';
    }).join("");
  }
  function bindCards(b) {
    b.querySelectorAll("[data-iname]").forEach(function (el) { el.oninput = function () { CS[el.dataset.iname].name = el.value; }; });
    b.querySelectorAll("[data-ikind]").forEach(function (el) { el.onclick = function () { var p = el.dataset.ikind.split("|"); CS[p[0]].kind = p[1]; draw(true); }; });
    b.querySelectorAll("[data-iklass]").forEach(function (el) { el.onclick = function () { var p = el.dataset.iklass.split("|"); CS[p[0]].klass = p.slice(1).join("|"); draw(true); }; });
    b.querySelectorAll("[data-isave]").forEach(function (el) { el.onclick = function () {
      var id = el.dataset.isave, c = CS[id]; el.disabled = true;
      api("/api/stage_save", { id: id, name: c.name, kind: c.kind, klass: c.klass || null }).then(function (v) {
        var r = v.result || {}; if (!r.ok) alertLine(r.error || "Couldn't save that"); else alertLine("Saved · on its way to " + destFor(c.kind, c.klass));
        delete CS[id]; V = v; draw(true); });
    }; });
    b.querySelectorAll("[data-iskip]").forEach(function (el) { el.onclick = function () { var id = el.dataset.iskip; api("/api/stage_drop", { id: id }).then(function (v) { delete CS[id]; V = v; draw(true); }); }; });
    b.querySelectorAll("[data-gonotes]").forEach(function (el) { el.onclick = function () { tab = "notes"; editing = null; setTab(); }; });
  }

  function draw(force) {
    if (!V) return;
    syncLine();
    var scroll = $("body").scrollTop, active = document.activeElement && document.activeElement.closest && document.activeElement.closest("#body form");
    if (active && force === false) return;     // a background refresh never redraws under someone typing
    var waiting = (V.staged || []).length;
    $("body").innerHTML = (tab === "notes" && !editing ? icards() : waiting ? '<button class="ibanner" data-gonotes="1">' + waiting + " dropped file" + (waiting === 1 ? "" : "s") + " waiting for a name and class · open</button>" : "") + views[tab]();
    $("body").scrollTop = scroll;
    bind();
    bindCards($("body"));
  }
  function change(op) { return api("/api/change", op).then(function (v) { V = Object.assign(V || {}, v); draw(); }); }
  function formData(f) { var o = {}; new FormData(f).forEach(function (v, k) { o[k] = String(v); }); return o; }
  function newNote() {
    var k = V.klass;
    editing = { nid: null, title: k ? k.title + " · " + new Date().toLocaleDateString([], { month: "short", day: "numeric" }) : "", klass: k ? k.title : "", date: iso(new Date()), text: "" };
    noteStatus = ""; tab = "notes"; setTab();
    var ta = document.querySelector("#noteform textarea"); if (ta) ta.focus();
  }
  function saveNote(now) {
    var f = $("noteform"); if (!f || !editing) return;
    var d = formData(f), ed = editing;
    clearTimeout(saveTimer);
    var go = function () {
      if (!d.text.trim() && !ed.nid) return;     // an empty new note isn't saved
      if (ed.nid && d.title.trim() === String(ed.title || "").trim() && d.klass === (ed.klass || "") && d.date === ed.date && d.text === (ed.text || "")) return;   // nothing changed: nothing to send
      api("/api/note", { nid: ed.nid, title: d.title.trim(), klass: d.klass, date: d.date, text: d.text }).then(function (r) {
        if (r.ok) { ed.nid = r.nid; ed.title = d.title; ed.klass = d.klass; ed.date = d.date; ed.text = d.text; }
        noteStatus = r.ok ? "saved on this laptop · " + new Date().toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }) + " · goes to Obsidian at the next sync" : "couldn't save: " + (r.error || "?");
        var el = $("notestatus"); if (el) el.textContent = noteStatus;
      });
    };
    if (now) go(); else saveTimer = setTimeout(go, 1200);
  }
  function bind() {
    var b = $("body");
    b.querySelectorAll("[data-save]").forEach(function (x) { x.onclick = function () {
      var s = window._stories[+x.dataset.save], src = (s.src && s.src[0]) || {};
      change({ type: "save_story", title: s.t, url: src.url || "", publisher: src.source || src.name || "", time: s.last }); x.textContent = "saved ✓"; }; });
    b.querySelectorAll("[data-task]").forEach(function (x) { x.onchange = function () { change({ type: "task_done", text: x.dataset.task, done: x.checked }); }; });
    b.querySelectorAll("[data-del]").forEach(function (x) { x.onclick = function () { change({ type: "cal_del", id: x.dataset.del }); }; });
    b.querySelectorAll("[data-unfollow]").forEach(function (x) { x.onclick = function () { change({ type: "follow_remove", topic: V.snapshot.follow[+x.dataset.unfollow] }); }; });
    b.querySelectorAll("[data-tab]").forEach(function (x) { x.onclick = function () { tab = x.dataset.tab; setTab(); }; });
    b.querySelectorAll("[data-newnote]").forEach(function (x) { x.onclick = newNote; });
    b.querySelectorAll("[data-rec]").forEach(function (x) { x.onclick = function () {
      var a = x.dataset.rec;
      if (a === "start") recStart(); else if (a === "stop") recStop(); else if (a === "pause") recPause();
      else if (a === "mark") { var f = $("markform"); f.hidden = !f.hidden; if (!f.hidden) $("marktext").focus(); else recMark(""); } }; });
    b.querySelectorAll("[data-dlabel]").forEach(function (x) { x.oninput = function () { clearTimeout(x._t); x._t = setTimeout(function () {
      api("/api/draft/set", { id: x.dataset.dlabel, label: x.value }).then(function (r) { var n = document.querySelector('[data-dname="' + x.dataset.dlabel + '"]'); if (n && r.name) n.textContent = r.name; }); }, 400); }; });
    b.querySelectorAll("[data-dklass]").forEach(function (x) { x.onchange = function () { api("/api/draft/set", { id: x.dataset.dklass, klass: x.value }); }; });
    b.querySelectorAll("[data-dsend]").forEach(function (x) { x.onclick = function () { x.disabled = true; var f = x.closest("form"), lab = f.querySelector("[data-dlabel]"), kl = f.querySelector("[data-dklass]");
      api("/api/draft/set", { id: x.dataset.dsend, label: lab.value, klass: kl.value }).then(function () { return api("/api/draft/send", { id: x.dataset.dsend }); })
        .then(function (r) { alertLine(r.ok ? "Sent: " + r.name : (r.error || "couldn't send")); poll(); }); }; });
    b.querySelectorAll("[data-ddiscard]").forEach(function (x) { x.onclick = function () { if (confirm("Discard this recording? It can't be undone.")) api("/api/draft/discard", { id: x.dataset.ddiscard }).then(poll); }; });
    b.querySelectorAll("[data-dnote]").forEach(function (x) { x.onclick = function () { var d = (V.drafts || []).filter(function (y) { return y.id === x.dataset.dnote; })[0]; if (!d) return;
      var st = new Date(d.started * 1000); editing = { nid: null, title: (d.label || d.klass || "Lecture") + " · " + st.toLocaleDateString([], { month: "short", day: "numeric" }), klass: d.klass || "", date: iso(st), text: "" }; noteStatus = ""; draw();
      var ta = document.querySelector("#noteform textarea"); if (ta) ta.focus(); }; });
    var mf = $("markform"); if (mf) mf.onsubmit = function (e) { e.preventDefault(); recMark($("marktext").value.trim()); $("marktext").value = ""; mf.hidden = true; };
    var dk = $("dropklass"); if (dk) dk.onchange = function () { api("/api/drop_klass", { klass: dk.value }).then(poll); };
    b.querySelectorAll("[data-dropauto]").forEach(function (x) { x.onclick = function () { api("/api/drop_klass", { klass: null }).then(poll); }; });
    b.querySelectorAll("[data-open]").forEach(function (x) { x.onclick = function () {
      var n = (V.notes || []).filter(function (y) { return y.nid === x.dataset.open; })[0]; if (!n) return;
      editing = { nid: n.nid, title: n.title, klass: n.klass || "", date: n.date, text: n.text || "" }; noteStatus = ""; draw(); }; });
    b.querySelectorAll("[data-nhide]").forEach(function (x) { x.onclick = function (e) { e.stopPropagation(); x.disabled = true;
      api("/api/note_hide", { nid: x.dataset.nhide }).then(function () { alertLine("Off the list · still in Obsidian"); poll(); }); }; });
    b.querySelectorAll("[data-back]").forEach(function (x) { x.onclick = function () { if (editing) saveNote(true); editing = null; reading = null; draw(); }; });
    b.querySelectorAll("[data-openfile]").forEach(function (x) { x.onclick = function () { api("/api/open", { path: x.dataset.openfile }); }; });
    b.querySelectorAll("[data-openfolder]").forEach(function (x) { x.onclick = function () { api("/api/open", { path: V.files_dir }); }; });
    b.querySelectorAll("[data-clearchat]").forEach(function (x) { x.onclick = function () { api("/api/chat_clear", {}).then(poll); }; });
    b.querySelectorAll("[data-read]").forEach(function (x) {
      var open = function () { var rel = x.dataset.read; reading = { rel: rel, text: null }; draw();
        api("/api/article?rel=" + encodeURIComponent(rel)).then(function (r) { if (reading && reading.rel === rel) { reading.text = r.text || "*(not on this laptop yet)*"; draw(); $("body").scrollTop = 0; } }); };
      x.onclick = open; x.onkeydown = function (e) { if (e.key === "Enter") open(); };
    });
    b.querySelectorAll("[data-sub]").forEach(function (x) { x.onclick = function () { NW.sub = x.dataset.sub; if (NW.sub === "govs" && !NW.govs) loadGovs(); if (NW.sub !== "brief") loadNews(); draw(); $("body").scrollTop = 0; }; });
    b.querySelectorAll("[data-iso]").forEach(function (x) { x.onclick = function () { loadCountry(x.dataset.iso); }; });
    b.querySelectorAll("[data-wsave]").forEach(function (x) { x.onclick = function () {
      var s = window._wstories[+x.dataset.wsave], it = (s.items || [])[0] || {};
      change({ type: "save_story", title: s.title, url: it.url || "", publisher: it.source || "", time: s.last || s.t }); x.textContent = "saved ✓"; }; });
    var wrf = $("wrf"); if (wrf) wrf.onclick = function () {
      wrf.disabled = true;
      api("/api/world/refresh", {}).then(function (r) { if (r.started && NW.sub === "brief") NW.sub = "live"; if (!r.started) alertLine("Getting the feed list from your PC first…"); loadNews(); if (NW.sub === "govs") setTimeout(loadGovs, 8000); });
    };
    var rg = $("rg"); if (rg) rg.onchange = function () { NW.region = rg.value; loadNews(); };
    var gq = $("gq"); if (gq) gq.oninput = function () {
      NW.q = gq.value; var f = NW.q.toLowerCase();
      document.querySelectorAll("#gl .gitem").forEach(function (el) { var c = NW.govs.list.filter(function (x) { return x.iso2 === el.dataset.iso; })[0];
        el.hidden = !!f && (c.name + " " + (c.leaders || "")).toLowerCase().indexOf(f) < 0; });
    };
    var nf = $("noteform");
    if (nf) {
      nf.oninput = function () { saveNote(false); var el = $("notestatus"); if (el) el.textContent = "typing…"; };
      nf.onchange = function () { saveNote(false); };
      nf.onsubmit = function (e) { e.preventDefault(); saveNote(true); };
    }
    var on = function (id, fn) { var form = $(id); if (form) form.onsubmit = function (e) { e.preventDefault(); var d = formData(form); Object.keys(d).forEach(function (k) { d[k] = d[k].trim(); }); fn(d, form); }; };
    on("calform", function (d, form) {
      change({ type: "cal_add", item: { title: d.title, date: d.date, time: d.time || null, kind: d.kind, notes: "", repeat: d.repeat || null, until: null } }); form.reset(); });
    on("taskform", function (d, form) { change({ type: "task_add", text: d.text, due: d.due || null }); form.reset(); });
    on("dlform", function (d, form) { change({ type: "deadline_add", what: d.what, date: d.date }); form.reset(); });
    on("followform", function (d, form) { change({ type: "follow_add", topic: d.topic }); form.reset(); });
  }

  function ask() {
    var q = $("ask").value.trim(); if (!q || busy) return;
    $("ask").value = ""; busy = true; tab = "chat"; editing = null;
    V.chat = (V.chat || []).concat([{ role: "user", text: q }]); setTab();
    api("/api/chat", { q: q }).then(function (r) {
      busy = false; if (r.chat) V.chat = r.chat; draw(); $("body").scrollTop = $("body").scrollHeight;
    }).catch(function () { busy = false; poll(); });
  }
  function setTab() {
    if (tab === "news" && !NW.news) loadNews();
    if (tab !== "notes" && editing) { saveNote(true); editing = null; }
    if (tab !== "saved") reading = null;
    document.querySelectorAll("#tabs button").forEach(function (b) { b.setAttribute("aria-selected", b.dataset.tab === tab ? "true" : "false"); });
    $("body").scrollTop = 0; draw();
  }
  document.querySelectorAll("#tabs button").forEach(function (b) { b.onclick = function () { tab = b.dataset.tab; setTab(); }; });
  $("send").onclick = ask;
  $("recbar").onclick = function () { tab = "notes"; editing = null; setTab(); };
  $("ask").onkeydown = function (e) { if (e.key === "Enter") ask(); };
  $("owlbtn").onclick = function () { api("/api/owl", {}).then(function (r) { alertLine(r.hidden ? "Owl hidden. This button or Ctrl+Alt+O brings it back." : "Owl is back"); poll(); }); };
  $("hide").onclick = function () { if (editing) saveNote(true); api("/api/hide", {}); };
  $("syncbtn").onclick = function () {
    if (syncing) return; syncing = true; $("syncbtn").classList.add("spin");
    api("/api/sync", {}).then(function (v) { V = v; draw(false); }).finally(function () { syncing = false; $("syncbtn").classList.remove("spin"); });
  };

  // drop anything on the panel: files are kept and sent, links are saved, text becomes a note
  var depth = 0, overlay = $("dropover");
  function hasStuff(e) { var t = e.dataTransfer && e.dataTransfer.types; return t && (Array.prototype.indexOf.call(t, "Files") >= 0 || Array.prototype.indexOf.call(t, "text/uri-list") >= 0 || Array.prototype.indexOf.call(t, "text/plain") >= 0); }
  document.addEventListener("dragenter", function (e) { if (!hasStuff(e)) return; e.preventDefault(); depth++; overlay.hidden = false; });
  document.addEventListener("dragover", function (e) { if (hasStuff(e)) e.preventDefault(); });
  document.addEventListener("dragleave", function () { if (--depth <= 0) { depth = 0; overlay.hidden = true; } });
  document.addEventListener("drop", function (e) {
    e.preventDefault(); depth = 0; overlay.hidden = true;
    var dt = e.dataTransfer, files = Array.prototype.slice.call(dt.files || []);
    if (files.length) {
      tab = "notes"; editing = null; setTab();
      files.forEach(function (f) {
        fetch("/api/drop", { method: "POST", headers: { "X-Lite-Token": T, "X-Card": "1", "X-Name": encodeURIComponent(f.name), "X-Mtime": String(f.lastModified || 0) }, body: f })
          .then(function (r) { return r.json(); }).then(function (r) { if (!r.ok) alertLine(r.error || "Couldn't take " + f.name); poll(); });
      });
      return;
    }
    var url = (dt.getData("text/uri-list") || "").split("\n").filter(function (l) { return l && l[0] !== "#"; })[0], text = dt.getData("text/plain");
    if (url || /^https?:\/\//i.test(text || "")) api("/api/quick", { text: url || text.trim() }).then(function (r) { alertLine(r.ok ? r.msg : r.error); poll(); });
    else if (text && text.trim()) change({ type: "note_quick", text: text.trim() }).then(function () { alertLine("Saved as a note"); });
  });
  function alertLine(t) { var el = $("flash"); el.textContent = t || ""; el.hidden = !t; clearTimeout(el._t); el._t = setTimeout(function () { el.hidden = true; }, 4000); }

  function poll() {
    var hd = { "X-Lite-Token": T }; if (R) hd["X-Rec"] = R.id;
    return fetch("/api/state", { headers: hd }).then(function (r) { return r.json(); }).then(function (v) {
      if (v.error && !v.snapshot) { $("synctext").textContent = "Archie Lite hit a problem: " + v.error + " (retrying)"; return; }
      V = v;
      if (v.hint && v.hint.at > lastHint) {        // the owl's pop-ups open the right tab
        if (lastHint || Date.now() / 1000 - v.hint.at < 20) { tab = v.hint.tab; editing = null; reading = null; lastHint = v.hint.at; setTab(); return; }
        lastHint = v.hint.at;
      }
      if (tab === "news" && NW.sub !== "brief") { syncLine(); return; }
      draw(false);
    }).catch(function (e) { if (!V) $("synctext").textContent = "can't load the panel yet (" + (e && e.message || e) + "), retrying…"; });
  }
  poll(); setInterval(poll, 4000);
})();
