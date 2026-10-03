-- BuildingClient: fades the roof and walls of a building when the local player is inside it (branch building-pass).
-- WHERE: a LocalScript named exactly BuildingClient in StarterPlayer > StarterPlayerScripts (create a new, empty
-- LocalScript there by hand and paste this whole file into it). It is not in the repo's game tree on purpose.
--
-- Client only, looks only. The server builds the Model "PlotBuilding" (PlotBuildingVisuals) and tags it
-- "PlotBuilding"; the numbers this script needs are attributes of that Model. This script:
--   * never fires a remote, never reads or writes a save, never touches anything outside tagged building Models;
--   * only writes Transparency of the parts in a building's "Fade" group (and TextTransparency / Enabled of the
--     SurfaceGui text on them), on this client only. Nothing it does reaches the server or another player;
--   * never touches CanCollide, CanTouch, CanQuery, Anchored or any part's position: the building has no effect on play.
-- The inside check and the fade maths below (BUILDINGMATH) are the same text as in PlotBuildingVisuals.lua,
-- which tools/building_test.py tests; it fails if the two copies differ.

local CollectionService = game:GetService("CollectionService")
local Players = game:GetService("Players")
local RunService = game:GetService("RunService")

local TAG = "PlotBuilding"
local player = Players.LocalPlayer

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

-- Reading a building -----------------------------------------------------------------------------------------

local FIELDS = {
	minX = "MinX", maxX = "MaxX", minY = "MinY", maxY = "MaxY", minZ = "MinZ", maxZ = "MaxZ",
	doorMinX = "DoorMinX", doorMaxX = "DoorMaxX", doorDepth = "DoorDepth", margin = "Margin",
}

-- The inside box from the Model's attributes, or nil if one is missing or not a finite number
local function readBounds(model)
	local bounds = {}
	for field, attribute in pairs(FIELDS) do
		local value = model:GetAttribute(attribute)
		if not finite(value) then
			return nil
		end
		bounds[field] = value
	end
	return bounds
end

-- One state per building Model: { model, bounds, seconds, levels, fade, level, inside, parts, labels, guis, connections }
local buildings = {}

local function rootPart()
	local character = player.Character
	local root = character and character:FindFirstChild("HumanoidRootPart")
	if root and root.Parent then
		return root
	end
	return nil
end

-- Writes one step of the fade on everything of the building. Only called when the step changes.
local function apply(state, level)
	local levels = state.levels
	for part, base in pairs(state.parts) do
		if part.Parent then
			part.Transparency = transparencyAt(base, level, levels)
		end
	end
	for label, base in pairs(state.labels) do
		if label.Parent then
			label.TextTransparency = transparencyAt(base, level, levels)
		end
	end
	for gui in pairs(state.guis) do
		if gui.Parent then
			gui.Enabled = level < levels -- a SurfaceGui keeps drawing on a part that is fully transparent
		end
	end
end

-- Remembers one part (or a piece of text) of the Fade group with its own starting values, at the current step
local function remember(state, item)
	if item:IsA("BasePart") then
		state.parts[item] = item.Transparency
		item.Transparency = transparencyAt(item.Transparency, state.level, state.levels)
	elseif item:IsA("SurfaceGui") then
		state.guis[item] = true
		item.Enabled = state.level < state.levels
	elseif item:IsA("TextLabel") then
		state.labels[item] = item.TextTransparency
		item.TextTransparency = transparencyAt(item.TextTransparency, state.level, state.levels)
	end
end

local function forget(model)
	local state = buildings[model]
	if state then
		for _, connection in ipairs(state.connections) do
			connection:Disconnect()
		end
		buildings[model] = nil
	end
end

-- A new building arrived (a join, or a new funding stage replaced the old one). It starts at the right step at
-- once, no fade: someone standing inside when the stage changes never sees the roof come back.
local function track(model)
	if buildings[model] then
		return
	end
	local bounds
	for _ = 1, 20 do -- attributes and children can arrive a moment after the Model
		bounds = readBounds(model)
		if bounds and model:FindFirstChild("Fade") then
			break
		end
		task.wait(0.25)
		if not model.Parent then
			return
		end
	end
	if not bounds or not model:FindFirstChild("Fade") then
		warn("BuildingClient: a building arrived without its numbers, so its roof will not fade")
		return
	end
	local seconds, levels = model:GetAttribute("FadeSeconds"), model:GetAttribute("FadeLevels")
	if not (finite(seconds) and finite(levels)) then
		seconds, levels = 0.4, 20
	end
	local root = rootPart()
	local inside = false
	if root then
		local p = root.Position
		inside = isInside(bounds, p.X, p.Y, p.Z, false)
	end
	local state = {
		model = model, bounds = bounds, seconds = seconds, levels = math.max(1, math.floor(levels + 0.5)),
		fade = inside and 1 or 0, inside = inside, parts = {}, labels = {}, guis = {}, connections = {},
	}
	state.level = quantize(state.fade, state.levels)
	local fade = model:FindFirstChild("Fade")
	for _, item in ipairs(fade:GetDescendants()) do
		remember(state, item)
	end
	table.insert(state.connections, fade.DescendantAdded:Connect(function(item)
		remember(state, item)
	end))
	buildings[model] = state
end

-- Following the buildings -------------------------------------------------------------------------------------

for _, model in ipairs(CollectionService:GetTagged(TAG)) do
	task.spawn(track, model)
end
CollectionService:GetInstanceAddedSignal(TAG):Connect(function(model)
	task.spawn(track, model)
end)
CollectionService:GetInstanceRemovedSignal(TAG):Connect(forget)

-- Every frame: is the local character inside each building? Move each fade toward its target, and write
-- Transparency only when the step changes (nothing is written while a roof holds still).
RunService.Heartbeat:Connect(function(dt)
	local root = rootPart()
	for model, state in pairs(buildings) do
		local ok, err = pcall(function()
			if root then -- no character (dead, respawning): hold the last state
				local p = root.Position
				state.inside = isInside(state.bounds, p.X, p.Y, p.Z, state.inside)
			end
			local target = state.inside and 1 or 0
			if state.fade ~= target then
				state.fade = fadeStep(state.fade, target, dt, state.seconds)
				local level = quantize(state.fade, state.levels)
				if level ~= state.level then
					state.level = level
					apply(state, level)
				end
			end
		end)
		if not ok then
			warn("BuildingClient: " .. tostring(err) .. " (this building's roof stays as it is)")
			forget(model)
		end
	end
end)
