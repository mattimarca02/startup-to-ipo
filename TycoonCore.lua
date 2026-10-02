-- TycoonCore: Startup to IPO, milestone 1 (garage stage) + hooks for employees (milestone 2) and the shop (milestone 3)
-- Put this Script in ServerScriptService. It builds everything by itself.
-- Game passes and developer products live in ShopServer (ServerScriptService) and ShopConfig (ReplicatedStorage).
-- Eggs and creature employees live in EmployeeServer (ServerScriptService) and CreatureConfig (ReplicatedStorage).
-- Poaching and the HR Department live in PoachServer (ServerScriptService) and CreatureConfig.Poaching.
-- Valuation, the IPO rebirth and the IPO shop live in IpoServer (ServerScriptService) and IpoConfig (ReplicatedStorage).
-- The first minute for new players (free egg, arrow, goals) lives in OnboardingServer (ServerScriptService) and OnboardingConfig (ReplicatedStorage).
-- The 7-day login calendar lives in DailyServer (ServerScriptService) and DailyConfig (ReplicatedStorage).

local Players = game:GetService("Players")
local DataStoreService = game:GetService("DataStoreService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")

-- GetDataStore errors when the place isn't published, or when Roblox is briefly unavailable, so
-- it's wrapped in pcall and looked up lazily: every call tries again until one works, so a
-- server whose store comes back heals by itself. load, peekSave and save all go through it.
-- Without a store, Studio plays without saving; a live server waits a little for it in load()
-- and then kicks the joining player, so nobody plays a session that can never be saved.
-- GETSTORE-START
local store
local function getStore()
	if store then return store end
	local storeOk, result = pcall(function()
		return DataStoreService:GetDataStore("StartupTycoon_v1")
	end)
	if storeOk then
		store = result
	else
		warn("DataStore unavailable: " .. tostring(result))
	end
	return store
end
-- GETSTORE-END
if not getStore() then
	if RunService:IsStudio() then
		warn("No DataStore: this Studio session will play WITHOUT saving. Publish the place and turn on Game Settings > Security > Enable Studio Access to API Services to test saving.")
	else
		warn("No DataStore yet on a live server: joining players wait for it, then are kicked if it never comes.")
	end
end

local IpoConfig = require(ReplicatedStorage:WaitForChild("IpoConfig"))
local ShopServer = require(script.Parent:WaitForChild("ShopServer"))
local IpoServer = require(script.Parent:WaitForChild("IpoServer"))
local EmployeeServer = require(script.Parent:WaitForChild("EmployeeServer"))
local PoachServer = require(script.Parent:WaitForChild("PoachServer"))
local OnboardingServer = require(script.Parent:WaitForChild("OnboardingServer"))
local DailyServer = require(script.Parent:WaitForChild("DailyServer"))

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
local LOAD_TRIES = 3 -- reads of a joining player's save before giving up and kicking them
local LOAD_FAILED_MESSAGE = "Your startup couldn't load. Please rejoin in a moment: your progress is safe."

-- The parts of the save this version writes. Any other part of a loaded save was written by
-- newer (or other) code: it's kept and written back unchanged, never deleted.
local KNOWN_SECTIONS = { cash = true, owned = true, lastSeen = true, shop = true, team = true, poach = true, ipo = true, onboarding = true, daily = true, fixedHires = true }

local plotOwners = {} -- slot number -> player
local playerData = {} -- player -> { owned, items, slot, folder, pad, cash, income, shop, team, fixedHires, poach, ipo, onboarding, daily, unknownSections, loaded, ready, saving }

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

