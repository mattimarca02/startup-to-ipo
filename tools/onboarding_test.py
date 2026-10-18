#!/usr/bin/env python3
"""Logic tests for the goal tracker's goals (OnboardingServer.lua + OnboardingConfig.lua), outside Studio.

Run:   python3 tools/onboarding_test.py
       LUAU=/path/to/luau python3 tools/onboarding_test.py

It runs the real OnboardingServer, OnboardingConfig, IpoConfig and TaskConfig with a fake Roblox (fake clock,
fake players, a fake garage) and checks the goal chain (docs/GAMEPLAY_FIRST_HOUR_PROPOSAL.md section 4):
the goal kinds, which goals the tracker shows (OnboardingConfig.ShowAtOnce at a time, a just-finished goal
keeps its place for DoneShowSeconds), that goals finish while hidden, that the call goals are skipped while
calls don't run, that ChainEnabled = false keeps today's two goals exactly, and that the save keeps every
finished key. It also checks the M5 review's F4 (a save with progress and no free egg on record is legacy),
F7 (the free-egg toast waits for data.ready) and F9 (bad saved values are warned about). Then it breaks the server on purpose (mutants) and checks that a named check catches each one.
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


def upgrade_names():
    """The upgrade names in TycoonCore's UPGRADES list."""
    text = read("TycoonCore.lua")
    block = text[text.index("local UPGRADES = {"):]
    block = block[:block.index("\n}")]
    return re.findall(r'name = "([^"]+)"', block)


PRELUDE = r"""
local NOW = 20000 * 86400 + 12 * 3600
local IS_STUDIO = false
local WARNINGS = {}
local function warn(...) table.insert(WARNINGS, table.concat({ ... }, " ")) end
local function print(...) end
local function typeof(v) return type(v) end
local function token(name) return { Name = name, WaitForChild = function(self, n) return token(n) end } end
local MODULES = {}
local function require(x) return assert(MODULES[x.Name], "no module " .. tostring(x.Name)) end
local PLAYERS = {}
local SERVICES = {
	ReplicatedStorage = token("ReplicatedStorage"),
	RunService = { IsStudio = function() return IS_STUDIO end },
	Players = { GetPlayers = function() return PLAYERS end },
}
local game = { GetService = function(_, n) return SERVICES[n] end }
local script = { Parent = token("ServerScriptService") }
local TOASTS = {}
local Instance = { new = function(c) return { ClassName = c, FireClient = function(_, player, text) table.insert(TOASTS, { player = player, text = text }) end } end }
local LOOP
local task = {
	spawn = function(f) LOOP = coroutine.create(f) end,
	wait = function() coroutine.yield() end,
}
local Color3 = { fromRGB = function(r, g, b) return { r, g, b } end }
local os = { time = function() return NOW end, clock = function() return NOW end }

local function load(name, source)
	local f = assert(loadstring(source, name))
	setfenv(f, setmetatable({ game = game, script = script, require = require, warn = warn, print = print,
		typeof = typeof, Instance = Instance, task = task, Color3 = Color3, os = os }, { __index = getfenv(1) }))
	return f()
end
"""


def build_source(server_source):
    configs = {name: read(name + ".lua") for name in ("OnboardingConfig", "IpoConfig", "TaskConfig")}
    parts = [PRELUDE]
    for name, src in configs.items():
        parts.append("MODULES.%s = load(%r, %s)\n" % (name, name, lua_long(src)))
    parts.append(r"""
MODULES.CreatureConfig = { getEgg = function(k) return { key = k, name = k .. " Egg" } end, Poaching = { NewPlayerShield = 900 } }
MODULES.EmployeeServer = { grantEgg = function(player, key)
	local inc = player.data.team.incubators
	for i = 1, #inc do if not inc[i] then inc[i] = { egg = key, hatchAt = NOW + 60 }; return i end end
	return nil
end }
MODULES.ShopServer = { addDebugAction = function() end }
local CONFIG_WARNINGS = #WARNINGS
""")
    parts.append("local Server = load('OnboardingServer', %s)\n" % lua_long(server_source))
    parts.append(TESTS)
    return "".join(parts)


def lua_long(text):
    level = 0
    while ("]" + "=" * level + "]") in text:
        level += 1
    return "[" + "=" * level + "[" + text + "]" + "=" * level + "]"


