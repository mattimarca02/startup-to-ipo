-- PlotBuilding: the closed building around each garage's room, one per funding stage, made from the 3D kit
-- (ReplicatedStorage.KitModels, docs/KIT_MODELS.md). Put this ModuleScript in ServerScriptService, next to
-- PlotBuildingVisuals (which builds it) and PlotArt (the room inside, unchanged).
--
-- Stages[i] is the building of IpoConfig.Stages[i]: 1 Garage, 2 Small Office (Seed), 3 Big Office (Series A),
-- 4 Small Corporate (Series B), 5 Big Corporate (IPO-ready). A stage past the last shows the last one.
-- Looks only, like PlotArt: nothing here is saved, sent through a remote or read back. Nothing random, no odds text.
--
-- Data and pure layout code (no services, no Instances), so tools/building_test.py runs it outside Studio:
--   PlotBuilding.KitManifest        the 36 kit models: size { x, y, z } (width, height, depth), roles and their colors
--   PlotBuilding.fallbackOf(key)    the Parts version of a kit model: boxes { role, size, at } (built when the model is missing)
--   PlotBuilding.layout(stage)      -> { pieces, boxes, inside, footprint, furniture }: every piece, every solid box
--   PlotBuilding.furnitureFootprints(stage) -> the floor boxes the furniture takes (customize PR 2 keeps them free)
--   PlotBuilding.styleOf(stage, key, role, look) -> { color, material, transparency } of one part
--   PlotBuilding.partsOf(piece)     the boxes of one piece built from Parts (a kit model's fallback, or a Block's one box)
--   PlotBuilding.rolesOf(piece)     { role = true } of one piece: one MeshPart per role from the kit (a Block: its one role)
--
-- The frame: studs from the middle of the Floor's top face (the garage's frame, TycoonCore plotFrame), +X right, +Z the
-- front (the door, toward the plaza), y 0 the floor top, y -1 the ground. A piece's "turn" is its front's direction in
-- degrees about +Y: 0 faces +Z, 90 faces +X, 180 faces -Z, 270 faces -X (TycoonCore's quarter turns). A piece stands on
-- its bottom-center (the kit models' WorldPivot).

local PlotBuilding = {}

PlotBuilding.KIT_FOLDER = "KitModels" -- ReplicatedStorage.KitModels.<Key>
-- The turn that brings an imported kit model's front back to +Z. The files face +Z; whether Studio's importer kept that
-- is not verified. 0 = it did, 180 = it turned them around. docs/STUDIO_SYNC_LOBBY.md's kit front check pins it.
PlotBuilding.KIT_FRONT_TURN = 180

-- The frame and the lot -------------------------------------------------------------------------------------------
PlotBuilding.FLOOR_TOP = 0.5 -- TycoonCore's Floor is 1 thick, centered on the plot center (PlotArt.Layout.floorTop)
PlotBuilding.GROUND = -1 -- the Floor's bottom, the Baseplate's top: walls stand on it
PlotBuilding.STORY = 14 -- the kit's walls are 14 high: one story
PlotBuilding.WALL = 2 -- and 2 deep
PlotBuilding.FRONT_IN = 30.2 -- the front wall's inner face, the same at every stage (the room's parts end at 30.15)
PlotBuilding.FRONT_OUT = 32.2 -- its outer face: the front never moves
PlotBuilding.Lot = { half = 41.3, front = 32.3, back = -54.3 } -- 82.6 x 86.6 (docs/LOBBY_GARAGE_PROPOSAL.md 4.2)
PlotBuilding.MinShell = { half = 31, back = -31 } -- building-pass's shell (62 x 62): every stage is at least this big
PlotBuilding.ROOM_EDGE = 30 -- the Floor's edge (60 x 60)
PlotBuilding.Room = { half = 30.15 } -- the room's parts (PlotArt) stand inside this, except stage 1's yard and stage 5's skyline
PlotBuilding.OUTSIDE_TO = 40 -- pieces in front of the facade (plants, columns, the door leaf) stay before this z (WorldArt plotReach.front)
-- The doorway lane: 9 wide, 9 high above the floor top, from inside the room's front edge to the end of the apron.
-- Nothing solid stands in it; only a stage's door pieces (marked lane = true, never solid) may.
PlotBuilding.Lane = { half = 4.5, top = 9, from = 26, to = 35.7 }
PlotBuilding.APRON = 3.5 -- in front of the door: counts as inside for the fade
PlotBuilding.ClaimPost = { x0 = 6, x1 = 10, z0 = 34.2, z1 = 36.2, top = 9 } -- PR L3's claim post (x 7, 3 in front of the wall) and its lamp
PlotBuilding.Landing = { x = 0, z = 12, half = 2.5, top = 8 } -- where TycoonCore's teleportToPlot lands a player
PlotBuilding.CLEAR_ABOVE = 12.5 -- a solid part over the 60 x 60 floor stays this high or higher (a jump reaches about 12.3)
PlotBuilding.ROOF = 0.5 -- the roof's solid box: this thick, under the top of the outer mass (12.5 to 13 on one story)
PlotBuilding.Budget = { parts = 160, lights = 1 } -- per building: kit MeshParts (or fallback Parts) plus the solid boxes; one light (the ceiling's)
PlotBuilding.Inside = { floorBelow = 3, margin = 1 } -- the ground floor's inside box (PlotBuildingVisuals.isInside; the server's unstick and the tests)
-- The occlusion fade (BuildingClient, overhaul phase 2): a shell part between the camera and the player goes to `occluded`
-- (from its own transparency) in `seconds`, and comes back 1.5 times slower
PlotBuilding.Fade = { seconds = 0.3, occluded = 0.8 }
PlotBuilding.MATERIALS = {
	Concrete = true, CorrodedMetal = true, Metal = true, DiamondPlate = true, Wood = true, WoodPlanks = true, Brick = true,
	Fabric = true, Plastic = true, SmoothPlastic = true, Glass = true, Neon = true, Marble = true, Slate = true,
}
PlotBuilding.NEON_KEYS = { BareBulb = true } -- Neon only on a light
-- Only these may be stretched (by scaling their parts): along X, and Floor along Z too. Every other piece keeps its size.
-- WallDoor and its DoorLeaf are stretched 1.5 times along X (24 and 9 wide): the kit's opening is 6, the doorway lane 9.
PlotBuilding.STRETCH = { Wall = { x = true }, RoofEdge = { x = true }, Floor = { x = true, z = true }, WallDoor = { x = true }, DoorLeaf = { x = true } }
-- A Block is a piece that is one plain Part, never a kit model: { key = "Block", size = { x, y, z }, role, look }. It stands
-- on its bottom-center like a kit piece, is painted by its role from the stage's style (like the structure kit) and gets
-- the same flags as a fallback Part (never solid, never touched, never hit by a ray, no shadow). It is never stretched: its
-- size is its size. Roofs, signs, sills, gutters and pipes are Blocks: details the kit has no piece for.
PlotBuilding.BLOCK = "Block"
PlotBuilding.PITCH_THICK = 1 -- a pitched roof's sheets are this thick
-- The sign's text (the only gui of a building): a SurfaceGui on the board's +Z face (NormalId Back: toward the plaza), its
-- label in the right part of the board (the emblem's bars take the left), white, two lines at most, no decal, no asset
PlotBuilding.SIGN_TEXT = { name = "SignText", face = "Back", pixelsPerStud = 40, area = { 0.5, 0.08, 0.47, 0.84 }, font = "GothamBold", color = { 246, 246, 242 } }

-- The kit, copied from docs/KIT_MODELS.md (tools/building_test.py compares the two) -----------------------------
-- size = { width (X), height (Y), depth (Z) }. roles = the MeshParts of the model, one per role, with the file's colors.
local function kit(w, h, d, roles)
	return { size = { w, h, d }, roles = roles }
end
PlotBuilding.KitManifest = {
	Wall = kit(16, 14, 2, { main = "C8CCD2", trim = "F4F4F1" }),
	WallDoor = kit(16, 14, 2, { main = "C8CCD2", trim = "F4F4F1" }),
	DoorLeaf = kit(6, 10, 0.5, { trim = "F4F4F1", glass = "A6D6F0", dark = "34373D" }),
	WallWindow = kit(16, 14, 2, { main = "C8CCD2", trim = "F4F4F1", glass = "A6D6F0" }),
	WallGlass = kit(16, 14, 2, { trim = "F4F4F1", glass = "A6D6F0" }),
	WallGarage = kit(24, 14, 2, { main = "C8CCD2", trim = "F4F4F1" }),
	GarageDoor = kit(20, 12, 1, { accent = "F28A2E", dark = "34373D" }),
	Corner = kit(2, 14, 2, { trim = "F4F4F1" }),
	Floor = kit(16, 1, 16, { main = "C8CCD2" }),
	RoofEdge = kit(16, 3, 2, { trim = "F4F4F1" }),
	Stairs = kit(8, 15, 16, { main = "C8CCD2", trim = "F4F4F1" }),
	Column = kit(3, 14, 3, { main = "C8CCD2", accent = "F28A2E" }),
	WallElevator = kit(16, 14, 2, { main = "C8CCD2", trim = "F4F4F1", accent = "F28A2E", dark = "34373D" }),
	RevolvingDoor = kit(10, 12, 10, { trim = "F4F4F1", glass = "A6D6F0", dark = "34373D" }),
	RoofCrown = kit(24, 6, 24, { main = "E94B4B", accent = "F2C230", dark = "34373D" }),
	Computer = kit(3, 3, 2, { main = "F4F5F7", trim = "3E9BE0", dark = "2F3440" }),
	Laptop = kit(2, 1, 2, { main = "D5DAE1", dark = "2F3440" }),
	Phone = kit(2, 1, 2, { main = "F2803A", trim = "FFFFFF", dark = "2F3440" }),
	Crate = kit(4, 4, 4, { main = "F2A94E", trim = "C77B30" }),
	BareBulb = kit(1, 3, 1, { trim = "D5DAE1", glass = "FFE27A", dark = "2F3440" }),
	Shelf = kit(8, 8, 2, { main = "F2A94E", trim = "5DBB63", accent = "3E9BE0", dark = "2F3440" }),
	Plant = kit(3, 5, 3, { main = "5DBB63", trim = "F2803A", dark = "6B4A2F" }),
	Workbench = kit(8, 4, 4, { main = "F2A94E", trim = "3E9BE0", accent = "F2803A", dark = "2F3440" }),
	Whiteboard = kit(8, 7, 2, { main = "FFFFFF", trim = "D5DAE1", accent = "3E9BE0", dark = "2F3440" }),
	CoffeeMachine = kit(3, 3, 2, { dark = "2F3440", main = "3E9BE0", trim = "C9CED6", accent = "F6F4EF" }),
	MeetingTable = kit(16, 3, 6, { main = "F2A94E", dark = "2F3440", trim = "C9CED6" }),
	Sofa = kit(8, 4, 4, { trim = "F2A94E", main = "3E9BE0", accent = "F2C230" }),
	Armchair = kit(4, 4, 4, { trim = "F2A94E", main = "3E9BE0", accent = "F2C230" }),
	ReceptionDesk = kit(14, 4, 4, { dark = "2F3440", main = "F6F4EF", trim = "F2A94E", accent = "3E9BE0" }),
	ServerRack = kit(3, 8, 4, { main = "2F3440", trim = "C9CED6", accent = "5DBB4A" }),
	BoardTable = kit(20, 3, 8, { trim = "F2C230", main = "6E4325", dark = "2F3440" }),
	Rug = kit(12, 0.2, 8, { trim = "F6F4EF", main = "3E9BE0" }),
	LobbyTree = kit(4, 8, 4, { main = "F6F4EF", dark = "2F3440", trim = "F2A94E", accent = "5DBB4A" }),
	Bell = kit(6, 7, 6, { dark = "2F3440", main = "6E4325", accent = "F2C230" }),
	Chair = kit(3, 4, 3, { main = "3E9BE0", trim = "D5DAE1", dark = "2F3440" }),
	Desk = kit(8, 3, 4, { main = "F2A94E", trim = "3E9BE0", dark = "2F3440" }),
}
-- The structure kit: recolored per stage by role. Furniture keeps its own colors (the manifest's).
PlotBuilding.STRUCTURE = {
	Wall = true, WallDoor = true, DoorLeaf = true, WallWindow = true, WallGlass = true, WallGarage = true, GarageDoor = true,
	Corner = true, Floor = true, RoofEdge = true, Stairs = true, Column = true, WallElevator = true, RevolvingDoor = true,
	RoofCrown = true,
}

-- The Parts version of each kit model: boxes { role, size { x, y, z }, at { x, y, z } (its center) } in the model's own
-- frame (bottom-center, front +Z), filling exactly its size, every role at least once (the kit has one MeshPart per
-- role). Built when KitModels or the key is missing. A key with no entry here is its box cut into one slab per role.
local function box(role, w, h, d, x, y, z)
	return { role = role, size = { w, h, d }, at = { x, y, z } }
end
local FALLBACK = {
	Wall = { box("main", 16, 13, 2, 0, 6.5, 0), box("trim", 16, 1, 2, 0, 13.5, 0) },
	-- the opening: 6 wide, 10 high, centered, from the bottom
	WallDoor = { box("main", 5, 13, 2, -5.5, 6.5, 0), box("main", 5, 13, 2, 5.5, 6.5, 0), box("main", 6, 3, 2, 0, 11.5, 0), box("trim", 16, 1, 2, 0, 13.5, 0) },
	DoorLeaf = { box("dark", 6, 0.5, 0.5, 0, 0.25, 0), box("glass", 6, 8.5, 0.3, 0, 4.75, 0), box("trim", 6, 1, 0.5, 0, 9.5, 0) },
	-- two windows as one ribbon of glass 5 high, from 5 to 10
	WallWindow = { box("main", 16, 5, 2, 0, 2.5, 0), box("glass", 16, 5, 1, 0, 7.5, 0), box("trim", 16, 4, 2, 0, 12, 0) },
	WallGlass = { box("glass", 16, 13, 1, 0, 6.5, 0), box("trim", 16, 1, 2, 0, 13.5, 0) },
	-- the opening: 20 wide, 12 high, centered, from the bottom
	WallGarage = { box("main", 2, 13, 2, -11, 6.5, 0), box("main", 2, 13, 2, 11, 6.5, 0), box("main", 20, 1, 2, 0, 12.5, 0), box("trim", 24, 1, 2, 0, 13.5, 0) },
	GarageDoor = { box("accent", 20, 11, 1, 0, 5.5, 0), box("dark", 20, 1, 1, 0, 11.5, 0) },
	Corner = { box("trim", 2, 14, 2, 0, 7, 0) },
	Floor = { box("main", 16, 1, 16, 0, 0.5, 0) },
	RoofEdge = { box("trim", 16, 3, 2, 0, 1.5, 0) },
	Column = { box("main", 3, 13, 3, 0, 6.5, 0), box("accent", 3, 1, 3, 0, 13.5, 0) },
	-- two glass wings crossing, under the drum's dark top
	RevolvingDoor = { box("glass", 10, 11, 0.4, 0, 5.5, 0), box("glass", 0.4, 11, 10, 0, 5.5, 0), box("trim", 10, 0.5, 10, 0, 11.25, 0), box("dark", 10, 0.5, 10, 0, 11.75, 0) },
	RoofCrown = { box("main", 24, 4, 24, 0, 2, 0), box("accent", 20, 1, 20, 0, 4.5, 0), box("dark", 16, 1, 16, 0, 5.5, 0) },
	BareBulb = { box("glass", 1, 1.5, 1, 0, 0.75, 0), box("trim", 0.6, 0.3, 0.6, 0, 1.65, 0), box("dark", 0.4, 1.2, 0.4, 0, 2.4, 0) },
	Plant = { box("trim", 2, 2, 2, 0, 1, 0), box("dark", 1.6, 0.2, 1.6, 0, 2.1, 0), box("main", 3, 2.8, 3, 0, 3.6, 0) },
	ReceptionDesk = { box("dark", 14, 0.5, 4, 0, 0.25, 0), box("main", 14, 3, 3.8, 0, 2, -0.1), box("accent", 14, 0.6, 0.2, 0, 2, 1.9), box("trim", 14, 0.5, 4, 0, 3.75, 0) },
	-- the back is at -Z: the front (where you sit) is +Z
	Sofa = { box("main", 8, 2, 4, 0, 1, 0), box("trim", 8, 2, 1, 0, 3, -1.5), box("accent", 6, 0.4, 2.6, 0, 2.2, 0.5) },
	Armchair = { box("main", 4, 2, 4, 0, 1, 0), box("trim", 4, 2, 1, 0, 3, -1.5), box("accent", 3, 0.4, 2.6, 0, 2.2, 0.5) },
	CoffeeMachine = { box("dark", 3, 3, 1.5, 0, 1.5, -0.25), box("main", 1.5, 1, 0.5, 0, 1, 0.75), box("trim", 1.5, 0.2, 0.5, 0, 0.1, 0.75), box("accent", 0.6, 0.6, 0.1, 0, 2.4, 0.55) },
	Whiteboard = { box("main", 8, 3.7, 0.4, 0, 4.85, 0.4), box("trim", 8, 0.3, 0.4, 0, 6.85, 0.4), box("accent", 7, 0.2, 0.6, 0, 2.9, 0.5),
		box("dark", 0.4, 7, 2, -3.8, 3.5, 0), box("dark", 0.4, 7, 2, 3.8, 3.5, 0) },
	Shelf = { box("dark", 8, 0.5, 2, 0, 0.25, 0), box("main", 8, 6.5, 2, 0, 3.75, 0), box("trim", 8, 0.5, 2, 0, 7.25, 0), box("accent", 8, 0.5, 2, 0, 7.75, 0) },
	ServerRack = { box("main", 3, 7.6, 3.9, 0, 3.8, -0.05), box("trim", 3, 0.4, 4, 0, 7.8, 0), box("accent", 2, 0.3, 0.1, 0, 6, 1.95) },
	LobbyTree = { box("main", 3, 2.5, 3, 0, 1.25, 0), box("trim", 3.4, 0.5, 3.4, 0, 2.75, 0), box("dark", 0.6, 0.6, 0.6, 0, 3.3, 0), box("accent", 4, 4.4, 4, 0, 5.8, 0) },
	BoardTable = { box("dark", 12, 2.4, 4, 0, 1.2, 0), box("main", 20, 0.4, 8, 0, 2.6, 0), box("trim", 20, 0.2, 8, 0, 2.9, 0) },
	Rug = { box("trim", 12, 0.1, 8, 0, 0.05, 0), box("main", 10, 0.1, 6, 0, 0.15, 0) },
	Bell = { box("main", 6, 1, 6, 0, 0.5, 0), box("accent", 3, 3, 3, 0, 4, 0), box("dark", 6, 1, 1, 0, 6.5, 0) },
	-- the screen faces +Z: its dark back is at -Z
	Computer = { box("dark", 1.2, 0.6, 2, 0, 0.3, 0), box("main", 3, 2.4, 1.2, 0, 1.8, 0.2), box("trim", 2.6, 2, 0.2, 0, 1.8, 0.9) },
	Chair = { box("dark", 2.4, 1, 2.4, 0, 0.5, 0), box("main", 3, 1, 3, 0, 1.5, 0), box("trim", 3, 2, 0.6, 0, 3, -1.2) },
}
local fallbackOf
function PlotBuilding.fallbackOf(key)
	local list = FALLBACK[key]
	if list then
		return list
	end
	local entry = PlotBuilding.KitManifest[key]
	if not entry then
		return nil
	end
	local roles = {}
	for role in pairs(entry.roles) do
		table.insert(roles, role)
	end
	table.sort(roles)
	local s, out = entry.size, {}
	local h = s[2] / #roles
	for i, role in ipairs(roles) do
		table.insert(out, box(role, s[1], h, s[3], 0, h * (i - 0.5), 0))
	end
	return out
end
fallbackOf = PlotBuilding.fallbackOf

-- The boxes of one piece built from Parts: a Block is its one box, anything else its kit model's fallback
function PlotBuilding.partsOf(piece)
	if piece.key == PlotBuilding.BLOCK then
		local s = piece.size
		return { box(piece.role, s[1], s[2], s[3], 0, s[2] / 2, 0) }
	end
	return fallbackOf(piece.key)
end

-- The roles of one piece's parts (the kit builds one MeshPart per role; a Block is one Part)
function PlotBuilding.rolesOf(piece)
	if piece.key == PlotBuilding.BLOCK then
		return { [piece.role] = true }
	end
	local entry = PlotBuilding.KitManifest[piece.key]
	return entry and entry.roles
end

-- Styles: the color and material of each role, per stage ----------------------------------------------------------
-- roles: the structure kit's five roles. keys: one key's own role (it wins over roles). looks: a named set of roles a
-- piece can ask for (look = "tower"). Furniture uses its manifest color with `furniture`'s material.
local function rgb(r, g, b) return { r, g, b } end
local function S(color, material, transparency) return { color = color, material = material, transparency = transparency } end

local GLASS = 0.3 -- the kit's glass parts arrive at 0.3: the fade starts from it

PlotBuilding.Styles = {
	{ -- 1 Garage: brick-red walls, dark corners and roof edge, the orange roll-up door, a bare bulb
		roles = {
			main = S(rgb(156, 66, 52), "Brick"), trim = S(rgb(74, 74, 80), "Concrete"), accent = S(rgb(232, 132, 46), "Metal"),
			glass = S(rgb(196, 192, 160), "Glass", GLASS), dark = S(rgb(52, 55, 61), "Metal"),
		},
		keys = { BareBulb = { glass = S(rgb(255, 226, 122), "Neon"), trim = S(rgb(213, 218, 225), "Metal") } },
		-- pitch: the rusty sheet-metal roof, its ridge cap and gutters; sign: the board over the roll-up door (accent: its emblem)
		looks = { roof = { main = S(rgb(84, 86, 92), "Concrete") }, pitch = { main = S(rgb(128, 84, 62), "CorrodedMetal"), dark = S(rgb(60, 62, 68), "Metal") },
			sign = { dark = S(rgb(40, 42, 48), "Metal"), trim = S(rgb(214, 210, 200), "Concrete") } },
		furniture = "SmoothPlastic",
		light = { color = rgb(255, 214, 160), brightness = 0.8, range = 44 }, -- a warm bulb under the garage's roof
	},
	{ -- 2 Small Office: white walls, mint trim, clear glass
		roles = {
			main = S(rgb(242, 243, 240), "SmoothPlastic"), trim = S(rgb(46, 110, 100), "SmoothPlastic"), accent = S(rgb(232, 128, 102), "SmoothPlastic"),
			glass = S(rgb(166, 214, 240), "Glass", GLASS), dark = S(rgb(52, 55, 61), "Metal"),
		},
		looks = { roof = { main = S(rgb(150, 156, 160), "Concrete") }, floor = { main = S(rgb(200, 204, 210), "SmoothPlastic") } },
		furniture = "SmoothPlastic",
		light = { color = rgb(255, 246, 230), brightness = 0.9, range = 48 }, -- white office light
	},
	{ -- 3 Big Office: white and warm wood
		roles = {
			main = S(rgb(244, 244, 241), "SmoothPlastic"), trim = S(rgb(170, 122, 78), "Wood"), accent = S(rgb(246, 154, 52), "SmoothPlastic"),
			glass = S(rgb(170, 210, 232), "Glass", GLASS), dark = S(rgb(44, 52, 66), "Metal"),
		},
		looks = { roof = { main = S(rgb(120, 124, 130), "Concrete") }, floor = { main = S(rgb(196, 160, 118), "WoodPlanks") } },
		furniture = "SmoothPlastic",
		light = { color = rgb(255, 240, 214), brightness = 0.9, range = 50 }, -- warm white, the loft's wood
	},
	{ -- 4 Small Corporate: blue glass, a darker crown band
		roles = {
			main = S(rgb(70, 120, 196), "Glass"), trim = S(rgb(34, 42, 62), "SmoothPlastic"), accent = S(rgb(52, 120, 230), "SmoothPlastic"),
			glass = S(rgb(96, 156, 232), "Glass", GLASS), dark = S(rgb(28, 32, 44), "Metal"),
		},
		keys = { RoofEdge = { trim = S(rgb(22, 28, 44), "Metal") } },
		looks = { roof = { main = S(rgb(60, 66, 80), "Concrete") }, floor = { main = S(rgb(150, 156, 166), "Slate") } },
		furniture = "SmoothPlastic",
		light = { color = rgb(236, 244, 255), brightness = 1, range = 52 }, -- cool white, the glass tower
	},
	{ -- 5 Big Corporate: marble and dark glass with gold accents; the tower is dark glass
		roles = {
			main = S(rgb(232, 230, 224), "Marble"), trim = S(rgb(38, 40, 48), "Metal"), accent = S(rgb(255, 196, 60), "Metal"),
			glass = S(rgb(34, 46, 70), "Glass", GLASS), dark = S(rgb(24, 26, 32), "Metal"),
		},
		keys = { RoofCrown = { main = S(rgb(38, 40, 48), "Metal") } },
		looks = { tower = { main = S(rgb(30, 40, 62), "Glass"), trim = S(rgb(255, 196, 60), "Metal") }, roof = { main = S(rgb(48, 50, 58), "Concrete") },
			floor = { main = S(rgb(214, 210, 200), "Marble") } },
		furniture = "SmoothPlastic",
		light = { color = rgb(255, 236, 200), brightness = 1, range = 54 }, -- gold-white, the marble lobby
	},
}

local function hexColor(hex)
	return { tonumber(string.sub(hex, 1, 2), 16), tonumber(string.sub(hex, 3, 4), 16), tonumber(string.sub(hex, 5, 6), 16) }
end

-- The look of one part: { color = { r, g, b }, material, transparency }. nil when the stage has no style for it.
function PlotBuilding.styleOf(stage, key, role, look)
	local style = PlotBuilding.Styles[stage]
	local block = key == PlotBuilding.BLOCK
	local entry = PlotBuilding.KitManifest[key]
	if not style or not (entry or block) then
		return nil
	end
	local pick = style.keys and style.keys[key] and style.keys[key][role]
	if not pick and look and style.looks and style.looks[look] then
		pick = style.looks[look][role]
	end
	if not pick and (PlotBuilding.STRUCTURE[key] or block) then
		pick = style.roles[role]
		if not pick then
			return nil -- the structure kit and the Blocks are always styled: a role the stage forgot is a mistake, not the file's color
		end
	end
	if pick then
		local t = pick.transparency
		if t == nil and role == "glass" and pick.material == "Glass" then
			t = GLASS
		end
		return { color = pick.color, material = pick.material, transparency = t or 0 }
	end
	local hex = entry.roles[role]
	if not hex then
		return nil
	end
	return { color = hexColor(hex), material = style.furniture, transparency = role == "glass" and GLASS or 0 }
end

-- The five buildings ------------------------------------------------------------------------------------------------
-- A building is one or more masses (a box of stories: half-width, back face, front face, first and last story, corner
-- posts or not), the sequence of pieces along each wall of each story, the door, the pieces outside, and the furniture.
-- A mass may have a pitched roof (pitch = { slope, overhang }: two sheets from the side eaves to a ridge along Z, brick
-- gables stepped front and back, a ridge cap, gutters) and every stage has a sign over its door (sign = { y, w, h [, z] }:
-- a plate and a board on the facade (z = the plate's back face, FRONT_OUT unless the sign sits on a band in front of it),
-- a growth-chart emblem on the board's left and, on its right, the one text a building carries: a SurfaceGui the server
-- writes through PlotBuildingVisuals.setSign (the owner's company name and the stage, or FREE on a free garage; overhaul
-- phase 1, the owner's point 7). Both are Blocks. Extras may be Blocks too: { block = { x, y, z }, role, name }.
-- Walls: doorWall (the front of the ground story), frontWall (the front above it), sideWall, backWall. A wall sequence lists pieces from one end to the other: { key = "WallWindow" } (its kit width), { fill = true } (a
-- Wall stretched to share what is left), { gap = 10 } (nothing in the wall run: the doorway, or the room an extra fills,
-- like the offices' stretched WallDoor).

local F = { fill = true }
local function K(key) return { key = key } end
local function gap(width) return { gap = width } end

PlotBuilding.Stages = {
	{ -- 1 Garage: one story, brick, corner posts, the roll-up door rolled up under the ceiling, a bare bulb by the door, a
		-- rusty pitched roof between stepped brick gables, the company's sign over the door, windows either side of it
		key = "Garage", name = "Garage",
		masses = { { half = 34, back = -34, front = 32.2, from = 1, to = 1, corners = true, roofEdge = true, pitch = { slope = 1 / 3, overhang = 1 },
			doorWall = { F, K("WallWindow"), K("WallGarage"), K("WallWindow"), F }, sideWall = { F, K("WallWindow"), F }, backWall = { F, K("WallWindow"), F } } },
		door = { half = 10, top = 11, lanePiece = "WallGarage" }, -- the WallGarage opening: 20 wide, 12 high from the ground
		sign = { y = 16.4, w = 18, h = 5.5 }, -- on the front gable, over the roll-up door
		extras = {
			-- rolled up: lying flat under the ceiling, just inside the opening (front facing up), non-solid
			{ key = "GarageDoor", x = 0, y = 11.5, z = 30.2, turn = 0, tilt = -90 },
			{ key = "BareBulb", x = 0, y = 10.2, z = 32.7, turn = 0 },
			-- the facade: sills under the two windows (their holes start 4 above the floor top), a concrete plinth either side
			-- of the door (from the opening's jambs to the corners)
			{ block = { 14, 0.4, 0.8 }, role = "trim", name = "SillL", x = -20, y = 3.6, z = 32.4 },
			{ block = { 14, 0.4, 0.8 }, role = "trim", name = "SillR", x = 20, y = 3.6, z = 32.4 },
			{ block = { 22, 1.2, 0.4 }, role = "trim", name = "PlinthL", x = -23, y = -1, z = 32.4 },
			{ block = { 22, 1.2, 0.4 }, role = "trim", name = "PlinthR", x = 23, y = -1, z = 32.4 },
			-- four downpipes against the side walls, under the gutters, from the ground up to them
			{ block = { 0.6, 15.2, 0.6 }, role = "dark", look = "pitch", name = "PipeLF", x = -34.4, y = -1, z = 31 },
			{ block = { 0.6, 15.2, 0.6 }, role = "dark", look = "pitch", name = "PipeRF", x = 34.4, y = -1, z = 31 },
			{ block = { 0.6, 15.2, 0.6 }, role = "dark", look = "pitch", name = "PipeLB", x = -34.4, y = -1, z = -33 },
			{ block = { 0.6, 15.2, 0.6 }, role = "dark", look = "pitch", name = "PipeRB", x = 34.4, y = -1, z = -33 },
		},
		furniture = {},
	},
	{ -- 2 Small Office: one story, white, WallDoor with its leaf swung open flat against the facade, windows, two plants
		key = "Seed", bandFloor = true, name = "Small Office",
		masses = { { half = 36.2, back = -36.2, front = 32.2, from = 1, to = 1, corners = true, roofEdge = true,
			doorWall = { F, K("WallWindow"), gap(24), K("WallWindow"), F }, sideWall = { F, K("WallWindow"), K("WallWindow"), F },
			backWall = { F, K("WallWindow"), F } } },
		door = { half = 4.5, top = 9 }, -- the WallDoor (an extra, stretched to 24) has a 9-wide opening, its frame on the lane's edges (P1)
		sign = { y = 10.2, w = 18, h = 2.6 }, -- over the door, under the roof edge (13)
		extras = {
			-- in the wall's 24-stud gap; lane = true only because the kit's one wall mesh spans its own opening
			{ key = "WallDoor", x = 0, y = -1, z = 31.2, turn = 0, width = 24, lane = true },
			{ key = "DoorLeaf", x = -9.1, y = -1, z = 32.45, turn = 0, width = 9 }, -- open flat against the facade, left of the opening
			{ key = "Plant", x = -15.5, y = -1, z = 34, turn = 0 },
			{ key = "Plant", x = 15.5, y = -1, z = 34, turn = 0 },
		},
		furniture = {
			{ key = "ReceptionDesk", side = "left", along = 16 },
			{ key = "Plant", side = "left", along = 26.5 },
			{ key = "Sofa", side = "right", along = 16 },
		},
	},
	{ -- 3 Big Office: two stories, white and warm wood, glass beside the door, windows above
		key = "SeriesA", bandFloor = true, name = "Big Office",
		masses = { { half = 38, back = -38, front = 32.2, from = 1, to = 2, corners = true, roofEdge = true, ceiling = true,
			doorWall = { F, K("WallGlass"), gap(24), K("WallGlass"), F }, frontWall = { F, K("WallWindow"), K("WallWindow"), K("WallWindow"), F },
			sideWall = { F, K("WallWindow"), K("WallWindow"), F }, backWall = { F, K("WallWindow"), F } } },
		door = { half = 4.5, top = 9 }, -- the stretched WallDoor, as in the Small Office
		sign = { y = 10.2, w = 18, h = 2.6 }, -- over the door, on the ground story
		extras = {
			{ key = "WallDoor", x = 0, y = -1, z = 31.2, turn = 0, width = 24, lane = true },
			{ key = "DoorLeaf", x = -9.1, y = -1, z = 32.45, turn = 0, width = 9 },
			{ key = "Plant", x = -15.5, y = -1, z = 34, turn = 0 },
			{ key = "Plant", x = 15.5, y = -1, z = 34, turn = 0 },
		},
		furniture = {
			{ key = "ReceptionDesk", side = "left", along = 16 },
			{ key = "Plant", side = "left", along = 26.5 },
			{ key = "Sofa", side = "right", along = 16 },
			{ key = "CoffeeMachine", side = "right", along = 26 },
			{ key = "Whiteboard", side = "back", along = -18 },
			{ key = "Shelf", side = "back", along = 18 },
		},
	},
	{ -- 4 Small Corporate: four stories of blue glass, a darker crown, an open entrance between two pillars
		key = "SeriesB", bandFloor = true, name = "Small Corporate",
		masses = { { half = 40, back = -40, front = 32.2, from = 1, to = 4, roofEdge = true, ceiling = true,
			doorWall = { F, K("WallGlass"), gap(10), K("WallGlass"), F }, frontWall = { F, K("WallGlass"), K("WallGlass"), K("WallGlass"), K("WallGlass"), F },
			sideWall = { F }, backWall = { F } } },
		-- An open entrance 10 wide. No RevolvingDoor: on the lane players walked through its middle post, and beside the
		-- doorway (10 x 10) it would cut through the glass wall or reach past z 40.
		door = { half = 5, top = 11 },
		sign = { y = 11.3, w = 14, h = 2.4, z = 32.7 }, -- on the band over the door (its front face is z 32.7)
		extras = {
			{ key = "RoofEdge", x = 0, y = 11, z = 31.7, turn = 0, width = 10 }, -- a band over the door (P3: pillars below)
			{ key = "Corner", x = -6, y = -1, z = 33.2, turn = 0 },
			{ key = "Corner", x = 6, y = -1, z = 33.2, turn = 0 },
		},
		furniture = {
			{ key = "ReceptionDesk", side = "left", along = 16 },
			{ key = "Plant", side = "left", along = 26.5 },
			{ key = "Sofa", side = "right", along = 16 },
			{ key = "CoffeeMachine", side = "right", along = 26 },
			{ key = "Whiteboard", side = "back", along = -18 },
			{ key = "Shelf", side = "back", along = 18 },
			{ key = "Armchair", side = "right", along = 6 },
			{ key = "Armchair", side = "right", along = 0 },
			{ key = "LobbyTree", side = "left", along = 4 },
			{ key = "LobbyTree", side = "left", along = -8 },
			{ key = "ServerRack", side = "back", along = 0 },
		},
	},
	{ -- 5 Big Corporate: a marble podium on the whole lot, a five-story dark glass tower, columns, a crown, gold
		key = "IpoReady", bandFloor = true, name = "Big Corporate",
		masses = {
			{ half = 41.2, back = -42.2, front = 32.2, from = 1, to = 1, roofEdge = true,
				doorWall = { F, K("WallGlass"), gap(18), K("WallGlass"), F }, sideWall = { F }, backWall = { F } },
			{ half = 26, back = -18, front = 14, from = 2, to = 6, roofEdge = true, crown = true, look = "tower",
				frontWall = { K("WallGlass"), K("WallGlass"), K("WallGlass") }, sideWall = { F }, backWall = { F } },
		},
		-- an open entrance 12 wide under a RoofEdge lintel, between two columns standing in the wall's gap (x 6 to 9 each side)
		door = { half = 6, top = 10, lintel = true },
		sign = { y = 13.2, w = 16, h = 2.6 }, -- on the podium's roof edge (13 to 16), above the columns (14 high from the ground)
		extras = {
			{ key = "Column", x = -7.5, y = -1, z = 31.7, turn = 0 },
			{ key = "Column", x = 7.5, y = -1, z = 31.7, turn = 0 },
		},
		backBand = 8, -- P2: the BoardTable, the Rug and the Bell are 6 to 8 deep
		furniture = {
			{ key = "ReceptionDesk", side = "left", along = 16 },
			{ key = "Plant", side = "left", along = 26.5 },
			{ key = "Sofa", side = "right", along = 16 },
			{ key = "CoffeeMachine", side = "right", along = 26 },
			{ key = "Whiteboard", side = "back", along = -33 },
			{ key = "Shelf", side = "back", along = 26 },
			{ key = "Armchair", side = "right", along = 6 },
			{ key = "Armchair", side = "right", along = 0 },
			{ key = "LobbyTree", side = "left", along = 4 },
			{ key = "LobbyTree", side = "left", along = -8 },
			{ key = "ServerRack", side = "back", along = 18 },
			{ key = "Rug", side = "back", along = -22 },
			{ key = "BoardTable", side = "back", along = -4 },
			{ key = "Bell", side = "back", along = 11 },
		},
	},
}
PlotBuilding.BAND = 4 -- furniture stands in a band this deep along the shell's inner faces (a stage may set backBand)

-- Layout (pure) -----------------------------------------------------------------------------------------------------

local function shownStage(stage)
	local last = #PlotBuilding.Stages
	if type(stage) ~= "number" or stage ~= stage then
		return 1
	end
	return math.clamp(math.floor(stage), 1, last)
end
PlotBuilding.shownStage = shownStage

local function widthOf(key)
	local entry = PlotBuilding.KitManifest[key]
	return entry and entry.size[1]
end

-- One piece: name, key, x y z (bottom-center), turn, tilt (about its own X), sx sz (stretch: 1 = kit size), look,
-- size and role (a Block only), text (a Block only: the sign board, it carries the building's SurfaceGui),
-- group ("Fade": the shell, it fades; "Static": the furniture, it stays), lane (a door piece, allowed in the doorway lane)
local function addPiece(out, p)
	p.sx = p.sx or 1
	p.sz = p.sz or 1
	p.tilt = p.tilt or 0
	p.group = p.group or "Fade"
	table.insert(out, p)
	return p
end

-- A wall run along one line: from..to on the axis, at the other coordinate, facing turn, standing at y
local function wallRun(out, name, line, seq, look, door)
	local fixed, fills = 0, 0
	for _, item in ipairs(seq) do
		if item.fill then
			fills += 1
		elseif item.gap then
			fixed += item.gap
		else
			fixed += widthOf(item.key) or error("PlotBuilding: unknown kit key " .. tostring(item.key))
		end
	end
	local len = line.to - line.from
	local left = len - fixed
	if left < -1e-6 or (fills == 0 and math.abs(left) > 1e-6) then
		error(string.format("PlotBuilding: %s is %.2f long but its pieces need %.2f", name, len, fixed))
	end
	local fillLen = fills > 0 and left / fills or 0
	local pos = line.from
	for i, item in ipairs(seq) do
		local w = item.fill and fillLen or item.gap or widthOf(item.key)
		if not item.gap and w > 1e-6 then
			local c = pos + w / 2
			local key = item.fill and "Wall" or item.key
			addPiece(out, {
				name = name .. i, key = key, x = line.axis == "x" and c or line.at, y = line.y, z = line.axis == "x" and line.at or c,
				turn = line.turn, sx = item.fill and w / widthOf("Wall") or 1, look = look,
				lane = door and door.lanePiece == key or nil,
			})
		end
		pos += w
	end
end

-- A pitched roof on a mass whose walls end at `top`: two sheets (Blocks, tilted) from 1 past each side wall up to a ridge
-- along Z, over the whole depth between the gables. Their top face rises `slope` studs per stud from the eave (the roof
-- edge's top) to the middle. The gables front and back step up in tiers as high as the roof edge, each `run` narrower on
-- both sides, and always reach the sheets' top: the outer corner of each step is on the slope (crow steps). Each tier has
-- a coping on top. A ridge cap and two gutters under the eaves. Looks only: the roof's solid box stays the flat one.
local function pitchedRoof(out, m, mass, top)
	local p, h, W = mass.pitch, mass.half, PlotBuilding.WALL
	local tierH = PlotBuilding.KitManifest.RoofEdge.size[2]
	local eave = top + (mass.roofEdge and tierH or 0)
	local s, T = p.slope, PlotBuilding.PITCH_THICK
	local run = tierH / s
	local tiers = math.ceil(h * s / tierH - 1e-9)
	local z0, z1 = mass.back + W, mass.front - W
	local cz, depth = (z0 + z1) / 2, z1 - z0
	local reach = h + p.overhang
	local a = math.atan(s)
	local mid = reach / 2
	local tag = "M" .. m
	for _, side in ipairs({ -1, 1 }) do
		local lr = side < 0 and "L" or "R"
		-- turned to face outward, tilted down by the slope: its top face's middle is on the slope, halfway out
		addPiece(out, { name = tag .. "Pitch" .. lr, key = PlotBuilding.BLOCK, size = { depth, T, reach / math.cos(a) }, role = "main", look = "pitch",
			x = side * (mid - math.sin(a) * T), y = eave + (h - mid) * s - math.cos(a) * T, z = cz, turn = side < 0 and 270 or 90, tilt = math.deg(a) })
		addPiece(out, { name = tag .. "Gutter" .. lr, key = PlotBuilding.BLOCK, size = { 0.8, 0.6, depth }, role = "dark", look = "pitch",
			x = side * (reach - 0.2), y = eave - p.overhang * s - T - 0.6, z = cz, turn = 0 })
	end
	addPiece(out, { name = tag .. "Ridge", key = PlotBuilding.BLOCK, size = { 2, 0.6, depth }, role = "dark", look = "pitch", x = 0, y = eave + h * s - 0.3, z = cz, turn = 0 })
	for k = 1, tiers do
		local half, y = h - (k - 1) * run, eave + (k - 1) * tierH
		for _, g in ipairs({ { "F", mass.front - W / 2, 0 }, { "B", mass.back + W / 2, 180 } }) do
			addPiece(out, { name = tag .. "Gable" .. g[1] .. k, key = PlotBuilding.BLOCK, size = { 2 * half, tierH, W }, role = "main", look = mass.look,
				x = 0, y = y, z = g[2], turn = g[3] })
			addPiece(out, { name = tag .. "Coping" .. g[1] .. k, key = PlotBuilding.BLOCK, size = { 2 * half + 0.4, 0.4, W + 0.4 }, role = "trim", look = mass.look,
				x = 0, y = y + tierH, z = g[2], turn = g[3] })
		end
	end
end

-- The sign on the facade over the door: a plate, the board on it (it carries the text, PlotBuilding.SIGN_TEXT) and a growth
-- chart of three bars on the board's left (the emblem; no odds). Its bottom at sign.y, centered, standing out of the front
-- face (from sign.z, FRONT_OUT by default, to 0.7 in front of it). The bars are drawn for an 18-wide board and shrink with it.
local function addSign(out, sign)
	local w, h, y, z = sign.w, sign.h, sign.y, sign.z or PlotBuilding.FRONT_OUT
	local B, k = PlotBuilding.BLOCK, sign.w / 18
	addPiece(out, { name = "SignPlate", key = B, size = { w + 0.6, h + 0.6, 0.3 }, role = "trim", look = "sign", x = 0, y = y - 0.3, z = z + 0.15, turn = 0 })
	addPiece(out, { name = "SignBoard", key = B, size = { w, h, 0.2 }, role = "dark", look = "sign", x = 0, y = y, z = z + 0.4, turn = 0, text = true })
	for i, share in ipairs({ 0.28, 0.48, 0.68 }) do
		addPiece(out, { name = "SignBar" .. i, key = B, size = { 2 * k, h * share, 0.2 }, role = "accent", look = "sign", x = -w / 2 + k * (2.2 + (i - 1) * 2.6), y = y + h * 0.16, z = z + 0.6, turn = 0 })
	end
end

-- The layout of one stage. Errors on data that can't be laid out (tools/building_test.py lays out all five).
function PlotBuilding.layout(stage)
	local shown = shownStage(stage)
	local def = PlotBuilding.Stages[shown]
	local W, GR, ST = PlotBuilding.WALL, PlotBuilding.GROUND, PlotBuilding.STORY
	local pieces, furniture = {}, {}
	local outer = def.masses[1]
	local top1 = GR + ST * outer.to -- the outer mass's top: where its walls and the roof box end
	for m, mass in ipairs(def.masses) do
		local h, back, front = mass.half, mass.back, mass.front
		local isOuter = m == 1
		for k = mass.from, mass.to do
			local y = GR + ST * (k - 1)
			local tag = "M" .. m .. "S" .. k
			local frontSeq = (k == 1 and mass.doorWall) or mass.frontWall or mass.doorWall
			local d = (isOuter and k == 1) and def.door or nil
			if mass.corners then
				for _, c in ipairs({ { -1, 1 }, { 1, 1 }, { -1, -1 }, { 1, -1 } }) do
					addPiece(pieces, { name = tag .. "Corner" .. (c[1] < 0 and "L" or "R") .. (c[2] > 0 and "F" or "B"), key = "Corner",
						x = c[1] * (h - W / 2), y = y, z = c[2] > 0 and front - W / 2 or back + W / 2, turn = c[2] > 0 and 0 or 180, look = mass.look })
				end
			end
			local sideFrom = mass.corners and back + W or back
			local sideTo = mass.corners and front - W or front
			wallRun(pieces, tag .. "Front", { axis = "x", from = -h + W, to = h - W, at = front - W / 2, turn = 0, y = y }, frontSeq, mass.look, d)
			wallRun(pieces, tag .. "Back", { axis = "x", from = -h + W, to = h - W, at = back + W / 2, turn = 180, y = y }, mass.backWall, mass.look)
			wallRun(pieces, tag .. "Left", { axis = "z", from = sideFrom, to = sideTo, at = -h + W / 2, turn = 270, y = y }, mass.sideWall, mass.look)
			wallRun(pieces, tag .. "Right", { axis = "z", from = sideFrom, to = sideTo, at = h - W / 2, turn = 90, y = y }, mass.sideWall, mass.look)
		end
		local top = GR + ST * mass.to
		-- The ceiling over the ground floor (only when stories stand above it: upper stories are hollow) and the roof
		local innerW, innerD = 2 * (h - W), (front - W) - (back + W)
		local cz = ((front - W) + (back + W)) / 2
		local fw = widthOf("Floor")
		if mass.ceiling then
			addPiece(pieces, { name = "M" .. m .. "Ceiling", key = "Floor", x = 0, y = GR + ST - 1, z = cz, turn = 0, sx = innerW / fw, sz = innerD / fw, look = "roof" })
		end
		addPiece(pieces, { name = "M" .. m .. "Roof", key = "Floor", x = 0, y = top - 1, z = cz, turn = 0, sx = innerW / fw, sz = innerD / fw, look = "roof" })
		if mass.roofEdge then
			local ew = widthOf("RoofEdge")
			addPiece(pieces, { name = "M" .. m .. "EdgeFront", key = "RoofEdge", x = 0, y = top, z = front - W / 2, turn = 0, sx = 2 * h / ew, look = mass.look })
			addPiece(pieces, { name = "M" .. m .. "EdgeBack", key = "RoofEdge", x = 0, y = top, z = back + W / 2, turn = 180, sx = 2 * h / ew, look = mass.look })
			addPiece(pieces, { name = "M" .. m .. "EdgeLeft", key = "RoofEdge", x = -h + W / 2, y = top, z = cz, turn = 270, sx = innerD / ew, look = mass.look })
			addPiece(pieces, { name = "M" .. m .. "EdgeRight", key = "RoofEdge", x = h - W / 2, y = top, z = cz, turn = 90, sx = innerD / ew, look = mass.look })
		end
		if mass.crown then
			addPiece(pieces, { name = "M" .. m .. "Crown", key = "RoofCrown", x = 0, y = top, z = cz, turn = 0, look = mass.look })
		end
		if mass.pitch then
			pitchedRoof(pieces, m, mass, top)
		end
	end
	-- The door's lintel (an open entrance) and the pieces outside the walls
	local door = def.door
	if door.lintel then
		addPiece(pieces, { name = "DoorLintel", key = "RoofEdge", x = 0, y = door.top, z = PlotBuilding.FRONT_IN + W / 2, turn = 0, sx = 2 * door.half / widthOf("RoofEdge") })
	end
	if def.sign then
		addSign(pieces, def.sign)
	end
	for i, e in ipairs(def.extras) do
		if e.block then
			addPiece(pieces, { name = "Extra" .. i .. e.name, key = PlotBuilding.BLOCK, size = e.block, role = e.role, look = e.look,
				x = e.x, y = e.y, z = e.z, turn = e.turn or 0, tilt = e.tilt })
		else
			addPiece(pieces, { name = "Extra" .. i .. e.key, key = e.key, x = e.x, y = e.y, z = e.z, turn = e.turn, tilt = e.tilt,
				sx = e.width and e.width / widthOf(e.key) or 1, lane = e.lane })
		end
	end
	-- The band's floor (stages with furniture): three strips around the room, level with its Floor (top at y 0), each with a
	-- solid box under it, so a player walks around the room at the room's height. Never in front: the front wall is there.
	local inner, backInner = outer.half - W, outer.back + W
	local edge = PlotBuilding.ROOM_EDGE
	local bandBoxes = {}
	if def.bandFloor then
		local fw = widthOf("Floor")
		local strips = {
			{ "BandLeft", -inner, -edge, backInner, PlotBuilding.FRONT_IN },
			{ "BandRight", edge, inner, backInner, PlotBuilding.FRONT_IN },
			{ "BandBack", -edge, edge, backInner, -edge },
		}
		for _, s in ipairs(strips) do
			addPiece(pieces, { name = s[1], key = "Floor", x = (s[2] + s[3]) / 2, y = GR, z = (s[4] + s[5]) / 2, turn = 0,
				sx = (s[3] - s[2]) / fw, sz = (s[5] - s[4]) / fw, look = "floor", group = "Static" })
			table.insert(bandBoxes, { name = s[1], box = { s[2], s[3], GR, 0, s[4], s[5] } })
		end
	end
	-- Furniture: against the shell's inner faces, facing the room, in the band, on the band's floor
	for i, f in ipairs(def.furniture) do
		local s = PlotBuilding.KitManifest[f.key].size
		local depth = s[3]
		local p = { name = "Furniture" .. i .. f.key, key = f.key, y = def.bandFloor and 0 or GR, group = "Static" }
		if f.side == "left" then
			p.x, p.z, p.turn = -inner + depth / 2, f.along, 90
		elseif f.side == "right" then
			p.x, p.z, p.turn = inner - depth / 2, f.along, 270
		else
			p.x, p.z, p.turn = f.along, backInner + depth / 2, 0
		end
		addPiece(pieces, p)
		local wx, wz = s[1], depth
		if f.side ~= "back" then
			wx, wz = depth, s[1]
		end
		table.insert(furniture, { key = f.key, side = f.side, x0 = p.x - wx / 2, x1 = p.x + wx / 2, z0 = p.z - wz / 2, z1 = p.z + wz / 2, top = p.y + s[2] })
	end

	-- The solid boxes: the outer mass's walls (the doorway left open) and its roof. Invisible; the only solid parts.
	local h, back, front = outer.half, outer.back, outer.front
	local function solid(name, x0, x1, y0, y1, z0, z1)
		return { name = name, box = { x0, x1, y0, y1, z0, z1 } }
	end
	local boxes = {
		solid("WallLeft", -h, -h + W, GR, top1, back, front),
		solid("WallRight", h - W, h, GR, top1, back, front),
		solid("WallBack", -h + W, h - W, GR, top1, back, back + W),
		solid("FrontLeft", -h + W, -door.half, GR, top1, front - W, front),
		solid("FrontRight", door.half, h - W, GR, top1, front - W, front),
		solid("Lintel", -door.half, door.half, door.top, top1, front - W, front), -- from the door's top (above the floor top)
		solid("Roof", -h + W, h - W, top1 - PlotBuilding.ROOF, top1, back + W, front - W), -- from 12.5 on one story: over a jump
	}
	for _, b2 in ipairs(bandBoxes) do
		table.insert(boxes, b2)
	end

	local inside = {
		minX = -h + W, maxX = h - W, minZ = back + W, maxZ = front - W,
		minY = -PlotBuilding.Inside.floorBelow, maxY = GR + ST - 1, -- the ground floor's ceiling
		-- the doorway and the apron count as inside only as wide as the lane (the Garage's door is 20 wide): the claim post
		-- (x 6 to 10) is never inside, so the shell never fades for someone standing at it
		doorMinX = -PlotBuilding.Lane.half, doorMaxX = PlotBuilding.Lane.half, doorDepth = W + PlotBuilding.APRON, margin = PlotBuilding.Inside.margin,
	}
	return {
		stage = shown, key = def.key, name = def.name, pieces = pieces, boxes = boxes, inside = inside, furniture = furniture,
		footprint = { x0 = -h, x1 = h, z0 = back, z1 = front, top = top1 }, height = GR + PlotBuilding.STORY * def.masses[#def.masses].to, door = door,
	}
end

-- The floor boxes the furniture of a stage takes: { key, x0, x1, z0, z1, top } in the garage's frame. Customize PR 2
-- keeps them free (CompanyConfig.checkPlacement is not changed by this file).
function PlotBuilding.furnitureFootprints(stage)
	return PlotBuilding.layout(stage).furniture
end

return PlotBuilding
