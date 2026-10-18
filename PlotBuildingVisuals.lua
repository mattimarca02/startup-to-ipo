-- PlotBuildingVisuals: builds the closed building around a garage from PlotBuilding's layout, with the 3D kit
-- (ReplicatedStorage.KitModels) or, for any piece whose model is missing, from Parts; and holds the pure maths of the
-- fade. Put this ModuleScript in ServerScriptService, next to PlotBuilding (the data) and TycoonCore (which calls it).
--
-- Blocks (PlotBuilding.BLOCK: roofs, signs, sills...) are always one plain Part each, with the fallback's flags.
-- Only looks, plus seven to ten invisible boxes that make the outer walls and the roof solid. Nothing is saved, sent
-- through a remote or read back by the game. Every kit MeshPart and every fallback Part is anchored with CanCollide,
-- CanTouch and CanQuery off and no shadow: it never decides collision, touch, rays or the camera. The solid boxes are
-- anchored Parts with CanCollide on, CanTouch off, Transparency 1 (Roblox's camera ignores a part that transparent).
-- The client script BuildingClient fades the parts of the "Fade" group that stand between the camera and the local
-- player (an occlusion fade, overhaul phase 2); the server never learns it. The one light of a building (its ceiling
-- light, a PointLight on the roof piece: PlotBuilding.Styles[stage].light) is the only Light it ever makes.
--
--   PlotBuildingVisuals.build(parent, frame, building, stage, kit) -> Model "PlotBuilding": Fade, Static, Solid
--   PlotBuildingVisuals.sync(garage, frame, building, stage, kit)  -> the Model of that stage in the garage, changed
--   PlotBuildingVisuals.unstick(model, roots, landing)             -> moves a character found inside a solid box
--   PlotBuildingVisuals.buildPiece(parent, frame, building, stage, piece, kit) -> one piece alone (the kit front check)
--   PlotBuildingVisuals.setSign(model, title, subtitle)            -> writes the facade sign's text (the one gui of a building)
--   PlotBuildingVisuals.checkKit(folder, manifest)                 -> problems of ReplicatedStorage.KitModels (empty = fine)
--   PlotBuildingVisuals.check(model, frame, building, opts)        -> problems of a built Model (budget, flags, lane...)
--   Pure maths, the same text as BuildingClient (a test compares them):
--   isInside(bounds, x, y, z, wasInside), segmentHitsBox(ax, ay, az, bx, by, bz, hx, hy, hz),
--   fadeStep(fade, target, dt, seconds), occludedTransparency(base, fade, top)
--
-- frame = the garage's frame (TycoonCore plotFrame(slot), a CFrame: the plot center, turned). Every number of the
-- layout is in it, from the Floor's top (frame * (0, FLOOR_TOP, 0)). kit = the KitModels folder, or nil (all Parts).

local PlotBuildingVisuals = {}

PlotBuildingVisuals.TAG = "PlotBuilding" -- CollectionService tag on the Model: the client finds buildings by it
PlotBuildingVisuals.GROUPS = { Fade = true, Static = true, Solid = true }

local OVERLAP = 0.01 -- parts must go this far into a box to count as inside it
local STRETCH_EPS = 1e-3 -- a stretch this close to 1 is float noise (a KitSize of 15.9999), never a real stretch
local PIVOT_EPS = 0.05 -- checkKit: a model's WorldPivot this close to the bottom-center of its parts is fine

-- The pure maths ---------------------------------------------------------------------------------------------------
-- No services, no Instances: they run the same in the tests (a fake Roblox) and in BuildingClient, which carries a copy
-- of this block (tools/building_test.py fails if the two texts differ). isInside's bounds are in the garage's frame;
-- segmentHitsBox works in a part's own frame.

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

PlotBuildingVisuals.isInside = isInside
PlotBuildingVisuals.segmentHitsBox = segmentHitsBox
PlotBuildingVisuals.fadeStep = fadeStep
PlotBuildingVisuals.occludedTransparency = occludedTransparency

-- Helpers ------------------------------------------------------------------------------------------------------------

-- One warning per server for each kind of problem (a missing kit warns once, not 60 times a build)
local warned = {}
local function warnOnce(kind, text)
	if not warned[kind] then
		warned[kind] = true
		warn("Plot buildings: " .. text)
	end
end
PlotBuildingVisuals.resetWarnings = function()
	warned = {}
end

local function rgb(c)
	return Color3.fromRGB(c[1], c[2], c[3])
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
PlotBuildingVisuals.overlaps = overlaps

-- The Floor's top in the garage's frame: every layout number starts here
local function originOf(frame, building)
	return frame * CFrame.new(0, building.FLOOR_TOP, 0)
end
PlotBuildingVisuals.originOf = originOf

-- Where a piece stands: its bottom-center, turned (its front), then tilted about its own X (the rolled-up garage door)
local function pieceFrame(origin, piece)
	return origin * CFrame.new(piece.x, piece.y, piece.z) * CFrame.Angles(0, math.rad(piece.turn or 0), 0)
		* CFrame.Angles(math.rad(piece.tilt or 0), 0, 0)
end
PlotBuildingVisuals.pieceFrame = pieceFrame

local function stretched(s)
	return math.abs(s - 1) > STRETCH_EPS
end

-- The stretch a piece may have: only PlotBuilding.STRETCH keys, only on their axes. Anything else is built at kit size.
local function stretchOf(building, piece)
	local allowed = building.STRETCH[piece.key]
	local sx, sz = piece.sx or 1, piece.sz or 1
	if (stretched(sx) and not (allowed and allowed.x)) or (stretched(sz) and not (allowed and allowed.z)) then
		warnOnce("stretch " .. piece.key, piece.key .. " may not be stretched: built at its kit size")
		return 1, 1
	end
	if not (finite(sx) and sx > 0 and finite(sz) and sz > 0) then
		return 1, 1
	end
	return sx, sz
end
PlotBuildingVisuals.stretchOf = stretchOf

-- The flags every look part gets: never solid, never touched, never hit by a ray, no shadow
local function lookFlags(part)
	part.Anchored = true
	part.CanCollide = false
	part.CanTouch = false
	part.CanQuery = false
	part.CastShadow = false
end

local function paint(part, building, stage, piece, role)
	local style = building.styleOf(stage, piece.key, role, piece.look)
	if not style then
		warnOnce("style " .. piece.key .. "." .. tostring(role), "no style for " .. piece.key .. "." .. tostring(role))
		return
	end
	part.Color = rgb(style.color)
	part.Material = Enum.Material[style.material]
	part.Transparency = style.transparency
end

local function tag(part, piece, role)
	part:SetAttribute("Piece", piece.name)
	part:SetAttribute("Key", piece.key)
	part:SetAttribute("Role", role)
end

-- The sign's text: the one gui of a building (PlotBuilding.SIGN_TEXT), on the board's plaza side, empty until the server
-- writes it (setSign). No decal, no asset: a TextLabel in a SurfaceGui.
local function addSignText(part, building)
	local spec = building.SIGN_TEXT
	local gui = Instance.new("SurfaceGui")
	gui.Name = spec.name
	gui.Face = Enum.NormalId[spec.face]
	gui.SizingMode = Enum.SurfaceGuiSizingMode.PixelsPerStud
	gui.PixelsPerStud = spec.pixelsPerStud
	gui.LightInfluence = 0.5
	local label = Instance.new("TextLabel")
	label.Name = "Label"
	label.Position = UDim2.fromScale(spec.area[1], spec.area[2])
	label.Size = UDim2.fromScale(spec.area[3], spec.area[4])
	label.BackgroundTransparency = 1
	label.TextScaled = true
	label.Font = Enum.Font[spec.font]
	label.TextColor3 = rgb(spec.color)
	label.Text = ""
	label.Parent = gui
	gui.Parent = part
	return gui
end

-- The Parts version of one piece (PlotBuilding.partsOf: a kit model's fallback, or a Block's one Part), in the
-- building-pass style. The sign board (a Block with text = true) gets the building's SurfaceGui.
local function buildFallback(parent, origin, building, stage, piece)
	local base = pieceFrame(origin, piece)
	local sx, sz = stretchOf(building, piece)
	local parts = {}
	for i, b in ipairs(building.partsOf(piece) or {}) do
		local part = Instance.new("Part")
		part.Name = piece.name .. "_" .. b.role .. i
		part.Size = Vector3.new(b.size[1] * sx, b.size[2], b.size[3] * sz)
		part.CFrame = base * CFrame.new(b.at[1] * sx, b.at[2], b.at[3] * sz)
		part.TopSurface = Enum.SurfaceType.Smooth
		part.BottomSurface = Enum.SurfaceType.Smooth
		lookFlags(part)
		paint(part, building, stage, piece, b.role)
		tag(part, piece, b.role)
		if piece.text and piece.key == building.BLOCK then
			addSignText(part, building)
		end
		part.Parent = parent
		table.insert(parts, part)
	end
	return parts
end

-- Writes the sign's text: title on the first line, subtitle (or nothing) on the second. The server calls it with the
-- owner's company name and the stage's name, or FREE and "Claim this garage" (TycoonCore). Returns true when the
-- building has a sign. Looks only: nothing is read back.
function PlotBuildingVisuals.setSign(model, title, subtitle)
	local fade = model and model:FindFirstChild("Fade")
	local gui = fade and fade:FindFirstChild(PlotBuildingVisuals.SIGN_TEXT_NAME, true)
	local label = gui and gui:FindFirstChild("Label")
	if not label then
		return false
	end
	local text = tostring(title or "")
	if subtitle ~= nil and subtitle ~= "" then
		text ..= "\n" .. tostring(subtitle)
	end
	if label.Text ~= text then
		label.Text = text
	end
	return true
end
PlotBuildingVisuals.SIGN_TEXT_NAME = "SignText"

-- The axis of a part (1 X, 2 Y, 3 Z) that lies along the model's axis (1 X or 3 Z), or nil when it is turned otherwise
local function alignedAxis(rel, modelAxis)
	local _, _, _, r00, r01, r02, _, _, _, r20, r21, r22 = rel:GetComponents()
	local row = modelAxis == 1 and { r00, r01, r02 } or { r20, r21, r22 }
	for i = 1, 3 do
		if math.abs(math.abs(row[i]) - 1) < 1e-4 then
			return i
		end
	end
	return nil
end

-- The kit version of one piece: a copy of each MeshPart of KitModels.<key>, stretched (Wall, RoofEdge, Floor), turned
-- by KIT_FRONT_TURN, placed by the model's WorldPivot. Returns the parts, or nil and why (then the Parts version is built).
local function buildKit(parent, origin, building, stage, piece, template)
	if not template:IsA("Model") then
		return nil, "not a Model"
	end
	local entry = building.KitManifest[piece.key]
	local size = template:GetAttribute("KitSize")
	local kx = (typeof(size) == "Vector3" and size.X > 0) and size.X or entry.size[1]
	local kz = (typeof(size) == "Vector3" and size.Z > 0) and size.Z or entry.size[3]
	local sx, sz = stretchOf(building, piece)
	sx, sz = sx * entry.size[1] / kx, sz * entry.size[3] / kz -- the wanted width over the model's real one
	local pivot = template.WorldPivot
	local target = pieceFrame(origin, piece) * CFrame.Angles(0, math.rad(building.KIT_FRONT_TURN), 0)
	local made = {}
	for _, d in ipairs(template:GetDescendants()) do
		if d:IsA("MeshPart") then
			local rel = pivot:ToObjectSpace(d.CFrame)
			local partSize = d.Size
			if stretched(sx) or stretched(sz) then
				local ax, az = alignedAxis(rel, 1), alignedAxis(rel, 3)
				if (stretched(sx) and not ax) or (stretched(sz) and not az) then
					for _, p in ipairs(made) do
						p:Destroy()
					end
					return nil, "a part is not square to the model, so it can't be stretched"
				end
				local s = { partSize.X, partSize.Y, partSize.Z }
				if ax and stretched(sx) then s[ax] *= sx end
				if az and stretched(sz) then s[az] *= sz end
				partSize = Vector3.new(s[1], s[2], s[3])
				local x, y, z = rel:GetComponents()
				rel = CFrame.new(stretched(sx) and x * sx or x, y, stretched(sz) and z * sz or z) * rel.Rotation
			end
			local part = d:Clone()
			if not part then -- Archivable is off: Roblox's Clone gives nil
				for _, p in ipairs(made) do
					p:Destroy()
				end
				return nil, "a MeshPart can't be copied (" .. d.Name .. ": Archivable is off)"
			end
			for _, child in ipairs(part:GetChildren()) do
				child:Destroy() -- only the MeshPart itself
			end
			local role = d:GetAttribute("Role") or (string.gsub(d.Name, "%d+$", ""))
			part.Name = piece.name .. "_" .. role
			part.Size = partSize
			part.CFrame = target * rel
			lookFlags(part)
			paint(part, building, stage, piece, role)
			tag(part, piece, role)
			part.Parent = parent
			table.insert(made, part)
		else
			warnOnce("kit extras", "KitModels: only MeshParts are used; other objects in a model are left out (" .. piece.key .. "." .. d.Name .. ")")
		end
	end
	if #made == 0 then
		return nil, "no MeshPart in it"
	end
	return made
end

-- One solid box: anchored, invisible, solid, never touched (the only solid parts of a building)
local function buildBox(parent, origin, b)
	local box = b.box
	local part = Instance.new("Part")
	part.Name = "Solid" .. b.name
	part.Size = Vector3.new(box[2] - box[1], box[4] - box[3], box[6] - box[5])
	part.CFrame = origin * CFrame.new((box[1] + box[2]) / 2, (box[3] + box[4]) / 2, (box[5] + box[6]) / 2)
	part.Anchored = true
	part.CanCollide = true
	part.CanTouch = false
	part.CanQuery = true
	part.CastShadow = false
	part.Transparency = 1
	part.Color = Color3.fromRGB(128, 128, 128)
	part.Material = Enum.Material.SmoothPlastic
	part:SetAttribute("Piece", b.name)
	part.Parent = parent
	return part
end

-- One piece on its own, the way build places it (the Studio kit front check uses it): a Model holding its parts, from
-- the kit when kit has the key, else from Parts. Returns the Model and true when it came from the kit.
function PlotBuildingVisuals.buildPiece(parent, frame, building, stage, piece, kit)
	local model = Instance.new("Model")
	model.Name = piece.name
	local origin = originOf(frame, building)
	local template = kit and piece.key ~= building.BLOCK and kit:FindFirstChild(piece.key)
	local made = template and buildKit(model, origin, building, stage, piece, template)
	if not made then
		buildFallback(model, origin, building, stage, piece)
	end
	model.Parent = parent
	return model, made ~= nil and made ~= false
end

-- The building's one light: a PointLight under the ground floor's ceiling (on the outer mass's roof piece, a part of the
-- Fade group), styled per stage (PlotBuilding.Styles[stage].light); none when the stage has no light or no roof part
local function addCeilingLight(fadeGroup, building, stage)
	local style = building.Styles[stage]
	local spec = style and style.light
	if type(spec) ~= "table" then
		return nil
	end
	local roof = nil
	for _, part in ipairs(fadeGroup:GetChildren()) do
		if part:IsA("BasePart") and part:GetAttribute("Piece") == "M1Roof" then
			roof = part
			break
		end
	end
	if not roof then
		return nil
	end
	local light = Instance.new("PointLight")
	light.Name = "CeilingLight"
	light.Color = rgb(spec.color)
	light.Brightness = spec.brightness
	light.Range = spec.range
	light.Shadows = false
	light.Parent = roof
	return light
end

-- The attribute names the client reads (the inside box, in the garage's frame) and the frame itself
PlotBuildingVisuals.ATTRIBUTES = {
	minX = "MinX", maxX = "MaxX", minY = "MinY", maxY = "MaxY", minZ = "MinZ", maxZ = "MaxZ",
	doorMinX = "DoorMinX", doorMaxX = "DoorMaxX", doorDepth = "DoorDepth", margin = "Margin",
}

-- Building ---------------------------------------------------------------------------------------------------------

-- The Model "PlotBuilding" of one stage: Fade (the shell: it fades), Static (the furniture and the band's floor: it
-- stays), Solid (the invisible boxes). Its attributes are everything BuildingClient needs.
function PlotBuildingVisuals.build(parent, frame, building, stage, kit)
	local layout = building.layout(stage)
	local origin = originOf(frame, building)
	local model = Instance.new("Model")
	model.Name = "PlotBuilding"
	model:SetAttribute("Stage", layout.stage)
	model:SetAttribute("StageKey", layout.key)
	model:SetAttribute("StageName", layout.name) -- the sign's second line for a taken garage (TycoonCore)
	model:SetAttribute("Frame", origin)
	for field, attribute in pairs(PlotBuildingVisuals.ATTRIBUTES) do
		model:SetAttribute(attribute, layout.inside[field])
	end
	model:SetAttribute("FadeSeconds", building.Fade.seconds)
	model:SetAttribute("Occluded", building.Fade.occluded)
	local groups = {}
	for _, name in ipairs({ "Fade", "Static", "Solid" }) do
		local g = Instance.new("Model")
		g.Name = name
		g.Parent = model
		groups[name] = g
	end
	if not kit then
		warnOnce("no kit", "ReplicatedStorage." .. building.KIT_FOLDER .. " is missing: every building is built from Parts")
	end
	local fromKit, fromParts, blocks = 0, 0, 0
	for _, piece in ipairs(layout.pieces) do
		local parent2 = groups[piece.group] or groups.Fade
		local isBlock = piece.key == building.BLOCK
		local template = kit and not isBlock and kit:FindFirstChild(piece.key)
		local made, why = nil, nil
		if isBlock then
			blocks += 1 -- a Block is always one Part: there is no kit model to look for
		elseif template then
			made, why = buildKit(parent2, origin, building, layout.stage, piece, template)
			if not made then
				warnOnce("kit " .. piece.key, "KitModels." .. piece.key .. " can't be used (" .. tostring(why) .. "): built from Parts")
			end
		elseif kit then
			warnOnce("kit " .. piece.key, "KitModels." .. piece.key .. " is missing: built from Parts")
		end
		if made then
			fromKit += 1
		else
			buildFallback(parent2, origin, building, layout.stage, piece)
			if not isBlock then
				fromParts += 1
			end
		end
	end
	for _, b in ipairs(layout.boxes) do
		buildBox(groups.Solid, origin, b)
	end
	addCeilingLight(groups.Fade, building, layout.stage)
	model:SetAttribute("KitPieces", fromKit) -- kit pieces built from the kit
	model:SetAttribute("PartPieces", fromParts) -- kit pieces built from Parts (their model missing or unusable)
	model:SetAttribute("BlockPieces", blocks) -- Blocks (always one Part each)
	-- Streaming: the whole building is always there, even far away (lobby L4: the shells are seen across the plaza).
	-- Some versions may not allow it from a script: then it simply stays the default.
	pcall(function()
		model.ModelStreamingMode = Enum.ModelStreamingMode.Persistent
	end)
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

-- TycoonCore calls this every second (income loop), at server start and on a reset: the building of `stage` in the
-- garage, or nothing to do when it already shows it. A new stage replaces the old Model. Returns the Model and whether
-- it was just built.
function PlotBuildingVisuals.sync(garage, frame, building, stage, kit)
	local shown = building.shownStage(stage)
	local old = garage:FindFirstChild("PlotBuilding")
	if old and old:GetAttribute("Stage") == shown then
		return old, false
	end
	local model = PlotBuildingVisuals.build(nil, frame, building, shown, kit)
	model.Parent = garage
	if old then
		old:Destroy()
	end
	return model, true
end

-- After a stage change: a character standing where a solid box now is (a visitor in the old building's furniture band
-- when an IPO brings back the Garage) is moved to `landing` (a CFrame inside the room). roots = HumanoidRootParts.
-- The roof never counts: it is overhead, and a player under it in the middle of a jump is not trapped. Returns how many
-- were moved.
function PlotBuildingVisuals.unstick(model, roots, landing)
	local solid = model and model:FindFirstChild("Solid")
	local frame = model and model:GetAttribute("Frame")
	if not solid or typeof(frame) ~= "CFrame" then
		return 0
	end
	local boxes = {}
	for _, part in ipairs(solid:GetChildren()) do
		if part:IsA("BasePart") and part:GetAttribute("Piece") ~= "Roof" then
			table.insert(boxes, boxOf(frame:ToObjectSpace(part.CFrame), part.Size))
		end
	end
	local moved = 0
	for _, root in ipairs(roots) do
		local p = frame:PointToObjectSpace(root.Position)
		local body = { p.X - 1, p.X + 1, p.Y - 3, p.Y + 2, p.Z - 1, p.Z + 1 } -- a character around its root part
		for _, b in ipairs(boxes) do
			if overlaps(body, b, OVERLAP) then
				root.CFrame = landing
				moved += 1
				break
			end
		end
	end
	return moved
end

-- Checks -----------------------------------------------------------------------------------------------------------

-- Problems of ReplicatedStorage.KitModels against the manifest (empty list = fine): every key a Model, KitSize within
-- 0.05 of the manifest's size, its MeshParts' roles exactly the manifest's (one MeshPart per role), its WorldPivot the
-- bottom-center of its MeshParts (within 0.05: the builder stands every piece on it), nothing but MeshParts in it.
function PlotBuildingVisuals.checkKit(folder, manifest)
	local problems = {}
	local function problem(text)
		table.insert(problems, text)
	end
	if not folder then
		problem("ReplicatedStorage.KitModels is missing")
		return problems
	end
	local keys = {}
	for key in pairs(manifest) do
		table.insert(keys, key)
	end
	table.sort(keys)
	for _, key in ipairs(keys) do
		local entry = manifest[key]
		local model = folder:FindFirstChild(key)
		if not model then
			problem(key .. ": missing")
		elseif not model:IsA("Model") then
			problem(key .. ": is a " .. model.ClassName .. ", not a Model")
		else
			local size = model:GetAttribute("KitSize")
			if typeof(size) ~= "Vector3" then
				problem(key .. ": no KitSize attribute")
			else
				local want = entry.size
				local dx, dy, dz = math.abs(size.X - want[1]), math.abs(size.Y - want[2]), math.abs(size.Z - want[3])
				if dx > 0.05 or dy > 0.05 or dz > 0.05 then
					problem(string.format("%s: KitSize %.2f x %.2f x %.2f, want %g x %g x %g (W x H x D)", key, size.X, size.Y, size.Z, want[1], want[2], want[3]))
				end
			end
			local seen, other = {}, {}
			local pivot = model.WorldPivot
			local bounds = { math.huge, -math.huge, math.huge, -math.huge, math.huge, -math.huge }
			for _, d in ipairs(model:GetDescendants()) do
				if d:IsA("MeshPart") then
					local role = d:GetAttribute("Role")
					if type(role) ~= "string" then
						problem(key .. "." .. d.Name .. ": no Role attribute")
					elseif not entry.roles[role] then
						problem(key .. "." .. d.Name .. ": role " .. role .. " is not in the manifest")
					elseif seen[role] then
						problem(key .. "." .. d.Name .. ": a second MeshPart with role " .. role .. " (one per role)")
					else
						seen[role] = true
					end
					local b = boxOf(pivot:ToObjectSpace(d.CFrame), d.Size)
					for k = 1, 5, 2 do
						bounds[k] = math.min(bounds[k], b[k])
						bounds[k + 1] = math.max(bounds[k + 1], b[k + 1])
					end
				else
					table.insert(other, d.ClassName .. " " .. d.Name)
				end
			end
			for role in pairs(entry.roles) do
				if not seen[role] then
					problem(key .. ": no MeshPart with role " .. role)
				end
			end
			if #other > 0 then
				problem(key .. ": not only MeshParts (" .. table.concat(other, ", ") .. "; the game leaves them out)")
			end
			if bounds[1] <= bounds[2] then
				local cx, cz, bottom = (bounds[1] + bounds[2]) / 2, (bounds[5] + bounds[6]) / 2, bounds[3]
				if math.abs(cx) > PIVOT_EPS or math.abs(bottom) > PIVOT_EPS or math.abs(cz) > PIVOT_EPS then
					problem(string.format("%s: WorldPivot is not the bottom-center of its parts (the parts' bottom-center is at %.2f, %.2f, %.2f from it)",
						key, cx, bottom, cz))
				end
			end
		end
	end
	for _, child in ipairs(folder:GetChildren()) do
		if not manifest[child.Name] then
			problem(child.Name .. ": not in the manifest (unused)")
		end
	end
	return problems
end

-- Problems of a built building (empty list = fine), measured in the garage's frame. opts (all optional): zones =
-- PlotVisuals.zones(PlotArt.Layout) (no part in a reserved zone), roomBoxes = { { name, box } } of the room built in the
-- same garage, in the frame of the Floor's top (no part goes into a room part, except flat marks on the ground).
function PlotBuildingVisuals.check(model, frame, building, opts)
	opts = opts or {}
	local problems = {}
	local function problem(text)
		table.insert(problems, text)
	end
	local origin = originOf(frame, building)
	local layout = building.layout(model:GetAttribute("Stage"))
	local lot, lane, post, landing = building.Lot, building.Lane, building.ClaimPost, building.Landing
	local laneBox = { -lane.half, lane.half, building.GROUND, lane.top, lane.from, lane.to }
	local postBox = { post.x0, post.x1, building.GROUND, post.top, post.z0, post.z1 }
	local landBox = { landing.x - landing.half, landing.x + landing.half, 0, landing.top, landing.z - landing.half, landing.z + landing.half }
	local edge = building.ROOM_EDGE
	local laneKeys = {}
	for _, piece in ipairs(layout.pieces) do
		if piece.lane then
			laneKeys[piece.name] = true
		end
	end
	local parts, lights = {}, 0
	for _, d in ipairs(model:GetDescendants()) do
		if d:IsA("ParticleEmitter") then
			lights += 1000 -- never: an emitter is not a light
		elseif d:IsA("Light") then
			lights += 1
			if d.Parent == nil or d.Parent:GetAttribute("Piece") ~= "M1Roof" or d.Parent.Parent ~= model:FindFirstChild("Fade") then
				problem(d.Name .. ": a light anywhere but on the roof piece (the ceiling light)")
			end
		elseif d:IsA("BasePart") then
			table.insert(parts, d)
		end
	end
	if #parts > building.Budget.parts then
		problem(string.format("%d parts (budget %d)", #parts, building.Budget.parts))
	end
	if lights > building.Budget.lights then
		problem(lights .. " lights or emitters (a building has at most " .. building.Budget.lights .. ": its ceiling light)")
	end
	local solids = 0
	for _, part in ipairs(parts) do
		local name = part.Name
		local group = part.Parent and part.Parent.Name
		local b = boxOf(origin:ToObjectSpace(part.CFrame), part.Size)
		local flat = b[4] - b[3] <= 0.25
		if not PlotBuildingVisuals.GROUPS[group] or part.Parent.Parent ~= model then
			problem(name .. ": not in Fade, Static or Solid")
		end
		if not part.Anchored then
			problem(name .. ": not anchored")
		end
		if group == "Solid" then
			solids += 1
			if not part.CanCollide or part.CanTouch or part.Transparency < 1 then
				problem(name .. ": a solid box must be CanCollide on, CanTouch off, Transparency 1")
			end
			if overlaps(b, laneBox, OVERLAP) then
				problem(name .. ": a solid box in the doorway lane")
			end
			-- over the 60 x 60 floor only well above a jumping player's head (the roof)
			if b[1] < edge - OVERLAP and b[2] > -edge + OVERLAP and b[5] < edge - OVERLAP and b[6] > -edge + OVERLAP and b[3] < building.CLEAR_ABOVE then
				problem(name .. ": a solid box over the floor, lower than " .. building.CLEAR_ABOVE)
			end
		else
			if part.CanCollide or part.CanTouch or part.CanQuery then
				problem(name .. ": CanCollide, CanTouch and CanQuery must all be off")
			end
			if part.CastShadow then
				problem(name .. ": casts a shadow")
			end
			if not building.MATERIALS[part.Material.Name] then
				problem(name .. ": material not allowed: " .. part.Material.Name)
			elseif part.Material.Name == "Neon" and not building.NEON_KEYS[part:GetAttribute("Key")] then
				problem(name .. ": Neon on something that isn't a light")
			end
			if not flat and overlaps(b, laneBox, OVERLAP) and not laneKeys[part:GetAttribute("Piece")] then
				problem(name .. ": in the doorway lane")
			end
		end
		if overlaps(b, postBox, OVERLAP) then
			problem(name .. ": on the claim post's spot")
		end
		if overlaps(b, landBox, OVERLAP) then
			problem(name .. ": on the landing spot")
		end
		-- the lot; only the shell's pieces in front of the facade (plants, columns, the door leaf) may reach OUTSIDE_TO
		local limit = group == "Fade" and building.OUTSIDE_TO or lot.front
		if b[1] < -lot.half - OVERLAP or b[2] > lot.half + OVERLAP or b[5] < lot.back - OVERLAP or b[6] > limit + OVERLAP then
			problem(name .. ": outside the lot")
		end
		for _, zone in ipairs(opts.zones or {}) do
			if overlaps(b, zone.box, OVERLAP) then
				problem(name .. " is inside " .. zone.kind .. " zone " .. zone.name)
			end
		end
		for _, room in ipairs(opts.roomBoxes or {}) do
			local rb = room.box
			local mark = rb[4] - rb[3] <= 0.25 and rb[3] <= building.GROUND + 0.3 -- a flat mark on the ground (stage 1's yard)
			if not mark and overlaps(b, rb, OVERLAP) then
				problem(name .. " goes into the room part " .. room.name)
			end
		end
	end
	if solids ~= #layout.boxes then
		problem(string.format("%d solid parts, the layout has %d boxes", solids, #layout.boxes))
	end
	return problems
end

return PlotBuildingVisuals
