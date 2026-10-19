#!/usr/bin/env python3
"""Tests for overhaul 2 phase 5's plaza pieces outside the world builder, outside Studio.

Run:   LUAU=/path/to/luau python3 tools/plaza_test.py

  - the founder activities' window on every phone size (FounderClient's WINDOWLAYOUT block): it fits, 44 px touch targets
  - the join cinematic (IntroClient's INTROPLAN block, run in Luau): about 7 s, from the arch over the fountain and the ring
    to the character; the client code skips on a tap, holds OpenPanel only when free and always gives the camera back
  - the FREE sign (the owner's point 4): a board with a SurfaceGui on both faces, never a BillboardGui or AlwaysOnTop
  - the Roman arch (the owner's point 1) in WorldArt: its size, the archway, the columns, the inscription, solid piers only
  - the VIP Lounge's inside (the owner's point 18): built in pcall, the showcase, nothing that collides or is bought by touch
Broken versions (mutants) must be caught. tools/world_test.py checks the world rules for the arch and the fountain.
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(name, files=None):
    if files and name in files:
        return files[name]
    with open(os.path.join(ROOT, name), encoding="utf-8") as f:
        return f.read()


def between(text, a, b):
    i, j = text.find(a), text.find(b)
    return text[i + len(a):j] if i >= 0 and j > i else None


INTRO_TESTS = r"""
__PLAN__
__WINDOW__
local passed, failed = 0, 0
local function check(name, ok, extra)
	if ok then passed += 1 else failed += 1; print("FAIL: " .. name .. (extra ~= nil and (" -- " .. tostring(extra)) or "")) end
end
local total = introSeconds()
check("intro: about 7 s from the first shot to the landing (6 to 8 s)", total >= 6 and total <= 8, total)
check("intro: it starts on the arch's side (south of the center) looking at the arch", SHOTS[1][3] < -26 and SHOTS[1][6] == -26 and SHOTS[1][7] == 0)
local fountain, high = false, false
for _, shot in ipairs(SHOTS) do
	if shot[6] == 50 and shot[3] >= 20 then fountain = true end
	if shot[2] >= 60 then high = true end
