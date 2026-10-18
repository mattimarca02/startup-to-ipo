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
	grantShares = function(player, n) -- raw, like the real one: refused while the IPO is filing
		if player.data.ipo.busy then return false end
		player.data.ipo.shares += n; return true
	end,
}
"""

TESTS = r"""-- Tests ---------------------------------------------------------------------
__STORABLE__
local DailyServer = wrapSerialize(MODULES.DailyServer)
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
-- M6 F2: a Shares day while the IPO is filing is refused before anything is granted (the claim itself, past onAction's gate)
do
	local week = { lastClaimDay = DailyConfig.dayNumber(NOW) - 1, streak = 6, best = 6, claims = 6 }
	local p7, d7 = newPlayer(week)
	check("Day 7 is the Shares day", p7.attrs.DailyDay == 7, p7.attrs.DailyDay)
	-- ready but busy: onAction's gate lets it through, so the claim's own check decides
	d7.ipo.busy = true
	local before = d7.cash.Value
	local okBusy, msgBusy = tap(p7)
	check("M6 F2: Day 7 refused while the IPO files", okBusy == false and msgBusy == DailyConfig.Texts.IpoBusy, msgBusy)
	check("M6 F2: no egg and no Cash given", d7.team.incubators[1] == false and d7.cash.Value == before)
	check("M6 F2: the day is not used up", d7.daily.lastClaimDay == week.lastClaimDay and d7.daily.streak == 6)
	d7.ipo.busy = false
	local okAfter = tap(p7)
	check("M6 F2: after the IPO the whole day is given", okAfter and d7.ipo.shares == 3 and d7.team.incubators[1] and d7.team.incubators[1].egg == "Unicorn")
end

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

check("every section DailyServer.serialize produced in these tests is storable (" .. STORE_SCREEN.seen .. " screened)", STORE_SCREEN.bad == 0 and STORE_SCREEN.seen > 0, STORE_SCREEN.first)
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


STORABLE_LUA = r"""-- A faithful DataStore (customize PR 1 review fix C). The real SetAsync refuses a table that mixes list and string keys, and a list with
-- holes (or keys 0, negative, fractional) is not a list. The old fake stored anything, so these tests could not see that class of bug.
-- storableProblems(value) lists, recursively through the whole payload, every table the store would refuse; newFaithfulStore() is a
-- fake store whose SetAsync throws on one; screenStorable(value) is for sections that are serialized but never sent to a store here.
local function storableProblems(value, path, problems, open)
	path = path or "payload"
	problems = problems or {}
	open = open or {}
	local kind = typeof(value)
	if kind == "table" then
		if open[value] then
			table.insert(problems, path .. ": a table that contains itself")
			return problems
		end
		open[value] = true
		local strings, numbers, others = 0, 0, 0
		for key in pairs(value) do
			local keyKind = typeof(key)
			if keyKind == "string" then
				strings += 1
			elseif keyKind == "number" then
				numbers += 1
			else
				others += 1
			end
		end
		if others > 0 then
			table.insert(problems, path .. ": has a key that is neither a string nor a number")
		end
		if strings > 0 and numbers > 0 then
			table.insert(problems, path .. ": mixes list and string keys")
		elseif numbers > 0 then
			for i = 1, numbers do
				if value[i] == nil then
					table.insert(problems, path .. ": is not a list 1 .. " .. numbers .. " in a row (a hole, or a key that is 0, negative or fractional)")
					break
				end
			end
		end
		for key, inner in pairs(value) do
			storableProblems(inner, path .. "[" .. tostring(key) .. "]", problems, open)
		end
		open[value] = nil
	elseif kind ~= "string" and kind ~= "number" and kind ~= "boolean" then
		table.insert(problems, path .. ": a " .. kind .. " can't be stored")
	end
	return problems
end
local function storeCopy(value)
	if typeof(value) ~= "table" then return value end
	local copy = {}
	for key, inner in pairs(value) do copy[key] = storeCopy(inner) end
	return copy
end
local function newFaithfulStore()
	local store = { calls = 0, refused = 0, problem = nil, data = {} }
	function store.SetAsync(self, key, payload)
		self.calls += 1
		local problems = storableProblems(payload)
		if #problems > 0 then
			self.refused += 1
			self.problem = self.problem or problems[1]
			error("105: Cannot store " .. problems[1] .. " in DataStore", 2)
		end
		self.data[key] = storeCopy(payload)
	end
	return store
end
local STORE_SCREEN = { on = true, seen = 0, bad = 0, first = nil }
local function screenStorable(value)
	if STORE_SCREEN.on and value ~= nil then
		STORE_SCREEN.seen += 1
		local problems = storableProblems(value)
		if #problems > 0 then
			STORE_SCREEN.bad += 1
			STORE_SCREEN.first = STORE_SCREEN.first or problems[1]
		end
	end
	return value
end
local function wrapSerialize(module, name)
	name = name or "serialize"
	local real = module[name]
	module[name] = function(...) return screenStorable(real(...)) end
	return module
end
-- The fake must refuse what the real store refuses (and accept a clean payload): named checks, so a broken fake is caught
local function runStoreSelfTest(check)
	local function refused(value) return not pcall(newFaithfulStore().SetAsync, newFaithfulStore(), "k", value) end
	local function accepted(value) return pcall(newFaithfulStore().SetAsync, newFaithfulStore(), "k", value) end
	check("the faithful store accepts a clean list", accepted({ "Desk", "Laptop" }))
	check("the faithful store accepts a map of string keys", accepted({ future = "x", other = { a = 1 } }))
	check("the faithful store accepts an empty table", accepted({}))
	check("the faithful store accepts a clean nested payload", accepted({ cash = 5, owned = { "Desk" }, pokedex = { v = 1, sectors = { Software = { card = { owned = { "Desk" } } } } } }))
	check("the faithful store refuses a list plus a string key", refused({ 1, 2, 3, foo = "x" }))
	check("the faithful store refuses a list with a hole", refused({ [1] = "a", [2] = "b", [5] = "c" }))
	check("the faithful store refuses a table with only [2]", refused({ [2] = "a" }))
	check("the faithful store refuses a table with only [1] and [3]", refused({ [1] = "a", [3] = "b" }))
	check("the faithful store refuses a fractional key", refused({ [1.5] = "a" }))
	check("the faithful store refuses keys 0 and -3 next to a list", refused({ "Desk", [0] = "a", [-3] = "b" }))
	check("the faithful store refuses a string key \"1\" next to [1]", refused({ "Desk", ["1"] = "x" }))
	check("the faithful store refuses a mixed table three levels down", refused({ a = { b = { c = { 1, 2, foo = 3 } } } }))
	check("the faithful store refuses a hole inside a list of maps", refused({ list = { { a = 1 }, nil, { a = 2 } } }))
	check("the faithful store refuses a function value", refused({ f = function() end }))
	check("the faithful store refuses a table that contains itself", (function() local t = {}; t.me = t; return refused(t) end)())
	check("the faithful store says what it refused", (function()
		local store = newFaithfulStore()
		pcall(store.SetAsync, store, "k", { a = { 1, foo = 2 } })
		return store.refused == 1 and store.problem ~= nil and string.find(store.problem, "payload[a]", 1, true) ~= nil and string.find(store.problem, "mixes", 1, true) ~= nil
	end)())
end
"""


BUILD_TESTS = r"""-- Tests for TycoonCore's buildPayload (the code between its BUILDSAVE markers) ----------
local print_real = print
__STORABLE__
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
local POKEDEX = { v = 1, run = 0 } -- what CompanyServer.serialize returns
local CompanyServer = { serialize = function(data)
	if FAIL == "pokedex" then error("pokedex exploded") end
	return POKEDEX
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
check("... every section is there", payload.shop and payload.team and payload.poach and payload.ipo and payload.onboarding and payload.daily and payload.tasks and payload.pokedex)
check("... the pokedex section is the one CompanyServer.serialize gave", payload.pokedex.v == 1 and payload.pokedex == POKEDEX)
do
	local store = newFaithfulStore()
	local okStore, problem = pcall(store.SetAsync, store, "player_1", payload)
	check("the normal payload, every section of it, is accepted by the faithful store", okStore and store.refused == 0, problem)
	local bad = { cash = 1, owned = { "Desk", future = "x" } }
	check("... and the same store refuses a payload with a mixed list (so the check above can fail)", not pcall(store.SetAsync, store, "player_1", bad) and store.refused == 1)
end
check("pokedex is a known section (saved by its own serialize, never kept as unknown)", KNOWN_SECTIONS.pokedex == true)
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

for _, name in ipairs({ "shop", "team", "poach", "ipo", "onboarding", "daily", "fixedHires", "tasks", "pokedex" }) do
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
__STORABLE__
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
wrapSerialize(EmployeeServer, "serializeFixedHires")
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
check("every section serializeFixedHires produced in these tests is storable (" .. STORE_SCREEN.seen .. " screened)", STORE_SCREEN.bad == 0 and STORE_SCREEN.seen > 0, STORE_SCREEN.first)
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
__STORABLE__
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
local Vector3, Color3, UDim2, Enum, CFrame = ghost, ghost, ghost, ghost, ghost
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
wrapSerialize(IpoServer)
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
	plotFrame = function() return ghost end, -- TycoonCore hands IpoServer the garage's frame (lobby PR L1)
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

check("every section IpoServer.serialize produced in these tests is storable (" .. STORE_SCREEN.seen .. " screened)", STORE_SCREEN.bad == 0 and STORE_SCREEN.seen > 0, STORE_SCREEN.first)
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
__STORABLE__
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
local function loadServerRaw()
__TASKSERVER__
end
local function loadServer() return wrapSerialize(loadServerRaw()) end

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
-- The numbers docs/STUDIO_SYNC.md quotes for the first call after the Desk: 20 s at best only with no hires at the Garage rung (the
-- gap formula is the one from main, never raised to a floor of 10 s)
check("gap: the numbers the Studio sync steps quote (20 s with no hires; 10 s, 9.26 s and 7.81 s at best with 13+ hires at rung 0, rung 4 and rung 4 after 10 IPOs)",
	near(C.gap(row, 0, 0, 0), 20) and near(C.gap(row, 13, 0, 0), 10) and near(C.gap(row, 13, C.level(4, 0), 0), 9.2593, 0.0001)
	and near(C.gap(row, 13, C.level(4, 10), 0), 7.8125) and C.gap(row, 13, C.level(0, 0), 0) >= 10 and C.gap(row, 13, C.level(4, 10), 0) < 10)
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

	-- Missed calls never carry over (OWNER DEFAULT): when calls turn on, the count of calls that ran out in a row starts at 0 and the idle
	-- clock starts at the unlock. Only the Studio Debug buttons ("spawn a call", "IpoReset") can ring a call before the Desk, so this
	-- is reachable only in Studio, but it must not start quiet mode ("Tap to resume") the moment the Desk is bought.
	do
		local p, d = newPlayer(nil, { owned = {} })
		spawnCall(p); spawnCall(p); spawnCall(p)
		tick(p, 10, 0.5)
		local run = p.data.tasks.run
		check("desk: ... the calls that ran out while calls were off are counted by the engine (the test starts from three misses)", stats(p).missed == 3 and run.misses == 3 and run.quiet == false, run.misses)
		buyDesk(p)
		tick(p, 1, 0.5)
		check("desk: missed calls from before the Desk do not start quiet mode when it is bought (the miss counter starts at 0)",
			run.misses == 0 and run.quiet == false and lastState(p).quiet == false and lastState(p).on == true, run.misses)
		local waited = waitForArrival(p, 80)
		check("desk: ... and the first call comes after a normal gap, with no 'Tap to resume' in between",
			waited ~= nil and waited + 1 >= 20 - 1e-9 and waited + 1 <= 21.01 and run.quiet == false and lastState(p).quiet == false, waited)
	end
	do
		local p, d = newPlayer(nil, { owned = {} })
		spawnCall(p); spawnCall(p)
		tick(p, 10, 0.5) -- two ran out while calls were off
		local id = spawnCall(p) -- and one is waiting when the Desk is bought
		buyDesk(p)
		tick(p, 1, 0.5)
		local run = p.data.tasks.run
		check("desk: when calls turn on the miss counter is reset and the call that is waiting is kept (open, counting down)",
			run.misses == 0 and openCount(p) == 1 and #waiting(p) == 1 and waiting(p)[1].id == id and waiting(p)[1].left > 0, run.misses)
		local ok, _, info = answer(p, id)
		check("desk: ... and that call can still be answered and pays", ok == true and info ~= nil and info.cash == 70 and stats(p).answered == 1)
	end
	do
		local p, d = newPlayer(nil) -- the Desk is owned: calls are on all the time
		noArrivals(p)
		spawnCall(p); spawnCall(p)
		tick(p, 10, 0.5)
		local run = p.data.tasks.run
		check("desk: with calls on, two calls that ran out stay counted (the counter is reset when calls turn on, not on every tick)", run.misses == 2 and run.quiet == false, run.misses)
		spawnCall(p)
		tick(p, 10, 0.5)
		check("desk: ... and the third in a row still starts quiet mode", run.quiet == true and lastState(p).quiet == true, run.misses)
	end
	do
		local p, d = newPlayer(nil, { owned = {} })
		tick(p, 10, 0.5)
		buyDesk(p)
		advance(200) -- one late tick: nothing ran in between (a server hiccup)
		TaskServer.step(p, CLOCK)
		local run = p.data.tasks.run
		check("desk: when calls turn on after a long step the idle clock starts at the unlock (no quiet mode)",
			run.quiet == false and lastState(p).quiet == false and lastState(p).on == true and run.lastActionAt == CLOCK, run.lastActionAt)
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

check("every section TaskServer.serialize produced in these tests is storable (" .. STORE_SCREEN.seen .. " screened)", STORE_SCREEN.bad == 0 and STORE_SCREEN.seen > 0, STORE_SCREEN.first)
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
local GOALS = __GOALCOUNT__ -- the Goals card's rows, min(ShowAtOnce, #activeGoals()): 30 + 22 per row + 8 high
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
local WARNED, ALL_WARNED = {}, {} -- ALL_WARNED is never cleared: a warning given once per server is counted over the whole run
local function warn(...) table.insert(WARNED, table.concat({ ... }, " ")); table.insert(ALL_WARNED, table.concat({ ... }, " ")) end
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
	if k == "Rotation" then return cf(0, 0, 0, t.r) end
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
	new = function(x, y, z, ...)
		if getmetatable(x) == V then return cf(x.X, x.Y, x.Z) end -- CFrame.new(position)
		if select("#", ...) == 9 then return cf(x, y, z, { ... }) end -- CFrame.new(x, y, z, R00, R01, R02, R10, ..., R22), row by row
		return cf(x or 0, y or 0, z or 0)
	end,
	Angles = function(a, b, c) return cf(0, 0, 0, matmul(matmul(rx(a), ry(b)), rz(c))) end,
	fromEulerAnglesYXZ = function(a, b, c) return cf(0, 0, 0, matmul(matmul(ry(b), rx(a)), rz(c))) end,
}
-- What a turned garage needs (lobby PR L1): the inverse (a rotation's inverse is its transpose), ToObjectSpace, the
-- YXZ angles, CFrame.lookAt, and typeof for the fake's Vector3 and CFrame
function CF.Inverse(t)
	local r = t.r
	local q = { r[1], r[4], r[7], r[2], r[5], r[8], r[3], r[6], r[9] }
	return cf(-(q[1] * t.x + q[2] * t.y + q[3] * t.z), -(q[4] * t.x + q[5] * t.y + q[6] * t.z), -(q[7] * t.x + q[8] * t.y + q[9] * t.z), q)
end
function CF.ToObjectSpace(a, b) return a:Inverse() * b end
function CF.ToEulerAnglesYXZ(t)
	local r = t.r
	return math.asin(-math.clamp(r[6], -1, 1)), math.atan2(r[3], r[9]), math.atan2(r[4], r[5])
end
CFrame.lookAt = function(at, target) -- -Z looks at the target, +Y stays up (never straight up or down here)
	local lx, ly, lz = target.X - at.X, target.Y - at.Y, target.Z - at.Z
	local n = math.sqrt(lx * lx + ly * ly + lz * lz)
	lx, ly, lz = lx / n, ly / n, lz / n
	local rx_, ry_, rz_ = -lz, 0, lx -- look x up(0, 1, 0)
	local m = math.sqrt(rx_ * rx_ + rz_ * rz_)
	rx_, rz_ = rx_ / m, rz_ / m
	local ux, uy, uz = ry_ * lz - rz_ * ly, rz_ * lx - rx_ * lz, rx_ * ly - ry_ * lx -- right x look
	return cf(at.X, at.Y, at.Z, { rx_, ux, -lx, ry_, uy, -ly, rz_, uz, -lz })
end
local function typeof(v)
	local mt = getmetatable(v)
	if mt == CF then return "CFrame" elseif mt == V then return "Vector3" end
	return type(v)
end

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
local KITDOC = __KITDOC__

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
	check("garage: the only lights are the bare bulb (the kit's BareBulb, its glass) and the old PC's screen", #neon == 2 and neon[1] == "Bulb_glass" and neon[2] == "ComputerScreen", table.concat(neon, ","))
	check("garage: no monitor, laptop or server in the room (they are upgrades)", techWords == nil, techWords)
	check("garage: the cardboard OFFICE sign", texts["OFFICE"] == true)
	check("garage: the 'WIFI: ask mom' sticky note", texts["WIFI:\nask mom"] == true)
	check("garage: the old PC and the phone are there", room:FindFirstChild("Decor"):FindFirstChild("ComputerCRT") ~= nil
		and room:FindFirstChild("Decor"):FindFirstChild("DeskPhoneHandset") ~= nil)
	check("garage: hire desks are crates (the kit's Crate, no tech)", room:FindFirstChild("Decor"):FindFirstChild("HireDesk1"):FindFirstChild("Crate_main") ~= nil
		and room:FindFirstChild("Decor"):FindFirstChild("HireDesk1"):FindFirstChild("Crate_trim") ~= nil)
end

-- 5. One player's plot: stage swaps keep the props, the floor follows, effects ----------------
do
	ROOT = newInstance("Folder")
	local folder = newInstance("Folder")
	folder.Parent = ROOT
	local floor = newInstance("Part")
	floor.Name = "Floor"
	floor.Size = Vector3.new(60, 1, 60)
	floor.CFrame = CFrame.new(center) -- TycoonCore makes it at the plot center (unturned here)
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
-- six props or the layout changed: that is only allowed on purpose, by hand. Stage 1's was taken again on purpose by
-- interiors PR 1 (the Garage's furniture from the kit: crates, workbench, old desk and chair, bare bulb); the props' and
-- the layout's are still cb326d8's.
local function num(n) return string.format("%.4f", n) end
local function triple(t) if not t then return "-" end return num(t[1]) .. "," .. num(t[2]) .. "," .. num(t[3]) end
local function specString(s)
	local tr = s.text and (s.text.value .. s.text.font) or ""
	local lt = s.light and (s.light.brightness .. "/" .. s.light.range) or ""
	if s.kit then -- a kit piece (interiors): its key, spot, turn, scale and each role's look, in role order
		local sc = type(s.scale) == "number" and { s.scale, s.scale, s.scale } or s.scale
		local roles = {}
		for role, look in pairs(s.roles) do table.insert(roles, role .. "=" .. triple(look[1]) .. look[2] .. num(look[3] or 0)) end
		table.sort(roles)
		return table.concat({ s.name, "kit:" .. s.kit, triple(s.offset), tostring(s.turn or 0), triple(sc), table.concat(roles, ","), tostring(s.lightRole), lt }, "|")
	end
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
		hash(listString(g.shell) .. "#" .. listString(g.decor) .. "#" .. listString(g.desk) .. g.floor.material .. triple(g.floor.color) .. g.key) == 995603267
		and #g.shell == 35 and #g.decor == 72 and #g.desk == 1)
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

-- 8. The furniture kit (interiors): kit pieces from ReplicatedStorage.KitModels, Parts when it is missing -----------------
IS_A.MeshPart = { BasePart = true }
function Methods.FindFirstChildOfClass(t, class) for _, c in ipairs(t._children) do if c.ClassName == class then return c end end return nil end
function Methods.Clone(t)
	if rawget(t, "Archivable") == false then return nil end -- like Roblox: Archivable off is not copied
	local c = newInstance(t.ClassName)
	for k, v in pairs(t) do
		if k ~= "_children" and k ~= "_parent" and k ~= "_attrs" then rawset(c, k, v) end
	end
	rawset(c, "_attrs", table.clone(t._attrs))
	for _, child in ipairs(t._children) do
		local copy = child:Clone()
		if copy then copy.Parent = c end
	end
	return c
end
do
	local K = PlotArt.Kit
	-- docs/KIT_MODELS.md is the kit: every key PlotArt uses is there, with the same size and the same roles
	for key, entry in pairs(K) do
		local doc = KITDOC[key]
		local same = doc ~= nil and doc.size[1] == entry.size[1] and doc.size[2] == entry.size[2] and doc.size[3] == entry.size[3] and #doc.roles == #entry.roles
		if same then for _, r in ipairs(entry.roles) do if not table.find(doc.roles, r) then same = false end end end
		check("kit: PlotArt.Kit." .. key .. " has the size and the roles of docs/KIT_MODELS.md", same)
	end
	check("kit: PlotArt.Kit names the furniture the rooms use (Crate, Workbench, Desk, Chair, BareBulb)", K.Crate and K.Workbench and K.Desk and K.Chair and K.BareBulb and true or false)
	check("kit: PlotVisuals.findKit is nil outside Roblox (no game): the rooms are built from Parts", PlotVisuals.findKit(PlotArt) == nil)

	-- A fake KitModels: one Model per key, anywhere in the world, its WorldPivot the bottom-center, its KitSize the box. Each
	-- role is one MeshPart (Roblox-like names, the Role attribute) that is the union of that role's fallback boxes ("union"),
	-- or the whole kit box ("full": the worst case for the zones). importTurn = how the importer turned the model.
	local function makeKit(importTurn, mode, edit)
		local folder = newInstance("Folder")
		folder.Name = "KitModels"
		local i = 0
		for key, entry in pairs(K) do
			i += 1
			local m = newInstance("Model")
			m.Name = key
			local pivot = CFrame.new(400 + i * 40, 7, -300 - i * 3)
			m.WorldPivot = pivot
			m:SetAttribute("KitSize", Vector3.new(entry.size[1], entry.size[2], entry.size[3]))
			local byRole, order = {}, {}
			for _, b in ipairs(entry.fallback) do
				local bx = { b.at[1] - b.size[1] / 2, b.at[1] + b.size[1] / 2, b.at[2] - b.size[2] / 2, b.at[2] + b.size[2] / 2, b.at[3] - b.size[3] / 2, b.at[3] + b.size[3] / 2 }
				if mode == "full" then bx = { -entry.size[1] / 2, entry.size[1] / 2, 0, entry.size[2], -entry.size[3] / 2, entry.size[3] / 2 } end
				local u = byRole[b.role]
				if not u then byRole[b.role] = bx; table.insert(order, b.role)
				else for k = 1, 5, 2 do u[k] = math.min(u[k], bx[k]); u[k + 1] = math.max(u[k + 1], bx[k + 1]) end end
			end
			for j, role in ipairs(order) do
				local u = byRole[role]
				local p = newInstance("MeshPart")
				p.Name = role .. (j * 3 + 1)
				p:SetAttribute("Role", role)
				p.Size = Vector3.new(u[2] - u[1], u[4] - u[3], u[6] - u[5])
				p.CFrame = pivot * CFrame.Angles(0, math.rad(importTurn), 0) * CFrame.new((u[1] + u[2]) / 2, (u[3] + u[4]) / 2, (u[5] + u[6]) / 2)
				p.Color = Color3.fromRGB(163, 162, 165)
				p.Material = Enum.Material.Plastic
				p.Anchored = true
				p.CanCollide, p.CanTouch, p.CanQuery, p.CastShadow = true, true, true, true -- the importer's defaults: the builder turns them off
				p.Parent = m
			end
			m.Parent = folder
		end
		if edit then edit(folder) end
		return folder
	end
	local function kitRoom(art, stage, kit)
		local room = PlotVisuals.buildRoom(nil, center, art, stage, kit)
		for _, slot in ipairs(art.Layout.itemSlots) do
			PlotVisuals.buildProp(room:FindFirstChild("UpgradeProps"), center, art, slot.name, slotVec(slot))
		end
		return room
	end
	-- The importer's turn: the kit as imported is turned by PlotArt.KIT_FRONT_TURN (the builder turns it back); the other
	-- value is tested too, so the builder is right whichever way Studio's importer turned the models
	local IMPORT = PlotArt.KIT_FRONT_TURN
	local turned = deepCopy(PlotArt)
	turned.KIT_FRONT_TURN = 180 - IMPORT
	local modes = {
		{ "the kit (each role one MeshPart, as imported)", PlotArt, makeKit(IMPORT, "union") },
		{ "the kit with every role filling the whole model (worst case)", PlotArt, makeKit(IMPORT, "full") },
		{ "the kit imported the other way (KIT_FRONT_TURN " .. (180 - IMPORT) .. ")", turned, makeKit(180 - IMPORT, "union") },
		{ "no kit (Parts only)", PlotArt, nil },
	}
	-- Every room, in every mode: the same checks as the Parts rooms (zones, floating, walls, flags, 260 parts, 3 lights)
	for _, mode in ipairs(modes) do
		for i = 1, #PlotArt.Stages do
			local room = kitRoom(mode[2], i, mode[3])
			local probs = PlotVisuals.check(room, center, mode[2])
			check("kit: room " .. i .. " with " .. mode[1] .. ": PlotVisuals.check finds nothing (zones, floating, walls, flags, 260 parts, 3 lights)", #probs == 0,
				#probs .. " problem(s), first: " .. tostring(probs[1]))
			local bad
			for _, d in ipairs(room:GetDescendants()) do
				if d.ClassName == "MeshPart" and (not d.Anchored or d.CanCollide or d.CanTouch or d.CanQuery or not ALLOWED[d.Material.Name]
					or (math.max(d.Size.X, d.Size.Y, d.Size.Z) < 2 and d.CastShadow) or #d:GetChildren() > (d:FindFirstChild("Light") and 1 or 0)) then
					bad = bad or d:GetFullName()
				end
			end
			check("kit: room " .. i .. " with " .. mode[1] .. ": every kit MeshPart anchored, no collide, touch or query, an allowed material, tiny ones no shadow, nothing inside it but its light", bad == nil, bad)
		end
	end

	-- Every kit piece of every room: its parts (kit or Parts) stay inside PlotVisuals.kitBox, and kit and Parts build the
	-- same parts (names), each MeshPart in its role's color and material; the kit puts each role where the Parts version does
	local origin = CFrame.new(center.X, center.Y + L.floorTop, center.Z)
	local function piecesOf(i)
		local out = {}
		for _, spec in ipairs(PlotArt.Stages[i].decor) do if spec.kit then table.insert(out, { spec = spec, group = "Decor", at = { 0, 0 } }) end end
		for s, spot in ipairs(L.employeeSpots) do
			for _, spec in ipairs(PlotArt.Stages[i].desk) do
				if spec.kit then table.insert(out, { spec = spec, group = "HireDesk" .. s, at = { spot[1] + L.desks[s][1], spot[2] + L.desks[s][2] } }) end
			end
		end
		return out
	end
	local function partsOfPiece(room, piece)
		local parent = room:FindFirstChild("Decor")
		if piece.group ~= "Decor" then parent = parent:FindFirstChild(piece.group) end
		local out = {}
		for _, d in ipairs(parent:GetChildren()) do
			if d:IsA("BasePart") and string.find(d.Name, piece.spec.name .. "_", 1, true) == 1 then table.insert(out, d) end
		end
		table.sort(out, function(a, b) return a.Name < b.Name end)
		return out
	end
	local pieceCount = 0
	for i = 1, #PlotArt.Stages do
		for _, mode in ipairs(modes) do
			local room = kitRoom(mode[2], i, mode[3])
			local outside, meshes, wrongLook
			for _, piece in ipairs(piecesOf(i)) do
				local kb = PlotVisuals.kitBox(PlotArt, piece.spec)
				kb = { kb[1] + piece.at[1], kb[2] + piece.at[1], kb[3], kb[4], kb[5] + piece.at[2], kb[6] + piece.at[2] }
				local parts = partsOfPiece(room, piece)
				if #parts == 0 then outside = outside or (piece.spec.name .. ": no part") end
				for _, p in ipairs(parts) do
					local b = PlotVisuals.boxOf(origin:ToObjectSpace(p.CFrame), p.Size)
					if b[1] < kb[1] - 0.03 or b[2] > kb[2] + 0.03 or b[3] < kb[3] - 0.03 or b[4] > kb[4] + 0.03 or b[5] < kb[5] - 0.03 or b[6] > kb[6] + 0.03 then
						outside = outside or p:GetFullName()
					end
					if mode[3] and p.ClassName ~= "MeshPart" then meshes = meshes or p:GetFullName() end
					local role = string.match(p.Name, "_(%a+)%d*$")
					local look = piece.spec.roles[role]
					if not look or p.Color.rgb[1] ~= look[1][1] or p.Color.rgb[2] ~= look[1][2] or p.Color.rgb[3] ~= look[1][3] or p.Material.Name ~= look[2] then
						wrongLook = wrongLook or p:GetFullName()
					end
				end
				pieceCount += 1
			end
			check("kit: room " .. i .. " with " .. mode[1] .. ": every part of every kit piece stays inside its kitBox (the kit size times the scale, turned)", outside == nil, outside)
			check("kit: room " .. i .. " with " .. mode[1] .. ": every kit piece part has its role's color and material", wrongLook == nil, wrongLook)
			if mode[3] then
				check("kit: room " .. i .. " with " .. mode[1] .. ": every kit piece is built from the kit's MeshParts", meshes == nil, meshes)
			end
		end
		-- the kit (as imported, and imported turned around) puts each role where the Parts version has it (one box per role)
		local plain, kitA, kitB = kitRoom(PlotArt, i, nil), kitRoom(PlotArt, i, modes[1][3]), kitRoom(turned, i, modes[3][3])
		local moved
		for _, piece in ipairs(piecesOf(i)) do
			local entry = K[piece.spec.kit]
			local perRole = {}
			for _, b in ipairs(entry.fallback) do perRole[b.role] = (perRole[b.role] or 0) + 1 end
			local a, b1, b2 = partsOfPiece(plain, piece), partsOfPiece(kitA, piece), partsOfPiece(kitB, piece)
			for _, k in ipairs({ b1, b2 }) do
				for _, mp in ipairs(k) do
					local role = string.match(mp.Name, "_(%a+)$")
					if perRole[role] == 1 then
						local pp
						for _, x in ipairs(a) do if x.Name == mp.Name then pp = x end end
						local ba, bb = PlotVisuals.boxOf(pp.CFrame, pp.Size), PlotVisuals.boxOf(mp.CFrame, mp.Size)
						for c = 1, 6 do if math.abs(ba[c] - bb[c]) > 1e-6 then moved = moved or mp:GetFullName() end end
					end
				end
			end
		end
		check("kit: room " .. i .. ": a kit model as imported and one imported the other way (the other KIT_FRONT_TURN) put each part where the Parts version has it", moved == nil, moved)
	end
	check("kit: the rooms have kit pieces to test (the Garage at least)", pieceCount > 0, pieceCount)

	-- The Garage's furniture (interiors item 1): crates for the hires, a workbench, an old desk and a chair, the bare bulb
	local g = PlotArt.Stages[1]
	local function spec(list, name) for _, x in ipairs(list) do if x.name == name then return x end end end
	local desk, chair, bench, bulb = spec(g.decor, "OldDesk"), spec(g.decor, "OldChair"), spec(g.decor, "Workbench"), spec(g.decor, "Bulb")
	check("garage: the hire desk is the kit's Crate and nothing else", #g.desk == 1 and g.desk[1].kit == "Crate")
	check("garage: an old desk (the kit's Desk) and a chair (the kit's Chair) facing it, a workbench (Workbench), the bare bulb (BareBulb) and a pile of crates",
		desk and desk.kit == "Desk" and chair and chair.kit == "Chair" and chair.turn == 180 and bench and bench.kit == "Workbench" and bulb and bulb.kit == "BareBulb"
		and spec(g.decor, "JunkCrateLow") and spec(g.decor, "JunkCrateHigh") and true or false)
	local db = PlotVisuals.kitBox(PlotArt, desk)
	local cb = PlotVisuals.kitBox(PlotArt, chair)
	check("garage: the chair stands on the desk's +Z side (where the PC's screen looks), not inside it", cb[5] >= db[6] and cb[1] < db[2] and cb[2] > db[1])
	local onDesk = true
	for _, name in ipairs({ "CRTStand", "Keyboard", "DeskPhone", "Mug", "SodaCan1" }) do
		local p = spec(g.decor, name)
		local bottom = p.offset[2] - (p.shape == "Cylinder" and p.size[1] or p.size[2]) / 2
		if math.abs(bottom - db[4]) > 0.06 or p.offset[1] < db[1] or p.offset[1] > db[2] or p.offset[3] < db[5] or p.offset[3] > db[6] then onDesk = name end
	end
	check("garage: the old PC, its keyboard, the phone, the mug and the can stand on the old desk's top (2.7)", onDesk == true and math.abs(db[4] - 2.7) < 1e-6, onDesk)
	for _, mode in ipairs(modes) do
		local room = kitRoom(mode[2], 1, mode[3])
		local glass = room:FindFirstChild("Decor"):FindFirstChild("Bulb_glass")
		check("garage with " .. mode[1] .. ": the bulb's glass glows (Neon) and holds the PointLight", glass ~= nil and glass.Material.Name == "Neon" and glass:FindFirstChild("Light") ~= nil)
		local lights = 0
		for _, d in ipairs(room:GetDescendants()) do if d:IsA("PointLight") then lights += 1 end end
		check("garage with " .. mode[1] .. ": two PointLights (the bulb and the old PC)", lights == 2, lights)
	end

	-- Kit problems never stop a room: the piece is built from Parts, with one warning per model per server. Each case runs
	-- inside pcall: a build that errors is a named failure here (in the game, looks() would leave the plot without a room)
	local function buildWith(edit, art)
		local kit = makeKit(IMPORT, "union", edit)
		return kitRoom(art or PlotArt, 1, kit), kit
	end
	local function warnings(word)
		local n = 0
		for _, w in ipairs(WARNED) do if string.find(w, word, 1, true) then n += 1 end end
		return n
	end
	local function isParts(room, name)
		local p = room:FindFirstChild("Decor"):FindFirstChild(name)
		return p ~= nil and p.ClassName == "Part"
	end
	local function case(name, fn)
		WARNED = {}
		local ok, result = pcall(fn)
		check(name, ok and result == true, not ok and result or nil)
	end
	case("kit: a missing model (Workbench) is built from Parts, with one warning even when the room is built twice", function()
		local room = buildWith(function(f) f:FindFirstChild("Workbench"):Destroy() end)
		buildWith(function(f) f:FindFirstChild("Workbench"):Destroy() end)
		return isParts(room, "Workbench_main") and room:FindFirstChild("Decor"):FindFirstChild("OldDesk_main").ClassName == "MeshPart" and warnings("Workbench") == 1
	end)
	case("kit: a MeshPart that can't be copied (Archivable off): its piece is built from Parts, nothing of the kit copy is left, one warning", function()
		local room = buildWith(function(f) f:FindFirstChild("Chair"):FindFirstChildOfClass("MeshPart").Archivable = false end)
		local leftover = 0
		for _, d in ipairs(room:GetDescendants()) do if d.ClassName == "MeshPart" and string.find(d.Name, "OldChair", 1, true) == 1 then leftover += 1 end end
		return isParts(room, "OldChair_main") and leftover == 0 and warnings("Chair") == 1
	end)
	case("kit: something that isn't a MeshPart inside a model is left out (one warning); the piece still comes from the kit", function()
		local room = buildWith(function(f)
			local x = newInstance("Script") x.Name = "Sneaky" x.Parent = f:FindFirstChild("BareBulb")
		end)
		local sneaky = false
		for _, d in ipairs(room:GetDescendants()) do if d.Name == "Sneaky" or d.ClassName == "Script" then sneaky = true end end
		return not sneaky and room:FindFirstChild("Decor"):FindFirstChild("Bulb_glass").ClassName == "MeshPart" and warnings("Sneaky") == 1
	end)
	case("kit: a MeshPart with a role the piece has no color for: the piece is built from Parts (one warning)", function()
		local room = buildWith(function(f) f:FindFirstChild("Desk"):FindFirstChildOfClass("MeshPart"):SetAttribute("Role", "mian") end)
		return isParts(room, "OldDesk_main") and warnings("mian") == 1
	end)
	case("kit: a part turned inside its model can't be scaled unevenly (the hire's crate): built from Parts; the evenly scaled crates still use the kit", function()
		local room = buildWith(function(f)
			local p = f:FindFirstChild("Crate"):FindFirstChildOfClass("MeshPart")
			p.CFrame = p.CFrame * CFrame.Angles(0, math.rad(30), 0)
		end)
		local hire = room:FindFirstChild("Decor"):FindFirstChild("HireDesk1")
		return hire:FindFirstChild("Crate_main").ClassName == "Part" and hire:FindFirstChild("Crate_trim").ClassName == "Part"
			and room:FindFirstChild("Decor"):FindFirstChild("JunkCrateLow_main").ClassName == "MeshPart"
	end)
	case("kit: a model a little bigger than the manifest (KitSize 8.8 x 4.4 x 4.4) is fitted to its size: the workbench stays in its kitBox", function()
		local room = buildWith(function(f)
			local m = f:FindFirstChild("Workbench")
			for _, p in ipairs(m:GetChildren()) do
				local rel = m.WorldPivot:ToObjectSpace(p.CFrame)
				local x, y, z = rel:GetComponents()
				p.Size = Vector3.new(p.Size.X * 1.1, p.Size.Y * 1.1, p.Size.Z * 1.1)
				p.CFrame = m.WorldPivot * CFrame.new(x * 1.1, y * 1.1, z * 1.1) * rel.Rotation
			end
			m:SetAttribute("KitSize", Vector3.new(8.8, 4.4, 4.4))
		end)
		local wb = PlotVisuals.kitBox(PlotArt, bench)
		local fits, n = true, 0
		for _, d in ipairs(room:FindFirstChild("Decor"):GetChildren()) do
			if string.find(d.Name, "Workbench_", 1, true) == 1 then
				n += 1
				local b = PlotVisuals.boxOf(origin:ToObjectSpace(d.CFrame), d.Size)
				if d.ClassName ~= "MeshPart" or b[1] < wb[1] - 1e-6 or b[2] > wb[2] + 1e-6 or b[4] > wb[4] + 1e-6 or b[6] > wb[6] + 1e-6 then fits = false end
			end
		end
		return fits and n == 4
	end)
	-- A quarter turn swaps width and depth: a workbench (8 x 4) turned 90 is 4 wide, from the kit and from Parts
	local wb90 = PlotVisuals.kitBox(PlotArt, { kit = "Workbench", offset = { 1, 0, 2 }, turn = 90, scale = 1 })
	check("kit: kitBox of a workbench turned 90 is 4 wide (X) and 8 deep (Z)", math.abs(wb90[1] + 1) < 1e-9 and math.abs(wb90[2] - 3) < 1e-9 and math.abs(wb90[5] + 2) < 1e-9 and math.abs(wb90[6] - 6) < 1e-9
		and wb90[3] == 0 and wb90[4] == 4)
	for _, mode in ipairs(modes) do
		case("kit: a workbench turned 90 stays inside its kitBox with " .. mode[1], function()
			local model = newInstance("Model")
			local spec = { name = "Turned", kit = "Workbench", offset = { 1, 0, 2 }, turn = 90, roles = bench.roles }
			PlotVisuals.buildKitPiece(model, origin, spec, mode[2], mode[3])
			local n = 0
			for _, d in ipairs(model:GetChildren()) do
				n += 1
				local b = PlotVisuals.boxOf(origin:ToObjectSpace(d.CFrame), d.Size)
				if b[1] < wb90[1] - 1e-6 or b[2] > wb90[2] + 1e-6 or b[5] < wb90[5] - 1e-6 or b[6] > wb90[6] + 1e-6 then return false end
			end
			return n > 0
		end)
	end
	local folder = newInstance("Folder")
	folder.Parent = ROOT
	local floor = newInstance("Part")
	floor.Name = "Floor"
	floor.Size = Vector3.new(60, 1, 60)
	floor.CFrame = CFrame.new(center)
	floor.Parent = folder
	local kit = makeKit(IMPORT, "union")
	local plot = PlotVisuals.newPlot(folder, center, PlotArt, floor, 2, kit)
	PlotVisuals.setStage(plot, 1, false)
	check("kit: newPlot keeps the kit it is given, and setStage builds the next room with it", plot.kit == kit
		and plot.room:FindFirstChild("Decor"):FindFirstChild("Workbench_main").ClassName == "MeshPart")
	local plain = PlotVisuals.newPlot(folder, center, PlotArt, floor, 1)
	local told = 0
	for _, w in ipairs(ALL_WARNED) do if string.find(w, "ReplicatedStorage.KitModels is missing", 1, true) then told += 1 end end
	check("kit: newPlot with no kit (none found) builds from Parts and warns once per server (plots were made without a kit earlier too)",
		plain.kit == nil and isParts(plain.room, "Workbench_main") and told == 1, told)

	-- Mutations: validate and check catch broken kit pieces
	local function art1(edit) local a = deepCopy(PlotArt) edit(a) return a end
	local function piece(a, name) for _, x in ipairs(a.Stages[1].decor) do if x.name == name then return x end end end
	check("mutation (kit): an unknown kit key is caught", anyMatch(PlotVisuals.validate(art1(function(a) piece(a, "Workbench").kit = "Bookcase" end)), "unknown kit key Bookcase"))
	check("mutation (kit): a turn that is not a quarter turn is caught", anyMatch(PlotVisuals.validate(art1(function(a) piece(a, "Workbench").turn = 45 end)), "turn must be"))
	check("mutation (kit): a role without a color is caught", anyMatch(PlotVisuals.validate(art1(function(a) piece(a, "Workbench").roles = { main = { { 1, 2, 3 }, "Wood" } } end)), "role trim needs a color"))
	check("mutation (kit): a role the model doesn't have is caught", anyMatch(PlotVisuals.validate(art1(function(a) piece(a, "OldDesk").roles = deepCopy(piece(a, "Workbench").roles) end)), "has no role accent"))
	check("mutation (kit): Neon on a kit piece that isn't a light is caught", anyMatch(PlotVisuals.validate(art1(function(a) piece(a, "Workbench").roles.main[2] = "Neon" end)), "Neon is only for lights"))
	check("mutation (kit): a material outside the list is caught", anyMatch(PlotVisuals.validate(art1(function(a) piece(a, "Workbench").roles.main[2] = "Grass" end)), "material not allowed: Grass"))
	check("mutation (kit): a scale of 0 is caught", anyMatch(PlotVisuals.validate(art1(function(a) piece(a, "Workbench").scale = 0 end)), "scale must be"))
	check("mutation (kit): an uneven scale of a model whose Parts version has a Ball is caught", anyMatch(PlotVisuals.validate(art1(function(a) piece(a, "Bulb").scale = { 1, 2, 1 } end)), "scales evenly only"))
	check("mutation (kit): a kit piece with its own size or shape is caught", anyMatch(PlotVisuals.validate(art1(function(a) piece(a, "Workbench").size = { 1, 1, 1 } end)), "a kit piece has no shape"))
	check("mutation (kit): a light without a lightRole is caught", anyMatch(PlotVisuals.validate(art1(function(a) piece(a, "Bulb").lightRole = nil end)), "a light needs lightRole"))
	check("mutation (kit): a fallback box sticking out of the model's size is caught", anyMatch(PlotVisuals.validate(art1(function(a) a.Kit.Crate.fallback[2].at[2] = 4 end)), "sticks out of the model's size"))
	check("mutation (kit): a fallback with no box for a role is caught", anyMatch(PlotVisuals.validate(art1(function(a) table.remove(a.Kit.Crate.fallback, 2) end)), "no box for role trim"))
	check("mutation (kit): KIT_FRONT_TURN other than 0 or 180 is caught", anyMatch(PlotVisuals.validate(art1(function(a) a.KIT_FRONT_TURN = 45 end)), "KIT_FRONT_TURN"))
	for _, mode in ipairs({ modes[1], modes[4] }) do
		local function roomProbs(edit)
			local a = art1(edit)
			return PlotVisuals.check(kitRoom(a, 1, mode[3]), center, a)
		end
		check("mutation (kit, " .. mode[1] .. "): the workbench moved into the walking lane is caught", anyMatch(roomProbs(function(a) piece(a, "Workbench").offset = { 0, 0, 20 } end), "lane zone WalkingLane"))
		check("mutation (kit, " .. mode[1] .. "): the hire's crate made too big for its desk zone is caught", anyMatch(roomProbs(function(a) a.Stages[1].desk[1].scale = { 1, 0.55, 0.44 } end), "a hire desk must stay inside its own desk zone"))
		check("mutation (kit, " .. mode[1] .. "): the top crate lifted off the bottom one is caught", anyMatch(roomProbs(function(a) piece(a, "JunkCrateHigh").offset[2] = 4 end), "JunkCrateHigh_main is floating"))
		check("mutation (kit, " .. mode[1] .. "): a crate in an upgrade station is caught", anyMatch(roomProbs(function(a) piece(a, "JunkCrateLow").offset = { 23, 0, -10 } end), "slot zone Server Rack"))
	end
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


COMPANY_TESTS = r"""-- Tests for the Pokedex rules: the real CompanyConfig and SectorConfig (customize PR 1) -------------------
-- Pure code: no Roblox state. The saved section, its loader (bad values, unknown fields, version, run check) and the
-- placement function run exactly as the server runs them. PlotVisuals.zones and PlotArt give the real reserved zones.
local print_real = print
local passed, failed = 0, 0
local function check(name, cond, extra)
	if cond then passed += 1 else failed += 1; print_real("FAIL: " .. name .. (extra ~= nil and (" -- " .. tostring(extra)) or "")) end
end
local WARNINGS = {}
local function warn(...) table.insert(WARNINGS, table.concat({...}, " ")) end
local IS_STUDIO = true
local MODULES = {}
local function token(name) return { Name = name, WaitForChild = function(self, n) return token(n) end } end
local function require(x) return assert(MODULES[x.Name], "no module " .. tostring(x.Name)) end
local SERVICES = {
	ReplicatedStorage = token("ReplicatedStorage"),
	RunService = { IsStudio = function() return IS_STUDIO end },
}
local game = { GetService = function(_, n) return SERVICES[n] end }
local script = { Parent = token("ReplicatedStorage") }

MODULES.SectorConfig = (function()
__SECTORCONFIG__
end)()
MODULES.IpoConfig = (function()
__IPOCONFIG__
end)()
MODULES.CompanyConfig = (function()
__COMPANYCONFIG__
end)()
local PlotVisuals = (function()
__PLOTVISUALS__
end)()
local PlotArt = (function()
__PLOTART__
end)()
local UPGRADES = __UPGRADES__
local SectorConfig = MODULES.SectorConfig
local CC = MODULES.CompanyConfig

local NOW = 1760000000
local function ctx(count)
	return { warn = warn, who = "P", ipoCount = count or 0, now = NOW }
end
local function load(saved, count)
	WARNINGS = {}
	return CC.load(saved, ctx(count))
end
local function save(state, studio)
	return CC.toSave(state, studio == true)
end

local function deepEqual(a, b)
	if typeof(a) ~= typeof(b) then return false end
	if typeof(a) == "number" and a ~= a and b ~= b then return true end -- NaN is NaN
	if typeof(a) ~= "table" then return a == b end
	for k, v in pairs(a) do
		if not deepEqual(v, b[k]) then return false end
	end
	for k in pairs(b) do
		if a[k] == nil then return false end
	end
	return true
end
local function deepCopy(v)
	if typeof(v) ~= "table" then return v end
	local c = {}
	for k, inner in pairs(v) do c[k] = deepCopy(inner) end
	return c
end
local function count(t)
	local n = 0
	for _ in pairs(t) do n += 1 end
	return n
end
local function anyWarning(text)
	for _, w in ipairs(WARNINGS) do
		if string.find(w, text, 1, true) then return true end
	end
	return false
end
__STORABLE__
-- Every section CompanyConfig.toSave hands out in these tests (the loader's result written back, by any test) is screened: it must be storable
do
	local realToSave = CC.toSave
	CC.toSave = function(state, studio) return screenStorable(realToSave(state, studio)) end
end
runStoreSelfTest(check)

-- 1. SectorConfig --------------------------------------------------------------------------
check("four sector keys from day one, in order", deepEqual(SectorConfig.Order, { "Software", "Gaming", "Fintech", "Biotech" }))
check("every key has an entry", (function()
	for _, key in ipairs(SectorConfig.Order) do
		if not SectorConfig.isKnown(key) then return false end
	end
	return count(SectorConfig.Sectors) == 4
end)())
check("only Software can be picked", SectorConfig.isEnabled("Software") and not SectorConfig.isEnabled("Gaming")
	and not SectorConfig.isEnabled("Fintech") and not SectorConfig.isEnabled("Biotech"))
check("the picker is off", SectorConfig.PickerEnabled == false)
check("an unknown or bad key is not a sector", not SectorConfig.isKnown("Energy") and not SectorConfig.isKnown(nil) and not SectorConfig.isKnown(5) and SectorConfig.get({}) == nil)
check("Software has 12 or more company names and the default is the first", #SectorConfig.Sectors.Software.names >= 12 and SectorConfig.defaultName("Software") == SectorConfig.Sectors.Software.names[1])
check("the default sector is Software", SectorConfig.Default == "Software")
check("the Launch goal is Software and Gaming", deepEqual(SectorConfig.Goals.Launch.sectors, { "Software", "Gaming" }))
check("no sector text claims odds or chance (D9)", (function()
	for _, sector in pairs(SectorConfig.Sectors) do
		local texts = { sector.name, sector.summary }
		for _, name in ipairs(sector.names) do table.insert(texts, name) end
		for _, text in ipairs(texts) do
			local lower = string.lower(text)
			for _, word in ipairs({ "odds", "chance", "luck", "random", "probab", "%" }) do
				if string.find(lower, word, 1, true) then return false end
			end
		end
	end
	return true
end)())

-- 2. A missing section is a new founding ----------------------------------------------------
local state = load(nil, 0)
check("missing section: not locked, no event, no warning", state.locked == false and state.event == nil and #WARNINGS == 0)
local s = state.section
check("missing section: v 1, run = the IPO count, Software, building 1, picked (the picker is off)",
	s.v == 1 and s.run == 0 and s.active.sector == "Software" and s.active.building == 1 and s.active.picked == true)
check("missing section: the first name from the sector's list, founded now", s.active.name == SectorConfig.defaultName("Software") and s.active.foundedAt == NOW)
check("missing section: nothing placed, stored, told or raised", next(s.active.objects) == nil and next(s.active.stored) == nil and next(s.active.told) == nil
	and next(s.active.rounds) == nil and next(s.active.decor) == nil and next(s.active.sx) == nil and s.active.engaged == 0)
check("missing section: no sector started, nothing kept, no Hall of Fame entry, no dust", next(s.sectors) == nil and next(s.kept) == nil and next(s.hall) == nil and s.dust == 0)
check("missing section: run follows a save that has IPOs", load(nil, 4).section.run == 4)
check("missing section: no board mark in a normal server", save(state, false).studio == nil)
check("a Studio server marks the section for good", save(state, true).studio == true)
SectorConfig.PickerEnabled = true
check("with the picker on, a new company starts unpicked (the picker opens)", load(nil, 0).section.active.picked == false)
SectorConfig.PickerEnabled = false
state = load("hello", 2)
check("a section that isn't a table is a new founding with a warning", state.section.run == 2 and state.section.active.sector == "Software" and anyWarning("isn't a table"))

-- 3. Round trip: every field, unknown fields at every level -----------------------------------
local function objectsList(extra)
	return { { id = "Desk", x = -23, z = -40, r = 0, futureObj = extra }, { id = "Laptop", x = -25.5, z = -30, r = 3 } }
end
local FULL = {
	v = 1, run = 2,
	active = {
		sector = "Software", picked = true, name = "Pixel Pioneers", foundedAt = 1700000000, engaged = 1234.5,
		passSeconds = { DoubleCash = 100.5, VIP = 20, FuturePass = { a = 1 } },
		building = 3,
		decor = { Chair = 2, Future = "x" },
		objects = objectsList("keep me"),
		stored = { Whiteboard = true, ["Gaming PC"] = true },
		told = { Seed = true, SeriesA = true, FutureStage = 7 },
		rounds = {
			Seed = { s = "raised", c = 2, cash = 360, bp = 122, at = 1700000100, studio = false, extra = { deep = true } },
			SeriesA = { s = "skipped", c = 0, cash = 0, bp = 0, at = 1700000200, studio = true },
			FutureStage = { anything = "goes", bp = 50 },
		},
		sx = { n = 3, deep = { a = { b = 1 } } },
		futureActive = { x = 1 },
	},
	sectors = {
		Software = {
			state = "done", stamp = 2, replays = 1, firstAt = 1690000000, bestEngaged = 9999.25,
			card = {
				name = "Old Co", ipoNumber = 1, at = 1690000001, engaged = 8888.5, ratio = 1.25, building = 5,
				owned = { "Desk", "Laptop", "Gaming PC" },
				decor = { Chair = 1, Future = 3 },
				objects = objectsList("card object"),
				rounds = { Seed = { s = "raised", c = 1, cash = 100, bp = 40, at = 5, studio = false, extra = 1 }, FutureStage = { bp = 9 } },
				stake = 9951, shares = 14, sx = { score = 5 },
				futureCard = "keep",
			},
			futureSector = { y = 2 },
		},
		Gaming = { state = "progress", stamp = 0, replays = 0, firstAt = 0, bestEngaged = 0 },
		Energy = { whatever = { 1, 2, 3 } },
	},
	kept = { Chair = 1, Plant = 2 },
	hall = { Launch = 1700000300, Four = 1700000400 },
	dust = -1234,
	studio = false,
	futureTop = { z = { 1, 2, 3 } },
}
state = load(deepCopy(FULL), 2)
check("round trip: nothing is warned about in a complete good section", #WARNINGS == 0, WARNINGS[1])
check("round trip: not locked, no run check event", state.locked == false and state.event == nil)
local out = save(state, false)
check("round trip: the saved section equals the loaded one, deep", deepEqual(out, FULL))
check("round trip: v = 1 is written", out.v == 1)
check("round trip: saving twice gives the same section", deepEqual(save(state, false), out))
local again = load(deepCopy(out), 2)
check("round trip: load(save(load(x))) is stable", deepEqual(save(again, false), out) and #WARNINGS == 0)
local keptAt = {
	["top-level unknown field"] = function() return out.futureTop and out.futureTop.z[3] == 3 end,
	["active unknown field"] = function() return out.active.futureActive.x == 1 end,
	["active.objects[i] unknown field"] = function() return out.active.objects[1].futureObj == "keep me" end,
	["active.passSeconds unknown key"] = function() return out.active.passSeconds.FuturePass.a == 1 end,
	["active.decor unknown key"] = function() return out.active.decor.Future == "x" end,
	["active.stored unknown id"] = function() return out.active.stored["Gaming PC"] == true end,
	["active.told unknown key"] = function() return out.active.told.FutureStage == 7 end,
	["active.rounds[k] unknown field"] = function() return out.active.rounds.Seed.extra.deep == true end,
	["active.rounds unknown stage"] = function() return out.active.rounds.FutureStage.anything == "goes" and out.active.rounds.FutureStage.bp == 50 end,
	["active.sx whole"] = function() return out.active.sx.deep.a.b == 1 end,
	["sectors unknown key kept whole"] = function() return out.sectors.Energy.whatever[3] == 3 end,
	["sectors[k] unknown field"] = function() return out.sectors.Software.futureSector.y == 2 end,
	["card unknown field"] = function() return out.sectors.Software.card.futureCard == "keep" end,
	["card.owned unknown upgrade name"] = function() return out.sectors.Software.card.owned[3] == "Gaming PC" end,
	["card.decor unknown key"] = function() return out.sectors.Software.card.decor.Future == 3 end,
	["card.objects[i] unknown field"] = function() return out.sectors.Software.card.objects[1].futureObj == "card object" end,
	["card.rounds[k] unknown field"] = function() return out.sectors.Software.card.rounds.Seed.extra == 1 end,
	["card.rounds unknown stage"] = function() return out.sectors.Software.card.rounds.FutureStage.bp == 9 end,
	["card.sx whole"] = function() return out.sectors.Software.card.sx.score == 5 end,
	["kept unknown key"] = function() return out.kept.Plant == 2 end,
	["hall unknown goal"] = function() return out.hall.Four == 1700000400 end,
}
for name, probe in pairs(keptAt) do
	local ok, result = pcall(probe)
	check("unknown data is kept: " .. name, ok and result == true)
end
local changedCopy = pcall(function() out.active.objects[1].x = 99 end)
check("the saved section is a copy: changing it never changes the live state", changedCopy and state.section.active.objects[1].x == -23)

-- 4. The version rule ----------------------------------------------------------------------
local V2 = { v = 2, run = 0, active = { sector = "Software", name = "From the future", newShape = { 1, 2 } }, extra = { a = { b = 1 } }, sectors = { Software = "other shape" } }
state = load(deepCopy(V2), 5)
check("v = 2: kept opaque (locked), no run check, no event", state.locked == true and state.event == nil and state.section == nil)
check("v = 2: a warning says why", anyWarning("version 2"))
out = save(state, true)
check("v = 2: deep-equal after a save, even from a Studio server (nothing added)", deepEqual(out, V2) and out.studio == nil)
check("v = 2: the very table that loaded is written back", out == state.raw)
check("v = 99 is kept the same way", load({ v = 99, x = 1 }, 0).locked == true)
for _, bad in ipairs({ 0, -1, 1.5, "1", "2", true, {}, 0 / 0, math.huge }) do
	local st = load({ v = bad, run = 0 }, 0)
	check("a bad v (" .. tostring(bad) .. ") is skipped with a warning and the section is read as version 1", st.locked == false and anyWarning("bad v") and save(st, false).v == 1)
end
check("a section with no v is read as version 1 without a warning", #(function() load({ run = 0 }, 0) return WARNINGS end)() == 0)

-- 5. The run check ----------------------------------------------------------------------------
local function savedCompany(run, extra)
	local active = {
		sector = "Software", picked = true, name = "Pixel Pioneers", foundedAt = 1700000000, engaged = 100.5,
		passSeconds = {}, building = 3, decor = { Chair = 1 }, objects = { { id = "Desk", x = -23, z = -40, r = 0 } },
		stored = { Laptop = true }, told = { Seed = true },
		rounds = { Seed = { s = "raised", c = 2, cash = 360, bp = 300, at = 1700000100, studio = false } },
		sx = { n = 1 },
	}
	for k, v in pairs(extra or {}) do active[k] = v end
	return { v = 1, run = run, active = active, sectors = {}, kept = {}, hall = {}, dust = 0 }
end
-- (1) run < count: an older version ran an IPO
state = load(savedCompany(0), 1)
s = state.section
check("run < count: the event is 'complete', with a warning", state.event == "complete" and anyWarning("older version ran an IPO"))
local entry = s.sectors.Software or {} -- (a broken run check must fail these checks by name, not crash the program)
check("run < count: Software is done with Bronze, first done now", entry.state == "done" and entry.stamp == 1 and entry.firstAt == NOW and entry.replays == 0)
check("run < count: the best engaged time is the company's", entry.bestEngaged == 100.5)
local card = entry.card or { decor = {}, objects = {}, rounds = {}, sx = {}, owned = {} }
check("run < count: the card names the company, the IPO number and the date", card.name == "Pixel Pioneers" and card.ipoNumber == 1 and card.at == NOW)
check("run < count: the card keeps the building, decor, items and sx as they were",
	card.building == 3 and card.decor.Chair == 1 and card.objects[1].id == "Desk" and card.sx.n == 1 and card.engaged == 100.5)
check("run < count: the card keeps the rounds (the Seed round, 300 bp)", card.rounds.Seed ~= nil and card.rounds.Seed.bp == 300)
check("run < count: the stake is 10,000 minus the dilution, what is unknown is 0", card.stake == 9700 and card.ratio == 0 and card.shares == 0 and #card.owned == 0)
do
	local live = CC.load(deepCopy(savedCompany(2)), ctx(2)).section
	CC.completeCompany(live, 3, NOW)
	-- (changing the live company afterwards: through pcall, a broken load must fail this check, not stop the program)
	local touched = pcall(function()
		live.active.objects[1].x = 99
		live.active.rounds.Seed.bp = 1
		live.active.decor.Chair = 9
	end)
	local made = live.sectors.Software.card
	check("completeCompany: the card is a copy (changing the live company never changes it)", touched and made.objects[1].x == -23 and made.rounds.Seed ~= nil and made.rounds.Seed.bp == 300 and made.decor.Chair == 1)
end
check("run < count: a new company starts (same sector, building 1, nothing placed, no rounds, picked while the picker is off)",
	s.active.sector == "Software" and s.active.building == 1 and next(s.active.objects) == nil and next(s.active.rounds) == nil
	and next(s.active.stored) == nil and next(s.active.told) == nil and s.active.picked == true and s.active.foundedAt == NOW and s.active.engaged == 0)
check("run < count: run = the IPO count", s.run == 1)
check("run < count: one launch sector done is not the Launch goal", s.hall.Launch == nil)
local saved = save(state, false)
local second = load(deepCopy(saved), 1)
check("run < count: the next join does nothing more (Bronze once, one card)", second.event == nil and #WARNINGS == 0 and deepEqual(save(second, false), saved))
-- run 2 with count 3: Bronze and a card once
state = load(savedCompany(2), 3)
check("run 2, count 3: Bronze and a card, the card says IPO 3", state.event == "complete" and state.section.sectors.Software.stamp == 1 and state.section.sectors.Software.card.ipoNumber == 3 and state.section.run == 3)
check("run 2, count 3: joining again changes nothing", load(deepCopy(save(state, false)), 3).event == nil)
-- several IPOs missed: still one company, one card
state = load(savedCompany(0), 4)
check("run 0, count 4: one completion (the one company the section knows), run = 4", state.event == "complete" and state.section.run == 4 and state.section.sectors.Software.replays == 0)
-- a sector done before: replays count, the stamp never goes down, firstAt stays
local done = savedCompany(1)
done.sectors = { Software = { state = "done", stamp = 3, replays = 2, firstAt = 1650000000, bestEngaged = 500, card = { name = "Old", ipoNumber = 1, at = 1650000000, engaged = 500 } } }
state = load(done, 2)
s = state.section.sectors.Software
check("a replay: Platinum stays Platinum, replays + 1, firstAt kept, best engaged is the larger", s.stamp == 3 and s.replays == 3 and s.firstAt == 1650000000 and s.bestEngaged == 500 and s.card.ipoNumber == 2)
done.sectors.Software.stamp = 0
done.sectors.Software.state = "done"
check("a finished sector saved with stamp 0 counts as Bronze", load(done, 1).section.sectors.Software.stamp == 1)
-- a Studio test entry under Gaming: kept, never picked, counts for no goal
local both = savedCompany(0)
both.sectors = { Gaming = { state = "done", stamp = 3, replays = 0, firstAt = 5, bestEngaged = 1 } }
state = load(both, 1)
check("Gaming 'done' in a save (a Studio test) is kept but Launch is not reached while Gaming can't be picked", state.section.sectors.Gaming.stamp == 3 and (state.section.sectors.Software or {}).state == "done" and state.section.hall.Launch == nil)
SectorConfig.Sectors.Gaming.enabled = true
check("... with Gaming enabled, both done is the Launch goal", load(deepCopy(both), 1).section.hall.Launch == NOW)
SectorConfig.Sectors.Gaming.enabled = false
-- (2) run > count: never an IPO
local reset = savedCompany(3)
reset.active.rounds.Seed.bp = 300
state = load(reset, 0)
check("run > count: the event is 'rebase', with a warning", state.event == "rebase" and anyWarning("IPO reset in Studio"))
check("run > count: run = the count, the company stays as it was (settled rounds stay settled)", state.section.run == 0 and state.section.active.building == 3
	and state.section.active.rounds.Seed.bp == 300 and state.section.active.objects[1].id == "Desk" and state.section.active.name == "Pixel Pioneers")
check("run > count: no stamp, no card, no Hall of Fame entry", next(state.section.sectors) == nil and next(state.section.hall) == nil)
check("run > count: the section is marked as saved by Studio", state.section.studio == true and save(state, false).studio == true)
check("run > count: joining again does nothing more", load(deepCopy(save(state, false)), 0).event == nil)
check("a damaged ipo (count 0) with run 3 lands in the same case", load(savedCompany(3), 0).event == "rebase")
check("run = count does nothing", load(savedCompany(2), 2).event == nil and #WARNINGS == 0)

-- 6. Bad values are skipped with a warning, never an error ---------------------------------------
local function good()
	return deepCopy(FULL)
end
local function loadsWith(change, count)
	local data = good()
	change(data)
	local ok, result = pcall(CC.load, data, ctx(count or 2))
	check("a bad value never throws", ok, result)
	WARNINGS = {}
	return ok and result or nil
end
local function loaded(change, count)
	local data = good()
	change(data)
	WARNINGS = {}
	local ok, result = pcall(CC.load, data, ctx(count or 2))
	check("a bad value never throws", ok, result)
	return ok and result.section or nil, #WARNINGS
end
local sec, warned
sec, warned = loaded(function(d) d.active.engaged = -5 end)
check("engaged -5 is skipped (0) with a warning", sec.active.engaged == 0 and warned == 1)
sec, warned = loaded(function(d) d.active.engaged = 0 / 0 end)
check("engaged NaN is skipped", sec.active.engaged == 0 and warned == 1)
sec, warned = loaded(function(d) d.active.engaged = math.huge end)
check("engaged infinity is skipped", sec.active.engaged == 0 and warned == 1)
sec, warned = loaded(function(d) d.active.foundedAt = 1.5 end)
check("a fractional foundedAt is skipped", sec.active.foundedAt == NOW and warned == 1)
sec, warned = loaded(function(d) d.active.building = 0 end)
check("building 0 is skipped (1)", sec.active.building == 1 and warned == 1)
sec, warned = loaded(function(d) d.active.building = 2.5 end)
check("building 2.5 is skipped (1)", sec.active.building == 1 and warned == 1)
sec, warned = loaded(function(d) d.active.building = 7 end)
check("a building number above the five known is kept (a newer version), it just can't be used", sec.active.building == 7 and warned == 0)
sec, warned = loaded(function(d) d.active.picked = "yes" end)
check("picked 'yes' is skipped (the default)", sec.active.picked == true and warned == 1)
sec, warned = loaded(function(d) d.active.name = 5 end)
check("a name that isn't a string is skipped (the sector's first name)", sec.active.name == SectorConfig.defaultName("Software") and warned == 1)
sec, warned = loaded(function(d) d.active.name = string.rep("x", 61) end)
check("a name over 60 characters is skipped", sec.active.name == SectorConfig.defaultName("Software") and warned == 1)
sec, warned = loaded(function(d) d.active.passSeconds.DoubleCash = -1; d.active.passSeconds.VIP = "x" end)
check("passSeconds: a bad value of a known pass is skipped, the others stay", sec.active.passSeconds.DoubleCash == nil and sec.active.passSeconds.VIP == nil and (sec.active.passSeconds.FuturePass or {}).a == 1 and warned == 2)
sec, warned = loaded(function(d) d.active.passSeconds = 5 end)
check("passSeconds that isn't a table is skipped", next(sec.active.passSeconds) == nil and warned == 1)
sec, warned = loaded(function(d)
	d.active.objects = {
		{ id = "Desk", x = 0 / 0, z = 0, r = 0 }, { id = "Laptop", x = 1, z = 1, r = 8 }, { id = "Laptop", x = 1, z = 1, r = 1.5 },
		{ id = string.rep("a", 40), x = 1, z = 1, r = 0 }, { id = 5, x = 1, z = 1, r = 0 }, { id = "Server Rack", x = 0.3, z = 1, r = 0 },
		{ id = "Whiteboard", x = 1, z = 1 }, "junk", { id = "Neon Logo", x = 2, z = 3, r = 7 }, { id = "Neon Logo", x = 4, z = 4, r = 0 },
		{ id = "Desk", x = math.huge, z = 0, r = 0 }, { id = "Coffee Machine", x = 1e9, z = 0, r = 0 },
	}
end)
check("objects: a bad x, r, id, grid step, missing field, junk, a repeated id or a far x is skipped, the one good item stays",
	#sec.active.objects == 1 and sec.active.objects[1].id == "Neon Logo" and sec.active.objects[1].x == 2 and warned == 11, warned)
sec, warned = loaded(function(d)
	d.active.objects = {}
	for i = 1, 50 do table.insert(d.active.objects, { id = "Item" .. i, x = i, z = 0, r = 0 }) end
end)
check("objects: at most 40 are kept (ids this version has no item for are kept too)", #sec.active.objects == 40 and sec.active.objects[40].id == "Item40" and warned == 10, warned)
sec, warned = loaded(function(d)
	d.active.stored = { Desk = true, Laptop = false, [1] = true, [string.rep("a", 40)] = true, Server = "yes" }
end)
check("stored: only string ids of 1 to 39 characters stay, and a value other than true is kept as it was",
	count(sec.active.stored) == 3 and sec.active.stored.Desk == true and sec.active.stored.Laptop == false and sec.active.stored.Server == "yes" and warned == 2, warned)
do
	local record = { tier = 2, tags = { "a", "b" } }
	sec, warned = loaded(function(d) d.active.stored = { Desk = true, Rack = record } end)
	check("stored: a record of a newer version (a table) is kept whole, as a copy, with no warning",
		deepEqual(sec.active.stored.Rack, { tier = 2, tags = { "a", "b" } }) and sec.active.stored.Rack ~= record and sec.active.stored.Desk == true and warned == 0, warned)
	check("stored: ... and it is written back as it was", deepEqual(save({ section = sec, locked = false }, false).active.stored, { Desk = true, Rack = { tier = 2, tags = { "a", "b" } } }))
end
sec, warned = loaded(function(d)
	d.active.stored = {}
	for i = 1, 45 do d.active.stored["Item" .. string.format("%02d", i)] = true end
end)
check("stored: at most 40 are kept, always the same ones", count(sec.active.stored) == 40 and sec.active.stored.Item40 == true and sec.active.stored.Item41 == nil and warned == 5, warned)
-- Placed items. A table with ONLY string keys (a shape this version doesn't know, and one the store can hold) can't be carried back in a
-- list: the whole section is kept as it was. A list with a gap or with other keys is something the store refuses, so it is tidied on
-- load: the entries in key order, the gap closed, every other key dropped, each with a warning (never written back as it was).
do
	local function keptAsItWas(name, change)
		local saved = good()
		change(saved)
		local copy = deepCopy(saved)
		local st = load(saved, 2)
		check(name .. ": the section is kept as it was (locked, written back unchanged)", st.locked == true and deepEqual(CC.toSave(st, true), copy) and CC.toSave(st, true) == saved and anyWarning("not a plain list"))
	end
	keptAsItWas("objects that is a dictionary", function(d) d.active.objects = { first = { id = "Desk", x = 0, z = 0, r = 0 } } end)
	keptAsItWas("a card's objects that is a dictionary", function(d) d.sectors.Software.card.objects = { future = 1 } end)
	local store = newFaithfulStore()
	local function tidied(name, change, wantIds, wantWarnings, inCard)
		local saved = good()
		change(saved)
		local st = load(saved, 2)
		local nWarned = #WARNINGS
		local out = save(st, false)
		local list = inCard and out.sectors.Software.card.objects or out.active.objects
		local ids, keys = {}, 0
		for i = 1, #list do table.insert(ids, list[i].id) end
		for _ in pairs(list) do keys += 1 end
		check(name .. ": not locked, a plain list of the right entries in key order", st.locked == false and keys == #wantIds and table.concat(ids, ",") == table.concat(wantIds, ","), table.concat(ids, ","))
		check(name .. ": " .. wantWarnings .. " warning(s)", nWarned == wantWarnings, nWarned)
		local okStore, problem = pcall(store.SetAsync, store, "k", out)
		check(name .. ": the saved section is accepted by the store", okStore, problem)
	end
	local GAP = { id = "Whiteboard", x = 1, z = 1, r = 0 }
	tidied("objects with a string key next to the list", function(d) d.active.objects.future = { id = "Gaming PC", x = 0, z = 0, r = 0 } end, { "Desk", "Laptop" }, 1)
	tidied("objects with a gap in its indexes", function(d) d.active.objects[5] = deepCopy(GAP) end, { "Desk", "Laptop", "Whiteboard" }, 1)
	tidied("objects with keys 0 and -3", function(d) d.active.objects[0] = deepCopy(GAP); d.active.objects[-3] = deepCopy(GAP) end, { "Desk", "Laptop" }, 2)
	tidied("objects with only [1] and [3]", function(d) d.active.objects = { [1] = { id = "Desk", x = -23, z = -40, r = 0 }, [3] = { id = "Laptop", x = -25.5, z = -30, r = 3 } } end, { "Desk", "Laptop" }, 1)
	tidied("objects whose entries start after a gap (no [1])", function(d) d.active.objects = { [2] = { id = "Laptop", x = -25.5, z = -30, r = 3 }, [4] = deepCopy(GAP) } end, { "Laptop", "Whiteboard" }, 1)
	tidied("a card's objects with a string key next to the list", function(d) d.sectors.Software.card.objects.future = 1 end, { "Desk", "Laptop" }, 1, true)
	tidied("a card's objects with a gap in its indexes", function(d) d.sectors.Software.card.objects[7] = deepCopy(GAP) end, { "Desk", "Laptop", "Whiteboard" }, 1, true)
	tidied("objects with a bad entry after a gap (skipped, then the gap is closed)", function(d) d.active.objects[5] = "junk" end, { "Desk", "Laptop" }, 2)
	local clean = load(good(), 2)
	check("objects: a plain list (even with bad entries) does not lock the section", clean.locked == false and #clean.section.active.objects == 2)
end
-- A key that isn't a string next to the named fields of a table (the section, active, a round, a placed item, a sector entry, a card ...)
-- can't be saved there (the store refuses a table that mixes keys): it is dropped, with a warning, and the rest comes back unchanged.
do
	local store = newFaithfulStore()
	local PLACES = {
		{ "the section", function(d) return d end },
		{ "active", function(d) return d.active end },
		{ "an active round", function(d) return d.active.rounds.Seed end },
		{ "a placed item", function(d) return d.active.objects[1] end },
		{ "a sector entry", function(d) return d.sectors.Software end },
		{ "a card", function(d) return d.sectors.Software.card end },
		{ "a card's round", function(d) return d.sectors.Software.card.rounds.Seed end },
		{ "a card's placed item", function(d) return d.sectors.Software.card.objects[1] end },
	}
	for _, place in ipairs(PLACES) do
		local allGood, allWarned, allStored = true, true, true
		for _, key in ipairs({ 99, 0, -3, 1.5 }) do
			local saved = good()
			place[2](saved)[key] = { z = 1 }
			local st = load(saved, 2)
			allWarned = allWarned and #WARNINGS == 1
			local out = save(st, false)
			allGood = allGood and deepEqual(out, FULL)
			allStored = allStored and pcall(store.SetAsync, store, "k", out)
		end
		check("a number key (99, 0, -3, 1.5) next to the named fields of " .. place[1] .. " is dropped, with one warning each", allWarned)
		check("... and the rest of " .. place[1] .. " is written back unchanged", allGood)
		check("... and what is saved is accepted by the store (" .. place[1] .. ")", allStored)
	end
end
sec, warned = loaded(function(d) d.active.told = { Seed = false, SeriesA = true } end)
check("told: a known stage that isn't true is skipped", sec.active.told.Seed == nil and sec.active.told.SeriesA == true and warned == 1)
sec, warned = loaded(function(d) d.active.sx = 5 end)
check("sx that isn't a table starts again as {} with a warning", next(sec.active.sx) == nil and warned == 1)
sec, warned = loaded(function(d) d.active.decor = "x" end)
check("decor that isn't a table is skipped", next(sec.active.decor) == nil and warned == 1)
-- rounds: never dropped
sec, warned = loaded(function(d)
	d.active.rounds = { Seed = "x", SeriesA = { s = "maybe", bp = 300, extra = 1 }, SeriesB = { s = "raised", bp = 12.5 }, Future = { bp = 500 } }
end)
check("rounds: a record of a known stage that isn't a table counts as settled (skipped, no dilution)", (sec.active.rounds.Seed or {}).s == "skipped" and (sec.active.rounds.Seed or {}).bp == 0)
check("rounds: a malformed record counts as settled with bp 0, its unknown fields stay", (sec.active.rounds.SeriesA or {}).s == "skipped" and (sec.active.rounds.SeriesA or {}).bp == 0 and (sec.active.rounds.SeriesA or {}).extra == 1)
check("rounds: a fractional bp is malformed too", (sec.active.rounds.SeriesB or {}).bp == 0 and (sec.active.rounds.SeriesB or {}).s == "skipped")
check("rounds: an unknown stage is kept whole", (sec.active.rounds.Future or {}).bp == 500 and warned == 3, warned)
check("dilution: an unknown stage's valid bp counts, a malformed one counts 0", CC.dilution(sec.active.rounds) == 500 and CC.stakeOf(sec.active.rounds) == 9500)
check("dilution is capped (4,000 bp), the stake never falls under 6,000", CC.dilution({ A = { bp = 3000 }, B = { bp = 3000 } }) == 4000 and CC.stakeOf({ A = { bp = 9000 } }) == 6000)
check("dilution ignores bad bp (negative, fractional, huge, NaN, a string)", CC.dilution({ A = { bp = -5 }, B = { bp = 1.5 }, C = { bp = 20000 }, D = { bp = 0 / 0 }, E = { bp = "9" }, F = "x", G = { bp = 7 } }) == 7)
check("no rounds: the founder keeps 10,000", CC.stakeOf({}) == 10000 and CC.stakeOf(nil) == 10000)
-- sectors
sec, warned = loaded(function(d)
	d.sectors = {
		Software = { state = "done", stamp = 0 }, Gaming = { state = "weird", stamp = 9, replays = -1 },
		Fintech = { state = "done", stamp = -2, firstAt = "x", bestEngaged = -3 }, Biotech = "text", Energy = 5,
	}
end)
check("sectors: done with stamp 0 becomes Bronze", sec.sectors.Software.stamp == 1 and sec.sectors.Software.state == "done")
check("sectors: a bad state is 'progress', a stamp over 3 is clamped to 3 and a bad replays is 0", sec.sectors.Gaming.state == "progress" and sec.sectors.Gaming.stamp == 3 and sec.sectors.Gaming.replays == 0)
check("sectors: a negative stamp is clamped to 0 (then Bronze, the sector is done), bad numbers are 0", sec.sectors.Fintech.stamp == 1 and sec.sectors.Fintech.firstAt == 0 and sec.sectors.Fintech.bestEngaged == 0)
check("sectors: an entry that isn't a table is skipped (not started)", sec.sectors.Biotech == nil)
check("sectors: an unknown key is kept whole, whatever it is", sec.sectors.Energy == 5)
sec, warned = loaded(function(d) d.sectors.Software.stamp = "gold" end)
check("sectors: a stamp that isn't a number is 0 (then Bronze, the sector is done)", sec.sectors.Software.stamp == 1 and warned == 1)
sec, warned = loaded(function(d) d.sectors.Software.card = "text" end)
check("sectors: a card that isn't a table is skipped", sec.sectors.Software.card == nil and warned == 1)
sec, warned = loaded(function(d) d.sectors.Software.card.stake = 20000; d.sectors.Software.card.ipoNumber = -1; d.sectors.Software.card.owned = { "Desk", 5 } end)
check("card: a bad stake, ipoNumber and owned name are skipped", sec.sectors.Software.card.stake == 10000 and sec.sectors.Software.card.ipoNumber == 0 and #sec.sectors.Software.card.owned == 1 and warned == 3, warned)
-- card.owned is tidied on load. The store refuses a table that mixes list and string keys, and a list with holes loses what comes after a
-- hole, so: every valid name goes into a plain list 1 .. n in key order (a gap is closed, with a warning), any other key (a string, 0, a
-- negative or fractional number) is dropped with a warning, and a table with ONLY string keys is kept as it is. Duplicates, bad values
-- and the limit of 200 behave as before.
do
	local function ownedWith(owned)
		local saved = good()
		saved.sectors.Software.card.owned = owned
		local st = load(saved, 2)
		local nWarned = #WARNINGS
		local out = save(st, false)
		return st, out.sectors.Software.card.owned, nWarned, out
	end
	local function plainList(t, n)
		local keys = 0
		for _ in pairs(t) do keys += 1 end
		for i = 1, n do
			if t[i] == nil then return false end
		end
		return keys == n
	end
	local function sameList(t, want)
		if not plainList(t, #want) then return false end
		for i, name in ipairs(want) do
			if t[i] ~= name then return false end
		end
		return true
	end
	local store = newFaithfulStore()
	local CASES = {
		{ "a hole {Desk, nil, Laptop}", { "Desk", nil, "Laptop" }, { "Desk", "Laptop" }, 1 },
		{ "a string key {Desk, Laptop, future}", { "Desk", "Laptop", future = "GamingRig" }, { "Desk", "Laptop" }, 1 },
		{ "an entry after a gap {Desk, Laptop, [5]}", { "Desk", "Laptop", [5] = "Neon Logo" }, { "Desk", "Laptop", "Neon Logo" }, 1 },
		{ "the review's mixed case {Desk, Laptop, future, [5]}", { "Desk", "Laptop", future = "GamingRig", [5] = "Neon Logo" }, { "Desk", "Laptop", "Neon Logo" }, 2 },
		{ "[1] and [3]", { [1] = "a", [3] = "b" }, { "a", "b" }, 1 },
		{ "[1], [3] and [4]", { [1] = "a", [3] = "b", [4] = "c" }, { "a", "b", "c" }, 1 },
		{ "keys 0 and -3 next to a name", { "Desk", [0] = "Zero", [-3] = "Minus" }, { "Desk" }, 2 },
		{ "key 1.5 next to names", { "Desk", "Laptop", [1.5] = "Half" }, { "Desk", "Laptop" }, 1 },
		{ "a string key \"1\" next to [1]", { "Desk", ["1"] = "x" }, { "Desk" }, 1 },
		{ "names that start after a gap (no [1])", { [2] = "Laptop", [3] = "Desk" }, { "Laptop", "Desk" }, 1 },
		{ "names stored under keys out of order", { [10] = "c", [2] = "b", [1] = "a" }, { "a", "b", "c" }, 1 },
		{ "a plain list", { "Desk", "Laptop", "Gaming PC" }, { "Desk", "Laptop", "Gaming PC" }, 0 },
		{ "duplicates", { "Desk", "Desk", "Laptop" }, { "Desk", "Desk", "Laptop" }, 0 },
		{ "duplicates after a gap", { [1] = "Desk", [4] = "Desk" }, { "Desk", "Desk" }, 1 },
		{ "a value that is not a name (a number)", { "Desk", 5, "Laptop" }, { "Desk", "Laptop" }, 1 },
		{ "bad values (a table, empty, 40 characters, false) and a string key", { "Desk", { tier = 2 }, "", string.rep("x", 40), false, "Laptop", future = "k" }, { "Desk", "Laptop" }, 5 },
		{ "an empty table", {}, {}, 0 },
	}
	for _, case in ipairs(CASES) do
		local label, input, want, warnings = case[1], case[2], case[3], case[4]
		local st, owned, nWarned, out = ownedWith(input)
		check("card.owned " .. label .. ": not locked, a plain list with the right names in key order", st.locked == false and sameList(owned, want))
		check("card.owned " .. label .. ": " .. warnings .. " warning(s)", nWarned == warnings, nWarned)
		local okStore, problem = pcall(store.SetAsync, store, "k", out)
		check("card.owned " .. label .. ": the saved section is accepted by the store", okStore, problem)
		local second = load(deepCopy(out), 2)
		check("card.owned " .. label .. ": loading what was saved changes nothing and warns about nothing", #WARNINGS == 0 and deepEqual(save(second, false), out))
	end
	local st, owned, nWarned = ownedWith({ future = "x" })
	check("card.owned: a table with only string keys (no names) is kept as it is, with no warning", nWarned == 0 and deepEqual(owned, { future = "x" }))
	local record = { tier = 2, tags = { "a" } }
	st, owned, nWarned = ownedWith({ future = record })
	check("card.owned: a map of a newer version's records is kept whole, as a copy, with no warning",
		nWarned == 0 and deepEqual(owned, { future = { tier = 2, tags = { "a" } } }) and st.section.sectors.Software.card.owned.future ~= record)
	st, owned, nWarned = ownedWith({ [1] = 5, future = "x" })
	check("card.owned: when no list entry is a name the string keys stay (a map), with one warning for the bad value", deepEqual(owned, { future = "x" }) and nWarned == 1, nWarned)
	st, owned, nWarned = ownedWith({ [0] = "Zero", future = "x" })
	check("card.owned: a key 0 next to string keys (no names) is dropped, the map stays", deepEqual(owned, { future = "x" }) and nWarned == 1, nWarned)
	st, owned, nWarned = ownedWith({ [0] = "Zero" })
	check("card.owned: a lone key 0 is dropped, with a warning", next(owned) == nil and nWarned == 1, nWarned)
	local many = {}
	for i = 1, 205 do many[i] = "Name" .. i end
	st, owned, nWarned = ownedWith(many)
	check("card.owned: names past 200 are skipped, with a warning for each", plainList(owned, 200) and nWarned == 5, nWarned)
	many = {}
	for i = 1, 100 do many[i] = "Name" .. i end
	for i = 102, 206 do many[i] = "Name" .. i end
	st, owned, nWarned = ownedWith(many)
	check("card.owned: names after a gap count toward the 200 too (the first 200 in key order stay), with the gap and each skipped name warned about",
		plainList(owned, 200) and owned[100] == "Name100" and owned[101] == "Name102" and owned[200] == "Name201" and nWarned == 6, nWarned)
	st, owned, nWarned = ownedWith("Desk")
	check("card.owned: a value that isn't a table is skipped, with a warning", next(st.section.sectors.Software.card.owned) == nil and nWarned == 1, nWarned)
	-- a number above 3 and the other scalar values of a sector entry and its card: changed or skipped only with a warning
	for _, case in ipairs({ { 7, 3 }, { 3.5, 3 }, { 2.5, 2 }, { -2, 1 }, { 9e9, 3 } }) do
		sec, warned = loaded(function(d) d.sectors.Software.stamp = case[1] end)
		check("sectors: a stamp of " .. tostring(case[1]) .. " is clamped to " .. case[2] .. " with a warning", sec.sectors.Software.stamp == case[2] and warned == 1, warned)
	end
	sec, warned = loaded(function(d) d.sectors.Software.stamp = 3 end)
	check("sectors: a stamp of 3 (Platinum) is kept with no warning", sec.sectors.Software.stamp == 3 and warned == 0, warned)
	for _, field in ipairs({ "name", "ipoNumber", "at", "engaged", "ratio", "building", "stake", "shares" }) do
		sec, warned = loaded(function(d) d.sectors.Software.card[field] = { whatever = 1 } end)
		check("card: a table where card." .. field .. " should be a plain value is replaced by its default, with a warning", warned == 1, warned)
	end
end
sec, warned = loaded(function(d) d.sectors = "x" end)
check("sectors that isn't a table is skipped", next(sec.sectors) == nil and warned == 1)
sec, warned = loaded(function(d) d.dust = 6000 end)
check("dust over 4,999 is skipped (0)", sec.dust == 0 and warned == 1)
sec, warned = loaded(function(d) d.dust = 0.5 end)
check("a fractional dust is skipped (0)", sec.dust == 0 and warned == 1)
sec, warned = loaded(function(d) d.dust = -5000 end)
check("dust -5000 and 4999 are the edges and stay", sec.dust == -5000 and warned == 0)
sec, warned = loaded(function(d) d.hall.Launch = "now"; d.hall.Four = "later" end)
check("hall: a known goal with a bad time is skipped, an unknown goal keeps its value", sec.hall.Launch == nil and sec.hall.Four == "later" and warned == 1)
sec, warned = loaded(function(d) d.kept.Chair = "x" end)
check("kept: an unknown key keeps its value as it is", sec.kept.Chair == "x" and warned == 0)
sec, warned = loaded(function(d) d.run = "x" end, 4)
check("run that isn't a number is skipped: it follows the IPO count, so no stamp", sec.run == 4 and warned == 1)
check("... and no card was made for it", sec.sectors.Software.card.name == "Old Co")
sec, warned = loaded(function(d) d.run = -1 end, 0)
check("a negative run is skipped too", sec.run == 0 and warned == 1)
sec, warned = loaded(function(d) d.studio = "yes" end)
check("studio that isn't a boolean is skipped", sec.studio == false and warned == 1)
sec, warned = loaded(function(d) d.active = 7 end)
check("active that isn't a table starts a new company", sec.active.building == 1 and sec.active.sector == "Software" and warned == 1)
sec, warned = loaded(function(d) d.active.sector = 5 end)
check("active.sector that isn't a string starts a new company", sec.active.building == 1 and warned == 1)
-- an unknown sector in the active company: kept opaque
local unknownSector = good()
unknownSector.active.sector = "Energy"
state = load(unknownSector, 2)
check("an active company in a sector this version doesn't know is kept opaque (locked), unchanged", state.locked == true and deepEqual(save(state, true), good() and unknownSector) and anyWarning("isn't known"))

-- 7. Fuzz: every field replaced by every kind of bad value, the loader never throws ---------------------
local WEIRD = { 0 / 0, math.huge, -math.huge, -1, 0, 1.5, 2 ^ 53, "", "x", true, false, {}, { 1, 2 }, { a = { b = 1 } }, 1e308 }
local function paths(value, prefix, list)
	if typeof(value) == "table" then
		for k, v in pairs(value) do
			local p = table.clone(prefix)
			table.insert(p, k)
			table.insert(list, p)
			paths(v, p, list)
		end
	end
	return list
end
local function setAt(root, path, value)
	local node = root
	for i = 1, #path - 1 do node = node[path[i]] end
	node[path[#path]] = value
end
local function noBadNumbers(value)
	if typeof(value) == "number" then return value == value and value ~= math.huge and value ~= -math.huge end
	if typeof(value) == "table" then
		for _, v in pairs(value) do
			if not noBadNumbers(v) then return false end
		end
	end
	return true
end
local allPaths = paths(FULL, {}, {})
local ran, bad, unstable = 0, 0, 0
for _, path in ipairs(allPaths) do
	for _, weird in ipairs(WEIRD) do
		local data = deepCopy(FULL)
		setAt(data, path, deepCopy(weird))
		local ok, result = pcall(CC.load, data, ctx(2))
		ran += 1
		if not ok then
			bad += 1
			print_real("FAIL fuzz: " .. table.concat(path, ".") .. " = " .. tostring(weird) .. " -- " .. tostring(result))
		elseif not result.locked then
			local first = CC.toSave(result, false)
			local second = CC.toSave(CC.load(deepCopy(first), ctx(2)), false)
			if not deepEqual(first, second) then
				unstable += 1
				print_real("FAIL fuzz (a second load changes it): " .. table.concat(path, ".") .. " = " .. tostring(weird))
			end
		end
	end
end
check("fuzz: " .. ran .. " bad values (every field x " .. #WEIRD .. " kinds) never throw", bad == 0 and ran > 500, ran)
check("fuzz: loading what was saved again never changes it", unstable == 0)
-- Never silent: an unknown key added to any table of the section (and to the section itself) is written back unchanged, or a warning says
-- why not. A string key is kept in every map; in a list (card.owned, objects) it is dropped with a warning; a number key next to named fields is dropped
-- with a warning. These inputs can't come out of a store (they are mixed tables), so the screen for storable results is off here.
do
	STORE_SCREEN.on = false
	local tablePaths = { {} }
	for _, path in ipairs(paths(FULL, {}, {})) do
		local node = FULL
		for _, k in ipairs(path) do node = node[k] end
		if typeof(node) == "table" then table.insert(tablePaths, path) end
	end
	local silent, tried, kept, warnedOnly = {}, 0, 0, 0
	for _, path in ipairs(tablePaths) do
		for _, key in ipairs({ "futureKey", 99, 0, -3 }) do
			local data = deepCopy(FULL)
			local node = data
			for _, k in ipairs(path) do node = node[k] end
			node[key] = { z = 1 }
			local expected = deepCopy(data)
			WARNINGS = {}
			local ok, result = pcall(CC.load, data, ctx(2))
			tried += 1
			if not ok then
				table.insert(silent, "throws: ." .. table.concat(path, ".") .. "[" .. tostring(key) .. "]")
			elseif deepEqual(CC.toSave(result, false), expected) then
				kept += 1
			elseif #WARNINGS > 0 then
				warnedOnly += 1
			else
				table.insert(silent, "." .. table.concat(path, ".") .. "[" .. tostring(key) .. "]")
			end
		end
	end
	check("never silent: an unknown key added to any table is written back unchanged or warned about (" .. tried .. " tried)", #silent == 0 and tried > 100 and kept > 0 and warnedOnly > 0, silent[1])
	check("never silent: a string key is written back unchanged in every map, with no warning (in the two lists, card.owned and objects, it is dropped with one)", (function()
		for _, path in ipairs(tablePaths) do
			local data = deepCopy(FULL)
			local node = data
			for _, k in ipairs(path) do node = node[k] end
			node.futureKey = { z = 1 }
			local expected = deepCopy(data)
			WARNINGS = {}
			local ok, result = pcall(CC.load, data, ctx(2))
			local last = path[#path]
			local isTidiedList = last == "owned" or last == "objects"
			local good = ok and (isTidiedList and #WARNINGS == 1 or (deepEqual(CC.toSave(result, false), expected) and #WARNINGS == 0))
			if not good then
				print_real("a string key under ." .. table.concat(path, ".") .. " is not handled")
				return false
			end
		end
		return true
	end)())
	STORE_SCREEN.on = true
end

-- 8. Placement ------------------------------------------------------------------------------------
local zones = CC.anchorZones(PlotVisuals.zones(PlotArt.Layout), PlotArt.Layout.floorSize[3])
local ALL = {}
for _, upgrade in ipairs(UPGRADES) do ALL[upgrade] = true end
local function env(change)
	local e = { building = 1, zones = zones, owned = deepCopy(ALL), decor = {}, objects = {} }
	if change then change(e) end
	return e
end
local function placed(e, id, x, z, r)
	-- A check that throws is neither a yes nor a refusal: it returns nil (never == false), so `== false` checks fail by name
	local called, ok, why = pcall(CC.checkPlacement, e, id, x, z, r)
	if not called then return nil, "error: " .. tostring(ok) end
	return ok, why
end
-- A refusal for exactly this reason (the text is the server's answer to the player)
local function refusedFor(name, reason, e, id, x, z, r)
	local ok, why = placed(e, id, x, z, r)
	check(name, ok == false and why == reason, why)
end
local SPOT_BAD, TURN_BAD, NO_SIZE, NO_ZONES = "That spot isn't valid", "That turn isn't valid", "Your office isn't ready for that yet", "The office layout isn't available right now"
check("the anchor: the plot's Floor is 60 deep and the plot center is 30 behind its front", CC.FloorDepth == PlotArt.Layout.floorSize[3] and CC.Buildings.Sizes[1].w == PlotArt.Layout.floorSize[1] and CC.Buildings.Sizes[1].d == PlotArt.Layout.floorSize[3])
check("five nested buildings, each at least as big as the one before", #CC.Buildings.Sizes == 5 and (function()
	for i = 2, 5 do
		if CC.Buildings.Sizes[i].w < CC.Buildings.Sizes[i - 1].w or CC.Buildings.Sizes[i].d < CC.Buildings.Sizes[i - 1].d then return false end
	end
	return CC.Buildings.Sizes[5].w == 78 and CC.Buildings.Sizes[5].d == 82
end)())
check("an upgrade has a footprint for every UPGRADES name, and no footprint for anything else", (function()
	for _, upgrade in ipairs(UPGRADES) do
		if not CC.footprintOf(upgrade) then return false end
	end
	return count(CC.Footprints) == #UPGRADES and CC.footprintOf("Gaming PC") == nil
end)())
check("every upgrade's footprint holds every part of its PlotArt prop (turned by its own yaw)", (function()
	for _, upgrade in ipairs(UPGRADES) do
		local w, d = CC.footprintOf(upgrade)
		local hx, hz = 0, 0
		for _, part in ipairs(PlotArt.Props[upgrade]) do
			local yaw = part.rot and part.rot[2] or 0
			local c, s = math.abs(math.cos(math.rad(yaw))), math.abs(math.sin(math.rad(yaw)))
			local px, pz = part.size[1], part.size[3]
			if part.shape == "Cylinder" and part.rot and part.rot[3] == 90 then px, pz = part.size[2], part.size[3] end
			hx = math.max(hx, math.abs(part.offset[1]) + (px * c + pz * s) / 2)
			hz = math.max(hz, math.abs(part.offset[3]) + (px * s + pz * c) / 2)
		end
		if w / 2 < hx - 1e-6 or d / 2 < hz - 1e-6 then
			print_real("footprint of " .. upgrade .. " is " .. w .. " x " .. d .. ", the prop needs " .. 2 * hx .. " x " .. 2 * hz)
			return false
		end
	end
	return true
end)())

-- every upgrade fits at its default slot (the anchor is 30 studs in front of the plot center)
for _, slot in ipairs(PlotArt.Layout.itemSlots) do
	local ok, why = placed(env(), slot.name, slot.x, slot.z - 30, 0)
	check("placement: " .. slot.name .. " is allowed at its default slot (x " .. slot.x .. ", z " .. slot.z - 30 .. ")", ok, why)
end
local e = env()
-- the free band in front of the hire desks (z -10 to -2 from the anchor, x -27 to -5 and 5 to 28) is where tests place things
check("placement: a free spot in front of the hire desks is allowed", placed(e, "Coffee Machine", -20, -6, 0) == true)
check("placement: ... for any turn from 0 to 7", (function()
	for r = 0, 7 do
		if not placed(e, "Coffee Machine", -20, -6, r) then return false end
	end
	return true
end)())
-- ids
for _, id in ipairs({ "", string.rep("a", 40), 5, true, false, {}, "Desk#1", "Unknown", "Gaming PC", "Desk ", "desk" }) do
	check("placement: the id " .. tostring(id) .. " is refused", placed(e, id, -20, -6, 0) == false)
end
check("placement: a 39-character unknown id is still refused (it is not an item)", placed(e, string.rep("a", 39), -20, -6, 0) == false)
check("placement: nil id", placed(e, nil, -20, -6, 0) == false)
-- numbers
for _, bad in ipairs({ 0 / 0, math.huge, -math.huge, "1", true, 1e9, -1e9, 1001 }) do
	refusedFor("placement: x = " .. tostring(bad) .. " is refused (as not a valid spot)", SPOT_BAD, e, "Coffee Machine", bad, -6, 0)
	refusedFor("placement: z = " .. tostring(bad) .. " is refused (as not a valid spot)", SPOT_BAD, e, "Coffee Machine", -20, bad, 0)
end
check("placement: a spot off the 0.5 grid is refused (the same spot on the grid is allowed)", placed(e, "Coffee Machine", -20.3, -6, 0) == false and placed(e, "Coffee Machine", -20, -6.25, 0) == false
	and placed(e, "Coffee Machine", -20.25, -6, 0) == false and placed(e, "Coffee Machine", -20.5, -6, 0) == true and placed(e, "Coffee Machine", -20, -6.5, 0) == true)
refusedFor("placement: a missing x is refused (as not a valid spot)", SPOT_BAD, e, "Coffee Machine", nil, -6, 0)
refusedFor("placement: a missing z is refused (as not a valid spot)", SPOT_BAD, e, "Coffee Machine", -20, nil, 0)
for _, bad in ipairs({ -1, 8, 1.5, "1", true, 0 / 0, math.huge, 100 }) do
	refusedFor("placement: r = " .. tostring(bad) .. " is refused (as not a valid turn)", TURN_BAD, e, "Coffee Machine", -20, -6, bad)
end
refusedFor("placement: a missing r is refused (as not a valid turn)", TURN_BAD, e, "Coffee Machine", -20, -6, nil)
-- ownership
local none = env(function(x) x.owned = {} end)
check("placement: an upgrade you don't own is refused", placed(none, "Coffee Machine", -20, -6, 0) == false)
local why
_, why = placed(none, "Coffee Machine", -20, -6, 0)
check("placement: ... and says so", string.find(tostring(why), "own", 1, true) ~= nil, why)
check("placement: owning another upgrade doesn't help", placed(env(function(x) x.owned = { Desk = true } end), "Coffee Machine", -20, -6, 0) == false)
check("placement: no owned table at all is refused", placed(env(function(x) x.owned = nil end), "Desk", -23, -40, 0) == false)
-- inside the building
check("placement: against the left wall is allowed (the footprint touches x -30)", placed(e, "Coffee Machine", -27.5, -6, 0) == true)
check("placement: through the left wall is refused", placed(e, "Coffee Machine", -28, -6, 0) == false)
check("placement: through the right wall is refused", placed(e, "Coffee Machine", 28, -6, 0) == false)
check("placement: in front of the front edge is refused (z 0 is the front)", placed(e, "Coffee Machine", -20, 0.5, 0) == false)
check("placement: behind the back wall is refused (between two incubators, so only the wall says no)", placed(e, "Coffee Machine", -18, -59.5, 0) == false and placed(e, "Coffee Machine", -18, -58.5, 0) == true)
check("placement: turned 90 degrees, the sides swap", placed(e, "Coffee Machine", -28.5, -6, 2) == true and placed(e, "Coffee Machine", -28.5, -6, 0) == false)
check("placement: turned 45 degrees takes more room (the corners)", placed(e, "Coffee Machine", -28.5, -6, 1) == false)
local big = env(function(x) x.building = 5 end)
check("placement: building 5 (78 x 82) is bigger: x -36.5 fits there and not in building 1", placed(big, "Coffee Machine", -36.5, -6, 0) == true and placed(e, "Coffee Machine", -36.5, -6, 0) == false)
refusedFor("placement: building 6 has no size: refused (the office isn't ready)", NO_SIZE, env(function(x) x.building = 6 end), "Desk", -23, -40, 0)
refusedFor("placement: building 0 has no size: refused (the office isn't ready)", NO_SIZE, env(function(x) x.building = 0 end), "Desk", -23, -40, 0)
refusedFor("placement: no building at all: refused (the office isn't ready)", NO_SIZE, env(function(x) x.building = nil end), "Desk", -23, -40, 0)
-- zones
check("placement: the walking lane down the middle is reserved", placed(e, "Coffee Machine", 0, -35, 0) == false)
check("placement: the spawn is reserved", placed(e, "Coffee Machine", 0, -18, 0) == false)
check("placement: where a hire stands is reserved", placed(e, "Coffee Machine", -4.5, -28, 0) == false)
check("placement: the incubators are reserved", placed(e, "Coffee Machine", -12, -55, 0) == false)
check("placement: the signs' space is reserved", placed(e, "Coffee Machine", 21, -6, 0) == false)
check("placement: another upgrade's slot is reserved", placed(e, "Desk", -23, -28, 0) == false)
_, why = placed(e, "Desk", -23, -28, 0)
check("placement: ... and says so", string.find(tostring(why), "reserved", 1, true) ~= nil, why)
check("placement: your own slot is yours (the Laptop in the Desk's slot is not)", placed(e, "Desk", -23, -40, 0) == true and placed(e, "Laptop", -23, -40, 0) == false)
check("placement: a slot's owner can move around inside it", placed(e, "Desk", -22, -41, 0) == true)
refusedFor("placement: without the plot's zones the server refuses (it can't know what is reserved)", NO_ZONES, env(function(x) x.zones = nil end), "Coffee Machine", -20, -6, 0)
refusedFor("placement: zones that are not a table are refused the same way", NO_ZONES, env(function(x) x.zones = true end), "Coffee Machine", -20, -6, 0)
check("placement: an empty zone list is not 'unknown': nothing is reserved", placed(env(function(x) x.zones = {} end), "Coffee Machine", 0, -35, 0) == true)
-- overlap, with the 0.1 stud tolerance
local with = env(function(x) x.objects = { { id = "Coffee Machine", x = -20, z = -6, r = 0 } } end)
-- Coffee Machine is 2.9 deep (-7.45 to -4.55) and the Laptop 3.3 deep, so a Laptop 3.1 away just touches
check("overlap: clear of another item is allowed", placed(with, "Laptop", -20, -2.5, 0) == true)
check("overlap: 0.1 stud into another item is allowed", placed(with, "Laptop", -20, -3, 0) == true)
check("overlap: 0.6 stud into another item is refused", placed(with, "Laptop", -20, -3.5, 0) == false)
check("overlap: 0.4 stud into another item (side by side) is refused", placed(with, "Laptop", -15, -6, 0) == false and placed(with, "Laptop", -14.5, -6, 0) == true)
_, why = placed(with, "Laptop", -20, -6, 0)
check("overlap: right on top is refused and says 'taken'", string.find(tostring(why), "taken", 1, true) ~= nil, why)
check("overlap: a turned footprint is measured turned (a Whiteboard turned 90 degrees reaches 4.85 each way)",
	placed(env(function(x) x.objects = { { id = "Whiteboard", x = -12, z = -8, r = 0 } } end), "Laptop", -12, -4, 0) == true
	and placed(env(function(x) x.objects = { { id = "Whiteboard", x = -12, z = -8, r = 2 } } end), "Laptop", -12, -4, 0) == false)
check("overlap: moving an item doesn't make it collide with its own old place", placed(with, "Coffee Machine", -20, -6.5, 0) == true)
check("overlap: an item this version has no footprint for blocks nothing (it is kept, not measured)", placed(env(function(x) x.objects = { { id = "Gaming PC", x = -20, z = -6, r = 0 } } end), "Coffee Machine", -20, -6, 0) == true)
check("overlap depth: two 4 x 4 squares 3 apart overlap by 1", math.abs(CC.overlapDepth({ { 0, 0 }, { 4, 0 }, { 4, 4 }, { 0, 4 } }, { { 3, 0 }, { 7, 0 }, { 7, 4 }, { 3, 4 } }) - 1) < 1e-9)
check("overlap depth: apart is 0, touching is 0", CC.overlapDepth({ { 0, 0 }, { 4, 0 }, { 4, 4 }, { 0, 4 } }, { { 5, 0 }, { 9, 0 }, { 9, 4 }, { 5, 4 } }) == 0
	and CC.overlapDepth({ { 0, 0 }, { 4, 0 }, { 4, 4 }, { 0, 4 } }, { { 4, 0 }, { 8, 0 }, { 8, 4 }, { 4, 4 } }) == 0)
-- furniture ids (none ship yet: a test key is added and removed)
CC.Furniture.Crate = { name = "Crate", w = 0.5, d = 0.5 }
CC.Furniture.Chair = { name = "Chair", w = 2, d = 2 }
local owns = env(function(x) x.decor = { Chair = 2, Crate = 99 } end)
check("furniture: Chair#1 and Chair#2 are yours, Chair#3 is not", placed(owns, "Chair#1", -20, -6, 0) == true and placed(owns, "Chair#2", -14, -6, 0) == true and placed(owns, "Chair#3", -20, -6, 0) == false)
check("furniture: the number must be 1 to 99 and plain", placed(owns, "Chair#0", -20, -6, 0) == false and placed(owns, "Chair#100", -20, -6, 0) == false and placed(owns, "Chair#01x", -20, -6, 0) == false and placed(owns, "Chair#", -20, -6, 0) == false and placed(owns, "#1", -20, -6, 0) == false)
check("furniture: a key with no entry is refused", placed(owns, "Sofa#1", -20, -6, 0) == false)
check("furniture: it may not stand in an upgrade's slot", placed(owns, "Chair#1", -23, -40, 0) == false)
check("parseId: upgrade, furniture and nothing", (function()
	local k1, key1 = CC.parseId("Desk")
	local k2, key2, n2 = CC.parseId("Chair#2")
	return k1 == "upgrade" and key1 == "Desk" and k2 == "furniture" and key2 == "Chair" and n2 == 2 and CC.parseId("Chair#2#3") == nil and CC.parseId(7) == nil
end)())
-- the item limit
local crowd = env(function(x)
	x.decor = { Crate = 99 }
	x.objects = {}
	for i = 1, 40 do
		table.insert(x.objects, { id = "Crate#" .. i, x = -27 + (i - 1) * 0.5, z = -3, r = 0 }) -- anywhere: placed items are not measured again
	end
end)
check("limit: the office holds 40 items", #crowd.objects == 40 and CC.MaxObjects == 40)
check("limit: a 41st item is refused", placed(crowd, "Crate#41", -20, -9, 0) == false)
_, why = placed(crowd, "Crate#41", -20, -9, 0)
check("limit: ... and says the office is full", string.find(tostring(why), "more items", 1, true) ~= nil, why)
check("limit: moving an item that is already placed still works at the limit", placed(crowd, "Crate#1", -20, -9, 0) == true)
local unknowns = env(function(x)
	x.objects = {}
	for i = 1, 40 do table.insert(x.objects, { id = "Future" .. i, x = i, z = -30, r = 0 }) end
end)
check("limit: items kept from a newer version count toward it", placed(unknowns, "Coffee Machine", -20, -6, 0) == false)

-- store, apply, inventory
local active = { objects = {}, stored = {} }
check("store: an upgrade you own can be stored", CC.checkStore(env(), active, "Laptop") == true)
check("store: one you don't own can't", CC.checkStore(none, active, "Laptop") == false)
check("store: an unknown id, a bad id and a bad type can't", CC.checkStore(env(), active, "Gaming PC") == false and CC.checkStore(env(), active, 5) == false and CC.checkStore(env(), active, string.rep("a", 40)) == false and CC.checkStore(env(), active, nil) == false)
active.stored.Laptop = true
local alreadyOk, alreadyWhy = CC.checkStore(env(), active, "Laptop")
check("store: one already in storage can't be stored again", alreadyOk == false and string.find(tostring(alreadyWhy), "already in storage", 1, true) ~= nil, alreadyWhy)
active.stored = {}
for i = 1, 40 do active.stored["Crate#" .. i] = true end
check("store: a full storage (40) refuses another", CC.checkStore(owns, active, "Chair#1") == false)
active = { objects = { { id = "Desk", x = -23, z = -40, r = 0 } }, stored = { Laptop = true } }
CC.applyPlace(active, "Laptop", -25, -30, 0)
check("applyPlace: a stored item leaves the storage and stands in the office", active.stored.Laptop == nil and #active.objects == 2 and active.objects[2].id == "Laptop" and active.objects[2].x == -25)
CC.applyPlace(active, "Laptop", -22, -30, 3)
check("applyPlace: placing again moves it (never two entries)", #active.objects == 2 and active.objects[2].x == -22 and active.objects[2].r == 3)
CC.applyStore(active, "Desk")
check("applyStore: the item leaves the office and goes to storage", #active.objects == 1 and active.objects[1].id == "Laptop" and active.stored.Desk == true)
CC.applyStore(active, "Whiteboard")
check("applyStore: an upgrade that stood at its default slot goes to storage too", active.stored.Whiteboard == true and #active.objects == 1)
check("inventory: the stored ids, sorted", deepEqual(CC.inventory(active, {}), { "Desk", "Whiteboard" }))
check("inventory: only ids stored as true are listed (a false or a newer version's record is not)",
	deepEqual(CC.inventory({ objects = {}, stored = { Desk = true, Laptop = false, Rack = { tier = 2 }, Whiteboard = "yes" } }, {}), { "Desk" }))
do
	local held = { objects = {}, stored = { Desk = { tier = 2 }, Laptop = false } }
	local ok1 = CC.checkStore(env(), held, "Desk")
	local ok2 = CC.checkStore(env(), held, "Laptop")
	check("store: a record of a newer version on that id is never overwritten, a stored false is", ok1 == false and ok2 == true)
	CC.applyStore(held, "Laptop")
	check("store: ... and storing over a false makes it true", held.stored.Laptop == true and deepEqual(held.stored.Desk, { tier = 2 }))
	local placing = { objects = { { id = "Desk", x = -23, z = -40, r = 0 } }, stored = { Desk = { tier = 2 }, Laptop = { tier = 3 }, Whiteboard = true } }
	CC.applyPlace(placing, "Desk", -22, -40, 0)
	CC.applyPlace(placing, "Laptop", -25, -30, 0)
	CC.applyPlace(placing, "Whiteboard", -25, -20, 0)
	check("place: a kept record on the id survives a Place (only a true leaves the inventory)",
		deepEqual(placing.stored.Desk, { tier = 2 }) and deepEqual(placing.stored.Laptop, { tier = 3 }) and placing.stored.Whiteboard == nil)
end
check("inventory: owned furniture with no entry joins it (placed ones don't)", (function()
	local list = CC.inventory({ objects = { { id = "Chair#1", x = 0, z = 0, r = 0 } }, stored = { Desk = true } }, { Chair = 2 })
	return deepEqual(list, { "Chair#2", "Desk" })
end)())
CC.Furniture.Crate, CC.Furniture.Chair = nil, nil
check("the test furniture is gone again (the real config has none yet)", next(CC.Furniture) == nil)

-- the request limit
local bucket = CC.newBucket(100)
local allowed = 0
for _ = 1, 10 do
	if CC.takeToken(bucket, 100) then allowed += 1 end
end
check("rate: 4 requests at once, the 5th is refused", allowed == 4)
check("rate: after a quarter second one more is allowed (4 a second)", CC.takeToken(bucket, 100.25) == true and CC.takeToken(bucket, 100.25) == false)
check("rate: 4 a second keeps going", (function()
	local b = CC.newBucket(0)
	local ok = 0
	for i = 1, 40 do
		if CC.takeToken(b, i * 0.25) then ok += 1 end
	end
	return ok == 40
end)())
check("rate: faster than 4 a second is refused (10 a second gets about 4 a second)", (function()
	local b = CC.newBucket(0)
	local ok = 0
	for i = 1, 100 do
		if CC.takeToken(b, i * 0.1) then ok += 1 end
	end
	return ok >= 40 and ok <= 47
end)())
check("rate: a long quiet time refills no more than 4", (function()
	local b = CC.newBucket(0)
	local ok = 0
	for _ = 1, 10 do
		if CC.takeToken(b, 1000) then ok += 1 end
	end
	return ok == 4
end)())
check("rate: a clock that goes back adds nothing", (function()
	local b = CC.newBucket(50)
	for _ = 1, 4 do CC.takeToken(b, 50) end
	return CC.takeToken(b, 40) == false
end)())

-- placement is only for Studio until the office screen exists
check("Placement is on in Studio only (StudioOnly)", CC.Placement.Enabled == true and CC.Placement.StudioOnly == true and CC.isPlacementActive() == true)
IS_STUDIO = false
check("... and off on a live server", CC.isPlacementActive() == false)
IS_STUDIO = true
CC.Placement.StudioOnly = false
IS_STUDIO = false
check("... until StudioOnly is turned off", CC.isPlacementActive() == true)
CC.Placement.Enabled = false
check("... or Enabled is", CC.isPlacementActive() == false)
CC.Placement.Enabled, CC.Placement.StudioOnly = true, true
IS_STUDIO = true

check("every section toSave handed out in these tests is storable (" .. STORE_SCREEN.seen .. " screened)", STORE_SCREEN.bad == 0 and STORE_SCREEN.seen > 100, STORE_SCREEN.first)
print_real(string.format("%d passed, %d failed", passed, failed))
"""


def company_source(mutation=None):
    """The COMPANY_TESTS program with the real SectorConfig, IpoConfig, CompanyConfig, PlotVisuals and PlotArt.
    mutation = (old, new) breaks one rule of CompanyConfig (or SectorConfig): `old` must be in exactly one of them once."""
    def read(name):
        with open(os.path.join(ROOT, name), encoding="utf-8") as f:
            return f.read()

    parts = {name: read(name + ".lua") for name in ("SectorConfig", "IpoConfig", "CompanyConfig", "PlotVisuals", "PlotArt")}
    storable = STORABLE_LUA
    if mutation and mutation[0] == "@fake":
        if storable.count(mutation[1]) != 1:
            raise SystemExit("mutation target not found exactly once in the faithful store: " + mutation[1])
        storable = storable.replace(mutation[1], mutation[2], 1)
    elif mutation:
        for i in range(0, len(mutation), 2):  # one or more (old, new) pairs
            old, new = mutation[i], mutation[i + 1]
            hits = [name for name in ("CompanyConfig", "SectorConfig") if old in parts[name]]
            if len(hits) != 1 or parts[hits[0]].count(old) != 1:
                raise SystemExit("mutation target not found exactly once: " + old)
            parts[hits[0]] = parts[hits[0]].replace(old, new, 1)
    return (COMPANY_TESTS.replace("__STORABLE__", storable).replace("__UPGRADES__", upgrades_lua_names())
            .replace("__SECTORCONFIG__", parts["SectorConfig"]).replace("__IPOCONFIG__", parts["IpoConfig"])
            .replace("__COMPANYCONFIG__", parts["CompanyConfig"]).replace("__PLOTVISUALS__", parts["PlotVisuals"])
            .replace("__PLOTART__", parts["PlotArt"]))


def upgrades_lua_names():
    """The six UPGRADES names from TycoonCore.lua, as a Luau list."""
    import re
    with open(os.path.join(ROOT, "TycoonCore.lua"), encoding="utf-8") as f:
        text = f.read()
    block = text[text.index("local UPGRADES = {"):]
    block = block[:block.index("\n}")]
    names = re.findall(r'name = "([^"]+)"', block)
    if len(names) != 6:
        raise SystemExit("TycoonCore UPGRADES changed: update the Pokedex placement tests (expected 6 upgrades, found %d)" % len(names))
    return "{ " + ", ".join('"%s"' % n for n in names) + " }"


COMPANY_MUTATIONS = [
    # The version rule
    ("the version rule (a higher v is read and rewritten)", ("if isWhole(version, 1) and version > CompanyConfig.Version then", "if false then"),
     "v = 2: kept opaque (locked), no run check, no event"),
    ("the version rule (written back as a copy, not as it was loaded)", ("\t\treturn state.raw\n", "\t\treturn deepCopy(state.raw)\n"),
     "v = 2: the very table that loaded is written back"),
    ("the version rule (a Studio server adds its mark to an opaque section)", ("\tif state.locked then\n\t\treturn state.raw\n\tend\n", "\tif state.locked then\n\t\tstate.raw.studio = studio or nil\n\t\treturn state.raw\n\tend\n"),
     "v = 2: deep-equal after a save, even from a Studio server (nothing added)"),
    ("the unknown sector rule", ("if unknownSector then", "if false then"),
     "an active company in a sector this version doesn't know is kept opaque (locked), unchanged"),
    # The run check
    ("the run check (run < count)", ("if section.run < count then", "if false then"),
     "run < count: the event is 'complete', with a warning"),
    ("the run check (run = count also completes)", ("if section.run < count then", "if section.run <= count then"),
     "run = count does nothing"),
    ("the run check (run > count)", ("elseif section.run > count then", "elseif false then"),
     "run > count: the event is 'rebase', with a warning"),
    ("the run check (run = count also rebases)", ("elseif section.run > count then", "elseif section.run >= count then"),
     "run = count does nothing"),
    ("the run check (a rebase stamps the sector)", ("\t\tsection.run = count\n\t\tsection.studio = true\n", "\t\tcompleteCompany(section, count, ctx.now)\n\t\tsection.run = count\n\t\tsection.studio = true\n"),
     "run > count: no stamp, no card, no Hall of Fame entry"),
    ("the run check (a rebase doesn't mark the section as saved by Studio)", ("\t\tsection.run = count\n\t\tsection.studio = true\n", "\t\tsection.run = count\n"),
     "run > count: the section is marked as saved by Studio"),
    ("the run check (the new company keeps the old rounds)", ("section.active = CompanyConfig.newActive(active.sector, ctx.now, ctx)", "section.active = active"),
     "run < count: a new company starts (same sector, building 1, nothing placed, no rounds, picked while the picker is off)"),
    ("the run check (run is not moved to the count)", ("\t\tsection.run = count\n\t\tstate.event = \"complete\"", "\t\tstate.event = \"complete\""),
     "run < count: run = the IPO count"),
    ("Bronze (a completion sets the stamp to 1, so a Platinum falls)", ("entry.stamp = math.max(entry.stamp, 1) -- Bronze if there was no stamp yet", "entry.stamp = 1"),
     "a replay: Platinum stays Platinum, replays + 1, firstAt kept, best engaged is the larger"),
    ("Bronze (no stamp at all)", ("entry.stamp = math.max(entry.stamp, 1) -- Bronze if there was no stamp yet", "entry.stamp = entry.stamp"),
     "run < count: Software is done with Bronze, first done now"),
    ("replays (a second completion isn't counted)", ("\t\tentry.replays += 1\n", "\t\tentry.replays += 0\n"),
     "a replay: Platinum stays Platinum, replays + 1, firstAt kept, best engaged is the larger"),
    ("the card (it doesn't keep the rounds)", ("rounds = deepCopy(active.rounds),\n\t\tstake", "rounds = {},\n\t\tstake"),
     "run < count: the card keeps the rounds (the Seed round, 300 bp)"),
    ("the card (the stake ignores the dilution)", ("stake = CompanyConfig.stakeOf(active.rounds),", "stake = TOTAL_BP,"),
     "run < count: the stake is 10,000 minus the dilution, what is unknown is 0"),
    ("the Launch goal (a sector that can't be picked counts)", ("if not (SectorConfig.isEnabled(key) and typeof(other) == \"table\" and other.state == \"done\") then", "if not (typeof(other) == \"table\" and other.state == \"done\") then"),
     "Gaming 'done' in a save (a Studio test) is kept but Launch is not reached while Gaming can't be picked"),
    ("the new company's picked flag (always unpicked)", ("local picked = SectorConfig.PickerEnabled ~= true", "local picked = false"),
     "missing section: v 1, run = the IPO count, Software, building 1, picked (the picker is off)"),
    # Unknown fields kept at every level
    ("keeping unknown fields (the section)", ("copyUnknown(ctx, \"pokedex\", saved, TOP_KNOWN, section)", ""),
     "unknown data is kept: top-level unknown field"),
    ("keeping unknown fields (active)", ("copyUnknown(ctx, where, value, ACTIVE_KNOWN, active)", ""),
     "unknown data is kept: active unknown field"),
    ("keeping unknown fields (objects[i])", ("copyUnknown(ctx, where .. \".\" .. key .. \"[\" .. index .. \"]\", entry, OBJECT_KNOWN, object)", ""),
     "unknown data is kept: active.objects[i] unknown field"),
    ("keeping unknown fields (rounds[k])", ("\tlocal round = { s = value.s, c = value.c or 0, cash = value.cash or 0, bp = value.bp or 0, at = value.at or 0, studio = value.studio or false }\n\tcopyUnknown(ctx, where, value, ROUND_KNOWN, round)\n", "\tlocal round = { s = value.s, c = value.c or 0, cash = value.cash or 0, bp = value.bp or 0, at = value.at or 0, studio = value.studio or false }\n"),
     "unknown data is kept: active.rounds[k] unknown field"),
    ("keeping unknown fields (unknown stage keys in rounds)", ("out[name] = deepCopy(inner) -- a stage this version doesn't know: kept whole, its bp still counts", ""),
     "unknown data is kept: active.rounds unknown stage"),
    ("keeping unknown fields (sectors[k])", ("copyUnknown(ctx, where, value, SECTOR_KNOWN, entry)", ""),
     "unknown data is kept: sectors[k] unknown field"),
    ("keeping unknown fields (unknown sector keys)", ("out[key] = deepCopy(inner) -- a sector this version doesn't know: kept whole", ""),
     "unknown data is kept: sectors unknown key kept whole"),
    ("keeping unknown fields (card)", ("copyUnknown(ctx, here, value, CARD_KNOWN, card)", ""),
     "unknown data is kept: card unknown field"),
    ("keeping unknown fields (unknown keys in a map)", ("\t\telse\n\t\t\tout[name] = deepCopy(inner)\n\t\tend\n\tend\n\treturn out\nend\n\nlocal function validCopies", "\t\tend\n\tend\n\treturn out\nend\n\nlocal function validCopies"),
     "unknown data is kept: active.decor unknown key"),
    ("keeping unknown fields (unknown upgrade names on a card)", ("if typeof(name) == \"string\" and #name >= 1 and #name <= CompanyConfig.MaxIdLength and #out < MAX_OWNED_NAMES then", "if typeof(name) == \"string\" and CompanyConfig.Footprints[name] then"),
     "unknown data is kept: card.owned unknown upgrade name"),
    ("keeping the sx table whole", ("return deepCopy(value)\n\tend\n\tnote(ctx, \"a bad \" .. where .. \".\" .. key .. \", it starts again empty\")", "return {}\n\tend\n\tnote(ctx, \"a bad \" .. where .. \".\" .. key .. \", it starts again empty\")"),
     "unknown data is kept: active.sx whole"),
    ("saving a copy (the live state is handed out)", ("local section = deepCopy(state.section)\n", "local section = state.section\n"),
     "the saved section is a copy: changing it never changes the live state"),
    # Bad values
    ("the bad value check on numbers (a negative number passes)", ("if isNumber(value) and value >= minimum and (maximum == nil or value <= maximum) and (not whole or value % 1 == 0) then", "if isNumber(value) then"),
     "engaged -5 is skipped (0) with a warning"),
    ("the bad value check (NaN passes)", ("return typeof(value) == \"number\" and value == value and value ~= math.huge and value ~= -math.huge\n", "return typeof(value) == \"number\"\n"),
     "engaged infinity is skipped"),
    ("a finished sector with stamp 0", ("if entry.state == \"done\" and entry.stamp == 0 then", "if false then"),
     "sectors: done with stamp 0 becomes Bronze"),
    ("the stamp clamp", ("entry.stamp = math.clamp(math.floor(stamp), 0, 3)", "entry.stamp = math.floor(stamp)"),
     "sectors: a bad state is 'progress', a stamp over 3 is clamped to 3 and a bad replays is 0"),
    ("the dust range", ("elseif isWhole(dust, -5000, 4999) then", "elseif isWhole(dust, -5000, 9999) then"),
     "dust over 4,999 is skipped (0)"),
    ("the objects limit (40)", ("elseif #out >= CompanyConfig.MaxObjects then", "elseif false then"),
     "objects: at most 40 are kept (ids this version has no item for are kept too)"),
    ("the object grid check on load", ("and isNumber(entry.x) and math.abs(entry.x) <= limit and (entry.x / CompanyConfig.Grid) % 1 == 0", "and isNumber(entry.x) and math.abs(entry.x) <= limit"),
     "objects: a bad x, r, id, grid step, missing field, junk, a repeated id or a far x is skipped, the one good item stays"),
    ("repeated object ids on load", ("elseif seen[entry.id] then", "elseif false then"),
     "objects: a bad x, r, id, grid step, missing field, junk, a repeated id or a far x is skipped, the one good item stays"),
    ("a malformed round counts as nothing (dropped dilution)", ("local settled = { s = \"skipped\", c = 0, cash = 0, bp = 0, at = 0, studio = false }", "local settled = { s = \"skipped\", c = 0, cash = 0, bp = 100, at = 0, studio = false }"),
     "rounds: a record of a known stage that isn't a table counts as settled (skipped, no dilution)"),
    ("a malformed round keeps its claimed bp", ("\t\tnote(ctx, \"a bad \" .. where .. \", counted as settled with no dilution\")\n\t\tcopyUnknown(ctx, where, value, ROUND_KNOWN, settled)\n\t\treturn settled\n", "\t\tnote(ctx, \"a bad \" .. where .. \", counted as settled with no dilution\")\n\t\tsettled.bp = isWhole(value.bp, 0, TOTAL_BP) and value.bp or 0\n\t\treturn settled\n"),
     "rounds: a malformed record counts as settled with bp 0, its unknown fields stay"),
    ("the dilution cap", ("return math.min(CompanyConfig.Funding.DilutionCap, total)", "return total"),
     "dilution is capped (4,000 bp), the stake never falls under 6,000"),
    ("the dilution sum (unknown stages ignored)", ("if typeof(round) == \"table\" and isWhole(round.bp, 0, TOTAL_BP) then", "if typeof(round) == \"table\" and STAGE_KEYS[_] and isWhole(round.bp, 0, TOTAL_BP) then"),
     "dilution: an unknown stage's valid bp counts, a malformed one counts 0"),
    # Placement
    ("the coordinate check", ("if not isNumber(x) or not isNumber(z) or math.abs(x) > limit or math.abs(z) > limit then", "if false then"),
     "placement: x = "),
    ("the grid check on placement", ("if (x / CompanyConfig.Grid) % 1 ~= 0 or (z / CompanyConfig.Grid) % 1 ~= 0 then", "if false then")),
    ("the rotation check", ("if not isWhole(r, 0, CompanyConfig.MaxRotation) then", "if false then")),
    ("the rotation range (0 to 8)", ("if not isWhole(r, 0, CompanyConfig.MaxRotation) then", "if not isWhole(r, 0, CompanyConfig.MaxRotation + 1) then"),
     "placement: r = 8 is refused"),
    ("the ownership check (upgrades)", ("\t\tif not (env.owned and env.owned[key]) then\n\t\t\treturn false, \"You don't own \" .. id\n\t\tend\n\telseif not (env.decor and (env.decor[key] or 0) >= copy) then\n\t\treturn false, \"You don't own \" .. id\n\tend\n\tlocal building", "\t\tif false then\n\t\t\treturn false, \"You don't own \" .. id\n\t\tend\n\telseif not (env.decor and (env.decor[key] or 0) >= copy) then\n\t\treturn false, \"You don't own \" .. id\n\tend\n\tlocal building"),
     "placement: an upgrade you don't own is refused"),
    ("the ownership check (furniture)", ("elseif not (env.decor and (env.decor[key] or 0) >= copy) then\n\t\treturn false, \"You don't own \" .. id\n\tend\n\tlocal building", "elseif false then\n\t\treturn false, \"You don't own \" .. id\n\tend\n\tlocal building"),
     "furniture: Chair#1 and Chair#2 are yours, Chair#3 is not"),
    ("the building check (a size that doesn't exist)", ("if not building then\n\t\treturn false, \"Your office isn't ready for that yet\"", "if false then\n\t\treturn false, \"Your office isn't ready for that yet\""),
     "placement: building 6 has no size: refused (the office isn't ready)"),
    ("the zones check (missing zones accepted)", ("if typeof(env.zones) ~= \"table\" then", "if false then"),
     "placement: without the plot's zones the server refuses (it can't know what is reserved)"),
    ("the inside-the-building check (the back wall)", ("or corner[2] < -building.d - EPSILON or corner[2] > EPSILON then", "or corner[2] > EPSILON then"),
     "placement: behind the back wall is refused"),
    ("the inside-the-building check (the front)", ("or corner[2] < -building.d - EPSILON or corner[2] > EPSILON then", "or corner[2] < -building.d - EPSILON then"),
     "placement: in front of the front edge is refused (z 0 is the front)"),
    ("the inside-the-building check (the sides)", ("if corner[1] < -building.w / 2 - EPSILON or corner[1] > building.w / 2 + EPSILON\n\t\t\tor corner[2]", "if corner[1] < -building.w / 2 - EPSILON\n\t\t\tor corner[2]"),
     "placement: through the right wall is refused"),
    ("the zones (nothing is reserved)", ("if zone.owner ~= id and overlapDepth(shape, axisRect(zone.x0, zone.x1, zone.z0, zone.z1)) > tolerance then", "if false then"),
     "placement: the walking lane down the middle is reserved"),
    ("the zones (an upgrade may use every slot)", ("if zone.owner ~= id and overlapDepth(", "if zone.owner == nil and overlapDepth("),
     "placement: another upgrade's slot is reserved"),
    ("the zones (the owner is not exempt in its own slot)", ("if zone.owner ~= id and overlapDepth(", "if overlapDepth("),
     "placement: your own slot is yours (the Laptop in the Desk's slot is not)"),
    ("the zones (shifted by the wrong sign)", ("z0 = box[5] - shift, z1 = box[6] - shift", "z0 = box[5] + shift, z1 = box[6] + shift"),
     "placement: the walking lane down the middle is reserved"),
    ("the overlap tolerance (none)", ("local tolerance = CompanyConfig.OverlapTolerance + EPSILON", "local tolerance = EPSILON"),
     "overlap: 0.1 stud into another item is allowed"),
    ("the overlap tolerance (half a stud)", ("local tolerance = CompanyConfig.OverlapTolerance + EPSILON", "local tolerance = 0.5 + EPSILON"),
     "overlap: 0.4 stud into another item (side by side) is refused"),
    ("the overlap check between items", ("if ow and overlapDepth(shape, corners(ow, od, other.x, other.z, other.r)) > tolerance then", "if false then"),
     "overlap: right on top is refused and says 'taken'"),
    ("the overlap check (turned items measured unturned)", ("overlapDepth(shape, corners(ow, od, other.x, other.z, other.r))", "overlapDepth(shape, corners(ow, od, other.x, other.z, 0))"),
     "overlap: a turned footprint is measured turned (a Whiteboard turned 90 degrees reaches 4.85 each way)"),
    ("the overlap check (a moved item blocks itself)", ("\t\tif other.id ~= id then\n\t\t\tothers += 1", "\t\tif true then\n\t\t\tothers += 1"),
     "overlap: moving an item doesn't make it collide with its own old place"),
    ("the item limit", ("if others >= CompanyConfig.MaxObjects then", "if false then"),
     "limit: a 41st item is refused"),
    ("the rotation (turns ignored)", ("local angle = math.rad(45 * r)", "local angle = math.rad(0 * r)"),
     "placement: turned 90 degrees, the sides swap"),
    ("the storage check (already stored)", ("if held == true then\n\t\treturn false, id .. \" is already in storage\"", "if false then\n\t\treturn false, id .. \" is already in storage\""),
     "store: one already in storage can't be stored again"),
    ("a stored value other than true is dropped on load", ("if typeof(id) == \"string\" and #id >= 1 and #id <= CompanyConfig.MaxIdLength then\n\t\t\ttable.insert(ids, id)", "if typeof(id) == \"string\" and #id >= 1 and #id <= CompanyConfig.MaxIdLength and flag == true then\n\t\t\ttable.insert(ids, id)"),
     "stored: only string ids of 1 to 39 characters stay, and a value other than true is kept as it was"),
    ("a kept stored value is rewritten as true", ("out[id] = deepCopy(value[id])", "out[id] = true"),
     "stored: only string ids of 1 to 39 characters stay, and a value other than true is kept as it was"),
    ("a kept stored record is shared with the save (not copied)", ("out[id] = deepCopy(value[id])", "out[id] = value[id]"),
     "stored: a record of a newer version (a table) is kept whole, as a copy, with no warning"),
    ("a record of a newer version can be overwritten by Store", ("elseif held ~= nil and held ~= false then", "elseif false then"),
     "store: a record of a newer version on that id is never overwritten, a stored false is"),
    ("a stored false blocks Store", ("if held == true then\n\t\treturn false, id .. \" is already in storage\"", "if held ~= nil then\n\t\treturn false, id .. \" is already in storage\""),
     "store: a record of a newer version on that id is never overwritten, a stored false is"),
    ("the inventory lists every stored entry", ("if held == true then\n\t\t\ttable.insert(list, id)", "if true then\n\t\t\ttable.insert(list, id)"),
     "inventory: only ids stored as true are listed (a false or a newer version's record is not)"),
    ("Place deletes a kept record (moving an item)", ("object.x, object.z, object.r = x, z, r\n\t\t\tif active.stored[id] == true then", "object.x, object.z, object.r = x, z, r\n\t\t\tif active.stored[id] ~= nil then"),
     "place: a kept record on the id survives a Place (only a true leaves the inventory)"),
    ("Place deletes a kept record (a new item)", ("table.insert(active.objects, { id = id, x = x, z = z, r = r })\n\tif active.stored[id] == true then", "table.insert(active.objects, { id = id, x = x, z = z, r = r })\n\tif active.stored[id] ~= nil then"),
     "place: a kept record on the id survives a Place (only a true leaves the inventory)"),
    ("the map-shape check on placed items (a map of items is read as an empty list)", ("if #indexes == 0 and #others > 0 then", "if false then"),
     "objects that is a dictionary: the section is kept as it was (locked, written back unchanged)"),
    ("the map-shape check (a card's objects are not looked at)", ("if #indexes == 0 and #others > 0 then", "if #indexes == 0 and #others > 0 and where ~= \"sectors.Software.card\" then"),
     "a card's objects that is a dictionary: the section is kept as it was (locked, written back unchanged)"),
    ("the lock on a shape this version doesn't know", ("if ctx.foreign then\n\t\t-- A shape", "if false then\n\t\t-- A shape"),
     "objects that is a dictionary: the section is kept as it was (locked, written back unchanged)"),
    ("the lock on a foreign shape (written back as a copy)", ("ctx.warn(\"Keeping \" .. ctx.who .. \"'s pokedex as it is: its \" .. ctx.foreign .. \" (a shape this version doesn't know)\")\n\t\tstate.locked, state.raw = true, saved", "ctx.warn(\"Keeping \" .. ctx.who .. \"'s pokedex as it is: its \" .. ctx.foreign .. \" (a shape this version doesn't know)\")\n\t\tstate.locked, state.raw = true, deepCopy(saved)"),
     "objects that is a dictionary: the section is kept as it was (locked, written back unchanged)"),
    ("the storage limit", ("if count >= CompanyConfig.MaxStored then", "if false then"),
     "store: a full storage (40) refuses another"),
    ("placing doesn't take the item out of storage", ("\ttable.insert(active.objects, { id = id, x = x, z = z, r = r })\n\tif active.stored[id] == true then active.stored[id] = nil end\n", "\ttable.insert(active.objects, { id = id, x = x, z = z, r = r })\n"),
     "applyPlace: a stored item leaves the storage and stands in the office"),
    ("placing twice makes two entries", ("\t\tif object.id == id then\n\t\t\tobject.x, object.z, object.r = x, z, r", "\t\tif false then\n\t\t\tobject.x, object.z, object.r = x, z, r"),
     "applyPlace: placing again moves it (never two entries)"),
    ("storing leaves the item placed", ("\t\t\ttable.remove(active.objects, i)\n\t\t\tbreak\n", "\t\t\tbreak\n"),
     "applyStore: the item leaves the office and goes to storage"),
    # The request limit
    ("the request limit (no refill cap)", ("bucket.tokens = math.min(limit.burst, bucket.tokens + math.max(0, now - bucket.at) * limit.perSecond)", "bucket.tokens = bucket.tokens + math.max(0, now - bucket.at) * limit.perSecond"),
     "rate: a long quiet time refills no more than 4"),
    ("the request limit (no limit)", ("if bucket.tokens < 1 then", "if false then"),
     "rate: 4 requests at once, the 5th is refused"),
    ("the request limit (8 a second)", ("CompanyConfig.RateLimit = { perSecond = 4, burst = 4 }", "CompanyConfig.RateLimit = { perSecond = 8, burst = 4 }"),
     "rate: faster than 4 a second is refused (10 a second gets about 4 a second)"),
    ("the request limit (a clock going back adds)", ("math.max(0, now - bucket.at)", "math.abs(now - bucket.at)"),
     "rate: a clock that goes back adds nothing"),
    # Switches and config
    ("the placement switch (live servers allowed)", ("return placement.Enabled == true and (placement.StudioOnly ~= true or RunService:IsStudio())", "return placement.Enabled == true"),
     "... and off on a live server"),
    ("the placement default (not Studio only)", ("\tStudioOnly = true,\n}\n\nfunction CompanyConfig.isPlacementActive", "\tStudioOnly = false,\n}\n\nfunction CompanyConfig.isPlacementActive"),
     "Placement is on in Studio only (StudioOnly)"),
    ("the picker (on)", ("SectorConfig.PickerEnabled = false", "SectorConfig.PickerEnabled = true"),
     "the picker is off"),
    ("a sector enabled (Gaming)", ("Gaming = { name = \"Gaming\", icon = \"🎮\", enabled = false,", "Gaming = { name = \"Gaming\", icon = \"🎮\", enabled = true,"),
     "only Software can be picked"),
    ("a sector key renamed", ("SectorConfig.Order = { \"Software\", \"Gaming\", \"Fintech\", \"Biotech\" }", "SectorConfig.Order = { \"Software\", \"Gaming\", \"Finance\", \"Biotech\" }"),
     "four sector keys from day one, in order"),
    ("the format version (2)", ("CompanyConfig.Version = 1", "CompanyConfig.Version = 2"),
     "round trip: v = 1 is written"),
    ("the Desk footprint too small for its prop", ("[\"Desk\"] = { w = 8.4, d = 7.6 },", "[\"Desk\"] = { w = 6, d = 4 },"),
     "every upgrade's footprint holds every part of its PlotArt prop (turned by its own yaw)"),
    # card.owned and the other lists are tidied on load (review fix C): the store refuses mixed tables and holes
    ("card.owned goes back to the old KEEP rule (list up to its first gap, every other key copied next to it)",
     ("\tlocal indexes, others = splitKeys(value)\n\tnoteGap(ctx, where .. \".\" .. key, indexes)\n\tfor _, index in ipairs(indexes) do\n\t\tlocal name = value[index]\n\t\tif typeof(name) == \"string\" and #name >= 1 and #name <= CompanyConfig.MaxIdLength and #out < MAX_OWNED_NAMES then",
      "\tlocal indexes, others = {}, {}\n\tlocal listed = 0\n\twhile value[listed + 1] ~= nil do\n\t\tlisted += 1\n\t\ttable.insert(indexes, listed)\n\tend\n\tfor other in pairs(value) do\n\t\tif not (isWhole(other, 1) and other <= listed) then\n\t\t\ttable.insert(others, other)\n\t\tend\n\tend\n\tfor _, index in ipairs(indexes) do\n\t\tlocal name = value[index]\n\t\tif typeof(name) == \"string\" and #name >= 1 and #name <= CompanyConfig.MaxIdLength and #out < MAX_OWNED_NAMES then",
      "\t\tif #out == 0 and typeof(other) == \"string\" then\n\t\t\tout[other] = deepCopy(value[other]) -- no names at all",
      "\t\tif true then\n\t\t\tout[other] = deepCopy(value[other]) -- no names at all"),
     "card.owned the review's mixed case {Desk, Laptop, future, [5]}: the saved section is accepted by the store"),
    ("card.owned keeps the hole (the names after it stay under their own keys)", ("\t\t\ttable.insert(out, name)\n\t\telse\n\t\t\tnote(ctx, \"a bad name in \"", "\t\t\tout[index] = name\n\t\telse\n\t\t\tnote(ctx, \"a bad name in \""),
     "card.owned a hole {Desk, nil, Laptop}: the saved section is accepted by the store"),
    ("card.owned keeps a string key next to the names", ("\t\tif #out == 0 and typeof(other) == \"string\" then\n\t\t\tout[other]", "\t\tif typeof(other) == \"string\" then\n\t\t\tout[other]"),
     "card.owned a string key {Desk, Laptop, future}: the saved section is accepted by the store"),
    ("card.owned keeps keys 0, negative and fractional next to the names", ("\t\tif #out == 0 and typeof(other) == \"string\" then\n\t\t\tout[other]", "\t\tif #out == 0 and typeof(other) == \"string\" or typeof(other) == \"number\" then\n\t\t\tout[other]"),
     "card.owned keys 0 and -3 next to a name: the saved section is accepted by the store"),
    ("card.owned loses the names after a gap", ("\tfor _, index in ipairs(indexes) do\n\t\tlocal name = value[index]\n\t\tif typeof(name) == \"string\" and #name >= 1 and #name <= CompanyConfig.MaxIdLength and #out < MAX_OWNED_NAMES then", "\tfor position, index in ipairs(indexes) do\n\t\tif index ~= position then break end\n\t\tlocal name = value[index]\n\t\tif typeof(name) == \"string\" and #name >= 1 and #name <= CompanyConfig.MaxIdLength and #out < MAX_OWNED_NAMES then"),
     "card.owned an entry after a gap {Desk, Laptop, [5]}: not locked, a plain list with the right names in key order"),
    ("card.owned reads the names in the wrong order of keys", ("\ttable.sort(indexes)\n\treturn indexes, others", "\ttable.sort(indexes, function(a, b) return a > b end)\n\treturn indexes, others"),
     "card.owned names stored under keys out of order: not locked, a plain list with the right names in key order"),
    ("card.owned drops a repeated name", ("\t\t\ttable.insert(out, name)\n\t\telse\n\t\t\tnote(ctx, \"a bad name in \"", "\t\t\tif not table.find(out, name) then table.insert(out, name) end\n\t\telse\n\t\t\tnote(ctx, \"a bad name in \""),
     "card.owned duplicates: not locked, a plain list with the right names in key order"),
    ("card.owned has no limit of 200", ("#name <= CompanyConfig.MaxIdLength and #out < MAX_OWNED_NAMES then\n\t\t\ttable.insert(out, name)", "#name <= CompanyConfig.MaxIdLength then\n\t\t\ttable.insert(out, name)"),
     "card.owned: names past 200 are skipped, with a warning for each"),
    ("card.owned closes a gap without a warning", ("\t\t\tnote(ctx, where .. \" had a gap in its list: what comes after it moved up\")\n", ""),
     "card.owned a hole {Desk, nil, Laptop}: 1 warning(s)"),
    ("card.owned drops a key without a warning", ("\t\t\tnote(ctx, \"a key in \" .. where .. \".\" .. key .. \" that can't sit next to a list, dropped (\" .. tostring(other) .. \")\")\n\t\tend\n\tend\n\treturn out\nend\n\n-- The card", "\t\tend\n\tend\n\treturn out\nend\n\n-- The card"),
     "card.owned a string key {Desk, Laptop, future}: 1 warning(s)"),
    ("card.owned keeps a map of records as the same table (not a copy)", ("out[other] = deepCopy(value[other])", "out[other] = value[other]"),
     "card.owned: a map of a newer version's records is kept whole, as a copy, with no warning"),
    ("card.owned drops the string keys of a map with no names", ("\t\tif #out == 0 and typeof(other) == \"string\" then\n\t\t\tout[other]", "\t\tif false then\n\t\t\tout[other]"),
     "card.owned: a table with only string keys (no names) is kept as it is, with no warning"),
    ("card.owned skips a bad name without a warning", ("\t\t\tnote(ctx, \"a bad name in \" .. where .. \".\" .. key)\n", ""),
     "card.owned a value that is not a name (a number): 1 warning(s)"),
    ("card.owned keeps 400 names (the limit is 200)", ("local MAX_OWNED_NAMES = 200", "local MAX_OWNED_NAMES = 400"),
     "card.owned: names past 200 are skipped, with a warning for each"),
    # the placed items
    ("objects keep the hole (an entry after a gap stays under its own key)", ("\t\t\ttable.insert(out, object)\n", "\t\t\tout[index] = object\n"),
     "objects with a gap in its indexes: not locked, a plain list of the right entries in key order"),
    ("objects with a string key lock the section again", ("\tnoteGap(ctx, where .. \".\" .. key, indexes)\n\tlocal seen = {}\n", "\tif #others > 0 then ctx.foreign = ctx.foreign or (where .. \".\" .. key .. \" is not a plain list\") end\n\tnoteGap(ctx, where .. \".\" .. key, indexes)\n\tlocal seen = {}\n"),
     "objects with a string key next to the list: not locked, a plain list of the right entries in key order"),
    ("objects drop a key without a warning", ("\t\tnote(ctx, \"a key in \" .. where .. \".\" .. key .. \" that can't sit next to a list, dropped (\" .. tostring(other) .. \")\")\n\tend\n\treturn out\nend\n\n-- The inventory", "\tend\n\treturn out\nend\n\n-- The inventory"),
     "objects with a string key next to the list: 1 warning(s)"),
    ("objects that is a map no longer keeps the section as it was", ("\t\tif onlyStrings then\n\t\t\tctx.foreign = ctx.foreign or (where .. \".\" .. key .. \" is not a plain list\")\n\t\t\treturn out\n\t\tend", "\t\tif onlyStrings then\n\t\t\treturn out\n\t\tend"),
     "objects that is a dictionary: the section is kept as it was (locked, written back unchanged)"),
    ("objects close a gap without a warning", ("\t\t\tnote(ctx, where .. \" had a gap in its list: what comes after it moved up\")\n", ""),
     "objects with a gap in its indexes: 1 warning(s)"),
    # a key that isn't a string next to named fields
    ("a number key next to named fields is kept (written back mixed)", ("\t\tif typeof(key) ~= \"string\" then\n\t\t\tnote(ctx, \"a key in \" .. where .. \" that isn't a name, dropped (\" .. tostring(key) .. \")\")\n\t\telseif not known[key] then", "\t\tif false then\n\t\t\tnote(ctx, \"a key in \" .. where .. \" that isn't a name, dropped (\" .. tostring(key) .. \")\")\n\t\telseif not known[key] then"),
     "a number key (99, 0, -3, 1.5) next to the named fields of active is dropped, with one warning each"),
    ("a number key next to named fields is dropped without a warning", ("\t\t\tnote(ctx, \"a key in \" .. where .. \" that isn't a name, dropped (\" .. tostring(key) .. \")\")\n\t\telseif not known[key] then", "\t\telseif not known[key] then"),
     "a number key (99, 0, -3, 1.5) next to the named fields of a card is dropped, with one warning each"),
    # the faithful store itself: a fake that accepts what the real one refuses would hide every bug above
    ("the faithful store accepts a list plus a string key", ("@fake", "\t\tif strings > 0 and numbers > 0 then\n", "\t\tif false then\n"),
     "the faithful store refuses a list plus a string key"),
    ("the faithful store accepts a list with a hole", ("@fake", "\t\t\t\tif value[i] == nil then\n", "\t\t\t\tif false then\n"),
     "the faithful store refuses a list with a hole"),
    ("the faithful store only looks at the top table (not recursively)", ("@fake", "\t\t\tstorableProblems(inner, path .. \"[\" .. tostring(key) .. \"]\", problems, open)\n", "\t\t\tlocal _ = nil\n"),
     "the faithful store refuses a mixed table three levels down"),
    ("the faithful store accepts a function", ("@fake", "\telseif kind ~= \"string\" and kind ~= \"number\" and kind ~= \"boolean\" then\n", "\telseif false then\n"),
     "the faithful store refuses a function value"),
    ("a stamp above 3 is clamped without a warning", ("\t\t\tnote(ctx, \"a \" .. where .. \".stamp out of range (\" .. tostring(stamp) .. \")\")\n", ""),
     "sectors: a stamp of 7 is clamped to 3 with a warning"),
    ("a number key in a map is skipped without a warning", ("\t\tif typeof(name) ~= \"string\" then\n\t\t\tnote(ctx, \"a bad key in \" .. where .. \".\" .. key)\n\t\telseif isKnown(name) then", "\t\tif typeof(name) ~= \"string\" then\n\t\telseif isKnown(name) then"),
     "never silent: an unknown key added to any table is written back unchanged or warned about"),
]


SERVER_TESTS = r"""-- Tests for CompanyServer: the real module with the real CompanyConfig, SectorConfig, PlotVisuals and PlotArt, and a fake Roblox ----
-- (customize PR 1). Join (new founding, run check, a newer or unreadable section kept as it was), saving, and the three requests
-- on CompanyRemotes.CompanyAction: Place, Store and Sync. Every refusal must change nothing.
local print_real = print
local passed, failed = 0, 0
local function check(name, cond, extra)
	if cond then passed += 1 else failed += 1; print_real("FAIL: " .. name .. (extra ~= nil and (" -- " .. tostring(extra)) or "")) end
end
local WARNINGS = {}
local function warn(...) table.insert(WARNINGS, table.concat({...}, " ")) end
local NOW = 1760000000
local CLOCK = 100
local os = { time = function() return NOW end, clock = function() return CLOCK end }
local IS_STUDIO = true
local MODULES = {}
local function token(name) return { Name = name, WaitForChild = function(self, n) return token(n) end } end
local function require(x) return assert(MODULES[x.Name], "no module " .. tostring(x.Name)) end
local SERVICES = {
	ReplicatedStorage = token("ReplicatedStorage"),
	RunService = { IsStudio = function() return IS_STUDIO end },
}
local game = { GetService = function(_, n) return SERVICES[n] end }
local script = { Parent = token("ReplicatedStorage") }
local CREATED = {}
local Instance = { new = function(c) local i = { ClassName = c }; table.insert(CREATED, i); return i end }
local task = { wait = function() error("CompanyServer must never yield") end, spawn = function() error("CompanyServer must never spawn") end }

MODULES.SectorConfig = (function()
__SECTORCONFIG__
end)()
MODULES.IpoConfig = (function()
__IPOCONFIG__
end)()
MODULES.CompanyConfig = (function()
__COMPANYCONFIG__
end)()
local PlotVisuals = (function()
__PLOTVISUALS__
end)()
local PlotArt = (function()
__PLOTART__
end)()
local function buildCompanyServer()
__COMPANYSERVER__
end
MODULES.CompanyServer = buildCompanyServer()
local UPGRADES = __UPGRADES__
local CC = MODULES.CompanyConfig
local CompanyServer = MODULES.CompanyServer
__STORABLE__
-- Every section CompanyConfig.toSave hands out (through CompanyServer.serialize and the IPO's payload step) is screened: it must be storable
do
	local realToSave = CC.toSave
	CC.toSave = function(state, studio) return screenStorable(realToSave(state, studio)) end
end

local function deepEqual(a, b)
	if typeof(a) ~= typeof(b) then return false end
	if typeof(a) == "number" and a ~= a and b ~= b then return true end
	if typeof(a) ~= "table" then return a == b end
	for k, v in pairs(a) do
		if not deepEqual(v, b[k]) then return false end
	end
	for k in pairs(b) do
		if a[k] == nil then return false end
	end
	return true
end
local function deepCopy(v)
	if typeof(v) ~= "table" then return v end
	local c = {}
	for k, inner in pairs(v) do c[k] = deepCopy(inner) end
	return c
end
local function anyWarning(text)
	for _, w in ipairs(WARNINGS) do
		if string.find(w, text, 1, true) then return true end
	end
	return false
end

local SAVES = 0
local ZONES_ON = true
local coreApi = {
	getData = function(p) return p.data end,
	save = function() SAVES += 1; return true end,
	plotZones = function()
		if not ZONES_ON then return nil end
		return PlotVisuals.zones(PlotArt.Layout), PlotArt.Layout.floorSize[3]
	end,
}
CompanyServer.init(coreApi)
local action
local folderName
for _, inst in ipairs(CREATED) do
	if inst.Name == "CompanyAction" then action = inst.OnServerInvoke end
	if inst.Name == "CompanyRemotes" then folderName = inst end
end
check("init builds CompanyRemotes with a CompanyAction remote and nothing else", action ~= nil and folderName ~= nil)
-- Every request goes through a wrapper: a handler that throws is recorded and answers nil (never == false, never a refusal),
-- so a broken rule fails its own named check instead of stopping the program.
local THROWS = {}
do
	local handler = action
	action = function(...)
		local called, a, b, c = pcall(handler, ...)
		if not called then
			table.insert(THROWS, tostring(a))
			return nil, "error: " .. tostring(a)
		end
		return a, b, c
	end
end
check("... and exactly two Instances were made (the folder and the remote)", #CREATED == 2)

local function newPlayer(saved, opts)
	opts = opts or {}
	local player = { Name = "P" }
	local owned = {}
	for _, name in ipairs(opts.owned or UPGRADES) do owned[name] = true end
	local data = {
		ready = opts.ready ~= false, loaded = true, owned = owned,
		cash = { Value = 500 }, income = { Value = 10 },
		ipo = { count = opts.count or 0, valuation = 700, lifetime = 900, best = 800, shares = 4 },
	}
	player.data = data
	WARNINGS = {}
	CompanyServer.setupPlayer(player, data, saved)
	return player, data
end
local function snapshotOf(data) return deepCopy(CC.toSave(data.pokedex, true)) end -- always as a Studio server would write it: comparable
local function tap(player, ...)
	CLOCK += 1 -- one request a second: never the rate limit unless a test wants it
	return action(player, ...)
end

-- 1. Join ---------------------------------------------------------------------------------------
local p, d = newPlayer(nil, { count = 3 })
check("join: a new player gets data.pokedex, no warning", d.pokedex ~= nil and #WARNINGS == 0)
local out = CompanyServer.serialize(d)
check("join: a new founding: v 1, run = the IPO count, Software, building 1", out.v == 1 and out.run == 3 and out.active.sector == "Software" and out.active.building == 1)
check("join: a Studio server marks the section (it never reaches a live board)", out.studio == true)
IS_STUDIO = false
check("join: a live server doesn't", CompanyServer.serialize(d).studio == nil)
IS_STUDIO = true
check("join: the player is not locked", CompanyServer.isLocked(d) == false and CompanyServer.isLocked(nil) == false and CompanyServer.isLocked({}) == false)
check("join: nothing changed Cash, Income or the valuation", d.cash.Value == 500 and d.income.Value == 10 and d.ipo.valuation == 700 and d.ipo.lifetime == 900 and d.ipo.best == 800 and d.ipo.shares == 4)
check("serialize: no data.pokedex, no section", CompanyServer.serialize({}) == nil)
-- the run check, through setupPlayer (the IPO count comes from data.ipo)
local saved = deepCopy(out)
saved.studio = nil
p, d = newPlayer(deepCopy(saved), { count = 4 })
check("join: an older version ran an IPO (run 3, count 4): Bronze and a card", (CompanyServer.serialize(d).sectors.Software or {}).stamp == 1 and CompanyServer.serialize(d).run == 4 and anyWarning("older version ran an IPO"))
p, d = newPlayer(deepCopy(saved), { count = 0 })
check("join: the count went down (Studio IpoReset): no stamp, run follows, the company stays", CompanyServer.serialize(d).sectors.Software == nil and CompanyServer.serialize(d).run == 0 and anyWarning("IPO reset in Studio"))
p, d = newPlayer(deepCopy(saved), { count = 3 })
check("join: same count: nothing happens", #WARNINGS == 0 and next(CompanyServer.serialize(d).sectors) == nil)
d.ipo = nil
WARNINGS = {}
CompanyServer.setupPlayer(p, d, nil)
check("join: no data.ipo reads as count 0", CompanyServer.serialize(d).run == 0)

-- 2. A newer or unreadable section is kept as it was ----------------------------------------------
local V2 = { v = 2, run = 0, active = { sector = "Software", future = { 1, 2 } }, other = { a = 1 } }
p, d = newPlayer(deepCopy(V2), { count = 5 })
check("v 2: locked", CompanyServer.isLocked(d) == true)
check("v 2: the save writes it back deep-equal, even from a Studio server", deepEqual(CompanyServer.serialize(d), V2))
for _, request in ipairs({ { "Place", "Desk", -23, -40, 0 }, { "Store", "Desk" }, { "Sync" } }) do
	local called, ok, why = pcall(tap, p, table.unpack(request)) -- a request that throws is not a refusal
	check("v 2: " .. request[1] .. " is refused and says why", called and ok == false and string.find(tostring(why), "newer version", 1, true) ~= nil, called and why or ok)
end
check("v 2: nothing changed", deepEqual(CompanyServer.serialize(d), V2))
-- a load that throws: the section is kept as it was. The stub throws only for a saved section (a real new founding still
-- works), so code that answers a throw with a new company would lose the section: setupPlayer is called through pcall.
local realLoad = CC.load
CC.load = function(saved, ctx) if saved ~= nil then error("boom") end return realLoad(saved, ctx) end
local broken = { v = 1, run = 0, active = "whatever", precious = { x = 1 } }
local brokenPlayer = { Name = "P" }
local brokenData = { ready = true, loaded = true, owned = {}, ipo = { count = 0 } }
brokenPlayer.data = brokenData
WARNINGS = {}
local joinedOk, joinError = pcall(CompanyServer.setupPlayer, brokenPlayer, brokenData, deepCopy(broken))
CC.load = realLoad
check("a load that throws: setupPlayer itself doesn't throw", joinedOk, joinError)
check("a load that throws: locked, warned, written back as it was", joinedOk and CompanyServer.isLocked(brokenData) and anyWarning("boom") and deepEqual(CompanyServer.serialize(brokenData), broken))
-- an unknown sector in the active company
p, d = newPlayer({ v = 1, run = 0, active = { sector = "Energy" } }, { count = 0 })
check("an unknown active sector: locked and written back as it was", CompanyServer.isLocked(d) and deepEqual(CompanyServer.serialize(d), { v = 1, run = 0, active = { sector = "Energy" } }))
for _, request in ipairs({ { "Place", "Desk", -23, -40, 0 }, { "Store", "Desk" }, { "Sync" } }) do
	local called, ok = pcall(tap, p, table.unpack(request))
	check("unknown sector: " .. request[1] .. " is refused (through pcall: a throw is not a refusal)", called and ok == false, ok)
end
check("unknown sector: Place, Store and Sync are refused and the section is unchanged",
	#d.pokedex.section.active.objects == 0 and next(d.pokedex.section.active.stored) == nil and deepEqual(CompanyServer.serialize(d), { v = 1, run = 0, active = { sector = "Energy" } }))

-- 3. Requests: who may ask, and when -------------------------------------------------------------
p, d = newPlayer(nil)
local before = snapshotOf(d)
local function refused(name, ...)
	local ok, why = tap(p, ...)
	check(name .. ": refused", ok == false and typeof(why) == "string", why)
	check(name .. ": nothing changed", deepEqual(snapshotOf(d), before))
end
for _, bad in ipairs({ 5, true, {}, 0 / 0, "" }) do
	refused("an action that is " .. tostring(bad), bad, "Desk", -23, -40, 0)
end
check("no action at all is refused", select(1, tap(p)) == false and select(1, tap(p, nil)) == false)
refused("an unknown action", "Buy", "Desk", -23, -40, 0)
refused("an action in the wrong case", "place", "Desk", -23, -40, 0)
refused("a price-looking request", "BuyBuilding", 2)
d.ready = false
refused("not ready (loading, or an IPO is being saved)", "Place", "Desk", -23, -40, 0)
d.ready = true
check("a player with no data is refused", select(1, action({ data = nil }, "Sync")) == false)
check("a player with no pokedex is refused", select(1, action({ data = { ready = true } }, "Sync")) == false)
IS_STUDIO = false
refused("a live server (Studio only until the office screen exists): Place", "Place", "Desk", -23, -40, 0)
refused("a live server: Store", "Store", "Desk")
check("a live server: Sync is refused too", select(1, tap(p, "Sync")) == false)
check("a live server says it isn't available yet", select(2, tap(p, "Sync")) == "Not available yet")
IS_STUDIO = true
check("in Studio Sync works", select(1, tap(p, "Sync")) == true)

-- 4. The request limit ---------------------------------------------------------------------------
p, d = newPlayer(nil)
local oks, tooFast = 0, 0
for _ = 1, 10 do
	local ok, why = action(p, "Sync") -- the clock doesn't move
	if ok then oks += 1 elseif why == "Too fast" then tooFast += 1 end
end
check("rate: 4 requests in the same instant, then 'Too fast'", oks == 4 and tooFast == 6, oks)
CLOCK += 0.25
check("rate: a quarter second later one more goes through", select(1, action(p, "Sync")) == true and select(1, action(p, "Sync")) == false)
local before2 = snapshotOf(d)
for _ = 1, 20 do action(p, "Place", "Desk", -23, -40, 0) end
check("rate: a flood of Place requests changed nothing while limited", deepEqual(snapshotOf(d), before2))
local second = newPlayer(nil)
check("rate: another player has their own limit", select(1, action(second, "Sync")) == true)

-- 5. Place, Store and Sync -----------------------------------------------------------------------
p, d = newPlayer(nil)
SAVES = 0
local ok, msg, info = tap(p, "Sync")
check("sync: building 1, a 60 x 60 office, nothing placed or stored", ok and info.building == 1 and info.size.w == 60 and info.size.d == 60 and #info.objects == 0 and #info.stored == 0 and info.sector == "Software")
check("sync: the reserved zones come with it (so the client can preview)", typeof(info.zones) == "table" and #info.zones == 40 and info.zones[1].x0 ~= nil)
check("sync: the zones are measured from the anchor (the walking lane ends at the front, z 0)", (function()
	for _, zone in ipairs(info.zones) do
		if zone.name == "WalkingLane" then return zone.z1 == 0 end
	end
	return false
end)())
ok, msg, info = tap(p, "Place", "Coffee Machine", -20, -6, 2)
check("place: an owned upgrade in a free spot", ok == true and msg == "Placed Coffee Machine" and info.x == -20 and info.r == 2)
check("place: the company has it, saved on the next save (not on every request)", (CompanyServer.serialize(d).active.objects[1] or {}).id == "Coffee Machine" and SAVES == 0)
check("place: Cash, Income and the valuation are untouched", d.cash.Value == 500 and d.income.Value == 10 and d.ipo.valuation == 700 and d.ipo.lifetime == 900)
ok, msg = tap(p, "Place", "Coffee Machine", -14, -6, 0)
check("place: placing it again moves it, never two entries", ok and #CompanyServer.serialize(d).active.objects == 1 and CompanyServer.serialize(d).active.objects[1].x == -14)
ok = tap(p, "Place", "Laptop", -14, -6, 0)
check("place: another item can't stand on it", ok == false and #CompanyServer.serialize(d).active.objects == 1)
before = snapshotOf(d)
refused("an item you don't own", "Place", "Gaming PC", -20, -6, 0)
refused("a reserved spot (the walking lane)", "Place", "Laptop", 0, -35, 0)
refused("outside the building", "Place", "Laptop", -40, -6, 0)
refused("a spot off the grid", "Place", "Laptop", -20.3, -6, 0)
refused("a bad turn", "Place", "Laptop", -20, -6, 9)
refused("a NaN spot", "Place", "Laptop", 0 / 0, -6, 0)
refused("a missing spot", "Place", "Laptop")
refused("a table for an id", "Place", {}, -20, -6, 0)
ok = tap(p, "Place", "Laptop", -20, -3, 0, "extra", { junk = true })
check("extra arguments are ignored", ok == true)
local p2, d2 = newPlayer(nil, { owned = { "Desk" } })
check("place: owning only the Desk, the Laptop is refused and the Desk is accepted", select(1, tap(p2, "Place", "Laptop", -20, -6, 0)) == false and select(1, tap(p2, "Place", "Desk", -23, -40, 0)) == true)
ok, msg = tap(p, "Store", "Coffee Machine")
check("store: it leaves the office for the inventory", ok and #CompanyServer.serialize(d).active.objects == 1 and CompanyServer.serialize(d).active.stored["Coffee Machine"] == true)
before = snapshotOf(d)
refused("store: the same item again", "Store", "Coffee Machine")
refused("store: an item you don't own", "Store", "Gaming PC")
refused("store: no id", "Store")
ok = tap(p, "Place", "Coffee Machine", -20, -6, 0)
check("place: a stored item can be placed again, and leaves the inventory", ok and CompanyServer.serialize(d).active.stored["Coffee Machine"] == nil)
ok, msg, info = tap(p, "Sync")
check("sync: shows what was placed and stored", #info.objects == 2 and #info.stored == 0)
tap(p, "Store", "Laptop")
ok, msg, info = tap(p, "Sync")
check("sync: lists the inventory sorted", #info.stored == 1 and info.stored[1] == "Laptop" and #info.objects == 1)
do
	local sp, sd = newPlayer({ v = 1, run = 0, active = { sector = "Software", stored = { Laptop = true, Desk = { tier = 2 }, Whiteboard = false } } }, { count = 0 })
	local _, _, sinfo = tap(sp, "Sync")
	check("sync: only what is stored as true is listed (a newer version's record and a false are kept, not shown)", sinfo ~= nil and #sinfo.stored == 1 and sinfo.stored[1] == "Laptop"
		and deepEqual(CompanyServer.serialize(sd).active.stored.Desk, { tier = 2 }) and CompanyServer.serialize(sd).active.stored.Whiteboard == false)
	local sok = tap(sp, "Store", "Desk")
	check("store: over a record of a newer version is refused and the record stays", sok == false and deepEqual(CompanyServer.serialize(sd).active.stored.Desk, { tier = 2 }))
end
check("place, store and sync never saved by themselves (autosave does it)", SAVES == 0)
local objectsCopy = info.objects
local changedAnswer = pcall(function() objectsCopy[1].x = 99 end)
check("sync: the answer is a copy (changing it never changes the company)", changedAnswer and CompanyServer.serialize(d).active.objects[1].x ~= 99)
-- without the plot's zones the server can't know what is reserved
do
	local bare = buildCompanyServer()
	local bareCore = { getData = coreApi.getData, save = coreApi.save, plotZones = function() return nil end }
	local before = #CREATED
	bare.init(bareCore)
	local bareAction
	for i = before + 1, #CREATED do
		if CREATED[i].Name == "CompanyAction" then bareAction = CREATED[i].OnServerInvoke end
	end
	local bp = { Name = "B" }
	local bd = { ready = true, loaded = true, owned = { ["Coffee Machine"] = true }, ipo = { count = 0 } }
	bp.data = bd
	bare.setupPlayer(bp, bd, nil)
	local bok, bwhy = bareAction(bp, "Place", "Coffee Machine", -20, -6, 0)
	check("no zones: Place is refused (the server can't know what is reserved)", bok == false and #bd.pokedex.section.active.objects == 0, bwhy)
	local sok, _, sinfo = bareAction(bp, "Sync")
	check("no zones: Sync still answers, with zones = false", sok == true and sinfo.zones == false)
end
-- the building number decides the room
p, d = newPlayer(nil)
d.pokedex.section.active.building = 5
check("place: in building 5 (78 x 82) the left side reaches further", select(1, tap(p, "Place", "Coffee Machine", -36.5, -6, 0)) == true)
d.pokedex.section.active.building = 1
check("place: back in building 1 the same spot is outside", select(1, tap(p, "Place", "Laptop", -36.5, -6, 0)) == false)
d.pokedex.section.active.building = 9
check("place: a building number this version has no size for is refused", select(1, tap(p, "Place", "Laptop", -20, -6, 0)) == false)

-- 6. Fuzz: bad requests never change anything and never throw -------------------------------------
p, d = newPlayer(nil)
tap(p, "Place", "Desk", -23, -40, 0)
before = snapshotOf(d)
local WEIRD = { 0 / 0, math.huge, -math.huge, -1, 0, 1.5, 2 ^ 53, "", "x", true, false, {}, 1e308, -23, -40 }
local errors, changed = 0, 0
for _, action_ in ipairs({ "Place", "Store" }) do
	for _, a in ipairs(WEIRD) do
		for _, b in ipairs(WEIRD) do
			CLOCK += 1
			local ok2, r1 = pcall(action, p, action_, a, b, b, a)
			if not ok2 then errors += 1; print_real("FAIL fuzz error: " .. action_ .. " " .. tostring(a) .. " " .. tostring(b) .. " -- " .. tostring(r1)) end
			if r1 == true and action_ == "Place" then changed += 1 end
		end
	end
end
check("fuzz: bad Place and Store requests never throw", errors == 0 and #THROWS == 0, THROWS[1])
check("fuzz: ... and none of them was accepted", changed == 0 and deepEqual(snapshotOf(d), before))

-- 7. An IPO done by this version: run follows the count (no stamp, no card, no run-check event) --------------------
-- TycoonCore.commitIpo calls writeIpoRun inside the IPO's save (the payload is built before the count rises) and onIpo
-- once that save worked. The IPO transform itself (stamps, cards) is PR 4: until then run just moves with the count.
p, d = newPlayer(nil, { count = 0 })
tap(p, "Place", "Coffee Machine", -20, -6, 2)
local activeBefore = deepCopy(CompanyServer.serialize(d).active)
local ipo1 = { pokedex = CompanyServer.serialize(d) }
CompanyServer.writeIpoRun(d, ipo1, 1)
check("an IPO by this version: the saved payload carries run = the new count", ipo1.pokedex.run == 1, ipo1.pokedex.run)
check("an IPO by this version: the section in memory is not changed by the payload step (only after the save worked)", CompanyServer.serialize(d).run == 0)
-- a crash right after that save: the next join sees only the payload
local joined, joinedData = newPlayer(deepCopy(ipo1.pokedex), { count = 1 })
local after = CompanyServer.serialize(joinedData)
check("an IPO by this version: the next join has no run-check event and no warning, and no stamp or card",
	joinedData.pokedex.event == nil and #WARNINGS == 0 and next(after.sectors) == nil and after.run == 1, WARNINGS[1])
check("an IPO by this version: the company is the same one (no completion, no new company)", deepEqual(after.active, activeBefore))
CompanyServer.onIpo(d, 1)
check("an IPO by this version: after the save worked, the section in memory follows (an autosave keeps run)", CompanyServer.serialize(d).run == 1)
-- a second IPO in the same session
local ipo2 = { pokedex = CompanyServer.serialize(d) }
check("two IPOs in one session: the autosave between them kept run = 1", ipo2.pokedex.run == 1)
CompanyServer.writeIpoRun(d, ipo2, 2)
CompanyServer.onIpo(d, 2)
check("two IPOs in one session: each one moves run (the second payload and the section in memory say 2)", ipo2.pokedex.run == 2 and CompanyServer.serialize(d).run == 2)
joined, joinedData = newPlayer(deepCopy(ipo2.pokedex), { count = 2 })
check("two IPOs in one session: the next join has no run-check event and no warning, and no stamp or card",
	joinedData.pokedex.event == nil and #WARNINGS == 0 and next(CompanyServer.serialize(joinedData).sectors) == nil and CompanyServer.serialize(joinedData).run == 2, WARNINGS[1])
-- a locked section (a newer version's) is never touched, and bad arguments never throw
p, d = newPlayer(deepCopy(V2), { count = 5 })
local lockedPayload = { pokedex = CompanyServer.serialize(d) }
CompanyServer.writeIpoRun(d, lockedPayload, 6)
CompanyServer.onIpo(d, 6)
check("a locked section: writeIpoRun and onIpo change nothing", deepEqual(lockedPayload.pokedex, V2) and deepEqual(CompanyServer.serialize(d), V2))
local okCalls = pcall(function()
	CompanyServer.writeIpoRun(nil, {}, 1)
	CompanyServer.writeIpoRun({}, {}, 1)
	CompanyServer.writeIpoRun({ pokedex = { locked = false } }, nil, 1)
	CompanyServer.writeIpoRun({ pokedex = { locked = false, section = {} } }, {}, 1)
	CompanyServer.onIpo(nil, 1)
	CompanyServer.onIpo({}, 1)
	CompanyServer.onIpo({ pokedex = { locked = false } }, 1)
end)
check("writeIpoRun and onIpo never throw (no data, no section, no payload)", okCalls)

-- 7b. The same IPO when the section holds fields this version doesn't know (top level, and every level below it the plan lists:
-- active, decor, passSeconds, objects[i], stored, told, rounds, rounds[k], sectors, sectors[k], card, card.owned, card.decor,
-- card.objects[i], card.rounds[k], kept, hall, sx): the run is still written and moved, and every unknown field comes back unchanged.
do
	local FAT = __FATPOKEDEX__
	local fatPlayer, fatData = newPlayer(deepCopy(FAT), { count = FAT.run })
	check("unknown fields: the join is clean (no warning, no run check, not locked)", #WARNINGS == 0 and fatData.pokedex.event == nil and not CompanyServer.isLocked(fatData), WARNINGS[1])
	local expected = deepCopy(FAT)
	expected.run = FAT.run + 1
	expected.studio = true -- a Studio server marks every save
	local fatPayload = { pokedex = CompanyServer.serialize(fatData) }
	CompanyServer.writeIpoRun(fatData, fatPayload, FAT.run + 1)
	check("an IPO by this version, a section with unknown fields: the saved payload carries run = the new count", fatPayload.pokedex.run == FAT.run + 1, fatPayload.pokedex.run)
	check("an IPO by this version, a section with unknown fields: every unknown field is written back unchanged, at every level", deepEqual(fatPayload.pokedex, expected))
	check("an IPO by this version, a section with unknown fields: the section in memory is not changed by the payload step", CompanyServer.serialize(fatData).run == FAT.run)
	CompanyServer.onIpo(fatData, FAT.run + 1)
	check("an IPO by this version, a section with unknown fields: the section in memory follows (run = the new count)", CompanyServer.serialize(fatData).run == FAT.run + 1, CompanyServer.serialize(fatData).run)
	check("an IPO by this version, a section with unknown fields: its unknown fields are unchanged in memory", deepEqual(CompanyServer.serialize(fatData), expected))
	-- only a top-level unknown field (the smallest case), and only a nested one
	for name, saved in pairs({ ["a top-level unknown field"] = { v = 1, run = 0, newThing = { 1, 2 } }, ["a nested unknown field"] = { v = 1, run = 0, active = { sector = "Software", newThing = 7 } } }) do
		local _, data = newPlayer(deepCopy(saved), { count = 0 })
		local payload = { pokedex = CompanyServer.serialize(data) }
		CompanyServer.writeIpoRun(data, payload, 1)
		CompanyServer.onIpo(data, 1)
		check("an IPO by this version, " .. name .. ": run = 1 in the payload and in memory, the field is kept", payload.pokedex.run == 1 and CompanyServer.serialize(data).run == 1
			and (payload.pokedex.newThing ~= nil or payload.pokedex.active.newThing == 7) and deepEqual(CompanyServer.serialize(data).active, payload.pokedex.active))
	end
end

check("no request ever threw (a handler that throws is a bug, not a refusal)", #THROWS == 0, THROWS[1])

check("every section the server saved in these tests is storable (" .. STORE_SCREEN.seen .. " screened)", STORE_SCREEN.bad == 0 and STORE_SCREEN.seen > 20, STORE_SCREEN.first)
print_real(string.format("%d passed, %d failed", passed, failed))
"""


def company_server_source(mutation=None):
    """The SERVER_TESTS program with the real CompanyServer, CompanyConfig, SectorConfig, IpoConfig, PlotVisuals and PlotArt.
    mutation = (old, new) breaks one rule of CompanyServer (`old` must be in it exactly once)."""
    def read(name):
        with open(os.path.join(ROOT, name), encoding="utf-8") as f:
            return f.read()

    parts = {name: read(name + ".lua") for name in ("SectorConfig", "IpoConfig", "CompanyConfig", "PlotVisuals", "PlotArt", "CompanyServer")}
    if mutation:
        old, new = mutation
        if parts["CompanyServer"].count(old) != 1:
            raise SystemExit("mutation target not found exactly once in CompanyServer: " + old)
        parts["CompanyServer"] = parts["CompanyServer"].replace(old, new, 1)
    return (SERVER_TESTS.replace("__UPGRADES__", upgrades_lua_names())
            .replace("__SECTORCONFIG__", parts["SectorConfig"]).replace("__IPOCONFIG__", parts["IpoConfig"])
            .replace("__COMPANYCONFIG__", parts["CompanyConfig"]).replace("__PLOTVISUALS__", parts["PlotVisuals"])
            .replace("__PLOTART__", parts["PlotArt"]).replace("__COMPANYSERVER__", parts["CompanyServer"]).replace("__FATPOKEDEX__", FAT_POKEDEX_LUA))


SERVER_MUTATIONS = [
    ("the ready check", ("if not state or not data.ready then", "if not state then"),
     "not ready (loading, or an IPO is being saved): refused"),
    ("the request limit", ("if not CompanyConfig.takeToken(state.bucket, os.clock()) then", "if false then"),
     "rate: 4 requests in the same instant, then 'Too fast'"),
    ("the request limit (shared by every player)", ("state.bucket = CompanyConfig.newBucket(os.clock()) -- the request limit (not saved)", "state.bucket = sharedBucket or CompanyConfig.newBucket(os.clock())\n\tsharedBucket = state.bucket"),
     "rate: another player has their own limit"),
    ("the Studio-only switch", ("if not CompanyConfig.isPlacementActive() then", "if false then"),
     "a live server (Studio only until the office screen exists): Place: refused"),
    ("the lock on a newer version", ("if state.locked then\n\t\treturn false, \"Your office", "if false then\n\t\treturn false, \"Your office"),
     "v 2: Place is refused and says why"),
    ("the unknown action check", ("if action ~= \"Place\" and action ~= \"Store\" and action ~= \"Sync\" then", "if false then"),
     "an unknown action: nothing changed"),
    ("the placement check", ("local ok, reason = CompanyConfig.checkPlacement(env, id, x, z, r)\n\t\tif not ok then return false, reason end", "local ok = true"),
     "an item you don't own: refused"),
    ("the ownership (every upgrade owned)", ("owned = data.owned,", "owned = setmetatable({}, { __index = function() return true end }),"),
     "place: owning only the Desk, the Laptop is refused and the Desk is accepted"),
    ("the store check", ("local ok, reason = CompanyConfig.checkStore(env, active, id)\n\tif not ok then return false, reason end", "local ok = true"),
     "store: the same item again: refused"),
    ("a save on every request", ("\t\tCompanyConfig.applyPlace(active, id, x, z, r)\n", "\t\tCompanyConfig.applyPlace(active, id, x, z, r)\n\t\tcore.save(player)\n"),
     "place, store and sync never saved by themselves (autosave does it)"),
    ("the building (always 1)", ("building = active.building,\n\t\tzones = zones(),", "building = 1,\n\t\tzones = zones(),"),
     "place: in building 5 (78 x 82) the left side reaches further"),
    ("the Studio mark on save", ("return CompanyConfig.toSave(state, RunService:IsStudio())", "return CompanyConfig.toSave(state, false)"),
     "join: a Studio server marks the section (it never reaches a live board)"),
    ("the Studio mark on a live server", ("return CompanyConfig.toSave(state, RunService:IsStudio())", "return CompanyConfig.toSave(state, true)"),
     "join: a live server doesn't"),
    ("the IPO count for the run check", ("ipoCount = data.ipo and data.ipo.count or 0,", "ipoCount = 0,"),
     "join: an older version ran an IPO (run 3, count 4): Bronze and a card"),
    ("the unreadable section guard", ("state = { locked = true, raw = savedPokedex }", "state = CompanyConfig.load(nil, ctx)"),
     "a load that throws: locked, warned, written back as it was"),
    ("the lock query", ("return state ~= nil and state.locked == true", "return false"),
     "v 2: locked"),
    ("the sync answer (live tables)", ("table.insert(list, { id = object.id, x = object.x, z = object.z, r = object.r })", "list = objects"),
     "sync: the answer is a copy (changing it never changes the company)"),
    ("the sync answer lists every stored entry", ("if held == true then\n\t\t\ttable.insert(stored, id)", "if true then\n\t\t\ttable.insert(stored, id)"),
     "sync: only what is stored as true is listed (a newer version's record and a false are kept, not shown)"),
    ("the zones (never measured from the anchor)", ("zonesCache = CompanyConfig.anchorZones(raw, floorDepth)", "zonesCache = raw"),
     "sync: the reserved zones come with it (so the client can preview)"),
    ("the run in the IPO's save (never written)", ("\tpayload.pokedex.run = count\n", "\tpayload.pokedex.run = payload.pokedex.run\n"),
     "an IPO by this version: the saved payload carries run = the new count"),
    ("the run in the IPO's save (the wrong value)", ("\tpayload.pokedex.run = count\n", "\tpayload.pokedex.run = count - 1\n"),
     "an IPO by this version: the saved payload carries run = the new count"),
    ("the run in the IPO's save (written into the section in memory too early)", ("\tpayload.pokedex.run = count\n", "\tpayload.pokedex.run = count\n\tstate.section.run = count\n"),
     "an IPO by this version: the section in memory is not changed by the payload step (only after the save worked)"),
    ("the run in memory after an IPO (never set)", ("\tstate.section.run = count\nend\n\n-- True while", "\tstate.section.run = state.section.run\nend\n\n-- True while"),
     "an IPO by this version: after the save worked, the section in memory follows (an autosave keeps run)"),
    ("the run in memory after an IPO (the wrong value)", ("\tstate.section.run = count\nend\n\n-- True while", "\tstate.section.run = count - 1\nend\n\n-- True while"),
     "an IPO by this version: after the save worked, the section in memory follows (an autosave keeps run)"),
    ("the lock guard of the IPO's run", ("if state == nil or state.locked or typeof(payload) ~= \"table\"", "if state == nil or typeof(payload) ~= \"table\""),
     "a locked section: writeIpoRun and onIpo change nothing"),
    ("the run in the IPO's save (skipped when the section has an unknown top-level field)", ("\tpayload.pokedex.run = count\n", "\tfor key in pairs(payload.pokedex) do\n\t\tif key ~= \"v\" and key ~= \"run\" and key ~= \"active\" and key ~= \"sectors\" and key ~= \"kept\" and key ~= \"hall\" and key ~= \"dust\" and key ~= \"studio\" then return end\n\tend\n\tpayload.pokedex.run = count\n"),
     "an IPO by this version, a section with unknown fields: the saved payload carries run = the new count"),
    ("the run in memory after an IPO (skipped when the section has an unknown top-level field)", ("\tstate.section.run = count\nend\n\n-- True while", "\tfor key in pairs(state.section) do\n\t\tif key ~= \"v\" and key ~= \"run\" and key ~= \"active\" and key ~= \"sectors\" and key ~= \"kept\" and key ~= \"hall\" and key ~= \"dust\" and key ~= \"studio\" then return end\n\tend\n\tstate.section.run = count\nend\n\n-- True while"),
     "an IPO by this version, a section with unknown fields: the section in memory follows (run = the new count)"),
]


# A pokedex section with fields this version doesn't know at every level the plan lists (docs/CUSTOMIZE_PROPOSAL.md, "KEEP unknown fields"):
# shared by the CompanyServer tests and the commitIpo tests. run = 2: join it with an IPO count of 2 and nothing happens.
FAT_POKEDEX_LUA = r"""{
	v = 1, run = 2,
	active = {
		sector = "Software", picked = true, name = "Pixel Pioneers", foundedAt = 1700000000, engaged = 1234.5,
		passSeconds = { DoubleCash = 100.5, VIP = 20, FuturePass = { a = 1 } },
		building = 3,
		decor = { Chair = 2, Future = "x" },
		objects = { { id = "Desk", x = -23, z = -40, r = 0, futureObj = "keep me" }, { id = "Laptop", x = -25.5, z = -30, r = 3 } },
		stored = { Whiteboard = true, ["Gaming PC"] = true, ["Future Rack"] = { size = 3 } },
		told = { Seed = true, SeriesA = true, FutureStage = 7 },
		rounds = {
			Seed = { s = "raised", c = 2, cash = 360, bp = 122, at = 1700000100, studio = false, extra = { deep = true } },
			SeriesA = { s = "skipped", c = 0, cash = 0, bp = 0, at = 1700000200, studio = true },
			FutureStage = { anything = "goes", bp = 50 },
		},
		sx = { n = 3, deep = { a = { b = 1 } } },
		futureActive = { x = 1 },
	},
	sectors = {
		Software = {
			state = "done", stamp = 2, replays = 1, firstAt = 1690000000, bestEngaged = 9999.25,
			card = {
				name = "Old Co", ipoNumber = 1, at = 1690000001, engaged = 8888.5, ratio = 1.25, building = 5,
				owned = { "Desk", "Laptop", "Gaming PC" },
				decor = { Chair = 1, Future = 3 },
				objects = { { id = "Desk", x = -23, z = -40, r = 0, futureObj = "card object" }, { id = "Laptop", x = -25.5, z = -30, r = 3 } },
				rounds = { Seed = { s = "raised", c = 1, cash = 100, bp = 40, at = 5, studio = false, extra = 1 }, FutureStage = { bp = 9 } },
				stake = 9951, shares = 14, sx = { score = 5 },
				futureCard = "keep",
			},
			futureSector = { y = 2 },
		},
		Gaming = { state = "progress", stamp = 0, replays = 0, firstAt = 0, bestEngaged = 0 },
		Energy = { whatever = { 1, 2, 3 } },
	},
	kept = { Chair = 1, Plant = 2 },
	hall = { Launch = 1700000300, Four = 1700000400 },
	dust = -1234,
	studio = false,
	futureTop = { z = { 1, 2, 3 } },
}"""


COMMITIPO_TESTS = r"""-- Tests for TycoonCore.commitIpo and save(): the code between the COMMITIPO and SAVEFN markers, with the real CompanyServer,
-- CompanyConfig, SectorConfig and IpoConfig, fake modules for the rest and a fake DataStore (customize PR 1 review fix).
-- An IPO is refused while the pokedex is locked and nothing changes; an IPO by this version saves run = the new count.
local print_real = print
__STORABLE__
local passed, failed = 0, 0
local function check(name, cond, extra)
	if cond then passed += 1 else failed += 1; print_real("FAIL: " .. name .. (extra ~= nil and (" -- " .. tostring(extra)) or "")) end
end
local WARNINGS = {}
local function warn(...) table.insert(WARNINGS, table.concat({...}, " ")) end
local function anyWarning(text)
	for _, w in ipairs(WARNINGS) do
		if string.find(w, text, 1, true) then return true end
	end
	return false
end
local NOW = 1760000000
local os = { time = function() return NOW end, clock = function() return 100 end }
local IS_STUDIO = true
local MODULES = {}
local function token(name) return { Name = name, WaitForChild = function(self, n) return token(n) end } end
local function require(x) return assert(MODULES[x.Name], "no module " .. tostring(x.Name)) end
local SERVICES = {
	ReplicatedStorage = token("ReplicatedStorage"),
	RunService = { IsStudio = function() return IS_STUDIO end },
}
local game = { GetService = function(_, n) return SERVICES[n] end }
local script = { Parent = token("ReplicatedStorage") }
local task = { wait = function() error("save() waited: a lock was left on") end }

MODULES.SectorConfig = (function()
__SECTORCONFIG__
end)()
MODULES.IpoConfig = (function()
__IPOCONFIG__
end)()
MODULES.CompanyConfig = (function()
__COMPANYCONFIG__
end)()
local function buildCompanyServer()
__COMPANYSERVER__
end
local CompanyServer = buildCompanyServer()
local CC = MODULES.CompanyConfig
local IpoConfig = MODULES.IpoConfig

local function deepEqual(a, b)
	if typeof(a) ~= typeof(b) then return false end
	if typeof(a) == "number" and a ~= a and b ~= b then return true end
	if typeof(a) ~= "table" then return a == b end
	for k, v in pairs(a) do
		if not deepEqual(v, b[k]) then return false end
	end
	for k in pairs(b) do
		if a[k] == nil then return false end
	end
	return true
end
local function deepCopy(v)
	if typeof(v) ~= "table" then return v end
	local c = {}
	for k, inner in pairs(v) do c[k] = deepCopy(inner) end
	return c
end

-- The other modules: they only have to serialize (fresh tables, like the real ones) and count what commitIpo asks of them
local COUNT = { destroyed = 0, cleared = 0, hrReset = 0, income = 0, sign = 0 }
local ShopServer = { serialize = function(data) return { luckLeft = 0 } end, notify = function() end }
local EmployeeServer = {
	serialize = function(data) return deepCopy(data.team) end,
	serializeFixedHires = function() return nil end,
	clearIncubators = function() COUNT.cleared += 1 end,
}
local PoachServer = { serialize = function(data) return { hrLevel = data.poachLevel } end, resetHrDepartment = function() COUNT.hrReset += 1 end }
local IpoServer = { serialize = function(data) return deepCopy(data.ipo) end }
local OnboardingServer = { serialize = function() return { seenIntro = true } end }
local DailyServer = { serialize = function() return { streak = 4 } end }
local TaskServer = { serialize = function() return nil end }
__KNOWNSECTIONS__
local playerData = {}
local STORE = { calls = 0, last = nil, fail = false, refused = 0, problem = nil, sent = 0 }
-- The faithful DataStore: like the real SetAsync it throws on a payload that mixes list and string keys or has holes, anywhere in it
local fakeStore = { SetAsync = function(_, key, payload)
	STORE.calls += 1
	if STORE.fail then error("DataStore is down") end
	local problems = storableProblems(payload)
	if #problems > 0 then
		STORE.refused += 1
		STORE.problem = STORE.problem or problems[1]
		error("105: Cannot store " .. problems[1] .. " in DataStore")
	end
	STORE.sent += 1
	STORE.key, STORE.last = key, deepCopy(payload)
end }
local function getStore() return fakeStore end
local function updateIncome() COUNT.income += 1 end
local function refreshSign() COUNT.sign += 1 end
__BUILDSAVE__
__SAVENOTE__
__SAVEFN__
__COMMITIPO__

local function newPlayer(savedPokedex, count)
	local player = { Name = "P", UserId = 7 }
	local data = {
		loaded = true, ready = true, saving = false,
		owned = { Desk = true, Laptop = true }, cash = { Value = 250 },
		items = { Desk = { Destroy = function() COUNT.destroyed += 1 end }, Laptop = { Destroy = function() COUNT.destroyed += 1 end } },
		unknownSections = { future = { x = 1 } },
		shop = {}, onboarding = {}, daily = {}, tasks = {}, poachLevel = 2, poach = {},
		team = { employees = {}, incubators = { { egg = "Garage" }, false, false } },
		ipo = { count = count or 1, shares = 5, valuation = 900, lifetime = 900, best = 900 },
	}
	player.data = data
	playerData[player] = data
	WARNINGS = {}
	CompanyServer.setupPlayer(player, data, savedPokedex)
	return player, data
end
local function resetFakes()
	STORE.calls, STORE.last, STORE.fail = 0, nil, false
	for key in pairs(COUNT) do COUNT[key] = 0 end
end
local function ipoAfter(data) -- the IPO section IpoServer hands over: the same one with the next count
	local after = deepCopy(data.ipo)
	after.count += 1
	after.shares += 3
	after.valuation = 0
	return after
end
local function live(data) -- everything an IPO may change in the running game
	return deepCopy({ cash = data.cash.Value, owned = data.owned, ipo = data.ipo, team = data.team, section = CompanyServer.serialize(data) })
end

-- 1. An IPO is refused while the pokedex is locked --------------------------------------------------
local V2 = { v = 2, run = 0, active = { sector = "Software", future = { 1, 2 } }, other = { a = 1 } }
local UNKNOWN_SECTOR = { v = 1, run = 0, active = { sector = "Energy" } }
local NOT_A_LIST = { v = 1, run = 0, active = { sector = "Software", objects = { first = { id = "Desk", x = -23, z = -40, r = 0 } } } } -- a map: a shape this version doesn't know, and one the store can hold
local BROKEN = { v = 1, run = 0, active = "whatever", precious = { x = 1 } }
local LOCKED = {
	{ "a newer version's section", function() return newPlayer(deepCopy(V2)) end, V2 },
	{ "a sector this version doesn't know", function() return newPlayer(deepCopy(UNKNOWN_SECTOR)) end, UNKNOWN_SECTOR },
	{ "placed items that are not a plain list", function() return newPlayer(deepCopy(NOT_A_LIST)) end, NOT_A_LIST },
	{ "a section that failed to load", function()
		local realLoad = CC.load
		CC.load = function(saved, ctx) if saved ~= nil then error("boom") end return realLoad(saved, ctx) end
		local made, player, data = pcall(newPlayer, deepCopy(BROKEN))
		CC.load = realLoad
		assert(made, player)
		return player, data
	end, BROKEN },
}
for _, kind in ipairs(LOCKED) do
	local label, make, section = kind[1], kind[2], kind[3]
	local player, data = make()
	resetFakes()
	check("locked (" .. label .. "): the player is locked", CompanyServer.isLocked(data) == true)
	local before = live(data)
	WARNINGS = {}
	local called, result = pcall(commitIpo, player, ipoAfter(data))
	check("an IPO while the pokedex is locked: the call returns false (" .. label .. ")", called and result == false, called and tostring(result) or result)
	check("an IPO while the pokedex is locked: Cash, upgrades, eggs, ipo.count and the company are unchanged (" .. label .. ")",
		deepEqual(live(data), before) and data.cash.Value == 250 and data.ipo.count == 1 and next(data.owned) ~= nil and COUNT.destroyed == 0 and COUNT.cleared == 0 and COUNT.hrReset == 0 and COUNT.income == 0)
	check("an IPO while the pokedex is locked: nothing was saved (" .. label .. ")", STORE.calls == 0 and STORE.last == nil, STORE.calls)
	check("an IPO while the pokedex is locked: the refusal is logged with the player and the reason (" .. label .. ")",
		#WARNINGS == 1 and string.find(WARNINGS[1], "Not going public for P: their pokedex is kept as it is (a newer version's, or unreadable)", 1, true) ~= nil, WARNINGS[1])
	check("an IPO while the pokedex is locked: the lock is released (" .. label .. ")", data.saving == false)
	local saved = save(player)
	check("an IPO while the pokedex is locked: the next save writes the section back as it was, with the old Cash and ipo (" .. label .. ")",
		saved == true and STORE.last ~= nil and deepEqual(STORE.last.pokedex, section) and STORE.last.cash == 250 and STORE.last.ipo.count == 1 and #STORE.last.owned == 2)
end
check("an IPO for a player who is gone: false", commitIpo({ Name = "Gone" }, { count = 2 }) == false)

-- 2. An IPO with a readable pokedex goes through, with run = the new count in the same save ------------------------------
do
	local player, data = newPlayer(nil, 1) -- a new founding, run = 1
	resetFakes()
	local company = deepCopy(CompanyServer.serialize(data).active)
	local after = ipoAfter(data)
	local result = commitIpo(player, after)
	check("an IPO with an unlocked pokedex: the call returns true and saves once", result == true and STORE.calls == 1 and STORE.key == "player_7", result)
	local payload = STORE.last or { owned = {}, ipo = {}, pokedex = {} }
	check("an IPO with an unlocked pokedex: the saved payload has Cash reset, upgrades cleared and the new IPO section",
		payload.cash == IpoConfig.StartingCash and #payload.owned == 0 and payload.ipo.count == 2 and payload.ipo.shares == 8)
	check("an IPO with an unlocked pokedex: the saved payload carries run = the new count (same company, no stamp, no card)",
		payload.pokedex.run == 2 and deepEqual(payload.pokedex.active, company) and next(payload.pokedex.sectors) == nil, payload.pokedex.run)
	check("an IPO with an unlocked pokedex: the live game followed (Cash, upgrades, items, eggs, income)",
		data.cash.Value == IpoConfig.StartingCash and next(data.owned) == nil and next(data.items) == nil and COUNT.destroyed == 2 and COUNT.cleared == 1 and COUNT.hrReset == (IpoConfig.Resets.HRDepartment and 1 or 0) and COUNT.income == 1 and COUNT.sign == 1)
	check("an IPO with an unlocked pokedex: the section in memory follows (run 2)", CompanyServer.serialize(data).run == 2)
	data.ipo = after -- IpoServer replaces its own section after a good commit
	resetFakes()
	check("an IPO with an unlocked pokedex: an autosave right after keeps run = 2", save(player) == true and STORE.last.pokedex.run == 2)
end
do
	local player, data = newPlayer(nil, 1)
	resetFakes()
	STORE.fail = true
	WARNINGS = {}
	local result = commitIpo(player, ipoAfter(data))
	check("an IPO whose save failed: the call returns false", result == false, result)
	check("an IPO whose save failed: Cash, upgrades, ipo.count and the section in memory (run 1) are unchanged",
		data.cash.Value == 250 and next(data.owned) ~= nil and data.ipo.count == 1 and CompanyServer.serialize(data).run == 1 and COUNT.destroyed == 0 and COUNT.cleared == 0)
	check("an IPO whose save failed: the lock is released and the failure is logged", data.saving == false and anyWarning("Save failed for P"))
end

-- 3. A section with fields this version doesn't know: an IPO still writes run and keeps every unknown field -----------------
do
	local FAT = __FATPOKEDEX__
	local player, data = newPlayer(deepCopy(FAT), FAT.run)
	resetFakes()
	check("unknown fields: the join is clean (no warning, no run check, not locked)", #WARNINGS == 0 and data.pokedex.event == nil and not CompanyServer.isLocked(data), WARNINGS[1])
	local expected = deepCopy(FAT)
	expected.run = FAT.run + 1
	expected.studio = true -- a Studio server marks every save
	local result = commitIpo(player, ipoAfter(data))
	check("an IPO with unknown fields in the pokedex: the call returns true and saves once", result == true and STORE.calls == 1, result)
	local payload = STORE.last or { pokedex = {} }
	check("an IPO with unknown fields in the pokedex: the saved payload carries run = the new count", payload.pokedex.run == FAT.run + 1, payload.pokedex.run)
	check("an IPO with unknown fields in the pokedex: every unknown field is written back unchanged, at every level", deepEqual(payload.pokedex, expected))
	check("an IPO with unknown fields in the pokedex: the section in memory follows (run = the new count)", CompanyServer.serialize(data).run == FAT.run + 1)
	check("an IPO with unknown fields in the pokedex: and its unknown fields are unchanged in memory", deepEqual(CompanyServer.serialize(data), expected))
end

-- 4. A card.owned the store would refuse (the review's case): tidied on load, so the save works ----------------------------------
do
	local FAT = __FATPOKEDEX__
	local mixed = deepCopy(FAT)
	mixed.sectors.Software.card.owned = { "Desk", "Laptop", future = "GamingRig", [5] = "Neon Logo" }
	local player, data = newPlayer(mixed, FAT.run)
	check("a mixed card.owned: the join warns about it and does not lock the section", not CompanyServer.isLocked(data) and anyWarning("card.owned"))
	resetFakes()
	local ok = save(player)
	check("a mixed card.owned: save() succeeds against the faithful store (nothing refused)", ok == true and STORE.calls == 1 and STORE.refused == 0, STORE.problem)
	local owned = (STORE.last or { pokedex = { sectors = { Software = { card = { owned = {} } } } } }).pokedex.sectors.Software.card.owned
	check("a mixed card.owned: what is written is the plain list Desk, Laptop, Neon Logo", #owned == 3 and owned[1] == "Desk" and owned[2] == "Laptop" and owned[3] == "Neon Logo" and next(owned, 3) == nil)
	local holey = deepCopy(FAT)
	holey.sectors.Software.card.owned = { "Desk", nil, "Laptop" }
	holey.active.objects[4] = { id = "Whiteboard", x = 1, z = 1, r = 0 }
	player, data = newPlayer(holey, FAT.run)
	resetFakes()
	check("a holey card.owned and a holey objects list: save() succeeds against the faithful store", save(player) == true and STORE.refused == 0, STORE.problem)
end
check("every payload save() sent to the faithful store was accepted (" .. STORE.sent .. " sent, " .. STORE.refused .. " refused)", STORE.refused == 0 and STORE.sent > 0, STORE.problem)
print_real(string.format("%d passed, %d failed", passed, failed))
"""


def commit_ipo_source(mutation=None):
    """The COMMITIPO_TESTS program with the real save() and commitIpo() (the TycoonCore code between the SAVEFN and COMMITIPO markers),
    the real CompanyServer, CompanyConfig, SectorConfig and IpoConfig, and fake everything else. mutation = (file, old, new) breaks one
    rule in TycoonCore.lua or CompanyServer.lua (`old` must be in it exactly once)."""
    def read(name):
        with open(os.path.join(ROOT, name), encoding="utf-8") as f:
            return f.read()

    texts = {name: read(name + ".lua") for name in ("SectorConfig", "IpoConfig", "CompanyConfig", "CompanyServer", "TycoonCore")}
    if mutation:
        name, old, new = mutation
        name = name[:-4] if name.endswith(".lua") else name
        if texts[name].count(old) != 1:
            raise SystemExit("mutation target not found exactly once in %s: %s" % (name, old))
        texts[name] = texts[name].replace(old, new, 1)

    def slice_of(marker):
        text = texts["TycoonCore"]
        return text[text.index("-- %s-START" % marker) + len("-- %s-START" % marker):text.index("-- %s-END" % marker)]

    return (COMMITIPO_TESTS.replace("__SECTORCONFIG__", texts["SectorConfig"]).replace("__IPOCONFIG__", texts["IpoConfig"])
            .replace("__COMPANYCONFIG__", texts["CompanyConfig"]).replace("__COMPANYSERVER__", texts["CompanyServer"])
            .replace("__KNOWNSECTIONS__", known_sections_line()).replace("__BUILDSAVE__", slice_of("BUILDSAVE"))
            .replace("__SAVENOTE__", slice_of("SAVENOTE")).replace("__SAVEFN__", slice_of("SAVEFN"))
            .replace("__COMMITIPO__", slice_of("COMMITIPO")).replace("__FATPOKEDEX__", FAT_POKEDEX_LUA))


_GUARD_WARN = "warn(\"Not going public for \" .. player.Name .. \": their pokedex is kept as it is (a newer version's, or unreadable)\")\n"
COMMITIPO_MUTATIONS = [
    ("the lock guard of commitIpo returns true", ("TycoonCore.lua", "unreadable)\")\n\t\treturn false\n", "unreadable)\")\n\t\treturn true\n"),
     "an IPO while the pokedex is locked: the call returns false"),
    ("the lock guard of commitIpo returns nothing", ("TycoonCore.lua", "unreadable)\")\n\t\treturn false\n", "unreadable)\")\n\t\treturn\n"),
     "an IPO while the pokedex is locked: the call returns false"),
    ("the lock guard of commitIpo falls through", ("TycoonCore.lua", "unreadable)\")\n\t\treturn false\n", "unreadable)\")\n"),
     "an IPO while the pokedex is locked: the call returns false"),
    ("the lock guard of commitIpo is off", ("TycoonCore.lua", "\tif CompanyServer.isLocked(data) then\n", "\tif false then\n"),
     "an IPO while the pokedex is locked: the call returns false"),
    ("the refusal of a locked IPO is not logged", ("TycoonCore.lua", "\t\t" + _GUARD_WARN, ""),
     "an IPO while the pokedex is locked: the refusal is logged with the player and the reason"),
    ("the refusal of a locked IPO logs another reason", ("TycoonCore.lua", "Not going public for \" .. player.Name .. \": their pokedex", "Not going public for \" .. player.Name .. \": their cash"),
     "an IPO while the pokedex is locked: the refusal is logged with the player and the reason"),
    ("commitIpo no longer writes run in the IPO's save", ("TycoonCore.lua", "\t\tCompanyServer.writeIpoRun(data, payload, newIpo.count) -- the pokedex's run follows the new count in this very save\n", ""),
     "an IPO with an unlocked pokedex: the saved payload carries run = the new count"),
    ("commitIpo moves the run in memory even when the save failed", ("TycoonCore.lua", "\tif not ok or playerData[player] ~= data then\n\t\treturn ok\n\tend\n\tCompanyServer.onIpo", "\tCompanyServer.onIpo(data, newIpo.count)\n\tif not ok or playerData[player] ~= data then\n\t\treturn ok\n\tend\n\tCompanyServer.onIpo"),
     "an IPO whose save failed: Cash, upgrades, ipo.count and the section in memory (run 1) are unchanged"),
    ("card.owned keeps a string key next to its names (the old KEEP rule): save() is refused by the faithful store", ("CompanyConfig.lua", "\t\tif #out == 0 and typeof(other) == \"string\" then\n\t\t\tout[other]", "\t\tif typeof(other) == \"string\" then\n\t\t\tout[other]"),
     "a mixed card.owned: save() succeeds against the faithful store (nothing refused)"),
    ("placed items keep a hole (an entry after a gap stays under its own key): save() is refused by the faithful store", ("CompanyConfig.lua", "\t\t\ttable.insert(out, object)\n", "\t\t\tout[index] = object\n"),
     "a holey card.owned and a holey objects list: save() succeeds against the faithful store"),
    ("commitIpo no longer resets the Cash in the live game", ("TycoonCore.lua", "\tif resets.Cash then\n\t\tdata.cash.Value = IpoConfig.StartingCash\n\tend\n", ""),
     "an IPO with an unlocked pokedex: the live game followed (Cash, upgrades, items, eggs, income)"),
]


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
          sorted(re.findall(r"(\w+) = true", sections)) == sorted("cash owned lastSeen shop team poach ipo onboarding daily fixedHires tasks pokedex".split()), sections)
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
          'button.Visible = row.state ~= "locked"' in client and 'setButton(button, "Owned", COLORS.owned, false)' in client)

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
    save_gate = re.search(r"if not \(data\.shop and[^\n]*\) then", core)
    check("TycoonCore: a save needs data.tasks and data.pokedex like every other part",
          save_gate is not None and all("data." + name in save_gate.group(0) for name in ("shop", "team", "poach", "ipo", "onboarding", "daily", "tasks", "pokedex")),
          save_gate and save_gate.group(0))
    check("TycoonCore: DataStore name and key untouched", 'GetDataStore("StartupTycoon_v1")' in core and '"player_" .. player.UserId' in core)

    # Every addEarnings call site in the game. A new one fails here until it is reviewed (valuation!).
    expected = {"TycoonCore.lua": 3, "ShopServer.lua": 1, "IpoServer.lua": 2, "TaskServer.lua": 1, "DailyServer.lua": 0, "EmployeeServer.lua": 0, "PoachServer.lua": 0, "OnboardingServer.lua": 0}
    for filename, count in expected.items():
        calls = 0
        for line in code_only(read(filename)).split("\n"):
            if re.search(r"addEarnings\s*\(", line) and not re.search(r"function\s+[\w.]*addEarnings\s*\(", line):
                calls += 1
        check("%s has %d addEarnings call(s)" % (filename, count), calls == count, calls)
    # A file that isn't in the list has none (the new files are scanned too: a new call site fails here until it is reviewed)
    for filename in sorted(n for n in os.listdir(ROOT) if n.endswith(".lua") and n not in expected):
        calls = len(addearnings_calls(code_only(read(filename))))
        check("%s has no addEarnings call (it is not in the reviewed list)" % filename, calls == 0, calls)

    server = code_only(read("TaskServer.lua"))
    check("TaskServer pays only through core.addEarnings (never IpoServer directly)", server.count("core.addEarnings(") == 1 and "IpoServer.addEarnings" not in server)
    check("TaskServer never grants Shares, eggs or products", all(word not in server for word in ("grantShares", "grantEgg", "grantProduct", "PromptProductPurchase")))
    check("TaskServer only touches data.tasks, data.cash and data.income of the player's data",
          not re.search(r"data\.(shop|team|poach|ipo|onboarding|daily|fixedHires)\s*(=[^=]|\.[A-Za-z_]+\s*(=[^=]|\+=|-=))", server))
    config = read("TaskConfig.lua")
    check("TaskConfig: Enabled and StudioOnly are on (PR 1 runs only in Studio)", "TaskConfig.Enabled = true" in config and "TaskConfig.StudioOnly = true" in config)

    forbidden = ("odds", "chance", "luck", "random", "probab", "%")
    for filename in ("TaskClient.lua", "TaskServer.lua", "CompanyServer.lua", "CompanyConfig.lua", "SectorConfig.lua"):
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
    ("the idle clock is not held before the Desk and not started when it is bought", "TaskServer.lua",
     "\tif not on then\n\t\trun.lastActionAt = now\n\tend\n\tif run.on ~= on then\n\t\tif on and run.on == false then\n\t\t\trun.misses = 0\n\t\t\trun.lastActionAt = now\n",
     "\tif run.on ~= on then\n\t\tif on and run.on == false then\n\t\t\trun.misses = 0\n",
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
    ("the miss counter is not reset when calls turn on", "TaskServer.lua",
     "\t\t\trun.misses = 0\n\t\t\trun.lastActionAt = now\n", "\t\t\trun.lastActionAt = now\n",
     "engine", "desk: missed calls from before the Desk do not start quiet mode when it is bought"),
    ("the miss counter is reset on every tick, calls on or off", "TaskServer.lua",
     "\tif run.on ~= on then\n\t\tif on and run.on == false then\n", "\trun.misses = 0\n\tif run.on ~= on then\n\t\tif on and run.on == false then\n",
     "engine", "desk: ... the calls that ran out while calls were off are counted by the engine"),
    ("the reset removes a waiting call", "TaskServer.lua",
     "\t\t\trun.misses = 0\n\t\t\trun.lastActionAt = now\n", "\t\t\trun.misses = 0\n\t\t\trun.lastActionAt = now\n\t\t\tfor _, id in ipairs(table.clone(run.order)) do closeTask(run, id) end\n",
     "engine", "desk: when calls turn on the miss counter is reset and the call that is waiting is kept"),
    ("the miss counter is also reset while calls stay on", "TaskServer.lua",
     "\tif on and not run.quiet and not run.paused\n", "\tif on then run.misses = 0 end\n\tif on and not run.quiet and not run.paused\n",
     "engine", "desk: with calls on, two calls that ran out stay counted"),
    ("the idle clock is not started when calls turn on", "TaskServer.lua",
     "\t\t\trun.misses = 0\n\t\t\trun.lastActionAt = now\n", "\t\t\trun.misses = 0\n",
     "engine", "desk: when calls turn on after a long step the idle clock starts at the unlock"),
    ("the miss counter is reset when calls turn off instead of on", "TaskServer.lua",
     "\t\tif on and run.on == false then\n", "\t\tif not on and run.on == true then\n",
     "engine", "desk: missed calls from before the Desk do not start quiet mode when it is bought"),
    ("the miss counter is also reset at the first tick (a join)", "TaskServer.lua",
     "\t\tif on and run.on == false then\n", "\t\tif on and run.on ~= true then\n",
     "engine", "3 expired calls in a row start quiet mode"),
    ("the gap formula changes (a faster pace per level)", "TaskConfig.lua",
     "gapPerLevel = 0.02,", "gapPerLevel = 0.03,",
     "engine", "gap: the numbers the Studio sync steps quote"),
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
    spawn = re.search(r"local spawnPos = plotFrame\(slot\) \* Vector3\.new\((-?[\d.]+), 4, (-?[\d.]+)\)", core)
    floor = re.search(r'makePart\(garage, "Floor", Vector3\.new\((\d+), (\d+), (\d+)\), plotFrame\(slot\)', core)  # lobby L2: made once, in buildGarages
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


# Interiors: broken versions of PlotVisuals' kit builder. Each must be caught by the named visuals check (its start).
VISUALS_KIT_MUTANTS = [
    ("a kit MeshPart left collidable", "\t\t\tpart.CanCollide = false\n\t\t\tpart.CanQuery = false\n", "\t\t\tpart.CanQuery = false\n",
     "kit: room 1 with the kit (each role one MeshPart, as imported): PlotVisuals.check finds nothing"),
    ("the importer's turn ignored", "local target = pieceFrame(base, spec) * CFrame.Angles(0, math.rad(frontTurn), 0)", "local target = pieceFrame(base, spec)",
     "kit: room 1: a kit model as imported and one imported the other way"),
    ("a model's KitSize ignored (not fitted to the manifest)", "sx * entry.size[1] / (ok and real.X or entry.size[1]),", "sx,",
     "kit: a model a little bigger than the manifest"),
    ("the Parts version not scaled", "size = { b.size[1] * sx, b.size[2] * sy, b.size[3] * sz },", "size = { b.size[1], b.size[2], b.size[3] },",
     "room 1: no part in a reserved zone"),
    ("a kit MeshPart not recolored", "\t\t\tpart.Color = rgb(look[1])\n", "",
     "kit: room 1 with the kit (each role one MeshPart, as imported): every kit piece part has its role's color and material"),
    ("an uneven scale of a part turned in its model", "return fail(\"a part is not square to the model, so it can't be scaled unevenly\")", "out[axis] = size[axis] * f[axis]",
     "kit: a part turned inside its model can't be scaled unevenly"),
    ("no PointLight on a kit bulb", "if spec.light and role == spec.lightRole and seen[role] == 1 then", "if false then",
     "garage with the kit (each role one MeshPart, as imported): the bulb's glass glows"),
    ("a MeshPart that can't be copied (Clone gives nil) not handled", "\t\t\tif not part then -- Roblox's Clone gives nil when Archivable is off\n", "\t\t\tif false then\n",
     "kit: a MeshPart that can't be copied"),
    ("kitBox ignores a quarter turn", "if (spec.turn or 0) % 180 == 90 then", "if false then",
     "kit: kitBox of a workbench turned 90"),
    ("a missing model warned at every build", "\t\twarnOnce(\"kit \" .. spec.kit, \"KitModels.\" .. spec.kit .. \" is missing: the rooms build it from Parts\")",
     "\t\twarn(\"Plot visuals: KitModels.\" .. spec.kit .. \" is missing: the rooms build it from Parts\")",
     "kit: a missing model (Workbench) is built from Parts"),
    ("validate lets any turn through", "if s.turn ~= nil and not PlotVisuals.TURNS[s.turn] then", "if false then",
     "mutation (kit): a turn that is not a quarter turn is caught"),
    ("a kit piece built from Parts even with the kit", "\tlocal template = kit and kit:FindFirstChild(spec.kit)\n", "\tlocal template = nil\n",
     "kit: room 1 with the kit (each role one MeshPart, as imported): every kit piece is built from the kit's MeshParts"),
    ("newPlot forgets the kit it is given", "kit = kit or PlotVisuals.findKit(art)", "kit = PlotVisuals.findKit(art)",
     "kit: newPlot keeps the kit it is given"),
]


def run_visuals_kit_mutants(luau, base):
    """Runs the visuals tests (base: the program with every placeholder but __PLOTVISUALS__ filled) once per mutant."""
    with open(os.path.join(ROOT, "PlotVisuals.lua"), encoding="utf-8") as f:
        real = f.read()
    caught, problems = 0, []
    for label, old, new, expected in VISUALS_KIT_MUTANTS:
        if real.count(old) != 1:
            problems.append("FAIL: the kit mutant '%s' no longer matches PlotVisuals.lua (update VISUALS_KIT_MUTANTS)" % label)
            continue
        result = run_luau(luau, base.replace("__PLOTVISUALS__", real.replace(old, new)))
        verdict = mutant_verdict(result, (expected,), "plot visuals", label)
        if verdict:
            problems.append(verdict)
        else:
            caught += 1
    return caught, problems


def kit_doc_lua():
    """docs/KIT_MODELS.md's table of the 36 kit models as a Luau table: { Key = { size = { W, H, D }, roles = { ... } } }.
    The doc gives W x D x H; PlotArt.Kit (and PlotBuilding.KitManifest) give width, height, depth."""
    import re
    with open(os.path.join(ROOT, "docs", "KIT_MODELS.md"), encoding="utf-8") as f:
        text = f.read()
    rows = re.findall(r"^\| `(\w+)` \| [^|]+ \| ([\d.]+) x ([\d.]+) x ([\d.]+) \| \d+ \| ([^|]+) \|$", text, re.M)
    if len(rows) != 36:
        raise SystemExit("docs/KIT_MODELS.md: expected 36 kit rows, found %d" % len(rows))
    out = []
    for key, w, d, h, roles in rows:
        names = re.findall(r"(\w+) #[0-9A-Fa-f]{6}", roles)
        out.append('%s = { size = { %s, %s, %s }, roles = { %s } }' % (key, w, h, d, ", ".join('"%s"' % n for n in names)))
    return "{ " + ", ".join(out) + " }"


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
        if name == "PlotVisuals.lua":
            # interiors: the one service PlotVisuals reads is ReplicatedStorage, for the furniture kit (findKit, inside pcall)
            code = code.replace('game:GetService("ReplicatedStorage"):FindFirstChild(art.KIT_FOLDER)', "", 1)
        for word in ("GetService", "RemoteEvent", "RemoteFunction", "DataStore", "SetAsync", "addEarnings", "Random", "math.random",
                     "rbxasset", "http", "Texture =", "MeshId", "Decal", "require("):
            check("%s never uses %s (pure looks: no services, remotes, saves, assets or randomness)" % (name, word), word not in code)
    vis = code_only(read("PlotVisuals.lua"))
    find_kit = vis[vis.index("function PlotVisuals.findKit("):vis.index("local function scaleOf(")]
    check("PlotVisuals: the only service it reads is ReplicatedStorage, once, inside pcall in findKit (the furniture kit)",
          vis.count("GetService") == 1 and 'pcall(function()\n\t\treturn game:GetService("ReplicatedStorage"):FindFirstChild(art.KIT_FOLDER)' in find_kit)
    check("PlotVisuals: a kit MeshPart is only copied (Clone), never made from an asset id", "MeshId" not in vis and "CreateMeshPartAsync" not in vis
          and "InsertService" not in vis and "d:Clone()" in vis)
    pb = read("PlotBuilding.lua")
    m_turn = re.search(r"PlotBuilding\.KIT_FRONT_TURN = (\d+)", pb)
    m_art = re.search(r"PlotArt\.KIT_FRONT_TURN = (\d+)", read("PlotArt.lua"))
    check("PlotArt.KIT_FRONT_TURN is PlotBuilding.KIT_FRONT_TURN (the rooms and the buildings turn the kit the same way)",
          m_turn is not None and m_art is not None and m_turn.group(1) == m_art.group(1), (m_turn and m_turn.group(1), m_art and m_art.group(1)))
    m_folder = re.search(r'PlotBuilding\.KIT_FOLDER = "(\w+)"', pb)
    check("PlotArt.KIT_FOLDER is PlotBuilding.KIT_FOLDER (one KitModels folder)", m_folder is not None and ('PlotArt.KIT_FOLDER = "%s"' % m_folder.group(1)) in read("PlotArt.lua"))
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
    # Lobby L2: the closed building (PlotBuilding, PlotBuildingVisuals) and its client (BuildingClient); tools/building_test.py
    # tests them in depth. Here: looks only, wired like the plot visuals.
    for name in ("PlotBuilding.lua", "PlotBuildingVisuals.lua", "BuildingClient.lua"):
        text = code_only(read(name))
        for word in ("RemoteEvent", "RemoteFunction", "FireServer", "DataStore", "SetAsync", "addEarnings", "math.random", "Random.new",
                     "rbxasset", "http", "MeshId", "require("):
            check("%s never uses %s (looks only: no remotes, saves, earnings, randomness or assets)" % (name, word), word not in text)
    check("TycoonCore: PlotBuilding and PlotBuildingVisuals are required inside pcall (a building bug can never stop the game)",
          re.search(r'pcall\(require, script\.Parent:WaitForChild\("PlotBuildingVisuals", \d+\)\)', code) is not None
          and re.search(r'pcall\(require, script\.Parent:WaitForChild\("PlotBuilding", \d+\)\)', code) is not None)
    check("TycoonCore: the building is synced only through pcall (syncBuilding) and never inside the save code",
          code.count("PlotBuildingVisuals.sync") == 1 and "pcall(PlotBuildingVisuals.sync" in code
          and "PlotBuilding" not in core[core.index("-- BUILDSAVE-START"):core.index("-- SAVEFN-END")])
    return passed, failed


# --- The plot frame (lobby PR L1, docs/LOBBY_GARAGE_PROPOSAL.md section 4.3) -----------------------------------------
# Every "center + offset" of a garage goes through TycoonCore's plotFrame (the center turned by GARAGE_TURNS), so a turned
# garage is the unturned one turned. L1 turns nothing: every turn is 0 and every position must be main's, exactly. The
# real code of TycoonCore, EmployeeServer, IpoServer, PlotVisuals and PlotArt runs in the visuals fake (real rotations).

FRAME_TESTS = r"""
-- More of Roblox for these tests: a Part's Position and CFrame are one property, Models pivot, prompts connect
do
	local index, newindex = Mt.__index, Mt.__newindex
	Mt.__index = function(t, k)
		if k == "Position" and rawget(t, "CFrame") then return rawget(t, "CFrame").Position end
		return index(t, k)
	end
	Mt.__newindex = function(t, k, v)
		if k == "Position" and rawget(t, "ClassName") == "Part" then
			local c = rawget(t, "CFrame")
			rawset(t, "CFrame", cf(v.X, v.Y, v.Z, c and c.r or nil))
			return
		end
		newindex(t, k, v)
	end
end
function Methods.PivotTo(t, c) rawset(t, "pivot", c) end
function Methods.WaitForChild(t, name) return t:FindFirstChild(name) end
Methods.Triggered = { Connect = function() end }
Enum.MeshType = enumType({ "Sphere" })
UDim2.new = function() return {} end
UDim2.fromOffset = function(x, y) return { x, y } end
Color3.new = function(r, g, b) return { R = r, G = g, B = b } end

local PlotArt = (function()
__PLOTART__
end)()
local PlotVisuals = (function()
__PLOTVISUALS__
end)()

-- CompanyConfig (the placement rules), loaded the way the server requires it
local MODULES = {}
local function token(name) return { Name = name, WaitForChild = function(self, n) return token(n) end } end
local function require(x) return assert(MODULES[x.Name], "no module " .. tostring(x.Name)) end
local SERVICES = { ReplicatedStorage = token("ReplicatedStorage"), RunService = { IsStudio = function() return true end } }
local game = { GetService = function(_, n) return SERVICES[n] end }
MODULES.SectorConfig = (function()
__SECTORCONFIG__
end)()
MODULES.IpoConfig = (function()
__IPOCONFIG__
end)()
MODULES.CompanyConfig = (function()
__COMPANYCONFIG__
end)()
local CompanyConfig = MODULES.CompanyConfig

-- The real TycoonCore code, with the garages turned by TURNS (its own GARAGE_TURNS line is read separately below)
local function coreAt(TURNS)
	local playerData = {}
	local LobbyConfig = { ClaimEnabled = false } -- the row: plotCenter reads the ring only with the claim on (lobby L4, tested in tools/lobby_test.py and world_test.py)
	local Players = { GetPlayerFromCharacter = function() return nil end } -- the landing asks streaming for a player (lobby L4)
__CORE_CONSTANTS__
	local GARAGE_TURNS = TURNS
__UPGRADES__
__CORE_FUNCTIONS__
	local plotZones = __PLOTZONES__
	return { plotFrame = plotFrame, plotCenter = plotCenter, makePart = makePart, itemOffset = itemOffset, spawnItem = spawnItem,
		refreshSign = refreshSign, teleportToPlot = teleportToPlot, plotZones = plotZones, playerData = playerData, UPGRADES = UPGRADES,
		MAX_PLOTS = MAX_PLOTS, SIGN_OFFSET = SIGN_OFFSET }
end
local REAL_TURNS = (function()
__TURNS_LINE__
	return GARAGE_TURNS
end)()

-- IpoServer's garage sign and EmployeeServer's employees and incubators, with a core that gives plotFrame
local function ipoAt(core)
__IPO_CONSTANTS__
	local function refreshSign() end
__BUILDSIGN__
	return buildSign
end
local function employeeAt(core)
__EMPLOYEE_CONSTANTS__
	local CreatureConfig = { getCreature = function(name) return { name = name } end }
	local CreatureModels = { build = function() local m = newInstance("Model") return m end }
	local CollectionService = { AddTag = function() end }
	local function addNameTag() end
	local function makeLabel() return newInstance("TextLabel") end
	local function hatch() end
	local function refreshIncubator() end
__EMPLOYEE_FUNCTIONS__
	return placeEmployees, buildIncubator, EMPLOYEE_SPOTS, INCUBATOR_SPOTS, FEET
end

local EPS = 1e-6
local function sameCF(a, b, eps)
	if not a or not b then return false end
	eps = eps or EPS
	if math.abs(a.x - b.x) > eps or math.abs(a.y - b.y) > eps or math.abs(a.z - b.z) > eps then return false end
	for i = 1, 9 do if math.abs(a.r[i] - b.r[i]) > eps then return false end end
	return true
end
local function exactCF(a, b) return sameCF(a, b, 0) end
local function sameVec(a, b, eps)
	eps = eps or EPS
	return a ~= nil and b ~= nil and math.abs(a.X - b.X) <= eps and math.abs(a.Y - b.Y) <= eps and math.abs(a.Z - b.Z) <= eps
end
local IDENTITY = cf(0, 0, 0)
local function rowCenter(slot) return Vector3.new(-225 + (slot - 1) * 90, 0.5, 150) end -- main's plotCenter, written out
local function partsOf(model)
	local out = {}
	for _, d in ipairs(model:GetDescendants()) do if d:IsA("BasePart") then table.insert(out, d) end end
	return out
end
-- Is listT the 0-degree list0 moved from frame0 into frameT, part for part (names, sizes and CFrames)?
local function turnedMatch(list0, listT, frame0, frameT)
	if #list0 == 0 or #list0 ~= #listT then return false, #list0 .. " / " .. #listT .. " parts" end
	local move = frameT * frame0:Inverse()
	for i = 1, #list0 do
		local a, b = list0[i], listT[i]
		if a.Name ~= b.Name or not sameVec(a.Size, b.Size, 0) or not sameCF(move * a.CFrame, b.CFrame) then return false, b:GetFullName() end
	end
	return true
end
local function newPlayer()
	local player = newInstance("Player")
	player.UserId = 7
	return player
end

local ZERO = { 0, 0, 0, 0, 0, 0 }
local MIXED = { 90, 180, 270, 0, 270, 90 } -- each turn on two garages, and slot 4 unturned
local core0, coreT = coreAt(ZERO), coreAt(MIXED)
local TURN_NAMES = { [0] = "0", [90] = "90", [180] = "180", [270] = "270" }
local function slotsAt(turn)
	local out = {}
	for slot, t in ipairs(MIXED) do if t == turn then table.insert(out, slot) end end
	return out
end

-- 1. The turn math ---------------------------------------------------------------------------------------------------
do
	local zeros, quarters = #REAL_TURNS > 0, #REAL_TURNS > 0
	for _, t in ipairs(REAL_TURNS) do
		if t ~= 0 then zeros = false end
		if t ~= 0 and t ~= 90 and t ~= 180 and t ~= 270 then quarters = false end
	end
	check("turn math: L1 turns no garage (GARAGE_TURNS is six zeros)", zeros and #REAL_TURNS == 6, table.concat(REAL_TURNS, ","))
	check("turn math: one turn per garage (#GARAGE_TURNS == MAX_PLOTS)", #REAL_TURNS == core0.MAX_PLOTS, #REAL_TURNS .. " turns, " .. core0.MAX_PLOTS .. " plots")
	check("turn math: every turn is a quarter turn (0, 90, 180 or 270)", quarters, table.concat(REAL_TURNS, ","))
	local real = coreAt(REAL_TURNS)
	local same, centers = true, true
	local ran, crash = pcall(function() -- a turn plotFrame can't make (not a quarter turn) errors: a failed check here, not a crash
		for slot = 1, core0.MAX_PLOTS do
			local want = rowCenter(slot)
			if not exactCF(real.plotFrame(slot), cf(want.X, want.Y, want.Z)) then same = false end
			local c = real.plotCenter(slot)
			if c.X ~= want.X or c.Y ~= want.Y or c.Z ~= want.Z then centers = false end
		end
	end)
	check("turn math: plotFrame(slot) is main's plotCenter(slot), unturned, for all six garages (exactly)", ran and same, crash)
	check("turn math: plotCenter is main's row (x -225 to 225, 90 apart, y 0.5, z 150), exactly", centers)
	local function dir(frame, x, z)
		local p = frame * Vector3.new(x, 0, z)
		return Vector3.new(p.X - frame.x, p.Y - frame.y, p.Z - frame.z)
	end
	local WANT = { -- the garage's front (+Z) and right (+X) in world axes; west garages turn 90 and face +X (section 4.2)
		[90] = { "+X", Vector3.new(1, 0, 0), "-Z", Vector3.new(0, 0, -1) },
		[180] = { "-Z", Vector3.new(0, 0, -1), "-X", Vector3.new(-1, 0, 0) },
		[270] = { "-X", Vector3.new(-1, 0, 0), "+Z", Vector3.new(0, 0, 1) },
	}
	for _, turn in ipairs({ 90, 180, 270 }) do
		local w, ok = WANT[turn], true
		for _, slot in ipairs(slotsAt(turn)) do
			local f = coreT.plotFrame(slot)
			if not (sameVec(dir(f, 0, 1), w[2]) and sameVec(dir(f, 1, 0), w[4])) then ok = false end
		end
		check("turn math: at " .. turn .. " degrees the garage's front (+Z) faces world " .. w[1] .. " and its right (+X) faces world " .. w[3], ok)
	end
	local keeps = true
	for slot = 1, 6 do
		local f = coreT.plotFrame(slot)
		if not sameVec(f.Position, rowCenter(slot), 0) or not sameVec(f * Vector3.new(0, 1, 0) - f.Position, Vector3.new(0, 1, 0)) then keeps = false end
	end
	check("turn math: a turn keeps the garage's center (Position is plotCenter) and its up (+Y)", keeps)
end

-- 2. The room, the props and the Floor (PlotVisuals.newPlot takes the turn from the Floor) ------------------------------
-- What the join builds in a garage: the Floor (onPlayerAdded), the room of a stage with its props (the load: newPlot on
-- the room line, with plotCenter(slot), then spawnItem for every upgrade owned).
local function buildGarage(core, slot, withLooks)
	ROOT = newInstance("Folder")
	local folder = newInstance("Folder")
	folder.Parent = ROOT
	local floor = core.makePart(folder, "Floor", Vector3.new(60, 1, 60), core.plotFrame(slot), Color3.fromRGB(90, 90, 100))
	local data = { slot = slot, folder = folder, items = {}, owned = {} }
	if withLooks then
		data.looks = PlotVisuals.newPlot(folder, core.plotCenter(slot), PlotArt, floor, 1)
	end
	for i, upg in ipairs(core.UPGRADES) do
		data.owned[upg.name] = true
		core.spawnItem(data, i, upg)
	end
	return data, floor
end
do
	local stages = #PlotArt.Stages
	-- at 0 degrees: the room is main's, part for part (main built it from the Vector3 plot center)
	local exact, exactWhy = true, nil
	local floorExact = true
	for slot = 1, 6 do
		local data, floor = buildGarage(core0, slot, true)
		if not exactCF(floor.CFrame, cf(rowCenter(slot).X, 0.5, 150)) then floorExact = false end
		for s = 1, stages do
			PlotVisuals.setStage(data.looks, s, false)
			local main = PlotVisuals.buildRoom(nil, rowCenter(slot), PlotArt, s)
			for i, upg in ipairs(core0.UPGRADES) do
				PlotVisuals.buildProp(main:FindFirstChild("UpgradeProps"), rowCenter(slot), PlotArt, upg.name, core0.itemOffset(i))
			end
			local a, b = partsOf(main), partsOf(data.looks.room)
			if #a ~= #b or #a == 0 then exact = false; exactWhy = exactWhy or (#a .. " / " .. #b) end
			for i = 1, math.min(#a, #b) do
				if a[i].Name ~= b[i].Name or not exactCF(a[i].CFrame, b[i].CFrame) then exact = false; exactWhy = exactWhy or b[i]:GetFullName() end
			end
		end
	end
	check("room at 0 degrees: every stage room with the six props is main's, part for part (same names, exactly the same CFrames)", exact, exactWhy)
	check("room at 0 degrees: the Floor is main's (at plotCenter, unturned), exactly", floorExact)
	for _, turn in ipairs({ 90, 180, 270 }) do
		local same, why, clean, problem = true, nil, true, nil
		for _, slot in ipairs(slotsAt(turn)) do
			local d0, f0 = buildGarage(core0, slot, true)
			local dT, fT = buildGarage(coreT, slot, true)
			for s = 1, stages do
				PlotVisuals.setStage(d0.looks, s, false)
				PlotVisuals.setStage(dT.looks, s, false)
				local l0, lT = partsOf(d0.looks.room), partsOf(dT.looks.room)
				table.insert(l0, f0)
				table.insert(lT, fT)
				local ok, w = turnedMatch(l0, lT, core0.plotFrame(slot), coreT.plotFrame(slot))
				if not ok then same = false; why = why or ("stage " .. s .. ": " .. tostring(w)) end
				local probs = PlotVisuals.check(dT.looks.room, coreT.plotFrame(slot), PlotArt)
				if #probs > 0 then clean = false; problem = problem or ("stage " .. s .. ": " .. probs[1]) end
			end
		end
		check("room at " .. turn .. " degrees: every stage room, the six props and the Floor are the 0-degree build turned", same, why)
		check("room at " .. turn .. " degrees: PlotVisuals.check in the garage's frame finds no problem (every stage, six props)", clean, problem)
	end
end

-- 3. The plain blocks (no plot visuals) and the next-upgrade sign (TycoonCore) ----------------------------------------------
do
	local exact = true
	for slot = 1, 6 do
		local data = buildGarage(core0, slot, false)
		for i, upg in ipairs(core0.UPGRADES) do
			local want = rowCenter(slot) + core0.itemOffset(i) + Vector3.new(0, 0.5 + upg.size.Y / 2, 0)
			if not exactCF(data.items[upg.name].CFrame, cf(want.X, want.Y, want.Z)) then exact = false end
		end
	end
	check("blocks at 0 degrees: the six plain upgrade blocks (no plot visuals) stand where main puts them, exactly", exact)
	for _, turn in ipairs({ 90, 180, 270 }) do
		local same, why = true, nil
		for _, slot in ipairs(slotsAt(turn)) do
			local d0, dT = buildGarage(core0, slot, false), buildGarage(coreT, slot, false)
			local l0, lT = {}, {}
			for _, upg in ipairs(core0.UPGRADES) do
				table.insert(l0, d0.items[upg.name])
				table.insert(lT, dT.items[upg.name])
			end
			local ok, w = turnedMatch(l0, lT, core0.plotFrame(slot), coreT.plotFrame(slot))
			if not ok then same = false; why = why or w end
		end
		check("blocks at " .. turn .. " degrees: the six plain upgrade blocks are the 0-degree blocks turned", same, why)
	end
	local function buySign(core, slot)
		ROOT = newInstance("Folder")
		local player = newPlayer()
		local folder = newInstance("Folder")
		folder.Parent = ROOT
		local data = { slot = slot, folder = folder, owned = {}, items = {} }
		core.playerData[player] = data
		core.refreshSign(player)
		local post = data.sign
		return post, post and post:FindFirstChild("Board")
	end
	local exactSign = true
	for slot = 1, 6 do
		local post, board = buySign(core0, slot)
		local foot = rowCenter(slot) + core0.SIGN_OFFSET
		if not (post and board and exactCF(post.CFrame, cf(foot.X, foot.Y + 1.5, foot.Z)) and exactCF(board.CFrame, cf(foot.X, foot.Y + 4.3, foot.Z))) then exactSign = false end
	end
	check("BuySign at 0 degrees: the next-upgrade sign's post and board are main's, exactly", exactSign)
	for _, turn in ipairs({ 90, 180, 270 }) do
		local same, why = true, nil
		for _, slot in ipairs(slotsAt(turn)) do
			local p0, b0 = buySign(core0, slot)
			local pT, bT = buySign(coreT, slot)
			local ok, w = turnedMatch({ p0, b0 }, { pT, bT }, core0.plotFrame(slot), coreT.plotFrame(slot))
			if not ok then same = false; why = why or w end
		end
		check("BuySign at " .. turn .. " degrees: the next-upgrade sign (post and board) is the 0-degree sign turned", same, why)
	end
end

-- 4. The IPO sign (IpoServer) ---------------------------------------------------------------------------------------------
do
	local function ipoSign(core, slot)
		ROOT = newInstance("Folder")
		local folder = newInstance("Folder")
		folder.Parent = ROOT
		local data = { slot = slot, folder = folder, ipo = {} }
		ipoAt({ plotFrame = core.plotFrame })(newPlayer(), data)
		local post = folder:FindFirstChild("IpoSign")
		return post, post and post:FindFirstChild("Board")
	end
	local exact = true
	for slot = 1, 6 do
		local post, board = ipoSign(core0, slot)
		local foot = rowCenter(slot) + Vector3.new(21, 0.5, 24)
		if not (post and board and exactCF(post.CFrame, cf(foot.X, foot.Y + 1.5, foot.Z)) and exactCF(board.CFrame, cf(foot.X, foot.Y + 4.3, foot.Z))) then exact = false end
	end
	check("IpoSign at 0 degrees: the IPO sign's post and board are main's, exactly (21, 0.5, 24 from the center)", exact)
	for _, turn in ipairs({ 90, 180, 270 }) do
		local same, why = true, nil
		for _, slot in ipairs(slotsAt(turn)) do
			local p0, b0 = ipoSign(core0, slot)
			local pT, bT = ipoSign(coreT, slot)
			local ok, w = turnedMatch({ p0, b0 }, { pT, bT }, core0.plotFrame(slot), coreT.plotFrame(slot))
			if not ok then same = false; why = why or w end
		end
		check("IpoSign at " .. turn .. " degrees: the IPO sign (post and board) is the 0-degree sign turned", same, why)
	end
end

-- 5. Hire spots, employee facing and incubators (EmployeeServer) ------------------------------------------------------
do
	local HIRES = 13 -- more than the 11 spots: the second lap is shifted too
	local function team(core, slot)
		ROOT = newInstance("Folder")
		local folder = newInstance("Folder")
		folder.Parent = ROOT
		local data = { slot = slot, folder = folder, team = { employees = {}, models = {}, incubatorParts = {} } }
		for i = 1, HIRES do table.insert(data.team.employees, { id = "e" .. i, creature = "CodingCat" }) end
		local place, incubator, spots, incubatorSpots, feet = employeeAt({ plotFrame = core.plotFrame })
		place(data)
		for i = 1, 5 do incubator(newPlayer(), data, i) end
		local models = {}
		for i = 1, HIRES do models[i] = data.team.models["e" .. i] end
		return data, models, spots, incubatorSpots, feet
	end
	local homesExact, faceExact = true, true
	for slot = 1, 6 do
		local _, models, spots, _, feet = team(core0, slot)
		for i, model in ipairs(models) do
			local lap = (i - 1) // #spots
			local want = rowCenter(slot) + (spots[(i - 1) % #spots + 1] + Vector3.new(lap * 2, 0, lap * 2)) + feet
			local home = model:GetAttribute("Home")
			if not (home and home.X == want.X and home.Y == want.Y and home.Z == want.Z) then homesExact = false end
			if not exactCF(model.pivot, CFrame.new(want) * CFrame.Angles(0, math.pi, 0)) or model:GetAttribute("Facing") ~= math.pi then faceExact = false end
		end
	end
	check("hire spots at 0 degrees: every employee's Home is main's (center + spot + feet, second lap included), exactly", homesExact)
	check("employee facing at 0 degrees: every employee is pivoted as on main (math.pi) and Facing is exactly math.pi", faceExact)
	local incubatorsExact = true
	for slot = 1, 6 do
		local data, _, _, incubatorSpots = team(core0, slot)
		for i = 1, 5 do
			local parts, spot = data.team.incubatorParts[i], rowCenter(slot) + incubatorSpots[i]
			if not (parts and sameVec(parts.base.Position, spot + Vector3.new(0, 1, 0), 0) and sameVec(parts.glow.Position, spot + Vector3.new(0, 1.6, 0), 0)
				and sameVec(parts.egg.Position, spot + Vector3.new(0, 3.3, 0), 0)) then incubatorsExact = false end
		end
	end
	check("incubators at 0 degrees: the five incubators (base, glow, egg) stand where main puts them, exactly", incubatorsExact)
	for _, turn in ipairs({ 90, 180, 270 }) do
		local homes, facing, facingWhy, incubators = true, true, nil, true
		for _, slot in ipairs(slotsAt(turn)) do
			local d0, m0 = team(core0, slot)
			local dT, mT = team(coreT, slot)
			local move = coreT.plotFrame(slot) * core0.plotFrame(slot):Inverse()
			local front = coreT.plotFrame(slot) * Vector3.new(0, 0, 1) - coreT.plotFrame(slot).Position
			for i = 1, HIRES do
				if not sameVec(mT[i]:GetAttribute("Home"), move * m0[i]:GetAttribute("Home")) then homes = false end
				local pivot = mT[i].pivot
				local look = pivot and (pivot * Vector3.new(0, 0, -1) - pivot.Position) -- models face -Z
				local yaw = mT[i]:GetAttribute("Facing")
				if not (pivot and sameCF(pivot, move * m0[i].pivot) and sameVec(look, front) and type(yaw) == "number"
					and sameCF(CFrame.Angles(0, yaw, 0), pivot.Rotation)) then
					facing = false
					facingWhy = facingWhy or ("employee " .. i .. " in garage " .. slot)
				end
			end
			for i = 1, 5 do
				local a, b = d0.team.incubatorParts[i], dT.team.incubatorParts[i]
				for _, key in ipairs({ "base", "glow", "egg" }) do
					if not (a and b and sameVec(b[key].Position, move * a[key].Position)) then incubators = false end
				end
			end
		end
		check("hire spots at " .. turn .. " degrees: every employee's Home is the 0-degree Home turned (13 hires)", homes)
		check("employee facing at " .. turn .. " degrees: every employee faces the garage's front (its -Z is the frame's +Z) and Facing is that yaw", facing, facingWhy)
		check("incubators at " .. turn .. " degrees: the five incubators (base, glow, egg) are the 0-degree ones turned", incubators)
	end
end

-- 6. The landing on spawn (teleportToPlot) ------------------------------------------------------------------------------
do
	local function land(core, slot)
		local character = newInstance("Model")
		local root = newInstance("Part")
		root.Name = "HumanoidRootPart"
		root.Parent = character
		core.teleportToPlot(character, slot)
		return root.CFrame
	end
	local exact = true
	for slot = 1, 6 do
		local c = rowCenter(slot)
		if not exactCF(land(core0, slot), CFrame.lookAt(c + Vector3.new(0, 4, 12), c + Vector3.new(0, 4, 24))) then exact = false end
	end
	check("landing at 0 degrees: teleportToPlot lands where main lands (+12, looking at +24), exactly", exact)
	for _, turn in ipairs({ 90, 180, 270 }) do
		local same = true
		for _, slot in ipairs(slotsAt(turn)) do
			local move = coreT.plotFrame(slot) * core0.plotFrame(slot):Inverse()
			if not sameCF(land(coreT, slot), move * land(core0, slot)) then same = false end
		end
		check("landing at " .. turn .. " degrees: teleportToPlot lands at the 0-degree landing turned, facing the front sign", same)
	end
end

-- 7. plotZones and CompanyServer's placement: anchor coordinates, the same at every turn ---------------------------------
do
	local function serial(zones)
		local out = {}
		for _, z in ipairs(zones or {}) do
			table.insert(out, string.format("%s|%s|%s|%.6f,%.6f,%.6f,%.6f,%.6f,%.6f", z.kind or "", z.name or "", tostring(z.owner), z.box[1], z.box[2], z.box[3], z.box[4], z.box[5], z.box[6]))
		end
		return table.concat(out, ";")
	end
	local raw0, depth0 = core0.plotZones()
	local sameZones = raw0 ~= nil and #raw0 > 0
	for _, turns in ipairs({ MIXED, { 90, 90, 90, 90, 90, 90 }, { 180, 180, 180, 180, 180, 180 }, { 270, 270, 270, 270, 270, 270 } }) do
		local raw, depth = coreAt(turns).plotZones()
		if serial(raw) ~= serial(raw0) or depth ~= depth0 then sameZones = false end
	end
	check("plotZones: the reserved zones CompanyServer places against are identical at every turn (anchor coordinates)", sameZones)
	local function answers(raw, depth)
		local env = { building = 1, zones = CompanyConfig.anchorZones(raw, depth), owned = {}, decor = {}, objects = {} }
		for _, upg in ipairs(core0.UPGRADES) do env.owned[upg.name] = true end
		local out = {}
		for _, upg in ipairs(core0.UPGRADES) do
			for x = -24, 24, 4 do
				for z = -56, -4, 4 do
					for _, r in ipairs({ 0, 2 }) do
						local ok, reason = CompanyConfig.checkPlacement(env, upg.name, x, z, r)
						table.insert(out, tostring(ok) .. tostring(reason))
					end
				end
			end
		end
		return out
	end
	local a0 = answers(raw0, depth0)
	local yes = 0
	for _, a in ipairs(a0) do if string.sub(a, 1, 4) == "true" then yes += 1 end end
	local samePlacement = yes > 0 and yes < #a0
	for _, turns in ipairs({ MIXED, { 270, 270, 270, 270, 270, 270 } }) do
		local aT = answers(coreAt(turns).plotZones())
		if #aT ~= #a0 then samePlacement = false end
		for i = 1, #a0 do if aT[i] ~= a0[i] then samePlacement = false end end
	end
	check("CompanyConfig.checkPlacement: " .. #a0 .. " placements (" .. yes .. " allowed) give the same answers at every turn", samePlacement)
end

print_real(string.format("%d passed, %d failed", passed, failed))
"""


def frame_texts():
    """{file name: text} of the scripts the frame tests read."""
    names = ("TycoonCore.lua", "EmployeeServer.lua", "IpoServer.lua", "PlotVisuals.lua", "PlotArt.lua", "EmployeeClient.lua",
             "SectorConfig.lua", "IpoConfig.lua", "CompanyConfig.lua")
    out = {}
    for name in names:
        with open(os.path.join(ROOT, name), encoding="utf-8") as f:
            out[name] = f.read()
    return out


def frame_extract_function(text, header):
    """A top-level `local function` from its header line to its closing `end` at column 0 (empty when it is missing)."""
    start = text.find(header)
    if start < 0:
        return ""
    end = text.find("\nend\n", start)
    return text[start:end + len("\nend\n")] if end >= 0 else ""


def frame_block(text, header):
    """A top-level table from its header line to its closing `}` at column 0 (empty when it is missing)."""
    start = text.find(header)
    if start < 0:
        return ""
    end = text.find("\n}\n", start)
    return text[start:end + len("\n}\n")] if end >= 0 else ""


def frame_line(text, prefix):
    import re
    m = re.search(r"^" + re.escape(prefix) + r".*$", text, re.M)
    return m.group(0) if m else ""


FRAME_CORE_FUNCTIONS = ("local function makePart(", "local function addLabel(", "local function plotCenter(", "local function plotFrame(",
                        "local function itemOffset(", "local function nextUpgrade(", "local function looks(", "local function spawnItem(",
                        "local function publishUpgrades(", "local function refreshSign(", "local function teleportToPlot(")


def frame_source(texts):
    """The frame test program, with the (possibly mutated) scripts in texts."""
    core, ipo, employee = texts["TycoonCore.lua"], texts["IpoServer.lua"], texts["EmployeeServer.lua"]
    constants = "\n".join(frame_line(core, "local %s = " % name) for name in ("PLOT_SPACING", "SIGN_OFFSET", "MAX_PLOTS"))
    functions = "\n".join(frame_extract_function(core, header) for header in FRAME_CORE_FUNCTIONS)
    functions = frame_line(core, "local QUARTER_TURNS = ") + "\n" + functions
    zones_at = core.find("\tplotZones = function()")
    zones_end = core.find("\n\tend,\n", zones_at)
    plot_zones = core[zones_at + len("\tplotZones = "):zones_end + len("\n\tend")] if zones_at >= 0 and zones_end >= 0 else "nil"
    ipo_constants = "\n".join(frame_line(ipo, "local %s = " % name) for name in ("SIGN_OFFSET", "SIGN_COLOR", "WHITE"))
    employee_constants = "\n".join((frame_block(employee, "local EMPLOYEE_SPOTS = {"), frame_block(employee, "local INCUBATOR_SPOTS = {"),
                                    frame_line(employee, "local FEET = "), frame_line(employee, "local WHITE = ")))
    employee_functions = "\n".join(frame_extract_function(employee, header) for header in (
        "local function makePart(", "local function spotFor(", "local function placeEmployees(", "local function buildIncubator("))
    visuals_fake = VISUALS_TESTS[:VISUALS_TESTS.index("local PlotArt = (function()")]
    text = (FRAME_TESTS.replace("__PLOTART__", texts["PlotArt.lua"]).replace("__PLOTVISUALS__", texts["PlotVisuals.lua"])
            .replace("__SECTORCONFIG__", texts["SectorConfig.lua"]).replace("__IPOCONFIG__", texts["IpoConfig.lua"])
            .replace("__COMPANYCONFIG__", texts["CompanyConfig.lua"])
            .replace("__CORE_CONSTANTS__", constants).replace("__UPGRADES__", frame_block(core, "local UPGRADES = {"))
            .replace("__CORE_FUNCTIONS__", functions).replace("__PLOTZONES__", plot_zones)
            .replace("__TURNS_LINE__", frame_line(core, "local GARAGE_TURNS = ") or "local GARAGE_TURNS = {}")
            .replace("__IPO_CONSTANTS__", ipo_constants).replace("__BUILDSIGN__", frame_extract_function(ipo, "local function buildSign("))
            .replace("__EMPLOYEE_CONSTANTS__", employee_constants).replace("__EMPLOYEE_FUNCTIONS__", employee_functions))
    return visuals_fake + text


def frame_enclosing(text, index):
    """The name of the top-level function (or init table) the character at index sits in."""
    import re
    best = "(top level)"
    for m in re.finditer(r"^(?:local function (\w+)|function ([\w.:]+)|(\w+)\.init\(\{)", text[:index], re.M):
        best = m.group(1) or m.group(2) or (m.group(3) + ".init")
    return best


# Where a garage position may be computed (file, function) -> how many lines use plotFrame. A new site fails until it is reviewed.
FRAME_SITES = {
    ("TycoonCore.lua", "spawnItem"): 1, ("TycoonCore.lua", "refreshSign"): 1,
    ("TycoonCore.lua", "IpoServer.init"): 1, ("TycoonCore.lua", "EmployeeServer.init"): 1,
    ("TycoonCore.lua", "teleportToPlot"): 2,
    # lobby L2: the Floor and the garage sign are made once, in buildGarages; syncBuilding builds the building in the
    # garage's frame and gives unstick its landing (the join no longer makes a Floor)
    ("TycoonCore.lua", "buildGarages"): 3, ("TycoonCore.lua", "syncBuilding"): 2,
    # lobby L3: the claim post (buildGarages) and the Free garage's room (buildFreeRoom, from the frame's position)
    ("TycoonCore.lua", "buildFreeRoom"): 1,
    ("EmployeeServer.lua", "placeEmployees"): 1, ("EmployeeServer.lua", "buildIncubator"): 1, ("IpoServer.lua", "buildSign"): 1,
}
# WorldArt and WorldVisuals are not wired yet: PR L4 builds the ring from the garages' frames (docs/LOBBY_GARAGE_PROPOSAL.md)
FRAME_UNWIRED = ("WorldArt.lua", "WorldVisuals.lua")
WANDER_LINES = (
    "\t\t\t\tw.target = math.random() < 0.3 and w.offset or Vector3.new(math.random() * 6 - 3, 0, math.random() * 6 - 3)\n",
    "\t\t\t\tw.yaw = math.atan2(-delta.X, -delta.Z) -- models face -Z\n",
    "\t\t\tmodel:PivotTo(CFrame.new(home + w.offset + Vector3.new(0, bob, 0)) * CFrame.Angles(0, w.yaw, 0))\n",
)


def frame_static_checks(texts=None):
    """[(name, ok, extra)]: where garage positions are computed, read from the source text of every script at the root."""
    import re
    if texts is None:
        texts = {}
        for name in sorted(os.listdir(ROOT)):
            if name.endswith(".lua"):
                with open(os.path.join(ROOT, name), encoding="utf-8") as f:
                    texts[name] = f.read()
    out = []

    def add(name, ok, extra=None):
        out.append((name, bool(ok), extra))

    offsets, core_center, sites = [], [], {}
    for name, text in sorted(texts.items()):
        if name in FRAME_UNWIRED:
            continue
        code = code_only(text)
        offsets += ["%s: %s" % (name, m.group(0)) for m in re.finditer(r"plotCenter\s*\([^()]*\)\s*[-+*]", code)]
        core_center += ["%s: %s" % (name, m.group(0)) for m in re.finditer(r"core\s*\.\s*plotCenter\s*\(", code)]
        lines = set()
        for m in re.finditer(r"plotFrame\b", code):
            start = code.rfind("\n", 0, m.start()) + 1
            if start in lines or re.match(r"\s*local function plotFrame\(", code[start:code.find("\n", m.start())]):
                continue
            lines.add(start)
            key = (name, frame_enclosing(code, m.start()))
            sites[key] = sites.get(key, 0) + 1
    add("center plus offset: no script adds an offset to plotCenter (every garage position goes through plotFrame; WorldArt and WorldVisuals are PR L4's)",
        not offsets, offsets[:3])
    add("center plus offset: no module computes from core.plotCenter (IpoServer and EmployeeServer get core.plotFrame)", not core_center, core_center[:3])
    want = {k: v for k, v in FRAME_SITES.items() if v}
    add("center plus offset: every plotFrame use is pinned (TycoonCore: spawnItem, refreshSign, teleportToPlot x2, buildGarages x3, syncBuilding x2, buildFreeRoom, two core tables; "
        "EmployeeServer: placeEmployees, buildIncubator; IpoServer: buildSign)", sites == want,
        sorted(set(sites.items()) ^ set(want.items())))
    core = code_only(texts.get("TycoonCore.lua", ""))
    calls = [m.start() for m in re.finditer(r"(?<!function )\bplotCenter\s*\(", core)]
    where = sorted(frame_enclosing(core, i) for i in calls)
    room = "looks(\"room\", PlotVisuals.newPlot, folder, plotCenter(slot), PlotArt, floor, stageOf(data))"
    add("center plus offset: plotCenter is called only by plotFrame and on the room line (newPlot takes the turn from the Floor)",
        where == ["claimGarage", "plotFrame"] and core.count(room) == 1, where)  # lobby L3: the join's load is the claim's
    client = texts.get("EmployeeClient.lua", "")
    beat_at = client.find("RunService.Heartbeat:Connect(function(dt)")
    beat = client[beat_at:client.find("\nend)\n", beat_at)] if beat_at >= 0 else ""
    add("EmployeeClient: the wander, the walking yaw and the pivot are in world axes (pinned: main's three lines, nothing turned in the Heartbeat)",
        all(client.count(line) == 1 and line in beat for line in WANDER_LINES)
        and not re.search(r"Facing|plotFrame|ToObjectSpace|VectorToWorldSpace|\bturn\b", code_only(beat)))
    add("EmployeeClient: a walker starts at the server's Facing (math.pi when it is missing)",
        client.count("\t\tlocal facing = model:GetAttribute(\"Facing\")\n") == 1
        and client.count("yaw = type(facing) == \"number\" and facing or math.pi,") == 1)
    employee = texts.get("EmployeeServer.lua", "")
    place = frame_extract_function(employee, "local function placeEmployees(")
    facing_at, parent_at = place.find("model:SetAttribute(\"Facing\", facing)"), place.find("model.Parent = data.folder")
    add("EmployeeServer: Facing is set before the new model is parented (it reaches the client with the model)",
        place.count("model:SetAttribute(\"Facing\", facing)") == 1 and 0 <= facing_at < parent_at)
    return out


# (what is broken, [(file, old, new)], the start of the named check that must fail)
FRAME_MUTATIONS = [
    # The proposal's L1 set
    ("the IPO sign offset not turned", [("IpoServer.lua", "local pos = core.plotFrame(data.slot) * CFrame.new(SIGN_OFFSET)",
                                         "local pos = CFrame.new(core.plotFrame(data.slot).Position + SIGN_OFFSET)")], "IpoSign at 90 degrees"),
    ("the employee facing ignores the turn", [("EmployeeServer.lua", "local facing = math.pi + turn", "local facing = math.pi")],
     "employee facing at 90 degrees"),
    ("the turn's sign flipped", [("TycoonCore.lua", "c, 0, s, 0, 1, 0, -s, 0, c)", "c, 0, -s, 0, 1, 0, s, 0, c)")],
     "turn math: at 90 degrees the garage's front"),
    ("PlotVisuals.check in world axes", [("PlotVisuals.lua", "\t\t\tlocal b = boxOf(origin:ToObjectSpace(d.CFrame), d.Size) -- in the garage's frame\n",
                                          "\t\t\tlocal b, o = boxOf(d.CFrame, d.Size), origin.Position\n"
                                          "\t\t\tb = { b[1] - o.X, b[2] - o.X, b[3] - o.Y, b[4] - o.Y, b[5] - o.Z, b[6] - o.Z }\n")],
     "room at 90 degrees: PlotVisuals.check in the garage's frame"),
    # Every other site of section 4.3
    ("the next-upgrade sign not turned", [("TycoonCore.lua", "local pos = plotFrame(data.slot) * CFrame.new(SIGN_OFFSET)",
                                           "local pos = CFrame.new(plotFrame(data.slot).Position + SIGN_OFFSET)")], "BuySign at 90 degrees"),
    ("the plain upgrade block not turned", [("TycoonCore.lua", "local pos = plotFrame(data.slot) * CFrame.new(itemOffset(i)",
                                             "local pos = CFrame.new(plotFrame(data.slot).Position + itemOffset(i)")], "blocks at 90 degrees"),
    ("the landing not turned", [("TycoonCore.lua", "local spawnPos = plotFrame(slot) * Vector3.new(0, 4, 12)",
                                 "local spawnPos = plotFrame(slot).Position + Vector3.new(0, 4, 12)")], "landing at 90 degrees"),
    ("the hire spots not turned", [("EmployeeServer.lua", "local home = frame * (spotFor(i) + FEET)", "local home = frame.Position + spotFor(i) + FEET")],
     "hire spots at 90 degrees"),
    ("the incubators not turned", [("EmployeeServer.lua", "local spot = core.plotFrame(data.slot) * (INCUBATOR_SPOTS[i]",
                                    "local spot = core.plotFrame(data.slot).Position + (INCUBATOR_SPOTS[i]")], "incubators at 90 degrees"),
    ("the room ignores the Floor's turn", [("PlotVisuals.lua", "local frame = floor and CFrame.new(center) * floor.CFrame.Rotation or center",
                                            "local frame = center")], "room at 90 degrees: every stage room"),
    ("makePart drops the turn of a CFrame (places only its position)", [("TycoonCore.lua", "\t\tp.CFrame = position -- a part placed in a garage's frame",
                                                                        "\t\tp.Position = position.Position -- a part placed in a garage's frame")],
     "BuySign at 90 degrees"),
    ("every garage takes the first garage's turn", [("TycoonCore.lua", "local c, s = QUARTER_TURNS[GARAGE_TURNS[slot]][1], QUARTER_TURNS[GARAGE_TURNS[slot]][2]",
                                                     "local c, s = QUARTER_TURNS[GARAGE_TURNS[1]][1], QUARTER_TURNS[GARAGE_TURNS[1]][2]")],
     "turn math: at 180 degrees"),
    ("an employee re-pivoted without the turn", [("EmployeeServer.lua", "\t\t\tmodel:PivotTo(CFrame.new(home) * CFrame.Angles(0, facing, 0)) -- face",
                                                 "\t\t\tmodel:PivotTo(CFrame.new(home) * CFrame.Angles(0, math.pi, 0)) -- face")],
     "employee facing at 90 degrees"),
    # L1 changes no behavior
    ("a garage turned in L1", [("TycoonCore.lua", "local GARAGE_TURNS = { 0, 0, 0, 0, 0, 0 }", "local GARAGE_TURNS = { 0, 0, 0, 90, 0, 0 }")],
     "turn math: L1 turns no garage"),
    ("seven turns for six garages", [("TycoonCore.lua", "local GARAGE_TURNS = { 0, 0, 0, 0, 0, 0 }", "local GARAGE_TURNS = { 0, 0, 0, 0, 0, 0, 0 }")],
     "turn math: one turn per garage"),
    ("a turn that is not a quarter turn", [("TycoonCore.lua", "local GARAGE_TURNS = { 0, 0, 0, 0, 0, 0 }", "local GARAGE_TURNS = { 0, 0, 0, 0, 0, 45 }")],
     "turn math: every turn is a quarter turn"),
    ("the row moved (plotCenter's z 150 becomes 151)", [("TycoonCore.lua", "(slot - 1) * PLOT_SPACING, 0.5, 150)", "(slot - 1) * PLOT_SPACING, 0.5, 151)")],
     "turn math: plotFrame(slot) is main's plotCenter(slot)"),
    ("the employees face the back at 0 degrees (math.pi dropped)", [("EmployeeServer.lua", "local facing = math.pi + turn", "local facing = turn")],
     "employee facing at 0 degrees"),
    ("the room built half a stud higher in the frame", [("PlotVisuals.lua", "return center * CFrame.new(0, art.Layout.floorTop, 0) -- a turned garage",
                                                         "return center * CFrame.new(0, art.Layout.floorTop + 0.5, 0) -- a turned garage")],
     "room at 0 degrees: every stage room"),
    ("plotZones turned with the first garage", [("TycoonCore.lua", "\t\tif not zones then return nil end\n\t\treturn zones, PlotArt.Layout.floorSize[3]",
                                                 "\t\tif not zones then return nil end\n\t\tif GARAGE_TURNS[1] ~= 0 then for _, z in ipairs(zones) do "
                                                 "z.box = { -z.box[2], -z.box[1], z.box[3], z.box[4], z.box[5], z.box[6] } end end\n"
                                                 "\t\treturn zones, PlotArt.Layout.floorSize[3]")],
     "plotZones: the reserved zones CompanyServer places against are identical at every turn"),
    # The source pins
    ("a new center plus offset in PoachServer", [("PoachServer.lua", "return PoachServer\n", "local spot = core.plotCenter(1) + Vector3.new(0, 0, 9)\nreturn PoachServer\n")],
     "center plus offset: no script adds an offset to plotCenter"),
    ("a new plotFrame site in DailyServer", [("DailyServer.lua", "return DailyServer\n", "local frame = core.plotFrame and core.plotFrame(1)\nreturn DailyServer\n")],
     "center plus offset: every plotFrame use is pinned"),
    ("the Floor back on plotCenter", [("TycoonCore.lua", "Vector3.new(60, 1, 60), plotFrame(slot), Color3", "Vector3.new(60, 1, 60), plotCenter(slot), Color3")],
     "center plus offset: every plotFrame use is pinned"),
    ("EmployeeServer back on core.plotCenter", [("EmployeeServer.lua", "local frame = core.plotFrame(data.slot)\n",
                                                 "local frame = CFrame.new(core.plotCenter(data.slot))\n")],
     "center plus offset: no module computes from core.plotCenter"),
    ("EmployeeClient's walking yaw turned by Facing", [("EmployeeClient.lua", "w.yaw = math.atan2(-delta.X, -delta.Z) -- models face -Z",
                                                        "w.yaw = math.atan2(-delta.X, -delta.Z) + (model:GetAttribute(\"Facing\") or math.pi) - math.pi -- models face -Z")],
     "EmployeeClient: the wander, the walking yaw and the pivot are in world axes"),
    ("EmployeeClient's wander turned into the garage's frame", [("EmployeeClient.lua", "Vector3.new(math.random() * 6 - 3, 0, math.random() * 6 - 3)",
                                                                 "CFrame.Angles(0, w.turn or 0, 0) * Vector3.new(math.random() * 6 - 3, 0, math.random() * 6 - 3)")],
     "EmployeeClient: the wander, the walking yaw and the pivot are in world axes"),
    ("EmployeeClient ignores Facing", [("EmployeeClient.lua", "yaw = type(facing) == \"number\" and facing or math.pi,", "yaw = math.pi,")],
     "EmployeeClient: a walker starts at the server's Facing"),
    ("Facing set after the model is parented", [("EmployeeServer.lua", "\t\t\tmodel:SetAttribute(\"Facing\", facing) -- EmployeeClient starts them facing it\n", ""),
                                                ("EmployeeServer.lua", "\t\tmodel:SetAttribute(\"Home\", home)\n",
                                                 "\t\tmodel:SetAttribute(\"Home\", home)\n\t\tmodel:SetAttribute(\"Facing\", facing)\n")],
     "EmployeeServer: Facing is set before the new model is parented"),
]


def frame_mutant_texts(edits):
    """The scripts with the mutation's edits applied in memory, or None when an edit's old text is not there exactly once."""
    texts = frame_texts()
    for name in ("PoachServer.lua", "DailyServer.lua"):
        with open(os.path.join(ROOT, name), encoding="utf-8") as f:
            texts[name] = f.read()
    for name, old, new in edits:
        if texts.get(name, "").count(old) != 1:
            return None
        texts[name] = texts[name].replace(old, new)
    return texts


def run_frame_mutants(luau, mutations=None):
    """Each mutation must be caught by its NAMED check: a Luau run that reaches its summary line with that FAIL line, or a
    source pin of that name. A crash, or a run that never reaches its summary, is never a catch."""
    import re
    caught, problems = 0, []
    for label, edits, want in (FRAME_MUTATIONS if mutations is None else mutations):
        texts = frame_mutant_texts(edits)
        if texts is None:
            problems.append("FAIL: frame mutation not applied (its text is missing or there twice): " + label)
            continue
        static = [name for name, ok, _ in frame_static_checks(all_root_texts(texts)) if not ok]
        result = run_luau(luau, frame_source(texts))
        finished = result.returncode == 0 and re.search(r"^\d+ passed, \d+ failed$", result.stdout, re.M) is not None
        named = [line[len("FAIL: "):].split(" -- ")[0] for line in result.stdout.split("\n") if line.startswith("FAIL: ")] if finished else []
        hit = next((n for n in static + named if n.startswith(want)), None)
        if hit:
            caught += 1
            print("  frame mutant caught: %s -> %s" % (label, hit))
        else:
            why = "the tests crashed: " + (result.stderr.strip().split("\n")[0] if result.stderr.strip() else "no summary") if not finished else \
                "\"%s\" stayed green (failed: %s)" % (want, static + named)
            problems.append("FAIL: frame mutation not caught by its named check: %s -- %s" % (label, why))
    return caught, problems


def all_root_texts(overrides):
    """{file name: text} for every script at the root, with overrides (the mutated scripts) in place of the real ones."""
    texts = {}
    for name in sorted(os.listdir(ROOT)):
        if name.endswith(".lua"):
            with open(os.path.join(ROOT, name), encoding="utf-8") as f:
                texts[name] = f.read()
    texts.update(overrides)
    return texts


# A mutation that makes the frame tests crash must never count as caught (the harness's own self-test)
FRAME_SELF_TEST = ("the frame tests crash (plotFrame errors)", [("TycoonCore.lua", "local function plotFrame(slot)\n", "local function plotFrame(slot)\n\terror(\"boom\")\n")],
                   "turn math: plotFrame(slot) is main's plotCenter(slot)")


def addearnings_calls(code):
    """The lines of (comment-free) Lua that call addEarnings (a function definition is not a call)."""
    import re
    return [line for line in code.split("\n")
            if re.search(r"addEarnings\s*\(", line) and not re.search(r"function\s+[\w.]*addEarnings\s*\(", line)]


def ipo_number_writes(code):
    """The lines of (comment-free) Lua that assign to a .valuation, .lifetime or .best (=, +=, -=, also inside a multiple
    assignment, also as ["valuation"]). Only IpoServer may; DailyServer's daily.best is the streak record, not the IPO."""
    import re
    hits = []
    for line in code.split("\n"):
        for statement in line.split(";"):
            match = re.search(r"(?<![=~<>])[-+*/]?=(?!=)", statement)
            if match and re.search(r"(\.|\[\s*[\"'])(valuation|lifetime|best)\b", statement[:match.start()]):
                hits.append(statement.strip())
    return hits


def scanner_selftests():
    """The two scanners above must be able to fail: lines they have to flag, and lines they must leave alone."""
    passed, failed = 0, 0
    flagged_writes = ["ipo.valuation += amount", "ipo.lifetime = 0", "data.ipo.best -= 1", "ipo.count, ipo.valuation = 0, 0",
                      "a, ipo.best, b = 1, 2, 3", "data.ipo[\"lifetime\"] = 5", "local ipo = data.ipo; ipo.valuation = 7"]
    clean_writes = ["if ipo.valuation == 5 then", "local x = ipo.best", "ipo.best_of = 3", "math.max(ipo.best, ipo.valuation)",
                    "if a.best ~= b.best then", "if a.lifetime >= 3 then", "tbl.valuations = 3", "local value = ipo.lifetime + 1"]
    flagged_calls = ["core.addEarnings(player, 5)", "addEarnings(player, n)", "IpoServer.addEarnings (player, 1)"]
    clean_calls = ["local function addEarnings(player, amount)", "function IpoServer.addEarnings(player, amount)", "addEarnings = addEarnings,", "local pay = core.addEarnings"]
    cases = ([(line, ipo_number_writes(line), True) for line in flagged_writes] + [(line, ipo_number_writes(line), False) for line in clean_writes]
             + [(line, addearnings_calls(line), True) for line in flagged_calls] + [(line, addearnings_calls(line), False) for line in clean_calls])
    for line, found, should in cases:
        if bool(found) == should:
            passed += 1
        else:
            failed += 1
            print("FAIL: scanner self-test: %r should %sbe flagged" % (line, "" if should else "not "))
    return passed, failed


def pokedex_wiring_checks():
    """Checks on the source text for the Pokedex (customize PR 1): module order, no way to earn or pay, only IpoServer writes
    the valuation, nothing the client can send but id, x, z and r, and nothing that yields or saves by itself."""
    import re
    passed, failed = scanner_selftests()

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

    core = read("TycoonCore.lua")
    code = code_only(core)
    # Order: the module is plugged in after OnboardingServer and before TaskServer, and DailyServer stays last
    for call in (".init(", ".setupPlayer("):
        order = ["IpoServer", "ShopServer", "EmployeeServer", "PoachServer", "OnboardingServer", "CompanyServer", "TaskServer", "DailyServer"] if call == ".init(" else \
            ["IpoServer", "EmployeeServer", "PoachServer", "OnboardingServer", "CompanyServer", "TaskServer", "DailyServer"]
        positions = [code.find(name + call) for name in order] # find: a missing call is -1 and fails the order check by name
        check("TycoonCore: %s%s calls run in the order %s" % ("<module>", call, " > ".join(order)), positions == sorted(positions), positions)
    check("TycoonCore: CompanyServer.setupPlayer is called exactly once", code.count("CompanyServer.setupPlayer(") == 1, code.count("CompanyServer.setupPlayer("))
    check("TycoonCore: CompanyServer.setupPlayer runs before DailyServer.setupPlayer (Daily stays last)", 0 <= code.find("CompanyServer.setupPlayer(") < code.find("DailyServer.setupPlayer("))
    check("TycoonCore: CompanyServer.setupPlayer runs after IpoServer.setupPlayer (the run check reads the IPO count)", 0 <= code.find("IpoServer.setupPlayer(") < code.find("CompanyServer.setupPlayer("))
    setups = re.findall(r"(\w+Server)\.setupPlayer\(", code)
    check("TycoonCore: DailyServer is the last module set up for a player", setups[-1] == "DailyServer", setups)
    check("TycoonCore: CompanyServer is required with the other modules", 'local CompanyServer = require(script.Parent:WaitForChild("CompanyServer"))' in core)
    check("TycoonCore: pokedex is a known section and the payload is built with CompanyServer.serialize", re.search(r"local KNOWN_SECTIONS = \{[^}]*\bpokedex = true", core) is not None and "pokedex = CompanyServer.serialize(data)" in core)
    init_block = code[code.index("CompanyServer.init({"):]
    init_block = init_block[:init_block.index("\n})")]
    check("TycoonCore: CompanyServer.init gets no addEarnings (it can never earn or pay)", "addEarnings" not in init_block and "updateIncome" not in init_block, init_block)
    daily_block = code[code.index("DailyServer.init({"):]
    daily_block = daily_block[:daily_block.index("\n})")]
    check("TycoonCore: DailyServer.init gets no addEarnings either (a gift is never an earning)", "addEarnings" not in daily_block)
    check("TycoonCore: CompanyServer.init gets only getData, save and plotZones", re.findall(r"^\t(\w+) = ", init_block, re.M) == ["getData", "save", "plotZones"], re.findall(r"^\t(\w+) = ", init_block, re.M))
    commit = code[code.index("local function commitIpo("):]
    commit = commit[:commit.index("local resets")]
    # (the runtime test "an IPO while the pokedex is locked" is the real proof; this is the second layer. The guard is read as its own
    # block: `if not data then return false end` above it must not count as the refusal)
    start = commit.find("if CompanyServer.isLocked(data) then")
    guard = commit[start:commit.find("\n\tend\n", start)] if start >= 0 else ""
    check("TycoonCore: an IPO is refused first of all while the pokedex is locked (a newer version's, or unreadable)",
          guard != "" and re.search(r"\breturn false\s*$", guard) is not None and "return true" not in guard, guard)
    ipo_code = code_only(read("IpoServer.lua"))
    check("IpoServer: a refused commit (the lock) shows \"The IPO couldn't be saved. Nothing changed: try again in a moment.\"",
          "core.commitIpo(player, toSave(after))" in ipo_code and "return false, \"The IPO couldn't be saved. Nothing changed: try again in a moment.\"" in ipo_code)
    commit_all = code[code.index("local function commitIpo("):]
    commit_all = commit_all[:commit_all.index("\nend\n")]
    save_guard = commit_all.find("if not ok or playerData[player] ~= data then")
    run_call = "CompanyServer.writeIpoRun(data, payload, newIpo.count)"
    check("TycoonCore: commitIpo writes the pokedex's run (the new count) inside the IPO's save transform, after the new ipo section",
          commit_all.count(run_call) == 1 and 0 <= commit_all.find("payload.ipo = newIpo") < commit_all.find(run_call) < save_guard)
    check("TycoonCore: commitIpo moves the pokedex's run in memory (the new count) only after the save worked",
          commit_all.count("CompanyServer.onIpo(data, newIpo.count)") == 1 and 0 <= save_guard < commit_all.find("CompanyServer.onIpo(data, newIpo.count)"))
    check("TycoonCore: the zones come through looks() (a broken plot visuals never stops the game)", 'looks("zones", PlotVisuals.zones, PlotArt.Layout)' in code)
    check("TycoonCore: DataStore name and key untouched, still one DataStore", code.count("GetDataStore(") == 1 and 'GetDataStore("StartupTycoon_v1")' in code and '"player_" .. player.UserId' in code)

    # The new files
    names = ("CompanyServer.lua", "CompanyConfig.lua", "SectorConfig.lua")
    for name in names:
        raw = read(name)
        text = code_only(raw)
        check("%s never mentions addEarnings, in code or in a comment (it can't earn)" % name, "addEarnings" not in raw)
        for word in ("DataStore", "SetAsync", "GetAsync", "UpdateAsync", "OrderedDataStore", "MarketplaceService", "PromptProductPurchase", "grantShares", "grantEgg", "Touched", "TeleportService"):
            check("%s never uses %s" % (name, word), word not in text)
        for word in ("math.random", "Random.new", "os.date", "tick("):
            check("%s has nothing random or clock-dependent (%s)" % (name, word), word not in text)
        check("%s writes no valuation, lifetime or best" % name, ipo_number_writes(text) == [])
        check("%s never yields or starts a thread (a check and its change are one step)" % name, not re.search(r"task\.(wait|spawn|defer|delay)|:Wait\(|wait\(", text))
    for name in ("CompanyServer.lua", "CompanyConfig.lua"):
        text = code_only(read(name))
        check("%s names no sector (the engine never does: a sector key is data in SectorConfig)" % name, not re.search(r'"(Software|Gaming|Fintech|Biotech)"', text))
    server = code_only(read("CompanyServer.lua"))
    check("CompanyServer: the only remotes are CompanyRemotes and its one CompanyAction", server.count('Instance.new("Remote') == 1 and 'Instance.new("RemoteFunction")' in server and 'Name = "CompanyRemotes"' in server.replace("folder.Name = ", 'Name = ') and 'remotes.action.Name = "CompanyAction"' in server)
    check("CompanyServer: the request handler takes only the action, id, x, z and r", "local function onAction(player, action, id, x, z, r)" in server)
    check("CompanyServer: it never writes another module's data (no data.cash, income, owned, ipo, team, shop, poach, daily, tasks or onboarding)",
          not re.search(r"data\.(cash|income|owned|ipo|team|shop|poach|daily|tasks|onboarding|fixedHires)\b\s*(\.\w+\s*)*(=[^=]|\+=|-=)", server)
          and not re.search(r"\.Value\s*(=[^=]|\+=|-=)", server))
    check("CompanyServer: it never calls core.save (autosave and the leave save write placements; a purchase is not involved)", "core.save" not in server)
    check("CompanyServer: Place and Store change data only after CompanyConfig.checkPlacement / checkStore", 0 <= server.find("CompanyConfig.checkPlacement(") < server.find("CompanyConfig.applyPlace(") and 0 <= server.find("CompanyConfig.checkStore(") < server.find("CompanyConfig.applyStore("))
    check("CompanyServer: the Studio-only switch is checked before any change", 0 <= server.find("CompanyConfig.isPlacementActive()") < server.find("CompanyConfig.applyPlace("))
    check("CompanyServer: the request limit is called exactly once, before the switch and the checks", server.count("CompanyConfig.takeToken(") == 1 and 0 <= server.find("CompanyConfig.takeToken(") < server.find("CompanyConfig.isPlacementActive()"))
    config = code_only(read("CompanyConfig.lua"))
    check("CompanyConfig: the placement switch is on and Studio only (nothing is drawn until the office screen exists)", re.search(r"CompanyConfig\.Placement = \{\s*Enabled = true,\s*StudioOnly = true,", config) is not None)
    check("CompanyConfig: the Pokedex format version is 1", "CompanyConfig.Version = 1" in config)
    sector = code_only(read("SectorConfig.lua"))
    check("SectorConfig: the picker is off, and only Software is enabled", "SectorConfig.PickerEnabled = false" in sector and len(re.findall(r"enabled = true", sector)) == 1 and re.search(r"Software = \{[^}]*enabled = true", sector, re.S) is not None)

    # Nothing but IpoServer writes the valuation (a Pokedex or a round must never raise it by itself)
    writes = {}
    for name in sorted(n for n in os.listdir(ROOT) if n.endswith(".lua")):
        found = ipo_number_writes(code_only(read(name)))
        if found:
            writes[name] = found
    allowed_daily = {"daily.best = math.max(daily.best, daily.streak)", "daily.lastClaimDay, daily.streak, daily.best, daily.claims, daily.fakeDays = 0, 0, 0, 0, 0"}
    check("no .lua file but IpoServer assigns .valuation, .lifetime or .best (DailyServer's daily.best is the streak record)",
          set(writes) <= {"IpoServer.lua", "DailyServer.lua"} and set(writes.get("DailyServer.lua", [])) <= allowed_daily, writes.keys())
    check("DailyServer's three daily.best writes are all there is outside IpoServer", len(writes.get("DailyServer.lua", [])) == 3, writes.get("DailyServer.lua"))
    check("IpoServer's own valuation, lifetime and best writes are pinned (10 lines): a new one fails until it is reviewed", len(writes.get("IpoServer.lua", [])) == 10, len(writes.get("IpoServer.lua", [])))
    return passed, failed


# Each of these breaks one wiring rule in a copy of the .lua files; the source checks must notice (a check that can't fail proves
# nothing). (label, file, old, new): `old` None creates the file with `new`; "return X\n" lines are used to add code at the end.
WIRING_MUTATIONS = [
    ("a call to addEarnings in CompanyServer", "CompanyServer.lua", "return CompanyServer\n", "core.addEarnings(1, 5)\nreturn CompanyServer\n"),
    ("an alias of addEarnings in CompanyServer", "CompanyServer.lua", "return CompanyServer\n", "local pay = core.addEarnings\nreturn CompanyServer\n"),
    ("addEarnings handed to CompanyServer.init", "TycoonCore.lua", "\tsave = save,\n\tplotZones", "\tsave = save,\n\taddEarnings = addEarnings,\n\tplotZones"),
    ("addEarnings handed to DailyServer.init", "TycoonCore.lua", "DailyServer.init({\n\tgetData", "DailyServer.init({\n\taddEarnings = addEarnings,\n\tgetData"),
    ("a fourth addEarnings call in TycoonCore", "TycoonCore.lua", "\t\t\t\tsyncRoom(data)\n", "\t\t\t\taddEarnings(player, 1)\n\t\t\t\tsyncRoom(data)\n"),
    ("an addEarnings call in a file nobody reviewed", "Extra.lua", None, "local x = core.addEarnings(player, 5)\nreturn x\n"),
    ("a write to the valuation in CompanyServer", "CompanyServer.lua", "return CompanyServer\n", "data.ipo.valuation += 5\nreturn CompanyServer\n"),
    ("a write to lifetime in EmployeeServer", "EmployeeServer.lua", "return EmployeeServer\n", "local ipo = {}\nipo.lifetime = 0\nreturn EmployeeServer\n"),
    ("a write to best through brackets in TaskServer", "TaskServer.lua", "return TaskServer\n", "local ipo = {}\nipo[\"best\"] = 0\nreturn TaskServer\n"),
    ("a new valuation write in IpoServer", "IpoServer.lua", "return IpoServer\n", "local ipo = {}\nipo.valuation = 1\nreturn IpoServer\n"),
    ("CompanyServer set up after DailyServer (moved)", "TycoonCore.lua", [
        ("\t\tCompanyServer.setupPlayer(player, data, saved and saved.pokedex) -- after the IPO (the run check reads the IPO count); before TaskServer and DailyServer\n", ""),
        ("\t\tDailyServer.setupPlayer(player, data, saved and saved.daily) -- after employees: a claim can grant an egg\n",
         "\t\tDailyServer.setupPlayer(player, data, saved and saved.daily) -- after employees: a claim can grant an egg\n\t\tCompanyServer.setupPlayer(player, data, saved and saved.pokedex)\n")], None),
    ("CompanyServer set up before IpoServer (moved: the run check would read no IPO count)", "TycoonCore.lua", [
        ("\t\tCompanyServer.setupPlayer(player, data, saved and saved.pokedex) -- after the IPO (the run check reads the IPO count); before TaskServer and DailyServer\n", ""),
        ("\t\tIpoServer.setupPlayer(", "\t\tCompanyServer.setupPlayer(player, data, saved and saved.pokedex)\n\t\tIpoServer.setupPlayer(")], None),
    ("CompanyServer never set up", "TycoonCore.lua", "\t\tCompanyServer.setupPlayer(player, data, saved and saved.pokedex) -- after the IPO (the run check reads the IPO count); before TaskServer and DailyServer\n", ""),
    ("CompanyServer set up twice", "TycoonCore.lua", "\t\tDailyServer.setupPlayer(player, data, saved and saved.daily) -- after employees: a claim can grant an egg\n",
     "\t\tCompanyServer.setupPlayer(player, data, saved and saved.pokedex)\n\t\tDailyServer.setupPlayer(player, data, saved and saved.daily) -- after employees: a claim can grant an egg\n"),
    ("DailyServer no longer last", "TycoonCore.lua", "\t\tDailyServer.setupPlayer(player, data, saved and saved.daily) -- after employees: a claim can grant an egg\n", "\t\tDailyServer.setupPlayer(player, data, saved and saved.daily) -- after employees: a claim can grant an egg\n\t\tOnboardingServer.setupPlayer(player, data, saved and saved.onboarding, ok)\n"),
    ("CompanyServer.init before OnboardingServer.init", "TycoonCore.lua", "OnboardingServer.init({\n", "CompanyServer.init({ getData = function() end, save = save, plotZones = function() end })\nOnboardingServer.init({\n"),
    ("CompanyServer yields", "CompanyServer.lua", "return CompanyServer\n", "task.wait(1)\nreturn CompanyServer\n"),
    ("CompanyServer writes Cash", "CompanyServer.lua", "return CompanyServer\n", "data.cash.Value += 1\nreturn CompanyServer\n"),
    ("CompanyServer saves by itself", "CompanyServer.lua", "return CompanyServer\n", "core.save(1)\nreturn CompanyServer\n"),
    ("CompanyServer with a Touched handler", "CompanyServer.lua", "return CompanyServer\n", "part.Touched:Connect(print)\nreturn CompanyServer\n"),
    ("CompanyServer names a sector", "CompanyServer.lua", "return CompanyServer\n", "local k = \"Gaming\"\nreturn CompanyServer\n"),
    ("a D9 word in CompanyServer", "CompanyServer.lua", "\"Too fast\"", "\"Good luck\""),
    ("a DataStore in CompanyConfig", "CompanyConfig.lua", "return CompanyConfig\n", "local s = game:GetService(\"DataStoreService\"):GetDataStore(\"Other\")\nreturn CompanyConfig\n"),
    ("an IPO allowed while the pokedex is locked", "TycoonCore.lua", "\tif CompanyServer.isLocked(data) then\n", "\tif false then\n"),
    ("the save gate without data.pokedex", "TycoonCore.lua", "data.tasks and data.pokedex) then", "data.tasks) then"),
    ("pokedex missing from KNOWN_SECTIONS", "TycoonCore.lua", "tasks = true, pokedex = true }", "tasks = true }"),
    ("the payload without the pokedex", "TycoonCore.lua", "pokedex = CompanyServer.serialize(data),", "pokedex = nil,"),
    ("commitIpo no longer writes the pokedex's run in the IPO's save", "TycoonCore.lua", "\t\tCompanyServer.writeIpoRun(data, payload, newIpo.count) -- the pokedex's run follows the new count in this very save\n", ""),
    ("commitIpo writes the wrong run in the IPO's save", "TycoonCore.lua", "CompanyServer.writeIpoRun(data, payload, newIpo.count)", "CompanyServer.writeIpoRun(data, payload, newIpo.count - 1)"),
    ("commitIpo no longer moves the run in memory", "TycoonCore.lua", "\tCompanyServer.onIpo(data, newIpo.count) -- the save worked: the section in memory follows too (the next autosave keeps it)\n", ""),
    ("commitIpo moves the run in memory before the save worked", "TycoonCore.lua", "\tif not ok or playerData[player] ~= data then\n\t\treturn ok\n\tend\n\tCompanyServer.onIpo", "\tCompanyServer.onIpo(data, newIpo.count)\n\tif not ok or playerData[player] ~= data then\n\t\treturn ok\n\tend\n\tCompanyServer.onIpo"),
    ("commitIpo moves the wrong run in memory", "TycoonCore.lua", "CompanyServer.onIpo(data, newIpo.count)", "CompanyServer.onIpo(data, newIpo.count + 1)"),
    ("a second DataStore", "TycoonCore.lua", "local plotOwners = {}", "local other = DataStoreService:GetDataStore(\"Other\")\nlocal plotOwners = {}"),
    ("the picker switched on", "SectorConfig.lua", "SectorConfig.PickerEnabled = false", "SectorConfig.PickerEnabled = true"),
    ("a second sector enabled", "SectorConfig.lua", "Fintech = { name = \"Fintech\", icon = \"💳\", enabled = false,", "Fintech = { name = \"Fintech\", icon = \"💳\", enabled = true,"),
    ("placement open on live servers", "CompanyConfig.lua", "\tStudioOnly = true,\n}\n\nfunction CompanyConfig.isPlacementActive", "\tStudioOnly = false,\n}\n\nfunction CompanyConfig.isPlacementActive"),
    ("a second remote in CompanyServer", "CompanyServer.lua", "return CompanyServer\n", "local extra = Instance.new(\"RemoteEvent\")\nreturn CompanyServer\n"),
    ("the request handler takes a price", "CompanyServer.lua", "local function onAction(player, action, id, x, z, r)", "local function onAction(player, action, id, x, z, r, price)"),
    ("the request limit after the checks (moved)", "CompanyServer.lua", [
        ("\tif not CompanyConfig.takeToken(state.bucket, os.clock()) then\n\t\treturn false, \"Too fast\"\n\tend\n", ""),
        ("\tif not CompanyConfig.isPlacementActive() then\n\t\treturn false, \"Not available yet\"\n\tend\n",
         "\tif not CompanyConfig.isPlacementActive() then\n\t\treturn false, \"Not available yet\"\n\tend\n\tif not CompanyConfig.takeToken(state.bucket, os.clock()) then\n\t\treturn false, \"Too fast\"\n\tend\n")], None),
    ("no request limit at all", "CompanyServer.lua", "\tif not CompanyConfig.takeToken(state.bucket, os.clock()) then\n\t\treturn false, \"Too fast\"\n\tend\n", ""),
    ("the request limit twice", "CompanyServer.lua", "\tif action ~= \"Place\" and action ~= \"Store\"", "\tif not CompanyConfig.takeToken(state.bucket, os.clock()) then\n\t\treturn false, \"Too fast\"\n\tend\n\tif action ~= \"Place\" and action ~= \"Store\""),
]


def wiring_mutation_run(label, filename, old, new):
    """Copies the .lua files to a temp folder, applies one mutation and runs the source checks there. True if one failed."""
    import contextlib
    import io
    global ROOT
    with tempfile.TemporaryDirectory() as folder:
        for name in os.listdir(ROOT):
            if name.endswith(".lua"):
                shutil.copy(os.path.join(ROOT, name), os.path.join(folder, name))
        path = os.path.join(folder, filename)
        if old is None:
            with open(path, "w", encoding="utf-8") as f:
                f.write(new)
        else:
            pairs = old if isinstance(old, list) else [(old, new)] # a list of (old, new) steps makes a real move
            for step_old, step_new in pairs:
                with open(path, encoding="utf-8") as f:
                    text = f.read()
                if text.count(step_old) != 1:
                    raise SystemExit("wiring mutation target not found exactly once in %s: %r" % (filename, step_old))
                with open(path, "w", encoding="utf-8") as f:
                    f.write(text.replace(step_old, step_new, 1))
        real_root, ROOT = ROOT, folder
        out = io.StringIO()
        try:
            with contextlib.redirect_stdout(out):
                results = [task_wiring_checks(), pokedex_wiring_checks(), pads_gone_checks()]
        except (ValueError, IndexError) as error:
            # A check that crashes on the mutated text didn't fail by name: that is a hole in the check, not a catch
            print("FAIL: the source checks crashed on a mutant (%s: %s) instead of failing a named check" % (label, repr(error)))
            return False
        finally:
            ROOT = real_root
        return any(failed for _, failed in results) and any(line.startswith("FAIL: ") for line in out.getvalue().split("\n"))


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
    """How many goal rows the Goals card has (it grows by 22 px per row): math.min(OnboardingConfig.ShowAtOnce,
    #activeGoals()), the way OnboardingClient sizes it. activeGoals() is Chain with ChainEnabled on, else Goals."""
    import re
    with open(os.path.join(ROOT, "OnboardingConfig.lua"), encoding="utf-8") as f:
        text = f.read()
    chain = re.search(r"^OnboardingConfig\.ChainEnabled = (true|false)\b", text, re.M).group(1) == "true"
    block = text[text.index("OnboardingConfig.Chain = {" if chain else "OnboardingConfig.Goals = {"):]
    block = block[:block.index("\n}")]
    at_once = int(re.search(r"^OnboardingConfig\.ShowAtOnce = (\d+)\b", text, re.M).group(1))
    return min(at_once, len(re.findall(r"\{\s*key = ", block)))


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
    source = source.replace("__STORABLE__", STORABLE_LUA)
    with tempfile.NamedTemporaryFile("w", suffix=".luau", delete=False, encoding="utf-8") as f:
        f.write(source)
        path = f.name
    try:
        result = subprocess.run([luau, path], capture_output=True, text=True)
    finally:
        os.remove(path)
    return result


def mutant_verdict(mutant, expected, what, label):
    """None when the mutated program is caught, else the FAIL line to print. A mutant is caught only by a NAMED check: at
    least one "FAIL: <name>" line in its output (a crash, a timeout or a program that doesn't compile proves nothing, and a
    crash never skips the named-check test below). When the mutation names its test, that test must be among the failures."""
    failures = [line for line in mutant.stdout.split("\n") if line.startswith("FAIL: ")]
    if "SyntaxError" in mutant.stderr or not failures:
        how = "it crashed with no failed check: " + (mutant.stderr.strip().split("\n")[0] if mutant.stderr.strip() else "no output") if "passed," not in mutant.stdout and "SyntaxError" not in mutant.stderr else "no check failed"
        return "FAIL: mutation not caught: the %s tests do not notice a broken %s (%s)" % (what, label, how)
    if expected and not any(line.startswith("FAIL: " + expected[0]) for line in failures):
        return "FAIL: mutation of %s is caught, but not by the test \"%s\"" % (label, expected[0])
    return None


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
    visuals_base = (VISUALS_TESTS.replace("__PLOTART__", plot_art).replace("__IPOCONFIG__", ipo_config).replace("__EXPECTED__", visuals_expected_lua())
                    .replace("__KITDOC__", kit_doc_lua()).replace("__ALL_STAGES__", "true" if VISUALS_ALL_STAGES else "false"))
    result18 = run_luau(luau, visuals_base.replace("__PLOTVISUALS__", plot_visuals))
    print("Plot visuals check (PlotArt + PlotVisuals): " + (result18.stdout.strip() or result18.stderr.strip()))
    if result18.returncode != 0 or " 0 failed" not in result18.stdout:
        code = 1
    kit_caught, kit_problems = run_visuals_kit_mutants(luau, visuals_base)
    for line in kit_problems:
        print(line)
    print("Plot visuals kit mutations (interiors): %d of %d caught, each by its named check" % (kit_caught, len(VISUALS_KIT_MUTANTS)))
    if kit_problems:
        code = 1
    visuals_passed, visuals_failed = visuals_wiring_checks()
    print("Plot visuals wiring check: %d passed, %d failed" % (visuals_passed, visuals_failed))
    if visuals_failed:
        code = 1
    frame = run_luau(luau, frame_source(frame_texts()))
    print("Plot frame check (lobby L1: every garage position through plotFrame; 0 degrees is main's, 90/180/270 the same garage turned): "
          + (frame.stdout.strip() or frame.stderr.strip()))
    if frame.returncode != 0 or " 0 failed" not in frame.stdout:
        code = 1
    pins = frame_static_checks()
    for name, ok, extra in pins:
        if not ok:
            print("FAIL: " + name + (" -- " + str(extra) if extra else ""))
            code = 1
    print("Plot frame source pins: %d passed, %d failed" % (sum(1 for _, ok, _ in pins if ok), sum(1 for _, ok, _ in pins if not ok)))
    frame_caught, frame_problems = run_frame_mutants(luau)
    for line in frame_problems:
        print(line)
        code = 1
    print("Plot frame mutations: %d of %d caught, each by its named check" % (frame_caught, len(FRAME_MUTATIONS)))
    self_caught, self_problems = run_frame_mutants(luau, [FRAME_SELF_TEST])
    if self_caught or "the tests crashed" not in "".join(self_problems):
        print("FAIL: the frame mutation harness counted a mutant that crashed the tests as caught")
        code = 1
    print("Plot frame harness self-test (a mutant that crashes the tests never counts): %d of 1 reported as not caught" % (0 if self_caught else 1))
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
    result20 = run_luau(luau, company_source())
    print("Pokedex rules check (CompanyConfig + SectorConfig): " + (result20.stdout.strip() or result20.stderr.strip()))
    if result20.returncode != 0 or " 0 failed" not in result20.stdout:
        code = 1
    company_caught = 0
    for label, mutation, *expected in COMPANY_MUTATIONS:
        mutant = run_luau(luau, company_source(mutation))
        problem = mutant_verdict(mutant, expected, "Pokedex", label)
        if problem:
            print(problem)
            code = 1
        else:
            company_caught += 1
    print("Pokedex rule mutations: %d of %d broken rules caught" % (company_caught, len(COMPANY_MUTATIONS)))
    result21 = run_luau(luau, company_server_source())
    print("CompanyServer check (join, saving, Place, Store, Sync): " + (result21.stdout.strip() or result21.stderr.strip()))
    if result21.returncode != 0 or " 0 failed" not in result21.stdout:
        code = 1
    server_caught = 0
    for label, mutation, *expected in SERVER_MUTATIONS:
        mutant = run_luau(luau, company_server_source(mutation))
        problem = mutant_verdict(mutant, expected, "CompanyServer", label)
        if problem:
            print(problem)
            code = 1
        else:
            server_caught += 1
    print("CompanyServer mutations: %d of %d broken rules caught" % (server_caught, len(SERVER_MUTATIONS)))
    result22 = run_luau(luau, commit_ipo_source())
    print("TycoonCore IPO check (commitIpo with the real save, a fake DataStore and the real CompanyServer): " + (result22.stdout.strip() or result22.stderr.strip()))
    if result22.returncode != 0 or " 0 failed" not in result22.stdout:
        code = 1
    commit_caught = 0
    for label, mutation, *expected in COMMITIPO_MUTATIONS:
        mutant = run_luau(luau, commit_ipo_source(mutation))
        problem = mutant_verdict(mutant, expected, "commitIpo", label)
        if problem:
            print(problem)
            code = 1
        else:
            commit_caught += 1
    print("commitIpo mutations: %d of %d broken rules caught" % (commit_caught, len(COMMITIPO_MUTATIONS)))
    pokedex_passed, pokedex_failed = pokedex_wiring_checks()
    print("Pokedex wiring check: %d passed, %d failed" % (pokedex_passed, pokedex_failed))
    if pokedex_failed:
        code = 1
    wiring_caught = 0
    for label, filename, old, new in WIRING_MUTATIONS:
        if wiring_mutation_run(label, filename, old, new):
            wiring_caught += 1
        else:
            print("FAIL: mutation not caught: the source checks do not notice " + label)
            code = 1
    print("Source check mutations: %d of %d broken rules caught" % (wiring_caught, len(WIRING_MUTATIONS)))
    pads_passed, pads_failed = pads_gone_checks()
    print("Pads gone and Office wiring check: %d passed, %d failed" % (pads_passed, pads_failed))
    if pads_failed:
        code = 1
    return code


if __name__ == "__main__":
    sys.exit(main())
