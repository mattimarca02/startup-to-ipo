#!/usr/bin/env python3
"""Tests for the world pass (WorldArt.lua and WorldVisuals.lua), outside Studio.

Run:   python3 tools/world_test.py

It needs the free Luau command-line tool (https://github.com/luau-lang/luau/releases, the "luau" file from
luau-macos.zip, luau-windows.zip or luau-ubuntu.zip). Put it on your PATH, or point to it:
       LUAU=/path/to/luau python3 tools/world_test.py

It runs the real WorldArt and WorldVisuals with its own fake Roblox (real vector and rotation maths, Instances with
classes, parents and properties, a Workspace holding the Baseplate and the SpawnLocation as the owner measured them),
and the real VIP Lounge builder (ShopServer.lua), plotCenter and makePart (TycoonCore.lua) and the five plot rooms
(PlotArt.lua, PlotVisuals.lua), so the world is checked against the real objects. It checks the part and light
budgets, that no decor collides, that nothing enters a plot, a sign, the lounge or the spawn pad, that nothing floats
or flickers, that the paths join the spawn to every plot's front, that the plots, the lounge and the spawn are left
exactly where they were, that every palette color exists, the same for a sweep of PLOT_SPACING 90 and 112 with 1 to
6 plots, and the Studio preview block. Then it breaks the data and the builder on purpose (mutation runs): each
must be caught by a named check, never by a crash.

It changes nothing in the game or in Studio. It never edits tools/daily_test.py (other branches own it).
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = "e3c9e67"  # main when world-icons-pass was made: no existing file may differ from it but CONTRIBUTING.md
NEW_LUA = ("WorldArt.lua", "WorldVisuals.lua")


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
    """Lua source without comments (a line's -- tail is cut, like tools/daily_test.py does)."""
    out = []
    for line in text.split("\n"):
        cut = line.find("--")
        out.append(line if cut < 0 else line[:cut])
    return "\n".join(out)


def lua_strings(text):
    """Every string literal of a Lua source ("...", '...' and [[...]]), comments left out."""
    code = code_only(text)
    found = re.findall(r'"((?:[^"\\\n]|\\.)*)"', code) + re.findall(r"'((?:[^'\\\n]|\\.)*)'", code)
    found += re.findall(r"\[\[(.*?)\]\]", code, re.S)
    return found


def extract_function(text, header):
    """The source of a top-level `local function` from its header line to its closing `end` at column 0."""
    start = text.index(header)
    end = text.index("\nend\n", start)
    return text[start:end + len("\nend\n")]


PRELUDE = r"""-- Fake Roblox for the world pass: vector and rotation maths like Roblox's, Instances with classes, parents,
-- attributes and properties, a Workspace with the Baseplate and the SpawnLocation, a few services.
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
local task = { spawn = function() end, wait = function() end, delay = function() end }

-- Vector3 (compared by value, like Roblox)
local V = {}
V.__index = V
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

-- CFrame: a position and a row-major rotation matrix, composed like Roblox's
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
CF.__eq = function(a, b)
	if a.x ~= b.x or a.y ~= b.y or a.z ~= b.z then return false end
	for i = 1, 9 do if a.r[i] ~= b.r[i] then return false end end
	return true
end
function CF.GetComponents(t) local r = t.r return t.x, t.y, t.z, r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8], r[9] end
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

-- Signals
local function newSignal()
	local s = { handlers = {} }
	function s.Connect(self, fn)
		local c = { fn = fn, connected = true }
		function c.Disconnect(self2) self2.connected = false end
		table.insert(self.handlers, c)
		return c
	end
	return s
end

-- Instances: classes, parents, children, attributes, properties. A Part keeps its Position inside its CFrame.
local IS_A = {
	Part = { BasePart = true, PVInstance = true }, SpawnLocation = { Part = true, BasePart = true, PVInstance = true },
	Seat = { Part = true, BasePart = true, PVInstance = true }, WedgePart = { BasePart = true, PVInstance = true },
	PointLight = { Light = true }, SpotLight = { Light = true }, SurfaceLight = { Light = true },
	Model = { PVInstance = true }, Workspace = { Model = true, PVInstance = true },
	Script = { BaseScript = true, LuaSourceContainer = true }, LocalScript = { Script = true, BaseScript = true, LuaSourceContainer = true },
	ModuleScript = { LuaSourceContainer = true }, SurfaceGui = { LayerCollector = true, GuiBase = true },
	TextLabel = { GuiObject = true, GuiBase2d = true }, Decal = { FaceInstance = true },
}
local PART_CLASSES = { Part = true, SpawnLocation = true, Seat = true, WedgePart = true }
local Methods = {}
local Mt = {}
Mt.__index = function(t, k)
	if k == "Parent" then return rawget(t, "_parent") end
	local props = rawget(t, "_props")
	if props then
		if k == "Position" and props.CFrame then return props.CFrame.Position end
		if props[k] ~= nil then return props[k] end
	end
	if k == "Touched" then
		local s = rawget(t, "_touched")
		if not s then s = newSignal(); rawset(t, "_touched", s) end
		return s
	end
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
	if props then
		if k == "Position" then
			local old = props.CFrame
			props.CFrame = cf(v.X, v.Y, v.Z, old and old.r or nil)
			return
		end
		if k == "Shape" and v.Name == "Ball" then
			local s = props.Size
			local m = math.min(s.X, s.Y, s.Z)
			props.Size = vec(m, m, m)
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
			Shape = Enum.PartType.Block, CollisionGroup = "Default",
		})
	elseif class == "Model" then
		rawset(i, "_props", { ModelStreamingMode = Enum.ModelStreamingMode.Default })
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
function Methods.IsA(t, class) return t.ClassName == class or (IS_A[t.ClassName] ~= nil and IS_A[t.ClassName][class] == true) end
function Methods.FindFirstChildWhichIsA(t, class, recursive)
	for _, c in ipairs(recursive and t:GetDescendants() or t._children) do if c:IsA(class) then return c end end
	return nil
end
function Methods.SetAttribute(t, k, v) t._attrs[k] = v end
function Methods.GetAttribute(t, k) return t._attrs[k] end
function Methods.Destroy(t) t.Parent = nil; rawset(t, "destroyed", true) end
function Methods.GetFullName(t) local p = t.Parent return (p and p.ClassName ~= "DataModel" and (p:GetFullName() .. ".") or "") .. t.Name end

-- The place: a Workspace with the Baseplate and the SpawnLocation where the owner measured them (Studio facts)
local game = newInstance("DataModel")
local workspace = newInstance("Workspace")
workspace.Name = "Workspace"
workspace.Parent = game
local baseplate = newInstance("Part")
baseplate.Name = "Baseplate"
baseplate.Size = vec(2048, 16, 2048)
baseplate.Position = vec(0, -8, 0)
baseplate.Anchored = true
baseplate.Color = Color3.fromRGB(108, 172, 82)
baseplate.Parent = workspace
local spawnPad = newInstance("SpawnLocation")
spawnPad.Name = "SpawnLocation"
spawnPad.Size = vec(12, 1, 12)
spawnPad.Position = vec(-1, 0.5, -1)
spawnPad.Anchored = true
spawnPad.Parent = workspace
local SERVICES = {}
for _, name in ipairs({ "ServerScriptService", "ReplicatedStorage", "StarterGui", "Players", "Lighting" }) do
	local s = newInstance(name)
	s.Name = name
	s.Parent = game
	SERVICES[name] = s
end
SERVICES.Workspace = workspace
function Methods.GetService(t, name)
	local s = SERVICES[name]
	if not s then error("no service " .. tostring(name)) end
	return s
end
local MODULES = {}
function Methods.WaitForChild(t, name) return t:FindFirstChild(name) end
function Methods.IsDescendantOf(t, ancestor)
	local p = t.Parent
	while p do
		if p == ancestor then return true end
		p = p.Parent
	end
	return false
end
function Methods.Clone(t)
	local c = newInstance(t.ClassName)
	c.Name = t.Name
	local from, to = rawget(t, "_props"), rawget(c, "_props")
	if from and to then for k, v in pairs(from) do to[k] = v end end
	for k, v in pairs(t._attrs) do c._attrs[k] = v end
	if MODULES[t] ~= nil then MODULES[c] = MODULES[t] end
	for _, child in ipairs(t._children) do child:Clone().Parent = c end
	return c
end
local function require(module)
	local m = MODULES[module]
	if m == nil then error("require of an unknown module " .. tostring(module and module.Name)) end
	return m
end
"""


TESTS = r"""-- Tests: the real WorldArt and WorldVisuals, the real lounge builder, plotCenter and makePart, and the real rooms ------
local WorldArt = (function()
__WORLDART__
end)()
local WorldVisuals = (function()
__WORLDVISUALS__
end)()
local PlotArt = (function()
__PLOTART__
end)()
local PlotVisuals = (function()
__PLOTVISUALS__
end)()
local REAL = __REAL__

-- Every part below runs inside section(): if broken code makes one error, that becomes a named FAIL and the
-- rest still runs (a mutation must be caught by a named check, never by a crash)
local function section(name, fn)
	local ok, err = pcall(fn)
	if not ok then check(name .. ": this part of the tests could not finish", false, err) end
end
local S, site, world, PARTS, LIGHTS, SWEEP, ROOMS, roomBoxes = WorldArt.Site, nil, nil, 0, 0, {}, {}, nil

local function deepCopy(t)
	if type(t) ~= "table" then return t end
	local c = {}
	for k, v in pairs(t) do c[deepCopy(k)] = deepCopy(v) end
	return setmetatable(c, getmetatable(t))
end
local function anyMatch(list, word) for _, p in ipairs(list) do if string.find(p, word, 1, true) then return true end end return false end
local function results(world, art, site, options)
	local byName = {}
	for _, r in ipairs(WorldVisuals.checks(world, art or WorldArt, site, options)) do byName[r.name] = r.problems end
	return byName
end
local function failsWith(world, site, name, word, options, art)
	local r = results(world, art, site, options)[name]
	return r ~= nil and anyMatch(r, word), r and r[1]
end
local function partsOf(model)
	local out = {}
	for _, d in ipairs(model:GetDescendants()) do if d:IsA("BasePart") then table.insert(out, d) end end
	return out
end
local function count(model, class)
	local n = 0
	for _, d in ipairs(model:GetDescendants()) do if d.ClassName == class then n += 1 end end
	return n
end

-- The real code of the game, run in the fake: TycoonCore's plotCenter and makePart, ShopServer's lounge
local function realPlotCenter(PLOT_SPACING, MAX_PLOTS)
__PLOTCENTER__
	return plotCenter
end
local tycoonMakePart = (function()
__TYCOON_MAKEPART__
	return makePart
end)()
local buildRealLounge = (function()
__LOUNGE_CONSTANTS__
__SHOP_MAKEPART__
__BUILDVIPLOUNGE__
	return buildVipLounge
end)()

-- 1. The data -------------------------------------------------------------------------------------------------------
section("data", function()
	local problems = WorldVisuals.validate(WorldArt)
	check("data: WorldVisuals.validate finds no problem in WorldArt", #problems == 0, problems[1])
	check("data: every named check exists, in order", table.concat(WorldVisuals.CHECKS, ",") == "data,budget,flags,keepouts,floating,zfighting,baseplate,connected,palette,texts")
	check("data: the budget is 600 parts and 8 lights (placeholders)", WorldArt.Budget.parts == 600 and WorldArt.Budget.lights == 8)
	check("data: the only fixed text is BUILD YOUR STARTUP", #WorldArt.Texts == 1 and WorldArt.Texts[1] == "BUILD YOUR STARTUP")
	check("data: layers are ground 0.04, path 0.16, kerb 0.4 (at least 0.04 apart, and never the stage 1 dirt's 0.06)",
		WorldArt.Layout.groundTop == 0.04 and WorldArt.Layout.pathTop == 0.16 and WorldArt.Layout.kerbHeight == 0.4)
end)

-- 2. The numbers copied from the scripts and the Studio facts ------------------------------------------------------------
section("copied numbers and Studio facts", function()
	check("copied: PLOT_SPACING (TycoonCore) is " .. REAL.spacing, S.plotSpacing == REAL.spacing, S.plotSpacing)
	check("copied: MAX_PLOTS (TycoonCore) is " .. REAL.count, S.plotCount == REAL.count, S.plotCount)
	check("copied: plotY and plotZ (TycoonCore plotCenter)", S.plotY == REAL.plotY and S.plotZ == REAL.plotZ, S.plotY .. " " .. S.plotZ)
	check("copied: the Floor is " .. table.concat(REAL.floor, " x ") .. " (TycoonCore)", S.floorSize[1] == REAL.floor[1] and S.floorSize[2] == REAL.floor[2] and S.floorSize[3] == REAL.floor[3])
	check("copied: the next-upgrade sign offset (TycoonCore SIGN_OFFSET)", S.signs[1].name == "BuySign" and S.signs[1].x == REAL.buySign[1] and S.signs[1].z == REAL.buySign[2])
	check("copied: the IPO sign offset (IpoServer SIGN_OFFSET)", S.signs[2].name == "IpoSign" and S.signs[2].x == REAL.ipoSign[1] and S.signs[2].z == REAL.ipoSign[2])
	check("copied: the signs' board and post (both scripts)", S.signBoard[1] == REAL.board[1] and S.signBoard[2] == REAL.board[2] and S.signBoard[3] == REAL.board[3]
		and S.signPostHeight == REAL.postHeight and S.signBoardY == REAL.boardY)
	local lounge = S.lounge
	check("copied: lounge center, size, wall height and door (ShopServer)", lounge.center[1] == REAL.lounge.center[1] and lounge.center[2] == REAL.lounge.center[2]
		and lounge.center[3] == REAL.lounge.center[3] and lounge.size[1] == REAL.lounge.size[1] and lounge.size[2] == REAL.lounge.size[2]
		and lounge.size[3] == REAL.lounge.size[3] and lounge.wallHeight == REAL.lounge.wall and lounge.doorWidth == REAL.lounge.door)
	check("copied: lounge sign height and the drop spot past the front wall (ShopServer)", lounge.signHeight == REAL.lounge.signHeight and lounge.dropOut == REAL.lounge.dropOut)
	check("copied: the front is +Z (teleportToPlot lands at +12 and looks at +24)", REAL.landing[3] < REAL.lookAt[3] and REAL.landing[1] == 0 and REAL.lookAt[1] == 0)
	check("Studio facts: the Baseplate is 2048 x 16 x 2048 at (0, -8, 0)", S.baseplate.size[1] == 2048 and S.baseplate.size[2] == 16 and S.baseplate.size[3] == 2048
		and S.baseplate.position[1] == 0 and S.baseplate.position[2] == -8 and S.baseplate.position[3] == 0)
	check("Studio facts: the SpawnLocation is 12 x 1 x 12 at (-1, 0.5, -1)", S.spawn.size[1] == 12 and S.spawn.size[2] == 1 and S.spawn.size[3] == 12
		and S.spawn.position[1] == -1 and S.spawn.position[2] == 0.5 and S.spawn.position[3] == -1)
	site = WorldVisuals.site(WorldArt)
	local facts = WorldVisuals.studioFacts(site, spawnPad, baseplate)
	check("Studio facts: they match the SpawnLocation and the Baseplate in the fake place", #facts == 0, facts[1])
	do
		local moved = newInstance("SpawnLocation")
		moved.Size = vec(12, 1, 12)
		moved.Position = vec(-1, 0.5, 4)
		check("Studio facts: a SpawnLocation 5 studs off is reported", anyMatch(WorldVisuals.studioFacts(site, moved, baseplate), "SpawnLocation is at"))
		check("Studio facts: a missing Baseplate is reported", anyMatch(WorldVisuals.studioFacts(site, spawnPad, nil), "no Baseplate"))
	end
end)

-- 3. The pure functions ------------------------------------------------------------------------------------------------
section("pure functions", function()
	check("site: six plots 90 apart at x -225 ... 225, y 0.5, z 150 (TycoonCore's formula)", #site.plots == 6 and site.plots[1].x == -225 and site.plots[6].x == 225
		and site.plots[3].x == -45 and site.plots[1].z == 150 and site.plots[1].y == 0.5)
	do
		local real = realPlotCenter(REAL.spacing, REAL.count)
		local fromCore = WorldVisuals.site(WorldArt, REAL.spacing, REAL.count, real)
		local same = true
		for i, p in ipairs(fromCore.plots) do
			local q = site.plots[i]
			if p.x ~= q.x or p.y ~= q.y or p.z ~= q.z then same = false end
		end
		check("site: the real plotCenter and the copied formula give the same six centers", same and #fromCore.plots == 6)
		for _, sweep in ipairs({ { 112, 6 }, { 90, 1 }, { 112, 3 } }) do
			local a = WorldVisuals.site(WorldArt, sweep[1], sweep[2], realPlotCenter(sweep[1], sweep[2]))
			local b = WorldVisuals.site(WorldArt, sweep[1], sweep[2])
			local ok = #a.plots == sweep[2]
			for i = 1, #a.plots do if a.plots[i].x ~= b.plots[i].x then ok = false end end
			check("site: the real plotCenter and the formula agree at spacing " .. sweep[1] .. " with " .. sweep[2] .. " plots", ok)
		end
	end
	check("site: the lounge as ShopServer builds it (walls x -18.5..18.5, z 57.5..82.5, sign to y 14.5, drop spot (0, 88))",
		site.lounge.halfX == 18.5 and site.lounge.back == 57.5 and site.lounge.front == 82.5 and site.lounge.top == 14.5
		and site.lounge.drop.x == 0 and site.lounge.drop.z == 88)
	check("site: the spawn pad from the Studio fact (x -7..5, z -7..5, top 1)", site.spawn.x == -1 and site.spawn.z == -1 and site.spawn.halfX == 6 and site.spawn.top == 1)
	check("site: the Baseplate's top is y 0 and it spans -1024..1024", site.ground.top == 0 and site.ground.x0 == -1024 and site.ground.x1 == 1024 and site.ground.z1 == 1024)
	check("site: the Studio preview rooms count at the default site", site.preview ~= nil and site.preview[1] == -636 and site.preview[2] == -284)
	do
		local wide = WorldVisuals.site(WorldArt, 112, 6)
		check("site: at spacing 112 the preview rooms (placed for spacing 90) don't count: the preview snippet must move", wide.preview == nil)
		local fewer = WorldVisuals.site(WorldArt, 90, 4)
		check("site: at spacing 90 with fewer plots the preview rooms still count", fewer.preview ~= nil)
	end
	do
		local g = WorldVisuals.gapLines(site)
		check("gap lines: halfway between plots and half a spacing past each end (-270 ... 270)", g[0] == -270 and g[1] == -180 and g[3] == 0 and g[6] == 270)
		local one = WorldVisuals.gapLines(WorldVisuals.site(WorldArt, 90, 1))
		check("gap lines: one plot has a line on each side", one[0] == -45 and one[1] == 45)
	end
	do
		local b = WorldVisuals.aboveGround("Ball", { -10, 10, -16, 4, -10, 10 })
		check("aboveGround: a sunk ball shows only its cap (radius 8 at y 0 for a radius 10 ball centered 6 down)",
			math.abs(b[1] + 8) < 1e-9 and math.abs(b[2] - 8) < 1e-9 and b[3] == 0 and b[4] == 4)
		local c = WorldVisuals.aboveGround("Block", { 0, 1, -2, 3, 0, 1 })
		check("aboveGround: a block is cut at y 0", c[3] == 0 and c[4] == 3 and c[1] == 0)
	end
	do
		local a, b = WorldVisuals.layout(WorldArt, site), WorldVisuals.layout(WorldArt, site)
		local same = #a.paths == #b.paths and #a.items == #b.items
		for i = 1, #a.items do
			if a.items[i].name ~= b.items[i].name or a.items[i].x ~= b.items[i].x or a.items[i].z ~= b.items[i].z then same = false end
		end
		check("layout: the same site always gives the same world (nothing random)", same)
		local names = {}
		local unique = true
		for _, list in ipairs({ a.paths, a.kerbs, a.ground, a.items, a.hills }) do
			for _, r in ipairs(list) do
				if names[r.name] then unique = false end
				names[r.name] = true
			end
		end
		check("layout: every path, kerb, lawn, item and hill has its own name", unique)
		check("layout: one walk, one sign and one street piece of each street per plot", names.Walk6 and names.StreetSign6 and names.FrontStreet6 and names.BackStreet6
			and not names.Walk7 and not names.StreetSign7)
		check("layout: connectors through every gap at the default site (7)", names.Connector0 and names.Connector3 and names.Connector6)
		local lit = 0
		for _, it in ipairs(a.items) do if it.lit then lit += 1 end end
		check("layout: only the plaza's four lamps and the forecourt's two are lit", lit == 6)
		check("layout: the front street starts 1 stud past what the plots reach (z 191) and the back street ends 5 short of it (z 95)",
			a.frontZ0 == 191 and a.backZ1 == 95)
	end
end)

-- 4. What the rooms reach: every part of all five rooms (props included) stays inside Site.plotReach -------------------
section("rooms", function()
	do
		local center = Vector3.new(0, 0.5, 150)
		local reach = { side = 0, back = 0, front = 0, top = 0 }
		for stage = 1, #PlotArt.Stages do
			local room = PlotVisuals.buildRoom(nil, center, PlotArt, stage)
			for _, slot in ipairs(PlotArt.Layout.itemSlots) do
				PlotVisuals.buildProp(room:FindFirstChild("UpgradeProps"), center, PlotArt, slot.name, Vector3.new(slot.x, 0, slot.z))
			end
			ROOMS[stage] = room
			for _, p in ipairs(partsOf(room)) do
				local b = PlotVisuals.boxOf(p.CFrame, p.Size)
				reach.side = math.max(reach.side, math.abs(b[1] - center.X), math.abs(b[2] - center.X))
				reach.back = math.max(reach.back, center.Z - b[5])
				reach.front = math.max(reach.front, b[6] - center.Z)
				reach.top = math.max(reach.top, b[4])
			end
		end
		local R = S.plotReach
		check(string.format("rooms: every room fits in Site.plotReach (they reach %.1f to the sides, %.1f behind, %.1f in front, %.1f up)", reach.side, reach.back, reach.front, reach.top),
			reach.side <= R.side and reach.back <= R.back and reach.front <= R.front and reach.top <= R.top)
		check("rooms: the reach is the measured one plus a little (no stud wasted: within 1 to the sides and 1 behind)", R.side - reach.side <= 1 and R.back - reach.back <= 1)
	end
	-- The parts of the rooms at every plot of a site (stage 1 has the yard dirt, stage 5 the skyline), as world boxes
	roomBoxes = function(s)
		local out = {}
		for i, p in ipairs(s.plots) do
			for _, stage in ipairs({ 1, 5 }) do
				local room = PlotVisuals.buildRoom(nil, Vector3.new(p.x, p.y, p.z), PlotArt, stage)
				for _, part in ipairs(partsOf(room)) do
					table.insert(out, { name = "Plot" .. i .. ".Stage" .. stage .. "." .. part.Name, box = PlotVisuals.boxOf(part.CFrame, part.Size) })
				end
			end
		end
		return out
	end
end)

-- 5. The default world --------------------------------------------------------------------------------------------------
section("default site", function()
	world = WorldVisuals.build(nil, WorldArt, site)
	PARTS = #partsOf(world)
	LIGHTS = count(world, "PointLight")
	local byName = results(world, WorldArt, site, { roomBoxes = roomBoxes(site) })
	for _, name in ipairs(WorldVisuals.CHECKS) do
		check("default site: check " .. name .. " passes (rooms of stages 1 and 5 at every plot included)", byName[name] ~= nil and #byName[name] == 0, byName[name] and byName[name][1])
	end
	check("default site: " .. PARTS .. " parts, within 600", PARTS <= 600 and PARTS > 100, PARTS)
	check("default site: " .. LIGHTS .. " lights, within 8", LIGHTS <= 8 and LIGHTS == 6, LIGHTS)
	check("default site: the World Model holds Paths, Kerbs, Ground, Decor and Hills", world.Name == "World" and world:FindFirstChild("Paths") and world:FindFirstChild("Kerbs")
		and world:FindFirstChild("Ground") and world:FindFirstChild("Decor") and world:FindFirstChild("Hills"))
	check("default site: knows its spacing and plot count", world:GetAttribute("Spacing") == 90 and world:GetAttribute("Plots") == 6)
	do
		local collide, touch, query, anchored, scripts = 0, 0, 0, 0, 0
		for _, p in ipairs(partsOf(world)) do
			if p.CanCollide then collide += 1 end
			if p.CanTouch then touch += 1 end
			if p.CanQuery then query += 1 end
			if not p.Anchored then anchored += 1 end
		end
		for _, d in ipairs(world:GetDescendants()) do if d:IsA("LuaSourceContainer") then scripts += 1 end end
		check("default site: no decor collides, is touched or stops a ray; every part is anchored; no script", collide + touch + query + anchored + scripts == 0)
		local atomic = 0
		for _, m in ipairs(world:FindFirstChild("Decor"):GetChildren()) do if m.ModelStreamingMode == Enum.ModelStreamingMode.Atomic then atomic += 1 end end
		check("default site: every decor item streams whole (ModelStreamingMode Atomic)", atomic == #world:FindFirstChild("Decor"):GetChildren() and atomic > 0)
		local lightsIn = true
		for _, d in ipairs(world:GetDescendants()) do
			if d.ClassName == "PointLight" and not (d.Parent.Name == "LampGlow" and (string.find(d.Parent.Parent.Name, "PlazaLamp", 1, true) or string.find(d.Parent.Parent.Name, "ForecourtLamp", 1, true))) then
				lightsIn = false
			end
		end
		check("default site: the lights are in the lanterns of the plaza and forecourt lamps only", lightsIn)
		local texts = {}
		for _, d in ipairs(world:GetDescendants()) do if d.ClassName == "TextLabel" then texts[d.Text] = (texts[d.Text] or 0) + 1 end end
		check("default site: the arch says BUILD YOUR STARTUP on both faces, each sign its number on both faces",
			texts["BUILD YOUR STARTUP"] == 2 and texts["1"] == 2 and texts["6"] == 2 and texts["7"] == nil)
		local signs = world:FindFirstChild("Decor"):FindFirstChild("StreetSign3")
		local sb = WorldVisuals.boxOf(signs:FindFirstChild("SignBoard").CFrame, signs:FindFirstChild("SignBoard").Size)
		check("default site: plot 3's sign stands across the street from it (x -45 + 7, past the street)", math.abs((sb[1] + sb[2]) / 2 - (-38)) < 1e-6 and sb[5] > 199)
	end
end)

-- 6. The real objects: the plots (real plotCenter and makePart), their signs, the lounge (ShopServer's own builder), the
-- SpawnLocation and the Baseplate stand in the Workspace. The world is built next to them and changes none of them.
section("real objects", function()
	do
		local real = realPlotCenter(REAL.spacing, REAL.count)
		local existing = { baseplate, spawnPad }
		for slot = 1, REAL.count do
			local folder = newInstance("Folder")
			folder.Name = "Player" .. slot .. "_Startup"
			folder.Parent = workspace
			local floor = tycoonMakePart(folder, "Floor", Vector3.new(REAL.floor[1], REAL.floor[2], REAL.floor[3]), real(slot), Color3.fromRGB(90, 90, 100))
			table.insert(existing, floor)
			for _, sign in ipairs({ { "BuySign", REAL.buySign }, { "IpoSign", REAL.ipoSign } }) do
				local pos = real(slot) + Vector3.new(sign[2][1], 0.5, sign[2][2])
				local post = tycoonMakePart(folder, sign[1], Vector3.new(0.4, REAL.postHeight, 0.4), pos + Vector3.new(0, REAL.postHeight / 2, 0), Color3.fromRGB(70, 74, 86))
				local board = tycoonMakePart(post, "Board", Vector3.new(REAL.board[1], REAL.board[2], REAL.board[3]), pos + Vector3.new(0, REAL.boardY, 0), Color3.fromRGB(0, 140, 70))
				table.insert(existing, post)
				table.insert(existing, board)
			end
		end
		buildRealLounge()
		local loungeFolder = workspace:FindFirstChild("VipLounge")
		check("real objects: ShopServer's own lounge builder ran in the fake (" .. (loungeFolder and #loungeFolder:GetChildren() or 0) .. " parts)", loungeFolder ~= nil and #loungeFolder:GetChildren() >= 10)
		for _, p in ipairs(loungeFolder and loungeFolder:GetChildren() or {}) do table.insert(existing, p) end
		-- The lounge the site describes is the lounge ShopServer builds: every lounge part inside the site's box
		local inside = true
		for _, p in ipairs(loungeFolder and loungeFolder:GetChildren() or {}) do
			local b = WorldVisuals.boxOf(p.CFrame, p.Size)
			local lg = site.lounge
			if b[1] < lg.x - lg.halfX - 1e-6 or b[2] > lg.x + lg.halfX + 1e-6 or b[5] < lg.back - 0.11 or b[6] > lg.front + 1e-6 or b[4] > lg.top + 1e-6 then inside = false end
		end
		check("real objects: every part ShopServer builds for the lounge is inside the site's lounge box", inside)
		local snap = WorldVisuals.snapshot(existing)
		local before = #workspace:GetChildren()
		local built = WorldVisuals.build(workspace, WorldArt, WorldVisuals.site(WorldArt, REAL.spacing, REAL.count, real))
		local changed = WorldVisuals.compare(snap)
		check("real objects: the plots, their signs, the lounge, the SpawnLocation and the Baseplate are exactly as before (" .. #snap .. " parts)", #changed == 0, changed[1])
		check("real objects: the build only added its own Model to the Workspace", #workspace:GetChildren() == before + 1 and built.Parent == workspace)
		local others = {}
		for _, p in ipairs(existing) do if p ~= baseplate then table.insert(others, p) end end
		local clashes = WorldVisuals.clashes(built, others)
		check("real objects: no world part goes into a real plot floor, sign, lounge part or the spawn pad", #clashes == 0, clashes[1])
		check("real objects: a world part pushed into the real lounge is reported as a clash", (function()
			local lamp = built:FindFirstChild("Decor"):FindFirstChild("ForecourtLampWest")
			local glow = lamp:FindFirstChild("LampGlow")
			local old = glow.CFrame
			glow.CFrame = CFrame.new(0, 0.5, 70) -- on the lounge's floor
			local found = anyMatch(WorldVisuals.clashes(built, others), "would go into")
			glow.CFrame = old
			return found
		end)())
		-- A builder that touched them would be seen
		baseplate.Size = vec(2048, 16, 2047)
		check("real objects: a resized Baseplate is noticed", anyMatch(WorldVisuals.compare(snap), "Baseplate was resized"))
		baseplate.Size = vec(2048, 16, 2048)
		spawnPad.Position = vec(-1, 0.5, 0)
		check("real objects: a moved SpawnLocation is noticed", anyMatch(WorldVisuals.compare(snap), "SpawnLocation was moved"))
		spawnPad.Position = vec(-1, 0.5, -1)
		local floor1 = existing[3]
		floor1.Parent = nil
		check("real objects: a deleted plot Floor is noticed", anyMatch(WorldVisuals.compare(snap), "Floor was moved to another parent or deleted"))
		floor1.Parent = workspace:FindFirstChild("Player1_Startup")
		check("real objects: everything put back is clean again", #WorldVisuals.compare(snap) == 0, WorldVisuals.compare(snap)[1])
		built:Destroy()
	end
end)

-- 7. The sweep: PLOT_SPACING 90 and 112, 1 to 6 plots, with the real plotCenter --------------------------------------------
section("sweep", function()
	for _, spacing in ipairs({ 90, 112 }) do
		for n = 1, 6 do
			local s = WorldVisuals.site(WorldArt, spacing, n, realPlotCenter(spacing, n))
			local w = WorldVisuals.build(nil, WorldArt, s)
			local r = results(w, WorldArt, s, { roomBoxes = roomBoxes(s) })
			local bad = nil
			for _, name in ipairs(WorldVisuals.CHECKS) do
				if #r[name] > 0 then bad = bad or (name .. ": " .. r[name][1]) end
			end
			local parts, lights = #partsOf(w), count(w, "PointLight")
			table.insert(SWEEP, string.format("spacing %d, %d plot%s: %d parts, %d lights", spacing, n, n == 1 and "" or "s", parts, lights))
			check(string.format("sweep: spacing %d with %d plot(s): every named check passes", spacing, n), bad == nil, bad)
			check(string.format("sweep: spacing %d with %d plot(s): %d parts and %d lights within the budget", spacing, n, parts, lights), parts <= 600 and lights <= 8)
			local walks = 0
			for _, p in ipairs(w:FindFirstChild("Paths"):GetChildren()) do if string.find(p.Name, "Walk", 1, true) == 1 then walks += 1 end end
			check(string.format("sweep: spacing %d with %d plot(s): one walk per plot", spacing, n), walks == n)
		end
	end
end)

-- 8. The checks catch a broken world (a check that can't fail proves nothing) ---------------------------------------------
section("negative tests", function()
	do
		local function fresh() return WorldVisuals.build(nil, WorldArt, site) end
		local function anyPart(w, name) return w:FindFirstChild(name, true) end
		local w = fresh()
		check("clean: a fresh default world passes every check", #WorldVisuals.check(w, WorldArt, site) == 0, WorldVisuals.check(w, WorldArt, site)[1])
		local p = anyPart(w, "Avenue")
		p.CanCollide = true
		check("negative flags: a collidable part is caught", failsWith(w, site, "flags", "CanCollide is on"))
		p.CanCollide = false
		p.CanQuery = true
		check("negative flags: a part that stops rays is caught", failsWith(w, site, "flags", "CanQuery is on"))
		p.CanQuery = false
		p.CanTouch = true
		check("negative flags: a touchable part is caught", failsWith(w, site, "flags", "CanTouch is on"))
		p.CanTouch = false
		p.Anchored = false
		check("negative flags: an unanchored part is caught", failsWith(w, site, "flags", "not anchored"))
		p.Anchored = true
		p.CastShadow = true
		check("negative flags: a flat path that casts a shadow is caught", failsWith(w, site, "flags", "casts a shadow"))
		p.CastShadow = false
		p.Material = Enum.Material.Neon
		check("negative flags: Neon on a path is caught", failsWith(w, site, "flags", "Neon on something"))
		p.Material = Enum.Material.SmoothPlastic
		local script = newInstance("Script")
		script.Parent = anyPart(w, "PlazaLamp1")
		check("negative flags: a script inside the world is caught", failsWith(w, site, "flags", "no scripts"))
		script.Parent = nil
		local decal = newInstance("Decal")
		decal.Parent = p
		check("negative flags: an image (Decal) is caught", failsWith(w, site, "flags", "(Decal)"))
		decal.Parent = nil
		local trunk = anyPart(w, "PlazaTree1"):FindFirstChild("Trunk")
		local trunkCf = trunk.CFrame
		trunk.CFrame = trunkCf * CFrame.Angles(0, 0, math.rad(10))
		check("negative flags: a part turned by 10 degrees is caught", failsWith(w, site, "flags", "quarter turns"))
		trunk.CFrame = trunkCf
		check("clean: put back, the flags check is clean again", #results(w, WorldArt, site).flags == 0)

		for i = 1, 3 do
			local light = newInstance("PointLight")
			light.Parent = anyPart(w, "StreetLamp" .. i):FindFirstChild("LampGlow")
		end
		check("negative budget: 9 lights are caught (budget 8)", failsWith(w, site, "budget", "lights (budget 8)"))
		local filler = newInstance("Model")
		filler.Parent = w
		for i = 1, 400 do
			local q = newInstance("Part")
			q.Size = vec(1, 1, 1)
			q.Position = vec(500 + (i % 20) * 2, 0.5, 500 + i)
			q.Anchored, q.CanCollide, q.CanTouch, q.CanQuery, q.CastShadow = true, false, false, false, false
			q.Parent = filler
		end
		check("negative budget: 668 parts are caught (budget 600)", failsWith(w, site, "budget", "parts (budget 600)"))

		w = fresh()
		local lamp = anyPart(w, "ForecourtLampWest")
		for _, part in ipairs(lamp:GetChildren()) do if part:IsA("BasePart") then part.CFrame = CFrame.new(20.5, 0, -15) * part.CFrame end end -- from (-20.5, 85) to (0, 70)
		check("negative keepouts: a lamp moved into the lounge is caught", failsWith(w, site, "keepouts", "lounge zone VipLounge"))
		w = fresh()
		local bush = anyPart(w, "StreetBush2"):FindFirstChild("BushBig")
		bush.CFrame = CFrame.new(-135, 1, 150)
		check("negative keepouts: a bush on a plot's floor is caught", failsWith(w, site, "keepouts", "plot floor zone Plot2"))
		bush.CFrame = CFrame.new(-135, 4, 174)
		check("negative keepouts: a bush on a garage sign is caught", failsWith(w, site, "keepouts", "sign zone BuySign2"))
		bush.CFrame = CFrame.new(-1, 1, -1)
		check("negative keepouts: a bush on the spawn pad is caught", failsWith(w, site, "keepouts", "spawn pad zone"))
		bush.CFrame = CFrame.new(0, 1.5, 86)
		check("negative keepouts: a bush in front of the lounge door is caught", failsWith(w, site, "keepouts", "lounge door zone"))
		bush.CFrame = CFrame.new(-500, 1, 150)
		check("negative keepouts: a bush in the Studio preview rooms is caught", failsWith(w, site, "keepouts", "preview rooms zone"))
		bush.CFrame = CFrame.new(-135, 1, 112)
		check("negative keepouts: a bush where a room's yard reaches (behind the plot) is caught", failsWith(w, site, "keepouts", "plot reach zone Plot2"))
		w = fresh()
		check("keepouts: the walks lie in their plot's front yard on purpose (allowed, and flat)", #results(w, WorldArt, site).keepouts == 0)
		local walk = anyPart(w, "Walk2")
		walk.CFrame = walk.CFrame * CFrame.new(0, 0, -3)
		check("negative keepouts: a walk pushed onto its plot's floor is caught", failsWith(w, site, "keepouts", "Walk2 is inside the plot floor zone Plot2"))

		w = fresh()
		local cap = anyPart(w, "StreetSign4"):FindFirstChild("SignCap")
		cap.CFrame = cap.CFrame * CFrame.new(0, 3, 0)
		check("negative floating: a sign cap lifted 3 studs off its post is caught", failsWith(w, site, "floating", "SignCap is floating"))
		w = fresh()
		local twin = anyPart(w, "Avenue")
		local copy = newInstance("Part")
		copy.Name = "AvenueTwin"
		copy.Size = twin.Size
		copy.CFrame = twin.CFrame * CFrame.new(1, 0, 0)
		copy.Anchored, copy.CanCollide, copy.CanTouch, copy.CanQuery, copy.CastShadow = true, false, false, false, false
		copy.Material = Enum.Material.SmoothPlastic
		copy.Parent = w:FindFirstChild("Paths")
		check("negative zfighting: a second slab on the avenue's plane is caught", failsWith(w, site, "zfighting", "share a face plane"))
		copy.Size = vec(copy.Size.X, 0.08, copy.Size.Z)
		copy.CFrame = CFrame.new(0, -0.04, 400) -- half sunk: its top is y 0, the Baseplate's top plane
		check("negative zfighting: a slab whose top is the Baseplate's top is caught", failsWith(w, site, "zfighting", "the Baseplate's top"))
		copy.Parent = nil
		local roomPlane = { { name = "FakeRoomMat", box = { -150, -120, 0, 0.16, 182, 188 } } }
		check("negative zfighting: a room part whose top is a world path's top is caught", failsWith(w, site, "zfighting", "FakeRoomMat", { roomBoxes = roomPlane }))
		w = fresh()
		local hill = anyPart(w, "HillWest")
		hill.CFrame = hill.CFrame * CFrame.new(-300, 0, 0)
		check("negative baseplate: a hill pushed past the Baseplate's edge is caught", failsWith(w, site, "baseplate", "HillWest reaches past"))
		w = fresh()
		anyPart(w, "Walk3").Parent = nil
		check("negative connected: plot 3 without its walk is caught", failsWith(w, site, "connected", "plot 3's front edge"))
		w = fresh()
		anyPart(w, "Avenue").Parent = nil
		local r = results(w, WorldArt, site).connected
		check("negative connected: without the avenue no plot is reached from the spawn", #r == 6, #r)
		w = fresh()
		for _, name in ipairs({ "PlazaSouth", "PlazaNorth", "PlazaWest", "PlazaEast" }) do anyPart(w, name).Parent = nil end
		check("negative connected: without the plaza nothing reaches the spawn pad", failsWith(w, site, "connected", "no path reaches the spawn"))
		w = fresh()
		local poor = deepCopy(WorldArt.Palette)
		poor.Kerb = nil
		check("negative palette: a palette without Kerb is caught", failsWith(w, site, "palette", "color Kerb is not in the palette", { palette = poor }))
		local magenta = WorldVisuals.build(nil, WorldArt, site, poor):FindFirstChild("Kerbs"):GetChildren()[1].Color
		check("palette: a missing color builds bright magenta instead of stopping the build", magenta.rgb[1] == 255 and magenta.rgb[2] == 0 and magenta.rgb[3] == 255)
		local night = deepCopy(WorldArt.Palette)
		night.Path = { 60, 60, 70 }
		local restyled = WorldVisuals.build(nil, WorldArt, site, night)
		check("palette: another palette restyles the world (a sector's) and still passes every check", restyled:FindFirstChild("Avenue", true).Color.rgb[1] == 60
			and #WorldVisuals.check(restyled, WorldArt, site, { palette = night }) == 0)
		w = fresh()
		anyPart(w, "StreetSign2"):FindFirstChild("SignBoard"):FindFirstChild("TextFront"):FindFirstChild("Label").Text = "FREE CASH"
		check("negative texts: a word that is not in WorldArt.Texts is caught", failsWith(w, site, "texts", "FREE CASH"))
		local gui = newInstance("SurfaceGui")
		gui.Parent = anyPart(w, "Avenue")
		check("negative texts: a text surface without its label is caught", failsWith(w, site, "texts", "text surfaces"))
		local bad = deepCopy(WorldArt)
		bad.Pieces.Bush[1].shape = "Wedge"
		check("negative data: a Wedge is caught", anyMatch(WorldVisuals.validate(bad), "unknown shape Wedge"))
		bad = deepCopy(WorldArt)
		bad.Pieces.Bush[1].size = { 3, 2, 3 }
		check("negative data: a squashed Ball is caught", anyMatch(WorldVisuals.validate(bad), "3 equal sides"))
		bad = deepCopy(WorldArt)
		bad.Pieces.Lamp[2].rot = { 0, 0, 80 }
		check("negative data: a rotation that is not a quarter turn is caught", anyMatch(WorldVisuals.validate(bad), "quarter turns"))
		bad = deepCopy(WorldArt)
		bad.Pieces.Bench[1].material = "Neon"
		check("negative data: Neon on a bench is caught", anyMatch(WorldVisuals.validate(bad), "Neon is only for lights"))
		bad = deepCopy(WorldArt)
		bad.Pieces.Arch[3].text.value = "WIN"
		check("negative data: a text that is not in WorldArt.Texts is caught", anyMatch(WorldVisuals.validate(bad), "text must be"))
		bad = deepCopy(WorldArt)
		bad.Pieces.Sign[1].collide = true
		check("negative data: a part that wants to collide is caught", anyMatch(WorldVisuals.validate(bad), "never collide"))
		bad = deepCopy(WorldArt)
		bad.Layout.pathTop = bad.Layout.groundTop + 0.01
		check("negative data: layers closer than 0.04 are caught", anyMatch(WorldVisuals.validate(bad), "at least 0.04 apart"))
		bad = deepCopy(WorldArt)
		bad.Pieces.Bush[2].name = "BushBig"
		check("negative data: two parts with the same name in a piece are caught", anyMatch(WorldVisuals.validate(bad), "two parts named BushBig"))
		bad = deepCopy(WorldArt)
		bad.Pieces.Sign[2].name = "Floor"
		check("negative data: a part named like the game's Floor is caught", anyMatch(WorldVisuals.validate(bad), "belongs to the game"))
		bad = deepCopy(WorldArt)
		bad.Hills[1].radius = 10
		check("negative data: a hill steeper than it is wide is caught", anyMatch(WorldVisuals.validate(bad), "Hills[1]"))
		bad = deepCopy(WorldArt)
		bad.Site.spawn = nil
		check("negative data: a missing Studio fact is caught", anyMatch(WorldVisuals.validate(bad), "Site.spawn"))
	end
end)

print_real(string.format("%d passed, %d failed", passed, failed))
print_real(string.format("  default site: %d parts, %d lights", PARTS, LIGHTS))
for _, line in ipairs(SWEEP) do print_real("  " .. line) end
"""


def real_numbers():
    """The numbers the world must agree with, read from the real scripts, as a Luau table."""
    core, ipo, shop = read("TycoonCore.lua"), read("IpoServer.lua"), read("ShopServer.lua")

    def one(pattern, text, what):
        m = re.search(pattern, text)
        if not m:
            raise SystemExit("world_test: %s not found in the scripts (the world pass must be checked against it again)" % what)
        return m

    spacing = int(one(r"local PLOT_SPACING = (\d+)", core, "PLOT_SPACING").group(1))
    count = int(one(r"local MAX_PLOTS = (\d+)", core, "MAX_PLOTS").group(1))
    center = one(r"return Vector3\.new\(startX \+ \(slot - 1\) \* PLOT_SPACING, ([\d.]+), ([\d.]+)\)", core, "plotCenter")
    floor = one(r'makePart\(folder, "Floor", Vector3\.new\(([\d.]+), ([\d.]+), ([\d.]+)\), plotCenter\(slot\)', core, "the Floor")
    buy = one(r"local SIGN_OFFSET = Vector3\.new\((-?[\d.]+), 0\.5, (-?[\d.]+)\)", core, "TycoonCore SIGN_OFFSET")
    ipo_sign = one(r"local SIGN_OFFSET = Vector3\.new\((-?[\d.]+), 0\.5, (-?[\d.]+)\)", ipo, "IpoServer SIGN_OFFSET")
    post = one(r'"BuySign", Vector3\.new\(0\.4, ([\d.]+), 0\.4\), pos \+ Vector3\.new\(0, ([\d.]+), 0\)', core, "the sign's post")
    board = one(r'"Board", Vector3\.new\(([\d.]+), ([\d.]+), ([\d.]+)\), pos \+ Vector3\.new\(0, ([\d.]+), 0\)', core, "the sign's board")
    ipo_post = one(r'"IpoSign", Vector3\.new\(0\.4, ([\d.]+), 0\.4\), pos \+ Vector3\.new\(0, ([\d.]+), 0\)', ipo, "the IPO sign's post")
    ipo_board = one(r'"Board", Vector3\.new\(([\d.]+), ([\d.]+), ([\d.]+)\), pos \+ Vector3\.new\(0, ([\d.]+), 0\)', ipo, "the IPO sign's board")
    if post.groups() != ipo_post.groups() or board.groups() != ipo_board.groups():
        raise SystemExit("world_test: the two garage signs no longer have the same post and board: WorldArt.Site.signBoard must be split")
    landing = one(r"local spawnPos = plotCenter\(slot\) \+ Vector3\.new\((-?[\d.]+), (-?[\d.]+), (-?[\d.]+)\)", core, "the landing spot")
    look = one(r"local signPos = plotCenter\(slot\) \+ Vector3\.new\((-?[\d.]+), (-?[\d.]+), (-?[\d.]+)\)", core, "the landing look")
    lc = one(r"local LOUNGE_CENTER = Vector3\.new\((-?[\d.]+), (-?[\d.]+), (-?[\d.]+)\)", shop, "LOUNGE_CENTER")
    ls = one(r"local LOUNGE_SIZE = Vector3\.new\(([\d.]+), ([\d.]+), ([\d.]+)\)", shop, "LOUNGE_SIZE")
    wall = one(r"local LOUNGE_WALL_HEIGHT = ([\d.]+)", shop, "LOUNGE_WALL_HEIGHT")
    door = one(r"local DOOR_WIDTH = ([\d.]+)", shop, "DOOR_WIDTH")
    sign = one(r'"Sign", Vector3\.new\(DOOR_WIDTH \+ 4, ([\d.]+), 1\), Vector3\.new\(c\.X, c\.Y \+ h \+ ([\d.]+), c\.Z \+ d / 2\)', shop, "the lounge sign")
    drop = one(r"LOUNGE_CENTER \+ Vector3\.new\(0, 4, LOUNGE_SIZE\.Z / 2 \+ ([\d.]+)\)", shop, "the non-VIP drop spot")
    one(r'\{ "BackWall", Vector3\.new\(w, h, 1\)', shop, "the lounge walls (1 thick)")

    def v(*xs):
        return "{ " + ", ".join(str(x) for x in xs) + " }"

    return ("{ spacing = %d, count = %d, plotY = %s, plotZ = %s, floor = %s, buySign = %s, ipoSign = %s, postHeight = %s, board = %s, boardY = %s, "
            "landing = %s, lookAt = %s, lounge = { center = %s, size = %s, wall = %s, door = %s, signHeight = %s, dropOut = %s } }") % (
        spacing, count, center.group(1), center.group(2), v(*floor.groups()), v(*buy.groups()), v(*ipo_sign.groups()), post.group(1),
        v(board.group(1), board.group(2), board.group(3)), board.group(4), v(*landing.groups()), v(*look.groups()),
        v(*lc.groups()), v(*ls.groups()), wall.group(1), door.group(1), sign.group(1), drop.group(1))


def lounge_constants():
    shop = read("ShopServer.lua")
    lines = [l for l in shop.split("\n") if re.match(r"local (LOUNGE_CENTER|LOUNGE_SIZE|LOUNGE_WALL_HEIGHT|DOOR_WIDTH|DOOR_GROUP) =", l)]
    if len(lines) != 5:
        raise SystemExit("world_test: the lounge constants of ShopServer.lua changed")
    return "\n".join(lines)


def world_source(art=None, visuals=None):
    """The test program with the real files. art / visuals replace WorldArt.lua / WorldVisuals.lua (a mutation run)."""
    core, shop = read("TycoonCore.lua"), read("ShopServer.lua")
    replacements = {
        "__WORLDART__": art if art is not None else read("WorldArt.lua"),
        "__WORLDVISUALS__": visuals if visuals is not None else read("WorldVisuals.lua"),
        "__PLOTART__": read("PlotArt.lua"),
        "__PLOTVISUALS__": read("PlotVisuals.lua"),
        "__REAL__": real_numbers(),
        "__PLOTCENTER__": extract_function(core, "local function plotCenter(slot)"),
        "__TYCOON_MAKEPART__": extract_function(core, "local function makePart(parent, name, size, position, color, material)"),
        "__LOUNGE_CONSTANTS__": lounge_constants(),
        "__SHOP_MAKEPART__": extract_function(shop, "local function makePart(parent, name, size, position, color, material)"),
        "__BUILDVIPLOUNGE__": extract_function(shop, "local function buildVipLounge()"),
    }
    text = TESTS
    for key, value in replacements.items():
        text = text.replace(key, value)
    return PRELUDE + text


INTEGRATION_TESTS = r"""-- Tests: the two blocks docs/world_pass_integration.patch inserts into TycoonCore, run as they are ----------------
local MODS = {
	WorldArt = (function()
__WORLDART__
	end)(),
	WorldVisuals = (function()
__WORLDVISUALS__
	end)(),
}
local WARNED = {}
local function warn(text) table.insert(WARNED, tostring(text)) end
-- What TycoonCore's script.Parent:WaitForChild(name, 5) finds in ServerScriptService
local function scriptIn(present)
	local container = {}
	function container.WaitForChild(_, name, timeout)
		if not present[name] then return nil end
		local module = newInstance("ModuleScript")
		module.Name = name
		MODULES[module] = present[name]
		return module
	end
	return { Parent = container }
end
local function runPatch(present)
	for _, c in ipairs(workspace:GetChildren()) do if c.Name == "World" then c:Destroy() end end
	table.clear(WARNED)
	local script = scriptIn(present)
	local ok, err = pcall(function()
__E1__
__CONSTANTS__
__PLOTCENTER__
__E2__
	end)
	local worlds = {}
	for _, c in ipairs(workspace:GetChildren()) do if c.Name == "World" then table.insert(worlds, c) end end
	return ok, err, worlds
end
local function anyMatch(list, word) for _, p in ipairs(list) do if string.find(p, word, 1, true) then return true end end return false end

local ok, err, worlds = runPatch({ WorldArt = MODS.WorldArt, WorldVisuals = MODS.WorldVisuals })
check("integration: with both modules the patched TycoonCore builds one World in the Workspace, without an error or a warning", ok and #worlds == 1 and #WARNED == 0, err or WARNED[1])
if worlds[1] then
	local site = MODS.WorldVisuals.site(MODS.WorldArt)
	local problems = MODS.WorldVisuals.check(worlds[1], MODS.WorldArt, site)
	check("integration: that World passes every named check", #problems == 0, problems[1])
	check("integration: it was built from TycoonCore's own numbers (spacing 90, 6 plots)", worlds[1]:GetAttribute("Spacing") == 90 and worlds[1]:GetAttribute("Plots") == 6)
	check("integration: one street sign per plot", worlds[1]:FindFirstChild("StreetSign6", true) ~= nil and worlds[1]:FindFirstChild("StreetSign7", true) == nil)
end
ok, err, worlds = runPatch({ WorldArt = MODS.WorldArt })
check("integration: without WorldVisuals there is one warning, no World and no error", ok and #worlds == 0 and #WARNED == 1 and anyMatch(WARNED, "World visuals are off"), err or WARNED[1])
ok, err, worlds = runPatch({ WorldVisuals = MODS.WorldVisuals })
check("integration: without WorldArt there is one warning, no World and no error", ok and #worlds == 0 and #WARNED == 1 and anyMatch(WARNED, "World visuals are off"), err or WARNED[1])
local broken = table.clone(MODS.WorldArt)
broken.Layout = nil
ok, err, worlds = runPatch({ WorldArt = broken, WorldVisuals = MODS.WorldVisuals })
check("integration: a broken WorldArt gives a warning, no World and no error (the game runs on)", ok and #worlds == 0 and anyMatch(WARNED, "the world could not be built"), err or WARNED[1])
print_real(string.format("%d passed, %d failed", passed, failed))
"""


PREVIEW_TESTS = r"""-- Tests: the world preview block of docs/STUDIO_SYNC_WORLD.md, run as it is in a fake place ------------------------
local WorldArtModule = (function()
__WORLDART__
end)()
local WorldVisualsModule = (function()
__WORLDVISUALS__
end)()
local SSS = SERVICES.ServerScriptService
for name, module in pairs({ WorldArt = WorldArtModule, WorldVisuals = WorldVisualsModule }) do
	local script = newInstance("ModuleScript")
	script.Name = name
	script.Parent = SSS
	MODULES[script] = module
end
-- The plot visuals' own preview rooms stand in the place too (Studio only): a few parts where they are
local stages = newInstance("Folder")
stages.Name = "PREVIEW_STAGES"
stages.Parent = workspace
for stage = 1, 5 do
	local floor = newInstance("Part")
	floor.Name = "Floor"
	floor.Size = vec(60, 1, 60)
	floor.Position = vec(-600 + (stage - 1) * 70, 0.5, 150)
	floor.Parent = stages
end
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
local spawnBefore, baseBefore = spawnPad.CFrame, baseplate.Size
local ok, err = runPreview()
check("preview: the block runs in the fake place without an error", ok, err)
local folder = workspace:FindFirstChild("PREVIEW_WORLD")
check("preview: it builds Workspace.PREVIEW_WORLD holding the World and the ghosts", folder ~= nil and folder:FindFirstChild("World") ~= nil and folder:FindFirstChild("Ghosts") ~= nil)
for _, name in ipairs(WorldVisualsModule.CHECKS) do
	check("preview: it prints OK for the check " .. name, has("OK " .. name), PRINTED[1])
end
check("preview: it prints OK for the Studio facts (the SpawnLocation and the Baseplate where the owner measured them)", has("OK studio facts"))
check("preview: it prints OK for untouched (the SpawnLocation and the Baseplate as they were)", has("OK untouched"))
check("preview: it prints OK for clashes (the plot visuals' preview rooms are not in the way)", has("OK clashes with parts already in the Workspace"))
do
	local empty = newInstance("Folder")
	local saved = {}
	for _, c in ipairs(SSS:GetChildren()) do table.insert(saved, c); c.Parent = empty end
	local missingOk, missingErr = runPreview()
	check("preview: without the two ModuleScripts it stops at once with a clear message (it never waits forever)",
		not missingOk and string.find(tostring(missingErr), "First create the ModuleScripts", 1, true) ~= nil, missingErr)
	for _, c in ipairs(saved) do c.Parent = SSS end
	runPreview()
end
check("preview: it prints the part and light counts with their budgets", has("PREVIEW_WORLD: 268 parts (budget 600), 6 lights (budget 8). Delete it before publishing."))
check("preview: the SpawnLocation and the Baseplate were not changed", spawnPad.CFrame == spawnBefore and baseplate.Size == baseBefore and spawnPad.Parent == workspace and baseplate.Parent == workspace)
check("preview: the ghosts are see-through and never solid", (function()
	for _, g in ipairs(folder:FindFirstChild("Ghosts"):GetChildren()) do
		if g.Transparency < 0.5 or g.CanCollide or g.CanQuery or g.CanTouch then return false end
	end
	return #folder:FindFirstChild("Ghosts"):GetChildren() == 7
end)())
runPreview()
local n = 0
for _, c in ipairs(workspace:GetChildren()) do if c.Name == "PREVIEW_WORLD" then n += 1 end end
check("preview: running it again replaces the old preview (one PREVIEW_WORLD)", n == 1)
spawnPad.Position = vec(-1, 0.5, 9)
runPreview()
check("preview: a SpawnLocation away from the measured spot prints PROBLEM studio facts", has("PROBLEM studio facts"))
spawnPad.Position = vec(-1, 0.5, -1)
local stray = newInstance("Part")
stray.Name = "OldFence"
stray.Size = vec(10, 4, 1)
stray.Position = vec(0, 2, 195)
stray.Parent = workspace
runPreview()
check("preview: a hand-placed part standing on the front street is listed as a NOTE", has("NOTE clashes with parts already in the Workspace"))
stray.Parent = nil
runPreview()
check("preview: with it gone, OK again", has("OK clashes with parts already in the Workspace") and has("OK studio facts"))
print_real(string.format("%d passed, %d failed", passed, failed))
"""


def doc_block(heading):
    """The first ```lua block after a heading of docs/STUDIO_SYNC_WORLD.md."""
    text = read("docs/STUDIO_SYNC_WORLD.md")
    start = text.index("```lua\n", text.index(heading)) + len("```lua\n")
    return text[start:text.index("```", start)]


def preview_source():
    block = "\n".join("\t\t" + line if line.strip() else line for line in doc_block("## The world preview (command bar)").split("\n"))
    return PRELUDE + PREVIEW_TESTS.replace("__WORLDART__", read("WorldArt.lua")).replace("__WORLDVISUALS__", read("WorldVisuals.lua")).replace("__PREVIEW__", block)


def patched_tycoon():
    """main's TycoonCore.lua with docs/world_pass_integration.patch applied in a scratch folder, or None without git."""
    try:
        base = subprocess.run(["git", "show", BASE + ":TycoonCore.lua"], cwd=ROOT, capture_output=True)
    except OSError:
        return None
    if base.returncode != 0:
        return None
    with tempfile.TemporaryDirectory() as tmp:
        with open(os.path.join(tmp, "TycoonCore.lua"), "wb") as f:
            f.write(base.stdout)
        applied = subprocess.run(["git", "apply", os.path.join(ROOT, "docs", "world_pass_integration.patch")], cwd=tmp, capture_output=True, text=True)
        if applied.returncode != 0:
            raise SystemExit("world_test: docs/world_pass_integration.patch does not apply to TycoonCore.lua at %s: %s" % (BASE, applied.stderr.strip()))
        with open(os.path.join(tmp, "TycoonCore.lua"), encoding="utf-8") as f:
            return f.read()


def patch_hunks():
    """The lines each hunk of the integration patch adds (without their leading +)."""
    hunks, current = [], None
    for line in read("docs/world_pass_integration.patch").split("\n"):
        if line.startswith("@@"):
            current = []
            hunks.append(current)
        elif current is not None and line.startswith("+") and not line.startswith("+++"):
            current.append(line[1:])
    return ["\n".join(h) for h in hunks]


def patched_blocks(patched):
    """The two blocks the patch inserts, read from the patched TycoonCore by their first comment line."""
    e1_start = patched.index("-- The world around the plots (the spawn plaza")
    e1_end = patched.index("\tWorldVisuals, WorldArt = nil, nil\nend\n", e1_start) + len("\tWorldVisuals, WorldArt = nil, nil\nend\n")
    e2_start = patched.index("-- The world around the plots, built once")
    e2_end = patched.index("\nPlayers.PlayerAdded:Connect(onPlayerAdded)", e2_start)
    return patched[e1_start:e1_end], patched[e2_start:e2_end]


def integration_source(patched):
    e1, e2 = patched_blocks(patched)
    constants = "\n".join(l for l in patched.split("\n") if re.match(r"local (PLOT_SPACING|MAX_PLOTS) = ", l))
    text = (INTEGRATION_TESTS.replace("__WORLDART__", read("WorldArt.lua")).replace("__WORLDVISUALS__", read("WorldVisuals.lua"))
            .replace("__E1__", e1).replace("__CONSTANTS__", constants)
            .replace("__PLOTCENTER__", extract_function(patched, "local function plotCenter(slot)")).replace("__E2__", e2))
    return PRELUDE + text


def patch_checks(patched):
    """Source checks on the patch itself and on the patched TycoonCore."""
    passed, failed = 0, 0

    def check(name, cond, extra=None):
        nonlocal passed, failed
        if cond:
            passed += 1
        else:
            failed += 1
            print("FAIL: " + name + (" -- " + str(extra) if extra else ""))

    patch = read("docs/world_pass_integration.patch")
    files = re.findall(r"^\+\+\+ b/(\S+)", patch, re.M)
    check("integration patch: it changes TycoonCore.lua and nothing else", files == ["TycoonCore.lua"], files)
    removed = [l for l in patch.split("\n") if l.startswith("-") and not l.startswith("---")]
    check("integration patch: it only adds lines (nothing of TycoonCore is removed or rewritten)", removed == [], removed[:2])
    hunks = patch_hunks()
    check("integration patch: two blocks, of 10 and 12 lines", len(hunks) == 2 and len(hunks[0].split("\n")) == 10 and len(hunks[1].split("\n")) == 12, [len(h.split("\n")) for h in hunks])
    added = "\n".join(hunks)
    for word in ("Touched", "Instance.new", "DataStore", "addEarnings", "Remote", "SetAttribute", "playerData", "data."):
        check("integration patch: the added lines never use %s" % word, word not in added)
    check("integration patch: both modules are required inside pcall with a 5 s wait, like PlotVisuals",
          'pcall(require, script.Parent:WaitForChild("WorldVisuals", 5))' in added and 'pcall(require, script.Parent:WaitForChild("WorldArt", 5))' in added)
    check("integration patch: the build runs inside pcall and only warns on failure", "pcall(function()" in hunks[1] and "warn(" in hunks[1])
    check("integration patch: the world is built from TycoonCore's PLOT_SPACING, MAX_PLOTS and plotCenter",
          "WorldVisuals.site(WorldArt, PLOT_SPACING, MAX_PLOTS, plotCenter)" in hunks[1])
    if patched is not None:
        check("integration patch: the patched TycoonCore still builds the world before players are set up",
              patched.index("WorldVisuals.build(") < patched.index("Players.PlayerAdded:Connect(onPlayerAdded)") and patched.index("local function plotCenter(") < patched.index("WorldVisuals.build("))
        check("integration patch: the patched TycoonCore has no Touched handler (tools/daily_test.py's rule)", "Touched" not in patched)
    return passed, failed


def integration_suites(luau):
    """Optional (--integration): a scratch copy of the repo with the patch applied runs tools/daily_test.py and this test."""
    with tempfile.TemporaryDirectory() as tmp:
        files = subprocess.run(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"], cwd=ROOT, capture_output=True).stdout.split(b"\0")
        for raw in files:
            if not raw:
                continue
            name = raw.decode()
            target = os.path.join(tmp, name)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            if os.path.exists(os.path.join(ROOT, name)):
                shutil.copy(os.path.join(ROOT, name), target)
        with open(os.path.join(tmp, "TycoonCore.lua"), "w", encoding="utf-8") as f:
            f.write(patched_tycoon())
        env = dict(os.environ, LUAU=luau)
        ok = True
        for script in ("tools/daily_test.py", "tools/world_test.py"):
            result = subprocess.run([sys.executable, os.path.join(tmp, script)], cwd=tmp, capture_output=True, text=True, env=env)
            bad = [l for l in result.stdout.split("\n") if l.startswith("FAIL") and "no existing file is edited" not in l] if script.endswith("world_test.py") else \
                [l for l in result.stdout.split("\n") if "FAIL" in l or (" failed" in l and " 0 failed" not in l)]
            print("  with the patch applied, %s: %s" % (script, "all pass" if not bad and (result.returncode == 0 or script.endswith("world_test.py")) else "FAILS " + "; ".join(bad[:3])))
            ok = ok and not bad
        return ok


def static_checks():
    """Source checks on the new files: looks only, pure data, no services, no randomness, no assets, no emoji, no odds words,
    and no existing file edited."""
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
                     "rbxasset", "http", "MeshId", "TextureId", "Image =", "loadstring", "task.wait", "LocalPlayer", "FireServer",
                     "InvokeServer", "OnServerEvent", "Players", "PromptProductPurchase", "PromptGamePassPurchase", "PromptPurchase"):
            check("%s never uses %s (looks only: no input, remote, save, asset or randomness)" % (name, word), word not in code)
        check("%s is plain ASCII (no emoji or other symbols anywhere, comments included)" % name, all(ord(c) < 128 for c in text),
              sorted(set(c for c in text if ord(c) >= 128)))
        offending = [lit for lit in lua_strings(text) if any(w in lit.lower() for w in ("random", "chance", "odds", "luck"))]
        check("%s: no string uses the words random, chance, odds or luck (D9)" % name, not offending, offending[:3])
        size = len(text.encode("utf-8"))
        check("%s stays under 120 KB (%d bytes)" % (name, size), size < 120 * 1024)
    art, vis = code_only(read("WorldArt.lua")), code_only(read("WorldVisuals.lua"))
    check("WorldArt.lua is pure data: no Instance.new, GetService, require or function call on the game", not any(w in art for w in ("Instance.new", "GetService", "require(", "game", "workspace")))
    check("WorldVisuals.lua asks for no service and requires nothing (art and site are passed in)", "GetService" not in vis and "require(" not in vis)
    check("WorldVisuals.lua never reads or writes the Workspace by itself", "workspace" not in vis and "game." not in vis and "game:" not in vis)
    check("WorldVisuals.lua sets every part's CanCollide, CanTouch and CanQuery to false in one place",
          vis.count("part.CanCollide = false") == 1 and vis.count("part.CanTouch = false") == 1 and vis.count("part.CanQuery = false") == 1
          and "CanCollide = true" not in vis)

    try:
        have = subprocess.run(["git", "cat-file", "-e", BASE + "^{commit}"], cwd=ROOT, capture_output=True).returncode == 0
    except OSError:
        have = False
    if not have:
        print("note: git or the base commit %s is not available here, so the 'no existing file edited' checks are skipped" % BASE)
    else:
        changed = subprocess.run(["git", "diff", "--name-only", "--diff-filter=MDRT", BASE, "--"], cwd=ROOT, capture_output=True, text=True).stdout.split()
        check("no existing file is edited: against %s only CONTRIBUTING.md differs (the integration patch is not applied)" % BASE,
              [n for n in changed if n != "CONTRIBUTING.md"] == [], changed)
        diff = subprocess.run(["git", "diff", "-U0", BASE, "--", "CONTRIBUTING.md"], cwd=ROOT, capture_output=True, text=True).stdout
        edits = [l for l in diff.split("\n") if l[:1] in ("+", "-") and not l.startswith(("+++", "---"))]
        check("CONTRIBUTING.md: only rows of the Ownership table change (the claims)", all(l[1:].startswith("| ") for l in edits), [l for l in edits if not l[1:].startswith("| ")][:2])
        same = subprocess.run(["git", "diff", "--quiet", BASE, "--", "tools/daily_test.py"], cwd=ROOT).returncode == 0
        check("tools/daily_test.py (other branches own it) is untouched", same)
    return passed, failed


def apply_mutation(text, old, new, what):
    if text.count(old) < 1:
        raise SystemExit("mutation target not found in %s: %r" % (what, old))
    return text.replace(old, new, 1)


# Mutation runs: (label, file, old text, new text, the named check that must fail). Each one is run as the full test
# program; it counts only if it runs to the end AND the named check fails (a crash or another check is not enough).
V = "WorldVisuals.lua"
A = "WorldArt.lua"
# Group A: WorldVisuals.lua. The builder breaks a rule (the default world's named check must fail), or a check is
# weakened (the negative test that proves that check must fail).
MUTANTS_A = [
    ("decor that collides", V, "part.CanCollide = false", "part.CanCollide = true", "default site: check flags"),
    ("decor that stops rays and the camera", V, "part.CanQuery = false", "part.CanQuery = true", "default site: check flags"),
    ("decor that can be touched", V, "part.CanTouch = false", "part.CanTouch = true", "default site: check flags"),
    ("unanchored decor", V, "\tpart.Anchored = true\n\tpart.CanCollide", "\tpart.Anchored = false\n\tpart.CanCollide", "default site: check flags"),
    ("every part casts a shadow (flat paths too)", V, "part.CastShadow = longest >= WorldVisuals.TINY and not flat and not neon", "part.CastShadow = true",
     "default site: check flags"),
    ("no avenue from the plaza", V, 'rect(plan.paths, "Avenue", ax - half, ax + half, pz1, crossZ0, "Path")', "", "default site: check connected"),
    ("walks stop a stud short of their plot", V, 'p.z + site.floor[3] / 2, frontZ0, "Walk")', 'p.z + site.floor[3] / 2 + 1, frontZ0, "Walk")',
     "default site: check connected"),
    ("walks run onto their plot's floor", V, 'p.z + site.floor[3] / 2, frontZ0, "Walk")', 'p.z + site.floor[3] / 2 - 2, frontZ0, "Walk")',
     "default site: check keepouts"),
    ("no connector between the streets", V, "if roomLeft and roomRight then", "if false then", "default site: check connected"),
    ("the back street pushed into the rooms' yard", V, "local backZ1 = backZ0 + L.pathWidth", "local backZ1 = backZ0 + L.pathWidth + 8",
     "default site: check keepouts"),
    ("every street lamp lit", V, 'item("Lamp", "StreetLamp" .. k, gaps[k], far + L.lampDZ)', 'item("Lamp", "StreetLamp" .. k, gaps[k], far + L.lampDZ, 0, { lit = true })',
     "default site: check budget"),
    ("the plaza over the spawn pad's margin", V, "local hx, hz = sp.halfX + L.spawnMargin, sp.halfZ + L.spawnMargin", "local hx, hz = sp.halfX - 1, sp.halfZ - 1",
     "default site: check keepouts"),
    ("the forecourt overlapping the back street", V, 'rect(plan.paths, "Forecourt", ax - armIn, ax + armIn, foreZ0, backZ0, "Plaza")',
     'rect(plan.paths, "Forecourt", ax - armIn, ax + armIn, foreZ0, backZ0 + 2, "Plaza")', "default site: check zfighting"),
    ("hills standing on the ground instead of sunk", V, "part.CFrame = CFrame.new(h.x, h.height - d / 2, h.z)", "part.CFrame = CFrame.new(h.x, d / 2, h.z)",
     "default site: check baseplate"),
    ("a street sign shows the next plot's number", V, "{ slot = i })", "{ slot = i + 1 })", "default site: check texts"),
    ("a street sign planted inside its plot", V, 'item("Sign", "StreetSign" .. i, p.x + L.signDX, far + L.signDZ, 0, { slot = i })',
     'item("Sign", "StreetSign" .. i, p.x + L.signDX, p.z, 0, { slot = i })', "default site: check keepouts"),
    ("a script in every decor item", V, "\t\tmodel.Parent = decor", "\t\tInstance.new(\"Script\").Parent = model\n\t\tmodel.Parent = decor",
     "default site: check flags"),
    ("paths, kerbs and lawns in Neon", V, "part.Material = Enum.Material[material]", "part.Material = Enum.Material.Neon", "default site: check flags"),
    ("two plaza slabs overlapping", V, 'rect(plan.paths, "PlazaWest", px0, cx - hx, cz - hz, cz + hz, "Plaza")',
     'rect(plan.paths, "PlazaWest", px0, cx - hx, cz - hz - 2, cz + hz, "Plaza")', "default site: check zfighting"),
    ("the build resizes the Baseplate next to it", V, "\tworld.Parent = parent\n\treturn world",
     "\tif parent and parent:FindFirstChild(\"Baseplate\") then parent:FindFirstChild(\"Baseplate\").Size = Vector3.new(2048, 16, 2000) end\n\tworld.Parent = parent\n\treturn world",
     "real objects: the plots, their signs, the lounge, the SpawnLocation and the Baseplate are exactly as before"),
    ("the flags check forgets CanCollide", V, "if part.CanCollide then", "if false then", "negative flags: a collidable part is caught"),
    ("the flicker check wants exactly the same plane", V, "WorldVisuals.PLANE = 0.005", "WorldVisuals.PLANE = 0", "negative zfighting"),
    ("the floating check thinks everything touches", V, "WorldVisuals.TOUCH = 0.06", "WorldVisuals.TOUCH = 50", "negative floating"),
    ("the keep-out zones are never looked at", V, "if overlaps(p.above, zone.box, WorldVisuals.OVERLAP) and", "if false and overlaps(p.above, zone.box, WorldVisuals.OVERLAP) and",
     "negative keepouts"),
    ("the Baseplate's edge is never looked at", V, "if b[1] < g.x0 or b[2] > g.x1 or b[5] < g.z0 or b[6] > g.z1 then", "if false then", "negative baseplate"),
    ("the parts budget is never looked at", V, "if #parts > art.Budget.parts then", "if false then", "negative budget: 668 parts"),
    ("the texts check allows any word", V, "if not allowed[label.Text] then", "if false then", "negative texts: a word"),
    ("a sunk ball measured as a whole sphere", V, "local a = cy >= 0 and r or math.sqrt(math.max(r * r - cy * cy, 0))", "local a = r", "aboveGround: a sunk ball"),
    ("two paths join without touching", V, "return ox >= need and oz >= need", "return true", "negative connected"),
]
# Group B: WorldArt.lua. The data breaks a rule, or a copied number or a Studio fact stops matching the real thing.
MUTANTS_B = [
    ("a palette color removed", A, "\tKerb = { 246, 246, 240 },\n", "", "default site: check palette"),
    ("a part names a color the palette lacks", A, 'upright("LampPole", 7, 0.5, 0, 0.6, 0, "LampPost", "Metal"),',
     'upright("LampPole", 7, 0.5, 0, 0.6, 0, "LampPoles", "Metal"),', "default site: check palette"),
    ("the arch says something else", A, 'value = "BUILD YOUR STARTUP", font', 'value = "FREE CASH", font', "default site: check data"),
    ("a bench seat in Neon", A, '{ 0, 1.15, 0 }, "Bench", "WoodPlanks"),', '{ 0, 1.15, 0 }, "Bench", "Neon"),', "default site: check flags"),
    ("a Wedge for a bush", A, 'P("BushBig", "Ball",', 'P("BushBig", "Wedge",', "default site: check flags"),
    ("a squashed bush ball", A, 'P("BushBig", "Ball", { 3, 3, 3 }', 'P("BushBig", "Ball", { 3, 2, 3 }', "default site: check data"),
    ("every upright cylinder tilted 10 degrees", A, "color, material, { rot = { 0, 0, 90 } })", "color, material, { rot = { 0, 0, 80 } })",
     "default site: check flags"),
    ("a parts budget too small for the world", A, "Budget = { parts = 600, lights = 8 }", "Budget = { parts = 200, lights = 8 }", "default site: check budget"),
    ("a lights budget too small for the world", A, "Budget = { parts = 600, lights = 8 }", "Budget = { parts = 600, lights = 5 }", "default site: check budget"),
    ("the plaza reaching over the spawn pad", A, "spawnMargin = 1,", "spawnMargin = -1,", "default site: check keepouts"),
    ("paths on the lawn layer", A, "pathTop = 0.16,", "pathTop = 0.04,", "default site: check data"),
    ("lawns on the Baseplate's top plane", A, "groundTop = 0.04,", "groundTop = 0.001,", "default site: check zfighting"),
    ("the front street into the rooms' yard", A, "frontGap = 1,", "frontGap = -2,", "default site: check keepouts"),
    ("the lounge loop hugging the lounge (the hedge in its walls)", A, "armGap = 4.5,", "armGap = 1,", "default site: check keepouts"),
    ("a hill next to the plots", A, "x = 180, z = 600, height = 20, radius = 120", "x = 180, z = 250, height = 20, radius = 120", "default site: check keepouts"),
    ("the measured SpawnLocation written down wrong", A, "spawn = { position = { -1, 0.5, -1 }", "spawn = { position = { -1, 0.5, 30 }",
     "Studio facts: they match the SpawnLocation"),
    ("plotZ copied wrong from TycoonCore", A, "plotZ = 150,", "plotZ = 160,", "copied: plotY and plotZ"),
    ("the lounge copied wrong from ShopServer", A, "center = { 0, 0.5, 70 }", "center = { 0, 0.5, 64 }", "copied: lounge center"),
    ("the plots' reach smaller than the rooms", A, "plotReach = { side = 36,", "plotReach = { side = 30,", "rooms: every room fits"),
    ("a text on a face that doesn't exist", A, 'color = "SignText", faces = { "Front", "Back" } } }),', 'color = "SignText", faces = { "Inside" } } }),',
     "default site: check data"),
    ("the arch's beam lifted off its posts", A, '{ 0, 9.9, 0 }, "ArchBeam"', '{ 0, 12, 0 }, "ArchBeam"', "default site: check floating"),
    ("the drop spot copied wrong from ShopServer", A, "dropOut = 6 }", "dropOut = 3 }", "copied: lounge sign height and the drop spot"),
    ("walks too narrow to walk through", A, "walkWidth = 6,", "walkWidth = 3,", "default site: check connected"),
    ("the garage sign board copied wrong", A, "signBoard = { 8, 2.6, 0.3 },", "signBoard = { 6, 2.6, 0.3 },", "copied: the signs' board and post"),
]


def run_mutants(luau, mutants, group):
    """Runs every mutant (four at a time). Returns how many were caught and a FAIL line for each one that was not."""
    from concurrent.futures import ThreadPoolExecutor
    art, vis = read("WorldArt.lua"), read("WorldVisuals.lua")

    def one(mutant):
        label, filename, old, new, expected = mutant
        if filename == "WorldArt.lua":
            source = world_source(art=apply_mutation(art, old, new, filename))
        else:
            source = world_source(visuals=apply_mutation(vis, old, new, filename))
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
    result = run_luau(luau, world_source())
    out = result.stdout.strip() or result.stderr.strip()
    print("World data, builder, checks, the real objects and the sweep: " + out)
    m = re.search(r"^(\d+) passed, (\d+) failed$", result.stdout, re.M)
    if not m or m.group(2) != "0" or result.returncode != 0:
        code = 1
    total += int(m.group(1)) if m else 0
    static_passed, static_failed = static_checks()
    print("World source checks: %d passed, %d failed" % (static_passed, static_failed))
    total += static_passed
    if static_failed:
        code = 1
    if os.path.exists(os.path.join(ROOT, "docs", "STUDIO_SYNC_WORLD.md")):
        result = run_luau(luau, preview_source())
        print("World preview block (docs/STUDIO_SYNC_WORLD.md) in a fake place: " + (result.stdout.strip() or result.stderr.strip()))
        m = re.search(r"^(\d+) passed, (\d+) failed$", result.stdout, re.M)
        if not m or m.group(2) != "0":
            code = 1
        total += int(m.group(1)) if m else 0
    if os.path.exists(os.path.join(ROOT, "docs", "world_pass_integration.patch")):
        patched = patched_tycoon()
        if patched is None:
            print("note: git or the base commit %s is not available here, so the integration blocks are not run" % BASE)
        else:
            result = run_luau(luau, integration_source(patched))
            print("Integration patch blocks run in the fake: " + (result.stdout.strip() or result.stderr.strip()))
            m = re.search(r"^(\d+) passed, (\d+) failed$", result.stdout, re.M)
            if not m or m.group(2) != "0":
                code = 1
            total += int(m.group(1)) if m else 0
        patch_passed, patch_failed = patch_checks(patched)
        print("Integration patch source checks: %d passed, %d failed" % (patch_passed, patch_failed))
        total += patch_passed
        if patch_failed:
            code = 1
        if "--integration" in sys.argv:
            print("Integration: both test suites on a scratch copy with the patch applied:")
            if not integration_suites(luau):
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
            print("World mutations, group %s: %d of %d caught, each by its named check" % (group, got, len(mutants)))
    print("world_test.py: %d checks passed, %d of %d mutation runs caught%s" % (total, caught, runs, "" if code == 0 else "  -- SOMETHING FAILED"))
    return code


if __name__ == "__main__":
    sys.exit(main())
