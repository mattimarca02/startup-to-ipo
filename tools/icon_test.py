#!/usr/bin/env python3
"""Tests for the icons (IconArt.lua and IconVisuals.lua), outside Studio.

Run:   python3 tools/icon_test.py

It needs the free Luau command-line tool (https://github.com/luau-lang/luau/releases, the "luau" file from
luau-macos.zip, luau-windows.zip or luau-ubuntu.zip). Put it on your PATH, or point to it:
       LUAU=/path/to/luau python3 tools/icon_test.py

It runs the real IconArt and IconVisuals with its own fake Roblox (UI instances, ViewportFrames and cameras with real
vector maths, model pivots), together with the real CreatureModels, CreatureConfig, ShopConfig and PlotArt, and checks:
every shop item, egg, creature, Office upgrade and HUD button has exactly one icon; every color is in the palette; the
part and shape counts; that every 3D model sits whole inside its camera's picture; the cap on live ViewportFrames while
a list scrolls; that icons are only built when their card is on screen; no image, asset, emoji or odds word; one light
direction and one outline for every icon; the Office icons are PlotArt's own props; nothing moves unless tapped. Then
it breaks the data and the builder on purpose (mutation runs): each must be caught by a named check, never by a crash.

It changes nothing in the game or in Studio. It never edits tools/daily_test.py (other branches own it).
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NEW_LUA = ("IconArt.lua", "IconVisuals.lua")


def read(name):
    with open(os.path.join(ROOT, name), encoding="utf-8") as f:
        return f.read()


def run_luau(luau, source):
    with tempfile.NamedTemporaryFile("w", suffix=".luau", delete=False, encoding="utf-8") as f:
        f.write(source)
        path = f.name
    try:
        return subprocess.run([luau, path], capture_output=True, text=True, timeout=600)
    finally:
        os.unlink(path)


def code_only(text):
    out = []
    for line in text.split("\n"):
        cut = line.find("--")
        out.append(line if cut < 0 else line[:cut])
    return "\n".join(out)


def lua_strings(text):
    code = code_only(text)
    found = re.findall(r'"((?:[^"\\\n]|\\.)*)"', code) + re.findall(r"'((?:[^'\\\n]|\\.)*)'", code)
    found += re.findall(r"\[\[(.*?)\]\]", code, re.S)
    return found


PRELUDE = r"""-- Fake Roblox for the icons: UI instances, ViewportFrames and cameras with real vector maths, model pivots
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
local PRINTED = {}
local function print(...)
	local parts = {}
	for i = 1, select("#", ...) do parts[i] = tostring((select(i, ...))) end
	table.insert(PRINTED, table.concat(parts, " "))
end
local function warn() end
local SPAWNS, CLOCK = 0, 0
local PENDING = {}
local task = {
	spawn = function(f, ...) SPAWNS += 1; table.insert(PENDING, f) end,
	wait = function() CLOCK += 0.05 end,
	delay = function() SPAWNS += 1 end,
}
local os = { clock = function() CLOCK += 0.01; return CLOCK end, time = function() return 0 end }

-- Vector3
local V = {}
local function vec(x, y, z) return setmetatable({ X = x, Y = y, Z = z }, V) end
V.__index = function(t, k)
	if k == "Magnitude" then return math.sqrt(t.X * t.X + t.Y * t.Y + t.Z * t.Z) end
	if k == "Unit" then local m = math.sqrt(t.X * t.X + t.Y * t.Y + t.Z * t.Z) return vec(t.X / m, t.Y / m, t.Z / m) end
	return rawget(V, k)
end
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
local function cross(a, b) return vec(a.Y * b.Z - a.Z * b.Y, a.Z * b.X - a.X * b.Z, a.X * b.Y - a.Y * b.X) end
local Vector3 = { new = function(x, y, z) return vec(x or 0, y or 0, z or 0) end }

-- CFrame: a position and a row-major rotation matrix (columns: right, up, back)
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
CF.__index = function(t, k)
	if k == "Position" then return vec(t.x, t.y, t.z) end
	if k == "LookVector" then local r = t.r return vec(-r[3], -r[6], -r[9]) end
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
function CF.Inverse(t)
	local rt = transpose(t.r)
	return cf(-(rt[1] * t.x + rt[2] * t.y + rt[3] * t.z), -(rt[4] * t.x + rt[5] * t.y + rt[6] * t.z), -(rt[7] * t.x + rt[8] * t.y + rt[9] * t.z), rt)
end
function CF.PointToObjectSpace(t, p) return t:Inverse() * p end
function CF.VectorToWorldSpace(t, v) local r = t.r return vec(r[1] * v.X + r[2] * v.Y + r[3] * v.Z, r[4] * v.X + r[5] * v.Y + r[6] * v.Z, r[7] * v.X + r[8] * v.Y + r[9] * v.Z) end
function CF.VectorToObjectSpace(t, v) local r = transpose(t.r) return vec(r[1] * v.X + r[2] * v.Y + r[3] * v.Z, r[4] * v.X + r[5] * v.Y + r[6] * v.Z, r[7] * v.X + r[8] * v.Y + r[9] * v.Z) end
local function rx(a) local c, s = math.cos(a), math.sin(a) return { 1, 0, 0, 0, c, -s, 0, s, c } end
local function ry(a) local c, s = math.cos(a), math.sin(a) return { c, 0, s, 0, 1, 0, -s, 0, c } end
local function rz(a) local c, s = math.cos(a), math.sin(a) return { c, -s, 0, s, c, 0, 0, 0, 1 } end
local CFrame = {
	new = function(x, y, z)
		if type(x) == "table" then return cf(x.X, x.Y, x.Z) end
		return cf(x or 0, y or 0, z or 0)
	end,
	Angles = function(a, b, c) return cf(0, 0, 0, matmul(matmul(rx(a), ry(b)), rz(c))) end,
	fromEulerAnglesYXZ = function(a, b, c) return cf(0, 0, 0, matmul(matmul(ry(b), rx(a)), rz(c))) end,
	lookAt = function(at, target, up)
		up = up or vec(0, 1, 0)
		local look = (target - at).Unit
		local right = cross(look, up).Unit
		local upv = cross(right, look)
		return cf(at.X, at.Y, at.Z, { right.X, upv.X, -look.X, right.Y, upv.Y, -look.Y, right.Z, upv.Z, -look.Z })
	end,
}

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
	MeshType = enumType({ "Sphere", "Brick", "Cylinder", "Wedge", "FileMesh" }),
	Font = enumType({ "GothamBold", "Gotham", "FredokaOne", "GothamBlack", "LuckiestGuy" }),
	ApplyStrokeMode = enumType({ "Border", "Contextual" }),
	FillDirection = enumType({ "Horizontal", "Vertical" }),
	AutomaticSize = enumType({ "None", "X", "Y", "XY" }),
	SortOrder = enumType({ "LayoutOrder", "Name" }),
	TextXAlignment = enumType({ "Left", "Center", "Right" }),
}
local C3 = {}
C3.__eq = function(a, b) return a.R == b.R and a.G == b.G and a.B == b.B end
local Color3 = {
	fromRGB = function(r, g, b) return setmetatable({ R = r / 255, G = g / 255, B = b / 255, rgb = { r, g, b } }, C3) end,
	new = function(r, g, b) return setmetatable({ R = r, G = g, B = b, rgb = { math.floor(r * 255 + 0.5), math.floor(g * 255 + 0.5), math.floor(b * 255 + 0.5) } }, C3) end,
}
local ColorSequence = { new = function(a, b) return { a, b or a } end }
local NumberSequence = { new = function(a, b) return { a, b or a } end }
local NumberRange = { new = function(a, b) return { a, b or a } end }
local UDim = { new = function(s, o) return { Scale = s, Offset = o } end }
local UDim2 = {
	fromScale = function(x, y) return { X = { Scale = x, Offset = 0 }, Y = { Scale = y, Offset = 0 } } end,
	fromOffset = function(x, y) return { X = { Scale = 0, Offset = x }, Y = { Scale = 0, Offset = y } } end,
	new = function(a, b, c, d) return { X = { Scale = a, Offset = b }, Y = { Scale = c, Offset = d } } end,
}
local Vector2 = { new = function(x, y) return { X = x, Y = y } end }

