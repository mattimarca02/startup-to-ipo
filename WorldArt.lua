-- WorldArt: what the world around the plots looks like (branch world-icons-pass): the spawn plaza, the paths to
-- every plot, kerbs, lamps, trees, bushes, a street sign per plot, the lounge forecourt, lawns and far hills.
-- Put this ModuleScript in ServerScriptService, next to WorldVisuals (which builds it). Data only: built-in Parts,
-- no assets, nothing random, no script.
--
-- No world position of a path or a lamp is written here: WorldVisuals.layout computes them from the site
-- (PLOT_SPACING, the plot count and centers, the lounge, the spawn), so a spacing change needs no redesign.
--   Site     the place's own numbers: copied from the scripts (tools/world_test.py compares each one with the
--            real file) and the Studio facts (placed by hand in Studio, measured by the owner)
--   Layout   widths, gaps and layer heights, in studs
--   Palette  every color, by name. A part names its color; a sector can pass its own palette to WorldVisuals.build
--   Pieces   the small decor items, as part lists around a base point on the ground
--   Hills    the far hills (optional backdrop)
--   Texts    the only words the world may show (the street signs show their plot's number)
--   Budget   parts and lights for the whole world
--
-- A part: P(name, shape, size, offset, color, material [, extra])
--   shape    "Block", "Cylinder" (lies along X: rot = { 0, 0, 90 } stands it up) or "Ball" (3 equal sides)
--   size     { x, y, z } studs
--   offset   { x, y, z } studs from the piece's base point on the ground (y 0 = the Baseplate's top)
--   color    a Palette key
--   material SmoothPlastic, Plastic, Concrete, Cobblestone, Brick, Wood, WoodPlanks, Metal, Fabric, Grass, or Neon
--            (lights only: the name must say Lamp, Light, Glow or Bulb)
--   extra    rot = { x, y, z } degrees, quarter turns only (except an ArchVoussoir..., any angle about Z); text = { value or slot = true, font, color, faces, glow }
--            (faces "Front" = -Z, "Back" = +Z; slot = true shows the plot's number)
-- Everything is decor: anchored, no collision, no touch, no queries. Lights are added by the layout (WorldArt.LampLight).
-- A piece's `solid` list (overhaul phase 1, the owner's point 2) names the invisible boxes a player bumps into:
-- { w, h, d, x, z } (the box's width, height and depth in studs, its center from the piece's base point, its bottom on the
-- ground). Only what a player expects to be solid: a trunk, a post, a bench, a planter, the fountain's basin, the arch's
-- posts. WorldVisuals builds them in the World's Solid group (anchored, CanCollide on, CanTouch off, Transparency 1), each
-- inside its own piece's footprint, so nothing invisible ever stands on a path away from the decor.

local WorldArt = {}

-- The site --------------------------------------------------------------------
WorldArt.Site = {
	-- Copied from the scripts (tools/world_test.py checks every number against the real file)
	plotSpacing = 90, -- TycoonCore PLOT_SPACING
	plotCount = 6, -- TycoonCore MAX_PLOTS
	plotY = 0.5, -- TycoonCore plotCenter: x = -((count - 1) * spacing) / 2 + (slot - 1) * spacing
	plotZ = 150,
	floorSize = { 60, 1, 60 }, -- TycoonCore's "Floor" Part, centered on plotCenter
	-- The two garage signs (offsets from plotCenter): a 0.4 x 3 x 0.4 post on the floor and an 8 x 2.6 x 0.3 board
	signs = {
		{ name = "BuySign", x = 0, z = 24 }, -- TycoonCore SIGN_OFFSET
		{ name = "IpoSign", x = 21, z = 24 }, -- IpoServer SIGN_OFFSET
	},
	signBoard = { 8, 2.6, 0.3 },
	signPostHeight = 3,
	signBoardY = 4.3, -- the board's center above the sign's foot (foot = plotCenter + SIGN_OFFSET)
	-- The VIP Lounge (ShopServer LOUNGE_CENTER, LOUNGE_SIZE, LOUNGE_WALL_HEIGHT, DOOR_WIDTH): glass walls 1 stud thick,
	-- a sign 3 high over the door, the door in the front wall (+Z). A player without VIP is put back 6 studs in front of it.
	lounge = { center = { 0, 0.5, 70 }, size = { 36, 1, 24 }, wallHeight = 10, doorWidth = 8, signHeight = 3, dropOut = 6 },
	-- What the plots' own art uses outside the floor, in studs from the plot center: today's five rooms reach 35.5 to
	-- the sides, 49 behind (stage 5's skyline) and 36.2 in front (stage 1's dirt); the building pass's ground pieces
	-- reach 40 in front. tools/world_test.py builds every room and fails if one reaches further.
	plotReach = { side = 36, back = 50, front = 40, top = 32 },
	-- Studio facts: placed by hand in Studio and measured by the owner; no script makes them, so nothing can be
	-- compared with a file. The world never moves, resizes, replaces or deletes them, and never covers the spawn pad.
	baseplate = { position = { 0, -8, 0 }, size = { 2048, 16, 2048 } }, -- its top is y 0
	spawn = { position = { -1, 0.5, -1 }, size = { 12, 1, 12 } },
	-- Studio only: the preview rooms of the plot visuals (Workspace.PREVIEW_STAGES, docs/STUDIO_SYNC.md), deleted
	-- before publishing. The world keeps out of them (and their reach) while they stand there.
	previewStages = { x0 = -630, x1 = -290, z0 = 120, z1 = 180, reach = 6 },
}

