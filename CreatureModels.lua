-- CreatureModels: builds a creature's placeholder 3D model from its "look" in CreatureConfig (milestone 2).
-- Put this ModuleScript in ReplicatedStorage. The server uses it for employees in the garage,
-- the client for the hatch reveal. Models stand on the ground at their pivot and face -Z.
--
-- Extras a look can list: catEars, roundEars, longEars, snout, beak, tail, fin, wings, antennae,
-- spots, headset, glasses, tie, laptop, coffee, crest, crown, horn, spikes, longNeck

local CreatureModels = {}

local BLACK = Color3.fromRGB(25, 25, 30)
local GOLD = Color3.fromRGB(255, 200, 50)
local TIE_RED = Color3.fromRGB(200, 40, 50)
local BEAK_ORANGE = Color3.fromRGB(255, 170, 40)
local LAPTOP_GREY = Color3.fromRGB(70, 72, 82)

local function addPart(model, name, size, cframe, color, kind)
	local p = Instance.new("Part")
	p.Name = name
	p.Size = size
	p.CFrame = cframe
	p.Color = color
	p.Material = Enum.Material.SmoothPlastic
	p.Anchored = true
	p.CanCollide = false -- players walk through employees, and they never press buy pads
	p.CanTouch = false
	p.CanQuery = false
	p.TopSurface = Enum.SurfaceType.Smooth
	p.BottomSurface = Enum.SurfaceType.Smooth
	if kind == "ball" then
		-- A sphere mesh stretches to the part's size, so "balls" can be bean- or egg-shaped
		local mesh = Instance.new("SpecialMesh")
		mesh.MeshType = Enum.MeshType.Sphere
		mesh.Parent = p
	elseif kind == "cylinder" then
		p.Shape = Enum.PartType.Cylinder -- lies along X; rotate it to stand up
	end
	p.Parent = model
	return p
end

local BODY_SIZES = {
	round = Vector3.new(3, 3, 3),
	boxy = Vector3.new(3, 2.6, 2.6),
	tall = Vector3.new(2.4, 3.4, 2.2),
	long = Vector3.new(2.4, 2.2, 3.6),
}

