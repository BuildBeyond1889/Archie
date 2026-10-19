/* Archie World: the solar system view, drawn as an orrery.
   Planet positions are computed here from NASA/JPL's approximate orbital elements (good to a fraction of a degree, 1800-2050).
   Spacecraft positions come from JPL Horizons through Archie (/api/solar), refreshed twice a day. */
window.ArchieSolar = function (ctx) {
  "use strict";
  var $ = ctx.$, esc = ctx.esc, api = ctx.api, rich = ctx.rich;
  var D2R = Math.PI / 180, AU_KM = 149597870.7, LIGHT_S = 499.005;

  // a, e, I, L, long. perihelion, long. node (J2000) and their rates per century (Standish, JPL)
  var EL = {
    Mercury: [[0.38709927, 0.20563593, 7.00497902, 252.25032350, 77.45779628, 48.33076593], [0.00000037, 0.00001906, -0.00594749, 149472.67411175, 0.16047689, -0.12534081]],
    Venus: [[0.72333566, 0.00677672, 3.39467605, 181.97909950, 131.60246718, 76.67984255], [0.00000390, -0.00004107, -0.00078890, 58517.81538729, 0.00268329, -0.27769418]],
    Earth: [[1.00000261, 0.01671123, -0.00001531, 100.46457166, 102.93768193, 0.0], [0.00000562, -0.00004392, -0.01294668, 35999.37244981, 0.32327364, 0.0]],
    Mars: [[1.52371034, 0.09339410, 1.84969142, -4.55343205, -23.94362959, 49.55953891], [0.00001847, 0.00007882, -0.00813131, 19140.30268499, 0.44441088, -0.29257343]],
    Jupiter: [[5.20288700, 0.04838624, 1.30439695, 34.39644051, 14.72847983, 100.47390909], [-0.00011607, -0.00013253, -0.00183714, 3034.74612775, 0.21252668, 0.20469106]],
    Saturn: [[9.53667594, 0.05386179, 2.48599187, 49.95424423, 92.59887831, 113.66242448], [-0.00125060, -0.00050991, 0.00193609, 1222.49362201, -0.41897216, -0.28867794]],
    Uranus: [[19.18916464, 0.04725744, 0.77263783, 313.23810451, 170.95427630, 74.01692503], [-0.00196176, -0.00004397, -0.00242939, 428.48202785, 0.40805281, 0.04240589]],
    Neptune: [[30.06992276, 0.00859048, 1.77004347, -55.12002969, 44.96476227, 131.78422574], [0.00026291, 0.00005105, 0.00035372, 218.45945325, -0.32241464, -0.01262724]],
    Pluto: [[39.48211675, 0.24882730, 17.14001206, 238.92903833, 224.06891629, 110.30393684], [-0.00031596, 0.00005170, 0.00004818, 145.20780515, -0.04062942, -0.01183482]]
  };
  // name: [color, size, radius km, day, year, moons, temp, gravity (Earth = 1), about]
  var PL = {
    Sun: ["#fff3b0", 11, 696340, "25–35 days (it spins faster at the equator)", "—", "8 planets", "5,500 °C surface, 15 million °C core", "28", "A middle-aged yellow star about 4.6 billion years old, holding 99.8% of the solar system's mass. Its 11-year activity cycle peaked around 2024–2025, which is why auroras have been reaching unusually far south."],
    Mercury: ["#a8a29e", 3.2, 2440, "59 Earth days (one sunrise to the next takes 176)", "88 days", "none", "−180 °C at night to 430 °C by day", "0.38", "The smallest planet and closest to the Sun. No real air to hold heat, so its nights are frozen and its days hot enough to melt lead. There's water ice in shadowed craters at its poles."],
    Venus: ["#e8c77a", 4.3, 6052, "243 Earth days, spinning backwards", "225 days", "none", "about 465 °C everywhere", "0.90", "Earth's near-twin in size, wrapped in thick carbon dioxide and sulfuric acid clouds. The runaway greenhouse makes it the hottest planet, and the air pressure at the surface is 92 times Earth's."],
    Earth: ["#5b9bd5", 4.6, 6371, "24 hours", "365.25 days", "1 (the Moon)", "about 15 °C on average", "1", "Home: the only place known to have life, with liquid water on the surface and an atmosphere of nitrogen and oxygen."],
    Mars: ["#d9643a", 3.9, 3390, "24 h 37 min (a 'sol')", "687 days", "2 (Phobos, Deimos)", "about −60 °C on average", "0.38", "A cold desert with a thin carbon dioxide atmosphere, the biggest volcano (Olympus Mons) and a canyon as long as the US. Rivers and lakes once flowed here; rovers are looking for signs of ancient life."],
    Jupiter: ["#d8a86b", 7.2, 69911, "9 h 56 min (the fastest)", "11.9 years", "about 95", "about −110 °C at the cloud tops", "2.5", "The biggest planet: over 300 Earths of mass, mostly hydrogen and helium. The Great Red Spot is a storm wider than Earth. Its moon Europa hides an ocean under its ice."],
    Saturn: ["#e6d08a", 6.6, 58232, "10 h 33 min", "29.5 years", "about 270", "about −140 °C", "1.07", "Famous for its rings of ice and rock, which are almost flat and only tens of meters thick. Less dense than water. Its moon Titan has lakes of liquid methane; Enceladus sprays water from an ocean."],
    Uranus: ["#9fd7de", 5.2, 25362, "17 h 14 min", "84 years", "28", "about −195 °C", "0.89", "An ice giant tipped on its side, so each pole gets 42 years of sunlight then 42 of darkness. Only Voyager 2 has visited (1986)."],
    Neptune: ["#4f77d9", 5.1, 24622, "16 h 6 min", "165 years", "16", "about −200 °C", "1.14", "The farthest planet, with the fastest winds measured in the solar system (over 2,000 km/h). Found in 1846 by math before anyone saw it. Only Voyager 2 has visited (1989)."],
    Pluto: ["#c9b8a3", 2.6, 1188, "6.4 Earth days", "248 years", "5 (Charon is biggest)", "about −230 °C", "0.06", "A dwarf planet in the Kuiper Belt, with a heart-shaped nitrogen-ice plain. New Horizons flew past in 2015."]
  };
  var PLANETS = ["Mercury", "Venus", "Earth", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"];
  var MOONS = { Earth: [["Moon", 27.3]], Mars: [["Phobos", 0.32], ["Deimos", 1.26]], Jupiter: [["Io", 1.77], ["Europa", 3.55], ["Ganymede", 7.15], ["Callisto", 16.7]],
    Saturn: [["Enceladus", 1.37], ["Rhea", 4.5], ["Titan", 15.9]], Uranus: [["Miranda", 1.4], ["Titania", 8.7], ["Oberon", 13.5]], Neptune: [["Triton", 5.9]], Pluto: [["Charon", 6.4]] };

  // spacecraft: [JPL id or "", name, country, agency, launched, where ("sun", "deep", "interstellar", or a planet / "Moon"), status, about]
  var CRAFT = [
    ["-31", "Voyager 1", "United States", "NASA", 1977, "interstellar", "working (a few instruments left)", "The farthest human-made object. Flew past Jupiter and Saturn, then crossed out of the Sun's bubble into interstellar space in 2012. Its radio signal takes nearly a day to reach us."],
    ["-32", "Voyager 2", "United States", "NASA", 1977, "interstellar", "working (a few instruments left)", "The only spacecraft to visit all four giant planets, including Uranus and Neptune. Entered interstellar space in 2018."],
    ["-98", "New Horizons", "United States", "NASA", 2006, "deep", "working", "Flew past Pluto in 2015 and the icy world Arrokoth in 2019; now exploring the Kuiper Belt."],
    ["-96", "Parker Solar Probe", "United States", "NASA", 2018, "sun", "working", "Dives through the Sun's outer atmosphere. At its closest it passes 6 million km from the surface at about 690,000 km/h, the fastest thing people have ever built."],
    ["-144", "Solar Orbiter", "Europe / United States", "ESA and NASA", 2020, "sun", "working", "Takes the closest pictures of the Sun and the first-ever views of its poles."],
    ["-21", "SOHO", "Europe / United States", "ESA and NASA", 1995, "Earth", "working", "Has watched the Sun from a point 1.5 million km toward it (L1) for 30 years, and has found over 5,000 comets."],
    ["-78", "DSCOVR", "United States", "NOAA and NASA", 2015, "Earth", "working", "Sits at L1 and gives about an hour's warning of solar storms heading for Earth; also photographs the whole sunlit Earth."],
    ["", "Aditya-L1", "India", "ISRO", 2023, "Earth", "working", "India's first solar observatory, parked at L1 watching the Sun."],
    ["-170", "James Webb Space Telescope", "United States / Europe / Canada", "NASA, ESA and CSA", 2021, "Earth", "working", "The biggest space telescope, 1.5 million km from Earth on the side away from the Sun (L2), looking at the first galaxies and at planets around other stars."],
    ["", "Euclid", "Europe", "ESA", 2023, "Earth", "working", "Mapping billions of galaxies from L2 to study dark matter and dark energy."],
    ["-85", "Lunar Reconnaissance Orbiter", "United States", "NASA", 2009, "Moon", "working", "Has mapped the Moon in fine detail since 2009, including future landing sites near the south pole."],
    ["-152", "Chandrayaan-2 orbiter", "India", "ISRO", 2019, "Moon", "working", "India's Moon orbiter; its sister mission Chandrayaan-3 landed near the south pole in 2023."],
    ["-155", "Danuri (KPLO)", "South Korea", "KARI", 2022, "Moon", "working", "South Korea's first mission beyond Earth, carrying a NASA camera that sees into permanently dark craters."],
    ["", "Queqiao-2", "China", "CNSA", 2024, "Moon", "working", "China's relay satellite that lets landers on the Moon's far side talk to Earth."],
    ["-121", "BepiColombo", "Europe / Japan", "ESA and JAXA", 2018, "deep", "on its way to Mercury (arrives late 2026)", "Two orbiters travelling stacked together, using gravity from Earth, Venus and Mercury to slow down enough to be captured by Mercury."],
    ["-74", "Mars Reconnaissance Orbiter", "United States", "NASA", 2005, "Mars", "working", "Its HiRISE camera can see objects the size of a kitchen table on Mars, and it relays rover data home."],
    ["-202", "MAVEN", "United States", "NASA", 2013, "Mars", "orbiting", "Studies how Mars lost most of its air to space."],
    ["-53", "Mars Odyssey", "United States", "NASA", 2001, "Mars", "working", "The longest-serving spacecraft at Mars; found water ice under the surface."],
    ["-41", "Mars Express", "Europe", "ESA", 2003, "Mars", "working", "Europe's first Mars mission; its radar found signs of liquid water under the south polar ice."],
    ["-143", "ExoMars Trace Gas Orbiter", "Europe", "ESA", 2016, "Mars", "working", "Sniffs the Martian air for methane and relays data for NASA's rovers."],
    ["-62", "Hope (Emirates Mars Mission)", "United Arab Emirates", "UAE Space Agency / MBRSC", 2020, "Mars", "working", "The Arab world's first interplanetary mission, watching Mars's weather through the day."],
    ["", "Tianwen-1 orbiter", "China", "CNSA", 2020, "Mars", "working", "China's first Mars orbiter; it delivered the Zhurong rover and maps the planet."],
    ["-76", "Curiosity rover", "United States", "NASA", 2011, "Mars", "working on the surface", "A car-sized rover climbing Mount Sharp in Gale Crater since 2012, reading layers of rock like pages of Mars's history. It reports the weather each sol."],
    ["-168", "Perseverance rover", "United States", "NASA", 2020, "Mars", "working on the surface", "Collecting rock samples in Jezero Crater, an old lake bed. It brought the Ingenuity helicopter, the first aircraft to fly on another planet."],
    ["", "Zhurong rover", "China", "CNSA", 2020, "Mars", "asleep since 2022", "China's first Mars rover; it went into hibernation in 2022 and never woke up."],
    ["-61", "Juno", "United States", "NASA", 2011, "Jupiter", "orbiting", "Orbiting Jupiter since 2016 on long loops over its poles, studying its interior, storms and moons."],
    ["-159", "Europa Clipper", "United States", "NASA", 2024, "deep", "on its way to Jupiter (arrives 2030)", "Will fly past Europa about 50 times to check whether its hidden ocean could support life."],
    ["-28", "Juice", "Europe", "ESA", 2023, "deep", "on its way to Jupiter (arrives 2031)", "Will study Jupiter's icy moons and end up orbiting Ganymede, the first spacecraft to orbit another planet's moon."],
    ["-255", "Psyche", "United States", "NASA", 2023, "deep", "on its way (arrives 2029)", "Headed to Psyche, a metal-rich asteroid that may be the exposed core of a broken planet."],
    ["-49", "Lucy", "United States", "NASA", 2021, "deep", "on its way (first Trojan in 2027)", "A 12-year tour of the Trojan asteroids that share Jupiter's orbit, leftovers from when the planets formed."],
    ["-64", "OSIRIS-APEX", "United States", "NASA", 2016, "deep", "on its way (arrives 2029)", "Brought asteroid Bennu samples back to Earth in 2023 as OSIRIS-REx; now heading to asteroid Apophis for its close pass by Earth in 2029."],
    ["-37", "Hayabusa2", "Japan", "JAXA", 2014, "deep", "on its way (arrives 2031)", "Returned samples of asteroid Ryugu in 2020; now on an extended trip to the tiny, fast-spinning asteroid 1998 KY26."],
    ["-91", "Hera", "Europe", "ESA", 2024, "deep", "on its way (arrives late 2026)", "Going to check what NASA's DART crash did to the asteroid moon Dimorphos in 2022, the first test of pushing an asteroid off course."],
    ["", "Tianwen-2", "China", "CNSA", 2025, "deep", "at or near asteroid Kamoʻoalewa", "China's first asteroid sample-return mission, launched in May 2025 to the tiny near-Earth asteroid Kamoʻoalewa (possibly a chip off the Moon), with a comet to visit afterwards. Its exact path isn't in NASA's public tracking."],
    ["", "Spektr-RG", "Russia / Germany", "Roscosmos and DLR", 2019, "Earth", "working (Russian telescope only)", "An X-ray observatory at L2 mapping the whole sky. Germany switched off its eROSITA telescope in 2022 after Russia invaded Ukraine; Russia's ART-XC telescope still works."]
  ];

  var el = null, svg, gAll, W = 0, H = 0, R = 0, cx = 0, cy = 0;
  var fx = 0, fy = 0, fz = 0, focusName = null, flyT = null;   // the point the view is centered on (model units)
  var yaw = -35, tilt = 24, zoom = 1, dt = 0, playing = false, lastT = 0, live = null, sel = null, raf = null, active = false;
  function now() { return new Date(Date.now() + dt * 86400000); }
  function jd(d) { return d.getTime() / 86400000 + 2440587.5; }
  function helio(name, d) {
    var T = (jd(d) - 2451545) / 36525, e0 = EL[name][0], r = EL[name][1];
    var a = e0[0] + r[0] * T, e = e0[1] + r[1] * T, I = (e0[2] + r[2] * T) * D2R, L = e0[3] + r[3] * T, wb = e0[4] + r[4] * T, O = e0[5] + r[5] * T;
    var w = (wb - O) * D2R, M = ((L - wb) % 360 + 540) % 360 - 180; O *= D2R; M *= D2R;
    var E = M + e * Math.sin(M);
    for (var i = 0; i < 8; i++) E = E - (E - e * Math.sin(E) - M) / (1 - e * Math.cos(E));
    var xp = a * (Math.cos(E) - e), yp = a * Math.sqrt(1 - e * e) * Math.sin(E);
    var cw = Math.cos(w), sw = Math.sin(w), cO = Math.cos(O), sO = Math.sin(O), cI = Math.cos(I), sI = Math.sin(I);
    return [(cw * cO - sw * sO * cI) * xp + (-sw * cO - cw * sO * cI) * yp, (cw * sO + sw * cO * cI) * xp + (-sw * sO + cw * cO * cI) * yp, (sw * sI) * xp + (cw * sI) * yp];
  }
  function orbit(name, d) {   // one full lap as points, from the current elements
    var T = (jd(d) - 2451545) / 36525, e0 = EL[name][0], r = EL[name][1], pts = [];
    var period = 36525 * 360 / (EL[name][1][3]);   // days
    for (var i = 0; i <= 180; i++) pts.push(helio(name, new Date(d.getTime() + (i / 180) * period * 86400000)));
    return pts;
  }
  // distances squeezed so Mercury and Neptune both fit; anything past 45 AU sits on the rim
  var RMAX = 45;
  function squash(p) {
    var r = Math.hypot(p[0], p[1], p[2]); if (!r) return [0, 0, 0];
    var s = Math.log(1 + Math.min(r, RMAX) / 0.3) / Math.log(1 + RMAX / 0.3), k = s / r;
    return [p[0] * k, p[1] * k, p[2] * k * 0.9];
  }
  function proj(p) {   // ecliptic xyz (AU) -> screen, squashed so everything fits
    return projW(squash(p));
  }
  function projW(q0) {  // model units: the horizon ring is radius ~1.08; z is up
    var q = [q0[0] - fx, q0[1] - fy, q0[2] - fz];
    var y = yaw * D2R, el = tilt * D2R;
    var x1 = q[0] * Math.cos(y) - q[1] * Math.sin(y), y1 = q[0] * Math.sin(y) + q[1] * Math.cos(y);
    var S = R * zoom;
    return [cx + x1 * S, cy - y1 * Math.sin(el) * S - q[2] * Math.cos(el) * S, y1 * Math.cos(el) - q[2] * Math.sin(el)];
  }
  function craftPos(c, d) {
    if (hasTrail(c[0]) && trailCovers(c[0], d) && Math.abs(d.getTime() - Date.now()) > 30 * 86400000) return trailPos(c[0], d);
    var v = live && live.craft && live.craft[c[0]];
    if (v) { var days = (d.getTime() / 1000 - v.at) / 86400; return [v.x + (v.vx || 0) * days, v.y + (v.vy || 0) * days, v.z + (v.vz || 0) * days]; }
    var host = c[5] === "Moon" ? "Earth" : c[5];
    return EL[host] ? helio(host, d) : null;
  }
  function dist(a, b) { return Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]); }
  function lightTime(au) { var s = au * LIGHT_S; return s < 90 ? Math.round(s) + " seconds" : s < 5400 ? Math.round(s / 60) + " minutes" : (s / 3600).toFixed(1) + " hours"; }
  function fmtAU(au) { return au < 0.1 ? Math.round(au * AU_KM).toLocaleString() + " km" : au.toFixed(au < 10 ? 2 : 1) + " AU (" + (au * AU_KM / 1e6 >= 1000 ? (au * AU_KM / 1e9).toFixed(1) + " billion km" : Math.round(au * AU_KM / 1e6).toLocaleString() + " million km") + ")"; }
  function skyNote(name, d) {   // morning or evening sky, from the angle between the planet and the Sun seen from Earth
    var E = helio("Earth", d), P = helio(name, d), gp = [P[0] - E[0], P[1] - E[1], P[2] - E[2]];
    var lamP = Math.atan2(gp[1], gp[0]) / D2R, lamS = Math.atan2(-E[1], -E[0]) / D2R, diff = ((lamP - lamS) % 360 + 540) % 360 - 180;
    var el = Math.abs(diff);
    if (el < 15) return ["too close to the Sun to see", el];
    return [(diff > 0 ? "evening sky (west after sunset)" : "morning sky (east before dawn)") + (el > 150 ? ", up all night" : ""), el];
  }
  function moonPhase(d) {
    var age = ((jd(d) - 2451550.26) % 29.530588853 + 29.530588853) % 29.530588853, f = (1 - Math.cos(2 * Math.PI * age / 29.530588853)) / 2;
    var name = age < 1.5 || age > 28 ? "new moon" : age < 6.4 ? "waxing crescent" : age < 8.9 ? "first quarter" : age < 13.8 ? "waxing gibbous" : age < 15.8 ? "full moon" : age < 20.8 ? "waning gibbous" : age < 23.3 ? "last quarter" : "waning crescent";
    return name + ", " + Math.round(f * 100) + "% lit";
  }

  /* ---------- drawing ---------- */
  function build() {
    el = $("solar");
    svg = d3.select(el).append("svg").attr("class", "orrery");
    var defs = svg.append("defs");
    var hp = defs.append("pattern").attr("id", "hatch").attr("width", 5).attr("height", 5).attr("patternUnits", "userSpaceOnUse").attr("patternTransform", "rotate(38)");
    hp.append("line").attr("x1", 0).attr("y1", 0).attr("x2", 0).attr("y2", 5).attr("stroke-width", 0.8);
    var g2 = defs.append("radialGradient").attr("id", "sunglow");
    [["0%", "#ffffff", 1], ["35%", "#fff6c0", 0.95], ["100%", "#fff6c0", 0]].forEach(function (s) { g2.append("stop").attr("offset", s[0]).attr("stop-color", s[1]).attr("stop-opacity", s[2]); });
    gAll = svg.append("g");
    var bar = d3.select(el).append("div").attr("class", "orr-bar").html(
      '<div class="orr-row"><input id="orr-q" placeholder="find a planet, spacecraft or country (Voyager, Mars, India…)" autocomplete="off"><button id="orr-list" title="every spacecraft beyond Earth">spacecraft ▾</button><button id="orr-arc" title="people in space, the Golden Record, space sounds, mission planner">archive ▾</button><button id="orr-trl" title="show where the long-haul probes have been since launch" aria-pressed="false">paths</button><button id="orr-home" title="back to the whole solar system">⌂</button><button id="orr-gal" title="zoom out to the Milky Way">milky way ▸</button></div><div id="orr-res" class="orr-res" hidden></div><div id="orr-dd" class="orr-res orr-dd" hidden></div><div id="orr-arcdd" class="orr-res orr-dd" hidden></div>');
    d3.select(el).append("div").attr("class", "orr-theme").html('<span>style</span><select id="orr-style">' + Object.keys(THEMES).map(function (k) { return '<option value="' + k + '">' + THEMES[k].label + "</option>"; }).join("") + "</select>");
    $("orr-style").onchange = function () { setTheme(this.value); };
    d3.select(el).select(".orr-theme").append("label").attr("class", "orr-nightlab").attr("title", "switch light styles to a dark one between sunset and sunrise").html('<input type="checkbox" id="orr-night"> dark after sunset');
    $("orr-night").checked = nightOn();
    $("orr-night").onchange = function () { try { localStorage.setItem(NIGHT_KEY, this.checked ? "1" : "0"); } catch (e) { } applyTheme(themePref()); };
    d3.select(el).append("div").attr("class", "orr-cap").attr("id", "orr-cap").attr("hidden", true);
    $("orr-trl").onclick = function () { setTrails(!trailsOn); };
    $("orr-trl").setAttribute("aria-pressed", trailsOn ? "true" : "false");
    $("orr-home").onclick = function () { fly(0, 0, 0, 1, null); };
    $("orr-gal").onclick = function () { enterGalaxy(true); };
    $("orr-arc").onclick = function () {
      var m = $("orr-arcdd"); if (!m.hidden) { m.hidden = true; return; } $("orr-res").hidden = true; $("orr-dd").hidden = true;
      var ex = archive(); if (!ex) return;
      var mine = [["grandtour", "The Grand Tour: replay the Voyagers from 1977"], ["launches", "Rocket launches: what's next"], ["moon", "The Moon: phases and every landing"]];
      m.innerHTML = ex.menu.concat(mine).map(function (x) { return '<button data-k="' + x[0] + '"><b>' + esc(x[1]) + "</b></button>"; }).join(""); m.hidden = false;
      m.querySelectorAll("button").forEach(function (b) { b.onclick = function () { m.hidden = true; if (!localOpen(b.dataset.k)) ex.open(b.dataset.k); }; });
    };
    $("orr-list").onclick = function () { var dd = $("orr-dd"); if (!dd.hidden) { dd.hidden = true; return; } $("orr-res").hidden = true; $("orr-arcdd").hidden = true; dd.innerHTML = craftMenu(); dd.hidden = false;
      dd.querySelectorAll("button").forEach(function (b) { b.onclick = function () { dd.hidden = true; var c = CRAFT.find(function (x) { return x[1] === b.dataset.n; }); if (c) goCraft(c); }; }); };
    applyTheme(themePref());
    d3.select(el).append("div").attr("class", "orr-live").attr("id", "orr-live");
    d3.select(el).append("div").attr("class", "orr-time").html('<button id="orr-back" title="back 30 days">◀ 30d</button><button id="orr-play" title="run time forward, 10 days a second">▶</button><button id="orr-fwd" title="forward 30 days">30d ▶</button><span id="orr-date"></span><button id="orr-now">now</button>');
    d3.select(el).append("div").attr("class", "orr-note").html("Distances are squeezed so every planet fits on the machine: the real gap from Mars to Neptune is 20 times the gap from Earth to Mars. Planet positions are worked out on your PC; spacecraft positions come from NASA JPL twice a day. Drag to turn it or tip it, scroll to zoom. The ring's months show where Earth is in its year.");
    // drag to turn, wheel to zoom
    var drag = null;
    // no pointer capture: it would send every click to the background instead of the planet under the mouse
    svg.on("pointerdown", function (e) { if (e.button === 0) drag = [e.clientX, e.clientY, yaw, tilt, false]; });
    window.addEventListener("pointermove", function (e) {
      if (!drag || !active) return;
      var dx = e.clientX - drag[0], dy = e.clientY - drag[1];
      if (!drag[4] && Math.abs(dx) + Math.abs(dy) < 4) return;
      drag[4] = true; yaw = drag[2] + dx * 0.4; tilt = Math.max(3, Math.min(89, drag[3] + dy * 0.3)); draw();
    });
    window.addEventListener("pointerup", function () { if (drag) { var was = drag[4]; setTimeout(function () { if (drag && drag[4] === was) drag = null; }, 0); } });
    var outPush = 0;   // scrolling out past the smallest size, twice, leaves for the Milky Way
    svg.on("wheel", function (e) {
      e.preventDefault();
      if (e.deltaY > 0 && zoom <= 0.701) { if (++outPush >= 2) { outPush = 0; enterGalaxy(true); } return; }
      outPush = 0;
      zoom = Math.max(0.7, Math.min(40, zoom * (e.deltaY < 0 ? 1.15 : 1 / 1.15))); if (zoom < 1.3 && focusName) { fx = fy = fz = 0; focusName = null; } draw();
    });
    svg.on("click", function (e) { if (drag && drag[4]) e.stopPropagation(); }, true);
    $("orr-play").onclick = function () { playing = !playing; this.textContent = playing ? "❚❚" : "▶"; lastT = performance.now(); if (playing) loop(); };
    $("orr-back").onclick = function () { dt -= 30; draw(); };
    $("orr-fwd").onclick = function () { dt += 30; draw(); };
    $("orr-now").onclick = function () { tourOn = false; caption(""); dt = 0; playing = false; PLAN = null; planEnd = null; SPEED = 10; $("orr-play").textContent = "▶"; draw(); };
    var q = $("orr-q"), res = $("orr-res");
    q.oninput = function () {
      var raw = q.value.trim(), v = raw.toLowerCase().replace(/\./g, ""); if (!v) { res.hidden = true; return; }
      var alias = ALIAS[v] || v, esaMember = ESA_MEMBERS.indexOf(v) >= 0;
      var hits = ["Sun"].concat(PLANETS, ["Moon"]).filter(function (n) { return n.toLowerCase().indexOf(v) >= 0; }).map(function (n) { return { k: "p", n: n, sub: n === "Moon" ? "Earth's moon" : n === "Sun" ? "star" : "planet" }; })
        .concat(CRAFT.filter(function (c) {
          var txt = (c[1] + " " + c[2] + " " + c[3] + " " + c[5]).toLowerCase();
          return txt.indexOf(alias) >= 0 || (v.length > 2 && txt.indexOf(v) >= 0) || (esaMember && /ESA/.test(c[3]));
        }).map(function (c) { return { k: "c", c: c, n: c[1], sub: c[2] + " · " + c[3] + (esaMember && /ESA/.test(c[3]) && c[2].toLowerCase().indexOf(v) < 0 ? " (" + raw + " builds and funds ESA missions)" : "") + " · " + where(c) }; }));
      res.innerHTML = hits.length ? hits.slice(0, 30).map(function (h, i) { return '<button data-i="' + i + '"><b>' + esc(h.n) + "</b><span>" + esc(h.sub) + "</span></button>"; }).join("") :
        '<div class="mut" style="padding:8px 10px;line-height:1.5">No spacecraft beyond Earth from "' + esc(raw) + '" in Archie\'s list. Satellites circling Earth (every country\'s) are on the globe: switch on the groups under <b>Space</b> in the layers, then click one to see who owns it.</div>';
      res.hidden = false;
      res.querySelectorAll("button").forEach(function (b) { b.onclick = function () { var h = hits[+b.dataset.i]; res.hidden = true; q.value = ""; if (h.k === "c") goCraft(h.c); else if (h.n === "Moon") { goPlanet("Earth"); setTimeout(showMoon, 750); } else goPlanet(h.n); }; });
    };
    q.onkeydown = function (e) { if (e.key === "Enter") { var b = res.querySelector("button"); if (b) b.click(); } if (e.key === "Escape") { res.hidden = true; q.blur(); } };
    new ResizeObserver(function () { if (active) { size(); draw(); } }).observe(el);
    new MutationObserver(function () { if (active) { if (document.getElementById("card").hidden) sel = null; size(); draw(); } }).observe(document.getElementById("card"), { attributes: true, attributeFilter: ["hidden"] });
  }
  function card() { var c = document.getElementById("card"); return c && !c.hidden && W > 1100; }
  function where(c) { return c[5] === "interstellar" ? "interstellar space" : c[5] === "deep" ? "deep space" : c[5] === "sun" ? "orbiting the Sun" : c[5] === "Moon" ? "at the Moon" : c[5] === "Earth" ? "near Earth" : "at " + c[5]; }
  var OPTS = window.__orrOpts || { stars: true, belts: true, helio: true, rings: true, strip: true, big: true, near: true, ladder: true, title: true };
  function size() {   // with the side cards showing, the machine moves a little left so they don't cover its ring
    W = el.clientWidth; H = el.clientHeight; var side = (OPTS.near || OPTS.ladder || OPTS.roster) && W > 1100;
    R = OPTS.big ? Math.min(W * (side ? 0.33 : 0.36), H * 0.56) : Math.min(W * 0.3, H * 0.5); cx = card() ? W * 0.4 : side ? (W - 300) / 2 + 10 : W / 2; cy = H * 0.47; svg.attr("viewBox", "0 0 " + W + " " + H);
  }
  function path(pts) { return "M" + pts.map(function (p) { var s = proj(p); return s[0].toFixed(1) + "," + s[1].toFixed(1); }).join("L"); }
  // the machine: a many-sided base, columns holding a flat horizon ring, a center column with the Sun,
  // and one arm per planet (stacked at different heights) with a post up to the planet
  var ZB = -0.3, ZR = -0.015, RR0 = 1.03, RR1 = 1.13, NSIDE = 10;
  function ringPts(r, z, n, a0, a1) { var out = []; for (var i = 0; i <= n; i++) { var a = a0 + (a1 - a0) * i / n; out.push(projW([Math.cos(a) * r, Math.sin(a) * r, z])); } return out; }
  function lineP(pts) { return "M" + pts.map(function (p) { return p[0].toFixed(1) + "," + p[1].toFixed(1); }).join("L"); }
  function seg(g, a, b, cls) { var A = projW(a), B = projW(b); return g.append("line").attr("x1", A[0]).attr("y1", A[1]).attr("x2", B[0]).attr("y2", B[1]).attr("class", cls); }
  function draw() {
    if (!el || !active || inGal) return;
    var d = now(); gAll.selectAll("*").remove(); svg.select("defs").selectAll("clipPath").remove(); body.n = 0;
    $("orr-date").textContent = d.toLocaleDateString([], { year: "numeric", month: "short", day: "numeric" }) + (dt ? "" : " · now");
    if (OPTS.stars) sky();
    decorate();
    avoidReset();
    if (OPTS.title) titleBlock(d);
    var below = OPTS.near ? starMap(d) : null;
    if (OPTS.ladder) ladder(d, below); else if (OPTS.roster) roster(d);
    var y0 = yaw * D2R, back = [], front = [];
    // base: two stacked polygons with a skirt
    var poly = function (r, z) { var pts = []; for (var i = 0; i <= NSIDE; i++) { var a = (i / NSIDE) * 2 * Math.PI + Math.PI / NSIDE; pts.push(projW([Math.cos(a) * r, Math.sin(a) * r, z])); } return pts; };
    var top = poly(1.17, ZB), bot = poly(1.19, ZB - 0.06);
    gAll.append("path").attr("d", lineP(bot) + "Z").attr("class", "orr-base");
    for (var i = 0; i < NSIDE; i++) gAll.append("path").attr("d", lineP([top[i], top[i + 1], bot[i + 1], bot[i]]) + "Z").attr("class", "orr-skirt");
    gAll.append("path").attr("d", lineP(top) + "Z").attr("class", "orr-base top");
    gAll.append("path").attr("d", lineP(poly(0.72, ZB)) + "Z").attr("class", "orr-inlay");
    // columns under the ring (the far ones first, near ones at the end)
    var posts = [];
    for (i = 0; i < 12; i++) { var a = i / 12 * 2 * Math.PI, p = [Math.cos(a) * 1.08, Math.sin(a) * 1.08]; posts.push({ p: p, depth: projW([p[0], p[1], 0])[2] }); }
    posts.filter(function (q) { return q.depth > 0; }).forEach(function (q) { seg(gAll, [q.p[0], q.p[1], ZB], [q.p[0], q.p[1], ZR - 0.01], "orr-post"); });
    // the far half of the horizon ring
    var farA0 = -y0, ringBack = function (r) { return ringPts(r, ZR, 60, farA0, farA0 + Math.PI); };
    var ringFront = function (r) { return ringPts(r, ZR, 60, farA0 + Math.PI, farA0 + 2 * Math.PI); };
    gAll.append("path").attr("d", lineP(ringBack(RR1)) + "L" + lineP(ringBack(RR0).reverse()).slice(1) + "Z").attr("class", "orr-ring-band");
    // orbits (faint) in the planet plane
    if (TH.bands) PLANETS.slice().reverse().forEach(function (n, i) { if (n !== "Pluto") gAll.append("path").attr("d", path(orbit(n, d)) + "Z").attr("fill", TH.bands[i % TH.bands.length]).attr("fill-opacity", TH.bandOp).attr("stroke", "none"); });
    PLANETS.forEach(function (n, i) { gAll.append("path").attr("d", path(orbit(n, d))).attr("class", "orr-orbit" + (n === "Pluto" ? " dwarf" : "")).style("stroke", TH.orbitCols ? TH.orbitCols[i % TH.orbitCols.length] : null); });
    // everything that stands up: center column, arms, posts, planets, sorted far to near
    var things = [], hub = 0;
    things.push({ depth: projW([0, 0, 0])[2], draw: function () {
      seg(gAll, [0, 0, ZB], [0, 0, -0.03], "orr-column");
      for (var k = 0; k < 4; k++) { var z = ZB + 0.04 + k * 0.03, e = ringPts(0.08 - k * 0.012, z, 24, 0, 2 * Math.PI); gAll.append("path").attr("d", lineP(e)).attr("class", "orr-gear"); }
      var s = projW([0, 0, 0]);
      gAll.append("circle").attr("cx", s[0]).attr("cy", s[1]).attr("r", 30 * Math.sqrt(zoom)).attr("fill", "url(#sunglow)").style("pointer-events", "none");
      var sg = gAll.append("g").attr("transform", "translate(" + s[0] + "," + s[1] + ")").style("cursor", "pointer").on("click", function () { showPlanet("Sun"); });
      var sr = PL.Sun[1] * Math.min(3, Math.sqrt(zoom));
      for (var k2 = 0; k2 < 16; k2++) { var aa = k2 / 16 * 2 * Math.PI; sg.append("line").attr("x1", Math.cos(aa) * sr * 1.15).attr("y1", Math.sin(aa) * sr * 1.15).attr("x2", Math.cos(aa) * sr * (k2 % 2 ? 1.5 : 1.85)).attr("y2", Math.sin(aa) * sr * (k2 % 2 ? 1.5 : 1.85)).attr("class", "orr-ray"); }
      sg.append("circle").attr("r", sr).attr("fill", TH.sun).attr("class", "orr-body sun");
      if (TH.latin) sg.append("text").attr("y", sr * 1.9 + 11).attr("text-anchor", "middle").attr("class", "orr-lab").text("SOL");
    } });
    PLANETS.forEach(function (n, idx) {
      var P = helio(n, d), q = squash(P), zArm = -0.05 - idx * 0.02, pz = Math.max(q[2], zArm + 0.03);
      var sp = projW([q[0], q[1], pz]);
      things.push({ depth: sp[2], draw: function () {
        seg(gAll, [0, 0, zArm], [q[0], q[1], zArm], "orr-arm");
        seg(gAll, [q[0], q[1], zArm], [q[0], q[1], pz], "orr-rod");
        var g = gAll.append("g").attr("class", "orr-pl" + (sel === n ? " sel" : "")).attr("transform", "translate(" + sp[0] + "," + sp[1] + ")").style("cursor", "pointer");
        var r = PL[n][1] * bodyScale();
        var sunS = projW([0, 0, 0]), sunDir = Math.atan2(sunS[1] - sp[1], sunS[0] - sp[0]);
        if (RINGS[n]) ringHalf(g, n, r, true);
        (MOONS[n] || []).slice(0, 4).forEach(function (m, k) {   // little moon arms, like a real orrery
          var ang = (jd(d) / m[1]) * 2 * Math.PI + k, rr = r * (RINGS[n] ? 2.5 : 1) + 5 + k * 3.2;
          var mx = Math.cos(ang) * rr, my = Math.sin(ang) * rr * Math.max(0.25, Math.sin(tilt * D2R));
          g.append("line").attr("x1", 0).attr("y1", 0).attr("x2", mx).attr("y2", my).attr("class", "orr-moonarm");
          g.append("circle").attr("cx", mx).attr("cy", my).attr("r", 1.5).attr("class", "orr-moon");
        });
        g.append("circle").attr("r", r + 7).attr("fill", "transparent");
        body(g, n, r, sunDir, d);
        if (RINGS[n]) ringHalf(g, n, r, false);
        if (sel === n) g.append("circle").attr("r", r + 5).attr("class", "orr-selring");
        var lab = g.append("text").attr("x", r + 5).attr("y", -r - 2).attr("class", "orr-lab").text(TH.latin ? LATIN[n] : TH.upper ? n.toUpperCase() : n);
        if (TH.latin) g.append("text").attr("x", r + 5).attr("y", -r + 8).attr("class", "orr-lab2").text(n);
        g.on("click", function () { showPlanet(n); }).on("dblclick", function (e) { e.stopPropagation(); goPlanet(n); });
      } });
    });
    CRAFT.forEach(function (c) {
      if (!/^(deep|sun|interstellar)$/.test(c[5])) return;
      if (beforeLaunch(c[0], d)) return;
      var p = craftPos(c, d); if (!p) return;
      if (Math.abs(dt) > 60 && c[5] !== "interstellar" && !trailCovers(c[0], d)) return;
      var rAU = Math.hypot(p[0], p[1], p[2]), far = rAU > RMAX, q = squash(p);
      if (far) { var k2 = 1.19 / Math.hypot(q[0], q[1]); q = [q[0] * k2, q[1] * k2, Math.max(-0.12, Math.min(0.32, q[2] * k2))]; }
      var s = projW(q);
      things.push({ depth: s[2], draw: function () {
        seg(gAll, [q[0], q[1], ZR], q, "orr-drop");
        var g = gAll.append("g").attr("class", "orr-sc" + (sel === c[1] ? " sel" : "")).attr("transform", "translate(" + s[0] + "," + s[1] + ")").style("cursor", "pointer");
        g.append("rect").attr("x", -3.2).attr("y", -3.2).attr("width", 6.4).attr("height", 6.4).attr("transform", "rotate(45)");
        g.append("rect").attr("x", -8).attr("y", -8).attr("width", 16).attr("height", 16).attr("fill", "transparent");
        if (far || Math.hypot(q[0], q[1]) * zoom > 0.42 || sel === c[1]) g.append("text").attr("x", 6).attr("y", -5).attr("class", "orr-sclab").text(c[1] + (far ? " · " + Math.round(rAU) + " AU" : ""));
        g.append("title").text(c[1] + " · " + c[2]);
        g.on("click", function () { showCraft(c); });
      } });
    });
    if (OPTS.rings) distanceRings();
    if (OPTS.belts) belts();
    if (OPTS.helio) helioRing();
    if (trailsOn && TRAILS) drawTrails(d);
    drawPing();
    if (tourOn) tourCaption(d);
    if (PLAN) drawPlan(d);
    things.sort(function (a, b) { return b.depth - a.depth; }).forEach(function (t) { t.draw(); });
    // near half of the ring with its scale, then the near columns
    gAll.append("path").attr("d", lineP(ringFront(RR1)) + "L" + lineP(ringFront(RR0).reverse()).slice(1) + "Z").attr("class", "orr-ring-band front");
    for (i = 0; i < 72; i++) {   // a 5-degree scale around the ring
      var aa = i / 72 * 2 * Math.PI, A = projW([Math.cos(aa) * RR0, Math.sin(aa) * RR0, ZR]), B = projW([Math.cos(aa) * (i % 6 ? RR0 + 0.025 : RR0 + 0.05), Math.sin(aa) * (i % 6 ? RR0 + 0.025 : RR0 + 0.05), ZR]);
      gAll.append("line").attr("x1", A[0]).attr("y1", A[1]).attr("x2", B[0]).attr("y2", B[1]).attr("class", "orr-tick");
    }
    for (i = 0; i < 12; i++) {   // month names where Earth is on the 15th of each month
      var ep = helio("Earth", new Date(d.getFullYear(), i, 15)), ang = Math.atan2(ep[1], ep[0]), rm = (RR0 + RR1) / 2 + 0.012;
      var L = projW([Math.cos(ang) * rm, Math.sin(ang) * rm, ZR]);
      gAll.append("text").attr("x", L[0]).attr("y", L[1] + 3).attr("text-anchor", "middle").attr("class", "orr-mon").text(new Date(2000, i, 1).toLocaleDateString("en-US", { month: "short" }));
    }
    if (TH.zodiac) zodiacRing(d);
    posts.filter(function (q) { return q.depth <= 0; }).forEach(function (q) { seg(gAll, [q.p[0], q.p[1], ZB], [q.p[0], q.p[1], ZR - 0.01], "orr-post"); });
    var lowest = d3.max(bot, function (q) { return q[1]; });
    if (OPTS.strip) scaleStrip(d);
    if (lowest + 16 < H - 90 && !OPTS.strip) gAll.append("text").attr("x", cx).attr("y", lowest + 16).attr("text-anchor", "middle").attr("class", "orr-plate").text("ARCHIE ORRERY · " + d.toLocaleDateString([], { day: "numeric", month: "short", year: "numeric" }).toUpperCase());
  }
  function loop() {
    if (!playing || !active) return;
    var t = performance.now(); dt += (t - lastT) / 1000 * SPEED; lastT = t;
    if (planEnd != null && dt >= planEnd) { dt = planEnd; planEnd = null; playing = false; SPEED = 10; var pb = $("orr-play"); if (pb) pb.textContent = "▶"; draw(); if (tourOn) tourDone(); return; }
    draw();
    raf = setTimeout(function () { requestAnimationFrame(loop); }, 50);   // ~20 frames a second is plenty
  }




  /* ---------- a sense of scale: the sky, the belts, distance rings, and the real-scale strip ---------- */
  function rng(seed) { return function () { seed |= 0; seed = seed + 0x6D2B79F5 | 0; var t = Math.imul(seed ^ seed >>> 15, 1 | seed); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
  var SKY = null, BELT = null;
  function light() { return /^(harmonia|moebius|nasa|cosmos)$/.test(el.dataset.theme || ""); }
  function sky() {
    if (!SKY) {   // directions on the sky; a denser band along the Milky Way (tilted about 60° to the planets' plane)
      var r = rng(7), out = [], gi = 60 * D2R, gn = 270 * D2R;
      for (var i = 0; i < 1400; i++) { var u = r() * 2 - 1, a = r() * 2 * Math.PI, c = Math.sqrt(1 - u * u); out.push([c * Math.cos(a), c * Math.sin(a), u, Math.pow(r(), 3), 0]); }
      for (i = 0; i < 2600; i++) {
        var L = r() * 2 * Math.PI, b = (r() + r() + r() - 1.5) * 0.16;
        var x = Math.cos(b) * Math.cos(L), y = Math.cos(b) * Math.sin(L), z = Math.sin(b);
        var y2 = y * Math.cos(gi) - z * Math.sin(gi), z2 = y * Math.sin(gi) + z * Math.cos(gi);   // tip the band
        var x3 = x * Math.cos(gn) - y2 * Math.sin(gn), y3 = x * Math.sin(gn) + y2 * Math.cos(gn);
        out.push([x3, y3, z2, Math.pow(r(), 5) * 0.5, 1]);
      }
      SKY = out;
    }
    var g = gAll.append("g").style("pointer-events", "none"), dark = !light(), col = dark ? "#ffffff" : (TH.vars.line || "#111");
    var y0 = yaw * D2R, el0 = tilt * D2R, S = Math.max(W, H) * 0.62;
    SKY.forEach(function (st) {
      var x1 = st[0] * Math.cos(y0) - st[1] * Math.sin(y0), y1 = st[0] * Math.sin(y0) + st[1] * Math.cos(y0);
      var depth = y1 * Math.cos(el0) - st[2] * Math.sin(el0);
      if (depth < -0.15) return;   // behind the viewer
      var sx = W / 2 + x1 * S, sy = H * 0.45 - y1 * Math.sin(el0) * S - st[2] * Math.cos(el0) * S;
      if (sx < -5 || sx > W + 5 || sy < -5 || sy > H + 5) return;
      g.append("circle").attr("cx", sx).attr("cy", sy).attr("r", 0.45 + st[3] * 1.6).attr("fill", col).attr("opacity", (st[4] ? 0.22 : 0.45) + st[3] * 0.5);
    });
  }
  function belts() {
    if (!BELT) {
      var r = rng(11), ast = [], kui = [];
      for (var i = 0; i < 520; i++) { var a = 2.15 + r() * 1.15, t = r() * 2 * Math.PI; ast.push([a * Math.cos(t), a * Math.sin(t), (r() - 0.5) * 0.25]); }
      for (i = 0; i < 420; i++) { a = 30.5 + r() * 18; t = r() * 2 * Math.PI; kui.push([a * Math.cos(t), a * Math.sin(t), (r() - 0.5) * 3]); }
      BELT = { ast: ast, kui: kui };
    }
    var g = gAll.append("g").style("pointer-events", "none"), col = TH.vars.orbit;
    [["ast", 0.8, 0.55], ["kui", 0.9, 0.4]].forEach(function (b) {
      BELT[b[0]].forEach(function (p) { var s = proj(p); g.append("circle").attr("cx", s[0]).attr("cy", s[1]).attr("r", b[1] * Math.min(2.5, Math.sqrt(zoom))).attr("fill", col).attr("opacity", b[2]); });
    });
    var lab = function (au, ang, text) { var s = proj([au * Math.cos(ang), au * Math.sin(ang), 0]); g.append("text").attr("x", s[0]).attr("y", s[1] - 6).attr("text-anchor", "middle").attr("class", "orr-beltlab").text(text); };
    lab(2.7, -2.2 - yaw * D2R, "ASTEROID BELT");
    lab(38, -2.0 - yaw * D2R, "KUIPER BELT");
  }
  function helioRing() {   // the edge of the Sun's bubble is about 120 AU out, past the squeezed scale, so it sits at the rim with the Voyagers
    var pts = ringPts(1.165, ZR, 120, 0, 2 * Math.PI);
    gAll.append("path").attr("d", lineP(pts)).attr("class", "orr-helio");
    var a = Math.PI * 0.5 - yaw * D2R, s = projW([Math.cos(a) * 1.165, Math.sin(a) * 1.165, ZR]);
    gAll.append("text").attr("x", s[0]).attr("y", s[1] - 6).attr("text-anchor", "middle").attr("class", "orr-beltlab").text("HELIOPAUSE · ABOUT 120 AU · THE SUN'S BUBBLE ENDS (VOYAGERS ARE PAST IT)");
  }
  function distanceRings() {
    [[1, "1 AU · light takes 8 min"], [5, "5 AU · 42 min"], [10, "10 AU · 1.4 h"], [30, "30 AU · 4.2 h"]].forEach(function (rg, i) {
      var pts = []; for (var k = 0; k <= 120; k++) { var a = k / 120 * 2 * Math.PI; pts.push(proj([Math.cos(a) * rg[0], Math.sin(a) * rg[0], 0])); }
      gAll.append("path").attr("d", lineP(pts)).attr("class", "orr-dring");
      var a2 = -Math.PI / 2 - yaw * D2R + 0.35, s = proj([Math.cos(a2) * rg[0], Math.sin(a2) * rg[0], 0]);
      gAll.append("text").attr("x", s[0] + 4).attr("y", s[1] + 10).attr("class", "orr-dlab").text(rg[1]);
    });
  }
  /* the corner cards fold up to their title bar: click the title; Archie remembers */
  var FOLD = (function () { try { return JSON.parse(localStorage.getItem("archieOrreryFold") || "{}"); } catch (e) { return {}; } })();
  function foldHead(g, x, y, w, title, key) {
    var open = !FOLD[key], hg = g.append("g").attr("class", "orr-fold").style("pointer-events", "all").style("cursor", "pointer");
    hg.append("rect").attr("x", x).attr("y", y).attr("width", w).attr("height", 30).attr("fill", "transparent");
    hg.append("text").attr("x", x + 14).attr("y", y + 19).attr("class", "orr-striph").text(title);
    hg.append("text").attr("x", x + w - 14).attr("y", y + 19).attr("text-anchor", "end").attr("class", "orr-fold-caret").text(open ? "▾" : "▸");
    hg.append("title").text(open ? "fold this card" : "open this card");
    hg.on("pointerdown", function (e) { e.stopPropagation(); }).on("click", function (e) {
      e.stopPropagation(); FOLD[key] = open; try { localStorage.setItem("archieOrreryFold", JSON.stringify(FOLD)); } catch (err) { } draw();
    });
    return open;
  }
  function scaleStrip(d) {   // a card in the corner: true distances (top) and true sizes (bottom)
    var w = Math.min(500, W * 0.3), x0 = 34, top = H - 196, g = gAll.append("g").attr("class", "orr-strip").style("pointer-events", "none");
    if (FOLD.strip) { g.append("rect").attr("x", x0 - 18).attr("y", H - 76).attr("width", w + 36).attr("height", 30).attr("rx", 9).attr("class", "orr-stripbg"); foldHead(g, x0 - 18, H - 76, w + 36, "REAL DISTANCES AND SIZES", "strip"); return; }
    g.append("rect").attr("x", x0 - 18).attr("y", top).attr("width", w + 36).attr("height", 150).attr("rx", 9).attr("class", "orr-stripbg");
    foldHead(g, x0 - 18, top - 1, w + 36, "REAL DISTANCES FROM THE SUN, TO SCALE", "strip");
    // distances
    var y1 = top + 42, maxAU = 31;
    g.append("line").attr("x1", x0).attr("x2", x0 + w).attr("y1", y1).attr("y2", y1).attr("class", "orr-stripline");
    g.append("circle").attr("cx", x0).attr("cy", y1).attr("r", 4).attr("fill", TH.sun);
    PLANETS.slice(0, 8).forEach(function (n, i) {
      var r = Math.hypot.apply(null, helio(n, d)), x = x0 + r / maxAU * w;
      g.append("circle").attr("cx", x).attr("cy", y1).attr("r", i < 4 ? 2 : 3).attr("fill", TH.planet[n] || PL[n][0]).attr("class", "orr-body");
      if (i >= 4) g.append("text").attr("x", x).attr("y", y1 + 15).attr("text-anchor", "middle").attr("class", "orr-striplab").text(n);
    });
    g.append("path").attr("d", "M" + (x0 + 2) + "," + (y1 - 7) + " h" + (1.6 / maxAU * w)).attr("class", "orr-stripline");
    g.append("text").attr("x", x0).attr("y", y1 + 15).attr("class", "orr-striplab").text("rocky 4");
    g.append("text").attr("x", x0 + w - 18).attr("y", top + 18).attr("text-anchor", "end").attr("class", "orr-striplab").text("Voyager 1: 5½ widths further →");
    // sizes, all at one scale; the Sun is so big only its edge fits
    var ys = top + 108, k = 150 / 696340, rS = 696340 * k, cid = "stripclip" + (++body.n);
    svg.select("defs").append("clipPath").attr("id", cid).append("rect").attr("x", x0 - 18).attr("y", top + 70).attr("width", w + 36).attr("height", 80);
    g.append("text").attr("x", x0 + 40).attr("y", top + 80).attr("class", "orr-striph").text("REAL SIZES, SAME SCALE");
    g.append("circle").attr("cx", x0 + 16 - rS).attr("cy", ys).attr("r", rS).attr("fill", TH.sun).attr("clip-path", "url(#" + cid + ")");
    var cx2 = x0 + 34;
    PLANETS.slice(0, 8).forEach(function (n) {
      var r = Math.max(0.8, PL[n][2] * k);
      cx2 += r + 8;
      g.append("circle").attr("cx", cx2).attr("cy", ys).attr("r", r).attr("fill", TH.planet[n] || PL[n][0]).attr("class", "orr-body");
      if (n === "Jupiter" || n === "Saturn") g.append("text").attr("x", cx2).attr("y", ys + r + 11).attr("text-anchor", "middle").attr("class", "orr-striplab").text(n);
      cx2 += r;
    });
    g.append("text").attr("x", cx2 + 12).attr("y", ys - 4).attr("class", "orr-striplab").text("Earth is the dot after Venus.");
    g.append("text").attr("x", cx2 + 12).attr("y", ys + 8).attr("class", "orr-striplab").text("1.3 million Earths fit in the Sun.");
  }
  /* ---------- beyond the machine: the nearest stars, where the probes are heading, how far light goes ---------- */
  // [name, right ascension (hours), declination (deg), light-years, note]
  var NEAR = [
    ["Alpha Centauri", 14.66, -60.83, 4.37, "The closest star system: two Sun-like stars plus Proxima, a small red star 4.24 light-years away with at least one planet."],
    ["Barnard's Star", 17.963, 4.69, 5.96, "A small, old red star. It moves across our sky faster than any other star."],
    ["Wolf 359", 10.941, 7.01, 7.86, "A dim red star, too faint to see without a telescope."],
    ["Lalande 21185", 11.056, 35.97, 8.31, "A red star with at least two planets."],
    ["Sirius", 6.7525, -16.72, 8.6, "The brightest star in the night sky, twice the Sun's mass, with a white dwarf partner."],
    ["Luyten 726-8", 1.65, -17.95, 8.7, "A pair of small red stars; one of them, UV Ceti, flares."],
    ["Ross 154", 18.83, -23.84, 9.7, "A red star that flares."],
    ["Ross 248", 23.699, 44.17, 10.3, "Voyager 2 will pass about 1.7 light-years from it in roughly 40,000 years."],
    ["Epsilon Eridani", 3.549, -9.46, 10.5, "A young Sun-like star with a dust ring and a giant planet."],
    ["61 Cygni", 21.115, 38.75, 11.4, "The first star whose distance was measured (1838)."],
    ["Procyon", 7.655, 5.22, 11.5, "One of the brightest stars, with a white dwarf partner."],
    ["Tau Ceti", 1.734, -15.94, 11.9, "A Sun-like star with possible planets; a favorite in science fiction."],
    ["Gliese 445", 11.795, 78.68, 17.1, "Voyager 1 will pass about 1.6 light-years from it in roughly 40,000 years (the star is moving toward us)."]
  ];
  var HEAD = { "-31": ["VOYAGER 1", "toward Ophiuchus · passes Gliese 445 in ~40,000 yr"], "-32": ["VOYAGER 2", "toward Pavo · passes Ross 248 in ~40,000 yr"], "-98": ["NEW HORIZONS", "toward Sagittarius"] };
  var LY_AU = 63241, OBL = 23.439 * D2R;
  function eclDir(raH, dec) {   // star direction, equatorial -> ecliptic
    var a = raH * 15 * D2R, dd = dec * D2R, x = Math.cos(dd) * Math.cos(a), y = Math.cos(dd) * Math.sin(a), z = Math.sin(dd);
    return [x, y * Math.cos(OBL) + z * Math.sin(OBL), -y * Math.sin(OBL) + z * Math.cos(OBL)];
  }
  function skyXY(v) {   // a direction on the sky -> screen, the same way the background stars are drawn
    var y0 = yaw * D2R, el0 = tilt * D2R, S = Math.max(W, H) * 0.62;
    var x1 = v[0] * Math.cos(y0) - v[1] * Math.sin(y0), y1 = v[0] * Math.sin(y0) + v[1] * Math.cos(y0);
    return [W / 2 + x1 * S, H * 0.45 - y1 * Math.sin(el0) * S - v[2] * Math.cos(el0) * S, y1 * Math.cos(el0) - v[2] * Math.sin(el0)];
  }
  var AVOID = [];
  function avoidReset() {   // the machine and the panels sitting over the view
    AVOID = [];
    var rp = ringPts(1.25, ZR, 48, 0, 2 * Math.PI).concat(ringPts(1.25, ZB - 0.06, 48, 0, 2 * Math.PI));
    AVOID.push([d3.min(rp, function (q) { return q[0]; }) - 10, d3.min(rp, function (q) { return q[1]; }) - 60 * Math.sqrt(zoom), d3.max(rp, function (q) { return q[0]; }) + 10, d3.max(rp, function (q) { return q[1]; }) + 24]);
    var host = el.getBoundingClientRect();
    ["orr-live", "orr-style", "orr-q"].forEach(function (id) {
      var n = document.getElementById(id); if (!n) return; if (id !== "orr-live") n = n.parentNode;
      var r = n.getBoundingClientRect(); if (r.width) AVOID.push([r.left - host.left - 8, r.top - host.top - 8, r.right - host.left + 8, r.bottom - host.top + 8]);
    });
    AVOID.push([0, H - 60, W, H]);   // the note and the time buttons
  }
  function free(x0, y0, x1, y1) {
    if (x0 < 4 || y0 < 4 || x1 > W - 4 || y1 > H - 4) return false;
    for (var i = 0; i < AVOID.length; i++) { var a = AVOID[i]; if (x0 < a[2] && x1 > a[0] && y0 < a[3] && y1 > a[1]) return false; }
    return true;
  }
  function starMap(d) {   // the Sun's neighbourhood: the nearest stars on stems over a floor, turning with the machine
    if (card()) return null;
    var w = 270, h = 300, x0 = W - w - 26, top = 62, R2 = 118, LYMAX = 15.5, cx2 = x0 + w / 2, cy2 = top + 185;
    if (FOLD.near) {
      var gf = gAll.append("g").attr("class", "orr-strip"); AVOID.push([x0 - 6, top - 6, x0 + w + 6, top + 36]);
      gf.append("rect").attr("x", x0).attr("y", top).attr("width", w).attr("height", 30).attr("rx", 9).attr("class", "orr-stripbg");
      foldHead(gf, x0, top, w, "THE NEAREST STARS · TO SCALE", "near"); return top + 30;
    }
    AVOID.push([x0 - 6, top - 6, x0 + w + 6, top + h + 6]);
    var y0 = yaw * D2R, el0 = Math.max(38, tilt) * D2R, k = R2 / LYMAX;
    var P = function (v) { var x1 = v[0] * Math.cos(y0) - v[1] * Math.sin(y0), y1 = v[0] * Math.sin(y0) + v[1] * Math.cos(y0); return [cx2 + x1 * k, cy2 - y1 * Math.sin(el0) * k - v[2] * Math.cos(el0) * k * 0.7, y1]; };
    var g = gAll.append("g").attr("class", "orr-strip orr-near");
    g.append("rect").attr("x", x0).attr("y", top).attr("width", w).attr("height", h).attr("rx", 9).attr("class", "orr-stripbg");

    g.append("text").attr("x", x0 + 14).attr("y", top + 33).attr("class", "orr-striplab").text("all of the machine fits inside the Sun's dot");
    [5, 10, 15].forEach(function (r) {
      var pts = []; for (var a = 0; a <= 72; a++) { var t = a / 72 * 2 * Math.PI; pts.push(P([Math.cos(t) * r, Math.sin(t) * r, 0])); }
      g.append("path").attr("d", lineP(pts)).attr("class", "orr-near-floor");
      var lp = P([Math.cos(-y0) * r, Math.sin(-y0) * r, 0]); if (r > 5) g.append("text").attr("x", Math.min(lp[0] + 3, x0 + w - 34)).attr("y", lp[1] + 3).attr("class", "orr-near-sub").text(r + " ly");
    });
    for (var a = 0; a < 12; a++) { var t = a / 12 * 2 * Math.PI, A = P([Math.cos(t) * 2, Math.sin(t) * 2, 0]), B = P([Math.cos(t) * 15, Math.sin(t) * 15, 0]); g.append("line").attr("x1", A[0]).attr("y1", A[1]).attr("x2", B[0]).attr("y2", B[1]).attr("class", "orr-near-floor spoke"); }
    // where the escaping probes are pointed
    Object.keys(HEAD).forEach(function (id) {
      var v = live && live.craft && live.craft[id]; if (!v) return;
      var r = Math.hypot(v.x, v.y, v.z), u = [v.x / r * 15.5, v.y / r * 15.5, v.z / r * 15.5], S0 = P([0, 0, 0]), E = P(u);
      g.append("line").attr("x1", S0[0]).attr("y1", S0[1]).attr("x2", E[0]).attr("y2", E[1]).attr("class", "orr-head-line");
      g.append("text").attr("x", E[0]).attr("y", E[1] - 4).attr("text-anchor", "middle").attr("class", "orr-head-name").text(HEAD[id][0].replace("VOYAGER ", "V").replace("NEW HORIZONS", "NH")).append("title").text(HEAD[id][0] + " is heading " + HEAD[id][1]);
    });
    var S = P([0, 0, 0]);
    g.append("circle").attr("cx", S[0]).attr("cy", S[1]).attr("r", 4).attr("fill", TH.sun);
    g.append("text").attr("x", S[0] + 6).attr("y", S[1] + 11).attr("class", "orr-near-sub").text("Sun");
    var v1 = live && live.craft && live.craft["-31"], v1au = v1 ? Math.hypot(v1.x, v1.y, v1.z) : 170, used = [[S[0] - 5, S[1] - 5, S[0] + 26, S[1] + 13]];
    var stars = NEAR.map(function (st, i) { var v = eclDir(st[1], st[2]), q = [v[0] * st[3], v[1] * st[3], v[2] * st[3]]; return { st: st, i: i, q: q, s: P(q), f: P([q[0], q[1], 0]) }; });
    stars.slice().sort(function (a, b) { return b.s[2] - a.s[2]; }).forEach(function (o) {
      var st = o.st, sg = g.append("g").style("cursor", "help"), r = 2.6 + 4 / st[3];
      sg.append("line").attr("x1", o.f[0]).attr("y1", o.f[1]).attr("x2", o.s[0]).attr("y2", o.s[1]).attr("class", o.q[2] >= 0 ? "orr-near-stem" : "orr-near-stem down");
      sg.append("ellipse").attr("cx", o.f[0]).attr("cy", o.f[1]).attr("rx", 2.5).attr("ry", 1.1).attr("class", "orr-near-foot");
      sg.append("circle").attr("cx", o.s[0]).attr("cy", o.s[1]).attr("r", r + 4).attr("fill", "transparent");
      sg.append("circle").attr("cx", o.s[0]).attr("cy", o.s[1]).attr("r", r).attr("class", "orr-near-star");
      sg.append("title").text(st[0] + " · " + st[3] + " light-years (" + Math.round(st[3] * LY_AU).toLocaleString() + " AU)\nVoyager 1 has gone " + (v1au / (st[3] * LY_AU) * 100).toFixed(2) + "% of that.\n" + st[4]);
      used.push([o.s[0] - r - 1, o.s[1] - r - 1, o.s[0] + r + 1, o.s[1] + r + 1]);
    });
    // labels, most useful first, wherever they fit without covering a star or another label
    stars.slice().sort(function (a, b) { return a.st[3] - b.st[3]; }).forEach(function (o) {
      var t = o.st[0] + " " + o.st[3], lw = t.length * 5.2 + 4, lh = 10, sx = o.s[0], sy = o.s[1];
      [[sx + 7, sy - 4, "start"], [sx - 7 - lw, sy - 4, "end"], [sx - lw / 2, sy - 16, "middle"], [sx - lw / 2, sy + 7, "middle"]].some(function (c) {
        var lx = c[0], ly = c[1];
        if (lx < x0 + 4 || lx + lw > x0 + w - 4 || ly < top + 40 || ly + lh > top + h - 18) return false;
        if (used.some(function (u) { return lx < u[2] && lx + lw > u[0] && ly < u[3] && ly + lh > u[1]; })) return false;
        used.push([lx, ly, lx + lw, ly + lh]);
        g.append("text").attr("x", c[2] === "start" ? lx : c[2] === "end" ? lx + lw : lx + lw / 2).attr("y", ly + 8).attr("text-anchor", c[2]).attr("class", "orr-near-lab").text(t);
        return true;
      });
    });
    g.append("text").attr("x", x0 + 14).attr("y", top + h - 10).attr("class", "orr-striplab").text("V1 V2 NH: where each probe is headed");
    foldHead(g, x0, top + 1, w, "THE NEAREST STARS · TO SCALE", "near");
    return top + h;
  }
  function titleBlock(d) {   // a printed-chart heading in the empty sky, next to the live panel
    var lv = document.getElementById("orr-live"), host = el.getBoundingClientRect(), x = 26, y = 70;
    if (lv && lv.getBoundingClientRect().width) { var r = lv.getBoundingClientRect(); x = r.right - host.left + 30; }
    var v1 = live && live.craft && live.craft["-31"], E = helio("Earth", d), n = live && live.craft ? Object.keys(live.craft).length : 0;
    var doy = Math.floor((d - new Date(d.getFullYear(), 0, 0)) / 86400000);
    var g = gAll.append("g").attr("class", "orr-title").style("pointer-events", "none");
    g.append("text").attr("x", x).attr("y", y + 26).attr("class", "orr-title-big").text("THE SOLAR SYSTEM");
    g.append("rect").attr("x", x).attr("y", y + 36).attr("width", 250).attr("height", 3).attr("class", "orr-title-rule");
    g.append("text").attr("x", x).attr("y", y + 54).attr("class", "orr-title-sub").text(("Positions for " + d.toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" }) + " · day " + doy).toUpperCase());
    g.append("text").attr("x", x).attr("y", y + 68).attr("class", "orr-title-sub dim").text(("8 planets · " + (n || "—") + " spacecraft tracked" + (v1 ? " · Voyager 1's signal takes " + lightTime(dist(E, [v1.x, v1.y, v1.z])) : "")).toUpperCase());
    AVOID.push([x - 6, y, x + 420, y + 76]);
  }
  function ladder(d, below) {   // how far light goes in a second, a minute, an hour… with real things on each rung
    if (card()) return;
    var E = helio("Earth", d), v1 = live && live.craft && live.craft["-31"], LT = function (au) { return au * LIGHT_S; };
    var items = [["the Moon", 1.28], ["the Sun", LT(1)], ["Mars", LT(dist(E, helio("Mars", d)))], ["Jupiter", LT(dist(E, helio("Jupiter", d)))], ["Neptune", LT(dist(E, helio("Neptune", d)))],
      ["Voyager 1", LT(v1 ? dist(E, [v1.x, v1.y, v1.z]) : 170)], ["inner Oort cloud", LT(2000)], ["Proxima Centauri", LT(4.24 * LY_AU)], ["Sirius", LT(8.6 * LY_AU)]];
    var w = 270, x0 = W - w - 26, top = below ? below + 12 : 62, h = Math.min(330, H - top - 110), yA = top + 40, yB = top + h - 18;
    if (FOLD.ladder) {
      var gf = gAll.append("g").attr("class", "orr-strip"); AVOID.push([x0 - 6, top - 6, x0 + w + 6, top + 36]);
      gf.append("rect").attr("x", x0).attr("y", top).attr("width", w).attr("height", 30).attr("rx", 9).attr("class", "orr-stripbg");
      foldHead(gf, x0, top, w, "HOW LONG LIGHT TAKES FROM EARTH", "ladder"); return;
    }
    if (h < 200) return;
    AVOID.push([x0 - 6, top - 6, x0 + w + 6, top + h + 6]);
    var g = gAll.append("g").attr("class", "orr-strip").style("pointer-events", "none");
    g.append("rect").attr("x", x0).attr("y", top).attr("width", w).attr("height", h).attr("rx", 9).attr("class", "orr-stripbg");
    foldHead(g, x0, top + 1, w, "HOW LONG LIGHT TAKES FROM EARTH", "ladder");
    var ys = d3.scaleLog().domain([1, 4e8]).range([yA, yB]), ax = x0 + 92;
    g.append("line").attr("x1", ax).attr("x2", ax).attr("y1", yA).attr("y2", yB).attr("class", "orr-ladder-axis");
    [[1, "1 second"], [60, "1 minute"], [3600, "1 hour"], [86400, "1 day"], [86400 * 30.4, "1 month"], [31557600, "1 year"], [315576000, "10 years"]].forEach(function (t) {
      var y = ys(t[0]);
      g.append("line").attr("x1", ax - 8).attr("x2", ax).attr("y1", y).attr("y2", y).attr("class", "orr-ladder-tick");
      g.append("text").attr("x", ax - 12).attr("y", y + 3).attr("text-anchor", "end").attr("class", "orr-striplab").text(t[1]);
    });
    var lastY = -99;
    items.forEach(function (it) {
      var y = ys(it[1]), ty = Math.max(y, lastY + 13); lastY = ty;
      g.append("circle").attr("cx", ax).attr("cy", y).attr("r", 3).attr("class", "orr-ladder-dot");
      g.append("path").attr("d", "M" + (ax + 4) + "," + y + " L" + (ax + 14) + "," + ty + " h4").attr("class", "orr-ladder-lead");
      var s = it[1], txt = s < 90 ? s.toFixed(1) + " s" : s < 5400 ? Math.round(s / 60) + " min" : s < 172800 ? (s / 3600).toFixed(1) + " h" : s < 31557600 ? Math.round(s / 86400) + " days" : (s / 31557600).toFixed(1) + " yr";
      g.append("text").attr("x", ax + 22).attr("y", ty + 3).attr("class", "orr-striplab").text(it[0] + " · " + txt);
    });
  }
  function roster(d) {   // the deep-space missions still flying, on a 1970–2030 timeline
    if (card()) return;
    var list = CRAFT.filter(function (c) { return /^(deep|interstellar|sun|Jupiter|Saturn|Mars|Venus|Mercury)$/.test(c[5]) && !/ended|lost|over/.test(c[6]); }).sort(function (a, b) { return a[4] - b[4]; }).slice(0, 14);
    var w = 300, x0 = W - w - 26, top = 62, rowH = 15, h = 52 + list.length * rowH, g = gAll.append("g").attr("class", "orr-strip").style("pointer-events", "none");
    AVOID.push([x0 - 6, top - 6, x0 + w + 6, top + h + 6]);
    g.append("rect").attr("x", x0).attr("y", top).attr("width", w).attr("height", h).attr("rx", 9).attr("class", "orr-stripbg");
    g.append("text").attr("x", x0 + 14).attr("y", top + 20).attr("class", "orr-striph").text("STILL FLYING · YEARS IN SPACE");
    var xs = d3.scaleLinear().domain([1970, 2030]).range([x0 + 112, x0 + w - 14]), yr = d.getFullYear() + d.getMonth() / 12;
    [1970, 1990, 2010, 2030].forEach(function (y) { g.append("text").attr("x", xs(y)).attr("y", top + 36).attr("text-anchor", "middle").attr("class", "orr-striplab").text(y); });
    list.forEach(function (c, i) {
      var y = top + 48 + i * rowH;
      g.append("text").attr("x", x0 + 14).attr("y", y + 4).attr("class", "orr-striplab").text(c[1].length > 17 ? c[1].slice(0, 16) + "…" : c[1]);
      g.append("rect").attr("x", xs(c[4])).attr("y", y - 3).attr("width", Math.max(2, xs(yr) - xs(c[4]))).attr("height", 7).attr("class", "orr-roster-bar");
    });
    g.append("line").attr("x1", xs(yr)).attr("x2", xs(yr)).attr("y1", top + 40).attr("y2", top + h - 6).attr("class", "orr-roster-now");
  }
  /* ---------- period decorations drawn behind the machine ---------- */
  function decorate() {
    var sunS = projW([0, 0, 0]), g = gAll.append("g").style("pointer-events", "none");
    if (TH.deco === "bursts") {        // 1960s atomic sparkles
      var spots = [[0.12, 0.2, 22], [0.86, 0.16, 16], [0.08, 0.72, 14], [0.92, 0.66, 26], [0.3, 0.1, 9], [0.7, 0.88, 12], [0.55, 0.08, 7], [0.18, 0.45, 8], [0.8, 0.4, 7]];
      spots.forEach(function (sp) {
        var x = sp[0] * W, y = sp[1] * H, r = sp[2];
        g.append("path").attr("d", "M" + x + "," + (y - r) + " Q" + x + "," + y + " " + (x + r) + "," + y + " Q" + x + "," + y + " " + x + "," + (y + r) + " Q" + x + "," + y + " " + (x - r) + "," + y + " Q" + x + "," + y + " " + x + "," + (y - r) + "Z").attr("fill", TH.burst).attr("opacity", 0.85);
        g.append("circle").attr("cx", x).attr("cy", y).attr("r", r * 0.55).attr("fill", "none").attr("stroke", TH.burst).attr("stroke-width", 1).attr("opacity", 0.5);
      });
      g.append("path").attr("d", "M" + (W * 0.04) + "," + (H * 0.9) + " q" + (W * 0.1) + "," + (-H * 0.12) + " " + (W * 0.22) + ",0").attr("fill", "none").attr("stroke", "#e76f51").attr("stroke-width", 3).attr("opacity", 0.6);
    } else if (TH.deco === "rays") {   // poster sunburst from the Sun
      for (var i = 0; i < 24; i += 2) {
        var a0 = i / 24 * 2 * Math.PI, a1 = (i + 1) / 24 * 2 * Math.PI, L = Math.max(W, H) * 1.5;
        g.append("path").attr("d", "M" + sunS[0] + "," + sunS[1] + " L" + (sunS[0] + Math.cos(a0) * L) + "," + (sunS[1] + Math.sin(a0) * L) + " L" + (sunS[0] + Math.cos(a1) * L) + "," + (sunS[1] + Math.sin(a1) * L) + "Z").attr("fill", TH.rays).attr("opacity", 0.1);
      }
    } else if (TH.deco === "stripes") { // 1970s rainbow halo
      ["#d0318b", "#ff7f11", "#ffbf00", "#8c4a1d"].forEach(function (c, i) {
        g.append("circle").attr("cx", sunS[0]).attr("cy", sunS[1] + R * 0.1).attr("r", R * (1.55 - i * 0.09) * Math.min(1.5, zoom)).attr("fill", "none").attr("stroke", c).attr("stroke-width", R * 0.07).attr("opacity", 0.35);
      });
    } else if (TH.deco === "floor") {  // 1980s neon grid floor
      var z = ZB - 0.07;
      for (var k = -16; k <= 16; k++) {
        var major = TH.gridMajor && k % 4 === 0, col = major ? TH.gridMajor : TH.grid;
        [seg(g, [k * 0.25, -4, z], [k * 0.25, 4, z], "orr-floor"), seg(g, [-4, k * 0.25, z], [4, k * 0.25, z], "orr-floor")].forEach(function (l) {
          l.attr("stroke", col); if (TH.gridOp) l.style("opacity", major ? 1 : TH.gridOp).style("stroke-width", major ? 1 : 0.6);
        });
      }
      if (TH.floorSun) g.append("circle").attr("cx", W * 0.5).attr("cy", H * 0.93).attr("r", H * 0.16).attr("fill", "#ff6f3c").attr("opacity", 0.18);
    }
  }
  /* ---------- search helpers: other names for countries and agencies ---------- */
  var ALIAS = { usa: "united states", us: "united states", america: "united states", american: "united states", "united states of america": "united states", nasa: "nasa", noaa: "noaa",
    russia: "russia", russian: "russia", roscosmos: "roscosmos", ussr: "russia", "soviet union": "russia",
    china: "china", chinese: "china", prc: "china", cnsa: "cnsa", japan: "japan", japanese: "japan", jaxa: "jaxa",
    india: "india", indian: "india", isro: "isro", korea: "south korea", "south korea": "south korea", korean: "south korea", kari: "kari",
    uae: "united arab emirates", emirates: "united arab emirates", emirati: "united arab emirates", dubai: "united arab emirates",
    europe: "europe", european: "europe", eu: "europe", esa: "esa", canada: "canada", canadian: "canada", csa: "csa" };
  // ESA's member countries: their spacecraft fly under ESA's name
  var ESA_MEMBERS = ["germany", "german", "france", "french", "italy", "italian", "uk", "united kingdom", "britain", "great britain", "england", "british",
    "spain", "spanish", "netherlands", "dutch", "belgium", "sweden", "swedish", "switzerland", "swiss", "norway", "norwegian", "austria", "denmark", "danish",
    "finland", "ireland", "irish", "portugal", "poland", "polish", "czechia", "czech republic", "romania", "greece", "luxembourg", "estonia", "hungary", "slovenia", "slovakia", "lithuania", "latvia"];

  /* ---------- planet faces ---------- */
  var LATIN = { Mercury: "MERCVRIVS", Venus: "VENVS", Earth: "TERRA", Mars: "MARS", Jupiter: "IVPPITER", Saturn: "SATVRNVS", Uranus: "VRANVS", Neptune: "NEPTVNVS", Pluto: "PLVTO" };
  // ring systems: [inner, outer, color, opacity] in planet radii; tilt of the ring plane on screen
  var RINGS = { Saturn: { bands: [[1.24, 1.52, "#8c7a52", 0.45], [1.53, 1.95, "#e8d7a4", 0.95], [2.03, 2.27, "#cdb987", 0.8]], tilt: -14, flat: 1 },
    Uranus: { bands: [[1.6, 1.64, "#bfe6ee", 0.9], [1.8, 1.9, "#d9f2f6", 0.95], [2.0, 2.03, "#bfe6ee", 0.7]], tilt: 82, flat: 0.38 },
    Neptune: { bands: [[1.55, 1.58, "#9fb6ff", 0.55], [2.1, 2.16, "#b7c7ff", 0.7]], tilt: -18, flat: 1 } };
  function bodyScale() { return Math.min(7, Math.pow(zoom, 0.8)); }
  function ringHalf(g, n, r, back) {
    var R0 = RINGS[n], k = Math.max(0.16, Math.sin(tilt * D2R)) * R0.flat, gg = g.append("g").attr("transform", "rotate(" + R0.tilt + ")");
    R0.bands.forEach(function (b) {
      var rx = r * (b[0] + b[1]) / 2, ry = rx * k, w = r * (b[1] - b[0]);
      // back half = the part of the ellipse above the planet's center (drawn before the planet)
      var arc = back ? "M" + (-rx) + ",0 A" + rx + "," + ry + " 0 0 1 " + rx + ",0" : "M" + rx + ",0 A" + rx + "," + ry + " 0 0 1 " + (-rx) + ",0";
      gg.append("path").attr("d", arc).attr("fill", "none").attr("stroke", b[2]).attr("stroke-opacity", b[3]).attr("stroke-width", Math.max(0.6, w * (0.55 + 0.45 * k)));
    });
  }
  var landCache = null;
  function body(g, n, r, sunDir, d) {
    var id = "pc-" + n + "-" + (++body.n), cp = svg.select("defs").append("clipPath").attr("id", id);
    cp.append("circle").attr("r", r);
    var f = g.append("g").attr("clip-path", "url(#" + id + ")");
    var base = TH.planet[n] || PL[n][0];
    f.append("circle").attr("r", r).attr("fill", base);
    if (n === "Earth") {
      var land = ctx.land && ctx.land();
      f.append("circle").attr("r", r).attr("fill", TH.ocean || "#1f5fa8");
      if (land) {
        // the longitude where it's noon right now sits on the edge facing the Sun
        var ut = d.getUTCHours() + d.getUTCMinutes() / 60, subsolar = -(ut - 12) * 15, center = subsolar - 90 * Math.cos(sunDir);
        var pr = d3.geoOrthographic().scale(r).translate([0, 0]).clipAngle(90).rotate([-center, -15]);
        f.append("path").attr("d", d3.geoPath(pr)(land)).attr("fill", TH.land || "#6fae54").attr("stroke", TH.landEdge || "none").attr("stroke-width", 0.4);
      }
      f.append("circle").attr("r", r * 0.98).attr("fill", "none").attr("stroke", "#bfe3ff").attr("stroke-opacity", 0.5).attr("stroke-width", Math.max(0.6, r * 0.08));
    } else if (n === "Jupiter" || n === "Saturn") {
      var bands = n === "Jupiter" ? [[-0.95, 0.18, "#b98b62"], [-0.55, 0.12, "#e9d8b6"], [-0.3, 0.16, "#a86f48"], [0.02, 0.1, "#f0e2c4"], [0.2, 0.16, "#b27a52"], [0.5, 0.14, "#e2caa0"], [0.75, 0.2, "#c49a70"]]
        : [[-0.8, 0.2, "#d8c28b"], [-0.35, 0.18, "#f1e2b4"], [0.05, 0.2, "#dcc690"], [0.45, 0.2, "#efe0b0"]];
      bands.forEach(function (b) { f.append("rect").attr("x", -r).attr("width", 2 * r).attr("y", b[0] * r).attr("height", b[1] * r).attr("fill", b[2]).attr("opacity", 0.9); });
      if (n === "Jupiter" && r > 5) f.append("ellipse").attr("cx", r * 0.3).attr("cy", r * 0.33).attr("rx", r * 0.2).attr("ry", r * 0.11).attr("fill", "#c8553a");
    } else if (n === "Mars") {
      [[0.25, -0.1, 0.45, "#9c3f22"], [-0.35, 0.3, 0.3, "#8f3a1f"], [-0.1, -0.45, 0.22, "#a64726"]].forEach(function (m) { f.append("ellipse").attr("cx", m[0] * r).attr("cy", m[1] * r).attr("rx", m[2] * r).attr("ry", m[2] * r * 0.6).attr("fill", m[3]).attr("opacity", 0.8); });
      f.append("ellipse").attr("cy", -r * 0.92).attr("rx", r * 0.45).attr("ry", r * 0.22).attr("fill", "#f6f1e8");
    } else if (n === "Venus") {
      [0.35, -0.1, -0.5].forEach(function (y, i) { f.append("path").attr("d", "M" + (-r) + "," + (y * r) + " Q0," + ((y + (i % 2 ? 0.25 : -0.25)) * r) + " " + r + "," + (y * r)).attr("fill", "none").attr("stroke", "#fff6d6").attr("stroke-opacity", 0.6).attr("stroke-width", Math.max(0.6, r * 0.12)); });
    } else if (n === "Mercury" || n === "Pluto") {
      [[0.3, -0.2, 0.16], [-0.35, 0.25, 0.12], [0.1, 0.45, 0.1], [-0.2, -0.45, 0.09]].forEach(function (c) { f.append("circle").attr("cx", c[0] * r).attr("cy", c[1] * r).attr("r", c[2] * r).attr("fill", "#000").attr("opacity", 0.18); });
      if (n === "Pluto") f.append("path").attr("d", "M" + (0.05 * r) + "," + (0.1 * r) + " c" + (-0.35 * r) + "," + (-0.45 * r) + " " + (-0.1 * r) + "," + (-0.6 * r) + " 0," + (-0.25 * r) + " c" + (0.1 * r) + "," + (-0.35 * r) + " " + (0.35 * r) + "," + (-0.2 * r) + " 0," + (0.25 * r) + "z").attr("fill", "#f3e9dc").attr("opacity", 0.85);
    } else if (n === "Neptune") {
      f.append("ellipse").attr("cx", -r * 0.25).attr("cy", r * 0.2).attr("rx", r * 0.22).attr("ry", r * 0.13).attr("fill", "#233f9e");
      f.append("rect").attr("x", -r).attr("width", 2 * r).attr("y", -r * 0.45).attr("height", r * 0.12).attr("fill", "#7ea0ff").attr("opacity", 0.5);
    } else if (n === "Uranus") {
      f.append("circle").attr("cx", -r * 0.1).attr("cy", -r * 0.1).attr("r", r * 0.55).attr("fill", "#c9f1f5").attr("opacity", 0.35);
    }
    // night side: a shadow on the half facing away from the Sun
    f.append("circle").attr("cx", -Math.cos(sunDir) * r * 0.62).attr("cy", -Math.sin(sunDir) * r * 0.62).attr("r", r * 1.05).attr("fill", "#000").attr("opacity", TH.night);
    g.append("circle").attr("r", r).attr("fill", "none").attr("class", "orr-body");
  }
  body.n = 0;
  function zodiacRing(d) {   // the twelve signs around the ring (ecliptic longitude, as seen from Earth: 0° = Aries)
    var sg = ["♈", "♉", "♊", "♋", "♌", "♍", "♎", "♏", "♐", "♑", "♒", "♓"], cols = TH.zodiac;
    for (var i = 0; i < 12; i++) {
      var a0 = i * 30 * D2R, a1 = (i + 1) * 30 * D2R, rO = RR1 + 0.075, rI = RR1 + 0.012;
      var outer = ringPts(rO, ZR, 12, a0, a1), inner = ringPts(rI, ZR, 12, a1, a0);
      gAll.append("path").attr("d", lineP(outer) + "L" + lineP(inner).slice(1) + "Z").attr("fill", cols[i % cols.length]).attr("fill-opacity", TH.zodOp).attr("stroke", TH.zodEdge).attr("stroke-width", 0.8);
      var mid = projW([Math.cos((i + 0.5) * 30 * D2R) * (rO + rI) / 2, Math.sin((i + 0.5) * 30 * D2R) * (rO + rI) / 2, ZR]);
      gAll.append("text").attr("x", mid[0]).attr("y", mid[1] + 4).attr("text-anchor", "middle").attr("class", "orr-zod").text(sg[i] + "︎");
    }
  }
  /* ---------- styles: sleek, and three that mix old star charts with modern color ---------- */
  var THEMES = {
    graphite: { label: "graphite", vars: { bg: "radial-gradient(ellipse at 50% 45%, #0e1209 0%, #050704 70%)", line: "#8a9280", post: "#6b7461", ring: "rgba(20,24,16,.78)", ringEdge: "#7b8470", tick: "#7b8470", text: "#e8eadf", sub: "#b9c2a6", halo: "#050704", orbit: "#c6f432", orbitOp: ".18", base: "#0c0f09", baseEdge: "#4a5240", craft: "#f4f4ef", accent: "#c6f432", font: "var(--mono)" },
      sun: "#fff3b0", night: 0.45, planet: {} },
    copernicus: { label: "copernicus", latin: true, vars: { bg: "radial-gradient(ellipse at 50% 40%, #16204a 0%, #0a0f24 55%, #05070f 100%)", line: "#f3e6c8", post: "#e9d9b4", ring: "rgba(12,18,44,.85)", ringEdge: "#f3e6c8", tick: "#f3e6c8", text: "#fff4dc", sub: "#ffc21a", halo: "#0a0f24", orbit: "#f3e6c8", orbitOp: ".55", base: "#0d1330", baseEdge: "#f3e6c8", craft: "#19d3a2", accent: "#ff5a36", font: "Georgia, 'Times New Roman', serif" },
      bands: ["#3a5bff", "#ff5a36", "#ffc21a", "#19d3a2"], bandOp: 0.13, zodiac: ["#ff5a36", "#3a5bff", "#ffc21a", "#19d3a2"], zodOp: 0.85, zodEdge: "#f3e6c8",
      sun: "#ffc21a", night: 0.5, ocean: "#2a4cff", land: "#19d3a2", landEdge: "#0a0f24", planet: { Mercury: "#b9b3c9", Venus: "#ffd27a", Mars: "#ff5a36", Jupiter: "#f0b27a", Saturn: "#ffd98a", Uranus: "#7ff0e0", Neptune: "#3a5bff", Pluto: "#d7c6ff" } },
    harmonia: { label: "harmonia", latin: true, vars: { bg: "radial-gradient(ellipse at 50% 42%, #fbf3e2 0%, #f1e4c8 60%, #e3d2ae 100%)", line: "#141414", post: "#141414", ring: "rgba(255,248,232,.92)", ringEdge: "#141414", tick: "#141414", text: "#141414", sub: "#d0341c", halo: "#fbf3e2", orbit: "#141414", orbitOp: ".7", base: "#efe2c4", baseEdge: "#141414", craft: "#1f4fff", accent: "#d0341c", font: "Georgia, 'Times New Roman', serif" },
      bands: ["#1f4fff", "#ff5b3a", "#ffc400", "#1fd1a5"], bandOp: 0.2, zodiac: ["#ff5b3a", "#1f4fff", "#ffc400", "#1fd1a5"], zodOp: 0.95, zodEdge: "#141414",
      sun: "#ffc400", night: 0.3, ocean: "#1f4fff", land: "#1fd1a5", landEdge: "#141414", planet: { Mercury: "#9b958a", Venus: "#ffb347", Mars: "#ff5b3a", Neptune: "#1f4fff", Uranus: "#4fd8d0" } },
    neon: { label: "neon", vars: { bg: "radial-gradient(ellipse at 50% 45%, #140a24 0%, #07060d 60%, #030306 100%)", line: "#9fb3c8", post: "#5e7086", ring: "rgba(12,10,24,.85)", ringEdge: "#9fb3c8", tick: "#9fb3c8", text: "#f5f7ff", sub: "#ff3d8b", halo: "#07060d", orbit: "#ffffff", orbitOp: ".85", base: "#0c0a18", baseEdge: "#5e7086", craft: "#00e5ff", accent: "#ff3d8b", font: "var(--mono)" },
      orbitCols: ["#ff3d8b", "#ff7a1a", "#ffd21a", "#00e58f", "#00c8ff", "#5b6bff", "#b44dff", "#ff4df0", "#8a8aa8"], zodiac: ["#1a1030", "#10152e"], zodOp: 0.95, zodEdge: "#ff3d8b",
      sun: "#ffe066", night: 0.55, ocean: "#1647ff", land: "#00e58f", planet: { Mars: "#ff5a36", Neptune: "#3b5bff" } },
    moebius: { label: "moebius (inspired)", vars: { bg: "linear-gradient(180deg, #f7d9b8 0%, #f3e7cf 38%, #cfe8dc 100%)", line: "#1b1b1b", post: "#1b1b1b", ring: "rgba(255,246,228,.9)", ringEdge: "#1b1b1b", tick: "#1b1b1b", text: "#1b1b1b", sub: "#b4452f", halo: "#fbf1e0", orbit: "#1b1b1b", orbitOp: ".75", base: "url(#hatch)", baseEdge: "#1b1b1b", craft: "#2f6f8f", accent: "#d9482b", font: "var(--mono)" },
      bands: ["#f2a65a", "#9fd8c0", "#c9b6e4", "#f6d38b"], bandOp: 0.55, zodiac: ["#f2a65a", "#9fd8c0", "#c9b6e4", "#f6d38b"], zodOp: 1, zodEdge: "#1b1b1b", hatch: "#1b1b1b", upper: true,
      sun: "#ffcf5a", night: 0.28, ocean: "#7cc3d6", land: "#e9b36b", landEdge: "#1b1b1b", planet: { Mercury: "#c8bba6", Venus: "#f6d38b", Mars: "#e0703f", Jupiter: "#e9b98a", Saturn: "#f2d7a0", Uranus: "#9fd8c0", Neptune: "#6f9fe0", Pluto: "#d9c7e8" } },
    spaceage: { label: "1960s space age", vars: { bg: "radial-gradient(ellipse at 50% 40%, #174f55 0%, #0e3438 60%, #082326 100%)", line: "#f4ecd8", post: "#e9c46a", ring: "rgba(12,44,48,.9)", ringEdge: "#f4ecd8", tick: "#f4ecd8", text: "#f4ecd8", sub: "#e9c46a", halo: "#0e3438", orbit: "#f4ecd8", orbitOp: ".7", base: "#0b2c2f", baseEdge: "#e76f51", craft: "#e76f51", accent: "#e76f51", font: "'Futura', 'Century Gothic', 'Trebuchet MS', sans-serif" },
      bands: ["#e76f51", "#e9c46a", "#2a9d8f"], bandOp: 0.16, zodiac: ["#e76f51", "#e9c46a", "#2a9d8f", "#f4ecd8"], zodOp: 0.9, zodEdge: "#0e3438", deco: "bursts", burst: "#e9c46a", upper: true,
      sun: "#f4a261", night: 0.4, ocean: "#2a9d8f", land: "#e9c46a", planet: { Mars: "#e76f51", Neptune: "#4fa3c7", Uranus: "#9ed8cf" } },
    cosmos: { label: "1960s space poster", vars: { bg: "linear-gradient(160deg, #efe3c8 0%, #e8d6b0 100%)", line: "#141414", post: "#c1272d", ring: "rgba(193,39,45,.95)", ringEdge: "#141414", tick: "#efe3c8", text: "#141414", sub: "#c1272d", halo: "#efe3c8", orbit: "#141414", orbitOp: ".85", base: "#141414", baseEdge: "#141414", craft: "#c1272d", accent: "#c1272d", font: "'Arial Black', 'Impact', sans-serif" },
      bands: ["#c1272d", "#efe3c8"], bandOp: 0.22, zodiac: ["#141414", "#c1272d"], zodOp: 1, zodEdge: "#efe3c8", deco: "rays", rays: "#c1272d", upper: true,
      sun: "#f2b705", night: 0.45, ocean: "#141414", land: "#c1272d", planet: { Mercury: "#8c8c8c", Venus: "#f2b705", Earth: "#141414", Mars: "#c1272d", Jupiter: "#d9a066", Saturn: "#f2b705", Uranus: "#9fb8b0", Neptune: "#34506b" } },
    nasa: { label: "1970s NASA", vars: { bg: "radial-gradient(ellipse at 50% 40%, #ffffff 0%, #ffffff 55%, #f1f1f1 100%)", line: "#111111", post: "#111111", ring: "rgba(255,255,255,.95)", ringEdge: "#fc3d21", tick: "#fc3d21", text: "#111111", sub: "#fc3d21", halo: "#ffffff", orbit: "#111111", orbitOp: ".6", base: "#f2f2f2", baseEdge: "#111111", craft: "#fc3d21", accent: "#fc3d21", font: "'Helvetica Neue', 'Helvetica', 'Arial', sans-serif" },
      zodiac: ["#ffffff"], zodOp: 1, zodEdge: "#fc3d21", deco: "floor", grid: "#c9c9c9", gridMajor: "#fc3d21", gridOp: 0.9,
      sun: "#fc3d21", night: 0.2, ocean: "#0b3d91", land: "#ffffff", landEdge: "#0b3d91", planet: { Mercury: "#b3b3b3", Venus: "#e0e0e0", Earth: "#0b3d91", Mars: "#fc3d21", Jupiter: "#d9d9d9", Saturn: "#cccccc", Uranus: "#bfbfbf", Neptune: "#0b3d91", Pluto: "#999999" } },
    nasanight: { label: "1970s NASA (dark)", vars: { bg: "radial-gradient(ellipse at 50% 40%, #17191d 0%, #0b0c0e 58%, #050506 100%)", line: "#ededed", post: "#e2e2e2", ring: "rgba(10,11,13,.94)", ringEdge: "#fc3d21", tick: "#fc3d21", text: "#f4f4f4", sub: "#fc3d21", halo: "#0b0c0e", orbit: "#ededed", orbitOp: ".5", base: "#121316", baseEdge: "#cfcfcf", craft: "#fc3d21", accent: "#fc3d21", font: "'Helvetica Neue', 'Helvetica', 'Arial', sans-serif" },
      zodiac: ["#0b0c0e"], zodOp: 1, zodEdge: "#fc3d21", deco: "floor", grid: "#2b2e34", gridMajor: "#a8291a", gridOp: 0.9,
      sun: "#fc3d21", night: 0.45, ocean: "#2f6fd6", land: "#e8e8e8", landEdge: "#2f6fd6", planet: { Mercury: "#9a9a9a", Venus: "#d6d6d6", Earth: "#2f6fd6", Mars: "#fc3d21", Jupiter: "#cfcfcf", Saturn: "#bdbdbd", Uranus: "#a9b8c9", Neptune: "#2f6fd6", Pluto: "#8a8a8a" } },
    synthwave: { label: "1980s synthwave", vars: { bg: "linear-gradient(180deg, #120024 0%, #2b0a4a 45%, #7a1d6e 72%, #ff6f3c 100%)", line: "#00f0ff", post: "#ff2fb4", ring: "rgba(18,0,36,.85)", ringEdge: "#00f0ff", tick: "#00f0ff", text: "#ffffff", sub: "#ffd23f", halo: "#1a0033", orbit: "#ff2fb4", orbitOp: ".9", base: "#12002a", baseEdge: "#ff2fb4", craft: "#ffd23f", accent: "#ffd23f", font: "var(--mono)" },
      zodiac: ["#1a0033", "#2b0a4a"], zodOp: 0.95, zodEdge: "#00f0ff", deco: "floor", grid: "#ff2fb4", floorSun: true, upper: true,
      sun: "#ffd23f", night: 0.5, ocean: "#3a0ca3", land: "#00f0ff", planet: { Mars: "#ff4f5e", Neptune: "#4361ee", Uranus: "#4cc9f0", Venus: "#ffb3c6" } },
    terminal: { label: "1990s terminal", vars: { bg: "radial-gradient(ellipse at 50% 45%, #041a08 0%, #010a03 75%)", line: "#33ff66", post: "#1fa344", ring: "rgba(2,20,6,.9)", ringEdge: "#33ff66", tick: "#33ff66", text: "#7dff9b", sub: "#33ff66", halo: "#010a03", orbit: "#33ff66", orbitOp: ".55", base: "#021206", baseEdge: "#1fa344", craft: "#b6ffc7", accent: "#d4ff3a", font: "'Consolas', 'Courier New', monospace" },
      zodiac: ["#021206"], zodOp: 1, zodEdge: "#33ff66", upper: true, mono: "#33ff66",
      sun: "#b6ffc7", night: 0.55, ocean: "#021206", land: "#33ff66", planet: { Mercury: "#33ff66", Venus: "#33ff66", Earth: "#021206", Mars: "#33ff66", Jupiter: "#33ff66", Saturn: "#33ff66", Uranus: "#33ff66", Neptune: "#33ff66", Pluto: "#33ff66" } },
  };
  var TH = THEMES.graphite, THEME_KEY = "archieOrreryStyle";
  function themePref() { try { return localStorage.getItem(THEME_KEY) || "graphite"; } catch (e) { return "graphite"; } }
  function setTheme(k) {
    try { localStorage.setItem(THEME_KEY, k); } catch (e) { }
    applyTheme(k);
  }
  function applyTheme(k0) {
    var k = effectiveTheme(THEMES[k0] ? k0 : "graphite");
    TH = THEMES[k] || THEMES.graphite;
    Object.keys(TH.vars).forEach(function (v) { el.style.setProperty("--o-" + v, TH.vars[v]); });
    el.dataset.theme = k;
    if ($("orr-style")) $("orr-style").value = THEMES[k0] ? k0 : "graphite";
    svg.select("#hatch line").attr("stroke", TH.hatch || "#000");
    draw();
  }
  /* ---------- flying to things ---------- */
  function fly(tx, ty, tz, tzoom, name) {
    var s0 = [fx, fy, fz, zoom], t0 = performance.now(); focusName = name;
    clearTimeout(flyT);
    (function step() {
      var k = Math.min(1, (performance.now() - t0) / 700), e = k < 0.5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2;
      fx = s0[0] + (tx - s0[0]) * e; fy = s0[1] + (ty - s0[1]) * e; fz = s0[2] + (tz - s0[2]) * e;
      zoom = Math.exp(Math.log(s0[3]) + (Math.log(tzoom) - Math.log(s0[3])) * e);
      draw();
      if (k < 1) flyT = setTimeout(function () { requestAnimationFrame(step); }, 16);
    })();
  }
  function goPlanet(n) {
    if (n === "Sun") { fly(0, 0, 0, 4, "Sun"); showPlanet("Sun"); return; }
    var q = squash(helio(n, now()));
    fly(q[0], q[1], Math.max(q[2], -0.05), n === "Earth" || n === "Venus" || n === "Mercury" || n === "Mars" ? 14 : 9, n);
    showPlanet(n);
  }
  function goCraft(c) {
    var bound = !/^(deep|sun|interstellar)$/.test(c[5]);
    if (bound) { var host = c[5] === "Moon" ? "Earth" : c[5]; goPlanet(host); setTimeout(function () { showCraft(c); }, 750); return; }
    var p = craftPos(c, now()); if (!p) { showCraft(c); return; }
    var rAU = Math.hypot(p[0], p[1], p[2]), q = squash(p);
    if (rAU > RMAX) { var k2 = 1.19 / Math.hypot(q[0], q[1]); q = [q[0] * k2, q[1] * k2, Math.max(-0.12, Math.min(0.32, q[2] * k2))]; }
    fly(q[0], q[1], q[2], rAU > RMAX ? 3 : Math.hypot(q[0], q[1]) < 0.35 ? 9 : 5, c[1]);
    showCraft(c);
  }
  function craftMenu() {
    var groups = [["Interstellar space", function (c) { return c[5] === "interstellar"; }], ["Deep space and on the way", function (c) { return c[5] === "deep"; }],
      ["Watching the Sun", function (c) { return c[5] === "sun"; }], ["Mercury", function (c) { return c[5] === "Mercury"; }], ["Mars", function (c) { return c[5] === "Mars"; }],
      ["Jupiter", function (c) { return c[5] === "Jupiter"; }], ["The Moon", function (c) { return c[5] === "Moon"; }], ["Sun–Earth L1 and L2 (1.5 million km out)", function (c) { return c[5] === "Earth"; }]];
    return groups.map(function (g) {
      var list = CRAFT.filter(g[1]); if (!list.length) return "";
      return '<div class="dd-h">' + g[0] + " · " + list.length + "</div>" + list.map(function (c) {
        var v = live && live.craft && live.craft[c[0]];
        return '<button data-n="' + esc(c[1]) + '"><b>' + esc(c[1]) + "</b><span>" + esc(c[2]) + " · " + esc(c[3]) + " · " + c[4] + (v ? " · live position" : "") + "</span></button>";
      }).join("");
    }).join("");
  }

  /* ---------- cards ---------- */
  function atBody(name) {
    if (name === "Sun") return CRAFT.filter(function (c) { return c[5] === "sun" || /^(SOHO|DSCOVR|Aditya-L1)$/.test(c[1]); });
    return CRAFT.filter(function (c) { return c[5] === name || (name === "Earth" && c[5] === "Moon"); });
  }
  function mini(name) {   // a little live diagram of what's circling the planet
    var moons = MOONS[name] || [], craft = atBody(name);
    return { moons: moons, craft: craft };
  }
  function runMini(name) {
    var box = $("orr-mini"); if (!box) return;
    var m = mini(name), w = 300, h = 150, s = d3.select(box).append("svg").attr("viewBox", "0 0 " + w + " " + h).attr("class", "orr-minisvg");
    var col = PL[name][0], items = [];
    s.append("circle").attr("cx", w / 2).attr("cy", h / 2).attr("r", 13).attr("fill", col).attr("stroke", "#0b0d09");
    if (name === "Saturn") s.append("ellipse").attr("cx", w / 2).attr("cy", h / 2).attr("rx", 26).attr("ry", 8).attr("class", "orr-ring");
    var orbiters = m.craft.filter(function (c) { return !/surface|asleep/.test(c[6]); }), surface = m.craft.filter(function (c) { return /surface|asleep/.test(c[6]); });
    orbiters.forEach(function (c, i) { items.push({ r: 22 + i * 6, per: 3 + i * 0.9, lab: c[1], kind: "c", ph: i * 1.7 }); });
    m.moons.forEach(function (mo, i) { items.push({ r: 22 + orbiters.length * 6 + 12 + i * 12, per: 6 + mo[1] * 1.4, lab: mo[0], kind: "m", ph: i * 2.3 }); });
    items.forEach(function (it) {
      s.append("ellipse").attr("cx", w / 2).attr("cy", h / 2).attr("rx", it.r * 1.9).attr("ry", it.r * 0.55).attr("class", "orr-miniorb");
      it.g = s.append("g"); it.g.append(it.kind === "c" ? "rect" : "circle").attr(it.kind === "c" ? "width" : "r", it.kind === "c" ? 4 : 2.6).attr("height", 4).attr("x", -2).attr("y", -2).attr("fill", it.kind === "c" ? "#f4f4ef" : "#c9c3b0");
      it.g.append("text").attr("x", 5).attr("y", -3).attr("class", "orr-minilab").text(it.lab);
    });
    if (surface.length) s.append("text").attr("x", w / 2).attr("y", h / 2 + 26).attr("text-anchor", "middle").attr("class", "orr-minilab").text("on the ground: " + surface.map(function (c) { return c[1].replace(" rover", ""); }).join(", "));
    var t0 = performance.now();
    (function tick() {
      if (!box.isConnected) return;
      var t = (performance.now() - t0) / 1000;
      items.forEach(function (it) { var a = t / it.per * 2 * Math.PI + it.ph; it.g.attr("transform", "translate(" + (w / 2 + Math.cos(a) * it.r * 1.9) + "," + (h / 2 + Math.sin(a) * it.r * 0.55) + ")"); });
      setTimeout(function () { requestAnimationFrame(tick); }, 60);
    })();
  }
  function kpText(kp) { return kp < 4 ? "quiet" : kp < 5 ? "unsettled" : kp < 6 ? "minor storm (G1)" : kp < 7 ? "moderate storm (G2)" : kp < 8 ? "strong storm (G3)" : kp < 9 ? "severe storm (G4)" : "extreme storm (G5)"; }
  function auroraText(kp) { return kp >= 8 ? "Auroras could reach the southern US." : kp >= 7 ? "Auroras possible across the northern US, including New York." : kp >= 6 ? "Auroras possible along the northern tier of US states." : kp >= 5 ? "Auroras possible in Canada and the far northern US." : "Auroras mostly stay near the Arctic."; }
  function showPlanet(name) {
    sel = name; draw();
    var d = now(), info = PL[name], E = helio("Earth", d);
    var P = name === "Sun" ? [0, 0, 0] : helio(name, d), fromSun = Math.hypot(P[0], P[1], P[2]), fromEarth = dist(P, E);
    var sky = name === "Sun" || name === "Earth" ? null : skyNote(name, d);
    var boxes = name === "Earth" ? [["From the Sun", fromSun.toFixed(3) + " AU", "var(--fg)"], ["Sunlight takes", lightTime(fromSun), "var(--fg)"], ["The Moon", moonPhase(d).split(",")[0], "#e8e8e3"]]
      : [["From Earth", fromEarth.toFixed(2) + " AU", "var(--fg)"], ["Light takes", lightTime(fromEarth), "var(--fg)"], [name === "Sun" ? "Activity" : "From the Sun", name === "Sun" ? (live && live.spacewx && live.spacewx.kp != null ? "Kp " + live.spacewx.kp.toFixed(1) : "—") : fromSun.toFixed(2) + " AU", info[0]]];
    var conditions = '<div class="rc-note" style="color:var(--fg)">' + [["Size", Math.round(info[2]).toLocaleString() + " km across (radius)"], ["A day", info[3]], ["A year", info[4]], ["Temperature", info[6]], ["Gravity", info[7] + "× Earth's"], [name === "Sun" ? "Orbiting it" : "Moons", info[5]]]
      .filter(function (r) { return r[1] && r[1] !== "—"; }).map(function (r) { return "<b>" + r[0] + ":</b> " + esc(r[1]); }).join("<br>") + "</div>";
    var livebox = "";
    if (name === "Sun" || name === "Earth") {
      var w = live && live.spacewx;
      livebox = w ? '<div class="rc-note" style="color:var(--fg)">' + (w.kp != null ? "<b>Geomagnetic activity:</b> Kp " + w.kp.toFixed(1) + ", " + kpText(w.kp) + ". " + auroraText(w.kp) + "<br>" : "") +
        (w.wind_kms ? "<b>Solar wind:</b> " + Math.round(w.wind_kms) + " km/s" + (w.wind_kms > 600 ? " (fast: a stream or storm is hitting)" : w.wind_kms > 450 ? " (a bit fast)" : " (normal)") + "<br>" : "") +
        (w.flare ? "<b>Biggest flare in 24 h:</b> " + esc(w.flare) + (/^X/.test(w.flare) ? " (major: can cause radio blackouts)" : /^M/.test(w.flare) ? " (medium)" : " (small)") + ", " + w.flares_24h + " flares in all" : "<b>Flares:</b> none reported in 24 h") +
        '</div><div class="rc-note">From NOAA\'s Space Weather Prediction Center, checked every 30 minutes.</div>' : '<div class="rc-note">No space weather yet (Archie checks NOAA every 30 minutes while online).</div>';
    }
    if (name === "Mars") {
      var m = live && live.marswx;
      livebox = m ? '<div class="rc-note" style="color:var(--fg)"><b>Latest from Curiosity</b> (sol ' + esc(m.sol) + ", " + esc(m.terrestrial_date) + "): high " + esc(m.max_temp) + " °C, low " + esc(m.min_temp) + " °C" + (m.pressure ? ", air pressure " + esc(m.pressure) + " Pa (under 1% of Earth's)" : "") + (m.atmo_opacity ? ", sky " + esc(String(m.atmo_opacity).toLowerCase()) : "") + (m.season ? ", " + esc(m.season) : "") + '.</div><div class="rc-note">Reported by the rover\'s weather station in Gale Crater; reports lag a few days.</div>' : '<div class="rc-note">No Curiosity weather report reached Archie yet.</div>';
    }
    var list = atBody(name);
    var craftHTML = list.length ? list.map(function (c) { return '<div class="srow hl orr-cr" data-n="' + esc(c[1]) + '"><span style="color:var(--fg);font-family:var(--body);font-size:11px;white-space:normal">' + esc(c[1]) + '</span><span>' + esc(c[2]) + "</span></div>"; }).join("") : '<div class="rc-note">No spacecraft there right now.</div>';
    rich({
      hash: "planet=" + name.toLowerCase(), color: info[0], title: name.toUpperCase(), badge: name === "Sun" ? "STAR" : name === "Pluto" ? "DWARF PLANET" : "PLANET", badgeColor: info[0],
      sub: name === "Earth" ? "You are here · the Moon is a " + moonPhase(d) : sky ? "In the sky: " + sky[0] : name === "Sun" ? "The star at the center" : "",
      boxes: boxes,
      sections: [["About", '<div class="rc-note" style="color:var(--fg)">' + esc(info[8]) + "</div>"],
        [livebox ? (name === "Mars" ? "Weather on Mars" : "Space weather right now") : null, livebox],
        name === "Mars" ? ["Where the rovers are", marsSection()] : [null, ""],
        ["Facts", conditions],
        [(name === "Earth" ? "Spacecraft near Earth and at the Moon" : name === "Sun" ? "Spacecraft watching it" : "Spacecraft there") + " · " + list.length, (name !== "Sun" && (list.length || MOONS[name]) ? '<div id="orr-mini" class="orr-mini"></div>' : "") + craftHTML],
        [null, '<div class="rc-note">' + (name === "Earth" ? "The thousands of satellites close to Earth are on the globe: switch them on under Space in the layers. " : "") + "Positions are for " + (dt ? d.toDateString() : "right now") + ".</div>"]],
      actions: name === "Earth" ? [["the Moon close-up", function () { showMoon(); }], ["open the globe", function () { ctx.setView("globe"); }]] : [],
      explain: { title: name, names: [name === "Sun" ? "Sun" : name + (name === "Pluto" ? "" : " (planet)")], kind: "planet" },
      after: function () {
        runMini(name);
        if (name === "Mars") drawMars();
        document.querySelectorAll(".orr-cr").forEach(function (r) { r.onclick = function () { var c = CRAFT.find(function (x) { return x[1] === r.dataset.n; }); if (c) showCraft(c); }; });
      }
    });
  }
  function showCraft(c) {
    sel = c[1]; draw();
    var d = now(), p = craftPos(c, d), E = helio("Earth", d);
    var fromSun = p ? Math.hypot(p[0], p[1], p[2]) : null, fromEarth = p ? dist(p, E) : null, v = live && live.craft && live.craft[c[0]];
    var speed = v && v.vx != null ? Math.hypot(v.vx, v.vy, v.vz) * AU_KM / 86400 : null;
    var bound = !/^(deep|sun|interstellar)$/.test(c[5]), ev = earthView(c, p, d), pg = pingState();
    var acts = bound && EL[c[5] === "Moon" ? "Earth" : c[5]] ? [["show " + (c[5] === "Moon" ? "Earth" : c[5]), function () { showPlanet(c[5] === "Moon" ? "Earth" : c[5]); }]] : [];
    if (/^(-31|-32|-98)$/.test(c[0]) && v) acts.unshift([pg ? "ping on its way (" + pg.name + ")" : "send it a ping", function () { if (!pingState()) { sendPing(c); showCraft(c); } }]);
    if (FLY[c[0]]) acts.push(["its path since launch", function () { setTrails(true); }]);
    rich({
      hash: "craft=" + ctx.slug(c[1]), color: "#f4f4ef", title: c[1].toUpperCase(), badge: c[2].toUpperCase(), badgeColor: "#d9a441",
      sub: c[3] + " · launched " + c[4] + " · " + c[6],
      boxes: bound ? [["Where", esc(where(c)), "#34d399"], ["From Earth", fromEarth != null ? (fromEarth < 0.05 ? Math.round(fromEarth * AU_KM).toLocaleString() + " km" : fromEarth.toFixed(2) + " AU") : "—", "var(--fg)"], ["Signal takes", fromEarth != null ? lightTime(fromEarth) : "—", "var(--fg)"]]
        : [["From Earth", fromEarth != null ? fromEarth.toFixed(fromEarth < 10 ? 2 : 1) + " AU" : "—", "var(--fg)"], ["Signal takes", fromEarth != null ? lightTime(fromEarth) : "—", "#d9a441"], ["Speed", speed ? Math.round(speed).toLocaleString() + " km/s" : "—", "var(--fg)"]],
      sections: [["About", '<div class="rc-note" style="color:var(--fg)">' + esc(c[7]) + "</div>"],
        [null, '<dl class="facts own"><dt>Country</dt><dd>' + esc(c[2]) + "</dd><dt>Agency</dt><dd>" + esc(c[3]) + "</dd><dt>Launched</dt><dd>" + c[4] + "</dd><dt>Status</dt><dd>" + esc(c[6]) + "</dd>" + (fromSun != null && !bound ? "<dt>From the Sun</dt><dd>" + esc(fmtAU(fromSun)) + "</dd>" : "") + "</dl>"],
        ev, FLY[c[0]] ? ["Its journey", '<div class="rc-note" style="color:var(--fg)">' + FLY[c[0]].map(function (e) { return "<b>" + new Date(e[0] + "T12:00:00Z").toLocaleDateString([], { month: "short", day: "numeric", year: "numeric" }) + "</b> · " + esc(e[1]); }).join("<br>") + "</div>"] : null,
        /^(-31|-32|-98)$/.test(c[0]) ? ["Send a ping", '<div class="rc-note">' + (pg ? "Your ping to " + esc(pg.name) + " is on its way; the live panel counts it down." : "A radio signal to " + esc(c[1]) + " takes " + (fromEarth != null ? lightTime(fromEarth) : "hours") + " at the speed of light, and the answer just as long to come back. Send a pretend ping and Archie draws it crossing the solar system in real time and tells you when it would arrive.") + "</div>"] : null,
        [null, '<div class="rc-note">' + (v ? "Position from NASA JPL Horizons, updated " + ctx.ago(Math.round((Date.now() / 1000 - v.at) / 60)) + "." : bound ? "Shown with the body it's at; its exact orbit isn't in NASA's public trajectory service." : "Waiting for NASA JPL's position (Archie checks twice a day while online).") + "</div>"]].filter(Boolean),
      actions: acts,
      explain: { title: c[1], names: [c[1].replace(/ \(.*\)$/, "") + (/rover|orbiter|telescope/i.test(c[1]) ? "" : " (spacecraft)")], kind: "spacecraft" }
    });
  }

  /* ---------- the archive menu (archive.js) and the mission planner's path ---------- */
  var EX = null, PLAN = null, planEnd = null, SPEED = 10;
  function archive() {
    if (!EX && window.ArchieArchive) EX = window.ArchieArchive({ $: $, esc: esc, api: api, rich: rich, ago: ctx.ago, helio: helio, now: now, live: function () { return live; },
      setPlan: function (pl) { PLAN = pl; draw(); },
      goTo: function (when, flyDays) {   // jump the clock to the launch, and optionally run it to arrival in about 12 seconds
        dt = (when.getTime() - Date.now()) / 86400000; fx = fy = fz = 0; focusName = null; zoom = 1;
        if (flyDays) { planEnd = dt + flyDays; SPEED = Math.max(10, flyDays / 12); playing = true; lastT = performance.now(); var pb = $("orr-play"); if (pb) pb.textContent = "❚❚"; loop(); }
        else { playing = false; draw(); }
      } });
    return EX;
  }
  function localOpen(k) {
    if (k === "grandtour") { grandTour(); return true; }
    if (k === "launches") { openLaunches(); return true; }
    if (k === "moon") { showMoon(); return true; }
    return false;
  }
  function drawPlan(d) {   // the transfer ellipse from Earth's orbit to the target's, and where the probe would be today
    var P = PLAN, out = P.r2 > P.r1, a = (P.r1 + P.r2) / 2, e = Math.abs(P.r2 - P.r1) / (P.r1 + P.r2), g = gAll.append("g").style("pointer-events", "none");
    var at = function (nu) { var r = a * (1 - e * e) / (1 + e * Math.cos(nu)), th = P.L0 + (out ? nu : nu - Math.PI); return [r * Math.cos(th), r * Math.sin(th), 0]; };
    var pts = []; for (var i = 0; i <= 90; i++) pts.push(at(out ? Math.PI * i / 90 : Math.PI + Math.PI * i / 90));
    g.append("path").attr("d", path(pts)).attr("class", "orr-plan");
    var A = proj(pts[0]), B = proj(pts[90]);
    g.append("circle").attr("cx", A[0]).attr("cy", A[1]).attr("r", 4).attr("class", "orr-plan-end");
    g.append("circle").attr("cx", B[0]).attr("cy", B[1]).attr("r", 4).attr("class", "orr-plan-end");
    g.append("text").attr("x", A[0] + 7).attr("y", A[1] + 14).attr("class", "orr-plan-lab").text("LAUNCH " + P.launch.toLocaleDateString([], { month: "short", day: "numeric", year: "numeric" }).toUpperCase());
    g.append("text").attr("x", B[0] + 7).attr("y", B[1] + 14).attr("class", "orr-plan-lab").text("ARRIVE AT " + P.target.toUpperCase());
    var tau = (d.getTime() - P.launch.getTime()) / 86400000;
    if (tau >= 0 && tau <= P.days) {
      var M = (out ? 0 : Math.PI) + Math.PI * tau / P.days, E = M;
      for (var k = 0; k < 12; k++) E = E - (E - e * Math.sin(E) - M) / (1 - e * Math.cos(E));
      var nu = 2 * Math.atan2(Math.sqrt(1 + e) * Math.sin(E / 2), Math.sqrt(1 - e) * Math.cos(E / 2)), s = proj(at(nu));
      g.append("path").attr("d", "M" + s[0] + "," + (s[1] - 6) + " l6,6 l-6,6 l-6,-6Z").attr("class", "orr-plan-craft");
      g.append("text").attr("x", s[0] + 9).attr("y", s[1] - 6).attr("class", "orr-plan-lab").text("YOUR PROBE · DAY " + Math.round(tau));
    }
  }

  /* ---------- the Milky Way (galaxy.js) ---------- */
  var GAL = null, inGal = false;
  function enterGalaxy(anim) {
    if (!window.ArchieGalaxy) return;
    if (!GAL) { GAL = window.ArchieGalaxy(ctx); GAL.make(el, exitGalaxy); }
    inGal = true; playing = false; var pb = $("orr-play"); if (pb) pb.textContent = "▶";
    el.classList.add("galmode"); GAL.show(anim);
  }
  function exitGalaxy() {
    if (!GAL) return;
    GAL.hide(); inGal = false; el.classList.remove("galmode");
    fx = fy = fz = 0; focusName = null; zoom = 0.7; size(); draw(); tickLive();
  }

  /* ================= round 1: trails and the Grand Tour, launches, Pale Blue Dot, the ping, the Moon, the Mars rovers, night style ================= */
  // finished missions, drawn only with their paths: [JPL id, name, country, agency, launched, color]
  var HIST = [["-23", "Pioneer 10", "United States", "NASA", 1972], ["-24", "Pioneer 11", "United States", "NASA", 1973], ["-82", "Cassini", "United States / Europe / Italy", "NASA, ESA and ASI", 1997], ["-77", "Galileo", "United States", "NASA", 1989]];
  var TRAIL_COL = { "-31": "#ffd166", "-32": "#4cc9f0", "-98": "#f15bb5", "-23": "#b8c0a8", "-24": "#9aa38a", "-82": "#ff9f43", "-77": "#a3e635" };
  var SHORT = { "-31": "V1", "-32": "V2", "-98": "NH", "-23": "P10", "-24": "P11", "-82": "Cassini", "-77": "Galileo" };
  var FLY = {
    "-31": [["1977-09-05", "launch"], ["1979-03-05", "Jupiter"], ["1980-11-12", "Saturn and Titan"], ["1990-02-14", "the Pale Blue Dot"], ["2012-08-25", "enters interstellar space"]],
    "-32": [["1977-08-20", "launch"], ["1979-07-09", "Jupiter"], ["1981-08-25", "Saturn"], ["1986-01-24", "Uranus"], ["1989-08-25", "Neptune"], ["2018-11-05", "enters interstellar space"]],
    "-98": [["2006-01-19", "launch"], ["2007-02-28", "Jupiter"], ["2015-07-14", "Pluto"], ["2019-01-01", "Arrokoth"]],
    "-23": [["1972-03-03", "launch"], ["1973-12-03", "Jupiter, the first visit"], ["2003-01-23", "last signal"]],
    "-24": [["1973-04-06", "launch"], ["1974-12-02", "Jupiter"], ["1979-09-01", "Saturn, the first visit"], ["1995-09-30", "last contact"]],
    "-82": [["1997-10-15", "launch"], ["1998-04-26", "Venus"], ["1999-06-24", "Venus again"], ["1999-08-18", "Earth"], ["2000-12-30", "Jupiter"], ["2004-07-01", "arrives at Saturn"], ["2017-09-15", "dives into Saturn"]],
    "-77": [["1989-10-18", "launch"], ["1990-02-10", "Venus"], ["1990-12-08", "Earth"], ["1992-12-08", "Earth again"], ["1995-12-07", "arrives at Jupiter"], ["2003-09-21", "dives into Jupiter"]]
  };
  var TRAILS = null, trailsOn = (function () { try { return localStorage.getItem("archieOrrTrails") === "1"; } catch (e) { return false; } })(), tourOn = false, capT = null;
  var trailsAt = 0;
  function loadTrails(cb) {   // asks again (at most once a minute) while the paths haven't downloaded yet
    var have = TRAILS && Object.keys(TRAILS).length;
    if (have || (TRAILS && Date.now() - trailsAt < 60000)) { if (cb) cb(); return; }
    trailsAt = Date.now();
    api("/api/solar_trails").then(function (d) { TRAILS = d || {}; if (cb) cb(); if (active) draw(); }).catch(function () { TRAILS = TRAILS || {}; if (cb) cb(); });
  }
  setInterval(function () { if (trailsOn && active && !(TRAILS && Object.keys(TRAILS).length)) loadTrails(); }, 60000);
  if (trailsOn) setTimeout(function () { loadTrails(); }, 1500);
  function trailPos(id, d) {   // where a probe was on a date, from its weekly points (null before launch or after its last point)
    var T = TRAILS && TRAILS[id]; if (!T || !T.pts || !T.pts.length) return null;
    var P = T.pts, t = d.getTime() / 1000;
    if (t < P[0][0] - 86400 || t > P[P.length - 1][0] + 8 * 86400) return null;
    if (t <= P[0][0]) return P[0].slice(1);
    var lo = 0, hi = P.length - 1;
    if (t >= P[hi][0]) return P[hi].slice(1);
    while (hi - lo > 1) { var mid = (lo + hi) >> 1; if (P[mid][0] <= t) lo = mid; else hi = mid; }
    var k = (t - P[lo][0]) / (P[hi][0] - P[lo][0]);
    return [P[lo][1] + (P[hi][1] - P[lo][1]) * k, P[lo][2] + (P[hi][2] - P[lo][2]) * k, P[lo][3] + (P[hi][3] - P[lo][3]) * k];
  }
  function hasTrail(id) { return !!(TRAILS && TRAILS[id] && TRAILS[id].pts && TRAILS[id].pts.length); }
  function trailCovers(id, d) { if (!hasTrail(id)) return false; var P = TRAILS[id].pts; return d.getTime() / 1000 <= P[P.length - 1][0] + 8 * 86400; }
  function beforeLaunch(id, d) { return hasTrail(id) && d.getTime() / 1000 < TRAILS[id].pts[0][0] - 86400; }
  function modelQ(p) {   // a position (AU) -> model units, with anything past the squeezed scale parked on the rim
    var rAU = Math.hypot(p[0], p[1], p[2]), q = squash(p);
    if (rAU > RMAX) { var k2 = 1.19 / Math.hypot(q[0], q[1]); q = [q[0] * k2, q[1] * k2, Math.max(-0.12, Math.min(0.32, q[2] * k2))]; }
    return q;
  }
  function drawTrails(d) {
    var g = gAll.append("g").attr("class", "orr-trails"), t = d.getTime() / 1000;
    Object.keys(TRAILS).forEach(function (id) {
      var P = TRAILS[id].pts; if (!P || !P.length || t < P[0][0]) return;
      var pts = [], step = Math.max(1, Math.floor(P.length / 700));
      for (var i = 0; i < P.length && P[i][0] <= t; i += step) pts.push(projW(modelQ(P[i].slice(1))));
      var now0 = trailPos(id, d); if (now0) pts.push(projW(modelQ(now0)));
      if (pts.length < 2) return;
      g.append("path").attr("d", lineP(pts)).attr("class", "orr-trail").style("stroke", TRAIL_COL[id] || "#ffffff");
      (FLY[id] || []).forEach(function (ev) {
        var ed = new Date(ev[0] + "T12:00:00Z"); if (ed.getTime() / 1000 > t || ev[1] === "launch") return;
        var p = trailPos(id, ed); if (!p) return;
        var s = projW(modelQ(p)), mg = g.append("g").attr("class", "orr-fly");
        mg.append("circle").attr("cx", s[0]).attr("cy", s[1]).attr("r", 3.2).style("stroke", TRAIL_COL[id]);
        if (tourOn ? /^-3[12]$/.test(id) : (zoom > 1.6 || sel === TRAILS[id].name)) mg.append("text").attr("x", s[0] + 5).attr("y", s[1] + 10).attr("class", "orr-flylab").text(SHORT[id] + " · " + ev[1].replace(/, the first visit/, "") + " " + ev[0].slice(0, 4));
        mg.append("title").text(TRAILS[id].name + ": " + ev[1] + ", " + new Date(ev[0] + "T12:00:00Z").toLocaleDateString([], { month: "long", day: "numeric", year: "numeric" }));
      });
    });
    HIST.forEach(function (h) {   // the finished missions, where they were on this date
      var p = trailPos(h[0], d); if (!p) return;
      var s = projW(modelQ(p)), gg = g.append("g").attr("class", "orr-sc hist").attr("transform", "translate(" + s[0] + "," + s[1] + ")");
      gg.append("rect").attr("x", -3).attr("y", -3).attr("width", 6).attr("height", 6).attr("transform", "rotate(45)").style("fill", TRAIL_COL[h[0]]);
      gg.append("text").attr("x", 6).attr("y", -5).attr("class", "orr-sclab").text(h[1]);
    });
  }
  function setTrails(on) {
    trailsOn = on; try { localStorage.setItem("archieOrrTrails", on ? "1" : "0"); } catch (e) { }
    var b = $("orr-trl"); if (b) b.setAttribute("aria-pressed", on ? "true" : "false");
    if (on) loadTrails(); else draw();
  }
  function caption(text, ms) {
    var c = $("orr-cap"); if (!c) return;
    c.textContent = text; c.hidden = !text; clearTimeout(capT);
    if (text && ms) capT = setTimeout(function () { c.hidden = true; }, ms);
  }
  function tourCaption(d) {
    var t = d.getTime(), best = null;
    ["-31", "-32"].forEach(function (id) { FLY[id].forEach(function (ev) { var et = new Date(ev[0] + "T12:00:00Z").getTime(); if (et <= t && t - et < 330 * 86400000 && (!best || et > best[0])) best = [et, id, ev]; }); });
    if (!best) { caption(d.getFullYear() < 1979 ? "1977 · BOTH VOYAGERS ARE ON THEIR WAY · THE PLANETS LINE UP ONCE EVERY 175 YEARS" : ""); return; }
    var nm = best[1] === "-31" ? "VOYAGER 1" : "VOYAGER 2", ev = best[2][1];
    caption(new Date(best[0]).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" }).toUpperCase() + " · " + nm + (ev === "launch" ? " LAUNCHES" : ev === "the Pale Blue Dot" ? " LOOKS BACK AT EARTH" : " FLIES PAST " + ev.toUpperCase()));
  }
  function grandTour() {
    loadTrails(function () {
      if (!hasTrail("-31")) { caption("THE VOYAGERS' PATHS HAVEN'T DOWNLOADED YET (NASA JPL, ONCE A WEEK WHILE ONLINE). TRY AGAIN IN A FEW MINUTES.", 8000); return; }
      setTrails(true); tourOn = true; fx = fy = fz = 0; focusName = null; zoom = 1;
      var start = new Date("1977-08-15T12:00:00Z"), end = new Date("1990-02-14T12:00:00Z");
      dt = (start.getTime() - Date.now()) / 86400000; planEnd = (end.getTime() - Date.now()) / 86400000;
      SPEED = (planEnd - dt) / 60; playing = true; lastT = performance.now(); var pb = $("orr-play"); if (pb) pb.textContent = "❚❚"; loop();
    });
  }
  function tourDone() {
    tourOn = false;
    caption("FEB 14, 1990 · 6 BILLION KM OUT, VOYAGER 1 TURNS AROUND AND PHOTOGRAPHS EARTH: THE PALE BLUE DOT", 14000);
    var c = CRAFT.find(function (x) { return x[0] === "-31"; }); if (c) showCraft(c);
  }

  /* ---------- launches ---------- */
  function tMinus(t) {
    var s = Math.round(t - Date.now() / 1000), neg = s < 0; s = Math.abs(s);
    var dd = Math.floor(s / 86400), hh = Math.floor(s % 86400 / 3600), mm = Math.floor(s % 3600 / 60), ss = s % 60, p2 = function (n) { return (n < 10 ? "0" : "") + n; };
    return (neg ? "T+" : "T−") + (dd ? dd + "d " : "") + p2(hh) + ":" + p2(mm) + ":" + p2(ss);
  }
  function nextLaunch() { var L = (live && live.launches) || [], n = Date.now() / 1000 - 1800; return L.filter(function (l) { return l.t > n; }).sort(function (a, b) { return a.t - b.t; })[0]; }
  function openLaunches() {
    var L = ((live && live.launches) || []).filter(function (l) { return l.t > Date.now() / 1000 - 3 * 3600; }).sort(function (a, b) { return a.t - b.t; });
    var row = function (l) {
      var go = /^go/i.test(l.abbrev) || /go for launch/i.test(l.status);
      return '<details class="arc-dd"><summary><span class="orr-tm" data-t="' + l.t + '">' + tMinus(l.t) + "</span> " + esc(l.name) + "</summary><div class=\"arc-body\">" +
        '<div class="rc-note" style="color:var(--fg)">' + [l.provider ? "<b>" + esc(l.provider) + "</b>" + (l.ptype ? " (" + esc(l.ptype.toLowerCase()) + ")" : "") : "", l.rocket ? "Rocket: " + esc(l.rocket) : "", l.mission && l.mission !== l.name ? "Mission: " + esc(l.mission) + (l.mtype ? " · " + esc(l.mtype) : "") : (l.mtype ? esc(l.mtype) : ""), l.orbit ? "Going to: " + esc(l.orbit) : "",
          "From: " + esc([l.pad, l.where].filter(Boolean).join(", ")), "When: " + new Date(l.t * 1000).toLocaleString([], { weekday: "short", month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }) + (l.precision && !/second|minute/i.test(l.precision) ? " (" + esc(l.precision.toLowerCase()) + " precision)" : ""),
          "Status: " + (go ? "<b style=\"color:#9fd36a\">" + esc(l.status) + "</b>" : esc(l.status || "to be confirmed"))].filter(Boolean).join("<br>") + "</div>" +
        (l.about ? '<div class="rc-note">' + esc(l.about) + "</div>" : "") + "</div></details>";
    };
    rich({ hash: "archive=launches", color: "#ffb86b", title: "ROCKET LAUNCHES", badge: "WORLDWIDE", badgeColor: "#ffb86b",
      sub: L.length ? "The next " + L.length + " launches anywhere on Earth, counting down live" : "no launch schedule yet",
      boxes: L.length ? [["Next", '<span class="orr-tm" data-t="' + L[0].t + '">' + tMinus(L[0].t) + "</span>", "#ffb86b"], ["Rocket", esc((L[0].rocket || L[0].name.split("|")[0]).slice(0, 26)), "var(--fg)"], ["This week", String(L.filter(function (l) { return l.t < Date.now() / 1000 + 7 * 86400; }).length), "var(--fg)"]] : [],
      sections: [[null, L.length ? L.map(row).join("") : '<div class="rc-note">Archie checks The Space Devs\' Launch Library every few hours while online.</div>'],
        [null, '<div class="rc-note">Times move a lot: weather, rocket problems and busy launch ranges push launches back, sometimes by minutes, often by days. "Go for launch" means the final checks passed. Schedule from The Space Devs\' Launch Library 2 (a free, community-run database). New missions to the Moon, Mars or deep space join the spacecraft list in a later update, once NASA tracks their path.</div>']],
      after: function () {
        var tick = function () { var els = document.querySelectorAll(".orr-tm"); if (!els.length) return; els.forEach(function (e) { e.textContent = tMinus(+e.dataset.t); }); setTimeout(tick, 1000); };
        tick();
      } });
  }

  /* ---------- the Pale Blue Dot, and how Earth looks from far away ---------- */
  function earthView(c, p, d) {
    if (!p || !/^(-31|-32|-98)$/.test(c[0])) return null;
    var E = helio("Earth", d), au = dist(p, E), km = au * AU_KM, rad = 2 * Math.atan(6371 / km), arcsec = rad * 206265;
    var toS = [-p[0], -p[1], -p[2]], toE = [E[0] - p[0], E[1] - p[1], E[2] - p[2]];
    var ang = Math.acos((toS[0] * toE[0] + toS[1] * toE[1] + toS[2] * toE[2]) / (Math.hypot.apply(null, toS) * Math.hypot.apply(null, toE))) / D2R;
    var coinKm = 0.0243 / rad / 1000, px = 0.12 * 40.5 / au;
    var html = '<div class="rc-note" style="color:var(--fg)">From ' + esc(c[1]) + ", all of Earth is " + (arcsec < 1 ? arcsec.toFixed(2) : arcsec.toFixed(1)) + " arcseconds across: about the size of a quarter (the coin) seen from " + Math.round(coinKm).toLocaleString() + " km away. " +
      "It sits just " + ang.toFixed(1) + "° from the Sun, lost in its glare." +
      (c[0] === "-31" ? " In Voyager's camera it would now fill " + px.toFixed(2) + " of one pixel (it was 0.12 in 1990)." : "") + "</div>";
    if (c[0] === "-31") html += '<div class="rc-note">On February 14, 1990, about 6 billion km (40 AU) out, Voyager 1 turned its camera back toward home at Carl Sagan\'s urging and took 60 pictures: a portrait of the solar system. In one, Earth is a speck 0.12 pixels across, caught in a ray of scattered sunlight. Sagan called it the Pale Blue Dot. Thirty-four minutes later the cameras were switched off for good to save power. ' +
      '<a href="https://photojournal.jpl.nasa.gov/catalog/PIA00452" target="_blank" rel="noopener">see the photo at NASA ↗</a></div>';
    return [c[0] === "-31" ? "The Pale Blue Dot" : "How Earth looks from here", html];
  }

  /* ---------- a ping to the probes: the real wait for a radio signal ---------- */
  var PING_KEY = "archiePing";
  function pingState() { try { return JSON.parse(localStorage.getItem(PING_KEY) || "null"); } catch (e) { return null; } }
  function pingSave(s) { try { if (s) localStorage.setItem(PING_KEY, JSON.stringify(s)); else localStorage.removeItem(PING_KEY); } catch (e) { } }
  function sendPing(c) {
    var p = craftPos(c, new Date()); if (!p) return;
    var owlt = dist(p, helio("Earth", new Date())) * LIGHT_S;
    pingSave({ id: c[0], name: c[1], t0: Date.now(), owlt: owlt, arrived: false });
    if (ctx.note) ctx.note('<span class="k" style="color:#ffd166">● PING SENT</span><span>Your signal is on its way to ' + esc(c[1]) + ". It reaches it in " + dur(owlt) + "; an answer would be back " + dur(owlt * 2) + " from now.</span>", 9000);
    draw(); tickLive();
  }
  function dur(s) { s = Math.round(s); var h = Math.floor(s / 3600), m = Math.floor(s % 3600 / 60); return h ? h + " h " + m + " min" : m ? m + " min " + (s % 60) + " s" : s + " s"; }
  function pingCheck() {
    var s = pingState(); if (!s) return;
    var el2 = (Date.now() - s.t0) / 1000;
    if (!s.arrived && el2 >= s.owlt) { s.arrived = true; pingSave(s); if (ctx.note) ctx.note('<span class="k" style="color:#ffd166">● PING ARRIVED</span><span>Your ping just reached ' + esc(s.name) + ", " + dur(s.owlt) + " after you sent it. If it answered now, the reply would land " + new Date(s.t0 + s.owlt * 2000).toLocaleString([], { weekday: "short", hour: "numeric", minute: "2-digit" }) + ".</span>", 15000); }
    else if (el2 >= s.owlt * 2) { pingSave(null); if (ctx.note) ctx.note('<span class="k" style="color:#ffd166">● ROUND TRIP</span><span>A reply to your ping would be arriving from ' + esc(s.name) + " right now: " + dur(s.owlt * 2) + " there and back at the speed of light.</span>", 15000); }
  }
  setInterval(pingCheck, 5000);
  function drawPing() {
    var s = pingState(); if (!s || dt) return;
    var c = CRAFT.find(function (x) { return x[0] === s.id; }); if (!c) return;
    var d = new Date(), p = craftPos(c, d); if (!p) return;
    var A = squash(helio("Earth", d)), B = modelQ(p), f = (Date.now() - s.t0) / 1000 / s.owlt, k = f <= 1 ? f : 2 - f;
    if (k < 0 || k > 1) return;
    var Pa = projW(A), Pb = projW(B), q = projW([A[0] + (B[0] - A[0]) * k, A[1] + (B[1] - A[1]) * k, A[2] + (B[2] - A[2]) * k]);
    var g = gAll.append("g").style("pointer-events", "none");
    g.append("line").attr("x1", Pa[0]).attr("y1", Pa[1]).attr("x2", Pb[0]).attr("y2", Pb[1]).attr("class", "orr-pingline");
    g.append("circle").attr("cx", q[0]).attr("cy", q[1]).attr("r", 4).attr("class", "orr-ping");
    g.append("text").attr("x", q[0] + 7).attr("y", q[1] - 6).attr("class", "orr-sclab").text(f <= 1 ? "PING → " + s.name.toUpperCase() : "REPLY → EARTH");
  }
  function pingRow() {
    var s = pingState(); if (!s) return "";
    var el2 = (Date.now() - s.t0) / 1000, out = el2 < s.owlt;
    return '<button data-ping="1"><b>Ping ' + (out ? "→ " + esc(s.name) : "reply → Earth") + '</b><span>' + (out ? "arrives in " + dur(s.owlt - el2) : "back in " + dur(s.owlt * 2 - el2)) + " · " + Math.round(100 * Math.min(1, el2 / (s.owlt * 2))) + "% of the round trip</span></button>";
  }

  /* ---------- the Moon ---------- */
  function moonEl(d) {   // the Moon's angle from the Sun, seen from Earth (0 new, 90 first quarter, 180 full, 270 last quarter), plus its distance
    var n = jd(d) - 2451545, r = function (x) { return (x % 360 + 360) % 360 * D2R; };
    var Lm = 218.316 + 13.176396 * n, Mm = r(134.963 + 13.064993 * n), F = r(93.272 + 13.22935 * n), D = r(297.85 + 12.190749 * n), Ms = r(357.529 + 0.98560028 * n);
    var lon = Lm + 6.289 * Math.sin(Mm) + 1.274 * Math.sin(2 * D - Mm) + 0.658 * Math.sin(2 * D) + 0.214 * Math.sin(2 * Mm) - 0.186 * Math.sin(Ms) - 0.114 * Math.sin(2 * F)
      + 0.059 * Math.sin(2 * D - 2 * Mm) + 0.057 * Math.sin(2 * D - Ms - Mm) + 0.053 * Math.sin(2 * D + Mm) + 0.046 * Math.sin(2 * D - Ms) + 0.041 * Math.sin(Mm - Ms) - 0.035 * Math.sin(D) - 0.031 * Math.sin(Mm + Ms);
    var sun = 280.466 + 0.98564736 * n + 1.915 * Math.sin(Ms) + 0.02 * Math.sin(2 * Ms);
    var km = 385001 - 20905 * Math.cos(Mm) - 3699 * Math.cos(2 * D - Mm) - 2956 * Math.cos(2 * D) - 570 * Math.cos(2 * Mm);
    return [((lon - sun) % 360 + 360) % 360, km];
  }
  function moonPhases(from, n) {   // the next n main phases, found by stepping and narrowing down
    var out = [], names = ["New moon", "First quarter", "Full moon", "Last quarter"], t = from.getTime(), step = 6 * 3600000;
    var prev = moonEl(new Date(t))[0];
    for (var i = 0; i < 4 * 31 && out.length < n; i++) {
      var t2 = t + step, cur = moonEl(new Date(t2))[0];
      for (var q = 0; q < 4; q++) {
        var target = q * 90, a = ((prev - target) % 360 + 540) % 360 - 180, b = ((cur - target) % 360 + 540) % 360 - 180;
        if (a < 0 && b >= 0) {
          var lo = t, hi = t2;
          for (var k = 0; k < 20; k++) { var m = (lo + hi) / 2, v = ((moonEl(new Date(m))[0] - target) % 360 + 540) % 360 - 180; if (v < 0) lo = m; else hi = m; }
          out.push([names[q], new Date((lo + hi) / 2), q]);
        }
      }
      prev = cur; t = t2;
    }
    return out;
  }
  // [name, lat, lon (east +), country, year, note]
  var MOONSITES = [
    ["Luna 2", 29.1, 0, "USSR", 1959, "the first thing from Earth to reach the Moon (a planned crash)"], ["Luna 9", 7.08, -64.37, "USSR", 1966, "the first soft landing and first photos from the surface"],
    ["Surveyor 1", -2.47, -43.34, "US", 1966, "America's first soft landing"], ["Surveyor 3", -3.02, -23.42, "US", 1967, "Apollo 12 astronauts later walked over and took parts of it home"],
    ["Surveyor 7", -40.98, -11.51, "US", 1968, "landed beside the bright young crater Tycho"],
    ["Apollo 11", 0.674, 23.473, "US", 1969, "Neil Armstrong and Buzz Aldrin, the first people on the Moon (July 20, 1969)"], ["Apollo 12", -3.012, -23.422, "US", 1969, "Pete Conrad and Alan Bean, a pinpoint landing next to Surveyor 3"],
    ["Apollo 14", -3.645, -17.471, "US", 1971, "Alan Shepard and Edgar Mitchell; Shepard hit two golf balls"], ["Apollo 15", 26.132, 3.634, "US", 1971, "David Scott and James Irwin, the first lunar rover drive"],
    ["Apollo 16", -8.973, 15.5, "US", 1972, "John Young and Charlie Duke, in the highlands"], ["Apollo 17", 20.191, 30.772, "US", 1972, "Gene Cernan and Harrison Schmitt, the last people on the Moon (December 1972)"],
    ["Luna 16", -0.51, 56.36, "USSR", 1970, "the first robot to bring Moon rock home"], ["Lunokhod 1 (Luna 17)", 38.24, -35, "USSR", 1970, "the first rover on another world"],
    ["Lunokhod 2 (Luna 21)", 25.85, 30.45, "USSR", 1973, "drove 39 km, a record until 2014"], ["Luna 24", 12.71, 62.21, "USSR", 1976, "the last Soviet sample return"],
    ["Chang'e 3", 44.12, -19.51, "China", 2013, "China's first landing, with the Yutu rover"], ["Chang'e 4", -45.44, 177.59, "China", 2019, "the first landing on the far side, with the Yutu-2 rover"],
    ["Chang'e 5", 43.06, -51.92, "China", 2020, "brought 1.7 kg of young volcanic rock home"], ["Chang'e 6", -41.64, -153.99, "China", 2024, "the first samples from the far side"],
    ["Chandrayaan-3", -69.37, 32.32, "India", 2023, "the first landing near the south pole region"], ["SLIM", -13.32, 25.25, "Japan", 2024, "a pinpoint landing (within 100 m of its target), though it tipped onto its nose"],
    ["Odysseus (IM-1)", -80.13, 1.44, "US (private)", 2024, "the first private lander to touch down, near the south pole"], ["Blue Ghost 1", 18.56, 61.81, "US (private)", 2025, "a private landing in Mare Crisium that worked for a full lunar day"]
  ];
  var MARIA = [["Oceanus Procellarum", 18.4, -57.4, 22], ["Mare Imbrium", 32.8, -15.6, 16], ["Mare Serenitatis", 28, 17.5, 9], ["Mare Tranquillitatis", 8.5, 31.4, 11], ["Mare Crisium", 17, 59.1, 7],
    ["Mare Fecunditatis", -7.8, 51.3, 9], ["Mare Nectaris", -15.2, 35.5, 5], ["Mare Nubium", -21.3, -16.6, 10], ["Mare Humorum", -24.4, -38.6, 5.5], ["Mare Frigoris", 56, 1.4, 7], ["Mare Vaporum", 13.3, 3.6, 4],
    ["Mare Moscoviense", 27.3, 147.9, 4.5], ["Mare Orientale", -19.4, -92.8, 5], ["South Pole–Aitken basin", -53, -169, 20]];
  var SITECOL = { US: "#4cc9f0", USSR: "#ff6b5e", China: "#ffd166", India: "#9fd36a", Japan: "#f4f4ef", "US (private)": "#b39ddb" };
  function showMoon() {
    sel = "Earth"; draw();
    var d = now(), me = moonEl(d), ph = moonPhases(d, 8);
    rich({ hash: "planet=moon", color: "#e8e8e3", title: "THE MOON", badge: "EARTH'S MOON", badgeColor: "#e8e8e3",
      sub: "Tonight: " + moonPhase(d),
      boxes: [["From Earth", Math.round(me[1]).toLocaleString() + " km", "var(--fg)"], ["Light takes", (me[1] / 299792).toFixed(2) + " s", "var(--fg)"], ["Next full moon", (ph.find(function (x) { return x[2] === 2; }) || [0, null])[1] ? ph.find(function (x) { return x[2] === 2; })[1].toLocaleDateString([], { month: "short", day: "numeric" }) : "—", "#e8e8e3"]],
      sections: [["Phases coming up", '<div class="orr-phases">' + ph.map(function (x) { return '<div><i class="mph q' + x[2] + '"></i><b>' + x[0] + "</b><span>" + x[1].toLocaleDateString([], { weekday: "short", month: "short", day: "numeric" }) + ", around " + x[1].toLocaleTimeString([], { hour: "numeric" }) + "</span></div>"; }).join("") + '</div><div class="rc-note">Worked out on your PC from the Moon\'s orbit; times are good to within about an hour.</div>'],
        ["Where people and robots have landed", '<div id="orr-moonmap" class="orr-moonmap"></div><div class="orr-sitekey">' + Object.keys(SITECOL).map(function (k) { return '<span><i style="background:' + SITECOL[k] + '"></i>' + esc(k === "USSR" ? "Soviet Union" : k === "US" ? "United States (NASA)" : k) + "</span>"; }).join("") + "</div>" +
          '<div class="rc-note">The side facing us (left) and the far side (right), which never faces Earth. Dark patches are the maria, old lava plains. Point at a dot for what landed there. <b>Artemis III</b>, NASA\'s first crewed landing since 1972, is aimed at the region around the south pole, where ice hides in craters that never see sunlight.</div>' +
          '<details class="arc-dd"><summary>Every landing · ' + MOONSITES.length + "</summary><div class=\"arc-body\">" + MOONSITES.slice().sort(function (a, b) { return a[4] - b[4]; }).map(function (s) { return '<div class="arc-row"><b><i class="orr-dotk" style="background:' + SITECOL[s[3]] + '"></i>' + esc(s[0]) + " · " + s[4] + "</b><span>" + esc(s[5]) + "</span></div>"; }).join("") + "</div></details>"],
        ["Spacecraft at the Moon", atBody("Moon").map(function (c) { return '<div class="srow hl orr-cr" data-n="' + esc(c[1]) + '"><span style="color:var(--fg);font-family:var(--body);font-size:11px;white-space:normal">' + esc(c[1]) + "</span><span>" + esc(c[2]) + "</span></div>"; }).join("") || '<div class="rc-note">None tracked right now.</div>'],
        ["Facts", '<div class="rc-note" style="color:var(--fg)"><b>Size:</b> 1,737 km radius, about a quarter of Earth\'s<br><b>A day:</b> 29.5 Earth days, sunrise to sunrise; the same side always faces us<br><b>Gravity:</b> 0.17× Earth\'s<br><b>Temperature:</b> about 120 °C by day, −130 °C at night, and −240 °C in polar craters<br><b>Distance:</b> 356,000 to 407,000 km over each month; it drifts 3.8 cm farther from Earth every year</div>']],
      actions: [["show Earth", function () { showPlanet("Earth"); }]],
      explain: { title: "The Moon", names: ["Moon"], kind: "planet" },
      after: function () {
        drawMoonMap();
        document.querySelectorAll(".orr-cr").forEach(function (r) { r.onclick = function () { var c = CRAFT.find(function (x) { return x[1] === r.dataset.n; }); if (c) showCraft(c); }; });
      } });
  }
  function drawMoonMap() {
    var box = $("orr-moonmap"); if (!box) return;
    var w = 300, h = 150, s = d3.select(box).append("svg").attr("viewBox", "0 0 " + w + " " + h).attr("class", "orr-moonsvg");
    s.attr("viewBox", "0 0 " + w + " 162");
    [[0, 75, "NEAR SIDE"], [180, 225, "FAR SIDE"]].forEach(function (side) {
      var pr = d3.geoOrthographic().scale(64).translate([side[1], 76]).rotate([-side[0], 0]).clipAngle(90), path = d3.geoPath(pr);
      s.append("path").attr("d", path({ type: "Sphere" })).attr("class", "orr-moonball");
      s.append("path").attr("d", path(d3.geoGraticule().step([30, 30])())).attr("class", "orr-moongrat");
      MARIA.forEach(function (m) { s.append("path").attr("d", path(d3.geoCircle().center([m[2], m[1]]).radius(m[3])())).attr("class", "orr-mare" + (/Aitken/.test(m[0]) ? " basin" : "")).append("title").text(m[0]); });
      MOONSITES.forEach(function (st) {
        var xy = pr([st[2], st[1]]); if (!xy || d3.geoDistance([st[2], st[1]], [side[0], 0]) > Math.PI / 2) return;
        var g = s.append("g").attr("class", "orr-site");
        g.append("circle").attr("cx", xy[0]).attr("cy", xy[1]).attr("r", 2.4).attr("fill", SITECOL[st[3]]);
        g.append("title").text(st[0] + " (" + st[4] + ", " + (st[3] === "USSR" ? "Soviet Union" : st[3]) + "): " + st[5]);
      });
      var sp = pr([0, -88]); if (sp) s.append("circle").attr("cx", sp[0]).attr("cy", sp[1]).attr("r", 5).attr("class", "orr-artemis").append("title").text("Artemis III candidate landing regions, around the south pole");
      s.append("text").attr("x", side[1]).attr("y", 158).attr("text-anchor", "middle").attr("class", "orr-minilab").text(side[2]);
    });
  }

  /* ---------- Mars: where the rovers are ---------- */
  // [name, lat, lon (east +), year, country, still working]
  var MARSSITES = [["Curiosity", -4.59, 137.44, 2012, "US", 1], ["Perseverance", 18.44, 77.45, 2021, "US", 1], ["Zhurong", 25.07, 109.93, 2021, "China", 0],
    ["Viking 1", 22.27, -47.95, 1976, "US", 0], ["Viking 2", 47.64, 134.29, 1976, "US", 0], ["Pathfinder", 19.13, -33.22, 1997, "US", 0], ["Spirit", -14.57, 175.47, 2004, "US", 0],
    ["Opportunity", -1.95, -5.53, 2004, "US", 0], ["Phoenix", 68.22, -125.75, 2008, "US", 0], ["InSight", 4.5, 135.62, 2018, "US", 0]];
  var MARSFEAT = [["Olympus Mons", 18.65, -133.8], ["Valles Marineris", -14, -59], ["Hellas", -42.4, 70.5], ["Tharsis", 0, -112], ["Utopia", 46.7, 117.5], ["Argyre", -49.7, -43.4]];
  var LANDED = { curiosity: Date.UTC(2012, 7, 6, 5, 17), perseverance: Date.UTC(2021, 1, 18, 20, 55) };
  function marsSection() {
    return '<div id="orr-mars" class="orr-mars"><div class="rc-note">Loading the rovers\' routes…</div></div>';
  }
  function drawMars() {
    var box = $("orr-mars"); if (!box) return;
    api("/api/rovers").then(function (R) {
      R = R || {}; box.innerHTML = "";
      var w = 300, h = 150, s = d3.select(box).append("svg").attr("viewBox", "0 0 " + w + " " + h).attr("class", "orr-marssvg");
      var X = function (lon) { return (lon + 180) / 360 * w; }, Y = function (lat) { return (90 - lat) / 180 * h; };
      s.append("rect").attr("width", w).attr("height", h).attr("class", "orr-marsbg");
      for (var lo = -180; lo <= 180; lo += 30) s.append("line").attr("x1", X(lo)).attr("x2", X(lo)).attr("y1", 0).attr("y2", h).attr("class", "orr-marsgrid");
      for (var la = -60; la <= 60; la += 30) s.append("line").attr("y1", Y(la)).attr("y2", Y(la)).attr("x1", 0).attr("x2", w).attr("class", "orr-marsgrid" + (la === 0 ? " eq" : ""));
      MARSFEAT.forEach(function (f) { s.append("text").attr("x", X(f[2])).attr("y", Y(f[1])).attr("text-anchor", "middle").attr("class", "orr-marsfeat").text(f[0]); });
      MARSSITES.forEach(function (m) {
        var g = s.append("g");
        g.append("circle").attr("cx", X(m[2])).attr("cy", Y(m[1])).attr("r", m[5] ? 3.6 : 2.3).attr("class", "orr-marssite" + (m[5] ? " live" : m[4] === "China" ? " cn" : ""));
        if (m[5] || m[4] === "China") { var rt = X(m[2]) > w - 70; g.append("text").attr("x", X(m[2]) + (rt ? -5 : 5)).attr("y", Y(m[1]) + 3).attr("text-anchor", rt ? "end" : "start").attr("class", "orr-minilab").text(m[0]); }
        g.append("title").text(m[0] + " · landed " + m[3] + (m[5] ? " · still driving" : m[4] === "China" ? " · China · asleep since 2022" : " · mission over"));
      });
      var routes = [["curiosity", "Curiosity", "Gale Crater, climbing Mount Sharp"], ["perseverance", "Perseverance", "Jezero Crater, an old lake bed, and up its rim"]].map(function (r) {
        var D = R[r[0]]; if (!D || !D.pts || D.pts.length < 2) return '<div class="rc-note">' + r[1] + "'s route hasn't downloaded yet (NASA's rover maps, once a day while online).</div>";
        var P = D.pts, last = P[P.length - 1], when = new Date(LANDED[r[0]] + last[0] * 88775244);
        return '<div class="orr-rv"><b>' + r[1] + "</b> <span>" + esc(r[2]) + "</span><div id=\"orr-rv-" + r[0] + '"></div><div class="rc-note">' + (last[3] ? last[3].toFixed(1) + " km driven · " : "") + "latest stop on sol " + last[0].toLocaleString() + " (a Mars day; about " + when.toLocaleDateString([], { month: "short", day: "numeric", year: "numeric" }) + ") · " + P.length.toLocaleString() + " stops</div></div>";
      }).join("");
      box.insertAdjacentHTML("beforeend", '<div class="orr-sitekey"><span><i style="background:#c6f432"></i>still driving</span><span><i style="background:#ffd166"></i>China</span><span><i style="background:#9a8f80"></i>missions that ended</span></div>' + routes +
        '<div class="rc-note">Routes from NASA\'s rover location maps (the same data as its "Where is the rover?" pages), checked daily. Map: longitude across, latitude up; not to scale near the poles.</div>');
      ["curiosity", "perseverance"].forEach(function (k) {
        var D = R[k], el2 = $("orr-rv-" + k); if (!D || !el2) return;
        var P = D.pts, lat0 = P[0][2], km = 3389.5 * D2R, cosl = Math.cos(lat0 * D2R);
        var xy = P.map(function (p) { return [(p[1] - P[0][1]) * km * cosl, (p[2] - lat0) * km]; });
        var ex = d3.extent(xy, function (q) { return q[0]; }), ey = d3.extent(xy, function (q) { return q[1]; }), span = Math.max(ex[1] - ex[0], ey[1] - ey[0], 0.5);
        var W2 = 300, H2 = 150, sc = Math.min((W2 - 30) / (ex[1] - ex[0] || 1), (H2 - 30) / (ey[1] - ey[0] || 1));
        var ox = (W2 - (ex[1] - ex[0]) * sc) / 2 - ex[0] * sc, oy = (H2 + (ey[1] - ey[0]) * sc) / 2 + ey[0] * sc;
        var pt = function (q) { return [ox + q[0] * sc, oy - q[1] * sc]; };
        var s2 = d3.select(el2).append("svg").attr("viewBox", "0 0 " + W2 + " " + H2).attr("class", "orr-marssvg");
        s2.append("rect").attr("width", W2).attr("height", H2).attr("class", "orr-marsbg");
        s2.append("path").attr("d", lineP(xy.map(pt))).attr("class", "orr-rvpath");
        var a = pt(xy[0]), b = pt(xy[xy.length - 1]);
        s2.append("circle").attr("cx", a[0]).attr("cy", a[1]).attr("r", 3).attr("class", "orr-rvstart");
        s2.append("text").attr("x", a[0] + 5).attr("y", a[1] + 11).attr("class", "orr-minilab").text("landed");
        s2.append("circle").attr("cx", b[0]).attr("cy", b[1]).attr("r", 4).attr("class", "orr-rvnow");
        s2.append("text").attr("x", b[0] + 6).attr("y", b[1] - 5).attr("class", "orr-minilab").text("now");
        var bar = Math.pow(10, Math.floor(Math.log10(span / 3))), bl = bar * sc;
        s2.append("line").attr("x1", 10).attr("x2", 10 + bl).attr("y1", H2 - 10).attr("y2", H2 - 10).attr("class", "orr-rvbar");
        s2.append("text").attr("x", 14 + bl).attr("y", H2 - 7).attr("class", "orr-minilab").text(bar >= 1 ? bar + " km" : bar * 1000 + " m");
        s2.append("text").attr("x", W2 - 8).attr("y", 12).attr("text-anchor", "end").attr("class", "orr-minilab").text("north ↑");
      });
    }).catch(function () { box.innerHTML = '<div class="rc-note">Couldn\'t reach Archie for the rover routes.</div>'; });
  }

  /* ---------- the dark style after sunset ---------- */
  var NIGHT_KEY = "archieOrrNight", DARK_OF = { nasa: "nasanight", harmonia: "copernicus", moebius: "graphite", cosmos: "spaceage" };
  var TZ_LL = { "America/New_York": [40.71, -74.0], "America/Detroit": [42.33, -83.05], "America/Toronto": [43.65, -79.38], "America/Chicago": [41.88, -87.63], "America/Denver": [39.74, -104.99],
    "America/Phoenix": [33.45, -112.07], "America/Los_Angeles": [34.05, -118.24], "America/Anchorage": [61.22, -149.9], "Pacific/Honolulu": [21.31, -157.86], "Europe/London": [51.51, -0.13],
    "Europe/Paris": [48.86, 2.35], "Europe/Berlin": [52.52, 13.4], "Asia/Tokyo": [35.68, 139.69], "Australia/Sydney": [-33.87, 151.21] };
  function nightOn() { try { return localStorage.getItem(NIGHT_KEY) === "1"; } catch (e) { return false; } }
  function isNight(d) {   // sunset to sunrise where this PC's clock says it is (its time zone's main city)
    var tz = ""; try { tz = Intl.DateTimeFormat().resolvedOptions().timeZone; } catch (e) { }
    var ll = TZ_LL[tz] || [40, -d.getTimezoneOffset() / 4], lat = ll[0] * D2R;
    var n = Math.floor((Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()) - Date.UTC(d.getUTCFullYear(), 0, 0)) / 86400000);
    var dec = 23.44 * D2R * Math.sin(2 * Math.PI / 365 * (284 + n)), B = 2 * Math.PI / 365 * (n - 81), eot = 9.87 * Math.sin(2 * B) - 7.53 * Math.cos(B) - 1.5 * Math.sin(B);
    var cosH = (Math.sin(-0.833 * D2R) - Math.sin(lat) * Math.sin(dec)) / (Math.cos(lat) * Math.cos(dec));
    if (cosH > 1) return true; if (cosH < -1) return false;
    var H = Math.acos(cosH) / D2R / 15, noon = 12 - ll[1] / 15 - eot / 60, u = d.getUTCHours() + d.getUTCMinutes() / 60;
    var rise = ((noon - H) % 24 + 24) % 24, set = ((noon + H) % 24 + 24) % 24;
    return rise < set ? (u < rise || u >= set) : (u >= set && u < rise);
  }
  function effectiveTheme(k) { return nightOn() && DARK_OF[k] && isNight(new Date()) ? DARK_OF[k] : k; }
  setInterval(function () { if (!el || !active) return; var want = effectiveTheme(themePref()); if ((el.dataset.theme || "") !== want) applyTheme(themePref()); }, 60000);

  /* ---------- public ---------- */
  function load() { return api("/api/solar").then(function (d) { live = d; live.got = Date.now(); if (active) { draw(); tickLive(); } }).catch(function () { }); }
  // the live panel: distances that count up every second, the Sun's weather, Mars weather
  function tickLive() {
    var box = $("orr-live"); if (!box || !active || inGal) return;
    var d = new Date(), E = helio("Earth", d), rows = [];
    ["-31", "-32", "-98"].forEach(function (id) {
      var c = CRAFT.find(function (x) { return x[0] === id; }), v = live && live.craft && live.craft[id];
      if (!c || !v) return;
      var p = craftPos(c, d), km = dist(p, E) * AU_KM;
      rows.push('<button data-c="' + esc(c[1]) + '"><b>' + esc(c[1]) + "</b><span>" + Math.round(km).toLocaleString() + " km from Earth · signal " + lightTime(dist(p, E)) + "</span></button>");
    });
    var w = live && live.spacewx;
    rows.push('<button data-p="Sun"><b>Sun</b><span>' + (w ? (w.kp != null ? "Kp " + w.kp.toFixed(1) + " (" + kpText(w.kp) + ")" : "") + (w.wind_kms ? " · wind " + Math.round(w.wind_kms) + " km/s" : "") + (w.flare ? " · top flare " + esc(w.flare) : "") : "waiting for NOAA space weather") + "</span></button>");
    var m = live && live.marswx, M = helio("Mars", d);
    rows.push('<button data-p="Mars"><b>Mars</b><span>' + (m ? "Curiosity, sol " + esc(m.sol) + ": " + esc(m.max_temp) + " / " + esc(m.min_temp) + " °C · " : "") + "light takes " + lightTime(dist(M, E)) + "</span></button>");
    rows.push('<button data-p="Moon"><b>Moon</b><span>' + moonPhase(d) + "</span></button>");
    var nl = nextLaunch();
    if (nl) rows.push('<button data-launch="1"><b>Next launch · <span class="orr-tm2">' + tMinus(nl.t) + "</span></b><span>" + esc(nl.name.length > 46 ? nl.name.slice(0, 45) + "…" : nl.name) + "</span></button>");
    var pr = pingRow(); if (pr) rows.push(pr);
    var n = live && live.craft ? Object.keys(live.craft).length : 0, newest = n ? Math.max.apply(null, Object.keys(live.craft).map(function (k) { return live.craft[k].at || 0; })) : 0;
    box.innerHTML = '<div class="h"><i class="dot"></i>LIVE</div>' + rows.join("") + '<div class="orr-live-f">' + (n ? n + " spacecraft tracked by NASA JPL · updated " + ctx.ago(Math.round((Date.now() / 1000 - newest) / 60)) : "spacecraft positions: waiting for NASA JPL (first check takes a minute)") + "</div>";
    box.querySelectorAll("button").forEach(function (b) { b.onclick = function () {
      if (b.dataset.launch) { openLaunches(); return; }
      if (b.dataset.ping) { var s0 = pingState(), c0 = s0 && CRAFT.find(function (x) { return x[0] === s0.id; }); if (c0) goCraft(c0); return; }
      if (b.dataset.c) { var c = CRAFT.find(function (x) { return x[1] === b.dataset.c; }); if (c) showCraft(c); } else if (b.dataset.p === "Moon") showMoon(); else showPlanet(b.dataset.p); }; });
  }
  setInterval(function () { if (active && !document.hidden) tickLive(); }, 1000);
  setInterval(function () { if (active && !document.hidden) load(); }, 180000);
  return {
    show: function () { if (!el) build(); active = true; el.hidden = false; size(); draw(); tickLive(); if (inGal && GAL) GAL.show(false); if (!live || Date.now() - (live.got || 0) > 120000) load(); },
    hide: function () { active = false; playing = false; if (GAL) GAL.hide(); if (el) { el.hidden = true; var b = $("orr-play"); if (b) b.textContent = "▶"; } },
    select: function (k, v) {
      if (k === "archive") { if (inGal) exitGalaxy(); if (localOpen(v)) return; var ex = archive(); if (ex) ex.open(v); return; }
      if (k === "merger") { if (!inGal) enterGalaxy(false); GAL.merger(); return; }
      if (k === "galaxy") { if (!inGal) enterGalaxy(true); else GAL.zoomOut(); return; }
      if (k === "system") { if (!inGal) enterGalaxy(false); GAL.select(v); return; }
      if (inGal) exitGalaxy();
      if (k === "planet") { if (v === "moon") { showMoon(); return; } var n = PLANETS.concat(["Sun"]).find(function (x) { return x.toLowerCase() === v; }); if (n) showPlanet(n); }
      if (k === "craft") { var c = CRAFT.find(function (x) { return ctx.slug(x[1]) === v || x[1].toLowerCase().indexOf(v.replace(/-/g, " ")) >= 0; }); if (c) showCraft(c); }
    }
  };
};
