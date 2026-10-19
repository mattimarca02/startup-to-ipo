#!/usr/bin/env python3
"""Tests for the world pass (WorldArt.lua and WorldVisuals.lua), outside Studio.

Run:   python3 tools/world_test.py
       python3 tools/world_test.py --integration   (also both suites on a scratch copy with the patch applied)
       python3 tools/world_test.py --review        (also the review checks against the merge-base with main)
       python3 tools/world_test.py --strict-patch  (at merge time, with --review: the integration patch must apply
           exactly, and its preamble and the TycoonCore row of docs/STUDIO_SYNC_WORLD.md must be what --regen-patch
           writes; without it, an offset, fuzz or a stale preamble is only a NOTE)
       python3 tools/world_test.py --regen-patch [label]   (rewrites docs/world_pass_integration.patch and the
           TycoonCore row of docs/STUDIO_SYNC_WORLD.md for this worktree's TycoonCore.lua, at merge time)

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
# The first comment line of each block the integration patch adds: if TycoonCore.lua already has them, it is merged
PATCH_MARKERS = ("-- The world around the plots (the spawn plaza", "-- The world around the plots, built once")
STALE = "patch needs regenerating"
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
-- overhaul 2 phase 2: the rooms' solid boxes are measured in the garage's frame (PlotVisuals.addSolid / decorSolids)
function CF.Inverse(t)
	local r = t.r
	local q = { r[1], r[4], r[7], r[2], r[5], r[8], r[3], r[6], r[9] }
	return cf(-(q[1] * t.x + q[2] * t.y + q[3] * t.z), -(q[4] * t.x + q[5] * t.y + q[6] * t.z), -(q[7] * t.x + q[8] * t.y + q[9] * t.z), q)
end
function CF.ToObjectSpace(a, b) return a:Inverse() * b end
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
	Terrain = { BasePart = true, PVInstance = true },
	Script = { BaseScript = true, LuaSourceContainer = true }, LocalScript = { Script = true, BaseScript = true, LuaSourceContainer = true },
	ModuleScript = { LuaSourceContainer = true }, SurfaceGui = { LayerCollector = true, GuiBase = true },
	TextLabel = { GuiObject = true, GuiBase2d = true }, Decal = { FaceInstance = true },
}
local PART_CLASSES = { Part = true, SpawnLocation = true, Seat = true, WedgePart = true, Terrain = true }
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
	local LobbyConfig = { ClaimEnabled = false } -- the row (lobby L4: with the claim on, the ring, tested on its own)
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
	check("data: every named check exists, in order", table.concat(WorldVisuals.CHECKS, ",") == "data,budget,flags,solid,keepouts,floating,zfighting,baseplate,connected,palette,texts")
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
	check("copied: the front is the frame's +Z (teleportToPlot lands at +12 and looks at +24 in the garage's frame)", REAL.landing[3] < REAL.lookAt[3] and REAL.landing[1] == 0 and REAL.lookAt[1] == 0)
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
	check("default site: the World Model holds Paths, Kerbs, Ground, Decor, Solid and Hills", world.Name == "World" and world:FindFirstChild("Paths") and world:FindFirstChild("Kerbs")
		and world:FindFirstChild("Ground") and world:FindFirstChild("Decor") and world:FindFirstChild("Solid") and world:FindFirstChild("Hills"))
	check("default site: knows its spacing and plot count", world:GetAttribute("Spacing") == 90 and world:GetAttribute("Plots") == 6)
	do
		local collide, touch, query, anchored, scripts, solids, badSolid = 0, 0, 0, 0, 0, 0, 0
		for _, p in ipairs(partsOf(world)) do
			if p.Parent.Name == "Solid" then
				solids += 1
				if not (p.CanCollide and p.Anchored and p.Transparency == 1 and not p.CanTouch and p.CanQuery) then badSolid += 1 end
			else
				if p.CanCollide then collide += 1 end
				if p.CanTouch then touch += 1 end
				if p.CanQuery then query += 1 end
			end
			if not p.Anchored then anchored += 1 end
		end
		for _, d in ipairs(world:GetDescendants()) do if d:IsA("LuaSourceContainer") then scripts += 1 end end
		check("default site: no decor collides, is touched or stops a ray; every part is anchored; no script", collide + touch + query + anchored + scripts == 0)
		check("default site: the Solid group's invisible boxes are the only parts that collide (the lamps, trees, benches, planters, signs, the arch: overhaul phase 1)",
			solids > 0 and badSolid == 0, solids .. " solids, " .. badSolid .. " bad")
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
		local wedge = newInstance("WedgePart")
		wedge.Size = vec(1, 1, 1)
		wedge.Position = vec(-500, 0.5, -500)
		wedge.Anchored, wedge.CanCollide, wedge.CanTouch, wedge.CanQuery, wedge.CastShadow = true, false, false, false, false
		wedge.Parent = w:FindFirstChild("Decor")
		check("negative flags: a WedgePart (not a plain Part) is caught, and the checks don't stop on it", failsWith(w, site, "flags", "only plain Parts"))
		wedge.Parent = nil
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
		-- the flat pieces' materials (overhaul phase 5: textured ground instead of flat plastic)
		check("materials: WorldArt.Materials is Concrete paths and kerbs, Grass lawns and hills (overhaul phase 5)", type(WorldArt.Materials) == "table"
			and WorldArt.Materials.path == "Concrete" and WorldArt.Materials.kerb == "Concrete" and WorldArt.Materials.ground == "Grass" and WorldArt.Materials.hill == "Grass")
		w = fresh()
		check("materials: a built path slab is Concrete, a kerb Concrete, a lawn Grass and a hill Grass", w:FindFirstChild("Paths"):GetChildren()[1].Material.Name == "Concrete"
			and w:FindFirstChild("Kerbs"):GetChildren()[1].Material.Name == "Concrete" and w:FindFirstChild("Ground"):GetChildren()[1].Material.Name == "Grass"
			and w:FindFirstChild("Hills"):GetChildren()[1].Material.Name == "Grass")
		check("materials: the trees' crowns, the bushes, the hedge balls and the planters' flowers are Grass (leafy), the trunks Wood", WorldArt.Pieces.TreeA[2].material == "Grass"
			and WorldArt.Pieces.TreeC[3].material == "Grass" and WorldArt.Pieces.Bush[1].material == "Grass" and WorldArt.Pieces.Hedge[1].material == "Grass"
			and WorldArt.Pieces.Planter[2].material == "Grass" and WorldArt.Pieces.TreeA[1].material == "Wood")
		local bad = deepCopy(WorldArt)
		bad.Materials.ground = "Neon"
		check("negative data: a Neon lawn material is caught (Materials.ground)", anyMatch(WorldVisuals.validate(bad), "Materials.ground"))
		bad = deepCopy(WorldArt)
		bad.Materials.path = "Sand"
		check("negative data: a path material outside MATERIALS is caught", anyMatch(WorldVisuals.validate(bad), "Materials.path"))
		bad = deepCopy(WorldArt)
		bad.Materials = nil
		check("data: with no Materials table the world still builds (SmoothPlastic paths and lawns, as before phase 5)", #WorldVisuals.validate(bad) == 0
			and WorldVisuals.build(nil, bad, site):FindFirstChild("Paths"):GetChildren()[1].Material.Name == "SmoothPlastic")
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
    floor = one(r'makePart\(garage, "Floor", Vector3\.new\(([\d.]+), ([\d.]+), ([\d.]+)\), plotFrame\(slot\)', core, "the Floor")  # lobby L2: in buildGarages
    buy = one(r"local SIGN_OFFSET = Vector3\.new\((-?[\d.]+), 0\.5, (-?[\d.]+)\)", core, "TycoonCore SIGN_OFFSET")
    ipo_sign = one(r"local SIGN_OFFSET = Vector3\.new\((-?[\d.]+), 0\.5, (-?[\d.]+)\)", ipo, "IpoServer SIGN_OFFSET")
    # Both signs stand at `pos`, their spot in the garage's frame (lobby PR L1): post and board are placed from it with CFrame.new
    post = one(r'"BuySign", Vector3\.new\(0\.4, ([\d.]+), 0\.4\), pos \* CFrame\.new\(0, ([\d.]+), 0\)', core, "the sign's post")
    board = one(r'"Board", Vector3\.new\(([\d.]+), ([\d.]+), ([\d.]+)\), pos \* CFrame\.new\(0, ([\d.]+), 0\)', core, "the sign's board")
    ipo_post = one(r'"IpoSign", Vector3\.new\(0\.4, ([\d.]+), 0\.4\), pos \* CFrame\.new\(0, ([\d.]+), 0\)', ipo, "the IPO sign's post")
    ipo_board = one(r'"Board", Vector3\.new\(([\d.]+), ([\d.]+), ([\d.]+)\), pos \* CFrame\.new\(0, ([\d.]+), 0\)', ipo, "the IPO sign's board")
    if post.groups() != ipo_post.groups() or board.groups() != ipo_board.groups():
        raise SystemExit("world_test: the two garage signs no longer have the same post and board: WorldArt.Site.signBoard must be split")
    landing = one(r"local spawnPos = plotFrame\(slot\) \* Vector3\.new\((-?[\d.]+), (-?[\d.]+), (-?[\d.]+)\)", core, "the landing spot")
    look = one(r"local signPos = plotFrame\(slot\) \* Vector3\.new\((-?[\d.]+), (-?[\d.]+), (-?[\d.]+)\)", core, "the landing look")
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
		local LobbyConfig = { ClaimEnabled = false } -- the row (lobby L4: plotCenter reads the ring only with the claim on)
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
-- Workspace.Terrain: a BasePart whose box is the whole map (Studio always has it)
local terrain = newInstance("Terrain")
terrain.Name = "Terrain"
terrain.Size = vec(2044, 252, 2044)
terrain.Position = vec(0, 0, 0)
terrain.Parent = workspace
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
check("preview: Workspace.Terrain is never listed as a clash (its box covers the world, so it would be without the rule)",
	has("OK clashes with parts already in the Workspace") and #WorldVisualsModule.clashes(folder:FindFirstChild("World"), { terrain }) > 0)
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
check("preview: it prints the part and light counts with their budgets", has("PREVIEW_WORLD: 320 parts (budget 600), 6 lights (budget 8). Delete it before publishing."))
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

-- The cleanup block and the check block of section (e), as written, after the previews
local function runBlock(block)
	table.clear(PRINTED)
	local ok, err = pcall(block)
	return ok, err, table.concat(PRINTED, "\n")
end
local function cleanupBlock()
__CLEANUP__
end
local function checkBlock()
__CHECK__
end
local StarterGui = SERVICES.StarterGui
local function folderAt(name, parent)
	local f = newInstance("Folder")
	f.Name = name
	f.Parent = parent
	return f
end
local function contains(text, piece)
	return string.find(text, piece, 1, true) ~= nil
end
local icons = folderAt("PREVIEW_ICONS", StarterGui)
local lightTest = folderAt("LightTest", icons)
local shopGui = folderAt("ShopGui", StarterGui)
local holder = newInstance("Model")
holder.Name = "Props"
holder.Parent = workspace
local nested = folderAt("PREVIEW_OLD", holder)             -- an unknown PREVIEW_ object, deep down
local stray = folderAt("PREVIEW_X", workspace)             -- unrelated, at the top: must survive the cleanup
local misplaced = folderAt("PREVIEW_WORLD", holder)        -- a known name in the wrong place: unknown
local oldLight = folderAt("PREVIEW_LIGHT", StarterGui)     -- what an older light test left: unknown
local inner = folderAt("PREVIEW_INNER", workspace:FindFirstChild("PREVIEW_WORLD")) -- inside a known one: goes with it
local twin = folderAt("PREVIEW_STAGES", workspace)         -- two with a known name at the right place: both go
local okC, errC, said = runBlock(checkBlock)
check("check block: with previews there it prints FAIL and every PREVIEW_ object, known and unknown", okC and string.sub(said, 1, 5) == "FAIL "
	and contains(said, "Workspace.PREVIEW_WORLD (known") and contains(said, "Workspace.PREVIEW_STAGES (known") and contains(said, "StarterGui.PREVIEW_ICONS (known")
	and contains(said, "Workspace.PREVIEW_WORLD.PREVIEW_INNER (known") and contains(said, "Workspace.Props.PREVIEW_OLD (unknown")
	and contains(said, "Workspace.PREVIEW_X (unknown") and contains(said, "Workspace.Props.PREVIEW_WORLD (unknown")
	and contains(said, "StarterGui.PREVIEW_LIGHT (unknown") and contains(said, "FAIL 9 PREVIEW_"), errC or said)
check("check block: it changes nothing", workspace:FindFirstChild("PREVIEW_WORLD") ~= nil and icons.Parent == StarterGui and stray.Parent == workspace
	and nested.Parent == holder and twin.Parent == workspace)
local okR, errR, cleaned = runBlock(cleanupBlock)
local removedLine = ""
for _, line in ipairs(string.split(cleaned, "\n")) do if string.sub(line, 1, 9) == "Removed: " then removedLine = line end end
local removedCount = #string.split(string.sub(removedLine, 10), ", ")
check("cleanup block: it removes exactly the three known previews (Workspace.PREVIEW_STAGES, Workspace.PREVIEW_WORLD, StarterGui.PREVIEW_ICONS) and says which",
	okR and workspace:FindFirstChild("PREVIEW_WORLD") == nil and workspace:FindFirstChild("PREVIEW_STAGES") == nil and StarterGui:FindFirstChild("PREVIEW_ICONS") == nil
	and twin.Parent == nil and not lightTest:IsDescendantOf(StarterGui) and not inner:IsDescendantOf(workspace)
	and contains(removedLine, "Workspace.PREVIEW_WORLD") and contains(removedLine, "Workspace.PREVIEW_STAGES") and contains(removedLine, "StarterGui.PREVIEW_ICONS")
	and removedCount == 4 and not contains(removedLine, "PREVIEW_INNER") and not contains(removedLine, "Props"), errR or (removedLine .. " | " .. cleaned))
check("cleanup block: an unrelated PREVIEW_X, a PREVIEW_WORLD in the wrong place, a nested PREVIEW_OLD and an old PREVIEW_LIGHT all survive",
	stray.Parent == workspace and misplaced.Parent == holder and nested.Parent == holder and oldLight.Parent == StarterGui, cleaned)
check("cleanup block: each unknown PREVIEW_ object is reported: unknown PREVIEW_ object: <path>, delete it by hand",
	contains(cleaned, "unknown PREVIEW_ object: Workspace.PREVIEW_X, delete it by hand") and contains(cleaned, "unknown PREVIEW_ object: Workspace.Props.PREVIEW_OLD, delete it by hand")
	and contains(cleaned, "unknown PREVIEW_ object: Workspace.Props.PREVIEW_WORLD, delete it by hand") and contains(cleaned, "unknown PREVIEW_ object: StarterGui.PREVIEW_LIGHT, delete it by hand"), cleaned)
check("cleanup block: with unknown PREVIEW_ objects left it ends with FAIL, not OK", contains(cleaned, "\nFAIL 4 unknown PREVIEW_ object(s) left, not deleted: ")
	and not contains(cleaned, "\nOK "), cleaned)
check("cleanup block: everything else stays (Baseplate, SpawnLocation, Terrain, StarterGui.ShopGui, Workspace.Props)",
	baseplate.Parent == workspace and spawnPad.Parent == workspace and terrain.Parent == workspace and shopGui.Parent == StarterGui and holder.Parent == workspace)
local _, _, between = runBlock(checkBlock)
check("check block: after the cleanup it lists only the unknown ones", contains(between, "FAIL 4 PREVIEW_") and contains(between, "Workspace.PREVIEW_X (unknown")
	and not contains(between, "(known"), between)
for _, gone in ipairs({ stray, misplaced, nested, oldLight }) do gone:Destroy() end -- deleted by hand
local _, _, after = runBlock(checkBlock)
check("check block: once they are deleted by hand it prints OK", after == "OK no PREVIEW_ object in Workspace or StarterGui", after)
local okAgain, _, again = runBlock(cleanupBlock)
check("cleanup block: run again, it says nothing was there and OK", okAgain and contains(again, "Removed: nothing (no preview was there)")
	and contains(again, "OK no PREVIEW_ object is left") and not contains(again, "unknown"), again)
print_real(string.format("%d passed, %d failed", passed, failed))
"""


