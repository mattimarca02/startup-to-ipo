-- TycoonCore: Startup to IPO, milestone 1 (garage stage) + hooks for employees (milestone 2) and the shop (milestone 3)
-- Put this Script in ServerScriptService. It builds everything by itself.
-- Game passes and developer products live in ShopServer (ServerScriptService) and ShopConfig (ReplicatedStorage).
-- Eggs and creature employees live in EmployeeServer (ServerScriptService) and CreatureConfig (ReplicatedStorage).
-- Poaching and the HR Department live in PoachServer (ServerScriptService) and CreatureConfig.Poaching.
-- Valuation, the IPO rebirth and the IPO shop live in IpoServer (ServerScriptService) and IpoConfig (ReplicatedStorage).
-- The first minute for new players (free egg, arrow, goals) lives in OnboardingServer (ServerScriptService) and OnboardingConfig (ReplicatedStorage).
-- The 7-day login calendar lives in DailyServer (ServerScriptService) and DailyConfig (ReplicatedStorage).
-- The task engine (customer calls; Studio only until the economy core) lives in TaskServer (ServerScriptService) and TaskConfig (ReplicatedStorage).
-- The company, its sector and the Pokedex (the `pokedex` save section) live in CompanyServer (ServerScriptService), CompanyConfig and SectorConfig (ReplicatedStorage).

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
local LobbyConfig = require(ReplicatedStorage:WaitForChild("LobbyConfig")) -- the garages, the plaza and the claim (ClaimEnabled)
local OfficeConfig = require(ReplicatedStorage:WaitForChild("OfficeConfig")) -- the office catalog, buildings, desks, hires (overhaul 2)
local ShopServer = require(script.Parent:WaitForChild("ShopServer"))
local IpoServer = require(script.Parent:WaitForChild("IpoServer"))
local EmployeeServer = require(script.Parent:WaitForChild("EmployeeServer"))
local PoachServer = require(script.Parent:WaitForChild("PoachServer"))
local OnboardingServer = require(script.Parent:WaitForChild("OnboardingServer"))
local CompanyServer = require(script.Parent:WaitForChild("CompanyServer"))
local TaskServer = require(script.Parent:WaitForChild("TaskServer"))
local DailyServer = require(script.Parent:WaitForChild("DailyServer"))

-- The garage that grows with the startup: PlotVisuals builds it from the data in PlotArt (both in
-- ServerScriptService). Only looks, never saved. Loaded inside pcall: if either is missing or broken,
-- the game runs as before with plain upgrade blocks and a warning in the Output.
local visualsOk, PlotVisuals = pcall(require, script.Parent:WaitForChild("PlotVisuals", 5))
local artOk, PlotArt = pcall(require, script.Parent:WaitForChild("PlotArt", 5))
if not (visualsOk and artOk) then
	warn("Plot visuals are off: " .. tostring(visualsOk and PlotArt or PlotVisuals))
	PlotVisuals, PlotArt = nil, nil
end

-- The office catalog (overhaul 2): OfficeConfig.Items, bought in the shop's Office tab (ShopClient), any order inside
-- the funding stages reached (the Desk first). name = the key saved in `owned`, cost = Cash, income = Cash per second
-- before the building's office multiplier, stage = the funding stage that unlocks it. Only the six old garage upgrades
-- have a station prop (slot = their old station, itemOffset) and a plain block for when the plot visuals are off.
local OLD_STATIONS = {
	Desk =             { slot = 1, color = Color3.fromRGB(160, 110, 60),  size = Vector3.new(6, 3, 4) },
	["Coffee Machine"] = { slot = 2, color = Color3.fromRGB(60, 60, 60),    size = Vector3.new(2, 4, 2) },
	Laptop =           { slot = 3, color = Color3.fromRGB(200, 200, 210), size = Vector3.new(3, 1, 2) },
	["Server Rack"] =  { slot = 4, color = Color3.fromRGB(30, 30, 40),    size = Vector3.new(4, 8, 3) },
	Whiteboard =       { slot = 5, color = Color3.fromRGB(245, 245, 245), size = Vector3.new(8, 5, 1) },
	["Neon Logo"] =    { slot = 6, color = Color3.fromRGB(0, 170, 255),   size = Vector3.new(10, 4, 1) },
}
local UPGRADES = {}
for _, item in ipairs(OfficeConfig.Items) do
	local station = OLD_STATIONS[item.key]
	table.insert(UPGRADES, {
		name = item.key, cost = item.price, income = item.income, icon = item.icon, stage = item.stage,
		slot = station and station.slot, color = station and station.color, size = station and station.size,
	})
end

local PLOT_SPACING = 90
local SIGN_OFFSET = Vector3.new(0, 0.5, 24) -- the garage sign that names the next upgrade (front of the plot)
local MAX_PLOTS = 6
-- Each garage's turn in degrees, one per slot (quarter turns only: 0, 90, 180 or 270). Offsets inside a garage are in
-- its own frame (+X right, +Z the front, toward the signs), so they turn with it (plotFrame). All 0 for now: every
-- garage stands as it always has (docs/LOBBY_GARAGE_PROPOSAL.md, PR L1; the ring of PR L4 turns them).
local GARAGE_TURNS = { 0, 0, 0, 0, 0, 0 }
if LobbyConfig.ClaimEnabled then -- the ring (lobby L4): each garage turned to face the plaza (LobbyConfig.Ring)
	for slot, g in ipairs(LobbyConfig.Garages) do
		GARAGE_TURNS[slot] = g.turn
	end
end
local OFFLINE_CAP_SECONDS = 8 * 60 * 60 -- max 8 hours of offline earnings (the Night Shift IPO perk adds more)
local OFFLINE_RATE = 0.5 -- offline you earn 50% of normal income
local WELCOME_BACK_MIN_SECONDS = 5 * 60 -- away at least this long: one "Welcome back" pop-up says what the startup earned
local WELCOME_BACK_DELAY = 3 -- seconds after the load, so the pop-up shows once the player's screen is up
local LOAD_TRIES = 3 -- reads of a joining player's save before giving up and kicking them
local LOAD_FAILED_MESSAGE = "Your startup couldn't load. Please rejoin in a moment: your progress is safe."

-- The parts of the save this version writes. Any other part of a loaded save was written by
-- newer (or other) code: it's kept and written back unchanged, never deleted.
local KNOWN_SECTIONS = { cash = true, owned = true, lastSeen = true, shop = true, team = true, poach = true, ipo = true, onboarding = true, daily = true, fixedHires = true, tasks = true, pokedex = true, office = true }