TESTS = r"""
local Config = MODULES.OnboardingConfig
local Ipo = MODULES.IpoConfig
local passed, failed = 0, 0
local function check(name, cond, extra)
	if cond then passed += 1 else failed += 1; print_real("FAIL: " .. name .. (extra ~= nil and (" -- " .. tostring(extra)) or "")) end
end

local function newPlayer(name)
	local attrs = {}
	local player = { Name = name, Parent = true }
	function player:GetAttribute(k) return attrs[k] end
	function player:SetAttribute(k, v) attrs[k] = v end
	player.attrs = attrs
	player.data = {
		ready = true,
		cash = { Value = 0 },
		owned = {},
		team = { employees = {}, pending = nil, parked = {}, incubators = { false, false, false }, incubatorParts = {} },
		ipo = { count = 0, shares = 0, lifetime = 0, perks = {}, valuation = 0 },
		shop = { receipts = {}, instantHatches = 0 },
		poach = { hrLevel = 0, lost = {}, gained = {}, shieldUntil = 0 },
		tasks = { done = 0, bestChain = 0 },
	}
	return player
end

Server.init({
	getData = function(player) return player.data end,
	save = function() end,
	updateIncome = function() end,
	nextUpgradeCost = function() return nil end,
})
check("init: the loop exists", LOOP ~= nil)
check("config: loads with no warning", CONFIG_WARNINGS == 0, table.concat(WARNINGS, " | "))
check("init: no warning (every stage of Goals and Chain exists)", #WARNINGS == 0, table.concat(WARNINGS, " | "))
coroutine.resume(LOOP) -- runs to the first wait

local function tick(seconds)
	for _ = 1, seconds or 1 do
		NOW += 1
		local ok, err = coroutine.resume(LOOP)
		assert(ok, err)
	end
end

local function shownKeys(player)
	local keys = {}
	for _, goal in ipairs(Config.activeGoals()) do
		if player:GetAttribute("OnboardingGoalShown_" .. goal.key) == true then table.insert(keys, goal.key) end
	end
	return table.concat(keys, ",")
end

local function hire(player, n)
	for _ = 1, n do table.insert(player.data.team.employees, { id = tostring(#player.data.team.employees + 1) }) end
end

local function fresh(name, saved)
	local player = newPlayer(name)
	Server.setupPlayer(player, player.data, saved, true)
	table.clear(PLAYERS)
	table.insert(PLAYERS, player)
	return player
end

local function savedKeys(player)
	return table.concat(Server.serialize(player.data).goals, ",")
end

-- 1. Config ------------------------------------------------------------------------------
check("config: ChainEnabled ships false", Config.ChainEnabled == false)
check("config: off = today's list", Config.activeGoals() == Config.Goals)
check("config: today's list is still Hire3 then Seed", #Config.Goals == 2 and Config.Goals[1].key == "Hire3" and Config.Goals[2].key == "Seed")
check("config: ShowAtOnce is a whole number from 1", typeof(Config.ShowAtOnce) == "number" and Config.ShowAtOnce >= 1 and Config.ShowAtOnce % 1 == 0)
check("config: DoneShowSeconds is a number from 1", typeof(Config.DoneShowSeconds) == "number" and Config.DoneShowSeconds >= 1)
do
	local byKey = {}
	for _, g in ipairs(Config.Goals) do byKey[g.key] = g end
	local same = true
	for _, g in ipairs(Config.Chain) do
		local o = byKey[g.key]
		if o and (o.kind ~= g.kind or o.target ~= g.target or o.stage ~= g.stage or o.text ~= g.text) then same = false end
	end
	check("config: Hire3 and Seed mean the same in both lists", same and byKey.Hire3 and byKey.Seed)
	local inChain = {}
	for _, g in ipairs(Config.Chain) do inChain[g.key] = true end
	check("config: the chain keeps Hire3 and Seed", inChain.Hire3 and inChain.Seed)
	local stagesOk, wordsOk, kindsOk = true, true, true
	local KINDS = { employees = 1, stage = 1, upgrades = 1, owns = 1, calls = 1, chain = 1, ipos = 1 }
	for _, g in ipairs(Config.Chain) do
		if g.kind == "stage" then
			local found = false
			for _, s in ipairs(Ipo.Stages) do if s.key == g.stage then found = true end end
			stagesOk = stagesOk and found
		end
		local lower = string.lower(g.text)
		if string.find(lower, "chance") or string.find(lower, "odds") or string.find(lower, "luck") or string.find(lower, "random") then wordsOk = false end
		kindsOk = kindsOk and KINDS[g.kind] ~= nil and typeof(g.icon) == "string" and typeof(g.text) == "string"
	end
	check("config: every chain stage exists in IpoConfig", stagesOk)
	check("config: no chain text speaks of odds or chance (D9)", wordsOk)
	check("config: every chain goal has a known kind, an icon and a text", kindsOk)
	local names = {}
	for _, n in ipairs(UPGRADE_NAMES) do names[n] = true end
	local ownsOk = true
	for _, g in ipairs(Config.Chain) do
		if g.kind == "owns" then ownsOk = ownsOk and names[g.upgrade] == true end
	end
	check("config: every 'owns' goal names an upgrade in TycoonCore's UPGRADES", ownsOk)
end

-- 2. Chain off: exactly today's tracker ------------------------------------------------------
do
	IS_STUDIO = true
	local p = fresh("Off")
	tick()
	check("off: both of today's goals are shown", shownKeys(p) == "Hire3,Seed", shownKeys(p))
	check("off: no chain goal gets an attribute", p:GetAttribute("OnboardingGoalShown_Own3") == nil and p:GetAttribute("OnboardingGoal_Calls3") == nil)
	check("off: Hire3 progress 0 / 3", p:GetAttribute("OnboardingGoal_Hire3") == 0 and p:GetAttribute("OnboardingGoalTarget_Hire3") == 3)
	hire(p, 3); tick()
	check("off: Hire3 finished and saved", p.data.onboarding.goals.Hire3 == true and savedKeys(p) == "Hire3")
	check("off: the tracker stays while Seed is left", p:GetAttribute("OnboardingTracker") == true)
	p.data.ipo.valuation = Ipo.stageValuation(2, 0); tick()
	check("off: all done hides the tracker", p:GetAttribute("OnboardingTracker") == false)
	IS_STUDIO = false
end

-- 3. Chain on, live server (calls don't run) -------------------------------------------------
Config.ChainEnabled = true
do
	IS_STUDIO = false
	local p = fresh("Live")
	tick()
	check("live: the call goals are skipped, Own3 and Hire3 shown", shownKeys(p) == "Own3,Hire3", shownKeys(p))
	check("live: a skipped goal gets no progress", p:GetAttribute("OnboardingGoal_Calls3") == nil and p:GetAttribute("OnboardingGoalTarget_Calls10Row") == nil)
	check("live: a skipped goal is marked not shown", p:GetAttribute("OnboardingGoalShown_Calls3") == false)
	check("live: no tracker before the first hire", p:GetAttribute("OnboardingTracker") == false)
	hire(p, 1); tick()
	check("live: tracker after the first hire", p:GetAttribute("OnboardingTracker") == true)
	check("live: Own3 progress counts upgrades", p:GetAttribute("OnboardingGoal_Own3") == 0 and p:GetAttribute("OnboardingGoalTarget_Own3") == 3)
	p.data.owned.Desk = true; p.data.owned["Coffee Machine"] = true; tick()
	check("live: two upgrades = 2 / 3", p:GetAttribute("OnboardingGoal_Own3") == 2)
	p.data.owned.Laptop = true; tick()
	check("live: Own3 finished and saved", p.data.onboarding.goals.Own3 == true)
	check("live: a just-finished goal keeps its place", shownKeys(p) == "Own3,Hire3", shownKeys(p))
	check("live: its tick shows target / target", p:GetAttribute("OnboardingGoal_Own3") == 3)
	tick(Config.DoneShowSeconds - 1)
	check("live: still there before DoneShowSeconds", shownKeys(p) == "Own3,Hire3", shownKeys(p))
	tick(1)
	check("live: after DoneShowSeconds the next goal comes", shownKeys(p) == "Hire3,ServerRack", shownKeys(p))
	-- A hidden goal finishes in the background
	p.data.ipo.valuation = Ipo.stageValuation(2, 0); tick()
	check("live: Seed finishes while hidden", p.data.onboarding.goals.Seed == true)
	check("live: a goal finished while hidden never shows", shownKeys(p) == "Hire3,ServerRack", shownKeys(p))
	check("live: no tick time kept for a hidden goal", p.data.onboarding.justDone.Seed == nil)
	p.data.owned["Server Rack"] = true; tick()
	check("live: owns goal finished", p.data.onboarding.goals.ServerRack == true)
	tick(Config.DoneShowSeconds)
	check("live: Seed is skipped, Series A comes next", shownKeys(p) == "Hire3,SeriesA", shownKeys(p))
	-- An IPO takes the player below: finished goals stay finished
	p.data.owned = {}; p.data.ipo.valuation = 0; tick()
	check("live: finished goals stay after the upgrades reset", p.data.onboarding.goals.Own3 and p.data.onboarding.goals.ServerRack)
	check("live: a finished goal shows its target after a reset", p:GetAttribute("OnboardingGoal_Own3") == 3)
	hire(p, 2); p.data.ipo.valuation = Ipo.stageValuation(3, 0); tick(Config.DoneShowSeconds + 1)
	check("live: only the IPO is left", shownKeys(p) == "FirstIpo", shownKeys(p))
	check("live: tracker still up", p:GetAttribute("OnboardingTracker") == true)
	p.data.ipo.count = 1; tick()
	check("live: the IPO goal finishes", p.data.onboarding.goals.FirstIpo == true)
	check("live: every reachable goal done hides the tracker (call goals skipped, not blocking)", p:GetAttribute("OnboardingTracker") == false)
	check("live: the save lists every finished key, sorted", savedKeys(p) == "FirstIpo,Hire3,Own3,Seed,SeriesA,ServerRack", savedKeys(p))
end

-- 4. Chain on, calls running (Studio) ------------------------------------------------------
do
	IS_STUDIO = true
	local p = fresh("Studio")
	hire(p, 1); tick()
	check("studio: Calls3 comes first", shownKeys(p) == "Calls3,Own3", shownKeys(p))
	check("studio: Calls3 progress from tasks.done", p:GetAttribute("OnboardingGoal_Calls3") == 0 and p:GetAttribute("OnboardingGoalTarget_Calls3") == 3)
	p.data.tasks.done = 2; tick()
	check("studio: 2 / 3 calls", p:GetAttribute("OnboardingGoal_Calls3") == 2)
	p.data.tasks.done = 3; tick(Config.DoneShowSeconds + 1)
	check("studio: Calls3 done, Hire3 joins", p.data.onboarding.goals.Calls3 and shownKeys(p) == "Own3,Hire3", shownKeys(p))
	p.data.tasks.bestChain = 9; tick()
	check("studio: the chain goal reads bestChain", p:GetAttribute("OnboardingGoal_Calls10Row") == 9)
	check("studio: 9 in a row is not 10", not p.data.onboarding.goals.Calls10Row)
	p.data.tasks.bestChain = 10; tick()
	check("studio: 10 in a row finishes it", p.data.onboarding.goals.Calls10Row == true)
	-- calls stop (live): a finished call goal stays finished, an unfinished one stops blocking
	local q = fresh("NoTasks")
	q.data.tasks = nil; hire(q, 1); tick()
	check("studio: no tasks section = call goals skipped", shownKeys(q) == "Own3,Hire3", shownKeys(q))
	IS_STUDIO = false
end

-- 5. Saves -------------------------------------------------------------------------------
do
	local p = fresh("Old", { seenIntro = true, legacy = false, arrowDone = true, dismissed = false, goals = { "Hire3", "Seed", "FromTheFuture" }, extra = 7 })
	hire(p, 3); tick()
	check("save: Hire3 and Seed finished before stay finished", p.data.onboarding.goals.Hire3 and p.data.onboarding.goals.Seed)
	check("save: a player who finished today's goals meets the chain", p:GetAttribute("OnboardingTracker") == true and shownKeys(p) == "Own3,ServerRack", shownKeys(p))
	local s = Server.serialize(p.data)
	check("save: an unknown goal key is kept", string.find(table.concat(s.goals, ","), "FromTheFuture") ~= nil)
	check("save: an unknown field is kept", s.extra == 7)
	check("save: nothing of this session's tick times is saved", s.justDone == nil)
	local fields = 0
	for _ in pairs(s) do fields += 1 end
	check("save: same fields as before (5 known + the unknown one)", fields == 6, fields)
	local d = fresh("Dismissed", { seenIntro = true, arrowDone = true, dismissed = true, goals = {} })
	hire(d, 1); tick()
	check("save: a closed tracker stays closed", d:GetAttribute("OnboardingTracker") == false)
	local l = fresh("Legacy", { seenIntro = true, legacy = true, goals = {} })
	hire(l, 1); tick()
	check("save: legacy players get no tracker and no shown goals", l:GetAttribute("OnboardingTracker") ~= true and shownKeys(l) == "")
end

-- 7. M5 review fixes: F4, F7, F9 ---------------------------------------------------------------
do
	local function toastsFor(player)
		local n = 0
		for _, t in ipairs(TOASTS) do if t.player == player then n += 1 end end
		return n
	end
	-- F7: the free egg's toast is sent by the first update after data.ready, once
	local p = newPlayer("NewToast")
	p.data.ready = false -- TycoonCore calls setupPlayer while the save is still loading
	Server.setupPlayer(p, p.data, nil, true)
	table.clear(PLAYERS); table.insert(PLAYERS, p)
	check("F7: a new player gets the free egg", p.data.team.incubators[1] ~= false and p.data.onboarding.seenIntro == true)
	check("F7: no toast during the load", toastsFor(p) == 0, toastsFor(p))
	tick()
	check("F7: still none while data.ready is false", toastsFor(p) == 0, toastsFor(p))
	p.data.ready = true; tick()
	check("F7: the toast comes with the first update after ready", toastsFor(p) == 1, toastsFor(p))
	check("F7: it names the free egg", TOASTS[#TOASTS].text == string.format(Config.FreeEggMessage, Config.FreeEgg .. " Egg"), TOASTS[#TOASTS].text)
	tick(3)
	check("F7: it is sent only once", toastsFor(p) == 1, toastsFor(p))
	check("F7: the waiting toast is never saved", Server.serialize(p.data).toast == nil)

	-- F4: a save written while onboarding was off (seenIntro false, legacy false) with progress is legacy
	local v = newPlayer("VeteranOff")
	v.data.cash.Value = 500
	Server.setupPlayer(v, v.data, { seenIntro = false, legacy = false, arrowDone = false, dismissed = false, goals = {} }, true)
	table.clear(PLAYERS); table.insert(PLAYERS, v)
	hire(v, 1); tick()
	check("F4: progress and no egg on record = legacy", v.data.onboarding.legacy == true and v.data.onboarding.seenIntro == true)
	check("F4: no free egg for them", v.data.team.incubators[1] == false)
	check("F4: no arrow and no tracker", v:GetAttribute("OnboardingTarget") == nil and v:GetAttribute("OnboardingTracker") ~= true)
	-- ... while the same section with no progress is still a new player
	local n = fresh("NewOff", { seenIntro = false, legacy = false, goals = {} })
	check("F4: no progress = still new, gets the egg", n.data.onboarding.legacy == false and n.data.team.incubators[1] ~= false)
	-- ... and onboarding switched off gives nothing and marks nothing
	Config.Enabled = false
	local off = fresh("Disabled")
	check("F4: Enabled = false gives no egg", off.data.team.incubators[1] == false and off.data.onboarding.seenIntro == false)
	Config.Enabled = true

	-- F9: bad values are skipped with a warning
	local before = #WARNINGS
	local b = fresh("BadValues", { seenIntro = "yes", legacy = 1, arrowDone = true, dismissed = false, goals = 5 })
	local text = table.concat(WARNINGS, " | ", before + 1)
	check("F9: a bad boolean is warned about", string.find(text, "onboarding.seenIntro", 1, true) ~= nil and string.find(text, "onboarding.legacy", 1, true) ~= nil, text)
	check("F9: a goals value that is not a list is warned about", string.find(text, "onboarding.goals", 1, true) ~= nil, text)
	check("F9: good values next to them still load", b.data.onboarding.arrowDone == true)
	check("F9: a bad value is not taken as true", b.data.onboarding.legacy == false)
	local before2 = #WARNINGS
	fresh("GoodValues", { seenIntro = true, legacy = false, arrowDone = false, dismissed = false, goals = { "Hire3" } })
	check("F9: a good section gives no warning", #WARNINGS == before2, table.concat(WARNINGS, " | ", before2 + 1))
end

-- 6. ShowAtOnce = 1 -----------------------------------------------------------------------
do
	Config.ShowAtOnce = 1
	local p = fresh("One")
	hire(p, 1); tick()
	check("one: a single goal shown", shownKeys(p) == "Own3", shownKeys(p))
	Config.ShowAtOnce = 2
end

print_real(string.format("%d passed, %d failed", passed, failed))
"""