-- Instances
local IS_A = {
	Part = { BasePart = true, PVInstance = true }, WedgePart = { BasePart = true, PVInstance = true }, Model = { PVInstance = true },
	ViewportFrame = { GuiObject = true, GuiBase2d = true },
	Frame = { GuiObject = true, GuiBase2d = true }, TextLabel = { GuiObject = true, GuiBase2d = true }, ScreenGui = { LayerCollector = true },
	ImageLabel = { GuiObject = true }, Camera = {}, Folder = {},
}
local DEFAULTS = {
	Part = { Anchored = false, CanCollide = true, CanTouch = true, CanQuery = true, CastShadow = true, Transparency = 0, Size = vec(4, 1.2, 2),
		CFrame = cf(0, 0, 0), Color = Color3.fromRGB(163, 162, 165), Material = Enum.Material.Plastic, Shape = Enum.PartType.Block },
	SpecialMesh = { MeshType = Enum.MeshType.Brick, MeshId = "", TextureId = "" },
	Model = {},
	Camera = { CFrame = cf(0, 0, 0), FieldOfView = 70 },
	ViewportFrame = { BackgroundTransparency = 0, LightDirection = vec(-1, -1, -1), Ambient = Color3.fromRGB(200, 200, 200), LightColor = Color3.fromRGB(140, 140, 140) },
	Frame = { BackgroundTransparency = 0, Rotation = 0, ZIndex = 1, BackgroundColor3 = Color3.fromRGB(255, 255, 255) },
	TextLabel = { Text = "Label", BackgroundTransparency = 0, Rotation = 0, ZIndex = 1 },
	UIGradient = { Rotation = 0 },
	UIStroke = { Thickness = 1 },
	UIScale = { Scale = 1 },
}
local Methods = {}
local Mt = {}
Mt.__index = function(t, k)
	if k == "Parent" then return rawget(t, "_parent") end
	local props = rawget(t, "_props")
	if k == "Position" and props and props.CFrame and rawget(t, "ClassName") == "Part" then return props.CFrame.Position end
	if props and props[k] ~= nil then return props[k] end
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
		return
	end
	local props = rawget(t, "_props")
	if k == "Shape" and v and v.Name == "Ball" and props.Size then
		local s = props.Size
		local m = math.min(s.X, s.Y, s.Z)
		props.Size = vec(m, m, m)
	end
	props[k] = v
end
local INSTANCES = 0
local function newInstance(class)
	INSTANCES += 1
	local props = {}
	for k, v in pairs(DEFAULTS[class] or {}) do props[k] = v end
	return setmetatable({ ClassName = class, _children = {}, _attrs = {}, _props = props, Name = class }, Mt)
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
function Methods.IsA(t, class) return t.ClassName == class or (IS_A[t.ClassName] ~= nil and IS_A[t.ClassName][class] == true) end
function Methods.SetAttribute(t, k, v) t._attrs[k] = v end
function Methods.GetAttribute(t, k) return t._attrs[k] end
function Methods.Destroy(t)
	t.Parent = nil
	rawset(t, "destroyed", true)
	for _, c in ipairs(table.clone(t._children)) do c:Destroy() end
end
function Methods.GetFullName(t) local p = t.Parent return (p and p.ClassName ~= "DataModel" and (p:GetFullName() .. ".") or "") .. t.Name end
function Methods.GetPivot(t)
	if t.PrimaryPart then return t.PrimaryPart.CFrame end
	return t.WorldPivot or cf(0, 0, 0)
end
function Methods.PivotTo(t, target)
	local delta = target * t:GetPivot():Inverse()
	for _, d in ipairs(t:GetDescendants()) do
		if d.ClassName == "Part" then d.CFrame = delta * d.CFrame end
	end
	if not t.PrimaryPart then t.WorldPivot = target end
end
function Methods.Clone(t)
	local c = newInstance(t.ClassName)
	for k, v in pairs(t._props) do c._props[k] = v end
	c.Name = t.Name
	for k, v in pairs(t._attrs) do c._attrs[k] = v end
	for _, child in ipairs(t._children) do child:Clone().Parent = c end
	return c
end
function Methods.WaitForChild(t, name) return t:FindFirstChild(name) end
function Methods.FindFirstChildWhichIsA(t, class)
	for _, c in ipairs(t._children) do if c:IsA(class) then return c end end
	return nil
end
IS_A.UIAspectRatioConstraint = { UIConstraint = true }
local game = newInstance("DataModel")
local SERVICES = {}
for _, name in ipairs({ "ReplicatedStorage", "StarterGui", "ServerScriptService", "Workspace" }) do
	local s = newInstance(name)
	s.Name = name
	s.Parent = game
	SERVICES[name] = s
end
local workspace = SERVICES.Workspace
function Methods.GetService(t, name)
	local s = SERVICES[name]
	if not s then error("no service " .. tostring(name)) end
	return s
end
local MODULES = {}
local function require(module)
	local m = MODULES[module]
	if m == nil then error("require of an unknown module " .. tostring(module and module.Name)) end
	return m
end
"""


TESTS = r"""-- Tests: the real IconArt and IconVisuals with the real CreatureModels, CreatureConfig, ShopConfig and PlotArt -------
local IconArt = (function()
__ICONART__
end)()
local IconVisuals = (function()
__ICONVISUALS__
end)()
local CreatureConfig = (function()
__CREATURECONFIG__
end)()
local CreatureModels = (function()
__CREATUREMODELS__
end)()
local ShopConfig = (function()
__SHOPCONFIG__
end)()
local PlotArt = (function()
__PLOTART__
end)()
local UPGRADES = __UPGRADES__
local HUD = __HUD__
local DEPS = { CreatureModels = CreatureModels, CreatureConfig = CreatureConfig }

local function section(name, fn)
	local ok, err = pcall(fn)
	if not ok then check(name .. ": this part of the tests could not finish", false, err) end
end
local function anyMatch(list, word) for _, p in ipairs(list) do if string.find(p, word, 1, true) then return true end end return false end
local function deepCopy(t)
	if type(t) ~= "table" then return t end
	local c = {}
	for k, v in pairs(t) do c[deepCopy(k)] = deepCopy(v) end
	return setmetatable(c, getmetatable(t))
end

-- What the game has: every key that needs an icon
local EXPECT = { Office = UPGRADES, Eggs = {}, Creatures = {}, Shop = {}, Hud = HUD, rarity = {}, noText = {} }
for _, egg in ipairs(CreatureConfig.Eggs) do table.insert(EXPECT.Eggs, egg.key) end
for _, c in ipairs(CreatureConfig.Creatures) do table.insert(EXPECT.Creatures, c.key); EXPECT.rarity[c.key] = c.rarity end
for _, list in ipairs({ ShopConfig.Passes, ShopConfig.Products }) do
	for _, item in ipairs(list) do
		table.insert(EXPECT.Shop, item.key)
		if item.changesOdds then EXPECT.noText[item.key] = true end
	end
end
local ICONS, BYID = {}, {}
local function buildAll(art, size)
	local holder = newInstance("Folder")
	local out = {}
	for _, group in ipairs(IconVisuals.GROUPS) do
		for _, key in ipairs(EXPECT[group]) do
			local icon = IconVisuals.build(holder, art or IconArt, group, key, size or 56, DEPS)
			if icon then table.insert(out, icon) end
		end
	end
	return out
end
local function results(art, icons)
	local by = {}
	for _, r in ipairs(IconVisuals.checks(art or IconArt, icons, EXPECT)) do by[r.name] = r.problems end
	return by
end

