# Workshop library

| Folder | What's in it |
|---|---|
| `courses/` | Six courses (Python, Java, Web, C#, C++, C). Each unit is one JSON file: a lesson, a worked example, a problem set with tests, a quiz and an explain-it-back prompt |
| `blocks/` | About 40 tested building blocks. `block.json` says what a block does, which files go where, how to test it and its changelog |
| `recipes/` | Eight whole apps made from blocks (farm log, clinic stock, class attendance, savings-group ledger, water tank alarm, soil-moisture irrigation, desk clock, stock and records) |
| `archie-coach/` | The VSCodium add-on that links the editor to the Workshop (`archie-coach.vsix` is the packaged version) |
| `arduino-stub/` | A practice Arduino so sketches can be checked with no board support installed |

Every block's test runs in `tests/test_library.py`, the same way the Workshop's **test on this PC** button runs it.
