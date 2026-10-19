"""
Archie World - the live globe of world news, conflict, disasters and markets.

How it fits together
  * A small web server runs inside Archie (only on this PC, 127.0.0.1).
    The globe window is Microsoft Edge in "app mode" pointed at it, so it
    looks like its own program, not a browser tab.
  * While you're online, background jobs pull public feeds on a slow timer:
    earthquakes (USGS), disasters (GDACS), volcanoes (Smithsonian), news
    (RSS from outlets around the world + Google News searches in local
    languages), public Telegram channels, markets (Yahoo / FRED / an
    economic calendar / Nasdaq earnings / Polymarket), front lines
    (DeepState, if reachable) and weather radar (RainViewer tiles).
  * Everything lands in World/world.db (SQLite) so the time slider, the
    nightly digest and "ask the map" work from what's already stored.
  * Only non-English posts and Telegram posts go through the local model
    (translate + pull out the place and what happened), a few at a time,
    so the GPU stays cool. English headlines are sorted with plain rules.

Nothing here is required for the rest of Archie. If you're offline the
globe shows whatever was pulled last.
"""

import datetime
import email.utils
import gzip
import hashlib
import html
import unicodedata
import io
import json
import math
import os
import random
import re
import sqlite3
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
import xml.etree.ElementTree as ET
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

APP_DIR = os.path.dirname(os.path.abspath(__file__))
WORLD_DIR = os.path.join(APP_DIR, "World")
WEB_DIR = os.path.join(WORLD_DIR, "web")
GEO_DIR = os.path.join(WORLD_DIR, "geo")
TILE_DIR = os.path.join(WORLD_DIR, "tiles")
SAVED_DIR = os.path.join(WORLD_DIR, "Saved Articles")
DB_PATH = os.path.join(WORLD_DIR, "world.db")
SOURCES_PATH = os.path.join(WORLD_DIR, "sources.json")
WATCH_PATH = os.path.join(WORLD_DIR, "watch.json")
NAV_PENDING = os.path.join(WORLD_DIR, "pending_nav.txt")
RULES_PATH = os.path.join(WORLD_DIR, "label_rules.json")
FLAG_DIR = os.path.join(WORLD_DIR, "flags")            # country flags from Wikimedia, kept on this PC
GOLD_DIR = os.path.join(WORLD_DIR, "golden-record")   # the Golden Record's pictures, downloaded from NASA the first time you open the album
FONTS_DIR = os.path.join(APP_DIR, "fonts")
PORT = 8765
VERSION = "3.26.0"       # the page checks this; if it differs, an old Archie is still running
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0 Safari/537.36")
TILE_CACHE_MB = 600

# ---------------------------------------------------------------------------
# Default sources. World/sources.json is created from this the first time;
# edit that file to add or remove feeds. Bad ones show up in the Sources panel.
# side: which side of a conflict the source speaks for (shown on every report)
# lean: for US outlets, used for the left / center / right coverage bar
# ---------------------------------------------------------------------------
DEFAULT_SOURCES = {
    "rss": [
        {"name": "BBC World", "url": "http://feeds.bbci.co.uk/news/world/rss.xml", "lean": "center"},
        {"name": "Al Jazeera", "url": "https://www.aljazeera.com/xml/rss/all.xml"},
        {"name": "DW", "url": "https://rss.dw.com/rdf/rss-en-all"},
        {"name": "France 24", "url": "https://www.france24.com/en/rss"},
        {"name": "The Guardian", "url": "https://www.theguardian.com/world/rss", "lean": "left"},
        {"name": "NPR", "url": "https://feeds.npr.org/1004/rss.xml", "lean": "left"},
        {"name": "Politico", "url": "https://rss.politico.com/politics-news.xml", "lean": "left"},
        {"name": "The Hill", "url": "https://thehill.com/news/feed/", "lean": "center"},
        {"name": "Fox News", "url": "https://moxie.foxnews.com/google-publisher/world.xml", "lean": "right"},
        {"name": "New York Post", "url": "https://nypost.com/feed/", "lean": "right"},
        {"name": "CNBC", "url": "https://www.cnbc.com/id/100003114/device/rss/rss.html", "lean": "center"},
        {"name": "Ukrainska Pravda", "url": "https://www.pravda.com.ua/eng/rss/", "side": "Ukrainian"},
        {"name": "Meduza", "url": "https://meduza.io/rss/en/all", "side": "Russian independent"},
        {"name": "TASS", "url": "https://tass.com/rss/v2.xml", "side": "Russian state"},
        {"name": "Times of Israel", "url": "https://www.timesofisrael.com/feed/", "side": "Israeli"},
        {"name": "Tehran Times", "url": "https://www.tehrantimes.com/rss", "side": "Iranian state"},
        {"name": "Tagesschau", "url": "https://www.tagesschau.de/xml/rss2/", "lang": "de"},
        {"name": "Der Spiegel (English)", "url": "https://www.spiegel.de/international/index.rss"},
        {"name": "ReliefWeb (UN OCHA)", "url": "https://reliefweb.int/updates/rss.xml", "side": "UN humanitarian"}
    ],
    # Google News searches: local-language press from the places themselves
    "gnews": [
        {"name": "Ukraine (Ukrainian press)", "q": "Україна фронт", "hl": "uk", "gl": "UA", "region": "ukraine"},
        {"name": "Sudan (Arabic press)", "q": "السودان الفاشر OR الخرطوم", "hl": "ar", "gl": "SD", "region": "sudan"},
        {"name": "Iran (Persian press)", "q": "ایران", "hl": "fa", "gl": "IR", "region": "iran"},
        {"name": "Lebanon & Syria (Arabic press)", "q": "لبنان OR سوريا", "hl": "ar", "gl": "LB", "region": "mideast"},
        {"name": "Germany (German press)", "q": "Bundesregierung OR Bundestag", "hl": "de", "gl": "DE", "region": "germany"},
        {"name": "Washington", "q": "White House OR Congress OR Senate", "hl": "en-US", "gl": "US", "region": "usa"},
        {"name": "Sudan (English)", "q": "Sudan RSF army", "hl": "en-US", "gl": "US", "region": "sudan"},
        {"name": "Red Sea shipping", "q": "Red Sea shipping Houthi", "hl": "en-US", "gl": "US"},
        {"name": "Kyiv Independent", "q": "site:kyivindependent.com", "hl": "en-US", "gl": "US", "side": "Ukrainian"},
        {"name": "Sudan Tribune", "q": "site:sudantribune.com", "hl": "en-US", "gl": "US"}
    ],
    # public Telegram channels (read through t.me/s/<name>, no account needed)
    "telegram": [
        {"name": "DeepStateUA", "side": "Ukrainian", "lang": "uk", "cc": "UA"},
        {"name": "kyivindependent_official", "side": "Ukrainian", "lang": "en", "cc": "UA"},
        {"name": "rybar", "side": "Russian (milblogger)", "lang": "ru", "cc": "UA"}
    ],
    # prediction-market questions to show (matched against Polymarket's biggest markets)
    "polymarket_keywords": ["Fed", "rate cut", "recession", "ceasefire", "oil", "Bitcoin", "election", "tariff"],
    # close to home: local news searches for the news brief
    "local": [{"name": "Close to home", "q": "\"Your County\" OR \"Your Town\""}],
    "firms_map_key": "",       # free NASA FIRMS key for wildfires (optional)
    # GDELT: a free global database of events pulled from news in 100+ languages
    "gdelt": [{"region": "ukraine", "q": "(drone OR shelling OR missile OR offensive) (Ukraine OR Russia)"},
              {"region": "sudan", "q": "Sudan (RSF OR army OR fighting OR attack)"},
              {"region": "mideast", "q": "(Gaza OR Lebanon OR Syria OR Israel) (strike OR attack OR raid OR clashes)"},
              {"region": "iran", "q": "Iran (protest OR strike OR attack OR arrested)"},
              {"region": None, "q": "(airstrike OR clashes OR militants OR \"armed group\" OR insurgents)"}],
    # ACLED: checked conflict data. Needs a free account at acleddata.com; what a free account can see is limited.
    "acled_email": "",
    "acled_password": "",
    "tiles": True,             # street-level map when zoomed in (cached on this PC)
    # where the street map comes from. OpenStreetMap is free for light personal use; Archie
    # darkens it to match. If you get a key from a provider (CARTO, Stadia, MapTiler), put
    # its URL here with {z}/{x}/{y} and set tile_dark to false.
    "tile_url": "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
    "tile_dark": True,
    # a starting point for the conflict shading, from the public conflict datasets (UCDP / ACLED)
    # as of mid-2026. This week's reports can raise a country's level; edit freely.
    "conflict_baseline": {
        "Ukraine": "war", "Sudan": "war", "Myanmar": "war",
        "Palestine": "armed", "Dem. Rep. Congo": "armed", "Mali": "armed", "Burkina Faso": "armed", "Niger": "armed",
        "Nigeria": "armed", "Somalia": "armed", "Yemen": "armed", "Syria": "armed", "Haiti": "armed", "Ethiopia": "armed",
        "S. Sudan": "armed", "Mozambique": "armed", "Pakistan": "armed", "Cameroon": "armed", "Central African Rep.": "armed",
        "Colombia": "unrest", "Mexico": "unrest", "Lebanon": "unrest", "Iraq": "unrest", "Libya": "unrest", "Chad": "unrest"
    }
}

DEFAULT_WATCH = {
    "items": [{"kind": "region", "id": "ukraine"}, {"kind": "region", "id": "sudan"},
              {"kind": "region", "id": "mideast"}, {"kind": "region", "id": "iran"},
              {"kind": "choke", "id": "Bab el-Mandeb"}, {"kind": "choke", "id": "Strait of Hormuz"},
              {"kind": "asset", "id": "CL=F", "pct": 3}, {"kind": "asset", "id": "^GSPC", "pct": 2},
              {"kind": "asset", "id": "BTC-USD", "pct": 6}],
    "quake_min": 6.3,
    "quiet_hours": [23, 7],    # no pop-ups between 11 pm and 7 am (they wait for morning)
    "follow": ["video games, game studio", "animation", "AI, artificial intelligence"],   # topics in the news brief
    "mute": [],                # topics you never want in the news brief
    "brief_hour": 6,           # the news brief's morning edition is written at this hour
    "big_story_outlets": 0     # outlets that make a story "big" enough to offer a brief refresh (0 = as big as the morning's top story)
}

# regions: the liveuamap-style tabs ([west, south], [east, north])
REGIONS = {
    "ukraine": ((22.0, 44.0), (41.0, 52.6)),
    "sudan": ((21.5, 8.5), (38.8, 22.5)),
    "mideast": ((33.0, 29.0), (45.5, 38.0)),
    "iran": ((43.5, 24.5), (63.5, 40.0)),
    "usa": ((-125.0, 24.0), (-66.0, 50.0)),
    "germany": ((5.5, 47.2), (15.2, 55.1)),
}
REGION_NAMES = {"ukraine": "Ukraine", "sudan": "Sudan", "mideast": "Middle East", "iran": "Iran",
                "usa": "United States", "germany": "Germany"}

# markets: Yahoo symbols. (label, symbol, group, decimals, unit)
MARKETS = [
    ("S&P 500 futures", "ES=F", "US futures", 0, ""), ("Nasdaq 100 futures", "NQ=F", "US futures", 0, ""),
    ("Dow futures", "YM=F", "US futures", 0, ""), ("Russell 2000 futures", "RTY=F", "US futures", 0, ""),
    ("S&P 500", "^GSPC", "US stocks", 0, ""), ("Nasdaq 100", "^NDX", "US stocks", 0, ""),
    ("STOXX 600", "^STOXX", "Europe", 1, ""), ("DAX", "^GDAXI", "Europe", 0, ""), ("FTSE 100", "^FTSE", "Europe", 0, ""),
    ("CAC 40", "^FCHI", "Europe", 0, ""),
    ("Nikkei 225", "^N225", "Asia", 0, ""), ("Hang Seng", "^HSI", "Asia", 0, ""), ("Shanghai", "000001.SS", "Asia", 0, ""),
    ("KOSPI", "^KS11", "Asia", 0, ""), ("Sensex", "^BSESN", "Asia", 0, ""),
    ("Dollar index", "DX-Y.NYB", "FX", 2, ""), ("EUR/USD", "EURUSD=X", "FX", 4, ""), ("USD/JPY", "JPY=X", "FX", 2, ""),
    ("GBP/USD", "GBPUSD=X", "FX", 4, ""), ("USD/CNY", "CNY=X", "FX", 3, ""), ("USD/MXN", "MXN=X", "FX", 2, ""),
    ("WTI crude", "CL=F", "Commodities", 2, ""), ("Brent crude", "BZ=F", "Commodities", 2, ""),
    ("Natural gas", "NG=F", "Commodities", 2, ""), ("Gold", "GC=F", "Commodities", 0, ""), ("Silver", "SI=F", "Commodities", 2, ""),
    ("Copper", "HG=F", "Commodities", 2, ""), ("Wheat", "ZW=F", "Commodities", 0, ""),
    ("Bitcoin", "BTC-USD", "Crypto", 0, ""), ("Ethereum", "ETH-USD", "Crypto", 0, ""),
    ("VIX", "^VIX", "Volatility", 1, ""),
    # S&P 500 sectors (for the heatmap)
    ("Tech", "XLK", "Sectors", 2, ""), ("Comm. services", "XLC", "Sectors", 2, ""), ("Cons. discretionary", "XLY", "Sectors", 2, ""),
    ("Financials", "XLF", "Sectors", 2, ""), ("Health care", "XLV", "Sectors", 2, ""), ("Industrials", "XLI", "Sectors", 2, ""),
    ("Energy", "XLE", "Sectors", 2, ""), ("Materials", "XLB", "Sectors", 2, ""), ("Utilities", "XLU", "Sectors", 2, ""),
    ("Real estate", "XLRE", "Sectors", 2, ""), ("Cons. staples", "XLP", "Sectors", 2, ""),
]
# exchange index symbols (for the exchange cards on the globe)
EXCHANGE_INDEX = {"NYSE": "^GSPC", "NASDAQ": "^NDX", "TSX": "^GSPTSE", "BMV": "^MXX", "B3": "^BVSP", "LSE": "^FTSE",
                  "EPA": "^FCHI", "XETRA": "^GDAXI", "SIX": "^SSMI", "BIST": "XU100.IS", "TASE": "TA35.TA",
                  "EGX": "^CASE30", "TADAWUL": "^TASI.SR", "DFM": "^DFMGI", "JSE": "^J203.JO", "NSE": "^NSEI",
                  "SSE": "000001.SS", "HKEX": "^HSI", "TSE": "^N225", "KRX": "^KS11", "TWSE": "^TWII", "SGX": "^STI",
                  "IDX": "^JKSE", "ASX": "^AXJO"}
FRED_CURVE = [("3M", "DGS3MO"), ("6M", "DGS6MO"), ("1Y", "DGS1"), ("2Y", "DGS2"), ("3Y", "DGS3"), ("5Y", "DGS5"),
              ("7Y", "DGS7"), ("10Y", "DGS10"), ("20Y", "DGS20"), ("30Y", "DGS30")]
FRED_OTHER = [("US high-yield spread", "BAMLH0A0HYM2"), ("US inv. grade spread", "BAMLC0A0CM"),
              ("Fed funds upper", "DFEDTARU"), ("Fed funds lower", "DFEDTARL"), ("ECB deposit rate", "ECBDFR")]

# ---------------------------------------------------------------------------
# Sorting headlines without the model
# ---------------------------------------------------------------------------
ETYPES = [  # checked in order; first match wins
    ("alert", r"\bair[- ]raid|\bsirens?\b|\balert (?:in|across|for)\b"),
    ("drone", r"\bdrones?\b|\buavs?\b|\bshahed"),
    ("missile", r"\bmissiles?\b|\bair ?strikes?\b|\bbombing|\bbombed|\bballistic|\bstrikes? (?:on|hit)"),
    ("shelling", r"\bshell(?:ing|ed|s)\b|\bartillery\b|\bmortar|\brocket fire|\brockets\b"),
    ("clash", r"\bclash|\battack(?:s|ed)? (?:on|near)\b|\brepel|\bfighting\b|\bbattle|\bassault|\boffensive\b|\bfirefight|\bgunmen|\bambush|\btroops advance|\bfront ?line"),
    ("blast", r"\bexplosions?\b|\bblasts?\b|\bexplod"),
    ("fire", r"(?<!cease)\bfire\b(?!works)|\bblaze\b|\bwildfire"),
    ("aid", r"\bhumanitarian|\baid\b|\brefugees?\b|\bdisplaced|\bfamine|\bevacuat|\bcholera"),
    ("protest", r"\bprotest|\bdemonstrat|\brall(?:y|ies)\b|\bgeneral strike|\bwalkout|\briot"),
    ("ship", r"\btanker|\bshipping\b|\bvessel|\bnavy\b|\bnaval\b|\bfreighter|\bcargo ship"),
    ("police", r"\bpolice\b|\barrest|\bdetain|\bsecurity forces|\braid\b"),
    ("economy", r"\binflation|\bcurrency|\binterest rates?|\bstocks?\b|\bmarkets?\b|\btariff|\bgdp\b|\brecession|\bbank\b|\bprices\b"),
    ("politics", r"\bparliament|\belection|\bvote\b|\bminister|\bpresident|\bsenate|\bcongress|\bbundestag|\bcourt\b|\bbill\b|\bcabinet|\bsummit|\btalks\b|\bsanction|\bdiplomat"),
]
ETYPES_RE = [(k, re.compile(p, re.I)) for k, p in ETYPES]
# English headlines use "battle", "assault", "strike" loosely ("a battle over the budget").
# A military label only sticks if the headline also sounds like actual fighting.
WAR_CTX = re.compile(r"\btroops?\b|\barmy\b|\bmilitary\b|\bforces\b|\bdrones?\b|\bmissiles?\b|\bshell|\bartillery|\brebels?\b|"
                     r"\bmilitia|\binsurgent|\bair ?strike|\bfront\b|\bwar\b|\bceasefire|\bRSF\b|\bHamas\b|\bHezbollah|"
                     r"\bHouthi|\bIDF\b|\bsoldiers?\b|\bkilled\b|\bwounded\b|\bcasualt|\bbomb|\bjihad|\bgunmen|\bfighters\b", re.I)
MILITARY = {"clash", "shelling", "drone", "missile", "blast", "alert"}
# Words that show a translated sentence really is about fighting (used to double-check the small model).
FIGHT_RE = re.compile(r"\benem(?:y|ies)\b|\boccup(?:iers?|ied)\b|\bshot down\b|\bintercept|\bstruck\b|\bstrikes?\b|"
                      r"\badvanc|\bfront ?line|\bpositions?\b|\bbrigade|\bbattalion|\bshelled\b|\bexplosions?\b|\bblasts?\b|"
                      r"\bgunfire|\bgunshots?|\bgrenade|\bair ?raid|\bsirens?\b|\battack", re.I)


def looks_military(text):
    t = text or ""
    return bool(WAR_CTX.search(t) or FIGHT_RE.search(t) or
                any(rx.search(t) for k, rx in ETYPES_RE if k in MILITARY))


def check_type(model_type, english):
    """The small model sometimes grabs a fighting label for ordinary news (a court case, a pet dispute).
    Keep its label only if its own English sentence sounds like fighting; otherwise sort by the words."""
    if model_type not in TYPES or model_type == "other":
        return classify(english, strict=True)
    if model_type in MILITARY and not looks_military(english):
        return classify(english, strict=True)
    return refine(model_type, english)
TOPIC_OF = {"clash": "conflict", "shelling": "conflict", "drone": "conflict", "missile": "conflict", "blast": "conflict",
            "alert": "conflict", "fire": "climate", "aid": "health", "protest": "politics", "ship": "economy",
            "police": "politics", "economy": "economy", "politics": "politics", "defense": "politics"}
SCIENCE_RE = re.compile(r"\bscien|\bspace\b|\bnasa\b|\bresearch|\bAI\b|\bchip|\btech", re.I)
HEALTH_RE = re.compile(r"\bhealth|\bvirus|\bvaccin|\boutbreak|\bdisease|\bhospital", re.I)
CLIMATE_RE = re.compile(r"\bclimate|\bheatwave|\bdrought|\bflood|\bstorm|\bhurricane|\btyphoon|\bearthquake", re.I)
DISRUPT_RE = re.compile(r"\battack|\bhalt|\bshut|\bclos(?:ed|es|ure)|\bblock|\bexplosion|\bsuspend|\bseiz|\bdamag|\bsabotag|\bleak", re.I)

STOP = set("""a an the of in on at to for from by with and or but as is are was were be been has have had it its
this that these those after before over under into near amid says said say new will would could may might not no
than more most less up down out about against between during without within via per vs just also""".split())


# Defense news: about the military, but not fighting (budgets, arms deals, exercises, NATO).
DEFENSE_RE = re.compile(
    r"\bdefen[cs]e (?:budget|spending|minist|secretar|chief|pact|deal|contract|industr|firm|compan|procurement|agreement|"
    r"cooperation|export|bill|plan|review|strategy|summit|official|stock|giant|group|forces? chief)|"
    r"\bmilitary (?:aid|spending|budget|exercises?|drills?|parade|procurement|contract|buildup|build-up|cooperation|package|"
    r"base|reform|service|academy|industr|funding)|\barms (?:deals?|sales?|packages?|exports?|imports?|shipments?|deliver|embargo|"
    r"control|race|makers?|industry|fair)|\bweapons? (?:deals?|sales?|packages?|deliver|shipments?|contracts?|makers?|exports?|"
    r"production|factory|plant|aid)|\bNATO\b|\bPentagon\b|\bwar ?games\b|\bjoint (?:exercises?|drills?|patrols?)|"
    r"\bnaval (?:drills?|exercises?)|\bconscription|\bdraft (?:law|age|dodg)|\bmobili[sz]ation (?:law|plan|age)|\brearm|"
    r"\b(?:F-16|F-35|Patriot|HIMARS|Leopard|Abrams|Taurus|Tomahawk|Gripen|Rafale|Eurofighter)s? (?:deliver|shipments?|deal|order|"
    r"purchase|package|batch|arriv|contract|sale|jets? arriv)|\bammunition (?:shipments?|deliver|production|plant|factory|supply)|"
    r"\bRheinmetall|\bLockheed|\bRaytheon|\bNorthrop|\bBAE Systems|\bGeneral Dynamics|\bSaab\b|\bThales\b|\bLeonardo\b|"
    r"\bsecretary of (?:defen[cs]e|war)|\bdefen[cs]e secretary|\bdefen[cs]e minister", re.I)
# ...unless the headline also reports actual violence.
ATTACK_RE = re.compile(r"\bkill(?:ed|s|ing)\b|\bwounded\b|\binjur|\bdead\b|\bstruck\b|\bhits?\b|\bshot down|\bintercept|"
                       r"\battack(?:s|ed)? (?:on|near)|\bshell(?:ed|ing)\b|\bstrikes? (?:on|hit)|\bexplosion|\bcasualt|"
                       r"\bclashes\b|\bfighting\b|\bbombard|\bdrone attack|\bmissile attack", re.I)
TYPES = set(dict(ETYPES)) | {"defense"}

# ---------------------------------------------------------------------------
# Markets that depend on a strait, pipeline or country (Yahoo symbols)
# ---------------------------------------------------------------------------
_M = {"brent": ("Brent crude", "BZ=F"), "wti": ("WTI crude", "CL=F"), "ttf": ("EU gas (TTF)", "TTF=F"),
      "ng": ("US natural gas", "NG=F"), "wheat": ("Wheat", "ZW=F"), "corn": ("Corn", "ZC=F"), "soy": ("Soybeans", "ZS=F"),
      "copper": ("Copper", "HG=F"), "gold": ("Gold", "GC=F"), "coffee": ("Coffee", "KC=F"), "cocoa": ("Cocoa", "CC=F"),
      "plat": ("Platinum", "PL=F"), "rbob": ("Gasoline", "RB=F"), "ho": ("Diesel / heating oil", "HO=F"),
      "fro": ("Frontline (tankers)", "FRO"), "dht": ("DHT (tankers)", "DHT"), "jets": ("Airlines ETF", "JETS"),
      "maersk": ("Maersk", "MAERSK-B.CO"), "zim": ("ZIM (containers)", "ZIM"), "hapag": ("Hapag-Lloyd", "HLAG.DE"),
      "sblk": ("Star Bulk (dry bulk)", "SBLK"), "lng": ("Cheniere (US LNG)", "LNG"), "tsm": ("TSMC", "TSM"),
      "soxx": ("Chip stocks ETF", "SOXX"), "ita": ("US defense stocks ETF", "ITA"), "rhm": ("Rheinmetall", "RHM.DE"),
      "mol": ("MOL (Hungarian refiner)", "MOL.BD"), "tte": ("TotalEnergies", "TTE"), "trp": ("TC Energy", "TRP")}
CHOKE_LINKS = {
    "Strait of Hormuz": [("brent", "about a fifth of the world's oil sails through it"), ("ttf", "Qatar's gas exports (LNG) go this way"),
                         ("fro", "tanker owner: rates jump when the strait is threatened"), ("dht", "tanker owner"),
                         ("jets", "jet fuel is airlines' biggest cost")],
    "Bab el-Mandeb": [("maersk", "reroutes around Africa when the Red Sea is unsafe"), ("zim", "Asia–Europe container line"),
                      ("hapag", "container line"), ("brent", "tankers to Europe pass here")],
    "Suez Canal": [("maersk", "reroutes around Africa when Suez is blocked"), ("zim", "Asia–Europe container line"),
                   ("hapag", "container line"), ("brent", "roughly 1 in 10 barrels traded by sea")],
    "Strait of Malacca": [("brent", "most of East Asia's oil imports pass here"), ("zim", "container line"),
                          ("sblk", "coal, grain and ore shipping")],
    "Panama Canal": [("soy", "US Gulf grain heads to Asia through it"), ("corn", "same route"), ("lng", "US gas cargoes to Asia"),
                     ("zim", "container line")],
    "Turkish Straits": [("wheat", "Black Sea grain from Ukraine and Russia"), ("corn", "Ukrainian corn exports"),
                        ("brent", "Russian and Kazakh oil")],
    "Taiwan Strait": [("tsm", "makes most of the world's advanced chips, in Taiwan"), ("soxx", "the whole chip industry leans on Taiwan"),
                      ("zim", "container line")],
    "Strait of Gibraltar": [("brent", "the Mediterranean's western door"), ("maersk", "container line")],
    "Dover Strait": [("maersk", "container line"), ("hapag", "container line")],
    "Danish Straits": [("brent", "Russia's Baltic oil exports pass here"), ("ttf", "Europe's gas price")],
    "Kerch Strait": [("wheat", "grain from the Sea of Azov ports"), ("brent", "Russian oil")],
    "Cape of Good Hope": [("maersk", "ships go this way when the Red Sea is closed"), ("zim", "container line"),
                          ("brent", "tankers rerouted around Africa")],
}
PIPE_KIND = {"Druzhba (northern leg)": "oil", "Druzhba (southern leg)": "oil", "Caspian Pipeline (CPC)": "oil", "Nord Stream": "gas",
             "Ukraine gas transit": "gas", "Yamal–Europe": "gas", "TurkStream": "gas", "Southern Gas Corridor (TANAP / TAP)": "gas",
             "Baku–Tbilisi–Ceyhan": "oil", "Kirkuk–Ceyhan": "oil", "East–West Pipeline (Petroline)": "oil", "Habshan–Fujairah": "oil",
             "SUMED": "oil", "Power of Siberia": "gas", "ESPO": "oil", "Central Asia–China": "gas", "Myanmar–China": "gas",
             "Trans-Alaska": "oil", "Keystone": "oil", "Keystone XL": "oil", "Trans Mountain": "oil", "Colonial Pipeline": "oil",
             "Transmed": "gas", "Langeled": "gas", "Baltic Pipe": "gas", "EACOP": "oil"}
PIPE_LINKS = {"Colonial Pipeline": [("rbob", "it carries refined fuel to the East Coast"), ("ho", "diesel and heating oil too")],
              "Keystone": [("wti", "Canadian crude into US refineries"), ("trp", "the company behind the Keystone system")],
              "Trans-Alaska": [("wti", "US oil price")], "Trans Mountain": [("wti", "North American oil price")],
              "Druzhba (northern leg)": [("brent", "Europe's oil price"), ("mol", "refiner that relies on Druzhba crude")],
              "Druzhba (southern leg)": [("brent", "Europe's oil price"), ("mol", "Hungary's refiner runs on this pipeline")],
              "EACOP": [("brent", "global oil price"), ("tte", "TotalEnergies leads the project")]}
COUNTRY_ETF = {"Germany": "EWG", "Japan": "EWJ", "United Kingdom": "EWU", "China": "FXI", "Brazil": "EWZ", "India": "INDA",
               "Mexico": "EWW", "South Korea": "EWY", "Taiwan": "EWT", "Canada": "EWC", "Australia": "EWA", "France": "EWQ",
               "Italy": "EWI", "Spain": "EWP", "Switzerland": "EWL", "Netherlands": "EWN", "Sweden": "EWD", "Turkey": "TUR",
               "Saudi Arabia": "KSA", "Israel": "EIS", "South Africa": "EZA", "Argentina": "ARGT", "Chile": "ECH", "Poland": "EPOL",
               "Indonesia": "EIDO", "Philippines": "EPHE", "Thailand": "THD", "Vietnam": "VNM", "Singapore": "EWS",
               "Hong Kong": "EWH", "New Zealand": "ENZL", "Peru": "EPU", "Colombia": "GXG", "Qatar": "QAT",
               "United Arab Emirates": "UAE", "Malaysia": "EWM", "Norway": "NORW", "Austria": "EWO", "Belgium": "EWK",
               "Egypt": "EGPT", "Nigeria": "NGE", "Greece": "GREK", "Ireland": "EIRL", "Denmark": "EDEN", "Finland": "EFNL",
               "United States": "SPY"}
COUNTRY_LINKS = {"Russia": [("brent", "oil is Russia's biggest export"), ("ttf", "Europe's gas price"), ("wheat", "world's top wheat exporter"),
                            ("rhm", "European arms maker that grew with the war")],
                 "Ukraine": [("wheat", "a top wheat exporter"), ("corn", "a top corn exporter"), ("rhm", "European arms maker supplying Ukraine")],
                 "Saudi Arabia": [("brent", "the world's biggest oil exporter")], "Iran": [("brent", "OPEC member; sits on Hormuz"), ("ita", "US defense stocks")],
                 "Iraq": [("brent", "OPEC's #2 producer")], "Kuwait": [("brent", "oil exporter")], "United Arab Emirates": [("brent", "oil exporter")],
                 "Qatar": [("ttf", "one of the world's biggest gas (LNG) exporters")], "Libya": [("brent", "oil exports swing with the fighting")],
                 "Nigeria": [("brent", "Africa's biggest oil producer")], "Venezuela": [("brent", "huge oil reserves")],
                 "Kazakhstan": [("brent", "exports oil through the CPC pipeline")], "Norway": [("brent", "oil exporter"), ("ttf", "Europe's biggest gas supplier")],
                 "Israel": [("ita", "US defense stocks")], "Yemen": [("brent", "the Houthis sit on the Red Sea route"), ("maersk", "container shipping")],
                 "Chile": [("copper", "the world's biggest copper producer")], "Peru": [("copper", "#2 copper producer")],
                 "Democratic Republic of the Congo": [("copper", "huge copper and cobalt mines")], "Zambia": [("copper", "copper exporter")],
                 "Ivory Coast": [("cocoa", "grows about 40% of the world's cocoa")], "Côte d'Ivoire": [("cocoa", "grows about 40% of the world's cocoa")],
                 "Ghana": [("cocoa", "#2 cocoa grower"), ("gold", "Africa's top gold producer")],
                 "Brazil": [("soy", "the top soybean exporter"), ("coffee", "the top coffee grower")], "Argentina": [("soy", "big soybean exporter")],
                 "Colombia": [("coffee", "big coffee grower"), ("brent", "oil exporter")], "Vietnam": [("coffee", "#2 coffee grower")],
                 "Ethiopia": [("coffee", "Africa's biggest coffee grower")], "South Africa": [("gold", "gold miner"), ("plat", "most of the world's platinum")],
                 "Taiwan": [("tsm", "the world's leading chipmaker"), ("soxx", "the chip industry")], "Egypt": [("wheat", "one of the biggest wheat buyers")],
                 "Sudan": [("gold", "gold funds both sides of the war")], "India": [("brent", "the #3 oil importer")],
                 "China": [("copper", "the biggest buyer of copper"), ("brent", "the biggest oil importer")], "Canada": [("wti", "oil exporter")],
                 "United States": [("wti", "US oil price")], "Germany": [("ttf", "Germany's industry runs on gas"), ("rhm", "Germany's biggest arms maker")],
                 "Panama": [("soy", "the canal carries US grain")]}


def market_links(kind, name, pk="", info=None):
    pick = []
    if kind == "choke":
        pick = CHOKE_LINKS.get(name) or [("brent", "global oil price"), ("sblk", "bulk shipping")]
    elif kind == "pipe":
        pk = pk or PIPE_KIND.get(name, "oil")
        pick = list(PIPE_LINKS.get(name) or [])
        base = [("brent", "Europe's and the world's oil price"), ("wti", "US oil price")] if pk == "oil" else \
               [("ttf", "Europe's gas price"), ("ng", "US gas price")]
        for b in base:
            if len(pick) < 3 and b[0] not in [x[0] for x in pick]:
                pick.append(b)
    out = [(_M[k][0], _M[k][1], why) for k, why in pick if k in _M]
    if kind == "country":
        etf = COUNTRY_ETF.get(name)
        if etf:
            out.append((f"{name} stocks ETF" if name != "United States" else "S&P 500 ETF", etf, "the country's stock market, in dollars"))
        cur = list(((info or {}).get("currencies") or {}).keys())
        c0 = cur[0] if cur else ""
        if c0 and c0 != "USD":
            if c0 in ("EUR", "GBP", "AUD", "NZD"):
                out.append((f"{c0}/USD", f"{c0}USD=X", "its currency: up means it's getting stronger"))
            else:
                out.append((f"USD/{c0}", f"{c0}=X", f"its currency: up means the {c0} is getting weaker"))
        out += [(_M[k][0], _M[k][1], why) for k, why in COUNTRY_LINKS.get(name, []) if k in _M]
    return out[:6]


# Corrections you made with the "wrong label" button: [{"word": "pig", "from": "shelling", "to": "other"}]
LABEL_RULES = []


