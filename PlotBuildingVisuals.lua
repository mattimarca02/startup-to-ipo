-- PlotBuildingVisuals: builds the building around a stage room and holds the pure maths of the roof
-- fade (branch building-pass). Put this ModuleScript in ServerScriptService, next to PlotBuilding
-- (the data) and TycoonCore (which calls it through its looks() helper).
--
-- Only looks: nothing here is saved, sent through a remote or read back by the game. Every part it
-- builds is anchored, with CanCollide, CanTouch and CanQuery off and no shadow, so the building never
-- changes how anything plays. The client script BuildingClient (a LocalScript made by hand in
-- StarterPlayerScripts, source in docs/studio_scripts/) fades it when the local player is inside.
-- The server never learns who is inside: it only publishes the numbers as attributes of the Model.
--
--   PlotBuildingVisuals.build(parent, center, art, building, stage) -> Model "PlotBuilding": Fade, Static
--   PlotBuildingVisuals.sync(folder, center, art, building, stage)  -> the Model for that stage in the plot folder
--                                                                      (does nothing when it already shows it)
--   PlotBuildingVisuals.bounds(center, art, building)               -> the inside box, in world studs (pure)
--   PlotBuildingVisuals.validate(building)                          -> problems in the data (empty = fine)
--   PlotBuildingVisuals.check(model, center, art, building, opts)   -> problems in a built Model (budgets, flags, zones...)
--   Pure maths, the same text as BuildingClient (a test compares them):
--   isInside(bounds, x, y, z, wasInside), fadeStep(fade, target, dt, seconds), quantize(fade, levels),
--   transparencyAt(base, level, levels)
--
-- Offsets in the data are studs from the plot's floor-top center (the middle of the Floor's top face,
-- plot center + art.Layout.floorTop). +X is right, +Z is the front (the door), -Z the back wall.

local PlotBuildingVisuals = {}

PlotBuildingVisuals.TAG = "PlotBuilding" -- CollectionService tag on the Model: the client finds buildings by it
PlotBuildingVisuals.MATERIALS = {
	Concrete = true, CorrodedMetal = true, Metal = true, DiamondPlate = true, Wood = true, WoodPlanks = true,
	Brick = true, Fabric = true, Plastic = true, SmoothPlastic = true, Glass = true, Neon = true,
}
PlotBuildingVisuals.SHAPES = { Block = true, Cylinder = true, Ball = true }
PlotBuildingVisuals.FONTS = { GothamBold = true, PermanentMarker = true, IndieFlower = true, LuckiestGuy = true, FredokaOne = true }
PlotBuildingVisuals.LIGHT_WORDS = { "Bulb", "Lamp", "Light", "Screen", "LED", "Sign", "Logo", "Neon", "Glow" }
PlotBuildingVisuals.MAX_REACH = 40 -- no part further than this from the plot center on x or z
PlotBuildingVisuals.MAX_HEIGHT = 24 -- or higher than this above the floor top

local OVERLAP = 0.01 -- parts must go this far into another to count as inside it
local TOUCH = 0.06 -- parts closer than this touch (floating check)

-- The pure maths ---------------------------------------------------------------------------------------
-- No services, no Instances: they run the same in the tests (a fake Roblox) and in BuildingClient, which
-- carries a copy of this block (tools/building_test.py fails if the two texts differ).

-- BUILDINGMATH-START
local function clamp01(n)
	if n ~= n then
		return 0
	end
	if n < 0 then
		return 0
	elseif n > 1 then
		return 1
	end
	return n
end

local function finite(n)
	return type(n) == "number" and n == n and n ~= math.huge and n ~= -math.huge
end

-- Is a point inside the building? b = { minX, maxX, minY, maxY, minZ, maxZ, doorMinX, doorMaxX, doorDepth, margin }
-- (world studs; maxY is the underside of the roof; the door is on the +Z side). Edges count as inside. The
-- doorway and the apron in front of it count too, so the front wall starts to fade as you walk up to the
-- door. Above the roof is outside. wasInside makes the box `margin` bigger (no flicker on a wall line).
-- A coordinate that is NaN or infinite is never inside.
local function isInside(b, x, y, z, wasInside)
	if not (finite(x) and finite(y) and finite(z)) then
		return false
	end
	local m = wasInside and b.margin or 0
	if y < b.minY - m or y > b.maxY + m then
		return false
	end
	if z >= b.minZ - m and z <= b.maxZ + m and x >= b.minX - m and x <= b.maxX + m then
		return true
	end
	return z > b.maxZ and z <= b.maxZ + b.doorDepth + m and x >= b.doorMinX - m and x <= b.doorMaxX + m