def doc_block(heading, doc=None):
    """The first ```lua block after a heading of docs/STUDIO_SYNC_WORLD.md (or of `doc`, a changed copy)."""
    text = doc if doc is not None else read("docs/STUDIO_SYNC_WORLD.md")
    start = text.index("```lua\n", text.index(heading)) + len("```lua\n")
    return text[start:text.index("```", start)]


def indented(block, tabs):
    return "\n".join("\t" * tabs + line if line.strip() else line for line in block.split("\n"))


def preview_source(doc=None):
    block = indented(doc_block("## The world preview (command bar)", doc), 2)
    return PRELUDE + (PREVIEW_TESTS.replace("__WORLDART__", read("WorldArt.lua")).replace("__WORLDVISUALS__", read("WorldVisuals.lua"))
                      .replace("__CLEANUP__", indented(doc_block("### The cleanup block (command bar)", doc), 1))
                      .replace("__CHECK__", indented(doc_block("### The check block (command bar)", doc), 1)).replace("__PREVIEW__", block))


HASH_TESTS = r"""-- Tests: the hash block of docs/STUDIO_SYNC_WORLD.md, run as it is, on the files at SYNC_HISTORY in a fake place ----------------
local SOURCES = __SOURCES__
for name, entry in pairs(SOURCES) do
	local script = newInstance("ModuleScript")
	script.Name = name
	script.Source = entry.source
	script.Parent = SERVICES[entry.place]
end
local ok, err = pcall(function()
__HASHBLOCK__
end)
check("hash block: it runs without an error", ok, err)
for name in pairs(SOURCES) do
	local said = nil
	for _, line in ipairs(PRINTED) do if string.sub(line, 1, #name + 1) == name .. " " then said = line end end
	check("hash block: " .. name .. " prints OK (Luau's SHA-256 of the file at 98cc7a9 is the one in the table)", said ~= nil and string.find(said, " OK ", 1, true) ~= nil, said)
end
local function runWith(change)
	for name, entry in pairs(SOURCES) do
		SERVICES[entry.place]:FindFirstChild(name).Source = change(entry.source)
	end
	table.clear(PRINTED)
	pcall(function()
__HASHBLOCK__
	end)
	local ok, different = 0, 0
	for _, line in ipairs(PRINTED) do
		if string.find(line, " OK ", 1, true) then ok += 1 end
		if string.find(line, " DIFFERENT ", 1, true) then different += 1 end
	end
	return ok, different
end
local okDropped = runWith(function(source) return string.sub(source, 1, -2) end)
check("hash block: a script whose last newline Studio dropped prints OK (four of four)", okDropped == 4, okDropped)
local okAdded = runWith(function(source) return source .. "\n" end)
check("hash block: a script with one newline added at the end prints OK (four of four)", okAdded == 4, okAdded)
local _, twoAdded = runWith(function(source) return source .. "\n\n" end)
check("hash block: two newlines added is DIFFERENT (four of four)", twoAdded == 4, twoAdded)
local _, different = runWith(function(source) return source .. "-- changed\n" end)
check("hash block: a changed script prints DIFFERENT (four of four)", different == 4, different)
local _, oneChar = runWith(function(source) return "x" .. string.sub(source, 2) end)
check("hash block: one character changed (same size) prints DIFFERENT (four of four)", oneChar == 4, oneChar)
print_real(string.format("%d passed, %d failed", passed, failed))
"""


def lua_long_string(text):
    eq = "="
    while ("]" + eq + "]") in text:
        eq += "="
    return "[" + eq + "[\n" + text + "]" + eq + "]"


SYNCED = (("WorldArt", "ServerScriptService"), ("WorldVisuals", "ServerScriptService"), ("IconArt", "ReplicatedStorage"), ("IconVisuals", "ReplicatedStorage"))
# docs/STUDIO_SYNC_WORLD.md is the world pass's history (the quality lane owns it, docs/LANES.md): its rows and hash block
# give the four files as they were on main at SYNC_HISTORY, before the lanes. A world lane PR that changes one of them
# lists its new SHA-256 and size in its own lane file (LANE_FILE, "Studio steps"), and the quality lane carries it into
# docs/STUDIO_SYNC_BATCH.md (BATCH_FILE). So the doc is checked against the files at SYNC_HISTORY, and every newer file
# against its row in either file (once a batch is done the lane file's section empties, and the batch keeps the row).
SYNC_HISTORY = "98cc7a9"
LANE_FILE = "docs/lanes/world.md"
BATCH_FILE = "docs/STUDIO_SYNC_BATCH.md"


def history_bytes(name):
    """A file as it was at SYNC_HISTORY (bytes), or None when git can't show it (a copy without the history)."""
    got = subprocess.run(["git", "show", "%s:%s" % (SYNC_HISTORY, name)], cwd=ROOT, capture_output=True)
    return got.stdout if got.returncode == 0 else None


def hash_source(doc=None):
    block = doc_block("## (d) Hash check (command bar)", doc)
    old = {name: history_bytes(name + ".lua") for name, _ in SYNCED}
    sources = "{ " + ", ".join('%s = { place = "%s", source = %s }' % (name, place, lua_long_string(
        old[name].decode("utf-8") if old[name] is not None else read(name + ".lua"))) for name, place in SYNCED) + " }"
    text = HASH_TESTS.replace("__SOURCES__", sources).replace("__HASHBLOCK__", block)
    return PRELUDE + text


def sync_table_checks():
    """docs/STUDIO_SYNC_WORLD.md's table and hash block list each new file with its real SHA-256 and size."""
    import hashlib
    passed, failed = 0, 0

    def check(name, cond, extra=None):
        nonlocal passed, failed
        if cond:
            passed += 1
        else:
            failed += 1
            print("FAIL: " + name + (" -- " + str(extra) if extra else ""))

    doc = read("docs/STUDIO_SYNC_WORLD.md")
    lane = read(LANE_FILE) if os.path.exists(os.path.join(ROOT, LANE_FILE)) else ""
    batch = read(BATCH_FILE) if os.path.exists(os.path.join(ROOT, BATCH_FILE)) else ""
    for name, place in SYNCED:
        raw = open(os.path.join(ROOT, name + ".lua"), "rb").read()
        old = history_bytes(name + ".lua")
        check("git: %s.lua can be read at %s (git show; a copy without the git history lacks it)" % (name, SYNC_HISTORY), old is not None)
        if old is None:
            continue
        h = hashlib.sha256(old).hexdigest()
        row = "| `%s` | ModuleScript, %s | new | `%s` | %d |" % (name, place, h, len(old))
        check("STUDIO_SYNC_WORLD.md: the table row of %s has its SHA-256 and size at %s" % (name, SYNC_HISTORY), row in doc, "%s %d" % (h, len(old)))
        check("STUDIO_SYNC_WORLD.md: the hash block expects %s's SHA-256 and size at %s" % (name, SYNC_HISTORY), ('%s = { "%s", %d, "%s" },' % (name, h, len(old), place)) in doc)
        if raw != old:
            h = hashlib.sha256(raw).hexdigest()
            row = "| `%s` | ModuleScript, %s | changed | `%s` | %d |" % (name, place, h, len(raw))
            check("%s or %s: %s changed since %s, and the lane file's Studio steps or the batch give its real SHA-256 and size"
                  % (LANE_FILE, BATCH_FILE, name, SYNC_HISTORY), row in lane or row in batch, "%s %d" % (h, len(raw)))
    how, patched = integration_state()
    made = patch_made_for()
    if how == "applied" and made is not None and sha(read("TycoonCore.lua"))[:2] == made[:2]:
        h, size = sha(patched)
        check("STUDIO_SYNC_WORLD.md: the patched TycoonCore's SHA-256 and size are the patch's real result",
              ("`%s` | %d |" % (h, size)) in doc, h)
    else:
        print("note: TycoonCore.lua is not the file the patch was made for (main at %s) or the patch is merged, so the patched "
              "TycoonCore hash in STUDIO_SYNC_WORLD.md (valid for that file only) is not compared" % (made[2] if made else "?"))
    return passed, failed


def unpatched_tycoon(text, hunks=None):
    """TycoonCore.lua without the two blocks the integration patch adds (for a file where the patch is merged)."""
    for block in (hunks if hunks is not None else patch_hunks()):
        text = text.replace(block + "\n", "", 1)
    return text


