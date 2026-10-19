# World

The two bigger screens Archie opens in an app window, plus what they need.

| Folder | What's in it |
|---|---|
| `web/` | Archie World (`index.html`, `app.js`: globe, news, markets; `solar.js`, `galaxy.js`: space; `gov.js`, `civic*.js`: governments and lawmaking; `archive.js`), the Workshop (`workshop.html`) and the Vault (`vault.html`, `search.html`) |
| `web/lib/` | globe.gl, D3, satellite.js, topojson-client (see THIRD-PARTY.md) |
| `web/data/` | Country outlines, the Earth textures, constellation lines, government structures, US counties |
| `web/flags/` | Country flags (flag-icons, MIT) |
| `workshop/` | Courses, building blocks, whole-app recipes, the VSCodium add-on and a practice Arduino |
| `sources.json` | News feeds and searches. Edit `local` for news close to home |

Everything Archie World downloads while running (the news database, map tiles, records from parliaments) is kept next to these files on your PC and is never part of the repository.
