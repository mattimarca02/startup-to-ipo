#!/usr/bin/env python3
"""Tests for the lobby and garages plan (docs/LOBBY_GARAGE_PROPOSAL.md), outside Studio.

Run:   python3 tools/lobby_test.py

It needs git, the commit 99eed7b (every full clone of the repo has it; a shallow clone may not) and the free Luau
command-line tool (https://github.com/luau-lang/luau/releases, the "luau" file from luau-macos.zip, luau-windows.zip
or luau-ubuntu.zip). Put it on your PATH, or point to it:
       LUAU=/path/to/luau python3 tools/lobby_test.py

PR L0 (this file's first version) only adds the CLAIMLOAD markers to TycoonCore.lua, around the join load that PR L3
moves into claimGarage: onPlayerAdded from `local saved, ok = load(player)` to `data.ready = true`, lines 774-863 of
TycoonCore.lua at main 99eed7b (the proposal's section 2.1). It checks that:
- there is one CLAIMLOAD-START line and one CLAIMLOAD-END line, comment lines only, inside onPlayerAdded;
- the text between them is lines 774-863 of TycoonCore.lua at 99eed7b (read with git show), byte for byte;
- TycoonCore.lua without its CLAIMLOAD comment lines is the file at 99eed7b, byte for byte (L0 adds comments
  only; L1 changes other lines and narrows this check);
- docs/STUDIO_SYNC_LOBBY.md gives TycoonCore.lua's real SHA-256 and size, and its hash block (run in Luau against a
  fake Studio) says OK for the real file and DIFFERENT for a changed one.
Then it breaks TycoonCore.lua on purpose, in memory (mutation runs): each must be caught by its named check, never
by a crash. Running the marked block with fakes (a DataStore, the modules, a player leaving at each yield) is PR L3's.

It changes nothing in the game or in Studio. It never edits the other test files.
"""

import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = "99eed7b"            # main before L0: the CLAIMLOAD block is compared with this commit's TycoonCore.lua
FIRST, LAST = 774, 863      # the block's lines at BASE (docs/LOBBY_GARAGE_PROPOSAL.md section 2.1)
START = "-- CLAIMLOAD-START"
END = "-- CLAIMLOAD-END"
SYNC_DOC = "docs/STUDIO_SYNC_LOBBY.md"


def read(name):
    with open(os.path.join(ROOT, name), encoding="utf-8") as f:
        return f.read()


def read_bytes(name):
    with open(os.path.join(ROOT, name), "rb") as f:
        return f.read()


def git_show(rev, path):
    """The bytes of path at rev, or None if git or the commit is missing."""
    try:
        got = subprocess.run(["git", "show", "%s:%s" % (rev, path)], cwd=ROOT, capture_output=True)
    except OSError:
        return None
    return got.stdout if got.returncode == 0 else None


def run_luau(luau, source):
    with tempfile.NamedTemporaryFile("w", suffix=".luau", delete=False, encoding="utf-8") as f:
        f.write(source)
        path = f.name
    try:
        return subprocess.run([luau, path], capture_output=True, text=True, timeout=600)
    finally:
        os.unlink(path)


def lua_long_string(text):
    level = 0
    while ("]" + "=" * level + "]") in text:
        level += 1
    return "[" + "=" * level + "[\n" + text + "]" + "=" * level + "]"


def marker_lines(lines, marker):
    """Indexes (0-based) of the lines that hold marker."""
    return [i for i, line in enumerate(lines) if marker.encode() in line]


def marked_block(lines):
    """The lines strictly between the one START line and the one END line, each with its newline, or None."""
    starts, ends = marker_lines(lines, START), marker_lines(lines, END)
    if len(starts) != 1 or len(ends) != 1 or ends[0] <= starts[0]:
        return None
    return b"".join(line + b"\n" for line in lines[starts[0] + 1:ends[0]])


