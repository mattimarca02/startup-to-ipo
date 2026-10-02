-- EmployeeServer: recruiting eggs, incubators and creature employees (milestone 2).
-- Put this ModuleScript in ServerScriptService, next to TycoonCore and ShopServer.
-- TycoonCore owns player data and saving, and plugs this module in with EmployeeServer.init.
-- Everything is decided here on the server: buying, timers, the random hatch roll, slots and
-- income. The client only shows the state and asks for actions.
-- PoachServer moves employees between players with hasFreeSlot / releaseEmployee /
-- finishRelease / addEmployee (see "Poaching" below).
-- IPO perks (IpoServer) add incubators and desks, speed up eggs and improve luck; an IPO empties
-- the incubators (clearIncubators) and buying a perk calls refreshCapacity.
-- OnboardingServer gives a brand-new player one free egg with grantEgg (server only, no remote).
-- Players for whom paid random items are restricted (ShopServer.isRandomRestricted, Roblox policy,
-- FR-13 / D9 option B) get no random roll: every hatch takes the next hire of the egg's fixed order
-- (CreatureConfig.fixedHire), counted per egg in its own save section, fixedHires.

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local HttpService = game:GetService("HttpService")
local CollectionService = game:GetService("CollectionService")

local CreatureConfig = require(ReplicatedStorage:WaitForChild("CreatureConfig"))
local CreatureModels = require(ReplicatedStorage:WaitForChild("CreatureModels"))
local ShopServer = require(script.Parent:WaitForChild("ShopServer"))
local IpoServer = require(script.Parent:WaitForChild("IpoServer"))

-- Where employees hang out, as offsets from the plot center: between the furniture rows,
-- away from the spawn point and the green pad
local EMPLOYEE_SPOTS = {
	Vector3.new(-9, 0, -6), Vector3.new(9, 0, -6), Vector3.new(-25, 0, -6), Vector3.new(25, 0, -6),
	Vector3.new(-18, 0, 10), Vector3.new(18, 0, 10), Vector3.new(-12, 0, 21), Vector3.new(12, 0, 21),
	Vector3.new(-25, 0, 21), Vector3.new(25, 0, 21), Vector3.new(0, 0, -6),
}
-- The first three are the base incubators; the rest come from the Extra Incubator IPO perk
local INCUBATOR_SPOTS = {
	Vector3.new(-12, 0, -25), Vector3.new(0, 0, -25), Vector3.new(12, 0, -25),
	Vector3.new(-24, 0, -25), Vector3.new(24, 0, -25),
}
local FEET = Vector3.new(0, 1, 0) -- plot center -> a model's pivot with its feet on the floor
local GOLD = Color3.fromRGB(255, 200, 50)
local WHITE = Color3.new(1, 1, 1)

local EmployeeServer = {}

local core -- { getData, save, updateIncome, plotCenter }, given by TycoonCore
local remotes = {}
local rng = Random.new()

-- Helpers ---------------------------------------------------------------

local function getTeam(player)
	local data = core.getData(player)
	return data and data.team, data
end

local function maxEmployees(player)
	local data = core.getData(player)
	return ShopServer.getMaxEmployees(player, CreatureConfig.BaseEmployeeSlots + IpoServer.perk(data, "ExtraSlot"))
end

-- How many eggs can incubate at once (base + Extra Incubator IPO perk)
local function incubatorCount(data)
	return CreatureConfig.Incubators + IpoServer.perk(data, "ExtraIncubator")
end

local function makePart(parent, name, size, position, color, material)
	local p = Instance.new("Part")
	p.Name = name
	p.Size = size
	p.Position = position
	p.Color = color
	p.Material = material or Enum.Material.SmoothPlastic
	p.Anchored = true
	p.TopSurface = Enum.SurfaceType.Smooth
	p.BottomSurface = Enum.SurfaceType.Smooth
	p.Parent = parent
	return p
end

local function makeLabel(parent, text, color, position, size)
	local label = Instance.new("TextLabel")
	label.Position = position
	label.Size = size
	label.BackgroundTransparency = 1
	label.TextScaled = true
	label.Font = Enum.Font.GothamBold
	label.TextColor3 = color
	label.TextStrokeTransparency = 0
	label.Text = text
	label.Parent = parent
	return label
