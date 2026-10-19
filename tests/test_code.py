"""Every Python file compiles, every bundled data file is valid JSON, and nothing personal ships."""
import glob, json, os, py_compile, re

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


def test_python_compiles(tmp_path):
    files = glob.glob(os.path.join(ROOT, "*.py"))
    assert len(files) > 30
    for f in files:
        py_compile.compile(f, cfile=str(tmp_path / (os.path.basename(f) + "c")), doraise=True)


def test_json_files_parse():
    for f in glob.glob(os.path.join(ROOT, "World", "**", "*.json"), recursive=True):
        with open(f, encoding="utf-8") as fh:
            json.load(fh)


def test_no_personal_files():
    for name in ("about_me.txt", "archie_config.json", "tasks.txt", "deadlines.txt", "calendar.json",
                 "notes_index.json", os.path.join("World", "watch.json"), os.path.join("World", "world.db")):
        assert not os.path.exists(os.path.join(ROOT, name)), f"{name} is personal and must not be in the repo"
    for d in ("Chats", "Notes", "Recordings", "Study", "Memory", "Recaps", "Screenshots", "Images"):
        assert not os.path.isdir(os.path.join(ROOT, d)), f"{d}/ is personal and must not be in the repo"


def test_no_keys_in_sources():
    s = json.load(open(os.path.join(ROOT, "World", "sources.json"), encoding="utf-8"))
    assert not s.get("acled_email") and not s.get("acled_password") and not s.get("firms_map_key")
    for f in glob.glob(os.path.join(ROOT, "*.py")):
        text = open(f, encoding="utf-8").read()
        assert not re.search(r"(api_key|apikey|token)\s*=\s*['\"][A-Za-z0-9]{24,}['\"]", text, re.I), f
