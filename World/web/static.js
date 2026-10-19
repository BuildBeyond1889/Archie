// Archie World: fixed reference data (places, routes, hours). Live numbers come from /api/state.
"use strict";
function esc(s) { return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function X(name, full, city, cc, lat, lng, tz, open, chg, tier, desc, idx, wk) { return { name: name, full: full, city: city, cc: cc, lat: lat, lng: lng, tz: tz, open: open, chg: chg, tier: tier, desc: desc, idx: idx, wk: wk || ["Sat", "Sun"] }; }
  var exchanges = [
    X("NYSE", "New York Stock Exchange", "New York", "US", 40.71, -74.01, "America/New_York", [9.5, 16], 0.42, "MAJOR", "The world's largest exchange by the value of the companies listed on it.", "S&P 500"),
    X("NASDAQ", "Nasdaq", "New York", "US", 40.757, -73.986, "America/New_York", [9.5, 16], 0.61, "MAJOR", "Home of most big US tech listings.", "Nasdaq 100"),
    X("TSX", "Toronto Stock Exchange", "Toronto", "CA", 43.65, -79.38, "America/Toronto", [9.5, 16], 0.18, "DEVELOPED", "Canada's main exchange; heavy in banks, energy and mining.", "S&P/TSX"),
    X("BMV", "Bolsa Mexicana de Valores", "Mexico City", "MX", 19.43, -99.17, "America/Mexico_City", [8.5, 15], -0.22, "EMERGING", "Mexico's main exchange.", "S&P/BMV IPC"),
    X("B3", "B3 (Brasil Bolsa Balcão)", "São Paulo", "BR", -23.55, -46.63, "America/Sao_Paulo", [10, 17], -0.61, "EMERGING", "Latin America's largest exchange.", "Ibovespa"),
    X("LSE", "London Stock Exchange", "London", "GB", 51.51, -0.09, "Europe/London", [8, 16.5], -0.12, "MAJOR", "Europe's biggest listing venue for international companies.", "FTSE 100"),
    X("EPA", "Euronext Paris", "Paris", "FR", 48.87, 2.34, "Europe/Paris", [9, 17.5], 0.11, "MAJOR", "Part of Euronext, the largest exchange group in Europe.", "CAC 40"),
    X("XETRA", "Deutsche Börse · Xetra", "Frankfurt", "DE", 50.11, 8.68, "Europe/Berlin", [9, 17.5], 0.27, "MAJOR", "Germany's main electronic trading venue.", "DAX"),
    X("SIX", "SIX Swiss Exchange", "Zurich", "CH", 47.37, 8.54, "Europe/Zurich", [9, 17.5], 0.08, "DEVELOPED", "Switzerland's exchange; big in pharma, food and banking.", "SMI"),
    X("BIST", "Borsa Istanbul", "Istanbul", "TR", 41.1, 29.0, "Europe/Istanbul", [10, 18], -0.74, "EMERGING", "Turkey's exchange; swings with the lira and interest rates.", "BIST 100"),
    X("TASE", "Tel Aviv Stock Exchange", "Tel Aviv", "IL", 32.07, 34.79, "Asia/Jerusalem", [9.9, 17.25], 0.35, "DEVELOPED", "Israel's exchange; strong in tech and defense.", "TA-35"),
    X("EGX", "Egyptian Exchange", "Cairo", "EG", 30.05, 31.25, "Africa/Cairo", [10, 14.5], 1.31, "EMERGING", "Egypt's exchange, one of the oldest in the Middle East. Trades Sunday to Thursday.", "EGX 30", ["Fri", "Sat"]),
    X("TADAWUL", "Saudi Exchange (Tadawul)", "Riyadh", "SA", 24.71, 46.67, "Asia/Riyadh", [10, 15], -0.18, "EMERGING", "The largest exchange in the Arab world. Trades Sunday to Thursday.", "TASI", ["Fri", "Sat"]),
    X("DFM", "Dubai Financial Market", "Dubai", "AE", 25.22, 55.28, "Asia/Dubai", [10, 14.75], 0.24, "EMERGING", "Dubai's exchange; heavy in property and banks.", "DFM General"),
    X("JSE", "Johannesburg Stock Exchange", "Johannesburg", "ZA", -26.1, 28.05, "Africa/Johannesburg", [9, 17], 0.05, "EMERGING", "Africa's largest exchange; big in mining.", "JSE All Share"),
    X("NGX", "Nigerian Exchange", "Lagos", "NG", 6.45, 3.39, "Africa/Lagos", [10, 14.5], 0.62, "FRONTIER", "West Africa's biggest market.", "NGX All-Share"),
    X("NSE", "National Stock Exchange of India", "Mumbai", "IN", 19.06, 72.86, "Asia/Kolkata", [9.25, 15.5], 0.83, "EMERGING", "One of the busiest exchanges in the world by number of trades.", "Nifty 50"),
    X("SSE", "Shanghai Stock Exchange", "Shanghai", "CN", 31.23, 121.5, "Asia/Shanghai", [9.5, 15], -0.34, "EMERGING", "Mainland China's largest exchange.", "SSE Composite"),
    X("HKEX", "Hong Kong Exchanges", "Hong Kong", "HK", 22.28, 114.16, "Asia/Hong_Kong", [9.5, 16], -0.91, "MAJOR", "Gateway for global money into Chinese companies.", "Hang Seng"),
    X("TSE", "Tokyo Stock Exchange (JPX)", "Tokyo", "JP", 35.68, 139.78, "Asia/Tokyo", [9, 15.5], 1.12, "MAJOR", "Asia's largest exchange by the value of listed companies.", "Nikkei 225"),
    X("KRX", "Korea Exchange", "Seoul", "KR", 37.52, 126.93, "Asia/Seoul", [9, 15.5], 0.42, "EMERGING", "Korea's exchange; Samsung and SK Hynix drive it.", "KOSPI"),
    X("TWSE", "Taiwan Stock Exchange", "Taipei", "TW", 25.03, 121.56, "Asia/Taipei", [9, 13.5], 0.95, "EMERGING", "Dominated by TSMC, the world's biggest chipmaker.", "TAIEX"),
    X("SGX", "Singapore Exchange", "Singapore", "SG", 1.28, 103.85, "Asia/Singapore", [9, 17], 0.12, "DEVELOPED", "Southeast Asia's financial hub.", "STI"),
    X("IDX", "Indonesia Stock Exchange", "Jakarta", "ID", -6.22, 106.81, "Asia/Jakarta", [9, 16], -0.28, "EMERGING", "Southeast Asia's largest economy's exchange.", "JCI"),
    X("ASX", "Australian Securities Exchange", "Sydney", "AU", -33.87, 151.21, "Australia/Sydney", [10, 16], 0.21, "DEVELOPED", "Australia's exchange; banks and miners.", "ASX 200")
  ];
  // central banks (places are real; the live rate comes from FRED where it has one)
  var banks = [
    ["Fed", "Federal Reserve", "Washington", 38.893, -77.046, "fed"], ["ECB", "European Central Bank", "Frankfurt", 50.109, 8.703, "ecb"],
    ["BoE", "Bank of England", "London", 51.514, -0.088], ["BoJ", "Bank of Japan", "Tokyo", 35.686, 139.771],
    ["PBoC", "People's Bank of China", "Beijing", 39.91, 116.36], ["SNB", "Swiss National Bank", "Bern", 46.947, 7.444],
    ["RBI", "Reserve Bank of India", "Mumbai", 18.932, 72.836], ["BCB", "Banco Central do Brasil", "Brasília", -15.8, -47.87],
    ["Banxico", "Banco de México", "Mexico City", 19.435, -99.14], ["CBRT", "Central Bank of Turkey", "Ankara", 39.92, 32.85],
    ["SAMA", "Saudi Central Bank", "Riyadh", 24.69, 46.68], ["CBE", "Central Bank of Egypt", "Cairo", 30.047, 31.24],
    ["BoC", "Bank of Canada", "Ottawa", 45.42, -75.7], ["RBA", "Reserve Bank of Australia", "Sydney", -33.87, 151.21]
  ].map(function (b) { return { short: b[0], name: b[1], city: b[2], lat: b[3], lng: b[4], live: b[5] || null }; });
  function isOpen(x) {
    var parts = new Intl.DateTimeFormat("en-US", { timeZone: x.tz, hour: "numeric", minute: "numeric", weekday: "short", hour12: false }).formatToParts(new Date());
    var get = function (t) { var p = parts.find(function (p) { return p.type === t; }); return p ? p.value : ""; };
    var h = parseInt(get("hour"), 10) % 24 + parseInt(get("minute"), 10) / 60, wd = get("weekday");
    return (x.wk || ["Sat", "Sun"]).indexOf(wd) < 0 && h >= x.open[0] && h < x.open[1];
  }
  // what each chokepoint connects (shown under the name)
  var CSUB = { "Strait of Hormuz": "Gulf oil & LNG exports", "Strait of Malacca": "Indian Ocean–Pacific shipping", "Suez Canal": "Europe–Asia shipping",
    "Bab el-Mandeb": "Red Sea southern gate", "Panama Canal": "Atlantic–Pacific shortcut", "Turkish Straits": "Black Sea exit", "Taiwan Strait": "East Asia container lane",
    "Strait of Gibraltar": "Mediterranean–Atlantic gate", "Dover Strait": "North Sea–Channel traffic", "Danish Straits": "Baltic exit", "Kerch Strait": "Sea of Azov exit",
    "Cape of Good Hope": "The long way around Africa", "Lombok Strait": "Deep-water bypass of Malacca", "Sunda Strait": "Java Sea–Indian Ocean", "Korea Strait": "Korea–Japan lane",
    "Mozambique Channel": "East Africa tanker route", "Bering Strait": "Arctic gateway", "Drake Passage": "Around South America" };
  // pipelines that let oil or gas skip a chokepoint
  var BYPASS = { "Strait of Hormuz": ["East–West Pipeline (Petroline)", "Habshan–Fujairah"], "Bab el-Mandeb": ["East–West Pipeline (Petroline)"],
    "Suez Canal": ["SUMED"], "Strait of Malacca": ["Myanmar–China"], "Turkish Straits": ["TurkStream", "Baku–Tbilisi–Ceyhan"], "Danish Straits": ["Baltic Pipe"] };
  var chokes = [
    { name: "Strait of Hormuz", lat: 26.57, lng: 56.25, major: true, what: "About a fifth of the world's oil moves through here, most of it bound for Asia." },
    { name: "Strait of Malacca", lat: 2.5, lng: 101.3, major: true, what: "Shortest sea route between the Indian Ocean and the Pacific; the busiest oil strait by volume." },
    { name: "Suez Canal", lat: 30.6, lng: 32.33, major: true, what: "Links the Mediterranean and the Red Sea. Roughly a tenth of world trade in a normal year." },
    { name: "Bab el-Mandeb", lat: 12.6, lng: 43.3, major: true, what: "The Red Sea's southern gate. Traffic drops fast when ships are attacked, pushing them around Africa." },
    { name: "Panama Canal", lat: 9.08, lng: -79.68, major: true, what: "Links the Atlantic and Pacific. Droughts limit how many ships can cross." },
    { name: "Turkish Straits", lat: 41.12, lng: 29.07, major: true, what: "Bosporus and Dardanelles: the Black Sea's only way out. Key for Russian and Kazakh oil and Ukrainian grain." },
    { name: "Taiwan Strait", lat: 24.5, lng: 119.5, major: true, what: "A large share of the world's container ships pass through; any blockade would hit chip supply chains." },
    { name: "Strait of Gibraltar", lat: 35.95, lng: -5.6, what: "The Mediterranean's Atlantic gate." },
    { name: "Dover Strait", lat: 51.0, lng: 1.45, what: "The busiest shipping lane in the world, between England and France." },
    { name: "Danish Straits", lat: 55.6, lng: 12.7, what: "The Baltic's exit to the North Sea; carries Russian oil exports from Baltic ports." },
    { name: "Kerch Strait", lat: 45.3, lng: 36.5, what: "Connects the Sea of Azov to the Black Sea." },
    { name: "Lombok Strait", lat: -8.75, lng: 115.75, what: "Deep-water route for ships too big for Malacca." },
    { name: "Sunda Strait", lat: -6.0, lng: 105.8, what: "Backup route between the Indian Ocean and the Java Sea." },
    { name: "Korea Strait", lat: 34.5, lng: 129.2, what: "Between Korea and Japan; busy with container and car carriers." },
    { name: "Cape of Good Hope", lat: -34.8, lng: 18.5, what: "The detour when the Red Sea is unsafe; adds roughly 10 to 14 days to Asia–Europe trips." },
    { name: "Mozambique Channel", lat: -17.5, lng: 41.5, what: "Route for tankers going around Africa." },
    { name: "Bering Strait", lat: 65.8, lng: -169.0, what: "The Arctic gateway between Russia and Alaska." },
    { name: "Drake Passage", lat: -57.5, lng: -65.5, what: "The open-water route around South America." }
  ];
  function P(name, kind, from, to, status, note, pts) { return { name: name, kind: kind, from: from, to: to, status: status, note: note, pts: pts }; }
  var pipes = [
    P("Druzhba (northern leg)", "oil", "Russia", "Poland · Germany", "reduced", "Once Europe's biggest oil artery. Germany and Poland stopped buying Russian crude, so it mostly carries Kazakh oil now.", [[54.9, 52.3], [53.2, 50.1], [52.85, 32.7], [52.05, 29.25], [52.1, 23.7], [52.55, 19.7], [53.06, 14.28]]),
    P("Druzhba (southern leg)", "oil", "Russia", "Slovakia · Hungary", "flowing", "Still supplies Hungary and Slovakia through Ukraine. Strikes on pumping stations have paused it before.", [[52.05, 29.25], [50.6, 26.2], [48.62, 22.3], [48.15, 17.1]]),
    P("Caspian Pipeline (CPC)", "oil", "Kazakhstan", "Black Sea (Novorossiysk)", "disrupted", "Carries most of Kazakhstan's oil exports, around 1.5% of world supply. Drone attacks on its sea terminal have cut loadings.", [[46.15, 53.4], [47.1, 51.9], [46.35, 48.05], [45.85, 40.1], [44.72, 37.77]]),
    P("Nord Stream", "gas", "Russia", "Germany", "offline", "Blown up in September 2022; no gas has moved since.", [[60.7, 28.75], [60.0, 26.0], [59.3, 22.5], [57.5, 19.5], [55.3, 15.5], [54.14, 13.64]]),
    P("Ukraine gas transit", "gas", "Russia", "Slovakia (through Ukraine)", "offline", "Transit ended when the Russia–Ukraine contract expired on January 1, 2025.", [[50.6, 36.6], [49.6, 34.5], [50.0, 30.0], [49.4, 26.0], [48.62, 22.3]]),
    P("Yamal–Europe", "gas", "Russia", "Germany (through Belarus, Poland)", "offline", "Idle since 2022 sanctions; Poland occasionally runs it in reverse.", [[57.04, 34.96], [53.9, 27.56], [52.4, 23.2], [52.65, 19.07], [52.35, 14.55]]),
    P("TurkStream", "gas", "Russia", "Turkey · southeast Europe", "flowing", "Under the Black Sea; the last route taking Russian pipeline gas into the EU.", [[44.9, 37.3], [43.5, 33.0], [41.63, 28.1], [41.4, 27.35]]),
    P("Southern Gas Corridor (TANAP / TAP)", "gas", "Azerbaijan", "Italy", "flowing", "Caspian gas to Europe through Georgia, Turkey, Greece and Albania, avoiding Russia.", [[40.4, 49.9], [41.7, 44.8], [39.9, 41.27], [39.77, 30.52], [40.95, 26.35], [40.64, 22.94], [40.72, 19.56], [40.27, 18.4]]),
    P("Baku–Tbilisi–Ceyhan", "oil", "Azerbaijan", "Turkey (Mediterranean)", "flowing", "Caspian oil to the Mediterranean without touching Russia or Iran.", [[40.3, 49.8], [41.6, 44.9], [40.6, 42.6], [38.4, 38.3], [36.88, 35.93]]),
    P("Kirkuk–Ceyhan", "oil", "Iraq (Kurdistan)", "Turkey (Mediterranean)", "reduced", "Shut for two and a half years over a legal fight, restarted in 2025 at part of its old volume.", [[35.47, 44.39], [36.34, 43.13], [37.25, 42.47], [36.88, 35.93]]),
    P("East–West Pipeline (Petroline)", "oil", "Saudi Gulf coast", "Red Sea (Yanbu)", "flowing", "Lets Saudi oil skip the Strait of Hormuz by crossing the country to the Red Sea.", [[25.93, 49.67], [24.7, 46.7], [24.09, 38.06]]),
    P("Habshan–Fujairah", "oil", "Abu Dhabi", "Gulf of Oman (Fujairah)", "flowing", "The UAE's way around Hormuz.", [[23.83, 53.65], [25.12, 56.33]]),
    P("SUMED", "oil", "Red Sea (Ain Sukhna)", "Mediterranean", "flowing", "Moves crude across Egypt next to the Suez Canal, for tankers too big for it.", [[29.6, 32.35], [31.1, 29.6]]),
    P("Power of Siberia", "gas", "East Siberia", "China", "flowing", "Russia's main gas line to China, pivoted to after Europe cut purchases.", [[60.3, 112.0], [60.7, 114.9], [58.6, 125.4], [53.98, 123.9], [50.26, 127.5]]),
    P("ESPO", "oil", "East Siberia", "Pacific coast · China", "flowing", "Carries Russian crude to Asia, now its main buyers.", [[55.94, 98.0], [56.8, 105.8], [53.98, 123.9], [48.5, 135.1], [42.75, 133.05]]),
    P("Central Asia–China", "gas", "Turkmenistan", "China", "flowing", "China's biggest source of pipeline gas.", [[39.1, 63.6], [39.77, 64.42], [41.3, 69.24], [42.3, 69.6], [43.25, 76.9], [44.2, 80.4], [43.8, 87.6]]),
    P("Myanmar–China", "gas", "Bay of Bengal", "China (Kunming)", "flowing", "Lets China bring in energy while bypassing Malacca. It crosses Myanmar's war zones.", [[19.43, 93.55], [21.97, 96.08], [23.98, 97.9], [25.04, 102.7]]),
    P("Trans-Alaska", "oil", "Prudhoe Bay", "Valdez", "flowing", "Carries all of Alaska's North Slope oil south to the port of Valdez.", [[70.25, -148.3], [64.8, -147.7], [62.1, -145.5], [61.13, -146.35]]),
    P("Keystone", "oil", "Alberta", "US Gulf Coast · Illinois", "flowing", "Canadian oil sands crude to US refineries.", [[52.67, -111.3], [50.0, -104.0], [40.0, -97.0], [35.98, -96.77], [29.9, -93.93]]),
    P("Keystone XL", "oil", "Alberta", "Nebraska", "cancelled", "Cancelled in 2021 after years of fights; never built.", [[52.67, -111.3], [49.0, -107.0], [45.5, -103.5], [42.5, -99.5], [40.0, -97.0]]),
    P("Trans Mountain", "oil", "Alberta", "Pacific coast (Vancouver)", "flowing", "Expanded in 2024 to carry about three times as much, opening Asian markets to Canadian oil.", [[53.55, -113.5], [50.67, -120.3], [49.25, -122.97]]),
    P("Colonial Pipeline", "oil", "Gulf Coast (Houston)", "New York area", "flowing", "Refined fuel for much of the US East Coast. A 2021 ransomware attack shut it for days.", [[29.76, -95.37], [30.45, -91.15], [33.75, -84.39], [36.07, -79.79], [40.63, -74.24]]),
    P("Transmed", "gas", "Algeria", "Italy", "flowing", "North African gas to Italy through Tunisia and Sicily.", [[32.93, 3.27], [35.5, 8.5], [36.8, 11.0], [37.65, 12.59], [38.2, 15.55], [41.0, 15.0], [44.6, 11.5]]),
    P("Langeled", "gas", "Norway", "United Kingdom", "flowing", "Norway is now Europe's biggest gas supplier; this line feeds Britain.", [[62.85, 6.95], [58.5, 3.5], [53.65, 0.12]]),
    P("Baltic Pipe", "gas", "Norway", "Poland (through Denmark)", "flowing", "Opened in 2022 to replace Russian gas in Poland.", [[56.5, 6.5], [55.5, 9.5], [55.2, 12.0], [54.2, 15.7]]),
    P("EACOP", "oil", "Uganda", "Tanzania coast (Tanga)", "building", "The world's longest heated crude pipeline, under construction.", [[1.43, 31.35], [-1.5, 32.0], [-4.5, 36.0], [-5.07, 39.1]])
  ];
  var PST = { flowing: "#34d399", reduced: "#f5c542", disrupted: "#ff5f57", offline: "#8f918a", cancelled: "#62645e", building: "#60a5fa" };
  var DEAD = { offline: 1, cancelled: 1, building: 1 };
  function pipeTip(p) { return '<div class="ptip"><b>' + esc(p.name) + (p.status === "cancelled" ? " (cancelled)" : "") + "</b><span>" + p.kind.toUpperCase() + " PIPELINE · <b style=\"color:" + PST[p.status] + '">' + p.status.toUpperCase() + "</b></span><span class=\"pdir\">" + esc(p.from) + " → " + esc(p.to) + "</span></div>"; }
  var LVL = { war: { name: "major war", v: "--war" }, armed: { name: "armed conflict", v: "--armed" }, unrest: { name: "unrest", v: "--unrest" } };
  var ET = {
    clash: { name: "clashes", col: "#e5484d", g: '<path d="M-5,-5L5,5M5,-5L-5,5" stroke="#fff" stroke-width="2.2" stroke-linecap="round"/>' },
    shelling: { name: "shelling", col: "#e5484d", g: '<path d="M0,-6L1.6,-2L6,-2.2L2.6,0.8L4,5.2L0,2.6L-4,5.2L-2.6,0.8L-6,-2.2L-1.6,-2Z" fill="#fff"/>' },
    drone: { name: "drone attack", col: "#e5484d", g: '<path d="M0,-6L5.5,4L0,1.4L-5.5,4Z" fill="#fff"/>' },
    missile: { name: "missile / airstrike", col: "#e5484d", g: '<path d="M-1.4,-6.5h2.8v8.5l2.8,3h-8.4l2.8,-3z" fill="#fff"/>' },
    blast: { name: "explosion", col: "#f97316", g: '<path d="M0,-7L1.5,-2.5L6,-4L3,0L6.5,3L2,2.5L1,7L-1.5,3L-6,5L-3.5,0.5L-6.5,-3.5L-2,-2.5Z" fill="#fff"/>' },
    fire: { name: "fire", col: "#f97316", g: '<path d="M0,-6.5C3.5,-2 5,1.5 0,6.5C-5,1.5 -3,-1.5 0,-6.5Z" fill="#fff"/>' },
    alert: { name: "air-raid alert", col: "#f5a524", g: '<path d="M-1.2,-5.5h2.4l-.5,7h-1.4z M0,3.2a1.3,1.3 0 1,0 .01,0" fill="#0a0a0a"/>' },
    politics: { name: "politics", col: "#3b82f6", g: '<path d="M-6,-4.5L0,-7L6,-4.5z M-5,-3.5h2v6h-2z M-1,-3.5h2v6h-2z M3,-3.5h2v6h-2z M-6,3h12v2h-12z" fill="#fff"/>' },
    protest: { name: "protest", col: "#f59e0b", g: '<path d="M-6,-2h3l6,-4v12l-6,-4h-3z" fill="#0a0a0a"/>' },
    aid: { name: "humanitarian", col: "#14b8a6", g: '<path d="M-1.8,-6h3.6v4.2h4.2v3.6h-4.2v4.2h-3.6v-4.2h-4.2v-3.6h4.2z" fill="#fff"/>' },
    economy: { name: "economy", col: "#65a30d", g: '<text x="0" y="4" text-anchor="middle" font-size="11" font-weight="700" fill="#fff" font-family="JetBrains Mono,monospace">$</text>' },
    ship: { name: "shipping", col: "#0d9488", g: '<path d="M-6,1.5h12l-3,4.5h-6z M-1,-6h2v7h-2z M1,-5l4,3.5h-4z" fill="#fff"/>' },
    police: { name: "police / security", col: "#6366f1", g: '<path d="M0,-6.5L5.5,-4V0.5C5.5,4 0,6.5 0,6.5C0,6.5 -5.5,4 -5.5,0.5V-4Z" fill="#fff"/>' },
    defense: { name: "defense (not fighting)", col: "#6b7d3a", g: '<path d="M0,-6.5L5.5,-4V0.5C5.5,4 0,6.5 0,6.5C0,6.5 -5.5,4 -5.5,0.5V-4Z" fill="#fff"/><path d="M0,-3.6L1,-1.1L3.6,-1L1.6,.7L2.3,3.3L0,1.8L-2.3,3.3L-1.6,.7L-3.6,-1L-1,-1.1Z" fill="#6b7d3a"/>' }
  };
  function icon(type, r) {
    var t = ET[type]; r = r || 11;
    return '<svg width="' + (r * 2) + '" height="' + (r * 2) + '" viewBox="-11 -11 22 22" aria-hidden="true"><circle r="10" fill="' + t.col + '" stroke="#fff" stroke-width="1.2"/>' + t.g + "</svg>";
  }

  // regions: the liveuamap-style tabs. bbox = [[west, south], [east, north]]
  var REGIONS = [
    { id: "ukraine", name: "Ukraine", bbox: [[22.0, 44.0], [41.0, 52.6]], sides: ["Ukrainian", "Russian"],
      cities: [["Kyiv", "Київ", 50.45, 30.52, 1], ["Kharkiv", "Харків", 49.99, 36.23, 1], ["Odesa", "Одеса", 46.48, 30.72, 1], ["Dnipro", "Дніпро", 48.46, 35.05, 1], ["Zaporizhzhia", "Запоріжжя", 47.84, 35.14], ["Kherson", "Херсон", 46.64, 32.61], ["Mykolaiv", "Миколаїв", 46.97, 32.0], ["Donetsk", "Донецьк", 48.0, 37.8], ["Luhansk", "Луганськ", 48.57, 39.31], ["Kramatorsk", "Краматорськ", 48.72, 37.56], ["Pokrovsk", "Покровськ", 48.28, 37.18], ["Kupiansk", "Куп'янськ", 49.71, 37.61], ["Sumy", "Суми", 50.91, 34.8], ["Chernihiv", "Чернігів", 51.49, 31.29], ["Lviv", "Львів", 49.84, 24.03, 1], ["Zhytomyr", "Житомир", 50.25, 28.66], ["Vinnytsia", "Вінниця", 49.23, 28.47], ["Mariupol", "Маріуполь", 47.1, 37.55], ["Melitopol", "Мелітополь", 46.85, 35.37], ["Simferopol", "Сімферополь", 44.95, 34.1], ["Sevastopol", "Севастополь", 44.6, 33.52], ["Belgorod", "Белгород", 50.6, 36.59], ["Kursk", "Курск", 51.73, 36.19], ["Rostov-on-Don", "Ростов-на-Дону", 47.23, 39.72], ["Chișinău", "", 47.01, 28.86]] },
    { id: "sudan", name: "Sudan", bbox: [[21.5, 8.5], [38.8, 22.5]], sides: ["army (SAF)", "RSF"],
      cities: [["Khartoum", "الخرطوم", 15.5, 32.56, 1], ["Omdurman", "أم درمان", 15.64, 32.48], ["Port Sudan", "بورتسودان", 19.62, 37.22, 1], ["El Fasher", "الفاشر", 13.63, 25.35, 1], ["Nyala", "نيالا", 12.05, 24.88], ["El Obeid", "الأبيض", 13.18, 30.22], ["Kassala", "كسلا", 15.45, 36.4], ["Wad Madani", "ود مدني", 14.4, 33.52], ["Kadugli", "كادقلي", 11.01, 29.72], ["El Geneina", "الجنينة", 13.45, 22.45], ["Atbara", "عطبرة", 17.7, 33.98], ["N'Djamena", "", 12.13, 15.06], ["Juba", "", 4.85, 31.58]] },
    { id: "mideast", name: "Middle East", bbox: [[33.0, 29.0], [45.5, 38.0]], sides: [],
      cities: [["Damascus", "دمشق", 33.51, 36.29, 1], ["Beirut", "بيروت", 33.89, 35.5, 1], ["Jerusalem", "ירושלים", 31.77, 35.21, 1], ["Tel Aviv", "תל אביב", 32.08, 34.78], ["Gaza", "غزة", 31.5, 34.47], ["Amman", "عمّان", 31.95, 35.93, 1], ["Baghdad", "بغداد", 33.31, 44.36, 1], ["Aleppo", "حلب", 36.2, 37.16], ["Homs", "حمص", 34.73, 36.72], ["Mosul", "الموصل", 36.34, 43.13], ["Erbil", "هەولێر", 36.19, 44.01], ["Deir ez-Zor", "دير الزور", 35.33, 40.14], ["Haifa", "חיפה", 32.79, 34.99], ["Tyre", "صور", 33.27, 35.2]] },
    { id: "iran", name: "Iran", bbox: [[43.5, 24.5], [63.5, 40.0]], sides: [],
      cities: [["Tehran", "تهران", 35.69, 51.39, 1], ["Isfahan", "اصفهان", 32.65, 51.67, 1], ["Mashhad", "مشهد", 36.3, 59.6, 1], ["Tabriz", "تبریز", 38.08, 46.29], ["Shiraz", "شیراز", 29.59, 52.58], ["Bandar Abbas", "بندرعباس", 27.18, 56.27], ["Ahvaz", "اهواز", 31.32, 48.67], ["Kermanshah", "کرمانشاه", 34.31, 47.07], ["Bushehr", "بوشهر", 28.97, 50.84], ["Qom", "قم", 34.64, 50.88], ["Zahedan", "زاهدان", 29.5, 60.86], ["Kerman", "کرمان", 30.28, 57.08]] },
    { id: "usa", name: "United States", bbox: [[-125.0, 24.0], [-66.0, 50.0]], sides: [],
      cities: [["Washington", "", 38.9, -77.04, 1], ["New York", "", 40.71, -74.0, 1], ["Chicago", "", 41.88, -87.63, 1], ["Los Angeles", "", 34.05, -118.24, 1], ["Houston", "", 29.76, -95.37], ["Atlanta", "", 33.75, -84.39], ["Miami", "", 25.76, -80.19], ["Seattle", "", 47.61, -122.33], ["Denver", "", 39.74, -104.99], ["Phoenix", "", 33.45, -112.07], ["Dallas", "", 32.78, -96.8], ["Boston", "", 42.36, -71.06], ["San Francisco", "", 37.77, -122.42]] },
    { id: "germany", name: "Germany", bbox: [[5.5, 47.2], [15.2, 55.1]], sides: [],
      cities: [["Berlin", "", 52.52, 13.4, 1], ["Hamburg", "", 53.55, 9.99, 1], ["Munich", "München", 48.14, 11.58, 1], ["Cologne", "Köln", 50.94, 6.96], ["Frankfurt", "", 50.11, 8.68, 1], ["Stuttgart", "", 48.78, 9.18], ["Düsseldorf", "", 51.23, 6.78], ["Leipzig", "", 51.34, 12.37], ["Dresden", "", 51.05, 13.74], ["Hanover", "Hannover", 52.37, 9.73], ["Bremen", "", 53.08, 8.8], ["Nuremberg", "Nürnberg", 49.45, 11.08]] }
  ];
  var LANG = { uk: "Ukrainian", ru: "Russian", ar: "Arabic", fa: "Persian", he: "Hebrew", ku: "Kurdish", de: "German", fr: "French", en: "English" };
  var FACTS = {
    "United States of America": ["US", "Washington, D.C.", "~335M", "US dollar", "English"], "Canada": ["CA", "Ottawa", "~41M", "Canadian dollar", "English, French"],
    "Mexico": ["MX", "Mexico City", "~130M", "Mexican peso", "Spanish"], "Brazil": ["BR", "Brasília", "~212M", "Brazilian real", "Portuguese"],
    "United Kingdom": ["GB", "London", "~69M", "Pound sterling", "English"], "France": ["FR", "Paris", "~68M", "Euro", "French"],
    "Germany": ["DE", "Berlin", "~84M", "Euro", "German"], "Ukraine": ["UA", "Kyiv", "~37M", "Hryvnia", "Ukrainian"],
    "Russia": ["RU", "Moscow", "~144M", "Ruble", "Russian"], "China": ["CN", "Beijing", "~1.41B", "Renminbi (yuan)", "Mandarin"],
    "India": ["IN", "New Delhi", "~1.44B", "Indian rupee", "Hindi, English"], "Japan": ["JP", "Tokyo", "~124M", "Yen", "Japanese"],
    "Australia": ["AU", "Canberra", "~27M", "Australian dollar", "English"], "Egypt": ["EG", "Cairo", "~110M", "Egyptian pound", "Arabic"],
    "Nigeria": ["NG", "Abuja", "~225M", "Naira", "English"], "Sudan": ["SD", "Khartoum (government based in Port Sudan)", "~50M", "Sudanese pound", "Arabic, English"],
    "Iran": ["IR", "Tehran", "~90M", "Iranian rial", "Persian"], "Saudi Arabia": ["SA", "Riyadh", "~35M", "Saudi riyal", "Arabic"],
    "Turkey": ["TR", "Ankara", "~86M", "Turkish lira", "Turkish"], "South Africa": ["ZA", "Pretoria (executive)", "~63M", "Rand", "12 official languages"],
    "Myanmar": ["MM", "Naypyidaw", "~55M", "Kyat", "Burmese"], "Dem. Rep. Congo": ["CD", "Kinshasa", "~110M", "Congolese franc", "French"],
    "Yemen": ["YE", "Sana'a (contested)", "~35M", "Yemeni rial", "Arabic"], "Taiwan": ["TW", "Taipei", "~23M", "New Taiwan dollar", "Mandarin"],
    "Israel": ["IL", "Jerusalem (disputed)", "~10M", "Shekel", "Hebrew, Arabic"], "Syria": ["SY", "Damascus", "~24M", "Syrian pound", "Arabic"],
    "Lebanon": ["LB", "Beirut", "~5.8M", "Lebanese pound", "Arabic"], "Iraq": ["IQ", "Baghdad", "~46M", "Iraqi dinar", "Arabic, Kurdish"],
    "Poland": ["PL", "Warsaw", "~37M", "Złoty", "Polish"], "Italy": ["IT", "Rome", "~59M", "Euro", "Italian"], "Spain": ["ES", "Madrid", "~48M", "Euro", "Spanish"],
    "Haiti": ["HT", "Port-au-Prince", "~12M", "Gourde", "Haitian Creole, French"], "Somalia": ["SO", "Mogadishu", "~19M", "Somali shilling", "Somali, Arabic"],
    "Ethiopia": ["ET", "Addis Ababa", "~130M", "Birr", "Amharic and others"], "Kenya": ["KE", "Nairobi", "~56M", "Kenyan shilling", "Swahili, English"],
    "Argentina": ["AR", "Buenos Aires", "~46M", "Argentine peso", "Spanish"], "Indonesia": ["ID", "Jakarta", "~280M", "Rupiah", "Indonesian"],
    "South Korea": ["KR", "Seoul", "~52M", "Won", "Korean"], "North Korea": ["KP", "Pyongyang", "~26M", "North Korean won", "Korean"], "Pakistan": ["PK", "Islamabad", "~245M", "Pakistani rupee", "Urdu, English"]
  };
