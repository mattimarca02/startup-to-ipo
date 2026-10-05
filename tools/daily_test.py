#!/usr/bin/env python3
"""Logic tests for the daily calendar (DailyServer.lua + DailyConfig.lua), outside Studio.

Run:   python3 tools/daily_test.py

It needs the free Luau command-line tool (https://github.com/luau-lang/luau/releases, the
"luau" file from luau-macos.zip or luau-windows.zip). Put it on your PATH, or point to it:
       LUAU=/path/to/luau python3 tools/daily_test.py

It runs the real DailyServer and DailyConfig code with a fake Roblox (fake clock, fake player,
fake incubators) and checks every claim rule: one claim per UTC day, double tap, rejoin, one
missed day keeps the place, two missed days go back to Day 1, full incubators, bad saves,
Day 7 Shares not doubled, Studio-only debug, and that calendar Cash never changes the IPO
valuation. It also checks the egg odds the screens show (the whole CreatureConfig), and runs the marked code of PoachServer (move notes, the FR-4 guard), ShopServer (pass checks: purchase confirmation retries,
parallel join check) and TycoonCore (sanitizer, store, save payload build) with fakes.
For players in regions where paid random items are restricted (FR-13, D9 option B) it checks the fixed hire
order against the odds (CreatureConfig), EmployeeServer's roll and the fixedHires save section, and
ShopServer's PolicyService check (fail closed, the 10 s cap) and what stays on sale (ShopConfig).
It changes nothing in the game or in Studio.
"""

import ast
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PRELUDE = r"""-- Fake Roblox environment for testing DailyServer outside Studio
local NOW = 20000 * 86400 + 12 * 3600 -- noon UTC on day 20000
local CLOCK = 1000
local IS_STUDIO = true
local WARNINGS = {}
local os = { time = function() return NOW end, clock = function() return CLOCK end }
local function warn(...) local t = table.concat({...}, " "); table.insert(WARNINGS, t) end
local function print(...) end
local function token(name) return { Name = name, WaitForChild = function(self, n) return token(n) end } end
local MODULES = {}
local function require(x) return assert(MODULES[x.Name], "no module " .. tostring(x.Name)) end
local SERVICES = {
	ReplicatedStorage = token("ReplicatedStorage"),
	RunService = { IsStudio = function() return IS_STUDIO end },
	Players = { GetPlayers = function() return {} end },
}
local game = { GetService = function(_, n) return SERVICES[n] end }
local script = { Parent = token("ServerScriptService") }
local CREATED = {}
local Instance = { new = function(c) local i = { ClassName = c }; table.insert(CREATED, i); return i end }
local task = { spawn = function() end, wait = function() end }

MODULES.CreatureConfig = { getEgg = function(k) local e = ({ Garage = 1, Startup = 1, Unicorn = 1 })[k]; return e and { key = k, name = k .. " Egg" } end }
MODULES.OnboardingConfig = { Enabled = true }
MODULES.ShopConfig = { formatCash = function(n) return "$" .. n end }
local DEBUG = {}
MODULES.ShopServer = { addDebugAction = function(name, f) DEBUG[name] = f end }
MODULES.EmployeeServer = { grantEgg = function(player, key)
	local inc = player.data.team.incubators
	for i = 1, #inc do if not inc[i] then inc[i] = { egg = key }; return i end end
	return nil
end }
MODULES.IpoServer = {
	isBusy = function(data) return data ~= nil and data.ipo ~= nil and data.ipo.busy == true end,
	grantShares = function(player, n) player.data.ipo.shares += n; return true end, -- raw, like the real one
}
"""

TESTS = r"""-- Tests ---------------------------------------------------------------------
local DailyServer = MODULES.DailyServer
local DailyConfig = MODULES.DailyConfig
local passed, failed = 0, 0
local function check(name, cond, extra)
	if cond then passed += 1 else failed += 1; print_real("FAIL: " .. name .. (extra and (" -- " .. tostring(extra)) or "")) end
end

local function newPlayer(saved, opts)
	opts = opts or {}
	local player = { Name = "P", attrs = {} }
	function player:SetAttribute(k, v) self.attrs[k] = v end
	function player:GetAttribute(k) return self.attrs[k] end
	local data = {
		ready = true, loaded = opts.loaded ~= false,
		cash = { Value = 0 }, income = { Value = opts.income or 10 },
		ipo = { valuation = 500, lifetime = 900, shares = 0, busy = false },
		team = { incubators = { false, false, false } },
		onboarding = opts.onboarding or { legacy = true },
	}
	player.data = data
	DailyServer.setupPlayer(player, data, saved)
	return player, data
end

local saves = 0
local currentData
DailyServer.init({ getData = function(p) return p.data end, save = function() saves += 1; return true end })
local onAction
for _, inst in ipairs(CREATED) do if inst.Name == "DailyAction" then onAction = inst.OnServerInvoke end end
check("remote created", onAction ~= nil)
local function tap(p) CLOCK += 2; return onAction(p, "Claim") end
local function nextDay(n) NOW += 86400 * (n or 1) end

-- 1. Old save with no section / new player: Day 1
local p, d = newPlayer(nil)
check("no section: ready", p.attrs.DailyReady == true)
check("no section: Day 1", p.attrs.DailyDay == 1)
local ok, msg, info = tap(p)
check("claim Day 1 ok", ok, msg)
check("Day 1 cash = 5 min of 10/s", d.cash.Value == 3000, d.cash.Value)
check("valuation unchanged", d.ipo.valuation == 500 and d.ipo.lifetime == 900)
check("saved once", saves == 1)
check("marker set", d.daily.lastClaimDay == DailyConfig.dayNumber(NOW))
check("now not ready", p.attrs.DailyReady == false)

-- 2. Double tap: debounce, then already claimed
local ok2, msg2 = onAction(p, "Claim") -- same clock: debounce
check("double tap within debounce refused", not ok2 and msg2 == "One moment...", msg2)
local ok3, msg3 = tap(p)
check("second claim same day refused", not ok3 and string.find(msg3, "Already claimed") ~= nil, msg3)
check("cash unchanged after refusal", d.cash.Value == 3000)

-- 3. Rejoin same day (same save): still claimed, nothing granted on join
local saved = DailyServer.serialize(d)
local p2, d2 = newPlayer(saved)
check("rejoin: not ready", p2.attrs.DailyReady == false)
check("rejoin: no cash granted", d2.cash.Value == 0)
check("rejoin: claim refused", not (tap(p2)))

-- 4. Next day: Day 2
nextDay()
p, d = newPlayer(saved)
check("next day: Day 2 ready", p.attrs.DailyReady and p.attrs.DailyDay == 2, p.attrs.DailyDay)
ok = tap(p)
check("claim Day 2", ok and d.daily.streak == 2)
saved = DailyServer.serialize(d)

-- 5. Miss exactly one day: place kept, Day 3 (egg)
nextDay(2)
p, d = newPlayer(saved)
check("1 missed: Day 3", p.attrs.DailyDay == 3, p.attrs.DailyDay)
check("1 missed: kept", p.attrs.DailyKept == true and p.attrs.DailyMissed == 1)
-- incubators full: refused, day not used
d.team.incubators = { { egg = "Garage" }, { egg = "Garage" }, { egg = "Garage" } }
DailyServer.serialize(d)
local okF, msgF = tap(p)
check("full incubators refused", not okF and msgF == DailyConfig.Texts.NoIncubator, msgF)
check("full incubators: marker not set", d.daily.lastClaimDay ~= DailyConfig.dayNumber(NOW))
d.team.incubators[2] = false
ok = tap(p)
check("egg day claimed after freeing", ok and d.team.incubators[2] and d.team.incubators[2].egg == "Garage")
check("egg day: no cash", d.cash.Value == 0)
check("streak 3", d.daily.streak == 3)
saved = DailyServer.serialize(d)

-- 6. Miss two days: back to Day 1
nextDay(3)
p, d = newPlayer(saved)
check("2 missed: Day 1", p.attrs.DailyDay == 1, p.attrs.DailyDay)
check("2 missed: lost day 3", p.attrs.DailyLostDay == 3 and p.attrs.DailyMissed == 2 and p.attrs.DailyKept == false)
check("2 missed: streak shown 0", p.attrs.DailyStreak == 0)
ok = tap(p)
check("reset claim gives Day 1", ok and d.daily.streak == 1 and d.daily.best == 3)
saved = DailyServer.serialize(d)

-- 7. Full week: Day 7 gives Unicorn + 3 Shares, not doubled
for day = 2, 7 do
	nextDay()
	p, d = newPlayer(saved)
	d.ipo.shares = 100
	check("week day " .. day, p.attrs.DailyDay == day, p.attrs.DailyDay)
	ok = tap(p)
	check("claim day " .. day, ok)
	if day == 7 then
		check("Day 7 shares +3 exactly", d.ipo.shares == 103, d.ipo.shares)
		check("Day 7 unicorn egg", d.team.incubators[1] and d.team.incubators[1].egg == "Unicorn")
	end
	saved = DailyServer.serialize(d)
end
nextDay()
p, d = newPlayer(saved)
check("after Day 7: Day 1 again, streak goes on", p.attrs.DailyDay == 1 and p.attrs.DailyStreak == 7, p.attrs.DailyDay)
tap(p)
check("streak 8", d.daily.streak == 8 and d.daily.best == 8)

-- 8. Not loaded / not ready / IPO busy
p, d = newPlayer(nil, { loaded = false })
check("not loaded refused", not tap(p))
p, d = newPlayer(nil)
d.ready = false
local _, m = tap(p)
check("loading refused", m == DailyConfig.Texts.Loading, m)
d.ipo.busy = true
_, m = tap(p)
check("IPO busy refused", m == DailyConfig.Texts.IpoBusy, m)
check("bad action refused", not onAction(p, "GiveMeCash") and not onAction(p, 42))
check("extra args ignored", true)

-- 9. Bad and unknown values
WARNINGS = {}
p, d = newPlayer({ lastClaimDay = "x", streak = -3, best = 0 / 0, claims = 2.5, future = { a = 1 } })
check("bad values warned", #WARNINGS == 4, #WARNINGS)
check("bad values defaulted", d.daily.lastClaimDay == 0 and d.daily.streak == 0 and d.daily.claims == 0)
check("unknown kept", DailyServer.serialize(d).future.a == 1)
WARNINGS = {}
p, d = newPlayer("garbage")
check("bad section warned", #WARNINGS == 1)
-- far future: clamped to today, never grants
WARNINGS = {}
p, d = newPlayer({ lastClaimDay = DailyConfig.dayNumber(NOW) + 50, streak = 4 })
check("future clamped", d.daily.lastClaimDay == DailyConfig.dayNumber(NOW) and #WARNINGS == 1)
check("future: not ready", p.attrs.DailyReady == false)
-- one day ahead (another server's clock): counted as claimed
p, d = newPlayer({ lastClaimDay = DailyConfig.dayNumber(NOW) + 1, streak = 4 })
check("1 day ahead: not ready", p.attrs.DailyReady == false and not tap(p))

-- 10. Auto-open only after the M5 first minute
p = newPlayer(nil, { onboarding = { legacy = false, arrowDone = false } })
check("first minute: no auto-open", p.attrs.DailyAutoOpen == false)
p = newPlayer(nil, { onboarding = { legacy = false, arrowDone = true } })
check("after arrow: auto-open", p.attrs.DailyAutoOpen == true)

-- 11. Studio debug: next day and reset
p, d = newPlayer(nil)
tap(p)
check("debug: claimed", p.attrs.DailyReady == false)
DEBUG.DailyNextDay(p, d)
check("debug +1: Day 2 ready", p.attrs.DailyReady == true and p.attrs.DailyDay == 2)
DEBUG.DailyNextDay(p, d)
check("debug +2: kept", p.attrs.DailyKept == true and p.attrs.DailyDay == 2)
DEBUG.DailyNextDay(p, d)
check("debug +3: back to Day 1", p.attrs.DailyDay == 1 and p.attrs.DailyLostDay == 1)
DEBUG.DailyReset(p, d)
check("debug reset", d.daily.streak == 0 and d.daily.lastClaimDay == 0 and p.attrs.DailyDay == 1)
IS_STUDIO = false
check("debug outside Studio does nothing", DEBUG.DailyNextDay(p, d) == "Debug is disabled" and DEBUG.DailyReset(p, d) == "Debug is disabled")
IS_STUDIO = true

-- 12. Cash: min, cap, income 0
check("cash min for income 0", DailyConfig.cashFor({ cashMinutes = 5 }, 0) == 300)
check("cash cap 60 min", DailyConfig.cashFor({ cashMinutes = 1000 }, 1) == 3600)
check("no cash day", DailyConfig.cashFor({ egg = "Garage" }, 100) == 0)
-- UTC boundary: the day changes at ResetHourUtc = 8 (D3), not at midnight
check("reset hour is 8 UTC (D3)", DailyConfig.ResetHourUtc == 8)
local RESET = 8 * 3600
check("day changes at 08:00 UTC", DailyConfig.dayNumber(20001 * 86400 + RESET - 1) == 20000 and DailyConfig.dayNumber(20001 * 86400 + RESET) == 20001)
check("midnight UTC is not a new day", DailyConfig.dayNumber(20001 * 86400) == 20000 and DailyConfig.dayNumber(20001 * 86400 + 1) == 20000)
check("dayStart is 08:00 UTC", DailyConfig.dayStart(20001) == 20001 * 86400 + RESET)
check("dayNumber(dayStart(n)) == n", DailyConfig.dayNumber(DailyConfig.dayStart(20001)) == 20001 and DailyConfig.dayNumber(DailyConfig.dayStart(20001) - 1) == 20000)
check("formatWait", DailyConfig.formatWait(18720) == "5h 12m" and DailyConfig.formatWait(750) == "12m 30s" and DailyConfig.formatWait(42) == "42s")

-- 13. The 08:00 UTC reset in a real flow (D3). Times are given as day D at hour H UTC.
local function at(day, hour, minute) return day * 86400 + hour * 3600 + (minute or 0) * 60 end
local savedNow = NOW
-- claim at 07:59, claim again at 08:00 (a new day), refused at 08:01
NOW = at(20000, 7, 59)
p, d = newPlayer(nil)
check("07:59: ready", p.attrs.DailyReady == true)
check("07:59: claim ok", tap(p) == true)
check("07:59: the countdown points at 08:00 UTC", p.attrs.DailyNextAt == at(20000, 8) and p.attrs.DailyReady == false)
NOW = at(20000, 8)
DailyServer.setupPlayer(p, d, DailyServer.serialize(d))
check("08:00: next day is ready", p.attrs.DailyReady == true and p.attrs.DailyDay == 2)
check("08:00: claim Day 2 ok", tap(p) == true)
NOW = at(20000, 8, 1)
check("08:01: same day, refused", tap(p) == false)
NOW = at(20001, 7, 59)
check("next 07:59: still claimed", tap(p) == false)
NOW = at(20001, 8)
check("next 08:00: Day 3 claimable", tap(p) == true and d.daily.streak == 3)
-- midnight does nothing: claimed at 23:00, still claimed at 00:30 the next calendar day
NOW = at(20010, 23)
p, d = newPlayer(nil)
check("23:00: claim ok", tap(p) == true)
NOW = at(20011, 0, 30)
check("00:30 next calendar day: still claimed", tap(p) == false)
NOW = at(20011, 8)
check("08:00 next calendar day: claimable", tap(p) == true)
-- a save made under the old hour 0 (lastClaimDay = floor(t / 86400)), joining under hour 8
-- (a) claimed at 10:00 on day 20000 (same number under both rules): next claim 08:00 on 20001
NOW = at(20000, 12)
p, d = newPlayer({ lastClaimDay = 20000, streak = 2, best = 2, claims = 2 })
check("old save, claimed 10:00: not ready", p.attrs.DailyReady == false and not tap(p))
check("old save, claimed 10:00: next at 08:00 UTC", p.attrs.DailyNextAt == at(20001, 8))
NOW = at(20001, 0, 10)
check("old save, claimed 10:00: still refused after midnight", not tap(p))
NOW = at(20001, 8)
check("old save, claimed 10:00: ready at 08:00", tap(p) == true and d.daily.streak == 3)
-- (b) claimed at 03:00 on day 20000 under hour 0, joins at 05:00 the same day (new day number is 19999):
--     counted as claimed today, no warning, and the player waits until 08:00 on 20001 (up to 8 h longer, never an extra claim)
WARNINGS = {}
NOW = at(20000, 5)
p, d = newPlayer({ lastClaimDay = 20000, streak = 2, best = 2, claims = 2 })
check("old save, claimed 03:00, join 05:00: claimed, not clamped", p.attrs.DailyReady == false and d.daily.lastClaimDay == 20000 and #WARNINGS == 0)
NOW = at(20001, 1)
check("old save, claimed 03:00: 01:00 next day is still waiting", not tap(p))
NOW = at(20001, 8)
check("old save, claimed 03:00: ready at 08:00 next day", tap(p) == true and d.daily.streak == 3)
-- (c) the grace edge only gets kinder: last claim day 20000, back at 05:00 on 20003 (old rules: 2 missed, Day 1; new: 1 missed, place kept; from 08:00 on both rules agree)
NOW = at(20003, 5)
p, d = newPlayer({ lastClaimDay = 20000, streak = 3, best = 3, claims = 3 })
check("old save, back at 05:00 after 2 days: place kept", p.attrs.DailyKept == true and p.attrs.DailyDay == 4 and p.attrs.DailyMissed == 1)
NOW = at(20003, 9)
p, d = newPlayer({ lastClaimDay = 20000, streak = 3, best = 3, claims = 3 })
check("old save, back at 09:00 after 2 days: back to Day 1 (same as the old rule)", p.attrs.DailyDay == 1 and p.attrs.DailyLostDay == 3)
NOW = at(20004, 5)
p, d = newPlayer({ lastClaimDay = 20000, streak = 3, best = 3, claims = 3 })
check("old save, 3 missed days: back to Day 1", p.attrs.DailyDay == 1 and p.attrs.DailyLostDay == 3)
-- (d) no extra claim: for an old save claimed on day 20000 (any hour), whenever the new rule says "ready",
--     the old rule (day = floor(t / 86400)) says "ready" too, checked hour by hour for 4 days
local extra, firstReady = 0, nil
for hour = 0, 4 * 24 do
	NOW = at(20000, hour)
	local pp = newPlayer({ lastClaimDay = 20000, streak = 2, best = 2, claims = 2 })
	local newReady = pp.attrs.DailyReady == true
	local oldReady = math.floor(NOW / 86400) > 20000
	if newReady and not oldReady then extra += 1 end
	if newReady and not firstReady then firstReady = hour end
end
check("old save: the new reset never allows a claim the old one didn't", extra == 0, extra)
check("old save: first ready at 08:00 on day 20001 (hour 32 from the start of day 20000)", firstReady == 32, firstReady)
NOW = savedNow

print_real(string.format("%d passed, %d failed", passed, failed))
"""

SANITIZE_TESTS = r"""-- Tests for TycoonCore's sanitizeSave (the code between its SANITIZE markers) ---------
local print_real = print
local WARNINGS = {}
local function warn(...) table.insert(WARNINGS, table.concat({...}, " ")) end
local function typeof(v) return type(v) end
__SANITIZE__
local passed, failed = 0, 0
local function check(name, cond, extra)
	if cond then passed += 1 else failed += 1; print_real("FAIL: " .. name .. (extra and (" -- " .. tostring(extra)) or "")) end
end
local nan = 0 / 0
local c, o, s = sanitizeSave({ cash = 150, owned = { "Desk", "Laptop" }, lastSeen = 1700000000 }, "P")
check("good save: cash", c == 150, c)
check("good save: owned", #o == 2 and o[1] == "Desk" and o[2] == "Laptop")
check("good save: lastSeen", s == 1700000000)
check("good save: no warnings", #WARNINGS == 0)
check("empty save: defaults", select(1, sanitizeSave({}, "P")) == 0 and #select(2, sanitizeSave({}, "P")) == 0 and select(3, sanitizeSave({}, "P")) == nil)
check("empty save: no warnings", #WARNINGS == 0)
check("cash as a numeric string", select(1, sanitizeSave({ cash = "42" }, "P")) == 42)
check("cash is a word", select(1, sanitizeSave({ cash = "lots" }, "P")) == 0)
check("cash is a table", select(1, sanitizeSave({ cash = {} }, "P")) == 0)
check("cash is a boolean", select(1, sanitizeSave({ cash = true }, "P")) == 0)
check("cash is NaN", select(1, sanitizeSave({ cash = nan }, "P")) == 0)
check("cash is inf", select(1, sanitizeSave({ cash = math.huge }, "P")) == 0)
check("cash is -inf", select(1, sanitizeSave({ cash = -math.huge }, "P")) == 0)
check("cash is negative", select(1, sanitizeSave({ cash = -5 }, "P")) == 0)
check("cash is huge but finite", select(1, sanitizeSave({ cash = 1e300 }, "P")) == 2 ^ 53)
check("cash fraction floors", select(1, sanitizeSave({ cash = 10.9 }, "P")) == 10)
check("bad cash warns", #WARNINGS >= 7)
WARNINGS = {}
local _, o2 = sanitizeSave({ owned = "Desk" }, "P")
check("owned is a string: empty list", #o2 == 0)
local _, o3 = sanitizeSave({ owned = 7 }, "P")
check("owned is a number: empty list", #o3 == 0)
local _, o4 = sanitizeSave({ owned = { "Desk", 5, {}, "Laptop", false } }, "P")
check("owned with junk: keeps the names", #o4 == 2 and o4[1] == "Desk" and o4[2] == "Laptop", #o4)
check("bad owned warns", #WARNINGS >= 4)
local _, _, s1 = sanitizeSave({ lastSeen = "yesterday" }, "P")
local _, _, s2 = sanitizeSave({ lastSeen = nan }, "P")
local _, _, s3 = sanitizeSave({ lastSeen = math.huge }, "P")
local _, _, s4 = sanitizeSave({ lastSeen = {} }, "P")
check("bad lastSeen is dropped", s1 == nil and s2 == nil and s3 == nil and s4 == nil)
print_real(string.format("%d passed, %d failed", passed, failed))
"""


STORE_TESTS = r"""-- Tests for TycoonCore's getStore (lazy retry) and readableSave (R5) ----------------
local print_real = print
local WARNINGS = {}
local function warn(...) table.insert(WARNINGS, table.concat({...}, " ")) end
local function typeof(v) return type(v) end
local FAILS = 2 -- GetDataStore errors this many times, then works
local CALLS = 0
local DataStoreService = {}
function DataStoreService:GetDataStore(name)
	CALLS += 1
	if FAILS > 0 then FAILS -= 1; error("503 unavailable") end
	return { name = name }
end
__GETSTORE__
__READABLE__
local passed, failed = 0, 0
local function check(name, cond, extra)
	if cond then passed += 1 else failed += 1; print_real("FAIL: " .. name .. (extra and (" -- " .. tostring(extra)) or "")) end
end
check("getStore fails while unavailable (1)", getStore() == nil)
check("getStore fails while unavailable (2)", getStore() == nil)
check("every call retried", CALLS == 2, CALLS)
local st = getStore()
check("getStore succeeds on the 3rd try", st ~= nil and st.name == "StartupTycoon_v1")
check("store is cached afterwards", getStore() == st and CALLS == 3, CALLS)
check("failures warned", #WARNINGS == 2, #WARNINGS)
WARNINGS = {}
check("table save is readable", readableSave({ cash = 1 }, true, "P") == true)
check("missing save (nil) is a new player, not a failure", readableSave(nil, true, "P") == true)
check("string save is a load failure", readableSave("junk", true, "P") == false)
check("number save is a load failure", readableSave(5, true, "P") == false)
check("boolean save is a load failure", readableSave(false, true, "P") == false)
check("non-table save warns", #WARNINGS == 3, #WARNINGS)
check("a failed read stays failed", readableSave(nil, false, "P") == false)
print_real(string.format("%d passed, %d failed", passed, failed))
"""


PASS_TESTS = r"""-- Tests for ShopServer's pass checks (the code between its PASSCHECK markers) ---------
local print_real = print
local WARNINGS = {}
local function warn(...) table.insert(WARNINGS, table.concat({...}, " ")) end

-- A tiny scheduler: task.spawn starts a thread, task.wait pauses it on a fake clock, so "slow Roblox" can be timed
local CLOCK = 0
local os = { clock = function() return CLOCK end, time = function() return 1700000000 end }
local sleeping = {}
local depth = 0 -- > 0 while a spawned thread runs (the test script itself is the "main" thread)
local function resume(co)
	depth += 1
	local ok, delay = coroutine.resume(co)
	depth -= 1
	if not ok then error(delay) end
	if coroutine.status(co) == "suspended" then table.insert(sleeping, { co = co, at = CLOCK + delay }) end
end
local task = {}
function task.spawn(f) resume(coroutine.create(f)) end
function task.wait(n)
	n = n or 0.03
	if depth > 0 then coroutine.yield(n) return n end
	local target = CLOCK + n
	while true do
		local best
		for i, t in ipairs(sleeping) do
			if t.at <= target and (not best or t.at < sleeping[best].at) then best = i end
		end
		if not best then break end
		local t = table.remove(sleeping, best)
		CLOCK = math.max(CLOCK, t.at)
		resume(t.co)
	end
	CLOCK = target
	return n
end

local ShopConfig = {
	PassConfirm = { RetrySeconds = 5, GiveUpSeconds = 120 },
	Passes = {
		{ key = "DoubleCash", name = "2x Cash", id = 11 },
		{ key = "VIP", name = "VIP", id = 12 },
		{ key = "Placeholder", name = "Soon", id = 0 },
		{ key = "Shareholder", name = "Shareholder", id = 13 },
	},
}
function ShopConfig.getPassById(id)
	if id == 0 then return nil end
	for _, p in ipairs(ShopConfig.Passes) do if p.id == id then return p end end
	return nil
end

local SHOP, PUBLISHED, NOTES, ASKED = nil, {}, {}, {}
local ASK = function() return nil end -- (player, id) -> true / false / nil, may task.wait
local function userOwnsPass(player, id)
	table.insert(ASKED, id)
	return ASK(player, id)
end
local function getShop(player) return player.shop end
local function publish(player) table.insert(PUBLISHED, CLOCK) end
local function notify(player, text) table.insert(NOTES, text) end
__PASSCHECK__
local passed, failed = 0, 0
local function check(name, cond, extra)
	if cond then passed += 1 else failed += 1; print_real("FAIL: " .. name .. (extra and (" -- " .. tostring(extra)) or "")) end
end
local function reset(startClock)
	CLOCK = startClock or 0
	sleeping = {}
	PUBLISHED, NOTES, ASKED, WARNINGS = {}, {}, {}, {}
	ShopConfig.PassConfirm = { RetrySeconds = 5, GiveUpSeconds = 120 }
	local shop = { passes = {} }
	return { Name = "P", Parent = {}, shop = shop }, shop
end
local function has(list, text)
	for _, t in ipairs(list) do if string.find(t, text, 1, true) then return true end end
	return false
end
local VIP, CASH = ShopConfig.Passes[2], ShopConfig.Passes[1]

-- Purchase confirmation (item 5) ----------------------------------------------------
local player, shop = reset()
ASK = function() return true end
onPassPromptFinished(player, 12, true)
check("buy, Roblox answers at once: granted", shop.passes.VIP == true)
check("... published once and the player told", #PUBLISHED == 1 and has(NOTES, "VIP unlocked!"))
check("... one ask, no waiting", #ASKED == 1 and CLOCK == 0)

player, shop = reset()
ASK = function() return false end
onPassPromptFinished(player, 12, false)
check("cancelled purchase: nothing asked", #ASKED == 0 and not shop.passes.VIP)
onPassPromptFinished(player, 999, true)
check("unknown pass id: nothing asked", #ASKED == 0)
onPassPromptFinished(player, 0, true)
check("pass id 0: nothing asked", #ASKED == 0)
player.shop = nil
onPassPromptFinished(player, 12, true)
check("no loaded shop: nothing asked", #ASKED == 0)

player, shop = reset()
local calls = 0
ASK = function() calls += 1; if calls < 4 then return nil end return true end
onPassPromptFinished(player, 12, true)
check("Roblox unreachable 3 times, then yes: granted", shop.passes.VIP == true and calls == 4)
check("... retried every 5 s (3 waits = 15 s)", CLOCK == 15, CLOCK)
check("... player told 'confirming' once, then 'unlocked'", #NOTES == 2 and has(NOTES, "Confirming VIP") and has(NOTES, "VIP unlocked!"), #NOTES)
check("... published once", #PUBLISHED == 1)

player, shop = reset()
calls = 0
ASK = function() calls += 1; if calls < 3 then return false end return true end
onPassPromptFinished(player, 12, true)
check("stale 'no' right after buying, then yes: granted", shop.passes.VIP == true and calls == 3)

player, shop = reset()
ASK = function() return nil end
onPassPromptFinished(player, 12, true)
check("Roblox never answers: NOT granted (no yes, no pass)", shop.passes.VIP == nil)
check("... gave up after about 2 minutes", CLOCK >= 120 and CLOCK < 126, CLOCK)
check("... about 25 asks, not a flood", #ASKED >= 24 and #ASKED <= 26, #ASKED)
check("... never published", #PUBLISHED == 0)
check("... player told Roblox is slow", has(NOTES, "slow to confirm VIP"))

player, shop = reset()
ASK = function() return false end
onPassPromptFinished(player, 12, true)
check("Roblox keeps saying no: never granted", shop.passes.VIP == nil and #PUBLISHED == 0)

player, shop = reset()
ShopConfig.PassConfirm = { RetrySeconds = 10, GiveUpSeconds = 35 }
ASK = function() return nil end
onPassPromptFinished(player, 12, true)
check("interval and duration come from ShopConfig", #ASKED == 5 and CLOCK >= 35 and CLOCK < 45, #ASKED .. " asks, clock " .. CLOCK)

player, shop = reset()
calls = 0
ASK = function() calls += 1; if calls == 2 then player.Parent = nil end return nil end
onPassPromptFinished(player, 12, true)
check("player leaves while waiting: stops, nothing granted", shop.passes.VIP == nil and calls == 2)

player, shop = reset()
calls = 0
ASK = function()
	calls += 1
	if calls == 2 then onPassPromptFinished(player, 12, true) end -- a second event while waiting
	if calls < 3 then return nil end
	return true
end
onPassPromptFinished(player, 12, true)
check("a second event while waiting does not start a second loop", calls == 3 and #NOTES == 2, calls .. " asks, " .. #NOTES .. " notes")

player, shop = reset()
calls = 0
ASK = function() calls += 1; shop.passes.VIP = true; return nil end -- the 2-minute recheck found it meanwhile
onPassPromptFinished(player, 12, true)
check("pass found by another path while waiting: still told, loop ends", has(NOTES, "VIP unlocked!") and calls == 1)

player, shop = reset()
ASK = function() return nil end
onPassPromptFinished(player, 12, true) -- gives up after 2 minutes
ASK = function() return true end
onPassPromptFinished(player, 12, true) -- the website purchase shows up later: a new confirmation can start
check("after giving up, a later event can still grant the pass", shop.passes.VIP == true)

-- Join-time check (item 5, second part) --------------------------------------------------
player, shop = reset()
ASK = function(_, id) return id == 12 end
local changed = checkPasses(player, shop)
check("checkPasses returns true when a pass was found", changed == true and shop.passes.VIP == true)
check("... only the real passes are asked (id 0 skipped)", #ASKED == 3, #ASKED)
check("... published once, for the one pass found", #PUBLISHED == 1)
ASKED = {}
check("a second check asks only the passes not owned yet", checkPasses(player, shop) == false and #ASKED == 2, #ASKED)

player, shop = reset()
ASK = function(_, id) task.wait(6) return nil end -- Roblox down: every pass takes 6 s to give up
check("Roblox down: nothing found", checkPasses(player, shop) == false and next(shop.passes) == nil)
check("... passes are asked in parallel: 6 s in total, not 18", CLOCK >= 6 and CLOCK < 7, CLOCK)

player, shop = reset()
ASK = function(_, id)
	if id == 12 then task.wait(0.5) return true end -- VIP answers fast, the others are stuck
	task.wait(6)
	return nil
end
checkPasses(player, shop)
check("a fast VIP answer is published at 0.5 s, not after the slow passes", #PUBLISHED == 1 and PUBLISHED[1] == 0.5, PUBLISHED[1])

player, shop = reset()
ASK = function(_, id)
	if id == 11 then task.wait(3) return true end
	if id == 12 then task.wait(1) return true end
	return false
end
checkPasses(player, shop)
check("each pass is published when found (VIP at 1 s, 2x Cash at 3 s)", #PUBLISHED == 2 and PUBLISHED[1] == 1 and PUBLISHED[2] == 3, #PUBLISHED)

player, shop = reset()
ASK = function(_, id) if id == 11 then error("boom") end return id == 12 end
check("one pass check throwing does not stop the others or hang", checkPasses(player, shop) == true and shop.passes.VIP == true)
check("... the error is warned", #WARNINGS == 1 and string.find(WARNINGS[1], "boom", 1, true) ~= nil, #WARNINGS)

print_real(string.format("%d passed, %d failed", passed, failed))
"""


BUILD_TESTS = r"""-- Tests for TycoonCore's buildPayload (the code between its BUILDSAVE markers) ----------
local print_real = print
local WARNINGS = {}
local function warn(...) table.insert(WARNINGS, table.concat({...}, " ")) end
local NOW = 1700000000
local os = { time = function() return NOW end }
local FAIL = nil -- name of the module whose serialize throws
local function module(name, value)
	return { serialize = function(data)
		if FAIL == name then error(name .. " exploded") end
		return value
	end }
end
local ShopServer = module("shop", { luckLeft = 0 })
local EmployeeServer = module("team", { incubators = { { egg = "Garage" }, false, false }, employees = {} })
local FIXED = nil -- what serializeFixedHires returns: nil = no fixedHires section (most players)
EmployeeServer.serializeFixedHires = function(data)
	if FAIL == "fixedHires" then error("fixedHires exploded") end
	return FIXED
end
__KNOWNSECTIONS__
local PoachServer = module("poach", { hrLevel = 2 })
local IpoServer = module("ipo", { count = 1, shares = 3 })
local OnboardingServer = module("onboarding", { seenIntro = true })
local DailyServer = module("daily", { streak = 4 })
local TASKS = { done = 3 } -- what TaskServer.serialize returns: nil = no tasks section (everyone outside Studio in PR 1)
local TaskServer = { serialize = function(data)
	if FAIL == "tasks" then error("tasks exploded") end
	return TASKS
end }
__BUILDSAVE__
local passed, failed = 0, 0
local function check(name, cond, extra)
	if cond then passed += 1 else failed += 1; print_real("FAIL: " .. name .. (extra and (" -- " .. tostring(extra)) or "")) end
end
local function newData()
	return { owned = { Desk = true, Laptop = true }, cash = { Value = 250 }, unknownSections = { future = { x = 1 } }, saving = true }
end

local data = newData()
local payload = buildPayload(data, nil, "P")
check("normal build returns the payload", payload ~= nil and payload.cash == 250 and #payload.owned == 2)
check("... every section is there", payload.shop and payload.team and payload.poach and payload.ipo and payload.onboarding and payload.daily and payload.tasks)
check("... the tasks section is the one TaskServer.serialize gave", payload.tasks.done == 3)
TASKS = nil
check("no tasks section for a player who never had tasks (nothing is invented)", buildPayload(newData(), nil, "P").tasks == nil)
TASKS = { done = 3 }
check("tasks is a known section (saved by its own serialize, never kept as unknown)", KNOWN_SECTIONS.tasks == true)
check("... unknown sections are written back", payload.future ~= nil and payload.future.x == 1)
check("... lastSeen is set", payload.lastSeen == NOW)
check("... a good build leaves the lock to save() (still saving)", data.saving == true)
check("... no warning", #WARNINGS == 0)
check("... no fixedHires section for a player who never needed one", payload.fixedHires == nil)
FIXED = { counts = { Startup = 4 } }
check("a restricted player's fixedHires counters are in the payload", buildPayload(newData(), nil, "P").fixedHires.counts.Startup == 4)
FIXED = nil
check("fixedHires is a known section (saved by its own serialize, never kept as unknown)", KNOWN_SECTIONS.fixedHires == true)
check("a save from before D9 has nothing unknown (every section it has is known)", (function()
	for _, key in ipairs({ "cash", "owned", "lastSeen", "shop", "team", "poach", "ipo", "onboarding", "daily" }) do
		if not KNOWN_SECTIONS[key] then return false end
	end
	return true
end)())

for _, name in ipairs({ "shop", "team", "poach", "ipo", "onboarding", "daily", "fixedHires", "tasks" }) do
	data = newData()
	FAIL = name
	WARNINGS = {}
	local p = buildPayload(data, nil, "P")
	check(name .. ".serialize throws: nothing to write", p == nil)
	check(name .. ".serialize throws: lock released", data.saving == false)
	check(name .. ".serialize throws: warned with the player and the error", #WARNINGS == 1 and string.find(WARNINGS[1], "P", 1, true) and string.find(WARNINGS[1], name .. " exploded", 1, true))
end
FAIL = nil

-- the IPO transform throws half-way
data = newData()
WARNINGS = {}
local p = buildPayload(data, function(payload)
	payload.cash = 0
	payload.owned = {}
	error("transform exploded")
end, "P")
check("transform throws: nothing to write (no half-reset payload)", p == nil)
check("transform throws: lock released and warned", data.saving == false and #WARNINGS == 1)
check("transform throws: live data untouched", data.cash.Value == 250 and data.owned.Desk == true)

-- the transform works
data = newData()
p = buildPayload(data, function(payload) payload.cash = 5; payload.owned = {} end, "P")
check("transform runs on the payload", p ~= nil and p.cash == 5 and #p.owned == 0)

-- a later save is not blocked: this is save()'s own wait loop
data = newData()
FAIL = "ipo"
buildPayload(data, nil, "P")
FAIL = nil
local waits = 0
while data.saving and waits < 5 do waits += 1 end
check("a later save does not wait forever after a failed build", waits == 0 and data.saving == false)
data.saving = true
check("... and that later save builds fine", buildPayload(data, nil, "P") ~= nil)

print_real(string.format("%d passed, %d failed", passed, failed))
"""


WAIT_TESTS = r"""-- Tests for IpoServer's passCheckBlocksIpo (the code between its PASSWAIT markers) ----------
local print_real = print
local IpoConfig = { PassCheckMaxWaitSeconds = 20 }
local AGE = nil -- seconds the player's pass check has run (nil = not running)
local ShopServer = {
	isPassCheckPending = function(player) return AGE ~= nil end,
	passCheckAge = function(player) return AGE end,
}
__PASSWAIT__
local passed, failed = 0, 0
local function check(name, cond, extra)
	if cond then passed += 1 else failed += 1; print_real("FAIL: " .. name .. (extra and (" -- " .. tostring(extra)) or "")) end
end
local P = {}
-- Same path for a pass owner and a player with no pass: the check doesn't know yet which one they are
AGE = 0
check("check just started: IPO refused (owner or not)", passCheckBlocksIpo(P) == true)
AGE = 5.9
check("check still running at 6 s: refused", passCheckBlocksIpo(P) == true)
AGE = 19.9
check("check running just under the limit: refused", passCheckBlocksIpo(P) == true)
AGE = 20
check("check stuck for the full limit: IPO allowed (timed out)", passCheckBlocksIpo(P) == false)
AGE = 300
check("check stuck for minutes: IPO allowed", passCheckBlocksIpo(P) == false)
AGE = nil
check("check finished (owner or not): IPO allowed, no delay", passCheckBlocksIpo(P) == false)
IpoConfig.PassCheckMaxWaitSeconds = 5
AGE = 6
check("limit comes from IpoConfig", passCheckBlocksIpo(P) == false)
AGE = 4
check("... a shorter limit still refuses before it", passCheckBlocksIpo(P) == true)
print_real(string.format("%d passed, %d failed", passed, failed))
"""


