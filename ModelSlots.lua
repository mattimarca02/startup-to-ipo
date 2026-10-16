-- ModelSlots: puts a ready-made model into a building slot, or says why not (branch lobby-all).
-- Put this ModuleScript in ServerScriptService, next to PlotBuildingVisuals (which calls it) and PlotBuilding (the data).
-- docs/MODEL_ASSETS_PLAN.md is the plan: the slots, the budgets, the owner's checklist and how to add a model.
--
-- A slot is one piece of a building (a wall panel, a window, a desk...). The owner may put a model for it in
-- ReplicatedStorage.BuildingModels.<Building>.<Slot>. This module only READS that template: it never changes, moves
-- or deletes it (except scrubTemplates at server start, which deletes scripts inside the folder). For each placement it:
--   1. checks the template (a Model, Checked = true, Triangles a whole number under the piece's cap, 1 to 12 parts);
--   2. clones it and DELETES from the copy everything whose class is not on the allow-list (scripts first);
--   3. makes every part anchored and never solid, never touched, never hit by a ray (solid slots keep their own
--      collider from the Parts version: PlotBuildingVisuals does that);
--   4. scales it to the slot's box (one factor, or each axis for "stretch" slots) and puts its bottom-center on the
--      slot's bottom-center, its front (the pivot's LookVector) to the slot's front (+Z);
-- and refuses (nil and a reason) when anything is off. The caller then builds the Parts version: nothing is ever
-- missing because a model is missing or wrong. No asset ID is ever written here.
--
-- No services, no require: the folder and the slot are passed in, so it also runs in the tests' fake Roblox.
--   ModelSlots.find(root, buildingKey, slotName)          -> the template Model, or nil
--   ModelSlots.checkTemplate(template, cap)               -> triangles, or nil and the reason
--   ModelSlots.clean(model)                               -> list of what was deleted ("Script Foo", ...)
--   ModelSlots.fit(template, box, fitMode, cap, cframe)   -> model (not parented), triangles, deleted list; or nil, reason
--   ModelSlots.scrubTemplates(root)                       -> list of scripts deleted from the templates (server start)

local ModelSlots = {}

ModelSlots.FOLDER = "BuildingModels" -- ReplicatedStorage.BuildingModels.<Building>.<Slot>
-- What a model may keep. Everything else in a copy is deleted before the copy goes anywhere.
ModelSlots.ALLOWED = {
	Model = true, Folder = true, Part = true, MeshPart = true, WedgePart = true, CornerWedgePart = true,
	UnionOperation = true, SpecialMesh = true, SurfaceAppearance = true, Texture = true, Decal = true,
}
ModelSlots.PART_CLASSES = { Part = true, MeshPart = true, WedgePart = true, CornerWedgePart = true, UnionOperation = true }
ModelSlots.SCRIPT_CLASSES = { Script = true, LocalScript = true, ModuleScript = true }
ModelSlots.MAX_PARTS_PER_PIECE = 12
ModelSlots.MIN_FILL = 0.8 -- a uniform fit must fill this share of the box's width and height
ModelSlots.MIN_SCALE = 0.25
ModelSlots.MAX_SCALE = 4
ModelSlots.TINY = 2 -- a part whose longest side is shorter than this casts no shadow

local EPS = 1e-6

local function finite(n)
	return type(n) == "number" and n == n and n ~= math.huge and n ~= -math.huge
end

local function isPart(instance)
	return ModelSlots.PART_CLASSES[instance.ClassName] == true
end

-- The template for one slot of one building, or nil (no folder, no building folder, no such slot, or not a Model)
function ModelSlots.find(root, buildingKey, slotName)
	if not root or type(buildingKey) ~= "string" or type(slotName) ~= "string" then
		return nil
	end
	local building = root:FindFirstChild(buildingKey)
	local template = building and building:FindFirstChild(slotName)
	if template and template.ClassName == "Model" then
		return template
	end
	return nil
end

-- Is the template usable at all? Returns its triangle count, or nil and the reason (shown by the Debug button).
function ModelSlots.checkTemplate(template, cap)
	if not template or template.ClassName ~= "Model" then
		return nil, "not a Model"
	end
	if template:GetAttribute("Checked") ~= true then
		return nil, "Checked is not true (do the checklist, docs/MODEL_ASSETS_PLAN.md section 4)"
	end
	local triangles = template:GetAttribute("Triangles")
	if not finite(triangles) or triangles % 1 ~= 0 or triangles < 1 then
		return nil, "Triangles is missing or not a whole number above 0"
	end
	if finite(cap) and triangles > cap then
		return nil, string.format("%d triangles (this piece allows %d)", triangles, cap)
	end
	local parts = 0
	for _, d in ipairs(template:GetDescendants()) do
		if isPart(d) then
			parts += 1
		end
	end
	if parts == 0 then
		return nil, "no part in it"
	end
	if parts > ModelSlots.MAX_PARTS_PER_PIECE then
		return nil, string.format("%d parts (a piece allows %d)", parts, ModelSlots.MAX_PARTS_PER_PIECE)
	end
	return triangles
