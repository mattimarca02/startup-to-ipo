-- OnboardingServer: the first minute for brand-new players (milestone 5).
-- Put this ModuleScript in ServerScriptService, next to TycoonCore and EmployeeServer.
-- TycoonCore owns player data and saving, and plugs this module in with OnboardingServer.init.
-- Everything is decided here on the server. The free egg is given once, by the server, when a
-- brand-new player's save loads; no remote can ask for it.
-- Players who already had a save before milestone 5 count as already onboarded.
-- Settings (the free egg, goals, arrow) live in OnboardingConfig (ReplicatedStorage).

local ReplicatedStorage = game:GetService("ReplicatedStorage")

local OnboardingConfig = require(ReplicatedStorage:WaitForChild("OnboardingConfig"))
local EmployeeServer = require(script.Parent:WaitForChild("EmployeeServer"))

local OnboardingServer = {}

local core -- { getData, save, updateIncome, nextUpgradeCost }, given by TycoonCore

-- The fields of the saved "onboarding" section this version knows. Others were written by newer
-- code: they're kept and saved back unchanged, never deleted.
local KNOWN_FIELDS = { seenIntro = true, legacy = true, goals = true }

-- Helpers ---------------------------------------------------------------

-- True if this player has done anything at all: Cash, upgrades, eggs, employees, IPO progress,
-- purchases or poaching. Only a player with none of these can get the free egg, so a save that
-- already has the free egg (or what hatched from it) can never get a second one.
local function hasProgress(data)
	if data.cash.Value > 0 or next(data.owned) ~= nil then return true end
	local team = data.team
	if #team.employees > 0 or team.pending or next(team.parked) ~= nil then return true end
	for i = 1, #team.incubators do
		if team.incubators[i] then return true end
	end
	local ipo = data.ipo
	if ipo.count > 0 or ipo.shares > 0 or ipo.lifetime > 0 or next(ipo.perks) ~= nil then return true end
	if #data.shop.receipts > 0 or data.shop.instantHatches > 0 then return true end
	return data.poach.hrLevel > 0 or next(data.poach.lost) ~= nil or next(data.poach.gained) ~= nil
end

-- Gives the free egg. seenIntro flips in the same step, so the save that has the egg also says
-- it was given (one save holds both, they can't be written apart).
local function grantFreeEgg(player, data)
	local onboarding = data.onboarding
	local index = EmployeeServer.grantEgg(player, OnboardingConfig.FreeEgg)
	if not index then
		warn("Could not give " .. player.Name .. " the free egg (unknown egg or no free incubator)")
		return false
	end
	onboarding.seenIntro = true
	print(player.Name .. " is new: free " .. OnboardingConfig.FreeEgg .. " egg in incubator " .. index)
	return true
end

-- Saving (TycoonCore calls these) ----------------------------------------------

-- Called right after the player's save loads, after every other module (it looks at their data
-- to tell a new player from an old one). savedOnboarding is the "onboarding" part of the save,
-- or nil: saves from before milestone 5, and new players. loadOk is false if the save couldn't
-- be read (then this session never saves, and nobody gets a free egg).
function OnboardingServer.setupPlayer(player, data, savedOnboarding, loadOk)
	local onboarding = {
		seenIntro = false, -- the free egg was given, or the player didn't need it (saved)
		legacy = false, -- had a save before milestone 5: counts as already onboarded (saved)
		goals = {}, -- goal key -> true once finished; stays finished (saved)
		unknown = {}, -- fields of the saved section this version doesn't know (saved back as they were)
	}
	if typeof(savedOnboarding) == "table" then -- bad values are skipped, never an error
		onboarding.seenIntro = savedOnboarding.seenIntro == true
		onboarding.legacy = savedOnboarding.legacy == true
		-- Every finished goal key is kept, even ones this version's config doesn't list
		for _, key in ipairs(typeof(savedOnboarding.goals) == "table" and savedOnboarding.goals or {}) do
			if typeof(key) == "string" then
				onboarding.goals[key] = true
			else
				warn("Skipped a bad finished goal in " .. player.Name .. "'s save: " .. tostring(key))
			end
		end
		for key, value in pairs(savedOnboarding) do
			if not KNOWN_FIELDS[key] then
				onboarding.unknown[key] = value
			end
		end
	elseif savedOnboarding ~= nil then
		warn("Skipped a bad onboarding section in " .. player.Name .. "'s save")
	end
	data.onboarding = onboarding

	if not loadOk then
		onboarding.legacy = true -- we don't know who this is: no free egg (this session isn't saved anyway)
		return
	end
	if savedOnboarding == nil and hasProgress(data) then
		onboarding.seenIntro = true -- a save from before milestone 5: already onboarded
		onboarding.legacy = true
		return
	end
	if OnboardingConfig.Enabled and not onboarding.seenIntro and not onboarding.legacy and not hasProgress(data) then
		grantFreeEgg(player, data)
	end
end

-- The part of the save file that belongs to onboarding
function OnboardingServer.serialize(data)
	local onboarding = data.onboarding
	if not onboarding then return nil end
	local goals = {}
	for key in pairs(onboarding.goals) do
		table.insert(goals, key)
	end
	table.sort(goals)
	local section = {
		seenIntro = onboarding.seenIntro,
		legacy = onboarding.legacy,
		goals = goals,
	}
	for key, value in pairs(onboarding.unknown) do -- written by newer code: kept as it was
		if section[key] == nil then
			section[key] = value
		end
	end
	return section
end

-- Setup -----------------------------------------------------------------

function OnboardingServer.init(coreApi)
	core = coreApi
end

return OnboardingServer
