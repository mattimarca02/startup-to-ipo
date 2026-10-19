#!/usr/bin/env python3
"""Tests for the founder's activities and the economy core (overhaul 2 phase 3), outside Studio.

Run:   LUAU=/path/to/luau python3 tools/founder_test.py

It runs the real FounderConfig, FounderServer, TaskConfig, TaskServer, OfficeConfig, IpoConfig and DailyConfig with a fake
Roblox (fake clock, fake players, a fake character position) and checks:
  - the `founder` save section: new players, saved values kept, bad values skipped, unknown fields written back, a new run
  - the coding sprint, the production bug, the brainstorm and the investor pitch: unlocks, reach, time limits, grading,
    rewards (seconds of Income times the office items' effect), the bug's penalty (never below $0, never the valuation)
  - the economy core in TaskServer: the daily cap, a rejoin's empty reward bank, payReward and the calls boost, the flags a
    rejoin on the same server keeps
  - the wiring in TycoonCore and the client (source pins), and broken versions of the code (mutants) that the tests catch.
It changes nothing in the game or in Studio.
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import daily_test as dt  # noqa: E402  (its task-engine harness: the fake Roblox, the real TaskServer)


def read(name):
    with open(os.path.join(ROOT, name), encoding="utf-8") as f:
        return f.read()


PRELUDE_EXTRA = r"""
-- Founder test additions: a Vector3 with arithmetic, a translation-only CFrame, players with attributes and characters
local V3 = {}
V3.__index = function(t, k)
	if k == "Magnitude" then return math.sqrt(t.X * t.X + t.Y * t.Y + t.Z * t.Z) end
	return rawget(V3, k)
end
V3.__add = function(a, b) return Vector3.new(a.X + b.X, a.Y + b.Y, a.Z + b.Z) end
V3.__sub = function(a, b) return Vector3.new(a.X - b.X, a.Y - b.Y, a.Z - b.Z) end
Vector3 = { new = function(x, y, z) return setmetatable({ isFakeVector3 = true, X = x or 0, Y = y or 0, Z = z or 0 }, V3) end }
local CF = {}
CF.__index = CF
CF.__mul = function(a, b)
	if getmetatable(b) == CF then return CFrame.new(a.Position.X + b.Position.X, a.Position.Y + b.Position.Y, a.Position.Z + b.Position.Z) end
	return a.Position + b
end
CFrame = { new = function(x, y, z) return setmetatable({ Position = Vector3.new(x, y, z) }, CF) end }
local realMath = math
local DRAW = nil -- a list of numbers math.random(a, b) answers in turn (nil: always a)
math = setmetatable({ random = function(a, b)
	if a == nil then return RANDOM end
	if b == nil then a, b = 1, a end
	if DRAW and #DRAW > 0 then return table.remove(DRAW, 1) end
	return a
end }, { __index = realMath })
"""

TESTS = r"""
-- Founder tests -------------------------------------------------------------------------------------------------------
local FC = (function()
__FOUNDERCONFIG__
end)()
MODULES.FounderConfig = FC
local FC_WARNINGS = #WARNINGS
local TaskServer = loadServer()
MODULES.TaskServer = TaskServer
local NOTES, INCOME_UPDATES = {}, 0
local function plotFrame(slot) return CFrame.new(slot * 100, 0, 0) end
local STAGE = {}
local core = {
	getData = function(p) return p.data end,
	addEarnings = function(p, amount) table.insert(EARNINGS, amount) end,
	baseIncome = function(p) return p.data.income.Value end,
	updateIncome = function(p) INCOME_UPDATES += 1 end,
	plotFrame = plotFrame,
	stageOf = function(data) return STAGE[data] or 1 end,
	notify = function(p, text) table.insert(NOTES, text) end,
}
EARNINGS = {}
TaskServer.init(core)
local function loadFounder()
__FOUNDERSERVER__
end
local Founder = loadFounder()
Founder.init(core)
local onAction = Founder._onAction
local C = MODULES.TaskConfig
C.BudgetBank = 1e9

local passed, failed = 0, 0
local function check(name, cond, extra)
	if cond then passed += 1 else failed += 1; print_real("FAIL: " .. name .. (extra ~= nil and (" -- " .. tostring(extra)) or "")) end
end
local function near(a, b, eps) return math.abs(a - b) <= (eps or 1e-6) end
local function advance(s) CLOCK += s; NOW += s end