end

-- Deletes every descendant whose class is not allowed (scripts, sounds, lights, GUIs, welds, values, anything
-- unknown), outermost first. Returns what it deleted, as "Class Name" strings.
function ModelSlots.clean(model)
	local deleted = {}
	local function walk(node)
		for _, child in ipairs(node:GetChildren()) do
			if ModelSlots.ALLOWED[child.ClassName] then
				walk(child)
			else
				table.insert(deleted, child.ClassName .. " " .. tostring(child.Name))
				child:Destroy()
			end
		end
	end
	walk(model)
	return deleted
end

-- Every part of a copy: anchored, never solid, never touched, never hit by a ray; tiny parts cast no shadow
local function settle(model)
	for _, d in ipairs(model:GetDescendants()) do
		if isPart(d) then
			d.Anchored = true
			d.CanCollide = false
			d.CanTouch = false
			d.CanQuery = false
			local s = d.Size
			if math.max(s.X, s.Y, s.Z) < ModelSlots.TINY then
				d.CastShadow = false
			end
		end
	end
end

-- The model's own frame with its front on +Z (Roblox's front, the LookVector, is -Z: turned half a turn)
local HALF_TURN = CFrame.fromEulerAnglesYXZ(0, math.pi, 0)

local function modelFrame(model)
	local pivot = model:GetPivot()
	return pivot * HALF_TURN
end

-- The box around every part, in a frame: { minX, maxX, minY, maxY, minZ, maxZ }
local function extents(parts, frame)
	local box = { math.huge, -math.huge, math.huge, -math.huge, math.huge, -math.huge }
	for _, p in ipairs(parts) do
		local rel = frame:ToObjectSpace(p.CFrame)
		local x, y, z, r00, r01, r02, r10, r11, r12, r20, r21, r22 = rel:GetComponents()
		local s = p.Size
		local hx = (math.abs(r00) * s.X + math.abs(r01) * s.Y + math.abs(r02) * s.Z) / 2
		local hy = (math.abs(r10) * s.X + math.abs(r11) * s.Y + math.abs(r12) * s.Z) / 2
		local hz = (math.abs(r20) * s.X + math.abs(r21) * s.Y + math.abs(r22) * s.Z) / 2
		box[1], box[2] = math.min(box[1], x - hx), math.max(box[2], x + hx)
		box[3], box[4] = math.min(box[3], y - hy), math.max(box[4], y + hy)
		box[5], box[6] = math.min(box[5], z - hz), math.max(box[6], z + hz)
	end
	return box
end
ModelSlots.extents = extents

-- Is a rotation only quarter turns (every entry -1, 0 or 1)? Then a stretch keeps every part a box on the axes.
local function quarterOnly(rel)
	local _, _, _, r00, r01, r02, r10, r11, r12, r20, r21, r22 = rel:GetComponents()
	for _, v in ipairs({ r00, r01, r02, r10, r11, r12, r20, r21, r22 }) do
		local a = math.abs(v)
		if a > EPS and math.abs(a - 1) > EPS then
			return false
		end
	end
	return true
end

