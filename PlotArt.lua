-- PlotArt: what every stage room, hire desk and upgrade prop looks like (branch visuals-garage).
-- Put this ModuleScript in ServerScriptService, next to PlotVisuals (which builds it) and TycoonCore
-- (which decides when). Data only: built-in Parts and materials, no assets, nothing random.
--
-- Stages[i] is the room for IpoConfig.Stages[i] (same key): add a funding stage, add a room here.
-- Props[upgrade name] is the prop that stands in that upgrade's slot once it's bought (the names
-- are TycoonCore's UPGRADES names: they are saved, never rename them).
--
-- A part: P(name, shape, size, offset, color, material [, extra])
--   shape    "Block", "Cylinder" (lies along X: rot = { 0, 0, 90 } stands it up), "Ball" (3 equal
--            sides) or "Wedge" (rises toward +Z)
--   size     { x, y, z } studs
--   offset   { x, y, z } studs from the plot's floor-top center (for a prop: from its slot on the
--            floor; for a hire desk: from the desk's spot). +X right, +Z front (signs), -Z back.
--   color    { r, g, b } 0-255
--   material Concrete, CorrodedMetal, Metal, DiamondPlate, Wood, WoodPlanks, Brick, Fabric, Plastic,
--            SmoothPlastic, Glass, or Neon (lights and signs only: the name must say Bulb, Lamp,
--            Light, Screen, LED, Sign, Logo, Neon or Glow)
--   extra    rot = { x, y, z } degrees; collide = true (floors only); shadow = false; transparency;
--            light = { color, brightness, range } (a PointLight, at most 3 per plot);
--            text = { value, font, color, face, area, glow } (face "Back" = toward +Z);
--            particles = { ... } (the default emitter: no texture asset)
-- Everything else is decor: anchored, no collision, no touch, no queries.
--
-- A kit piece (furniture from the 3D kit, docs/KIT_MODELS.md): KIT(name, key, x, y, z, roles [, extra])
--   key      a key of PlotArt.Kit (a model in ReplicatedStorage.KitModels)
--   x, y, z  where its bottom-center stands (like an offset)
--   roles    { role = { color, material [, transparency] } } for every role of the model: the same model recolored
--   extra    turn = 0, 90, 180 or 270 (its front, +Z in the file, then faces that way: 90 = +X); scale = a number or
--            { x, y, z } (of the kit size); light = { color, brightness, range } on the part of role lightRole
-- PlotVisuals builds it from the kit's MeshParts, or from PlotArt.Kit's boxes when the kit is missing: same colors,
-- never bigger than the kit size times the scale.

local PlotArt = {}

-- The layout map -----------------------------------------------------------
-- Where the game's own objects stand, copied from the scripts (tools/daily_test.py checks every
-- number against them). Offsets from the plot's floor-top center, in studs.
PlotArt.Layout = {
	floorSize = { 60, 1, 60 }, -- TycoonCore's "Floor" Part, centered on plotCenter
	floorTop = 0.5, -- its top face, above plotCenter
	signs = { -- the two garage signs (non-interactive: nothing buys or opens by touch)
		{ name = "BuySign", x = 0, z = 24 }, -- TycoonCore SIGN_OFFSET: names the next upgrade
		{ name = "IpoSign", x = 21, z = 24 }, -- IpoServer SIGN_OFFSET: funding stage and valuation
	},
	spawn = { x = 0, z = 12 }, -- TycoonCore teleportToPlot
	-- The upgrade props, in UPGRADES order: two walls of stations (TycoonCore itemOffset), in line with the hire rows
	itemSlots = {
		{ name = "Desk", x = -23, z = -10 },
		{ name = "Coffee Machine", x = -23, z = 2 },
		{ name = "Laptop", x = -23, z = 14 },
		{ name = "Server Rack", x = 23, z = -10 },
		{ name = "Whiteboard", x = 23, z = 2 },
		{ name = "Neon Logo", x = 23, z = 14 },
	},
	incubators = { { -12, -25 }, { 0, -25 }, { 12, -25 }, { -24, -25 }, { 24, -25 } }, -- EmployeeServer INCUBATOR_SPOTS
	-- EmployeeServer EMPLOYEE_SPOTS: a grid of 4 columns (9 apart) and 3 rows (12 apart), filled row by row
	-- from the middle out. A hire strolls up to 3 studs around its spot.
	employeeSpots = {
		{ -4.5, -10 }, { 4.5, -10 }, { -13.5, -10 }, { 13.5, -10 },
		{ -4.5, 2 }, { 4.5, 2 }, { -13.5, 2 }, { 13.5, 2 },
		{ -4.5, 14 }, { 4.5, 14 }, { -13.5, 14 },
	},
	-- Each hire's desk: { x, z offset from its spot, turn in degrees }. All in front of the hire (+Z), all
	-- facing the same way.
	desks = {
		{ 0, 3.3, 0 }, { 0, 3.3, 0 }, { 0, 3.3, 0 }, { 0, 3.3, 0 }, { 0, 3.3, 0 }, { 0, 3.3, 0 },
		{ 0, 3.3, 0 }, { 0, 3.3, 0 }, { 0, 3.3, 0 }, { 0, 3.3, 0 }, { 0, 3.3, 0 },
	},
	-- Reserved zones (PlotVisuals.zones): the signs, the spawn and the walking lane down the middle, incubators
	-- + the space in front of them, where each hire stands and its desk, the upgrade slots, and the aisles
	-- (between the incubators and the first row, and between rows: at least minAisle studs). Heights: nothing
	-- of the room below these. Props stay inside their slot zone, and the zones never overlap each other.
	reserve = {
		signHalfX = 4.5, signHalfZ = 1.5, signHeight = 6, height = 8, spawnHalf = 2.5, incubatorHalf = 3.5, incubatorFront = 7,
		hireHalf = 1.5, hireHeight = 7, deskHalfX = 1.9, deskFrom = 2.4, deskTo = 4.2, deskHeight = 3,
		slotHalfX = 6, slotBack = 4.5, slotFront = 3.5, slotHeight = 12, minAisle = 6, laneEnd = 30,
	},
}

-- The furniture kit ---------------------------------------------------------------
-- The kit models the rooms use, copied from docs/KIT_MODELS.md (tools/daily_test.py compares them): size = { width (X),
-- height (Y), depth (Z) }, roles = the model's MeshParts (one per role), fallback = its Parts version: boxes { role,
-- size, at (center), shape } in the model's own frame (bottom-center, front +Z), inside its size, each role at least once.
PlotArt.KIT_FOLDER = "KitModels" -- ReplicatedStorage.KitModels.<Key>
PlotArt.KIT_FRONT_TURN = 180 -- the importer's turn: always the same as PlotBuilding.KIT_FRONT_TURN (tools/daily_test.py checks)

local function box(role, w, h, d, x, y, z, shape)
	return { role = role, size = { w, h, d }, at = { x, y, z }, shape = shape }
end

PlotArt.Kit = {
	-- A wooden crate: the body and a lid board on top
	Crate = { size = { 4, 4, 4 }, roles = { "main", "trim" }, fallback = {
		box("main", 3.8, 3.6, 3.8, 0, 1.8, 0),
		box("trim", 4, 0.4, 4, 0, 3.8, 0),
	} },
	-- A workbench: the top, two leg frames, a low shelf and a vise on the top
	Workbench = { size = { 8, 4, 4 }, roles = { "main", "trim", "accent", "dark" }, fallback = {
		box("main", 8, 0.5, 4, 0, 3.25, 0),
		box("dark", 0.5, 3, 3.6, -3.6, 1.5, 0),
		box("dark", 0.5, 3, 3.6, 3.6, 1.5, 0),
		box("trim", 6.7, 0.3, 3.4, 0, 0.8, 0),
		box("accent", 1.2, 0.5, 0.9, 2.6, 3.75, 1),
	} },
	-- A desk (you sit on its +Z side): the top, two side panels, a modesty panel at the back
	Desk = { size = { 8, 3, 4 }, roles = { "main", "trim", "dark" }, fallback = {
		box("main", 8, 0.3, 4, 0, 2.85, 0),
		box("dark", 0.4, 2.7, 3.6, -3.7, 1.35, 0),
		box("dark", 0.4, 2.7, 3.6, 3.7, 1.35, 0),
		box("trim", 7, 1.4, 0.2, 0, 2, -1.7),
	} },
	-- A chair: the base, the seat, the back (at -Z: the seat side, +Z, is its front)
	Chair = { size = { 3, 4, 3 }, roles = { "main", "trim", "dark" }, fallback = {
		box("dark", 2.4, 1, 2.4, 0, 0.5, 0),
		box("main", 3, 0.8, 3, 0, 1.4, 0),
		box("trim", 3, 2.2, 0.6, 0, 2.9, -1.2),
	} },
	-- A bare bulb hanging from its cord: the glass at the bottom, the socket, the cord up to the top
	BareBulb = { size = { 1, 3, 1 }, roles = { "trim", "glass", "dark" }, fallback = {
		box("glass", 1, 1, 1, 0, 0.6, 0, "Ball"),
		box("trim", 0.5, 0.4, 0.5, 0, 1.3, 0),
		box("dark", 0.12, 1.5, 0.12, 0, 2.25, 0),
	} },
}

