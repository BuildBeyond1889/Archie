/* Archie World: the solar system's "archive ▾" menu: people in space right now, the Voyager Golden Record,
   the Golden Record's picture album (from NASA's gallery, kept on this PC), and a mission planner. */
window.ArchieArchive = function (H) {
  "use strict";
  var $ = H.$, esc = H.esc, api = H.api, rich = H.rich, D2R = Math.PI / 180;
  function dd(title, body, open) { return '<details class="arc-dd"' + (open ? " open" : "") + "><summary>" + esc(title) + "</summary><div class=\"arc-body\">" + body + "</div></details>"; }
  function p(t) { return '<div class="rc-note" style="color:var(--fg)">' + t + "</div>"; }

  /* ---------------- people in space ---------------- */
  var FLAG = function (code) { if (!code || code.length !== 2) return ""; return String.fromCodePoint.apply(null, code.toUpperCase().split("").map(function (c) { return 127397 + c.charCodeAt(0); })); };
  function openPeople() {
    rich({ hash: "archive=people", color: "#9fe7c4", title: "PEOPLE IN SPACE", badge: "RIGHT NOW", badgeColor: "#9fe7c4", sub: "checking…", boxes: [], sections: [[null, p("Loading the crew list…")]] });
    api("/api/people").then(function (d) {
      var ppl = (d && d.people) || [], now = Date.now() / 1000, groups = {};
      ppl.forEach(function (x) { var k = x.spacecraft || (x.iss ? "ISS" : "in orbit"); (groups[k] = groups[k] || []).push(x); });
      var craftOf = function (k) { return /tiangong|shenzhou/i.test(k) ? "China's Tiangong station" : /dragon|soyuz|starliner|iss|crew-/i.test(k) ? "the International Space Station" : k; };
      var html = Object.keys(groups).map(function (k) {
        return dd(k + " · " + groups[k].length, groups[k].map(function (x) {
          var days = x.launched ? Math.max(0, Math.floor((now - x.launched) / 86400)) : null;
          return '<div class="arc-row"><b>' + (x.flag_code ? FLAG(x.flag_code) + " " : "") + esc(x.name) + "</b><span>" + esc([x.position, x.agency, x.country].filter(Boolean).join(" · ")) + "</span>" +
            (days != null ? "<i>up for " + days + " day" + (days === 1 ? "" : "s") + " (launched " + new Date(x.launched * 1000).toLocaleDateString([], { month: "short", day: "numeric", year: "numeric" }) + ")</i>" : "") + "</div>";
        }).join("") + p("They are aboard " + esc(craftOf(k)) + "."), true);
      }).join("");
      rich({
        hash: "archive=people", color: "#9fe7c4", title: "PEOPLE IN SPACE", badge: "RIGHT NOW", badgeColor: "#9fe7c4",
        sub: ppl.length ? ppl.length + " people are off the planet right now" : "no crew list yet",
        boxes: [["In space", ppl.length ? String(ppl.length) : "—", "#9fe7c4"], ["Spacecraft", String(Object.keys(groups).length || "—"), "var(--fg)"], ["Updated", d && d.at ? H.ago(Math.round((Date.now() / 1000 - d.at) / 60)) : "—", "var(--fg)"]],
        sections: [[null, html || p("Archie hasn't reached a crew list yet. It checks every 6 hours while online.")],
          [null, '<div class="rc-note">The ISS orbits about 400 km up, once every 92 minutes, so its crew sees 16 sunrises a day. People have lived on it without a break since November 2000. ' + (d && d.src ? "Crew list from " + esc(d.src) + "." : "") + " See the ISS itself on the globe (Space in the layers).</div>"]],
        actions: [["show the ISS", function () { location.hash = "iss"; }]],
        explain: { title: "People in space", names: ["International Space Station", "Tiangong space station"], kind: "space" }
      });
    }).catch(function () { });
  }

  /* ---------------- the Voyager Golden Record ---------------- */
  var MUSIC = [
    ["Bach", "Brandenburg Concerto No. 2 in F, first movement", "Munich Bach Orchestra, Karl Richter", "4:40"],
    ["Java", "court gamelan, \"Kinds of Flowers\"", "", "4:43"],
    ["Senegal", "percussion", "", "2:08"],
    ["Zaire", "Pygmy girls' initiation song", "", "0:56"],
    ["Australia", "Aboriginal songs, \"Morning Star\" and \"Devil Bird\"", "", "1:26"],
    ["Mexico", "\"El Cascabel\"", "Lorenzo Barcelata and the Mariachi México", "3:14"],
    ["Chuck Berry", "\"Johnny B. Goode\"", "", "2:38"],
    ["New Guinea", "men's house song", "", "1:20"],
    ["Japan", "shakuhachi, \"Tsuru no Sugomori\" (Crane's Nest)", "Goro Yamaguchi", "4:51"],
    ["Bach", "\"Gavotte en rondeaux\" from Partita No. 3 for violin", "Arthur Grumiaux", "2:55"],
    ["Mozart", "The Magic Flute, Queen of the Night aria", "Edda Moser, Bavarian State Opera, Wolfgang Sawallisch", "2:55"],
    ["Georgia", "chorus, \"Tchakrulo\"", "", "2:18"],
    ["Peru", "panpipes and drum", "", "0:52"],
    ["Louis Armstrong and his Hot Seven", "\"Melancholy Blues\"", "", "3:05"],
    ["Azerbaijan", "bagpipes", "", "2:30"],
    ["Stravinsky", "The Rite of Spring, Sacrificial Dance", "Columbia Symphony Orchestra, Igor Stravinsky", "4:35"],
    ["Bach", "The Well-Tempered Clavier, Book 2, Prelude and Fugue in C", "Glenn Gould", "4:48"],
    ["Beethoven", "Fifth Symphony, first movement", "Philharmonia Orchestra, Otto Klemperer", "7:20"],
    ["Bulgaria", "\"Izlel je Delyo Hagdutin\"", "Valya Balkanska", "4:59"],
    ["Navajo", "Night Chant", "", "0:57"],
    ["Holborne", "\"The Fairie Round\"", "David Munrow and the Early Music Consort of London", "1:17"],
    ["Solomon Islands", "panpipes", "", "1:12"],
    ["Peru", "wedding song", "", "0:38"],
    ["China", "ch'in (zither), \"Flowing Streams\"", "Kuan P'ing-hu", "7:37"],
    ["India", "raga, \"Jaat Kahan Ho\"", "Surshri Kesar Bai Kerkar", "3:30"],
    ["Blind Willie Johnson", "\"Dark Was the Night, Cold Was the Ground\"", "", "3:15"],
    ["Beethoven", "String Quartet No. 13, Cavatina", "Budapest String Quartet", "6:37"]
  ];
  var EARTH_SOUNDS = ["Music of the spheres", "Volcanoes, earthquake, thunder", "Mud pots", "Wind, rain, surf", "Crickets, frogs", "Birds, hyena, elephant", "Chimpanzee", "Wild dog",
    "Footsteps, heartbeat, laughter", "Fire, speech", "The first tools", "Tame dog", "Herding sheep, blacksmith, sawing", "Tractor, riveter", "Morse code, ships", "Horse and cart", "Train",
    "Tractor, bus, car", "F-111 flyby, Saturn V lift-off", "Kiss, mother and child", "Life signs (brainwaves), pulsar"];
  function openGolden() {
    var v = H.live(), far = ["-31", "-32"].map(function (id) { var c = v && v.craft && v.craft[id]; return c ? Math.hypot(c.x, c.y, c.z) : null; });
    var music = '<table class="arc-t"><tr><th>#</th><th>Piece</th><th>Length</th></tr>' + MUSIC.map(function (m, i) {
      return "<tr><td>" + (i + 1) + "</td><td><b>" + esc(m[0]) + "</b> · " + esc(m[1]) + (m[2] ? '<br><i>' + esc(m[2]) + "</i>" : "") + "</td><td>" + m[3] + "</td></tr>";
    }).join("") + "</table>";
    rich({
      hash: "archive=golden-record", color: "#e9c46a", title: "THE VOYAGER GOLDEN RECORD", badge: "1977 · TWO COPIES", badgeColor: "#e9c46a",
      sub: "A message from Earth, bolted to the side of Voyager 1 and Voyager 2",
      boxes: [["Voyager 1's copy", far[0] ? far[0].toFixed(0) + " AU out" : "—", "#e9c46a"], ["Voyager 2's copy", far[1] ? far[1].toFixed(0) + " AU out" : "—", "#e9c46a"], ["Built to last", "a billion years+", "var(--fg)"]],
      sections: [
        [null, dd("What it is", p("A 12-inch gold-plated copper phonograph record carried by both Voyagers, in case someone, someday, finds one drifting between the stars. It holds 115 pictures (stored as sound), greetings in 55 languages, a 12-minute collage of the sounds of Earth, and 90 minutes of music from around the world. Each spacecraft also carries a needle and cartridge to play it. Neither probe will come near another star for about 40,000 years.") +
          p("Carl Sagan chaired the committee that chose what went on it, with Frank Drake (technical director), Ann Druyan (creative director), Timothy Ferris (producer), Jon Lomberg (designer) and Linda Salzman Sagan (who gathered the greetings). They had about six weeks."), true)],
        [null, dd("The cover: instructions for aliens", p("The aluminum cover is engraved, with no words, in the language of science:") +
          '<ul class="arc-ul"><li><b>How to play it:</b> the record and needle drawn from the side and from above, with the playing time written in binary.</li><li><b>The speed:</b> 16⅔ revolutions per minute, given in units of a basic hydrogen atom vibration (shown bottom right) so any physicist could decode it.</li><li><b>How to turn the sound into pictures:</b> the shape of the signal and how its lines build up a frame, plus the first picture (a circle) to check you did it right.</li><li><b>Where we are:</b> the Sun located by its direction and distance to 14 pulsars, each tagged with its blinking rate in binary (the same map as on the Pioneer plaques).</li><li><b>When it was made:</b> a small sample of uranium-238 is plated on the cover. Measuring how much has decayed tells a finder how long ago it left.</li></ul>')],
        [null, dd("Greetings in 55 languages", p("Spoken greetings from ancient Akkadian and Sumerian to modern Wu Chinese, recorded mostly by people at Cornell University. The English one, \"Hello from the children of planet Earth,\" is spoken by Carl Sagan's six-year-old son Nick. There are also messages from U.S. President Jimmy Carter (printed) and UN Secretary-General Kurt Waldheim (spoken), and a greeting in humpback whale song."))],
        [null, dd("Sounds of Earth (about 12 minutes)", '<ol class="arc-ol">' + EARTH_SOUNDS.map(function (x) { return "<li>" + esc(x) + "</li>"; }).join("") + "</ol>" + p("Arranged as a story: the forming planet, then life, then people and their machines. Ann Druyan's brainwaves were recorded for one segment while she thought about, among other things, falling in love."))],
        [null, dd("Music: 27 pieces, about 90 minutes", music)],
        [null, dd("The pictures", p("115 images (116 counting the calibration circle), encoded as sound waves, the way a fax machine works. They start with how to decode them, then math, physics and chemistry definitions, our solar system, DNA and the human body, and then life on Earth:") +
          '<ul class="arc-ul"><li>The Sun, the planets, and Earth from space</li><li>Diagrams of DNA, cells, anatomy, and a baby growing before birth</li><li>Animals, plants, landscapes: a snowflake, a leaf, seashells, dolphins, an eagle</li><li>People: families, children, a mother nursing, people eating and drinking, a school class, a supermarket</li><li>What we build: houses, the Great Wall of China, the Taj Mahal, the Sydney Opera House, a radio telescope, a Titan rocket launching</li></ul>' +
          p("Photos of war, disease, poverty and religion were left out on purpose: the committee chose to show what people hoped the finders would see.") +
          '<button class="arc-album-btn" id="arc-album-btn">▦ open the picture album</button>', true)],
      ],
      actions: [["▦ picture album", openAlbum], ["show Voyager 1", function () { location.hash = "craft=voyager-1"; }]],
      explain: { title: "Voyager Golden Record", names: ["Voyager Golden Record"], kind: "space history" },
      after: function () { var b = document.getElementById("arc-album-btn"); if (b) b.onclick = openAlbum; }
    });
  }

  /* ---------------- the Golden Record's pictures: an album from NASA's gallery ---------------- */
  var ALB = null;
  function openAlbum() {
    if (!ALB) {
      ALB = document.createElement("div"); ALB.className = "arc-album"; ALB.hidden = true;
      ALB.innerHTML = '<div class="alb-top"><b>THE GOLDEN RECORD · PICTURES</b><span class="alb-n"></span><button class="alb-x" title="close">✕</button></div><div class="alb-grid"></div>' +
        '<div class="alb-view" hidden><button class="alb-prev">‹</button><figure><img alt=""><figcaption></figcaption></figure><button class="alb-next">›</button><button class="alb-back">✕</button></div>';
      document.body.appendChild(ALB);
      ALB.querySelector(".alb-x").onclick = function () { ALB.hidden = true; };
      ALB.querySelector(".alb-back").onclick = function () { ALB.querySelector(".alb-view").hidden = true; };
      document.addEventListener("keydown", function (e) {
        if (ALB.hidden) return; var v = ALB.querySelector(".alb-view");
        if (e.key === "Escape") { if (!v.hidden) v.hidden = true; else ALB.hidden = true; }
        if (!v.hidden && e.key === "ArrowRight") step(1); if (!v.hidden && e.key === "ArrowLeft") step(-1);
      });
      ALB.querySelector(".alb-prev").onclick = function () { step(-1); };
      ALB.querySelector(".alb-next").onclick = function () { step(1); };
    }
    ALB.hidden = false; loadAlbum();
  }
  var albList = [], albAt = 0, albTimer = null;
  function step(n) { if (!albList.length) return; albAt = (albAt + n + albList.length) % albList.length; showPic(); }
  function showPic() {
    var im = albList[albAt], v = ALB.querySelector(".alb-view"); v.hidden = false;
    v.querySelector("img").src = im.url || ""; v.querySelector("img").alt = im.title;
    v.querySelector("figcaption").innerHTML = "<b>" + (albAt + 1) + ". " + esc(im.title) + "</b>" + (im.about ? "<span>" + esc(im.about) + "</span>" : "") + '<a href="' + esc(im.page) + '" target="_blank" rel="noopener">NASA\'s page for this picture</a>';
  }
  function loadAlbum() {
    clearTimeout(albTimer);
    api("/api/golden").then(function (d) {
      var imgs = (d && d.images) || [];
      albList = imgs.filter(function (x) { return x.url; });
      ALB.querySelector(".alb-n").textContent = albList.length ? albList.length + " pictures" + (d.busy ? " so far · still downloading from NASA…" : " · from NASA's gallery, kept on your PC") : (d.busy ? "downloading from NASA's gallery (first time only)…" : "not downloaded yet: Archie fetches them the first time it's online");
      var g = ALB.querySelector(".alb-grid");
      g.innerHTML = albList.map(function (im, i) { return '<button class="alb-t" data-i="' + i + '"><img loading="lazy" src="' + esc(im.url) + '" alt=""><span>' + (i + 1) + ". " + esc(im.title) + "</span></button>"; }).join("") ||
        '<div class="rc-note" style="padding:30px">The pictures come from NASA\'s "Images on the Golden Record" gallery. ' + (d.busy ? "They're downloading now; this fills in as they arrive." : "Archie will download them next time it's online.") + "</div>";
      g.querySelectorAll(".alb-t").forEach(function (b) { b.onclick = function () { albAt = +b.dataset.i; showPic(); }; });
      if (d.busy && !ALB.hidden) albTimer = setTimeout(loadAlbum, 4000);
    }).catch(function () { });
  }

  /* ---------------- mission planner ---------------- */
  // planet: [orbit radius AU (average), GM km^3/s^2, radius km, real mission to compare]
  var PLAN = {
    Mercury: [0.387, 22032, 2440, "MESSENGER took 6.6 years (2004–2011), using 6 planet flybys to slow down enough to stay."],
    Venus: [0.723, 324859, 6052, "Magellan took 15 months (1989–1990) on a slower, longer path."],
    Mars: [1.524, 42828, 3390, "Perseverance launched July 30, 2020 and landed February 18, 2021: 203 days, faster than this simple path."],
    Jupiter: [5.203, 126686534, 69911, "Juno took 5 years (2011–2016), swinging past Earth once for a speed boost."],
    Saturn: [9.537, 37931187, 58232, "Cassini took 6.7 years (1997–2004) using flybys of Venus twice, Earth and Jupiter."],
    Uranus: [19.19, 5793939, 25362, "Voyager 2 got there in 8.4 years (1977–1986) by slingshotting off Jupiter and Saturn."],
    Neptune: [30.07, 6836529, 24622, "Voyager 2 got there in 12 years (1977–1989), one planet slingshot after another."],
    Pluto: [39.48, 871, 1188, "New Horizons flew past after 9.5 years (2006–2015), boosted by Jupiter, but only flew by: it was too fast to stop."]
  };
  var MU_SUN = 132712440018, AU_KM = 149597870.7, G0 = 9.80665, YEAR_D = 365.25;
  var ENGINES = [["chemical: hydrogen + oxygen", 450], ["chemical: kerosene + oxygen", 330], ["chemical: storable (hydrazine)", 320], ["ion engine (very weak, very efficient)", 3000]];
  function hohmann(target) {
    var r1 = 1 * AU_KM, r2 = PLAN[target][0] * AU_KM, a = (r1 + r2) / 2;
    var v1 = Math.sqrt(MU_SUN / r1), v2 = Math.sqrt(MU_SUN / r2);
    var dv1 = Math.abs(v1 * (Math.sqrt(2 * r2 / (r1 + r2)) - 1)), dv2 = Math.abs(v2 * (1 - Math.sqrt(2 * r1 / (r1 + r2))));
    var days = Math.PI * Math.sqrt(a * a * a / MU_SUN) / 86400;
    var rLEO = 6378 + 200, muE = 398600.4, leave = Math.sqrt(dv1 * dv1 + 2 * muE / rLEO) - Math.sqrt(muE / rLEO);
    var GM = PLAN[target][1], rp = PLAN[target][2] * 1.1 + (target === "Mars" || target === "Venus" || target === "Mercury" ? 300 : 0), e = 0.9;
    var capture = Math.sqrt(dv2 * dv2 + 2 * GM / rp) - Math.sqrt(GM * (1 + e) / rp);
    var T2 = Math.pow(PLAN[target][0], 1.5) * YEAR_D, phase = Math.PI - 2 * Math.PI * days / T2;   // how far ahead (or behind) of Earth the target must be at launch
    return { vinf1: dv1, vinf2: dv2, days: days, leave: leave, capture: Math.max(0, capture), phase: phase, a: a / AU_KM, r2: PLAN[target][0], T2: T2 };
  }
  function lon(name, d) { var q = H.helio(name, d); return Math.atan2(q[1], q[0]); }
  function wrap(a) { a = a % (2 * Math.PI); return a < -Math.PI ? a + 2 * Math.PI : a > Math.PI ? a - 2 * Math.PI : a; }
  function nextWindow(target, h) {   // the first day from now when the target leads Earth by the right angle
    var start = H.now(), prev = null;
    for (var i = 0; i < 2000; i++) {
      var d = new Date(start.getTime() + i * 86400000), diff = wrap(lon(target, d) - lon("Earth", d) - h.phase);
      if (prev != null && Math.abs(diff) < 0.6 && ((prev < 0 && diff >= 0) || (prev > 0 && diff <= 0))) return d;
      prev = diff;
    }
    return null;
  }
  function fmtDays(d) { return d < 700 ? Math.round(d) + " days" : (d / YEAR_D).toFixed(1) + " years"; }
  var plan = { target: "Mars", engine: 0, payload: 1000 };
  function openPlanner() {
    var h = hohmann(plan.target), win = nextWindow(plan.target, h), arrive = win ? new Date(win.getTime() + h.days * 86400000) : null;
    var isp = ENGINES[plan.engine][1], dvTot = h.leave + h.capture, ratio = Math.exp(dvTot * 1000 / (isp * G0)), fuel = plan.payload * (ratio - 1);
    var opts = Object.keys(PLAN).map(function (n) { return '<option' + (n === plan.target ? " selected" : "") + ">" + n + "</option>"; }).join("");
    var eng = ENGINES.map(function (e, i) { return '<option value="' + i + '"' + (i === plan.engine ? " selected" : "") + ">" + esc(e[0]) + "</option>"; }).join("");
    var form = '<div class="arc-form"><label>Go to <select id="pl-t">' + opts + '</select></label><label>Engine <select id="pl-e">' + eng + '</select></label><label>Spacecraft mass <input id="pl-m" type="number" min="10" step="100" value="' + plan.payload + '"> kg</label></div>';
    var df = function (d) { return d ? d.toLocaleDateString([], { month: "short", day: "numeric", year: "numeric" }) : "—"; };
    rich({
      hash: "archive=planner", color: "#7fd1ff", title: "MISSION PLANNER", badge: "EARTH → " + plan.target.toUpperCase(), badgeColor: "#7fd1ff",
      sub: "The simplest, cheapest path (a Hohmann transfer): one push to leave, coast half an orbit around the Sun, one push to arrive.",
      boxes: [["Trip", fmtDays(h.days), "#7fd1ff"], ["Next launch window", df(win), "var(--fg)"], ["Arrive", df(arrive), "var(--fg)"]],
      sections: [[null, form],
        ["The pushes (Δv, change in speed)", '<dl class="facts own"><dt>Leave Earth orbit</dt><dd>' + h.leave.toFixed(2) + " km/s (from a 200 km orbit)</dd><dt>Arrive and stay</dt><dd>" + h.capture.toFixed(2) + " km/s (into a long, looping orbit)</dd><dt>Total</dt><dd><b>" + dvTot.toFixed(2) + ' km/s</b></dd><dt>Speed when arriving</dt><dd>' + h.vinf2.toFixed(2) + " km/s faster or slower than " + plan.target + "</dd></dl>"],
        ["Fuel", p("With a " + esc(ENGINES[plan.engine][0]) + " engine (exhaust speed " + (isp * G0 / 1000).toFixed(1) + " km/s), a " + plan.payload.toLocaleString() + " kg spacecraft needs about <b>" + Math.round(fuel).toLocaleString() + " kg of propellant</b>: " + ratio.toFixed(1) + " times its own mass in total. That's after a rocket has already lifted it to Earth orbit, which takes about 9.4 km/s more.")],
        ["Real missions", p(esc(PLAN[plan.target][3]))],
        [null, dd("How it works (the math)", p("Earth goes around the Sun at about 29.8 km/s. To reach a farther planet, speed up so your orbit stretches out to touch the target's orbit; to reach a closer one, slow down so you fall inward. The transfer orbit is an ellipse with its ends on the two orbits.") +
          '<ul class="arc-ul"><li><b>Transfer orbit size:</b> a = (r₁ + r₂) ÷ 2 = ' + h.a.toFixed(2) + ' AU</li><li><b>Trip time:</b> half of that ellipse\'s orbit, t = π √(a³ ÷ μ) = ' + fmtDays(h.days) + '</li><li><b>Speed change at Earth:</b> v₁(√(2r₂ ÷ (r₁+r₂)) − 1) = ' + h.vinf1.toFixed(2) + ' km/s, then add escaping Earth\'s pull: √(v∞² + v_escape²) − v_orbit</li><li><b>Fuel:</b> the rocket equation, mass ratio = e^(Δv ÷ exhaust speed)</li><li><b>Launch window:</b> you aim for where ' + plan.target + ' will be, so it must start ' + Math.abs(h.phase / D2R).toFixed(0) + '° ' + (h.phase >= 0 ? "ahead of" : "behind") + " Earth. That lines up once every " + fmtDays(Math.abs(1 / (1 / YEAR_D - 1 / h.T2))) + ".</li></ul>" +
          p("Real missions bend these rules: faster paths cost more fuel, and slingshots past planets trade time for speed. Planet orbits here are taken as circles, so dates can be off by days to weeks."))]],
      actions: [["show it on the orrery", function () { show(win, h); }], ["▶ fly it", function () { show(win, h, true); }]],
      explain: { title: "Hohmann transfer to " + plan.target, names: ["Hohmann transfer orbit"], kind: "physics" },
      after: function () {
        $("pl-t").onchange = function () { plan.target = this.value; openPlanner(); };
        $("pl-e").onchange = function () { plan.engine = +this.value; openPlanner(); };
        $("pl-m").onchange = function () { plan.payload = Math.max(10, +this.value || 1000); openPlanner(); };
      }
    });
  }
  function show(win, h, fly) {
    if (!win) return;
    var L0 = lon("Earth", win);
    H.setPlan({ target: plan.target, launch: win, days: h.days, L0: L0, r1: 1, r2: h.r2 });
    H.goTo(win, fly ? h.days : 0);
  }

  return {
    menu: [["people", "People in space right now", openPeople], ["golden-record", "The Voyager Golden Record", openGolden], ["golden-album", "Golden Record picture album", openAlbum], ["planner", "Mission planner", openPlanner]],
    open: function (k) { var m = this.menu.find(function (x) { return x[0] === k; }); if (m) m[2](); }
  };
};