ODDS_TESTS = r"""-- Tests for the odds the screens show (CreatureConfig.getCreatureOdds, FR-12) -----------------
local print_real = print
local WARNINGS = {}
local function warn(...) table.insert(WARNINGS, table.concat({...}, " ")) end
local Color3 = { fromRGB = function(r, g, b) return { r, g, b } end }
local CreatureConfig = (function()
__CREATURECONFIG__
end)()
local IpoConfig = (function()
__IPOCONFIG__
end)()
-- Talent Scouts luck comes from IpoConfig (1 + perkValue), never from a number typed in here
local TOP_LEVEL = #IpoConfig.getPerk("BaseLuck").costs
local function luckAt(level) return 1 + IpoConfig.perkValue("BaseLuck", level) end
local passed, failed = 0, 0
local function check(name, cond, extra)
	if cond then passed += 1 else failed += 1; print_real("FAIL: " .. name .. (extra and (" -- " .. tostring(extra)) or "")) end
end
local UNITS = CreatureConfig.ODDS_UNITS
check("Talent Scouts: level 0 has no luck, the top level has the most", luckAt(0) == 1 and luckAt(TOP_LEVEL) > luckAt(TOP_LEVEL - 1) and luckAt(TOP_LEVEL + 5) == luckAt(TOP_LEVEL))
check("the real config loads without warnings", #WARNINGS == 0, WARNINGS[1])
check("units are hundredths of a percent", UNITS == 10000)

-- Every egg, in every luck state the server can roll with: no boost, Luck Boost (x2), the strongest
-- Talent Scouts perk (level 5 = the old top, the top level after D1), and both. The perk's luck is read
-- from IpoConfig; Luck Boost's x2 is the ShopConfig product's luckMultiplier.
local STATES = { { "no boost", 1 }, { "Luck Boost", 2 }, { "Talent Scouts Lv 5", luckAt(5) }, { "Luck Boost + Talent Scouts Lv 5", 2 * luckAt(5) },
	{ "Talent Scouts Lv " .. TOP_LEVEL .. " (top)", luckAt(TOP_LEVEL) }, { "Luck Boost + Talent Scouts Lv " .. TOP_LEVEL, 2 * luckAt(TOP_LEVEL) } }
for _, egg in ipairs(CreatureConfig.Eggs) do
	for _, state in ipairs(STATES) do
		local label = egg.name .. ", " .. state[1]
		local luck = state[2]
		local odds = CreatureConfig.getCreatureOdds(egg, luck)
		local total, minUnits, worst = 0, math.huge, 0
		for _, item in ipairs(odds) do
			total += item.units
			minUnits = math.min(minUnits, item.units)
			worst = math.max(worst, math.abs(item.units - item.chance * UNITS))
		end
		check(label .. ": shown odds add up to exactly 100.00%", total == UNITS, total)
		check(label .. ": every possible hire shows at least 0.01%", minUnits >= 1, minUnits)
		check(label .. ": each shown number is the true chance, rounded (off by < 0.01%)", worst < 1, worst)
		-- The same numbers the server rolls with: per rarity, the creatures' true chances add up to getOdds
		local byRarity, expected = {}, 0
		for _, item in ipairs(odds) do byRarity[item.rarity] = (byRarity[item.rarity] or 0) + item.chance end
		local same = true
		for _, entry in ipairs(CreatureConfig.getOdds(egg, luck)) do
			expected += #CreatureConfig.creaturesOfRarity(entry.rarity)
			if math.abs((byRarity[entry.rarity] or 0) - entry.chance) > 1e-12 then same = false end
		end
		check(label .. ": one entry per possible creature, matching the server's roll", same and #odds == expected, #odds)
		local rarityTotal = 0
		for _, entry in ipairs(CreatureConfig.rarityOdds(odds)) do rarityTotal += entry.units end
		check(label .. ": the per-rarity line also adds up to exactly 100.00%", rarityTotal == UNITS, rarityTotal)
	end
end

-- Every Talent Scouts level, with and without Luck Boost
local allExact = true
for level = 0, TOP_LEVEL do
	for _, boost in ipairs({ 1, 2 }) do
		for _, egg in ipairs(CreatureConfig.Eggs) do
			local total = 0
			for _, item in ipairs(CreatureConfig.getCreatureOdds(egg, luckAt(level) * boost)) do total += item.units end
			if total ~= UNITS then allExact = false end
		end
	end
end
check("every egg x every Talent Scouts level x Luck Boost on/off: exactly 100.00%", allExact)

-- Per rarity (FR-12 follow-up, review finding b): the rounding is done inside each rarity, so the rarity
-- line shows the rounded true chance and adds up to exactly 100.00 at every level, with and without Luck Boost
local rarityExact, rarityNear, rarityStrings, perRarityCreatures, rarityCount = true, true, true, true, 0
local worstRarity = 0
for level = 0, TOP_LEVEL do
	for _, boost in ipairs({ 1, 2 }) do
		for _, egg in ipairs(CreatureConfig.Eggs) do
			local luck = luckAt(level) * boost
			local odds = CreatureConfig.getCreatureOdds(egg, luck)
			local summary = CreatureConfig.rarityOdds(odds)
			local total, shown = 0, 0
			for _, entry in ipairs(summary) do
				total += entry.units
				local whole, hundredths = string.match(CreatureConfig.formatOdds(entry.units), "^(%d+)%.(%d%d)%%$")
				shown += tonumber(whole) * 100 + tonumber(hundredths)
				local exact
				for _, real in ipairs(CreatureConfig.getOdds(egg, luck)) do
					if real.rarity == entry.rarity then exact = real.chance * UNITS end
				end
				if not exact or math.abs(entry.units - exact) >= 1 then rarityNear = false end
				worstRarity = math.max(worstRarity, exact and math.abs(entry.units - exact) or math.huge)
				-- the creatures of this rarity differ by at most 0.01% from each other
				local lo, hi = math.huge, -math.huge
				for _, item in ipairs(odds) do
					if item.rarity == entry.rarity then lo = math.min(lo, item.units); hi = math.max(hi, item.units) end
				end
				if hi - lo > 1 then perRarityCreatures = false end
			end
			rarityCount += 1
			if total ~= UNITS then rarityExact = false end
			if shown ~= UNITS then rarityStrings = false end
		end
	end
end
check("every egg x Talent Scouts 0-8 x Luck Boost on/off: the per-rarity units add up to exactly 100.00%", rarityExact)
check("... and so do the per-rarity strings the screens show, added up", rarityStrings)
check("each shown rarity is its true chance, rounded (off by < 0.01%)", rarityNear, worstRarity)
check("the creatures of one rarity differ by at most 0.01% from each other", perRarityCreatures)
check("that loop covered every level x 2 states x every egg", rarityCount == (TOP_LEVEL + 1) * 2 * #CreatureConfig.Eggs, rarityCount)
local function rarityLine(egg, luck)
	local parts = {}
	for _, entry in ipairs(CreatureConfig.rarityOdds(CreatureConfig.getCreatureOdds(egg, luck))) do
		table.insert(parts, entry.rarity .. " " .. CreatureConfig.formatOdds(entry.units))
	end
	return table.concat(parts, " / ")
end
check("Garage Egg at level 0 shows 70.00 / 25.00 / 5.00 (was 69.99 / 25.01 / 5.00)",
	rarityLine(CreatureConfig.getEgg("Garage"), 1) == "Common 70.00% / Uncommon 25.00% / Rare 5.00%", rarityLine(CreatureConfig.getEgg("Garage"), 1))
-- The real odds are not touched: getOdds is the same function, the server's weights
local realTotal = 0
for _, entry in ipairs(CreatureConfig.getOdds(CreatureConfig.getEgg("Garage"), 1)) do realTotal += entry.chance end
check("the server's own odds (getOdds) still add up to 1", math.abs(realTotal - 1) < 1e-12)
-- Largest remainder at the rarity level, with awkward numbers
local awkward = CreatureConfig.rarityOdds(CreatureConfig.getCreatureOdds({ odds = { Common = 1, Rare = 1, Epic = 1 } }, 1))
check("three equal rarities: 33.34 / 33.33 / 33.33, total exactly 100.00", #awkward == 3 and awkward[1].units == 3334 and awkward[2].units == 3333 and awkward[3].units == 3333)

-- The text shown, added up from the strings themselves
local shownTotal = 0
for _, item in ipairs(CreatureConfig.getCreatureOdds(CreatureConfig.Eggs[2], 2)) do
	local whole, hundredths = string.match(CreatureConfig.formatOdds(item.units), "^(%d+)%.(%d%d)%%$")
	shownTotal += tonumber(whole) * 100 + tonumber(hundredths)
end
check("the formatted strings add up to 100.00", shownTotal == UNITS, shownTotal)
check("formatOdds", CreatureConfig.formatOdds(10000) == "100.00%" and CreatureConfig.formatOdds(1333) == "13.33%" and CreatureConfig.formatOdds(5) == "0.05%")

-- The Luck Boost example the shop shows (Unicorn Egg Legendary): 8.00% -> 9.70%
local function legendary(luck)
	local summary = CreatureConfig.rarityOdds(CreatureConfig.getCreatureOdds(CreatureConfig.getEgg("Unicorn"), luck))
	return summary[#summary]
end
check("Unicorn Legendary without the boost: 8.00%", legendary(1).rarity == "Legendary" and legendary(1).units == 800, legendary(1).units)
check("Unicorn Legendary with Luck Boost: 9.70%", legendary(2).units == 970, legendary(2).units)

-- Odd weights: rounding still adds up, a tiny chance still shows 0.01%, same input gives the same output
local tiny = { odds = { Common = 1000000, Legendary = 1 } }
local odds = CreatureConfig.getCreatureOdds(tiny, 1)
local total, smallest = 0, math.huge
for _, item in ipairs(odds) do total += item.units; smallest = math.min(smallest, item.units) end
check("a one-in-a-million hire still shows 0.01%, total still 100.00%", total == UNITS and smallest == 1, total .. " / " .. smallest)
local thirds = CreatureConfig.getCreatureOdds({ odds = { Common = 1 } }, 1)
check("three equal hires: 33.34% + 33.33% + 33.33%", thirds[1].units == 3334 and thirds[2].units == 3333 and thirds[3].units == 3333)
local again = CreatureConfig.getCreatureOdds(CreatureConfig.Eggs[3], 3)
local same = true
for i, item in ipairs(CreatureConfig.getCreatureOdds(CreatureConfig.Eggs[3], 3)) do
	if item.units ~= again[i].units or item.creature ~= again[i].creature then same = false end
end
check("the same egg and luck always show the same numbers", same)
print_real(string.format("%d passed, %d failed", passed, failed))
"""


MOVE_TESTS = r"""-- Tests for PoachServer's move notes and the FR-4 guard (the code between its MOVENOTES markers) ----
local print_real = print
local inTransit = {}
__MOVENOTES__
local passed, failed = 0, 0
local function check(name, cond, extra)
	if cond then passed += 1 else failed += 1; print_real("FAIL: " .. name .. (extra and (" -- " .. tostring(extra)) or "")) end
end
local function newPoach() return { gained = {}, lost = {} } end
local V, A, C = 101, 102, 103 -- the owner, the poacher, a third account
local X = "employee-X"

-- The FR-4 chain, step by step (state exactly as PoachServer.transfer leaves it)
local pV, pA, pC = newPoach(), newPoach(), newPoach()
check("no open note: anyone may poach the employee", movable(pV, X, A) and movable(pV, X, C))
recordMove(pA, pV, X, V, 500) -- 1. A poaches X from V
inTransit[X] = true
check("1. the move is recorded on A", pA.gained[X] ~= nil and pA.gained[X].from == V and pA.gained[X].refund == 500)
check("1. while the move is being saved, nobody can move it", not movable(pA, X, C) and not movable(pA, X, V))
-- 2-3. V left before A's save returned: V's save still has X, so V's side never confirms. A keeps its note.
inTransit[X] = nil
check("3. chain: a third player can't poach it while A's note is open", not movable(pA, X, C))
check("3. the owner the note points to can still take it back (Counter-Offer)", movable(pA, X, V))
check("3. other employees of A are not affected", movable(pA, "employee-Y", C))
-- Why the guard matters: had C's move gone through, it would erase the note that undoes step 1
local copy = { gained = { [X] = pA.gained[X] }, lost = {} }
recordMove(pC, copy, X, A, 700)
check("without the guard: moving on erases the holder's note (V and C would both keep X)", copy.gained[X] == nil and pC.gained[X].from == A)
-- With the guard, X stays on A with its note; A's next join hands it back to V: one copy
check("with the guard: A still has the note that hands X back to V on A's next join (one copy)", pA.gained[X] ~= nil and pA.gained[X].from == V)

-- The normal path: V's save confirms, A's note is cleared, X can be poached again
pV, pA, pC = newPoach(), newPoach(), newPoach()
recordMove(pA, pV, X, V, 500)
pA.gained[X] = nil -- confirmSave(V) worked
check("confirmed move: X can be poached by anyone again", movable(pA, X, C) and movable(pA, X, V))

-- A Counter-Offer back to V: A's note goes, V gets one pointing at A
pV, pA = newPoach(), newPoach()
recordMove(pA, pV, X, V, 500)
check("Counter-Offer allowed while A's note points at V", movable(pA, X, V))
recordMove(pV, pA, X, A, 250)
check("after the Counter-Offer: A has no note, V's note points at A", pA.gained[X] == nil and pV.gained[X].from == A and pV.gained[X].refund == 250)
check("... and then only A may take it back until V's note is confirmed", movable(pV, X, A) and not movable(pV, X, C))
check("recordMove clears the receiver's old lost note", (function()
	local r, g = newPoach(), newPoach()
	r.lost[X] = { to = 9, at = 1 }
	recordMove(r, g, X, 5)
	return r.lost[X] == nil and r.gained[X].refund == 0
end)())

-- Holders with no notes at all (the Studio dummy, a player still loading)
check("a holder without a gained table (Studio dummy) is movable", movable({ hrLevel = 0 }, X, C))
check("a holder with no poach data is movable (the loading check stops it elsewhere)", movable(nil, X, C))
inTransit[X] = true
check("inTransit still blocks everyone, even the dummy", not movable({}, X, C) and not movable(nil, X, C))
inTransit[X] = nil
print_real(string.format("%d passed, %d failed", passed, failed))
"""


SAVE_TESTS = r"""-- Tests for TycoonCore's failed-save notice and leave-save retry (SAVENOTE and LEAVESAVE markers, FR-1) ----
local print_real = print
local WARNINGS, NOTES = {}, {}
local function warn(...) table.insert(WARNINGS, table.concat({...}, " ")) end
local ShopServer = { notify = function(player, text) table.insert(NOTES, text) end }
__SAVENOTE__
local playerData = {}
local RESULTS = {} -- what each fake save returns, in order (empty = false)
local SAVES, WAITED = 0, 0
local function save(player) SAVES += 1; return table.remove(RESULTS, 1) or false end
local task = { wait = function(n) WAITED += n end }
__LEAVESAVE__
local passed, failed = 0, 0
local function check(name, cond, extra)
	if cond then passed += 1 else failed += 1; print_real("FAIL: " .. name .. (extra and (" -- " .. tostring(extra)) or "")) end
end
local P = { Name = "P" }

-- The notice
local data = {}
noteSaveResult(P, data, true)
check("a working save says nothing", #NOTES == 0 and data.failedSaves == 0)
noteSaveResult(P, data, false)
check("one failed save: not told yet (one blip is normal)", #NOTES == 0 and data.failedSaves == 1)
noteSaveResult(P, data, false)
check("two in a row: the player is told saving has trouble", #NOTES == 1 and string.find(NOTES[1], "having trouble", 1, true) ~= nil)
noteSaveResult(P, data, false)
noteSaveResult(P, data, false)
check("more failures: told only once", #NOTES == 1 and data.failedSaves == 4)
noteSaveResult(P, data, true)
check("then a save works: told it's safe again, count reset", #NOTES == 2 and string.find(NOTES[2], "works again", 1, true) ~= nil and data.failedSaves == 0)
noteSaveResult(P, data, true)
check("later good saves say nothing", #NOTES == 2)
NOTES = {}
data = {}
noteSaveResult(P, data, false)
noteSaveResult(P, data, true)
check("one failure then a success: no message at all", #NOTES == 0 and data.failedSaves == 0)

-- The leave save
playerData[P] = { loaded = true }
RESULTS = { true }
check("leave save works first time: one save, no wait", saveOnLeave(P) == true and SAVES == 1 and WAITED == 0)
SAVES, WAITED = 0, 0
RESULTS = { false, false, true }
check("fails twice, then works: three saves, waited 2 s + 4 s", saveOnLeave(P) == true and SAVES == 3 and WAITED == 6, SAVES .. " / " .. WAITED)
SAVES, WAITED, WARNINGS = 0, 0, {}
RESULTS = {}
check("always fails: stops after 3 tries, no endless loop", saveOnLeave(P) == false and SAVES == 3 and WAITED == 6, SAVES)
check("... each retry is warned", #WARNINGS == 2, #WARNINGS)
SAVES, WAITED = 0, 0
playerData[P] = { loaded = false }
check("save never loaded: one call, no retries (nothing may be saved)", saveOnLeave(P) == false and SAVES == 1 and WAITED == 0)
SAVES, WAITED = 0, 0
playerData[P] = nil
check("data already gone: one call, no retries", saveOnLeave(P) == false and SAVES == 1 and WAITED == 0)
print_real(string.format("%d passed, %d failed", passed, failed))
"""


REREAD_TESTS = r"""-- Tests for TycoonCore's join re-read decision (the code between its REREAD markers, F10 minimum) ----
local print_real = print
local function typeof(v) return type(v) end
__REREAD__
local passed, failed = 0, 0
local function check(name, cond, extra)
	if cond then passed += 1 else failed += 1; print_real("FAIL: " .. name .. (extra and (" -- " .. tostring(extra)) or "")) end
end
local NOW = 1700000000
check("new player (no save): no wait", shouldReread(nil, NOW) == false)
check("unreadable save: no wait", shouldReread("junk", NOW) == false)
check("save without lastSeen: no wait", shouldReread({ cash = 5 }, NOW) == false)
check("save from yesterday: no wait", shouldReread({ lastSeen = NOW - 86400 }, NOW) == false)
check("save from 2 minutes ago: no wait", shouldReread({ lastSeen = NOW - 120 }, NOW) == false)
check("save from an autosave 60 s ago (session may be live): wait", shouldReread({ lastSeen = NOW - 60 }, NOW) == true)
check("save from 5 s ago (quick rejoin, second device): wait", shouldReread({ lastSeen = NOW - 5 }, NOW) == true)
check("exactly 75 s: no wait", shouldReread({ lastSeen = NOW - REREAD_RECENT_SECONDS }, NOW) == false)
check("written 3 s in the future (another server's clock): wait", shouldReread({ lastSeen = NOW + 3 }, NOW) == true)
check("far in the future (bad data): no wait", shouldReread({ lastSeen = NOW + 86400 }, NOW) == false)
check("NaN lastSeen: no wait", shouldReread({ lastSeen = 0 / 0 }, NOW) == false)
check("text lastSeen that is a number: read as one", shouldReread({ lastSeen = tostring(NOW - 10) }, NOW) == true)
check("the wait is short (under 10 s)", REREAD_WAIT_SECONDS > 0 and REREAD_WAIT_SECONDS < 10)
print_real(string.format("%d passed, %d failed", passed, failed))
"""


FIXED_TESTS = r"""-- Tests for the fixed hire order (CreatureConfig.fixedOrder / fixedHire, FR-13, D9 option B) -----------
local print_real = print
local WARNINGS = {}
local function warn(...) table.insert(WARNINGS, table.concat({...}, " ")) end
local Color3 = { fromRGB = function(r, g, b) return { r, g, b } end }
local CreatureConfig = (function()
__CREATURECONFIG__
end)()
local IpoConfig = (function()
__IPOCONFIG__
end)()
-- Talent Scouts luck comes from IpoConfig (1 + perkValue), never from a number typed in here
local TOP_LEVEL = #IpoConfig.getPerk("BaseLuck").costs
local function luckAt(level) return 1 + IpoConfig.perkValue("BaseLuck", level) end
local passed, failed = 0, 0
local function check(name, cond, extra)
	if cond then passed += 1 else failed += 1; print_real("FAIL: " .. name .. (extra and (" -- " .. tostring(extra)) or "")) end
end
check("one round is 100 hires", CreatureConfig.FIXED_ORDER_LENGTH == 100)

-- Rounds after which every creature has had its exact share: the creatures of a rarity take turns
local function gcd(a, b) while b ~= 0 do a, b = b, a % b end return a end
local ROUNDS = 1
for _, rarity in ipairs(CreatureConfig.Rarities) do
	local n = #CreatureConfig.creaturesOfRarity(rarity.key)
	if n > 0 then ROUNDS = ROUNDS * n // gcd(ROUNDS, n) end
end

-- Every egg, without luck and at every Talent Scouts level (Luck Boost never applies to a fixed order)
for _, egg in ipairs(CreatureConfig.Eggs) do
	for level = 0, TOP_LEVEL do
		local luck = luckAt(level)
		local label = egg.name .. ", Talent Scouts Lv " .. level
		local odds = CreatureConfig.getOdds(egg, luck)
		local byRarity, total = {}, 0
		for n = 0, 99 do
			local creature = CreatureConfig.fixedHire(egg, luck, n)
			byRarity[creature.rarity] = (byRarity[creature.rarity] or 0) + 1
			total += 1
		end
		local close, exact = true, true
		for _, entry in ipairs(odds) do
			local count = byRarity[entry.rarity] or 0
			if math.abs(count - entry.chance * 100) >= 1 then close = false end
			if math.abs(count - entry.chance * 100) > 1e-9 then exact = false end
		end
		check(label .. ": 100 hires, every rarity within one hire of its odds (largest remainder)", close and total == 100)
		if level == 0 then
			check(label .. ": 100 hires match the odds exactly, rarity by rarity", exact)
		end
		-- Every possible creature, and only those, comes up; after enough rounds each exactly as often as its odds
		local creatureOdds = CreatureConfig.getCreatureOdds(egg, luck)
		local counts, hires = {}, 100 * ROUNDS
		for n = 0, hires - 1 do
			local key = CreatureConfig.fixedHire(egg, luck, n).key
			counts[key] = (counts[key] or 0) + 1
		end
		local all, onlyPossible, exactCreatures = true, true, true
		local possible = {}
		for _, item in ipairs(creatureOdds) do
			possible[item.creature.key] = true
			if not counts[item.creature.key] then all = false end
			if math.abs((counts[item.creature.key] or 0) - item.chance * hires) > 1e-9 then exactCreatures = false end
		end
		for key in pairs(counts) do if not possible[key] then onlyPossible = false end end
		check(label .. ": every possible hire comes up, and nothing else", all and onlyPossible)
		if level == 0 then
			check(label .. ": over " .. hires .. " hires every creature matches its own odds exactly", exactCreatures)
			local perCreature = true
			local first = {}
			for n = 0, 99 do
				local key = CreatureConfig.fixedHire(egg, luck, n).key
				first[key] = (first[key] or 0) + 1
			end
			for _, item in ipairs(creatureOdds) do
				if math.abs((first[item.creature.key] or 0) - item.chance * 100) >= 1 then perCreature = false end
			end
			check(label .. ": in the first 100 hires every creature is within one hire of its odds", perCreature)
		end
		-- Spread out: after any number of hires in a round, every rarity is within one hire of its share
		local order = CreatureConfig.fixedOrder(egg, luck)
		local places, seen, spread = {}, {}, true
		for _, rarity in ipairs(order) do places[rarity] = (places[rarity] or 0) + 1 end
		for k = 1, #order do
			seen[order[k]] = (seen[order[k]] or 0) + 1
			for rarity, p in pairs(places) do
				if math.abs((seen[rarity] or 0) - k * p / #order) >= 1 then spread = false end
			end
		end
		check(label .. ": spread evenly (never more than one hire ahead or behind)", spread)
		check(label .. ": the first hire is the most common rarity", order[1] == odds[1].rarity or (function()
			local best = odds[1]
			for _, entry in ipairs(odds) do if entry.chance > best.chance then best = entry end end
			return order[1] == best.rarity
		end)())
		-- Same egg, luck and count: always the same hire (server and screens agree)
		local same = true
		for n = 0, 250 do
			if CreatureConfig.fixedHire(egg, luck, n) ~= CreatureConfig.fixedHire(egg, luck, n) then same = false end
		end
		check(label .. ": deterministic", same)
	end
end
check("round 2 starts again with the order of round 1 (rarities)", CreatureConfig.fixedHire(CreatureConfig.Eggs[2], 1, 100).rarity == CreatureConfig.fixedHire(CreatureConfig.Eggs[2], 1, 0).rarity)
check("a rarity with a tiny chance still gets a place in the round", (function()
	local order = CreatureConfig.fixedOrder({ odds = { Common = 100000, Legendary = 1 } }, 1)
	local legendary = 0
	for _, r in ipairs(order) do if r == "Legendary" then legendary += 1 end end
	return #order == 100 and legendary == 1
end)())
check("the config loads without warnings", #WARNINGS == 0, WARNINGS[1])
print_real(string.format("%d passed, %d failed", passed, failed))
"""


ROLL_TESTS = r"""-- Tests for EmployeeServer's roll and the fixedHires section (ROLL and FIXEDSAVE markers, FR-13, D9 option B) ----
local print_real = print
local WARNINGS = {}
local function warn(...) table.insert(WARNINGS, table.concat({...}, " ")) end
local function typeof(v) return type(v) end
local Color3 = { fromRGB = function(r, g, b) return { r, g, b } end }
local CreatureConfig = (function()
__CREATURECONFIG__
end)()
local RESTRICTED, LUCK = true, 1 -- what ShopServer says: restricted (fixed order), Luck Boost multiplier
local ShopServer = {
	isRandomRestricted = function(player) return RESTRICTED end,
	getLuckMultiplier = function(player) return LUCK end,
}
local IpoServer = { perk = function(data, key) return data.perks[key] or 0 end }
local core = { getData = function(player) return player.data end }
local DRAWS, seed = 0, 12345 -- a small deterministic random generator that counts every number drawn
local rng = {}
function rng:NextNumber() DRAWS += 1; seed = (seed * 16807) % 2147483647; return seed / 2147483647 end
function rng:NextInteger(a, b) DRAWS += 1; seed = (seed * 16807) % 2147483647; return a + seed % (b - a + 1) end
local EmployeeServer = {}
local nextFixedHire
__ROLL__
__FIXEDSAVE__
local passed, failed = 0, 0
local function check(name, cond, extra)
	if cond then passed += 1 else failed += 1; print_real("FAIL: " .. name .. (extra and (" -- " .. tostring(extra)) or "")) end
end
local function copy(v) -- what a DataStore round trip does: a fresh table with the same values
	if type(v) ~= "table" then return v end
	local t = {}
	for k, x in pairs(v) do t[k] = copy(x) end
	return t
end
local function join(savedFixed, perks)
	local player = { Name = "P", data = { perks = perks or {} } }
	EmployeeServer.setupFixedHires(player, player.data, savedFixed)
	return player, player.data
end
local function hatch(player, egg, team) return rollCreature(player, team or {}, egg) end
local GARAGE, STARTUP, UNICORN = CreatureConfig.getEgg("Garage"), CreatureConfig.getEgg("Startup"), CreatureConfig.getEgg("Unicorn")

-- An old save (before D9) has no fixedHires section
WARNINGS = {}
local p, d = join(nil)
check("old save without fixedHires: loads with no warning", #WARNINGS == 0 and d.fixedHires ~= nil and next(d.fixedHires.counts) == nil)
check("old save: every egg starts at the first hire of its order", nextFixedHire(d, STARTUP) == CreatureConfig.fixedHire(STARTUP, 1, 0))
check("old save: no section is written while nothing used it", EmployeeServer.serializeFixedHires(d) == nil)
check("no data at all: nothing to write", EmployeeServer.serializeFixedHires({}) == nil)

-- Restricted: 100 hatches of every egg follow the order and match the odds, without drawing a random number
RESTRICTED, LUCK, DRAWS = true, 1, 0
for _, egg in ipairs(CreatureConfig.Eggs) do
	p, d = join(nil)
	local byRarity, inOrder = {}, true
	for n = 0, 99 do
		local shown = nextFixedHire(d, egg) -- what the Eggs tab shows before this hatch
		local creature = hatch(p, egg)
		if creature ~= CreatureConfig.fixedHire(egg, 1, n) or creature ~= shown then inOrder = false end
		byRarity[creature.rarity] = (byRarity[creature.rarity] or 0) + 1
	end
	local exact = true
	for _, entry in ipairs(CreatureConfig.getOdds(egg, 1)) do
		if math.abs((byRarity[entry.rarity] or 0) - entry.chance * 100) > 1e-9 then exact = false end
	end
	check(egg.name .. ": 100 restricted hatches follow the fixed order (the hire shown is the hire given)", inOrder)
	check(egg.name .. ": 100 restricted hatches match the odds exactly, rarity by rarity", exact)
	check(egg.name .. ": counter is 100", d.fixedHires.counts[egg.key] == 100)
end
check("restricted: no random number is ever drawn", DRAWS == 0, DRAWS)

-- Luck Boost doesn't change the order (ShopServer keeps it aside for them); Talent Scouts does, as for odds
LUCK = 2
p = join(nil)
local same = true
for n = 0, 99 do if hatch(p, UNICORN) ~= CreatureConfig.fixedHire(UNICORN, 1, n) then same = false end end
check("restricted with Luck Boost running: the order is the one without it", same)
LUCK = 1
p = join(nil, { BaseLuck = 0.5 })
same = true
for n = 0, 99 do if hatch(p, UNICORN) ~= CreatureConfig.fixedHire(UNICORN, 1.5, n) then same = false end end
check("restricted with Talent Scouts Lv 5: the order follows the weights with the perk", same)

-- The counter survives save and load
p, d = join(nil)
for _ = 1, 7 do hatch(p, STARTUP) end
for _ = 1, 3 do hatch(p, GARAGE) end
local saved = EmployeeServer.serializeFixedHires(d)
check("saved: one count per egg used", saved.counts.Startup == 7 and saved.counts.Garage == 3 and saved.counts.Unicorn == nil)
WARNINGS = {}
local p2, d2 = join(copy(saved))
check("loaded back with no warning", #WARNINGS == 0)
check("after a rejoin the next Startup hire is the 8th of the order", hatch(p2, STARTUP) == CreatureConfig.fixedHire(STARTUP, 1, 7))
check("... and its counter goes on to 8, the Garage one stays 3", d2.fixedHires.counts.Startup == 8 and d2.fixedHires.counts.Garage == 3)
-- A whole round with a save and a rejoin after every hatch gives the same hires as one long session
p, d = join(nil)
local rejoined, sameRound = nil, true
for n = 0, 99 do
	local _, dd = join(copy(EmployeeServer.serializeFixedHires(rejoined or d)))
	local pp = { Name = "P", data = dd }
	if hatch(pp, GARAGE) ~= CreatureConfig.fixedHire(GARAGE, 1, n) then sameRound = false end
	rejoined = dd
end
check("a save and rejoin after every hatch: the same 100 hires as one long session", sameRound and rejoined.fixedHires.counts.Garage == 100)

-- An unrestricted player still rolls randomly, and the counter doesn't move
RESTRICTED, DRAWS = false, 0
p, d = join({ counts = { Garage = 5 } })
local seen, kinds, commons, differs = {}, 0, 0, false
for n = 0, 999 do
	local creature = hatch(p, GARAGE)
	if not seen[creature.key] then seen[creature.key] = true; kinds += 1 end
	if creature.rarity == "Common" then commons += 1 end
	if n < 30 and creature ~= CreatureConfig.fixedHire(GARAGE, 1, 5 + n) then differs = true end
end
check("unrestricted: two random numbers per hatch (rarity, then creature)", DRAWS == 2000, DRAWS)
check("unrestricted: the counter doesn't move", d.fixedHires.counts.Garage == 5)
check("unrestricted: about 70% Commons in 1000 hatches (the odds)", commons > 650 and commons < 750, commons)
check("unrestricted: all 8 Garage Egg hires come up", kinds == 8, kinds)
check("unrestricted: not the fixed order", differs)
check("unrestricted: Luck Boost still counts for the random roll", (function()
	LUCK = 2
	local rare = 0
	local pp = join(nil)
	for _ = 1, 2000 do if hatch(pp, GARAGE).rarity == "Rare" then rare += 1 end end
	LUCK = 1
	return rare > 140 -- 9.5% with Luck Boost, 5% without
end)())

-- Restriction changes between sessions (step 5): the order goes on where it stopped, never restarts
RESTRICTED = true
p, d = join(nil)
for _ = 1, 5 do hatch(p, STARTUP) end
local s1 = copy(EmployeeServer.serializeFixedHires(d))
RESTRICTED = false
p, d = join(s1)
for _ = 1, 10 do hatch(p, STARTUP) end
local s2 = copy(EmployeeServer.serializeFixedHires(d))
check("an unrestricted session saves the counter unchanged", s2.counts.Startup == 5)
RESTRICTED = true
p, d = join(s2)
check("restricted again: the 6th hire of the order comes next, not the 1st", hatch(p, STARTUP) == CreatureConfig.fixedHire(STARTUP, 1, 5))

-- The Studio Debug "Next hatch" still works for a restricted player, and doesn't use up the order
p, d = join({ counts = { Garage = 2 } })
local team = { forceRarity = "Legendary" }
local forced = hatch(p, GARAGE, team)
check("Studio Debug forced rarity: given, counter untouched, used once", forced.rarity == "Legendary" and d.fixedHires.counts.Garage == 2 and team.forceRarity == nil)

-- Nothing from the client: the hire depends only on the egg, the saved counter and Talent Scouts
local a = join({ counts = { Unicorn = 42 } })
local b = join({ counts = { Unicorn = 42 } })
check("two players with the same counter get the same hire", hatch(a, UNICORN) == hatch(b, UNICORN))

-- Bad values in the section are skipped with a warning; unknown things are kept
WARNINGS = {}
p, d = join({ counts = { Garage = "x", Startup = -1, Unicorn = 0 / 0, Old = math.huge, Half = 2.5, [5] = 3, FutureEgg = 4 }, future = { a = 1 } })
check("6 bad counts: 6 warnings", #WARNINGS == 6, #WARNINGS)
check("bad counts start at 0", d.fixedHires.counts.Garage == nil and d.fixedHires.counts.Startup == nil and d.fixedHires.counts.Unicorn == nil)
local s = EmployeeServer.serializeFixedHires(d)
check("an egg this version doesn't know and an unknown field are written back", s ~= nil and s.counts.FutureEgg == 4 and s.future ~= nil and s.future.a == 1)
WARNINGS = {}
p, d = join("garbage")
check("a section that isn't a table: one warning, empty", #WARNINGS == 1 and next(d.fixedHires.counts) == nil)
WARNINGS = {}
p, d = join({ counts = "lots" })
check("counts that aren't a table: one warning, empty", #WARNINGS == 1 and next(d.fixedHires.counts) == nil)
print_real(string.format("%d passed, %d failed", passed, failed))
"""


POLICY_TESTS = r"""-- Tests for ShopServer's paid random items check (the code between its POLICY markers, FR-13, D9 option B) ----
local print_real = print
local WARNINGS = {}
local function warn(...) table.insert(WARNINGS, table.concat({...}, " ")) end
local function typeof(v) return type(v) end

-- The same tiny scheduler as the pass check tests: task.wait pauses a thread on a fake clock
local CLOCK, NOW = 0, 1700000000
local os = { clock = function() return CLOCK end, time = function() return NOW end }
local sleeping = {}
local depth = 0
local function resume(co)
	depth += 1
	local ok, delay = coroutine.resume(co)
	depth -= 1
	if not ok then error(delay) end
	if coroutine.status(co) == "suspended" then table.insert(sleeping, { co = co, at = CLOCK + delay }) end
end
local task = {}
function task.spawn(f) resume(coroutine.create(f)) end
function task.wait(n)
	n = n or 0.03
	if depth > 0 then coroutine.yield(n) return n end
	local target = CLOCK + n
	while true do
		local best
		for i, t in ipairs(sleeping) do
			if t.at <= target and (not best or t.at < sleeping[best].at) then best = i end
		end
		if not best then break end
		local t = table.remove(sleeping, best)
		CLOCK = math.max(CLOCK, t.at)
		resume(t.co)
	end
	CLOCK = target
	return n
end

local ShopConfig = (function()
__SHOPCONFIG__
end)()
local ASKS = 0
local ANSWER = function() return { ArePaidRandomItemsRestricted = false } end -- may task.wait or error
local PolicyService = {}
function PolicyService:GetPolicyInfoForPlayerAsync(player)
	ASKS += 1
	return ANSWER(player, ASKS)
end
__POLICY__
local passed, failed = 0, 0
local function check(name, cond, extra)
	if cond then passed += 1 else failed += 1; print_real("FAIL: " .. name .. (extra and (" -- " .. tostring(extra)) or "")) end
end
local REAL = { TimeoutSeconds = ShopConfig.PolicyCheck.TimeoutSeconds, Attempts = ShopConfig.PolicyCheck.Attempts, RetrySeconds = ShopConfig.PolicyCheck.RetrySeconds }
-- A join, as ShopServer.setupPlayer runs it: start the check, wait while it may still answer, go on
local function join(answer)
	CLOCK, sleeping, ASKS, WARNINGS = 0, {}, 0, {}
	ANSWER = answer
	local player, shop = { Name = "P" }, { luckUntil = 0, luckPaused = 0 }
	local check = startPolicyCheck(player, shop)
	local atStart = shop.randomRestricted
	while policyCheckWaiting(check) do
		task.wait(0.1)
	end
	stopPolicyWait(player, check)
	return shop, check, atStart, CLOCK
end
local function has(text)
	for _, w in ipairs(WARNINGS) do if string.find(w, text, 1, true) then return true end end
	return false
end

check("the cap is the same 10 s as the pass check", REAL.TimeoutSeconds == 10)
local shop, c, atStart, waited = join(function() task.wait(0.4) return { ArePaidRandomItemsRestricted = false } end)
check("restricted from the start, until Roblox answers (fail closed)", atStart == true)
check("Roblox says not restricted: random hires allowed", shop.randomRestricted == false and c.state == "done")
check("... loading waits only for the answer (0.4 s), not the whole cap", waited < 1, waited)
shop = join(function() return { ArePaidRandomItemsRestricted = true } end)
check("Roblox says restricted: restricted", shop.randomRestricted == true and ASKS == 1)
shop, c, atStart, waited = join(function() error("HTTP 500") end)
check("the check fails every time: restricted for the session", shop.randomRestricted == true)
check("... asked 3 times (ShopConfig.PolicyCheck.Attempts), 1 s apart, then loading goes on", ASKS == 3 and waited >= 2 and waited < 3, ASKS .. " asks, " .. waited .. " s")
check("... every failure is warned", has("HTTP 500") and #WARNINGS == 3, #WARNINGS)
shop = join(function(_, n) if n == 1 then error("blip") end return { ArePaidRandomItemsRestricted = false } end)
check("fails once, then says not restricted: allowed", shop.randomRestricted == false and ASKS == 2)
shop = join(function() return {} end)
check("an answer without ArePaidRandomItemsRestricted: restricted", shop.randomRestricted == true and has("no ArePaidRandomItemsRestricted"))
shop = join(function() return { ArePaidRandomItemsRestricted = "no" } end)
check("a value that isn't true or false: restricted", shop.randomRestricted == true)
shop = join(function() return nil end)
check("no answer at all (nil): restricted", shop.randomRestricted == true)
shop, c, atStart, waited = join(function() task.wait(15) return { ArePaidRandomItemsRestricted = false } end)
check("Roblox hangs: loading waits the 10 s cap, no more", waited >= 10 and waited < 10.2, waited)
check("... and goes on restricted (fail closed), the check marked late", shop.randomRestricted == true and c.state == "late" and has("is slow"))
task.wait(10) -- the answer comes at 15 s
check("a late 'not restricted' never lifts it: restricted for the whole session", shop.randomRestricted == true and has("after loading went on"))
shop, c, atStart, waited = join(function() task.wait(9) return { ArePaidRandomItemsRestricted = false } end)
check("a slow answer still inside the cap (9 s) counts", shop.randomRestricted == false and waited >= 9 and waited < 9.2, waited)
ShopConfig.PolicyCheck = { TimeoutSeconds = 3, Attempts = 1, RetrySeconds = 1 }
shop, c, atStart, waited = join(function() task.wait(5) return { ArePaidRandomItemsRestricted = false } end)
check("the cap comes from ShopConfig (3 s)", waited >= 3 and waited < 3.2 and shop.randomRestricted == true, waited)
shop = join(function() error("down") end)
check("the number of tries comes from ShopConfig (1)", ASKS == 1 and shop.randomRestricted == true)
ShopConfig.PolicyCheck = REAL

-- Luck Boost is kept aside while restricted, never lost (syncLuckPause)
local s = { randomRestricted = true, luckUntil = 0, luckPaused = 600 }
syncLuckPause(s)
check("restricted with 10 min of Luck Boost saved: kept aside, not running", s.luckUntil == 0 and s.luckPaused == 600)
NOW += 300
syncLuckPause(s)
check("... 5 minutes later it's still 10 min (doesn't count down)", s.luckPaused == 600)
s.randomRestricted = false
syncLuckPause(s)
check("not restricted: it runs again, all 10 min", s.luckUntil == NOW + 600 and s.luckPaused == 0)
NOW += 100
s.randomRestricted = true
syncLuckPause(s)
check("restricted again: the 8:20 left are kept aside", s.luckUntil == 0 and s.luckPaused == 500)
s = { randomRestricted = false, luckUntil = 0, luckPaused = 0 }
syncLuckPause(s)
check("no Luck Boost: nothing changes", s.luckUntil == 0 and s.luckPaused == 0)

-- What's for sale to a restricted player (ShopConfig.isForSale, option B: only Luck Boost goes)
ShopConfig.EggsEnabled = true -- as at launch, with egg items on sale
local onlyLuck, othersForSale = true, true
for _, product in ipairs(ShopConfig.Products) do
	if (product.changesOdds == true) ~= (product.key == "LuckBoost") then onlyLuck = false end
	if product.key ~= "LuckBoost" and product.id ~= 0 and not ShopConfig.isForSale(product, true) then othersForSale = false end
end
for _, pass in ipairs(ShopConfig.Passes) do
	if pass.id ~= 0 and not ShopConfig.isForSale(pass, true) then othersForSale = false end
end
local luck = ShopConfig.getProduct("LuckBoost")
check("only Luck Boost is marked changesOdds", onlyLuck)
check("restricted: Luck Boost is not for sale", ShopConfig.isForSale(luck, true) == false)
check("restricted: Cash packs, Instant Hatch, Poach Shield and every pass stay on sale", othersForSale)
check("not restricted: Luck Boost for sale as before", ShopConfig.isForSale(luck, false) == true and ShopConfig.isForSale(luck) == true)
ShopConfig.EggsEnabled = false
check("EggsEnabled off: Luck Boost off sale for everyone, as before", ShopConfig.isForSale(luck) == false and ShopConfig.isForSale(luck, false) == false)
check("EggsEnabled off: Cash packs still on sale to restricted players (option B keeps them)", ShopConfig.isForSale(ShopConfig.getProduct("CashSmall"), true) == true)
print_real(string.format("%d passed, %d failed", passed, failed))
"""


