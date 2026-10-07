-- WorldVisuals: builds the world around the plots from WorldArt (branch world-icons-pass), and checks it.
-- Put this ModuleScript in ServerScriptService, next to WorldArt. The art itself (pieces, palette, numbers) is data
-- in WorldArt.
--
-- Only looks: nothing here is saved, sent through a remote or read back by the game. Every part is anchored and never
-- collides, is touched or stops a ray or the camera (CanCollide, CanTouch and CanQuery off): the paths are thin
-- colored layers on the Baseplate, which stays the only solid ground (with the game's own floors). No script, no
-- asset, nothing random. The builder only creates new parts inside its own Model; it never moves, resizes, renames,
-- re-parents or deletes anything else (the SpawnLocation, the Baseplate, the plots, the lounge).
--
-- No GetService and no require: the art and the site are passed in, so the same code runs in the game, in Studio's
-- command bar (the preview) and in tools/world_test.py.
--   WorldVisuals.site(art, spacing, count, centerOf)  -> the site's numbers (pure). centerOf(slot) is TycoonCore's
--                                                       plotCenter when wired; without it, the same formula
--   WorldVisuals.layout(art, site)                    -> every path, kerb, lawn, decor item and hill, placed (pure)
--   WorldVisuals.build(parent, art, site, palette)    -> Model "World" (palette: optional, another palette table)
--   WorldVisuals.ghosts(parent, site)                 -> see-through boxes where the plots and the lounge stand (preview only)
-- Checks (tools/world_test.py and the Studio preview run them):
--   WorldVisuals.validate(art)                        -> problems in the data (empty = fine)
--   WorldVisuals.checks(world, art, site, options)    -> { { name = ..., problems = { ... } }, ... }, one per named check
--   WorldVisuals.check(world, art, site, options)     -> every problem in one list
--   WorldVisuals.snapshot(parts) / WorldVisuals.compare(snapshot) -> proof that other parts were left as they were
--   WorldVisuals.studioFacts(site, spawn, baseplate)  -> the measured Studio facts against the real objects
--   WorldVisuals.clashes(world, others)               -> world parts that would go into other (hand-placed) parts
--
-- World coordinates, in studs. +Z is the plots' front (the default camera looks that way); y 0 is the Baseplate's top.

local WorldVisuals = {}

-- What the art may use. Neon only on lights: the part's name must say so (LIGHT_WORDS).
WorldVisuals.MATERIALS = {
	SmoothPlastic = true, Plastic = true, Concrete = true, Cobblestone = true, Brick = true, Wood = true, WoodPlanks = true,
	Metal = true, Fabric = true, Grass = true, Neon = true,
}
WorldVisuals.SHAPES = { Block = true, Cylinder = true, Ball = true }
WorldVisuals.FONTS = { GothamBold = true, FredokaOne = true, GothamBlack = true }
WorldVisuals.FACES = { Front = true, Back = true, Left = true, Right = true, Top = true }
WorldVisuals.LIGHT_WORDS = { "Lamp", "Light", "Glow", "Bulb" }
WorldVisuals.RESERVED_NAMES = { Floor = true, Baseplate = true, SpawnLocation = true, VipDoor = true, VipLounge = true }
WorldVisuals.FORBIDDEN_CLASSES = {
	Script = true, LocalScript = true, ModuleScript = true, Decal = true, Texture = true, SpecialMesh = true, MeshPart = true,
	Sound = true, ParticleEmitter = true, ClickDetector = true, ProximityPrompt = true, Seat = true, VehicleSeat = true,
	SpawnLocation = true, Beam = true, Trail = true,
}
WorldVisuals.CHECKS = { "data", "budget", "flags", "keepouts", "floating", "zfighting", "baseplate", "connected", "palette", "texts" }
WorldVisuals.TINY = 2 -- a part whose longest side is shorter than this casts no shadow
WorldVisuals.FLAT = 0.2 -- a part at most this tall lying on the ground is a ground layer (paving, lawn)
WorldVisuals.TOUCH = 0.06 -- parts closer than this touch (floating check)
WorldVisuals.OVERLAP = 0.01 -- a part must go this far into a zone to count as inside it
WorldVisuals.PLANE = 0.005 -- two faces closer than this lie on the same plane (they would flicker)
WorldVisuals.CONTACT = 4 -- two paths join when they share an edge at least this long
WorldVisuals.FACT = 0.01 -- tolerance when the Studio facts are compared with the real objects

-- Helpers ---------------------------------------------------------------------

local function finite(n)
	return type(n) == "number" and n == n and n ~= math.huge and n ~= -math.huge
end

local function colorOk(c)
	if type(c) ~= "table" or #c ~= 3 then
		return false
	end
	for i = 1, 3 do
		if type(c[i]) ~= "number" or c[i] % 1 ~= 0 or c[i] < 0 or c[i] > 255 then
			return false
		end
	end
	return true
end

local function rgb(c)
	return Color3.fromRGB(c[1], c[2], c[3])
end

-- A palette color by name. A name the palette doesn't have builds bright magenta (never an error): the palette
-- check names it, and in the game it shows instead of stopping the whole world.
local function colorOf(palette, key)
	local c = palette[key]
	if colorOk(c) then
		return rgb(c)
	end
	return Color3.fromRGB(255, 0, 255)
end

local function turn(r)
	if not r then
		return CFrame.new()
	end
	return CFrame.fromEulerAnglesYXZ(math.rad(r[1]), math.rad(r[2]), math.rad(r[3]))
end

local function isLightName(name)
	for _, word in ipairs(WorldVisuals.LIGHT_WORDS) do
		if string.find(name, word, 1, true) then
			return true
		end
	end
	return false
end

-- The world box around a part: { minX, maxX, minY, maxY, minZ, maxZ }
local function boxOf(cframe, size)
	local x, y, z, r00, r01, r02, r10, r11, r12, r20, r21, r22 = cframe:GetComponents()
	local hx = (math.abs(r00) * size.X + math.abs(r01) * size.Y + math.abs(r02) * size.Z) / 2
	local hy = (math.abs(r10) * size.X + math.abs(r11) * size.Y + math.abs(r12) * size.Z) / 2
	local hz = (math.abs(r20) * size.X + math.abs(r21) * size.Y + math.abs(r22) * size.Z) / 2
	return { x - hx, x + hx, y - hy, y + hy, z - hz, z + hz }
end
WorldVisuals.boxOf = boxOf

local function overlaps(a, b, margin)
	return a[1] < b[2] - margin and b[1] < a[2] - margin
		and a[3] < b[4] - margin and b[3] < a[4] - margin
		and a[5] < b[6] - margin and b[5] < a[6] - margin
end
WorldVisuals.overlaps = overlaps

-- A quarter turn has every rotation number at -1, 0 or 1 (the face checks need it)
local function quarterTurns(cframe)
	local comps = { cframe:GetComponents() }
	for i = 4, 12 do
		local v = comps[i]
		if math.abs(v) > 1e-6 and math.abs(math.abs(v) - 1) > 1e-6 then
			return false
		end
	end
	return true
end

-- The part above the ground: a Ball sunk into it shows only its cap, as wide as the circle where it meets y 0
local function aboveGround(shape, box)
	local b = { box[1], box[2], math.max(box[3], 0), box[4], box[5], box[6] }
	if shape == "Ball" and box[3] < 0 then
		local r = (box[2] - box[1]) / 2
		local cx, cy, cz = (box[1] + box[2]) / 2, (box[3] + box[4]) / 2, (box[5] + box[6]) / 2
		local a = cy >= 0 and r or math.sqrt(math.max(r * r - cy * cy, 0))
		b = { cx - a, cx + a, 0, cy + r, cz - a, cz + a }
	end
	return b
end
WorldVisuals.aboveGround = aboveGround

-- The site --------------------------------------------------------------------

-- The numbers of one site. spacing and count default to the art's copy of TycoonCore's; centerOf(slot) returns a plot
-- center (a Vector3: TycoonCore's plotCenter); without it the same formula as plotCenter is used.
function WorldVisuals.site(art, spacing, count, centerOf)
	local s = art.Site
	spacing = spacing or s.plotSpacing
	count = count or s.plotCount
	local plots = {}
	for slot = 1, count do
		if centerOf then
			local c = centerOf(slot)
			plots[slot] = { x = c.X, y = c.Y, z = c.Z }
		else
			plots[slot] = { x = -((count - 1) * spacing) / 2 + (slot - 1) * spacing, y = s.plotY, z = s.plotZ }
		end
	end
	local lc, ls = s.lounge.center, s.lounge.size
	local wall = 1 -- ShopServer's lounge walls are 1 stud thick, centered on the floor's edges
	local lounge = {
		x = lc[1], z = lc[3],
		halfX = ls[1] / 2 + wall / 2,
		back = lc[3] - ls[3] / 2 - wall / 2,
		front = lc[3] + ls[3] / 2 + wall / 2,
		floorTop = lc[2] + ls[2] / 2,
		door = s.lounge.doorWidth,
	}
	lounge.top = lounge.floorTop + s.lounge.wallHeight + s.lounge.signHeight + 0.5 -- the sign over the door, plus its gap
	lounge.drop = { x = lc[1], z = lounge.front - wall / 2 + s.lounge.dropOut } -- where a player without VIP is put back
	local sp, ss = s.spawn.position, s.spawn.size
	local bp, bs = s.baseplate.position, s.baseplate.size
	local site = {
		spacing = spacing, count = count, plots = plots,
		floor = { s.floorSize[1], s.floorSize[2], s.floorSize[3] },
		reach = s.plotReach, signs = s.signs, signBoard = s.signBoard, signPostHeight = s.signPostHeight, signBoardY = s.signBoardY,
		lounge = lounge,
		spawn = { x = sp[1], z = sp[3], halfX = ss[1] / 2, halfZ = ss[3] / 2, top = sp[2] + ss[2] / 2 },
		spawnFact = { position = sp, size = ss },
		baseplateFact = { position = bp, size = bs },
		ground = { x0 = bp[1] - bs[1] / 2, x1 = bp[1] + bs[1] / 2, z0 = bp[3] - bs[3] / 2, z1 = bp[3] + bs[3] / 2, top = bp[2] + bs[2] / 2 },
	}
	-- The Studio preview rooms (placed for the game's own spacing) count only at that spacing, and only while they
	-- don't stand on a plot of this site; at another spacing the preview snippet has to move (docs/WORLD_ICONS_NOTES.md)
	local pv = s.previewStages
	if pv and spacing == s.plotSpacing then
		local box = { pv.x0 - pv.reach, pv.x1 + pv.reach, 0, 40, pv.z0 - pv.reach, pv.z1 + pv.reach }
		local onPlot = nil
		for i, p in ipairs(plots) do
			local r = site.reach
			if overlaps(box, { p.x - r.side, p.x + r.side, 0, 40, p.z - r.back, p.z + r.front }, 0) then
				onPlot = onPlot or i
			end
		end
		site.preview = not onPlot and box or nil
		site.previewOnPlot = onPlot
	end
	return site
end

-- The layout (pure) -----------------------------------------------------------------

-- Gap lines: halfway between two plots, plus one half a spacing beyond each end of the row
function WorldVisuals.gapLines(site)
	local plots, gaps = site.plots, {}
	gaps[0] = plots[1].x - site.spacing / 2
	for k = 1, #plots - 1 do
		gaps[k] = (plots[k].x + plots[k + 1].x) / 2
	end
	gaps[#plots] = plots[#plots].x + site.spacing / 2
	return gaps
end

-- Every rectangle and placement of the world. Rectangles are { name, x0, x1, z0, z1, color }; items are
-- { piece, name, x, z, yaw, lit, slot }; hills are WorldArt.Hills entries.
function WorldVisuals.layout(art, site)
	local L = art.Layout
	local plan = { paths = {}, kerbs = {}, ground = {}, items = {}, hills = {} }
	local half, kw = L.pathWidth / 2, L.kerbWidth
	local function rect(list, name, x0, x1, z0, z1, color)
		if x1 > x0 and z1 > z0 then
			table.insert(list, { name = name, x0 = x0, x1 = x1, z0 = z0, z1 = z1, color = color })
		end
	end
	local function item(piece, name, x, z, yaw, extra)
		local it = { piece = piece, name = name, x = x, z = z, yaw = yaw or 0 }
		for k, v in pairs(extra or {}) do
			it[k] = v
		end
		table.insert(plan.items, it)
	end
	local trees = { "TreeA", "TreeB", "TreeC" }
	local function treeAt(n)
		return trees[(n - 1) % #trees + 1]
	end

	-- The spawn plaza: four slabs around the pad and its bare margin, kerbs round it, open where the avenue leaves
	local sp, lg = site.spawn, site.lounge
	local cx, cz, ax = sp.x, sp.z, lg.x
	local P = L.plazaHalf
	local hx, hz = sp.halfX + L.spawnMargin, sp.halfZ + L.spawnMargin
	local px0, px1, pz0, pz1 = cx - P, cx + P, cz - P, cz + P
	rect(plan.paths, "PlazaSouth", px0, px1, pz0, cz - hz, "Plaza")
	rect(plan.paths, "PlazaNorth", px0, px1, cz + hz, pz1, "Plaza")
	rect(plan.paths, "PlazaWest", px0, cx - hx, cz - hz, cz + hz, "Plaza")
	rect(plan.paths, "PlazaEast", cx + hx, px1, cz - hz, cz + hz, "Plaza")
	rect(plan.kerbs, "KerbPlazaSouth", px0 - kw, px1 + kw, pz0 - kw, pz0)
	rect(plan.kerbs, "KerbPlazaWest", px0 - kw, px0, pz0, pz1)
	rect(plan.kerbs, "KerbPlazaEast", px1, px1 + kw, pz0, pz1)
	rect(plan.kerbs, "KerbPlazaNorthWest", px0 - kw, ax - half, pz1, pz1 + kw)
	rect(plan.kerbs, "KerbPlazaNorthEast", ax + half, px1 + kw, pz1, pz1 + kw)
	local inset = L.plazaLampInset
	local corners = { { px0 + inset, pz0 + inset }, { px1 - inset, pz0 + inset }, { px0 + inset, pz1 - inset }, { px1 - inset, pz1 - inset } }
	for i, c in ipairs(corners) do
		item("Lamp", "PlazaLamp" .. i, c[1], c[2], 0, { lit = true })
	end
	for i, b in ipairs(L.benches) do
		item("Bench", "PlazaBench" .. i, cx + b[1], cz + b[2], b[3])
	end
	for i, p in ipairs(L.planters) do
		item("Planter", "PlazaPlanter" .. i, cx + p[1], cz + p[2])
	end
	local t = L.plazaTrees
	for i, c in ipairs({ { -t, -t }, { t, -t }, { -t, t }, { t, t } }) do
		item(treeAt(i), "PlazaTree" .. i, cx + c[1], cz + c[2])
	end
	item("Arch", "WelcomeArch", ax, pz1 + L.archOut)

	-- The avenue, the cross walk behind the lounge, the two arms around it and the forecourt at its door
	local crossZ1 = lg.back - L.crossGap
	local crossZ0 = crossZ1 - L.pathWidth
	local armIn = lg.halfX + L.armGap
	local armOut = armIn + L.pathWidth
	local foreZ0 = lg.front + L.loungeMargin
	local backZ0 = foreZ0 + L.forecourtDepth
	local backZ1 = backZ0 + L.pathWidth
	rect(plan.paths, "Avenue", ax - half, ax + half, pz1, crossZ0, "Path")
	rect(plan.paths, "CrossWalk", ax - armOut, ax + armOut, crossZ0, crossZ1, "Path")
	rect(plan.paths, "ArmWest", ax - armOut, ax - armIn, crossZ1, backZ0, "Path")
	rect(plan.paths, "ArmEast", ax + armIn, ax + armOut, crossZ1, backZ0, "Path")
	rect(plan.paths, "Forecourt", ax - armIn, ax + armIn, foreZ0, backZ0, "Plaza")
	rect(plan.kerbs, "KerbCrossWest", ax - armOut - kw, ax - half, crossZ0 - kw, crossZ0)
	rect(plan.kerbs, "KerbCrossEast", ax + half, ax + armOut + kw, crossZ0 - kw, crossZ0)
	rect(plan.kerbs, "KerbArmWest", ax - armOut - kw, ax - armOut, crossZ0, backZ0 - kw)
	rect(plan.kerbs, "KerbArmEast", ax + armOut, ax + armOut + kw, crossZ0, backZ0 - kw)
	rect(plan.ground, "MeadowWest", ax - armOut - kw - L.meadowWidth, ax - armOut - kw, crossZ0 - kw, backZ0 - kw, "Meadow")
	rect(plan.ground, "MeadowEast", ax + armOut + kw, ax + armOut + kw + L.meadowWidth, crossZ0 - kw, backZ0 - kw, "Meadow")
	for i, dz in ipairs(L.hedgeZ) do
		item("Hedge", "HedgeWest" .. i, ax - lg.halfX - L.armGap / 2, lg.z + dz)
		item("Hedge", "HedgeEast" .. i, ax + lg.halfX + L.armGap / 2, lg.z + dz)
	end
	item("Lamp", "ForecourtLampWest", ax - armIn + inset, (foreZ0 + backZ0) / 2, 0, { lit = true })
	item("Lamp", "ForecourtLampEast", ax + armIn - inset, (foreZ0 + backZ0) / 2, 0, { lit = true })
	item(treeAt(2), "CrossTreeWest", ax - armOut - L.crossTrees, (crossZ0 + crossZ1) / 2)
	item(treeAt(3), "CrossTreeEast", ax + armOut + L.crossTrees, (crossZ0 + crossZ1) / 2)

	-- The back street, the connectors between the plots and the front street, one piece per plot block
	local plots, r = site.plots, site.reach
	local gaps = WorldVisuals.gapLines(site)
	local n = #plots
	-- The two end connectors move out when the spacing is tight, so they always clear the end plots
	local endRoom = r.side + L.connectorClear + half
	gaps[0] = math.min(gaps[0], plots[1].x - endRoom)
	gaps[n] = math.max(gaps[n], plots[n].x + endRoom)
	local frontReach, floorFront = -math.huge, -math.huge
	for _, p in ipairs(plots) do
		frontReach = math.max(frontReach, p.z + r.front)
		floorFront = math.max(floorFront, p.z + site.floor[3] / 2)
	end
	local frontZ0 = frontReach + L.frontGap
	local frontZ1 = frontZ0 + L.pathWidth
	local west, east = gaps[0] - half, gaps[n] + half
	for i = 1, n do
		local x0 = i == 1 and west or gaps[i - 1]
		local x1 = i == n and east or gaps[i]
		rect(plan.paths, "BackStreet" .. i, x0, x1, backZ0, backZ1, "Street")
		rect(plan.paths, "FrontStreet" .. i, x0, x1, frontZ0, frontZ1, "Street")
		local p = plots[i]
		rect(plan.paths, "Walk" .. i, p.x - L.walkWidth / 2, p.x + L.walkWidth / 2, p.z + site.floor[3] / 2, frontZ0, "Walk")
	end
	for k = 0, n do
		local g = gaps[k]
		local roomLeft = k == 0 or (g - half) - (plots[k].x + r.side) >= L.connectorClear
		local roomRight = k == n or (plots[k + 1].x - r.side) - (g + half) >= L.connectorClear
		if roomLeft and roomRight then
			rect(plan.paths, "Connector" .. k, g - half, g + half, backZ1, frontZ0, "Path")
		end
	end
	rect(plan.kerbs, "KerbBackWest", west, ax - armOut, backZ0 - kw, backZ0)
	rect(plan.kerbs, "KerbBackEast", ax + armOut, east, backZ0 - kw, backZ0)
	rect(plan.kerbs, "KerbFront", west, east, frontZ1, frontZ1 + kw)
	rect(plan.kerbs, "KerbWestEnd", west - kw, west, backZ0 - kw, frontZ1 + kw)
	rect(plan.kerbs, "KerbEastEnd", east, east + kw, backZ0 - kw, frontZ1 + kw)
	local far = frontZ1 + kw
	rect(plan.ground, "FrontLawn", west - kw, east + kw, far, far + L.lawnDepth, "Lawn")

	-- Across the street from each plot: its number, a bush, two trees; a lamp at every gap line
	for i, p in ipairs(plots) do
		item("Sign", "StreetSign" .. i, p.x + L.signDX, far + L.signDZ, 0, { slot = i })
		item("Bush", "StreetBush" .. i, p.x + L.bushDX, far + L.bushDZ)
		item(treeAt(2 * i - 1), "StreetTree" .. (2 * i - 1), p.x - L.treeDX, far + L.treeDZ)
		item(treeAt(2 * i), "StreetTree" .. (2 * i), p.x + L.treeDX, far + L.treeDZ)
	end
	for k = 0, n do
		item("Lamp", "StreetLamp" .. k, gaps[k], far + L.lampDZ)
	end
	-- Behind the back street, beyond the lounge loop: a tree at each gap line
	for k = 0, n do
		if math.abs(gaps[k] - ax) >= armOut + 8 then
			item(treeAt(k + 1), "BackTree" .. k, gaps[k], backZ0 - kw - L.backTreeDZ)
		end
	end

	for _, hill in ipairs(art.Hills) do
		table.insert(plan.hills, hill)
	end
	plan.frontZ0, plan.backZ1, plan.floorFront = frontZ0, backZ1, floorFront
	return plan
end

-- Building ----------------------------------------------------------------------------

local function decorate(part, longest, flat, neon)
	part.Anchored = true
	part.CanCollide = false
	part.CanQuery = false
	part.CanTouch = false
	part.TopSurface = Enum.SurfaceType.Smooth
	part.BottomSurface = Enum.SurfaceType.Smooth
	part.CastShadow = longest >= WorldVisuals.TINY and not flat and not neon
end

-- A flat piece on the ground: a path slab, a kerb or a lawn (height = its top, its foot on y 0)
local function slab(parent, r, height, color, material)
	local part = Instance.new("Part")
	part.Name = r.name
	part.Shape = Enum.PartType.Block
	part.Size = Vector3.new(r.x1 - r.x0, height, r.z1 - r.z0)
	part.CFrame = CFrame.new((r.x0 + r.x1) / 2, height / 2, (r.z0 + r.z1) / 2)
	part.Color = color
	part.Material = Enum.Material[material]
	decorate(part, math.max(r.x1 - r.x0, r.z1 - r.z0), height <= WorldVisuals.FLAT, false)
	part.Parent = parent
	return part
end

local function addText(part, text, palette, slot)
	for _, face in ipairs(text.faces or { "Back" }) do
		if not WorldVisuals.FACES[face] then
			continue -- the data check names it; the build goes on without that face
		end
		local gui = Instance.new("SurfaceGui")
		gui.Name = "Text" .. face
		gui.Face = Enum.NormalId[face]
		gui.SizingMode = Enum.SurfaceGuiSizingMode.PixelsPerStud
		gui.PixelsPerStud = 40
		gui.LightInfluence = text.glow and 0 or 1
		local label = Instance.new("TextLabel")
		label.Name = "Label"
		label.Size = UDim2.fromScale(1, 1)
		label.BackgroundTransparency = 1
		label.TextScaled = true
		label.Font = Enum.Font[text.font or "GothamBold"]
		label.TextColor3 = colorOf(palette, text.color)
		label.Text = text.slot and tostring(slot) or text.value
		label.Parent = gui
		gui.Parent = part
	end
end

-- One part of a piece, placed at base * offset * rotation
local function piecePart(parent, base, spec, palette, slot)
	local part = Instance.new("Part")
	part.Name = spec.name
	part.Shape = Enum.PartType[spec.shape]
	part.Size = Vector3.new(spec.size[1], spec.size[2], spec.size[3])
	part.CFrame = base * CFrame.new(spec.offset[1], spec.offset[2], spec.offset[3]) * turn(spec.rot)
	part.Color = colorOf(palette, spec.color)
	part.Material = Enum.Material[spec.material]
	local box = boxOf(part.CFrame, part.Size)
	decorate(part, math.max(spec.size[1], spec.size[2], spec.size[3]), box[4] - box[3] <= WorldVisuals.FLAT, spec.material == "Neon")
	if spec.text then
		addText(part, spec.text, palette, slot)
	end
	part.Parent = parent
	return part
end

-- The whole world, in a Model named World. palette: another palette table (a sector's), or WorldArt's.
function WorldVisuals.build(parent, art, site, palette)
	palette = palette or art.Palette
	local L = art.Layout
	local plan = WorldVisuals.layout(art, site)
	local world = Instance.new("Model")
	world.Name = "World"
	world:SetAttribute("Spacing", site.spacing)
	world:SetAttribute("Plots", site.count)
	local function group(name)
		local g = Instance.new("Model")
		g.Name = name
		g.Parent = world
		return g
	end
	local paths, kerbs, ground, decor, hills = group("Paths"), group("Kerbs"), group("Ground"), group("Decor"), group("Hills")
	for _, r in ipairs(plan.paths) do
		slab(paths, r, L.pathTop, colorOf(palette, r.color), "SmoothPlastic")
	end
	for _, r in ipairs(plan.kerbs) do
		slab(kerbs, r, L.kerbHeight, colorOf(palette, "Kerb"), "Concrete")
	end
	for _, r in ipairs(plan.ground) do
		slab(ground, r, L.groundTop, colorOf(palette, r.color), "SmoothPlastic")
	end
	local lamp = art.LampLight
	for _, it in ipairs(plan.items) do
		local model = Instance.new("Model")
		model.Name = it.name
		local base = CFrame.new(it.x, 0, it.z) * CFrame.Angles(0, math.rad(it.yaw), 0)
		for _, spec in ipairs(art.Pieces[it.piece]) do
			local part = piecePart(model, base, spec, palette, it.slot)
			if it.lit and spec.name == lamp.part then
				local light = Instance.new("PointLight")
				light.Name = "Light"
				light.Color = colorOf(palette, lamp.color)
				light.Brightness = lamp.brightness
				light.Range = lamp.range
				light.Shadows = false
				light.Parent = part
			end
		end
		-- Streaming: the item arrives and leaves whole (never a pole without its head). Some versions may not
		-- allow it from a script: then it simply stays the default.
		pcall(function()
			model.ModelStreamingMode = Enum.ModelStreamingMode.Atomic
		end)
		model.Parent = decor
	end
	for _, h in ipairs(plan.hills) do
		local d = (h.radius * h.radius + h.height * h.height) / h.height -- the sphere whose cap at y 0 has this radius
		local part = Instance.new("Part")
		part.Name = h.name
		part.Shape = Enum.PartType.Ball
		part.Size = Vector3.new(d, d, d)
		part.CFrame = CFrame.new(h.x, h.height - d / 2, h.z)
		part.Color = colorOf(palette, h.color)
		part.Material = Enum.Material.SmoothPlastic
		decorate(part, d, false, false)
		part.CastShadow = false -- far away and huge: a shadow would only cost
		part.Parent = hills
	end
	world.Parent = parent
	return world
end

-- See-through boxes where the plots, their signs and the lounge stand once the game runs (the Studio preview only:
-- in edit mode those don't exist). Never part of the World Model.
function WorldVisuals.ghosts(parent, site)
	local model = Instance.new("Model")
	model.Name = "Ghosts"
	local function ghost(name, x0, x1, y0, y1, z0, z1, color)
		local part = Instance.new("Part")
		part.Name = name
		part.Size = Vector3.new(x1 - x0, y1 - y0, z1 - z0)
		part.CFrame = CFrame.new((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2)
		part.Color = Color3.fromRGB(color[1], color[2], color[3])
		part.Material = Enum.Material.SmoothPlastic
		part.Transparency = 0.7
		decorate(part, 0, true, false)
		part.Parent = model
	end
	for i, p in ipairs(site.plots) do
		local fx, fz = site.floor[1] / 2, site.floor[3] / 2
		ghost("GhostPlot" .. i, p.x - fx, p.x + fx, p.y - site.floor[2] / 2, p.y + site.floor[2] / 2, p.z - fz, p.z + fz, { 90, 90, 100 })
	end
	local lg = site.lounge
	ghost("GhostLounge", lg.x - lg.halfX, lg.x + lg.halfX, 0, lg.top - 0.5, lg.back, lg.front, { 170, 210, 255 })
	model.Parent = parent
	return model
end

-- Checks ----------------------------------------------------------------------------------

-- Problems in the art data itself (empty list = fine)
function WorldVisuals.validate(art)
	local problems = {}
	local function problem(text)
		table.insert(problems, text)
	end
	local function triple(t, positive)
		if type(t) ~= "table" or #t ~= 3 then
			return false
		end
		for i = 1, 3 do
			if not finite(t[i]) or (positive and t[i] <= 0) then
				return false
			end
		end
		return true
	end
	local palette = art.Palette
	if type(palette) ~= "table" then
		problem("Palette: missing")
		palette = {}
	end
	for key, c in pairs(palette) do
		if not colorOk(c) then
			problem("Palette." .. tostring(key) .. ": a color is 3 whole numbers 0-255")
		end
	end
	local texts = {}
	for _, t in ipairs(art.Texts or {}) do
		if type(t) ~= "string" or t == "" or string.find(t, "[^ -~]") then
			problem("Texts: plain words only (letters, numbers, spaces)")
		else
			texts[t] = true
		end
	end

	local s = art.Site
	if type(s) ~= "table" then
		problem("Site: missing")
	else
		for _, key in ipairs({ "plotSpacing", "plotCount", "plotY", "plotZ", "signPostHeight", "signBoardY" }) do
			if not finite(s[key]) then
				problem("Site." .. key .. ": number missing")
			end
		end
		if not triple(s.floorSize, true) or not triple(s.signBoard, true) then
			problem("Site: floorSize and signBoard are 3 numbers above 0")
		end
		local lounge = s.lounge
		if type(lounge) ~= "table" or not triple(lounge.center) or not triple(lounge.size, true) or not finite(lounge.wallHeight)
			or not finite(lounge.doorWidth) or not finite(lounge.signHeight) or not finite(lounge.dropOut) then
			problem("Site.lounge: center, size, wallHeight, doorWidth, signHeight and dropOut")
		end
		local reach = s.plotReach
		if type(reach) ~= "table" or not (finite(reach.side) and finite(reach.back) and finite(reach.front) and finite(reach.top)) then
			problem("Site.plotReach: side, back, front and top")
		end
		for _, key in ipairs({ "baseplate", "spawn" }) do
			local fact = s[key]
			if type(fact) ~= "table" or not triple(fact.position) or not triple(fact.size, true) then
				problem("Site." .. key .. ": the Studio fact needs a position and a size")
			end
		end
		if type(s.signs) ~= "table" or #s.signs == 0 then
			problem("Site.signs: missing")
		end
	end

	local L = art.Layout
	if type(L) ~= "table" then
		problem("Layout: missing")
	else
		for key, v in pairs(L) do
			if type(v) == "number" and not finite(v) then
				problem("Layout." .. key .. ": not a usable number")
			end
		end
		for _, key in ipairs({ "pathWidth", "walkWidth", "groundTop", "pathTop", "kerbWidth", "kerbHeight", "plazaHalf", "spawnMargin",
			"crossGap", "armGap", "forecourtDepth", "loungeMargin", "doorClear", "dropClear", "backGap", "frontGap", "connectorClear", "lawnDepth",
			"meadowWidth" }) do
			if not finite(L[key]) or L[key] <= 0 then
				problem("Layout." .. key .. ": number missing")
			end
		end
		if finite(L.groundTop) and finite(L.pathTop) and finite(L.kerbHeight) then
			if L.pathTop - L.groundTop < 0.04 or L.kerbHeight - L.pathTop < 0.04 then
				problem("Layout: the ground, path and kerb layers must be at least 0.04 apart (else they flicker)")
			end
			if L.pathTop > WorldVisuals.FLAT or L.groundTop > WorldVisuals.FLAT then
				problem("Layout: paths and lawns are flat layers (at most " .. WorldVisuals.FLAT .. " tall)")
			end
		end
		if finite(L.walkWidth) and L.walkWidth < WorldVisuals.CONTACT then
			problem("Layout.walkWidth: a walk must be at least " .. WorldVisuals.CONTACT .. " wide")
		end
	end

	local function spec(where, sp)
		local name = type(sp) == "table" and sp.name
		if type(name) ~= "string" or name == "" then
			problem(where .. ": a part without a name")
			return
		end
		where = where .. "." .. name
		if WorldVisuals.RESERVED_NAMES[name] then
			problem(where .. ": that name belongs to the game")
		end
		if not WorldVisuals.SHAPES[sp.shape] then
			problem(where .. ": unknown shape " .. tostring(sp.shape))
		end
		if not triple(sp.size, true) then
			problem(where .. ": size must be 3 numbers above 0")
		elseif sp.shape == "Ball" and not (sp.size[1] == sp.size[2] and sp.size[2] == sp.size[3]) then
			problem(where .. ": a Ball needs 3 equal sides")
		elseif sp.shape == "Cylinder" and sp.size[2] ~= sp.size[3] then
			problem(where .. ": a Cylinder needs equal Y and Z (its diameter)")
		end
		if not triple(sp.offset) then
			problem(where .. ": offset must be 3 numbers")
		end
		if sp.rot ~= nil then
			if not triple(sp.rot) then
				problem(where .. ": rot must be 3 numbers (degrees)")
			else
				for i = 1, 3 do
					if sp.rot[i] % 90 ~= 0 then
						problem(where .. ": rot must be quarter turns (0, 90, 180, 270)")
						break
					end
				end
			end
		end
		if type(sp.color) ~= "string" or not palette[sp.color] then
			problem(where .. ": color " .. tostring(sp.color) .. " is not in the palette")
		end
		if not WorldVisuals.MATERIALS[sp.material] then
			problem(where .. ": material not allowed: " .. tostring(sp.material))
		elseif sp.material == "Neon" and not isLightName(name) then
			problem(where .. ": Neon is only for lights (name it Lamp, Light, Glow or Bulb)")
		end
		if sp.collide ~= nil or sp.light ~= nil or sp.particles ~= nil or sp.transparency ~= nil then
			problem(where .. ": world parts never collide, light (the layout lights lamps), emit or fade")
		end
		if sp.text ~= nil then
			local t = sp.text
			local valueOk = (t.slot == true and t.value == nil) or (t.slot == nil and type(t.value) == "string" and texts[t.value])
			local facesOk = type(t.faces) == "table" and #t.faces > 0
			for _, face in ipairs(type(t.faces) == "table" and t.faces or {}) do
				if not WorldVisuals.FACES[face] then
					facesOk = false
				end
			end
			if not valueOk then
				problem(where .. ": text must be the plot's number (slot = true) or one of WorldArt.Texts")
			end
			if not facesOk or not WorldVisuals.FONTS[t.font or "GothamBold"] or type(t.color) ~= "string" or not palette[t.color] then
				problem(where .. ": text needs known faces, a known font and a palette color")
			end
		end
	end
	if type(art.Pieces) ~= "table" then
		problem("Pieces: missing")
	else
		for key, list in pairs(art.Pieces) do
			local names = {}
			for i, sp in ipairs(list) do
				spec("Pieces." .. tostring(key) .. "[" .. i .. "]", sp)
				if type(sp) == "table" and sp.name then
					if names[sp.name] then
						problem("Pieces." .. tostring(key) .. ": two parts named " .. sp.name)
					end
					names[sp.name] = true
				end
			end
		end
		for _, needed in ipairs({ "Lamp", "TreeA", "TreeB", "TreeC", "Bush", "Hedge", "Bench", "Planter", "Sign", "Arch" }) do
			if type(art.Pieces[needed]) ~= "table" or #art.Pieces[needed] == 0 then
				problem("Pieces." .. needed .. ": missing")
			end
		end
	end
	local lamp = art.LampLight
	if type(lamp) ~= "table" or type(lamp.part) ~= "string" or not palette[lamp.color] or not finite(lamp.brightness) or lamp.brightness <= 0
		or not finite(lamp.range) or lamp.range <= 0 or lamp.range > 60 then
		problem("LampLight: needs a part name, a palette color, brightness above 0 and range 0-60")
	else
		local found = false
		for _, sp in ipairs((art.Pieces or {}).Lamp or {}) do
			if sp.name == lamp.part then
				found = true
			end
		end
		if not found then
			problem("LampLight: the Lamp piece has no part named " .. lamp.part)
		end
	end
	for i, h in ipairs(art.Hills or {}) do
		if type(h.name) ~= "string" or not finite(h.x) or not finite(h.z) or not finite(h.height) or h.height <= 0
			or not finite(h.radius) or h.radius <= h.height or not palette[h.color] then
			problem("Hills[" .. i .. "]: a name, x, z, a height above 0, a radius above the height and a palette color")
		end
	end
	local budget = art.Budget
	if type(budget) ~= "table" or not finite(budget.parts) or budget.parts < 1 or not finite(budget.lights) or budget.lights < 0 then
		problem("Budget: parts and lights")
	end
	return problems
end

-- The zones no world part may enter: { kind, name, box, flatOk (a ground layer may lie in it), allow (a part that
-- may) }. Plots (floor and what their art reaches), their signs, the lounge, its door and drop spot, the spawn pad
-- with its margin, and the Studio preview rooms.
function WorldVisuals.zones(art, site)
	local L = art.Layout
	local zones = {}
	local function add(kind, name, box, flatOk, allow)
		table.insert(zones, { kind = kind, name = name, box = box, flatOk = flatOk, allow = allow })
	end
	local fx, fy, fz = site.floor[1] / 2, site.floor[2], site.floor[3] / 2
	local r = site.reach
	for i, p in ipairs(site.plots) do
		local floorTop = p.y + fy / 2
		add("plot floor", "Plot" .. i, { p.x - fx, p.x + fx, 0, floorTop, p.z - fz, p.z + fz }, false)
		local walk = "Walk" .. i
		add("plot reach", "Plot" .. i, { p.x - r.side, p.x + r.side, 0, r.top, p.z - r.back, p.z + r.front }, false, function(part)
			return part.Name == walk and part.flat
		end)
		for _, sign in ipairs(site.signs) do
			local x, z = p.x + sign.x, p.z + sign.z
			local b = site.signBoard
			add("sign", sign.name .. i, { x - b[1] / 2, x + b[1] / 2, floorTop, floorTop + site.signBoardY + b[2] / 2, z - b[3] / 2 - 0.2, z + b[3] / 2 + 0.2 }, false)
		end
	end
	local lg, m = site.lounge, L.loungeMargin
	add("lounge", "VipLounge", { lg.x - lg.halfX - m, lg.x + lg.halfX + m, 0, lg.top + m, lg.back - m, lg.front + m }, false)
	add("lounge door", "VipDoor", { lg.x - lg.door / 2, lg.x + lg.door / 2, 0, lg.top, lg.front, lg.front + L.doorClear }, true)
	local d = L.dropClear
	add("drop spot", "VipDrop", { lg.drop.x - d, lg.drop.x + d, 0, 8, lg.drop.z - d, lg.drop.z + d }, true)
	local sp, sm = site.spawn, math.max(L.spawnMargin, 0) -- never smaller than the pad itself
	add("spawn pad", "SpawnLocation", { sp.x - sp.halfX - sm, sp.x + sp.halfX + sm, 0, sp.top + 12, sp.z - sp.halfZ - sm, sp.z + sp.halfZ + sm }, false)
	if site.preview then
		add("preview rooms", "PREVIEW_STAGES", site.preview, false)
	end
	return zones
end

-- The planar faces of a part (Blocks: 6, Cylinders: their 2 round ends, Balls: none), for the flicker check
local function facesOf(info)
	local b, out = info.box, {}
	local function face(axis, side)
		local at = side < 0 and b[axis * 2 - 1] or b[axis * 2]
		local u, v = axis == 1 and 2 or 1, axis == 3 and 2 or 3
		table.insert(out, { axis = axis, side = side, at = at, u0 = b[u * 2 - 1], u1 = b[u * 2], v0 = b[v * 2 - 1], v1 = b[v * 2], who = info })
	end
	if info.shape == "Block" then
		for axis = 1, 3 do
			face(axis, -1)
			face(axis, 1)
		end
	elseif info.shape == "Cylinder" then
		local _, _, _, r00, _, _, r10, _, _, r20 = info.part.CFrame:GetComponents()
		local axis = math.abs(r00) > 0.5 and 1 or (math.abs(r10) > 0.5 and 2 or 3)
		face(axis, -1)
		face(axis, 1)
	end
	return out
end

local function partInfo(d)
	local b = boxOf(d.CFrame, d.Size)
	local shape = d:IsA("Part") and d.Shape.Name or "Block" -- only a Part has a Shape (reading it on a MeshPart errors)
	local above = aboveGround(shape, b)
	return {
		part = d, name = d:GetFullName(), box = b, above = above, shape = shape,
		flat = b[4] - b[3] <= WorldVisuals.FLAT and b[3] >= -WorldVisuals.TOUCH and b[3] <= WorldVisuals.TOUCH,
		Name = d.Name,
	}
end

-- Every named check, in order. options: palette (when build was given one), roomBoxes (parts of the plots' rooms,
-- { name, box }, world coordinates), extraFaces (more faces to check for flicker).
function WorldVisuals.checks(world, art, site, options)
	options = options or {}
	local palette = options.palette or art.Palette
	local L = art.Layout
	local results = {}
	local function run(name, fn)
		local problems = {}
		local ok, err = pcall(fn, function(text)
			table.insert(problems, text)
		end)
		if not ok then
			table.insert(problems, "the " .. name .. " check could not run: " .. tostring(err))
		end
		table.insert(results, { name = name, problems = problems })
	end

	local parts, lights, labels, guis, forbidden = {}, 0, {}, 0, {}
	for _, d in ipairs(world:GetDescendants()) do
		if d:IsA("BasePart") then
			table.insert(parts, partInfo(d))
		elseif d.ClassName == "PointLight" or d.ClassName == "SpotLight" or d.ClassName == "SurfaceLight" then
			lights += 1
		elseif d.ClassName == "TextLabel" or d.ClassName == "TextButton" or d.ClassName == "TextBox" then
			table.insert(labels, d)
		elseif d.ClassName == "SurfaceGui" or d.ClassName == "BillboardGui" then
			guis += 1
		end
		if WorldVisuals.FORBIDDEN_CLASSES[d.ClassName] then
			table.insert(forbidden, d:GetFullName() .. " (" .. d.ClassName .. ")")
		end
	end

	run("data", function(problem)
		for _, text in ipairs(WorldVisuals.validate(art)) do
			problem(text)
		end
	end)

	run("budget", function(problem)
		if #parts > art.Budget.parts then
			problem(string.format("%d parts (budget %d)", #parts, art.Budget.parts))
		end
		if lights > art.Budget.lights then
			problem(string.format("%d lights (budget %d)", lights, art.Budget.lights))
		end
	end)

	run("flags", function(problem)
		for _, what in ipairs(forbidden) do
			problem(what .. ": no scripts, seats, sounds, effects, meshes or images in the world")
		end
		for _, p in ipairs(parts) do
			local part = p.part
			if part.ClassName ~= "Part" then
				problem(p.name .. ": only plain Parts in the world (not a " .. part.ClassName .. ")")
			end
			if not part.Anchored then
				problem(p.name .. ": not anchored")
			end
			if part.CanCollide then
				problem(p.name .. ": CanCollide is on (decor never collides)")
			end
			if part.CanTouch then
				problem(p.name .. ": CanTouch is on")
			end
			if part.CanQuery then
				problem(p.name .. ": CanQuery is on (it would stop rays and the camera)")
			end
			local longest = math.max(part.Size.X, part.Size.Y, part.Size.Z)
			if part.CastShadow and (longest < WorldVisuals.TINY or p.flat or part.Material.Name == "Neon") then
				problem(p.name .. ": a tiny, flat or glowing part casts a shadow")
			end
			if not WorldVisuals.MATERIALS[part.Material.Name] then
				problem(p.name .. ": material not allowed: " .. part.Material.Name)
			elseif part.Material.Name == "Neon" and not isLightName(part.Name) then
				problem(p.name .. ": Neon on something that isn't a light")
			end
			if not WorldVisuals.SHAPES[p.shape] then
				problem(p.name .. ": shape not allowed: " .. p.shape)
			end
			if not quarterTurns(part.CFrame) then
				problem(p.name .. ": turned by something other than quarter turns")
			end
			if WorldVisuals.RESERVED_NAMES[part.Name] then
				problem(p.name .. ": named like a part of the game")
			end
		end
	end)

	run("keepouts", function(problem)
		local zones = WorldVisuals.zones(art, site)
		for _, p in ipairs(parts) do
			for _, zone in ipairs(zones) do
				if overlaps(p.above, zone.box, WorldVisuals.OVERLAP) and not (zone.flatOk and p.flat) and not (zone.allow and zone.allow(p)) then
					problem(p.name .. " is inside the " .. zone.kind .. " zone " .. zone.name)
				end
			end
			if options.roomBoxes then
				for _, room in ipairs(options.roomBoxes) do
					local flatRoom = room.box[4] - room.box[3] <= WorldVisuals.FLAT and room.box[3] <= WorldVisuals.TOUCH
					if overlaps(p.above, room.box, WorldVisuals.OVERLAP) and not (p.flat and flatRoom) then
						problem(p.name .. " goes into the room part " .. room.name)
					end
				end
			end
		end
	end)

	run("floating", function(problem)
		local supported, queue = {}, {}
		for i, p in ipairs(parts) do
			if p.box[3] <= WorldVisuals.TOUCH then
				supported[i] = true
				table.insert(queue, i)
			end
		end
		local head, t = 1, WorldVisuals.TOUCH
		while head <= #queue do
			local a = parts[queue[head]].box
			head += 1
			for j, p in ipairs(parts) do
				if not supported[j] then
					local b = p.box
					if a[1] <= b[2] + t and b[1] <= a[2] + t and a[3] <= b[4] + t and b[3] <= a[4] + t and a[5] <= b[6] + t and b[5] <= a[6] + t then
						supported[j] = true
						table.insert(queue, j)
					end
				end
			end
		end
		for i, p in ipairs(parts) do
			if not supported[i] then
				problem(p.name .. " is floating")
			end
		end
	end)

	run("zfighting", function(problem)
		local g = site.ground
		local faces = { { axis = 2, side = 1, at = g.top, u0 = g.x0, u1 = g.x1, v0 = g.z0, v1 = g.z1, who = { name = "the Baseplate's top" }, other = true } }
		for _, p in ipairs(parts) do
			for _, f in ipairs(facesOf(p)) do
				if not (f.axis == 2 and f.side == -1 and f.at <= WorldVisuals.TOUCH) then -- a bottom resting on the ground is never seen
					table.insert(faces, f)
				end
			end
		end
		for _, room in ipairs(options.roomBoxes or {}) do
			local b = room.box
			if b[4] - b[3] > 0 then
				table.insert(faces, { axis = 2, side = 1, at = b[4], u0 = b[1], u1 = b[2], v0 = b[5], v1 = b[6], who = { name = room.name }, other = true })
			end
		end
		local buckets = {}
		for _, f in ipairs(faces) do
			local key = f.axis * 2 + (f.side > 0 and 1 or 0)
			local cell = math.floor(f.at / 0.01 + 0.5)
			buckets[key] = buckets[key] or {}
			buckets[key][cell] = buckets[key][cell] or {}
			table.insert(buckets[key][cell], f)
		end
		local seen = {}
		for _, f in ipairs(faces) do
			local key = f.axis * 2 + (f.side > 0 and 1 or 0)
			local cell = math.floor(f.at / 0.01 + 0.5)
			for dc = -1, 1 do
				for _, h in ipairs(buckets[key][cell + dc] or {}) do
					if h ~= f and h.who ~= f.who and not (h.other and f.other) and math.abs(h.at - f.at) < WorldVisuals.PLANE then
						local du = math.min(f.u1, h.u1) - math.max(f.u0, h.u0)
						local dv = math.min(f.v1, h.v1) - math.max(f.v0, h.v0)
						if du > 1e-4 and dv > 1e-4 then
							local a, b = f.who.name, h.who.name
							local pair = a < b and (a .. "|" .. b) or (b .. "|" .. a)
							if not seen[pair] then
								seen[pair] = true
								problem(string.format("%s and %s share a face plane (%s = %.3f): they would flicker", a, b, ({ "x", "y", "z" })[f.axis], f.at))
							end
						end
					end
				end
			end
		end
	end)

	run("baseplate", function(problem)
		local g = site.ground
		for _, p in ipairs(parts) do
			local b = p.above
			if b[1] < g.x0 or b[2] > g.x1 or b[5] < g.z0 or b[6] > g.z1 then
				problem(p.name .. " reaches past the Baseplate's edge")
			end
		end
	end)

	run("connected", function(problem)
		local paths = world:FindFirstChild("Paths")
		local rects = {}
		for _, part in ipairs(paths and paths:GetChildren() or {}) do
			if part:IsA("BasePart") then
				local b = boxOf(part.CFrame, part.Size)
				table.insert(rects, { name = part.Name, x0 = b[1], x1 = b[2], z0 = b[5], z1 = b[6] })
			end
		end
		local eps, need = 0.01, WorldVisuals.CONTACT - 0.01
		local function along(a0, a1, b0, b1)
			return math.min(a1, b1) - math.max(a0, b0)
		end
		local function joined(a, b)
			local ox, oz = along(a.x0, a.x1, b.x0, b.x1), along(a.z0, a.z1, b.z0, b.z1)
			if (math.abs(a.z1 - b.z0) <= eps or math.abs(b.z1 - a.z0) <= eps) and ox >= need then
				return true
			end
			if (math.abs(a.x1 - b.x0) <= eps or math.abs(b.x1 - a.x0) <= eps) and oz >= need then
				return true
			end
			return ox >= need and oz >= need
		end
		local sp, sm = site.spawn, L.spawnMargin
		local pad = { x0 = sp.x - sp.halfX - sm, x1 = sp.x + sp.halfX + sm, z0 = sp.z - sp.halfZ - sm, z1 = sp.z + sp.halfZ + sm }
		local reached, queue = {}, {}
		for i, r in ipairs(rects) do
			if joined(r, pad) then
				reached[i] = true
				table.insert(queue, i)
			end
		end
		if #queue == 0 then
			problem("no path reaches the spawn pad's edge")
		end
		local head = 1
		while head <= #queue do
			local a = rects[queue[head]]
			head += 1
			for j, b in ipairs(rects) do
				if not reached[j] and joined(a, b) then
					reached[j] = true
					table.insert(queue, j)
				end
			end
		end
		for i, p in ipairs(site.plots) do
			local edge = { x0 = p.x - site.floor[1] / 2, x1 = p.x + site.floor[1] / 2, z0 = p.z + site.floor[3] / 2, z1 = p.z + site.floor[3] / 2 }
			local ok = false
			for j, r in ipairs(rects) do
				if reached[j] and math.abs(r.z0 - edge.z0) <= eps and along(r.x0, r.x1, edge.x0, edge.x1) >= need then
					ok = true
				end
			end
			if not ok then
				problem("plot " .. i .. "'s front edge is not reached by the paths from the spawn")
			end
		end
	end)

	run("palette", function(problem)
		local used = {}
		local function use(key, where)
			if type(key) ~= "string" or not palette[key] then
				problem(where .. ": color " .. tostring(key) .. " is not in the palette")
			elseif not colorOk(palette[key]) then
				problem(where .. ": palette color " .. key .. " is not 3 whole numbers 0-255")
			end
			used[key] = true
		end
		for name, list in pairs(art.Pieces) do
			for _, sp in ipairs(list) do
				use(sp.color, "Pieces." .. name .. "." .. tostring(sp.name))
				if sp.text then
					use(sp.text.color, "Pieces." .. name .. "." .. tostring(sp.name) .. " text")
				end
			end
		end
		local plan = WorldVisuals.layout(art, site)
		for _, list in ipairs({ plan.paths, plan.ground }) do
			for _, r in ipairs(list) do
				use(r.color, r.name)
			end
		end
		for _, h in ipairs(plan.hills) do
			use(h.color, h.name)
		end
		use("Kerb", "kerbs")
		use(art.LampLight.color, "LampLight")
	end)

	run("texts", function(problem)
		local allowed = {}
		for _, t in ipairs(art.Texts) do
			allowed[t] = true
		end
		for i = 1, site.count do
			allowed[tostring(i)] = true
		end
		for _, label in ipairs(labels) do
			if not allowed[label.Text] then
				problem(label:GetFullName() .. ": text \"" .. tostring(label.Text) .. "\" is not one of WorldArt.Texts or a plot number")
			end
		end
		if guis ~= #labels then
			problem(string.format("%d text surfaces for %d labels (one label each)", guis, #labels))
		end
	end)
	return results
end

-- Every problem of every check in one list (empty = fine)
function WorldVisuals.check(world, art, site, options)
	local all = {}
	for _, result in ipairs(WorldVisuals.checks(world, art, site, options)) do
		for _, text in ipairs(result.problems) do
			table.insert(all, result.name .. ": " .. text)
		end
	end
	return all
end

-- The state of parts the world must never change (the SpawnLocation, the Baseplate, the plots, the lounge)
function WorldVisuals.snapshot(list)
	local snap = {}
	for _, inst in ipairs(list) do
		table.insert(snap, {
			inst = inst, name = inst.Name, parent = inst.Parent, size = inst.Size, cframe = inst.CFrame, color = inst.Color,
			anchored = inst.Anchored, canCollide = inst.CanCollide, transparency = inst.Transparency,
		})
	end
	return snap
end

function WorldVisuals.compare(snap)
	local problems = {}
	local function same3(a, b)
		return math.abs(a.X - b.X) < 1e-6 and math.abs(a.Y - b.Y) < 1e-6 and math.abs(a.Z - b.Z) < 1e-6
	end
	for _, s in ipairs(snap) do
		local inst = s.inst
		local where = s.name
		if inst.Parent ~= s.parent then
			table.insert(problems, where .. " was moved to another parent or deleted")
		end
		if inst.Name ~= s.name then
			table.insert(problems, where .. " was renamed")
		end
		if not same3(inst.Size, s.size) then
			table.insert(problems, where .. " was resized")
		end
		local a, b = { inst.CFrame:GetComponents() }, { s.cframe:GetComponents() }
		for i = 1, 12 do
			if math.abs(a[i] - b[i]) > 1e-6 then
				table.insert(problems, where .. " was moved or turned")
				break
			end
		end
		if inst.Color ~= s.color or inst.Anchored ~= s.anchored or inst.CanCollide ~= s.canCollide or inst.Transparency ~= s.transparency then
			table.insert(problems, where .. " was changed (color, anchoring, collision or transparency)")
		end
	end
	return problems
end

-- The Studio facts (measured by the owner) against the real objects. Read only.
function WorldVisuals.studioFacts(site, spawn, baseplate)
	local problems = {}
	local function compare(what, part, fact)
		if not part then
			table.insert(problems, "no " .. what .. " found in the Workspace")
			return
		end
		local p, s = part.Position, part.Size
		local want = fact.position
		local size = fact.size
		local off = math.max(math.abs(p.X - want[1]), math.abs(p.Y - want[2]), math.abs(p.Z - want[3]),
			math.abs(s.X - size[1]), math.abs(s.Y - size[2]), math.abs(s.Z - size[3]))
		if off > WorldVisuals.FACT then
			table.insert(problems, string.format("%s is at (%.2f, %.2f, %.2f) size (%.2f, %.2f, %.2f); WorldArt.Site says (%g, %g, %g) size (%g, %g, %g)",
				what, p.X, p.Y, p.Z, s.X, s.Y, s.Z, want[1], want[2], want[3], size[1], size[2], size[3]))
		end
	end
	compare("SpawnLocation", spawn, site.spawnFact)
	compare("Baseplate", baseplate, site.baseplateFact)
	return problems
end

-- World parts that would go into other parts (hand-placed things the repo doesn't know about). others: BaseParts.
function WorldVisuals.clashes(world, others)
	local out, mine = {}, {}
	for _, d in ipairs(world:GetDescendants()) do
		if d:IsA("BasePart") then
			table.insert(mine, partInfo(d))
		end
	end
	for _, other in ipairs(others) do
		local b = boxOf(other.CFrame, other.Size)
		for _, p in ipairs(mine) do
			if overlaps(p.above, b, WorldVisuals.OVERLAP) then
				table.insert(out, p.name .. " would go into " .. other:GetFullName())
				break
			end
		end
	end
	return out
end

return WorldVisuals