-- The layout's numbers ----------------------------------------------------------
WorldArt.Layout = {
	pathWidth = 8, -- the avenue, the lounge loop, both streets and the connectors
	walkWidth = 6, -- each plot's front walk
	groundTop = 0.04, -- lawn tints: tops at this height
	pathTop = 0.16, -- every paved piece (stage 1's yard dirt is at 0.06: never the same height)
	kerbWidth = 0.6,
	kerbHeight = 0.4,
	plazaHalf = 22, -- the square around the spawn pad's center
	spawnMargin = 1, -- bare ground around the pad: nothing at all in it
	archOut = 2, -- the welcome arch stands this far past the plaza's edge, over the avenue
	crossGap = 17.5, -- grass between the cross walk and the lounge's back wall
	armGap = 4.5, -- from the lounge's walls to the arms of the loop (the hedge grows there)
	forecourtDepth = 4, -- stone between the lounge's front wall (plus loungeMargin) and the back street
	loungeMargin = 0.5, -- nothing within this of the lounge's walls, door and sign
	doorClear = 10, -- in front of the door, this deep and as wide as the door: nothing taller than the paving
	dropClear = 3, -- around the spot a player without VIP is put back: nothing taller than the paving
	backGap = 5, -- from the back street to what the rooms reach behind
	frontGap = 1, -- from what the rooms reach in front to the front street
	connectorClear = 4, -- a connector between two plots needs this much to each plot's reach, or it is left out
	lawnDepth = 22, -- the lawn on the far side of the front street
	meadowWidth = 18, -- the meadow beside each arm of the lounge loop
	-- Decor around each plot, on the far side of the front street (offsets from the plot's x and the street's far edge)
	signDX = 7, signDZ = 2.5, bushDX = -7, bushDZ = 2.5, treeDX = 18, treeDZ = 10, lampDZ = 2.5,
	backTreeDZ = 6, -- the row of trees this far behind the back street, at the gap lines beyond the lounge loop
	hedgeZ = { -8, -2, 4, 10 }, -- hedge balls between the lounge's walls and the arms (z from the lounge's center)
	plazaLampInset = 2.5,
	-- Plaza furniture (offsets from the pad's center; yaw in degrees, a bench faces +Z at 0)
	benches = { { -16, -1, 90 }, { 14, -1, -90 }, { -1, -16, 0 } },
	planters = { { -12, -12 }, { 10, -12 }, { -12, 10 }, { 10, 10 } },
	plazaTrees = 28, -- one tree beyond each corner of the plaza, this far from the pad's center on both axes
	crossTrees = 9, -- two trees this far beyond the ends of the cross walk
}

-- Palette (bright chunky cartoon, next to the Baseplate's grass and PlotArt's colors) ------------------------
WorldArt.Palette = {
	Grass = { 96, 150, 72 }, -- the Baseplate's color (a Studio setting, docs/STUDIO_SYNC.md (b); Grass material since overhaul phase 5); only the previews use it
	Plaza = { 236, 226, 204 },
	Path = { 222, 212, 192 },
	Street = { 168, 174, 186 },
	Walk = { 230, 220, 198 },
	Kerb = { 246, 246, 240 },
	Lawn = { 128, 190, 96 },
	Meadow = { 96, 156, 74 },
	Trunk = { 124, 84, 54 },
	LeafA = { 84, 170, 84 },
	LeafB = { 62, 148, 76 },
	LeafC = { 120, 194, 92 },
	LeafTop = { 150, 214, 110 },
	Bush = { 70, 160, 80 },
	BushLight = { 112, 186, 92 },
	Flower = { 255, 150, 170 },
	Planter = { 200, 112, 74 },
	LampPost = { 54, 56, 62 },
	LampCap = { 40, 44, 54 },
	LampGlow = { 255, 222, 150 },
	LampLight = { 255, 214, 160 },
	Bench = { 184, 136, 92 },
	BenchLeg = { 54, 56, 62 },
	SignPost = { 54, 56, 62 },
	SignBoard = { 46, 110, 100 },
	SignText = { 246, 246, 242 },
	ArchPost = { 40, 44, 54 },
	ArchBeam = { 26, 34, 60 },
	ArchText = { 255, 196, 60 },
	Marble = { 242, 240, 234 }, -- overhaul 2 phase 5: the triumphal arch's white marble
	MarbleShade = { 222, 218, 208 }, -- its mouldings and column shafts
	Inscription = { 70, 64, 56 }, -- the carved letters on the attic
	Hill = { 104, 162, 92 },
	HillFar = { 122, 170, 118 },
	Stone = { 214, 208, 196 }, -- the fountain's stone
	Water = { 84, 170, 230 },
	WaterLight = { 160, 214, 246 },
}

-- The materials of the flat pieces (overhaul phase 5): the paved paths, the kerbs, the lawn tints and the far hills. Each
-- must be in WorldVisuals.MATERIALS (the data check). The pieces below carry their own.
WorldArt.Materials = { path = "Concrete", kerb = "Concrete", ground = "Grass", hill = "Grass" }

-- Helpers ------------------------------------------------------------------------

local function P(name, shape, size, offset, color, material, extra)
	local spec = extra or {}
	spec.name, spec.shape, spec.size, spec.offset, spec.color, spec.material = name, shape, size, offset, color, material
	return spec
end

-- A cylinder standing up (its length is the height), its foot at y
local function upright(name, height, diameter, x, y, z, color, material)
	return P(name, "Cylinder", { height, diameter, diameter }, { x, y + height / 2, z }, color, material, { rot = { 0, 0, 90 } })
end

-- A solid box (see the top of this file): { w, h, d, x, z }
local function solid(w, h, d, x, z)
	return { w, h, d, x or 0, z or 0 }
end

-- A tree: a trunk, a big round crown on it and a smaller one on top (three sizes, three greens; leafy Grass material since overhaul phase 5). Solid: the trunk up into
-- the crown's middle (a player walks under the crown's edge, never through the tree).
local function tree(trunk, crown, top, leaf)
	local crownY = trunk + crown * 0.3
	local parts = {
		upright("Trunk", trunk, 1.3, 0, 0, 0, "Trunk", "Wood"),
		P("Crown", "Ball", { crown, crown, crown }, { 0, crownY, 0 }, leaf, "Grass"),
		P("CrownTop", "Ball", { top, top, top }, { 0.5, crownY + crown * 0.4, -0.4 }, "LeafTop", "Grass"),
	}
	parts.solid = { solid(1.8, crownY, 1.8) }
	return parts
