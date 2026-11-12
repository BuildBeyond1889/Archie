/* Archie on your phone (1.0). Everything is kept on the phone (works offline) and synced with your PC
   through the same requests Archie Lite uses. Files and recordings travel in 2 MB pieces. */
(function () {
  "use strict";
  var VERSION = "1.0.0", CHUNK = 2 * 1024 * 1024;
  var $ = function (id) { return document.getElementById(id); };
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function rid() { var a = new Uint8Array(5); crypto.getRandomValues(a); return Array.prototype.map.call(a, function (b) { return ("0" + b.toString(16)).slice(-2); }).join(""); }
  function iso(d) { return d.getFullYear() + "-" + ("0" + (d.getMonth() + 1)).slice(-2) + "-" + ("0" + d.getDate()).slice(-2); }
  function dayLabel(s) { return new Date(s + "T12:00:00").toLocaleDateString([], { weekday: "short", month: "short", day: "numeric" }); }
  function clock(hm) { if (!hm) return ""; var p = hm.split(":"), d = new Date(); d.setHours(+p[0], +p[1] || 0); return d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }); }
  function daysTo(s) { return Math.round((new Date(s + "T12:00:00") - new Date(iso(new Date()) + "T12:00:00")) / 86400000); }
  function ago(ts) { if (!ts) return "never"; var s = Math.max(0, Date.now() / 1000 - ts); return s < 90 ? "just now" : s < 5400 ? Math.round(s / 60) + " min ago" : s < 129600 ? Math.round(s / 3600) + " h ago" : Math.round(s / 86400) + " days ago"; }
  function hms(sec) { sec = Math.max(0, Math.floor(sec)); var h = Math.floor(sec / 3600), m = Math.floor(sec % 3600 / 60), s = sec % 60; return (h ? h + ":" + ("0" + m).slice(-2) : m) + ":" + ("0" + s).slice(-2); }
  function takeHtml(t) {                       // the brief's "- a - b - c" as one line each
    t = String(t || "").trim();
    if (!/^-\s/.test(t)) return esc(t);
    return t.replace(/^-\s+/, "").split(/\s+-\s+(?=\S)/).map(function (x) { return '<div class="tk">' + esc(x) + "</div>"; }).join("");
  }
  function nice(d) {                         // "2026-11-09 3.22 PM": readable, and safe in a file name
    var h = d.getHours(), ap = h < 12 ? "AM" : "PM"; h = h % 12 || 12;
    return d.getFullYear() + "-" + ("0" + (d.getMonth() + 1)).slice(-2) + "-" + ("0" + d.getDate()).slice(-2) + " " + h + "." + ("0" + d.getMinutes()).slice(-2) + " " + ap;
  }
  function stamp(d) { var p = function (n) { return ("0" + n).slice(-2); }; return d.getFullYear() + p(d.getMonth() + 1) + p(d.getDate()) + p(d.getHours()) + p(d.getMinutes()) + p(d.getSeconds()); }
  function safeName(s) { return String(s || "file").replace(/[<>:"/\\|?*#^\[\]\u0000-\u001f]/g, " ").replace(/\s+/g, " ").trim().slice(0, 90) || "file"; }

  // ----- storage on the phone ------------------------------------------------------------------------
  var LS = { get: function (k, d) { try { var v = localStorage.getItem("archie:" + k); return v ? JSON.parse(v) : d; } catch (e) { return d; } },
    set: function (k, v) { try { localStorage.setItem("archie:" + k, JSON.stringify(v)); } catch (e) {} } };
  var dbp = null;
  function db() {
    if (!dbp) dbp = new Promise(function (res, rej) {
      var r = indexedDB.open("archie", 1);
      r.onupgradeneeded = function () { var d = r.result; ["blobs", "world", "articles", "shared", "rec"].forEach(function (n) { if (!d.objectStoreNames.contains(n)) d.createObjectStore(n); }); };
      r.onsuccess = function () { res(r.result); }; r.onerror = function () { rej(r.error); };
    });
    return dbp;
  }
  function idb(store, mode, fn) {
    return db().then(function (d) { return new Promise(function (res, rej) {
      var tx = d.transaction(store, mode), req = fn(tx.objectStore(store));
      tx.oncomplete = function () { res(req && req.result); }; tx.onerror = function () { rej(tx.error); };
    }); });
  }
  var idbGet = function (s, k) { return idb(s, "readonly", function (st) { return st.get(k); }); };
  var idbPut = function (s, k, v) { return idb(s, "readwrite", function (st) { return st.put(v, k); }); };
  var idbDel = function (s, k) { return idb(s, "readwrite", function (st) { return st.delete(k); }); };
  var idbKeys = function (s) { return idb(s, "readonly", function (st) { return st.getAllKeys(); }); };

  var EMPTY = { calendar: [], tasks: [], deadlines: [], brief: null, saved: [], follow: [], pc: null, model: null, mail_cards: [] };
  var S = Object.assign({}, EMPTY, LS.get("snap", {}));
  var pending = LS.get("pending", []), notes = LS.get("notes", {}), chat = LS.get("chat", []), drops = LS.get("drops", []);
  var drafts = LS.get("drafts", []);        // stopped recordings waiting for SEND: [{ id, mode, klass, started, duration, marks, items }]
  var meta = Object.assign({ last_ok: null, articles: {}, world_at: 0, govs_at: 0, seenClip: "", recent: [] }, LS.get("meta", {}));
  var status = { state: "starting", msg: "" }, syncing = false, W = null, tab = "today", sub = {}, editing = null, reading = null, rec = null;
  function save() { LS.set("snap", S); LS.set("pending", pending); LS.set("notes", notes); LS.set("chat", chat.slice(-200)); LS.set("drops", drops.slice(0, 80)); LS.set("meta", meta); LS.set("drafts", drafts); }

  // ----- talking to the PC ------------------------------------------------------------------------------
  function op(body, ms) {
    var c = new AbortController(), t = setTimeout(function () { c.abort(); }, ms || 30000);
    return fetch("/api/op", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body), signal: c.signal })
      .then(function (r) { if (r.status === 403) throw new Error("this phone isn't allowed (open it through Tailscale, signed in as you)"); if (!r.ok) throw new Error("your PC answered " + r.status); return r.json(); })
      .catch(function (e) { throw new Error(e.name === "AbortError" ? "your PC didn't answer in time" : (e.message || "can't reach your PC")); })
      .finally(function () { clearTimeout(t); });
  }

  function applyLocal(s, c) {
    var t = c.type;
    if (t === "cal_add" && !s.calendar.some(function (e) { return e.id === c.id; })) s.calendar.push(Object.assign({}, c.item, { id: c.id }));
    else if (t === "cal_del") s.calendar = s.calendar.filter(function (e) { return e.id !== c.id; });
    else if (t === "mail_done") s.mail_cards = (s.mail_cards || []).filter(function (m) { return m.id !== c.id; });
    else if (t === "mail_file") (s.mail_cards || []).forEach(function (m) { if (m.id === c.id) (m.files || []).forEach(function (f) { if (f.n === c.n) f.filed = "sending…"; }); });
    else if (t === "cal_edit") s.calendar.forEach(function (e) { if (e.id === c.id) Object.assign(e, c.item); });
    else if (t === "task_add" && !s.tasks.some(function (x) { return !x.done && x.text.toLowerCase() === c.text.toLowerCase(); })) s.tasks.push({ text: c.text, done: false, due: c.due || null });
    else if (t === "task_done") s.tasks.forEach(function (x) { if (x.text.toLowerCase() === c.text.toLowerCase()) x.done = !!c.done; });
    else if (t === "deadline_add") { s.deadlines.push({ date: c.date, what: c.what }); s.deadlines.sort(function (a, b) { return a.date.localeCompare(b.date); }); }
    else if (t === "follow_add" && s.follow.indexOf(c.topic) < 0) s.follow.push(c.topic);
    else if (t === "follow_remove") s.follow = s.follow.filter(function (f) { return f.toLowerCase() !== c.topic.toLowerCase(); });
    else if (t === "save_story" && !s.saved.some(function (x) { return x.name === c.title; })) s.saved.unshift({ name: c.title, time: Date.now() / 1000, pending: true });
    return s;
  }
  function change(c) {
    c.oid = rid() + rid();
    if (c.type === "cal_add") c.id = c.id || rid();
    if (c.type === "cal_del" || c.type === "cal_edit") { var cur = S.calendar.filter(function (e) { return e.id === c.id; })[0]; if (!cur) return; c.base = { title: cur.title, date: cur.date, time: cur.time, kind: cur.kind, notes: cur.notes, repeat: cur.repeat, until: cur.until }; }
    applyLocal(S, c); if (/^cal_/.test(c.type) && calSince) { var sg = calSig(); calSince = sg; meta.calSig = sg; } pending.push(c); save(); render(); kick();
  }
  function quickAdd(text) {
    text = (text || "").trim(); if (!text) return;
    var k = currentClass();
    pending.push({ type: "quick_add", oid: rid() + rid(), text: text, klass: k ? k.title : null, at: Date.now() / 1000 });
    save(); render(); toast(status.state === "home" ? "Adding…" : "Saved on your phone; it's added when your PC is reachable"); kick();
  }

  function clientInfo() {
    return { version: VERSION, host: "Phone", pending: pending.filter(function (c) { return c.type !== "file_drop"; }).length,
      files_waiting: pending.filter(function (c) { return c.type === "file_drop"; }).length,
      chat_waiting: chat.filter(function (m) { return m.queued; }).length, battery: false, update_error: null, build: null, files_dir: "phone" };
  }

  var kickT = null;
  function kick(ms) { clearTimeout(kickT); kickT = setTimeout(syncNow, ms == null ? 600 : ms); }
  function syncNow() {
    if (syncing) return Promise.resolve(); syncing = true; syncUI();
    return uploadFiles().then(function () { meta.upload_error = null; }, function (e) { meta.upload_error = e.message; })
      .then(function () {
        var sending = pending.filter(function (c) { return c.type !== "file_drop" || (c.sent || 0) >= c.n; });
        var wire = sending.map(function (c) { var o = Object.assign({}, c); ["sent", "tries", "at", "local"].forEach(function (k) { delete o[k]; }); return o; });
        return op({ op: "sync", changes: wire, client: clientInfo() }, sending.some(function (c) { return c.type === "file_drop"; }) ? 180000 : 30000).then(function (res) {
          if (!res.ok) throw new Error(res.error || "sync failed");
          var byOid = {}; (res.results || []).forEach(function (r) { byOid[r.oid] = r; });
          var sent = {}, retry = [];
          sending.forEach(function (c) {
            sent[c.oid] = 1; var r = byOid[c.oid] || {}, unknown = /unknown/.test(r.note || "");
            if (!r.ok && /^(file_drop|note_save|quick_add)$/.test(c.type) && ((c.tries || 0) < 5 || unknown)) {
              if (!unknown) c.tries = (c.tries || 0) + 1; if (c.type === "file_drop") c.sent = 0; retry.push(c); return;
            }
            if (c.type === "file_drop") { drops.unshift({ name: c.name, klass: c.klass, folder: c.folder, at: c.at, ok: !!r.ok, note: r.note }); idbDel("blobs", c.fid).catch(function () {}); }
            if (c.type === "quick_add") toast(r.ok ? r.note : "Couldn't add “" + c.text + "”: " + (r.note || "?"));
          });
          pending = retry.concat(pending.filter(function (c) { return !sent[c.oid]; }));
          S = Object.assign({}, EMPTY, res.snapshot); delete S.lite_files; delete S.addresses;
          pending.forEach(function (c) { applyLocal(S, c); });
          meta.last_ok = Date.now() / 1000; status = { state: "home", pc: S.pc };
          save(); render();
          return afterSync();
        });
      })
      .catch(function (e) { status = { state: "away", msg: e.message }; })
      .then(function () { syncing = false; syncUI(); if (tab !== "class" || !rec) render(false); });
  }
  function afterSync() {
    return fetchWorld(false).catch(function () {})
      .then(function () { return fetchArticles(); }).catch(function () {})
      .then(drainChat).catch(function () {});
  }

  function toB64(blob) {
    return new Promise(function (res, rej) { var r = new FileReader(); r.onload = function () { res(String(r.result).split(",")[1] || ""); }; r.onerror = function () { rej(r.error); }; r.readAsDataURL(blob); });
  }
  function uploadFiles() {
    var todo = pending.filter(function (c) { return c.type === "file_drop" && (c.sent || 0) < c.n; });
    return todo.reduce(function (p, c) {
      return p.then(function () {
        return idbGet("blobs", c.fid).then(function (blob) {
          if (!blob) { pending = pending.filter(function (x) { return x !== c; }); drops.unshift({ name: c.name, ok: false, note: "the phone's copy is gone" }); save(); return; }
          function next() {
            if ((c.sent || 0) >= c.n) return Promise.resolve();
            var i = c.sent || 0;
            return toB64(blob.slice(i * CHUNK, (i + 1) * CHUNK)).then(function (b64) {
              return op({ op: "file_chunk", fid: c.fid, i: i, n: c.n, b64: b64 }, 120000);
            }).then(function (r) {
              if (!r.ok) throw new Error(/unknown/.test(r.error || "") ? "restart Archie on your PC to receive files" : (r.error || "a piece was refused"));
              c.sent = i + 1; save(); if (tab === "class" || tab === "more" || tab === "add") render(false); return next();
            });
          }
          return next();
        });
      });
    }, Promise.resolve());
  }
  function addFile(blob, name, klass, mtime, extra) {
    var fid = rid() + rid();
    return idbPut("blobs", fid, blob).then(function () { return blob.arrayBuffer(); })
      .then(function (buf) { return crypto.subtle.digest("SHA-256", buf); })
      .then(function (h) {
        var sha = Array.prototype.map.call(new Uint8Array(h), function (b) { return ("0" + b.toString(16)).slice(-2); }).join("");
        pending.push({ type: "file_drop", oid: rid() + rid(), fid: fid, name: safeName(name), klass: klass || null, sha: sha, size: blob.size,
          mtime: (mtime || Date.now()) / 1000, date: iso(new Date()), n: Math.max(1, Math.ceil(blob.size / CHUNK)), sent: 0, at: Date.now() / 1000 });
        if (extra) Object.assign(pending[pending.length - 1], extra);
        save(); render(false); kick();
      });
  }

  // ----- notes -----------------------------------------------------------------------------------------------
  function noteSave(n) {
    n.nid = n.nid || rid() + rid(); n.updated = Date.now() / 1000;
    n.title = (n.title || "").trim() || (n.text || "").trim().split("\n")[0].slice(0, 60) || "Untitled";
    notes[n.nid] = n;
    pending = pending.filter(function (c) { return !(c.type === "note_save" && c.nid === n.nid); });
    pending.push({ type: "note_save", oid: rid() + rid(), nid: n.nid, title: n.title, klass: n.klass || null, date: n.date, text: n.text || "", folder: n.folder || null });
    save(); kick(15000);
    return n;
  }

  // ----- classes from the calendar ---------------------------------------------------------------------------
  var DUR = { class: 75, lab: 110 };
  function occurrences(fromDate, days) {
    var out = [], start = new Date(iso(fromDate) + "T12:00:00"), end = new Date(start.getTime() + days * 86400000);
    (S.calendar || []).forEach(function (e) {
      var d0 = new Date(e.date + "T12:00:00");
      if (e.repeat === "weekly") {
        var until = e.until ? new Date(e.until + "T12:00:00") : end, d = new Date(d0);
        while (d < start) d = new Date(d.getTime() + 7 * 86400000);
        for (; d <= end && d <= until; d = new Date(d.getTime() + 7 * 86400000)) out.push({ e: e, date: iso(d) });
      } else if (d0 >= start && d0 <= end) out.push({ e: e, date: e.date });
    });
    return out.sort(function (a, b) { return (a.date + (a.e.time || "99")).localeCompare(b.date + (b.e.time || "99")); });
  }
  function currentClass(now) {
    now = now || new Date(); var best = null;
    occurrences(now, 0).forEach(function (x) {
      var e = x.e; if (!(e.kind in DUR) || !e.time) return;
      var p = e.time.split(":"), t0 = new Date(now); t0.setHours(+p[0], +p[1], 0, 0);
      var mins = DUR[e.kind], diff = (now - t0) / 60000;
      if (diff >= -20 && diff <= mins + 30 && (!best || Math.abs(diff) < best.gap)) best = { gap: Math.abs(diff), title: e.title, kind: e.kind, time: e.time, until: new Date(t0.getTime() + mins * 60000) };
    });
    return best;
  }
  function classNames() { var out = []; (S.calendar || []).forEach(function (e) { if (e.kind in DUR && out.indexOf(e.title) < 0) out.push(e.title); }); return out.sort(); }

  // ----- the class recorder ------------------------------------------------------------------------------------
  function recElapsed() { if (!rec) return 0; return (rec.acc + (rec.paused ? 0 : Date.now() - rec.since)) / 1000; }
  function startRec() {
    if (!navigator.mediaDevices || !window.MediaRecorder) return toast("This browser can't record audio.");
    var mode = sub.mode === "ideas" ? "ideas" : "lecture";
    var k = mode === "ideas" ? "" : sub.klass !== undefined ? sub.klass : (currentClass() || {}).title || "";
    navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: false, noiseSuppression: true, autoGainControl: true } }).then(function (stream) {
      var type = MediaRecorder.isTypeSupported("audio/webm;codecs=opus") ? "audio/webm;codecs=opus" : "";
      var mr = new MediaRecorder(stream, type ? { mimeType: type, audioBitsPerSecond: 32000 } : {});
      var id = rid() + rid(), idx = 0, started = new Date();
      rec = { id: id, mr: mr, stream: stream, klass: k, mode: mode, started: started.getTime(), acc: 0, since: Date.now(), paused: false, marks: [], photos: [], lock: null, level: 0 };
      LS.set("rec_active", { id: id, klass: k, mode: mode, started: rec.started, marks: [], photos: [] });
      mr.ondataavailable = function (e) { if (e.data && e.data.size) idbPut("rec", id + ":" + ("00000" + idx++).slice(-6), e.data).catch(function () {}); };
      mr.onstop = function () { setTimeout(function () { finishRec(id); }, 400); };
      mr.start(10000);                                   // a piece every 10 s, kept on the phone as it goes
      try { var ac = new (window.AudioContext || window.webkitAudioContext)(), an = ac.createAnalyser(); an.fftSize = 512; ac.createMediaStreamSource(stream).connect(an);
        var buf = new Uint8Array(an.fftSize); rec.ac = ac;
        (function meter() { if (!rec || rec.id !== id) return; an.getByteTimeDomainData(buf); var m = 0; for (var i = 0; i < buf.length; i++) m = Math.max(m, Math.abs(buf[i] - 128)); rec.level = m / 128; var el = $("lvl"); if (el) el.style.width = Math.min(100, rec.level * 160) + "%"; requestAnimationFrame(meter); })();
      } catch (e) {}
      if (navigator.wakeLock) navigator.wakeLock.request("screen").then(function (l) { if (rec) rec.lock = l; }).catch(function () {});
      render(); tick();
    }).catch(function (e) { toast("The microphone isn't available: " + (e.message || e.name)); });
  }
  function tick() { if (!rec) return; var el = $("timer"); if (el) el.textContent = hms(recElapsed()); setTimeout(tick, 500); }
  function pauseRec() { if (!rec) return; if (rec.paused) { rec.mr.resume(); rec.since = Date.now(); rec.paused = false; } else { rec.mr.pause(); rec.acc += Date.now() - rec.since; rec.paused = true; } render(); }
  function markRec(label) {
    if (!rec) return; rec.marks.push({ t: recElapsed(), label: label || "" });
    var a = LS.get("rec_active", null); if (a) { a.marks = rec.marks; LS.set("rec_active", a); }
    navigator.vibrate && navigator.vibrate(30); render(false);
  }
  function stopRec() {
    if (!rec) return;
    rec.duration = recElapsed();
    try { rec.mr.stop(); } catch (e) { finishRec(rec.id); }
    rec.stream.getTracks().forEach(function (t) { t.stop(); });
    if (rec.ac) rec.ac.close().catch(function () {});
    if (rec.lock) rec.lock.release().catch(function () {});
    rec.stopping = true; render();
  }
  function finishRec(id, recovered) {
    // Stopping doesn't send: it makes a draft you can add photos and notes to, rename, then SEND.
    var info = rec && rec.id === id ? rec : recovered;
    if (!info || info.done) return; info.done = true;
    idbKeys("rec").then(function (keys) {
      var mine = keys.filter(function (k) { return String(k).indexOf(id + ":") === 0; }).sort();
      return Promise.all(mine.map(function (k) { return idbGet("rec", k); })).then(function (parts) {
        parts = parts.filter(Boolean);
        if (!parts.length && !(info.photos || []).length) { toast("Nothing was recorded."); return; }
        var started = new Date(info.started), blob = new Blob(parts, { type: "audio/webm" });
        var dur = info.duration || (recovered ? Math.max(0, parts.length * 10) : (Date.now() - info.started) / 1000);
        var bid = rid() + rid();
        return (parts.length ? idbPut("blobs", bid, blob) : Promise.resolve()).then(function () {
          var items = parts.length ? [{ kind: "audio", bid: bid, tag: nice(started), size: blob.size, label: "" }] : [];
          (info.photos || []).forEach(function (ph) { items.push({ kind: "photo", bid: ph.bid, tag: ph.tag, label: "" }); });
          drafts.push({ id: id, mode: info.mode || "lecture", klass: info.klass || "", started: info.started, duration: dur,
                        marks: info.marks || [], items: items, recovered: !!recovered });
          sub.draft = id; save();
          return Promise.all(mine.map(function (k) { return idbDel("rec", k); }));
        }).then(function () { toast(recovered ? "Found an unfinished recording (" + hms(dur) + "). It's ready to send." : "Stopped at " + hms(dur) + ". Add photos or notes, rename, then press SEND."); });
      });
    }).catch(function (e) { toast("Couldn't keep the recording: " + e.message + ". It's still on the phone; reopen the app to try again."); info.done = false; return; })
      .then(function () { if (rec && rec.id === id) rec = null; if (!info.done) return; LS.set("rec_active", null); tab = "class"; render(); });
  }
  function sentList() {
    var sending = pending.filter(function (c) { return c.type === "file_drop"; });
    var when = function (t) { return t ? new Date(t * 1000).toLocaleString([], { weekday: "short", month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }) : ""; };
    var where = function (f) { return f.folder === "ideas" ? "Ideas" : f.klass || "no class"; };
    var recent = sending.map(function (c) { return { name: c.name, where: where(c), at: c.at, st: "sending " + Math.round(100 * (c.sent || 0) / c.n) + "%" }; })
      .concat(drops.slice(0, 12).map(function (f) { return { name: f.name, where: where(f), at: f.at, st: f.ok ? (f.note || "in Obsidian") : "not sent: " + (f.note || "?") }; }));
    if (!recent.length) return "";
    return '<div class="col sent"><button class="dd" data-act="sent" aria-expanded="' + !!sub.sentOpen + '"><span>Sent from this phone</span><span class="n">' + recent.length + (sending.length ? " · " + sending.length + " sending" : "") + '</span><svg viewBox="0 0 24 24"><path d="M6 9l6 6 6-6"/></svg></button>' +
      (sub.sentOpen ? recent.map(function (f) { return '<div class="when sentrow"><span class="w">' + esc(f.name) + '</span><span class="sentmeta"><b>' + esc(f.where) + "</b>" + (f.at ? " · " + esc(when(f.at)) : "") + '</span><span class="k">' + esc(f.st) + "</span></div>"; }).join("") : "") + "</div>";
  }
  function draftName(d, it) {                 // "Test1243 (2026-11-09 3.22 PM).webm", "whiteboard (Board 2026-11-09 3.25 PM).jpg"
    var lab = String(it.label || "").replace(/[<>:"/\\|?*#^\[\]();]/g, " ").replace(/\s+/g, " ").trim();
    if (/^\d{14}$/.test(it.tag)) {             // drafts made before the new names
      if (it.kind === "audio") return lab ? lab + " · " + it.tag.slice(0, 8) + " " + it.tag.slice(8) + ".webm" : "Recording " + it.tag + ".webm";
    }
    if (it.kind === "audio") return (lab || "Recording") + " (" + it.tag + ").webm";
    if (/^(Board|Photo) \d{14}$/.test(it.tag)) return (lab ? lab + " · " : "") + it.tag + ".jpg";
    var kind = it.tag.split(" ")[0], when = it.tag.slice(kind.length + 1);
    return lab ? lab + " (" + kind + " " + when + ").jpg" : kind + " (" + when + ").jpg";
  }
  function sendDraft(d) {
    var folder = d.mode === "ideas" ? "ideas" : null, klass = folder ? null : (d.klass || null), audioName = null, jobs = [];
    d.items.forEach(function (it) {
      if (it.kind === "note") {
        if ((it.text || "").trim() || (it.title || "").trim()) noteSave({ title: it.title || ((d.mode === "ideas" ? "Idea" : (klass || "Lecture")) + " · " + new Date(d.started).toLocaleDateString([], { month: "short", day: "numeric" })), klass: klass, date: iso(new Date(d.started)), text: it.text || "", folder: folder });
        return;
      }
      var name = draftName(d, it); if (it.kind === "audio") audioName = name;
      jobs.push(idbGet("blobs", it.bid).then(function (blob) {
        if (!blob) return toast("The phone's copy of " + name + " is gone.");
        return addFile(blob, name, klass, it.kind === "audio" ? d.started + d.duration * 1000 : Date.now(), { own: true, folder: folder })
          .then(function () { return idbDel("blobs", it.bid); });
      }));
    });
    if (audioName && d.marks.length) {
      var lines = d.marks.map(function (m) { return "- **" + hms(m.t) + "** " + (m.label || "marked"); });
      noteSave({ title: (d.mode === "ideas" ? "Idea" : (klass || "Lecture")) + " · " + new Date(d.started).toLocaleDateString([], { month: "short", day: "numeric" }) + " marks",
        klass: klass, folder: folder, date: iso(new Date(d.started)), text: "Recording: [[" + audioName + "]] (" + hms(d.duration) + ").\n\n## Marked moments\n\n" + lines.join("\n") + "\n" });
    }
    drafts = drafts.filter(function (x) { return x !== d; }); sub.draft = null; save();
    return Promise.all(jobs).then(function () { toast("Sending " + (d.mode === "ideas" ? "to Ideas" : klass ? "to " + klass : "(no class)") + ". Archie types it out on your PC."); render(); });
  }
  function draftView(d) {
    var classes = classNames(); if (d.klass && classes.indexOf(d.klass) < 0) classes.push(d.klass);
    var when = new Date(d.started).toLocaleString([], { weekday: "short", month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
    var icon = { audio: "🎙", photo: "📷", note: "📝" };
    var h = '<form id="draftform" class="draft" onsubmit="return false"><div class="h neon">' + (d.mode === "ideas" ? "Idea" : "Lecture") + " ready to send</div>" +
      '<div class="sub">recorded ' + esc(when) + " · " + hms(d.duration) + (d.recovered ? " · recovered after the app closed" : "") + "</div>";
    if (d.mode !== "ideas") h += '<label class="l">Filed under<select id="dklass"><option value="">no class (Voice inbox)</option>' + classes.map(function (c) { return "<option" + (c === d.klass ? " selected" : "") + ">" + esc(c) + "</option>"; }).join("") + "</select></label>";
    else h += '<div class="sub">goes to Obsidian: Ideas</div>';
    h += '<div class="col">' + d.items.map(function (it, i) {
      if (it.kind === "note") return '<div class="ditem note"><span class="ic">📝</span><div class="col"><input data-dn="' + i + '" data-f="title" value="' + esc(it.title || "") + '" placeholder="note title"><textarea data-dn="' + i + '" data-f="text" rows="4" placeholder="type your note">' + esc(it.text || "") + '</textarea></div><button type="button" data-act="ddel:' + i + '" aria-label="Remove">✕</button></div>';
      return '<div class="ditem"><span class="ic">' + icon[it.kind] + '</span><div class="col"><input data-dl="' + i + '" value="' + esc(it.label || "") + '" placeholder="' + esc(it.kind === "audio" ? "name it (optional)" : "label (optional)") + '"><span class="sub">' + esc(draftName(d, it)) + "</span></div>" +
        (it.kind === "audio" ? "" : '<button type="button" data-act="ddel:' + i + '" aria-label="Remove">✕</button>') + "</div>";
    }).join("") + "</div>" +
      '<div class="grid2"><button type="button" class="tile" data-act="dphoto"><svg viewBox="0 0 24 24"><path d="M4 8h3l2-3h6l2 3h3v11H4z"/><circle cx="12" cy="13" r="3.5"/></svg><b>Add a photo</b><span>' + (d.mode === "ideas" ? "a sketch, a page" : "the board, a handout") + '</span></button>' +
      '<button type="button" class="tile" data-act="dnote"><svg viewBox="0 0 24 24"><path d="M4 20h4L19 9l-4-4L4 16z"/></svg><b>Add a note</b><span>sent with it</span></button></div>' +
      '<div class="rec"><button type="button" class="recbtn send" data-act="dsend">SEND</button><div class="sub">nothing leaves the phone until you press send</div></div>' +
      '<button type="button" class="link danger" data-act="ddiscard">discard this recording</button>';
    var others = drafts.filter(function (x) { return x !== d; });
    if (others.length) h += '<div class="col"><div class="h">Also waiting to send</div>' + others.map(function (x) { return '<button type="button" class="when" data-act="dopen:' + esc(x.id) + '"><span class="w">' + esc((x.mode === "ideas" ? "Idea" : x.klass || "no class") + " · " + new Date(x.started).toLocaleString([], { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })) + '</span><span class="k">' + hms(x.duration) + "</span></button>"; }).join("") + "</div>";
    return h + "</form>";
  }
  function recoverRec() {
    var a = LS.get("rec_active", null);
    if (!a || (rec && rec.id === a.id)) return;
    idbKeys("rec").then(function (keys) {
      if (keys.some(function (k) { return String(k).indexOf(a.id + ":") === 0; }) || (a.photos || []).length) {
        finishRec(a.id, a);
      } else LS.set("rec_active", null);
    });
  }

  // ----- chat, articles, world ------------------------------------------------------------------------------------
  function ask(q) {
    q = (q || "").trim(); if (!q) return;
    var hist = chat.filter(function (m) { return !m.queued; }).slice(-6).map(function (m) { return { role: m.role, text: m.text }; });
    var m = { role: "user", text: q, at: Date.now() / 1000, qid: rid() }; chat.push(m); save(); sub.chatBusy = true; render();
    op({ op: "chat", q: q, history: hist }, 200000).then(function (r) { answer(m, r); }, function () { m.queued = true; save(); })
      .then(function () { sub.chatBusy = false; render(); scrollEnd(); });
  }
  function answer(m, r) { delete m.queued; chat.push({ role: "archie", text: r.ok ? (r.answer || "(no answer)") : "(Archie couldn't answer: " + r.error + ")", at: Date.now() / 1000 }); save(); }
  function drainChat() {
    var q = chat.filter(function (m) { return m.queued; });
    return q.reduce(function (p, m) {
      return p.then(function () {
        var i = chat.indexOf(m), hist = chat.slice(0, i).filter(function (x) { return !x.queued; }).slice(-6).map(function (x) { return { role: x.role, text: x.text }; });
        return op({ op: "chat", q: m.text, history: hist }, 200000).then(function (r) { answer(m, r); toast("Archie answered: " + (r.answer || "").slice(0, 90)); render(false); });
      });
    }, Promise.resolve());
  }
  function scrollEnd() { var m = $("main"); m.scrollTop = m.scrollHeight; }
  function fetchArticles() {
    var rels = (S.saved || []).map(function (s) { return s.md; }).filter(Boolean).slice(0, 60);
    var missing = rels.filter(function (r) { return !meta.articles[r]; }).slice(0, 20);
    if (!missing.length) return Promise.resolve();
    return op({ op: "articles", want: missing }, 90000).then(function (r) {
      var a = r.articles || {};
      return Promise.all(Object.keys(a).map(function (rel) { meta.articles[rel] = 1; return idbPut("articles", rel, a[rel]); })).then(save);
    });
  }
  function gunzip(b64) {
    var bin = atob(b64), bytes = new Uint8Array(bin.length); for (var i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    var ds = new Blob([bytes]).stream().pipeThrough(new DecompressionStream("gzip"));
    return new Response(ds).text().then(JSON.parse);
  }
  function loadWorld() { return W ? Promise.resolve(W) : idbGet("world", "pack").then(function (p) { W = p || null; return W; }); }
  function fetchWorld(force) {
    var now = Date.now() / 1000;
    if (!force && now - (meta.world_at || 0) < 1800) return Promise.resolve();
    var govs = !meta.govs_at || now - meta.govs_at > (force ? 6 * 3600 : 86400);
    return op({ op: "world", govs: govs }, 120000).then(function (r) {
      if (!r.ok || !r.gz) return;
      return Promise.all([gunzip(r.gz), loadWorld()]).then(function (x) {
        var pack = x[0], old = x[1] || {};
        if (!pack.govs && old.govs) pack.govs = old.govs; else if (pack.govs) meta.govs_at = now;
        meta.world_at = now; W = pack; save(); if (tab === "news") render(false);
        return idbPut("world", "pack", pack);
      });
    });
  }
  function flagImg(iso2, h) {
    var key = "flag:" + iso2, id = "f" + rid();
    idbGet("world", key).then(function (svg) {
      if (svg) return svg;
      if (status.state !== "home") return null;
      return op({ op: "flag", iso: iso2 }, 8000).then(function (r) { if (r.ok) { idbPut("world", key, r.svg); return r.svg; } return null; }).catch(function () { return null; });
    }).then(function (svg) { var el = document.getElementById(id); if (el && svg) el.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(svg); });
    return '<img class="flag" id="' + id + '" style="height:' + h + 'px" alt="">';
  }

  // ----- markdown for notes and saved articles -------------------------------------------------------------------------
  function inline(s) {
    return esc(s).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/\[\[([^\]|]+)(?:\|([^\]]+))?\]\]/g, function (_, a, b) { return "<i>" + (b || a) + "</i>"; })
      .replace(/\[([^\]]+)\]\((https?:[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
  }
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

  // ----- screens --------------------------------------------------------------------------------------------------------------
  function taskRow(t) {
    return '<label class="check' + (t.done ? " done" : "") + '"><input type="checkbox" data-task="' + esc(t.text) + '"' + (t.done ? " checked" : "") + "><span>" + esc(t.text) + "</span>" +
      (t.due ? '<span class="due">' + dayLabel(t.due) + "</span>" : "") + "</label>";
  }
  // ----- "since you last opened": what happened on the PC (and the calendar) while the app was closed -------------
  var sinceFrom = meta.lastSeen || Date.now() / 1000, calSince = meta.calSig || null;
  function calSig() { var o = {}; (S.calendar || []).forEach(function (e) { o[e.id] = [e.title, e.date, e.time || ""].join("|"); }); return o; }
  function markSeen() { meta.lastSeen = Date.now() / 1000; meta.calSig = calSig(); save(); }
  function sinceBox() {
    var acts = (S.activity || []).filter(function (a) { return a.at > sinceFrom; }), rows = [];
    var mail = acts.filter(function (a) { return a.kind === "mail"; });
    if (mail.length) rows.push({ i: "✉", t: mail.length === 1 ? mail[0].text : mail.length + " emails that matter · " + mail[mail.length - 1].text, go: "mail" });
    acts.filter(function (a) { return a.kind === "filed"; }).slice(-3).forEach(function (a) { rows.push({ i: "↓", t: a.text }); });
    acts.filter(function (a) { return a.kind === "lecture"; }).slice(-3).forEach(function (a) { rows.push({ i: "✎", t: a.text }); });
    if (calSince) (S.calendar || []).forEach(function (e) {
      var was = calSince[e.id], now = [e.title, e.date, e.time || ""].join("|");
      if (was === now) return;
      var when = dayLabel(e.date) + (e.time ? " " + clock(e.time) : "");
      rows.push({ i: "◷", t: (was ? e.title + " moved to " : e.title + " added · ") + when, go: "cal", ev: e.id, day: e.date });
    });
    if (!rows.length) return "";
    var ago = Math.max(1, Math.round((Date.now() / 1000 - sinceFrom) / 60)), agoT = ago < 60 ? ago + " min" : ago < 2880 ? Math.round(ago / 60) + " h" : Math.round(ago / 1440) + " days";
    return '<div class="since"><div class="sh">SINCE YOU LAST OPENED · ' + agoT + " AGO</div>" + rows.slice(0, 6).map(function (r) {
      return '<div class="sr' + (r.go ? " tap" : "") + '"' + (r.go ? ' data-go="' + r.go + '"' + (r.ev ? ' data-ev="' + esc(r.ev) + '" data-day="' + esc(r.day) + '"' : "") : "") + '><span class="si">' + r.i + '</span><span class="st">' + esc(r.t) + "</span>" + (r.go ? '<span class="sa">›</span>' : "") + "</div>";
    }).join("") + "</div>";
  }
  function whenRow(x, showDay) {
    return '<div class="when tap" data-go="cal" data-ev="' + esc(x.e.id || "") + '" data-day="' + esc(x.date) + '"><span class="d">' + (showDay ? dayLabel(x.date) : (clock(x.e.time) || "all day")) + '</span><span class="w">' + esc(x.e.title) + (showDay && x.e.time ? " · " + clock(x.e.time) : "") + '</span><span class="k">' + esc(x.e.kind || "") + "</span></div>";
  }
  function waitingAdds() {
    var q = pending.filter(function (c) { return c.type === "quick_add"; });
    return q.length ? '<div class="col"><div class="h">Waiting for your PC</div>' + q.map(function (c) { return '<div class="when"><span class="w">' + esc(c.text) + '</span><span class="k">adding</span></div>'; }).join("") + "</div>" : "";
  }
  var V = {
    today: function () {
      var d = new Date(), hr = d.getHours(), h = "", today = iso(d), k = currentClass();
      h += "<div><h1>" + (hr < 12 ? "Good morning" : hr < 18 ? "Good afternoon" : "Good evening") + '</h1><div class="sub">' + d.toLocaleDateString([], { weekday: "long", month: "long", day: "numeric" }) + "</div></div>";
      if (status.state === "away" && !meta.last_ok) h += '<div class="warn">' + esc(status.msg) + "</div>";
      h += sinceBox();
      if (k) h += '<a class="card now" href="#class"><div class="h" style="color:var(--blue)">' + (k.kind === "lab" ? "Lab" : "Class") + ' now</div><div class="t">' + esc(k.title) + '</div><div class="sub">until ' + k.until.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }) + " · tap to record</div></a>";
      var next = (S.deadlines || []).filter(function (x) { return daysTo(x.date) >= 0; })[0];
      if (next) { var n = daysTo(next.date); h += '<div class="count tap" data-go="todo"><span>' + esc(next.what) + "</span><b>" + (n === 0 ? "today" : n === 1 ? "tomorrow" : n + " days") + "</b></div>"; }
      var todays = occurrences(d, 0);
      h += '<div class="col"><a class="h hlink" href="#cal">Today ›</a>' + (todays.length ? todays.map(function (x) { return whenRow(x, false); }).join("") : '<p class="note">Nothing on the calendar today.</p>') + "</div>";
      var dueT = (S.tasks || []).filter(function (t) { return !t.done && t.due && t.due <= today; }), dls = (S.deadlines || []).filter(function (x) { var n = daysTo(x.date); return n >= 0 && n <= 1; });
      if (dueT.length || dls.length) h += '<div class="col"><a class="h hlink" href="#todo">Due ›</a>' + dls.map(function (x) { return '<div class="when tap" data-go="todo"><span class="d">' + (daysTo(x.date) ? "tomorrow" : "today") + '</span><span class="w">' + esc(x.what) + "</span></div>"; }).join("") + dueT.map(taskRow).join("") + "</div>";
      var open = (S.tasks || []).filter(function (t) { return !t.done && !(t.due && t.due <= today); }).slice(0, 10);
      if (open.length) h += '<div><a class="h hlink" href="#todo">To-do ›</a>' + open.map(taskRow).join("") + "</div>";
      h += waitingAdds();
      var soon = occurrences(new Date(Date.now() + 86400000), 6).slice(0, 6);
      if (soon.length) h += '<div class="col"><a class="h hlink" href="#cal">This week ›</a>' + soon.map(function (x) { return whenRow(x, true); }).join("") + "</div>";
      var b = S.brief || {}, take = b.take || {};
      if (take.world) h += '<a class="card" href="#news"><div class="h">News</div><div class="take">' + esc(take.world.slice(0, 260)) + (take.world.length > 260 ? "…" : "") + '</div><div class="sub" style="margin-top:6px">full brief →</div></a>';
      return h;
    },
    class: function () {
      var k = currentClass(), classes = classNames(), picked = sub.klass !== undefined ? sub.klass : (k ? k.title : "");
      var dr = drafts.filter(function (x) { return x.id === sub.draft; })[0] || (!rec && drafts[0]);
      if (!rec && dr) return draftView(dr);
      if (rec) {
        var h = '<div class="rec"><div class="sub">' + (rec.stopping ? "saving…" : rec.paused ? "paused" : "recording") + (rec.mode === "ideas" ? " · idea" : rec.klass ? " · " + esc(rec.klass) : "") + '</div>' +
          '<div class="timer' + (rec.paused ? " paused" : "") + '" id="timer">' + hms(recElapsed()) + '</div><div class="level"><i id="lvl"></i></div>' +
          '<div class="recrow">' +
          '<button data-act="pause"><svg viewBox="0 0 24 24">' + (rec.paused ? '<path d="M7 5l12 7-12 7z"/>' : '<path d="M8 5v14M16 5v14"/>') + "</svg>" + (rec.paused ? "Resume" : "Pause") + "</button>" +
          '<button data-act="mark"><svg viewBox="0 0 24 24"><path d="M6 3h12v18l-6-4-6 4z"/></svg>Mark</button>' +
          '<button data-act="photo"><svg viewBox="0 0 24 24"><path d="M4 8h3l2-3h6l2 3h3v11H4z"/><circle cx="12" cy="13" r="3.5"/></svg>Board</button>' +
          '<button data-act="say"><svg viewBox="0 0 24 24"><path d="M4 20h4L19 9l-4-4L4 16z"/></svg>Note</button></div>' +
          '<form id="markform" class="classpick" hidden><input id="marktext" placeholder="What just happened? (exam topic, homework…)" autocomplete="off"><button class="btn">add</button></form>' +
          '<button class="recbtn on" data-act="stop">STOP</button>' +
          (rec.marks.length ? '<div class="marks"><div class="h">Marked</div>' + rec.marks.slice().reverse().map(function (m) { return '<div class="mark"><b>' + hms(m.t) + "</b><span>" + esc(m.label || "marked") + "</span></div>"; }).join("") + "</div>" : "") +
          '<p class="note">Keep Archie open while you record; the screen stays on. Every 10 seconds is saved on your phone, so nothing is lost if the app closes.</p></div>';
        return h;
      }
      var ideas = sub.mode === "ideas";
      var seg = '<div class="seg"><button data-act="mode:lecture" aria-selected="' + !ideas + '">Lecture</button><button data-act="mode:ideas" aria-selected="' + ideas + '">Ideas</button></div>';
      if (ideas) {
        var hi = seg + '<div><h1>Ideas</h1><div class="sub">talk it through; Archie types it out and tidies it into an idea note in Obsidian: Ideas</div></div>' +
          '<div class="rec"><button class="recbtn idea" data-act="rec">RECORD</button><div class="sub">stop when you\'re done: you can add a photo or a note, name it, then send</div></div>';
        return hi + sentList();
      }
      var h2 = seg + '<div><h1>Class</h1><div class="sub">' + (k ? (k.kind === "lab" ? "lab" : "class") + " now: " + esc(k.title) : "no class on the calendar right now") + "</div></div>" +
        '<label class="l">Filed under<select id="klass"><option value="">no class (Voice inbox)</option>' + classes.map(function (c) { return "<option" + (c === picked ? " selected" : "") + ">" + esc(c) + "</option>"; }).join("") + "</select></label>" +
        '<div class="rec"><button class="recbtn" data-act="rec">RECORD</button><div class="sub">Archie types it out and makes the lecture notes in Obsidian: Lectures/' + esc(picked || "…") + "</div></div>" +
        '<div class="grid2"><button class="tile" data-act="photo"><svg viewBox="0 0 24 24"><path d="M4 8h3l2-3h6l2 3h3v11H4z"/><circle cx="12" cy="13" r="3.5"/></svg><b>Snap the board</b><span>photo into the class folder</span></button>' +
        '<button class="tile" data-act="write"><svg viewBox="0 0 24 24"><path d="M4 20h4L19 9l-4-4L4 16z"/></svg><b>Write notes</b><span>typed, filed under the class</span></button></div>';
      return h2 + sentList();
    },
    add: function () {
      if (scan) return scanView();
      var h = '<div><h1>Add</h1><div class="sub">anything: plans, to-dos, deadlines, links, thoughts</div></div>' +
        '<form id="quickform"><input id="quick" placeholder="dentist fri 3pm · essay due friday · a link" autocomplete="off" enterkeyhint="done"><button class="btn wide">add</button></form>' +
        '<div class="chips">' + ["call mom", "bio exam dec 12 9am", "essay due friday", "note: "].map(function (x) { return '<button class="chip" data-ex="' + esc(x) + '">' + esc(x) + "</button>"; }).join("") + "</div>" +
        (sub.clip ? '<div class="card"><div class="h">Copied link</div><div class="row"><span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">' + esc(sub.clip) + '</span><button class="btn" data-act="saveclip">save</button></div></div>' : "") +
        '<button class="tile scantile" data-act="scan"><svg viewBox="0 0 24 24"><path d="M4 8V5h3M17 5h3v3M20 16v3h-3M7 19H4v-3M4 12h16"/></svg><b>Scan a handout</b><span>pages → one clean PDF, filed to its class</span></button>' +
        '<div class="grid2"><button class="tile" data-act="paste"><svg viewBox="0 0 24 24"><rect x="6" y="4" width="12" height="17" rx="2"/><path d="M9 4h6v3H9z"/></svg><b>Paste</b><span>a copied link or text</span></button>' +
        '<button class="tile" data-act="photo"><svg viewBox="0 0 24 24"><path d="M4 8h3l2-3h6l2 3h3v11H4z"/><circle cx="12" cy="13" r="3.5"/></svg><b>Photo</b><span>to Obsidian</span></button>' +
        '<button class="tile" data-act="file"><svg viewBox="0 0 24 24"><path d="M6 3h8l4 4v14H6z"/><path d="M14 3v4h4"/></svg><b>File</b><span>PDFs, slides, anything</span></button>' +
        '<button class="tile" data-act="write"><svg viewBox="0 0 24 24"><path d="M4 20h4L19 9l-4-4L4 16z"/></svg><b>Note</b><span>a longer note</span></button></div>' +
        '<p class="note">From any app: Share → Archie. Links become saved articles, files go to Obsidian, text becomes a note.</p>';
      return askCard() + h + waitingAdds();
    },
    news: function () {
      var subs = [["brief", "Brief"], ["stories", "Stories"], ["govs", "Governments"]], s = sub.news || "brief";
      var h = '<div class="row"><h1>News</h1><button class="btn ghost" data-act="newsrefresh">' + (sub.newsBusy ? '<span class="spin"></span>' : "refresh") + "</button></div>" +
        '<div class="seg">' + subs.map(function (x) { return '<button data-news="' + x[0] + '" aria-selected="' + (s === x[0]) + '">' + x[1] + "</button>"; }).join("") + "</div>";
      if (s === "brief") {
        var b = S.brief || {}, take = b.take || {}, ed = b.edition;
        h += '<div class="sub">' + (b.global ? (ed && ed.at ? "edition " + new Date(ed.at * 1000).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }) + " · " : "") + "from your PC · readable offline" : "the brief comes with the first sync") + "</div>";
        if (take.world) h += '<div><div class="h neon">The world</div><div class="take">' + takeHtml(take.world) + "</div></div>";
        if (take.home) h += '<div><div class="h neon">At home</div><div class="take">' + takeHtml(take.home) + "</div></div>";
        window._st = [];
        [["Around the world", b.global], ["At home", b.home], ["Close to home", b.local]].forEach(function (sec) {
          if (!sec[1] || !sec[1].length) return;
          h += '<div><div class="h neon">' + sec[0] + "</div>" + sec[1].map(function (st) { window._st.push({ title: st.t, items: (st.src || []).map(function (x) { return { url: x.url, source: x.source || x.name }; }), last: st.last }); var i = window._st.length - 1, src = (st.src || [])[0] || {};
            return '<div class="story"><div class="t">' + esc(st.t) + '</div><div class="m">' + esc([st.n + " outlets", st.place || "", ago(st.last)].filter(Boolean).join(" · ")) + '</div><div class="a"><button data-save="' + i + '">save</button>' + (src.url ? '<a href="' + esc(src.url) + '" target="_blank" rel="noopener">read ↗</a>' : "") + "</div></div>"; }).join("") + "</div>";
        });
        return h;
      }
      if (!W) { loadWorld().then(function (w) { if (w) render(false); }); return h + '<p class="note">' + (meta.world_at ? "Loading…" : "Stories and governments come from your PC with the next sync.") + "</p>"; }
      if (s === "stories") {
        var regions = []; (W.stories || []).forEach(function (x) { if (x.region && regions.indexOf(x.region) < 0) regions.push(x.region); });
        var list = (W.stories || []).filter(function (x) { return !sub.region || x.region === sub.region; }).slice(0, 120);
        window._st = [];
        return h + '<div class="row"><div class="sub">as of ' + new Date(W.at * 1000).toLocaleString([], { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }) + '</div><select id="region" style="width:auto"><option value="">all regions</option>' + regions.sort().map(function (r) { return "<option" + (r === sub.region ? " selected" : "") + ">" + esc(r) + "</option>"; }).join("") + "</select></div>" +
          "<div>" + list.map(function (st) { window._st.push(st); var i = window._st.length - 1, it = st.items || [];
            return '<div class="story"><div class="t">' + esc(st.title) + '</div><div class="m">' + esc([st.n + " sources", st.place || "", ago(st.last)].filter(Boolean).join(" · ")) + "</div>" +
              (it[0] && it[0].summary && it[0].summary !== st.title ? '<div class="s">' + esc(it[0].summary.slice(0, 200)) + "</div>" : "") +
              '<div class="a">' + it.slice(0, 4).map(function (x) { return x.url ? '<a href="' + esc(x.url) + '" target="_blank" rel="noopener">' + esc(x.source) + " ↗</a>" : ""; }).join("") + '<button data-save="' + i + '">save</button></div></div>'; }).join("") + "</div>";
      }
      var govs = (W.govs || []).filter(function (c) { return c.name; }).sort(function (a, b) { return a.name.localeCompare(b.name); });
      if (sub.iso) {
        var c = govs.filter(function (x) { return x.iso2 === sub.iso; })[0];
        if (!c) { sub.iso = null; return V.news(); }
        var names = function (L) { return (L || []).map(function (p) { return esc(p.name) + (p.since ? ' <span class="dim">since ' + esc(String(p.since).slice(0, 7)) + "</span>" : ""); }).join("<br>") || '<span class="dim">unknown</span>'; };
        return h + '<button class="chip" data-act="govback">← all countries</button><div class="row" style="justify-content:flex-start;gap:14px">' + flagImg(c.iso2, 34) + "<div><h2>" + esc(c.name) + '</h2><div class="sub">' + esc(c.label || "") + (c.capital ? " · " + esc(c.capital) : "") + "</div></div></div>" +
          '<div class="card"><div class="h">' + esc(c.hosOffice || "Head of state") + "</div>" + names(c.hos) + '</div><div class="card"><div class="h">' + esc(c.hogOffice || "Head of government") + "</div>" + names(c.hog) + "</div>" +
          (c.cabinet || []).map(function (gr) { return '<div class="card"><div class="h">' + esc(gr.label || "Cabinet") + "</div>" + (gr.people || []).map(function (p) { return '<div class="cab"><span class="dim">' + esc(p.title || "") + "</span><span>" + esc(p.name || "") + "</span></div>"; }).join("") + "</div>"; }).join("") +
          (c.intro ? '<div class="card"><div class="h">Background</div><div class="reader">' + esc(c.intro).replace(/\n\n/g, "<br><br>") + "</div></div>" : "");
      }
      var f = (sub.gq || "").toLowerCase();
      return h + '<form onsubmit="return false"><input id="gq" placeholder="search countries or leaders" value="' + esc(sub.gq || "") + '" autocomplete="off"></form>' +
        '<div class="list" id="gl">' + govs.map(function (c) { var lead = (c.hos || []).concat(c.hog || []).map(function (p) { return p.name; }).join(", ");
          return '<button class="li" data-iso="' + esc(c.iso2) + '" data-s="' + esc((c.name + " " + lead).toLowerCase()) + '"' + (f && (c.name + " " + lead).toLowerCase().indexOf(f) < 0 ? " hidden" : "") + "><span>" + esc(c.name) + '</span><span class="m">' + esc(lead.slice(0, 40)) + "</span></button>"; }).join("") + "</div>";
    },
    more: function () {
      var page = sub.more || "";
      if (page === "cal") return back() + calView();
      if (page === "todo") return back() + todoView();
      if (page === "notes") return back() + notesView();
      if (page === "saved") return back() + savedView();
      if (page === "settings") return back() + settingsView();
      if (page === "mail") return back() + mailView();
      if (page === "shelf") return back() + shelfView();
      var items = [["cal", "Calendar", "next 45 days · add events"], ["todo", "To-do & deadlines", (S.tasks || []).filter(function (t) { return !t.done; }).length + " open"],
        ["mail", "Mail", (S.mail_cards || []).length ? (S.mail_cards || []).length + " to look at" : "nothing new"],
        ["notes", "Notes", Object.keys(notes).length + " on this phone"], ["shelf", "Shelf", "flashcards & exams with Feather"], ["saved", "Saved articles", "readable offline"], ["settings", "Settings & notifications", status.state === "home" ? "connected to " + (S.pc || "your PC") : "not connected"]];
      return '<h1>More</h1><div class="list">' + items.map(function (x) { return '<button class="li" data-more="' + x[0] + '"><span>' + x[1] + '</span><span class="m">' + esc(x[2]) + "</span></button>"; }).join("") + "</div>" +
        '<a class="card" href="#chat"><div class="h">Ask Archie</div><div>Answered by your PC. Questions wait here when it isn\'t reachable.</div></a>';
    },
    chat: function () {
      var h = '<div class="row"><h1>Ask Archie</h1>' + (chat.length ? '<button class="chip" data-act="clearchat">clear</button>' : "") + "</div>";
      if (status.state !== "home") h += '<div class="warn">Your PC isn\'t reachable right now. Ask anyway: questions wait on your phone and get answered when it is.</div>';
      h += '<div class="col" style="gap:10px">' + chat.slice(-60).map(function (m) { return '<div class="msg ' + (m.role === "user" ? "me" : "ai") + '">' + esc(m.text) + (m.queued ? '<span class="q">waiting for your PC</span>' : "") + "</div>"; }).join("") +
        (sub.chatBusy ? '<div class="sub">Archie is thinking on ' + esc(S.pc || "your PC") + "…</div>" : "") + "</div>";
      return h + '<form id="chatform" class="chatbar"><input id="askq" placeholder="Ask Archie…" autocomplete="off" enterkeyhint="send"><button class="btn">ask</button></form>';
    }
  };
  function back() { return '<button class="chip" data-more="">← more</button>'; }
  // ----- Shelf: Archie's flashcards and mock exams next to Feather's; moves only when you tap ----------------
  var shelfData = null, shelfBusy = false, shelfErr = "";
  function shelfLoad() {
    if (shelfBusy) return; shelfBusy = true; shelfErr = "";
    op({ op: "shelf" }, 20000).then(function (r) { if (r.ok) shelfData = r; else shelfErr = r.error || "your PC couldn't read the shelf"; },
      function (e) { shelfErr = e.message; }).then(function () { shelfBusy = false; if (tab === "more" && sub.more === "shelf") render(false); });
  }
  function shelfView() {
    if (!shelfData && !shelfBusy && !shelfErr) shelfLoad();
    var h = '<div class="row"><h1>Shelf</h1><button class="chip" data-act="shelfre">refresh</button></div>' +
      '<div class="sub">Nothing moves on its own. A send or get happens at the next sync with your phone or a laptop; the old copy is kept in the history.</div>';
    if (shelfErr) return h + '<div class="warn">' + esc(shelfErr) + "</div>";
    if (!shelfData) return h + '<div class="sub">asking ' + esc(S.pc || "your PC") + "…</div>";
    var D = shelfData, bt = function (label, a) { return '<button class="chip" ' + a + ">" + label + "</button>"; },
      at = function (o) { return Object.keys(o).map(function (k) { return "data-" + k + '="' + esc(String(o[k])) + '"'; }).join(" "); };
    h += '<div class="card"><div class="h">Flashcards in Archie</div>' + (D.decks.length ? D.decks.map(function (d) {
      return '<div class="shr"><div><b>' + esc(d.name) + '</b><div class="sub">' + d.n + " cards · " + d.due + " due · " + esc(d.st) + "</div></div><div>" +
        bt("send", at({ sh: "a2f", n: d.name })) + bt("clean copy", at({ sh: "a2f", n: d.name, clean: 1 })) + (d.inf ? bt("get Feather's", at({ sh: "f2a", n: d.fname })) : "") + "</div></div>"; }).join("")
      : '<div class="sub">No decks yet.</div>') + "</div>";
    if (D.fonly.length) h += '<div class="card"><div class="h">Only in Feather</div>' + D.fonly.map(function (d) {
      return '<div class="shr"><div><b>' + esc(d.name) + '</b><div class="sub">' + d.n + " cards</div></div><div>" + bt("request", at({ sh: "f2a", n: d.name })) + "</div></div>"; }).join("") + "</div>";
    h += '<div class="card"><div class="h">Mock exams</div>' + (D.exams.length ? D.exams.map(function (e) {
      return '<div class="shr"><div><b>' + esc(e.title) + '</b><div class="sub">' + e.q + " questions · " + (e.best == null ? "not taken yet" : "best " + e.best + "%") + (e.st ? " · " + esc(e.st) : "") + "</div></div><div>" +
        bt("send", at({ sh: "a2f", n: e.title, kind: "exam", eid: e.id })) + (e.inf ? bt("get Feather's", at({ sh: "f2a", n: e.title, kind: "exam", eid: e.id })) : "") + "</div></div>"; }).join("")
      : '<div class="sub">No mock exams yet.</div>') + D.xonly.map(function (e) {
      return '<div class="shr"><div><b>' + esc(e.title) + '</b><div class="sub">only in Feather</div></div><div>' + bt("request", at({ sh: "f2a", n: e.title, kind: "exam", eid: e.id })) + "</div></div>"; }).join("") + "</div>";
    if (D.hist.length) h += '<div class="card"><div class="h">History</div>' + D.hist.map(function (x) {
      return '<div class="shr"><div><b>' + esc(x.name) + '</b><div class="sub">' + (x.side === "archie" ? "Archie's" : "Feather's") + " copy · " + (x.kind === "exam" ? x.n + " questions" : x.n + " cards") + " · " + ago(x.t) + "</div></div><div>" +
        bt("put it back", at({ sh: "restore", n: x.name, hid: x.id })) + "</div></div>"; }).join("") + "</div>";
    return h;
  }
  function bindShelf(m) {
    var re = m.querySelector('[data-act="shelfre"]'); if (re) re.onclick = function () { shelfData = null; shelfErr = ""; shelfLoad(); render(false); };
    m.querySelectorAll("[data-sh]").forEach(function (x) { x.onclick = function () {
      var d = x.dataset, words = { a2f: "Send “" + d.n + "” to Feather? It replaces Feather's copy", f2a: "Get Feather's “" + d.n + "”? It replaces Archie's copy", restore: "Put back this version of “" + d.n + "”?" };
      if (!confirm(words[d.sh] + (d.sh === "restore" ? "" : " (the old one is kept).") )) return;
      x.disabled = true;
      op({ op: "shelf_do", act: d.sh, name: d.n, kind: d.kind || "", eid: d.eid || "", clean: !!d.clean, hid: d.hid || "" }, 20000).then(function (r) {
        if (!r.ok) throw new Error(r.error || "didn't work"); x.textContent = "queued ✓"; toast("Queued · happens at the next sync with Feather");
      }).catch(function (e) { x.disabled = false; toast(e.message); });
    }; });
  }
  function calView() {
    var list = occurrences(new Date(), 45), kinds = ["event", "class", "lab", "exam", "test", "quiz", "due"];
    return "<h1>Calendar</h1>" +
      '<form id="calform"><input name="title" required placeholder="What"><div class="f2"><input name="date" type="date" required value="' + iso(new Date()) + '"><input name="time" type="time"></div>' +
      '<div class="f2"><select name="kind">' + kinds.map(function (k) { return "<option>" + k + "</option>"; }).join("") + '</select><select name="repeat"><option value="">once</option><option value="weekly">every week</option></select></div><button class="btn">add to calendar</button></form>' +
      '<div class="col">' + (list.length ? list.map(function (x) { var hi = sub.calFocus && sub.calFocus.id === x.e.id && sub.calFocus.day === x.date, ed = sub.calEdit && sub.calEdit.id === x.e.id && sub.calEdit.day === x.date; return '<div class="when tap' + (hi || ed ? " hi" : "") + '"' + (hi ? ' id="calhi"' : "") + ' data-edit="' + esc(x.e.id) + '" data-day="' + esc(x.date) + '"><span class="d">' + dayLabel(x.date) + '</span><span class="w">' + esc(x.e.title) + (x.e.time ? " · " + clock(x.e.time) : "") + (x.e.repeat ? " ↻" : "") + '</span><button data-del="' + esc(x.e.id) + '" aria-label="Delete">✕</button></div>' + (ed ? editSheet(x.e) : ""); }).join("") : '<p class="note">Nothing in the next 45 days.</p>') + "</div>";
  }
  // ----- email cards: the mail Archie made a card for on the PC (school, files, dates) ---------------------
  function mailView() {
    var cards = S.mail_cards || [];
    if (!cards.length) return '<h1>Mail</h1><p class="note">Nothing waiting. School mail, mail with files and mail with dates show up here (and on the PC).</p>';
    return "<h1>Mail</h1>" + cards.map(mailCard).join("");
  }
  function mailCard(m) {
    var d = m.date ? new Date(m.date) : null, filing = sub.mailFile && sub.mailFile.id === m.id ? sub.mailFile : null;
    var h = '<div class="card mailcard' + (m.prof ? " prof" : "") + '"><div class="mk"><b>✉ GMAIL</b> · ' + (d ? esc(d.toLocaleString([], { weekday: "short", hour: "numeric", minute: "2-digit" })) + " · " : "") + esc((m.why || []).join(", ")) + "</div>" +
      '<div class="mf">' + esc(m.from || "") + '</div><div class="ms">' + esc(m.subject || "") + "</div>" + (m.snippet ? '<div class="mp">' + esc(m.snippet) + "</div>" : "");
    if ((m.files || []).length) {
      h += '<div class="il">ATTACHMENTS · TAP ONE TO FILE IT</div>';
      m.files.forEach(function (f) {
        h += '<button class="mfile" data-mfile="' + esc(m.id) + "|" + f.n + '"' + (f.filed ? " disabled" : "") + '><span>📎 ' + esc(f.name) + '</span><span class="m">' + (f.filed ? "✓ " + esc(f.filed) : mbs(f.size)) + "</span></button>";
        if (filing && filing.n === f.n && !f.filed) {
          var classes = classNames(); if (filing.klass && classes.indexOf(filing.klass) < 0) classes.unshift(filing.klass);
          h += '<form id="mailfile" class="mfform" onsubmit="return false"><label class="l">Name<span class="iname"><input id="mfname" value="' + esc(filing.name) + '"><b>' + esc(splitName(f.name)[1]) + "</b></span></label>" +
            '<div class="il">WHAT IS IT</div><div class="chips">' + KINDS.map(function (k) { return '<button type="button" class="chip' + (k === filing.kind ? " on" : "") + '" data-mkind="' + esc(k) + '">' + esc(k) + "</button>"; }).join("") + "</div>" +
            '<div class="il">CLASS</div><div class="chips">' + classes.concat([""]).map(function (k) { return '<button type="button" class="chip' + (k === filing.klass ? " on" : "") + '" data-mklass="' + esc(k) + '">' + esc(k || "no class") + "</button>"; }).join("") + "</div>" +
            '<div class="il">SAVE TO</div><div class="idest">' + esc(destFor(filing.kind, filing.klass) + "/" + renamed(f.name, filing.name)) + "</div>" +
            '<div class="row"><button type="button" class="btn" data-act="mailfile">File it</button><button type="button" class="btn ghost" data-act="mailfilecancel">Not now</button></div></form>';
        }
      });
    }
    h += '<div class="row mrow">' + (m.body ? '<button class="btn ghost" data-mdates="' + esc(m.id) + '">Find dates on PC</button>' : "") +
      (m.link ? '<a class="btn ghost" href="' + esc(m.link) + '" target="_blank" rel="noopener">Open in Gmail</a>' : "") +
      '<button class="btn ghost" data-mdone="' + esc(m.id) + '">Done</button></div></div>';
    return h;
  }
  function bindMail(m) {
    m.querySelectorAll("[data-mfile]").forEach(function (x) { x.onclick = function () {
      var p = x.dataset.mfile.split("|"), card = (S.mail_cards || []).filter(function (c) { return c.id === p[0]; })[0]; if (!card) return;
      var f = card.files.filter(function (y) { return y.n === +p[1]; })[0], k = currentClass(), kl = k ? k.title : "";
      sub.mailFile = sub.mailFile && sub.mailFile.id === card.id && sub.mailFile.n === f.n ? null : { id: card.id, n: f.n, name: splitName(f.name)[0], kind: guessKind(f.name, kl), klass: kl };
      render();
    }; });
    var nm = $("mfname"); if (nm) nm.oninput = function () { if (sub.mailFile) sub.mailFile.name = nm.value; };
    m.querySelectorAll("[data-mkind]").forEach(function (x) { x.onclick = function () { sub.mailFile.kind = x.dataset.mkind; render(); }; });
    m.querySelectorAll("[data-mklass]").forEach(function (x) { x.onclick = function () { sub.mailFile.klass = x.dataset.mklass; render(); }; });
    m.querySelectorAll("[data-mdates]").forEach(function (x) { x.onclick = function () { change({ type: "mail_dates", id: x.dataset.mdates }); toast("Sent · its dates show up on your PC to tick"); }; });
    m.querySelectorAll("[data-mdone]").forEach(function (x) { x.onclick = function () { change({ type: "mail_done", id: x.dataset.mdone }); }; });
  }
  // ----- scan a handout: camera → find the page → straighten → clean → PDF → the inbox (same filing as everything) -----
  var scan = null;
  function scanStamp(d) { var h = d.getHours(); return d.getFullYear() + "-" + ("0" + (d.getMonth() + 1)).slice(-2) + "-" + ("0" + d.getDate()).slice(-2) + " " + (h % 12 || 12) + "." + ("0" + d.getMinutes()).slice(-2) + " " + (h < 12 ? "AM" : "PM"); }
  function confirmDiscard() { var b = $("scandiscard"); if (b) return true; sub.scanAsk = true; toast("Tap discard again to throw away the scanned pages"); var t = document.querySelector('[data-act="scanclose"]'); if (t) { t.id = "scandiscard"; t.textContent = "tap again"; } return false; }
  function scanStop() { if (scan && scan.stream) { scan.stream.getTracks().forEach(function (t) { t.stop(); }); scan.stream = null; } }
  function scanStart() {
    var k = currentClass();
    scan = { stage: "camera", pages: [], name: "", kind: "slides / handout", klass: k ? k.title : "", stream: null, busy: false };
    scanCam(); render();
  }
  function scanCam() {
    if (!scan || scan.stage !== "camera" || scan.stream || scan.noCam) return;
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) { scan.noCam = true; return render(); }
    navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: "environment" }, width: { ideal: 2560 }, height: { ideal: 1440 } }, audio: false })
      .then(function (st) { if (!scan || scan.stage !== "camera") { st.getTracks().forEach(function (t) { t.stop(); }); return; } scan.stream = st; var v = $("scanv"); if (v) { v.srcObject = st; v.play().catch(function () {}); } })
      .catch(function () { if (scan) { scan.noCam = true; render(); } });
  }
  function scanUseCanvas(cv) {
    scan.shot = cv; scan.quad = ArchieScan.detect(cv); scan.stage = "adjust"; scanStop();
    var sc = Math.min(1, 1000 / Math.max(cv.width, cv.height)), d = document.createElement("canvas");
    d.width = Math.round(cv.width * sc); d.height = Math.round(cv.height * sc); d.getContext("2d").drawImage(cv, 0, 0, d.width, d.height);
    scan.preview = d.toDataURL("image/jpeg", 0.8); render();
  }
  function scanSnap() {
    var v = $("scanv"); if (!v || !v.videoWidth) return toast("The camera isn't ready yet");
    var cv = document.createElement("canvas"); cv.width = v.videoWidth; cv.height = v.videoHeight; cv.getContext("2d").drawImage(v, 0, 0);
    scanUseCanvas(cv);
  }
  function scanPick() {   // no live camera: take the photo with the phone's camera app
    var inp = document.createElement("input"); inp.type = "file"; inp.accept = "image/*"; inp.setAttribute("capture", "environment");
    inp.onchange = function () {
      var f = inp.files && inp.files[0]; if (!f) return;
      var img = new Image(); img.onload = function () { var cv = document.createElement("canvas"); cv.width = img.naturalWidth; cv.height = img.naturalHeight; cv.getContext("2d").drawImage(img, 0, 0); URL.revokeObjectURL(img.src); scanUseCanvas(cv); };
      img.src = URL.createObjectURL(f);
    };
    inp.click();
  }
  function scanKeep() {
    if (scan.busy) return; scan.busy = true; render();
    setTimeout(function () {
      var out = ArchieScan.flatten(scan.shot, scan.quad, 1800);
      out.toBlob(function (b) {
        b.arrayBuffer().then(function (buf) {
          scan.pages.push({ jpeg: new Uint8Array(buf), w: out.width, h: out.height, url: URL.createObjectURL(b) });
          scan.shot = null; scan.preview = null; scan.busy = false; scan.stage = "camera"; render(); scanCam();
        });
      }, "image/jpeg", 0.85);
    }, 30);
  }
  function scanSave() {
    if (!scan.pages.length) return;
    var name = safeName((scan.name || "").trim() || "Scan") + " (" + scanStamp(new Date()) + ").pdf", s0 = scan;
    var blob = ArchieScan.pdf(s0.pages.map(function (p) { return { jpeg: p.jpeg, w: p.w, h: p.h }; }));
    scanStop(); s0.pages.forEach(function (p) { URL.revokeObjectURL(p.url); }); scan = null; render();
    addFile(blob, name, s0.klass || null, Date.now(), { kind: s0.kind, folder: s0.kind === "idea" ? "ideas" : null })
      .then(function () { toast("Saved · " + s0.pages.length + " page" + (s0.pages.length === 1 ? "" : "s") + " → " + destFor(s0.kind, s0.klass)); });
  }
  function scanView() {
    var n = scan.pages.length, h = '<div class="row"><h1>Scan</h1><button class="chip" data-act="scanclose">' + (n ? "discard" : "← back") + "</button></div>";
    if (scan.stage === "adjust") {
      var q = scan.quad, W = scan.shot.width, H = scan.shot.height, r = Math.max(W, H) * 0.035;
      h += '<div class="sub">Drag the corners onto the page\'s corners if they\'re off.</div><div class="scanadj"><img src="' + scan.preview + '" alt="the photo"><svg id="scansvg" viewBox="0 0 ' + W + " " + H + '" preserveAspectRatio="none">' +
        '<polygon id="scanpoly" points="' + q.map(function (p) { return p.join(","); }).join(" ") + '"/>' +
        q.map(function (p, i) { return '<circle class="hdl" data-h="' + i + '" cx="' + p[0] + '" cy="' + p[1] + '" r="' + r + '"/>'; }).join("") + "</svg></div>" +
        '<div class="row"><button class="btn" data-act="scankeep"' + (scan.busy ? " disabled" : "") + ">" + (scan.busy ? "straightening…" : "Use page " + (n + 1)) + '</button><button class="btn ghost" data-act="scanretake">Retake</button></div>';
      return h;
    }
    h += scan.noCam ? '<button class="tile scantile" data-act="scanpick"><svg viewBox="0 0 24 24"><path d="M4 8h3l2-3h6l2 3h3v11H4z"/><circle cx="12" cy="13" r="3.5"/></svg><b>Take a photo of page ' + (n + 1) + '</b><span>lay it on something darker than the paper</span></button>'
      : '<div class="scancam"><video id="scanv" playsinline autoplay muted></video><div class="scanhint">page ' + (n + 1) + ' · lay it on something darker than the paper</div><button class="snap" data-act="snap" aria-label="Take page ' + (n + 1) + '"></button></div>';
    if (n) {
      h += '<div class="scanpages">' + scan.pages.map(function (p, i) { return '<div class="sp"><img src="' + p.url + '" alt="page ' + (i + 1) + '"><button data-sdel="' + i + '" aria-label="Remove page ' + (i + 1) + '">✕</button></div>'; }).join("") + "</div>";
      var classes = classNames(); if (scan.klass && classes.indexOf(scan.klass) < 0) classes.unshift(scan.klass);
      h += '<form id="scanform" class="card askcard" onsubmit="return false"><label class="l">Name<span class="iname"><input id="scanname" value="' + esc(scan.name) + '" placeholder="Lab 3 handout"><b>.pdf</b></span></label>' +
        '<div class="il">WHAT IS IT</div><div class="chips">' + KINDS.map(function (k) { return '<button type="button" class="chip' + (k === scan.kind ? " on" : "") + '" data-skind="' + esc(k) + '">' + esc(k) + "</button>"; }).join("") + "</div>" +
        '<div class="il">CLASS</div><div class="chips">' + classes.concat([""]).map(function (k) { return '<button type="button" class="chip' + (k === scan.klass ? " on" : "") + '" data-sklass="' + esc(k) + '">' + esc(k || "no class") + "</button>"; }).join("") + "</div>" +
        '<div class="il">SAVE TO</div><div class="idest">' + esc(destFor(scan.kind, scan.klass) + "/" + safeName((scan.name || "").trim() || "Scan") + " (" + scanStamp(new Date()) + ").pdf") + "</div>" +
        '<div class="row"><button type="button" class="btn" data-act="scansave">Save PDF · ' + n + " page" + (n === 1 ? "" : "s") + "</button></div></form>";
    }
    return h;
  }
  function bindScan(m) {
    if (!scan) return;
    var v = $("scanv"); if (v && scan.stream && v.srcObject !== scan.stream) { v.srcObject = scan.stream; v.play().catch(function () {}); }
    if (scan.stage === "camera") scanCam();
    var nm = $("scanname"); if (nm) nm.oninput = function () { scan.name = nm.value; var d = document.querySelector("#scanform .idest"); if (d) d.textContent = destFor(scan.kind, scan.klass) + "/" + safeName(nm.value.trim() || "Scan") + " (" + scanStamp(new Date()) + ").pdf"; };
    m.querySelectorAll("[data-skind]").forEach(function (x) { x.onclick = function () { scan.kind = x.dataset.skind; render(); }; });
    m.querySelectorAll("[data-sklass]").forEach(function (x) { x.onclick = function () { scan.klass = x.dataset.sklass; render(); }; });
    m.querySelectorAll("[data-sdel]").forEach(function (x) { x.onclick = function () { var p = scan.pages.splice(+x.dataset.sdel, 1)[0]; if (p) URL.revokeObjectURL(p.url); render(); }; });
    var svg = $("scansvg"); if (!svg) return;
    svg.querySelectorAll(".hdl").forEach(function (c) {
      c.onpointerdown = function (ev) {
        ev.preventDefault(); c.setPointerCapture(ev.pointerId); var i = +c.dataset.h;
        c.onpointermove = function (e2) {
          var b = svg.getBoundingClientRect(), W = scan.shot.width, H = scan.shot.height;
          var x = Math.max(0, Math.min(W, (e2.clientX - b.left) / b.width * W)), y = Math.max(0, Math.min(H, (e2.clientY - b.top) / b.height * H));
          scan.quad[i] = [x, y]; c.setAttribute("cx", x); c.setAttribute("cy", y);
          $("scanpoly").setAttribute("points", scan.quad.map(function (p) { return p.join(","); }).join(" "));
        };
        c.onpointerup = c.onpointercancel = function () { c.onpointermove = null; };
      };
    });
  }
  function editSheet(e) {      // tap an event: change it right here (the PC and laptops get it on the next sync)
    var kinds = ["event", "class", "lab", "exam", "test", "quiz", "due"];
    return '<form id="caledit" class="card editsheet"><div class="h">Edit event</div>' +
      '<label class="l">What<input name="title" required value="' + esc(e.title) + '"></label>' +
      '<div class="f2"><label class="l">Day<input name="date" type="date" required value="' + esc(e.date) + '"></label><label class="l">Time<input name="time" type="time" value="' + esc(e.time || "") + '"></label></div>' +
      '<div class="f2"><select name="kind">' + kinds.map(function (k) { return "<option" + (k === (e.kind || "event") ? " selected" : "") + ">" + k + "</option>"; }).join("") + '</select><select name="repeat"><option value="">once</option><option value="weekly"' + (e.repeat ? " selected" : "") + '>every week</option></select></div>' +
      '<label class="l">Note<input name="notes" value="' + esc(e.notes || "") + '" placeholder="optional"></label>' +
      '<div class="row"><button class="btn">Save</button><button type="button" class="btn ghost" data-act="editcancel">Cancel</button><button type="button" class="btn danger" data-del="' + esc(e.id) + '">Delete</button></div>' +
      (e.repeat ? '<p class="note">It repeats weekly: changing the day moves the whole series.</p>' : "") + "</form>";
  }
  function todoView() {
    var t = S.tasks || [];
    return "<h1>To-do</h1><div>" + (t.filter(function (x) { return !x.done; }).concat(t.filter(function (x) { return x.done; }).slice(-5)).map(taskRow).join("") || '<p class="note">No tasks.</p>') + "</div>" +
      '<form id="taskform"><input name="text" required placeholder="New task"><input name="due" type="date"><button class="btn">add task</button></form>' +
      '<div class="col"><div class="h">Deadlines</div>' + (S.deadlines || []).filter(function (x) { return daysTo(x.date) >= 0; }).map(function (x) { return '<div class="when"><span class="d">' + dayLabel(x.date) + '</span><span class="w">' + esc(x.what) + '</span><span class="k">' + daysTo(x.date) + " d</span></div>"; }).join("") + "</div>" +
      '<form id="dlform"><input name="what" required placeholder="New deadline"><input name="date" type="date" required><button class="btn">add deadline</button></form>';
  }
  function notesView() {
    if (editing) {
      var classes = classNames(); if (editing.klass && classes.indexOf(editing.klass) < 0) classes.push(editing.klass);
      return '<form id="noteform"><input name="title" placeholder="Title" value="' + esc(editing.title || "") + '" style="font-weight:600;font-size:18px">' +
        '<div class="f2"><select name="klass"><option value="">no class</option>' + classes.map(function (c) { return "<option" + (c === editing.klass ? " selected" : "") + ">" + esc(c) + "</option>"; }).join("") + '</select><input name="date" type="date" value="' + esc(editing.date) + '"></div>' +
        '<textarea name="text" placeholder="Type your notes. They save as you go and go to Obsidian on your PC.">' + esc(editing.text || "") + '</textarea><div class="sub" id="nstat">' + (editing.nid ? "saved on your phone" : "new note") + "</div></form>";
    }
    var list = Object.keys(notes).map(function (k) { return notes[k]; }).sort(function (a, b) { return b.updated - a.updated; });
    var waiting = pending.filter(function (c) { return c.type === "note_save"; }).map(function (c) { return c.nid; });
    return '<div class="row"><h1>Notes</h1><button class="btn" data-act="write">+ new</button></div>' +
      (list.length ? '<div class="list">' + list.map(function (n) { return '<button class="li" data-note="' + esc(n.nid) + '"><span>' + esc(n.title) + '</span><span class="m">' + esc((n.klass || "no class") + " · " + (waiting.indexOf(n.nid) >= 0 ? "sending" : "in Obsidian")) + "</span></button>"; }).join("") + "</div>" : '<p class="note">No notes from this phone yet.</p>');
  }
  function savedView() {
    if (reading) return '<button class="chip" data-act="unread">← saved</button><article class="reader">' + (reading.text ? md(reading.text) : '<p class="note">Loading…</p>') + "</article>";
    return "<h1>Saved</h1><div>" + ((S.saved || []).slice(0, 50).map(function (s) {
      var off = s.md && meta.articles[s.md];
      return '<div class="story"' + (off ? ' data-read="' + esc(s.md) + '" role="button" tabindex="0"' : "") + '><div class="t">' + esc(String(s.name).replace(/^\d{4}-\d\d-\d\d - /, "")) + '</div><div class="m">' + (s.pending ? "saving on your PC" : off ? "tap to read · offline" : "text comes with the next sync") + "</div></div>";
    }).join("") || '<p class="note">Nothing saved yet. Share a link to Archie, or tap save on a story.</p>') + "</div>" +
      '<div class="col"><div class="h">Following</div><div class="chips">' + (S.follow || []).map(function (f, i) { return '<button class="chip" data-unfollow="' + i + '">' + esc(f) + " ✕</button>"; }).join("") + "</div></div>" +
      '<form id="followform"><input name="topic" required placeholder="Follow a topic"><button class="btn">follow</button></form>';
  }
  function settingsView() {
    var perm = window.Notification ? Notification.permission : "unsupported";
    return "<h1>Settings</h1>" +
      '<div class="card"><div class="h">Notifications</div><div>' + (perm === "granted" && meta.pushOn ? "On: classes 15 min ahead, a morning summary, and when lecture notes are ready." : perm === "denied" ? "Blocked. Allow notifications for this site in Chrome's settings, then come back." : "Off") + "</div>" +
      '<div class="row" style="margin-top:12px;justify-content:flex-start;gap:8px">' + (meta.pushOn && perm === "granted" ? '<button class="btn ghost" data-act="pushtest">send a test</button><button class="btn ghost" data-act="pushoff">turn off</button>' : '<button class="btn" data-act="pushon">turn on</button>') + "</div></div>" +
      '<div class="card"><div class="h">Sync</div><div>' + (status.state === "home" ? "Connected to " + esc(S.pc || "your PC") + " · " + ago(meta.last_ok) : "Not connected" + (status.msg ? ": " + esc(status.msg) : "") + " · last sync " + ago(meta.last_ok)) + "</div>" +
      '<div class="sub" style="margin-top:6px">' + pending.length + " change" + (pending.length === 1 ? "" : "s") + " waiting" + (meta.upload_error ? " · " + esc(meta.upload_error) : "") + '</div><button class="btn ghost" style="margin-top:12px" data-act="sync">sync now</button></div>' +
      '<div class="card"><div class="h">Install</div><div>In Chrome: ⋮ → <b>Install app</b> (or Add to Home screen). Then Archie shows up in the share menu.</div></div>' +
      '<div class="sub">Archie phone ' + VERSION + "</div>";
  }

  // ----- drawing ----------------------------------------------------------------------------------------------------
  function syncUI() {
    var el = $("sync"), n = pending.length, t;
    el.className = "sync " + (syncing ? "busy " : "") + (status.state === "home" ? (n ? "wait" : "home") : status.state === "away" ? "away" : "");
    if (status.state === "home") t = "synced with " + (S.pc || "your PC") + " · " + ago(meta.last_ok) + (n ? " · " + n + " sending" : "");
    else if (status.state === "away") t = "can't reach your PC" + (n ? " · " + n + " waiting" : "") + (meta.last_ok ? " · " + ago(meta.last_ok) : "");
    else t = "connecting…";
    $("synctext").textContent = t;
  }
  function render(force) {
    syncUI();
    var main = $("main"), active = document.activeElement && document.activeElement.closest && document.activeElement.closest("#main form");
    if (active && force === false) return;
    var sc = main.scrollTop;
    main.innerHTML = (V[tab] || V.today)();
    main.scrollTop = sc;
    document.querySelectorAll(".tabs a").forEach(function (a) { a.toggleAttribute("aria-current", a.dataset.tab === tab || (tab === "chat" && a.dataset.tab === "more")); if (a.dataset.tab === tab) a.setAttribute("aria-current", "page"); });
    bind();
  }
  function fd(f) { var o = {}; new FormData(f).forEach(function (v, k) { o[k] = String(v); }); return o; }
  function bind() {
    var m = $("main");
    m.querySelectorAll("[data-task]").forEach(function (x) { x.onchange = function () { change({ type: "task_done", text: x.dataset.task, done: x.checked }); }; });
    m.querySelectorAll("[data-del]").forEach(function (x) { x.onclick = function (ev) { ev.stopPropagation(); sub.calEdit = null; change({ type: "cal_del", id: x.dataset.del }); }; });
    bindMail(m);
    bindShelf(m);
    bindScan(m);
    m.querySelectorAll("[data-edit]").forEach(function (x) { x.onclick = function (ev) {
      if (ev.target.closest("button")) return;
      var same = sub.calEdit && sub.calEdit.id === x.dataset.edit && sub.calEdit.day === x.dataset.day;
      sub.calEdit = same ? null : { id: x.dataset.edit, day: x.dataset.day }; sub.calFocus = null; render(false);
      var f = $("caledit"); if (f) f.scrollIntoView({ block: "nearest" });
    }; });
    m.querySelectorAll("[data-go]").forEach(function (x) { x.onclick = function (ev) {      // tap a row: go to its page
      if (ev.target.closest("button, input, label")) return;
      sub.calFocus = x.dataset.go === "cal" ? { id: x.dataset.ev, day: x.dataset.day } : null;
      location.hash = x.dataset.go;
    }; });
    var hi = $("calhi");
    if (hi && sub.calFocus) { hi.scrollIntoView({ block: "center" }); var f = sub.calFocus; setTimeout(function () { if (sub.calFocus === f) { sub.calFocus = null; var e = $("calhi"); if (e) e.classList.remove("hi"); } }, 4000); }
    m.querySelectorAll("[data-more]").forEach(function (x) { x.onclick = function () { sub.more = x.dataset.more; editing = null; reading = null; render(); m.scrollTop = 0; }; });
    m.querySelectorAll("[data-news]").forEach(function (x) { x.onclick = function () { sub.news = x.dataset.news; sub.iso = null; render(); m.scrollTop = 0; }; });
    m.querySelectorAll("[data-iso]").forEach(function (x) { x.onclick = function () { sub.iso = x.dataset.iso; render(); m.scrollTop = 0; }; });
    m.querySelectorAll("[data-save]").forEach(function (x) { x.onclick = function () { var st = window._st[+x.dataset.save], it = (st.items || [])[0] || {}; change({ type: "save_story", title: st.title, url: it.url || "", publisher: it.source || "", time: st.last }); x.textContent = "saved ✓"; }; });
    m.querySelectorAll("[data-ex]").forEach(function (x) { x.onclick = function () { var q = $("quick"); q.value = x.dataset.ex; q.focus(); }; });
    m.querySelectorAll("[data-unfollow]").forEach(function (x) { x.onclick = function () { change({ type: "follow_remove", topic: S.follow[+x.dataset.unfollow] }); }; });
    m.querySelectorAll("[data-note]").forEach(function (x) { x.onclick = function () { var n = notes[x.dataset.note]; editing = Object.assign({}, n); render(); }; });
    m.querySelectorAll("[data-read]").forEach(function (x) { x.onclick = function () { var rel = x.dataset.read; reading = { rel: rel, text: null }; render(); idbGet("articles", rel).then(function (t) { if (reading && reading.rel === rel) { reading.text = t || "*(not on this phone yet)*"; render(); m.scrollTop = 0; } }); }; });
    m.querySelectorAll("[data-act]").forEach(function (x) { x.onclick = function (e) { e.preventDefault(); act(x.dataset.act); }; });
    var k = $("klass"); if (k) k.onchange = function () { sub.klass = k.value; render(); };
    bindAsk(m);
    var dcur = drafts.filter(function (x) { return x.id === sub.draft; })[0] || drafts[0];
    var dk = $("dklass"); if (dk && dcur) dk.onchange = function () { dcur.klass = dk.value; save(); };
    m.querySelectorAll("[data-dl]").forEach(function (x) { x.oninput = function () { var it = dcur && dcur.items[+x.dataset.dl]; if (!it) return; it.label = x.value; save(); var s = x.parentNode.querySelector(".sub"); if (s) s.textContent = draftName(dcur, it); }; });
    m.querySelectorAll("[data-dn]").forEach(function (x) { x.oninput = function () { var it = dcur && dcur.items[+x.dataset.dn]; if (!it) return; it[x.dataset.f] = x.value; save(); }; });
    var rg = $("region"); if (rg) rg.onchange = function () { sub.region = rg.value; render(); };
    var gq = $("gq"); if (gq) gq.oninput = function () { sub.gq = gq.value; var f = gq.value.toLowerCase(); document.querySelectorAll("#gl [data-s]").forEach(function (el) { el.hidden = !!f && el.dataset.s.indexOf(f) < 0; }); };
    var on = function (id, fn) { var f = $(id); if (f) f.onsubmit = function (e) { e.preventDefault(); fn(fd(f), f); }; };
    on("quickform", function (d, f) { quickAdd($("quick").value); f.reset(); });
    on("chatform", function () { var q = $("askq").value; $("askq").value = ""; ask(q); });
    on("caledit", function (d) {
      if (!sub.calEdit) return;
      var id = sub.calEdit.id; sub.calEdit = null;
      var cur = S.calendar.filter(function (e) { return e.id === id; })[0] || {};
      change({ type: "cal_edit", id: id, item: { title: d.title.trim(), date: d.date, time: d.time || null, kind: d.kind, notes: (d.notes || "").trim(), repeat: d.repeat || null, until: d.repeat ? (cur.until || null) : null } });
      toast("Saved · your PC gets it on the next sync");
    });
    on("calform", function (d, f) { change({ type: "cal_add", item: { title: d.title.trim(), date: d.date, time: d.time || null, kind: d.kind, notes: "", repeat: d.repeat || null, until: null } }); f.reset(); toast("Added to your calendar"); });
    on("taskform", function (d, f) { change({ type: "task_add", text: d.text.trim(), due: d.due || null }); f.reset(); });
    on("dlform", function (d, f) { change({ type: "deadline_add", what: d.what.trim(), date: d.date }); f.reset(); });
    on("followform", function (d, f) { change({ type: "follow_add", topic: d.topic.trim() }); f.reset(); });
    on("markform", function () { var t = $("marktext").value.trim(); if (t) markRec(t); $("marktext").value = ""; $("markform").hidden = true; });
    var nf = $("noteform"), nt = null;
    if (nf) nf.oninput = nf.onchange = function () { clearTimeout(nt); $("nstat").textContent = "typing…"; nt = setTimeout(function () { var d = fd(nf); if (!d.text.trim() && !editing.nid) return; editing = noteSave(Object.assign(editing, { title: d.title, klass: d.klass, date: d.date, text: d.text })); editing = Object.assign({}, editing); var s = $("nstat"); if (s) s.textContent = "saved on your phone · goes to Obsidian at the next sync"; }, 900); };
  }
  function act(a) {
    var k = currentClass();
    if (a === "editcancel") { sub.calEdit = null; return render(); }
    if (a === "scan") return scanStart();
    if (a === "scanclose") { if (scan && scan.pages.length && !confirmDiscard()) return; scanStop(); if (scan) scan.pages.forEach(function (p) { URL.revokeObjectURL(p.url); }); scan = null; return render(); }
    if (a === "snap") return scanSnap();
    if (a === "scanpick") return scanPick();
    if (a === "scankeep") return scanKeep();
    if (a === "scanretake") { scan.stage = "camera"; scan.shot = null; scan.preview = null; render(); if (scan.noCam) scanPick(); else scanCam(); return; }
    if (a === "scansave") return scanSave();
    if (a === "mailfilecancel") { sub.mailFile = null; return render(); }
    if (a === "mailfile" && sub.mailFile) { var mf = sub.mailFile; sub.mailFile = null; change({ type: "mail_file", id: mf.id, n: mf.n, name: mf.name, kind: mf.kind, klass: mf.klass || null }); toast("Filing it on your PC · " + destFor(mf.kind, mf.klass)); return; }
    if (a === "rec") return startRec();
    if (a === "stop") return stopRec();
    if (a === "pause") return pauseRec();
    if (a === "mark") return markRec("");
    if (a === "say") { var f = $("markform"); f.hidden = !f.hidden; if (!f.hidden) $("marktext").focus(); return; }
    if (a === "sent") { sub.sentOpen = !sub.sentOpen; return render(); }
    if (a.indexOf("mode:") === 0) { sub.mode = a.slice(5); return render(); }
    var cur = drafts.filter(function (x) { return x.id === sub.draft; })[0] || drafts[0];
    if (a.indexOf("dopen:") === 0) { sub.draft = a.slice(6); return render(); }
    if (a === "dphoto" && cur) { sub.photoDraft = cur; return $("camera").click(); }
    if (a === "dnote" && cur) { cur.items.push({ kind: "note", title: "", text: "" }); save(); render(); var ts = document.querySelectorAll("#draftform textarea"); if (ts.length) ts[ts.length - 1].focus(); return; }
    if (a.indexOf("ddel:") === 0 && cur) { var it = cur.items[+a.slice(5)]; if (it && it.kind !== "audio") { if (it.bid) idbDel("blobs", it.bid).catch(function () {}); cur.items.splice(+a.slice(5), 1); save(); } return render(); }
    if (a === "dsend" && cur) return sendDraft(cur);
    if (a === "ddiscard" && cur) { if (!confirm("Discard this recording and everything added to it? It can't be undone.")) return;
      cur.items.forEach(function (it) { if (it.bid) idbDel("blobs", it.bid).catch(function () {}); }); drafts = drafts.filter(function (x) { return x !== cur; }); sub.draft = null; save(); return render(); }
    if (a === "photo" && tab === "add") { sub.photoPage = true; return $("camera").click(); }
    if (a === "photo") { sub.photoFor = rec ? rec.klass : (tab === "class" ? (sub.klass !== undefined ? sub.klass : (k || {}).title) : (k || {}).title); return $("camera").click(); }
    if (a === "file") return $("picker").click();
    if (a === "write") { editing = { nid: null, title: "", klass: tab === "class" ? (sub.klass !== undefined ? sub.klass : (k || {}).title || "") : (k || {}).title || "", date: iso(new Date()), text: "" }; tab = "more"; sub.more = "notes"; location.hash = "more"; render(); var ta = document.querySelector("#noteform textarea"); if (ta) ta.focus(); return; }
    if (a === "paste") return pasteClip(true);
    if (a === "saveclip") { saveLink(sub.clip); meta.seenClip = sub.clip; sub.clip = null; save(); return render(); }
    if (a === "newsrefresh") { sub.newsBusy = true; render(); return syncNow().then(function () { return fetchWorld(true); }).catch(function (e) { toast(e.message); }).then(function () { sub.newsBusy = false; render(); }); }
    if (a === "govback") { sub.iso = null; return render(); }
    if (a === "unread") { reading = null; return render(); }
    if (a === "clearchat") { chat = chat.filter(function (m) { return m.queued; }); save(); return render(); }
    if (a === "sync") return syncNow();
    if (a === "pushon") return pushOn();
    if (a === "pushoff") return pushOff();
    if (a === "pushtest") return op({ op: "push_test" }).then(function (r) { toast(r.sent ? "Sent. It should pop up in a moment." : "Your PC couldn't send it (check Archie Doctor)."); }, function (e) { toast(e.message); });
  }

  // ----- links, sharing, clipboard -------------------------------------------------------------------------------------
  var URLRX = /https?:\/\/[^\s<>"]+/i;
  function saveLink(u) { change({ type: "save_story", title: u, url: u, publisher: "", time: null }); toast("Link saved; your PC reads the article"); }
  function pasteClip(fromButton) {
    if (!navigator.clipboard || !navigator.clipboard.readText) { if (fromButton) toast("This phone doesn't let apps read the clipboard; paste into the box instead."); return; }
    navigator.clipboard.readText().then(function (t) {
      t = (t || "").trim(); if (!t) { if (fromButton) toast("The clipboard is empty."); return; }
      var u = (t.match(URLRX) || [])[0];
      if (fromButton) { if (u) saveLink(u); else { tab = "add"; render(); $("quick").value = t; $("quick").focus(); } return; }
      if (u && u !== meta.seenClip && meta.recent.indexOf(u) < 0) { sub.clip = u; if (tab === "add" || tab === "today") render(false); }
    }).catch(function () { if (fromButton) toast("Allow clipboard access to paste from here."); });
  }
  // files waiting for their inbox card: name, what it is, which class (shared, picked or photographed on the Add tab).
  // Same kinds and filing rules as Archie's card on the PC; the PC files it when it arrives.
  var KINDS = ["slides / handout", "reading", "syllabus", "assignment", "board photo", "my notes", "recording", "idea", "other"], BIG = 50 * 1048576;
  var asking = null;
  function guessKind(name, klass) {
    var low = name.toLowerCase(), ext = (low.match(/\.[a-z0-9]+$/) || [""])[0];
    if (/syllabus/.test(low)) return "syllabus";
    if (/\.(mp3|m4a|wav|webm|ogg|opus|aac|flac|mp4|mov|mkv)$/.test(low)) return /^recording\b|\(20\d\d-\d\d-\d\d/.test(low) || !klass ? "recording" : "slides / handout";
    if (/\.(png|jpe?g|gif|webp|heic|bmp)$/.test(low)) return /\bboard\b/.test(low) || klass ? "board photo" : "other";
    if (/assign|homework|\bhw\d*\b|worksheet|lab report|problem set|pset|due/.test(low)) return "assignment";
    if (/\.(pptx?|key|odp)$/.test(low)) return "slides / handout";
    if (/chapter|\bch\.? ?\d|reading|article|paper/.test(low)) return "reading";
    if (ext === ".md" || ext === ".txt") return "my notes";
    if (klass && /\.(pdf|docx?|rtf|odt)$/.test(low)) return "slides / handout";
    return "other";
  }
  function splitName(n) { var i = n.lastIndexOf("."); return i > 0 ? [n.slice(0, i), n.slice(i)] : [n, ""]; }
  function renamed(orig, stem) {
    var p = splitName(orig); stem = safeName((stem || "").trim());
    if (!stem || stem === p[0]) return orig;
    var m = p[0].match(/\((?:[A-Za-z]+ )?(20\d\d-\d\d-\d\d[^)]*)\)/);
    if (m && stem.indexOf(m[1]) < 0) stem += " (" + (/\bboard\b/i.test(p[0]) ? "Board " : "") + m[1] + ")";
    return stem + p[1];
  }
  function destFor(kind, klass) {
    if (kind === "idea") return "Ideas";
    if (!klass) return kind === "recording" ? "Archie Lite/Voice inbox" : "Archie Inbox";
    var c = "Lectures/" + klass;
    return /slides|reading|syllabus/.test(kind) ? c + "/Materials" : kind === "assignment" ? c + "/Assignments" : kind === "recording" || kind === "my notes" ? c : c + "/Files";
  }
  function mbs(n) { return n >= 1048576 ? (n / 1048576).toFixed(1) + " MB" : Math.max(1, Math.round(n / 1024)) + " KB"; }
  function askClass(list) {
    var files = Array.prototype.slice.call(list || []); if (!files.length) return;
    var k = currentClass(), kl = k ? k.title : "";
    asking = (asking || []).concat(files.map(function (f) { var n = f.name || ("Shared " + stamp(new Date())); return { file: f, orig: n, name: splitName(n)[0], kind: guessKind(n, kl), klass: kl }; }));
    tab = "add"; location.hash = "add"; render();
    var c = document.querySelector(".askcard"); if (c) c.scrollIntoView({ block: "start" });
  }
  function askCard() {
    if (!asking || !asking.length) return "";
    return asking.map(function (x, i) {
      var classes = classNames(); if (x.klass && classes.indexOf(x.klass) < 0) classes.unshift(x.klass);
      var big = (x.file.size || 0) > BIG;
      return '<form class="card askcard" onsubmit="return false"><div class="h neon">' + esc(x.orig) + '</div><div class="sub">' + mbs(x.file.size || 0) + "</div>" +
        (big ? '<div class="iwarn">⚠ ' + mbs(x.file.size) + ": a big one. Better on Wi-Fi; it waits on this phone until it's sent.</div>" : "") +
        '<label class="l">Name<span class="iname"><input data-aname="' + i + '" value="' + esc(x.name) + '"><b>' + esc(splitName(x.orig)[1]) + "</b></span></label>" +
        '<div class="il">WHAT IS IT</div><div class="chips">' + KINDS.map(function (k) { return '<button type="button" class="chip' + (k === x.kind ? " on" : "") + '" data-akind="' + i + "|" + esc(k) + '">' + esc(k) + "</button>"; }).join("") + "</div>" +
        '<div class="il">CLASS</div><div class="chips">' + classes.concat([""]).map(function (k) { return '<button type="button" class="chip' + (k === x.klass ? " on" : "") + '" data-aklass="' + i + "|" + esc(k) + '">' + esc(k || "no class") + "</button>"; }).join("") + "</div>" +
        '<div class="il">SAVE TO</div><div class="idest">' + esc(destFor(x.kind, x.klass) + "/" + renamed(x.orig, x.name)) + "</div>" +
        '<div class="row"><button type="button" class="btn" data-asave="' + i + '">' + (big ? "Send " + mbs(x.file.size) : "Save") + '</button><button type="button" class="btn ghost" data-askip="' + i + '">Not now</button></div></form>';
    }).join("");
  }
  function bindAsk(m) {
    m.querySelectorAll("[data-aname]").forEach(function (el) { el.oninput = function () { asking[+el.dataset.aname].name = el.value; }; });
    m.querySelectorAll("[data-akind]").forEach(function (el) { el.onclick = function () { var p = el.dataset.akind.split("|"); asking[+p[0]].kind = p[1]; render(); }; });
    m.querySelectorAll("[data-aklass]").forEach(function (el) { el.onclick = function () { var p = el.dataset.aklass.split("|"); asking[+p[0]].klass = p.slice(1).join("|"); render(); }; });
    m.querySelectorAll("[data-asave]").forEach(function (el) { el.onclick = function () {
      var x = asking[+el.dataset.asave]; asking.splice(+el.dataset.asave, 1); if (!asking.length) asking = null; render();
      addFile(x.file, renamed(x.orig, x.name), x.klass || null, x.file.lastModified, { kind: x.kind, folder: x.kind === "idea" ? "ideas" : null })
        .then(function () { toast("Saved · on its way to " + destFor(x.kind, x.klass)); });
    }; });
    m.querySelectorAll("[data-askip]").forEach(function (el) { el.onclick = function () { asking.splice(+el.dataset.askip, 1); if (!asking.length) asking = null; render(); }; });
  }
  function handleFiles(list, klass) {
    var files = Array.prototype.slice.call(list || []); if (!files.length) return;
    Promise.all(files.map(function (f) { return addFile(f, f.name || ("Shared " + stamp(new Date())), klass, f.lastModified); }))
      .then(function () { toast(files.length + " file" + (files.length === 1 ? "" : "s") + " saved" + (klass ? " for " + klass : "") + "; on the way to Obsidian"); });
  }
  function handleShared() {
    return idbGet("shared", "last").then(function (s) {
      if (!s) return; idbDel("shared", "last");
      var k = currentClass(), kl = k ? k.title : null, text = [s.title, s.text, s.url].filter(Boolean).join("\n").trim(), u = s.url || (text.match(URLRX) || [])[0];
      if (s.files && s.files.length) { askClass(s.files); if (!(u || text)) return; }
      if (u) { saveLink(u); meta.recent.unshift(u); meta.recent = meta.recent.slice(0, 20); save(); }
      else if (text) { noteSave({ title: (s.title || text.split("\n")[0]).slice(0, 60), klass: kl, date: iso(new Date()), text: text }); toast("Saved as a note"); }
      if (!asking) { tab = "today"; location.hash = "today"; } render();
    });
  }

  // ----- notifications ---------------------------------------------------------------------------------------------------
  function urlB64(s) { var p = "=".repeat((4 - s.length % 4) % 4), b = atob((s + p).replace(/-/g, "+").replace(/_/g, "/")), a = new Uint8Array(b.length); for (var i = 0; i < b.length; i++) a[i] = b.charCodeAt(i); return a; }
  function pushOn() {
    if (!("serviceWorker" in navigator) || !("PushManager" in window)) return toast("This browser can't do notifications. Use Chrome.");
    Notification.requestPermission().then(function (p) {
      if (p !== "granted") throw new Error("Notifications weren't allowed.");
      return Promise.all([navigator.serviceWorker.ready, op({ op: "push_key" })]);
    }).then(function (x) {
      return x[0].pushManager.getSubscription().then(function (s) { return s || x[0].pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: urlB64(x[1].key) }); });
    }).then(function (sub) { return op({ op: "push_subscribe", sub: sub.toJSON(), label: navigator.userAgent.slice(0, 60) }); })
      .then(function (r) { if (!r.ok) throw new Error(r.error); meta.pushOn = true; save(); render(); toast("Notifications are on. Try “send a test”."); })
      .catch(function (e) { toast(e.message || "Couldn't turn on notifications."); });
  }
  function pushOff() {
    navigator.serviceWorker.ready.then(function (r) { return r.pushManager.getSubscription(); }).then(function (s) {
      if (!s) return; var ep = s.endpoint; return s.unsubscribe().then(function () { return op({ op: "push_unsubscribe", endpoint: ep }); });
    }).catch(function () {}).then(function () { meta.pushOn = false; save(); render(); });
  }

  // ----- the rest -------------------------------------------------------------------------------------------------------
  var toastT = null;
  function toast(t) { var el = $("toast"); el.textContent = t || ""; el.hidden = !t; clearTimeout(toastT); toastT = setTimeout(function () { el.hidden = true; }, 4200); }
  function route() {
    var h = (location.hash || "#today").slice(1).split("/")[0];
    if (h === "shared") { handleShared(); return; }
    if (h === "notes" || h === "cal" || h === "todo" || h === "saved" || h === "settings" || h === "mail") { sub.more = h; h = "more"; }
    tab = V[h] ? h : "today"; if (tab !== "more") { editing = null; reading = null; }
    if (tab !== "add") scanStop();
    if (tab === "more" && !editing && !reading) sub.more = sub.more || "";
    render(); if (!sub.calFocus) $("main").scrollTop = 0;
    if (tab === "chat") scrollEnd();
  }
  window.addEventListener("hashchange", route);
  $("sync").onclick = function () { syncNow(); };
  $("camera").onchange = function (e) {
    if (sub.photoPage) { sub.photoPage = false; var pf = e.target.files[0]; e.target.value = "";
      if (pf) askClass([new File([pf], "Photo (" + nice(new Date()) + ").jpg", { type: pf.type || "image/jpeg", lastModified: Date.now() })]); return; }
    if (sub.photoDraft) {                       // a photo for a stopped recording waiting to send
      var dd = sub.photoDraft; sub.photoDraft = null; var df = e.target.files[0]; e.target.value = "";
      if (df) { var dbid = rid() + rid(); idbPut("blobs", dbid, df).then(function () { dd.items.push({ kind: "photo", bid: dbid, tag: (dd.mode === "ideas" ? "Photo " : "Board ") + nice(new Date()), label: "" }); save(); render(); }); }
      return;
    }
    if (rec && e.target.files[0]) {             // during a recording: kept with it, sent when you send the recording
      var rf = e.target.files[0], rbid = rid() + rid(), me = rec; e.target.value = ""; sub.photoFor = undefined;
      idbPut("blobs", rbid, rf).then(function () {
        me.photos.push({ bid: rbid, tag: (me.mode === "ideas" ? "Photo " : "Board ") + nice(new Date()) });
        var a = LS.get("rec_active", null); if (a && a.id === me.id) { a.photos = me.photos; LS.set("rec_active", a); }
        markRec("photo " + me.photos.length); toast("Photo kept with this recording");
      });
      return;
    }
    var f = e.target.files[0], k = sub.photoFor !== undefined ? sub.photoFor : (rec ? rec.klass : (currentClass() || {}).title);
    sub.photoFor = undefined;
    if (f) { sub.photoFor = k; addFile(f, "Board (" + nice(new Date()) + ").jpg", k || null, Date.now()).then(function () { toast("Photo saved" + (k ? " for " + k : "") + "; on the way to Obsidian"); sub.photoFor = undefined; }); if (rec) markRec("photo of the board"); }
    e.target.value = ""; };
  $("picker").onchange = function (e) { askClass(e.target.files); e.target.value = ""; };
  document.addEventListener("visibilitychange", function () {
    if (document.visibilityState === "hidden") { markSeen(); scanStop(); return; }
    if (document.visibilityState === "visible") { sinceFrom = meta.lastSeen || Date.now() / 1000; calSince = meta.calSig || null; if (tab === "today") render(false); if (tab === "add" && scan) scanCam(); }
  });
  document.addEventListener("visibilitychange", function () { if (document.visibilityState === "visible") { kick(200); setTimeout(function () { pasteClip(false); }, 400); } });
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/sw.js").catch(function () {});
    navigator.serviceWorker.addEventListener("message", function (e) { if (e.data && e.data.tab) { location.hash = e.data.tab; } });
  }
  setInterval(function () { if (document.visibilityState === "visible" && !syncing) syncNow(); }, 90000);
  setInterval(function () { if (!rec && document.visibilityState === "visible") render(false); }, 30000);
  route(); recoverRec(); syncNow();
  window.__archie = { state: function () { return { S: S, pending: pending, notes: notes, chat: chat, drops: drops, status: status, meta: meta }; }, syncNow: syncNow, quickAdd: quickAdd, addFile: addFile, finishRec: finishRec };
})();