def apply_rules(etype, text):
    if not LABEL_RULES or not text:
        return etype
    low = text.lower()
    for r in LABEL_RULES:
        w = (r.get("word") or "").lower()
        if not w or not re.search(r"(?<![a-z0-9])" + re.escape(w) + r"(?![a-z0-9])", low):
            continue
        frm = r.get("from") or "*"
        if frm == "*" or frm == (etype or "other") or (frm in MILITARY and etype in MILITARY):
            to = r.get("to")
            return None if to in (None, "", "other", "news") else to
    return etype


def refine(etype, text):
    """Defense override, then your own correction rules."""
    t = text or ""
    if etype in MILITARY or etype in (None, "politics", "economy", "police", "other", "ship"):
        if DEFENSE_RE.search(t) and not ATTACK_RE.search(t):
            etype = "defense"
    return apply_rules(etype, t)


def _classify_raw(text, strict=False):
    for k, rx in ETYPES_RE:
        if rx.search(text or ""):
            if strict and k in MILITARY and not WAR_CTX.search(text):
                continue
            return k
    return None


def classify(text, strict=False):
    """strict: English wire headlines, where military words need a war context."""
    return refine(_classify_raw(text, strict), text)


def topic_for(text, etype):
    if etype in TOPIC_OF and etype not in ("economy", "politics"):
        return TOPIC_OF[etype]
    if HEALTH_RE.search(text):
        return "health"
    if SCIENCE_RE.search(text):
        return "science"
    if CLIMATE_RE.search(text):
        return "climate"
    return TOPIC_OF.get(etype, "politics")


def tokens(text):
    return {w for w in re.findall(r"[a-z0-9]+", (text or "").lower()) if len(w) > 2 and w not in STOP}


