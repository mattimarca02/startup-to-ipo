#!/usr/bin/env python3
"""Tests for the egg and the hatch reveal (overhaul 2 phase 4, the owner's point 7), outside Studio.

Run:   LUAU=/path/to/luau python3 tools/egg_test.py

It runs EmployeeClient's REVEALPLAN block (how each rarity hatches) with the real CreatureConfig and checks: a common
hatch is short and simple (about 2 s), a legendary one about 6 s with rays, sparkles, a camera shake and a built-in sound,
and every step in between grows with the rarity; only built-in rbxasset sounds; every egg has its pattern colors and the
incubator shows them only with an egg; the reveal never shows odds or chance (D9: the rarity is the server's roll, or the
fixed hire order for restricted players, FR-13). Broken versions (mutants) must be caught. It changes nothing in the game.
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(name):
    with open(os.path.join(ROOT, name), encoding="utf-8") as f:
        return f.read()


def between(text, start, end):
    a, b = text.find(start), text.find(end)
    return text[a + len(start):b] if a >= 0 and b > a else None


TESTS = r"""
local Color3 = { fromRGB = function(r, g, b) return { r = r, g = g, b = b } end, new = function(r, g, b) return { r = r, g = g, b = b } end }
local warn = function() end
local CreatureConfig = (function()
__CREATURECONFIG__
end)()
__PLAN__
local passed, failed = 0, 0
local function check(name, ok, extra)
	if ok then passed += 1 else failed += 1; print("FAIL: " .. name .. (extra ~= nil and (" -- " .. tostring(extra)) or "")) end
end
local order = { "Common", "Uncommon", "Rare", "Epic", "Legendary" }
local every = true
for _, rarity in ipairs(CreatureConfig.Rarities) do
	if REVEAL_PLAN[rarity.key] == nil then every = false end
