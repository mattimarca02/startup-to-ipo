-- CompanyConfig: the rules of a company's office and the saved Pokedex, in one place (customize PR 1,
-- docs/CUSTOMIZE_PROPOSAL.md sections 1.2, 1.4, 3 and 4).
-- Put this ModuleScript in ReplicatedStorage, next to SectorConfig (CompanyServer reads it now, and the
-- office screen will read it later: the client previews a placement with the same function, the server decides).
--
-- Everything here is pure: numbers, tables and functions with no Roblox state, so tools/daily_test.py runs
-- the real code. The `pokedex` save section is written by CompanyServer.serialize (the data) and read here:
--   CompanyConfig.load(saved, ctx)     -> the state of a joining player (bad values skipped, unknown fields kept, run check)
--   CompanyConfig.toSave(state, studio) -> the section to write (an unknown newer version is written back unchanged)
--   CompanyConfig.checkPlacement(...)  -> is "Place id at x, z, rotation r" allowed? (one function, client and server)
-- Rules for the section (CLAUDE.md rule A10 and docs/CUSTOMIZE_PROPOSAL.md 1.2):
--   * Old saves keep loading: every field is optional and gets a default. A bad value is skipped with a warning.
--   * Unknown fields are KEPT at every level (the section, active, objects[i], rounds[k], sectors[k], card, ...) and
--     written back as they were: code that doesn't know a field never deletes it. One exception: what the DataStore can't hold.
--     SetAsync is believed to refuse a table that mixes list and string keys and to lose what comes after a hole (a review's finding;
--     docs/CUSTOMIZE_PR1_NOTES.md has the Studio test that settles it, not run yet). So a list
--     (card.owned, the placed items) is tidied on load into a plain list 1 .. n, and a key that can't sit next to the named fields
--     or next to a list is dropped, each with a warning, never written back as it was.
--   * `v` rises only when a field changes meaning. A higher `v` is kept opaque and unchanged, and the session
--     refuses everything that would change the company (a placement, a store, an IPO).
-- PR 1 is invisible to players: nothing here changes how the game plays, and the placement actions only work in Studio.
-- No text here may claim odds or chance (D9).

local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")

local SectorConfig = require(ReplicatedStorage:WaitForChild("SectorConfig"))
local IpoConfig = require(ReplicatedStorage:WaitForChild("IpoConfig"))

local CompanyConfig = {}

CompanyConfig.Version = 1 -- the pokedex format this code writes (`v`)

-- Placement ("Place", "Store" and "Sync" on CompanyRemotes.CompanyAction). Nothing draws a placed object until the
-- office screen exists (PR 3), so until then the actions work only in Studio (like TaskConfig.StudioOnly).
CompanyConfig.Placement = {
	Enabled = true,
	StudioOnly = true,
}

function CompanyConfig.isPlacementActive()
	local placement = CompanyConfig.Placement
	return placement.Enabled == true and (placement.StudioOnly ~= true or RunService:IsStudio())
end

-- Buildings: footprints in studs, nested (building n + 1 contains building n). Coordinates are measured from the
-- ANCHOR = the front-center of the plot's Floor: +x right, z 0 at the front edge and going back (negative) toward the
-- back wall. So the default Desk slot (x -23, z -10 from the plot center) is x -23, z -40. The sizes are estimates
-- (docs/CUSTOMIZE_PROPOSAL.md section 3); building 1 is today's 60 x 60 garage. Prices and the switch come with PR 2.
CompanyConfig.Buildings = {
	Sizes = {
		{ w = 60, d = 60 },
		{ w = 64, d = 66 },
		{ w = 68, d = 70 },
		{ w = 72, d = 76 },
		{ w = 78, d = 82 },
	},
}
CompanyConfig.FloorDepth = 60 -- TycoonCore's Floor Part is 60 deep: the plot center is 30 studs behind the anchor

-- What an object may be asked to do (all checked again on the server)
CompanyConfig.Grid = 0.5 -- x and z are whole steps of this many studs
CompanyConfig.MaxRotation = 7 -- r = 0 to 7, in steps of 45 degrees
CompanyConfig.MaxObjects = 40 -- placed items per company
CompanyConfig.MaxStored = 40 -- items in the inventory per company
CompanyConfig.MaxIdLength = 39 -- an id is a string under 40 characters
CompanyConfig.MaxCopies = 99 -- furniture ids are "<objectKey>#<n>", n = 1 to this
CompanyConfig.MaxCoordinate = 1000 -- sanity bound for x and z, far outside any building
CompanyConfig.OverlapTolerance = 0.1 -- two footprints may overlap by this many studs at most
CompanyConfig.RateLimit = { perSecond = 4, burst = 4 } -- requests per player on CompanyAction

-- Footprints (width x, depth z at rotation 0), centered on the object's x, z. An upgrade's footprint is the box
-- around its PlotArt prop (tools/daily_test.py checks that it contains every part). Upgrade names are TycoonCore's
-- UPGRADES names (saved, never renamed).
CompanyConfig.Footprints = {
	["Desk"] = { w = 8.4, d = 7.6 },
	["Coffee Machine"] = { w = 5.0, d = 2.9 },
	["Laptop"] = { w = 5.8, d = 3.3 },
	["Server Rack"] = { w = 5.4, d = 3.9 },
	["Whiteboard"] = { w = 9.7, d = 3.7 },
	["Neon Logo"] = { w = 11.9, d = 3.4 },
}