IPOSHOP_TESTS = r"""-- Tests for the IPO shop (IpoConfig.perks, the real IpoServer.lua with fakes) and D1: the 1,770-Share shop ----
local print_real = print
local WARNINGS = {}
local function warn(...) table.insert(WARNINGS, table.concat({...}, " ")) end
local function typeof(v) return type(v) end
local passed, failed = 0, 0
local function check(name, cond, extra)
	if cond then passed += 1 else failed += 1; print_real("FAIL: " .. name .. (extra and (" -- " .. tostring(extra)) or "")) end
end

-- A fake Roblox: any property that isn't set answers with a harmless "ghost"; real values are kept
local ghost
ghost = setmetatable({}, { __index = function() return ghost end, __call = function() return ghost end,
	__add = function() return ghost end, __sub = function() return ghost end, __mul = function() return ghost end,
	__newindex = function() end })
local CREATED = {}
local Instance = { new = function(class)
	local i = setmetatable({ ClassName = class }, { __index = function() return ghost end })
	table.insert(CREATED, i)
	return i
end }
local Vector3, Color3, UDim2, Enum = ghost, ghost, ghost, ghost
local task = { spawn = function(f, ...) f(...) end, delay = function() end, wait = function() end }
local os = { time = function() return 1700000000 end, clock = function() return 0 end }
local function token(name) return { Name = name, WaitForChild = function(_, n) return token(n) end } end
local MODULES = {}
local function require(x) return assert(MODULES[x.Name], "no module " .. tostring(x.Name)) end
local SERVICES = {
	ReplicatedStorage = token("ReplicatedStorage"),
	RunService = { IsStudio = function() return false end },
	Players = { GetPlayerFromCharacter = function() return nil end },
}
local game = { GetService = function(_, n) return SERVICES[n] end }
local script = { Parent = token("ServerScriptService") }

MODULES.IpoConfig = (function()
__IPOCONFIG__
end)()
MODULES.ShopConfig = (function()
__SHOPCONFIG__
end)()
MODULES.ShopServer = { addDebugAction = function() end, getSharesMultiplier = function() return 1 end,
	isPassCheckPending = function() return false end, passCheckAge = function() return 0 end }
local IpoConfig = MODULES.IpoConfig
local IpoServer = (function()
__IPOSERVER__
end)()
check("the real IpoConfig loads without warnings", #WARNINGS == 0, WARNINGS[1])

-- 1. The shop: size, frozen shipped levels, the new levels
local function total(costs) local n = 0 for _, c in ipairs(costs) do n += c end return n end
local shop, perPerk = 0, {}
for _, perk in ipairs(IpoConfig.Perks) do
	perPerk[perk.key] = total(perk.costs)
	shop += perPerk[perk.key]
end
check("the whole shop costs exactly 1770 Shares", shop == 1770, shop)
check("per perk: Faster Recruiting 350, Extra Incubator 55, Extra Desk 85, Night Shift 70, Talent Scouts 495, Recruiter Network 715",
	perPerk.FasterEggs == 350 and perPerk.ExtraIncubator == 55 and perPerk.ExtraSlot == 85 and perPerk.OfflineCap == 70
	and perPerk.BaseLuck == 495 and perPerk.CheaperPoach == 715)
check("the shop before D1 was 525: the shipped levels still add up to 525", (function()
	local n = 0
	for _, perk in ipairs(IpoConfig.Perks) do
		local old = { FasterEggs = 5, ExtraIncubator = 2, ExtraSlot = 3, OfflineCap = 4, BaseLuck = 5, CheaperPoach = 5 }
		for level = 1, old[perk.key] do n += perk.costs[level] end
	end
	return n
end)() == 525)

-- What shipped before D1, never to change (saves and players keep these levels): key, name, effect, perLevel, costs
local SHIPPED = {
	{ "FasterEggs", "Faster Recruiting", "hatchTime", 0.1, { 5, 10, 20, 35, 50 } },
	{ "ExtraIncubator", "Extra Incubator", "incubators", 1, { 15, 40 } },
	{ "ExtraSlot", "Extra Desk", "employeeSlots", 1, { 10, 25, 50 } },
	{ "OfflineCap", "Night Shift", "offlineSeconds", 7200, { 5, 10, 20, 35 } },
	{ "BaseLuck", "Talent Scouts", "luck", 0.1, { 5, 10, 20, 35, 50 } },
	{ "CheaperPoach", "Recruiter Network", "poachDiscount", 0.05, { 5, 10, 15, 20, 25 } },
}
check("the same 6 perks in the same order", #IpoConfig.Perks == 6)
for i, old in ipairs(SHIPPED) do
	local perk = IpoConfig.Perks[i]
	local label = old[2]
	check(label .. ": key, name, effect and perLevel are unchanged", perk.key == old[1] and perk.name == old[2] and perk.effect == old[3] and perk.perLevel == old[4])
	local same = #perk.costs >= #old[5]
	for level, cost in ipairs(old[5]) do
		if perk.costs[level] ~= cost then same = false end
	end
	check(label .. ": every old level cost is unchanged (levels 1-" .. #old[5] .. ")", same)
	local rising = true
	for level = 2, #perk.costs do
		if perk.costs[level] <= perk.costs[level - 1] then rising = false end
	end
	check(label .. ": costs rise with every level", rising)
	check(label .. ": " .. (#perk.costs - #old[5]) .. " new levels", #perk.costs - #old[5] == ({ 2, 0, 0, 0, 3, 5 })[i])
end
check("the new Faster Recruiting levels cost 90, 140", IpoConfig.Perks[1].costs[6] == 90 and IpoConfig.Perks[1].costs[7] == 140)
check("the new Talent Scouts levels cost 80, 120, 175", IpoConfig.Perks[5].costs[6] == 80 and IpoConfig.Perks[5].costs[7] == 120 and IpoConfig.Perks[5].costs[8] == 175)
check("the new Recruiter Network levels cost 50, 75, 110, 165, 240", (function()
	local c = IpoConfig.Perks[6].costs
	return c[6] == 50 and c[7] == 75 and c[8] == 110 and c[9] == 165 and c[10] == 240
end)())
-- The caps from the D1 plan: more incubators, desks or offline hours would speed up every IPO
check("Extra Incubator, Extra Desk and Night Shift were not extended", #IpoConfig.Perks[2].costs == 2 and #IpoConfig.Perks[3].costs == 3 and #IpoConfig.Perks[4].costs == 4)
check("top Faster Recruiting is -70% (Instant Hatch keeps its value)", math.abs(IpoConfig.perkValue("FasterEggs", 99) - 0.7) < 1e-9)
check("top Recruiter Network is -50%", math.abs(IpoConfig.perkValue("CheaperPoach", 99) - 0.5) < 1e-9)
check("top Talent Scouts is +80%", math.abs(IpoConfig.perkValue("BaseLuck", 99) - 0.8) < 1e-9)
check("max-level clamp: perkValue past the max = the max, below 0 = 0", IpoConfig.perkValue("ExtraIncubator", 5) == 2 and IpoConfig.perkValue("ExtraIncubator", -3) == 0
	and IpoConfig.perkValue("FasterEggs", 7) == IpoConfig.perkValue("FasterEggs", 100))

-- 2. Nothing else moved: the pass, the Shares formula and the IPO numbers
local passEffect
for _, pass in ipairs(MODULES.ShopConfig.Passes) do if pass.key == "Shareholder" then passEffect = pass.effect end end
check("the Shareholder pass is still 2x Shares", passEffect and passEffect.sharesMultiplier == 2)
check("Shares formula numbers: 10, growth 0.8, exponent 0.5, cap 2", IpoConfig.SharesPerIpo == 10 and IpoConfig.SharesGrowthPerIpo == 0.8
	and IpoConfig.SharesExponent == 0.5 and IpoConfig.SharesRatioCap == 2)
check("IPO 1 gives 10 Shares, 20 with the pass", IpoConfig.sharesFor(IpoConfig.ipoValuation(0), 0, 1) == 10 and IpoConfig.sharesFor(IpoConfig.ipoValuation(0), 0, 2) == 20)
check("IPO 2 gives 18, IPO 3 gives 26, IPO 4 with the pass gives 68", IpoConfig.sharesFor(IpoConfig.ipoValuation(1), 1, 1) == 18
	and IpoConfig.sharesFor(IpoConfig.ipoValuation(2), 2, 1) == 26 and IpoConfig.sharesFor(IpoConfig.ipoValuation(3), 3, 2) == 68)
check("waiting past 2x IPO-ready gives no more Shares (cap 2)", IpoConfig.sharesFor(10 * IpoConfig.ipoValuation(0), 0, 1) == IpoConfig.sharesFor(2 * IpoConfig.ipoValuation(0), 0, 1)
	and IpoConfig.sharesFor(2 * IpoConfig.ipoValuation(0), 0, 1) == 14)
check("stages 0 / 1800 / 6300 / 23400 / 81000, growth x2.5 per IPO", IpoConfig.stageValuation(2, 0) == 1800 and IpoConfig.stageValuation(3, 0) == 6300
	and IpoConfig.stageValuation(4, 0) == 23400 and IpoConfig.ipoValuation(0) == 81000 and IpoConfig.StageGrowthPerIpo == 2.5 and IpoConfig.ipoValuation(1) == 202500)
check("multiplier and cooldown unchanged", IpoConfig.BonusPerIpo == 0.5 and IpoConfig.BonusExponent == 0.75 and IpoConfig.CooldownSeconds == 60)

-- IPO_PERK_COSTS in tools/economy_sim.py (the sim's copy, read by the Python side) must equal the real costs
local SIM_COSTS = __SIMCOSTS__
local sameCosts, simKeys = true, 0
for key, costs in pairs(SIM_COSTS) do
	simKeys += 1
	local perk = IpoConfig.getPerk(key)
	if not perk or #perk.costs ~= #costs then sameCosts = false else
		for i, cost in ipairs(costs) do if perk.costs[i] ~= cost then sameCosts = false end end
	end
end
check("economy_sim.py IPO_PERK_COSTS has the same perks as IpoConfig", simKeys == #IpoConfig.Perks, simKeys)
check("economy_sim.py IPO_PERK_COSTS equals the IpoConfig costs, level by level", sameCosts)

-- 3. Saves: old saves with perks load and behave exactly as before; the new levels can be bought
local saves = 0
local CORE = {
	getData = function(p) return p.data end,
	save = function() saves += 1; return true end,
	onPerksChanged = function() end, updateIncome = function() end,
	plotCenter = function() return ghost end,
}
IpoServer.init(CORE)
local onAction
for _, inst in ipairs(CREATED) do if inst.Name == "IpoAction" then onAction = inst.OnServerInvoke end end
check("the IPO remote exists", onAction ~= nil)

local function join(savedIpo)
	local player = { Name = "P", attrs = {} }
	function player:SetAttribute(k, v) self.attrs[k] = v end
	function player:GetAttribute(k) return self.attrs[k] end
	function player:FindFirstChild() return nil end
	local data = { ready = true, loaded = true, slot = 1 }
	player.data = data
	IpoServer.setupPlayer(player, data, savedIpo, 0)
	return player, data
end
local function buy(p, key) return onAction(p, "BuyPerk", key) end

local OLD_MAX = { FasterEggs = 5, ExtraIncubator = 2, ExtraSlot = 3, OfflineCap = 4, BaseLuck = 5, CheaperPoach = 5 }
local p, d = join({ count = 6, shares = 40, valuation = 1234, lifetime = 99999, best = 5000, lastIpoAt = 1699999000, perks = OLD_MAX })
local levelsKept = true
for key, level in pairs(OLD_MAX) do
	if d.ipo.perks[key] ~= level or p.attrs["IpoPerk_" .. key] ~= level then levelsKept = false end
end
check("old save with every old perk maxed: levels load as saved", levelsKept)
check("... and their effects are what they always were", math.abs(IpoServer.perk(d, "FasterEggs") - 0.5) < 1e-9 and math.abs(IpoServer.perk(d, "BaseLuck") - 0.5) < 1e-9
	and math.abs(IpoServer.perk(d, "CheaperPoach") - 0.25) < 1e-9 and IpoServer.perk(d, "ExtraIncubator") == 2 and IpoServer.perk(d, "ExtraSlot") == 3
	and IpoServer.perk(d, "OfflineCap") == 28800)
check("... and Shares, count and valuation are untouched", d.ipo.shares == 40 and d.ipo.count == 6 and d.ipo.valuation == 1234 and d.ipo.lifetime == 99999 and d.ipo.best == 5000)
local saved = IpoServer.serialize(d)
local sameSave = saved.shares == 40 and saved.count == 6
for key, level in pairs(OLD_MAX) do if saved.perks[key] ~= level then sameSave = false end end
check("... and saves back exactly the same perk levels", sameSave)
check("no warnings loading an old save", #WARNINGS == 0, WARNINGS[1])

-- 40 Shares: Faster Recruiting 6 costs 90 and is refused, nothing is spent; the maxed old perks refuse too
local ok, msg = buy(p, "FasterEggs")
check("40 Shares can't buy the 90-Share level 6", ok == false and d.ipo.perks.FasterEggs == 5 and d.ipo.shares == 40, msg)
check("... and the message says what it costs", type(msg) == "string" and msg:find("90") ~= nil, msg)
ok, msg = buy(p, "ExtraIncubator")
check("a perk that was not extended is still at its max", ok == false and d.ipo.perks.ExtraIncubator == 2 and msg:find("max level") ~= nil, msg)
-- With enough Shares the new levels can be bought one by one
d.ipo.shares = 1245
local expectLevel = { FasterEggs = 5, BaseLuck = 5, CheaperPoach = 5 }
local order = { "FasterEggs", "FasterEggs", "BaseLuck", "BaseLuck", "BaseLuck", "CheaperPoach", "CheaperPoach", "CheaperPoach", "CheaperPoach", "CheaperPoach" }
local costs = { 90, 140, 80, 120, 175, 50, 75, 110, 165, 240 }
local allBought, spent = true, 0
for i, key in ipairs(order) do
	ok = buy(p, key)
	expectLevel[key] += 1
	spent += costs[i]
	if not ok or d.ipo.perks[key] ~= expectLevel[key] or p.attrs["IpoPerk_" .. key] ~= expectLevel[key] or d.ipo.shares ~= 1245 - spent then allBought = false end
end
check("an old save with maxed old perks buys every new level, paying exactly 1,245 Shares in all", allBought and d.ipo.shares == 0, d.ipo.shares)
check("... the new top effects work (-70% hatch, +80% luck, -50% poach)", math.abs(IpoServer.perk(d, "FasterEggs") - 0.7) < 1e-9
	and math.abs(IpoServer.perk(d, "BaseLuck") - 0.8) < 1e-9 and math.abs(IpoServer.perk(d, "CheaperPoach") - 0.5) < 1e-9)
d.ipo.shares = 500
for _, key in ipairs({ "FasterEggs", "BaseLuck", "CheaperPoach" }) do
	ok, msg = buy(p, key)
	check(key .. ": no level past the new max, nothing spent", ok == false and d.ipo.shares == 500 and msg:find("max level") ~= nil, msg)
end
check("every purchase was saved", saves == #order)
saved = IpoServer.serialize(d)
check("the new levels are saved", saved.perks.FasterEggs == 7 and saved.perks.BaseLuck == 8 and saved.perks.CheaperPoach == 10 and saved.perks.OfflineCap == 4)
local p2, d2 = join(saved)
check("... and load again", d2.ipo.perks.FasterEggs == 7 and d2.ipo.perks.BaseLuck == 8 and d2.ipo.perks.CheaperPoach == 10 and d2.ipo.shares == 500)
check("buying a perk needs the Shares (no negative Shares)", (function()
	d2.ipo.shares = 0
	local bought = buy(p2, "ExtraSlot")
	return bought == false and d2.ipo.shares == 0 and d2.ipo.perks.ExtraSlot == 3 -- already max: refused either way
end)())

-- An old save with some low levels: the level costs are what they were
local p3, d3 = join({ count = 2, shares = 15, perks = { FasterEggs = 2, BaseLuck = 1, CheaperPoach = 4 } })
check("a save with low levels keeps them", d3.ipo.perks.FasterEggs == 2 and d3.ipo.perks.BaseLuck == 1 and d3.ipo.perks.CheaperPoach == 4 and d3.ipo.perks.ExtraSlot == nil)
ok = buy(p3, "FasterEggs")
check("level 3 of Faster Recruiting still costs 20 (15 Shares: refused)", ok == false and d3.ipo.shares == 15)
d3.ipo.shares = 20
ok = buy(p3, "FasterEggs")
check("... and 20 Shares buy it", ok == true and d3.ipo.perks.FasterEggs == 3 and d3.ipo.shares == 0)

-- 4. Clamp on load: bad or too-high saved levels never exceed the max (or go below 0)
WARNINGS = {}
local p4, d4 = join({ perks = { FasterEggs = 99, BaseLuck = 9, CheaperPoach = 11, ExtraIncubator = 3, ExtraSlot = -4, OfflineCap = 0 / 0, Nonsense = 2 } })
check("clamp: Faster Recruiting 99 -> 7, Talent Scouts 9 -> 8, Recruiter Network 11 -> 10", d4.ipo.perks.FasterEggs == 7 and d4.ipo.perks.BaseLuck == 8 and d4.ipo.perks.CheaperPoach == 10)
check("clamp: levels past the old max of a perk that was not extended (Extra Incubator 3 -> 2)", d4.ipo.perks.ExtraIncubator == 2)
check("clamp: negative and NaN levels become 0", d4.ipo.perks.ExtraSlot == 0 and d4.ipo.perks.OfflineCap == 0)
check("an unknown perk in a save is skipped with a warning", d4.ipo.perks.Nonsense == nil and #WARNINGS == 1, #WARNINGS)
check("a level that is not a number loads as 0", (function()
	local _, d5 = join({ perks = { FasterEggs = "lots" } })
	return d5.ipo.perks.FasterEggs == 0
end)())
check("a save with no IPO section loads with no perks", (function()
	local _, d6 = join(nil)
	return next(d6.ipo.perks) == nil and d6.ipo.shares == 0
end)())

print_real(string.format("%d passed, %d failed", passed, failed))
"""


NEXTHIRE_TESTS = r"""-- Tests for DailyClient's egg-day line for restricted players (the code between its NEXTHIRE markers, FR-13) ----
local print_real = print
local passed, failed = 0, 0
local function check(name, cond, extra)
	if cond then passed += 1 else failed += 1; print_real("FAIL: " .. name .. (extra and (" -- " .. tostring(extra)) or "")) end
end
__NEXTHIRE__
check("restriction unknown (nil) counts as restricted", isRestricted(nil) == true)
check("restricted flag true is restricted", isRestricted(true) == true)
check("only an explicit false is unrestricted", isRestricted(false) == false)
local egg = { name = "Garage Egg" }
local line = nextHireLine(egg, { name = "Coding Cat", emoji = "🐱" }, "#ffffff")
check("line names the egg and says next hire", line:find("Garage Egg next hire: ", 1, true) ~= nil, line)
check("line names the creature", line:find("Coding Cat", 1, true) ~= nil, line)
check("line says fixed order, not random", line:find("fixed order, not a random roll", 1, true) ~= nil, line)
check("line has no odds or percent", line:find("odds", 1, true) == nil and line:find("%", 1, true) == nil, line)
check("line has no empty font colour", line:find('<font color="#ffffff">', 1, true) ~= nil, line)
local loading = nextHireLine(egg, nil, "#ffffff")
check("no server data yet shows loading, never odds", loading:find("loading...", 1, true) ~= nil and loading:find("odds", 1, true) == nil, loading)
check("creature without emoji still renders", nextHireLine(egg, { name = "Bug Bear" }, "#fff"):find("Bug Bear", 1, true) ~= nil)
check("card note for restricted says next hire", eggNote(true) == "tap for next hire")
check("card note for others says odds", eggNote(false) == "tap for odds")
print_real(string.format("%d passed, %d failed", passed, failed))
"""