-- Palette --------------------------------------------------------------------
local C = {
	-- Garage
	rust = { 150, 86, 52 }, rustLight = { 178, 112, 70 }, rustDark = { 104, 58, 38 },
	tin = { 140, 148, 150 }, tinDark = { 104, 110, 116 }, steel = { 84, 86, 92 },
	door = { 176, 184, 188 }, doorDark = { 150, 158, 164 },
	woodDark = { 104, 74, 50 }, dustyGlass = { 196, 192, 160 }, tape = { 228, 206, 150 },
	cord = { 38, 38, 42 }, bulb = { 255, 222, 150 }, warmLight = { 255, 196, 128 },
	tableTop = { 206, 200, 186 }, beige = { 214, 204, 176 }, crtGreen = { 120, 220, 150 },
	phone = { 64, 62, 60 }, phoneDark = { 44, 42, 40 }, mugRed = { 196, 64, 56 },
	canRed = { 210, 60, 60 }, canGreen = { 80, 176, 90 }, canBlue = { 60, 120, 210 },
	sticky = { 255, 234, 110 }, ink = { 40, 32, 30 }, inkBlue = { 40, 80, 170 },
	paintBlue = { 70, 130, 200 }, paintRed = { 214, 82, 70 }, bucketWhite = { 226, 226, 220 },
	wood = { 170, 122, 78 }, cardboard = { 196, 156, 104 }, cardboardDark = { 168, 128, 82 },
	pizza = { 222, 196, 150 }, pizzaDark = { 206, 176, 128 }, cordOrange = { 236, 140, 40 },
	oil = { 40, 38, 42 }, crack = { 108, 104, 96 }, tire = { 38, 38, 42 },
	sleepingBag = { 64, 120, 90 }, pillow = { 236, 230, 214 },
	trashBag = { 48, 48, 54 }, trashBag2 = { 70, 70, 78 },
	weed = { 104, 168, 72 }, weedDark = { 72, 132, 54 }, dirt = { 140, 106, 72 },
	crate = { 176, 134, 88 }, board = { 200, 164, 112 },
	-- Props
	white = { 246, 246, 242 }, black = { 32, 32, 36 }, silver = { 200, 204, 210 },
	walnut = { 140, 98, 66 }, walnutDark = { 104, 70, 46 }, gold = { 255, 196, 60 }, brass = { 196, 160, 80 },
	lampGlow = { 190, 255, 170 }, mugWhite = { 240, 240, 236 }, espressoRed = { 200, 56, 48 },
	coffeeBag = { 120, 84, 56 }, rack = { 40, 42, 48 }, serverGray = { 72, 76, 84 },
	ledGreen = { 80, 255, 140 }, ledCyan = { 80, 220, 255 }, cableBlue = { 60, 120, 230 }, cableRed = { 220, 70, 60 },
	steelDark = { 54, 56, 62 }, neonBlue = { 0, 170, 255 }, neonOrange = { 255, 150, 60 }, navyDark = { 26, 34, 60 },
	screenBlue = { 130, 190, 255 }, pot = { 200, 112, 74 }, leaf = { 86, 168, 86 },
	barBlue = { 70, 140, 230 }, barGreen = { 80, 190, 110 }, barOrange = { 240, 150, 60 },
	walnutLight = { 184, 136, 92 }, charcoal = { 52, 54, 60 }, grayLight = { 170, 176, 186 }, frameDark = { 78, 82, 92 },
	beigeDark = { 172, 162, 136 }, phoneRed = { 190, 56, 50 }, phoneRedDark = { 142, 40, 38 }, powerGreen = { 90, 220, 120 },
	barBlueLight = { 140, 190, 245 }, barBlueDark = { 40, 96, 190 }, rocketWhite = { 235, 244, 255 },
	-- Stage 2: the glow-up (fresh mint paint, a coral sofa, teal trim)
	mint = { 170, 226, 204 }, mintDark = { 46, 110, 100 }, mintLight = { 214, 242, 230 }, coral = { 232, 128, 102 }, coralLight = { 248, 172, 148 },
	oak = { 214, 184, 140 }, oakDark = { 150, 112, 76 }, offwhite = { 244, 246, 244 }, doorLight = { 238, 242, 242 }, doorGray = { 204, 210, 214 },
	rugTeal = { 60, 138, 126 }, cream = { 246, 238, 214 }, glassTint = { 126, 172, 190 }, glassDark = { 54, 84, 100 }, skyGlass = { 170, 210, 232 },
	-- Stage 3: the loft (red brick, black steel, amber)
	brick = { 172, 94, 76 }, brickLight = { 190, 112, 90 }, steelBlack = { 40, 44, 54 }, birch = { 232, 224, 206 }, sofaBlue = { 72, 86, 112 },
	sofaBlueLight = { 112, 130, 164 }, amber = { 246, 154, 52 }, bayDark = { 44, 52, 66 }, shutter = { 196, 202, 206 },
	stickyPink = { 255, 170, 190 }, stickyGreen = { 170, 232, 150 },
	-- Stage 4: the office (white, navy, cobalt, blue-gray carpet)
	officeWhite = { 240, 242, 244 }, navy = { 34, 42, 62 }, cobalt = { 52, 120, 230 }, carpetLine = { 86, 100, 120 }, officeGlass = { 150, 196, 220 },
	-- Stage 5: the headquarters (polished white, graphite, gold, a pale blue skyline)
	hqWhite = { 246, 247, 248 }, graphite = { 38, 40, 48 }, skyA = { 128, 156, 196 }, skyB = { 154, 180, 214 }, skyC = { 104, 132, 172 },
}

-- Helpers --------------------------------------------------------------------

local function P(name, shape, size, offset, color, material, extra)
	local spec = extra or {}
	spec.name, spec.shape, spec.size, spec.offset, spec.color, spec.material = name, shape, size, offset, color, material
	return spec
end

-- One list from several lists of parts
local function join(...)
	local out = {}
	for _, list in ipairs({ ... }) do
		for _, spec in ipairs(list) do
			table.insert(out, spec)
		end
	end
	return out
end

-- A weed: two blades. y = what it grows from (0 the Floor, -1 the ground around it)
local function weed(name, x, y, z, yaw)
	return {
		P(name .. "A", "Wedge", { 0.2, 1.1, 0.5 }, { x, y + 0.55, z }, C.weed, "SmoothPlastic", { rot = { 0, yaw, 6 } }),
		P(name .. "B", "Wedge", { 0.2, 0.8, 0.45 }, { x + 0.3, y + 0.4, z + 0.1 }, C.weedDark, "SmoothPlastic", { rot = { 0, yaw + 70, -8 } }),
	}
end

-- A cylinder standing up (its length is the height)
local function upright(name, height, diameter, x, y, z, color, material)
	return P(name, "Cylinder", { height, diameter, diameter }, { x, y + height / 2, z }, color, material, { rot = { 0, 0, 90 } })
end

-- A block from its center and its width, height and depth (the shape most decor is)
local function B(name, x, y, z, w, h, d, color, material, extra)
	return P(name, "Block", { w, h, d }, { x, y, z }, color, material, extra)
end

-- A kit piece (see the top of this file): a model of PlotArt.Kit standing at x, y, z, recolored by roles
local function KIT(name, key, x, y, z, roles, extra)
	local spec = extra or {}
	spec.name, spec.kit, spec.offset, spec.roles = name, key, { x, y, z }, roles
	return spec
end

-- A plant: a pot and a round bush on it
local function plant(name, x, z, pot, bush, potColor, leafColor)
	return {
		upright(name .. "Pot", pot[1], pot[2], x, 0, z, potColor, "SmoothPlastic"),
		P(name .. "Leaves", "Ball", { bush, bush, bush }, { x, pot[1] + bush * 0.4, z }, leafColor, "Fabric"),
	}
end

-- A sofa against the left wall, facing +X (the center is the middle of its base on the floor)
local function sofaLeft(name, x, z, body, cushion)
	return {
		B(name .. "Base", x, 0.45, z, 2.6, 0.9, 6, body, "SmoothPlastic"),
		B(name .. "Seat", x + 0.3, 1.15, z, 2, 0.5, 5.2, cushion, "Fabric"),
		B(name .. "Back", x - 0.8, 1.9, z, 0.7, 2, 6, body, "SmoothPlastic"),
		B(name .. "ArmA", x, 1.4, z - 2.65, 2.4, 1, 0.7, body, "SmoothPlastic"),
		B(name .. "ArmB", x, 1.4, z + 2.65, 2.4, 1, 0.7, body, "SmoothPlastic"),
	}
end

-- The founder's desk, standing in the front band (z 24.5) with its chair on the +Z side: its screen
-- and its DeskPhone (the one the phone step makes ring) face the front. look = { top, panel, accent }
local function founderDesk(x, z, look)
	return {
		B("FounderTop", x, 2.5, z, 5.4, 0.2, 2.4, look.top, "Wood"),
		B("FounderPanelLeft", x - 2.3, 1.2, z, 0.2, 2.4, 2.2, look.panel, "Metal"),
		B("FounderPanelRight", x + 2.3, 1.2, z, 0.2, 2.4, 2.2, look.panel, "Metal"),
		B("FounderStand", x - 0.5, 2.775, z, 0.3, 0.35, 0.3, C.charcoal, "Metal"),
		B("FounderMonitor", x - 0.5, 3.55, z, 2.4, 1.4, 0.12, C.black, "SmoothPlastic"),
		B("FounderScreen", x - 0.5, 3.55, z + 0.08, 2.1, 1.1, 0.04, look.accent, "Neon"),
		B("DeskPhone", x + 1.6, 2.75, z + 0.4, 1.1, 0.3, 0.85, C.phoneRed, "SmoothPlastic"),
		B("FounderKeyboard", x - 0.5, 2.64, z + 0.7, 1.6, 0.08, 0.5, C.charcoal, "SmoothPlastic"),
		upright("FounderChairPost", 1.5, 0.3, x - 0.5, 0, z + 2, C.steel, "Metal"),
		B("FounderChairSeat", x - 0.5, 1.65, z + 2, 1.8, 0.3, 1.8, C.black, "Fabric"),
		B("FounderChairBack", x - 0.5, 2.8, z + 2.9, 1.8, 2, 0.3, C.black, "Fabric"),
	}
end

-- A prop designed at its natural size, then made bigger so it reads from the default camera: every
-- size and offset is multiplied by k (rotations, colors, text, lights and particles stay as they are)
local function scaled(list, k)
	local out = {}
	for _, spec in ipairs(list) do
		local copy = {}
		for key, value in pairs(spec) do
			copy[key] = value
		end
		copy.size = { spec.size[1] * k, spec.size[2] * k, spec.size[3] * k }
		copy.offset = { spec.offset[1] * k, spec.offset[2] * k, spec.offset[3] * k }
		table.insert(out, copy)
	end
	return out
end

local STEAM = { -- coffee steam
	rate = 3, lifetime = { 1.2, 2.2 }, speed = { 1, 1.8 }, spread = 12, size = { 0.25, 0.8 },
	transparency = { 0.45, 1 }, color = { { 255, 255, 255 }, { 230, 230, 230 } }, lightEmission = 0.1,
	direction = "Right", -- an upright cylinder's +X points up
}

-- Stage 1: the Garage ------------------------------------------------------------
-- A poor founder's garage: cracked concrete, dented rusty sheet walls, a half-open roll-up door,
-- one dusty taped window and a bare bulb. The only tech: an old PC and a desk phone.

local garage = { key = "Garage", floor = { color = { 150, 145, 136 }, material = "Concrete" } }

garage.shell = {
	-- Back wall (12 high, behind the incubators): rusty sheets around the roll-up door (x -7..7)
	P("BackSheet1", "Block", { 12, 11.6, 0.6 }, { -24, 5.8, -29.7 }, C.rust, "CorrodedMetal"),
	P("BackSheet2", "Block", { 11, 11.6, 0.6 }, { -12.5, 5.8, -29.7 }, C.rustLight, "CorrodedMetal", { rot = { 0, 0, 0.6 } }),
	P("BackSheet3", "Block", { 11, 11.6, 0.6 }, { 12.5, 5.8, -29.7 }, C.tin, "CorrodedMetal"),
	P("BackSheet4", "Block", { 12, 11.6, 0.6 }, { 24, 5.8, -29.7 }, C.rust, "CorrodedMetal", { rot = { 0, 0, -0.5 } }),
	P("DoorHeader", "Block", { 14, 1.6, 0.6 }, { 0, 10.8, -29.7 }, C.rustDark, "CorrodedMetal"),
	P("BackCap", "Block", { 60, 0.4, 0.9 }, { 0, 11.8, -29.7 }, C.rustDark, "Metal"),
	-- The roll-up door, stuck half open
	P("DoorPostLeft", "Block", { 0.6, 10, 0.9 }, { -7.3, 5, -29.55 }, C.steel, "Metal"),
	P("DoorPostRight", "Block", { 0.6, 10, 0.9 }, { 7.3, 5, -29.55 }, C.steel, "Metal"),
	P("DoorRoller", "Cylinder", { 14.4, 1.3, 1.3 }, { 0, 10.35, -28.95 }, C.tinDark, "Metal"),
	P("DoorSlat1", "Block", { 13.6, 1.6, 0.3 }, { 0, 5.8, -29.5 }, C.door, "Metal"),
	P("DoorSlat2", "Block", { 13.6, 1.6, 0.3 }, { 0, 7.4, -29.5 }, C.doorDark, "Metal", { rot = { 0, 0, 0.8 } }),
	P("DoorSlat3", "Block", { 13.6, 1.6, 0.3 }, { 0, 9, -29.5 }, C.door, "Metal"),
	P("DoorBottomBar", "Block", { 13.6, 0.35, 0.45 }, { 0, 5, -29.45 }, C.steel, "Metal"),
	-- Corrugation ribs
	P("Rib1", "Block", { 0.35, 11.6, 0.2 }, { -27, 5.8, -29.3 }, C.rustDark, "CorrodedMetal"),
	P("Rib2", "Block", { 0.35, 11.6, 0.2 }, { -21, 5.8, -29.3 }, C.rustDark, "CorrodedMetal"),
	P("Rib3", "Block", { 0.35, 11.6, 0.2 }, { -15.5, 5.8, -29.3 }, C.rustDark, "CorrodedMetal"),
	P("Rib4", "Block", { 0.35, 11.6, 0.2 }, { -10.5, 5.8, -29.3 }, C.rustDark, "CorrodedMetal"),
	P("Rib5", "Block", { 0.35, 11.6, 0.2 }, { 22, 5.8, -29.3 }, C.rustDark, "CorrodedMetal"),
	P("Rib6", "Block", { 0.35, 11.6, 0.2 }, { 27, 5.8, -29.3 }, C.rustDark, "CorrodedMetal"),
	-- Side walls (5.5 high, the camera looks in over them): patched sheets
	P("SideSheetL1", "Block", { 0.6, 5.5, 19.6 }, { -29.7, 2.75, -19.6 }, C.rust, "CorrodedMetal"),
	P("SideSheetL2", "Block", { 0.6, 5.5, 20 }, { -29.7, 2.75, 0.2 }, C.tin, "CorrodedMetal", { rot = { 0, 0.5, 0 } }),
	P("SideSheetL3", "Block", { 0.6, 5.5, 19.8 }, { -29.7, 2.75, 20.1 }, C.rustLight, "CorrodedMetal"),
	P("SideSheetR1", "Block", { 0.6, 5.5, 19.6 }, { 29.7, 2.75, -19.6 }, C.rustLight, "CorrodedMetal"),
	P("SideSheetR2", "Block", { 0.6, 5.5, 20 }, { 29.7, 2.75, 0.2 }, C.rust, "CorrodedMetal", { rot = { 0, -0.5, 0 } }),
	P("SideSheetR3", "Block", { 0.6, 5.5, 19.8 }, { 29.7, 2.75, 20.1 }, C.tin, "CorrodedMetal"),
	P("SideCapLeft", "Block", { 0.9, 0.3, 59.4 }, { -29.7, 5.65, 0.3 }, C.rustDark, "Metal"),
	P("SideCapRight", "Block", { 0.9, 0.3, 59.4 }, { 29.7, 5.65, 0.3 }, C.rustDark, "Metal"),
	P("PostBackLeft", "Block", { 0.9, 12, 0.9 }, { -29.7, 6, -29.7 }, C.steel, "Metal"),
	P("PostBackRight", "Block", { 0.9, 12, 0.9 }, { 29.7, 6, -29.7 }, C.steel, "Metal"),
	P("PostFrontLeft", "Block", { 0.9, 5.9, 0.9 }, { -29.7, 2.95, 29.55 }, C.steel, "Metal"),
	P("PostFrontRight", "Block", { 0.9, 5.9, 0.9 }, { 29.7, 2.95, 29.55 }, C.steel, "Metal"),
	-- One dusty window, taped where it cracked
	P("WindowFrame", "Block", { 7.6, 4.6, 0.25 }, { 14.5, 7, -29.27 }, C.woodDark, "Wood"),
	P("WindowGlass", "Block", { 6.8, 3.8, 0.1 }, { 14.5, 7, -29.1 }, C.dustyGlass, "Glass", { transparency = 0.15 }),
	P("WindowTape1", "Block", { 5.2, 0.4, 0.05 }, { 14.5, 7, -29.02 }, C.tape, "SmoothPlastic", { rot = { 0, 0, 32 } }),
	P("WindowTape2", "Block", { 5.2, 0.4, 0.05 }, { 14.5, 7, -29.01 }, C.tape, "SmoothPlastic", { rot = { 0, 0, -32 } }),
}