def apply_patch_how(text, patch=None):
    """(text with the integration patch applied in a scratch folder, how it applied). how: "exact" (every hunk at
    the line its header names), "offset" (git found a hunk some lines away), "fuzz" (only with less context: git
    apply -C1, one line of context must match, like patch's default fuzz of 2 on 3 lines). (None, None) if it does
    not apply or git is missing. patch: the patch's text (default: docs/world_pass_integration.patch)."""
    with tempfile.TemporaryDirectory() as tmp:
        target = os.path.join(tmp, "TycoonCore.lua")
        patch_path = os.path.join(tmp, "integration.patch")
        with open(patch_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(patch if patch is not None else read("docs/world_pass_integration.patch"))
        for extra in ([], ["-C1"]):
            with open(target, "w", encoding="utf-8", newline="\n") as f:
                f.write(text)
            try:
                applied = subprocess.run(["git", "apply", "-v"] + extra + [patch_path], cwd=tmp, capture_output=True, text=True)
            except OSError:
                return None, None
            if applied.returncode == 0:
                said = applied.stdout + applied.stderr
                how = "fuzz" if extra or "Context reduced" in said else ("offset" if re.search(r"\(offset -?\d+ lines?\)", said) else "exact")
                with open(target, encoding="utf-8") as f:
                    return f.read(), how
    return None, None


def apply_patch(text):
    """text with docs/world_pass_integration.patch applied (exactly, with an offset or with fuzz), or None."""
    return apply_patch_how(text)[0]


def integration_state():
    """How the integration patch stands against the TycoonCore.lua of this worktree:
    ("merged", text)   TycoonCore.lua already holds the patch's marker lines (the patch was applied or merged)
    ("applied", text)  the patch applies to it (exactly or with fuzz); text = the patched file, in memory only
    ("stale", None)    it does not apply: the patch needs regenerating
    ("nogit", None)    git is not installed, so it could not be tried"""
    current = read("TycoonCore.lua")
    if any(marker in current for marker in PATCH_MARKERS):
        return "merged", current
    if shutil.which("git") is None:
        return "nogit", None
    patched = apply_patch(current)
    if patched is None:
        return "stale", None
    return "applied", patched


def patched_tycoon():
    """The patched TycoonCore (merged or applied in memory), or None (stale patch or no git)."""
    return integration_state()[1]


def patch_hunks():
    """The lines each hunk of the integration patch adds (without their leading +)."""
    return patch_hunks_of(read("docs/world_pass_integration.patch"))


def patch_hunks_of(text):
    hunks, current = [], None
    for line in text.split("\n"):
        if line.startswith("@@"):
            current = []
            hunks.append(current)
        elif current is not None and line.startswith("+") and not line.startswith("+++"):
            current.append(line[1:])
    return ["\n".join(h) for h in hunks]


# The integration patch's preamble. Its hashes, line numbers and hunk headers are valid only for the TycoonCore.lua
# named in "Made for:"; python3 tools/world_test.py --regen-patch rewrites them for the TycoonCore.lua of the worktree.
PATCH_PREAMBLE = """World pass integration (branch world-icons-pass): NOT APPLIED. It needs the owner's approval.

Made for: TycoonCore.lua sha256 {base_sha}, {base_size} bytes (main at {label}).
Result:   TycoonCore.lua sha256 {res_sha}, {res_size} bytes.
Both hashes, the line numbers below and the hunk headers are valid for that TycoonCore.lua only (main at {label}).
On any other TycoonCore.lua (main moved on), regenerate them at merge time, in the repo folder, on the branch that
claims TycoonCore:
  python3 tools/world_test.py --regen-patch
It rewrites this file and the TycoonCore row of docs/STUDIO_SYNC_WORLD.md (a) for the TycoonCore.lua it finds, and
prints the new hash. tools/world_test.py tests that procedure and fails ("patch needs regenerating") once the patch
no longer applies.

What it does: TycoonCore builds the world around the plots once, when the server starts, from WorldArt and
WorldVisuals. It passes its own PLOT_SPACING, MAX_PLOTS and plotCenter, so the world moves with the plots if
those ever change. Both modules are required inside pcall with a 5 second wait, the same way as PlotVisuals and
PlotArt: if either is missing or broken there is one warning and the game runs exactly as today. No save, no
remote, no player data, no touch handler, nothing runs per player.

The two edits, in TycoonCore.lua at main {label} (TycoonCore is the only file this changes):
  E1  after line {e1_end} (the end of the "Plot visuals are off" block, lines {e1_start}-{e1_end}): 10 lines that require
      WorldVisuals and WorldArt inside pcall and warn if they are missing.
  E2  between line {e2_before} (the end of onPlayerAdded) and line {e2_after} (Players.PlayerAdded:Connect(onPlayerAdded)):
      12 lines that build the world once inside pcall, from PLOT_SPACING (line {ps}), MAX_PLOTS (line {mp}) and
      plotCenter (lines {pc0}-{pc1}).

Studio steps by hand, in this order (nothing syncs by itself):
  1. ServerScriptService: create a ModuleScript named exactly WorldArt and paste WorldArt.lua into it.
  2. ServerScriptService: create a ModuleScript named exactly WorldVisuals and paste WorldVisuals.lua into it.
     Do both before pasting TycoonCore (it waits 5 s for each inside pcall, so it never hangs, but without
     them the world is simply not built).
  3. Only after approval: apply this patch (git apply docs/world_pass_integration.patch on a branch that claims
     TycoonCore), then paste the new TycoonCore.lua into the Script TycoonCore (ServerScriptService).
  4. Remove Workspace.PREVIEW_WORLD if it exists (the cleanup block, docs/STUDIO_SYNC_WORLD.md (e)), then F5.
  5. View > Drafts: commit every draft. Publish with Shut down all servers, as always.

Checked by tools/world_test.py --integration: the patch applies to the worktree's TycoonCore.lua, the patched file
passes tools/daily_test.py and tools/world_test.py, and the two inserted blocks build the world in the fake.

"""
MADE_FOR = re.compile(r"^Made for: TycoonCore\.lua sha256 ([0-9a-f]{64}), (\d+) bytes \(main at (\S+)\)\.$", re.M)
RESULT = re.compile(r"^Result:   TycoonCore\.lua sha256 ([0-9a-f]{64}), (\d+) bytes\.$", re.M)
SYNC_ROW = re.compile(r"^\| `TycoonCore` \| Script, ServerScriptService \|.*$", re.M)
E1_ANCHOR = "\tPlotVisuals, PlotArt = nil, nil\nend\n\n"
E2_ANCHOR = "\nPlayers.PlayerAdded:Connect(onPlayerAdded)\n"


def sha(text):
    import hashlib
    raw = text.encode("utf-8")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def patch_made_for(patch=None):
    """(sha256, bytes, label) of the TycoonCore.lua the patch was made for, from its "Made for:" line, or None."""
    m = MADE_FOR.search(patch if patch is not None else read("docs/world_pass_integration.patch"))
    return (m.group(1), int(m.group(2)), m.group(3)) if m else None


def patch_result(patch=None):
    m = RESULT.search(patch if patch is not None else read("docs/world_pass_integration.patch"))
    return (m.group(1), int(m.group(2))) if m else None


def insert_blocks(base, hunks):
    """base (a TycoonCore.lua without the patch) with the two blocks put at their anchors. Raises ValueError, naming
    the anchor, if one is missing or there twice (then the blocks must be placed by hand)."""
    for name, anchor in (("E1 (the end of the plot visuals block)", E1_ANCHOR), ("E2 (Players.PlayerAdded:Connect(onPlayerAdded))", E2_ANCHOR)):
        if base.count(anchor) != 1:
            raise ValueError("cannot regenerate the patch: the anchor of %s is found %d times in TycoonCore.lua" % (name, base.count(anchor)))
    i = base.index(E1_ANCHOR) + len(E1_ANCHOR)
    text = base[:i] + hunks[0] + "\n" + base[i:]
    j = text.index(E2_ANCHOR) + 1
    return text[:j] + hunks[1] + "\n" + text[j:]


def line_of(text, start, prefix):
    """1-based number of the first line at or after line `start` that begins with prefix."""
    lines = text.split("\n")
    for n in range(start - 1, len(lines)):
        if lines[n].startswith(prefix):
            return n + 1
    raise ValueError("cannot regenerate the patch: no line starting with %r in TycoonCore.lua" % prefix)


def regen_patch(base, label, hunks=None):
    """The whole integration patch (preamble and hunks) for this TycoonCore.lua, and the patched file."""
    hunks = hunks if hunks is not None else patch_hunks()
    patched = insert_blocks(base, hunks)
    with tempfile.TemporaryDirectory() as tmp:
        for side, text in (("old", base), ("new", patched)):
            os.makedirs(os.path.join(tmp, side))
            with open(os.path.join(tmp, side, "TycoonCore.lua"), "w", encoding="utf-8", newline="\n") as f:
                f.write(text)
        diff = subprocess.run(["git", "diff", "--no-index", "--no-color", "--no-ext-diff", "-U3", "old/TycoonCore.lua", "new/TycoonCore.lua"],
                              cwd=tmp, capture_output=True, text=True).stdout
    body = diff[diff.index("\n@@") + 1:]
    e1_start = line_of(base, 1, "local visualsOk, PlotVisuals = pcall(require")
    e1_end = line_of(base, e1_start, "end")
    e2_after = line_of(base, 1, "Players.PlayerAdded:Connect(onPlayerAdded)")
    pc0 = line_of(base, 1, "local function plotCenter(")
    base_sha, base_size = sha(base)
    res_sha, res_size = sha(patched)
    preamble = PATCH_PREAMBLE.format(base_sha=base_sha, base_size=base_size, label=label, res_sha=res_sha, res_size=res_size,
                                     e1_start=e1_start, e1_end=e1_end, e2_before=e2_after - 1, e2_after=e2_after,
                                     ps=line_of(base, 1, "local PLOT_SPACING = "), mp=line_of(base, 1, "local MAX_PLOTS = "),
                                     pc0=pc0, pc1=line_of(base, pc0, "end"))
    return preamble + "--- a/TycoonCore.lua\n+++ b/TycoonCore.lua\n" + body, patched


def sync_row(label, res_sha, res_size):
    return ("| `TycoonCore` | Script, ServerScriptService | **only after approval**: `main`'s file (at %s) with "
            "`docs/world_pass_integration.patch` applied; valid for that file only (`--regen-patch`) | `%s` | %d |" % (label, res_sha, res_size))


def regen_command():
    """--regen-patch [label]: rewrites docs/world_pass_integration.patch and the TycoonCore row of
    docs/STUDIO_SYNC_WORLD.md for this worktree's TycoonCore.lua (with the patch merged, for the file without it)."""
    current = read("TycoonCore.lua")
    base = unpatched_tycoon(current) if any(m in current for m in PATCH_MARKERS) else current
    args = sys.argv[sys.argv.index("--regen-patch") + 1:]
    label = args[0] if args and not args[0].startswith("-") else None
    if label is None:
        got = subprocess.run(["git", "show", "origin/main:TycoonCore.lua"], cwd=ROOT, capture_output=True)
        same = got.returncode == 0 and got.stdout.decode("utf-8") == base
        label = subprocess.run(["git", "rev-parse", "--short", "origin/main"], cwd=ROOT, capture_output=True, text=True).stdout.strip() if same else ""
        label = label or "worktree-" + sha(base)[0][:7]
    try:
        patch, patched = regen_patch(base, label)
    except ValueError as e:
        print(str(e))
        return 1
    with open(os.path.join(ROOT, "docs", "world_pass_integration.patch"), "w", encoding="utf-8", newline="\n") as f:
        f.write(patch)
    doc_path = os.path.join(ROOT, "docs", "STUDIO_SYNC_WORLD.md")
    res_sha, res_size = sha(patched)
    doc = read("docs/STUDIO_SYNC_WORLD.md")
    with open(doc_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(SYNC_ROW.sub(lambda _: sync_row(label, res_sha, res_size), doc, count=1))
    print("Regenerated docs/world_pass_integration.patch for TycoonCore.lua %s (%d bytes, main at %s)" % (sha(base)[0], sha(base)[1], label))
    print("Patched TycoonCore.lua: sha256 %s, %d bytes (written to the TycoonCore row of docs/STUDIO_SYNC_WORLD.md (a))" % (res_sha, res_size))
    print("Now run python3 tools/world_test.py --integration")
    return 0


STRICT = "integration patch (--strict-patch): it applies exactly, and its preamble and the TycoonCore row of STUDIO_SYNC_WORLD.md are what --regen-patch writes -- " + STALE


def strict_problems(current, patch, doc):
    """Why --strict-patch fails for this TycoonCore.lua (current, merged or not), patch and STUDIO_SYNC_WORLD.md
    (doc): the patch applies only with an offset or fuzz, or its Made for / Result lines, the patched file's
    SHA-256 and size, the preamble's line numbers, the hunk headers or the doc's TycoonCore row are not what
    --regen-patch would write. Empty = all exact."""
    problems = []
    hunks = patch_hunks_of(patch)
    base = unpatched_tycoon(current, hunks) if any(m in current for m in PATCH_MARKERS) else current
    applied, how = apply_patch_how(base, patch)
    if applied is None:
        problems.append("it does not apply")
    elif how != "exact":
        problems.append("it applies only with %s (git apply)" % ("an offset" if how == "offset" else "fuzz"))
    made, result = patch_made_for(patch), patch_result(patch)
    label = made[2] if made else "?"
    try:
        again, again_patched = regen_patch(base, label, hunks)
    except ValueError as e:
        return problems + [str(e)]
    want_made, want_result = sha(base), sha(again_patched)
    if made is None or made[:2] != want_made:
        problems.append("Made for: says %s, %s bytes; this TycoonCore.lua is %s, %d bytes" % (made and made[0][:12], made and made[1], want_made[0][:12], want_made[1]))
    if result is None or result != want_result:
        problems.append("Result: says %s, %s bytes; regeneration gives %s, %d bytes" % (result and result[0][:12], result and result[1], want_result[0][:12], want_result[1]))
    if applied is not None and sha(applied) != result:
        problems.append("the patched file is %s, %d bytes, not the Result line's" % (sha(applied)[0][:12], sha(applied)[1]))
    old_lines, new_lines = PREAMBLE_LINES.search(patch), PREAMBLE_LINES.search(again)
    if not (old_lines and new_lines and old_lines.groups() == new_lines.groups()):
        problems.append("the preamble's line numbers are %s; regeneration gives %s" % (old_lines and old_lines.groups(), new_lines and new_lines.groups()))
    headers = [l for l in patch.split("\n") if l.startswith("@@")]
    want_headers = [l for l in again.split("\n") if l.startswith("@@")]
    if headers != want_headers:
        problems.append("the hunk headers are %s; regeneration gives %s" % ([h.split(" @@")[0] for h in headers], [h.split(" @@")[0] for h in want_headers]))
    row = SYNC_ROW.search(doc)
    if row is None or row.group(0) != sync_row(label, *want_result):
        problems.append("the TycoonCore row of the STUDIO_SYNC doc is not the one --regen-patch writes (%s)" % (row and row.group(0)[-90:]))
    if not problems and again != patch:
        problems.append("the patch is not byte for byte what --regen-patch writes (from byte %d)" % next(
            (i for i, (a, b) in enumerate(zip(again, patch)) if a != b), min(len(again), len(patch))))
    return problems


PREAMBLE_LINES = re.compile(r"E1  after line (\d+) .*lines (\d+)-(\d+)\).*\n.*\n  E2  between line (\d+) .* and line (\d+) .*\n"
                            r".*PLOT_SPACING \(line (\d+)\), MAX_PLOTS \(line (\d+)\) and\n\s+plotCenter \(lines (\d+)-(\d+)\)")


def preamble_problems(patch, base):
    """What the preamble's line numbers point at in base, if not the lines they name (empty = all right)."""
    m = PREAMBLE_LINES.search(patch)
    if not m:
        return ["the preamble's line numbers are missing"]
    e1, e1a, e1b, e2a, e2b, ps, mp, pc0, pc1 = (int(v) for v in m.groups())
    lines = [""] + base.split("\n")

    def at(n):
        return lines[n] if 0 < n < len(lines) else ""
    problems = []
    if not (e1 == e1b and at(e1a).startswith("local visualsOk, PlotVisuals = pcall(require") and at(e1b) == "end"
            and "PlotVisuals, PlotArt = nil, nil" in at(e1b - 1) and "end" not in lines[e1a + 1:e1b - 1]):
        problems.append("E1: lines %d-%d are not the plot visuals block" % (e1a, e1b))
    if not (e2b == e2a + 1 and at(e2a) == "end" and at(e2b) == "Players.PlayerAdded:Connect(onPlayerAdded)"):
        problems.append("E2: lines %d and %d are not the end of onPlayerAdded and the PlayerAdded hook" % (e2a, e2b))
    if not (at(ps).startswith("local PLOT_SPACING = ") and at(mp).startswith("local MAX_PLOTS = ")):
        problems.append("PLOT_SPACING or MAX_PLOTS is not on the line named")
    if not (at(pc0).startswith("local function plotCenter(") and at(pc1) == "end" and pc1 > pc0 and "end" not in lines[pc0 + 1:pc1]):
        problems.append("plotCenter is not lines %d-%d" % (pc0, pc1))
    return problems


def regen_checks():
    """The regeneration procedure, tested: it reproduces the committed patch from the file it was made for, and on a
    TycoonCore.lua with lines added it gives a patch that applies exactly, with the line numbers and the hash moved."""
    passed, failed = 0, 0

    def check(name, cond, extra=None):
        nonlocal passed, failed
        if cond:
            passed += 1
        else:
            failed += 1
            print("FAIL: " + name + (" -- " + str(extra) if extra else ""))

    patch = read("docs/world_pass_integration.patch")
    made, result = patch_made_for(patch), patch_result(patch)
    check("regen: the patch names the TycoonCore.lua it was made for and its result (Made for:, Result:)", made is not None and result is not None)
    if made is None or result is None or shutil.which("git") is None:
        return passed, failed
    doc = read("docs/STUDIO_SYNC_WORLD.md")
    row = SYNC_ROW.search(doc)
    check("regen: STUDIO_SYNC_WORLD.md's TycoonCore row has the patch's Result hash and size and its base",
          row is not None and row.group(0) == sync_row(made[2], result[0], result[1]), row and row.group(0))
    current = read("TycoonCore.lua")
    base = unpatched_tycoon(current) if any(m in current for m in PATCH_MARKERS) else current
    if sha(base)[:2] == made[:2]:
        again, patched = regen_patch(base, made[2])
        check("regen: from the TycoonCore.lua it was made for, --regen-patch gives the committed patch byte for byte", again == patch,
              next((i for i, (a, b) in enumerate(zip(again, patch)) if a != b), "lengths %d %d" % (len(again), len(patch))))
        check("regen: the committed Result line is the hash of that file with the patch applied", sha(patched)[:2] == result)
    else:
        print("note: TycoonCore.lua is not the file the patch was made for (main at %s), so the byte-for-byte regeneration "
              "check is skipped (the checks on this worktree's TycoonCore.lua below still run)" % made[2])
    # On this worktree's own TycoonCore.lua, whichever it is
    try:
        cur_patch, cur_patched = regen_patch(base, "test")
    except ValueError as e:
        cur_patch, cur_patched = None, None
        check("regen: this worktree's TycoonCore.lua can be regenerated -- " + STALE + " by hand (an anchor changed)", False, e)
    if cur_patch is not None:
        check("regen: the regenerated Made for and Result lines are the hashes of this TycoonCore.lua and of it patched",
              patch_made_for(cur_patch)[:2] == sha(base)[:2] and patch_result(cur_patch) == sha(cur_patched)[:2])
        problems = preamble_problems(cur_patch, base)
        check("regen: every line number in the regenerated preamble points at the line it names", problems == [], problems[:1])
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, "TycoonCore.lua")
            with open(target, "w", encoding="utf-8", newline="\n") as f:
                f.write(base)
            with open(os.path.join(tmp, "p.patch"), "w", encoding="utf-8", newline="\n") as f:
                f.write(cur_patch)
            exact = subprocess.run(["git", "apply", "p.patch"], cwd=tmp, capture_output=True).returncode == 0
            with open(target, encoding="utf-8") as f:
                applied = f.read()
        committed = apply_patch(base)
        check("regen: the regenerated patch applies exactly to this TycoonCore.lua and gives the same file as the committed patch",
              exact and applied == cur_patched and block_order(cur_patched) == [] and (committed is None or committed == cur_patched))
    lines = base.split("\n")
    pc = next((i for i, l in enumerate(lines) if l.startswith("local function onPlayerAdded(")), None)
    check("regen: this worktree's TycoonCore.lua has local function onPlayerAdded( -- " + STALE + " by hand", pc is not None)
    if pc is None:
        return passed, failed
    moved = "\n".join(["-- added line %d" % k for k in range(5)] + lines[:pc] + ["-- moved %d" % k for k in range(3)] + lines[pc:])
    try:
        new_patch, new_patched = regen_patch(moved, "test")
    except ValueError as e:
        new_patch, new_patched = None, None
        check("regen: a TycoonCore.lua with 5 lines added at the top and 3 before onPlayerAdded can be regenerated", False, e)
    if new_patch is not None and cur_patch is not None:
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, "TycoonCore.lua")
            with open(target, "w", encoding="utf-8", newline="\n") as f:
                f.write(moved)
            with open(os.path.join(tmp, "p.patch"), "w", encoding="utf-8", newline="\n") as f:
                f.write(new_patch)
            exact = subprocess.run(["git", "apply", "p.patch"], cwd=tmp, capture_output=True).returncode == 0
            with open(target, encoding="utf-8") as f:
                applied = f.read()
        nm, om = PREAMBLE_LINES.search(new_patch), PREAMBLE_LINES.search(cur_patch)
        check("regen: with lines added, the new patch applies exactly (no fuzz) and gives the file its Result line names",
              exact and applied == new_patched and patch_result(new_patch) == sha(applied)[:2] and patch_made_for(new_patch)[:2] == sha(moved)[:2])
        check("regen: with lines added, E1's line numbers moved by 5 and E2's by 8", nm is not None and om is not None
              and [int(x) - int(y) for x, y in zip(nm.groups(), om.groups())] == [5, 5, 5, 8, 8, 5, 5, 5, 5], nm and om and (nm.groups(), om.groups()))
        check("regen: the regenerated hunks add exactly the committed blocks", patch_hunks_of(new_patch) == patch_hunks_of(patch))
        # The command itself, in a scratch copy holding the moved TycoonCore.lua: it rewrites the patch and only the doc's row
        with tempfile.TemporaryDirectory() as tmp:
            for name in ("tools/world_test.py", "docs/world_pass_integration.patch", "docs/STUDIO_SYNC_WORLD.md"):
                os.makedirs(os.path.dirname(os.path.join(tmp, name)), exist_ok=True)
                shutil.copy(os.path.join(ROOT, name), os.path.join(tmp, name))
            with open(os.path.join(tmp, "TycoonCore.lua"), "w", encoding="utf-8", newline="\n") as f:
                f.write(moved)
            ran = subprocess.run([sys.executable, os.path.join(tmp, "tools", "world_test.py"), "--regen-patch", "test"], cwd=tmp, capture_output=True, text=True)
            with open(os.path.join(tmp, "docs", "world_pass_integration.patch"), encoding="utf-8") as f:
                written = f.read()
            with open(os.path.join(tmp, "docs", "STUDIO_SYNC_WORLD.md"), encoding="utf-8") as f:
                doc_after = f.read()
        want_row = sync_row("test", *sha(new_patched))
        check("regen: the command (--regen-patch) writes that patch and changes only the TycoonCore row of STUDIO_SYNC_WORLD.md",
              ran.returncode == 0 and written == new_patch and SYNC_ROW.sub(lambda _: "ROW", doc_after) == SYNC_ROW.sub(lambda _: "ROW", doc)
              and want_row in doc_after and sha(new_patched)[0] in ran.stdout, ran.stdout.strip()[-200:] or ran.stderr.strip()[-200:])
    broken = base.replace(E1_ANCHOR, "\tPlotVisuals, PlotArt = nil, nil -- off\nend\n\n", 1)
    try:
        regen_patch(broken, "test")
        refused = None
    except ValueError as e:
        refused = str(e)
    check("regen: without its anchor (the plot visuals block changed) it refuses and names the anchor", refused is not None and "E1" in refused, refused)
    return passed, failed


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


