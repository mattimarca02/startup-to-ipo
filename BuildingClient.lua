-- BuildingClient: fades the shell parts of a garage's building that stand between the camera and the local player
-- (lobby L2, from building-pass; overhaul phase 2: an occlusion fade instead of the whole-shell fade).
-- WHERE: a LocalScript named exactly BuildingClient in StarterPlayer > StarterPlayerScripts.
--
-- Client only, looks only. The server builds the Model "PlotBuilding" (PlotBuildingVisuals) and tags it "PlotBuilding";
-- the numbers this script needs are attributes of that Model: the garage's frame (Frame, a CFrame), the fade's time
-- (FadeSeconds) and the transparency a part in the way goes to (Occluded). This script:
--   * every frame, for each building near the camera, finds the parts of its "Fade" group (the shell: kit MeshParts or
--     Parts) that the two segments from the camera to the character (its root and its head) pass through, and fades only
--     those toward the Occluded transparency (from each part's own starting value: glass from 0.3); a part no longer in
--     the way comes back to its own value. Inside the building you see its walls, ceiling, door and windows around you;
--     from outside it stays solid; only what hides the character from the camera turns see-through;
--   * when the local player's own garage changes to a higher funding stage (a new building Model with a higher Stage
--     arrives in their garage), gives a short look at the new facade: the camera flies to a spot in front of the door
--     for about two seconds and comes back (a tap or a key skips it; never while a window is open, PlayerGui "OpenPanel";
--     never after an IPO, which brings the Garage back), with a built-in sound;
--   * never fires a remote, never reads or writes a save, never touches anything outside tagged building Models;
--   * only writes Transparency of the Fade parts, on this client only, and the camera's CFrame during the look. The
--     furniture ("Static") and the invisible solid boxes ("Solid") are never touched; CanCollide, CanTouch, CanQuery,
--     Anchored and every position stay the server's.
-- The pure maths below (BUILDINGMATH) are the same text as in PlotBuildingVisuals.lua, which tools/building_test.py
-- tests; it fails if the two copies differ.

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
-- (the garage's frame; maxY is the ground floor's ceiling; the door is on the +Z side). Edges count as inside. The
-- doorway and the apron in front of it count too. Above the ceiling is outside. wasInside makes the box `margin`
-- bigger (no flicker on a wall line). A coordinate that is NaN or infinite is never inside.
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