end

-- Moves the fade (0 = solid, 1 = gone) toward the target by dt / seconds, never past it, always in 0..1.
-- A dt that is zero, negative or NaN changes nothing; seconds that are zero, negative or NaN jump to the target.
local function fadeStep(fade, target, dt, seconds)
	fade, target = clamp01(fade), clamp01(target)
	if not (dt > 0) then
		return fade
	end
	if not (seconds > 0) then
		return target
	end
	local step = dt / seconds
	if fade < target then
		return clamp01(math.min(fade + step, target))
	elseif fade > target then
		return clamp01(math.max(fade - step, target))
	end
	return fade
end

-- The fade as a whole step 0..levels (Transparency is only written when this changes)
local function quantize(fade, levels)
	local n = math.max(1, math.floor(levels + 0.5))
	return math.floor(clamp01(fade) * n + 0.5)
end

-- A part's Transparency at a step: its own base value at step 0, 1 (gone) at the last step, in 0..1
local function transparencyAt(base, level, levels)
	local n = math.max(1, math.floor(levels + 0.5))
	local b = clamp01(base)
	return clamp01(b + (1 - b) * clamp01(level / n))
end
-- BUILDINGMATH-END

PlotBuildingVisuals.isInside = isInside
PlotBuildingVisuals.fadeStep = fadeStep
PlotBuildingVisuals.quantize = quantize
PlotBuildingVisuals.transparencyAt = transparencyAt

-- Helpers ---------------------------------------------------------------------------------------------

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
PlotBuildingVisuals.boxOf = boxOf

local function overlaps(a, b, margin)
	return a[1] < b[2] - margin and b[1] < a[2] - margin
		and a[3] < b[4] - margin and b[3] < a[4] - margin
		and a[5] < b[6] - margin and b[5] < a[6] - margin
end

local function isLightName(name)
	for _, word in ipairs(PlotBuildingVisuals.LIGHT_WORDS) do
		if string.find(name, word, 1, true) then
			return true
		end
	end
	return false
end

local function floorOrigin(center, art)
	return CFrame.new(center.X, center.Y + art.Layout.floorTop, center.Z)
end

-- The inside box of a building at this plot center, in world studs (the numbers the client reads)
function PlotBuildingVisuals.bounds(center, art, building)
	local E, I = building.Envelope, building.Inside
	local floorY = center.Y + art.Layout.floorTop
	return {
		minX = center.X - E.inner, maxX = center.X + E.inner,
		minZ = center.Z - E.inner, maxZ = center.Z + E.inner,
		minY = floorY - I.floorBelow, maxY = floorY + E.roofBottom,
		doorMinX = center.X - E.doorHalf, doorMaxX = center.X + E.doorHalf,
		doorDepth = I.doorDepth, margin = I.margin,
	}
end

-- The attribute names the client reads, in the order of the bounds table
PlotBuildingVisuals.ATTRIBUTES = {
	minX = "MinX", maxX = "MaxX", minY = "MinY", maxY = "MaxY", minZ = "MinZ", maxZ = "MaxZ",
	doorMinX = "DoorMinX", doorMaxX = "DoorMaxX", doorDepth = "DoorDepth", margin = "Margin",
}

-- Building ----------------------------------------------------------------------------------------------

-- One part from its spec. Always anchored, never solid, never touched, never hit by a ray, no shadow.
function PlotBuildingVisuals.buildPart(parent, base, spec)
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
	part.CanCollide = false
	part.CanTouch = false
	part.CanQuery = false
	part.CastShadow = false
	part.TopSurface = Enum.SurfaceType.Smooth
	part.BottomSurface = Enum.SurfaceType.Smooth

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
		label.Parent = gui
	end

	part.Parent = parent
	return part
