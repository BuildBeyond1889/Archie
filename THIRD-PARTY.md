# Third-party credits

A.R.C.H.I.E.'s own code is under the [MIT licence](LICENSE). These parts come from other people and keep their own licences.

## Bundled in this repository

| What | Where | Licence |
|---|---|---|
| [globe.gl](https://github.com/vasturiano/globe.gl) 2.46 | `World/web/lib/globe.gl.min.js` | MIT |
| [D3](https://d3js.org) 7.9 | `World/web/lib/d3.min.js` | ISC |
| [satellite.js](https://github.com/shashwatak/satellite-js) 5.0 | `World/web/lib/satellite.min.js` | MIT |
| [topojson-client](https://github.com/topojson/topojson-client) 3.1 | `World/web/lib/topojson-client.min.js` | ISC |
| [flag-icons](https://github.com/lipis/flag-icons) | `World/web/flags/` | MIT (licence file in that folder) |
| Country outlines from [Natural Earth](https://www.naturalearthdata.com) via [world-atlas](https://github.com/topojson/world-atlas) | `World/web/data/countries-*.json` | Public domain / ISC |
| Earth texture and relief (NASA Blue Marble and topography, via the three-globe examples) | `World/web/data/topo.jpg`, `bump.png` | Public domain (NASA) |
| Constellation boundaries (IAU) | `World/web/data/constbounds.json` | Public data |
| Government structure, from the CIA World Factbook | `World/web/data/govs.json` | Public domain (US government work) |
| US county list (US Census Bureau) | `World/web/data/us_counties.json` | Public domain |
| [Geist](https://vercel.com/font) | `fonts/` | SIL Open Font License 1.1 |
| [JetBrains Mono](https://www.jetbrains.com/lp/mono/) | `fonts/` | SIL Open Font License 1.1 |
| [Micro 5](https://fonts.google.com/specimen/Micro+5) | `fonts/` | SIL Open Font License 1.1 |
| [Atkinson Hyperlegible](https://www.brailleinstitute.org/freefont/) (Braille Institute) | `fonts/` | SIL Open Font License 1.1 |
| [Young Serif](https://github.com/noirblancrouge/YoungSerif) | `fonts/` | SIL Open Font License 1.1 |

Each font's licence text sits next to it in `fonts/`.

## Downloaded by the Get / Install files (not in this repository)

| What | Licence |
|---|---|
| [Ollama](https://ollama.com) | MIT |
| Qwen 2.5 models (Alibaba) | Apache 2.0 (7B and smaller) |
| Gemma 3 (Google) | Gemma Terms of Use |
| [faster-whisper](https://github.com/SYSTRAN/faster-whisper) and Whisper models (OpenAI) | MIT |
| [Piper](https://github.com/rhasspy/piper) and its voices | MIT; each voice has its own licence on its model card |
| Stable Diffusion XL (Stability AI) | CreativeML Open RAIL++-M |
| T2I-Adapter sketch model (TencentARC) | Apache 2.0 |
| [diffusers](https://github.com/huggingface/diffusers), [transformers](https://github.com/huggingface/transformers), PyTorch | Apache 2.0 / BSD |
| [libzim](https://github.com/openzim/python-libzim) | GPL-3.0 (installed separately; not bundled) |
| [VSCodium](https://vscodium.com), [Continue](https://github.com/continuedev/continue) | MIT / Apache 2.0 |
| Offline Wikipedia and other Kiwix packs | Each pack's own licence (mostly CC BY-SA) |

## Data used while running

Archie World reads public sources when you open it: news feeds, GDELT, ReliefWeb, USGS, GDACS, NOAA, NASA JPL Horizons, CelesTrak, Wikidata, Wikipedia, the World Bank, the FEC, govinfo.gov, parliaments' open data and others listed in the manual. Their content stays theirs; Archie only shows and links it.
