#!/usr/bin/env python3
"""Tests for the building pass (PlotBuilding.lua, PlotBuildingVisuals.lua and the roof-fade client), outside Studio.

Run:   python3 tools/building_test.py

It needs the free Luau command-line tool (https://github.com/luau-lang/luau/releases, the
"luau" file from luau-macos.zip, luau-windows.zip or luau-ubuntu.zip). Put it on your PATH, or point to it:
       LUAU=/path/to/luau python3 tools/building_test.py

It runs the real PlotArt, PlotVisuals, PlotBuilding and PlotBuildingVisuals code with a fake Roblox
(real vector and rotation maths, Instances with parents and attributes) and checks, for each of the five
stages: the part budget, that no building part collides, is touched or hit by a ray, that nothing stands in
a gameplay zone, in the doorway or inside a room part, that nothing floats or flickers, the pure inside check
(door, corners, above the roof, hysteresis, bad numbers) and the pure fade maths (always 0..1). Then it
breaks the inside check and the fade on purpose (mutation runs): every one of them must be caught.
It changes nothing in the game or in Studio. It never edits tools/daily_test.py (another session owns it).
"""

import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PRELUDE = r"""-- Fake Roblox environment for testing the building pass outside Studio (a copy of the plot visuals fake, plus
-- CollectionService, SurfaceGui and ParticleEmitter, so the building builder runs the way it does in Studio)
local print_real = print
local passed, failed = 0, 0
local function check(name, cond, extra)
	if cond then passed += 1 else failed += 1; print_real("FAIL: " .. name .. (extra ~= nil and (" -- " .. tostring(extra)) or "")) end
end
local function warn() end
local SPAWNED = {}
local task = { spawn = function(f, ...) table.insert(SPAWNED, f) end, wait = function() end }
local CLOCK = 0
local os = { clock = function() CLOCK += 0.05; return CLOCK end, time = function() return 0 end }

-- Vector3
local V = {}
local function vec(x, y, z) return setmetatable({ X = x, Y = y, Z = z }, V) end
V.__index = V
V.__add = function(a, b) return vec(a.X + b.X, a.Y + b.Y, a.Z + b.Z) end
V.__sub = function(a, b) return vec(a.X - b.X, a.Y - b.Y, a.Z - b.Z) end
V.__mul = function(a, b)
	if type(a) == "number" then return vec(a * b.X, a * b.Y, a * b.Z) end
	return vec(a.X * b, a.Y * b, a.Z * b)
end
local Vector3 = { new = function(x, y, z) return vec(x or 0, y or 0, z or 0) end }

-- CFrame: position + row-major rotation matrix, composed like Roblox's
local CF = {}
local function cf(x, y, z, r) return setmetatable({ x = x, y = y, z = z, r = r or { 1, 0, 0, 0, 1, 0, 0, 0, 1 } }, CF) end
local function matmul(a, b)
	local m = {}
	for i = 0, 2 do
		for j = 0, 2 do
			m[i * 3 + j + 1] = a[i * 3 + 1] * b[j + 1] + a[i * 3 + 2] * b[j + 4] + a[i * 3 + 3] * b[j + 7]
		end
	end
	return m
end
CF.__index = function(t, k)
	if k == "Position" then return vec(t.x, t.y, t.z) end
	return CF[k]
end
CF.__mul = function(a, b)
	local r = a.r
	if getmetatable(b) == V then
		return vec(r[1] * b.X + r[2] * b.Y + r[3] * b.Z + a.x, r[4] * b.X + r[5] * b.Y + r[6] * b.Z + a.y, r[7] * b.X + r[8] * b.Y + r[9] * b.Z + a.z)
	end
	return cf(r[1] * b.x + r[2] * b.y + r[3] * b.z + a.x, r[4] * b.x + r[5] * b.y + r[6] * b.z + a.y, r[7] * b.x + r[8] * b.y + r[9] * b.z + a.z, matmul(r, b.r))
end
function CF.GetComponents(t) local r = t.r return t.x, t.y, t.z, r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8], r[9] end
local function rx(a) local c, s = math.cos(a), math.sin(a) return { 1, 0, 0, 0, c, -s, 0, s, c } end
local function ry(a) local c, s = math.cos(a), math.sin(a) return { c, 0, s, 0, 1, 0, -s, 0, c } end
local function rz(a) local c, s = math.cos(a), math.sin(a) return { c, -s, 0, s, c, 0, 0, 0, 1 } end
local CFrame = {
	new = function(x, y, z) return cf(x or 0, y or 0, z or 0) end,
	Angles = function(a, b, c) return cf(0, 0, 0, matmul(matmul(rx(a), ry(b)), rz(c))) end,
	fromEulerAnglesYXZ = function(a, b, c) return cf(0, 0, 0, matmul(matmul(ry(b), rx(a)), rz(c))) end,
}

-- Enums: an unknown name errors, like Roblox
local function enumType(names)
	local t = {}
	for _, n in ipairs(names) do t[n] = { Name = n } end
	return setmetatable(t, { __index = function(_, k) error("not a valid enum item: " .. tostring(k)) end })
end
local Enum = {
	Material = enumType({ "Plastic", "SmoothPlastic", "Neon", "Wood", "WoodPlanks", "Marble", "Slate", "Concrete", "Granite", "Brick",
		"Pebble", "Cobblestone", "CorrodedMetal", "DiamondPlate", "Foil", "Metal", "Grass", "Sand", "Fabric", "Ice", "Glass" }),
	PartType = enumType({ "Block", "Cylinder", "Ball", "Wedge", "CornerWedge" }),
	SurfaceType = enumType({ "Smooth" }),
	NormalId = enumType({ "Top", "Bottom", "Left", "Right", "Front", "Back" }),
	Font = enumType({ "GothamBold", "PermanentMarker", "IndieFlower", "LuckiestGuy", "FredokaOne" }),
	SurfaceGuiSizingMode = enumType({ "PixelsPerStud" }),
}
local Color3 = { fromRGB = function(r, g, b) return { R = r / 255, G = g / 255, B = b / 255, rgb = { r, g, b } } end }
local UDim2 = { fromScale = function(x, y) return { x, y } end }
local NumberRange = { new = function(a, b) return { a, b } end }
local NumberSequence = { new = function(a, b) return { a, b } end }
local ColorSequence = { new = function(a, b) return { a, b } end }
local Vector2 = { new = function(x, y) return { x, y } end }

-- Instances with parents, children and attributes
local IS_A = { Part = { BasePart = true }, PointLight = { Light = true } }
local Methods = {}
local Mt = {}
Mt.__index = function(t, k)
	if k == "Parent" then return rawget(t, "_parent") end
	return Methods[k]
end
Mt.__newindex = function(t, k, v)
	if k == "Parent" then
		local old = rawget(t, "_parent")
		if old then
			for i, c in ipairs(old._children) do if c == t then table.remove(old._children, i) break end end
		end
		rawset(t, "_parent", v)
		if v then table.insert(v._children, t) end
	else
		rawset(t, k, v)
	end
end
local function newInstance(class)
	local i = setmetatable({ ClassName = class, Name = class, _children = {}, _attrs = {} }, Mt)
	if class == "Part" then
		rawset(i, "Anchored", false); rawset(i, "CanCollide", true); rawset(i, "CanTouch", true)
		rawset(i, "CanQuery", true); rawset(i, "CastShadow", true); rawset(i, "Transparency", 0)
	end
	return i
end
local Instance = { new = newInstance }
function Methods.GetChildren(t) return table.clone(t._children) end
function Methods.GetDescendants(t)
	local out = {}
	local function walk(n) for _, c in ipairs(n._children) do table.insert(out, c); walk(c) end end
	walk(t)
	return out
end
function Methods.FindFirstChild(t, name) for _, c in ipairs(t._children) do if c.Name == name then return c end end return nil end
function Methods.IsA(t, class) return t.ClassName == class or (IS_A[t.ClassName] ~= nil and IS_A[t.ClassName][class] == true) end
function Methods.SetAttribute(t, k, v) t._attrs[k] = v end
function Methods.GetAttribute(t, k) return t._attrs[k] end
function Methods.Destroy(t) t.Parent = nil; rawset(t, "destroyed", true) end
function Methods.GetFullName(t) local p = t.Parent return (p and (p:GetFullName() .. ".") or "") .. t.Name end
function Methods.ScaleTo(t, s) rawset(t, "scale", s) end

-- CollectionService: AddTag is recorded (the builder tags the Model before it enters the game)
local TAGGED = {}
local game = { GetService = function(_, name)
	if name == "CollectionService" then
		return { AddTag = function(_, inst, tag) TAGGED[inst] = tag end }
	end
	error("no service " .. tostring(name))
end }
"""