local function newPlayer(opts, savedFounder, savedTasks)
	opts = opts or {}
	local attrs = {}
	local player = { Name = opts.name or "F", UserId = opts.userId or 1, Parent = true, events = {} }
	function player:SetAttribute(k, v) attrs[k] = v end
	function player:GetAttribute(k) return attrs[k] end
	player.attrs = attrs
	local data = {
		ready = true, loaded = true, slot = 2,
		cash = { Value = opts.cash or 0 }, income = { Value = opts.income or 10 },
		ipo = { valuation = 0, count = opts.ipos or 0, busy = false },
		team = { employees = opts.employees or {} },
		owned = opts.owned or { Desk = true },
	}
	player.data = data
	STAGE[data] = opts.stage or 1
	TaskServer.setupPlayer(player, data, savedTasks)
	Founder.setupPlayer(player, data, savedFounder)
	-- standing at a station: the character's root at a garage offset
	function player.at(x, z)
		local pos = plotFrame(data.slot) * Vector3.new(x, 3, z)
		player.Character = { FindFirstChild = function(_, n) return n == "HumanoidRootPart" and { Position = pos } or nil end }
	end
	player.at(FC.Stations.Desk.x + 2, FC.Stations.Desk.z)
	return player, data
end
local function step(p) Founder.step(p, CLOCK) end
local function lastState(p)
	for i = #p.events, 1, -1 do if p.events[i].kind == "state" then return p.events[i].payload end end
	return nil
end
local function act(p, action, arg) return onAction(p, action, arg) end

-- 1. The config ---------------------------------------------------------------------------------------------------------
check("FounderConfig loads without a warning", FC_WARNINGS == 0, WARNINGS[1])
check("sprint pays 20 + 3 per right line (0 right pays nothing, 5 right pay 35)", FC.sprintSeconds(0) == 0 and FC.sprintSeconds(1) == 23 and FC.sprintSeconds(5) == 35 and FC.sprintSeconds(9) == 35)
check("a brainstorm idea grows with the items' brainstorm effect", near(FC.ideaShare(FC.Brainstorm.Ideas[1], 0.5), 0.3) and FC.ideaText(FC.Brainstorm.Ideas[1], 0.5) == "Calls pay 30% more for 3 min")
local bad
for key, text in pairs(FC.Texts) do
	for _, word in ipairs({ "odds", "chance", "luck", "random", "%%" }) do
		if string.find(string.lower(text), word, 1, true) then bad = key end
	end
end
check("no founder text claims odds or chance (D9)", bad == nil, bad)
check("the remotes: FounderAction and FounderState in a FounderRemotes folder", (function()
	for _, inst in ipairs(CREATED) do if inst.Name == "FounderRemotes" then return inst.Parent == SERVICES.ReplicatedStorage end end
	return false
end)())