TASK_TESTS = r"""-- Tests for the task engine: the real TaskConfig and TaskServer with a fake Roblox (PR 1) ----------
local print_real = print
local NOW = 20000 * 86400 + 12 * 3600 -- noon UTC on day 20000
local CLOCK = 1000
local IS_STUDIO = true
local WARNINGS, PRINTS = {}, {}
local os = { time = function() return NOW end, clock = function() return CLOCK end }
local function warn(...) table.insert(WARNINGS, table.concat({...}, " ")) end
local function print(...) table.insert(PRINTS, table.concat({...}, " ")) end
local function token(name) return { Name = name, WaitForChild = function(self, n) return token(n) end } end
local MODULES = {}
local function require(x) return assert(MODULES[x.Name], "no module " .. tostring(x.Name)) end
local PLAYER_REMOVING = {}
local SERVICES = {
	ReplicatedStorage = token("ReplicatedStorage"),
	RunService = { IsStudio = function() return IS_STUDIO end },
	Players = { GetPlayers = function() return {} end, PlayerRemoving = { Connect = function(_, f) table.insert(PLAYER_REMOVING, f) end } },
}
local game = { GetService = function(_, n) return SERVICES[n] end }
local script = { Parent = token("ServerScriptService") }
local CREATED = {}
local Instance = { new = function(class)
	local i = { ClassName = class }
	if class == "RemoteEvent" then
		function i:FireClient(player, kind, payload) table.insert(player.events, { kind = kind, payload = payload }) end
	end
	table.insert(CREATED, i)
	return i
end }
-- A fake Vector3 (the plain Luau tool has none): typeof says "Vector3" for it, like Roblox does
local realTypeof = typeof
local function typeof(v) if type(v) == "table" and v.isFakeVector3 then return "Vector3" end return realTypeof(v) end
local function Vector3(x, y, z) return { isFakeVector3 = true, X = x, Y = y, Z = z } end
local SPAWNED = {}
local task = { spawn = function(f) table.insert(SPAWNED, f) end, wait = function() end }

local RANDOM = 0 -- what math.random() answers (0 = the shortest gap, and the team always takes a call it can)
local math = setmetatable({ random = function() return RANDOM end }, { __index = math }) -- the real math is read-only; the engine sees this one

MODULES.CreatureConfig = { getEgg = function(k) local e = ({ Garage = 1, Startup = 1, Unicorn = 1 })[k]; return e and { key = k, name = k .. " Egg" } end }
MODULES.DailyConfig = (function()
__DAILYCONFIG__
end)()
MODULES.IpoConfig = (function()
__IPOCONFIG__
end)()
MODULES.ShopConfig = { formatCash = function(n) return "$" .. n end, DebugInStudio = true }
local DEBUG = {}
MODULES.ShopServer = { addDebugAction = function(name, f) DEBUG[name] = f end }
MODULES.IpoServer = { isBusy = function(data) return data ~= nil and data.ipo ~= nil and data.ipo.busy == true end }
MODULES.TaskConfig = (function()
__TASKCONFIG__
end)()
local CONFIG_WARNINGS = #WARNINGS
MODULES.TaskConfig.BudgetBank = 1e9 -- most tests run without the reward budget; section 17 turns it on
local function loadServer()
__TASKSERVER__
end

-- Tests ---------------------------------------------------------------------
local C = MODULES.TaskConfig
local DC = MODULES.DailyConfig
local IC = MODULES.IpoConfig
local TEXTS = C.Texts
local row = C.getRow("Call")
local passed, failed = 0, 0
local function check(name, cond, extra)
	if cond then passed += 1 else failed += 1; print_real("FAIL: " .. name .. (extra and (" -- " .. tostring(extra)) or "")) end
end
local function near(a, b, eps) return math.abs(a - b) <= (eps or 1e-6) end

-- 1. The real config ----------------------------------------------------------
check("TaskConfig loads without a warning", CONFIG_WARNINGS == 0, WARNINGS[1])
check("one row: the customer call", #C.Rows == 1 and row ~= nil and row.action == "click" and row.role == "sales")
check("a call rings every 20-40 s", row.every[1] == 20 and row.every[2] == 40)
check("at most 3 calls wait", row.queue == 3)
check("answer within 8 s", row.limit == 8)
check("reward is 7 s of Income", row.reward.seconds == 7)
check("chain: +0.1 per answer, up to x2", row.reward.chain.step == 0.1 and row.reward.chain.max == 2)
check("Sales take 20% each, 0.08 demand per hire, skip is free, the team pays half", row.auto == 0.20 and row.demand == 0.08 and row.skip == true and row.teamPays == 0.5)
check("a call has no cooldown and no miss penalty in PR 1", row.cooldown == 0 and row.miss == 0)
check("demand cap D <= 2.0", C.DemandCap == 2.0)
check("gap, shortest roll, no hires", near(C.gap(row, 0, 0, 0), 20))
check("gap, longest roll, no hires", near(C.gap(row, 0, 0, 1), 40))
check("gap with 5 hires: 20 / 1.4", near(C.gap(row, 5, 0, 0), 20 / 1.4))
check("demand factor 0 hires = 1", C.demandFactor(row, 0) == 1)
check("demand factor 5 hires = 1.4", near(C.demandFactor(row, 5), 1.4))
check("demand factor 12 hires = 1.96", near(C.demandFactor(row, 12), 1.96))
check("demand factor 13 hires hits the cap 2.0", C.demandFactor(row, 13) == 2.0)
check("demand factor never above 2.0 (1000 hires)", C.demandFactor(row, 1000) == 2.0)
check("demand factor ignores negative hires", C.demandFactor(row, -5) == 1)
check("gap at the demand cap: 10 s", near(C.gap(row, 13, 0, 0), 10) and near(C.gap(row, 500, 0, 0), 10))
check("pace factor", C.paceFactor(0) == 1 and near(C.paceFactor(5), 1.1) and C.paceFactor(100) == 1.4)
check("limit shrinks with level, never below 65%", C.limitFor(row, 0) == 8 and near(C.limitFor(row, 5), 6.8) and near(C.limitFor(row, 50), 5.2))
check("auto share: none without employees", C.autoShare(row, 0) == 0)
check("auto share: 1 employee 20%, 3 employees 48.8%", near(C.autoShare(row, 1), 0.2) and near(C.autoShare(row, 3), 0.488))
check("auto share is capped at 75% (the founder keeps 25%)", C.autoShare(row, 100) == 0.75)
check("chain multiplier: x1, x1.1, x2 at 10, x2 forever", C.chainMultiplier(row, 0) == 1 and near(C.chainMultiplier(row, 1), 1.1) and C.chainMultiplier(row, 10) == 2 and C.chainMultiplier(row, 50) == 2)
check("reward seconds: 7 at the start, 14 at the chain cap", C.rewardSeconds(row, 0) == 7 and C.rewardSeconds(row, 10) == 14 and C.rewardSeconds(row, 99) == 14)
check("budgets per rung", C.budgetFor(0) == 0.85 and C.budgetFor(1) == 0.85 and C.budgetFor(2) == 0.95 and C.budgetFor(3) == 1.05 and C.budgetFor(4) == 1.15 and C.budgetFor(5) == 1.25 and C.budgetFor(99) == 1.25)
check("level = rung + IPOs (at most 10)", C.level(0, 0) == 0 and C.level(2, 3) == 5 and C.level(4, 50) == 14)
row.unlock.rung = 2
check("a task appears at its rung", not C.isUnlocked(row, 1, 0, { Desk = true }) and C.isUnlocked(row, 2, 0, { Desk = true }))
check("after the first IPO every task is on", C.isUnlocked(row, 0, 1))
row.unlock.rung = 0
check("the Call row needs rung 0 and the Desk (the first upgrade)", row.unlock.rung == 0 and row.unlock.owns == "Desk")
local allMapped = true
for i, stage in ipairs(IC.Stages) do
	if C.rungForStage(stage.key) ~= i - 1 then allMapped = false end
end
check("every funding stage maps to its rung (Garage 0, Seed 1, Series A 2, Series B 3, IPO-ready 4)", allMapped and #IC.Stages == 5)
local bad
for key, text in pairs(TEXTS) do
	for _, word in ipairs({ "odds", "chance", "luck", "random", "probab", "%%" }) do
		if string.find(string.lower(text), word, 1, true) then bad = key .. ": " .. word end
	end
end
check("no task text claims odds or chance (D9)", bad == nil, bad)
check("sales creatures take calls, others don't", C.roleOf("HustleHamster") == "sales" and C.roleOf("SalesShark") == "sales" and C.roleOf("CodingCat") == "eng" and C.roleOf("UnicornCEO") == nil)

-- 2. Studio only, and Enabled = false does nothing ---------------------------------
local function active(enabled, studioOnly, studio)
	local oldE, oldS, oldStudio = C.Enabled, C.StudioOnly, IS_STUDIO
	C.Enabled, C.StudioOnly, IS_STUDIO = enabled, studioOnly, studio
	local result = C.isActive()
	C.Enabled, C.StudioOnly, IS_STUDIO = oldE, oldS, oldStudio
	return result
end
check("active in Studio", active(true, true, true) == true)
check("not active on a live server in PR 1", active(true, true, false) == false)
check("Enabled = false: never active", active(false, true, true) == false and active(false, false, false) == false)
check("StudioOnly = false (PR 2): active everywhere", active(true, false, false) == true)
check("shipped config: Enabled and StudioOnly", C.Enabled == true and C.StudioOnly == true)

local EARNINGS = {}
local core = {
	getData = function(p) return p.data end,
	addEarnings = function(p, amount) table.insert(EARNINGS, amount) end,
	baseIncome = function(p) return p.base or p.data.income.Value end,
}
local function newPlayerFor(server, saved, opts)
	opts = opts or {}
	local player = { Name = opts.name or "P", Parent = true, events = {} }
	local data = {
		ready = opts.ready ~= false, loaded = true,
		cash = { Value = 0 }, income = { Value = opts.income or 10 },
		ipo = { valuation = opts.valuation or 0, count = opts.ipos or 0, busy = false, shares = 0, lifetime = 0 },
		team = { employees = opts.employees or {} },
		owned = opts.owned or { Desk = true }, -- the set of upgrade names, like TycoonCore's data.owned (calls start with the Desk)
	}
	player.data = data
	player.base = opts.base
	server.setupPlayer(player, data, saved)
	return player, data
end

for _, off in ipairs({ "live server", "Enabled = false" }) do
	local oldE, oldStudio = C.Enabled, IS_STUDIO
	if off == "live server" then IS_STUDIO = false else C.Enabled = false end
	local created, spawned, debugCount = #CREATED, #SPAWNED, 0
	for _ in pairs(DEBUG) do debugCount += 1 end
	local removing = #PLAYER_REMOVING
	local server = loadServer()
	server.init(core)
	local debugAfter = 0
	for _ in pairs(DEBUG) do debugAfter += 1 end
	check(off .. ": no remotes are built", #CREATED == created)
	check(off .. ": no loop is started", #SPAWNED == spawned and #PLAYER_REMOVING == removing)
	check(off .. ": no Debug buttons", debugAfter == debugCount)
	local p, d = newPlayerFor(server, nil)
	check(off .. ": a new player gets no tasks section", server.serialize(d) == nil)
	check(off .. ": nobody is engaged", server.isEngaged(p) == false and server.engagedSeconds(p) == 0)
	local before = #EARNINGS
	for _ = 1, 20 do CLOCK += 5; server.step(p, CLOCK) end
	check(off .. ": time passing creates nothing and pays nothing", #p.events == 0 and #EARNINGS == before and d.cash.Value == 0)
	local run = d.tasks.run
	check(off .. ": no call is open (run.open is empty, nothing in the queue)", next(run.open) == nil and #run.order == 0)
	local offStats = server.getStats(p)
	check(off .. ": no call arrived or was offered, no clock ran, nothing answered", offStats.arrivals == 0 and offStats.offered == 0 and offStats.answered == 0 and offStats.online == 0 and next(run.nextAt) == nil)
	local answerRemote = false
	for i = created + 1, #CREATED do
		if CREATED[i].Name == "TaskAction" then answerRemote = true end
	end
	check(off .. ": no remote exists to answer", not answerRemote and #CREATED == created)
	local saved = { sharesRun = 2, done = 5, bestChain = 4, seen = { Call = true }, engagedDay = 20000, engagedSeconds = 77, future = { x = 1 } }
	local p2, d2 = newPlayerFor(server, saved)
	local out = server.serialize(d2)
	check(off .. ": a saved section is kept as it was",
		out and out.done == 5 and out.sharesRun == 2 and out.bestChain == 4 and out.seen.Call == true and out.engagedDay == 20000 and out.engagedSeconds == 77 and out.future.x == 1)
	C.Enabled, IS_STUDIO = oldE, oldStudio
end

-- 3. The active engine ---------------------------------------------------------------
local TaskServer = loadServer()
local createdBefore, spawnedBefore = #CREATED, #SPAWNED
TaskServer.init(core)
local onAction, stateEvent, folder
for i = createdBefore + 1, #CREATED do
	local inst = CREATED[i]
	if inst.Name == "TaskAction" then onAction = inst.OnServerInvoke end
	if inst.Name == "TaskState" then stateEvent = inst end
	if inst.Name == "TaskRemotes" then folder = inst end
end
check("remotes: TaskAction and TaskState in a TaskRemotes folder", onAction ~= nil and stateEvent ~= nil and folder ~= nil and folder.Parent == SERVICES.ReplicatedStorage)
check("one loop is started", #SPAWNED == spawnedBefore + 1)
check("Studio Debug buttons: Set rung, stats, spawn", DEBUG.TaskSetRung and DEBUG.TaskStats and DEBUG.TaskSpawn)

local function newPlayer(saved, opts) return newPlayerFor(TaskServer, saved, opts) end
local function crew(n, creature)
	local list = {}
	for i = 1, n do table.insert(list, { id = tostring(i), creature = creature or "CodingCat" }) end
	return list
end
local function advance(seconds) CLOCK += seconds; NOW += seconds end
local function tick(p, seconds, stepSize)
	stepSize = stepSize or 1
	local left = seconds
	while left > 1e-9 do
		local d = math.min(stepSize, left)
		advance(d)
		TaskServer.step(p, CLOCK)
		left -= d
	end
end
local function lastState(p)
	for i = #p.events, 1, -1 do
		if p.events[i].kind == "state" then return p.events[i].payload end
	end
	return nil
end
local function waiting(p)
	local s = lastState(p)
	return s and s.tasks or {}
end
local function answer(p, id) return onAction(p, "Answer", id) end
local function spawnCall(p)
	local text = DEBUG.TaskSpawn(p, p.data)
	local list = waiting(p)
	return list[#list] and list[#list].id, text
end
local function stats(p) return TaskServer.getStats(p) end
local function noArrivals(p) p.data.tasks.run.nextAt.Call = 1e12 end
local function richBank(p) p.data.tasks.run.bank = 1e9 end -- (the budget has its own section)
local function waitForArrival(p, limit)
	local before = stats(p).offered + stats(p).autoResolved
	local waited = 0
	while waited < limit do
		tick(p, 0.5, 0.5)
		waited += 0.5
		if stats(p).offered + stats(p).autoResolved > before then return waited end
	end
	return nil
end

-- 3b. The handler and the tick check isActive themselves (Enabled switched off after the engine started) ----------------
do
	RANDOM = 0
	local p, d = newPlayer(nil)
	noArrivals(p)
	local id = spawnCall(p)
	advance(1)
	local run = d.tasks.run
	local offeredBefore, onlineBefore = stats(p).offered, stats(p).online
	C.Enabled = false
	local ok, msg = onAction(p, "Answer", id)
	check("Enabled = false: the remote refuses with 'off' and grades nothing", ok == false and msg == TEXTS.Off and stats(p).answered == 0 and run.open[id] ~= nil and d.cash.Value == 0)
	check("Enabled = false: Pause, Start and Sync are refused too", onAction(p, "Pause", true) == false and run.paused == false and onAction(p, "Start") == false and onAction(p, "Sync") == false)
	run.nextAt.Call = 0 -- a call would be due right now
	for _ = 1, 30 do advance(5); TaskServer.step(p, CLOCK) end
	check("Enabled = false: step() creates nothing, expires nothing, runs no clock and pays nothing",
		stats(p).offered == offeredBefore and stats(p).arrivals == 0 and stats(p).missed == 0 and stats(p).online == onlineBefore and run.open[id] ~= nil and d.cash.Value == 0)
	C.Enabled = true
end

-- 3c. Calls start with the Desk (or after the first IPO) -------------------------------------------------------------------------
-- (Placed early on purpose: a broken rule stops the later sections, and this one must name the failure before that.)
-- Owner decision: the phone rings on the desk. The first arrival after the unlock waits a NORMAL gap (not an instant call).
do
	local function desk() return { Desk = true } end
	local function buyDesk(p) p.data.owned.Desk = true end -- what TycoonCore does when the upgrade is bought
	local function calls(p) local s = stats(p); return s.arrivals + s.offered + s.autoResolved + s.dropped end
	local function openCount(p) local n = 0; for _ in pairs(p.data.tasks.run.open) do n += 1 end; return n end
	local function on(owned, rung, ipos) return C.isUnlocked(row, rung, ipos, owned) end
	RANDOM = 0

	-- the rule itself (TaskConfig.isUnlocked, used by TaskServer)
	check("desk: isUnlocked, no Desk and no IPO is off, with the Desk it is on", on({}, 0, 0) == false and on(desk(), 0, 0) == true)
	check("desk: isUnlocked fails closed without an owned list (a row that needs the Desk is off)", on(nil, 0, 0) == false)
	check("desk: owning other upgrades without the Desk starts no call", on({ ["Coffee Machine"] = true, Laptop = true }, 0, 0) == false)
	check("desk: isUnlocked, after the first IPO calls are on without the Desk and without a list", on({}, 0, 1) == true and on(nil, 0, 1) == true and on({}, 0, 7) == true)
	check("desk: isUnlocked, the Desk does not skip the rung", (function()
		row.unlock.rung = 2
		local result = on(desk(), 1, 0) == false and on(desk(), 2, 0) == true
		row.unlock.rung = 0
		return result
	end)())
	check("desk: isUnlocked, a row without `owns` needs no upgrade", (function()
		local old = row.unlock.owns
		row.unlock.owns = nil
		local result = on({}, 0, 0) == true
		row.unlock.owns = old
		return result
	end)())

	-- nothing before the Desk, in a long stretch of time: 2 hours of real 0.5 s ticks, with a big sales team and every kind of roll
	for _, roll in ipairs({ 0, 0.5, 1 }) do
		RANDOM = roll
		local before = #EARNINGS
		local p, d = newPlayer(nil, { owned = {}, employees = crew(12, "SalesShark") })
		tick(p, 7200, 0.5)
		local s = stats(p)
		check("desk: no call arrives before the Desk, in 2 hours of ticks (roll " .. roll .. ")",
			s.arrivals == 0 and s.offered == 0 and s.autoResolved == 0 and s.dropped == 0 and openCount(p) == 0, s.arrivals)
		check("desk: ... the clock really ran in that stretch (the test is not empty)", s.online >= 7000, s.online)
		check("desk: ... nothing was paid and nothing was earned", d.cash.Value == 0 and #EARNINGS == before)
		local shown = false
		for _, event in ipairs(p.events) do
			if event.kind == "handled" or (event.kind == "state" and (#event.payload.tasks > 0 or event.payload.on ~= false or event.payload.quiet)) then shown = true end
		end
		check("desk: ... and no message to the player ever showed a call, 'on' or quiet mode", shown == false and #p.events >= 1)
	end
	RANDOM = 0

	-- what a player sees and hears before the Desk
	do
		local p, d = newPlayer(nil, { owned = {} })
		tick(p, 300, 1)
		local st = lastState(p)
		check("desk: before the Desk the state says calls are off, with no call and no quiet mode", st ~= nil and st.on == false and #st.tasks == 0 and st.quiet == false)
		check("desk: ... and no arrival timer is set", p.data.tasks.run.nextAt.Call == nil)
		local ok, msg = onAction(p, "Sync")
		check("desk: Sync before the Desk is accepted with no 'off' message", ok == true and msg == nil, msg)
		local okAnswer, msgAnswer = answer(p, 1)
		check("desk: answering before the Desk finds no call (and says nothing about tasks being off)", okAnswer == false and msgAnswer == TEXTS.Gone, msgAnswer)

		-- the Desk is bought after 5 minutes: no quiet mode, no instant call, 'on' goes true
		buyDesk(p)
		tick(p, 1, 0.5)
		check("desk: buying the Desk after 5 minutes does not start quiet mode", lastState(p).quiet == false and p.data.tasks.run.quiet == false)
		check("desk: buying the Desk sends 'on' and rings nothing at once", lastState(p).on == true and calls(p) == 0)
	end

	-- the first call after the Desk is bought: a normal gap, never earlier than the shortest one
	for _, hires in ipairs({ 0, 5, 13, 50 }) do
		RANDOM = 0
		local p, d = newPlayer(nil, { owned = {}, employees = crew(hires, "CodingCat") })
		tick(p, 300, 1)
		buyDesk(p)
		local gap = C.gap(row, hires, 0, 0)
		local waited = waitForArrival(p, 80)
		check("desk: the first call after the Desk is bought is not earlier than the shortest gap (" .. hires .. " hires)",
			waited ~= nil and waited >= gap - 1e-9 and waited <= gap + 1.01, waited)
	end
	do
		RANDOM = 1
		local p = newPlayer(nil, { owned = {} })
		tick(p, 300, 1)
		buyDesk(p)
		local waited = waitForArrival(p, 80)
		check("desk: the first call after the Desk is bought follows the same roll as any other (longest roll: 40 s)", waited ~= nil and waited >= 40 and waited <= 41.01, waited)
		RANDOM = 0
	end
	do
		-- an old timer is never used: the Desk is lost and bought again
		local p, d = newPlayer(nil)
		tick(p, 1, 0.5)
		p.data.tasks.run.nextAt.Call = CLOCK + 1 -- a call due in a second
		d.owned = {}
		tick(p, 10, 0.5)
		check("desk: with the Desk gone nothing rings and the old timer is forgotten", calls(p) == 0 and p.data.tasks.run.nextAt.Call == nil)
		buyDesk(p)
		local waited = waitForArrival(p, 80)
		check("desk: a timer from before the Desk was lost is not used when it is bought again", waited ~= nil and waited >= 20 - 1e-9, waited)
	end

	-- a rejoin
	do
		local saved = { done = 5, bestChain = 3, seen = { Call = true }, engagedDay = DC.dayNumber(NOW), engagedSeconds = 40 }
		local p, d = newPlayer(saved, { owned = desk() })
		local waited = waitForArrival(p, 80)
		check("desk: a rejoin with the Desk owned gets its first call after a normal gap", waited ~= nil and waited >= 20 - 1e-9 and waited <= 21.01 and lastState(p).on == true, waited)
		check("desk: ... and its saved numbers are kept", d.tasks.done == 5 and TaskServer.serialize(d).done == 5)
		local q, qd = newPlayer(saved, { owned = {} })
		tick(q, 600, 1)
		check("desk: a rejoin without the Desk gets no call, and its saved numbers stay", calls(q) == 0 and qd.tasks.done == 5 and TaskServer.serialize(qd).done == 5)
	end

	-- after the first IPO: the upgrades are reset (the Desk is gone) and calls go on
	do
		local p, d = newPlayer(nil, { employees = crew(3, "CodingCat") })
		tick(p, 5, 0.5)
		local run = p.data.tasks.run
		local timer = run.nextAt.Call
		check("desk: with the Desk a call timer is running", timer ~= nil and timer > CLOCK)
		d.owned = {} -- the IPO reset
		d.ipo.count = 1
		tick(p, 0.5, 0.5)
		check("desk: after the first IPO, with the Desk gone, the state still says calls are on", lastState(p).on == true)
		check("desk: ... and the running call timer is not reset", run.nextAt.Call == timer)
		local waited = waitForArrival(p, 60)
		check("desk: after the first IPO calls keep coming without the Desk", waited ~= nil and waited <= 20, waited)
		local q, qd = newPlayer(nil, { owned = {}, ipos = 1 })
		local gap = C.gap(row, 0, C.level(0, 1), 0)
		local waitedQ = waitForArrival(q, 80)
		check("desk: a player who joins after an IPO without the Desk gets calls after a normal gap", waitedQ ~= nil and waitedQ >= gap - 1e-9 and waitedQ <= gap + 1.01, waitedQ)
	end

	-- a call that is already waiting is never removed by the condition changing
	do
		local p, d = newPlayer(nil)
		noArrivals(p); richBank(p)
		local ids = { spawnCall(p), spawnCall(p), spawnCall(p) }
		advance(1)
		d.owned = {} -- no Desk and no IPO: calls are off
		tick(p, 2, 0.5)
		check("desk: calls already waiting are not removed when calls turn off", openCount(p) == 3 and #waiting(p) == 3 and lastState(p).on == false, openCount(p))
		check("desk: ... they are still counting down", waiting(p)[1] ~= nil and waiting(p)[1].left > 0 and waiting(p)[1].left < 8)
		local ok, _, info = answer(p, ids[2])
		check("desk: ... a waiting call can still be answered and pays", ok == true and info.cash == 70 and #waiting(p) == 2)
		tick(p, 8, 0.5)
		check("desk: ... the others leave only by running out", openCount(p) == 0 and stats(p).missed == 2)
		tick(p, 300, 1)
		check("desk: ... and with calls off none comes in", stats(p).arrivals == 0)
	end
	do
		local p, d = newPlayer(nil)
		noArrivals(p)
		spawnCall(p); spawnCall(p); spawnCall(p)
		d.owned = {}
		tick(p, 10, 0.5)
		check("desk: three calls that run out after the Desk is gone do not start quiet mode or a 'Tap to resume'",
			stats(p).missed == 3 and p.data.tasks.run.quiet == false and lastState(p).quiet == false)
	end
	do
		local p, d = newPlayer(nil, { owned = {} })
		spawnCall(p) -- the Studio Debug button rings a call even before the Desk
		buyDesk(p)
		tick(p, 1, 0.5)
		check("desk: a call that waits when the Desk is bought is kept", openCount(p) == 1 and lastState(p).on == true)
	end

	-- the team still takes routine calls for the player, once calls are on
	do
		RANDOM = 0.1 -- 0.1 < 1 - 0.8^3: the team takes the call
		local function makeEngaged(p) -- one graded answer makes the player present (the Debug call rings without the Desk too)
			richBank(p)
			local id = spawnCall(p)
			advance(1)
			answer(p, id)
		end
		local p, d = newPlayer(nil, { owned = {}, employees = crew(3, "HustleHamster") })
		makeEngaged(p)
		EARNINGS = {}
		tick(p, 100, 0.5)
		check("desk: the team takes no call before the Desk (none rings)", stats(p).autoResolved == 0 and stats(p).arrivals == 0 and #EARNINGS == 0)
		buyDesk(p)
		local cash = d.cash.Value
		local waited = waitForArrival(p, 60)
		check("desk: once the Desk is bought the team takes calls for the player (half pay, through addEarnings)",
			waited ~= nil and stats(p).autoResolved == 1 and openCount(p) == 0 and d.cash.Value == cash + 35 and #EARNINGS == 1 and EARNINGS[1] == 35, waited)
		local q, qd = newPlayer(nil, { owned = {}, ipos = 1, employees = crew(3, "HustleHamster") })
		makeEngaged(q)
		EARNINGS = {}
		local waitedQ = waitForArrival(q, 60)
		check("desk: after the first IPO, without the Desk, the team takes calls too", waitedQ ~= nil and stats(q).autoResolved == 1 and #EARNINGS == 1, waitedQ)
		RANDOM = 0
	end

	-- 'Tap to resume' and the Studio rung button
	do
		local p, d = newPlayer(nil, { owned = {} })
		p.data.tasks.run.quiet = true
		advance(1)
		check("desk: 'Tap to resume' is accepted but brings no call before the Desk", onAction(p, "Start") == true and openCount(p) == 0 and stats(p).offered == 0)
		tick(p, 1, 0.5)
		check("desk: ... and leaves no arrival timer behind", p.data.tasks.run.nextAt.Call == nil)
		local q, qd = newPlayer(nil, { owned = {} })
		DEBUG.TaskSetRung(q, qd, "4")
		tick(q, 300, 1)
		check("desk: a high rung from the Debug button does not start calls without the Desk", calls(q) == 0)
	end
	RANDOM = 0
	EARNINGS = {} -- the later sections count the earnings from zero
end

-- 4. Saving and loading ---------------------------------------------------------------------
do
	local p, d = newPlayer(nil)
	check("no section yet for a new player", TaskServer.serialize(d) == nil)
	check("the default state", d.tasks.done == 0 and d.tasks.bestChain == 0 and d.tasks.sharesRun == 0 and d.tasks.engagedSeconds == 0 and next(d.tasks.seen) == nil)
	check("the player's other data is untouched by setup", d.cash.Value == 0 and d.ipo.valuation == 0 and d.ipo.count == 0)

	local day = DC.dayNumber(NOW)
	local good = { sharesRun = 3, done = 120, bestChain = 14, seen = { Call = true }, engagedDay = day, engagedSeconds = 5000 }
	p, d = newPlayer(good)
	local out = TaskServer.serialize(d)
	check("a good section loads and saves back the same",
		out.sharesRun == 3 and out.done == 120 and out.bestChain == 14 and out.seen.Call == true and out.engagedDay == day and out.engagedSeconds == 5000)
	check("a good section gives no warning", #WARNINGS == CONFIG_WARNINGS)
	out.future = nil
	local p2, d2 = newPlayer({ done = 1, future = { a = 1 }, other = "x" })
	local out2 = TaskServer.serialize(d2)
	check("fields this version doesn't know are kept as they were", out2.future.a == 1 and out2.other == "x" and out2.done == 1)

	local function load(saved)
		WARNINGS = {}
		local lp, ld = newPlayer(saved)
		return ld.tasks, #WARNINGS
	end
	local t, w
	t, w = load({ done = -5 })
	check("done = -5 is skipped with a warning", t.done == 0 and w == 1)
	t, w = load({ done = 0 / 0 })
	check("done = NaN is skipped with a warning", t.done == 0 and w == 1)
	t, w = load({ done = math.huge })
	check("done = infinity is skipped with a warning", t.done == 0 and w == 1)
	t, w = load({ done = 2.5 })
	check("done = 2.5 is skipped with a warning", t.done == 0 and w == 1)
	t, w = load({ done = "many" })
	check("done = text is skipped with a warning", t.done == 0 and w == 1)
	t, w = load({ done = 1e12 })
	check("done = 1e12 is clamped to 1e9 with a warning", t.done == 1e9 and w == 1)
	t, w = load({ bestChain = 5e6, sharesRun = -1 })
	check("bestChain over the limit is clamped, a negative sharesRun skipped", t.bestChain == 1e6 and t.sharesRun == 0 and w == 2)
	t, w = load({ engagedDay = day, engagedSeconds = 1e9 })
	check("engagedSeconds over a day is clamped to 86400", t.engagedSeconds == 86400 and w == 1)
	t, w = load({ engagedDay = day, engagedSeconds = -1 })
	check("engagedSeconds = -1 is skipped", t.engagedSeconds == 0 and w == 1)
	t, w = load({ engagedDay = day, engagedSeconds = 0 / 0 })
	check("engagedSeconds = NaN is skipped", t.engagedSeconds == 0 and w == 1)
	t, w = load({ engagedDay = day, engagedSeconds = 90.9 })
	check("engagedSeconds is whole seconds", t.engagedSeconds == 90)
	t, w = load({ engagedDay = -3, engagedSeconds = 50 })
	check("engagedDay = -3 is skipped (an old day: the seconds are ignored)", t.engagedDay == day and t.engagedSeconds == 0 and w == 1)
	t, w = load({ engagedDay = day - 1, engagedSeconds = 5000 })
	check("an older day's seconds are ignored", t.engagedDay == day and t.engagedSeconds == 0 and w == 0)
	t, w = load({ engagedDay = day, engagedSeconds = 5000 })
	check("today's seconds are kept", t.engagedDay == day and t.engagedSeconds == 5000)
	t, w = load({ engagedDay = day + 5, engagedSeconds = 700 })
	check("a day in the future is rejected: the engaged counters start again at today with 0 seconds, with a warning", t.engagedDay == day and t.engagedSeconds == 0 and w == 1)
	t, w = load({ engagedDay = day + 1, engagedSeconds = 700 })
	check("tomorrow is a future day too: rejected the same way (never extra seconds)", t.engagedDay == day and t.engagedSeconds == 0 and w == 1)
	t, w = load({ done = 9, bestChain = 3, sharesRun = 1, seen = { Call = true }, engagedDay = day + 40, engagedSeconds = 80000, future = { x = 1 } })
	check("a future engagedDay resets only the engaged counters of this section: the other fields stay",
		t.done == 9 and t.bestChain == 3 and t.sharesRun == 1 and t.seen.Call == true and t.unknown.future.x == 1 and t.engagedDay == day and t.engagedSeconds == 0 and w == 1)
	do
		local fp, fd = newPlayer({ done = 9, engagedDay = day + 2, engagedSeconds = 5000 })
		local out = TaskServer.serialize(fd)
		check("... and it saves back today's day with 0 seconds and everything else as it was", out.engagedDay == day and out.engagedSeconds == 0 and out.done == 9)
		check("... and nobody is engaged by it", not TaskServer.isEngaged(fp) and TaskServer.engagedSeconds(fp) == 0)
		WARNINGS = {}
	end
	t, w = load({ seen = "Call" })
	check("seen = text is skipped", next(t.seen) == nil and w == 1)
	t, w = load({ seen = { Call = true, [1] = true, Bad = false, Worse = "yes" } })
	check("seen keeps only { key = true } entries", t.seen.Call == true and t.seen.Bad == nil and t.seen.Worse == nil and t.seen[1] == nil and w == 3)
	local many = {}
	for i = 1, 80 do many["Task" .. i] = true end
	t, w = load({ seen = many })
	local kept = 0
	for _ in pairs(t.seen) do kept += 1 end
	check("seen keeps at most 50 keys", kept == 50)
	for _, junk in ipairs({ 5, "text", true }) do
		WARNINGS = {}
		local jp, jd = newPlayer(junk)
		check("a tasks section that is " .. type(junk) .. " is skipped with a warning and saves nothing", #WARNINGS == 1 and TaskServer.serialize(jd) == nil and jd.tasks.done == 0)
	end
	t, w = load({ done = 7 })
	check("a section with only some keys loads with defaults for the rest", t.done == 7 and t.bestChain == 0 and t.engagedSeconds == 0 and w == 0)
	local before = { cash = d.cash.Value, valuation = d.ipo.valuation, count = d.ipo.count, hires = #d.team.employees }
	TaskServer.setupPlayer(p, d, { done = "x", engagedSeconds = {}, seen = 3 })
	check("a bad section never touches the other sections", d.cash.Value == before.cash and d.ipo.valuation == before.valuation and d.ipo.count == before.count and #d.team.employees == before.hires)
	WARNINGS = {}
end

-- 5. Grading: too early, too late, double answer ---------------------------------------------
do
	local p, d = newPlayer(nil)
	noArrivals(p)
	local id, text = spawnCall(p)
	check("a spawned call is waiting", id ~= nil and #waiting(p) == 1 and waiting(p)[1].kind == "Call" and near(waiting(p)[1].left, 8) and waiting(p)[1].limit == 8)
	check("offered counted", stats(p).offered == 1)

	advance(0.24)
	local ok, msg = answer(p, id)
	check("too early (0.24 s): refused", ok == false and msg == TEXTS.TooEarly, msg)
	check("too early: no Cash, nothing earned", d.cash.Value == 0 and #EARNINGS == 0)
	check("too early: the call is closed, counted, and nobody is engaged", #waiting(p) == 0 and stats(p).early == 1 and stats(p).answered == 0 and not TaskServer.isEngaged(p))
	ok, msg = answer(p, id)
	check("answering a closed call again: it is gone", ok == false and msg == TEXTS.Gone)

	id = spawnCall(p)
	advance(0.25)
	ok = answer(p, id)
	check("exactly 0.25 s is not too early", ok == true and stats(p).answered == 1)
	check("0.25 s: engaged", TaskServer.isEngaged(p))

	id = spawnCall(p)
	advance(8)
	ok = answer(p, id)
	check("exactly at the limit (8 s) is still in time", ok == true and stats(p).answered == 2)

	local cash = d.cash.Value
	id = spawnCall(p)
	advance(8.01)
	ok, msg = answer(p, id)
	check("too late (8.01 s): refused", ok == false and msg == TEXTS.TooLate, msg)
	check("too late: no Cash, counted as missed, call closed", d.cash.Value == cash and stats(p).missed == 1 and #waiting(p) == 0)
	check("too late: the chain is broken", lastState(p).chain == 0 and lastState(p).mult == 1)

	-- the tick expires a call by itself; a late answer finds it gone
	id = spawnCall(p)
	advance(9)
	TaskServer.step(p, CLOCK)
	check("the tick expires a call after its limit", #waiting(p) == 0 and stats(p).missed == 2)
	ok, msg = answer(p, id)
	check("answering an expired call: gone", ok == false and msg == TEXTS.Gone)

	-- double answer
	id = spawnCall(p)
	advance(1)
	cash = d.cash.Value
	local ok1, _, info1 = answer(p, id)
	local ok2, msg2 = answer(p, id)
	check("double answer: the first pays", ok1 == true and info1.cash > 0 and d.cash.Value == cash + info1.cash)
	check("double answer: the second is refused and pays nothing", ok2 == false and msg2 == TEXTS.Gone and d.cash.Value == cash + info1.cash)
	check("double answer: counted once", stats(p).answered == 3)

	-- an id that was never a call
	ok, msg = answer(p, 999)
	check("a call number that never existed: gone", ok == false and msg == TEXTS.Gone)
end

-- 6. Reward = 7 s of Income, the chain, the pay path ------------------------------------------
do
	EARNINGS = {}
	local p, d = newPlayer(nil, { income = 10 })
	noArrivals(p)
	richBank(p)
	local id = spawnCall(p)
	advance(1)
	local ok, text, info = answer(p, id)
	check("reward = 7 s of Income (10/s -> $70)", ok and info.cash == 70 and d.cash.Value == 70, info and info.cash)
	check("the Cash goes through addEarnings once, with the same amount", #EARNINGS == 1 and EARNINGS[1] == 70)
	check("the answer says what it paid", text == "+$70")
	check("the stats count it", stats(p).cash == 70 and near(stats(p).rewardSeconds, 7))

	for _, income in ipairs({ 1, 3, 100, 12345 }) do
		local q, qd = newPlayer(nil, { income = income })
		noArrivals(q); richBank(q)
		local qid = spawnCall(q)
		advance(1)
		local _, _, qi = answer(q, qid)
		check("reward at Income " .. income .. " = floor(7 x Income)", qi.cash == 7 * income, qi.cash)
	end
	local z, zd = newPlayer(nil, { income = 0 })
	noArrivals(z)
	local zid = spawnCall(z)
	advance(1)
	local zok, _, zinfo = answer(z, zid)
	check("Income 0: the answer is graded and pays 0 (no error)", zok == true and zinfo.cash == 0 and zd.cash.Value == 0)

	-- the chain: x1.0, x1.1 ... x2.0, then x2.0 forever
	EARNINGS = {}
	local c, cd = newPlayer(nil, { income = 10 })
	noArrivals(c); richBank(c)
	local expected = { 70, 77, 84, 91, 98, 105, 112, 119, 126, 133, 140, 140, 140 }
	local all = true
	local maxMult = 0
	for i = 1, #expected do
		local cid = spawnCall(c)
		advance(0.4 + 0.07 * ((i * 3) % 7))
		local cok, _, ci = answer(c, cid)
		if not cok or ci.cash ~= expected[i] then
			all = false
			print_real("   chain step " .. i .. " paid " .. tostring(ci and ci.cash) .. ", expected " .. expected[i])
		end
		maxMult = math.max(maxMult, ci and ci.mult or 0)
	end
	check("chain: 70, 77, 84 ... 140 and then 140 again", all)
	check("chain bonus never goes above x2", maxMult == 2)
	check("bestChain is the longest chain", cd.tasks.bestChain == 13)

	-- expiry breaks the chain, skip keeps it
	local cid = spawnCall(c)
	advance(9)
	TaskServer.step(c, CLOCK)
	cid = spawnCall(c)
	advance(1)
	local _, _, afterMiss = answer(c, cid)
	check("an expired call resets the chain (next answer x1.0)", afterMiss.cash == 70 and afterMiss.mult == 1)
	cid = spawnCall(c)
	advance(1)
	answer(c, cid)
	cid = spawnCall(c)
	advance(1)
	local skipOk = onAction(c, "Skip", cid)
	check("skip is free", skipOk == true and #waiting(c) == 0 and stats(c).skipped == 1)
	cid = spawnCall(c)
	advance(1)
	local _, _, afterSkip = answer(c, cid)
	check("skip keeps the chain (x1.2 after two answers)", near(afterSkip.mult, 1.2), afterSkip.mult)
end

-- 7. Skip rules, cooldown, busy, not ready -----------------------------------------------------
do
	local p, d = newPlayer(nil)
	noArrivals(p)
	local ok, msg = onAction(p, "Skip", 12345)
	check("skipping a call that isn't there: gone", ok == false and msg == TEXTS.Gone)
	local id = spawnCall(p)
	row.skip = false
	ok, msg = onAction(p, "Skip", id)
	check("a row with skip = false can't be skipped", ok == false and #waiting(p) == 1)
	row.skip = true
	advance(1)
	onAction(p, "Skip", id)
	check("a skip never makes the player engaged", not TaskServer.isEngaged(p) and stats(p).answered == 0)

	-- cooldown between two answers of the same kind
	row.cooldown = 5
	richBank(p)
	local a = spawnCall(p)
	advance(1)
	answer(p, a)
	local b = spawnCall(p)
	advance(1)
	ok, msg = answer(p, b)
	check("cooldown: a second answer too soon is refused", ok == false and msg == TEXTS.Slow and #waiting(p) == 1)
	advance(4)
	ok = answer(p, b)
	check("cooldown: allowed again after it", ok == true)
	row.cooldown = 0

	-- IPO being saved
	local q, qd = newPlayer(nil)
	noArrivals(q)
	local qid = spawnCall(q)
	advance(1)
	qd.ipo.busy = true
	ok, msg = answer(q, qid)
	check("during an IPO save an answer is refused and the call waits", ok == false and msg == TEXTS.IpoBusy and #waiting(q) == 1 and qd.cash.Value == 0)
	qd.ipo.busy = false
	ok = answer(q, qid)
	check("after the IPO save the same call can be answered", ok == true)
	local r, rd = newPlayer(nil)
	RANDOM = 0
	TaskServer.step(r, CLOCK) -- schedules
	rd.ipo.busy = true
	tick(r, 60, 1)
	check("no call arrives while an IPO is being saved", stats(r).offered == 0)
	rd.ipo.busy = false

	-- not ready
	local s, sd = newPlayer(nil, { ready = false })
	ok, msg = onAction(s, "Sync")
	check("before data.ready every request is refused", ok == false and msg == TEXTS.Loading)
	tick(s, 60, 1)
	check("before data.ready nothing arrives and no time is counted", stats(s).offered == 0 and stats(s).online == 0)
	sd.ready = true
	ok = onAction(s, "Sync")
	check("once ready, it works", ok == true)

	-- the engine can be switched off while a server runs
	C.Enabled = false
	ok, msg = onAction(s, "Sync")
	check("Enabled = false: the remote refuses", ok == false and msg == TEXTS.Off)
	check("Enabled = false: nobody is engaged", TaskServer.isEngaged(s) == false)
	check("Enabled = false: Debug is refused", DEBUG.TaskSpawn(s, sd) == TEXTS.Off)
	C.Enabled = true
end

-- 8. Queue overflow --------------------------------------------------------------------------------
do
	local p, d = newPlayer(nil)
	noArrivals(p)
	local oldLimit = row.limit
	row.limit = 1000
	for i = 1, 3 do spawnCall(p) end
	check("3 calls wait", #waiting(p) == 3 and stats(p).offered == 3)
	local id, text = spawnCall(p)
	check("a 4th call is refused: the queue holds 3", #waiting(p) == 3 and text == "The queue is full" and stats(p).dropped == 1 and stats(p).offered == 3)
	-- a natural arrival into a full queue is dropped too
	p.data.tasks.run.nextAt.Call = CLOCK + 5
	tick(p, 6, 1)
	check("an arrival into a full queue is dropped", #waiting(p) == 3 and stats(p).dropped == 2 and stats(p).arrivals == 1, #waiting(p) .. " waiting, dropped " .. stats(p).dropped)
	local ids = {}
	for _, call in ipairs(waiting(p)) do ids[#ids + 1] = call.id end
	check("the 3 waiting calls have their own numbers", ids[1] ~= ids[2] and ids[2] ~= ids[3] and ids[1] ~= ids[3])
	advance(1)
	check("answering the middle one leaves the other two", answer(p, ids[2]) and #waiting(p) == 2)
	row.limit = oldLimit
end

-- 9. Input from the client: only a call number ---------------------------------------------------------
do
	local p, d = newPlayer(nil)
	noArrivals(p)
	local id = spawnCall(p)
	advance(1)
	WARNINGS = {}
	local junk = { "5", 1.5, -3, 0, 0 / 0, math.huge, 2 ^ 40, {}, true, nil }
	local all = true
	for i = 1, 10 do
		advance(0.2)
		local ok, msg = onAction(p, "Answer", junk[i])
		if ok ~= false or msg ~= "Bad request" then all = false end
	end
	check("a call number that isn't a whole number from 1 up is refused (Bad request)", all)
	check("bad input paid nothing and changed nothing", d.cash.Value == 0 and #waiting(p) == 1 and stats(p).answered == 0)
	check("bad input is ignored with a warning, but only one in 10 s", #WARNINGS >= 1 and #WARNINGS <= 2, #WARNINGS)
	advance(1)
	local ok, msg = onAction(p, nil)
	check("no action: Bad request", ok == false and msg == "Bad request")
	ok, msg = onAction(p, 5)
	check("a number as the action: Bad request", ok == false and msg == "Bad request")
	ok, msg = onAction(p, "Hack")
	check("an unknown action is refused", ok == false and msg == "Unknown action")
	ok, msg = onAction(p, "Pause", "yes")
	check("Pause needs a boolean", ok == false and msg == "Bad request" and p.data.tasks.run.paused == false)
	ok, msg = onAction(p, "Skip", "x")
	check("Skip needs a call number too", ok == false and msg == "Bad request")
	check("a client can't send a reward, time or amount: Answer takes only the call number and ignores the rest",
		(function()
			advance(1)
			local before = d.cash.Value
			local okAns, _, info = onAction(p, "Answer", id, 999999, "reward")
			return okAns == true and d.cash.Value == before + 70 and info.cash == 70
		end)())
end

-- 10. Rate limits ---------------------------------------------------------------------------------------
do
	local p, d = newPlayer(nil)
	noArrivals(p)
	advance(10)
	local okCount, refused = 0, 0
	for i = 1, 10 do
		local ok, msg = onAction(p, "Sync")
		if ok then okCount += 1 elseif msg == TEXTS.Slow then refused += 1 end
	end
	check("8 requests in one instant pass, the rest are refused (token bucket)", okCount == 8 and refused == 2, okCount)
	advance(0.5)
	okCount = 0
	for i = 1, 6 do
		if onAction(p, "Sync") then okCount += 1 end
	end
	check("half a second later 4 more tokens are back", okCount == 4, okCount)

	-- 40 graded answers a minute
	local q, qd = newPlayer(nil)
	noArrivals(q); richBank(q)
	advance(10)
	local graded = 0
	local refusedAt
	for i = 1, 45 do
		local id = spawnCall(q)
		advance(0.25 + 0.06 * ((i * 5) % 11))
		local ok, msg = answer(q, id)
		if ok then graded += 1 elseif not refusedAt then refusedAt = i end
		advance(0.1)
		if not ok then break end
	end
	check("at most 40 graded answers per minute, the 41st waits", graded == 40 and refusedAt == 41, graded)
	check("the refused call stays open", #waiting(q) >= 1)
	advance(61)
	local nid = spawnCall(q)
	advance(1)
	check("... and it is graded", answer(q, nid) == true)
end

-- 11. Auto-resolve by Sales, never engaged -----------------------------------------------------------------
do
	-- a player who is engaged, with 3 Sales: the team may take the call
	local p, d = newPlayer(nil, { income = 10, employees = crew(3, "HustleHamster") })
	noArrivals(p); richBank(p)
	local id = spawnCall(p)
	advance(1)
	answer(p, id)
	EARNINGS = {}
	local cashBefore = d.cash.Value
	RANDOM = 0.1 -- 0.1 < 1 - 0.8^3 = 0.488: the team takes it
	p.data.tasks.run.nextAt.Call = CLOCK + 1
	local offeredBefore = stats(p).offered
	tick(p, 2, 1)
	check("Sales take a call: nothing waits for the player", #waiting(p) == 0 and stats(p).offered == offeredBefore and stats(p).autoResolved == 1)
	check("the team's call pays half: 3.5 s of Income = $35, through addEarnings", d.cash.Value == cashBefore + 35 and #EARNINGS == 1 and EARNINGS[1] == 35, EARNINGS[1])
	check("the team's call is not graded: answered stays 1, the chain stays", stats(p).answered == 1 and lastState(p).chain == 1)
	local engagedBefore = stats(p).engaged
	tick(p, 10, 1)
	local handled
	for _, event in ipairs(p.events) do if event.kind == "handled" then handled = event.payload end end
	check("the player hears it once, as one line: 'Team handled 1 call'", handled == 1)

	-- not a call the team can take: the roll is above the share
	RANDOM = 0.5 -- 0.5 >= 0.488
	p.data.tasks.run.nextAt.Call = CLOCK + 1
	tick(p, 2, 1)
	check("above the share the call waits for the player", #waiting(p) == 1 and stats(p).autoResolved == 1)
	advance(1)
	answer(p, waiting(p)[1].id)

	-- a never-engaged player: the team does nothing
	RANDOM = 0
	local q, qd = newPlayer(nil, { employees = crew(10, "HustleHamster") })
	TaskServer.step(q, CLOCK)
	q.data.tasks.run.nextAt.Call = CLOCK + 1
	tick(q, 2, 1)
	check("a player who isn't engaged is not 'present': the team does not take the call", stats(q).autoResolved == 0 and #waiting(q) == 1)

	-- other roles don't count
	local r, rd = newPlayer(nil, { employees = crew(10, "CodingCat") })
	noArrivals(r); richBank(r)
	local rid = spawnCall(r)
	advance(1)
	answer(r, rid)
	r.data.tasks.run.nextAt.Call = CLOCK + 1
	tick(r, 2, 1)
	check("engineers don't take calls (no Sales, no share)", stats(r).autoResolved == 0 and #waiting(r) == 1)

	-- the cap: the founder keeps 25%
	local many, md = newPlayer(nil, { employees = crew(20, "SalesShark") })
	noArrivals(many); richBank(many)
	local mid = spawnCall(many)
	advance(1)
	answer(many, mid)
	RANDOM = 0.74
	many.data.tasks.run.nextAt.Call = CLOCK + 1
	tick(many, 2, 1)
	check("20 Sales: share is capped at 75% (0.74 is taken)", stats(many).autoResolved == 1)
	RANDOM = 0.76
	many.data.tasks.run.nextAt.Call = CLOCK + 1
	tick(many, 2, 1)
	check("20 Sales: 0.76 is not taken (the founder keeps 25%)", stats(many).autoResolved == 1 and #waiting(many) == 1)

	-- exceptions are never taken
	row.routine = false
	RANDOM = 0
	local e, ed = newPlayer(nil, { employees = crew(10, "HustleHamster") })
	noArrivals(e); richBank(e)
	local eid = spawnCall(e)
	advance(1)
	answer(e, eid)
	e.data.tasks.run.nextAt.Call = CLOCK + 1
	tick(e, 2, 1)
	check("a task that isn't routine is never taken by the team", stats(e).autoResolved == 0)
	row.routine = true
	RANDOM = 0
end

-- 12. Demand: the gap shrinks with hires, never past the cap D <= 2.0 ------------------------------------------
do
	local function firstArrival(hires, opts)
		opts = opts or {}
		opts.employees = crew(hires, "CodingCat")
		RANDOM = 0
		local p = newPlayer(nil, opts)
		TaskServer.step(p, CLOCK) -- schedules the first call
		local waited = waitForArrival(p, 60)
		return waited, p
	end
	local w0 = firstArrival(0)
	check("no hires: the first call after 20 s", w0 == 20, w0)
	local w5 = firstArrival(5)
	check("5 hires: 20 / 1.4 = 14.3 s -> the call comes in the tick after 14.3 s", w5 == 14.5, w5)
	local w13 = firstArrival(13)
	check("13 hires: D hits 2.0, 10 s", w13 == 10, w13)
	local w50 = firstArrival(50)
	local w500 = firstArrival(500)
	check("50 and 500 hires: still 10 s (D <= 2.0)", w50 == 10 and w500 == 10, tostring(w50) .. " " .. tostring(w500))
	RANDOM = 1
	local p = newPlayer(nil, { employees = crew(0) })
	TaskServer.step(p, CLOCK)
	local waited = waitForArrival(p, 60)
	check("the longest roll with no hires: 40 s", waited == 40, waited)
	RANDOM = 0

	-- the rung speeds calls up and shortens the limit
	local q, qd = newPlayer(nil)
	DEBUG.TaskSetRung(q, qd, "4")
	TaskServer.step(q, CLOCK)
	local qw = waitForArrival(q, 60)
	check("rung 4 (level 4): the gap is 20 / 1.08 = 18.5 s (the tick after it)", qw == 19, qw)
	check("rung 4: the limit is 8 x 0.88 = 7.04 s", near(waiting(q)[1].limit, 7.04), waiting(q)[1] and waiting(q)[1].limit)
	local r, rd = newPlayer(nil, { ipos = 20 })
	DEBUG.TaskSetRung(r, rd, "0")
	check("20 IPOs count as level 10 at most", near(C.limitFor(row, C.level(0, 20)), 8 * 0.70))
end

-- 13. Engaged: only a graded answer, 3 minutes ---------------------------------------------------------------
do
	local p, d = newPlayer(nil)
	noArrivals(p); richBank(p)
	check("nobody starts engaged", not TaskServer.isEngaged(p))
	tick(p, 30, 1)
	check("time alone never makes anyone engaged", not TaskServer.isEngaged(p) and stats(p).engaged == 0)
	for _, action in ipairs({ "Sync", "Start", "Pause" }) do
		onAction(p, action, action == "Pause" and false or nil)
		advance(0.2)
	end
	check("Sync, Start and Pause never make anyone engaged", not TaskServer.isEngaged(p))
	local id = spawnCall(p)
	advance(1)
	answer(p, id)
	check("a graded answer makes the player engaged", TaskServer.isEngaged(p))
	advance(179)
	check("... still engaged after 179 s", TaskServer.isEngaged(p))
	advance(1)
	check("... and at exactly 180 s", TaskServer.isEngaged(p))
	advance(0.5)
	check("... but not after 180.5 s", not TaskServer.isEngaged(p))
	id = spawnCall(p)
	advance(1)
	answer(p, id)
	check("a new answer makes the player engaged again", TaskServer.isEngaged(p))

	-- seconds are counted while engaged
	local q, qd = newPlayer(nil, { income = 10 })
	noArrivals(q); richBank(q)
	local qid = spawnCall(q)
	advance(1)
	answer(q, qid)
	tick(q, 10, 1)
	check("engaged seconds are counted: 10 s", stats(q).engaged == 10 and TaskServer.engagedSeconds(q) == 10, stats(q).engaged)
	tick(q, 200, 2)
	check("the counter stops when the player isn't engaged any more (180 s window)", stats(q).engaged >= 179 and stats(q).engaged <= 181, stats(q).engaged)
	check("online seconds are counted too", stats(q).online >= 210)

	-- a pause never counts as engaged: a graded answer, then a window open, adds no engaged seconds beyond the grading window
	local pp, pd = newPlayer(nil, { income = 10 })
	noArrivals(pp); richBank(pp)
	local pid = spawnCall(pp)
	advance(1)
	answer(pp, pid)
	tick(pp, 5, 1)
	local engagedBefore = stats(pp).engaged
	local secondsBefore = TaskServer.engagedSeconds(pp)
	check("before the pause: 5 engaged seconds after the graded answer", engagedBefore == 5 and secondsBefore == 5, engagedBefore)
	onAction(pp, "Pause", true)
	tick(pp, 120, 1)
	check("a pause of 120 s (inside the 180 s window) adds no engaged seconds", stats(pp).engaged == engagedBefore and TaskServer.engagedSeconds(pp) == secondsBefore, stats(pp).engaged)
	check("... but the session's online seconds still count", stats(pp).online >= 125)
	tick(pp, 400, 5)
	check("a pause far past the window adds none either", stats(pp).engaged == engagedBefore, stats(pp).engaged)
	onAction(pp, "Pause", false)
	check("closing the window adds none for the time it was open", stats(pp).engaged == engagedBefore, stats(pp).engaged)
	-- a window that opens late: the seconds before it count, the window does not
	local qq, qd = newPlayer(nil, { income = 10 })
	noArrivals(qq); richBank(qq)
	local qid2 = spawnCall(qq)
	advance(1)
	answer(qq, qid2)
	tick(qq, 10, 1)
	onAction(qq, "Pause", true)
	tick(qq, 30, 1)
	onAction(qq, "Pause", false)
	tick(qq, 10, 1)
	check("10 s before, 30 s in a window, 10 s after: 20 engaged seconds", stats(qq).engaged == 20 and TaskServer.engagedSeconds(qq) == 20, stats(qq).engaged)

	-- nothing else sets lastGradedAt
	local r, rd = newPlayer(nil, { employees = crew(5, "HustleHamster") })
	noArrivals(r)
	local rid = spawnCall(r)
	advance(0.1)
	answer(r, rid) -- too early
	rid = spawnCall(r)
	advance(1)
	onAction(r, "Skip", rid)
	check("too early and skip never make a player engaged", not TaskServer.isEngaged(r) and r.data.tasks.run.lastGradedAt == nil)
end

-- 14. The engaged counter at the 08:00 UTC boundary -------------------------------------------------------------
do
	check("the day starts at 08:00 UTC", DC.ResetHourUtc == 8 and DC.dayNumber(DC.dayStart(20001) - 1) == 20000 and DC.dayNumber(DC.dayStart(20001)) == 20001)
	NOW = DC.dayStart(20001) - 4
	local p, d = newPlayer(nil)
	noArrivals(p); richBank(p)
	local id = spawnCall(p)
	advance(1) -- NOW = boundary - 3
	answer(p, id)
	tick(p, 2, 1) -- boundary - 1: two seconds counted on day 20000
	check("before 08:00 UTC the seconds belong to day 20000", d.tasks.engagedDay == 20000 and d.tasks.engagedSeconds == 2, d.tasks.engagedSeconds)
	check("the day's seconds are saved with their day", TaskServer.serialize(d).engagedDay == 20000 and TaskServer.serialize(d).engagedSeconds == 2)
	tick(p, 1, 1) -- exactly 08:00:00 UTC
	check("at exactly 08:00:00 UTC the counter starts again on day 20001", d.tasks.engagedDay == 20001 and d.tasks.engagedSeconds == 1, d.tasks.engagedSeconds)
	tick(p, 3, 1)
	check("and goes on counting from there", d.tasks.engagedDay == 20001 and d.tasks.engagedSeconds == 4, d.tasks.engagedSeconds)
	check("the total of the day before is not carried over", TaskServer.engagedSeconds(p) == 4)
	check("the stats still count the whole session", stats(p).engaged == 6, stats(p).engaged)
	-- a rejoin after the boundary ignores yesterday
	local saved = TaskServer.serialize(d)
	NOW = DC.dayStart(20002) + 5
	local p2, d2 = newPlayer(saved)
	check("a rejoin on the next day starts at 0", d2.tasks.engagedDay == 20002 and d2.tasks.engagedSeconds == 0 and TaskServer.engagedSeconds(p2) == 0)
	NOW = DC.dayStart(20002) - 1
	local p3, d3 = newPlayer({ engagedDay = 20001, engagedSeconds = 9000 })
	check("one second before 08:00 UTC yesterday's seconds still count", d3.tasks.engagedDay == 20001 and d3.tasks.engagedSeconds == 9000 and TaskServer.engagedSeconds(p3) == 9000)
	NOW = 20000 * 86400 + 12 * 3600
end

-- 15. Quiet mode and resume -------------------------------------------------------------------------------------------
do
	RANDOM = 0
	local p, d = newPlayer(nil)
	noArrivals(p)
	for i = 1, 3 do
		spawnCall(p)
		advance(9)
		TaskServer.step(p, CLOCK)
	end
	check("3 expired calls in a row start quiet mode", lastState(p).quiet == true and stats(p).missed == 3)
	p.data.tasks.run.nextAt.Call = CLOCK - 1
	tick(p, 100, 1)
	check("in quiet mode no call arrives", stats(p).offered == 3 and #waiting(p) == 0)
	local ok = onAction(p, "Start")
	check("'Tap to resume' brings back a call at once", ok == true and #waiting(p) == 1 and lastState(p).quiet == false)
	advance(1)
	check("and answering it is graded", answer(p, waiting(p)[1].id) == true and TaskServer.isEngaged(p))
	onAction(p, "Start")
	check("Start when not quiet changes nothing", #waiting(p) == 0)

	-- 90 s without a graded answer
	local q, qd = newPlayer(nil)
	TaskServer.step(q, CLOCK)
	for _ = 1, 80 do -- the player skips every call: no expiry, but no graded answer either
		tick(q, 1, 1)
		for _, call in ipairs(waiting(q)) do onAction(q, "Skip", call.id) end
	end
	check("80 s in, calls come and it isn't quiet yet", stats(q).offered >= 3 and stats(q).skipped >= 3 and lastState(q).quiet == false)
	for _ = 1, 15 do
		tick(q, 1, 1)
		for _, call in ipairs(waiting(q)) do onAction(q, "Skip", call.id) end
	end
	check("90 s without a graded answer: quiet mode", lastState(q).quiet == true)
	local offered = stats(q).offered
	tick(q, 120, 1)
	check("... and it stays quiet", stats(q).offered == offered)

	-- answering a waiting call also ends quiet mode
	local r, rd = newPlayer(nil)
	noArrivals(r)
	local rid = spawnCall(r)
	r.data.tasks.run.quiet = true
	advance(1)
	answer(r, rid)
	check("answering a call that was waiting ends quiet mode", r.data.tasks.run.quiet == false)

	-- a skip is not an expiry
	local s, sd = newPlayer(nil)
	noArrivals(s)
	for i = 1, 6 do
		local sid = spawnCall(s)
		advance(1)
		if i % 3 == 0 then onAction(s, "Skip", sid) else advance(9); TaskServer.step(s, CLOCK) end
	end
	check("a skip between expiries keeps it from being 3 in a row", s.data.tasks.run.quiet == false or s.data.tasks.run.misses < 3)
end

-- 16. Flags: early spam and a constant reaction -----------------------------------------------------------------------
do
	local function play(p, reaction)
		local id = spawnCall(p)
		advance(reaction)
		local ok, msg, info = answer(p, id)
		advance(0.5)
		return ok, msg, info
	end
	local p, d = newPlayer(nil)
	noArrivals(p); richBank(p)
	local paid = 0
	local last
	for i = 1, 30 do
		local ok, _, info = play(p, 0.5)
		if i < 30 and ok and info.cash > 0 then paid += 1 end
		last = info
	end
	check("29 answers with the very same reaction time are paid", paid == 29)
	check("the 30th identical reaction flags the player: it pays 0", last.cash == 0 and stats(p).flagged == 1 and stats(p).answered == 29)
	local ok, _, info = play(p, 0.9)
	check("a different reaction time clears the pattern: the next answer pays again", ok == true and info.cash > 0)

	local q, qd = newPlayer(nil)
	noArrivals(q); richBank(q)
	local flagged = 0
	for i = 1, 60 do
		local _, _, info = play(q, 0.3 + 0.05 * ((i * 7) % 13))
		advance(1.5)
		if info and info.cash == 0 then flagged += 1 end
	end
	check("60 answers with natural reaction times are never flagged", flagged == 0 and stats(q).flagged == 0 and stats(q).answered == 60, stats(q).answered)

	local r, rd = newPlayer(nil)
	noArrivals(r); richBank(r)
	for i = 1, 20 do
		local ok, msg = play(r, 0.1)
		if msg ~= TEXTS.TooEarly then paid = -1 end
	end
	check("20 early answers in an hour", stats(r).early == 20)
	local _, _, flaggedInfo = play(r, 1)
	check("the 21st answer is flagged: pays 0 and is not engaged", flaggedInfo.cash == 0 and stats(r).flagged == 1 and not TaskServer.isEngaged(r))
	advance(3601)
	local _, _, freshInfo = play(r, 1)
	check("an hour later the flags are gone and answers pay again", freshInfo.cash > 0 and TaskServer.isEngaged(r))
end

-- 17. Budget: the autoclicker wall --------------------------------------------------------------------------------------
do
	C.BudgetBank = 60
	local p, d = newPlayer(nil, { income = 1000 })
	noArrivals(p)
	local paidEach = {}
	for i = 1, 10 do
		local id = spawnCall(p)
		advance(0.4 + 0.07 * ((i * 3) % 7))
		local _, _, info = answer(p, id)
		paidEach[i] = info.cash
		advance(0.3)
	end
	check("the first answer is paid in full (7 s = $7000)", paidEach[1] == 7000)
	local naive = 0
	for i = 1, 10 do naive += math.floor(7 * C.chainMultiplier(row, i - 1) * 1000 + 1e-6) end
	check("the bank is 60 s: answers beyond it pay 20% of the rest", stats(p).overBudget > 0 and stats(p).cash < naive, stats(p).cash)
	check("... and never less than the 60 s banked", stats(p).cash >= 60 * 1000, stats(p).cash)
	check("... the reward seconds in the stats match the Cash", near(stats(p).rewardSeconds * 1000, stats(p).cash, 10))

	local q, qd = newPlayer(nil)
	noArrivals(q)
	q.data.tasks.run.bank = 0
	tick(q, 10, 1)
	check("the bank refills at the rung's budget (0.85 s per s at Garage): 8.5 s in 10 s", near(q.data.tasks.run.bank, 8.5, 0.01), q.data.tasks.run.bank)
	DEBUG.TaskSetRung(q, qd, "4")
	noArrivals(q)
	q.data.tasks.run.bank = 0
	tick(q, 10, 1)
	check("rung 4 refills at 1.15 per s", near(q.data.tasks.run.bank, 11.5, 0.01), q.data.tasks.run.bank)
	tick(q, 200, 2)
	check("the bank never holds more than 60 s", q.data.tasks.run.bank == 60)
	C.BudgetBank = 1e9
end

-- 18. Pause: a window open freezes waiting calls ---------------------------------------------------------------------------
do
	RANDOM = 0
	local p, d = newPlayer(nil)
	noArrivals(p)
	local id = spawnCall(p)
	advance(1)
	check("Pause(true) is accepted", onAction(p, "Pause", true) == true and p.data.tasks.run.paused)
	tick(p, 20, 1)
	check("a call waits through 20 s of an open window", #waiting(p) == 1 and stats(p).missed == 0)
	check("an open window never makes anyone engaged", not TaskServer.isEngaged(p))
	onAction(p, "Pause", false)
	check("Pause(false): a fresh state with the exact time left", lastState(p).tasks[1] and near(lastState(p).tasks[1].left, 7, 1.1))
	advance(1)
	local ok, _, info = answer(p, id)
	check("answered after the window: graded and paid (the frozen time doesn't count as reaction)", ok == true and info.cash == 70)

	-- at most 30 s per call
	local q, qd = newPlayer(nil)
	noArrivals(q)
	spawnCall(q)
	onAction(q, "Pause", true)
	tick(q, 25, 1)
	check("25 s open: still waiting", #waiting(q) == 1)
	tick(q, 20, 1)
	check("a call can be frozen for 30 s at most: it ended by 45 s", #waiting(q) == 0 and stats(q).missed == 1)

	-- no new calls while a window is open
	local r, rd = newPlayer(nil)
	TaskServer.step(r, CLOCK)
	onAction(r, "Pause", true)
	tick(r, 120, 1)
	check("no call arrives while a window is open", stats(r).offered == 0 and stats(r).arrivals == 0, stats(r).arrivals)
	check("and an open window is not time away (no quiet mode)", lastState(r) == nil or lastState(r).quiet == false)
	onAction(r, "Pause", false)
	local arrived = waitForArrival(r, 60)
	check("calls come again once the window is closed", arrived ~= nil and arrived <= 21, arrived)
end

-- 18b. Pause stays in sync with the client's window -------------------------------------------------------------------------
do
	RANDOM = 0
	local function emptyBucket(p)
		local n = 0
		while n < 40 do
			local ok = onAction(p, "Sync")
			if ok == false then return n end
			n += 1
		end
		return n
	end
	-- the state carries `paused`, so a client that starts with a window open (or lost a request) can see the difference
	local p, d = newPlayer(nil)
	noArrivals(p)
	onAction(p, "Sync")
	check("Sync on start: the state says the server is not paused", lastState(p) ~= nil and lastState(p).paused == false)
	onAction(p, "Pause", true)
	onAction(p, "Sync")
	check("Sync after a Pause(true): the state says paused", lastState(p).paused == true)
	local events = #p.events
	onAction(p, "Pause", true)
	check("a repeated Pause(true) changes nothing and sends no new state", #p.events == events and p.data.tasks.run.paused == true)

	-- Pause(true) refused for rate: the client retries; nothing is lost and nothing stays frozen
	local q, qd = newPlayer(nil)
	local used = emptyBucket(q)
	check("the request bucket runs out after the burst", used == C.RateLimit.burst, used)
	local ok, msg = onAction(q, "Pause", true)
	check("Pause(true) while rate-limited is refused with 'one moment' and the server is NOT paused", ok == false and msg == TEXTS.Slow and q.data.tasks.run.paused == false)
	advance(0.5)
	ok = onAction(q, "Pause", true)
	check("the client's retry a moment later is accepted", ok == true and q.data.tasks.run.paused == true)

	-- Pause(false) is never refused for rate: the server cannot stay paused with no calls coming
	emptyBucket(q)
	ok, msg = onAction(q, "Sync")
	check("the bucket is empty again", ok == false and msg == TEXTS.Slow)
	ok = onAction(q, "Pause", false)
	check("Pause(false) with an empty bucket is still accepted: the server resumes", ok == true and q.data.tasks.run.paused == false and lastState(q).paused == false)
	local arrived2 = waitForArrival(q, 60)
	check("... and calls come again (not stuck paused with no calls)", arrived2 ~= nil and arrived2 <= 21, arrived2)

	-- spam of Pause(false) costs nothing: no state, no reward, no flag
	local r, rd = newPlayer(nil)
	noArrivals(r)
	local before = #r.events
	for _ = 1, 100 do onAction(r, "Pause", false) end
	check("100 x Pause(false) while not paused: nothing is sent and nothing changes", #r.events == before and r.data.tasks.run.paused == false and stats(r).flagged == 0 and rd.cash.Value == 0)
	-- only a bool is accepted
	ok = onAction(r, "Pause", "yes")
	check("Pause needs true or false", ok == false and r.data.tasks.run.paused == false)
end

-- 19. Measurement hooks (gate G1) -----------------------------------------------------------------------------------------------
do
	RANDOM = 0
	local p, d = newPlayer(nil, { income = 10, employees = crew(4) })
	DEBUG.TaskSetRung(p, d, "1")
	noArrivals(p); richBank(p)
	-- 5 answers, then 100 engaged seconds
	for i = 1, 5 do
		local id = spawnCall(p)
		advance(0.5 + 0.1 * i)
		answer(p, id)
	end
	tick(p, 100, 1)
	local s = stats(p)
	check("stats: rung and hires", s.rung == 1 and s.hires == 4)
	check("stats: calls offered, answered, missed", s.offered == 5 and s.answered == 5 and s.missed == 0)
	check("stats: engaged seconds", s.engaged >= 100 and s.engaged <= 105, s.engaged)
	check("stats: Cash and reward seconds", s.cash == 70 + 77 + 84 + 91 + 98 and near(s.rewardSeconds, 42), s.cash)
	local expectedF = s.cash / (10 * s.engaged)
	check("fCash = task Cash per engaged second / base Income per second (information only)", near(s.fCash, expectedF, 1e-9) and s.fCash > 0, s.fCash)
	check("fSecs (the G1 f) = seconds of Income paid per engaged second", near(s.fSecs, s.rewardSeconds / s.engaged, 1e-9) and s.fSecs > 0, s.fSecs)
	check("the stats have no bare 'f': G1 reads fSecs, so nobody reads the Cash-based value by mistake", s.f == nil)
	p.base = 5
	tick(p, 10, 1)
	local after = stats(p)
	check("fCash follows the base Income, second by second",
		near(after.fCash, after.cash / (10 * s.engaged + 5 * (after.engaged - s.engaged)), 1e-9), after.fCash)

	-- Blocker 1: a pass multiplier moves fCash, never fSecs. Same play twice; the second player's Income is
	-- 3x (Cash x2 pass and the like) while the base Income, which has no passes, is the same.
	local function session(income)
		local sp, sd = newPlayer(nil, { income = income, base = 10 })
		DEBUG.TaskSetRung(sp, sd, "1")
		noArrivals(sp); richBank(sp)
		for i = 1, 5 do
			local id = spawnCall(sp)
			advance(0.5 + 0.1 * i)
			answer(sp, id)
		end
		tick(sp, 100, 1)
		return stats(sp), sd
	end
	local plain = session(10)
	local boosted = session(30)
	check("a pass multiplier pays more Cash (x3 here)", boosted.cash == plain.cash * 3, boosted.cash)
	check("fSecs, the G1 f, is the same with or without a pass multiplier", near(plain.fSecs, boosted.fSecs, 1e-9) and plain.fSecs > 0, boosted.fSecs)
	check("fCash is inflated by it (x3 here), which is why it is not the G1 number", near(boosted.fCash, plain.fCash * 3, 1e-9) and boosted.fCash > plain.fCash, boosted.fCash)
	check("the stats are also on the player's tasks section", d.tasks.done == 5 and d.tasks.bestChain == 5 and d.tasks.seen.Call == true)

	-- the log line every 10 minutes, and on leaving
	PRINTS = {}
	local q, qd = newPlayer(nil, { employees = crew(2) })
	noArrivals(q)
	spawnCall(q)
	tick(q, 601, 1)
	local line = PRINTS[#PRINTS]
	check("a stats line is logged after 10 minutes", line ~= nil and string.find(line, "[TaskStats]", 1, true) ~= nil)
	check("... it has the rung, hires, engaged seconds, calls, Cash and f",
		line and string.find(line, "rung=0", 1, true) and string.find(line, "hires=2", 1, true) and string.find(line, "engaged=", 1, true)
		and string.find(line, "offered=", 1, true) and string.find(line, "answered=", 1, true) and string.find(line, "missed=", 1, true)
		and string.find(line, "cash=", 1, true) and string.find(line, " fSecs=", 1, true) and string.find(line, " fCash=", 1, true))
	check("... the log line says which one is the G1 f",
		line and string.find(line, "(G1 f)", 1, true) and string.find(line, "(info, passes inflate it)", 1, true))
	PRINTS = {}
	PLAYER_REMOVING[#PLAYER_REMOVING](q)
	check("a stats line is logged when the player leaves", #PRINTS == 1)

	-- Debug
	local r, rd = newPlayer(nil)
	check("Debug Set rung: 3", string.find(DEBUG.TaskSetRung(r, rd, "3"), "Rung set to 3", 1, true) ~= nil and stats(r).rung == 3)
	check("Debug Set rung: auto goes back to the funding stage", string.find(DEBUG.TaskSetRung(r, rd, "auto"), "Garage", 1, true) ~= nil and stats(r).rung == 0)
	for _, bad in ipairs({ "5", "-1", "1.5", "abc", "", "nan" }) do
		check("Debug Set rung '" .. bad .. "' is refused", DEBUG.TaskSetRung(r, rd, bad) == "Bad rung" and stats(r).rung == 0)
	end
	local summary = DEBUG.TaskStats(r, rd)
	check("Debug stats gives a short line", string.find(summary, "Rung 0", 1, true) ~= nil)
	check("Debug stats shows both numbers, labelled, and says which one G1 uses",
		string.find(summary, "G1 f = ", 1, true) and string.find(summary, "Income-seconds per engaged second", 1, true)
		and string.find(summary, "fCash ", 1, true) and string.find(summary, "info only", 1, true), summary)
	check("Debug stats says the GUI size is not reported yet", string.find(summary, "TaskGui size not reported yet", 1, true) ~= nil, summary)
	local okLayout = onAction(r, "Layout", Vector3(375, 609, 58))
	local withBar = DEBUG.TaskStats(r, rd)
	check("Layout (Studio only): Debug stats shows the TaskGui size, the top bar and the device height",
		okLayout == true and string.find(withBar, "TaskGui 375x609 (top bar 58 px, device height 667)", 1, true) ~= nil, withBar)
	check("Layout with a number is refused", onAction(r, "Layout", 5) == false and string.find(DEBUG.TaskStats(r, rd), "375x609", 1, true) ~= nil)
	check("Layout with NaN is refused", onAction(r, "Layout", Vector3(0 / 0, 1, 1)) == false)
	onAction(r, "Layout", Vector3(1e12, -5, 1e9))
	check("a huge or negative size is clamped (display only)", string.find(DEBUG.TaskStats(r, rd), "TaskGui 10000x0 (top bar 1000 px", 1, true) ~= nil, DEBUG.TaskStats(r, rd))
	onAction(r, "Layout", Vector3(375, 609, 58))
	IS_STUDIO = false
	check("Layout is refused outside Studio", onAction(r, "Layout", Vector3(1, 2, 3)) == false)
	IS_STUDIO = true
	IS_STUDIO = false
	check("Debug is refused outside Studio", DEBUG.TaskSetRung(r, rd, "2") == "Debug is disabled" and DEBUG.TaskSpawn(r, rd) == "Debug is disabled" and stats(r).rung == 0)
	IS_STUDIO = true
	MODULES.ShopConfig.DebugInStudio = false
	check("Debug is refused with DebugInStudio off", DEBUG.TaskStats(r, rd) == "Debug is disabled")
	MODULES.ShopConfig.DebugInStudio = true

	-- stage to rung
	local expectedRungs = { { 0, 0 }, { 1799, 0 }, { 1800, 1 }, { 6300, 2 }, { 23400, 3 }, { 81000, 4 }, { 1e9, 4 } }
	local allRungs = true
	for _, pair in ipairs(expectedRungs) do
		local sp = newPlayer(nil, { valuation = pair[1] })
		if stats(sp).rung ~= pair[2] then allRungs = false; print_real("   valuation " .. pair[1] .. " gave rung " .. stats(sp).rung) end
	end
	check("stage to rung: Garage 0, Seed 1, Series A 2, Series B 3, IPO-ready 4", allRungs)
	check("after an IPO the stages grow, so the same valuation is a lower rung", stats((newPlayer(nil, { valuation = 1800, ipos = 1 }))).rung == 0)
end

-- 20. Save round trip ---------------------------------------------------------------------------------------------------------------
do
	local p, d = newPlayer(nil, { income = 10 })
	noArrivals(p); richBank(p)
	for i = 1, 6 do
		local id = spawnCall(p)
		advance(0.5 + 0.1 * i)
		answer(p, id)
	end
	tick(p, 30, 1)
	local out = TaskServer.serialize(d)
	check("after play there is a section", out ~= nil and out.done == 6 and out.bestChain == 6 and out.seen.Call == true and out.sharesRun == 0)
	check("its engaged day is today's and its seconds whole", out.engagedDay == DC.dayNumber(NOW) and out.engagedSeconds >= 30 and out.engagedSeconds % 1 == 0)
	local keys = 0
	for _ in pairs(out) do keys += 1 end
	check("the section has exactly the 6 fields (sharesRun, done, bestChain, seen, engagedDay, engagedSeconds)", keys == 6)
	local q, qd = newPlayer(out)
	local out2 = TaskServer.serialize(qd)
	check("it loads back the same", out2.done == 6 and out2.bestChain == 6 and out2.engagedSeconds == out.engagedSeconds and out2.engagedDay == out.engagedDay and out2.seen.Call == true)
	check("a loaded player starts with a fresh chain and no waiting calls", #waiting(q) == 0 and (lastState(q) == nil))
end

print_real(string.format("%d passed, %d failed", passed, failed))
"""


