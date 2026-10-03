-- PlotBuilding: the building around each stage room (branch building-pass).
-- Put this ModuleScript in ServerScriptService, next to PlotBuildingVisuals (which builds it) and
-- PlotArt (the rooms inside). Data only: built-in Parts and materials, no assets, nothing random.
--
-- Stages[i] is the building around PlotArt.Stages[i] (same order, same IpoConfig funding stage).
-- Looks only, like PlotArt: nothing here is saved, sent through a remote or read back, and every
-- part is anchored with CanCollide, CanTouch and CanQuery off, so the building never changes how
-- anything plays. The client script BuildingClient fades the `fade` list when the local player is
-- inside; the `static` list (ground pieces) stays.
--
-- A part is written like PlotArt's: a table with name, shape, size { x, y, z }, offset { x, y, z },
-- color { r, g, b }, material and, when needed, rot = { x, y, z } degrees, transparency, and
-- text = { value, font, color, face, area, glow } (value: OFFICE, HQ or BUILD YOUR STARTUP only).
-- Offsets are studs from the plot's floor-top center (+X right, +Z the front with the door, -Z the back).
-- The building stands OUTSIDE the old open shells (their parts end at 30.15), so no part touches a
-- room part: the walls start at 30.2.

local PlotBuilding = {}

