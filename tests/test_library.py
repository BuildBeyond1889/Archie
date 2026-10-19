"""The Workshop's library and courses, checked the way Archie uses them.

- Every Python and JavaScript building block is copied into a scratch project exactly as Archie
  would (each file to the place its block.json says) and its own test is run.
- Every course and unit file is valid JSON with the parts the Workshop needs.
- Every whole-app recipe names blocks that exist.
"""
import json, os, re, shutil, sys
import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
WORKSHOP = os.path.join(HERE, "..", "World", "workshop")
BLOCKS = os.path.join(WORKSHOP, "blocks")
COURSES = os.path.join(WORKSHOP, "courses")
RECIPES = os.path.join(WORKSHOP, "recipes")


sys.path.insert(0, os.path.join(HERE, ".."))
import archie_blocks  # noqa: E402

LIB = archie_blocks.Blocks(BLOCKS, os.path.join(HERE, "_user_blocks_unused"))
RT = {k: shutil.which(k) for k in ("node", "g++", "gcc", "javac", "java", "dotnet")}
ALL = sorted(b for b in os.listdir(BLOCKS) if os.path.isfile(os.path.join(BLOCKS, b, "block.json")))


@pytest.mark.parametrize("bid", ALL)
def test_block(bid):
    """Archie's own "test on this PC" for every block. Blocks whose tools aren't installed
    (dotnet, javac, a window toolkit) are skipped, the same way Archie reports them."""
    r = LIB.test(bid, RT)
    out = r.get("output") or ""
    if r.get("ok") is None or re.search(r"No module named '(tkinter|pygame|_tkinter)'|no display name|couldn't connect to display|TclError", out):
        pytest.skip(out.splitlines()[-1] if out else "needs a tool that isn't installed")
    assert r["ok"], out


def test_every_block_is_complete():
    for bid in os.listdir(BLOCKS):
        b = json.load(open(os.path.join(BLOCKS, bid, "block.json"), encoding="utf-8"))
        for key in ("name", "kind", "lang", "version", "summary"):
            assert b.get(key), f"{bid}: missing {key}"
        for name in b.get("files", {}).values():
            assert os.path.isfile(os.path.join(BLOCKS, bid, name)), f"{bid}: {name} is missing"


def test_courses_load():
    units = 0
    for c in sorted(os.listdir(COURSES)):
        course = json.load(open(os.path.join(COURSES, c, "course.json"), encoding="utf-8"))
        assert course.get("title") or course.get("name"), c
        for u in os.listdir(os.path.join(COURSES, c, "units")):
            unit = json.load(open(os.path.join(COURSES, c, "units", u), encoding="utf-8"))
            assert unit.get("id") and unit.get("title"), u
            units += 1
    assert units >= 100


def test_recipes_use_real_blocks():
    have = set(os.listdir(BLOCKS))
    for r in os.listdir(RECIPES):
        recipe = json.load(open(os.path.join(RECIPES, r, "recipe.json"), encoding="utf-8"))
        for bid in recipe.get("blocks", []):
            bid = bid if isinstance(bid, str) else bid.get("id")
            assert bid in have, f"{r} needs a block called {bid}"