def checks(core, base, doc):
    """[(name, ok, extra)] for TycoonCore.lua's bytes (core), the file at BASE (base, or None) and the sync doc."""
    out = []

    def add(name, ok, extra=None):
        out.append((name, bool(ok), extra))

    lines = core.split(b"\n")
    base_lines = base.split(b"\n") if base is not None else []
    add("git: TycoonCore.lua at %s can be read (git show %s:TycoonCore.lua; a shallow clone may lack it)" % (BASE, BASE),
        base is not None)
    add("base: at %s, line %d is the save read (local saved, ok = load(player)) and line %d sets data.ready" % (BASE, FIRST, LAST),
        len(base_lines) > LAST and base_lines[FIRST - 1] == b"\tlocal saved, ok = load(player)"
        and base_lines[LAST - 1].startswith(b"\tdata.ready = true"))
    add("base: TycoonCore.lua at %s has no CLAIMLOAD text" % BASE, base is not None and b"CLAIMLOAD" not in base)

    starts, ends = marker_lines(lines, START), marker_lines(lines, END)
    add("markers: exactly one CLAIMLOAD-START line and one CLAIMLOAD-END line, START first",
        len(starts) == 1 and len(ends) == 1 and starts[0] < ends[0], (len(starts), len(ends)))
    add("markers: each marker line is a tab and the marker, nothing else",
        all(lines[i] == b"\t" + START.encode() for i in starts) and all(lines[i] == b"\t" + END.encode() for i in ends))
    head = next((i for i, line in enumerate(lines) if line == b"local function onPlayerAdded(player)"), None)
    tail = next((i for i, line in enumerate(lines) if line == b"Players.PlayerAdded:Connect(onPlayerAdded)"), None)
    add("markers: both are inside onPlayerAdded (after its first line, before Players.PlayerAdded:Connect)",
        head is not None and tail is not None and starts and ends and all(head < i < tail for i in starts + ends))

    block = marked_block(lines)
    want = b"".join(line + b"\n" for line in base_lines[FIRST - 1:LAST]) if len(base_lines) > LAST else None
    add("block: the text between the CLAIMLOAD markers is lines %d-%d of TycoonCore.lua at %s, byte for byte" % (FIRST, LAST, BASE),
        block is not None and want is not None and block == want,
        None if block is None or want is None else "%d bytes, want %d" % (len(block), len(want)))

    named = [line for line in lines if b"CLAIMLOAD" in line]
    add("outside: every line that names CLAIMLOAD is a comment line (no code hides on one)",
        all(line.lstrip(b"\t ").startswith(b"--") for line in named), [line[:60] for line in named])
    stripped = b"\n".join(line for line in lines if b"CLAIMLOAD" not in line)
    add("outside: TycoonCore.lua without its CLAIMLOAD comment lines is TycoonCore.lua at %s, byte for byte (L0 adds comments only)" % BASE,
        base is not None and stripped == base)
    add("file: TycoonCore.lua has no word \"Touched\", comments included (tools/daily_test.py searches the raw text)",
        b"Touched" not in core)

    digest = hashlib.sha256(core).hexdigest()
    add("doc: %s's table row has TycoonCore.lua's real SHA-256 and size (%s, %d bytes)" % (SYNC_DOC, digest[:12], len(core)),
        ("| `TycoonCore` | Script, ServerScriptService | changed | `%s` | %d |" % (digest, len(core))) in doc)
    add("doc: %s's hash block expects TycoonCore.lua's real SHA-256 and size" % SYNC_DOC,
        ('{ "TycoonCore", "Script", "ServerScriptService", "%s", %d },' % (digest, len(core))) in doc)
    return out


def lua_block(doc, heading):
    """The first ```lua block after heading in doc, or "" if there is none."""
    at = doc.find(heading)
    if at < 0:
        return ""
    m = re.search(r"```lua\n(.*?)```", doc[at:], re.S)
    return m.group(1) if m else ""


FAKE_STUDIO = """
local scripts = { TycoonCore = { ClassName = "Script", Source = __SOURCE__ } }
local server = { FindFirstChild = function(_, name) return scripts[name] end }
game = { GetService = function(_, name) if name == "ServerScriptService" then return server end return nil end }
"""