-- The founder's corner, moved to the front-left of the room (the middle is the hire grid): the old PC,
-- the phone and the dinner. Written around the folding table at (9, 2.2); `moved` carries it to its spot.
-- The Garage's furniture from the kit, recolored worn and secondhand
local OLD_DESK = { main = { C.woodDark, "Wood" }, trim = { C.tinDark, "Metal" }, dark = { C.steel, "Metal" } }
local OLD_CHAIR = { main = { C.sleepingBag, "Fabric" }, trim = { C.tinDark, "Metal" }, dark = { C.cord, "SmoothPlastic" } }
local CRATE = { main = { C.crate, "WoodPlanks" }, trim = { C.board, "Wood" } }
local BENCH = { main = { C.wood, "WoodPlanks" }, trim = { C.tinDark, "Metal" }, accent = { C.paintRed, "Metal" }, dark = { C.steel, "Metal" } }
local BULB = { trim = { C.steel, "Metal" }, glass = { C.bulb, "Neon" }, dark = { C.cord, "SmoothPlastic" } }

local corner = {
	-- The founder's corner: an old secondhand desk (the kit's Desk, worn wood, its top at 2.7), an old chunky PC and a landline phone
	KIT("OldDesk", "Desk", 9, 0, 2.2, OLD_DESK, { scale = { 0.6, 0.9, 0.65 } }),
	P("CRTStand", "Block", { 1, 0.1, 1 }, { 8.3, 2.75, 1.9 }, C.beigeDark, "SmoothPlastic"),
	P("ComputerCRT", "Block", { 2.2, 1.8, 1.7 }, { 8.3, 3.7, 1.95 }, C.beige, "SmoothPlastic"),
	P("CRTHump", "Block", { 1.5, 1.2, 0.7 }, { 8.3, 3.6, 1.05 }, C.beigeDark, "SmoothPlastic"),
	P("CRTBezel", "Block", { 1.8, 1.45, 0.08 }, { 8.3, 3.72, 2.83 }, C.beigeDark, "SmoothPlastic"),
	P("ComputerScreen", "Block", { 1.4, 1.1, 0.06 }, { 8.3, 3.72, 2.89 }, C.crtGreen, "Neon", { light = { color = C.crtGreen, brightness = 0.8, range = 8 } }),
	P("ComputerTower", "Block", { 0.9, 1.9, 1.9 }, { 12, 0.95, 2 }, C.beige, "SmoothPlastic"),
	P("TowerFloppy", "Block", { 0.6, 0.09, 0.05 }, { 12, 1.45, 2.97 }, C.charcoal, "SmoothPlastic"),
	P("TowerPowerDot", "Block", { 0.16, 0.16, 0.05 }, { 12.25, 0.55, 2.97 }, C.powerGreen, "SmoothPlastic"),
	P("Keyboard", "Block", { 1.7, 0.12, 0.5 }, { 8.4, 2.76, 3.15 }, C.beige, "SmoothPlastic"),
	P("KeyboardKeys", "Block", { 1.5, 0.05, 0.34 }, { 8.4, 2.84, 3.15 }, C.beigeDark, "SmoothPlastic"),
	P("DeskPhone", "Block", { 1.1, 0.3, 0.85 }, { 10.4, 2.85, 2.3 }, C.phoneRed, "SmoothPlastic"),
	P("PhoneKeypad", "Block", { 0.5, 0.05, 0.4 }, { 10.4, 3.025, 2.5 }, C.tape, "SmoothPlastic"),
	P("DeskPhoneHandset", "Block", { 1.3, 0.2, 0.3 }, { 10.4, 3.1, 2.05 }, C.phoneRedDark, "SmoothPlastic"),
	P("HandsetEar", "Block", { 0.3, 0.26, 0.36 }, { 9.82, 3.1, 2.05 }, C.phoneRedDark, "SmoothPlastic"),
	upright("Mug", 0.55, 0.45, 7.3, 2.7, 1.5, C.mugRed, "SmoothPlastic"),
	upright("SodaCan1", 0.55, 0.4, 10.6, 2.7, 3.15, C.canRed, "SmoothPlastic"),
	P("StickyNote", "Block", { 0.7, 0.7, 0.04 }, { 9.25, 4.25, 2.985 }, C.sticky, "SmoothPlastic",
		{ rot = { 0, 0, 8 }, text = { value = "WIFI:\nask mom", font = "IndieFlower", color = C.ink } }),
	KIT("OldChair", "Chair", 9, 0, 4.9, OLD_CHAIR, { scale = 0.75, turn = 180 }), -- facing the desk
	upright("SignBucket", 1.2, 1.1, 11.4, 0, 6.2, C.bucketWhite, "Plastic"),
	P("SignStick", "Block", { 0.18, 4.2, 0.18 }, { 11.4, 2.4, 6.2 }, C.wood, "Wood"),
	P("OfficeSign", "Block", { 3, 1.4, 0.12 }, { 11.4, 3.9, 6.33 }, C.cardboard, "SmoothPlastic",
		{ rot = { 0, 0, -4 }, text = { value = "OFFICE", font = "PermanentMarker", color = C.ink } }),
	-- Dinner and power: two pizza boxes, cans, an extension cord with one socket
	P("PizzaBox1", "Block", { 2.2, 0.28, 2.2 }, { 6.5, 0.14, 5.6 }, C.pizza, "SmoothPlastic"),
	P("PizzaBox2", "Block", { 2.2, 0.28, 2.2 }, { 6.6, 0.42, 5.5 }, C.pizza, "SmoothPlastic", { rot = { 0, 10, 0 } }),
	P("SodaCan2", "Cylinder", { 0.55, 0.4, 0.4 }, { 5.6, 0.2, 7.3 }, C.canGreen, "SmoothPlastic", { rot = { 0, 30, 0 } }),
	upright("SodaCan3", 0.55, 0.4, 8, 0, 7.1, C.canBlue, "SmoothPlastic"),
	P("PowerStrip", "Block", { 1.4, 0.25, 0.5 }, { 12.3, 0.125, 7.4 }, C.bucketWhite, "Plastic"),
	P("PowerSocket", "Block", { 0.32, 0.04, 0.32 }, { 12, 0.27, 7.4 }, C.cord, "SmoothPlastic"),
	P("ExtensionCord", "Block", { 10.7, 0.12, 0.12 }, { 6.95, 0.06, 7.4 }, C.cordOrange, "SmoothPlastic"),
	P("PcCord", "Block", { 0.12, 0.12, 4.45 }, { 12.3, 0.06, 5.175 }, C.cord, "SmoothPlastic"),
}

-- A copy of a list of parts, carried dx studs along X and dz along Z (the Y of every part stays)
local function moved(list, dx, dz)
	local out = {}
	for _, spec in ipairs(list) do
		local copy = {}
		for key, value in pairs(spec) do
			copy[key] = value
		end
		copy.offset = { spec.offset[1] + dx, spec.offset[2], spec.offset[3] + dz }
		table.insert(out, copy)
	end
	return out
end

