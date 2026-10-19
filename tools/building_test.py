#!/usr/bin/env python3
"""Tests for the closed garage buildings (lobby L2 and the five kit buildings), outside Studio.

Run:   python3 tools/building_test.py

It needs the free Luau command-line tool (https://github.com/luau-lang/luau/releases, the "luau" file from
luau-macos.zip, luau-windows.zip or luau-ubuntu.zip). Put it on your PATH, or point to it:
       LUAU=/path/to/luau python3 tools/building_test.py

It runs the real PlotArt, PlotVisuals, PlotBuilding, PlotBuildingVisuals and BuildingClient code, and TycoonCore's real
garage functions, in a fake Roblox (real vector and rotation maths, Instances with classes, parents, attributes and
clones, a fake ReplicatedStorage.KitModels made from the kit's sizes and roles). It checks:
- the kit manifest in PlotBuilding against docs/KIT_MODELS.md (36 keys, sizes, roles, colors);
- the layout of the five stages: footprints between building-pass's 62 x 62 and the lot (82.6 x 86.6), the front fixed,
  the doorway, the boxes, the furniture band, the style table, the part budget (kit and Parts), only Wall, RoofEdge and
  Floor stretched;
- every stage built at four turns, with the kit, with the kit imported turned around (both KIT_FRONT_TURN values) and
  with no kit (the Parts fallback): exactly the boxes solid, every look part non-solid, lane, apron, claim post,
  landing, reserved zones, hire spots and incubators clear, every solid part outside the floor, nothing inside a room
  part, everything 0.25 or more transparent at full fade, the kit and the fallback building the same pieces;
- the pure inside check and fade maths (in the module and in BuildingClient, the same text), and the real BuildingClient
  in a fake world (a turned garage, glass from 0.3, the furniture and the boxes never touched);
- TycoonCore's garages (buildGarages, syncBuilding, the sign, the reset, the leave handler) and its source pins.
Then it breaks the code and the data on purpose (mutation runs): each break must be caught by its NAMED check, never by
a crash. It changes nothing in the game or in Studio.
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---------------------------------------------------------------------------------------------------------------------
# The fake Roblox (from the earlier lobby-all attempt's harness, itself from tools/world_test.py's fake)
PRELUDE = r"""
local print_real = print
local passed, failed = 0, 0
local function check(name, cond, extra)
	if cond then
		passed += 1
	else
		failed += 1
		print_real("FAIL: " .. name .. (extra ~= nil and (" -- " .. tostring(extra)) or ""))
	end
end
local WARNED = {}
local function warn(...) table.insert(WARNED, table.concat({ ... }, " ")) end
local task = { spawn = function(f, ...) end, wait = function() end, delay = function() end }

local V = {}
V.__index = function(t, k)
	if k == "Magnitude" then return math.sqrt(t.X * t.X + t.Y * t.Y + t.Z * t.Z) end
	return V[k]
end
local function vec(x, y, z) return setmetatable({ X = x, Y = y, Z = z }, V) end
V.__add = function(a, b) return vec(a.X + b.X, a.Y + b.Y, a.Z + b.Z) end
V.__sub = function(a, b) return vec(a.X - b.X, a.Y - b.Y, a.Z - b.Z) end
V.__unm = function(a) return vec(-a.X, -a.Y, -a.Z) end
V.__mul = function(a, b)
	if type(a) == "number" then return vec(a * b.X, a * b.Y, a * b.Z) end
	if type(b) == "number" then return vec(a.X * b, a.Y * b, a.Z * b) end
	return vec(a.X * b.X, a.Y * b.Y, a.Z * b.Z)
end
V.__div = function(a, b) return vec(a.X / b, a.Y / b, a.Z / b) end
V.__eq = function(a, b) return a.X == b.X and a.Y == b.Y and a.Z == b.Z end
V.__tostring = function(a) return string.format("%g, %g, %g", a.X, a.Y, a.Z) end
local Vector3 = { new = function(x, y, z) return vec(x or 0, y or 0, z or 0) end }

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
local function transpose(r) return { r[1], r[4], r[7], r[2], r[5], r[8], r[3], r[6], r[9] } end
local function inverse(a)
	local t = transpose(a.r)
	return cf(-(t[1] * a.x + t[2] * a.y + t[3] * a.z), -(t[4] * a.x + t[5] * a.y + t[6] * a.z), -(t[7] * a.x + t[8] * a.y + t[9] * a.z), t)
end
CF.__index = function(t, k)
	if k == "Position" then return vec(t.x, t.y, t.z) end
	if k == "Rotation" then return cf(0, 0, 0, t.r) end
	if k == "LookVector" then return vec(-t.r[3], -t.r[6], -t.r[9]) end
	if k == "X" then return t.x elseif k == "Y" then return t.y elseif k == "Z" then return t.z end
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
function CF.Inverse(t) return inverse(t) end
function CF.ToObjectSpace(a, b) return inverse(a) * b end
function CF.PointToObjectSpace(a, v) return inverse(a) * v end
function CF.ToWorldSpace(a, b) return a * b end
local function rx(a) local c, s = math.cos(a), math.sin(a) return { 1, 0, 0, 0, c, -s, 0, s, c } end
local function ry(a) local c, s = math.cos(a), math.sin(a) return { c, 0, s, 0, 1, 0, -s, 0, c } end
local function rz(a) local c, s = math.cos(a), math.sin(a) return { c, -s, 0, s, c, 0, 0, 0, 1 } end
local CFrame = {
	new = function(x, y, z, ...)
		if type(x) == "table" then return cf(x.X, x.Y, x.Z) end
		local n = select("#", ...)
		if n == 9 then return cf(x, y, z, { ... }) end
		return cf(x or 0, y or 0, z or 0)
	end,
	Angles = function(a, b, c) return cf(0, 0, 0, matmul(matmul(rx(a), ry(b)), rz(c))) end,
	fromEulerAnglesYXZ = function(a, b, c) return cf(0, 0, 0, matmul(matmul(ry(b), rx(a)), rz(c))) end,
	lookAt = function(at, target) return cf(at.X, at.Y, at.Z) end,
}
local function typeof(v)
	local mt = getmetatable(v)
	if mt == CF then return "CFrame" elseif mt == V then return "Vector3" end
	if type(v) == "table" and rawget(v, "_children") then return "Instance" end
	return type(v)
end

local function enumType(names)
	local t = {}
	for _, n in ipairs(names) do t[n] = { Name = n } end
	return setmetatable(t, { __index = function(_, k) error("not a valid enum item: " .. tostring(k)) end })
end
local Enum = {
	Material = enumType({ "Plastic", "SmoothPlastic", "Neon", "Wood", "WoodPlanks", "Marble", "Slate", "Concrete", "Granite", "Brick",
		"Pebble", "Cobblestone", "CorrodedMetal", "DiamondPlate", "Foil", "Metal", "Grass", "Sand", "Fabric", "Ice", "Glass" }),
	PartType = enumType({ "Block", "Cylinder", "Ball", "Wedge", "CornerWedge" }),
	SurfaceType = enumType({ "Smooth", "Studs" }),
	NormalId = enumType({ "Top", "Bottom", "Left", "Right", "Front", "Back" }),
	Font = enumType({ "GothamBold", "GothamBlack", "Gotham", "FredokaOne", "LuckiestGuy", "PermanentMarker", "IndieFlower" }),
	SurfaceGuiSizingMode = enumType({ "PixelsPerStud", "FixedSize" }),
	ModelStreamingMode = enumType({ "Default", "Atomic", "Persistent", "PersistentPerPlayer", "Nonatomic" }),
}
local C3 = {}
C3.__eq = function(a, b) return a.R == b.R and a.G == b.G and a.B == b.B end
local Color3 = {
	fromRGB = function(r, g, b) return setmetatable({ R = r / 255, G = g / 255, B = b / 255, rgb = { r, g, b } }, C3) end,
	new = function(r, g, b) return setmetatable({ R = r, G = g, B = b, rgb = { math.floor(r * 255 + 0.5), math.floor(g * 255 + 0.5), math.floor(b * 255 + 0.5) } }, C3) end,
	fromHex = function(h) return setmetatable({ rgb = { tonumber(h:sub(1, 2), 16), tonumber(h:sub(3, 4), 16), tonumber(h:sub(5, 6), 16) } }, C3) end,
}
local UDim2 = {
	fromScale = function(x, y) return { 0, x, 0, y } end,
	fromOffset = function(x, y) return { x, 0, y, 0 } end,
	new = function(a, b, c, d) return { b, a, d, c } end,
}
local Vector2 = { new = function(x, y) return { X = x, Y = y } end }
local NumberRange = { new = function(a, b) return { a, b or a } end }
local NumberSequence = { new = function(a, b) return { a, b or a } end }
local ColorSequence = { new = function(a, b) return { a, b or a } end }

local function newSignal()
	local s = { handlers = {} }
	function s.Connect(self, fn)
		local c = { fn = fn, connected = true }
		function c.Disconnect(self2) self2.connected = false end
		table.insert(self.handlers, c)
		return c
	end
	function s.Fire(self, ...) for _, c in ipairs(table.clone(self.handlers)) do if c.connected then c.fn(...) end end end
	return s
end

local WRITES = 0 -- every Transparency write (the client must not write while a building holds still)
local PART = { BasePart = true, PVInstance = true }
local IS_A = {
	Part = PART, MeshPart = PART, WedgePart = PART, CornerWedgePart = PART, UnionOperation = PART, SpawnLocation = { Part = true, BasePart = true, PVInstance = true },
	PointLight = { Light = true }, SpotLight = { Light = true }, SurfaceLight = { Light = true },
	Model = { PVInstance = true }, Workspace = { Model = true, PVInstance = true },
	Script = { BaseScript = true, LuaSourceContainer = true }, LocalScript = { Script = true, BaseScript = true, LuaSourceContainer = true },
	ModuleScript = { LuaSourceContainer = true }, SurfaceGui = { LayerCollector = true, GuiBase = true },
	BillboardGui = { LayerCollector = true, GuiBase = true }, TextLabel = { GuiObject = true, GuiBase2d = true },
	Decal = { FaceInstance = true }, Texture = { Decal = true, FaceInstance = true }, SurfaceAppearance = {},
}
local PART_CLASSES = { Part = true, MeshPart = true, WedgePart = true, CornerWedgePart = true, UnionOperation = true, SpawnLocation = true }
local Methods = {}
local Mt = {}
Mt.__index = function(t, k)
	if k == "Parent" then return rawget(t, "_parent") end
	local props = rawget(t, "_props")
	if props then
		if k == "Position" and props.CFrame then return props.CFrame.Position end
		if props[k] ~= nil then return props[k] end
	end
	if k == "DescendantAdded" then
		local s = rawget(t, "_descAdded")
		if not s then s = newSignal(); rawset(t, "_descAdded", s) end
		return s
	end
	local m = Methods[k]
	if m then return m end
	for _, c in ipairs(rawget(t, "_children")) do if c.Name == k then return c end end -- garage.Floor, gui.TextLabel
	return nil
end
Mt.__newindex = function(t, k, v)
	if k == "Parent" then
		local old = rawget(t, "_parent")
		if old then
			for i, c in ipairs(old._children) do if c == t then table.remove(old._children, i) break end end
		end
		rawset(t, "_parent", v)
		if v then
			table.insert(v._children, t)
			local a = v
			while a do
				local s = rawget(a, "_descAdded")
				if s then s:Fire(t) end
				a = rawget(a, "_parent")
			end
		end
		return
	end
	if k == "Transparency" then WRITES += 1 end
	local props = rawget(t, "_props")
	if props then
		if k == "Position" then
			local old = props.CFrame
			props.CFrame = cf(v.X, v.Y, v.Z, old and old.r or nil)
			return
		end
		props[k] = v
		return
	end
	rawset(t, k, v)
end
local function newInstance(class)
	local i = setmetatable({ ClassName = class, Name = class, _children = {}, _attrs = {} }, Mt)
	if PART_CLASSES[class] then
		rawset(i, "_props", {
			Anchored = false, CanCollide = true, CanTouch = true, CanQuery = true, CastShadow = true, Transparency = 0,
			Size = vec(4, 1.2, 2), CFrame = cf(0, 0, 0), Color = Color3.fromRGB(163, 162, 165), Material = Enum.Material.Plastic,
			Shape = Enum.PartType.Block,
		})
	elseif class == "Model" then
		rawset(i, "_props", { ModelStreamingMode = Enum.ModelStreamingMode.Default, WorldPivot = cf(0, 0, 0) })
	elseif class == "TextLabel" then
		rawset(i, "TextTransparency", 0)
		rawset(i, "Text", "")
	elseif class == "SurfaceGui" or class == "BillboardGui" then
		rawset(i, "Enabled", true)
	elseif class == "ProximityPrompt" then
		rawset(i, "Enabled", true)
		rawset(i, "Triggered", newSignal())
	elseif class == "Decal" or class == "Texture" then
		rawset(i, "Transparency", 0)
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
function Methods.FindFirstChild(t, name, recursive)
	for _, c in ipairs(recursive and t:GetDescendants() or t._children) do if c.Name == name then return c end end
	return nil
end
function Methods.FindFirstChildOfClass(t, class)
	for _, c in ipairs(t._children) do if c.ClassName == class then return c end end
	return nil
end
function Methods.IsA(t, class) return t.ClassName == class or (IS_A[t.ClassName] ~= nil and IS_A[t.ClassName][class] == true) end
function Methods.SetAttribute(t, k, v) t._attrs[k] = v end
function Methods.GetAttribute(t, k) return t._attrs[k] end
function Methods.GetAttributes(t) return table.clone(t._attrs) end
function Methods.Destroy(t) t.Parent = nil; rawset(t, "destroyed", true) end
function Methods.GetFullName(t) local p = t.Parent return (p and p.ClassName ~= "DataModel" and (p:GetFullName() .. ".") or "") .. t.Name end
function Methods.GetPivot(t)
	local props = rawget(t, "_props")
	if props and props.CFrame then return props.CFrame end
	return (props and props.WorldPivot) or cf(0, 0, 0)
end
function Methods.IsDescendantOf(t, ancestor)
	local p = t.Parent
	while p do
		if p == ancestor then return true end
		p = p.Parent
	end
	return false
end
function Methods.Clone(t)
	if t.Archivable == false then return nil end -- like Roblox: an Instance with Archivable off is not copied
	local c = newInstance(t.ClassName)
	for k, v in pairs(t) do
		if k ~= "_children" and k ~= "_attrs" and k ~= "_props" and k ~= "_parent" and k ~= "_descAdded" then rawset(c, k, v) end
	end
	local from, to = rawget(t, "_props"), rawget(c, "_props")
	if from and to then for k, v in pairs(from) do to[k] = v end end
	for k, v in pairs(t._attrs) do c._attrs[k] = v end
	for _, child in ipairs(t._children) do
		local copy = child:Clone()
		if copy then copy.Parent = c end
	end
	return c
end

local TAGS = {}
local TAG_ADDED, TAG_REMOVED = newSignal(), newSignal()
local CollectionService = {
	AddTag = function(_, inst, tag) TAGS[inst] = tag; TAG_ADDED:Fire(inst) end,
	GetTagged = function(_, tag)
		local out = {}
		for inst, t in pairs(TAGS) do if t == tag and not rawget(inst, "destroyed") then table.insert(out, inst) end end
		return out
	end,
	GetInstanceAddedSignal = function() return TAG_ADDED end,
	GetInstanceRemovedSignal = function() return TAG_REMOVED end,
}
local game = newInstance("DataModel")
local workspace = newInstance("Workspace")
workspace.Name = "Workspace"
workspace.Parent = game
local SERVICES = { CollectionService = CollectionService, Workspace = workspace }
for _, name in ipairs({ "ServerScriptService", "ReplicatedStorage", "Players", "StarterPlayer", "RunService" }) do
	local s = newInstance(name)
	s.Name = name
	s.Parent = game
	SERVICES[name] = s
end
function Methods.GetService(t, name)
	local s = SERVICES[name]
	if not s then error("no service " .. tostring(name)) end
	return s
end
"""

MODULES = r"""
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
__PBV__
end)()
local PB = PlotBuilding
"""

# Shared Luau helpers: the fake kit (made from the manifest's sizes and the fallback boxes, imported turned by `turn`),
# frames at a turn, rooms, boxes in the frame of the Floor's top.
HELPERS = r"""
local EPS = 1e-6
local function near(a, b, e) return math.abs(a - b) <= (e or EPS) end
local function frameAt(turn, x, z)
	return CFrame.new(x or -135, 0.5, z or 150) * CFrame.Angles(0, math.rad(turn), 0)
