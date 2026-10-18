-- DailyServer: the 7-day login calendar (milestone 6).
-- Put this ModuleScript in ServerScriptService, next to TycoonCore.
-- TycoonCore owns player data and saving, and plugs this module in with DailyServer.init.
-- Everything is decided here on the server, from the server's own clock (os.time(), UTC):
-- which day it is, whether today was claimed, the streak and the reward. The rewards live in
-- DailyConfig (ReplicatedStorage).
-- Calendar Cash is a gift: it goes to Cash only, never through addEarnings, so it never raises
-- the IPO valuation. Calendar Shares are added as they are (no Shareholder pass bonus).
-- The screen (DailyClient) only reads what this module puts on the player:
--   DailyEnabled, DailyReady (booleans)   -> the calendar is on; a reward is waiting today
--   DailyDay (number)                     -> calendar day to claim (or the one claimed today)
--   DailyStreak, DailyBest (numbers)      -> claims in a row, longest ever
--   DailyNextAt (number, os.time())       -> when the next day starts (the countdown)
--   DailyMissed, DailyLostDay (numbers), DailyKept (boolean) -> the "you missed a day" line
--   DailyBlocked (string)                 -> why Claim can't work right now ("" = it can)
--   DailyAutoOpen (boolean)               -> the window may open by itself (not in the first minute; a
--                                            brand-new player's first gift waits for the first pause)
-- The only thing the client can ask (DailyRemotes.DailyAction) is "Claim". It sends no day,
-- time, streak or amount: the server works all of that out.

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")

local DailyConfig = require(ReplicatedStorage:WaitForChild("DailyConfig"))
local OnboardingConfig = require(ReplicatedStorage:WaitForChild("OnboardingConfig"))
local CreatureConfig = require(ReplicatedStorage:WaitForChild("CreatureConfig")) -- egg names, for the message
local ShopConfig = require(ReplicatedStorage:WaitForChild("ShopConfig")) -- money format, for the message
local EmployeeServer = require(script.Parent:WaitForChild("EmployeeServer"))
local IpoServer = require(script.Parent:WaitForChild("IpoServer"))
local ShopServer = require(script.Parent:WaitForChild("ShopServer")) -- for the Studio Debug tab

local TEXTS = DailyConfig.Texts

local DailyServer = {}

local core -- { getData, save }, given by TycoonCore
local remotes = {}

-- The fields of the saved "daily" section this version knows. Others were written by newer
-- code: they're kept and saved back unchanged, never deleted.
local KNOWN_FIELDS = { lastClaimDay = true, streak = true, best = true, claims = true }

-- Helpers ---------------------------------------------------------------

local function today()
	return DailyConfig.dayNumber(os.time())
end

-- Changes an attribute only when the value is different (no extra traffic every second)
local function setAttribute(player, name, value)
	if player:GetAttribute(name) ~= value then
		player:SetAttribute(name, value)
	end
end

-- True if at least one incubator is empty (EmployeeServer.grantEgg has the final say)
local function hasFreeIncubator(data)
	local incubators = data.team and data.team.incubators
	if not incubators then return false end
	for i = 1, #incubators do -- empty incubators are false, so # still counts them all
		if not incubators[i] then
			return true
		end
	end
	return false
end

-- What the calendar looks like on day number `now`, from the saved claim and streak only:
--   claimedToday -> today's reward was already claimed
--   day          -> the calendar day a claim gives now (or the one claimed today)
--   streak       -> the streak after that claim
--   missed       -> whole days missed since the last claim
--   kept         -> missed some days, but within GraceDays: the place in the calendar is kept
--   lostDay      -> missed too many: the calendar day the old streak had reached (0 = none)
-- A last claim on a later day than today (another server's clock was a few seconds ahead at
-- the 08:00 UTC reset) counts as claimed today: it never grants, and setupPlayer clamps far-off values.
local function status(daily, now)
	local last = daily.lastClaimDay
	if last > 0 and now <= last then
		return { claimedToday = true, day = DailyConfig.calendarDay(daily.streak), streak = daily.streak, missed = 0, lostDay = 0 }
	end
	local missed = last > 0 and (now - last - 1) or 0
	if last > 0 and daily.streak > 0 and missed <= DailyConfig.GraceDays then
		local streak = daily.streak + 1
		return { day = DailyConfig.calendarDay(streak), streak = streak, missed = missed, kept = missed > 0, lostDay = 0 }
	end
	local lostDay = (last > 0 and daily.streak > 0) and DailyConfig.calendarDay(daily.streak) or 0
	return { day = 1, streak = 1, missed = missed, lostDay = lostDay }
end

-- The Shares a day gives, or 0 (a bad config value gives none rather than something odd)
local function sharesFor(reward)
	local shares = reward.shares
	if typeof(shares) == "number" and shares % 1 == 0 and shares >= 1 and shares <= DailyConfig.MaxShares then
		return shares
	end
	return 0
end

-- True while a brand-new player's first gift waits for the first pause of session 1 (TUT 6): onboarding
-- is on, they never claimed, and they haven't had DailyConfig.FirstPause.employees employees for
-- FirstPause.delay seconds yet. Once reached it stays reached for the session (a poach doesn't undo it).
local function waitsForFirstPause(data, daily)
	local onboarding = data.onboarding
	local pause = DailyConfig.FirstPause
	if not OnboardingConfig.Enabled or onboarding == nil or onboarding.legacy or daily.claims > 0
		or typeof(pause) ~= "table" or typeof(pause.employees) ~= "number" or typeof(pause.delay) ~= "number" then
		return false
	end
	if not daily.pauseAt then
		local employees = data.team and data.team.employees
		if typeof(employees) ~= "table" or #employees < pause.employees then
			return true
		end
		daily.pauseAt = os.time() + pause.delay -- not saved: this session only
	end
	return os.time() < daily.pauseAt
end

-- Copies the state the Daily window shows onto the player. The server never reads them back.
local function publish(player, data, now)
	local daily = data.daily
	local info = status(daily, now)
	local reward = DailyConfig.getDay(info.day)
	local blocked = ""
	if not data.loaded then
		blocked = TEXTS.NotLoaded -- the save didn't load: a claim could never be saved
	elseif not info.claimedToday and reward and reward.egg and not hasFreeIncubator(data) then
		blocked = TEXTS.NoIncubator
	end
	-- The M5 first minute keeps the screen for the free egg and the arrow: no pop-up then
	local onboarding = data.onboarding
	local firstMinute = OnboardingConfig.Enabled and onboarding ~= nil and not onboarding.legacy and not onboarding.arrowDone
	local waiting = firstMinute or waitsForFirstPause(data, daily)

	setAttribute(player, "DailyEnabled", DailyConfig.Enabled)
	setAttribute(player, "DailyReady", DailyConfig.Enabled and not info.claimedToday)
	setAttribute(player, "DailyDay", info.day)
	setAttribute(player, "DailyStreak", (info.claimedToday or info.streak > 1) and daily.streak or 0) -- 0 once it's lost
	setAttribute(player, "DailyBest", daily.best)
	setAttribute(player, "DailyNextAt", DailyConfig.dayStart(math.max(now, daily.lastClaimDay) + 1))
	setAttribute(player, "DailyMissed", info.missed)
	setAttribute(player, "DailyKept", info.kept == true)
	setAttribute(player, "DailyLostDay", info.lostDay)
	setAttribute(player, "DailyBlocked", blocked)
	setAttribute(player, "DailyAutoOpen", DailyConfig.AutoOpen and not waiting and data.loaded == true)
end

-- "Day 3: Garage Egg, it's incubating"
local function rewardMessage(day, cash, eggKey, shares)
	local parts = {}
	if cash > 0 then
		table.insert(parts, "+" .. ShopConfig.formatCash(cash))
	end
	if eggKey then
		local egg = CreatureConfig.getEgg(eggKey)
		table.insert(parts, (egg and egg.name or eggKey) .. ", it's incubating")
	end
	if shares > 0 then
		table.insert(parts, "+" .. shares .. " Shares")
	end
	return "Day " .. day .. ": " .. table.concat(parts, " · ")
end

-- Claiming -------------------------------------------------------------------

-- One safe step. Nothing between "is today still free?" and "today is claimed" waits, so a
-- second request (double tap, a second invoke) always sees the claim and is refused. The
-- reward and the marker change together in memory and land in the same save: they can never
-- be saved apart. If that save fails, the next autosave or the leave save writes both.
local function claim(player, data)
	local daily = data.daily
	local now = today()
	local info = status(daily, now)
	if info.claimedToday then
		return false, string.format(TEXTS.AlreadyClaimed, DailyConfig.formatWait(DailyConfig.dayStart(math.max(now, daily.lastClaimDay) + 1) - os.time()))
	end
	local reward = DailyConfig.getDay(info.day)
	if not reward then
		return false, TEXTS.Off
	end

	-- 0. A day with Shares needs the IPO not to be filing (grantShares refuses then). Checked
	--    before anything is granted, so a refusal never uses up the day with part of it (M6 F2).
	if sharesFor(reward) > 0 and IpoServer.isBusy(data) then
		return false, TEXTS.IpoBusy
	end

	-- 1. The egg first: it's the only part that can fail. If it does, nothing changed and the
	--    day isn't used up (the player can free an incubator and claim again today).
	local eggKey = reward.egg
	if eggKey then
		if not hasFreeIncubator(data) then
			return false, TEXTS.NoIncubator
		end
		if not EmployeeServer.grantEgg(player, eggKey) then
			return false, TEXTS.NoIncubator
		end
	end

	-- 2. Cash, as a gift: data.cash only, never addEarnings (it must not raise the valuation)
	local ipo = data.ipo
	local valuationBefore, lifetimeBefore = ipo.valuation, ipo.lifetime
	local cash = DailyConfig.cashFor(reward, data.income.Value)
	if cash > 0 then
		data.cash.Value += cash
	end

	-- 3. Shares, as they are: no Shareholder pass bonus
	local shares = sharesFor(reward)
	if shares > 0 and not IpoServer.grantShares(player, shares) then
		warn("Could not give " .. player.Name .. " the daily Shares")
		shares = 0
	end

	-- 4. Today is claimed (same step as the reward, nothing waited in between)
	daily.lastClaimDay = now
	daily.streak = info.streak
	daily.best = math.max(daily.best, daily.streak)
	daily.claims += 1

	-- Check: calendar Cash must never count toward the IPO valuation (it would make the first IPO
	-- about 25% sooner). Only addEarnings changes these, and nothing above calls it.
	if ipo.valuation ~= valuationBefore or ipo.lifetime ~= lifetimeBefore then
		warn(string.format("BUG: a daily claim changed %s's valuation (%d -> %d). Calendar Cash must not count toward the IPO.",
			player.Name, valuationBefore, ipo.valuation))
	end

	publish(player, data, now)
	local message = rewardMessage(info.day, cash, eggKey, shares)
	print(player.Name .. " claimed daily " .. message .. " (streak " .. daily.streak .. ")")

	-- Save right away (like a purchase), and answer only after the save did
	local saved = core.save(player)
	if not saved then
		warn("The daily claim save failed for " .. player.Name .. ": the next save will write it")
	end
	return true, message, { day = info.day, cash = cash, egg = eggKey or false, shares = shares, saved = saved == true }
end

local function onAction(player, action)
	if typeof(action) ~= "string" then return false, "Bad request" end
	if action ~= "Claim" then return false, "Unknown action" end
	if not DailyConfig.Enabled then return false, TEXTS.Off end
	local data = core.getData(player)
	if not data or not data.ready or not data.daily then
		return false, IpoServer.isBusy(data) and TEXTS.IpoBusy or TEXTS.Loading
	end
	if not data.loaded then return false, TEXTS.NotLoaded end -- the reward could never be saved

	local daily = data.daily
	local clock = os.clock()
	if clock - daily.lastRequest < DailyConfig.ClaimDebounce then
		return false, "One moment..."
	end
	daily.lastRequest = clock
	return claim(player, data)
end

-- Saving (TycoonCore calls these) ----------------------------------------------

-- Called right after the player's save loads, after OnboardingServer. savedDaily is the "daily"
-- part of the save, or nil (saves from before milestone 6, and new players): they start at Day 1.
-- Nothing is granted or changed here: joining never gives a reward, only a Claim does.
function DailyServer.setupPlayer(player, data, savedDaily)
	local daily = {
		lastClaimDay = 0, -- day number (DailyConfig.dayNumber) of the last claim; 0 = never (saved)
		streak = 0, -- claims in a row (a missed day within GraceDays doesn't break it) (saved)
		best = 0, -- longest streak ever, for display (saved)
		claims = 0, -- claims ever (saved)
		unknown = {}, -- fields of the saved section this version doesn't know (saved back as they were)
		lastRequest = 0, -- os.clock() of the last Claim request (debounce)
		fakeDays = 0, -- Studio Debug tab only: fake days passed this session
		pauseAt = nil, -- os.time() of the first pause of a brand-new player (not saved)
	}
	if typeof(savedDaily) == "table" then -- bad values are skipped with a warning, never an error
		for key in pairs(KNOWN_FIELDS) do
			local value = savedDaily[key]
			if value ~= nil then
				if typeof(value) == "number" and value == value and value >= 0 and value < math.huge and value % 1 == 0 then
					daily[key] = value
				else
					warn("Skipped a bad daily." .. key .. " in " .. player.Name .. "'s save: " .. tostring(value))
				end
			end
		end
		for key, value in pairs(savedDaily) do
			if not KNOWN_FIELDS[key] then
				daily.unknown[key] = value
			end
		end
	elseif savedDaily ~= nil then
		warn("Skipped a bad daily section in " .. player.Name .. "'s save")
	end
	-- A last claim far in the future is bad data (or a server clock that was wrong): count it as
	-- today, so it never grants anything and never locks the player out for good.
	local now = today()
	if daily.lastClaimDay > now + 1 then
		warn(string.format("%s's last daily claim is in the future (day %d, today is %d): counted as today",
			player.Name, daily.lastClaimDay, now))
		daily.lastClaimDay = now
	end
	daily.best = math.max(daily.best, daily.streak)
	data.daily = daily
	publish(player, data, now)
end

-- The part of the save file that belongs to the daily calendar
function DailyServer.serialize(data)
	local daily = data.daily
	if not daily then return nil end
	local section = {
		lastClaimDay = daily.lastClaimDay,
		streak = daily.streak,
		best = daily.best,
		claims = daily.claims,
	}
	for key, value in pairs(daily.unknown) do -- written by newer code: kept as it was
		if section[key] == nil then
			section[key] = value
		end
	end
	return section
end

-- Studio Debug tab -------------------------------------------------------------
-- Only registered in Studio, and ShopServer's Debug remote only exists in Studio with
-- ShopConfig.DebugInStudio on. Each handler checks IsStudio again. Live servers never run these.

local function describe(daily)
	local info = status(daily, today())
	if info.claimedToday then
		return "Day " .. info.day .. " already claimed today"
	end
	local text = "Ready: Day " .. info.day
	if info.kept then
		text ..= " (missed " .. info.missed .. ", place kept)"
	elseif info.lostDay > 0 then
		text ..= " (missed " .. info.missed .. ", back to Day 1)"
	end
	return text
end

local function addDebugActions()
	-- A fake UTC day for this player: the last claim moves one day back, which for every rule
	-- here is the same as the calendar moving one day forward. No future date is ever saved.
	ShopServer.addDebugAction("DailyNextDay", function(player, data)
		if not RunService:IsStudio() then return "Debug is disabled" end
		local daily = data.daily
		if daily.lastClaimDay <= 0 then
			return "Nothing claimed yet: Day 1 is already waiting"
		end
		daily.lastClaimDay -= 1
		daily.fakeDays += 1
		publish(player, data, today())
		return "Fake day +" .. daily.fakeDays .. " this session (written to your real save at the next save). " .. describe(daily)
	end)
	ShopServer.addDebugAction("DailyReset", function(player, data)
		if not RunService:IsStudio() then return "Debug is disabled" end
		local daily = data.daily
		daily.lastClaimDay, daily.streak, daily.best, daily.claims, daily.fakeDays = 0, 0, 0, 0, 0
		publish(player, data, today())
		return "Calendar reset: next claim is Day 1, no streak (written to your real save at the next save)"
	end)
end

-- Setup -----------------------------------------------------------------

function DailyServer.init(coreApi)
	core = coreApi

	local folder = Instance.new("Folder")
	folder.Name = "DailyRemotes"
	remotes.action = Instance.new("RemoteFunction")
	remotes.action.Name = "DailyAction"
	remotes.action.OnServerInvoke = onAction
	remotes.action.Parent = folder
	folder.Parent = ReplicatedStorage

	if RunService:IsStudio() then
		addDebugActions()
	end

	-- Every second: the day can change (the 08:00 UTC reset, DailyConfig.ResetHourUtc) and incubators fill up and empty
	task.spawn(function()
		while true do
			task.wait(1)
			local now = today()
			for _, player in ipairs(Players:GetPlayers()) do
				local data = core.getData(player)
				if data and data.ready and data.daily then
					local ok, err = pcall(publish, player, data, now) -- one bad player never stops the loop
					if not ok then
						warn("Daily update failed for " .. player.Name .. ": " .. tostring(err))
					end
				end
			end
		end
	end)
end

return DailyServer