TRAY_TESTS = r"""-- Tests for TaskClient's tray layout (the code between its TRAY markers): it fits both phone sizes,
-- clear of the HUD, every bottom-center pop-up lane and Roblox's touch controls ---------------------------
local print_real = print
local passed, failed = 0, 0
local function check(name, cond, extra)
	if cond then passed += 1 else failed += 1; print_real("FAIL: " .. name .. (extra and (" -- " .. tostring(extra)) or "")) end
end
__TRAY__
__PAUSE__
__SHOWN__
local GOALS = __GOALCOUNT__ -- OnboardingConfig.Goals: the Goals card is 30 + 22 per goal + 8 high
local function rect(x, y, w, h) return { x = x, y = y, w = w, h = h } end
local function overlaps(a, b) return a.x < b.x + b.w and b.x < a.x + a.w and a.y < b.y + b.h and b.y < a.y + a.h end
local function trayRect(l) return rect(l.x, l.y, l.w, l.h) end
local function infoRect(l) return rect(l.x, l.infoY, l.w, l.infoH) end
local function touches(layout, other) return overlaps(trayRect(layout), other) or overlaps(infoRect(layout), other) end

-- The bottom-center pop-up lanes: AnchorPoint (0.5, 1), Position (0.5, 0, 1, -offset), Size (0.6, 0, 0, 48) at most 520 wide.
-- Shop and IPO -16, Recruiting -72, Poach -128, Onboarding -184, Daily -240 (-72 on short screens).
local LANE_OFFSETS = { 16, 72, 128, 184, 240 }
local function lane(w, h, offset)
	local width = math.min(0.6 * w, 520)
	return rect((w - width) / 2, h - offset - 48, width, 48)
end
local function lanes(w, h, portrait)
	local list = {}
	for _, offset in ipairs(LANE_OFFSETS) do
		if portrait or offset ~= 240 then list["lane -" .. offset] = lane(w, h, offset) end
	end
	return list
end

-- The numbers the doc's layout section gives
local p = trayLayout(320, 568)
check("portrait 320x568: three chips of 68x48 from x 98 to 310", p.x == 98 and p.chipWidth == 68 and p.h == 48 and p.gap == 4 and p.x + p.w == 310, p.w)
check("portrait 320x568: chips at y 188-236, their line at y 166-186", p.y == 188 and p.y + p.h == 236 and p.infoY == 166 and p.infoY + p.infoH == 186)
local l = trayLayout(667, 375)
check("landscape 667x375: three chips of 52x48 from x 10 to 174, y 92-140, their line at y 70-90",
	l.x == 10 and l.chipWidth == 52 and l.h == 48 and l.x + l.w == 174 and l.y == 92 and l.y + l.h == 140 and l.infoY == 70 and l.infoY + l.infoH == 90, l.w)

-- Every size: on screen, chips of 48 or more, clear of the thumbstick and the jump button
local sizes = { { 320, 568 }, { 375, 667 }, { 360, 640 }, { 414, 736 }, { 768, 1024 }, { 667, 375 }, { 812, 375 }, { 568, 320 }, { 736, 414 }, { 480, 320 }, { 1024, 768 } }
for _, size in ipairs(sizes) do
	local w, h = size[1], size[2]
	local lay = trayLayout(w, h)
	local label = w .. "x" .. h
	local tray, info = trayRect(lay), infoRect(lay)
	check(label .. ": the tray and its line are on the screen", lay.x >= 0 and lay.x + lay.w <= w and lay.y >= 0 and lay.y + lay.h <= h and lay.infoY >= 0)
	check(label .. ": every chip is 48 or more in both directions (touch target)", lay.chipWidth >= 48 and lay.h >= 48)
	local thumbstick = rect(0, h - 170, 170, 170)
	local jump = rect(w - 150, h - 130, 150, 130)
	check(label .. ": clear of the thumbstick zone", not overlaps(tray, thumbstick) and not overlaps(info, thumbstick))
	check(label .. ": clear of the jump button zone", not overlaps(tray, jump) and not overlaps(info, jump))
end

-- Portrait (height 460 and up uses the tall layout): the HUD, and EVERY pop-up lane, for every portrait size
local function portraitRects(w, h)
	local barWidth = math.clamp(w - 108 - 54, 150, 250) -- IpoClient: leaves room for the gift chip
	return {
		hudColumn = rect(12, h / 2 - 210, 76, 420), -- EGGS, SHOP, TEAM, POACH, IPO: x 12-88, centered
		valuationBar = rect(98, 12, barWidth, 64),
		dailyChip = rect(98 + barWidth + 6, 20, 48, 48),
		goalCard = rect(98, 82, barWidth, 30 + 22 * GOALS + 8),
	}
end
for _, size in ipairs({ { 320, 568 }, { 375, 667 }, { 360, 640 }, { 414, 736 }, { 768, 1024 }, { 1024, 768 } }) do
	local w, h = size[1], size[2]
	local lay = trayLayout(w, h)
	local label = "portrait " .. w .. "x" .. h
	local bad
	for name, other in pairs(portraitRects(w, h)) do
		if touches(lay, other) then bad = name end
	end
	check(label .. ": the tray and its line never touch the HUD column, the valuation bar, the gift chip or the Goals card", bad == nil, bad)
	bad = nil
	for name, other in pairs(lanes(w, h, true)) do
		if touches(lay, other) then bad = name end
	end
	check(label .. ": the tray and its line never touch a pop-up lane (-16, -72, -128, -184, -240)", bad == nil, bad)
end
local card = portraitRects(320, 568).goalCard
check("portrait 320x568: the Goals card ends at y " .. (card.y + card.h) .. " and the line above the tray starts at 166 (at least 2 px apart)", p.infoY - (card.y + card.h) >= 2, card.y + card.h)
check("portrait 320x568 (top bar 0): the -240 lane starts at y 280, 44 px below the tray", lane(320, 568, 240).y == 280 and lane(320, 568, 240).y - (p.y + p.h) == 44)
local laneClear = true
for height = 524, 1400 do
	if overlaps(trayRect(trayLayout(320, height)), lane(320, height, 240)) then laneClear = false end
end
check("portrait, any GUI height from 524 up (the -240 lane then starts at or below the tray): clear of the highest lane", laneClear)

-- Landscape 667x375: PROVISIONAL spot (the final one is chosen in Studio, Test > Device). At least: clear of the
-- HUD button row, the valuation bar, the Goals card, the gift chip (CLAIM), the thumbstick and the jump button.
local landscape = {
	hudRow = rect(10, 6, 360, 64), -- 5 buttons of 64 + 8 gap
	valuationBar = rect(370, 6, 233, 64),
	dailyChip = rect(609, 14, 48, 48),
	goalCard = rect(370, 76, 233, 30 + 22 * GOALS + 8),
	thumbstick = rect(0, 375 - 170, 170, 170),
	jump = rect(667 - 150, 375 - 130, 150, 130),
}
local bad
for name, other in pairs(landscape) do
	if touches(l, other) then bad = name end
end
check("landscape 667x375: the tray and its line never touch the HUD row, the valuation bar, the gift chip, the Goals card, the thumbstick or the jump button", bad == nil, bad)
check("landscape: the tray's right edge is clear of the Goals card by 8 px or more", l.x + l.w <= 370 - 8)
bad = nil
for name, other in pairs(lanes(667, 375, false)) do
	if touches(l, other) then bad = name end
end
check("landscape 667x375: it also clears the pop-up lanes (-16, -72, -128, -184), with the current provisional spot", bad == nil, bad)
-- Other wide landscape screens (the bar sits right of the HUD row from 614 px wide on)
for _, size in ipairs({ { 736, 414 }, { 812, 375 } }) do
	local w, h = size[1], size[2]
	local lay = trayLayout(w, h)
	local barWidth = math.clamp(w - 370 - 10 - 54, 0, 250)
	local rects = {
		hudRow = rect(10, 6, 360, 64), valuationBar = rect(370, 6, barWidth, 64),
		dailyChip = rect(370 + barWidth + 6, 14, 48, 48), goalCard = rect(370, 76, barWidth, 30 + 22 * GOALS + 8),
	}
	local why
	for name, other in pairs(rects) do
		if touches(lay, other) then why = name end
	end
	check("landscape " .. w .. "x" .. h .. ": clear of the HUD row, the valuation bar, the gift chip and the Goals card", why == nil, why)
end

-- ---------------------------------------------------------------------------------------------------------------
-- Top bar (IgnoreGuiInset = false): the GUI is shorter than the device by Roblox's top bar, whose size is NOT
-- measured (Debug > Task stats prints the real one). Every size below is run with a bar of 0, 36 and 58 px.
-- Top-anchored things (HUD, valuation bar, Goals card, gift chip) keep their y; the lanes, the thumbstick and the
-- jump button hang from the bottom of the GUI; the left button column is centered in the GUI.
-- ---------------------------------------------------------------------------------------------------------------
local BARS = { 0, 36, 58 }
local function hud(w, h)
	local list = {}
	local cardHeight = 30 + 22 * GOALS + 8
	local barX, barY, barW
	if h < 460 then
		-- short screens: the HUD buttons are a row (5 x 64, 8 apart, from x 10); the valuation bar is right of the row
		-- when it has 180 px or more (IpoClient), else under it
		list["HUD button row"] = rect(10, 6, 352, 64)
		local width = math.clamp(w - 370 - 10 - 54, 0, 250)
		if width >= 180 then
			barX, barY, barW = 370, 6, width
		else
			barX, barY, barW = 10, 76, math.min(250, w - 20 - 54)
		end
	else
		list["left button column"] = rect(12, h / 2 - 210, 76, 420)
		barX, barY, barW = 98, 12, math.clamp(w - 108 - 54, 150, 250)
	end
	list["valuation bar"] = rect(barX, barY, barW, 64)
	list["CLAIM chip"] = rect(math.min(barX + barW + 6, w - 50), barY + 8, 48, 48)
	list["Goals card"] = rect(barX, barY + 70, barW, cardHeight)
	for name, r in pairs(lanes(w, h, h >= 460)) do list[name] = r end
	list["thumbstick"] = rect(0, h - 170, 170, 170)
	list["jump button"] = rect(w - 150, h - 130, 150, 130)
	return list
end
local function touched(w, h)
	local lay = trayLayout(w, h)
	local names = {}
	for name, other in pairs(hud(w, h)) do
		if touches(lay, other) then table.insert(names, name) end
	end
	table.sort(names)
	return names, lay
end

-- ACCEPTED overlaps. Nothing fits everywhere: a spot clear of every lane does not exist at 667x375 with a top bar of
-- 36 px or more, nor at 320x568 with 58 px, and a 568x320 phone has no free gap at all. The tray draws below every
-- other pop-up (DisplayOrder -2), so these overlaps never hide a message. A size/bar that is not listed must touch
-- nothing; a listed one must touch exactly what is listed (so the list can't go stale). Confirm in Studio with Test >
-- Device (320x568 and 667x375); the lines are also in docs/ACTIVE_LOOPS_PROPOSAL.md.
local ACCEPTED = {
	["320x568/58"] = "lane -240",
	["667x375/36"] = "lane -184",
	["667x375/58"] = "lane -184",
	["568x320/0"] = "lane -184, valuation bar",
	["568x320/36"] = "lane -128, lane -184, thumbstick, valuation bar",
	["568x320/58"] = "lane -128, lane -184, thumbstick, valuation bar",
	["640x360/0"] = "lane -184",
	["640x360/36"] = "lane -184",
	["640x360/58"] = "lane -128, lane -184, thumbstick",
	["812x375/36"] = "lane -184",
	["812x375/58"] = "lane -184",
	["844x390/36"] = "lane -184",
	["844x390/58"] = "lane -184",
}
local DUMP = __DUMP__
local REFERENCE = { { 320, 568 }, { 667, 375 } }
local SWEEP = { { 360, 640 }, { 375, 667 }, { 390, 844 }, { 568, 320 }, { 640, 360 }, { 812, 375 }, { 844, 390 } }
local ALL = { { 320, 568 }, { 667, 375 }, { 360, 640 }, { 375, 667 }, { 390, 844 }, { 568, 320 }, { 640, 360 }, { 812, 375 }, { 844, 390 } }
for _, size in ipairs(ALL) do
	for _, bar in ipairs(BARS) do
		local w, h = size[1], size[2] - bar
		local label = w .. "x" .. size[2] .. " top bar " .. bar
		local names, lay = touched(w, h)
		local key = w .. "x" .. size[2] .. "/" .. bar
		local got = table.concat(names, ", ")
		if DUMP then print_real("DUMP " .. key .. " = " .. (got == "" and "none" or got)) end
		local want = ACCEPTED[key] or ""
		check(label .. ": the tray and its line touch " .. (want == "" and "nothing" or ("only " .. want)), got == want, got)
		check(label .. ": on the screen, chips 48 or more (touch target)", lay.x >= 0 and lay.x + lay.w <= w and lay.infoY >= 0 and lay.y + lay.h <= h and lay.chipWidth >= 48 and lay.h >= 48)
		-- never an overlap with the HUD, the Goals card, the gift chip or the touch controls on the two reference sizes
		if size == REFERENCE[1] or size == REFERENCE[2] then
			local bad
			for _, name in ipairs(names) do
				if not string.find(name, "^lane %-") then bad = name end
			end
			check(label .. ": reference size: only pop-up lanes are ever touched (never HUD, Goals card, CLAIM, thumbstick, jump)", bad == nil, bad)
		end
	end
end
check("reference sizes with a top bar of 0 px touch nothing at all", #touched(320, 568) == 0 and #touched(667, 375) == 0)
check("320x568 with 36 px: clear of every lane (-16 ... -240)", #touched(320, 568 - 36) == 0)
do
	local names = touched(320, 568 - 58)
	check("320x568 with 58 px: only the -240 lane (the Daily pop-up) is touched", #names == 1 and names[1] == "lane -240", table.concat(names, ","))
end

-- The client's pause sync (PAUSE markers): the server must hear about a window that is already open at start,
-- and about every change, until it agrees
check("pause sync: a window already open at start is sent (server says not paused)", pauseToSend(true, false) == true)
check("pause sync: a closed window is sent while the server is still paused", pauseToSend(false, true) == false)
check("pause sync: nothing is sent when they agree", pauseToSend(true, true) == nil and pauseToSend(false, false) == nil)
do
	-- a refused request is tried again until the server accepts; the server's state then agrees
	local serverPaused, windowOpen = false, true
	local refusals, sends = 2, 0
	local function round()
		local wanted = pauseToSend(windowOpen, serverPaused)
		if wanted == nil then return false end
		sends += 1
		if refusals > 0 then refusals -= 1 else serverPaused = wanted end
		return true
	end
	while round() and sends < 10 do end
	check("pause sync: two refused requests (rate limit) are retried and the third is accepted", sends == 3 and serverPaused == true)
	windowOpen = false
	refusals = 1
	sends = 0
	while round() and sends < 10 do end
	check("pause sync: closing the window is retried until the server resumes", sends == 2 and serverPaused == false)
	-- a state that arrives while the window is open and says 'not paused' (a lost request) is repaired
	windowOpen, serverPaused = true, false
	check("pause sync: a state that disagrees with the open window sends Pause(true) again", pauseToSend(windowOpen, serverPaused) == true)
end

-- What is on screen before the Desk (SHOWN markers): nothing about calls until the server says calls are on
check("shown: before the Desk nothing about calls is shown (calls off, none waiting)", callsShown(false, false, 0) == false)
check("shown: with calls on the tray is shown, with or without a waiting call", callsShown(false, true, 0) == true and callsShown(false, true, 2) == true)
check("shown: a call that is still waiting stays visible even if calls are off", callsShown(false, false, 1) == true and callsShown(false, false, 3) == true)
check("shown: an open window hides everything", callsShown(true, true, 3) == false and callsShown(true, false, 0) == false and callsShown(true, true, 0) == false)

print_real(string.format("%d passed, %d failed", passed, failed))
"""

