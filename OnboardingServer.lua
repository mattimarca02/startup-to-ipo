-- OnboardingServer: the first minute for brand-new players (milestone 5).
-- Put this ModuleScript in ServerScriptService, next to TycoonCore and EmployeeServer.
-- TycoonCore owns player data and saving, and plugs this module in with OnboardingServer.init.
-- Everything is decided here on the server. The free egg is given once, by the server, when a
-- brand-new player's save loads; no remote can ask for it.
-- Players who already had a save before milestone 5 count as already onboarded.
-- Settings (the free egg, goals, arrow) live in OnboardingConfig (ReplicatedStorage).
-- The screen (OnboardingClient) only reads what this module puts on the player:
--   OnboardingTarget (Vector3 or nil) -> where the glowing arrow points
--   OnboardingTracker (boolean)       -> show the goal tracker
--   OnboardingGoal_<key>, OnboardingGoalTarget_<key> (numbers) -> each goal's progress
-- Goals are checked here from the server's own data; the client can't finish one.
-- The only thing the client can ask (OnboardingRemotes.OnboardingAction) is "DismissTracker":
-- hide the tracker for good. It grants nothing.

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")

local OnboardingConfig = require(ReplicatedStorage:WaitForChild("OnboardingConfig"))
local IpoConfig = require(ReplicatedStorage:WaitForChild("IpoConfig"))
local EmployeeServer = require(script.Parent:WaitForChild("EmployeeServer"))
local ShopServer = require(script.Parent:WaitForChild("ShopServer")) -- for the Studio Debug tab

local OnboardingServer = {}

local core -- { getData, save, updateIncome, nextUpgradeCost }, given by TycoonCore
local remotes = {}

-- The fields of the saved "onboarding" section this version knows. Others were written by newer
-- code: they're kept and saved back unchanged, never deleted.
local KNOWN_FIELDS = { seenIntro = true, legacy = true, arrowDone = true, dismissed = true, goals = true }

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

local function countOwned(data)
	local count = 0
	for _ in pairs(data.owned) do
		count += 1
	end
	return count
end

-- Changes an attribute only when the value is different (no extra traffic every second)
local function setAttribute(player, name, value)
	if player:GetAttribute(name) ~= value then
		player:SetAttribute(name, value)
	end
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

-- The glowing arrow -------------------------------------------------------

-- Where to go next: a ready egg (tap Hatch), else the green pad if its upgrade is affordable
-- (the first one is free), else the egg that's still incubating. nil = nowhere.
local function arrowTarget(data, now)
	local team = data.team
	local incubating
	for i = 1, #team.incubators do
		local egg = team.incubators[i]
		local parts = team.incubatorParts[i]
		if egg and parts then
			if egg.hatchAt <= now and not team.pending then
				return parts.base.Position
			end
			incubating = incubating or parts.base.Position
		end
	end
	local cost = core.nextUpgradeCost(data)
	if data.pad and cost and data.cash.Value >= cost then
		return data.pad.Position
	end
	return incubating
end

-- Goals ---------------------------------------------------------------------

local function stageNumber(key)
	for i, stage in ipairs(IpoConfig.Stages) do
		if stage.key == key then
			return i
		end
	end
	return nil
end

-- (where the player is now, what the goal needs), from the server's own data.
-- nil for a goal this version can't check (it's skipped, never blocks the tracker).
local function goalProgress(data, goal)
	if goal.kind == "employees" then
		return #data.team.employees, goal.target
	elseif goal.kind == "stage" then
		local index = stageNumber(goal.stage)
		if index then
			return data.ipo.valuation, IpoConfig.stageValuation(index, data.ipo.count)
		end
	end
	return nil
end

-- Marks goals that just became true as finished (saved, so they stay finished even if an IPO
-- or a poach takes the player back below), and sends each goal's progress to the screen.
-- Returns true when every goal is finished.
local function updateGoals(player, data)
	local onboarding = data.onboarding
	local allDone = true
	for _, goal in ipairs(OnboardingConfig.Goals) do
		local current, target = goalProgress(data, goal)
		if current then
			if not onboarding.goals[goal.key] and current >= target then
				onboarding.goals[goal.key] = true
			end
			if onboarding.goals[goal.key] then
				current = target
			else
				allDone = false
			end
			setAttribute(player, "OnboardingGoal_" .. goal.key, math.min(current, target))
			setAttribute(player, "OnboardingGoalTarget_" .. goal.key, target)
		end
	end
	return allDone
end