end

-- Income from every employee (TycoonCore adds this to the leaderboard Income)
function EmployeeServer.getIncome(data)
	local sum = 0
	if data.team then
		for _, employee in ipairs(data.team.employees) do
			local creature = CreatureConfig.getCreature(employee.creature)
			if creature then
				sum += creature.income
			end
		end
	end
	return sum
end

local nextFixedHire -- (data, egg) -> the creature the egg's next fixed hire gives (see "Hatching")

-- What the client is allowed to see
local function snapshot(player, team)
	local data = core.getData(player)
	-- Restricted players see what each egg will give instead of odds: egg key -> creature key
	local nextHires = false
	if data and data.fixedHires and ShopServer.isRandomRestricted(player) then
		nextHires = {}
		for _, egg in ipairs(CreatureConfig.Eggs) do
			local creature = nextFixedHire(data, egg)
			nextHires[egg.key] = creature and creature.key or false
		end
	end
	local employees, incubators = {}, {}
	for _, employee in ipairs(team.employees) do
		table.insert(employees, { id = employee.id, creature = employee.creature })
	end
	for i = 1, incubatorCount(core.getData(player)) do
		local egg = team.incubators[i]
		incubators[i] = egg and { egg = egg.egg, startedAt = egg.startedAt, hatchAt = egg.hatchAt } or false
	end
	return {
		employees = employees,
		incubators = incubators,
		pending = team.pending and { id = team.pending.id, creature = team.pending.creature } or false,
		maxEmployees = maxEmployees(player),
		nextHires = nextHires,
	}
end

local function push(player)
	local team = getTeam(player)
	if team and player.Parent then
		remotes.update:FireClient(player, snapshot(player, team))
	end
end

-- Reveals wait until the player's screen is ready (e.g. eggs that auto-hatched while offline)
local function reveal(player, team, info)
	if team.clientReady then
		remotes.hatched:FireClient(player, info)
	else
		table.insert(team.revealQueue, info)
	end
end

-- Employees in the garage ------------------------------------------------

local function addNameTag(model, creature)
	local rarity = CreatureConfig.getRarity(creature.rarity)
	local gui = Instance.new("BillboardGui")
	gui.Name = "NameTag"
	gui.Size = UDim2.fromScale(7, 1.8) -- in studs, so far-away tags shrink instead of piling up
	gui.StudsOffset = Vector3.new(0, model:GetExtentsSize().Y, 0)
	gui.MaxDistance = 60
	gui.Adornee = model.PrimaryPart
	gui.Parent = model
	makeLabel(gui, creature.name, rarity and rarity.color or WHITE, UDim2.new(), UDim2.fromScale(1, 0.6))
	makeLabel(gui, creature.role .. " · $" .. creature.income .. "/s", WHITE, UDim2.fromScale(0, 0.6), UDim2.fromScale(1, 0.4))
end