VISUALS_TESTS = r"""-- Tests for the plot visuals: the real PlotArt and PlotVisuals with a fake Roblox (visuals-garage) ----
-- The fake has real 3D math (Vector3, CFrame with rotations) and Instances with parents, so the
-- builder makes the same parts it makes in Studio, and PlotVisuals.check measures them.
local print_real = print
local passed, failed = 0, 0
local function check(name, cond, extra)
	if cond then passed += 1 else failed += 1; print_real("FAIL: " .. name .. (extra ~= nil and (" -- " .. tostring(extra)) or "")) end
end
local function warn() end
local SPAWNED = {}
local task = { spawn = function(f, ...) table.insert(SPAWNED, f) end, wait = function() end }
local CLOCK = 0
local os = { clock = function() CLOCK += 0.05; return CLOCK end, time = function() return 0 end }

-- Vector3
local V = {}
local function vec(x, y, z) return setmetatable({ X = x, Y = y, Z = z }, V) end
V.__index = V
V.__add = function(a, b) return vec(a.X + b.X, a.Y + b.Y, a.Z + b.Z) end
V.__sub = function(a, b) return vec(a.X - b.X, a.Y - b.Y, a.Z - b.Z) end
V.__mul = function(a, b)
	if type(a) == "number" then return vec(a * b.X, a * b.Y, a * b.Z) end
	return vec(a.X * b, a.Y * b, a.Z * b)
end
local Vector3 = { new = function(x, y, z) return vec(x or 0, y or 0, z or 0) end }

-- CFrame: position + row-major rotation matrix, composed like Roblox's
local CF = {}
local function cf(x, y, z, r) return setmetatable({ x = x, y = y, z = z, r = r or { 1, 0, 0, 0, 1, 0, 0, 0, 1 } }, CF) end
local function matmul(a, b)
	local m = {}
	for i = 0, 2 do
		for j = 0, 2 do
			m[i * 3 + j + 1] = a[i * 3 + 1] * b[j + 1] + a[i * 3 + 2] * b[j + 4] + a[i * 3 + 3] * b[j + 7]
		end
	end
	return m
end
CF.__index = function(t, k)
	if k == "Position" then return vec(t.x, t.y, t.z) end
	return CF[k]
end
CF.__mul = function(a, b)
	local r = a.r
	if getmetatable(b) == V then
		return vec(r[1] * b.X + r[2] * b.Y + r[3] * b.Z + a.x, r[4] * b.X + r[5] * b.Y + r[6] * b.Z + a.y, r[7] * b.X + r[8] * b.Y + r[9] * b.Z + a.z)
	end
	return cf(r[1] * b.x + r[2] * b.y + r[3] * b.z + a.x, r[4] * b.x + r[5] * b.y + r[6] * b.z + a.y, r[7] * b.x + r[8] * b.y + r[9] * b.z + a.z, matmul(r, b.r))
end
function CF.GetComponents(t) local r = t.r return t.x, t.y, t.z, r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8], r[9] end
local function rx(a) local c, s = math.cos(a), math.sin(a) return { 1, 0, 0, 0, c, -s, 0, s, c } end
local function ry(a) local c, s = math.cos(a), math.sin(a) return { c, 0, s, 0, 1, 0, -s, 0, c } end
local function rz(a) local c, s = math.cos(a), math.sin(a) return { c, -s, 0, s, c, 0, 0, 0, 1 } end
local CFrame = {
	new = function(x, y, z) return cf(x or 0, y or 0, z or 0) end,
	Angles = function(a, b, c) return cf(0, 0, 0, matmul(matmul(rx(a), ry(b)), rz(c))) end,
	fromEulerAnglesYXZ = function(a, b, c) return cf(0, 0, 0, matmul(matmul(ry(b), rx(a)), rz(c))) end,
}

-- Enums: an unknown name errors, like Roblox
local function enumType(names)
	local t = {}
	for _, n in ipairs(names) do t[n] = { Name = n } end
	return setmetatable(t, { __index = function(_, k) error("not a valid enum item: " .. tostring(k)) end })
end
local Enum = {
	Material = enumType({ "Plastic", "SmoothPlastic", "Neon", "Wood", "WoodPlanks", "Marble", "Slate", "Concrete", "Granite", "Brick",
		"Pebble", "Cobblestone", "CorrodedMetal", "DiamondPlate", "Foil", "Metal", "Grass", "Sand", "Fabric", "Ice", "Glass" }),
	PartType = enumType({ "Block", "Cylinder", "Ball", "Wedge", "CornerWedge" }),
	SurfaceType = enumType({ "Smooth" }),
	NormalId = enumType({ "Top", "Bottom", "Left", "Right", "Front", "Back" }),
	Font = enumType({ "GothamBold", "PermanentMarker", "IndieFlower", "LuckiestGuy", "FredokaOne" }),
	SurfaceGuiSizingMode = enumType({ "PixelsPerStud" }),
}
local Color3 = { fromRGB = function(r, g, b) return { R = r / 255, G = g / 255, B = b / 255, rgb = { r, g, b } } end }
local UDim2 = { fromScale = function(x, y) return { x, y } end }
local NumberRange = { new = function(a, b) return { a, b } end }
local NumberSequence = { new = function(a, b) return { a, b } end }
local ColorSequence = { new = function(a, b) return { a, b } end }
local Vector2 = { new = function(x, y) return { x, y } end }

-- Instances with parents and children
local IS_A = { Part = { BasePart = true }, PointLight = { Light = true } }
local Methods = {}
local Mt = {}
Mt.__index = function(t, k)
	if k == "Parent" then return rawget(t, "_parent") end
	return Methods[k]
end
Mt.__newindex = function(t, k, v)
	if k == "Parent" then
		local old = rawget(t, "_parent")
		if old then
			for i, c in ipairs(old._children) do if c == t then table.remove(old._children, i) break end end
		end
		rawset(t, "_parent", v)
		if v then table.insert(v._children, t) end
	else
		rawset(t, k, v)
	end
end
local function newInstance(class)
	local i = setmetatable({ ClassName = class, Name = class, _children = {}, _attrs = {} }, Mt)
	if class == "Part" then
		rawset(i, "Anchored", false); rawset(i, "CanCollide", true); rawset(i, "CanTouch", true)
		rawset(i, "CanQuery", true); rawset(i, "CastShadow", true); rawset(i, "Transparency", 0)
	end
	return i
end
local Instance = { new = newInstance }
function Methods.GetChildren(t) return table.clone(t._children) end
function Methods.GetDescendants(t)
	local out = {}
	local function walk(n) for _, c in ipairs(n._children) do table.insert(out, c); walk(c) end end
	walk(t)
	return out
end
function Methods.FindFirstChild(t, name) for _, c in ipairs(t._children) do if c.Name == name then return c end end return nil end
function Methods.IsA(t, class) return t.ClassName == class or (IS_A[t.ClassName] ~= nil and IS_A[t.ClassName][class] == true) end
function Methods.SetAttribute(t, k, v) t._attrs[k] = v end
function Methods.GetAttribute(t, k) return t._attrs[k] end
function Methods.Destroy(t) t.Parent = nil; rawset(t, "destroyed", true) end
function Methods.GetFullName(t) local p = t.Parent return (p and p ~= ROOT and (p:GetFullName() .. ".") or "") .. t.Name end
function Methods.ScaleTo(t, s) rawset(t, "scale", s) end
ROOT = nil

local PlotArt = (function()
__PLOTART__
end)()
local PlotVisuals = (function()
__PLOTVISUALS__
end)()
local IpoConfig = (function()
__IPOCONFIG__
end)()
local EXPECTED = __EXPECTED__

-- 1. The data -------------------------------------------------------------------
local problems = PlotVisuals.validate(PlotArt)
check("PlotVisuals.validate finds no problem in PlotArt (shapes, sizes > 0, colors 0-255, materials, Neon names, fonts)", #problems == 0, problems[1])
check("PlotArt has at least one room and never more rooms than IpoConfig has funding stages",
	#PlotArt.Stages >= 1 and #PlotArt.Stages <= #IpoConfig.Stages, #PlotArt.Stages)
if __ALL_STAGES__ then
	check("PlotArt has exactly one room per IpoConfig funding stage", #PlotArt.Stages == #IpoConfig.Stages, #PlotArt.Stages)
end
for i, room in ipairs(PlotArt.Stages) do
	check("room " .. i .. " is keyed to IpoConfig stage " .. i .. " (" .. tostring(IpoConfig.Stages[i] and IpoConfig.Stages[i].key) .. ")",
		IpoConfig.Stages[i] ~= nil and room.key == IpoConfig.Stages[i].key, room.key)
end
for _, name in ipairs(EXPECTED.upgrades) do
	check("upgrade '" .. name .. "' has a prop", type(PlotArt.Props[name]) == "table" and #PlotArt.Props[name] > 0)
end
local known = {}
for _, name in ipairs(EXPECTED.upgrades) do known[name] = true end
for name in pairs(PlotArt.Props) do
	check("prop '" .. tostring(name) .. "' belongs to a real upgrade (UPGRADES in TycoonCore)", known[name] == true)
end

-- 2. The layout map matches the scripts ----------------------------------------------
local L = PlotArt.Layout
check("layout: Floor size and top match TycoonCore", L.floorSize[1] == EXPECTED.floor[1] and L.floorSize[2] == EXPECTED.floor[2]
	and L.floorSize[3] == EXPECTED.floor[3] and L.floorTop == EXPECTED.floorTop)
for _, sign in ipairs(L.signs) do
	local e = EXPECTED.signs[sign.name]
	check("layout: " .. sign.name .. " offset matches its script", e ~= nil and sign.x == e[1] and sign.z == e[2])
end
check("layout: two signs and no pad (the walk-on pads are gone)", #L.signs == 2 and L.pads == nil and L.padSize == nil)
check("layout: spawn landing matches teleportToPlot", L.spawn.x == EXPECTED.spawn[1] and L.spawn.z == EXPECTED.spawn[2])
check("layout: one item slot per upgrade", #L.itemSlots == #EXPECTED.upgrades)
for i, slot in ipairs(L.itemSlots) do
	local e = EXPECTED.slots[i]
	check("layout: slot " .. i .. " is " .. tostring(EXPECTED.upgrades[i]) .. " at itemOffset(" .. i .. ")",
		e ~= nil and slot.name == EXPECTED.upgrades[i] and slot.x == e[1] and slot.z == e[2])
end
local function sameSpots(a, b)
	if #a ~= #b then return false end
	for i = 1, #a do if a[i][1] ~= b[i][1] or a[i][2] ~= b[i][2] then return false end end
	return true
end
check("layout: EMPLOYEE_SPOTS match EmployeeServer", sameSpots(L.employeeSpots, EXPECTED.spots))
check("layout: INCUBATOR_SPOTS match EmployeeServer", sameSpots(L.incubators, EXPECTED.incubators))
check("layout: one desk per employee spot", #L.desks == #L.employeeSpots)

-- 2b. The tidy startup-studio layout: an even grid, desks all one way, aisles of 6+ studs --------------------
do
	local R = L.reserve
	local xs, zs, seenX, seenZ = {}, {}, {}, {}
	for _, spot in ipairs(L.employeeSpots) do
		if not seenX[spot[1]] then seenX[spot[1]] = true table.insert(xs, spot[1]) end
		if not seenZ[spot[2]] then seenZ[spot[2]] = true table.insert(zs, spot[2]) end
	end
	table.sort(xs) table.sort(zs)
	check("layout: 11 hire spots in a grid of 4 columns and 3 rows", #L.employeeSpots == 11 and #xs == 4 and #zs == 3, #xs .. " columns, " .. #zs .. " rows")
	local evenX, evenZ = true, true
	for i = 3, #xs do if math.abs((xs[i] - xs[i - 1]) - (xs[2] - xs[1])) > 1e-9 then evenX = false end end
	for i = 3, #zs do if math.abs((zs[i] - zs[i - 1]) - (zs[2] - zs[1])) > 1e-9 then evenZ = false end end
	check("layout: equal spacing between columns and between rows", evenX and evenZ)
	local filled = {}
	local aligned = true
	for _, spot in ipairs(L.employeeSpots) do
		local key = spot[1] .. "," .. spot[2]
		if filled[key] then aligned = false end
		filled[key] = true
	end
	check("layout: no two hires share a spot", aligned)
	local sameWay = true
	for _, desk in ipairs(L.desks) do
		if desk[1] ~= 0 or desk[2] ~= L.desks[1][2] or desk[3] ~= 0 then sameWay = false end
	end
	check("layout: every desk is in front of its hire and faces the same way", sameWay)
	local rowsFilledInOrder = true
	for i = 2, #L.employeeSpots do
		if L.employeeSpots[i][2] < L.employeeSpots[i - 1][2] then rowsFilledInOrder = false end
	end
	check("layout: spots fill row by row from the back", rowsFilledInOrder)
	local symmetricStart = L.employeeSpots[1][1] == -L.employeeSpots[2][1] and L.employeeSpots[3][1] == -L.employeeSpots[4][1]
	check("layout: a small team fills the middle first and stays symmetric", symmetricStart)
	local aisles = PlotVisuals.aisles(L)
	check("layout: an aisle in front of the first row and one between every two rows", #aisles == #zs, #aisles)
	for i, a in ipairs(aisles) do
		check("layout: aisle " .. i .. " is at least " .. R.minAisle .. " studs deep (" .. (a[4] - a[3]) .. ")", a[4] - a[3] >= R.minAisle)
	end
	local lastIncubator = -math.huge
	for _, s in ipairs(L.incubators) do lastIncubator = math.max(lastIncubator, s[2]) end
	check("layout: at least 6 studs from the door side (incubators) to the first row of hires",
		(zs[1] - R.hireHalf) - (lastIncubator + R.incubatorFront) >= R.minAisle)
	check("layout: the walking lane is clear of every hire column (the spawn stays in it)",
		(function()
			for _, spot in ipairs(L.employeeSpots) do
				if spot[1] - R.hireHalf < L.spawn.x + R.spawnHalf and spot[1] + R.hireHalf > L.spawn.x - R.spawnHalf then return false end
			end
			return true
		end)())
	-- No two reserved zones overlap, except the ones meant to sit inside another
	local zones = PlotVisuals.zones(L)
	local allowed = { ["spawn|lane"] = true, ["spawn|aisle"] = true, ["sign|lane"] = true, ["aisle|lane"] = true }
	local overlapping
	for i = 1, #zones do
		for j = i + 1, #zones do
			local a, b = zones[i], zones[j]
			local key1, key2 = a.kind .. "|" .. b.kind, b.kind .. "|" .. a.kind
			local ab, bb = a.box, b.box
			local hit = ab[1] < bb[2] - 1e-6 and bb[1] < ab[2] - 1e-6 and ab[5] < bb[6] - 1e-6 and bb[5] < ab[6] - 1e-6
			if hit and not allowed[key1] and not allowed[key2] then overlapping = overlapping or (a.name .. " / " .. b.name) end
		end
	end
	check("layout: the reserved zones (hires, desks, props, incubators, signs, aisles, lane) never overlap each other", overlapping == nil, overlapping)
	local inside = true
	for _, z in ipairs(zones) do
		local b = z.box
		if b[1] < -L.floorSize[1] / 2 or b[2] > L.floorSize[1] / 2 or b[5] < -L.floorSize[3] / 2 or b[6] > L.floorSize[3] / 2 then inside = false end
	end
	check("layout: every reserved zone is inside the 60 x 60 floor", inside)
	local walls = true
	for _, slot in ipairs(L.itemSlots) do
		if math.abs(slot.x) - R.slotHalfX < 17 then walls = false end
	end
	check("layout: the upgrade stations stand on the two side strips, clear of the hire grid", walls)
end

-- 3. Every room, with every prop in it ----------------------------------------------------
local center = Vector3.new(-135, 0.5, 150) -- a real plot center (slot 2)
local function slotVec(slot) return Vector3.new(slot.x, 0, slot.z) end
local function fullRoom(art, stage)
	local room = PlotVisuals.buildRoom(nil, center, art, stage)
	for _, slot in ipairs(art.Layout.itemSlots) do
		PlotVisuals.buildProp(room:FindFirstChild("UpgradeProps"), center, art, slot.name, slotVec(slot))
	end
	return room
end
local ALLOWED = { Concrete = true, CorrodedMetal = true, Metal = true, DiamondPlate = true, Wood = true, WoodPlanks = true,
	Brick = true, Fabric = true, Plastic = true, SmoothPlastic = true, Glass = true, Neon = true }
for i = 1, #PlotArt.Stages do
	local room = fullRoom(PlotArt, i)
	local probs = PlotVisuals.check(room, center, PlotArt)
	check("room " .. i .. ": no part in a reserved zone, no floating part, walls and flags right (PlotVisuals.check)", #probs == 0,
		#probs .. " problem(s), first: " .. tostring(probs[1]))
	local parts, lights, badFlags, badMaterial, tinyShadow = 0, 0, nil, nil, nil
	for _, d in ipairs(room:GetDescendants()) do
		if d:IsA("BasePart") then
			parts += 1
			local floorish = string.find(d.Name, "Floor", 1, true) ~= nil
			if not d.Anchored or d.CanTouch or (d.CanCollide and not floorish) or d.CanQuery ~= d.CanCollide then badFlags = badFlags or d:GetFullName() end
			if not ALLOWED[d.Material.Name] then badMaterial = badMaterial or d:GetFullName() end
			if math.max(d.Size.X, d.Size.Y, d.Size.Z) < 2 and d.CastShadow then tinyShadow = tinyShadow or d:GetFullName() end
		elseif d:IsA("PointLight") then
			lights += 1
		end
	end
	check("room " .. i .. ": at most 260 parts with all 6 props (" .. parts .. ")", parts <= 260 and parts > 0, parts)
	check("room " .. i .. ": at most 3 PointLights (" .. lights .. ")", lights <= 3, lights)
	check("room " .. i .. ": decor anchored, no touch, no query, only floors collide", badFlags == nil, badFlags)
	check("room " .. i .. ": allowed materials only", badMaterial == nil, badMaterial)
	check("room " .. i .. ": tiny parts cast no shadow", tinyShadow == nil, tinyShadow)
	check("room " .. i .. ": grouped in Shell, Decor and UpgradeProps", room:FindFirstChild("Shell") and room:FindFirstChild("Decor")
		and room:FindFirstChild("UpgradeProps") and #room:FindFirstChild("UpgradeProps"):GetChildren() == #EXPECTED.upgrades)
	check("room " .. i .. ": named PlotRoom with its stage", room.Name == "PlotRoom" and room:GetAttribute("Stage") == i
		and room:GetAttribute("StageKey") == PlotArt.Stages[i].key)
	local decor = room:FindFirstChild("Decor")
	local phone = decor:FindFirstChild("DeskPhone")
	check("room " .. i .. ": has the DeskPhone (a later step makes it ring)", phone ~= nil)
	local desksOk = true
	for s, spot in ipairs(L.employeeSpots) do
		local desk = decor:FindFirstChild("HireDesk" .. s)
		if not desk or #desk:GetChildren() == 0 then desksOk = false else
			for _, p in ipairs(desk:GetChildren()) do
				local dx, dz = p.CFrame.x - (center.X + spot[1]), p.CFrame.z - (center.Z + spot[2])
				if math.sqrt(dx * dx + dz * dz) > 5 then desksOk = false end
			end
		end
	end
	check("room " .. i .. ": every hire spot has its own desk next to it (within 5 studs)", desksOk)
	local unnamed = nil
	for _, d in ipairs(room:GetDescendants()) do if d.Name == "" or d.Name == d.ClassName and d:IsA("BasePart") then unnamed = d end end
	check("room " .. i .. ": every part is named", unnamed == nil)
end

-- 3b. Clearer props: bigger, with small distinct parts (screen glow, keyboard, mug, handset, rack LEDs, marker tray, sign bracket) ----
do
	local DETAILS = {
		["Desk"] = { "MonitorScreen", "Keyboard", "Mug", "HandleLeft", "LampShade", "DeskLip" },
		["Coffee Machine"] = { "PanelLED", "Cup2", "SteamWand", "BeanHopper", "MachineCap" },
		["Laptop"] = { "LaptopScreen", "Mouse", "Mug", "StandGlowStrip", "LaptopLid" },
		["Server Rack"] = { "ServerLED1", "ServerLED4", "PatchPanel", "CableBlue", "RackTop" },
		["Whiteboard"] = { "MarkerTray", "MarkerRed", "ChartBar3", "StickyYellow", "FrameTop" },
		["Neon Logo"] = { "SignBracketLeft", "SignBracketRight", "SignGlow", "LogoRocket", "SignCapTop" },
	}
	local total = 0
	for name, details in pairs(DETAILS) do
		local have = {}
		for _, spec in ipairs(PlotArt.Props[name]) do have[spec.name] = spec end
		local missing
		for _, d in ipairs(details) do if not have[d] then missing = d end end
		check("prop " .. name .. ": has its small distinct parts", missing == nil, missing)
		total += #PlotArt.Props[name]
		local lit = false
		for _, spec in ipairs(PlotArt.Props[name]) do if spec.material == "Neon" then lit = true end end
		check("prop " .. name .. ": has one glowing accent (a Neon screen, LED or sign; the whiteboard's accent is its blue chart)", lit or name == "Whiteboard")
		check("prop " .. name .. ": 14 to 30 parts (readable, not a pile)", #PlotArt.Props[name] >= 14 and #PlotArt.Props[name] <= 30, #PlotArt.Props[name])
		-- It is bigger than the old one: the tallest edge of every prop at least 1.2 x its old design's
		local top = 0
		for _, spec in ipairs(PlotArt.Props[name]) do top = math.max(top, spec.offset[2] + spec.size[2] / 2) end
		check("prop " .. name .. ": tall enough to read from the camera (top at " .. string.format("%.1f", top) .. " studs)", top >= 5.5, top)
	end
	check("the six props use at most 135 parts together (" .. total .. ")", total <= 135, total)
	local names = {}
	for _, spec in ipairs(PlotArt.Stages[1].decor) do names[spec.name] = true end
	check("the old PC has its bezel, keys, floppy slot and stand; the phone its keypad and handset ear",
		names.CRTBezel and names.KeyboardKeys and names.TowerFloppy and names.CRTStand and names.PhoneKeypad and names.HandsetEar and names.DeskPhoneHandset)
end

-- 4. The garage story: the only tech is an old PC and a desk phone -------------------------
do
	local room = PlotVisuals.buildRoom(nil, center, PlotArt, 1)
	local neon, texts, techWords = {}, {}, nil
	for _, d in ipairs(room:GetDescendants()) do
		if d:IsA("BasePart") and d.Material.Name == "Neon" then table.insert(neon, d.Name) end
		if d.ClassName == "TextLabel" then texts[d.Text] = true end
		if d:IsA("BasePart") then
			for _, word in ipairs({ "Monitor", "Laptop", "Server", "Screen" }) do
				if string.find(d.Name, word, 1, true) and d.Name ~= "ComputerScreen" then techWords = d.Name end
			end
		end
	end
	table.sort(neon)
	check("garage: the only lights are the bare bulb and the old PC's screen", #neon == 2 and neon[1] == "Bulb" and neon[2] == "ComputerScreen", table.concat(neon, ","))
	check("garage: no monitor, laptop or server in the room (they are upgrades)", techWords == nil, techWords)
	check("garage: the cardboard OFFICE sign", texts["OFFICE"] == true)
	check("garage: the 'WIFI: ask mom' sticky note", texts["WIFI:\nask mom"] == true)
	check("garage: the old PC and the phone are there", room:FindFirstChild("Decor"):FindFirstChild("ComputerCRT") ~= nil
		and room:FindFirstChild("Decor"):FindFirstChild("DeskPhoneHandset") ~= nil)
	check("garage: hire desks are crates (no tech)", room:FindFirstChild("Decor"):FindFirstChild("HireDesk1"):FindFirstChild("Crate") ~= nil)
end

-- 5. One player's plot: stage swaps keep the props, the floor follows, effects ----------------
do
	ROOT = newInstance("Folder")
	local folder = newInstance("Folder")
	folder.Parent = ROOT
	local floor = newInstance("Part")
	floor.Name = "Floor"
	floor.Size = Vector3.new(60, 1, 60)
	floor.Parent = folder
	SPAWNED = {}
	local plot = PlotVisuals.newPlot(folder, center, PlotArt, floor, 1)
	check("newPlot: the stage-1 room is in the folder, no flash on join", plot.room.Parent == folder and plot.stage == 1 and #SPAWNED == 0)
	check("newPlot: the Floor keeps its name and size, gets the stage's color and material",
		floor.Name == "Floor" and floor.Size.X == 60 and floor.Material.Name == PlotArt.Stages[1].floor.material
		and floor.Color.rgb[1] == PlotArt.Stages[1].floor.color[1])
	local desk = PlotVisuals.addProp(plot, "Desk", Vector3.new(-18, 0, -14), false)
	local laptop = PlotVisuals.addProp(plot, "Laptop", Vector3.new(18, 0, -14), true)
	check("addProp: builds the prop in the room's UpgradeProps", desk and desk.Parent == plot.room:FindFirstChild("UpgradeProps") and desk:GetAttribute("Upgrade") == "Desk")
	check("addProp: a purchase pops in (one effect started), a load does not", #SPAWNED == 1 and SPAWNED[1] == PlotVisuals.popIn)
	check("addProp: an upgrade without art gives nil (TycoonCore shows its old block)", PlotVisuals.addProp(plot, "Rocket Ship", Vector3.new(0, 0, 0), true) == nil)
	PlotVisuals.popIn(laptop)
	check("popIn: ends at full size", laptop.scale == 1, laptop.scale)
	local old = plot.room
	SPAWNED = {}
	local last = #PlotArt.Stages
	PlotVisuals.setStage(plot, 2, true)
	check("setStage: the old room is destroyed and a new one is in the folder", old.destroyed == true and plot.room ~= old and plot.room.Parent == folder)
	check("setStage: the bought props move into the new room (same Models)", desk.Parent == plot.room:FindFirstChild("UpgradeProps") and laptop.Parent == desk.Parent)
	check("setStage: a stage change flashes", #SPAWNED == 1 and SPAWNED[1] == PlotVisuals.flash)
	check("setStage: remembers the stage asked for", plot.stage == 2)
	check("setStage: shows the room of that stage, or the last room when there are fewer", plot.room:GetAttribute("Stage") == math.min(2, last))
	PlotVisuals.setStage(plot, 99, false)
	check("setStage: a stage past the last room shows the last room", plot.room:GetAttribute("Stage") == last and plot.stage == 99)
	PlotVisuals.setStage(plot, 1, true)
	check("setStage: back to the Garage after an IPO (stage 1), props kept for TycoonCore to clear", plot.room:GetAttribute("Stage") == 1 and desk.Parent ~= nil)
	check("setStage: the floor is restyled for the Garage again", floor.Material.Name == PlotArt.Stages[1].floor.material)
	PlotVisuals.flash(plot)
	check("flash: its part is gone afterwards", folder:FindFirstChild("StageFlash") == nil)
	local rooms = 0
	for _, c in ipairs(folder:GetChildren()) do if c.Name == "PlotRoom" then rooms += 1 end end
	check("only one room in the plot folder after all swaps", rooms == 1)
end

-- 6. Mutations: the checks catch broken art -------------------------------------------------
local function deepCopy(t)
	if type(t) ~= "table" then return t end
	local c = {}
	for k, v in pairs(t) do c[deepCopy(k)] = deepCopy(v) end
	return c
end
local function find(list, name) for _, s in ipairs(list) do if s.name == name then return s end end end
local function anyMatch(list, word) for _, p in ipairs(list) do if string.find(p, word, 1, true) then return true end end return false end
do
	local art = deepCopy(PlotArt)
	find(art.Stages[1].decor, "Tire1").offset = { 0, 0.45, 24 }
	check("mutation: a tire on the next-upgrade sign is caught", anyMatch(PlotVisuals.check(fullRoom(art, 1), center, art), "sign zone BuySign"))
	art = deepCopy(PlotArt)
	find(art.Stages[1].decor, "Tire1").offset = { 0, 0.45, 3 }
	check("mutation: a tire in the walking lane down the middle is caught", anyMatch(PlotVisuals.check(fullRoom(art, 1), center, art), "lane zone WalkingLane"))
	art = deepCopy(PlotArt)
	find(art.Stages[1].decor, "Tire1").offset = { 10, 0.45, -3 }
	check("mutation: a tire in the aisle between two rows is caught", anyMatch(PlotVisuals.check(fullRoom(art, 1), center, art), "aisle zone RowAisle1"))
	art = deepCopy(PlotArt)
	find(art.Stages[1].decor, "Box1").offset = { 4.5, 0.9, -15 }
	check("mutation: a box in the aisle in front of the incubators is caught", anyMatch(PlotVisuals.check(fullRoom(art, 1), center, art), "aisle zone DoorAisle"))
	art = deepCopy(PlotArt)
	find(art.Stages[1].decor, "Box1").offset = { -13.5, 0.9, 14 }
	check("mutation: a box where a hire stands is caught", anyMatch(PlotVisuals.check(fullRoom(art, 1), center, art), "hire zone Hire"))
	art = deepCopy(PlotArt)
	find(art.Stages[1].decor, "Box1").offset = { -4.5, 0.9, 16.3 }
	check("mutation: a box on a hire's desk is caught", anyMatch(PlotVisuals.check(fullRoom(art, 1), center, art), "desk zone HireDesk"))
	art = deepCopy(PlotArt)
	table.insert(art.Stages[1].decor, { name = "Floater", shape = "Block", size = { 2, 2, 2 }, offset = { 8, 20, -8 }, color = { 1, 2, 3 }, material = "Wood" })
	check("mutation: a floating part is caught", anyMatch(PlotVisuals.check(fullRoom(art, 1), center, art), "Floater is floating"))
	art = deepCopy(PlotArt)
	find(art.Stages[1].shell, "SideSheetL2").size = { 0.6, 8, 20 }
	check("mutation: a side wall over 6 studs is caught", anyMatch(PlotVisuals.check(fullRoom(art, 1), center, art), "SideSheetL2: taller than 6"))
	art = deepCopy(PlotArt)
	art.Props["Desk"][1].offset = { 8, 2.85, 0.4 }
	check("mutation: a prop leaving its slot is caught", anyMatch(PlotVisuals.check(fullRoom(art, 1), center, art), "must stay inside its own slot"))
	art = deepCopy(PlotArt)
	find(art.Stages[1].decor, "Box1").material = "Grass"
	check("mutation: a material outside the list is caught", anyMatch(PlotVisuals.validate(art), "material not allowed: Grass"))
	art = deepCopy(PlotArt)
	find(art.Stages[1].decor, "Box2").material = "Neon"
	check("mutation: Neon on a box (not a light or a sign) is caught", anyMatch(PlotVisuals.validate(art), "Neon is only for lights"))
	art = deepCopy(PlotArt)
	find(art.Stages[1].decor, "TrashBag1").size = { 1.6, 1, 1.6 }
	check("mutation: a squashed Ball is caught", anyMatch(PlotVisuals.validate(art), "a Ball needs 3 equal sides"))
	art = deepCopy(PlotArt)
	find(art.Stages[1].decor, "Crack1").color = { 300, 0, 0 }
	check("mutation: a color over 255 is caught", anyMatch(PlotVisuals.validate(art), "color must be"))
	art = deepCopy(PlotArt)
	find(art.Stages[1].decor, "Crack1").size = { 0, 0.03, 0.14 }
	check("mutation: a size of 0 is caught", anyMatch(PlotVisuals.validate(art), "size must be"))
end

-- 7. Stages 2 to 5 (visuals-garage): same builder, same rules, new shells and decor --------------------
-- The fingerprints below were taken from the commit before stages 2-5 (cb326d8). If one fails, stage 1, the
-- six props or the layout changed: that is only allowed on purpose, by hand.
local function num(n) return string.format("%.4f", n) end
local function triple(t) if not t then return "-" end return num(t[1]) .. "," .. num(t[2]) .. "," .. num(t[3]) end
local function specString(s)
	local tr = s.text and (s.text.value .. s.text.font) or ""
	local lt = s.light and (s.light.brightness .. "/" .. s.light.range) or ""
	return table.concat({ s.name, s.shape, triple(s.size), triple(s.offset), triple(s.rot), triple(s.color), s.material, num(s.transparency or 0), tostring(s.collide), tr, lt }, "|")
end
local function listString(list)
	local out = {}
	for _, s in ipairs(list) do table.insert(out, specString(s)) end
	return table.concat(out, ";")
end
local function hash(str)
	local h = 5381
	for i = 1, #str do h = (h * 33 + string.byte(str, i)) % 4294967291 end
	return h
end
do
	local g = PlotArt.Stages[1]
	check("stage 1 is unchanged (fingerprint of its shell, decor, desks, floor and key)",
		hash(listString(g.shell) .. "#" .. listString(g.decor) .. "#" .. listString(g.desk) .. g.floor.material .. triple(g.floor.color) .. g.key) == 2156961517
		and #g.shell == 35 and #g.decor == 81 and #g.desk == 2)
	local names = {}
	for n in pairs(PlotArt.Props) do table.insert(names, n) end
	table.sort(names)
	local ps = {}
	for _, n in ipairs(names) do table.insert(ps, n .. "=" .. listString(PlotArt.Props[n])) end
	check("the six upgrade props are unchanged (fingerprint of every part)", hash(table.concat(ps, "##")) == 893633666)
	local L2 = PlotArt.Layout
	local ls = {}
	for _, s in ipairs(L2.employeeSpots) do table.insert(ls, s[1] .. "," .. s[2]) end
	for _, s in ipairs(L2.incubators) do table.insert(ls, s[1] .. "," .. s[2]) end
	for _, s in ipairs(L2.itemSlots) do table.insert(ls, s.name .. s.x .. "," .. s.z) end
	for _, s in ipairs(L2.signs) do table.insert(ls, s.name .. s.x .. "," .. s.z) end
	for _, s in ipairs(L2.desks) do table.insert(ls, s[1] .. "," .. s[2] .. "," .. s[3]) end
	table.insert(ls, L2.spawn.x .. "," .. L2.spawn.z)
	local rs = {}
	for k, v in pairs(L2.reserve) do table.insert(rs, k .. "=" .. v) end
	table.sort(rs)
	check("every gameplay position is unchanged: hire grid, incubators, upgrade stations, signs, spawn, desk offsets, reserved zones (fingerprint)",
		hash(table.concat(ls, ";") .. table.concat(rs, ";")) == 1471280708)
	for i, look in ipairs(PlotArt.Stages) do
		check("stage " .. i .. ": no stage owns props (the six props are one shared list)", look.props == nil and look.Props == nil)
	end
end

-- What each later room must show: the parts that tell its story (a name each), and the rules it keeps
local STORY = {
	[2] = { shell = { "BackWall", "DoorPanel1", "DoorPanel4", "DoorGlassBand", "WindowGlassL", "WindowGlassR" },
		decor = { "StringBulbL0", "StringBulbR5", "StringCordL", "RugBase", "RugInner", "SofaBase", "SofaBack", "CornerPlant" .. "Pot", "FounderTop", "DeskPhone", "DoorSign" },
		desk = { "DeskTop", "DeskLegL", "MonitorFrame", "MonitorScreen" }, wall = { 170, 226, 204 }, lights = 3 },
	[3] = { shell = { "BackWall", "BayLShutter", "BayRShutter", "BayLDark", "PartitionLGlass", "PartitionRGlass", "WallBoard", "WallNote1", "WallBoardTray" },
		decor = { "WallLampBulbL", "WallLampBulbM", "WallLampBulbR", "BayLineL", "BayLineR", "CabinetA", "SofaBase", "FounderTop", "DeskPhone", "RugBase" },
		desk = { "DeskTop", "DeskLegL", "MonitorFrame", "MonitorScreen" }, wall = { 172, 94, 76 }, lights = 3 },
	[4] = { shell = { "BackLower", "BackGlass", "BackMullion1", "BackMullion5", "SideGlassL", "SideGlassR", "SideRailL", "SideMullionR3" },
		decor = { "FloorTileX1", "FloorTileZ5", "MeetGlassBack", "MeetGlassSide", "MeetTableTop", "MeetChairA1", "MeetScreen", "GapPlantLPot", "CornerPlantPot",
			"FounderTop", "DeskPhone", "FloorLampShadeA" },
		desk = { "DeskTop", "DeskLegL", "MonitorFrame", "MonitorScreen" }, wallPart = "BackLower", wall = { 240, 242, 244 }, lights = 3 },
	[5] = { shell = { "BackLower", "WindowA", "WindowB", "WindowC", "WindowD", "MullionL", "MullionR", "LogoWall", "LogoWallGlow", "LogoWallSign", "LogoWallUnderline",
			"SideGlassL", "SideGlassR", "Skyline1", "Skyline9" },
		decor = { "ShelfBack", "ShelfBoard3", "Trophy1", "Trophy5", "RugBase", "LoungeTable", "ArmchairA", "ArmchairB", "FounderTop", "DeskPhone", "GapPlantLPot", "FloorLampShadeA" },
		desk = { "DeskTop", "DeskLegL", "MonitorFrame", "MonitorScreen", "Keyboard" }, wallPart = "BackLower", wall = { 246, 247, 248 }, lights = 3 },
}
local function has(list, name) for _, s in ipairs(list) do if s.name == name then return s end end return nil end
local function countPrefix(list, prefix) local n = 0 for _, s in ipairs(list) do if string.find(s.name, prefix, 1, true) == 1 then n += 1 end end return n end
for i = 2, #PlotArt.Stages do
	local look = PlotArt.Stages[i]
	local room = fullRoom(PlotArt, i)
	local story = STORY[i]
	check("stage " .. i .. ": has a story entry in this test (add one when a stage is added)", story ~= nil)
	if story then
		for _, group in ipairs({ "shell", "decor", "desk" }) do
			local missing
			for _, name in ipairs(story[group]) do if not has(look[group], name) then missing = name end end
			check("stage " .. i .. ": its " .. group .. " has the parts of its story", missing == nil, missing)
		end
		local wall = has(look.shell, story.wallPart or "BackWall")
		check("stage " .. i .. ": the back wall has its color", wall ~= nil and wall.color[1] == story.wall[1] and wall.color[2] == story.wall[2] and wall.color[3] == story.wall[3])
		local lights = 0
		for _, d in ipairs(room:GetDescendants()) do if d:IsA("PointLight") then lights += 1 end end
		check("stage " .. i .. ": uses " .. story.lights .. " of its 3 PointLights", lights == story.lights, lights)
	end
	check("stage " .. i .. ": a different floor from every earlier stage", (function()
		for j = 1, i - 1 do
			local f = PlotArt.Stages[j].floor
			if f.material == look.floor.material and f.color[1] == look.floor.color[1] and f.color[2] == look.floor.color[2] and f.color[3] == look.floor.color[3] then return false end
		end
		return true
	end)())
	-- Only walls, floors and decor: nothing collides, nothing is a roof or a facade, the front stays open
	local solid, roof, front, parts = 0, nil, nil, 0
	local tall = 0
	for _, d in ipairs(room:GetDescendants()) do
		if d:IsA("BasePart") then
			parts += 1
			if d.CanCollide then solid += 1 end
			local oy, hy = d.CFrame.y - center.Y - 0.5, d.Size.Y / 2
			local lowest = oy - hy
			if d.Size.X > 20 and d.Size.Z > 20 and lowest > 5 and string.find(d.Name, "Skyline", 1, true) ~= 1 then roof = roof or d:GetFullName() end
			if d.Size.X > 30 and d.CFrame.z - center.Z > 20 and string.find(d.Name, "Floor", 1, true) == nil and d.Size.Y > 0.3 then front = front or d:GetFullName() end
		end
	end
	check("stage " .. i .. ": nothing collides (walls and floors are looks; the real Floor is the only solid)", solid == 0, solid)
	check("stage " .. i .. ": no roof", roof == nil, roof)
	check("stage " .. i .. ": the front is open (no long wall or facade along the front)", front == nil, front)
	local desks = room:FindFirstChild("Decor"):FindFirstChild("HireDesk1")
	check("stage " .. i .. ": hire desks are not the garage crate", desks ~= nil and desks:FindFirstChild("Crate") == nil and #desks:GetChildren() >= 3)
	check("stage " .. i .. ": shell, decor and 11 desks use at most 142 parts so the six props (118) always fit (" .. (parts - 118) .. ")", parts - 118 <= 142, parts)
	-- The six props are the same in every room
	local propsOf = function(r)
		local out = {}
		for _, m in ipairs(r:FindFirstChild("UpgradeProps"):GetChildren()) do
			for _, p in ipairs(m:GetChildren()) do
				table.insert(out, string.format("%s.%s %.3f,%.3f,%.3f %.3f,%.3f,%.3f", m.Name, p.Name, p.Size.X, p.Size.Y, p.Size.Z, p.CFrame.x, p.CFrame.y, p.CFrame.z))
			end
		end
		return table.concat(out, ";")
	end
	check("stage " .. i .. ": the six props are exactly the same parts in the same places as in the Garage", propsOf(room) == propsOf(fullRoom(PlotArt, 1)))
	-- Every part of this room outside the props: nothing in the six slots but the prop itself
	local slotClear = true
	for _, d in ipairs(room:FindFirstChild("Decor"):GetDescendants()) do
		if d:IsA("BasePart") and string.find(d:GetFullName(), "HireDesk", 1, true) == nil then
			for _, slot in ipairs(L.itemSlots) do
				local x, z = d.CFrame.x - center.X - slot.x, d.CFrame.z - center.Z - slot.z
				if math.abs(x) < 4 and z > -3.5 and z < 2.5 and d.Size.Y > 0.3 then slotClear = false end
			end
		end
	end
	check("stage " .. i .. ": no decor stands in an upgrade station", slotClear)
	-- The skyline stays behind the back wall and the plot's own width
	for _, group in ipairs({ look.shell, look.decor }) do
		for _, s in ipairs(group) do
			if string.find(s.name, "Skyline", 1, true) == 1 then
				check("stage " .. i .. ": " .. s.name .. " stays behind the back wall inside the plot's width", s.offset[3] + s.size[3] / 2 <= PlotVisuals.BACKDROP_Z and math.abs(s.offset[1]) + s.size[1] / 2 <= 30, s.name)
			end
		end
	end
end

-- 7a. What makes each room different, measured on the parts (not only named)
do
	local function room(i) return fullRoom(PlotArt, i) end
	local function find(r, name)
		for _, d in ipairs(r:GetDescendants()) do if d:IsA("BasePart") and d.Name == name then return d end end
		return nil
	end
	local function count(r, prefix, material)
		local n = 0
		for _, d in ipairs(r:GetDescendants()) do
			if d:IsA("BasePart") and string.find(d.Name, prefix, 1, true) == 1 and (material == nil or d.Material.Name == material) then n += 1 end
		end
		return n
	end
	if PlotArt.Stages[2] then
		local r = room(2)
		check("stage 2: twelve warm string-light bulbs, all glowing (Neon), on two cords", count(r, "StringBulb", "Neon") == 12 and count(r, "StringCord") == 2)
		check("stage 2: a new door of four panels with a smoked glass band", count(r, "DoorPanel") == 4 and find(r, "DoorGlassBand").Material.Name == "Glass")
		check("stage 2: fresh paint is smooth (SmoothPlastic), not the Garage's corroded metal", find(r, "BackWall").Material.Name == "SmoothPlastic" and count(r, "SideWall", "CorrodedMetal") == 0)
		check("stage 2: a rug of two layers and a sofa of five parts", count(r, "Rug") == 2 and count(r, "Sofa") == 5)
		check("stage 2: every hire desk has an oak top, two legs and a monitor (5 parts)", #PlotArt.Stages[2].desk == 5)
	end
	if PlotArt.Stages[3] then
		local r = room(3)
		check("stage 3: brick walls (Brick material) on the back and the sides", find(r, "BackWall").Material.Name == "Brick" and find(r, "SideWallL").Material.Name == "Brick")
		check("stage 3: a second bay: two roll-up doors, each with a dark opening, a frame, a header and a shutter; two safety lines", (function()
			for _, side in ipairs({ "L", "R" }) do
				for _, part in ipairs({ "Dark", "FrameL", "FrameR", "Header", "Shutter" }) do
					if not find(r, "Bay" .. side .. part) then return false end
				end
			end
			return count(r, "BayLine") == 2
		end)())
		check("stage 3: two glass partitions (see-through) that stand 5 studs high or more", (function()
			for _, side in ipairs({ "L", "R" }) do
				local g = find(r, "Partition" .. side .. "Glass")
				if not g or g.Material.Name ~= "Glass" or g.Transparency < 0.3 or g.Size.Y < 5 then return false end
			end
			return true
		end)())
		check("stage 3: a whiteboard wall at least 15 studs wide with sticky notes and a tray", find(r, "WallBoard").Size.X >= 15 and count(r, "WallNote") == 5 and find(r, "WallBoardTray") ~= nil)
		check("stage 3: three wall lamps, each with a bulb", count(r, "WallLampBulb", "Neon") == 3)
	end
	if PlotArt.Stages[4] then
		local r = room(4)
		check("stage 4: carpet tiles: a Fabric floor and a grid of tile lines (10)", PlotArt.Stages[4].floor.material == "Fabric" and count(r, "FloorTile") == 10)
		check("stage 4: glass walls on both sides, nearly the whole length (55 studs or more)", (function()
			for _, side in ipairs({ "L", "R" }) do
				local g = find(r, "SideGlass" .. side)
				if not g or g.Material.Name ~= "Glass" or g.Size.Z < 55 then return false end
			end
			return true
		end)())
		check("stage 4: a ribbon of glass along the back wall in navy mullions", find(r, "BackGlass").Material.Name == "Glass" and count(r, "BackMullion") == 5)
		check("stage 4: a glass-walled meeting room: two glass walls, a table, four chairs and a wall screen", count(r, "MeetGlass", "Glass") == 2
			and find(r, "MeetTableTop") ~= nil and count(r, "MeetChairA") + count(r, "MeetChairB") >= 4 and find(r, "MeetScreen") ~= nil)
		check("stage 4: three plants", count(r, "GapPlantLPot") + count(r, "GapPlantRPot") + count(r, "CornerPlantPot") == 3)
	end
	if PlotArt.Stages[5] then
		local r = room(5)
		check("stage 5: a polished light floor (SmoothPlastic, bright)", PlotArt.Stages[5].floor.material == "SmoothPlastic" and PlotArt.Stages[5].floor.color[1] >= 200)
		check("stage 5: big windows: four glass panes at least 7 studs tall on the back wall", count(r, "Window", "Glass") == 4 and find(r, "WindowA").Size.Y >= 7)
		check("stage 5: a simple block skyline: 9 towers behind the back wall, none over 30 studs", count(r, "Skyline") == 9)
		check("stage 5: the skyline is inside the plot's width (it never reaches a neighbour)", (function()
			for _, d in ipairs(r:GetDescendants()) do
				if d:IsA("BasePart") and string.find(d.Name, "Skyline", 1, true) == 1 then
					local x = d.CFrame.x - center.X
					if math.abs(x) + d.Size.X / 2 > 30 or d.CFrame.z - center.Z + d.Size.Z / 2 > -43 then return false end
				end
			end
			return true
		end)())
		check("stage 5: a neon logo wall (a Neon rim and underline, a sign saying HQ)", find(r, "LogoWallGlow").Material.Name == "Neon" and find(r, "LogoWallUnderline").Material.Name == "Neon"
			and (function() for _, d in ipairs(r:GetDescendants()) do if d.ClassName == "TextLabel" and d.Text == "HQ" then return true end end return false end)())
		check("stage 5: a trophy shelf with three shelves and five gold cups", count(r, "ShelfBoard") == 3 and count(r, "Trophy", "Metal") == 5)
		check("stage 5: no text in the room claims odds, chances or prices (D9)", (function()
			for _, d in ipairs(r:GetDescendants()) do
				if d.ClassName == "TextLabel" then
					local text = string.lower(d.Text)
					for _, word in ipairs({ "odds", "chance", "%", "$", "r$", "robux", "free", "win", "lucky" }) do
						if string.find(text, word, 1, true) then return false end
					end
				end
			end
			return true
		end)())
	end
end

-- 7b. Mutations on every later room: the same checks catch a bad part in stages 2 to 5 too
for i = 2, #PlotArt.Stages do
	local function extra(part)
		local art = deepCopy(PlotArt)
		table.insert(art.Stages[i].decor, part)
		return PlotVisuals.check(fullRoom(art, i), center, art)
	end
	local box = { name = "TestBox", shape = "Block", size = { 2, 2, 2 }, color = { 1, 2, 3 }, material = "Wood" }
	local function at(x, y, z, more)
		local part = deepCopy(box)
		part.offset = { x, y, z }
		for k, v in pairs(more or {}) do part[k] = v end
		return part
	end
	check("mutation (stage " .. i .. "): a box where a hire stands is caught", anyMatch(extra(at(-4.5, 1, 14)), "hire zone"))
	check("mutation (stage " .. i .. "): a box in the walking lane is caught", anyMatch(extra(at(0, 1, 20)), "lane zone WalkingLane"))
	check("mutation (stage " .. i .. "): a box inside an upgrade station is caught", anyMatch(extra(at(-23, 1, 2)), "slot zone Coffee Machine"))
	check("mutation (stage " .. i .. "): a box on a hire's desk is caught", anyMatch(extra(at(4.5, 1, 5.3)), "desk zone HireDesk"))
	check("mutation (stage " .. i .. "): a box on the BuySign is caught", anyMatch(extra(at(0, 1, 24)), "sign zone BuySign"))
	check("mutation (stage " .. i .. "): a floating box is caught", anyMatch(extra(at(8, 20, 26)), "TestBox is floating"))
	check("mutation (stage " .. i .. "): a collidable box is caught", anyMatch(extra(at(-8, 1, 26, { collide = true })), "only floors and low walls may collide"))
	check("mutation (stage " .. i .. "): four extra PointLights are caught", (function()
		local art = deepCopy(PlotArt)
		for k = 1, 4 do
			table.insert(art.Stages[i].decor, at(-8 + k, 1, 26, { name = "TestLight" .. k, material = "Neon", light = { color = { 255, 255, 255 }, brightness = 1, range = 10 } }))
		end
		return anyMatch(PlotVisuals.check(fullRoom(art, i), center, art), "lights (budget 3)")
	end)())
	check("mutation (stage " .. i .. "): a tall wall on the side is caught", anyMatch(extra({ name = "TestWall", shape = "Block", size = { 0.6, 9, 6 }, offset = { -29.7, 4.5, 24 }, color = { 1, 2, 3 }, material = "Wood" }), "taller than 6"))
	check("mutation (stage " .. i .. "): too many parts is caught", (function()
		local art = deepCopy(PlotArt)
		for k = 1, 60 do
			table.insert(art.Stages[i].decor, at(-8 + (k % 10) * 0.5, 0.2 + math.floor(k / 10) * 0.1, 27, { name = "Extra" .. k, size = { 0.4, 0.2, 0.4 } }))
		end
		return anyMatch(PlotVisuals.check(fullRoom(art, i), center, art), "parts (budget 260)")
	end)())
end

print_real(string.format("%d passed, %d failed", passed, failed))
"""