# The lines of TycoonCore.lua the two blocks are placed by (block_order): if one is missing, the patch needs regenerating
LANDMARKS = ("PlotVisuals, PlotArt = nil, nil", "local UPGRADES = {", "local function plotCenter(", "local function onPlayerAdded(",
             "Players.PlayerAdded:Connect(onPlayerAdded)", "WorldVisuals.build(")


def block_order(text, hunks=None):
    """Problems with where the two blocks sit in a patched TycoonCore (empty = both in place, in order). Never raises:
    a missing marker or landmark line is a problem like any other. hunks: the blocks (default: the patch's)."""
    problems = []
    missing = [m for m in PATCH_MARKERS if m not in text]
    if missing:
        return ["a marker line is missing: %s" % missing]
    gone = [m for m in LANDMARKS if m not in text]
    if gone:
        return ["a line the blocks are placed by is missing from TycoonCore.lua: %s" % gone]
    e1, e2 = text.index(PATCH_MARKERS[0]), text.index(PATCH_MARKERS[1])
    if not (text.index("PlotVisuals, PlotArt = nil, nil") < e1 < text.index("local UPGRADES = {")):
        problems.append("the require block is not between the plot visuals block and UPGRADES")
    if not (text.index("local function plotCenter(") < text.index("local function onPlayerAdded(") < e2
            < text.index("Players.PlayerAdded:Connect(onPlayerAdded)")):
        problems.append("the build block is not after onPlayerAdded and before Players.PlayerAdded:Connect")
    # the patch's own build call, after its marker (lobby L4's ring hook has a build call of its own, earlier in the file)
    if not (text.find("WorldVisuals.build(", e2) > e2 and text.count(PATCH_MARKERS[0]) == 1 and text.count(PATCH_MARKERS[1]) == 1):
        problems.append("a block is there twice, or the build call is outside its block")
    hunks = hunks if hunks is not None else patch_hunks()
    if len(hunks) == 2 and E1_ANCHOR + hunks[0] + "\n" not in text:
        problems.append("the require block is not right after the plot visuals block")
    if len(hunks) == 2 and "\nend\n" + hunks[1] + "\n" + E2_ANCHOR[1:] not in text:
        problems.append("the build block is not right between the end of onPlayerAdded and Players.PlayerAdded:Connect")
    return problems


def patch_checks(how, patched):
    """Source checks on the patch itself and on the patched TycoonCore (applied in memory, or merged), and the
    --strict-patch check (without the flag, what it would find is a NOTE)."""
    passed, failed = 0, 0

    def check(name, cond, extra=None):
        nonlocal passed, failed
        if cond:
            passed += 1
        else:
            failed += 1
            print("FAIL: " + name + (" -- " + str(extra) if extra else ""))

    if how != "nogit":
        check("integration patch: it applies to this worktree's TycoonCore.lua (exactly or with fuzz), or is already merged in it -- " + STALE
              + " (python3 tools/world_test.py --regen-patch)", how in ("applied", "merged"), how)
    if how == "merged":
        current = read("TycoonCore.lua")
        missing = [i + 1 for i, block in enumerate(patch_hunks()) if block not in current]
        check("integration patch: merged: TycoonCore.lua holds both blocks exactly as the patch adds them -- " + STALE, missing == [], missing)
    if patched is not None:
        order = block_order(patched)
        check("integration patch: both marker lines are in TycoonCore, once each, in the right places and order -- " + STALE, order == [], order[:1])
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
    if how in ("applied", "merged"):
        problems = strict_problems(read("TycoonCore.lua"), patch, read("docs/STUDIO_SYNC_WORLD.md"))
        if "--strict-patch" in sys.argv:
            check(STRICT, problems == [], problems[:3])
        elif problems:
            print("NOTE: the integration patch is not exact for this TycoonCore.lua (fine until merge time; --strict-patch fails here; "
                  "regenerate it with --regen-patch on the branch that claims TycoonCore): " + "; ".join(problems[:3]))
    return passed, failed