end

local function buildGroup(parent, name, base, specs)
	local model = Instance.new("Model")
	model.Name = name
	for _, spec in ipairs(specs) do
		PlotBuildingVisuals.buildPart(model, base, spec)
	end
	model.Parent = parent
	return model
end

-- A stage past the last building shows the last one; below 1 shows the first
local function shownStage(building, stage)
	local last = #building.Stages
	if type(stage) ~= "number" or stage ~= stage then
		return 1
	end
	return math.clamp(math.floor(stage), 1, last)
end

-- The Model "PlotBuilding" of one stage: Fade (the roof, the walls, the front: everything that fades) and
-- Static (ground pieces). Its attributes are everything BuildingClient needs.
function PlotBuildingVisuals.build(parent, center, art, building, stage)
	local shown = shownStage(building, stage)
	local look = building.Stages[shown]
	local origin = floorOrigin(center, art)
	local model = Instance.new("Model")
	model.Name = "PlotBuilding"
	model:SetAttribute("Stage", shown)
	model:SetAttribute("StageKey", look.key)
	local bounds = PlotBuildingVisuals.bounds(center, art, building)
	for field, attribute in pairs(PlotBuildingVisuals.ATTRIBUTES) do
		model:SetAttribute(attribute, bounds[field])
	end
	model:SetAttribute("FadeSeconds", building.Fade.seconds)
	model:SetAttribute("FadeLevels", building.Fade.levels)
	buildGroup(model, "Fade", origin, look.fade)
	buildGroup(model, "Static", origin, look.static)
	-- Tag it before it enters the game, so the client sees it the moment it arrives
	local ok, service = pcall(function()
		return game:GetService("CollectionService")
	end)
	if ok and service then
		service:AddTag(model, PlotBuildingVisuals.TAG)
	end
	model.Parent = parent
	return model
end

-- TycoonCore calls this every second (through looks()): it builds the building of `stage` in the player's plot
-- folder, or does nothing when the folder already has it. A new stage replaces the old Model.
function PlotBuildingVisuals.sync(folder, center, art, building, stage)
	local shown = shownStage(building, stage)
	local old = folder:FindFirstChild("PlotBuilding")
	if old and old:GetAttribute("Stage") == shown then
		return old
	end
	local model = PlotBuildingVisuals.build(nil, center, art, building, shown)
	model.Parent = folder
	if old then
		old:Destroy()
	end
	return model
end

-- Checks ----------------------------------------------------------------------------------------------------

-- Problems in the data itself (empty list = fine)
function PlotBuildingVisuals.validate(building)
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
	local function spec(where, s)
		local name = type(s) == "table" and s.name
		if type(name) ~= "string" or name == "" then
			problem(where .. ": a part without a name")
			return
		end
		where = where .. "." .. name
		if not PlotBuildingVisuals.SHAPES[s.shape] then
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
		if not PlotBuildingVisuals.MATERIALS[s.material] then
			problem(where .. ": material not allowed: " .. tostring(s.material))
		elseif s.material == "Neon" and not isLightName(name) then
			problem(where .. ": Neon is only for lights and signs (name it Sign, Glow, Neon...)")
		end
		if s.transparency ~= nil and not (finite(s.transparency) and s.transparency >= 0 and s.transparency <= 1) then
			problem(where .. ": transparency must be 0-1")
		end
		if s.collide ~= nil or s.light ~= nil or s.particles ~= nil then
			problem(where .. ": a building part never collides, lights or emits")
		end
		if s.text then
			local t = s.text
			if type(t.value) ~= "string" or not building.Texts[t.value] then
				problem(where .. ": text must be one of OFFICE, HQ, BUILD YOUR STARTUP")
			elseif not colorOk(t.color) or not PlotBuildingVisuals.FONTS[t.font or "GothamBold"] then
				problem(where .. ": text needs a color and a known font")
			end
		end
	end
	local function list(where, specs)
		if type(specs) ~= "table" or #specs == 0 then
			problem(where .. ": missing or empty")
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
	if type(building.Stages) ~= "table" or #building.Stages == 0 then
		problem("Stages: missing")
		return problems
	end
	local E, I, F, Bg = building.Envelope, building.Inside, building.Fade, building.Budget
	if type(E) ~= "table" or type(I) ~= "table" or type(F) ~= "table" or type(Bg) ~= "table" then
		problem("Envelope, Inside, Fade and Budget are all needed")
		return problems
	end
	for _, group in ipairs({ { E, "inner", "thick", "roofBottom", "roofThick", "roofHalf", "doorHalf", "doorHeight", "clearHeight" },
		{ I, "floorBelow", "doorDepth", "margin" }, { F, "seconds", "levels" }, { Bg, "parts", "static", "gui" } }) do
		for i = 2, #group do
			if not (finite(group[1][group[i]]) and group[1][group[i]] > 0) then
				problem("number missing or not above 0: " .. tostring(group[i]))
			end
		end
	end
	if finite(F.levels) and F.levels % 1 ~= 0 then
		problem("Fade.levels must be a whole number")
	end
	for i, stage in ipairs(building.Stages) do
		local where = "Stage " .. i
		if type(stage.key) ~= "string" then
			problem(where .. ": needs the key of its funding stage")
		end
		list(where .. " fade", stage.fade)
		list(where .. " static", stage.static)
	end
	return problems
