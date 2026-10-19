/* Archie World: the Milky Way view, reached by scrolling out of the solar system.
   The galaxy's shape (bar, four main arms, the Orion Spur we live on) is a drawn model; the star systems are real:
   every confirmed planet from NASA's Exoplanet Archive (Archie downloads it weekly), placed by its real direction and distance.
   It only redraws while you move it, so it costs nothing sitting still. */
window.ArchieGalaxy = function (ctx) {
  "use strict";
  var $ = ctx.$, esc = ctx.esc, api = ctx.api, rich = ctx.rich;
  var D2R = Math.PI / 180, R0 = 26670, LY_KM = 9.4607e12, YEAR_S = 31557600;
  var SUN = [-R0, 0, 55], CENTER = [0, 0, 0];

  /* ---------- famous systems: shown before the full catalog downloads, and their notes are added to it after ---------- */
  // [host, RA (hours), Dec (deg), light-years, spectral type, star temp K, star radius (Suns), about, planets]
  // planet: [name, orbit days, orbit AU, radius (Earths), mass (Earths), temperature K (no air), discovered, method]
  var FAMOUS = [
    ["Proxima Cen", 14.4953, -62.679, 4.24, "M5.5 V", 3042, 0.154, "The nearest star to the Sun, a small red dwarf circling the Alpha Centauri pair. Its planet b sits in the zone where water could be liquid, but the star throws strong flares.",
      [["Proxima Cen d", 5.12, 0.029, null, 0.26, 360, 2022, "Radial Velocity"], ["Proxima Cen b", 11.19, 0.0485, null, 1.07, 234, 2016, "Radial Velocity"]]],
    ["Barnard's star", 17.963, 4.69, 5.96, "M4 V", 3195, 0.19, "A small, very old red star that moves across our sky faster than any other. Four small rocky planets were confirmed around it in 2024 and 2025, all too hot for water.",
      [["Barnard b", 3.154, 0.0229, null, 0.30, 400, 2024, "Radial Velocity"], ["Barnard c", 4.124, 0.0274, null, 0.34, 370, 2025, "Radial Velocity"], ["Barnard d", 2.34, 0.0188, null, 0.26, 440, 2025, "Radial Velocity"], ["Barnard e", 6.739, 0.0381, null, 0.19, 310, 2025, "Radial Velocity"]]],
    ["eps Eri", 3.549, -9.458, 10.5, "K2 V", 5084, 0.74, "A young, Sun-like orange star with dust belts like our asteroid and Kuiper belts, and one known giant planet.",
      [["eps Eri b", 2692, 3.5, null, 209, 90, 2000, "Radial Velocity"]]],
    ["Lalande 21185", 11.056, 35.97, 8.31, "M2 V", 3601, 0.39, "One of the closest red dwarfs, with a hot super-Earth and a cold outer planet.",
      [["Lalande 21185 b", 12.95, 0.079, null, 2.7, 370, 2019, "Radial Velocity"], ["Lalande 21185 c", 2908, 2.94, null, 13.6, 60, 2021, "Radial Velocity"]]],
    ["Teegarden's Star", 2.8889, 16.884, 12.5, "M7 V", 2904, 0.11, "A tiny, dim red dwarf, found only in 2003. Two of its planets are about Earth's mass and get roughly Earth-like warmth.",
      [["Teegarden's Star b", 4.91, 0.0259, null, 1.05, 277, 2019, "Radial Velocity"], ["Teegarden's Star c", 11.41, 0.0455, null, 1.11, 209, 2019, "Radial Velocity"], ["Teegarden's Star d", 26.13, 0.0791, null, 0.82, 159, 2024, "Radial Velocity"]]],
    ["Ross 128", 11.7957, 0.805, 11.0, "M4 V", 3192, 0.2, "A quiet red dwarf (few flares) with an Earth-mass planet at a mild temperature. It is moving toward us and will be our nearest star in about 79,000 years.",
      [["Ross 128 b", 9.866, 0.0496, null, 1.4, 294, 2017, "Radial Velocity"]]],
    ["GJ 273", 7.4529, 5.225, 12.4, "M3.5 V", 3382, 0.29, "Luyten's Star. In 2017 a message called \"Sónar Calling GJ 273b\" was beamed toward it; it arrives in 2030.",
      [["GJ 273 b", 18.65, 0.091, null, 2.9, 259, 2017, "Radial Velocity"], ["GJ 273 c", 4.72, 0.036, null, 1.2, 400, 2017, "Radial Velocity"]]],
    ["TRAPPIST-1", 23.1062, -5.041, 40.7, "M8 V", 2566, 0.119, "A cool red dwarf barely bigger than Jupiter, with seven Earth-sized rocky planets packed closer than Mercury is to our Sun. Three (e, f, g) are in the zone where water could be liquid. The James Webb telescope studies them.",
      [["TRAPPIST-1 b", 1.511, 0.01154, 1.116, 1.374, 398, 2016, "Transit"], ["TRAPPIST-1 c", 2.422, 0.0158, 1.097, 1.308, 340, 2016, "Transit"], ["TRAPPIST-1 d", 4.05, 0.02227, 0.788, 0.388, 286, 2017, "Transit"], ["TRAPPIST-1 e", 6.1, 0.02925, 0.92, 0.692, 250, 2017, "Transit"], ["TRAPPIST-1 f", 9.207, 0.03849, 1.045, 1.039, 218, 2017, "Transit"], ["TRAPPIST-1 g", 12.353, 0.04683, 1.129, 1.321, 197, 2017, "Transit"], ["TRAPPIST-1 h", 18.767, 0.06189, 0.755, 0.326, 173, 2017, "Transit"]]],
    ["51 Peg", 22.9576, 20.769, 50.6, "G2 IV", 5768, 1.15, "The first planet ever found around a Sun-like star (1995, Nobel Prize 2019). A \"hot Jupiter\": half Jupiter's mass, circling its star in four days.",
      [["51 Peg b", 4.2308, 0.0527, null, 146, 1260, 1995, "Radial Velocity"]]],
    ["PSR B1257+12", 13.0, 12.68, 2300, "pulsar", null, null, "The first planets ever found outside the solar system (1992), around a pulsar: the spinning, city-sized core left after a star exploded. They were found from tiny wobbles in its radio pulses.",
      [["PSR B1257+12 b", 25.26, 0.19, null, 0.02, null, 1994, "Pulsar Timing"], ["PSR B1257+12 c", 66.5, 0.36, null, 4.3, null, 1992, "Pulsar Timing"], ["PSR B1257+12 d", 98.2, 0.46, null, 3.9, null, 1992, "Pulsar Timing"]]],
    ["Kepler-452", 19.7378, 44.2775, 1800, "G2 V", 5757, 1.11, "A Sun-like star a bit older than ours. Its planet b takes 385 days to go around, in the zone where water could be liquid, and was nicknamed \"Earth's cousin\".",
      [["Kepler-452 b", 384.8, 1.046, 1.63, null, 265, 2015, "Transit"]]],
    ["Kepler-186", 19.9134, 43.954, 579, "M1 V", 3755, 0.52, "Kepler-186 f was the first Earth-sized planet found in a star's temperate zone (2014).",
      [["Kepler-186 b", 3.887, 0.0378, 1.07, null, 579, 2014, "Transit"], ["Kepler-186 c", 7.267, 0.0574, 1.25, null, 470, 2014, "Transit"], ["Kepler-186 d", 13.34, 0.0861, 1.40, null, 383, 2014, "Transit"], ["Kepler-186 e", 22.41, 0.1216, 1.27, null, 323, 2014, "Transit"], ["Kepler-186 f", 129.9, 0.432, 1.17, null, 188, 2014, "Transit"]]],
    ["Kepler-22", 19.2783, 47.884, 640, "G5 V", 5518, 0.98, "The first planet the Kepler telescope found in a Sun-like star's temperate zone (2011). It is over twice Earth's width, so it may be a water world or a small Neptune.",
      [["Kepler-22 b", 289.9, 0.849, 2.38, null, 262, 2011, "Transit"]]],
    ["Kepler-16", 19.2723, 51.757, 245, "K7 + M", 4450, 0.65, "A real \"Tatooine\": a Saturn-sized planet that circles two stars, so it has two sunsets.",
      [["Kepler-16 b", 228.8, 0.7048, 8.45, 105.8, 188, 2011, "Transit"]]],
    ["Kepler-90", 18.9724, 49.305, 2840, "G0 V", 6080, 1.2, "Eight known planets, tied with our solar system for the most. Small rocky ones close in, giants further out, like a squeezed copy of our system. The eighth was found by Google's AI in 2017.",
      [["Kepler-90 b", 7.008, 0.074, 1.31, null, 1200, 2013, "Transit"], ["Kepler-90 c", 8.719, 0.089, 1.18, null, 1100, 2013, "Transit"], ["Kepler-90 i", 14.449, 0.107, 1.32, null, 1000, 2017, "Transit"], ["Kepler-90 d", 59.74, 0.32, 2.88, null, 580, 2013, "Transit"], ["Kepler-90 e", 91.94, 0.42, 2.67, null, 500, 2013, "Transit"], ["Kepler-90 f", 124.9, 0.48, 2.89, null, 470, 2013, "Transit"], ["Kepler-90 g", 210.6, 0.71, 8.13, null, 380, 2013, "Transit"], ["Kepler-90 h", 331.6, 1.01, 11.3, null, 330, 2013, "Transit"]]],
    ["HR 8799", 23.1218, 21.134, 133, "A5 V", 7430, 1.34, "A young, bright star with four giant planets that telescopes have photographed directly, and filmed moving around it over the years.",
      [["HR 8799 e", 16400, 16.4, 13, 2300, 1000, 2010, "Imaging"], ["HR 8799 d", 36500, 27, 13, 2300, 1000, 2008, "Imaging"], ["HR 8799 c", 69000, 41, 13, 2300, 1000, 2008, "Imaging"], ["HR 8799 b", 165000, 71, 13, 1800, 900, 2008, "Imaging"]]],
    ["bet Pic", 5.7881, -51.066, 63.4, "A6 V", 8052, 1.5, "A very young star (about 20 million years) still surrounded by the dusty disk planets form from, with two giant planets inside it.",
      [["bet Pic c", 1200, 2.7, null, 2800, 400, 2019, "Radial Velocity"], ["bet Pic b", 8700, 10.3, 16, 3000, 1600, 2008, "Imaging"]]],
    ["HD 209458", 22.0525, 18.884, 157, "G0 V", 6091, 1.2, "Nicknamed Osiris. The first planet seen passing in front of its star (1999), and the first with an atmosphere detected. It is losing gas into a comet-like tail.",
      [["HD 209458 b", 3.5247, 0.047, 15.1, 219, 1450, 1999, "Transit"]]],
    ["HD 189733", 20.0084, 22.711, 64.5, "K2 V", 5050, 0.8, "Its hot Jupiter is a deep cobalt blue, with winds of about 8,700 km/h that are thought to carry molten glass sideways.",
      [["HD 189733 b", 2.2186, 0.031, 12.7, 360, 1200, 2005, "Transit"]]],
    ["WASP-12", 6.5072, 29.672, 1400, "G0", 6300, 1.66, "Its giant planet is so close it is stretched into an egg shape and is slowly spiraling in; the star will swallow it in a few million years.",
      [["WASP-12 b", 1.0914, 0.0234, 20.8, 465, 2580, 2008, "Transit"]]],
    ["KELT-9", 20.5148, 39.94, 670, "B9.5-A0", 10170, 2.4, "The hottest planet known: its day side is hotter than many stars, about 4,000 °C, hot enough to tear molecules apart.",
      [["KELT-9 b", 1.4811, 0.035, 21.2, 916, 4050, 2016, "Transit"]]],
    ["WASP-76", 1.7907, 2.7, 634, "F7", 6250, 1.75, "A hot Jupiter where iron vaporizes on the day side and is thought to rain down as liquid iron on the night side.",
      [["WASP-76 b", 1.81, 0.033, 20.5, 290, 2160, 2013, "Transit"]]],
    ["55 Cnc", 8.8752, 28.33, 41, "K0 IV", 5196, 0.94, "Five planets, including 55 Cancri e, a super-Earth so hot (about 2,000 °C) its surface is probably molten lava.",
      [["55 Cnc e", 0.7365, 0.0154, 1.88, 7.99, 1950, 2004, "Radial Velocity"], ["55 Cnc b", 14.65, 0.113, null, 263, 700, 1996, "Radial Velocity"], ["55 Cnc c", 44.4, 0.237, null, 54, 480, 2004, "Radial Velocity"], ["55 Cnc f", 260, 0.77, null, 47, 270, 2007, "Radial Velocity"], ["55 Cnc d", 4800, 5.5, null, 1230, 110, 2002, "Radial Velocity"]]],
    ["GJ 436", 11.7, 26.7, 31.9, "M2.5 V", 3480, 0.42, "A Neptune-sized planet trailing a huge cloud of hydrogen like a comet's tail.",
      [["GJ 436 b", 2.644, 0.029, 4.17, 22, 686, 2004, "Radial Velocity"]]],
    ["GJ 1214", 17.2531, 4.963, 47.5, "M4.5 V", 3250, 0.22, "A \"mini-Neptune\" wrapped in thick haze; it may hold a lot of water.",
      [["GJ 1214 b", 1.58, 0.0149, 2.74, 8.2, 596, 2009, "Transit"]]],
    ["TOI-700", 6.4472, -65.578, 101, "M2 V", 3480, 0.42, "Found by NASA's TESS telescope: two Earth-sized planets (d and e) in the temperate zone of a quiet red dwarf.",
      [["TOI-700 b", 9.98, 0.0637, 0.91, null, 415, 2020, "Transit"], ["TOI-700 c", 16.05, 0.0925, 2.6, null, 345, 2020, "Transit"], ["TOI-700 e", 27.81, 0.134, 0.95, null, 295, 2023, "Transit"], ["TOI-700 d", 37.42, 0.163, 1.07, null, 269, 2020, "Transit"]]],
    ["LHS 1140", 0.7477, -15.272, 48.8, "M4.5 V", 3096, 0.21, "LHS 1140 b is one of the best places to look for an atmosphere on a temperate world; it may be covered in ice or ocean.",
      [["LHS 1140 c", 3.78, 0.027, 1.27, 1.9, 420, 2018, "Transit"], ["LHS 1140 b", 24.74, 0.0946, 1.73, 5.6, 226, 2017, "Transit"]]],
    ["K2-18", 11.5025, 7.589, 124, "M2.5 V", 3457, 0.41, "The James Webb telescope found methane and carbon dioxide in its planet's air. It could be an ocean world under a hydrogen sky; that is still argued over.",
      [["K2-18 b", 32.94, 0.143, 2.61, 8.6, 255, 2015, "Transit"]]],
    ["Kepler-10", 19.0278, 50.241, 608, "G", 5708, 1.06, "Kepler-10 b was the first rocky planet confirmed outside the solar system (2011): a lava world that circles in under a day.",
      [["Kepler-10 b", 0.8375, 0.0168, 1.47, 3.3, 1833, 2011, "Transit"], ["Kepler-10 c", 45.29, 0.24, 2.35, 7.4, 580, 2011, "Transit"]]],
    ["Kepler-444", 19.31, 41.63, 119, "K0 V", 5046, 0.75, "One of the oldest planet systems known, about 11 billion years old, more than twice the age of Earth, with five planets smaller than Earth.",
      [["Kepler-444 b", 3.6, 0.042, 0.40, null, 1170, 2015, "Transit"], ["Kepler-444 c", 4.55, 0.049, 0.50, null, 1090, 2015, "Transit"], ["Kepler-444 d", 6.19, 0.06, 0.53, null, 980, 2015, "Transit"], ["Kepler-444 e", 7.74, 0.07, 0.55, null, 910, 2015, "Transit"], ["Kepler-444 f", 9.74, 0.081, 0.74, null, 850, 2015, "Transit"]]],
    ["GJ 581", 15.3247, -7.722, 20.5, "M3 V", 3480, 0.3, "A famous red dwarf system; some planets claimed here turned out to be signals from the star itself, a lesson in how hard this is.",
      [["GJ 581 e", 3.15, 0.028, null, 1.7, 470, 2009, "Radial Velocity"], ["GJ 581 b", 5.37, 0.041, null, 15.6, 400, 2005, "Radial Velocity"], ["GJ 581 c", 12.92, 0.073, null, 5.4, 300, 2007, "Radial Velocity"]]],
    ["GJ 876", 22.885, -14.263, 15.2, "M4 V", 3348, 0.38, "The first red dwarf found with planets (1998). Three of its four planets tug each other in a precise rhythm.",
      [["GJ 876 d", 1.938, 0.0208, null, 6.8, 600, 2005, "Radial Velocity"], ["GJ 876 c", 30.1, 0.13, null, 227, 230, 2001, "Radial Velocity"], ["GJ 876 b", 61.1, 0.21, null, 723, 180, 1998, "Radial Velocity"], ["GJ 876 e", 124, 0.33, null, 14, 145, 2010, "Radial Velocity"]]],
    ["ups And", 1.6114, 41.405, 44, "F8 V", 6212, 1.48, "The first star (other than the Sun) found with more than one planet (1999). Visible without a telescope in Andromeda.",
      [["ups And b", 4.617, 0.059, null, 218, 1500, 1996, "Radial Velocity"], ["ups And c", 241.3, 0.83, null, 630, 400, 1999, "Radial Velocity"], ["ups And d", 1276, 2.5, null, 1300, 220, 1999, "Radial Velocity"]]],
    ["47 UMa", 10.991, 40.43, 45.9, "G1 V", 5892, 1.17, "A Sun-like star with three giant planets far out, a bit like a heavier version of our Jupiter and Saturn.",
      [["47 UMa b", 1078, 2.1, null, 813, 200, 1996, "Radial Velocity"], ["47 UMa c", 2391, 3.6, null, 172, 150, 2001, "Radial Velocity"], ["47 UMa d", 14000, 11.6, null, 521, 85, 2010, "Radial Velocity"]]],
    ["HD 80606", 9.3763, 50.604, 217, "G5", 5574, 0.98, "Its giant planet has one of the most stretched orbits known: it swings from near its star (heating up hundreds of degrees in hours) to far out.",
      [["HD 80606 b", 111.4, 0.449, 11.5, 1270, 400, 2001, "Radial Velocity"]]],
    ["Kepler-62", 18.8807, 45.349, 990, "K2 V", 4925, 0.64, "Five planets; e and f are super-Earths in the temperate zone, possibly covered in ocean.",
      [["Kepler-62 b", 5.71, 0.0553, 1.31, null, 750, 2013, "Transit"], ["Kepler-62 c", 12.44, 0.0929, 0.54, null, 578, 2013, "Transit"], ["Kepler-62 d", 18.16, 0.12, 1.95, null, 510, 2013, "Transit"], ["Kepler-62 e", 122.4, 0.427, 1.61, null, 270, 2013, "Transit"], ["Kepler-62 f", 267.3, 0.718, 1.41, null, 208, 2013, "Transit"]]],
    ["Kepler-442", 19.0137, 39.28, 1200, "K", 4402, 0.6, "Kepler-442 b is often ranked among the most Earth-like planets found: a little bigger than Earth, with a similar amount of starlight.",
      [["Kepler-442 b", 112.3, 0.409, 1.34, null, 233, 2015, "Transit"]]],
    ["Kepler-1649", 19.5, 41.06, 301, "M5 V", 3240, 0.23, "Kepler-1649 c, close to Earth's size and warmth, was found in old Kepler data in 2020 after the computer had missed it.",
      [["Kepler-1649 c", 19.54, 0.0827, 1.06, null, 234, 2020, "Transit"]]],
    ["AU Mic", 20.7518, -31.342, 32, "M1 Ve", 3700, 0.75, "A baby star (about 22 million years old) with a dusty disk and two young planets still settling in.",
      [["AU Mic b", 8.463, 0.0645, 4.07, 20, 600, 2020, "Transit"], ["AU Mic c", 18.86, 0.11, 3.24, 10, 460, 2021, "Transit"]]],
    ["GJ 667 C", 17.3197, -34.99, 23.6, "M1.5 V", 3350, 0.42, "Part of a triple star system: from its planet c you would see two other suns in the sky.",
      [["GJ 667 C b", 7.2, 0.05, null, 5.6, 460, 2009, "Radial Velocity"], ["GJ 667 C c", 28.14, 0.125, null, 3.8, 277, 2011, "Radial Velocity"]]],
    ["OGLE-2005-BLG-390L", 17.909, -30.38, 21500, "M", 3000, 0.4, "Found toward the middle of the galaxy by gravitational microlensing (the star briefly bent and brightened light from a star behind it). A frozen super-Earth at about −220 °C.",
      [["OGLE-2005-BLG-390L b", 3500, 2.6, null, 5.5, 50, 2005, "Microlensing"]]]
  ];
  var FAME = {};   // notes by host name, added to the full catalog when it arrives
  FAMOUS.forEach(function (f) { FAME[norm(f[0])] = f[7]; });
  function norm(s) { return String(s || "").toLowerCase().replace(/[^a-z0-9]/g, ""); }
  function famousAsSystems() {
    return FAMOUS.map(function (f) {
      return { h: f[0], ra: f[1] * 15, dec: f[2], ly: f[3], sp: f[4], t: f[5], r: f[6], p: f[8].map(function (p) { return [p[0], p[1], p[2], p[3], p[4], p[5], null, p[6], p[7], ""]; }) };
    });
  }

  /* ---------- landmarks: nebulae, clusters, giant stars, a black hole, the galaxies around ours ---------- */
  // [name, galactic longitude, latitude, light-years, kind, color, about]
  var MARKS = [
    ["Orion Nebula", 209.0, -19.4, 1344, "nebula", "#ff6fa8", "The nearest big star nursery, visible to the eye as the fuzzy middle \"star\" in Orion's sword. Thousands of stars are being born in it right now."],
    ["Pleiades", 166.6, -23.5, 444, "cluster", "#9ec3ff", "The Seven Sisters: a cluster of hot young blue stars about 100 million years old, easy to see in winter skies."],
    ["Hyades", 180.1, -22.3, 153, "cluster", "#ffd28a", "The nearest star cluster to us, the V-shaped face of Taurus the bull."],
    ["Crab Nebula", 184.6, -5.8, 6500, "remnant", "#7fe3ff", "The wreck of a star that exploded in 1054. Chinese astronomers recorded it as a \"guest star\" bright enough to see in daylight for weeks. A pulsar spinning 30 times a second sits at its center."],
    ["Eagle Nebula", 17.0, 0.8, 5700, "nebula", "#ffb36b", "Home of the Pillars of Creation, towers of gas and dust light-years tall where new stars are forming."],
    ["Carina Nebula", 287.6, -0.6, 8500, "nebula", "#ff7e5f", "One of the biggest star nurseries in the galaxy, home to Eta Carinae, a huge unstable star that could explode as a supernova."],
    ["Lagoon Nebula", 6.0, -1.2, 4100, "nebula", "#ff6fa8", "A glowing cloud of gas and young stars toward the galaxy's middle, visible in binoculars."],
    ["Ring Nebula", 63.2, 13.97, 2570, "remnant", "#7fe3ff", "A shell of gas puffed off by a dying Sun-like star. Our Sun will make something like this in about 5 billion years."],
    ["Helix Nebula", 36.2, -57.1, 650, "remnant", "#7fe3ff", "The nearest bright shell from a dying Sun-like star, nicknamed the Eye of God."],
    ["Vela pulsar", 263.6, -2.8, 940, "remnant", "#7fe3ff", "The spinning core left by a supernova about 11,000 years ago, turning 11 times a second."],
    ["Betelgeuse", 199.8, -9.0, 550, "star", "#ff8a4c", "A red supergiant in Orion's shoulder. Put in the Sun's place it would swallow Mars. It will explode as a supernova sometime in the next 100,000 years."],
    ["Rigel", 209.2, -25.2, 860, "star", "#9ec3ff", "A blue supergiant, Orion's foot: about 120,000 times brighter than the Sun."],
    ["Polaris", 123.3, 26.5, 433, "star", "#fff1c9", "The North Star, almost straight above Earth's north pole, so the whole sky seems to turn around it."],
    ["Vega", 67.4, 19.2, 25, "star", "#cfe0ff", "One of the brightest stars in summer skies, with a dusty disk. It was the North Star 12,000 years ago and will be again."],
    ["Sirius", 227.2, -8.9, 8.6, "star", "#cfe0ff", "The brightest star in the night sky, with a white dwarf partner, the hot leftover core of a dead star."],
    ["Alpha Centauri A & B", 315.7, -0.7, 4.37, "star", "#fff1c9", "Two Sun-like stars that circle each other every 80 years; Proxima Centauri circles them both. The nearest star system."],
    ["Cygnus X-1", 71.3, 3.1, 7200, "blackhole", "#c9a7ff", "The first black hole ever confirmed (1971): about 21 times the Sun's mass, pulling gas off a blue giant companion."],
    ["Omega Centauri", 309.1, 15.0, 17090, "globular", "#ffd28a", "The biggest ball of stars in the galaxy, about 10 million stars, possibly the core of a small galaxy the Milky Way swallowed."],
    ["Sagittarius A*", 0, 0, R0, "core", "#ffcf7a", "The black hole at the center of the galaxy, 4 million times the Sun's mass. The Event Horizon Telescope photographed its shadow in 2022. Everything here, the Sun included, circles it: one lap takes the Sun about 230 million years."],
    ["Large Magellanic Cloud", 280.5, -32.9, 163000, "galaxy", "#bcd2ff", "A small galaxy circling ours, visible to the eye from the southern hemisphere. A star there exploded in 1987, the closest supernova seen in modern times."],
    ["Small Magellanic Cloud", 302.8, -44.3, 200000, "galaxy", "#bcd2ff", "A smaller companion galaxy to ours, next to the Large Magellanic Cloud in southern skies."],
    // the Local Group: the few dozen galaxies bound together with ours
    ["Andromeda Galaxy", 121.17, -21.57, 2537000, "spiral", "#ffd9b0", "The nearest big galaxy, about 220,000 light-years across with around a trillion stars: bigger than the Milky Way. It is the farthest thing most people can see without a telescope, a faint smudge in autumn skies. It is coming toward us at about 110 km/s. For years the forecast was a head-on merger in about 4.5 billion years; a 2025 study using newer measurements put the odds of merging at about 50-50 over the next 10 billion years. Stars almost never hit each other in a merger: they are too far apart.", 220000],
    ["Triangulum Galaxy", 133.61, -31.33, 2730000, "spiral", "#c9dcff", "The third-largest galaxy in the Local Group, a loose spiral about 60,000 light-years across. On a very dark night it is the most distant thing the eye can see.", 60000],
    ["M32", 121.15, -21.98, 2490000, "dwarf", "#ffe6c8", "A small, dense galaxy hugging Andromeda, probably the stripped core of a bigger galaxy Andromeda tore apart.", 6500],
    ["M110", 120.72, -21.14, 2690000, "dwarf", "#ffe6c8", "A dwarf galaxy orbiting Andromeda.", 17000],
    ["Sagittarius Dwarf", 5.6, -14.2, 65000, "dwarf", "#ffe6c8", "A small galaxy being pulled apart by the Milky Way right now; its stars are strung in streams that wrap around our galaxy. It has passed through our disk several times.", 10000],
    ["Draco Dwarf", 86.4, 34.7, 260000, "dwarf", "#ffe6c8", "A faint dwarf galaxy circling ours, made mostly of dark matter.", 2700],
    ["Ursa Minor Dwarf", 105.0, 44.8, 200000, "dwarf", "#ffe6c8", "A very old, faint dwarf galaxy circling ours.", 2000],
    ["Sculptor Dwarf", 287.5, -83.2, 290000, "dwarf", "#ffe6c8", "A dwarf galaxy circling ours, below the plane of the Milky Way.", 3000],
    ["Fornax Dwarf", 237.1, -65.7, 460000, "dwarf", "#ffe6c8", "One of the brighter dwarf galaxies circling ours, with its own six globular star clusters.", 5000],
    ["Carina Dwarf", 260.1, -22.2, 330000, "dwarf", "#ffe6c8", "A dwarf galaxy circling ours that made its stars in bursts.", 2000],
    ["Leo I", 225.99, 49.11, 820000, "dwarf", "#ffe6c8", "One of the farthest dwarf galaxies still tied to the Milky Way.", 2600],
    ["NGC 6822", 25.34, -18.4, 1600000, "dwarf", "#ffe6c8", "Barnard's Galaxy, an irregular dwarf galaxy full of star-forming clouds, on its own between us and the edge of the Local Group.", 7000],
    ["IC 1613", 129.7, -60.6, 2400000, "dwarf", "#ffe6c8", "A quiet irregular dwarf galaxy near Andromeda's side of the Local Group.", 12000],
    ["WLM", 75.86, -73.62, 3000000, "dwarf", "#ffe6c8", "A lonely dwarf galaxy at the outer edge of the Local Group.", 8000],
    // beyond the Local Group: real groups and clusters of galaxies, by their real directions and distances
    ["M81 Group", 142.1, 40.9, 11700000, "galgroup", "#d6e2ff", "A nearby group of galaxies around the spiral M81, with the bright starburst galaxy M82 being stirred up by M81's pull.", 3000000],
    ["Centaurus A Group", 309.5, 19.4, 12000000, "galgroup", "#d6e2ff", "A group around Centaurus A, a giant galaxy with a supermassive black hole firing jets a million light-years long.", 4000000],
    ["Sculptor Group", 97.4, -87.96, 11400000, "galgroup", "#d6e2ff", "The nearest group of galaxies to ours, around the dusty spiral NGC 253.", 4000000],
    ["Virgo Cluster", 283.8, 74.4, 54000000, "galcluster", "#ffe0c2", "The nearest big cluster: about 1,300 galaxies (maybe 2,000), including M87, whose central black hole was the first ever photographed (2019). Our Local Group sits on its outskirts.", 15000000],
    ["Fornax Cluster", 236.7, -53.6, 62000000, "galcluster", "#ffe0c2", "The second-nearest rich cluster of galaxies, small and tightly packed.", 8000000],
    ["Norma Cluster (Great Attractor)", 325.3, -7.3, 220000000, "galcluster", "#ffc2a8", "The heart of the Great Attractor, a huge pile-up of mass that our Local Group and thousands of other galaxies are drifting toward at about 600 km/s. It sits behind the Milky Way's dusty disk, so it is hard to see.", 20000000],
    ["Perseus Cluster", 150.6, -13.3, 240000000, "galcluster", "#ffe0c2", "One of the most massive things nearby: thousands of galaxies in a cloud of hot gas. NASA turned pressure waves from its central black hole into sound.", 20000000],
    ["Coma Cluster", 58.1, 87.96, 321000000, "galcluster", "#ffe0c2", "A cluster of over 1,000 galaxies. In 1933 Fritz Zwicky noticed its galaxies move too fast for the matter we can see, the first hint of dark matter.", 20000000],
    ["Shapley Supercluster", 312, 30, 650000000, "supercluster", "#ffb3a0", "The biggest concentration of galaxies in our part of the universe, just beyond the Great Attractor.", 120000000]
  ];
  var ARMS = [["PERSEUS ARM", 32600], ["SAGITTARIUS–CARINA ARM", 23350], ["SCUTUM–CENTAURUS ARM", 16700], ["NORMA–OUTER ARM", 12000]];
  var PITCH = Math.tan(12.5 * D2R);

  /* ---------- coordinates ---------- */
  var EQ2GAL = [[-0.0548755604, -0.8734370902, -0.4838350155], [0.4941094279, -0.44482963, 0.7469822445], [-0.867666149, -0.1980763734, 0.4559837762]];
  function galDir(raDeg, dec) {
    var a = raDeg * D2R, d = dec * D2R, e = [Math.cos(d) * Math.cos(a), Math.cos(d) * Math.sin(a), Math.sin(d)];
    return EQ2GAL.map(function (r) { return r[0] * e[0] + r[1] * e[1] + r[2] * e[2]; });
  }
  function fromSun(dir, ly) { return [SUN[0] + dir[0] * ly, SUN[1] + dir[1] * ly, SUN[2] + dir[2] * ly]; }
  function lbDir(l, b) { l *= D2R; b *= D2R; return [Math.cos(b) * Math.cos(l), Math.cos(b) * Math.sin(l), Math.sin(b)]; }

  /* ---------- the drawn galaxy: particles made once from a fixed seed ---------- */
  function rng(seed) { return function () { seed |= 0; seed = seed + 0x6D2B79F5 | 0; var t = Math.imul(seed ^ seed >>> 15, 1 | seed); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
  var COLS = ["185,205,255", "255,236,212", "255,204,140", "255,105,170", "130,175,255"], LEVELS = [0.22, 0.45, 0.8];
  var PART = null, DUST = null, OTHER = null;
  function armPoint(r, j) { var phi = Math.PI + Math.log(r / ARMS[j][1]) / PITCH; return [r * Math.cos(phi), r * Math.sin(phi)]; }
  function build() {
    var rr = rng(42), gauss = function () { return (rr() + rr() + rr() + rr() - 2) * 0.87; }, xs = [], ys = [], zs = [], bk = [];
    var add = function (x, y, z, c, lvl) { xs.push(x); ys.push(y); zs.push(z); bk.push(c * 3 + lvl); };
    var i, r, p, w, j;
    for (i = 0; i < 40000; i++) {   // the four main arms (each wraps round, so the far parts make the outer arms)
      j = i % 4; r = 9500 + Math.pow(rr(), 0.9) * 46000; p = armPoint(r, j); w = 900 + r * 0.05;
      var c = rr() < 0.12 ? 4 : 0, lv = rr() < 0.15 ? 2 : rr() < 0.5 ? 1 : 0;
      add(p[0] + gauss() * w, p[1] + gauss() * w, gauss() * 260, c, lv);
      if (rr() < 0.045) { var kx = p[0] + gauss() * w * 0.6, ky = p[1] + gauss() * w * 0.6; for (var n = 0; n < 6; n++) add(kx + gauss() * 160, ky + gauss() * 160, gauss() * 60, 3, n < 2 ? 2 : 1); }
    }
    for (i = 0; i < 1400; i++) {   // the Orion Spur, the little arm the Sun sits on (a faint bridge, bending with the arms)
      var s = -8000 + rr() * 15000, d = lbDir(78 + s / 1000, 0);
      add(SUN[0] + d[0] * s + gauss() * 900, SUN[1] + d[1] * s + gauss() * 900, gauss() * 220, rr() < 0.15 ? 4 : 0, 0);
    }
    for (i = 0; i < 22000; i++) {   // the thin disk between the arms
      r = -11500 * Math.log(1 - rr() * 0.985); if (r < 3000) { i--; continue; } var a = rr() * 2 * Math.PI;
      add(r * Math.cos(a), r * Math.sin(a), gauss() * 380, 1, rr() < 0.25 ? 1 : 0);
    }
    var bar = [-Math.cos(27 * D2R), Math.sin(27 * D2R)];   // the bar's near end points toward our side
    for (i = 0; i < 8000; i++) { var t = gauss() * 5200, q = gauss() * 1300; add(bar[0] * t - bar[1] * q, bar[1] * t + bar[0] * q, gauss() * 900, 2, rr() < 0.4 ? 2 : 1); }
    for (i = 0; i < 6500; i++) { var u = rr() * 2 - 1, aa = rr() * 2 * Math.PI, rad = Math.pow(rr(), 1.6) * 6500, cc = Math.sqrt(1 - u * u); add(cc * Math.cos(aa) * rad, cc * Math.sin(aa) * rad, u * rad * 0.6, 2, rad < 2500 ? 2 : 1); }
    for (i = 0; i < 1800; i++) { var hr = 10000 + rr() * 60000, ha = rr() * 2 * Math.PI, hu = rr() * 2 - 1, hc = Math.sqrt(1 - hu * hu); add(hc * Math.cos(ha) * hr, hc * Math.sin(ha) * hr, hu * hr, 1, 0); }   // the faint halo
    var order = []; for (i = 0; i < xs.length; i++) order.push(i);
    PART = { x: new Float32Array(xs), y: new Float32Array(ys), z: new Float32Array(zs), buckets: [] };
    for (var b = 0; b < COLS.length * 3; b++) PART.buckets.push(order.filter(function (k) { return bk[k] === b; }));
    var dx = [], dy = [], dz = [];
    for (i = 0; i < 9000; i++) {   // dust lanes along the inner edge of each arm
      j = i % 4; r = 11000 + rr() * 38000; p = armPoint(r * 0.94, j); w = 300 + r * 0.012;
      dx.push(p[0] + gauss() * w); dy.push(p[1] + gauss() * w); dz.push(gauss() * 90);
    }
    DUST = { x: new Float32Array(dx), y: new Float32Array(dy), z: new Float32Array(dz) };
    // Andromeda and Triangulum, tipped the way we see them (Andromeda nearly edge-on, 77°)
    var ox = [], oy = [], oz = [], ob = [];
    [[121.17, -21.57, 2537000, 77, 16000, 20000, 1.15], [133.61, -31.33, 2730000, 55, 5000, 7000, 0.6]].forEach(function (G) {
      var los = lbDir(G[0], G[1]), c0 = fromSun(los, G[2]);
      var u = [los[1], -los[0], 0], ul = Math.hypot(u[0], u[1]); u = [u[0] / ul, u[1] / ul, 0];
      var inc = G[3] * D2R, n = [los[0] * Math.cos(inc) + u[0] * Math.sin(inc), los[1] * Math.cos(inc) + u[1] * Math.sin(inc), los[2] * Math.cos(inc)];
      var e1 = [n[1] * 0 - n[2] * 1, n[2] * 0 - n[0] * 0, n[0] * 1 - n[1] * 0]; var el1 = Math.hypot(e1[0], e1[1], e1[2]) || 1; e1 = e1.map(function (v) { return v / el1; });
      var e2 = [n[1] * e1[2] - n[2] * e1[1], n[2] * e1[0] - n[0] * e1[2], n[0] * e1[1] - n[1] * e1[0]];
      for (var q = 0; q < G[4]; q++) {
        var bulge = rr() < 0.22, rr0, a, h;
        if (bulge) { rr0 = Math.abs(gauss()) * 5000 * G[6]; a = rr() * 2 * Math.PI; h = gauss() * 2500 * G[6]; }
        else {   // a smooth disk, a bright star-forming ring (Andromeda's is about 33,000 ly out) and faint arms
          var kind = rr();
          if (kind < 0.45) { rr0 = -G[5] * Math.log(1 - rr() * 0.98); a = rr() * 2 * Math.PI; }
          else if (kind < 0.75) { rr0 = 29000 * G[6] + gauss() * 4000 * G[6]; a = rr() * 2 * Math.PI; }
          else { rr0 = -G[5] * Math.log(1 - rr() * 0.97); a = (q % 2) * Math.PI + Math.log(Math.max(1, rr0) / (8000 * G[6])) / 0.35 + gauss() * 0.3; }
          h = gauss() * 600;
        }
        var lx = Math.cos(a) * rr0, ly = Math.sin(a) * rr0;
        ox.push(c0[0] + e1[0] * lx + e2[0] * ly + n[0] * h); oy.push(c0[1] + e1[1] * lx + e2[1] * ly + n[1] * h); oz.push(c0[2] + e1[2] * lx + e2[2] * ly + n[2] * h);
        ob.push(bulge ? 2 * 3 + 2 : (rr() < 0.1 ? 3 * 3 + 1 : (rr() < 0.3 ? 4 : 0) * 3 + (rr() < 0.4 ? 1 : 0)));
      }
    });
    var ord2 = []; for (i = 0; i < ox.length; i++) ord2.push(i);
    OTHER = { x: new Float32Array(ox), y: new Float32Array(oy), z: new Float32Array(oz), buckets: [] };
    for (var b2 = 0; b2 < COLS.length * 3; b2++) OTHER.buckets.push(ord2.filter(function (k) { return ob[k] === b2; }));
  }

  /* ---------- state ---------- */
  var host = null, root, cv, g2, W = 0, H = 0, dpr = 1, active = false, onExit = null;
  var yaw = 90, tilt = 52, rad = 60, anchor = null, flying = null, drawQ = false, filter = "all";
  var systems = famousAsSystems(), catalogAt = null, loaded = false, shown = [], tipEl, hoverId = null;
  var BG = null;
  function S() { return Math.min(W, H) * 0.46 / rad; }
  function sstep(a, b, x) { var t = Math.max(0, Math.min(1, (x - a) / (b - a))); return t * t * (3 - 2 * t); }
  var camF = null, LG = null;
  function focus() {
    if (camF) return camF;
    if (anchor && Math.hypot(anchor[0], anchor[1], anchor[2]) > 80000) return anchor;   // centered on another galaxy
    var base = anchor || SUN, k = sstep(Math.log(5000), Math.log(55000), Math.log(rad));
    var f = [base[0] + (CENTER[0] - base[0]) * k, base[1] + (CENTER[1] - base[1]) * k, base[2] + (CENTER[2] - base[2]) * k];
    if (!LG) { var m = fromSun(lbDir(121.17, -21.57), 2537000); LG = [m[0] * 0.52, m[1] * 0.52, m[2] * 0.52]; }   // the Local Group's middle, a bit nearer us than Andromeda
    var k2 = sstep(Math.log(300000), Math.log(1600000), Math.log(rad)) * (1 - sstep(Math.log(5000000), Math.log(40000000), Math.log(rad)));   // and back to us: we sit at the middle of our own observable universe
    return [f[0] + (LG[0] - f[0]) * k2, f[1] + (LG[1] - f[1]) * k2, f[2] + (LG[2] - f[2]) * k2];
  }
  var P0, cy0, sy0, ct, st, sc, cxs, cys;
  function setCam() { P0 = focus(); cy0 = Math.cos(yaw * D2R); sy0 = Math.sin(yaw * D2R); ct = Math.cos(tilt * D2R); st = Math.sin(tilt * D2R); sc = S(); cxs = cardOpen() ? W * 0.4 : W / 2; cys = H * 0.5; }
  function cardOpen() { var c = document.getElementById("card"); return c && !c.hidden && W > 1100; }
  function proj(x, y, z) {
    var qx = x - P0[0], qy = y - P0[1], qz = z - P0[2];
    var x1 = qx * cy0 - qy * sy0, y1 = qx * sy0 + qy * cy0;
    return [cxs + x1 * sc, cys - y1 * st * sc - qz * ct * sc, y1 * ct - qz * st];
  }
  function sysPos(s) { if (!s.g) s.g = fromSun(galDir(s.ra, s.dec), s.ly); return s.g; }
  function teffCol(t, sp) {
    if (/pulsar|PSR/i.test(sp || "")) return "#7fe3ff";
    if (/^D/.test(sp || "")) return "#e8f0ff";
    if (!t) return "#ffe9c4";
    return t < 3500 ? "#ff8a5c" : t < 4600 ? "#ffb36b" : t < 5500 ? "#ffd99a" : t < 6200 ? "#fff1c9" : t < 7500 ? "#f4f6ff" : "#a9c6ff";
  }
  function temperate(p) { var R = p[3] != null ? p[3] : p[4] != null ? estR(p[4]) : null; return p[5] != null && p[5] >= 175 && p[5] <= 305 && R != null && R <= 1.9; }
  function estR(m) { return m < 2 ? Math.pow(m, 0.28) : m < 130 ? 0.8 * Math.pow(m, 0.59) : 11.5; }

  /* ---------- page parts ---------- */
  function make(hostEl, exitFn) {
    host = hostEl; onExit = exitFn;
    root = document.createElement("div"); root.className = "gal"; root.hidden = true; host.appendChild(root);
    root.innerHTML = '<canvas class="gal-cv"></canvas>' +
      '<div class="orr-bar gal-bar"><div class="orr-row"><input id="gal-q" placeholder="find a star system, planet or nebula (TRAPPIST, Kepler-452, Orion…)" autocomplete="off"><button id="gal-sun" title="back to the Sun">☉ sun</button><button id="gal-out" title="the whole galaxy">whole galaxy</button><button id="gal-lg" title="our galaxy&#39;s neighbors">local group</button><button id="gal-uni" title="the whole observable universe">universe</button><button id="gal-back" title="back to the solar system">◂ solar system</button></div><div id="gal-res" class="orr-res" hidden></div></div>' +
      '<div class="gal-panel" id="gal-panel"></div><div class="gal-sim" id="gal-sim" hidden><div class="sim-h">THE MILKY WAY AND ANDROMEDA · A SIMPLIFIED SIMULATION</div><div class="sim-t"></div><div class="sim-sep"></div><div class="sim-c"></div><div class="sim-b"><button id="sim-pause">❚❚ pause</button><button id="sim-again">↺ again</button><button id="sim-close">✕ close</button></div><div class="sim-f">This plays the classic forecast. Newer (2025) measurements say a merger in the next 10 billion years is about a coin flip. Stars almost never hit each other: the Sun would most likely survive, maybe flung far out. Each dot stands for millions of stars.</div></div><div class="gal-scale" id="gal-scale"></div><div class="gal-tip" id="gal-tip" hidden></div>' +
      '<div class="orr-note gal-note">The galaxy\'s shape is a model drawn from radio and Gaia star surveys; we can\'t photograph it from inside. Every planet system is real, placed by its true direction and distance. Drag to turn, scroll to zoom; scroll all the way in on the Sun to go back to the solar system.</div>';
    cv = root.querySelector("canvas"); g2 = cv.getContext("2d"); tipEl = $("gal-tip");
    $("gal-back").onclick = function () { exit(); };
    $("gal-sun").onclick = function () { flyTo(null, 60); };
    $("gal-out").onclick = function () { flyTo(null, 52000); };
    $("gal-lg").onclick = function () { flyTo(null, 1750000); };
    $("gal-uni").onclick = function () { flyTo(null, 6.2e10); };
    var drag = null;
    cv.addEventListener("pointerdown", function (e) { if (e.button === 0) drag = [e.clientX, e.clientY, yaw, tilt, false]; });
    window.addEventListener("pointermove", function (e) {
      if (!active) return;
      if (drag) {
        var dx = e.clientX - drag[0], dy = e.clientY - drag[1];
        if (!drag[4] && Math.abs(dx) + Math.abs(dy) < 4) return;
        drag[4] = true; tipEl.hidden = true; yaw = drag[2] + dx * 0.35; tilt = Math.max(4, Math.min(89, drag[3] + dy * 0.3)); req(); return;
      }
      if (e.target !== cv || SIM) { tipEl.hidden = true; return; }
      var r = cv.getBoundingClientRect(), h = hit(e.clientX - r.left, e.clientY - r.top);
      if (h) { tipEl.innerHTML = h.tip; tipEl.style.left = (e.clientX - r.left + 14) + "px"; tipEl.style.top = (e.clientY - r.top + 12) + "px"; tipEl.hidden = false; cv.style.cursor = "pointer"; }
      else { tipEl.hidden = true; cv.style.cursor = ""; }
    });
    window.addEventListener("pointerup", function (e) {
      if (!drag || !active) return; var moved = drag[4]; drag = null;
      if (!moved && e.target === cv && !SIM) { var r = cv.getBoundingClientRect(), h = hit(e.clientX - r.left, e.clientY - r.top); if (h) h.open(); }
    });
    cv.addEventListener("wheel", function (e) {
      e.preventDefault();
      if (SIM) { SIM.zoom = Math.max(0.3, Math.min(8, SIM.zoom * (e.deltaY < 0 ? 1.15 : 1 / 1.15))); req(); return; }
      if (flying) { flying = null; anchor = null; camF = null; }
      if (e.deltaY < 0 && rad <= 16 && !anchor) { exit(); return; }
      rad = Math.max(12, Math.min(9e10, rad * (e.deltaY < 0 ? 1 / 1.18 : 1.18)));
      if (anchor && rad > (Math.hypot(anchor[0], anchor[1], anchor[2]) > 80000 ? 1500000 : 30000)) anchor = null;
      req();
    }, { passive: false });
    var q = $("gal-q"), res = $("gal-res");
    q.oninput = function () {
      var v = norm(q.value); if (!v) { res.hidden = true; return; }
      var hits = MARKS.filter(function (m) { return norm(m[0]).indexOf(v) >= 0; }).map(function (m) { return { n: m[0], sub: m[4] === "globular" ? "star cluster" : m[4], go: function () { openMark(m); } }; })
        .concat(systems.filter(function (s) { return norm(s.h).indexOf(v) >= 0 || s.p.some(function (p) { return norm(p[0]).indexOf(v) >= 0; }); }).slice(0, 40)
          .map(function (s) { return { n: s.h, sub: s.p.length + " planet" + (s.p.length > 1 ? "s" : "") + " · " + fmtLy(s.ly), go: function () { openSys(s, true); } }; }));
      res.innerHTML = hits.length ? hits.slice(0, 30).map(function (h, i) { return '<button data-i="' + i + '"><b>' + esc(h.n) + "</b><span>" + esc(h.sub) + "</span></button>"; }).join("") :
        '<div class="mut" style="padding:8px 10px;line-height:1.5">Nothing called "' + esc(q.value) + '" in ' + (catalogAt ? "NASA's catalog" : "Archie's built-in list (the full NASA catalog downloads the first time Archie is online)") + ".</div>";
      res.hidden = false;
      res.querySelectorAll("button").forEach(function (b) { b.onclick = function () { res.hidden = true; q.value = ""; hits[+b.dataset.i].go(); }; });
    };
    q.onkeydown = function (e) { if (e.key === "Enter") { var b = res.querySelector("button"); if (b) b.click(); } if (e.key === "Escape") { res.hidden = true; q.blur(); } };
    new ResizeObserver(function () { if (active) { resize(); req(); } }).observe(root);
  }
  function resize() { dpr = Math.min(2, window.devicePixelRatio || 1); W = root.clientWidth; H = root.clientHeight; cv.width = W * dpr; cv.height = H * dpr; BG = null; }
  function req() { if (drawQ) return; drawQ = true; requestAnimationFrame(function () { drawQ = false; draw(); }); }
  function fmtLy(ly) { return ly < 1 ? ly.toFixed(2) + " light-years" : ly < 100 ? ly.toFixed(1) + " light-years" : Math.round(ly).toLocaleString() + " light-years"; }

  /* ---------- drawing ---------- */
  function background() {   // a fixed scatter of faint far stars, made once per size
    BG = document.createElement("canvas"); BG.width = cv.width; BG.height = cv.height;
    var b = BG.getContext("2d"), r = rng(5);
    for (var i = 0; i < 900; i++) { var a = 0.15 + Math.pow(r(), 3) * 0.7; b.fillStyle = "rgba(220,230,255," + a + ")"; var s = (r() < 0.95 ? 0.8 : 1.6) * dpr; b.fillRect(r() * BG.width, r() * BG.height, s, s); }
  }
  function draw() {
    if (!active) return;
    var T0 = performance.now();
    if (!PART) build();
    if (!BG) background();
    var c = g2; c.setTransform(1, 0, 0, 1, 0, 0); c.clearRect(0, 0, cv.width, cv.height); c.drawImage(BG, 0, 0);
    c.setTransform(dpr, 0, 0, dpr, 0, 0);
    if (SIM) { drawSim(c); window.__galMs = performance.now() - T0; return; }
    setCam(); shown = []; lab = [];
    var fade = sstep(Math.log(900), Math.log(9000), Math.log(rad)), i, k, p, b;
    if (fade > 0.01) {
      c.globalCompositeOperation = "lighter";
      var cen = proj(0, 0, 0), sq = Math.max(0.18, st);
      [[46000, "120,140,210", 0.13], [11000, "255,200,140", 0.42], [3600, "255,236,200", 0.6]].forEach(function (gl) {
        var R = gl[0] * sc; if (R < 2) return;
        c.save(); c.translate(cen[0], cen[1]); c.scale(1, sq);
        var gr = c.createRadialGradient(0, 0, 0, 0, 0, R); gr.addColorStop(0, "rgba(" + gl[1] + "," + gl[2] * fade + ")"); gr.addColorStop(1, "rgba(" + gl[1] + ",0)");
        c.fillStyle = gr; c.beginPath(); c.arc(0, 0, R, 0, 2 * Math.PI); c.fill(); c.restore();
      });
      var size = Math.max(0.8, Math.min(1.7, sc * 160)), X = PART.x, Y = PART.y, Z = PART.z;
      for (b = 0; b < PART.buckets.length; b++) {
        var list = PART.buckets[b]; if (!list.length) continue;
        c.fillStyle = "rgba(" + COLS[Math.floor(b / 3)] + "," + (LEVELS[b % 3] * fade) + ")";
        var sz = Math.floor(b / 3) === 3 ? Math.min(2.2, size * 1.3) : size, h = sz / 2;
        for (k = 0; k < list.length; k++) {
          i = list[k]; var qx = X[i] - P0[0], qy = Y[i] - P0[1], qz = Z[i] - P0[2];
          var x1 = qx * cy0 - qy * sy0, y1 = qx * sy0 + qy * cy0, sx = cxs + x1 * sc, sy = cys - y1 * st * sc - qz * ct * sc;
          if (sx < -4 || sy < -4 || sx > W + 4 || sy > H + 4) continue;
          c.fillRect(sx - h, sy - h, sz, sz);
        }
      }
      c.globalCompositeOperation = "destination-out";   // dust lanes block the light behind them
      c.fillStyle = "rgba(0,0,0," + 0.16 * fade + ")";
      var ds = size * 2.4;
      for (i = 0; i < DUST.x.length; i++) { p = proj(DUST.x[i], DUST.y[i], DUST.z[i]); if (p[0] > -5 && p[1] > -5 && p[0] < W + 5 && p[1] < H + 5) c.fillRect(p[0] - ds / 2, p[1] - ds / 2, ds, ds); }
      bloom(c, fade);
      c.globalCompositeOperation = "source-over";
    }
    if (fade < 0.99) towardCenter(c, 1 - fade);
    mwLab = null;
    var fo = sstep(Math.log(150000), Math.log(700000), Math.log(rad));
    if (fo > 0.01) {
      c.globalCompositeOperation = "lighter";
      [[121.17, -21.57, 2537000, 110000, "255,215,170"], [133.61, -31.33, 2730000, 32000, "190,210,255"], [0, 0, -1, 55000, "200,215,255"]].forEach(function (G) {
        var cc = G[2] < 0 ? [0, 0, 0] : fromSun(lbDir(G[0], G[1]), G[2]), q = proj(cc[0], cc[1], cc[2]), R = G[3] * sc; if (R < 1) return;
        var gr = c.createRadialGradient(q[0], q[1], 0, q[0], q[1], R); gr.addColorStop(0, "rgba(" + G[4] + "," + 0.35 * fo + ")"); gr.addColorStop(1, "rgba(" + G[4] + ",0)");
        c.fillStyle = gr; c.beginPath(); c.arc(q[0], q[1], R, 0, 2 * Math.PI); c.fill();
      });
      for (b = 0; b < OTHER.buckets.length; b++) {
        var ol = OTHER.buckets[b]; if (!ol.length) continue;
        c.fillStyle = "rgba(" + COLS[Math.floor(b / 3)] + "," + (LEVELS[b % 3] * fo) + ")";
        for (k = 0; k < ol.length; k++) { i = ol[k]; p = proj(OTHER.x[i], OTHER.y[i], OTHER.z[i]); if (p[0] > -3 && p[1] > -3 && p[0] < W + 3 && p[1] < H + 3) c.fillRect(p[0] - 0.6, p[1] - 0.6, 1.2, 1.2); }
      }
      c.globalCompositeOperation = "source-over";
      if (rad > 600000) {   // the gap to Andromeda, for scale
        var A = proj(0, 0, 0), mB = fromSun(lbDir(121.17, -21.57), 2537000), B = proj(mB[0], mB[1], mB[2]);
        c.save(); c.globalAlpha = fo * 0.7; c.strokeStyle = "#c9cfe8"; c.setLineDash([2, 5]); c.lineWidth = 1;
        c.beginPath(); c.moveTo(A[0], A[1]); c.lineTo(B[0], B[1]); c.stroke(); c.restore();
        mwLab = { x: (A[0] + B[0]) / 2, y: (A[1] + B[1]) / 2 - 8, r: 0, t: "2.5 MILLION LIGHT-YEARS · CLOSING AT 110 KM/S", pri: -2.7, col: "rgba(201,207,232,.85)", center: true };
      }
    }
    var fw = sstep(Math.log(1.2e8), Math.log(1.2e9), Math.log(rad));
    if (fw > 0.01) cosmicWeb(c, fw);
    if (rad > 5e7 && rad < 5e9) laniakea(c, Math.min(sstep(Math.log(5e7), Math.log(1.5e8), Math.log(rad)), 1 - sstep(Math.log(1.5e9), Math.log(5e9), Math.log(rad))));
    if (rad > 3e9) universeEdge(c, sstep(Math.log(3e9), Math.log(2e10), Math.log(rad)));
    // where almost every known planet is
    ringLab = null;
    if (rad > 7000) {
      var ring = []; for (k = 0; k <= 72; k++) { var a = k / 72 * 2 * Math.PI; ring.push(proj(SUN[0] + Math.cos(a) * 3000, SUN[1] + Math.sin(a) * 3000, SUN[2])); }
      c.strokeStyle = "rgba(255,255,255,.45)"; c.setLineDash([3, 4]); c.lineWidth = 1; c.beginPath(); ring.forEach(function (q, n) { if (n) c.lineTo(q[0], q[1]); else c.moveTo(q[0], q[1]); }); c.stroke(); c.setLineDash([]);
      var low = ring.reduce(function (a, q) { return q[1] > a[1] ? q : a; }), rpx = 3000 * sc;
      ringLab = { x: low[0], y: low[1] + 12, r: 0, t: rpx > 40 ? "ALMOST EVERY KNOWN PLANET IS INSIDE THIS RING" : "◌ KNOWN PLANETS", pri: -2.5, col: "rgba(255,255,255,.75)", center: true };
    }
    drawLap(c);
    drawRadio(c);
    drawSystems(c);
    if (ringLab) lab.push(ringLab);
    if (mwLab) lab.push(mwLab);
    armLabels();
    drawMarks(c);
    drawAlerts(c);
    drawSun(c);
    labels(c);
    panel(); scaleBar();
    window.__galMs = performance.now() - T0;
  }
  function towardCenter(c, k) {   // up close the galaxy is too big to see, so show which way its bright middle lies
    var base = anchor || SUN, d = [CENTER[0] - base[0], CENTER[1] - base[1]], L = Math.hypot(d[0], d[1]) || 1;
    var S0 = proj(base[0], base[1], base[2]), F = proj(base[0] + d[0] / L * rad * 2.2, base[1] + d[1] / L * rad * 2.2, base[2]);
    var R = rad * 2.6 * sc;
    c.save(); c.globalCompositeOperation = "lighter";
    var gr = c.createRadialGradient(F[0], F[1], 0, F[0], F[1], R); gr.addColorStop(0, "rgba(255,200,150," + 0.16 * k + ")"); gr.addColorStop(1, "rgba(255,200,150,0)");
    c.fillStyle = gr; c.fillRect(0, 0, W, H); c.restore();
    var dx = F[0] - S0[0], dy = F[1] - S0[1], dl = Math.hypot(dx, dy); if (dl < 1) return;
    dx /= dl; dy /= dl;
    var m = Math.min(W, H) * 0.4, x = Math.max(120, Math.min(W - 120, S0[0] + dx * m)), y = Math.max(110, Math.min(H - 70, S0[1] + dy * m));
    c.globalAlpha = 0.75 * k; c.strokeStyle = "#ffcf9a"; c.fillStyle = "#ffcf9a"; c.lineWidth = 1.2;
    c.beginPath(); c.moveTo(x - dx * 22, y - dy * 22); c.lineTo(x, y); c.stroke();
    c.beginPath(); c.moveTo(x + dx * 6, y + dy * 6); c.lineTo(x - dx * 3 - dy * 4, y - dy * 3 + dx * 4); c.lineTo(x - dx * 3 + dy * 4, y - dy * 3 - dx * 4); c.fill();
    c.font = "600 10px ui-monospace, Consolas, monospace"; c.textAlign = dx > 0.3 ? "right" : dx < -0.3 ? "left" : "center";
    var tx = x + (dx > 0.3 ? -10 : dx < -0.3 ? 10 : 0), ty = y + (dy > 0 ? -12 : 18);
    c.fillText("TOWARD THE GALAXY'S CENTER · " + Math.round(L).toLocaleString() + " LY", tx, ty);
    c.globalAlpha = 1;
  }
  /* ---------- the Andromeda merger: a simplified simulation, played once (nothing runs after it ends) ---------- */
  // Each galaxy is a heavy core with a disk of star-dots that only feel the two cores' pull (the classic
  // Toomre-style setup). The cores slow each other down when close (dynamical friction), so they sink together.
  var SIM = null, TU = 4.5 / 258;   // one time unit in billions of years (first close pass at about 4.5 billion)
  function simStart() {
    var M1 = 1, M2 = 1.5, MT = M1 + M2, EPS = 0.25, r = rng(1977), g = function () { return (r() + r() + r() + r() - 2) * 0.87; };
    var nrm = function (v) { var l = Math.hypot(v[0], v[1], v[2]); return [v[0] / l, v[1] / l, v[2] / l]; };
    var cross = function (a, b) { return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]; };
    var disks = [[M1, 4200, 1.0, nrm([0, -0.5, 0.866])], [M2, 5200, 1.3, nrm([0.5, 0.35, -0.8])]];
    var N = disks[0][1] + disks[1][1], P = { x: new Float64Array(N), y: new Float64Array(N), z: new Float64Array(N), vx: new Float64Array(N), vy: new Float64Array(N), vz: new Float64Array(N),
      r: new Float64Array(N), th: new Float64Array(N), om: new Float64Array(N), who: new Uint8Array(N) };
    var k = 0, basis = [];
    disks.forEach(function (D, gi) {
      var n = D[3], e1 = nrm(cross(n, Math.abs(n[2]) < 0.9 ? [0, 0, 1] : [1, 0, 0])), e2 = cross(n, e1);
      basis.push([e1, e2]);
      for (var i = 0; i < D[1]; i++, k++) {
        var rr0 = gi === 0 && i === 0 ? 0.534 : 0.08 + D[2] * Math.sqrt(r()) * (r() < 0.25 ? 0.45 : 1);   // dot 0 is the Sun, 26,700 ly out
        P.r[k] = rr0; P.th[k] = r() * 2 * Math.PI; P.who[k] = gi;
        P.om[k] = Math.sqrt(D[0] / Math.pow(rr0 * rr0 + EPS * EPS, 1.5));
        P.x[k] = g() * 0.01;   // a little thickness, stored for later
      }
    });
    var keep = SIM && SIM.saved; SIM = { saved: keep, M1: M1, M2: M2, MT: MT, EPS: EPS, rel: [50, 0, 0], vrel: [0, 0.05, 0], t: 0, P: P, basis: basis, disks: disks, free: false, end: 430, run: true, zoom: 1, vr: 30, n1: disks[0][1] };
    flying = null; tipEl.hidden = true;
    if (!SIM.saved) SIM.saved = [yaw, tilt];
    yaw = 0; tilt = 58;   // side-on, so they come at each other across the screen
    var cd = document.getElementById("card"); if (cd) cd.hidden = true;
    var pn = $("gal-panel"); if (pn) pn.hidden = true;
    var o = $("gal-sim"); o.hidden = false;
    o.querySelector("#sim-pause").onclick = function () { SIM.run = !SIM.run; this.textContent = SIM.run ? "❚❚ pause" : "▶ play"; if (SIM.run) simLoop(); };
    o.querySelector("#sim-again").onclick = function () { simStart(); };
    o.querySelector("#sim-close").onclick = function () { simStop(); };
    o.querySelector("#sim-pause").textContent = "❚❚ pause";
    simLoop();
  }
  function simStop() {
    if (SIM && SIM.saved) { yaw = SIM.saved[0]; tilt = SIM.saved[1]; }
    SIM = null; var o = $("gal-sim"); if (o) o.hidden = true; var pn = $("gal-panel"); if (pn) pn.hidden = false; req();
  }
  window.__galSimJump = function (t) { if (!SIM) return; while (SIM.t < t) { var d = Math.hypot(SIM.rel[0], SIM.rel[1], SIM.rel[2]); simAdvance(!SIM.free && d > 8 ? 2.2 : 0.2); } SIM.vr = Math.max(3, d * 0.72 + 1.2); draw(); };   // for testing
  function simCores() {
    var S2 = SIM, c1 = [-S2.M2 / S2.MT * S2.rel[0], -S2.M2 / S2.MT * S2.rel[1], -S2.M2 / S2.MT * S2.rel[2]], c2 = [S2.M1 / S2.MT * S2.rel[0], S2.M1 / S2.MT * S2.rel[1], S2.M1 / S2.MT * S2.rel[2]];
    var v1 = [-S2.M2 / S2.MT * S2.vrel[0], -S2.M2 / S2.MT * S2.vrel[1], -S2.M2 / S2.MT * S2.vrel[2]], v2 = [S2.M1 / S2.MT * S2.vrel[0], S2.M1 / S2.MT * S2.vrel[1], S2.M1 / S2.MT * S2.vrel[2]];
    return [c1, c2, v1, v2];
  }
  function simStepCores(dt) {
    var S2 = SIM, r = S2.rel, v = S2.vrel, d = Math.hypot(r[0], r[1], r[2]), s3 = Math.pow(d * d + S2.EPS * S2.EPS, 1.5), rho = Math.exp(-d / 0.6) * 0.3;
    for (var i = 0; i < 3; i++) v[i] += (-S2.MT * r[i] / s3 - rho * v[i]) * dt;
    for (i = 0; i < 3; i++) r[i] += v[i] * dt;
  }
  function simRigid() {   // far apart: each disk just turns, carried along by its core
    var S2 = SIM, P = S2.P, C = simCores();
    for (var k = 0; k < P.r.length; k++) {
      var gi = P.who[k], B = S2.basis[gi], a = P.th[k] + P.om[k] * S2.t, ca = Math.cos(a), sa = Math.sin(a), rr0 = P.r[k], c = C[gi], v = C[gi + 2];
      var n = S2.disks[gi][3], hz = P.x[k] === undefined ? 0 : 0;
      P.x[k] = c[0] + (B[0][0] * ca + B[1][0] * sa) * rr0; P.y[k] = c[1] + (B[0][1] * ca + B[1][1] * sa) * rr0; P.z[k] = c[2] + (B[0][2] * ca + B[1][2] * sa) * rr0;
      var w = P.om[k] * rr0;
      P.vx[k] = v[0] + (-B[0][0] * sa + B[1][0] * ca) * w; P.vy[k] = v[1] + (-B[0][1] * sa + B[1][1] * ca) * w; P.vz[k] = v[2] + (-B[0][2] * sa + B[1][2] * ca) * w;
    }
  }
  function simAdvance(span) {
    var S2 = SIM, d = Math.hypot(S2.rel[0], S2.rel[1], S2.rel[2]);
    if (!S2.free && d > 8) {   // the long approach: big cheap steps
      var n = Math.ceil(span / 0.05); for (var i = 0; i < n; i++) simStepCores(span / n);
      S2.t += span; simRigid(); return;
    }
    if (!S2.free) { simRigid(); S2.free = true; }
    var P = S2.P, dt = 0.02, steps = Math.ceil(span / dt), e2 = S2.EPS * S2.EPS;
    for (var st2 = 0; st2 < steps; st2++) {
      simStepCores(dt);
      var C = simCores(), a = C[0], b = C[1], m1 = S2.M1, m2 = S2.M2;
      for (var k = 0; k < P.x.length; k++) {
        var dx = P.x[k] - a[0], dy = P.y[k] - a[1], dz = P.z[k] - a[2], q = dx * dx + dy * dy + dz * dz + e2, f1 = m1 / (q * Math.sqrt(q));
        var ex = P.x[k] - b[0], ey = P.y[k] - b[1], ez = P.z[k] - b[2], q2 = ex * ex + ey * ey + ez * ez + e2, f2 = m2 / (q2 * Math.sqrt(q2));
        P.vx[k] -= (dx * f1 + ex * f2) * dt; P.vy[k] -= (dy * f1 + ey * f2) * dt; P.vz[k] -= (dz * f1 + ez * f2) * dt;
        P.x[k] += P.vx[k] * dt; P.y[k] += P.vy[k] * dt; P.z[k] += P.vz[k] * dt;
      }
    }
    S2.t += steps * dt;
  }
  function simLoop() {
    if (!SIM || !SIM.run || !active) return;
    var d = Math.hypot(SIM.rel[0], SIM.rel[1], SIM.rel[2]);
    simAdvance(!SIM.free && d > 8 ? 2.2 : 0.2);
    draw();
    if (SIM && SIM.t < SIM.end) requestAnimationFrame(simLoop);
    else if (SIM) { SIM.run = false; var b = $("sim-pause"); if (b) b.textContent = "▶ play"; }
  }
  function simCaption(t) {
    return t < 200 ? "They drift toward each other for billions of years (sped up here)." : t < 250 ? "Andromeda grows until it fills Earth's night sky." :
      t < 272 ? "First pass: gravity pulls long tails of stars out of both galaxies." : t < 298 ? "They swing apart, slow down, and fall back together." :
      t < 345 ? "The second pass: the two centers sink into each other." : "One galaxy: a big, round elliptical, nicknamed Milkomeda. Its old black holes will meet in the middle.";
  }
  function drawSim(c) {
    var S2 = SIM, P = S2.P, C = simCores(), d = Math.hypot(S2.rel[0], S2.rel[1], S2.rel[2]);
    var want = Math.max(3, d * 0.72 + 1.2); S2.vr += (want - S2.vr) * 0.12;
    var scl = Math.min(W, H) * 0.46 / (S2.vr / S2.zoom), y0 = yaw * D2R, cyy = Math.cos(y0), syy = Math.sin(y0), ctl = Math.cos(tilt * D2R), stl = Math.sin(tilt * D2R), X0 = W * 0.56, Y0 = H * 0.5;
    var pj = function (x, y, z) { var x1 = x * cyy - y * syy, y1 = x * syy + y * cyy; return [X0 + x1 * scl, Y0 - y1 * stl * scl - z * ctl * scl]; };
    c.globalCompositeOperation = "lighter";
    [[C[0], "170,195,255", 1.0], [C[1], "255,214,170", 1.25]].forEach(function (G) {
      var q = pj(G[0][0], G[0][1], G[0][2]), R = Math.max(4, 0.22 * G[2] * scl);
      var gr = c.createRadialGradient(q[0], q[1], 0, q[0], q[1], R); gr.addColorStop(0, "rgba(" + G[1] + ",.7)"); gr.addColorStop(1, "rgba(" + G[1] + ",0)");
      c.fillStyle = gr; c.beginPath(); c.arc(q[0], q[1], R, 0, 2 * Math.PI); c.fill();
    });
    var sz = Math.max(0.9, Math.min(1.6, scl * 0.008));
    [[0, S2.n1, "rgba(150,180,255,.42)"], [S2.n1, P.x.length, "rgba(255,205,160,.38)"]].forEach(function (G) {
      c.fillStyle = G[2];
      for (var k = G[0]; k < G[1]; k++) { var q = pj(P.x[k], P.y[k], P.z[k]); if (q[0] > -2 && q[1] > -2 && q[0] < W + 2 && q[1] < H + 2) c.fillRect(q[0] - sz / 2, q[1] - sz / 2, sz, sz); }
    });
    bloom(c, 0.4);
    c.globalCompositeOperation = "source-over";
    var sp = pj(P.x[0], P.y[0], P.z[0]);   // the Sun
    c.fillStyle = "#ffd76a"; c.beginPath(); c.arc(sp[0], sp[1], 3, 0, 2 * Math.PI); c.fill();
    c.font = "700 10px ui-monospace, Consolas, monospace"; c.textAlign = "left"; c.fillStyle = "#ffd76a"; c.fillText("THE SUN", sp[0] + 7, sp[1] - 6);
    if (S2.t < 300) {
      var a1 = pj(C[0][0], C[0][1], C[0][2]), a2 = pj(C[1][0], C[1][1], C[1][2]);
      c.font = "600 11px ui-monospace, Consolas, monospace"; c.textAlign = "center";
      c.fillStyle = "rgba(190,210,255,.9)"; c.fillText("MILKY WAY", a1[0], a1[1] + Math.max(22, 0.55 * scl));
      c.fillStyle = "rgba(255,214,170,.9)"; c.fillText("ANDROMEDA", a2[0], a2[1] + Math.max(22, 0.7 * scl));
    }
    var o = $("gal-sim"); if (o) {
      o.querySelector(".sim-t").textContent = "+" + (S2.t * TU).toFixed(1) + " billion years";
      o.querySelector(".sim-c").textContent = simCaption(S2.t);
      o.querySelector(".sim-sep").textContent = d > 0.3 ? "centers " + Math.round(d * 50000).toLocaleString() + " light-years apart" : "centers merged";
    }
  }
  /* ---------- the largest scales ---------- */
  var WEB = null, OBS = 46.5e9;
  function buildWeb() {   // an illustration of the cosmic web: knots joined by threads, with voids between
    var r = rng(77), g = function () { return (r() + r() + r() + r() - 2) * 0.87; }, x = [], y = [], z = [], nodeX = [], nodeY = [], nodeZ = [];
    var place = function (n, R, rmin, out) {
      for (var i = 0; i < n; i++) { var u = r() * 2 - 1, a = r() * 2 * Math.PI, rr = R * Math.cbrt(r()); if (rr < rmin) { i--; continue; } var cc = Math.sqrt(1 - u * u); out.push([cc * Math.cos(a) * rr, cc * Math.sin(a) * rr, u * rr]); }
      return out;
    };
    [[place(240, 1.6e9, 6e7, []), 3, 14, 0.05], [place(650, 4.4e10, 1.6e9, []), 2, 12, 0.04]].forEach(function (set) {
      var N = set[0];
      N.forEach(function (n, i) {
        for (var q = 0; q < 14; q++) { x.push(n[0] + g() * 2e7 * (i % 3 + 1) * (set[1] === 2 ? 8 : 1)); y.push(n[1] + g() * 2e7 * (i % 3 + 1) * (set[1] === 2 ? 8 : 1)); z.push(n[2] + g() * 2e7 * (set[1] === 2 ? 8 : 1)); nodeX.push(1); }
        var d = N.map(function (m, j) { return [j, Math.hypot(m[0] - n[0], m[1] - n[1], m[2] - n[2])]; }).sort(function (a, b) { return a[1] - b[1]; }).slice(1, 1 + set[1]);
        d.forEach(function (e) {
          var m = N[e[0]];
          for (var k = 0; k < set[2]; k++) { var t = r(), j = e[1] * set[3]; x.push(n[0] + (m[0] - n[0]) * t + g() * j); y.push(n[1] + (m[1] - n[1]) * t + g() * j); z.push(n[2] + (m[2] - n[2]) * t + g() * j); nodeX.push(0); }
        });
      });
    });
    WEB = { x: new Float64Array(x), y: new Float64Array(y), z: new Float64Array(z), knot: nodeX };
  }
  function cosmicWeb(c, f) {
    if (!WEB) buildWeb();
    c.save(); c.globalCompositeOperation = "lighter";
    for (var pass = 0; pass < 2; pass++) {
      c.fillStyle = pass ? "rgba(255,214,190," + 0.38 * f + ")" : "rgba(150,165,255," + 0.32 * f + ")";
      for (var i = 0; i < WEB.x.length; i++) {
        if (WEB.knot[i] !== pass) continue;
        var p = proj(WEB.x[i], WEB.y[i], WEB.z[i]); if (p[0] < -2 || p[1] < -2 || p[0] > W + 2 || p[1] > H + 2) continue;
        c.fillRect(p[0] - 0.7, p[1] - 0.7, pass ? 1.6 : 1.2, pass ? 1.6 : 1.2);
      }
    }
    c.restore();
    if (rad > 1.5e9 && rad < 2.5e10) lab.push({ x: W * 0.5, y: H - 92, r: 0, t: "THE COSMIC WEB (DRAWN AS AN ILLUSTRATION: THE REAL PATTERN IS MAPPED BY GALAXY SURVEYS)", pri: -2.6, col: "rgba(170,180,255,.75)", center: true });
  }
  function laniakea(c, f) {
    if (f <= 0.01) return;
    var cen = fromSun(lbDir(307, 9), 2.5e8), q = proj(cen[0], cen[1], cen[2]), R = 2.6e8 * sc;
    c.save(); c.globalAlpha = 0.75 * f; c.strokeStyle = "#ffb3a0"; c.setLineDash([3, 6]); c.lineWidth = 1.2;
    c.beginPath(); c.ellipse(q[0], q[1], R, R * Math.max(0.35, st), 0, 0, 2 * Math.PI); c.stroke(); c.restore();
    lab.push({ x: q[0], y: q[1] + R * Math.max(0.35, st) + 14, r: 0, t: "LANIAKEA SUPERCLUSTER · OUR HOME · ABOUT 100,000 GALAXIES, 520 MILLION LIGHT-YEARS ACROSS", pri: -2.75, col: "rgba(255,190,170,.9)", center: true });
  }
  function universeEdge(c, f) {
    var q = proj(0, 0, 0), R = OBS * sc;
    c.save(); c.globalCompositeOperation = "lighter";
    var gr = c.createRadialGradient(q[0], q[1], R * 0.9, q[0], q[1], R * 1.04);
    gr.addColorStop(0, "rgba(255,120,80,0)"); gr.addColorStop(0.65, "rgba(255,130,80," + 0.22 * f + ")"); gr.addColorStop(0.85, "rgba(255,190,140," + 0.42 * f + ")"); gr.addColorStop(1, "rgba(255,190,140,0)");
    c.fillStyle = gr; c.beginPath(); c.arc(q[0], q[1], R * 1.05, 0, 2 * Math.PI); c.fill();
    var r = rng(9);   // speckles like the microwave background's tiny hot and cold spots
    for (var i = 0; i < 900; i++) { var a = r() * 2 * Math.PI, d = R * (0.955 + r() * 0.05); c.fillStyle = r() < 0.5 ? "rgba(255,150,90," + 0.5 * f + ")" : "rgba(120,170,255," + 0.35 * f + ")"; c.fillRect(q[0] + Math.cos(a) * d, q[1] + Math.sin(a) * d, 1.4, 1.4); }
    c.restore();
    lab.push({ x: q[0], y: q[1] - R - 12, r: 0, t: "EDGE OF THE OBSERVABLE UNIVERSE · 46.5 BILLION LIGHT-YEARS AWAY IN EVERY DIRECTION", pri: -2.95, col: "rgba(255,200,160,.95)", center: true });
    lab.push({ x: q[0], y: q[1] + R + 22, r: 0, t: "THE GLOW: THE COSMIC MICROWAVE BACKGROUND, LIGHT FROM 380,000 YEARS AFTER THE BIG BANG", pri: -2.94, col: "rgba(255,200,160,.8)", center: true });
  }
  var OFF = null;
  function bloom(c, fade) {   // a soft glow: shrink the picture, then lay it back over itself, blurred
    if (!OFF) OFF = document.createElement("canvas");
    var w = Math.max(1, Math.round(cv.width / 6)), h = Math.max(1, Math.round(cv.height / 6));
    if (OFF.width !== w || OFF.height !== h) { OFF.width = w; OFF.height = h; }
    var o = OFF.getContext("2d"); o.clearRect(0, 0, w, h); o.drawImage(cv, 0, 0, w, h);
    c.save(); c.setTransform(1, 0, 0, 1, 0, 0); c.globalCompositeOperation = "lighter"; c.globalAlpha = 0.7 * fade;
    c.imageSmoothingEnabled = true; c.drawImage(OFF, 0, 0, cv.width, cv.height); c.restore();
  }
  function armLabels() {
    if (rad < 9000) return;
    [[0, 38000], [1, 29000], [2, 21000], [3, 47000]].forEach(function (a) { var q = armPoint(a[1], a[0]), s = proj(q[0], q[1], 0); lab.push({ x: s[0], y: s[1], r: 0, t: ARMS[a[0]][0], pri: -3, col: "rgba(200,215,255,.6)", center: true }); });
    if (rad < 40000) { var o = lbDir(78, 0), s2 = proj(SUN[0] + o[0] * 6500, SUN[1] + o[1] * 6500, 0); lab.push({ x: s2[0], y: s2[1], r: 0, t: "ORION SPUR (OUR ARM)", pri: -3, col: "rgba(200,215,255,.6)", center: true }); }
  }
  var lab = [], ringLab = null, mwLab = null;
  function drawSystems(c) {
    var near = rad < 2000, base = rad < 150 ? 2.2 : rad < 3000 ? 1.6 : 1.1;
    systems.forEach(function (s, idx) {
      if (filter === "temperate" && !s.hab) return;
      if (filter === "famous" && !s.about) return;
      if (filter === "webb" && !s.webb) return;
      var g = sysPos(s), q = proj(g[0], g[1], g[2]);
      if (q[0] < -10 || q[1] < -10 || q[0] > W + 10 || q[1] > H + 10) return;
      var col = teffCol(s.t, s.sp);
      if (rad > 15000) {   // from far out they are one bright patch around the Sun; only far famous ones get names
        c.fillStyle = col; c.globalAlpha = 0.8; c.fillRect(q[0] - 0.8, q[1] - 0.8, 1.6, 1.6); c.globalAlpha = 1;
        if (s.about && s.ly > 3000) { shown.push({ x: q[0], y: q[1], r: 6, tip: "<b>" + esc(s.h) + "</b><span>" + fmtLy(s.ly) + "</span>", open: function () { openSys(s); } }); lab.push({ x: q[0], y: q[1], r: 2, t: s.h, pri: 1, col: "rgba(235,240,255,.9)" }); }
        return;
      }
      var r = base + Math.min(2.2, (s.p.length - 1) * 0.45) + (s.about ? 0.6 : 0);
      if (near) { var gl = c.createRadialGradient(q[0], q[1], 0, q[0], q[1], r * 4); gl.addColorStop(0, col); gl.addColorStop(1, "rgba(0,0,0,0)"); c.globalAlpha = 0.35; c.fillStyle = gl; c.beginPath(); c.arc(q[0], q[1], r * 4, 0, 2 * Math.PI); c.fill(); c.globalAlpha = 1; }
      c.fillStyle = col; c.beginPath(); c.arc(q[0], q[1], r, 0, 2 * Math.PI); c.fill();
      if (s.hab) { c.strokeStyle = "rgba(90,230,160,.9)"; c.lineWidth = 1; c.beginPath(); c.arc(q[0], q[1], r + 2.5, 0, 2 * Math.PI); c.stroke(); }
      if (s.webb) { c.strokeStyle = "rgba(255,200,90,.95)"; c.lineWidth = 1; var wq = r + 4.5; c.beginPath(); c.moveTo(q[0], q[1] - wq); c.lineTo(q[0] + wq, q[1]); c.lineTo(q[0], q[1] + wq); c.lineTo(q[0] - wq, q[1]); c.closePath(); c.stroke(); }
      if (LAYERS.radio && s.ly <= radioR() && rad < 6000) { c.fillStyle = "rgba(120,220,255,.9)"; c.fillRect(q[0] + r + 1, q[1] - r - 3, 2, 2); }
      shown.push({ x: q[0], y: q[1], r: r + 4, tip: "<b>" + esc(s.h) + "</b><span>" + s.p.length + " planet" + (s.p.length > 1 ? "s" : "") + " · " + fmtLy(s.ly) + (s.hab ? " · has a temperate planet" : "") + (s.webb ? " · Webb has studied its air" : "") + "</span>", open: function () { openSys(s); } });
      lab.push({ x: q[0], y: q[1], r: r, t: s.h, pri: (s.about ? 0 : 2) + (s.hab ? -0.5 : 0) + s.ly / 1e6, col: "rgba(235,240,255,.9)" });
    });
  }
  function drawMarks(c) {
    MARKS.forEach(function (m) {
      var g = m[4] === "core" ? [0, 0, 0] : fromSun(lbDir(m[1], m[2]), m[3]), q = proj(g[0], g[1], g[2]);
      if (q[0] < -20 || q[1] < -20 || q[0] > W + 20 || q[1] > H + 20) return;
      if (m[4] !== "core" && m[4] !== "galaxy" && m[4] !== "dwarf" && m[4] !== "spiral" && m[3] * sc < 0.02 && rad > 30000) return;   // too small to matter that far out
      if ((m[4] === "dwarf" || m[4] === "spiral") && rad < 90000 && m[3] > 100000) return;
      if (m[4] === "blackhole" && rad > 22000) return;   // up close only; from outside the galaxy they would sit on top of the Sun
      if (m[4] === "dwarf" && rad > 1200000 && m[3] < 1000000) return;   // the little ones around us blur into our galaxy
      var big = m[4] === "galgroup" || m[4] === "galcluster" || m[4] === "supercluster";
      if (big && (rad < m[3] * 0.08 || rad > m[3] * 60)) return;
      if (!big && m[4] !== "core" && rad > 6000000 && !(m[4] === "spiral" && rad < 3e7)) return;
      c.save(); c.translate(q[0], q[1]);
      var R = big ? Math.max(5, (m[7] || 1e7) * 0.5 * sc) : m[4] === "galaxy" ? Math.max(6, 12000 * sc) : m[4] === "dwarf" ? Math.max(3, (m[7] || 3000) * 0.6 * sc) : m[4] === "spiral" ? Math.max(8, (m[7] || 1e5) * 0.5 * sc) : m[4] === "nebula" ? 9 : 6;
      if (m[4] === "nebula" || m[4] === "galaxy" || m[4] === "dwarf" || big) {
        var gr = c.createRadialGradient(0, 0, 0, 0, 0, R * 1.6); gr.addColorStop(0, m[5]); gr.addColorStop(1, "rgba(0,0,0,0)");
        c.globalCompositeOperation = "lighter"; c.globalAlpha = 0.55; c.fillStyle = gr; c.beginPath(); c.arc(0, 0, R * 1.6, 0, 2 * Math.PI); c.fill(); c.globalAlpha = 1; c.globalCompositeOperation = "source-over";
      }
      c.strokeStyle = m[5]; c.fillStyle = m[5]; c.lineWidth = 1.2;
      if (m[4] === "cluster" || m[4] === "globular") { for (var k = 0; k < 7; k++) { var a = k * 2.4, d = 2 + (k % 3) * 2; c.fillRect(Math.cos(a) * d - 1, Math.sin(a) * d - 1, 2, 2); } }
      else if (m[4] === "remnant") { c.beginPath(); c.arc(0, 0, 5, 0, 2 * Math.PI); c.stroke(); c.beginPath(); c.arc(0, 0, 1.5, 0, 2 * Math.PI); c.fill(); }
      else if (m[4] === "blackhole" || m[4] === "core") { c.fillStyle = "#000"; c.beginPath(); c.arc(0, 0, 4, 0, 2 * Math.PI); c.fill(); c.beginPath(); c.arc(0, 0, 6.5, 0, 2 * Math.PI); c.stroke(); }
      else if (m[4] === "star") { c.beginPath(); c.arc(0, 0, 2.6, 0, 2 * Math.PI); c.fill(); c.beginPath(); c.moveTo(-7, 0); c.lineTo(7, 0); c.moveTo(0, -7); c.lineTo(0, 7); c.globalAlpha = 0.6; c.stroke(); c.globalAlpha = 1; }
      else if (big) { for (var k3 = 0; k3 < 9; k3++) { var a3 = k3 * 2.39, d3 = (0.2 + (k3 % 4) * 0.2) * Math.min(R, 26); c.fillRect(Math.cos(a3) * d3 - 1, Math.sin(a3) * d3 - 1, 2, 2); } }
      else if (m[4] !== "galaxy" && m[4] !== "dwarf" && m[4] !== "spiral") { c.beginPath(); c.arc(0, 0, 2, 0, 2 * Math.PI); c.fill(); }
      c.restore();
      shown.push({ x: q[0], y: q[1], r: Math.max(9, R), tip: "<b>" + esc(m[0]) + "</b><span>" + esc(kindName(m[4])) + " · " + fmtLy(m[4] === "core" ? R0 : m[3]) + "</span>", open: function () { openMark(m); } });
      if (m[4] === "spiral") lab.push({ x: q[0], y: q[1] + Math.max(14, (m[7] || 1e5) * 0.32 * sc * Math.max(0.35, st)) + 6, r: 0, t: m[0], pri: -2.8, col: m[5], center: true });
      else lab.push({ x: q[0], y: q[1], r: R, t: m[0], pri: m[4] === "spiral" ? -2.8 : m[4] === "core" || m[4] === "galaxy" ? -2 : m[4] === "dwarf" ? -0.5 : -1, col: m[5], big: true });
    });
  }
  function kindName(k) { return { galgroup: "group of galaxies", galcluster: "cluster of galaxies", supercluster: "supercluster of galaxies", spiral: "spiral galaxy", dwarf: "dwarf galaxy", nebula: "star nursery (nebula)", cluster: "star cluster", remnant: "what's left of a dead star", star: "star", blackhole: "black hole", globular: "globular star cluster", core: "the galaxy's central black hole", galaxy: "neighbor galaxy" }[k] || k; }
  function drawSun(c) {
    var q = proj(SUN[0], SUN[1], SUN[2]);
    c.fillStyle = "#ffd76a"; c.beginPath(); c.arc(q[0], q[1], 3.5, 0, 2 * Math.PI); c.fill();
    c.strokeStyle = "#ffd76a"; c.lineWidth = 1.2; c.beginPath(); c.arc(q[0], q[1], 8, 0, 2 * Math.PI); c.stroke();
    c.beginPath(); c.moveTo(q[0] + 8, q[1] - 8); c.lineTo(q[0] + 18, q[1] - 18); c.stroke();
    c.font = "700 11px ui-monospace, Consolas, monospace"; c.textAlign = "left"; c.fillStyle = "#ffd76a";
    c.fillText(rad < 40 ? "THE SUN" : rad > 400000 ? "MILKY WAY · YOU ARE HERE" : "SUN · YOU ARE HERE", q[0] + 21, q[1] - 20);
    shown.push({ x: q[0], y: q[1], r: 10, tip: "<b>The Sun</b><span>you are here · click to go back to the solar system</span>", open: function () { exit(); } });
    used = [[q[0] - 12, q[1] - 32, q[0] + 150, q[1] + 10]];
    var hr = root.getBoundingClientRect();
    ["gal-panel", "gal-q", "card"].forEach(function (id) {   // keep names out from under the panels
      var n = document.getElementById(id); if (!n || n.hidden) return; if (id === "gal-q") n = n.parentNode;
      var r = n.getBoundingClientRect(); if (r.width) used.push([r.left - hr.left - 4, r.top - hr.top - 4, r.right - hr.left + 4, r.bottom - hr.top + 4]);
    });
  }
  var used = [];
  function labels(c) {
    var n = 0, max = rad < 100 ? 30 : 26;
    lab.sort(function (a, b) { return a.pri - b.pri; }).forEach(function (L) {
      if (n >= max) return;
      c.font = (L.big || L.center ? "600 11px " : "10px ") + "ui-monospace, Consolas, monospace";
      var w = c.measureText(L.t).width, x = L.center ? L.x - w / 2 : L.x + L.r + 5, y = L.y + 4;
      var box = [x - 2, y - 10, x + w + 2, y + 3];
      if (box[2] > W - 8 && !L.center) { x = L.x - L.r - 5 - w; box = [x - 2, y - 10, x + w + 2, y + 3]; }
      if (box[0] < 4 || box[1] < 50 || box[3] > H - 40) return;
      if (used.some(function (u) { return box[0] < u[2] && box[2] > u[0] && box[1] < u[3] && box[3] > u[1]; })) return;
      used.push(box); n++;
      c.font = (L.big || L.center ? "600 11px " : "10px ") + "ui-monospace, Consolas, monospace";
      c.textAlign = "left"; c.lineWidth = 3; c.strokeStyle = "rgba(3,4,12,.85)"; c.strokeText(L.t, x, y); c.fillStyle = L.col; c.fillText(L.t, x, y);
    });
  }
  function hit(x, y) {
    var best = null, bd = 1e9;
    shown.forEach(function (s) { var d = Math.hypot(s.x - x, s.y - y); if (d < Math.max(8, s.r) && d < bd) { bd = d; best = s; } });
    return best;
  }
  function viewName() { if (anchor && !camF && Math.hypot(anchor[0], anchor[1], anchor[2]) > 80000) return rad < 600000 ? "another galaxy, millions of light-years from ours" : "the Local Group"; return rad < 30 ? "the nearest stars" : rad < 400 ? "our stellar neighborhood" : rad < 5000 ? "the Orion Spur, our little arm of the galaxy" : rad < 90000 ? "the Milky Way, seen from outside" : rad < 500000 ? "the Milky Way and the small galaxies circling it" : rad > 2e10 ? "the whole observable universe: everything whose light has had time to reach us since the Big Bang" : rad > 1.5e9 ? "the cosmic web: galaxies strung along threads around huge empty voids" : rad > 1.2e8 ? "Laniakea, our supercluster: about 100,000 galaxies" : rad > 6e6 ? "nearby groups and clusters of galaxies" : "the Local Group: our galaxy, Andromeda, Triangulum and about 80 small galaxies, 10 million light-years across"; }
  function panel() {
    var el = $("gal-panel"); if (!el) return;
    var nP = systems.reduce(function (a, s) { return a + s.p.length; }, 0), nT = systems.filter(function (s) { return s.hab; }).length;
    el.innerHTML = '<div class="h"><i class="dot"></i>MILKY WAY</div>' +
      '<div class="gal-row"><b>Looking at</b><span>' + esc(viewName()) + "</span></div>" +
      '<div class="gal-row"><b>' + nP.toLocaleString() + " planets around " + systems.length.toLocaleString() + " stars</b><span>" + (catalogAt ? "every confirmed planet, NASA Exoplanet Archive · updated " + ctx.ago(Math.round((Date.now() / 1000 - catalogAt) / 60)) : "Archie's built-in famous systems; the full NASA catalog (6,000+ planets) downloads the first time Archie is online") + "</span></div>" +
      '<div class="gal-row"><b>The galaxy</b><span>about 100,000 light-years across, 100–400 billion stars. The Sun is 26,700 light-years from the middle and takes 230 million years to go around once.</span></div>' +
      '<div class="gal-filt"><button data-f="all" class="' + (filter === "all" ? "on" : "") + '">all systems</button><button data-f="temperate" class="' + (filter === "temperate" ? "on" : "") + '">temperate · ' + nT + '</button><button data-f="famous" class="' + (filter === "famous" ? "on" : "") + '">famous</button><button data-f="webb" class="' + (filter === "webb" ? "on" : "") + '">Webb · ' + systems.filter(function (s) { return s.webb; }).length + '</button></div>' +
      '<div class="gal-filt gal-lay"><span>show</span>' + [["radio", "radio bubble"], ["lap", "Sun's lap"], ["alerts", "live alerts"]].map(function (L) { return '<button data-l="' + L[0] + '" class="' + (LAYERS[L[0]] ? "on" : "") + '">' + L[1] + "</button>"; }).join("") + "</div>" +
      alertsRow() +
      '<div class="gal-key"><span><i style="background:#ff8a5c"></i>red dwarf</span><span><i style="background:#ffb36b"></i>orange</span><span><i style="background:#fff1c9"></i>Sun-like</span><span><i style="background:#a9c6ff"></i>hot blue-white</span><span><i class="ring"></i>has a temperate planet</span><span><i class="dia"></i>Webb studied its air</span></div>';
    el.querySelectorAll(".gal-filt button[data-f]").forEach(function (b) { b.onclick = function () { filter = b.dataset.f; req(); }; });
    el.querySelectorAll(".gal-lay button").forEach(function (b) { b.onclick = function () { setLayer(b.dataset.l, !LAYERS[b.dataset.l]); }; });
    el.querySelectorAll("[data-al]").forEach(function (b) { b.onclick = function () { var a = alertList()[+b.dataset.al]; if (a) openAlert(a); }; });
  }
  function alertsRow() {
    if (!LAYERS.alerts) return "";
    var L = alertList(); if (!L.length) return COSMIC ? '<div class="gal-row"><b>Live alerts</b><span>none right now</span></div>' : "";
    var n = { sn: 0, grb: 0, gw: 0 }; L.forEach(function (a) { n[a.kind]++; });
    var recent = L.map(function (a, i) { return [a, i]; }).sort(function (x, y) { return String(y[0].t || y[0].last || "").localeCompare(String(x[0].t || x[0].last || "")); }).slice(0, 3);
    return '<div class="gal-row"><b>Live alerts</b><span>' + [n.sn ? n.sn + " supernova" + (n.sn > 1 ? "e" : "") : "", n.grb ? n.grb + " gamma-ray burst" + (n.grb > 1 ? "s" : "") : "", n.gw ? n.gw + " black-hole or neutron-star collision" + (n.gw > 1 ? "s" : "") : ""].filter(Boolean).join(" · ") +
      '</span><span class="gal-al">' + recent.map(function (r) { return '<button data-al="' + r[1] + '" style="color:' + AK[r[0].kind][0] + '">' + esc(r[0].name) + "</button>"; }).join("") + "</span></div>";
  }
  function scaleBar() {
    var el = $("gal-scale"); if (!el) return;
    var target = 140 / sc, pow = Math.pow(10, Math.floor(Math.log10(target))), L = [1, 2, 5, 10].map(function (m) { return m * pow; }).filter(function (v) { return v <= target; }).pop() || pow;
    var words = function (v) { return v >= 1e9 ? (v / 1e9) + " billion" : v >= 1e6 ? (v / 1e6) + " million" : v.toLocaleString(); };
    el.innerHTML = '<div class="gal-bar-line" style="width:' + Math.round(L * sc) + 'px"></div><span>' + words(L) + " light-year" + (L === 1 ? "" : "s") + " · light takes " + (L === 1 ? "a year" : words(L) + " years") + " to cross it" + (rad > 5e8 ? " (space stretches on the way, so it's not quite that simple out here)" : "") + "</span>" + '<span class="gal-past">◷ ' + esc(pastLine()) + "</span>";
  }

  /* ---------- cards ---------- */
  function ptype(p) {
    var R = p[3] != null ? p[3] : p[4] != null ? estR(p[4]) : null;
    if (R == null) return "size unknown";
    return R < 1.25 ? "rocky, Earth-size" : R < 2 ? "super-Earth" : R < 4 ? "mini-Neptune" : R < 8 ? "Neptune-like" : "gas giant";
  }
  function fmtYear(d) { return d == null ? "—" : d < 2 ? Math.round(d * 24) + " hours" : d < 700 ? (d < 20 ? d.toFixed(1) : Math.round(d)) + " days" : (d / 365.25).toFixed(d < 3650 ? 1 : 0) + " years"; }
  function fmtTemp(k) { if (k == null) return "—"; var c = Math.round(k - 273); return (c > 0 ? "about " + c.toLocaleString() : "about −" + Math.abs(c).toLocaleString()) + " °C"; }
  function starKind(s) {
    var sp = s.sp || "", t = s.t;
    if (/pulsar|PSR/i.test(sp) || /^PSR/.test(s.h)) return "pulsar (the spinning core of an exploded star)";
    if (/^D/.test(sp)) return "white dwarf (a dead star's leftover core)";
    if (/III|II\b/.test(sp)) return "giant star";
    if (!t) return "star";
    return t < 3900 ? "red dwarf, smaller and cooler than the Sun" : t < 5300 ? "orange dwarf, a bit smaller and cooler than the Sun" : t < 6000 ? "yellow star, like the Sun" : t < 7500 ? "yellow-white star, hotter than the Sun" : "hot white or blue-white star";
  }
  function openSys(s, go) {
    if (go) { var g = sysPos(s); flyTo(g, Math.max(14, Math.min(4000, s.ly * 0.35))); }
    var yr = new Date().getFullYear(), years = s.ly * LY_KM / 17 / YEAR_S;
    var light = s.ly < yr ? "left around " + Math.round(yr - s.ly) : "left " + Math.round(s.ly).toLocaleString() + " years ago, around " + Math.round(s.ly - yr + 1).toLocaleString() + " BC";
    var rows = s.p.map(function (p) {
      var R = p[3] != null ? p[3] : null, M = p[4];
      var size = R != null ? (R < 4 ? R.toFixed(2) + "× Earth's width" : (R / 11.2).toFixed(2) + "× Jupiter's width") : M != null ? "at least " + (M < 50 ? M.toFixed(1) + " Earths of mass" : (M / 317.8).toFixed(2) + " Jupiters of mass") : "size unknown";
      return '<div class="gal-pl' + (temperate(p) ? " hab" : "") + '"><b>' + esc(p[0]) + "</b><span>" + esc(ptype(p)) + (temperate(p) ? " · <em>temperate</em>" : "") + "</span>" +
        "<i>" + esc(size) + " · year " + esc(fmtYear(p[1])) + " · " + esc(fmtTemp(p[5])) + (p[7] ? " · found " + p[7] + (p[8] ? " (" + esc(String(p[8]).toLowerCase()) + ")" : "") : "") + "</i>" +
        (WEBB[norm(p[0])] ? '<i class="gal-webb">◇ Webb: ' + esc(WEBB[norm(p[0])]) + "</i>" : "") + "</div>";
    }).join("");
    var about = s.about || ("A " + starKind(s).split(",")[0] + " with " + s.p.length + " known planet" + (s.p.length > 1 ? "s" : "") + ". " + (s.p[0] && s.p[0][9] ? "Found by " + s.p[0][9] + "." : ""));
    rich({
      hash: "system=" + ctx.slug(s.h), color: teffCol(s.t, s.sp), title: s.h.toUpperCase(), badge: s.p.length > 1 ? s.p.length + "-PLANET SYSTEM" : "PLANET SYSTEM", badgeColor: teffCol(s.t, s.sp),
      sub: starKind(s),
      boxes: [["Distance", (s.ly < 100 ? s.ly.toFixed(1) : Math.round(s.ly).toLocaleString()) + " ly", "var(--fg)"], ["Planets", String(s.p.length), "var(--fg)"], ["Star", s.t ? Math.round(s.t).toLocaleString() + " K" : s.sp || "—", teffCol(s.t, s.sp)]],
      sections: [["About", '<div class="rc-note" style="color:var(--fg)">' + esc(about) + "</div>"],
        [null, '<div id="gal-mini" class="gal-mini"></div>'],
        ["Planets", rows],
        ["Getting there", '<div class="rc-note" style="color:var(--fg)">The light you would see from this star ' + esc(light) + ". At Voyager 1's speed (17 km/s) the trip would take about " + Math.round(years).toLocaleString() + " years." + esc(radioLine(s)) + "</div>"],
        [null, '<div class="rc-note">' + (s.t ? "Star: " + (s.sp ? esc(s.sp) + ", " : "") + Math.round(s.t) + " K" + (s.r ? ", " + s.r + "× the Sun's width" : "") + (s.age ? ", about " + s.age + " billion years old" : "") + ". " : "") + "Temperatures are for a bare planet with no air; a thick atmosphere can make it far hotter. \"Temperate\" means it gets about the warmth that would let water stay liquid, not that anything lives there." + (catalogAt ? " From NASA's Exoplanet Archive." : " From Archie's built-in list.") + "</div>"]],
      actions: [["center on it", function () { var g = sysPos(s); flyTo(g, Math.max(14, Math.min(4000, s.ly * 0.35))); }], ["★ the sky from here", function () { skyFrom(s); }]],
      explain: { title: s.h, names: [s.h + " (star)", s.p[0] ? s.p[0][0] : s.h], kind: "star system" },
      after: function () { mini(s); }
    });
  }
  function mini(s) {   // the system from above: orbits on a squeezed scale, planets sized by width, temperate ones green
    var box = document.getElementById("gal-mini"); if (!box) return;
    var w = box.clientWidth || 300, h = 120, maxA = Math.max.apply(null, s.p.map(function (p) { return p[2] || 0.05; }).concat([0.05]));
    var sv = d3.select(box).append("svg").attr("width", w).attr("height", h), cx = w / 2, cy = h / 2;
    var rs = function (a) { return 14 + (Math.log(1 + (a || 0.05) / maxA * 20) / Math.log(21)) * (w / 2 - 24); };
    sv.append("circle").attr("cx", cx).attr("cy", cy).attr("r", 5).attr("fill", teffCol(s.t, s.sp));
    s.p.forEach(function (p, i) {
      var r = rs(p[2]), ang = (i * 2.399) % (2 * Math.PI);
      sv.append("ellipse").attr("cx", cx).attr("cy", cy).attr("rx", r).attr("ry", r * 0.42).attr("fill", "none").attr("stroke", temperate(p) ? "#5ae6a0" : "rgba(255,255,255,.3)");
      var R = p[3] != null ? p[3] : p[4] != null ? estR(p[4]) : 1, pr = Math.max(1.6, Math.min(6, 1.4 + Math.log(1 + R) * 1.6));
      sv.append("circle").attr("cx", cx + Math.cos(ang) * r).attr("cy", cy + Math.sin(ang) * r * 0.42).attr("r", pr).attr("fill", temperate(p) ? "#5ae6a0" : "#d8dde8").append("title").text(p[0]);
    });
    sv.append("text").attr("x", 6).attr("y", h - 6).attr("class", "gal-mini-lab").text("orbits squeezed to fit · green = temperate");
  }
  function openMark(m, go) {
    var g = m[4] === "core" ? [0, 0, 0] : fromSun(lbDir(m[1], m[2]), m[3]);
    var near = /^(galgroup|galcluster|supercluster)$/.test(m[4]) ? Math.max(m[7] * 2, m[3] * 0.25) : m[4] === "spiral" ? Math.max(90000, (m[7] || 1e5) * 1.1) : m[4] === "dwarf" ? Math.max(15000, (m[7] || 3000) * 4) : m[4] === "galaxy" ? 160000 : m[4] === "core" ? 22000 : Math.max(60, Math.min(9000, m[3] * 0.6));
    if (go !== false) flyTo(g, near);
    var ly = m[4] === "core" ? R0 : m[3], yr = new Date().getFullYear();
    rich({
      hash: "system=" + ctx.slug(m[0]), color: m[5], title: m[0].toUpperCase(), badge: kindName(m[4]).split(" (")[0].toUpperCase(), badgeColor: m[5],
      sub: fmtLy(ly) + " away",
      boxes: [["Distance", (ly < 100 ? ly.toFixed(1) : Math.round(ly).toLocaleString()) + " ly", "var(--fg)"], ["Its light left", ly < yr ? "around " + Math.round(yr - ly) : Math.round(ly).toLocaleString() + " years ago", "var(--fg)"], ["Kind", kindName(m[4]).split(" (")[0], m[5]]],
      sections: [["About", '<div class="rc-note" style="color:var(--fg)">' + esc(m[6]) + "</div>"]],
      actions: [["center on it", function () { flyTo(g, near); }]].concat(m[0] === "Andromeda Galaxy" ? [["▶ play the merger", function () { simStart(); }]] : []),
      explain: { title: m[0], names: [m[0]], kind: "astronomy" }
    });
  }
  function flyTo(target, toRad) {   // a short glide (then nothing runs until you move it again)
    var f0 = focus(), r0 = rad, a0 = anchor, t0 = performance.now(), dur = toRad / r0 > 30 || r0 / toRad > 30 ? 1500 : 950, id = {};
    camF = null; anchor = target; rad = toRad; var f1 = focus(); anchor = a0; rad = r0;
    flying = id;
    (function step() {
      if (flying !== id || !active) { if (flying !== id) camF = null; return; }
      var e = Math.min(1, (performance.now() - t0) / dur), k = e * e * (3 - 2 * e);
      rad = Math.exp(Math.log(r0) + (Math.log(toRad) - Math.log(r0)) * k);
      camF = [f0[0] + (f1[0] - f0[0]) * k, f0[1] + (f1[1] - f0[1]) * k, f0[2] + (f1[2] - f0[2]) * k];
      draw();
      if (e < 1) requestAnimationFrame(step); else { flying = null; camF = null; anchor = target; draw(); }
    })();
  }

  /* ---------- round two: the radio bubble, Webb's targets, the Sun's lap, the sky from another star, black holes, how old the light is, live alerts ---------- */
  var LAYERS = (function () { try { return Object.assign({ radio: true, lap: true, alerts: true }, JSON.parse(localStorage.getItem("archieGalLayers") || "{}")); } catch (e) { return { radio: true, lap: true, alerts: true }; } })();
  function setLayer(k, v) { LAYERS[k] = v; try { localStorage.setItem("archieGalLayers", JSON.stringify(LAYERS)); } catch (e) { } req(); }
  var RADIO_START = 1920;   // regular radio broadcasting began in the early 1920s (earlier signals were too weak to matter)
  function radioR() { return new Date().getFullYear() + new Date().getMonth() / 12 - RADIO_START; }
  function drawRadio(c) {
    if (!LAYERS.radio || rad < 25 || rad > 6000) return;
    var R = radioR(), q = proj(SUN[0], SUN[1], SUN[2]), px = R * sc;
    if (px < 6) return;
    var gr = c.createRadialGradient(q[0], q[1], px * 0.6, q[0], q[1], px);
    gr.addColorStop(0, "rgba(120,220,255,0)"); gr.addColorStop(1, "rgba(120,220,255,.10)");
    c.fillStyle = gr; c.beginPath(); c.arc(q[0], q[1], px, 0, 2 * Math.PI); c.fill();
    c.strokeStyle = "rgba(120,220,255,.55)"; c.setLineDash([2, 4]); c.lineWidth = 1; c.beginPath(); c.arc(q[0], q[1], px, 0, 2 * Math.PI); c.stroke(); c.setLineDash([]);
    lab.push({ x: q[0], y: q[1] - px - 8, r: 0, t: px > 120 ? "RADIO BUBBLE · " + Math.round(R) + " LY: AS FAR AS EARTH'S BROADCASTS HAVE GONE" : "RADIO BUBBLE", pri: -2.4, col: "rgba(120,220,255,.85)", center: true });
    shown.push({ x: q[0] + px * 0.7071, y: q[1] - px * 0.7071, r: 10, tip: "<b>The radio bubble</b><span>" + Math.round(R) + " light-years: our radio and TV signals have been spreading at light speed since the 1920s. " + systems.filter(function (s) { return s.ly <= R; }).length + " known planet systems are inside it.</span>", open: function () { openRadio(); } });
  }
  function openRadio() {
    var R = radioR(), inside = systems.filter(function (s) { return s.ly <= R; }).sort(function (a, b) { return a.ly - b.ly; });
    rich({ hash: "system=radio-bubble", color: "#78dcff", title: "THE RADIO BUBBLE", badge: "EARTH'S SIGNALS", badgeColor: "#78dcff", sub: Math.round(R) + " light-years from the Sun in every direction",
      boxes: [["Radius", Math.round(R) + " ly", "var(--fg)"], ["Planet systems inside", String(inside.length), "#78dcff"], ["Growing", "1 ly a year", "var(--fg)"]],
      sections: [["About", '<div class="rc-note" style="color:var(--fg)">Radio and TV signals travel at the speed of light, so the first regular broadcasts of the early 1920s have now spread about ' + Math.round(R) + " light-years. Anyone listening inside this bubble could in principle pick them up; anyone outside it can't have heard us yet. In practice the signals fade fast with distance: past a few light-years, even our strongest broadcasts would be almost impossible to tell apart from noise, so this is how far they've gone, not how far they can be heard. Our galaxy is about 100,000 light-years across, so the bubble is a tiny speck.</div>"],
        ["Closest planet systems inside", inside.slice(0, 12).map(function (s) { return '<div class="gal-pl"><b>' + esc(s.h) + "</b><span>" + fmtLy(s.ly) + "</span><i>signals arrived around " + Math.round(RADIO_START + s.ly) + "</i></div>"; }).join("")]],
      actions: [["center on it", function () { flyTo(null, 260); }]] });
  }
  function radioLine(s) {
    var y = Math.round(RADIO_START + s.ly), now = new Date().getFullYear();
    return y <= now ? " Our first radio broadcasts reached it around " + y + "." : " Our first radio broadcasts won't reach it until about " + (y < 1e5 ? y : Math.round(y).toLocaleString()) + ".";
  }

  // what the James Webb Space Telescope has found in each planet's air (keyed by planet name); results as published through mid-2026
  var WEBB = {
    wasp39b: "The first carbon dioxide ever found on a planet outside the solar system (2022), plus water, sulfur dioxide made by starlight acting on its air, and patchy clouds.",
    wasp96b: "Water vapor and signs of clouds and haze, in one of Webb's first released results (July 2022).",
    k218b: "Methane and carbon dioxide (2023). A claimed hint of dimethyl sulfide, a gas made by life on Earth, has not held up in other teams' analyses; what this planet is like underneath is still debated.",
    trappist1b: "Measured its heat (2023): no sign of a thick carbon-dioxide atmosphere. It may be bare rock, though a hazy atmosphere isn't ruled out.",
    trappist1c: "No thick carbon-dioxide atmosphere like Venus's (2023); a thin one is still possible.",
    trappist1d: "No sign of an Earth-like atmosphere so far (2025); it may have a very thin one or none.",
    trappist1e: "Early results (2025) rule out a hydrogen-rich atmosphere; whether it has a thinner one is still being tested.",
    lhs475b: "Webb's first confirmed Earth-size planet (2023). No thick methane-rich atmosphere; it could still have pure carbon dioxide, or none.",
    gj1214b: "Thick haze hides most of its air. Signs point to a heavy atmosphere, possibly steamy and rich in carbon dioxide (2023).",
    "55cnce": "Strong evidence of a real atmosphere on a rocky lava world, likely carbon monoxide or dioxide coming out of its magma ocean (2024).",
    wasp107b: "Sulfur dioxide, water vapor and clouds of silicate 'sand' (2023), and less methane than expected, a sign its inside is hot (2024).",
    wasp17b: "Tiny quartz crystals in its high clouds (2023).",
    hd189733b: "Hydrogen sulfide, the rotten-egg gas (2024), along with water and carbon dioxide.",
    wasp43b: "Thick clouds on its night side, clearer skies on its day side, and no methane: fast winds keep stirring its air (2024).",
    wasp80b: "Methane in a warm gas giant (2023).",
    toi270d: "Methane, carbon dioxide and water vapor (2024).",
    lhs1140b: "Hints of a nitrogen-rich atmosphere (2024), not yet confirmed. If real, it could have liquid water on its surface.",
    wasp121b: "Silicon monoxide gas and powerful winds that carry heat from its day side to its night side (2025).",
    wasp18b: "Water vapor seen in its glowing day side (2023).",
    gj486b: "A water signal (2023) that may come from the planet or from cool spots on its star; not settled."
  };

  // the nearest known black holes (galactic longitude/latitude worked out from their published positions)
  [["Gaia BH1", 22.63, 18.05, 1560, "The nearest known black hole: about 9.6 times the Sun's mass, with a Sun-like star circling it every 186 days. Gaia's measurements of that star's wobble gave it away in 2022; it isn't eating anything, so it gives off no X-rays."],
   ["Gaia BH3", 51.67, -3.49, 1926, "The heaviest black hole known to come from a single star in our galaxy: about 33 times the Sun's mass. Found in 2024 in Gaia data from the wobble of an old companion star that takes 11.6 years to circle it."],
   ["Gaia BH2", 310.4, 2.78, 3800, "About 8.9 times the Sun's mass, circled by a red giant star every 1,277 days. Found by Gaia in 2023."],
   ["A0620-00", 209.96, -6.54, 3460, "Long the nearest black hole known (it flared up as an X-ray nova in 1975): about 6.6 times the Sun's mass, pulling gas off a small orange star."],
   ["V404 Cygni", 73.12, -2.09, 7800, "About 9 times the Sun's mass. It erupted in 1989 and again in 2015, when it flickered in X-rays for weeks."]].forEach(function (b) {
    MARKS.push([b[0], b[1], b[2], b[3], "blackhole", "#c9a7ff", b[4]]);
  });

  // the Sun's lap around the galaxy: about 230 million years. The marks are where the Sun was when each happened on Earth.
  var LAP_YEARS = 230e6;
  var LAP = [[66e6, "66 million years ago: the asteroid that ended the dinosaurs"], [252e6, "252 million years ago: the Great Dying, the worst extinction in Earth's history"],
    [375e6, "375 million years ago: the first animals with legs crawl onto land"], [538e6, "538 million years ago: the Cambrian explosion, when animal life took off"],
    [LAP_YEARS, "one lap ago (about 230 million years): the first dinosaurs"]];
  function lapPos(yearsAgo) { var a = Math.PI + 2 * Math.PI * yearsAgo / LAP_YEARS; return [R0 * Math.cos(a), R0 * Math.sin(a), 0]; }   // the Sun goes around clockwise seen from the north side
  function drawLap(c) {
    if (!LAYERS.lap || rad < 9000 || rad > 400000) return;
    var k = sstep(Math.log(9000), Math.log(20000), Math.log(rad));
    c.save(); c.globalAlpha = 0.85 * k; c.strokeStyle = "#ffd76a"; c.lineWidth = 1.4; c.setLineDash([4, 5]); c.beginPath();
    for (var i = 0; i <= 120; i++) { var q = proj.apply(null, lapPos(i / 120 * LAP_YEARS)); if (i) c.lineTo(q[0], q[1]); else c.moveTo(q[0], q[1]); }
    c.stroke(); c.setLineDash([]);
    var s0 = proj.apply(null, lapPos(0)), s1 = proj.apply(null, lapPos(-LAP_YEARS * 0.03));   // which way the Sun is heading
    var ang = Math.atan2(s1[1] - s0[1], s1[0] - s0[0]);
    c.fillStyle = "#ffd76a"; c.beginPath(); c.moveTo(s1[0], s1[1]); c.lineTo(s1[0] - 9 * Math.cos(ang - 0.4), s1[1] - 9 * Math.sin(ang - 0.4)); c.lineTo(s1[0] - 9 * Math.cos(ang + 0.4), s1[1] - 9 * Math.sin(ang + 0.4)); c.fill();
    c.restore();
    LAP.forEach(function (e) {
      var q = proj.apply(null, lapPos(e[0])); if (q[0] < -10 || q[1] < -10 || q[0] > W + 10 || q[1] > H + 10) return;
      c.save(); c.globalAlpha = k; c.fillStyle = "#ffd76a"; c.beginPath(); c.arc(q[0], q[1], 3, 0, 2 * Math.PI); c.fill(); c.restore();
      if (e[0] !== LAP_YEARS) lab.push({ x: q[0], y: q[1], r: 3, t: e[1].split(":")[0].replace(" years ago", "").toUpperCase() + " YEARS AGO", pri: -1.6, col: "rgba(255,215,106,.85)" });
      shown.push({ x: q[0], y: q[1], r: 8, tip: "<b>Where the Sun was</b><span>" + esc(e[1]) + "</span>", open: openLap });
    });
    var mid = proj.apply(null, lapPos(LAP_YEARS * 0.42));
    lab.push({ x: mid[0], y: mid[1] + 14, r: 0, t: "THE SUN'S LAP · 230 MILLION YEARS", pri: -2.2, col: "rgba(255,215,106,.8)", center: true });
  }
  function openLap() {
    rich({ hash: "system=suns-lap", color: "#ffd76a", title: "THE SUN'S LAP AROUND THE GALAXY", badge: "230 MILLION YEARS", badgeColor: "#ffd76a", sub: "about 26,700 light-years from the middle, at about 230 km/s",
      boxes: [["One lap", "≈ 230 million yrs", "var(--fg)"], ["Speed", "≈ 230 km/s", "var(--fg)"], ["Laps since Earth formed", "about 20", "#ffd76a"]],
      sections: [["About", '<div class="rc-note" style="color:var(--fg)">The Sun, carrying Earth and everything else in the solar system, circles the middle of the galaxy about once every 230 million years (estimates run from about 220 to 250 million). The gold dots show where it was when big things happened on Earth: the last dinosaurs lived about a quarter of a lap ago, and the first dinosaurs appeared roughly one full lap ago. Earth has gone around about 20 times since it formed.</div>'],
        ["Along the way", LAP.slice().sort(function (a, b) { return a[0] - b[0]; }).map(function (e) { return '<div class="gal-pl"><b>' + esc(e[1].split(":")[0]) + "</b><span>" + esc(e[1].split(": ")[1] || "") + "</span><i>" + (e[0] / LAP_YEARS).toFixed(2) + " of a lap back</i></div>"; }).join("")],
        [null, '<div class="rc-note">Drawn as a simple circle. The real path wobbles in and out and bobs up and down through the disk, and the spiral arms turn too (more slowly than the stars), so the arms were not where they are drawn now.</div>']],
      actions: [["show the whole lap", function () { flyTo(null, 52000); }]] });
  }

  // the sky from another star: where the Sun would be, and how the brightest stars shift
  // [name, RA deg, Dec deg, light-years, brightness from Earth (magnitude; smaller is brighter)]
  var BRIGHT = [["Sirius", 101.287, -16.716, 8.6, -1.46], ["Canopus", 95.988, -52.696, 310, -0.74], ["Alpha Centauri", 219.9, -60.835, 4.37, -0.27], ["Arcturus", 213.915, 19.182, 36.7, -0.05],
    ["Vega", 279.235, 38.784, 25.0, 0.03], ["Capella", 79.172, 45.998, 42.9, 0.08], ["Rigel", 78.634, -8.202, 860, 0.13], ["Procyon", 114.825, 5.225, 11.5, 0.34], ["Achernar", 24.429, -57.237, 139, 0.46],
    ["Betelgeuse", 88.793, 7.407, 550, 0.5], ["Hadar", 210.956, -60.373, 390, 0.61], ["Altair", 297.696, 8.868, 16.7, 0.76], ["Acrux", 186.65, -63.099, 320, 0.76], ["Aldebaran", 68.98, 16.509, 65, 0.86],
    ["Antares", 247.352, -26.432, 550, 0.96], ["Spica", 201.298, -11.161, 250, 0.97], ["Pollux", 116.329, 28.026, 33.8, 1.14], ["Fomalhaut", 344.413, -29.622, 25.1, 1.16], ["Deneb", 310.358, 45.28, 2600, 1.25],
    ["Regulus", 152.093, 11.967, 79, 1.35], ["Castor", 113.65, 31.888, 51, 1.58], ["Polaris", 37.955, 89.264, 433, 1.98], ["Proxima Centauri", 217.429, -62.68, 4.24, 11.13], ["Barnard's Star", 269.452, 4.693, 5.96, 9.5],
    ["Epsilon Eridani", 53.233, -9.458, 10.5, 3.73], ["Tau Ceti", 26.017, -15.937, 11.9, 3.5], ["61 Cygni", 316.725, 38.749, 11.4, 5.21], ["Wolf 359", 164.12, 7.015, 7.86, 13.5]];
  var CB = null;
  function constellation(ra, dec) {
    if (!CB || !window.d3 || !d3.geoContains) return "";
    var lon = ra > 180 ? ra - 360 : ra;
    for (var k in CB) if (d3.geoContains({ type: "MultiPolygon", coordinates: CB[k].p }, [lon, dec])) return CB[k].n;
    return "";
  }
  function eqVec(ra, dec) { var a = ra * D2R, d = dec * D2R; return [Math.cos(d) * Math.cos(a), Math.cos(d) * Math.sin(a), Math.sin(d)]; }
  function vecEq(v) { var L = Math.hypot(v[0], v[1], v[2]); return [((Math.atan2(v[1], v[0]) / D2R) + 360) % 360, Math.asin(v[2] / L) / D2R, L]; }
  function sepDeg(a, b) { var u = eqVec(a[0], a[1]), v = eqVec(b[0], b[1]); return Math.acos(Math.max(-1, Math.min(1, u[0] * v[0] + u[1] * v[1] + u[2] * v[2]))) / D2R; }
  function fmtMag(m) { return (m < 0 ? "−" + Math.abs(m).toFixed(1) : m.toFixed(1)); }
  function seeable(m) { return m < 1 ? "one of the brightest stars in the sky" : m < 6 ? "visible to the eye on a dark night" : m < 9 ? "too faint for the eye; binoculars would show it" : "only visible through a telescope"; }
  function skyFrom(s) {
    var go = function () {
      var V = eqVec(s.ra, s.dec).map(function (x) { return x * s.ly; });
      var sunEq = vecEq([-V[0], -V[1], -V[2]]), sunMag = 4.83 + 5 * Math.log10(s.ly / 3.26156 / 10), sunCon = constellation(sunEq[0], sunEq[1]);
      var rows = BRIGHT.filter(function (b) { return Math.abs(b[3] - s.ly) > 0.01; }).map(function (b) {
        var P = eqVec(b[1], b[2]).map(function (x) { return x * b[3]; }), Dv = [P[0] - V[0], P[1] - V[1], P[2] - V[2]], e = vecEq(Dv);
        return { n: b[0], from: [b[1], b[2]], to: [e[0], e[1]], m0: b[4], m1: b[4] + 5 * Math.log10(e[2] / b[3]), c0: constellation(b[1], b[2]), c1: constellation(e[0], e[1]), d: e[2] };
      });
      rows.forEach(function (r) { r.move = sepDeg(r.from, r.to); });
      var changed = rows.filter(function (r) { return r.move > 1 || Math.abs(r.m1 - r.m0) > 0.4; }).sort(function (a, b) { return b.move - a.move; });
      var same = rows.filter(function (r) { return changed.indexOf(r) < 0; });
      var far = s.ly > 300;
      rich({ hash: "system=" + ctx.slug(s.h) + "-sky", color: "#ffd76a", title: "THE SKY FROM " + s.h.toUpperCase(), badge: "SEEN FROM " + fmtLy(s.ly).toUpperCase() + " AWAY", badgeColor: "#ffd76a",
        sub: "where our Sun would be, and how the brightest stars shift",
        boxes: [["The Sun would be in", sunCon || "—", "#ffd76a"], ["Its magnitude", fmtMag(sunMag), "var(--fg)"], ["Stars that shift", String(changed.length) + " of " + rows.length, "var(--fg)"]],
        sections: [["Our Sun from there", '<div class="rc-note" style="color:var(--fg)">From ' + esc(s.h) + ", the Sun would sit " + (sunCon ? "in the constellation we call " + esc(sunCon) : "in the opposite direction from where we see " + esc(s.h)) + ", " + esc(seeable(sunMag)) + " (magnitude " + fmtMag(sunMag) + ")." + (sunMag > 6 ? " Anyone there would need a telescope to know we exist." : "") + "</div>"],
          [null, '<div id="gal-skymap" class="gal-skymap"></div>'],
          ["What changes", changed.length ? changed.slice(0, 14).map(function (r) {
            var line = r.move > 1 ? "moves " + (r.move < 10 ? r.move.toFixed(1) : Math.round(r.move)) + "°" + (r.c1 && r.c1 !== r.c0 ? ", out of " + r.c0 + " into " + r.c1 : r.c0 ? ", staying in " + r.c0 : "") : "stays put";
            return '<div class="gal-pl"><b>' + esc(r.n) + "</b><span>" + esc(line) + "</span><i>" + (Math.abs(r.m1 - r.m0) > 0.4 ? (r.m1 < r.m0 ? "brighter: " : "dimmer: ") + fmtMag(r.m0) + " → " + fmtMag(r.m1) + " · " : "") + esc(seeable(r.m1)) + "</i></div>";
          }).join("") : '<div class="rc-note">Almost nothing: this star is close enough that the sky looks nearly the same as ours.</div>'],
          [null, '<div class="rc-note">' + (same.length ? "Barely changed: " + esc(same.map(function (r) { return r.n; }).join(", ")) + ". " : "") + (far ? "From this far away most of the stars we know would be scattered or too faint to see, so the familiar constellations would be gone. " : "") + "Constellations are just patterns as seen from Earth: the stars in them are at very different distances, so from somewhere else they come apart. Directions use our names for that part of the sky. Brightness is magnitude: smaller is brighter, and about 6 is the faintest the eye can see.</div>"]],
        actions: [["back to " + s.h, function () { openSys(s); }]],
        after: function () { skyMap(rows, sunEq, sunMag); } });
    };
    if (CB) go(); else fetch("/web/data/constbounds.json").then(function (r) { return r.json(); }).then(function (d) { CB = d; go(); }).catch(function () { CB = {}; go(); });
  }
  function skyMap(rows, sunEq, sunMag) {   // the whole sky flattened out: grey dots where we see the stars, white where they'd be from there
    var box = document.getElementById("gal-skymap"); if (!box) return;
    var w = box.clientWidth || 320, h = Math.round(w / 2), X = function (ra) { return w - ra / 360 * w; }, Y = function (dec) { return h / 2 - dec / 180 * h; };
    var r = function (m) { return Math.max(1, Math.min(4.5, 3.2 - m * 0.55)); };
    var svg = '<svg width="' + w + '" height="' + (h + 14) + '"><rect width="' + w + '" height="' + h + '" fill="#050817" stroke="#1d2550"/>' +
      '<line x1="0" x2="' + w + '" y1="' + h / 2 + '" y2="' + h / 2 + '" stroke="#1d2550" stroke-dasharray="2 4"/>';
    rows.forEach(function (o) {
      var x0 = X(o.from[0]), y0 = Y(o.from[1]), x1 = X(o.to[0]), y1 = Y(o.to[1]);
      if (o.move > 1 && Math.abs(x1 - x0) < w / 2) svg += '<line x1="' + x0 + '" y1="' + y0 + '" x2="' + x1 + '" y2="' + y1 + '" stroke="rgba(255,255,255,.25)"/>';
      svg += '<circle cx="' + x0 + '" cy="' + y0 + '" r="' + r(o.m0) + '" fill="#59607d"><title>' + esc(o.n) + ' from Earth</title></circle>';
      svg += '<circle cx="' + x1 + '" cy="' + y1 + '" r="' + r(o.m1) + '" fill="#f4f6ff"><title>' + esc(o.n) + ' from there</title></circle>';
    });
    svg += '<circle cx="' + X(sunEq[0]) + '" cy="' + Y(sunEq[1]) + '" r="' + Math.max(2.5, r(sunMag)) + '" fill="#ffd76a" stroke="#ffd76a" stroke-width="5" stroke-opacity=".25"><title>the Sun</title></circle>';
    svg += '<text x="4" y="' + (h + 11) + '" class="gal-mini-lab">whole sky · grey = from Earth · white = from there · gold = the Sun</text></svg>';
    box.innerHTML = svg;
  }

  // how old the light is at the edge of the view, matched to Earth's history
  var PAST = [[100, "the first radio broadcasts"], [250, "the American Revolution"], [530, "Columbus crossing the Atlantic"], [1000, "the Vikings reaching North America"], [2000, "the Roman Empire"],
    [4500, "the building of the Great Pyramid"], [5200, "the first writing"], [12000, "the end of the last ice age and the first farms"], [40000, "the oldest cave paintings"], [300000, "the first modern humans"],
    [2.6e6, "the first stone tools"], [7e6, "our ancestors splitting from chimpanzees'"], [66e6, "the dinosaurs' last days"], [230e6, "the first dinosaurs"], [375e6, "the first animals walking onto land"],
    [540e6, "animal life taking off in the seas"], [2.4e9, "oxygen first building up in the air"], [3.7e9, "the earliest signs of life on Earth"], [4.54e9, "Earth forming"], [9e9, "a time long before the Sun existed"], [13.4e9, "the first galaxies forming"]];
  var CT = null;
  function lookback(ly) {   // a distance (light-years, as it is now) -> how long its light has been travelling (years)
    if (ly < 1e8) return ly;
    if (!CT) { CT = [[0, 0]]; var z = 0, D = 0, T = 0, dz = 0.002, ht = 977.8e9 / 67.7, ch = 299792.458 / 67.7 * 3.26156e6;
      while (z < 30) { var E = Math.sqrt(0.31 * Math.pow(1 + z + dz / 2, 3) + 0.69); D += ch * dz / E; T += ht * dz / ((1 + z + dz / 2) * E); z += dz; if (z > 3) dz = 0.02; CT.push([D, T]); } }
    for (var i = 1; i < CT.length; i++) if (CT[i][0] >= ly) { var f = (ly - CT[i - 1][0]) / (CT[i][0] - CT[i - 1][0]); return CT[i - 1][1] + f * (CT[i][1] - CT[i - 1][1]); }
    return 13.79e9;
  }
  function fmtYears(y) { return y >= 1e9 ? (y / 1e9).toFixed(y < 1e10 ? 1 : 1) + " billion years" : y >= 1e6 ? (y / 1e6 < 10 ? (y / 1e6).toFixed(1) : Math.round(y / 1e6)) + " million years" : y >= 10000 ? Math.round(y / 1000).toLocaleString() + ",000 years" : Math.round(y).toLocaleString() + " years"; }
  function pastLine() {
    var y = lookback(rad);
    if (y < 60) return "LIGHT FROM THE EDGE OF THIS VIEW LEFT " + fmtYears(y).toUpperCase() + " AGO · WITHIN A LIFETIME";
    var best = PAST[0]; PAST.forEach(function (p) { if (Math.abs(Math.log(p[0] / y)) < Math.abs(Math.log(best[0] / y))) best = p; });
    return "LIGHT FROM THE EDGE OF THIS VIEW LEFT ABOUT " + fmtYears(y).toUpperCase() + " AGO · ON EARTH THEN: " + best[1].toUpperCase();
  }

  // live alerts: supernovae, gamma-ray bursts, and gravitational waves from colliding black holes and neutron stars
  var COSMIC = null, cosmicAt = 0;
  var AK = { sn: ["#ffb36b", "supernova", "SUPERNOVA"], grb: ["#7fe3ff", "gamma-ray burst", "GAMMA-RAY BURST"], gw: ["#c9a7ff", "gravitational waves", "GRAVITATIONAL WAVES"] };
  function loadCosmic() {
    if (Date.now() - cosmicAt < 30 * 60 * 1000) return;
    cosmicAt = Date.now();
    api("/api/cosmic").then(function (d) { COSMIC = d || {}; req(); }).catch(function () { cosmicAt = 0; });
  }
  function alertList() {
    if (!COSMIC) return [];
    var now = Date.now(), L = [];
    (COSMIC.sn || []).forEach(function (a) { if (a.ra != null) L.push(a); });
    (COSMIC.grb || []).forEach(function (a) { if (a.ra != null && !a.nopos && now - Date.parse(a.t) < 45 * 864e5) L.push(a); });
    (COSMIC.gw || []).forEach(function (a) { if (a.ra != null && now - Date.parse(a.t) < 400 * 864e5) L.push(a); });
    return L;
  }
  function drawAlerts(c) {
    if (!LAYERS.alerts) return;
    var S0 = proj(SUN[0], SUN[1], SUN[2]), t = performance.now();
    alertList().forEach(function (a) {
      var k = AK[a.kind], dir = galDir(a.ra, a.dec), q, ray = true;
      if (a.ly && a.ly < rad * 2.5 && a.ly > rad * 0.02) { var g = fromSun(dir, a.ly); q = proj(g[0], g[1], g[2]); ray = false; }
      else { var L = Math.min(rad * 0.62, a.ly || 1e30); var g2 = fromSun(dir, L); q = proj(g2[0], g2[1], g2[2]); var dx = q[0] - S0[0], dy = q[1] - S0[1], dl = Math.hypot(dx, dy) || 1, want = Math.min(W, H) * 0.3; q = [S0[0] + dx / dl * want, S0[1] + dy / dl * want]; }
      if (q[0] < -10 || q[1] < -10 || q[0] > W + 10 || q[1] > H + 10) return;
      c.save();
      if (ray) { var gr = c.createLinearGradient(S0[0], S0[1], q[0], q[1]); gr.addColorStop(0, "rgba(0,0,0,0)"); gr.addColorStop(1, k[0]); c.strokeStyle = gr; c.globalAlpha = 0.5; c.lineWidth = 1; c.beginPath(); c.moveTo(S0[0], S0[1]); c.lineTo(q[0], q[1]); c.stroke(); c.globalAlpha = 1; }
      c.strokeStyle = k[0]; c.fillStyle = k[0]; c.lineWidth = 1.2;
      if (a.kind === "gw") { [4, 7, 10].forEach(function (r) { c.beginPath(); c.arc(q[0], q[1], r, 0, 2 * Math.PI); c.globalAlpha = 1.1 - r / 11; c.stroke(); }); c.globalAlpha = 1; }
      else if (a.kind === "grb") { for (var i = 0; i < 4; i++) { var an = i * Math.PI / 4 + 0.2; c.beginPath(); c.moveTo(q[0] - Math.cos(an) * 7, q[1] - Math.sin(an) * 7); c.lineTo(q[0] + Math.cos(an) * 7, q[1] + Math.sin(an) * 7); c.stroke(); } }
      else { c.beginPath(); c.arc(q[0], q[1], 2.6, 0, 2 * Math.PI); c.fill(); c.beginPath(); c.arc(q[0], q[1], 6, 0, 2 * Math.PI); c.globalAlpha = 0.5; c.stroke(); c.globalAlpha = 1; }
      c.restore();
      shown.push({ x: q[0], y: q[1], r: 9, tip: "<b>" + esc(a.name) + "</b><span>" + esc(k[1]) + (a.host ? " in " + esc(a.host) : "") + (a.ly ? " · " + fmtLy(a.ly) : "") + (ray ? " · this way (too far to show at this zoom)" : "") + "</span>", open: function () { openAlert(a); } });
      lab.push({ x: q[0], y: q[1], r: 8, t: a.name, pri: -1.2, col: k[0] });
    });
  }
  function openAlert(a) {
    var k = AK[a.kind], yr = new Date().getFullYear(), rows = [];
    var light = a.lookback ? (a.kind === "gw" ? "Its ripples" : "Its light") + " set out about " + fmtYears(a.lookback) + " ago. On Earth then: " + PAST.reduce(function (b, p) { return Math.abs(Math.log(p[0] / a.lookback)) < Math.abs(Math.log(b[0] / a.lookback)) ? p : b; }, PAST[0])[1] + "." : "";
    var about = a.kind === "sn" ? "A star that exploded" + (a.host ? " in the galaxy " + a.host : "") + ". Type " + a.type + ": " + (/^Ia/.test(a.type) ? "a white dwarf that blew itself apart; these all peak at about the same brightness, which is how astronomers measure distances across the universe (and found that its expansion is speeding up)." : /^II/.test(a.type) ? "a massive star whose core collapsed at the end of its life, leaving a neutron star or black hole." : /^I[bc]/.test(a.type) ? "a massive star stripped of its outer layers before its core collapsed." : "its exact kind is still being worked out.") + " Brightest it has been: magnitude " + a.mag + (parseFloat(a.mag) < 13 ? ", bright enough for a backyard telescope." : ".") :
      a.kind === "grb" ? "A gamma-ray burst: for a few " + (a.short ? "tenths of a second" : "seconds to minutes") + ", more energy than the Sun will give off in its whole life. " + (a.short ? "Short bursts like this usually come from two neutron stars colliding." : "Long bursts come from very massive stars collapsing into black holes.") + " They happen in far-off galaxies, so they're only seen by satellites." :
      "Ripples in space itself from " + a.what + (a.p != null ? " (" + a.p + "% likely, by the detectors' own estimate)" : "") + ". LIGO in the US, Virgo in Italy and KAGRA in Japan felt space stretch and squeeze by less than the width of a proton." + (a.area ? " The detectors can only narrow the direction to a patch of sky about " + a.area.toLocaleString() + " square degrees wide (the full Moon covers 0.2), so the mark is the single likeliest spot." : "");
    if (a.kind === "sn") rows = [["Found", a.first || "—", "var(--fg)"], ["Type", a.type || "—", k[0]], ["Brightness", a.mag || "—", "var(--fg)"]];
    else if (a.kind === "grb") rows = [["Date", a.t, "var(--fg)"], ["Kind", a.short ? "short burst" : "burst", k[0]], ["Position within", a.err || "—", "var(--fg)"]];
    else rows = [["Date", (a.t || "").slice(0, 10), "var(--fg)"], ["What", (a.what || "").replace(" merging", ""), k[0]], ["Distance", a.ly ? fmtLy(a.ly).replace(" light-years", " ly") : "—", "var(--fg)"]];
    rich({ hash: "system=" + ctx.slug(a.name), color: k[0], title: a.name.toUpperCase(), badge: k[2], badgeColor: k[0], sub: (a.ly ? fmtLy(a.ly) + " away · " : "") + "RA " + a.ra.toFixed(1) + "°, Dec " + a.dec.toFixed(1) + "°" + (CB ? " (in " + (constellation(a.ra, a.dec) || "?") + ")" : ""),
      boxes: rows,
      sections: [["About", '<div class="rc-note" style="color:var(--fg)">' + esc(about) + (light ? " " + esc(light) : "") + "</div>"],
        [null, '<div class="rc-note">' + (a.kind === "sn" ? "From the Latest Supernovae list (rochesterastronomy.org), which collects reports from survey telescopes and amateurs." : a.kind === "grb" ? "From the GCN Circulars, where NASA's Fermi and Swift teams and others post positions. " + esc(a.src || "") : "From LIGO-Virgo-KAGRA's public alerts (GraceDB). Distances to these are rough, often ±30%.") + ' <a href="' + esc(a.url || "#") + '" target="_blank" rel="noopener">source</a></div>']],
      actions: [["show its direction", function () { flyTo(a.ly && a.ly < 3e9 ? fromSun(galDir(a.ra, a.dec), a.ly) : null, a.ly ? Math.max(60000, a.ly * 0.6) : 52000); }]] });
    if (!CB) fetch("/web/data/constbounds.json").then(function (r) { return r.json(); }).then(function (d) { CB = d; }).catch(function () { });
  }

  /* ---------- data ---------- */
  function load() {
    if (loaded) return; loaded = true;
    api("/api/exo").then(function (d) {
      if (!d || !d.systems || d.systems.length < 100) { mark(); return; }
      catalogAt = d.at;
      var have = {};
      systems = d.systems.map(function (s) { var k = norm(s.h); have[k] = 1; if (FAME[k]) s.about = FAME[k]; return s; });
      famousAsSystems().forEach(function (f) { if (!have[norm(f.h)]) { f.about = FAME[norm(f.h)]; systems.push(f); } });
      mark(); req();
    }).catch(function () { loaded = false; mark(); });
  }
  function mark() { systems.forEach(function (s) { if (s.about === undefined) s.about = FAME[norm(s.h)] || null; s.hab = s.p.some(temperate); s.webb = s.p.some(function (p) { return WEBB[norm(p[0])]; }); }); }
  mark();
  function exit() { if (onExit) onExit(); }

  return {
    make: make,
    show: function (fromSolar) {
      active = true; root.hidden = false; resize(); load(); loadCosmic();
      if (fromSolar) { anchor = null; rad = 14; flyTo(null, 60); } else req();
    },
    hide: function () { active = false; flying = null; if (SIM) simStop(); if (root) root.hidden = true; if (tipEl) tipEl.hidden = true; },
    select: function (v) {
      v = norm(v);
      var m = MARKS.find(function (x) { return norm(x[0]) === v; }); if (m) { openMark(m); return; }
      if (v === "radiobubble") { openRadio(); return; }
      if (v === "sunslap") { openLap(); return; }
      var s = systems.find(function (x) { return norm(x.h) === v; }) || systems.find(function (x) { return norm(x.h).indexOf(v) === 0; });
      if (s) openSys(s, true);
      else if (!catalogAt) setTimeout(function () { var s2 = systems.find(function (x) { return norm(x.h) === v; }); if (s2) openSys(s2, true); }, 2500);
    },
    zoomOut: function () { flyTo(null, 52000); },
    merger: function () { simStart(); }
  };
};