def guarded(what, fn, *args):
    """Runs one step of the patch checks. If it raises (a TycoonCore.lua the step cannot read), the error is the named
    check "patch needs regenerating", never a crash: returns (0, 1) for (passed, failed) then."""
    try:
        return fn(*args)
    except Exception as e:  # noqa: BLE001 -- every error of a step is reported by name
        print("FAIL: integration patch: the %s ran to the end -- %s (%s: %s)" % (what, STALE, type(e).__name__, e))
        return 0, 1


def run_blocks(luau, patched):
    result = run_luau(luau, integration_source(patched))
    print("Integration patch blocks run in the fake: " + (result.stdout.strip() or result.stderr.strip()))
    m = re.search(r"^(\d+) passed, (\d+) failed$", result.stdout, re.M)
    if not m:
        print("FAIL: integration patch: the blocks in the fake ran to the end -- " + STALE)
    return (int(m.group(1)), int(m.group(2))) if m else (0, 1)


def patch_section(luau, top=False):
    """Everything about the integration patch: how it applies, its two blocks run in the fake, its source checks and
    the regeneration procedure. Every failure is a named FAIL line; nothing in it can stop the test with an error.
    Returns (passed, failed)."""
    passed = failed = 0
    try:
        how, patched = integration_state()
    except Exception as e:  # noqa: BLE001
        print("FAIL: integration patch: the patch state ran to the end -- %s (%s: %s)" % (STALE, type(e).__name__, e))
        return 0, 1
    if how == "nogit":
        print("note: git is not installed, so the integration patch could not be applied and its blocks are not run")
    elif patched is None:
        print("note: the integration patch does not apply to this TycoonCore.lua, so its blocks are not run (" + STALE + ")")
    else:
        got = guarded("blocks in the fake", run_blocks, luau, patched)
        passed, failed = passed + got[0], failed + got[1]
    got = guarded("patch source checks", patch_checks, how, patched)
    print("Integration patch source checks: %d passed, %d failed" % got)
    passed, failed = passed + got[0], failed + got[1]
    got = guarded("regeneration checks", regen_checks)
    print("Integration patch regeneration (--regen-patch): %d passed, %d failed" % got)
    passed, failed = passed + got[0], failed + got[1]
    if top:
        got = guarded("--strict-patch scenarios", mode_checks, luau)
        print("Integration patch, the default run and --strict-patch on 6 scenarios: %d passed, %d failed" % got)
        passed, failed = passed + got[0], failed + got[1]
    if "--integration" in sys.argv and patched is not None:
        print("Integration: both test suites on a scratch copy with the patch applied:")
        if not integration_suites(luau):
            failed += 1
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
        with open(os.path.join(tmp, "TycoonCore.lua"), "w", encoding="utf-8", newline="\n") as f:
            f.write(patched_tycoon())
        env = dict(os.environ, LUAU=luau)
        ok = True
        for script in ("tools/daily_test.py", "tools/world_test.py"):
            result = subprocess.run([sys.executable, os.path.join(tmp, script)], cwd=tmp, capture_output=True, text=True, env=env)
            bad = [l for l in result.stdout.split("\n") if "FAIL" in l or (" failed" in l and " 0 failed" not in l)]
            print("  with the patch applied, %s: %s" % (script, "all pass" if not bad and result.returncode == 0 else "FAILS " + "; ".join(bad[:3])))
            ok = ok and not bad
        return ok


def static_checks():
    """Source checks on the new files: looks only, pure data, no services, no randomness, no assets, no emoji, no odds words."""
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
    check("WorldVisuals.lua sets every look part's CanCollide, CanTouch and CanQuery to false in one place, and only the Solid group's boxes to collide",
          vis.count("part.CanCollide = false") == 1 and vis.count("part.CanTouch = false") == 1 and vis.count("part.CanQuery = false") == 1
          and vis.count("CanCollide = true") == 1 and vis.count("box.CanCollide = true") == 1)

    return passed, failed


def review_checks():
    """Optional (--review), for reviewing this branch before it is merged: against the merge-base with origin/main (or
    main), only CONTRIBUTING.md's Ownership rows and the branch's own new files changed, and tools/daily_test.py is
    untouched. Not part of the permanent run: once the branch is merged, the merge-base is main itself."""
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
    diff = git("diff", "-U0", base, "--", "CONTRIBUTING.md").stdout
    edits = [l for l in diff.split("\n") if l[:1] in ("+", "-") and not l.startswith(("+++", "---"))]
    check("review: CONTRIBUTING.md: only rows of the Ownership table change (the claims)", all(l[1:].startswith("| ") for l in edits),
          [l for l in edits if not l[1:].startswith("| ")][:2])
    check("review: tools/daily_test.py (other branches own it) is untouched", git("diff", "--quiet", base, "--", "tools/daily_test.py").returncode == 0)
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
    ("the lawns back to SmoothPlastic (the Materials table ignored)", V, 'M.ground or "SmoothPlastic"', '"SmoothPlastic"', "materials: a built path slab"),
    ("the hills back to SmoothPlastic", V, 'Enum.Material[M.hill or "SmoothPlastic"]', 'Enum.Material.SmoothPlastic', "materials: a built path slab"),
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
    ("the parts budget is never looked at", V, "if #parts > budget then", "if false then", "negative budget: 668 parts"),
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
    ("a parts budget too small for the world", A, "Budget = { parts = 600, lights = 8, ringParts = 480 }", "Budget = { parts = 200, lights = 8, ringParts = 480 }", "default site: check budget"),
    ("a lights budget too small for the world", A, "Budget = { parts = 600, lights = 8, ringParts = 480 }", "Budget = { parts = 600, lights = 5, ringParts = 480 }", "default site: check budget"),
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


# Group C: the command-bar blocks of docs/STUDIO_SYNC_WORLD.md (review item 3). The block is broken in a copy of the
# doc; the program that runs it (the world preview program, or the hash block's) must fail the named check.
D = "docs/STUDIO_SYNC_WORLD.md"
MUTANTS_C = [
    ("the world preview lists Terrain as a clash", D, ' and not d:IsA("Terrain") and not d:IsDescendantOf(folder) then', " and not d:IsDescendantOf(folder) then",
     "preview: Workspace.Terrain is never listed as a clash"),
    ("the hash block refuses a newline Studio added", D, ' or (string.sub(source, -2) == "\\n\\n" and matches(string.sub(source, 1, -2)))', "",
     "hash block: a script with one newline added at the end prints OK"),
    ("the hash block refuses a newline Studio dropped", D, 'matches(source) or matches(source .. "\\n") or', "matches(source) or",
     "hash block: a script whose last newline Studio dropped prints OK"),
    ("the cleanup block deletes every PREVIEW_ object at the top level", D,
     '\t\tif known(d) then\n\t\t\ttable.insert(removed, d:GetFullName())', '\t\tif string.sub(d.Name, 1, 8) == "PREVIEW_" then\n\t\t\ttable.insert(removed, d:GetFullName())',
     "cleanup block: an unrelated PREVIEW_X"),
    ("the cleanup block looks for the three names at any depth", D,
     'for _, place in ipairs({ workspace, StarterGui }) do\n\tfor _, d in ipairs(place:GetChildren()) do\n\t\tif known(d) then',
     'for _, place in ipairs({ workspace, StarterGui }) do\n\tfor _, d in ipairs(place:GetDescendants()) do\n\t\tif d.Name == "PREVIEW_STAGES" or d.Name == "PREVIEW_WORLD" or d.Name == "PREVIEW_ICONS" then',
     "cleanup block: an unrelated PREVIEW_X"),
    ("the cleanup block forgets PREVIEW_STAGES", D,
     '\treturn (d.Parent == workspace and (d.Name == "PREVIEW_STAGES" or d.Name == "PREVIEW_WORLD"))\n\t\tor (d.Parent == StarterGui and d.Name == "PREVIEW_ICONS")\nend\nlocal removed',
     '\treturn (d.Parent == workspace and d.Name == "PREVIEW_WORLD")\n\t\tor (d.Parent == StarterGui and d.Name == "PREVIEW_ICONS")\nend\nlocal removed',
     "cleanup block: it removes exactly the three known previews"),
    ("the cleanup block reports nothing unknown", D, '\t\t\tprint("unknown PREVIEW_ object: " .. d:GetFullName() .. ", delete it by hand")\n', "",
     "cleanup block: each unknown PREVIEW_ object is reported"),
    ("the cleanup block's report only looks at the top level", D,
     'for _, place in ipairs({ workspace, StarterGui }) do\n\tfor _, d in ipairs(place:GetDescendants()) do\n\t\tif string.sub(d.Name, 1, 8) == "PREVIEW_" then\n\t\t\ttable.insert(unknown,',
     'for _, place in ipairs({ workspace, StarterGui }) do\n\tfor _, d in ipairs(place:GetChildren()) do\n\t\tif string.sub(d.Name, 1, 8) == "PREVIEW_" then\n\t\t\ttable.insert(unknown,',
     "cleanup block: each unknown PREVIEW_ object is reported"),
    ("the cleanup block says OK with unknown objects left", D, 'print(#unknown == 0 and "OK no PREVIEW_ object is left', 'print(true and "OK no PREVIEW_ object is left',
     "cleanup block: with unknown PREVIEW_ objects left it ends with FAIL"),
    ("the check block forgets StarterGui", D, 'for _, place in ipairs({ workspace, StarterGui }) do\n\tfor _, d in ipairs(place:GetDescendants()) do\n\t\tif string.sub(d.Name, 1, 8) == "PREVIEW_" then\n\t\t\ttable.insert(found,',
     'for _, place in ipairs({ workspace }) do\n\tfor _, d in ipairs(place:GetDescendants()) do\n\t\tif string.sub(d.Name, 1, 8) == "PREVIEW_" then\n\t\t\ttable.insert(found,',
     "check block: with previews there it prints FAIL and every PREVIEW_ object"),
    ("the check block lists only the unknown ones", D, '\t\tif string.sub(d.Name, 1, 8) == "PREVIEW_" then\n\t\t\ttable.insert(found,',
     '\t\tif string.sub(d.Name, 1, 8) == "PREVIEW_" and not known(d) then\n\t\t\ttable.insert(found,',
     "check block: with previews there it prints FAIL and every PREVIEW_ object"),
    ("the check block calls a known name anywhere known", D, '\t\tif (d.Parent == workspace and (d.Name == "PREVIEW_STAGES" or d.Name == "PREVIEW_WORLD"))\n\t\t\tor (d.Parent == StarterGui and d.Name == "PREVIEW_ICONS") then',
     '\t\tif d.Name == "PREVIEW_STAGES" or d.Name == "PREVIEW_WORLD" or d.Name == "PREVIEW_ICONS" then',
     "check block: with previews there it prints FAIL and every PREVIEW_ object"),
]


# Group D: the patch regeneration (review item 5). This test file itself is changed in a scratch copy (with the
# TycoonCore.lua, the patch and the doc); its regen_checks() must fail the named check.
T = "tools/world_test.py"
MUTANTS_D = [
    ("the preamble names E2's line one too far", T, "e2_before=e2_after - 1", "e2_before=e2_after", "regen: every line number in the regenerated preamble"),
    ("E2 put one character early", T, "    j = text.index(E2_ANCHOR) + 1\n", "    j = text.index(E2_ANCHOR)\n", "regen: the regenerated patch applies exactly to this TycoonCore.lua"),
    ("the Result line hashes the unpatched file", T, "    res_sha, res_size = sha(patched)\n    preamble", "    res_sha, res_size = sha(base)\n    preamble",
     "regen: the regenerated Made for and Result lines"),
    ("the command forgets the doc's row", T, "        f.write(SYNC_ROW.sub(lambda _: sync_row(label, res_sha, res_size), doc, count=1))", "        f.write(doc)",
     "regen: the command (--regen-patch)"),
    ("plotCenter's end looked up from the top", T, 'pc0=pc0, pc1=line_of(base, pc0, "end"))', 'pc0=pc0, pc1=line_of(base, 1, "end"))',
     "regen: every line number in the regenerated preamble"),
    ("a missing anchor is not refused", T, "        if base.count(anchor) != 1:\n            raise ValueError", "        if False:\n            raise ValueError",
     "regen: without its anchor"),
]


