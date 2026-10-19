#!/usr/bin/env python3
"""Logic tests for the office of overhaul 2 (docs/OVERHAUL2_PLAN.md), outside Studio.

Run:   LUAU=/path/to/luau python3 tools/office_test.py

It runs the real OfficeConfig, CreatureConfig, IpoConfig, CompanyConfig, SectorConfig and CompanyServer with a fake
Roblox, and TycoonCore's own setupOffice / officeToSave cut out of the real file, and checks:
  - the catalog: at least 60 items over the six stages, the six old upgrade keys kept (saves hold them in `owned`),
    unique keys, the Desk first and free, prices that grow inside a stage, no odds words (D9);
  - the ladder: six stages in IpoConfig with the owner's thresholds (30K, 10M, 100M, 300M, 1B) and one building each;
  - the pure checks (checkItem, checkBuilding, checkDesk): the stage lock, the Desk first, Cash, one step at a time;
  - workstations: 5 without the pass (1 free + 4 bought), the Extra Employee Slots pass is always +3 (never less), 11 at most;
  - direct hires: only common and uncommon, a fixed creature each (no roll), at least 3x what an egg pays on average;
  - the save: the `office` section (a legacy save gets the old 5 slots, a new player none, bad values warned about,
    unknown fields written back at the same level) and the one-time building move in CompanyServer (a save keeps the
    building its old stage showed, never twice, an IPO starts the Garage again, a locked pokedex is never changed).
Then it breaks the code on purpose (mutants): each must be caught by a named check, never by a crash.
It changes nothing in the game or in Studio.
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
    i = text.find(start)
    j = text.find(end, i + 1) if i >= 0 else -1
    return text[i:j] if i >= 0 and j >= 0 else None


def lua_long(text):
    level = 0
    while ("]" + "=" * level + "]") in text:
        level += 1
    return "[" + "=" * level + "[\n" + text + "]" + "=" * level + "]"


PRELUDE = r"""
local PASS, FAIL = 0, 0
local function check(name, ok, extra)
	if ok then PASS += 1 else FAIL += 1 print("FAIL: " .. name .. (extra ~= nil and (" -- " .. tostring(extra)) or "")) end
end
local WARNINGS = {}
warn = function(...) table.insert(WARNINGS, table.concat({ ... }, " ")) end
Color3 = { fromRGB = function(r, g, b) return { r, g, b } end, new = function(r, g, b) return { r, g, b } end }
Vector3 = { new = function(x, y, z) return { X = x, Y = y, Z = z } end }
typeof = function(v) return type(v) end
local RunService = { IsStudio = function() return false end }
local modules = {}
local folder = { WaitForChild = function(_, name) return modules[name] or error("no module " .. name) end, FindFirstChild = function(_, name) return modules[name] end }
game = { GetService = function(_, name)
	if name == "RunService" then return RunService end
	if name == "ReplicatedStorage" then return folder end
	return {}
end }
Instance = { new = function() return setmetatable({}, { __newindex = rawset }) end }
local function load(name, source)
	local fn = assert(loadstring(source, "=" .. name))
	local env = setmetatable({ script = { Parent = folder }, require = function(m) return m end }, { __index = getfenv(1) })
	setfenv(fn, env)
	local value = fn()
	modules[name] = value
	return value