-- 1. The data -------------------------------------------------------------------------------------------------------
section("data", function()
	local problems = IconVisuals.validate(IconArt)
	check("data: IconVisuals.validate finds no problem in IconArt", #problems == 0, problems[1])
	check("data: every named check exists, in order", table.concat(IconVisuals.CHECKS, ",") == "data,coverage,palette,assets,texts,style,framing,budget,grid")
	check("data: the icons are 56 px on cards and 72 px on the biggest card, at phone size", IconVisuals.pixels(IconArt, "card") == 56 and IconVisuals.pixels(IconArt, "hero") == 72)
	check("data: at most 8 3D icons (ViewportFrames) live at once", IconArt.Style.viewportCap == 8)
	check("data: the only texts are 2x, +3 and $", table.concat(IconArt.Texts, " ") == "2x +3 $")
	check("data: one light direction for every icon (top-left, gradient at 45 degrees, light (1, -1, -1) in the camera's frame)",
		IconArt.Style.lightRotation == 45 and IconArt.Style.lightDirection[1] == 1 and IconArt.Style.lightDirection[2] == -1 and IconArt.Style.lightDirection[3] == -1)
	local count = 0
	for _, group in ipairs(IconVisuals.GROUPS) do for _ in pairs(IconArt[group]) do count += 1 end end
	check("data: 38 recipes (6 Office, 3 eggs, 12 creatures, 12 shop items, 5 HUD buttons)", count == 38, count)
end)

-- 2. Coverage: exactly one recipe for everything in the game -------------------------------------------------------------
section("coverage", function()
	check("coverage: the six Office upgrades are TycoonCore's UPGRADES, in order", #UPGRADES == 6 and UPGRADES[1] == "Desk" and UPGRADES[6] == "Neon Logo")
	check("coverage: the five HUD buttons are EGGS, SHOP, TEAM, POACH and IPO", table.concat(HUD, ",") == "Eggs,Shop,Team,Poach,Ipo")
	check("coverage: 12 shop items (6 passes, 6 products), 3 eggs, 12 creatures in the configs", #EXPECT.Shop == 12 and #EXPECT.Eggs == 3 and #EXPECT.Creatures == 12)
	for _, group in ipairs(IconVisuals.GROUPS) do
		local n = 0
		for _ in pairs(IconArt[group]) do n += 1 end
		check("coverage: " .. group .. " has exactly one recipe per key (" .. n .. ")", n == #EXPECT[group])
	end
	local rarities = {}
	for _, r in ipairs(CreatureConfig.Rarities) do rarities[r.key] = true end
	local same = true
	for k in pairs(IconArt.RarityPlates) do if not rarities[k] then same = false end end
	for k in pairs(rarities) do if not IconArt.RarityPlates[k] then same = false end end
	check("coverage: a plate per CreatureConfig rarity, no more", same)
	for _, egg in ipairs(CreatureConfig.Eggs) do
		local body = IconArt.Eggs[egg.key] and IconArt.Eggs[egg.key].shapes[1]
		local c = body and IconArt.Palette[body.color]
		check("coverage: the " .. egg.key .. " egg icon has CreatureConfig's egg color", c ~= nil and c[1] == egg.color.rgb[1] and c[2] == egg.color.rgb[2] and c[3] == egg.color.rgb[3])
	end
	check("coverage: the item that changes odds is marked noText and has no text shape", (function()
		for key in pairs(EXPECT.noText) do
			local recipe = IconArt.Shop[key]
			if not (recipe and recipe.noText) then return false end
			for _, s in ipairs(recipe.shapes) do if s.kind == "text" then return false end end
		end
		return next(EXPECT.noText) ~= nil
	end)())
end)

-- 3. The Office icons are PlotArt's own props (copied: PlotArt lives on the server) --------------------------------------
section("props", function()
	for _, name in ipairs(UPGRADES) do
		local mine, theirs = IconArt.Models[IconArt.Office[name].model], PlotArt.Props[name]
		local same = mine ~= nil and theirs ~= nil and #mine == #theirs
		local k = same and (theirs[1].size[1] / mine[1].size[1]) or 0
		if same then
			for i, p in ipairs(mine) do
				local q = theirs[i]
				local c = IconArt.Palette[p.color]
				if p.name ~= q.name or p.shape ~= q.shape or p.material ~= q.material or c == nil or c[1] ~= q.color[1] or c[2] ~= q.color[2] or c[3] ~= q.color[3] then same = false end
				for j = 1, 3 do
					if math.abs(p.size[j] * k - q.size[j]) > 1e-6 or math.abs(p.offset[j] * k - q.offset[j]) > 1e-6 then same = false end
					if (p.rot and p.rot[j] or 0) ~= (q.rot and q.rot[j] or 0) then same = false end
				end
			end
		end
		check(string.format("props: the %s icon is PlotArt's %s prop, part for part (scale %.1f)", name, name, k), same)
	end
end)

-- 4. Every icon, built at card size and at hero size ---------------------------------------------------------------------
section("icons", function()
	SPAWNS = 0
	ICONS = buildAll(IconArt, 56)
	local by = results(IconArt, ICONS)
	for _, name in ipairs(IconVisuals.CHECKS) do
		check("icons at 56 px: check " .. name .. " passes", by[name] ~= nil and #by[name] == 0, by[name] and by[name][1])
	end
	local hero = buildAll(IconArt, 72)
	local byHero = results(IconArt, hero)
	local heroBad = nil
	for _, name in ipairs(IconVisuals.CHECKS) do if #byHero[name] > 0 then heroBad = heroBad or (name .. ": " .. byHero[name][1]) end end
	check("icons at 72 px: every check passes", heroBad == nil, heroBad)
	check("icons: building all 76 made no animation start (nothing moves unless tapped)", SPAWNS == 0, SPAWNS)
	for _, icon in ipairs(ICONS) do BYID[icon:GetAttribute("Group") .. "/" .. icon:GetAttribute("Key")] = icon end
	local views, uis = 0, 0
	for _, icon in ipairs(ICONS) do
		if icon:FindFirstChild("View") then views += 1 elseif icon:FindFirstChild("Art") then uis += 1 end
	end
	check("icons: 18 are 3D (6 props, 12 creatures) and 20 are drawn shapes", views == 18 and uis == 20, views .. "/" .. uis)
	local clover = BYID["Shop/" .. next(EXPECT.noText)]
	local texts = 0
	for _, d in ipairs(clover:GetDescendants()) do if d.ClassName == "TextLabel" then texts += 1 end end
	check("icons: the clover has no text at all", texts == 0 and clover:GetAttribute("Recipe") == "Clover")
	local coin = BYID["Shop/DoubleCash"]
	check("icons: the 2x Cash coin says 2x", coin:FindFirstChild("CoinLabel", true) ~= nil and coin:FindFirstChild("CoinLabel", true).Text == "2x")
	check("icons: card icons sit on an outlined plate, HUD icons on none", BYID["Shop/VIP"]:FindFirstChild("Plate") ~= nil and BYID["Shop/VIP"]:FindFirstChild("OutlinePlate") ~= nil
		and BYID["Hud/Shop"]:FindFirstChild("Plate") == nil)
	local creature = BYID["Creatures/UnicornCEO"]
	check("icons: a creature icon shows CreatureModels' model on its rarity's plate", creature:FindFirstChild("View"):FindFirstChild("Model"):FindFirstChild("Horn") ~= nil
		and creature:FindFirstChild("Plate").BackgroundColor3 == Color3.fromRGB(table.unpack(IconArt.Palette.plateLegendary)))
	check("icons: every icon fills its slot and keeps it square", (function()
		for _, icon in ipairs(ICONS) do
			if icon.Size.X.Scale ~= 1 or icon.Size.Y.Scale ~= 1 or not icon:FindFirstChildWhichIsA("UIAspectRatioConstraint") then return false end
		end
		return true
	end)())
	check("icons: a diamond is a square turned 45 degrees (the crown's points)", BYID["Shop/VIP"]:FindFirstChild("PointLeft", true).Rotation == 45
		and BYID["Shop/VIP"]:FindFirstChild("OutlinePointLeft", true).Rotation == 45)
	check("icons: outline widths are 2 px at 56 and 3 px at 72", IconVisuals.outlinePx(IconArt, 56) == 2 and IconVisuals.outlinePx(IconArt, 72) == 3)
	local ring = coin:FindFirstChild("CoinRim", true):FindFirstChild("Line")
	check("icons: a ring's line scales with the icon (4 grid units = 2.24 px at 56)", math.abs(ring.Thickness - 2.24) < 1e-9, ring.Thickness)
	check("icons: an unknown key builds nothing (and never errors)", IconVisuals.build(nil, IconArt, "Shop", "NoSuchItem", 56, DEPS) == nil
		and IconVisuals.build(nil, IconArt, "NoGroup", "Desk", 56, DEPS) == nil)
end)
-- 5. The pure functions --------------------------------------------------------------------------------------------------
section("pure", function()
	local seed = 4242
	local function rand() seed = (seed * 1664525 + 1013904223) % 4294967296 return seed / 4294967296 end
	local bad, loose = nil, nil
	for _ = 1, 400 do
		local box = { -rand() * 5, rand() * 5, -rand() * 3, rand() * 8, -rand() * 4, rand() * 4 }
		local view = { yaw = rand() * 360 - 180, pitch = rand() * 100 - 50 }
		local fov, padding = 20 + rand() * 40, rand() * 0.3
		local shot = IconVisuals.frame(box, view, fov, padding)
		local t = math.tan(math.rad(fov) / 2)
		local reach = 0
		for _, x in ipairs({ box[1], box[2] }) do for _, y in ipairs({ box[3], box[4] }) do for _, z in ipairs({ box[5], box[6] }) do
			local rel = { x - shot.eye[1], y - shot.eye[2], z - shot.eye[3] }
			local cx = rel[1] * shot.right[1] + rel[2] * shot.right[2] + rel[3] * shot.right[3]
			local cy = rel[1] * shot.up[1] + rel[2] * shot.up[2] + rel[3] * shot.up[3]
			local depth = -(rel[1] * shot.back[1] + rel[2] * shot.back[2] + rel[3] * shot.back[3])
			if depth <= 0 then bad = bad or "a corner behind the camera" end
			local s = math.max(math.abs(cx), math.abs(cy)) / depth / t
			reach = math.max(reach, s)
			if s > (1 - padding) + 1e-6 then bad = bad or string.format("a corner at %.3f of the picture (padding %.2f)", s, padding) end
		end end end
		if reach < (1 - padding) - 1e-6 then loose = loose or string.format("the model only reaches %.3f, not %.3f", reach, 1 - padding) end
	end
	check("frame: 400 boxes, views and lenses: every corner inside the picture, padding kept", bad == nil, bad)
	check("frame: and as close as it can be (the farthest corner touches the padding)", loose == nil, loose)
	local p = IconVisuals.plan({}, { 1, 2, 3 }, 8)
	check("plan: icons on screen are made while there is room", #p.make == 3 and #p.drop == 0 and #p.wait == 0)
	p = IconVisuals.plan({ [1] = 5, [2] = 9, [3] = 7 }, { 4 }, 3)
	check("plan: at the cap, the icon seen longest ago makes room", #p.make == 1 and p.make[1] == 4 and #p.drop == 1 and p.drop[1] == 1)
	p = IconVisuals.plan({ [1] = 5, [2] = 9 }, { 1, 2, 3 }, 2)
	check("plan: when every live icon is on screen, the new one waits (never past the cap)", #p.make == 0 and #p.drop == 0 and #p.wait == 1 and p.wait[1] == 3)
	p = IconVisuals.plan({ [1] = 5, [2] = 9 }, { 1, 2 }, 2)
	check("plan: icons already live are kept as they are", #p.make == 0 and #p.drop == 0 and #p.wait == 0)
	p = IconVisuals.plan({ [7] = 3, [4] = 3 }, { 9 }, 2)
	check("plan: a tie in age drops the lowest key first (always the same result)", p.drop[1] == 4)
	check("spin: 0 degrees before the tap, 360 at the end, half way in the middle, never past", IconVisuals.spinAngle(0, 1.2) == 0 and IconVisuals.spinAngle(1.2, 1.2) == 360
		and math.abs(IconVisuals.spinAngle(0.6, 1.2) - 180) < 1e-9 and IconVisuals.spinAngle(5, 1.2) == 360 and IconVisuals.spinAngle(-1, 1.2) == 0
		and IconVisuals.spinAngle(0 / 0, 1.2) == 0 and IconVisuals.spinAngle(0.5, 0) == 0)
	check("pop: 1 before and after, at most 1.12 in the middle", IconVisuals.popScale(0, 0.3) == 1 and IconVisuals.popScale(0.3, 0.3) == 1
		and math.abs(IconVisuals.popScale(0.15, 0.3) - 1.12) < 1e-9 and IconVisuals.popScale(0 / 0, 0.3) == 1)
	local b = IconVisuals.shapeBox(IconArt, { kind = "diamond", x = 40, y = 40, w = 20, h = 20 })
	check("shapeBox: a diamond's box is its turned square (20 wide becomes 28.3)", math.abs((b[2] - b[1]) - 20 * math.sqrt(2)) < 1e-9)
	b = IconVisuals.shapeBox(IconArt, { kind = "rect", x = 10, y = 10, w = 20, h = 10, outline = true })
	check("shapeBox: an outlined rect grows by the outline on every side", b[1] == 6 and b[2] == 34 and b[3] == 6 and b[4] == 24)
end)

-- 6. Lazy creation and the cap while a list scrolls -----------------------------------------------------------------------
section("lazy", function()
	local cache = IconVisuals.newCache(IconArt, DEPS)
	local slots = {}
	for _, group in ipairs(IconVisuals.GROUPS) do
		for _, key in ipairs(EXPECT[group]) do
			local frame = newInstance("Frame")
			frame.Name = "Slot"
			table.insert(slots, { frame = frame, group = group, key = key, size = 56 })
		end
	end
	check("lazy: a list of 38 cards builds nothing before it is shown", cache.built == 0)
	local function window(from, count)
		local out = {}
		for i = from, math.min(#slots, from + count - 1) do table.insert(out, slots[i]) end
		return out
	end
	local live = IconVisuals.show(cache, window(1, 4))
	check("lazy: 4 cards on screen build 4 icons", cache.built == 4)
	local worst, missing = 0, nil
	SPAWNS = 0
	for from = 1, #slots - 3 do
		live = IconVisuals.show(cache, window(from, 4))
		local views = 0
		for _, entry in pairs(cache.live) do views += 1 end
		worst = math.max(worst, views)
		for _, slot in ipairs(window(from, 4)) do
			if not slot.frame:FindFirstChild("Icon") and not slot.frame:FindFirstChild("Waiting") then missing = missing or (slot.group .. "/" .. slot.key) end
		end
	end
	check("lazy: scrolling the whole list, never more than 8 ViewportFrames exist (" .. worst .. " at most)", worst <= 8 and worst > 0, worst)
	check("lazy: every card on screen shows its icon (or its plate while it waits)", missing == nil, missing)
	check("lazy: scrolling starts no animation", SPAWNS == 0)
	local built = cache.built
	IconVisuals.show(cache, window(#slots - 3, 4))
	check("lazy: showing the same cards again builds nothing", cache.built == built, cache.built - built)
	IconVisuals.show(cache, window(22, 4)) -- four shop cards (drawn icons) seen long ago
	check("lazy: drawn icons that left the screen are reused when they come back (not built again)", cache.built == built, cache.built - built)
	IconVisuals.show(cache, window(1, 4))
	check("lazy: back at the top, only the 3D icons dropped for room are built again (4 here)", cache.built - built == 4, cache.built - built)
	-- Ten 3D cards on screen at once (more than the cap): 8 get their model, 2 wait with their plate
	local big = {}
	for i, key in ipairs(EXPECT.Creatures) do
		if i <= 10 then
			local frame = newInstance("Frame")
			table.insert(big, { frame = frame, group = "Creatures", key = key, size = 56 })
		end
	end
	local fresh = IconVisuals.newCache(IconArt, DEPS)
	local count = IconVisuals.show(fresh, big)
	local waiting = 0
	for _, slot in ipairs(big) do if slot.frame:FindFirstChild("Waiting") then waiting += 1 end end
	check("lazy: ten 3D icons on screen at once: 8 are built, 2 show their plate and wait", count == 8 and waiting == 2, count .. "/" .. waiting)
	IconVisuals.show(fresh, { big[9], big[10] })
	local nine = big[9].frame:FindFirstChild("Icon")
	check("lazy: once room is free, the waiting ones get their model and lose the plate", nine ~= nil and big[9].frame:FindFirstChild("Waiting") == nil)
	-- Two slots showing the same creature (two Coding Cats in the Team list): two icons
	local twins = { { frame = newInstance("Frame"), group = "Creatures", key = "CodingCat", size = 56 }, { frame = newInstance("Frame"), group = "Creatures", key = "CodingCat", size = 56 } }
	local tw = IconVisuals.newCache(IconArt, DEPS)
	IconVisuals.show(tw, twins)
	check("lazy: the same creature twice on screen gets an icon in each slot", twins[1].frame:FindFirstChild("Icon") ~= nil and twins[2].frame:FindFirstChild("Icon") ~= nil)
	-- A slot that now shows another item gets the new icon
	twins[1].key = "SalesShark"
	IconVisuals.show(tw, twins)
	check("lazy: a slot that changes item changes icon", twins[1].frame:FindFirstChild("Icon"):GetAttribute("Key") == "SalesShark")
end)

-- 7. Taps ----------------------------------------------------------------------------------------------------------------
section("tap", function()
	local holder = newInstance("Folder")
	local icon = IconVisuals.build(holder, IconArt, "Office", "Desk", 72, DEPS)
	local model = icon:FindFirstChild("View"):FindFirstChild("Model")
	local before = model:GetPivot()
	SPAWNS = 0
	table.clear(PENDING)
	check("tap: a tap starts one animation", IconVisuals.tap(icon) == true and SPAWNS == 1)
	check("tap: a second tap while it moves is ignored", IconVisuals.tap(icon) == false and SPAWNS == 1)
	PENDING[1]()
	local after = model:GetPivot()
	check("tap: after the spin the model is back exactly where it was", math.abs(after.x - before.x) < 1e-9 and math.abs(after.z - before.z) < 1e-9
		and math.abs(after.r[1] - before.r[1]) < 1e-9 and icon:GetAttribute("Moving") == false)
	local ui = IconVisuals.build(holder, IconArt, "Shop", "VIP", 56, DEPS)
	table.clear(PENDING)
	IconVisuals.tap(ui)
	PENDING[1]()
	check("tap: a drawn icon pops and ends at its own size", ui:FindFirstChild("Pop").Scale == 1)
end)

-- 8. The checks catch broken icons (a check that can't fail proves nothing) -------------------------------------------------
section("negative", function()
	local function fresh() return buildAll(IconArt, 56) end
	local function fails(icons, name, word, art)
		local r = results(art or IconArt, icons)[name]
		return r ~= nil and anyMatch(r, word), r and r[1]
	end
	local icons = fresh()
	local function find(id) for _, i in ipairs(icons) do if i:GetAttribute("Group") .. "/" .. i:GetAttribute("Key") == id then return i end end end
	local img = newInstance("ImageLabel")
	img.Parent = find("Shop/VIP")
	check("negative assets: an image in an icon is caught", fails(icons, "assets", "ImageLabel"))
	img.Parent = nil
	local mesh = newInstance("SpecialMesh")
	mesh.MeshType = Enum.MeshType.FileMesh
	mesh.MeshId = "rbxassetid://1"
	mesh.Parent = find("Office/Desk"):FindFirstChild("View"):FindFirstChild("Model"):GetChildren()[1]
	check("negative assets: a mesh file in an icon is caught", fails(icons, "assets", "no mesh or texture file"))
	mesh.Parent = nil
	local wedge = newInstance("WedgePart")
	wedge.Parent = find("Office/Desk"):FindFirstChild("View"):FindFirstChild("Model")
	check("negative assets: a WedgePart (not a plain Part) in a 3D icon is caught", fails(icons, "assets", "only plain Parts"))
	wedge.Parent = nil
	local label = find("Shop/DoubleCash"):FindFirstChild("CoinLabel", true)
	label.Text = "50%"
	check("negative texts: a word that is not in IconArt.Texts is caught", fails(icons, "texts", "is not one of IconArt.Texts"))
	label.Text = "2x"
	local extra = newInstance("TextLabel")
	extra.Text = "$"
	extra.Parent = find("Shop/" .. next(EXPECT.noText))
	check("negative texts: any text on the clover is caught", fails(icons, "texts", "shows no text at all"))
	extra.Parent = nil
	local grad = find("Shop/VIP"):FindFirstChild("Band", true):FindFirstChild("Shade")
	grad.Rotation = 135
	check("negative style: a gradient lit from another side is caught", fails(icons, "style", "top-left"))
	grad.Rotation = 45
	local view = find("Creatures/CodingCat"):FindFirstChild("View")
	local light = view.LightDirection
	view.LightDirection = Vector3.new(-1, -1, -1)
	check("negative style: a 3D icon lit from another side is caught", fails(icons, "style", "picture's top-left"))
	view.LightDirection = light
	local camera = find("Office/Whiteboard"):FindFirstChild("View").CurrentCamera
	local shot = camera.CFrame
	camera.CFrame = shot * CFrame.new(0, 0, -shot.Position.Magnitude * 0.2) -- moved 20% closer to the board
	check("negative framing: a camera too close (the board sticks out) is caught", fails(icons, "framing", "sticks out of the picture"))
	camera.CFrame = shot * CFrame.new(0, 0, 60)
	check("negative framing: a camera so far the model is a speck is caught", fails(icons, "framing", "fills only"))
	camera.CFrame = shot
	local model = find("Office/Laptop"):FindFirstChild("View"):FindFirstChild("Model")
	for i = 1, 20 do
		local p = newInstance("Part")
		p.Size = vec(0.1, 0.1, 0.1)
		p.CFrame = CFrame.new(0, 2.6, 0)
		p.Parent = model
	end
	check("negative budget: 37 parts in one 3D icon are caught (at most 30)", fails(icons, "budget", "parts (at most 30)"))
	local art = find("Hud/Ipo"):FindFirstChild("Art")
	for i = 1, 14 do
		local f = newInstance("Frame")
		f.Name = "Extra" .. i
		f.Parent = art
	end
	check("negative budget: 19 shapes in one drawn icon are caught (at most 16)", fails(icons, "budget", "shapes (at most 16)"))
	icons = fresh()
	local plate = find("Eggs/Garage"):FindFirstChild("Plate")
	plate.Parent = nil
	check("negative style: a card icon without its plate is caught", fails(icons, "style", "sits on a plate"))
	local outline = find("Hud/Team"):FindFirstChild("OutlineHeadFront", true)
	outline.BackgroundColor3 = Color3.fromRGB(255, 0, 0)
	check("negative style: an outline in another color is caught", fails(icons, "style", "outline color"))
	table.remove(icons, 1)
	check("negative coverage: an icon that was never built is caught", fails(icons, "coverage", "was not built"))
	local copy = deepCopy(IconArt)
	copy.Shop.PoachShield = nil
	check("negative coverage: a shop item without a recipe is caught", fails(fresh(), "coverage", "Shop PoachShield has no icon", copy))
	copy = deepCopy(IconArt)
	copy.Shop.OldThing = copy.Shop.VIP
	check("negative coverage: a recipe for a key the game doesn't have is caught", fails(fresh(), "coverage", "nothing in the game uses that key", copy))
	copy = deepCopy(IconArt)
	copy.Creatures.CodingCat.plate = "plateLegendary"
	check("negative coverage: a creature on another rarity's plate is caught", fails(fresh(), "coverage", "CodingCat: its plate", copy))
	copy = deepCopy(IconArt)
	copy.Shop.VIP.shapes[1].color = "royalPurple"
	check("negative palette: a color that is not in the palette is caught", fails(fresh(), "palette", "royalPurple", copy))
	copy = deepCopy(IconArt)
	copy.Hud.Eggs.shapes[1].x = 70
	check("negative grid: a shape reaching out of the grid is caught", fails(fresh(), "grid", "Hud.Eggs.EggBody: reaches out", copy))
	local v = IconVisuals.validate
	copy = deepCopy(IconArt)
	copy.Shop.VIP.shapes[2].kind = "star"
	check("negative data: an unknown shape kind is caught", anyMatch(v(copy), "unknown shape kind star"))
	copy = deepCopy(IconArt)
	copy.Shop.VIP.shapes[4].w = 12
	check("negative data: a circle that isn't round is caught", anyMatch(v(copy), "a circle needs w = h"))
	copy = deepCopy(IconArt)
	copy.Hud.Ipo.plate = "plateCream"
	check("negative data: a plate on a HUD icon is caught", anyMatch(v(copy), "has no plate"))
	copy = deepCopy(IconArt)
	copy.Models.Desk[1].text = { value = "BIG IDEAS" }
	check("negative data: a text on a 3D part (a ViewportFrame can't draw it) is caught", anyMatch(v(copy), "draws no text"))
	copy = deepCopy(IconArt)
	copy.Office.Desk.view.pitch = 80
	check("negative data: a view from straight above is caught", anyMatch(v(copy), "pitch within 60"))
	copy = deepCopy(IconArt)
	copy.Shop.CashLarge.name = "Bag"
	check("negative data: two recipes with the same name are caught", anyMatch(v(copy), "is used twice"))
	copy = deepCopy(IconArt)
	table.insert(copy.Texts, "WIN BIG")
	check("negative data: a long text label is caught", anyMatch(v(copy), "short plain labels"))
	copy = deepCopy(IconArt)
	table.insert(copy.Shop[next(EXPECT.noText)].shapes, { kind = "text", name = "Tag", x = 40, y = 40, w = 20, h = 20, color = "white", text = "2x" })
	check("negative data: a text shape on the clover is caught", anyMatch(v(copy), "shows no text at all"))
end)

print_real(string.format("%d passed, %d failed", passed, failed))
"""


PREVIEW_TESTS = r"""-- Tests: the icon preview block of docs/STUDIO_SYNC_WORLD.md, run as it is in a fake place -------------------------
local loaded = {
	IconArt = (function()
__ICONART__
	end)(),
	IconVisuals = (function()
__ICONVISUALS__
	end)(),
	CreatureConfig = (function()
__CREATURECONFIG__
	end)(),
	CreatureModels = (function()
__CREATUREMODELS__
	end)(),
	ShopConfig = (function()
__SHOPCONFIG__
	end)(),
}
local RS, StarterGui = SERVICES.ReplicatedStorage, SERVICES.StarterGui
for name, module in pairs(loaded) do
	local script = newInstance("ModuleScript")
	script.Name = name
	script.Parent = RS
	MODULES[script] = module
end
local baseClone = Methods.Clone
function Methods.Clone(t)
	local c = baseClone(t)
	if MODULES[t] ~= nil then MODULES[c] = MODULES[t] end
	return c
end
local REAL_HUD = __HUDCOLORS__
local function has(prefix)
	for _, line in ipairs(PRINTED) do if string.sub(line, 1, #prefix) == prefix then return true end end
	return false
end
local function runPreview()
	table.clear(PRINTED)
	return pcall(function()
__PREVIEW__
	end)
end
local ok, err = runPreview()
check("icon preview: the block runs in the fake place without an error", ok, err)
local gui = StarterGui:FindFirstChild("PREVIEW_ICONS")
local sheet = gui and gui:FindFirstChild("Sheet")
local cells, icons, missing = 0, 0, 0
for _, cell in ipairs(sheet and sheet:GetChildren() or {}) do
	if cell.ClassName == "Frame" then
		cells += 1
		local slot = cell:FindFirstChild("Slot")
		if slot and slot:FindFirstChild("Icon") then icons += 1 end
		if string.find(cell:FindFirstChild("Caption").Text, "MISSING", 1, true) then missing += 1 end
	end
end
check("icon preview: StarterGui.PREVIEW_ICONS holds 38 cells, each with its icon and a caption", gui ~= nil and cells == 38 and icons == 38 and missing == 0, cells .. "/" .. icons .. "/" .. missing)
for _, name in ipairs(loaded.IconVisuals.CHECKS) do
	check("icon preview: it prints OK for the check " .. name, has("OK " .. name), PRINTED[1])
end
check("icon preview: it prints the count line (38 icons, 18 3D, 20 drawn, the cap of 8)",
	has("PREVIEW_ICONS: 38 icons (18 3D, 20 drawn). The game keeps at most 8 3D icons alive; this sheet shows all. Delete it before publishing."))
local captions = {}
for _, cell in ipairs(sheet:GetChildren()) do
	local caption = cell:FindFirstChild("Caption")
	if caption then captions[caption.Text] = true end
end
check("icon preview: captions name the drawing, never the product's word (Shop: Clover, Shop: Coin2x, Hud: HudMagnet)", captions["Shop: Clover"] and captions["Shop: Coin2x"] and captions["Hud: HudMagnet"])
local hudOk = true
for _, cell in ipairs(sheet:GetChildren()) do
	local slot = cell:FindFirstChild("Slot")
	local icon = slot and slot:FindFirstChild("Icon")
	if icon and icon:GetAttribute("Group") == "Hud" then
		local want = REAL_HUD[icon:GetAttribute("Key")]
		if not want or slot.BackgroundColor3 ~= Color3.fromRGB(want[1], want[2], want[3]) or slot.BackgroundTransparency ~= 0 then hudOk = false end
	end
end
check("icon preview: each HUD icon sits on its button's real color (from the client scripts)", hudOk)
runPreview()
local n = 0
for _, c in ipairs(StarterGui:GetChildren()) do if c.Name == "PREVIEW_ICONS" then n += 1 end end
check("icon preview: running it again replaces the old sheet (one PREVIEW_ICONS)", n == 1)
local saved = {}
for _, c in ipairs(RS:GetChildren()) do if c.Name == "IconArt" or c.Name == "IconVisuals" then table.insert(saved, c); c.Parent = nil end end
local missingOk, missingErr = runPreview()
check("icon preview: without the two ModuleScripts it stops at once with a clear message", not missingOk and string.find(tostring(missingErr), "First create the ModuleScripts", 1, true) ~= nil, missingErr)
for _, c in ipairs(saved) do c.Parent = RS end
print_real(string.format("%d passed, %d failed", passed, failed))
"""


def hud_colors_lua():
    """The HUD buttons' background colors, read from the four client scripts."""
    def color(filename, field):
        text = read(filename)
        m = re.search(r"\b%s = Color3\.fromRGB\((\d+), (\d+), (\d+)\)" % field, text)
        if not m or ("BackgroundColor3 = COLORS.%s," % field) not in text:
            raise SystemExit("icon_test: the %s button color changed in %s" % (field, filename))
        return "{ %s, %s, %s }" % m.groups()
    employee, shop, poach, ipo = color("EmployeeClient.lua", "hud"), color("ShopClient.lua", "buy"), color("PoachClient.lua", "poach"), color("IpoClient.lua", "hud")
    return "{ Eggs = %s, Shop = %s, Team = %s, Poach = %s, Ipo = %s }" % (employee, shop, employee, poach, ipo)


def doc_block(heading):
    text = read("docs/STUDIO_SYNC_WORLD.md")
    start = text.index("```lua\n", text.index(heading)) + len("```lua\n")
    return text[start:text.index("```", start)]


def preview_source():
    block = "\n".join("\t\t" + line if line.strip() else line for line in doc_block("## The icon preview (command bar)").split("\n"))
    text = PREVIEW_TESTS
    for key, value in (("__ICONART__", read("IconArt.lua")), ("__ICONVISUALS__", read("IconVisuals.lua")), ("__CREATURECONFIG__", read("CreatureConfig.lua")),
                       ("__CREATUREMODELS__", read("CreatureModels.lua")), ("__SHOPCONFIG__", read("ShopConfig.lua")), ("__HUDCOLORS__", hud_colors_lua()),
                       ("__PREVIEW__", block)):
        text = text.replace(key, value)
    return PRELUDE + text


def upgrades_lua():
    core = read("TycoonCore.lua")
    names = re.findall(r'\{ name = "([^"]+)",\s+cost = ', core)
    if len(names) != 6:
        raise SystemExit("icon_test: TycoonCore's UPGRADES changed (%d found): the Office icons must be checked again" % len(names))
    return "{ " + ", ".join('"%s"' % n for n in names) + " }"


def hud_lua():
    """The five HUD buttons, from the client scripts (names and slots), as IconArt.Hud keys."""
    found = {}
    employee = read("EmployeeClient.lua")
    for name, slot in re.findall(r'hudButton\("(\w+)Button", "[^"]*", (\d)\)', employee):
        found[int(slot)] = name
    shop, poach, ipo = read("ShopClient.lua"), read("PoachClient.lua"), read("IpoClient.lua")
    if 'Name = "ShopButton"' in shop and "placeHudButton(shopButton, 1)" in shop:
        found[1] = "Shop"
    if 'Name = "PoachButton"' in poach and "local HUD_SLOT = 3" in poach:
        found[3] = "Poach"
    if 'Name = "IpoButton"' in ipo and "local HUD_SLOT = 4" in ipo:
        found[4] = "Ipo"
    if sorted(found) != [0, 1, 2, 3, 4]:
        raise SystemExit("icon_test: the HUD buttons changed (%r): the HUD icons must be checked again" % found)
    return "{ " + ", ".join('"%s"' % found[i] for i in range(5)) + " }"


def icon_source(art=None, visuals=None):
    replacements = {
        "__ICONART__": art if art is not None else read("IconArt.lua"),
        "__ICONVISUALS__": visuals if visuals is not None else read("IconVisuals.lua"),
        "__CREATURECONFIG__": read("CreatureConfig.lua"),
        "__CREATUREMODELS__": read("CreatureModels.lua"),
        "__SHOPCONFIG__": read("ShopConfig.lua"),
        "__PLOTART__": read("PlotArt.lua"),
        "__UPGRADES__": upgrades_lua(),
        "__HUD__": hud_lua(),
    }
    text = TESTS
    for key, value in replacements.items():
        text = text.replace(key, value)
    return PRELUDE + text


def static_checks():
    passed, failed = 0, 0

    def check(name, cond, extra=None):
        nonlocal passed, failed
        if cond:
            passed += 1
        else:
            failed += 1
            print("FAIL: " + name + (" -- " + str(extra) if extra else ""))

    for name in NEW_LUA:
        text = read(name)
        code = code_only(text)
        for word in (".Touched", "math.random", "Random.new", "RemoteEvent", "RemoteFunction", "DataStore", "SetAsync", "addEarnings",
                     "rbxasset", "http", "MeshId =", "TextureId =", "Image =", "ImageLabel\"", "loadstring", "FireServer", "InvokeServer",
                     "PromptProductPurchase", "PromptGamePassPurchase", "LocalPlayer", "TweenService", "RenderStepped", "Heartbeat"):
            check("%s never uses %s (looks only: no remote, save, asset, randomness or running animation)" % (name, word), word not in code)
        check("%s is plain ASCII (no emoji or other symbols anywhere, comments included)" % name, all(ord(c) < 128 for c in text),
              sorted(set(c for c in text if ord(c) >= 128)))
        offending = [lit for lit in lua_strings(text) if any(w in lit.lower() for w in ("random", "chance", "odds", "luck"))]
        check("%s: no string uses the words random, chance, odds or luck (D9)" % name, not offending, offending[:3])
        size = len(text.encode("utf-8"))
        check("%s stays under 120 KB (%d bytes)" % (name, size), size < 120 * 1024)
    art, vis = code_only(read("IconArt.lua")), code_only(read("IconVisuals.lua"))
    check("IconArt.lua is pure data: no Instance.new, GetService, require or game", not any(w in art for w in ("Instance.new", "GetService", "require(", "game", "workspace")))
    check("IconVisuals.lua asks for no service and requires nothing (art and creature modules are passed in)", "GetService" not in vis and "require(" not in vis)
    check("IconVisuals.lua starts an animation in one place only (tap)", vis.count("task.spawn(") == 1 and "task.delay" not in vis)
    return passed, failed


def review_checks():
    """Optional (--review), for reviewing this branch before it is merged: against the merge-base with origin/main (or
    main), no existing file is edited but CONTRIBUTING.md, and tools/daily_test.py is untouched. Not part of the
    permanent run: once the branch is merged, the merge-base is main itself."""
    passed, failed = 0, 0

    def check(name, cond, extra=None):
        nonlocal passed, failed
        if cond:
            passed += 1
        else:
            failed += 1
            print("FAIL: " + name + (" -- " + str(extra) if extra else ""))

    def git(*args):
        return subprocess.run(["git"] + list(args), cwd=ROOT, capture_output=True, text=True)

    base = None
    for ref in ("origin/main", "main"):
        got = git("merge-base", ref, "HEAD")
        if got.returncode == 0:
            base = got.stdout.strip()
            break
    if base is None:
        print("note: no merge-base with origin/main or main, so the review checks are skipped")
        return passed, failed
    changed = git("diff", "--name-only", "--diff-filter=MDRT", base, "--").stdout.split()
    check("review: against the merge-base %s, no existing file is edited but CONTRIBUTING.md" % base[:7],
          [n for n in changed if n != "CONTRIBUTING.md"] == [], changed)
    check("review: tools/daily_test.py (other branches own it) is untouched", git("diff", "--quiet", base, "--", "tools/daily_test.py").returncode == 0)
    return passed, failed


def apply_mutation(text, old, new, what):
    if text.count(old) < 1:
        raise SystemExit("mutation target not found in %s: %r" % (what, old))
    return text.replace(old, new, 1)


V = "IconVisuals.lua"
A = "IconArt.lua"
# Group A: IconVisuals.lua. The builder breaks the style sheet or a rule (the icons' named check must fail), or a check
# or a pure function is weakened (the test that proves it must fail).
MUTANTS_A = [
    ("outlines drawn in each shape's own color", V, 'local color = outlineCopy and colorOf(art, "outline") or colorOf(art, shape.color)',
     "local color = colorOf(art, shape.color)", "icons at 56 px: check style"),
    ("gradients lit from the bottom-right", V, 'Name = "Shade", Rotation = art.Style.lightRotation,', 'Name = "Shade", Rotation = art.Style.lightRotation + 180,',
     "icons at 56 px: check style"),
    ("the 3D light fixed in the world instead of the picture", V, "view.LightDirection = camera.CFrame:VectorToWorldSpace(Vector3.new(d[1], d[2], d[3]).Unit)",
     "view.LightDirection = Vector3.new(d[1], d[2], d[3]).Unit", "icons at 56 px: check style"),
    ("the framing forgets the padding and the lens (models stick out)", V, "local t = math.tan(math.rad(fov) / 2) * (1 - padding)",
     "local t = math.tan(math.rad(fov) / 2) * 1.6", "icons at 56 px: check framing"),
    ("the camera at half the distance it needs", V, "need = math.max(need, nearest + 0.1)", "need = math.max(need, nearest + 0.1) * 0.5",
     "icons at 56 px: check framing"),
    ("the plan ignores the cap", V, "if count < cap then", "if true then", "lazy: scrolling the whole list, never more than 8"),
    ("the plan drops icons still on screen", V, "if not wantedSet[key] then\n\t\t\ttable.insert(spare", "if true then\n\t\t\ttable.insert(spare",
     "plan: when every live icon is on screen, the new one waits"),
    ("drawn icons rebuilt every time they are shown", V, "if not entry then\n\t\t\t\tentry = { what = what, icon",
     "if true then\n\t\t\t\tentry = { what = what, icon", "lazy: drawn icons that left the screen are reused"),
    ("card icons built without their plate", V, "\tif recipe.plate then\n\t\tdrawPlate(root, art, recipe.plate, size)\n\tend\n", "",
     "icons at 56 px: check style"),
    ("the spin ends a little turned", V, "\t\t\tmodel:PivotTo(start)\n", "\t\t\tmodel:PivotTo(start * CFrame.Angles(0, 1, 0))\n",
     "tap: after the spin the model is back exactly where it was"),
    ("every icon starts moving when it is built", V, "\troot.Parent = parent\n\treturn root\nend", "\ttask.spawn(function() end)\n\troot.Parent = parent\n\treturn root\nend",
     "icons: building all 76 made no animation start"),
    ("the assets check lets images through", V, "\tImageLabel = true, ImageButton = true,", "\tImageLabel = false, ImageButton = true,",
     "negative assets: an image in an icon is caught"),
    ("the texts check lets any word through", V, "elseif not allowed[d.Text] then", "elseif false then", "negative texts: a word"),
    ("the grid box forgets the outline", V, "\tif shape.outline then\n\t\tgrow = art.Style.outline\n\tend\n", "", "shapeBox: an outlined rect"),
    ("diamonds left square", V, 'Rotation = (shape.kind == "diamond" and 45 or 0) + (shape.rotation or 0),', "Rotation = shape.rotation or 0,",
     "icons: a diamond is a square turned 45 degrees"),
    ("the budget check never counts parts", V, "if parts > style.maxParts then", "if false then", "negative budget: 37 parts"),
    ("the coverage check never misses an icon", V, 'problem(group .. " " .. tostring(key) .. " has no icon")', "",
     "negative coverage: a shop item without a recipe"),
]
# Group B: IconArt.lua. The data breaks the style sheet or a rule, or stops matching the game (the named check must fail).
MUTANTS_B = [
    ("a shape color the palette doesn't have", A, 'S("circle", "Coin", 16, 16, 68, 68, "gold",', 'S("circle", "Coin", 16, 16, 68, 68, "goldd",',
     "icons at 56 px: check palette"),
    ("an emoji on the coin", A, '{ text = "2x" }', '{ text = "\\u{1F4B0}" }', "icons at 56 px: check texts"),
    ("a percent on the coin", A, '{ text = "2x" }', '{ text = "50%" }', "icons at 56 px: check texts"),
    ("a label on the clover", A, 'S("circle", "Heart", 42, 40, 16, 16, "cloverDark"),',
     'S("circle", "Heart", 42, 40, 16, 16, "cloverDark"),\n\t\tS("text", "Tag", 30, 30, 40, 40, "white", { text = "2x" }),',
     "icons at 56 px: check texts"),
    ("a target that reaches out of the grid", A, 'S("circle", "RingOuter", 14, 14, 72, 72,', 'S("circle", "RingOuter", 2, 2, 96, 96,', "icons at 56 px: check grid"),
    ("the desk copy drifting from PlotArt", A, 'P("DeskTop", "Block", { 6.2, 0.3, 3 }', 'P("DeskTop", "Block", { 6.4, 0.3, 3 }', "props: the Desk icon is PlotArt's"),
    ("a laptop with a part PlotArt doesn't have", A, 'P("PlantLeaves", "Ball", { 0.8, 0.8, 0.8 }, { -1.3, 3.5, -0.5 }, "leaf", "Fabric"),',
     'P("PlantLeaves", "Ball", { 0.8, 0.8, 0.8 }, { -1.3, 3.5, -0.5 }, "leaf", "Fabric"),\n\t\tP("ExtraLeaf", "Ball", { 0.5, 0.5, 0.5 }, { -1.1, 3.9, -0.5 }, "leaf", "Fabric"),',
     "props: the Laptop icon is PlotArt's"),
    ("the cap raised to 30 ViewportFrames", A, "viewportCap = 8,", "viewportCap = 30,", "data: at most 8 3D icons"),
    ("a plate under a HUD icon", A, 'Eggs = { name = "HudEgg", kind = "ui", shapes', 'Eggs = { name = "HudEgg", kind = "ui", plate = "plateCream", shapes',
     "icons at 56 px: check style"),
    ("a common creature on the epic plate", A, 'CodingCat = creature("CodingCat", "Common"),', 'CodingCat = creature("CodingCat", "Epic"),',
     "icons at 56 px: check coverage"),
    ("the light from the bottom-right", A, "lightRotation = 45,", "lightRotation = 225,", "data: one light direction for every icon"),
    ("the Startup egg in another blue than CreatureConfig's", A, "eggStartup = { 60, 150, 255 }", "eggStartup = { 60, 150, 200 }",
     "coverage: the Startup egg icon has CreatureConfig's egg color"),
    ("a shop item's recipe under the wrong key", A, 'PoachShield = { name = "Shield",', 'PoachShieldOld = { name = "Shield",', "icons at 56 px: check coverage"),
    ("the props seen from straight above", A, "local PROP_VIEW = { yaw = -28, pitch = 22 }", "local PROP_VIEW = { yaw = -28, pitch = 75 }",
     "icons at 56 px: check data"),
    ("a squashed circle", A, 'S("circle", "Bullseye", 43, 43, 14, 14, "white"),', 'S("circle", "Bullseye", 43, 43, 14, 10, "white"),',
     "icons at 56 px: check data"),
    ("no outline color in the palette", A, "outline = { 28, 30, 38 }, shine", "outlines = { 28, 30, 38 }, shine", "icons at 56 px: check palette"),
    ("a creature CreatureConfig doesn't have", A, 'VentureDragon = creature("VentureDragon", "Legendary"),',
     'VentureDragon = { name = "VentureDragon", kind = "creature", creature = "VentureDragonX", plate = "plateLegendary", view = CREATURE_VIEW },',
     "icons at 56 px: check style"),
]


def run_mutants(luau, mutants, group):
    from concurrent.futures import ThreadPoolExecutor
    art, vis = read("IconArt.lua"), read("IconVisuals.lua")

    def one(mutant):
        label, filename, old, new, expected = mutant
        if filename == "IconArt.lua":
            source = icon_source(art=apply_mutation(art, old, new, filename))
        else:
            source = icon_source(visuals=apply_mutation(vis, old, new, filename))
        result = run_luau(luau, source)
        finished = re.search(r"^\d+ passed, \d+ failed$", result.stdout, re.M) is not None
        named = any(line.startswith("FAIL: " + expected) for line in result.stdout.split("\n"))
        if finished and named:
            return None
        if not finished:
            why = "it crashed: " + (result.stderr.strip().split("\n")[0] if result.stderr.strip() else "no summary")
        else:
            why = "the check '%s' did not fail" % expected
        return "FAIL: mutation %s, %s: not caught by its named check (%s)" % (group, label, why)

    with ThreadPoolExecutor(max_workers=4) as pool:
        outcomes = list(pool.map(one, mutants))
    problems = [o for o in outcomes if o]
    return len(mutants) - len(problems), problems


def main():
    luau = os.environ.get("LUAU") or shutil.which("luau")
    if not luau:
        print("Luau not found. Download it from https://github.com/luau-lang/luau/releases and set LUAU=/path/to/luau")
        return 2
    code, total = 0, 0
    result = run_luau(luau, icon_source())
    print("Icon data, coverage, builders, framing, the cap, taps and broken icons: " + (result.stdout.strip() or result.stderr.strip()))
    m = re.search(r"^(\d+) passed, (\d+) failed$", result.stdout, re.M)
    if not m or m.group(2) != "0" or result.returncode != 0:
        code = 1
    total += int(m.group(1)) if m else 0
    if os.path.exists(os.path.join(ROOT, "docs", "STUDIO_SYNC_WORLD.md")) and "## The icon preview (command bar)" in read("docs/STUDIO_SYNC_WORLD.md"):
        result = run_luau(luau, preview_source())
        print("Icon preview block (docs/STUDIO_SYNC_WORLD.md) in a fake place: " + (result.stdout.strip() or result.stderr.strip()))
        m = re.search(r"^(\d+) passed, (\d+) failed$", result.stdout, re.M)
        if not m or m.group(2) != "0":
            code = 1
        total += int(m.group(1)) if m else 0
    static_passed, static_failed = static_checks()
    print("Icon source checks: %d passed, %d failed" % (static_passed, static_failed))
    total += static_passed
    if static_failed:
        code = 1
    if "--review" in sys.argv:
        review_passed, review_failed = review_checks()
        print("Review checks (--review, against the merge-base with main): %d passed, %d failed" % (review_passed, review_failed))
        total += review_passed
        if review_failed:
            code = 1
    runs = caught = 0
    for group, mutants in (("A", MUTANTS_A), ("B", MUTANTS_B)):
        got, problems = run_mutants(luau, mutants, group)
        for line in problems:
            print(line)
        if problems:
            code = 1
        runs += len(mutants)
        caught += got
        if mutants:
            print("Icon mutations, group %s: %d of %d caught, each by its named check" % (group, got, len(mutants)))
    print("icon_test.py: %d checks passed, %d of %d mutation runs caught%s" % (total, caught, runs, "" if code == 0 else "  -- SOMETHING FAILED"))
    return code


if __name__ == "__main__":
    sys.exit(main())
