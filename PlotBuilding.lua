-- PlotBuilding: the five buildings around the garage rooms, one per funding stage (branch lobby-all).
-- Put this ModuleScript in ServerScriptService, next to PlotBuildingVisuals (the builder and the checks), ModelSlots
-- (ready-made models for the slots) and PlotArt (the rooms inside, unchanged). Data only.
-- docs/BUILDING_STAGES_PROPOSAL.md is the design; docs/MODEL_ASSETS_PLAN.md the model slots.
--
-- Buildings[i] is the building of IpoConfig.Stages[i] (same order): 1 Garage, 2 Small Office (Seed), 3 Big Office
-- (Series A), 4 Small Corporate (Series B), 5 Big Corporate (IPO-ready). A stage past the last shows the last one.
-- Looks only, like PlotArt: nothing here is saved, sent through a remote or read back. Nothing random, no odds text.
--
-- Every piece of a building is a SLOT placement: { id, slot, group, at, turn, box, parts, text }.
--   slot   the slot's name (Slots below): a model in ReplicatedStorage.BuildingModels.<key>.<slot> replaces `parts`
--   group  "Shell" (walls, roof, door, sign: fades when you are inside), "Interior" (furniture and the added floor),
--          "Outside" (small things in front of the facade)
--   at     { x, y, z }: the bottom-center of the slot's box, in the garage's frame (studs from the floor-top center:
--          +X right, +Z the front with the door, y 0 = the floor top, y -1 = the ground)
--   turn   0, 90, 180 or 270 degrees about +Y: the slot's front (+Z) turned; 90 faces +X (the right), 180 the back
--   box    { w, h, d }: width (x), height (y), depth (z) in the slot's own frame
--   parts  the Parts version, built when no model is used: part specs like PlotArt's, offsets from the box's
--          bottom-center in the slot's own frame. In a solid slot exactly one part has collide = true: the collider,
--          as wide and deep as the box, from its bottom. With a model only the collider is built, invisible, so the
--          walls stay closed whatever the model looks like.
--   text   optional { value, color, font, glow, x, y, z, w, h }: written on a thin plate by the builder, centered at
--          (x, y, z) of the slot (default: the box's front face), w x h big (default: the box's). value is one of
--          Texts; sign = true instead of a value for the garage sign, whose words the server sets.

local PlotBuilding = {}

PlotBuilding.Enabled = true -- false: no building at all (the rooms stand open, as before this branch)

