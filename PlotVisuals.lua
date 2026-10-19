-- PlotVisuals: builds the garage that grows with the startup (branch visuals-garage).
-- Put this ModuleScript in ServerScriptService, next to TycoonCore. The art itself (every part of
-- every stage room, the hire desks, the upgrade props) is data in PlotArt (ServerScriptService).
--
-- Only looks: nothing here is saved, sent through a remote or read back by the game. Parts the
-- server builds replicate to every player by themselves. Every part is anchored; decor never
-- collides, is never touched and never stops a ray or the camera (CanCollide, CanTouch and
-- CanQuery off). Only parts the art marks `collide` (floors) are solid.
--
-- The builders are plain functions of their arguments (a parent, the plot center, the art): no
-- game services and no player data, so they also run from Studio's command bar (the preview).
--   PlotVisuals.buildRoom(parent, center, art, stage)         -> Model "PlotRoom": Shell, Decor, UpgradeProps
--   PlotVisuals.buildProp(parent, center, art, upgrade, slot)  -> Model named after the upgrade, or nil (no art)
--   PlotVisuals.styleFloor(floor, art, stage)                   -> color and material only (name and size stay)
--   PlotVisuals.buildRoom(parent, center, art, stage, kit)    -> the same room with its furniture from the 3D kit
--   PlotVisuals.buildRoom(parent, center, art, stage, kit, desks) -> with a hire desk at the first `desks` hire spots only
--                                                                (plus a see-through "next hire" desk at the spot after
--                                                                them; nil = a desk at every spot, the full room)
--   PlotVisuals.buildDesks(decor, origin, art, stage, kit, desks) -> the hire desks alone (what setDesks rebuilds)
-- Furniture ("kit pieces" in the art: a kit key instead of a shape) comes from the 3D kit, kit = the folder
-- ReplicatedStorage.KitModels (docs/KIT_MODELS.md): copies of a model's MeshParts, recolored per role, scaled, turned.
-- Without the kit, or for a model that is missing or can't be used, the piece is built from Parts (PlotArt.Kit's
-- fallback boxes, the same colors): the game looks right with no kit at all.
-- TycoonCore keeps one plot table per player (in memory, never saved):
--   PlotVisuals.newPlot(folder, center, art, floor, stage, kit) -> plot, with the room of that stage (kit: the folder,
--                                                                   or nil = PlotVisuals.findKit(art)) and no hire desk
--                                                                   yet (setDesks puts one per hire)
--   PlotVisuals.setStage(plot, stage, flash)                    -> swaps the room (quick flash), keeps the props and the desks
--   PlotVisuals.setDesks(plot, count, popIn)                    -> a desk at the first `count` hire spots and a see-through
--                                                                   one at the next (the office grows with the team,
--                                                                   overhaul phase 3; derived from the team, never saved)
--   PlotVisuals.addProp(plot, upgrade, slot, popIn)             -> the prop Model (pops in), or nil
-- Checks (tools/daily_test.py and the Studio preview run them):
--   PlotVisuals.validate(art)             -> list of problems in the data (empty = fine)
--   PlotVisuals.kitBox(art, spec)         -> the box a kit piece may fill, from its spot (kit or Parts: never bigger)
--   PlotVisuals.check(room, center, art)  -> list of problems in a built room (zones, floating parts, walls, budget),
--                                            measured in the garage's frame
--
-- Offsets in the art are studs from the plot's floor-top center: the middle of the Floor's top
-- face (plot center + Layout.floorTop). +X is right, +Z is the front (the signs), -Z the back wall.
-- They are in the garage's own frame: `center` is the plot center (a Vector3: a garage facing +Z) or the
-- garage's frame (a CFrame: the center, turned), and the whole room turns with it. newPlot takes the turn
-- from the Floor's CFrame (TycoonCore builds the Floor in the garage's frame); check measures in that frame.

local PlotVisuals = {}