MUTANTS = [
    ("no ShowAtOnce cap", "if shown < OnboardingConfig.ShowAtOnce and (not done or fresh) then",
     "if (not done or fresh) then"),
    ("a finished goal never keeps its place", "and (not done or fresh) then", "and (not done) then"),
    ("calls goals ignore isActive", "if TaskConfig.isActive() and typeof(tasks) == \"table\" then",
     "if typeof(tasks) == \"table\" then"),
    ("chain reads done", "return goal.kind == \"calls\" and tasks.done or tasks.bestChain, goal.target",
     "return tasks.done, goal.target"),
    ("hidden goals get a tick time", "if player:GetAttribute(\"OnboardingGoalShown_\" .. goal.key) == true then",
     "if true then"),
    ("the shown flag is never cleared", "\t\tsetAttribute(player, \"OnboardingGoalShown_\" .. goal.key, show)\n",
     "\t\tif show then setAttribute(player, \"OnboardingGoalShown_\" .. goal.key, show) end\n"),
    ("owns ignores the name", "return data.owned[goal.upgrade] and 1 or 0, 1", "return countOwned(data) > 0 and 1 or 0, 1"),
    ("ipos kind missing", "\telseif goal.kind == \"ipos\" then\n\t\treturn data.ipo.count, goal.target\n", ""),
    ("only the old list", "for _, goal in ipairs(OnboardingConfig.activeGoals()) do", "for _, goal in ipairs(OnboardingConfig.Goals) do"),
    ("F7: the toast is sent during the load", "notifyWhenReady(data, string.format(", "notify(player, string.format("),
    ("F7: the toast is sent every second", "\t\tonboarding.toast = nil\n", ""),
    ("F4: only a missing section counts as legacy", "if not onboarding.seenIntro and hasProgress(data) then",
     "if savedOnboarding == nil and hasProgress(data) then"),
    ("F9: no warning for a bad boolean", "\t\t\telseif value ~= nil then\n", "\t\t\telseif false then\n"),
    ("F9: no warning for bad goals", "if savedOnboarding.goals ~= nil and typeof(savedOnboarding.goals) ~= \"table\" then", "if false then"),
    ("F9: a non-boolean is taken as true", "if typeof(value) == \"boolean\" then\n\t\t\t\tonboarding[key] = value", "if value then\n\t\t\t\tonboarding[key] = value == true or value == 1"),
    ("the done window counts one second more", "now - justDone[goal.key] < OnboardingConfig.DoneShowSeconds",
     "now - justDone[goal.key] <= OnboardingConfig.DoneShowSeconds"),
]