-- 2. The `founder` section ------------------------------------------------------------------------------------------------
do
	local p, d = newPlayer()
	check("save: a new player gets no founder section", Founder.serialize(d) == nil)
	check("save: the stations go to the client as attributes (desk, rack, board, the seat and where to stand)",
		p.attrs.FounderDesk ~= nil and p.attrs.FounderRack ~= nil and p.attrs.FounderBoard ~= nil and p.attrs.FounderSeat ~= nil and p.attrs.FounderStand ~= nil)
	WARNINGS = {}
	local p2, d2 = newPlayer({ ipos = 1 }, { v = 1, run = 1, pitched = { Seed = true, [5] = true, SeriesA = "yes" }, dinnerDay = 20000, future = { x = 1 } })
	local out = Founder.serialize(d2)
	check("save: kept as it was (run, pitched, dinnerDay) and the unknown field written back",
		out and out.run == 1 and out.pitched.Seed == true and out.dinnerDay == 20000 and (out.future or {}).x == 1 and out.v == 1)
	check("save: bad pitched entries are skipped with a warning", out and out.pitched.SeriesA == nil and out.pitched[5] == nil and #WARNINGS == 2, #WARNINGS)
	local _, d3 = newPlayer({ ipos = 2 }, { v = 1, run = 1, pitched = { Seed = true } })
	check("save: a section from an older run (an IPO since) starts the pitches again", next(d3.founder.pitched) == nil and d3.founder.run == 2 and Founder.serialize(d3).run == 2)
	local _, d4 = newPlayer(nil, { v = 3, run = "x", dinnerDay = -1 })
	local out4 = Founder.serialize(d4)
	check("save: a newer version's number is kept; bad run and dinnerDay are skipped", out4.v == 3 and out4.run == 0 and out4.dinnerDay == 0)
	WARNINGS = {}
	local _, d5 = newPlayer(nil, "broken")
	check("save: a section that is not a table is skipped with a warning (and not written)", #WARNINGS == 1 and Founder.serialize(d5) == nil)
end

-- 3. The coding sprint -------------------------------------------------------------------------------------------------
do
	local p, d = newPlayer({ owned = {} })
	check("sprint: locked without the Desk", select(2, act(p, "Start", "sprint")) == FC.Texts.Locked)
	d.owned.Desk = true
	p.at(10, 10)
	check("sprint: refused away from the desk", select(2, act(p, "Start", "sprint")) == FC.Texts.TooFar)
	p.at(FC.Stations.Desk.x + 3, FC.Stations.Desk.z + 3)
	check("sprint: starts at the desk", act(p, "Start", "sprint") == true and d.founder.live.activity.kind == "sprint")
	local s = lastState(p)
	check("sprint: the client sees 4 lines, round 1 of 5, and never the answer", s and s.activity and #s.activity.lines == 4 and s.activity.round == 1 and s.activity.answer == nil)
	check("sprint: one at a time", select(2, act(p, "Start", "sprint")) == FC.Texts.Busy)
	local live = d.founder.live
	-- round 1: right; round 2: too fast (a script); round 3: wrong; round 4: too late; round 5: right
	advance(1); act(p, "Pick", live.activity.answer)
	advance(0.1); act(p, "Pick", live.activity.answer)
	advance(1); act(p, "Pick", live.activity.answer % 4 + 1)
	advance(FC.Sprint.roundSeconds + 1); act(p, "Pick", live.activity.answer)
	advance(1)
	local cashBefore, earnBefore = d.cash.Value, #EARNINGS
	local ok, text, info = act(p, "Pick", live.activity.answer)
	check("sprint: 2 right of 5 (a too-fast and a too-late pick count as wrong)", ok and info and info.hits == 2, info and info.hits)
	check("sprint: pays (20 + 3 x 2) seconds of Income through the earnings path", d.cash.Value - cashBefore == 260 and #EARNINGS == earnBefore + 1, d.cash.Value - cashBefore)
	check("sprint: says what it paid", type(text) == "string" and string.find(text, "2/5", 1, true) ~= nil)
	check("sprint: then it cools down", select(2, act(p, "Start", "sprint")) == string.format(FC.Texts.Cooldown, FC.Sprint.cooldown))
	advance(FC.Sprint.cooldown)
	d.owned["Second Monitor"] = true
	act(p, "Start", "sprint")
	for _ = 1, 5 do advance(1); act(p, "Pick", live.activity.answer) end
	check("sprint: the Second Monitor makes it pay 25% more (35 x 1.25 s)", near(d.cash.Value - cashBefore - 260, math.floor(35 * 1.25 * 10)), d.cash.Value - cashBefore - 260)
	-- a sprint left alone: every round runs out on the server's clock, the result is told
	advance(FC.Sprint.cooldown)
	act(p, "Start", "sprint")
	NOTES = {}
	for _ = 1, 5 do advance(FC.Sprint.roundSeconds + 0.6); step(p) end
	check("sprint: rounds that run out move on by themselves and the end is told", live.activity == nil and NOTES[#NOTES] == FC.Texts.SprintNone, NOTES[#NOTES])
end

-- 4. The production bug ---------------------------------------------------------------------------------------------------
do
	local p, d = newPlayer({ cash = 50 })
	local live = d.founder.live
	for _ = 1, 3 do advance(500); step(p) end
	check("bug: no alarm without the Server Rack", live.alarmUntil == nil and live.bugNextAt == nil)
	d.owned["Server Rack"] = true
	step(p)
	check("bug: the first alarm waits a normal gap", live.bugNextAt ~= nil and live.bugNextAt - CLOCK >= FC.Bug.gap[1] - 1e-6)
	advance(FC.Bug.gap[1] - 1); step(p)
	check("bug: not before the gap", live.alarmUntil == nil)
	advance(1); step(p)
	local alarmEvent = false
	for _, e in ipairs(p.events) do if e.kind == "alarm" then alarmEvent = true end end
	check("bug: the alarm rings, and the client is told", live.alarmUntil ~= nil and alarmEvent and lastState(p).bug.alarm == true)
	check("bug: refused away from the rack", select(2, act(p, "Start", "bug")) == FC.Texts.TooFar)
	p.at(FC.Stations.Rack.x, FC.Stations.Rack.z + 4)
	check("bug: starts at the rack", act(p, "Start", "bug") == true)
	local order = live.activity.order
	local view = lastState(p).activity
	check("bug: the client sees the 4 fixes and their order", #view.order == 4 and view.order[1] == FC.Bug.buttons[order[1]])
	local cash0, earn0 = d.cash.Value, #EARNINGS
	for i = 1, 4 do advance(0.5); act(p, "Pick", order[i]) end
	check("bug: the right order fixes it: 25 s of Income", d.cash.Value - cash0 == 250 and #EARNINGS == earn0 + 1 and live.alarmUntil == nil and live.activity == nil)
	-- a wrong press: it costs 10 s of Income, never more than the Cash there is, never the valuation
	live.bugNextAt = CLOCK; step(p)
	act(p, "Start", "bug")
	d.cash.Value = 40
	local earn1 = #EARNINGS
	local okWrong, textWrong, infoWrong = act(p, "Pick", live.activity.order[2])
	check("bug: a wrong press fails it and costs Cash, down to $0 at most (40 here, 100 asked)", okWrong == false and d.cash.Value == 0 and infoWrong.cash == -40)
	check("bug: the cost never touches the valuation (no earnings call)", #EARNINGS == earn1)
	check("bug: the next alarm is a new gap away", live.alarmUntil == nil and live.bugNextAt ~= nil and live.bugNextAt > CLOCK)
	-- running out after starting: a fail
	live.bugNextAt = CLOCK; step(p)
	act(p, "Start", "bug")
	d.cash.Value = 500
	advance(FC.Bug.limit + 1); step(p)
	check("bug: the time running out fails it (100 = 10 s of Income)", d.cash.Value == 400 and live.activity == nil)
	-- an alarm nobody answers costs nothing
	live.bugNextAt = CLOCK; step(p)
	NOTES = {}
	advance(FC.Bug.alarmSeconds + 1); step(p)
	check("bug: an alarm nobody answers stops by itself and costs nothing", d.cash.Value == 400 and live.alarmUntil == nil and NOTES[1] == FC.Texts.BugGone)
	-- the QA Lab: fixes pay 50% more
	d.owned["QA Lab"] = true
	live.bugNextAt = CLOCK; step(p)
	act(p, "Start", "bug")
	local cash2 = d.cash.Value
	for i = 1, 4 do advance(0.5); act(p, "Pick", live.activity.order[i]) end
	check("bug: the QA Lab makes a fix pay 50% more (37.5 s)", d.cash.Value - cash2 == 375, d.cash.Value - cash2)
	-- no alarm while another activity runs
	live.bugNextAt = CLOCK
	p.at(FC.Stations.Desk.x, FC.Stations.Desk.z)
	act(p, "Start", "sprint")
	step(p)
	check("bug: never rings while another activity runs (it waits)", live.alarmUntil == nil and live.bugNextAt > CLOCK)
	act(p, "Cancel")
end

-- 5. The brainstorm ---------------------------------------------------------------------------------------------------------
do
	local p, d = newPlayer()
	p.at(FC.Stations.Board.x, FC.Stations.Board.z - 3)
	check("brainstorm: locked before the first hire", select(2, act(p, "Start", "brainstorm")) == FC.Texts.Locked)
	d.team.employees = { { id = "1", creature = "CodingCat" } }
	p.at(0, 0)
	check("brainstorm: refused away from the blackboard", select(2, act(p, "Start", "brainstorm")) == FC.Texts.TooFar)
	p.at(FC.Stations.Board.x, FC.Stations.Board.z - 3)
	check("brainstorm: three ideas on the board", act(p, "Start", "brainstorm") == true and #lastState(p).activity.ideas == 3)
	local id = nil
	DEBUG.TaskSpawn(p, d)
	for i = #p.events, 1, -1 do
		local e = p.events[i]
		if e.kind == "state" and e.payload.tasks and #e.payload.tasks > 0 then id = e.payload.tasks[#e.payload.tasks].id break end
	end
	d.owned.Whiteboard = true
	act(p, "Pick", 1) -- calls +20% x 1.5 (the Whiteboard) = +30% for 3 minutes
	advance(1)
	local before = d.cash.Value
	local okCall = (function()
		for _, inst in ipairs(CREATED) do
			if inst.Name == "TaskAction" and inst.OnServerInvoke then return inst.OnServerInvoke(p, "Answer", id) end
		end
	end)()
	check("brainstorm: the calls idea makes a call pay 30% more (7 s x 1.3 = 91)", okCall == true and d.cash.Value - before == 91, d.cash.Value - before)
	check("brainstorm: then it cools down", select(2, act(p, "Start", "brainstorm")) == string.format(FC.Texts.Cooldown, FC.Brainstorm.cooldown - 1))
	advance(FC.Brainstorm.cooldown)
	INCOME_UPDATES = 0
	act(p, "Start", "brainstorm")
	act(p, "Pick", 2)
	check("brainstorm: the Income idea raises the Income (x 1.225 with the Whiteboard) and recomputes it", near(Founder.incomeBoost(p), 1 + 0.15 * 1.5) and INCOME_UPDATES == 1)
	check("brainstorm: one boost at a time (the calls boost is gone)", d.tasks.run.boost.share == 0)
	advance(FC.Brainstorm.Ideas[2].seconds + 1); step(p)
	check("brainstorm: when it runs out the Income goes back (recomputed again)", Founder.incomeBoost(p) == 1 and INCOME_UPDATES == 2)
	advance(FC.Brainstorm.cooldown)
	p.at(FC.Stations.Board.x, FC.Stations.Board.z - 3)
	d.founder.live.sprintReadyAt = CLOCK + 100
	act(p, "Start", "brainstorm")
	act(p, "Pick", 3)
	check("brainstorm: the sprint idea makes the sprint ready at once", d.founder.live.sprintReadyAt <= CLOCK)
end

-- 6. The investor pitch ---------------------------------------------------------------------------------------------------
do
	local p, d = newPlayer({ stage = 1 })
	step(p)
	check("pitch: none at the Garage", lastState(p).pitch == nil and select(2, act(p, "Start", "pitch")) == FC.Texts.Locked)
	STAGE[d] = 2
	NOTES = {}
	step(p)
	check("pitch: Seed offers one, and the player is told", lastState(p).pitch == "Seed" and NOTES[1] == string.format(FC.Texts.PitchOffer, "Seed"), NOTES[1])
	p.at(0, 20)
	check("pitch: at the desk only", select(2, act(p, "Start", "pitch")) == FC.Texts.TooFar)
	p.at(FC.Stations.Desk.x, FC.Stations.Desk.z)
	check("pitch: starts at the desk", act(p, "Start", "pitch") == true)
	local live = d.founder.live
	local view = lastState(p).activity
	check("pitch: the client sees the question and 3 answers, never which is good", view.question ~= nil and #view.options == 3 and view.good == nil and live.activity.good ~= nil)
	d.tasks.run.bank = 0 -- the pitch is a round bonus: it does not come from the reward bank
	local cash0 = d.cash.Value
	advance(2); act(p, "Pick", live.activity.good)
	advance(2); act(p, "Pick", live.activity.good % 3 + 1)
	advance(2)
	local ok, text, info = act(p, "Pick", live.activity.good)
	check("pitch: 2 good answers of 3 pay 2 x 40 s of Income, in full with an empty bank", ok and info.hits == 2 and d.cash.Value - cash0 == 800, d.cash.Value - cash0)
	check("pitch: done for this round (saved), not offered again", d.founder.pitched.Seed == true and Founder.serialize(d).pitched.Seed == true and select(2, act(p, "Start", "pitch")) == FC.Texts.Locked)
	STAGE[d] = 3; step(p)
	check("pitch: the next round offers its own", lastState(p).pitch == "Series A")
	d.ipo.count = 1; STAGE[d] = 2; step(p)
	check("pitch: a new run (an IPO) offers every round again", lastState(p).pitch == "Seed" and next(d.founder.pitched) == nil)
	d.owned.Bookshelf = true
	act(p, "Start", "pitch")
	local cash1 = d.cash.Value
	for _ = 1, 3 do advance(2); act(p, "Pick", live.activity.good) end
	check("pitch: the Bookshelf makes each answer pay 20% more (3 x 48 s)", d.cash.Value - cash1 == 1440, d.cash.Value - cash1)
end

-- 7. The economy core (TaskServer) ----------------------------------------------------------------------------------------
do
	C.BudgetBank = 60
	local p, d = newPlayer()
	check("bank: a first session today starts with a full bank", d.tasks.run.bank == 60)
	local paid = TaskServer.payReward(p, 30)
	check("payReward: pays from the bank in full (30 s = 300)", paid == 300 and d.tasks.run.bank == 30)
	paid = TaskServer.payReward(p, 50)
	check("payReward: past the bank pays the over-budget share (30 + 20 x 0.2 = 34 s)", paid == 340, paid)
	check("payReward: a graded activity makes the player engaged", TaskServer.isEngaged(p) == true)
	d.tasks.engagedSeconds = C.EngagedCap.seconds
	d.tasks.engagedDay = MODULES.DailyConfig.dayNumber(NOW)
	d.tasks.run.bank = 60
	paid = TaskServer.payReward(p, 20)
	check("cap: past 3 engaged hours today every reward pays 25%", paid == 50, paid)
	check("cap: capShare", C.capShare(0) == 1 and C.capShare(C.EngagedCap.seconds - 1) == 1 and C.capShare(C.EngagedCap.seconds) == 0.25)
	-- a rejoin on the same day, engaged already: the bank starts empty
	local saved = { done = 1, engagedDay = MODULES.DailyConfig.dayNumber(NOW), engagedSeconds = 100 }
	local p2, d2 = newPlayer({ userId = 2 }, nil, saved)
	check("bank: a rejoin on a day already engaged starts with an empty bank", d2.tasks.run.bank == 0)
	local _, d3 = newPlayer({ userId = 3 }, nil, { done = 4, engagedDay = MODULES.DailyConfig.dayNumber(NOW) - 1, engagedSeconds = 500 })
	check("bank: the first session of a new day starts full", d3.tasks.run.bank == 60)
	d.ready = false
	check("payReward: nothing before the save is loaded", TaskServer.payReward(p, 10) == 0)
	d.ready = true
	check("payReward: refuses nonsense amounts", TaskServer.payReward(p, -5) == 0 and TaskServer.payReward(p, 0 / 0) == 0)
	-- flags survive a rejoin on this server
	local p4, d4 = newPlayer({ userId = 44 })
	for _ = 1, 5 do table.insert(d4.tasks.run.flags, CLOCK) end
	for _, f in ipairs(PLAYER_REMOVING) do f(p4) end
	local _, d5 = newPlayer({ userId = 44 })
	check("flags: a rejoin on this server keeps the last hour's flags", #d5.tasks.run.flags == 5)
	for _, f in ipairs(PLAYER_REMOVING) do f(p4) end
	advance(3601)
	local _, d6 = newPlayer({ userId = 44 })
	check("flags: after an hour they are forgotten", #d6.tasks.run.flags == 0)
	C.BudgetBank = 1e9
end

-- 8. Requests ------------------------------------------------------------------------------------------------------------
do
	local p, d = newPlayer()
	WARNINGS = {}
	check("requests: a Pick that is not a whole number is refused", select(2, act(p, "Pick", "1")) == "Bad request" and select(2, act(p, "Pick", 1.5)) == "Bad request")
	advance(20)
	check("requests: an unknown action is refused", select(2, act(p, "Fly")) == "Unknown action")
	advance(20)
	check("requests: an unknown activity is refused", select(2, act(p, "Start", "nap")) == "Bad request")
	advance(20)
	local slow = 0
	for _ = 1, 20 do if select(2, act(p, "Sync")) == FC.Texts.Slow then slow += 1 end end
	check("requests: a flood is slowed down (token bucket)", slow >= 10, slow)
	d.ready = false
	advance(20)
	check("requests: nothing before the save is loaded", select(2, act(p, "Sync")) == FC.Texts.Loading)
end

print_real(string.format("%d passed, %d failed", passed, failed))
print_real("DONE")
"""


def program(files=None):
    files = files or {}

    def src(name):
        return files.get(name) or read(name)

    base = dt.task_engine_source(files)
    prelude = base[:base.index("\n-- Tests ---")]
    prelude = prelude.replace("__STORABLE__", dt.STORABLE_LUA)
    body = TESTS.replace("__FOUNDERCONFIG__", src("FounderConfig.lua")).replace("__FOUNDERSERVER__", src("FounderServer.lua"))
    return prelude + "\n" + PRELUDE_EXTRA + "\n" + body


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
    return (int(m.group(1)) if m else 0), fails, done, result.stderr.strip()[-400:]


def source_pins():
    """[(name, ok)]: the wiring that the Luau tests can't reach."""
    core, client, shop = read("TycoonCore.lua"), read("FounderClient.lua"), read("ShopClient.lua")
    task_client = read("TaskClient.lua")
    board = core[core.index("writeBoard = function"):core.index("local function refreshSign")]
    return [
        ("wiring: TycoonCore requires FounderServer and knows the founder section",
         'local FounderServer = require(script.Parent:WaitForChild("FounderServer"))' in core and "office = true, founder = true }" in core),
        ("wiring: the save writes the founder section and waits for it (the save gate)",
         "founder = FounderServer.serialize(data)," in core and "data.office and data.founder) then" in core),
        ("wiring: FounderServer.setupPlayer runs right after setupOffice, after the marked load block",
         re.search(r"-- CLAIMLOAD-END\n\n\tsetupOffice\(player, data, saved\)[^\n]*\n\tFounderServer\.setupPlayer\(player, data, saved and saved\.founder\)", core) is not None),
        ("wiring: FounderServer.init comes after TaskServer.init and before DailyServer.init",
         0 <= core.find("TaskServer.init({") < core.find("FounderServer.init({") < core.find("DailyServer.init({")),
        ("wiring: the Income includes the brainstorm's Income boost", "* FounderServer.incomeBoost(player))" in core),
        ("blackboard: chalk (IndieFlower) on a SurfaceGui, never a BillboardGui or AlwaysOnTop",
         "Enum.Font.IndieFlower" in board and "SurfaceGui" in board and "BillboardGui" not in board and "AlwaysOnTop" not in board),
        ("blackboard: the old green next-upgrade sign is gone", '"BuySign"' not in core and "Buy it in SHOP > Office" not in core),
        ("blackboard: it is rewritten every second with the room (syncRoom)", "pcall(writeBoard, data) -- the goal chain moves on every second" in core),
        ("client: the prompts never need line of sight (the solid boxes would hide them) and are made on the client",
         "RequiresLineOfSight = false" in client and 'make("ProximityPrompt"' in client),
        ("client: the activity window is a window (OpenPanel) and the call board above the desk is not drawn on top",
         'playerGui:SetAttribute("OpenPanel", PANEL_NAME)' in client and "AlwaysOnTop = true" not in client),
        ("client: the desk's Answer asks TaskServer at once (the server grades the call, the walk is only the show)",
         'taskAction:InvokeServer("Answer", id)' in client and "task.spawn(function() -- the server grades the answer now" in client),
        ("client: nothing on the client picks a reward or a right answer", "math.random" not in client and "addEarnings" not in client),
        ("client: the phone tray still answers from anywhere (TaskClient unchanged in what it sends)", 'taskAction:InvokeServer("Answer", call.id)' in task_client),
        ("debug: the founder buttons are in the Studio Debug tab",
         all('"%s"' % a in shop for a in ("FounderBugNow", "FounderReady", "FounderPitchAgain"))),
        ("server only: the code lines and the pitch answers are in FounderServer, never in ReplicatedStorage",
         "Hire engineers and grow sales" in read("FounderServer.lua") and "Hire engineers and grow sales" not in read("FounderConfig.lua")),
    ]


MUTANTS = [
    ("the sprint ignores the reaction floor", "FounderServer.lua", "and reaction >= s.minReaction and n == activity.answer",
     "and n == activity.answer", "sprint: 2 right of 5"),
    ("the sprint takes late picks", "FounderServer.lua", "if now <= activity.deadline and reaction >= s.minReaction", "if reaction >= s.minReaction",
     "sprint: 2 right of 5"),
    ("the sprint forgets the desk", "FounderServer.lua", '\t\tif not closeEnough(player, data, "Desk") then return false, TEXTS.TooFar end\n\t\tlive.activity = { kind = "sprint"',
     '\t\tlive.activity = { kind = "sprint"', "sprint: refused away from the desk"),
    ("the sprint skips its item effect", "FounderServer.lua", '(1 + effect(data, "sprint") + boostShare(live, "sprint", now))',
     '(1 + boostShare(live, "sprint", now))', "sprint: the Second Monitor"),
    ("the bug penalty goes below $0", "FounderServer.lua", "local cost = math.min(data.cash.Value, math.floor(seconds * data.income.Value))",
     "local cost = math.floor(seconds * data.income.Value)", "bug: a wrong press fails it"),
    ("the bug's wrong press is ignored", "FounderServer.lua", "if now > activity.deadline or n ~= activity.order[activity.pos] then",
     "if now > activity.deadline then", "bug: a wrong press fails it"),
    ("an unanswered alarm costs Cash", "FounderServer.lua", "\t\t\t\tlive.alarmUntil = nil\n\t\t\t\tscheduleBug(live, now)\n\t\t\t\tlive.changed = true\n\t\t\t\tcore.notify(player, TEXTS.BugGone)",
     "\t\t\t\tlive.alarmUntil = nil\n\t\t\t\tscheduleBug(live, now)\n\t\t\t\tlive.changed = true\n\t\t\t\tcharge(data, 10)\n\t\t\t\tcore.notify(player, TEXTS.BugGone)",
     "bug: an alarm nobody answers"),
    ("the pitch counts any answer", "FounderServer.lua", "if now <= activity.deadline and n == activity.good then", "if now <= activity.deadline then",
     "pitch: 2 good answers of 3"),
    ("the pitch is offered again after it is done", "FounderServer.lua", "\tdata.founder.pitched[activity.stageKey] = true\n", "\n",
     "pitch: done for this round"),
    ("the pitch's answer goes to the client", "FounderServer.lua", "view.question, view.options = activity.stageName, activity.q, #activity.questions, activity.question, activity.options",
     "view.question, view.options, view.good = activity.stageName, activity.q, #activity.questions, activity.question, activity.options, activity.good",
     "pitch: the client sees the question"),
    ("the daily cap is ignored", "TaskServer.lua", " * TaskConfig.capShare(data.tasks.engagedSeconds)", "", "cap: past 3 engaged hours"),
    ("a rejoin refills the bank", "TaskServer.lua", "tasks.run = newRun(now, rejoin and 0 or nil)", "tasks.run = newRun(now, nil)",
     "bank: a rejoin on a day already engaged"),
    ("the flags are not remembered", "TaskServer.lua", "\t\t\tremembered[player.UserId] = { at = now, flags = run.flags }\n", "\n",
     "flags: a rejoin on this server"),
    ("the calls boost is ignored", "TaskServer.lua", "\tif boost and now < boost.untilAt then\n\t\tshare += boost.share\n\tend\n", "",
     "brainstorm: the calls idea"),
    ("the founder section forgets unknown fields", "FounderServer.lua", "\t\t\t\tfounder.extra[key] = value\n", "\n",
     "save: kept as it was"),
    ("the Income boost never ends", "FounderServer.lua", "\tif boost and now >= boost.untilAt then\n\t\tlive.boost = nil",
     "\tif false then\n\t\tlive.boost = nil", "brainstorm: when it runs out"),
]


def main():
    luau = os.environ.get("LUAU") or shutil.which("luau")
    if not luau:
        print("Luau not found. Set LUAU=/path/to/luau")
        return 2
    passed, fails, done, err = outcome(run(luau, program()))
    for f in fails:
        print("FAIL: " + f)
    if not done:
        print("CRASH: " + err)
    pins = source_pins()
    for name, ok in pins:
        if not ok:
            print("FAIL: " + name)
    pins_failed = sum(1 for _, ok in pins if not ok)
    print("Founder checks: %d passed, %d failed" % (passed + len(pins) - pins_failed, len(fails) + pins_failed + (0 if done else 1)))
    caught = 0
    for label, file, old, new, want in MUTANTS:
        text = read(file)
        if text.count(old) != 1:
            print("NOT CAUGHT: %s -- not applied (its anchor is missing or there %d times)" % (label, text.count(old)))
            continue
        _, mfails, mdone, merr = outcome(run(luau, program({file: text.replace(old, new)})))
        hit = [f for f in mfails if f.startswith(want)]
        if hit:
            caught += 1
            print("caught: %s -- by \"%s\"" % (label, hit[0]))
        else:
            print("NOT CAUGHT: %s -- %s" % (label, merr[:200] if not mdone and not mfails else mfails[:3]))
    print("Founder mutations: %d of %d caught, each by its named check" % (caught, len(MUTANTS)))
    ok = done and not fails and not pins_failed and caught == len(MUTANTS)
    print("founder_test.py: %s" % ("OK" if ok else "FAILED"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