local function spotFor(index)
	local lap = (index - 1) // #EMPLOYEE_SPOTS
	return EMPLOYEE_SPOTS[(index - 1) % #EMPLOYEE_SPOTS + 1] + Vector3.new(lap * 2, 0, lap * 2)
end

-- Makes the garage match the team: builds new employees, removes fired ones, lines everyone up.
-- The client makes them wander around their "Home" spot.
local function placeEmployees(data)
	local team = data.team
	local center = core.plotCenter(data.slot)
	local employed = {}
	for i, employee in ipairs(team.employees) do
		employed[employee.id] = true
		local home = center + spotFor(i) + FEET
		local model = team.models[employee.id]
		if not model then
			local creature = CreatureConfig.getCreature(employee.creature)
			model = CreatureModels.build(creature)
			addNameTag(model, creature)
			model:SetAttribute("EmployeeId", employee.id)
			model:PivotTo(CFrame.new(home) * CFrame.Angles(0, math.pi, 0)) -- face the front of the plot
			CollectionService:AddTag(model, "Employee")
			model.Parent = data.folder
			team.models[employee.id] = model
		elseif model:GetAttribute("Home") ~= home then
			model:PivotTo(CFrame.new(home) * CFrame.Angles(0, math.pi, 0))
		end
		model:SetAttribute("Home", home)
	end
	for id, model in pairs(team.models) do
		if not employed[id] then
			model:Destroy()
			team.models[id] = nil
		end
	end
end

-- Incubators on the plot ----------------------------------------------------

local function refreshIncubator(data, index, now)
	local parts = data.team.incubatorParts[index]
	if not parts then return end
	local state = data.team.incubators[index] -- false when empty
	local egg = state and CreatureConfig.getEgg(state.egg) or nil
	local ready = egg ~= nil and state.hatchAt <= now

	local text
	if not egg then
		text = "Incubator " .. index .. "\nEmpty"
	elseif ready then
		text = egg.name .. "\nREADY!"
	else
		text = egg.name .. "\n" .. CreatureConfig.formatTime(state.hatchAt - now)
	end
	if parts.label.Text ~= text then
		parts.label.Text = text
		parts.label.TextColor3 = ready and GOLD or WHITE
	end
	parts.egg.Transparency = egg and 0 or 1
	if egg then
		parts.egg.Color = egg.color
	end
	parts.prompt.Enabled = ready
	parts.prompt.ObjectText = egg and egg.name or ""
end

-- Hatching ------------------------------------------------------------------

local function newEmployee(creatureKey)
	return { id = HttpService:GenerateGUID(false), creature = creatureKey, hiredAt = os.time() }
end

-- ROLL-START
-- (tools/daily_test.py runs the code between the ROLL markers, so keep it free of Roblox calls except those it fakes.)

-- Fixed hire order (Roblox's Paid Random Items policy, FR-13, D9 option B). Luck Boost never counts
-- here (ShopServer keeps it aside for restricted players); the Talent Scouts perk does, as it does
-- for the random roll, so the order follows the same weights the server rolls with.
nextFixedHire = function(data, egg)
	local luck = 1 + IpoServer.perk(data, "BaseLuck")
	return CreatureConfig.fixedHire(egg, luck, data.fixedHires.counts[egg.key] or 0)
end

-- The random roll happens only here, on the server. A player with paid random items restricted gets
-- no roll: the egg's next fixed hire, and its counter moves on (saved in fixedHires). Nothing here
-- waits, so a save has the new hire and the new count together, or neither.
local function rollCreature(player, team, egg)
	local rarity = team.forceRarity -- set by the Studio Debug tab
	team.forceRarity = nil
	if not rarity and ShopServer.isRandomRestricted(player) then
		local data = core.getData(player)
		local creature = nextFixedHire(data, egg)
		data.fixedHires.counts[egg.key] = (data.fixedHires.counts[egg.key] or 0) + 1
		return creature
	end
	if not rarity then
		local roll = rng:NextNumber()
		local luck = ShopServer.getLuckMultiplier(player) * (1 + IpoServer.perk(core.getData(player), "BaseLuck"))
		for _, entry in ipairs(CreatureConfig.getOdds(egg, luck)) do
			rarity = entry.rarity
			roll -= entry.chance
			if roll < 0 then
				break
			end
		end
	end
	local options = CreatureConfig.creaturesOfRarity(rarity)
	return options[rng:NextInteger(1, #options)]
end
-- ROLL-END

-- Hatches a ready egg. If the team is full, the new creature waits as "pending" until the
-- player replaces someone or lets it go.
local function hatch(player, index, how)
	local team, data = getTeam(player)
	local state = team.incubators[index]
	if not state then return false, "That incubator is empty" end
	if state.hatchAt > os.time() then return false, "That egg isn't ready yet" end
	if team.pending then return false, "First decide about your waiting new hire (Team tab)" end
	local egg = CreatureConfig.getEgg(state.egg)

	local creature = rollCreature(player, team, egg)
	team.incubators[index] = false
	local employee = newEmployee(creature.key)
	local hired = #team.employees < maxEmployees(player)
	if hired then
		table.insert(team.employees, employee)
		placeEmployees(data)
		core.updateIncome(player)
	else
		team.pending = employee
	end
	refreshIncubator(data, index, os.time())
	push(player)
	reveal(player, team, { creature = creature.key, egg = egg.key, hired = hired, auto = how == "auto" })
	return true, hired and (creature.name .. " joined your team!") or "Your team is full"
end

local function removeEmployee(team, id)
	for i, employee in ipairs(team.employees) do
		if employee.id == id then
			return table.remove(team.employees, i)
		end
	end
	return nil
end

local function findEmployee(team, id)
	for _, employee in ipairs(team.employees) do
		if employee.id == id then
			return employee
		end
	end
	return nil
end

-- Actions the client can ask for ------------------------------------------------

-- The first empty incubator, or nil if they're all busy
local function freeIncubator(team, data)
	for i = 1, incubatorCount(data) do
		if not team.incubators[i] then
			return i
		end
	end
	return nil
end

-- Starts an egg's timer in an empty incubator (buying it and the free onboarding egg both use this)
local function startEgg(player, team, data, egg, index)
	local now = os.time()
	local seconds = math.ceil(egg.hatchSeconds * math.max(0, 1 - IpoServer.perk(data, "FasterEggs")))
	team.incubators[index] = { egg = egg.key, startedAt = now, hatchAt = now + seconds }
	refreshIncubator(data, index, now)
	push(player)
end

local function buyEgg(player, eggKey)
	local team, data = getTeam(player)
	local egg = typeof(eggKey) == "string" and CreatureConfig.getEgg(eggKey)
	if not egg then return false, "Unknown egg" end
	local index = freeIncubator(team, data)
	if not index then return false, "All incubators are busy" end
	if data.cash.Value < egg.price then return false, "Not enough Cash" end

	data.cash.Value -= egg.price
	startEgg(player, team, data, egg, index)
	return true, egg.name .. " is incubating"
end

-- Server only (OnboardingServer): puts a free egg in the first empty incubator, timer running.
-- No remote can call this. Returns the incubator number, or nil if there's no egg or no room.
function EmployeeServer.grantEgg(player, eggKey)
	local team, data = getTeam(player)
	local egg = team and CreatureConfig.getEgg(eggKey)
	if not egg then return nil end
	local index = freeIncubator(team, data)
	if not index then return nil end
	startEgg(player, team, data, egg, index)
	return index
end

local function instantHatch(player, index)
	local team = getTeam(player)
	local state = team.incubators[index]
	if not state then return false, "That incubator is empty" end
	if state.hatchAt <= os.time() then
		return hatch(player, index, "manual") -- already ready: don't use up a token
	end
	if team.pending then return false, "First decide about your waiting new hire (Team tab)" end
	if not ShopServer.useInstantHatch(player) then return false, "You don't have any Instant Hatches" end
	state.hatchAt = os.time()
	return hatch(player, index, "instant")
end

local function fire(player, employeeId)
	local team, data = getTeam(player)
	if typeof(employeeId) ~= "string" then return false, "Bad request" end
	local employee = removeEmployee(team, employeeId)
	if not employee then return false, "That employee isn't on your team" end
	placeEmployees(data)
	core.updateIncome(player)
	push(player)
	local creature = CreatureConfig.getCreature(employee.creature)
	return true, (creature and creature.name or "Employee") .. " left the company"
end

-- choice: "hire" (needs a free slot), "letgo", or the ID of the employee to replace
local function resolvePending(player, choice)
	local team, data = getTeam(player)
	local pending = team.pending
	if not pending then return false, "Nobody is waiting" end
	if typeof(choice) ~= "string" then return false, "Bad request" end
	local creature = CreatureConfig.getCreature(pending.creature)

	if choice == "letgo" then
		team.pending = nil
		push(player)
		return true, creature.name .. " went to work somewhere else"
	elseif choice == "hire" then
		if #team.employees >= maxEmployees(player) then return false, "Your team is still full" end
	elseif not removeEmployee(team, choice) then
		return false, "That employee isn't on your team"
	end

	team.pending = nil
	table.insert(team.employees, pending)
	placeEmployees(data)
	core.updateIncome(player)
	push(player)
	return true, creature.name .. " joined your team!"
end

-- Poaching (PoachServer moves employees between two players' teams) ---------------

function EmployeeServer.hasFreeSlot(player)
	local team = getTeam(player)
	return team ~= nil and #team.employees < maxEmployees(player)
end

-- Takes an employee off the team and returns it (nil if it isn't there).
-- keepInSave: it stays in this player's save ("outgoing") until finishRelease, so an employee
-- that is moving to another player is never lost if the server stops halfway.
function EmployeeServer.releaseEmployee(player, id, keepInSave)
	local team, data = getTeam(player)
	local employee = team and removeEmployee(team, id)
	if not employee then return nil end
	if keepInSave then
		team.outgoing[id] = employee
	end
	placeEmployees(data)
	core.updateIncome(player)
	push(player)
	return employee
end

-- The other player's save has the employee now: stop saving it here
function EmployeeServer.finishRelease(player, id)
	local team = getTeam(player)
	if team then
		team.outgoing[id] = nil
	end
end

-- Puts an employee (same ID) on the team. False if the team is full, or if this ID is already on
-- it (an employee is never on a team twice). If it was on its way out (outgoing), it's back now.
function EmployeeServer.addEmployee(player, employee)
	local team, data = getTeam(player)
	if not team or #team.employees >= maxEmployees(player) then return false end
	if findEmployee(team, employee.id) or (team.pending and team.pending.id == employee.id) then
		warn("Not adding employee " .. tostring(employee.id) .. " to " .. player.Name .. ": that ID is already on the team")
		return false
	end
	team.outgoing[employee.id] = nil -- saved once, as a team member, not also as leaving
	table.insert(team.employees, { id = employee.id, creature = employee.creature, hiredAt = os.time() })
	placeEmployees(data)
	core.updateIncome(player)
	push(player)
	return true
end

local ACTIONS = {
	BuyEgg = buyEgg,
	Hatch = function(player, index)
		return hatch(player, index, "manual")
	end,
	InstantHatch = instantHatch,
	Fire = fire,
	ResolvePending = resolvePending,
}

local function onAction(player, action, arg)
	if typeof(action) ~= "string" then return false, "Bad request" end
	local team, data = getTeam(player)
	if not team or not data.ready then
		return false, IpoServer.isBusy(data) and "Your IPO is being filed, one moment" or "Still loading, try again in a moment"
	end

	if action == "Sync" then
		-- The screen is ready: send the state and any reveals that happened before it was
		team.clientReady = true
		push(player)
		for _, info in ipairs(team.revealQueue) do
			remotes.hatched:FireClient(player, info)
		end
		table.clear(team.revealQueue)
		return true
	end
	if action == "Hatch" or action == "InstantHatch" then
		if typeof(arg) ~= "number" or arg % 1 ~= 0 or arg < 1 or arg > incubatorCount(data) then
			return false, "Bad request"
		end
	end
	local handler = ACTIONS[action]
	if not handler then return false, "Unknown action" end
	return handler(player, arg)
end

-- Saving (TycoonCore calls these) ----------------------------------------------

-- One incubator on the back of the plot. Walk up to a ready egg to hatch it.
local function buildIncubator(player, data, i)
	local team = data.team
	local spot = core.plotCenter(data.slot) + (INCUBATOR_SPOTS[i] or Vector3.new(-12 + (i - 1) * 12, 0, -25))
	local base = makePart(data.folder, "Incubator" .. i, Vector3.new(5, 1, 5), spot + Vector3.new(0, 1, 0), Color3.fromRGB(60, 62, 72), Enum.Material.Metal)
	local glow = makePart(data.folder, "IncubatorGlow", Vector3.new(4.4, 0.2, 4.4), spot + Vector3.new(0, 1.6, 0), Color3.fromRGB(90, 200, 255), Enum.Material.Neon)
	local egg = makePart(data.folder, "IncubatorEgg", Vector3.new(2.4, 3.2, 2.4), spot + Vector3.new(0, 3.3, 0), WHITE)
	egg.CanCollide = false
	local mesh = Instance.new("SpecialMesh")
	mesh.MeshType = Enum.MeshType.Sphere
	mesh.Parent = egg

	local gui = Instance.new("BillboardGui")
	gui.Size = UDim2.fromScale(7, 2.4) -- in studs, like the employee name tags
	gui.StudsOffset = Vector3.new(0, 5.5, 0)
	gui.MaxDistance = 80
	gui.Parent = base
	local label = makeLabel(gui, "", WHITE, UDim2.new(), UDim2.fromScale(1, 1))

	local prompt = Instance.new("ProximityPrompt")
	prompt.ActionText = "Hatch"
	prompt.HoldDuration = 0
	prompt.MaxActivationDistance = 12
	prompt.RequiresLineOfSight = false
	prompt.Enabled = false
	prompt:SetAttribute("OwnerUserId", player.UserId) -- other players' screens hide it
	CollectionService:AddTag(prompt, "IncubatorPrompt")
	prompt.Parent = base
	prompt.Triggered:Connect(function(who)
		if who == player and data.ready then
			hatch(player, i, "prompt")
		end
	end)

	team.incubatorParts[i] = { base = base, glow = glow, egg = egg, label = label, prompt = prompt }
	refreshIncubator(data, i, os.time())
end

-- Called right after the player's save loads. savedTeam is the "team" part of the save, or nil
-- (old saves from before milestone 2 simply start with an empty team).
function EmployeeServer.setupPlayer(player, data, savedTeam)
	local team = {
		employees = {}, -- { id, creature, hiredAt } (saved)
		incubators = {}, -- [1..incubatorCount] = { egg, startedAt, hatchAt } or false (saved)
		parked = {}, -- incubator number -> egg above incubatorCount: still saved, back in place when the perk is (saved)
		pending = nil, -- a hatched creature waiting for a free desk (saved)
		outgoing = {}, -- employee ID -> employee being poached away: still saved here until the new owner's save has it
		models = {}, -- employee ID -> Model in the garage
		incubatorParts = {},
		revealQueue = {},
		clientReady = false,
		forceRarity = nil, -- Studio Debug tab only
	}
	local count = incubatorCount(data)
	for i = 1, count do
		team.incubators[i] = false
	end
	if typeof(savedTeam) == "table" then
		local seen = {} -- employee IDs already loaded: a save with the same ID twice keeps only the first
		for _, e in ipairs(typeof(savedTeam.employees) == "table" and savedTeam.employees or {}) do
			if typeof(e) == "table" and typeof(e.id) == "string" and seen[e.id] then
				warn("Skipped a duplicate employee in " .. player.Name .. "'s save: " .. e.id)
			elseif typeof(e) == "table" and typeof(e.id) == "string" and CreatureConfig.getCreature(e.creature) then
				seen[e.id] = true
				table.insert(team.employees, { id = e.id, creature = e.creature, hiredAt = e.hiredAt or 0 })
			else
				warn("Skipped an employee with an unknown creature: " .. tostring(typeof(e) == "table" and e.creature))
			end
		end
		for i, state in ipairs(typeof(savedTeam.incubators) == "table" and savedTeam.incubators or {}) do
			if typeof(state) == "table" and CreatureConfig.getEgg(state.egg) then
				local egg = { egg = state.egg, startedAt = state.startedAt or 0, hatchAt = state.hatchAt or 0 }
				if i <= count then
					team.incubators[i] = egg
				else
					team.parked[i] = egg -- e.g. incubators 4-5 while the Extra Incubator perk didn't load: never deleted
				end
			end
		end
		local p = savedTeam.pending
		if typeof(p) == "table" and typeof(p.id) == "string" and seen[p.id] then
			warn("Skipped a waiting employee in " .. player.Name .. "'s save: it's already on the team (" .. p.id .. ")")
		elseif typeof(p) == "table" and typeof(p.id) == "string" and CreatureConfig.getCreature(p.creature) then
			team.pending = { id = p.id, creature = p.creature, hiredAt = p.hiredAt or 0 }
		end
	end
	data.team = team

	-- Incubators on the back of the plot. Walk up to a ready egg to hatch it.
	for i = 1, count do
		buildIncubator(player, data, i)
	end

	placeEmployees(data)
end

-- The part of the save file that belongs to eggs and employees
function EmployeeServer.serialize(data)
	local team = data.team
	if not team then return nil end
	local employees, incubators = {}, {}
	for _, e in ipairs(team.employees) do
		table.insert(employees, { id = e.id, creature = e.creature, hiredAt = e.hiredAt })
	end
	for _, e in pairs(team.outgoing) do -- being poached: see releaseEmployee
		table.insert(employees, { id = e.id, creature = e.creature, hiredAt = e.hiredAt })
	end
	local count = incubatorCount(data)
	local last = count
	for i in pairs(team.parked) do
		last = math.max(last, i)
	end
	for i = 1, last do -- parked eggs above the current count are saved too (false fills the gaps)
		local egg = team.incubators[i]
		if i > count then
			egg = team.parked[i]
		end
		incubators[i] = egg and { egg = egg.egg, startedAt = egg.startedAt, hatchAt = egg.hatchAt } or false
	end
	local p = team.pending
	return {
		employees = employees,
		incubators = incubators, -- hatch times are real clock times, so eggs keep hatching while you're offline
		pending = p and { id = p.id, creature = p.creature, hiredAt = p.hiredAt } or nil,
	}
end

-- FIXEDSAVE-START
-- (tools/daily_test.py runs the code between the FIXEDSAVE markers, so keep it free of Roblox calls except warn.)
-- The fixed hire order's counters have their own top-level save section, "fixedHires" (CLAUDE.md rule
-- A10: older code keeps an unknown section as it is, but drops unknown fields inside "team"). They
-- count hires ever, not per run, so an IPO doesn't touch them and older code keeping them frozen is fine.

-- Called right after the player's save loads, before setupPlayer (a free egg can hatch right away).
-- savedFixed is the "fixedHires" part of the save, or nil (saves from before D9, and new players):
-- every egg then starts at the first hire of its order. Bad values are skipped with a warning.
function EmployeeServer.setupFixedHires(player, data, savedFixed)
	local fixed = {
		counts = {}, -- egg key -> hires already made from that egg's fixed order (saved; unknown eggs too)
		unknown = {}, -- fields of the saved section this version doesn't know (saved back as they were)
	}
	if typeof(savedFixed) == "table" then
		local counts = savedFixed.counts
		if typeof(counts) == "table" then
			for eggKey, value in pairs(counts) do
				if typeof(eggKey) == "string" and typeof(value) == "number" and value == value
					and value >= 0 and value < math.huge and value % 1 == 0 then
					fixed.counts[eggKey] = value
				else
					warn("Skipped a bad fixedHires count in " .. player.Name .. "'s save: " .. tostring(eggKey) .. " = " .. tostring(value))
				end
			end
		elseif counts ~= nil then
			warn("Skipped bad fixedHires counts in " .. player.Name .. "'s save")
		end
		for key, value in pairs(savedFixed) do
			if key ~= "counts" then
				fixed.unknown[key] = value
			end
		end
	elseif savedFixed ~= nil then
		warn("Skipped a bad fixedHires section in " .. player.Name .. "'s save")
	end
	data.fixedHires = fixed
end

-- The "fixedHires" part of the save file, or nil when there's nothing in it (most players never use it)
function EmployeeServer.serializeFixedHires(data)
	local fixed = data.fixedHires
	if not fixed or (next(fixed.counts) == nil and next(fixed.unknown) == nil) then
		return nil
	end
	local section = { counts = {} }
	for eggKey, count in pairs(fixed.counts) do
		section.counts[eggKey] = count
	end
	for key, value in pairs(fixed.unknown) do -- written by newer code: kept as it was
		if section[key] == nil then
			section[key] = value
		end
	end
	return section
end
-- FIXEDSAVE-END

-- IPO (IpoServer and TycoonCore call these) ----------------------------------------

-- The eggs going public would clear: (still incubating, ready to hatch). Parked eggs count too.
function EmployeeServer.countEggs(player)
	local team = getTeam(player)
	if not team then return 0, 0 end
	local now = os.time()
	local incubating, ready = 0, 0
	local function add(egg)
		if egg then
			if egg.hatchAt <= now then
				ready += 1
			else
				incubating += 1
			end
		end
	end
	for i = 1, #team.incubators do
		add(team.incubators[i])
	end
	for _, egg in pairs(team.parked) do
		add(egg)
	end
	return incubating, ready
end

-- Going public empties every incubator (the eggs are part of the run that resets)
function EmployeeServer.clearIncubators(player)
	local team, data = getTeam(player)
	if not team then return end
	local now = os.time()
	for i = 1, #team.incubators do
		team.incubators[i] = false
		refreshIncubator(data, i, now)
	end
	table.clear(team.parked)
	push(player)
end

-- After an IPO perk changes: builds new incubators, with any parked egg back in them (or, after
-- the Studio Debug reset, removes extra ones and parks their eggs) and sends the new desk count
function EmployeeServer.refreshCapacity(player)
	local team, data = getTeam(player)
	if not team then return end
	local count = incubatorCount(data)
	for i = #team.incubators + 1, count do
		team.incubators[i] = team.parked[i] or false
		team.parked[i] = nil
		buildIncubator(player, data, i)
	end
	for i = #team.incubators, count + 1, -1 do
		local parts = team.incubatorParts[i]
		if parts then
			parts.base:Destroy()
			parts.glow:Destroy()
			parts.egg:Destroy()
			team.incubatorParts[i] = nil
		end
		team.parked[i] = team.incubators[i] or nil
		team.incubators[i] = nil
	end
	push(player)
end

-- Setup -----------------------------------------------------------------

function EmployeeServer.init(coreApi)
	core = coreApi

	local folder = Instance.new("Folder")
	folder.Name = "EmployeeRemotes"
	remotes.action = Instance.new("RemoteFunction")
	remotes.action.Name = "TeamAction"
	remotes.action.OnServerInvoke = onAction
	remotes.action.Parent = folder
	remotes.update = Instance.new("RemoteEvent")
	remotes.update.Name = "TeamUpdate"
	remotes.update.Parent = folder
	remotes.hatched = Instance.new("RemoteEvent")
	remotes.hatched.Name = "EggHatched"
	remotes.hatched.Parent = folder
	folder.Parent = ReplicatedStorage

	-- Studio-only buttons in the shop's Debug tab
	if RunService:IsStudio() then
		ShopServer.addDebugAction("GiveCash", function(_, data, amount)
			amount = tonumber(amount)
			if not amount or amount <= 0 or amount > 1e9 then return "Bad amount" end
			data.cash.Value += math.floor(amount)
			return "Gave $" .. math.floor(amount)
		end)
		ShopServer.addDebugAction("ForceRarity", function(_, data, rarityKey)
			if #CreatureConfig.creaturesOfRarity(rarityKey) == 0 then return "Unknown rarity" end
			data.team.forceRarity = rarityKey
			return "Your next hatch will be " .. rarityKey
		end)
		ShopServer.addDebugAction("SkipEggTimers", function(player, data)
			local now, skipped = os.time(), 0
			for i = 1, incubatorCount(data) do
				local state = data.team.incubators[i]
				if state and state.hatchAt > now then
					state.hatchAt = now
					skipped += 1
				end
			end
			push(player)
			return skipped .. " egg timer(s) skipped"
		end)
	end

	-- Every second: count down incubator labels, and auto-hatch for Auto-Hatch pass owners
	task.spawn(function()
		while true do
			task.wait(1)
			local now = os.time()
			for _, player in ipairs(Players:GetPlayers()) do
				local team, data = getTeam(player)
				if team and data.ready then
					for i = 1, incubatorCount(data) do
						local state = team.incubators[i]
						if state and state.hatchAt <= now and not team.pending
							and #team.employees < maxEmployees(player) and ShopServer.hasAutoHatch(player) then
							hatch(player, i, "auto")
						end
						refreshIncubator(data, i, now)
					end
				end
			end
		end
	end)
end

return EmployeeServer
