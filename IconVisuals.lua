-- IconVisuals: builds the icons of IconArt (branch world-icons-pass) and checks them. Put this ModuleScript in
-- ReplicatedStorage, next to IconArt. Client-side looks only: an icon is a Frame of UI shapes, or a ViewportFrame
-- showing a small model (an Office prop, or a creature from CreatureModels). No image, no asset, no emoji, no text but
-- IconArt.Texts, no remote, nothing saved. Nothing moves unless the player taps an icon.
--
-- No GetService and no require: the art and the creature modules are passed in (deps = { CreatureModels = ...,
-- CreatureConfig = ... }), so the same code runs in the game, in Studio's command bar and in tools/icon_test.py.
--   IconVisuals.build(parent, art, group, key, size, deps)  -> Frame "Icon" (group: Office, Eggs, Creatures, Shop, Hud)
--   IconVisuals.newCache(art, deps, cap) / IconVisuals.show(cache, slots)
--       lazy icons for a scrolling list: show() gets the card slots that are on screen now and builds only those,
--       keeps them for later, and never lets more than `cap` 3D icons (ViewportFrames) exist at once
--   IconVisuals.tap(icon)                                   -> the one animation: a spin (3D) or a pop (UI)
-- Pure functions (numbers in, numbers out):
--   pixels(art, role), outlinePx(art, size), shapeBox(art, shape), frame(box, view, fov, padding),
--   plan(liveUsed, wanted, cap), spinAngle(t, seconds), popScale(t, seconds)
-- Checks (tools/icon_test.py and the Studio preview run them):
--   IconVisuals.validate(art)                     -> problems in the data (empty = fine)
--   IconVisuals.checks(art, icons, expect)        -> { { name = ..., problems = { ... } }, ... }, one per named check

local IconVisuals = {}

IconVisuals.GROUPS = { "Office", "Eggs", "Creatures", "Shop", "Hud" }
IconVisuals.KINDS = { ui = true, model = true, creature = true }
IconVisuals.SHAPES = { rect = true, circle = true, pill = true, diamond = true, ring = true, frame = true, text = true }
IconVisuals.MATERIALS = {
	Concrete = true, CorrodedMetal = true, Metal = true, DiamondPlate = true, Wood = true, WoodPlanks = true, Brick = true,
	Fabric = true, Plastic = true, SmoothPlastic = true, Glass = true, Neon = true,
}
IconVisuals.PART_SHAPES = { Block = true, Cylinder = true, Ball = true }
IconVisuals.CHECKS = { "data", "coverage", "palette", "assets", "texts", "style", "framing", "budget", "grid" }
IconVisuals.FORBIDDEN_CLASSES = {
	ImageLabel = true, ImageButton = true, Decal = true, Texture = true, MeshPart = true, SurfaceAppearance = true, VideoFrame = true,
	Script = true, LocalScript = true, ModuleScript = true, Sound = true, ParticleEmitter = true, ClickDetector = true,
	ProximityPrompt = true, SurfaceGui = true, BillboardGui = true, PointLight = true, SpotLight = true, SurfaceLight = true,
}
IconVisuals.SPIN_SECONDS = 1.2
IconVisuals.POP_SECONDS = 0.3

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

-- A palette color by name; a name the palette doesn't have is bright magenta (the palette check names it)
local function colorOf(art, key)
	local c = art.Palette[key]
	if colorOk(c) then
		return Color3.fromRGB(c[1], c[2], c[3])
	end
	return Color3.fromRGB(255, 0, 255)
end

local function turn(r)
	if not r then
		return CFrame.new()
	end
	return CFrame.fromEulerAnglesYXZ(math.rad(r[1]), math.rad(r[2]), math.rad(r[3]))
end

local function boxOf(cframe, size)
	local x, y, z, r00, r01, r02, r10, r11, r12, r20, r21, r22 = cframe:GetComponents()
	local hx = (math.abs(r00) * size.X + math.abs(r01) * size.Y + math.abs(r02) * size.Z) / 2
	local hy = (math.abs(r10) * size.X + math.abs(r11) * size.Y + math.abs(r12) * size.Z) / 2
	local hz = (math.abs(r20) * size.X + math.abs(r21) * size.Y + math.abs(r22) * size.Z) / 2
	return { x - hx, x + hx, y - hy, y + hy, z - hz, z + hz }
end
IconVisuals.boxOf = boxOf

local function hasText(name)
	return type(name) == "string" and name ~= ""
end

-- Pure functions ---------------------------------------------------------------------

-- Pixels of an icon at phone size: "card" (56) or "hero" (72)
function IconVisuals.pixels(art, role)
	return art.Style.sizes[role] or art.Style.sizes.card
end

-- The outline's width in pixels on an icon of `size` pixels (at least 1)
function IconVisuals.outlinePx(art, size)
	return math.max(1, math.floor(size * art.Style.outline / art.Style.grid + 0.5))
end

