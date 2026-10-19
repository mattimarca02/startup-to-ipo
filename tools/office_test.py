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
  - the room (phase 2): every catalog item that is not an old station has its spot in the room of its stage, inside
    the floor and clear of every reserved zone and of the other items; every stage room with all its items passes
    PlotVisuals.check; every furniture piece (a workstation, a station, an item) has one invisible solid box and the
    see-through next desk none; the decor's boxes; setItems / setStage show the room's own items only; the hires' walk in
    (EmployeeServer's pathTo between the PATH markers) never crosses a desk, a station or an item, and EmployeeClient's
    alongPath (WALK markers) follows it;
  - the Studio-only "Reset my save" Debug button (TycoonCore's two debug actions, cut out of the real file): two steps
    within 15 s, nothing saves once it starts (data.loaded off), a running save is waited for, the key is removed in a
    pcall, a failure leaves the save as it was, and the player is kicked to start as new; registered only in Studio.
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


def room_program(sources):
    """The room tests: the real PlotArt, PlotVisuals and OfficeConfig with daily_test.py's fake Roblox (3D math, Instances)."""
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import importlib.util
    spec = importlib.util.spec_from_file_location("daily_test_fake", os.path.join(ROOT, "tools", "daily_test.py"))
    dt = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(dt)
    fake = dt.VISUALS_TESTS[:dt.VISUALS_TESTS.index("local PlotArt = (function()")]
    path = between(sources["EmployeeServer.lua"], "-- PATH-START", "-- PATH-END") or 'error("PATH markers not found")'
    walk = between(sources["EmployeeClient.lua"], "-- WALK-START", "-- WALK-END") or 'error("WALK markers not found")'
    constants = []
    for name in ("FRONT_BAND", "FRONT_AISLE", "INCUBATOR_LINE", "DOOR"):
        m = re.search(r"^local %s = .*$" % name, sources["EmployeeServer.lua"], re.M)
        constants.append(m.group(0) if m else 'error("%s not found")' % name)
    spots = between(sources["EmployeeServer.lua"], "local EMPLOYEE_SPOTS = {", "\n}\n")
    incubators = between(sources["EmployeeServer.lua"], "local INCUBATOR_SPOTS = {", "\n}\n")
    return "\n".join([
        fake,
        "local PlotArt = (function()\n" + sources["PlotArt.lua"] + "\nend)()",
        "local PlotVisuals = (function()\n" + sources["PlotVisuals.lua"] + "\nend)()",
        "local OfficeConfig = (function()\n" + sources["OfficeConfig.lua"].replace(
            'local RunService = game:GetService("RunService")', "local RunService = { IsStudio = function() return false end }") + "\nend)()",
        "\n".join(constants),
        (spots or 'error("EMPLOYEE_SPOTS")') + "\n}",
        (incubators or 'error("INCUBATOR_SPOTS")') + "\n}",
        path, walk, ROOM_TESTS,
    ])


ROOM_TESTS = r"""
local PASS, FAIL = 0, 0
local function check(name, ok, extra)
	if ok then PASS += 1 else FAIL += 1 print_real("FAIL: " .. name .. (extra ~= nil and (" -- " .. tostring(extra)) or "")) end
end
-- The fake's Vector3 has no Magnitude: the walk needs it
V.__index = function(t, k)
	if k == "Magnitude" then return math.sqrt(t.X * t.X + t.Y * t.Y + t.Z * t.Z) end
	return rawget(V, k)
end
local L = PlotArt.Layout
local center = Vector3.new(-135, 0.5, 150)
local function inside(b, x, z) return x > b[1] + 0.01 and x < b[2] - 0.01 and z > b[5] + 0.01 and z < b[6] - 0.01 end
local function overlap(a, b) return a[1] < b[2] - 0.01 and b[1] < a[2] - 0.01 and a[5] < b[6] - 0.01 and b[5] < a[6] - 0.01 end

-- 1. Every catalog item that is not an old station has its spot, in the room of its own stage
do
	local missing, wrong, extra, count = nil, nil, nil, 0
	for _, item in ipairs(OfficeConfig.Items) do
		local look = PlotArt.Items[item.key]
		if PlotArt.Props[item.key] then
			if look then extra = item.key end
		elseif not look then
			missing = missing or item.key
		else
			count += 1
			if look.stage ~= item.stage then wrong = wrong or item.key end
		end
	end
	for key in pairs(PlotArt.Items) do
		if not OfficeConfig.getItem(key) then extra = extra or key end
	end
	check("items: every catalog item that is not one of the six stations has its look and spot in PlotArt.Items", missing == nil and count >= 54, missing or count)
	check("items: each stands in the room of its own stage", wrong == nil, wrong)
	check("items: no look for an unknown key or a station (the stations keep their props)", extra == nil, extra)
	check("items: PlotVisuals.validate finds nothing in the art", #PlotVisuals.validate(PlotArt) == 0, PlotVisuals.validate(PlotArt)[1])
end

-- 2. Every spot: inside the floor, clear of the reserved zones and of the other items of its room
do
	local bad, why = nil, nil
	for stage = 1, #PlotArt.Stages do
		local keys = PlotVisuals.itemsOf(PlotArt, stage)
		local zones = PlotVisuals.zones(L)
		for i, key in ipairs(keys) do
			local b = PlotVisuals.itemBox(PlotArt.Items[key])
			if b[1] < -30 or b[2] > 30 or b[5] < -30 or b[6] > 30 then bad, why = bad or key, why or "outside the floor" end
			for _, z in ipairs(zones) do
				if overlap(b, z.box) then bad, why = bad or key, why or ("in " .. z.kind .. " zone " .. z.name) end
			end
			for j = i + 1, #keys do
				if overlap(b, PlotVisuals.itemBox(PlotArt.Items[keys[j]])) then bad, why = bad or key, why or ("on " .. keys[j]) end
			end
		end
	end
	check("items: every spot is inside the floor, clear of the aisles, the lane, the spawn, the signs, the incubators, the workstations, the stations and the other items",
		bad == nil, tostring(bad) .. ": " .. tostring(why))
end

-- 3. Every stage room with all its items: the room checks, one solid box per furniture piece
local function fullRoom(stage, desks)
	local room = PlotVisuals.buildRoom(nil, center, PlotArt, stage, nil, desks)
	for _, slot in ipairs(L.itemSlots) do
		PlotVisuals.buildProp(room:FindFirstChild("UpgradeProps"), center, PlotArt, slot.name, Vector3.new(slot.x, 0, slot.z))
	end
	for _, key in ipairs(PlotVisuals.itemsOf(PlotArt, stage)) do
		PlotVisuals.buildItem(room:FindFirstChild("UpgradeProps"), center, PlotArt, key)
	end
	return room
end
do
	local clean, cleanWhy, pieces, piecesWhy, ghostOk, decorOk, flagsOk, walkOk, walkWhy = true, nil, true, nil, true, true, true, true, nil
	for stage = 1, #PlotArt.Stages do
		local room = fullRoom(stage, 6) -- six workstations and the see-through seventh
		local probs = PlotVisuals.check(room, center, PlotArt)
		if #probs > 0 then clean, cleanWhy = false, cleanWhy or ("room " .. stage .. ": " .. probs[1]) end
		for _, d in ipairs(room:GetDescendants()) do
			if d:IsA("Model") and (string.find(d.Name, "HireDesk", 1, true) == 1 or d:GetAttribute("Upgrade") or d:GetAttribute("Item")) then
				local n = 0
				for _, c in ipairs(d:GetChildren()) do if c:IsA("BasePart") and c:GetAttribute("Solid") then n += 1 end end
				if d:GetAttribute("Ghost") then
					if n ~= 0 then ghostOk = false end
				elseif n ~= 1 then
					pieces, piecesWhy = false, piecesWhy or (d.Name .. " has " .. n)
				end
			end
			if d:IsA("BasePart") and d:GetAttribute("Solid") then
				if not (d.CanCollide and not d.CanTouch and d.Transparency == 1 and not d.CastShadow and d.Anchored) then flagsOk = false end
			end
		end
		local solids = room:FindFirstChild(PlotVisuals.SOLIDS)
		if not solids or #solids:GetChildren() < 3 then decorOk = false end
		-- nothing solid where a player walks: the lane, the spawn, the aisles, in front of the incubators
		for _, d in ipairs(room:GetDescendants()) do
			if d:IsA("BasePart") and d:GetAttribute("Solid") then
				local p = d.CFrame.Position - center
				local b = { p.X - d.Size.X / 2, p.X + d.Size.X / 2, 0, 1, p.Z - d.Size.Z / 2, p.Z + d.Size.Z / 2 }
				for _, z in ipairs(PlotVisuals.zones(L)) do
					if (z.kind == "lane" or z.kind == "spawn" or z.kind == "aisle" or z.kind == "sign") and overlap(b, z.box) then
						walkOk, walkWhy = false, walkWhy or (d:GetFullName() .. " in " .. z.name)
					end
				end
			end
		end
	end
	check("room: every stage room with all its items, six workstations and the stations passes PlotVisuals.check", clean, cleanWhy)
	check("solids: every furniture piece (a workstation, a station, an item) has exactly one solid box", pieces, piecesWhy)
	check("solids: the see-through next desk has none (walk through it)", ghostOk)
	check("solids: every box collides, is never touched, is invisible, casts no shadow, is anchored", flagsOk)
	check("solids: the decor's furniture has its boxes too (the Solids model, at least 3 per room)", decorOk)
	check("solids: nothing solid in the lane, the spawn, the aisles or on the signs", walkOk, walkWhy)
end

-- 4. setItems and setStage: the room shows its own stage's items, the stations move along
do
	ROOT = newInstance("Folder")
	local folder = newInstance("Folder")
	folder.Parent = ROOT
	SPAWNED = {}
	local plot = PlotVisuals.newPlot(folder, center, PlotArt, nil, 2)
	local owned = { ["Team Table"] = true, ["Gym"] = true, ["Desk"] = true }
	local desk = PlotVisuals.addProp(plot, "Desk", Vector3.new(-23, 0, -10), false)
	PlotVisuals.setItems(plot, owned, "Team Table")
	local props = plot.room:FindFirstChild("UpgradeProps")
	check("setItems: the room shows the owned items of its own stage only", props:FindFirstChild("Team Table") ~= nil and props:FindFirstChild("Gym") == nil)
	check("setItems: a purchase pops in", #SPAWNED == 1 and SPAWNED[1] == PlotVisuals.popIn)
	local before = props:FindFirstChild("Team Table")
	PlotVisuals.setItems(plot, owned)
	check("setItems: running it again changes nothing (every second)", props:FindFirstChild("Team Table") == before and #SPAWNED == 1)
	PlotVisuals.setStage(plot, 5, false)
	props = plot.room:FindFirstChild("UpgradeProps")
	check("setStage: the catalog items are the new room's (the Gym in Series C, no Team Table)", props:FindFirstChild("Gym") ~= nil and props:FindFirstChild("Team Table") == nil)
	check("setStage: the stations move along", desk.Parent == props)
	owned["Gym"] = nil
	PlotVisuals.setItems(plot, owned)
	check("setItems: an item no longer owned (an IPO) goes", props:FindFirstChild("Gym") == nil and desk.Parent == props)
end

-- 5. The walk in: never across a desk, a station or an item; along the path
do
	local blocks = {}
	local r = L.reserve
	for i, spot in ipairs(L.employeeSpots) do
		table.insert(blocks, { name = "workstation " .. i, spot = i, box = { spot[1] - r.deskHalfX, spot[1] + r.deskHalfX, 0, 1, spot[2] - r.hireHalf, spot[2] + r.deskTo } })
	end
	for _, z in ipairs(PlotVisuals.zones(L)) do
		if z.kind == "slot" or z.kind == "sign" then table.insert(blocks, { name = z.kind .. " " .. z.name, box = z.box }) end
	end
	for key, look in pairs(PlotArt.Items) do table.insert(blocks, { name = "item " .. key, box = PlotVisuals.itemBox(look) }) end
	local starts = {}
	for i, s in ipairs(INCUBATOR_SPOTS) do table.insert(starts, { name = "incubator " .. i, at = s }) end
	table.insert(starts, { name = "the door", at = DOOR })
	for i, s in ipairs(EMPLOYEE_SPOTS) do table.insert(starts, { name = "desk " .. i, at = s, fromSpot = true, spot = i }) end
	local ok, why, ends = true, nil, true
	for _, start in ipairs(starts) do
		for target, spot in ipairs(EMPLOYEE_SPOTS) do
			local way = pathTo(start.at, spot, start.fromSpot)
			local last = way[#way]
			if math.abs(last.X - spot.X) > 1e-6 or math.abs(last.Z - spot.Z) > 1e-6 then ends = false end
			for i = 2, #way do
				local a, b = way[i - 1], way[i]
				for k = 0, 40 do
					local x, z = a.X + (b.X - a.X) * k / 40, a.Z + (b.Z - a.Z) * k / 40
					for _, blk in ipairs(blocks) do
						if blk.spot ~= target and blk.spot ~= start.spot and inside(blk.box, x, z) then
							ok, why = false, why or (start.name .. " -> spot " .. target .. " crosses " .. blk.name .. string.format(" at %.1f, %.1f", x, z))
						end
					end
				end
			end
		end
	end
	check("path: every walk ends exactly at the hire's spot", ends)
	check("path: from every incubator, the door and every other desk to every spot, the walk crosses no workstation, station, sign or catalog item", ok, why)
	local way = { Vector3.new(0, 0, 0), Vector3.new(0, 0, 10), Vector3.new(5, 0, 10) }
	local p0 = alongPath(way, 0)
	local p1, step1 = alongPath(way, 12)
	check("alongPath: it starts at the first point and follows the segments", p0 and p0.Z == 0 and p1 and math.abs(p1.X - 2) < 1e-9 and math.abs(p1.Z - 10) < 1e-9 and step1.X > 0)
	check("alongPath: done (nil) past the end, then the hire sits", alongPath(way, 15.5) == nil)
end

print_real(string.format("%d passed, %d failed", PASS, FAIL))
print_real("DONE")
"""

ROOM_MUTANTS = [
    ("an item spot in the walking lane", "PlotArt.lua", '["Router"] = ITEM(1, { x = -14, z = 22.3,', '["Router"] = ITEM(1, { x = 0, z = 16,', "items: every spot is inside the floor"),
    ("an item built without its solid box", "PlotVisuals.lua", '\tmodel:SetAttribute("Item", key)\n\tPlotVisuals.addSolid(model, origin)\n', '\tmodel:SetAttribute("Item", key)\n', "solids: every furniture piece"),
    ("the ghost desk solid", "PlotVisuals.lua", "\t\t\tmodel:SetAttribute(\"Ghost\", true)\n", "\t\t\tmodel:SetAttribute(\"Ghost\", true)\n\t\t\tPlotVisuals.addSolid(model, origin)\n", "solids: the see-through next desk"),
    ("setItems ignores the room's stage", "PlotVisuals.lua", "local want = look.stage == stage and plot.owned ~= nil", "local want = plot.owned ~= nil", "setItems: the room shows the owned items of its own stage only"),
    ("setStage forgets the new room's items", "PlotVisuals.lua", "\t\told:Destroy()\n\tend\n\tPlotVisuals.setItems(plot, nil)\n", "\t\told:Destroy()\n\tend\n", "setStage: the catalog items are the new room's"),
    ("the walk skips the lane (straight across the rows)", "EmployeeServer.lua", "\t\tadd(0, way[#way].Z)\n\t\tadd(0, aisle)\n", "", "path: from every incubator"),
    ("a decor box over the lane", "PlotVisuals.lua", "\t\tif onFloor[g] and makeSolid(", "\t\tif g == keys[1] then makeSolid(model, 'LaneSolid', origin, { -2, 2, 0, 3, 0, 4 }) end\n\t\tif onFloor[g] and makeSolid(", "solids: nothing solid in the lane"),
]


def reset_program(sources):
    """The Reset my save actions, cut out of TycoonCore (the Studio-only block), with a fake store, clock and ShopServer."""
    core = sources["TycoonCore.lua"]
    block = between(core, "if RunService:IsStudio() then\n\tShopServer.addDebugAction(\"BuildingNextStage\"", "\n-- Eggs and employees (milestone 2)")
    return RESET_PRELUDE + "\n" + (block or 'error("the Studio debug block not found")') + "\n" + RESET_TESTS


RESET_PRELUDE = r"""
local PASS, FAIL = 0, 0
local function check(name, ok, extra)
	if ok then PASS += 1 else FAIL += 1 print("FAIL: " .. name .. (extra ~= nil and (" -- " .. tostring(extra)) or "")) end
end
local STUDIO = true
local RunService = { IsStudio = function() return STUDIO end }
local ACTIONS = {}
local ShopServer = { addDebugAction = function(name, fn) ACTIONS[name] = fn end }
local NOW = 100
local os = { clock = function() return NOW end, time = function() return 0 end }
local DELAYED = {}
local SAVING_FOR = 0
local data
local task = {
	wait = function(t) NOW += t or 0; SAVING_FOR -= 1; if SAVING_FOR <= 0 and data then data.saving = false end; return t or 0 end,
	delay = function(t, fn) table.insert(DELAYED, fn) end,
}
local REMOVED, STORE_FAILS, STORE_ON = {}, false, true
local LOADED_WHEN_REMOVED, SAVING_WHEN_REMOVED
local function getStore()
	if not STORE_ON then return nil end
	return { RemoveAsync = function(_, key)
		if STORE_FAILS then error("DataStore request was throttled") end
		LOADED_WHEN_REMOVED, SAVING_WHEN_REMOVED = data.loaded, data.saving
		table.insert(REMOVED, key)
	end }
end
local KICKED
local player = { UserId = 7, Parent = true, Kick = function(_, msg) KICKED = msg end }
local IpoConfig = { Stages = { { name = "Garage" } } }
local function stageOf() return 1 end
local function fresh() data = { loaded = true, ready = true, saving = false } ; REMOVED = {} ; DELAYED = {} ; KICKED = nil end
"""

RESET_TESTS = r"""
check("reset: both steps are Debug actions (Studio)", ACTIONS.ResetSaveArm ~= nil and ACTIONS.ResetSaveConfirm ~= nil)
fresh()
local msg = ACTIONS.ResetSaveConfirm(player, data)
check("reset: Yes without Reset first does nothing", #REMOVED == 0 and data.loaded == true and string.find(msg, "Tap Reset first", 1, true) ~= nil, msg)
fresh()
ACTIONS.ResetSaveArm(player, data)
NOW += 16
msg = ACTIONS.ResetSaveConfirm(player, data)
check("reset: a second tap after 15 s does nothing", #REMOVED == 0 and data.loaded == true, msg)
fresh()
ACTIONS.ResetSaveArm(player, data)
NOW += 3
data.saving = true
SAVING_FOR = 4
msg = ACTIONS.ResetSaveConfirm(player, data)
check("reset: the key player_<UserId> is removed (the store's only key for this player)", #REMOVED == 1 and REMOVED[1] == "player_7", REMOVED[1])
check("reset: nothing saves once it starts (data.loaded off before the removal, and after)", LOADED_WHEN_REMOVED == false and data.loaded == false)
check("reset: a save already running is waited for before the removal", SAVING_WHEN_REMOVED == false)
check("reset: the player is kicked a moment later, to come back as a new player", #DELAYED == 1 and (DELAYED[1]() or true) and KICKED ~= nil and string.find(KICKED, "Stop", 1, true) ~= nil, KICKED)
msg = ACTIONS.ResetSaveConfirm(player, data)
check("reset: one Reset tap allows one removal only", #REMOVED == 1, #REMOVED)
fresh()
STORE_FAILS = true
ACTIONS.ResetSaveArm(player, data)
msg = ACTIONS.ResetSaveConfirm(player, data)
check("reset: a store error leaves the save as it was (saving again, nobody kicked)", data.loaded == true and #DELAYED == 0 and string.find(msg, "unchanged", 1, true) ~= nil, msg)
STORE_FAILS = false
fresh()
STORE_ON = false
ACTIONS.ResetSaveArm(player, data)
msg = ACTIONS.ResetSaveConfirm(player, data)
check("reset: no DataStore (Studio without API access): nothing changes", data.loaded == true and #REMOVED == 0, msg)
print(string.format("%d passed, %d failed", PASS, FAIL))
print("DONE")
"""

RESET_MUTANTS = [
    ("the session keeps saving after the reset (the leave save writes the old save back)", "\t\tdata.loaded = false -- from here on nothing saves this session\n", "",
     "reset: nothing saves once it starts"),
    ("one tap is enough", "\t\tif not armed or os.clock() - armed > RESET_SECONDS then\n", "\t\tif false then\n", "reset: Yes without Reset first"),
    ("a running save not waited for", "\t\twhile data.saving and waited < 10 do\n", "\t\twhile false do\n", "reset: a save already running"),
    ("a failure leaves the session unsaved", "\t\tif not ok then\n\t\t\tdata.loaded = true\n", "\t\tif not ok then\n", "reset: a store error leaves the save"),
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
    names = ("OfficeConfig", "CreatureConfig", "IpoConfig", "SectorConfig", "CompanyConfig", "CompanyServer", "TycoonCore",
             "PlotArt", "PlotVisuals", "EmployeeServer", "EmployeeClient")
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
    rpassed, rfails, rdone, rerr = outcome(run(luau, room_program(sources)))
    for f in rfails:
        print("FAIL: " + f)
    if not rdone:
        print("CRASH (room): " + rerr)
    print("Room checks (phase 2): %d passed, %d failed" % (rpassed, len(rfails) + (0 if rdone else 1)))
    rcaught = 0
    for label, file, old, new, want in ROOM_MUTANTS:
        if sources[file].count(old) != 1:
            print("NOT CAUGHT: %s -- not applied (its anchor is missing or there twice)" % label)
            continue
        mutated = dict(sources)
        mutated[file] = sources[file].replace(old, new)
        _, mfails, mdone, merr = outcome(run(luau, room_program(mutated)))
        hit = [f for f in mfails if f.startswith(want)]
        if not mdone:
            print("NOT CAUGHT: %s -- it crashed: %s" % (label, merr[:200]))
        elif hit:
            rcaught += 1
            print("caught: %s -- by \"%s\"" % (label, hit[0]))
        else:
            print("NOT CAUGHT: %s -- no failing check starts with \"%s\" (failed: %s)" % (label, want, mfails[:3]))
    print("Room mutations: %d of %d caught, each by its named check" % (rcaught, len(ROOM_MUTANTS)))
    spassed, sfails, sdone, serr = outcome(run(luau, reset_program(sources)))
    for f in sfails:
        print("FAIL: " + f)
    if not sdone:
        print("CRASH (reset): " + serr)
    core = sources["TycoonCore.lua"]
    studio_block = between(core, "if RunService:IsStudio() then\n\tShopServer.addDebugAction(\"BuildingNextStage\"", "\n-- Eggs and employees (milestone 2)") or ""
    pins = [
        ("reset: registered only inside TycoonCore's `if RunService:IsStudio()` block (the Debug remote never exists live)",
         core.count('"ResetSaveConfirm"') == 1 and '"ResetSaveConfirm"' in studio_block and core.count('"ResetSaveArm"') == 1 and '"ResetSaveArm"' in studio_block),
        ("reset: ShopServer's Debug handler still refuses outside Studio or with DebugInStudio off",
         "if not RunService:IsStudio() or not ShopConfig.DebugInStudio then" in read("ShopServer.lua")),
        ("reset: the shop's Debug tab asks twice (Reset, then Yes, erase it) and sends both steps",
         all(t in read("ShopClient.lua") for t in ('runDebug("ResetSaveArm")', 'runDebug("ResetSaveConfirm")', '"Yes, erase it"'))),
    ]
    for name, ok in pins:
        if not ok:
            print("FAIL: " + name)
    pins_failed = sum(1 for _, ok in pins if not ok)
    print("Reset my save checks: %d passed, %d failed" % (spassed + len(pins) - pins_failed, len(sfails) + pins_failed + (0 if sdone else 1)))
    scaught = 0
    for label, old, new, want in RESET_MUTANTS:
        if core.count(old) != 1:
            print("NOT CAUGHT: %s -- not applied (its anchor is missing or there twice)" % label)
            continue
        mutated = dict(sources)
        mutated["TycoonCore.lua"] = core.replace(old, new)
        _, mfails, mdone, merr = outcome(run(luau, reset_program(mutated)))
        hit = [f for f in mfails if f.startswith(want)]
        if mdone and hit:
            scaught += 1
            print("caught: %s -- by \"%s\"" % (label, hit[0]))
        else:
            print("NOT CAUGHT: %s -- %s" % (label, merr[:200] if not mdone else mfails[:3]))
    print("Reset mutations: %d of %d caught, each by its named check" % (scaught, len(RESET_MUTANTS)))
    passed += spassed + len(pins) - pins_failed
    caught += scaught
    reset_ok = not sfails and sdone and pins_failed == 0
    total, total_caught, total_mutants = passed + rpassed, caught + rcaught, len(MUTANTS) + len(ROOM_MUTANTS) + len(RESET_MUTANTS)
    print("office_test.py: %d checks passed, %d of %d mutation runs caught" % (total, total_caught, total_mutants))
    return 0 if (not fails and done and not rfails and rdone and reset_ok and total_caught == total_mutants) else 1


if __name__ == "__main__":
    sys.exit(main())