-- The envelope: the numbers every stage shares (PlotBuildingVisuals and the tests read them) ------
PlotBuilding.Envelope = {
	inner = 30.2, -- inner face of the walls, from the plot center, on x and z
	thick = 0.8, -- wall thickness (outer face at 31.0)
	ground = -1, -- the Floor's bottom, where the Baseplate's top is: walls start here
	roofBottom = 14, -- underside of the roof (the inside check's ceiling)
	roofThick = 0.9,
	roofHalf = 32.5, -- the roof slab is 65 x 65 (1.5 studs of eave)
	doorHalf = 4.5, -- the door opening is 9 wide, centered on the walking lane
	doorHeight = 9, -- and 9 high; nothing hangs lower than clearHeight inside it
	clearHeight = 5.5,
}

-- What counts as "inside" for the roof fade (see PlotBuildingVisuals.isInside) ---------------------
PlotBuilding.Inside = {
	floorBelow = 3, -- studs below the floor top still count (a character is about 3 above its feet)
	doorDepth = 3.5, -- the apron in front of the door that counts as inside
	margin = 1, -- once inside, the box is this much bigger (no flicker on a wall line)
}

PlotBuilding.Fade = {
	seconds = 0.4, -- a full fade, out or in
	levels = 20, -- Transparency is written in steps of 1/levels (nothing is written while it holds still)
}

-- Budgets (PlotBuildingVisuals.check enforces them; the room's own 260 is not touched) ---------------
PlotBuilding.Budget = { parts = 64, static = 12, gui = 2 }

-- The only text a building may show (same rule as the rooms: no odds text, D9)
PlotBuilding.Texts = { ["OFFICE"] = true, ["HQ"] = true, ["BUILD YOUR STARTUP"] = true }

-- Palette ------------------------------------------------------------------------------------------
local C = {
	-- Garage: rust, tin, blue tarp
	rust = { 150, 86, 52 }, rustLight = { 178, 112, 70 }, rustDark = { 104, 58, 38 }, tin = { 140, 148, 150 }, tinDark = { 104, 110, 116 },
	steel = { 84, 86, 92 }, door = { 176, 184, 188 }, doorDark = { 150, 158, 164 }, woodDark = { 104, 74, 50 }, wood = { 170, 122, 78 },
	dustyGlass = { 196, 192, 160 }, tape = { 228, 206, 150 }, tarp = { 70, 130, 200 }, tire = { 38, 38, 42 }, weed = { 104, 168, 72 },
	concrete = { 170, 168, 160 }, board = { 214, 196, 150 }, ink = { 40, 32, 30 },
	-- Seed: mint, dark teal, coral
	mint = { 170, 226, 204 }, mintDark = { 46, 110, 100 }, mintLight = { 214, 242, 230 }, coral = { 232, 128, 102 }, glassTint = { 126, 172, 190 },
	cream = { 246, 238, 214 }, pot = { 200, 112, 74 }, leaf = { 86, 168, 86 }, white = { 246, 246, 242 }, silver = { 200, 204, 210 },
	-- Series A: brick, black steel, amber
	brick = { 172, 94, 76 }, brickLight = { 190, 112, 90 }, steelBlack = { 40, 44, 54 }, amber = { 246, 154, 52 }, bayDark = { 44, 52, 66 },
	shutter = { 196, 202, 206 }, grayLight = { 170, 176, 186 }, skyGlass = { 170, 210, 232 },
	-- Series B: white office, navy, cobalt
	officeWhite = { 240, 242, 244 }, navy = { 34, 42, 62 }, cobalt = { 52, 120, 230 }, officeGlass = { 150, 196, 220 }, benchWood = { 214, 184, 140 },
	-- IPO-ready: polished white, graphite, gold, neon blue
	hqWhite = { 246, 247, 248 }, graphite = { 38, 40, 48 }, gold = { 255, 196, 60 }, neonBlue = { 0, 170, 255 }, flagRed = { 214, 82, 70 },
}

-- Helpers ------------------------------------------------------------------------------------------
local E = PlotBuilding.Envelope
local IN, T = E.inner, E.thick
local OUT = IN + T -- 31.0, the outer face
local MID = IN + T / 2 -- 30.6, the wall's center line
local G, TOP = E.ground, E.roofBottom
local H = TOP - G -- the walls' height, from the ground to the underside of the roof
local CY = (TOP + G) / 2
local DH = E.doorHalf
local ROOF_TOP = TOP + E.roofThick -- 14.9
local ROOF_HALF = E.roofHalf

local function P(name, shape, size, offset, color, material, extra)
	local spec = extra or {}
	spec.name, spec.shape, spec.size, spec.offset, spec.color, spec.material = name, shape, size, offset, color, material
	return spec
end

-- A block from its center and its width, height and depth
local function B(name, x, y, z, w, h, d, color, material, extra)
	return P(name, "Block", { w, h, d }, { x, y, z }, color, material, extra)
end

-- A cylinder standing up from y (its length is the height; rot stands it up)
local function U(name, x, y, z, diameter, height, color, material)
	return P(name, "Cylinder", { height, diameter, diameter }, { x, y + height / 2, z }, color, material, { rot = { 0, 0, 90 } })
end

local function O(name, x, y, z, diameter, color, material)
	return P(name, "Ball", { diameter, diameter, diameter }, { x, y, z }, color, material)
end

local function join(...)
	local out = {}
	for _, list in ipairs({ ... }) do
		for _, spec in ipairs(list) do
			table.insert(out, spec)
		end
	end
	return out
end

-- The shell: tiling without overlap ---------------------------------------------------------------
-- The side walls run the whole depth (z -31 to 31). The back wall and the front wall fit between
-- them (x -30.2 to 30.2), and the front wall leaves the door opening (x -4.5 to 4.5) with a lintel
-- over it. Every wall rests on the ground. A list of colors cuts a wall into that many panels.

local function sideWalls(colors, material)
	local out, n = {}, #colors
	local len = 2 * OUT / n
	for i = 1, n do
		local z = -OUT + len * (i - 0.5)
		table.insert(out, B("SideL" .. i, -MID, CY, z, T, H, len, colors[i], material))
		table.insert(out, B("SideR" .. i, MID, CY, z, T, H, len, colors[(i % n) + 1], material))
	end
	return out
end

local function backWalls(colors, material)
	local out, n = {}, #colors
	local len = 2 * IN / n
	for i = 1, n do
		table.insert(out, B("Back" .. i, -IN + len * (i - 0.5), CY, -MID, len, H, T, colors[i], material))
	end
	return out
end

-- Front: left and right of the door, `n` panels each, and the lintel over the opening
local function frontWalls(left, right, material, lintel)
	local out = {}
	local len = (IN - DH) / #left
	for i = 1, #left do
		table.insert(out, B("FrontL" .. i, -DH - len * (i - 0.5), CY, MID, len, H, T, left[i], material))
	end
	len = (IN - DH) / #right
	for i = 1, #right do
		table.insert(out, B("FrontR" .. i, DH + len * (i - 0.5), CY, MID, len, H, T, right[i], material))
	end
	local top = E.doorHeight
	table.insert(out, B("Lintel", 0, (top + TOP) / 2, MID, 2 * DH, TOP - top, T, lintel[1], lintel[2] or material))
	return out
end

-- The roof slab and the parapet around its edge (4 strips, tiled: sides full depth, front and back between)
local function roofAndParapet(roof, roofMaterial, parapet, parapetMaterial, height)
	local out = { B("Roof", 0, TOP + E.roofThick / 2, 0, 2 * ROOF_HALF, E.roofThick, 2 * ROOF_HALF, roof, roofMaterial) }
	local w = 0.8
	local y = ROOF_TOP + height / 2
	local between = 2 * (ROOF_HALF - w)
	table.insert(out, B("ParapetL", -(ROOF_HALF - w / 2), y, 0, w, height, 2 * ROOF_HALF, parapet, parapetMaterial))
	table.insert(out, B("ParapetR", ROOF_HALF - w / 2, y, 0, w, height, 2 * ROOF_HALF, parapet, parapetMaterial))
	table.insert(out, B("ParapetBack", 0, y, -(ROOF_HALF - w / 2), between, height, w, parapet, parapetMaterial))
	table.insert(out, B("ParapetFront", 0, y, ROOF_HALF - w / 2, between, height, w, parapet, parapetMaterial))
	return out
end

-- A window on the front's outer face: a frame, then the glass in front of it (so no two faces share a plane).
-- Sits at x, with its middle at y. w and h are the glass.
local function frontWindow(name, x, y, w, h, frame, glass, tint)
	return {
		B(name .. "Frame", x, y, OUT + 0.15, w + 0.8, h + 0.8, 0.3, frame, "Metal"),
		B(name .. "Glass", x, y, OUT + 0.4, w, h, 0.2, glass, "Glass", { transparency = tint or 0.35 }),
	}
end

-- The same on a side wall (side = -1 left, 1 right), z is its middle
local function sideWindow(name, side, z, y, w, h, frame, glass, tint)
	return {
		B(name .. "Frame", side * (OUT + 0.15), y, z, 0.3, h + 0.8, w + 0.8, frame, "Metal"),
		B(name .. "Glass", side * (OUT + 0.4), y, z, 0.2, h, w, glass, "Glass", { transparency = tint or 0.35 }),
	}
end

-- A sign on the front over the door: a rim, then the board with the text in front of it
local function doorSign(text, y, w, h, rim, board, ink, font, glow)
	return {
		B("SignRim", 0, y, OUT + 0.1, w + 0.6, h + 0.6, 0.2, rim, "Metal"),
		B("SignBoard", 0, y, OUT + 0.35, w, h, 0.3, board, "SmoothPlastic",
			{ text = { value = text, font = font, color = ink, glow = glow, area = { 0.05, 0.08, 0.9, 0.84 } } }),
	}
end

-- A pot with a round bush, standing on the ground
local function planter(name, x, z, potColor, leafColor, size)
	return {
		U(name .. "Pot", x, G, z, 2 * size, 1.6, potColor, "SmoothPlastic"),
		O(name .. "Leaves", x, G + 1.6 + size * 0.7, z, 2.6 * size, leafColor, "Fabric"),
	}
end

-- A flat slab on the ground (a path or a mat)
local function ground(name, x, z, w, d, color, material, lift)
	return B(name, x, G + 0.05 + (lift or 0), z, w, 0.1, d, color, material)
end

-- Stage 1: the Garage ------------------------------------------------------------------------------
-- Rusty dented sheets, the roll-up door pulled up, one taped window, a repair tarp, a stove pipe,
-- an old AC box and a hand-painted board on the roof.

local garage = { key = "Garage" }

garage.fade = join(
	sideWalls({ C.rust, C.tin, C.rustLight }, "CorrodedMetal"),
	backWalls({ C.rust, C.rustLight, C.tin }, "CorrodedMetal"),
	frontWalls({ C.tin, C.rust }, { C.rustLight, C.tin }, "CorrodedMetal", { C.rustDark, "Metal" }),
	roofAndParapet(C.rustDark, "CorrodedMetal", C.steel, "Metal", 0.6),
	{
		-- Ribs on the front sheets
		B("FrontRibL1", -24, 6, OUT + 0.125, 0.3, 13, 0.25, C.rustDark, "CorrodedMetal"),
		B("FrontRibL2", -10, 6, OUT + 0.125, 0.3, 13, 0.25, C.rustDark, "CorrodedMetal"),
		B("FrontRibR1", 10, 6, OUT + 0.125, 0.3, 13, 0.25, C.rustDark, "CorrodedMetal"),
		B("FrontRibR2", 24, 6, OUT + 0.125, 0.3, 13, 0.25, C.rustDark, "CorrodedMetal"),
		-- The roll-up door, pulled up and stuck: drum and two slats hang from the lintel, rails on both sides
		P("DoorDrum", "Cylinder", { 2 * DH + 0.4, 1.3, 1.3 }, { 0, 8.35, OUT + 0.7 }, C.tinDark, "Metal"),
		B("DoorSlat1", 0, 7.05, OUT + 0.7, 2 * DH, 1.3, 0.4, C.door, "Metal"),
		B("DoorBottomBar", 0, 6.2, OUT + 0.7, 2 * DH + 0.2, 0.4, 0.6, C.steel, "Metal"),
		B("DoorRailL", -(DH + 0.35), 3.8, OUT + 0.125, 0.5, 9.6, 0.25, C.steel, "Metal"),
		B("DoorRailR", DH + 0.35, 3.8, OUT + 0.125, 0.5, 9.6, 0.25, C.steel, "Metal"),
	},
	-- One small window, taped where it cracked (left of the door)
	frontWindow("Window", -17, 6, 3.6, 2.8, C.woodDark, C.dustyGlass, 0.15),
	{
		B("WindowTape1", -17, 6, OUT + 0.53, 4.6, 0.4, 0.06, C.tape, "SmoothPlastic", { rot = { 0, 0, 32 } }),
		B("WindowTape2", -17, 6, OUT + 0.55, 4.6, 0.4, 0.06, C.tape, "SmoothPlastic", { rot = { 0, 0, -32 } }),
		-- The roof: ribs, a tarp, a stove pipe, an old AC box
		B("RoofRib1", -27, ROOF_TOP + 0.175, 0, 0.6, 0.35, 62, C.rustLight, "CorrodedMetal"),
		B("RoofRib2", -21, ROOF_TOP + 0.175, 0, 0.6, 0.35, 62, C.rustLight, "CorrodedMetal"),
		B("RoofRib3", -15, ROOF_TOP + 0.175, 0, 0.6, 0.35, 62, C.rustLight, "CorrodedMetal"),
		B("RoofRib4", -9, ROOF_TOP + 0.175, 0, 0.6, 0.35, 62, C.rustLight, "CorrodedMetal"),
		B("RoofRib5", 15, ROOF_TOP + 0.175, 0, 0.6, 0.35, 62, C.rustLight, "CorrodedMetal"),
		B("RoofRib6", 21, ROOF_TOP + 0.175, 0, 0.6, 0.35, 62, C.rustLight, "CorrodedMetal"),
		B("RoofRib7", 27, ROOF_TOP + 0.175, 0, 0.6, 0.35, 62, C.rustLight, "CorrodedMetal"),
		B("RoofTarp", 5.5, ROOF_TOP + 0.075, -8, 11, 0.15, 12, C.tarp, "Fabric"),
		U("StovePipe", -20, ROOF_TOP, -14, 1.6, 5, C.tinDark, "Metal"),
		U("StovePipeCap", -20, ROOF_TOP + 5, -14, 2.4, 0.4, C.steel, "Metal"),
		B("AcBox", 18, ROOF_TOP + 1.5, 8, 5, 3, 4, C.door, "Metal"),
		P("AcFan", "Cylinder", { 0.2, 2.6, 2.6 }, { 18, ROOF_TOP + 3.1, 8 }, C.steel, "Metal", { rot = { 0, 0, 90 } }),
		-- The hand-painted board on the roof
		B("BoardPostL", -5.5, ROOF_TOP + 2, 25, 0.6, 4, 0.6, C.woodDark, "Wood"),
		B("BoardPostR", 5.5, ROOF_TOP + 2, 25, 0.6, 4, 0.6, C.woodDark, "Wood"),
		B("RoofBoard", 0, ROOF_TOP + 3.3, 25, 15, 3.2, 0.4, C.board, "Wood",
			{ text = { value = "BUILD YOUR STARTUP", font = "PermanentMarker", color = C.ink, area = { 0.04, 0.1, 0.92, 0.8 } } }),
	}
)

garage.static = {
	ground("Path", 0, 34, 9, 6, C.tinDark, "Concrete"),
	U("Tire", 9, G, 33.5, 3, 1, C.tire, "Plastic"),
	O("WeedTuft", -8, G + 0.7, 33, 1.4, C.weed, "Fabric"),
	B("Crate", -7.2, G + 0.9, 34.6, 1.8, 1.8, 1.8, C.wood, "Wood"),
}

-- Stage 2: Seed -----------------------------------------------------------------------------------
-- Fresh mint paint with a dark teal base and parapet, an OFFICE sign, a four-panel door standing open
-- under a coral awning, two windows with sills, a satellite dish and two vents.

local seed = { key = "Seed" }

seed.fade = join(
	sideWalls({ C.mint }, "SmoothPlastic"),
	backWalls({ C.mint }, "SmoothPlastic"),
	frontWalls({ C.mint }, { C.mint }, "SmoothPlastic", { C.mintLight }),
	roofAndParapet(C.mintLight, "SmoothPlastic", C.mintDark, "SmoothPlastic", 1.4),
	{
		-- Dark teal base band around the walls
		B("BaseBandL", -(OUT + 0.1), 0.2, 0, 0.2, 2.4, 62.4, C.mintDark, "SmoothPlastic"),
		B("BaseBandR", OUT + 0.1, 0.2, 0, 0.2, 2.4, 62.4, C.mintDark, "SmoothPlastic"),
		B("BaseBandBack", 0, 0.2, -(OUT + 0.1), 62, 2.4, 0.2, C.mintDark, "SmoothPlastic"),
		B("BaseBandFrontL", -(DH + 0.8 + OUT) / 2, 0.2, OUT + 0.1, OUT - DH - 0.8, 2.4, 0.2, C.mintDark, "SmoothPlastic"),
		B("BaseBandFrontR", (DH + 0.8 + OUT) / 2, 0.2, OUT + 0.1, OUT - DH - 0.8, 2.4, 0.2, C.mintDark, "SmoothPlastic"),
		-- The door: a frame on the outside, the leaf swung open, a coral awning
		B("DoorJambL", -(DH + 0.35), 3.5, OUT + 0.25, 0.7, 9, 0.5, C.mintDark, "SmoothPlastic"),
		B("DoorJambR", DH + 0.35, 3.5, OUT + 0.25, 0.7, 9, 0.5, C.mintDark, "SmoothPlastic"),
		B("DoorHeader", 0, 9.35, OUT + 0.25, 2 * DH + 1.4, 0.7, 0.5, C.mintDark, "SmoothPlastic"),
		B("DoorLeaf", DH + 0.9, 3.4, OUT + 0.5 + 2.2, 0.3, 8.8, 4.4, C.coral, "SmoothPlastic"),
		B("DoorLeafGlass", DH + 1.1, 4.4, OUT + 0.5 + 2.2, 0.1, 3, 2.4, C.glassTint, "Glass", { transparency = 0.3 }),
		B("Awning", 0, 9.9, OUT + 1.5, 11, 0.4, 3, C.coral, "SmoothPlastic"),
		B("AwningLip", 0, 9.7, OUT + 3.15, 11, 0.8, 0.3, C.cream, "SmoothPlastic"),
	},
	frontWindow("WindowL", -17, 6, 4.4, 3.4, C.mintDark, C.glassTint),
	frontWindow("WindowR", 17, 6, 4.4, 3.4, C.mintDark, C.glassTint),
	{
		B("SillL", -17, 3.65, OUT + 0.45, 5.8, 0.5, 0.9, C.cream, "SmoothPlastic"),
		B("SillR", 17, 3.65, OUT + 0.45, 5.8, 0.5, 0.9, C.cream, "SmoothPlastic"),
	},
	sideWindow("SideWindowL", -1, 0, 6, 4.4, 3.4, C.mintDark, C.glassTint),
	sideWindow("SideWindowR", 1, 0, 6, 4.4, 3.4, C.mintDark, C.glassTint),
	doorSign("OFFICE", 11.4, 8.2, 1.8, C.mintDark, C.cream, C.mintDark, "FredokaOne"),
	{
		-- The roof: a coral stripe, a satellite dish and two vents
		B("RoofStripe", 0, ROOF_TOP + 0.06, 8, 63, 0.12, 4, C.coral, "SmoothPlastic"),
		B("DishPole", -20, ROOF_TOP + 1.5, -14, 0.5, 3, 0.5, C.silver, "Metal"),
		P("DishDisc", "Cylinder", { 0.4, 4.4, 4.4 }, { -19.4, ROOF_TOP + 3.9, -14 }, C.white, "SmoothPlastic", { rot = { 0, 0, 55 } }),
		B("VentA", 20, ROOF_TOP + 1.25, -10, 3.2, 2.5, 3.2, C.mintDark, "SmoothPlastic"),
		U("VentACap", 20, ROOF_TOP + 2.5, -10, 2.4, 0.4, C.silver, "Metal"),
		B("VentB", 24, ROOF_TOP + 1, 10, 3, 2, 3, C.mintDark, "SmoothPlastic"),
	}
)

seed.static = join(
	{
		ground("Path", 0, 34.5, 9, 7, C.concrete, "Concrete"),
		ground("Mat", 0, 33, 4.4, 2.4, C.coral, "Fabric", 0.04),
	},
	planter("PlanterL", -8.5, 33.5, C.pot, C.leaf, 1),
	planter("PlanterR", 8.5, 33.5, C.pot, C.leaf, 1)
)

-- Stage 3: Series A ----------------------------------------------------------------------------------
-- Red brick with a black steel band and parapet, two closed roll-up bays beside a wide door with a sliding
-- panel pushed aside, two glass windows over the bays, skylights, vents and a brick stack on the roof.

local seriesA = { key = "SeriesA" }

seriesA.fade = join(
	sideWalls({ C.brick, C.brickLight, C.brick }, "Brick"),
	backWalls({ C.brick, C.brickLight, C.brick }, "Brick"),
	frontWalls({ C.brick, C.brickLight }, { C.brickLight, C.brick }, "Brick", { C.steelBlack, "Metal" }),
	roofAndParapet(C.steelBlack, "Metal", C.bayDark, "Metal", 1.8),
	{
		-- A black steel band under the roof line
		B("BandL", -(OUT + 0.1), 12.8, 0, 0.2, 0.8, 62.4, C.steelBlack, "Metal"),
		B("BandR", OUT + 0.1, 12.8, 0, 0.2, 0.8, 62.4, C.steelBlack, "Metal"),
		B("BandBack", 0, 12.8, -(OUT + 0.1), 62, 0.8, 0.2, C.steelBlack, "Metal"),
		B("BandFrontL", -(DH + OUT) / 2, 12.8, OUT + 0.1, OUT - DH, 0.8, 0.2, C.steelBlack, "Metal"),
		B("BandFrontR", (DH + OUT) / 2, 12.8, OUT + 0.1, OUT - DH, 0.8, 0.2, C.steelBlack, "Metal"),
		-- Two closed roll-up bays: a dark frame, the shutter in front of it, an amber stripe at the foot
		B("BayLFrame", -17, 2.8, OUT + 0.15, 10.4, 7.6, 0.3, C.bayDark, "Metal"),
		B("BayLShutter", -17, 2.8, OUT + 0.4, 9.6, 6.8, 0.2, C.shutter, "Metal"),
		B("BayLStripe", -17, -0.55, OUT + 0.55, 9.6, 0.5, 0.1, C.amber, "SmoothPlastic"),
		B("BayRFrame", 17, 2.8, OUT + 0.15, 10.4, 7.6, 0.3, C.bayDark, "Metal"),
		B("BayRShutter", 17, 2.8, OUT + 0.4, 9.6, 6.8, 0.2, C.shutter, "Metal"),
		B("BayRStripe", 17, -0.55, OUT + 0.55, 9.6, 0.5, 0.1, C.amber, "SmoothPlastic"),
		-- The wide door: steel jambs and header, one big glass panel slid aside
		B("DoorJambL", -(DH + 0.35), 3.5, OUT + 0.25, 0.7, 9, 0.5, C.steelBlack, "Metal"),
		B("DoorJambR", DH + 0.35, 3.5, OUT + 0.25, 0.7, 9, 0.5, C.steelBlack, "Metal"),
		B("DoorHeader", 0, 9.35, OUT + 0.25, 2 * DH + 1.4, 0.7, 0.5, C.steelBlack, "Metal"),
		B("DoorSlidingPanel", DH + 2.4, 3.5, OUT + 0.5, 3.4, 9, 0.2, C.skyGlass, "Glass", { transparency = 0.3 }),
	},
	frontWindow("WindowL", -17, 9.6, 4.4, 2.4, C.steelBlack, C.skyGlass),
	frontWindow("WindowR", 17, 9.6, 4.4, 2.4, C.steelBlack, C.skyGlass),
	doorSign("OFFICE", 11, 8.2, 1.8, C.steelBlack, C.shutter, C.steelBlack, "FredokaOne"),
	{
		-- The roof: two skylights, two vents, an amber stripe and a brick stack
		B("SkylightLFrame", -14, ROOF_TOP + 0.4, -6, 7.6, 0.8, 7.6, C.steelBlack, "Metal"),
		B("SkylightLGlass", -14, ROOF_TOP + 0.95, -6, 6, 0.3, 6, C.skyGlass, "Glass", { transparency = 0.3 }),
		B("SkylightRFrame", 14, ROOF_TOP + 0.4, -6, 7.6, 0.8, 7.6, C.steelBlack, "Metal"),
		B("SkylightRGlass", 14, ROOF_TOP + 0.95, -6, 6, 0.3, 6, C.skyGlass, "Glass", { transparency = 0.3 }),
		U("VentL", -24, ROOF_TOP, 12, 2.2, 2.5, C.grayLight, "Metal"),
		U("VentR", 24, ROOF_TOP, 12, 2.2, 2.5, C.grayLight, "Metal"),
		B("RoofStripe", 0, ROOF_TOP + 0.06, 24, 62, 0.12, 1.2, C.amber, "SmoothPlastic"),
		B("BrickStack", 22, ROOF_TOP + 3, -22, 2.6, 6, 2.6, C.brick, "Brick"),
		B("BrickStackCap", 22, ROOF_TOP + 6.2, -22, 3.2, 0.4, 3.2, C.steelBlack, "Metal"),
	}
)

seriesA.static = join(
	{
		ground("Path", 0, 34.5, 10, 7, C.concrete, "Concrete"),
		U("BollardL", -6.5, G, 33.5, 0.9, 2.4, C.amber, "SmoothPlastic"),
		U("BollardR", 6.5, G, 33.5, 0.9, 2.4, C.amber, "SmoothPlastic"),
	},
	planter("PlanterL", -12, 33.5, C.steelBlack, C.leaf, 1),
	planter("PlanterR", 12, 33.5, C.steelBlack, C.leaf, 1)
)

-- Stage 4: Series B ----------------------------------------------------------------------------------
-- White office panels with a ribbon of cobalt-tinted glass all round, navy mullions and two navy columns
-- either side of a glass entrance with a canopy, an OFFICE sign, a glass skylight strip and HVAC units.

local seriesB = { key = "SeriesB" }

seriesB.fade = join(
	sideWalls({ C.officeWhite }, "SmoothPlastic"),
	backWalls({ C.officeWhite }, "SmoothPlastic"),
	frontWalls({ C.officeWhite }, { C.officeWhite }, "SmoothPlastic", { C.navy }),
	roofAndParapet(C.officeWhite, "SmoothPlastic", C.cobalt, "SmoothPlastic", 1.4),
	{
		-- The glass ribbon on the three closed sides, and the front either side of the door
		B("GlassL", -(OUT + 0.1), 6, 0, 0.2, 5, 56, C.officeGlass, "Glass", { transparency = 0.35 }),
		B("GlassR", OUT + 0.1, 6, 0, 0.2, 5, 56, C.officeGlass, "Glass", { transparency = 0.35 }),
		B("GlassBack", 0, 6, -(OUT + 0.1), 56, 5, 0.2, C.officeGlass, "Glass", { transparency = 0.35 }),
		B("GlassFrontL", -17, 6, OUT + 0.1, 22, 5, 0.2, C.officeGlass, "Glass", { transparency = 0.35 }),
		B("GlassFrontR", 17, 6, OUT + 0.1, 22, 5, 0.2, C.officeGlass, "Glass", { transparency = 0.35 }),
		-- Navy mullions on the glass (they stand in front of it)
		B("MullionL1", -(OUT + 0.4), 6, -14, 0.4, 5.2, 0.4, C.navy, "Metal"),
		B("MullionL2", -(OUT + 0.4), 6, 14, 0.4, 5.2, 0.4, C.navy, "Metal"),
		B("MullionR1", OUT + 0.4, 6, -14, 0.4, 5.2, 0.4, C.navy, "Metal"),
		B("MullionR2", OUT + 0.4, 6, 14, 0.4, 5.2, 0.4, C.navy, "Metal"),
		B("MullionFrontL1", -23, 6, OUT + 0.4, 0.4, 5.2, 0.4, C.navy, "Metal"),
		B("MullionFrontL2", -11, 6, OUT + 0.4, 0.4, 5.2, 0.4, C.navy, "Metal"),
		B("MullionFrontR1", 11, 6, OUT + 0.4, 0.4, 5.2, 0.4, C.navy, "Metal"),
		B("MullionFrontR2", 23, 6, OUT + 0.4, 0.4, 5.2, 0.4, C.navy, "Metal"),
		-- The entrance: two navy columns, a cobalt header, a canopy on two thin posts
		B("ColumnL", -(DH + 1.2), 6.5, OUT + 0.9, 1.4, 15, 1.8, C.navy, "SmoothPlastic"),
		B("ColumnR", DH + 1.2, 6.5, OUT + 0.9, 1.4, 15, 1.8, C.navy, "SmoothPlastic"),
		B("DoorHeader", 0, 9.35, OUT + 0.25, 2 * DH, 0.7, 0.5, C.cobalt, "SmoothPlastic"),
		B("Canopy", 0, 8.9, OUT + 3, 13, 0.4, 4.4, C.cobalt, "Glass", { transparency = 0.2 }),
		U("CanopyPostL", -6, G, OUT + 4.6, 0.4, 9.7, C.navy, "Metal"),
		U("CanopyPostR", 6, G, OUT + 4.6, 0.4, 9.7, C.navy, "Metal"),
	},
	doorSign("OFFICE", 11.4, 8.2, 1.8, C.navy, C.officeWhite, C.cobalt, "FredokaOne"),
	{
		-- The roof: a glass skylight strip, two HVAC units with fans, a mast
		B("SkylightFrame", 0, ROOF_TOP + 0.4, -10, 32, 0.8, 7, C.navy, "Metal"),
		B("SkylightGlass", 0, ROOF_TOP + 0.95, -10, 30, 0.3, 5.4, C.officeGlass, "Glass", { transparency = 0.3 }),
		B("HvacL", -22, ROOF_TOP + 1.5, 8, 6, 3, 4, C.silver, "Metal"),
		P("HvacLFan", "Cylinder", { 0.2, 2.8, 2.8 }, { -22, ROOF_TOP + 3.1, 8 }, C.navy, "Metal", { rot = { 0, 0, 90 } }),
		B("HvacR", 22, ROOF_TOP + 1.5, 8, 6, 3, 4, C.silver, "Metal"),
		P("HvacRFan", "Cylinder", { 0.2, 2.8, 2.8 }, { 22, ROOF_TOP + 3.1, 8 }, C.navy, "Metal", { rot = { 0, 0, 90 } }),
		U("Mast", 24, ROOF_TOP, -24, 0.4, 7, C.navy, "Metal"),
		O("MastTip", 24, ROOF_TOP + 7.2, -24, 0.7, C.cobalt, "SmoothPlastic"),
	}
)

seriesB.static = join(
	{
		ground("Path", 0, 35, 12, 8, C.concrete, "Concrete"),
		B("BenchSeat", 14, G + 1.2, 33.5, 5, 0.4, 1.4, C.benchWood, "Wood"),
		B("BenchLegL", 12, G + 0.5, 33.5, 0.4, 1, 1.2, C.navy, "Metal"),
		B("BenchLegR", 16, G + 0.5, 33.5, 0.4, 1, 1.2, C.navy, "Metal"),
	},
	planter("PlanterL", -12, 33.5, C.navy, C.leaf, 1.1),
	planter("PlanterR", 8.5, 33.5, C.navy, C.leaf, 1.1)
)

-- Stage 5: IPO-ready --------------------------------------------------------------------------------
-- The headquarters: polished white with graphite columns, big glass curtain-wall panels, a gold band and
-- gold-trimmed parapet, a lobby with a deep canopy and a neon-rimmed HQ sign, a glass dome, an antenna
-- and a helipad on the roof.

local ipoReady = { key = "IpoReady" }

ipoReady.fade = join(
	sideWalls({ C.hqWhite }, "SmoothPlastic"),
	backWalls({ C.hqWhite }, "SmoothPlastic"),
	frontWalls({ C.hqWhite }, { C.hqWhite }, "SmoothPlastic", { C.graphite }),
	roofAndParapet(C.hqWhite, "SmoothPlastic", C.gold, "Metal", 1),
	{
		-- Curtain-wall glass: two big panels per side, one each side of the door, one at the back
		B("GlassL1", -(OUT + 0.1), 5.5, -15, 0.2, 11, 24, C.skyGlass, "Glass", { transparency = 0.3 }),
		B("GlassL2", -(OUT + 0.1), 5.5, 15, 0.2, 11, 24, C.skyGlass, "Glass", { transparency = 0.3 }),
		B("GlassR1", OUT + 0.1, 5.5, -15, 0.2, 11, 24, C.skyGlass, "Glass", { transparency = 0.3 }),
		B("GlassR2", OUT + 0.1, 5.5, 15, 0.2, 11, 24, C.skyGlass, "Glass", { transparency = 0.3 }),
		B("GlassFrontL", -17, 5.5, OUT + 0.1, 20, 11, 0.2, C.skyGlass, "Glass", { transparency = 0.3 }),
		B("GlassFrontR", 17, 5.5, OUT + 0.1, 20, 11, 0.2, C.skyGlass, "Glass", { transparency = 0.3 }),
		B("GlassBack", 0, 5.5, -(OUT + 0.1), 50, 11, 0.2, C.skyGlass, "Glass", { transparency = 0.3 }),
		-- Graphite columns in front of the glass: four on the front, two each side
		B("ColumnFront1", -27.5, 6.5, OUT + 0.9, 1.6, 15, 1.8, C.graphite, "SmoothPlastic"),
		B("ColumnFront2", -DH - 1.2, 6.5, OUT + 0.9, 1.6, 15, 1.8, C.graphite, "SmoothPlastic"),
		B("ColumnFront3", DH + 1.2, 6.5, OUT + 0.9, 1.6, 15, 1.8, C.graphite, "SmoothPlastic"),
		B("ColumnFront4", 27.5, 6.5, OUT + 0.9, 1.6, 15, 1.8, C.graphite, "SmoothPlastic"),
		B("ColumnSideL1", -(OUT + 0.9), 6.5, -3, 1.8, 15, 1.6, C.graphite, "SmoothPlastic"),
		B("ColumnSideL2", -(OUT + 0.9), 6.5, 3, 1.8, 15, 1.6, C.graphite, "SmoothPlastic"),
		B("ColumnSideR1", OUT + 0.9, 6.5, -3, 1.8, 15, 1.6, C.graphite, "SmoothPlastic"),
		B("ColumnSideR2", OUT + 0.9, 6.5, 3, 1.8, 15, 1.6, C.graphite, "SmoothPlastic"),
		-- A gold band under the parapet
		B("BandL", -(OUT + 0.25), 13.2, 0, 0.5, 0.8, 62.4, C.gold, "Metal"),
		B("BandR", OUT + 0.25, 13.2, 0, 0.5, 0.8, 62.4, C.gold, "Metal"),
		B("BandBack", 0, 13.2, -(OUT + 0.25), 62, 0.8, 0.5, C.gold, "Metal"),
		B("BandFrontL", -(DH + OUT) / 2, 13.2, OUT + 0.25, OUT - DH, 0.8, 0.5, C.gold, "Metal"),
		B("BandFrontR", (DH + OUT) / 2, 13.2, OUT + 0.25, OUT - DH, 0.8, 0.5, C.gold, "Metal"),
		-- The lobby: a graphite header, a deep gold-edged canopy on two round columns
		B("DoorHeader", 0, 9.35, OUT + 0.5, 2 * DH, 0.7, 1, C.graphite, "SmoothPlastic"),
		B("Canopy", 0, 9.9, OUT + 3.5, 14, 0.6, 6, C.hqWhite, "SmoothPlastic"),
		B("CanopyLip", 0, 9.9, OUT + 6.65, 14, 0.8, 0.3, C.gold, "Metal"),
		U("CanopyColumnL", -6.4, G, OUT + 5.6, 1.2, 10.6, C.graphite, "SmoothPlastic"),
		U("CanopyColumnR", 6.4, G, OUT + 5.6, 1.2, 10.6, C.graphite, "SmoothPlastic"),
		-- The HQ sign over the door: a neon glow behind a graphite board
		B("SignGlow", 0, 11.6, OUT + 0.1, 7.8, 2.9, 0.15, C.neonBlue, "Neon"),
		B("SignBoard", 0, 11.6, OUT + 0.4, 7, 2.5, 0.45, C.graphite, "SmoothPlastic",
			{ text = { value = "HQ", font = "GothamBold", color = C.neonBlue, glow = true, area = { 0.05, 0.08, 0.9, 0.84 } } }),
		-- The roof: a glass dome box, an antenna with a gold tip, a helipad and two AC units
		B("DomeFrame", -16, ROOF_TOP + 1.4, -8, 9, 2.8, 9, C.graphite, "Metal"),
		B("DomeGlass", -16, ROOF_TOP + 3.1, -8, 7.6, 1.2, 7.6, C.skyGlass, "Glass", { transparency = 0.3 }),
		U("Antenna", 24, ROOF_TOP, -24, 0.5, 8, C.graphite, "Metal"),
		O("AntennaTip", 24, ROOF_TOP + 8.2, -24, 0.9, C.gold, "Metal"),
		P("HelipadDisc", "Cylinder", { 0.15, 13, 13 }, { 14, ROOF_TOP + 0.075, 4 }, C.graphite, "SmoothPlastic", { rot = { 0, 0, 90 } }),
		P("HelipadRing", "Cylinder", { 0.1, 9, 9 }, { 14, ROOF_TOP + 0.2, 4 }, C.gold, "SmoothPlastic", { rot = { 0, 0, 90 } }),
		B("AcUnitA", -24, ROOF_TOP + 1.25, 14, 5, 2.5, 4, C.silver, "Metal"),
		B("AcUnitB", -24, ROOF_TOP + 1.25, 22, 5, 2.5, 4, C.silver, "Metal"),
	}
)

ipoReady.static = join(
	{
		ground("Path", 0, 35.5, 14, 9, C.hqWhite, "SmoothPlastic"),
		U("FlagPoleL", -18, G, 33.5, 0.3, 9, C.silver, "Metal"),
		B("FlagL", -17.2, G + 8, 33.5, 1.6, 1.1, 0.1, C.gold, "Fabric"),
		U("FlagPoleR", 18, G, 33.5, 0.3, 9, C.silver, "Metal"),
		B("FlagR", 18.8, G + 8, 33.5, 1.6, 1.1, 0.1, C.flagRed, "Fabric"),
	},
	planter("PlanterL", -12, 33.5, C.graphite, C.leaf, 1.1),
	planter("PlanterR", 12, 33.5, C.graphite, C.leaf, 1.1)
)

PlotBuilding.Stages = { garage, seed, seriesA, seriesB, ipoReady }

return PlotBuilding
