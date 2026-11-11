# Archie on your phone

A home-screen app for Android (Chrome) that syncs with Archie on your PC through Tailscale.

## Set up (once)
1. On the PC: restart Archie, then double-click **Set up phone.bat** in `D:\Archie` (Windows asks for
   admin). It turns on a private https address for this PC on your Tailscale network and copies it.
2. On the phone: install Tailscale, sign in with the same account, open the address in Chrome, then
   menu > **Install app**.
3. In the app: **More > Settings > turn on notifications**.

Only your own Tailscale login can open it (the first login to open it becomes the owner; it's stored
in `D:\Archie\phone_state.json`). Nothing is reachable from the internet.

## What it does
- **Today**: class now, today's schedule, what's due, countdown, to-dos, the week, news.
- **Class**: one big record button. The class comes from your calendar (or pick one). While
  recording: **Mark** a moment, **Board** photo, **Note** at the current time, pause. Stop saves
  `Recording <date time>.webm` into `Lectures/<class>` in your vault, where Archie types it out and
  writes the lecture notes as always, plus a note with your marks. Every 10 s is kept on the phone,
  so a crash or a closed app doesn't lose the recording (it's saved the next time Archie opens).
- **Add**: one line for anything ("dentist fri 3pm", "essay due friday", a link, "note: ..."), paste,
  photo, file, note. Share from any app (Share > Archie): links become saved articles, files go to
  Obsidian (filed under the class during a class), text becomes a note. A link you just copied is
  offered when you open Archie.
- **News**: the brief, every story from the last 3 days by region, and governments, all offline.
- **More**: calendar, to-dos and deadlines, notes, saved articles (readable offline), settings.
- **Chat** (top right): answered by your PC; questions wait on the phone when it isn't reachable.
- **Notifications**: classes, labs and exams 15 minutes ahead (other events 30), a morning summary at
  8, and "lecture notes ready" when Archie finishes a recording.

Everything works offline; changes and files wait on the phone and go through when the PC is reachable.

## Files
`index.html`, `app.js`, `style.css` the app · `sw.js` offline, sharing and notifications ·
`manifest.webmanifest` install details. PC side: `archie_phone.py` (server, notifications),
`archie_webpush.py` (encrypted push), `archie_sync.py` (the sync it shares with Archie Lite).