-- Runs every second for each loaded player: ends the arrow once it's done its job, tells the
-- screen where it points, and checks the goals
local function update(player, data, now)
	local onboarding = data.onboarding
	local active = OnboardingConfig.Enabled and not onboarding.legacy
	if active and not onboarding.arrowDone then
		local ends = OnboardingConfig.ArrowEndsAt
		if #data.team.employees >= ends.employees and countOwned(data) >= ends.upgrades then
			onboarding.arrowDone = true -- saved: it never comes back (not even after an IPO)
		end
	end
	setAttribute(player, "OnboardingTarget", active and not onboarding.arrowDone and arrowTarget(data, now) or nil)

	local showTracker = false
	if active then
		local allDone = updateGoals(player, data)
		-- It appears once the free egg has hatched (or the player is already past that point),
		-- and stays until every goal is finished or the player closes it
		local started = #data.team.employees >= OnboardingConfig.TrackerAfterEmployees
			or onboarding.arrowDone or next(onboarding.goals) ~= nil
		showTracker = started and not allDone and not onboarding.dismissed
	end
	setAttribute(player, "OnboardingTracker", showTracker)
end

-- Actions the client can ask for ------------------------------------------------

local function onAction(player, action)
	if typeof(action) ~= "string" then return false, "Bad request" end
	local data = core.getData(player)
	if not data or not data.ready or not data.onboarding then
		return false, "Still loading, try again in a moment"
	end
	if action == "DismissTracker" then
		data.onboarding.dismissed = true -- saved: the tracker stays closed
		setAttribute(player, "OnboardingTracker", false)
		return true
	end
	return false, "Unknown action"
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
		arrowDone = false, -- the arrow did its job and is gone for good (saved)
		dismissed = false, -- the player closed the goal tracker with its X (saved)
		goals = {}, -- goal key -> true once finished; stays finished (saved)
		unknown = {}, -- fields of the saved section this version doesn't know (saved back as they were)
	}
	if typeof(savedOnboarding) == "table" then -- bad values are skipped, never an error
		onboarding.seenIntro = savedOnboarding.seenIntro == true
		onboarding.legacy = savedOnboarding.legacy == true
		onboarding.arrowDone = savedOnboarding.arrowDone == true
		onboarding.dismissed = savedOnboarding.dismissed == true
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
		arrowDone = onboarding.arrowDone,
		dismissed = onboarding.dismissed,
		goals = goals,
	}
	for key, value in pairs(onboarding.unknown) do -- written by newer code: kept as it was
		if section[key] == nil then
			section[key] = value
		end
	end
	return section
end

-- Studio Debug tab -------------------------------------------------------------

local function addDebugActions()
	-- Start the first minute again on any save: free egg, arrow, goals. Studio only, so it can
	-- skip the "no progress at all" rule that protects live players from a second free egg.
	ShopServer.addDebugAction("OnboardingRestart", function(player, data)
		local onboarding = data.onboarding
		onboarding.seenIntro = false
		onboarding.legacy = false
		onboarding.arrowDone = false
		onboarding.dismissed = false
		table.clear(onboarding.goals)
		if not grantFreeEgg(player, data) then
			return "Tutorial restarted, but there was no empty incubator for the free egg"
		end
		return "Tutorial restarted: free " .. OnboardingConfig.FreeEgg .. " egg is incubating (saved at the next save)"
	end)
	-- Back to how a save from before milestone 5 behaves: no arrow, no tracker
	ShopServer.addDebugAction("OnboardingMarkOld", function(_, data)
		data.onboarding.seenIntro = true
		data.onboarding.legacy = true
		return "You now count as an old save: no arrow, no tracker (saved at the next save)"
	end)
end

-- Setup -----------------------------------------------------------------

function OnboardingServer.init(coreApi)
	core = coreApi

	local folder = Instance.new("Folder")
	folder.Name = "OnboardingRemotes"
	remotes.action = Instance.new("RemoteFunction")
	remotes.action.Name = "OnboardingAction"
	remotes.action.OnServerInvoke = onAction
	remotes.action.Parent = folder
	folder.Parent = ReplicatedStorage

	if RunService:IsStudio() then
		addDebugActions()
	end

	for _, goal in ipairs(OnboardingConfig.Goals) do
		if goal.kind == "stage" and not stageNumber(goal.stage) then
			warn("OnboardingConfig: goal " .. goal.key .. " needs a stage IpoConfig doesn't have: " .. tostring(goal.stage))
		end
	end

	-- Every second: arrow (and goals) for every loaded player
	task.spawn(function()
		while true do
			task.wait(1)
			local now = os.time()
			for _, player in ipairs(Players:GetPlayers()) do
				local data = core.getData(player)
				if data and data.ready and data.onboarding then
					local ok, err = pcall(update, player, data, now) -- one bad player never stops the loop
					if not ok then
						warn("Onboarding update failed for " .. player.Name .. ": " .. tostring(err))
					end
				end
			end
		end
	end)
end

return OnboardingServer