-- Does the segment from a to b (both in a box's own frame, as numbers) pass through the box of half sizes hx, hy, hz
-- centered on the origin? The slab test, edges count. A NaN or infinite coordinate never hits.
local function segmentHitsBox(ax, ay, az, bx, by, bz, hx, hy, hz)
	if not (finite(ax) and finite(ay) and finite(az) and finite(bx) and finite(by) and finite(bz)) then
		return false
	end
	local t0, t1 = 0, 1
	local as, bs, hs = { ax, ay, az }, { bx, by, bz }, { hx, hy, hz }
	for axis = 1, 3 do
		local a, d, h = as[axis], bs[axis] - as[axis], hs[axis]
		if math.abs(d) < 1e-9 then
			if a < -h or a > h then
				return false
			end
		else
			local ta, tb = (-h - a) / d, (h - a) / d
			if ta > tb then
				ta, tb = tb, ta
			end
			t0 = math.max(t0, ta)
			t1 = math.min(t1, tb)
			if t0 > t1 then
				return false
			end
		end
	end
	return true
end

-- Moves the fade (0 = as built, 1 = fully in the way) toward the target by dt / seconds, never past it, always in 0..1.
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

-- A part's Transparency at a fade: its own base value at 0, `top` (the occluded transparency, never below its base)
-- at 1, in 0..1
local function occludedTransparency(base, fade, top)
	local b, t = clamp01(base), clamp01(top)
	if t < b then
		t = b
	end
	return clamp01(b + (t - b) * clamp01(fade))
end
-- BUILDINGMATH-END

-- Reading a building -----------------------------------------------------------------------------------------

local DEFAULT_SECONDS, DEFAULT_OCCLUDED = 0.3, 0.8
local FADE_BACK = 1.5 -- a part comes back this many times slower than it goes out of the way (no flicker)
local HEAD = 2.2 -- the second segment ends this far above the root part (the head)
local NEAR = 240 -- a building whose box is farther than this from the camera is left as it is

-- One state per building Model: { model, frame, seconds, occluded, parts = { [part] = { base, fade } }, box, connections }
local buildings = {}

local function rootPart()
	local character = player.Character
	local root = character and character:FindFirstChild("HumanoidRootPart")
	if root and root.Parent then
		return root
	end
	return nil
end

-- The world box around a part (axis-aligned)
local function boxOf(cframe, size)
	local x, y, z, r00, r01, r02, r10, r11, r12, r20, r21, r22 = cframe:GetComponents()
	local hx = (math.abs(r00) * size.X + math.abs(r01) * size.Y + math.abs(r02) * size.Z) / 2
	local hy = (math.abs(r10) * size.X + math.abs(r11) * size.Y + math.abs(r12) * size.Z) / 2
	local hz = (math.abs(r20) * size.X + math.abs(r21) * size.Y + math.abs(r22) * size.Z) / 2
	return { x - hx, x + hx, y - hy, y + hy, z - hz, z + hz }
end

-- Grows the building's world box to hold a part
local function growBox(state, part)
	local b = boxOf(part.CFrame, part.Size)
	local box = state.box
	if not box then
		state.box = b
		return
	end
	for k = 1, 5, 2 do
		box[k] = math.min(box[k], b[k])
		box[k + 1] = math.max(box[k + 1], b[k + 1])
	end
end

-- Remembers one shell part with its own starting value (a part that arrives later starts as built)
local function remember(state, item)
	if item:IsA("BasePart") then
		state.parts[item] = { base = item.Transparency, fade = 0 }
		growBox(state, item)
	end
end

local function forget(model)
	local state = buildings[model]
	if state then
		for _, connection in ipairs(state.connections) do
			connection:Disconnect()
		end
		for part, info in pairs(state.parts) do
			if part.Parent and info.fade > 0 then
				part.Transparency = info.base -- a building that goes while in the way: as built, not half see-through
			end
		end
		buildings[model] = nil
	end
end

-- Does the segment a-b (world points) pass through a part?
local function hitsPart(part, a, b)
	local cframe, size = part.CFrame, part.Size
	local la, lb = cframe:PointToObjectSpace(a), cframe:PointToObjectSpace(b)
	return segmentHitsBox(la.X, la.Y, la.Z, lb.X, lb.Y, lb.Z, size.X / 2, size.Y / 2, size.Z / 2)
end

-- Does the segment a-b pass through a world box (axis-aligned)?
local function hitsBox(box, a, b)
	local cx, cy, cz = (box[1] + box[2]) / 2, (box[3] + box[4]) / 2, (box[5] + box[6]) / 2
	return segmentHitsBox(a.X - cx, a.Y - cy, a.Z - cz, b.X - cx, b.Y - cy, b.Z - cz, (box[2] - box[1]) / 2, (box[4] - box[3]) / 2, (box[6] - box[5]) / 2)
end

-- The stage-up look ---------------------------------------------------------------------------------------------
-- The local player's own garage got a building of a higher stage: a short look at the new facade. The camera flies to
-- a spot in front of the door and comes back; a tap or a key skips it. Nothing of it is saved or sent; the server
-- swapped the building exactly as before. It runs inside pcall: a camera or input API that is missing (an old client,
-- the tests' fake) plays nothing and breaks nothing.
local LOOK_SECONDS = 2.6 -- the whole look
local LOOK_FLY = 0.45 -- of it, the flight out (and back)
local LOOK_SOUND = "rbxasset://sounds/victory.wav" -- a built-in sound (no Store asset); a missing one plays nothing
local lastStage = {} -- slot -> the Stage of the building last seen in that garage
local looking = false
local looksStarted = 0 -- how many looks began (the tests read it)

local function easeOut(t)
	t = clamp01(t)
	return 1 - (1 - t) * (1 - t)
end

local function playLookSound()
	pcall(function()
		local sound = Instance.new("Sound")
		sound.Name = "StageUpSound"
		sound.SoundId = LOOK_SOUND
		sound.Volume = 0.6
		sound.Parent = player:WaitForChild("PlayerGui", 5)
		sound:Play()
		task.delay(6, function()
			sound:Destroy()
		end)
	end)
end

local function lookAt(model)
	local frame = model:GetAttribute("Frame")
	local playerGui = player:FindFirstChild("PlayerGui")
	if looking or typeof(frame) ~= "CFrame" or (playerGui and playerGui:GetAttribute("OpenPanel") ~= nil) then
		return
	end
	local camera = workspace.CurrentCamera
	if not camera then
		return
	end
	looking = true
	looksStarted += 1
	playLookSound()
	local ok, err = pcall(function()
		local from = camera.CFrame
		local spot = frame * Vector3.new(0, 18, 80)
		local target = CFrame.lookAt(spot, frame * Vector3.new(0, 7, 22))
		camera.CameraType = Enum.CameraType.Scriptable
		local skipped = false
		local connection = nil
		pcall(function()
			connection = game:GetService("UserInputService").InputBegan:Connect(function(input, processed)
				if not processed then
					skipped = true
				end
			end)
		end)
		local t = 0
		while t < LOOK_SECONDS and not skipped do
			local dt = RunService.Heartbeat:Wait()
			t += dt
			local k
			if t < LOOK_FLY then
				k = easeOut(t / LOOK_FLY)
			elseif t > LOOK_SECONDS - LOOK_FLY then
				k = easeOut((LOOK_SECONDS - t) / LOOK_FLY)
			else
				k = 1
			end
			camera.CFrame = from:Lerp(target, k)
		end
		if connection then
			connection:Disconnect()
		end
		camera.CFrame = from
		camera.CameraType = Enum.CameraType.Custom
	end)
	if not ok then
		pcall(function()
			camera.CameraType = Enum.CameraType.Custom
		end)
		warn("BuildingClient: the stage-up look stopped early: " .. tostring(err))
	end
	looking = false
end

-- A new building Model in a garage: the local player's own garage at a higher stage gets the look
local function noteStage(model)
	local garage = model.Parent
	local slot = garage and garage:GetAttribute("Slot")
	local stage = model:GetAttribute("Stage")
	if type(slot) ~= "number" or type(stage) ~= "number" then
		return
	end
	local before = lastStage[slot]
	lastStage[slot] = stage
	if before and stage > before and player:GetAttribute("Garage") == slot then
		task.spawn(lookAt, model)
	end
end

-- Following the buildings -------------------------------------------------------------------------------------

-- A new building arrived (a join, or a new funding stage replaced the old one)
local function track(model)
	if buildings[model] then
		return
	end
	local fade
	for _ = 1, 20 do -- attributes and children can arrive a moment after the Model
		fade = model:FindFirstChild("Fade")
		if fade and typeof(model:GetAttribute("Frame")) == "CFrame" then
			break
		end
		task.wait(0.25)
		if not model.Parent then
			return
		end
	end
	if not fade then
		warn("BuildingClient: a building arrived without its shell, so nothing of it will fade")
		return
	end
	local seconds, occluded = model:GetAttribute("FadeSeconds"), model:GetAttribute("Occluded")
	if not finite(seconds) then
		seconds = DEFAULT_SECONDS
	end
	if not finite(occluded) then
		occluded = DEFAULT_OCCLUDED
	end
	local state = { model = model, frame = model:GetAttribute("Frame"), seconds = seconds, occluded = occluded, parts = {}, box = nil, connections = {} }
	for _, item in ipairs(fade:GetDescendants()) do
		remember(state, item)
	end
	table.insert(state.connections, fade.DescendantAdded:Connect(function(item)
		remember(state, item)
	end))
	buildings[model] = state
	noteStage(model)
end

for _, model in ipairs(CollectionService:GetTagged(TAG)) do
	task.spawn(track, model)
end
CollectionService:GetInstanceAddedSignal(TAG):Connect(function(model)
	task.spawn(track, model)
end)
CollectionService:GetInstanceRemovedSignal(TAG):Connect(forget)

-- One building, one frame: which shell parts stand between the camera and the character? Move each part's fade toward
-- 1 (in the way) or 0 (clear) and write its Transparency only when it changes (nothing is written while all holds still).
local function update(state, camera, root, dt)
	local a = camera.Position
	local b1 = root.Position
	local b2 = b1 + Vector3.new(0, HEAD, 0)
	local box = state.box
	local near = box ~= nil and (hitsBox(box, a, b1) or hitsBox(box, a, b2))
	if not near then
		-- the camera's line never crosses the building: everything comes back (or stays) as built
		local far = box == nil or math.abs(a.X - (box[1] + box[2]) / 2) > NEAR or math.abs(a.Z - (box[5] + box[6]) / 2) > NEAR
		for part, info in pairs(state.parts) do
			if info.fade > 0 then
				info.fade = far and 0 or fadeStep(info.fade, 0, dt, state.seconds * FADE_BACK)
				if part.Parent then
					part.Transparency = occludedTransparency(info.base, info.fade, state.occluded)
				end
			end
		end
		return
	end
	for part, info in pairs(state.parts) do
		local inWay = part.Parent ~= nil and (hitsPart(part, a, b1) or hitsPart(part, a, b2))
		local target = inWay and 1 or 0
		if info.fade ~= target then
			info.fade = fadeStep(info.fade, target, dt, inWay and state.seconds or state.seconds * FADE_BACK)
			if part.Parent then
				part.Transparency = occludedTransparency(info.base, info.fade, state.occluded)
			end
		end
	end
end

RunService.Heartbeat:Connect(function(dt)
	local root = rootPart()
	local camera = workspace.CurrentCamera
	if not (root and camera) then
		return -- no character (dead, respawning) or no camera: hold the last state
	end
	local cameraFrame = camera.CFrame
	for model, state in pairs(buildings) do
		local ok, err = pcall(update, state, cameraFrame, root, dt)
		if not ok then
			warn("BuildingClient: " .. tostring(err) .. " (this building stays as it is)")
			forget(model)
		end
	end
end)