-- A UI shape's box on the grid once turned, with its outline: { x0, x1, y0, y1 }
function IconVisuals.shapeBox(art, shape)
	local cx, cy = shape.x + shape.w / 2, shape.y + shape.h / 2
	local w, h = shape.w, shape.h
	local angle = math.rad((shape.kind == "diamond" and 45 or 0) + (shape.rotation or 0))
	local c, s = math.abs(math.cos(angle)), math.abs(math.sin(angle))
	local hx, hy = (w * c + h * s) / 2, (w * s + h * c) / 2
	if shape.kind == "circle" or shape.kind == "ring" then
		hx, hy = w / 2, h / 2 -- a circle is the same however it is turned
	end
	local grow = 0
	if shape.outline then
		grow = art.Style.outline
	end
	if shape.kind == "ring" or shape.kind == "frame" then
		grow = math.max(grow, (shape.thickness or 0) / 2 + (shape.outline and art.Style.outline or 0))
	end
	return { cx - hx - grow, cx + hx + grow, cy - hy - grow, cy + hy + grow }
end

local function sub(a, b) return { a[1] - b[1], a[2] - b[2], a[3] - b[3] } end
local function dot(a, b) return a[1] * b[1] + a[2] * b[2] + a[3] * b[3] end
local function cross(a, b) return { a[2] * b[3] - a[3] * b[2], a[3] * b[1] - a[1] * b[3], a[1] * b[2] - a[2] * b[1] } end
local function unit(a)
	local m = math.sqrt(dot(a, a))
	return { a[1] / m, a[2] / m, a[3] / m }
end

-- The camera of a 3D icon: it looks at the middle of the model's box from the view's direction (yaw around Y, 0 = from
-- +Z; pitch up from level), as close as it can while every corner of the box stays inside the square picture with
-- `padding` (a share of the picture) to spare. box = { minX, maxX, minY, maxY, minZ, maxZ }, fov in degrees.
-- Returns { eye = { x, y, z }, target = { x, y, z }, distance, right, up, back } (unit vectors of the camera).
function IconVisuals.frame(box, view, fov, padding)
	local center = { (box[1] + box[2]) / 2, (box[3] + box[4]) / 2, (box[5] + box[6]) / 2 }
	local yaw, pitch = math.rad(view.yaw), math.rad(view.pitch)
	local back = { math.sin(yaw) * math.cos(pitch), math.sin(pitch), math.cos(yaw) * math.cos(pitch) } -- from the target to the eye
	local right = unit(cross({ 0, 1, 0 }, back))
	local up = cross(back, right)
	local t = math.tan(math.rad(fov) / 2) * (1 - padding)
	local need, nearest = 0, -math.huge
	for _, x in ipairs({ box[1], box[2] }) do
		for _, y in ipairs({ box[3], box[4] }) do
			for _, z in ipairs({ box[5], box[6] }) do
				local rel = sub({ x, y, z }, center)
				local rx, ry, rz = dot(rel, right), dot(rel, up), dot(rel, back)
				need = math.max(need, rz + math.abs(rx) / t, rz + math.abs(ry) / t)
				nearest = math.max(nearest, rz)
			end
		end
	end
	need = math.max(need, nearest + 0.1)
	return {
		eye = { center[1] + back[1] * need, center[2] + back[2] * need, center[3] + back[3] * need },
		target = center, distance = need, right = right, up = up, back = back,
	}
end

-- Which 3D icons to build and which to drop. liveUsed: { [key] = when it was last on screen } for the ViewportFrames
-- that exist; wanted: the keys on screen now, most important first. Never more than `cap` exist: an icon that left the
-- screen is dropped (least recently seen first, then the lowest key) to make room; when every live icon is still on
-- screen, the rest wait (their slot shows the plate alone). Returns { make = {...}, drop = {...}, wait = {...} }.
function IconVisuals.plan(liveUsed, wanted, cap)
	local wantedSet, count = {}, 0
	for _, key in ipairs(wanted) do
		wantedSet[key] = true
	end
	local spare = {}
	for key, used in pairs(liveUsed) do
		count += 1
		if not wantedSet[key] then
			table.insert(spare, { key = key, used = used })
		end
	end
	table.sort(spare, function(a, b)
		if a.used ~= b.used then
			return a.used < b.used
		end
		return a.key < b.key
	end)
	local out, made = { make = {}, drop = {}, wait = {} }, {}
	for _, key in ipairs(wanted) do
		if liveUsed[key] == nil and not made[key] then
			if count < cap then
				count += 1
				made[key] = true
				table.insert(out.make, key)
			elseif #spare > 0 then
				table.insert(out.drop, table.remove(spare, 1).key)
				made[key] = true
				table.insert(out.make, key)
			else
				table.insert(out.wait, key)
			end
		end
	end
	return out
end

-- The tap animations, as pure functions of the time since the tap: a 3D icon turns once (eased), a UI icon pops
local function smooth(t)
	return t * t * (3 - 2 * t)
end
function IconVisuals.spinAngle(t, seconds)
	if not (finite(t) and finite(seconds)) or seconds <= 0 or t <= 0 then
		return 0
	end
	if t >= seconds then
		return 360
	end
	return 360 * smooth(t / seconds)