end
"""


def program(sources):
    core = sources["TycoonCore.lua"]
    office_fns = between(core, "-- The `office` section as it is saved (overhaul 2)", "-- BUILDSAVE-START")
    setup_fn = between(core, "-- The `office` save section (overhaul 2, rule A10", "-- Moves a player into a garage")
    parts = [PRELUDE]
    for name in ("OfficeConfig", "CreatureConfig", "IpoConfig", "SectorConfig", "CompanyConfig", "CompanyServer"):
        parts.append('local %s = load("%s", %s)' % (name, name, lua_long(sources[name + ".lua"])))
    parts.append("local CORE_OFFICE = %s" % lua_long((office_fns or 'error("officeToSave not found")') + "\n"
                                                    + (setup_fn or 'error("setupOffice not found")') + "\nreturn officeToSave, setupOffice\n"))
    parts.append(TESTS)
    return "\n".join(parts)


TESTS = r"""
-- 1. The catalog ---------------------------------------------------------------------------------------------------
local items = OfficeConfig.Items
check("catalog: at least 60 items", #items >= 60, #items)
local perStage, keys, dup = {}, {}, nil
for i, item in ipairs(items) do
	perStage[item.stage] = (perStage[item.stage] or 0) + 1
	if keys[item.key] then dup = item.key end
	keys[item.key] = i
end
check("catalog: every key is unique", dup == nil, dup)
local everyStage = true
for s = 1, 6 do if (perStage[s] or 0) < 8 then everyStage = false end end
check("catalog: each of the six stages has at least 8 items", everyStage)
for _, old in ipairs({ "Desk", "Coffee Machine", "Laptop", "Server Rack", "Whiteboard", "Neon Logo" }) do
	check("catalog: the old upgrade " .. old .. " is still a key (saves hold it in owned) and a Garage item", keys[old] ~= nil and items[keys[old]].stage == 1)
end
check("catalog: the Desk is the first item and free", items[1].key == "Desk" and items[1].price == 0 and OfficeConfig.FirstItem == "Desk")
local growing = true
for i = 2, #items do
	if items[i].stage == items[i - 1].stage and items[i].price < items[i - 1].price then growing = false end
	if items[i].stage < items[i - 1].stage then growing = false end
end
check("catalog: listed stage by stage, prices growing inside a stage", growing)
local realEffect = true
for _, item in ipairs(items) do
	local e = item.effect
	if item.income <= 0 and not (type(e) == "table" and next(e) ~= nil) then realEffect = false end
end
check("catalog: every item gives something (income or an effect)", realEffect)
local oddsWords = nil
for _, item in ipairs(items) do
	local t = string.lower(item.key .. " " .. item.text)
	for _, w in ipairs({ "odds", "chance", "random", "luck" }) do if string.find(t, w) then oddsWords = item.key end end
end
check("catalog: no text claims odds or chance (D9)", oddsWords == nil, oddsWords)

-- 2. The ladder ----------------------------------------------------------------------------------------------------
local want = { 0, 30000, 10000000, 100000000, 300000000, 1000000000 }
local keysWant = { "Garage", "Seed", "SeriesA", "SeriesB", "SeriesC", "IpoReady" }
local ladderOk = #IpoConfig.Stages == 6
for s = 1, 6 do
	local st = IpoConfig.Stages[s]
	if not st or st.valuation ~= want[s] or st.key ~= keysWant[s] then ladderOk = false end
end
check("ladder: six stages with the owner's thresholds (Seed 30K, Series A 10M, Series B 100M, Series C 300M, IPO 1B)", ladderOk)
check("ladder: one building per stage, the Garage free", #OfficeConfig.Buildings == 6 and OfficeConfig.Buildings[1].price == 0)
local bOk = true
for s = 2, 6 do
	local b, a = OfficeConfig.Buildings[s], OfficeConfig.Buildings[s - 1]
	if b.stage ~= s or b.price <= a.price or b.office < a.office or b.team < a.team then bOk = false end
end
check("ladder: each building costs more and multiplies at least as much as the one before", bOk)
check("ladder: a building's price is a share of its round's threshold (between 10% and 60%)", (function()
	for s = 2, 6 do local r = OfficeConfig.Buildings[s].price / want[s] if r < 0.1 or r > 0.6 then return false end end return true end)())

-- 3. The pure checks -----------------------------------------------------------------------------------------------
local owned = {}
check("checkItem: a number out of range is refused", OfficeConfig.checkItem(0, 6, owned, 1e12) == nil and OfficeConfig.checkItem(#items + 1, 6, owned, 1e12) == nil
	and OfficeConfig.checkItem(1.5, 6, owned, 1e12) == nil and OfficeConfig.checkItem("1", 6, owned, 1e12) == nil)
local _, r1 = OfficeConfig.checkItem(2, 1, owned, 1e12)
check("checkItem: anything else before the Desk is refused", r1 ~= nil and string.find(r1, "Desk") ~= nil, r1)
check("checkItem: the Desk is free at the Garage", OfficeConfig.checkItem(1, 1, owned, 0) ~= nil)
owned.Desk = true
check("checkItem: an owned item is refused", OfficeConfig.checkItem(1, 1, owned, 1e12) == nil)
local seedIndex
for i, item in ipairs(items) do if item.stage == 2 then seedIndex = seedIndex or i end end
local _, r2 = OfficeConfig.checkItem(seedIndex, 1, owned, 1e12)
check("checkItem: a Seed item at the Garage is refused (Unlocks at Seed)", r2 ~= nil and string.find(r2, "Unlocks at Seed") ~= nil, r2)
check("checkItem: a Seed item at Seed with the Cash is allowed", OfficeConfig.checkItem(seedIndex, 2, owned, items[seedIndex].price) ~= nil)
check("checkItem: one Cash short is refused", OfficeConfig.checkItem(seedIndex, 2, owned, items[seedIndex].price - 1) == nil)
check("checkItem: any order inside the stages reached (the last Garage item before the second)", OfficeConfig.checkItem(perStage[1], 1, owned, 1e12) ~= nil)
check("checkBuilding: the Small Office needs Seed", OfficeConfig.checkBuilding(1, 1, 1e12) == nil and OfficeConfig.checkBuilding(1, 2, 1e12) ~= nil)
check("checkBuilding: one step at a time (never the Big Office from the Garage)", select(2, OfficeConfig.checkBuilding(1, 6, 1e12)) == 2)
check("checkBuilding: Cash is checked", OfficeConfig.checkBuilding(1, 2, OfficeConfig.Buildings[2].price - 1) == nil)
check("checkBuilding: nothing after the HQ Tower", OfficeConfig.checkBuilding(6, 6, 1e12) == nil)
check("checkDesk: desk 2 at the Garage, Cash checked", OfficeConfig.checkDesk(0, 1, OfficeConfig.Bought[1].price, 1) ~= nil and OfficeConfig.checkDesk(0, 1, OfficeConfig.Bought[1].price - 1, 1) == nil)
check("checkDesk: a desk waits for its stage", OfficeConfig.checkDesk(2, 1, 1e12, 3) == nil and OfficeConfig.checkDesk(2, OfficeConfig.Bought[3].stage, 1e12, 3) ~= nil)
check("checkDesk: never more than four bought, never past 11 workstations", OfficeConfig.checkDesk(4, 6, 1e12, 5) == nil and OfficeConfig.checkDesk(0, 6, 1e12, 11) == nil)

-- 4. Workstations and the pass -------------------------------------------------------------------------------------
check("workstations: 1 free, 5 with every desk bought (the old 5 base slots)", OfficeConfig.workstations(0, 0) == 1 and OfficeConfig.workstations(4, 0) == 5)
local passOk = true
for bought = 0, 4 do
	for perk = 0, 3 do
		local without, with = OfficeConfig.workstations(bought, perk), OfficeConfig.workstations(bought, perk + 3)
		if with - without ~= 3 then passOk = false end
	end
end
check("workstations: the Extra Employee Slots pass is always +3, whatever was bought (it never loses value)", passOk)
check("workstations: 11 at most (every desk, the pass and the three perk levels)", OfficeConfig.workstations(4, 6) == 11 and OfficeConfig.workstations(99, 99) == 11)

-- 5. Direct hires ----------------------------------------------------------------------------------------------------
local hires = OfficeConfig.hireList(CreatureConfig)
local hiresOk, rarities = #hires > 0, {}
for _, h in ipairs(hires) do
	local c = CreatureConfig.getCreature(h.creature)
	if not c or c.rarity ~= h.rarity or h.price < 3 * h.eggAverage then hiresOk = false end
	rarities[h.rarity] = true
end
check("hires: a fixed creature each, priced at 3x or more what an egg pays on average", hiresOk)
check("hires: only common and uncommon kinds", rarities.Common and rarities.Uncommon and not rarities.Rare and not rarities.Epic and not rarities.Legendary)
local again = OfficeConfig.hireList(CreatureConfig)
check("hires: the same list every time (no roll)", #again == #hires and again[1].price == hires[1].price and again[#again].creature == hires[#hires].creature)

-- 6. The `office` section -------------------------------------------------------------------------------------------
local officeToSave, setupOffice
do
	local env = setmetatable({ OfficeConfig = OfficeConfig, EmployeeServer = { refreshCapacity = function() end } }, { __index = getfenv(1) })
	local f = assert(loadstring(CORE_OFFICE, "=TycoonCore office"))
	setfenv(f, env)
	officeToSave, setupOffice = f()
end
local P = { Name = "Ann" }
local d1 = { owned = {} }
setupOffice(P, d1, { cash = 5 }) -- a save from before overhaul 2
check("office: a save from before overhaul 2 gets 4 bought desks (its old 5 base slots)", d1.office.desks == 4)
local d2 = { owned = {} }
setupOffice(P, d2, nil)
check("office: a new player has none (1 free desk)", d2.office.desks == 0)
local d3 = { owned = {} }
setupOffice(P, d3, { office = { v = 1, desks = 2, future = { x = 1 } } })
local saved3 = officeToSave(d3)
check("office: a saved count loads", d3.office.desks == 2)
check("office: an unknown field is written back at the same level", type(saved3.future) == "table" and saved3.future.x == 1 and saved3.desks == 2 and saved3.extra == nil)
local w0 = #WARNINGS
local d4 = { owned = {} }
setupOffice(P, d4, { office = { desks = "lots" } })
check("office: a bad count gets 0 with a warning", d4.office.desks == 0 and #WARNINGS > w0)
local d5 = { owned = {} }
setupOffice(P, d5, { office = { desks = 99 } })
check("office: a count over four is clamped", d5.office.desks == 4)
local d6 = { owned = {} }
setupOffice(P, d6, { office = { v = 7, desks = 1 } })
check("office: a newer version number is kept", officeToSave(d6).v == 7)

-- 7. The one-time building move (CompanyServer) ---------------------------------------------------------------------
CompanyServer.init({ getData = function() end, save = function() end, plotZones = function() end })
local function setup(valuation, count, pokedex)
	local data = { ipo = { valuation = valuation, count = count } }
	CompanyServer.setupPlayer({ Name = "Bob" }, data, pokedex)
	return data
end
local a = setup(0, 0, nil)
check("move: a new player starts in the Garage", CompanyServer.getBuilding(a) == 1)
local b = setup(7000, 0, nil) -- old Series A (6,300), no pokedex yet
check("move: a save at the old Series A keeps the Big Office it saw", CompanyServer.getBuilding(b) == 3)
local saved = CompanyServer.serialize(b)
check("move: the mark is saved (o2 = 1)", type(saved) == "table" and type(saved.active) == "table" and saved.active.o2 == 1)
local c = setup(5e9, 0, saved) -- later, a huge valuation of the new economy
check("move: it never runs twice (a later big valuation gives nothing for free)", CompanyServer.getBuilding(c) == 3)
local e = setup(1e6, 1, nil) -- old IPO-ready after 1 IPO is 202,500
check("move: the old stage counts the IPOs (x2.5 each)", CompanyServer.getBuilding(e) == 5)
check("move: setBuilding changes it; an IPO starts the Garage again", CompanyServer.setBuilding(c, 4) and CompanyServer.getBuilding(c) == 4
	and (function() CompanyServer.onIpo(c, 1) return CompanyServer.getBuilding(c) == 1 end)())
local payload = { pokedex = CompanyServer.serialize(b) }
CompanyServer.writeIpoRun(b, payload, 1)
check("move: the IPO's save carries the Garage too", payload.pokedex.active.building == 1)
local locked = setup(7000, 0, { v = 99, active = { building = 4 } })
check("move: a locked (newer) pokedex is never changed, its building is read", CompanyServer.getBuilding(locked) == 4 and not CompanyServer.setBuilding(locked, 5))

print(string.format("%d passed, %d failed", PASS, FAIL))
print("DONE")
"""

MUTANTS = [
    # (what is broken, file, old, new, the start of the check that must fail)
    ("the pass counted inside the old 5 (it would lose value with every desk bought)", "OfficeConfig.lua",
     "OfficeConfig.FreeDesks + math.clamp(bought or 0, 0, #OfficeConfig.Bought) + (extra or 0))",
     "math.max(OfficeConfig.FreeDesks + math.clamp(bought or 0, 0, #OfficeConfig.Bought), extra or 0))", "workstations: the Extra Employee Slots pass"),
    ("no stage lock on items", "OfficeConfig.lua", "\tif stage < item.stage then\n\t\treturn nil, OfficeConfig.unlockText(item.stage)", "\tif false then\n\t\treturn nil, OfficeConfig.unlockText(item.stage)", "checkItem: a Seed item at the Garage"),
    ("buildings may skip a step", "OfficeConfig.lua", "\tlocal nextNumber = current + 1\n", "\tlocal nextNumber = math.max(current + 1, stage)\n", "checkBuilding: one step at a time"),
    ("hires as cheap as an egg", "OfficeConfig.lua", "OfficeConfig.HireFactor = 4", "OfficeConfig.HireFactor = 1", "hires: a fixed creature each"),
    ("a legacy save treated as new (its team would shrink)", "TycoonCore.lua", "\tif saved ~= nil and section == nil then\n\t\toffice.desks = OfficeConfig.LegacyDesks", "\tif false then\n\t\toffice.desks = OfficeConfig.LegacyDesks", "office: a save from before overhaul 2"),
    ("unknown office fields dropped", "TycoonCore.lua", "\t\tif out[key] == nil then\n\t\t\tout[key] = value", "\t\tif false then\n\t\t\tout[key] = value", "office: an unknown field"),
    ("the move runs every load", "CompanyServer.lua", "if typeof(active) == \"table\" and active.o2 == nil then", "if typeof(active) == \"table\" then", "move: it never runs twice"),
    ("the IPO keeps the building", "CompanyServer.lua", "\t\tstate.section.active.building = 1 -- overhaul 2: a new run starts in the Garage", "\t\tlocal _ = 1", "move: setBuilding changes it"),
]


def run(luau, source):
    with tempfile.NamedTemporaryFile("w", suffix=".luau", delete=False, encoding="utf-8") as f:
        f.write(source)
        path = f.name
    try:
        return subprocess.run([luau, path], capture_output=True, text=True, timeout=120)
    finally:
        os.unlink(path)


def outcome(result):
    fails = [line[6:] for line in result.stdout.splitlines() if line.startswith("FAIL: ")]
    m = re.search(r"(\d+) passed, (\d+) failed", result.stdout)
    done = result.returncode == 0 and "DONE" in result.stdout.splitlines()
    return (int(m.group(1)) if m else 0), fails, done, result.stderr.strip()[-300:]


def main():
    luau = os.environ.get("LUAU") or shutil.which("luau")
    if not luau:
        print("Luau not found. Download it from https://github.com/luau-lang/luau/releases and set LUAU=/path/to/luau")
        return 2
    names = ("OfficeConfig", "CreatureConfig", "IpoConfig", "SectorConfig", "CompanyConfig", "CompanyServer", "TycoonCore")
    sources = {n + ".lua": read(n + ".lua") for n in names}
    passed, fails, done, err = outcome(run(luau, program(sources)))
    for f in fails:
        print("FAIL: " + f)
    if not done:
        print("CRASH: " + err)
    print("Office checks: %d passed, %d failed" % (passed, len(fails) + (0 if done else 1)))
    caught = 0
    for label, file, old, new, want in MUTANTS:
        if sources[file].count(old) != 1:
            print("NOT CAUGHT: %s -- not applied (its anchor is missing or there twice)" % label)
            continue
        mutated = dict(sources)
        mutated[file] = sources[file].replace(old, new)
        _, mfails, mdone, merr = outcome(run(luau, program(mutated)))
        hit = [f for f in mfails if f.startswith(want)]
        if not mdone:
            print("NOT CAUGHT: %s -- it crashed: %s" % (label, merr[:200]))
        elif hit:
            caught += 1
            print("caught: %s -- by \"%s\"" % (label, hit[0]))
        else:
            print("NOT CAUGHT: %s -- no failing check starts with \"%s\" (failed: %s)" % (label, want, mfails[:3]))
    print("Office mutations: %d of %d caught, each by its named check" % (caught, len(MUTANTS)))
    print("office_test.py: %d checks passed, %d of %d mutation runs caught" % (passed, caught, len(MUTANTS)))
    return 0 if (not fails and done and caught == len(MUTANTS)) else 1


if __name__ == "__main__":
    sys.exit(main())