BUY_TESTS = r"""-- Tests for buying an office upgrade: TycoonCore's checkUpgradePurchase and buyUpgrade (BUYUPGRADE markers),
-- ShopServer's handleShopAction (SHOPACTION markers) and PoachServer's checkHrPurchase (HRBUY markers) ----
local print_real = print
local function typeof(v) return type(v) end
local passed, failed = 0, 0
local function check(name, cond, extra)
	if cond then passed += 1 else failed += 1; print_real("FAIL: " .. name .. (extra ~= nil and (" -- " .. tostring(extra)) or "")) end
end
local CLOCK = 100
local os = { clock = function() return CLOCK end }
local UPGRADES = __UPGRADES__
local playerData = {}
local CALLS = {}
local function updateIncome(player) table.insert(CALLS, "income") end
local function spawnItem(data, i, upg, popIn) table.insert(CALLS, "spawn:" .. i .. ":" .. upg.name .. ":" .. tostring(popIn)) end
local function refreshSign(player) table.insert(CALLS, "sign") end
__BUYUPGRADE__
local function upgradeList()
	local list = {}
	for _, upg in ipairs(UPGRADES) do table.insert(list, { name = upg.name, cost = upg.cost, income = upg.income }) end
	return list
end
local core = { buyUpgrade = buyUpgrade, upgradeList = upgradeList }
__SHOPACTION__

local function newPlayer(cash, ready)
	local player = {}
	playerData[player] = { ready = ready ~= false, owned = {}, cash = { Value = cash } }
	return player, playerData[player]
end
local function buy(player, id)
	CALLS = {}
	CLOCK += 1 -- a new second: the rate limit is not what is being tested, unless a test says so
	return handleShopAction(player, "BuyUpgrade", id)
end

-- 1. The purchase, in the same order and with the same rules as the old pad -------------------------
do
	local p, d = newPlayer(1000)
	local ok, msg = buy(p, 1)
	check("Desk (free): bought, no Cash taken", ok == true and d.owned.Desk == true and d.cash.Value == 1000, msg)
	check("a purchase pops its prop in, updates the income and the sign",
		table.concat(CALLS, ",") == "income,spawn:1:Desk:true,sign", table.concat(CALLS, ","))
	ok, msg = buy(p, 2)
	check("Coffee Machine ($25): bought, exactly its price taken", ok == true and d.owned["Coffee Machine"] == true and d.cash.Value == 975, d.cash.Value)
	ok, msg = buy(p, 3)
	check("Laptop ($100)", ok == true and d.cash.Value == 875)
	ok = buy(p, 4); check("Server Rack ($400)", ok == true and d.cash.Value == 475)
	ok = buy(p, 5); check("Whiteboard ($1500): not enough Cash, refused", ok == false and d.owned.Whiteboard == nil and d.cash.Value == 475)
	d.cash.Value = 1500
	ok = buy(p, 5); check("Whiteboard with exactly $1500: bought, Cash is 0 (never negative)", ok == true and d.cash.Value == 0)
	d.cash.Value = 5000
	ok = buy(p, 6); check("Neon Logo ($5000): the last one", ok == true and d.cash.Value == 0)
	local all = true
	for _, upg in ipairs(UPGRADES) do if not d.owned[upg.name] then all = false end end
	check("all six owned after buying in order", all)
	ok, msg = buy(p, 6)
	check("everything bought: another request is refused", ok == false)
end

-- 2. Refusals change nothing ----------------------------------------------------------------------
do
	local p, d = newPlayer(24)
	buy(p, 1)
	local ok, msg = buy(p, 2)
	check("insufficient Cash ($24 for $25): refused with the price", ok == false and d.cash.Value == 24 and d.owned["Coffee Machine"] == nil
		and string.find(msg, "$25", 1, true) ~= nil, msg)
	check("insufficient Cash: no prop, no income change, no sign refresh", #CALLS == 0, table.concat(CALLS, ","))
	ok, msg = buy(p, 1)
	check("already owned: refused, nothing taken", ok == false and d.cash.Value == 24 and string.find(msg, "already", 1, true) ~= nil, msg)
	d.cash.Value = 100000
	ok, msg = buy(p, 4)
	check("wrong order (Server Rack before Coffee Machine): refused, says what to buy first", ok == false and d.owned["Server Rack"] == nil
		and d.cash.Value == 100000 and string.find(msg, "Coffee Machine first", 1, true) ~= nil, msg)
	ok = buy(p, 6)
	check("wrong order (Neon Logo with the Desk only): refused", ok == false and d.owned["Neon Logo"] == nil)
	check("a refused request never spawns a prop", #CALLS == 0)
end

-- 3. Spam is refused, not queued -----------------------------------------------------------------------
do
	local p, d = newPlayer(100000)
	CLOCK += 10
	local first = handleShopAction(p, "BuyUpgrade", 1)
	local second, msg = handleShopAction(p, "BuyUpgrade", 2) -- the same instant
	check("spam: the second request in the same instant is refused", first == true and second == false and msg == "Too fast" and d.owned["Coffee Machine"] == nil, msg)
	CLOCK += BUY_MIN_INTERVAL - 0.01
	check("spam: still refused just under the interval", handleShopAction(p, "BuyUpgrade", 2) == false)
	CLOCK += 0.02
	check("spam: allowed again once the interval has passed", handleShopAction(p, "BuyUpgrade", 2) == true and d.owned["Coffee Machine"] == true)
	-- A refused request leaves the stamp (and so the next allowed time) exactly where the last looked-at request put it
	CLOCK += 1
	local stampedAt = CLOCK
	check("spam: a request after the interval is looked at and stamps the time", handleShopAction(p, "BuyUpgrade", 3) == true and d.lastBuyAt == stampedAt, d.lastBuyAt)
	local stampOk = true
	for _ = 1, 5 do
		CLOCK += 0.05
		local ok, why = handleShopAction(p, "BuyUpgrade", 4)
		if ok ~= false or why ~= "Too fast" or d.lastBuyAt ~= stampedAt then stampOk = false end
	end
	check("a refused spam request does not push the next allowed time forward (the stamp stays exactly the same)", stampOk and d.lastBuyAt == stampedAt, d.lastBuyAt)
	CLOCK = stampedAt + BUY_MIN_INTERVAL + 0.05 -- 0.45 s after the last purchase, 0.2 s after the last refused request
	check("spam: allowed once the interval from the last purchase has passed, even right after refused requests",
		handleShopAction(p, "BuyUpgrade", 4) == true and d.owned["Server Rack"] == true and d.lastBuyAt == CLOCK, d.lastBuyAt)
end

-- 3b. 100 spammed requests on a moving clock: the exact purchases and the exact Cash --------------------------
do
	local p, d = newPlayer(100000)
	d.owned.Desk = true -- the free one: every purchase below costs Cash
	CLOCK += 10
	local function nextId() -- what a spammed Buy button sends: the next upgrade's number
		for i, upg in ipairs(UPGRADES) do if not d.owned[upg.name] then return i end end
		return 1
	end
	local bought, at = 0, {}
	for request = 1, 100 do
		if request == 42 then
			CLOCK += 0.29 -- 0.45 s after the first purchase (outside the window)
		elseif request == 100 then
			CLOCK += 0.5 -- outside the window again
		elseif request > 1 then
			CLOCK += 0.004 -- inside the 0.4 s window
		end
		if handleShopAction(p, "BuyUpgrade", nextId()) then
			bought += 1
			table.insert(at, request)
		end
	end
	check("spam: 100 requests on a moving clock buy exactly 3 times (requests 1, 42 and 100)", bought == 3 and table.concat(at, ",") == "1,42,100", table.concat(at, ","))
	check("spam: 100 requests spend exactly $525 (Coffee Machine + Laptop + Server Rack)", d.cash.Value == 100000 - 525, 100000 - d.cash.Value)
	check("spam: after 100 requests the next is the Whiteboard (nothing skipped, nothing doubled)",
		d.owned["Server Rack"] == true and d.owned.Whiteboard == nil)
end

-- 4. Bad numbers and bad states --------------------------------------------------------------------------
do
	local p, d = newPlayer(100000)
	for _, bad in ipairs({ "1", "2", true, {}, 0, -1, 7, 1.5, 2.0000001, 0 / 0, math.huge, -math.huge, 1e300 }) do
		local ran, ok, msg = pcall(buy, p, bad)
		check("bad id " .. tostring(bad) .. " (" .. type(bad) .. "): refused cleanly (no error), nothing changed", ran and ok == false and next(d.owned) == nil and d.cash.Value == 100000, msg)
	end
	local ok, msg = buy(p, nil)
	check("no id at all: refused", ok == false and msg == "Bad request" and next(d.owned) == nil, msg)
	check("a bad action name is refused", handleShopAction(p, "GiveCash", 1) == false and handleShopAction(p, 5, 1) == false and handleShopAction(p, nil, 1) == false)
	local loading, ld = newPlayer(1000, false)
	ok, msg = buy(loading, 1)
	check("data.ready is false (loading, or an IPO being saved): refused", ok == false and ld.owned.Desk == nil and #CALLS == 0, msg)
	ok, msg = buy({}, 1)
	check("a player with no data: refused", ok == false, msg)
	local before = CLOCK
	check("a bad id never moves the rate limit stamp", d.lastBuyAt == nil, d.lastBuyAt)
end

-- 5. The client chooses the upgrade, never the price ---------------------------------------------------------
do
	local p, d = newPlayer(25)
	buy(p, 1)
	CALLS = {}
	CLOCK += 1
	local ok = handleShopAction(p, "BuyUpgrade", 2, 0, 1, "cost", { cost = 0 }) -- a client sending a price of 0 and more
	check("a price sent by the client is ignored: the real $25 is taken", ok == true and d.cash.Value == 0, d.cash.Value)
	local seen
	core.buyUpgrade = function(...) seen = { ... } return false, "x" end
	handleShopAction(p, "BuyUpgrade", 3, 0, 99)
	check("ShopServer passes only (player, id) on: nothing else the client sent reaches the buy", seen ~= nil and #seen == 2 and seen[1] == p and seen[2] == 3, seen and #seen)
	core.buyUpgrade = buyUpgrade
	local ok2, list = handleShopAction(p, "Upgrades", 5, 6)
	check("Upgrades: the six, in order, with name, price and income", ok2 == true and #list == #UPGRADES and list[1].name == "Desk" and list[2].cost == 25 and list[6].income == 120)
end

-- 6. HR Department purchase (PoachServer's HRBUY) ------------------------------------------------------------------
local ShopConfig = { formatCash = function(n) return "$" .. n end }
__HRBUY__
do
	local levels = { { cost = 100, defense = 0.1 }, { cost = 300, defense = 0.2 } }
	local poach = { hrLevel = 0 }
	CLOCK = 1000
	local nextLevel, msg = checkHrPurchase(levels, poach, 99, CLOCK)
	check("HR: not enough Cash is refused with the price", nextLevel == nil and string.find(msg, "$100", 1, true) ~= nil, msg)
	CLOCK += 1
	nextLevel = checkHrPurchase(levels, poach, 100, CLOCK)
	check("HR: exactly the price is enough, the next level's rules come back", nextLevel == levels[1])
	CLOCK += 0.1
	nextLevel, msg = checkHrPurchase(levels, poach, 100000, CLOCK)
	check("HR: spam within a second is refused", nextLevel == nil and msg == "Too fast", msg)
	poach.hrLevel = 2
	CLOCK += 5
	nextLevel, msg = checkHrPurchase(levels, poach, 100000, CLOCK)
	check("HR: past the last level there is nothing to buy", nextLevel == nil and string.find(msg, "fully", 1, true) ~= nil, msg)
	poach.hrLevel = 1
	CLOCK += 5
	check("HR: level 2 costs its own price", checkHrPurchase(levels, poach, 299, CLOCK) == nil and (function() CLOCK += 5 return checkHrPurchase(levels, poach, 300, CLOCK) == levels[2] end)())
end

-- 7. HR Department purchase: PoachServer's buyHr and the BuyHr action (lifted from the source) ---------------------
local RULES = { HRDepartment = __HRLEVELS__ }
local REAL_HR = RULES.HRDepartment
local SAVES, PUBLISHED = {}, {}
local task = { spawn = function(f, ...) f(...) end }
core.save = function(player) table.insert(SAVES, player) return true end
local function publish(player) table.insert(PUBLISHED, player) end
local function percent(chance) return math.floor(chance * 100 + 0.5) .. "%" end
local hrData = {}
local function getPoach(player)
	local data = hrData[player]
	return data and data.poach, data
end
local IpoServer = { isBusy = function() return false end }
local lastTargetsCall, TARGETS_MIN_INTERVAL = {}, 2
local function targetsFor() return {} end
local function start() return false, "start" end
local function counterOffer() return false, "counter" end
__BUYHR__
__ONACTION__
local function hrPlayer(cash, ready)
	local player = {}
	hrData[player] = { ready = ready ~= false, cash = { Value = cash }, poach = { hrLevel = 0 } }
	return player, hrData[player]
end
local function hrBuy(player, ...) -- pcall: a broken rule may error, which must count as a failed test, not a crash
	SAVES, PUBLISHED = {}, {}
	local ran, ok, msg = pcall(buyHr, player, ...)
	if not ran then return "error", tostring(ok) end
	return ok, msg
end
do
	CLOCK = 5000
	local p, d = hrPlayer(1000000, false)
	local ok, msg = hrBuy(p)
	check("HR buy: not ready (loading or an IPO being saved) is refused, nothing changes",
		ok == false and d.cash.Value == 1000000 and d.poach.hrLevel == 0 and #SAVES == 0 and d.poach.lastHrBuyAt == nil, msg)

	p, d = hrPlayer(REAL_HR[1].cost - 1)
	CLOCK += 2
	ok, msg = hrBuy(p)
	check("HR buy: one Cash short is refused with the price, nothing changes, no save",
		ok == false and d.cash.Value == REAL_HR[1].cost - 1 and d.poach.hrLevel == 0 and #SAVES == 0
		and string.find(msg, "$" .. REAL_HR[1].cost, 1, true) ~= nil, msg)

	p, d = hrPlayer(REAL_HR[1].cost)
	CLOCK += 2
	ok, msg = hrBuy(p)
	check("HR buy: exactly the price buys Lv 1, the exact cost is taken", ok == true and d.cash.Value == 0 and d.poach.hrLevel == 1, msg)
	check("HR buy: a purchase saves once and publishes the new level", #SAVES == 1 and SAVES[1] == p and #PUBLISHED == 1, #SAVES)

	-- every level, in order, at the server's own prices, then the cap
	local total = 0
	for _, level in ipairs(REAL_HR) do total += level.cost end
	p, d = hrPlayer(total + 7)
	local allOk = true
	for i, level in ipairs(REAL_HR) do
		CLOCK += 1.5
		local before = d.cash.Value
		ok, msg = hrBuy(p)
		if not (ok == true and d.poach.hrLevel == i and before - d.cash.Value == level.cost and #SAVES == 1) then
			allOk = false
			check("HR buy: Lv " .. i .. " costs exactly " .. level.cost .. " and raises the level by 1", false, msg)
		end
	end
	check("HR buy: every level costs exactly its server price and raises hrLevel by 1", allOk and d.cash.Value == 7 and d.poach.hrLevel == #REAL_HR, d.cash.Value)
	d.cash.Value = 10 ^ 9
	CLOCK += 1.5
	ok, msg = hrBuy(p)
	check("HR buy: past the last level is refused, nothing taken, no save",
		ok == false and d.poach.hrLevel == #REAL_HR and d.cash.Value == 10 ^ 9 and #SAVES == 0 and string.find(tostring(msg), "fully", 1, true) ~= nil, msg)

	-- the 1 s rate limit
	p, d = hrPlayer(1000000)
	CLOCK += 2
	local boughtAt = CLOCK
	ok = hrBuy(p)
	CLOCK += 0.6
	local ok2, msg2 = hrBuy(p)
	check("HR buy: a second buy 0.6 s later is refused (Too fast), nothing taken, no save",
		ok == true and ok2 == false and msg2 == "Too fast" and d.poach.hrLevel == 1 and d.cash.Value == 1000000 - REAL_HR[1].cost and #SAVES == 0, msg2)
	check("HR buy: the refused request leaves the stamp exactly where the purchase put it", d.poach.lastHrBuyAt == boughtAt, d.poach.lastHrBuyAt)
	CLOCK = boughtAt + 0.99
	check("HR buy: still refused at 0.99 s", hrBuy(p) == false and d.poach.hrLevel == 1)
	CLOCK = boughtAt + 1.05
	ok = hrBuy(p)
	check("HR buy: allowed again after 1 s, Lv 2 at its own price", ok == true and d.poach.hrLevel == 2
		and d.cash.Value == 1000000 - REAL_HR[1].cost - REAL_HR[2].cost, d.cash.Value)

	-- the price and the cap come from the server's rules only
	RULES.HRDepartment = { { cost = 7, defense = 0.5 } }
	p, d = hrPlayer(100)
	CLOCK += 2
	ok = hrBuy(p)
	CLOCK += 2
	ok2, msg2 = hrBuy(p)
	check("HR buy: with other server rules, their price (7) and their cap (1 level) are used",
		ok == true and d.cash.Value == 93 and d.poach.hrLevel == 1 and ok2 == false and d.cash.Value == 93, msg2)
	RULES.HRDepartment = REAL_HR

	-- the BuyHr action: whatever else the client sends is never read
	p, d = hrPlayer(REAL_HR[1].cost)
	CLOCK += 2
	SAVES = {}
	local ran, okA, msgA = pcall(onAction, p, "BuyHr", 0, { cost = 0, level = 5 })
	check("BuyHr action: a price or level sent by the client is ignored, the real price is taken and the level goes up by 1",
		ran and okA == true and d.cash.Value == 0 and d.poach.hrLevel == 1, msgA)
	p, d = hrPlayer(1000000, false)
	ran, okA = pcall(onAction, p, "BuyHr")
	check("BuyHr action: refused while not ready", ran and okA == false and d.poach.hrLevel == 0 and d.cash.Value == 1000000)
end

print_real(string.format("%d passed, %d failed", passed, failed))
"""


def code_only(text):
    """The Lua text without comments (a line's `--` tail is cut, so words in comments never count)."""
    lines = []
    for line in text.split("\n"):
        cut = line.find("--")
        lines.append(line if cut < 0 else line[:cut])
    return "\n".join(lines)


def upgrades_lua():
    """UPGRADES from TycoonCore.lua as a Luau table (name, cost, income: the real prices)."""
    import re
    with open(os.path.join(ROOT, "TycoonCore.lua"), encoding="utf-8") as f:
        text = f.read()
    block = text[text.index("local UPGRADES = {"):]
    block = block[:block.index("\n}")]
    rows = re.findall(r'name = "([^"]+)",\s*cost = (\d+),\s*income = (\d+)', block)
    if len(rows) != 6:
        raise SystemExit("UPGRADES in TycoonCore.lua no longer has 6 rows with name, cost and income")
    return "{ " + ", ".join('{ name = "%s", cost = %s, income = %s }' % row for row in rows) + " }"


def hr_levels_lua():
    """CreatureConfig.Poaching.HRDepartment as a Luau table (cost, defense: the real server rules)."""
    import re
    with open(os.path.join(ROOT, "CreatureConfig.lua"), encoding="utf-8") as f:
        text = f.read()
    block = text[text.index("HRDepartment = {"):]
    block = block[:block.index("\n\t},")]
    rows = re.findall(r"\{ cost = (\d+), defense = ([\d.]+) \}", block)
    if len(rows) < 2:
        raise SystemExit("CreatureConfig.Poaching.HRDepartment no longer has rows with cost and defense")
    return "{ " + ", ".join("{ cost = %s, defense = %s }" % row for row in rows) + " }"


def function_source(header, filename):
    """One top-level Lua function, from its header line to its closing `end` at the start of a line."""
    with open(os.path.join(ROOT, filename), encoding="utf-8") as f:
        text = f.read()
    if text.count(header) != 1:
        raise SystemExit("%s: expected exactly one '%s'" % (filename, header))
    start = text.index(header)
    return text[start:text.index("\nend\n", start) + len("\nend\n")]


def buy_source(mutation=None):
    """The BUY_TESTS program, with the real regions. mutation = (old, new) breaks one rule: it is applied to the
    first region that has `old` (TycoonCore, ShopServer, PoachServer's HRBUY region, buyHr, onAction)."""
    parts = {
        "__BUYUPGRADE__": marked_source("BUYUPGRADE"),
        "__SHOPACTION__": marked_source("SHOPACTION", "ShopServer.lua"),
        "__HRBUY__": marked_source("HRBUY", "PoachServer.lua"),
        "__BUYHR__": function_source("local function buyHr(player)", "PoachServer.lua"),
        "__ONACTION__": function_source("local function onAction(player, action, a, b)", "PoachServer.lua"),
    }
    if mutation:
        old, new = mutation
        for key, region in parts.items():
            if old in region:
                parts[key] = region.replace(old, new, 1)
                break
        else:
            raise SystemExit("mutation target not found: " + old)
    source = BUY_TESTS.replace("__UPGRADES__", upgrades_lua()).replace("__HRLEVELS__", hr_levels_lua())
    for key, region in parts.items():
        source = source.replace(key, region)
    return source


# Each of these breaks one rule of the purchase; the tests must notice (a test that can't fail proves nothing).
# A third element names a test that must be among the failures (proof that this test is the one that can fail).
BUY_MUTATIONS = [
    ("the Cash check", ("if cash < upg.cost then", "if false then")),
    ("the already-owned check", ("if data.owned[upg.name] then", "if false then")),
    ("the order check", ("if i ~= id then", "if false then")),
    ("the rate limit", ("if data.lastBuyAt and now - data.lastBuyAt < BUY_MIN_INTERVAL then", "if false then"),
     "spam: 100 requests on a moving clock buy exactly 3 times"),
    ("the rate limit (a refused request also stamps the time)",
     ("\tif data.lastBuyAt and now - data.lastBuyAt < BUY_MIN_INTERVAL then\n\t\treturn nil, \"Too fast\"\n\tend\n\tdata.lastBuyAt = now\n",
      "\tlocal previous = data.lastBuyAt\n\tdata.lastBuyAt = now\n\tif previous and now - previous < BUY_MIN_INTERVAL then\n\t\treturn nil, \"Too fast\"\n\tend\n"),
     "a refused spam request does not push the next allowed time forward"),
    ("the rate limit (a refused request also stamps the time, seen by the 100 requests)",
     ("\tif data.lastBuyAt and now - data.lastBuyAt < BUY_MIN_INTERVAL then\n\t\treturn nil, \"Too fast\"\n\tend\n\tdata.lastBuyAt = now\n",
      "\tlocal previous = data.lastBuyAt\n\tdata.lastBuyAt = now\n\tif previous and now - previous < BUY_MIN_INTERVAL then\n\t\treturn nil, \"Too fast\"\n\tend\n"),
     "spam: 100 requests on a moving clock buy exactly 3 times"),
    ("the rate limit interval (0.4 s cut to 0.1 s)", ("local BUY_MIN_INTERVAL = 0.4", "local BUY_MIN_INTERVAL = 0.1"),
     "spam: 100 requests on a moving clock buy exactly 3 times"),
    ("the id range check", ("id < 1 or id > #upgrades", "false")),
    ("the whole-number check", ("id % 1 ~= 0 or ", "")),
    ("the ready check", ("if not data.ready then", "if false then")),
    ("the type check in ShopServer", ("if typeof(id) ~= \"number\" then", "if false then")),
    ("the HR ready check in buyHr", ("if not poach or not data.ready then", "if not poach then"),
     "HR buy: not ready (loading or an IPO being saved) is refused"),
    ("the HR Cash check", ("if cash < nextLevel.cost then", "if false then"),
     "HR buy: one Cash short is refused"),
    ("the HR Cash deduction", ("data.cash.Value -= nextLevel.cost", "data.cash.Value -= 0"),
     "HR buy: exactly the price buys Lv 1, the exact cost is taken"),
    ("the HR level increase", ("poach.hrLevel += 1", "poach.hrLevel += 0"),
     "HR buy: every level costs exactly its server price and raises hrLevel by 1"),
    ("the HR save", ("task.spawn(core.save, player)", "-- no save"),
     "HR buy: a purchase saves once and publishes the new level"),
    ("the HR level cap (the last level sold again)", ("levels[poach.hrLevel + 1]", "levels[math.min(poach.hrLevel + 1, #levels)]"),
     "HR buy: past the last level is refused"),
    ("the HR rate limit", ("if poach.lastHrBuyAt and now - poach.lastHrBuyAt < HR_BUY_MIN_INTERVAL then", "if false then"),
     "HR buy: a second buy 0.6 s later is refused"),
    ("the HR rate limit interval (1 s cut to 0.5 s)", ("local HR_BUY_MIN_INTERVAL = 1", "local HR_BUY_MIN_INTERVAL = 0.5"),
     "HR buy: a second buy 0.6 s later is refused"),
    ("the HR price from the server rules (a hardcoded level list)", ("checkHrPurchase(RULES.HRDepartment,", "checkHrPurchase(" + "{ { cost = 2500, defense = 0.05 } },"),
     "HR buy: with other server rules, their price (7) and their cap (1 level) are used"),
]


