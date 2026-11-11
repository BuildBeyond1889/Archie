# Archie Lite

The laptop side of Archie: a small owl on your desktop and a panel with Today, Calendar, To-do,
Saved and Chat. It syncs with Archie on your PC over your home Wi-Fi. No AI or news downloading
runs on the laptop: the PC does the heavy work.

## Use

- **Click the owl** or press **Ctrl+Alt+A** to open or hide the panel. Drag the owl anywhere.
- **Ctrl+Alt+Space** opens quick add. **Drop files on the owl** to keep them and send them to Obsidian.
- **Right-click the owl**: sync now, Start with Windows, quit.
- The dot under the owl: **lime** = synced with your PC, **amber** = changes waiting or away from home,
  **grey** = not paired yet.
- Everything works offline. Changes go to the PC the next time you're on home Wi-Fi with Archie running.
- **Chat** only works at home: your PC's model answers.

## What's new in 1.3

- **News** works like Feather's World: **refresh** pulls the news feeds live from this laptop
  (anywhere with internet) and groups matching headlines; it also gets your PC's latest when it's
  reachable. Views: **Brief** (your PC's news brief), **Live**, **All stories** (every story from the
  last 3 days, by region) and **Governments**: every country's leaders, cabinet and background,
  searchable by country or leader, readable offline. Flags come from the PC the first time each shows.

## What's new in 1.2

- **Today** is your day: the class you're in, today's schedule, what's due, the next countdown,
  your to-dos and the week ahead. **News** has its own tab with the full brief from your PC.
- **Notes:** during a class, *take notes* (Today or Notes) starts a note filed under that class.
  Notes save as you type, to `Documents\Archie Lite` on this laptop, and go to Obsidian on the PC in
  `Lectures\<class>` (or `Archie Lite` when there's no class). Edit them here; if a note was also
  changed in Obsidian on the PC, both versions are kept.
- **Drop anything on the owl or the panel.** Files are kept in `Documents\Archie Lite` and sent to
  the PC in encrypted pieces. In Obsidian each file gets its own note (PDFs and images embedded,
  text files included). During a class it's all filed under that class. Recordings go where Archie
  already types them out into lecture notes or voice notes. Links dropped on the panel are saved as
  articles; dropped text becomes a note.
- **Quick add: Ctrl+Alt+Space** anywhere. `dentist fri 3pm`, `essay due friday`,
  `finish lab report by thursday`, `call mom`, a link, or `note: ...`. Works offline.
- **Pop-ups** 15 minutes before classes, labs and exams (30 before other events), plus a morning
  summary of what's due. Click one to open the right tab.
- **Hover the owl** for a status line: last sync, what's due, the class you're in or what's next.
- **On battery** it syncs every 10 minutes instead of 2, and catches up when you plug in.
- **Saved articles** are kept here as text: tap one in Saved to read it offline.
- **Chat** questions asked while the PC can't be reached wait here and are answered at the next
  sync, with a pop-up.
- **Archie Doctor** on the PC shows the laptop: last seen, version, anything waiting.

## How syncing works

Each change (a calendar entry, a ticked task, a new deadline, a followed topic, a saved story) is sent
on its own, so one edit never overwrites another. If the same calendar entry was changed on both
machines, both versions are kept and the laptop's is marked "(laptop)". Every message is encrypted
with the pairing key in `data\pairing.json` (written by Archie on the PC). Keep that file private.

## Install and update

**First install (from the stick):** on the laptop, open the stick's `ArchieLite` folder and double-click
**Install or Update Archie Lite.bat**. It installs Python if the laptop has none, adds the encryption
package, copies Archie Lite to `%LOCALAPPDATA%\ArchieLite`, brings over your data and the pairing key,
adds it to the Start menu and to "start with Windows", and starts the owl. Running it again updates
and keeps your data.

**Updates after that come over Wi-Fi.** Each sync, the PC tells the laptop which Archie Lite files it has
(`D:\ArchieLite\app` and `web`). Changed files are fetched, checked, and installed the next time the panel
is closed; Archie Lite then restarts itself in about two seconds. Python files that don't compile are
never installed, and the replaced files are kept in `data\update_backup`.

**Stick as the backup way:** on the PC, double-click **Make Archie Lite stick.bat** in `D:\ArchieLite`
(it asks for the stick's drive letter), then run the installer on the laptop.

## Network

The laptop and the PC must be able to reach each other: the same Wi-Fi network, or a Tailscale link
(addresses `100.x`, accepted too). A Wi-Fi extender in "router" mode makes its own network
(for example `192.168.39.x` while the main router is `192.168.1.x`), and the two can't see each other.
Fix it by connecting the laptop to the extender's Wi-Fi, setting the extender to access point/bridge
mode, or installing Tailscale on both.

## Files

- `app\lite.py` the owl, hotkey and panel window · `app\lite_core.py` data and syncing ·
  `app\lite_proto.py` the encryption (identical to `D:\Archie\archie_lite_proto.py`)
- `app\lite_quick.py` quick add · `app\lite_world.py` news and governments (from Feather) · `app\lite_cal.py` dates and times (a copy of `D:\Archie\archie_calendar.py`) ·
  `installer\install.py` the installer · `web\` the panel · `data\lite.json` your laptop's copy · `data\pairing.json` the pairing key