def hash_block_checks(luau, core, doc):
    """docs/STUDIO_SYNC_LOBBY.md's hash block, run in Luau against a fake Studio holding TycoonCore."""
    out = []
    block = lua_block(doc, "## (c) Hash check (command bar)")
    master = lua_block(read("docs/STUDIO_SYNC_MASTER.md"), "## 6. Hash check (command bar)")
    fn = re.compile(r"^local K = \{.*?\nend\n", re.S)
    mine, theirs = fn.search(block), fn.search(master)
    out.append(("doc: the hash block's sha256 is docs/STUDIO_SYNC_MASTER.md section 6's, character for character",
                bool(mine and theirs and mine.group(0) == theirs.group(0)), None))
    text = core.decode("utf-8")
    cases = (("the real file", text, "ALL OK"),
             ("the real file with its last newline dropped (Studio may do that)", text[:-1], "ALL OK"),
             ("a file with one byte changed", text.replace("REREAD_WAIT_SECONDS = 7", "REREAD_WAIT_SECONDS = 8", 1), "NOT YET"))
    for label, source, want in cases:
        result = run_luau(luau, FAKE_STUDIO.replace("__SOURCE__", lua_long_string(source)) + block)
        last = result.stdout.strip().split("\n")[-1] if result.stdout.strip() else result.stderr.strip()[:200]
        out.append(("doc: the hash block, run in Luau on a fake Studio with %s, ends with %s" % (label, want),
                    result.returncode == 0 and last.startswith(want), last))
    return out


def ins_after(anchor, text):
    def apply(core):
        if core.count(anchor) != 1:
            return None
        return core.replace(anchor, anchor + text)
    return apply


def swap(old, new):
    def apply(core):
        if core.count(old) != 1:
            return None
        return core.replace(old, new)
    return apply


def move(piece, before):
    """Removes piece and puts it again just before the anchor before."""
    def apply(core):
        if core.count(piece) != 1:
            return None
        rest = core.replace(piece, "")
        if rest.count(before) != 1:
            return None
        return rest.replace(before, piece + before)
    return apply


LEFT_LOADING = "\tif playerData[player] ~= data then return end -- they left while loading: nothing was saved\n"
LEADERSTATS = ('\tlocal leaderstats = Instance.new("Folder")\n\tleaderstats.Name = "leaderstats"\n\tleaderstats.Parent = player\n\n'
               '\tlocal cash = Instance.new("IntValue")\n\tcash.Name = "Cash"\n\tcash.Parent = leaderstats\n\n'
               '\tlocal income = Instance.new("IntValue")\n\tincome.Name = "Income"\n\tincome.Parent = leaderstats\n\n')
BLOCK_CHECK = "block: the text between the CLAIMLOAD markers is lines %d-%d of TycoonCore.lua at %s, byte for byte" % (FIRST, LAST, BASE)
OUTSIDE_CHECK = "outside: TycoonCore.lua without its CLAIMLOAD comment lines is TycoonCore.lua at %s, byte for byte (L0 adds comments only)" % BASE
COUNT_CHECK = "markers: exactly one CLAIMLOAD-START line and one CLAIMLOAD-END line, START first"
SHAPE_CHECK = "markers: each marker line is a tab and the marker, nothing else"
PLACE_CHECK = "markers: both are inside onPlayerAdded (after its first line, before Players.PlayerAdded:Connect)"
COMMENT_CHECK = "outside: every line that names CLAIMLOAD is a comment line (no code hides on one)"
DOC_ROW_CHECK = "doc: %s's table row has TycoonCore.lua's real SHA-256" % SYNC_DOC

