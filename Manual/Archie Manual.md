# ARCHIE Manual
<!-- version: 3.23.0 · updated: Oct 2, 2026 -->

**A**rtificial **R**easoning **C**ore, **H**ome **I**ntelligence **E**ngine. Your private AI that runs entirely on your own PC. This manual works offline. It lives at `D:\Archie\Archie Manual.html` and opens in any browser, with no internet needed.

> **Tip:** You can also just ask Archie. Questions like "archie, how do I snip the screen?" make it look up the answer in this manual.

## Quick start

1. Make sure **Ollama** is running. It starts with Windows; if it isn't running, open the Ollama app.
2. Double-click the **Archie** shortcut on your Desktop, or `Start Archie.bat` in `D:\Archie`.
3. The lime owl appears near the bottom-right of your screen. **Click it** to open the chat.
4. Type after the lime `>` and press {{Enter}} (or click **RUN**).

That's it. Everything else in this manual is optional extras.

| Want to... | Do this |
|---|---|
| Open or hide Archie from anywhere | {{Ctrl+Alt+A}} |
| Ask about something on screen | {{Ctrl+Alt+S}}, then drag a box |
| Record a voice note | {{Ctrl+Alt+V}} or **mic**; do it again to stop |
| Ask by voice | {{Ctrl+Alt+T}}, speak, {{Ctrl+Alt+T}} again |
| Open today's daily note | Type `daily` |
| Study flashcards | Type `study` |
| See or add to your calendar | Click the **date** at the top, or type `exam: bio midterm oct 12 9am` |
| Make a picture | Type `draw a ruined desert city at dusk` |
| Open an app | Type `open blender` (or say it with {{Ctrl+Alt+T}}) |
| Attach a file | Drag it onto the chat, or click **+ attach** |
| Start fresh | The **+** icon at the top |
| See today's plan | The **sun** icon at the top |
| Find an old chat | The **clock** icon at the top |
| See everything Archie can do | Click **help** at the bottom (or type `help`) |
| More options | **Right-click the owl** |

### A school day with Archie

Type `school day` to see this in the chat.