-- Reads the basic fields of a loaded save, skipping bad values with a warning instead of erroring.
-- A corrupt field must never lock a player out: it gets a safe default (0 Cash, no upgrades, no offline time).
-- Returns cash (a whole number >= 0), a list of upgrade names, and lastSeen (a number or nil).
-- (tools/daily_test.py runs the code between the two SANITIZE markers, so keep it free of Roblox calls except warn.)
-- SANITIZE-BEGIN
local MAX_CASH = 2 ^ 53 -- Cash is a whole number; far above anything the game can earn
local function sanitizeSave(saved, playerName)
	local cash, owned, lastSeen = 0, {}, nil
	local rawCash = tonumber(saved.cash)
	if rawCash ~= nil and rawCash == rawCash and rawCash >= 0 and rawCash ~= math.huge then -- not NaN, not negative, not inf
		cash = math.floor(math.min(rawCash, MAX_CASH))
	elseif saved.cash ~= nil then
		warn("Ignoring a bad Cash value in " .. playerName .. "'s save: " .. tostring(saved.cash))
	end
	if typeof(saved.owned) == "table" then
		for _, name in ipairs(saved.owned) do
			if typeof(name) == "string" then
				table.insert(owned, name)
			else
				warn("Skipping a bad upgrade name in " .. playerName .. "'s save: " .. tostring(name))
			end
		end
	elseif saved.owned ~= nil then
		warn("Ignoring a bad upgrade list in " .. playerName .. "'s save: " .. tostring(saved.owned))
	end
	local rawSeen = tonumber(saved.lastSeen)
	if rawSeen ~= nil and rawSeen == rawSeen and rawSeen ~= math.huge and rawSeen ~= -math.huge then
		lastSeen = rawSeen
	elseif saved.lastSeen ~= nil then
		warn("Ignoring a bad lastSeen value in " .. playerName .. "'s save: " .. tostring(saved.lastSeen))
	end
	return cash, owned, lastSeen
end
-- SANITIZE-END

-- A save that exists but isn't a table is unreadable, not "a new player": it counts as a failed
-- load (no free egg, no shield, and data.loaded stays false so nothing overwrites it). A missing
-- save (nil) stays a genuine new player.
-- READABLE-START
local function readableSave(saved, ok, name)
	if ok and saved ~= nil and typeof(saved) ~= "table" then
		warn("Not using " .. name .. "'s save: it isn't a table (" .. typeof(saved) .. ")")
		return false
	end
	return ok
end
-- READABLE-END

-- Returns (save or nil, worked). A failed read is tried again (LOAD_TRIES in all, waiting a bit
-- longer each time). If it still fails, the player is kicked (see PlayerAdded), never left
-- playing a session that can't save.
local function load(player)
	for attempt = 1, LOAD_TRIES do
		local currentStore = getStore()
		if not currentStore and RunService:IsStudio() then
			return nil, false -- Studio without a DataStore plays unsaved (PlayerAdded allows it)
		end
		local ok, result
		if currentStore then
			ok, result = pcall(function()
				return currentStore:GetAsync("player_" .. player.UserId)
			end)
			if ok then
				return result, true
			end
		else
			result = "no DataStore yet"
		end
		warn(string.format("Could not load %s's data (try %d of %d). In Studio, turn on API access. Error: %s",
			player.Name, attempt, LOAD_TRIES, tostring(result)))
		if attempt == LOAD_TRIES or not player.Parent then break end
		task.wait(attempt * 2) -- 2s, then 4s
	end
	return nil, false
end

-- REREAD-START
-- (tools/daily_test.py runs the code between the REREAD markers.)
-- There's no session lock yet (F10). A save written in the last REREAD_RECENT_SECONDS may come from a
-- session that is still closing on another server (a second device, a quick rejoin): its leave save
-- usually lands within a few seconds. Joining reads such a save again after REREAD_WAIT_SECONDS, so the
-- other server's last minute (and a purchase made there) isn't overwritten. A clean join after a
-- longer break doesn't wait. lastSeen within a few seconds in the future (another server's clock) counts.
local REREAD_RECENT_SECONDS = 75 -- autosave is every 60 s, so a live session's save is never older
local REREAD_WAIT_SECONDS = 7
local function shouldReread(saved, now)
	if typeof(saved) ~= "table" then return false end
	local seen = tonumber(saved.lastSeen)
	return seen ~= nil and seen == seen and math.abs(now - seen) < REREAD_RECENT_SECONDS
end
-- REREAD-END