-- The frame every building shares ---------------------------------------------------------------------------------
PlotBuilding.FRONT = 32 -- the front wall's outer face (the door side): the same line for every building
PlotBuilding.THICK = 1 -- wall thickness
PlotBuilding.CORNER = 2 -- corner posts are CORNER x CORNER
PlotBuilding.GROUND = -1 -- the Floor's bottom, where the Baseplate's top is: walls start here
PlotBuilding.DOOR_TOP = 11 -- every door opening goes from the ground to 11 above the floor top
PlotBuilding.Inside = { floorBelow = 3, apron = 3.5, margin = 1 } -- the fade's inside box (PlotBuildingVisuals.isInside)
PlotBuilding.Fade = { seconds = 0.4, levels = 20 }
-- The doorway lane: no solid part and no piece of any slot in it (docs/LOBBY_GARAGE_PROPOSAL.md section 3.4)
PlotBuilding.Lane = { half = 4.5, height = 9, from = 30, to = 35.5 }
-- The lot every building stays inside (82.6 x 86.6, 2.3 in front of the floor's front edge), and the band in front
-- of the facade where Outside pieces may stand (to z 38), never on the claim post's spot (PR L3)
PlotBuilding.Lot = { half = 41.3, front = 32.3, back = -54.3, outsideTo = 38, top = 64 }
PlotBuilding.ClaimSpot = { 5, 11, 33, 38 } -- x0, x1, z0, z1: the claim post and its lamp
PlotBuilding.Texts = { ["OFFICE"] = true, ["HQ"] = true, ["BUILD YOUR STARTUP"] = true }

-- Triangles a model may have, per kind of piece (docs/MODEL_ASSETS_PLAN.md section 1.2)
PlotBuilding.Caps = { panel = 200, window = 300, trim = 300, roof = 600, floor = 100, door = 1000, roofprop = 600, small = 500, big = 1200, plant = 800 }

-- The slots: kind (its triangle cap), fit ("uniform": one scale; "stretch": each side to the box), solid (has a collider)
PlotBuilding.Slots = {
	WallPanel = { kind = "panel", fit = "uniform", solid = true },
	WallPanelNarrow = { kind = "panel", fit = "uniform", solid = true },
	WallWindow = { kind = "window", fit = "uniform", solid = true },
	Corner = { kind = "panel", fit = "uniform", solid = true },
	Lintel = { kind = "trim", fit = "stretch", solid = true },
	UpperPanel = { kind = "panel", fit = "uniform", solid = true },
	UpperWindow = { kind = "window", fit = "uniform", solid = true },
	Roof = { kind = "roof", fit = "stretch", solid = true },
	FloorStrip = { kind = "floor", fit = "stretch", solid = true },
	Parapet = { kind = "trim", fit = "stretch" },
	SignBoard = { kind = "trim", fit = "uniform" },
	RoofBoard = { kind = "trim", fit = "uniform" },
	DoorDrum = { kind = "door", fit = "uniform" },
	Tarp = { kind = "roofprop", fit = "stretch" },
	StovePipe = { kind = "roofprop", fit = "uniform" },
	AcUnit = { kind = "roofprop", fit = "uniform" },
	OilDrum = { kind = "small", fit = "uniform" },
	TireStack = { kind = "small", fit = "uniform" },
	Shelf = { kind = "big", fit = "uniform" },
	Tire = { kind = "small", fit = "uniform" },
}

-- Palette (PlotArt's and building-pass's colors) -------------------------------------------------------------------
local C = {
	-- Garage: rust, tin, blue tarp
	rust = { 150, 86, 52 }, rustLight = { 178, 112, 70 }, rustDark = { 104, 58, 38 }, tin = { 140, 148, 150 }, tinDark = { 104, 110, 116 },
	steel = { 84, 86, 92 }, door = { 176, 184, 188 }, doorDark = { 150, 158, 164 }, woodDark = { 104, 74, 50 }, wood = { 170, 122, 78 },
	dustyGlass = { 196, 192, 160 }, tape = { 228, 206, 150 }, tarp = { 70, 130, 200 }, tire = { 38, 38, 42 }, drumRed = { 186, 64, 52 },
	concrete = { 170, 168, 160 }, board = { 214, 196, 150 }, ink = { 40, 32, 30 }, paint = { 230, 196, 80 }, paintBlue = { 70, 120, 190 },
}

-- Helpers --------------------------------------------------------------------------------------------------------
local function P(name, shape, size, offset, color, material, extra)
	local spec = extra or {}
	spec.name, spec.shape, spec.size, spec.offset, spec.color, spec.material = name, shape, size, offset, color, material
	return spec
end

-- A block from its center and its width, height and depth (offsets from the slot's bottom-center)
local function B(name, x, y, z, w, h, d, color, material, extra)
	return P(name, "Block", { w, h, d }, { x, y, z }, color, material, extra)
end

-- A cylinder standing up from y (its length is the height; rot stands it up, like PlotArt's)
local function U(name, x, y, z, diameter, height, color, material, extra)
	local spec = extra or {}
	spec.rot = { 0, 0, 90 }
	return P(name, "Cylinder", { height, diameter, diameter }, { x, y + height / 2, z }, color, material, spec)
end

-- A cylinder lying along x (a drum, a pipe)
local function L(name, x, y, z, length, diameter, color, material)
	return P(name, "Cylinder", { length, diameter, diameter }, { x, y, z }, color, material)
end

-- The collider of a solid slot: the whole box, solid
local function solidBox(name, box, color, material, extra)
	local spec = extra or {}
	spec.collide = true
	return B(name, 0, box[2] / 2, 0, box[1], box[2], box[3], color, material, spec)
end

-- One placement
local function S(id, slot, group, at, turn, box, parts, text)
	return { id = id, slot = slot, group = group, at = at, turn = turn, box = box, parts = parts, text = text }
end

-- The shell: four walls of panels between corner posts, a door opening in the front wall with a lintel over it.
-- b = the building (width, back, wallHeight, door), look = functions that give each piece's Parts version:
--   look.panel(i, w, h, side) / look.window(i, w, h, side) / look.corner(h) / look.lintel(w, h)
-- windows = { left = { panel numbers }, right = ..., back = ..., front = ... } (panels counted from the front,
-- from the left, from the left of the door outward). Panels are 8 wide, the last one of a run 4 when it must be.
local function shell(list, b, look, windows)
	local W, BACK, H = b.width, b.back, b.wallHeight
	local half, door = W / 2, b.door / 2
	local y = PlotBuilding.GROUND
	local wallMid = PlotBuilding.THICK / 2
	local function isWindow(side, i)
		for _, n in ipairs(windows[side] or {}) do
			if n == i then
				return true
			end
		end
		return false
	end
	-- a run of panels from a to b along one wall (a < b, in the wall's own direction), placed by place(center, w)
	local function run(side, a, b2, place)
		local i, pos = 0, a
		while pos < b2 - 1e-6 do
			i += 1
			local w = math.min(8, b2 - pos)
			local center = pos + w / 2
			local slot, parts
			if isWindow(side, i) and w == 8 then
				slot, parts = "WallWindow", look.window(i, w, H, side)
			else
				slot, parts = (w == 8 and "WallPanel" or "WallPanelNarrow"), look.panel(i, w, H, side)
			end
			place(side .. i, slot, center, w, parts)
			pos += w
		end
	end
	local C2 = PlotBuilding.CORNER
	-- Left wall (outside faces -X): panels from the front corner to the back corner, counted from the front
	run("left", 0, (PlotBuilding.FRONT - C2) - (BACK + C2), function(id, slot, offset, w, parts)
		table.insert(list, S("Wall" .. id, slot, "Shell", { -half + wallMid, y, PlotBuilding.FRONT - C2 - offset }, 270, { w, H, PlotBuilding.THICK }, parts))
	end)
	run("right", 0, (PlotBuilding.FRONT - C2) - (BACK + C2), function(id, slot, offset, w, parts)
		table.insert(list, S("Wall" .. id, slot, "Shell", { half - wallMid, y, PlotBuilding.FRONT - C2 - offset }, 90, { w, H, PlotBuilding.THICK }, parts))
	end)
	-- Back wall (outside faces -Z): from the left corner to the right corner
	run("back", 0, W - 2 * C2, function(id, slot, offset, w, parts)
		table.insert(list, S("Wall" .. id, slot, "Shell", { -half + C2 + offset, y, BACK + wallMid }, 180, { w, H, PlotBuilding.THICK }, parts))
	end)
	-- Front wall (outside faces +Z): left of the door going left, right of the door going right
	run("frontLeft", 0, half - C2 - door, function(id, slot, offset, w, parts)
		table.insert(list, S("Wall" .. id, slot, "Shell", { -door - offset, y, PlotBuilding.FRONT - wallMid }, 0, { w, H, PlotBuilding.THICK }, parts))
	end)
	run("frontRight", 0, half - C2 - door, function(id, slot, offset, w, parts)
		table.insert(list, S("Wall" .. id, slot, "Shell", { door + offset, y, PlotBuilding.FRONT - wallMid }, 0, { w, H, PlotBuilding.THICK }, parts))
	end)
	-- Corner posts
	for _, corner in ipairs({ { -1, 1, "CornerFL", 0 }, { 1, 1, "CornerFR", 0 }, { -1, -1, "CornerBL", 180 }, { 1, -1, "CornerBR", 180 } }) do
		local z = corner[2] > 0 and PlotBuilding.FRONT - C2 / 2 or BACK + C2 / 2
		table.insert(list, S(corner[3], "Corner", "Shell", { corner[1] * (half - C2 / 2), y, z }, corner[4], { C2, H, C2 }, look.corner(H)))
	end
	-- The lintel over the door, from the top of the opening to the top of the wall
	local lintelH = (y + H) - PlotBuilding.DOOR_TOP
	table.insert(list, S("Lintel", "Lintel", "Shell", { 0, PlotBuilding.DOOR_TOP, PlotBuilding.FRONT - wallMid }, 0, { b.door, lintelH, PlotBuilding.THICK }, look.lintel(b.door, lintelH)))
end

local function join(...)
	local out = {}
	for _, list in ipairs({ ... }) do
		for _, item in ipairs(list) do
			table.insert(out, item)
		end
	end
	return out
end

-- 1. Garage ----------------------------------------------------------------------------------------------------------
-- Corrugated rust sheets between dark posts, a flat tin roof with ribs, a blue tarp, a stove pipe and an old AC box, a
-- double roll-up door pulled up, a taped dusty window on each side, the crooked BUILD YOUR STARTUP board on the roof.
-- Inside: the stage 1 room as it is, with a dirt margin around the slab (no floor added): an old shelf, two oil
-- drums and a stack of tires along the back.
local function garage()
	local b = {
		key = "Garage", name = "Garage", stage = "Garage",
		width = 68, back = -36, wallHeight = 16, door = 16, ceiling = 15,
		budget = { parts = 80, triangles = 10000, gui = 3 },
	}
	local sheets = { C.rust, C.rustLight, C.rustDark, C.rust, C.rustLight }
	local look = {
		panel = function(i, w, h, side)
			local shade = sheets[(i + #side) % #sheets + 1]
			return { solidBox("Sheet", { w, h, PlotBuilding.THICK }, shade, "CorrodedMetal") }
		end,
		window = function(i, w, h, side)
			return {
				solidBox("Sheet", { w, h, PlotBuilding.THICK }, C.rust, "CorrodedMetal"),
				B("DustyGlass", 0, 8, 0.55, 4, 3, 0.2, C.dustyGlass, "Glass", { transparency = 0.25 }),
				B("Tape", 0, 8, 0.7, 4.4, 0.4, 0.1, C.tape, "SmoothPlastic", { rot = { 0, 0, 35 } }),
			}
		end,
		corner = function(h)
			return { solidBox("Post", { PlotBuilding.CORNER, h, PlotBuilding.CORNER }, C.steel, "Metal") }
		end,
		lintel = function(w, h)
			return { solidBox("Beam", { w, h, PlotBuilding.THICK }, C.rustDark, "CorrodedMetal") }
		end,
	}
	local slots = {}
	shell(slots, b, look, { left = { 4 }, right = { 5 } })
	local top = PlotBuilding.GROUND + b.wallHeight -- 15: the top of the walls, the underside of the roof
	local depth = PlotBuilding.FRONT - b.back
	local roofBox = { b.width, 1.5, depth }
	local roofParts = { solidBox("TinRoof", { b.width, 1, depth }, C.tin, "Metal") }
	for i, x in ipairs({ -24, -8, 8, 24 }) do
		table.insert(roofParts, B("Rib" .. i, x, 1.25, 0, 1, 0.5, depth - 2, C.tinDark, "Metal"))
	end
	-- the roof's solid part is the slab (1 high); the ribs sit on it, inside the box
	roofParts[1].offset = { 0, 0.5, 0 }
	roofParts[1].size = { b.width, 1, depth }
	table.insert(slots, S("Roof", "Roof", "Shell", { 0, top, (PlotBuilding.FRONT + b.back) / 2 }, 0, roofBox, roofParts))
	local roofTop = top + 1
	table.insert(slots, S("Tarp", "Tarp", "Shell", { -14, roofTop + 0.5, -8 }, 0, { 16, 0.4, 12 }, {
		B("TarpSheet", 0, 0.2, 0, 16, 0.4, 12, C.tarp, "Fabric"),
	}))
	table.insert(slots, S("StovePipe", "StovePipe", "Shell", { 16, roofTop, -20 }, 0, { 4, 8, 4 }, {
		U("Pipe", 0, 0, 0, 1.6, 7, C.steel, "Metal"),
		B("PipeCap", 0, 7.5, 0, 2.4, 1, 2.4, C.tinDark, "Metal"),
	}))
	table.insert(slots, S("AcUnit", "AcUnit", "Shell", { 16, roofTop, 8 }, 0, { 4, 4, 4 }, {
		B("AcBox", 0, 1.5, 0, 4, 3, 4, C.door, "Metal"),
		B("AcGrille", 0, 1.5, 2.05, 3, 2, 0.1, C.doorDark, "DiamondPlate"),
	}))
	table.insert(slots, S("RoofBoard", "RoofBoard", "Shell", { -2, roofTop, 22 }, 0, { 20, 8, 4 }, {
		B("BoardFace", 0, 5.5, 1.5, 20, 5, 0.4, C.board, "WoodPlanks"),
		B("BoardPostL", -7, 1.75, 1, 0.6, 3.5, 0.6, C.woodDark, "Wood"),
		B("BoardPostR", 7, 1.75, 1, 0.6, 3.5, 0.6, C.woodDark, "Wood"),
	}, { value = "BUILD YOUR STARTUP", color = C.ink, font = "PermanentMarker", y = 5.5, z = 1.7, w = 19, h = 4.4 }))
	-- The roll-up door pulled up: its drum just inside the lintel, two slats hanging under it (above the lane)
	table.insert(slots, S("DoorDrum", "DoorDrum", "Shell", { 0, 10, PlotBuilding.FRONT - PlotBuilding.THICK - 1 }, 0, { 16, 4, 2 }, {
		L("Drum", 0, 2.6, 0, 16, 2.4, C.door, "Metal"),
		B("SlatA", 0, 0.75, 0.4, 15.6, 0.6, 0.2, C.doorDark, "Metal"),
		B("SlatB", 0, 0.25, 0.4, 15.6, 0.5, 0.2, C.door, "Metal"),
	}))
	-- The garage sign over the door (the owner's name, FREE...): the server writes its words
	table.insert(slots, S("GarageSign", "SignBoard", "Shell", { 0, PlotBuilding.DOOR_TOP, PlotBuilding.FRONT + 0.1 }, 0, { 16, 4, 0.2 }, {
		B("SignFace", 0, 2, 0, 16, 4, 0.2, C.board, "WoodPlanks"),
	}, { sign = true, color = C.ink, font = "PermanentMarker" }))
	-- Inside, along the back, behind the room (the dirt margin: the ground is y -1)
	local g = PlotBuilding.GROUND
	local backBand = b.back + PlotBuilding.THICK + 2.5 -- z -32.5: the middle of a 4-deep piece against the back wall
	table.insert(slots, S("Shelf", "Shelf", "Interior", { -20, g, backBand }, 0, { 8, 8, 4 }, {
		B("ShelfFrame", 0, 4, -1, 8, 8, 2, C.steel, "Metal"),
		B("CanRow", -1.5, 4.6, 0.4, 4, 1.2, 0.8, C.paint, "SmoothPlastic"),
		B("CanRowB", 1.5, 1.6, 0.4, 4, 1.2, 0.8, C.paintBlue, "SmoothPlastic"),
	}))
	table.insert(slots, S("OilDrumA", "OilDrum", "Interior", { 14, g, backBand }, 0, { 4, 4, 4 }, {
		U("Drum", 0, 0, 0, 3, 4, C.drumRed, "Metal"),
	}))
	table.insert(slots, S("OilDrumB", "OilDrum", "Interior", { 19, g, backBand }, 0, { 4, 4, 4 }, {
		U("Drum", 0, 0, 0, 3, 4, C.drumRed, "Metal"),
	}))
	table.insert(slots, S("TireStack", "TireStack", "Interior", { 25, g, backBand }, 0, { 4, 4, 4 }, {
		U("TireLow", 0, 0, 0, 3.6, 1.3, C.tire, "Fabric"),
		U("TireMid", 0, 1.3, 0, 3.6, 1.3, C.tire, "Fabric"),
		U("TireTop", 0, 2.6, 0, 3.6, 1.3, C.tire, "Fabric"),
	}))
	-- Outside: a tire by the facade
	table.insert(slots, S("Tire", "Tire", "Outside", { -14, g, PlotBuilding.FRONT + 3 }, 0, { 4, 4, 4 }, {
		P("TireRing", "Cylinder", { 1.2, 3.4, 3.4 }, { 0, 1.7, 0 }, C.tire, "Fabric"),
	}))
	b.slots = slots
	return b
end

PlotBuilding.Buildings = {
	garage(),
}

-- Every slot's box, its kind and its fit come from here; the tests and the Debug report read it
function PlotBuilding.slotInfo(name)
	return PlotBuilding.Slots[name]
end

return PlotBuilding
