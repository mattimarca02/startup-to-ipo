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
check("... every section is there", payload.shop and payload.team and payload.poach and payload.ipo and payload.onboarding and payload.daily)
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

for _, name in ipairs({ "shop", "team", "poach", "ipo", "onboarding", "daily", "fixedHires" }) do
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
    return code


if __name__ == "__main__":
    sys.exit(main())