BUILDING_TESTS = r"""-- Tests: the real PlotArt, PlotVisuals, PlotBuilding and PlotBuildingVisuals with the fake Roblox --------------
local PlotArt = (function()
__PLOTART__
end)()
local PlotVisuals = (function()
__PLOTVISUALS__
end)()
local PlotBuilding = (function()
__PLOTBUILDING__
end)()
local PBV = (function()
__PLOTBUILDINGVISUALS__
end)()
local IpoConfig = (function()
__IPOCONFIG__
end)()

local function anyMatch(list, word) for _, p in ipairs(list) do if string.find(p, word, 1, true) then return true end end return false end
local function deepCopy(t)
	if type(t) ~= "table" then return t end
	local c = {}
	for k, v in pairs(t) do c[deepCopy(k)] = deepCopy(v) end
	return c
end
local function find(list, name) for _, s in ipairs(list) do if s.name == name then return s end end end

local center = Vector3.new(-135, 0.5, 150) -- a real plot center (slot 2)
local floorTop = PlotArt.Layout.floorTop
local zones = PlotVisuals.zones(PlotArt.Layout)

-- A room with all six props, and the boxes of its parts as offsets from the floor top (what check() compares with)
local function fullRoom(stage)
	local room = PlotVisuals.buildRoom(nil, center, PlotArt, stage)
	for _, slot in ipairs(PlotArt.Layout.itemSlots) do
		PlotVisuals.buildProp(room:FindFirstChild("UpgradeProps"), center, PlotArt, slot.name, Vector3.new(slot.x, 0, slot.z))
	end
	return room
end
local function roomBoxes(room)
	local out = {}
	for _, d in ipairs(room:GetDescendants()) do
		if d:IsA("BasePart") then
			local b = PBV.boxOf(d.CFrame, d.Size)
			table.insert(out, { name = d:GetFullName(), box = { b[1] - center.X, b[2] - center.X, b[3] - center.Y - floorTop, b[4] - center.Y - floorTop, b[5] - center.Z, b[6] - center.Z } })
		end
	end
	return out
end
local function partsOf(model)
	local out = {}
	for _, d in ipairs(model:GetDescendants()) do if d:IsA("BasePart") then table.insert(out, d) end end
	return out
end
local function checkOf(model, room)
	return PBV.check(model, center, PlotArt, PlotBuilding, { zones = zones, roomBoxes = room and roomBoxes(room) or nil })
end

-- 1. The data -----------------------------------------------------------------------------------------------
local problems = PBV.validate(PlotBuilding)
check("PlotBuildingVisuals.validate finds no problem in PlotBuilding", #problems == 0, problems[1])
check("one building per room (PlotArt) and per IpoConfig funding stage", #PlotBuilding.Stages == #PlotArt.Stages and #PlotBuilding.Stages == #IpoConfig.Stages,
	#PlotBuilding.Stages .. " buildings, " .. #PlotArt.Stages .. " rooms, " .. #IpoConfig.Stages .. " stages")
for i, look in ipairs(PlotBuilding.Stages) do
	check("building " .. i .. " is keyed like room " .. i .. " and IpoConfig stage " .. i .. " (" .. tostring(look.key) .. ")",
		look.key == PlotArt.Stages[i].key and look.key == IpoConfig.Stages[i].key, look.key)
end
local E, Inside, Fade, Budget = PlotBuilding.Envelope, PlotBuilding.Inside, PlotBuilding.Fade, PlotBuilding.Budget
check("the building budget is its own (64 parts, 12 ground pieces, 2 SurfaceGuis) and below the room's 260 limit", Budget.parts == 64 and Budget.static == 12
	and Budget.gui == 2 and Budget.parts < PlotVisuals.MAX_PARTS)
check("the envelope is the one in the design: walls from 30.2, 0.8 thick, 14 to the roof, a 9 wide and 9 high door",
	E.inner == 30.2 and E.thick == 0.8 and E.roofBottom == 14 and E.doorHalf == 4.5 and E.doorHeight == 9)
check("the fade is 0.4 s in 20 steps and the inside margin is 1 stud", Fade.seconds == 0.4 and Fade.levels == 20 and Inside.margin == 1)
check("only OFFICE, HQ and BUILD YOUR STARTUP may be written on a building (no odds text, D9)",
	PlotBuilding.Texts["OFFICE"] and PlotBuilding.Texts["HQ"] and PlotBuilding.Texts["BUILD YOUR STARTUP"])
local textCount = 0
for _ in pairs(PlotBuilding.Texts) do textCount += 1 end
check("exactly three texts are allowed", textCount == 3, textCount)
-- The building stands outside every old shell: each room part (props included) is either inside the inner face or
-- wholly beyond the outer face (the garage's weeds and yard marks outside the plot), never in the wall itself
do
	local outer = E.inner + E.thick
	local straddles, reach = nil, 0
	for i = 1, #PlotArt.Stages do
		for _, r in ipairs(roomBoxes(fullRoom(i))) do
			local bx = r.box
			local isYard = bx[4] <= 0.05 or string.find(r.name, "Skyline", 1, true) ~= nil
			local within = math.max(math.abs(bx[1]), math.abs(bx[2]), math.abs(bx[5]), math.abs(bx[6])) <= E.inner
			local beyond = bx[1] >= outer - 1e-9 or bx[2] <= -outer + 1e-9 or bx[5] >= outer - 1e-9 or bx[6] <= -outer + 1e-9
			if within then reach = math.max(reach, math.abs(bx[1]), math.abs(bx[2]), math.abs(bx[5]), math.abs(bx[6])) end
			if not (isYard or within or beyond) then straddles = straddles or r.name end
		end
	end
	check("no room part (props included) is in a wall of the building: inside the inner face or wholly beyond the outer one (reach " .. string.format("%.2f", reach) .. ")", straddles == nil, straddles)
end

-- 2. Every stage, built --------------------------------------------------------------------------------------
local PARTS = {}
for i = 1, #PlotBuilding.Stages do
	local room = fullRoom(i)
	local model = PBV.build(nil, center, PlotArt, PlotBuilding, i)
	local probs = checkOf(model, room)
	check("stage " .. i .. ": no problem in the built building (budget, flags, zones, doorway, room parts, faces, floating) (PlotBuildingVisuals.check)", #probs == 0,
		#probs .. " problem(s), first: " .. tostring(probs[1]))
	local parts = partsOf(model)
	PARTS[i] = #parts
	local statics = #model:FindFirstChild("Static"):GetChildren()
	check("stage " .. i .. ": " .. #parts .. " parts, at most " .. Budget.parts .. " (its own budget, not the room's 260)", #parts >= 30 and #parts <= Budget.parts, #parts)
	check("stage " .. i .. ": " .. statics .. " ground pieces, at most " .. Budget.static, statics >= 1 and statics <= Budget.static, statics)
	local flagged, shadow, nonAnchored = nil, nil, nil
	local lights, emitters, guis, texts = 0, 0, 0, {}
	for _, d in ipairs(model:GetDescendants()) do
		if d:IsA("BasePart") then
			if d.CanCollide or d.CanTouch or d.CanQuery then flagged = flagged or d:GetFullName() end
			if d.CastShadow then shadow = shadow or d:GetFullName() end
			if not d.Anchored then nonAnchored = nonAnchored or d:GetFullName() end
		elseif d.ClassName == "PointLight" or d.ClassName == "SpotLight" or d.ClassName == "SurfaceLight" then lights += 1
		elseif d.ClassName == "ParticleEmitter" then emitters += 1
		elseif d.ClassName == "SurfaceGui" then guis += 1
		elseif d.ClassName == "TextLabel" then table.insert(texts, d.Text) end
	end
	check("stage " .. i .. ": no building part collides, is touched or is hit by a ray (CanCollide, CanTouch, CanQuery off)", flagged == nil, flagged)
	check("stage " .. i .. ": no building part casts a shadow", shadow == nil, shadow)
	check("stage " .. i .. ": every part is anchored", nonAnchored == nil, nonAnchored)
	check("stage " .. i .. ": no light, no particle emitter, at most 2 SurfaceGuis", lights == 0 and emitters == 0 and guis <= 2, lights .. "/" .. emitters .. "/" .. guis)
	local textOk = true
	for _, t in ipairs(texts) do if not PlotBuilding.Texts[t] then textOk = false end end
	check("stage " .. i .. ": its text is only OFFICE, HQ or BUILD YOUR STARTUP", textOk, table.concat(texts, ","))
	check("stage " .. i .. ": named PlotBuilding, with a Fade and a Static group and a Roof", model.Name == "PlotBuilding" and model:FindFirstChild("Fade") ~= nil
		and model:FindFirstChild("Static") ~= nil and model:FindFirstChild("Fade"):FindFirstChild("Roof") ~= nil)
	check("stage " .. i .. ": tagged PlotBuilding for the client", TAGGED[model] == PBV.TAG and PBV.TAG == "PlotBuilding")
	check("stage " .. i .. ": knows its stage and key", model:GetAttribute("Stage") == i and model:GetAttribute("StageKey") == PlotBuilding.Stages[i].key)
	-- The roof sits on the walls, wider than them, and everything that fades is in Fade
	local roof = model:FindFirstChild("Fade"):FindFirstChild("Roof")
	local rb = PBV.boxOf(roof.CFrame, roof.Size)
	check("stage " .. i .. ": the roof is the top, sitting on the walls (underside at 14, a 65 x 65 slab)",
		math.abs(rb[3] - (center.Y + floorTop + E.roofBottom)) < 1e-6 and math.abs((rb[2] - rb[1]) - 2 * E.roofHalf) < 1e-6 and math.abs((rb[6] - rb[5]) - 2 * E.roofHalf) < 1e-6)
	local fadeCount = #partsOf(model:FindFirstChild("Fade"))
	check("stage " .. i .. ": Fade holds every part but the ground pieces", fadeCount + statics == #parts, fadeCount)
	-- The building never moves a gameplay position: it is only a Model next to the room
	check("stage " .. i .. ": building a stage does not touch the room (the room is a separate Model)", room.Name == "PlotRoom" and model ~= room)
end

-- 3. The numbers the client reads --------------------------------------------------------------------------------
do
	local model = PBV.build(nil, center, PlotArt, PlotBuilding, 3)
	local b = PBV.bounds(center, PlotArt, PlotBuilding)
	local floorY = center.Y + floorTop
	check("bounds: the inner faces are 30.2 studs from the plot center on x and z", b.minX == center.X - 30.2 and b.maxX == center.X + 30.2
		and b.minZ == center.Z - 30.2 and b.maxZ == center.Z + 30.2)
	check("bounds: from 3 below the floor top to the underside of the roof", b.minY == floorY - 3 and b.maxY == floorY + 14)
	check("bounds: the door is 9 wide, centered on the plot, with a 3.5 apron, and the margin is 1", b.doorMinX == center.X - 4.5 and b.doorMaxX == center.X + 4.5
		and b.doorDepth == 3.5 and b.margin == 1)
	local allThere = true
	for field, attribute in pairs(PBV.ATTRIBUTES) do
		if model:GetAttribute(attribute) ~= b[field] or type(model:GetAttribute(attribute)) ~= "number" then allThere = false end
	end
	check("the Model carries every number as an attribute (MinX MaxX MinY MaxY MinZ MaxZ DoorMinX DoorMaxX DoorDepth Margin)", allThere)
	check("the Model carries the fade time and the number of steps", model:GetAttribute("FadeSeconds") == 0.4 and model:GetAttribute("FadeLevels") == 20)
	local n = 0
	for _ in pairs(PBV.ATTRIBUTES) do n += 1 end
	check("exactly ten bounds attributes", n == 10, n)
end

-- 4. sync: one building per plot folder, replaced when the stage changes ------------------------------------------
do
	local folder = newInstance("Folder")
	local function count() local n = 0 for _, c in ipairs(folder:GetChildren()) do if c.Name == "PlotBuilding" then n += 1 end end return n end
	local first = PBV.sync(folder, center, PlotArt, PlotBuilding, 1)
	check("sync: builds the stage-1 building in the plot folder", first.Parent == folder and first:GetAttribute("Stage") == 1 and count() == 1)
	local again = PBV.sync(folder, center, PlotArt, PlotBuilding, 1)
	check("sync: the same stage again does nothing (the same Model, no rebuild)", again == first and count() == 1 and not first.destroyed)
	local second = PBV.sync(folder, center, PlotArt, PlotBuilding, 2)
	check("sync: a new stage replaces the building (the old one is destroyed, one is left)", second ~= first and first.destroyed == true and count() == 1 and second:GetAttribute("Stage") == 2)
	local last = #PlotBuilding.Stages
	check("sync: a stage past the last shows the last building", PBV.sync(folder, center, PlotArt, PlotBuilding, 99):GetAttribute("Stage") == last and count() == 1)
	check("sync: stage 0 or below shows the first", PBV.sync(folder, center, PlotArt, PlotBuilding, 0):GetAttribute("Stage") == 1 and count() == 1)
	check("sync: nil, NaN and text show the first (a bad stage never errors)", PBV.sync(folder, center, PlotArt, PlotBuilding, nil):GetAttribute("Stage") == 1
		and PBV.sync(folder, center, PlotArt, PlotBuilding, 0 / 0):GetAttribute("Stage") == 1 and PBV.sync(folder, center, PlotArt, PlotBuilding, "x"):GetAttribute("Stage") == 1)
	check("sync: 2.7 shows the stage below it", PBV.sync(folder, center, PlotArt, PlotBuilding, 2.7):GetAttribute("Stage") == 2)
	PBV.sync(folder, center, PlotArt, PlotBuilding, 5)
	PBV.sync(folder, center, PlotArt, PlotBuilding, 1) -- an IPO: back to the Garage
	check("sync: back to the Garage after an IPO leaves one building", count() == 1 and folder:FindFirstChild("PlotBuilding"):GetAttribute("Stage") == 1)
	-- A room next to it is never touched
	local room = PlotVisuals.buildRoom(folder, center, PlotArt, 1)
	local kids = #room:GetDescendants()
	PBV.sync(folder, center, PlotArt, PlotBuilding, 4)
	check("sync: the PlotRoom in the same folder is not touched", room.Parent == folder and not room.destroyed and #room:GetDescendants() == kids)
end

-- 5. The pure inside check ------------------------------------------------------------------------------------------
local b = PBV.bounds(center, PlotArt, PlotBuilding)
local cx, cz = center.X, center.Z
local fy = center.Y + floorTop
local function inside(x, y, z, was) return PBV.isInside(b, x, y, z, was) end
check("inside: standing in the middle of the room", inside(cx, fy + 3, cz) == true)
check("inside: at the spawn (0, 12) of the plot", inside(cx, fy + 3, cz + 12) == true)
check("inside: next to an incubator at the back", inside(cx - 12, fy + 3, cz - 25) == true)
check("inside: far outside the building is outside", inside(cx + 200, fy + 3, cz) == false and inside(cx, fy + 3, cz + 200) == false and inside(cx, fy + 3, cz - 200) == false)
check("inside: in front of a neighbor's plot (90 studs away) is outside this one", inside(cx + 90, fy + 3, cz) == false and inside(cx - 90, fy + 3, cz) == false)
-- Edges are inside, a hair beyond them is outside
check("inside: the four inner corners count as inside (edges are inclusive)", inside(b.minX, fy + 3, b.minZ) and inside(b.maxX, fy + 3, b.minZ)
	and inside(b.minX, fy + 3, b.maxZ) and inside(b.maxX, fy + 3, b.maxZ))
check("inside: 0.01 beyond a corner is outside (on both axes, all four corners)", not inside(b.minX - 0.01, fy + 3, b.minZ - 0.01) and not inside(b.maxX + 0.01, fy + 3, b.minZ - 0.01)
	and not inside(b.minX - 0.01, fy + 3, b.maxZ + 0.01) and not inside(b.maxX + 0.01, fy + 3, b.maxZ + 0.01))
check("inside: 0.01 past the left, right and back walls is outside", not inside(b.minX - 0.01, fy + 3, cz) and not inside(b.maxX + 0.01, fy + 3, cz) and not inside(cx, fy + 3, b.minZ - 0.01))
check("inside: 0.01 past the front wall, away from the door, is outside", not inside(cx + 10, fy + 3, b.maxZ + 0.01) and not inside(cx - 10, fy + 3, b.maxZ + 0.01))
check("inside: a corner of the building seen from outside, diagonal, is outside", not inside(b.maxX + 1, fy + 3, b.maxZ + 1))
-- The door
check("inside: in the doorway (on the front wall line) is inside", inside(cx, fy + 3, b.maxZ + 0.4) == true)
check("inside: on the apron in front of the door is inside, up to its end (3.5 studs)", inside(cx, fy + 3, b.maxZ + 1) and inside(cx, fy + 3, b.maxZ + 3.5))
check("inside: 0.01 past the end of the apron is outside", not inside(cx, fy + 3, b.maxZ + 3.51))
check("inside: the apron is as wide as the door (edges inclusive), not wider", inside(b.doorMaxX, fy + 3, b.maxZ + 2) and inside(b.doorMinX, fy + 3, b.maxZ + 2)
	and not inside(b.doorMaxX + 0.01, fy + 3, b.maxZ + 2) and not inside(b.doorMinX - 0.01, fy + 3, b.maxZ + 2))
check("inside: beside the door, in front of the wall, is outside", not inside(cx + 6, fy + 3, b.maxZ + 1) and not inside(cx - 6, fy + 3, b.maxZ + 1))
check("inside: there is no door at the back or the sides (no apron there)", not inside(cx, fy + 3, b.minZ - 1) and not inside(b.maxX + 1, fy + 3, cz) and not inside(b.minX - 1, fy + 3, cz))
check("inside: walking in through the door is outside, apron, inside in that order",
	(function()
		local seq = {}
		for z = b.maxZ + 6, b.maxZ - 6, -0.5 do seq[#seq + 1] = inside(cx, fy + 3, z) end
		local state, changes = seq[1], 0
		for i = 2, #seq do if seq[i] ~= state then changes += 1 state = seq[i] end end
		return seq[1] == false and seq[#seq] == true and changes == 1
	end)())
-- Height: the floor, the ceiling, above the roof
check("inside: at the floor top and 3 below it is inside, 3.01 below is outside", inside(cx, fy, cz) and inside(cx, fy - 3, cz) and not inside(cx, fy - 3.01, cz))
check("inside: just under the roof (the underside) is inside", inside(cx, b.maxY, cz) == true)
check("inside: 0.01 above the underside of the roof is outside (the roof stays solid for someone on it)", not inside(cx, b.maxY + 0.01, cz))
check("inside: high above the roof, flying, is outside", not inside(cx, fy + 100, cz) and not inside(cx, fy + 1e6, cz))
check("inside: far below the map (a fall) is outside", not inside(cx, fy - 500, cz))
check("inside: above the roof is outside even above the door apron", not inside(cx, fy + 20, b.maxZ + 1))
-- Bad numbers
check("inside: NaN in any coordinate is never inside", not inside(0 / 0, fy + 3, cz) and not inside(cx, 0 / 0, cz) and not inside(cx, fy + 3, 0 / 0))
check("inside: infinity in any coordinate is never inside", not inside(math.huge, fy + 3, cz) and not inside(-math.huge, fy + 3, cz)
	and not inside(cx, math.huge, cz) and not inside(cx, fy + 3, math.huge) and not inside(cx, fy + 3, -math.huge))
check("inside: NaN is never inside, even when the player just was (hysteresis)", not inside(0 / 0, fy + 3, cz, true) and not inside(cx, 0 / 0, cz, true))
check("inside: text or nil instead of a number is never inside", not inside("5", fy + 3, cz) and not inside(cx, nil, cz) and not inside(cx, fy + 3, {}))
-- Hysteresis
check("hysteresis: 0.5 past a wall is outside for someone who was outside, inside for someone who was inside", not inside(b.maxX + 0.5, fy + 3, cz, false)
	and inside(b.maxX + 0.5, fy + 3, cz, true))
check("hysteresis: exactly the margin (1 stud) past a wall still counts for someone who was inside, a hair more does not", inside(b.maxX + 1, fy + 3, cz, true)
	and not inside(b.maxX + 1.01, fy + 3, cz, true))
check("hysteresis: it works on every wall, on the roof line and on the floor line", inside(b.minX - 1, fy + 3, cz, true) and inside(cx, fy + 3, b.minZ - 1, true)
	and inside(cx, fy + 3, b.maxZ + 1, true) and inside(cx, b.maxY + 1, cz, true) and not inside(cx, b.maxY + 1.01, cz, true)
	and inside(cx, b.minY - 1, cz, true) and not inside(cx, b.minY - 1.01, cz, true))
check("hysteresis: the apron grows by the margin too (4.5 studs for someone who was inside)", inside(cx, fy + 3, b.maxZ + 4.5, true) and not inside(cx, fy + 3, b.maxZ + 4.51, true)
	and not inside(cx, fy + 3, b.maxZ + 3.51, false))
check("hysteresis: the apron widens by the margin for someone who was inside", inside(b.doorMaxX + 1, fy + 3, b.maxZ + 2, true) and not inside(b.doorMaxX + 1.01, fy + 3, b.maxZ + 2, true))
check("hysteresis: nobody is inside because of it from far away", not inside(b.maxX + 5, fy + 3, cz, true) and not inside(cx, fy + 3, b.minZ - 5, true))
-- Several buildings: a different center gives different bounds
do
	local other = PBV.bounds(Vector3.new(cx + 90, 0.5, cz), PlotArt, PlotBuilding)
	check("inside: the building next door has its own box (90 studs over)", PBV.isInside(other, cx + 90, fy + 3, cz, false) and not PBV.isInside(other, cx, fy + 3, cz, false)
		and not PBV.isInside(b, cx + 90, fy + 3, cz, false))
end
-- Every point of the plot's floor that a hire or a prop uses is inside
do
	local all = true
	for _, s in ipairs(PlotArt.Layout.employeeSpots) do if not inside(cx + s[1], fy + 3, cz + s[2]) then all = false end end
	for _, s in ipairs(PlotArt.Layout.incubators) do if not inside(cx + s[1], fy + 3, cz + s[2]) then all = false end end
	for _, s in ipairs(PlotArt.Layout.itemSlots) do if not inside(cx + s.x, fy + 3, cz + s.z) then all = false end end
	check("inside: every hire spot, incubator and upgrade station of the plot is inside the building", all)
	check("inside: both garage signs and the spawn are inside the building", inside(cx + PlotArt.Layout.signs[1].x, fy + 3, cz + PlotArt.Layout.signs[1].z)
		and inside(cx + PlotArt.Layout.signs[2].x, fy + 3, cz + PlotArt.Layout.signs[2].z) and inside(cx + PlotArt.Layout.spawn.x, fy + 3, cz + PlotArt.Layout.spawn.z))
end

-- 6. The pure fade maths ------------------------------------------------------------------------------------------------
local step = PBV.fadeStep
check("fade: moves toward 1 by dt / seconds (0.1 s of 0.4 s = 0.25)", math.abs(step(0, 1, 0.1, 0.4) - 0.25) < 1e-9)
check("fade: moves toward 0 by dt / seconds", math.abs(step(1, 0, 0.1, 0.4) - 0.75) < 1e-9)
check("fade: never goes past the target (a long frame stops at 1 and at 0)", step(0.9, 1, 5, 0.4) == 1 and step(0.1, 0, 5, 0.4) == 0)
check("fade: a huge or infinite frame time stops at the target", step(0, 1, math.huge, 0.4) == 1 and step(1, 0, math.huge, 0.4) == 0)
check("fade: holds when it is at the target", step(1, 1, 0.1, 0.4) == 1 and step(0, 0, 0.1, 0.4) == 0 and step(0.5, 0.5, 0.1, 0.4) == 0.5)
check("fade: a zero, negative or NaN frame time changes nothing", step(0.3, 1, 0, 0.4) == 0.3 and step(0.3, 1, -1, 0.4) == 0.3 and step(0.3, 1, 0 / 0, 0.4) == 0.3)
check("fade: a time of zero, below zero or NaN jumps to the target", step(0, 1, 0.1, 0) == 1 and step(1, 0, 0.1, -3) == 0 and step(0, 1, 0.1, 0 / 0) == 1)
check("fade: values outside 0..1 are clamped (a fade of 5 is 1, of -5 is 0)", step(5, 5, 0.1, 0.4) == 1 and step(-5, -5, 0.1, 0.4) == 0 and step(5, 0, 0.1, 0.4) == 0.75
	and step(-5, 1, 0.1, 0.4) == 0.25)
check("fade: NaN as the fade or the target is treated as 0", step(0 / 0, 1, 0.1, 0.4) == 0.25 and step(1, 0 / 0, 0.1, 0.4) == 0.75 and step(0 / 0, 0 / 0, 0.1, 0.4) == 0)
check("fade: infinity is clamped, not passed on", step(math.huge, 1, 0.1, 0.4) == 1 and step(-math.huge, 0, 0.1, 0.4) == 0 and step(0, math.huge, 0.1, 0.4) == 0.25)
do
	local f, frames = 0, 0
	while f < 1 and frames < 1000 do f = step(f, 1, 1 / 60, 0.4) frames += 1 end
	check("fade: at 60 frames a second a full fade takes 0.4 s (24 frames)", f == 1 and frames >= 24 and frames <= 25, frames)
	frames = 0
	while f > 0 and frames < 1000 do f = step(f, 0, 1 / 30, 0.4) frames += 1 end
	check("fade: at 30 frames a second it takes 12 frames and ends at exactly 0", f == 0 and frames >= 12 and frames <= 13, frames)
end
local seed = 12345
local function rand() seed = (seed * 1664525 + 1013904223) % 4294967296 return seed / 4294967296 end
do
	local bad, mono, over = nil, nil, nil
	for _ = 1, 3000 do
		local f, t = rand() * 4 - 2, rand() * 4 - 2
		local dt, s = rand() * 2 - 0.5, rand() * 2 - 0.2
		local n = step(f, t, dt, s)
		if not (n >= 0 and n <= 1) or n ~= n then bad = bad or string.format("%g %g %g %g -> %g", f, t, dt, s, n) end
		local cf, ct = math.clamp(f, 0, 1), math.clamp(t, 0, 1)
		if cf < ct and n < cf then mono = mono or "went down" end
		if cf > ct and n > cf then mono = mono or "went up" end
		if (cf < ct and n > ct) or (cf > ct and n < ct) then over = over or "overshot" end
	end
	check("fade: 3,000 random inputs always give a value in 0..1", bad == nil, bad)
	check("fade: 3,000 random inputs always move the right way and never overshoot", mono == nil and over == nil, mono or over)
end
do
	local bad = nil
	for _ = 1, 2000 do
		local f, lv = rand() * 6 - 3, math.floor(rand() * 40) + 1
		local q = PBV.quantize(f, lv)
		if q ~= math.floor(q) or q < 0 or q > lv then bad = bad or string.format("%g %d -> %g", f, lv, q) end
	end
	check("quantize: always a whole step from 0 to the number of steps", bad == nil, bad)
	check("quantize: 0 is step 0, 1 is the last step, 0.5 is half, below 0 and above 1 clamp", PBV.quantize(0, 20) == 0 and PBV.quantize(1, 20) == 20 and PBV.quantize(0.5, 20) == 10
		and PBV.quantize(-3, 20) == 0 and PBV.quantize(3, 20) == 20 and PBV.quantize(0 / 0, 20) == 0)
	check("quantize: a step number of 0, NaN or below counts as one step (never divides by zero)", PBV.quantize(1, 0) == 1 and PBV.quantize(1, 0 / 0) == 1 and PBV.quantize(1, -4) == 1)
	check("quantize: a tiny fade is still step 0, so nothing is written for dust", PBV.quantize(0.0001, 20) == 0 and PBV.quantize(0.9999, 20) == 20)
end
do
	local t = PBV.transparencyAt
	check("transparency: step 0 gives the part's own value back (glass stays 0.35, solid stays 0)", t(0.35, 0, 20) == 0.35 and t(0, 0, 20) == 0)
	check("transparency: the last step is 1 (gone) whatever the base", t(0.35, 20, 20) == 1 and t(0, 20, 20) == 1 and t(1, 20, 20) == 1 and t(0.9, 20, 20) == 1)
	check("transparency: halfway between the base and 1", math.abs(t(0.4, 10, 20) - 0.7) < 1e-9 and math.abs(t(0, 10, 20) - 0.5) < 1e-9)
	check("transparency: a base outside 0..1 is clamped (-1 is 0, 2 is 1), NaN is 0", t(-1, 0, 20) == 0 and t(2, 0, 20) == 1 and t(0 / 0, 0, 20) == 0)
	check("transparency: a step past the ends is clamped", t(0.2, 99, 20) == 1 and t(0.2, -5, 20) == 0.2)
	local bad, mono = nil, nil
	for _ = 1, 2000 do
		local base, lv, lvl = rand() * 3 - 1, math.floor(rand() * 30) + 1, math.floor(rand() * 40) - 5
		local v = t(base, lvl, lv)
		if not (v >= 0 and v <= 1) or v ~= v then bad = bad or string.format("%g %d %d -> %g", base, lvl, lv, v) end
		if t(base, lvl + 1, lv) < v then mono = mono or "a later step is more solid" end
	end
	check("transparency: 2,000 random inputs always give 0..1", bad == nil, bad)
	check("transparency: never less transparent at a later step", mono == nil, mono)
end

print_real(string.format("%d passed, %d failed", passed, failed))
for i, n in ipairs(PARTS) do print_real("  stage " .. i .. ": " .. n .. " building parts") end
"""