garage.decor = join({
	-- The bare bulb (the kit's BareBulb), hanging on its cord from an arm over the door
	P("LampArm", "Block", { 0.3, 0.3, 3.6 }, { -6, 10.6, -27.6 }, C.steel, "Metal"),
	KIT("Bulb", "BareBulb", -6, 7.45, -26, BULB, { lightRole = "glass", light = { color = C.warmLight, brightness = 2.2, range = 40 } }),
	-- The workbench in the front-right corner, and two crates stacked in the back-right corner
	KIT("Workbench", "Workbench", 10.5, 0, 20.2, BENCH, { scale = 0.8 }),
	KIT("JunkCrateLow", "Crate", 25.6, 0, -16.3, CRATE, { scale = 0.7 }),
	KIT("JunkCrateHigh", "Crate", 25.8, 2.8, -16.2, CRATE, { scale = 0.6, turn = 90 }),
	-- The floor: an oil stain and cracks
	P("OilStain1", "Cylinder", { 0.04, 4.6, 4.6 }, { -8.5, 0.02, 7.5 }, C.oil, "SmoothPlastic", { rot = { 0, 0, 90 } }),
	P("Crack1", "Block", { 5.5, 0.03, 0.14 }, { -14, 0.015, -8.8 }, C.crack, "Concrete", { rot = { 0, 25, 0 } }),
	P("Crack2", "Block", { 4.2, 0.03, 0.12 }, { 5.5, 0.015, -9.2 }, C.crack, "Concrete", { rot = { 0, -35, 0 } }),
	P("Crack3", "Block", { 6, 0.03, 0.14 }, { -20, 0.015, 16.5 }, C.crack, "Concrete", { rot = { 0, 12, 0 } }),
	-- Junk between the incubators: tires, paint buckets, two boxes, a rusty bike
	upright("Tire1", 0.9, 2.6, -18, 0, -27.4, C.tire, "SmoothPlastic"),
	upright("Tire2", 0.9, 2.6, -18.15, 0.9, -27.3, C.tire, "SmoothPlastic"),
	upright("Tire3", 0.9, 2.6, -17.9, 1.8, -27.5, C.tire, "SmoothPlastic"),
	upright("PaintBucket1", 1.3, 1.1, -7.2, 0, -27.8, C.bucketWhite, "Plastic"),
	upright("PaintBucket2", 1.3, 1.1, -5.5, 0, -28.1, C.paintRed, "Plastic"),
	upright("PaintBucket3", 1.3, 1.1, -7.1, 1.3, -27.85, C.paintBlue, "Plastic"),
	P("Box1", "Block", { 2.2, 1.8, 2 }, { 5.6, 0.9, -27.6 }, C.cardboard, "SmoothPlastic", { rot = { 0, 6, 0 } }),
	P("Box2", "Block", { 1.8, 1.5, 1.8 }, { 6.6, 0.75, -25.1 }, C.cardboardDark, "SmoothPlastic", { rot = { 0, -12, 0 } }),
	P("BikeWheelBack", "Cylinder", { 0.25, 2.2, 2.2 }, { 19.3, 1.1, -28.55 }, C.tire, "SmoothPlastic", { rot = { 0, 90, 0 } }),
	P("BikeWheelFront", "Cylinder", { 0.25, 2.2, 2.2 }, { 16.7, 1.1, -28.55 }, C.tire, "SmoothPlastic", { rot = { 0, 90, 0 } }),
	P("BikeTopTube", "Block", { 2.5, 0.2, 0.2 }, { 18.05, 2.1, -28.55 }, C.rust, "CorrodedMetal"),
	P("BikeDownTube", "Block", { 1.8, 0.2, 0.2 }, { 17.6, 1.6, -28.55 }, C.rust, "CorrodedMetal", { rot = { 0, 0, -35.5 } }),
	P("BikeFork", "Block", { 0.18, 1.42, 0.18 }, { 16.83, 1.8, -28.55 }, C.rust, "CorrodedMetal", { rot = { 0, 0, -10 } }),
	P("BikeSeat", "Block", { 0.8, 0.22, 0.4 }, { 19, 2.31, -28.55 }, C.tire, "SmoothPlastic"),
	P("BikeHandlebar", "Block", { 0.18, 0.18, 1.2 }, { 16.95, 2.55, -28.55 }, C.steel, "Metal"),
	-- Where the founder sleeps: in the back corner, out of the way
	P("SleepingBag", "Block", { 1.6, 0.5, 6 }, { -28.5, 0.25, -24.4 }, C.sleepingBag, "Fabric", { rot = { 0, 2, 0 } }),
	P("Pillow", "Block", { 1.4, 0.45, 1 }, { -28.5, 0.725, -27.2 }, C.pillow, "Fabric"),
	-- Trash in the corner
	P("TrashBag1", "Ball", { 1.6, 1.6, 1.6 }, { 27.8, 0.8, 26.5 }, C.trashBag, "SmoothPlastic"),
	P("TrashBag2", "Ball", { 1.2, 1.2, 1.2 }, { 28.4, 0.6, 28.3 }, C.trashBag2, "SmoothPlastic"),
	-- The lot around it: dirt (on the ground, 1 stud under the Floor's top)
	P("DirtFront", "Block", { 26, 0.06, 6 }, { 0, -0.97, 33.2 }, C.dirt, "Concrete"),
	P("DirtBack", "Block", { 16, 0.06, 7 }, { 0, -0.97, -34 }, C.dirt, "Concrete"),
	P("DirtLeft", "Block", { 5, 0.06, 20 }, { -33, -0.97, -4 }, C.dirt, "Concrete"),
	P("DirtRight", "Block", { 5, 0.06, 16 }, { 33, -0.97, 12 }, C.dirt, "Concrete"),
},
	moved(corner, -31, 20),
	weed("Weed1", -28.9, 0, 8, 20), weed("Weed2", 28.9, 0, -17, -40), weed("Weed3", -15.3, 0, 28.6, 75),
	weed("Weed4", -31.3, -1, 2, 10), weed("Weed5", 31.3, -1, -12, 130)
)

-- A hire's desk: a crate on its side, the kit's Crate made low and shallow to fit the desk zone (no tech in the garage)
garage.desk = {
	KIT("Crate", "Crate", 0, 0, 0, CRATE, { scale = { 0.9, 0.55, 0.44 } }),
}

-- Stage 2: the garage glow-up (Seed) -------------------------------------------------
-- The same garage with money in it: fresh mint paint with dark teal trim, a new sectional door, clean
-- windows, a desk for every hire, string lights over the door and a rug and a sofa in the front-left
-- corner. Nothing of it stands in a reserved gameplay zone (PlotVisuals.check proves it).

local seed = { key = "Seed", floor = { color = { 190, 188, 180 }, material = "Concrete" } }

seed.shell = {
	-- Back wall (12 high): mint paint, a dark baseboard and cap
	B("BackWall", 0, 5.8, -29.7, 60, 11.6, 0.6, C.mint, "SmoothPlastic"),
	B("BackBase", 0, 0.35, -29.34, 60, 0.7, 0.12, C.mintDark, "SmoothPlastic"),
	B("BackCap", 0, 11.8, -29.7, 60, 0.4, 0.9, C.mintDark, "Metal"),
	-- Side walls (5.5 high, the camera looks in over them)
	B("SideWallL", -29.7, 2.75, 0.3, 0.6, 5.5, 59.4, C.mint, "SmoothPlastic"),
	B("SideWallR", 29.7, 2.75, 0.3, 0.6, 5.5, 59.4, C.mint, "SmoothPlastic"),
	B("SideBaseL", -29.34, 0.35, 0.3, 0.12, 0.7, 59.4, C.mintDark, "SmoothPlastic"),
	B("SideBaseR", 29.34, 0.35, 0.3, 0.12, 0.7, 59.4, C.mintDark, "SmoothPlastic"),
	B("SideCapL", -29.7, 5.65, 0.3, 0.9, 0.3, 59.4, C.mintDark, "Metal"),
	B("SideCapR", 29.7, 5.65, 0.3, 0.9, 0.3, 59.4, C.mintDark, "Metal"),
	B("PostBackL", -29.7, 6, -29.7, 0.9, 12, 0.9, C.steelDark, "Metal"),
	B("PostBackR", 29.7, 6, -29.7, 0.9, 12, 0.9, C.steelDark, "Metal"),
	B("PostFrontL", -29.7, 2.95, 29.55, 0.9, 5.9, 0.9, C.steelDark, "Metal"),
	B("PostFrontR", 29.7, 2.95, 29.55, 0.9, 5.9, 0.9, C.steelDark, "Metal"),
	-- The new sectional door (x -7..7): dark frame, four panels, a smoked glass band, a mint stripe
	B("DoorFrameL", -7.3, 5, -29.2, 0.6, 10, 0.5, C.mintDark, "Metal"),
	B("DoorFrameR", 7.3, 5, -29.2, 0.6, 10, 0.5, C.mintDark, "Metal"),
	B("DoorHeader", 0, 10.4, -29.2, 15.2, 0.8, 0.5, C.mintDark, "Metal"),
	B("DoorPanel1", 0, 1.2, -29.2, 14, 2.4, 0.25, C.doorLight, "SmoothPlastic"),
	B("DoorPanel2", 0, 3.6, -29.2, 14, 2.4, 0.25, C.doorGray, "SmoothPlastic"),
	B("DoorPanel3", 0, 6, -29.2, 14, 2.4, 0.25, C.doorLight, "SmoothPlastic"),
	B("DoorPanel4", 0, 8.4, -29.2, 14, 2.4, 0.25, C.doorGray, "SmoothPlastic"),
	B("DoorGlassBand", 0, 6, -29.02, 12.6, 1.2, 0.1, C.glassDark, "Glass", { transparency = 0.2, shadow = false }),
	B("DoorStripe", 0, 2.4, -29.05, 14, 0.25, 0.05, C.mint, "SmoothPlastic"),
	-- Two clean windows in the gaps between the incubators
	B("WindowFrameL", -18, 7, -29.27, 6.8, 4.4, 0.25, C.offwhite, "SmoothPlastic"),
	B("WindowGlassL", -18, 7, -29.1, 6, 3.6, 0.1, C.skyGlass, "Glass", { transparency = 0.25, shadow = false }),
	B("WindowBarL", -18, 7, -29.04, 0.25, 3.6, 0.06, C.offwhite, "SmoothPlastic"),
	B("WindowFrameR", 18, 7, -29.27, 6.8, 4.4, 0.25, C.offwhite, "SmoothPlastic"),
	B("WindowGlassR", 18, 7, -29.1, 6, 3.6, 0.1, C.skyGlass, "Glass", { transparency = 0.25, shadow = false }),
	B("WindowBarR", 18, 7, -29.04, 0.25, 3.6, 0.06, C.offwhite, "SmoothPlastic"),
}

-- String lights: a cord under the cap on each side of the door, warm bulbs hanging from it
local function stringLights()
	local out = {
		B("StringCordL", -18, 11.1, -29.3, 20, 0.08, 0.3, C.cord, "SmoothPlastic"),
		B("StringCordR", 18, 11.1, -29.3, 20, 0.08, 0.3, C.cord, "SmoothPlastic"),
	}
	for i = 0, 5 do
		for _, side in ipairs({ { "L", -1 }, { "R", 1 } }) do
			local x = side[2] * (9.5 + i * 3.6)
			local extra = nil
			if i == 2 then
				extra = { light = { color = C.warmLight, brightness = 1.4, range = 34 } }
			end
			table.insert(out, P("StringBulb" .. side[1] .. i, "Ball", { 0.55, 0.55, 0.55 }, { x, 10.8, -29.2 }, C.bulb, "Neon", extra))
		end
	end
	return out
end

seed.decor = join(
	stringLights(),
	{
		B("DoorSign", 0, 11.2, -29.28, 6.4, 0.8, 0.2, C.mintDark, "SmoothPlastic",
			{ text = { value = "OFFICE", font = "FredokaOne", color = C.offwhite } }),
		-- The front-left corner: a rug, a coral sofa against the wall, a coffee table, a plant and a floor lamp
		B("RugBase", -20.8, 0.03, 24, 9, 0.06, 7, C.rugTeal, "Fabric"),
		B("RugInner", -20.8, 0.05, 24, 7.6, 0.1, 5.6, C.cream, "Fabric"),
		B("TableTop", -22.2, 1.35, 24, 2.4, 0.2, 2.4, C.oak, "Wood"),
		B("TableBase", -22.2, 0.625, 24, 1.6, 1.25, 1.6, C.oakDark, "Wood"),
		B("FloorLampPole", -27.8, 2.2, 20.4, 0.2, 4.4, 0.2, C.steelDark, "Metal"),
		B("FloorLampShade", -27.8, 4.8, 20.4, 1.2, 0.9, 1.2, C.bulb, "Neon", { light = { color = C.warmLight, brightness = 1.2, range = 26 } }),
	},
	sofaLeft("Sofa", -28.1, 24, C.coral, C.coralLight),
	plant("CornerPlant", -27.6, 28.4, { 1.2, 1.1 }, 2.6, C.pot, C.leaf),
	plant("GapPlantL", -6, -26.5, { 1.6, 1.4 }, 3, C.pot, C.leaf),
	plant("GapPlantR", 6, -26.5, { 1.6, 1.4 }, 3, C.pot, C.leaf),
	founderDesk(10.5, 24.5, { top = C.oak, panel = C.mintDark, accent = C.screenBlue })
)

-- A hire's desk (zone: 3.8 wide, 1.8 deep, 3 high): a light oak top on two dark legs and a monitor
-- whose screen faces the hire
seed.desk = {
	B("DeskTop", 0, 1.92, 0, 3.6, 0.16, 1.7, C.oak, "Wood"),
	B("DeskLegL", -1.65, 0.92, 0, 0.2, 1.84, 1.5, C.mintDark, "Metal"),
	B("DeskLegR", 1.65, 0.92, 0, 0.2, 1.84, 1.5, C.mintDark, "Metal"),
	B("MonitorFrame", 0, 2.42, 0.1, 1.4, 0.84, 0.1, C.black, "SmoothPlastic"),
	B("MonitorScreen", 0, 2.42, -0.0, 1.2, 0.64, 0.04, C.screenBlue, "Neon"),
}

-- Stage 3: the expanded garage-office (Series A) ----------------------------------------
-- The loft: red brick walls with black steel trim, a second bay (two roll-up doors) with glass partitions
-- around the outer incubators, a whiteboard wall over the middle, warm wall lamps, filing cabinets and
-- a charcoal sofa. Still open to the camera: low side walls, no roof, no front wall.

local seriesA = { key = "SeriesA", floor = { color = { 172, 176, 178 }, material = "Concrete" } }

-- One roll-up bay door in the back wall, centered at x, its shutter half rolled up
local function bayDoor(tag, x)
	return {
		B("Bay" .. tag .. "Dark", x, 4.4, -29.3, 10.4, 8.8, 0.1, C.bayDark, "SmoothPlastic"),
		B("Bay" .. tag .. "FrameL", x - 5.45, 4.6, -29.15, 0.5, 9.2, 0.5, C.steelBlack, "Metal"),
		B("Bay" .. tag .. "FrameR", x + 5.45, 4.6, -29.15, 0.5, 9.2, 0.5, C.steelBlack, "Metal"),
		B("Bay" .. tag .. "Header", x, 9.15, -29.15, 11.4, 0.7, 0.5, C.steelBlack, "Metal"),
		B("Bay" .. tag .. "Shutter", x, 7.4, -29.15, 10.4, 2.8, 0.25, C.shutter, "Metal"),
	}
end

-- A glass partition standing in the gap between two incubators, from the back wall toward the front
local function partition(tag, x)
	return {
		B("Partition" .. tag .. "Glass", x, 2.7, -23.9, 0.1, 5.4, 10.6, C.glassTint, "Glass", { transparency = 0.55 }),
		B("Partition" .. tag .. "Rail", x, 5.55, -23.9, 0.25, 0.3, 10.6, C.steelBlack, "Metal"),
		B("Partition" .. tag .. "PostFront", x, 2.85, -18.75, 0.3, 5.7, 0.3, C.steelBlack, "Metal"),
		B("Partition" .. tag .. "PostMid", x, 2.85, -24, 0.3, 5.7, 0.3, C.steelBlack, "Metal"),
	}
end

-- A warm wall lamp on an arm: arm, shade, glowing bulb (the bulb carries the PointLight)
local function wallLamp(tag, x)
	return {
		B("WallLampArm" .. tag, x, 10.8, -28.7, 0.2, 0.2, 1.4, C.steelBlack, "Metal"),
		B("WallLampShade" .. tag, x, 10.55, -28.1, 1.1, 0.5, 1.1, C.steelBlack, "Metal"),
		P("WallLampBulb" .. tag, "Ball", { 0.6, 0.6, 0.6 }, { x, 10.0, -28.1 }, C.bulb, "Neon",
			{ light = { color = C.warmLight, brightness = 1.3, range = 36 } }),
	}
end

local function whiteboardWall()
	local out = {
		B("WallBoard", 0, 7.6, -29.3, 15.6, 4.4, 0.12, C.white, "SmoothPlastic"),
		B("WallBoardTop", 0, 9.9, -29.25, 15.9, 0.25, 0.2, C.steelBlack, "Metal"),
		B("WallBoardBottom", 0, 5.4, -29.25, 15.9, 0.25, 0.2, C.steelBlack, "Metal"),
		B("WallBoardTray", 0, 5.2, -29.1, 9, 0.15, 0.4, C.silver, "Metal"),
		B("WallBoardArrow", -2.4, 7.4, -29.2, 7, 0.22, 0.04, C.amber, "SmoothPlastic"),
	}
	local notes = { { -6.2, 8.6, C.sticky }, { -4.6, 8.9, C.stickyPink }, { 4.4, 8.7, C.stickyGreen }, { 6, 8.3, C.sticky }, { 3, 6.2, C.stickyPink } }
	for i, n in ipairs(notes) do
		table.insert(out, B("WallNote" .. i, n[1], n[2], -29.2, 0.9, 0.9, 0.04, n[3], "SmoothPlastic"))
	end
	return out
end

seriesA.shell = join(
	{
		B("BackWall", 0, 5.8, -29.7, 60, 11.6, 0.6, C.brick, "Brick"),
		B("BackBase", 0, 0.35, -29.34, 60, 0.7, 0.12, C.steelBlack, "Metal"),
		B("BackCap", 0, 11.8, -29.7, 60, 0.4, 0.9, C.steelBlack, "Metal"),
		B("SideWallL", -29.7, 2.75, 0.3, 0.6, 5.5, 59.4, C.brickLight, "Brick"),
		B("SideWallR", 29.7, 2.75, 0.3, 0.6, 5.5, 59.4, C.brickLight, "Brick"),
		B("SideBaseL", -29.34, 0.35, 0.3, 0.12, 0.7, 59.4, C.steelBlack, "Metal"),
		B("SideBaseR", 29.34, 0.35, 0.3, 0.12, 0.7, 59.4, C.steelBlack, "Metal"),
		B("SideCapL", -29.7, 5.65, 0.3, 0.9, 0.3, 59.4, C.steelBlack, "Metal"),
		B("SideCapR", 29.7, 5.65, 0.3, 0.9, 0.3, 59.4, C.steelBlack, "Metal"),
		B("PostBackL", -29.7, 6, -29.7, 0.9, 12, 0.9, C.steelBlack, "Metal"),
		B("PostBackR", 29.7, 6, -29.7, 0.9, 12, 0.9, C.steelBlack, "Metal"),
		B("PostFrontL", -29.7, 2.95, 29.55, 0.9, 5.9, 0.9, C.steelBlack, "Metal"),
		B("PostFrontR", 29.7, 2.95, 29.55, 0.9, 5.9, 0.9, C.steelBlack, "Metal"),
	},
	bayDoor("L", -14.5),
	bayDoor("R", 14.5),
	whiteboardWall(),
	partition("L", -18),
	partition("R", 18)
)

seriesA.decor = join(
	wallLamp("L", -22),
	wallLamp("M", 0),
	wallLamp("R", 22),
	{
		-- Safety lines of the second bay, painted on the floor under the partitions
		B("BayLineL", -18, 0.03, -23.9, 0.4, 0.06, 10.6, C.amber, "SmoothPlastic"),
		B("BayLineR", 18, 0.03, -23.9, 0.4, 0.06, 10.6, C.amber, "SmoothPlastic"),
		-- Two filing cabinets in the gap left of the middle incubator
		B("CabinetA", -7.2, 2, -27.4, 2, 4, 1.6, C.grayLight, "Metal"),
		B("CabinetB", -4.8, 2, -27.4, 2, 4, 1.6, C.grayLight, "Metal"),
		B("CabinetTop", -6, 4.05, -27.4, 4.2, 0.12, 1.7, C.steelBlack, "Metal"),
		-- The front-left corner: a rug, a charcoal sofa, a table, a plant and a floor lamp
		B("RugBase", -20.8, 0.03, 24, 9, 0.06, 7, C.steelBlack, "Fabric"),
		B("RugInner", -20.8, 0.05, 24, 7.6, 0.1, 5.6, C.amber, "Fabric"),
		B("TableTop", -22.2, 1.35, 24, 2.4, 0.2, 2.4, C.birch, "Wood"),
		B("TableBase", -22.2, 0.625, 24, 1.6, 1.25, 1.6, C.steelBlack, "Metal"),
		B("FloorLampPole", -27.8, 2.2, 20.4, 0.2, 4.4, 0.2, C.steelBlack, "Metal"),
		B("FloorLampShade", -27.8, 4.8, 20.4, 1.2, 0.9, 1.2, C.bulb, "SmoothPlastic"),
	},
	sofaLeft("Sofa", -28.1, 24, C.sofaBlue, C.sofaBlueLight),
	plant("CornerPlant", -27.6, 28.4, { 1.2, 1.1 }, 2.6, C.steelBlack, C.leaf),
	plant("GapPlant", 6, -26.5, { 1.6, 1.4 }, 3, C.steelBlack, C.leaf),
	founderDesk(10.5, 24.5, { top = C.birch, panel = C.steelBlack, accent = C.screenBlue })
)

-- A hire's desk: a birch top on two black steel legs and a monitor (screen toward the hire)
seriesA.desk = {
	B("DeskTop", 0, 1.92, 0, 3.6, 0.16, 1.7, C.birch, "Wood"),
	B("DeskLegL", -1.65, 0.92, 0, 0.2, 1.84, 1.5, C.steelBlack, "Metal"),
	B("DeskLegR", 1.65, 0.92, 0, 0.2, 1.84, 1.5, C.steelBlack, "Metal"),
	B("MonitorFrame", 0, 2.42, 0.1, 1.4, 0.84, 0.1, C.black, "SmoothPlastic"),
	B("MonitorScreen", 0, 2.42, 0, 1.2, 0.64, 0.04, C.screenBlue, "Neon"),
}

-- Stage 4: the real office (Series B) -----------------------------------------------------
-- Blue-gray carpet tiles, white walls with a ribbon of windows along the back, glass walls on the two
-- sides (low, the camera looks in over them), a glass-walled meeting room in the front-left corner,
-- big plants and a reception desk. Open at the front, no roof.

local seriesB = { key = "SeriesB", floor = { color = { 104, 118, 138 }, material = "Fabric" } }

local function sideWall(tag, x, glassX)
	local out = {
		B("SideBase" .. tag, x, 0.6, 0.3, 0.6, 1.2, 59.4, C.officeWhite, "SmoothPlastic"),
		B("SideGlass" .. tag, x, 3.15, 0.3, 0.2, 3.9, 59.4, C.officeGlass, "Glass", { transparency = 0.4, shadow = false }),
		B("SideRail" .. tag, x, 5.275, 0.3, 0.7, 0.35, 59.4, C.navy, "Metal"),
	}
	for i, z in ipairs({ -19.7, 0.3, 20.3 }) do
		table.insert(out, B("SideMullion" .. tag .. i, x, 3.15, z, 0.4, 3.9, 0.4, C.navy, "Metal"))
	end
	return out
end

seriesB.shell = join(
	{
		-- The back wall: white below, a ribbon of glass in navy mullions, a white band on top
		B("BackLower", 0, 3.1, -29.7, 60, 6.2, 0.6, C.officeWhite, "SmoothPlastic"),
		B("BackBase", 0, 0.35, -29.34, 60, 0.7, 0.12, C.navy, "SmoothPlastic"),
		B("BackAccent", 0, 5.7, -29.34, 60, 0.5, 0.12, C.cobalt, "SmoothPlastic"),
		B("BackGlass", 0, 7.8, -29.7, 60, 3.2, 0.2, C.officeGlass, "Glass", { transparency = 0.35, shadow = false }),
		B("BackUpper", 0, 10.5, -29.7, 60, 2.2, 0.6, C.officeWhite, "SmoothPlastic"),
		B("BackCap", 0, 11.8, -29.7, 60, 0.4, 0.9, C.navy, "Metal"),
		B("BackSill", 0, 6.3, -29.55, 60, 0.25, 0.7, C.navy, "Metal"),
		B("BackHead", 0, 9.45, -29.55, 60, 0.25, 0.7, C.navy, "Metal"),
		B("PostBackL", -29.7, 6, -29.7, 0.9, 12, 0.9, C.navy, "Metal"),
		B("PostBackR", 29.7, 6, -29.7, 0.9, 12, 0.9, C.navy, "Metal"),
		B("PostFrontL", -29.7, 2.95, 29.55, 0.9, 5.9, 0.9, C.navy, "Metal"),
		B("PostFrontR", 29.7, 2.95, 29.55, 0.9, 5.9, 0.9, C.navy, "Metal"),
	},
	(function()
		local out = {}
		for i, x in ipairs({ -24, -12, 0, 12, 24 }) do
			table.insert(out, B("BackMullion" .. i, x, 7.8, -29.55, 0.4, 3.2, 0.5, C.navy, "Metal"))
		end
		return out
	end)(),
	sideWall("L", -29.7),
	sideWall("R", 29.7)
)

-- A floor lamp: a pole and a glowing shade (the shade carries a PointLight)
local function floorLamp(tag, x, z)
	return {
		B("FloorLampPole" .. tag, x, 2.2, z, 0.2, 4.4, 0.2, C.navy, "Metal"),
		B("FloorLampShade" .. tag, x, 4.8, z, 1.2, 0.9, 1.2, C.bulb, "Neon", { light = { color = C.warmLight, brightness = 1.1, range = 28 } }),
	}
end

local function carpetTiles()
	local out = {}
	for i, v in ipairs({ -20, -10, 0, 10, 20 }) do
		table.insert(out, B("FloorTileX" .. i, v, 0.02, -4.25, 0.14, 0.04, 51.5, C.carpetLine, "Fabric")) -- stops short of the signs
		table.insert(out, B("FloorTileZ" .. i, 0, 0.02, v, 60, 0.04, 0.14, C.carpetLine, "Fabric"))
	end
	return out
end

local function meetingRoom()
	local out = {
		-- Glass on the back and the right, open to the front and the left wall
		B("MeetGlassBack", -19, 2.3, 19.6, 20, 4.6, 0.1, C.officeGlass, "Glass", { transparency = 0.45, shadow = false }),
		B("MeetGlassSide", -9, 2.3, 24.5, 0.1, 4.6, 9.8, C.officeGlass, "Glass", { transparency = 0.45, shadow = false }),
		B("MeetRailBack", -19, 4.7, 19.6, 20, 0.25, 0.3, C.navy, "Metal"),
		B("MeetRailSide", -9, 4.7, 24.5, 0.3, 0.25, 9.8, C.navy, "Metal"),
		B("MeetPost", -9, 2.35, 19.6, 0.4, 4.7, 0.4, C.navy, "Metal"),
		-- The table on two pedestals, four chairs (a block seat and a back), the wall screen
		B("MeetTableTop", -18.8, 2.4, 25, 8, 0.25, 3.4, C.officeWhite, "SmoothPlastic"),
		B("MeetPedestalA", -20.8, 1.15, 25, 1.2, 2.3, 1.6, C.navy, "Metal"),
		B("MeetPedestalB", -16.8, 1.15, 25, 1.2, 2.3, 1.6, C.navy, "Metal"),
		B("MeetScreen", -29.2, 3.8, 24.8, 0.12, 2.2, 3.6, C.cobalt, "Neon"),
		B("MeetScreenFrame", -29.25, 3.8, 24.8, 0.1, 2.5, 3.9, C.black, "SmoothPlastic"),
	}
	for i, x in ipairs({ -20.4, -17.2 }) do
		table.insert(out, B("MeetChairA" .. i, x, 0.75, 22.7, 1.4, 1.5, 1.4, C.cobalt, "Fabric"))
		table.insert(out, B("MeetChairBackA" .. i, x, 2.2, 22.15, 1.4, 1.4, 0.25, C.navy, "Fabric"))
		table.insert(out, B("MeetChairB" .. i, x, 0.75, 27.3, 1.4, 1.5, 1.4, C.cobalt, "Fabric"))
		table.insert(out, B("MeetChairBackB" .. i, x, 2.2, 27.85, 1.4, 1.4, 0.25, C.navy, "Fabric"))
	end
	return out
end

seriesB.decor = join(
	carpetTiles(),
	meetingRoom(),
	floorLamp("A", -9.8, 28.6),
	floorLamp("B", 15.6, 21.2),
	floorLamp("C", 27.6, 19.8),
	plant("GapPlantL", -6, -26.5, { 1.6, 1.4 }, 3, C.navy, C.leaf),
	plant("GapPlantR", 6, -26.5, { 1.6, 1.4 }, 3, C.navy, C.leaf),
	plant("CornerPlant", 27.6, 27.8, { 1.4, 1.3 }, 3, C.navy, C.leaf),
	founderDesk(10.5, 24.5, { top = C.officeWhite, panel = C.navy, accent = C.screenBlue })
)

-- A hire's desk: a white top on two navy legs and a monitor
seriesB.desk = {
	B("DeskTop", 0, 1.92, 0, 3.6, 0.16, 1.7, C.officeWhite, "SmoothPlastic"),
	B("DeskLegL", -1.65, 0.92, 0, 0.2, 1.84, 1.5, C.navy, "Metal"),
	B("DeskLegR", 1.65, 0.92, 0, 0.2, 1.84, 1.5, C.navy, "Metal"),
	B("MonitorFrame", 0, 2.42, 0.1, 1.4, 0.84, 0.1, C.black, "SmoothPlastic"),
	B("MonitorScreen", 0, 2.42, 0, 1.2, 0.64, 0.04, C.cobalt, "Neon"),
}

-- Stage 5: the headquarters (IPO-ready) ----------------------------------------------------
-- A polished light floor, big windows along the back with a simple block skyline behind them, a graphite
-- logo wall with a neon rim in the middle, a trophy shelf and a lounge in the front-left corner and a
-- reception desk. Low glass-topped side walls, open front, no roof: the full building comes later.

local ipoReady = { key = "IpoReady", floor = { color = { 228, 230, 232 }, material = "SmoothPlastic" } }

local function hqSide(tag, x)
	return {
		B("SideBase" .. tag, x, 1.2, 0.3, 0.6, 2.4, 59.4, C.hqWhite, "SmoothPlastic"),
		B("SideGlass" .. tag, x, 3.9, 0.3, 0.2, 3, 59.4, C.officeGlass, "Glass", { transparency = 0.4, shadow = false }),
		B("SideRail" .. tag, x, 5.55, 0.3, 0.7, 0.3, 59.4, C.graphite, "Metal"),
	}
end

-- The skyline stands behind the back wall (z -46, 3 to 6 studs deep), on the ground, inside the plot's width
local function skyline()
	local towers = { -- x, width, height, color
		{ -26, 6, 18, C.skyA }, { -19.5, 5, 26, C.skyB }, { -13, 6, 21, C.skyC }, { -6.5, 5, 29, C.skyA }, { 0, 6, 17, C.skyB },
		{ 6.5, 5, 24, C.skyC }, { 13, 6, 28, C.skyA }, { 19.5, 5, 20, C.skyB }, { 26, 6, 25, C.skyC },
	}
	local out = {}
	for i, tower in ipairs(towers) do
		table.insert(out, B("Skyline" .. i, tower[1], -1 + tower[3] / 2, -46, tower[2], tower[3], 6, tower[4], "Concrete"))
	end
	return out
end

ipoReady.shell = join(
	{
		B("BackLower", 0, 1.6, -29.7, 60, 3.2, 0.6, C.hqWhite, "SmoothPlastic"),
		B("BackSill", 0, 3.35, -29.55, 60, 0.3, 0.7, C.graphite, "Metal"),
		B("BackHead", 0, 11.35, -29.55, 60, 0.5, 0.7, C.graphite, "Metal"),
		B("BackCap", 0, 11.8, -29.7, 60, 0.4, 0.9, C.graphite, "Metal"),
		-- Four big panes and the mullions between them
		B("WindowA", -24.5, 7.4, -29.7, 9.8, 7.7, 0.2, C.skyGlass, "Glass", { transparency = 0.3, shadow = false }),
		B("WindowB", -13.9, 7.4, -29.7, 9.8, 7.7, 0.2, C.skyGlass, "Glass", { transparency = 0.3, shadow = false }),
		B("WindowC", 13.9, 7.4, -29.7, 9.8, 7.7, 0.2, C.skyGlass, "Glass", { transparency = 0.3, shadow = false }),
		B("WindowD", 24.5, 7.4, -29.7, 9.8, 7.7, 0.2, C.skyGlass, "Glass", { transparency = 0.3, shadow = false }),
		B("MullionL", -19.2, 7.4, -29.55, 0.8, 7.7, 0.5, C.graphite, "Metal"),
		B("MullionR", 19.2, 7.4, -29.55, 0.8, 7.7, 0.5, C.graphite, "Metal"),
		-- The logo wall in the middle: graphite, a neon rim, the company sign
		B("LogoWall", 0, 7.4, -29.7, 18, 7.7, 0.6, C.graphite, "SmoothPlastic"),
		B("LogoWallGlow", 0, 7.4, -29.33, 17.2, 7.2, 0.1, C.neonBlue, "Neon", { light = { color = C.neonBlue, brightness = 1.2, range = 40 } }),
		B("LogoWallSign", 0, 7.4, -29.25, 16.6, 6.6, 0.2, C.navyDark, "SmoothPlastic",
			{ text = { value = "HQ", font = "LuckiestGuy", color = C.neonBlue, glow = true, area = { 0.3, 0.1, 0.4, 0.55 } } }),
		B("LogoWallTagline", 0, 5.1, -29.12, 11, 1, 0.04, C.navyDark, "SmoothPlastic",
			{ text = { value = "BUILD YOUR STARTUP", font = "GothamBold", color = C.rocketWhite, glow = true } }),
		B("LogoWallUnderline", 0, 4.4, -29.11, 12, 0.14, 0.05, C.neonBlue, "Neon"),
		B("PostBackL", -29.7, 6, -29.7, 0.9, 12, 0.9, C.graphite, "Metal"),
		B("PostBackR", 29.7, 6, -29.7, 0.9, 12, 0.9, C.graphite, "Metal"),
		B("PostFrontL", -29.7, 2.95, 29.55, 0.9, 5.9, 0.9, C.graphite, "Metal"),
		B("PostFrontR", 29.7, 2.95, 29.55, 0.9, 5.9, 0.9, C.graphite, "Metal"),
	},
	hqSide("L", -29.7),
	hqSide("R", 29.7),
	skyline()
)

-- The trophy shelf against the left wall (faces +X): a back panel, two ends, three shelves, gold cups
local function trophyShelf(x, z)
	local out = {
		B("ShelfBack", x - 0.55, 3, z, 0.3, 6, 5, C.graphite, "SmoothPlastic"),
		B("ShelfEndN", x, 3, z - 2.35, 1.4, 6, 0.3, C.graphite, "SmoothPlastic"),
		B("ShelfEndS", x, 3, z + 2.35, 1.4, 6, 0.3, C.graphite, "SmoothPlastic"),
	}
	for i, y in ipairs({ 0.4, 2.2, 4 }) do
		table.insert(out, B("ShelfBoard" .. i, x, y, z, 1.4, 0.2, 4.4, C.hqWhite, "SmoothPlastic"))
	end
	local cups = { { 0.5, z - 1.3, 1.1 }, { 0.5, z + 1.2, 0.8 }, { 2.3, z - 0.6, 0.9 }, { 2.3, z + 1.4, 0.7 }, { 4.1, z, 1 } }
	for i, cup in ipairs(cups) do
		table.insert(out, upright("Trophy" .. i, cup[3], 0.6, x, cup[1] - 0.1, cup[2], C.gold, "Metal"))
	end
	return out
end

-- An armchair: a block seat and a back (facing the table)
local function armchair(tag, x, z, backZ)
	return {
		B("Armchair" .. tag, x, 0.8, z, 1.8, 1.6, 1.8, C.graphite, "Fabric"),
		B("ArmchairBack" .. tag, x, 2.2, z + backZ, 1.8, 1.8, 0.4, C.graphite, "Fabric"),
	}
end

ipoReady.decor = join(
	trophyShelf(-28.4, 25),
	{
		-- The lounge rug, a round-edged table and two armchairs facing each other
		B("RugBase", -19.8, 0.03, 24.5, 9, 0.06, 7, C.graphite, "Fabric"),
		B("RugInner", -19.8, 0.05, 24.5, 7.6, 0.1, 5.6, C.rocketWhite, "Fabric"),
		P("LoungeTable", "Cylinder", { 1.2, 2.6, 2.6 }, { -19.8, 0.7, 24.5 }, C.gold, "Metal", { rot = { 0, 0, 90 } }),
		B("FloorLampPoleA", -9.8, 2.2, 28.6, 0.2, 4.4, 0.2, C.graphite, "Metal"),
		B("FloorLampShadeA", -9.8, 4.8, 28.6, 1.2, 0.9, 1.2, C.bulb, "Neon", { light = { color = C.warmLight, brightness = 1.1, range = 28 } }),
		B("FloorLampPoleB", 27.6, 2.2, 19.8, 0.2, 4.4, 0.2, C.graphite, "Metal"),
		B("FloorLampShadeB", 27.6, 4.8, 19.8, 1.2, 0.9, 1.2, C.bulb, "Neon", { light = { color = C.warmLight, brightness = 1.1, range = 28 } }),
	},
	armchair("A", -19.8, 21.6, -0.7),
	armchair("B", -19.8, 27.4, 0.7),
	plant("GapPlantL", -6, -26.5, { 1.6, 1.4 }, 3, C.graphite, C.leaf),
	plant("GapPlantR", 6, -26.5, { 1.6, 1.4 }, 3, C.graphite, C.leaf),
	plant("CornerPlant", 27.6, 27.8, { 1.4, 1.3 }, 3, C.graphite, C.leaf),
	founderDesk(10.5, 24.5, { top = C.hqWhite, panel = C.graphite, accent = C.screenBlue })
)

-- A hire's desk: a glossy white top on two graphite legs, a monitor and a keyboard
ipoReady.desk = {
	B("DeskTop", 0, 1.92, 0, 3.6, 0.16, 1.7, C.hqWhite, "SmoothPlastic"),
	B("DeskLegL", -1.65, 0.92, 0, 0.2, 1.84, 1.5, C.graphite, "Metal"),
	B("DeskLegR", 1.65, 0.92, 0, 0.2, 1.84, 1.5, C.graphite, "Metal"),
	B("MonitorFrame", 0, 2.42, 0.1, 1.4, 0.84, 0.1, C.black, "SmoothPlastic"),
	B("MonitorScreen", 0, 2.42, 0, 1.2, 0.64, 0.04, C.neonBlue, "Neon"),
	B("Keyboard", 0, 2.03, 0.4, 1.3, 0.06, 0.4, C.graphite, "SmoothPlastic"),
}

PlotArt.Stages = { garage, seed, seriesA, seriesB, ipoReady }

-- Upgrade props ----------------------------------------------------------------
-- Each stands in its upgrade's slot (offsets from the slot on the floor), facing the front. Every prop
-- is drawn at its natural size and then made bigger with scaled(): a lighter body against a darker
-- trim, one accent color, and a few small distinct parts so it reads from the default camera. Each
-- stays inside its slot zone (PlotArt.Layout.reserve: 6 studs left and right, 4.5 back, 3.5 front).

local desk = {
	-- Light walnut top and drawer fronts, dark walnut pedestals and lip, gold handles (the accent)
	P("DeskTop", "Block", { 6.2, 0.3, 3 }, { 0, 2.85, 0.4 }, C.walnutLight, "WoodPlanks"),
	P("DeskLip", "Block", { 6.3, 0.3, 0.12 }, { 0, 2.78, 1.96 }, C.walnutDark, "Wood"),
	P("PedestalLeft", "Block", { 1.8, 2.7, 2.7 }, { -2.1, 1.35, 0.4 }, C.walnutDark, "Wood"),
	P("PedestalRight", "Block", { 1.8, 2.7, 2.7 }, { 2.1, 1.35, 0.4 }, C.walnutDark, "Wood"),
	P("DrawerLeftTop", "Block", { 1.5, 0.85, 0.07 }, { -2.1, 2.15, 1.775 }, C.walnutLight, "Wood"),
	P("DrawerLeftLow", "Block", { 1.5, 0.85, 0.07 }, { -2.1, 1.05, 1.775 }, C.walnutLight, "Wood"),
	P("DrawerRightTop", "Block", { 1.5, 0.85, 0.07 }, { 2.1, 2.15, 1.775 }, C.walnutLight, "Wood"),
	P("DrawerRightLow", "Block", { 1.5, 0.85, 0.07 }, { 2.1, 1.05, 1.775 }, C.walnutLight, "Wood"),
	P("HandleLeft", "Block", { 0.7, 0.12, 0.1 }, { -2.1, 2.15, 1.86 }, C.gold, "Metal"),
	P("HandleRight", "Block", { 0.7, 0.12, 0.1 }, { 2.1, 2.15, 1.86 }, C.gold, "Metal"),
	P("ModestyPanel", "Block", { 2.4, 2.1, 0.12 }, { 0, 1.55, -0.85 }, C.walnutDark, "Wood"),
	P("MonitorBase", "Block", { 1, 0.08, 0.7 }, { 0, 3.04, 0.3 }, C.silver, "Metal"),
	P("MonitorNeck", "Block", { 0.25, 0.9, 0.18 }, { 0, 3.53, 0.2 }, C.charcoal, "Metal"),
	P("MonitorFrame", "Block", { 2.6, 1.6, 0.14 }, { 0, 4.3, 0.15 }, C.black, "SmoothPlastic"),
	P("MonitorScreen", "Block", { 2.3, 1.3, 0.05 }, { 0, 4.3, 0.25 }, C.screenBlue, "Neon"),
	P("Keyboard", "Block", { 1.7, 0.1, 0.55 }, { -0.2, 3.05, 1.2 }, C.charcoal, "SmoothPlastic"),
	upright("Mug", 0.55, 0.45, -2.4, 3, 0.9, C.mugWhite, "SmoothPlastic"),
	P("LampBase", "Block", { 0.6, 0.15, 0.6 }, { 2.5, 3.075, -0.5 }, C.brass, "Metal"),
	P("LampPost", "Block", { 0.12, 1.2, 0.12 }, { 2.5, 3.75, -0.5 }, C.brass, "Metal"),
	P("LampShade", "Block", { 0.9, 0.45, 0.6 }, { 2.5, 4.55, -0.35 }, C.lampGlow, "Neon"),
	upright("ChairBase", 0.2, 1.8, 0, 0, -2, C.black, "Metal"),
	upright("ChairPost", 1.3, 0.3, 0, 0.2, -2, C.steel, "Metal"),
	P("ChairSeat", "Block", { 1.8, 0.3, 1.8 }, { 0, 1.65, -2 }, C.black, "Fabric"),
	P("ChairBack", "Block", { 1.8, 2, 0.3 }, { 0, 2.8, -2.75 }, C.black, "Fabric"),
}

local coffee = {
	-- A white counter with a dark top and kick plate, a red espresso machine (the accent) with a dark cap
	P("Counter", "Block", { 3.6, 2.6, 2 }, { 0, 1.3, 0 }, C.white, "SmoothPlastic"),
	P("CounterTop", "Block", { 3.8, 0.2, 2.2 }, { 0, 2.7, 0 }, C.charcoal, "Metal"),
	P("KickPlate", "Block", { 3.4, 0.3, 1.9 }, { 0, 0.15, 0 }, C.charcoal, "Metal"),
	P("DoorSeam", "Block", { 0.06, 2.1, 0.05 }, { 0, 1.4, 1.02 }, C.charcoal, "SmoothPlastic"),
	P("DoorHandleLeft", "Block", { 0.12, 0.5, 0.08 }, { -0.25, 1.6, 1.05 }, C.silver, "Metal"),
	P("DoorHandleRight", "Block", { 0.12, 0.5, 0.08 }, { 0.25, 1.6, 1.05 }, C.silver, "Metal"),
	P("MachineBody", "Block", { 1.9, 1.9, 1.3 }, { -0.5, 3.75, -0.2 }, C.espressoRed, "SmoothPlastic"),
	P("MachineCap", "Block", { 2, 0.2, 1.4 }, { -0.5, 4.8, -0.2 }, C.charcoal, "Metal"),
	P("BeanHopper", "Block", { 0.7, 0.7, 0.7 }, { -0.9, 5.25, -0.35 }, C.coffeeBag, "Plastic"),
	P("ControlPanel", "Block", { 1.5, 0.7, 0.06 }, { -0.5, 4.2, 0.48 }, C.charcoal, "SmoothPlastic"),
	P("PanelLED", "Block", { 0.2, 0.12, 0.04 }, { -0.1, 4.2, 0.53 }, C.ledGreen, "Neon"),
	P("GroupHead", "Block", { 0.6, 0.35, 0.45 }, { -0.5, 3.4, 0.6 }, C.silver, "Metal"),
	P("SteamWand", "Block", { 0.1, 0.9, 0.1 }, { 0.55, 3.25, 0.5 }, C.silver, "Metal"),
	P("DripTray", "Block", { 1.3, 0.12, 0.7 }, { -0.5, 2.86, 0.6 }, C.charcoal, "Metal"),
	P("Cup1", "Cylinder", { 0.4, 0.4, 0.4 }, { -0.5, 3.12, 0.6 }, C.white, "SmoothPlastic", { rot = { 0, 0, 90 }, particles = STEAM }),
	upright("Cup2", 0.4, 0.4, 1.0, 2.8, 0.5, C.white, "SmoothPlastic"),
	P("CoffeeBag", "Block", { 0.6, 0.9, 0.4 }, { 1.35, 3.25, -0.5 }, C.coffeeBag, "Fabric"),
}

local laptop = {
	-- A white standing desk on dark legs with a blue glow strip (the accent), a silver laptop with a dark lid
	P("StandTop", "Block", { 3.6, 0.2, 2.2 }, { 0, 2.5, 0 }, C.white, "SmoothPlastic"),
	P("StandApron", "Block", { 3.4, 0.12, 2 }, { 0, 2.34, 0 }, C.charcoal, "Metal"),
	P("StandLegLeft", "Block", { 0.2, 2.25, 1.9 }, { -1.6, 1.125, 0 }, C.grayLight, "Metal"),
	P("StandLegRight", "Block", { 0.2, 2.25, 1.9 }, { 1.6, 1.125, 0 }, C.grayLight, "Metal"),
	P("StandFootLeft", "Block", { 0.6, 0.12, 2.2 }, { -1.6, 0.06, 0 }, C.charcoal, "Metal"),
	P("StandFootRight", "Block", { 0.6, 0.12, 2.2 }, { 1.6, 0.06, 0 }, C.charcoal, "Metal"),
	P("StandCrossBar", "Block", { 3, 0.15, 0.15 }, { 0, 0.7, -0.6 }, C.charcoal, "Metal"),
	P("StandGlowStrip", "Block", { 3.3, 0.06, 0.06 }, { 0, 2.3, 1.03 }, C.cableBlue, "Neon"),
	P("LaptopBase", "Block", { 1.8, 0.1, 1.2 }, { 0, 2.65, 0.2 }, C.silver, "Metal"),
	P("LaptopKeys", "Block", { 1.5, 0.04, 0.5 }, { 0, 2.72, 0.35 }, C.charcoal, "SmoothPlastic"),
	P("LaptopLid", "Block", { 1.8, 1.2, 0.08 }, { 0, 3.29, -0.5 }, C.charcoal, "Metal", { rot = { -12, 0, 0 } }),
	P("LaptopScreen", "Block", { 1.6, 1, 0.03 }, { 0, 3.3, -0.446 }, C.screenBlue, "Neon", { rot = { -12, 0, 0 } }),
	P("Mouse", "Block", { 0.35, 0.1, 0.5 }, { 1.2, 2.65, 0.5 }, C.charcoal, "SmoothPlastic"),
	P("Phone", "Block", { 0.4, 0.05, 0.75 }, { -1.3, 2.625, 0.5 }, C.black, "SmoothPlastic"),
	upright("Mug", 0.55, 0.45, 1.4, 2.6, -0.5, C.mugWhite, "SmoothPlastic"),
	upright("PlantPot", 0.6, 0.7, -1.3, 2.6, -0.5, C.pot, "SmoothPlastic"),
	P("PlantLeaves", "Ball", { 0.8, 0.8, 0.8 }, { -1.3, 3.5, -0.5 }, C.leaf, "Fabric"),
}

local rack = {
	-- A light gray cabinet between dark top and base plates; four server units with dark vents and
	-- green and cyan LEDs (the accent), a patch panel, cables and a glowing strip
	P("RackBase", "Block", { 3.6, 0.3, 2.8 }, { 0, 0.15, 0 }, C.charcoal, "Metal"),
	P("RackTop", "Block", { 3.6, 0.3, 2.8 }, { 0, 7.65, 0 }, C.charcoal, "Metal"),
	P("RackBack", "Block", { 3.4, 7.2, 0.15 }, { 0, 3.9, -1.2 }, C.charcoal, "Metal"),
	P("RackSideLeft", "Block", { 0.2, 7.2, 2.6 }, { -1.6, 3.9, 0 }, C.grayLight, "Metal"),
	P("RackSideRight", "Block", { 0.2, 7.2, 2.6 }, { 1.6, 3.9, 0 }, C.grayLight, "Metal"),
	P("RackInside", "Block", { 3, 7, 2.2 }, { 0, 3.9, 0 }, C.rack, "Metal"),
	P("Server1", "Block", { 3, 1.1, 0.3 }, { 0, 1.2, 1.2 }, C.grayLight, "DiamondPlate"),
	P("Server2", "Block", { 3, 1.1, 0.3 }, { 0, 2.55, 1.2 }, C.grayLight, "DiamondPlate"),
	P("Server3", "Block", { 3, 1.1, 0.3 }, { 0, 3.9, 1.2 }, C.grayLight, "DiamondPlate"),
	P("Server4", "Block", { 3, 1.1, 0.3 }, { 0, 5.25, 1.2 }, C.grayLight, "DiamondPlate"),
	P("ServerVent1", "Block", { 1.3, 0.5, 0.04 }, { -0.6, 1.2, 1.37 }, C.charcoal, "SmoothPlastic"),
	P("ServerVent2", "Block", { 1.3, 0.5, 0.04 }, { -0.6, 2.55, 1.37 }, C.charcoal, "SmoothPlastic"),
	P("ServerVent3", "Block", { 1.3, 0.5, 0.04 }, { -0.6, 3.9, 1.37 }, C.charcoal, "SmoothPlastic"),
	P("ServerVent4", "Block", { 1.3, 0.5, 0.04 }, { -0.6, 5.25, 1.37 }, C.charcoal, "SmoothPlastic"),
	P("ServerLED1", "Block", { 0.5, 0.16, 0.05 }, { 0.8, 1.2, 1.37 }, C.ledGreen, "Neon"),
	P("ServerLED2", "Block", { 0.5, 0.16, 0.05 }, { 0.8, 2.55, 1.37 }, C.ledCyan, "Neon"),
	P("ServerLED3", "Block", { 0.5, 0.16, 0.05 }, { 0.8, 3.9, 1.37 }, C.ledGreen, "Neon"),
	P("ServerLED4", "Block", { 0.5, 0.16, 0.05 }, { 0.8, 5.25, 1.37 }, C.ledCyan, "Neon"),
	P("PatchPanel", "Block", { 3, 0.7, 0.3 }, { 0, 6.6, 1.2 }, C.charcoal, "Metal"),
	P("PatchPortLEDs", "Block", { 2.4, 0.18, 0.04 }, { 0, 6.6, 1.37 }, C.ledCyan, "Neon"),
	upright("CableBlue", 6.5, 0.25, 1.95, 0.25, -0.6, C.cableBlue, "Plastic"),
	upright("CableRed", 6.5, 0.25, 1.95, 0.25, -0.2, C.cableRed, "Plastic"),
	P("TopFan", "Cylinder", { 0.12, 1.4, 1.4 }, { 0, 7.86, 0 }, C.steelDark, "Metal", { rot = { 0, 0, 90 } }),
	P("FloorGlowStrip", "Block", { 3.2, 0.06, 0.06 }, { 0, 0.35, 1.45 }, C.ledCyan, "Neon"),
}

local whiteboard = {
	-- A white board in a dark frame with a blue chart (the accent), sticky notes, a marker tray and wheeled feet
	P("FrameTop", "Block", { 7.4, 0.25, 0.22 }, { 0, 6.8, 0 }, C.frameDark, "Metal"),
	P("FrameBottom", "Block", { 7.4, 0.25, 0.22 }, { 0, 2.4, 0 }, C.frameDark, "Metal"),
	P("FrameLeft", "Block", { 0.25, 4.65, 0.22 }, { -3.575, 4.6, 0 }, C.frameDark, "Metal"),
	P("FrameRight", "Block", { 0.25, 4.65, 0.22 }, { 3.575, 4.6, 0 }, C.frameDark, "Metal"),
	P("Board", "Block", { 7, 4.2, 0.2 }, { 0, 4.6, 0 }, C.white, "SmoothPlastic",
		{ text = { value = "BIG IDEAS", font = "PermanentMarker", color = C.barBlueDark, area = { 0.05, 0.05, 0.55, 0.3 } } }),
	P("ChartBar1", "Block", { 0.6, 0.8, 0.03 }, { 1.2, 3.4, 0.115 }, C.barBlueLight, "SmoothPlastic"),
	P("ChartBar2", "Block", { 0.6, 1.3, 0.03 }, { 2, 3.65, 0.115 }, C.barBlue, "SmoothPlastic"),
	P("ChartBar3", "Block", { 0.6, 1.9, 0.03 }, { 2.8, 3.95, 0.115 }, C.barBlueDark, "SmoothPlastic"),
	P("StickyYellow", "Block", { 0.7, 0.7, 0.04 }, { -2.8, 4.4, 0.12 }, C.sticky, "SmoothPlastic", { rot = { 0, 0, 6 } }),
	P("StickyPink", "Block", { 0.7, 0.7, 0.04 }, { -1.9, 3.7, 0.12 }, { 255, 170, 190 }, "SmoothPlastic", { rot = { 0, 0, -8 } }),
	P("LegLeft", "Block", { 0.25, 2.4, 0.25 }, { -3.1, 1.2, -0.2 }, C.frameDark, "Metal"),
	P("LegRight", "Block", { 0.25, 2.4, 0.25 }, { 3.1, 1.2, -0.2 }, C.frameDark, "Metal"),
	P("FootLeft", "Block", { 0.4, 0.25, 2.4 }, { -3.1, 0.125, -0.2 }, C.charcoal, "Metal"),
	P("FootRight", "Block", { 0.4, 0.25, 2.4 }, { 3.1, 0.125, -0.2 }, C.charcoal, "Metal"),
	P("BackBrace", "Block", { 6.4, 0.2, 0.2 }, { 0, 2.5, -0.15 }, C.frameDark, "Metal"),
	P("MarkerTray", "Block", { 6, 0.15, 0.45 }, { 0, 2.4, 0.3 }, C.silver, "Metal"),
	P("MarkerRed", "Block", { 0.55, 0.12, 0.12 }, { -1, 2.535, 0.3 }, C.paintRed, "SmoothPlastic"),
	P("MarkerBlue", "Block", { 0.55, 0.12, 0.12 }, { 0.2, 2.535, 0.3 }, C.barBlueDark, "SmoothPlastic"),
	P("Eraser", "Block", { 0.7, 0.2, 0.3 }, { 1.6, 2.575, 0.3 }, C.charcoal, "SmoothPlastic"),
}

local logo = {
	-- A navy board with a neon blue rim (the accent) on dark posts, brackets and caps, with a rocket
	P("SignPostLeft", "Block", { 0.3, 6, 0.3 }, { -4.2, 3, -0.4 }, C.steelDark, "Metal"),
	P("SignPostRight", "Block", { 0.3, 6, 0.3 }, { 4.2, 3, -0.4 }, C.steelDark, "Metal"),
	P("SignFootLeft", "Block", { 0.7, 0.25, 2 }, { -4.2, 0.125, -0.4 }, C.charcoal, "Metal"),
	P("SignFootRight", "Block", { 0.7, 0.25, 2 }, { 4.2, 0.125, -0.4 }, C.charcoal, "Metal"),
	P("SignBracketLeft", "Block", { 0.4, 0.4, 0.9 }, { -4.2, 5.6, -0.15 }, C.charcoal, "Metal"),
	P("SignBracketRight", "Block", { 0.4, 0.4, 0.9 }, { 4.2, 5.6, -0.15 }, C.charcoal, "Metal"),
	P("SignGlow", "Block", { 9.8, 4.6, 0.15 }, { 0, 5.6, -0.33 }, C.neonBlue, "Neon"),
	P("SignBoard", "Block", { 9.4, 4.2, 0.3 }, { 0, 5.6, -0.1 }, C.navyDark, "SmoothPlastic",
		{ text = { value = "STARTUP", font = "LuckiestGuy", color = C.neonBlue, glow = true, area = { 0.3, 0.45, 0.66, 0.38 } } }),
	P("SignCapTop", "Block", { 9.9, 0.25, 0.5 }, { 0, 8, -0.2 }, C.charcoal, "Metal"),
	P("SignCapBottom", "Block", { 9.9, 0.25, 0.5 }, { 0, 3.2, -0.2 }, C.charcoal, "Metal"),
	P("LogoRocket", "Block", { 0.8, 2, 0.1 }, { -3, 6, 0.1 }, C.rocketWhite, "Neon", { rot = { 0, 0, -30 } }),
	P("LogoRocketNose", "Ball", { 0.8, 0.8, 0.8 }, { -2.45, 6.95, 0.1 }, C.neonBlue, "Neon"),
	P("LogoFlame", "Block", { 0.6, 0.6, 0.1 }, { -3.6, 4.96, 0.1 }, C.neonOrange, "Neon", { rot = { 0, 0, 15 } }),
	P("NeonUnderline", "Block", { 6.4, 0.18, 0.08 }, { 1.2, 3.85, 0.09 }, C.neonBlue, "Neon"),
	P("LogoSparkA", "Ball", { 0.3, 0.3, 0.3 }, { -1.2, 6.9, 0.1 }, C.rocketWhite, "Neon"),
	P("LogoSparkB", "Ball", { 0.25, 0.25, 0.25 }, { -0.4, 7.3, 0.1 }, C.neonBlue, "Neon"),
	P("LogoSparkC", "Ball", { 0.3, 0.3, 0.3 }, { -4, 7.4, 0.1 }, C.rocketWhite, "Neon"),
}

PlotArt.Props = {
	["Desk"] = scaled(desk, 1.3),
	["Coffee Machine"] = scaled(coffee, 1.3),
	["Laptop"] = scaled(laptop, 1.5),
	["Server Rack"] = scaled(rack, 1.3),
	["Whiteboard"] = scaled(whiteboard, 1.3),
	["Neon Logo"] = scaled(logo, 1.2),
}

-- The stage-change flash -----------------------------------------------------------
-- A bright see-through box over the whole plot that fades out, with a burst of sparkles.
PlotArt.Flash = {
	seconds = 0.5, steps = 10, linger = 1.6,
	part = P("StageFlash", "Block", { 62, 16, 74 }, { 0, 8, -6 }, { 255, 244, 214 }, "Neon", {
		transparency = 0.55,
		particles = {
			rate = 300, lifetime = { 0.8, 1.4 }, speed = { 2, 6 }, spread = 180, size = { 0.7, 0.2 },
			transparency = { 0, 1 }, color = { { 255, 214, 90 }, { 120, 230, 200 } }, lightEmission = 1,
		},
	}),
}

return PlotArt