local plotOwners = {} -- slot number -> player
local syncDesks -- the office's workstations (set with the employees, below; buyDesk calls it first)
local playerData = {} -- player -> { owned, items, slot, folder, sign, cash, income, shop, team, fixedHires, poach, ipo, onboarding, daily, tasks, pokedex, unknownSections, loaded, ready, saving }

-- Helpers ---------------------------------------------------------------

local function makePart(parent, name, size, position, color, material)
	local p = Instance.new("Part")
	p.Name = name
	p.Size = size
	if typeof(position) == "CFrame" then
		p.CFrame = position -- a part placed in a garage's frame, turned with it
	else
		p.Position = position
	end
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
	if LobbyConfig.ClaimEnabled then -- the ring around the plaza (lobby L4); with the claim off, the row as always
		local g = LobbyConfig.Garages[slot]
		return Vector3.new(g.x, 0.5, g.z)
	end
	local startX = -((MAX_PLOTS - 1) * PLOT_SPACING) / 2
	return Vector3.new(startX + (slot - 1) * PLOT_SPACING, 0.5, 150)
end

-- A garage's frame: its center, turned by its GARAGE_TURNS. frame * offset is where an offset in the garage lands in
-- the world, at any turn (plotFrame(slot).Position is plotCenter(slot)). Quarter turns are exact (cos and sin are -1, 0
-- or 1), so a turned room's boxes stay on the grid: the turn is about +Y, and 90 turns the front (+Z) to world +X.
local QUARTER_TURNS = { [0] = { 1, 0 }, [90] = { 0, 1 }, [180] = { -1, 0 }, [270] = { 0, -1 } } -- degrees -> cos, sin
local function plotFrame(slot)
	local center = plotCenter(slot)
	local c, s = QUARTER_TURNS[GARAGE_TURNS[slot]][1], QUARTER_TURNS[GARAGE_TURNS[slot]][2]
	return CFrame.new(center.X, center.Y, center.Z, c, 0, s, 0, 1, 0, -s, 0, c)
end

-- Where each upgrade's prop stands: two walls of stations, the first three (Desk, Coffee Machine, Laptop) along
-- the left wall and the next three (Server Rack, Whiteboard, Neon Logo) along the right wall, 12 studs apart
-- from the back, in line with the rows of hire desks (EmployeeServer EMPLOYEE_SPOTS).
local function itemOffset(i)
	local col = (i - 1) // 3
	local row = (i - 1) % 3
	return Vector3.new(-23 + col * 46, 0, -10 + row * 12)
end

-- The building bought this run (overhaul 2: CompanyServer keeps it in the pokedex; 1 = the Garage)
local function buildingOf(data)
	return CompanyServer.getBuilding(data)
end

-- Overhaul 2: the items' income times the building's office multiplier, plus the employees' times its team multiplier
local function totalIncome(data)
	local building = OfficeConfig.building(buildingOf(data))
	return OfficeConfig.itemIncome(data.owned) * building.office + EmployeeServer.getIncome(data) * building.team -- creature employees earn too
end

-- The Income on the leaderboard already includes game pass bonuses (2x Cash, VIP) and the IPO multiplier
local function updateIncome(player)
	local data = playerData[player]
	if not data then return end
	data.income.Value = math.floor(totalIncome(data) * ShopServer.getCashMultiplier(player) * IpoServer.getMultiplier(player))
	local building, number = OfficeConfig.building(buildingOf(data))
	player:SetAttribute("Building", number) -- overhaul 2: for display only (the shop, the Team window); nothing reads it back
	player:SetAttribute("TeamMultiplier", building.team)
end

-- The cheapest item the player can buy at their stage (the Desk first), or nil when none is left there
local function nextUpgrade(data)
	local stage = data.ipo and IpoConfig.stageIndex(data.ipo.valuation, data.ipo.count) or 1
	local best, bestIndex
	for i, upg in ipairs(UPGRADES) do
		if not data.owned[upg.name] and upg.stage <= stage and (data.owned[OfficeConfig.FirstItem] or upg.name == OfficeConfig.FirstItem) then
			if not best or upg.cost < best.cost then
				best, bestIndex = upg, i
			end
		end
	end
	return bestIndex, best
end

-- Plot looks: a failing look is warned about and skipped, never allowed to stop loading, a
-- purchase or an IPO. data.looks is the plot's PlotVisuals state (in memory only).
local function looks(what, fn, ...)
	if not PlotVisuals then return nil end
	local ok, result = pcall(fn, ...)
	if not ok then
		warn("Plot visuals: " .. what .. " failed: " .. tostring(result))
		return nil
	end
	return result
end

-- The funding stage the valuation reached (what can be unlocked; overhaul 2: the room follows the building bought)
local function stageOf(data)
	return data.ipo and IpoConfig.stageIndex(data.ipo.valuation, data.ipo.count) or 1
end

-- The closed building around each garage: PlotBuildingVisuals builds it from PlotBuilding (both in ServerScriptService)
-- with the 3D kit in ReplicatedStorage.KitModels (Parts where a model is missing), and the client script BuildingClient
-- fades it while you are inside. Only looks plus invisible solid outer walls; never saved. Loaded inside pcall: if
-- either is missing or broken, the garages stand open, as before.
local buildingOk, PlotBuildingVisuals = pcall(require, script.Parent:WaitForChild("PlotBuildingVisuals", 5))
local buildingDataOk, PlotBuilding = pcall(require, script.Parent:WaitForChild("PlotBuilding", 5))
if not (buildingOk and buildingDataOk) then
	warn("Plot buildings are off: " .. tostring(buildingOk and PlotBuilding or PlotBuildingVisuals))
	PlotBuildingVisuals, PlotBuilding = nil, nil
end