end
function IconVisuals.popScale(t, seconds)
	if not (finite(t) and finite(seconds)) or seconds <= 0 or t <= 0 or t >= seconds then
		return 1
	end
	return 1 + 0.12 * math.sin(math.pi * t / seconds)
end

-- Building ----------------------------------------------------------------------------

local function make(className, props)
	local inst = Instance.new(className)
	for key, value in pairs(props) do
		if key ~= "Parent" then
			inst[key] = value
		end
	end
	inst.Parent = props.Parent
	return inst
end

local function corner(parent, scale)
	make("UICorner", { CornerRadius = UDim.new(scale, 0), Parent = parent })
end

-- One shape (or its outline copy, grown by `grow` grid units, in the outline color)
local function drawShape(layer, art, shape, size, grow, z)
	local grid = art.Style.grid
	local x, y, w, h = shape.x - grow, shape.y - grow, shape.w + grow * 2, shape.h + grow * 2
	local outlineCopy = grow > 0
	local color = outlineCopy and colorOf(art, "outline") or colorOf(art, shape.color)
	local props = {
		Name = (outlineCopy and "Outline" or "") .. shape.name,
		AnchorPoint = Vector2.new(0.5, 0.5),
		Position = UDim2.fromScale((x + w / 2) / grid, (y + h / 2) / grid),
		Size = UDim2.fromScale(w / grid, h / grid),
		Rotation = (shape.kind == "diamond" and 45 or 0) + (shape.rotation or 0),
		BorderSizePixel = 0,
		ZIndex = z,
		Parent = layer,
	}
	local kind = shape.kind
	if kind == "text" and not outlineCopy then
		props.BackgroundTransparency = 1
		props.Text = shape.text
		props.Font = Enum.Font.FredokaOne
		props.TextScaled = true
		props.TextColor3 = color
		props.TextTransparency = shape.transparency or 0
		return make("TextLabel", props)
	end
	if kind == "ring" or kind == "frame" then
		props.BackgroundTransparency = 1
		local frame = make("Frame", props)
		corner(frame, kind == "ring" and 0.5 or art.Style.corner)
		local thickness = (shape.thickness or 1) + (outlineCopy and art.Style.outline * 2 or 0)
		make("UIStroke", {
			Name = "Line", Color = color, Thickness = math.max(1, size * thickness / grid),
			ApplyStrokeMode = Enum.ApplyStrokeMode.Border, Transparency = shape.transparency or 0, Parent = frame,
		})
		return frame
	end
	props.BackgroundColor3 = color
	props.BackgroundTransparency = outlineCopy and 0 or (shape.transparency or 0)
	local frame = make("Frame", props)
	if kind == "circle" or kind == "pill" then
		corner(frame, 0.5)
	elseif kind == "rect" then
		corner(frame, art.Style.corner)
	elseif kind == "diamond" then
		corner(frame, art.Style.corner * 0.6)
	end
	if shape.shade and not outlineCopy then
		local dark = art.Style.shadeDark
		make("UIGradient", {
			Name = "Shade", Rotation = art.Style.lightRotation,
			Color = ColorSequence.new(Color3.new(1, 1, 1), Color3.new(dark, dark, dark)), Parent = frame,
		})
	end
	return frame
end

-- The round plate a card icon sits on (with its outline)
local function drawPlate(root, art, plate, size)
	local p = art.Style.plate
	local shape = { kind = "circle", name = "Plate", x = p[1], y = p[2], w = p[3], h = p[4], color = plate, outline = true }
	drawShape(root, art, shape, size, art.Style.outline, 1)
	drawShape(root, art, shape, size, 0, 2)
end

-- A UI icon: every outline copy first, then the fills in order
function IconVisuals.buildUi(root, art, recipe, size)
	local layer = make("Frame", { Name = "Art", BackgroundTransparency = 1, Size = UDim2.fromScale(1, 1), ZIndex = 3, Parent = root })
	for i, shape in ipairs(recipe.shapes) do
		if shape.outline then
			drawShape(layer, art, shape, size, art.Style.outline, 3 + i)
		end
	end
	local base = 4 + #recipe.shapes
	for i, shape in ipairs(recipe.shapes) do
		drawShape(layer, art, shape, size, 0, base + i)
	end
	make("UIScale", { Name = "Pop", Scale = 1, Parent = root })
	return layer
end

-- The parts of a 3D model recipe, around the origin (a prop stands on y 0 and faces +Z)
local function buildParts(art, specs)
	local model = Instance.new("Model")
	for _, spec in ipairs(specs) do
		local part = Instance.new("Part")
		part.Name = spec.name
		part.Shape = Enum.PartType[spec.shape]
		part.Size = Vector3.new(spec.size[1], spec.size[2], spec.size[3])
		part.CFrame = CFrame.new(spec.offset[1], spec.offset[2], spec.offset[3]) * turn(spec.rot)
		part.Color = colorOf(art, spec.color)
		part.Material = Enum.Material[spec.material]
		part.Anchored = true
		part.CanCollide = false
		part.CanQuery = false
		part.CanTouch = false
		part.CastShadow = false
		part.TopSurface = Enum.SurfaceType.Smooth
		part.BottomSurface = Enum.SurfaceType.Smooth
		part.Parent = model
	end
	return model
