-- PlotBuildingVisuals: builds the building around a garage's room and checks it (branch lobby-all).
-- Put this ModuleScript in ServerScriptService, next to PlotBuilding (the data), ModelSlots (models for the slots) and
-- PlotArt (the rooms). TycoonCore calls it through its looks() helper: a failing building never stops the game.
-- docs/BUILDING_STAGES_PROPOSAL.md is the design, docs/MODEL_ASSETS_PLAN.md the model slots.
--
-- Only looks: nothing here is saved, sent through a remote or read back by the game. Every part is anchored and never
-- touched (CanTouch off). Only the colliders of solid slots (outer walls, corner posts, lintel, roof, the added floor)
-- are solid; everything else has CanCollide, CanTouch and CanQuery off. The client script BuildingClient fades the
-- Shell when the local player is inside; the server never learns who is inside.
--
--   PlotBuildingVisuals.build(parent, frame, art, data, index, opts)  -> Model "PlotBuilding": Shell, Interior, Outside
--   PlotBuildingVisuals.sync(parent, frame, art, data, index, opts)   -> the Model of that building (does nothing when
--                                                                        `parent` already shows it)
--   PlotBuildingVisuals.setSign(model, text)                          -> writes the garage sign's words
--   PlotBuildingVisuals.bounds(building)                              -> the inside box in the garage frame (pure)
--   PlotBuildingVisuals.slotReport(model)                             -> { { id, slot, source, why } } (the Debug button)
--   PlotBuildingVisuals.solidBoxes(model), stuckIn(boxes, point, pad), landing() -> the "nobody is trapped" maths
--   PlotBuildingVisuals.validate(data)                                -> problems in the data (empty = fine)
--   PlotBuildingVisuals.check(model, frame, art, data, building, opts) -> problems in a built Model (empty = fine)
-- frame = the garage's frame (TycoonCore plotFrame: a CFrame, or a Vector3 for a garage facing +Z); art = PlotArt
-- (for the floor top); data = PlotBuilding; opts = { models = the BuildingModels folder or nil, slots = ModelSlots
-- or nil, signText = the garage sign's words, persistent = true to keep the Shell streamed in }.
-- Pure maths, the same text as BuildingClient (tools/building_test.py compares them): isInside, fadeStep, quantize,
-- transparencyAt.

local PlotBuildingVisuals = {}

PlotBuildingVisuals.TAG = "PlotBuilding" -- CollectionService tag on the Model: the client finds buildings by it
PlotBuildingVisuals.GROUPS = { Shell = true, Interior = true, Outside = true }
PlotBuildingVisuals.MATERIALS = {
	Concrete = true, CorrodedMetal = true, Metal = true, DiamondPlate = true, Wood = true, WoodPlanks = true,
	Brick = true, Fabric = true, Plastic = true, SmoothPlastic = true, Glass = true, Neon = true,
}
PlotBuildingVisuals.SHAPES = { Block = true, Cylinder = true, Ball = true }
PlotBuildingVisuals.FONTS = { GothamBold = true, PermanentMarker = true, IndieFlower = true, LuckiestGuy = true, FredokaOne = true }
PlotBuildingVisuals.LIGHT_WORDS = { "Bulb", "Lamp", "Light", "Screen", "LED", "Sign", "Logo", "Neon", "Glow" }
PlotBuildingVisuals.FRONT_SLACK = 0.3 -- a Parts-version part may stick out of its box's front by this (window glass, tape)
PlotBuildingVisuals.FLOOR_HALF = 30 -- the Floor is 60 x 60: no solid building part over it
PlotBuildingVisuals.LANDING = { 0, 3, 37 } -- where `unstick` puts a player: on the apron's far end, outside the door

local OVERLAP = 0.01 -- parts must go this far into something to count as inside it
local TOUCH = 0.06 -- parts closer than this touch (floating check)

-- The pure maths ------------------------------------------------------------------------------------------------
-- No services, no Instances: they run the same in the tests and in BuildingClient, which carries a copy of this
-- block (tools/building_test.py fails if the two texts differ). Positions are in the garage's frame.

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
-- (studs in the garage's frame; maxY is the ground floor's ceiling; the door is on the +Z side). Edges count as
-- inside. The doorway and the apron in front of it count too, so the front wall starts to fade as you walk up to the
-- door. Above the ceiling is outside. wasInside makes the box `margin` bigger (no flicker on a wall line).
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

-- Helpers -------------------------------------------------------------------------------------------------------

local function rgb(c)
	return Color3.fromRGB(c[1], c[2], c[3])
end

local function turn(r)
	if not r then
		return CFrame.new()
	end
	return CFrame.fromEulerAnglesYXZ(math.rad(r[1]), math.rad(r[2]), math.rad(r[3]))
end

local function yaw(degrees)
	return CFrame.fromEulerAnglesYXZ(0, math.rad(degrees or 0), 0)
end

-- The box around a part in some frame: { minX, maxX, minY, maxY, minZ, maxZ }
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

-- The floor-top center of a garage, turned like it (frame: a CFrame, or a Vector3 for a garage facing +Z)
function PlotBuildingVisuals.origin(frame, art)
	if typeof(frame) == "CFrame" then
		return frame * CFrame.new(0, art.Layout.floorTop, 0)
	end
	return CFrame.new(frame.X, frame.Y + art.Layout.floorTop, frame.Z)
end

-- Where a slot's box stands: its bottom-center, its front (+Z) turned by `turn`
local function slotFrame(origin, placement)
	local at = placement.at
	return origin * CFrame.new(at[1], at[2], at[3]) * yaw(placement.turn)
end
PlotBuildingVisuals.slotFrame = slotFrame

-- A building index past the last shows the last one; below 1, or not a number, shows the first
local function shownIndex(data, index)
	local last = #data.Buildings
	if type(index) ~= "number" or index ~= index then
		return 1
	end
	return math.clamp(math.floor(index), 1, last)
end
PlotBuildingVisuals.shownIndex = shownIndex

-- The inside box of a building, in the garage's frame (the numbers the client reads as attributes)
function PlotBuildingVisuals.bounds(data, building)
	local t = data.THICK
	return {
		minX = -building.width / 2 + t, maxX = building.width / 2 - t,
		minZ = building.back + t, maxZ = data.FRONT - t,
		minY = -data.Inside.floorBelow, maxY = building.ceiling,
		doorMinX = -building.door / 2, doorMaxX = building.door / 2,
		doorDepth = t + data.Inside.apron, margin = data.Inside.margin,
	}
end

-- The attribute names the client reads, for the bounds table's fields
PlotBuildingVisuals.ATTRIBUTES = {
	minX = "MinX", maxX = "MaxX", minY = "MinY", maxY = "MaxY", minZ = "MinZ", maxZ = "MaxZ",
	doorMinX = "DoorMinX", doorMaxX = "DoorMaxX", doorDepth = "DoorDepth", margin = "Margin",
}

-- Building --------------------------------------------------------------------------------------------------------

-- One part of a Parts version. solid: a collider (CanCollide and CanQuery on). Never touched, never a shadow.
local function buildPart(parent, base, spec, solid, invisible)
	local size = Vector3.new(spec.size[1], spec.size[2], spec.size[3])
	local part = Instance.new("Part")
	part.Name = spec.name
	part.Shape = Enum.PartType[spec.shape or "Block"]
	part.Size = size
	part.CFrame = base * CFrame.new(spec.offset[1], spec.offset[2], spec.offset[3]) * turn(spec.rot)
	part.Color = rgb(spec.color)
	part.Material = Enum.Material[spec.material]
	part.Transparency = invisible and 1 or (spec.transparency or 0)
	part.Anchored = true
	part.CanCollide = solid
	part.CanQuery = solid -- Roblox needs CanQuery on for anything solid
	part.CanTouch = false
	part.CastShadow = false
	part.TopSurface = Enum.SurfaceType.Smooth
	part.BottomSurface = Enum.SurfaceType.Smooth
	if solid then
		part:SetAttribute("Collider", true)
	end
	part.Parent = parent
	return part
end

-- The words of a slot on a thin, invisible plate (a model or the Parts version may be under it)
local function writeText(parent, slotCF, placement, value)
	local text, box = placement.text, placement.box
	local w, h = text.w or box[1], text.h or box[2]
	local y, z = text.y or box[2] / 2, (text.z or box[3] / 2) + 0.03
	local plate = Instance.new("Part")
	plate.Name = "TextPlate"
	plate.Size = Vector3.new(w, h, 0.05)
	plate.CFrame = slotCF * CFrame.new(text.x or 0, y, z)
	plate.Transparency = 1
	plate.Anchored = true
	plate.CanCollide = false
	plate.CanQuery = false
	plate.CanTouch = false
	plate.CastShadow = false
	local gui = Instance.new("SurfaceGui")
	gui.Name = "Text"
	gui.Face = Enum.NormalId.Back -- Back = the plate's +Z side: the slot's front
	gui.SizingMode = Enum.SurfaceGuiSizingMode.PixelsPerStud
	gui.PixelsPerStud = 40
	gui.LightInfluence = text.glow and 0 or 1
	gui.Parent = plate
	local label = Instance.new("TextLabel")
	label.Name = "Label"
	label.Size = UDim2.fromScale(1, 1)
	label.BackgroundTransparency = 1
	label.TextScaled = true
	label.Font = Enum.Font[text.font or "GothamBold"]
	label.TextColor3 = rgb(text.color)
	label.Text = value or ""
	label.Parent = gui
	plate.Parent = parent
	return plate
end

-- One slot placement: the owner's model when there is a good one (and the collider of a solid slot, invisible), else
-- the Parts version. tally = { triangles, parts } so far for this building (a model must fit the building's budget).
local function buildSlot(groupModel, origin, data, building, placement, opts, tally)
	local info = data.Slots[placement.slot] or {}
	local slotCF = slotFrame(origin, placement)
	local model = Instance.new("Model")
	model.Name = placement.id
	model:SetAttribute("Slot", placement.slot)
	local source, why, triangles = "parts", "no model", 0
	local placed = nil
	local slots = opts.slots
	if slots and opts.models then
		local template = slots.find(opts.models, building.key, placement.slot)
		if template then
			local cap = data.Caps[info.kind]
			local copy, got, deleted = slots.fit(template, placement.box, info.fit, cap, slotCF)
			if not copy then
				why = got
			else
				local colliders = 0
				for _, spec in ipairs(placement.parts) do
					if spec.collide then
						colliders += 1
					end
				end
				local count = 0
				for _, d in ipairs(copy:GetDescendants()) do
					if d:IsA("BasePart") then
						count += 1
					end
				end
				if tally.triangles + got > building.budget.triangles or tally.parts + count + colliders > building.budget.parts then
					copy:Destroy()
					why = "over the building's budget"
				else
					placed, triangles = copy, got
					source = "model"
					why = (deleted and #deleted > 0) and ("deleted from the copy: " .. table.concat(deleted, ", ")) or ""
				end
			end
		end
	end
	if placed then
		placed.Name = "Model"
		placed.Parent = model
		for _, spec in ipairs(placement.parts) do
			if spec.collide then
				buildPart(model, slotCF, spec, true, true)
			end
		end
	else
		for _, spec in ipairs(placement.parts) do
			buildPart(model, slotCF, spec, spec.collide == true, false)
		end
	end
	if placement.text then
		local value = placement.text.value
		if placement.text.sign then
			value = opts.signText or ""
			model:SetAttribute("GarageSign", true)
		end
		writeText(model, slotCF, placement, value)
	end
	model:SetAttribute("Source", source)
	model:SetAttribute("Why", why)
	model:SetAttribute("Triangles", triangles)
	tally.triangles += triangles
	for _, d in ipairs(model:GetDescendants()) do
		if d:IsA("BasePart") then
			tally.parts += 1
		end
	end
	model.Parent = groupModel
	return model
end

-- The Model "PlotBuilding" of one building: Shell (fades), Interior and Outside (stay). Its attributes are everything
-- BuildingClient needs (the garage's frame, the inside box, the fade) and what the server reads back (the index).
function PlotBuildingVisuals.build(parent, frame, art, data, index, opts)
	opts = opts or {}
	local shown = shownIndex(data, index)
	local building = data.Buildings[shown]
	local origin = PlotBuildingVisuals.origin(frame, art)
	local model = Instance.new("Model")
	model.Name = "PlotBuilding"
	model:SetAttribute("Building", shown)
	model:SetAttribute("Key", building.key)
	model:SetAttribute("Frame", origin)
	local bounds = PlotBuildingVisuals.bounds(data, building)
	for field, attribute in pairs(PlotBuildingVisuals.ATTRIBUTES) do
		model:SetAttribute(attribute, bounds[field])
	end
	model:SetAttribute("FadeSeconds", data.Fade.seconds)
	model:SetAttribute("FadeLevels", data.Fade.levels)
	model:SetAttribute("SignText", opts.signText or "")
	local groups = {}
	for _, name in ipairs({ "Shell", "Interior", "Outside" }) do
		local g = Instance.new("Model")
		g.Name = name
		g.Parent = model
		groups[name] = g
	end
	if opts.persistent then
		pcall(function()
			groups.Shell.ModelStreamingMode = Enum.ModelStreamingMode.Persistent
		end)
	end
	local tally = { triangles = 0, parts = 0 }
	for _, placement in ipairs(building.slots) do
		buildSlot(groups[placement.group], origin, data, building, placement, opts, tally)
	end
	model:SetAttribute("Triangles", tally.triangles)
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

-- The building of `index` in `parent` (a garage), or nothing to do when it already shows it. A new building replaces
-- the old Model (built first, so there is never a moment without one).
function PlotBuildingVisuals.sync(parent, frame, art, data, index, opts)
	local shown = shownIndex(data, index)
	local old = parent:FindFirstChild("PlotBuilding")
	if old and old:GetAttribute("Building") == shown then
		return old, false
	end
	opts = opts or {}
	if old and opts.signText == nil then
		opts.signText = old:GetAttribute("SignText")
	end
	local model = PlotBuildingVisuals.build(nil, frame, art, data, shown, opts)
	model.Parent = parent
	if old then
		old:Destroy()
	end
	return model, true
end

-- The garage sign's words (the owner's name, FREE, ...): kept on the Model so a new building shows them too
function PlotBuildingVisuals.setSign(model, text)
	model:SetAttribute("SignText", text)
	for _, d in ipairs(model:GetDescendants()) do
		if d:IsA("Model") and d:GetAttribute("GarageSign") then
			local plate = d:FindFirstChild("TextPlate")
			local gui = plate and plate:FindFirstChild("Text")
			local label = gui and gui:FindFirstChild("Label")
			if label then
				label.Text = text
			end
		end
	end
end

-- Which slots use a model and which the Parts version (and why): the Studio Debug button shows this
function PlotBuildingVisuals.slotReport(model)
	local out = {}
	for _, group in ipairs({ "Shell", "Interior", "Outside" }) do
		local g = model:FindFirstChild(group)
		if g then
			for _, slot in ipairs(g:GetChildren()) do
				table.insert(out, { id = slot.Name, slot = slot:GetAttribute("Slot"), source = slot:GetAttribute("Source"), why = slot:GetAttribute("Why") })
			end
		end
	end
	return out
end

-- Nobody is trapped ----------------------------------------------------------------------------------------------

-- The solid parts of a built building, as boxes in the garage's frame
function PlotBuildingVisuals.solidBoxes(model)
	local origin = model:GetAttribute("Frame")
	local boxes = {}
	for _, d in ipairs(model:GetDescendants()) do
		if d:IsA("BasePart") and d.CanCollide then
			table.insert(boxes, boxOf(origin:ToObjectSpace(d.CFrame), d.Size))
		end
	end
	return boxes
end

-- Is a point (garage frame) inside a solid box grown by pad on every side (a character is about 2 studs wide)?
function PlotBuildingVisuals.stuckIn(boxes, point, pad)
	for _, b in ipairs(boxes) do
		if point.X > b[1] - pad and point.X < b[2] + pad and point.Y > b[3] - pad and point.Y < b[4] + pad
			and point.Z > b[5] - pad and point.Z < b[6] + pad then
			return true
		end
	end
	return false
end

-- Where a stuck player goes, in the garage's frame: outside the door, looking in
function PlotBuildingVisuals.landing()
	local l = PlotBuildingVisuals.LANDING
	return Vector3.new(l[1], l[2], l[3]), Vector3.new(l[1], l[2], 0)
end

-- Checks --------------------------------------------------------------------------------------------------------

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

-- On the 4-stud grid, or a thin side (walls 1, corner posts 2, flat pieces): docs/MODEL_ASSETS_PLAN.md section 1.1
local function onGrid(n)
	return n <= 2 + 1e-9 or math.abs(n / 4 - math.floor(n / 4 + 0.5)) < 1e-9
end
PlotBuildingVisuals.onGrid = onGrid

-- Problems in the data itself (empty list = fine)
function PlotBuildingVisuals.validate(data)
	local problems = {}
	local function problem(text)
		table.insert(problems, text)
	end
	if type(data.Buildings) ~= "table" or #data.Buildings == 0 then
		problem("Buildings: missing")
		return problems
	end
	for _, field in ipairs({ "FRONT", "THICK", "CORNER", "GROUND", "DOOR_TOP" }) do
		if not finite(data[field]) then
			problem("number missing: " .. field)
		end
	end
	if type(data.Inside) ~= "table" or type(data.Fade) ~= "table" or type(data.Lane) ~= "table" or type(data.Lot) ~= "table"
		or type(data.Caps) ~= "table" or type(data.Slots) ~= "table" or type(data.Texts) ~= "table" then
		problem("Inside, Fade, Lane, Lot, Caps, Slots and Texts are all needed")
		return problems
	end
	for name, info in pairs(data.Slots) do
		if not finite(data.Caps[info.kind]) then
			problem("slot " .. tostring(name) .. ": unknown kind " .. tostring(info.kind))
		end
		if info.fit ~= "uniform" and info.fit ~= "stretch" then
			problem("slot " .. tostring(name) .. ": fit is uniform or stretch")
		end
	end
	local keys = {}
	local before = nil
	for i, b in ipairs(data.Buildings) do
		local where = "Building " .. i
		if type(b.key) ~= "string" or keys[b.key] then
			problem(where .. ": needs a key of its own")
		end
		keys[b.key or ""] = true
		for _, field in ipairs({ "width", "back", "wallHeight", "door", "ceiling" }) do
			if not finite(b[field]) then
				problem(where .. ": number missing: " .. field)
			end
		end
		if finite(b.width) and (b.width % 4 ~= 0) then
			problem(where .. ": width must be a multiple of 4")
		end
		if finite(b.back) and ((data.FRONT - b.back) % 4 ~= 0) then
			problem(where .. ": depth must be a multiple of 4")
		end
		if finite(b.door) and (b.door % 4 ~= 0 or b.door / 2 < data.Lane.half) then
			problem(where .. ": the door opening is a multiple of 4, wider than the lane")
		end
		if type(b.budget) ~= "table" or not (finite(b.budget.parts) and finite(b.budget.triangles) and finite(b.budget.gui)) then
			problem(where .. ": budget needs parts, triangles and gui")
		end
		if before and finite(b.width) and finite(b.back) and (b.width < before.width or b.back > before.back) then
			problem(where .. ": must contain building " .. (i - 1) .. " (D-A: never narrower or shallower)")
		end
		before = b
		local ids = {}
		for j, s in ipairs(b.slots or {}) do
			local at = where .. " slot " .. tostring(s.id or j)
			if type(s.id) ~= "string" or ids[s.id] then
				problem(at .. ": needs an id of its own")
			end
			ids[s.id or ""] = true
			local info = data.Slots[s.slot]
			if not info then
				problem(at .. ": unknown slot " .. tostring(s.slot))
			end
			if not PlotBuildingVisuals.GROUPS[s.group] then
				problem(at .. ": group is Shell, Interior or Outside")
			end
			if not triple(s.at) then
				problem(at .. ": at must be 3 numbers")
			end
			if s.turn ~= 0 and s.turn ~= 90 and s.turn ~= 180 and s.turn ~= 270 then
				problem(at .. ": turn is 0, 90, 180 or 270")
			end
			if not triple(s.box, true) then
				problem(at .. ": box must be 3 numbers above 0")
			elseif info and info.fit == "uniform" and not (onGrid(s.box[1]) and onGrid(s.box[2]) and onGrid(s.box[3])) then
				problem(at .. ": a uniform slot's box is on the 4-stud grid (or 2 studs at most on a thin side)")
			end
			local names, colliders = {}, 0
			if type(s.parts) ~= "table" or #s.parts == 0 then
				problem(at .. ": no Parts version")
			else
				for _, spec in ipairs(s.parts) do
					local pw = at .. " part " .. tostring(spec.name)
					if type(spec.name) ~= "string" or spec.name == "" or names[spec.name] then
						problem(pw .. ": needs a name of its own")
					end
					names[spec.name or ""] = true
					if not PlotBuildingVisuals.SHAPES[spec.shape] then
						problem(pw .. ": unknown shape")
					end
					if not triple(spec.size, true) or not triple(spec.offset) then
						problem(pw .. ": size and offset must be 3 numbers")
					elseif spec.shape == "Ball" and not (spec.size[1] == spec.size[2] and spec.size[2] == spec.size[3]) then
						problem(pw .. ": a Ball needs 3 equal sides")
					elseif spec.shape == "Cylinder" and spec.size[2] ~= spec.size[3] then
						problem(pw .. ": a Cylinder needs equal Y and Z")
					end
					if spec.rot ~= nil and not triple(spec.rot) then
						problem(pw .. ": rot must be 3 numbers")
					end
					if not colorOk(spec.color) then
						problem(pw .. ": color must be 3 whole numbers 0-255")
					end
					if not PlotBuildingVisuals.MATERIALS[spec.material] then
						problem(pw .. ": material not allowed: " .. tostring(spec.material))
					elseif spec.material == "Neon" and not isLightName(spec.name or "") then
						problem(pw .. ": Neon is only for lights and signs")
					end
					if spec.transparency ~= nil and not (finite(spec.transparency) and spec.transparency >= 0 and spec.transparency <= 1) then
						problem(pw .. ": transparency must be 0-1")
					end
					if spec.light ~= nil or spec.particles ~= nil or spec.text ~= nil then
						problem(pw .. ": a building part has no light, particles or text of its own")
					end
					if spec.collide ~= nil and spec.collide ~= true then
						problem(pw .. ": collide is true or left out")
					end
					if spec.collide then
						colliders += 1
						if triple(s.box, true) and triple(spec.size, true) and triple(spec.offset)
							and (math.abs(spec.size[1] - s.box[1]) > 1e-6 or math.abs(spec.size[3] - s.box[3]) > 1e-6
								or math.abs(spec.offset[1]) > 1e-6 or math.abs(spec.offset[3]) > 1e-6
								or math.abs(spec.offset[2] - spec.size[2] / 2) > 1e-6 or spec.size[2] > s.box[2] + 1e-6 or spec.rot ~= nil) then
							problem(pw .. ": a collider is as wide and deep as its box, from the box's bottom")
						end
					end
					-- every piece of the Parts version stays inside its box (the front may stick out a little)
					if triple(s.box, true) and triple(spec.size, true) and triple(spec.offset) then
						local pb = boxOf(CFrame.new(spec.offset[1], spec.offset[2], spec.offset[3]) * turn(spec.rot), Vector3.new(spec.size[1], spec.size[2], spec.size[3]))
						local w, h, d = s.box[1], s.box[2], s.box[3]
						if pb[1] < -w / 2 - OVERLAP or pb[2] > w / 2 + OVERLAP or pb[3] < -OVERLAP or pb[4] > h + OVERLAP
							or pb[5] < -d / 2 - OVERLAP or pb[6] > d / 2 + PlotBuildingVisuals.FRONT_SLACK + OVERLAP then
							problem(pw .. ": sticks out of its slot's box")
						end
					end
				end
			end
			if info and info.solid and colliders ~= 1 then
				problem(at .. ": a solid slot has exactly one collider")
			elseif info and not info.solid and colliders ~= 0 then
				problem(at .. ": only solid slots have a collider")
			end
			if s.text ~= nil then
				local t = s.text
				if not (t.sign == true or (type(t.value) == "string" and data.Texts[t.value])) then
					problem(at .. ": text must be one of OFFICE, HQ, BUILD YOUR STARTUP (or the garage sign)")
				elseif not colorOk(t.color) or not PlotBuildingVisuals.FONTS[t.font or "GothamBold"] then
					problem(at .. ": text needs a color and a known font")
				end
			end
		end
	end
	return problems
end

-- Problems in a built building (empty list = fine). opts (all optional): zones = PlotVisuals.zones(art.Layout) (no
-- part in a gameplay zone), roomBoxes = { { name, box } } of the room built in the same garage, in the garage frame
-- with the floor top at y 0 (no part inside a room part, except the room's flat marks on the ground), signText (the
-- garage sign's words the server set), skipFaces = true to skip the z-fighting check (models are not boxes).
function PlotBuildingVisuals.check(model, frame, art, data, building, opts)
	opts = opts or {}
	local problems = {}
	local function problem(text)
		table.insert(problems, text)
	end
	local origin = PlotBuildingVisuals.origin(frame, art)
	local parts, lights, emitters, guis, triangles = {}, 0, 0, 0, 0
	for _, d in ipairs(model:GetDescendants()) do
		if d:IsA("Light") then
			lights += 1
		elseif d:IsA("ParticleEmitter") or d:IsA("Fire") or d:IsA("Smoke") or d:IsA("Sparkles") then
			emitters += 1
		elseif d:IsA("SurfaceGui") or d:IsA("BillboardGui") then
			guis += 1
		elseif d:IsA("BaseScript") or d:IsA("ModuleScript") or d:IsA("Sound") then
			problem(d:GetFullName() .. ": a building never has a script or a sound")
		elseif d:IsA("TextLabel") then
			if not (data.Texts[d.Text] or d.Text == (opts.signText or "")) then
				problem(d:GetFullName() .. ": text not allowed: " .. tostring(d.Text))
			end
		elseif d:IsA("BasePart") then
			local b = boxOf(origin:ToObjectSpace(d.CFrame), d.Size)
			local slot, group = nil, nil
			local node = d.Parent
			while node and node ~= model do
				if node:GetAttribute("Slot") ~= nil then
					slot = node
				end
				if node.Parent == model then
					group = node.Name
				end
				node = node.Parent
			end
			table.insert(parts, { part = d, name = d:GetFullName(), box = b, slot = slot, group = group,
				fromModel = slot ~= nil and slot:GetAttribute("Source") == "model" and d:GetAttribute("Collider") ~= true })
		end
	end
	for _, slotModel in ipairs(model:GetDescendants()) do
		if slotModel:IsA("Model") and slotModel:GetAttribute("Slot") ~= nil then
			triangles += slotModel:GetAttribute("Triangles") or 0
		end
	end
	local budget = building.budget
	if #parts > budget.parts then
		problem(string.format("budget: %d parts (budget %d)", #parts, budget.parts))
	end
	if triangles > budget.triangles then
		problem(string.format("budget: %d triangles (budget %d)", triangles, budget.triangles))
	end
	if guis > budget.gui then
		problem(string.format("budget: %d SurfaceGuis (budget %d)", guis, budget.gui))
	end
	if lights > 0 then
		problem("budget: " .. lights .. " lights (a building has none)")
	end
	if emitters > 0 then
		problem("budget: " .. emitters .. " particle emitters (a building has none)")
	end
	for name in pairs(PlotBuildingVisuals.GROUPS) do
		if not model:FindFirstChild(name) then
			problem("groups: the Model needs its " .. name)
		end
	end

	local Lane, Lot, F = data.Lane, data.Lot, PlotBuildingVisuals.FLOOR_HALF
	local lane = { -Lane.half, Lane.half, TOUCH, Lane.height, Lane.from, Lane.to }
	local opening = { -building.door / 2, building.door / 2, data.GROUND + TOUCH, data.DOOR_TOP - TOUCH, data.FRONT - data.THICK, data.FRONT }
	local overFloor = { -F, F, data.GROUND, 10000, -F, F }
	local claim = data.ClaimSpot
	local claimBox = { claim[1], claim[2], -10, 10000, claim[3], claim[4] }
	for _, p in ipairs(parts) do
		local part, b = p.part, p.box
		-- Flags: anchored, never touched, no shadow; solid only for colliders, and a collider is solid
		if not part.Anchored then
			problem(p.name .. ": flags: not anchored")
		end
		if part.CanTouch then
			problem(p.name .. ": flags: CanTouch is on")
		end
		if part.CastShadow then
			problem(p.name .. ": flags: casts a shadow")
		end
		local collider = part:GetAttribute("Collider") == true
		if part.CanCollide ~= collider or part.CanQuery ~= collider then
			problem(p.name .. ": flags: only colliders are solid (CanCollide and CanQuery), and every collider is")
		end
		if collider then
			local info = p.slot and data.Slots[p.slot:GetAttribute("Slot")]
			if not (info and info.solid) then
				problem(p.name .. ": flags: a collider outside a solid slot")
			end
			if overlaps(b, overFloor, OVERLAP) then
				problem(p.name .. ": solid: a solid part over the Floor (it could trap a player at a stage change)")
			end
		end
		if not p.slot or not p.group or not PlotBuildingVisuals.GROUPS[p.group] then
			problem(p.name .. ": groups: not in a slot of Shell, Interior or Outside")
		end
		if not p.fromModel then
			if not PlotBuildingVisuals.MATERIALS[part.Material.Name] then
				problem(p.name .. ": material not allowed: " .. part.Material.Name)
			elseif part.Material.Name == "Neon" and not isLightName(part.Name) then
				problem(p.name .. ": Neon on something that isn't a light or a sign")
			end
		end
		-- The lane and the door opening stay clear of everything
		if overlaps(b, lane, OVERLAP) then
			problem(p.name .. ": lane: inside the doorway lane")
		end
		if overlaps(b, opening, OVERLAP) then
			problem(p.name .. ": lane: inside the door opening")
		end
		-- The lot (Outside pieces: the band in front of the facade, never on the claim post's spot)
		if p.group == "Outside" then
			if b[1] < -Lot.half or b[2] > Lot.half or b[5] < data.FRONT - OVERLAP or b[6] > Lot.outsideTo or b[4] > Lot.top then
				problem(p.name .. ": lot: outside pieces stay in the band in front of the facade")
			end
			if overlaps(b, claimBox, OVERLAP) then
				problem(p.name .. ": lot: on the claim post's spot")
			end
		elseif b[1] < -Lot.half or b[2] > Lot.half or b[5] < Lot.back or b[6] > Lot.front or b[4] > Lot.top or b[3] < data.GROUND - TOUCH then
			problem(p.name .. ": lot: outside the garage's lot")
		end
		for _, zone in ipairs(opts.zones or {}) do
			if overlaps(b, zone.box, OVERLAP) then
				problem(p.name .. ": zones: inside " .. zone.kind .. " zone " .. zone.name)
			end
		end
		for _, room in ipairs(opts.roomBoxes or {}) do
			local rb = room.box
			local mark = rb[4] - rb[3] <= 0.2 and rb[3] <= data.GROUND + TOUCH -- a flat mark on the ground (dirt, a stain)
			if not mark and overlaps(b, rb, OVERLAP) then
				problem(p.name .. ": room: goes into the room part " .. room.name)
			end
		end
	end

	-- Closed: every point of the four wall lines, from the ground to the ceiling, is inside a solid part, except the
	-- door opening (sampled every half stud along, every stud up)
	local solid = {}
	for _, p in ipairs(parts) do
		if p.part.CanCollide then
			table.insert(solid, p.box)
		end
	end
	local function inSolid(x, y, z)
		for _, b in ipairs(solid) do
			if x >= b[1] - 1e-6 and x <= b[2] + 1e-6 and y >= b[3] - 1e-6 and y <= b[4] + 1e-6 and z >= b[5] - 1e-6 and z <= b[6] + 1e-6 then
				return true
			end
		end
		return false
	end
	local half, t = building.width / 2, data.THICK
	local gaps = 0
	local firstGap = nil
	local function sample(x, y, z)
		if not inSolid(x, y, z) then
			gaps += 1
			firstGap = firstGap or string.format("(%.1f, %.1f, %.1f)", x, y, z)
		end
	end
	local y = data.GROUND + 0.5
	while y < building.ceiling do
		local z = building.back
		while z <= data.FRONT + 1e-6 do
			sample(-half + t / 2, y, z)
			sample(half - t / 2, y, z)
			z += 0.5
		end
		local x = -half
		while x <= half + 1e-6 do
			sample(x, y, building.back + t / 2)
			if not (math.abs(x) < building.door / 2 - 1e-6 and y < data.DOOR_TOP) then
				sample(x, y, data.FRONT - t / 2)
			end
			x += 0.5
		end
		y += 1
	end
	if gaps > 0 then
		problem(string.format("closed: %d points of the outer walls are open (first at %s in the garage frame)", gaps, firstGap))
	end

	-- Two faces on the same plane, looking the same way, over the same area, flicker (z-fighting). Faces looking down
	-- rest on something and are never seen. Model parts are not boxes: skipped.
	if not opts.skipFaces then
		for i = 1, #parts do
			for j = i + 1, #parts do
				local a, b = parts[i], parts[j]
				if not a.fromModel and not b.fromModel and a.part.Transparency < 1 and b.part.Transparency < 1 then
					for axis = 0, 2 do
						local lo, hi = axis * 2 + 1, axis * 2 + 2
						local o1, o2 = (axis + 1) % 3, (axis + 2) % 3
						local area1 = math.min(a.box[o1 * 2 + 2], b.box[o1 * 2 + 2]) - math.max(a.box[o1 * 2 + 1], b.box[o1 * 2 + 1])
						local area2 = math.min(a.box[o2 * 2 + 2], b.box[o2 * 2 + 2]) - math.max(a.box[o2 * 2 + 1], b.box[o2 * 2 + 1])
						if area1 > OVERLAP and area2 > OVERLAP then
							local same = math.abs(a.box[hi] - b.box[hi]) < OVERLAP and "top/outer"
								or (axis ~= 1 and math.abs(a.box[lo] - b.box[lo]) < OVERLAP and "bottom/inner") or nil
							if same then
								problem("faces: " .. a.name .. " and " .. b.name .. " share a face (" .. same .. ", axis " .. axis .. ")")
							end
						end
					end
				end
			end
		end
	end

	-- Floating: everything rests on the ground, the Floor or a chain of touching parts
	local floorBox = { -F, F, data.GROUND, 0, -F, F }
	local supported, queue = {}, {}
	local function touching(a, b)
		return a[1] <= b[2] + TOUCH and b[1] <= a[2] + TOUCH and a[3] <= b[4] + TOUCH and b[3] <= a[4] + TOUCH
			and a[5] <= b[6] + TOUCH and b[5] <= a[6] + TOUCH
	end
	for i, p in ipairs(parts) do
		if p.box[3] <= data.GROUND + TOUCH or touching(p.box, floorBox) then
			supported[i] = true
			table.insert(queue, i)
		end
	end
	local head = 1
	while head <= #queue do
		local a = parts[queue[head]].box
		head += 1
		for j, p in ipairs(parts) do
			if not supported[j] and touching(a, p.box) then
				supported[j] = true
				table.insert(queue, j)
			end
		end
	end
	for i, p in ipairs(parts) do
		if not supported[i] and p.part.Name ~= "TextPlate" then
			problem(p.name .. ": floating")
		end
	end
	return problems
end

return PlotBuildingVisuals