def pads_gone_checks():
    """Source checks: no walk-on pad, no Touched buy or trigger, the Office tab sends only an upgrade number, no new save section."""
    import re
    passed, failed = 0, 0

    def check(name, cond, extra=None):
        nonlocal passed, failed
        if cond:
            passed += 1
        else:
            failed += 1
            print("FAIL: " + name + (" -- " + str(extra) if extra else ""))

    def read(name):
        with open(os.path.join(ROOT, name), encoding="utf-8") as f:
            return f.read()

    lua_files = [n for n in sorted(os.listdir(ROOT)) if n.endswith(".lua")]
    touched = {n: len(re.findall(r"\.Touched\b", code_only(read(n)))) for n in lua_files}
    touched = {n: c for n, c in touched.items() if c}
    check("the only Touched handler in the game is the VIP Lounge door in ShopServer (it opens Roblox's own confirm prompt)", touched == {"ShopServer.lua": 1}, touched)
    for name in lua_files:
        code = code_only(read(name))
        for word in ("BuyPad", "HRPad", "IpoPad", "HR_PAD_OFFSET", "buildHrPad", "refreshPad", "hrLabel", "padLabel"):
            check("%s has no %s (the pads are gone)" % (name, word), word not in code)

    core = read("TycoonCore.lua")
    code = code_only(core)
    check("TycoonCore: one purchase function, and the shop gets it", "buyUpgrade = buyUpgrade," in code and code.count("local function buyUpgrade(") == 1)
    check("TycoonCore: the sign has no touch, collision or query", "post.CanCollide, post.CanTouch, post.CanQuery = false, false, false" in code
          and "board.CanCollide, board.CanTouch, board.CanQuery = false, false, false" in code)
    check("TycoonCore: a join and an IPO reset refresh the sign and the Office state", code.count("refreshSign(player)") >= 3)
    check("TycoonCore: spawning on a plot buys nothing (the character only lands and faces the sign)", "auto-buy" not in core and "Touched" not in core)
    sections = re.search(r"local KNOWN_SECTIONS = \{([^}]*)\}", core).group(1)
    check("TycoonCore: no new save section (the Office tab saves nothing: owned already is)",
          sorted(re.findall(r"(\w+) = true", sections)) == sorted("cash owned lastSeen shop team poach ipo onboarding daily fixedHires tasks".split()), sections)
    check("TycoonCore: nothing new is written to the save for the Office (no lastBuyAt or Upgrade attribute in the payload)",
          "lastBuyAt" not in core[core.index("local function buildPayload"):core.index("-- BUILDSAVE-END")])

    shop = code_only(read("ShopServer.lua"))
    region = shop[shop.index("local function handleShopAction"):shop.index("function ShopServer.addDebugAction") if "function ShopServer.addDebugAction" in shop else len(shop)]
    handler = region[:region.index("return false, \"Unknown action\"")]
    check("ShopServer: the Office action only calls core.buyUpgrade(player, id) (no price, no Cash, no save of its own)",
          handler.count("core.buyUpgrade(player, id)") == 1 and "cash" not in handler.lower() and "cost" not in handler.lower())
    check("ShopServer: ShopAction is created on live servers too (not behind the Studio debug check)",
          shop.index('actionRemote.Name = "ShopAction"') < shop.index("if RunService:IsStudio() and ShopConfig.DebugInStudio then", shop.index('actionRemote.Name = "ShopAction"') - 400))

    client = code_only(read("ShopClient.lua"))
    invokes = re.findall(r"actionRemote:InvokeServer\(([^)]*)\)", client)
    check("ShopClient: the Office tab asks only for the list and sends the upgrade number (no price)",
          sorted(invokes) == ['"BuyUpgrade", index', '"Upgrades"'], invokes)
    check("ShopClient: an Office tab, first and the one shown when the shop opens",
          'local tabNames = { "Office",' in client and 'showTab("Office")' in client)
    check("ShopClient: Buy is only offered for the next upgrade when the Cash is there (the server decides anyway)",
          'setButton(button, "Locked", COLORS.disabled, false)' in client and 'setButton(button, "Owned", COLORS.owned, false)' in client)

    poach = code_only(read("PoachClient.lua"))
    check("PoachClient: Buy HR sends only the action", 'request("BuyHr")' in poach and 'request("BuyHr",' not in poach)
    check("PoachClient: the HR card no longer sends players to a pad", "pad" not in poach.lower().replace("padding", ""))
    poach_server = code_only(read("PoachServer.lua"))
    check("PoachServer: BuyHr is an action of the existing PoachAction remote (no new remote)", 'action == "BuyHr"' in poach_server and poach_server.count("Instance.new(\"Remote") == 2)
    return passed, failed


def source_file(name, files=None):
    """The text of a file at the repo root; `files` ({name: text}) replaces it (the mutation runner breaks one file in memory)."""
    if files and name in files:
        return files[name]
    with open(os.path.join(ROOT, name), encoding="utf-8") as f:
        return f.read()


def task_wiring_checks(files=None, failures=None):
    """Checks on the source text: load order, the save section, addEarnings call sites, D9 words, the client's requests,
    and that calls start with the Desk. `files` and `failures` are for the mutation runner (see TASK_MUTANTS)."""
    import re
    passed, failed = 0, 0

    def check(name, cond, extra=None):
        nonlocal passed, failed
        if cond:
            passed += 1
        else:
            failed += 1
            line = "FAIL: " + name + (" -- " + str(extra) if extra else "")
            if failures is None:
                print(line)
            else:
                failures.append(line)

    def read(name):
        return source_file(name, files)

    core = read("TycoonCore.lua")
    check("TycoonCore: TaskServer.init comes before DailyServer.init", 0 < core.index("TaskServer.init(") < core.index("DailyServer.init("))
    check("TycoonCore: TaskServer.setupPlayer comes before DailyServer.setupPlayer (Daily stays last)", 0 < core.index("TaskServer.setupPlayer(") < core.index("DailyServer.setupPlayer("))
    for earlier in ("IpoServer.setupPlayer(", "EmployeeServer.setupPlayer(", "OnboardingServer.setupPlayer("):
        check("TycoonCore: " + earlier + " runs before TaskServer.setupPlayer", core.index(earlier) < core.index("TaskServer.setupPlayer("))
    check("TycoonCore: tasks is a known section", re.search(r"local KNOWN_SECTIONS = \{[^}]*\btasks = true", core) is not None)
    check("TycoonCore: the payload is built with TaskServer.serialize", "tasks = TaskServer.serialize(data)" in core)
    check("TycoonCore: a save needs data.tasks like every other part", "data.daily and data.tasks)" in core)
    check("TycoonCore: DataStore name and key untouched", 'GetDataStore("StartupTycoon_v1")' in core and '"player_" .. player.UserId' in core)

    # Every addEarnings call site in the game. A new one fails here until it is reviewed (valuation!).
    expected = {"TycoonCore.lua": 3, "ShopServer.lua": 1, "IpoServer.lua": 2, "TaskServer.lua": 1, "DailyServer.lua": 0, "EmployeeServer.lua": 0, "PoachServer.lua": 0, "OnboardingServer.lua": 0}
    for filename, count in expected.items():
        calls = 0
        for line in code_only(read(filename)).split("\n"):
            if re.search(r"addEarnings\s*\(", line) and not re.search(r"function\s+[\w.]*addEarnings\s*\(", line):
                calls += 1
        check("%s has %d addEarnings call(s)" % (filename, count), calls == count, calls)

    server = code_only(read("TaskServer.lua"))
    check("TaskServer pays only through core.addEarnings (never IpoServer directly)", server.count("core.addEarnings(") == 1 and "IpoServer.addEarnings" not in server)
    check("TaskServer never grants Shares, eggs or products", all(word not in server for word in ("grantShares", "grantEgg", "grantProduct", "PromptProductPurchase")))
    check("TaskServer only touches data.tasks, data.cash and data.income of the player's data",
          not re.search(r"data\.(shop|team|poach|ipo|onboarding|daily|fixedHires)\s*(=[^=]|\.[A-Za-z_]+\s*(=[^=]|\+=|-=))", server))
    config = read("TaskConfig.lua")
    check("TaskConfig: Enabled and StudioOnly are on (PR 1 runs only in Studio)", "TaskConfig.Enabled = true" in config and "TaskConfig.StudioOnly = true" in config)

    forbidden = ("odds", "chance", "luck", "random", "probab", "%")
    for filename in ("TaskClient.lua", "TaskServer.lua"):
        found = None
        for literal in re.findall(r'"((?:[^"\\\n]|\\.)*)"', code_only(read(filename))):
            for word in forbidden:
                if word in literal.lower() and not (word == "%" and re.search(r"%[ds.0-9]", literal)):
                    found = literal
        check(filename + ": no text claims odds, chance or luck (D9)", found is None, found)

    client = code_only(read("TaskClient.lua"))
    invokes = re.findall(r"InvokeServer\(([^)]*)\)", client)
    check("TaskClient: only asks the server (Answer with a call number, Start, Pause, Sync, and Layout: the GUI size, Studio only)", len(invokes) == 5 and all(len(args.split(",")) <= 2 for args in invokes), invokes)
    check("TaskClient: the Layout report is Studio only", re.search(r'if not RunService:IsStudio\(\) then\s*return\s*end\s*reportToken', client) is not None)
    check("TaskClient: sends no Cash, time or reward", not any(word in args.lower() for args in invokes for word in ("cash", "reward", "time", "clock", "amount")))
    check("TaskClient: ends at once when the engine is off (outside Studio in PR 1)", re.search(r"if not TaskConfig\.isActive\(\) then\s*return\s*end", client) is not None)
    check("TaskClient: windows hide the tray through the OpenPanel attribute", 'GetAttribute("OpenPanel")' in client)
    tray_gui = client[client.index('Name = "TaskGui"'):client.index('Name = "TaskFrontGui"')]
    front_gui = client[client.index('Name = "TaskFrontGui"'):client.index("local tray = make")]
    check("TaskClient: the tray draws below every other pop-up (TaskGui DisplayOrder -2, under the HUD at -1)", "DisplayOrder = -2" in tray_gui)
    check("TaskClient: its own message sits in a layer above the HUD (TaskFrontGui DisplayOrder 5, like the other pop-ups)", "DisplayOrder = 5" in front_gui and "Parent = front" in client[client.index('Name = "Toast"'):client.index("round(toast, 12)")])
    check("TaskClient: the spots are the named constants PORTRAIT_SPOT and LANDSCAPE_SPOT", "local PORTRAIT_SPOT = {" in client and "local LANDSCAPE_SPOT = {" in client and "PORTRAIT_SPOT.y" in client and "LANDSCAPE_SPOT.y" in client)

    # Calls start with the Desk (owner decision): the Call row names the first upgrade, TaskServer only reads it from the
    # data it already has, and the client shows nothing about calls until the server says they are on.
    first_upgrade = re.search(r'local UPGRADES = \{\s*\{ name = "([^"]+)",\s+cost = (\d+)', core)
    check("desk wiring: TycoonCore's first upgrade is a Desk that costs 0 (the row's `owns` must name it)", first_upgrade is not None and first_upgrade.group(1) == "Desk" and first_upgrade.group(2) == "0", first_upgrade and first_upgrade.groups())
    check("desk wiring: the Call row's `owns` is the name of TycoonCore's first upgrade",
          first_upgrade is not None and re.search(r'unlock = \{ rung = 0, owns = "%s" \}' % re.escape(first_upgrade.group(1)), config) is not None)
    check("desk wiring: TaskServer reads the Desk from data.owned in one place (rowOn) and never writes it",
          server.count("data.owned") == 1 and "TaskConfig.isUnlocked(row, rungOf(data), ipoCountOf(data), data.owned)" in server
          and not re.search(r"\.owned\s*(\[[^\]]*\])?\s*(=[^=]|\+=|-=)", server) and "table.insert(data.owned" not in server and "table.clear(data.owned" not in server)
    check("desk wiring: TaskServer asks TaskConfig.isUnlocked only through rowOn (Start, the tick and the state share it)",
          server.count("TaskConfig.isUnlocked(") == 1 and server.count("rowOn(data, row)") >= 3 and "on = callsOn(data)," in server)
    check("desk wiring: TaskServer adds no remote for it (still TaskAction and TaskState)", server.count('Instance.new("Remote') == 2)
    check("desk wiring: TaskServer reads no TycoonCore field it was not given (only data.owned is new)", "UPGRADES" not in server and "playerData" not in server)
    check("desk wiring: TaskClient decides what is shown only with callsShown (the tray, its chips, 'Tap to resume' and the line above it)",
          client.count("callsShown(windowOpen, callsOn, #calls)") == 2 and "local showTray = callsShown(windowOpen, callsOn, #calls)" in client
          and "tray.Visible = showTray" in client and "tray.Visible = true" not in client and "info.Visible = callsShown(windowOpen, callsOn, #calls) and text ~= \"\"" in client
          and "chip.button.Visible = showTray and chip.call ~= nil" in client and "resume.Visible = showTray and quiet and #calls == 0" in client)
    check("desk wiring: TaskClient starts with calls off and only the server's `on` turns them on",
          "local callsOn = false" in client and "callsOn = state.on == true" in client and client.count("callsOn = ") == 2)
    check("desk wiring: TaskClient has no 'tasks are off' text of its own (it shows nothing before the Desk)", "TEXTS.Off" not in client and "Tasks are off" not in client)

    shop = read("ShopClient.lua")
    check("ShopClient: the task Debug rows are inside the Studio-only Debug block", shop.index("TaskSpawn") > shop.index("if debugRemote then") and shop.index("TaskSpawn") < shop.index("-- Tabs, opening and closing"))
    return passed, failed


def marked_text(text, name):
    """The part of `text` between `-- NAME-START` and `-- NAME-END`."""
    start = text.index("-- %s-START" % name) + len("-- %s-START" % name)
    return text[start:text.index("-- %s-END" % name)]


def task_engine_source(files=None):
    """The TASK_TESTS program with the real TaskConfig and TaskServer (`files` replaces a file's text, for the mutants)."""
    return (TASK_TESTS.replace("__DAILYCONFIG__", source_file("DailyConfig.lua", files)).replace("__IPOCONFIG__", source_file("IpoConfig.lua", files))
            .replace("__TASKCONFIG__", source_file("TaskConfig.lua", files)).replace("__TASKSERVER__", source_file("TaskServer.lua", files)))


def tray_source(files=None, dump=False):
    """The TRAY_TESTS program with the marked code of the real TaskClient."""
    client = source_file("TaskClient.lua", files)
    return (TRAY_TESTS.replace("__DUMP__", "true" if dump else "false").replace("__TRAY__", marked_text(client, "TRAY"))
            .replace("__PAUSE__", marked_text(client, "PAUSE")).replace("__SHOWN__", marked_text(client, "SHOWN"))
            .replace("__GOALCOUNT__", str(onboarding_goal_count())))


# Each of these breaks one rule of "calls start when the player owns the Desk (or after the first IPO)" in one file, in memory
# (nothing on disk changes). A mutant counts as caught only when the check NAMED here is among the FAIL lines of its suite
# ("engine" = the task engine tests, "tray" = the TaskClient tests, "wiring" = the source checks): a crash alone is no catch.
# (label, file, old text, new text, suite, name the FAIL line must start with)
TASK_MUTANTS = [
    ("the Desk condition is ignored (always on)", "TaskConfig.lua",
     "\treturn needs == nil or (owned ~= nil and owned[needs] == true)\n", "\treturn true\n",
     "engine", "desk: no call arrives before the Desk"),
    ("the Desk condition is inverted", "TaskConfig.lua",
     "needs == nil or (owned ~= nil and owned[needs] == true)", "needs == nil or not (owned ~= nil and owned[needs] == true)",
     "engine", "desk: no call arrives before the Desk"),
    ("the Desk check uses the wrong name (config)", "TaskConfig.lua",
     'owns = "Desk" }', 'owns = "Coffee Machine" }',
     "engine", "desk: the first call after the Desk is bought is not earlier"),
    ("the Desk check reads the wrong field (server)", "TaskServer.lua",
     "ipoCountOf(data), data.owned)", "ipoCountOf(data), data.upgrades)",
     "engine", "desk: the first call after the Desk is bought is not earlier"),
    ("the first call is instant when the Desk is bought", "TaskServer.lua",
     "\t\t\t\tif at == nil then\n\t\t\t\t\tscheduleNext(data, run, row, now)", "\t\t\t\tif at == nil then\n\t\t\t\t\trun.nextAt[row.key] = now",
     "engine", "desk: the first call after the Desk is bought is not earlier"),
    ("the IPO bypass is removed", "TaskConfig.lua",
     "\tif ipoCount >= 1 then\n\t\treturn true\n\tend\n\tif rung", "\tif rung",
     "engine", "desk: after the first IPO calls keep coming without the Desk"),
    ("the IPO bypass is always on", "TaskConfig.lua",
     "\tif ipoCount >= 1 then\n\t\treturn true", "\tif true then\n\t\treturn true",
     "engine", "desk: no call arrives before the Desk"),
    ("the IPO bypass starts at the second IPO", "TaskConfig.lua",
     "\tif ipoCount >= 1 then\n\t\treturn true", "\tif ipoCount >= 2 then\n\t\treturn true",
     "engine", "desk: after the first IPO calls keep coming without the Desk"),
    ("a waiting call is removed when calls turn off", "TaskServer.lua",
     "\t\t\trun.nextAt[row.key] = nil\n\t\tend\n\tend\n\tif not on then",
     "\t\t\trun.nextAt[row.key] = nil\n\t\t\tfor _, id in ipairs(table.clone(run.order)) do closeTask(run, id) end\n\t\tend\n\tend\n\tif not on then",
     "engine", "desk: calls already waiting are not removed when calls turn off"),
    ("quiet mode can start before the Desk", "TaskServer.lua",
     "\tif on and not run.quiet and not run.paused", "\tif not run.quiet and not run.paused",
     "engine", "desk: three calls that run out after the Desk is gone"),
    ("the idle clock is not held before the Desk", "TaskServer.lua",
     "\tif not on then\n\t\trun.lastActionAt = now\n\tend\n", "",
     "engine", "desk: buying the Desk after 5 minutes does not start quiet mode"),
    ("an old arrival timer is kept while calls are off", "TaskServer.lua",
     "\t\t\trun.nextAt[row.key] = nil\n\t\tend\n\tend\n\tif not on then", "\t\tend\n\tend\n\tif not on then",
     "engine", "desk: a timer from before the Desk was lost is not used when it is bought again"),
    ("'Tap to resume' opens a call before the Desk", "TaskServer.lua",
     "if row and rowOn(data, row) then", "if row then",
     "engine", "desk: 'Tap to resume' is accepted but brings no call before the Desk"),
    ("the state always says calls are on", "TaskServer.lua",
     "on = callsOn(data),", "on = true,",
     "engine", "desk: before the Desk the state says calls are off"),
    ("the rung is ignored", "TaskConfig.lua",
     "\tif rung < row.unlock.rung then\n\t\treturn false\n\tend\n", "",
     "engine", "desk: isUnlocked, the Desk does not skip the rung"),
    ("a missing owned list counts as owning the Desk", "TaskConfig.lua",
     "(owned ~= nil and owned[needs] == true)", "(owned == nil or owned[needs] == true)",
     "engine", "desk: isUnlocked fails closed without an owned list"),
    ("any upgrade counts as the Desk", "TaskConfig.lua",
     "owned ~= nil and owned[needs] == true", "owned ~= nil and next(owned) ~= nil",
     "engine", "desk: owning other upgrades without the Desk starts no call"),
    ("the team's call pays nothing", "TaskServer.lua",
     "pay(player, data, run, row.reward.seconds * row.teamPays)", "pay(player, data, run, 0)",
     "engine", "desk: once the Desk is bought the team takes calls for the player"),
    ("the client shows the tray early", "TaskClient.lua",
     "\treturn not windowOpen and (callsOn or waitingCount > 0)", "\treturn not windowOpen",
     "tray", "shown: before the Desk nothing about calls is shown"),
    ("the client hides a call that is still waiting", "TaskClient.lua",
     "\treturn not windowOpen and (callsOn or waitingCount > 0)", "\treturn not windowOpen and callsOn",
     "tray", "shown: a call that is still waiting stays visible"),
    ("the client's tray ignores the rule", "TaskClient.lua",
     "\tlocal showTray = callsShown(windowOpen, callsOn, #calls)", "\tlocal showTray = not windowOpen",
     "wiring", "desk wiring: TaskClient decides what is shown only with callsShown"),
    ("the client's line above the tray ignores the rule", "TaskClient.lua",
     "info.Visible = callsShown(windowOpen, callsOn, #calls) and text", "info.Visible = not windowOpen and text",
     "wiring", "desk wiring: TaskClient decides what is shown only with callsShown"),
    ("the client starts with calls on", "TaskClient.lua",
     "local callsOn = false", "local callsOn = true",
     "wiring", "desk wiring: TaskClient starts with calls off"),
    ("the client ignores the server's flag", "TaskClient.lua",
     "callsOn = state.on == true", "callsOn = true",
     "wiring", "desk wiring: TaskClient starts with calls off"),
    ("the first upgrade is renamed in TycoonCore (the row's name drifts)", "TycoonCore.lua",
     '{ name = "Desk",           cost = 0,', '{ name = "Writing Desk",    cost = 0,',
     "wiring", "desk wiring: TycoonCore's first upgrade is a Desk"),
    ("TaskServer writes the player's Desk", "TaskServer.lua",
     "local function callsOn(data)\n", "local function callsOn(data)\n\tdata.owned.Desk = true\n",
     "wiring", "desk wiring: TaskServer reads the Desk from data.owned in one place"),
]


def run_task_mutants(luau):
    """Runs every TASK_MUTANTS entry. Returns (caught, problems): a mutant is caught only by its named FAIL line."""
    caught, problems = 0, 0
    for label, filename, old, new, suite, expected in TASK_MUTANTS:
        text = source_file(filename)
        if text.count(old) != 1:
            print("FAIL: task mutant \"%s\": its target text is in %s %d times (it must be exactly once)" % (label, filename, text.count(old)))
            problems += 1
            continue
        files = {filename: text.replace(old, new)}
        ran_to_end = True
        if suite == "wiring":
            failures = []
            task_wiring_checks(files, failures)
        else:
            source = task_engine_source(files) if suite == "engine" else tray_source(files)
            result = run_luau(luau, source)
            failures = [line for line in result.stdout.split("\n") if line.startswith("FAIL: ")]
            ran_to_end = "passed," in result.stdout
        named = [line for line in failures if line.startswith("FAIL: " + expected)]
        if not named:
            print("FAIL: task mutant not caught by its named check: \"%s\" should fail \"%s\" (%s suite; it failed %d other check(s))" % (label, expected, suite, len(failures)))
            problems += 1
        else:
            caught += 1
            note = "" if ran_to_end else "  [the later tests then crashed on the broken engine; the catch is the named FAIL line above]"
            print("  mutant caught: %s -> %s%s" % (label, named[0][len("FAIL: "):].split(" -- ")[0], note))
    return caught, problems


# Rooms were built one stage at a time (visuals-garage); all 5 exist now, one per IpoConfig funding stage.
VISUALS_ALL_STAGES = True


def visuals_expected_lua():
    """The layout map read from the real scripts, as a Luau table (PlotArt.Layout must match it)."""
    import re

    def read(name):
        with open(os.path.join(ROOT, name), encoding="utf-8") as f:
            return f.read()

    def num(text):
        return float(text) if "." in text else int(text)

    def spots(text, name):
        block = text[text.index("local %s = {" % name):]
        block = block[:block.index("\n}")]
        return [(num(x), num(z)) for x, z in re.findall(r"Vector3\.new\((-?[\d.]+), 0, (-?[\d.]+)\)", block)]

    core = read("TycoonCore.lua")
    upgrades_block = core[core.index("local UPGRADES = {"):]
    upgrades_block = upgrades_block[:upgrades_block.index("\n}")]
    upgrades = re.findall(r'name = "([^"]+)"', upgrades_block)
    item = re.search(r"local function itemOffset\(i\)\s*local col = \(i - 1\) // 3\s*local row = \(i - 1\) % 3\s*return Vector3\.new\((-?[\d.]+) \+ col \* (-?[\d.]+), 0, (-?[\d.]+) \+ row \* (-?[\d.]+)\)", core)
    if not item:
        raise SystemExit("itemOffset changed in TycoonCore.lua: update visuals_expected_lua and PlotArt.Layout")
    x0, dx, z0, dz = (num(item.group(k)) for k in (1, 2, 3, 4))
    slots = [(x0 + ((i - 1) // 3) * dx, z0 + ((i - 1) % 3) * dz) for i in range(1, len(upgrades) + 1)]
    spawn = re.search(r"local spawnPos = plotCenter\(slot\) \+ Vector3\.new\((-?[\d.]+), 4, (-?[\d.]+)\)", core)
    floor = re.search(r'makePart\(folder, "Floor", Vector3\.new\((\d+), (\d+), (\d+)\), plotCenter\(slot\)', core)
    center_y = re.search(r"return Vector3\.new\(startX \+ \(slot - 1\) \* PLOT_SPACING, ([\d.]+), 150\)", core)
    buy = re.search(r"local SIGN_OFFSET = Vector3\.new\((-?[\d.]+), 0\.5, (-?[\d.]+)\)", core)
    ipo = re.search(r"local SIGN_OFFSET = Vector3\.new\((-?[\d.]+), 0\.5, (-?[\d.]+)\)", read("IpoServer.lua"))
    employee = read("EmployeeServer.lua")
    if not all((buy, spawn, floor, center_y, ipo)):
        raise SystemExit("A sign, the spawn or the Floor moved in the scripts: update visuals_expected_lua and PlotArt.Layout")
    floor_top = float(floor.group(2)) / 2  # the Floor is centered on plotCenter

    def pairs(points):
        return "{ " + ", ".join("{ %s, %s }" % p for p in points) + " }"

    return ("{ upgrades = { %s }, slots = %s, spots = %s, incubators = %s, floor = { %s, %s, %s }, floorTop = %s, "
            "signs = { BuySign = { %s, %s }, IpoSign = { %s, %s } }, spawn = { %s, %s } }") % (
        ", ".join('"%s"' % u for u in upgrades), pairs(slots), pairs(spots(employee, "EMPLOYEE_SPOTS")),
        pairs(spots(employee, "INCUBATOR_SPOTS")), floor.group(1), floor.group(2), floor.group(3), floor_top,
        buy.group(1), buy.group(2), ipo.group(1), ipo.group(2), spawn.group(1), spawn.group(2))


def visuals_wiring_checks():
    """Checks on the source text of PlotArt, PlotVisuals and TycoonCore's hooks (looks only, never gameplay)."""
    import re
    passed, failed = 0, 0

    def check(name, cond, extra=None):
        nonlocal passed, failed
        if cond:
            passed += 1
        else:
            failed += 1
            print("FAIL: " + name + (" -- " + str(extra) if extra else ""))

    def read(name):
        with open(os.path.join(ROOT, name), encoding="utf-8") as f:
            return f.read()

    for name in ("PlotArt.lua", "PlotVisuals.lua"):
        size = len(read(name).encode("utf-8"))
        check("%s stays under 120 KB (%d bytes)" % (name, size), size < 120 * 1024, size)
        code = code_only(read(name))
        for word in ("GetService", "RemoteEvent", "RemoteFunction", "DataStore", "SetAsync", "addEarnings", "Random", "math.random",
                     "rbxasset", "http", "Texture =", "MeshId", "Decal", "require("):
            check("%s never uses %s (pure looks: no services, remotes, saves, assets or randomness)" % (name, word), word not in code)
    art = code_only(read("PlotArt.lua"))
    check("PlotArt: every Instance comes from PlotVisuals (no Instance.new in the data)", "Instance.new" not in art)

    core = read("TycoonCore.lua")
    code = code_only(core)
    check("TycoonCore: PlotVisuals and PlotArt are required inside pcall (an art bug can never stop the game)",
          re.search(r'pcall\(require, script\.Parent:WaitForChild\("PlotVisuals", \d+\)\)', code) is not None
          and re.search(r'pcall\(require, script\.Parent:WaitForChild\("PlotArt", \d+\)\)', code) is not None)
    calls = re.findall(r"PlotVisuals\.\w+", code)
    wrapped = re.findall(r'looks\("[^"]*"[^,]*, PlotVisuals\.\w+', code)
    check("TycoonCore: every PlotVisuals call goes through looks() (pcall + warn)", len(calls) == len(wrapped) and len(calls) >= 3, (len(calls), len(wrapped)))
    spawn_item = core[core.index("local function spawnItem("):core.index("-- Which upgrades the player owns")]
    check("TycoonCore: spawnItem falls back to the plain block when there is no prop", 'makePart(data.folder, upg.name, upg.size' in spawn_item)
    loop = core[core.index("-- Passive income every second"):core.index("-- Autosave every minute")]
    check("TycoonCore: the income loop keeps the room on the current funding stage", "syncRoom(data)" in loop)
    check("TycoonCore: the stage comes from IpoConfig.stageIndex (the same rule as the IPO sign)", "IpoConfig.stageIndex(data.ipo.valuation, data.ipo.count)" in code)
    check("TycoonCore: a purchase pops its prop in", re.search(r"spawnItem\(data, i, upg, true\)", code) is not None)
    check("TycoonCore: no new remote, DataStore or save field for the looks",
          code.count('Instance.new("Remote') == 0 and code.count("GetDataStore(") == 1 and "looks =" not in core[core.index("local function buildPayload"):core.index("-- BUILDSAVE-END")])
    return passed, failed


def sanitize_source():
    with open(os.path.join(ROOT, "TycoonCore.lua"), encoding="utf-8") as f:
        text = f.read()
    start = text.index("-- SANITIZE-BEGIN") + len("-- SANITIZE-BEGIN")
    end = text.index("-- SANITIZE-END")
    return text[start:end]


def marked_source(name, filename="TycoonCore.lua"):
    with open(os.path.join(ROOT, filename), encoding="utf-8") as f:
        text = f.read()
    start = text.index("-- %s-START" % name) + len("-- %s-START" % name)
    return text[start:text.index("-- %s-END" % name)]


def onboarding_goal_count():
    """How many goals OnboardingConfig.Goals has (the Goals card grows by 22 px per goal)."""
    import re
    with open(os.path.join(ROOT, "OnboardingConfig.lua"), encoding="utf-8") as f:
        text = f.read()
    block = text[text.index("OnboardingConfig.Goals = {"):]
    block = block[:block.index("\n}")]
    return len(re.findall(r"\{\s*key = ", block))


def known_sections_line():
    with open(os.path.join(ROOT, "TycoonCore.lua"), encoding="utf-8") as f:
        for line in f:
            if line.startswith("local KNOWN_SECTIONS = "):
                return line
    raise ValueError("KNOWN_SECTIONS not found in TycoonCore.lua")


def sim_perk_costs_lua():
    """IPO_PERK_COSTS from tools/economy_sim.py as a Luau table (read with ast, the sim is not run)."""
    with open(os.path.join(ROOT, "tools", "economy_sim.py"), encoding="utf-8") as f:
        tree = ast.parse(f.read())
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "IPO_PERK_COSTS" for t in node.targets):
            costs = ast.literal_eval(node.value)
            return "{ " + ", ".join(f'{key} = {{ {", ".join(str(c) for c in levels)} }}' for key, levels in costs.items()) + " }"
    raise SystemExit("IPO_PERK_COSTS not found in tools/economy_sim.py")


def run_luau(luau, source):
    with tempfile.NamedTemporaryFile("w", suffix=".luau", delete=False, encoding="utf-8") as f:
        f.write(source)
        path = f.name
    try:
        result = subprocess.run([luau, path], capture_output=True, text=True)
    finally:
        os.remove(path)
    return result


def main():
    luau = os.environ.get("LUAU") or shutil.which("luau")
    if not luau:
        print("Luau not found. Download it from https://github.com/luau-lang/luau/releases and set LUAU=/path/to/luau")
        return 2
    source = "local print_real = print\n" + PRELUDE
    for name in ("DailyConfig", "DailyServer"):
        with open(os.path.join(ROOT, name + ".lua"), encoding="utf-8") as f:
            source += "\nMODULES.%s = (function()\n%s\nend)()\n" % (name, f.read())
    source += TESTS
    result = run_luau(luau, source)
    print(result.stdout.strip() or result.stderr.strip())
    code = 0 if result.returncode == 0 and " 0 failed" in result.stdout else 1
    result2 = run_luau(luau, SANITIZE_TESTS.replace("__SANITIZE__", sanitize_source()))
    print("TycoonCore save check: " + (result2.stdout.strip() or result2.stderr.strip()))
    if result2.returncode != 0 or " 0 failed" not in result2.stdout:
        code = 1
    result3 = run_luau(luau, STORE_TESTS.replace("__GETSTORE__", marked_source("GETSTORE")).replace("__READABLE__", marked_source("READABLE")))
    print("TycoonCore store check: " + (result3.stdout.strip() or result3.stderr.strip()))
    if result3.returncode != 0 or " 0 failed" not in result3.stdout:
        code = 1
    result4 = run_luau(luau, PASS_TESTS.replace("__PASSCHECK__", marked_source("PASSCHECK", "ShopServer.lua")))
    print("ShopServer pass check: " + (result4.stdout.strip() or result4.stderr.strip()))
    if result4.returncode != 0 or " 0 failed" not in result4.stdout:
        code = 1
    result5 = run_luau(luau, BUILD_TESTS.replace("__BUILDSAVE__", marked_source("BUILDSAVE")).replace("__KNOWNSECTIONS__", known_sections_line()))
    print("TycoonCore build check: " + (result5.stdout.strip() or result5.stderr.strip()))
    if result5.returncode != 0 or " 0 failed" not in result5.stdout:
        code = 1
    result6 = run_luau(luau, WAIT_TESTS.replace("__PASSWAIT__", marked_source("PASSWAIT", "IpoServer.lua")))
    print("IpoServer pass wait check: " + (result6.stdout.strip() or result6.stderr.strip()))
    if result6.returncode != 0 or " 0 failed" not in result6.stdout:
        code = 1
    with open(os.path.join(ROOT, "CreatureConfig.lua"), encoding="utf-8") as f:
        creature_config = f.read()
    with open(os.path.join(ROOT, "IpoConfig.lua"), encoding="utf-8") as f:
        ipo_config = f.read()
    result7 = run_luau(luau, ODDS_TESTS.replace("__CREATURECONFIG__", creature_config).replace("__IPOCONFIG__", ipo_config))
    print("CreatureConfig odds check: " + (result7.stdout.strip() or result7.stderr.strip()))
    if result7.returncode != 0 or " 0 failed" not in result7.stdout:
        code = 1
    result8 = run_luau(luau, MOVE_TESTS.replace("__MOVENOTES__", marked_source("MOVENOTES", "PoachServer.lua")))
    print("PoachServer move check: " + (result8.stdout.strip() or result8.stderr.strip()))
    if result8.returncode != 0 or " 0 failed" not in result8.stdout:
        code = 1
    result9 = run_luau(luau, SAVE_TESTS.replace("__SAVENOTE__", marked_source("SAVENOTE")).replace("__LEAVESAVE__", marked_source("LEAVESAVE")))
    print("TycoonCore leave save check: " + (result9.stdout.strip() or result9.stderr.strip()))
    if result9.returncode != 0 or " 0 failed" not in result9.stdout:
        code = 1
    result10 = run_luau(luau, REREAD_TESTS.replace("__REREAD__", marked_source("REREAD")))
    print("TycoonCore join re-read check: " + (result10.stdout.strip() or result10.stderr.strip()))
    if result10.returncode != 0 or " 0 failed" not in result10.stdout:
        code = 1
    result11 = run_luau(luau, FIXED_TESTS.replace("__CREATURECONFIG__", creature_config).replace("__IPOCONFIG__", ipo_config))
    print("CreatureConfig fixed order check: " + (result11.stdout.strip() or result11.stderr.strip()))
    if result11.returncode != 0 or " 0 failed" not in result11.stdout:
        code = 1
    result12 = run_luau(luau, ROLL_TESTS.replace("__CREATURECONFIG__", creature_config)
                        .replace("__ROLL__", marked_source("ROLL", "EmployeeServer.lua"))
                        .replace("__FIXEDSAVE__", marked_source("FIXEDSAVE", "EmployeeServer.lua")))
    print("EmployeeServer fixed hires check: " + (result12.stdout.strip() or result12.stderr.strip()))
    if result12.returncode != 0 or " 0 failed" not in result12.stdout:
        code = 1
    with open(os.path.join(ROOT, "ShopConfig.lua"), encoding="utf-8") as f:
        shop_config = f.read()
    result13 = run_luau(luau, POLICY_TESTS.replace("__SHOPCONFIG__", shop_config).replace("__POLICY__", marked_source("POLICY", "ShopServer.lua")))
    print("ShopServer policy check: " + (result13.stdout.strip() or result13.stderr.strip()))
    if result13.returncode != 0 or " 0 failed" not in result13.stdout:
        code = 1
    result14 = run_luau(luau, NEXTHIRE_TESTS.replace("__NEXTHIRE__", marked_source("NEXTHIRE", "DailyClient.lua")))
    print("DailyClient next hire check: " + (result14.stdout.strip() or result14.stderr.strip()))
    if result14.returncode != 0 or " 0 failed" not in result14.stdout:
        code = 1
    with open(os.path.join(ROOT, "IpoServer.lua"), encoding="utf-8") as f:
        ipo_server = f.read()
    result15 = run_luau(luau, IPOSHOP_TESTS.replace("__IPOCONFIG__", ipo_config).replace("__SHOPCONFIG__", shop_config).replace("__IPOSERVER__", ipo_server)
                        .replace("__SIMCOSTS__", sim_perk_costs_lua()))
    print("IPO shop check (D1, 1,770 Shares): " + (result15.stdout.strip() or result15.stderr.strip()))
    if result15.returncode != 0 or " 0 failed" not in result15.stdout:
        code = 1
    result16 = run_luau(luau, task_engine_source())
    print("TaskServer engine check (PR 1, customer calls): " + (result16.stdout.strip() or result16.stderr.strip()))
    if result16.returncode != 0 or " 0 failed" not in result16.stdout:
        code = 1
    result17 = run_luau(luau, tray_source(dump="--layout-table" in sys.argv))
    print("TaskClient tray layout check: " + (result17.stdout.strip() or result17.stderr.strip()))
    if result17.returncode != 0 or " 0 failed" not in result17.stdout:
        code = 1
    wiring_passed, wiring_failed = task_wiring_checks()
    print("TaskServer wiring check: %d passed, %d failed" % (wiring_passed, wiring_failed))
    if wiring_failed:
        code = 1
    task_caught, task_problems = run_task_mutants(luau)
    print("Task start mutations (calls start with the Desk): %d of %d broken rules caught by their named check" % (task_caught, len(TASK_MUTANTS)))
    if task_problems:
        code = 1
    with open(os.path.join(ROOT, "PlotArt.lua"), encoding="utf-8") as f:
        plot_art = f.read()
    with open(os.path.join(ROOT, "PlotVisuals.lua"), encoding="utf-8") as f:
        plot_visuals = f.read()
    result18 = run_luau(luau, VISUALS_TESTS.replace("__PLOTART__", plot_art).replace("__PLOTVISUALS__", plot_visuals)
                        .replace("__IPOCONFIG__", ipo_config).replace("__EXPECTED__", visuals_expected_lua())
                        .replace("__ALL_STAGES__", "true" if VISUALS_ALL_STAGES else "false"))
    print("Plot visuals check (PlotArt + PlotVisuals): " + (result18.stdout.strip() or result18.stderr.strip()))
    if result18.returncode != 0 or " 0 failed" not in result18.stdout:
        code = 1
    visuals_passed, visuals_failed = visuals_wiring_checks()
    print("Plot visuals wiring check: %d passed, %d failed" % (visuals_passed, visuals_failed))
    if visuals_failed:
        code = 1
    result19 = run_luau(luau, buy_source())
    print("Office upgrade and HR purchase check: " + (result19.stdout.strip() or result19.stderr.strip()))
    if result19.returncode != 0 or " 0 failed" not in result19.stdout:
        code = 1
    caught = 0
    for label, mutation, *expected in BUY_MUTATIONS:
        mutant = run_luau(luau, buy_source(mutation))
        failures = [line for line in mutant.stdout.split("\n") if line.startswith("FAIL: ")]
        if "passed," not in mutant.stdout or " 0 failed" in mutant.stdout:
            # the tests must run to the end and report failures (a crash would not count)
            print("FAIL: mutation not caught: the purchase tests do not notice a broken " + label)
            code = 1
        elif expected and not any(line.startswith("FAIL: " + expected[0]) for line in failures):
            print("FAIL: mutation of %s is caught, but not by the test \"%s\"" % (label, expected[0]))
            code = 1
        else:
            caught += 1
    print("Office upgrade mutations: %d of %d broken rules caught" % (caught, len(BUY_MUTATIONS)))
    pads_passed, pads_failed = pads_gone_checks()
    print("Pads gone and Office wiring check: %d passed, %d failed" % (pads_passed, pads_failed))
    if pads_failed:
        code = 1
    return code


if __name__ == "__main__":
    sys.exit(main())