def run(luau, source):
    names = "local UPGRADE_NAMES = {%s}\nlocal print_real = print\n" % ", ".join('"%s"' % n for n in upgrade_names())
    with tempfile.NamedTemporaryFile("w", suffix=".luau", delete=False, encoding="utf-8") as f:
        f.write(names + source)
        path = f.name
    try:
        out = subprocess.run([luau, path], capture_output=True, text=True, timeout=60)
        return out.stdout + out.stderr
    finally:
        os.unlink(path)


def summary(output):
    m = re.search(r"(\d+) passed, (\d+) failed", output)
    return (int(m.group(1)), int(m.group(2))) if m else None


def main():
    luau = os.environ.get("LUAU") or shutil.which("luau")
    if not luau:
        print("Luau not found. Download it from https://github.com/luau-lang/luau/releases and set LUAU=/path/to/luau")
        return 1
    server = read("OnboardingServer.lua")
    out = run(luau, build_source(server))
    result = summary(out)
    print(out.strip())
    if not result or result[1] != 0:
        print("FAILED")
        return 1
    caught = 0
    for label, old, new in MUTANTS:
        if server.count(old) != 1:
            print("MUTANT %s: the text to change is not in OnboardingServer.lua exactly once" % label)
            return 1
        mout = run(luau, build_source(server.replace(old, new)))
        mres = summary(mout)
        if mres and mres[1] > 0:
            caught += 1
            first = next((l for l in mout.splitlines() if l.startswith("FAIL: ")), "")
            print("mutant caught: %s (%s)" % (label, first[6:]))
        elif mres is None:
            # A run that errors never counts as a catch (as in lobby_test, hud_test, building_test)
            print("MUTANT NOT CAUGHT: %s (the run errored, no named check failed)" % label)
        else:
            print("MUTANT NOT CAUGHT: %s" % label)
    print("%d checks passed, %d of %d mutants caught" % (result[0], caught, len(MUTANTS)))
    return 0 if caught == len(MUTANTS) else 1


if __name__ == "__main__":
    sys.exit(main())
