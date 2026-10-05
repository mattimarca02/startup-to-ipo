-- CompanyServer: a player's company and their Pokedex (customize PR 1, docs/CUSTOMIZE_PROPOSAL.md sections 1 and 4).
-- Put this ModuleScript in ServerScriptService, next to TycoonCore.
-- TycoonCore owns player data and saving, and plugs this module in with CompanyServer.init.
-- It owns the `pokedex` save section (a new top-level section, rule A10): CompanyConfig (ReplicatedStorage) holds the
-- rules and the pure code that reads and writes it, SectorConfig the sectors. This module is the glue: it sets the
-- section up on join, writes it back on every save, and answers the three office requests.
--
-- PR 1 is invisible to players. The active company's live state stays where it is (cash, owned, team, ipo.valuation);
-- nothing here changes Income, Cash or the valuation (it has no way to pay or earn anything). The office requests only
-- work in Studio until the office screen exists (CompanyConfig.Placement.StudioOnly).
-- The client (later) can ask for exactly three things on CompanyRemotes.CompanyAction:
--   "Place", id, x, z, r   -> put an item you own at x, z (from the plot's front-center), turned r x 45 degrees
--   "Store", id            -> put an item in the inventory
--   "Sync"                 -> the office as the server has it (to draw it, and to preview a placement with CompanyConfig)
-- It sends no price, amount, building number or sector. The server checks everything (ready, rate, types, ownership,
-- inside the building, reserved zones, overlap, limits) with CompanyConfig.checkPlacement and refuses anything else.

local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")

local CompanyConfig = require(ReplicatedStorage:WaitForChild("CompanyConfig"))

local CompanyServer = {}

local core -- { getData, save, plotZones }, given by TycoonCore
local remotes = {}
local zonesCache -- the plot's reserved zones from the anchor (they never change while the server runs)

-- Helpers ---------------------------------------------------------------

-- The reserved zones of a plot, measured from the anchor, or nil when the plot visuals are off
local function zones()
	if zonesCache then return zonesCache end
	local raw, floorDepth = core.plotZones()
	if typeof(raw) ~= "table" then return nil end
	zonesCache = CompanyConfig.anchorZones(raw, floorDepth)
	return zonesCache
end

local function copyObjects(objects)
	local list = {}
	for _, object in ipairs(objects) do
		table.insert(list, { id = object.id, x = object.x, z = object.z, r = object.r })
	end
	return list
end

-- What "Sync" answers: everything the client needs to draw the office and to preview a placement itself
local function snapshot(state)
	local active = state.section.active
	local size = CompanyConfig.Buildings.Sizes[active.building]
	local stored = {}
	for id in pairs(active.stored) do
		table.insert(stored, id)
	end
	table.sort(stored)
	return {
		sector = active.sector,
		building = active.building,
		size = size and { w = size.w, d = size.d } or false,
		objects = copyObjects(active.objects),
		stored = stored,
		zones = zones() or false,
	}
end

-- Requests -----------------------------------------------------------------

-- No yield between a check and the change it allows: a second request always sees the first one's result.
local function onAction(player, action, id, x, z, r)
	if typeof(action) ~= "string" then return false, "Bad request" end
	local data = core.getData(player)
	local state = data and data.pokedex
	if not state or not data.ready then
		return false, "Still loading, try again in a moment" -- loading, or an IPO is being saved
	end
	if not CompanyConfig.takeToken(state.bucket, os.clock()) then
		return false, "Too fast"
	end
	if action ~= "Place" and action ~= "Store" and action ~= "Sync" then
		return false, "Unknown action"
	end
	if not CompanyConfig.isPlacementActive() then
		return false, "Not available yet"
	end
	if state.locked then
		return false, "Your office was saved by a newer version of the game: nothing can be changed here"
	end

	local active = state.section.active
	if action == "Sync" then
		return true, nil, snapshot(state)
	end
	local env = {
		building = active.building,
		zones = zones(),
		owned = data.owned,
		decor = active.decor,
		objects = active.objects,
	}
	if action == "Place" then
		local ok, reason = CompanyConfig.checkPlacement(env, id, x, z, r)
		if not ok then return false, reason end
		CompanyConfig.applyPlace(active, id, x, z, r)
		return true, "Placed " .. id, { id = id, x = x, z = z, r = r }
	end
	local ok, reason = CompanyConfig.checkStore(env, active, id)
	if not ok then return false, reason end
	CompanyConfig.applyStore(active, id)
	return true, id .. " is in storage", { id = id }
end

-- Saving (TycoonCore calls these) ----------------------------------------------

-- Called right after the player's save loads, after OnboardingServer and before TaskServer (IpoServer ran earlier,
-- so data.ipo.count is there for the run check). savedPokedex is the "pokedex" part of the save, or nil (every save
-- from before this version, and new players): a new founding. Nothing is granted or changed here. A bad section is
-- repaired with a warning; one this version can't read is kept as it was (state.locked) and writes nothing new.
function CompanyServer.setupPlayer(player, data, savedPokedex)
	local ctx = {
		warn = warn,
		who = player.Name,
		ipoCount = data.ipo and data.ipo.count or 0,
		now = os.time(),
	}
	local ok, state = pcall(CompanyConfig.load, savedPokedex, ctx)
	if not ok then
		-- Never lose a section because of a bug: keep it exactly as it was and let nothing change it
		warn("Could not read " .. player.Name .. "'s pokedex, keeping it as it was: " .. tostring(state))
		state = { locked = true, raw = savedPokedex }
	end
	state.bucket = CompanyConfig.newBucket(os.clock()) -- the request limit (not saved)
	data.pokedex = state