-- Reads someone else's save without loading it. Poaching uses it to check that an employee
-- moving between two players was saved on both sides. Returns (save or nil, worked).
local function peekSave(userId)
	local currentStore = getStore()
	if not currentStore then return nil, false end
	local ok, result = pcall(function()
		return currentStore:GetAsync("player_" .. userId)
	end)
	if not ok then
		warn("Could not read a save for a poaching check: " .. tostring(result))
		return nil, false
	end
	return result, true
end

-- BUILDSAVE-START
-- (tools/daily_test.py runs the code between the BUILDSAVE markers, so keep it free of Roblox calls except warn.)
-- Builds the payload save() writes, inside a pcall. If a module's serialize or the IPO transform throws,
-- nothing is written (the payload only exists as a whole, never half-built), the one-save-at-a-time lock
-- is released so a later save (autosave, the one on leave) isn't stuck behind it forever, and this
-- returns nil. The caller must have set data.saving = true.
local function buildPayload(data, transform, playerName)
	local built, result = pcall(function()
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
			onboarding = OnboardingServer.serialize(data),
			daily = DailyServer.serialize(data),
			fixedHires = EmployeeServer.serializeFixedHires(data), -- nil (no section) until a restricted player hatches
		}
		for key, value in pairs(data.unknownSections) do -- parts this version doesn't know: write them back as they were
			if payload[key] == nil then
				payload[key] = value
			end
		end
		if transform then
			transform(payload)
		end
		return payload
	end)
	if built then
		return result
	end
	data.saving = false
	warn("Save skipped for " .. playerName .. ": building it failed, so nothing was written: " .. tostring(result))
	return nil
end
-- BUILDSAVE-END

-- SAVENOTE-START
-- (tools/daily_test.py runs the code between the SAVENOTE markers.)
-- Tells the player when saving keeps failing, and again once it works: otherwise only the server log
-- knows, and they keep playing a session that may never be saved (review finding FR-1).
local SAVE_TROUBLE_AFTER = 2 -- failed saves in a row (about 2 minutes of autosaves) before the player is told
local SAVE_TROUBLE_TEXT = "Saving is having trouble right now. Keep playing: your progress is saved as soon as it works again."
local SAVE_BACK_TEXT = "Saving works again: your progress is safe."
local function noteSaveResult(player, data, ok)
	local failed = data.failedSaves or 0
	if ok then
		if failed >= SAVE_TROUBLE_AFTER then
			ShopServer.notify(player, SAVE_BACK_TEXT)
		end
		data.failedSaves = 0
	else
		data.failedSaves = failed + 1
		if data.failedSaves == SAVE_TROUBLE_AFTER then
			ShopServer.notify(player, SAVE_TROUBLE_TEXT)
		end
	end
end
-- SAVENOTE-END