-- What the art may use. Neon only for lights and signs: its part name must say so (LIGHT_WORDS).
PlotVisuals.MATERIALS = {
	Concrete = true, CorrodedMetal = true, Metal = true, DiamondPlate = true, Wood = true, WoodPlanks = true,
	Brick = true, Fabric = true, Plastic = true, SmoothPlastic = true, Glass = true, Neon = true,
}
PlotVisuals.SHAPES = { Block = true, Cylinder = true, Ball = true, Wedge = true }
PlotVisuals.FONTS = { GothamBold = true, PermanentMarker = true, IndieFlower = true, LuckiestGuy = true, FredokaOne = true }
local FACES = { Top = true, Bottom = true, Left = true, Right = true, Front = true, Back = true }
PlotVisuals.LIGHT_WORDS = { "Bulb", "Lamp", "Light", "Screen", "LED", "Sign", "Logo", "Neon", "Glow", "Flash" }
PlotVisuals.TINY = 2 -- a part whose longest side is shorter than this casts no shadow
PlotVisuals.FLAT = 0.2 -- a part at most this tall lying on the floor or the ground is a floor mark (rug, stain, line)
PlotVisuals.MAX_PARTS = 420 -- per stage room: upgrade props, catalog items and solid boxes included (overhaul 2: was 260)
PlotVisuals.MAX_LIGHTS = 3 -- PointLights per plot
PlotVisuals.SIDE_WALL_MAX = 6 -- the sides and the front, where the camera looks in
PlotVisuals.BACK_WALL_MAX = 12 -- behind the incubators (z <= BACK_BAND)
PlotVisuals.BACK_BAND = -29
PlotVisuals.BACKDROP_Z = -43 -- the skyline ("Skyline" parts) stands behind this line only
PlotVisuals.BACKDROP_MAX = 30
PlotVisuals.TURNS = { [0] = true, [90] = true, [180] = true, [270] = true } -- a kit piece turns by quarter turns only
PlotVisuals.KIT_FIT = 0.02 -- a fallback box may stick out of its kit size by this much (float noise), never more
-- Solid boxes (overhaul 2, the owner's point 5): one invisible anchored box per furniture piece, the only room parts a
-- player bumps into besides the floors. Each stands on the floor inside its piece's footprint (inset a little), at most
-- SOLID_MAX tall; a piece lower than SOLID_MIN (cans, pizza boxes, weeds) stays something to walk over.
PlotVisuals.SOLID_MAX = 8
PlotVisuals.SOLID_MIN = 1.2
PlotVisuals.SOLID_INSET = 0.1
PlotVisuals.SOLIDS = "Solids" -- the room's Model of the decor's boxes (a desk's, a prop's, an item's box is in its own Model)

local TOUCH = 0.06 -- parts closer than this touch (floating check)
local OVERLAP = 0.01 -- parts must go this far into a zone to count as inside it
local POP_FROM, POP_SECONDS = 0.2, 0.35

-- Helpers ---------------------------------------------------------------

local function rgb(c)
	return Color3.fromRGB(c[1], c[2], c[3])
end

local function turn(r)
	if not r then
		return CFrame.new()
	end
	return CFrame.fromEulerAnglesYXZ(math.rad(r[1]), math.rad(r[2]), math.rad(r[3]))
end

-- The world box around a part: { minX, maxX, minY, maxY, minZ, maxZ }
local function boxOf(cframe, size)
	local x, y, z, r00, r01, r02, r10, r11, r12, r20, r21, r22 = cframe:GetComponents()
	local hx = (math.abs(r00) * size.X + math.abs(r01) * size.Y + math.abs(r02) * size.Z) / 2
	local hy = (math.abs(r10) * size.X + math.abs(r11) * size.Y + math.abs(r12) * size.Z) / 2
	local hz = (math.abs(r20) * size.X + math.abs(r21) * size.Y + math.abs(r22) * size.Z) / 2
	return { x - hx, x + hx, y - hy, y + hy, z - hz, z + hz }
end
PlotVisuals.boxOf = boxOf

local function overlaps(a, b, margin)
	return a[1] < b[2] - margin and b[1] < a[2] - margin
		and a[3] < b[4] - margin and b[3] < a[4] - margin
		and a[5] < b[6] - margin and b[5] < a[6] - margin
end

-- One warning per kind per server (a room is rebuilt at every stage change: the same problem is told once)
local warned = {}
local function warnOnce(kind, text)
	if not warned[kind] then
		warned[kind] = true
		warn("Plot visuals: " .. text)
	end
end

local function isLightName(name)
	for _, word in ipairs(PlotVisuals.LIGHT_WORDS) do
		if string.find(name, word, 1, true) then
			return true
		end
	end
	return false
end

-- Building --------------------------------------------------------------

-- One part from its spec (see PlotArt), placed at base * offset * rotation
function PlotVisuals.buildPart(parent, base, spec)
	local size = Vector3.new(spec.size[1], spec.size[2], spec.size[3])
	local part = Instance.new("Part")
	part.Name = spec.name
	part.Shape = Enum.PartType[spec.shape or "Block"]
	part.Size = size
	part.CFrame = base * CFrame.new(spec.offset[1], spec.offset[2], spec.offset[3]) * turn(spec.rot)
	part.Color = rgb(spec.color)
	part.Material = Enum.Material[spec.material]
	part.Transparency = spec.transparency or 0
	part.Anchored = true
	local solid = spec.collide == true
	part.CanCollide = solid
	part.CanQuery = solid -- Roblox needs CanQuery on for anything solid
	part.CanTouch = false
	part.TopSurface = Enum.SurfaceType.Smooth
	part.BottomSurface = Enum.SurfaceType.Smooth
	local box = boxOf(part.CFrame, size)
	local longest = math.max(spec.size[1], spec.size[2], spec.size[3])
	local shadow = longest >= PlotVisuals.TINY and box[4] - box[3] > PlotVisuals.FLAT
		and spec.material ~= "Neon" and (spec.transparency or 0) < 0.5
	if spec.shadow ~= nil then
		shadow = spec.shadow and longest >= PlotVisuals.TINY
	end
	part.CastShadow = shadow

	local light = spec.light
	if light then
		local point = Instance.new("PointLight")
		point.Name = "Light"
		point.Color = rgb(light.color)
		point.Brightness = light.brightness
		point.Range = light.range
		point.Shadows = false
		point.Parent = part
	end

	local text = spec.text
	if text then
		local gui = Instance.new("SurfaceGui")
		gui.Name = "Text"
		gui.Face = Enum.NormalId[text.face or "Back"] -- Back = the +Z side, toward the front
		gui.SizingMode = Enum.SurfaceGuiSizingMode.PixelsPerStud
		gui.PixelsPerStud = 40
		gui.LightInfluence = text.glow and 0 or 1
		gui.Parent = part
		local area = text.area or { 0, 0, 1, 1 }
		local label = Instance.new("TextLabel")
		label.Name = "Label"
		label.Position = UDim2.fromScale(area[1], area[2])
		label.Size = UDim2.fromScale(area[3], area[4])
		label.BackgroundTransparency = 1
		label.TextScaled = true
		label.Font = Enum.Font[text.font or "GothamBold"]
		label.TextColor3 = rgb(text.color)
		label.Text = text.value
		label.Rotation = text.rotation or 0
		label.Parent = gui
	end

	local particles = spec.particles
	if particles then
		local emitter = Instance.new("ParticleEmitter") -- the default texture: no asset
		emitter.Name = "Particles"
		emitter.Rate = particles.rate
		emitter.Lifetime = NumberRange.new(particles.lifetime[1], particles.lifetime[2])
		emitter.Speed = NumberRange.new(particles.speed[1], particles.speed[2])
		emitter.SpreadAngle = Vector2.new(particles.spread, particles.spread)
		emitter.Size = NumberSequence.new(particles.size[1], particles.size[2])
		emitter.Transparency = NumberSequence.new(particles.transparency[1], particles.transparency[2])
		emitter.Color = ColorSequence.new(rgb(particles.color[1]), rgb(particles.color[2]))
		emitter.LightEmission = particles.lightEmission or 0
		emitter.EmissionDirection = Enum.NormalId[particles.direction or "Top"] -- the part's own side
		emitter.Parent = part
	end

	part.Parent = parent
	return part
end

-- Kit pieces (furniture from the 3D kit) ------------------------------------------------

-- The kit folder (ReplicatedStorage.<art.KIT_FOLDER>), or nil. The only service PlotVisuals reads, inside pcall: outside
-- Roblox (the tests) there is no game, and the rooms are built from Parts.
function PlotVisuals.findKit(art)
	if type(art) ~= "table" or type(art.KIT_FOLDER) ~= "string" then
		return nil
	end
	local ok, folder = pcall(function()
		return game:GetService("ReplicatedStorage"):FindFirstChild(art.KIT_FOLDER)
	end)
	return ok and folder or nil
end

-- A piece's scale: a number (all three sides) or { x, y, z }; nil is 1
local function scaleOf(spec)
	local s = spec.scale
	if type(s) == "number" then
		return s, s, s
	elseif type(s) == "table" then
		return s[1], s[2], s[3]
	end
	return 1, 1, 1
end

-- The box a kit piece may fill, from its base (the room's floor-top center, or a hire desk's spot): its kit size times
-- its scale, standing on its offset, turned by quarter turns. { minX, maxX, minY, maxY, minZ, maxZ }
function PlotVisuals.kitBox(art, spec)
	local entry = art.Kit[spec.kit]
	local sx, sy, sz = scaleOf(spec)
	local w, h, d = entry.size[1] * sx, entry.size[2] * sy, entry.size[3] * sz
	if (spec.turn or 0) % 180 == 90 then
		w, d = d, w
	end
	local o = spec.offset
	return { o[1] - w / 2, o[1] + w / 2, o[2], o[2] + h, o[3] - d / 2, o[3] + d / 2 }
end

-- Where a piece stands: its spot on the base, turned (the fallback's front, +Z, then faces the turn)
local function pieceFrame(base, spec)
	return base * CFrame.new(spec.offset[1], spec.offset[2], spec.offset[3]) * CFrame.Angles(0, math.rad(spec.turn or 0), 0)
end

-- The part's name: the piece's name and the role (a second part with the same role gets a number)
local function roleName(spec, role, seen)
	local n = (seen[role] or 0) + 1
	seen[role] = n
	return spec.name .. "_" .. role .. (n > 1 and tostring(n) or "")
end

-- The Parts version of a kit piece: its fallback boxes, scaled from the piece's bottom-center, in the role's color
local function buildFallback(parent, base, spec, entry)
	local sx, sy, sz = scaleOf(spec)
	local target = pieceFrame(base, spec)
	local seen, made = {}, {}
	for _, b in ipairs(entry.fallback) do
		local look = spec.roles[b.role]
		local name = roleName(spec, b.role, seen)
		local lit = spec.light and b.role == spec.lightRole and seen[b.role] == 1
		table.insert(made, PlotVisuals.buildPart(parent, target, {
			name = name, shape = b.shape or "Block",
			size = { b.size[1] * sx, b.size[2] * sy, b.size[3] * sz },
			offset = { b.at[1] * sx, b.at[2] * sy, b.at[3] * sz },
			color = look[1], material = look[2], transparency = look[3],
			light = lit and spec.light or nil,
		}))
	end
	return made
end

-- The axis of a part (1 X, 2 Y, 3 Z) that lies along the model's axis (1 X, 2 Y, 3 Z), or nil when it is turned otherwise
local function alignedAxis(rel, axis)
	local _, _, _, r00, r01, r02, r10, r11, r12, r20, r21, r22 = rel:GetComponents()
	local row = ({ { r00, r01, r02 }, { r10, r11, r12 }, { r20, r21, r22 } })[axis]
	for i = 1, 3 do
		if math.abs(math.abs(row[i]) - 1) < 1e-4 then
			return i
		end
	end
	return nil
end

-- The kit version of a piece: a copy of each MeshPart of KitModels.<key>, fitted to the manifest size (KitSize), scaled,
-- turned (and by art.KIT_FRONT_TURN, the importer's turn), placed by the model's WorldPivot (its bottom-center), recolored
-- by its Role. Returns the parts, or nil and why (the Parts version is built then).
local function buildFromKit(parent, base, spec, entry, template, frontTurn)
	if not template:IsA("Model") then
		return nil, "it is not a Model"
	end
	local real = template:GetAttribute("KitSize")
	local ok = typeof(real) == "Vector3" and real.X > 0 and real.Y > 0 and real.Z > 0
	local sx, sy, sz = scaleOf(spec)
	local f = {
		sx * entry.size[1] / (ok and real.X or entry.size[1]),
		sy * entry.size[2] / (ok and real.Y or entry.size[2]),
		sz * entry.size[3] / (ok and real.Z or entry.size[3]),
	}
	local uniform = math.abs(f[1] - f[2]) < 1e-6 and math.abs(f[2] - f[3]) < 1e-6
	local pivot = template.WorldPivot
	local target = pieceFrame(base, spec) * CFrame.Angles(0, math.rad(frontTurn), 0)
	local made, seen = {}, {}
	local function fail(why)
		for _, p in ipairs(made) do
			p:Destroy()
		end
		return nil, why
	end
	for _, d in ipairs(template:GetDescendants()) do
		if d:IsA("MeshPart") then
			local role = d:GetAttribute("Role") or (string.gsub(d.Name, "%d+$", ""))
			local look = spec.roles[role]
			if not look then
				return fail("a MeshPart has a role the piece has no color for (" .. tostring(role) .. ")")
			end
			local rel = pivot:ToObjectSpace(d.CFrame)
			local size = { d.Size.X, d.Size.Y, d.Size.Z }
			local out = { size[1] * f[1], size[2] * f[2], size[3] * f[3] }
			if not uniform then -- each model axis scales the part's side that lies along it: the part must be square to the model
				for axis = 1, 3 do
					local a = alignedAxis(rel, axis)
					if not a then
						return fail("a part is not square to the model, so it can't be scaled unevenly")
					end
					out[a] = size[a] * f[axis]
				end
			end
			local x, y, z = rel:GetComponents()
			rel = CFrame.new(x * f[1], y * f[2], z * f[3]) * rel.Rotation
			local part = d:Clone()
			if not part then -- Roblox's Clone gives nil when Archivable is off
				return fail("a MeshPart can't be copied (" .. d.Name .. ")")
			end
			for _, child in ipairs(part:GetChildren()) do
				child:Destroy() -- only the MeshPart itself
			end
			part.Name = roleName(spec, role, seen)
			part.Size = Vector3.new(out[1], out[2], out[3])
			part.CFrame = target * rel
			part.Color = rgb(look[1])
			part.Material = Enum.Material[look[2]]
			part.Transparency = look[3] or 0
			part.Anchored = true
			part.CanCollide = false
			part.CanQuery = false
			part.CanTouch = false
			local longest = math.max(out[1], out[2], out[3])
			part.CastShadow = longest >= PlotVisuals.TINY and out[2] > PlotVisuals.FLAT and look[2] ~= "Neon" and (look[3] or 0) < 0.5
			if spec.light and role == spec.lightRole and seen[role] == 1 then
				local point = Instance.new("PointLight")
				point.Name = "Light"
				point.Color = rgb(spec.light.color)
				point.Brightness = spec.light.brightness
				point.Range = spec.light.range
				point.Shadows = false
				point.Parent = part
			end
			part.Parent = parent
			table.insert(made, part)
		elseif not d:IsA("Model") and not d:IsA("Folder") then
			warnOnce("kit extras " .. spec.kit, "KitModels." .. spec.kit .. ": " .. d.Name .. " is not a MeshPart, so it is left out of the room")
		end
	end
	if #made == 0 then
		return fail("it has no MeshPart")
	end
	return made
end

-- One kit piece: from the kit when it has the model, else from Parts (one warning per model per server)
function PlotVisuals.buildKitPiece(parent, base, spec, art, kit)
	local entry = art.Kit[spec.kit]
	local template = kit and kit:FindFirstChild(spec.kit)
	if template then
		local made, why = buildFromKit(parent, base, spec, entry, template, art.KIT_FRONT_TURN or 0)
		if made then
			return made
		end
		warnOnce("kit " .. spec.kit, "KitModels." .. spec.kit .. " can't be used in the rooms (" .. tostring(why) .. "): built from Parts")
	elseif kit then
		warnOnce("kit " .. spec.kit, "KitModels." .. spec.kit .. " is missing: the rooms build it from Parts")
	end
	return buildFallback(parent, base, spec, entry)
end

-- A Model with one part per spec, all placed from the same base CFrame (a kit piece is built from the kit or from Parts)
function PlotVisuals.buildGroup(parent, name, base, specs, art, kit)
	local model = Instance.new("Model")
	model.Name = name
	for _, spec in ipairs(specs) do
		if spec.kit then
			PlotVisuals.buildKitPiece(model, base, spec, art, kit)
		else
			PlotVisuals.buildPart(model, base, spec)
		end
	end
	model.Parent = parent
	return model
end

-- The box around some parts in the garage's frame (origin): { minX, maxX, minY, maxY, minZ, maxZ }, or nil
local function boxAround(parts, origin)
	local b
	for _, part in ipairs(parts) do
		local p = boxOf(origin:ToObjectSpace(part.CFrame), part.Size)
		if b then
			b = { math.min(b[1], p[1]), math.max(b[2], p[2]), math.min(b[3], p[3]), math.max(b[4], p[4]), math.min(b[5], p[5]), math.max(b[6], p[6]) }
		else
			b = p
		end
	end
	return b
end

local function isSolid(part)
	return part:GetAttribute("Solid") == true
end
PlotVisuals.isSolid = isSolid

-- One solid box over b (a box in the garage's frame) from the floor up: invisible, anchored, collides, never touched, no
-- shadow (CanQuery stays on, like the plaza's Solid group: a colliding part is always queryable). nil when too low or thin.
local function makeSolid(parent, name, origin, b)
	local r = {}
	for k = 1, 6 do
		r[k] = math.floor(b[k] * 1000 + 0.500001) / 1000 -- the same box at every turn of the garage (float noise, exact halves up)
	end
	b = r
	local inset = PlotVisuals.SOLID_INSET
	local w, d = b[2] - b[1] - 2 * inset, b[6] - b[5] - 2 * inset
	local h = math.min(b[4], PlotVisuals.SOLID_MAX)
	if w < 0.2 or d < 0.2 or h < PlotVisuals.SOLID_MIN then
		return nil
	end
	local part = Instance.new("Part")
	part.Name = name
	part.Size = Vector3.new(w, h, d)
	part.CFrame = origin * CFrame.new((b[1] + b[2]) / 2, h / 2, (b[5] + b[6]) / 2)
	part.Transparency = 1
	part.Anchored = true
	part.CanCollide = true
	part.CanTouch = false
	part.CanQuery = true
	part.CastShadow = false
	part.Material = Enum.Material.SmoothPlastic
	part:SetAttribute("Solid", true)
	part.Parent = parent
	return part
end

-- A furniture piece's solid box (a hire desk with its chair, an upgrade prop, a catalog item): over all its parts, inside it
function PlotVisuals.addSolid(model, origin)
	local parts = {}
	for _, d in ipairs(model:GetDescendants()) do
		if d:IsA("BasePart") and not isSolid(d) then
			table.insert(parts, d)
		end
	end
	local b = boxAround(parts, origin)
	return b and makeSolid(model, model.Name .. "Solid", origin, b)
end

-- The decor's solid boxes: its parts that stand low inside the floor (not floor marks, not see-through, not the hire
-- desks: those have their own) are grouped by touching, and each group that stands on the floor and is at least
-- SOLID_MIN tall gets one box. Built once per room, in the room's Solids model.
function PlotVisuals.decorSolids(room, origin, art)
	local decor = room:FindFirstChild("Decor")
	if not decor then
		return 0
	end
	local half = art.Layout.floorSize[1] / 2
	local items = {}
	for _, d in ipairs(decor:GetDescendants()) do
		if d:IsA("BasePart") and not isSolid(d) and d.Transparency < 0.9 then
			local node, inDesk = d.Parent, false
			while node and node ~= decor do
				if string.find(node.Name, "HireDesk", 1, true) == 1 then
					inDesk = true
				end
				node = node.Parent
			end
			local b = boxOf(origin:ToObjectSpace(d.CFrame), d.Size)
			for k = 1, 6 do
				b[k] = math.floor(b[k] * 1000 + 0.500001) / 1000 -- the same groups at every turn of the garage (no float noise at TOUCH)
			end
			if not inDesk and b[4] - b[3] > PlotVisuals.FLAT and b[3] < 4 and b[3] > -TOUCH
				and b[1] > -half and b[2] < half and b[5] > -half and b[6] < half then
				table.insert(items, b)
			end
		end
	end
	local group = {}
	local function find(i)
		while group[i] ~= i do
			group[i] = group[group[i]]
			i = group[i]
		end
		return i
	end
	for i = 1, #items do
		group[i] = i
	end
	for i = 1, #items do
		local a = items[i]
		for j = i + 1, #items do
			local b = items[j]
			if a[1] <= b[2] + TOUCH and b[1] <= a[2] + TOUCH and a[3] <= b[4] + TOUCH and b[3] <= a[4] + TOUCH
				and a[5] <= b[6] + TOUCH and b[5] <= a[6] + TOUCH then
				group[find(i)] = find(j)
			end
		end
	end
	local boxes, onFloor = {}, {}
	for i, b in ipairs(items) do
		local g = find(i)
		local u = boxes[g]
		boxes[g] = u and { math.min(u[1], b[1]), math.max(u[2], b[2]), math.min(u[3], b[3]), math.max(u[4], b[4]), math.min(u[5], b[5]), math.max(u[6], b[6]) } or b
		onFloor[g] = onFloor[g] or b[3] <= TOUCH
	end
	local model = Instance.new("Model")
	model.Name = PlotVisuals.SOLIDS
	local keys = {}
	for g in pairs(boxes) do
		table.insert(keys, g)
	end
	table.sort(keys)
	local count = 0
	for _, g in ipairs(keys) do
		if onFloor[g] and makeSolid(model, "DecorSolid" .. (count + 1), origin, boxes[g]) then
			count += 1
		end
	end
	model.Parent = room
	return count
end

local function floorOrigin(center, art)
	if typeof(center) == "CFrame" then
		return center * CFrame.new(0, art.Layout.floorTop, 0) -- a turned garage
	end
	return CFrame.new(center.X, center.Y + art.Layout.floorTop, center.Z)
end

PlotVisuals.GHOST_TRANSPARENCY = 0.7 -- the "next hire" desk: see-through, no light, no shadow

-- The hire desks (the office grows with the team, overhaul phase 3): a desk at the first `desks` hire spots
-- (EmployeeServer's EMPLOYEE_SPOTS, copied in PlotArt.Layout; nil = every spot, the full room), each named HireDesk<i>, and
-- after them one see-through "next hire" desk at the next spot (HireDesk<i> too, attribute Ghost = true, so it keeps its
-- desk zone), none once every spot has a hire. Returns the index of the first new desk's Model (for the pop-in).
function PlotVisuals.buildDesks(decor, origin, art, stage, kit, desks)
	local look = art.Stages[stage]
	local spots = art.Layout.employeeSpots
	local count = desks == nil and #spots or math.clamp(math.floor(desks), 0, #spots)
	local last = desks == nil and count or math.min(count + 1, #spots)
	for i = 1, last do
		local spot, desk = spots[i], art.Layout.desks[i]
		local base = origin * CFrame.new(spot[1] + desk[1], 0, spot[2] + desk[2]) * CFrame.Angles(0, math.rad(desk[3]), 0)
		local model = PlotVisuals.buildGroup(decor, "HireDesk" .. i, base, look.desk, art, kit)
		model.WorldPivot = base -- the pop-in grows it from the floor
		if i <= count then
			PlotVisuals.addSolid(model, origin) -- the desk and its chair: one box (overhaul 2)
		else -- the next hire's spot: the same desk, see-through, walk-through
			model:SetAttribute("Ghost", true)
			for _, d in ipairs(model:GetDescendants()) do
				if d:IsA("BasePart") then
					d.Transparency = math.max(d.Transparency, PlotVisuals.GHOST_TRANSPARENCY)
					d.CastShadow = false
				elseif d:IsA("Light") then
					d:Destroy()
				end
			end
		end
	end
	return count
end

-- The room of one funding stage: its shell, its decor (with a desk for every hire spot, or for the first `desks` of
-- them plus the next hire's see-through one: see buildDesks) and an empty UpgradeProps model for the props of the
-- upgrades bought. kit = ReplicatedStorage.KitModels or nil (Parts only).
function PlotVisuals.buildRoom(parent, center, art, stage, kit, desks)
	local look = art.Stages[stage]
	local origin = floorOrigin(center, art)
	local room = Instance.new("Model")
	room.Name = "PlotRoom"
	room:SetAttribute("Stage", stage)
	room:SetAttribute("StageKey", look.key)
	PlotVisuals.buildGroup(room, "Shell", origin, look.shell, art, kit)
	local decor = PlotVisuals.buildGroup(room, "Decor", origin, look.decor, art, kit)
	PlotVisuals.buildDesks(decor, origin, art, stage, kit, desks)
	PlotVisuals.decorSolids(room, origin, art)
	local props = Instance.new("Model")
	props.Name = "UpgradeProps"
	props.Parent = room
	room.Parent = parent
	return room
end

-- The prop of one upgrade, standing in its slot (slot = TycoonCore's itemOffset, a Vector3).
-- nil when the art has no prop for that upgrade (TycoonCore then shows its plain block).
function PlotVisuals.buildProp(parent, center, art, upgrade, slot)
	local look = art.Props[upgrade]
	if not look then
		return nil
	end
	local base = floorOrigin(center, art) * CFrame.new(slot.X, 0, slot.Z)
	local model = PlotVisuals.buildGroup(nil, upgrade, base, look)
	model:SetAttribute("Upgrade", upgrade)
	PlotVisuals.addSolid(model, floorOrigin(center, art))
	model.WorldPivot = base -- the pop-in grows it from the floor
	model.Parent = parent
	return model
end

-- A catalog item's spot in its room (overhaul 2, PlotArt.Items): its zone in the garage's frame { x0, x1, y0, y1, z0, z1 }
function PlotVisuals.itemBox(look)
	local s = look.spot
	local quarter = (s.turn or 0) % 180 == 90
	local hw, hd = (quarter and s.d or s.w) / 2, (quarter and s.w or s.d) / 2
	return { s.x - hw, s.x + hw, s.y0 or 0, s.h, s.z - hd, s.z + hd }
end

-- The catalog items that have a spot in the room of `stage` (their own stage's room), sorted by name
function PlotVisuals.itemsOf(art, stage)
	local out = {}
	for key, look in pairs(art.Items or {}) do
		if look.stage == stage then
			table.insert(out, key)
		end
	end
	table.sort(out)
	return out
end

-- One catalog item, standing on its spot (its front, +Z in the art, turned by spot.turn), with its solid box
function PlotVisuals.buildItem(parent, center, art, key)
	local look = art.Items and art.Items[key]
	if not look then
		return nil
	end
	local origin = floorOrigin(center, art)
	local base = origin * CFrame.new(look.spot.x, 0, look.spot.z) * CFrame.Angles(0, math.rad(look.spot.turn or 0), 0)
	local model = PlotVisuals.buildGroup(nil, key, base, look.parts)
	model:SetAttribute("Item", key)
	PlotVisuals.addSolid(model, origin)
	model.WorldPivot = base -- the pop-in grows it from the floor
	model.Parent = parent
	return model
end

-- The Floor Part keeps its name and size (other code uses them): only color and material change
function PlotVisuals.styleFloor(floor, art, stage)
	local look = art.Stages[stage].floor
	floor.Color = rgb(look.color)
	floor.Material = Enum.Material[look.material]
end

-- One player's plot ---------------------------------------------------------

function PlotVisuals.newPlot(folder, center, art, floor, stage, kit)
	local frame = floor and CFrame.new(center) * floor.CFrame.Rotation or center -- the garage's turn comes from its Floor
	kit = kit or PlotVisuals.findKit(art)
	if not kit then
		warnOnce("no kit", "ReplicatedStorage." .. tostring(art.KIT_FOLDER) .. " is missing: the room furniture is built from Parts")
	end
	local plot = { folder = folder, center = center, frame = frame, art = art, floor = floor, kit = kit, room = nil, stage = nil, desks = 0 }
	PlotVisuals.setStage(plot, stage, false)
	return plot
end

-- A desk for each of the first `count` hires and a see-through one at the next spot (the team's size, never saved).
-- A desk that is new pops in (popIn); fewer desks (a hire poached or let go) just go. Nothing else of the room changes.
function PlotVisuals.setDesks(plot, count, popIn)
	local spots = plot.art.Layout.employeeSpots
	count = math.clamp(math.floor(tonumber(count) or 0), 0, #spots)
	local decor = plot.room and plot.room:FindFirstChild("Decor")
	if not decor then
		plot.desks = count
		return
	end
	local before = plot.desks or 0
	for _, child in ipairs(decor:GetChildren()) do
		if string.find(child.Name, "HireDesk", 1, true) == 1 then
			child:Destroy()
		end
	end
	plot.desks = count
	PlotVisuals.buildDesks(decor, floorOrigin(plot.frame, plot.art), plot.art, math.clamp(plot.stage or 1, 1, #plot.art.Stages), plot.kit, count)
	if popIn then
		for i = before + 1, count do
			local desk = decor:FindFirstChild("HireDesk" .. i)
			if desk then
				task.spawn(PlotVisuals.popIn, desk)
			end
		end
	end
end

-- Builds the room of `stage` and swaps it in. The props already bought move into the new room.
-- A stage past the last room shows the last room. plot.stage is set first, so a failed build is
-- never tried again every second.
function PlotVisuals.setStage(plot, stage, flash)
	plot.stage = stage
	local art = plot.art
	local shown = math.clamp(stage, 1, #art.Stages)
	local old = plot.room
	local room = PlotVisuals.buildRoom(nil, plot.frame, art, shown, plot.kit, plot.desks or 0)
	local props = room:FindFirstChild("UpgradeProps")
	local oldProps = old and old:FindFirstChild("UpgradeProps")
	if oldProps then
		for _, prop in ipairs(oldProps:GetChildren()) do
			if prop:GetAttribute("Item") == nil then -- a station prop moves along; the catalog items are the new room's
				prop.Parent = props
			end
		end
	end
	if plot.floor then
		PlotVisuals.styleFloor(plot.floor, art, shown)
	end
	room.Parent = plot.folder
	plot.room = room
	if old then
		old:Destroy()
	end
	PlotVisuals.setItems(plot, nil)
	if flash then
		task.spawn(PlotVisuals.flash, plot)
	end
	return room
end

function PlotVisuals.addProp(plot, upgrade, slot, popIn)
	local props = plot.room and plot.room:FindFirstChild("UpgradeProps")
	if not props then
		return nil
	end
	local model = PlotVisuals.buildProp(props, plot.frame, plot.art, upgrade, slot)
	if model and popIn then
		task.spawn(PlotVisuals.popIn, model)
	end
	return model
end

-- The catalog items on show (overhaul 2): the room shows the items of its own stage that `owned` has (TycoonCore's
-- data.owned, kept for the next room; nil = the last one given). A new one pops in when it is popKey (a purchase); one
-- that is no longer owned (an IPO) goes. Cheap enough to run every second.
function PlotVisuals.setItems(plot, owned, popKey)
	if owned ~= nil then
		plot.owned = owned
	end
	local props = plot.room and plot.room:FindFirstChild("UpgradeProps")
	if not props then
		return
	end
	local stage = plot.room:GetAttribute("Stage")
	for key, look in pairs(plot.art.Items or {}) do
		local model = props:FindFirstChild(key)
		local want = look.stage == stage and plot.owned ~= nil and plot.owned[key] == true
		if want and not model then
			model = PlotVisuals.buildItem(props, plot.frame, plot.art, key)
			if model and popKey == key then
				task.spawn(PlotVisuals.popIn, model)
			end
		elseif model and not want and model:GetAttribute("Item") ~= nil then
			model:Destroy()
		end
	end
end

-- Effects (they wait: run them with task.spawn) ----------------------------------

local function backOut(t)
	local s = 1.70158
	t -= 1
	return 1 + (s + 1) * t * t * t + s * t * t
end

-- A short grow from small to full size, with a little overshoot
function PlotVisuals.popIn(model)
	local start = os.clock()
	model:ScaleTo(POP_FROM)
	while model.Parent do
		local t = math.min((os.clock() - start) / POP_SECONDS, 1)
		model:ScaleTo(POP_FROM + (1 - POP_FROM) * backOut(t))
		if t >= 1 then
			return
		end
		task.wait()
	end
end

-- A quick bright flash over the plot with a burst of sparkles (a new stage, or back to the Garage)
function PlotVisuals.flash(plot)
	local fx = plot.art.Flash
	local part = PlotVisuals.buildPart(plot.folder, floorOrigin(plot.frame, plot.art), fx.part)
	local from = fx.part.transparency
	for i = 1, fx.steps do
		task.wait(fx.seconds / fx.steps)
		if not part.Parent then
			return
		end
		part.Transparency = from + (1 - from) * i / fx.steps
	end
	local emitter = part:FindFirstChild("Particles")
	if emitter then
		emitter.Enabled = false
	end
	task.wait(fx.linger) -- the last sparkles finish before their emitter goes
	part:Destroy()
end

-- Checks --------------------------------------------------------------------

-- Problems in the art data itself (empty list = fine)
function PlotVisuals.validate(art)
	local problems = {}
	local function problem(text)
		table.insert(problems, text)
	end
	local function finite(n)
		return type(n) == "number" and n == n and n ~= math.huge and n ~= -math.huge
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
	local function lightOk(l)
		return type(l) == "table" and colorOk(l.color) and finite(l.brightness) and l.brightness > 0 and finite(l.range) and l.range > 0 and l.range <= 60
	end
	-- A kit piece: a key of art.Kit, a spot, a quarter turn, a scale above 0, a color and an allowed material for each of
	-- the model's roles (Neon only when the piece's name says it is a light), a light only on one of its roles
	local function kitSpec(where, s)
		local entry = type(art.Kit) == "table" and art.Kit[s.kit]
		if type(entry) ~= "table" then
			problem(where .. ": unknown kit key " .. tostring(s.kit) .. " (add it to PlotArt.Kit)")
			return
		end
		if s.shape ~= nil or s.size ~= nil or s.rot ~= nil or s.text ~= nil or s.particles ~= nil or s.collide ~= nil then
			problem(where .. ": a kit piece has no shape, size, rot, text, particles or collide (its model gives them)")
		end
		if not triple(s.offset) then
			problem(where .. ": offset must be 3 numbers")
		end
		if s.turn ~= nil and not PlotVisuals.TURNS[s.turn] then
			problem(where .. ": turn must be 0, 90, 180 or 270")
		end
		local sc = s.scale
		if sc ~= nil and not ((type(sc) == "number" and finite(sc) and sc > 0) or triple(sc, true)) then
			problem(where .. ": scale must be a number above 0 or 3 of them")
		end
		if type(sc) == "table" and type(entry.fallback) == "table" then
			for _, b in ipairs(entry.fallback) do
				if b.shape == "Ball" and not (sc[1] == sc[2] and sc[2] == sc[3]) then
					problem(where .. ": " .. s.kit .. "'s Parts version has a Ball, so it scales evenly only")
					break
				end
			end
		end
		if type(s.roles) ~= "table" then
			problem(where .. ": roles missing (a color and a material for each role of " .. s.kit .. ")")
			return
		end
		for _, role in ipairs(entry.roles or {}) do
			local look = s.roles[role]
			if type(look) ~= "table" or not colorOk(look[1]) then
				problem(where .. ": role " .. role .. " needs a color")
			elseif not PlotVisuals.MATERIALS[look[2]] then
				problem(where .. ": material not allowed: " .. tostring(look[2]))
			elseif look[2] == "Neon" and not isLightName(s.name) then
				problem(where .. ": Neon is only for lights and signs (name it Bulb, Lamp, Light, Screen, LED, Sign, Logo...)")
			elseif look[3] ~= nil and not (finite(look[3]) and look[3] >= 0 and look[3] <= 1) then
				problem(where .. ": role " .. role .. ": transparency must be 0-1")
			end
		end
		for role in pairs(s.roles) do
			if not table.find(entry.roles or {}, role) then
				problem(where .. ": " .. s.kit .. " has no role " .. tostring(role))
			end
		end
		if s.light ~= nil then
			if not lightOk(s.light) then
				problem(where .. ": light needs color, brightness > 0 and range 0-60")
			end
			if not table.find(entry.roles or {}, s.lightRole) then
				problem(where .. ": a light needs lightRole, one of " .. s.kit .. "'s roles")
			end
		end
	end
	local function spec(where, s)
		local name = type(s) == "table" and s.name
		if type(name) ~= "string" or name == "" then
			problem(where .. ": a part without a name")
			return
		end
		where = where .. "." .. name
		if s.kit ~= nil then
			kitSpec(where, s)
			return
		end
		if not PlotVisuals.SHAPES[s.shape] then
			problem(where .. ": unknown shape " .. tostring(s.shape))
		end
		if not triple(s.size, true) then
			problem(where .. ": size must be 3 numbers above 0")
		elseif s.shape == "Ball" and not (s.size[1] == s.size[2] and s.size[2] == s.size[3]) then
			problem(where .. ": a Ball needs 3 equal sides")
		elseif s.shape == "Cylinder" and s.size[2] ~= s.size[3] then
			problem(where .. ": a Cylinder needs equal Y and Z (its diameter)")
		end
		if not triple(s.offset) then
			problem(where .. ": offset must be 3 numbers")
		end
		if s.rot ~= nil and not triple(s.rot) then
			problem(where .. ": rot must be 3 numbers (degrees)")
		end
		if not colorOk(s.color) then
			problem(where .. ": color must be 3 whole numbers 0-255")
		end
		if not PlotVisuals.MATERIALS[s.material] then
			problem(where .. ": material not allowed: " .. tostring(s.material))
		elseif s.material == "Neon" and not isLightName(name) then
			problem(where .. ": Neon is only for lights and signs (name it Bulb, Lamp, Light, Screen, LED, Sign, Logo...)")
		end
		if s.transparency ~= nil and not (finite(s.transparency) and s.transparency >= 0 and s.transparency <= 1) then
			problem(where .. ": transparency must be 0-1")
		end
		if s.collide ~= nil and s.collide ~= true then
			problem(where .. ": collide is true or left out")
		end
		if s.light and not lightOk(s.light) then
			problem(where .. ": light needs color, brightness > 0 and range 0-60")
		end
		if s.text then
			local t = s.text
			if type(t.value) ~= "string" or t.value == "" or not colorOk(t.color) or not PlotVisuals.FONTS[t.font or "GothamBold"]
				or (t.face ~= nil and not FACES[t.face]) then
				problem(where .. ": text needs a value, a color and a known font")
			end
		end
		if s.particles then
			local p = s.particles
			if not (finite(p.rate) and p.rate >= 0 and type(p.lifetime) == "table" and type(p.speed) == "table"
				and type(p.size) == "table" and type(p.transparency) == "table" and type(p.color) == "table"
				and colorOk(p.color[1]) and colorOk(p.color[2]) and finite(p.spread)
				and (p.direction == nil or FACES[p.direction])) then
				problem(where .. ": particles need rate, lifetime, speed, size, transparency, color, spread (and a face as direction)")
			end
		end
	end
	local function list(where, specs)
		if type(specs) ~= "table" then
			problem(where .. ": missing")
			return
		end
		local names = {}
		for i, s in ipairs(specs) do
			spec(where .. "[" .. i .. "]", s)
			if type(s) == "table" and s.name then
				if names[s.name] then
					problem(where .. ": two parts named " .. s.name)
				end
				names[s.name] = true
			end
		end
	end

	-- The kit models the rooms use: a size, its roles, and a Parts version (boxes inside the size, each role at least once)
	if type(art.Kit) ~= "table" or type(art.KIT_FOLDER) ~= "string" or not PlotVisuals.TURNS[art.KIT_FRONT_TURN] then
		problem("Kit: needs Kit, KIT_FOLDER and KIT_FRONT_TURN (0 or 180)")
	else
		for key, entry in pairs(art.Kit) do
			local where = "Kit." .. tostring(key)
			if type(entry) ~= "table" or not triple(entry.size, true) or type(entry.roles) ~= "table" or #entry.roles == 0 or type(entry.fallback) ~= "table" then
				problem(where .. ": needs size (3 numbers above 0), roles and fallback")
			else
				local used = {}
				local w, h, d = entry.size[1], entry.size[2], entry.size[3]
				local fit = PlotVisuals.KIT_FIT
				for i, b in ipairs(entry.fallback) do
					if not table.find(entry.roles, b.role) then
						problem(where .. ".fallback[" .. i .. "]: unknown role " .. tostring(b.role))
					end
					used[b.role] = true
					if not (triple(b.size, true) and triple(b.at)) then
						problem(where .. ".fallback[" .. i .. "]: size and at must be 3 numbers")
					else
						if b.shape ~= nil and b.shape ~= "Block" and b.shape ~= "Ball" then
							problem(where .. ".fallback[" .. i .. "]: a box is a Block or a Ball")
						elseif b.shape == "Ball" and not (b.size[1] == b.size[2] and b.size[2] == b.size[3]) then
							problem(where .. ".fallback[" .. i .. "]: a Ball needs 3 equal sides")
						end
						local x0, x1 = b.at[1] - b.size[1] / 2, b.at[1] + b.size[1] / 2
						local y0, y1 = b.at[2] - b.size[2] / 2, b.at[2] + b.size[2] / 2
						local z0, z1 = b.at[3] - b.size[3] / 2, b.at[3] + b.size[3] / 2
						if x0 < -w / 2 - fit or x1 > w / 2 + fit or y0 < -fit or y1 > h + fit or z0 < -d / 2 - fit or z1 > d / 2 + fit then
							problem(where .. ".fallback[" .. i .. "]: the box sticks out of the model's size")
						end
					end
				end
				for _, role in ipairs(entry.roles) do
					if not used[role] then
						problem(where .. ": the Parts version has no box for role " .. role)
					end
				end
			end
		end
	end

	local layout = art.Layout
	if type(layout) ~= "table" or type(layout.employeeSpots) ~= "table" or type(layout.desks) ~= "table" then
		problem("Layout: missing")
		return problems
	end
	if #layout.desks ~= #layout.employeeSpots then
		problem("Layout: one desk per employee spot")
	end
	if type(art.Stages) ~= "table" or #art.Stages == 0 then
		problem("Stages: missing")
		return problems
	end
	for i, stage in ipairs(art.Stages) do
		local where = "Stage " .. i
		if type(stage.key) ~= "string" then
			problem(where .. ": needs the key of its funding stage")
		end
		if type(stage.floor) ~= "table" or not colorOk(stage.floor.color) or not PlotVisuals.MATERIALS[stage.floor.material] then
			problem(where .. ": floor needs a color and an allowed material")
		end
		list(where .. " shell", stage.shell)
		list(where .. " decor", stage.decor)
		list(where .. " desk", stage.desk)
	end
	if type(art.Props) ~= "table" then
		problem("Props: missing")
	else
		for upgrade, specs in pairs(art.Props) do
			list("Prop " .. tostring(upgrade), specs)
		end
	end
	if art.Items ~= nil then
		for key, look in pairs(art.Items) do
			local where = "Item " .. tostring(key)
			local s = type(look) == "table" and look.spot
			if type(look) ~= "table" or type(look.stage) ~= "number" or look.stage % 1 ~= 0 or look.stage < 1 or look.stage > #art.Stages then
				problem(where .. ": needs the stage of its room (1 to " .. #art.Stages .. ")")
			elseif type(s) ~= "table" or not (finite(s.x) and finite(s.z) and finite(s.w) and finite(s.d) and finite(s.h) and s.w > 0 and s.d > 0 and s.h > 0)
				or (s.turn ~= nil and not PlotVisuals.TURNS[s.turn]) or (s.y0 ~= nil and not (finite(s.y0) and s.y0 >= 0 and s.y0 < s.h)) then
				problem(where .. ": spot needs x, z, w, d, h (above 0), a quarter turn and y0 under h")
			end
			if type(look) == "table" then
				list(where, look.parts)
			end
		end
	end
	if type(art.Flash) ~= "table" or type(art.Flash.part) ~= "table" then
		problem("Flash: missing")
	else
		spec("Flash", art.Flash.part)
	end
	return problems
end

-- The aisles of the hire grid, from the layout map: the strip between the incubators and the first row
-- of hires, and the strips between rows (a hire's desk is in front of it). Each is { x0, x1, z0, z1 }
-- over the width of the grid; its depth z1 - z0 must be at least reserve.minAisle.
function PlotVisuals.aisles(layout)
	local r = layout.reserve
	local rows, x0, x1 = {}, math.huge, -math.huge
	local seen = {}
	for _, spot in ipairs(layout.employeeSpots) do
		if not seen[spot[2]] then
			seen[spot[2]] = true
			table.insert(rows, spot[2])
		end
		x0 = math.min(x0, spot[1] - r.deskHalfX)
		x1 = math.max(x1, spot[1] + r.deskHalfX)
	end
	table.sort(rows)
	local doorEnd = -math.huge
	for _, spot in ipairs(layout.incubators) do
		doorEnd = math.max(doorEnd, spot[2] + r.incubatorFront)
	end
	local aisles = { { x0, x1, doorEnd, rows[1] - r.hireHalf } }
	for i = 2, #rows do
		table.insert(aisles, { x0, x1, rows[i - 1] + r.deskTo, rows[i] - r.hireHalf })
	end
	return aisles
end

-- The reserved gameplay zones from the layout map: boxes no room part may enter (the garage signs,
-- the spawn and the walking lane down the middle, incubators and the space in front of them, where each
-- hire stands and its desk, the aisles) and the upgrade slots (only that upgrade's prop goes in its slot).
function PlotVisuals.zones(layout, art, stage)
	local r = layout.reserve
	local zones = {}
	local function add(kind, name, x0, x1, z0, z1, top, owner)
		table.insert(zones, { kind = kind, name = name, owner = owner, box = { x0, x1, 0, top, z0, z1 } })
	end
	for _, sign in ipairs(layout.signs) do
		add("sign", sign.name, sign.x - r.signHalfX, sign.x + r.signHalfX, sign.z - r.signHalfZ, sign.z + r.signHalfZ, r.signHeight)
	end
	local s = layout.spawn
	add("spawn", "Spawn", s.x - r.spawnHalf, s.x + r.spawnHalf, s.z - r.spawnHalf, s.z + r.spawnHalf, r.height)
	local aisles = PlotVisuals.aisles(layout)
	add("lane", "WalkingLane", s.x - r.spawnHalf, s.x + r.spawnHalf, aisles[1][3], r.laneEnd, r.height)
	for i, spot in ipairs(layout.incubators) do
		add("incubator", "Incubator" .. i, spot[1] - r.incubatorHalf, spot[1] + r.incubatorHalf,
			spot[2] - r.incubatorHalf, spot[2] + r.incubatorFront, r.height)
	end
	for i, spot in ipairs(layout.employeeSpots) do
		add("hire", "Hire" .. i, spot[1] - r.hireHalf, spot[1] + r.hireHalf, spot[2] - r.hireHalf, spot[2] + r.hireHalf, r.hireHeight, "HireDesk" .. i)
		add("desk", "HireDesk" .. i, spot[1] - r.deskHalfX, spot[1] + r.deskHalfX, spot[2] + r.deskFrom, spot[2] + r.deskTo, r.deskHeight)
	end
	for _, slot in ipairs(layout.itemSlots) do
		add("slot", slot.name, slot.x - r.slotHalfX, slot.x + r.slotHalfX, slot.z - r.slotBack, slot.z + r.slotFront, r.slotHeight, slot.name)
	end
	for i, a in ipairs(aisles) do
		add("aisle", i == 1 and "DoorAisle" or ("RowAisle" .. (i - 1)), a[1], a[2], a[3], a[4], r.height)
	end
	-- The catalog items' spots in this stage's room (overhaul 2): only that item goes in its spot
	if art and stage then
		for _, key in ipairs(PlotVisuals.itemsOf(art, stage)) do
			table.insert(zones, { kind = "item", name = key, owner = key, box = PlotVisuals.itemBox(art.Items[key]) })
		end
	end
	return zones
end

-- Problems in a built room (props inside it included): parts in a reserved zone, props outside
-- their slot, floating parts, walls too high where the camera looks in, flags, the part and
-- light budgets. center = the plot center (or the garage's frame) the room was built at: every part
-- is measured in the garage's own frame, so a turned room gets the same checks.
function PlotVisuals.check(room, center, art)
	local problems = {}
	local function problem(text)
		table.insert(problems, text)
	end
	local layout = art.Layout
	local origin = floorOrigin(center, art)
	local half = layout.floorSize[1] / 2
	local ground = -layout.floorSize[2] -- the Floor's bottom: where the Baseplate's top is
	local parts, lights = {}, 0
	for _, d in ipairs(room:GetDescendants()) do
		if d:IsA("PointLight") or d:IsA("SpotLight") or d:IsA("SurfaceLight") then
			lights += 1
		elseif d:IsA("BasePart") then
			local b = boxOf(origin:ToObjectSpace(d.CFrame), d.Size) -- in the garage's frame
			local upgrade, item, deskName, node = nil, nil, nil, d.Parent
			while node and node ~= room do
				upgrade = upgrade or node:GetAttribute("Upgrade")
				item = item or node:GetAttribute("Item")
				if not deskName and string.find(node.Name, "HireDesk", 1, true) == 1 then
					deskName = node.Name
				end
				node = node.Parent
			end
			local flat = b[4] - b[3] <= PlotVisuals.FLAT and (math.abs(b[3]) <= TOUCH or math.abs(b[3] - ground) <= TOUCH)
			table.insert(parts, { part = d, name = d:GetFullName(), box = b, upgrade = upgrade, item = item, desk = deskName, flat = flat, solid = isSolid(d) })
		end
	end
	if #parts > PlotVisuals.MAX_PARTS then
		problem(string.format("%d parts (budget %d)", #parts, PlotVisuals.MAX_PARTS))
	end
	if lights > PlotVisuals.MAX_LIGHTS then
		problem(string.format("%d lights (budget %d)", lights, PlotVisuals.MAX_LIGHTS))
	end

	local zones = PlotVisuals.zones(layout, art, room:GetAttribute("Stage"))
	local slotOf, deskOf, itemOf = {}, {}, {}
	for _, zone in ipairs(zones) do
		if zone.kind == "slot" then
			slotOf[zone.owner] = zone
		elseif zone.kind == "item" then
			itemOf[zone.owner] = zone.box
		elseif zone.kind == "desk" then
			-- a workstation: the desk zone and, behind it, the hire's spot where its chair stands (overhaul 2)
			local spot = layout.employeeSpots[tonumber(string.sub(zone.name, 9))]
			local r = layout.reserve
			deskOf[zone.name] = { zone.box[1], zone.box[2], 0, r.hireHeight, spot[2] - r.hireHalf, zone.box[6] }
		end
	end
	for _, p in ipairs(parts) do
		local part, b = p.part, p.box
		-- Flags
		if not part.Anchored then
			problem(p.name .. ": not anchored")
		end
		if part.CanTouch then
			problem(p.name .. ": CanTouch is on")
		end
		if p.solid then
			if not (part.CanCollide and part.CanQuery and part.Transparency == 1 and not part.CastShadow) then
				problem(p.name .. ": a solid box is CanCollide on, CanQuery on, Transparency 1, no shadow")
			end
			if b[3] > TOUCH or b[3] < -TOUCH or b[4] > PlotVisuals.SOLID_MAX + OVERLAP then
				problem(p.name .. ": a solid box stands on the floor, at most " .. PlotVisuals.SOLID_MAX .. " tall")
			end
		elseif part.CanCollide then
			if not (string.find(part.Name, "Floor", 1, true) or string.find(part.Name, "LowWall", 1, true)) then
				problem(p.name .. ": only floors and low walls may collide")
			end
		elseif part.CanQuery then
			problem(p.name .. ": decor must have CanQuery off")
		end
		if math.max(part.Size.X, part.Size.Y, part.Size.Z) < PlotVisuals.TINY and part.CastShadow then
			problem(p.name .. ": a tiny part casts a shadow")
		end
		if not PlotVisuals.MATERIALS[part.Material.Name] then
			problem(p.name .. ": material not allowed: " .. part.Material.Name)
		elseif part.Material.Name == "Neon" and not isLightName(part.Name) then
			problem(p.name .. ": Neon on something that isn't a light or a sign")
		end
		-- Reserved zones
		for _, zone in ipairs(zones) do
			if (not p.flat or zone.kind == "sign") and overlaps(b, zone.box, OVERLAP)
				and not (zone.kind == "slot" and p.upgrade == zone.owner) and not (zone.kind == "desk" and p.desk == zone.name)
				and not (zone.kind == "hire" and p.desk == zone.owner) and not (zone.kind == "item" and p.item == zone.owner) then
				problem(p.name .. " is inside " .. zone.kind .. " zone " .. zone.name)
			end
		end
		if p.upgrade then
			local own = slotOf[p.upgrade]
			local z = own and own.box
			if not z or b[1] < z[1] - OVERLAP or b[2] > z[2] + OVERLAP or b[5] < z[5] - OVERLAP or b[6] > z[6] + OVERLAP or b[4] > z[4] + OVERLAP then
				problem(p.name .. ": a prop must stay inside its own slot")
			end
		end
		if p.item then
			local z = itemOf[p.item]
			if not z or b[1] < z[1] - OVERLAP or b[2] > z[2] + OVERLAP or b[5] < z[5] - OVERLAP or b[6] > z[6] + OVERLAP or b[4] > z[4] + OVERLAP
				or (b[3] < z[3] - OVERLAP and not p.solid) then
				problem(p.name .. ": a catalog item must stay inside its own spot")
			end
		end
		if p.desk then
			local z = deskOf[p.desk]
			if not z or b[1] < z[1] - OVERLAP or b[2] > z[2] + OVERLAP or b[5] < z[5] - OVERLAP or b[6] > z[6] + OVERLAP or b[4] > z[4] + OVERLAP then
				problem(p.name .. ": a hire desk must stay inside its own desk zone")
			end
		end
		-- A solid box never sticks out of its piece (inside its desk, slot or spot by the checks above)
		if p.solid and not (p.desk or p.upgrade or p.item) and not (part.Parent and part.Parent.Name == PlotVisuals.SOLIDS) then
			problem(p.name .. ": a solid box of no furniture piece")
		end
		-- Walls where the camera looks in
		if string.find(part.Name, "Skyline", 1, true) == 1 then
			if b[6] > PlotVisuals.BACKDROP_Z or b[4] > PlotVisuals.BACKDROP_MAX then
				problem(p.name .. ": the skyline stays behind the back wall and under " .. PlotVisuals.BACKDROP_MAX)
			end
		elseif b[6] <= PlotVisuals.BACK_BAND then
			if b[4] > PlotVisuals.BACK_WALL_MAX + OVERLAP then
				problem(p.name .. ": taller than the back wall limit")
			end
		elseif (b[1] <= -half + 1 or b[2] >= half - 1 or b[6] >= half - 1) and b[4] > PlotVisuals.SIDE_WALL_MAX + OVERLAP then
			problem(p.name .. ": taller than " .. PlotVisuals.SIDE_WALL_MAX .. " on a side the camera looks in over")
		end
	end

	-- Every furniture piece has its solid box: a real hire desk, an upgrade prop, a catalog item
	for _, d in ipairs(room:GetDescendants()) do
		if d:IsA("Model") and ((string.find(d.Name, "HireDesk", 1, true) == 1 and not d:GetAttribute("Ghost")) or d:GetAttribute("Upgrade") or d:GetAttribute("Item")) then
			local has = false
			for _, c in ipairs(d:GetChildren()) do
				has = has or (c:IsA("BasePart") and isSolid(c))
			end
			if not has then
				problem(d:GetFullName() .. ": a furniture piece without its solid box")
			end
		end
	end

	-- Floating parts: everything must rest on the Floor, the ground or a chain of touching parts
	local supported, queue = {}, {}
	for i, p in ipairs(parts) do
		local b = p.box
		local onFloor = b[3] <= TOUCH and b[3] >= ground - TOUCH and b[1] < half and b[2] > -half and b[5] < half and b[6] > -half
		if onFloor or b[3] <= ground + TOUCH then
			supported[i] = true
			table.insert(queue, i)
		end
	end
	local head = 1
	while head <= #queue do
		local a = parts[queue[head]].box
		head += 1
		for j, p in ipairs(parts) do
			if not supported[j] then
				local b = p.box
				if a[1] <= b[2] + TOUCH and b[1] <= a[2] + TOUCH and a[3] <= b[4] + TOUCH and b[3] <= a[4] + TOUCH
					and a[5] <= b[6] + TOUCH and b[5] <= a[6] + TOUCH then
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
	return problems
end

return PlotVisuals