end

-- The part of the save file that belongs to the Pokedex (nil only for a section that failed to load and never existed)
function CompanyServer.serialize(data)
	local state = data.pokedex
	if not state then return nil end
	return CompanyConfig.toSave(state, RunService:IsStudio())
end

-- An IPO done by this version (TycoonCore.commitIpo): the company's run follows the IPO count. PR 1 has no IPO
-- transform (no stamp, no card, no sector completion: PR 4 turns those on), so run just moves with the count and a
-- later join never mistakes this version's own IPO for one an older version ran (the run check, CompanyConfig.load).
-- Two steps, because the IPO's save is built before the count rises and a crash right after it must not leave run behind:
--   writeIpoRun(data, payload, count)  inside the IPO's save transform: the payload that gets written carries the new run
--   onIpo(data, count)                 only after that save worked: the section in memory follows
-- Neither changes anything for a locked section (commitIpo refuses to go public then) and neither can throw.
function CompanyServer.writeIpoRun(data, payload, count)
	local state = data and data.pokedex
	if state == nil or state.locked or typeof(payload) ~= "table" or typeof(payload.pokedex) ~= "table" then return end
	payload.pokedex.run = count
end

function CompanyServer.onIpo(data, count)
	local state = data and data.pokedex
	if state == nil or state.locked or typeof(state.section) ~= "table" then return end
	state.section.run = count
end

-- True while this session must not change the company: the section is from a newer version (or its sector is), or
-- it couldn't be read. TycoonCore refuses to go public then (the IPO would reset a company this version can't stamp).
function CompanyServer.isLocked(data)
	local state = data and data.pokedex
	return state ~= nil and state.locked == true
end

-- Setup -----------------------------------------------------------------

function CompanyServer.init(coreApi)
	core = coreApi

	local folder = Instance.new("Folder")
	folder.Name = "CompanyRemotes"
	remotes.action = Instance.new("RemoteFunction")
	remotes.action.Name = "CompanyAction"
	remotes.action.OnServerInvoke = onAction
	remotes.action.Parent = folder
	folder.Parent = ReplicatedStorage
end

return CompanyServer