# Group E: TycoonCore.lua changes the patch must notice (review 2, item 1). TycoonCore.lua is changed in a scratch
# copy (with the patch, the doc, this file and the two world modules); patch_section() there must run to the end and
# fail the named check, which says "patch needs regenerating". Never a crash.
TC = "TycoonCore.lua"
HOOK = "Players.PlayerAdded:Connect(onPlayerAdded)\n"
MUTANTS_E = [
    ("the plot visuals block's last line changed", TC, "\tPlotVisuals, PlotArt = nil, nil\nend\n", "\tPlotArt, PlotVisuals = nil, nil\nend\n",
     "integration patch: both marker lines are in TycoonCore, once each, in the right places and order -- " + STALE),
    ("E1's anchor line removed", TC, "\tPlotVisuals, PlotArt = nil, nil\nend\n", "end\n",
     "integration patch: both marker lines are in TycoonCore, once each, in the right places and order -- " + STALE),
    # stale with the patch not merged; with it merged, the build block is no longer right before the hook
    ("the PlayerAdded hook moved below the PlayerRemoving handler", TC, HOOK + "-- Players already in the server",
     "-- Players already in the server", ("integration patch: it applies to this worktree's TycoonCore.lua",
                                          "integration patch: both marker lines are in TycoonCore, once each, in the right places and order -- " + STALE)),
]


def tycoon_mutation(text, old, new):
    """apply_mutation for group E; the hook mutant also puts the removed hook back further down."""
    changed = apply_mutation(text, old, new, TC)
    if old.startswith(HOOK):
        anchor = "Players.PlayerRemoving:Connect(function(player)"
        changed = apply_mutation(changed, anchor, HOOK + "\n" + anchor, TC)
    return changed


def scratch_copy(tmp, files):
    """Copies the files patch_section() reads into tmp; files: { name: text or None (copied as it is) }."""
    for name in ("TycoonCore.lua", "WorldArt.lua", "WorldVisuals.lua", "docs/world_pass_integration.patch", "docs/STUDIO_SYNC_WORLD.md", T):
        target = os.path.join(tmp, name)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        if files.get(name) is None:
            shutil.copy(os.path.join(ROOT, name), target)
        else:
            with open(target, "w", encoding="utf-8", newline="\n") as f:
                f.write(files[name])


def run_patch_section(luau, tmp, args=()):
    """patch_section() of the world_test.py in tmp, in its own process: (finished, its stdout)."""
    code = ("import sys; sys.argv = ['x'] + %r; sys.path.insert(0, 'tools'); import world_test; print('skip: %%s' %% world_test.patch_mutants_skip()); "
            "print(world_test.patch_section(%r))" % (list(args), luau))
    ran = subprocess.run([sys.executable, "-c", code], cwd=tmp, capture_output=True, text=True)
    finished = ran.returncode == 0 and re.search(r"^\(\d+, \d+\)$", ran.stdout, re.M) is not None
    return finished, ran.stdout + ("" if finished else ran.stderr)


# Group F: --strict-patch, the default run's NOTE and the skip of groups D and E (review 2, item 2). This file is
# changed in a scratch copy; its mode_checks() must run to the end and fail the named check.
MUTANTS_F = [
    ("an offset counts as exact", T, 'else ("offset" if re.search(', 'else ("exact" if re.search(', "patch modes: offset, --strict-patch: the FAIL says why"),
    ("fuzz counts as exact", T, 'how = "fuzz" if extra or "Context reduced" in said else', 'how = "exact" if extra or "Context reduced" in said else',
     "patch modes: fuzz, --strict-patch: the FAIL says why"),
    ("--strict-patch only prints the NOTE", T, '        if "--strict-patch" in sys.argv:\n            check(STRICT', '        if False:\n            check(STRICT',
     "patch modes: offset, --strict-patch: it fails the named check"),
    ("the default run fails on an offset", T, '        if "--strict-patch" in sys.argv:\n            check(STRICT', '        if True:\n            check(STRICT',
     "patch modes: offset, default: no check fails"),
    ("the default run says nothing about an offset", T, '        elif problems:\n            print("NOTE: the integration patch', '        elif False:\n            print("NOTE: the integration patch',
     "patch modes: offset, default: it passes with a NOTE"),
    ("the STUDIO_SYNC row is not compared", T, "    if row is None or row.group(0) != sync_row(label, *want_result):", "    if False:",
     "patch modes: row, --strict-patch: it fails the named check"),
    ("the Made for line is not compared", T, "    if made is None or made[:2] != want_made:", "    if False:",
     "patch modes: hashes, --strict-patch: the FAIL says why"),
    ("groups D and E run on a stale patch", T, '    if how == "stale":\n        return "the integration patch does not apply', '    if False:\n        return "the integration patch does not apply',
     "patch modes: stale, default: groups D and E are skipped"),
]


def run_mode_mutants(luau, mutants, group):
    """Group F: each mutant of this file runs mode_checks() in a scratch copy; caught only by its named FAIL line."""
    from concurrent.futures import ThreadPoolExecutor
    own = read(T)

    def one(mutant):
        label, _, old, new, expected = mutant
        with tempfile.TemporaryDirectory() as tmp:
            scratch_copy(tmp, {T: apply_mutation(own, old, new, T)})
            code = "import sys; sys.argv = ['x']; sys.path.insert(0, 'tools'); import world_test; print(world_test.mode_checks(%r))" % luau
            ran = subprocess.run([sys.executable, "-c", code], cwd=tmp, capture_output=True, text=True)
        finished = ran.returncode == 0 and re.search(r"^\(\d+, \d+\)$", ran.stdout, re.M) is not None
        named = any(line.startswith("FAIL: " + expected) for line in ran.stdout.split("\n"))
        if finished and named:
            return None
        why = ("it crashed: " + (ran.stderr.strip().split("\n")[-1] if ran.stderr.strip() else "no summary")) if not finished else "the check '%s' did not fail" % expected
        return "FAIL: mutation %s, %s: not caught by its named check (%s)" % (group, label, why)

    with ThreadPoolExecutor(max_workers=2) as pool:
        problems = [o for o in pool.map(one, mutants) if o]
    return len(mutants) - len(problems), problems


def patch_mutants_skip():
    """Why groups D and E cannot run on this TycoonCore.lua (a note), or None. Both need the committed patch to apply
    (or to be merged): on a stale patch the checks they must trip are not run, so they would be reported as not
    caught next to the real failure ("patch needs regenerating", above)."""
    how = integration_state()[0]
    if how == "stale":
        return "the integration patch does not apply to this TycoonCore.lua (" + STALE + ", see the FAIL above)"
    if how == "nogit":
        return "git is not installed"
    return None


def mode_scenarios():
    """The --strict-patch scenarios, made from this worktree's TycoonCore.lua (without the patch) and a patch
    regenerated for it: { name: (TycoonCore.lua, patch, STUDIO_SYNC_WORLD.md) }."""
    current = read(TC)
    base = unpatched_tycoon(current) if any(m in current for m in PATCH_MARKERS) else current
    patch, patched = regen_patch(base, "test")
    doc = SYNC_ROW.sub(lambda _: sync_row("test", *sha(patched)), read(D), count=1)
    h1, h2 = (int(n) for n in re.findall(r"^@@ -(\d+),", patch, re.M))
    lines = base.split("\n")

    def changed(index):
        out = list(lines)
        out[index] += " -- changed"
        return "\n".join(out)
    other_row = SYNC_ROW.sub(lambda _: sync_row("other", *sha(patched)), doc, count=1)
    return {
        "exact": (base, patch, doc),
        "offset": ("-- a line added at the top\n" + base, patch, doc),
        "fuzz": (changed(h2 - 1), patch, doc),          # hunk 2's outermost context line: git apply -C1 drops it
        "hashes": (changed(0), patch, doc),              # line 1, far from both hunks: it applies exactly, the hashes are stale
        "row": (base, patch, other_row),                 # the doc's TycoonCore row names another base
        "stale": (changed(h1 - 1 + 3), patch, doc),      # hunk 1's innermost context line: it does not apply at all
    }


# What each scenario must give: (run with --strict-patch, the FAIL that must print or None, the text in it or in
# the NOTE, whether a NOTE must print, whether groups D and E are skipped)
MODE_EXPECT = [
    ("exact", False, None, None, False, False),
    ("exact", True, None, None, False, False),
    ("offset", False, None, "an offset", True, False),
    ("offset", True, STRICT, "an offset", False, False),
    ("fuzz", False, None, "fuzz", True, False),
    ("fuzz", True, STRICT, "fuzz", False, False),
    ("hashes", False, None, "Made for", True, False),
    ("hashes", True, STRICT, "Made for", False, False),
    ("row", False, "regen: STUDIO_SYNC_WORLD.md's TycoonCore row", None, True, False),
    ("row", True, STRICT, "STUDIO_SYNC doc", False, False),
    ("stale", False, "integration patch: it applies to this worktree's TycoonCore.lua", None, False, True),
    ("stale", True, "integration patch: it applies to this worktree's TycoonCore.lua", None, False, True),
]


def mode_checks(luau):
    """--strict-patch and the default run, tested: each scenario's TycoonCore.lua, patch and doc in a scratch copy,
    patch_section() run without and with --strict-patch. Returns (passed, failed)."""
    from concurrent.futures import ThreadPoolExecutor
    passed, failed = 0, 0

    def check(name, cond, extra=None):
        nonlocal passed, failed
        if cond:
            passed += 1
        else:
            failed += 1
            print("FAIL: " + name + (" -- " + str(extra) if extra else ""))

    try:
        scenarios = mode_scenarios()
    except ValueError as e:
        print("note: this TycoonCore.lua cannot be regenerated (%s), so the --strict-patch scenarios are not run" % e)
        return passed, failed

    def one(case):
        name, strict = case[0], case[1]
        tycoon, patch, doc = scenarios[name]
        with tempfile.TemporaryDirectory() as tmp:
            scratch_copy(tmp, {TC: tycoon, "docs/world_pass_integration.patch": patch, D: doc})
            return run_patch_section(luau, tmp, ["--strict-patch"] if strict else [])

    with ThreadPoolExecutor(max_workers=4) as pool:
        outcomes = list(pool.map(one, MODE_EXPECT))
    for (name, strict, fail, text, note, skipped), (finished, out) in zip(MODE_EXPECT, outcomes):
        mode = "--strict-patch" if strict else "default"
        lines = out.split("\n")
        fails = [l for l in lines if l.startswith("FAIL: ")]
        notes = [l for l in lines if l.startswith("NOTE: the integration patch")]
        where = "patch modes: %s, %s:" % (name, mode)
        check(where + " it runs to the end", finished, lines[-3:])
        if fail is None:
            check(where + " no check fails", fails == [], fails[:2])
        else:
            hit = [l for l in fails if l.startswith("FAIL: " + fail)]
            check(where + " it fails the named check", hit != [], fails[:2])
            if text:
                check(where + " the FAIL says why (%s)" % text, any(text in l for l in hit), hit[:1])
        if note and text and fail is None:
            check(where + " it passes with a NOTE that says why (%s)" % text, any(text in l for l in notes), notes[:1] or fails[:1])
        elif not note:
            check(where + " no NOTE", notes == [], notes[:1])
        check(where + (" groups D and E are skipped, saying so" if skipped else " groups D and E run"),
              any(l.startswith("skip: ") and (l != "skip: None") == skipped for l in lines))
    return passed, failed


def run_tycoon_mutants(luau, mutants, group):
    """Group E: each changed TycoonCore.lua runs patch_section() in a scratch copy; caught only by its named FAIL line
    (expected: one name, or a tuple of names when the state decides which check sees it)."""
    skip = patch_mutants_skip()
    if skip:
        print("note: group %s is not run: %s" % (group, skip))
        return 0, []
    problems = []
    for label, _, old, new, expected in mutants:
        with tempfile.TemporaryDirectory() as tmp:
            scratch_copy(tmp, {TC: tycoon_mutation(read(TC), old, new)})
            finished, out = run_patch_section(luau, tmp)
        names = expected if isinstance(expected, tuple) else (expected,)
        named = any(line.startswith("FAIL: " + name) for line in out.split("\n") for name in names)
        if not (finished and named):
            why = ("it crashed: " + out.strip().split("\n")[-1]) if not finished else "the check '%s' did not fail" % "' or '".join(names)
            problems.append("FAIL: mutation %s, %s: not caught by its named check (%s)" % (group, label, why))
    return len(mutants) - len(problems), problems


def run_regen_mutants(mutants, group):
    """Group D: each mutant of this file runs regen_checks() in a scratch copy; caught only by its named FAIL line."""
    own = read(T)
    problems = []
    skip = patch_mutants_skip()
    if skip:
        print("note: group %s is not run: %s" % (group, skip))
        return 0, []
    current = read("TycoonCore.lua")
    try:
        regen_patch(unpatched_tycoon(current) if any(m in current for m in PATCH_MARKERS) else current, "test")
    except ValueError:
        print("note: this TycoonCore.lua cannot be regenerated (an anchor changed: see the regen FAIL above), so group %s is not run" % group)
        return 0, []
    for label, _, old, new, expected in mutants:
        with tempfile.TemporaryDirectory() as tmp:
            for name in ("TycoonCore.lua", "docs/world_pass_integration.patch", "docs/STUDIO_SYNC_WORLD.md"):
                os.makedirs(os.path.dirname(os.path.join(tmp, name)) or tmp, exist_ok=True)
                shutil.copy(os.path.join(ROOT, name), os.path.join(tmp, name))
            os.makedirs(os.path.join(tmp, "tools"))
            with open(os.path.join(tmp, T), "w", encoding="utf-8", newline="\n") as f:
                f.write(apply_mutation(own, old, new, T))
            ran = subprocess.run([sys.executable, "-c", "import sys; sys.argv = ['x']; sys.path.insert(0, 'tools'); import world_test; print(world_test.regen_checks())"],
                                 cwd=tmp, capture_output=True, text=True)
        finished = ran.returncode == 0 and re.search(r"^\(\d+, \d+\)$", ran.stdout, re.M) is not None
        named = any(line.startswith("FAIL: " + expected) for line in ran.stdout.split("\n"))
        if not (finished and named):
            why = ("it crashed: " + (ran.stderr.strip().split("\n")[-1] if ran.stderr.strip() else "no summary")) if not finished else "the check '%s' did not fail" % expected
            problems.append("FAIL: mutation %s, %s: not caught by its named check (%s)" % (group, label, why))
    return len(mutants) - len(problems), problems