end

-- The box around every part of a model: { minX, maxX, minY, maxY, minZ, maxZ }
function IconVisuals.modelBox(model)
	local b = { math.huge, -math.huge, math.huge, -math.huge, math.huge, -math.huge }
	for _, d in ipairs(model:GetDescendants()) do
		if d:IsA("BasePart") and d.Transparency < 1 then
			local p = boxOf(d.CFrame, d.Size)
			b = { math.min(b[1], p[1]), math.max(b[2], p[2]), math.min(b[3], p[3]), math.max(b[4], p[4]), math.min(b[5], p[5]), math.max(b[6], p[6]) }
		end
	end
	return b
end

-- A 3D icon: a ViewportFrame with its camera framed on the model, lit from the picture's top-left
function IconVisuals.buildModel(root, art, recipe, size, deps)
	local style = art.Style
	local model
	if recipe.kind == "creature" then
		local config = deps and deps.CreatureConfig
		local models = deps and deps.CreatureModels
		local creature = config and config.getCreature(recipe.creature)
		if not (creature and models) then
			return nil
		end
		model = models.build(creature)
	else
		model = buildParts(art, art.Models[recipe.model])
	end
	model.Name = "Model"
	local view = make("ViewportFrame", {
		Name = "View", BackgroundTransparency = 1, Size = UDim2.fromScale(1, 1), ZIndex = 3,
		Ambient = Color3.fromRGB(style.ambient[1], style.ambient[2], style.ambient[3]),
		LightColor = Color3.fromRGB(style.lightColor[1], style.lightColor[2], style.lightColor[3]), Parent = root,
	})
	local camera = make("Camera", { Name = "Camera", FieldOfView = style.fov, Parent = view })
	view.CurrentCamera = camera
	local box = IconVisuals.modelBox(model)
	local shot = IconVisuals.frame(box, recipe.view, style.fov, style.padding)
	camera.CFrame = CFrame.lookAt(Vector3.new(shot.eye[1], shot.eye[2], shot.eye[3]), Vector3.new(shot.target[1], shot.target[2], shot.target[3]))
	local d = style.lightDirection
	view.LightDirection = camera.CFrame:VectorToWorldSpace(Vector3.new(d[1], d[2], d[3]).Unit)
	if not model.PrimaryPart then
		model.WorldPivot = CFrame.new(shot.target[1], shot.target[2], shot.target[3])
	end
	model.Parent = view
	return view
end

