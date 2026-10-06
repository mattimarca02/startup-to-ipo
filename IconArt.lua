-- IconArt: every icon of the game as data (branch world-icons-pass): the six Office upgrades, the recruiting eggs, the
-- creatures, the shop's passes, boosts and Cash packs, and the five HUD buttons. They replace the emoji: no emoji, no
-- image, no asset anywhere. Put this ModuleScript in ReplicatedStorage (the screens build icons with IconVisuals).
--
-- Style sheet (every icon follows it; IconVisuals applies it, tools/icon_test.py checks it):
--   Grid     a UI icon is drawn on a 100 x 100 grid (x, y = a shape's top-left corner) and scaled to its size: 56 px on
--            a card and 72 px on the biggest card and the details sheet, at phone size (Style.sizes)
--   Outline  one dark outline (Palette.outline) around each icon's silhouette, Style.outline grid units wide (2 px at
--            56 px): a shape marked `outline` gets an inflated copy drawn behind every fill, so a figure made of several
--            shapes has one clean outline and no seams
--   Palette  the colors below, by name. The props use PlotArt's own color names and values
--   Shading  light from the top-left for every icon: a shape marked `shade` gets a gradient from its full color (top-left)
--            to Style.shadeDark of it (bottom-right), turned Style.lightRotation degrees; a 3D icon is lit from the same
--            side of the picture (Style.lightDirection, in the camera's frame)
--   Corners  "rect" shapes are rounded by Style.corner (a share of their short side); circles, pills and plates are round
--   Plate    card icons sit on a round outlined plate; HUD icons sit on their button and have none
--   Text     only the short labels in IconArt.Texts. No word about odds, ever; the clover icon has no text at all
--   Motion   none, unless the player taps the icon (IconVisuals.tap: one spin or one pop)
-- 3D icons: the Office upgrades are PlotArt's prop parts (copied here because PlotArt lives on the server where the
-- screens can't read it; tools/icon_test.py fails if a copy differs from PlotArt), the creatures are CreatureModels'
-- own models. A ViewportFrame draws neither text nor particles, so the props' board texts and coffee steam are left out.
--
-- A UI shape: S(kind, name, x, y, w, h, color [, extra])
--   kind   "rect" (rounded), "circle" (w = h), "pill", "diamond" (a square turned 45 degrees), "ring" (a circle's line),
--          "frame" (a rect's line) or "text" (one of IconArt.Texts)
--   extra  outline = true, shade = true, rotation = degrees (clockwise, around the shape's middle), transparency,
--          thickness (a ring's or frame's line, in grid units), text
-- A 3D part: P(name, shape, size, offset, color, material [, extra]) as in PlotArt, with a palette name for the color.

local IconArt = {}

IconArt.Style = {
	grid = 100,
	outline = 4, -- grid units: 2.2 px at 56 px, 2.9 px at 72
	corner = 0.22,
	lightRotation = 45, -- UIGradient.Rotation: from the top-left (full color) to the bottom-right (shaded)
	shadeDark = 0.72, -- the bottom-right of a shaded shape is this share of its color
	lightDirection = { 1, -1, -1 }, -- in the camera's frame: toward the right, down and away, so lit from the top-left
	ambient = { 150, 150, 160 },
	lightColor = { 255, 250, 240 },
	fov = 30, -- degrees, the 3D icons' camera
	padding = 0.1, -- share of the picture left free around a 3D model
	plate = { 4, 4, 92, 92 }, -- the round plate on the grid (with its outline it fills 0-100)
	sizes = { card = 56, hero = 72 }, -- px at phone size
	-- At most this many 3D icons (ViewportFrames) exist at once on the whole client: every window, list and direct
	-- IconVisuals.build together (IconVisuals' one registry enforces it; past it an icon shows its drawn fallback).
	-- A reasoned guess, not measured on a phone (docs/WORLD_ICONS_NOTES.md)
	viewportCap = 8,
	maxParts = 30, -- parts in one 3D icon
	maxShapes = 16, -- shapes in one UI icon (without its plate and outline copies)
}

-- The only words an icon may show
IconArt.Texts = { "2x", "+3", "$" }

-- Palette ---------------------------------------------------------------------------------------------------
IconArt.Palette = {
	-- Style
	outline = { 28, 30, 38 }, shine = { 255, 255, 255 },
	plateCream = { 246, 238, 214 }, plateCommon = { 222, 226, 232 }, plateUncommon = { 196, 236, 196 }, plateRare = { 190, 216, 255 },
	plateEpic = { 222, 196, 255 }, plateLegendary = { 255, 230, 160 },
	-- The props (PlotArt's names and values)
	walnutLight = { 184, 136, 92 }, walnutDark = { 104, 70, 46 }, gold = { 255, 196, 60 }, silver = { 200, 204, 210 },
	charcoal = { 52, 54, 60 }, black = { 32, 32, 36 }, screenBlue = { 130, 190, 255 }, mugWhite = { 240, 240, 236 },
	brass = { 196, 160, 80 }, lampGlow = { 190, 255, 170 }, steel = { 84, 86, 92 }, white = { 246, 246, 242 },
	espressoRed = { 200, 56, 48 }, coffeeBag = { 120, 84, 56 }, ledGreen = { 80, 255, 140 }, grayLight = { 170, 176, 186 },
	cableBlue = { 60, 120, 230 }, pot = { 200, 112, 74 }, leaf = { 86, 168, 86 }, rack = { 40, 42, 48 }, ledCyan = { 80, 220, 255 },
	cableRed = { 220, 70, 60 }, steelDark = { 54, 56, 62 }, frameDark = { 78, 82, 92 }, barBlueLight = { 140, 190, 245 },
	barBlue = { 70, 140, 230 }, barBlueDark = { 40, 96, 190 }, sticky = { 255, 234, 110 }, stickyPink = { 255, 170, 190 },
	paintRed = { 214, 82, 70 }, neonBlue = { 0, 170, 255 }, navyDark = { 26, 34, 60 }, rocketWhite = { 235, 244, 255 },
	neonOrange = { 255, 150, 60 },
	-- Eggs (the body colors are CreatureConfig's egg colors)
	eggGarage = { 165, 120, 75 }, eggGarageSpot = { 222, 190, 144 }, eggStartup = { 60, 150, 255 }, eggStartupSpot = { 196, 226, 255 },
	eggUnicorn = { 255, 120, 210 }, eggUnicornSpot = { 255, 228, 130 }, eggCream = { 246, 226, 180 }, eggCreamSpot = { 232, 160, 90 },
	-- The shop
	goldDark = { 200, 144, 32 }, goldInk = { 112, 72, 20 }, jewelRed = { 222, 60, 72 }, jewelBlue = { 60, 130, 232 },
	jewelGreen = { 56, 182, 100 }, mint = { 170, 226, 204 }, mintDark = { 46, 110, 100 }, green = { 64, 186, 88 },
	targetRed = { 226, 70, 64 }, paper = { 250, 244, 226 }, inkSoft = { 172, 160, 138 }, sealRed = { 204, 56, 56 },
	bill = { 112, 192, 112 }, billDark = { 52, 128, 68 }, billLight = { 172, 224, 162 }, bag = { 214, 176, 120 },
	bagInk = { 96, 64, 36 }, clover = { 82, 188, 92 }, cloverDark = { 44, 132, 64 }, bolt = { 255, 214, 60 },
	shieldBlue = { 70, 130, 222 }, shieldLight = { 152, 198, 246 },
	-- HUD (light icons on the colored buttons)
	hudWhite = { 250, 250, 250 }, hudSoft = { 210, 220, 236 }, hudSpot = { 150, 200, 255 }, hudGold = { 255, 214, 90 },
}

-- Helpers -----------------------------------------------------------------------------------------------------

local function S(kind, name, x, y, w, h, color, extra)
	local shape = extra or {}
	shape.kind, shape.name, shape.x, shape.y, shape.w, shape.h, shape.color = kind, name, x, y, w, h, color
	return shape
end

local function P(name, shape, size, offset, color, material, extra)
	local spec = extra or {}
	spec.name, spec.shape, spec.size, spec.offset, spec.color, spec.material = name, shape, size, offset, color, material
	return spec
end

-- A cylinder standing up (its length is the height), as in PlotArt
local function upright(name, height, diameter, x, y, z, color, material)
	return P(name, "Cylinder", { height, diameter, diameter }, { x, y + height / 2, z }, color, material, { rot = { 0, 0, 90 } })
end

-- An egg: an outlined, shaded oval body with three spots and a shine. x, y = its top-left; w, h = its size
local function egg(x, y, w, h, body, spot)
	return {
		S("pill", "EggBody", x, y, w, h, body, { outline = true, shade = true }),
		S("circle", "EggSpotA", x + w * 0.2, y + h * 0.42, w * 0.2, w * 0.2, spot),
		S("circle", "EggSpotB", x + w * 0.56, y + h * 0.24, w * 0.15, w * 0.15, spot),
		S("circle", "EggSpotC", x + w * 0.5, y + h * 0.62, w * 0.24, w * 0.24, spot),
		S("pill", "EggShine", x + w * 0.2, y + h * 0.1, w * 0.16, h * 0.24, "shine", { rotation = -20, transparency = 0.35 }),
	}
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

-- 3D models: the six upgrade props, PlotArt's parts at their drawn size (PlotArt scales them up for the room) -------
IconArt.Models = {
	["Desk"] = {
		P("DeskTop", "Block", { 6.2, 0.3, 3 }, { 0, 2.85, 0.4 }, "walnutLight", "WoodPlanks"),
		P("DeskLip", "Block", { 6.3, 0.3, 0.12 }, { 0, 2.78, 1.96 }, "walnutDark", "Wood"),
		P("PedestalLeft", "Block", { 1.8, 2.7, 2.7 }, { -2.1, 1.35, 0.4 }, "walnutDark", "Wood"),
		P("PedestalRight", "Block", { 1.8, 2.7, 2.7 }, { 2.1, 1.35, 0.4 }, "walnutDark", "Wood"),
		P("DrawerLeftTop", "Block", { 1.5, 0.85, 0.07 }, { -2.1, 2.15, 1.775 }, "walnutLight", "Wood"),
		P("DrawerLeftLow", "Block", { 1.5, 0.85, 0.07 }, { -2.1, 1.05, 1.775 }, "walnutLight", "Wood"),
		P("DrawerRightTop", "Block", { 1.5, 0.85, 0.07 }, { 2.1, 2.15, 1.775 }, "walnutLight", "Wood"),
		P("DrawerRightLow", "Block", { 1.5, 0.85, 0.07 }, { 2.1, 1.05, 1.775 }, "walnutLight", "Wood"),
		P("HandleLeft", "Block", { 0.7, 0.12, 0.1 }, { -2.1, 2.15, 1.86 }, "gold", "Metal"),
		P("HandleRight", "Block", { 0.7, 0.12, 0.1 }, { 2.1, 2.15, 1.86 }, "gold", "Metal"),
		P("ModestyPanel", "Block", { 2.4, 2.1, 0.12 }, { 0, 1.55, -0.85 }, "walnutDark", "Wood"),
		P("MonitorBase", "Block", { 1, 0.08, 0.7 }, { 0, 3.04, 0.3 }, "silver", "Metal"),
		P("MonitorNeck", "Block", { 0.25, 0.9, 0.18 }, { 0, 3.53, 0.2 }, "charcoal", "Metal"),
		P("MonitorFrame", "Block", { 2.6, 1.6, 0.14 }, { 0, 4.3, 0.15 }, "black", "SmoothPlastic"),
		P("MonitorScreen", "Block", { 2.3, 1.3, 0.05 }, { 0, 4.3, 0.25 }, "screenBlue", "Neon"),
		P("Keyboard", "Block", { 1.7, 0.1, 0.55 }, { -0.2, 3.05, 1.2 }, "charcoal", "SmoothPlastic"),
		upright("Mug", 0.55, 0.45, -2.4, 3, 0.9, "mugWhite", "SmoothPlastic"),
		P("LampBase", "Block", { 0.6, 0.15, 0.6 }, { 2.5, 3.075, -0.5 }, "brass", "Metal"),
		P("LampPost", "Block", { 0.12, 1.2, 0.12 }, { 2.5, 3.75, -0.5 }, "brass", "Metal"),
		P("LampShade", "Block", { 0.9, 0.45, 0.6 }, { 2.5, 4.55, -0.35 }, "lampGlow", "Neon"),
		upright("ChairBase", 0.2, 1.8, 0, 0, -2, "black", "Metal"),
		upright("ChairPost", 1.3, 0.3, 0, 0.2, -2, "steel", "Metal"),
		P("ChairSeat", "Block", { 1.8, 0.3, 1.8 }, { 0, 1.65, -2 }, "black", "Fabric"),
		P("ChairBack", "Block", { 1.8, 2, 0.3 }, { 0, 2.8, -2.75 }, "black", "Fabric"),
	},
	["Coffee Machine"] = {
		P("Counter", "Block", { 3.6, 2.6, 2 }, { 0, 1.3, 0 }, "white", "SmoothPlastic"),
		P("CounterTop", "Block", { 3.8, 0.2, 2.2 }, { 0, 2.7, 0 }, "charcoal", "Metal"),
		P("KickPlate", "Block", { 3.4, 0.3, 1.9 }, { 0, 0.15, 0 }, "charcoal", "Metal"),
		P("DoorSeam", "Block", { 0.06, 2.1, 0.05 }, { 0, 1.4, 1.02 }, "charcoal", "SmoothPlastic"),
		P("DoorHandleLeft", "Block", { 0.12, 0.5, 0.08 }, { -0.25, 1.6, 1.05 }, "silver", "Metal"),
		P("DoorHandleRight", "Block", { 0.12, 0.5, 0.08 }, { 0.25, 1.6, 1.05 }, "silver", "Metal"),
		P("MachineBody", "Block", { 1.9, 1.9, 1.3 }, { -0.5, 3.75, -0.2 }, "espressoRed", "SmoothPlastic"),
		P("MachineCap", "Block", { 2, 0.2, 1.4 }, { -0.5, 4.8, -0.2 }, "charcoal", "Metal"),
		P("BeanHopper", "Block", { 0.7, 0.7, 0.7 }, { -0.9, 5.25, -0.35 }, "coffeeBag", "Plastic"),
		P("ControlPanel", "Block", { 1.5, 0.7, 0.06 }, { -0.5, 4.2, 0.48 }, "charcoal", "SmoothPlastic"),
		P("PanelLED", "Block", { 0.2, 0.12, 0.04 }, { -0.1, 4.2, 0.53 }, "ledGreen", "Neon"),
		P("GroupHead", "Block", { 0.6, 0.35, 0.45 }, { -0.5, 3.4, 0.6 }, "silver", "Metal"),
		P("SteamWand", "Block", { 0.1, 0.9, 0.1 }, { 0.55, 3.25, 0.5 }, "silver", "Metal"),
		P("DripTray", "Block", { 1.3, 0.12, 0.7 }, { -0.5, 2.86, 0.6 }, "charcoal", "Metal"),
		P("Cup1", "Cylinder", { 0.4, 0.4, 0.4 }, { -0.5, 3.12, 0.6 }, "white", "SmoothPlastic", { rot = { 0, 0, 90 } }),
		upright("Cup2", 0.4, 0.4, 1.0, 2.8, 0.5, "white", "SmoothPlastic"),
		P("CoffeeBag", "Block", { 0.6, 0.9, 0.4 }, { 1.35, 3.25, -0.5 }, "coffeeBag", "Fabric"),
	},
	["Laptop"] = {
		P("StandTop", "Block", { 3.6, 0.2, 2.2 }, { 0, 2.5, 0 }, "white", "SmoothPlastic"),
		P("StandApron", "Block", { 3.4, 0.12, 2 }, { 0, 2.34, 0 }, "charcoal", "Metal"),
		P("StandLegLeft", "Block", { 0.2, 2.25, 1.9 }, { -1.6, 1.125, 0 }, "grayLight", "Metal"),
		P("StandLegRight", "Block", { 0.2, 2.25, 1.9 }, { 1.6, 1.125, 0 }, "grayLight", "Metal"),
		P("StandFootLeft", "Block", { 0.6, 0.12, 2.2 }, { -1.6, 0.06, 0 }, "charcoal", "Metal"),
		P("StandFootRight", "Block", { 0.6, 0.12, 2.2 }, { 1.6, 0.06, 0 }, "charcoal", "Metal"),
		P("StandCrossBar", "Block", { 3, 0.15, 0.15 }, { 0, 0.7, -0.6 }, "charcoal", "Metal"),
		P("StandGlowStrip", "Block", { 3.3, 0.06, 0.06 }, { 0, 2.3, 1.03 }, "cableBlue", "Neon"),
		P("LaptopBase", "Block", { 1.8, 0.1, 1.2 }, { 0, 2.65, 0.2 }, "silver", "Metal"),
		P("LaptopKeys", "Block", { 1.5, 0.04, 0.5 }, { 0, 2.72, 0.35 }, "charcoal", "SmoothPlastic"),
		P("LaptopLid", "Block", { 1.8, 1.2, 0.08 }, { 0, 3.29, -0.5 }, "charcoal", "Metal", { rot = { -12, 0, 0 } }),
		P("LaptopScreen", "Block", { 1.6, 1, 0.03 }, { 0, 3.3, -0.446 }, "screenBlue", "Neon", { rot = { -12, 0, 0 } }),
		P("Mouse", "Block", { 0.35, 0.1, 0.5 }, { 1.2, 2.65, 0.5 }, "charcoal", "SmoothPlastic"),
		P("Phone", "Block", { 0.4, 0.05, 0.75 }, { -1.3, 2.625, 0.5 }, "black", "SmoothPlastic"),
		upright("Mug", 0.55, 0.45, 1.4, 2.6, -0.5, "mugWhite", "SmoothPlastic"),
		upright("PlantPot", 0.6, 0.7, -1.3, 2.6, -0.5, "pot", "SmoothPlastic"),
		P("PlantLeaves", "Ball", { 0.8, 0.8, 0.8 }, { -1.3, 3.5, -0.5 }, "leaf", "Fabric"),
	},
	["Server Rack"] = {
		P("RackBase", "Block", { 3.6, 0.3, 2.8 }, { 0, 0.15, 0 }, "charcoal", "Metal"),
		P("RackTop", "Block", { 3.6, 0.3, 2.8 }, { 0, 7.65, 0 }, "charcoal", "Metal"),
		P("RackBack", "Block", { 3.4, 7.2, 0.15 }, { 0, 3.9, -1.2 }, "charcoal", "Metal"),
		P("RackSideLeft", "Block", { 0.2, 7.2, 2.6 }, { -1.6, 3.9, 0 }, "grayLight", "Metal"),
		P("RackSideRight", "Block", { 0.2, 7.2, 2.6 }, { 1.6, 3.9, 0 }, "grayLight", "Metal"),
		P("RackInside", "Block", { 3, 7, 2.2 }, { 0, 3.9, 0 }, "rack", "Metal"),
		P("Server1", "Block", { 3, 1.1, 0.3 }, { 0, 1.2, 1.2 }, "grayLight", "DiamondPlate"),
		P("Server2", "Block", { 3, 1.1, 0.3 }, { 0, 2.55, 1.2 }, "grayLight", "DiamondPlate"),
		P("Server3", "Block", { 3, 1.1, 0.3 }, { 0, 3.9, 1.2 }, "grayLight", "DiamondPlate"),
		P("Server4", "Block", { 3, 1.1, 0.3 }, { 0, 5.25, 1.2 }, "grayLight", "DiamondPlate"),
		P("ServerVent1", "Block", { 1.3, 0.5, 0.04 }, { -0.6, 1.2, 1.37 }, "charcoal", "SmoothPlastic"),
		P("ServerVent2", "Block", { 1.3, 0.5, 0.04 }, { -0.6, 2.55, 1.37 }, "charcoal", "SmoothPlastic"),
		P("ServerVent3", "Block", { 1.3, 0.5, 0.04 }, { -0.6, 3.9, 1.37 }, "charcoal", "SmoothPlastic"),
		P("ServerVent4", "Block", { 1.3, 0.5, 0.04 }, { -0.6, 5.25, 1.37 }, "charcoal", "SmoothPlastic"),
		P("ServerLED1", "Block", { 0.5, 0.16, 0.05 }, { 0.8, 1.2, 1.37 }, "ledGreen", "Neon"),
		P("ServerLED2", "Block", { 0.5, 0.16, 0.05 }, { 0.8, 2.55, 1.37 }, "ledCyan", "Neon"),
		P("ServerLED3", "Block", { 0.5, 0.16, 0.05 }, { 0.8, 3.9, 1.37 }, "ledGreen", "Neon"),
		P("ServerLED4", "Block", { 0.5, 0.16, 0.05 }, { 0.8, 5.25, 1.37 }, "ledCyan", "Neon"),
		P("PatchPanel", "Block", { 3, 0.7, 0.3 }, { 0, 6.6, 1.2 }, "charcoal", "Metal"),
		P("PatchPortLEDs", "Block", { 2.4, 0.18, 0.04 }, { 0, 6.6, 1.37 }, "ledCyan", "Neon"),
		upright("CableBlue", 6.5, 0.25, 1.95, 0.25, -0.6, "cableBlue", "Plastic"),
		upright("CableRed", 6.5, 0.25, 1.95, 0.25, -0.2, "cableRed", "Plastic"),
		P("TopFan", "Cylinder", { 0.12, 1.4, 1.4 }, { 0, 7.86, 0 }, "steelDark", "Metal", { rot = { 0, 0, 90 } }),
		P("FloorGlowStrip", "Block", { 3.2, 0.06, 0.06 }, { 0, 0.35, 1.45 }, "ledCyan", "Neon"),
	},
	["Whiteboard"] = {
		P("FrameTop", "Block", { 7.4, 0.25, 0.22 }, { 0, 6.8, 0 }, "frameDark", "Metal"),
		P("FrameBottom", "Block", { 7.4, 0.25, 0.22 }, { 0, 2.4, 0 }, "frameDark", "Metal"),
		P("FrameLeft", "Block", { 0.25, 4.65, 0.22 }, { -3.575, 4.6, 0 }, "frameDark", "Metal"),
		P("FrameRight", "Block", { 0.25, 4.65, 0.22 }, { 3.575, 4.6, 0 }, "frameDark", "Metal"),
		P("Board", "Block", { 7, 4.2, 0.2 }, { 0, 4.6, 0 }, "white", "SmoothPlastic"),
		P("ChartBar1", "Block", { 0.6, 0.8, 0.03 }, { 1.2, 3.4, 0.115 }, "barBlueLight", "SmoothPlastic"),
		P("ChartBar2", "Block", { 0.6, 1.3, 0.03 }, { 2, 3.65, 0.115 }, "barBlue", "SmoothPlastic"),
		P("ChartBar3", "Block", { 0.6, 1.9, 0.03 }, { 2.8, 3.95, 0.115 }, "barBlueDark", "SmoothPlastic"),
		P("StickyYellow", "Block", { 0.7, 0.7, 0.04 }, { -2.8, 4.4, 0.12 }, "sticky", "SmoothPlastic", { rot = { 0, 0, 6 } }),
		P("StickyPink", "Block", { 0.7, 0.7, 0.04 }, { -1.9, 3.7, 0.12 }, "stickyPink", "SmoothPlastic", { rot = { 0, 0, -8 } }),
		P("LegLeft", "Block", { 0.25, 2.4, 0.25 }, { -3.1, 1.2, -0.2 }, "frameDark", "Metal"),
		P("LegRight", "Block", { 0.25, 2.4, 0.25 }, { 3.1, 1.2, -0.2 }, "frameDark", "Metal"),
		P("FootLeft", "Block", { 0.4, 0.25, 2.4 }, { -3.1, 0.125, -0.2 }, "charcoal", "Metal"),
		P("FootRight", "Block", { 0.4, 0.25, 2.4 }, { 3.1, 0.125, -0.2 }, "charcoal", "Metal"),
		P("BackBrace", "Block", { 6.4, 0.2, 0.2 }, { 0, 2.5, -0.15 }, "frameDark", "Metal"),
		P("MarkerTray", "Block", { 6, 0.15, 0.45 }, { 0, 2.4, 0.3 }, "silver", "Metal"),
		P("MarkerRed", "Block", { 0.55, 0.12, 0.12 }, { -1, 2.535, 0.3 }, "paintRed", "SmoothPlastic"),
		P("MarkerBlue", "Block", { 0.55, 0.12, 0.12 }, { 0.2, 2.535, 0.3 }, "barBlueDark", "SmoothPlastic"),
		P("Eraser", "Block", { 0.7, 0.2, 0.3 }, { 1.6, 2.575, 0.3 }, "charcoal", "SmoothPlastic"),
	},
	["Neon Logo"] = {
		P("SignPostLeft", "Block", { 0.3, 6, 0.3 }, { -4.2, 3, -0.4 }, "steelDark", "Metal"),
		P("SignPostRight", "Block", { 0.3, 6, 0.3 }, { 4.2, 3, -0.4 }, "steelDark", "Metal"),
		P("SignFootLeft", "Block", { 0.7, 0.25, 2 }, { -4.2, 0.125, -0.4 }, "charcoal", "Metal"),
		P("SignFootRight", "Block", { 0.7, 0.25, 2 }, { 4.2, 0.125, -0.4 }, "charcoal", "Metal"),
		P("SignBracketLeft", "Block", { 0.4, 0.4, 0.9 }, { -4.2, 5.6, -0.15 }, "charcoal", "Metal"),
		P("SignBracketRight", "Block", { 0.4, 0.4, 0.9 }, { 4.2, 5.6, -0.15 }, "charcoal", "Metal"),
		P("SignGlow", "Block", { 9.8, 4.6, 0.15 }, { 0, 5.6, -0.33 }, "neonBlue", "Neon"),
		P("SignBoard", "Block", { 9.4, 4.2, 0.3 }, { 0, 5.6, -0.1 }, "navyDark", "SmoothPlastic"),
		P("SignCapTop", "Block", { 9.9, 0.25, 0.5 }, { 0, 8, -0.2 }, "charcoal", "Metal"),
		P("SignCapBottom", "Block", { 9.9, 0.25, 0.5 }, { 0, 3.2, -0.2 }, "charcoal", "Metal"),
		P("LogoRocket", "Block", { 0.8, 2, 0.1 }, { -3, 6, 0.1 }, "rocketWhite", "Neon", { rot = { 0, 0, -30 } }),
		P("LogoRocketNose", "Ball", { 0.8, 0.8, 0.8 }, { -2.45, 6.95, 0.1 }, "neonBlue", "Neon"),
		P("LogoFlame", "Block", { 0.6, 0.6, 0.1 }, { -3.6, 4.96, 0.1 }, "neonOrange", "Neon", { rot = { 0, 0, 15 } }),
		P("NeonUnderline", "Block", { 6.4, 0.18, 0.08 }, { 1.2, 3.85, 0.09 }, "neonBlue", "Neon"),
		P("LogoSparkA", "Ball", { 0.3, 0.3, 0.3 }, { -1.2, 6.9, 0.1 }, "rocketWhite", "Neon"),
		P("LogoSparkB", "Ball", { 0.25, 0.25, 0.25 }, { -0.4, 7.3, 0.1 }, "neonBlue", "Neon"),
		P("LogoSparkC", "Ball", { 0.3, 0.3, 0.3 }, { -4, 7.4, 0.1 }, "rocketWhite", "Neon"),
	},
}

-- The Office tab: one per TycoonCore upgrade (keys are the saved upgrade names) -------------------------------
local PROP_VIEW = { yaw = -28, pitch = 22 } -- the front and a little of the left side, from a bit above
IconArt.Office = {
	["Desk"] = { name = "Desk", kind = "model", model = "Desk", plate = "plateCream", view = PROP_VIEW },
	["Coffee Machine"] = { name = "CoffeeMachine", kind = "model", model = "Coffee Machine", plate = "plateCream", view = PROP_VIEW },
	["Laptop"] = { name = "Laptop", kind = "model", model = "Laptop", plate = "plateCream", view = PROP_VIEW },
	["Server Rack"] = { name = "ServerRack", kind = "model", model = "Server Rack", plate = "plateCream", view = PROP_VIEW },
	["Whiteboard"] = { name = "Whiteboard", kind = "model", model = "Whiteboard", plate = "plateCream", view = PROP_VIEW },
	["Neon Logo"] = { name = "NeonLogo", kind = "model", model = "Neon Logo", plate = "plateCream", view = PROP_VIEW },
}

-- The recruiting eggs (CreatureConfig.Eggs keys) ------------------------------------------------------------
IconArt.Eggs = {
	Garage = { name = "EggGarage", kind = "ui", plate = "plateCream", shapes = egg(24, 12, 52, 72, "eggGarage", "eggGarageSpot") },
	Startup = { name = "EggStartup", kind = "ui", plate = "plateCream", shapes = egg(24, 12, 52, 72, "eggStartup", "eggStartupSpot") },
	Unicorn = { name = "EggUnicorn", kind = "ui", plate = "plateCream", shapes = egg(24, 12, 52, 72, "eggUnicorn", "eggUnicornSpot") },
}

-- The creatures (CreatureConfig.Creatures keys): CreatureModels' own model on a plate tinted by its rarity -------
IconArt.RarityPlates = {
	Common = "plateCommon", Uncommon = "plateUncommon", Rare = "plateRare", Epic = "plateEpic", Legendary = "plateLegendary",
}
local CREATURE_VIEW = { yaw = 205, pitch = 12 } -- creatures face -Z: the camera stands in front of them, a little to one side
local function creature(name, rarity)
	return { name = name, kind = "creature", creature = name, plate = IconArt.RarityPlates[rarity], view = CREATURE_VIEW }
end
IconArt.Creatures = {
	CoffeeCapybara = creature("CoffeeCapybara", "Common"),
	CodingCat = creature("CodingCat", "Common"),
	PixelPigeon = creature("PixelPigeon", "Common"),
	HustleHamster = creature("HustleHamster", "Uncommon"),
	BugBeetle = creature("BugBeetle", "Uncommon"),
	MemoMole = creature("MemoMole", "Uncommon"),
	SalesShark = creature("SalesShark", "Rare"),
	PitchParrot = creature("PitchParrot", "Rare"),
	ServerSloth = creature("ServerSloth", "Epic"),
	LedgerLlama = creature("LedgerLlama", "Epic"),
	UnicornCEO = creature("UnicornCEO", "Legendary"),
	VentureDragon = creature("VentureDragon", "Legendary"),
}

-- The shop's passes, boosts and Cash packs (ShopConfig keys) ----------------------------------------------------
IconArt.Shop = {
	DoubleCash = { name = "Coin2x", kind = "ui", plate = "plateCream", shapes = {
		S("circle", "Coin", 16, 16, 68, 68, "gold", { outline = true, shade = true }),
		S("ring", "CoinRim", 24, 24, 52, 52, "goldDark", { thickness = 4 }),
		S("text", "CoinLabel", 27, 31, 46, 38, "goldInk", { text = "2x" }),
		S("pill", "CoinShine", 27, 21, 9, 18, "shine", { rotation = -35, transparency = 0.35 }),
	} },
	VIP = { name = "Crown", kind = "ui", plate = "plateCream", shapes = {
		S("diamond", "PointLeft", 16, 30, 22, 22, "gold", { outline = true, shade = true }),
		S("diamond", "PointMiddle", 39, 22, 22, 22, "gold", { outline = true, shade = true }),
		S("diamond", "PointRight", 62, 30, 22, 22, "gold", { outline = true, shade = true }),
		S("circle", "TipLeft", 22, 18, 10, 10, "gold", { outline = true }),
		S("circle", "TipMiddle", 45, 10, 10, 10, "gold", { outline = true }),
		S("circle", "TipRight", 68, 18, 10, 10, "gold", { outline = true }),
		S("rect", "Band", 16, 44, 68, 30, "gold", { outline = true, shade = true }),
		S("circle", "JewelLeft", 24, 53, 12, 12, "jewelRed"),
		S("circle", "JewelMiddle", 44, 53, 12, 12, "jewelBlue"),
		S("circle", "JewelRight", 64, 53, 12, 12, "jewelGreen"),
	} },
	ExtraSlots = { name = "ChairPlus", kind = "ui", plate = "plateCream", shapes = {
		S("rect", "ChairBack", 22, 18, 34, 38, "mint", { outline = true, shade = true }),
		S("rect", "ChairLegLeft", 20, 62, 8, 22, "steel", { outline = true }),
		S("rect", "ChairLegRight", 50, 62, 8, 22, "steel", { outline = true }),
		S("rect", "ChairSeat", 16, 52, 46, 14, "mintDark", { outline = true, shade = true }),
		S("circle", "PlusBadge", 54, 50, 34, 34, "green", { outline = true, shade = true }),
		S("text", "PlusLabel", 58, 57, 26, 20, "white", { text = "+3" }),
	} },
	AutoHatch = { name = "EggGear", kind = "ui", plate = "plateCream", shapes = join(egg(14, 12, 42, 58, "eggCream", "eggCreamSpot"), {
		S("rect", "GearToothA", 51, 64, 38, 10, "steel", { outline = true }),
		S("rect", "GearToothB", 51, 64, 38, 10, "steel", { outline = true, rotation = 60 }),
		S("rect", "GearToothC", 51, 64, 38, 10, "steel", { outline = true, rotation = 120 }),
		S("circle", "GearBody", 56, 55, 28, 28, "steel", { outline = true, shade = true }),
		S("circle", "GearHole", 64, 63, 12, 12, "plateCream"),
	}) },
	Headhunter = { name = "Target", kind = "ui", plate = "plateCream", shapes = {
		S("circle", "RingOuter", 14, 14, 72, 72, "targetRed", { outline = true, shade = true }),
		S("circle", "RingWhite", 25, 25, 50, 50, "white"),
		S("circle", "RingMiddle", 34, 34, 32, 32, "targetRed"),
		S("circle", "Bullseye", 43, 43, 14, 14, "white"),
		S("rect", "ArrowShaft", 44, 33.5, 40, 5, "walnutLight", { outline = true, rotation = -45 }),
		S("diamond", "ArrowFletch", 72, 16, 12, 12, "targetRed", { outline = true }),
	} },
	Shareholder = { name = "Certificate", kind = "ui", plate = "plateCream", shapes = {
		S("rect", "Paper", 14, 18, 72, 60, "paper", { outline = true, shade = true }),
		S("rect", "Line1", 24, 29, 44, 5, "inkSoft"),
		S("rect", "Line2", 24, 39, 52, 5, "inkSoft"),
		S("rect", "Line3", 24, 49, 28, 5, "inkSoft"),
		S("rect", "RibbonLeft", 58, 66, 8, 20, "sealRed", { outline = true, rotation = 20 }),
		S("rect", "RibbonRight", 68, 66, 8, 20, "sealRed", { outline = true, rotation = -20 }),
		S("circle", "Seal", 55, 50, 26, 26, "sealRed", { outline = true, shade = true }),
		S("circle", "SealDot", 63, 58, 10, 10, "gold"),
	} },
	CashSmall = { name = "Bill", kind = "ui", plate = "plateCream", shapes = {
		S("rect", "BillBehind", 20, 24, 66, 38, "billDark", { outline = true, rotation = -8 }),
		S("rect", "Bill", 12, 34, 72, 40, "bill", { outline = true, shade = true }),
		S("frame", "BillBorder", 17, 39, 62, 30, "billDark", { thickness = 2 }),
		S("circle", "BillMedal", 38, 45, 20, 20, "billLight"),
		S("text", "BillSign", 41, 46, 14, 18, "billDark", { text = "$" }),
	} },
	CashMedium = { name = "Bag", kind = "ui", plate = "plateCream", shapes = {
		S("diamond", "BagTieLeft", 30, 10, 18, 18, "bag", { outline = true }),
		S("diamond", "BagTieRight", 52, 10, 18, 18, "bag", { outline = true }),
		S("rect", "BagNeck", 36, 22, 28, 16, "bag", { outline = true }),
		S("pill", "BagBody", 16, 32, 68, 56, "bag", { outline = true, shade = true }),
		S("rect", "BagCord", 32, 33, 36, 7, "coffeeBag", { outline = true }),
		S("text", "BagSign", 38, 48, 24, 32, "bagInk", { text = "$" }),
	} },
	CashLarge = { name = "Vault", kind = "ui", plate = "plateCream", shapes = {
		S("rect", "VaultFootLeft", 20, 76, 12, 10, "steel", { outline = true }),
		S("rect", "VaultFootRight", 68, 76, 12, 10, "steel", { outline = true }),
		S("rect", "VaultBody", 14, 14, 72, 66, "grayLight", { outline = true, shade = true }),
		S("circle", "VaultDoor", 26, 23, 48, 48, "steel", { outline = true, shade = true }),
		S("rect", "SpokeA", 30, 45, 40, 4, "gold"),
		S("rect", "SpokeB", 30, 45, 40, 4, "gold", { rotation = 60 }),
		S("rect", "SpokeC", 30, 45, 40, 4, "gold", { rotation = 120 }),
		S("circle", "Dial", 42, 39, 16, 16, "gold", { outline = true }),
	} },
	-- A four-leaf clover: no text at all on this icon
	LuckBoost = { name = "Clover", kind = "ui", plate = "plateCream", noText = true, shapes = {
		S("rect", "Stem", 58, 56, 7, 32, "cloverDark", { outline = true, rotation = -28 }),
		S("circle", "LeafTop", 34, 12, 32, 32, "clover", { outline = true, shade = true }),
		S("circle", "LeafRight", 54, 32, 32, 32, "clover", { outline = true, shade = true }),
		S("circle", "LeafBottom", 34, 52, 32, 32, "clover", { outline = true, shade = true }),
		S("circle", "LeafLeft", 14, 32, 32, 32, "clover", { outline = true, shade = true }),
		S("circle", "Heart", 42, 40, 16, 16, "cloverDark"),
	} },
	InstantHatch = { name = "EggBolt", kind = "ui", plate = "plateCream", shapes = join(egg(12, 18, 44, 60, "eggCream", "eggCreamSpot"), {
		S("rect", "BoltTop", 60, 12, 13, 32, "bolt", { outline = true, rotation = 25 }),
		S("rect", "BoltMiddle", 50, 41, 34, 11, "bolt", { outline = true, rotation = -15 }),
		S("rect", "BoltLow", 60, 48, 13, 34, "bolt", { outline = true, rotation = 25 }),
	}) },
	PoachShield = { name = "Shield", kind = "ui", plate = "plateCream", shapes = {
		S("diamond", "ShieldTip", 29, 36, 42, 42, "shieldBlue", { outline = true, shade = true }),
		S("rect", "ShieldTop", 20, 14, 60, 44, "shieldBlue", { outline = true, shade = true }),
		S("rect", "ShieldStripe", 45, 18, 10, 60, "shieldLight"),
		S("circle", "ShieldBoss", 41, 30, 18, 18, "gold", { outline = true }),
	} },
}

-- The HUD buttons (EGGS slot 0, SHOP 1, TEAM 2, POACH 3, IPO 4): light figures on the colored buttons, no plate -------
IconArt.Hud = {
	Eggs = { name = "HudEgg", kind = "ui", shapes = egg(24, 10, 52, 76, "hudWhite", "hudSpot") },
	Shop = { name = "HudBag", kind = "ui", shapes = {
		S("ring", "BagHandle", 32, 8, 36, 40, "hudWhite", { thickness = 7, outline = true }),
		S("rect", "BagBody", 18, 30, 64, 56, "hudWhite", { outline = true, shade = true }),
		S("rect", "BagStripe", 18, 44, 64, 8, "hudGold"),
	} },
	Team = { name = "HudPeople", kind = "ui", shapes = {
		S("circle", "HeadBack", 52, 12, 26, 26, "hudSoft", { outline = true }),
		S("pill", "BodyBack", 44, 40, 44, 40, "hudSoft", { outline = true }),
		S("circle", "HeadFront", 22, 22, 28, 28, "hudWhite", { outline = true, shade = true }),
		S("pill", "BodyFront", 12, 52, 48, 38, "hudWhite", { outline = true, shade = true }),
	} },
	-- A magnet (poaching pulls employees over): white, so it stands out on the red-orange POACH button
	Poach = { name = "HudMagnet", kind = "ui", shapes = {
		S("rect", "MagnetLeft", 16, 22, 22, 46, "hudWhite", { outline = true, shade = true }),
		S("rect", "MagnetRight", 62, 22, 22, 46, "hudWhite", { outline = true, shade = true }),
		S("rect", "MagnetBottom", 16, 58, 68, 26, "hudWhite", { outline = true, shade = true }),
		S("rect", "TipLeft", 16, 12, 22, 14, "hudSoft", { outline = true }),
		S("rect", "TipRight", 62, 12, 22, 14, "hudSoft", { outline = true }),
	} },
	Ipo = { name = "HudChart", kind = "ui", shapes = {
		S("rect", "BarLow", 14, 58, 18, 28, "hudWhite", { outline = true, shade = true }),
		S("rect", "BarMiddle", 40, 42, 18, 44, "hudWhite", { outline = true, shade = true }),
		S("rect", "BarHigh", 66, 26, 18, 60, "hudWhite", { outline = true, shade = true }),
		S("rect", "ArrowLine", 12, 32, 52, 8, "hudGold", { outline = true, rotation = -32 }),
		S("diamond", "ArrowHead", 56, 10, 18, 18, "hudGold", { outline = true }),
	} },
}

return IconArt