# (what is broken, how, the start of the named check that must fail)
MUTANTS = [
    # The proposal's section 2.1 set: in L0 the byte compare is what catches each one (L3 also runs the block)
    ("the \"left while loading\" check after the read (:775) is removed",
     swap("load(player)\n" + LEFT_LOADING + "\tok = readableSave", "load(player)\n\tok = readableSave"), BLOCK_CHECK),
    ("the \"left while waiting\" check after the re-read wait (:788) is removed",
     swap("\t\ttask.wait(REREAD_WAIT_SECONDS)\n\t\tif playerData[player] ~= data then return end -- they left while waiting: nothing was saved\n",
          "\t\ttask.wait(REREAD_WAIT_SECONDS)\n"), BLOCK_CHECK),
    ("the check after the second read (:790) is removed",
     swap("local again, againOk = load(player)\n\t\tif playerData[player] ~= data then return end\n", "local again, againOk = load(player)\n"),
     BLOCK_CHECK),
    ("the \"left while loading\" check after the setup pcall (:833) is removed",
     swap("\tend)\n" + LEFT_LOADING + "\tif not setupOk", "\tend)\n\tif not setupOk"), BLOCK_CHECK),
    ("data.loaded = ok moved above the check after the setup pcall (:833)",
     move("\tdata.loaded = ok -- from here on, saves are complete\n", "\tend)\n" + LEFT_LOADING), BLOCK_CHECK),
    ("data.loaded = true instead of ok", swap("\tdata.loaded = ok -- from", "\tdata.loaded = true -- from"), BLOCK_CHECK),
    ("leaderstats made after load (the folder and its two values moved below the read)",
     move(LEADERSTATS, "\tif playerData[player] ~= data then return end -- they left while loading: nothing was saved\n\tok = readableSave"),
     BLOCK_CHECK),
    # Spacing inside the block
    ("a line of the block indented with four spaces instead of a tab", swap("\tok = readableSave(", "    ok = readableSave("), BLOCK_CHECK),
    ("a trailing space after refreshSign(player) in the block", swap("\trefreshSign(player)\n\tdata.ready", "\trefreshSign(player) \n\tdata.ready"),
     BLOCK_CHECK),
    ("a CRLF line ending in the block", swap("\tupdateIncome(player)\n\n\t-- Offline", "\tupdateIncome(player)\r\n\n\t-- Offline"), BLOCK_CHECK),
    ("an empty line added inside the block", swap("\tlocal lastSeen = nil\n", "\tlocal lastSeen = nil\n\n"), BLOCK_CHECK),
    # The markers themselves
    ("the START marker one line lower (the read is left outside)",
     swap("\t" + START + "\n\tlocal saved, ok = load(player)\n", "\tlocal saved, ok = load(player)\n\t" + START + "\n"), BLOCK_CHECK),
    ("the END marker one line higher (data.ready is left outside)",
     swap("\tdata.ready = true -- the shop waits for this before granting purchases\n\t" + END + "\n",
          "\t" + END + "\n\tdata.ready = true -- the shop waits for this before granting purchases\n"), BLOCK_CHECK),
    ("a second START marker pasted lower in the block", ins_after("\tlocal lastSeen = nil\n", "\t" + START + "\n"), COUNT_CHECK),
    ("the END marker removed", swap("\t" + END + "\n", ""), COUNT_CHECK),
    ("the markers swapped (END first)",
     lambda core: core.replace("\t" + START + "\n", "\t@@S@@\n").replace("\t" + END + "\n", "\t" + START + "\n").replace("\t@@S@@\n", "\t" + END + "\n")
     if core.count("\t" + START + "\n") == 1 and core.count("\t" + END + "\n") == 1 else None, COUNT_CHECK),
    ("text after the START marker on its line", swap("\t" + START + "\n", "\t" + START + " (the join load)\n"), SHAPE_CHECK),
    ("the END marker moved below Players.PlayerAdded:Connect",
     move("\t" + END + "\n", "for _, existing in ipairs(Players:GetPlayers()) do\n"), PLACE_CHECK),
    # Outside the block
    ("code hidden on a CLAIMLOAD line outside the block (data.loaded = true -- CLAIMLOAD)",
     ins_after("\t" + END + "\n", "\tdata.loaded = true -- CLAIMLOAD\n"), COMMENT_CHECK),
    ("an edit outside the markers (REREAD_WAIT_SECONDS = 7 becomes 0)",
     swap("local REREAD_WAIT_SECONDS = 7\n", "local REREAD_WAIT_SECONDS = 0\n"), OUTSIDE_CHECK),
    ("the CLAIMLOAD note above the markers reworded (comments only: the doc's hash goes stale)",
     swap("byte for byte.)\n\t" + START, "byte by byte.)\n\t" + START), DOC_ROW_CHECK),
]