def jaccard(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def km(lat1, lng1, lat2, lng2):
    p = math.pi / 180
    a = (math.sin((lat2 - lat1) * p / 2) ** 2 +
         math.cos(lat1 * p) * math.cos(lat2 * p) * math.sin((lng2 - lng1) * p / 2) ** 2)
    return 12742 * math.asin(min(1, math.sqrt(a)))


def region_of(lat, lng):
    if lat is None or lng is None:
        return None
    for rid, ((w, s), (e, n)) in REGIONS.items():
        if w <= lng <= e and s <= lat <= n:
            return rid
    return None


def now():
    return int(time.time())


def iso(ts):
    return datetime.datetime.fromtimestamp(ts).isoformat(timespec="minutes")


# ---------------------------------------------------------------------------
# Fetching
# ---------------------------------------------------------------------------
class FetchError(Exception):
    pass



def secrets_eq(a, b):
    import hmac
    return bool(a) and bool(b) and hmac.compare_digest(a, b)

def fetch(url, timeout=20, headers=None, raw=False, data=None):
    h = {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.8", "Accept-Encoding": "gzip"}
    h.update(headers or {})
    req = urllib.request.Request(url, headers=h, data=data)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read()
            if r.headers.get("Content-Encoding") == "gzip":
                body = gzip.decompress(body)
            if raw:
                return body, r.geturl(), r.headers.get("Content-Type", "")
            cs = r.headers.get_content_charset() or "utf-8"
            return body.decode(cs, errors="replace")
    except urllib.error.HTTPError as e:
        raise FetchError(f"HTTP {e.code}")
    except Exception as e:
        raise FetchError(str(e)[:120])


def fetch_json(url, **kw):
    try:
        return json.loads(fetch(url, **kw))
    except ValueError:
        raise FetchError("not JSON")


def online(timeout=3):
    for host in ("https://www.gstatic.com/generate_204", "https://1.1.1.1"):
        try:
            urllib.request.urlopen(urllib.request.Request(host, headers={"User-Agent": UA}), timeout=timeout)
            return True
        except urllib.error.HTTPError:
            return True
        except Exception:
            continue
    return False


def _t(el, *names):
    for n in names:
        x = el.find(n)
        if x is not None and (x.text or "").strip():
            return x.text.strip()
    return ""


def strip_tags(s):
    s = re.sub(r"<br\s*/?>", "\n", s or "", flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    return html.unescape(s).strip()


def parse_date(s):
    if not s:
        return None
    try:
        return int(email.utils.parsedate_to_datetime(s).timestamp())
    except Exception:
        pass
    try:
        s2 = s.strip().replace("Z", "+00:00")
        d = datetime.datetime.fromisoformat(s2)
        if d.tzinfo is None:
            d = d.replace(tzinfo=datetime.timezone.utc)
        return int(d.timestamp())
    except Exception:
        return None


def parse_feed(text):
    """RSS 2.0, RDF and Atom. Returns [{title, url, published, summary, author, source}]"""
    text = re.sub(r"^[^<]+", "", text)
    try:
        root = ET.fromstring(text.encode("utf-8"))
    except ET.ParseError as e:
        raise FetchError(f"feed not readable ({e})")
    out = []
    ns_atom = "{http://www.w3.org/2005/Atom}"
    items = root.iter("item")
    items = list(items) or list(root.iter("{http://purl.org/rss/1.0/}item"))
    for it in items:
        title = strip_tags(_t(it, "title", "{http://purl.org/rss/1.0/}title"))
        link = _t(it, "link", "{http://purl.org/rss/1.0/}link", "guid")
        pub = parse_date(_t(it, "pubDate", "{http://purl.org/dc/elements/1.1/}date", ns_atom + "updated"))
        desc = strip_tags(_t(it, "description", "{http://purl.org/rss/1.0/}description"))[:600]
        author = strip_tags(_t(it, "{http://purl.org/dc/elements/1.1/}creator", "author"))
        src = it.find("source")
        out.append({"title": title, "url": link, "published": pub, "summary": desc, "author": author,
                    "source": (src.text or "").strip() if src is not None else ""})
    if not out:
        for en in root.iter(ns_atom + "entry"):
            link = ""
            for l in en.findall(ns_atom + "link"):
                if l.get("rel", "alternate") == "alternate":
                    link = l.get("href", "")
            a = en.find(ns_atom + "author")
            out.append({"title": strip_tags(_t(en, ns_atom + "title")), "url": link,
                        "published": parse_date(_t(en, ns_atom + "published", ns_atom + "updated")),
                        "summary": strip_tags(_t(en, ns_atom + "summary", ns_atom + "content"))[:600],
                        "author": _t(a, ns_atom + "name") if a is not None else "", "source": ""})
    return [o for o in out if o["title"]]


def parse_telegram(page, channel):
    """Posts from https://t.me/s/<channel> (the public web preview)."""
    posts = []
    for block in re.split(r'<div class="tgme_widget_message_wrap', page)[1:]:
        m_id = re.search(r'data-post="([^"]+)"', block)
        m_txt = re.search(r'<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>', block, re.S)
        m_time = re.search(r'<time[^>]*datetime="([^"]+)"', block)
        if not (m_id and m_txt):
            continue
        text = strip_tags(m_txt.group(1))
        if len(text) < 25:
            continue
        posts.append({"id": m_id.group(1), "text": text[:1500], "url": "https://t.me/" + m_id.group(1),
                      "published": parse_date(m_time.group(1)) if m_time else None})
    return posts


# ---------------------------------------------------------------------------
# Places: GeoNames cities (downloaded once) + country names
# ---------------------------------------------------------------------------
BAD_PLACE_WORDS = set("""march may june july august mobile reading nice split bath police president new union
victoria independence liberty justice hope unity progress democracy freedom center centre university hospital
temple orange deal sale man mission opportunity success eagle phoenix? lincoln? jackson? washington?
""".replace("?", "").split()) - {"phoenix", "lincoln", "jackson", "washington"}


US_STATES = {"alabama": (32.8, -86.8), "alaska": (64.2, -150.0), "arizona": (34.3, -111.7), "arkansas": (34.9, -92.4),
    "california": (37.2, -119.5), "colorado": (39.0, -105.5), "connecticut": (41.6, -72.7), "delaware": (39.0, -75.5),
    "florida": (28.6, -82.4), "georgia": (32.7, -83.4), "hawaii": (20.8, -156.3), "idaho": (44.4, -114.6), "illinois": (40.0, -89.2),
    "indiana": (39.9, -86.3), "iowa": (42.1, -93.5), "kansas": (38.5, -98.4), "kentucky": (37.5, -85.3), "louisiana": (31.1, -92.0),
    "maine": (45.4, -69.2), "maryland": (39.0, -76.8), "massachusetts": (42.3, -71.8), "michigan": (44.3, -85.4),
    "minnesota": (46.3, -94.3), "mississippi": (32.7, -89.7), "missouri": (38.4, -92.5), "montana": (47.0, -109.6),
    "nebraska": (41.5, -99.8), "nevada": (39.3, -116.6), "new hampshire": (43.7, -71.6), "new jersey": (40.2, -74.7),
    "new mexico": (34.4, -106.1), "new york": (42.9, -75.5), "north carolina": (35.6, -79.4), "north dakota": (47.5, -100.5),
    "ohio": (40.3, -82.8), "oklahoma": (35.6, -97.5), "oregon": (43.9, -120.6), "pennsylvania": (40.9, -77.8),
    "rhode island": (41.7, -71.5), "south carolina": (33.9, -80.9), "south dakota": (44.4, -100.2), "tennessee": (35.9, -86.4),
    "texas": (31.5, -99.3), "utah": (39.3, -111.7), "vermont": (44.1, -72.7), "virginia": (37.5, -78.9), "washington state": (47.4, -120.5),
    "west virginia": (38.6, -80.6), "wisconsin": (44.6, -89.9), "wyoming": (43.0, -107.6)}
US_STATES_RE = re.compile(r"\b(" + "|".join(sorted((re.escape(k.title()) for k in US_STATES), key=len, reverse=True)) + r")\b")


def storm_name(text):
    """'Tropical Cyclone FAY-26. Population affected by ...' -> 'Fay'."""
    n = re.split(r"\.\s|\s+-\s+|:", str(text or ""))[0].strip()
    n = re.sub(r"^(tropical cyclone|tropical depression|tropical storm|super typhoon|major hurricane|hurricane|typhoon|cyclone|storm)\s+",
               "", n, flags=re.I)
    n = re.sub(r"-\d{2}$", "", n).strip()
    if len(n) > 22:
        n = n.split()[0]
    return n.title() if n else "Storm"


def _any_date(v):
    """Dates in whatever shape a feed uses (ISO, RFC 822, 30/09/2026 18:00)."""
    t = parse_date(v)
    if t:
        return t
    for fmt in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%d/%m/%Y", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y%m%d%H%M"):
        try:
            return int(datetime.datetime.strptime(v.strip()[:19], fmt).replace(tzinfo=datetime.timezone.utc).timestamp())
        except ValueError:
            continue
    return None


class Gazetteer:
    URL_CITIES = "https://download.geonames.org/export/dump/cities15000.zip"
    URL_COUNTRIES = "https://download.geonames.org/export/dump/countryInfo.txt"

    def __init__(self, folder):
        self.folder = folder
        self.names = {}         # lowercase name -> [(pop, lat, lng, cc, display)]
        self.countries = {}     # iso2 -> {"name", "capital", "lat", "lng"}
        self.by_country_name = {}
        self.ready = False
        self.status = "not loaded"

    def ensure(self):
        if self.ready:
            return True
        os.makedirs(self.folder, exist_ok=True)
        cache = os.path.join(self.folder, "places.json")
        if os.path.exists(cache):
            try:
                with open(cache, encoding="utf-8") as f:
                    d = json.load(f)
                self.names, self.countries = d["names"], d["countries"]
                self._finish()
                return True
            except Exception:
                pass
        try:
            raw, _, _ = fetch(self.URL_CITIES, timeout=90, raw=True)
            cinfo = fetch(self.URL_COUNTRIES, timeout=60)
        except FetchError as e:
            self.status = f"place names not downloaded yet ({e})"
            return False
        names = {}
        caps = {}
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            with z.open("cities15000.txt") as f:
                for line in io.TextIOWrapper(f, encoding="utf-8"):
                    p = line.rstrip("\n").split("\t")
                    if len(p) < 15:
                        continue
                    try:
                        lat, lng, pop = float(p[4]), float(p[5]), int(p[14] or 0)
                    except ValueError:
                        continue
                    cc, disp = p[8], p[1]
                    if p[7] == "PPLC":
                        caps[cc] = (lat, lng, disp)
                    alts = {p[1], p[2]}
                    for a in p[3].split(","):
                        if a.isupper() and len(a) <= 5:
                            continue            # codes like LAX, NYC
                        if 3 <= len(a) <= 40 and not re.search(r"[0-9]", a):
                            alts.add(a)
                    for a in alts:
                        k = a.lower()
                        if k in BAD_PLACE_WORDS:
                            continue
                        names.setdefault(k, []).append((pop, round(lat, 3), round(lng, 3), cc, disp))
        for k in names:
            names[k] = sorted(names[k], reverse=True)[:4]
        countries = {}
        for line in cinfo.splitlines():
            if not line or line.startswith("#"):
                continue
            p = line.split("\t")
            if len(p) < 6:
                continue
            iso2, name, capital = p[0], p[4], p[5]
            c = caps.get(iso2)
            countries[iso2] = {"name": name, "capital": capital, "lat": c[0] if c else None, "lng": c[1] if c else None}
        self.names, self.countries = names, countries
        try:
            with open(cache, "w", encoding="utf-8") as f:
                json.dump({"names": names, "countries": countries}, f)
        except OSError:
            pass
        self._finish()
        return True

    def _finish(self):
        self.by_country_name = {c["name"].lower(): iso2 for iso2, c in self.countries.items()}
        extra = {"russia": "RU", "iran": "IR", "syria": "SY", "gaza": "PS", "west bank": "PS", "palestine": "PS",
                 "the us": "US", "u.s.": "US", "united states": "US", "america": "US", "uk": "GB", "britain": "GB",
                 "south korea": "KR", "north korea": "KP", "dr congo": "CD", "congo": "CD", "taiwan": "TW",
                 "czech republic": "CZ", "ivory coast": "CI", "turkey": "TR", "türkiye": "TR", "burma": "MM",
                 "україна": "UA", "россия": "RU", "السودان": "SD", "ایران": "IR", "لبنان": "LB", "سوريا": "SY"}
        for k, v in extra.items():
            self.by_country_name.setdefault(k, v)
        self.ready = True
        self.status = f"{len(self.names):,} place names"

    def country_name(self, cc):
        c = self.countries.get(cc)
        return c["name"] if c else ""

    def nearest(self, lat, lng, min_pop=40000):
        """Closest sizable place: (name, country, km) or None."""
        if not self.ready:
            return None
        if not getattr(self, "_pts", None):
            seen, pts = set(), []
            for cands in self.names.values():
                for c in cands:
                    if c[0] >= min_pop and (c[1], c[2]) not in seen:
                        seen.add((c[1], c[2]))
                        pts.append(c)
            self._pts = pts
        best, bd = None, 1e9
        for c in self._pts:
            if abs(c[1] - lat) > 8:
                continue
            d = km(lat, lng, c[1], c[2])
            if d < bd:
                best, bd = c, d
        if not best:
            return None
        return best[4], self.country_name(best[3]), round(bd)

    def lookup(self, name, prefer_cc=None, bbox=None, min_pop=0):
        """Best match for one place name. Returns (lat, lng, cc, display) or None."""
        if not self.ready or not name:
            return None
        k = name.strip().lower()
        k = re.sub(r"^(the|near|in|at)\s+", "", k)
        k = re.sub(r"\s+(oblast|region|province|governorate|state|district|city)$", "", k)
        big = self.names.get(k)
        if big and big[0][0] >= 150000 and k not in ("georgia", "jordan", "chad", "lebanon"):
            c = big[0]
            if not prefer_cc or c[3] == prefer_cc:
                return (c[1], c[2], c[3], c[4])
        if k in self.by_country_name:
            cc = self.by_country_name[k]
            c = self.countries.get(cc)
            if c and c.get("lat") is not None:
                return (c["lat"], c["lng"], cc, c["name"])
        cands = self.names.get(k)
        if not cands:
            return None
        def ok(c):
            if prefer_cc and c[3] != prefer_cc:
                return False
            if bbox:
                (w, s), (e, n) = bbox
                return w - 2 <= c[2] <= e + 2 and s - 2 <= c[1] <= n + 2
            return True
        for c in cands:
            if ok(c) and (c[0] >= min_pop or prefer_cc or bbox):
                return (c[1], c[2], c[3], c[4])
        c = cands[0]
        if c[0] < min_pop:
            return None
        if prefer_cc or bbox:
            if c[0] < 200000:       # a small town in the wrong country: probably not it
                return None
        return (c[1], c[2], c[3], c[4])

    HINTS = [(r"\b(senate|congress|white house|capitol hill|supreme court|pentagon|house republicans|house democrats)\b", (38.89, -77.02, "US", "Washington")),
             (r"\bbundestag|\bbundesregierung|\bchancellor merz", (52.52, 13.4, "DE", "Berlin")),
             (r"\bkremlin\b", (55.75, 37.62, "RU", "Moscow")), (r"\bdowning street|\bwestminster", (51.5, -0.13, "GB", "London")),
             (r"\bknesset\b", (31.78, 35.2, "IL", "Jerusalem")), (r"\belys[eé]e\b", (48.87, 2.32, "FR", "Paris")),
             (r"\bred sea\b|\bhouthis?\b", (15.5, 41.5, "", "Red Sea")), (r"\bhormuz\b", (26.57, 56.25, "", "Strait of Hormuz")),
             (r"\bwall street\b", (40.71, -74.01, "US", "New York")), (r"\bbrussels\b|\beuropean commission", (50.85, 4.35, "BE", "Brussels"))]

    def find_in_text(self, text, prefer_cc=None, bbox=None):
        """Scan a headline for the most specific place it names."""
        if not self.ready:
            return None
        for rx, place in self.HINTS:          # "White House" is Washington, not Casablanca
            if re.search(rx, text or "", re.I):
                return place
        hit = self._find(text, prefer_cc, bbox)
        if hit:
            return hit
        m = US_STATES_RE.search(text or "")
        if m:
            la, ln = US_STATES[m.group(1).lower()]
            return (la, ln, "US", m.group(1))
        return None

    def _find(self, text, prefer_cc=None, bbox=None):
        m = US_STATES_RE.search(text or "")
        if m and not prefer_cc:              # a US state named in the headline beats a same-named town abroad
            la, ln = US_STATES[m.group(1).lower()]
            city = self._find_city(text, "US")
            return city or (la, ln, "US", m.group(1))
        return self._find_city(text, prefer_cc, bbox)

    # places that are also people's first or last names: "Chad Lowe", "Michael Jordan", "Georgia May Jagger"
    NAMEY = set("""chad jordan georgia victoria florence austin lincoln paris chelsea sydney dallas houston phoenix orlando eugene troy
                   camden madison aurora savannah marion logan tyler laredo kingston hamilton nelson clifton denver charlotte
                   jackson washington lafayette raleigh beverly shelby trinidad israel""".split())
    PLACE_NEXT = set("""city river basin lake valley county state province region republic government army police capital border
                        airport port coast island islands mountains desert parish metro area president prime minister
                        ministry army military rebels junta forces troops officials police court parliament election
                        senate house governor mayor authorities national""".split())
    LEAD_OK = set("""in to from of at near across into for and the a an on by with outside inside over through says said""".split())

    def _looks_like_person(self, words, i):
        w = words[i].lower()
        if w not in self.NAMEY:
            return False
        rest = words[1:]
        caps = sum(1 for x in rest if x[:1].isupper())
        if len(rest) >= 3 and caps >= 0.7 * len(rest):
            return False       # Headline In Title Case: capitals tell us nothing
        nxt = words[i + 1] if i + 1 < len(words) else ""
        if nxt[:1].isupper() and nxt.lower() not in self.PLACE_NEXT and not nxt.lower().endswith(("'s", "’s")):
            return True        # "Chad Lowe", "Jordan Peterson"
        return False

    def _find_city(self, text, prefer_cc=None, bbox=None):
        words = re.findall(r"[^\W\d_][\w'\-’]*", text or "")
        best = None
        for n in (3, 2, 1):
            for i in range(len(words) - n + 1):
                chunk = words[i:i + n]
                if n == 1 and not chunk[0][:1].isupper() and chunk[0].isascii():
                    continue
                phrase = " ".join(chunk)
                if phrase.lower() in STOP or len(phrase) < 3:
                    continue
                if n == 1 and self._looks_like_person(words, i):
                    continue
                hit = self.lookup(phrase, prefer_cc, bbox, min_pop=60000 if n == 1 else 15000)
                if hit:
                    is_country = phrase.lower() in self.by_country_name
                    score = (0 if is_country else 2) + n
                    if not best or score > best[0]:
                        best = (score, hit)
            if best and best[0] >= 3:
                break
        return best[1] if best else None


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------
SCHEMA = """
CREATE TABLE IF NOT EXISTS items(
  id TEXT PRIMARY KEY, source TEXT, feed TEXT, lang TEXT, side TEXT, lean TEXT,
  title TEXT, title_en TEXT, summary TEXT, url TEXT, author TEXT,
  published INTEGER, fetched INTEGER, lat REAL, lng REAL, place TEXT, cc TEXT, region TEXT,
  etype TEXT, topic TEXT, cluster TEXT, needs_ai INTEGER DEFAULT 0);
CREATE INDEX IF NOT EXISTS items_pub ON items(published);
CREATE INDEX IF NOT EXISTS items_cluster ON items(cluster);
CREATE TABLE IF NOT EXISTS clusters(
  id TEXT PRIMARY KEY, first INTEGER, last INTEGER, etype TEXT, topic TEXT, lat REAL, lng REAL,
  place TEXT, cc TEXT, region TEXT, title TEXT, n_sources INTEGER, confirmed INTEGER DEFAULT 0,
  alerted INTEGER DEFAULT 0, kind TEXT);
CREATE INDEX IF NOT EXISTS clusters_last ON clusters(last);
CREATE TABLE IF NOT EXISTS hazards(
  id TEXT PRIMARY KEY, kind TEXT, title TEXT, lat REAL, lng REAL, mag REAL, level TEXT,
  time INTEGER, url TEXT, extra TEXT, alerted INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS kv(key TEXT PRIMARY KEY, value TEXT, updated INTEGER);
CREATE TABLE IF NOT EXISTS alerts(id INTEGER PRIMARY KEY AUTOINCREMENT, time INTEGER, title TEXT,
  body TEXT, hash TEXT, shown INTEGER DEFAULT 0, dedupe TEXT UNIQUE);
CREATE TABLE IF NOT EXISTS health(name TEXT PRIMARY KEY, kind TEXT, ok INTEGER, last INTEGER,
  count INTEGER, error TEXT);
"""


class Store:
    def __init__(self, path):
        self.path = path
        self.lock = threading.RLock()
        self.db = sqlite3.connect(path, check_same_thread=False, timeout=30)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)
        self.db.commit()

    def q(self, sql, args=(), one=False):
        with self.lock:
            cur = self.db.execute(sql, args)
            rows = cur.fetchall()
        return (rows[0] if rows else None) if one else rows

    def x(self, sql, args=()):
        with self.lock:
            cur = self.db.execute(sql, args)
            self.db.commit()
            return cur

    def many(self, sql, rows):
        with self.lock:
            self.db.executemany(sql, rows)
            self.db.commit()

    def kv_get(self, key, default=None):
        r = self.q("SELECT value, updated FROM kv WHERE key=?", (key,), one=True)
        if not r:
            return default
        try:
            return json.loads(r["value"])
        except ValueError:
            return default

    def kv_age(self, key):
        r = self.q("SELECT updated FROM kv WHERE key=?", (key,), one=True)
        return now() - r["updated"] if r else 10 ** 9

    def kv_set(self, key, value):
        self.x("INSERT OR REPLACE INTO kv(key, value, updated) VALUES(?,?,?)", (key, json.dumps(value), now()))

    def health(self, name, kind, ok, count=0, error=""):
        self.x("INSERT OR REPLACE INTO health(name, kind, ok, last, count, error) VALUES(?,?,?,?,?,?)",
               (name, kind, 1 if ok else 0, now(), count, error[:200]))

    def prune(self, days=45):
        cut = now() - days * 86400
        self.x("DELETE FROM items WHERE published < ?", (cut,))
        self.x("DELETE FROM clusters WHERE last < ?", (cut,))
        self.x("DELETE FROM hazards WHERE time < ?", (cut,))
        self.x("DELETE FROM alerts WHERE time < ?", (cut,))


def item_id(*parts):
    return hashlib.sha1("|".join(str(p) for p in parts).encode("utf-8", "ignore")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# The service
# ---------------------------------------------------------------------------
AI_PROMPT = """You read one post from a news or Telegram channel ({lang}; the source speaks for: {side}).
Reply ONLY with JSON:
{{"english": "one plain English sentence saying what the post reports (translate if needed; keep who claims it)",
  "type": one of ["other","politics","economy","police","protest","aid","fire","ship","defense","clash","shelling","drone","missile","blast","alert"] - use clash/shelling/drone/missile/blast/alert ONLY for real armed violence or war; "defense" is military news without fighting (budgets, arms deals, exercises, NATO); court cases, crime, animals, local disputes and everyday news are "police" or "other",
  "places": ["the most specific town or area named", "the wider region or country"],
  "is_report": true if it reports a specific event, false for opinion, ads, fundraising or general commentary}}

Post:
{text}"""

ASK_PROMPT = """You are Archie. Answer the question using ONLY the numbered reports below (newest first).
Cite them like [1] or [2][5] after each claim. If reports disagree, say so and cite both sides.
If they don't answer it, say what's missing. Keep it to one short paragraph, plain words.

Question: {q}

Reports:
{ctx}"""

NOTE_PROMPT = """You write the markets morning note for one reader. Use ONLY the numbers and headlines below.
Never invent a figure. Plain words, no jargon without a short explanation.
Reply ONLY with JSON:
{{"take": "3-4 sentences: what's driving markets today and the one thing to watch",
  "moved": [{{"what": "short label like 'Oil ▼'", "why": "one sentence, tied to a headline if one explains it", "headline": "the headline it ties to or empty"}}]}}
Give 3-5 'moved' items for the biggest moves.

Numbers (change is since the previous close):
{numbers}

Economic calendar today:
{calendar}

Top headlines:
{headlines}"""


class WorldService:
    def __init__(self, get_model=None, vault=None, log=None, wiki=None, add_calendar=None):
        self.wiki = wiki                      # Archie's offline Wikipedia (WikiLibrary), if there is one
        self.add_calendar = add_calendar      # adds an item to Archie's own calendar
        os.makedirs(WORLD_DIR, exist_ok=True)
        os.makedirs(SAVED_DIR, exist_ok=True)
        self.store = Store(DB_PATH)
        self.geo = Gazetteer(GEO_DIR)
        self.get_model = get_model or (lambda: "qwen2.5:7b")
        self.vault = vault or (lambda: None)
        self.log = log or (lambda *a: None)
        self.sources = self._load_json(SOURCES_PATH, DEFAULT_SOURCES)
        self.watch = self._load_json(WATCH_PATH, DEFAULT_WATCH)
        self.nav_queue = []
        self.nav_lock = threading.Lock()
        self.stop = threading.Event()
        self.is_online = False
        self.last_cycle = 0
        self.busy = ""
        self.server = None
        self.thread = None
        self.window_proc = None
        self.alert_cb = None
        try:     # the Workshop: coding with Archie (archie_workshop.py)
            import archie_workshop
            self.workshop = archie_workshop.Workshop(APP_DIR, self.get_model, os.path.join(APP_DIR, "Study"),
                                                     alert=lambda t, b: self._alert("ws:%s:%s" % (t, now() // 60), t, b, ""))
        except Exception as e:      # noqa: BLE001 - Archie runs without it
            self.workshop = None
            self.workshop_err = str(e)
        try:     # the Vault: browse, search and read the offline library (archie_vault.py)
            import archie_vault
            self.vaultlib = archie_vault.Vault(APP_DIR, WORLD_DIR, self.get_model, os.path.join(APP_DIR, "Study"),
                                               os.path.join(APP_DIR, "Wikipedia"), log=self.log)
        except Exception as e:      # noqa: BLE001 - Archie runs without it
            self.vaultlib = None
            self.vault_err = str(e)
        import shutil
        shutil.rmtree(os.path.join(TILE_DIR, "base"), ignore_errors=True)   # old tiles from a provider that now wants a key
        self._migrate_sources()
        self._load_rules()
        self._take_lock = threading.Lock()
        self._big_cache = (0, [])
        self.civic = None
        try:
            from archie_civic import Civic
            self.civic = Civic(self, WORLD_DIR, fetch, fetch_json, FetchError, UA)
        except Exception as e:      # the rest of the world view must work even if this part can't start
            self.log("lawmaking module failed to start:", e)
        if os.path.exists(NAV_PENDING):
            try:
                with open(NAV_PENDING, encoding="utf-8") as f:
                    self.nav_queue.append(f.read().strip())
                os.remove(NAV_PENDING)
            except OSError:
                pass

    def _migrate_sources(self):
        """Feeds that don't offer working RSS: read them through a Google News site search instead.
        Also adds feeds that came with updates (like ReliefWeb) to an existing sources.json."""
        if not any("reliefweb" in (r.get("url") or "") for r in self.sources.get("rss", [])):
            self.sources.setdefault("rss", []).append(next(r for r in DEFAULT_SOURCES["rss"] if "reliefweb" in r["url"]))
            try:
                with open(SOURCES_PATH, "w", encoding="utf-8") as f:
                    json.dump(self.sources, f, indent=2, ensure_ascii=False)
            except OSError:
                pass
        swap = {"https://kyivindependent.com/rss/": ("Kyiv Independent", "site:kyivindependent.com", "Ukrainian"),
                "https://sudantribune.com/feed/": ("Sudan Tribune", "site:sudantribune.com", "")}
        rss, changed = [], False
        for r in self.sources.get("rss", []):
            if r.get("url") in swap:
                name, q, side = swap[r["url"]]
                if not any(g.get("q") == q for g in self.sources.get("gnews", [])):
                    self.sources.setdefault("gnews", []).append({"name": name, "q": q, "hl": "en-US", "gl": "US", "side": side})
                changed = True
                continue
            rss.append(r)
        if changed:
            self.sources["rss"] = rss
            try:
                with open(SOURCES_PATH, "w", encoding="utf-8") as f:
                    json.dump(self.sources, f, indent=2, ensure_ascii=False)
            except OSError:
                pass

    def _reclassify(self):
        """Re-sort stored English headlines with the stricter rules (one time)."""
        rows = self.store.q("SELECT id, title_en, summary, region FROM items WHERE feed != 'telegram' AND title_en IS NOT NULL "
                            "AND title_en = title")
        out = []
        for r in rows:
            t = r["title_en"] or ""
            et = classify(t + " " + (r["summary"] or "")[:200], strict=True)
            bbox = REGIONS.get(r["region"]) if r["region"] else None
            hit = self.geo.find_in_text(t, None, bbox) or self.geo.find_in_text((r["summary"] or "")[:300], None, bbox)
            lat, lng, cc, place = hit if hit else (None, None, None, None)
            out.append((et, topic_for(t, et), lat, lng, cc, place, region_of(lat, lng) or r["region"], r["id"]))
        self.store.many("UPDATE items SET etype=?, topic=?, lat=?, lng=?, cc=?, place=?, region=? WHERE id=?", out)
        self.store.x("DELETE FROM kv WHERE key='t:cluster'")
        self.store.kv_set("classify_v", 3)

    def _recheck_ai_types(self):
        """One time: fix fighting labels the model gave to ordinary translated news, and sort out defense news."""
        rows = self.store.q("SELECT id, title, title_en, etype, feed FROM items WHERE title_en IS NOT NULL "
                            "AND COALESCE(etype,'') != 'skip' AND feed != 'acled'")
        out = []
        for r in rows:
            translated = r["title_en"] != r["title"]
            et = check_type(r["etype"] or "other", r["title_en"]) if translated else refine(r["etype"], r["title_en"])
            if et != r["etype"]:
                out.append((et, topic_for(r["title_en"], et), r["id"]))
        if out:
            self.store.many("UPDATE items SET etype=?, topic=? WHERE id=?", out)
            self.store.x("DELETE FROM kv WHERE key='t:cluster'")
        self.store.kv_set("aicheck_v", 2)

    # ---------- your label corrections ----------
    def _load_rules(self):
        global LABEL_RULES
        try:
            with open(RULES_PATH, encoding="utf-8") as f:
                LABEL_RULES = [r for r in json.load(f) if isinstance(r, dict) and r.get("word")]
        except (OSError, ValueError):
            LABEL_RULES = []

    def _save_rules(self):
        try:
            with open(RULES_PATH, "w", encoding="utf-8") as f:
                json.dump(LABEL_RULES, f, indent=2, ensure_ascii=False)
        except OSError:
            pass

    def rules(self):
        return {"rules": LABEL_RULES}

    def remove_rule(self, i):
        if 0 <= i < len(LABEL_RULES):
            LABEL_RULES.pop(i)
            self._save_rules()
        return self.rules()

    def label_words(self, cid):
        """Words from a story that could explain its label, rarest first (for 'remember this')."""
        c = self.store.q("SELECT * FROM clusters WHERE id=?", (cid,), one=True)
        if not c:
            return {"words": []}
        titles = [r["title_en"] for r in self.store.q("SELECT title_en FROM items WHERE cluster=? AND title_en IS NOT NULL", (cid,))]
        toks = set()
        for t in titles or [c["title"]]:
            toks |= {w for w in tokens(t) if len(w) > 2 and not any(ch.isdigit() for ch in w)}
        place = (c["place"] or "").lower()
        skip = {"reported", "report", "reports", "near", "area", "region", "city", "people", "year", "years", "today",
                "yesterday", "week", "officials", "official", "government", "local", "state", "country", "news", "video"}
        cands = []
        for w in toks:
            if w in skip or w in place or (self.geo.ready and w in self.geo.by_country_name):
                continue
            n = self.store.q("SELECT COUNT(*) n FROM items WHERE published > ? AND LOWER(title_en) LIKE ?",
                             (now() - 30 * 86400, "%" + w + "%"), one=True)["n"]
            cands.append((n, w))
        cands.sort()
        return {"words": [w for _, w in cands[:8]], "type": c["etype"] or "other"}

    def relabel(self, b):
        """The 'wrong label' button: fix one story, and optionally learn a rule from one word."""
        cid, to = b.get("id", ""), b.get("type") or "other"
        if to not in TYPES and to != "other":
            return {"error": "unknown label"}
        c = self.store.q("SELECT * FROM clusters WHERE id=?", (cid,), one=True)
        if not c:
            return {"error": "that story isn't stored any more"}
        frm = c["etype"] or "other"
        new = None if to == "other" else to
        items = self.store.q("SELECT id, title_en FROM items WHERE cluster=?", (cid,))
        self.store.many("UPDATE items SET etype=?, topic=? WHERE id=?",
                        [(new, topic_for(i["title_en"] or "", new), i["id"]) for i in items])
        changed = len(items)
        word = (b.get("word") or "").strip().lower()
        if word:
            LABEL_RULES[:] = [r for r in LABEL_RULES if not (r["word"] == word and r.get("from") == frm)]
            LABEL_RULES.append({"word": word, "from": frm, "to": to, "added": datetime.date.today().isoformat(),
                                "example": (c["title"] or "")[:120]})
            self._save_rules()
            for r in self.store.q("SELECT id, title_en, etype FROM items WHERE published > ? AND title_en IS NOT NULL "
                                  "AND COALESCE(etype,'') != 'skip'", (now() - 72 * 3600,)):
                et = apply_rules(r["etype"], r["title_en"])
                if et != r["etype"]:
                    self.store.x("UPDATE items SET etype=?, topic=? WHERE id=?", (et, topic_for(r["title_en"], et), r["id"]))
                    changed += 1
        self.recluster()
        return {"ok": True, "changed": changed, "id": cid, "item": self.item(cid)}

    # ---------- settings files ----------
    def _load_json(self, path, default):
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            missing = [k for k in default if k not in data]
            for k in missing:
                data[k] = default[k]
            if missing:           # new settings from an update: add them to the file so they can be edited
                try:
                    with open(path, "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=2, ensure_ascii=False)
                except OSError:
                    pass
            return data
        except (OSError, ValueError):
            try:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(default, f, indent=2, ensure_ascii=False)
            except OSError:
                pass
            return json.loads(json.dumps(default))

    def save_watch(self, data):
        self.watch.update(data or {})
        with open(WATCH_PATH, "w", encoding="utf-8") as f:
            json.dump(self.watch, f, indent=2, ensure_ascii=False)

    # ---------- start / stop ----------
    def start(self):
        if self.thread:
            return
        self.server = _make_server(self)
        threading.Thread(target=self.server.serve_forever, daemon=True, name="world-http").start()
        if self.vaultlib:
            try:
                self.vaultlib.start_content(PORT + 1)
            except Exception as e:      # noqa: BLE001
                self.log("vault pages server:", e)
        self.thread = threading.Thread(target=self._loop, daemon=True, name="world-fetch")
        self.thread.start()
        if self.civic:
            threading.Thread(target=self._civic_loop, daemon=True, name="world-civic").start()
        try:
            register_protocol()
        except Exception:
            pass

    def shutdown(self):
        self.stop.set()
        try:
            if self.server:
                self.server.shutdown()
        except Exception:
            pass
        try:
            if getattr(self, "vaultlib", None):
                self.vaultlib.stop()
        except Exception:
            pass

    def url(self, hash_=""):
        return f"http://127.0.0.1:{PORT}/" + (("#" + hash_.lstrip("#")) if hash_ else "")

    def open_window(self, hash_=""):
        """Open the globe window, or fly the open one to hash_."""
        if hash_:
            self.navigate(hash_)
        if self.window_open():
            return
        url = self.url(hash_)
        edge = None
        for p in (r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                  r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"):
            if os.path.exists(p):
                edge = p
        if edge:
            prof = os.path.join(WORLD_DIR, "window-profile")
            self.window_proc = subprocess.Popen([edge, f"--app={url}", f"--user-data-dir={prof}",
                                                 "--window-size=1600,940", "--no-first-run",
                                                 "--disable-features=Translate", "--autoplay-policy=no-user-gesture-required"])
        else:
            import webbrowser
            webbrowser.open(url)

    def open_workshop(self):
        """The Workshop gets its own window (same little server, its own page)."""
        url = "http://127.0.0.1:%d/web/workshop.html?v=%s" % (PORT, VERSION)   # new version, new address: never an old cached page
        for p in (r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"):
            if os.path.exists(p):
                subprocess.Popen([p, f"--app={url}", f"--user-data-dir={os.path.join(WORLD_DIR, 'window-profile')}", "--window-size=1500,920", "--no-first-run"])
                return
        import webbrowser
        webbrowser.open(url)

    def open_vault(self, hash_=""):
        """The Vault gets its own window too."""
        url = "http://127.0.0.1:%d/web/vault.html?v=%s%s" % (PORT, VERSION, ("#" + hash_) if hash_ else "")
        for p in (r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"):
            if os.path.exists(p):
                subprocess.Popen([p, f"--app={url}", f"--user-data-dir={os.path.join(WORLD_DIR, 'window-profile')}", "--window-size=1500,940", "--no-first-run"])
                return
        import webbrowser
        webbrowser.open(url)

    def window_open(self):
        return self.window_proc is not None and self.window_proc.poll() is None and \
            now() - getattr(self, "_last_poll", 0) < 10

    def navigate(self, hash_):
        with self.nav_lock:
            self.nav_queue.append(hash_.lstrip("#"))

    def pop_nav(self):
        self._last_poll = now()
        with self.nav_lock:
            return self.nav_queue.pop(0) if self.nav_queue else None

    # ---------- the slow loop ----------
    def _due(self, key, seconds):
        return self.store.kv_age("t:" + key) >= seconds

    def _mark(self, key):
        self.store.kv_set("t:" + key, 1)

    def _loop(self):
        time.sleep(8)       # let Archie finish starting
        while not self.stop.is_set():
            try:
                self.cycle()
            except Exception as e:
                self.log("world cycle failed:", e)
            self.stop.wait(120)

    def _civic_loop(self):
        """Votes, bills, campaign money and the rest run on their own thread: some downloads are big,
        and they shouldn't hold up the news. One job at a time, then a pause, so the PC stays cool."""
        time.sleep(45)
        while not self.stop.is_set():
            try:
                if self.is_online:
                    for key, every, fn in self.civic.jobs():
                        if self.stop.is_set():
                            return
                        if self._due(key, every):
                            self.civic.current = (key, now())
                            try:
                                fn()
                            except Exception as e:
                                self.store.health(key, "job", False, 0, str(e))
                                self.log("lawmaking job", key, "failed:", e)
                            self.civic.current = None
                            self._mark(key)
                            self.stop.wait(5)
            except Exception as e:
                self.log("lawmaking loop failed:", e)
            self.stop.wait(300)

    def cycle(self):
        self.is_online = online()
        self.last_cycle = now()
        if not self.is_online:
            return
        self.geo.ensure()
        if self.store.kv_get("classify_v") != 3 and self.geo.ready:
            self._reclassify()
        if self.store.kv_get("aicheck_v") != 2:
            self._recheck_ai_types()
        jobs = [
            ("quakes", 300, self.pull_quakes),
            ("gdacs", 1800, self.pull_gdacs),
            ("volcanoes", 21600, self.pull_volcanoes),
            ("storms", 1800, self.pull_storms),
            ("iss", 43200, self.pull_iss),
            ("sats", 86400, self.pull_sats),
            ("craft", 43200, self.pull_craft),
            ("spacewx", 1800, self.pull_spacewx),
            ("marswx", 21600, self.pull_marswx),
            ("launches", 10800, self.pull_launches),
            ("rovers", 86400, self.pull_rovers),
            ("trails", 604800, self.pull_trails),
            ("exo", 604800, self.pull_exo),
            ("cosmic", 10800, self.pull_cosmic),
            ("people", 21600, self.pull_people),
            ("govs", 86400, self.pull_govs),
            ("worldbank", 604800, self.pull_worldbank),
            ("cialeaders", 604800, self.pull_cia_leaders),
            ("uscabinet2", 604800, self.pull_us_cabinet),
            ("fires", 10800, self.pull_fires),
            ("rss", 600, self.pull_rss),
            ("gnews", 1200, self.pull_gnews),
            ("telegram", 600, self.pull_telegram),
            ("local", 1800, self.pull_local),
            ("gdelt", 1800, self.pull_gdelt),
            ("acled", 43200, self.pull_acled),
            ("ai", 600, self.run_ai),
            ("cluster", 600, self.recluster),
            ("markets", 300 if self._market_hours() else 1800, self.pull_markets),
            ("marketsdaily", 43200, self.pull_markets_daily),
            ("fred", 21600, self.pull_fred),
            ("calendar", 10800, self.pull_calendar),
            ("earnings", 21600, self.pull_earnings),
            ("polymarket", 3600, self.pull_polymarket),
            ("front", 21600, self.pull_front),
            ("ships", 43200, self.pull_portwatch),
            ("note", 1800, self.maybe_write_note),
            ("newsbrief", 600, self.maybe_edition),
            ("alerts", 120, self.check_alerts),
            ("digest", 1800, self.maybe_digest),
            ("worldcal", 21600, self.pull_world_calendar),
            ("weekly", 3600, self.maybe_weekly),
            ("prune", 86400, self.store.prune),
        ]
        for key, every, fn in jobs:
            if self.stop.is_set():
                return
            if self._due(key, every):
                self.busy = key
                try:
                    fn()
                except Exception as e:
                    self.store.health(key, "job", False, 0, str(e))
                    self.log("world job", key, "failed:", e)
                self._mark(key)
        self.busy = ""

    def _market_hours(self):
        h = datetime.datetime.utcnow().hour
        return datetime.datetime.utcnow().weekday() < 5 and 0 <= h <= 22

    # ---------- hazards ----------
    def pull_quakes(self):
        d = fetch_json("https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/2.5_week.geojson")
        rows = []
        for f in d.get("features", []):
            p, g = f.get("properties", {}), f.get("geometry", {}).get("coordinates", [0, 0, 0])
            if p.get("mag") is None:
                continue
            rows.append(("usgs:" + str(f.get("id")), "quake", p.get("title") or "", g[1], g[0], p.get("mag"),
                         "tsunami" if p.get("tsunami") else "", int((p.get("time") or 0) / 1000), p.get("url") or "",
                         json.dumps({"place": p.get("place"), "depth": g[2] if len(g) > 2 else None})))
        self.store.many("INSERT OR IGNORE INTO hazards(id, kind, title, lat, lng, mag, level, time, url, extra) "
                        "VALUES(?,?,?,?,?,?,?,?,?,?)", rows)
        self.store.health("USGS earthquakes", "hazard", True, len(rows))

    def pull_gdacs(self):
        kinds = {"TC": "cyclone", "FL": "flood", "VO": "volcano", "DR": "drought", "WF": "wildfire", "EQ": None}
        rows = []
        try:
            d = fetch_json("https://www.gdacs.org/gdacsapi/api/events/geteventlist/MAP")
            for f in d.get("features", []):
                p = f.get("properties", {})
                kind = kinds.get(p.get("eventtype"))
                geom = f.get("geometry", {})
                if not kind or geom.get("type") != "Point":
                    continue
                lng, lat = geom["coordinates"][:2]
                url = (p.get("url") or {}).get("report", "") if isinstance(p.get("url"), dict) else ""
                sev = (p.get("severitydata") or {}).get("severitytext", "")
                sd = p.get("severitydata") or {}
                title = p.get("name") or p.get("eventname") or kind
                if kind == "cyclone":
                    title = "Tropical cyclone " + storm_name(p.get("eventname") or title)
                elif len(title) > 90:
                    title = re.split(r"\.\s", title)[0][:90]
                rows.append((f"gdacs:{p.get('eventtype')}{p.get('eventid')}", kind, title,
                             lat, lng, None, (p.get("alertlevel") or "").lower(),
                             parse_date(p.get("fromdate")) or now(), url,
                             json.dumps({"severity": sev, "country": p.get("country"), "to": p.get("todate"),
                                         "current": p.get("iscurrent"), "eventid": p.get("eventid"),
                                         "episodeid": p.get("episodeid"), "sev": sd.get("severity"),
                                         "sevunit": sd.get("severityunit"), "eventname": p.get("eventname"),
                                         "geom": (p.get("url") or {}).get("geometry", "") if isinstance(p.get("url"), dict) else ""})))
        except FetchError:
            text = fetch("https://www.gdacs.org/xml/rss.xml")
            root = ET.fromstring(text.encode("utf-8"))
            ns = {"gdacs": "http://www.gdacs.org", "geo": "http://www.w3.org/2003/01/geo/wgs84_pos#"}
            for it in root.iter("item"):
                et = it.findtext("gdacs:eventtype", default="", namespaces=ns)
                kind = kinds.get(et)
                lat, lng = it.findtext("geo:Point/geo:lat", namespaces=ns), it.findtext("geo:Point/geo:long", namespaces=ns)
                if not kind or lat is None:
                    continue
                rows.append((f"gdacs:{et}{it.findtext('gdacs:eventid', namespaces=ns)}", kind, it.findtext("title") or kind,
                             float(lat), float(lng), None, (it.findtext("gdacs:alertlevel", default="", namespaces=ns)).lower(),
                             parse_date(it.findtext("pubDate")) or now(), it.findtext("link") or "",
                             json.dumps({"severity": it.findtext("gdacs:severity", default="", namespaces=ns)})))
        self.store.x("DELETE FROM hazards WHERE id LIKE 'gdacs:%'")
        self.store.many("INSERT OR REPLACE INTO hazards(id, kind, title, lat, lng, mag, level, time, url, extra) "
                        "VALUES(?,?,?,?,?,?,?,?,?,?)", rows)
        self.store.health("GDACS disasters", "hazard", True, len(rows))

    # ---------- storm tracks: where each cyclone has been and where it's forecast to go ----------
    NHC_CLASS = {"TD": "Tropical depression", "TS": "Tropical storm", "HU": "Hurricane", "MH": "Major hurricane",
                 "STD": "Subtropical depression", "STS": "Subtropical storm", "PTC": "Potential tropical cyclone",
                 "PC": "Post-tropical cyclone", "TY": "Typhoon", "STY": "Super typhoon", "TC": "Tropical cyclone"}

    @staticmethod
    def _kml_parts(kml):
        """Placemarks from a KML file: [{"name", "desc", "points": [[lat,lng]], "kind": point|line|poly}]."""
        out = []
        for pm in re.findall(r"<Placemark\b.*?</Placemark>", kml, re.S | re.I):
            name = strip_tags(html.unescape((re.search(r"<name>(.*?)</name>", pm, re.S | re.I) or [None, ""])[1]))
            desc = strip_tags(html.unescape(re.sub(r"<!\[CDATA\[|\]\]>", "", (re.search(r"<description>(.*?)</description>", pm, re.S | re.I) or [None, ""])[1])))
            data = {k.lower(): strip_tags(v) for k, v in re.findall(r'<Data name="([^"]+)">\s*<value>(.*?)</value>', pm, re.S | re.I)}
            data.update({k.lower(): strip_tags(v) for k, v in re.findall(r'<SimpleData name="([^"]+)">(.*?)</SimpleData>', pm, re.S | re.I)})
            kind = "poly" if re.search(r"<Polygon", pm, re.I) else "line" if re.search(r"<LineString", pm, re.I) else "point"
            for block in re.findall(r"<coordinates>(.*?)</coordinates>", pm, re.S | re.I)[:1]:
                pts = []
                for tok in block.split():
                    try:
                        x, y = tok.split(",")[:2]
                        pts.append([round(float(y), 3), round(float(x), 3)])
                    except ValueError:
                        continue
                if pts:
                    out.append({"name": name, "desc": desc, "data": data, "points": pts, "kind": kind})
        return out

    def _kmz(self, url):
        raw, _, _ = fetch(url, timeout=30, raw=True)
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as z:
                name = next(n for n in z.namelist() if n.lower().endswith(".kml"))
                return z.read(name).decode("utf-8", "ignore")
        except (zipfile.BadZipFile, StopIteration):
            return raw.decode("utf-8", "ignore")

    def _where(self, lat, lng):
        n = self.geo.nearest(lat, lng)
        if not n:
            return ""
        name, country, dist = n
        return f"near {name}, {country}" if dist < 120 else f"{dist} km from {name}, {country}" if dist < 900 else "over open ocean"

    def _nhc(self):
        """US National Hurricane Center: Atlantic, eastern and central Pacific (best data when it applies)."""
        d = fetch_json("https://www.nhc.noaa.gov/CurrentStorms.json", timeout=30)
        storms = []
        for st in d.get("activeStorms") or []:
            try:
                lat, lng = float(st.get("latitudeNumeric")), float(st.get("longitudeNumeric"))
            except (TypeError, ValueError):
                continue
            kt = float(st.get("intensity") or 0)
            cls = st.get("classification") or ""
            if cls == "HU" and kt >= 96:
                cls = "MH"
            one = {"id": "nhc:" + (st.get("id") or st.get("name", "")), "name": st.get("name", ""), "lat": lat, "lng": lng,
                   "cls": self.NHC_CLASS.get(cls, cls), "wind_kt": kt, "pressure": st.get("pressure"),
                   "move_dir": st.get("movementDir"), "move_kt": st.get("movementSpeed"), "updated": parse_date(st.get("lastUpdate")),
                   "advisory": ((st.get("publicAdvisory") or {}).get("url") or ""), "source": "US National Hurricane Center",
                   "past": [], "fcst": [], "cone": []}
            try:
                if (st.get("forecastTrack") or {}).get("kmzFile"):
                    for part in self._kml_parts(self._kmz(st["forecastTrack"]["kmzFile"])):
                        if part["kind"] == "point":
                            m = re.search(r"(\d+)\s*(?:knots|kt)", part["desc"], re.I)
                            one["fcst"].append({"lat": part["points"][0][0], "lng": part["points"][0][1],
                                                "label": part["name"] or "", "wind_kt": float(m.group(1)) if m else None})
                if (st.get("trackCone") or {}).get("kmzFile"):
                    for part in self._kml_parts(self._kmz(st["trackCone"]["kmzFile"])):
                        if part["kind"] == "poly" and len(part["points"]) > 4:
                            one["cone"] = part["points"]
                            break
                if (st.get("bestTrack") or {}).get("kmzFile"):
                    for part in self._kml_parts(self._kmz(st["bestTrack"]["kmzFile"])):
                        if part["kind"] == "point":
                            m = re.search(r"(\d+)\s*(?:knots|kt)", part["desc"], re.I)
                            one["past"].append({"lat": part["points"][0][0], "lng": part["points"][0][1],
                                                "label": part["name"] or "", "wind_kt": float(m.group(1)) if m else None})
                        elif part["kind"] == "line" and not one["past"]:
                            one["past_line"] = part["points"]
            except (FetchError, Exception):
                pass
            storms.append(one)
        return storms

    def _gdacs_track(self, h, ex):
        """Track and forecast for one GDACS cyclone (covers every ocean)."""
        url = ex.get("geom") or (f"https://www.gdacs.org/gdacsapi/api/polygons/getgeometry?eventtype=TC&eventid={ex.get('eventid')}"
                                 f"&episodeid={ex.get('episodeid')}" if ex.get("eventid") else "")
        one = {"id": h["id"], "name": storm_name(ex.get("eventname") or h["title"]), "lat": h["lat"], "lng": h["lng"], "cls": "",
               "wind_kt": None, "source": "GDACS", "advisory": h["url"], "past": [], "fcst": [], "cone": []}
        if ex.get("sev"):
            try:
                v = float(ex["sev"])
                unit = (ex.get("sevunit") or "km/h").lower()
                one["wind_kt"] = v / 1.852 if "km" in unit else v if "kt" in unit or "knot" in unit else v / 1.151
            except (TypeError, ValueError):
                pass
        if not url:
            return one
        d = fetch_json(url, timeout=30)
        nowt = now()
        pts = []
        for f in d.get("features") or []:
            g, p = f.get("geometry") or {}, f.get("properties") or {}
            cls = str(p.get("Class") or p.get("class") or "")
            blob = " ".join(str(v) for v in p.values()).lower()
            if g.get("type") == "Point":
                x, y = g["coordinates"][:2]
                t = None
                for k, v in p.items():
                    if isinstance(v, str) and re.search(r"date|time", k, re.I):
                        t = _any_date(v) or t
                wind = None
                for k, v in p.items():
                    if re.search(r"wind", k, re.I):
                        try:
                            wind = float(v)
                            break
                        except (TypeError, ValueError):
                            pass
                fc = "forecast" in blob or (t is not None and t > nowt + 1800)
                pts.append({"lat": round(y, 3), "lng": round(x, 3), "t": t, "wind_kmh": wind, "fc": fc,
                            "label": datetime.datetime.fromtimestamp(t).strftime("%a %b %d, %H:%M") if t else ""})
            elif g.get("type") == "Polygon" and "cone" in (cls + blob).lower():
                one["cone"] = [[round(c[1], 3), round(c[0], 3)] for c in g["coordinates"][0]]
            elif g.get("type") in ("LineString", "MultiLineString") and not pts:
                cs = g["coordinates"] if g["type"] == "LineString" else [c for part in g["coordinates"] for c in part]
                one["past_line"] = [[round(c[1], 3), round(c[0], 3)] for c in cs]
        if pts and any(p["t"] for p in pts):
            pts.sort(key=lambda p: p["t"] or 0)
        for p in pts:
            q = {"lat": p["lat"], "lng": p["lng"], "label": p["label"],
                 "wind_kt": p["wind_kmh"] / 1.852 if p["wind_kmh"] and p["wind_kmh"] > 60 else p["wind_kmh"]}
            (one["fcst"] if p["fc"] else one["past"]).append(q)
        return one

    @staticmethod
    def storm_name(text):
        """'Tropical Cyclone GONZALO-26. Population affected by…' -> 'Gonzalo'."""
        t = (text or "").strip()
        m = re.search(r"(?:cyclone|storm|hurricane|typhoon|depression|tc)\s+([A-Za-z'\-]+?)(?:-\d{2})?(?=[\s.,;:]|$)", t, re.I)
        if m:
            n = m.group(1)
        else:
            n = re.split(r"[.,;:(]", t)[0].strip()
            n = re.sub(r"-\d{2}$", "", n)
        n = n[:24]
        return n[:1].upper() + n[1:].lower() if n.isupper() or n.islower() else n

    def pull_storms(self):
        self._pull_storms()
        st = self.store.kv_get("storms", {})
        for v in st.values():
            v["name"] = self.storm_name(v.get("name") or "")
        self.store.kv_set("storms", st)

    def _pull_storms(self):
        cyc = self.store.q("SELECT * FROM hazards WHERE kind='cyclone'")
        storms, errs = {}, []
        nhc = []
        try:
            nhc = self._nhc()
        except (FetchError, ValueError) as e:
            errs.append(f"NHC: {e}")
        for h in cyc:
            try:
                ex = json.loads(h["extra"] or "{}")
            except ValueError:
                ex = {}
            match = next((n for n in nhc if n["name"] and n["name"].lower() in (h["title"] or "").lower()
                          or km(n["lat"], n["lng"], h["lat"], h["lng"]) < 300), None)
            if match:
                match["id"] = h["id"]
                storms[h["id"]] = match
                continue
            try:
                storms[h["id"]] = self._gdacs_track(h, ex)
            except (FetchError, ValueError, KeyError, TypeError) as e:
                errs.append(f"GDACS {h['title']}: {e}")
                storms[h["id"]] = {"id": h["id"], "name": storm_name(ex.get("eventname") or h["title"]), "lat": h["lat"], "lng": h["lng"],
                                   "past": [], "fcst": [], "cone": [], "source": "GDACS", "advisory": h["url"]}
        self.store.x("DELETE FROM hazards WHERE id LIKE 'nhc:%'")
        used = {s["id"] for s in storms.values()}
        for n in nhc:                           # NHC storms GDACS hasn't listed yet
            if n["id"] not in used:
                storms[n["id"]] = n
                self.store.x("INSERT OR REPLACE INTO hazards(id, kind, title, lat, lng, mag, level, time, url, extra) "
                             "VALUES(?,?,?,?,?,?,?,?,?,?)", (n["id"], "cyclone", f"{n['cls']} {n['name']}".strip(),
                                                             n["lat"], n["lng"], None, "", n.get("updated") or now(),
                                                             n["advisory"], json.dumps({"severity": n["cls"]})))
        for st in storms.values():
            st["fcst"] = [p for p in st.get("fcst", []) if km(p["lat"], p["lng"], st["lat"], st["lng"]) > 40]
            for p in st.get("fcst", []):
                p["where"] = self._where(p["lat"], p["lng"])
            st["where"] = self._where(st["lat"], st["lng"])
            if st.get("wind_kt") is None:
                pw = [p["wind_kt"] for p in st.get("past", []) if p.get("wind_kt")]
                st["wind_kt"] = pw[-1] if pw else None
            if not st.get("cls") and st.get("wind_kt"):
                k = st["wind_kt"]
                st["cls"] = ("Tropical depression" if k < 34 else "Tropical storm" if k < 64 else
                             "Hurricane / typhoon" if k < 96 else "Major hurricane / typhoon")
        self.store.kv_set("storms", storms)
        self.store.health("Storm tracks (GDACS / NHC)", "hazard", not errs or bool(storms), len(storms), "; ".join(errs)[:200])

    # ---------- the International Space Station ----------
    def pull_iss(self):
        """Orbit elements (TLE) for the ISS; the page works out where it is each second from these."""
        try:
            text = fetch("https://celestrak.org/NORAD/elements/gp.php?CATNR=25544&FORMAT=TLE", timeout=30)
            lines = [l.strip() for l in text.strip().splitlines() if l.strip()]
            l1 = next(l for l in lines if l.startswith("1 "))
            l2 = next(l for l in lines if l.startswith("2 "))
        except (FetchError, StopIteration):
            d = fetch_json("https://api.wheretheiss.at/v1/satellites/25544/tles", timeout=30)
            l1, l2 = d["line1"], d["line2"]
        self.store.kv_set("iss_tle", {"l1": l1, "l2": l2, "at": now()})
        self.store.health("ISS orbit (CelesTrak)", "space", True, 1)

    # ---------- satellite groups (the page shows the ones you switch on) ----------
    SAT_GROUPS = [("stations", "stations"), ("visual", "visual"), ("science", "science"), ("weather", "weather"),
                  ("gps", "gps-ops"), ("starlink", "starlink")]

    def pull_sats(self):
        got, errs = {}, []
        for key, grp in self.SAT_GROUPS:
            if self.stop.is_set():
                return
            try:
                text = fetch(f"https://celestrak.org/NORAD/elements/gp.php?GROUP={grp}&FORMAT=tle", timeout=90)
                lines = [l.rstrip() for l in text.splitlines() if l.strip()]
                sats = []
                for i in range(len(lines) - 2):
                    if lines[i + 1].startswith("1 ") and lines[i + 2].startswith("2 ") and not lines[i].startswith(("1 ", "2 ")):
                        sats.append([lines[i].strip(), lines[i + 1], lines[i + 2]])
                if sats:
                    got[key] = sats
            except FetchError as e:
                errs.append(f"{key}: {e}")
            time.sleep(1)
        if got:
            old = self.store.kv_get("sats", {})
            old.update(got)
            self.store.kv_set("sats", old)
        self.store.health("Satellites (CelesTrak)", "space", bool(got), sum(len(v) for v in got.values()), "; ".join(errs)[:200])

    SAT_OWNERS = {"US": "United States", "PRC": "China", "CIS": "Russia", "JPN": "Japan", "IND": "India", "ESA": "European Space Agency",
                  "FR": "France", "GER": "Germany", "UK": "United Kingdom", "IT": "Italy", "CA": "Canada", "ISS": "International (ISS partners)",
                  "SES": "SES (Luxembourg)", "EUTE": "Eutelsat (France)", "ITSO": "Intelsat", "GLOB": "Globalstar (US)", "IRID": "Iridium (US)",
                  "ORB": "ORBCOMM (US)", "EUME": "EUMETSAT (Europe)", "SKOR": "South Korea", "ISRA": "Israel", "IRAN": "Iran", "NKOR": "North Korea",
                  "BRAZ": "Brazil", "AUS": "Australia", "TURK": "Turkey", "UAE": "United Arab Emirates", "SAUD": "Saudi Arabia", "ARGN": "Argentina",
                  "SPN": "Spain", "NETH": "Netherlands", "SWED": "Sweden", "NOR": "Norway", "FIN": "Finland", "LUXE": "Luxembourg", "TWN": "Taiwan",
                  "SING": "Singapore", "INDO": "Indonesia", "MEX": "Mexico", "PAKI": "Pakistan", "EGYP": "Egypt", "NIG": "Nigeria", "KAZ": "Kazakhstan",
                  "UKR": "Ukraine", "AB": "Arabsat (Arab League)", "O3B": "O3b (SES)", "CHBZ": "China and Brazil", "ASRA": "Austria", "BEL": "Belgium",
                  "DEN": "Denmark", "POL": "Poland", "THAI": "Thailand", "VTNM": "Vietnam", "PHIL": "Philippines", "NZ": "New Zealand", "CHLE": "Chile",
                  "PER": "Peru", "SAFR": "South Africa", "ALG": "Algeria", "MA": "Morocco", "QAT": "Qatar", "GREC": "Greece", "CZE": "Czechia",
                  "SWTZ": "Switzerland", "BGD": "Bangladesh", "LTU": "Lithuania", "EST": "Estonia", "BOL": "Bolivia", "VENZ": "Venezuela",
                  "MALA": "Malaysia", "BELA": "Belarus", "AZER": "Azerbaijan", "ETH": "Ethiopia", "RWA": "Rwanda", "KEN": "Kenya", "TBD": "not yet assigned"}
    LAUNCH_SITES = {"AFETR": "Cape Canaveral / Kennedy, Florida", "AFWTR": "Vandenberg, California", "TYMSC": "Baikonur, Kazakhstan",
                    "PKMTR": "Plesetsk, Russia", "VOSTO": "Vostochny, Russia", "JSC": "Jiuquan, China", "XSC": "Xichang, China",
                    "TSC": "Taiyuan, China", "WSC": "Wenchang, China", "YSLA": "a sea platform off China", "FRGUI": "Kourou, French Guiana",
                    "SRILR": "Sriharikota, India", "TNSTA": "Tanegashima, Japan", "KSCUT": "Uchinoura, Japan", "RLLB": "Rocket Lab, Mahia (New Zealand)",
                    "WLPIS": "Wallops, Virginia", "KWAJ": "Kwajalein Atoll", "SEAL": "Sea Launch platform", "NSC": "Naro, South Korea",
                    "SEMLS": "Semnan, Iran", "KYMSC": "Kapustin Yar, Russia", "ERAS": "an aircraft (air launch)", "OREN": "Yasny, Russia",
                    "YUN": "Sohae, North Korea", "SVOBO": "Svobodny, Russia", "PMRF": "Barking Sands, Hawaii", "SNMLP": "San Marco platform, Kenya",
                    "HGSTR": "Hammaguir, Algeria", "WOMRA": "Woomera, Australia", "SADOL": "a submarine (Barents Sea)", "SMTS": "Shahrud, Iran",
                    "STARB": "Starbase, Texas", "KODAK": "Kodiak, Alaska", "RLLC": "Rocket Lab Launch Complex 2, Virginia"}
    SAT_OPERATORS = [(r"^STARLINK", "SpaceX (Starlink internet)"), (r"^ONEWEB", "Eutelsat OneWeb (internet)"), (r"^KUIPER", "Amazon (Project Kuiper)"),
                     (r"^(GPS|NAVSTAR)", "US Space Force (GPS)"), (r"^BEIDOU", "China (BeiDou navigation)"), (r"^(GALILEO|GSAT0)", "European Union (Galileo)"),
                     (r"^COSMOS", "Russian government / military"), (r"^GLONASS", "Russia (GLONASS navigation)"), (r"^(NOAA|GOES|JPSS|SUOMI)", "NOAA (US weather)"),
                     (r"^(METEOSAT|MSG|MTG|METOP)", "EUMETSAT (European weather)"), (r"^HIMAWARI", "Japan Meteorological Agency"),
                     (r"^(FENGYUN|FY-)", "China Meteorological Administration"), (r"^(METEOR|ELEKTRO|ARKTIKA)", "Roshydromet / Roscosmos (Russian weather)"),
                     (r"^(INSAT|GSAT|IRNSS|CARTOSAT|RISAT|OCEANSAT)", "ISRO (India)"), (r"^HST$", "NASA and ESA (Hubble)"),
                     (r"^(CSS|TIANHE|WENTIAN|MENGTIAN|SHENZHOU|TIANZHOU)", "China Manned Space Agency"), (r"^(SOYUZ|PROGRESS)", "Roscosmos (Russia)"),
                     (r"DRAGON", "SpaceX (for NASA)"), (r"^CYGNUS", "Northrop Grumman (for NASA)"), (r"^IRIDIUM", "Iridium Communications"),
                     (r"^GLOBALSTAR", "Globalstar"), (r"^ORBCOMM", "ORBCOMM"), (r"^SENTINEL", "ESA / EU Copernicus"), (r"^LANDSAT", "USGS and NASA"),
                     (r"^(TERRA|AQUA|AURA|SWIFT|FERMI|NUSTAR|TESS|ICESAT|SMAP|GPM|OCO|CALIPSO|IXPE)", "NASA"), (r"^JASON", "NOAA, NASA, EUMETSAT and CNES"),
                     (r"^(FLOCK|SKYSAT|PELICAN)", "Planet Labs (Earth imaging)"), (r"^LEMUR", "Spire Global"), (r"^ICEYE", "ICEYE (radar imaging)"),
                     (r"^CAPELLA", "Capella Space (radar imaging)"), (r"^YAOGAN", "Chinese military (PLA)"), (r"^(QIANFAN|G60)", "Shanghai Spacecom (China)"),
                     (r"^GUOWANG", "China SatNet"), (r"^(TIANGONG)", "China Manned Space Agency"), (r"^(INTELSAT|IS-)", "Intelsat"), (r"^SES", "SES"),
                     (r"^(EUTELSAT|HOTBIRD)", "Eutelsat"), (r"^VIASAT", "Viasat"), (r"^ECHOSTAR", "EchoStar (DISH)"), (r"^SIRIUS|^XM-", "SiriusXM"),
                     (r"R/B|ROCKET BODY", "an old rocket stage (space junk)"), (r"DEB$|DEBRIS", "debris (space junk)")]

    def sat_info(self, norad):
        norad = re.sub(r"\D", "", str(norad or ""))[:6]
        if not norad:
            return {"error": "no id"}
        key = "satinfo:" + norad
        d = self.store.kv_get(key)
        if d is None:
            try:
                r = fetch_json(f"https://celestrak.org/satcat/records.php?CATNR={norad}&FORMAT=json", timeout=20)
                d = r[0] if isinstance(r, list) and r else {}
            except (FetchError, ValueError):
                d = {}
            if d:
                self.store.kv_set(key, d)
        name = (d.get("OBJECT_NAME") or "").upper()
        op = next((v for rx, v in self.SAT_OPERATORS if re.search(rx, name)), "")
        owner = d.get("OWNER") or ""
        return {"name": d.get("OBJECT_NAME", ""), "owner": self.SAT_OWNERS.get(owner, owner), "owner_code": owner, "operator": op,
                "launched": d.get("LAUNCH_DATE", ""), "site": self.LAUNCH_SITES.get(d.get("LAUNCH_SITE", ""), d.get("LAUNCH_SITE", "")),
                "intl_id": d.get("OBJECT_ID", ""), "type": {"PAY": "working satellite", "R/B": "rocket stage", "DEB": "debris"}.get(d.get("OBJECT_TYPE", ""), ""),
                "status": {"+": "operating", "-": "not operating", "P": "partly operating", "B": "backup", "S": "spare", "X": "extended mission",
                           "D": "decayed", "?": "unknown"}.get(d.get("OPS_STATUS_CODE", ""), "")}

    def weather_at(self, lat, lng):
        """Current weather anywhere (Open-Meteo, free, no key). Cached 30 minutes."""
        try:
            lat, lng = round(float(lat), 2), round(float(lng), 2)
        except (TypeError, ValueError):
            return {"error": "bad place"}
        key = f"wx:{lat},{lng}"
        d = self.store.kv_get(key)
        if d and self.store.kv_age(key) < 1800:
            return d
        try:
            r = fetch_json("https://api.open-meteo.com/v1/forecast?latitude=%s&longitude=%s&current=temperature_2m,apparent_temperature,"
                           "wind_speed_10m,wind_gusts_10m,weather_code,is_day&daily=daylight_duration,sunrise,sunset&timezone=auto&forecast_days=1"
                           % (lat, lng), timeout=20)
        except (FetchError, ValueError) as e:
            return d or {"error": str(e)}
        cur, day = r.get("current") or {}, r.get("daily") or {}
        d = {"temp_c": cur.get("temperature_2m"), "feels_c": cur.get("apparent_temperature"), "wind_kmh": cur.get("wind_speed_10m"),
             "gust_kmh": cur.get("wind_gusts_10m"), "code": cur.get("weather_code"), "is_day": cur.get("is_day"),
             "daylight_s": (day.get("daylight_duration") or [None])[0], "tz": r.get("timezone", ""), "utc_offset": r.get("utc_offset_seconds"),
             "at": now()}
        self.store.kv_set(key, d)
        return d

    def sats(self, group):
        d = self.store.kv_get("sats", {})
        return {"group": group, "sats": d.get(group, []), "at": self.store.kv_age("sats")}

    # ---------- the solar system view: spacecraft positions and live conditions ----------
    # NASA/JPL Horizons ids (NAIF codes) of spacecraft with public trajectories
    CRAFT_IDS = [-31, -32, -98, -96, -144, -121, -61, -159, -28, -255, -49, -64, -37, -91, -74, -202, -41, -143, -62, -53,
                 -76, -168, -85, -152, -155, -170, -21, -78]

    def pull_craft(self):
        """Where each spacecraft is (relative to the Sun, in AU), once or twice a day from JPL Horizons."""
        out = self.store.kv_get("craft", {})
        ok, errs = 0, []
        start = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M")
        stop = (datetime.datetime.utcnow() + datetime.timedelta(hours=1)).strftime("%Y-%m-%d %H:%M")
        for cid in self.CRAFT_IDS:
            if self.stop.is_set():
                break
            q = urllib.parse.urlencode({"format": "json", "COMMAND": f"'{cid}'", "OBJ_DATA": "'NO'", "MAKE_EPHEM": "'YES'",
                                        "EPHEM_TYPE": "'VECTORS'", "CENTER": "'500@10'", "START_TIME": f"'{start}'",
                                        "STOP_TIME": f"'{stop}'", "STEP_SIZE": "'1 h'", "VEC_TABLE": "'2'", "OUT_UNITS": "'AU-D'",
                                        "REF_PLANE": "'ECLIPTIC'", "REF_SYSTEM": "'ICRF'"})
            try:
                d = fetch_json("https://ssd.jpl.nasa.gov/api/horizons.api?" + q, timeout=40)
                txt = d.get("result") or ""
                block = txt.split("$$SOE", 1)[1].split("$$EOE", 1)[0] if "$$SOE" in txt else ""
                num = r"([-+]?\d*\.?\d+(?:[Ee][-+]?\d+)?)"
                vals = {}
                for k in ("X", "Y", "Z", "VX", "VY", "VZ"):
                    m = re.search(r"(?<![A-Z])" + k + r"\s*=\s*" + num, block)
                    if m:
                        vals[k.lower()] = float(m.group(1))
                if all(k in vals for k in ("x", "y", "z")):
                    vals["at"] = now()
                    out[str(cid)] = vals
                    ok += 1
                else:
                    errs.append(f"{cid}: no position")
            except (FetchError, ValueError) as e:
                errs.append(f"{cid}: {e}")
            time.sleep(1.2)
        if ok:
            self.store.kv_set("craft", out)
        self.store.health("Spacecraft positions (NASA JPL)", "space", ok > 0, ok, "; ".join(errs)[:200])

    def pull_spacewx(self):
        """Space weather now (NOAA SWPC): geomagnetic Kp, solar wind, recent solar flares.
        NOAA serves some files as lists of lists and others as lists of objects; both are read."""
        d, errs = {}, []

        def rows_of(data, cols):
            out = []
            if isinstance(data, list) and data and isinstance(data[0], list):
                head = [str(h).lower() for h in data[0]]
                for r in data[1:]:
                    out.append({c: (r[head.index(c)] if c in head and head.index(c) < len(r) else None) for c in cols})
            elif isinstance(data, list):
                for r in data:
                    if isinstance(r, dict):
                        low = {str(k).lower(): v for k, v in r.items()}
                        out.append({c: low.get(c) for c in cols})
            return out
        try:
            rows = [r for r in rows_of(fetch_json("https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json", timeout=30),
                                       ["time_tag", "kp", "kp_index", "estimated_kp"]) if (r["kp"] or r["kp_index"] or r["estimated_kp"]) not in (None, "")]
            if rows:
                val = lambda r: float(r["kp"] if r["kp"] not in (None, "") else r["kp_index"] if r["kp_index"] not in (None, "") else r["estimated_kp"])
                d["kp"], d["kp_time"] = val(rows[-1]), rows[-1]["time_tag"]
                d["kp_24h"] = [val(r) for r in rows[-8:]]
        except Exception as e:
            errs.append(f"Kp: {e}")
        try:
            rows = rows_of(fetch_json("https://services.swpc.noaa.gov/products/solar-wind/plasma-1-day.json", timeout=30),
                           ["time_tag", "density", "speed"])
            for r in reversed(rows):
                if r["speed"] not in (None, ""):
                    d["wind_kms"], d["density"] = float(r["speed"]), float(r["density"] or 0)
                    break
        except Exception as e:
            errs.append(f"solar wind: {e}")
        try:
            fl = fetch_json("https://services.swpc.noaa.gov/json/goes/primary/xray-flares-7-day.json", timeout=30)
            day = [f for f in fl if isinstance(f, dict) and (parse_date(f.get("max_time") or f.get("begin_time")) or 0) > now() - 86400]
            def rank(c):
                try:
                    return "ABCMX".find(c[0].upper()) * 100 + float(c[1:] or 0)
                except (TypeError, ValueError, IndexError, AttributeError):
                    return -1
            if day:
                big = max(day, key=lambda f: rank(f.get("max_class")))
                d["flare"], d["flare_time"] = big.get("max_class"), big.get("max_time")
            d["flares_24h"] = len(day)
        except Exception as e:
            errs.append(f"flares: {e}")
        if d:
            d["at"] = now()
            self.store.kv_set("spacewx", d)
        self.store.health("Space weather (NOAA SWPC)", "space", "kp" in d or "wind_kms" in d, len(d), "; ".join(errs)[:200])

    # ---------- people in space right now ----------
    def pull_people(self):
        """Who is in orbit (ISS, Tiangong, any other crewed flight), every 6 hours."""
        out, errs = None, []
        try:
            d = fetch_json("https://corquaid.github.io/international-space-station-APIs/JSON/people-in-space.json", timeout=30)
            ppl = []
            for x in d.get("people") or []:
                if not isinstance(x, dict) or not x.get("name"):
                    continue
                ppl.append({k: x.get(k) for k in ("name", "country", "flag_code", "agency", "position", "spacecraft", "launched", "iss", "url", "image")})
            if ppl:
                out = {"people": ppl, "expedition": d.get("iss_expedition"), "src": "corquaid ISS API", "at": now()}
        except (FetchError, ValueError, AttributeError) as e:
            errs.append(f"corquaid: {e}")
        if not out:
            try:
                d = fetch_json("http://api.open-notify.org/astros.json", timeout=30)
                ppl = [{"name": x.get("name"), "spacecraft": x.get("craft")} for x in d.get("people") or [] if isinstance(x, dict) and x.get("name")]
                if ppl:
                    out = {"people": ppl, "src": "Open Notify", "at": now()}
            except (FetchError, ValueError, AttributeError) as e:
                errs.append(f"open-notify: {e}")
        if out:
            self.store.kv_set("people", out)
        self.store.health("People in space", "space", bool(out), len(out["people"]) if out else 0, "; ".join(errs)[:200])

    def people(self):
        return self.store.kv_get("people") or {"people": [], "at": None}

    # ---------- governments: who holds office (Wikidata, daily) and the economy in numbers (World Bank, weekly) ----------
    WIKIDATA = "https://query.wikidata.org/sparql"

    def _sparql(self, q, timeout=90):
        d = fetch_json(self.WIKIDATA + "?" + urllib.parse.urlencode({"query": q, "format": "json"}), timeout=timeout,
                       headers={"Accept": "application/sparql-results+json", "User-Agent": UA + " (Archie World governments view)"})
        return [{k: v.get("value") for k, v in b.items()} for b in (d.get("results") or {}).get("bindings") or []]

    def _gov_isos(self):
        try:
            with open(os.path.join(WEB_DIR, "data", "govs.json"), encoding="utf-8") as f:
                return [c["iso2"] for c in json.load(f) if c.get("iso2") and len(c["iso2"]) == 2 and c["iso2"] != "EU"]
        except (OSError, ValueError):
            return []

    def pull_govs(self):
        """Heads of state and government for every country, with when they took office, plus each country's flag."""
        isos = self._gov_isos()
        if not isos:
            return
        out, errs = {}, []
        for i in range(0, len(isos), 70):
            vals = " ".join('"%s"' % x for x in isos[i:i + 70])
            q = """SELECT ?iso ?c ?flag ?hos ?hosLabel ?hs ?hog ?hogLabel ?gs ?hosOffLabel ?hogOffLabel WHERE {
  VALUES ?iso { %s }
  ?c wdt:P297 ?iso . FILTER NOT EXISTS { ?c wdt:P576 ?gone }
  OPTIONAL { ?c wdt:P41 ?flag }
  OPTIONAL { ?c wdt:P1906 ?hosOff }
  OPTIONAL { ?c wdt:P1313 ?hogOff }
  OPTIONAL { ?c p:P35 ?s1 . ?s1 ps:P35 ?hos . FILTER NOT EXISTS { ?s1 pq:P582 ?e1 } MINUS { ?s1 wikibase:rank wikibase:DeprecatedRank } OPTIONAL { ?s1 pq:P580 ?hs } }
  OPTIONAL { ?c p:P6 ?s2 . ?s2 ps:P6 ?hog . FILTER NOT EXISTS { ?s2 pq:P582 ?e2 } MINUS { ?s2 wikibase:rank wikibase:DeprecatedRank } OPTIONAL { ?s2 pq:P580 ?gs } }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}""" % vals
            try:
                rows = self._sparql(q)
            except (FetchError, ValueError) as e:
                errs.append(str(e)[:80]); continue
            for r in rows:
                iso = r.get("iso")
                c = out.setdefault(iso, {"qid": (r.get("c") or "").rsplit("/", 1)[-1], "flag": r.get("flag"), "hos": {}, "hog": {},
                                         "hosOffice": r.get("hosOffLabel"), "hogOffice": r.get("hogOffLabel")})
                for fk, rk in (("flag", "flag"), ("hosOffice", "hosOffLabel"), ("hogOffice", "hogOffLabel")):
                    if not c.get(fk) and r.get(rk):
                        c[fk] = r[rk]
                for role, pk, sk in (("hos", "hos", "hs"), ("hog", "hog", "gs")):
                    if r.get(pk):
                        qid = r[pk].rsplit("/", 1)[-1]
                        prev = c[role].get(qid)
                        start = (r.get(sk) or "")[:10]
                        if not prev or (start and start > (prev.get("since") or "")):
                            c[role][qid] = {"name": r.get(pk + "Label"), "since": start, "qid": qid}
            time.sleep(1)
        for iso, c in out.items():   # newest holder first; keep co-holders (co-princes, captains regent) but drop stale ones
            for role in ("hos", "hog"):
                L = sorted(c[role].values(), key=lambda x: x.get("since") or "", reverse=True)
                if len(L) > 1 and L[0].get("since"):
                    L = [x for x in L if not x.get("since") or x["since"] >= L[0]["since"][:4] + "-00"] or L[:1]
                c[role] = L[:3]
        self._fix_qid_names(out)
        if out:
            self.store.kv_set("govs_live", out)   # flags are built in (World/web/flags), so nothing to download
        self.store.health("Governments: officeholders (Wikidata)", "world", bool(out), len(out), "; ".join(errs)[:200])

    def _fix_qid_names(self, out):
        """Wikidata's label service sometimes gives back the item number (Q22686) instead of the name; look those up directly."""
        need = sorted({p["qid"] for c in out.values() for role in ("hos", "hog") for p in c.get(role) or [] if re.match(r"^Q\d+$", p.get("name") or "")})
        names = {}
        for i in range(0, len(need), 45):
            try:
                d = fetch_json("https://www.wikidata.org/w/api.php?" + urllib.parse.urlencode({"action": "wbgetentities", "ids": "|".join(need[i:i + 45]), "props": "labels",
                                                                                                 "languages": "en", "languagefallback": "1", "format": "json"}), timeout=40)
                for q, e in (d.get("entities") or {}).items():
                    lab = ((e.get("labels") or {}).get("en") or {}).get("value")
                    if lab:
                        names[q] = lab
            except (FetchError, ValueError, AttributeError):
                pass
        for c in out.values():
            for role in ("hos", "hog"):
                keep = []
                for p in c.get(role) or []:
                    if re.match(r"^Q\d+$", p.get("name") or ""):
                        if p["qid"] in names:
                            p["name"] = names[p["qid"]]
                        else:
                            continue   # no name: leave it out and let the Factbook's name show
                    keep.append(p)
                c[role] = keep

    def _pull_flags(self, live):
        os.makedirs(FLAG_DIR, exist_ok=True)
        want = {iso: c.get("flag") for iso, c in live.items() if c.get("flag")}
        want["EU"] = "http://commons.wikimedia.org/wiki/Special:FilePath/Flag%20of%20Europe.svg"
        for iso, url in want.items():
            path = os.path.join(FLAG_DIR, iso + ".png")
            if os.path.isfile(path) and time.time() - os.path.getmtime(path) < 90 * 86400:
                continue
            try:
                body, _, ctype = fetch(url.replace("http://", "https://") + "?width=160", timeout=30, raw=True)
                if body[:4] == b"\x89PNG":
                    with open(path, "wb") as f:
                        f.write(body)
            except FetchError:
                pass
            time.sleep(0.2)

    WB_IND = {"gdp": "NY.GDP.MKTP.CD", "percap": "NY.GDP.PCAP.CD", "growth": "NY.GDP.MKTP.KD.ZG", "inflation": "FP.CPI.TOTL.ZG",
              "unemp": "SL.UEM.TOTL.ZS", "pop": "SP.POP.TOTL", "milgdp": "MS.MIL.XPND.GD.ZS", "debt": "GC.DOD.TOTL.GD.ZS", "trade": "NE.TRD.GNFS.ZS"}

    def pull_worldbank(self):
        out, errs = {}, []
        for key, ind in self.WB_IND.items():
            try:
                d = fetch_json("https://api.worldbank.org/v2/country/all/indicator/%s?format=json&mrnev=1&per_page=500" % ind, timeout=60)
                for r in (d[1] if isinstance(d, list) and len(d) > 1 and d[1] else []):
                    iso = ((r.get("country") or {}).get("id") or "")
                    if len(iso) == 2 and r.get("value") is not None:
                        out.setdefault(iso, {})[key] = [r["value"], r.get("date")]
            except (FetchError, ValueError, IndexError, AttributeError) as e:
                errs.append(f"{ind}: {e}")
            time.sleep(0.5)
        if out:
            self.store.kv_set("worldbank", out)
        self.store.health("Economy numbers (World Bank)", "world", bool(out), len(out), "; ".join(errs)[:200])

    def govs(self):
        return {"live": self.store.kv_get("govs_live") or {}, "at": self.store.kv_age("govs_live"),
                "wb": self.store.kv_get("worldbank") or {}, "wbAge": self.store.kv_age("worldbank"),
                "flags": sorted(f[:-4] for f in os.listdir(FLAG_DIR) if f.endswith(".png")) if os.path.isdir(FLAG_DIR) else []}

    # ---------- full administrations: the CIA's World Leaders directory (every foreign country) and the White House (US) ----------
    CIA_WL = "https://www.cia.gov/resources/world-leaders"
    ABBR = {"Pres.": "President", "Min.": "Minister", "Dep.": "Deputy", "Sec.": "Secretary", "Gen.": "General", "Admin.": "Administration",
            "Govt.": "Government", "Natl.": "National", "Dir.": "Director", "Amb.": "Ambassador", "Perm.": "Permanent", "Rep.": "Representative",
            "Chmn.": "Chairman", "Chrm.": "Chairman", "Gov.": "Governor", "Cdr.": "Commander", "Info.": "Information", "Dev.": "Development",
            "Intl.": "International", "Coop.": "Cooperation", "Env.": "Environment", "Affs.": "Affairs", "Econ.": "Economy", "Mgmt.": "Management",
            "Mil.": "Military", "Comm.": "Commission", "Cmte.": "Committee", "Assoc.": "Associate", "Asst.": "Assistant", "Exec.": "Executive",
            "Pub.": "Public", "Prov.": "Provincial", "Fed.": "Federal", "Dept.": "Department", "Org.": "Organization", "Bd.": "Board",
            "Cncl.": "Council", "Coun.": "Council", "Supt.": "Superintendent", "Atty.": "Attorney", "Chf.": "Chief", "Pol.": "Political",
            "Ldr.": "Leader", "Pltbr.": "Politburo", "Mbr.": "Member", "Natl": "National"}

    def _cia_title(self, t):
        return " ".join(self.ABBR.get(w, w) for w in (t or "").split())

    def pull_cia_leaders(self):
        """Weekly: every foreign government's leaders and cabinet from the CIA's World Leaders directory (public domain)."""
        base = self.CIA_WL + "/page-data"
        out, errs = {}, []
        try:
            idx = fetch_json(base + "/foreign-governments/page-data.json", timeout=40)
            names = None
            for h in idx.get("staticQueryHashes") or []:
                try:
                    sq = fetch_json(base + "/sq/d/%s.json" % h, timeout=40)
                except FetchError:
                    continue
                nodes = (((sq.get("data") or {}).get("leaders") or {}).get("nodes")) or []
                if nodes and nodes[0].get("country"):
                    names = [n["country"] for n in nodes]
                    break
            if not names:
                raise FetchError("country list not found")
        except (FetchError, ValueError, AttributeError) as e:
            self.store.health("Cabinets: CIA World Leaders", "world", False, 0, str(e)[:200]); return
        def slug(x):
            x = unicodedata.normalize("NFD", x.lower())
            x = "".join(ch for ch in x if unicodedata.category(ch) != "Mn")
            return re.sub(r"[^a-z0-9]+", "-", re.sub(r"['\u2019]", "", x)).strip("-")
        def people(L):
            res = []
            for x in L or []:
                nm, tt = (x.get("name") or "").strip(), (x.get("title") or "").strip()
                if not nm and not tt:
                    continue
                acting = "(Acting)" in nm or "(Interim)" in nm
                res.append({"title": self._cia_title(tt), "name": re.sub(r"\s*\((Acting|Interim)\)", "", nm).strip(), "hon": (x.get("honorific") or "").strip(), "acting": acting, "vacant": not nm or nm.lower().startswith("vacant")})
            return res
        for n in names:
            if self.stop.is_set():
                break
            try:
                pg = (((fetch_json(base + "/foreign-governments/%s/page-data.json" % slug(n), timeout=40).get("result") or {}).get("data") or {}).get("page")) or {}
                code = (pg.get("code") or "").lower()
                if not code:
                    continue
                groups = []
                for k, lk in (("leaders", "leaders_label"), ("leaders_2", "leaders_2_label"), ("leaders_3", "leaders_3_label")):
                    ppl = people(pg.get(k))
                    if ppl:
                        groups.append({"label": pg.get(lk) or "", "people": ppl})
                out[code] = {"country": pg.get("country") or n, "updated": (pg.get("date_updated") or "")[:10], "caveat": re.sub(r"<[^>]+>", " ", pg.get("caveat") or "").strip()[:600],
                             "groups": groups, "source": "CIA World Leaders directory", "url": self.CIA_WL + "/foreign-governments/" + slug(n) + "/"}
            except (FetchError, ValueError, AttributeError) as e:
                errs.append(f"{n}: {e}")
            time.sleep(0.6)
        if out:
            self.store.kv_set("cia_leaders", out)
        self.store.health("Cabinets: CIA World Leaders", "world", bool(out), len(out), "; ".join(errs[:5])[:200])

    def pull_us_cabinet(self):
        """Weekly: the US Cabinet, names and titles only, from the White House's own page."""
        try:
            h = fetch("https://www.whitehouse.gov/administration/cabinet/", timeout=40)
            main = h.split("<main", 1)[-1]
            heads = re.findall(r"<(h2|h3)[^>]*>(.*?)</\1>", main, re.S)
            ppl, cur = [], None
            OFFICE = re.compile(r"secretary|attorney general|director|administrator|representative|ambassador|chief of staff|vice president|adviser|advisor|counsel", re.I)
            for tag, txt in heads:
                t = html.unescape(re.sub(r"<[^>]+>", "", txt)).strip()
                if not t:
                    continue
                if tag == "h2":
                    cur = t
                elif cur:
                    if OFFICE.search(t) and len(cur.split()) <= 6 and not re.search(r"subscribe|newsletter|initiative|news|briefing", cur + " " + t, re.I):
                        ppl.append({"title": t, "name": cur, "hon": "", "acting": "acting" in t.lower(), "vacant": False})
                    cur = None
            if len(ppl) < 8:
                raise FetchError(f"only {len(ppl)} cabinet members found")
            if not any("vice president" in p["title"].lower() for p in ppl):
                try:     # the White House's cabinet page leaves out the Vice President; Wikidata has the current holder
                    q = ("SELECT ?p ?pLabel ?start WHERE { ?p p:P39 ?s . ?s ps:P39 wd:Q11699 . OPTIONAL { ?s pq:P580 ?start } "
                         "FILTER NOT EXISTS { ?s pq:P582 ?end } SERVICE wikibase:label { bd:serviceParam wikibase:language \"en\". } }")
                    rows = sorted(self._sparql(q), key=lambda b: b.get("start") or "", reverse=True)
                    if rows and rows[0].get("pLabel") and not re.match(r"^Q\d+$", rows[0]["pLabel"]):
                        ppl.insert(0, {"title": "Vice President of the United States", "name": rows[0]["pLabel"], "hon": "",
                                       "acting": False, "vacant": False, "since": (rows[0].get("start") or "")[:10]})
                except Exception:
                    pass
            self.store.kv_set("us_cabinet", {"country": "United States", "updated": datetime.date.today().isoformat(), "caveat": "", "source": "The White House (whitehouse.gov/administration/cabinet)",
                                             "url": "https://www.whitehouse.gov/administration/cabinet/", "groups": [{"label": "", "people": ppl}]})
            self.store.health("Cabinet: United States (White House)", "world", True, len(ppl))
        except (FetchError, ValueError) as e:
            self.store.health("Cabinet: United States (White House)", "world", False, 0, str(e)[:200])

    def gov_cabinet(self, iso, gec=""):
        """The full administration: the CIA directory (or the White House for the US); Wikidata only as a fallback."""
        iso = re.sub(r"[^A-Z]", "", str(iso).upper())[:2]
        gec = re.sub(r"[^a-z]", "", str(gec).lower())[:2]
        if iso == "US":
            d = self.store.kv_get("us_cabinet")
            if d:
                for g in d.get("groups") or []:
                    g["people"] = [p for p in g.get("people") or [] if not re.search(r"subscribe|newsletter|initiative", (p.get("name") or "") + " " + (p.get("title") or ""), re.I)]
                return d
        elif gec:
            d = (self.store.kv_get("cia_leaders") or {}).get(gec)
            if d:
                return d
        return self._wikidata_cabinet(iso)

    def _wikidata_cabinet(self, iso):
        key = "cab:" + iso
        d = self.store.kv_get(key)
        if d and self.store.kv_age(key) < 86400:
            return d
        live = (self.store.kv_get("govs_live") or {}).get(iso) or {}
        qid = live.get("qid")
        if not qid:
            try:
                r = self._sparql('SELECT ?c WHERE { ?c wdt:P297 "%s" . FILTER NOT EXISTS { ?c wdt:P576 ?g } } LIMIT 1' % iso, timeout=30)
                qid = r[0]["c"].rsplit("/", 1)[-1] if r else None
            except (FetchError, ValueError):
                qid = None
        if not qid:
            return d or {"ministers": [], "error": "not reachable right now"}
        q = """SELECT DISTINCT ?pos ?posLabel ?person ?personLabel ?start ?partyLabel WHERE {
  { ?pos wdt:P1001 wd:%(q)s . ?pos (wdt:P31|wdt:P279)/wdt:P279* wd:Q83307 . }
  UNION { wd:%(q)s wdt:P208 ?gov . ?pos wdt:P361 ?gov . }
  ?person p:P39 ?st . ?st ps:P39 ?pos .
  FILTER NOT EXISTS { ?st pq:P582 ?end }
  MINUS { ?st wikibase:rank wikibase:DeprecatedRank }
  FILTER NOT EXISTS { ?person wdt:P570 ?died }
  OPTIONAL { ?st pq:P580 ?start }
  OPTIONAL { ?person p:P102 ?ps . ?ps ps:P102 ?party . FILTER NOT EXISTS { ?ps pq:P582 ?pe } }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
} LIMIT 400""" % {"q": qid}
        try:
            rows = self._sparql(q, timeout=90)
        except (FetchError, ValueError) as e:
            return d or {"ministers": [], "error": "Wikidata didn't answer (" + str(e)[:60] + ")"}
        by = {}
        cutoff = str(datetime.datetime.utcnow().year - 12)
        for r in rows:
            pos = r.get("posLabel") or ""
            if not pos or re.match(r"^Q\d+$", pos):
                continue
            start = (r.get("start") or "")[:10]
            if start and start < cutoff:   # a holder with no recorded end date from long ago is almost always out of date
                continue
            cur = by.get(pos)
            if not cur or (start or "") > (cur.get("since") or ""):
                by[pos] = {"office": pos, "name": r.get("personLabel"), "since": start, "party": r.get("partyLabel") or "", "qid": (r.get("person") or "").rsplit("/", 1)[-1]}
            elif cur and r.get("partyLabel") and not cur.get("party"):
                cur["party"] = r.get("partyLabel")
        d = {"ministers": sorted(by.values(), key=lambda x: x["office"]), "at": now(), "qid": qid, "source": "Wikidata",
             "groups": [{"label": "", "people": [{"title": m["office"], "name": m["name"], "hon": "", "acting": False, "vacant": False, "since": m["since"], "party": m["party"]} for m in sorted(by.values(), key=lambda x: x["office"])]}]}
        self.store.kv_set(key, d)
        return d

    # ---------- the Voyager Golden Record's pictures, from NASA's gallery, kept on this PC ----------
    GOLD_GALLERY = "https://science.nasa.gov/gallery/images-on-the-golden-record/page/{}/"

    def golden(self):
        """The album as far as it has downloaded; the first call starts the download in the background."""
        idx = os.path.join(GOLD_DIR, "index.json")
        try:
            with open(idx, encoding="utf-8") as f:
                d = json.load(f)
        except (OSError, ValueError):
            d = {"images": [], "done": False}
        busy = getattr(self, "_gold_busy", False)
        if not d.get("done") and not busy and self.is_online:
            self._gold_busy = True
            threading.Thread(target=self._golden_fetch, daemon=True).start()
            busy = True
        for im in d.get("images", []):
            if im.get("file"):
                im["url"] = "/golden/" + urllib.parse.quote(im["file"])
        d["busy"] = busy
        return d

    def _golden_fetch(self):
        os.makedirs(GOLD_DIR, exist_ok=True)
        idx = os.path.join(GOLD_DIR, "index.json")
        try:
            try:
                with open(idx, encoding="utf-8") as f:
                    d = json.load(f)
            except (OSError, ValueError):
                d = {"images": [], "done": False}
            have = {im["page"]: im for im in d["images"]}
            pages = []
            for n in range(1, 12):   # the gallery's pages, until one adds nothing new
                try:
                    gal = fetch(self.GOLD_GALLERY.format(n), timeout=40)
                except FetchError:
                    break
                links = re.findall(r'href="(https://science\.nasa\.gov/(?:image-detail/[^"#?]+|wp-content/uploads/[^"#?]+\.(?:jpe?g|png|gif)))"', gal)
                new = [u for u in dict.fromkeys(links) if u not in pages]
                if not new:
                    break
                pages += new
                time.sleep(0.5)
            if not pages:
                raise FetchError("no pictures found in NASA's gallery")
            out = []
            for u in pages:
                if self.stop.is_set():
                    return
                if u in have and have[u].get("file") and os.path.isfile(os.path.join(GOLD_DIR, have[u]["file"])):
                    out.append(have[u]); continue
                title, desc, img = "", "", u
                if "/image-detail/" in u:
                    try:
                        h = fetch(u, timeout=40)
                        m = re.search(r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', h) or re.search(r'content="([^"]+)"[^>]+property="og:image"', h)
                        img = html.unescape(m.group(1)) if m else ""
                        t = re.search(r'<meta[^>]+property="og:title"[^>]+content="([^"]+)"', h)
                        title = html.unescape(t.group(1)).split(" - ")[0].strip() if t else ""
                        ds = re.search(r'<meta[^>]+(?:property="og:description"|name="description")[^>]+content="([^"]*)"', h)
                        desc = html.unescape(ds.group(1)).strip() if ds else ""
                    except FetchError:
                        img = ""
                if not title:
                    slug = u.rstrip("/").split("/")[-1].rsplit(".", 1)[0]
                    title = re.sub(r"-\d{8,}-o$", "", slug).replace("-", " ").strip().capitalize()
                item = {"page": u, "title": title, "about": desc[:400], "file": None}
                if img:
                    try:
                        body, _, ctype = fetch(img.replace(" ", "%20"), timeout=60, raw=True)
                        ext = os.path.splitext(urllib.parse.urlparse(img).path)[1].lower()
                        ext = ext if ext in (".jpg", ".jpeg", ".png", ".gif", ".webp") else ".jpg"
                        fn = "%03d-" % (len(out) + 1) + re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:50] + ext
                        with open(os.path.join(GOLD_DIR, fn), "wb") as f:
                            f.write(body)
                        item["file"] = fn
                    except (FetchError, OSError):
                        pass
                out.append(item)
                with open(idx, "w", encoding="utf-8") as f:
                    json.dump({"images": out, "done": False, "source": "NASA Science: Images on the Golden Record"}, f, indent=1)
                time.sleep(0.4)
            with open(idx, "w", encoding="utf-8") as f:
                json.dump({"images": out, "done": True, "at": now(), "source": "NASA Science: Images on the Golden Record"}, f, indent=1)
            self.store.health("Golden Record pictures (NASA)", "space", True, sum(1 for x in out if x.get("file")))
        except (FetchError, OSError, ValueError) as e:
            self.store.health("Golden Record pictures (NASA)", "space", False, 0, str(e)[:200])
        finally:
            self._gold_busy = False

    def pull_marswx(self):
        """The latest weather report from NASA's Curiosity rover on Mars."""
        try:
            d = fetch_json("https://mars.nasa.gov/rss/api/?feed=weather&category=msl&feedtype=json", timeout=30)
            sols = d.get("soles") or []
            good = next((x for x in sols if x.get("max_temp") not in (None, "--", "")), None)
            if good:
                self.store.kv_set("marswx", {k: good.get(k) for k in ("sol", "terrestrial_date", "min_temp", "max_temp", "pressure",
                                                                     "atmo_opacity", "season", "sunrise", "sunset", "ls")})
            self.store.health("Mars weather (Curiosity)", "space", bool(good), 1 if good else 0)
        except (FetchError, ValueError) as e:
            self.store.health("Mars weather (Curiosity)", "space", False, 0, str(e))

    def solar(self):
        return {"craft": self.store.kv_get("craft", {}), "spacewx": self.store.kv_get("spacewx"),
                "marswx": self.store.kv_get("marswx"), "launches": [l for l in (self.store.kv_get("launches") or []) if (l.get("t") or 0) > now() - 3 * 3600],
                "now": now()}

    # where the long-haul probes have been: NASA JPL Horizons, a point a week since launch (the Grand Tour)
    TRAIL_CRAFT = [(-31, "Voyager 1", "1977-09-06", ""), (-32, "Voyager 2", "1977-08-21", ""), (-98, "New Horizons", "2006-01-20", ""),
                   (-23, "Pioneer 10", "1972-03-04", "2003-01-22"), (-24, "Pioneer 11", "1973-04-07", "1995-09-30"),
                   (-82, "Cassini", "1997-10-16", "2017-09-14"), (-77, "Galileo", "1989-10-19", "2003-09-20")]

    def pull_trails(self):
        out, errs = self.store.kv_get("trails", {}) or {}, []
        today = datetime.datetime.utcnow().strftime("%Y-%m-%d")
        mon = {m: i + 1 for i, m in enumerate(["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"])}
        def hz(cid, start, stop):
            q = urllib.parse.urlencode({"format": "json", "COMMAND": f"'{cid}'", "OBJ_DATA": "'NO'", "MAKE_EPHEM": "'YES'", "EPHEM_TYPE": "'VECTORS'",
                                        "CENTER": "'500@10'", "START_TIME": f"'{start}'", "STOP_TIME": f"'{stop}'", "STEP_SIZE": "'7 d'",
                                        "VEC_TABLE": "'1'", "OUT_UNITS": "'AU-D'", "REF_PLANE": "'ECLIPTIC'", "REF_SYSTEM": "'ICRF'", "CSV_FORMAT": "'YES'"})
            return (fetch_json("https://ssd.jpl.nasa.gov/api/horizons.api?" + q, timeout=90).get("result") or "")
        def when(m):
            return "%s-%02d-%s %s" % (m.group(1), mon[m.group(2)], m.group(3), m.group(4))
        for cid, name, start, stop in self.TRAIL_CRAFT:
            if self.stop.is_set():
                break
            if stop and str(cid) in out:
                continue       # finished missions never change
            try:
                a, b = start + " 12:00", (stop or today) + " 00:00"
                txt = hz(cid, a, b)
                for _ in range(2):   # Horizons says when its data really starts or ends; ask again inside those dates
                    m1 = re.search(r"prior to A\.D\. (\d{4})-([A-Z]{3})-(\d{2}) (\d\d:\d\d)", txt)
                    m2 = re.search(r"after A\.D\. (\d{4})-([A-Z]{3})-(\d{2}) (\d\d:\d\d)", txt)
                    if "$$SOE" in txt or not (m1 or m2):
                        break
                    if m1:
                        a = when(m1)
                    if m2:
                        b = when(m2)
                    time.sleep(1.5)
                    txt = hz(cid, a, b)
                block = txt.split("$$SOE", 1)[1].split("$$EOE", 1)[0] if "$$SOE" in txt else ""
                pts = []
                for line in block.strip().splitlines():
                    f = [x.strip() for x in line.split(",")]
                    if len(f) >= 5:
                        try:
                            jd = float(f[0])
                            pts.append([round((jd - 2440587.5) * 86400), round(float(f[2]), 4), round(float(f[3]), 4), round(float(f[4]), 4)])
                        except ValueError:
                            continue
                if len(pts) > 10:
                    out[str(cid)] = {"name": name, "pts": pts}
                else:
                    errs.append(f"{name}: no points")
            except (FetchError, ValueError, KeyError) as e:
                errs.append(f"{name}: {e}")
            time.sleep(1.5)
        if out:
            self.store.kv_set("trails", out)
        self.store.health("Spacecraft paths (NASA JPL)", "space", len(out) > 0, len(out), "; ".join(errs)[:200])

    def pull_rovers(self):
        """Every stop Curiosity and Perseverance have made (NASA's rover location maps)."""
        out, errs = self.store.kv_get("rovers", {}) or {}, []
        for key, url in (("curiosity", "https://mars.nasa.gov/mmgis-maps/MSL/Layers/json/MSL_waypoints.json"),
                         ("perseverance", "https://mars.nasa.gov/mmgis-maps/M20/Layers/json/M20_waypoints.json")):
            try:
                d = fetch_json(url, timeout=90)
                pts = []
                for f in d.get("features") or []:
                    pr = f.get("properties") or {}
                    if pr.get("lon") is None or pr.get("lat") is None:
                        continue
                    pts.append([int(pr.get("sol") or 0), round(float(pr["lon"]), 6), round(float(pr["lat"]), 6),
                                round(float(pr.get("dist_km") or (pr.get("dist_total_m") or 0) / 1000.0), 2)])
                pts.sort(key=lambda x: x[0])
                if pts:
                    out[key] = {"pts": pts, "at": now()}
            except (FetchError, ValueError, KeyError, TypeError) as e:
                errs.append(f"{key}: {e}")
            time.sleep(1)
        if out:
            self.store.kv_set("rovers", out)
        self.store.health("Mars rover routes (NASA)", "space", not errs, len(out), "; ".join(errs)[:200])

    def pull_launches(self):
        """The next rocket launches worldwide (The Space Devs' Launch Library)."""
        try:
            d = fetch_json("https://ll.thespacedevs.com/2.2.0/launch/upcoming/?limit=25&mode=normal&hide_recent_previous=true", timeout=60)
            out = []
            for l in d.get("results") or []:
                ts = parse_date(l.get("net"))
                if not ts:
                    continue
                g = lambda o, *ks: next((o.get(k) for k in ks if isinstance(o, dict) and o.get(k)), None)
                pad = l.get("pad") if isinstance(l.get("pad"), dict) else {}
                loc = pad.get("location") if isinstance(pad.get("location"), dict) else {}
                mis = l.get("mission") if isinstance(l.get("mission"), dict) else {}
                rk = ((l.get("rocket") or {}).get("configuration") or {}) if isinstance(l.get("rocket"), dict) else {}
                lsp = l.get("launch_service_provider") if isinstance(l.get("launch_service_provider"), dict) else {}
                st = l.get("status") if isinstance(l.get("status"), dict) else {}
                orb = mis.get("orbit") if isinstance(mis.get("orbit"), dict) else {}
                out.append({"t": ts, "name": l.get("name") or "", "status": st.get("name") or "", "abbrev": st.get("abbrev") or "",
                            "rocket": rk.get("full_name") or rk.get("name") or "", "provider": lsp.get("name") or "", "ptype": lsp.get("type") or "",
                            "mission": mis.get("name") or "", "about": (mis.get("description") or "")[:600], "mtype": mis.get("type") or "",
                            "orbit": orb.get("name") or "", "pad": pad.get("name") or "", "where": loc.get("name") or "",
                            "cc": loc.get("country_code") or "", "window": [parse_date(l.get("window_start")), parse_date(l.get("window_end"))],
                            "precision": g(l.get("net_precision") or {}, "name") or "", "webcast": bool(l.get("webcast_live"))})
            if out:
                self.store.kv_set("launches", out)
            self.store.health("Rocket launches (The Space Devs)", "space", bool(out), len(out))
        except (FetchError, ValueError, KeyError, TypeError) as e:
            self.store.health("Rocket launches (The Space Devs)", "space", False, 0, str(e)[:200])

    # ---------- live cosmic alerts for the Milky Way view (gravitational waves, supernovae, gamma-ray bursts) ----------
    def pull_cosmic(self):
        import archie_cosmic as AC
        cur = self.store.kv_get("cosmic", {}) or {}
        get = lambda u, timeout=60, headers=None: fetch(u, timeout=timeout, headers=headers)
        getj = lambda u, timeout=60, headers=None: fetch_json(u, timeout=timeout, headers=headers)
        for key, label, fn in (("gw", "Gravitational waves (LIGO-Virgo-KAGRA)", lambda: AC.pull_gw(get, getj, {x["id"]: x for x in cur.get("gw") or []})),
                               ("sn", "Supernovae (Latest Supernovae list)", lambda: AC.pull_sn(get)),
                               ("grb", "Gamma-ray bursts (GCN Circulars)", lambda: AC.pull_grb(get, getj, {x["id"]: x for x in cur.get("grb") or []}))):
            if self.stop.is_set():
                break
            try:
                L = fn()
                if L or key not in cur:
                    cur[key] = L
                self.store.health(label, "space", True, len([x for x in L if not x.get("nopos")]))
            except (FetchError, ValueError, KeyError, TypeError, AttributeError) as e:
                self.store.health(label, "space", False, 0, str(e)[:200])
        cur["at"] = now()
        self.store.kv_set("cosmic", cur)

    # ---------- the Milky Way view: every confirmed planet outside the solar system (NASA Exoplanet Archive) ----------
    EXO_PATH = os.path.join(WORLD_DIR, "exoplanets.json")
    EXO_COLS = ["pl_name", "hostname", "ra", "dec", "sy_dist", "pl_orbper", "pl_orbsmax", "pl_rade", "pl_bmasse", "pl_eqt",
                "pl_orbeccen", "disc_year", "discoverymethod", "disc_facility", "st_spectype", "st_teff", "st_rad", "st_mass",
                "st_age", "sy_pnum"]

    def pull_exo(self):
        """Once a week: the archive's one-row-per-planet table, grouped into star systems and saved next to world.db."""
        q = "select " + ",".join(self.EXO_COLS) + " from pscomppars"
        url = "https://exoplanetarchive.ipac.caltech.edu/TAP/sync?" + urllib.parse.urlencode({"query": q, "format": "json"})
        try:
            rows = fetch_json(url, timeout=120)
            if isinstance(rows, dict):
                rows = rows.get("data") or rows.get("rows") or []
            systems = {}
            for r in rows:
                if not isinstance(r, dict):
                    continue
                host, dist = r.get("hostname"), r.get("sy_dist")
                if not host or dist in (None, "") or r.get("ra") is None or r.get("dec") is None:
                    continue
                def num(k, nd=4):
                    v = r.get(k)
                    try:
                        return round(float(v), nd) if v not in (None, "") else None
                    except (TypeError, ValueError):
                        return None
                sysd = systems.setdefault(host, {"h": host, "ra": num("ra", 4), "dec": num("dec", 4), "ly": round(float(dist) * 3.26156, 1),
                                                  "sp": (r.get("st_spectype") or "")[:12], "t": num("st_teff", 0), "r": num("st_rad", 3),
                                                  "m": num("st_mass", 3), "age": num("st_age", 2), "p": []})
                name = r.get("pl_name") or ""
                sysd["p"].append([name, num("pl_orbper", 4), num("pl_orbsmax", 5), num("pl_rade", 3), num("pl_bmasse", 2), num("pl_eqt", 0),
                                  num("pl_orbeccen", 3), r.get("disc_year"), r.get("discoverymethod") or "", r.get("disc_facility") or ""])
            out = sorted(systems.values(), key=lambda x: x["ly"])
            for x in out:
                x["p"].sort(key=lambda p: (p[1] is None, p[1] or 0))
            if len(out) < 500:
                raise FetchError(f"only {len(out)} systems came back")
            tmp = self.EXO_PATH + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"at": now(), "systems": out}, f, separators=(",", ":"))
            os.replace(tmp, self.EXO_PATH)
            self._exo = None
            n = sum(len(x["p"]) for x in out)
            self.store.health("Exoplanets (NASA Exoplanet Archive)", "space", True, n)
        except (FetchError, ValueError, OSError) as e:
            self.store.health("Exoplanets (NASA Exoplanet Archive)", "space", False, 0, str(e)[:200])

    def exo(self):
        """The saved catalog (the page has its own built-in list of famous systems for before the first download)."""
        cache = getattr(self, "_exo", None)
        try:
            mt = os.path.getmtime(self.EXO_PATH)
        except OSError:
            return {"systems": [], "at": None}
        if not cache or cache[0] != mt:
            try:
                with open(self.EXO_PATH, encoding="utf-8") as f:
                    cache = (mt, json.load(f))
                self._exo = cache
            except (OSError, ValueError):
                return {"systems": [], "at": None}
        return cache[1]

    def pull_volcanoes(self):
        text = fetch("https://volcano.si.edu/news/WeeklyVolcanoRSS.xml")
        root = ET.fromstring(re.sub(r"^[^<]+", "", text).encode("utf-8"))
        rows = []
        for it in root.iter("item"):
            title = it.findtext("title") or ""
            pt = it.findtext("{http://www.georss.org/georss}point")
            lat = lng = None
            if pt:
                try:
                    lat, lng = [float(v) for v in pt.split()[:2]]
                except ValueError:
                    pass
            if lat is None:
                hit = self.geo.find_in_text(title)
                if not hit:
                    continue
                lat, lng = hit[0], hit[1]
            status = "eruption" if re.search(r"erupt", (it.findtext("description") or ""), re.I) else "elevated"
            rows.append(("gvp:" + item_id(title), "volcano", strip_tags(title), lat, lng, None, status,
                         parse_date(it.findtext("pubDate")) or now(), it.findtext("link") or "", "{}"))
        self.store.x("DELETE FROM hazards WHERE id LIKE 'gvp:%'")
        self.store.many("INSERT OR REPLACE INTO hazards(id, kind, title, lat, lng, mag, level, time, url, extra) "
                        "VALUES(?,?,?,?,?,?,?,?,?,?)", rows)
        self.store.health("Smithsonian volcanoes", "hazard", True, len(rows))

    def pull_fires(self):
        key = (self.sources.get("firms_map_key") or "").strip()
        if not key:
            return
        text = fetch(f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{key}/VIIRS_SNPP_NRT/world/1", timeout=60)
        lines = text.splitlines()
        if not lines or "latitude" not in lines[0]:
            raise FetchError("FIRMS: unexpected reply (check the key)")
        head = lines[0].split(",")
        il, io_, ic = head.index("latitude"), head.index("longitude"), head.index("confidence") if "confidence" in head else None
        pts = []
        for ln in lines[1:]:
            p = ln.split(",")
            try:
                if ic is not None and p[ic] in ("l", "low"):
                    continue
                pts.append((round(float(p[il]), 2), round(float(p[io_]), 2)))
            except (ValueError, IndexError):
                continue
        pts = sorted(set(pts))[:6000]
        self.store.kv_set("fires", pts)
        self.store.health("NASA FIRMS wildfires", "hazard", True, len(pts))

    # ---------- news ----------
    def _add_items(self, feed, name, entries, lang="en", side="", lean="", region=None, cc=None):
        rows = []
        fresh = 0
        for e in entries:
            iid = item_id(name, e.get("url") or e.get("id") or e["title"])
            if self.store.q("SELECT 1 FROM items WHERE id=?", (iid,), one=True):
                continue
            pub = e.get("published") or now()
            if pub < now() - 4 * 86400:
                continue
            title = e["title"].strip()
            is_en = lang.startswith("en") and not re.search(r"[\u0400-\u04FF\u0600-\u06FF\u0590-\u05FF]", title)
            needs_ai = 0 if (is_en and feed != "telegram") else 1
            etype = classify(title + " " + (e.get("summary") or "")[:200], strict=feed != "telegram") if is_en else None
            lat = lng = place = pcc = reg = None
            if is_en:
                bbox = REGIONS.get(region) if region else None
                hit = self.geo.find_in_text(title, cc, bbox) or self.geo.find_in_text((e.get("summary") or "")[:300], cc, bbox)
                if hit:
                    lat, lng, pcc, place = hit
                    reg = region_of(lat, lng)
            publisher = e.get("source") or name
            rows.append((iid, publisher, feed, lang, side, lean, title, title if is_en else None,
                         (e.get("summary") or "")[:600], e.get("url") or "", e.get("author") or "", pub, now(),
                         lat, lng, place, pcc, reg or region, etype, topic_for(title, etype) if is_en else None, None, needs_ai))
            fresh += 1
        self.store.many("INSERT OR IGNORE INTO items(id, source, feed, lang, side, lean, title, title_en, summary, url, "
                        "author, published, fetched, lat, lng, place, cc, region, etype, topic, cluster, needs_ai) "
                        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
        return fresh

    def pull_rss(self):
        for s in self.sources.get("rss", []):
            if self.stop.is_set():
                return
            try:
                entries = parse_feed(fetch(s["url"]))
                self._add_items("rss", s["name"], entries, s.get("lang", "en"), s.get("side", ""), s.get("lean", ""))
                self.store.health(s["name"], "rss", True, len(entries))
            except (FetchError, Exception) as e:
                self.store.health(s["name"], "rss", False, 0, str(e))

    def pull_gnews(self):
        for s in self.sources.get("gnews", []):
            if self.stop.is_set():
                return
            hl, gl = s.get("hl", "en-US"), s.get("gl", "US")
            q = urllib.parse.quote(s["q"] + " when:1d")
            url = f"https://news.google.com/rss/search?q={q}&hl={hl}&gl={gl}&ceid={gl}:{hl.split('-')[0]}"
            try:
                entries = parse_feed(fetch(url))
                for e in entries:   # Google appends " - Publisher" to titles
                    if e.get("source") and e["title"].endswith(" - " + e["source"]):
                        e["title"] = e["title"][: -len(e["source"]) - 3]
                lang = hl.split("-")[0]
                self._add_items("gnews", "Google News: " + s["name"], entries[:25], lang, s.get("side", ""), "",
                                s.get("region"))
                self.store.health("Google News: " + s["name"], "gnews", True, len(entries))
            except (FetchError, Exception) as e:
                self.store.health("Google News: " + s["name"], "gnews", False, 0, str(e))

    def pull_local(self):
        for s in self.sources.get("local", []):
            if self.stop.is_set():
                return
            q = urllib.parse.quote(s["q"] + " when:2d")
            try:
                entries = parse_feed(fetch(f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"))
                for e in entries:
                    if e.get("source") and e["title"].endswith(" - " + e["source"]):
                        e["title"] = e["title"][: -len(e["source"]) - 3]
                self._add_items("local", "Local: " + s["name"], entries[:20], "en", "", "", "usa")
                self.store.health("Local: " + s["name"], "local", True, len(entries))
            except (FetchError, Exception) as e:
                self.store.health("Local: " + s["name"], "local", False, 0, str(e))

    def pull_telegram(self):
        for s in self.sources.get("telegram", []):
            if self.stop.is_set():
                return
            ch = s["name"].lstrip("@")
            try:
                posts = parse_telegram(fetch(f"https://t.me/s/{ch}"), ch)
                if not posts:
                    raise FetchError("no public posts (wrong name, or preview turned off)")
                entries = [{"title": p["text"][:400], "summary": p["text"], "url": p["url"], "id": p["id"],
                            "published": p["published"]} for p in posts[-20:]]
                self._add_items("telegram", "Telegram · " + ch, entries, s.get("lang", "en"), s.get("side", ""), "",
                                None, s.get("cc"))
                self.store.health("Telegram · " + ch, "telegram", True, len(posts))
            except (FetchError, Exception) as e:
                self.store.health("Telegram · " + ch, "telegram", False, 0, str(e))

    def ai_model(self):
        try:
            from archie_brain import list_models
            have = list_models() or []
        except Exception:
            have = []
        for m in ("qwen2.5:3b", "llama3.2:3b", "qwen2.5:1.5b", "gemma2:2b", "phi3:mini"):
            if m in have:
                return m
        return self.get_model()

    def run_ai(self, limit=16):
        """Translate + locate a handful of posts. Small batches keep the GPU cool."""
        rows = self.store.q("SELECT * FROM items WHERE needs_ai=1 AND published > ? ORDER BY published DESC LIMIT ?",
                            (now() - 12 * 3600, limit))
        if not rows:
            return
        try:
            from archie_brain import quick_chat
        except Exception:
            return
        model = self.ai_model()
        for r in rows:
            if self.stop.is_set():
                return
            text = (r["summary"] or r["title"] or "")[:1200]
            try:
                out = quick_chat(model, AI_PROMPT.format(lang=r["lang"], side=r["side"] or "unknown", text=text),
                                 max_tokens=220, timeout=90, json_mode=True, temperature=0.1)
                d = json.loads(out)
            except Exception:
                self.store.x("UPDATE items SET needs_ai=2 WHERE id=?", (r["id"],))
                continue
            if d.get("is_report") is False:
                self.store.x("UPDATE items SET needs_ai=0, etype='skip' WHERE id=?", (r["id"],))
                continue
            eng = (d.get("english") or "").strip() or r["title"]
            etype = check_type(d.get("type"), eng)
            src_cc = None
            for s in self.sources.get("telegram", []):
                if r["source"].endswith(s["name"].lstrip("@")):
                    src_cc = s.get("cc")
            bbox = REGIONS.get(r["region"]) if r["region"] else None
            hit = None
            for p in (d.get("places") or [])[:3]:
                if isinstance(p, str):
                    hit = self.geo.lookup(p, src_cc, bbox) or self.geo.lookup(p, None, bbox)
                if hit:
                    break
            if not hit:
                hit = self.geo.find_in_text(eng, src_cc, bbox)
            lat = lng = place = cc = reg = None
            if hit:
                lat, lng, cc, place = hit
                reg = region_of(lat, lng)
            self.store.x("UPDATE items SET title_en=?, etype=?, topic=?, lat=?, lng=?, place=?, cc=?, region=?, needs_ai=0 "
                         "WHERE id=?", (eng[:400], etype, topic_for(eng, etype), lat, lng, place, cc, reg or r["region"], r["id"]))

    # ---------- grouping reports into events / stories ----------
    def recluster(self):
        """Group reports: same kind of event, near each other, similar words, within 12 h
        (conflict) or 36 h (news stories). Confirmed = 2+ different sources."""
        cut = now() - 72 * 3600
        rows = self.store.q("SELECT * FROM items WHERE published > ? AND needs_ai=0 AND title_en IS NOT NULL "
                            "AND COALESCE(etype,'') != 'skip' ORDER BY published", (cut,))
        clusters = []
        for r in rows:
            toks = tokens(r["title_en"])
            military = r["etype"] in MILITARY
            best, bs = None, 0.0
            for c in clusters:
                window = 12 * 3600 if military else 36 * 3600
                if abs(r["published"] - c["last"]) > window:
                    continue
                if military != c["military"]:
                    continue
                s = max(jaccard(toks, m) for m in c["members"])
                if military:
                    if r["lat"] is None or c["lat"] is None or km(r["lat"], r["lng"], c["lat"], c["lng"]) > 60:
                        continue
                    same = r["etype"] == c["etype"] or {r["etype"], c["etype"]} <= {"drone", "missile", "blast"}
                    if not same and s < 0.2:
                        continue
                    s += 0.3 + (0.25 if same else 0)
                if s > bs:
                    best, bs = c, s
            if best and bs >= (0.45 if military else 0.34):
                best["items"].append(r)
                best["members"].append(toks)
                best["last"] = max(best["last"], r["published"])
                if best["lat"] is None and r["lat"] is not None:
                    best["lat"], best["lng"], best["place"], best["cc"], best["region"] = r["lat"], r["lng"], r["place"], r["cc"], r["region"]
            else:
                clusters.append({"items": [r], "members": [toks], "first": r["published"], "last": r["published"],
                                 "military": military, "etype": r["etype"], "lat": r["lat"], "lng": r["lng"],
                                 "place": r["place"], "cc": r["cc"], "region": r["region"]})
        crow, irow = [], []
        for c in clusters:
            srcs = {i["source"] for i in c["items"]}
            head = sorted(c["items"], key=lambda i: (i["feed"] == "telegram", -len(i["title_en"] or "")))[0]
            cid = "c" + item_id(c["items"][0]["id"])
            old = self.store.q("SELECT alerted FROM clusters WHERE id=?", (cid,), one=True)
            crow.append((cid, c["first"], c["last"], c["etype"], topic_for(head["title_en"], c["etype"]),
                         c["lat"], c["lng"], c["place"], c["cc"], c["region"], head["title_en"], len(srcs),
                         1 if len(srcs) >= 2 or any(i["feed"] == "acled" for i in c["items"]) else 0, old["alerted"] if old else 0,
                         "event" if c["military"] or c["etype"] in ("aid", "protest", "police", "ship", "fire", "defense") and c["lat"] is not None else "story"))
            for i in c["items"]:
                irow.append((cid, i["id"]))
        self.store.many("INSERT OR REPLACE INTO clusters(id, first, last, etype, topic, lat, lng, place, cc, region, title, "
                        "n_sources, confirmed, alerted, kind) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", crow)
        keep = {r[0] for r in crow}
        stale = [(r["id"],) for r in self.store.q("SELECT id FROM clusters WHERE last > ?", (cut,)) if r["id"] not in keep]
        self.store.many("DELETE FROM clusters WHERE id=?", stale)
        self.store.many("UPDATE items SET cluster=? WHERE id=?", irow)

    # ---------- markets ----------
    def _yahoo(self, sym, rng="1d", interval="15m"):
        d = fetch_json(f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(sym)}"
                       f"?range={rng}&interval={interval}&includePrePost=false")
        res = (d.get("chart") or {}).get("result") or []
        if not res:
            raise FetchError("no data")
        r = res[0]
        meta = r.get("meta", {})
        closes = [c for c in (((r.get("indicators") or {}).get("quote") or [{}])[0].get("close") or []) if c is not None]
        return meta, closes, r.get("timestamp") or []

    def pull_markets(self):
        quotes = self.store.kv_get("quotes", {})
        ok = 0
        syms = [m[1] for m in MARKETS] + [s for s in EXCHANGE_INDEX.values() if s not in {m[1] for m in MARKETS}]
        for sym in syms:
            if self.stop.is_set():
                return
            try:
                meta, closes, _ = self._yahoo(sym)
                price = meta.get("regularMarketPrice") or (closes[-1] if closes else None)
                prev = meta.get("chartPreviousClose") or meta.get("previousClose")
                if price is None or not prev:
                    continue
                q = quotes.get(sym, {})
                q.update({"price": price, "prev": prev, "chg": (price / prev - 1) * 100, "spark": [round(c, 5) for c in closes][-40:],
                          "time": meta.get("regularMarketTime"), "state": meta.get("marketState", "")})
                quotes[sym] = q
                ok += 1
            except FetchError:
                continue
            time.sleep(0.15)
        self.store.kv_set("quotes", quotes)
        self.store.health("Yahoo Finance prices", "markets", ok > 0, ok, "" if ok else "no quotes came back")

    def pull_markets_daily(self):
        quotes = self.store.kv_get("quotes", {})
        for label, sym, *_ in MARKETS:
            if self.stop.is_set():
                return
            try:
                meta, closes, ts = self._yahoo(sym, "ytd", "1d")
                if len(closes) >= 2:
                    q = quotes.setdefault(sym, {})
                    q["w1"] = (closes[-1] / closes[max(0, len(closes) - 6)] - 1) * 100
                    q["ytd"] = (closes[-1] / closes[0] - 1) * 100
                    q["d5"] = [round(c, 5) for c in closes[-5:]]
            except FetchError:
                continue
            time.sleep(0.2)
        self.store.kv_set("quotes", quotes)

    def pull_fred(self):
        ids = ",".join([i for _, i in FRED_CURVE] + [i for _, i in FRED_OTHER])
        text = fetch(timeout=60, url=f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={ids}&cosd="
                     f"{(datetime.date.today() - datetime.timedelta(days=45)).isoformat()}")
        lines = [l.split(",") for l in text.strip().splitlines()]
        head = lines[0]
        series = {h: [] for h in head[1:]}
        for row in lines[1:]:
            for h, v in zip(head[1:], row[1:]):
                try:
                    series[h].append((row[0], float(v)))
                except ValueError:
                    pass
        def last(h, back=0):
            s = series.get(h) or []
            return s[-1 - back][1] if len(s) > back else None
        def month_ago(h):
            s = series.get(h) or []
            if not s:
                return None
            target = (datetime.date.fromisoformat(s[-1][0]) - datetime.timedelta(days=30)).isoformat()
            older = [v for d, v in s if d <= target]
            return older[-1] if older else s[0][1]
        curve = {"t": [t for t, _ in FRED_CURVE], "now": [last(i) for _, i in FRED_CURVE],
                 "prev": [last(i, 1) for _, i in FRED_CURVE], "ago": [month_ago(i) for _, i in FRED_CURVE],
                 "date": (series.get("DGS10") or [("", 0)])[-1][0]}
        other = {lab: {"now": last(i), "prev": last(i, 1)} for lab, i in FRED_OTHER}
        self.store.kv_set("curve", curve)
        self.store.kv_set("fred", other)
        self.store.health("FRED (Treasury yields, spreads)", "markets", curve["now"][7] is not None, len(lines) - 1)

    def pull_calendar(self):
        data = fetch_json("https://nfs.faireconomy.media/ff_calendar_thisweek.json")
        rows = []
        for e in data:
            ts = parse_date(e.get("date"))
            if not ts:
                continue
            rows.append({"time": ts, "cc": e.get("country", ""), "title": e.get("title", ""), "impact": e.get("impact", ""),
                         "forecast": e.get("forecast", ""), "previous": e.get("previous", ""), "actual": e.get("actual", "")})
        self.store.kv_set("calendar", rows)
        self.store.health("Economic calendar", "markets", True, len(rows))

    def pull_earnings(self):
        day = datetime.date.today().isoformat()
        d = fetch_json(f"https://api.nasdaq.com/api/calendar/earnings?date={day}",
                       headers={"Accept": "application/json, text/plain, */*", "Origin": "https://www.nasdaq.com",
                                "Referer": "https://www.nasdaq.com/"})
        rows = ((d.get("data") or {}).get("rows")) or []
        def cap(r):
            try:
                return float(re.sub(r"[^0-9.]", "", r.get("marketCap") or "0") or 0)
            except ValueError:
                return 0
        rows.sort(key=cap, reverse=True)
        out = [{"symbol": r.get("symbol"), "name": r.get("name"), "when": "before open" if "pre" in (r.get("time") or "") else
                "after close" if "after" in (r.get("time") or "") else "during the day",
                "eps": r.get("epsForecast") or "", "cap": r.get("marketCap") or ""} for r in rows[:10]]
        self.store.kv_set("earnings", {"date": day, "rows": out})
        self.store.health("Nasdaq earnings calendar", "markets", True, len(rows))

    def pull_polymarket(self):
        d = fetch_json("https://gamma-api.polymarket.com/markets?active=true&closed=false&limit=400"
                       "&order=volume24hr&ascending=false")
        kws = [k.lower() for k in self.sources.get("polymarket_keywords", [])]
        out = []
        for m in d if isinstance(d, list) else d.get("data", []):
            qn = m.get("question") or ""
            if not any(k in qn.lower() for k in kws):
                continue
            try:
                prices = json.loads(m.get("outcomePrices") or "[]")
                outs = json.loads(m.get("outcomes") or "[]")
                yes = float(prices[outs.index("Yes")]) if "Yes" in outs else float(prices[0])
            except (ValueError, IndexError, TypeError):
                continue
            out.append({"q": qn, "yes": round(yes * 100), "vol": m.get("volume24hr") or 0, "slug": m.get("slug")})
            if len(out) >= 8:
                break
        self.store.kv_set("predictions", out)
        self.store.health("Polymarket odds", "markets", True, len(out))

    def pull_front(self):
        """Front line / control areas from DeepState's public map, if it answers."""
        try:
            d = fetch_json("https://deepstatemap.live/api/history/last", timeout=40)
        except FetchError as e:
            self.store.health("DeepState front line", "conflict", False, 0, str(e))
            return
        fc = d.get("map") if isinstance(d, dict) and "map" in d else d
        feats = (fc or {}).get("features", []) if isinstance(fc, dict) else []
        keep = []
        for f in feats:
            g = f.get("geometry") or {}
            if g.get("type") not in ("Polygon", "MultiPolygon"):
                continue
            col = str((f.get("properties") or {}).get("fill", "")).lower()
            if col and not re.match(r"#(a|b|c|d|e|f|9|8)[0-9a-f]{1}[0-4][0-9a-f]", col):
                continue            # keep the red-ish (occupied) areas
            keep.append({"type": "Feature", "geometry": g, "properties": {}})
        if keep:
            self.store.kv_set("front", {"type": "FeatureCollection", "features": keep, "date": d.get("datetime") or d.get("date")})
        self.store.health("DeepState front line", "conflict", bool(keep), len(keep), "" if keep else "no areas in reply")

    # ---------- ships through chokepoints (IMF PortWatch) ----------
    def pull_portwatch(self):
        """Daily ship counts per chokepoint from IMF PortWatch (public ArcGIS service)."""
        base = ("https://services9.arcgis.com/weJ1QsnbMYJlCHdG/arcgis/rest/services/Daily_Chokepoints_Data/"
                "FeatureServer/0/query")
        since = (datetime.date.today() - datetime.timedelta(days=380)).isoformat()
        rows, offset = [], 0
        while offset < 40000:
            q = urllib.parse.urlencode({"where": f"date >= DATE '{since}'", "outFields": "portname,date,n_total,n_tanker,"
                                        "n_container,n_dry_bulk,n_general_cargo,n_roro", "orderByFields": "date",
                                        "resultOffset": offset, "resultRecordCount": 2000, "f": "json"})
            d = fetch_json(base + "?" + q, timeout=60)
            feats = d.get("features") or []
            rows += [f.get("attributes", {}) for f in feats]
            if not d.get("exceededTransferLimit") or not feats:
                break
            offset += len(feats)
        if not rows:
            raise FetchError("no rows (the service may have moved)")
        out = {}
        for a in rows:
            name = a.get("portname")
            if not name:
                continue
            day = a.get("date")
            if isinstance(day, (int, float)):
                day = datetime.datetime.utcfromtimestamp(day / 1000).date().isoformat()
            o = out.setdefault(name, {"days": [], "mix": [0, 0, 0, 0, 0]})
            o["days"].append([str(day)[:10], a.get("n_total") or 0])
        for name, o in out.items():
            o["days"].sort()
            recent = [a for a in rows if a.get("portname") == name][-30:]
            for a in recent:
                for i, k in enumerate(("n_tanker", "n_container", "n_dry_bulk", "n_general_cargo", "n_roro")):
                    o["mix"][i] += a.get(k) or 0
            v = [n for _, n in o["days"]]
            wk = sum(v[-7:]) / max(1, len(v[-7:]))
            yr = sum(v[:-30]) / max(1, len(v[:-30])) if len(v) > 60 else wk
            o["week_avg"], o["year_avg"] = round(wk, 1), round(yr, 1)
            ratio = wk / yr if yr else 1
            o["status"] = "disrupted" if ratio < 0.6 else "reduced" if ratio < 0.85 else "busier than usual" if ratio > 1.25 else "normal"
            o["days"] = o["days"][-365:]
        self.store.kv_set("ships", out)
        self.store.health("IMF PortWatch (ships through chokepoints)", "trade", True, len(out))

    # ---------- morning note ----------
    def maybe_write_note(self, force=False):
        today = datetime.date.today().isoformat()
        note = self.store.kv_get("note") or {}
        hour = datetime.datetime.now().hour
        if not force and (note.get("date") == today or hour < 6):
            return
        quotes = self.store.kv_get("quotes", {})
        if len(quotes) < 8:
            return
        lines = []
        for label, sym, grp, dec, unit in MARKETS:
            q = quotes.get(sym)
            if q:
                lines.append(f"{label}: {q['price']:.{dec}f} ({q['chg']:+.2f}%)")
        curve = self.store.kv_get("curve") or {}
        if curve.get("now"):
            for t, v, p in zip(curve["t"], curve["now"], curve.get("prev") or []):
                if v is not None and p is not None and t in ("2Y", "10Y", "30Y"):
                    lines.append(f"US {t} yield: {v:.2f}% ({(v - p) * 100:+.0f} bp)")
        cal = [c for c in (self.store.kv_get("calendar") or []) if
               datetime.date.fromtimestamp(c["time"]).isoformat() == today and c["impact"] in ("High", "Medium")]
        heads = [r["title"] for r in self.store.q(
            "SELECT title FROM clusters WHERE last > ? AND kind='story' ORDER BY n_sources DESC LIMIT 12", (now() - 86400,))]
        try:
            from archie_brain import quick_chat
            out = quick_chat(self.get_model(), NOTE_PROMPT.format(
                numbers="\n".join(lines),
                calendar="\n".join(f"{datetime.datetime.fromtimestamp(c['time']).strftime('%H:%M')} {c['cc']} {c['title']} "
                                   f"(expected {c['forecast'] or '?'}, last {c['previous'] or '?'})" for c in cal) or "nothing major",
                headlines="\n".join(heads) or "none"), max_tokens=600, timeout=180, json_mode=True, temperature=0.3)
            d = json.loads(out)
        except Exception as e:
            self.store.health("Morning note writer", "markets", False, 0, str(e))
            return
        d["date"] = today
        d["written"] = now()
        self.store.kv_set("note", d)
        self.store.health("Morning note writer", "markets", True, 1)

    # ---------- GDELT (news in 100+ languages, found by event keywords) ----------
    GDELT_LANG = {"English": "en", "Ukrainian": "uk", "Russian": "ru", "Arabic": "ar", "Persian": "fa", "Hebrew": "he",
                  "German": "de", "French": "fr", "Spanish": "es", "Turkish": "tr", "Chinese": "zh"}

    def pull_gdelt(self):
        for i, g in enumerate(self.sources.get("gdelt", [])):
            if self.stop.is_set():
                return
            if i:
                time.sleep(6)                  # GDELT asks for one request every 5 seconds
            q = urllib.parse.quote(g["q"])
            url = (f"https://api.gdeltproject.org/api/v2/doc/doc?query={q}&mode=artlist&maxrecords=75"
                   f"&format=json&timespan=6h&sort=datedesc")
            name = "GDELT: " + (REGION_NAMES.get(g.get("region")) or "world conflict")
            try:
                d = fetch_json(url, timeout=40)
                arts = d.get("articles") or []
                by_lang = {}
                for a in arts:
                    lang = self.GDELT_LANG.get(a.get("language", ""), "")
                    if not lang:
                        continue
                    if lang != "en" and by_lang.get(lang, 0) >= 4:      # keep the translating light
                        continue
                    by_lang[lang] = by_lang.get(lang, 0) + 1
                    dom = (a.get("domain") or "").lower()
                    try:
                        pub = int(datetime.datetime.strptime(a.get("seendate", ""), "%Y%m%dT%H%M%SZ")
                                  .replace(tzinfo=datetime.timezone.utc).timestamp())
                    except ValueError:
                        pub = None
                    entry = {"title": (a.get("title") or "").strip(), "url": a.get("url"), "summary": "", "published": pub,
                             "source": dom}
                    if entry["title"]:
                        self._add_items("gdelt", dom or "GDELT", [entry], lang, a.get("sourcecountry") or "", "", g.get("region"))
                self.store.health(name, "gdelt", True, len(arts))
            except (FetchError, Exception) as e:
                self.store.health(name, "gdelt", False, 0, str(e))

    # ---------- ACLED (checked conflict data; optional account) ----------
    ACLED_TYPE = {"Battles": "clash", "Violence against civilians": "clash", "Protests": "protest", "Riots": "protest",
                  "Strategic developments": "politics"}
    ACLED_SUB = {"Air/drone strike": "drone", "Shelling/artillery/missile attack": "shelling",
                 "Remote explosive/landmine/IED": "blast", "Suicide bomb": "blast", "Grenade": "blast"}

    def pull_acled(self):
        email, pw = (self.sources.get("acled_email") or "").strip(), (self.sources.get("acled_password") or "").strip()
        if not email or not pw:
            return
        try:
            tok = json.loads(fetch("https://acleddata.com/oauth/token", timeout=40, data=urllib.parse.urlencode(
                {"username": email, "password": pw, "grant_type": "password", "client_id": "acled"}).encode(),
                headers={"Content-Type": "application/x-www-form-urlencoded"}))
            token = tok.get("access_token")
            if not token:
                raise FetchError("login refused (check the email and password in sources.json)")
            d1 = (datetime.date.today() - datetime.timedelta(days=30)).isoformat()
            d2 = datetime.date.today().isoformat()
            q = urllib.parse.urlencode({"_format": "json", "event_date": f"{d1}|{d2}", "event_date_where": "BETWEEN",
                                        "limit": 4000, "fields": "event_id_cnty|event_date|event_type|sub_event_type|actor1|"
                                        "actor2|country|admin1|location|latitude|longitude|notes|source|fatalities|iso"})
            d = fetch_json("https://acleddata.com/api/acled/read?" + q, timeout=90,
                           headers={"Authorization": "Bearer " + token})
            rows = d.get("data") or []
            added = []
            for r in rows:
                try:
                    lat, lng = float(r["latitude"]), float(r["longitude"])
                except (KeyError, ValueError, TypeError):
                    continue
                et = self.ACLED_SUB.get(r.get("sub_event_type")) or self.ACLED_TYPE.get(r.get("event_type"), "clash")
                who = " vs ".join(x for x in (r.get("actor1"), r.get("actor2")) if x)
                title = f"{r.get('sub_event_type') or r.get('event_type')} near {r.get('location')}, {r.get('admin1')}" + \
                        (f" ({who})" if who else "") + (f", {r['fatalities']} killed" if str(r.get("fatalities", "0")) not in ("0", "") else "")
                pub = parse_date((r.get("event_date") or "") + "T12:00:00") or now()
                iid = item_id("acled", r.get("event_id_cnty"))
                added.append((iid, "ACLED", "acled", "en", "checked dataset", "", title, title, (r.get("notes") or "")[:600],
                              "https://acleddata.com", "", pub, now(), lat, lng, r.get("location"), None,
                              region_of(lat, lng), et, topic_for(title, et), None, 0))
            self.store.many("INSERT OR IGNORE INTO items(id, source, feed, lang, side, lean, title, title_en, summary, url, "
                            "author, published, fetched, lat, lng, place, cc, region, etype, topic, cluster, needs_ai) "
                            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", added)
            note = "" if rows else "no rows came back (a free account may only see older data)"
            self.store.health("ACLED (checked conflict data)", "conflict", bool(rows), len(rows), note)
        except (FetchError, Exception) as e:
            self.store.health("ACLED (checked conflict data)", "conflict", False, 0, str(e))

    # ---------- background explainers (offline Wikipedia first) ----------
    EXTRACT_PROMPT = """From this news item, list the 1 to 4 things a reader most needs background on to understand it:
armed groups, organizations, people, places, companies, stock indexes, laws or ideas. Use their full proper names.
Reply ONLY with JSON: {{"things": [{{"name": "...", "kind": "armed group|organization|person|place|company|index|concept|event"}}]}}

Item: {text}"""
    EXPLAIN_PROMPT = """Explain the background of this item in plain words for a smart reader who hasn't been following it.
Use ONLY the reference text (from Wikipedia) and the item itself. 4 to 6 short sentences: who or what the key players are,
how it got here, and what's at stake now. If the reference doesn't cover something, say that instead of guessing.
Reply ONLY with JSON: {{"background": "...", "why": "one sentence on why it matters now"}}

Item: {item}

Reference:
{refs}"""

    def _wiki_lookup(self, name):
        """(title, text, source, url) from the offline Wikipedia, or online Wikipedia as a backup."""
        if self.wiki is not None:
            try:
                if self.wiki.zim_files():
                    res = self.wiki.search(name, k=1, chars_per_article=1400)
                    if res:
                        title, text = res[0]
                        if tokens(name) & tokens(title) or name.lower() in text.lower()[:600]:
                            return title, text, "offline Wikipedia", ""
            except Exception:
                pass
        if not self.is_online:
            return None
        try:
            d = fetch_json("https://en.wikipedia.org/w/rest.php/v1/search/title?q=" + urllib.parse.quote(name) + "&limit=1",
                           timeout=15)
            pages = d.get("pages") or []
            if not pages:
                return None
            key = pages[0]["key"]
            sm = fetch_json("https://en.wikipedia.org/api/rest_v1/page/summary/" + urllib.parse.quote(key), timeout=15)
            return (sm.get("title") or key, sm.get("extract") or "", "Wikipedia (online)",
                    ((sm.get("content_urls") or {}).get("desktop") or {}).get("page", ""))
        except (FetchError, Exception):
            return None

    def explain(self, payload):
        text = (payload.get("text") or "").strip()[:1500]
        names = [n for n in (payload.get("names") or []) if n][:4]
        key = "explain:" + item_id(text, "|".join(names))
        cached = self.store.kv_get(key)
        if cached and self.store.kv_age(key) < 3 * 86400:
            return cached
        try:
            from archie_brain import quick_chat
        except Exception as e:
            return {"error": str(e)}
        things = [{"name": n, "kind": payload.get("kind") or ""} for n in names]
        if not things:
            try:
                d = json.loads(quick_chat(self.ai_model(), self.EXTRACT_PROMPT.format(text=text), max_tokens=200,
                                          timeout=90, json_mode=True, temperature=0.1))
                things = [t for t in (d.get("things") or []) if isinstance(t, dict) and t.get("name")][:4]
            except Exception:
                things = []
        refs, found = [], []
        for t in things:
            hit = self._wiki_lookup(t["name"])
            if hit:
                title, body, src, url = hit
                found.append({"name": t["name"], "kind": t.get("kind", ""), "title": title,
                              "summary": re.sub(r"\s+", " ", body)[:520], "source": src, "url": url})
                refs.append(f"## {title}\n{body[:1400]}")
            else:
                found.append({"name": t["name"], "kind": t.get("kind", ""), "title": "", "summary": "", "source": "", "url": ""})
        out = {"things": found, "background": "", "why": ""}
        if refs or text:
            try:
                d = json.loads(quick_chat(self.get_model(), self.EXPLAIN_PROMPT.format(item=text or ", ".join(names),
                                          refs="\n\n".join(refs) or "(nothing found)"), max_tokens=450, timeout=150,
                                          json_mode=True, temperature=0.3))
                out["background"], out["why"] = d.get("background", ""), d.get("why", "")
            except Exception as e:
                out["background"] = f"(Couldn't reach the model: {e})"
        self.store.kv_set(key, out)
        return out

    # ---------- the world calendar ----------
    FOMC_2026 = ["2026-01-28", "2026-03-18", "2026-04-29", "2026-06-17", "2026-07-29", "2026-09-16", "2026-10-28", "2026-12-09"]
    CB_WORDS = re.compile(r"FOMC|Federal Funds|Cash Rate|Official Bank Rate|Main Refinancing|Policy Rate|Overnight Rate|"
                          r"Interest Rate Decision|Monetary Policy Statement|Rate Statement|SNB Policy", re.I)
    CC_OF_CCY = {"USD": ("US", "Federal Reserve"), "EUR": ("EU", "European Central Bank"), "GBP": ("GB", "Bank of England"),
                 "JPY": ("JP", "Bank of Japan"), "CAD": ("CA", "Bank of Canada"), "AUD": ("AU", "Reserve Bank of Australia"),
                 "NZD": ("NZ", "Reserve Bank of New Zealand"), "CHF": ("CH", "Swiss National Bank"), "CNY": ("CN", "People's Bank of China")}
    BANK_AT = {"US": (38.893, -77.046), "EU": (50.109, 8.703), "GB": (51.514, -0.088), "JP": (35.686, 139.771), "CA": (45.42, -75.7),
               "AU": (-33.87, 151.21), "NZ": (-41.28, 174.78), "CH": (46.947, 7.444), "CN": (39.91, 116.36)}

    def pull_world_calendar(self):
        items, errs = [], []
        today = datetime.date.today()
        horizon = today + datetime.timedelta(days=60)
        # central banks + big economic releases (this week and next)
        for which in ("thisweek", "nextweek"):
            try:
                for e in fetch_json(f"https://nfs.faireconomy.media/ff_calendar_{which}.json", timeout=30):
                    ts = parse_date(e.get("date"))
                    if not ts or e.get("impact") != "High":
                        continue
                    ccy = e.get("country", "")
                    cc, bank = self.CC_OF_CCY.get(ccy, ("", ""))
                    is_cb = bool(self.CB_WORDS.search(e.get("title", "")))
                    at = self.BANK_AT.get(cc)
                    items.append({"date": datetime.date.fromtimestamp(ts).isoformat(), "time": ts, "kind": "central bank" if is_cb else "economy",
                                  "title": (bank + ": " if is_cb and bank else ccy + " ") + e.get("title", ""),
                                  "where": bank if is_cb and bank else (self.geo.country_name(cc) if cc and cc != "EU" else "Eurozone" if cc == "EU" else ccy),
                                  "cc": cc, "lat": at[0] if at else None, "lng": at[1] if at else None,
                                  "detail": f"expected {e.get('forecast') or '?'}, last {e.get('previous') or '?'}", "source": "Forex Factory"})
                if which == "thisweek":
                    time.sleep(2)
            except (FetchError, Exception) as e:
                errs.append(f"calendar {which}: {e}")
        have_fed = {i["date"] for i in items if "Federal Reserve" in i["title"]}
        for d in self.FOMC_2026:
            dd = datetime.date.fromisoformat(d)
            if today <= dd <= horizon and d not in have_fed:
                items.append({"date": d, "time": None, "kind": "central bank", "title": "Federal Reserve: rate decision (FOMC)",
                              "where": "Federal Reserve", "cc": "US", "lat": 38.893, "lng": -77.046,
                              "detail": "from the Fed's published 2026 schedule", "source": "federalreserve.gov"})
        # elections (Wikidata)
        try:
            q = ("SELECT ?e ?eLabel ?date ?countryLabel ?cc ?coord WHERE { ?e wdt:P31/wdt:P279* wd:Q40231; wdt:P585 ?date. "
                 f'FILTER(?date >= "{today.isoformat()}T00:00:00Z"^^xsd:dateTime && ?date < "{horizon.isoformat()}T00:00:00Z"^^xsd:dateTime) '
                 "?e wdt:P17 ?country. OPTIONAL { ?country wdt:P297 ?cc. } OPTIONAL { ?country wdt:P625 ?coord. } "
                 'SERVICE wikibase:label { bd:serviceParam wikibase:language "en". } } LIMIT 400')
            d = fetch_json("https://query.wikidata.org/sparql?format=json&query=" + urllib.parse.quote(q), timeout=70,
                           headers={"Accept": "application/sparql-results+json", "User-Agent": TILE_UA})
            per = {}
            for b in d.get("results", {}).get("bindings", []):
                label = b.get("eLabel", {}).get("value", "")
                if re.search(r"municipal|local|mayor|county|city council|school|primary|caucus|by-election|referendum on",
                             label, re.I) or re.match(r"^Q\d+$", label):
                    continue
                country = b.get("countryLabel", {}).get("value", "")
                if per.get(country, 0) >= 3:
                    continue
                per[country] = per.get(country, 0) + 1
                lat = lng = None
                m = re.match(r"Point\(([-\d.]+) ([-\d.]+)\)", b.get("coord", {}).get("value", ""))
                if m:
                    lng, lat = float(m.group(1)), float(m.group(2))
                items.append({"date": b["date"]["value"][:10], "time": None, "kind": "election", "title": label, "where": country,
                              "cc": b.get("cc", {}).get("value", ""), "lat": lat, "lng": lng, "detail": "",
                              "source": "Wikidata", "url": b["e"]["value"]})
        except (FetchError, Exception) as e:
            errs.append(f"elections: {e}")
        # rocket launches (The Space Devs)
        try:
            d = fetch_json("https://ll.thespacedevs.com/2.2.0/launch/upcoming/?limit=25&mode=list", timeout=40)
            for l in d.get("results", []):
                ts = parse_date(l.get("net"))
                if not ts:
                    continue
                pad = l.get("pad") or {}
                loc = pad.get("location", {}).get("name") if isinstance(pad.get("location"), dict) else l.get("location", "")
                items.append({"date": datetime.date.fromtimestamp(ts).isoformat(), "time": ts, "kind": "launch",
                              "title": l.get("name", "Launch"), "where": loc or "", "cc": "",
                              "lat": float(pad["latitude"]) if pad.get("latitude") else None,
                              "lng": float(pad["longitude"]) if pad.get("longitude") else None,
                              "detail": (l.get("status") or {}).get("name", "") if isinstance(l.get("status"), dict) else "",
                              "source": "The Space Devs"})
        except (FetchError, Exception) as e:
            errs.append(f"launches: {e}")
        # big earnings, next 7 days
        for i in range(0, 8):
            day = today + datetime.timedelta(days=i)
            if day.weekday() >= 5:
                continue
            try:
                d = fetch_json(f"https://api.nasdaq.com/api/calendar/earnings?date={day.isoformat()}", timeout=30,
                               headers={"Accept": "application/json, text/plain, */*", "Origin": "https://www.nasdaq.com",
                                        "Referer": "https://www.nasdaq.com/"})
                rows = ((d.get("data") or {}).get("rows")) or []
                def cap(r):
                    try:
                        return float(re.sub(r"[^0-9.]", "", r.get("marketCap") or "0") or 0)
                    except ValueError:
                        return 0
                for r in sorted(rows, key=cap, reverse=True)[:4]:
                    if cap(r) < 50e9:
                        continue
                    items.append({"date": day.isoformat(), "time": None, "kind": "earnings", "title": f"{r.get('name')} earnings",
                                  "where": r.get("symbol", ""), "cc": "US", "lat": None, "lng": None,
                                  "detail": ("before the open" if "pre" in (r.get("time") or "") else "after the close" if "after" in (r.get("time") or "") else "")
                                  + (f" · EPS est. {r.get('epsForecast')}" if r.get("epsForecast") else ""), "source": "Nasdaq"})
                time.sleep(1)
            except (FetchError, Exception):
                continue
        seen, uniq = set(), []
        for i in items:
            k = (i["date"], i["title"].lower())
            if k not in seen:
                seen.add(k)
                uniq.append(i)
        items = [i for i in uniq if today.isoformat() <= i["date"] <= horizon.isoformat()]
        items.sort(key=lambda i: (i["date"], i["time"] or 0))
        for i in items:
            i["id"] = item_id(i["date"], i["title"])
        if items:
            self.store.kv_set("worldcal", items)
        self.store.health("World calendar", "calendar", bool(items), len(items), "; ".join(errs)[:200])

    def world_calendar(self):
        return {"items": self.store.kv_get("worldcal", []), "can_add": bool(self.add_calendar)}

    def calendar_add(self, it):
        if not self.add_calendar:
            return {"ok": False, "error": "Archie's calendar isn't connected"}
        try:
            when = datetime.date.fromisoformat(it["date"])
            tm = datetime.datetime.fromtimestamp(it["time"]).strftime("%H:%M") if it.get("time") else None
            self.add_calendar(it["title"][:120], when, tm, (it.get("detail") or "") + (" · " + it["where"] if it.get("where") else ""))
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ---------- weekly world review (Obsidian) ----------
    def _week_key(self, d):
        y, w, _ = d.isocalendar()
        return f"{y}-W{w:02d}"

    def _week_bounds(self, monday):
        t0 = int(datetime.datetime.combine(monday, datetime.time()).timestamp())
        return t0, t0 + 7 * 86400

    def _save_week_stats(self, monday):
        wk = self._week_key(monday)
        t0, t1 = self._week_bounds(monday)
        self.store.x("CREATE TABLE IF NOT EXISTS weekly(week TEXT, region TEXT, military INTEGER, events INTEGER, stories INTEGER, "
                     "PRIMARY KEY(week, region))")
        rows = []
        for reg in list(REGIONS) + ["world"]:
            cond = "" if reg == "world" else " AND region=?"
            args = (t0, t1) + (() if reg == "world" else (reg,))
            mil = self.store.q("SELECT COUNT(*) n FROM clusters WHERE last BETWEEN ? AND ? AND kind='event' AND etype IN "
                               "('clash','shelling','drone','missile','blast')" + cond, args, one=True)["n"]
            ev = self.store.q("SELECT COUNT(*) n FROM clusters WHERE last BETWEEN ? AND ? AND kind='event'" + cond, args, one=True)["n"]
            st = self.store.q("SELECT COUNT(*) n FROM clusters WHERE last BETWEEN ? AND ? AND kind='story'" + cond, args, one=True)["n"]
            rows.append((wk, reg, mil, ev, st))
        self.store.many("INSERT OR REPLACE INTO weekly(week, region, military, events, stories) VALUES(?,?,?,?,?)", rows)

    def maybe_weekly(self, force=False):
        """Sunday evening: write last week's review. Catches up on Monday if the PC was off."""
        today = datetime.date.today()
        this_monday = today - datetime.timedelta(days=today.weekday())
        if force or (today.weekday() == 6 and datetime.datetime.now().hour >= 20):
            monday = this_monday          # asked for it (or Sunday night): the week so far
        else:
            monday = this_monday - datetime.timedelta(days=7)
        wk = self._week_key(monday)
        if not force and self.store.kv_get("weekly_last") == wk:
            return None
        if not force and not self.store.q("SELECT 1 FROM clusters WHERE last BETWEEN ? AND ? LIMIT 1", self._week_bounds(monday), one=True):
            return None
        path = self.write_weekly(monday)
        if path:
            self.store.kv_set("weekly_last", wk)
        return path

    @staticmethod
    def _names(title):
        """Capitalized names in a headline (people, places, groups): the things stories are about."""
        skip = {"The", "A", "An", "In", "On", "At", "For", "And", "But", "With", "After", "Before", "As", "Says", "Why", "How",
                "What", "New", "Top", "More", "Over", "Amid", "Into", "From", "Of", "To", "By", "Is", "Are", "Was", "Will", "Can"}
        out, cur = [], []
        for w in re.findall(r"[A-Za-z][\w'’\-]*", title or ""):
            if w[0].isupper() and w not in skip and not w.isupper():
                cur.append(w)
            else:
                if cur:
                    out.append(" ".join(cur))
                cur = []
        if cur:
            out.append(" ".join(cur))
        if out and title and title.startswith(out[0]) and " " not in out[0] and out[0].lower().endswith(("ing", "ed", "s")) \
                and not out[0].endswith("ians"):
            out = out[1:]                 # a headline's first word is capitalized anyway ("Fighting near...")
        return [n for n in out if len(n) > 3]

    def write_weekly(self, monday):
        vault = self.vault()
        if not vault:
            return None
        wk = self._week_key(monday)
        t0, t1 = self._week_bounds(monday)
        for back in range(0, 9):              # make sure this week and the ones before have their numbers
            self._save_week_stats(monday - datetime.timedelta(days=7 * back))
        first = self.store.q("SELECT MIN(first) f FROM clusters", one=True)["f"] or t0
        first_monday = datetime.date.fromtimestamp(first)
        first_monday -= datetime.timedelta(days=first_monday.weekday())
        weeks = [self._week_key(monday - datetime.timedelta(days=7 * b)) for b in range(7, -1, -1)
                 if monday - datetime.timedelta(days=7 * b) >= first_monday]      # no zeros for weeks before Archie was watching
        stats = {}
        for r in self.store.q(f"SELECT * FROM weekly WHERE week IN ({','.join('?' * len(weeks))})", weeks):
            stats[(r["week"], r["region"])] = r["military"]
        folder = os.path.join(vault, "Archie", "World", "Weekly")
        os.makedirs(folder, exist_ok=True)
        chart = os.path.join(folder, f"{wk} fighting.png")
        regions = [r for r in REGIONS if r not in ("usa", "germany")]
        has_chart = len(weeks) >= 2
        if has_chart:
            self._weekly_chart(chart, weeks, regions, stats)
        # biggest stories, rising and fading names
        stories = self.store.q("SELECT * FROM clusters WHERE kind='story' AND last BETWEEN ? AND ? ORDER BY n_sources DESC LIMIT 60", (t0, t1))
        prev = self.store.q("SELECT title, n_sources FROM clusters WHERE last BETWEEN ? AND ?", (t0 - 7 * 86400, t0))
        cur_n, prev_n = {}, {}
        for c in self.store.q("SELECT title, n_sources FROM clusters WHERE last BETWEEN ? AND ?", (t0, t1)):
            for n in set(self._names(c["title"])):
                cur_n[n] = cur_n.get(n, 0) + c["n_sources"]
        for c in prev:
            for n in set(self._names(c["title"])):
                prev_n[n] = prev_n.get(n, 0) + c["n_sources"]
        rising = sorted([(n, v, prev_n.get(n, 0)) for n, v in cur_n.items() if v >= 4 and v >= 2 * max(1, prev_n.get(n, 0))],
                        key=lambda x: -(x[1] - x[2]))[:8]
        fading = sorted([(n, v, cur_n.get(n, 0)) for n, v in prev_n.items() if v >= 6 and cur_n.get(n, 0) * 2 <= v],
                        key=lambda x: -(x[1] - x[2]))[:6]
        seen, top = set(), []
        for c in stories:
            k = frozenset(tokens(c["title"]))
            if any(len(k & s) >= max(2, len(k) // 2) for s in seen):
                continue
            seen.add(k)
            top.append(c)
            if len(top) >= 10:
                break
        take = ""
        try:
            from archie_brain import quick_chat
            d = json.loads(quick_chat(self.get_model(),
                           "Write a plain, neutral 4-sentence summary of this week in world news, using ONLY these headlines "
                           "(with how many outlets covered each). Reply ONLY with JSON: {\"summary\": \"...\"}\n\n" +
                           "\n".join(f"- {c['title']} ({c['n_sources']})" for c in top), max_tokens=350, timeout=150,
                           json_mode=True, temperature=0.3))
            take = d.get("summary", "")
        except Exception:
            pass
        sun = monday + datetime.timedelta(days=6)
        out = ["---", f"week: {wk}", "tags: [archie-world, weekly-review]", "---", "",
               f"# World · week of {monday:%B %d} to {sun:%B %d, %Y}", ""]
        if take:
            out += ["## The week", take, ""]
        out += ["## Fighting by region", "Military reports (clashes, shelling, drones, missiles, explosions) per week, from the stored reports.", "",
                (f"![[{os.path.basename(chart)}]]" if has_chart else "*The trend chart starts once there are two weeks of reports.*"), "",
                "| region | this week | last week | 4-week average | |", "|---|---:|---:|---:|---|"]
        for reg in regions + ["world"]:
            now_v = stats.get((weeks[-1], reg), 0)
            last_v = stats.get((weeks[-2], reg), 0) if len(weeks) >= 2 else 0
            prior = weeks[-5:-1]
            avg = sum(stats.get((w, reg), 0) for w in prior) / len(prior) if prior else 0
            arrow = "▲ up" if now_v > max(last_v, avg) * 1.25 and now_v >= 5 else "▼ down" if now_v < min(last_v, avg) * 0.75 else "steady"
            out.append(f"| {REGION_NAMES.get(reg, 'All regions')} | {now_v} | {last_v} | {avg:.0f} | {arrow} |")
        out.append("")
        if top:
            out += ["## Biggest stories"] + [f"- {c['title']} · {c['n_sources']} outlet{'s' if c['n_sources'] != 1 else ''} · [open on globe](archie://world#story={c['id']})"
                                             for c in top] + [""]
        if prev and (rising or fading):          # only once there's a week before to compare with
            out.append("## Growing and fading")
            if rising:
                out.append("**In the news more than last week:** " + ", ".join(f"{n} ({p}→{v})" for n, v, p in rising))
            if fading:
                out.append("**Fading:** " + ", ".join(f"{n} ({v}→{c})" for n, v, c in fading))
            out.append("*Numbers are how many outlet reports mentioned the name.*")
            out.append("")
        follow = self.watch.get("follow", [])
        if follow:
            week_stories = [{"t": c["title"], "summary": ""} for c in self.store.q(
                "SELECT title FROM clusters WHERE last BETWEEN ? AND ?", (t0, t1))]
            out += ["## Topics you follow"] + [f"- **{t}**: {sum(1 for s in week_stories if self._matches(s, [t]))} stories" for t in follow] + [""]
        quotes = self.store.kv_get("quotes", {})
        mv = [(lab, quotes[sym]["w1"]) for lab, sym, grp, *_ in MARKETS if sym in quotes and quotes[sym].get("w1") is not None
              and grp not in ("Sectors",)]
        if mv:
            mv.sort(key=lambda x: -abs(x[1]))
            out += ["## Markets this week"] + [f"- {lab} {'▲' if v >= 0 else '▼'} {abs(v):.1f}%" for lab, v in mv[:10]] + [""]
        hz = self.store.q("SELECT * FROM hazards WHERE time BETWEEN ? AND ? AND ((kind='quake' AND mag >= 6) OR level IN ('orange','red'))"
                          " ORDER BY COALESCE(mag,0) DESC LIMIT 8", (t0, t1))
        if hz:
            out += ["## Disasters"] + [f"- {h['title']}" for h in hz] + [""]
        days = [(monday + datetime.timedelta(days=i)).isoformat() for i in range(7)]
        out += ["## Daily digests", " · ".join(f"[[{d}]]" for d in days), ""]
        saved = [s for s in self.saved_list() if t0 <= s["time"] < t1]
        if saved:
            out += ["## Saved this week"] + [f"- {s['name']}" for s in saved] + [""]
        quizzes = [q for q in self.store.kv_get("quiz_scores", []) if t0 <= q["t"] < t1 and q.get("total")]
        if quizzes:
            got, tot = sum(q["score"] for q in quizzes), sum(q["total"] for q in quizzes)
            out += ["## News quizzes", f"{len(quizzes)} {'quiz' if len(quizzes) == 1 else 'quizzes'} this week: "
                    f"{got} of {tot} right ({round(got / tot * 100)}%). Best: "
                    f"{max(quizzes, key=lambda q: q['score'] / q['total'])['score']}/{max(quizzes, key=lambda q: q['score'] / q['total'])['total']}.", ""]
        lessons_dir = os.path.join(vault, "Archie", "World", "Lessons")
        if os.path.isdir(lessons_dir):
            ls = sorted(f[:-3] for f in os.listdir(lessons_dir) if f.endswith(".md") and monday.isoformat() <= f[:10] <= days[-1])
            if ls:
                out += ["## Lessons you saved"] + [f"- [[{n}]]" for n in ls] + [""]
        path = os.path.join(folder, f"{wk}.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(out))
        return path

    def _weekly_chart(self, path, weeks, regions, stats):
        colors = {"ukraine": "#60a5fa", "sudan": "#f5a524", "mideast": "#ff6b5e", "iran": "#c084fc", "world": "#c6f432"}
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            fig, ax = plt.subplots(figsize=(8, 3.4), dpi=130)
            fig.patch.set_facecolor("#0a0a0a")
            ax.set_facecolor("#0a0a0a")
            ends = []
            for reg in regions:
                ys = [stats.get((w, reg), 0) for w in weeks]
                ax.plot(range(len(weeks)), ys, color=colors.get(reg, "#e8e8e3"), linewidth=2, marker="o", markersize=3)
                ends.append([ys[-1], reg])
            top = max([stats.get((w, r), 0) for w in weeks for r in regions] + [1])
            gap = top * 0.09                                  # keep end labels from sitting on top of each other
            ends.sort()
            for i in range(1, len(ends)):
                ends[i][0] = max(ends[i][0], ends[i - 1][0] + gap)
            for y, reg in ends:
                ax.annotate(REGION_NAMES.get(reg, reg), (len(weeks) - 1, y), textcoords="offset points", xytext=(8, -3),
                            color="#c8cac3", fontsize=8)
                ax.plot([len(weeks) - 1 + 0.04], [y], marker="s", markersize=4, color=colors.get(reg, "#e8e8e3"))
            ax.set_xticks(range(len(weeks)))
            ax.set_xticklabels([w.split("-")[1] for w in weeks], color="#8f918a", fontsize=8)
            ax.tick_params(axis="y", colors="#8f918a", labelsize=8)
            for sp in ax.spines.values():
                sp.set_visible(False)
            ax.grid(axis="y", color="#20231d", linewidth=0.8)
            ax.set_title("Military reports per week", color="#e8e8e3", fontsize=10, loc="left")
            ax.set_xlim(-0.3, len(weeks) - 0.3 + 0.75)
            fig.tight_layout()
            fig.savefig(path, facecolor=fig.get_facecolor())
            plt.close(fig)
        except Exception:
            from PIL import Image, ImageDraw
            W, H, m = 1000, 420, 50
            img = Image.new("RGB", (W, H), (10, 10, 10))
            d = ImageDraw.Draw(img)
            top = max([stats.get((w, r), 0) for w in weeks for r in regions] + [1])
            for reg in regions:
                pts = [(m + i * (W - 2 * m - 80) / (len(weeks) - 1), H - m - stats.get((w, reg), 0) / top * (H - 2 * m))
                       for i, w in enumerate(weeks)]
                d.line(pts, fill=colors.get(reg, "#e8e8e3"), width=3)
                d.text((pts[-1][0] + 8, pts[-1][1] - 6), REGION_NAMES.get(reg, reg), fill=colors.get(reg, "#e8e8e3"))
            img.save(path)

    # ---------- catch me up: a story's timeline across days ----------
    THREAD_PROMPT = """These are dated reports about one developing story, oldest first. Using ONLY them, write for someone
who hasn't been following it. Plain, neutral words; if reports conflict, say who claims what.
Reply ONLY with JSON: {{"so_far": "3-4 sentences: how the story developed", "new": "1-2 sentences: what's new in the last 24 hours, or empty if nothing"}}

Reports:
{lines}"""

    def story_thread(self, cid, days=14):
        base = self.store.q("SELECT * FROM clusters WHERE id=?", (cid,), one=True)
        if not base:
            return {"error": "that story isn't stored any more"}
        titles = [r["title_en"] for r in self.store.q("SELECT title_en FROM items WHERE cluster=? AND title_en IS NOT NULL", (cid,))]
        titles = titles or [base["title"]]
        btoks = [tokens(t) for t in titles]
        cands = self.store.q("SELECT * FROM clusters WHERE last > ? ORDER BY last LIMIT 6000", (now() - days * 86400,))
        # how common each word is across these two weeks: shared rare words ("Pokrovsk", "Patriot")
        # count for a lot, shared common ones ("White House", "Ukraine", "says") for very little
        ctoks = {c["id"]: tokens(c["title"]) for c in cands}
        df = {}
        for ts in ctoks.values():
            for w in ts:
                df[w] = df.get(w, 0) + 1
        N = max(1, len(cands))
        idf = lambda w: math.log((N + 1) / (df.get(w, 0) + 1)) + 0.05

        def wj(a, b):
            inter = sum(idf(w) for w in a & b)
            union = sum(idf(w) for w in a | b) or 1
            return inter / union, len(a & b)
        entries = []
        for c in cands:
            if c["id"] == cid:
                score = 9
            else:
                ct = ctoks[c["id"]]
                best = max((wj(ct, b) for b in btoks), key=lambda x: x[0])
                score, shared = best
                if shared < 2:
                    continue
                rare = [w for b in btoks for w in (ct & b) if df.get(w, 0) <= max(3, N * 0.02)]
                if not rare:
                    continue                  # nothing specific in common: probably a different story
                if base["lat"] is not None and c["lat"] is not None and km(base["lat"], base["lng"], c["lat"], c["lng"]) < 150:
                    score += 0.05
            if score >= 0.2:
                entries.append({"id": c["id"], "t": c["title"], "n": c["n_sources"], "first": c["first"], "last": c["last"],
                                "kind": c["kind"], "type": c["etype"] or "news", "place": c["place"], "lat": c["lat"],
                                "lng": c["lng"], "confirmed": bool(c["confirmed"]), "self": c["id"] == cid,
                                "score": round(score, 2)})
        # keep the story focused: if it matched a lot, keep the closest ones
        if len(entries) > 40:
            keep = sorted(entries, key=lambda e: -e["score"])[:40]
            entries = sorted(keep, key=lambda e: e["last"])
        days_seen = sorted({datetime.date.fromtimestamp(e["last"]).isoformat() for e in entries})
        return {"id": cid, "title": base["title"], "entries": entries, "days": days_seen,
                "since": entries[0]["first"] if entries else base["first"]}

    def thread_summary(self, cid):
        th = self.story_thread(cid)
        if th.get("error"):
            return th
        key = "thread:" + cid + ":" + str(len(th["entries"]))
        cached = self.store.kv_get(key)
        if cached:
            return cached
        lines = "\n".join(f"{datetime.datetime.fromtimestamp(e['last']):%a %b %d %H:%M} · {e['n']} source(s) · {e['t']}"
                          for e in th["entries"][-30:])
        try:
            from archie_brain import quick_chat
            d = json.loads(quick_chat(self.get_model(), self.THREAD_PROMPT.format(lines=lines), max_tokens=400, timeout=150,
                                      json_mode=True, temperature=0.3))
            out = {"so_far": d.get("so_far", ""), "new": d.get("new", "")}
        except Exception as e:
            return {"error": f"couldn't reach the model ({e})"}
        self.store.kv_set(key, out)
        return out

    # ---------- the morning news brief ----------
    def _story_rows(self, since, where="", args=()):
        rows = self.store.q("SELECT * FROM clusters WHERE kind='story' AND last > ? " + where +
                            " ORDER BY n_sources DESC, last DESC LIMIT 400", (since,) + tuple(args))
        out = []
        for c in rows:
            its = self.store.q("SELECT source, feed, lean, title, summary, url, author, published, lang FROM items WHERE cluster=? "
                               "ORDER BY published", (c["id"],))
            if not its:
                continue
            srcs, seen = [], set()
            for i in its:
                if i["source"] not in seen:
                    seen.add(i["source"])
                    srcs.append(i)
            summ = ""
            for i in its:
                sm = re.sub(r"\s+", " ", i["summary"] or "").strip()
                if len(sm) > 40 and not sm.startswith((i["title"] or "")[:30]) and i["lang"] == "en":
                    summ = sm[:240] + ("…" if len(sm) > 240 else "")
                    break
            out.append({"id": c["id"], "t": c["title"], "summary": summ, "n": c["n_sources"], "last": c["last"], "first": c["first"],
                        "place": c["place"], "region": c["region"], "cc": c["cc"], "topic": c["topic"],
                        "local": any(i["feed"] == "local" for i in its),
                        "l": sum(1 for i in srcs if i["lean"] == "left"), "c": sum(1 for i in srcs if i["lean"] == "center"),
                        "r": sum(1 for i in srcs if i["lean"] == "right"),
                        "src": [{"name": i["source"], "url": i["url"], "title": i["title"], "author": i["author"],
                                 "time": i["published"], "lang": i["lang"], "feed": i["feed"]} for i in srcs[:8]]})
        return out

    @staticmethod
    def _matches(story, phrase_list):
        text = (story["t"] + " " + story.get("summary", "")).lower()
        for ph in phrase_list:
            for p in [x.strip().lower() for x in ph.split(",") if x.strip()]:
                if re.search(r"(?<![a-z0-9])" + re.escape(p) + r"(?![a-z0-9])", text):
                    return True
        return False

    def news_brief(self):
        try:
            return self._brief_view()
        except Exception as e:
            import traceback
            self.log("news brief failed:", traceback.format_exc())
            return {"error": f"{type(e).__name__}: {e}"}

    # The brief is an edition: written once in the morning (6 am by default) and kept as it was,
    # so it reads like a paper. Big stories that break later are offered as a refresh.
    def _brief_hour(self):
        try:
            return max(0, min(23, int(self.watch.get("brief_hour", 6))))
        except (TypeError, ValueError):
            return 6

    def _edition_day(self):
        n = datetime.datetime.now()
        return (n.date() if n.hour >= self._brief_hour() else n.date() - datetime.timedelta(days=1)).isoformat()

    def _brief_view(self):
        live = self._news_brief()
        ed = self.store.kv_get("news_edition")
        if not ed or not (ed.get("global") or ed.get("home")):
            live["edition"], live["big_new"] = None, []
            return live
        mute = self.watch.get("mute", [])
        out = dict(live)
        for k in ("global", "home", "local"):
            out[k] = [s for s in ed.get(k, []) if not self._matches(s, mute)]
        out["coming"] = ed.get("coming", live["coming"])
        out["take"] = ed.get("take") or {}
        out["edition"] = {"at": ed["at"], "day": ed["day"], "kind": ed.get("kind", "morning"),
                          "take_pending": bool(ed.get("take_pending")), "stale": ed["day"] != self._edition_day(),
                          "hour": self._brief_hour()}
        out["big_new"] = self._big_since(ed)
        return out

    def _big_since(self, ed=None):
        """Stories that got big after the edition was written."""
        ed = ed or self.store.kv_get("news_edition")
        if not ed:
            return []
        full = self._news_brief(cap=False)
        have = [s for k in ("global", "home", "local") for s in ed.get(k, [])]
        try:
            thr = int(self.watch.get("big_story_outlets") or 0)
        except (TypeError, ValueError):
            thr = 0
        if thr <= 0:                             # auto: as big as the biggest story in the edition
            thr = max([3] + [s["n"] for s in ed.get("global", []) + ed.get("home", [])])
        ids = {s["id"] for s in have}
        htoks = [tokens(s["t"]) for s in have]
        out = []
        for sect, lim in (("global", thr), ("home", thr), ("local", max(2, thr // 2))):
            for s in full[sect]:
                if s["id"] in ids or s["n"] < lim or s["last"] <= ed["at"]:
                    continue
                if any(jaccard(tokens(s["t"]), h) >= 0.45 for h in htoks):
                    continue
                out.append(dict(s, section=sect))
        out.sort(key=lambda s: -s["n"])
        return out[:6]

    def big_count(self):
        t, v = self._big_cache
        if time.time() - t > 120:
            try:
                v = self._big_since()
            except Exception:
                v = []
            self._big_cache = (time.time(), v)
        return len(v)

    COMMONWORDS = set("""trump says said after over amid news report reports president world first year years week weeks
                         live latest update updates breaking video watch what know were have with from this that about into
                         their they will would could more than people official officials government state""".split())

    def _one_per_story(self, stories):
        """Different outlets often write up the same event as separate clusters; keep the best-covered one and
        fold the rest into it, so one big story can't fill the whole section."""
        def keys(s):
            out = set()
            for w in re.findall(r"[a-z]{4,}", (s.get("t") or "").lower()):
                if w in STOP or w in self.COMMONWORDS:
                    continue
                out.add(w[:4])
            return out
        kept, out = [], []
        for s in stories:
            k = keys(s)
            dup = None
            for o, ok in kept:
                if len(k & ok) >= 2 or (k and len(k & ok) / max(1, len(k | ok)) >= 0.34):
                    dup = o
                    ok |= k       # the story's vocabulary grows as more write-ups fold in
                    break
            if dup is not None:
                dup["also"] = dup.get("also", 0) + 1
                continue
            kept.append((s, k))
            out.append(s)
        return out

    def _news_brief(self, cap=True):
        since = now() - 24 * 3600
        stories = self._story_rows(since)
        mute = self.watch.get("mute", [])
        stories = [s for s in stories if not self._matches(s, mute)]
        def foreign(s):
            return s["cc"] not in (None, "US") and s["region"] != "usa" and bool(s["place"]) and s["place"].lower() in s["t"].lower()
        home = [s for s in stories if not s["local"] and (s["region"] == "usa" or s["cc"] == "US" or
                (not foreign(s) and (s["l"] + s["c"] + s["r"]) * 2 >= s["n"]))]
        local = [s for s in stories if s["local"]]
        homeids = {s["id"] for s in home} | {s["id"] for s in local}
        glob = self._one_per_story([s for s in stories if s["id"] not in homeids])
        home = self._one_per_story(home)
        following = []
        pool = self._story_rows(now() - 3 * 86400) if self.watch.get("follow") else []
        pool = [s for s in pool if not self._matches(s, mute)]
        for topic in self.watch.get("follow", []):
            hits = [s for s in pool if self._matches(s, [topic])]
            following.append({"topic": topic, "stories": hits[:4]})
        take = self.store.kv_get("news_take") or {}
        week_end = (datetime.date.today() + datetime.timedelta(days=7)).isoformat()
        rank = {"election": 0, "central bank": 1, "launch": 3, "earnings": 4, "economy": 2}
        coming = [i for i in self.store.kv_get("worldcal", []) if i["date"] <= week_end]
        coming = sorted(coming, key=lambda i: (rank.get(i["kind"], 5), i["date"]))[:8]
        coming.sort(key=lambda i: (i["date"], i["time"] or 0))
        if not cap:
            return {"global": glob, "home": home, "local": local}
        watched = []
        try:
            if self.civic:
                watched = [dict(r) for r in self.civic.q("SELECT * FROM watch_events WHERE at > ? ORDER BY n DESC LIMIT 12", (now() - 2 * 86400,))]
        except Exception:
            pass
        return {"now": now(), "take": take, "coming": coming, "global": glob[:8], "home": home[:7], "local": local[:5], "watched": watched,
                "following": following, "follow": self.watch.get("follow", []), "mute": mute,
                "outlets": len({i["source"] for i in self.store.q("SELECT DISTINCT source FROM items WHERE published > ?", (since,))})}

    def build_edition(self, kind="morning"):
        b = self._news_brief()
        old = self.store.kv_get("news_edition") or {}
        ed = {"day": self._edition_day(), "at": now(), "kind": kind, "global": b["global"], "home": b["home"],
              "local": b["local"], "coming": b["coming"], "take": old.get("take") if kind == "update" else {},
              "take_pending": True}
        self.store.kv_set("news_edition", ed)
        self._big_cache = (0, [])
        return ed

    def maybe_edition(self, force=False):
        ed = self.store.kv_get("news_edition") or {}
        if not force and ed.get("day") == self._edition_day():
            if ed.get("take_pending") and time.time() - ed.get("at", 0) > 600:
                self._write_take()          # the summary failed last time: try again
            return
        if not force and datetime.datetime.now().hour < self._brief_hour() and ed:
            return
        b = self._news_brief()
        if len(b["global"]) + len(b["home"]) < 4 and not force:
            return                           # not enough news pulled yet (just started up)
        self.build_edition("morning")
        self._write_take()

    def refresh_brief(self):
        """Rebuild the brief now (the refresh bar) and rewrite its summary in the background."""
        self.build_edition("update")
        threading.Thread(target=self._write_take, daemon=True).start()
        return self.news_brief()

    def _write_take(self):
        if not self._take_lock.acquire(blocking=False):
            return
        try:
            ed = self.store.kv_get("news_edition") or {}
            if not ed:
                return
            lines = ["GLOBAL:"] + [f"- {s['t']} ({s['n']} outlets)" for s in ed.get("global", [])[:8]] + \
                    ["AT HOME (United States):"] + [f"- {s['t']} ({s['n']} outlets)" for s in ed.get("home", [])[:7]]
            prompt = ("Write the top of a news brief for one reader, using ONLY these headlines (grouped by how many "
                      "outlets covered them). Plain words, neutral, no opinions, no invented details.\n"
                      'Reply ONLY with JSON: {"world": "3 sentences on the biggest things happening in the world", '
                      '"home": "2 sentences on the biggest things in the United States"}\n\n' + "\n".join(lines))
            try:
                from archie_brain import quick_chat
                d = json.loads(quick_chat(self.get_model(), prompt, max_tokens=400, timeout=150, json_mode=True, temperature=0.3))
            except Exception as e:
                self.store.health("News brief writer", "news", False, 0, str(e))
                return
            cur = self.store.kv_get("news_edition") or {}
            if cur.get("at") != ed.get("at"):
                return                           # a newer edition replaced it meanwhile
            cur["take"] = {"world": d.get("world", ""), "home": d.get("home", ""), "written": now()}
            cur["take_pending"] = False
            self.store.kv_set("news_edition", cur)
            self.store.health("News brief writer", "news", True, 1)
        finally:
            self._take_lock.release()

    # ---------- markets tied to places ----------
    def linked(self, kind, name, pk=""):
        if kind == "list":          # "Label~SYM~why|Label~SYM~why" from the page (mines)
            items = [tuple((p.split("~") + ["", "", ""])[:3]) for p in name.split("|") if p.count("~") >= 1][:8]
        else:
            items = market_links(kind, name, pk, self.country(name) if kind == "country" else None)
        quotes = self.store.kv_get("quotes", {})
        xq = self.store.kv_get("xquotes", {})
        dirty = False
        out = []
        for label, sym, why in items:
            q = quotes.get(sym) if self.store.kv_age("quotes") < 1800 else None
            if not q or q.get("price") is None:
                q = xq.get(sym)
                if (not q or time.time() - q.get("at", 0) > 900) and self.is_online:
                    try:
                        meta, closes, _ = self._yahoo(sym)
                        price = meta.get("regularMarketPrice") or (closes[-1] if closes else None)
                        prev = meta.get("chartPreviousClose") or meta.get("previousClose")
                        if price is not None and prev:
                            q = {"price": price, "prev": prev, "chg": (price / prev - 1) * 100,
                                 "spark": [round(c, 5) for c in closes][-40:], "at": time.time(),
                                 "cur": meta.get("currency", "")}
                            xq[sym] = q
                            dirty = True
                    except FetchError:
                        pass
            out.append({"label": label, "sym": sym, "why": why, "price": q.get("price") if q else None,
                        "chg": q.get("chg") if q else None, "spark": (q or {}).get("spark", [])[-40:],
                        "cur": (q or {}).get("cur", "")})
        if dirty:
            self.store.kv_set("xquotes", xq)
        return {"items": out}

    def _moves_text(self, kind, name):
        try:
            its = [i for i in self.linked(kind, name)["items"] if i["chg"] is not None]
        except Exception:
            return ""
        its.sort(key=lambda i: -abs(i["chg"]))
        return " · ".join(f"{i['label']} {'▲' if i['chg'] >= 0 else '▼'}{abs(i['chg']):.1f}%" for i in its[:3])

    # ---------- current-events quizzes and lessons ----------
    QUIZ_PROMPT = """Make a {n}-question multiple-choice quiz about the news for one reader who wants to stay informed.
Use ONLY facts stated in the numbered stories below. Never invent names, numbers, places or outcomes.
Mix question kinds: what happened, where, who is involved, and why it matters. Keep questions and options short.
Each question has exactly 4 options and exactly one is correct; wrong options must be believable but clearly wrong from the stories.
Reply ONLY with JSON:
{{"questions": [{{"q": "question", "options": ["A", "B", "C", "D"], "answer": 0, "why": "one sentence explaining the right answer, from the story", "story": 1}}]}}

Stories:
{ctx}"""

    LESSON_PROMPT = """You are Archie, a patient tutor. Teach one reader about this news story like a short class.
Use ONLY the reports and background below. If something isn't covered, say it's not known yet instead of guessing.
Plain words; explain any jargon.
Reply ONLY with JSON:
{{"title": "short lesson title",
  "big_picture": "2-3 sentences: what is going on",
  "background": "3-5 sentences: how it got to this point",
  "who": [{{"name": "a person, group or country", "role": "who they are and what they want"}}],
  "why_it_matters": "2-3 sentences",
  "terms": [{{"term": "a word or name from the story", "meaning": "plain explanation"}}],
  "watch_next": "1-2 sentences on what to watch for",
  "check": [{{"q": "a question to check understanding", "a": "its answer"}}]}}
Give 2-4 'who', 2-4 'terms' and 3 'check' items.

Story: {title}

Reports, oldest first:
{reports}

Background:
{bg}"""

    def _quiz_pool(self, days):
        since = now() - days * 86400
        st = self.store.q("SELECT * FROM clusters WHERE kind='story' AND last > ? AND n_sources >= 3 ORDER BY n_sources DESC LIMIT 60",
                          (since,))
        ev = self.store.q("SELECT * FROM clusters WHERE kind='event' AND confirmed=1 AND last > ? ORDER BY n_sources DESC LIMIT 20",
                          (since,))
        mute = self.watch.get("mute", [])
        pool, seen = [], []
        for c in list(st) + list(ev):
            tk = tokens(c["title"])
            if any(jaccard(tk, o) >= 0.4 for o in seen):
                continue
            if self._matches({"t": c["title"]}, mute):
                continue
            seen.append(tk)
            pool.append(c)
        random.shuffle(pool)
        pool = sorted(pool[:14], key=lambda c: -c["n_sources"])[:10]
        return pool

    def quiz(self, b):
        n = max(3, min(10, int(b.get("n") or 5)))
        days = max(1, min(14, int(b.get("days") or 7)))
        pool = self._quiz_pool(days)
        if len(pool) < 3:
            return {"error": "Not enough big stories stored yet. Leave Archie running a day and try again."}
        ctx = []
        for i, c in enumerate(pool, 1):
            alts = [r["title_en"] for r in self.store.q("SELECT title_en FROM items WHERE cluster=? AND title_en IS NOT NULL "
                                                        "ORDER BY published LIMIT 4", (c["id"],)) if r["title_en"] != c["title"]]
            summ = self.store.q("SELECT summary FROM items WHERE cluster=? AND lang='en' AND LENGTH(summary) > 60 LIMIT 1",
                                (c["id"],), one=True)
            where = self.geo.country_name(c["cc"]) or c["place"] or ""
            ctx.append(f"{i}. {c['title']}" + (f" ({where})" if where else "") +
                       ("\n   also reported as: " + " | ".join(alts[:2]) if alts else "") +
                       ("\n   " + re.sub(r"\s+", " ", summ["summary"])[:260] if summ else ""))
        try:
            from archie_brain import quick_chat
            d = json.loads(quick_chat(self.get_model(), self.QUIZ_PROMPT.format(n=n, ctx="\n".join(ctx)),
                                      max_tokens=1600, timeout=240, json_mode=True, temperature=0.4))
        except Exception as e:
            return {"error": f"couldn't reach the model ({e})"}
        qs = []
        for q in d.get("questions") or []:
            try:
                opts = [str(o).strip() for o in q["options"]][:4]
                ans = int(q["answer"])
                if len(opts) != 4 or not (0 <= ans < 4) or len(set(o.lower() for o in opts)) < 4 or not q.get("q"):
                    continue
                right = opts[ans]
                random.shuffle(opts)             # small models love putting the answer first
                si = int(q.get("story") or 0)
                c = pool[si - 1] if 1 <= si <= len(pool) else None
                qs.append({"q": str(q["q"]).strip(), "options": opts, "answer": opts.index(right),
                           "why": str(q.get("why") or "").strip(), "id": c["id"] if c else "",
                           "story": c["title"] if c else ""})
            except (KeyError, TypeError, ValueError):
                continue
        if not qs:
            return {"error": "The model's quiz didn't come out right. Try again."}
        out = {"questions": qs[:n], "days": days, "made": now()}
        self.store.kv_set("quiz_last", out)
        return out

    def quiz_score(self, b):
        hist = self.store.kv_get("quiz_scores", [])
        try:
            hist.append({"t": now(), "score": int(b.get("score", 0)), "total": int(b.get("total", 0))})
        except (TypeError, ValueError):
            return {"ok": False}
        self.store.kv_set("quiz_scores", hist[-60:])
        return {"ok": True, "history": hist[-10:]}

    def _bg_refs(self, text):
        try:
            from archie_brain import quick_chat
            d = json.loads(quick_chat(self.ai_model(), self.EXTRACT_PROMPT.format(text=text), max_tokens=200,
                                      timeout=90, json_mode=True, temperature=0.1))
            names = [t["name"] for t in (d.get("things") or []) if isinstance(t, dict) and t.get("name")][:3]
        except Exception:
            names = []
        refs = []
        for nm in names:
            hit = self._wiki_lookup(nm)
            if hit:
                refs.append({"title": hit[0], "text": re.sub(r"\s+", " ", hit[1])[:1200], "source": hit[2], "url": hit[3]})
        return refs

    def lesson(self, b):
        cid = b.get("id", "")
        c = self.store.q("SELECT * FROM clusters WHERE id=?", (cid,), one=True)
        if not c:
            return {"error": "that story isn't stored any more"}
        th = self.story_thread(cid)
        entries = th.get("entries") or []
        key = "lesson:" + cid + ":" + str(len(entries))
        cached = self.store.kv_get(key)
        if cached:
            return cached
        reports = "\n".join(f"{datetime.datetime.fromtimestamp(e['last']):%b %d} · {e['n']} source(s) · {e['t']}"
                            for e in entries[-25:]) or c["title"]
        refs = self._bg_refs(c["title"] + (" (" + (self.geo.country_name(c["cc"]) or "") + ")" if c["cc"] else ""))
        bg = "\n\n".join(f"## {r['title']} ({r['source']})\n{r['text']}" for r in refs) or "(no background found)"
        try:
            from archie_brain import quick_chat
            d = json.loads(quick_chat(self.get_model(), self.LESSON_PROMPT.format(title=c["title"], reports=reports, bg=bg),
                                      max_tokens=1100, timeout=240, json_mode=True, temperature=0.3))
        except Exception as e:
            return {"error": f"couldn't reach the model ({e})"}
        out = {"id": cid, "story": c["title"], "title": d.get("title") or c["title"], "big_picture": d.get("big_picture", ""),
               "background": d.get("background", ""), "why_it_matters": d.get("why_it_matters", ""),
               "watch_next": d.get("watch_next", ""),
               "who": [w for w in (d.get("who") or []) if isinstance(w, dict) and w.get("name")][:5],
               "terms": [t for t in (d.get("terms") or []) if isinstance(t, dict) and t.get("term")][:5],
               "check": [q for q in (d.get("check") or []) if isinstance(q, dict) and q.get("q")][:4],
               "refs": [{"title": r["title"], "source": r["source"], "url": r["url"]} for r in refs],
               "reports": len(entries), "since": th.get("since")}
        self.store.kv_set(key, out)
        return out

    def save_lesson(self, b):
        vault = self.vault()
        if not vault:
            return {"error": "No Obsidian vault is set in Archie."}
        L = b.get("lesson") or {}
        if not L.get("title"):
            return {"error": "nothing to save"}
        folder = os.path.join(vault, "Archie", "World", "Lessons")
        os.makedirs(folder, exist_ok=True)
        name = re.sub(r'[\\/:*?"<>|#^\[\]]', "", L["title"])[:80].strip() or "Lesson"
        path = os.path.join(folder, f"{datetime.date.today().isoformat()} {name}.md")
        md = [f"---\ntags: [archie-world, lesson]\ndate: {datetime.date.today().isoformat()}\n---", f"# {L['title']}", "",
              f"*From the story:* {L.get('story', '')} · [open on globe](archie://world#story={L.get('id', '')})", "",
              "## The big picture", L.get("big_picture", ""), "", "## How it got here", L.get("background", ""), ""]
        if L.get("who"):
            md += ["## Who's involved"] + [f"- **{w.get('name')}**: {w.get('role', '')}" for w in L["who"]] + [""]
        md += ["## Why it matters", L.get("why_it_matters", ""), ""]
        if L.get("terms"):
            md += ["## Words to know"] + [f"- **{t.get('term')}**: {t.get('meaning', '')}" for t in L["terms"]] + [""]
        md += ["## What to watch", L.get("watch_next", ""), ""]
        if L.get("check"):
            md += ["## Check yourself"] + [f"- {q.get('q')}\n  - *{q.get('a', '')}*" for q in L["check"]] + [""]
        if L.get("refs"):
            md += ["## Background from"] + [f"- {r['title']} ({r['source']})" + (f" {r['url']}" if r.get("url") else "") for r in L["refs"]]
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(md) + "\n")
        return {"ok": True, "path": path}

    # ---------- alerts (watchlist) ----------
    def _alert(self, dedupe, title, body, hash_):
        try:
            self.store.x("INSERT INTO alerts(time, title, body, hash, dedupe) VALUES(?,?,?,?,?)",
                         (now(), title, body, hash_, dedupe))
        except sqlite3.IntegrityError:
            return

    def check_alerts(self):
        w = self.watch
        items = w.get("items", [])
        regions = {i["id"] for i in items if i.get("kind") == "region"}
        countries = {i["id"].lower() for i in items if i.get("kind") == "country"}
        keywords = [i["id"].lower() for i in items if i.get("kind") in ("keyword", "choke", "pipe")]
        # 1. confirmed conflict events in watched places
        for c in self.store.q("SELECT * FROM clusters WHERE confirmed=1 AND alerted=0 AND last > ? AND kind='event'",
                              (now() - 6 * 3600,)):
            cname = (self.geo.country_name(c["cc"]) or "").lower()
            if c["region"] in regions or cname in countries:
                where = REGION_NAMES.get(c["region"]) or self.geo.country_name(c["cc"]) or "World"
                self._alert("c:" + c["id"], f"{where}: {c['title']}", f"confirmed by {c['n_sources']} sources",
                            f"event={c['id']}")
            self.store.x("UPDATE clusters SET alerted=1 WHERE id=?", (c["id"],))
        # 2. chokepoints / pipelines / keywords in the news with disruption words
        if keywords:
            for c in self.store.q("SELECT * FROM clusters WHERE n_sources >= 2 AND alerted=0 AND last > ? AND kind='story'",
                                  (now() - 6 * 3600,)):
                t = (c["title"] or "").lower()
                for k in keywords:
                    key = k.replace("strait of ", "").replace(" canal", "")
                    if key and key in t and DISRUPT_RE.search(t):
                        kind = next((i["kind"] for i in items if i["id"].lower() == k), "keyword")
                        orig = next((i["id"] for i in items if i["id"].lower() == k), k)
                        mv = self._moves_text(kind, orig) if kind in ("choke", "pipe") else ""
                        self._alert("s:" + c["id"], f"{k.title()}: {c['title']}", f"{c['n_sources']} outlets" + (f" · {mv}" if mv else ""),
                                    f"{'choke' if kind == 'choke' else 'at'}={slug(k) if kind == 'choke' else '%s,%s,3' % (c['lat'] or 20, c['lng'] or 0)}")
                        self.store.x("UPDATE clusters SET alerted=1 WHERE id=?", (c["id"],))
                        break
        # 3. big earthquakes
        for h in self.store.q("SELECT * FROM hazards WHERE kind='quake' AND alerted=0 AND mag >= ? AND time > ?",
                              (w.get("quake_min", 6.3), now() - 6 * 3600)):
            self._alert("q:" + h["id"], f"M{h['mag']:.1f} earthquake", h["title"] + (" · tsunami flag" if h["level"] else ""),
                        f"at={h['lat']},{h['lng']},1.2")
            self.store.x("UPDATE hazards SET alerted=1 WHERE id=?", (h["id"],))
        # 4. market moves
        quotes = self.store.kv_get("quotes", {})
        today = datetime.date.today().isoformat()
        for i in items:
            if i.get("kind") != "asset":
                continue
            q = quotes.get(i["id"])
            if q and abs(q.get("chg", 0)) >= float(i.get("pct", 3)):
                label = next((m[0] for m in MARKETS if m[1] == i["id"]), i["id"])
                self._alert(f"m:{i['id']}:{today}", f"{label} {'▲' if q['chg'] > 0 else '▼'} {abs(q['chg']):.1f}% today",
                            f"now {q['price']:,.2f}", "note")

    def brief_lines(self):
        """A few lines for Archie's morning brief (watched places first)."""
        watched = {i["id"] for i in self.watch.get("items", []) if i.get("kind") == "region"}
        cut = now() - 14 * 3600
        ev = self.store.q("SELECT * FROM clusters WHERE kind='event' AND last > ? ORDER BY confirmed DESC, n_sources DESC, last DESC "
                          "LIMIT 60", (cut,))
        ev = sorted(ev, key=lambda c: (c["region"] not in watched, -c["confirmed"], -c["n_sources"]))[:4]
        st = self.store.q("SELECT * FROM clusters WHERE kind='story' AND last > ? AND n_sources >= 3 ORDER BY n_sources DESC LIMIT 2",
                          (cut,))
        quotes = self.store.kv_get("quotes", {})
        moves = []
        for label, sym in (("S&P fut.", "ES=F"), ("Oil", "CL=F"), ("Gold", "GC=F"), ("Bitcoin", "BTC-USD")):
            q = quotes.get(sym)
            if q and self.store.kv_age("quotes") < 6 * 3600:
                moves.append(f"{label} {'▲' if q['chg'] >= 0 else '▼'}{abs(q['chg']):.1f}%")
        return {"events": [{"id": c["id"], "t": c["title"][:110], "confirmed": bool(c["confirmed"]),
                            "where": REGION_NAMES.get(c["region"]) or self.geo.country_name(c["cc"]) or (c["place"] or "")}
                           for c in ev],
                "stories": [{"id": c["id"], "t": c["title"][:110], "n": c["n_sources"]} for c in st],
                "moves": moves}

    def pop_alerts(self):
        """New alerts for Archie to pop up (held during quiet hours)."""
        qh = self.watch.get("quiet_hours") or [23, 7]
        h = datetime.datetime.now().hour
        if qh and (h >= qh[0] or h < qh[1]):
            return []
        rows = self.store.q("SELECT * FROM alerts WHERE shown=0 ORDER BY time LIMIT 5")
        for r in rows:
            self.store.x("UPDATE alerts SET shown=1 WHERE id=?", (r["id"],))
        return [dict(r) for r in rows]

    # ---------- what the page asks for ----------
    def item(self, cid):
        """One stored event/story by id (for old links from the digest or saved notes)."""
        c = self.store.q("SELECT * FROM clusters WHERE id=?", (cid,), one=True)
        if not c:
            return {}
        return self._pack([c])[0][0] if c["kind"] == "event" else self._pack([c])[1][0]

    def state(self, hours=72):
        cut = now() - hours * 3600
        crow = self.store.q("SELECT * FROM clusters WHERE last > ? ORDER BY last DESC LIMIT 1500", (cut,))
        events, stories = self._pack(crow)
        return self._state_rest(events, stories)

    def _pack(self, crow):
        events, stories = [], []
        ids = [c["id"] for c in crow]
        by_c = {}
        for i in range(0, len(ids), 400):
            chunk = ids[i:i + 400]
            for r in self.store.q(f"SELECT id, source, feed, lang, side, lean, title, title_en, url, author, published, fetched, cluster "
                                  f"FROM items WHERE cluster IN ({','.join('?' * len(chunk))})", chunk):
                by_c.setdefault(r["cluster"], []).append(r)
        trust = self.trust_scores()
        for c in crow:
            its = sorted(by_c.get(c["id"], []), key=lambda r: r["published"])
            src = []
            seen = set()
            for r in its:
                if r["source"] in seen:
                    continue
                seen.add(r["source"])
                src.append({"name": r["source"], "feed": r["feed"], "lang": r["lang"], "side": r["side"], "lean": r["lean"],
                            "url": r["url"], "title": r["title"], "author": r["author"], "time": r["published"],
                            "trust": trust.get(r["source"])})
            d = {"id": c["id"], "t": c["title"], "type": c["etype"] or "news", "topic": c["topic"], "lat": c["lat"],
                 "lng": c["lng"], "place": c["place"], "cc": c["cc"], "country": self.geo.country_name(c["cc"]),
                 "region": c["region"], "first": c["first"], "last": c["last"], "n": c["n_sources"],
                 "confirmed": bool(c["confirmed"]), "src": src,
                 "arrived": min((r["fetched"] or r["published"] for r in its), default=c["first"])}
            (events if c["kind"] == "event" else stories).append(d)
        return events, stories

    def _state_rest(self, events, stories):
        haz = [dict(h) for h in self.store.q("SELECT * FROM hazards WHERE time > ? OR kind != 'quake'", (now() - 7 * 86400,))]
        for h in haz:
            try:
                h["extra"] = json.loads(h["extra"] or "{}")
            except ValueError:
                h["extra"] = {}
        # conflict shading: countries with many military reports in the last 7 days
        rank = {"unrest": 1, "armed": 2, "war": 3}
        shade = dict(self.sources.get("conflict_baseline") or {})
        live = {}
        for r in self.store.q("SELECT cc, COUNT(*) n FROM clusters WHERE last > ? AND kind='event' AND etype IN "
                              "('clash','shelling','drone','missile','blast') AND cc IS NOT NULL GROUP BY cc", (now() - 7 * 86400,)):
            name = self.geo.country_name(r["cc"])
            if name and r["n"] >= 3:
                lv = "war" if r["n"] >= 25 else "armed" if r["n"] >= 8 else "unrest"
                live[name] = r["n"]
                if rank[lv] > rank.get(shade.get(name), 0):
                    shade[name] = lv
        return {
            "version": VERSION, "now": now(), "online": self.is_online, "last_cycle": self.last_cycle, "busy": self.busy,
            "events": events, "stories": stories, "hazards": haz, "fires": self.store.kv_get("fires", []),
            "shade": shade, "shade_live": live, "front": self.store.kv_get("front"),
            "quotes": self.store.kv_get("quotes", {}), "curve": self.store.kv_get("curve"), "fred": self.store.kv_get("fred"),
            "calendar": self.store.kv_get("calendar", []), "earnings": self.store.kv_get("earnings"),
            "predictions": self.store.kv_get("predictions", []), "note": self.store.kv_get("note"),
            "ships": self.store.kv_get("ships", {}),
            "watch": self.watch, "places": self.geo.status, "tiles": bool(self.sources.get("tiles", True)),
            "brief_new": self.big_count(),
            "storms": self.store.kv_get("storms", {}), "iss": self.store.kv_get("iss_tle"),
        }

    def sources_report(self):
        rows = [dict(r) for r in self.store.q("SELECT * FROM health ORDER BY kind, name")]
        trust = self.trust_scores(detail=True)
        for r in rows:
            r["trust"] = trust.get(r["name"])
        return {"sources": rows, "file": SOURCES_PATH}

    def trust_scores(self, detail=False):
        """How often each source's reports were matched by a different source (last 30 days).
        Matching looks past headline wording: shared words in the headline AND summary, shared names
        (people, places, groups), the same place on the map, within two days of each other.
        Reports newer than 48 h are still waiting, so they don't count yet."""
        if getattr(self, "_trust_t", 0) > now() - 3600:
            return self._trust
        cut_old, cut_new = now() - 30 * 86400, now() - 48 * 3600
        rows = self.store.q(
            "SELECT i.source, i.published, i.title, i.title_en, i.summary, i.lat, i.lng, i.cc, c.n_sources "
            "FROM items i LEFT JOIN clusters c ON c.id = i.cluster WHERE i.published >= ? "
            "AND (c.kind IS NULL OR c.kind = 'event')", (cut_old - 2 * 86400,))
        items = []
        for r in rows:
            head = r["title_en"] or r["title"] or ""
            words = tokens(head + " " + (r["summary"] or "")[:400])
            names = {w.lower() for w in re.findall(r"\b[A-Z][a-zA-Z'-]{2,}", head)} - STOP
            items.append((r["source"], r["published"] or 0, words, names, r["lat"], r["lng"], r["cc"], r["n_sources"] or 1))
        index = {}
        for i, it in enumerate(items):
            for w in it[2]:
                index.setdefault(w, []).append(i)
        common = {w for w, ids in index.items() if len(ids) > 400}  # words too common to tell stories apart
        out = {}
        for i, (src, pub, words, names, lat, lng, cc, nsrc) in enumerate(items):
            if not (cut_old <= pub <= cut_new):
                continue
            hit = nsrc >= 2
            if not hit:
                seen = {}
                for w in words - common:
                    for j in index[w]:
                        if j != i:
                            seen[j] = seen.get(j, 0) + 1
                for j, k in seen.items():
                    if k < 3:
                        continue
                    o = items[j]
                    if o[0] == src or abs(o[1] - pub) > 2 * 86400:
                        continue
                    shared_names = len(names & o[3])
                    near = (cc and cc == o[6]) or (lat is not None and o[4] is not None and km(lat, lng, o[4], o[5]) < 400)
                    if jaccard(words, o[2]) >= 0.2 or (shared_names >= 2 and (near or k >= 4)) or (shared_names >= 1 and near and k >= 4):
                        hit = True
                        break
            t = out.setdefault(src, [0, 0])
            t[0] += 1
            t[1] += 1 if hit else 0
        self._trust = {s: {"rate": round(100 * b / t), "n": t} for s, (t, b) in out.items() if t >= 8}
        self._trust_t = now()
        return self._trust

    def ask(self, question):
        """Answer from what's stored (last 3 days), with citations."""
        qt = tokens(question)
        places = []
        hit = self.geo.find_in_text(question)
        if hit:
            places.append(hit)
        cands = []
        for c in self.store.q("SELECT * FROM clusters WHERE last > ? ORDER BY last DESC LIMIT 1200", (now() - 72 * 3600,)):
            s = jaccard(qt, tokens(c["title"])) * 3 + min(c["n_sources"], 6) * 0.05
            if places and c["lat"] is not None and km(places[0][0], places[0][1], c["lat"], c["lng"]) < 400:
                s += 1.2
            if s > 0.15:
                cands.append((s, c))
        cands.sort(key=lambda x: -x[0])
        top = [c for _, c in cands[:12]]
        top.sort(key=lambda c: -c["last"])
        if not top:
            return {"answer": "I don't have any reports about that from the last three days.", "cites": []}
        ctx = "\n".join(f"[{i + 1}] {datetime.datetime.fromtimestamp(c['last']).strftime('%a %H:%M')} · "
                        f"{c['place'] or REGION_NAMES.get(c['region'], '')} · {c['n_sources']} source(s) · {c['title']}"
                        for i, c in enumerate(top))
        try:
            from archie_brain import quick_chat
            ans = quick_chat(self.get_model(), ASK_PROMPT.format(q=question, ctx=ctx), max_tokens=400, timeout=150)
        except Exception as e:
            ans = f"(Couldn't reach the model: {e}) Here are the closest reports."
        cites = [{"n": i + 1, "id": c["id"], "title": c["title"], "lat": c["lat"], "lng": c["lng"], "kind": c["kind"]}
                 for i, c in enumerate(top)]
        return {"answer": ans, "cites": cites}

    def country(self, name):
        key = "country:" + name.lower()
        d = self.store.kv_get(key)
        if d is None or self.store.kv_age(key) > 30 * 86400:
            try:
                r = fetch_json("https://restcountries.com/v3.1/name/" + urllib.parse.quote(name) +
                               "?fields=name,capital,population,currencies,languages,region,subregion,area,flag,cca2")
                d = r[0] if isinstance(r, list) and r else {}
                self.store.kv_set(key, d)
            except FetchError:
                d = d or {}
        return d

    # ---------- saving articles ----------
    def save_article(self, payload):
        """Save a headline picture + a note (with the article text when it can be read)."""
        title = (payload.get("title") or "").strip()
        url = (payload.get("url") or "").strip()
        publisher = (payload.get("publisher") or "").strip()
        author = (payload.get("author") or "").strip()
        published = payload.get("time")
        text, image_bytes = "", None
        if url and self.is_online:
            try:
                page, final, ctype = fetch(url, timeout=20, raw=True)
                if "html" in ctype and "news.google." not in (final or ""):
                    h = page.decode("utf-8", errors="replace")
                    meta = page_meta(h)
                    title = title or meta.get("title", "")
                    publisher = meta.get("site") or publisher
                    author = meta.get("author") or author
                    published = parse_date(meta.get("published")) or published
                    text = article_text(h)
                    url = final or url
                    if meta.get("image"):
                        try:
                            image_bytes, _, _ = fetch(urllib.parse.urljoin(url, meta["image"]), timeout=15, raw=True)
                        except FetchError:
                            image_bytes = None
            except FetchError:
                pass
        when = datetime.datetime.fromtimestamp(published) if published else datetime.datetime.now()
        folder = os.path.join(SAVED_DIR, when.strftime("%Y-%m"))
        os.makedirs(folder, exist_ok=True)
        base = f"{when:%Y-%m-%d} - {safe_name(title)[:70]}"
        png = os.path.join(folder, base + ".png")
        md = os.path.join(folder, base + ".md")
        headline_card(png, title, publisher, author, when, url, payload.get("place") or "", image_bytes)
        lines = [f"# {title}", "", f"- **Publisher:** {publisher or 'unknown'}", f"- **Author:** {author or 'not listed'}",
                 f"- **Published:** {when:%A %d %B %Y, %H:%M}", f"- **Saved:** {datetime.datetime.now():%Y-%m-%d %H:%M}",
                 f"- **Link:** {url}" if url else "- **Link:** (none)",
                 f"- **On the globe:** archie://world#{payload.get('hash')}" if payload.get("hash") else "",
                 "", f"![[{os.path.basename(png)}]]", ""]
        if payload.get("translated"):
            lines += ["**In English:** " + payload["translated"], ""]
        if payload.get("others"):
            lines += ["**Also reported by:** " + ", ".join(payload["others"]), ""]
        if text:
            lines += ["## Article text (as saved)", "", text]
        with open(md, "w", encoding="utf-8") as f:
            f.write("\n".join(l for l in lines if l is not None) + "\n")
        return {"ok": True, "png": png, "md": md, "folder": folder}

    def saved_list(self):
        out = []
        for root, _, files in os.walk(SAVED_DIR):
            for fn in files:
                if fn.endswith(".png"):
                    p = os.path.join(root, fn)
                    out.append({"name": fn[:-4], "png": os.path.relpath(p, SAVED_DIR).replace("\\", "/"),
                                "time": int(os.path.getmtime(p))})
        return sorted(out, key=lambda x: -x["time"])[:200]

    # ---------- nightly digest into the vault ----------
    def maybe_digest(self):
        """Write tonight's digest after 11 pm; catch up on yesterday if the PC was off."""
        last = self.store.kv_get("digest_last") or ""
        today = datetime.date.today()
        day = None
        if datetime.datetime.now().hour >= 23 and last < today.isoformat():
            day = today
        elif last < (today - datetime.timedelta(days=1)).isoformat() and self.store.q(
                "SELECT 1 FROM clusters WHERE last BETWEEN ? AND ? LIMIT 1",
                (now() - 2 * 86400, now() - 86400), one=True):
            day = today - datetime.timedelta(days=1)
        if day and self.write_digest(day):
            self.store.kv_set("digest_last", day.isoformat())

    def write_digest(self, day=None):
        vault = self.vault()
        if not vault:
            return None
        day = day or datetime.date.today()
        t0 = int(datetime.datetime.combine(day, datetime.time()).timestamp())
        t1 = t0 + 86400
        folder = os.path.join(vault, "Archie", "World")
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, f"{day.isoformat()}.md")
        ev = self.store.q("SELECT * FROM clusters WHERE kind='event' AND confirmed=1 AND last BETWEEN ? AND ? "
                          "ORDER BY n_sources DESC", (t0, t1))
        st = self.store.q("SELECT * FROM clusters WHERE kind='story' AND last BETWEEN ? AND ? ORDER BY n_sources DESC LIMIT 12",
                          (t0, t1))
        hz = self.store.q("SELECT * FROM hazards WHERE time BETWEEN ? AND ? AND (kind != 'quake' OR mag >= 5.5) "
                          "ORDER BY COALESCE(mag, 0) DESC LIMIT 10", (t0, t1))
        out = ["---", f"date: {day.isoformat()}", "tags: [archie-world]", "---", "",
               f"# World · {day:%A %d %B %Y}", "",
               "Confirmed means two or more separate sources reported it. Links open the spot on the globe.", ""]
        by_region = {}
        for c in ev:
            by_region.setdefault(REGION_NAMES.get(c["region"]) or self.geo.country_name(c["cc"]) or "Elsewhere", []).append(c)
        if by_region:
            out.append("## On the ground")
            for reg in sorted(by_region, key=lambda r: -len(by_region[r])):
                out.append(f"### {reg}")
                for c in by_region[reg][:10]:
                    out.append(f"- {c['title']} · {c['place'] or ''} · {c['n_sources']} sources · "
                               f"[open on globe](archie://world#event={c['id']})")
                out.append("")
        if st:
            out.append("## Biggest stories")
            for c in st:
                out.append(f"- {c['title']} · {c['n_sources']} outlet{'s' if c['n_sources'] != 1 else ''}")
            out.append("")
        if hz:
            out.append("## Disasters")
            for h in hz:
                lab = f"M{h['mag']:.1f} " if h["mag"] and not h["title"].startswith("M ") else ""
                out.append(f"- {lab}{h['title']} · [open on globe](archie://world#at={h['lat']},{h['lng']},1.2)")
            out.append("")
        quotes = self.store.kv_get("quotes", {})
        moves = []
        for label, sym, *_ in MARKETS:
            q = quotes.get(sym)
            if q and abs(q.get("chg", 0)) >= 1.0:
                moves.append(f"- {label} {'▲' if q['chg'] > 0 else '▼'} {abs(q['chg']):.2f}%")
        if moves:
            out += ["## Markets (big moves)"] + moves + [""]
        note = self.store.kv_get("note") or {}
        if note.get("date") == day.isoformat() and note.get("take"):
            out += ["## Morning note", note["take"], ""]
        saved = [s for s in self.saved_list() if datetime.date.fromtimestamp(s["time"]) == day]
        if saved:
            out += ["## Saved today"] + [f"- {s['name']}" for s in saved] + [""]
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(out))
        return path


def slug(t):
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")


def safe_name(t):
    t = re.sub(r'[\\/:*?"<>|\r\n\t]+', " ", t or "article").strip()
    return re.sub(r"\s+", " ", t) or "article"


def page_meta(h):
    def meta(*keys):
        for k in keys:
            m = re.search(r'<meta[^>]+(?:property|name)=["\']%s["\'][^>]*content=["\']([^"\']+)' % re.escape(k), h, re.I) or \
                re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]*(?:property|name)=["\']%s["\']' % re.escape(k), h, re.I)
            if m:
                return html.unescape(m.group(1)).strip()
        return ""
    d = {"title": meta("og:title", "twitter:title"), "site": meta("og:site_name", "application-name"),
         "author": meta("author", "article:author", "parsely-author", "sailthru.author", "byl"),
         "published": meta("article:published_time", "og:article:published_time", "pubdate", "date", "parsely-pub-date"),
         "image": meta("og:image", "twitter:image")}
    for blob in re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', h, re.S | re.I):
        try:
            j = json.loads(blob.strip())
        except ValueError:
            continue
        for o in (j if isinstance(j, list) else j.get("@graph", [j]) if isinstance(j, dict) else []):
            if not isinstance(o, dict):
                continue
            a = o.get("author")
            if a and not d["author"]:
                if isinstance(a, list):
                    a = ", ".join(x.get("name", "") if isinstance(x, dict) else str(x) for x in a[:3])
                elif isinstance(a, dict):
                    a = a.get("name", "")
                d["author"] = str(a)
            d["published"] = d["published"] or o.get("datePublished", "")
            pub = o.get("publisher")
            if isinstance(pub, dict) and not d["site"]:
                d["site"] = pub.get("name", "")
    if d["author"].startswith("http"):
        d["author"] = ""
    d["author"] = re.sub(r"^by\s+", "", d["author"], flags=re.I)
    return d


def article_text(h, limit=20000):
    body = re.search(r"<article[^>]*>(.*?)</article>", h, re.S | re.I)
    chunk = body.group(1) if body else h
    chunk = re.sub(r"<(script|style|nav|footer|aside|form)[^>]*>.*?</\1>", " ", chunk, flags=re.S | re.I)
    paras = [strip_tags(p) for p in re.findall(r"<p[^>]*>(.*?)</p>", chunk, re.S | re.I)]
    paras = [re.sub(r"\s+", " ", p) for p in paras if len(p) > 60]
    return "\n\n".join(paras)[:limit]


def headline_card(path, title, publisher, author, when, url, place="", image_bytes=None):
    """A 1200x675 picture of the headline you saved."""
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
    W, H = 1200, 675
    img = Image.new("RGB", (W, H), (7, 9, 7))
    if image_bytes:
        try:
            ph = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            ph = ph.resize((W, int(ph.height * W / ph.width)))
            ph = ph.crop((0, 0, W, min(ph.height, H)))
            ph = ph.filter(ImageFilter.GaussianBlur(1))
            shade = Image.new("L", (W, H), 0)
            sd = ImageDraw.Draw(shade)
            for y in range(H):
                sd.line([(0, y), (W, y)], fill=int(200 * max(0, 1 - y / (H * 0.95))))
            img.paste(Image.blend(Image.new("RGB", ph.size, (7, 9, 7)), ph, 0.8), (0, 0), shade.crop((0, 0) + ph.size))
        except Exception:
            pass
    d = ImageDraw.Draw(img)

    def font(name, size):
        for p in (os.path.join(FONTS_DIR, name), name):
            try:
                return ImageFont.truetype(p, size)
            except OSError:
                continue
        return ImageFont.load_default()
    f_head, f_mono, f_mono_b = font("Geist-SemiBold.ttf", 54), font("JetBrainsMono-Regular.ttf", 22), font("JetBrainsMono-Bold.ttf", 22)
    lime = (198, 244, 50)
    d.rectangle([0, 0, 10, H], fill=lime)
    d.text((56, 48), (publisher or "unknown publisher").upper(), font=f_mono_b, fill=lime)
    # wrap the headline
    words, lines, cur = (title or "").split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if d.textlength(t, font=f_head) > W - 112:
            lines.append(cur)
            cur = w
        else:
            cur = t
    if cur:
        lines.append(cur)
    size = 54
    while len(lines) > 5 and size > 34:
        size -= 6
        f_head = font("Geist-SemiBold.ttf", size)
        words, lines, cur = (title or "").split(), [], ""
        for w in words:
            t = (cur + " " + w).strip()
            if d.textlength(t, font=f_head) > W - 112:
                lines.append(cur)
                cur = w
            else:
                cur = t
        if cur:
            lines.append(cur)
    y = H - 170 - len(lines[:6]) * int(size * 1.22)
    for ln in lines[:6]:
        d.text((56, y), ln, font=f_head, fill=(236, 237, 232))
        y += int(size * 1.22)
    meta = f"{when:%a %d %b %Y · %H:%M}" + (f"   ·   by {author}" if author else "") + (f"   ·   {place}" if place else "")
    d.text((56, H - 118), meta, font=f_mono, fill=(170, 172, 165))
    short = re.sub(r"^https?://(www\.)?", "", url or "")[:86]
    d.text((56, H - 80), short, font=font("JetBrainsMono-Regular.ttf", 18), fill=(110, 112, 106))
    d.text((W - 260, H - 80), "saved in ARCHIE WORLD", font=font("JetBrainsMono-Regular.ttf", 18), fill=(110, 112, 106))
    img.save(path, "PNG", optimize=True)


# ---------------------------------------------------------------------------
# archie:// links (from the digest, saved notes, anywhere)
# ---------------------------------------------------------------------------
def register_protocol():
    if sys.platform != "win32":
        return
    import winreg
    py = sys.executable.replace("python.exe", "pythonw.exe")
    cmd = f'"{py}" "{os.path.abspath(__file__)}" --open "%1"'
    key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\archie")
    winreg.SetValueEx(key, "", 0, winreg.REG_SZ, "URL:Archie")
    winreg.SetValueEx(key, "URL Protocol", 0, winreg.REG_SZ, "")
    ck = winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\archie\shell\open\command")
    winreg.SetValueEx(ck, "", 0, winreg.REG_SZ, cmd)


def open_link(link):
    """Handle archie://world#... : tell the running Archie, or start it."""
    hash_ = link.split("#", 1)[1] if "#" in link else ""
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{PORT}/api/open", data=json.dumps({"hash": hash_}).encode(),
                                     headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=3)
        return
    except Exception:
        pass
    os.makedirs(WORLD_DIR, exist_ok=True)
    with open(NAV_PENDING, "w", encoding="utf-8") as f:
        f.write(hash_)
    py = sys.executable.replace("python.exe", "pythonw.exe")
    subprocess.Popen([py, os.path.join(APP_DIR, "archie.py"), "--world"], cwd=APP_DIR)


# ---------------------------------------------------------------------------
# The local web server (127.0.0.1 only)
# ---------------------------------------------------------------------------
MIME = {".html": "text/html; charset=utf-8", ".js": "application/javascript; charset=utf-8", ".json": "application/json",
        ".css": "text/css", ".png": "image/png", ".jpg": "image/jpeg", ".ttf": "font/ttf", ".svg": "image/svg+xml",
        ".ico": "image/x-icon", ".md": "text/markdown; charset=utf-8", ".mp3": "audio/mpeg", ".m4a": "audio/mp4",
        ".wav": "audio/wav", ".ogg": "audio/ogg", ".flac": "audio/flac", ".aac": "audio/aac", ".gif": "image/gif", ".webp": "image/webp", ".jpeg": "image/jpeg"}
TILE_SRC = {"base": ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"]}
TILE_UA = "ArchieWorld/1.0 (personal desktop app; tiles cached locally)"   # OSM asks apps to name themselves


def darken_tile(data):
    """Turn a light map tile dark to match Archie (invert, then turn the colors back around)."""
    try:
        from PIL import Image, ImageEnhance
        im = Image.open(io.BytesIO(data)).convert("RGB")
        inv = Image.eval(im, lambda v: 255 - v)
        h, s_, v = inv.convert("HSV").split()
        h = h.point(lambda x: (x + 128) % 256)
        s_ = s_.point(lambda x: int(x * 0.55))
        out = Image.merge("HSV", (h, s_, v)).convert("RGB")
        out = ImageEnhance.Brightness(out).enhance(0.82)
        out = ImageEnhance.Contrast(out).enhance(1.1)
        roads = im.convert("L").point(lambda v: 255 if v >= 250 else 0)     # white streets would turn black: make them gray
        out.paste((64, 68, 60), mask=roads)
        b = io.BytesIO()
        out.save(b, "PNG", optimize=True)
        return b.getvalue()
    except Exception:
        return data


def _tile_cache_trim():
    total, files = 0, []
    for root, _, fs in os.walk(TILE_DIR):
        for f in fs:
            p = os.path.join(root, f)
            try:
                st = os.stat(p)
            except OSError:
                continue
            total += st.st_size
            files.append((st.st_atime, st.st_size, p))
    if total <= TILE_CACHE_MB * 1e6:
        return
    for _, size, p in sorted(files):
        try:
            os.remove(p)
        except OSError:
            pass
        total -= size
        if total < TILE_CACHE_MB * 0.8e6:
            break


def _make_server(svc):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, body, ctype="application/json", cache=None):
            if isinstance(body, (dict, list)):
                body = json.dumps(body, ensure_ascii=False).encode("utf-8")
            elif isinstance(body, str):
                body = body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            if cache:
                self.send_header("Cache-Control", cache)
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def _file(self, base, rel, cache="max-age=3600"):
            p = os.path.normpath(os.path.join(base, rel))
            if not p.startswith(os.path.normpath(base)) or not os.path.isfile(p):
                return self._send(404, {"error": "not found"})
            with open(p, "rb") as f:
                self._send(200, f.read(), MIME.get(os.path.splitext(p)[1].lower(), "application/octet-stream"), cache)

        def _ws_ok(self, token_request=False):
            """The Workshop runs code, so only Archie's own page and the VSCodium add-on may use it: the request must be for
            this PC by name (no other site pointing its name here) and, except when the page asks for it, carry the key."""
            host = (self.headers.get("Host") or "").split(":")[0]
            if host not in ("127.0.0.1", "localhost"):
                return False
            if token_request:
                return not self.headers.get("Origin") or self.headers.get("Origin", "").startswith(("http://127.0.0.1", "http://localhost"))
            return secrets_eq(self.headers.get("X-Archie-Key") or "", svc.workshop.token if svc.workshop else "")

        def _body(self):
            n = int(self.headers.get("Content-Length") or 0)
            try:
                return json.loads(self.rfile.read(n) or b"{}")
            except ValueError:
                return {}

        def do_GET(self):
            u = urllib.parse.urlparse(self.path)
            path, qs = u.path, urllib.parse.parse_qs(u.query)
            try:
                if path in ("/", "/index.html"):
                    return self._file(WEB_DIR, "index.html", "no-cache")
                if path.startswith("/flags/"):
                    return self._file(FLAG_DIR, urllib.parse.unquote(path[7:]), "max-age=604800")
                if path.startswith("/golden/"):
                    return self._file(GOLD_DIR, urllib.parse.unquote(path[8:]), "max-age=604800")
                if path.startswith("/web/"):
                    return self._file(WEB_DIR, path[5:], "no-cache" if path.endswith(".js") else "max-age=86400")
                if path.startswith("/fonts/"):
                    return self._file(FONTS_DIR, path[7:], "max-age=604800")
                if path.startswith("/saved/"):
                    return self._file(SAVED_DIR, urllib.parse.unquote(path[7:]))
                if path.startswith("/ws/preview/") and svc.workshop:      # a web project's page, for the Workshop preview
                    parts = urllib.parse.unquote(path[12:]).split("/", 1)
                    if len(parts) == 2:
                        return self._file(svc.workshop.folder(parts[0]), parts[1], "no-cache")
                    return self._send(404, {"error": "not found"})
                if path.startswith("/api/vault/"):
                    if not svc.vaultlib:
                        return self._send(200, {"error": "The Vault didn't start: " + getattr(svc, "vault_err", "")})
                    if path == "/api/vault/icon":
                        got = svc.vaultlib.icon((qs.get("id") or [""])[0])
                        return self._send(200, got[0], got[1], "max-age=86400") if got else self._send(404, {"error": "no icon"})
                    return self._send(200, svc.vaultlib.get(path[11:], lambda k, d="": (qs.get(k) or [d])[0]))
                if path.startswith("/api/ws/"):
                    if not svc.workshop:
                        return self._send(200, {"error": "The Workshop didn't start: " + getattr(svc, "workshop_err", "")})
                    if not self._ws_ok(path[8:] == "token"):
                        return self._send(403, {"error": "not allowed"})
                    r = svc.workshop.get(path[8:], lambda k, d="": (qs.get(k) or [d])[0])
                    return self._send(200 if r is not None else 404, r if r is not None else {"error": "unknown"})
                if path == "/api/state":
                    return self._send(200, svc.state(int((qs.get("hours") or ["72"])[0])))
                if path == "/api/nav":
                    return self._send(200, {"hash": svc.pop_nav()})
                if path == "/api/sources":
                    return self._send(200, svc.sources_report())
                if path == "/api/saved":
                    return self._send(200, svc.saved_list())
                if path == "/api/calendar":
                    return self._send(200, svc.world_calendar())
                if path == "/api/thread":
                    return self._send(200, svc.story_thread((qs.get("id") or [""])[0]))
                if path == "/api/thread_summary":
                    return self._send(200, svc.thread_summary((qs.get("id") or [""])[0]))
                if path == "/api/brief":
                    return self._send(200, svc.news_brief())
                if path == "/api/item":
                    return self._send(200, svc.item((qs.get("id") or [""])[0]))
                if path == "/api/country":
                    return self._send(200, svc.country((qs.get("name") or [""])[0]))
                if path == "/api/linked":
                    return self._send(200, svc.linked((qs.get("kind") or [""])[0], (qs.get("name") or [""])[0],
                                                      (qs.get("pk") or [""])[0]))
                if path == "/api/rules":
                    return self._send(200, svc.rules())
                if path == "/api/solar_trails":
                    return self._send(200, svc.store.kv_get("trails", {}) or {})
                if path == "/api/rovers":
                    return self._send(200, svc.store.kv_get("rovers", {}) or {})
                if path == "/api/solar":
                    return self._send(200, svc.solar())
                if path == "/api/cosmic":
                    return self._send(200, svc.store.kv_get("cosmic", {}) or {})
                if path == "/api/exo":
                    return self._send(200, svc.exo())
                if path == "/api/people":
                    return self._send(200, svc.people())
                if path == "/api/golden":
                    return self._send(200, svc.golden())
                if path == "/api/govs":
                    return self._send(200, svc.govs())
                if path == "/api/gov_cabinet":
                    return self._send(200, svc.gov_cabinet((qs.get("iso") or [""])[0], (qs.get("gec") or [""])[0]))
                if path.startswith("/api/civic/"):
                    if not svc.civic:
                        return self._send(200, {"error": "The lawmaking module didn't start; check Archie's log."})
                    c, a = svc.civic, lambda k, d="": (qs.get(k) or [d])[0]
                    name = path[11:]
                    if name == "overview":
                        return self._send(200, c.overview())
                    if name == "votes":
                        return self._send(200, c.votes(a("cc"), a("chamber"), a("q"), a("offset", "0"), a("bill")))
                    if name == "vote":
                        return self._send(200, c.vote(a("id")))
                    if name == "members":
                        return self._send(200, c.members(a("cc"), a("q"), a("chamber")))
                    if name == "member":
                        return self._send(200, c.member(a("key")))
                    if name == "person":
                        return self._send(200, c.person(a("cc"), a("name"), a("title")))
                    if name == "money":
                        return self._send(200, c.money(a("bio"), a("name")))
                    if name == "donations":
                        return self._send(200, c.donations(a("name")))
                    if name == "employers":
                        return self._send(200, c.employers(a("cand"), a("cycle")))
                    if name == "find":
                        return self._send(200, c.find(a("q")))
                    if name == "watch":
                        return self._send(200, c.watching(a("kind"), a("id")))
                    if name == "bills":
                        return self._send(200, c.bills(a("cc"), a("q"), a("stage"), a("offset", "0"), a("sort", "latest")))
                    if name == "bill":
                        return self._send(200, c.bill(a("id")))
                    if name == "exec":
                        return self._send(200, c.execs(a("kind"), a("q"), a("offset", "0"), a("id")))
                    if name == "calendar":
                        return self._send(200, c.calendar())
                    if name == "myreps":
                        return self._send(200, c.myreps())
                    r = c.more_get(name, a)
                    if r is None:
                        r = c.extra_get(name, a)
                    if r is None:
                        r = c.local_get(name, a)
                    if r is not None:
                        return self._send(200, r)
                    return self._send(404, {"error": "unknown"})
                if path == "/api/satinfo":
                    return self._send(200, svc.sat_info((qs.get("id") or [""])[0]))
                if path == "/api/wx":
                    return self._send(200, svc.weather_at((qs.get("lat") or [""])[0], (qs.get("lng") or [""])[0]))
                if path == "/api/sats":
                    return self._send(200, svc.sats((qs.get("group") or [""])[0]))
                if path == "/api/label_words":
                    return self._send(200, svc.label_words((qs.get("id") or [""])[0]))
                if path == "/api/quiz_last":
                    return self._send(200, svc.store.kv_get("quiz_last") or {})
                if path == "/api/radar":
                    return self._send(200, radar_frames(svc))
                m = re.match(r"^/tile/(street|radar)/(\d+)/(\d+)/(\d+)(?:/(\d+))?\.png$", path)
                if m:
                    return self._tile("base" if m.group(1) == "street" else "radar", int(m.group(2)), int(m.group(3)),
                                      int(m.group(4)), m.group(5))
                return self._send(404, {"error": "not found"})
            except Exception as e:
                return self._send(500, {"error": str(e)})

        def _tile(self, kind, z, x, y, frame=None):
            if kind == "base" and not svc.sources.get("tiles", True):
                return self._send(404, b"", "image/png")
            src = svc.sources.get("tile_url") or TILE_SRC["base"][0]
            sub = f"radar/{frame}" if kind == "radar" else "base-" + hashlib.md5(src.encode()).hexdigest()[:6]
            p = os.path.join(TILE_DIR, sub, str(z), str(x), f"{y}.png")
            if os.path.exists(p):
                with open(p, "rb") as f:
                    return self._send(200, f.read(), "image/png", "max-age=86400")
            if not svc.is_online:
                return self._send(404, b"", "image/png")
            if kind == "radar":
                rf = radar_frames(svc)
                fr = next((f for f in rf.get("frames", []) if str(f["time"]) == str(frame)), None)
                if not fr or z > 7:
                    return self._send(404, b"", "image/png")
                url = f"{rf['host']}{fr['path']}/256/{z}/{x}/{y}/2/1_1.png"
            else:
                url = src.format(z=z, x=x, y=y, s="abc"[(x + y) % 3])
            try:
                data, _, _ = fetch(url, timeout=15, raw=True, headers={"User-Agent": TILE_UA} if "openstreetmap" in url else None)
            except FetchError:
                return self._send(404, b"", "image/png")
            if kind == "base" and svc.sources.get("tile_dark", True):
                data = darken_tile(data)
            try:
                os.makedirs(os.path.dirname(p), exist_ok=True)
                with open(p, "wb") as f:
                    f.write(data)
                if kind == "base" and hash(p) % 200 == 0:
                    threading.Thread(target=_tile_cache_trim, daemon=True).start()
            except OSError:
                pass
            return self._send(200, data, "image/png", "max-age=86400")

        def do_POST(self):
            path = urllib.parse.urlparse(self.path).path
            b = self._body()
            try:
                if path == "/api/save":
                    return self._send(200, svc.save_article(b))
                if path == "/api/ask":
                    return self._send(200, svc.ask(b.get("q", "")))
                if path == "/api/explain":
                    return self._send(200, svc.explain(b))
                if path == "/api/relabel":
                    return self._send(200, svc.relabel(b))
                if path == "/api/rules":
                    return self._send(200, svc.remove_rule(int(b.get("remove", -1))))
                if path == "/api/brief_refresh":
                    return self._send(200, svc.refresh_brief())
                if path == "/api/quiz":
                    return self._send(200, svc.quiz(b))
                if path == "/api/quiz_score":
                    return self._send(200, svc.quiz_score(b))
                if path == "/api/lesson":
                    return self._send(200, svc.lesson(b))
                if path == "/api/lesson_save":
                    return self._send(200, svc.save_lesson(b))
                if path == "/api/calendar_add":
                    return self._send(200, svc.calendar_add(b))
                if path.startswith("/api/vault/"):
                    host = (self.headers.get("Host") or "").split(":")[0]
                    origin = self.headers.get("Origin") or ""
                    if not svc.vaultlib or host not in ("127.0.0.1", "localhost") or (origin and not origin.startswith(("http://127.0.0.1:%d" % PORT, "http://localhost:%d" % PORT))):
                        return self._send(403, {"error": "not allowed"})
                    return self._send(200, svc.vaultlib.post(path[11:], b))
                if path.startswith("/api/ws/"):
                    if not svc.workshop or not self._ws_ok():
                        return self._send(403, {"error": "not allowed"})
                    r = svc.workshop.post(path[8:], b)
                    return self._send(200 if r is not None else 404, r if r is not None else {"error": "unknown"})
                if path.startswith("/api/civic/") and svc.civic:
                    name = path[11:]
                    if name == "summary":
                        return self._send(200, svc.civic.summary(b.get("kind", ""), b.get("id", ""), bool(b.get("force"))))
                    if name == "myreps":
                        return self._send(200, svc.civic.myreps(b))
                    if name == "settings":
                        return self._send(200, svc.civic.save_settings(b))
                    if name == "watch":
                        return self._send(200, svc.civic.watch_set(b))
                    if name == "watch_seen":
                        return self._send(200, svc.civic.watch_seen())
                    r = svc.civic.local_post(name, b)
                    if r is not None:
                        return self._send(200, r)
                    return self._send(404, {"error": "unknown"})
                if path == "/api/weekly":
                    p2 = svc.maybe_weekly(force=True)
                    return self._send(200, {"ok": bool(p2), "path": p2 or "", "error": "" if p2 else "no vault or no data yet"})
                if path == "/api/follow":
                    svc.save_watch({k: b[k] for k in ("follow", "mute") if isinstance(b.get(k), list)})
                    return self._send(200, svc.news_brief())
                if path == "/api/watch":
                    svc.save_watch(b)
                    return self._send(200, {"ok": True, "watch": svc.watch})
                if path == "/api/open":
                    svc.open_window(b.get("hash", ""))
                    return self._send(200, {"ok": True})
                if path == "/api/showfile":
                    p = b.get("path", "")
                    if p.startswith(SAVED_DIR) and os.path.exists(p) and sys.platform == "win32":
                        subprocess.Popen(["explorer", "/select,", p])
                    return self._send(200, {"ok": True})
                if path == "/api/refresh":
                    for k in ("rss", "gnews", "telegram", "quakes", "markets", "ai", "cluster"):
                        svc.store.x("DELETE FROM kv WHERE key=?", ("t:" + k,))
                    return self._send(200, {"ok": True})
                return self._send(404, {"error": "not found"})
            except Exception as e:
                return self._send(500, {"error": str(e)})

    class S(ThreadingHTTPServer):
        daemon_threads = True
        allow_reuse_address = True
    return S(("127.0.0.1", PORT), H)


_radar = {"t": 0, "d": {}}


def radar_frames(svc):
    if time.time() - _radar["t"] < 300 or not svc.is_online:
        return _radar["d"]
    try:
        d = fetch_json("https://api.rainviewer.com/public/weather-maps.json")
        past = ((d.get("radar") or {}).get("past")) or []
        _radar["d"] = {"host": d.get("host", "https://tilecache.rainviewer.com"), "frames": past[-13:]}
        _radar["t"] = time.time()
        svc.store.health("RainViewer radar", "weather", True, len(past))
    except FetchError as e:
        svc.store.health("RainViewer radar", "weather", False, 0, str(e))
    return _radar["d"]


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--open":
        open_link(sys.argv[2])
