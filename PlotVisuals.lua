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
-- TycoonCore keeps one plot table per player (in memory, never saved):
--   PlotVisuals.newPlot(folder, center, art, floor, stage)      -> plot, with the room of that stage
--   PlotVisuals.setStage(plot, stage, flash)                    -> swaps the room (quick flash), keeps the props
--   PlotVisuals.addProp(plot, upgrade, slot, popIn)             -> the prop Model (pops in), or nil
-- Checks (tools/daily_test.py and the Studio preview run them):
--   PlotVisuals.validate(art)             -> list of problems in the data (empty = fine)
--   PlotVisuals.check(room, center, art)  -> list of problems in a built room (zones, floating parts, walls, budget)
--
-- Offsets in the art are studs from the plot's floor-top center: the middle of the Floor's top
-- face (plot center + Layout.floorTop). +X is right, +Z is the front (the signs), -Z the back wall.

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
PlotVisuals.MAX_PARTS = 260 -- per stage room, upgrade props included
PlotVisuals.MAX_LIGHTS = 3 -- PointLights per plot
PlotVisuals.SIDE_WALL_MAX = 6 -- the sides and the front, where the camera looks in
PlotVisuals.BACK_WALL_MAX = 12 -- behind the incubators (z <= BACK_BAND)
PlotVisuals.BACK_BAND = -29
PlotVisuals.BACKDROP_Z = -43 -- the skyline ("Skyline" parts) stands behind this line only
PlotVisuals.BACKDROP_MAX = 30

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

-- A Model with one part per spec, all placed from the same base CFrame
function PlotVisuals.buildGroup(parent, name, base, specs)
	local model = Instance.new("Model")
	model.Name = name
	for _, spec in ipairs(specs) do
		PlotVisuals.buildPart(model, base, spec)
	end
	model.Parent = parent
	return model
end

local function floorOrigin(center, art)
	return CFrame.new(center.X, center.Y + art.Layout.floorTop, center.Z)
end