-- Returns true if the save worked (the shop needs to know before confirming a purchase).
-- transform (IPO only) changes the payload before it's written: see commitIpo.
local function save(player, transform)
	local data = playerData[player]
	if not data or not data.loaded then return false end -- never overwrite data we failed (or haven't finished) loading
	if not (data.shop and data.team and data.poach and data.ipo and data.onboarding and data.daily) then -- a save must have every part
		warn("Not saving " .. player.Name .. ": part of their data isn't set up")
		return false
	end

	-- One save at a time per player, so an older save can never land after a newer one
	while data.saving do
		task.wait()
	end
	data.saving = true

	local payload = buildPayload(data, transform, player.Name)
	if not payload then
		noteSaveResult(player, data, false)
		return false
	end
	local ok, err
	if transform and data.debugFailIpoSave then -- Studio Debug tab only: test the IPO failure path
		data.debugFailIpoSave = nil
		ok, err = false, "simulated failure (Studio Debug tab)"
	else
		ok, err = pcall(function()
			local currentStore = getStore()
			if not currentStore then error("no DataStore") end
			currentStore:SetAsync("player_" .. player.UserId, payload)
		end)
	end
	data.saving = false
	if not ok then
		warn("Save failed for " .. player.Name .. ": " .. tostring(err))
	end
	noteSaveResult(player, data, ok)
	return ok
end

-- LEAVESAVE-START
-- (tools/daily_test.py runs the code between the LEAVESAVE markers, with a fake save.)
-- The save when a player leaves is the last chance to keep their session, so a failed one is tried
-- again (FR-1): up to LEAVE_SAVE_TRIES in all, waiting 2 s, then 4 s (well inside BindToClose's time).
-- It stops at once when there is nothing that may be saved (gone, or never finished loading).
local LEAVE_SAVE_TRIES = 3
local function saveOnLeave(player)
	for attempt = 1, LEAVE_SAVE_TRIES do
		if save(player) then
			return true
		end
		local data = playerData[player]
		if not data or not data.loaded or attempt == LEAVE_SAVE_TRIES then
			break
		end
		warn(string.format("Leave save for %s failed (try %d of %d), trying again", player.Name, attempt, LEAVE_SAVE_TRIES))
		task.wait(attempt * 2)
	end
	return false
end
-- LEAVESAVE-END

-- IPO (milestone 4) -----------------------------------------------------

-- Going public: the save is written first with the reset already in it (what IpoConfig.Resets
-- turns on, and IpoServer's new "ipo" section). Only if that worked does the game change to
-- match. If it failed, nothing changed. Nothing here waits after the save, so a save that is
-- waiting behind this one (autosave, leaving) always sees the result.
local function commitIpo(player, newIpo)
	local data = playerData[player]
	if not data then return false end
	local resets = IpoConfig.Resets
	local ok = save(player, function(payload)
		if resets.Cash then
			payload.cash = IpoConfig.StartingCash
		end
		if resets.Upgrades then
			payload.owned = {}
		end
		if resets.Eggs and payload.team then
			for i in ipairs(payload.team.incubators) do
				payload.team.incubators[i] = false
			end
		end
		if resets.HRDepartment and payload.poach then
			payload.poach.hrLevel = 0
		end
		payload.ipo = newIpo
	end)
	if not ok or playerData[player] ~= data then
		return ok
	end

	if resets.Cash then
		data.cash.Value = IpoConfig.StartingCash
	end
	if resets.Upgrades then
		table.clear(data.owned)
		for name, item in pairs(data.items) do
			item:Destroy()
			data.items[name] = nil
		end
	end
	if resets.Eggs then
		EmployeeServer.clearIncubators(player)
	end
	if resets.HRDepartment then
		PoachServer.resetHrDepartment(player)
	end
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
	callOffPoachDeals = function(player)
		PoachServer.callOffForIpo(player)
	end,
	countEggs = function(player)
		return EmployeeServer.countEggs(player)
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

-- First minute for new players (milestone 5) -----------------------------

OnboardingServer.init({
	getData = function(player)
		return playerData[player]
	end,
	save = save,
	updateIncome = updateIncome,
	nextUpgradeCost = function(data) -- what the green pad sells now, or nil when everything is bought
		local _, upg = nextUpgrade(data)
		return upg and upg.cost
	end,
})

-- Daily login calendar (milestone 6) -------------------------------------

DailyServer.init({
	getData = function(player)
		return playerData[player]
	end,
	save = save,
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

local function onPlayerAdded(player)
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

	local data = { owned = {}, items = {}, slot = slot, folder = folder, cash = cash, income = income, unknownSections = {}, loaded = false }
	playerData[player] = data

	local floor = makePart(folder, "Floor", Vector3.new(60, 1, 60), plotCenter(slot), Color3.fromRGB(90, 90, 100))
	addLabel(floor, player.DisplayName .. "'s Startup", 12)

	-- Saving stays off (data.loaded is false) until every module has set up its part of the save.
	-- Some of them wait for Roblox (pass checks, poaching checks), and leaving or an autosave in
	-- that time must never write a save with parts missing. If a part can't be set up at all,
	-- this session never saves, so the save on the DataStore stays as it was.
	local saved, ok = load(player)
	if playerData[player] ~= data then return end -- they left while loading: nothing was saved
	ok = readableSave(saved, ok, player.Name)
	if not ok and (getStore() or not RunService:IsStudio()) then
		-- The DataStore didn't answer after every try (or there is none on a live server): playing on
		-- could never save, so send them back. Only Studio without a DataStore plays unsaved.
		warn("Kicking " .. player.Name .. ": their save couldn't be read, so this session could never save")
		player:Kick(LOAD_FAILED_MESSAGE)
		return
	end
	-- A save this fresh may still be written by another server: wait, then read again (see REREAD).
	-- Nothing can be saved yet (data.loaded is false). If the second read fails, the first one is used.
	if ok and shouldReread(saved, os.time()) then
		task.wait(REREAD_WAIT_SECONDS)
		if playerData[player] ~= data then return end -- they left while waiting: nothing was saved
		local again, againOk = load(player)
		if playerData[player] ~= data then return end
		if againOk and typeof(again) == "table" then
			saved = again
		end
	end
	local lastSeen = nil
	local setupOk, setupError = pcall(function()
		if saved then
			local savedCash, savedOwned
			savedCash, savedOwned, lastSeen = sanitizeSave(saved, player.Name)
			cash.Value = savedCash
			for _, name in ipairs(savedOwned) do
				data.owned[name] = true
			end
			for key, value in pairs(saved) do
				if not KNOWN_SECTIONS[key] then
					data.unknownSections[key] = value
					warn("Keeping a part of " .. player.Name .. "'s save this version doesn't know: " .. tostring(key))
				end
			end
		end
		ShopServer.setupPlayer(player, data, saved and saved.shop) -- passes, boosts and past receipts
		-- Saves from before milestone 4 have no valuation: count the upgrades they bought plus their Cash,
		-- capped at the first IPO-ready valuation (a huge old bank can't buy a pile of Shares on day one)
		local legacyValuation = 0
		if saved and saved.ipo == nil then
			legacyValuation = cash.Value
			for _, upg in ipairs(UPGRADES) do
				if data.owned[upg.name] then
					legacyValuation += upg.cost
				end
			end
			legacyValuation = math.min(legacyValuation, IpoConfig.ipoValuation(0))
		end
		IpoServer.setupPlayer(player, data, saved and saved.ipo, legacyValuation) -- before employees: perks change slots
		EmployeeServer.setupFixedHires(player, data, saved and saved.fixedHires) -- fixed hire order counters (before eggs can hatch)
		EmployeeServer.setupPlayer(player, data, saved and saved.team) -- employees and eggs (after passes: slots)
		PoachServer.setupPlayer(player, data, saved and saved.poach, ok and saved == nil) -- after employees
		OnboardingServer.setupPlayer(player, data, saved and saved.onboarding, ok) -- tells new players from old ones
		DailyServer.setupPlayer(player, data, saved and saved.daily) -- after employees: a claim can grant an egg
	end)
	if playerData[player] ~= data then return end -- they left while loading: nothing was saved
	if not setupOk then
		warn("Could not set up " .. player.Name .. "'s save, so it won't be saved this session: " .. tostring(setupError))
		player:Kick(LOAD_FAILED_MESSAGE)
		return
	end
	data.loaded = ok -- from here on, saves are complete

	for i, upg in ipairs(UPGRADES) do
		if data.owned[upg.name] then
			spawnItem(data, i, upg)
		end
	end
	updateIncome(player)

	-- Offline earnings: the startup keeps making money while you're away
	if lastSeen then
		local cap = OFFLINE_CAP_SECONDS + IpoServer.perk(data, "OfflineCap")
		local away = math.clamp(os.time() - lastSeen, 0, cap)
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
end
Players.PlayerAdded:Connect(onPlayerAdded)
-- Players already in the server (they joined while this script was still starting) are set up too
for _, existing in ipairs(Players:GetPlayers()) do
	if not playerData[existing] then
		task.spawn(onPlayerAdded, existing)
	end
end

Players.PlayerRemoving:Connect(function(player)
	saveOnLeave(player)
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
