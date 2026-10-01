-- DailyConfig: the 7-day login calendar (milestone 6).
-- Put this ModuleScript in ReplicatedStorage (DailyServer and the Daily window both read it).
--
-- Once per UTC day a player can claim the next day of the calendar. Days 1-7, then it starts
-- again at Day 1. Everything is decided by DailyServer on the server, from its own clock:
-- the client only asks "Claim". Nothing here is sold for Robux.
--
-- Safe to change any time: rewards, texts, icons and the numbers below, EXCEPT ResetHourUtc:
-- decide it before shipping. Moving it earlier later lets every player claim one extra day
-- (the hours between the old and new reset count as a new day).
-- Never rename or reuse a day's "key" once it has shipped.
-- Calendar Cash is a gift: it never counts toward the IPO valuation (see DailyServer).

local DailyConfig = {}

-- Turns the calendar off (no window, no chip, no claims). Saves are kept as they are.
DailyConfig.Enabled = true

-- The calendar, in order. A day can give:
--   cashMinutes = N  -> N minutes of the player's Income at the moment they claim
--   egg = "Key"      -> one free egg from CreatureConfig.Eggs, put in a free incubator
--   shares = N       -> N Shares (the IPO currency). Never doubled by the Shareholder pass.
DailyConfig.Days = {
	{ key = "Day1", cashMinutes = 5, icon = "💵" },
	{ key = "Day2", cashMinutes = 10, icon = "💵" },
	{ key = "Day3", egg = "Garage", icon = "🥚" },
	{ key = "Day4", cashMinutes = 20, icon = "💰" },
	{ key = "Day5", egg = "Startup", icon = "🥚" },
	{ key = "Day6", cashMinutes = 30, icon = "💰" },
	{ key = "Day7", egg = "Unicorn", shares = 3, icon = "🦄" },
}

-- Missing this many days in a row keeps your place in the calendar. Missing more starts it
-- again at Day 1. (1: miss one day and you're fine, miss two and it's Day 1.)
DailyConfig.GraceDays = 1

DailyConfig.CashMaxMinutes = 60 -- hard cap on any cashMinutes, so a bad config can't print money
DailyConfig.MinCash = 300 -- a Cash day never gives less (a brand-new player has $0 Income before the free Desk)
DailyConfig.MaxShares = 5 -- the config check warns above this (the cheapest IPO perk level costs 5)
DailyConfig.ResetHourUtc = 0 -- a new day starts at this hour, UTC, for every player at the same moment. Don't change after launch (see top)
DailyConfig.ClaimDebounce = 1 -- seconds between two Claim requests from one player

-- The window opens by itself once per join when a reward is waiting, a few seconds after the
-- player is in (never in the M5 first minute, never over another window or a poach panel)
DailyConfig.AutoOpen = true
DailyConfig.AutoOpenDelay = 3 -- seconds after the screen is ready
DailyConfig.AutoOpenWithin = 60 -- after this many seconds it no longer opens by itself (the chip stays)

-- The gift chip next to the valuation bar (pixels). IpoClient leaves this much room for it.
DailyConfig.ChipSize = 48
DailyConfig.ChipGap = 6

-- Texts. Calm and factual: no pressure, no countdown on a lost streak.
DailyConfig.Texts = {
	Title = "🎁 Daily Rewards",
	Rules = "Come back once a day for the next reward. Missing one day is fine. After 2 missed days the calendar starts again at Day 1.",
	Streak = "Streak: %d %s · best %d", -- streak, "day"/"days", best
	Grace = "You missed a day. Your place is kept: today is Day %d.",
	Reset = "You missed %d days. Your streak was Day %d. Today is Day 1.",
	Claim = "🎁 Claim Day %d",
	NextIn = "Next reward in %s",
	NoIncubator = "Free an incubator first",
	IpoBusy = "Your IPO is being filed, try again in a moment",
	Loading = "Still loading, try again in a moment",
	NotLoaded = "Your save didn't load, so rewards can't be claimed this session",
	AlreadyClaimed = "Already claimed today. Next reward in %s",
	Off = "Daily rewards are off right now",
	IpoReminder = "🎁 You have a daily reward waiting. Claim it after going public.",
}

-- Helpers used by both the server and the screen -------------------------------

local DAY_SECONDS = 24 * 60 * 60

-- The day number of a moment in time (os.time() seconds, UTC). Only the server's number counts.
function DailyConfig.dayNumber(seconds)
	return math.floor((seconds - DailyConfig.ResetHourUtc * 3600) / DAY_SECONDS)
end

-- When day number `day` starts (os.time() seconds). The next reset is dayStart(today + 1).
function DailyConfig.dayStart(day)
	return day * DAY_SECONDS + DailyConfig.ResetHourUtc * 3600
end

function DailyConfig.getDay(index)
	return DailyConfig.Days[index]
end

-- Calendar day (1..#Days) for the Nth claim of a streak (1 -> Day 1, 8 -> Day 1 again)
function DailyConfig.calendarDay(streak)
	return (math.max(1, streak) - 1) % #DailyConfig.Days + 1
end

-- Cash a day gives right now, from the player's Income per second. 0 for a day without Cash.
function DailyConfig.cashFor(day, incomePerSecond)
	local minutes = math.clamp(tonumber(day.cashMinutes) or 0, 0, DailyConfig.CashMaxMinutes)
	if minutes <= 0 then
		return 0
	end
	return math.max(DailyConfig.MinCash, math.floor(math.max(0, incomePerSecond) * 60 * minutes))
end

-- 18720 -> "5h 12m", 750 -> "12m 30s", 42 -> "42s"
function DailyConfig.formatWait(seconds)
	seconds = math.max(0, math.ceil(seconds))
	local h, m, s = seconds // 3600, (seconds // 60) % 60, seconds % 60
	if h > 0 then
		return string.format("%dh %02dm", h, m)
	elseif m > 0 then
		return string.format("%dm %02ds", m, s)
	end
	return s .. "s"
end

-- Warn early about mistakes that would break the calendar
do
	local ok, CreatureConfig = pcall(function()
		return require(script.Parent:WaitForChild("CreatureConfig", 5))
	end)
	local seen = {}
	for i, day in ipairs(DailyConfig.Days) do
		local name = tostring(day.key or ("day " .. i))
		if typeof(day.key) ~= "string" or seen[day.key] then
			warn("DailyConfig: day " .. i .. " needs its own key (got " .. tostring(day.key) .. ")")
		end
		seen[day.key or i] = true
		if not day.cashMinutes and not day.egg and not day.shares then
			warn("DailyConfig: " .. name .. " gives nothing")
		end
		if day.cashMinutes and (typeof(day.cashMinutes) ~= "number" or day.cashMinutes <= 0 or day.cashMinutes > DailyConfig.CashMaxMinutes) then
			warn("DailyConfig: " .. name .. " cashMinutes must be between 0 and " .. DailyConfig.CashMaxMinutes)
		end
		if day.egg and ok and CreatureConfig and not CreatureConfig.getEgg(day.egg) then
			warn("DailyConfig: " .. name .. " gives an egg CreatureConfig doesn't have: " .. tostring(day.egg))
		end
		if day.shares and (typeof(day.shares) ~= "number" or day.shares % 1 ~= 0 or day.shares < 1 or day.shares > DailyConfig.MaxShares) then
			warn("DailyConfig: " .. name .. " shares must be a whole number from 1 to " .. DailyConfig.MaxShares)
		end
	end
	if #DailyConfig.Days == 0 then
		warn("DailyConfig: the calendar has no days")
	end
end

return DailyConfig