-- The room of one funding stage: its shell, its decor (with a desk for every hire spot) and an
-- empty UpgradeProps model for the props of the upgrades bought
function PlotVisuals.buildRoom(parent, center, art, stage)
	local look = art.Stages[stage]
	local origin = floorOrigin(center, art)
	local room = Instance.new("Model")
	room.Name = "PlotRoom"
	room:SetAttribute("Stage", stage)
	room:SetAttribute("StageKey", look.key)
	PlotVisuals.buildGroup(room, "Shell", origin, look.shell)
	local decor = PlotVisuals.buildGroup(room, "Decor", origin, look.decor)
	-- Every hire stands at one of these (EmployeeServer's EMPLOYEE_SPOTS, copied in PlotArt.Layout)
	for i, spot in ipairs(art.Layout.employeeSpots) do
		local desk = art.Layout.desks[i]
		local base = origin * CFrame.new(spot[1] + desk[1], 0, spot[2] + desk[2]) * CFrame.Angles(0, math.rad(desk[3]), 0)
		PlotVisuals.buildGroup(decor, "HireDesk" .. i, base, look.desk)
	end
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

function PlotVisuals.newPlot(folder, center, art, floor, stage)
	local plot = { folder = folder, center = center, art = art, floor = floor, room = nil, stage = nil }
	PlotVisuals.setStage(plot, stage, false)
	return plot
end

-- Builds the room of `stage` and swaps it in. The props already bought move into the new room.
-- A stage past the last room shows the last room. plot.stage is set first, so a failed build is
-- never tried again every second.
function PlotVisuals.setStage(plot, stage, flash)
	plot.stage = stage
	local art = plot.art
	local shown = math.clamp(stage, 1, #art.Stages)
	local old = plot.room
	local room = PlotVisuals.buildRoom(nil, plot.center, art, shown)
	local props = room:FindFirstChild("UpgradeProps")
	local oldProps = old and old:FindFirstChild("UpgradeProps")
	if oldProps then
		for _, prop in ipairs(oldProps:GetChildren()) do
			prop.Parent = props
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
	local model = PlotVisuals.buildProp(props, plot.center, plot.art, upgrade, slot)
	if model and popIn then
		task.spawn(PlotVisuals.popIn, model)
	end
	return model
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
	local part = PlotVisuals.buildPart(plot.folder, floorOrigin(plot.center, plot.art), fx.part)
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
	local function spec(where, s)
		local name = type(s) == "table" and s.name
		if type(name) ~= "string" or name == "" then
			problem(where .. ": a part without a name")
			return
		end
		where = where .. "." .. name
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
		if s.light then
			local l = s.light
			if not (colorOk(l.color) and finite(l.brightness) and l.brightness > 0 and finite(l.range) and l.range > 0 and l.range <= 60) then
				problem(where .. ": light needs color, brightness > 0 and range 0-60")
			end
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
function PlotVisuals.zones(layout)
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
		add("hire", "Hire" .. i, spot[1] - r.hireHalf, spot[1] + r.hireHalf, spot[2] - r.hireHalf, spot[2] + r.hireHalf, r.hireHeight)
		add("desk", "HireDesk" .. i, spot[1] - r.deskHalfX, spot[1] + r.deskHalfX, spot[2] + r.deskFrom, spot[2] + r.deskTo, r.deskHeight)
	end
	for _, slot in ipairs(layout.itemSlots) do
		add("slot", slot.name, slot.x - r.slotHalfX, slot.x + r.slotHalfX, slot.z - r.slotBack, slot.z + r.slotFront, r.slotHeight, slot.name)
	end
	for i, a in ipairs(aisles) do
		add("aisle", i == 1 and "DoorAisle" or ("RowAisle" .. (i - 1)), a[1], a[2], a[3], a[4], r.height)
	end
	return zones
end

-- Problems in a built room (props inside it included): parts in a reserved zone, props outside
-- their slot, floating parts, walls too high where the camera looks in, flags, the part and
-- light budgets. center = the plot center the room was built at.
function PlotVisuals.check(room, center, art)
	local problems = {}
	local function problem(text)
		table.insert(problems, text)
	end
	local layout = art.Layout
	local ox, oy, oz = center.X, center.Y + layout.floorTop, center.Z
	local half = layout.floorSize[1] / 2
	local ground = -layout.floorSize[2] -- the Floor's bottom: where the Baseplate's top is
	local parts, lights = {}, 0
	for _, d in ipairs(room:GetDescendants()) do
		if d:IsA("PointLight") or d:IsA("SpotLight") or d:IsA("SurfaceLight") then
			lights += 1
		elseif d:IsA("BasePart") then
			local b = boxOf(d.CFrame, d.Size)
			b = { b[1] - ox, b[2] - ox, b[3] - oy, b[4] - oy, b[5] - oz, b[6] - oz }
			local upgrade, deskName, node = nil, nil, d.Parent
			while node and node ~= room do
				upgrade = upgrade or node:GetAttribute("Upgrade")
				if not deskName and string.find(node.Name, "HireDesk", 1, true) == 1 then
					deskName = node.Name
				end
				node = node.Parent
			end
			local flat = b[4] - b[3] <= PlotVisuals.FLAT and (math.abs(b[3]) <= TOUCH or math.abs(b[3] - ground) <= TOUCH)
			table.insert(parts, { part = d, name = d:GetFullName(), box = b, upgrade = upgrade, desk = deskName, flat = flat })
		end
	end
	if #parts > PlotVisuals.MAX_PARTS then
		problem(string.format("%d parts (budget %d)", #parts, PlotVisuals.MAX_PARTS))
	end
	if lights > PlotVisuals.MAX_LIGHTS then
		problem(string.format("%d lights (budget %d)", lights, PlotVisuals.MAX_LIGHTS))
	end

	local zones = PlotVisuals.zones(layout)
	local slotOf, deskOf = {}, {}
	for _, zone in ipairs(zones) do
		if zone.kind == "slot" then
			slotOf[zone.owner] = zone
		elseif zone.kind == "desk" then
			deskOf[zone.name] = zone.box
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
		if part.CanCollide then
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
				and not (zone.kind == "slot" and p.upgrade == zone.owner) and not (zone.kind == "desk" and p.desk == zone.name) then
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
		if p.desk then
			local z = deskOf[p.desk]
			if not z or b[1] < z[1] - OVERLAP or b[2] > z[2] + OVERLAP or b[5] < z[5] - OVERLAP or b[6] > z[6] + OVERLAP or b[4] > z[4] + OVERLAP then
				problem(p.name .. ": a hire desk must stay inside its own desk zone")
			end
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
