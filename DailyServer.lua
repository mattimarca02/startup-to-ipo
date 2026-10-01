-- DailyServer: the 7-day login calendar (milestone 6).
-- Put this ModuleScript in ServerScriptService, next to TycoonCore.
-- TycoonCore owns player data and saving, and plugs this module in with DailyServer.init.
-- Everything is decided here on the server, from the server's own clock (os.time(), UTC):
-- which day it is, whether today was claimed, the streak and the reward. The rewards live in
-- DailyConfig (ReplicatedStorage).
-- Calendar Cash is a gift: it goes to Cash only, never through addEarnings, so it never raises
-- the IPO valuation. Calendar Shares are added as they are (no Shareholder pass bonus).

local ReplicatedStorage = game:GetService("ReplicatedStorage")

local DailyConfig = require(ReplicatedStorage:WaitForChild("DailyConfig"))

local DailyServer = {}

local core -- { getData, save }, given by TycoonCore

-- The fields of the saved "daily" section this version knows. Others were written by newer
-- code: they're kept and saved back unchanged, never deleted.
local KNOWN_FIELDS = { lastClaimDay = true, streak = true, best = true, claims = true }

-- Helpers ---------------------------------------------------------------

local function today()
	return DailyConfig.dayNumber(os.time())
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

-- Setup -----------------------------------------------------------------

function DailyServer.init(coreApi)
	core = coreApi
end

return DailyServer