end

-- The pieces ---------------------------------------------------------------------
WorldArt.Pieces = {
	-- A street lamp: a dark post with a glowing lantern on top (the lantern carries the light when the layout lights it)
	Lamp = { -- overhaul 2 phase 5: 12 high, a street lamp at a character's scale
		P("LampBase", "Block", { 1.4, 0.6, 1.4 }, { 0, 0.3, 0 }, "LampPost", "Metal"),
		upright("LampPole", 9, 0.5, 0, 0.6, 0, "LampPost", "Metal"),
		P("LampCollar", "Block", { 1, 0.3, 1 }, { 0, 9.75, 0 }, "LampCap", "Metal"),
		P("LampGlow", "Block", { 1.2, 1.4, 1.2 }, { 0, 10.6, 0 }, "LampGlow", "Neon"),
		P("LampRoof", "Block", { 1.7, 0.35, 1.7 }, { 0, 11.475, 0 }, "LampCap", "Metal"),
		P("LampFinial", "Ball", { 0.5, 0.5, 0.5 }, { 0, 11.9, 0 }, "LampCap", "Metal"),
		solid = { solid(1.4, 11.5, 1.4) }, -- the post, base to lantern
	},
	TreeA = tree(5, 7, 4.6, "LeafA"),
	TreeB = tree(4, 6, 4, "LeafB"),
	TreeC = tree(6, 8, 5, "LeafC"),
	-- A bush: two round balls half sunk in the ground
	Bush = {
		P("BushBig", "Ball", { 3, 3, 3 }, { 0, 1.2, 0 }, "Bush", "Grass"),
		P("BushSmall", "Ball", { 2, 2, 2 }, { 1.3, 0.8, 0.5 }, "BushLight", "Grass"),
	},
	-- One ball of the hedge beside the lounge (it fits the 3.5 stud strip between the wall and the arm)
	Hedge = {
		P("HedgeBall", "Ball", { 2.6, 2.6, 2.6 }, { 0, 1, 0 }, "Bush", "Grass"),
	},
	-- A bench facing +Z at a character's scale (overhaul 2 phase 5: the seat's top 2 high, for a 5-stud character): a plank
	-- seat and back on two dark legs, with arm rests
	Bench = {
		P("BenchSeat", "Block", { 4.6, 0.3, 1.6 }, { 0, 1.85, 0 }, "Bench", "WoodPlanks"),
		P("BenchBack", "Block", { 4.6, 1.4, 0.3 }, { 0, 2.7, -0.65 }, "Bench", "WoodPlanks"),
		P("BenchLegLeft", "Block", { 0.3, 1.7, 1.4 }, { -2, 0.85, 0 }, "BenchLeg", "Metal"),
		P("BenchLegRight", "Block", { 0.3, 1.7, 1.4 }, { 2, 0.85, 0 }, "BenchLeg", "Metal"),
		P("BenchArmLeft", "Block", { 0.3, 0.2, 1.4 }, { -2, 2.6, 0 }, "BenchLeg", "Metal"),
		P("BenchArmRight", "Block", { 0.3, 0.2, 1.4 }, { 2, 2.6, 0 }, "BenchLeg", "Metal"),
		P("BenchArmPostLeft", "Block", { 0.3, 0.6, 0.3 }, { -2, 2.2, 0.5 }, "BenchLeg", "Metal"),
		P("BenchArmPostRight", "Block", { 0.3, 0.6, 0.3 }, { 2, 2.2, 0.5 }, "BenchLeg", "Metal"),
		solid = { solid(4.6, 3.3, 1.5, 0, -0.05) }, -- the whole bench (seat and back; taller than a step, so nobody climbs it)
	},
	-- A round planter with a ball of flowers
	Planter = {
		upright("PlanterPot", 1.2, 2.6, 0, 0, 0, "Planter", "SmoothPlastic"),
		P("PlanterFlowers", "Ball", { 2.2, 2.2, 2.2 }, { 0, 1.6, 0 }, "Flower", "Grass"),
		solid = { solid(2.6, 2.8, 2.6) }, -- the pot and the flowers (taller than a step)
	},
	-- A street sign: a post and a green board with the plot's number on both faces, a ball on top
	Sign = {
		upright("SignPost", 6.2, 0.4, 0, 0, 0, "SignPost", "Metal"),
		P("SignBoard", "Block", { 3.2, 2.2, 0.3 }, { 0, 5.2, 0 }, "SignBoard", "SmoothPlastic",
			{ text = { slot = true, font = "FredokaOne", color = "SignText", faces = { "Front", "Back" } } }),
		P("SignCap", "Ball", { 0.6, 0.6, 0.6 }, { 0, 6.5, 0 }, "SignPost", "Metal"),
		solid = { solid(0.6, 6.4, 0.6) }, -- the post
	},
	-- The welcome gate (overhaul 2 phase 5, the owner's point 1): a Roman triumphal arch in white marble at human scale,
	-- about 42 wide and 34 high: a central archway 12 wide and 20 high (a smooth half circle of radius 6 from 14 up: eight
	-- voussoirs turned 10 to 170 degrees about Z, the one exception to quarter turns, and the keystone at its top; their
	-- depths alternate 3.9 / 3.7 / 3.8 so no two touching faces share a plane, all inside the piers and the lintel), two side
	-- passages 5 wide and 10 high, four piers on plinths, eight engaged columns (base, shaft, capital) on its two faces,
	-- the entablature (architrave, frieze, cornice) and the attic with BUILD YOUR STARTUP carved in a serif on both faces.
	-- Solid: the four piers only (every passage stays open).
	Arch = {
		P("ArchPlinthInLeft", "Block", { 4.6, 1, 5 }, { -8, 0.5, 0 }, "MarbleShade", "Marble"),
		P("ArchPlinthOutLeft", "Block", { 5.6, 1, 5 }, { -17.5, 0.5, 0 }, "MarbleShade", "Marble"),
		P("ArchPierInLeft", "Block", { 4, 23, 4 }, { -8, 12.5, 0 }, "Marble", "Marble"),
		P("ArchPierOutLeft", "Block", { 5, 23, 4 }, { -17.5, 12.5, 0 }, "Marble", "Marble"),
		P("ArchSideLintelLeft", "Block", { 5, 14, 4 }, { -12.5, 17, 0 }, "Marble", "Marble"),
		P("ArchPlinthInRight", "Block", { 4.6, 1, 5 }, { 8, 0.5, 0 }, "MarbleShade", "Marble"),
		P("ArchPlinthOutRight", "Block", { 5.6, 1, 5 }, { 17.5, 0.5, 0 }, "MarbleShade", "Marble"),
		P("ArchPierInRight", "Block", { 4, 23, 4 }, { 8, 12.5, 0 }, "Marble", "Marble"),
		P("ArchPierOutRight", "Block", { 5, 23, 4 }, { 17.5, 12.5, 0 }, "Marble", "Marble"),
		P("ArchSideLintelRight", "Block", { 5, 14, 4 }, { 12.5, 17, 0 }, "Marble", "Marble"),
		P("ArchFrontInLeftBase", "Block", { 2, 2, 2 }, { -8, 1, -2.3 }, "MarbleShade", "Marble"),
		upright("ArchFrontInLeftShaft", 20.6, 1.4, -8, 2, -2.3, "MarbleShade", "Marble"),
		P("ArchFrontInLeftCapital", "Block", { 2.2, 1, 2.2 }, { -8, 23.1, -2.3 }, "MarbleShade", "Marble"),
		P("ArchFrontOutLeftBase", "Block", { 2, 2, 2 }, { -17.5, 1, -2.3 }, "MarbleShade", "Marble"),
		upright("ArchFrontOutLeftShaft", 20.6, 1.4, -17.5, 2, -2.3, "MarbleShade", "Marble"),
		P("ArchFrontOutLeftCapital", "Block", { 2.2, 1, 2.2 }, { -17.5, 23.1, -2.3 }, "MarbleShade", "Marble"),
		P("ArchFrontInRightBase", "Block", { 2, 2, 2 }, { 8, 1, -2.3 }, "MarbleShade", "Marble"),
		upright("ArchFrontInRightShaft", 20.6, 1.4, 8, 2, -2.3, "MarbleShade", "Marble"),
		P("ArchFrontInRightCapital", "Block", { 2.2, 1, 2.2 }, { 8, 23.1, -2.3 }, "MarbleShade", "Marble"),
		P("ArchFrontOutRightBase", "Block", { 2, 2, 2 }, { 17.5, 1, -2.3 }, "MarbleShade", "Marble"),
		upright("ArchFrontOutRightShaft", 20.6, 1.4, 17.5, 2, -2.3, "MarbleShade", "Marble"),
		P("ArchFrontOutRightCapital", "Block", { 2.2, 1, 2.2 }, { 17.5, 23.1, -2.3 }, "MarbleShade", "Marble"),
		P("ArchBackInLeftBase", "Block", { 2, 2, 2 }, { -8, 1, 2.3 }, "MarbleShade", "Marble"),
		upright("ArchBackInLeftShaft", 20.6, 1.4, -8, 2, 2.3, "MarbleShade", "Marble"),
		P("ArchBackInLeftCapital", "Block", { 2.2, 1, 2.2 }, { -8, 23.1, 2.3 }, "MarbleShade", "Marble"),
		P("ArchBackOutLeftBase", "Block", { 2, 2, 2 }, { -17.5, 1, 2.3 }, "MarbleShade", "Marble"),
		upright("ArchBackOutLeftShaft", 20.6, 1.4, -17.5, 2, 2.3, "MarbleShade", "Marble"),
		P("ArchBackOutLeftCapital", "Block", { 2.2, 1, 2.2 }, { -17.5, 23.1, 2.3 }, "MarbleShade", "Marble"),
		P("ArchBackInRightBase", "Block", { 2, 2, 2 }, { 8, 1, 2.3 }, "MarbleShade", "Marble"),
		upright("ArchBackInRightShaft", 20.6, 1.4, 8, 2, 2.3, "MarbleShade", "Marble"),
		P("ArchBackInRightCapital", "Block", { 2.2, 1, 2.2 }, { 8, 23.1, 2.3 }, "MarbleShade", "Marble"),
		P("ArchBackOutRightBase", "Block", { 2, 2, 2 }, { 17.5, 1, 2.3 }, "MarbleShade", "Marble"),
		upright("ArchBackOutRightShaft", 20.6, 1.4, 17.5, 2, 2.3, "MarbleShade", "Marble"),
		P("ArchBackOutRightCapital", "Block", { 2.2, 1, 2.2 }, { 17.5, 23.1, 2.3 }, "MarbleShade", "Marble"),
		P("ArchLintel", "Block", { 12, 4, 4 }, { 0, 22, 0 }, "Marble", "Marble"),
		P("ArchVoussoir1", "Block", { 3, 3, 3.9 }, { 7.386, 15.302, 0 }, "Marble", "Marble", { rot = { 0, 0, 10 } }),
		P("ArchVoussoir2", "Block", { 3, 3, 3.7 }, { 6.495, 17.75, 0 }, "Marble", "Marble", { rot = { 0, 0, 30 } }),
		P("ArchVoussoir3", "Block", { 3, 3, 3.9 }, { 4.821, 19.745, 0 }, "Marble", "Marble", { rot = { 0, 0, 50 } }),
		P("ArchVoussoir4", "Block", { 3, 3, 3.8 }, { 2.565, 21.048, 0 }, "Marble", "Marble", { rot = { 0, 0, 70 } }),
		P("ArchKeystone", "Block", { 2.2, 2.6, 4.4 }, { 0, 21.2, 0 }, "MarbleShade", "Marble"),
		P("ArchVoussoir6", "Block", { 3, 3, 3.8 }, { -2.565, 21.048, 0 }, "Marble", "Marble", { rot = { 0, 0, 110 } }),
		P("ArchVoussoir7", "Block", { 3, 3, 3.9 }, { -4.821, 19.745, 0 }, "Marble", "Marble", { rot = { 0, 0, 130 } }),
		P("ArchVoussoir8", "Block", { 3, 3, 3.7 }, { -6.495, 17.75, 0 }, "Marble", "Marble", { rot = { 0, 0, 150 } }),
		P("ArchVoussoir9", "Block", { 3, 3, 3.9 }, { -7.386, 15.302, 0 }, "Marble", "Marble", { rot = { 0, 0, 170 } }),
		P("ArchArchitrave", "Block", { 41, 1.2, 4.8 }, { 0, 24.6, 0 }, "MarbleShade", "Marble"),
		P("ArchFrieze", "Block", { 40.4, 1.4, 4.4 }, { 0, 25.9, 0 }, "Marble", "Marble"),
		P("ArchCornice", "Block", { 42.4, 0.8, 5.4 }, { 0, 27, 0 }, "MarbleShade", "Marble"),
		P("ArchAttic", "Block", { 30, 6, 4 }, { 0, 30.4, 0 }, "Marble", "Marble"),
		P("ArchInscription", "Block", { 26, 3.4, 4.3 }, { 0, 30.6, 0 }, "Marble", "Marble",
			{ text = { value = "BUILD YOUR STARTUP", font = "Garamond", color = "Inscription", faces = { "Front", "Back" } } }),
		P("ArchAtticCornice", "Block", { 31, 0.6, 4.6 }, { 0, 33.7, 0 }, "MarbleShade", "Marble"),
		solid = { solid(4, 24, 4, -8, 0), solid(4, 24, 4, 8, 0), solid(5, 24, 4, -17.5, 0), solid(5, 24, 4, 17.5, 0) },
	},
	-- The plaza's fountain (overhaul 2 phase 5, the owner's point 2): a round stone basin on a low step with a moulded rim,
	-- full of water, and a two-tier centre (a pedestal, a big bowl of water, a slimmer pedestal, a small bowl, a finial and a
	-- jet of water). The splash and the sound are the client's (IntroClient: a ParticleEmitter and a Sound on the jet, local).
	Fountain = {
		upright("FountainStep", 0.3, 15.6, 0, 0, 0, "Stone", "Concrete"),
		upright("FountainBasin", 1.2, 14, 0, 0, 0, "Stone", "Concrete"),
		upright("FountainRim", 0.3, 14.8, 0, 1, 0, "Stone", "Concrete"),
		upright("FountainWater", 1.45, 13, 0, 0, 0, "Water", "SmoothPlastic"),
		upright("FountainPillar", 3.4, 2, 0, 0, 0, "Stone", "Concrete"),
		upright("FountainBowl", 0.6, 7, 0, 3.4, 0, "Stone", "Concrete"),
		upright("FountainBowlRim", 0.2, 7.4, 0, 3.85, 0, "Stone", "Concrete"),
		upright("FountainBowlWater", 0.65, 6.4, 0, 3.5, 0, "Water", "SmoothPlastic"),
		upright("FountainUpperPillar", 2, 1.2, 0, 4, 0, "Stone", "Concrete"),
		upright("FountainUpperBowl", 0.5, 3.4, 0, 6, 0, "Stone", "Concrete"),
		upright("FountainUpperWater", 0.5, 3, 0, 6.1, 0, "Water", "SmoothPlastic"),
		P("FountainFinial", "Ball", { 1, 1, 1 }, { 0, 7, 0 }, "Stone", "Concrete"),
		upright("FountainSpout", 1.4, 0.5, 0, 7.4, 0, "WaterLight", "SmoothPlastic"),
		solid = { solid(13.6, 2.6, 13.6), solid(2, 7.5, 2) }, -- the basin (taller than a step: nobody walks into the water) and the pedestals
	},
}