function CreatureModels.build(creature)
	local look = creature.look
	local s = look.scale or 1
	local color, accent = look.color, look.accent
	local has = {}
	for _, extra in ipairs(look.extras or {}) do
		has[extra] = true
	end

	local function v(x, y, z)
		return Vector3.new(x, y, z) * s
	end

	local model = Instance.new("Model")
	model.Name = creature.name
	local root = addPart(model, "Root", Vector3.new(1, 1, 1), CFrame.new(0, 0.5, 0), color)
	root.Transparency = 1
	model.PrimaryPart = root

	-- Body and feet
	local body = (BODY_SIZES[look.shape] or BODY_SIZES.round) * s
	local bodyY = 0.35 * s + body.Y / 2
	addPart(model, "Body", body, CFrame.new(0, bodyY, 0), color, look.shape ~= "boxy" and "ball" or nil)
	for side = -1, 1, 2 do
		addPart(model, "Foot", v(0.9, 0.5, 1.1), CFrame.new(side * body.X * 0.25, 0.25 * s, -body.Z * 0.2), accent, "ball")
	end

	-- Head (in front for long bodies, on top for the rest)
	local head = v(2.1, 2, 2)
	local headPos
	if look.shape == "long" then
		headPos = Vector3.new(0, bodyY + body.Y * 0.35, -body.Z / 2 - 0.3 * s)
	else
		headPos = Vector3.new(0, bodyY + body.Y / 2 + 0.55 * s, -0.25 * s)
	end
	if has.longNeck then
		addPart(model, "Neck", v(0.9, 2.4, 0.9), CFrame.new(headPos + Vector3.new(0, 0.7 * s, 0)), color, "ball")
		headPos += Vector3.new(0, 1.5 * s, 0)
	end
	addPart(model, "Head", head, CFrame.new(headPos), color, "ball")
	local face = -head.Z / 2 -- z offset of the front of the head

	for side = -1, 1, 2 do
		addPart(model, "Eye", v(0.38, 0.45, 0.2), CFrame.new(headPos + Vector3.new(side * 0.45 * s, 0.2 * s, face + 0.12 * s)), BLACK, "ball")
	end

	-- Extras
	for side = -1, 1, 2 do
		if has.catEars then
			addPart(model, "Ear", v(0.75, 0.75, 0.3), CFrame.new(headPos + v(side * 0.55, 0.85, 0.1)) * CFrame.Angles(0, 0, math.rad(45)), color)
		end
		if has.roundEars then
			addPart(model, "Ear", v(0.75, 0.75, 0.4), CFrame.new(headPos + v(side * 0.8, 0.75, 0.1)), accent, "ball")
		end
		if has.longEars then
			addPart(model, "Ear", v(0.35, 1.3, 0.3), CFrame.new(headPos + v(side * 0.5, 1.1, 0.15)) * CFrame.Angles(0, 0, -side * 0.3), color)
		end
		if has.wings then
			addPart(model, "Wing", v(0.25, 1.4, 2), CFrame.new(side * (body.X / 2 + 0.05 * s), bodyY + 0.2 * s, 0.2 * s) * CFrame.Angles(0, 0, -side * 0.35), accent)
		end
		if has.antennae then
			addPart(model, "Antenna", v(0.15, 1.3, 0.15), CFrame.new(headPos + v(side * 0.35, 1.35, 0)) * CFrame.Angles(0, 0, -side * 0.3), BLACK)
			addPart(model, "AntennaTip", v(0.4, 0.4, 0.4), CFrame.new(headPos + v(side * 0.6, 1.95, 0)), accent, "ball")
		end
		if has.glasses then
			local lens = addPart(model, "Lens", v(0.6, 0.5, 0.06), CFrame.new(headPos + Vector3.new(side * 0.45 * s, 0.2 * s, face - 0.03 * s)), Color3.fromRGB(200, 230, 255))
			lens.Transparency = 0.4
		end
		if has.headset then
			addPart(model, "EarCup", v(0.5, 0.75, 0.75), CFrame.new(headPos + v(side * 1.05, 0, 0)), BLACK, "ball")
		end
	end

	if has.snout then
		addPart(model, "Snout", v(1.1, 0.8, 0.9), CFrame.new(headPos + Vector3.new(0, -0.3 * s, face - 0.1 * s)), accent, "ball")
		addPart(model, "Nose", v(0.35, 0.25, 0.2), CFrame.new(headPos + Vector3.new(0, -0.15 * s, face - 0.52 * s)), BLACK, "ball")
	end
	if has.beak then
		addPart(model, "Beak", v(0.55, 0.4, 1), CFrame.new(headPos + Vector3.new(0, -0.1 * s, face - 0.3 * s)), BEAK_ORANGE, "ball")
	end
	if has.tail then
		addPart(model, "Tail", v(0.45, 0.45, 1.8), CFrame.new(0, bodyY + 0.3 * s, body.Z / 2 + 0.6 * s) * CFrame.Angles(-0.6, 0, 0), has.horn and accent or color)
	end
	if has.fin then
		addPart(model, "Fin", v(0.3, 1.5, 1.3), CFrame.new(0, bodyY + body.Y / 2 + 0.4 * s, 0.2 * s) * CFrame.Angles(-0.35, 0, 0), color)
	end
	if has.spots then
		addPart(model, "WingLine", Vector3.new(0.1 * s, 0.06 * s, body.Z), CFrame.new(0, bodyY + body.Y / 2, 0), accent)
		for _, offset in ipairs({ v(0.7, 0, 0.4), v(-0.7, 0, 0.4), v(0.6, 0, -0.6), v(-0.6, 0, -0.6) }) do
			addPart(model, "Spot", v(0.7, 0.2, 0.7), CFrame.new(offset + Vector3.new(0, bodyY + body.Y / 2, 0)), accent, "ball")
		end
	end
	if has.headset then
		addPart(model, "HeadBand", v(2.3, 0.25, 0.4), CFrame.new(headPos + v(0, 0.95, 0)), accent)
		addPart(model, "Mic", v(0.3, 0.3, 0.3), CFrame.new(headPos + Vector3.new(-0.55 * s, -0.55 * s, face)), BLACK, "ball")
	end
	if has.glasses then
		addPart(model, "GlassesFrame", v(1.6, 0.12, 0.1), CFrame.new(headPos + Vector3.new(0, 0.47 * s, face - 0.03 * s)), BLACK)
	end
	if has.tie then
		addPart(model, "Tie", v(0.4, 1.3, 0.12), CFrame.new(0, bodyY, -body.Z / 2 - 0.02 * s), TIE_RED)
	end
	if has.laptop then
		local z = -body.Z / 2 - 0.7 * s
		local y = bodyY - body.Y * 0.2
		addPart(model, "LaptopBase", v(1.6, 0.12, 1.1), CFrame.new(0, y, z), LAPTOP_GREY)
		addPart(model, "LaptopLid", v(1.6, 1.05, 0.1), CFrame.new(0, y + 0.5 * s, z - 0.55 * s) * CFrame.Angles(-0.2, 0, 0), LAPTOP_GREY)
		local logo = addPart(model, "LaptopLogo", v(0.35, 0.35, 0.05), CFrame.new(0, y + 0.55 * s, z - 0.63 * s) * CFrame.Angles(-0.2, 0, 0), accent)
		logo.Material = Enum.Material.Neon
	end
	if has.coffee then
		local cup = CFrame.new(body.X / 2 + 0.15 * s, bodyY, -0.8 * s) * CFrame.Angles(0, 0, math.rad(90))
		addPart(model, "Cup", v(0.8, 0.55, 0.55), cup, Color3.new(1, 1, 1), "cylinder")
		addPart(model, "Coffee", v(0.05, 0.5, 0.5), cup * CFrame.new(0.4 * s, 0, 0), Color3.fromRGB(90, 55, 30), "cylinder")
	end
	if has.crest then
		for i = 0, 2 do
			addPart(model, "Crest", v(0.2, 0.8, 0.45), CFrame.new(headPos + v(0, 1.05, 0.05 + i * 0.3)) * CFrame.Angles(0.3 + i * 0.25, 0, 0), accent)
		end
	end
	if has.crown then
		local ring = addPart(model, "Crown", v(0.45, 1.3, 1.3), CFrame.new(headPos + v(0, 1.05, 0.1)) * CFrame.Angles(0, 0, math.rad(90)), GOLD, "cylinder")
		ring.Material = Enum.Material.Neon
		for i = 0, 2 do
			local angle = math.rad(i * 120)
			local point = addPart(model, "CrownPoint", v(0.25, 0.4, 0.25), CFrame.new(headPos + v(math.sin(angle) * 0.55, 1.4, 0.1 + math.cos(angle) * 0.55)), GOLD)
			point.Material = Enum.Material.Neon
		end
	end
	if has.horn then
		local horn = addPart(model, "Horn", v(0.3, 1.4, 0.3), CFrame.new(headPos + Vector3.new(0, 1.2 * s, face * 0.55)) * CFrame.Angles(-0.35, 0, 0), accent)
		horn.Material = Enum.Material.Neon
	end
	if has.spikes then
		for i = -1, 1 do
			addPart(model, "Spike", v(0.25, 0.7, 0.7), CFrame.new(0, bodyY + body.Y / 2 + 0.1 * s, i * 1 * s) * CFrame.Angles(math.rad(45), 0, 0), accent)
		end
	end

	return model
end

return CreatureModels