end
check("plan: every rarity of CreatureConfig has its own hatch", every and #CreatureConfig.Rarities == 5)
local common, legendary = revealSeconds(revealPlan("Common")), revealSeconds(revealPlan("Legendary"))
check("plan: a common hatch is short and simple (1 to 2 s to the card, no rays, no sparkles, no shake, no sound)",
	common >= 1 and common <= 2 and not revealPlan("Common").rays and revealPlan("Common").sparks == 0 and revealPlan("Common").shake == 0 and revealPlan("Common").sound == nil, common)
check("plan: a legendary hatch takes about 6 s (5 to 6.5 s to the card)", legendary >= 5 and legendary <= 6.5, legendary)
local grows, why = true, nil
for i = 2, #order do
	local a, b = revealPlan(order[i - 1]), revealPlan(order[i])
	if not (revealSeconds(b) > revealSeconds(a) and b.sparks >= a.sparks and b.shake >= a.shake and b.build >= a.build) then grows, why = false, order[i] end
end
check("plan: each rarer hatch is longer and bigger (time, build-up, sparkles, shake)", grows, why)
local L = revealPlan("Legendary")
check("plan: the legendary has rays, sparkles, a camera shake and the victory sound", L.rays and L.sparks >= 20 and L.shake >= 1 and L.sound == "rbxasset://sounds/victory.wav")
check("plan: rays from Rare up, a shake only for Epic and Legendary", revealPlan("Rare").rays and not revealPlan("Uncommon").rays and revealPlan("Rare").shake == 0 and revealPlan("Epic").shake > 0)
local soundsOk = true
for _, plan in pairs(REVEAL_PLAN) do
	if plan.sound ~= nil and not string.find(plan.sound, "^rbxasset://sounds/") then soundsOk = false end
end
check("plan: only built-in rbxasset sounds (no Store asset)", soundsOk)
check("plan: an unknown rarity hatches like a common one", revealPlan("Mythic") == revealPlan("Common"))
local colors = true
for _, egg in ipairs(CreatureConfig.Eggs) do
	if type(egg.band) ~= "table" or type(egg.spots) ~= "table" or type(egg.color) ~= "table" then colors = false end
end
check("eggs: every egg has its color, band and spots", colors and #CreatureConfig.Eggs == 3)
print(string.format("%d passed, %d failed", passed, failed))
print("DONE")
"""


def program(files=None):
    files = files or {}
    client = files.get("EmployeeClient.lua") or read("EmployeeClient.lua")
    plan = between(client, "-- REVEALPLAN-START", "-- REVEALPLAN-END") or 'error("REVEALPLAN markers not found")'
    config = files.get("CreatureConfig.lua") or read("CreatureConfig.lua")
    return TESTS.replace("__CREATURECONFIG__", config).replace("__PLAN__", plan)


def run(luau, source):
    with tempfile.NamedTemporaryFile("w", suffix=".luau", delete=False, encoding="utf-8") as f:
        f.write(source)
        path = f.name
    try:
        return subprocess.run([luau, path], capture_output=True, text=True, timeout=60)
    finally:
        os.unlink(path)


def outcome(result):
    fails = [line[6:] for line in result.stdout.splitlines() if line.startswith("FAIL: ")]
    done = result.returncode == 0 and "DONE" in result.stdout.splitlines()
    m = re.search(r"(\d+) passed", result.stdout)
    return (int(m.group(1)) if m else 0), fails, done, result.stderr[-300:]


def source_pins(files=None):
    files = files or {}
    client = files.get("EmployeeClient.lua") or read("EmployeeClient.lua")
    server = files.get("EmployeeServer.lua") or read("EmployeeServer.lua")
    reveal = client[client.find("local function playReveal("):client.find("local function onClickReveal()")]
    refresh = server[server.find("local function refreshIncubator("):server.find("-- Hatching ---")]
    return [
        ("reveal: the egg is a 3D oval with its band and spots, in the egg's colors", "MeshType = Enum.MeshType.Sphere" in client and "egg.band" in client and "egg.spots" in client),
        ("reveal: the hatch follows the creature's rarity (revealPlan), never a chance text",
         "local plan = revealPlan(creature.rarity)" in reveal
         and not any(re.search(r"(?i)odds|chance|luck|%", lit) for lit in re.findall(r'"([^"\n]*)"', reveal))),
        ("reveal: no Store asset (no rbxassetid in EmployeeClient)", "rbxassetid://" not in client),
        ("reveal: the camera shake is undone (UnbindFromRenderStep) and a broken reveal cleans it up",
         client.count('UnbindFromRenderStep("HatchShake")') >= 2),
        ("reveal: the window rules stay (HATCHPANEL block, OpenPanel held first and given back)", "-- HATCHPANEL-START" in client and "setRevealShowing(true)" in reveal and "setRevealShowing(false)" in reveal),
        ("incubator: the egg's band and spots show only with an egg, in its colors",
         "parts.band.Transparency = egg and 0 or 1" in refresh and "dot.Color = egg and egg.spots or WHITE" in refresh),
        ("incubator: the pattern never collides, is touched or is queried",
         "part.CanCollide, part.CanTouch, part.CanQuery, part.CastShadow = false, false, false, false" in server),
    ]


MUTANTS = [
    ("the legendary is as short as a common", "EmployeeClient.lua", "Legendary = { wobbles = 16, wobble = 0.14, build = 3.0,", "Legendary = { wobbles = 8, wobble = 0.12, build = 0,",
     "plan: a legendary hatch takes about 6 s"),
    ("the common gets the light show", "EmployeeClient.lua", "Common = { wobbles = 8, wobble = 0.12, build = 0, rays = false, sparks = 0,",
     "Common = { wobbles = 8, wobble = 0.12, build = 0, rays = true, sparks = 30,", "plan: a common hatch is short and simple"),
    ("a Store sound", "EmployeeClient.lua", 'sound = "rbxasset://sounds/victory.wav"', 'sound = "rbxassetid://12345"', "plan: the legendary has rays"),
    ("an epic shorter than a rare", "EmployeeClient.lua", "Epic = { wobbles = 12, wobble = 0.13, build = 1.8,", "Epic = { wobbles = 2, wobble = 0.13, build = 0.1,",
     "plan: each rarer hatch is longer"),
    ("the pattern shows on an empty incubator", "EmployeeServer.lua", "parts.band.Transparency = egg and 0 or 1", "parts.band.Transparency = 0",
     "incubator: the egg's band"),
    ("the reveal ignores the rarity", "EmployeeClient.lua", "local plan = revealPlan(creature.rarity)", "local plan = revealPlan(\"Legendary\")",
     "reveal: the hatch follows the creature's rarity"),
]


def main():
    luau = os.environ.get("LUAU") or shutil.which("luau")
    if not luau:
        print("Luau not found. Set LUAU=/path/to/luau")
        return 2
    passed, fails, done, err = outcome(run(luau, program()))
    pins = source_pins()
    for f in fails:
        print("FAIL: " + f)
    if not done:
        print("CRASH: " + err)
    for name, ok in pins:
        if not ok:
            print("FAIL: " + name)
    bad = sum(1 for _, ok in pins if not ok)
    print("Egg checks: %d passed, %d failed" % (passed + len(pins) - bad, len(fails) + bad + (0 if done else 1)))
    caught = 0
    for label, file, old, new, want in MUTANTS:
        text = read(file)
        if text.count(old) != 1:
            print("NOT CAUGHT: %s -- anchor there %d times" % (label, text.count(old)))
            continue
        files = {file: text.replace(old, new)}
        _, mfails, _, _ = outcome(run(luau, program(files)))
        mfails += [n for n, ok in source_pins(files) if not ok]
        hit = [f for f in mfails if f.startswith(want)]
        if hit:
            caught += 1
            print("caught: %s -- by \"%s\"" % (label, hit[0]))
        else:
            print("NOT CAUGHT: %s -- %s" % (label, mfails[:3]))
    print("Egg mutations: %d of %d caught, each by its named check" % (caught, len(MUTANTS)))
    ok = done and not fails and not bad and caught == len(MUTANTS)
    print("egg_test.py: %s" % ("OK" if ok else "FAILED"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