def read(name):
    with open(os.path.join(ROOT, name), encoding="utf-8") as f:
        return f.read()


def run_luau(luau, source):
    with tempfile.NamedTemporaryFile("w", suffix=".luau", delete=False, encoding="utf-8") as f:
        f.write(source)
        path = f.name
    try:
        result = subprocess.run([luau, path], capture_output=True, text=True)
    finally:
        os.remove(path)
    return result


def building_source():
    return (PRELUDE + BUILDING_TESTS.replace("__PLOTART__", read("PlotArt.lua")).replace("__PLOTVISUALS__", read("PlotVisuals.lua"))
            .replace("__PLOTBUILDING__", read("PlotBuilding.lua")).replace("__PLOTBUILDINGVISUALS__", read("PlotBuildingVisuals.lua"))
            .replace("__IPOCONFIG__", read("IpoConfig.lua")))


def main():
    luau = os.environ.get("LUAU") or shutil.which("luau")
    if not luau:
        print("Luau not found. Download it from https://github.com/luau-lang/luau/releases and set LUAU=/path/to/luau")
        return 2
    code = 0
    result = run_luau(luau, building_source())
    print("Building data, builder, inside check and fade maths: " + (result.stdout.strip() or result.stderr.strip()))
    if result.returncode != 0 or " 0 failed" not in result.stdout:
        code = 1
    return code


if __name__ == "__main__":
    sys.exit(main())