-- One icon, in a Frame named Icon that fills its parent (a card's icon slot). size = the slot's pixels (56 or 72 at
-- phone size): it only sets the line widths, everything else scales with the slot.
function IconVisuals.build(parent, art, group, key, size, deps)
	local recipe = art[group] and art[group][key]
	if not recipe then
		return nil
	end
	local root = make("Frame", { Name = "Icon", BackgroundTransparency = 1, Size = UDim2.fromScale(1, 1) })
	root:SetAttribute("Group", group)
	root:SetAttribute("Key", key)
	root:SetAttribute("Kind", recipe.kind)
	root:SetAttribute("Recipe", recipe.name)
	make("UIAspectRatioConstraint", { AspectRatio = 1, Parent = root })
	if recipe.plate then
		drawPlate(root, art, recipe.plate, size)
	end
	if recipe.kind == "ui" then
		IconVisuals.buildUi(root, art, recipe, size)
	else
		IconVisuals.buildModel(root, art, recipe, size, deps)
	end
	root.Parent = parent
	return root
end

-- The lazy cache -------------------------------------------------------------------------

function IconVisuals.newCache(art, deps, cap)
	return { art = art, deps = deps, cap = cap or art.Style.viewportCap, clock = 0, serial = 0, ids = {}, ui = {}, live = {}, built = 0 }
end

-- slots: the card slots on screen now, most important first: { frame = <the slot Frame>, group = "Office", key = "Desk",
-- size = 56 }. Builds only what these need, puts each icon in its slot, keeps icons that left the screen (out of the
-- game tree) for later, and never lets more than cache.cap 3D icons exist: past it a slot shows its plate until a 3D
-- icon that left the screen can be dropped. Returns the number of 3D icons that exist.
function IconVisuals.show(cache, slots)
	cache.clock += 1
	local art = cache.art
	local wanted, slotOf, seen = {}, {}, {}
	for _, slot in ipairs(slots) do
		local recipe = art[slot.group] and art[slot.group][slot.key]
		local id = cache.ids[slot.frame]
		if not id then
			cache.serial += 1
			id = cache.serial
			cache.ids[slot.frame] = id
		end
		seen[id] = true
		local what = slot.group .. "/" .. tostring(slot.key)
		if recipe and recipe.kind == "ui" then
			local entry = cache.ui[id]
			if entry and entry.what ~= what then
				entry.icon:Destroy()
				entry = nil
			end
			if not entry then
				entry = { what = what, icon = IconVisuals.build(nil, art, slot.group, slot.key, slot.size or IconVisuals.pixels(art, "card"), cache.deps) }
				cache.ui[id] = entry
				cache.built += 1
			end
			entry.icon.Parent = slot.frame
		elseif recipe then
			local entry = cache.live[id]
			if entry and entry.what ~= what then -- the slot now shows another item
				entry.icon:Destroy()
				cache.live[id] = nil
			end
			table.insert(wanted, id)
			slotOf[id] = { slot = slot, what = what }
		end
	end
	local liveUsed = {}
	for id, entry in pairs(cache.live) do
		liveUsed[id] = entry.used
	end
	local todo = IconVisuals.plan(liveUsed, wanted, cache.cap)
	for _, id in ipairs(todo.drop) do
		cache.live[id].icon:Destroy()
		cache.live[id] = nil
	end
	for _, id in ipairs(todo.make) do
		local s = slotOf[id]
		cache.live[id] = { what = s.what, used = cache.clock,
			icon = IconVisuals.build(nil, art, s.slot.group, s.slot.key, s.slot.size or IconVisuals.pixels(art, "card"), cache.deps) }
		cache.built += 1
	end
	local waiting = {}
	for _, id in ipairs(todo.wait) do
		waiting[id] = true
	end
	local count = 0
	for id, entry in pairs(cache.live) do
		count += 1
		if slotOf[id] then
			entry.used = cache.clock
			entry.icon.Parent = slotOf[id].slot.frame
		else
			entry.icon.Parent = nil -- off screen: a ViewportFrame out of the game tree draws nothing
		end
	end
	for id, entry in pairs(cache.ui) do
		if not seen[id] then
			entry.icon.Parent = nil
		end
	end
	for id in pairs(waiting) do
		local s = slotOf[id].slot
		local holder = s.frame:FindFirstChild("Waiting")
		if not holder then
			holder = make("Frame", { Name = "Waiting", BackgroundTransparency = 1, Size = UDim2.fromScale(1, 1), Parent = s.frame })
			drawPlate(holder, art, art[s.group][s.key].plate or "plateCream", s.size or IconVisuals.pixels(art, "card"))
		end
	end
	for _, slot in ipairs(slots) do
		local holder = slot.frame:FindFirstChild("Waiting")
		if holder and not waiting[cache.ids[slot.frame]] then
			holder:Destroy()
		end
	end
	return count
end

-- The one animation: a tap turns a 3D icon once around its middle, or pops a UI icon. Nothing moves otherwise.
function IconVisuals.tap(icon)
	if not icon or icon:GetAttribute("Moving") then
		return false
	end
	icon:SetAttribute("Moving", true)
	local view = icon:FindFirstChild("View")
	local model = view and view:FindFirstChild("Model")
	local pop = icon:FindFirstChild("Pop")
	local start = model and model:GetPivot()
	local seconds = model and IconVisuals.SPIN_SECONDS or IconVisuals.POP_SECONDS
	task.spawn(function()
		local began = os.clock()
		while icon.Parent do
			local t = os.clock() - began
			if model then
				model:PivotTo(start * CFrame.Angles(0, math.rad(IconVisuals.spinAngle(t, seconds)), 0))
			elseif pop then
				pop.Scale = IconVisuals.popScale(t, seconds)
			end
			if t >= seconds then
				break
			end
			task.wait()
		end
		if model then
			model:PivotTo(start)
		elseif pop then
			pop.Scale = 1
		end
		icon:SetAttribute("Moving", false)
	end)
	return true
end

-- Checks -------------------------------------------------------------------------------------------

function IconVisuals.validate(art)
	local problems = {}
	local function problem(text)
		table.insert(problems, text)
	end
	local palette = type(art.Palette) == "table" and art.Palette or {}
	if type(art.Palette) ~= "table" then
		problem("Palette: missing")
	end
	for key, c in pairs(palette) do
		if not colorOk(c) then
			problem("Palette." .. tostring(key) .. ": a color is 3 whole numbers 0-255")
		end
	end
	if not colorOk(palette.outline) then
		problem("Palette.outline: missing (every icon's outline)")
	end
	local style = art.Style
	if type(style) ~= "table" then
		problem("Style: missing")
		return problems
	end
	for _, key in ipairs({ "grid", "outline", "corner", "lightRotation", "shadeDark", "fov", "padding", "viewportCap", "maxParts", "maxShapes" }) do
		if not finite(style[key]) or style[key] < 0 then
			problem("Style." .. key .. ": a number 0 or above")
		end
	end
	if type(style.sizes) ~= "table" or not finite(style.sizes.card) or not finite(style.sizes.hero) then
		problem("Style.sizes: card and hero pixels")
	end
	if type(style.lightDirection) ~= "table" or #style.lightDirection ~= 3 then
		problem("Style.lightDirection: 3 numbers")
	end
	if not colorOk(style.ambient) or not colorOk(style.lightColor) then
		problem("Style: ambient and lightColor are colors")
	end
	local texts = {}
	for _, t in ipairs(art.Texts or {}) do
		if type(t) ~= "string" or t == "" or string.find(t, "[^ -~]") or #t > 3 then
			problem("Texts: short plain labels only (at most 3 letters, numbers or signs)")
		else
			texts[t] = true
		end
	end
	local names = {}
	for _, group in ipairs(IconVisuals.GROUPS) do
		local recipes = art[group]
		if type(recipes) ~= "table" then
			problem(group .. ": missing")
			continue
		end
		for key, recipe in pairs(recipes) do
			local where = group .. "." .. tostring(key)
			if type(recipe) ~= "table" then
				problem(where .. ": not a recipe")
				continue
			end
			if not hasText(recipe.name) or string.find(recipe.name, "[^%w]") then
				problem(where .. ": needs a name (letters and numbers)")
			elseif names[recipe.name] then
				problem(where .. ": the name " .. recipe.name .. " is used twice")
			else
				names[recipe.name] = true
			end
			if not IconVisuals.KINDS[recipe.kind] then
				problem(where .. ": unknown kind " .. tostring(recipe.kind))
			end
			if group == "Hud" then
				if recipe.plate ~= nil then
					problem(where .. ": a HUD icon has no plate (it sits on its button)")
				end
			elseif type(recipe.plate) ~= "string" or not palette[recipe.plate] then
				problem(where .. ": a card icon needs a plate color from the palette")
			end
			if recipe.kind == "ui" then
				local shapes = recipe.shapes
				if type(shapes) ~= "table" or #shapes == 0 then
					problem(where .. ": no shapes")
				else
					if #shapes > style.maxShapes then
						problem(string.format("%s: %d shapes (at most %d)", where, #shapes, style.maxShapes))
					end
					local shapeNames = {}
					for i, s in ipairs(shapes) do
						local at = where .. "[" .. i .. "]"
						if not hasText(s.name) then
							problem(at .. ": a shape without a name")
						elseif shapeNames[s.name] then
							problem(at .. ": two shapes named " .. s.name)
						else
							shapeNames[s.name] = true
						end
						if not IconVisuals.SHAPES[s.kind] then
							problem(at .. ": unknown shape kind " .. tostring(s.kind))
						end
						if not (finite(s.x) and finite(s.y) and finite(s.w) and finite(s.h)) or s.w <= 0 or s.h <= 0 then
							problem(at .. ": x, y, w, h are numbers, w and h above 0")
						elseif s.kind == "circle" and s.w ~= s.h then
							problem(at .. ": a circle needs w = h")
						end
						if type(s.color) ~= "string" or not palette[s.color] then
							problem(at .. ": color " .. tostring(s.color) .. " is not in the palette")
						end
						if s.kind == "text" then
							if not texts[s.text] then
								problem(at .. ": text must be one of IconArt.Texts")
							end
							if recipe.noText then
								problem(at .. ": this icon shows no text at all")
							end
						elseif s.text ~= nil then
							problem(at .. ": only a text shape has text")
						end
						if s.rotation ~= nil and not finite(s.rotation) then
							problem(at .. ": rotation is a number of degrees")
						end
						if s.transparency ~= nil and not (finite(s.transparency) and s.transparency >= 0 and s.transparency < 1) then
							problem(at .. ": transparency 0 to below 1")
						end
						if (s.kind == "ring" or s.kind == "frame") and not (finite(s.thickness) and s.thickness > 0) then
							problem(at .. ": a ring or a frame needs a thickness")
						end
					end
				end
			else
				local view = recipe.view
				if type(view) ~= "table" or not finite(view.yaw) or not finite(view.pitch) or math.abs(view.pitch) > 60 then
					problem(where .. ": a 3D icon needs a view (yaw, pitch within 60 degrees)")
				end
				if recipe.kind == "model" then
					local specs = type(art.Models) == "table" and art.Models[recipe.model]
					if type(specs) ~= "table" or #specs == 0 then
						problem(where .. ": no model " .. tostring(recipe.model) .. " in IconArt.Models")
					else
						if #specs > style.maxParts then
							problem(string.format("%s: %d parts (at most %d)", where, #specs, style.maxParts))
						end
						local partNames = {}
						for i, p in ipairs(specs) do
							local at = where .. " part " .. i
							if not hasText(p.name) then
								problem(at .. ": a part without a name")
							elseif partNames[p.name] then
								problem(at .. ": two parts named " .. p.name)
							else
								partNames[p.name] = true
							end
							if not IconVisuals.PART_SHAPES[p.shape] then
								problem(at .. ": unknown shape " .. tostring(p.shape))
							end
							local ok = type(p.size) == "table" and #p.size == 3 and type(p.offset) == "table" and #p.offset == 3
							for k = 1, 3 do
								ok = ok and finite(p.size[k]) and p.size[k] > 0 and finite(p.offset[k])
							end
							if not ok then
								problem(at .. ": size (above 0) and offset are 3 numbers")
							elseif p.shape == "Ball" and not (p.size[1] == p.size[2] and p.size[2] == p.size[3]) then
								problem(at .. ": a Ball needs 3 equal sides")
							elseif p.shape == "Cylinder" and p.size[2] ~= p.size[3] then
								problem(at .. ": a Cylinder needs equal Y and Z")
							end
							if type(p.color) ~= "string" or not palette[p.color] then
								problem(at .. ": color " .. tostring(p.color) .. " is not in the palette")
							end
							if not IconVisuals.MATERIALS[p.material] then
								problem(at .. ": material not allowed: " .. tostring(p.material))
							end
							if p.text ~= nil or p.particles ~= nil or p.light ~= nil then
								problem(at .. ": a ViewportFrame draws no text, particles or lights: leave them out")
							end
						end
					end
				elseif not hasText(recipe.creature) then
					problem(where .. ": a creature icon names its creature")
				end
			end
		end
	end
	return problems
end

-- The named checks on built icons. icons: the Icon frames (IconVisuals.build); expect: what must have an icon,
-- { Office = { names }, Eggs = { keys }, Creatures = { keys }, Shop = { keys }, Hud = { keys },
--   rarity = { [creatureKey] = rarityKey }, noText = { [shopKey] = true } }
function IconVisuals.checks(art, icons, expect)
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
	local style = art.Style

	run("data", function(problem)
		for _, text in ipairs(IconVisuals.validate(art)) do
			problem(text)
		end
	end)

	run("coverage", function(problem)
		for _, group in ipairs(IconVisuals.GROUPS) do
			local want, have = {}, {}
			for _, key in ipairs(expect[group] or {}) do
				want[key] = true
				if not (art[group] and art[group][key]) then
					problem(group .. " " .. tostring(key) .. " has no icon")
				end
			end
			for key in pairs(art[group] or {}) do
				have[key] = true
				if not want[key] then
					problem(group .. " " .. tostring(key) .. " has an icon but nothing in the game uses that key")
				end
			end
		end
		for key, rarity in pairs(expect.rarity or {}) do
			local recipe = art.Creatures and art.Creatures[key]
			if recipe and recipe.plate ~= art.RarityPlates[rarity] then
				problem("Creatures " .. key .. ": its plate is not the plate of its rarity")
			end
		end
		local built = {}
		for _, icon in ipairs(icons) do
			local id = tostring(icon:GetAttribute("Group")) .. "/" .. tostring(icon:GetAttribute("Key"))
			if built[id] then
				problem(id .. " was built twice")
			end
			built[id] = true
		end
		for _, group in ipairs(IconVisuals.GROUPS) do
			for _, key in ipairs(expect[group] or {}) do
				if not built[group .. "/" .. key] then
					problem(group .. "/" .. key .. " was not built")
				end
			end
		end
	end)

	run("palette", function(problem)
		local palette = art.Palette
		local function use(key, where)
			if type(key) ~= "string" or not colorOk(palette[key]) then
				problem(where .. ": color " .. tostring(key) .. " is not in the palette")
			end
		end
		use("outline", "Style outline")
		for _, group in ipairs(IconVisuals.GROUPS) do
			for key, recipe in pairs(art[group] or {}) do
				if recipe.plate then
					use(recipe.plate, group .. "." .. tostring(key) .. " plate")
				end
				for _, s in ipairs(recipe.shapes or {}) do
					use(s.color, group .. "." .. tostring(key) .. "." .. tostring(s.name))
				end
			end
		end
		for name, specs in pairs(art.Models or {}) do
			for _, p in ipairs(specs) do
				use(p.color, "Models." .. name .. "." .. tostring(p.name))
			end
		end
		for rarity, plate in pairs(art.RarityPlates or {}) do
			use(plate, "RarityPlates." .. rarity)
		end
	end)

	run("assets", function(problem)
		for _, icon in ipairs(icons) do
			local creatureIcon = icon:GetAttribute("Kind") == "creature"
			for _, d in ipairs(icon:GetDescendants()) do
				if IconVisuals.FORBIDDEN_CLASSES[d.ClassName] then
					problem(d:GetFullName() .. ": no images, meshes, sounds, effects, lights or scripts in an icon (" .. d.ClassName .. ")")
				elseif d.ClassName == "SpecialMesh" then
					if not creatureIcon or d.MeshType ~= Enum.MeshType.Sphere or (d.MeshId or "") ~= "" or (d.TextureId or "") ~= "" then
						problem(d:GetFullName() .. ": only CreatureModels' built-in sphere shapes, with no mesh or texture file")
					end
				end
			end
		end
	end)

	run("texts", function(problem)
		local allowed = {}
		for _, t in ipairs(art.Texts or {}) do
			allowed[t] = true
		end
		for _, icon in ipairs(icons) do
			local noText = icon:GetAttribute("Group") == "Shop" and expect.noText and expect.noText[icon:GetAttribute("Key")]
			for _, d in ipairs(icon:GetDescendants()) do
				if d.ClassName == "TextLabel" or d.ClassName == "TextButton" or d.ClassName == "TextBox" then
					if noText then
						problem(d:GetFullName() .. ": this icon shows no text at all")
					elseif not allowed[d.Text] then
						problem(d:GetFullName() .. ": text \"" .. tostring(d.Text) .. "\" is not one of IconArt.Texts")
					end
					if string.find(d.Text, "[^ -~]") then
						problem(d:GetFullName() .. ": only plain letters and signs (no emoji)")
					end
				end
			end
		end
	end)

	run("style", function(problem)
		local d = style.lightDirection
		local want = Vector3.new(d[1], d[2], d[3]).Unit
		local outline = colorOf(art, "outline")
		for _, icon in ipairs(icons) do
			local group, kind = icon:GetAttribute("Group"), icon:GetAttribute("Kind")
			local plate = icon:FindFirstChild("Plate")
			if group == "Hud" and plate then
				problem(icon:GetFullName() .. ": a HUD icon has no plate")
			elseif group ~= "Hud" and not plate then
				problem(icon:GetFullName() .. ": a card icon sits on a plate")
			end
			for _, x in ipairs(icon:GetDescendants()) do
				if x.ClassName == "UIGradient" and x.Rotation ~= style.lightRotation then
					problem(x:GetFullName() .. ": the light comes from the top-left (gradient rotation " .. style.lightRotation .. ")")
				end
				if x.ClassName == "Frame" and string.sub(x.Name, 1, 7) == "Outline" then
					local line = x:FindFirstChild("Line") -- a ring or a frame: its outline is its line
					if (line and line.Color or x.BackgroundColor3) ~= outline then
						problem(x:GetFullName() .. ": an outline is drawn in the outline color")
					end
				end
			end
			if kind ~= "ui" then
				local view = icon:FindFirstChild("View")
				local camera = view and view.CurrentCamera
				if not (view and camera) then
					problem(icon:GetFullName() .. ": a 3D icon needs its ViewportFrame and camera")
				else
					local seen = camera.CFrame:VectorToObjectSpace(view.LightDirection).Unit
					if math.abs(seen.X - want.X) > 1e-3 or math.abs(seen.Y - want.Y) > 1e-3 or math.abs(seen.Z - want.Z) > 1e-3 then
						problem(icon:GetFullName() .. ": the light must come from the picture's top-left like every icon")
					end
					if camera.FieldOfView ~= style.fov then
						problem(icon:GetFullName() .. ": camera field of view " .. tostring(camera.FieldOfView))
					end
				end
			end
		end
	end)

	run("framing", function(problem)
		for _, icon in ipairs(icons) do
			local view = icon:FindFirstChild("View")
			local camera = view and view.CurrentCamera
			local model = view and view:FindFirstChild("Model")
			if camera and model then
				local t = math.tan(math.rad(camera.FieldOfView) / 2)
				local reach = 0
				for _, p in ipairs(model:GetDescendants()) do
					if p:IsA("BasePart") and p.Transparency < 1 then
						local b = boxOf(p.CFrame, p.Size)
						for _, x in ipairs({ b[1], b[2] }) do
							for _, y in ipairs({ b[3], b[4] }) do
								for _, z in ipairs({ b[5], b[6] }) do
									local c = camera.CFrame:PointToObjectSpace(Vector3.new(x, y, z))
									local depth = -c.Z
									if depth <= 0 then
										problem(p:GetFullName() .. " is behind the camera")
									else
										local sx, sy = math.abs(c.X / depth) / t, math.abs(c.Y / depth) / t
										reach = math.max(reach, sx, sy)
										if sx > 1 + 1e-6 or sy > 1 + 1e-6 then
											problem(p:GetFullName() .. " sticks out of the picture")
										end
									end
								end
							end
						end
					end
				end
				if reach < 0.6 then
					problem(icon:GetFullName() .. string.format(": the model fills only %d%% of the picture", math.floor(reach * 100)))
				end
			end
		end
	end)

	run("budget", function(problem)
		for _, icon in ipairs(icons) do
			local parts, shapes = 0, 0
			for _, d in ipairs(icon:GetDescendants()) do
				if d:IsA("BasePart") and d.Transparency < 1 then
					parts += 1
				end
			end
			local layer = icon:FindFirstChild("Art")
			for _, c in ipairs(layer and layer:GetChildren() or {}) do
				if string.sub(c.Name, 1, 7) ~= "Outline" then
					shapes += 1
				end
			end
			if parts > style.maxParts then
				problem(string.format("%s: %d parts (at most %d)", icon:GetFullName(), parts, style.maxParts))
			end
			if shapes > style.maxShapes then
				problem(string.format("%s: %d shapes (at most %d)", icon:GetFullName(), shapes, style.maxShapes))
			end
		end
	end)

	run("grid", function(problem)
		for _, group in ipairs(IconVisuals.GROUPS) do
			for key, recipe in pairs(art[group] or {}) do
				for _, s in ipairs(recipe.shapes or {}) do
					local b = IconVisuals.shapeBox(art, s)
					if b[1] < -1e-6 or b[3] < -1e-6 or b[2] > style.grid + 1e-6 or b[4] > style.grid + 1e-6 then
						problem(string.format("%s.%s.%s: reaches out of the %d grid (%.1f..%.1f, %.1f..%.1f)", group, tostring(key), tostring(s.name),
							style.grid, b[1], b[2], b[3], b[4]))
					end
				end
			end
		end
	end)
	return results
end

return IconVisuals