-- Furniture (decor you own several of): objectKey -> { name, w, d }. None yet: it comes with the sector content
-- (PR 5-7). Keys are saved (pokedex.active.decor, pokedex.kept): never renamed or reused.
CompanyConfig.Furniture = {}

-- The Cash passes whose engaged seconds the Pokedex counts (ShopConfig keys; passSeconds)
CompanyConfig.CashPassKeys = { "DoubleCash", "VIP" }

-- Funding rounds (PR 4b adds the rest): the one number the saved card needs now. Placeholder (S8).
CompanyConfig.Funding = {
	DilutionCap = 4000, -- basis points: total dilution never counts for more than this
}

local TOTAL_BP = 10000

-- Helpers ---------------------------------------------------------------------

local function isNumber(value)
	return typeof(value) == "number" and value == value and value ~= math.huge and value ~= -math.huge
end

local function isWhole(value, minimum, maximum)
	return isNumber(value) and value % 1 == 0 and value >= minimum and (maximum == nil or value <= maximum)
end

local function deepCopy(value)
	if typeof(value) ~= "table" then
		return value
	end
	local copy = {}
	for key, inner in pairs(value) do
		copy[key] = deepCopy(inner)
	end
	return copy
end
CompanyConfig.deepCopy = deepCopy

local function setOf(list)
	local set = {}
	for _, key in ipairs(list) do
		set[key] = true
	end
	return set
end

local PASS_KEYS = setOf(CompanyConfig.CashPassKeys)
local STAGE_KEYS = {}
for _, stage in ipairs(IpoConfig.Stages) do
	STAGE_KEYS[stage.key] = true
end

-- Items: ids ----------------------------------------------------------------------

-- "Desk" (an upgrade) or "<objectKey>#<n>" (furniture n of that key). Returns kind, key, n, or nil for anything else.
function CompanyConfig.parseId(id)
	if typeof(id) ~= "string" or #id < 1 or #id > CompanyConfig.MaxIdLength then
		return nil
	end
	if CompanyConfig.Footprints[id] then
		return "upgrade", id, 1
	end
	local key, copy = string.match(id, "^([^#]+)#(%d+)$")
	if key and CompanyConfig.Furniture[key] then
		local n = tonumber(copy)
		if n and n >= 1 and n <= CompanyConfig.MaxCopies then
			return "furniture", key, n
		end
	end
	return nil
end

