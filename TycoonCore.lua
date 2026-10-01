-- TycoonCore: Startup to IPO, milestone 1 (garage stage) + hooks for employees (milestone 2) and the shop (milestone 3)
-- Put this Script in ServerScriptService. It builds everything by itself.
-- Game passes and developer products live in ShopServer (ServerScriptService) and ShopConfig (ReplicatedStorage).
-- Eggs and creature employees live in EmployeeServer (ServerScriptService) and CreatureConfig (ReplicatedStorage).
-- Poaching and the HR Department live in PoachServer (ServerScriptService) and CreatureConfig.Poaching.
-- Valuation, the IPO rebirth and the IPO shop live in IpoServer (ServerScriptService) and IpoConfig (ReplicatedStorage).

local Players = game:GetService("Players")
local DataStoreService = game:GetService("DataStoreService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

-- GetDataStore errors when the place isn't published, so it's wrapped in pcall too.
-- If it fails, the game still runs but progress isn't loaded or saved.
local storeOk, store = pcall(function()
	return DataStoreService:GetDataStore("StartupTycoon_v1")
end)
if not storeOk then
	warn("DataStore unavailable, progress will not be saved: " .. tostring(store))
	store = nil
end

local IpoConfig = require(ReplicatedStorage:WaitForChild("IpoConfig"))
local ShopServer = require(script.Parent:WaitForChild("ShopServer"))
local IpoServer = require(script.Parent:WaitForChild("IpoServer"))
local EmployeeServer = require(script.Parent:WaitForChild("EmployeeServer"))
local PoachServer = require(script.Parent:WaitForChild("PoachServer"))

-- Upgrades are bought in this order. cost = Cash, income = Cash per second.
local UPGRADES = {
	{ name = "Desk",           cost = 0,    income = 1,   color = Color3.fromRGB(160, 110, 60),  size = Vector3.new(6, 3, 4) },
	{ name = "Coffee Machine", cost = 25,   income = 2,   color = Color3.fromRGB(60, 60, 60),    size = Vector3.new(2, 4, 2) },
	{ name = "Laptop",         cost = 100,  income = 5,   color = Color3.fromRGB(200, 200, 210), size = Vector3.new(3, 1, 2) },
	{ name = "Server Rack",    cost = 400,  income = 15,  color = Color3.fromRGB(30, 30, 40),    size = Vector3.new(4, 8, 3) },
	{ name = "Whiteboard",     cost = 1500, income = 40,  color = Color3.fromRGB(245, 245, 245), size = Vector3.new(8, 5, 1) },
	{ name = "Neon Logo",      cost = 5000, income = 120, color = Color3.fromRGB(0, 170, 255),   size = Vector3.new(10, 4, 1) },
}

local PLOT_SPACING = 90
local MAX_PLOTS = 6
local OFFLINE_CAP_SECONDS = 8 * 60 * 60 -- max 8 hours of offline earnings (the Night Shift IPO perk adds more)
local OFFLINE_RATE = 0.5 -- offline you earn 50% of normal income

local plotOwners = {} -- slot number -> player
local playerData = {} -- player -> { owned, items, slot, folder, pad, cash, income, shop, team, poach, ipo, loaded, ready, saving }

-- Helpers ---------------------------------------------------------------

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

local function addLabel(part, text, height)
	local gui = Instance.new("BillboardGui")
	gui.Size = UDim2.fromOffset(220, 50)
	gui.StudsOffset = Vector3.new(0, height or 3, 0)
	gui.AlwaysOnTop = true
	gui.Parent = part
	local label = Instance.new("TextLabel")
	label.Size = UDim2.fromScale(1, 1)
	label.BackgroundTransparency = 1
	label.TextScaled = true
	label.Font = Enum.Font.GothamBold
	label.TextColor3 = Color3.new(1, 1, 1)
	label.TextStrokeTransparency = 0
	label.Text = text
	label.Parent = gui
	return label
end

local function plotCenter(slot)
	local startX = -((MAX_PLOTS - 1) * PLOT_SPACING) / 2
	return Vector3.new(startX + (slot - 1) * PLOT_SPACING, 0.5, 150)
end

local function itemOffset(i)
	local col = (i - 1) % 3
	local row = math.floor((i - 1) / 3)
	return Vector3.new(-18 + col * 18, 0, -14 + row * 16)
end

local function totalIncome(data)
	local sum = 0
	for _, upg in ipairs(UPGRADES) do
		if data.owned[upg.name] then
			sum += upg.income
		end
	end
	return sum + EmployeeServer.getIncome(data) -- creature employees earn too
end

-- The Income on the leaderboard already includes game pass bonuses (2x Cash, VIP) and the IPO multiplier
local function updateIncome(player)
	local data = playerData[player]
	if not data then return end
	data.income.Value = math.floor(totalIncome(data) * ShopServer.getCashMultiplier(player) * IpoServer.getMultiplier(player))
end

local function nextUpgrade(data)
	for i, upg in ipairs(UPGRADES) do
		if not data.owned[upg.name] then
			return i, upg
		end
	end
	return nil
end

local function spawnItem(data, i, upg)
	local pos = plotCenter(data.slot) + itemOffset(i) + Vector3.new(0, 0.5 + upg.size.Y / 2, 0)
	local item = makePart(data.folder, upg.name, upg.size, pos, upg.color)
	if upg.name == "Neon Logo" then
		item.Material = Enum.Material.Neon
	end
	data.items[upg.name] = item
end

-- The green pad always sells the next upgrade in the list.
local function refreshPad(player)
	local data = playerData[player]
	if not data then return end
	if data.pad then
		data.pad:Destroy()
		data.pad = nil
	end

	local i, upg = nextUpgrade(data)
	if not i then return end -- everything bought

	local pos = plotCenter(data.slot) + Vector3.new(0, 0.6, 24)
	local pad = makePart(data.folder, "BuyPad", Vector3.new(8, 0.2, 8), pos, Color3.fromRGB(0, 200, 90), Enum.Material.Neon)
	addLabel(pad, string.format("Buy %s\n$%d  (+$%d/s)", upg.name, upg.cost, upg.income), 4)
	data.pad = pad

	local busy = false
	pad.Touched:Connect(function(hit)
		if busy or not data.ready then return end -- not ready: loading, or an IPO is being saved
		if Players:GetPlayerFromCharacter(hit.Parent) ~= player then return end
		local cash = player.leaderstats.Cash
		if cash.Value < upg.cost then return end

		busy = true
		cash.Value -= upg.cost
		data.owned[upg.name] = true
		updateIncome(player)
		spawnItem(data, i, upg)
		refreshPad(player)
	end)
end

-- Saving and loading ----------------------------------------------------

local function load(player)
	if not store then return nil, false end -- no DataStore: play fresh, never save
	local ok, result = pcall(function()
		return store:GetAsync("player_" .. player.UserId)
	end)
	if not ok then
		warn("Could not load data. In Studio, turn on API access. Error: " .. tostring(result))
		return nil, false
	end
	return result, true
end

-- Reads someone else's save without loading it. Poaching uses it to check that an employee
-- moving between two players was saved on both sides. Returns (save or nil, worked).
local function peekSave(userId)
	if not store then return nil, false end
	local ok, result = pcall(function()
		return store:GetAsync("player_" .. userId)
	end)
	if not ok then
		warn("Could not read a save for a poaching check: " .. tostring(result))
		return nil, false
	end
	return result, true
end

-- Returns true if the save worked (the shop needs to know before confirming a purchase).
-- transform (IPO only) changes the payload before it's written: see commitIpo.
local function save(player, transform)
	local data = playerData[player]
	if not data or not data.loaded then return false end -- never overwrite data we failed to load

	-- One save at a time per player, so an older save can never land after a newer one
	while data.saving do
		task.wait()
	end
	data.saving = true

	local owned = {}
	for name in pairs(data.owned) do
		table.insert(owned, name)
	end
	local payload = {
		cash = data.cash.Value,
		owned = owned,
		lastSeen = os.time(),
		shop = ShopServer.serialize(data),
		team = EmployeeServer.serialize(data),
		poach = PoachServer.serialize(data),
		ipo = IpoServer.serialize(data),
	}
	if transform then
		transform(payload)
	end
	local ok, err
	if transform and data.debugFailIpoSave then -- Studio Debug tab only: test the IPO failure path
		data.debugFailIpoSave = nil
		ok, err = false, "simulated failure (Studio Debug tab)"
	else
		ok, err = pcall(function()
			store:SetAsync("player_" .. player.UserId, payload)
		end)
	end
	data.saving = false
	if not ok then
		warn("Save failed for " .. player.Name .. ": " .. tostring(err))
	end
	return ok
end

-- IPO (milestone 4) -----------------------------------------------------

-- Going public: the save is written first with the reset already in it (Cash, garage upgrades,
-- eggs in incubators, HR Department, and IpoServer's new "ipo" section). Only if that worked
-- does the game change to match. If it failed, nothing changed. Nothing here waits after the
-- save, so a save that is waiting behind this one (autosave, leaving) always sees the result.
local function commitIpo(player, newIpo)
	local data = playerData[player]
	if not data then return false end
	local ok = save(player, function(payload)
		payload.cash = IpoConfig.StartingCash
		payload.owned = {}
		if payload.team then
			for i in ipairs(payload.team.incubators) do
				payload.team.incubators[i] = false
			end
		end
		if payload.poach then
			payload.poach.hrLevel = 0
		end
		payload.ipo = newIpo
	end)
	if not ok or playerData[player] ~= data then
		return ok
	end

	data.cash.Value = IpoConfig.StartingCash
	table.clear(data.owned)
	for name, item in pairs(data.items) do
		item:Destroy()
		data.items[name] = nil
	end
	EmployeeServer.clearIncubators(player)
	PoachServer.resetHrDepartment(player)
	updateIncome(player)
	refreshPad(player)
	return true
end

-- Cash the startup earned (not refunds or gifts): raises the valuation
local function addEarnings(player, amount)
	IpoServer.addEarnings(player, amount)
end

IpoServer.init({
	getData = function(player)
		return playerData[player]
	end,
	save = save,
	updateIncome = updateIncome,
	plotCenter = plotCenter,
	commitIpo = commitIpo,
	isPoachBusy = function(player)
		return PoachServer.isBusy(player)
	end,
	onPerksChanged = function(player)
		EmployeeServer.refreshCapacity(player) -- extra incubators and desks
		updateIncome(player)
	end,
})

-- Shop (milestone 3) -----------------------------------------------------

ShopServer.init({
	getData = function(player)
		return playerData[player]
	end,
	save = save,
	updateIncome = updateIncome,
	addEarnings = addEarnings,
})

-- Eggs and employees (milestone 2) --------------------------------------

EmployeeServer.init({
	getData = function(player)
		return playerData[player]
	end,
	save = save,
	updateIncome = updateIncome,
	plotCenter = plotCenter,
})

-- Poaching (milestone 3 poaching) ---------------------------------------

PoachServer.init({
	getData = function(player)
		return playerData[player]
	end,
	save = save,
	updateIncome = updateIncome,
	plotCenter = plotCenter,
	peekSave = peekSave,
})

-- Players joining and leaving -------------------------------------------

local function teleportToPlot(character, slot)
	local root = character:WaitForChild("HumanoidRootPart")
	task.wait(0.1)
	-- Land a few studs in front of the green pad (not on it, or it would auto-buy), facing it
	local spawnPos = plotCenter(slot) + Vector3.new(0, 4, 12)
	local padPos = plotCenter(slot) + Vector3.new(0, 4, 24)
	root.CFrame = CFrame.lookAt(spawnPos, padPos)
end

Players.PlayerAdded:Connect(function(player)
	local slot
	for s = 1, MAX_PLOTS do
		if not plotOwners[s] then
			slot = s
			break
		end
	end
	if not slot then
		player:Kick("This server is full, please join another one.")
		return
	end
	plotOwners[slot] = player

	local leaderstats = Instance.new("Folder")
	leaderstats.Name = "leaderstats"
	leaderstats.Parent = player

	local cash = Instance.new("IntValue")
	cash.Name = "Cash"
	cash.Parent = leaderstats

	local income = Instance.new("IntValue")
	income.Name = "Income"
	income.Parent = leaderstats

	local folder = Instance.new("Folder")
	folder.Name = player.Name .. "_Startup"
	folder.Parent = workspace

	local data = { owned = {}, items = {}, slot = slot, folder = folder, cash = cash, income = income, loaded = false }
	playerData[player] = data

	local floor = makePart(folder, "Floor", Vector3.new(60, 1, 60), plotCenter(slot), Color3.fromRGB(90, 90, 100))
	addLabel(floor, player.DisplayName .. "'s Startup", 12)

	local saved, ok = load(player)
	data.loaded = ok
	if saved then
		cash.Value = saved.cash or 0
		for _, name in ipairs(saved.owned or {}) do
			data.owned[name] = true
		end
	end
	ShopServer.setupPlayer(player, data, saved and saved.shop) -- passes, boosts and past receipts
	-- Saves from before milestone 4 have no valuation: count the upgrades they bought plus their Cash
	local legacyValuation = 0
	if saved and saved.ipo == nil then
		legacyValuation = cash.Value
		for _, upg in ipairs(UPGRADES) do
			if data.owned[upg.name] then
				legacyValuation += upg.cost
			end
		end
	end
	IpoServer.setupPlayer(player, data, saved and saved.ipo, legacyValuation) -- before employees: perks change slots
	EmployeeServer.setupPlayer(player, data, saved and saved.team) -- employees and eggs (after passes: slots)
	PoachServer.setupPlayer(player, data, saved and saved.poach, ok and saved == nil) -- after employees

	for i, upg in ipairs(UPGRADES) do
		if data.owned[upg.name] then
			spawnItem(data, i, upg)
		end
	end
	updateIncome(player)

	-- Offline earnings: the startup keeps making money while you're away
	if saved and saved.lastSeen then
		local cap = OFFLINE_CAP_SECONDS + IpoServer.perk(data, "OfflineCap")
		local away = math.clamp(os.time() - saved.lastSeen, 0, cap)
		local earned = math.floor(away * income.Value * OFFLINE_RATE)
		if earned > 0 then
			cash.Value += earned
			addEarnings(player, earned)
			print(player.Name .. " earned $" .. earned .. " while offline")
		end
	end

	refreshPad(player)
	data.ready = true -- the shop waits for this before granting purchases

	player.CharacterAdded:Connect(function(character)
		teleportToPlot(character, slot)
	end)
	if player.Character then
		task.spawn(teleportToPlot, player.Character, slot)
	end
end)

Players.PlayerRemoving:Connect(function(player)
	save(player)
	local data = playerData[player]
	if data then
		data.folder:Destroy()
		plotOwners[data.slot] = nil
		playerData[player] = nil
	end
end)

-- Passive income every second (paused while loading, and while an IPO is being saved)
task.spawn(function()
	while true do
		task.wait(1)
		for player, data in pairs(playerData) do
			local stats = player:FindFirstChild("leaderstats")
			if stats and data.ready then
				stats.Cash.Value += stats.Income.Value
				addEarnings(player, stats.Income.Value)
			end
		end
	end
end)

-- Autosave every minute, and on shutdown
task.spawn(function()
	while true do
		task.wait(60)
		for player in pairs(playerData) do
			save(player)
		end
	end
end)

game:BindToClose(function()
	for player in pairs(playerData) do
		save(player)
	end
end)