end

-- Problems in a built building Model (empty list = fine). center = the plot center it was built at.
-- opts (all optional): zones = PlotVisuals.zones(art.Layout) (no part may stand in a gameplay zone),
-- roomBoxes = { { name, box } } of the room built at the same center, as offsets from the floor top
-- (no part may go into a room part, except yard marks on the ground).
function PlotBuildingVisuals.check(model, center, art, building, opts)
	opts = opts or {}
	local problems = {}
	local function problem(text)
		table.insert(problems, text)
	end
	local ox, oy, oz = center.X, center.Y + art.Layout.floorTop, center.Z
	local E = building.Envelope
	local ground = E.ground
	local parts, lights, emitters, guis, statics = {}, 0, 0, 0, 0
	for _, d in ipairs(model:GetDescendants()) do
		if d:IsA("PointLight") or d:IsA("SpotLight") or d:IsA("SurfaceLight") then
			lights += 1
		elseif d:IsA("ParticleEmitter") then
			emitters += 1
		elseif d:IsA("SurfaceGui") then
			guis += 1
		elseif d:IsA("BasePart") then
			local b = boxOf(d.CFrame, d.Size)
			b = { b[1] - ox, b[2] - ox, b[3] - oy, b[4] - oy, b[5] - oz, b[6] - oz }
			local _, _, _, _, r01, r02, r10, _, r12, r20, r21 = d.CFrame:GetComponents()
			local straight = math.abs(r01) + math.abs(r02) + math.abs(r10) + math.abs(r12) + math.abs(r20) + math.abs(r21) < 1e-6
			local group = d.Parent and d.Parent.Name
			if group == "Static" then
				statics += 1
			end
			table.insert(parts, { part = d, name = d:GetFullName(), box = b, straight = straight, group = group })
		end
	end
	local budget = building.Budget
	if #parts > budget.parts then
		problem(string.format("%d parts (budget %d)", #parts, budget.parts))
	end
	if statics > budget.static then
		problem(string.format("%d ground pieces (budget %d)", statics, budget.static))
	end
	if guis > budget.gui then
		problem(string.format("%d SurfaceGuis (budget %d)", guis, budget.gui))
	end
	if lights > 0 then
		problem(lights .. " lights (a building has none)")
	end
	if emitters > 0 then
		problem(emitters .. " particle emitters (a building has none)")
	end
	local fade = model:FindFirstChild("Fade")
	if not fade or not model:FindFirstChild("Static") then
		problem("the Model needs a Fade and a Static group")
	end
	if not (fade and fade:FindFirstChild("Roof")) then
		problem("no part named Roof in Fade")
	end

	local clear = { -E.doorHalf, E.doorHalf, ground, E.clearHeight, E.inner - 2, 60 } -- the doorway and the way out of it
	for _, p in ipairs(parts) do
		local part, b = p.part, p.box
		if not part.Anchored then
			problem(p.name .. ": not anchored")
		end
		if part.CanCollide or part.CanTouch or part.CanQuery then
			problem(p.name .. ": CanCollide, CanTouch and CanQuery must all be off")
		end
		if part.CastShadow then
			problem(p.name .. ": casts a shadow")
		end
		if p.group ~= "Fade" and p.group ~= "Static" then
			problem(p.name .. ": not in Fade or Static")
		end
		if not PlotBuildingVisuals.MATERIALS[part.Material.Name] then
			problem(p.name .. ": material not allowed: " .. part.Material.Name)
		elseif part.Material.Name == "Neon" and not isLightName(part.Name) then
			problem(p.name .. ": Neon on something that isn't a light or a sign")
		end
		if b[1] < -PlotBuildingVisuals.MAX_REACH or b[2] > PlotBuildingVisuals.MAX_REACH or b[5] < -PlotBuildingVisuals.MAX_REACH
			or b[6] > PlotBuildingVisuals.MAX_REACH or b[4] > PlotBuildingVisuals.MAX_HEIGHT or b[3] < ground - TOUCH then
			problem(p.name .. ": outside the building's reach")
		end
		-- The door stays open: nothing hangs in the doorway or on the way out (flat ground marks are fine)
		local flat = b[4] - b[3] <= 0.2 and b[3] <= ground + 0.2
		if not flat and overlaps(b, clear, OVERLAP) then
			problem(p.name .. " is in the doorway")
		end
		for _, zone in ipairs(opts.zones or {}) do
			if overlaps(b, zone.box, OVERLAP) then
				problem(p.name .. " is inside " .. zone.kind .. " zone " .. zone.name)
			end
		end
		for _, room in ipairs(opts.roomBoxes or {}) do
			local rb = room.box
			local mark = rb[4] <= 0.05 -- a yard mark lying on the ground outside the plot
			if not mark and overlaps(b, rb, OVERLAP) then
				problem(p.name .. " goes into the room part " .. room.name)
			end
		end
	end

	-- Two faces on the same plane, looking the same way, over the same area, flicker (z-fighting). Never
	-- seen, so never counted: faces looking down (they rest on something), and faces that press against
	-- a wall's outer face (a window frame, a column) or the roof.
	local outer = E.inner + E.thick
	local function hidden(axis, side, plane)
		if axis == 1 then
			return side == "lo"
		elseif axis == 0 then
			return (side == "hi" and math.abs(plane + outer) < OVERLAP) or (side == "lo" and math.abs(plane - outer) < OVERLAP)
		end
		return (side == "lo" and math.abs(plane - outer) < OVERLAP) or (side == "hi" and math.abs(plane + outer) < OVERLAP)
	end
	for i = 1, #parts do
		for j = i + 1, #parts do
			local a, b = parts[i], parts[j]
			if a.straight and b.straight then
				for axis = 0, 2 do
					local lo, hi = axis * 2 + 1, axis * 2 + 2
					local o1, o2 = (axis + 1) % 3, (axis + 2) % 3
					local area1 = math.min(a.box[o1 * 2 + 2], b.box[o1 * 2 + 2]) - math.max(a.box[o1 * 2 + 1], b.box[o1 * 2 + 1])
					local area2 = math.min(a.box[o2 * 2 + 2], b.box[o2 * 2 + 2]) - math.max(a.box[o2 * 2 + 1], b.box[o2 * 2 + 1])
					if area1 > OVERLAP and area2 > OVERLAP then
						local same = nil
						if math.abs(a.box[hi] - b.box[hi]) < OVERLAP and not hidden(axis, "hi", a.box[hi]) then
							same = "top/outer"
						elseif math.abs(a.box[lo] - b.box[lo]) < OVERLAP and not hidden(axis, "lo", a.box[lo]) then
							same = "bottom/inner"
						end
						if same then
							problem(a.name .. " and " .. b.name .. " share a face (" .. same .. ", axis " .. axis .. ")")
						end
					end
				end
			end
		end
	end

	-- Floating parts: everything rests on the ground or on a chain of touching parts
	local supported, queue = {}, {}
	for i, p in ipairs(parts) do
		if p.box[3] <= ground + TOUCH then
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

return PlotBuildingVisuals