end
local function inFrame(origin, part) return PBV.boxOf(origin:ToObjectSpace(part.CFrame), part.Size) end
-- The Floor's top in a garage's frame, computed here (not with the module's helper, so a builder that ignores the turn is seen)
local function topOf(frame) return frame * CFrame.new(0, PB.FLOOR_TOP, 0) end
local function overlaps(a, b, m) return PBV.overlaps(a, b, m or 0.01) end

-- A fake ReplicatedStorage.KitModels: one Model per key, its MeshParts from the fallback boxes (same sizes and roles), the
-- whole model turned by `importTurn` about +Y (what Studio's importer may have done), its WorldPivot the bottom-center,
-- its KitSize the box. Parts get Roblox-like names (main2, trim11), only the Role attribute names them. The builder's
-- tests use one MeshPart per fallback box (a jamb is its own part); onePerRole = true makes one MeshPart per role, the
-- union of that role's boxes, as in the real kit (checkKit wants exactly that).
local function makeKit(importTurn, skip, onePerRole)
	local folder = Instance.new("Folder")
	folder.Name = "KitModels"
	local i = 0
	local keys = {}
	for key in pairs(PB.KitManifest) do table.insert(keys, key) end
	table.sort(keys)
	for _, key in ipairs(keys) do
		i += 1
		if not (skip and skip[key]) then
			local entry = PB.KitManifest[key]
			local m = Instance.new("Model")
			m.Name = key
			local pivot = CFrame.new(400 + i * 40, 7, -300 - i * 3) -- anywhere: the importer leaves them somewhere
			m.WorldPivot = pivot
			m:SetAttribute("KitSize", Vector3.new(entry.size[1], entry.size[2], entry.size[3]))
			local boxes = PB.fallbackOf(key)
			if onePerRole then
				local byRole, order = {}, {}
				for _, b in ipairs(boxes) do
					local box = { b.at[1] - b.size[1] / 2, b.at[1] + b.size[1] / 2, b.at[2] - b.size[2] / 2, b.at[2] + b.size[2] / 2, b.at[3] - b.size[3] / 2, b.at[3] + b.size[3] / 2 }
					local u = byRole[b.role]
					if not u then
						byRole[b.role] = box
						table.insert(order, b.role)
					else
						for k = 1, 5, 2 do u[k] = math.min(u[k], box[k]); u[k + 1] = math.max(u[k + 1], box[k + 1]) end
					end
				end
				boxes = {}
				for _, role in ipairs(order) do
					local u = byRole[role]
					table.insert(boxes, { role = role, size = { u[2] - u[1], u[4] - u[3], u[6] - u[5] }, at = { (u[1] + u[2]) / 2, (u[3] + u[4]) / 2, (u[5] + u[6]) / 2 } })
				end
			end
			for j, b in ipairs(boxes) do
				local p = Instance.new("MeshPart")
				p.Name = b.role .. (j * 3 + 1)
				p:SetAttribute("Role", b.role)
				p.Size = Vector3.new(b.size[1], b.size[2], b.size[3])
				p.CFrame = pivot * CFrame.Angles(0, math.rad(importTurn), 0) * CFrame.new(b.at[1], b.at[2], b.at[3])
				p.Color = Color3.fromRGB(163, 162, 165)
				p.Anchored = true
				p.Parent = m
			end
			m.Parent = folder
		end
	end
	return folder
end

-- The room of a stage with the six upgrade props, built at a frame: its parts' boxes in the frame of the Floor's top
local function roomBoxes(frame, stage)
	local room = PlotVisuals.buildRoom(nil, frame, PlotArt, stage)
	local props = room:FindFirstChild("UpgradeProps")
	for _, slot in ipairs(PlotArt.Layout.itemSlots) do
		PlotVisuals.buildProp(props, frame, PlotArt, slot.name, Vector3.new(slot.x, 0, slot.z))
	end
	local origin = topOf(frame)
	local out = {}
	for _, d in ipairs(room:GetDescendants()) do
		if d:IsA("BasePart") then table.insert(out, { name = d:GetFullName(), box = inFrame(origin, d) }) end
	end
	return out
end

-- Every part of a built building by piece name: { role, box } sorted, in the frame of the Floor's top
local function piecesOf(model, frame)
	local origin = topOf(frame)
	local out = {}
	for _, d in ipairs(model:GetDescendants()) do
		if d:IsA("BasePart") and d.Parent.Name ~= "Solid" then
			local name = d:GetAttribute("Piece")
			out[name] = out[name] or {}
			table.insert(out[name], { role = d:GetAttribute("Role"), box = inFrame(origin, d) })
		end
	end
	for _, list in pairs(out) do
		table.sort(list, function(a, b)
			for k = 1, 6 do
				if math.abs(a.box[k] - b.box[k]) > 1e-4 then return a.box[k] < b.box[k] end
			end
			return tostring(a.role) < tostring(b.role)
		end)
	end
	return out
end
local function samePieces(a, b)
	for name, list in pairs(a) do
		local other = b[name]
		if not other or #other ~= #list then return false, name .. " (count)" end
		for i, e in ipairs(list) do
			if e.role ~= other[i].role then return false, name .. " (role)" end
			for k = 1, 6 do if not near(e.box[k], other[i].box[k], 1e-4) then return false, name .. " (box)" end end
		end
	end
	for name in pairs(b) do if not a[name] then return false, name .. " (missing)" end end
	return true
end
local function unionBox(list)
	local u = { math.huge, -math.huge, math.huge, -math.huge, math.huge, -math.huge }
	for _, e in ipairs(list) do
		for k = 1, 5, 2 do u[k] = math.min(u[k], e.box[k]); u[k + 1] = math.max(u[k + 1], e.box[k + 1]) end
	end
	return u
end
-- The box a piece takes, from the layout alone (its kit size, stretch, turn and tilt), in the frame of the Floor's top
local function pieceBox(p)
	local s = p.key == PB.BLOCK and p.size or PB.KitManifest[p.key].size
	local origin = CFrame.new()
	local f = PBV.pieceFrame(origin, p)
	local w, h, d = s[1] * (p.sx or 1), s[2], s[3] * (p.sz or 1)
	local c = f * CFrame.new(0, h / 2, 0)
	return PBV.boxOf(c, Vector3.new(w, h, d))
end
"""

DATA_TESTS = r"""
local function countBlocks(L) local n = 0 for _, p in ipairs(L.pieces) do if p.key == PB.BLOCK then n += 1 end end return n end
-- 1. The manifest against docs/KIT_MODELS.md -----------------------------------------------------------------------
do
	local n, bad = 0, nil
	for key, want in pairs(EXPECTED_KIT) do
		n += 1
		local e = PB.KitManifest[key]
		if not e then bad = bad or (key .. " missing") else
			if not (near(e.size[1], want.w, 0.05) and near(e.size[2], want.h, 0.05) and near(e.size[3], want.d, 0.05)) then bad = bad or (key .. " size") end
			for role, hex in pairs(want.roles) do if e.roles[role] ~= hex then bad = bad or (key .. "." .. role) end end
			for role in pairs(e.roles) do if not want.roles[role] then bad = bad or (key .. "." .. role .. " extra") end end
		end
	end
	local mine = 0
	for _ in pairs(PB.KitManifest) do mine += 1 end
	check("manifest: docs/KIT_MODELS.md has 36 models", n == 36, n)
	check("manifest: PlotBuilding.KitManifest has the same 36 keys, sizes (within 0.05) and roles with their colors", bad == nil and mine == 36, bad or mine)
end

-- 2. The fallback: the Parts version of every key fills exactly its kit size, with the key's roles only ------------------
do
	local bad = nil
	for key, e in pairs(PB.KitManifest) do
		local list = PB.fallbackOf(key)
		if not list or #list == 0 then bad = bad or (key .. ": no Parts version") else
			local u = { math.huge, -math.huge, math.huge, -math.huge, math.huge, -math.huge }
			for _, b in ipairs(list) do
				if not e.roles[b.role] then bad = bad or (key .. ": role " .. tostring(b.role)) end
				local bx = { b.at[1] - b.size[1] / 2, b.at[1] + b.size[1] / 2, b.at[2] - b.size[2] / 2, b.at[2] + b.size[2] / 2, b.at[3] - b.size[3] / 2, b.at[3] + b.size[3] / 2 }
				for k = 1, 5, 2 do u[k] = math.min(u[k], bx[k]); u[k + 1] = math.max(u[k + 1], bx[k + 1]) end
			end
			local s = e.size
			if not (near(u[1], -s[1] / 2) and near(u[2], s[1] / 2) and near(u[3], 0) and near(u[4], s[2]) and near(u[5], -s[3] / 2) and near(u[6], s[3] / 2)) then
				bad = bad or (key .. ": does not fill " .. s[1] .. " x " .. s[2] .. " x " .. s[3])
			end
		end
	end
	check("fallback: every piece is built and fills its kit size (bottom-center, front +Z), with its own roles", bad == nil, bad)
end

-- 3. The six layouts (overhaul 2: Series C added, the HQ Tower is the sixth building) ---------------------------------------------------------------------------------------------
local LAYOUTS = {}
for s = 1, 6 do LAYOUTS[s] = PB.layout(s) end
check("layout: six stages, one per funding stage, with PlotArt's keys in order", #PB.Stages == 6 and #PlotArt.Stages == 6 and (function()
	for s = 1, 6 do if LAYOUTS[s].key ~= PlotArt.Stages[s].key then return false end end return true end)())
check("layout: a stage past the last shows the last, below 1 or not a number shows the first",
	PB.layout(9).stage == 6 and PB.layout(0).stage == 1 and PB.layout(0 / 0).stage == 1 and PB.layout(nil).stage == 1)
check("frame: PlotBuilding.FLOOR_TOP is PlotArt.Layout.floorTop", PB.FLOOR_TOP == PlotArt.Layout.floorTop)

for s = 1, 6 do
	local L = LAYOUTS[s]
	local fp, lot, min = L.footprint, PB.Lot, PB.MinShell
	check("footprint: stage " .. s .. " is at least building-pass's shell (62 x 62) and inside the lot (82.6 x 86.6)",
		fp.x1 >= min.half and fp.x0 <= -min.half and fp.z0 <= min.back and fp.x1 <= lot.half and fp.x0 >= -lot.half and fp.z0 >= lot.back and fp.z1 <= lot.front,
		string.format("%g..%g x %g..%g", fp.x0, fp.x1, fp.z0, fp.z1))
	check("front: every stage's front face is z " .. PB.FRONT_OUT .. " (it grows from the floor's front-center; the front never moves)",
		fp.z1 == PB.FRONT_OUT and fp.x0 == -fp.x1, fp.z1)
	if s > 1 then
		local prev = LAYOUTS[s - 1].footprint
		check("footprint: stage " .. s .. " contains stage " .. (s - 1) .. " (it only grows)", fp.x1 >= prev.x1 and fp.z0 <= prev.z0)
	end
	-- keys and stretch
	local unknown, stretched, badBlock = nil, nil, nil
	for _, p in ipairs(L.pieces) do
		if p.key == PB.BLOCK then
			local sz = p.size
			if type(sz) ~= "table" or #sz ~= 3 or not (sz[1] > 0 and sz[2] > 0 and sz[3] > 0) or type(p.role) ~= "string" or #PB.partsOf(p) ~= 1 then badBlock = badBlock or p.name end
		elseif not PB.KitManifest[p.key] then unknown = unknown or p.key end
		local allowed = STRETCH_ALLOWED[p.key]
		if (p.sx ~= 1 and not (allowed and allowed.x)) or (p.sz ~= 1 and not (allowed and allowed.z)) then stretched = stretched or p.name end
	end
	check("kit: every key stage " .. s .. " uses is in the KitManifest (or is a Block)", unknown == nil, unknown)
	-- the facade's depth (overhaul phase 5): the named Blocks each stage adds outside its front wall (and the tower's band)
	local FACADE = { {}, { "Canopy", "CanopyFascia", "SillL", "SillR" }, { "Canopy", "Course", "Sill2", "PilasterL1", "PilasterR2" },
		{ "FinL1", "FinR2", "Line1", "Line3", "PlinthL", "PlinthR" }, { "PodiumGold", "TowerLine" }, { "PodiumGold", "TowerLine" } }
	local missing = nil
	for _, want in ipairs(FACADE[s]) do
		local found = false
		for _, p in ipairs(L.pieces) do
			if p.key == PB.BLOCK and string.sub(p.name, -#want) == want then found = true end
		end
		if not found then missing = missing or want end
	end
	check("facade: stage " .. s .. " has its facade Blocks (overhaul phase 5: canopy, sills, course, pilasters, fins, lines, plinths)", missing == nil, missing)
	check("block: every Block of stage " .. s .. " has a size (three positive numbers) and a role, and is one Part", badBlock == nil, badBlock)
	check("stretch: at stage " .. s .. " only Wall, RoofEdge, WallDoor and DoorLeaf (along X) and Floor (X and Z) are stretched", stretched == nil, stretched)
	-- the doorway
	local bx = {}
	for _, b in ipairs(L.boxes) do bx[b.name] = b.box end
	local gapW = bx.FrontRight[1] - bx.FrontLeft[2]
	check("doorway: stage " .. s .. "'s solid opening is at least 9 wide and 9 high, centered on the lane",
		gapW >= 9 and bx.Lintel[3] >= 9 and near(bx.FrontRight[1], -bx.FrontLeft[2]) and bx.FrontLeft[2] <= -PB.Lane.half and bx.FrontRight[1] >= PB.Lane.half,
		gapW .. " x " .. bx.Lintel[3])
	-- the solid boxes: the lane, the floor, the lot
	local laneBox = { -PB.Lane.half, PB.Lane.half, PB.GROUND, PB.Lane.top, PB.Lane.from, PB.Lane.to }
	local inLane, overFloor, outLot = nil, nil, nil
	for _, b in ipairs(L.boxes) do
		if overlaps(b.box, laneBox) then inLane = inLane or b.name end
		local e = PB.ROOM_EDGE
		if b.box[1] < e - 0.01 and b.box[2] > -e + 0.01 and b.box[5] < e - 0.01 and b.box[6] > -e + 0.01 and b.box[3] < PB.CLEAR_ABOVE then overFloor = overFloor or b.name end
		if b.box[1] < -PB.Lot.half or b.box[2] > PB.Lot.half or b.box[5] < PB.Lot.back or b.box[6] > PB.Lot.front then outLot = outLot or b.name end
	end
	check("lane: at stage " .. s .. " no solid box stands in the doorway lane (9 wide, 9 high, room to the end of the apron)", inLane == nil, inLane)
	check("floor: at stage " .. s .. " every solid box is outside the 60 x 60 floor, or above " .. PB.CLEAR_ABOVE .. " (the roof)", overFloor == nil, overFloor)
	check("lot: at stage " .. s .. " every solid box is inside the lot", outLot == nil, outLot)
	check("roof: at stage " .. s .. " the roof's solid box starts at 12.5 or higher (a jump reaches about 12.3)", bx.Roof and bx.Roof[3] >= 12.5 - EPS, bx.Roof and bx.Roof[3])
	-- the fade's inside check: standing at the claim post (x 6 to 10, z 34.2 to 36.2), coming from outside or from inside
	local atPost = nil
	for _, x in ipairs({ PB.ClaimPost.x0, LOBBY_POST.x, (PB.ClaimPost.x0 + PB.ClaimPost.x1) / 2, PB.ClaimPost.x1 }) do
		for _, z in ipairs({ PB.ClaimPost.z0, LOBBY_POST.z, PB.ClaimPost.z1 }) do
			for _, y in ipairs({ PB.GROUND, 2, 5 }) do
				for _, was in ipairs({ false, true }) do
					if PBV.isInside(L.inside, x, y, z, was) then atPost = atPost or string.format("%g, %g, %g (was inside: %s)", x, y, z, tostring(was)) end
				end
			end
		end
	end
	check("claim post: standing at the claim post is outside at stage " .. s .. " (the apron is only as wide as the lane, " .. PB.Lane.half .. " each side)",
		atPost == nil and L.inside.doorMinX == -PB.Lane.half and L.inside.doorMaxX == PB.Lane.half, atPost)
	-- pieces: in front only to OUTSIDE_TO, never past the lot's sides and back; the shell's walls on the lot's front line
	local far = nil
	for _, p in ipairs(L.pieces) do
		local b = pieceBox(p)
		if b[1] < -PB.Lot.half - 0.01 or b[2] > PB.Lot.half + 0.01 or b[5] < PB.Lot.back - 0.01 or b[6] > PB.OUTSIDE_TO + 0.01 then far = far or p.name end
		if string.find(p.name, "Front", 1, true) and b[6] > PB.Lot.front + 0.01 then far = far or p.name end
	end
	check("lot: every piece of stage " .. s .. " stands inside the lot (pieces in front of the facade up to z " .. PB.OUTSIDE_TO .. ")", far == nil, far)
	-- the style table
	local nostyle = nil
	for _, p in ipairs(L.pieces) do
		for role in pairs(PB.rolesOf(p)) do
			local st = PB.styleOf(s, p.key, role, p.look)
			if not st or type(st.color) ~= "table" or #st.color ~= 3 or not PB.MATERIALS[st.material] or not (st.transparency >= 0 and st.transparency < 1) then
				nostyle = nostyle or (p.key .. "." .. role)
			elseif st.material == "Neon" and not PB.NEON_KEYS[p.key] then
				nostyle = nostyle or (p.key .. "." .. role .. " Neon")
			end
		end
	end
	check("style: stage " .. s .. "'s table has every role of every key it uses (a color, an allowed material, Neon only on a light)", nostyle == nil, nostyle)
	-- the budget, both ways
	local kitParts, fbParts = #L.boxes, #L.boxes
	for _, p in ipairs(L.pieces) do
		for _ in pairs(PB.rolesOf(p)) do kitParts += 1 end
		fbParts += #PB.partsOf(p)
	end
	check("budget: stage " .. s .. " is at most " .. PB.Budget.parts .. " parts, kit MeshParts plus boxes (" .. kitParts .. ")", kitParts <= PB.Budget.parts, kitParts)
	check("budget: stage " .. s .. " is at most " .. PB.Budget.parts .. " parts built from Parts too (" .. fbParts .. ")", fbParts <= PB.Budget.parts, fbParts)
	-- the shell fades: every piece but the furniture and the band's floor is in Fade (the roof included)
	local wrong = nil
	for _, p in ipairs(L.pieces) do
		local inside = string.find(p.name, "Furniture", 1, true) or string.find(p.name, "Band", 1, true)
		if (inside and p.group ~= "Static") or (not inside and p.group ~= "Fade") then wrong = wrong or p.name end
	end
	check("fade: at stage " .. s .. " the roof and every wall, door and outside piece are in Fade, the furniture and the band's floor in Static", wrong == nil, wrong)
	-- the furniture band
	local band = LAYOUTS[s]
	local inner, backInner = band.footprint.x1 - PB.WALL, band.footprint.z0 + PB.WALL
	local def = PB.Stages[s]
	local inRoom, deep, clash, zone = nil, nil, nil, nil
	local zones = PlotVisuals.zones(PlotArt.Layout)
	for i, f in ipairs(L.furniture) do
		local fb = { f.x0, f.x1, 0, f.top, f.z0, f.z1 }
		if f.x1 > -PB.Room.half and f.x0 < PB.Room.half and f.z1 > -PB.Room.half and f.z0 < PB.Room.half then inRoom = inRoom or f.key end
		local limit = (f.side == "back") and (def.backBand or PB.BAND) or PB.BAND
		local depth = (f.side == "back") and (f.z1 - backInner) or (f.side == "left" and (f.x1 + inner) or (inner - f.x0))
		if depth > limit + 1e-6 or f.x0 < -inner - 1e-6 or f.x1 > inner + 1e-6 or f.z0 < backInner - 1e-6 or f.z1 > PB.FRONT_IN + 1e-6 then deep = deep or f.key end
		for j = i + 1, #L.furniture do
			local g = L.furniture[j]
			if overlaps(fb, { g.x0, g.x1, 0, g.top, g.z0, g.z1 }) then clash = clash or (f.key .. "/" .. g.key) end
		end
		for _, z in ipairs(zones) do if overlaps(fb, z.box) then zone = zone or (f.key .. " in " .. z.name) end end
		if overlaps(fb, laneBox) then zone = zone or (f.key .. " in the lane") end
	end
	check("furniture: at stage " .. s .. " every piece of furniture is outside the 60 x 60 room", inRoom == nil, inRoom)
	check("furniture: at stage " .. s .. " it stands in a band at most " .. PB.BAND .. " deep along the shell's inner faces (back band " .. (def.backBand or PB.BAND) .. ")", deep == nil, deep)
	check("furniture: at stage " .. s .. " no two pieces overlap, none is in a reserved zone or the lane", clash == nil and zone == nil, clash or zone)
	check("furniture: stage " .. s .. "'s footprints are listed for customize PR 2 (PlotBuilding.furnitureFootprints)", #PB.furnitureFootprints(s) == #def.furniture)
end
-- the offices' door: the WallDoor and its DoorLeaf stretched 1.5 along X (24 and 9 wide): the opening is the lane
for s = 2, 3 do
	local door, leaf = nil, nil
	for _, p in ipairs(LAYOUTS[s].pieces) do
		if p.key == "WallDoor" then door = p elseif p.key == "DoorLeaf" then leaf = p end
	end
	check("door: at stage " .. s .. " the WallDoor is stretched 1.5 (24 wide) in the middle of the facade and its DoorLeaf too (9 wide), the leaf beside the lane",
		door ~= nil and leaf ~= nil and near(door.sx, 1.5) and near(door.x, 0) and near(door.z, PB.FRONT_OUT - PB.WALL / 2) and near(leaf.sx, 1.5)
		and pieceBox(leaf)[2] <= -PB.Lane.half + EPS, door and door.sx)
end
-- the furniture each stage adds (the owner's list)
do
	local function keys(s) local t = {} for _, f in ipairs(PB.Stages[s].furniture) do t[f.key] = (t[f.key] or 0) + 1 end return t end
	local k2, k3, k4, k5 = keys(2), keys(3), keys(4), keys(5)
	check("furniture: Small Office has ReceptionDesk, Plant, Sofa", k2.ReceptionDesk and k2.Plant and k2.Sofa and #PB.Stages[1].furniture == 0)
	check("furniture: Big Office adds CoffeeMachine, Whiteboard, Shelf", k3.ReceptionDesk and k3.CoffeeMachine and k3.Whiteboard and k3.Shelf)
	check("furniture: Small Corporate adds Armchairs, LobbyTrees, ServerRack", k4.Shelf and (k4.Armchair or 0) >= 2 and (k4.LobbyTree or 0) >= 2 and k4.ServerRack)
	check("furniture: Big Corporate adds BoardTable, Rug, Bell", k5.ServerRack and k5.BoardTable and k5.Rug and k5.Bell)
end
-- the looks the owner asked for
do
	local function has(s, key) for _, p in ipairs(LAYOUTS[s].pieces) do if p.key == key then return true end end return false end
	local function stories(s) return (LAYOUTS[s].height + 1) / PB.STORY end
	check("look: Garage: one story, Corner posts, WallGarage with the GarageDoor rolled up, a BareBulb, WallWindow, RoofEdge",
		stories(1) == 1 and has(1, "Corner") and has(1, "WallGarage") and has(1, "GarageDoor") and has(1, "BareBulb") and has(1, "WallWindow") and has(1, "RoofEdge"))
	-- the Garage's pitched roof: the sheets' top faces run on the slope from 1 past the side walls to the ridge, and the
	-- gables (front and back) reach that top face at every x: crow steps, never a gap under the sheets
	do
		local L, mass = LAYOUTS[1], PB.Stages[1].masses[1]
		local pitch, h = mass.pitch, mass.half
		local tierH = PB.KitManifest.RoofEdge.size[2]
		local eave = PB.GROUND + PB.STORY * mass.to + tierH
		local function roofTop(x) return eave + (h - math.abs(x)) * pitch.slope end
		local sheets, ends = 0, true
		local gables = { F = {}, B = {} }
		for _, p in ipairs(L.pieces) do
			if string.find(p.name, "Pitch", 1, true) then
				sheets += 1
				local f = PBV.pieceFrame(CFrame.new(), p)
				local T, len = p.size[2], p.size[3]
				local inner, outer = f * Vector3.new(0, T, -len / 2), f * Vector3.new(0, T, len / 2)
				local side = p.x < 0 and -1 or 1
				local reach = h + pitch.overhang
				if not (near(inner.X, 0, 1e-4) and near(inner.Y, roofTop(0), 1e-4) and near(outer.X, side * reach, 1e-4) and near(outer.Y, roofTop(reach), 1e-4)
					and near(p.size[1], (mass.front - PB.WALL) - (mass.back + PB.WALL), 1e-4)) then ends = false end
			end
			local g, k = string.match(p.name, "Gable(%u)(%d+)")
			if g then table.insert(gables[g], { half = p.size[1] / 2, top = p.y + p.size[2] }) end
		end
		check("roof: the Garage has a pitched roof: two sheets whose top faces run on the slope from 1 past the side walls (the eave) to the ridge, over the whole depth",
			sheets == 2 and ends, sheets)
		local gap = nil
		for _, g in ipairs({ "F", "B" }) do
			if #gables[g] == 0 then gap = gap or (g .. ": no gable") end
			for x = -h, h, 0.5 do
				local high = -math.huge
				for _, t in ipairs(gables[g]) do if math.abs(x) <= t.half + 1e-6 then high = math.max(high, t.top) end end
				if high < roofTop(x) - 1e-6 then gap = gap or string.format("%s at x %g: the gable ends at %g, the roof at %g", g, x, high, roofTop(x)) end
			end
		end
		check("roof: the Garage's stepped gables (front and back) reach the roof's top at every x (no gap under the sheets)", gap == nil, gap)
		local sign, plate = 0, nil
		for _, p in ipairs(L.pieces) do
			if string.sub(p.name, 1, 4) == "Sign" then
				sign += 1
				local b = pieceBox(p)
				if p.name == "SignPlate" then plate = b end
				if b[3] < PB.Stages[1].door.top or b[5] < PB.FRONT_OUT - 1e-6 then sign = -100 end
			end
		end
		local function mat(role, look) local st = PB.styleOf(1, PB.BLOCK, role, look) return st and st.material end
		check("look: the Garage's roof sheets are rusty sheet metal (CorrodedMetal), its gables brick, its sign board dark metal on a concrete plate",
			mat("main", "pitch") == "CorrodedMetal" and mat("main", nil) == "Brick" and mat("dark", "sign") == "Metal" and mat("trim", "sign") == "Concrete",
			tostring(mat("main", "pitch")))
		check("sign: the Garage has a sign over its door: a plate on the facade, a board and three bars, all above the opening and in front of the wall",
			sign == 5 and plate ~= nil and near((plate[1] + plate[2]) / 2, 0), sign)
	end
	check("look: Small Office: one story, WallDoor with a DoorLeaf, WallWindow, Plants, RoofEdge",
		stories(2) == 1 and has(2, "WallDoor") and has(2, "DoorLeaf") and has(2, "WallWindow") and has(2, "Plant") and has(2, "RoofEdge"))
	check("look: Big Office: two stories, WallWindow and WallGlass, RoofEdge", stories(3) == 2 and has(3, "WallWindow") and has(3, "WallGlass") and has(3, "WallDoor"))
	check("look: Small Corporate: four stories, WallGlass, an open entrance between two pillars (no RevolvingDoor: players walked through its post)",
		stories(4) == 4 and has(4, "WallGlass") and has(4, "Corner") and not has(4, "RevolvingDoor"))
	check("look: Big Corporate: six stories, Columns, a RoofCrown", stories(5) == 6 and has(5, "Column") and has(5, "RoofCrown")
		and stories(5) > stories(4))
	check("look: HQ Tower (overhaul 2): the tallest (seven stories), Columns, a RoofCrown", stories(6) == 7 and has(6, "Column") and has(6, "RoofCrown")
		and stories(6) > stories(5))
	local mats = {}
	for s = 1, 5 do mats[s] = PB.styleOf(s, "Wall", "main").material end
	check("look: Brick for the garage, Concrete for the office, white brick for the loft, Glass for the tower, Marble for the headquarters (overhaul 2 phase 6)",
		mats[1] == "Brick" and mats[2] == "Concrete" and mats[3] == "Brick" and mats[4] == "Glass" and mats[5] == "Marble" and PB.styleOf(5, "Column", "accent").color[1] == 255)
	local want = { "WallGarage", "WallDoor", "WallDoor", "none", "none", "none" }
	local wrong = nil
	for s = 1, 6 do
		for _, p in ipairs(LAYOUTS[s].pieces) do
			if p.lane and p.key ~= want[s] then wrong = wrong or (s .. " " .. p.name) end
		end
	end
	check("lane: only the door piece may stand in the lane (stage 1 the WallGarage, 2 and 3 the WallDoor, none at 4 to 6), never solid", wrong == nil, wrong)
end
"""

BUILD_TESTS = r"""
local function countBlocks(L) local n = 0 for _, p in ipairs(L.pieces) do if p.key == PB.BLOCK then n += 1 end end return n end
-- 4. Every stage built at four turns, with the kit, with the kit imported turned around, and from Parts --------------
local zones = PlotVisuals.zones(PlotArt.Layout)
local KITS = { { name = "kit", kit = makeKit(0), turn = 0, front = 0 }, { name = "kit imported turned 180", kit = makeKit(180), turn = 180, front = 180 },
	{ name = "no kit", kit = nil } }
local laneBox = { -PB.Lane.half, PB.Lane.half, PB.GROUND, PB.Lane.top, PB.Lane.from, PB.Lane.to }
local postBox = { PB.ClaimPost.x0, PB.ClaimPost.x1, PB.GROUND, PB.ClaimPost.top, PB.ClaimPost.z0, PB.ClaimPost.z1 }
local landBox = { PB.Landing.x - PB.Landing.half, PB.Landing.x + PB.Landing.half, 0, PB.Landing.top, PB.Landing.z - PB.Landing.half, PB.Landing.z + PB.Landing.half }
local apronBox = { -PB.Lane.half, PB.Lane.half, PB.GROUND, PB.Lane.top, PB.FRONT_OUT, PB.FRONT_OUT + PB.APRON }
local results = {}
for s = 1, 6 do
	local L = PB.layout(s)
	local laneOk = {}
	for _, p in ipairs(L.pieces) do if p.lane then laneOk[p.name] = true end end
	local rooms = {}
	for _, turn in ipairs({ 0, 90, 180, 270 }) do
		local frame = frameAt(turn)
		local origin = topOf(frame)
		local rb = roomBoxes(frame, s)
		local built = {}
		for _, K in ipairs(KITS) do
			PB.KIT_FRONT_TURN = K.front or 0
			PBV.resetWarnings()
			local m = PBV.build(nil, frame, PB, s, K.kit)
			built[K.name] = m
			local tag = "stage " .. s .. " at " .. turn .. " (" .. K.name .. ")"
			local problems = PBV.check(m, frame, PB, { zones = zones, roomBoxes = rb })
			check("check: PlotBuildingVisuals.check finds nothing wrong with " .. tag, #problems == 0, problems[1])
			local solids, meshSolid, partSolid, flags, lane, apron, post, land, zone, hidden, room, mats = 0, nil, nil, nil, nil, nil, nil, nil, nil, nil, nil, nil
			local count = 0
			for _, d in ipairs(m:GetDescendants()) do
				if d:IsA("BasePart") then
					count += 1
					local b = inFrame(origin, d)
					local isSolid = d.Parent.Name == "Solid"
					if d.CanCollide then
						solids += 1
						if not isSolid then
							if d.ClassName == "MeshPart" then meshSolid = meshSolid or d.Name else partSolid = partSolid or d.Name end
						end
					end
					if isSolid then
						if d.CanTouch or not d.Anchored or d.Transparency < 1 or not d.CanCollide then flags = flags or d.Name end
						if overlaps(b, laneBox) then lane = lane or d.Name end
					else
						if d.CanTouch or d.CanQuery or not d.Anchored or d.CastShadow then flags = flags or d.Name end
						if overlaps(b, laneBox) and b[4] - b[3] > 0.25 and not laneOk[d:GetAttribute("Piece")] then lane = lane or d.Name end
						if not PB.MATERIALS[d.Material.Name] then mats = mats or d.Name end
					end
					if overlaps(b, apronBox) and not laneOk[d:GetAttribute("Piece")] and b[4] - b[3] > 0.25 then apron = apron or d.Name end
					if overlaps(b, postBox) then post = post or d.Name end
					if overlaps(b, landBox) then land = land or d.Name end
					for _, z in ipairs(zones) do if overlaps(b, z.box) then zone = zone or (d.Name .. " in " .. z.name) end end
					-- at full fade: the shell reaches 1, the boxes are 1 already (the camera ignores both)
					if d.Parent.Name == "Fade" then
						if PBV.occludedTransparency(d.Transparency, 1, PB.Fade.occluded) < 0.25 then hidden = hidden or d.Name end
					elseif isSolid and d.Transparency < 0.25 then hidden = hidden or d.Name end
					for _, r in ipairs(rb) do
						local mark = r.box[4] - r.box[3] <= 0.25 and r.box[3] <= PB.GROUND + 0.3
						if not mark and overlaps(b, r.box) then room = room or (d.Name .. " in " .. r.name) end
					end
				end
			end
			check("solid: " .. tag .. ": exactly the layout's boxes are solid (" .. #L.boxes .. ")", solids == #L.boxes and meshSolid == nil and partSolid == nil, meshSolid or partSolid or solids)
			check("flags: " .. tag .. ": every kit MeshPart and fallback Part is anchored, CanCollide, CanTouch and CanQuery off, no shadow; every box anchored, CanTouch off, Transparency 1",
				flags == nil and meshSolid == nil, flags or meshSolid)
			check("lane: " .. tag .. ": nothing stands in the doorway lane but the door piece", lane == nil, lane)
			check("apron: " .. tag .. ": the apron in front of the door is clear", apron == nil, apron)
			check("claim post: " .. tag .. ": its spot (x 6 to 10, 3 in front of the wall) is clear", post == nil, post)
			check("landing: " .. tag .. ": the respawn landing is clear", land == nil, land)
			check("zones: " .. tag .. ": no part in a reserved zone (signs, spawn, lane, incubators, hire spots and desks, upgrade slots, aisles)", zone == nil, zone)
			check("room: " .. tag .. ": no part goes into a part of the room or the six props (stage 1's flat yard marks aside)", room == nil, room)
			check("fade: " .. tag .. ": in the camera's way (occluded) every shell part is at least 0.25 transparent, every box is 1 (the camera's popper ignores both)", hidden == nil, hidden)
			check("budget: " .. tag .. ": " .. count .. " parts, at most " .. PB.Budget.parts, count <= PB.Budget.parts, count)
			check("materials: " .. tag .. ": allowed materials only", mats == nil, mats)
			if s == 2 or s == 3 then
				local inLane, left, right = nil, -math.huge, math.huge
				for _, d in ipairs(m:GetDescendants()) do
					if d:IsA("BasePart") and d:GetAttribute("Key") == "WallDoor" then
						local b = inFrame(origin, d)
						if overlaps(b, laneBox) then inLane = inLane or d.Name end
						if b[3] < PB.Lane.top - 0.01 then -- the jambs (below the opening's top)
							if b[2] <= 0 then left = math.max(left, b[2]) else right = math.min(right, b[1]) end
						end
					end
				end
				check("door: " .. tag .. ": no part of the WallDoor's frame stands inside the 9-wide lane; the opening is exactly 9, its jambs on the lane's edges",
					inLane == nil and near(left, -PB.Lane.half, 1e-4) and near(right, PB.Lane.half, 1e-4), inLane or (left .. " " .. right))
			end
			check("attributes: " .. tag .. ": the Frame and the inside box the client reads",
				m:GetAttribute("Frame") == nil and false or (function()
					local fr = m:GetAttribute("Frame")
					local ok = typeof(fr) == "CFrame"
					for field, attr in pairs(PBV.ATTRIBUTES) do if m:GetAttribute(attr) ~= L.inside[field] then ok = false end end
					return ok and near((origin.Position - fr.Position).Magnitude, 0) and m:GetAttribute("Stage") == s
				end)())
			if K.kit then
				local blocks = countBlocks(L)
				check("kit: " .. tag .. ": every piece is built from the kit (" .. (#L.pieces - blocks) .. "), every Block as one Part (" .. blocks .. ")",
					m:GetAttribute("KitPieces") == #L.pieces - blocks and m:GetAttribute("PartPieces") == 0 and m:GetAttribute("BlockPieces") == blocks,
					tostring(m:GetAttribute("KitPieces")) .. " / " .. tostring(m:GetAttribute("PartPieces")) .. " / " .. tostring(m:GetAttribute("BlockPieces")))
				local onlyMesh, blockParts = true, 0
				for _, d in ipairs(m:FindFirstChild("Fade"):GetDescendants()) do
					if d:IsA("BasePart") and d.ClassName ~= "MeshPart" then
						if d.ClassName == "Part" and d:GetAttribute("Key") == PB.BLOCK then blockParts += 1 else onlyMesh = false end
					end
				end
				check("kit: " .. tag .. ": the shell is MeshParts only, but for the Blocks (one Part each)", onlyMesh and blockParts == blocks, blockParts)
			else
				check("fallback: " .. tag .. ": every piece is built from Parts, with one warning for the missing kit",
					m:GetAttribute("PartPieces") == #L.pieces - countBlocks(L) and m:GetAttribute("BlockPieces") == countBlocks(L) and #WARNED >= 1)
			end
			-- The sign's text (overhaul phase 1): the building's one gui is the SurfaceGui on the sign board, with one empty TextLabel until
			-- the server writes it (setSign); no other gui, no decal, no texture anywhere
			local text, guis, labels, board = nil, 0, 0, nil
			for _, d in ipairs(m:GetDescendants()) do
				if d.ClassName == "SurfaceGui" then
					guis += 1
					if d.Name == PBV.SIGN_TEXT_NAME and d.Parent and d.Parent:GetAttribute("Piece") == "SignBoard" and d.Parent.Parent == m:FindFirstChild("Fade") then board = d end
				elseif d.ClassName == "TextLabel" then
					labels += 1
					if d.Text ~= "" then text = text or (d.Name .. "=" .. d.Text) end
				elseif d.ClassName == "BillboardGui" or d.ClassName == "Decal" or d.ClassName == "Texture" then text = text or d.Name end
			end
			local signOk = guis == 1 and labels == 1 and board ~= nil and board.Label ~= nil and text == nil
			if signOk then
				PBV.setSign(m, "Ana's Startup", "Small Office")
				signOk = board.Label.Text == "Ana's Startup\nSmall Office"
				PBV.setSign(m, "FREE", "Claim this garage")
				signOk = signOk and board.Label.Text == "FREE\nClaim this garage"
				PBV.setSign(m, "", nil)
				signOk = signOk and board.Label.Text == ""
			end
			local byPiece, blockBad = {}, nil
			for _, d in ipairs(m:GetDescendants()) do
				if d:IsA("BasePart") and d:GetAttribute("Key") == PB.BLOCK then byPiece[d:GetAttribute("Piece")] = d end
			end
			for _, p in ipairs(L.pieces) do
				if p.key == PB.BLOCK then
					local d, want = byPiece[p.name], pieceBox(p)
					if not d then blockBad = blockBad or (p.name .. " missing") else
						local b = inFrame(origin, d)
						for k = 1, 6 do if not near(b[k], want[k], 1e-4) then blockBad = blockBad or (p.name .. " box") end end
						if d.Material.Name ~= PB.styleOf(s, PB.BLOCK, p.role, p.look).material then blockBad = blockBad or (p.name .. " style") end
					end
				end
			end
			check("block: " .. tag .. ": every Block is one Part at its size, where the layout puts it, painted by its role", blockBad == nil, blockBad)
			check("text: " .. tag .. ": the one gui is the sign board's SurfaceGui (one TextLabel, empty until the server writes it with setSign); no other gui, decal or texture", signOk, text or (guis .. " guis, " .. labels .. " labels"))
		end
		-- The kit and the fallback build the same pieces (same roles, same boxes): the turn of the kit's front is right
		local a, b = piecesOf(built["kit"], frame), piecesOf(built["no kit"], frame)
		local same, why = samePieces(a, b)
		check("kit front: stage " .. s .. " at " .. turn .. ": the kit (KIT_FRONT_TURN 0) builds every piece exactly where the Parts version stands", same, why)
		local c = piecesOf(built["kit imported turned 180"], frame)
		local same2, why2 = samePieces(c, b)
		check("kit front: stage " .. s .. " at " .. turn .. ": a kit imported turned around, with KIT_FRONT_TURN 180, builds every piece where the Parts version stands", same2, why2)
		local boxesA, boxesB = {}, {}
		for _, d in ipairs(built["kit"]:FindFirstChild("Solid"):GetChildren()) do boxesA[d.Name] = inFrame(origin, d) end
		for _, d in ipairs(built["no kit"]:FindFirstChild("Solid"):GetChildren()) do boxesB[d.Name] = inFrame(origin, d) end
		local sameBoxes = true
		for n, bx in pairs(boxesA) do
			if not boxesB[n] then sameBoxes = false else for k = 1, 6 do if not near(bx[k], boxesB[n][k]) then sameBoxes = false end end end
		end
		for n in pairs(boxesB) do if not boxesA[n] then sameBoxes = false end end
		check("fallback: stage " .. s .. " at " .. turn .. ": the Parts version builds the same solid boxes as the kit", sameBoxes)
		if turn ~= 0 then
			-- at a turn, the building is the 0-degree one turned: compare in each garage's own frame
			local zero = piecesOf(results[s], frameAt(0))
			local same3, why3 = samePieces(a, zero)
			check("turn: stage " .. s .. " at " .. turn .. ": in its garage's frame the building is the same as at 0", same3, why3)
		else
			results[s] = built["kit"]
		end
	end
	PB.KIT_FRONT_TURN = 0
end
-- The check is sensitive: a kit imported turned around with KIT_FRONT_TURN left at 0 faces backward
do
	PB.KIT_FRONT_TURN = 0
	local frame = frameAt(0)
	local wrong = piecesOf(PBV.build(nil, frame, PB, 5, makeKit(180)), frame)
	local right = piecesOf(PBV.build(nil, frame, PB, 5, nil), frame)
	check("kit front: a kit imported turned around with KIT_FRONT_TURN left at 0 faces backward, and the kit front check sees it", not samePieces(wrong, right))
end

-- 5. Kit details: a missing key, extras in a model, a stretch the builder refuses, the kit check ------------------------
do
	PBV.resetWarnings()
	WARNED = {}
	local kit = makeKit(0, { WallGarage = true })
	local m = PBV.build(nil, frameAt(0), PB, 1, kit)
	local partPieces = m:GetAttribute("PartPieces")
	local warnings = 0
	for _, w in ipairs(WARNED) do if string.find(w, "WallGarage", 1, true) then warnings += 1 end end
	check("fallback: a missing key (WallGarage) is built from Parts, the rest from the kit, with one warning", partPieces == 1 and warnings == 1, partPieces .. " " .. warnings)
	PBV.build(nil, frameAt(0), PB, 1, kit)
	local again = 0
	for _, w in ipairs(WARNED) do if string.find(w, "WallGarage", 1, true) then again += 1 end end
	check("fallback: building it again does not warn again (one warning per server)", again == 1, again)
end
do
	PBV.resetWarnings()
	WARNED = {}
	local kit = makeKit(0)
	local wall = kit:FindFirstChild("Wall")
	local script = Instance.new("Script")
	script.Name = "Sneaky"
	script.Parent = wall
	local plain = Instance.new("Part")
	plain.Name = "PlainPart"
	plain.Parent = wall
	local m = PBV.build(nil, frameAt(0), PB, 2, kit)
	local foreign = nil
	for _, d in ipairs(m:GetDescendants()) do
		if d.ClassName == "Script" or d.Name == "Sneaky" or (d:IsA("BasePart") and d.Parent.Name == "Fade" and d.ClassName ~= "MeshPart" and d:GetAttribute("Key") ~= PB.BLOCK) then foreign = foreign or d.Name end
	end
	local warnings = 0
	for _, w in ipairs(WARNED) do if string.find(w, "only MeshParts", 1, true) then warnings += 1 end end
	check("kit: only MeshParts are used: a Script and a Part inside KitModels.Wall are left out, with one warning", foreign == nil and warnings == 1, foreign or warnings)
end
do
	PBV.resetWarnings()
	local piece = { name = "Test", key = "Column", x = 0, y = -1, z = 0, turn = 0, sx = 3, sz = 1 }
	local sx, sz = PBV.stretchOf(PB, piece)
	local f = Instance.new("Folder")
	local m = PBV.build(nil, frameAt(0), PB, 5, makeKit(0))
	local col = nil
	for _, d in ipairs(m:FindFirstChild("Fade"):GetDescendants()) do if d:GetAttribute("Key") == "Column" and d:GetAttribute("Role") == "main" then col = d break end end
	check("stretch: the builder refuses to stretch a Column (built at its kit size 3 x 14 x 3)", sx == 1 and sz == 1 and col and near(col.Size.X, 3) and near(col.Size.Z, 3))
	local wall = { name = "W", key = "Wall", x = 0, y = -1, z = 0, turn = 0, sx = 2, sz = 3 }
	local wx, wz = PBV.stretchOf(PB, wall)
	check("stretch: a Wall may stretch along X only (a Z stretch is refused)", wx == 1 and wz == 1)
	local floor = { name = "F", key = "Floor", x = 0, y = -1, z = 0, turn = 0, sx = 2, sz = 3 }
	local fx, fz = PBV.stretchOf(PB, floor)
	check("stretch: a Floor may stretch along X and Z", fx == 2 and fz == 3)
end
do
	-- a MeshPart with Archivable off: Clone gives nil, so that piece is built from Parts (never an error)
	PBV.resetWarnings()
	WARNED = {}
	local kit = makeKit(0)
	local wallPart = kit:FindFirstChild("Wall") and kit.Wall:FindFirstChildOfClass("MeshPart")
	if wallPart then wallPart.Archivable = false end
	local walls = 0
	for _, p in ipairs(PB.layout(2).pieces) do if p.key == "Wall" then walls += 1 end end
	local ok, m = pcall(PBV.build, nil, frameAt(0), PB, 2, kit)
	local warnings = 0
	for _, w in ipairs(WARNED) do if string.find(w, "Archivable", 1, true) then warnings += 1 end end
	local okPiece, piece, fromKit = pcall(PBV.buildPiece, nil, frameAt(0), PB, 2, { name = "W", key = "Wall", x = 0, y = -1, z = 0, turn = 0, sx = 1, sz = 1 }, kit)
	check("kit: a MeshPart with Archivable off (Clone gives nil): its pieces are built from Parts, with one warning, never an error",
		wallPart ~= nil and ok and m:GetAttribute("PartPieces") == walls and m:GetAttribute("KitPieces") == #PB.layout(2).pieces - walls - countBlocks(PB.layout(2)) and warnings == 1
		and okPiece and fromKit == false and #piece:GetChildren() > 0, ok and (tostring(m:GetAttribute("PartPieces")) .. " " .. warnings) or m)
end
do
	-- float noise: a KitSize of 3.0004 is no stretch, so a part turned in its model (not square to it) still comes from the kit
	PBV.resetWarnings()
	WARNED = {}
	local kit = makeKit(0)
	local plant = kit:FindFirstChild("Plant")
	plant:SetAttribute("KitSize", Vector3.new(3.0004, 5, 3))
	local leaves = nil
	for _, d in ipairs(plant:GetChildren()) do if d:GetAttribute("Role") == "main" then leaves = d end end
	leaves.CFrame = leaves.CFrame * CFrame.Angles(0, math.rad(30), 0)
	local m = PBV.build(nil, frameAt(0), PB, 2, kit)
	local warned = 0
	for _, w in ipairs(WARNED) do if string.find(w, "Plant", 1, true) then warned += 1 end end
	check("stretch: float noise in KitSize (3.0004 for 3) is no stretch: a Plant with a turned part is still built from the kit",
		m:GetAttribute("PartPieces") == 0 and m:GetAttribute("KitPieces") == #PB.layout(2).pieces - countBlocks(PB.layout(2)) and warned == 0, tostring(m:GetAttribute("PartPieces")) .. " " .. warned)
end
do
	local ok = PBV.checkKit(makeKit(0, nil, true), PB.KitManifest)
	check("checkKit: the fake KitModels (36 keys, right sizes and roles, one MeshPart per role, pivots at the bottom-center) is OK", #ok == 0, ok[1])
	local turned = PBV.checkKit(makeKit(180, nil, true), PB.KitManifest)
	check("checkKit: a kit imported turned around is OK too (the pivot is still the bottom-center)", #turned == 0, turned[1])
	check("checkKit: no KitModels folder", #PBV.checkKit(nil, PB.KitManifest) == 1)
	local kit = makeKit(0, { Bell = true }, true)
	local p1 = PBV.checkKit(kit, PB.KitManifest)
	check("checkKit: a missing key is named", #p1 == 1 and string.find(p1[1], "Bell", 1, true) ~= nil, p1[1])
	kit = makeKit(0, nil, true)
	kit:FindFirstChild("Sofa").WorldPivot = kit:FindFirstChild("Sofa").WorldPivot * CFrame.new(0.5, 0, 0)
	kit:FindFirstChild("Shelf").WorldPivot = kit:FindFirstChild("Shelf").WorldPivot * CFrame.new(0, -0.3, 0)
	kit:FindFirstChild("Rug").WorldPivot = kit:FindFirstChild("Rug").WorldPivot * CFrame.new(0.04, 0.04, -0.04)
	local pv = PBV.checkKit(kit, PB.KitManifest)
	local joined = table.concat(pv, "|")
	check("checkKit: a WorldPivot off the bottom-center is named (0.5 to the side, 0.3 too low); 0.04 off is OK",
		#pv == 2 and string.find(joined, "Sofa: WorldPivot", 1, true) ~= nil and string.find(joined, "Shelf: WorldPivot", 1, true) ~= nil, joined)
	kit = makeKit(0, nil, true)
	local desk = kit:FindFirstChild("Desk")
	local copy = desk:FindFirstChildOfClass("MeshPart"):Clone()
	copy.Name = "main99"
	copy:SetAttribute("Role", "main")
	copy.Parent = desk
	local dup = PBV.checkKit(kit, PB.KitManifest)
	check("checkKit: two MeshParts with the same role are named (the kit has one per role)", #dup == 1 and string.find(dup[1], "a second MeshPart with role main", 1, true) ~= nil, dup[1])
	kit = makeKit(0, nil, true)
	kit:FindFirstChild("Sofa"):SetAttribute("KitSize", Vector3.new(8, 4.2, 4))
	kit:FindFirstChild("Desk"):FindFirstChildOfClass("MeshPart"):SetAttribute("Role", "mian")
	local p2 = PBV.checkKit(kit, PB.KitManifest)
	local joined = table.concat(p2, "|")
	check("checkKit: a size off by 0.2 and a wrong role are both named", string.find(joined, "Sofa: KitSize", 1, true) ~= nil and string.find(joined, "mian", 1, true) ~= nil, joined)
	kit = makeKit(0, nil, true)
	kit:FindFirstChild("Rug"):SetAttribute("KitSize", Vector3.new(12.04, 0.2, 7.96))
	check("checkKit: a size within 0.05 is OK", #PBV.checkKit(kit, PB.KitManifest) == 0)
end

-- 6. sync, and a stage change never traps a player ---------------------------------------------------------------------
do
	local garage = Instance.new("Model")
	local frame = frameAt(90)
	local m1, c1 = PBV.sync(garage, frame, PB, 1, nil)
	local m2, c2 = PBV.sync(garage, frame, PB, 1, nil)
	check("sync: the same stage again does nothing (the same Model, not rebuilt)", m1 == m2 and c1 == true and c2 == false)
	local m3, c3 = PBV.sync(garage, frame, PB, 4, nil)
	local count = 0
	for _, c in ipairs(garage:GetChildren()) do if c.Name == "PlotBuilding" then count += 1 end end
	check("sync: a new stage replaces the building (one Model, the old one destroyed)", c3 and m3 ~= m1 and count == 1 and rawget(m1, "destroyed") == true)
	local m4 = PBV.sync(garage, frame, PB, 12, nil)
	check("sync: a stage past the last shows the last", m4:GetAttribute("Stage") == 6)
check("streaming: every building Model is Persistent (its shell never streams out across the plaza)", m4.ModelStreamingMode == Enum.ModelStreamingMode.Persistent)
	-- a visitor stands in Big Corporate's band; an IPO brings back the Garage, whose wall stands there
	local origin = PBV.originOf(frame, PB)
	local root = Instance.new("Part")
	root.CFrame = origin * CFrame.new(33, 2, 0) -- in the Garage's right wall (x 32 to 34)
	local safe = Instance.new("Part")
	safe.CFrame = origin * CFrame.new(0, 3, 0)
	local landing = frame * CFrame.new(0, 4, 12)
	local m5 = PBV.sync(garage, frame, PB, 1, nil)
	local moved = PBV.unstick(m5, { root, safe }, landing)
	check("unstick: a character standing where the new building's wall is goes to the landing; one in the room stays",
		moved == 1 and near((root.Position - landing.Position).Magnitude, 0) and near((safe.Position - (origin * Vector3.new(0, 3, 0))).Magnitude, 0))
	-- the top of a jump under the Garage's roof (the roof box from 12.5; this body reaches 12.6): never moved
	local jumper = Instance.new("Part")
	jumper.CFrame = origin * CFrame.new(5, 10.6, -5)
	local m6 = PBV.sync(garage, frame, PB, 3, nil)
	local m7 = PBV.sync(garage, frame, PB, 1, nil)
	local movedJump = PBV.unstick(m7, { jumper }, landing)
	check("unstick: a player mid-jump under the roof (overlapping the roof box) is not moved: only walls and floors count",
		m6 ~= m7 and movedJump == 0 and near((jumper.Position - (origin * Vector3.new(5, 10.6, -5))).Magnitude, 0), movedJump)
end

-- 7. Six garages at the biggest stage, and the plaza: under 4,000 parts (overhaul 2: 3,000 -> 3,200 for the HQ Tower; phase 2:
-- 3,200 -> 4,000 for the catalog items in the rooms and the solid boxes, about 35 per room, which are invisible) -----------
do
	local room = 0
	for stage = 1, #PlotArt.Stages do -- the biggest room with its six props and every catalog item of its stage
		local r = PlotVisuals.buildRoom(nil, frameAt(0), PlotArt, stage)
		for _, slot in ipairs(PlotArt.Layout.itemSlots) do PlotVisuals.buildProp(r:FindFirstChild("UpgradeProps"), frameAt(0), PlotArt, slot.name, Vector3.new(slot.x, 0, slot.z)) end
		for _, key in ipairs(PlotVisuals.itemsOf(PlotArt, stage)) do PlotVisuals.buildItem(r:FindFirstChild("UpgradeProps"), frameAt(0), PlotArt, key) end
		local n = 0
		for _, d in ipairs(r:GetDescendants()) do if d:IsA("BasePart") then n += 1 end end
		room = math.max(room, n)
	end
	local biggest = 0
	for s = 1, 6 do
		local m = PBV.build(nil, frameAt(0), PB, s, makeKit(0))
		local n = 0
		for _, d in ipairs(m:GetDescendants()) do if d:IsA("BasePart") then n += 1 end end
		biggest = math.max(biggest, n)
	end
	local total = 6 * (room + biggest + 2) + PLAZA_BUDGET -- + the Floor and the garage sign
	check("budget: six garages at their biggest stage (room " .. room .. " + building " .. biggest .. ") plus the plaza (" .. PLAZA_BUDGET .. ") is under 4,000: " .. total, total < 4000, total)
end
"""

MATH_A = r"""
local function inside(x, y, z, was) return M.isInside(b, x, y, z, was) end
local cx, cz, fy = 0, 0, 0
check("inside: standing in the middle of the room", inside(cx, fy + 3, cz) == true)
check("inside: at the landing (0, 12)", inside(cx, fy + 3, cz + 12) == true)
check("inside: next to an incubator at the back", inside(cx - 12, fy + 3, cz - 25) == true)
check("inside: in the furniture band, beside the room", inside(b.maxX - 1, fy + 3, cz) == true)
check("inside: far outside the building is outside", inside(cx + 200, fy + 3, cz) == false and inside(cx, fy + 3, cz + 200) == false and inside(cx, fy + 3, cz - 200) == false)
check("inside: the four inner corners count as inside (edges are inclusive)", inside(b.minX, fy + 3, b.minZ) and inside(b.maxX, fy + 3, b.minZ)
	and inside(b.minX, fy + 3, b.maxZ) and inside(b.maxX, fy + 3, b.maxZ))
check("inside: 0.01 beyond a corner is outside (on both axes, all four corners)", not inside(b.minX - 0.01, fy + 3, b.minZ - 0.01) and not inside(b.maxX + 0.01, fy + 3, b.minZ - 0.01)
	and not inside(b.minX - 0.01, fy + 3, b.maxZ + 0.01) and not inside(b.maxX + 0.01, fy + 3, b.maxZ + 0.01))
check("inside: 0.01 past the left, right and back walls is outside", not inside(b.minX - 0.01, fy + 3, cz) and not inside(b.maxX + 0.01, fy + 3, cz) and not inside(cx, fy + 3, b.minZ - 0.01))
check("inside: 0.01 past the front wall, away from the door, is outside", not inside(cx + 10, fy + 3, b.maxZ + 0.01) or b.doorMaxX >= 10)
check("inside: in the doorway (inside the front wall's thickness) is inside", inside(cx, fy + 3, b.maxZ + 1) == true)
check("inside: on the apron in front of the door is inside, up to its end (the wall's 2 plus 3.5)", inside(cx, fy + 3, b.maxZ + 3) and inside(cx, fy + 3, b.maxZ + b.doorDepth))
check("inside: 0.01 past the end of the apron is outside", not inside(cx, fy + 3, b.maxZ + b.doorDepth + 0.01))
check("inside: the apron is as wide as the lane (edges inclusive), not wider", inside(b.doorMaxX, fy + 3, b.maxZ + 2) and inside(b.doorMinX, fy + 3, b.maxZ + 2)
	and not inside(b.doorMaxX + 0.01, fy + 3, b.maxZ + 2) and not inside(b.doorMinX - 0.01, fy + 3, b.maxZ + 2))
check("inside: there is no door at the back or the sides (no apron there)", not inside(cx, fy + 3, b.minZ - 1) and not inside(b.maxX + 1, fy + 3, cz) and not inside(b.minX - 1, fy + 3, cz))
check("inside: behind the back wall, where the apron would be if it were on the wrong side, is outside", not inside(cx, fy + 3, b.minZ - 2) and not inside(cx, fy + 3, b.minZ - b.doorDepth))
check("inside: walking in through the door is outside, apron, inside in that order",
	(function()
		local seq = {}
		for z = b.maxZ + 9, b.maxZ - 6, -0.5 do seq[#seq + 1] = inside(cx, fy + 3, z) end
		local state, changes = seq[1], 0
		for i = 2, #seq do if seq[i] ~= state then changes += 1 state = seq[i] end end
		return seq[1] == false and seq[#seq] == true and changes == 1
	end)())
check("inside: at the floor top and 3 below it is inside, 3.01 below is outside", inside(cx, fy, cz) and inside(cx, fy - 3, cz) and not inside(cx, fy - 3.01, cz))
check("inside: just under the ceiling is inside, 0.01 above is outside (the upper stories are not inside)", inside(cx, b.maxY, cz) and not inside(cx, b.maxY + 0.01, cz))
check("inside: high above, flying, is outside", not inside(cx, fy + 100, cz) and not inside(cx, fy + 1e6, cz))
check("inside: NaN in any coordinate is never inside", not inside(0 / 0, fy + 3, cz) and not inside(cx, 0 / 0, cz) and not inside(cx, fy + 3, 0 / 0))
check("inside: infinity in any coordinate is never inside", not inside(math.huge, fy + 3, cz) and not inside(-math.huge, fy + 3, cz)
	and not inside(cx, math.huge, cz) and not inside(cx, fy + 3, math.huge) and not inside(cx, fy + 3, -math.huge))
check("inside: NaN is never inside, even when the player just was (hysteresis)", not inside(0 / 0, fy + 3, cz, true) and not inside(cx, 0 / 0, cz, true))
do
	local function safe(...) local ok, r = pcall(M.isInside, b, ...) return ok and r == false end
	check("inside: text, nil or a table instead of a number is never inside (and never an error)", safe("5", fy + 3, cz) and safe(cx, nil, cz) and safe(cx, fy + 3, {}) and safe(nil, nil, nil))
end
check("hysteresis: 0.5 past a wall is outside for someone who was outside, inside for someone who was inside", not inside(b.maxX + 0.5, fy + 3, cz, false)
	and inside(b.maxX + 0.5, fy + 3, cz, true))
check("hysteresis: exactly the margin (1 stud) past a wall still counts for someone who was inside, a hair more does not", inside(b.maxX + 1, fy + 3, cz, true)
	and not inside(b.maxX + 1.01, fy + 3, cz, true))
check("hysteresis: it works on every wall, on the ceiling line and on the floor line", inside(b.minX - 1, fy + 3, cz, true) and inside(cx, fy + 3, b.minZ - 1, true)
	and inside(cx, b.maxY + 1, cz, true) and not inside(cx, b.maxY + 1.01, cz, true) and inside(cx, b.minY - 1, cz, true) and not inside(cx, b.minY - 1.01, cz, true))
check("hysteresis: the apron grows by the margin too", inside(cx, fy + 3, b.maxZ + b.doorDepth + 1, true) and not inside(cx, fy + 3, b.maxZ + b.doorDepth + 1.01, true))
check("hysteresis: nobody is inside because of it from far away", not inside(b.maxX + 5, fy + 3, cz, true) and not inside(cx, fy + 3, b.minZ - 5, true))
"""

MATH_B = r"""
local step = M.fadeStep
check("fade: moves toward 1 by dt / seconds (0.1 s of 0.4 s = 0.25)", math.abs(step(0, 1, 0.1, 0.4) - 0.25) < 1e-9)
check("fade: moves toward 0 by dt / seconds", math.abs(step(1, 0, 0.1, 0.4) - 0.75) < 1e-9)
check("fade: never goes past the target (a long frame stops at 1 and at 0)", step(0.9, 1, 5, 0.4) == 1 and step(0.1, 0, 5, 0.4) == 0)
check("fade: holds when it is at the target", step(1, 1, 0.1, 0.4) == 1 and step(0, 0, 0.1, 0.4) == 0)
check("fade: a zero, negative or NaN frame time changes nothing", step(0.3, 1, 0, 0.4) == 0.3 and step(0.3, 1, -1, 0.4) == 0.3 and step(0.3, 1, 0 / 0, 0.4) == 0.3)
check("fade: a time of zero, below zero or NaN jumps to the target", step(0, 1, 0.1, 0) == 1 and step(1, 0, 0.1, -3) == 0 and step(0, 1, 0.1, 0 / 0) == 1)
check("fade: values outside 0..1 are clamped", step(5, 5, 0.1, 0.4) == 1 and step(-5, -5, 0.1, 0.4) == 0 and step(5, 0, 0.1, 0.4) == 0.75)
check("fade: NaN as the fade or the target is treated as 0", step(0 / 0, 1, 0.1, 0.4) == 0.25 and step(1, 0 / 0, 0.1, 0.4) == 0.75)
do
	local seed = 12345
	local function rand() seed = (seed * 1664525 + 1013904223) % 4294967296 return seed / 4294967296 end
	local bad = nil
	for _ = 1, 3000 do
		local f, t = rand() * 4 - 2, rand() * 4 - 2
		local dt, s = rand() * 2 - 0.5, rand() * 2 - 0.2
		local n = step(f, t, dt, s)
		if not (n >= 0 and n <= 1) or n ~= n then bad = bad or string.format("%g %g %g %g -> %g", f, t, dt, s, n) end
	end
	check("fade: 3,000 random inputs always give a value in 0..1", bad == nil, bad)
end
do
	local hit = M.segmentHitsBox
	check("segment: a segment through a 2x2x2 box at the origin hits it (edges count)", hit(-5, 0, 0, 5, 0, 0, 1, 1, 1) and hit(-5, 1, 0, 5, 1, 0, 1, 1, 1))
	check("segment: a segment beside, above or short of the box misses it", not hit(-5, 2, 0, 5, 2, 0, 1, 1, 1) and not hit(-5, 0, 0, -2, 0, 0, 1, 1, 1) and not hit(2, 0, 0, 5, 0, 0, 1, 1, 1))
	check("segment: a diagonal through the box hits, one that passes its corner misses", hit(-3, -3, -3, 3, 3, 3, 1, 1, 1) and not hit(-3, 3, 0, 3, 3.5, 0, 1, 1, 1))
	check("segment: a segment that starts or ends inside the box hits it", hit(0, 0, 0, 5, 5, 5, 1, 1, 1) and hit(5, 5, 5, 0.5, 0, 0, 1, 1, 1))
	check("segment: a thin wall (0.2) is hit by a segment crossing it and missed by one running beside it", hit(0, 0, -5, 0, 0, 5, 8, 7, 0.1) and not hit(9, 0, -5, 9, 0, 5, 8, 7, 0.1))
	check("segment: NaN or infinity in a point never hits", not hit(0 / 0, 0, 0, 5, 0, 0, 1, 1, 1) and not hit(0, 0, 0, math.huge, 0, 0, 1, 1, 1))
	local o = M.occludedTransparency
	check("occluded: fade 0 gives the part's own value back (glass stays 0.3, solid stays 0)", o(0.3, 0, 0.8) == 0.3 and o(0, 0, 0.8) == 0)
	check("occluded: fade 1 gives the occluded value whatever the base, never below the base", o(0.3, 1, 0.8) == 0.8 and o(0, 1, 0.8) == 0.8 and o(0.9, 1, 0.8) == 0.9)
	check("occluded: halfway between the base and the occluded value", math.abs(o(0.2, 0.5, 0.8) - 0.5) < 1e-9 and math.abs(o(0, 0.5, 0.8) - 0.4) < 1e-9)
	check("occluded: values outside 0..1 are clamped, NaN is 0", o(-1, 0, 0.8) == 0 and o(2, 0, 0.8) == 1 and o(0 / 0, 0, 0.8) == 0 and o(0, 0 / 0, 0.8) == 0 and o(0, 1, 0 / 0) == 0)
end
"""

MATH_TESTS = r"""
local b = PB.layout(3).inside
do
	local M = PBV
__MATH_A__
__MATH_B__
end
"""

CLIENT_TESTS = r"""
-- The real BuildingClient against a fake world: tagged buildings (the real ones PBV builds, kit MeshParts with glass at
-- 0.3), a Heartbeat the test fires, a local character and a camera the test moves. The rule (overhaul phase 2): only the
-- shell parts between the camera and the character fade (to Occluded, 0.8), everything else stays as built.
local WORLD
local function newWorld()
	local w = { tagged = {}, added = newSignal(), removed = newSignal(), heartbeat = newSignal() }
	w.cs = {
		GetTagged = function(_, tag) return table.clone(w.tagged) end,
		GetInstanceAddedSignal = function(_, tag) return w.added end,
		GetInstanceRemovedSignal = function(_, tag) return w.removed end,
	}
	w.root = { Position = vec(0, 0, 0), Parent = {} }
	w.character = { root = w.root, FindFirstChild = function(self, name) if name == "HumanoidRootPart" then return self.root end return nil end }
	w.camera = { CFrame = cf(0, 0, 0), CameraType = "Custom" }
	w.workspace = { CurrentCamera = w.camera }
	w.gui = nil -- a fake PlayerGui with an OpenPanel attribute, when a scenario sets one
	w.player = { Character = w.character, _attrs = {} }
	function w.player.GetAttribute(self, k) return self._attrs[k] end
	function w.player.FindFirstChild(self, name) if name == "PlayerGui" then return w.gui end return nil end
	function w.player.WaitForChild(self, name) return self:FindFirstChild(name) end
	w.players = { LocalPlayer = w.player }
	w.run = { Heartbeat = w.heartbeat }
	return w
end
local clientGame = { GetService = function(_, name)
	if name == "CollectionService" then return WORLD.cs elseif name == "Players" then return WORLD.players elseif name == "RunService" then return WORLD.run end
	error("no service " .. tostring(name))
end }
local function startClient()
	local game = clientGame
	local workspace = WORLD.workspace
	local task = { spawn = function(f, ...) f(...) end, wait = function() end, delay = function() end }
__CLIENT__
	return { isInside = isInside, segmentHitsBox = segmentHitsBox, fadeStep = fadeStep, occludedTransparency = occludedTransparency,
		looks = function() return looksStarted end }
end
local CLIENT_API
local function fresh() WORLD = newWorld() CLIENT_API = startClient() return WORLD end
local function frames(n, dt) for _ = 1, n do WORLD.heartbeat:Fire(dt or 1 / 60) end end

local TURN = 90 -- a garage turned to face +X: world axes are not the garage's
local frame = frameAt(TURN, -135, 150)
local origin = PBV.originOf(frame, PB)
local function place(x, y, z) WORLD.root.Position = origin * Vector3.new(x, y, z) end -- the character, in the garage's frame
local function look(x, y, z) WORLD.camera.CFrame = origin * CFrame.new(x, y, z) end -- the camera, in the garage's frame
local KIT = makeKit(0)
local OCC = PB.Fade.occluded

local function addBuilding(world, stage, fr, garage)
	local m = PBV.build(nil, fr or frame, PB, stage, KIT)
	if garage then m.Parent = garage end
	local fade, static, solid = {}, {}, {}
	for _, d in ipairs(m:FindFirstChild("Fade"):GetDescendants()) do if d:IsA("BasePart") then fade[d] = d.Transparency end end
	for _, d in ipairs(m:FindFirstChild("Static"):GetDescendants()) do if d:IsA("BasePart") then static[d] = d.Transparency end end
	for _, d in ipairs(m:FindFirstChild("Solid"):GetDescendants()) do if d:IsA("BasePart") then solid[d] = d.Transparency end end
	table.insert(world.tagged, m)
	world.added:Fire(m)
	return m, fade, static, solid
end
local function allAt(bases, fade)
	local worst = 0
	for part, base in pairs(bases) do worst = math.max(worst, math.abs(part.Transparency - PBV.occludedTransparency(base, fade, OCC))) end
	return worst < 1e-9, worst
end
local function untouched(bases) for part, base in pairs(bases) do if part.Transparency ~= base then return false end end return true end
local function count(t) local n = 0 for _ in pairs(t) do n += 1 end return n end
-- Is a part crossed by one of the two segments from the camera to the character (its root, its head 2.2 above)? The
-- test's own copy of the rule, with the module's pure segmentHitsBox: the client must fade exactly these parts.
local HEAD = 2.2
local function crossed(part)
	local a, b1 = WORLD.camera.CFrame.Position, WORLD.root.Position
	local b2 = b1 + Vector3.new(0, HEAD, 0)
	local cf, size = part.CFrame, part.Size
	local function hit(p, q)
		local la, lb = cf:PointToObjectSpace(p), cf:PointToObjectSpace(q)
		return PBV.segmentHitsBox(la.X, la.Y, la.Z, lb.X, lb.Y, lb.Z, size.X / 2, size.Y / 2, size.Z / 2)
	end
	return hit(a, b1) or hit(a, b2)
end
-- every part at its expected value (occluded if crossed, else its base): ok, how many are crossed, the worst difference
local function exact(bases)
	local worst, n = 0, 0
	for part, base in pairs(bases) do
		local c = crossed(part)
		if c then n += 1 end
		worst = math.max(worst, math.abs(part.Transparency - PBV.occludedTransparency(base, c and 1 or 0, OCC)))
	end
	return worst < 1e-9, n, worst
end
-- the parts of a piece group by the start of their Piece attribute (M1S1Back*, M1S1Front*, M1Roof)
local function piecesNamed(bases, prefix)
	local out = {}
	for part, base in pairs(bases) do if string.sub(tostring(part:GetAttribute("Piece")), 1, #prefix) == prefix then out[part] = base end end
	return out
end
local function snapshot(m)
	local out = {}
	for _, d in ipairs(m:GetDescendants()) do
		if d:IsA("BasePart") then
			table.insert(out, table.concat({ d:GetFullName(), tostring(d.Anchored), tostring(d.CanCollide), tostring(d.CanTouch), tostring(d.CanQuery),
				d.Size.X, d.Size.Y, d.Size.Z, d.CFrame.x, d.CFrame.y, d.CFrame.z }, "|"))
		end
	end
	return table.concat(out, "\n")
end

-- 1. Outside, then the camera behind the back wall of a turned garage ---------------------------------------------
do
	fresh()
	place(0, 3, 90)
	look(0, 8, 110) -- behind the character, both outside: nothing of the building between them
	local m, fade, static, solid = addBuilding(WORLD, 4)
	local glass = 0
	for part, base in pairs(fade) do if near(base, 0.3) then glass += 1 end end
	check("client: the stage-4 building has kit glass at 0.3, furniture and solid boxes", glass >= 5 and count(static) >= 5 and count(solid) >= 7, glass)
	local before = snapshot(m)
	frames(120)
	check("client: outside with nothing between the camera and the character, the shell stays at its own Transparency", allAt(fade, 0))
	local writes = WRITES
	frames(300)
	check("client: nothing is written while it holds still (300 frames)", WRITES == writes, WRITES - writes)
	place(6, 3, 12) -- inside, 6 to the right of the lane (world axes and the garage's differ)
	look(6, 8, -70) -- the camera outside, behind the back wall: the back wall is in the way, the front wall is not
	frames(60)
	local back, front = piecesNamed(fade, "M1S1Back"), piecesNamed(fade, "M1S1Front")
	local okAll, crossedCount = exact(fade)
	local _, crossedBack = exact(back)
	check("client: at 90 degrees (each part tested in its own frame), exactly the parts of the back wall the camera's line crosses go to the occluded transparency (" .. OCC .. "), nothing else",
		okAll and crossedCount >= 1 and crossedBack == crossedCount, crossedCount)
	check("client: the front wall, the roof and the sides, not in the way, stay as built", count(front) >= 1 and allAt(front, 0) and allAt(piecesNamed(fade, "M1Roof"), 0))
	check("client: the furniture (Static) and the solid boxes are never touched", untouched(static) and untouched(solid))
	look(6, 6, 22) -- the camera inside too, in front of the character: nothing in the way
	frames(90)
	check("client: with the camera inside the room nothing is in the way: every shell part is back at exactly its own Transparency", allAt(fade, 0))
	look(6, 70, 12) -- straight above the tower's roof (top 55), looking down through the roof and the ground floor's ceiling
	frames(60)
	local okRoof, crossedRoof = exact(fade)
	local _, roofCrossed = exact(piecesNamed(fade, "M1Roof"))
	check("client: the camera above the roof: the roof piece over the character fades, the walls do not", okRoof and crossedRoof >= 1 and roofCrossed >= 1 and allAt(back, 0) and allAt(front, 0))
	place(0, 3, 90)
	look(0, 8, 110)
	frames(90)
	check("client: walking out, every shell part is back at exactly its own Transparency (glass 0.3)", allAt(fade, 0))
	check("client: a full cycle changed nothing but Transparency (collision, size, position as built)", snapshot(m) == before)
end
-- 2. Glass, the apron and the claim post -----------------------------------------------------------------------------
do
	fresh()
	place(12, 3, 12)
	look(12, 8, 70) -- outside in front: the front wall's WallGlass right of the open entrance is in the way
	local m, fade = addBuilding(WORLD, 4)
	frames(60)
	local front = piecesNamed(fade, "M1S1Front")
	local glassOk = false
	for part, base in pairs(front) do if crossed(part) and near(base, 0.3) and near(part.Transparency, OCC) then glassOk = true end end
	local okG = exact(fade)
	check("client: glass in the way fades from 0.3 to the occluded transparency like the rest", glassOk and okG)
	place(0, 3, 34) -- on the apron, the camera behind: nothing in the way
	look(0, 8, 60)
	frames(90)
	check("client: on the apron with the camera behind you nothing fades (no apron rule: only what is in the way)", allAt(fade, 0))
end
do
	-- standing at the claim post with the camera behind: the shell is solid at every stage and turn
	local faded = nil
	for s = 1, 6 do
		for _, turn in ipairs({ 0, 90, 180, 270 }) do
			fresh()
			local fr = frameAt(turn, -135, 150)
			local o = PBV.originOf(fr, PB)
			WORLD.root.Position = o * Vector3.new(LOBBY_POST.x, 2, LOBBY_POST.z)
			WORLD.camera.CFrame = o * CFrame.new(LOBBY_POST.x, 9, LOBBY_POST.z + 18)
			local _, fade = addBuilding(WORLD, s, fr)
			frames(60)
			if not allAt(fade, 0) then faded = faded or ("stage " .. s .. " at " .. turn) end
		end
	end
	check("claim post: standing at the claim post with the camera behind you, the shell is solid at every stage and turn", faded == nil, faded)
end
-- 3. Arriving in the way, a late part, no character, a building removed, two garages, no Frame -------------------------
do
	fresh()
	place(6, 3, 12)
	look(6, 8, -70)
	local m, fade = addBuilding(WORLD, 1)
	frames(60)
	local okA, nA = exact(fade)
	check("client: a building that arrives between the camera and the character fades exactly its parts in the way", okA and nA >= 1, nA)
	local late = Instance.new("MeshPart")
	late.Transparency = 0.3
	late.Size = Vector3.new(16, 14, 2)
	late.CFrame = origin * CFrame.new(0, 6, -37) -- another piece of the back wall
	late.Parent = m:FindFirstChild("Fade")
	frames(60)
	check("client: a MeshPart that streams in late is tested like the rest (in the way: faded from its own 0.3)", near(late.Transparency, OCC))
	WORLD.players.LocalPlayer.Character = nil
	local snap = {}
	for part in pairs(fade) do snap[part] = part.Transparency end
	local writes = WRITES
	frames(120)
	local held = WRITES == writes
	for part, t in pairs(snap) do if part.Transparency ~= t then held = false end end
	check("client: with no character the shell holds its state (nothing written)", held and near(late.Transparency, OCC))
	WORLD.players.LocalPlayer.Character = WORLD.character
	look(6, 6, 22)
	frames(90)
	check("client: the character back, the camera inside: everything as built again, the late part at its own 0.3", allAt(fade, 0) and near(late.Transparency, 0.3))
	look(6, 8, -70)
	frames(60)
	for i, c in ipairs(WORLD.tagged) do if c == m then table.remove(WORLD.tagged, i) break end end
	WORLD.removed:Fire(m)
	check("client: a building removed while its parts were faded is left as built (never half see-through)", untouched(fade) and near(late.Transparency, 0.3))
end
do
	fresh()
	place(6, 3, 12)
	look(6, 8, -70)
	local a, fadeA = addBuilding(WORLD, 1)
	local other = frameAt(270, 300, 150)
	local bm, fadeB = addBuilding(WORLD, 3, other)
	frames(60)
	local okA2, nA2 = exact(fadeA)
	check("client: two garages: only the one between the camera and the character fades", okA2 and nA2 >= 1 and allAt(fadeB, 0))
	local o2 = PBV.originOf(other, PB)
	WORLD.root.Position = o2 * Vector3.new(6, 3, 5)
	WORLD.camera.CFrame = o2 * CFrame.new(6, 8, -70)
	frames(90)
	local okB2, nB2 = exact(fadeB)
	check("client: in the other garage (turned 270): the first is as built again, the second's parts in the way fade", allAt(fadeA, 0) and okB2 and nB2 >= 1)
end
do
	fresh()
	place(6, 3, 12)
	look(6, 8, -70)
	local m = PBV.build(nil, frame, PB, 2, KIT)
	m:SetAttribute("Frame", nil)
	local bases = {}
	for _, d in ipairs(m:FindFirstChild("Fade"):GetDescendants()) do if d:IsA("BasePart") then bases[d] = d.Transparency end end
	table.insert(WORLD.tagged, m)
	WORLD.added:Fire(m)
	frames(60)
	check("client: a building without its Frame is left alone (no error, nothing faded)", allAt(bases, 0))
end
-- 4. The stage-up look: only the local player's own garage, only a higher stage, never with a window open ---------------
do
	fresh()
	place(0, 3, 90)
	look(0, 8, 110)
	local garage = Instance.new("Model")
	garage.Name = "Garage2"
	garage:SetAttribute("Slot", 2)
	WORLD.player._attrs.Garage = 2
	local m1 = addBuilding(WORLD, 1, frame, garage)
	check("client: the first building of a garage starts no look (nothing to compare with)", CLIENT_API.looks() == 0)
	local m2 = addBuilding(WORLD, 2, frame, garage)
	check("client: the player's own garage at a higher stage starts the look (the camera flies to the facade; the fake has no camera API, so it ends at once)", CLIENT_API.looks() == 1)
	local m3 = addBuilding(WORLD, 1, frame, garage)
	check("client: back to the Garage (an IPO) starts no look", CLIENT_API.looks() == 1)
	local other = Instance.new("Model")
	other.Name = "Garage5"
	other:SetAttribute("Slot", 5)
	addBuilding(WORLD, 1, frameAt(270, 300, 150), other)
	addBuilding(WORLD, 3, frameAt(270, 300, 150), other)
	check("client: another player's garage going up starts no look", CLIENT_API.looks() == 1)
	WORLD.gui = { GetAttribute = function(_, k) if k == "OpenPanel" then return "Shop" end return nil end }
	addBuilding(WORLD, 3, frame, garage)
	check("client: a window open: no look (the toast still comes from the server)", CLIENT_API.looks() == 1)
	WORLD.gui = nil
	addBuilding(WORLD, 4, frame, garage)
	check("client: the window closed: the next stage up gets its look", CLIENT_API.looks() == 2)
	check("client: the camera is back to Custom after a look that could not run", WORLD.camera.CameraType == "Custom")
end
do
	fresh()
	check("client: the script listens to Heartbeat, the tag added and the tag removed (and nothing else)", #WORLD.heartbeat.handlers == 1 and #WORLD.added.handlers == 1 and #WORLD.removed.handlers == 1)
end
local M = (function() WORLD = newWorld() return startClient() end)()
local b = PB.layout(3).inside
do
__MATH_A__
__MATH_B__
end
"""

CORE_TESTS = r"""
-- TycoonCore's real garage functions (buildGarages, syncBuilding, setGarageSign, resetGarage) and its leave handler,
-- run with the real PlotArt, PlotVisuals, PlotBuilding and PlotBuildingVisuals.
local Players = { list = {}, removing = newSignal(), MaxPlayers = 6 }
local LobbyConfig = (function()
__LOBBYCONFIG__
end)()
function Players.GetPlayers() return Players.list end
Players.PlayerRemoving = Players.removing
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local PlotBuildingVisuals = PBV -- TycoonCore's names for the two modules
__KIT_SETUP__
__CONSTANTS__
__HELPERS_CORE__
__LOOKS__
__GARAGES__
local root = workspace:FindFirstChild("Garages")
check("garages: Workspace.Garages holds six garages, Garage1 to Garage6", root ~= nil and #root:GetChildren() == 6 and root:FindFirstChild("Garage6") ~= nil)
local bad = nil
for slot = 1, 6 do
	local g = root:FindFirstChild("Garage" .. slot)
	local floor = g and g:FindFirstChild("Floor")
	local building = g and g:FindFirstChild("PlotBuilding")
	local sign = g and g:FindFirstChild("GarageSign")
	local f = plotFrame(slot)
	if not (floor and near(floor.Size.X, 60) and near(floor.Size.Y, 1) and near(floor.Size.Z, 60) and floor.CanCollide and near((floor.Position - f.Position).Magnitude, 0)) then bad = bad or ("Floor " .. slot) end
	if not (building and building:GetAttribute("Stage") == 1) then bad = bad or ("building " .. slot) end
	local fr = building and building:GetAttribute("Frame")
	if not (fr and near((fr.Position - (f * Vector3.new(0, PB.FLOOR_TOP, 0))).Magnitude, 0) and near(fr.LookVector.X, f.LookVector.X) and near(fr.LookVector.Z, f.LookVector.Z)) then bad = bad or ("frame " .. slot) end
	local gui = sign and sign:FindFirstChildOfClass("BillboardGui")
	if not (gui and gui.Enabled == false and sign.Transparency == 1 and not sign.CanCollide) then bad = bad or ("sign " .. slot) end
	if g:GetAttribute("Slot") ~= slot then bad = bad or ("slot " .. slot) end
end
check("garages: each has its Floor (60 x 1 x 60, solid, at plotFrame), its building at stage 1 in its turned frame, a hidden sign", bad == nil, bad)
check("free: every garage starts Free with today's new-player room (stage 1, no props) and its claim post and lamp in a Persistent ClaimSpot; the prompt is off while the claim is off",
	(function()
		for slot = 1, 6 do
			local g = root:FindFirstChild("Garage" .. slot)
			local room = g:FindFirstChild("FreeRoom") and g.FreeRoom:FindFirstChild("PlotRoom")
			local spot = g:FindFirstChild("ClaimSpot")
			local post = spot and spot:FindFirstChild("ClaimPost")
			local prompt = post and post:FindFirstChildOfClass("ProximityPrompt")
			if g:GetAttribute("State") ~= "Free" or not room or room:GetAttribute("Stage") ~= 1 or #room.UpgradeProps:GetChildren() ~= 0 then return false end
			if not prompt or prompt.Enabled ~= LobbyConfig.ClaimEnabled or post.CanCollide or post.CanTouch then return false end
			if spot.ModelStreamingMode ~= Enum.ModelStreamingMode.Persistent or not spot:FindFirstChild("FreeLamp") then return false end
		end
		return true
	end)())
setGarageSign(2, "Ana's Startup")
local gui = root.Garage2.GarageSign:FindFirstChildOfClass("BillboardGui")
check("sign: setGarageSign shows the owner's name over their garage", gui.Enabled == true and gui.TextLabel.Text == "Ana's Startup")
syncBuilding(2, 3)
check("syncBuilding: a stage change builds that stage's building in the garage", root.Garage2.PlotBuilding:GetAttribute("Stage") == 3)
-- a visitor standing in the Big Office's band when the owner leaves: the reset never traps them
local visitor = Instance.new("Part")
visitor.Name = "HumanoidRootPart"
local vf = PBV.originOf(plotFrame(2), PB)
visitor.CFrame = vf * CFrame.new(-33, 2, 0)
local character = { FindFirstChild = function(_, name) return name == "HumanoidRootPart" and visitor or nil end }
Players.list = { { Character = character } }
if PlotVisuals then PlotVisuals.styleFloor(root.Garage2.Floor, PlotArt, 3) end
resetGarage(2)
check("reset: the garage goes back to a new Garage: building at stage 1, no name, the Floor styled as stage 1",
	root.Garage2.PlotBuilding:GetAttribute("Stage") == 1 and gui.Enabled == false and gui.TextLabel.Text == ""
	and root.Garage2.Floor.Material.Name == PlotArt.Stages[1].floor.material)
local landing = plotFrame(2) * Vector3.new(0, 4, 12)
check("reset: a visitor standing where the Garage's wall now is goes to the landing (a stage change never traps a player)",
	near((visitor.Position - landing).Magnitude, 0), tostring(visitor.Position))
local guis = 0
for _, d in ipairs(root.Garage2:GetDescendants()) do if d.ClassName == "BillboardGui" and not d:IsDescendantOf(root.Garage2.ClaimSpot) then guis += 1 end end
check("sign: one name label per garage, whatever happened (no label per owner; the claim post's FREE sign aside)", guis == 1, guis)
-- the leave handler: the save first, then the folder, the reset, the slot
local events = {}
local function saveOnLeave(player) table.insert(events, "save") end
local plotOwners, playerData = { [4] = "someone" }, {}
local player = { Name = "Ana", DisplayName = "Ana", UserId = 7 }
local folder = Instance.new("Folder")
folder.Parent = root.Garage4
playerData[player] = { folder = folder, slot = 4 }
syncBuilding(4, 5)
setGarageSign(4, "Ana's Startup")
__LEAVE__
Players.removing:Fire(player)
check("leave: the leave save runs, then the owner's folder is destroyed, the garage reset to a new Garage and the slot freed",
	events[1] == "save" and rawget(folder, "destroyed") == true and root.Garage4.PlotBuilding:GetAttribute("Stage") == 1
	and root.Garage4.GarageSign:FindFirstChildOfClass("BillboardGui").Enabled == false and plotOwners[4] == nil and playerData[player] == nil)
"""

STUDIO_TESTS = r"""
-- docs/STUDIO_SYNC_LOBBY.md's kit check, kit front check and spawn check, run as they are, in a fake place
local OUT = {}
local SSS, RS = game:GetService("ServerScriptService"), game:GetService("ReplicatedStorage")
local function module(parent, name, value)
	local m = Instance.new("ModuleScript")
	m.Name = name
	rawset(m, "_module", value)
	m.Parent = parent
	return m
end
local function require(m) return rawget(m, "_module") end
local function runBlock(source)
	OUT = {}
	local print = function(...) local t = {} for i = 1, select("#", ...) do t[i] = tostring(select(i, ...)) end table.insert(OUT, table.concat(t, " ")) end
	local ok, err = pcall(function()
		BLOCK(source, print)
	end)
	if not ok then table.insert(OUT, "ERROR: " .. tostring(err)) end
	return ok, err
end
local function last() return OUT[#OUT] or "" end
local function clearKit() local k = RS:FindFirstChild("KitModels") if k then k.Parent = nil end end
local function useKit(kit) clearKit() kit.Parent = RS end

-- kit check
local ok = runBlock("kit")
check("studio: the kit check without PlotBuilding says NOT YET", ok and string.find(last(), "NOT YET", 1, true) == 1, last())
local pbScript, pbvScript = module(SSS, "PlotBuilding", PB), module(SSS, "PlotBuildingVisuals", PBV)
useKit(makeKit(0, nil, true))
ok = runBlock("kit")
check("studio: the kit check on a right KitModels says KIT OK: 36 models", ok and string.find(last(), "KIT OK: 36 models", 1, true) == 1, last())
local broken = makeKit(0, { Bell = true }, true)
broken:FindFirstChild("Sofa"):SetAttribute("KitSize", Vector3.new(8, 4.3, 4))
useKit(broken)
ok = runBlock("kit")
local joined = table.concat(OUT, "|")
check("studio: the kit check names what is wrong (a missing Bell, a Sofa 0.3 too tall) and says KIT NOT OK", ok and string.find(last(), "KIT NOT OK", 1, true) == 1
	and string.find(joined, "WRONG: Bell: missing", 1, true) ~= nil and string.find(joined, "WRONG: Sofa: KitSize", 1, true) ~= nil, joined)
clearKit()
ok = runBlock("kit")
check("studio: the kit check with no KitModels says so", ok and string.find(table.concat(OUT, "|"), "KitModels is missing", 1, true) ~= nil and string.find(last(), "KIT NOT OK", 1, true) == 1)

-- kit front check: the Chair's back (its trim) is away from the STAND HERE pad when the turn is right
local function chairFacesPad()
	local folder = workspace:FindFirstChild("KIT_FRONT_CHECK")
	local chair = folder and folder:FindFirstChild("FrontChair")
	local pad = folder and folder:FindFirstChild("STAND_HERE")
	if not (chair and pad) then return nil end
	local seat, back
	for _, d in ipairs(chair:GetDescendants()) do
		if d:IsA("BasePart") then
			if d:GetAttribute("Role") == "main" then seat = d elseif d:GetAttribute("Role") == "trim" then back = d end
		end
	end
	return (pad.Position.Z - seat.Position.Z) > 0 and back.Position.Z < seat.Position.Z, pad.Position.Y
end
for _, case in ipairs({ { 0, 0, true }, { 180, 180, true }, { 180, 0, false } }) do
	useKit(makeKit(case[1]))
	PB.KIT_FRONT_TURN = case[2]
	ok = runBlock("front")
	local faces, padY = chairFacesPad()
	check(string.format("studio: the kit front check, a kit imported turned %d with KIT_FRONT_TURN %d: the chair %s the pad", case[1], case[2], case[3] and "faces" or "turns its back to"),
		ok and faces == case[3] and string.find(table.concat(OUT, "|"), "Chair from the kit: true", 1, true) ~= nil, table.concat(OUT, "|"))
	check("studio: the kit front check's pad lies on the ground (y 0 to 0.2), visible", ok and padY and math.abs(padY - 0.1) < 1e-6, padY)
end
PB.KIT_FRONT_TURN = 0
ok = runBlock("front")
check("studio: running the kit front check twice leaves one KIT_FRONT_CHECK", ok and #(function() local n = {} for _, c in ipairs(workspace:GetChildren()) do if c.Name == "KIT_FRONT_CHECK" then table.insert(n, c) end end return n end)() == 1)

-- spawn check
local spawn = Instance.new("SpawnLocation")
spawn.Name = "SpawnLocation"
spawn.Parent = workspace
for _, case in ipairs({ { vec(0, 0.5, 175), "ON THE PLAZA" }, { vec(-1, 0.5, -1), "WHERE IT ALWAYS WAS" }, { vec(3, 0.5, 175), "SOMEWHERE ELSE" } }) do
	spawn.Position = case[1]
	ok = runBlock("spawn")
	check("studio: the spawn check at " .. tostring(case[1]) .. " says " .. case[2], ok and string.find(last(), case[2], 1, true) ~= nil, last())
end
spawn.Parent = nil
ok = runBlock("spawn")
check("studio: the spawn check with no SpawnLocation says so", ok and last() == "NO SpawnLocation in the Workspace", last())
"""

TAIL = r"""
print_real(string.format("%d passed, %d failed", passed, failed))
print_real("DONE")
"""


def read(name):
    with open(os.path.join(ROOT, name), encoding="utf-8") as f:
        return f.read()


def run_luau(luau, source):
    with tempfile.NamedTemporaryFile("w", suffix=".luau", delete=False, encoding="utf-8") as f:
        f.write(source)
        path = f.name
    try:
        return subprocess.run([luau, path], capture_output=True, text=True, timeout=900)
    finally:
        os.unlink(path)


def kit_doc_table():
    """docs/KIT_MODELS.md's 36 rows as a Luau table: { Key = { w, d, h, roles = { role = "HEX" } } }."""
    doc = read("docs/KIT_MODELS.md")
    rows = re.findall(r"^\| `(\w+)` \| [\w.]+ \| ([\d.]+) x ([\d.]+) x ([\d.]+) \| \d+ \| (.+?) \|$", doc, re.M)
    out = []
    for key, w, d, h, parts in rows:
        roles = re.findall(r"(\w+) #([0-9A-F]{6})", parts)
        out.append('%s = { w = %s, d = %s, h = %s, roles = { %s } }' % (key, w, d, h, ", ".join('%s = "%s"' % r for r in roles)))
    return "local EXPECTED_KIT = { " + ", ".join(out) + " }\n"


STRETCH_ALLOWED = ('local STRETCH_ALLOWED = { Wall = { x = true }, RoofEdge = { x = true }, Floor = { x = true, z = true }, WallDoor = { x = true }, '
                   'DoorLeaf = { x = true } }\n')


# The plaza's share of the 3,000 parts: six garages at their biggest stage take about 2,470, so the ring plaza (PR L4) may
# use at most this many (tools/world_test.py checks the ring world against WorldArt's ring budget, which must not be more).
PLAZA_SHARE = 480


def plaza_budget():
    """The plaza's allowance: WorldArt's ring budget once PR L4 adds it (Budget.ringParts), else PLAZA_SHARE."""
    m = re.search(r"ringParts = (\d+)", read("WorldArt.lua"))
    return int(m.group(1)) if m else PLAZA_SHARE


def math_block(text):
    m = re.search(r"-- BUILDINGMATH-START\n.*?-- BUILDINGMATH-END\n", text, re.S)
    return m.group(0) if m else None


def between(text, start, end, inclusive_end=True):
    a = text.find(start)
    if a < 0:
        return None
    b = text.find(end, a)
    if b < 0:
        return None
    return text[a:b + (len(end) if inclusive_end else 0)]


def core_snippets(core):
    """TycoonCore's garage code, cut out of the real file (None when a piece is missing)."""
    consts = []
    for pat in (r"local PLOT_SPACING = \d+\n", r"local MAX_PLOTS = \d+\n", r"local GARAGE_TURNS = \{[^}]*\}\n"):
        m = re.search(pat, core)
        if not m:
            return None
        consts.append(m.group(0))
    helpers = between(core, "local function makePart(", "local function plotCenter(", False)
    frame = between(core, "local function plotCenter(", "-- Where each upgrade's prop stands", False)
    looks = between(core, "local function looks(", "-- The funding stage the valuation reached", False)
    garages = between(core, "local garages = {} -- slot", "\nbuildGarages()\n")
    leave = between(core, "Players.PlayerRemoving:Connect(function(player)\n", "\nend)\n")
    if None in (helpers, frame, looks, garages, leave):
        return None
    return {"__CONSTANTS__": "".join(consts), "__HELPERS_CORE__": helpers + frame, "__LOOKS__": looks,
            "__GARAGES__": garages, "__LEAVE__": leave}


def program(part, sources):
    """One Luau program: the fake, the modules and one test part."""
    mods = (MODULES.replace("__PLOTART__", sources["PlotArt.lua"]).replace("__PLOTVISUALS__", sources["PlotVisuals.lua"])
            .replace("__PLOTBUILDING__", sources["PlotBuilding.lua"]).replace("__PBV__", sources["PlotBuildingVisuals.lua"]))
    post = re.search(r"LobbyConfig\.Post = \{ x = ([\d.]+), z = ([\d.]+) \}", sources["LobbyConfig.lua"])
    head = (PRELUDE + mods + kit_doc_table() + STRETCH_ALLOWED + ("local PLAZA_BUDGET = %d\n" % plaza_budget())
            + ("local LOBBY_POST = { x = %s, z = %s }\n" % (post.group(1), post.group(2)) if post else 'error("LobbyConfig.Post not found")\n') + HELPERS)
    if part == "data":
        body = DATA_TESTS
    elif part == "build":
        body = BUILD_TESTS
    elif part == "math":
        body = MATH_TESTS.replace("__MATH_A__", MATH_A).replace("__MATH_B__", MATH_B)
    elif part == "studio":
        body = STUDIO_TESTS.replace("local function runBlock(source)", "__BLOCKS__\nlocal function runBlock(source)", 1)
        body = body.replace("__BLOCKS__", doc_blocks())
    elif part == "client":
        body = CLIENT_TESTS.replace("__CLIENT__", sources["BuildingClient.lua"]).replace("__MATH_A__", MATH_A).replace("__MATH_B__", MATH_B)
    else:
        snips = core_snippets(sources["TycoonCore.lua"])
        if snips is None:
            body = 'check("core: TycoonCore\'s garage code (makePart, plotFrame, looks, the garages block, the leave handler) can be cut out", false)\n'
        else:
            body = CORE_TESTS.replace("__KIT_SETUP__", "").replace("__LOBBYCONFIG__", sources["LobbyConfig.lua"])
            for k, v in snips.items():
                body = body.replace(k, v)
    return head + body + TAIL


PARTS = ("data", "build", "math", "client", "core", "studio")
SYNC_DOC = os.path.join("docs", "STUDIO_SYNC_LOBBY.md")


def doc_blocks():
    """The kit check, the kit front check and the spawn check from docs/STUDIO_SYNC_LOBBY.md, as Luau functions."""
    doc = read(SYNC_DOC)
    out = {}
    for key, heading in (("kit", "### 5. KitModels check (command bar)"), ("front", "### 6. Kit front check (command bar)"),
                         ("spawn", "### 7. The SpawnLocation")):
        at = doc.find(heading)
        m = re.search(r"```lua\n(.*?)```", doc[at:], re.S) if at >= 0 else None
        out[key] = m.group(1) if m else 'error("block missing in the sync doc")\n'
    body = "local BLOCKS = {}\n"
    for key, text in out.items():
        body += "BLOCKS.%s = function(print, require)\n%s\nend\n" % (key, text)
    return body + "local function BLOCK(name, print) return BLOCKS[name](print, require) end\n"


def run_parts(luau, sources, parts=PARTS):
    """{part: (passed, failed, [failed names], crashed text or None)}"""
    out = {}
    for part in parts:
        r = run_luau(luau, program(part, sources))
        lines = r.stdout.splitlines()
        names = [l[len("FAIL: "):].split(" -- ")[0] for l in lines if l.startswith("FAIL: ")]
        m = re.search(r"(\d+) passed, (\d+) failed", r.stdout)
        crashed = None
        if r.returncode != 0 or "DONE" not in lines:
            crashed = (r.stderr.strip() or r.stdout.strip())[-400:]
        out[part] = (int(m.group(1)) if m else 0, int(m.group(2)) if m else 0, names, crashed)
    return out


def code_only(text):
    """The Luau text without comments (so a word in a comment never counts)."""
    text = re.sub(r"--\[(=*)\[.*?\]\1\]", "", text, flags=re.S)
    return re.sub(r"--[^\n]*", "", text)


def static_checks(sources):
    out = []

    def add(name, ok, extra=None):
        out.append((name, bool(ok), extra))

    client, mod, core = sources["BuildingClient.lua"], sources["PlotBuildingVisuals.lua"], sources["TycoonCore.lua"]
    add("files: BuildingClient.lua is at the repo root (one Studio script = one root .lua) and not in docs/studio_scripts",
        os.path.exists(os.path.join(ROOT, "BuildingClient.lua")) and not os.path.exists(os.path.join(ROOT, "docs", "studio_scripts", "BuildingClient.lua")))
    a, b = math_block(mod), math_block(client)
    add("client: the inside check and fade maths in BuildingClient are the same text as in PlotBuildingVisuals", a is not None and a == b)
    cc = code_only(client)
    add("client: never fires a remote, never touches collision, anchoring or a part's position (only the camera's CFrame, during the look)", not re.search(
        r"FireServer|InvokeServer|RemoteEvent|RemoteFunction|\.CanCollide\s*=|\.CanTouch\s*=|\.CanQuery\s*=|\.Anchored\s*=|(?<!camera)\.CFrame\s*=|\.Position\s*=|\.Size\s*=", cc))
    add("client: tests each shell part in its own frame (PointToObjectSpace) and reads the garage's Frame for the look", "PointToObjectSpace(a)" in cc and 'GetAttribute("Frame")' in cc)
    add("client: fades only the Fade group", cc.count('FindFirstChild("Fade")') >= 1 and "Static" not in cc and '"Solid"' not in cc)
    for name, text in (("BuildingClient", client), ("PlotBuildingVisuals", mod), ("PlotBuilding", sources["PlotBuilding.lua"]), ("TycoonCore", core)):
        add("source: %s has no word \"Touched\" (nothing is bought or opened by touching the world)" % name, "Touched" not in text)
    pb = code_only(sources["PlotBuilding.lua"])
    add("data: PlotBuilding is data and pure layout (no Instance, no service, no require)", not re.search(r"Instance\.new|GetService|require\(|workspace", pb))
    add("data: no asset id anywhere (rbxassetid, MeshId, TextureID)", not re.search(r"rbxassetid|MeshId|TextureI[Dd]", sources["PlotBuilding.lua"] + mod))
    pbv = code_only(mod)
    add("builder: the one Light it makes is the ceiling's PointLight (never a spot or surface light, never an emitter)",
        pbv.count('Instance.new("PointLight")') == 1 and not re.search(r'Instance\.new\("(SpotLight|SurfaceLight|ParticleEmitter)"', pbv))
    # TycoonCore's L2 wiring
    add("core: PlotBuilding and PlotBuildingVisuals are required inside pcall (5 s wait), and set to nil when either fails",
        'pcall(require, script.Parent:WaitForChild("PlotBuildingVisuals", 5))' in core and 'pcall(require, script.Parent:WaitForChild("PlotBuilding", 5))' in core
        and "PlotBuildingVisuals, PlotBuilding = nil, nil" in core)
    floors = re.findall(r'makePart\((\w+), "Floor"', core)
    add("core: the Floor is made once, in buildGarages (the garage), never in the join", floors == ["garage"], floors)
    m = re.search(r"local function claimGarage\(player, slot\)\n(.*?)\n\t-- CLAIMLOAD-START", core, re.S)  # lobby L3: the join's load is the claim's
    join = m.group(1) if m else ""
    add("core: the claim (the join's load) puts the owner's folder in their garage and takes the garage's Floor",
        "\tfolder.Parent = garages[slot]" in join and "\tlocal floor = garages[slot].Floor" in join)
    add("core: the claim names the garage once (setGarageSign) and adds no label of its own (no label per owner)",
        join.count("setGarageSign(slot, ") == 1 and "addLabel(" not in code_only(join))
    block = between(core, "-- CLAIMLOAD-START", "-- CLAIMLOAD-END") or ""
    add("core: nothing of the building is called inside the CLAIMLOAD block (building-pass's third edit is dropped)",
        block != "" and "syncBuilding" not in block and "PlotBuilding" not in block)
    sync = between(code_only(core), "local function syncRoom(data)", "\nend\n") or ""
    add("core: syncRoom (every second) syncs the building with the building bought (overhaul 2; or the Studio Debug button's, in memory only)",
        "local stage = data.debugStage or buildingOf(data)" in sync and "syncBuilding(data.slot, stage)" in sync)
    leave = between(core, "Players.PlayerRemoving:Connect(function(player)\n", "\nend)\n") or ""
    add("core: the leave handler resets the garage after the leave save and the folder",
        leave.find("saveOnLeave(player)") >= 0 and leave.find("saveOnLeave(player)") < leave.find("data.folder:Destroy()") < leave.find("resetGarage(data.slot)") < leave.find("plotOwners[data.slot] = nil"))
    dbg = re.search(r'\nif RunService:IsStudio\(\) then\n\tShopServer\.addDebugAction\("BuildingNextStage", function\(_, data\)\n(.*?)\nend\n', core, re.S)
    save = between(core, "-- BUILDSAVE-START", "-- SAVEFN-END") or ""
    add("debug: the \"Building: next stage\" button is added only in Studio, and data.debugStage is never saved",
        dbg is not None and core.count('addDebugAction("BuildingNextStage"') == 1 and "debugStage" not in save
        and 'debugRow("🏗️", "Building: next stage",' in sources.get("ShopClient.lua", ""))
    add("core: buildGarages runs once, before players are set up", core.count("\nbuildGarages()\n") == 1
        and core.find("\nbuildGarages()\n") < core.find("Players.PlayerAdded:Connect(onPlayerAdded)"))
    return out


# --- mutation runs: break the code or the data on purpose; each must be caught by its NAMED check, never by a crash ----
PB, PBV, CLIENT, CORE = "PlotBuilding.lua", "PlotBuildingVisuals.lua", "BuildingClient.lua", "TycoonCore.lua"
MUTANTS = [
    # (what is broken, file, old, new, the start of the check that must fail, which parts to run)
    ("a box in the lane (FrontLeft reaches the middle)", PB, 'solid("FrontLeft", -h + W, -door.half,', 'solid("FrontLeft", -h + W, 0,', "lane:", ("data", "build")),
    ("a kit MeshPart left solid", PBV, "\t\t\tlookFlags(part)\n\t\t\tpaint(part, building, stage, piece, role)\n\t\t\ttag(part, piece, role)\n\t\t\tpart.Parent = parent\n\t\t\ttable.insert(made, part)",
     "\t\t\tlookFlags(part)\n\t\t\tpart.CanCollide = true\n\t\t\tpaint(part, building, stage, piece, role)\n\t\t\ttag(part, piece, role)\n\t\t\tpart.Parent = parent\n\t\t\ttable.insert(made, part)", "solid:", ("build",)),
    ("the client remembers only opaque parts (glass never fades)", CLIENT, "\tif item:IsA(\"BasePart\") then\n\t\tstate.parts[item] = { base = item.Transparency, fade = 0 }",
     "\tif item:IsA(\"BasePart\") and item.Transparency == 0 then\n\t\tstate.parts[item] = { base = item.Transparency, fade = 0 }", "client: glass in the way", ("client",)),
    ("a stage over the budget (Big Corporate gets 12 more columns)", PB, '\t\t\t{ block = { 52, 0.5, 0.6 }, role = "trim", look = "tower", name = "TowerLine", x = 0, y = 40.7, z = 14.4 },\n',
     '\t\t\t{ block = { 52, 0.5, 0.6 }, role = "trim", look = "tower", name = "TowerLine", x = 0, y = 40.7, z = 14.4 },\n' + "".join('\t\t\t{ key = "Column", x = %d, y = -1, z = -50, turn = 0 },\n' % x for x in range(-33, 39, 6)), "budget:", ("data",)),
    ("the front moves at stage 4 (z 33.2 instead of 32.2)", PB, "masses = { { half = 40, back = -40, front = 32.2,", "masses = { { half = 40, back = -40, front = 33.2,", "front:", ("data",)),
    ("furniture inside the room (the band measured from the room's edge inward)", PB, "p.x, p.z, p.turn = -inner + depth / 2, f.along, 90", "p.x, p.z, p.turn = -30 + depth / 2, f.along, 90", "furniture:", ("data",)),
    ("the fallback missing a wall (Wall has no Parts version)", PB, '\tWall = { box("main", 16, 13, 2, 0, 6.5, 0), box("trim", 16, 1, 2, 0, 13.5, 0) },', '\tWall = {},', "fallback:", ("data", "build")),
    ("a stretched Column (STRETCH lets Column stretch, the pillars made 6 wide)", PB, "PlotBuilding.STRETCH = { Wall = { x = true },", "PlotBuilding.STRETCH = { Column = { x = true }, Wall = { x = true },", "stretch:", ("data", "build")),
    ("the kit front turn ignored", PBV, "local target = pieceFrame(origin, piece) * CFrame.Angles(0, math.rad(building.KIT_FRONT_TURN), 0)", "local target = pieceFrame(origin, piece)", "kit front:", ("build",)),
    ("the client tests a part in world axes (its own frame ignored)", CLIENT, "\tlocal la, lb = cframe:PointToObjectSpace(a), cframe:PointToObjectSpace(b)", "\tlocal la, lb = a - cframe.Position, b - cframe.Position", "client: at 90 degrees", ("client",)),
    ("the client fades the whole shell whenever the camera's line crosses the building (not only the parts in the way)", CLIENT, "\t\tlocal inWay = part.Parent ~= nil and (hitsPart(part, a, b1) or hitsPart(part, a, b2))", "\t\tlocal inWay = part.Parent ~= nil", "client: the front wall", ("client",)),
    ("the look plays for every garage (not only the player's own)", CLIENT, "\tif before and stage > before and player:GetAttribute(\"Garage\") == slot then", "\tif before and stage > before then", "client: another player's garage", ("client",)),
    ("the look plays after an IPO too (any stage change)", CLIENT, "\tif before and stage > before and player:GetAttribute(\"Garage\") == slot then", "\tif before and stage ~= before and player:GetAttribute(\"Garage\") == slot then", "client: back to the Garage", ("client",)),
    ("a second light on every building (a spot light on the sign)", PBV, "\tlight.Parent = roof\n\treturn light", "\tlight.Parent = roof\n\tlocal extra = Instance.new(\"PointLight\")\n\textra.Parent = roof\n\treturn light", "check:", ("build",)),
    ("the apron on the wrong side (behind the back wall)", PBV, "return z > b.maxZ and z <= b.maxZ + b.doorDepth + m", "return z < b.minZ and z >= b.minZ - b.doorDepth - m", "inside:", ("math",)),
    ("a door jamb in the lane (a Corner at x 3 in front of the Small Office's door)", PB,
     '\t\t\t{ block = { 29.6, 0.5, 0.8 }, role = "trim", name = "SillR", x = 19.4, y = 3.6, z = 32.4 },\n\t\t},\n\t\tfurniture = {\n\t\t\t{ key = "ReceptionDesk", side = "left", along = 16 },\n\t\t\t{ key = "Plant", side = "left", along = 26.5 },\n\t\t\t{ key = "Sofa", side = "right", along = 16 },\n\t\t},',
     '\t\t\t{ block = { 29.6, 0.5, 0.8 }, role = "trim", name = "SillR", x = 19.4, y = 3.6, z = 32.4 },\n\t\t\t{ key = "Corner", x = 3, y = -1, z = 33.2, turn = 0 },\n\t\t},\n\t\tfurniture = {\n\t\t\t{ key = "ReceptionDesk", side = "left", along = 16 },\n\t\t\t{ key = "Plant", side = "left", along = 26.5 },\n\t\t\t{ key = "Sofa", side = "right", along = 16 },\n\t\t},', "lane:", ("build",)),
    ("an inner part solid (the fallback's Parts collide)", PBV, "\t\tlookFlags(part)\n\t\tpaint(part, building, stage, piece, b.role)", "\t\tlookFlags(part)\n\t\tpart.CanCollide = true\n\t\tpaint(part, building, stage, piece, b.role)", "solid:", ("build",)),
    ("the occluded transparency capped at 0.2 (the camera's popper would pull in on a shell part in the way)", PBV, "\treturn clamp01(b + (t - b) * clamp01(fade))", "\treturn math.min(0.2, clamp01(b + (t - b) * clamp01(fade)))", "fade:", ("build", "math")),
    ("the roof left unfaded (in Static)", PB, '"M" .. m .. "Roof", key = "Floor", x = 0, y = top - 1, z = cz, turn = 0, sx = innerW / fw, sz = innerD / fw, look = "roof" })',
     '"M" .. m .. "Roof", key = "Floor", x = 0, y = top - 1, z = cz, turn = 0, sx = innerW / fw, sz = innerD / fw, look = "roof", group = "Static" })', "fade:", ("data",)),
    ("a label per owner (the join adds a billboard again)", CORE, "\tsetGarageSign(slot, player.DisplayName .. \"'s Startup\")\n", "\tsetGarageSign(slot, player.DisplayName .. \"'s Startup\")\n\taddLabel(floor, player.DisplayName .. \"'s Startup\", 12)\n", "core: the claim names the garage once", ()),
    ("no reset on leave", CORE, "\t\tresetGarage(data.slot) -- the garage stays: back to a new Garage, Free, with no name on it\n", "", "leave:", ("core",)),
    ("the reset does not rebuild the Garage", CORE, "\tsyncBuilding(slot, 1)\n\tsetGarageSign(slot, \"\")\n", "\tsetGarageSign(slot, \"\")\n", "reset:", ("core",)),
    ("a stage change may trap a player (unstick does nothing)", PBV, "\t\t\t\troot.CFrame = landing\n\t\t\t\tmoved += 1", "\t\t\t\tmoved += 1", "unstick:", ("build",)),
    ("a solid box left visible (Transparency 0)", PBV, "\tpart.Transparency = 1\n\tpart.Color = Color3.fromRGB(128, 128, 128)", "\tpart.Transparency = 0\n\tpart.Color = Color3.fromRGB(128, 128, 128)", "flags:", ("build",)),
    ("the builder keeps every BasePart of a kit model (not only MeshParts)", PBV, "\t\tif d:IsA(\"MeshPart\") then\n\t\t\tlocal rel = pivot:ToObjectSpace(d.CFrame)", "\t\tif d:IsA(\"BasePart\") then\n\t\t\tlocal rel = pivot:ToObjectSpace(d.CFrame)", "kit: only MeshParts", ("build",)),
    ("the builder stretches anything it is asked to (no refusal)", PBV, "\tif (stretched(sx) and not (allowed and allowed.x)) or (stretched(sz) and not (allowed and allowed.z)) then", "\tif false then", "stretch:", ("build",)),
    ("a missing key warns on every build", PBV, "\tif not warned[kind] then\n\t\twarned[kind] = true", "\tif true then\n\t\twarned[kind] = true", "fallback:", ("build",)),
    ("the style table loses a role (stage 3 has no glass)", PB, '\t\t\tglass = S(rgb(170, 210, 232), "Glass", GLASS), dark = S(rgb(44, 52, 66), "Metal"),', '\t\t\tdark = S(rgb(44, 52, 66), "Metal"),', "style:", ("data",)),
    ("the manifest's Sofa size drifts from docs/KIT_MODELS.md", PB, "\tSofa = kit(8, 4, 4,", "\tSofa = kit(8, 4.5, 4,", "manifest:", ("data",)),
    ("the building is built in world axes (the Frame ignored)", PBV, "\treturn frame * CFrame.new(0, building.FLOOR_TOP, 0)", "\treturn CFrame.new(frame.Position) * CFrame.new(0, building.FLOOR_TOP, 0)", "turn:", ("build",)),
    ("the stage Debug button added on live servers too (no Studio check)", CORE, "if RunService:IsStudio() then\n\tShopServer.addDebugAction(\"BuildingNextStage\"",
     "if true then\n\tShopServer.addDebugAction(\"BuildingNextStage\"", "debug:", ()),
    ("the building streams like any model (not Persistent)", PBV, "\t\tmodel.ModelStreamingMode = Enum.ModelStreamingMode.Persistent", "\t\tmodel.ModelStreamingMode = Enum.ModelStreamingMode.Default",
     "streaming:", ("build",)),
    ("the lintel box starts at 5 (the doorway only 6 high)", PB, 'solid("Lintel", -door.half, door.half, door.top, top1,', 'solid("Lintel", -door.half, door.half, 5, top1,', "doorway:", ("data",)),
    # PR #32 review fixes
    ("the apron as wide as the door again (the Garage's 20: the inside box reaches the claim post)", PB,
     "doorMinX = -PlotBuilding.Lane.half, doorMaxX = PlotBuilding.Lane.half,", "doorMinX = -door.half, doorMaxX = door.half,", "claim post:", ("data",)),
    ("the Small Office's WallDoor at its kit size (its jambs 1.5 into the lane)", PB,
     '\t\t\t{ key = "WallDoor", x = 0, y = -1, z = 31.2, turn = 0, width = 24, lane = true },\n\t\t\t{ key = "DoorLeaf", x = -9.1, y = -1, z = 32.45, turn = 0, width = 9 }, -- open',
     '\t\t\t{ key = "WallDoor", x = 0, y = -1, z = 31.2, turn = 0, lane = true },\n\t\t\t{ key = "DoorLeaf", x = -9.1, y = -1, z = 32.45, turn = 0, width = 9 }, -- open',
     "door:", ("data", "build")),
    ("WallDoor may not stretch (the builder keeps its 6-wide opening)", PB, "Floor = { x = true, z = true }, WallDoor = { x = true },", "Floor = { x = true, z = true },",
     "door:", ("build",)),
    ("the roof box back at 12 (a jumping head reaches it)", PB, "top1 - PlotBuilding.ROOF, top1,", "top1 - 1, top1,", "roof:", ("data",)),
    ("unstick counts the roof (a player mid-jump under it is teleported)", PBV, '\t\tif part:IsA("BasePart") and part:GetAttribute("Piece") ~= "Roof" then',
     '\t\tif part:IsA("BasePart") then', "unstick: a player mid-jump", ("build",)),
    ("Clone's nil not handled (a MeshPart with Archivable off errors the build)", PBV, "\t\t\tlocal part = d:Clone()\n\t\t\tif not part then",
     "\t\t\tlocal part = d:Clone()\n\t\t\tif false then", "kit: a MeshPart with Archivable off", ("build",)),
    ("the stretch test exact again (float noise in KitSize stretches, a turned part falls back to Parts)", PBV, "\treturn math.abs(s - 1) > STRETCH_EPS",
     "\treturn s ~= 1", "stretch: float noise", ("build",)),
    ("checkKit skips the WorldPivot check", PBV, "\t\t\tif bounds[1] <= bounds[2] then", "\t\t\tif false then", "checkKit: a WorldPivot off", ("build",)),
    ("checkKit lets two MeshParts share a role", PBV, "\t\t\t\t\telseif seen[role] then", "\t\t\t\t\telseif false then", "checkKit: two MeshParts", ("build",)),
    ("the RevolvingDoor back on Small Corporate's lane", PB, '\t\textras = {\n\t\t\t{ key = "RoofEdge", x = 0, y = 11, z = 31.7, turn = 0, width = 10 },',
     '\t\textras = {\n\t\t\t{ key = "RevolvingDoor", x = 0, y = -1, z = 35, turn = 0, lane = true },\n\t\t\t{ key = "RoofEdge", x = 0, y = 11, z = 31.7, turn = 0, width = 10 },',
     "lane: only the door piece", ("data",)),
    # building-garage-roof
    ("the gable steps too narrow (a gap under the Garage's roof)", PB, "\tlocal run = tierH / s\n", "\tlocal run = tierH / s + 2\n", "roof: the Garage's stepped gables", ("data",)),
    ("the Garage's roof sheets tilted the wrong way (a valley, not a ridge)", PB, "turn = side < 0 and 270 or 90, tilt = math.deg(a) })", "turn = side < 0 and 270 or 90, tilt = -math.deg(a) })",
     "roof: the Garage has a pitched roof", ("data",)),
    ("a Block counted as a kit piece built from Parts", PBV, "\t\t\tif not isBlock then\n\t\t\t\tfromParts += 1\n\t\t\tend", "\t\t\tfromParts += 1", "kit: stage 1 at 0 (kit)", ("build",)),
    ("a Block painted by the stage's plain roles (its look ignored: the roof brick, not rusty metal)", PB, "\tif not pick and look and style.looks and style.looks[look] then",
     "\tif not pick and look and not block and style.looks and style.looks[look] then", "look: the Garage's roof sheets", ("data",)),
    ("the sign hung over the doorway (y 5: in the lane)", PB, "sign = { y = 16.4, w = 18, h = 5.5 },", "sign = { y = 5, w = 18, h = 5.5 },", "lane: stage 1 at 0 (kit)", ("build",)),
    ("a Block that ignores its size (built 1 x 1 x 1)", PB, "\t\treturn { box(piece.role, s[1], s[2], s[3], 0, s[2] / 2, 0) }", "\t\treturn { box(piece.role, 1, 1, 1, 0, 0.5, 0) }", "block: stage 1 at 0", ("build",)),
    ("the claim post outside its ClaimSpot (in the garage itself: it streams out on far clients)", CORE,
     '\t\tlocal post = makePart(spot, "ClaimPost",', '\t\tlocal post = makePart(garage, "ClaimPost",', "free:", ("core",)),
]


def apply(sources, file, old, new):
    text = sources[file]
    if text.count(old) != 1:
        return None
    out = dict(sources)
    out[file] = text.replace(old, new)
    return out


def main():
    luau = os.environ.get("LUAU") or shutil.which("luau")
    if not luau:
        print("Luau not found. Download it from https://github.com/luau-lang/luau/releases and set LUAU=/path/to/luau")
        return 2
    names = ("PlotArt.lua", "PlotVisuals.lua", "PlotBuilding.lua", "PlotBuildingVisuals.lua", "BuildingClient.lua", "TycoonCore.lua", "ShopClient.lua", "LobbyConfig.lua")
    sources = {n: read(n) for n in names}
    code = 0
    total_pass = total_fail = 0
    results = run_parts(luau, sources)
    for part in PARTS:
        p, f, failed, crashed = results[part]
        for n in failed:
            print("FAIL (%s): %s" % (part, n))
        if crashed:
            print("CRASH (%s): %s" % (part, crashed))
            code = 1
        print("Building check, %s: %d passed, %d failed" % (part, p, f))
        total_pass += p
        total_fail += f
    stat = static_checks(sources)
    sfail = [(n, e) for n, ok, e in stat if not ok]
    for n, e in sfail:
        print("FAIL (source): " + n + (" -- " + str(e) if e is not None else ""))
    print("Building check, source: %d passed, %d failed" % (len(stat) - len(sfail), len(sfail)))
    total_pass += len(stat) - len(sfail)
    total_fail += len(sfail)
    if total_fail:
        code = 1

    caught = 0
    for label, file, old, new, want, parts in MUTANTS:
        mutated = apply(sources, file, old, new)
        if mutated is None:
            print("NOT CAUGHT: %s -- not applied (its anchor is missing or there twice)" % label)
            continue
        failed_names = []
        crash = None
        if parts:
            res = run_parts(luau, mutated, parts)
            for part in parts:
                p, f, fn, crashed = res[part]
                failed_names += fn
                crash = crash or crashed
        failed_names += [n for n, ok, _ in static_checks(mutated) if not ok]
        hit = [n for n in failed_names if n.startswith(want)]
        if crash:  # a crash is never a catch, even after a named check failed
            print("NOT CAUGHT: %s -- it crashed: %s" % (label, crash[:200]))
        elif hit:
            caught += 1
            print("caught: %s -- by \"%s\"" % (label, hit[0]))
        else:
            print("NOT CAUGHT: %s -- no failing check starts with \"%s\" (failed: %s)" % (label, want, failed_names[:3]))
    print("Building mutations: %d of %d caught, each by its named check" % (caught, len(MUTANTS)))
    if caught != len(MUTANTS):
        code = 1
    print("building_test.py: %d checks passed, %d of %d mutation runs caught" % (total_pass, caught, len(MUTANTS)))
    return code


if __name__ == "__main__":
    sys.exit(main())