-- The light of a lit lamp (the layout lights the plaza's four and the forecourt's two): a PointLight in LampGlow
WorldArt.LampLight = { part = "LampGlow", color = "LampLight", brightness = 1.4, range = 20 }

-- The far hills: low, wide caps of big spheres sunk into the ground (height and radius of the cap at ground level),
-- 250+ studs from everything, inside the Baseplate and away from the Studio preview rooms
WorldArt.Hills = {
	{ name = "HillFrontWest", x = -560, z = 520, height = 22, radius = 110, color = "Hill" },
	{ name = "HillFrontMid", x = -200, z = 640, height = 26, radius = 130, color = "HillFar" },
	{ name = "HillFrontEast", x = 180, z = 600, height = 20, radius = 120, color = "Hill" },
	{ name = "HillFarEast", x = 520, z = 500, height = 24, radius = 110, color = "HillFar" },
	{ name = "HillWest", x = -760, z = 220, height = 18, radius = 100, color = "Hill" },
	{ name = "HillEast", x = 760, z = 260, height = 18, radius = 100, color = "HillFar" },
}

-- The only words the world shows (the street signs show their plot's number: 1, 2, 3...). No odds text (D9).
WorldArt.Texts = { "BUILD YOUR STARTUP" } -- the arch's attic (overhaul 2 phase 5: carved in Garamond)

-- The ring (lobby L4, only with LobbyConfig.ClaimEnabled on): the plaza in front of the lounge's door and the six garages
-- around it. The garages' places come from LobbyConfig.Ring; the numbers marked "copied" are compared with the real
-- files by tools/world_test.py.
WorldArt.Ring = {
	plaza = { x = 0, z = 175, half = 90 }, -- 180 x 180 (LobbyConfig.PlazaCenter, copied)
	-- The SpawnLocation, moved there by hand (docs/STUDIO_SYNC_LOBBY.md): the world never covers it
	spawn = { position = { 0, 0.5, 175 }, size = { 12, 1, 12 } },
	-- Each garage's lot, in its own frame (studs from its floor's center, +Z its front): PlotBuilding.Lot, copied. Nothing of the
	-- world stands in it but its own flat walk.
	lot = { half = 41.3, front = 32.3, back = -54.3, top = 120 },
	-- In front of each facade, the strip where its plants, columns, revolving door and claim post stand (PlotBuilding.OUTSIDE_TO,
	-- copied): flat paving only
	outside = { half = 15, to = 40 },
	frontLine = 32.2, -- each garage's front wall (PlotBuilding.FRONT_OUT, copied): its walk starts there
	walkWidth = 9, -- as wide as the doorway lane
	forecourt = { half = 12 }, -- the paving between the lounge's door and the plaza
	-- Decor, in each garage's frame (x across its front, z out from its floor's center): its number sign and a lamp beside
	-- the walk, two bushes at the facade's corners, all on the grass verge between the front wall and the promenade
	sign = { x = 18, z = 37 }, lamp = { x = -18, z = 37 }, bushes = { { -24, 36 }, { 24, 36 } },
	-- The plaza garden (world-ring-plaza). Every number is from the plaza's center (the spawn pad's), in studs; the four
	-- quarters are mirror images (x and z signs flipped), so one quarter's numbers draw all four.
	--   square     the paved square around the spawn pad: this half-width (the pad and its bare margin cut out of it)
	--   spokeWidth the four spokes from the square to the promenade (north, south, west, east)
	--   promenade  the paved band along the plaza's edges that every garage walk joins: inset from the edge, width
	--   node       the paved square on the north spoke where the fountain stands: its center (z) and half-width
	--   bed        the lawn bed in each quarter: from..to on both axes, with a kerb round it
	square = 22, spokeWidth = 8, promenade = { inset = 4, width = 8 }, node = { z = 50, half = 10 },
	bed = { from = 26, to = 72 },
	-- What stands in each bed (one quarter, mirrored into the other three): trees, bushes, a flower planter
	bedTrees = { { 36, 62, "TreeC" }, { 62, 36, "TreeA" }, { 60, 62, "TreeB" } },
	bedBushes = { { 36, 36 }, { 48, 64 }, { 64, 48 } },
	bedPlanter = { 48, 48 },
	-- Along each spoke (distance from the center, side: +1 or -1, the two sides of the spoke): two unlit lamps, and two
	-- benches facing the spoke, one on each side (on the north spoke they face the fountain's node)
	spokeLamps = { { 30, 1 }, { 66, -1 } },
	spokeBench = 50, -- both benches of a spoke stand this far out
	benchGap = 3, -- from a spoke bench's or lamp's center to the edge of the paving beside it
	-- The square (from the pad's center): four lit lamps, four benches facing the pad, four planters, the arch
	litLamps = 10, -- the four lit lamps stand this far from the pad's center on both axes
	benches = { { -17, -9, 90 }, { -17, 9, 90 }, { 17, -9, -90 }, { 17, 9, -90 } },
	planters = { { -14, -14 }, { 14, -14 }, { -14, 14 }, { 14, 14 } },
	arch = { x = 0, z = -26 }, -- over the south spoke: the gate from the lounge into the square
	gapTrees = { { -140, 175 }, { 140, 175 } }, -- in the gaps between the two west and the two east garages (world x, z)
}

-- For the whole world (placeholders until a phone test). ringParts: the ring world's own budget, so six garages at their
-- biggest stage plus the plaza stay under 3,000 parts (tools/building_test.py).
WorldArt.Budget = { parts = 600, lights = 8, ringParts = 520 } -- ringParts 480 -> 520: the triumphal arch (overhaul 2 phase 5; the ring world has 502)

return WorldArt