end
check("intro: it flies over the fountain and high over the ring of garages", fountain and high)
check("intro: it lands above and behind the character", LAND_BEHIND[2] > 0 and LAND_BEHIND[3] > 0 and LAND_SECONDS > 0)
-- The activity window (FounderClient's WINDOWLAYOUT block) on every phone size and top bar the call tray is tested with
local screens = { { 320, 568 }, { 360, 640 }, { 375, 667 }, { 390, 844 }, { 667, 375 }, { 568, 320 }, { 640, 360 }, { 812, 375 }, { 844, 390 } }
local cases = { { 4, false, "sprint" }, { 4, true, "bug" }, { 3, false, "pitch, brainstorm" }, { 2, false, "dinner" } }
local fits, touch, inside, apart, why = true, true, true, true, nil
for _, sc in ipairs(screens) do
	for _, bar in ipairs({ 0, 36, 58 }) do
		local W, H = sc[1], sc[2] - bar
		for _, c in ipairs(cases) do
			local L = windowLayout(W, H, c[1], c[2])
			local where = string.format("%dx%d bar %d, %s", sc[1], sc[2], bar, c[3])
			if L.w > W - 8 or L.h > H - 8 then fits, why = false, why or where end
			for i, b in ipairs(L.buttons) do
				if b.h < 44 or b.w < 44 then touch, why = false, why or (where .. ": button " .. i .. " " .. b.w .. "x" .. b.h) end
				if b.x < 0 or b.x + b.w > L.w - 10 or b.y < L.trackY + 6 or b.y + b.h > L.h - 6 then inside, why = false, why or (where .. ": button " .. i) end
				for j = i + 1, #L.buttons do
					local o = L.buttons[j]
					if b.x < o.x + o.w and o.x < b.x + b.w and b.y < o.y + o.h and o.y < b.y + b.h then apart, why = false, why or where end
				end
			end
			if #L.buttons ~= c[1] then inside = false end
		end
	end
end
check("window: fits every phone screen with a top bar of 0, 36 or 58 px", fits, why)
check("window: every button is at least 44 x 44 (a touch target) on every screen", touch, why)
check("window: every button is inside the window, under the timer bar", inside, why)
check("window: no two buttons overlap", apart, why)
local big = windowLayout(1280, 720, 4, false)
check("window: on a big screen it stays 360 x 320 with four rows of 46", big.w == 360 and big.h == 320 and big.buttons[4].h == 46 and big.buttons[1].w == 332)
print(string.format("%d passed, %d failed", passed, failed))
print("DONE")
"""


def run_intro(luau, files=None):
    plan = between(read("IntroClient.lua", files), "-- INTROPLAN-START", "-- INTROPLAN-END") or 'error("INTROPLAN markers not found")'
    window = between(read("FounderClient.lua", files), "-- WINDOWLAYOUT-START", "-- WINDOWLAYOUT-END") or 'error("WINDOWLAYOUT markers not found")'
    with tempfile.NamedTemporaryFile("w", suffix=".luau", delete=False, encoding="utf-8") as f:
        f.write(INTRO_TESTS.replace("__PLAN__", plan).replace("__WINDOW__", window))
        path = f.name
    try:
        r = subprocess.run([luau, path], capture_output=True, text=True, timeout=60)
    finally:
        os.unlink(path)
    fails = [l[6:] for l in r.stdout.splitlines() if l.startswith("FAIL: ")]
    done = r.returncode == 0 and "DONE" in r.stdout.splitlines()
    m = re.search(r"(\d+) passed", r.stdout)
    return (int(m.group(1)) if m else 0), fails, done


def pins(files=None):
    intro, core, lobby_client = read("IntroClient.lua", files), read("TycoonCore.lua", files), read("LobbyClient.lua", files)
    art, shop, config = read("WorldArt.lua", files), read("ShopServer.lua", files), read("LobbyConfig.lua", files)
    build = core[core.find("local function buildGarages("):core.find("\nbuildGarages()\n")]
    state = core[core.find("local function setGarageState("):core.find("-- A Free garage shows today's new-player room")]
    arch = art[art.find("\tArch = {"):art.find("\t-- The plaza's fountain")]
    furnish = shop[shop.find("local function furnishVipLounge()"):shop.find("local RARITY_RANK")]
    out = []

    def add(name, ok):
        out.append((name, bool(ok)))

    add("intro: a tap, a click, a key or a gamepad skips it", "UserInputService.InputBegan:Connect" in intro and "skipped = true" in intro)
    add("intro: it holds OpenPanel only when no window has it and gives it back", 'if playerGui:GetAttribute("OpenPanel") == nil then' in intro
        and 'if tookPanel and playerGui:GetAttribute("OpenPanel") == PANEL_NAME then' in intro)
    add("intro: the camera always goes back to the player's (outside the pcall)", re.search(r"end\)\n\tskip:Disconnect\(\)\n\tcamera\.CameraType = ", intro) is not None)
    add("intro: client only (no remote, no save) and only with the claim on", "InvokeServer" not in intro and "FireServer" not in intro and "if LobbyConfig.ClaimEnabled then" in intro)
    add("fountain: the splash and the sound are the client's, built-in only (no Store asset)", "rbxassetid://" not in intro and "rbxasset://sounds/" in intro)
    add("free sign: buildGarages makes a board with a SurfaceGui on both faces and no BillboardGui on the post",
        '"FreeSign"' in build and "Enum.NormalId.Front, Enum.NormalId.Back" in build and "addLabel(post" not in build)
    add("free sign: setGarageState writes the board's text and shows it", 'claimPart(slot, "FreeSign")' in state and "LobbyConfig.Texts.FreeSign" in state)
    add("free sign: never AlwaysOnTop (TycoonCore's claim spot, LobbyClient's marker)", "AlwaysOnTop = true" not in lobby_client and "AlwaysOnTop" not in build)
    add("free sign: the text says FREE OFFICE and how to claim", re.search(r'FreeSign = "FREE OFFICE[^"]*claim"', config) is not None)
    add("free sign: LobbyClient hides the board on this client once the player has a garage", 'spot:FindFirstChild("FreeSign")' in lobby_client)
    # The arch: about 42 x 34, a 12 x 20 archway, eight columns, the inscription, four solid piers
    add("arch: piers, eight engaged columns (base, shaft, capital), the attic and the inscription in Garamond",
        len(re.findall(r'"Arch(?:Front|Back)(?:In|Out)(?:Left|Right)Shaft"', arch)) == 8 and arch.count("ArchPier") == 4
        and 'font = "Garamond"' in arch and 'value = "BUILD YOUR STARTUP"' in arch)
    tops = [float(m.group(2)) + float(m.group(1)) / 2 for m in re.finditer(r'P\("Arch\w+", "Block", \{ [\d.]+, ([\d.]+), [\d.]+ \}, \{ [-\d.]+, ([\d.]+),', arch)]
    widths = [abs(float(m.group(2))) + float(m.group(1)) / 2 for m in re.finditer(r'P\("Arch\w+", "Block", \{ ([\d.]+), [\d.]+, [\d.]+ \}, \{ ([-\d.]+),', arch)]
    add("arch: about 42 wide and 34 high (a human-scale gate)", tops and 33 <= max(tops) <= 35 and widths and 40 <= 2 * max(widths) <= 44)
    add("arch: the central archway is 12 wide and 20 high (the inner piers at 6, the curve's top at 20)",
        'P("ArchPierInLeft", "Block", { 4, 23, 4 }, { -8,' in arch and 'P("ArchLintel", "Block", { 12, 4, 4 }, { 0, 22, 0 }' in arch)
    add("arch: solid on the four piers only", re.search(r"solid = \{ solid\(4, 24, 4, -8, 0\), solid\(4, 24, 4, 8, 0\), solid\(5, 24, 4, -17\.5, 0\), solid\(5, 24, 4, 17\.5, 0\) \}", arch) is not None)
    add("lounge: its inside is built in a pcall (a failure never stops the shop) and the showcase refreshes on a loop",
        "pcall(furnishVipLounge)" in shop and "pcall(refreshShowcase)" in shop)
    add("lounge: nothing inside collides, is touched or queried (the seats stay the only things to sit on)",
        "part.CanCollide, part.CanTouch, part.CanQuery = false, false, false" in furnish and "Touched" not in furnish and "Seat" not in furnish.replace("SofaBack", "").replace("DinnerChair", ""))
    add("lounge: the showcase board faces the door and the plaza (+Z), the model is anchored and never collides",
        "gui.Face = Enum.NormalId.Back -- faces the door and the plaza (+Z)" in furnish and "part.Anchored, part.CanCollide, part.CanTouch, part.CanQuery = true, false, false, false" in shop)
    add("lounge: still one Touched handler in ShopServer (the door)", shop.count(".Touched:Connect") == 1)
    return out


MUTANTS = [
    ("the window as tall as before (320) on every screen", "FounderClient.lua", "local h = math.min(320, screenH - 16)", "local h = 320",
     "window: fits every phone screen"),
    ("four rows never become a grid on a short screen", "FounderClient.lua", "if not grid and listRow < TOUCH and count == 4 then", "if false then",
     "window: every button is at least 44"),
    ("the intro twice as long", "IntroClient.lua", "{ 0, 95, 10, 0, 0, 30, 1.8 },", "{ 0, 95, 10, 0, 0, 30, 8 },", "intro: about 7 s"),
    ("no skip", "IntroClient.lua", "\t\t\tskipped = true\n", "\n", "intro: a tap"),
    ("the intro steals an open window's OpenPanel", "IntroClient.lua", 'if playerGui:GetAttribute("OpenPanel") == nil then\n\t\tplayerGui:SetAttribute("OpenPanel", PANEL_NAME)',
     'if true then\n\t\tplayerGui:SetAttribute("OpenPanel", PANEL_NAME)', "intro: it holds OpenPanel"),
    ("the marker drawn on top again", "LobbyClient.lua", "\tAlwaysOnTop = false,", "\tAlwaysOnTop = true,", "free sign: never AlwaysOnTop"),
    ("a solid box on the arch's beam", "WorldArt.lua", "solid(5, 24, 4, 17.5, 0) },", "solid(5, 24, 4, 17.5, 0), solid(12, 4, 4, 0, 0) },", "arch: solid on the four piers only"),
    ("the lounge's inside not in a pcall", "ShopServer.lua", "local furnished, why = pcall(furnishVipLounge)", "local furnished, why = true, furnishVipLounge()", "lounge: its inside is built in a pcall"),
]


def main():
    luau = os.environ.get("LUAU") or shutil.which("luau")
    if not luau:
        print("Luau not found. Set LUAU=/path/to/luau")
        return 2
    passed, fails, done = run_intro(luau)
    checks = pins()
    for f in fails:
        print("FAIL: " + f)
    if not done:
        print("CRASH: the intro plan did not run")
    for name, ok in checks:
        if not ok:
            print("FAIL: " + name)
    bad = sum(1 for _, ok in checks if not ok)
    print("Plaza checks: %d passed, %d failed" % (passed + len(checks) - bad, len(fails) + bad + (0 if done else 1)))
    caught = 0
    for label, file, old, new, want in MUTANTS:
        text = read(file)
        if text.count(old) != 1:
            print("NOT CAUGHT: %s -- anchor there %d times" % (label, text.count(old)))
            continue
        files = {file: text.replace(old, new)}
        _, mfails, _ = run_intro(luau, files)
        mfails += [n for n, ok in pins(files) if not ok]
        hit = [f for f in mfails if f.startswith(want)]
        if hit:
            caught += 1
            print("caught: %s -- by \"%s\"" % (label, hit[0]))
        else:
            print("NOT CAUGHT: %s -- %s" % (label, mfails[:3]))
    print("Plaza mutations: %d of %d caught, each by its named check" % (caught, len(MUTANTS)))
    ok = done and not fails and not bad and caught == len(MUTANTS)
    print("plaza_test.py: %s" % ("OK" if ok else "FAILED"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
