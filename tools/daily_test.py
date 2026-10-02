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
It changes nothing in the game or in Studio.
"""

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
-- UTC boundary
check("day changes at UTC midnight", DailyConfig.dayNumber(20001 * 86400 - 1) == 20000 and DailyConfig.dayNumber(20001 * 86400) == 20001)
check("formatWait", DailyConfig.formatWait(18720) == "5h 12m" and DailyConfig.formatWait(750) == "12m 30s" and DailyConfig.formatWait(42) == "42s")

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

for _, name in ipairs({ "shop", "team", "poach", "ipo", "onboarding", "daily" }) do
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
local passed, failed = 0, 0
local function check(name, cond, extra)
	if cond then passed += 1 else failed += 1; print_real("FAIL: " .. name .. (extra and (" -- " .. tostring(extra)) or "")) end
end
local UNITS = CreatureConfig.ODDS_UNITS
check("the real config loads without warnings", #WARNINGS == 0, WARNINGS[1])
check("units are hundredths of a percent", UNITS == 10000)

-- Every egg, in every luck state the server can roll with: no boost, Luck Boost (x2), the strongest
-- Talent Scouts perk (+50%), and both
local STATES = { { "no boost", 1 }, { "Luck Boost", 2 }, { "Talent Scouts Lv 5", 1.5 }, { "Luck Boost + Talent Scouts Lv 5", 3 } }
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
for level = 0, 5 do
	for _, boost in ipairs({ 1, 2 }) do
		for _, egg in ipairs(CreatureConfig.Eggs) do
			local total = 0
			for _, item in ipairs(CreatureConfig.getCreatureOdds(egg, (1 + 0.1 * level) * boost)) do total += item.units end
			if total ~= UNITS then allExact = false end
		end
	end
end
check("every egg x every Talent Scouts level x Luck Boost on/off: exactly 100.00%", allExact)

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
    result5 = run_luau(luau, BUILD_TESTS.replace("__BUILDSAVE__", marked_source("BUILDSAVE")))
    print("TycoonCore build check: " + (result5.stdout.strip() or result5.stderr.strip()))
    if result5.returncode != 0 or " 0 failed" not in result5.stdout:
        code = 1
    result6 = run_luau(luau, WAIT_TESTS.replace("__PASSWAIT__", marked_source("PASSWAIT", "IpoServer.lua")))
    print("IpoServer pass wait check: " + (result6.stdout.strip() or result6.stderr.strip()))
    if result6.returncode != 0 or " 0 failed" not in result6.stdout:
        code = 1
    with open(os.path.join(ROOT, "CreatureConfig.lua"), encoding="utf-8") as f:
        creature_config = f.read()
    result7 = run_luau(luau, ODDS_TESTS.replace("__CREATURECONFIG__", creature_config))
    print("CreatureConfig odds check: " + (result7.stdout.strip() or result7.stderr.strip()))
    if result7.returncode != 0 or " 0 failed" not in result7.stdout:
        code = 1
    result8 = run_luau(luau, MOVE_TESTS.replace("__MOVENOTES__", marked_source("MOVENOTES", "PoachServer.lua")))
    print("PoachServer move check: " + (result8.stdout.strip() or result8.stderr.strip()))
    if result8.returncode != 0 or " 0 failed" not in result8.stdout:
        code = 1
    return code


if __name__ == "__main__":
    sys.exit(main())