def run_mutants(luau, mutants, group):
    """Runs every mutant (four at a time). Returns how many were caught and a FAIL line for each one that was not."""
    from concurrent.futures import ThreadPoolExecutor
    art, vis = read("WorldArt.lua"), read("WorldVisuals.lua")
    doc = read(D) if os.path.exists(os.path.join(ROOT, D)) else ""

    def one(mutant):
        label, filename, old, new, expected = mutant
        if filename == D:
            changed = apply_mutation(doc, old, new, filename)
            source = hash_source(changed) if expected.startswith("hash block") else preview_source(changed)
        elif filename == "WorldArt.lua":
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


# --- Lobby L4: the ring around the plaza ------------------------------------------------------------------------------
RING_TESTS = r'''-- Tests: the ring around the plaza (lobby L4), from the real WorldArt, WorldVisuals and LobbyConfig ------------------------
local WorldArt = (function()
__WORLDART__
end)()
local WorldVisuals = (function()
__WORLDVISUALS__
end)()
local LobbyConfig = (function()
__LOBBYCONFIG__
end)()
local PB = __PBNUMBERS__
local function section(name, fn)
	local ok, err = pcall(fn)
	if not ok then check(name .. ": this part of the tests could not finish", false, err) end
end
local R, ring = WorldArt.Ring, LobbyConfig.Ring
local site, world

section("ring copied", function()
	check("ring copied: WorldArt.Ring.lot is PlotBuilding.Lot (82.6 x 86.6, 2.3 in front of the floor's front edge)",
		R.lot.half == PB.lotHalf and R.lot.front == PB.lotFront and R.lot.back == PB.lotBack)
	check("ring copied: the facade strip ends at PlotBuilding.OUTSIDE_TO and each walk starts at PlotBuilding.FRONT_OUT",
		R.outside.to == PB.outsideTo and R.frontLine == PB.frontOut)
	check("ring copied: the plaza's center is LobbyConfig.PlazaCenter", R.plaza.x == LobbyConfig.PlazaCenter.x and R.plaza.z == LobbyConfig.PlazaCenter.z)
	check("ring copied: one garage per slot (6, TycoonCore MAX_PLOTS)", #ring == 6 and #ring == WorldArt.Site.plotCount)
	check("ring copied: the moved SpawnLocation is on the plaza's center", R.spawn.position[1] == R.plaza.x and R.spawn.position[3] == R.plaza.z)
end)

section("ring lots", function()
	site = WorldVisuals.ringSite(WorldArt, ring)
	local lots = {}
	for i, p in ipairs(site.plots) do
		local x0, x1, z0, z1 = WorldVisuals.boxToWorld(p, -R.lot.half, R.lot.half, R.lot.back, R.lot.front)
		lots[i] = { x0, x1, z0, z1 }
	end
	local overlap, near, off, away, anchor = nil, nil, nil, nil, nil
	for i = 1, #lots do
		for j = i + 1, #lots do
			local a, b = lots[i], lots[j]
			local gx = math.max(b[1] - a[2], a[1] - b[2])
			local gz = math.max(b[3] - a[4], a[3] - b[4])
			if gx < 0 and gz < 0 then overlap = overlap or (i .. "/" .. j) end
			local dist = (gx > 0 and gz > 0) and math.sqrt(gx * gx + gz * gz) or math.max(gx, gz) -- the real distance (a corner: diagonal)
			if dist < 6 - 1e-9 then near = near or (i .. "/" .. j .. " " .. string.format("%.1f", dist)) end
		end
		local g = site.ground
		if lots[i][1] < g.x0 or lots[i][2] > g.x1 or lots[i][3] < g.z0 or lots[i][4] > g.z1 then off = off or i end
		-- the front (+Z of the garage's frame) points at the plaza's center, the way it is nearest to
		local p = site.plots[i]
		local fx, fz = WorldVisuals.toWorld(p, 0, 1)
		local dx, dz = fx - p.x, fz - p.z
		local cx, cz = R.plaza.x - p.x, R.plaza.z - p.z
		local best = math.max(math.abs(cx), math.abs(cz))
		if not (dx * cx + dz * cz > 0 and ((math.abs(cx) == best and dx ~= 0) or (math.abs(cz) == best and dz ~= 0))) then away = away or i end
		local ax, az = WorldVisuals.toWorld(p, 0, PB.floorHalf)
		if math.abs(math.max(math.abs(ax - R.plaza.x), math.abs(az - R.plaza.z)) - 95) > 1e-9 then anchor = anchor or i end
	end
	check("ring: no two lots overlap", overlap == nil, overlap)
	check("ring: every lot is 6 or more from the next (6.4 at the corners)", near == nil, near)
	check("ring: every lot is on the Baseplate", off == nil, off)
	check("ring: every garage faces the plaza (its front turned toward the plaza's center)", away == nil, away)
	check("ring: every floor's front-center is 95 studs from the plaza's center (the front line)", anchor == nil, anchor)
end)

section("ring world", function()
	site = site or WorldVisuals.ringSite(WorldArt, ring)
	world = WorldVisuals.build(nil, WorldArt, site)
	local problems = WorldVisuals.check(world, WorldArt, site)
	check("ring world: every named check passes (data, budget, flags, keepouts, floating, zfighting, baseplate, connected, palette, texts)", #problems == 0, problems[1])
	local parts, lights = 0, 0
	for _, d in ipairs(world:GetDescendants()) do
		if d:IsA("BasePart") then parts += 1 elseif d.ClassName == "PointLight" then lights += 1 end
	end
	check("ring world: at most " .. WorldArt.Budget.ringParts .. " parts (" .. parts .. ") and 6 lights (" .. lights .. ")", parts <= WorldArt.Budget.ringParts and lights <= 6)
	-- nothing taller than the paving in any garage's doorway lane (9 wide, from inside the floor to past the apron)
	local inLane = nil
	for i, p in ipairs(site.plots) do
		local x0, x1, z0, z1 = WorldVisuals.boxToWorld(p, -4.5, 4.5, 26, 40)
		for _, d in ipairs(world:GetDescendants()) do
			if d:IsA("BasePart") and d.Parent.Name ~= "Hills" then -- the far hills: huge spheres sunk in the ground, hundreds of studs away
				local b = WorldVisuals.boxOf(d.CFrame, d.Size)
				if b and b[1] < x1 - 0.01 and x0 < b[2] - 0.01 and b[5] < z1 - 0.01 and z0 < b[6] - 0.01 and b[4] > 0.25 then inLane = inLane or (d.Name .. " at garage " .. i) end
			end
		end
	end
	check("ring: no world part stands in a doorway lane (flat paving only)", inLane == nil, inLane)
	local signs = 0
	for i = 1, 6 do if world:FindFirstChild("GarageSign" .. i, true) then signs += 1 end end
	check("ring world: one number sign per garage, beside its walk", signs == 6)
	do -- a negative test: a ball dropped inside garage 1's lot must be reported by the keepouts check
		local p = site.plots[1]
		local bx, bz = WorldVisuals.toWorld(p, 0, -40)
		local ball = newInstance("Part")
		ball.Name = "StrayBall"
		ball.Shape = Enum.PartType.Ball
		ball.Size = vec(3, 3, 3)
		ball.CFrame = cf(bx, 1.5, bz)
		ball.Anchored, ball.CanCollide, ball.CanTouch, ball.CanQuery, ball.CastShadow = true, false, false, false, true
		ball.Parent = world:FindFirstChild("Decor")
		local found = false
		for _, r in ipairs(WorldVisuals.checks(world, WorldArt, site)) do
			if r.name == "keepouts" then for _, text in ipairs(r.problems) do if string.find(text, "lot zone Lot1", 1, true) then found = true end end end
		end
		check("ring world: a part dropped inside a garage's lot is reported (the lots are keep-outs)", found)
		ball.Parent = nil
	end
	check("ring world: the lounge, its door, the drop spot and the moved spawn pad are kept clear (the keepouts check)",
		(function() for _, r in ipairs(WorldVisuals.checks(world, WorldArt, site)) do if r.name == "keepouts" then return #r.problems == 0 end end return false end)())
end)

-- The plaza garden (world-ring-plaza): the paving, the beds, what stands where, the fountain, the benches
section("ring garden", function()
	site = site or WorldVisuals.ringSite(WorldArt, ring)
	world = world or WorldVisuals.build(nil, WorldArt, site)
	local cx, cz, H = R.plaza.x, R.plaza.z, R.plaza.half
	local function rectOf(part)
		local b = WorldVisuals.boxOf(part.CFrame, part.Size)
		return { name = part.Name, x0 = b[1], x1 = b[2], z0 = b[5], z1 = b[6], y0 = b[3], y1 = b[4] }
	end
	local paths, missing = {}, {}
	for _, part in ipairs(world:FindFirstChild("Paths"):GetChildren()) do paths[part.Name] = rectOf(part) end
	local WAYS = { "SpokeNorth", "SpokeNorthOuter", "SpokeSouth", "SpokeWest", "SpokeEast", "PromenadeNorth", "PromenadeSouth", "PromenadeWest", "PromenadeEast", "Forecourt" }
	for _, name in ipairs(WAYS) do if not paths[name] then table.insert(missing, name) end end
	for _, name in ipairs({ "PlazaSouth", "PlazaNorth", "PlazaWest", "PlazaEast", "FountainNode" }) do if not paths[name] then table.insert(missing, name) end end
	check("ring garden: the square, four spokes, the fountain's node, four promenade bands and the forecourt are paved", #missing == 0, missing[1])
	-- every walk ends on a promenade band (shares its whole width with the band's outer edge) and stays inside the plaza's verge
	local loose = nil
	for i = 1, 6 do
		local w = paths["Walk" .. i]
		local ok = false
		for _, band in ipairs({ "PromenadeNorth", "PromenadeSouth", "PromenadeWest", "PromenadeEast" }) do
			local b = paths[band]
			if w and b then
				local alongX = math.min(w.x1, b.x1) - math.max(w.x0, b.x0)
				local alongZ = math.min(w.z1, b.z1) - math.max(w.z0, b.z0)
				if (math.abs(w.x1 - b.x0) < 0.01 or math.abs(b.x1 - w.x0) < 0.01) and alongZ >= R.walkWidth - 0.01 then ok = true end
				if (math.abs(w.z1 - b.z0) < 0.01 or math.abs(b.z1 - w.z0) < 0.01) and alongX >= R.walkWidth - 0.01 then ok = true end
			end
		end
		if not ok then loose = loose or ("Walk" .. i) end
	end
	check("ring garden: every walk ends on the promenade, its whole width on the band's outer edge", loose == nil, loose)
	-- four beds, each with four kerbs, inside the promenade's inner edge and 4 or more from every path
	local ground = world:FindFirstChild("Ground")
	local beds, badBed, kerbs = 0, nil, 0
	for _, part in ipairs(ground and ground:GetChildren() or {}) do
		if string.sub(part.Name, 1, 3) == "Bed" then
			beds += 1
			local b = rectOf(part)
			local inner = H - R.promenade.inset - R.promenade.width
			if b.x0 < cx - inner or b.x1 > cx + inner or b.z0 < cz - inner or b.z1 > cz + inner then badBed = badBed or (part.Name .. " reaches the promenade") end
			for name, r in pairs(paths) do
				local gx = math.max(r.x0 - b.x1, b.x0 - r.x1)
				local gz = math.max(r.z0 - b.z1, b.z0 - r.z1)
				if math.max(gx, gz) < 4 - 1e-9 then badBed = badBed or (part.Name .. " is " .. string.format("%.1f", math.max(gx, gz)) .. " from " .. name) end
			end
		end
	end
	for _, part in ipairs(world:FindFirstChild("Kerbs"):GetChildren()) do if string.sub(part.Name, 1, 7) == "KerbBed" then kerbs += 1 end end
	check("ring garden: four lawn beds with four kerbs each (" .. beds .. " beds, " .. kerbs .. " kerbs)", beds == 4 and kerbs == 16)
	check("ring garden: every bed lies inside the promenade and 4 or more from every path (a grass verge)", beds == 4 and badBed == nil, badBed)
	-- nothing taller than the paving stands on a walking way: the spokes, the promenade, the walks and the forecourt (the
	-- arch's beam passes high over the south spoke; the square and the fountain's node carry their own furniture)
	local ways = {}
	for _, name in ipairs(WAYS) do if paths[name] then table.insert(ways, paths[name]) end end
	for i = 1, 6 do if paths["Walk" .. i] then table.insert(ways, paths["Walk" .. i]) end end
	local onWay = nil
	for _, d in ipairs(world:FindFirstChild("Decor"):GetDescendants()) do
		if d:IsA("BasePart") then
			local b = rectOf(d)
			if b.y1 > 0.25 and b.y0 < 7 then
				for _, w in ipairs(ways) do
					if b.x0 < w.x1 - 0.01 and w.x0 < b.x1 - 0.01 and b.z0 < w.z1 - 0.01 and w.z0 < b.z1 - 0.01 then
						onWay = onWay or (d.Parent.Name .. "." .. d.Name .. " on " .. w.name)
					end
				end
			end
		end
	end
	check("ring garden: no lamp, bench, sign, bush, planter, tree or fountain stands on a spoke, the promenade, a walk or the forecourt", onWay == nil, onWay)
	-- the fountain: every part of it on the node's paving
	local fountain, node, offNode, fparts = world:FindFirstChild("Fountain", true), paths.FountainNode, nil, 0
	for _, d in ipairs(fountain and fountain:GetChildren() or {}) do
		fparts += 1
		local b = rectOf(d)
		if not node or b.x0 < node.x0 or b.x1 > node.x1 or b.z0 < node.z0 or b.z1 > node.z1 then offNode = offNode or d.Name end
	end
	check("ring garden: the fountain stands on the north spoke's node, every part of it on the node's paving", fparts >= 4 and offNode == nil, offNode or fparts)
	-- the spokes: two lamps and two benches each; every bench faces the paving next to it (seat in front of its back)
	local count, facing = {}, nil
	for _, m in ipairs(world:FindFirstChild("Decor"):GetChildren()) do
		for _, kind in ipairs({ "SpokeLamp", "SpokeBench" }) do
			if string.sub(m.Name, 1, #kind) == kind then count[kind] = (count[kind] or 0) + 1 end
		end
		if string.sub(m.Name, 1, 10) == "SpokeBench" or string.sub(m.Name, 1, 10) == "PlazaBench" then
			local seat, back = m:FindFirstChild("BenchSeat"), m:FindFirstChild("BenchBack")
			local s, k = rectOf(seat), rectOf(back)
			local sx, sz = (s.x0 + s.x1) / 2, (s.z0 + s.z1) / 2
			local dx, dz = sx - (k.x0 + k.x1) / 2, sz - (k.z0 + k.z1) / 2
			-- 4 studs in front of the seat is paving (a spoke, the node or the square)
			local px, pz = sx + dx / math.max(math.abs(dx), math.abs(dz)) * 4, sz + dz / math.max(math.abs(dx), math.abs(dz)) * 4
			local paved = false
			for _, r in pairs(paths) do
				if px > r.x0 and px < r.x1 and pz > r.z0 and pz < r.z1 then paved = true end
			end
			if not paved then facing = facing or m.Name end
		end
	end
	check("ring garden: every spoke has two lamps and two benches (" .. tostring(count.SpokeLamp) .. " lamps, " .. tostring(count.SpokeBench) .. " benches)",
		count.SpokeLamp == 8 and count.SpokeBench == 8)
	check("ring garden: every bench on the plaza faces paving (4 studs in front of its seat is a spoke, the node or the square)", facing == nil, facing)
end)
print_real(string.format("%d passed, %d failed", passed, failed))
'''