# The harness must report this as not caught: the checks crash on it (the file is not text), and a crash never counts.
HARNESS_SELF_TEST = ("a mutant that makes the checks crash (TycoonCore.lua is not text)", lambda core: 0, BLOCK_CHECK)


def run_one(core_text, apply, base, doc):
    """(checks, error): the checks for the mutated file, or the error that stopped them (a crash)."""
    mutated = apply(core_text)
    if mutated is None:
        return None, "not applied: its anchor is missing or there twice"
    try:
        return checks(mutated.encode("utf-8"), base, doc), None
    except Exception as e:  # a crash is never a catch
        return None, "it crashed: %s: %s" % (type(e).__name__, e)


def run_mutants(core_text, base, doc, mutants=MUTANTS):
    caught, lines = 0, []
    names = [name for name, _, _ in checks(core_text.encode("utf-8"), base, doc)]
    for label, apply, want in mutants:
        if not any(name.startswith(want) for name in names):
            lines.append("NOT CAUGHT: %s -- no check is named \"%s\"" % (label, want))
            continue
        result, error = run_one(core_text, apply, base, doc)
        if error:
            lines.append("NOT CAUGHT: %s -- %s" % (label, error))
            continue
        failed = [name for name, ok, _ in result if not ok]
        if any(name.startswith(want) for name in failed):
            caught += 1
            lines.append("caught: %s -- by \"%s\"" % (label, next(n for n in failed if n.startswith(want))))
        else:
            lines.append("NOT CAUGHT: %s -- \"%s\" stayed green (failed: %s)" % (label, want, failed))
    return caught, lines


def main():
    luau = os.environ.get("LUAU") or shutil.which("luau")
    if not luau:
        print("Luau not found. Download it from https://github.com/luau-lang/luau/releases and set LUAU=/path/to/luau")
        return 2
    core = read_bytes("TycoonCore.lua")
    base = git_show(BASE, "TycoonCore.lua")
    doc = read(SYNC_DOC) if os.path.exists(os.path.join(ROOT, SYNC_DOC)) else ""
    code = 0

    results = checks(core, base, doc) + hash_block_checks(luau, core, doc)
    failed = [(name, extra) for name, ok, extra in results if not ok]
    for name, extra in failed:
        print("FAIL: " + name + (" -- " + str(extra) if extra is not None else ""))
    print("CLAIMLOAD markers, the block against %s and the Studio sync doc: %d passed, %d failed" % (BASE, len(results) - len(failed), len(failed)))
    if failed:
        code = 1

    if base is None:
        print("FAIL: the mutation runs need TycoonCore.lua at %s (git show)" % BASE)
        return 1
    core_text = core.decode("utf-8")
    caught, lines = run_mutants(core_text, base, doc)
    for line in lines:
        if line.startswith("NOT CAUGHT"):
            print(line)
    print("CLAIMLOAD mutations: %d of %d caught, each by its named check" % (caught, len(MUTANTS)))
    if caught != len(MUTANTS):
        code = 1

    self_caught, self_lines = run_mutants(core_text, base, doc, [HARNESS_SELF_TEST])
    self_ok = self_caught == 0 and "it crashed" in self_lines[0]
    print("Harness self-test (a mutant that crashes the checks never counts): %d of 1 reported as not caught" % (1 if self_ok else 0))
    if not self_ok:
        print("FAIL: the mutation harness counted a mutant that crashed the checks as caught")
        code = 1

    print("lobby_test.py: %d checks passed, %d of %d mutation runs caught" % (len(results) - len(failed), caught, len(MUTANTS)))
    return code


if __name__ == "__main__":
    sys.exit(main())