-- Puts a clean copy into the box. box = { w, h, d } (studs), fitMode = "uniform" or "stretch",
-- cframe = the slot's bottom-center in the world, front on its +Z. Returns the model (not parented) or nil, reason.
local function place(model, parts, box, fitMode, cframe)
	local frame = modelFrame(model)
	local e = extents(parts, frame)
	local size = { e[2] - e[1], e[4] - e[3], e[6] - e[5] }
	for i = 1, 3 do
		if not (finite(size[i]) and size[i] > EPS) then
			return nil, "a side of it is 0 studs"
		end
	end
	local k = { box[1] / size[1], box[2] / size[2], box[3] / size[3] }
	if fitMode ~= "stretch" then
		local u = math.min(k[1], k[2], k[3])
		if u < ModelSlots.MIN_SCALE or u > ModelSlots.MAX_SCALE then
			return nil, string.format("it would need a scale of %.2f (allowed %.2f to %.2f)", u, ModelSlots.MIN_SCALE, ModelSlots.MAX_SCALE)
		end
		if size[1] * u < box[1] * ModelSlots.MIN_FILL - EPS or size[2] * u < box[2] * ModelSlots.MIN_FILL - EPS then
			return nil, string.format("its shape does not fit the %gx%gx%g box (it would fill less than %d%%)", box[1], box[2], box[3], ModelSlots.MIN_FILL * 100)
		end
		k = { u, u, u }
	else
		for i = 1, 3 do
			if k[i] < ModelSlots.MIN_SCALE or k[i] > ModelSlots.MAX_SCALE then
				return nil, string.format("it would need a scale of %.2f on one side (allowed %.2f to %.2f)", k[i], ModelSlots.MIN_SCALE, ModelSlots.MAX_SCALE)
			end
		end
	end
	local bottom = Vector3.new((e[1] + e[2]) / 2, e[3], (e[5] + e[6]) / 2) -- bottom-center, in the model's frame
	local moves = {}
	for _, p in ipairs(parts) do
		local rel = frame:ToObjectSpace(p.CFrame)
		if fitMode == "stretch" and not quarterOnly(rel) then
			return nil, "a part of it is turned at an angle (a stretched slot needs quarter turns only)"
		end
		local pos = rel.Position - bottom
		local _, _, _, r00, r01, r02, r10, r11, r12, r20, r21, r22 = rel:GetComponents()
		local turn = CFrame.new(0, 0, 0, r00, r01, r02, r10, r11, r12, r20, r21, r22)
		-- The part's own size, scaled along the model axis each of its sides lies on
		local s = p.Size
		local sx = s.X * (math.abs(r00) * k[1] + math.abs(r10) * k[2] + math.abs(r20) * k[3])
		local sy = s.Y * (math.abs(r01) * k[1] + math.abs(r11) * k[2] + math.abs(r21) * k[3])
		local sz = s.Z * (math.abs(r02) * k[1] + math.abs(r12) * k[2] + math.abs(r22) * k[3])
		-- (a SpecialMesh scales with its part, side by side, in the part's own axes)
		table.insert(moves, { part = p, cframe = cframe * CFrame.new(pos.X * k[1], pos.Y * k[2], pos.Z * k[3]) * turn,
			size = Vector3.new(sx, sy, sz), ratio = { sx / s.X, sy / s.Y, sz / s.Z } })
	end
	for _, m in ipairs(moves) do
		m.part.Size = m.size
		m.part.CFrame = m.cframe
		for _, child in ipairs(m.part:GetChildren()) do
			if child.ClassName == "SpecialMesh" then
				local sc = child.Scale
				child.Scale = Vector3.new(sc.X * m.ratio[1], sc.Y * m.ratio[2], sc.Z * m.ratio[3])
			end
		end
	end
	return model
end

-- A ready copy of the template in the slot's box, or nil and the reason. Returns model, triangles, deleted.
function ModelSlots.fit(template, box, fitMode, cap, cframe)
	local triangles, why = ModelSlots.checkTemplate(template, cap)
	if not triangles then
		return nil, why
	end
	if type(box) ~= "table" or not (finite(box[1]) and finite(box[2]) and finite(box[3])) or box[1] <= 0 or box[2] <= 0 or box[3] <= 0 then
		return nil, "the slot has no box"
	end
	local copy = template:Clone()
	local deleted = ModelSlots.clean(copy)
	local parts = {}
	for _, d in ipairs(copy:GetDescendants()) do
		if isPart(d) then
			table.insert(parts, d)
		end
	end
	if #parts == 0 then
		copy:Destroy()
		return nil, "no part left after cleaning"
	end
	settle(copy)
	local placed, reason = place(copy, parts, box, fitMode, cframe)
	if not placed then
		copy:Destroy()
		return nil, reason
	end
	copy:SetAttribute("Checked", nil)
	copy:SetAttribute("Triangles", nil)
	return placed, triangles, deleted
end

-- At server start: deletes every script inside the templates (a Script with RunContext Client could run on its own)
-- and clears that template's Checked, so it is refused until the owner checks a clean one again. Returns the list.
function ModelSlots.scrubTemplates(root)
	local deleted = {}
	if not root then
		return deleted
	end
	for _, building in ipairs(root:GetChildren()) do
		for _, template in ipairs(building:GetChildren()) do
			local found = false
			for _, d in ipairs(template:GetDescendants()) do
				if ModelSlots.SCRIPT_CLASSES[d.ClassName] then
					table.insert(deleted, building.Name .. "." .. template.Name .. ": " .. d.ClassName .. " " .. tostring(d.Name))
					d:Destroy()
					found = true
				end
			end
			if found then
				template:SetAttribute("Checked", false)
			end
		end
	end
	return deleted
end

return ModelSlots