1. **Morning.** Open Archie and read the [morning brief](#morning-brief-and-to-dos): your countdowns, today's classes, to-dos from yesterday's lectures with their due dates, and last night's recap. Then put the PC to **sleep** (not shut down).
2. **In class.** When the lecture starts, tap the **microphone** in Obsidian on your phone. Put the phone face-down, listen, take normal notes, and tap it again when class ends. That's all you do.
3. **While you're out.** About 20 minutes after class, the PC wakes itself (with [wake after class](#lectures-class-capture) on). The recording syncs, and Archie types it out and writes the lecture note: summary, key points with times, notes, terms, to-dos, review questions and a mind map. Homework goes on your to-do list. Then the PC goes back to sleep.
4. **Home.** Every lecture is waiting in Obsidian under `Lectures`. Skim the summary and key points. If something didn't click, the time next to it tells you where to jump in the recording. With the note open, type `make flashcards from this note`, or ask about **this note**.
5. **Homework.** `focus: bouncing ball assignment` starts the [owl timer](#focus-timer-the-owl); it goes in your daily note.
6. **Drawing.** `gym` for 15 minutes of timed references in the [drawing gym](#drawing-gym). The class ladder makes a good warm-up, and it keeps your streak going.
7. **Night.** Click the **moon** for the [evening recap](#evening-recap) and talk for a minute. Tomorrow's brief picks it up.

**Before you rely on it:** do one long test recording with the phone locked (to be sure it keeps recording for a whole class), start the day with a charged phone, and check each syllabus about recording.

**Pin Archie to the taskbar:** run **Create Shortcut.bat**. Then open the Start menu, right-click **Archie**, and choose **Pin to taskbar**. Clicking the taskbar owl starts Archie, or opens the chat if Archie is already running.

## The chat window

From top to bottom:

- **Top row.** The owl, **ARCHIE**, the **model pill** (the one with the lime dot; click it to switch AI models), and **today's date** (click it for the calendar; a colored dot means something's on today). The icons on the right:
  - **Sun:** the morning brief.
  - **Clock:** chat history.
  - **+:** new chat.
  - **x:** hide the window. {{Esc}} does the same.
- **Mode tabs:** **Tutor · Professor · Code · Robotics · Writing**. The lit tab is the current mode. Click it again to go back to **General**. See [Modes](#modes).
- **The conversation.** Your messages sit in bubbles on the right. Archie's answers have a thin **lime line** down the left. Underneath an answer you may see `src:` (where the facts came from) and **save → obsidian**. You can select and copy any answer text.
- **The input bar.** Type after the `>` and the box grows as you type (up to 6 lines).
  - {{Enter}} sends and {{Shift+Enter}} adds a new line.
  - While Archie is answering, **RUN** becomes **STOP**.
- **Bottom buttons:**
  - **+ attach** adds files.
  - **snip** captures part of the screen.
  - **notes** searches your Notes, past chats and Obsidian.
  - **wiki** looks things up in offline Wikipedia.
  - **mic** records a voice note (see [Voice notes](#voice-notes)).
  - **speak** reads every answer out loud (see [Talking with Archie](#talking-with-archie)).
  - **help** lists everything Archie can do, grouped (talking and learning, studying, your day, making, and Obsidian and your notes), with **open** links and your hotkeys.
  - A filled dot **●** means on; **○** means off.
- **Status** (bottom right) shows what Archie is doing, like "Checking your notes...".
- **Resize** by dragging the little **◢** in the bottom-right corner. **Move** the window by dragging its top row.

**The owl** can be dragged anywhere and remembers where you put it. It **blinks** while Archie is thinking. Right-click it for the full menu (see [The owl menu](#the-owl-menu)).

## Models

Archie uses AI models installed in Ollama. Nothing is sent online.

| Friendly name | Real name | Good for |
|---|---|---|
| Main brain | `qwen2.5:7b` | School, writing, general questions |
| Coder | `qwen2.5-coder:7b` | Programming (Python, C#, Godot, Arduino...) |
| Vision | `gemma3:4b` | Reading images: photos of notes, screenshots |
| (handwriting) | `qwen2.5vl:7b` | Reads handwriting and scans into text (optional, from **Get Handwriting Model.bat**) |
| (helper) | `nomic-embed-text` | Lets the Notes search work; not a chat model |

- Switch models with the **model pill** at the top.
- When you attach a picture, Archie **switches to the Vision model by itself** and tells you. Start a new chat (**+**) to go back.
- **Rename models:** right-click the owl > **Edit model names**. Write one per line, like `qwen2.5:7b = Main brain`.
- **Update your models:** once a year, double-click **Update Archie.bat** (the yearly checkup, see [Updating Archie](#updating-archie)). Models never change by themselves.
- **Add a model:** open a Command Prompt and run `ollama pull <name>`. It appears in the pill menu next time you click it. This is the one thing that needs internet.

## The picture strip (header pictures)

The strip in the top bar, between the recap button and the icons, shows pictures from the **Banners** folder (`D:\Archie\Banners`).

- **Add your own:** drop any .jpg, .png or .webp into the Banners folder. Archie notices within about 20 seconds and shows the new one. Remove a file and it leaves the rotation. Wide pictures work best.
- **The time** (24-hour, in the pixel font Micro 5) sits small in the bottom left, softly faded into the edge.
- **Click it** for the next picture (a slow crossfade).
- **It changes by itself** every 15 minutes. Right-click it > **Change pictures...** for every 5, 15 or 30 minutes, every hour, once a day, or only when you click.
- **Time of day** (follows your clock): a gold tint in the morning (5-10 am), normal by day (10 am-5 pm), sunset orange in the evening (5-8 pm), and dark blue at night with stars and a small lime moon (8 pm-5 am). Right-click > **Preview morning / day / evening / night** shows all four.
- **Focus timer:** while the owl timer runs, a lime line fills along the bottom of the picture and the time shows on it.
- **Right-click** also has **Pin this picture**, **Previous picture**, **Open the Banners folder**, **Reload pictures** and **Hide the picture strip**. Turn it back on from the owl menu: **Header pictures**.
- **Aim the crop:** the strip is thin, so Archie crops each picture. To aim it, edit `Banners\banners.json`, like `"harbor.jpg": [55, 38]` (percent across, percent down).
- The strip needs room: at the smallest chat sizes it hides itself. Make the chat wider (drag the corner) to see it.

## Modes

Each mode changes how Archie behaves, and can pick the model that suits it.

| Tab | Mode | What it does |
|---|---|---|
| (none lit) | General | All-round helper |
| Tutor | Tutor | Helps you *learn*: hints, one step at a time, ends with a check question |
| Professor | Professor | Teaches like an MIT professor who's also a great explainer: the big idea, then first principles, the precise version, a worked example, common mistakes, connections, and check questions. Deep but understandable |
| Code | Programmer | Complete runnable code, points to exact lines when debugging. Uses the Coder model |
| Robotics | Robotics | Wiring pin by pin, parts lists, safety warnings (voltage, LiPo, heat) |
| Writing | Literature & Writing | Feedback on specific sentences, keeps your voice |

- **Change how a mode behaves:** right-click the owl > **Open Modes folder** and edit its `.txt` file in Notepad. An optional first line `model: qwen2.5-coder:7b` picks its model.
- **Make your own mode:** add a new `.txt` file to that folder, named like `6 - Game Design.txt`. Extra modes show up under a **more ▾** tab.

## About me

Archie reads `about_me.txt` before every answer, so it always knows your goals, projects and how you like things explained.

- Edit it: right-click the owl > **Edit About me**. Changes apply to your next message.
- Lines starting with `#` are notes to yourself and are ignored.

## Attaching files and pictures

- **Drag files onto the chat** or click **+ attach**. Attached files show as small tags above the input bar. Click **✕** on a tag to remove it.
- **Archie can read:** PDF, Word (`.docx`), EPUB books, text, Markdown, code files, Jupyter notebooks, and images (PNG, JPG, WebP, iPhone HEIC...). Phone photos are turned the right way up automatically.
- **Send with no question** and Archie tells you what the file is and summarizes it.
- **Big files:** about the first 10,000 words are read. For longer things (books, whole courses), put them in the **Notes** folder instead.
- **Scanned PDFs** (pictures of pages) can't be read as an attachment. Put them in **Notes** instead, and Archie reads them page by page (see [Handwritten notes and scans](#handwritten-notes-and-scans)).
- **Keep a copy:** each tag has a **notes ●/○** switch. When it's ● the file is also copied into `Notes\Saved from chat`, so Archie can find it later. Turn the default off with right-click the owl > **Save dropped files to Notes**. Snips and files already in Notes aren't copied.

## Handwritten notes and scans

Write on paper or with the Surface pen, and get the page into the **Notes** folder or your **Obsidian vault** (see [Notes on the Surface](#notes-on-the-surface-obsidian)). Archie **reads it by itself** within about a minute. From then on your handwriting is searchable like typed notes:
- "what did I write about mitosis?" with **notes ●**
- quiz questions in the morning brief
- **save → obsidian**

**How it works**
1. A new photo (JPG, PNG, iPhone HEIC...) or a **scanned PDF** shows up anywhere in Notes. `Notes\Handwritten` is the natural spot.
2. Archie reads it **once** with a vision model, in the background, and saves the text right next to it as `<photo name> (transcribed).md`.
3. It tells you in the chat ("Read 2 new pages of notes...").

- **Fix a misread word:** open the `(transcribed).md` in Notepad and correct it. Archie uses your version.
- **Read a page again:** delete its `(transcribed).md`.
- **Unclear words** get `[?]` after them. **Drawings and diagrams** become `[Diagram: ...]` descriptions.
- It **waits while you're chatting**, so answers never slow down. Each page takes roughly 10–30 seconds.
- **Turn it off or on:** right-click the owl > **Read photos of notes automatically**.
- **Check for new photos right now:** right-click the owl > **Re-read notes now**.

**Best results**
- Run **Get Handwriting Model.bat** once (while online). It adds `qwen2.5vl:7b`, which reads handwriting much better than the regular Vision model, and adds iPhone-photo support. Archie picks it automatically.
- Photograph straight on, with good light and one page per photo.
- Neat print reads almost perfectly, normal handwriting very well, and messy cursive is hit or miss.

### Notes on the Surface (Obsidian)

The recommended setup is to take all your notes in **Obsidian on the Surface**, in the same vault Archie reads on the PC.

1. **Sync the vault.** Two ways:
   - **Obsidian Sync** (paid, from about $4/month): turn it on in Obsidian on both the Surface and the PC. It's the easiest.
   - **Syncthing** (free): syncs over your home Wi-Fi with no cloud.
   Archie works the same with either.
2. **Typed notes:** just write. Archie already searches your vault with **notes ●**.
3. **Pen notes:** install the **Excalidraw** community plugin and write with the pen in an Excalidraw drawing. In Excalidraw's settings, turn on **auto-export PNG** (Embed & Export > Export settings). Every drawing then also saves a `.excalidraw.png`, which Archie reads.
   - Archie waits until you've stopped drawing for a minute, then types the page out as a note named `<drawing name> (transcribed).md`, right next to it.
   - When you add to the drawing later, the note is updated. Any fixes you made to that note by hand are replaced, so fix the drawing instead.
4. **Paper notes:** photo or scan the page and put it in the vault's **Handwritten** folder (Archie creates it). Any folder named Handwritten works, like `School/Handwritten`. Dragging the image into a note in that folder works too.

Each typed-out page shows up in Obsidian as a real note:
- tagged `#handwritten`,
- with the original image embedded at the top,
- linked in the graph view.

> **Note:** In your vault, Archie only reads pen pages (`.excalidraw.png`) and anything inside a **Handwritten** folder. Other pictures, like reference art and screenshots, are left alone.

### Getting photos to the PC without Obsidian (LocalSend)

To send photos straight to the PC instead, use LocalSend (free, over Wi-Fi, no account):

1. Double-click **Install LocalSend.bat** on the PC.
2. In LocalSend on the PC, go to **Settings > Receive**: set **Destination** to `D:\Archie\Notes\Handwritten` and turn **Quick Save** on.
3. Install LocalSend on the other device, tap **Send**, pick the photos, then tap your PC.

## Voice notes

Record yourself, a lecture or a brainstorm. Archie types it out on your own PC, and you can fix it and save it to Obsidian.

1. Click **mic** at the bottom of the chat, or press {{Ctrl+Alt+V}} from anywhere. The button turns red and counts up: `● 1:23  stop`.
2. Talk as long as you like. Hours are fine: the recording goes straight to a file, not to memory.
3. Click it again (or {{Ctrl+Alt+V}}) to stop. Archie types it out in the background, so you can keep chatting.
4. A **Voice note** window opens with the transcript, and you can edit anything in it. Long pauses start a new paragraph.

In the Voice note window:

| Button | What it does |
|---|---|
| **title** | The note's name in Obsidian. Change it to something useful |
| **tidy up** | The main AI turns the rambling transcript into clean notes: headings and bullets, filler removed, nothing made up. {{Ctrl+Z}} brings back the word-for-word version |
| **ask archie** | Puts the text in the chat box so you can ask about it ("what should I do next?", "quiz me on this") |
| **copy** | Copies the text |
| **save → obsidian** | Saves it as a note in your vault's `Archie/Voice notes` folder, tagged `#voice-note` and linked to related notes. It then becomes **open in obsidian** |
| **put the recording in Obsidian too** | Also copies the audio into the vault and embeds a player in the note. About 2 MB per minute, so it's off by default |

- Every recording and its word-for-word text are kept in `D:\Archie\Recordings`, even if you close the window without saving. Right-click the owl > **Open Recordings folder**.
- **Speed:** with the recommended model, typing out takes roughly a quarter to a half of the recording's length. A 1-hour lecture takes about 15–30 minutes.
- **Set up once:** run **Get Voice.bat** while online. It picks the speech model: **small.en** (recommended) or **medium.en** (a bit more accurate, slower).
- Voice notes use the processor, not the graphics card, so the chat models keep the graphics card to themselves.

## Talking with Archie

Archie can talk back, offline, with a natural-sounding voice (Piper).

**Ask by voice:** press {{Ctrl+Alt+T}} anywhere, or right-click the owl > **Talk to Archie**. The **mic** button turns red (`● 0:03 send`). Say your question, then press {{Ctrl+Alt+T}} again (or click the red button). Archie types out what you said and sends it. The answer is **written** as usual. To hear it spoken too, turn on **speak ●**, or set `talk_speaks` to `true` in the settings file so voice questions always get spoken answers.

**Hear every answer:** turn on **speak ●** at the bottom. Archie reads all its answers out loud until you turn it off.

**Hear one answer:** click **read aloud** under any answer.

- **Stop talking:** click **STOP**, send a new message, turn **speak** off, or right-click the owl > **Stop talking**.
- Code isn't read out. Archie says "I've put the code on screen" instead. Headings, bullets and links are cleaned up so they sound natural.
- **Change the voice:** right-click the owl > **Archie's voice**:
  - Alan, British man (the default)
  - Ryan, American man
  - Lessac, American woman
  - Jenny, British woman
  The same menu has **Slower / Normal / Faster**.
- **Set up once:** **Get Voice.bat** (it installs voice notes and talking together).

## Study: flashcards and spaced review

**Make cards** by typing any of these:
- `make flashcards about the Krebs cycle`: a topic. With **wiki ●** on, the cards are built from offline Wikipedia.
- `make flashcards from this note`: the note open in Obsidian.
- `make flashcards from that`: Archie's last answer. `... from this chat` uses the whole conversation.
- `make 20 flashcards on crime and punishment part 1 chapter 3`: a book chapter.
- Attach a file (PDF, Word...) and type `make flashcards`.

Archie writes them like a professor would: one idea per card, mostly **why / how / what-goes-wrong / apply-it** questions, with short precise answers that include the reason. They go into a **deck** named after the source. About 12 cards by default; say a number for more.

**Study** by typing `study`, clicking **study now** in the morning brief, or right-clicking the owl > **Study flashcards** (the menu shows how many are due).

1. Read the question and think of the answer.
2. Either press {{Space}} to just see the answer, or **type your answer and press {{Enter}}**. Archie then checks it like a professor: **✓ right**, **~ partly** or **✗ not quite**, what you missed and why, and a suggested rating.
3. Rate how well you knew it: {{1}} **again** · {{2}} **hard** · {{3}} **good** · {{4}} **easy**. Each button shows when you'll see the card next.
4. **explain this deeper in the chat** switches to Professor mode and teaches that card's idea from first principles.

How the spacing works: cards you know come back later and later (1 day, 3 days, 8, three weeks, months). Cards you miss come back the same session, then tomorrow. You get up to 20 new cards a day, so reviews never pile up.

- `decks` lists your decks. `study <deck name>` studies just one.
- **delete card** removes a bad card.
- The brief and today's daily note show how many cards are due.
- Decks are plain files in `D:\Archie\Study`.

## Mock quizzes and exams

Practice under real conditions, then see exactly what to fix.

**Make one:**
- `make a mock exam on PID control` (20 questions, 30 minutes)
- `make a practice quiz on the krebs cycle` (10 questions, untimed)
- `mock midterm on crime and punishment part 1 chapters 1-5`
- `give me a practice quiz on this note` (the note open in Obsidian)
- `practice exam from my krebs cycle deck` (built from a flashcard deck)
- `make a 30 question practice test on networking, timed 45 minutes`
- `test me on subnetting` (a quick 10-question quiz)
- attach a file and type `make a mock exam on this`

For a topic, Archie builds it from **your own notes first**, then offline Wikipedia.

**What's in it:**
- **multiple choice**, with believable wrong answers, never "all of the above"
- **true/false**
- **short answer**
- on exams, **long answer** questions graded against a rubric

Questions run from recall to applying and analysing, like a real professor's exam.

**Taking it:**
- The numbered boxes at the top show where you are: **lime** = answered, **orange** = flagged. Click any box to jump there.
- Multiple choice: click an answer, or press {{A}} {{B}} {{C}} {{D}}. True/false: {{T}} or {{F}}. Archie moves on by itself.
- Written answers: type in the box. {{Ctrl+Enter}} goes to the next question.
- **flag** marks a question to come back to. **‹ prev** / **next ›** (or the arrow keys) move around.
- A **timer** counts down on exams and turns red with 2 minutes left. When time's up, the exam is handed in.
- **submit** tells you what's unanswered first. Click it again to hand it in.

**Results:**
- Your **score**, **letter grade**, points and time, plus "last time" if you've taken it before.
- **What to review:** 2–4 concepts to study next.
- **Every question:** your answer, the right one, and why. Written answers get partial credit and a line of feedback.
- **flashcards from my mistakes** turns everything you missed into a flashcard deck.
- **save → obsidian** saves the exam and your results to `Archie/Mock exams`.
- **retake** gives the same questions with the answer order shuffled.

Type `exams` to see your past mock exams and retake one.

## Opening apps and making files

**Open things:** `open blender`, `launch unity`, `open vs code`, `open my notes folder`, `open downloads`. This works by voice too, with {{Ctrl+Alt+T}}.
- Archie looks through your **Start menu** every time, so apps you install later (Blender, Maya, Unity...) work the moment they're installed, with nothing to set up.
- It only opens things that are really in your Start menu or your own folders. If it can't find something, it says so and suggests close matches.
- Folders it knows: notes, vault, downloads, documents, desktop, pictures, recordings, screenshots, flashcards, audiobooks, voice inbox.

**Make files:** `make a godot script called player.gd that moves with WASD`, `create EnemyAI.cs for unity that patrols between points`, `write a python script that renames my screenshots by date`, `make an arduino sketch for a servo sweep`.
1. Archie writes it (with the **Coder** model for code).
2. A **NEW FILE** window shows it. Nothing is saved yet: edit anything, rename it, or **change** the folder.
3. Click **save** or **save & open**. If a file with that name already exists, Archie warns you, and it's only replaced if you click again.

New files go to `Documents\Archie Files` until you pick another folder. Archie remembers the last one you used, so point it at your Godot or Unity project once.

## Walk-and-talk voice notes from your phone

Record on your phone (headphone mic is fine) while you walk, and it turns up in Obsidian typed out and tidied.

**With Obsidian on your phone (recommended):**
1. Install Obsidian on the phone and open your vault with **Obsidian Sync** (or another sync).
2. The **Audio recorder** core plugin is already on in your vault. On the phone, tap the **microphone** in the ribbon (or run "Audio recorder: Start recording") and talk. Tap again to stop.
3. When it syncs to the PC, Archie types it out within a minute or two and saves `Recording ... (transcribed).md` right next to it:
   - tidied notes at the top,
   - the word-for-word text folded underneath,
   - the recording embedded,
   - tagged `#voice-note`.

**Without Obsidian on the phone:** send any recording (voice memo app, LocalSend...) into `D:\Archie\Notes\Voice inbox`, or a **Voice inbox** folder in your vault. The note lands in Obsidian under `Archie/Voice notes`.

- Turn tidying off with `"phone_tidy": false` in the settings file (you then get just the word-for-word text).
- Works with m4a, webm, mp3, wav, ogg and more.

## Lectures (class capture)

Record a class on your phone, and by the time you're home it's a full set of notes in Obsidian, laid out like a Plaud summary.

**Record it:** in Obsidian on your phone, tap the **microphone** (the Audio recorder) at the start of class and again at the end. That's all. It syncs to the PC like any voice note.

**Archie treats a recording as a lecture when:**
- it was made during a **class on your calendar** (add classes once, like `class: intro to animation mondays 6pm`), or
- it's in a folder called **Lectures** (in your vault, or `D:\Archie\Notes\Lectures`; a subfolder like `Lectures\Game Design` names the class), or
- it's **longer than 30 minutes**.

Shorter recordings outside class stay ordinary [voice notes](#walk-and-talk-voice-notes-from-your-phone).

**The note** lands in your vault under `Lectures/<class>/<date> <title>.md`:
1. **Title** Archie picks, with the class, day, time and length, and the recording to play.
2. **Summary:** what the lecture covered, in a few sentences.
3. **Key points**, each with the time it was said (like `12:04`), so you can scrub the recording to it.
4. **Notes** by topic, in order, with times.
5. **Terms** the lecturer defined, in a table.
6. **To-dos:** homework, readings and due dates, with the date worked out from the day of class ("due Friday" becomes that Friday). They're also **added to Archie's to-do list** with the class name, so they show up in your morning brief.
7. **Questions to review:** good self-test questions (try `make flashcards from this note` with it open).
8. **Mind map** of the lecture: a quick picture right in the note, plus a link to the same map as its own note, `<date> <title> (mind map).md`, which opens in the **Mindmap** plugin as an editable map you can drag, collapse and add to.
9. **Transcript:** everything, word for word with times, folded away until you click it.

Typing out and sorting an hour-long lecture takes a few minutes on your graphics card. Type `lectures` to open the Lectures folder.

**Ready when you get home (wake after class):**
Right-click the owl > **Lectures** > **Wake the PC after class** (or type `wake after class on`). For every weekly class on your calendar, Windows wakes the PC about 20 minutes after class ends (and again 30 minutes later, in case the phone was slow to sync). Archie opens Obsidian so it syncs, types up the lecture, then puts the PC **back to sleep**, but only if nobody has touched the keyboard or mouse for 10 minutes.
- **Once, in Windows:** Control Panel > Power Options > Change plan settings > Change advanced power settings > **Sleep > Allow wake timers > Enable**. Without it, Windows ignores the wake-ups.
- The PC has to be **asleep**, not shut down, and you stay signed in.
- Classes are assumed to run 75 minutes. Change `lecture_minutes` in the settings file if yours are longer.
- Don't want it to sleep again? Untick **Sleep again when the note is done** in the same menu.
- Turn it off: `wake after class off`. The wake-ups follow your calendar by themselves when you add or remove classes.

> **Note:** Check the syllabus or ask the professor before recording a class. Most are fine with it, but some schools and classes have their own rules.

## Audiobooks

1. Put an audiobook in `D:\Archie\Notes\Audiobooks` (owl menu > **Open Audiobooks folder**):
   - **a folder of files**, one per chapter (`Crime and Punishment\01.mp3, 02.mp3...`), or
   - **one file** (`.m4b`, `.mp3`, `.m4a`). Chapter marks inside the file are used. Without them, it's cut into 30-minute parts.
2. Archie types it out **in the background**, chapter by chapter. A whole book takes hours. It pauses while you're using Archie, picks up where it left off (even after a restart), and you can pause it from the owl menu (**Pause audiobooks**).
3. As chapters finish, the book appears as `Notes\Books\<title> (audiobook).txt`. Then `quiz me on <title> chapter 3` and `make flashcards on <title> chapter 3` work like any book.

- Type `audiobooks` to see progress.
- **Audible `.aax` files are copy-protected** and can't be read. DRM-free MP3/M4B audiobooks work: LibriVox (free public-domain classics, including Crime and Punishment and War and Peace), Libro.fm and Downpour.
- To make it faster, set `"audiobook_model": "small.en"` in the settings file (download small.en with **Get Voice.bat**, option 1). Narration is clear, so small.en does well.

## Drawing gym

Timed reference practice, like a figure-drawing class: a picture comes up, you draw it before the time runs out, and the next one appears.

**Open it:** type `gym` (or `drawing gym`), or right-click the owl > **Drawing gym**.

**Your pictures:** drop reference photos into `D:\Archie\Drawing Gym` (**open folder** in the gym takes you there). Archie looks at each new one with the Vision model and sorts it by itself: **figure**, **faces**, **hands & feet**, **animals**, **landscapes**, **places** (streets, buildings, rooms), **objects**, **vehicles & mechs**, or **other**. To choose yourself, put pictures in a subfolder named after the category, like `Drawing Gym\hands`. If Archie guessed wrong, right-click the picture during a session > **This picture is really...**

**Before you start, pick:**
- **What to draw:** one or more categories, or **all**. The numbers show how many pictures each has.
- **Time per picture:** 30 s, 1 min, 2 min, 5 min, 10 min, or **no timer** (take as long as you like and press next). **Class ladder** is the classic warm-up: 8 × 30 s, 4 × 1 min, 2 × 2 min, 2 × 5 min.
- **How many:** 5, 10, 20 or all.

A peek at the pictures in your set shows underneath. Click **start**.

**During a session:** the time counts down in the corner with a lime bar under the picture; it turns lime for the last 5 seconds, then the next picture comes up.
- **pause** (Space, or double-click the picture), **next →** (→), **←** back (←).
- **mirror** (M) flips the picture: a quick way to spot mistakes in your drawing. **gray** (G) shows it in black and white so you can see the values.
- **end** (Esc) stops early. Pictures you spent real time on still count.

**Afterwards:** how many pictures you drew and for how long, your **streak** (days in a row), this week's total, and **again** for another round. Each session also goes in today's daily note, and the log is kept in `Memory\gym_log.json`.

## Focus timer (the owl)

A Pomodoro timer: 25 minutes of focus, then a 5 minute break. Every 4th break is 15 minutes.

**Open it:** click **focus** next to the date at the top of Archie, type `focus`, or right-click the owl > **Focus timer**. Type `focus: network+ subnetting` to open it and start right away.

**How it looks:**
- **Focus:** the owl's wings unfold feather by feather as the session goes. Fully open = done. The wings slowly brighten and dim, and once a minute a pulse runs from the body out along the feathers.
- **Break (5 or 15):** the wings open the same way. Take the tips: stand, water, look far away.
- **Not running** (before you start, or paused): the owl sleeps, eyes closed with z's. While any timer runs its eyes are open and it blinks now and then.
- **Done:** wings fully open. Write what you got done and click **save + start break**. It goes in today's daily note (under Log), and the break starts.

**The buttons:**
- **start / pause** (or press Enter in the "working on" box), **+5 min**, **reset**.
- **focus 25 · short break 5 · long break 15** pick the kind of session.
- **The corner arrow** (top right, or Esc) hides the timer **and** the chat. The owl on your desktop spreads its wings and shows the time left. Click it to open the timer again.
- **✕** closes the timer window; it keeps running, and the time shows next to the date.
- On the done screen: **skip log** (counts it, but nothing goes in the daily note) and **flashcards** (saves it and makes flashcards from what you wrote).

**When time's up,** the timer pops up on screen with a sound, even if it was hidden.

Every finished session is also kept in `Study\focus_log.jsonl` (for a weekly report later).

## Where I left off

When a focus session ends, the done screen has a box: **where you stopped · what's next**. Write something like `stopped at panel 12, the jump reads flat. next: fight beat, panels 13-18` (or say it with the mic).
- The next time you start the same thing (the **working on** box), a **last time** card shows it, with how long ago and how long you worked. **recent:** under it lists your last few projects: click one to fill it in.
- The morning brief shows **pick up where you left off** for the last couple of days, each with **resume**, which opens the owl and starts it.
- Archie's answers know it too, so "what should I do tonight?" can start from where you actually are.

Kept in `Memory\left_off.json`.

## This week

Once a week Archie sums up your week so it can keep it in mind: what you're working on, what's stalling, what's on your mind, and what's coming up, plus where your hours went. It reads your focus sessions (and where you left off), recaps, drawing gym, lectures and chat titles. Nothing leaves your PC.

- **When:** on Sunday and Monday the brief offers **look over my week**. Any time: type `this week`, or right-click the owl > **This week**.
- **You decide what stays:** every line has a box. Click to untick anything that's wrong or private, then **keep these**. Only the lines you keep go into Archie's answers, and only for about 10 days.
- It's also saved in Obsidian as `Archie/This week.md`. **redo** writes it again.

## Patterns

Type `patterns` (or right-click the owl > **Patterns**) after a couple of weeks of focus sessions:
- **When you actually get deep work done:** a map of the week, hour by hour, brighter where you focused more.
- **Hours per project, week by week,** with anything that's stopped moving marked **slipping**.
- **What I'd suggest:** your best hours, your strongest and lightest days, what's slipping, and when the drawing gym sticks.

The morning brief adds one line from it (like "Tuesdays you average 2 focus sessions; your best hours are 7pm–10pm") with **see patterns**, and the calendar's week view glows in your best hours.

## Evening recap

Talk for a minute or two about your day. Archie types it out on your PC and turns it into tomorrow's plan.

**Start it:** click **recap** (the moon) next to the timer at the top, type `recap`, press **Ctrl+Alt+R**, or right-click the owl > **Evening recap**. After 7 pm the moon gets a small lime dot until you've done one.

**The stages:**
1. **Recording:** a waveform and the time. Some things to talk about (what you got done, what's still hanging, tomorrow, anything on your mind); click one to cross it off. **pause**, **cancel**, or **done, wrap it up** (or Ctrl+Alt+R again).
2. **Typing it out and sorting it:** about a minute. You can close the window; it pops back up when it's ready.
3. **Review:** Archie sorts what you said into **today**, **tomorrow** and **on your mind**. Edit any line. Checked tomorrow items go on your to-do list, with the day you said (or tomorrow). **full transcript** and **play it back** are there too. Click **save to tomorrow + daily note**.
4. **Next morning:** the brief opens with **from last night's recap**: a one-line summary, what was on your mind (with **make a plan for that**), and a link to the recap note. The tasks are in today's list.

Where it goes: a note in Obsidian (`Archie/Recaps`), a link in today's daily note, the recording and text in `Recordings`, and `Recaps\<date>.json` for the brief.

When the chat is narrow, the timer and recap buttons shrink to icons (the timer still shows the time while it runs).

## Calendar

Click the **date** at the top of Archie (or type `calendar`, or right-click the owl > **Calendar**).

- **Month view.** Today has a lime ring. Short colored bars show what's on each day, and each day **glows lime** by how much you focused (focus timer and drawing gym). Use **‹ ›** or the mouse wheel to change month, and **today** to jump back.
- **Click a day** to see its events, plus that day's recorded lectures (click one to open the note), focus sessions and drawing gym. Remove an event with **✕**.
- **Week view** (the **week** button at the top; Archie remembers which you like): the week hour by hour, 8 am to 11 pm.
  - Classes are blocks. After class they say **■ recorded · ✓ note** with a violet edge when the lecture note is there, **record it** before class, and **no recording** if one never came in.
  - Focus sessions you did are solid lime blocks and drawing gym rounds white pills.
  - Due dates sit at the top of the day, with a pink line at the time they're due.
  - Your best hours (from [patterns](#patterns)) glow faintly lime, so you can see where the hard work fits.
  - A white line marks right now. Things at the same time sit side by side. **‹ ›** moves a week; click a day to add to it.
- **Colors** (each is a different brightness too, so they're easy to tell apart): **blue** lecture · **violet** recorded, with a note · **pink** homework due · **red** exam · **orange** test · **amber** quiz · **teal** lab · **lime** focus · **white** drawing gym · **grey** anything else.
- **Add** at the bottom: pick a kind (**exam · test · quiz · due · lab · class · event**), type what it is (a time in the text like `9am` or `2:30pm` is picked up), tick **weekly** for classes, then **add** (or {{Enter}}).

**Or just type it in the chat:**

| Type | Adds |
|---|---|
| `exam: bio midterm oct 12 9am` | an exam on Oct 12 at 9am |
| `lab: chem titration friday 2pm` | a lab this Friday |
| `due: history essay 11/3` | a due date |
| `class: intro to animation mondays 6pm` | a class **every** Monday |
| `add dentist appointment on oct 3 at 3:15pm to my calendar` | an event |

Dates Archie understands: `oct 12`, `12th of october`, `10/12`, `2026-10-12`, `today`, `tomorrow`, `friday`, `next tuesday`, `in 3 days`.

**Where it shows up:**
- **Morning brief:** a **coming up** list: the next 7 days, plus exams, tests and due dates up to 6 weeks out.
- **Today's daily note:** a **Coming up** section.
- **Archie's answers:** it knows your schedule, so "when's my bio exam?", "what do I have this week?" and "make me a study plan for my midterm" work.

Events are saved in `D:\Archie\calendar.json`.

## Making images (offline)

Type things like:
- `draw a ruined desert city at dusk, concept art`
- `make an image of a scavenger girl character design`
- `generate 4 pictures of a floating island level`

Right-click the owl > **Make an image...** also opens it.

1. Archie turns your words into a detailed prompt for the image model, picks a good shape, and starts painting. The **IMAGINE** window shows the prompt: edit it any time and click **generate again**.
2. **avoid** lists things to keep out. The chips pick the **shape** (square / wide / tall), **how many** (1, 2, 4) and **quality** (fast / good).
3. **Click a picture** for:
   - **Open full size**
   - **Save to Obsidian** (goes in `Archie/Images` with a note holding the prompt)
   - **More like this**
   - **Ask Archie about it** (attaches it to the chat)
   - **Show in folder**

- It runs **on your RTX 2080**, with no internet and no datacenter. Model: Stable Diffusion XL. Every picture is saved in `D:\Archie\Images\<date>`, with its prompt stored inside the file.
- **Speed:** the first picture takes longer (the model loads, about 30 s). After that, roughly 30–60 seconds per picture on "good".
- While painting, Archie frees the graphics card by unloading the chat model. The next chat message takes a few seconds longer while it loads back.
- The image helper runs separately and closes itself after 10 idle minutes to give your memory back.
- `image: <exact prompt>` skips the prompt-writing step and uses your words as-is.
- **Set up once:** quit Archie and run **Get Image Maker.bat**, while online. It installs PyTorch for NVIDIA (about 2.5 GB, on C:) and the SDXL model (about 7 GB, on D:).

### Sketch to image

Turn your own drawings into finished pictures: fight scenes, environments, character designs. Archie keeps your layout and poses and paints the rest.

**Open it:** type `sketch`, click **from a sketch** in the Imagine window, or right-click the owl > **Sketch to image...**. You can also attach a drawing in the chat and type something like `turn this sketch into concept art`.

1. **Bring in the drawing:** drop a file on the window, **choose a file**, **paste** (Ctrl+V), **snip the screen**, or click one of your recent sketches (from `Excalidraw/` and `Handwritten/` in your vault). Photos of paper work: Archie evens out shadows and picks out your lines.
2. **Archie reads it** with the vision model, says what it sees, and starts a description. Change anything.
3. **Follow my lines:**
   - **loose:** your sketch is a rough layout; Archie invents more. Good for environments and mood.
   - **balanced:** keeps your composition and poses. Start here.
   - **strict:** stays right on your lines, like inking and coloring them. Best for character designs.
4. **Style:** 20 looks, including concept art, cinematic still, anime, cel-shaded game art, comic book, graphic novel noir, painterly, oil painting, watercolor, ink and wash, charcoal, storyboard, character sheet, matte painting, dark fantasy, sci-fi, 3D render, low poly, pixel art, and clay / stop motion. Each one says what it looks like when you click it.
5. **Shape** is picked from your drawing (change it if you like), plus **how many** (1, 2 or 4). Click **generate**.
6. **Results** appear beside your sketch. Click one for **open full size**, **more like this one**, **ask Archie about it** and **save to Obsidian**. **show my lines on top** lays your drawing over the results so you can see how closely they followed it. **try strict / try loose** repaints with the other setting.

Pencil smudges and specks of paper grain are cleaned out of your lines before painting, so they don't turn into glowing dots in the picture.

Tips: for fight scenes, draw bodies as simple shapes (circle head, box chest), keep the figures from overlapping too much, and make weapons clear lines. Hands and faces may need a second try.

**Set up once:** after Get Image Maker.bat, quit Archie and run **Get Sketch Model.bat** (online, a few hundred MB). It adds the sketch reader (T2I-Adapter) that lets the image model follow your lines. It shares the image model already on your drive.

## Snipping the screen

1. Press {{Ctrl+Alt+S}} anywhere, or click **snip**.
2. The screen dims. **Drag a box** around what you want.
3. The picture is attached to the chat. Ask your question and send.

{{Esc}} or a right-click cancels. Every snip is saved in `D:\Archie\Screenshots` (safe to empty anytime).

## Notes: Archie's memory for your stuff

Turn on **notes ●** and Archie searches, before answering:

- the **Notes** folder (`D:\Archie\Notes`, sub-folders are fine),
- **your past chats** with Archie,
- your **Obsidian vault**.

It uses the best matching passages and tells you where they came from (`src:`), like "from biology-notes.pdf" or "our chat on Sep 26".

- Open the folder: right-click the owl > **Open Notes folder**.
- The first read of a big folder or vault takes a few minutes. After that, only new or changed files are read.
- Force a re-read: right-click the owl > **Re-read notes now**.
- You can turn notes on halfway through a chat and ask "what did we figure out about the servo last week?"

> **Note:** Notes search needs the `nomic-embed-text` model (from **Install Extras.bat**).

## Workshop: code with Archie

Right-click the owl › **Workshop (code with Archie)**, or type `workshop` in the chat. It opens in its own window. Everything runs on this PC: the coding model (qwen2.5-coder 7B) in Ollama, and your programs in their project folder.

- **New project:** describe what you want in your own words, pick a language, and choose how to build it:
  - **Teach me to build it:** Archie plans the project as 3 to 8 small lessons. Each one explains one idea in plain words with a tiny example, then gives you a task. You write the code (in VSCodium or any editor) and save. Press **check my work**: Archie runs your program, reads what happened, and tells you how it went. If it's not there yet you get a nudge, not the answer; **hint** gives another nudge, and **show me** shows the code for just that step with each line explained. When a step passes, what you learned goes into your flashcards (a deck called "Coding - Python", and so on). **◂ back** and **skip ▸** move between steps.
  - **Build it for me:** Archie writes the files, runs them, and if there's an error it reads it and fixes it (up to 3 tries). Each change shows as a before-and-after (red taken out, green put in), and **undo** puts the last change back. Ask for changes in plain words ("make the second hand red").
  - **Or work on a folder you already have:** link any folder and Archie watches it, checks your code and explains it.
- **Watching saves:** every time you save, Archie's **checkers** look at the file: the real tools, not the AI's guess. Python gets its parser plus **ruff** (undefined names, unused imports, likely bugs); JavaScript gets `node --check`; HTML is checked for tags left open, duplicate ids, missing files and the script inside it; CSS and JSON for broken brackets; C and C++ go through the compiler with warnings on; Java through `javac`. C#, Arduino and Godot are slower to check, so they're checked when you press **check all files** or when Archie builds. Errors show on the right with the exact line, and Archie explains them in plain words; warnings (things worth a look that won't stop the program) are listed with the save. In VSCodium they also appear as squiggly lines and in the Problems panel. If the top bar says **get the Python checker**, click it once while online to install ruff.
- **Check all files:** runs every checker on the whole project and lists what they find.
- **Delete:** a project's **delete** button moves it to the **trash** (link at the bottom left), where **restore** puts it back exactly as it was; **empty the trash** is the only permanent delete. For a folder you linked, delete only stops watching it: your folder stays where it is. Courses have their own delete (your progress goes to the trash with it), and blocks you saved yourself can be deleted from the library.
- **new lesson plan:** clears a lesson project's steps (your code stays), lets you change what the project is, and plans fresh lessons.
- When Archie builds something, it runs the checkers too, and an error from them sends it back to fix the code, the same as a crash would.
- **Run:** runs the project's main file. Python, JavaScript (Node), Java, C and C++ run here; programs with a window or a loop keep running until you close them or press **stop**. Web pages open in a **preview** right in the Workshop. Godot scripts run in Godot; Arduino sketches compile here and upload from the Arduino tools.
- **Files:** click one to read it with line numbers, **explain this file**, or open it in VSCodium.
- **Ask:** the box at the bottom right asks Archie about the project. If you're in VSCodium, it knows the file and line you're on.
- Projects live in `D:\Archie\Workshop`, one folder each.
- **C# offline:** C# projects get a small `nuget.config` that stops `dotnet` reaching for the internet on every build (it does that even when the project uses no packages). Remove its `<clear />` line if you add NuGet packages.

### The library: blocks and whole apps

**library** (under + new project) holds tested building blocks that snap together, and whole apps made from them. Everything works offline.

- **Blocks** come in kinds: **shells** (the skeleton of an app: a command-line tool, a window app, a local web app, a 2D game, a web page, an offline phone app, an Arduino sketch, C, C++, Java and C# programs), **features** (save data, a database, forms with checks, search, charts, printable reports, spreadsheet import/export, backups, two languages with Swahili, a PIN lock, reminders, local AI, bigger text and high contrast, read aloud), **hardware** (soil moisture, ultrasonic distance and tank level, relays for pumps and valves with a safety limit, buttons, buzzer alarms, light, 12 V battery monitor, temperature and humidity) and **toolkit** (logs and crash reports, timers without delay, CSV over USB).
- Each block has a card (what it does, the parts it needs), its code, a version with a changelog, and a **test**. **test on this PC** runs it here and says whether it works on this computer.
- **Whole apps (recipes)** are a shell plus blocks plus the code that wires them together: Farm log, Clinic medicine stock, Class attendance, Savings group ledger (chama), Water tank alarm, Soil-moisture irrigation, Desk clock with reminders, and Stock and records. **start a project from this** gives you the whole working app as a new project to change however you like. Each lists who it's for, a cheap option, and the parts.
- In a project, **add to <project>** puts a block's files in and adds its import lines where the app's marker is (`# archie:imports`, `<!-- archie:scripts -->`, `// archie:includes`), so it's ready to use. The project's **blocks** panel shows which versions it uses. **check for updates** shows what changed in newer versions; each update is tested on this PC first, it won't replace block files you've changed unless you say so, and **undo** puts the old version back.
- **save part of this as a block:** pick files from your project, name it and say what it does, and it joins your library (marked "yours") for any future project. Saving again makes a new version.
- When Archie builds something, it looks for blocks that fit the request and starts from their tested code instead of writing that part from scratch.
- When you describe a new project, matching whole apps appear under the form, so you can start from one.
- **HOW IT WORKS:** projects made from the library open with a guide: what the app does in plain words, the parts, a wiring table for hardware (which wire to which pin), and the files in the order to read them. Click a file to read it with notes on the lines that matter (why the pump has a safety limit, why the timer isn't delay(), and so on).
- **teach me to build it:** the Farm log, Soil-moisture irrigation, Water tank alarm and Desk clock can also be started as lessons: the blocks are given, and you write the main file yourself in 4 to 6 steps written ahead of time (each says what you should see working, and **show me** gives the tested code for that step). A step passes when it runs and has every piece it needs.
- **Arduino without board support:** until you press **get Arduino board support** once while online, Archie checks sketches with its own practice Arduino, so lessons work offline; uploading to a real board needs the board support.

### Looking things up (the offline docs)

Before Archie answers a question, gives a hint, checks your step, explains an error or fixes a build, it searches the programming docs and Q&A in your vault (**D:\Archie\Vault**) and reads the part that matters. Under its answer, **LOOKED UP** lists the pages it used. Click one to read it in the docs panel, scrolled to the section Archie read. Nothing goes online.

- **What it searches, by language:** Python (the Python docs, plus pygame, NumPy, pandas, Matplotlib, Flask and the rest when your code uses them), Web (HTML, CSS, JavaScript, DOM), Node.js, Java, C, C++, Godot (the Godot docs and Game Development Q&A), Arduino (Arduino, Electronics and IoT Q&A), and **Stack Overflow** for all of them. For C# there are no official docs in the vault yet, so it uses Stack Overflow.
- **Q&A pages** show the question and the best answer (the accepted one first, then the most votes), with the vote count next to the link.
- **The docs chip** at the top right opens the panel. Its search box searches the docs directly, with no AI and instantly: type a function name or an error message.
- **look things up first** (the switch in the panel) turns it off if you ever want plain answers.
- If a doc file **didn't finish downloading**, the panel says which; run **Get Vault.bat** again and it picks up where it stopped. Until then Archie leaves those files out.
- If a very big file (Stack Overflow is about 115 GB) is slow to search on your drive, Archie leaves it out of answers for 10 minutes rather than make you wait. The panel's search box still uses it.

### Courses

**courses** (under + new project) are full courses, built the way Harvard's CS50 and MIT's open courses are. Six are ready, each with Levels 1 and 2 (Python also has Level 0); Levels 3 to 7 are planned for each, up to algorithms, systems and a capstone you defend:

| Course | Level 1 | Level 2 | Level 2 ends with | Good for |
|---|---|---|---|---|
| **Python** | 15 units (with Level 0) | 9: classes, special methods, properties, inheritance, dataclasses and enums, modules, files/CSV/JSON, testing your own code | a clinic medicine stock system with save/load and your own tests | first language, data, Archie itself |
| **Java** | 12 | 10: classes, equals/hashCode, interfaces, inheritance, polymorphism, generics, comparators, enums/records/exceptions, testing | a game inventory | AP Computer Science, university courses, Android |
| **Web (HTML, CSS, JavaScript)** | 12 | 9: building elements, events, forms and validation, lists that change, array methods, saving in the browser, JSON and fetch, organising an app | a savings-group (chama) tracker | pages and apps that work on any phone |
| **C#** | 12 | 10: classes and properties, interfaces, inheritance, pattern matching, generics, delegates and events, LINQ, records and exceptions, testing | a wave-defence battle system | Unity games, Windows apps |
| **C++** | 11 | 9: addresses, pointers and arrays, new/delete, destructors and RAII, unique_ptr, shared_ptr and weak_ptr, copying, linked structures | a projectile manager with no leaks | Unreal, games, robotics |
| **C** | 11 | 9: pointers, pointer arithmetic, malloc/free, growing arrays, heap strings, heap structs, linked lists, stacks and ring buffers | a sensor-log tool that frees everything | Arduino and electronics, how computers really work |

Level 2 opens when you've mastered Level 1 (or tested out of it). In Level 2 you also learn to **test your own code**: some exercises are graded by running *your* tests against working code (they must pass) and against broken versions (they must catch the bugs). The memory units in C and C++ check for leaks with an allocation counter that has to end at zero.

**Learn them in any order, or several at once.** Each course has its own project (**Course-Python**, **Course-Java**, **Course-Web**, **Course-CSharp**, **Course-Cpp**, **Course-C**) and its own progress. The courses share the same ideas (variables, decisions, loops, lists, functions, classes...), so:

- A unit whose idea you've already mastered in another course shows **you know this from Python** (or whichever), and starts with a short **bridge**: what's the same and what's different in this language.
- **test out:** take the quiz and do the last exercise yourself; 85% counts the unit as mastered, so you skip what you already know.
- **compare** shows the same idea side by side in the languages you're learning.

- Each **unit** has a lesson, a worked example you can run and break, a **problem set** graded by real tests (some hidden, like a real problem set), a quiz, and **explain it back** (you teach the idea in your own words and Archie grades the explanation).
- Your work goes in the course's project, one folder per unit, so you write it in VSCodium and press **Ctrl+Alt+K** to run the tests, or press **check** in the Workshop. Failed tests say what was expected and what your program did.
- **hint** gives the written hints one at a time, then Archie's own. **why did it fail?** has Archie read your code and the failed tests and explain, like a teaching assistant, without writing the fix. **show a solution** only appears after 3 tries, and an exercise you looked up counts half.
- **Mastery:** a unit counts as mastered at 85% (exercises plus the quiz), and the next unit opens. Mastered units add their flashcards to Study (a deck per course, e.g. "Course - Java"), and new units start with a **warm-up** from an older one so it stays fresh. The **skills map** shows how strong you are in each skill.
- Each language is graded by its real tools: Python, Java (javac), C and C++ (gcc and g++), C# (.NET), JavaScript (node), and web pages by Archie's page checker. C# needs .NET and Java needs a JDK; **Get Code Editor.bat** can add them.
- Every course is written ahead of time and every exercise's tests are checked against a working answer (and checked to fail on the starting code). The AI helps (hints, explanations, grading your explanations); it never makes up the curriculum.

### Project memory (big projects)

Small projects are shown to Archie whole. When a project is bigger than Archie can read at once (about 24,000 characters), project memory takes over:

- Archie keeps an index of the project (in the project's hidden `.archie` folder): each file cut into pieces (a function, a class, or about 60 lines), matched by meaning with the same model notes search uses (`nomic-embed-text`), or by keywords if that model isn't installed. Only files that changed are re-read.
- For each request it reads a **map** of every file with its functions and classes, plus the files that matter most **in full**: ones that match the request, the entry file, files named in your request or in an error, and files you changed recently.
- **Archie only changes files it read in full.** If it tries to change one it only saw on the map, it leaves it alone and tells you; name the file in your request and it reads it in full next time.
- The project's header says **project memory: N files indexed** when it's in use.

### Dev coach

**dev coach** (under the projects list) keeps a dev log for each game you're making, in any engine: Godot, Unity, Unreal or anything else. Tell it what you're working on or testing ("players say the corner turrets never fire") and it answers in the same shape every time:

- **What's probably going on** · **The design idea** (coverage, chokepoints, readability, pacing, cost curves...) · **Next steps** · **How to do it in your engine** (GDScript for Godot, C# for Unity, Blueprint or C++ for Unreal) · **Try this** (one change and what to measure) · **The concept** (the reusable lesson).
- It **remembers each game**: design notes, decisions (with why), what you tried and how it went, and open questions. It only files what *you* said or decided, never its own suggestions, and the **What Archie remembers** panel lets you add, fix or forget anything.
- It looks things up first in the offline docs (Godot docs, Game Development Q&A, Stack Overflow) and shows the pages under **LOOKED UP**.
- **Godot or Unity:** link the project folder and the coach reads the scripts that matter for your question. It never changes them, and its index is kept with the dev log, not in your project.
- **Unreal stays hands-off:** advice only; it never reads or touches your Unreal project. The 7B model isn't always sure of exact UE5 functions, so it says when it's unsure.
- Design talk uses Archie's main model; a deleted dev log goes to the Workshop's trash and can be restored.

### VSCodium and Archie Coach

**Get Code Editor.bat** (in the Archie folder) sets up a full code editor, offline:

- **VSCodium:** the open-source build of VS Code, without Microsoft's tracking.
- **Continue:** AI chat (Ctrl+L), "edit this" and autocomplete inside the editor, using Archie's own models through Ollama. Nothing goes online; its telemetry is switched off.
- **Archie Coach:** Archie's own add-on. It tells the Workshop which file and line you're on, and adds **Archie: explain this** (Ctrl+Alt+E), **Archie: check my step** (Ctrl+Alt+K) and **Archie: give me a hint** to the right-click menu. Answers show in the "Archie" panel at the bottom. When Archie spots an error, its note appears right on that line in the editor, and what the checkers find shows as squiggly lines and in the Problems panel (marked "Archie"). In a course, Ctrl+Alt+K runs the exercise's tests. After an update, run **Update Archie Coach.bat** once. The eye at the bottom right turns it on and off; when it's off, Archie isn't watching.
- **More languages**, if you want them (it asks for each): Node.js, Java, C and C++, C# (.NET), Godot, Arduino. After installing, restart Archie so the Workshop finds them.

**What to expect:** the 7B coding model is good at single files and small projects, and the run-check-fix loop catches most of its mistakes. Big projects with many files are past what it can hold in its head at once. A graphics card with more memory would let it run a bigger, much better model (see the ideas list).

## Archie World (the globe)

A live globe of what's happening in the world, when you're online: conflict reports from both sides, disasters, weather, pipelines, shipping straits and markets. It's not about you, just the world. Open it with `world` (or right-click the owl > **Archie World**). It opens in its own window (Edge's app mode, no tabs or address bar).

**What's on it**
- **Conflict:** countries shaded by how many military reports came in this week; warning triangles for hotspots; front lines and occupied areas (from DeepState, when it answers). Zoom in, or pick a region tab (**Ukraine, Sudan, Middle East, Iran, United States, Germany**), and the triangles turn into liveuamap-style icons: clashes, shelling, drones, missiles, alerts, protests, politics, aid, and **defense** (an olive shield: military news that isn't fighting, like defense budgets, arms deals, exercises and NATO). Defense news doesn't count toward the war shading.
- **On-the-ground reports:** public Telegram channels and local papers in their own language (Ukrainian, Russian, Arabic, Persian, Hebrew, German), translated on your PC, plus world outlets. Every report shows how long ago, who reported it, which side they speak for, and the language it came from. A report stays **unconfirmed** until a second, separate source says the same thing.
- **Disasters:** earthquakes from the last 24 hours (USGS; drag the time slider back to see older ones), cyclones, floods, volcanoes and wildfires (GDACS, Smithsonian), and the **weather radar** (RainViewer, the last two hours).
- **Storms:** each tropical storm, hurricane or typhoon shows the weather-map storm symbol, colored by strength (depression, tropical storm, category 1 to 5), with its name. A solid line shows where it has been, white dashes where it's forecast to go, and a faint outline the **cone** (the center could end up anywhere inside it). Click it for its winds, which way it's moving, its pressure, each forecast point with the expected wind and the nearest city, and a chart of its wind along the path. **Show its whole path** zooms out to fit it. Storms move forward when forecasters publish a new position (every 3 to 6 hours), not smoothly. Data: the US National Hurricane Center for the Atlantic and eastern Pacific, GDACS everywhere else.
- **Space station:** a little ISS moves along its real orbit, with the last 45 minutes as a line and the next lap dashed. Click it for where it is, how high and how fast; **follow it** keeps the globe on it (for up to 10 minutes, or until you drag). Its position is worked out on your PC from orbit data Archie downloads twice a day, so it keeps working briefly offline. Turn it off under **Space** in the layers.
- **Satellites:** under **Space** in the layers, switch on any of: **other space stations** (China's Tiangong and visiting craft), **brightest** (the ~150 you can spot by eye at dusk and dawn), **science** (Hubble and co.), **weather satellites**, **GPS**, and **Starlink** (thousands; 3D globe only, the heaviest). They're off until you switch them on, and Archie remembers your choice. They move along their real orbits (updated every few seconds, and not at all while the globe is paused). Hover one for its name; click it for where it is, how high and fast, **who it belongs to** (country, the company or agency that runs it, when and where it was launched, whether it still works), what kind of orbit it's in, and its next lap drawn on the globe. Heights are squashed so the far-out GPS and weather satellites still fit on screen. Lists come from CelesTrak once a day.
- **Trade & energy:** 26 main oil and gas pipelines with the direction they flow and their status (flowing, reduced, disrupted, offline), 18 chokepoints and straits with ships per day and the mix of ship types (IMF PortWatch), 25 stock exchanges (open or closed right now, the day's move) and 14 central banks.
- **Mines:** 45 of the world's most important mines, each marked with a pickaxe colored by what it produces (copper, cobalt, gold, lithium, rare earths, uranium, iron ore and more). **Artisanal** sites (dug by hand, often informally, like the cobalt diggers of Kolwezi, the coltan pits of Rubaya held by M23, Ghana's galamsey gold, Darfur's gold that funds Sudan's war, Myanmar's jade and rare earths) have a dashed ring. Click one for who runs it, what it produces, its rough share of world supply, a short bio, **why markets care**, live prices for the metals and companies it moves, and any news about it. Star it to get an alert if it's in headlines about a halt or accident. The list is in `World\web\places.js` if you want to add mines.
- **Antarctica:** 45 research stations with their country, who runs them, when they opened, whether they're staffed all year, and a note on each. Click one for the **weather there right now** (from Open-Meteo), the local time, whether it's polar night or midnight sun, and a link to the station's webcam where there is one (McMurdo, the South Pole, Palmer, Casey, Davis, Mawson). Crews and daily station logs aren't published live, so the weather and webcams are the live part.
- **Countries:** click any country for its facts (REST Countries), its borders, the markets tied to it, what's happening on the ground there and its latest articles.
- **Zoomed in:** street-level map tiles (OpenStreetMap, darkened), cached on your PC so places you've looked at work offline.

**The feed (right side):** CONFLICT (filter all / confirmed / unconfirmed), NEWS (stories grouped across outlets, with the left / center / right coverage bar for US outlets), MARKETS, and SAVED.

**Time slider:** drag it back up to 3 days to see what the map looked like then, or press ▶ to play it forward.

**Ask the map:** type in the box at the top, or `world what's happening near Hormuz` in the chat. Archie answers only from the reports it has stored, cites them like [1], and lights them up on the globe.

**News brief:** `news` (or the **news brief** button). An edition written at **6 am** (or when the PC wakes up after that) from the last 24 hours, and then kept as it was so it reads like a paper. When a story gets as big as the morning's top story after that, a lime bar at the top lists it with **refresh the brief**, and the **news brief** button gets a number. **Refresh now** in the header rebuilds it any time; the summary is rewritten in the background. Before 6 am you see yesterday's edition. The hour is `brief_hour` in `watch.json`; `big_story_outlets` sets how many outlets make a story "big" (0 = as big as the morning's top story). The brief has a few sentences on **the world** and **at home**, then the biggest stories **around the world**, **at home** (United States) and **close to home** (the local searches you set in `sources.json`), each with how many outlets covered it, the left / center / right mix, a one-line summary, and **save** / **follow** / **less like this**. The **Following** column shows the topics you follow (from the last 3 days); add one by typing it, or **follow** on any story; × removes it. **Muted** topics never show up. Topics can be several words separated by commas, and any of them counts. The local searches are in `sources.json` under `local`.

**Morning note:** `morning note` (or the button). Written after 6 am from real numbers: the take, a cross-asset board (futures, Europe, Asia, currencies, commodities, crypto, VIX, Treasury yields) with today, 1 week, year to date and a 5-day line, the S&P 500 sector heatmap, the yield curve against a month ago, rates and credit spreads, today's economic calendar, earnings and prediction-market odds. Prices are about 15 minutes delayed. Archie never makes up a figure.

**What's new since you looked:** when you come back to the globe (after minimizing it, or switching away for 10+ minutes), a lime **N new since 2:14 pm** button shows up at the top. Click it for the list; new things glow lime on the globe and the 2D map and say **NEW** in the feed until you press **mark all as seen**. In chat: `what's new`.

**Wrong label?** If a map icon is wrong (a pig story marked as shelling), open it and press **wrong label?** at the bottom of the card. Pick what it really is, then either **just fix this one** or pick the word that gives it away. Archie then remembers: stories with that word won't get that label again. Your fixes are listed at the top of the **sources** panel, where **remove** undoes one. (They're also in `World\label_rules.json`.)

**Markets tied to places:** straits, pipelines and countries show the markets that depend on them, with today's move and a small chart: for Hormuz, oil, European gas, tanker companies and airlines; for the Red Sea and Suez, container lines; for Taiwan, TSMC and chip stocks; for a country, its stock market ETF, its currency and what it exports. Alerts for a watched strait or pipeline include the biggest of those moves.

**Teach me (world lessons):** **teach me** on any story or report writes a short class about it: the big picture, how it got here, who's involved, why it matters, words to know, what to watch, and three check-yourself questions. It uses the story's reports from the last two weeks plus Wikipedia (offline first). **save to Obsidian** puts it in `Archie/World/Lessons`. In chat: `news lesson on <topic>` (or just `news lesson` for the biggest story). It takes a minute or two on your PC.

**News quiz:** the **quiz** button (or `news quiz` / `quiz me on the news` in chat) writes five multiple-choice questions from the biggest stories of the last day, three days or week. Answer with the mouse or the 1–4 keys and Enter; each answer explains itself and links to its story. Your recent scores show at the end, and the weekly review lists the week's quizzes and saved lessons.

**Catch me up:** on any story or report (and in the news brief), **catch me up** shows how the story developed over the last two weeks: a timeline by day, "the story so far", and **new in the last 24 hours**. In chat, `catch me up on <topic>` does the same. Reports are linked by the specific names and words they share (a town, a weapon, a person), not by common words like "White House", so it stays on one story; an unrelated item can still slip in now and then.

**Background:** **background** on any card (a story, an armed group, a country, a strait, a pipeline, an exchange, a central bank, a market on the board) explains who and what is involved and why it matters now. Archie looks each thing up in your offline Wikipedia first, then online Wikipedia, and writes only from what it finds; each piece is listed with where it came from. Your offline copy is only as new as its download, so recent events come from the news itself.

**World calendar:** the **calendar** button (or `world calendar` in chat) lists the next 60 days: national elections (Wikidata), central-bank decisions and big economic releases (Forex Factory, plus the Fed's published schedule), earnings from the biggest companies (Nasdaq), and rocket launches (The Space Devs). Filter by type, see an item on the globe, get its background, or **add to my calendar** to put it in Archie's calendar. The news brief shows what's coming up this week.

**More sources:** besides the outlets and Telegram channels, Archie reads **GDELT** (a free database of news from 100+ languages, searched by event keywords per region), **ReliefWeb** (UN humanitarian reports), and, if you set it up, **ACLED** (conflict events checked by researchers, with exact places and death tolls; an ACLED report counts as confirmed on its own). For ACLED, make a free account at acleddata.com, then put your email and password in `sources.json` (`acled_email`, `acled_password`). What a free account can see depends on ACLED's access rules; the Sources panel says if nothing comes back.

**Weekly world review:** every Sunday night Archie writes `Archie/World/Weekly/<year>-W<week>.md` in your vault: the week in a paragraph, military reports by region with a trend chart and a this-week / last-week / 4-week table, the biggest stories, names that grew or faded in the news, how the topics you follow did, the week's market moves, disasters, links to each day's digest, what you saved, your news quiz scores and the lessons you saved. `world review` writes it right away. The chart starts once there are two weeks of reports.

**Watching and alerts:** star (☆) an area, country, strait, pipeline or price. When something **confirmed** happens there, a strait or pipeline is in headlines about an attack or a shutdown, a price moves more than your limit, or there's an M6.3+ earthquake anywhere, a small note pops up at the bottom right. Click it to fly there. Nothing pops up between 11 pm and 7 am; those wait for the morning. The watch list is in the left panel.

**Saving articles:** **save** on any report or article. Archie keeps a picture of the headline (publisher, date, author, the article's photo when it has one) and a note with the link, who else reported it and the article text, in `D:\Archie\World\Saved Articles\<month>`. The **SAVED** tab shows them.

**Links that fly the globe:** headlines in the morning brief open the globe right at them. Every card has **copy link** (an `archie://world#...` link); paste it into Obsidian and clicking it opens the globe there.

**Nightly digest:** after 11 pm Archie writes `Archie/World/<date>.md` in your vault: the day's confirmed events by region, the biggest stories, disasters, big market moves, the morning note and what you saved, with links back to the globe.

**Sources and trust:** the **sources** button (left panel) lists your label fixes, then every feed, whether it's working, and how often each one was **backed up** by a different source over the last 30 days. Add or remove feeds and Telegram channels in `D:\Archie\World\sources.json`; Archie checks new ones on its next pass.

**Keeping the PC cool:** the globe draws at normal pixel density, stops drawing when its window is minimized or hidden, and pauses after 2 idle minutes (**eco** in the top bar). Only foreign-language and Telegram posts go through the AI, a handful every 10 minutes, on the smallest model you have.

**2D map · Pi:** a flat map that's much lighter than the globe.

**Governments:** the **governments** button next to layers (or `governments` / `who runs France` in chat) opens five screens you switch between at the top: **directory**, **map**, **lawmaking**, **calendar** and **my reps**. Esc or ✕ closes it.
- **Directory:** every country (plus the EU) in a scrollable list with its flag, how it's governed and who leads it. Filter by type, search by country, leader, office or any lawmaker (e.g. `cotton`), or jump to a big player (US, China, Russia, EU, India, UK, Japan, Germany, France, Brazil).
- **Country briefing:** written like a briefing for an advisor, with plain-language lines throughout. Dotted-underlined words explain themselves when you hover.
  - **Bottom line:** who's in charge, how the system works, whether it's running normally, and the next national vote.
  - **Numbered sections (each folds open):**
    1. Leadership: head of state and head of government, how long each has been in office.
    2. The administration as an org chart: the leaders on top, then every minister in columns (security and foreign policy, economy and money, home and services, other offices, central bank and diplomats). Hover anyone for what their office runs; **list** switches to a table. Countries with regions run separately (China's Hong Kong and Macau, for example) get their own dropdown.
    3. The legislature: each chamber with a seat bar by party, how members are elected, terms, and last and next elections. For the 15 parliaments in **lawmaking**, a button jumps to its bills and votes.
    4. The courts.
    5. Elections and how power changes hands, the constitution and how to change it.
    6. Political parties.
    7. Economy: World Bank numbers plus main industries and trading partners.
    8. Security and the military.
    9. International ties: UN, NATO, EU, G-20, BRICS and so on.
    10. In the news this week: from Archie's feed; click to open.
    11. Background.
- **Quick record (right side of the briefing):** click any leader or anyone in the org chart to see their record next to the briefing.
  - **Lawmakers:** how they vote and the bills they sponsor. In parliamentary countries most ministers are also lawmakers, so most of them have one.
  - **US members of Congress:** their campaign money as well.
  - **Presidents:** the laws and orders they've signed.
  - **US cabinet members:** their Senate confirmation vote and their department's major rules.
  - With nobody picked, it shows the latest votes in that country's parliament.
- **Map:** the world colored by **how it's run today**, **how it's set up on paper**, **next national vote**, or **leader in office for**. Hover for a country and its leader; click for its briefing.
- **How it stays neutral:** countries are grouped only by how power is organized (who picks the leader and who can remove them), not rated. Countries where the normal constitution isn't currently running (a coup, war or temporary government) are marked **not running normally**, with the reason. The CIA's own label for each country is shown in Background as a credited quote.
- **Where it comes from:** who holds office: Wikidata, checked daily, kept on the PC for offline use. Volunteers keep it current, so a change can take a few days to show. Full cabinets: the CIA's World Leaders directory for every foreign country (still updated by the CIA; each country shows when its list was last updated, with a warning if that was over a year ago), and the White House's own cabinet page for the US (names and titles only). Both are checked weekly and kept on the PC; Wikidata fills in only if neither has reached Archie yet. How each country is set up, its parliament and history: the CIA World Factbook's final edition (the CIA ended it in February 2026), built into Archie. Economy numbers: the World Bank, checked weekly. Flags are built into Archie (the open-source flag-icons set, MIT licence) in `D:\Archie\World\web\flags`, so they never need downloading.

**Lawmaking:** the public record of what parliaments do, downloaded to the PC so it works offline. No ratings or scores, only what was proposed, who voted how and what was said. Also in chat: `lawmaking`, `bill tracker`, `executive orders`, `how did Schumer vote`, `who funds Langworthy`.
- **Which countries:** US Congress, UK Commons and Lords, European Parliament, Canada, Ireland, France, Germany, Spain, Poland, Brazil, Switzerland, Finland, Denmark, Netherlands, Estonia, Sweden, Norway, Iceland, Italy, Lithuania, Ukraine, Chile, the Czech Republic and Australia. These are the parliaments that publish how each member votes in a form Archie can read. Most of the world votes by voice or show of hands, or doesn't publish names.
  - Germany only records names on special roll-call votes; most Bundestag votes are by show of hands.
  - In the Netherlands, most votes are cast by party, so Archie shows how each party voted.
  - Brazil decides many votes symbolically, with no names recorded.
  - Spain's names start from the sittings Archie sees after you install this version.
- **Bills:** every bill in the current session, with a 7-step bar for where it stands (introduced → in committee → out of committee → passed one chamber → passed both → sent for signature → law, or stopped). Click a step to filter, or **moving** for bills past committee but not yet law. Bill tracking covers the US, UK, Canada, Ireland and Poland. Click a bill for:
  - its official summary (for US bills, the nonpartisan Congressional Research Service's);
  - a timeline and the recorded votes on it;
  - a link to the official page.
- **Votes:** every recorded vote, newest first, with the result and a yes/no bar. Click one for how each party voted, and every name sorted into yes, no, abstain and didn't vote (searchable). Click any name for that person's record.
- **People:** every lawmaker, grouped by party. Each one's page shows:
  - their recorded votes, how often they didn't vote, and how often they voted with or broke from most of their party (filter to just those votes);
  - the bills they sponsored.
- **Campaign money (US Congress):** from the FEC's public filings, for each election cycle:
  - money raised, spent and on hand;
  - a pie of where it came from (individuals, PACs, party, the candidate's own money, other);
  - a pie of the biggest organized donors, adding what each group gave directly to the donations it collected from its members and passed on ("bundled" or earmarked, e.g. AIPAC, J Street, Club for Growth, EMILY's List, the NRA, LCV);
  - outside spending for and against them by super PACs;
  - **where their donors work** (top employers of their individual donors, like OpenSecrets' top contributors);
  - **their own political donations**: who they personally gave to and the split by party.
  - **Anyone in the directory, not just Congress:** presidents, cabinet members, or anyone who has run for Congress or President in the last eight years gets their campaign's money. Everyone else gets their personal donations. Because these donation lookups go by name, someone else with the same name can show up, so check the employers listed.
  - **OpenSecrets:** its data is no longer free to download (its API closed in 2025), so Archie builds the same views from the FEC's own filings.
  - The FEC's bulk files download weekly (about 60 MB the first time). Bundled totals come from the FEC's API on a free demo key, a few groups an hour. A free personal key from api.data.gov makes it much faster: paste it under **data sources and status**.
- **Supreme Court and judges (US, the **supreme court & judges** tab):**
  - **The Court:** each term's cases, how many were unanimous or decided 5–4, and the arguments coming up (from the Court's own argument calendar).
  - **The justices:** a card for each, with how often they were in the majority and how many opinions they wrote. Click one for every vote they cast (majority or dissent, and whose opinion they joined) and their financial disclosures. Justices are also in the directory: open the United States, then **The courts**, and click a name for the quick record.
  - **How often they agree:** a grid of how often each pair of justices ended up on the same side. Hover a square for the count.
  - **Each case:** the question, the facts, what the Court decided, how each justice voted, an **explain** button, and links to Oyez (with audio) and the full opinion.
  - **Federal judges' financial disclosures:** every federal judge files a yearly report. Search any judge or court for their gifts, paid travel, outside income, outside positions, book deals and other agreements, debts, their spouse's income sources, and (for the justices) investments. Values come in the ranges the forms use.
  - Sources: Oyez (Cornell's Legal Information Institute, Justia and Chicago-Kent) for cases and votes; the Free Law Project's CourtListener for disclosures (about 50 MB once a month). Archie doesn't show anyone's "ideology" scores.
- **Committees (US):** every House, Senate and joint committee and subcommittee.
  - **Where much of the power sits:** the committees that write spending and tax law, set the House's debate rules, confirm judges, oversee intelligence and so on come first, each with a sentence on why.
  - Each committee shows what it's for (in plain words and in its own), its chair and ranking member, its members split by party, its subcommittees, upcoming hearings (Senate), the bills sent to it this Congress and where each stands now, and the most-lobbied bills in its hands.
  - A lawmaker's page lists the committees they sit on, and a bill's page lists the committees it was sent to; click either to open the committee.
- **Lobbying (US):** the quarterly reports lobbyists must file (lda.gov).
  - Who spent the most, the biggest lobbying firms, what they lobbied about (filter by any of the 79 issue areas), and the most-lobbied bills, for each year.
  - Click any organization for its reports: which firms it hired, the bills and issues, what it said it lobbied on, who it contacted, and its lobbyists, including the past government jobs they listed.
  - A bill's page shows **who lobbied on it**. One report's amount covers everything on it, so it shows how big the effort was, not what was spent on that bill alone.
  - A lawmaker's page has **donations from lobbyists**: what lobbyists and their groups' PACs reported giving them (LD-203 reports).
  - Archie reads a few hundred report pages an hour (the free limit), so a full year takes a day or two of being online to load. A free key from lda.gov makes it faster: paste it under **data sources and status**.
- **Stock trades (US Congress):** members must report trades over $1,000 by them, their spouse or dependent children within 45 days.
  - The **stock trades** tab lists every trade Archie has read: who, whose account, the stock and ticker, bought or sold, the amount range, and how many days later it was reported. Filter by purchases or sales and by time, search a ticker, company or name, and see the most-traded stocks and most active traders of the last 90 days.
  - Each lawmaker's page has their trades and their most-traded stocks.
  - House reports come from the House Clerk. Archie reads the electronically filed reports (a few dozen every few hours); reports filed on paper are scans, so they're listed with a link.
  - **Senators:** their reports are on the Senate's eFD site, which asks every visitor to accept its terms (no unlawful or commercial use, no credit decisions, no fundraising). It's **off** until you turn it on under **data sources and status**; then Archie accepts those terms on your behalf when it checks.
  - Reading the reports uses the PDF reader from **Install Extras.bat**. If it's missing, the status page says so.
- **What was said (US and UK):** the **what was said** tab searches every word spoken on the floor: the US House and Senate (the Congressional Record, from govinfo.gov) and the UK Commons and Lords (Hansard). Type a word, phrase or name; results come newest first with who said it, where and a link to the official record. US results show the text when you click **show what was said**. Each US and UK lawmaker's page has **their latest speeches**. US searches use the same free api.data.gov key as campaign money.
- **UK money:** each MP's page has **money and interests**: donations reported to the Electoral Commission (who gave, how much, cash or in kind, with a pie of the biggest donors) and the Register of Members' Interests (paid jobs, gifts, trips abroad, shareholdings, property). Both are matched by name, so check the details.
- **Sweden, Norway and Iceland:** every vote by name from the Riksdag, the Storting and the Althing. Norway decides many things without a recorded vote, so only its electronic votes have names. Titles are in each country's language; **translate and explain** turns them into plain English.
- **Italy, Lithuania, Ukraine, Chile, the Czech Republic and Australia:** every recorded vote by name from Italy's Chamber of Deputies, Lithuania's Seimas, Ukraine's Verkhovna Rada, Chile's Chamber of Deputies and the Czech Chamber of Deputies, straight from each parliament's open data. Lithuania agrees some things by consensus, with no names. The Czech record comes as a weekly set of files (a few MB). Titles are in each country's language; **translate and explain** works on these too.
  - **Australia** (both the House of Representatives and the Senate) comes through They Vote For You, a nonpartisan project by the OpenAustralia Foundation built on the official Hansard records. It needs a free key: sign up at theyvoteforyou.org.au, open **API** from your account page, copy the key and paste it under **data sources and status**. Archie only uses its plain vote records, not its policy summaries.
- **Local government (the local tab in governments):** any county, city, town or village in the US. Pick a state and county; Archie lists the county government and every town, city and village in it (from Wikidata), biggest first. Moving somewhere new? Just pick the new county.
  - **☆ follow** a place and Archie looks on its own website for the page where it posts meeting agendas and minutes (most small towns post PDFs), then checks it twice a day. New agendas or minutes send a notification and show under **★ watching** and in the news brief.
  - **Where Archie looks:** the website comes from Wikidata and can be out of date. Fix it, or paste the exact page where they post agendas and minutes, and press **save and check now**. If Archie can't find anything, it says so and tells you what it tried. Places on Legistar (mostly bigger cities and counties) are read straight from its open data.
  - **Reading a document:** click one and Archie downloads it, reads the text (PDF or Word), and lists the **motions and votes** in it as the minutes word them (who moved what, carried or failed, the ayes and nays or the names when they're recorded). **what was decided, in plain English** has Archie's own AI explain it neutrally. Scanned PDFs (pictures of pages) have no text to read; open the original for those. **find in this document** highlights words.
  - **Search** at the top searches every agenda and set of minutes Archie has opened.
  - **+ add a board yourself:** for anything Wikidata doesn't list (a school board, fire district, planning board), give it a name and the page where it posts agendas.
- **Bill versions side by side (US):** every US bill's card has **versions of the text**: each printed version from govinfo.gov (introduced, reported by committee, passed one chamber, the final enrolled bill...). Pick two and press **show what changed**: Archie downloads both and shows every place the wording changed, word by word, with the section it's in (struck text was taken out, underlined text was put in) and how many words were added and removed. Big bills take a minute the first time. It uses the same free api.data.gov key as campaign money (it works without one, but slowly).
- **Your state legislature:** with a free Open States key (sign up at open.pluralpolicy.com, then copy the key from your profile and paste it under **data sources and status**), **my reps** lists recent votes in your state capitol and how your own state senator and representative voted on each. Only your state is downloaded.
- **Election night (the elections tab in governments):** national elections around the world: what's happening now, what's coming up, and results from the last two months. Each one shows seats and votes by party, the change since last time, which sides (alliances) they belong to and how close they are to a majority (the line on the bar). From election day until a few days after, Archie checks every 10 minutes. Results come from each election's Wikipedia article, which volunteers update from the official count, usually within minutes; check official results for anything important. The US midterms on November 3 show up here too.
- **Watching:** click **☆ watch** on any bill, lawmaker, committee or Supreme Court case.
  - Every half hour Archie compares what you've pinned with what it last saw. It sends you a notification when a bill moves (passes a chamber, becomes law, a new action), a lawmaker casts a new recorded vote or reports a new stock trade, a committee gets a new bill or hearing, or the Court schedules an argument or decides a case. One notification per item at a time.
  - **★ watching** in lawmaking lists everything you've pinned and what changed, and changes from the last two days also show in the news brief.
  - It uses data Archie already downloads, so it costs nothing extra.
- **Executive actions (US):** executive orders, proclamations and memos the President signs, and the biggest new agency rules, from the Federal Register.
- **Plain English:** any bill, vote or executive action has an **explain** button. Archie's own AI reads the official text on your PC and explains it neutrally, translating if needed. It's labeled as AI-written, so check the source for anything important.
- **Calendar:** coming committee hearings and floor business (US Senate and House, UK Parliament), Supreme Court oral arguments, plus national elections around the world from each country's last published schedule.
- **My reps:** type your US address. The Census Bureau's lookup finds your districts; the address isn't saved, only the district numbers, on this PC. You'll see:
  - your two senators and your House member (click for their votes and money);
  - your state senator and state representative, with phone, email and website.
- **Keeping the PC cool:** this runs on its own background thread, one source at a time with pauses, so it never holds up the news. The first day is the heaviest: about 250 MB across all sources (US bills about 50 MB, FEC files about 120 MB, France about 30 MB). After that it only fetches what changed.
- **Where it comes from:**
  - US: clerk.house.gov, Voteview and senate.gov (votes), govinfo.gov (bills), the FEC, the Federal Register, the Census geocoder, unitedstates/congress-legislators (people and committees) and Open States (state lawmakers), Oyez and supremecourt.gov (the Court), CourtListener (judges' disclosures), lda.gov (lobbying), disclosures-clerk.house.gov and efdsearch.senate.gov (stock trades).
  - Everywhere else: the UK Parliament's APIs, HowTheyVote.eu (European Parliament), openparliament.ca, the Oireachtas API, the Assemblée nationale's open data, abgeordnetenwatch.de, the Congreso's open data, the Sejm API, the Câmara dos Deputados, parlament.ch, the Eduskunta, the Folketing (oda.ft.dk), the Tweede Kamer, the Riigikogu, the Riksdag, the Storting and the Althing; Hansard, the Register of Members' Interests and the Electoral Commission (UK money); Wikidata and Wikipedia (elections).
  - Everything is kept in `D:\Archie\World\civic`. **data sources and status** (bottom left of lawmaking) shows whether each source is working.

**Solar system:** the **solar system** button in the top bar (or `solar system` / `planets` in chat) swaps the globe for an orrery: the Sun on a center column, each planet on its own arm and post, a horizon ring on columns marked with the months (where Earth is in its year), all drawn in the same style as the rest of Archie World.
- **Where things are:** every planet sits where it really is today, worked out on your PC from NASA/JPL's orbit formulas. Distances are squeezed so Mercury and Neptune both fit. Drag to turn or tip it, scroll to zoom, and use **◀ 30d / ▶ / 30d ▶** to run time back or forward (▶ runs 10 days a second; **now** returns to today).
- **Planet cards:** click a planet (or the Sun) for its distance from Earth and how long light takes, whether you can see it tonight (morning or evening sky), an about, its size, day, year, temperature, gravity and moons, and a little live diagram of its moons and the spacecraft circling it. **The Sun** shows space weather right now (NOAA: the Kp storm level and how far south auroras could reach, solar wind speed, the day's biggest flare). **Mars** shows the latest weather report from the Curiosity rover. **Earth** shows the Moon's phase.
- **Spacecraft:** 33 missions from the US, Europe, China, India, Japan, South Korea and the UAE: Voyager 1 and 2 in interstellar space, New Horizons, Parker Solar Probe, Juno, Europa Clipper, Juice, Psyche, Lucy, the Mars orbiters and rovers, the Moon orbiters, Webb and the Sun watchers. Ones in deep space are white diamonds; ones at a planet are listed on its card. Click one for its country, agency, launch year, status, distance from Earth, how long its signal takes, and speed. Positions come from NASA JPL Horizons twice a day.
- **Search:** the box at the top finds planets, spacecraft, countries and agencies ("India", "ESA", "Voyager", "Mars"). In chat: `where is Voyager 1`.
- **Spacecraft ▾:** a list of every spacecraft beyond Earth, grouped (interstellar, deep space, watching the Sun, Mars, Jupiter, the Moon, L1 and L2). Pick one and the view flies to where it is right now and opens its card. Picking a planet from search, or double-clicking a planet, flies in close; **⌂** goes back to the whole system.
- **Paths and the Grand Tour:** **paths** (next to ⌂) draws where the long-haul probes have been since launch, a point a week from NASA JPL: Voyager 1 and 2, New Horizons, and the finished missions Pioneer 10 and 11, Galileo and Cassini, with a ring at each flyby (hover for the date). Run time back and the probes sit where they were that day. **archive ▾ › The Grand Tour** replays it: the clock jumps to August 1977 and runs to February 1990 in about a minute while the Voyagers swing past Jupiter, Saturn, Uranus and Neptune, with each flyby named as it happens, and ends on the Pale Blue Dot.
- **Rocket launches:** the live panel counts down to the next launch anywhere on Earth. Click it (or **archive ▾ › Rocket launches**) for the next 25, each with its rocket, who's flying it, where it's going, the pad and whether it's "go". From The Space Devs' Launch Library, every few hours.
- **The Pale Blue Dot:** Voyager 1's card shows how big Earth looks from where it is today, how far from the Sun it appears, and the story of the 1990 photo, with a link to it. Voyager 2 and New Horizons show how Earth looks from them too.
- **Send a ping:** on Voyager 1, Voyager 2 or New Horizons, **send it a ping** fires a pretend radio signal. Archie draws it crossing the solar system in real time, counts it down in the live panel, and tells you when it arrives (about a day for Voyager 1) and when the answer would be back. It keeps going if you close Archie World.
- **The Moon:** search "Moon", click it in the live panel, or **the Moon close-up** on Earth's card: its distance now, the next phases with dates and times, a map of both sides with every landing (Apollo, Luna and the Lunokhods, Surveyor, Chang'e, Chandrayaan-3, SLIM, and the private landers), the Artemis landing region at the south pole, and the spacecraft orbiting it now.
- **The Mars rovers:** Mars's card has a map of every landing site, and the routes Curiosity and Perseverance have driven, stop by stop, with how far each has gone and its latest sol. From NASA's rover location maps, once a day.
- **Close up:** zoomed in, the planets get detail: Earth shows its continents turned the way they are right now (the side where it's noon faces the Sun), Jupiter and Saturn their cloud bands, Mars its dark plains and polar cap, and Saturn, Uranus (tipped on its side) and Neptune their rings. Every planet's night side is shaded away from the Sun.
- **Style:** the switch at the bottom right changes the look: **graphite** (sleek, dark), **copernicus** (deep navy with ivory linework, Latin names like TERRA and SATVRNVS, the zodiac on the ring, and the orbits filled with bands of color like old astronomy plates), **harmonia** (light parchment with bold ink and flat modern colors, after old star atlases), **neon** (each orbit its own color on black, with a glowing zodiac ring), plus era looks: **moebius (inspired)**, **1960s space age**, **1960s space poster**, **1970s NASA** (white, black linework, NASA red, with a grid floor), **1970s NASA (dark)** (the same on near-black, with white linework), **1980s synthwave** and **terminal**. Archie remembers your pick. **Dark after sunset** (next to it) switches the light styles to a dark one between sunset and sunrise: 1970s NASA to its dark version, harmonia to copernicus, moebius to graphite, the space poster to the 1960s space age. Sunset is worked out for your PC's time zone.
- **A sense of scale:** a starry background with the Milky Way's band, the asteroid and Kuiper belts as dots, dashed rings at 1, 5, 10 and 30 AU with how long light takes, and the heliopause (where the Sun's bubble ends, about 120 AU) at the rim. Around the machine:
  - **Title block** (top left): the date, day of the year, spacecraft tracked and how long Voyager 1's signal takes today.
  - **The nearest stars, to scale** (top right): a little 3D map of every star within about 17 light-years, on stems showing how far above or below the planets' plane they are, turning with the machine. Red lines show where Voyager 1 and 2 and New Horizons are headed. Hover a star for its distance, a bio, and how far Voyager 1 has gone toward it.
  - **How long light takes from Earth** (right): a ruler from 1 second to 10 years with the Moon, Sun, Mars, Jupiter, Neptune and Voyager 1 (all live), the Oort cloud, Proxima Centauri and Sirius.
  - **Real distances and sizes** (bottom left): the planets' true spacing on one line, and their true sizes next to the edge of the Sun.
  - Click any of these three cards' titles to fold it down to its title bar (▸) or open it again (▾). Archie remembers which are folded.
- **Milky Way:** scroll out past the smallest size (or press **milky way ▸**, or type `milky way` / `galaxy`) and the view pulls back out of the solar system into the galaxy. Scroll all the way back in on the Sun (or **◂ solar system**) to return.
  - **What's real:** every confirmed planet outside the solar system (over 6,000 around 4,000+ stars) from NASA's Exoplanet Archive, each star placed by its true direction and distance. Archie downloads the catalog once a week; until the first download it shows 40 famous systems built in. Also on the map: nebulae (Orion, Eagle, Carina, Lagoon), clusters (Pleiades, Hyades, Omega Centauri), dead-star remnants (Crab, Ring, Helix, Vela), giant stars (Betelgeuse, Rigel, Polaris, Vega, Sirius), the black hole Cygnus X-1, Sagittarius A* at the center, and the Magellanic Clouds.
  - **What's a model:** the galaxy's shape (the bar, the four main arms, the Orion Spur we live on, the dust lanes). Nobody can photograph it from inside, so it's drawn from radio and Gaia star surveys.
  - **Zooming:** close in you see the nearest stars and an arrow pointing toward the galaxy's center; further out, the Orion Spur and its nebulae; all the way out, the whole spiral with a ring around the Sun showing that almost every known planet is within about 3,000 light-years of us. The scale bar at the bottom left says how far light travels across it.
  - **System cards:** click a star (or search: "TRAPPIST", "Kepler-452", "Orion") for its star type and temperature, distance, when the light you'd see left it, how long Voyager 1 would take to get there, a top-down diagram of its orbits, and every planet with its size (vs Earth or Jupiter), year length, temperature, and when and how it was found. Planets in the **temperate** zone (about the warmth that would let water stay liquid) are green. Famous systems get a written about.
  - **Filters:** **all systems**, **temperate** (only stars with a temperate planet), **famous**, **Webb** (planets whose air the James Webb Space Telescope has tested). Star colors: red dwarf, orange, Sun-like, hot blue-white.
  - **Webb's targets:** a gold diamond marks systems with a planet Webb has studied. Each planet's line in the card says what it found (carbon dioxide on WASP-39 b, quartz clouds on WASP-17 b, no thick air on TRAPPIST-1 b and c, and so on), including results that are still debated.
  - **Show** (under the filters) turns three layers on and off:
    - **radio bubble:** a sphere reaching about 106 light-years out from the Sun (growing a light-year every year) showing how far Earth's radio and TV broadcasts have gone since the 1920s. Systems inside get a small blue dot; click the bubble's edge for its card and the nearest systems inside. Every system card says when our first broadcasts reached it (or will).
    - **Sun's lap:** zoomed out on the whole galaxy, a gold path shows the Sun's 230-million-year lap around the middle, with dots where the Sun was when the dinosaurs died out (66 million years ago), the first dinosaurs appeared (about one lap ago), the Great Dying, the first land animals and the Cambrian explosion.
    - **live alerts:** new supernovae (the brightest ones being watched, from the Latest Supernovae list), gamma-ray bursts (positions posted to NASA's GCN Circulars) and gravitational waves from black holes and neutron stars colliding (LIGO-Virgo-KAGRA's public alerts, with the likeliest direction from each sky map). Each is drawn in the direction it came from, or at its real place when it's within the view; the panel lists the latest and counts. Click one for what it is, how far, and how long its light (or ripples) has been travelling. Checked every 3 hours. The gravitational-wave detectors are between observing runs right now, so the last ones are from late 2025.
  - **The sky from here:** on any system card, **★ the sky from here** shows where our Sun would appear from that star (which constellation and how bright: from Proxima it's a bright star in Cassiopeia; from TRAPPIST-1 a faint one in Leo), a whole-sky map of how the bright stars shift, and a list of which ones move into other constellations or get brighter or dimmer.
  - **Nearest black holes:** Gaia BH1 (the nearest known, about 1,560 light-years), Gaia BH3 (33 times the Sun's mass), Gaia BH2, A0620-00 and V404 Cygni, plus Cygnus X-1. They show when you're zoomed in on our part of the galaxy.
  - **You're seeing the past:** under the scale bar, a gold line says how long ago the light at the edge of the view set out and what was happening on Earth then (the American Revolution, the pyramids, the first stone tools, the dinosaurs, Earth forming...). Far out it allows for space stretching while the light travels.
  - **Local Group:** keep scrolling out (or press **local group**) past the Milky Way to our galaxy's neighborhood: Andromeda (drawn tipped the way we see it, nearly edge-on) and Triangulum, the dwarf galaxies circling us and Andromeda (Sagittarius, Draco, Sculptor, Fornax, Leo I, M32, M110 and more), and a line showing the 2.5 million light-years to Andromeda. Click a galaxy for its card; searching "Andromeda" flies you there.
  - **Past the Local Group:** keep scrolling out (or press **universe**). Nearby groups of galaxies (M81, Centaurus A, Sculptor), the Virgo and Fornax clusters, the Great Attractor, the Perseus and Coma clusters, and the Shapley Supercluster, each in its real direction and distance. Then **Laniakea**, our home supercluster (about 100,000 galaxies), the **cosmic web** (drawn as an illustration: the real pattern comes from galaxy surveys), and finally the **edge of the observable universe**, 46.5 billion light-years away in every direction, glowing with the cosmic microwave background. Click any group or cluster for its card.
  - **The Andromeda merger:** open Andromeda's card and press **▶ play the merger** (or type `andromeda merger`). A simplified simulation plays once (about half a minute): the two galaxies fall together over 4.5 billion years, fling out long tails of stars on the first pass, swing apart, fall back and merge into one round galaxy. The Sun is marked so you can watch where it ends up. **❚❚ pause**, **↺ again**, **✕ close**; drag to turn it, scroll to zoom. It plays the classic forecast; the card notes that newer measurements make a merger in the next 10 billion years about a coin flip.
  - It only redraws while you move it, so it doesn't heat up the PC sitting still. In chat: `milky way`, or `star system TRAPPIST-1`.
- **Archive ▾** (next to Spacecraft ▾, only in the solar system view):
  - **People in space:** everyone in orbit right now, grouped by spacecraft (ISS, Tiangong), with their agency, country, job and how many days they've been up. Checked every 6 hours. **show the ISS** jumps to it on the globe.
  - **The Voyager Golden Record:** dropdowns for what it is, the cover's instructions for aliens, the greetings in 55 languages, the sounds of Earth, all 27 music tracks, the pictures (with a button to open the album), and where each copy is right now. Long cards scroll.
  - **Golden Record picture album:** every picture NASA has published from the record, in a full-screen album: thumbnails, click one to see it big with NASA's caption, ← → to flip through, Esc to close. Archie downloads them from NASA's gallery the first time you open it and keeps them in `D:\Archie\World\golden-record`, so after that they work offline. Also from the Golden Record card (**▦ picture album**).
  - **Mission planner:** pick a planet, an engine and a spacecraft mass. It works out the simplest path (a Hohmann transfer): trip time, the next launch window and arrival date, the speed changes needed to leave Earth orbit and to stay at the planet, the fuel from the rocket equation, and a real mission to compare. **show it on the orrery** jumps to the launch date and draws the path; **▶ fly it** runs time from launch to arrival in about 12 seconds with your probe moving along it. **now** clears it. A dropdown shows the math.
- **LIVE panel:** top left, updated every second: Voyager 1 and 2 and New Horizons counting away from Earth, the Sun's storm level and solar wind, Curiosity's Mars weather, and the Moon's phase.
- The side panels fold away while you're in the solar system and come back when you return to the globe.

## The Vault: your offline library

Right-click the owl › **Vault (the offline library)**, or type `vault` in the chat. It opens in its own window and reads everything Get Vault.bat downloaded into `D:\Archie\Vault` (the .zim packs and the RACHEL modules). Nothing in it needs the internet.

- **The front page is a catalogue.** Every pack is a card on a subject shelf: core knowledge, health, farming/water/energy/survival, repair and electronics, coding, learning for every age, and maps. Each card shows the pack's size, how many pages it has, its version, and who it's for. The first time you open the Vault it reads each pack's details. That takes a few minutes on the big drive, and the cards fill in as it goes.
- **Kids, Teens, Adults** at the top turn the front page into that age's shelf. Random pages and searches then stick to those packs too.
- **Open a pack** to see its own front page, exactly as its makers built it, with an **about** strip: what it is, its size and version, and **related packs** (Arduino Q&A leads to Electronics Q&A and Raspberry Pi Q&A, for example). Click around inside it like a website. **←** and **→** go back and forward.
- **Search** looks at page titles across every pack first, which is quick, then inside the pages. Results show which pack each one came from, with a line from the page. Click a pack's chip to see only its results. The box next to the search picks where to look: everything, one shelf, or only the pack you're in. On the big drive a few huge packs can be too slow to search everything at once. The Vault says which ones it skipped, so you can search inside them on their own.
- **Random page** opens a random page from the packs you're looking at. **Random in this pack** stays in one pack.
- **Picked for today:** three pages (for kids, teens and adults), new every day, from Wikipedia, storybooks and the how-to libraries.
- **New and updated:** when Get Vault brings in a new pack or a newer version, its card says **NEW** or **UPDATED** until you open it (or press **Mark all as seen**). If an older copy of a pack is still in the folder, the pack's about strip tells you its name and size so you can delete it.
- **Save** keeps a page on the Vault's front page (and under **Saved pages**). **Flashcards** has Archie read the page and write cards into a Study deck. Pick the deck name first. It uses your main model in Ollama.
- PDFs (the Hesperian books, for example) open in their own window. RACHEL modules' own search boxes need a web server Archie doesn't run, so they're hidden. The Vault search covers them by page title.

## Offline Wikipedia

All of English Wikipedia (text only, about 53 GB) is in `D:\Archie\Wikipedia`.

- Turn on **wiki ●**. Archie looks things up and names the articles it used, like "(Wikipedia: Photosynthesis)".
- Put the key words in your question. "What caused the Crimean War?" works better than "why did that war start?"
- To get a newer copy someday, run **Get Wikipedia.bat** (needs internet; the download can be stopped and resumed).

## Books and chapter quizzes

1. Put a book in the **Notes** folder (a `Books` sub-folder keeps it tidy). **EPUB**, PDF, `.txt` and Word all work. The best free, legal copies of classics are on Project Gutenberg: take the **EPUB** or **Plain Text UTF-8** version.
2. Name the book and the chapter:
   - `quiz me on crime and punishment part 3 chapter 5`
   - `war and peace book 2 chapters 1-4`
   - `quiz me on the first epilogue of war and peace`
3. Archie reads that exact chapter, word for word, and quizzes you one question at a time. It quotes the line that proves the answer, and won't spoil later chapters.
4. Keep going in the same chat: `now chapter 6` stays in the same book and part.

| Type | What happens |
|---|---|
| `books` | Lists the books Archie found |
| `stop book` | Puts the book away for this chat (a new chat does too) |

- Chapter numbers usually start over in each part, so say the part ("part 2 chapter 3"). If you don't, Archie uses the part you're on, or part 1.
- A whole part or a long range of chapters is too much to read at once, so Archie reads excerpts spread through it, and says so.
- Turn on **wiki ●** as well for plot summaries and themes.
- Copy-protected (DRM) EPUBs and scanned PDFs can't be read.

## Morning brief and to-dos

The brief opens the first time you open Archie each day (or click the **sun** icon). It shows:

- **Countdown:** days left to your deadlines (like the first day of classes).
- **today:** tasks due today or overdue. Click a task to tick it off.
- **where you left off:** your last two chats, with a one-line summary and **Reopen**.
- **new in your notes:** files added since the last brief.
- **from your wikipedia:** a random interesting article.
- **quick question from your notes:** a quiz question with **Show answer**.

**Commands you can type in the chat** (these work instantly, with no AI needed):

| Type | Result |
|---|---|
| `add: test servo wiring tomorrow` | Adds a task (also `todo:`, `task:`, `remind me to ...`) |
| `done: servo` | Ticks off the first task matching "servo" |
| `tasks` | Shows your open tasks |
| `deadline: portfolio due 11/15` | Adds a countdown to the brief |

Dates Archie understands: `today`, `tomorrow`, weekday names (`friday`), `next week`, `11/15`, `2026-11-15`.

- Edit the lists by hand: right-click the owl > **Edit to-do list** / **Edit deadlines**. The files are `tasks.txt` and `deadlines.txt`.
- Turn the daily pop-up off: right-click the owl > **Show the brief each morning**.

## Obsidian

Archie finds your vault automatically (the vault in Documents with the most notes). To pick another: right-click the owl > **Choose Obsidian vault...**

- **Read your vault:** with **notes ●** on, your vault is searched too.
- **Save one answer:** click **save → obsidian** under it. It becomes a note in the `Archie` folder of your vault, linked to related notes with `[[links]]` so it joins the graph view.
- **Save a whole chat:** right-click the owl > **Save this chat to Obsidian**.

### Today's daily note: your to-dos and brief

Archie keeps an **Archie** section in today's Obsidian daily note, and it works **both ways**:
- **Countdown** to your deadlines.
- **To-do** as checkboxes. **Tick one in Obsidian** and Archie marks it done. **Type a new line** like `- [ ] call the school friday` in that list and Archie adds it to your to-dos, with the date understood.
- The **morning brief** (where you left off, new notes, a Wikipedia fact, a quiz question with the answer folded away), once you've opened the brief that day.
- `log: fixed the servo jitter` in the chat adds a timestamped line under **Log** in today's note: a quick diary of what you did.

It uses your daily-note settings (folder, date format, template) and only ever changes its own section. Everything else in the note is yours. It updates when you add, tick or log something, and every minute and a half. Obsidian can be open or closed.

- Type `daily`, or right-click the owl > **Open today's daily note**.
- Turn it off: right-click the owl > **To-dos and brief in Obsidian daily note**.

### "This note": ask about the note you have open

Ask things like **"quiz me on this note"**, **"summarize this note"** or **"what's missing from my note?"**. Plain questions like **"what note do I have open in Obsidian?"** work too. Archie reads the note you currently have open in Obsidian and uses it, and `src:` shows which note.

Set up once: in Obsidian, go to **Settings > Community plugins > Browse**, search **Local REST API**, then **Install** and **Enable**. That's it. Archie finds the plugin's key by itself, and only ever connects to this PC. Obsidian needs to be open for this one feature.

### Archie and Obsidian Copilot

The Copilot plugin can use the same offline models: in Copilot's settings, pick **Ollama** and `qwen2.5:7b`. Use the **same model** as Archie, so the graphics card only holds one.
- **Copilot** is best *inside* a note: rewriting a selection, or chatting in the side panel.
- **Archie** is best everywhere else. Everything Archie saves lands in the vault, so Copilot's vault search can use it.

### Build a linked wiki from a conversation

Talk through any topic (a game's weapons and levels, a religion, a robot design). Then right-click the owl > **Build an Obsidian wiki from this chat...**, or type `build wiki`.

1. **Preview:** Archie proposes a title, sections and pages. Untick anything you don't want, or rename it.
2. **Choose how much to write:**
   - **Only what we said** sticks to the conversation.
   - **Expand** lets Archie fill in useful detail.
3. **Build it:** Archie writes a hub page, one page per section (with tables), and a detailed page for each item, all cross-linked. It lands in a new folder in your vault. Click **Open in Obsidian**.

## Chat history

Every chat saves itself automatically in `D:\Archie\Chats`, as a readable `.md` file plus a `.json` copy.

- Click the **clock** icon to search old chats. Double-click one to reopen it. Anything you send then continues that chat.
- **Delete** asks "Sure?" first.

## The owl menu

Right-click the owl for:

| Item | What it does |
|---|---|
| Open / hide chat | Same as clicking the owl or {{Ctrl+Alt+A}} |
| New conversation | Fresh chat |
| Snip screen | Same as {{Ctrl+Alt+S}} |
| Morning brief · Edit to-do list · Edit deadlines | See [Morning brief](#morning-brief-and-to-dos) |
| Chat history... | Search and reopen chats |
| Save this chat to Obsidian · Build an Obsidian wiki... · Choose Obsidian vault... | See [Obsidian](#obsidian) |
| Edit About me · Open Modes folder · Edit model names | Personalize Archie |
| Open Notes folder · Re-read notes now | Your Notes (Re-read also checks for new photos) |
| Read photos of notes automatically | The handwriting reader, on or off |
| Open the manual | This page |
| Study flashcards | Review what's due (shows the count) |
| Calendar · Focus timer (the owl) · Evening recap · Make an image... · Sketch to image... · Header pictures | See [Calendar](#calendar), [Focus timer](#focus-timer-the-owl), [Evening recap](#evening-recap) and [Making images](#making-images-offline) |
| Open Audiobooks folder · Pause audiobooks | See [Audiobooks](#audiobooks) |
| Talk to Archie · Stop talking · Archie's voice | See [Talking with Archie](#talking-with-archie) |
| To-dos and brief in Obsidian daily note · Open today's daily note | See [Obsidian](#obsidian) |
| Record a voice note | Same as **mic** or {{Ctrl+Alt+V}} |
| Open Recordings folder | Your voice recordings and their text |
| Owl size | Tiny / Small / Medium / Large |
| Chat size | Small / Medium / Large / Extra large |
| Text size | Small / Normal / Large / Extra large |
| Save dropped files to Notes | On or off |
| Show the brief each morning | On or off |
| Start Archie with Windows | Opens Archie when you log in |
| Quit Archie | Closes it completely |

## Command cheat sheet

Type these in Archie's chat. Change the words after the colon to your own. Capital letters don't matter.

> **Tip:** These are also a flashcard deck. Type `study Archie commands` to drill them.

### To-dos
- `add: test servo wiring tomorrow` (add a task; a date at the end is understood)
- `todo: buy servo horns friday` (same as add:)
- `task: email the school 10/2` (same as add:)
- `remind me to call the school friday` (same as add:)
- `done: servo` (tick off the task that matches)
- `tasks` (show your open tasks)
- `deadline: portfolio due 11/15` (a big countdown at the top of the brief)

### Calendar
- `exam: bio midterm oct 12 9am` (also works with final: and midterm:)
- `test: networking+ chapter 5 next tuesday 10:30am`
- `quiz: stats thursday`
- `due: history essay 11/3` (also assignment:, homework:, essay:, project:)
- `lab: chem titration friday 2pm`
- `class: intro to animation mondays 6pm` (repeats every week; also every monday)
- `event: college open house 10/17 at noon` (also appointment:, meeting:, reminder:)
- `add dentist on oct 3 at 3:15pm to my calendar` (any event in plain words)
- `calendar` (open the calendar; or click the date at the top)

Dates: `today`, `tomorrow`, `friday`, `next tuesday`, `in 3 days`, `oct 12`, `12th of october`, `10/12`, `2026-10-12`.
Times: `9am`, `2:30pm`, `14:00`, `noon`, `at 2` (means 2pm).

### Focus timer
- `focus` (open the owl timer; also pomodoro, timer)
- `focus: network+ subnetting` (open it and start a session on that)
- Corner arrow or Esc (hide it; the desktop owl keeps counting)

### Drawing gym
- `gym` (open the drawing gym; also drawing gym, gesture drawing, figure drawing)
- Space pause · → next · ← back · M mirror · G gray · Esc end

### Lectures
- `school day` (a walkthrough of a class day with Archie)
- `lectures` (open your lecture notes)
- `wake after class on` / `wake after class off`

### Where you are
- `this week` (sum up your week; you keep or cut each line)
- `patterns` (when you do your best work, what's slipping)

### Evening recap
- `recap` (start the evening recap; also wrap up my day, evening recap)
- Ctrl+Alt+R (start it; press again to wrap it up)

### Daily note (Obsidian)
- `daily` (open today's daily note)
- `log: fixed the servo jitter` (a timestamped line in today's note)

### Studying
- `make flashcards about the krebs cycle` (a topic)
- `make 20 flashcards about PID control` (pick how many)
- `make flashcards from this note` (the note open in Obsidian)
- `make flashcards from that` (Archie's last answer)
- `make flashcards from this chat` (the whole conversation)
- `make flashcards on crime and punishment part 1 chapter 3` (a book chapter)
- `make flashcards` with a file attached (from the file)
- `study` (review everything due)
- `study krebs cycle` (review one deck)
- `decks` (list your decks)
- `make a mock exam on PID control` (20 questions, timed)
- `make a practice quiz on the krebs cycle` (10 questions)
- `mock midterm on crime and punishment part 1 chapters 1-5`
- `give me a practice quiz on this note`
- `practice exam from my krebs cycle deck`
- `make a 30 question practice test on networking, timed 45 minutes`
- `test me on subnetting` (quick quiz)
- `exams` (your past mock exams; retake one)

In the study window: {{Space}} shows the answer. Type an answer and press {{Enter}} to have it checked. {{1}} again · {{2}} hard · {{3}} good · {{4}} easy.

### Books and audiobooks
- `quiz me on crime and punishment part 3 chapter 5`
- `now chapter 6` (next chapter, same book)
- `war and peace book 2 chapters 1-4`
- `books` (list the books Archie found)
- `stop book` (put the book away)
- `audiobooks` (how the audiobook typing-out is going, or why it's stuck)

### Obsidian
- `quiz me on this note` (the note open in Obsidian)
- `summarize this note`
- `what note do I have open in obsidian?` (checks which note is open)
- `build wiki` (turn this chat into a linked wiki)

### Apps and files
- `open blender` (any app in your Start menu; also launch, start, run)
- `open my notes folder` (also vault, downloads, documents, desktop, pictures, recordings, screenshots, flashcards, audiobooks, voice inbox)
- `make a godot script called player.gd that moves with WASD` (you see it before it's saved)
- `create EnemyAI.cs for unity that patrols between points`
- `write a python script that renames my screenshots by date`

### Pictures
- `draw a ruined desert city at dusk, concept art`
- `make an image of a scavenger girl character design`
- `generate 4 pictures of a floating island level`
- `image: red cube, studio lighting` (uses your exact words)
- `sketch` (turn one of your drawings into a picture)
- `turn this sketch into concept art` (with a drawing attached)

### Workshop
- `workshop` or `code` (open the Workshop) · in VSCodium: Ctrl+Alt+E (explain this), Ctrl+Alt+K (check my step, or run a course exercise's tests)
- in the Workshop: the **docs** chip (top right) searches the offline docs; **LOOKED UP** links under an answer open the pages Archie used; **dev coach** (left) keeps a dev log for each game

### Vault
- `vault` or `library` (open the Vault) · `vault solar water pump` (search the whole library)

### Archie World
- `world` (open the globe) · `governments` · `who runs <country>` · `solar system` · `where is Voyager 1` · `milky way` · `star system <name>` · `andromeda merger` · `people in space` · `golden record` · `mission planner` · `news` (the news brief) · `what's new` · `catch me up on <topic>` · `news lesson on <topic>` · `news quiz` · `world calendar` · `world review` · `world <question>` (ask the map) · `morning note` or `markets`

### Help
- `help` (or the **help** button: everything Archie can do, grouped, including everything it does with Obsidian and your notes, with **open** links; `what can you do` works too)
- `manual` (open this manual)
- `how do I snip the screen?` (any how-do-I question; Archie answers from the manual)
- `how do I update archie?` (the yearly checkup; the real update is double-clicking **Update Archie.bat**)

### Keys
- {{Ctrl+Alt+A}}: open or hide Archie from anywhere
- {{Ctrl+Alt+S}}: snip the screen (drag a box)
- {{Ctrl+Alt+V}}: start or stop a voice note
- {{Ctrl+Alt+T}}: talk to Archie (press again to send)
- {{Ctrl+Alt+R}}: evening recap (press again to wrap it up)
- {{Enter}}: send · {{Shift+Enter}}: new line · {{Esc}}: hide or close

## The Archie folder

| File or folder | What it is |
|---|---|
| **Start Archie.bat** | Starts Archie with no black window |
| **Create Shortcut.bat** | Puts the owl shortcut on the Desktop and in the Start menu |
| **Get Models.bat** | Downloads the AI models (internet) |
| **Install Extras.bat** | PDF/Word reading, drag-and-drop, Wikipedia reader, notes-search model (internet) |
| **Get Wikipedia.bat** | Downloads offline Wikipedia (internet) |
| **Get Handwriting Model.bat** | The better handwriting reader + iPhone photo support (internet) |
| **Install LocalSend.bat** | Phone-to-PC photo sending over Wi-Fi |
| **Get Image Maker.bat** | The offline image maker: PyTorch + Stable Diffusion XL (internet, ~10 GB) |
| **Get Sketch Model.bat** | The sketch reader for sketch to image (internet, a few hundred MB) |
| **Get Voice.bat** | Voice notes: the recording add-on + the Whisper speech model (internet) |
| **Update Archie.bat** | The yearly checkup: re-downloads your models (internet). See [Updating Archie](#updating-archie) |
| **Setup Archie.bat** | First-time setup |
| **Archie Manual.html** | This manual |
| `Manual\Archie Manual.md` | The manual's source text (see [Updating this manual](#updating-this-manual)) |
| **Notes** | Your files for Archie to search, including books. `Notes\Handwritten` is where photos of notes go |
| **Chats** | Every conversation |
| **Modes** | One text file per mode |
| **Screenshots** | Your snips |
| **Recordings** | Voice notes (`.wav` audio + `.txt` text) |
| **Study** | Flashcard decks |
| **Images** | Pictures you've made, and the image model |
| `calendar.json` | Your calendar |
| **Banners** | Pictures for the strip in the top bar (drop your own in) |
| `focus_state.json`, `Study\focus_log.jsonl` | The focus timer: today's count, and every session you finished |
| **Drawing Gym** | Reference pictures for the drawing gym (drop your own in; `gym.json` remembers how Archie sorted them) |
| **Memory** | `gym_log.json` (every drawing gym session), `left_off.json` (where you left off), `this_week.json` (the week you kept) |
| `Notes\Lectures` | Drop lecture recordings here if they're not in Obsidian (a subfolder names the class) |
| `lecture_wake.json` | The wake-after-class tasks Archie made in Windows (made automatically) |
| **Recaps** | Evening recaps (one `.json` per day, for the morning brief) |
| `last_update.txt` | When Update Archie.bat last ran (for the yearly reminder) |
| `Notes\Audiobooks`, `Notes\Voice inbox` | Drop audiobooks / recordings here |
| **Voice** | The speech model and Archie's speaking voices (`Voice\piper`) |
| **Wikipedia** | The offline Wikipedia file (`.zim`) |
| **fonts** | The fonts Archie's window uses |
| `about_me.txt` | Your profile |
| `model_names.txt` | Friendly model names |
| `tasks.txt`, `deadlines.txt` | To-dos and countdowns |
| `archie_config.json` | Settings (see below) |
| `notes_index.json`, `brief_state.json` | Made automatically. Safe to delete; they rebuild |
| `archie.py` + `archie_*.py` | Archie's program files |

### Settings file

`archie_config.json` holds your settings. Most are changed from the owl menu, but a few are only here. **Quit Archie before editing it**, and keep the quotes and commas.

| Setting | Default | Meaning |
|---|---|---|
| `hotkey_chat` | `"ctrl+alt+a"` | Show/hide hotkey |
| `hotkey_snip` | `"ctrl+alt+s"` | Snip hotkey |
| `hotkey_talk` | `"ctrl+alt+t"` | Talk to Archie hotkey |
| `hotkey_recap` | `"ctrl+alt+r"` | Evening recap hotkey |
| `speak_answers` | `false` | The **speak** switch |
| `talk_speaks` | `false` | `true` = {{Ctrl+Alt+T}} questions are always answered out loud |
| `speech_voice`, `speech_speed` | `"en_GB-alan-medium"`, `1.0` | Archie's voice (owl menu) |
| `daily_note` | `true` | To-dos and brief in the daily note |
| `files_dir` | `null` | Where new files are saved (`null` = Documents\\Archie Files) |
| `phone_tidy` | `true` | Tidy voice notes from the phone into notes |
| `audiobooks_paused` | `false` | The **Pause audiobooks** switch |
| `audiobook_model` | `null` | Whisper model for audiobooks (`null` = same as voice notes) |
| `hotkey_voice` | `"ctrl+alt+v"` | Voice note hotkey |
| `voice_model` | `"small.en"` | Speech model (`medium.en` is more accurate; download it with **Get Voice.bat**) |
| `voice_device` | `"cpu"` | `"cuda"` tries the graphics card (needs extra NVIDIA libraries; falls back to cpu) |
| `ocr_model` | `null` | Which vision model reads handwriting (`null` = the best one installed) |
| `context_tokens` | `16384` | How much text the model can hold at once. Higher uses more graphics memory |
| `model`, `mode` | | What you last picked |
| `use_notes`, `use_wiki` | | The ● / ○ switches |
| `obsidian_vault` | | Your vault folder |
| `system_prompt` | | Archie's core personality instructions |

## Troubleshooting

**"Ollama not reachable" or "I can't find Ollama"**
Open the Ollama app from the Start menu (a llama icon appears by the clock), then click **+** for a new chat.

**"No models are installed"**
Run **Get Models.bat** (needs internet once).

**The hotkeys open an old version, or nothing happens**
An old copy of Archie is still running. Right-click every owl you see > **Quit Archie** (or end `pythonw.exe` in Task Manager), then start Archie again. Only one Archie can run at a time; starting it again just brings the open one forward.

**A hotkey "didn't work"**
Another program uses that key combination. Pick another in `archie_config.json` (for example `"ctrl+alt+q"`), then restart Archie.

**Answers are slow**
- The first answer after starting loads the model into your graphics card (10–30 s). Later ones are quicker.
- Switching models reloads them.
- Very long chats get slower, so start a new one (**+**).

**Archie says it can't read a PDF, Word file or Wikipedia**
Run **Install Extras.bat** (needs internet once), then restart Archie.

**Notes are on but it doesn't find my file**
Right-click the owl > **Re-read notes now**. Check that the file isn't a scanned PDF.

**The window looks plain (wrong fonts)**
Make sure the `fonts` folder is next to `archie.py`.

**Archie doesn't talk**
- Run **Get Voice.bat** (it adds the voices). Check the sound is up and the right speakers are the default.

**"quiz me on this note" says Obsidian isn't open**
Open Obsidian with the note in front, and check **Local REST API** is enabled under Community plugins.

**Making an image says it ran out of memory**
Close games or other programs using the graphics card, and pick **1** picture at a time.

**"PyTorch can't see your NVIDIA graphics card"**
Run **Get Image Maker.bat** again. It installs the CUDA version of PyTorch. Also update your NVIDIA driver.

**The mic doesn't record**
- Open Windows **Settings > Privacy & security > Microphone** and turn on **Let desktop apps access your microphone**.
- Check the right microphone is the default: Settings > System > Sound > Input.
- "Voice notes need..." means **Get Voice.bat** hasn't been run yet. Quit Archie, run it, then start Archie again.

**The transcript has wrong words**
Fix them in the Voice note window before saving. Or switch to the more accurate model: run **Get Voice.bat** and pick 2 (medium.en).

**A photo of notes wasn't read**
- Check it's in the Notes folder, then right-click the owl > **Re-read notes now**.
- iPhone `.heic` photos need **Get Handwriting Model.bat** (or **Install Extras.bat**).
- If the text came out badly, run **Get Handwriting Model.bat**, delete the `(transcribed).md`, and it'll be read again.

**Drag-and-drop doesn't work**
Run **Install Extras.bat**. The **+ attach** button always works.

**Something else broke**
Right-click the owl > **Quit Archie**, then start it again. Your chats, notes and settings are all files, so nothing is lost.

## Updating Archie

When you get new Archie files:

1. Right-click the owl > **Quit Archie**.
2. Copy the new files into `D:\Archie`, replacing the old ones. Your **Notes**, **Chats**, `about_me.txt`, `tasks.txt`, settings and Wikipedia are never replaced.
3. Start Archie again.

### The yearly checkup (models)

Archie's models are files on your drive. They **never change by themselves**, and an older model doesn't wear out: it answers the same way next year as today. Two reasons to refresh them about once a year:

- A model only knows the world up to when it was trained. (Your offline Wikipedia helps with newer facts.)
- Better small models come out every year that still fit your 8 GB graphics card.

**How:**

1. When you're online, double-click **Update Archie.bat** (or click **run Update Archie.bat** in the brief). Archie can stay open.
2. It re-downloads the newest version of every model you already have. If something fails, the old version keeps working.
3. At the end it asks whether to open Ollama's model library, so you can look for **newer** models. Look for ones around **7-8B** in size.
4. To try a new one: open a Command Prompt, run `ollama pull <name>`, then pick it from the **model pill** at the top of Archie. Your old models stay installed, so you can always switch back.

About a year after the last update, the brief shows a **yearly checkup** reminder. (The date is kept in `last_update.txt`.)

On purpose, the update does **not** touch the image maker, voice, or Python add-ons, because updating those can break things (like the NumPy problem). Your offline Wikipedia also stays as it is; run **Get Wikipedia.bat** for a newer copy. Ollama itself updates on its own: when an update is ready, its tray icon says **Restart to update**.

**Back up** by copying these to another drive now and then:
- the `Notes` and `Chats` folders,
- `about_me.txt`, `tasks.txt` and `deadlines.txt`,
- the `Modes` folder.

## Updating this manual

The manual has two copies:

- `Manual\Archie Manual.md` is plain text you can edit in Notepad.
- **Archie Manual.html** is the pretty version.

When the `.md` is newer, Archie rebuilds the pretty version automatically the next time you open the manual (owl menu > **Open the manual**, or type `manual`). To add your own notes, write them in the `.md` under a `## ` heading.

## Changelog

**3.26 · Oct 9, 2026**
- **The Vault:** one screen to browse, search and read the whole offline library. A catalogue front page with subject shelves, a card for each pack, kids/teens/adults shelves, new and updated marks, and notes about older copies. Each pack opens on its own front page with related packs. Search covers titles and then full text across all packs, one shelf, or one pack. Also: random page, three picks for today, saved pages, and flashcards from any page into Study.

**3.23 · Oct 2, 2026**
- **Workshop checkers:** every save is checked by the real tools (ruff for Python, the C and C++ compilers, javac, node, plus HTML, CSS and JSON checks), shown with exact lines, as squiggles in VSCodium, and used by Archie when it builds. **check all files** checks the whole project.
- **Library:** about 40 tested building blocks (Python, web, Arduino, C, C++, Java, C#) that snap together, 8 whole apps to start from (Farm log, Clinic medicine stock, Class attendance, Chama ledger, Water tank alarm, Soil-moisture irrigation, Desk clock, Stock and records), block updates with changelogs, and saving your own code as blocks.
- **Courses:** six courses, learnable in any order or side by side: Python (Levels 0 and 1, 15 units), Java (12), Web: HTML, CSS and JavaScript (12), C# (12), C++ (11) and C (11). About 160 exercises graded by real tests, quizzes, explain-it-back, mastery at 85%, warm-ups, flashcards and a skills map. Shared ideas across languages give **you know this from...** bridges, **test out**, and side-by-side **compare**.
- **How it works** guides for library apps (overview, parts, wiring, annotated code) and **teach me to build it** lessons for four of them.
- **Delete and trash** for projects, courses and your own blocks (restorable), and **new lesson plan**.
- **Fix:** the Workshop page no longer wipes what you're typing when it refreshes, and the Workshop window always opens the current version.

**3.22 · Oct 2, 2026**
- **Workshop:** code with Archie offline. Teach mode (lessons, check my work, hints, flashcards) and build mode (Archie writes, runs and fixes, with undo), watching your saves and explaining errors, a live preview for web pages, and many languages.
- **VSCodium + Archie Coach:** Get Code Editor.bat sets up VSCodium with offline AI (Continue) and Archie's own add-on that links the editor to the Workshop.

**3.21 · Oct 2, 2026**
- **Lawmaking:** local government anywhere in the US (pick a state and county, follow the county, towns, cities and villages; Archie finds and watches their agendas and minutes, reads them and pulls out the motions and votes), and US bill versions side by side with every change highlighted.

**3.20 · Oct 2, 2026**
- **Lawmaking:** six more parliaments: Italy, Lithuania, Ukraine, Chile, the Czech Republic and Australia (with a free They Vote For You key).
- **Milky Way:** the radio bubble, Webb's targets and what it found, the Sun's lap around the galaxy with Earth's history on it, the sky from another star, the nearest black holes, a "you're seeing the past" line, and live alerts for supernovae, gamma-ray bursts and gravitational waves.

**3.19 · Oct 2, 2026**
- **Lawmaking:** search what was said on the floor of Congress and Parliament; UK MPs' donations and registered interests; Sweden, Norway and Iceland; your state legislature's votes (with a free Open States key); and election night, with results for national elections around the world as they come in.

**3.18 · Oct 2, 2026**
- **Solar system:** paths for the long-haul probes and a Grand Tour replay of the Voyagers (1977 to the Pale Blue Dot); a live countdown to the next rocket launch and a launch list; the Pale Blue Dot and how Earth looks from the probes; send a ping and watch it cross the solar system; a Moon close-up with phases and every landing on both sides; the Mars rovers' routes; and a dark style after sunset.

**3.17 · Oct 1, 2026**
- **Lawmaking:** the Supreme Court (every justice's votes, opinions, how often each pair agrees, upcoming arguments, each case explained), federal judges' financial disclosures, congressional committees (what each is for, who sits on it, what it's working on), lobbying (who spent what, on which bills, and lobbyists' donations to each lawmaker), and stock trades reported by members of Congress. Committees and cases can be watched; watched lawmakers now also alert on new stock trades.
- **Governments:** the US briefing lists the nine justices under **The courts**; click one for their record.
- **Note:** the US bill files download once more (about 50 MB) so Archie can record which committee each bill went to.

**3.16.1 · Oct 1, 2026**
- **Lawmaking:** watch bills and lawmakers and get notified when they move; yes/no votes now use green and violet so they can't be confused with party colors.
- **Governments:** parties in their own colors (US Democrats blue, Republicans red); the Vice President is in the US org chart; the calendar adds every country's upcoming national elections (exact dates), European Parliament and Polish Sejm sitting days, and folds long single-country days.
- **News:** a first name that's also a country (Chad, Jordan) no longer pins a story to that country; the brief keeps one entry per story and folds near-duplicate write-ups into it, so one event can't fill "around the world".

**3.16 · Oct 1, 2026**
- **Lawmaking:** bills and where they stand, every recorded vote and who cast it in 15 parliaments, each lawmaker's record, US campaign money (with bundled donations and outside spending), US executive actions, plain-English explanations, a political calendar, and **my reps**.
- **Governments:** the Netherlands was missing from the directory and map; it's back.

**3.15.2 · Oct 1, 2026**
- **Governments:** every country's flag is built in; leaders no longer show as a Wikidata number; stray entries from the White House page are filtered out; start dates no longer show a day early.

**3.15.1 · Oct 1, 2026**
- **Governments:** full administrations for every country (the CIA's World Leaders directory, and the White House for the US) shown as an org chart, instead of Wikidata's patchy minister lists.

**3.15 · Oct 1, 2026**
- **Governments:** a directory of every country with an in-depth briefing (leaders, cabinet, parliament with seats, courts, elections, economy, military, alliances, news) and a world map colored by how each country is run, its next vote, or how long its leader has been in office. Live officeholders from Wikidata; structure from the CIA World Factbook's final edition; economy from the World Bank.

**3.14 · Oct 1, 2026**
- **Milky Way:** the Local Group, then nearby galaxy groups and clusters, Laniakea, the cosmic web and the edge of the observable universe; a playable Andromeda merger simulation.
- **Solar system:** the archive menu: people in space, the Voyager Golden Record and its picture album, and a mission planner that draws the transfer on the orrery; foldable corner cards; the dark 1970s NASA style.

**3.13 · Oct 1, 2026**
- **Milky Way:** scroll out of the solar system into the galaxy and on to the Local Group (Andromeda, Triangulum and the dwarf galaxies), with every confirmed exoplanet from NASA's Exoplanet Archive (updated weekly), nebulae, clusters, the central black hole and the Magellanic Clouds; system cards with each planet's size, year and temperature.
- **Solar system:** era styles (moebius, 1960s, 1970s NASA with a grid floor, synthwave, terminal), a sense of scale (stars, belts, distance rings, the heliopause, real-scale distances and sizes), a title block, a nearest-stars map and a light-time ruler; search finds every country's missions; the "new report" pop-up no longer catches clicks after it fades.
- **2D map:** the blue tint over the map when cyclones were on is gone.

**3.12 · Sep 30, 2026**
- **Solar system:** a spacecraft list that flies to each one's current location, fly-in close-ups, detailed planets (continents on Earth, rings on Saturn, Uranus and Neptune, night sides), four styles, and a live panel; clicks work again.

**3.11 · Sep 30, 2026**
- **Archie World:** the solar system view, an orrery with real planet positions, planet cards with live space weather and Mars weather, 33 spacecraft positioned from NASA JPL, search by name or country, and a time control.

**3.10 · Sep 30, 2026**
- **Archie World:** satellite cards show who owns and runs each satellite; a mines layer (industrial and artisanal) with bios, supply share and live market prices; Antarctic research stations with live weather, polar night / midnight sun, and webcams.

**3.9.1 · Sep 30, 2026**
- **Archie World:** satellite groups you can switch on (space stations, brightest, science, weather, GPS, Starlink); the ISS can be clicked again; long storm names from GDACS are cut down to the storm's name.

**3.9 · Sep 30, 2026**
- **Archie World:** earthquakes leave the map after 24 hours; storms get a real symbol, their track, forecast, cone and a proper card; a live International Space Station with its orbit. The old spinning storm icon and its rings are gone (less work for the graphics card).

**3.8 · Sep 30, 2026**
- **Archie World:** the news brief is now a 6 am edition with a refresh bar when big stories break; a defense category (budgets, arms deals, exercises) that stays out of the war counts; **wrong label?** on every card, which learns from a word you pick; the markets that depend on each strait, pipeline and country; what's new since you last looked; world lessons (**teach me**); and the news quiz.
- Foreign-language posts no longer get a fighting label unless the translation actually describes fighting.

**3.7 · Sep 30, 2026**
- **Archie World:** catch me up (story timelines), background explainers for anything, the world calendar, GDELT / ReliefWeb / ACLED sources, and the weekly world review in Obsidian.

**3.6 · Sep 29, 2026**
- **Archie World:** the news brief (world, at home, close to home, topics you follow); the live globe (conflict reports from both sides with sources, disasters, weather radar, pipelines, straits, markets), street maps when zoomed in, a time slider, ask the map, the morning note, watchlist alerts, saved articles, a nightly digest in Obsidian, and a world section in the morning brief.

**3.5 · Sep 29, 2026**
- **Where I left off:** one line at the end of a focus session comes back when you start that project again and in the next morning's brief, with **resume**.
- **This week:** Archie drafts a summary of your week, you keep or cut each line, and the rest goes into its answers (and Obsidian).
- **Patterns:** when you do your best work, hours per project week by week, what's slipping, and suggestions. A line in the brief too.
- **Calendar:** a week view, color coding (lecture, recorded, due, exam, test, quiz, lab, focus, gym), days that glow by how much you focused, and recorded lectures on the day they happened.
- The drawing gym log moved to a new **Memory** folder (it was in with the flashcards, where it could confuse them).

**3.4 · Sep 29, 2026**
- **Drawing gym:** drop reference pictures in a folder and Archie sorts them (figure, faces, hands, animals, landscapes...). Pick categories, a time per picture (or no timer, or the class ladder) and how many, then draw. Mirror and gray buttons, streaks and a weekly count.
- **Lectures:** recordings made during a class on your calendar (or in a Lectures folder, or over 30 minutes) become full notes like a Plaud summary: summary, key points with times, notes by topic, terms, to-dos with due dates (added to your list), review questions, a mind map (also saved as an editable map for the Mindmap plugin) and the timestamped transcript.
- **Wake after class:** Windows wakes the PC after each class so the note is ready when you get home, then it goes back to sleep.
- **Sketch to image:** pencil smudges and paper grain no longer turn into glowing specks.
- **help button** at the bottom (next to speak): everything Archie can do in one list, grouped like the school day, with **open** links. `manual` now opens this manual.
- **A school day with Archie:** a walkthrough in the Quick start (type `school day` to see it in the chat; the greeting points to it).

**3.3 · Sep 28, 2026**
- **Picture strip** in the top bar: your pictures from the Banners folder, crossfading every 15 minutes (click for the next), faded into the header, tinted by the time of day, with the focus timer on it while it runs. Drop pictures in the folder and they join in by themselves.
- The owl icon left the top bar, so ARCHIE starts at the edge and the pictures get more room.
- A 24-hour clock in the bottom left of the picture, in the pixel font Micro 5.

**3.2 · Sep 28, 2026**
- **Sketch to image:** bring in a drawing (drop, paste, snip, or from your vault), Archie reads it and writes the description, you pick how closely to follow your lines (loose / balanced / strict) and one of 20 styles, and it paints 1–4 versions next to your sketch. Needs Get Sketch Model.bat once.

**3.1 · Sep 28, 2026**
- **Evening recap:** the moon button next to the timer (or Ctrl+Alt+R). Talk about your day; Archie types it out, sorts it into today, tomorrow and what's on your mind, puts tomorrow's tasks on your list, saves a note to Obsidian, and opens the next morning's brief with it.
- The header fits any chat size: the timer and recap buttons shrink to icons when it's narrow.

**3.0 · Sep 28, 2026**
- **Focus timer (the owl):** a Pomodoro timer next to the date. The owl's wings unfold as you work, the wings breathe, a pulse runs out through the feathers each minute, and the owl sleeps whenever the timer isn't running. It pops up with a sound when time's up, logs what you did in the daily note, and shrinks to the desktop owl.
- Fixed: if opening an app, tidying a voice note or saving it to Obsidian failed, the error message itself could crash that step.

**2.9 · Sep 28, 2026**
- **Yearly checkup:** **Update Archie.bat** refreshes your models in one click, and the brief reminds you once a year.
- Image making works from inside Archie now. (A Windows quirk froze the image helper while it loaded PyTorch, and a newer diffusers renamed a setting.)
- "This note" understands more ways of asking, like "what obsidian note do I have open?"

**2.8 · Sep 28, 2026**
- **Mock quizzes and exams:** timed, with multiple choice, true/false, short and long answers. Graded with partial credit, plus what to review, flashcards from your mistakes, save to Obsidian and retake.
- Audiobooks: if a file can't be opened, Archie now says why and keeps retrying instead of sitting at "waiting". It also uses the book's real title from inside the file, and accepts .mp4.

**2.7.1 · Sep 28, 2026**
- A command cheat sheet (a simple list, with a real example for each), and a flashcard deck of it (`study Archie commands`).
- The brief always shows **coming up**, even when the calendar is empty.

**2.7 · Sep 28, 2026**
- **Calendar:** click the date at the top. Exams, tests, quizzes, due dates, labs, weekly classes and events, added in the month view or by typing (`exam: bio midterm oct 12 9am`). It's in the brief, the daily note and Archie's answers.
- **Offline image making** with Stable Diffusion XL on your graphics card: `draw ...`, with prompt writing, shapes, variations and save to Obsidian.

**2.6 · Sep 28, 2026**
- **Professor** mode tab.
- Flashcards with spaced review: made from topics, notes, chats, books and files, with professor-style answer checking.
- `open <app>` (finds apps as you install them) and `make ... script called ...` files, with preview before saving.
- Walk-and-talk phone voice notes (Obsidian mobile's recorder or a Voice inbox), typed out and tidied into Obsidian.
- Audiobooks: typed out chapter by chapter in the background, then quizzable like books.

**2.5.1 · Sep 27, 2026**
- {{Ctrl+Alt+T}} answers are written, not spoken, unless **speak** is on (or `talk_speaks` is `true`).
- Voice notes use whichever speech model you downloaded.

**2.5 · Sep 27, 2026**
- Talking: {{Ctrl+Alt+T}} to ask by voice and hear the answer, **speak** to hear every answer, **read aloud** under each answer, and 4 voices.
- Today's Obsidian daily note: two-way to-dos, the countdown, the morning brief, and `log:`.
- "This note": ask about the note open in Obsidian (Local REST API plugin).
- A taskbar-pinnable shortcut.
- If Archie can't start, it now says why and writes `archie_error.log`.

**2.4 · Sep 27, 2026**
- Voice notes: **mic** or {{Ctrl+Alt+V}} records until you stop, and Whisper types it out offline.
- An editable transcript window: **tidy up**, **ask archie**, **copy**, and **save → obsidian** (optionally with the audio).
- **Get Voice.bat**.

**2.3 · Sep 27, 2026**
- The handwriting reader also watches your Obsidian vault: Excalidraw pen pages (auto-exported PNGs) and anything in a **Handwritten** folder.
- Typed-out pages are real Obsidian notes (`#handwritten`, the image embedded, linked in the graph).
- Pen pages are read again when you add to them.

**2.2 · Sep 27, 2026**
- The handwriting reader: photos of notes and scanned PDFs in Notes are read into searchable text automatically.
- Phone photos are turned the right way up; iPhone HEIC photos are supported.
- **Install LocalSend.bat** (phone to PC over Wi-Fi) and **Get Handwriting Model.bat**.

**2.1 · Sep 27, 2026**
- EPUB books, and chapter quizzes ("quiz me on crime and punishment part 3 chapter 5").
- This manual. Type `manual`, or ask Archie how to do things.

**2.0 · Sep 27, 2026**
- New look, "Graphite x Terminal": dark with lime.
  - Mode tabs, a model pill and icon buttons at the top.
  - Terminal-style input bar with RUN.
  - Bubbles for your messages; a lime line beside Archie's answers.
- New lime owl, and matching app icon.
- Rounded window (Windows 11) and bundled Geist + JetBrains Mono fonts.

**1.4 · Sep 27, 2026**
- Obsidian: search the vault, **save → obsidian** with `[[links]]`, save whole chats.
- Build a linked Obsidian wiki from any conversation.

**1.3 · Sep 27, 2026**
- Morning brief, to-dos and deadlines (typed commands).
- Hotkeys ({{Ctrl+Alt+A}}, {{Ctrl+Alt+S}}) and drag-a-box screen snips.
- Resizable chat and text size.
- Save dropped files to Notes.
- Only one Archie runs at a time.

**1.2 · Sep 26, 2026**
- Offline Wikipedia, friendly model names, About me, chat history, modes.

**1.0 · Sep 26, 2026**
- The floating owl and chat, attachments (PDF, Word, code, images), and Notes search.

## Coming later (saved ideas)

- **Animatic builder:** storyboard panels cleaned up with sketch to image, timed out with a scratch voice track into a rough video.
- **Election night for every election:** live results for US races and national elections abroad, showing which sides are winning seats.
- Someday: a physical Archie on a Raspberry Pi.
