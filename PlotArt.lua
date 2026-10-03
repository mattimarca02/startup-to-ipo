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
--            floor; for a hire desk: from the desk's spot). +X right, +Z front (pads), -Z back.
--   color    { r, g, b } 0-255
--   material Concrete, CorrodedMetal, Metal, DiamondPlate, Wood, WoodPlanks, Brick, Fabric, Plastic,
--            SmoothPlastic, Glass, or Neon (lights and signs only: the name must say Bulb, Lamp,
--            Light, Screen, LED, Sign, Logo, Neon or Glow)
--   extra    rot = { x, y, z } degrees; collide = true (floors only); shadow = false; transparency;
--            light = { color, brightness, range } (a PointLight, at most 3 per plot);
--            text = { value, font, color, face, area, glow } (face "Back" = toward +Z);
--            particles = { ... } (the default emitter: no texture asset)
-- Everything else is decor: anchored, no collision, no touch, no queries.

local PlotArt = {}

-- The layout map -----------------------------------------------------------
-- Where the game's own objects stand, copied from the scripts (tools/daily_test.py checks every
-- number against them). Offsets from the plot's floor-top center, in studs.
PlotArt.Layout = {
	floorSize = { 60, 1, 60 }, -- TycoonCore's "Floor" Part, centered on plotCenter
	floorTop = 0.5, -- its top face, above plotCenter
	padSize = 8,
	pads = {
		{ name = "BuyPad", x = 0, z = 24 }, -- TycoonCore refreshPad
		{ name = "HRPad", x = -21, z = 24 }, -- PoachServer HR_PAD_OFFSET
		{ name = "IpoPad", x = 21, z = 24 }, -- IpoServer PAD_OFFSET
	},
	spawn = { x = 0, z = 12 }, -- TycoonCore teleportToPlot
	itemSlots = { -- TycoonCore itemOffset(i), in UPGRADES order
		{ name = "Desk", x = -18, z = -14 },
		{ name = "Coffee Machine", x = 0, z = -14 },
		{ name = "Laptop", x = 18, z = -14 },
		{ name = "Server Rack", x = -18, z = 2 },
		{ name = "Whiteboard", x = 0, z = 2 },
		{ name = "Neon Logo", x = 18, z = 2 },
	},
	incubators = { { -12, -25 }, { 0, -25 }, { 12, -25 }, { -24, -25 }, { 24, -25 } }, -- EmployeeServer INCUBATOR_SPOTS
	employeeSpots = { -- EmployeeServer EMPLOYEE_SPOTS (a hire strolls up to 3 studs around its spot)
		{ -9, -6 }, { 9, -6 }, { -25, -6 }, { 25, -6 }, { -18, 10 }, { 18, 10 },
		{ -12, 21 }, { 12, 21 }, { -25, 21 }, { 25, 21 }, { 0, -6 },
	},
	-- Each hire's desk: { x, z offset from its spot, turn in degrees }. In front of the hire (+Z),
	-- or beside it for the two spots next to the HR and IPO pads.
	desks = {
		{ 0, 3.3, 0 }, { 0, 3.3, 0 }, { 0, 3.3, 0 }, { 0, 3.3, 0 }, { 0, 3.3, 0 }, { 0, 3.3, 0 },
		{ 0, 3.3, 0 }, { 0, 3.3, 0 }, { -3.3, 0, -90 }, { 3.3, 0, 90 }, { 0, 3.3, 0 },
	},
	-- Reserved zones (PlotVisuals.zones): pads + margin, the spawn and its lane to the green pad,
	-- incubators + the space in front of them, where each hire stands, the upgrade slots, the aisle
	-- in front of the pads. Heights: nothing of the room below these.
	reserve = {
		padMargin = 1, height = 8, spawnHalf = 3, incubatorHalf = 3.5, incubatorFront = 7,
		hireHalf = 1.5, hireHeight = 7, slotHalfX = 5, slotHalfZ = 3.5, slotHeight = 10,
		aisle = { -26, 26, 15, 19 },
	},
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

garage.decor = join({
	-- The bare bulb, hanging from an arm over the door
	P("LampArm", "Block", { 0.3, 0.3, 3.6 }, { -6, 10.6, -27.6 }, C.steel, "Metal"),
	P("LampCord", "Block", { 0.1, 1.2, 0.1 }, { -6, 9.85, -26 }, C.cord, "SmoothPlastic"),
	P("Bulb", "Ball", { 0.7, 0.7, 0.7 }, { -6, 8.9, -26 }, C.bulb, "Neon", { light = { color = C.warmLight, brightness = 2.2, range = 40 } }),
	-- The founder's corner: a wobbly folding table, an old chunky PC and a landline phone
	P("FoldingTable", "Block", { 4.4, 0.2, 2.4 }, { 9, 2.6, 2.2 }, C.tableTop, "Plastic", { rot = { 0, 0, 1.2 } }),
	P("TableLeg1", "Block", { 0.15, 2.5, 0.15 }, { 7, 1.25, 1.2 }, C.steel, "Metal"),
	P("TableLeg2", "Block", { 0.15, 2.5, 0.15 }, { 11, 1.25, 1.2 }, C.steel, "Metal", { rot = { 4, 0, 0 } }),
	P("TableLeg3", "Block", { 0.15, 2.5, 0.15 }, { 7, 1.25, 3.2 }, C.steel, "Metal"),
	P("TableLeg4", "Block", { 0.15, 2.4, 0.15 }, { 11, 1.2, 3.2 }, C.steel, "Metal", { rot = { -3, 0, 2 } }),
	P("ComputerCRT", "Block", { 2, 1.8, 1.8 }, { 8.4, 3.6, 2 }, C.beige, "SmoothPlastic"),
	P("ComputerScreen", "Block", { 1.4, 1.1, 0.06 }, { 8.4, 3.65, 2.93 }, C.crtGreen, "Neon", { light = { color = C.crtGreen, brightness = 0.8, range = 8 } }),
	P("ComputerTower", "Block", { 0.9, 1.9, 1.9 }, { 12, 0.95, 2 }, C.beige, "SmoothPlastic"),
	P("Keyboard", "Block", { 1.6, 0.12, 0.45 }, { 8.4, 2.76, 3.15 }, C.beige, "SmoothPlastic"),
	P("DeskPhone", "Block", { 1, 0.35, 0.8 }, { 10.4, 2.875, 2.3 }, C.phone, "SmoothPlastic"),
	P("DeskPhoneHandset", "Block", { 1.1, 0.22, 0.32 }, { 10.4, 3.16, 2.3 }, C.phoneDark, "SmoothPlastic"),
	upright("Mug", 0.55, 0.45, 7.3, 2.7, 1.5, C.mugRed, "SmoothPlastic"),
	upright("SodaCan1", 0.55, 0.4, 10.6, 2.7, 3.15, C.canRed, "SmoothPlastic"),
	P("StickyNote", "Block", { 0.7, 0.7, 0.04 }, { 9.25, 4.25, 2.985 }, C.sticky, "SmoothPlastic",
		{ rot = { 0, 0, 8 }, text = { value = "WIFI:\nask mom", font = "IndieFlower", color = C.ink } }),
	upright("BucketStool", 1.3, 1.3, 8.6, 0, 5, C.paintBlue, "Plastic"),
	upright("SignBucket", 1.2, 1.1, 11.4, 0, 6.2, C.bucketWhite, "Plastic"),
	P("SignStick", "Block", { 0.18, 4.2, 0.18 }, { 11.4, 2.4, 6.2 }, C.wood, "Wood"),
	P("OfficeSign", "Block", { 3, 1.4, 0.12 }, { 11.4, 3.9, 6.33 }, C.cardboard, "SmoothPlastic",
		{ rot = { 0, 0, -4 }, text = { value = "OFFICE", font = "PermanentMarker", color = C.ink } }),
	-- Dinner and power: pizza boxes, cans, an extension cord with one socket
	P("PizzaBox1", "Block", { 2.2, 0.28, 2.2 }, { 6.5, 0.14, 5.6 }, C.pizza, "SmoothPlastic"),
	P("PizzaBox2", "Block", { 2.2, 0.28, 2.2 }, { 6.6, 0.42, 5.5 }, C.pizza, "SmoothPlastic", { rot = { 0, 10, 0 } }),
	P("PizzaBox3", "Block", { 2.2, 0.28, 2.2 }, { 6.4, 0.7, 5.7 }, C.pizzaDark, "SmoothPlastic", { rot = { 0, -6, 0 } }),
	P("SodaCan2", "Cylinder", { 0.55, 0.4, 0.4 }, { 5.6, 0.2, 7.3 }, C.canGreen, "SmoothPlastic", { rot = { 0, 30, 0 } }),
	upright("SodaCan3", 0.55, 0.4, 8, 0, 7.1, C.canBlue, "SmoothPlastic"),
	P("PowerStrip", "Block", { 1.4, 0.25, 0.5 }, { 12.3, 0.125, 7.4 }, C.bucketWhite, "Plastic"),
	P("PowerSocket", "Block", { 0.32, 0.04, 0.32 }, { 12, 0.27, 7.4 }, C.cord, "SmoothPlastic"),
	P("ExtensionCord", "Block", { 16.5, 0.12, 0.12 }, { 21.15, 0.06, 7.4 }, C.cordOrange, "SmoothPlastic"),
	P("PcCord", "Block", { 0.12, 0.12, 4.45 }, { 12.3, 0.06, 5.175 }, C.cord, "SmoothPlastic"),
	-- The floor: an oil stain and cracks
	P("OilStain1", "Cylinder", { 0.04, 4.6, 4.6 }, { -8.5, 0.02, 7.5 }, C.oil, "SmoothPlastic", { rot = { 0, 0, 90 } }),
	P("OilStain2", "Cylinder", { 0.04, 2.4, 2.4 }, { -6.6, 0.025, 8.8 }, C.oil, "SmoothPlastic", { rot = { 0, 0, 90 } }),
	P("Crack1", "Block", { 5.5, 0.03, 0.14 }, { -14, 0.015, -8.8 }, C.crack, "Concrete", { rot = { 0, 25, 0 } }),
	P("Crack2", "Block", { 4.2, 0.03, 0.12 }, { 5.5, 0.015, -9.2 }, C.crack, "Concrete", { rot = { 0, -35, 0 } }),
	P("Crack3", "Block", { 6, 0.03, 0.14 }, { -20, 0.015, 16.5 }, C.crack, "Concrete", { rot = { 0, 12, 0 } }),
	P("Crack4", "Block", { 4.8, 0.03, 0.12 }, { 14, 0.015, 15.5 }, C.crack, "Concrete", { rot = { 0, 58, 0 } }),
	P("Crack5", "Block", { 3.6, 0.03, 0.12 }, { -5.5, 0.015, -19.5 }, C.crack, "Concrete", { rot = { 0, -15, 0 } }),
	-- Junk between the incubators: tires, paint buckets, boxes, a rusty bike
	upright("Tire1", 0.9, 2.6, -18, 0, -27.4, C.tire, "SmoothPlastic"),
	upright("Tire2", 0.9, 2.6, -18.15, 0.9, -27.3, C.tire, "SmoothPlastic"),
	upright("Tire3", 0.9, 2.6, -17.9, 1.8, -27.5, C.tire, "SmoothPlastic"),
	upright("PaintBucket1", 1.3, 1.1, -7.2, 0, -27.8, C.bucketWhite, "Plastic"),
	upright("PaintBucket2", 1.3, 1.1, -5.5, 0, -28.1, C.paintRed, "Plastic"),
	upright("PaintBucket3", 1.3, 1.1, -7.1, 1.3, -27.85, C.paintBlue, "Plastic"),
	P("Box1", "Block", { 2.2, 1.8, 2 }, { 5.6, 0.9, -27.6 }, C.cardboard, "SmoothPlastic", { rot = { 0, 6, 0 } }),
	P("Box2", "Block", { 1.8, 1.5, 1.8 }, { 6.6, 0.75, -25.1 }, C.cardboardDark, "SmoothPlastic", { rot = { 0, -12, 0 } }),
	P("Box3", "Block", { 1.6, 1.3, 1.5 }, { 5.5, 2.45, -27.5 }, C.cardboard, "SmoothPlastic", { rot = { 0, -10, 0 } }),
	P("BikeWheelBack", "Cylinder", { 0.25, 2.2, 2.2 }, { 19.3, 1.1, -28.55 }, C.tire, "SmoothPlastic", { rot = { 0, 90, 0 } }),
	P("BikeWheelFront", "Cylinder", { 0.25, 2.2, 2.2 }, { 16.7, 1.1, -28.55 }, C.tire, "SmoothPlastic", { rot = { 0, 90, 0 } }),
	P("BikeTopTube", "Block", { 2.5, 0.2, 0.2 }, { 18.05, 2.1, -28.55 }, C.rust, "CorrodedMetal"),
	P("BikeDownTube", "Block", { 1.8, 0.2, 0.2 }, { 17.6, 1.6, -28.55 }, C.rust, "CorrodedMetal", { rot = { 0, 0, -35.5 } }),
	P("BikeFork", "Block", { 0.18, 1.42, 0.18 }, { 16.83, 1.8, -28.55 }, C.rust, "CorrodedMetal", { rot = { 0, 0, -10 } }),
	P("BikeSeat", "Block", { 0.8, 0.22, 0.4 }, { 19, 2.31, -28.55 }, C.tire, "SmoothPlastic"),
	P("BikeHandlebar", "Block", { 0.18, 0.18, 1.2 }, { 16.95, 2.55, -28.55 }, C.steel, "Metal"),
	-- Where the founder sleeps
	P("SleepingBag", "Block", { 1.9, 0.5, 6 }, { -28.3, 0.25, -13.5 }, C.sleepingBag, "Fabric", { rot = { 0, 4, 0 } }),
	P("Pillow", "Block", { 1.5, 0.45, 1 }, { -28.25, 0.725, -16.2 }, C.pillow, "Fabric"),
	-- Trash in the corner
	P("TrashBag1", "Ball", { 1.6, 1.6, 1.6 }, { 27.8, 0.8, 26.5 }, C.trashBag, "SmoothPlastic"),
	P("TrashBag2", "Ball", { 1.2, 1.2, 1.2 }, { 28.4, 0.6, 28.3 }, C.trashBag2, "SmoothPlastic"),
	-- The lot around it: dirt (on the ground, 1 stud under the Floor's top)
	P("DirtFront", "Block", { 26, 0.06, 6 }, { 0, -0.97, 33.2 }, C.dirt, "Concrete"),
	P("DirtBack", "Block", { 16, 0.06, 7 }, { 0, -0.97, -34 }, C.dirt, "Concrete"),
	P("DirtLeft", "Block", { 5, 0.06, 20 }, { -33, -0.97, -4 }, C.dirt, "Concrete"),
	P("DirtRight", "Block", { 5, 0.06, 16 }, { 33, -0.97, 12 }, C.dirt, "Concrete"),
},
	weed("Weed1", -28.9, 0, 8, 20), weed("Weed2", 28.9, 0, -17, -40), weed("Weed3", -15.3, 0, 28.6, 75),
	weed("Weed4", -31.3, -1, 2, 10), weed("Weed5", 31.3, -1, -12, 130), weed("Weed6", 4, -1, -31.5, -20)
)

-- A hire's desk: a crate with a board on it (no tech in the garage)
garage.desk = {
	P("Crate", "Block", { 3.4, 2, 1.5 }, { 0, 1, 0 }, C.crate, "WoodPlanks"),
	P("Board", "Block", { 3.6, 0.15, 1.7 }, { 0, 2.075, 0 }, C.board, "Wood"),
}

PlotArt.Stages = { garage }

-- Upgrade props ----------------------------------------------------------------
-- Each stands in its upgrade's slot (offsets from the slot on the floor), facing the front.

PlotArt.Props = {
	["Desk"] = {
		P("DeskTop", "Block", { 6, 0.3, 3 }, { 0, 2.85, 0.4 }, C.walnut, "WoodPlanks"),
		P("DrawerLeft", "Block", { 1.8, 2.7, 2.8 }, { -2, 1.35, 0.4 }, C.walnutDark, "Wood"),
		P("DrawerRight", "Block", { 1.8, 2.7, 2.8 }, { 2, 1.35, 0.4 }, C.walnutDark, "Wood"),
		P("HandleLeft", "Block", { 0.8, 0.12, 0.1 }, { -2, 2, 1.85 }, C.gold, "Metal"),
		P("HandleRight", "Block", { 0.8, 0.12, 0.1 }, { 2, 2, 1.85 }, C.gold, "Metal"),
		upright("ChairBase", 0.2, 1.8, 0, 0, -2, C.black, "Metal"),
		upright("ChairPost", 1.3, 0.3, 0, 0.2, -2, C.steel, "Metal"),
		P("ChairSeat", "Block", { 1.8, 0.3, 1.8 }, { 0, 1.65, -2 }, C.black, "Fabric"),
		P("ChairBack", "Block", { 1.8, 2, 0.3 }, { 0, 2.8, -2.75 }, C.black, "Fabric"),
		P("LampBase", "Block", { 0.6, 0.15, 0.6 }, { 2.2, 3.075, -0.4 }, C.brass, "Metal"),
		P("LampPost", "Block", { 0.12, 1.2, 0.12 }, { 2.2, 3.75, -0.4 }, C.brass, "Metal"),
		P("LampShade", "Block", { 0.9, 0.45, 0.6 }, { 2.2, 4.55, -0.25 }, C.lampGlow, "Neon"),
		upright("Mug", 0.55, 0.45, -1.6, 3, 0.9, C.mugWhite, "SmoothPlastic"),
	},
	["Coffee Machine"] = {
		P("Counter", "Block", { 3.6, 2.6, 2 }, { 0, 1.3, 0 }, C.white, "SmoothPlastic"),
		P("CounterTop", "Block", { 3.8, 0.2, 2.2 }, { 0, 2.7, 0 }, C.walnut, "Wood"),
		P("MachineBody", "Block", { 1.6, 1.8, 1.3 }, { -0.4, 3.7, -0.2 }, C.espressoRed, "SmoothPlastic"),
		P("MachineTop", "Block", { 1.7, 0.2, 1.4 }, { -0.4, 4.7, -0.2 }, C.silver, "Metal"),
		P("GroupHead", "Block", { 0.5, 0.35, 0.45 }, { -0.4, 3.6, 0.675 }, C.silver, "Metal"),
		P("DripTray", "Block", { 1.1, 0.12, 0.6 }, { -0.4, 2.86, 0.6 }, C.black, "Metal"),
		P("Cup1", "Cylinder", { 0.4, 0.4, 0.4 }, { -0.4, 3.12, 0.6 }, C.white, "SmoothPlastic", { rot = { 0, 0, 90 }, particles = STEAM }),
		upright("Cup2", 0.4, 0.4, 0.9, 2.8, 0.5, C.white, "SmoothPlastic"),
		P("CoffeeBag", "Block", { 0.6, 0.9, 0.4 }, { 1.3, 3.25, -0.5 }, C.coffeeBag, "Fabric"),
	},
	["Laptop"] = {
		P("StandTop", "Block", { 3.6, 0.2, 2.2 }, { 0, 2.5, 0 }, C.white, "SmoothPlastic"),
		P("StandLegLeft", "Block", { 0.2, 2.4, 2 }, { -1.6, 1.2, 0 }, C.silver, "Metal"),
		P("StandLegRight", "Block", { 0.2, 2.4, 2 }, { 1.6, 1.2, 0 }, C.silver, "Metal"),
		P("LaptopBase", "Block", { 1.8, 0.1, 1.2 }, { 0, 2.65, 0.2 }, C.silver, "Metal"),
		P("LaptopLid", "Block", { 1.8, 1.2, 0.08 }, { 0, 3.29, -0.5 }, C.silver, "Metal", { rot = { -12, 0, 0 } }),
		P("LaptopScreen", "Block", { 1.6, 1, 0.03 }, { 0, 3.3, -0.446 }, C.screenBlue, "Neon", { rot = { -12, 0, 0 } }),
		upright("PlantPot", 0.6, 0.7, 1.2, 2.6, -0.5, C.pot, "SmoothPlastic"),
		P("PlantLeaves", "Ball", { 0.8, 0.8, 0.8 }, { 1.2, 3.5, -0.5 }, C.leaf, "Fabric"),
		P("Phone", "Block", { 0.4, 0.05, 0.75 }, { -1.2, 2.625, 0.5 }, C.black, "SmoothPlastic"),
	},
	["Server Rack"] = {
		P("RackFrame", "Block", { 3.4, 7.6, 2.6 }, { 0, 3.8, 0 }, C.rack, "Metal"),
		P("RackTop", "Block", { 3.6, 0.3, 2.8 }, { 0, 7.75, 0 }, C.silver, "Metal"),
		P("Server1", "Block", { 3, 1.2, 0.2 }, { 0, 1.3, 1.4 }, C.serverGray, "DiamondPlate"),
		P("Server2", "Block", { 3, 1.2, 0.2 }, { 0, 2.9, 1.4 }, C.serverGray, "DiamondPlate"),
		P("Server3", "Block", { 3, 1.2, 0.2 }, { 0, 4.5, 1.4 }, C.serverGray, "DiamondPlate"),
		P("Server4", "Block", { 3, 1.2, 0.2 }, { 0, 6.1, 1.4 }, C.serverGray, "DiamondPlate"),
		P("ServerLED1", "Block", { 1.2, 0.18, 0.06 }, { 0.6, 1.3, 1.53 }, C.ledGreen, "Neon"),
		P("ServerLED2", "Block", { 1.2, 0.18, 0.06 }, { 0.6, 2.9, 1.53 }, C.ledCyan, "Neon"),
		P("ServerLED3", "Block", { 1.2, 0.18, 0.06 }, { 0.6, 4.5, 1.53 }, C.ledGreen, "Neon"),
		P("ServerLED4", "Block", { 1.2, 0.18, 0.06 }, { 0.6, 6.1, 1.53 }, C.ledCyan, "Neon"),
		upright("CableBlue", 6.5, 0.25, 1.85, 0.25, -0.6, C.cableBlue, "Plastic"),
		upright("CableRed", 6.5, 0.25, 1.85, 0.25, -0.2, C.cableRed, "Plastic"),
	},
	["Whiteboard"] = {
		P("BoardFrame", "Block", { 7.4, 4.6, 0.12 }, { 0, 4.6, -0.16 }, C.silver, "Metal"),
		P("Board", "Block", { 7, 4.2, 0.2 }, { 0, 4.6, 0 }, C.white, "SmoothPlastic",
			{ text = { value = "BIG IDEAS", font = "PermanentMarker", color = C.inkBlue, area = { 0.05, 0.05, 0.55, 0.3 } } }),
		P("LegLeft", "Block", { 0.25, 6.6, 0.25 }, { -3.75, 3.3, -0.35 }, C.silver, "Metal"),
		P("LegRight", "Block", { 0.25, 6.6, 0.25 }, { 3.75, 3.3, -0.35 }, C.silver, "Metal"),
		P("FootLeft", "Block", { 0.4, 0.25, 2.4 }, { -3.75, 0.125, -0.35 }, C.silver, "Metal"),
		P("FootRight", "Block", { 0.4, 0.25, 2.4 }, { 3.75, 0.125, -0.35 }, C.silver, "Metal"),
		P("MarkerTray", "Block", { 6, 0.15, 0.4 }, { 0, 2.45, 0.25 }, C.silver, "Metal"),
		P("MarkerRed", "Block", { 0.5, 0.12, 0.12 }, { -1, 2.585, 0.25 }, C.paintRed, "SmoothPlastic"),
		P("MarkerBlue", "Block", { 0.5, 0.12, 0.12 }, { 0.2, 2.585, 0.25 }, C.inkBlue, "SmoothPlastic"),
		P("ChartBar1", "Block", { 0.6, 0.8, 0.03 }, { 1.2, 3.4, 0.115 }, C.barBlue, "SmoothPlastic"),
		P("ChartBar2", "Block", { 0.6, 1.3, 0.03 }, { 2, 3.65, 0.115 }, C.barGreen, "SmoothPlastic"),
		P("ChartBar3", "Block", { 0.6, 1.9, 0.03 }, { 2.8, 3.95, 0.115 }, C.barOrange, "SmoothPlastic"),
	},
	["Neon Logo"] = {
		P("SignPostLeft", "Block", { 0.3, 6, 0.3 }, { -4.2, 3, -0.4 }, C.steelDark, "Metal"),
		P("SignPostRight", "Block", { 0.3, 6, 0.3 }, { 4.2, 3, -0.4 }, C.steelDark, "Metal"),
		P("SignFootLeft", "Block", { 0.6, 0.25, 2 }, { -4.2, 0.125, -0.4 }, C.steelDark, "Metal"),
		P("SignFootRight", "Block", { 0.6, 0.25, 2 }, { 4.2, 0.125, -0.4 }, C.steelDark, "Metal"),
		P("SignGlow", "Block", { 9.8, 4.6, 0.15 }, { 0, 5.6, -0.33 }, C.neonBlue, "Neon"),
		P("SignBoard", "Block", { 9.4, 4.2, 0.3 }, { 0, 5.6, -0.1 }, C.navyDark, "SmoothPlastic",
			{ text = { value = "STARTUP", font = "LuckiestGuy", color = C.neonBlue, glow = true, area = { 0.3, 0.45, 0.66, 0.38 } } }),
		P("LogoRocket", "Block", { 0.8, 2, 0.1 }, { -3, 6, 0.1 }, C.neonBlue, "Neon", { rot = { 0, 0, -30 } }),
		P("LogoRocketNose", "Ball", { 0.8, 0.8, 0.8 }, { -2.45, 6.95, 0.1 }, C.neonBlue, "Neon"),
		P("LogoFlame", "Block", { 0.6, 0.6, 0.1 }, { -3.6, 4.96, 0.1 }, C.neonOrange, "Neon", { rot = { 0, 0, 15 } }),
		P("NeonUnderline", "Block", { 6.4, 0.18, 0.08 }, { 1.2, 3.85, 0.09 }, C.neonBlue, "Neon"),
	},
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