-- The six garages (lobby L2: permanent). Each is Workspace.Garages.Garage<slot>: its Floor (60 x 60, the room's only
-- solid part, in the garage's frame), its closed building (PlotBuilding) and its sign. An owner's folder (room, props,
-- employees, incubators, signs) stands in it while they play; when they leave, the garage goes back to a new Garage.
local garages = {} -- slot -> the garage Model

-- The claim (lobby L3). A joining player stands on the plaza (inPlaza) until they claim a garage. plotOwners[slot] stays
-- the only truth of who has a garage; garageState is only what the garage shows (Free, MovingIn, Taken, Closing).
local inPlaza = {} -- player -> true: joined, no garage yet (written before the join's first yield)
local claims = {} -- UserId -> { slot, leaving }: one garage per account, held until that account's leave save has returned
local claimedAt = {} -- player -> os.clock() of their claim (a Robux receipt waits for the save from then)
local lastClaimAsk = {} -- UserId -> os.clock() of their last claim request (one a second)
local garageState = {} -- slot -> "Free", "MovingIn", "Taken" or "Closing"
local requestClaim -- a prompt's handler (the claim, below onPlayerAdded's helpers)

-- A part of a garage's claim spot (its "ClaimPost" or its "FreeLamp"), or nil
local function claimPart(slot, name)
	local spot = garages[slot] and garages[slot]:FindFirstChild("ClaimSpot")
	return spot and spot:FindFirstChild(name)
end

-- The sign over each garage's door (the building's one text, PlotBuildingVisuals.setSign; overhaul phase 1): the owner's
-- company name and the stage's name while someone plays there ("Moving in..." or "Closing..." while their save runs),
-- FREE and "Claim this garage" while it is free. Looks only, in memory only; written again whenever the state or the
-- building changes. A building without a sign (the kit's fallback included) just shows none.
local facadeTitle = {} -- slot -> the owner's company name, or "" (a free garage)
local function applyFacadeSign(slot)
	local building = PlotBuildingVisuals and garages[slot] and garages[slot]:FindFirstChild("PlotBuilding")
	if not building then return end
	local state, title, subtitle = garageState[slot], facadeTitle[slot] or "", nil
	if state == "MovingIn" then
		subtitle = LobbyConfig.Texts.MovingIn
	elseif state == "Closing" then
		subtitle = LobbyConfig.Texts.Closing
	elseif state == "Taken" then
		subtitle = building:GetAttribute("StageName")
	else
		title, subtitle = LobbyConfig.Texts.Free, LobbyConfig.Texts.SignFree
	end
	pcall(PlotBuildingVisuals.setSign, building, title, subtitle)
end

-- What a garage shows: its State and OwnerName attributes (for display: nothing reads them back), the claim post's
-- prompt, FREE sign and lamp, which only a Free garage has, and only while the claim is on, and the facade sign's text
local function setGarageState(slot, state, ownerName)
	garageState[slot] = state
	local garage = garages[slot]
	if not garage then return end
	garage:SetAttribute("State", state)
	garage:SetAttribute("OwnerName", ownerName or "")
	applyFacadeSign(slot)
	local free = state == "Free" and LobbyConfig.ClaimEnabled
	local post = claimPart(slot, "ClaimPost")
	if post then
		post.Transparency = LobbyConfig.ClaimEnabled and 0 or 1
		local prompt = post:FindFirstChildOfClass("ProximityPrompt")
		if prompt then prompt.Enabled = free end
		local gui = post:FindFirstChildOfClass("BillboardGui")
		if gui then
			gui.Enabled = LobbyConfig.ClaimEnabled and state ~= "Taken"
			gui.TextLabel.Text = (state == "Free" and LobbyConfig.Texts.Free) or (state == "MovingIn" and LobbyConfig.Texts.MovingIn) or LobbyConfig.Texts.Closing
		end
	end
	local lamp = claimPart(slot, "FreeLamp")
	if lamp then lamp.Transparency = free and 0 or 1 end
end

-- A Free garage shows today's new-player room: the stage 1 room, with no props (nobody owns any). Looks only.
local function buildFreeRoom(slot)
	local garage = garages[slot]
	if not (garage and PlotVisuals) or garage:FindFirstChild("FreeRoom") then return end
	local folder = Instance.new("Folder")
	folder.Name = "FreeRoom"
	folder.Parent = garage
	looks("free room", PlotVisuals.newPlot, folder, plotFrame(slot).Position, PlotArt, garage.Floor, 1)
end
local function clearFreeRoom(slot)
	local room = garages[slot] and garages[slot]:FindFirstChild("FreeRoom")
	if room then room:Destroy() end
end

-- The building of a garage at a funding stage (nothing to do when it already shows it). A new building is never
-- allowed to trap anyone: a character standing where a solid box now is goes to the garage's landing spot.
local buildingWarned = false -- it runs every second: a broken building is told once per server, not every second
local function syncBuilding(slot, stage)
	if not (PlotBuildingVisuals and garages[slot]) then return end
	local kit = ReplicatedStorage:FindFirstChild(PlotBuilding.KIT_FOLDER)
	local ok, model, changed = pcall(PlotBuildingVisuals.sync, garages[slot], plotFrame(slot), PlotBuilding, stage, kit)
	if not ok then
		if not buildingWarned then
			buildingWarned = true
			warn("Plot buildings: the building failed: " .. tostring(model))
		end
	elseif changed then
		local roots = {}
		for _, other in ipairs(Players:GetPlayers()) do
			local root = other.Character and other.Character:FindFirstChild("HumanoidRootPart")
			if root then table.insert(roots, root) end
		end
		pcall(PlotBuildingVisuals.unstick, model, roots, plotFrame(slot) * CFrame.new(0, 4, 12)) -- teleportToPlot's landing
		applyFacadeSign(slot) -- a new building: its sign is blank until it is written again
	end
end

-- The name over a garage ("" hides it): set when someone moves in, cleared when they leave. It is the label over the roof
-- (seen across the plaza) and the first line of the facade sign over the door.
local function setGarageSign(slot, text)
	local sign = garages[slot] and garages[slot]:FindFirstChild("GarageSign")
	local gui = sign and sign:FindFirstChildOfClass("BillboardGui")
	if gui then
		gui.TextLabel.Text = text
		gui.Enabled = text ~= ""
	end
	facadeTitle[slot] = text
	applyFacadeSign(slot)
end

-- After the owner's leave save: the garage is a new Garage again (Floor and building at stage 1, no name)
local function resetGarage(slot)
	local garage = garages[slot]
	if not garage then return end
	if PlotVisuals then
		looks("floor", PlotVisuals.styleFloor, garage.Floor, PlotArt, 1)
	end
	syncBuilding(slot, 1)
	setGarageSign(slot, "")
	buildFreeRoom(slot)
	setGarageState(slot, "Free")
end

-- Builds the six garages once, when the server starts, before anyone is set up
local function buildGarages()
	local root = Instance.new("Folder")
	root.Name = "Garages"
	for slot = 1, MAX_PLOTS do
		local garage = Instance.new("Model")
		garage.Name = "Garage" .. slot
		garage:SetAttribute("Slot", slot)
		makePart(garage, "Floor", Vector3.new(60, 1, 60), plotFrame(slot), Color3.fromRGB(90, 90, 100)) -- the room takes its turn from it
		local sign = makePart(garage, "GarageSign", Vector3.new(1, 1, 1), plotFrame(slot), Color3.fromRGB(90, 90, 100))
		sign.Transparency, sign.CanCollide, sign.CanTouch, sign.CanQuery = 1, false, false, false
		addLabel(sign, "", 12).Parent.Enabled = false -- the owner's name, over the garage
		-- The claim post beside the door (lobby L3): the "Claim garage" prompt, the FREE sign and a lamp (Neon, no light).
		-- Never solid, never touched; only shown while the claim is on. Both stand in the garage's ClaimSpot, a Persistent
		-- model: with streaming on, every client has every post (and its prompt) from the start, however far away.
		local spot = Instance.new("Model")
		spot.Name = "ClaimSpot"
		pcall(function()
			spot.ModelStreamingMode = Enum.ModelStreamingMode.Persistent
		end)
		spot.Parent = garage
		local postAt = plotFrame(slot) * CFrame.new(LobbyConfig.Post.x, 1.5, LobbyConfig.Post.z)
		local post = makePart(spot, "ClaimPost", Vector3.new(0.6, 4, 0.6), postAt, Color3.fromRGB(70, 74, 86), Enum.Material.Metal)
		post.CanCollide, post.CanTouch, post.CanQuery = false, false, false
		local lamp = makePart(spot, "FreeLamp", Vector3.new(1, 1, 1), postAt * CFrame.new(0, 2.5, 0), Color3.fromRGB(90, 230, 120), Enum.Material.Neon)
		lamp.CanCollide, lamp.CanTouch, lamp.CanQuery = false, false, false
		local prompt = Instance.new("ProximityPrompt")
		prompt.ActionText = LobbyConfig.Texts.Prompt
		prompt.ObjectText = "Garage " .. slot
		prompt.HoldDuration = LobbyConfig.HoldSeconds
		prompt.MaxActivationDistance = LobbyConfig.PromptDistance
		prompt.RequiresLineOfSight = false
		prompt.Enabled = false
		prompt.Parent = post
		prompt.Triggered:Connect(function(player)
			requestClaim(player, slot)
		end)
		local freeSign = addLabel(post, LobbyConfig.Texts.Free, 4)
		freeSign.TextColor3 = Color3.fromRGB(90, 230, 120)
		freeSign.Parent.Enabled = false
		garage.Parent = root
		garages[slot] = garage
	end
	root.Parent = workspace
	if Players.MaxPlayers > MAX_PLOTS then -- nothing reads Max Players: a 7th player is only kicked (docs/PUBLISH_RULES.md)
		warn(string.format("Max Players is %d but there are %d garages: set it to %d in Creator Hub", Players.MaxPlayers, MAX_PLOTS, MAX_PLOTS))
	end
	for slot = 1, MAX_PLOTS do
		resetGarage(slot)
	end
end
buildGarages()

-- The plaza and the decor around the ring (lobby L4): WorldVisuals draws it once from WorldArt, only with the claim on
-- (with it off the garages stand in the row, as always, and there is no world). Looks only, inside pcall.
if LobbyConfig.ClaimEnabled then
	local worldOk, WorldVisuals = pcall(require, script.Parent:WaitForChild("WorldVisuals", 5))
	local worldArtOk, WorldArt = pcall(require, script.Parent:WaitForChild("WorldArt", 5))
	local drawn, problem = false, tostring(worldOk and WorldArt or WorldVisuals)
	if worldOk and worldArtOk then
		drawn, problem = pcall(function()
			local site = WorldVisuals.ringSite(WorldArt, LobbyConfig.Garages)
			return WorldVisuals.build(workspace, WorldArt, site)
		end)
	end
	if not drawn then
		warn("The plaza is off: " .. tostring(problem))
	end
end

-- A funding round reached (overhaul 2): one pop-up that says what it unlocked ("Seed reached! The Small Office and 11
-- new items are in SHOP > Office"). The building is the player's choice: buying it is buyBuilding's moment.
local function stageUpToast(data, to)
	local player = data.player
	local stage = IpoConfig.Stages[to]
	if not (player and stage and player.Parent) then return end
	local text = string.format("%s %s reached!", stage.icon or "", stage.name)
	local building = OfficeConfig.Buildings[to]
	if building and buildingOf(data) < to then
		text ..= string.format(" The %s is in SHOP > Office", building.name)
	end
	if to == #IpoConfig.Stages then
		text ..= " · tap IPO to go public"
	end
	ShopServer.notify(player, text)
end

-- Runs every second (income loop) and after a building is bought: the room and the building follow the building owned
-- (overhaul 2; never the valuation by itself), with a quick flash (the bought props move along). A funding stage
-- reached says so once (stageUpToast). data.debugStage is the Studio Debug button's (in memory only, never saved).
local function syncRoom(data)
	local reached = stageOf(data)
	if data.stageSeen and reached > data.stageSeen then
		stageUpToast(data, reached) -- a round reached, never the Garage after an IPO
	end
	data.stageSeen = reached
	local stage = data.debugStage or buildingOf(data)
	if data.looks and data.looks.stage ~= stage then
		looks("stage", PlotVisuals.setStage, data.looks, stage, true)
	end
	syncBuilding(data.slot, stage)
end

-- An upgrade shows its prop from PlotArt in its station (popIn on a purchase); without one, the plain block. Overhaul 2:
-- only the six old upgrades have a station (upg.slot); the other catalog items are placed by phase 2's office layout.
local function spawnItem(data, i, upg, popIn)
	if not upg.slot then return end
	i = upg.slot
	local prop = data.looks and looks("prop " .. upg.name, PlotVisuals.addProp, data.looks, upg.name, itemOffset(i), popIn)
	if prop then
		data.items[upg.name] = prop
		return
	end
	local pos = plotFrame(data.slot) * CFrame.new(itemOffset(i) + Vector3.new(0, 0.5 + upg.size.Y / 2, 0))
	local item = makePart(data.folder, upg.name, upg.size, pos, upg.color)
	if upg.name == "Neon Logo" then
		item.Material = Enum.Material.Neon
	end
	data.items[upg.name] = item
end

-- Which upgrades the player owns, for the shop's Office tab: Upgrade1 ... Upgrade6 (true or false), in UPGRADES order
local function publishUpgrades(player)
	local data = playerData[player]
	if not data then return end
	for i, upg in ipairs(UPGRADES) do
		player:SetAttribute("Upgrade" .. i, data.owned[upg.name] == true)
	end
end

-- The sign in the garage names the next upgrade. It is only a sign: nothing happens when you step
-- on it. Upgrades are bought in the shop's Office tab (buyUpgrade below).
local function refreshSign(player)
	local data = playerData[player]
	if not data then return end
	if data.sign then
		data.sign:Destroy()
		data.sign = nil
	end
	publishUpgrades(player)

	local i, upg = nextUpgrade(data)
	if not i then return end -- everything bought

	local pos = plotFrame(data.slot) * CFrame.new(SIGN_OFFSET) -- turned with the garage
	local post = makePart(data.folder, "BuySign", Vector3.new(0.4, 3, 0.4), pos * CFrame.new(0, 1.5, 0), Color3.fromRGB(70, 74, 86), Enum.Material.Metal)
	post.CanCollide, post.CanTouch, post.CanQuery = false, false, false
	local board = makePart(post, "Board", Vector3.new(8, 2.6, 0.3), pos * CFrame.new(0, 4.3, 0), Color3.fromRGB(0, 140, 70), Enum.Material.SmoothPlastic)
	board.CanCollide, board.CanTouch, board.CanQuery = false, false, false
	addLabel(board, string.format("Next: %s  %s\nBuy it in SHOP > Office", upg.name, OfficeConfig.money(upg.cost)), 3)
	data.sign = post
end

-- Buying an item of the office catalog: the shop's Office tab asks, only with the item's number. The server decides
-- everything (ready, number, owned, the Desk first, the funding stage, Cash, rate: OfficeConfig.checkItem). The price is
-- always OfficeConfig's, never the client's. Overhaul 2: any order inside the stages reached (was: the six in order).
-- BUYUPGRADE-START
-- (tools/daily_test.py runs the code between the BUYUPGRADE markers, with fakes for the Roblox parts.)
local BUY_MIN_INTERVAL = 0.4 -- seconds between two requests from one player (spam is refused, not queued)

-- The request rate and data.ready, shared by every office purchase (items, the building, desks, hires).
-- Stamps data.lastBuyAt on every request it looks at, so a spammed button is only looked at once per interval.
local function checkBuyRequest(data, now)
	if not data.ready then
		return nil, "Still loading, try again in a moment" -- loading, or an IPO is being saved
	end
	if data.lastBuyAt and now - data.lastBuyAt < BUY_MIN_INTERVAL then
		return nil, "Too fast"
	end
	data.lastBuyAt = now
	return true
end

-- Returns the index of the item the player may buy now, or nil and the reason (shown to them)
local function checkUpgradePurchase(upgrades, data, cash, id, now)
	if typeof(id) ~= "number" or id ~= id or id % 1 ~= 0 or id < 1 or id > #upgrades then
		return nil, "Unknown upgrade"
	end
	local ok, reason = checkBuyRequest(data, now)
	if not ok then
		return nil, reason
	end
	local stage = data.ipo and IpoConfig.stageIndex(data.ipo.valuation, data.ipo.count) or 1
	local item, refusal = OfficeConfig.checkItem(id, stage, data.owned, cash)
	if not item then
		return nil, refusal
	end
	return id
end

local function buyUpgrade(player, id)
	local data = playerData[player]
	if not data then
		return false, "Still loading, try again in a moment"
	end
	local i, reason = checkUpgradePurchase(UPGRADES, data, data.cash.Value, id, os.clock())
	if not i then
		return false, reason
	end
	local upg = UPGRADES[i]
	data.cash.Value -= upg.cost
	data.owned[upg.name] = true
	updateIncome(player)
	spawnItem(data, i, upg, true)
	refreshSign(player)
	return true, "Bought " .. upg.name
end
-- BUYUPGRADE-END

-- The next building (overhaul 2): unlocked by its funding stage, bought here, never given. The client sends nothing but
-- the request; the price and the number are OfficeConfig's. The room and the building change at once (syncRoom), and
-- BuildingClient gives the owner the look at the new facade.
local function buyBuilding(player)
	local data = playerData[player]
	if not data then
		return false, "Still loading, try again in a moment"
	end
	local ok, reason = checkBuyRequest(data, os.clock())
	if not ok then
		return false, reason
	end
	if CompanyServer.isLocked(data) then
		return false, "Your office was saved by a newer version of the game: it can't change here"
	end
	local from = buildingOf(data)
	local building, n = OfficeConfig.checkBuilding(from, stageOf(data), data.cash.Value)
	if not building then
		return false, n
	end
	data.cash.Value -= building.price
	CompanyServer.setBuilding(data, n)
	updateIncome(player)
	syncRoom(data)
	return true, string.format("Your %s becomes a %s!", OfficeConfig.Buildings[from].name, building.name)
end

-- The next workstation (overhaul 2): a desk, a chair and a computer at the next hire spot, kept through an IPO
local function buyDesk(player)
	local data = playerData[player]
	if not (data and data.office) then
		return false, "Still loading, try again in a moment"
	end
	local ok, reason = checkBuyRequest(data, os.clock())
	if not ok then
		return false, reason
	end
	local desk, refusal = OfficeConfig.checkDesk(data.office.desks, stageOf(data), data.cash.Value, EmployeeServer.capacity(player))
	if not desk then
		return false, refusal
	end
	data.cash.Value -= desk.price
	data.office.desks += 1
	EmployeeServer.refreshCapacity(player)
	syncDesks(data, true)
	return true, "New desk: room for one more employee"
end

-- A direct hire from the Hire tab (EmployeeServer checks the workstation, the price and Cash)
local function hireDirect(player, index)
	local data = playerData[player]
	if not data then
		return false, "Still loading, try again in a moment"
	end
	local ok, reason = checkBuyRequest(data, os.clock())
	if not ok then
		return false, reason
	end
	return EmployeeServer.hireDirect(player, index)
end

-- What the Office tab shows (it never sends a price: only the number)
local function upgradeList()
	local list = {}
	for _, upg in ipairs(UPGRADES) do
		table.insert(list, { name = upg.name, cost = upg.cost, income = upg.income, icon = upg.icon })
	end
	return list
end

-- Everything the Office and Hire tabs draw (overhaul 2), as the server has it: the stage reached, the building owned,
-- what is owned, the desks and the hires. Display only: every purchase is checked again on its own request.
local function officeState(player)
	local data = playerData[player]
	if not (data and data.ready and data.office) then
		return nil
	end
	local owned = {}
	for i, upg in ipairs(UPGRADES) do
		owned[i] = data.owned[upg.name] == true
	end
	local hires = {}
	for _, offer in ipairs(EmployeeServer.hireList()) do
		table.insert(hires, { creature = offer.creature, rarity = offer.rarity, price = offer.price, eggAverage = offer.eggAverage, egg = offer.egg })
	end
	return {
		stage = stageOf(data),
		building = buildingOf(data),
		owned = owned,
		desks = data.office.desks,
		capacity = EmployeeServer.capacity(player),
		team = data.team and #data.team.employees or 0,
		hires = hires,
	}
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

-- The `office` section as it is saved (overhaul 2): its fields, and the unknown ones it was loaded with, at the same level
local function officeToSave(data)
	local office = data.office
	if not office then return nil end
	local out = { v = office.v, desks = office.desks }
	for key, value in pairs(office.extra or {}) do
		if out[key] == nil then
			out[key] = value
		end
	end
	return out
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
			tasks = TaskServer.serialize(data), -- nil (no section) until there is something to keep: Studio only in PR 1
			office = officeToSave(data), -- overhaul 2: the desks bought (unknown fields written back as they came)
			pokedex = CompanyServer.serialize(data), -- the company, its sector and the Pokedex (a locked newer section is written back as it was)
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

-- SAVEFN-START
-- (tools/daily_test.py runs save() with a fake DataStore, with the COMMITIPO code below: keep it free of Roblox calls except warn, task.wait and getStore.)
-- Returns true if the save worked (the shop needs to know before confirming a purchase).
-- transform (IPO only) changes the payload before it's written: see commitIpo.
local function save(player, transform)
	local data = playerData[player]
	if not data or not data.loaded then return false end -- never overwrite data we failed (or haven't finished) loading
	if not (data.shop and data.team and data.poach and data.ipo and data.onboarding and data.daily and data.tasks and data.pokedex and data.office) then -- a save must have every part
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
-- SAVEFN-END

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
-- COMMITIPO-START
-- (tools/daily_test.py runs commitIpo with the real save(), a fake DataStore and the real CompanyServer.)
local function commitIpo(player, newIpo)
	local data = playerData[player]
	if not data then return false end
	if CompanyServer.isLocked(data) then
		-- The Pokedex is from a newer version (or couldn't be read): going public would reset a company this version can't stamp
		warn("Not going public for " .. player.Name .. ": their pokedex is kept as it is (a newer version's, or unreadable)")
		return false
	end
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
		CompanyServer.writeIpoRun(data, payload, newIpo.count) -- the pokedex's run follows the new count in this very save
	end)
	if not ok or playerData[player] ~= data then
		return ok
	end
	CompanyServer.onIpo(data, newIpo.count) -- the save worked: the section in memory follows too (the next autosave keeps it)

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
	refreshSign(player)
	return true
end
-- COMMITIPO-END

-- Cash the startup earned (not refunds or gifts): raises the valuation. kind "gift" (a Cash pack) and the join load's
-- offline pay count only OfficeConfig.GiftValuationShare of it (overhaul 2: Cash is paid in full, but a long absence
-- or a purchase can't skip a funding stage).
local function addEarnings(player, amount, kind)
	local data = playerData[player]
	local gift = kind == "gift"
	if data and not data.ready then
		-- Before data.ready the only earnings are the join load's offline pay: noted for the welcome-back
		-- pop-up (welcomeBack), in memory only, never saved
		data.offlineEarned = (data.offlineEarned or 0) + amount
		gift = true
	end
	IpoServer.addEarnings(player, gift and amount * OfficeConfig.GiftValuationShare or amount)
end

-- "3h 12m", "45m" (whole minutes, for the welcome-back pop-up)
local function formatAway(seconds)
	local minutes = math.floor(seconds / 60)
	local h, m = minutes // 60, minutes % 60
	if h > 0 and m > 0 then
		return string.format("%dh %dm", h, m)
	elseif h > 0 then
		return string.format("%dh", h)
	end
	return string.format("%dm", m)
end

-- The welcome-back pop-up (backlog item 7, GAMEPLAY_FIRST_HOUR_PROPOSAL A12): once per join, a few seconds after the
-- load, after an absence of WELCOME_BACK_MIN_SECONDS or more that paid offline Cash. It only tells: the Cash was paid
-- by the claim's load (its offline earnings), and this adds nothing, saves nothing and reads nothing back.
-- "8h max" when the absence reached the offline cap (Night Shift raises it). Free: no product doubles it (D7).
local function welcomeBack(player, data, lastSeen)
	local earned = data.offlineEarned
	data.offlineEarned = nil
	if not (type(earned) == "number" and earned > 0 and type(lastSeen) == "number") then return end
	local away = os.time() - lastSeen
	if away < WELCOME_BACK_MIN_SECONDS then return end
	local cap = OFFLINE_CAP_SECONDS + IpoServer.perk(data, "OfflineCap")
	local text = string.format("Welcome back! You earned %s while away (%s)", IpoConfig.formatShort(earned),
		away >= cap and formatAway(cap) .. " max" or formatAway(away))
	task.delay(WELCOME_BACK_DELAY, function()
		if playerData[player] == data and player.Parent then
			ShopServer.notify(player, text)
		end
	end)
end

IpoServer.init({
	getData = function(player)
		return playerData[player]
	end,
	save = save,
	updateIncome = updateIncome,
	plotFrame = plotFrame,
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
	buyUpgrade = buyUpgrade, -- the Office tab
	upgradeList = upgradeList,
	officeState = officeState, -- overhaul 2: the Office and Hire tabs
	buyBuilding = buyBuilding,
	buyDesk = buyDesk,
	hireDirect = hireDirect,
	claimedAt = function(player) -- when they claimed their garage (nil: not yet): a Robux receipt waits for the save from then
		return claimedAt[player]
	end,
})

-- Studio only (the Debug tab exists only in Studio): shows the next funding stage's room and building, to walk every
-- doorway. In memory only: the valuation, the save and the stage rule are untouched; a rejoin shows the real stage.
if RunService:IsStudio() then
	ShopServer.addDebugAction("BuildingNextStage", function(_, data)
		data.debugStage = (data.debugStage or stageOf(data)) % #IpoConfig.Stages + 1
		return "Showing stage " .. data.debugStage .. " (" .. IpoConfig.Stages[data.debugStage].name .. "): Studio only, not saved"
	end)
end

-- Eggs and employees (milestone 2) --------------------------------------

-- The office's workstations (overhaul 2): a desk at each workstation the player has (the free one, the ones bought, the
-- pass's and the perk's) and a see-through one at the next spot; looks only, nothing before the room exists
syncDesks = function(data, popIn)
	if data.looks and data.team and data.player then
		looks("desks", PlotVisuals.setDesks, data.looks, EmployeeServer.capacity(data.player), popIn)
	end
end

EmployeeServer.init({
	getData = function(player)
		return playerData[player]
	end,
	save = save,
	updateIncome = updateIncome,
	plotFrame = plotFrame,
	onTeamChanged = function(data)
		syncDesks(data, true)
	end,
	desksBought = function(data) -- overhaul 2: the desks bought (the old 5 base slots until the `office` section is read)
		return data and data.office and data.office.desks or OfficeConfig.LegacyDesks
	end,
	hatchBonus = function(data) -- overhaul 2: the office items that make eggs hatch faster
		return data and OfficeConfig.effect(data.owned, "hatch") or 0
	end,
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
	teamMultiplier = function(player) -- overhaul 2: a poach costs what the employee earns at the attacker's building
		local data = playerData[player]
		return data and OfficeConfig.building(buildingOf(data)).team or 1
	end,
})

-- First minute for new players (milestone 5) -----------------------------

OnboardingServer.init({
	getData = function(player)
		return playerData[player]
	end,
	save = save,
	updateIncome = updateIncome,
	nextUpgradeCost = function(data) -- what the next upgrade costs, or nil when everything is bought
		local _, upg = nextUpgrade(data)
		return upg and upg.cost
	end,
})

-- Company and Pokedex (customize PR 1, invisible to players) ------------------
-- Plugged in after OnboardingServer and before TaskServer. It gets no addEarnings: it never touches Cash or the valuation.

CompanyServer.init({
	getData = function(player)
		return playerData[player]
	end,
	save = save,
	plotZones = function() -- the plot's reserved gameplay zones from PlotVisuals (looks data), or nil when the plot visuals are off
		local zones = PlotVisuals and PlotArt and looks("zones", PlotVisuals.zones, PlotArt.Layout)
		if not zones then return nil end
		return zones, PlotArt.Layout.floorSize[3]
	end,
})

-- Task engine (PR 1: customer calls, Studio only) --------------------------
-- Plugged in before DailyServer, which stays last. Task Cash goes through addEarnings, the one
-- earnings path; baseIncome is what the stats line measures against (no passes, with the IPO multiplier).

TaskServer.init({
	getData = function(player)
		return playerData[player]
	end,
	addEarnings = addEarnings,
	baseIncome = function(player)
		local data = playerData[player]
		return data and totalIncome(data) * IpoServer.getMultiplier(player) or 0
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
	-- Land in the middle of the garage, facing the front sign (both in the garage's frame)
	local spawnPos = plotFrame(slot) * Vector3.new(0, 4, 12)
	local signPos = plotFrame(slot) * Vector3.new(0, 4, 24)
	local player = Players:GetPlayerFromCharacter(character)
	if player then
		pcall(player.RequestStreamAroundAsync, player, spawnPos) -- streaming: the garage is there before they land (lobby L4)
	end
	root.CFrame = CFrame.lookAt(spawnPos, signPos)
end

-- The `office` save section (overhaul 2, rule A10: a new top-level section, optional on load): the desks bought, kept
-- through an IPO. A save from before overhaul 2 (no section) gets OfficeConfig.LegacyDesks, its old 5 base slots, so no
-- team shrinks; a new player has none (1 free desk). Bad values get a safe default with a warning; unknown fields are
-- kept and written back (extra). Runs right after the claim's load block, with no yield since data.loaded was set.
local function setupOffice(player, data, saved)
	local section = saved and saved.office
	local office = { v = 1, desks = 0, extra = nil }
	if saved ~= nil and section == nil then
		office.desks = OfficeConfig.LegacyDesks
	elseif typeof(section) == "table" then
		local desks = section.desks
		if typeof(desks) == "number" and desks == desks and desks >= 0 then
			office.desks = math.clamp(math.floor(desks), 0, #OfficeConfig.Bought)
		else
			warn("Ignoring a bad desks value in " .. player.Name .. "'s office section: " .. tostring(desks))
		end
		if typeof(section.v) == "number" and section.v > office.v then
			office.v = section.v -- a newer version wrote it: keep its number
		end
		for key, value in pairs(section) do
			if key ~= "v" and key ~= "desks" and typeof(key) == "string" then
				office.extra = office.extra or {}
				office.extra[key] = value
			end
		end
	elseif section ~= nil then
		warn("Ignoring a bad office section in " .. player.Name .. "'s save: " .. tostring(section))
		office.desks = OfficeConfig.LegacyDesks
	end
	data.office = office
	EmployeeServer.refreshCapacity(player)
end

-- Moves a player into a garage: the claim (a prompt, or the server itself while ClaimEnabled is off). The caller asked
-- LobbyConfig.canClaim with no yield since: this writes the claim before anything here can yield, then loads the save
-- exactly as the join always did (the marked block below). The garage is never saved: only the company is.
local function claimGarage(player, slot)
	claims[player.UserId] = { slot = slot }
	plotOwners[slot] = player
	inPlaza[player] = nil
	claimedAt[player] = os.clock()
	player:SetAttribute("Garage", slot)
	setGarageState(slot, "MovingIn", player.DisplayName)
	clearFreeRoom(slot)

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
	folder.Parent = garages[slot] -- the owner's room, props, employees and signs stand in their garage

	local data = { owned = {}, items = {}, slot = slot, folder = folder, cash = cash, income = income, unknownSections = {}, loaded = false }
	data.player = player -- the stage-up toast names the player (syncRoom); never saved
	playerData[player] = data

	local floor = garages[slot].Floor -- permanent (buildGarages): the room takes its turn from it
	setGarageSign(slot, player.DisplayName .. "'s Startup")

	-- Saving stays off (data.loaded is false) until every module has set up its part of the save.
	-- Some of them wait for Roblox (pass checks, poaching checks), and leaving or an autosave in
	-- that time must never write a save with parts missing. If a part can't be set up at all,
	-- this session never saves, so the save on the DataStore stays as it was.
	-- (tools/lobby_test.py checks that the code between the CLAIMLOAD markers is main's at 99eed7b, byte for byte.)
	-- CLAIMLOAD-START
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
		CompanyServer.setupPlayer(player, data, saved and saved.pokedex) -- after the IPO (the run check reads the IPO count); before TaskServer and DailyServer
		TaskServer.setupPlayer(player, data, saved and saved.tasks) -- after employees (hires) and the IPO (rung); before DailyServer
		DailyServer.setupPlayer(player, data, saved and saved.daily) -- after employees: a claim can grant an egg
	end)
	if playerData[player] ~= data then return end -- they left while loading: nothing was saved
	if not setupOk then
		warn("Could not set up " .. player.Name .. "'s save, so it won't be saved this session: " .. tostring(setupError))
		player:Kick(LOAD_FAILED_MESSAGE)
		return
	end
	data.loaded = ok -- from here on, saves are complete

	-- The room of the player's funding stage, then the props of the upgrades they own
	data.looks = PlotVisuals and looks("room", PlotVisuals.newPlot, folder, plotCenter(slot), PlotArt, floor, stageOf(data))
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

	refreshSign(player)
	data.ready = true -- the shop waits for this before granting purchases
	-- CLAIMLOAD-END

	setupOffice(player, data, saved) -- overhaul 2: the desks bought (no yield since the block above: nothing saved yet)
	data.stageSeen = stageOf(data) -- the stage this session started at: only a later round reached is told
	syncRoom(data) -- the room and the building of the building owned
	syncDesks(data, false) -- the workstations that loaded (the room above starts with none)
	welcomeBack(player, data, lastSeen) -- what the offline pay above gave, said once
	setGarageState(slot, "Taken", player.DisplayName)
	player.CharacterAdded:Connect(function(character)
		teleportToPlot(character, slot)
	end)
	if player.Character then
		task.spawn(teleportToPlot, player.Character, slot)
	end
end

-- What LobbyConfig.canClaim needs, read from the server's own tables as they are now
local function claimState()
	local owners = {}
	for slot, owner in pairs(plotOwners) do
		owners[slot] = { name = owner.DisplayName, closing = garageState[slot] == "Closing" }
	end
	return { enabled = LobbyConfig.ClaimEnabled, count = MAX_PLOTS, owners = owners, claims = claims, lastAsk = lastClaimAsk }
end

-- A claim from a garage's prompt. The client only holds the prompt: the garage is the prompt's own and the distance is
-- measured here. The check and the claim run with no yield in between, so of two requests at once the first wins.
requestClaim = function(player, slot)
	if not inPlaza[player] then return end -- already moving in or playing, or gone
	local now = os.clock()
	local root = player.Character and player.Character:FindFirstChild("HumanoidRootPart")
	local post = claimPart(slot, "ClaimPost")
	local distance = root and post and (root.Position - post.Position).Magnitude or nil
	local ok, reason = LobbyConfig.canClaim(claimState(), { userId = player.UserId, slot = slot, distance = distance, now = now })
	lastClaimAsk[player.UserId] = now
	if not ok then
		ShopServer.notify(player, reason)
		return
	end
	claimGarage(player, slot)
end

-- ClaimEnabled off: the server claims the first free garage for a joining player and sends them in, as before. With none
-- free (one is closing: its leave save still runs) or this account's last visit still saving, they wait on the plaza
-- and it tries every second; after LobbyConfig.AutoClaimWait seconds, the old "server is full" kick.
local function autoClaim(player)
	local waited = 0
	while player.Parent and inPlaza[player] do
		for slot = 1, MAX_PLOTS do
			if LobbyConfig.canClaim(claimState(), { userId = player.UserId, slot = slot, auto = true }) then
				claimGarage(player, slot)
				return
			end
		end
		if waited >= LobbyConfig.AutoClaimWait then
			player:Kick(LobbyConfig.Texts.Full)
			return
		end
		task.wait(1)
		waited += 1
	end
end

-- The claim on: a spawn far from the plaza (the SpawnLocation was not moved there) is put on the plaza
local function toPlaza(player, character)
	if not (LobbyConfig.ClaimEnabled and inPlaza[player]) then return end
	local root = character:WaitForChild("HumanoidRootPart", 5)
	if not (root and inPlaza[player]) then return end
	local c = LobbyConfig.PlazaCenter
	local dx, dz = root.Position.X - c.x, root.Position.Z - c.z
	if math.sqrt(dx * dx + dz * dz) > LobbyConfig.PlazaRadius then
		local s = LobbyConfig.PlazaSpawn
		root.CFrame = CFrame.new(s.x, s.y, s.z)
	end
end

-- Joining: the player only enters the plaza. inPlaza is written before anything can yield, so the check below for players
-- who joined while this script was starting never sets anyone up twice. Nothing is read or saved before a claim.
local function onPlayerAdded(player)
	if inPlaza[player] or playerData[player] then return end -- already here: the startup loop and PlayerAdded both called
	inPlaza[player] = true
	player:SetAttribute("Garage", 0) -- 0 = no garage yet (LobbyClient, the shop's Robux buttons)
	if #Players:GetPlayers() > MAX_PLOTS then
		player:Kick(LobbyConfig.Texts.Full) -- more players than garages (Max Players above 6)
		return
	end
	player.CharacterAdded:Connect(function(character)
		toPlaza(player, character)
	end)
	if player.Character then
		task.spawn(toPlaza, player, player.Character)
	end
	if not LobbyConfig.ClaimEnabled then
		autoClaim(player)
	end
end
Players.PlayerAdded:Connect(onPlayerAdded)
-- Players already in the server (they joined while this script was still starting) are set up too
for _, existing in ipairs(Players:GetPlayers()) do
	if not inPlaza[existing] and not playerData[existing] then
		task.spawn(onPlayerAdded, existing)
	end
end

-- Leaving: the garage shows Closing while the leave save runs (the slot stays taken, FR-3). When it returns, the owner's
-- things go, the garage is a new Garage again (Free), and only then may this account claim again: a rejoin from another
-- device waits for it, so its load reads this save.
Players.PlayerRemoving:Connect(function(player)
	inPlaza[player] = nil
	local data = playerData[player]
	local held = claims[player.UserId]
	if data then
		setGarageState(data.slot, "Closing", player.DisplayName)
		if held then held.leaving = true end
	end
	saveOnLeave(player)
	if data then
		data.folder:Destroy()
		resetGarage(data.slot) -- the garage stays: back to a new Garage, Free, with no name on it
		plotOwners[data.slot] = nil
		playerData[player] = nil
		claimedAt[player] = nil
		if claims[player.UserId] == held then
			claims[player.UserId] = nil
		end
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
				syncRoom(data)
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