RING_MUTANTS = [
    # (what, file, old, new, the start of the named check that must fail)
    ("two lots overlapping (garage 2 moved onto garage 1)", "LobbyConfig.lua", "{ x = -125, z = 220, turn = 90 }", "{ x = -125, z = 200, turn = 90 }", "ring: no two lots overlap"),
    ("a corner gap under 6 (garage 3 moved 3 studs toward garage 2 on both axes)", "LobbyConfig.lua", "{ x = -45, z = 300, turn = 180 }", "{ x = -48, z = 297, turn = 180 }", "ring: every lot is 6 or more"),
    ("a lot off the Baseplate (garage 6 at x 1000)", "LobbyConfig.lua", "{ x = 125, z = 130, turn = 270 }", "{ x = 1000, z = 130, turn = 270 }", "ring: every lot is on the Baseplate"),
    ("a garage facing away from the plaza", "LobbyConfig.lua", "{ x = -125, z = 130, turn = 90 }", "{ x = -125, z = 130, turn = 270 }", "ring: every garage faces the plaza"),
    ("a lamp standing in a doorway (the walk lamps at x 0)", "WorldArt.lua", "lamp = { x = -18, z = 37 }", "lamp = { x = 0, z = 37 }", "ring: no world part stands in a doorway lane"),
    ("the spawn pad covered (a bench on it)", "WorldArt.lua", "benches = { { -17, -9, 90 },", "benches = { { 0, 0, 0 }, { -17, -9, 90 },", "ring world: the lounge, its door"),
    ("the ring's lot smaller than PlotBuilding's", "WorldArt.lua", "lot = { half = 41.3, front = 32.3, back = -54.3, top = 120 },", "lot = { half = 36, front = 32.3, back = -54.3, top = 120 },", "ring copied: WorldArt.Ring.lot"),
    ("the walks start at the floor's edge, not the front wall", "WorldArt.lua", "frontLine = 32.2,", "frontLine = 30,", "ring copied: the facade strip"),
    ("a tree inside a lot (the gap trees moved)", "WorldArt.lua", "gapTrees = { { -140, 175 }, { 140, 175 } },", "gapTrees = { { -140, 160 }, { 140, 175 } },", "ring world: every named check passes"),
    ("the ring world over its budget (the ring budget lowered to 100)", "WorldArt.lua", "ringParts = 480", "ringParts = 100", "ring world: every named check passes"),
    # the plaza garden (world-ring-plaza)
    ("a bed reaching the spokes (bed from 2)", "WorldArt.lua", "bed = { from = 26, to = 72 },", "bed = { from = 2, to = 72 },", "ring garden: every bed lies inside the promenade"),
    ("a bed short of its kerbs (the east kerb left out)", "WorldVisuals.lua", '\t\trect(plan.kerbs, "KerbBed" .. name .. "East", bx1, bx1 + kw, bz0, bz1)\n', "", "ring garden: four lawn beds with four kerbs"),
    ("the spoke lamps and benches on the spoke's edge (no gap)", "WorldArt.lua", "benchGap = 3,", "benchGap = 0,", "ring garden: no lamp, bench, sign"),
    ("a garage's number sign back on the promenade (z 42)", "WorldArt.lua", "sign = { x = 18, z = 37 }", "sign = { x = 18, z = 42 }", "ring garden: no lamp, bench, sign"),
    ("the benches turned away from their spoke", "WorldVisuals.lua", "local fx, fz = -side * oz, side * ox", "local fx, fz = side * oz, -side * ox", "ring garden: every bench on the plaza faces paving"),
    ("the fountain moved off its node", "WorldVisuals.lua", 'item("Fountain", "Fountain", cx, cz + nd.z)', 'item("Fountain", "Fountain", cx + 12, cz + nd.z)', "ring garden: the fountain stands"),
    ("the walks stop at the plaza's edge (not on to the promenade)", "WorldVisuals.lua", "\t\tfar += R.promenade.inset\n", "", "ring garden: every walk ends on the promenade"),
    ("one spoke without its lamps", "WorldArt.lua", "spokeLamps = { { 30, 1 }, { 66, -1 } },", "spokeLamps = { { 30, 1 } },", "ring garden: every spoke has two lamps"),
    ("the zones forget the ring's lots (only the row's plots)", "WorldVisuals.lua", "\tif site.ring then\n\t\t-- The ring: each garage's whole lot", "\tif false then\n\t\t-- The ring: each garage's whole lot", "ring world: a part dropped inside a garage's lot"),
]


def pb_numbers():
    pb = read("PlotBuilding.lua")
    lot = re.search(r"PlotBuilding\.Lot = \{ half = ([\d.]+), front = ([\d.]+), back = (-?[\d.]+) \}", pb)
    out = re.search(r"PlotBuilding\.OUTSIDE_TO = ([\d.]+)", pb)
    front = re.search(r"PlotBuilding\.FRONT_OUT = ([\d.]+)", pb)
    if not (lot and out and front):
        return "{}"
    return "{ lotHalf = %s, lotFront = %s, lotBack = %s, outsideTo = %s, frontOut = %s, floorHalf = 30 }" % (lot.group(1), lot.group(2), lot.group(3), out.group(1), front.group(1))


def ring_source(texts=None):
    texts = texts or {}
    body = (RING_TESTS.replace("__WORLDART__", texts.get("WorldArt.lua", read("WorldArt.lua")))
            .replace("__WORLDVISUALS__", texts.get("WorldVisuals.lua", read("WorldVisuals.lua")))
            .replace("__LOBBYCONFIG__", texts.get("LobbyConfig.lua", read("LobbyConfig.lua"))).replace("__PBNUMBERS__", pb_numbers()))
    return PRELUDE + body


def ring_run(luau, texts=None):
    """(passed, failed names, crashed)"""
    result = run_luau(luau, ring_source(texts))
    names = [line[len("FAIL: "):].split(" -- ")[0] for line in result.stdout.splitlines() if line.startswith("FAIL: ")]
    m = re.search(r"^(\d+) passed, (\d+) failed$", result.stdout, re.M)
    return (int(m.group(1)) if m else 0), names, (result.returncode != 0 or not m), result


def ring_mutants(luau):
    caught, lines = 0, []
    for label, name, old, new, want in RING_MUTANTS:
        text = read(name)
        if text.count(old) != 1:
            lines.append("NOT CAUGHT (group R): %s -- not applied" % label)
            continue
        _, names, crashed, result = ring_run(luau, {name: text.replace(old, new)})
        hit = [n for n in names if n.startswith(want)]
        if hit:
            caught += 1
        else:
            lines.append("NOT CAUGHT (group R): %s -- no failing check starts with \"%s\" (failed: %s%s)" % (label, want, names[:3], ", crashed" if crashed else ""))
    return caught, lines


def main():
    if "--regen-patch" in sys.argv:
        return regen_command()
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
    if os.path.exists(os.path.join(ROOT, "docs", "STUDIO_SYNC_WORLD.md")) and "## (d) Hash check (command bar)" in read("docs/STUDIO_SYNC_WORLD.md"):
        result = run_luau(luau, hash_source())
        print("Hash block (docs/STUDIO_SYNC_WORLD.md) on the files at " + SYNC_HISTORY + ": " + (result.stdout.strip() or result.stderr.strip()))
        m = re.search(r"^(\d+) passed, (\d+) failed$", result.stdout, re.M)
        if not m or m.group(2) != "0":
            code = 1
        total += int(m.group(1)) if m else 0
        table_passed, table_failed = sync_table_checks()
        print("Studio sync table: %d passed, %d failed" % (table_passed, table_failed))
        total += table_passed
        if table_failed:
            code = 1
    if "--review" in sys.argv:
        review_passed, review_failed = review_checks()
        print("Review checks (--review, against the merge-base with main): %d passed, %d failed" % (review_passed, review_failed))
        total += review_passed
        if review_failed:
            code = 1
    if os.path.exists(os.path.join(ROOT, "docs", "world_pass_integration.patch")):
        patch_passed, patch_failed = patch_section(luau, top=True)
        total += patch_passed
        if patch_failed:
            code = 1
    ring_passed, ring_failed, ring_crashed, ring_result = ring_run(luau)
    for name in ring_failed:
        print("FAIL: " + name)
    if ring_crashed:
        print("FAIL: the ring tests crashed: " + (ring_result.stderr or ring_result.stdout)[-300:])
    print("The ring around the plaza (lobby L4): %d passed, %d failed" % (ring_passed, len(ring_failed)))
    total += ring_passed
    if ring_failed or ring_crashed:
        code = 1
    runs = caught = 0
    ring_caught, ring_lines = ring_mutants(luau)
    for line in ring_lines:
        print(line)
    print("World mutations, group R (the ring): %d of %d caught, each by its named check" % (ring_caught, len(RING_MUTANTS)))
    runs += len(RING_MUTANTS)
    caught += ring_caught
    if ring_caught != len(RING_MUTANTS):
        code = 1
    for group, mutants in (("A", MUTANTS_A), ("B", MUTANTS_B), ("C", MUTANTS_C), ("D", MUTANTS_D), ("E", MUTANTS_E), ("F", MUTANTS_F)):
        if group == "D":
            got, problems = run_regen_mutants(mutants, group)
        elif group == "E":
            got, problems = run_tycoon_mutants(luau, mutants, group)
        elif group == "F":
            got, problems = run_mode_mutants(luau, mutants, group)
        else:
            got, problems = run_mutants(luau, mutants, group)
        for line in problems:
            print(line)
        if problems:
            code = 1
        if group in ("D", "E") and got == 0 and not problems:
            continue  # not run (the note says why)
        runs += len(mutants)
        caught += got
        if mutants:
            print("World mutations, group %s: %d of %d caught, each by its named check" % (group, got, len(mutants)))
    print("world_test.py: %d checks passed, %d of %d mutation runs caught%s" % (total, caught, runs, "" if code == 0 else "  -- SOMETHING FAILED"))
    return code


if __name__ == "__main__":
    sys.exit(main())