-- Width and depth of an item, or nil when it has no footprint (an id this version doesn't know)
function CompanyConfig.footprintOf(id)
	local kind, key = CompanyConfig.parseId(id)
	if kind == "upgrade" then
		local footprint = CompanyConfig.Footprints[key]
		return footprint.w, footprint.d
	elseif kind == "furniture" then
		local furniture = CompanyConfig.Furniture[key]
		return furniture.w, furniture.d
	end
	return nil
end

-- Geometry: footprints are rectangles turned in 45 degree steps ---------------------

-- The four corners of a w x d rectangle centered on x, z and turned r steps
local function corners(w, d, x, z, r)
	local angle = math.rad(45 * r)
	local c, s = math.cos(angle), math.sin(angle)
	local out = {}
	for _, corner in ipairs({ { -w / 2, -d / 2 }, { w / 2, -d / 2 }, { w / 2, d / 2 }, { -w / 2, d / 2 } }) do
		table.insert(out, { x + corner[1] * c - corner[2] * s, z + corner[1] * s + corner[2] * c })
	end
	return out
end

local function axisRect(x0, x1, z0, z1)
	return { { x0, z0 }, { x1, z0 }, { x1, z1 }, { x0, z1 } }
end

-- How deep two rectangles overlap (0 = apart or only touching): the smallest overlap over every edge direction
-- (the separating axis test). Rectangles are given as four corners in order.
local function overlapDepth(a, b)
	local depth = math.huge
	for _, polygon in ipairs({ a, b }) do
		for i = 1, 2 do -- two edge directions are enough for a rectangle
			local p, q = polygon[i], polygon[i + 1]
			local nx, nz = q[2] - p[2], p[1] - q[1]
			local length = math.sqrt(nx * nx + nz * nz)
			if length > 0 then
				nx, nz = nx / length, nz / length
				local aMin, aMax, bMin, bMax = math.huge, -math.huge, math.huge, -math.huge
				for _, corner in ipairs(a) do
					local projection = corner[1] * nx + corner[2] * nz
					aMin, aMax = math.min(aMin, projection), math.max(aMax, projection)
				end
				for _, corner in ipairs(b) do
					local projection = corner[1] * nx + corner[2] * nz
					bMin, bMax = math.min(bMin, projection), math.max(bMax, projection)
				end
				local overlap = math.min(aMax, bMax) - math.max(aMin, bMin)
				if overlap <= 0 then
					return 0
				end
				depth = math.min(depth, overlap)
			end
		end
	end
	return depth == math.huge and 0 or depth
end
CompanyConfig.overlapDepth = overlapDepth

local EPSILON = 1e-6

-- The reserved gameplay zones (PlotVisuals.zones) are boxes measured from the plot's floor-top center. Placement
-- works from the anchor, so each zone becomes { x0, x1, z0, z1, owner, name } with z moved by half the floor depth.
function CompanyConfig.anchorZones(rawZones, floorDepth)
	local zones = {}
	local shift = (floorDepth or CompanyConfig.FloorDepth) / 2
	for _, zone in ipairs(rawZones) do
		local box = zone.box
		table.insert(zones, { x0 = box[1], x1 = box[2], z0 = box[5] - shift, z1 = box[6] - shift, owner = zone.owner, name = zone.name })
	end
	return zones
end

-- Placement ---------------------------------------------------------------------

-- Is "put `id` at x, z, turned r steps" allowed? The client previews with it, the server decides with it.
-- env = {
--   building = number (1 = Garage),          zones = the list from anchorZones (nil = refuse: the plot's zones are unknown),
--   owned = { [upgradeName] = true },        decor = { [objectKey] = copies owned },
--   objects = { { id, x, z, r }, ... }       (the placed items now; an entry for the same id is being moved)
-- }
-- Returns true, or false and the reason shown to the player.
function CompanyConfig.checkPlacement(env, id, x, z, r)
	if typeof(id) ~= "string" or #id < 1 or #id > CompanyConfig.MaxIdLength then
		return false, "Unknown item"
	end
	local limit = CompanyConfig.MaxCoordinate
	if not isNumber(x) or not isNumber(z) or math.abs(x) > limit or math.abs(z) > limit then
		return false, "That spot isn't valid"
	end
	if (x / CompanyConfig.Grid) % 1 ~= 0 or (z / CompanyConfig.Grid) % 1 ~= 0 then
		return false, "That spot isn't on the grid"
	end
	if not isWhole(r, 0, CompanyConfig.MaxRotation) then
		return false, "That turn isn't valid"
	end
	local kind, key, copy = CompanyConfig.parseId(id)
	if not kind then
		return false, "You can't place that yet"
	end
	if kind == "upgrade" then
		if not (env.owned and env.owned[key]) then
			return false, "You don't own " .. id
		end
	elseif not (env.decor and (env.decor[key] or 0) >= copy) then
		return false, "You don't own " .. id
	end
	local building = CompanyConfig.Buildings.Sizes[env.building]
	if not building then
		return false, "Your office isn't ready for that yet"
	end
	if typeof(env.zones) ~= "table" then
		return false, "The office layout isn't available right now"
	end

	local w, d = CompanyConfig.footprintOf(id)
	local shape = corners(w, d, x, z, r)

	-- Inside the building: every corner within its walls
	for _, corner in ipairs(shape) do
		if corner[1] < -building.w / 2 - EPSILON or corner[1] > building.w / 2 + EPSILON
			or corner[2] < -building.d - EPSILON or corner[2] > EPSILON then
			return false, "That doesn't fit inside your office"
		end
	end

	-- Reserved zones: the walkways, the hire desks, the signs, the incubators and the other upgrades' slots
	local tolerance = CompanyConfig.OverlapTolerance + EPSILON
	for _, zone in ipairs(env.zones) do
		if zone.owner ~= id and overlapDepth(shape, axisRect(zone.x0, zone.x1, zone.z0, zone.z1)) > tolerance then
			return false, "That spot is reserved"
		end
	end

	-- The other placed items (the same id is being moved, so it doesn't block itself or count against the limit)
	local others = 0
	for _, other in ipairs(env.objects or {}) do
		if other.id ~= id then
			others += 1
			local ow, od = CompanyConfig.footprintOf(other.id)
			if ow and overlapDepth(shape, corners(ow, od, other.x, other.z, other.r)) > tolerance then
				return false, "That spot is taken"
			end
		end
	end
	if others >= CompanyConfig.MaxObjects then
		return false, "Your office can't hold more items"
	end
	return true
end

-- Is "store `id`" allowed? (the item goes to the inventory; stored items still earn). active = pokedex.active.
function CompanyConfig.checkStore(env, active, id)
	if typeof(id) ~= "string" or #id < 1 or #id > CompanyConfig.MaxIdLength then
		return false, "Unknown item"
	end
	local kind, key, copy = CompanyConfig.parseId(id)
	if not kind then
		return false, "You can't store that yet"
	end
	if kind == "upgrade" then
		if not (env.owned and env.owned[key]) then
			return false, "You don't own " .. id
		end
	elseif not (env.decor and (env.decor[key] or 0) >= copy) then
		return false, "You don't own " .. id
	end
	local held = active.stored[id]
	if held == true then
		return false, id .. " is already in storage"
	elseif held ~= nil and held ~= false then
		return false, "You can't store that yet" -- a record of a newer version sits there: never overwritten
	end
	local count = 0
	for _ in pairs(active.stored) do
		count += 1
	end
	if count >= CompanyConfig.MaxStored then
		return false, "Your storage is full"
	end
	return true
end

-- The state change of an allowed Place: the item stands at x, z, turned r, and leaves the inventory
function CompanyConfig.applyPlace(active, id, x, z, r)
	for _, object in ipairs(active.objects) do
		if object.id == id then
			object.x, object.z, object.r = x, z, r
			if active.stored[id] == true then active.stored[id] = nil end
			return
		end
	end
	table.insert(active.objects, { id = id, x = x, z = z, r = r })
	if active.stored[id] == true then active.stored[id] = nil end
end

-- The state change of an allowed Store: the item leaves the office and goes to the inventory
function CompanyConfig.applyStore(active, id)
	for i, object in ipairs(active.objects) do
		if object.id == id then
			table.remove(active.objects, i)
			break
		end
	end
	active.stored[id] = true
end

-- The items in the inventory: the ids in `stored`, plus owned furniture with no entry in `objects`. Sorted, so the
-- answer never depends on table order. (An owned upgrade that was never placed stands at its default slot: not here.)
function CompanyConfig.inventory(active, decor)
	local placed = {}
	for _, object in ipairs(active.objects) do
		placed[object.id] = true
	end
	local list = {}
	for id, held in pairs(active.stored) do
		if held == true then
			table.insert(list, id)
		end
	end
	for key, copies in pairs(decor or {}) do
		if CompanyConfig.Furniture[key] and isWhole(copies, 1, CompanyConfig.MaxCopies) then
			for n = 1, copies do
				local id = key .. "#" .. n
				if not placed[id] and active.stored[id] ~= true then
					table.insert(list, id)
				end
			end
		end
	end
	table.sort(list)
	return list
end

-- A request limit per player: a bucket of `burst` requests that refills `perSecond` a second. bucket.at is a clock in seconds.
function CompanyConfig.newBucket(now)
	return { tokens = CompanyConfig.RateLimit.burst, at = now }
end

function CompanyConfig.takeToken(bucket, now)
	local limit = CompanyConfig.RateLimit
	bucket.tokens = math.min(limit.burst, bucket.tokens + math.max(0, now - bucket.at) * limit.perSecond)
	bucket.at = now
	if bucket.tokens < 1 then
		return false
	end
	bucket.tokens -= 1
	return true
end

-- Funding rounds: the dilution already saved --------------------------------------

-- The total dilution of a company in basis points: the sum of every round's `bp` that is a whole 0 to 10,000
-- (a round under a stage key this version doesn't know counts too), never more than Funding.DilutionCap.
function CompanyConfig.dilution(rounds)
	local total = 0
	for _, round in pairs(rounds or {}) do
		if typeof(round) == "table" and isWhole(round.bp, 0, TOTAL_BP) then
			total += round.bp
		end
	end
	return math.min(CompanyConfig.Funding.DilutionCap, total)
end

-- The founder's stake in basis points (10,000 = everything)
function CompanyConfig.stakeOf(rounds)
	return TOTAL_BP - CompanyConfig.dilution(rounds)
end

-- The saved Pokedex: loading ---------------------------------------------------------

local TOP_KNOWN = setOf({ "v", "run", "active", "sectors", "kept", "hall", "dust", "studio" })
local ACTIVE_KNOWN = setOf({ "sector", "picked", "name", "foundedAt", "engaged", "passSeconds", "building", "decor", "objects", "stored", "told", "rounds", "sx" })
local OBJECT_KNOWN = setOf({ "id", "x", "z", "r" })
local ROUND_KNOWN = setOf({ "s", "c", "cash", "bp", "at", "studio" })
local SECTOR_KNOWN = setOf({ "state", "stamp", "replays", "firstAt", "bestEngaged", "card" })
local CARD_KNOWN = setOf({ "name", "ipoNumber", "at", "engaged", "ratio", "building", "owned", "decor", "objects", "rounds", "stake", "shares", "sx" })

local MAX_NAME_LENGTH = 60
local MAX_OWNED_NAMES = 200
local MAX_BUILDING = 99 -- a saved building number above Buildings.Sizes is kept (a newer version); it just can't be used here

-- ctx = { warn = function(text), who = "PlayerName", ipoCount = number, now = os.time() }
local function note(ctx, text)
	ctx.warn("Skipped in " .. ctx.who .. "'s pokedex: " .. text)
end

-- The unknown fields of a table that has named fields: kept as they were. A key that isn't a string can't sit next to the named
-- fields in a saved table (the store refuses a table that mixes keys), so it is dropped, with a warning.
local function copyUnknown(ctx, where, raw, known, out)
	for key, value in pairs(raw) do
		if typeof(key) ~= "string" then
			note(ctx, "a key in " .. where .. " that isn't a name, dropped (" .. tostring(key) .. ")")
		elseif not known[key] then
			out[key] = deepCopy(value)
		end
	end
end

-- A list the store can hold has exactly the keys 1, 2, 3 ... in a row; a map has only string keys; a table with both, or with
-- a gap, is refused. splitKeys gives the positive whole keys of a table in order, and every other key, for the readers
-- of lists below to tidy it: the values under the positive keys go into a plain list, in key order, gaps closed.
local function splitKeys(value)
	local indexes, others = {}, {}
	for key in pairs(value) do
		if isWhole(key, 1) then
			table.insert(indexes, key)
		else
			table.insert(others, key)
		end
	end
	table.sort(indexes)
	return indexes, others
end

local function noteGap(ctx, where, indexes)
	for position, index in ipairs(indexes) do
		if index ~= position then
			note(ctx, where .. " had a gap in its list: what comes after it moved up")
			return
		end
	end
end

-- A number field: the value when it is good, else the default (with a warning)
local function readNumber(ctx, where, raw, key, default, minimum, maximum, whole)
	local value = raw[key]
	if value == nil then
		return default
	end
	if isNumber(value) and value >= minimum and (maximum == nil or value <= maximum) and (not whole or value % 1 == 0) then
		return value
	end
	note(ctx, "a bad " .. where .. "." .. key .. " (" .. tostring(value) .. ")")
	return default
end

local function readString(ctx, where, raw, key, default)
	local value = raw[key]
	if value == nil then
		return default
	end
	if typeof(value) == "string" and #value >= 1 and #value <= MAX_NAME_LENGTH then
		return value
	end
	note(ctx, "a bad " .. where .. "." .. key)
	return default
end

local function readBoolean(ctx, where, raw, key, default)
	local value = raw[key]
	if value == nil then
		return default
	end
	if typeof(value) == "boolean" then
		return value
	end
	note(ctx, "a bad " .. where .. "." .. key .. " (" .. tostring(value) .. ")")
	return default
end

-- A table of anything the sector module keeps whole (`sx`): a bad one becomes {}
local function readWhole(ctx, where, raw, key)
	local value = raw[key]
	if value == nil then
		return {}
	end
	if typeof(value) == "table" then
		return deepCopy(value)
	end
	note(ctx, "a bad " .. where .. "." .. key .. ", it starts again empty")
	return {}
end

-- A map keyed by strings. The values of keys this version knows are checked (`valid` returns the value or nil);
-- an unknown key keeps its value as it is: code without this rule would drop it.
local function readMap(ctx, where, raw, key, isKnown, valid)
	local value = raw[key]
	local out = {}
	if value == nil then
		return out
	end
	if typeof(value) ~= "table" then
		note(ctx, "a bad " .. where .. "." .. key)
		return out
	end
	for name, inner in pairs(value) do
		if typeof(name) ~= "string" then
			note(ctx, "a bad key in " .. where .. "." .. key)
		elseif isKnown(name) then
			local good = valid(inner)
			if good ~= nil then
				out[name] = good
			else
				note(ctx, "a bad " .. where .. "." .. key .. "." .. name .. " (" .. tostring(inner) .. ")")
			end
		else
			out[name] = deepCopy(inner)
		end
	end
	return out
end

local function validCopies(value)
	return isWhole(value, 0, 999) and value or nil
end

local function validSeconds(value)
	return isNumber(value) and value >= 0 and value or nil
end

local function validTime(value)
	return isWhole(value, 0) and value or nil
end

local function validTrue(value)
	return value == true and true or nil
end

local function isFurniture(name)
	return CompanyConfig.Furniture[name] ~= nil
end

local function isPass(name)
	return PASS_KEYS[name] == true
end

local function isStage(name)
	return STAGE_KEYS[name] == true
end

local function isGoal(name)
	return SectorConfig.getGoal(name) ~= nil
end

-- The placed items: { id, x, z, r } with unknown fields kept. An entry that isn't well formed, repeats an id
-- or is over the limit is skipped. An id this version has no item for is KEPT (a newer version's item): it just
-- has no footprint here. The list is tidied on load: the entries are read in key order and written back as a plain list
-- 1 .. n (a gap is closed, with a warning), and a key that can't sit next to a list (a string, 0, a negative or fractional
-- number) is dropped, with a warning, because the store refuses a table that mixes keys or has holes. A table with ONLY
-- string keys (a map: a shape this version doesn't know, and one the store can hold) sets ctx.foreign and CompanyConfig.load
-- keeps the whole section as it was (locked), because a list can't carry it back.
local function readObjects(ctx, where, raw, key)
	local value = raw[key]
	local out = {}
	if value == nil then
		return out
	end
	if typeof(value) ~= "table" then
		note(ctx, "a bad " .. where .. "." .. key)
		return out
	end
	local indexes, others = splitKeys(value)
	if #indexes == 0 and #others > 0 then
		local onlyStrings = true
		for _, other in ipairs(others) do
			if typeof(other) ~= "string" then
				onlyStrings = false
			end
		end
		if onlyStrings then
			ctx.foreign = ctx.foreign or (where .. "." .. key .. " is not a plain list")
			return out
		end
	end
	noteGap(ctx, where .. "." .. key, indexes)
	local seen = {}
	for _, index in ipairs(indexes) do
		local entry = value[index]
		local limit = CompanyConfig.MaxCoordinate
		local good = typeof(entry) == "table"
			and typeof(entry.id) == "string" and #entry.id >= 1 and #entry.id <= CompanyConfig.MaxIdLength
			and isNumber(entry.x) and math.abs(entry.x) <= limit and (entry.x / CompanyConfig.Grid) % 1 == 0
			and isNumber(entry.z) and math.abs(entry.z) <= limit and (entry.z / CompanyConfig.Grid) % 1 == 0
			and isWhole(entry.r, 0, CompanyConfig.MaxRotation)
		if not good then
			note(ctx, "a bad item in " .. where .. "." .. key .. " (number " .. index .. ")")
		elseif seen[entry.id] then
			note(ctx, "a repeated item in " .. where .. "." .. key .. ": " .. entry.id)
		elseif #out >= CompanyConfig.MaxObjects then
			note(ctx, "too many items in " .. where .. "." .. key .. ": " .. entry.id)
		else
			seen[entry.id] = true
			local object = { id = entry.id, x = entry.x, z = entry.z, r = entry.r }
			copyUnknown(ctx, where .. "." .. key .. "[" .. index .. "]", entry, OBJECT_KNOWN, object)
			table.insert(out, object)
		end
	end
	for _, other in ipairs(others) do
		note(ctx, "a key in " .. where .. "." .. key .. " that can't sit next to a list, dropped (" .. tostring(other) .. ")")
	end
	return out
end

-- The inventory: { [id] = true }. Ids are kept even when this version has no item for them, and so is a value other
-- than true (a newer version's record for that id, or false): only `== true` means "in storage" here, and the other
-- values are written back as they were. They count toward the limit like any other entry.
local function readStored(ctx, where, raw, key)
	local value = raw[key]
	local out = {}
	if value == nil then
		return out
	end
	if typeof(value) ~= "table" then
		note(ctx, "a bad " .. where .. "." .. key)
		return out
	end
	local ids = {}
	for id, flag in pairs(value) do
		if typeof(id) == "string" and #id >= 1 and #id <= CompanyConfig.MaxIdLength then
			table.insert(ids, id)
		else
			note(ctx, "a bad entry in " .. where .. "." .. key .. " (" .. tostring(id) .. ")")
		end
	end
	table.sort(ids) -- if there are too many, the same ones are kept every time
	for i, id in ipairs(ids) do
		if i <= CompanyConfig.MaxStored then
			out[id] = deepCopy(value[id])
		else
			note(ctx, "too many items in " .. where .. "." .. key .. ": " .. id)
		end
	end
	return out
end

-- One funding round of a stage this version knows. Never dropped: a record that isn't well formed still counts
-- as settled, with no dilution (dropping it would allow a second raise). Unknown fields are kept.
local function readRound(ctx, where, value)
	local settled = { s = "skipped", c = 0, cash = 0, bp = 0, at = 0, studio = false }
	if typeof(value) ~= "table" then
		note(ctx, "a bad " .. where .. ", counted as settled")
		return settled
	end
	local good = (value.s == "raised" or value.s == "skipped")
		and (value.c == nil or isWhole(value.c, 0, 99))
		and (value.cash == nil or isWhole(value.cash, 0))
		and (value.bp == nil or isWhole(value.bp, 0, TOTAL_BP))
		and (value.at == nil or isWhole(value.at, 0))
		and (value.studio == nil or typeof(value.studio) == "boolean")
	if not good then
		note(ctx, "a bad " .. where .. ", counted as settled with no dilution")
		copyUnknown(ctx, where, value, ROUND_KNOWN, settled)
		return settled
	end
	local round = { s = value.s, c = value.c or 0, cash = value.cash or 0, bp = value.bp or 0, at = value.at or 0, studio = value.studio or false }
	copyUnknown(ctx, where, value, ROUND_KNOWN, round)
	return round
end

local function readRounds(ctx, where, raw, key)
	local value = raw[key]
	local out = {}
	if value == nil then
		return out
	end
	if typeof(value) ~= "table" then
		note(ctx, "a bad " .. where .. "." .. key)
		return out
	end
	for name, inner in pairs(value) do
		if typeof(name) ~= "string" then
			note(ctx, "a bad key in " .. where .. "." .. key)
		elseif isStage(name) then
			out[name] = readRound(ctx, where .. "." .. key .. "." .. name, inner)
		else
			out[name] = deepCopy(inner) -- a stage this version doesn't know: kept whole, its bp still counts
		end
	end
	return out
end

-- The upgrade names on a card: a list of strings (it is a set of names, so their order is not data). Names this version has no
-- upgrade for are kept. The list is tidied on load, because the store refuses a table that mixes list and string keys, and a
-- list with holes loses what comes after a hole: every valid name goes into a plain list 1 .. n in key order (a gap is closed,
-- with a warning), and any other key (a string, 0, a negative or fractional number) is dropped, with a warning. A table with
-- ONLY string keys (no name at all) is kept as it is. A value that isn't a name (not a string, empty, over 39 characters) or a
-- name past the limit is skipped, with a warning; a repeated name is kept, as it always was.
local function readOwnedNames(ctx, where, raw, key)
	local value = raw[key]
	local out = {}
	if value == nil then
		return out
	end
	if typeof(value) ~= "table" then
		note(ctx, "a bad " .. where .. "." .. key)
		return out
	end
	local indexes, others = splitKeys(value)
	noteGap(ctx, where .. "." .. key, indexes)
	for _, index in ipairs(indexes) do
		local name = value[index]
		if typeof(name) == "string" and #name >= 1 and #name <= CompanyConfig.MaxIdLength and #out < MAX_OWNED_NAMES then
			table.insert(out, name)
		else
			note(ctx, "a bad name in " .. where .. "." .. key)
		end
	end
	for _, other in ipairs(others) do
		if #out == 0 and typeof(other) == "string" then
			out[other] = deepCopy(value[other]) -- no names at all: a map, kept as it is
		else
			note(ctx, "a key in " .. where .. "." .. key .. " that can't sit next to a list, dropped (" .. tostring(other) .. ")")
		end
	end
	return out
end

-- The card of a finished company
local function readCard(ctx, where, value)
	if value == nil then
		return nil
	end
	if typeof(value) ~= "table" then
		note(ctx, "a bad " .. where)
		return nil
	end
	local here = where
	local card = {
		name = readString(ctx, here, value, "name", SectorConfig.defaultName(SectorConfig.Default) or "My Startup"),
		ipoNumber = readNumber(ctx, here, value, "ipoNumber", 0, 0, nil, true),
		at = readNumber(ctx, here, value, "at", 0, 0, nil, true),
		engaged = readNumber(ctx, here, value, "engaged", 0, 0),
		ratio = readNumber(ctx, here, value, "ratio", 0, 0),
		building = readNumber(ctx, here, value, "building", 1, 1, MAX_BUILDING, true),
		owned = readOwnedNames(ctx, here, value, "owned"),
		decor = readMap(ctx, here, value, "decor", isFurniture, validCopies),
		objects = readObjects(ctx, here, value, "objects"),
		rounds = readRounds(ctx, here, value, "rounds"),
		stake = readNumber(ctx, here, value, "stake", TOTAL_BP, 0, TOTAL_BP, true),
		shares = readNumber(ctx, here, value, "shares", 0, 0, nil, true),
		sx = readWhole(ctx, here, value, "sx"),
	}
	copyUnknown(ctx, here, value, CARD_KNOWN, card)
	return card
end

local function readSectorEntry(ctx, key, value)
	if typeof(value) ~= "table" then
		note(ctx, "a bad sectors." .. key)
		return nil
	end
	local where = "sectors." .. key
	local entry = {}
	local state = value.state
	if state == "progress" or state == "done" then
		entry.state = state
	else
		if state ~= nil then
			note(ctx, "a bad " .. where .. ".state (" .. tostring(state) .. ")")
		end
		entry.state = "progress"
	end
	local stamp = value.stamp
	if isNumber(stamp) then
		entry.stamp = math.clamp(math.floor(stamp), 0, 3)
		if entry.stamp ~= stamp then
			note(ctx, "a " .. where .. ".stamp out of range (" .. tostring(stamp) .. ")")
		end
	else
		if stamp ~= nil then
			note(ctx, "a bad " .. where .. ".stamp (" .. tostring(stamp) .. ")")
		end
		entry.stamp = 0
	end
	if entry.state == "done" and entry.stamp == 0 then
		entry.stamp = 1 -- a finished sector always has at least Bronze
	end
	entry.replays = readNumber(ctx, where, value, "replays", 0, 0, nil, true)
	entry.firstAt = readNumber(ctx, where, value, "firstAt", 0, 0, nil, true)
	entry.bestEngaged = readNumber(ctx, where, value, "bestEngaged", 0, 0)
	entry.card = readCard(ctx, where .. ".card", value.card)
	copyUnknown(ctx, where, value, SECTOR_KNOWN, entry)
	return entry
end

local function readSectors(ctx, raw)
	local value = raw.sectors
	local out = {}
	if value == nil then
		return out
	end
	if typeof(value) ~= "table" then
		note(ctx, "a bad sectors")
		return out
	end
	for key, inner in pairs(value) do
		if typeof(key) ~= "string" then
			note(ctx, "a bad key in sectors")
		elseif SectorConfig.isKnown(key) then
			out[key] = readSectorEntry(ctx, key, inner)
		else
			out[key] = deepCopy(inner) -- a sector this version doesn't know: kept whole
		end
	end
	return out
end

-- A new company: building 1, nothing owned or placed. `picked` is false only while the picker is open.
function CompanyConfig.newActive(sector, now, ctx)
	local picked = SectorConfig.PickerEnabled ~= true
	return {
		sector = sector,
		picked = picked,
		name = SectorConfig.defaultName(sector) or SectorConfig.defaultName(SectorConfig.Default) or "My Startup",
		foundedAt = now,
		engaged = 0,
		passSeconds = {},
		building = 1,
		decor = {},
		objects = {},
		stored = {},
		told = {},
		rounds = {},
		sx = {},
	}
end

-- Returns the active company, and whether its sector is one this version doesn't know (kept, never changed)
local function readActive(ctx, raw)
	local value = raw.active
	if value == nil then
		return CompanyConfig.newActive(SectorConfig.Default, ctx.now, ctx), false
	end
	if typeof(value) ~= "table" then
		note(ctx, "a bad active, a new company starts")
		return CompanyConfig.newActive(SectorConfig.Default, ctx.now, ctx), false
	end
	local sector = value.sector
	if sector ~= nil and typeof(sector) ~= "string" then
		note(ctx, "a bad active.sector (" .. tostring(sector) .. "), a new company starts")
		return CompanyConfig.newActive(SectorConfig.Default, ctx.now, ctx), false
	end
	local fresh = CompanyConfig.newActive(sector or SectorConfig.Default, ctx.now, ctx)
	local where = "active"
	local active = {
		sector = fresh.sector,
		picked = readBoolean(ctx, where, value, "picked", fresh.picked),
		name = readString(ctx, where, value, "name", fresh.name),
		foundedAt = readNumber(ctx, where, value, "foundedAt", ctx.now, 0, nil, true),
		engaged = readNumber(ctx, where, value, "engaged", 0, 0),
		passSeconds = readMap(ctx, where, value, "passSeconds", isPass, validSeconds),
		building = readNumber(ctx, where, value, "building", 1, 1, MAX_BUILDING, true),
		decor = readMap(ctx, where, value, "decor", isFurniture, validCopies),
		objects = readObjects(ctx, where, value, "objects"),
		stored = readStored(ctx, where, value, "stored"),
		told = readMap(ctx, where, value, "told", isStage, validTrue),
		rounds = readRounds(ctx, where, value, "rounds"),
		sx = readWhole(ctx, where, value, "sx"),
	}
	copyUnknown(ctx, where, value, ACTIVE_KNOWN, active)
	return active, not SectorConfig.isKnown(active.sector)
end

-- A company is finished (the sector is done): the Pokedex entry, its stamp and its card. Used by the run check now,
-- and by the IPO itself later. card.ratio, owned and shares are 0 or empty when they aren't known.
local function completeCompany(section, ipoNumber, now, extra)
	local active = section.active
	local entry = section.sectors[active.sector]
	if typeof(entry) ~= "table" then
		entry = { state = "progress", stamp = 0, replays = 0, firstAt = 0, bestEngaged = 0 }
		section.sectors[active.sector] = entry
	end
	if entry.state == "done" then
		entry.replays += 1
	else
		entry.state = "done"
		entry.firstAt = now
	end
	entry.stamp = math.max(entry.stamp, 1) -- Bronze if there was no stamp yet
	entry.bestEngaged = math.max(entry.bestEngaged, active.engaged)
	entry.card = {
		name = active.name,
		ipoNumber = ipoNumber,
		at = now,
		engaged = active.engaged,
		ratio = extra and extra.ratio or 0,
		building = active.building,
		owned = extra and extra.owned or {},
		decor = deepCopy(active.decor),
		objects = deepCopy(active.objects),
		rounds = deepCopy(active.rounds),
		stake = CompanyConfig.stakeOf(active.rounds),
		shares = extra and extra.shares or 0,
		sx = deepCopy(active.sx),
	}
	-- Goals of the Hall of Fame: every sector of the goal enabled and done
	for goal, definition in pairs(SectorConfig.Goals) do
		if section.hall[goal] == nil then
			local reached = true
			for _, key in ipairs(definition.sectors) do
				local other = section.sectors[key]
				if not (SectorConfig.isEnabled(key) and typeof(other) == "table" and other.state == "done") then
					reached = false
				end
			end
			if reached then
				section.hall[goal] = now
			end
		end
	end
end
CompanyConfig.completeCompany = completeCompany

-- Starts the player's pokedex from a save. saved = the "pokedex" part of the save (nil for every save from before
-- this version, and for new players). ctx = { warn, who, ipoCount, now }. Never errors on a bad save.
-- Returns a state:
--   state.section  the data in the saved shape (unknown fields inline), changed by the actions
--   state.locked   true when `v` is newer than this code knows (or the sector is): kept opaque, nothing may change
--   state.raw      what a locked state writes back, as it was loaded
--   state.event    what the run check did: nil, "complete" (an older version ran an IPO) or "rebase" (the count went down)
-- Missing section: a new founding (run = the IPO count, Software, building 1; the picker is off, so picked = true).
-- Run check (docs/CUSTOMIZE_PROPOSAL.md 1.2): `run` is the IPO count the active company belongs to.
--   run < count: an older version ran an IPO and left this section frozen. The sector is done (Bronze if it had no
--     stamp) with a card, and a new company starts. Rounds stay as they were, on the card.
--   run > count: never an IPO. Only Studio's Debug IpoReset lowers the count (or a damaged ipo reads as 0). The run is
--     set to the count, the company stays, nothing is stamped, `studio` is set and a warning is written.
function CompanyConfig.load(saved, ctx)
	local count = ctx.ipoCount
	local state = { locked = false }
	if saved ~= nil and typeof(saved) ~= "table" then
		note(ctx, "the section isn't a table, a new company starts")
		saved = nil
	end
	if saved == nil then
		state.section = {
			v = CompanyConfig.Version,
			run = count,
			active = CompanyConfig.newActive(SectorConfig.Default, ctx.now, ctx),
			sectors = {},
			kept = {},
			hall = {},
			dust = 0,
		}
		return state
	end

	local version = saved.v
	if isWhole(version, 1) and version > CompanyConfig.Version then
		ctx.warn("Keeping " .. ctx.who .. "'s pokedex as it is: it is version " .. tostring(version) .. " and this version knows " .. CompanyConfig.Version)
		state.locked, state.raw = true, saved
		return state
	end
	if version ~= nil and not (isWhole(version, 1) and version <= CompanyConfig.Version) then
		note(ctx, "a bad v (" .. tostring(version) .. ")")
	end

	ctx.foreign = nil
	local section = { v = CompanyConfig.Version }
	section.run = readNumber(ctx, "pokedex", saved, "run", count, 0, nil, true)
	local active, unknownSector = readActive(ctx, saved)
	section.active = active
	section.sectors = readSectors(ctx, saved)
	section.kept = readMap(ctx, "pokedex", saved, "kept", isFurniture, validCopies)
	section.hall = readMap(ctx, "pokedex", saved, "hall", isGoal, validTime)
	local dust = saved.dust
	if dust == nil then
		section.dust = 0
	elseif isWhole(dust, -5000, 4999) then
		section.dust = dust
	else
		note(ctx, "a bad dust (" .. tostring(dust) .. "), it starts again at 0")
		section.dust = 0
	end
	if saved.studio ~= nil then
		section.studio = readBoolean(ctx, "pokedex", saved, "studio", false)
	end
	copyUnknown(ctx, "pokedex", saved, TOP_KNOWN, section)
	state.section = section

	if unknownSector then
		-- A sector from a newer version: the company is kept as it is and nothing may change it
		ctx.warn("Keeping " .. ctx.who .. "'s pokedex as it is: its sector " .. tostring(active.sector) .. " isn't known to this version")
		state.locked, state.raw = true, saved
		return state
	end
	if ctx.foreign then
		-- A shape this version can't carry back (for example a list of placed items with other keys): kept as it is
		ctx.warn("Keeping " .. ctx.who .. "'s pokedex as it is: its " .. ctx.foreign .. " (a shape this version doesn't know)")
		state.locked, state.raw = true, saved
		return state
	end

	if section.run < count then
		ctx.warn(string.format("%s's pokedex is from IPO %d but they have done %d: an older version ran an IPO, the company is completed", ctx.who, section.run, count))
		completeCompany(section, section.run + 1, ctx.now)
		section.active = CompanyConfig.newActive(active.sector, ctx.now, ctx)
		section.run = count
		state.event = "complete"
	elseif section.run > count then
		ctx.warn(string.format("%s's pokedex is from IPO %d but their IPO count is %d (an IPO reset in Studio, or a restored save): no stamp, the company stays", ctx.who, section.run, count))
		section.run = count
		section.studio = true
		state.event = "rebase"
	end
	return state
end

-- The section to write. A locked state writes back exactly what it loaded. Otherwise `studio` is set by a Studio
-- server (and then never cleared): a Studio save never reaches a live board.
function CompanyConfig.toSave(state, studio)
	if state.locked then
		return state.raw
	end
	local section = deepCopy(state.section)
	section.v = CompanyConfig.Version
	if studio then
		section.studio = true
	end
	return section
end

return CompanyConfig
