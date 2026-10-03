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

-- Signals (Connect, Disconnect, and fire() for the test)
local function newSignal()
	local s = { handlers = {} }
	function s.Connect(self, fn)
		local c = { fn = fn, connected = true }
		function c.Disconnect(self2) self2.connected = false end
		table.insert(self.handlers, c)
		return c
	end
	function s.fire(...) for _, c in ipairs(table.clone(s.handlers)) do if c.connected then c.fn(...) end end end
	return s
end

-- Instances with parents, children, attributes and DescendantAdded. WRITES counts every Transparency write.
local WRITES = 0
local IS_A = { Part = { BasePart = true }, PointLight = { Light = true } }
local Methods = {}
local Mt = {}
Mt.__index = function(t, k)
	if k == "Parent" then return rawget(t, "_parent") end
	local def = rawget(t, "_def")
	if def and def[k] ~= nil then return def[k] end
	if k == "DescendantAdded" then
		local s = rawget(t, "_descAdded")
		if not s then s = newSignal(); rawset(t, "_descAdded", s) end
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
		if v then
			table.insert(v._children, t)
			local a = v
			while a do
				local s = rawget(a, "_descAdded")
				if s then s.fire(t) end
				a = rawget(a, "_parent")
			end
		end
	else
		if k == "Transparency" then WRITES += 1 end
		local def = rawget(t, "_def")
		if def and def[k] ~= nil then def[k] = v else rawset(t, k, v) end
	end
end
local function newInstance(class)
	local i = setmetatable({ ClassName = class, Name = class, _children = {}, _attrs = {} }, Mt)
	if class == "Part" then
		rawset(i, "_def", { Anchored = false, CanCollide = true, CanTouch = true, CanQuery = true, CastShadow = true, Transparency = 0 })
	elseif class == "TextLabel" then rawset(i, "TextTransparency", 0)
	elseif class == "SurfaceGui" then rawset(i, "Enabled", true) end
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
"""

# The builder's world: CollectionService.AddTag is recorded (the builder tags the Model before it enters the game)
MODULE_GAME = r"""
local TAGGED = {}
local game = { GetService = function(_, name)
	if name == "CollectionService" then
		return { AddTag = function(_, inst, tag) TAGGED[inst] = tag end }
	end
	error("no service " .. tostring(name))
end }
"""

MATH_A = r"""local function inside(x, y, z, was) return M.isInside(b, x, y, z, was) end
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
do
	local function safe(...) local ok, r = pcall(M.isInside, b, ...) return ok and r == false end
	check("inside: text, nil or a table instead of a number is never inside (and never an error)", safe("5", fy + 3, cz) and safe(cx, nil, cz) and safe(cx, fy + 3, {}) and safe(nil, nil, nil))
end
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
"""

MATH_B = r"""-- 6. The pure fade maths ------------------------------------------------------------------------------------------------
local step = M.fadeStep
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
		local q = M.quantize(f, lv)
		if q ~= math.floor(q) or q < 0 or q > lv then bad = bad or string.format("%g %d -> %g", f, lv, q) end
	end
	check("quantize: always a whole step from 0 to the number of steps", bad == nil, bad)
	check("quantize: 0 is step 0, 1 is the last step, 0.5 is half, below 0 and above 1 clamp", M.quantize(0, 20) == 0 and M.quantize(1, 20) == 20 and M.quantize(0.5, 20) == 10
		and M.quantize(-3, 20) == 0 and M.quantize(3, 20) == 20 and M.quantize(0 / 0, 20) == 0)
	check("quantize: a step number of 0, NaN or below counts as one step (never divides by zero)", M.quantize(1, 0) == 1 and M.quantize(1, 0 / 0) == 1 and M.quantize(1, -4) == 1)
	check("quantize: a tiny fade is still step 0, so nothing is written for dust", M.quantize(0.0001, 20) == 0 and M.quantize(0.9999, 20) == 20)
end
do
	local t = M.transparencyAt
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

-- 5. The pure inside check (these tests also run on the copy inside BuildingClient, see CLIENT_TESTS) ------------------------------------
local M = PBV
local b = PBV.bounds(center, PlotArt, PlotBuilding)
local cx, cz = center.X, center.Z
local fy = center.Y + floorTop
__MATH_A__
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

__MATH_B__
-- 6b. The checks catch broken buildings (a check that can't fail proves nothing) --------------------------------------------------------------
do
	local room3 = fullRoom(3)
	local boxes3 = roomBoxes(room3)
	-- A copy of the data, changed by `fn`, built at stage 3 and checked against the real zones and the real room
	local function broken(fn)
		local copy = deepCopy(PlotBuilding)
		fn(copy)
		local ok, model = pcall(PBV.build, nil, center, PlotArt, copy, 3) -- a missing envelope number can't even be built
		if not ok then return { "build failed: " .. tostring(model) }, PBV.validate(copy) end
		return PBV.check(model, center, PlotArt, copy, { zones = zones, roomBoxes = boxes3 }), PBV.validate(copy)
	end
	local function spec(name, x, y, z, w, h, d, extra)
		local s = { name = name, shape = "Block", size = { w, h, d }, offset = { x, y, z }, color = { 200, 200, 200 }, material = "Concrete" }
		for k, v in pairs(extra or {}) do s[k] = v end
		return s
	end
	local clean = broken(function() end)
	check("a copy of the real data passes the same checks (the mutations below start from a clean building)", #clean == 0, clean[1])
	check("mutation: a 65th part is caught (budget 64)", anyMatch((broken(function(c) for i = 1, 65 - #c.Stages[3].fade - #c.Stages[3].static do table.insert(c.Stages[3].fade, spec("Fill" .. i, 30 + (i % 3), -0.5, 20 + i * 0.6, 0.4, 1, 0.4)) end end)), "parts (budget"))
	check("mutation: a 13th ground piece is caught (budget 12)", anyMatch((broken(function(c) for i = 1, 13 do table.insert(c.Stages[3].static, spec("Pebble" .. i, 20 + i, -0.5, 40, 0.5, 1, 0.5)) end end)), "ground pieces (budget"))
	check("mutation: a third SurfaceGui is caught (budget 2)", anyMatch((broken(function(c) for i = 1, 3 do table.insert(c.Stages[3].fade, spec("Label" .. i, 12 + i * 3, 6, 31.5, 2, 1, 0.1, { text = { value = "OFFICE", font = "FredokaOne", color = { 0, 0, 0 } } })) end end)), "SurfaceGuis (budget"))
	do
		local model = PBV.build(nil, center, PlotArt, PlotBuilding, 3)
		local one = partsOf(model:FindFirstChild("Fade"))[3]
		one.CanCollide = true
		check("mutation: a part with CanCollide on is caught", anyMatch(PBV.check(model, center, PlotArt, PlotBuilding), "CanCollide"))
		one.CanCollide = false
		one.CanQuery = true
		check("mutation: a part with CanQuery on (it would stop rays and the camera) is caught", anyMatch(PBV.check(model, center, PlotArt, PlotBuilding), "CanQuery"))
		one.CanQuery = false
		one.CanTouch = true
		check("mutation: a part with CanTouch on is caught", anyMatch(PBV.check(model, center, PlotArt, PlotBuilding), "CanTouch"))
		one.CanTouch = false
		one.CastShadow = true
		check("mutation: a part that casts a shadow is caught", anyMatch(PBV.check(model, center, PlotArt, PlotBuilding), "casts a shadow"))
		one.CastShadow = false
		one.Anchored = false
		check("mutation: an unanchored part is caught", anyMatch(PBV.check(model, center, PlotArt, PlotBuilding), "not anchored"))
		one.Anchored = true
		check("...and with everything put back the building is clean again", #PBV.check(model, center, PlotArt, PlotBuilding) == 0)
		local light = Instance.new("PointLight")
		light.Parent = one
		check("mutation: a PointLight in a building is caught", anyMatch(PBV.check(model, center, PlotArt, PlotBuilding), "lights"))
		light.Parent = nil
		local emitter = Instance.new("ParticleEmitter")
		emitter.Parent = one
		check("mutation: a particle emitter in a building is caught", anyMatch(PBV.check(model, center, PlotArt, PlotBuilding), "particle"))
		emitter.Parent = nil
		one.Parent = model -- not in Fade or Static
		check("mutation: a part outside the Fade and Static groups is caught", anyMatch(PBV.check(model, center, PlotArt, PlotBuilding), "not in Fade or Static"))
	end
	check("mutation: a block standing in the doorway is caught", anyMatch((broken(function(c) table.insert(c.Stages[3].fade, spec("Barrier", 0, 3, 32, 2, 5, 0.4)) table.insert(c.Stages[3].fade, spec("BarrierPost", 0, -0.5, 32, 1, 1, 1)) end)), "in the doorway"))
	check("mutation: a hanging door (nothing under 5.5 studs) is caught: a slat at head height", anyMatch((broken(function(c) table.insert(c.Stages[3].static, spec("LowBeam", 0, 3, 36, 8, 0.4, 0.4)) table.insert(c.Stages[3].static, spec("LowBeamLeg", 4, -0.5, 36, 0.4, 1, 0.4)) end)), "in the doorway"))
	check("mutation: a flat path in the doorway is fine (a mat on the ground is not a barrier)", #(broken(function(c) table.insert(c.Stages[3].static, spec("Mat2", 0, -0.88, 33, 3, 0.1, 3)) end)) == 0)
	check("mutation: a part inside a hire's zone is caught", anyMatch((broken(function(c) table.insert(c.Stages[3].fade, spec("InHire", -4.5, 3, -10, 1, 1, 1)) end)), "hire zone"))
	check("mutation: a part on the next-upgrade sign's zone is caught", anyMatch((broken(function(c) table.insert(c.Stages[3].fade, spec("OnSign", 0, 3, 24, 1, 1, 1)) end)), "sign zone BuySign"))
	check("mutation: a part in the walking lane is caught", anyMatch((broken(function(c) table.insert(c.Stages[3].fade, spec("InLane", 0, 3, 5, 1, 1, 1)) end)), "lane zone"))
	check("mutation: a part in an upgrade station's slot is caught", anyMatch((broken(function(c) table.insert(c.Stages[3].fade, spec("InSlot", -23, 3, 2, 1, 1, 1)) end)), "slot zone"))
	check("mutation: a part inside a room part (a prop) is caught", anyMatch((broken(function(c) table.insert(c.Stages[3].fade, spec("IntoRoom", 23, 6, 2, 6, 6, 3)) end)), "goes into the room part"))
	check("mutation: a floating part is caught", anyMatch((broken(function(c) table.insert(c.Stages[3].fade, spec("Floater", 20, 20, 36, 1, 1, 1)) end)), "Floater is floating"))
	check("mutation: a part far outside the building (past 40 studs) is caught", anyMatch((broken(function(c) table.insert(c.Stages[3].static, spec("TooFar", 0, -0.5, 45, 1, 1, 1)) end)), "outside the building's reach"))
	check("mutation: a part above 24 studs is caught", anyMatch((broken(function(c) table.insert(c.Stages[3].fade, spec("TooTall", 24, 22, -24, 1, 12, 1)) end)), "outside the building's reach"))
	check("mutation: a part below the ground is caught", anyMatch((broken(function(c) table.insert(c.Stages[3].static, spec("Buried", 20, -3, 36, 1, 1, 1)) end)), "outside the building's reach"))
	check("mutation: two faces on the same plane (z-fighting) are caught", anyMatch((broken(function(c)
		table.insert(c.Stages[3].fade, spec("PanelA", -40 + 56, 3, 31.5, 4, 4, 0.2))
		table.insert(c.Stages[3].fade, spec("PanelB", -40 + 57, 3, 31.5, 4, 4, 0.2))
	end)), "share a face"))
	check("mutation: a second roof slab on the first one's top plane (flicker) is caught", anyMatch((broken(function(c) table.insert(c.Stages[3].fade, spec("RoofTwin", 0, 14.45, 0, 65, 0.9, 65)) end)), "share a face"))
	check("mutation: no Roof in the Fade group is caught", anyMatch((broken(function(c) for _, s in ipairs(c.Stages[3].fade) do if s.name == "Roof" then s.name = "Lid" end end end)), "no part named Roof"))
	check("mutation: a material outside the list is caught (validate)", anyMatch(select(2, broken(function(c) c.Stages[3].fade[1].material = "Grass" end)), "material not allowed: Grass"))
	check("mutation: Neon on something that is not a light or a sign is caught (validate)", anyMatch(select(2, broken(function(c) c.Stages[3].fade[1].material = "Neon" end)), "Neon is only for lights"))
	check("mutation: a Wedge is caught (its orientation can't be checked without Studio) (validate)", anyMatch(select(2, broken(function(c) c.Stages[3].fade[1].shape = "Wedge" end)), "unknown shape"))
	check("mutation: a squashed Ball is caught (validate)", anyMatch(select(2, broken(function(c) table.insert(c.Stages[3].static, { name = "Squashed", shape = "Ball", size = { 1, 2, 1 }, offset = { 0, 0, 40 }, color = { 1, 2, 3 }, material = "Fabric" }) end)), "a Ball needs 3 equal sides"))
	check("mutation: odds text on a building (D9) is caught (validate)", anyMatch(select(2, broken(function(c) c.Stages[3].fade[#c.Stages[3].fade].text = { value = "LEGENDARY 5%", font = "GothamBold", color = { 0, 0, 0 } } end)), "text must be one of"))
	check("mutation: text that is not OFFICE, HQ or BUILD YOUR STARTUP is caught (validate)", anyMatch(select(2, broken(function(c) c.Stages[3].fade[2].text = { value = "FREE EGGS", font = "GothamBold", color = { 0, 0, 0 } } end)), "text must be one of"))
	check("mutation: a collidable or glowing building part in the data is caught (validate)", anyMatch(select(2, broken(function(c) c.Stages[3].fade[1].collide = true end)), "never collides, lights or emits")
		and anyMatch(select(2, broken(function(c) c.Stages[3].fade[1].light = { color = { 1, 1, 1 }, brightness = 1, range = 10 } end)), "never collides, lights or emits"))
	check("mutation: a color over 255 is caught (validate)", anyMatch(select(2, broken(function(c) c.Stages[3].fade[1].color = { 300, 0, 0 } end)), "color must be"))
	check("mutation: a size of 0 is caught (validate)", anyMatch(select(2, broken(function(c) c.Stages[3].fade[1].size = { 0, 1, 1 } end)), "size must be"))
	check("mutation: two parts with the same name are caught (validate)", anyMatch(select(2, broken(function(c) c.Stages[3].fade[2].name = c.Stages[3].fade[1].name end)), "two parts named"))
	check("mutation: a stage without its key is caught (validate)", anyMatch(select(2, broken(function(c) c.Stages[3].key = nil end)), "needs the key"))
	check("mutation: a missing envelope number is caught (validate)", anyMatch(select(2, broken(function(c) c.Envelope.inner = nil end)), "number missing"))
	-- Heights: the roof clears everything in every room
	local clearance = math.huge
	for i = 1, #PlotArt.Stages do
		for _, r in ipairs(roomBoxes(fullRoom(i))) do
			if not string.find(r.name, "Skyline", 1, true) then clearance = math.min(clearance, E.roofBottom - r.box[4]) end
		end
	end
	check("the roof clears the tallest part of every room (props included) by at least 1 stud (" .. string.format("%.2f", clearance) .. ")", clearance >= 1, clearance)
	-- The five buildings differ: nobody gets the same shell twice
	local seen, distinct = {}, true
	for i = 1, #PlotBuilding.Stages do
		local sig = {}
		for _, s in ipairs(PlotBuilding.Stages[i].fade) do table.insert(sig, s.name .. s.color[1] .. s.color[2] .. s.color[3] .. s.material) end
		local key = table.concat(sig, ";")
		if seen[key] then distinct = false end
		seen[key] = true
	end
	check("the five buildings are all different (each stage has its own look)", distinct)
	local roofColors = {}
	for i = 1, #PlotBuilding.Stages do
		local roofSpec = find(PlotBuilding.Stages[i].fade, "Roof")
		roofColors[roofSpec.color[1] .. "," .. roofSpec.color[2] .. "," .. roofSpec.color[3]] = true
	end
	local nColors = 0
	for _ in pairs(roofColors) do nColors += 1 end
	check("each stage has its own roof color", nColors >= 4, nColors)
end

-- 7. Nothing existing moved: the rooms, the props and every gameplay position are exactly what they were ------------------
-- The fingerprints were taken from PlotArt at 7f5c141 (the five rooms of visuals-garage). Stage 1, the props and the layout
-- are the same numbers tools/daily_test.py pins; stages 2 to 5 are pinned here. If one fails, a room, a prop or a gameplay
-- position changed: only allowed on purpose, by hand, and the building must then be checked against it again.
local function num(n) return string.format("%.4f", n) end
local function triple(t) if not t then return "-" end return num(t[1]) .. "," .. num(t[2]) .. "," .. num(t[3]) end
local function specString(s)
	local tr = s.text and (s.text.value .. s.text.font) or ""
	local lt = s.light and (s.light.brightness .. "/" .. s.light.range) or ""
	return table.concat({ s.name, s.shape, triple(s.size), triple(s.offset), triple(s.rot), triple(s.color), s.material, num(s.transparency or 0), tostring(s.collide), tr, lt }, "|")
end
local function listString(list)
	local out = {}
	for _, s in ipairs(list) do table.insert(out, specString(s)) end
	return table.concat(out, ";")
end
local function hash(str)
	local h = 5381
	for i = 1, #str do h = (h * 33 + string.byte(str, i)) % 4294967291 end
	return h
end
local function fingerprints()
	local fp = { stages = {} }
	for i, g in ipairs(PlotArt.Stages) do
		fp.stages[i] = { hash(listString(g.shell) .. "#" .. listString(g.decor) .. "#" .. listString(g.desk) .. g.floor.material .. triple(g.floor.color) .. g.key), #g.shell, #g.decor, #g.desk }
	end
	local names = {}
	for n in pairs(PlotArt.Props) do table.insert(names, n) end
	table.sort(names)
	local ps = {}
	for _, n in ipairs(names) do table.insert(ps, n .. "=" .. listString(PlotArt.Props[n])) end
	fp.props = hash(table.concat(ps, "##"))
	local L2 = PlotArt.Layout
	local ls = {}
	for _, s in ipairs(L2.employeeSpots) do table.insert(ls, s[1] .. "," .. s[2]) end
	for _, s in ipairs(L2.incubators) do table.insert(ls, s[1] .. "," .. s[2]) end
	for _, s in ipairs(L2.itemSlots) do table.insert(ls, s.name .. s.x .. "," .. s.z) end
	for _, s in ipairs(L2.signs) do table.insert(ls, s.name .. s.x .. "," .. s.z) end
	for _, s in ipairs(L2.desks) do table.insert(ls, s[1] .. "," .. s[2] .. "," .. s[3]) end
	table.insert(ls, L2.spawn.x .. "," .. L2.spawn.z)
	local rs = {}
	for k, v in pairs(L2.reserve) do table.insert(rs, k .. "=" .. v) end
	table.sort(rs)
	fp.layout = hash(table.concat(ls, ";") .. table.concat(rs, ";"))
	fp.flash = hash(listString({ PlotArt.Flash.part }))
	return fp
end
local WANT = {
	{ 2156961517, 35, 81, 2 }, { 1293939730, 28, 43, 5 }, { 2848503495, 41, 40, 5 }, { 947567108, 29, 51, 5 }, { 1423901377, 34, 39, 6 },
}
local before = fingerprints()
check("PlotArt still has exactly the five rooms of visuals-garage", #PlotArt.Stages == 5, #PlotArt.Stages)
for i = 1, 5 do
	local got, want = before.stages[i], WANT[i]
	check("room " .. i .. " is unchanged (fingerprint of its shell, decor, desks, floor and key, and its part counts)",
		got ~= nil and got[1] == want[1] and got[2] == want[2] and got[3] == want[3] and got[4] == want[4], got and (got[1] .. " " .. got[2] .. "/" .. got[3] .. "/" .. got[4]))
end
check("the six upgrade props are unchanged (fingerprint of every part; the same number daily_test.py pins)", before.props == 893633666, before.props)
check("every gameplay position is unchanged: hire grid, incubators, upgrade stations, signs, spawn, desk offsets, reserved zones (the same fingerprint daily_test.py pins)", before.layout == 1471280708, before.layout)
check("the stage-change flash is unchanged", before.flash == 381513097, before.flash)
-- The same positions, compared one by one with the scripts (EXPECTED is read from TycoonCore, EmployeeServer and IpoServer)
do
	local EXPECTED = __EXPECTED__
	local L = PlotArt.Layout
	check("layout: Floor size and top match TycoonCore (60 x 1 x 60, top 0.5)", L.floorSize[1] == EXPECTED.floor[1] and L.floorSize[2] == EXPECTED.floor[2] and L.floorSize[3] == EXPECTED.floor[3] and L.floorTop == EXPECTED.floorTop)
	local signsOk = true
	for _, sign in ipairs(L.signs) do local e = EXPECTED.signs[sign.name] if not e or sign.x ~= e[1] or sign.z ~= e[2] then signsOk = false end end
	check("layout: the two signs are where their scripts put them", signsOk and #L.signs == 2)
	check("layout: the spawn is where teleportToPlot lands", L.spawn.x == EXPECTED.spawn[1] and L.spawn.z == EXPECTED.spawn[2])
	local slotsOk = #L.itemSlots == #EXPECTED.upgrades
	for i, slot in ipairs(L.itemSlots) do local e = EXPECTED.slots[i] if not e or slot.name ~= EXPECTED.upgrades[i] or slot.x ~= e[1] or slot.z ~= e[2] then slotsOk = false end end
	check("layout: the six upgrade stations are where TycoonCore's itemOffset puts them", slotsOk)
	local function sameSpots(a, b)
		if #a ~= #b then return false end
		for i = 1, #a do if a[i][1] ~= b[i][1] or a[i][2] ~= b[i][2] then return false end end
		return true
	end
	check("layout: the 11 hire spots are EmployeeServer's EMPLOYEE_SPOTS", sameSpots(L.employeeSpots, EXPECTED.spots))
	check("layout: the 5 incubators are EmployeeServer's INCUBATOR_SPOTS", sameSpots(L.incubators, EXPECTED.incubators))
	-- The door is on the walking lane: the lane (and the spawn) fit through it with room to spare
	local R = L.reserve
	check("the door opening (9 wide) is wider than the walking lane and centered on it", PlotBuilding.Envelope.doorHalf > R.spawnHalf + 1 and L.spawn.x == 0)
	check("the door opening leaves the lane's end (z = laneEnd) inside the wall: the lane ends before the building's inner face", R.laneEnd <= PlotBuilding.Envelope.inner)
end
-- Building changes nothing of the room: a room built beside a building is checked by the room's own check, unchanged
do
	local folder = newInstance("Folder")
	local room = PlotVisuals.buildRoom(folder, center, PlotArt, 4)
	for _, slot in ipairs(PlotArt.Layout.itemSlots) do
		PlotVisuals.buildProp(room:FindFirstChild("UpgradeProps"), center, PlotArt, slot.name, Vector3.new(slot.x, 0, slot.z))
	end
	local partsBefore = #room:GetDescendants()
	PBV.sync(folder, center, PlotArt, PlotBuilding, 4)
	local probs = PlotVisuals.check(room, center, PlotArt)
	check("a room next to its building still passes PlotVisuals.check (parts, zones, flags, budget 260)", #probs == 0 and #room:GetDescendants() == partsBefore, probs[1])
	local roomParts = 0
	for _, d in ipairs(room:GetDescendants()) do if d:IsA("BasePart") then roomParts += 1 end end
	check("the room's own count (" .. roomParts .. ") stays under its 260 limit and does not include the building", roomParts <= PlotVisuals.MAX_PARTS)
end
local after = fingerprints()
local same = after.props == before.props and after.layout == before.layout and after.flash == before.flash
for i = 1, 5 do same = same and after.stages[i][1] == before.stages[i][1] end
check("building and checking everything above changed no PlotArt data (the fingerprints are the same afterwards)", same)

print_real(string.format("%d passed, %d failed", passed, failed))
for i, n in ipairs(PARTS) do print_real("  stage " .. i .. ": " .. n .. " building parts") end
"""


CLIENT_TESTS = r"""-- Tests: the real BuildingClient (the LocalScript source in docs/studio_scripts) running against a fake world ---------------
-- The fake world has a CollectionService (tags), a Heartbeat the test fires frame by frame, and a local character that
-- the test moves. The building Models are the real ones PlotBuildingVisuals builds. Expected values are written out here
-- (base + (1 - base) * step / 20), not taken from the code under test.
local PlotArt = (function()
__PLOTART__
end)()
local PlotBuilding = (function()
__PLOTBUILDING__
end)()
local PBV = (function()
__PLOTBUILDINGVISUALS__
end)()

local task = { spawn = function(f, ...) f(...) end, wait = function() end }
local WORLD
local game = { GetService = function(_, name)
	if name == "CollectionService" then return WORLD.cs
	elseif name == "Players" then return WORLD.players
	elseif name == "RunService" then return WORLD.run end
	error("no service " .. tostring(name))
end }

local function startClient()
__CLIENT__
return { isInside = isInside, fadeStep = fadeStep, quantize = quantize, transparencyAt = transparencyAt }
end

local function newWorld()
	local w = { tagged = {}, added = newSignal(), removed = newSignal(), heartbeat = newSignal() }
	w.cs = {
		GetTagged = function(_, tag) return table.clone(w.tagged) end,
		GetInstanceAddedSignal = function(_, tag) return w.added end,
		GetInstanceRemovedSignal = function(_, tag) return w.removed end,
	}
	w.root = { Position = vec(0, 0, 0), Parent = {} }
	w.character = { root = w.root, FindFirstChild = function(self, name) if name == "HumanoidRootPart" then return self.root end return nil end }
	w.players = { LocalPlayer = { Character = w.character } }
	w.run = { Heartbeat = w.heartbeat }
	return w
end
local function fresh()
	WORLD = newWorld()
	startClient()
	return WORLD
end
local CLIENTMATH -- the maths as it sits inside BuildingClient: the same unit tests as the module's run on it
local function frames(n, dt) for _ = 1, n do WORLD.heartbeat.fire(dt or 1 / 60) end end
local function place(x, y, z) WORLD.root.Position = vec(x, y, z) end

local centerA = Vector3.new(-135, 0.5, 150) -- slot 2
local centerB = Vector3.new(-45, 0.5, 150) -- slot 3, 90 studs over
local cx, cz, fy = centerA.X, centerA.Z, centerA.Y + PlotArt.Layout.floorTop
local b = PBV.bounds(centerA, PlotArt, PlotBuilding)
CLIENTMATH = (function() WORLD = newWorld() return startClient() end)()
local M = CLIENTMATH
local center = centerA
do
__MATH_A__
__MATH_B__
end
local INSIDE = { cx, fy + 3, cz + 12 }
local OUTSIDE = { cx, fy + 3, cz + 90 }
local function putInside() place(INSIDE[1], INSIDE[2], INSIDE[3]) end
local function putOutside() place(OUTSIDE[1], OUTSIDE[2], OUTSIDE[3]) end

-- Adds a building the way the server does: built, tagged, then arriving in the world
local function addBuilding(world, center, stage)
	local m = PBV.build(nil, center, PlotArt, PlotBuilding, stage)
	local bases, statics = {}, {}
	for _, d in ipairs(m:FindFirstChild("Fade"):GetDescendants()) do if d:IsA("BasePart") then bases[d] = d.Transparency end end
	for _, d in ipairs(m:FindFirstChild("Static"):GetDescendants()) do if d:IsA("BasePart") then statics[d] = d.Transparency end end
	table.insert(world.tagged, m)
	world.added.fire(m)
	return m, bases, statics
end
local function expected(base, level) return base + (1 - base) * level / 20 end
local function allAt(bases, level)
	local worst = 0
	for part, base in pairs(bases) do worst = math.max(worst, math.abs(part.Transparency - expected(base, level))) end
	return worst < 1e-9, worst
end
local function range(bases)
	local lo, hi = 2, -1
	for part in pairs(bases) do lo = math.min(lo, part.Transparency) hi = math.max(hi, part.Transparency) end
	return lo, hi
end
local function count(t) local n = 0 for _ in pairs(t) do n += 1 end return n end
local function textsOf(m)
	local labels, guis = {}, {}
	for _, d in ipairs(m:FindFirstChild("Fade"):GetDescendants()) do
		if d.ClassName == "TextLabel" then table.insert(labels, d) elseif d.ClassName == "SurfaceGui" then table.insert(guis, d) end
	end
	return labels, guis
end
local function snapshot(m)
	local out = {}
	for _, d in ipairs(m:GetDescendants()) do
		if d:IsA("BasePart") then
			table.insert(out, table.concat({ d:GetFullName(), tostring(d.Anchored), tostring(d.CanCollide), tostring(d.CanTouch), tostring(d.CanQuery), tostring(d.CastShadow),
				d.Size.X, d.Size.Y, d.Size.Z, d.CFrame.x, d.CFrame.y, d.CFrame.z, d.Material.Name, d.Color.rgb[1], d.Color.rgb[2], d.Color.rgb[3] }, "|"))
		end
	end
	return table.concat(out, "\n")
end

-- 1. From outside to inside and back (stage 4: glass, a SurfaceGui with text, ground pieces) ----------------------------
do
	fresh()
	putOutside()
	local m, bases, statics = addBuilding(WORLD, centerA, 4)
	local labels, guis = textsOf(m)
	local glass = 0
	for _, base in pairs(bases) do if base > 0 and base < 1 then glass += 1 end end
	check("the stage-4 building has glass (a base Transparency between 0 and 1), text on a SurfaceGui and ground pieces", glass >= 5 and #labels >= 1 and #guis >= 1 and count(statics) >= 1, glass .. " glass, " .. #labels .. " labels")
	local before = snapshot(m)
	frames(120)
	check("outside: the building stays solid (every part at its own Transparency, text and SurfaceGui as they were)", allAt(bases, 0) and labels[1].TextTransparency == 0 and guis[1].Enabled == true)
	local writes = WRITES
	frames(300)
	check("outside: nothing is written while it holds still (300 frames, 0 writes)", WRITES == writes, WRITES - writes)
	-- Walk in
	putInside()
	frames(6)
	local lo, hi = range(bases)
	check("walking in: after 0.1 s the fade has started but is not done (some part between its base and 1)", lo >= 0 and hi <= 1 and (function()
		for part, base in pairs(bases) do if part.Transparency > base + 0.01 and part.Transparency < 0.99 then return true end end return false end)())
	local prevMax = 0
	local mono, within = true, true
	putOutside()
	putInside()
	local last = {}
	for part in pairs(bases) do last[part] = part.Transparency end
	writes = WRITES
	for _ = 1, 40 do
		frames(1)
		for part in pairs(bases) do
			if part.Transparency < last[part] - 1e-12 then mono = false end
			if not (part.Transparency >= 0 and part.Transparency <= 1) then within = false end
			last[part] = part.Transparency
		end
	end
	check("walking in: every part only gets more transparent, and always stays between 0 and 1", mono and within)
	local writeCount = WRITES - writes
	check("walking in: all parts are completely transparent (1) after the fade", allAt(bases, 20))
	check("walking in: the text is hidden too (TextTransparency 1) and its SurfaceGui is off, so no text floats", labels[1].TextTransparency == 1 and guis[1].Enabled == false)
	local sPart = next(statics)
	check("walking in: the ground pieces (Static) are never touched", (function() for part, base in pairs(statics) do if part.Transparency ~= base then return false end end return true end)())
	writes = WRITES
	frames(300)
	check("inside: nothing is written while it holds still (300 frames, 0 writes)", WRITES == writes, WRITES - writes)
	-- Walk out
	putOutside()
	frames(60)
	check("walking out: everything is back at exactly its own Transparency (glass 0.35 included), the text shows again", allAt(bases, 0) and labels[1].TextTransparency == 0 and guis[1].Enabled == true)
	check("a full cycle changed nothing but Transparency, TextTransparency and SurfaceGui.Enabled (anchoring, collision, size, position, material, color all as built)", snapshot(m) == before)
	-- A full fade writes each part at most 20 times (one per step), not once per frame
	putInside()
	writes = WRITES
	frames(60)
	local perPart = (WRITES - writes) / count(bases)
	check("a full fade writes each part at most once per step (at most 20 times, not once per frame): " .. string.format("%.1f", perPart), perPart <= 20 and perPart >= 10, perPart)
end

-- 2. The fade takes the time it says (0.4 s) at any frame rate, and never jumps -------------------------------------------
do
	fresh()
	putOutside()
	local m, bases = addBuilding(WORLD, centerA, 2)
	putInside()
	frames(12, 1 / 60) -- 0.2 s: halfway
	local lo, hi = range(bases)
	check("at 60 fps, 0.2 s into the 0.4 s fade the solid parts are about halfway (0.5)", math.abs(lo - 0.5) < 0.06 or math.abs(lo - 0.5) < 0.12, lo)
	frames(13, 1 / 60)
	check("at 60 fps it is done after 0.4 s (25 frames)", allAt(bases, 20))
	putOutside()
	frames(12, 1 / 30) -- 0.4 s at 30 fps
	check("at 30 fps it takes the same 0.4 s to come back", allAt(bases, 0))
	putInside()
	frames(1, 0.1) -- one long frame, a quarter of the fade
	lo = range(bases)
	check("one 0.1 s frame moves a quarter of the way (0.25), never more", math.abs(lo - 0.25) < 1e-9, lo)
	-- Reversing mid-fade continues from where it is: no jump
	frames(2, 0.1)
	local mid = range(bases)
	putOutside()
	frames(1, 1 / 60)
	local after = range(bases)
	check("reversing in the middle of a fade goes back from where it was (no jump to the end)", after < mid and mid - after < 0.1, mid .. " -> " .. after)
	frames(60)
	check("and gets back to solid", allAt(bases, 0))
	frames(1, 1e9)
	putInside()
	frames(1, 1e9)
	check("an enormous frame time finishes the fade at once, at exactly 1", allAt(bases, 20))
	putOutside()
	frames(1, 0)
	frames(1, -5)
	frames(1, 0 / 0)
	check("a frame time of zero, below zero or NaN changes nothing", allAt(bases, 20))
	frames(60)
	check("and the next sane frames carry on", allAt(bases, 0))
end

-- 3. The door and the corners, as the client sees them ---------------------------------------------------------------------
do
	fresh()
	putOutside()
	local m, bases = addBuilding(WORLD, centerA, 3)
	place(cx, fy + 3, b.maxZ + 3.6)
	frames(60)
	check("in front of the door, past the apron (3.6 studs from the wall): the roof stays solid", allAt(bases, 0))
	place(cx, fy + 3, b.maxZ + 3.4)
	frames(60)
	check("on the apron, 3.4 studs from the wall: the building fades before you cross the door", allAt(bases, 20))
	place(cx + 6, fy + 3, b.maxZ + 2)
	frames(60)
	check("beside the door, 2 studs in front of the wall: solid again", allAt(bases, 0))
	place(b.maxX, fy + 3, b.maxZ)
	frames(60)
	check("standing exactly in a corner of the room: faded (edges count as inside)", allAt(bases, 20))
	place(b.maxX + 1.5, fy + 3, b.maxZ + 1.5)
	frames(60)
	check("outside that corner: solid", allAt(bases, 0))
	place(cx, b.maxY + 5, cz)
	frames(60)
	check("above the roof (a jump or a fall from above, y over the underside of the roof): the roof stays solid", allAt(bases, 0))
	place(cx, b.maxY, cz)
	frames(60)
	check("just under the roof: faded", allAt(bases, 20))
	place(cx, fy - 50, cz)
	frames(60)
	check("far below the floor: solid", allAt(bases, 0))
	place(0 / 0, fy + 3, cz)
	frames(60)
	check("a NaN position is never inside: solid", allAt(bases, 0))
end

-- 4. The edge of a wall does not flicker (hysteresis) ------------------------------------------------------------------------
do
	fresh()
	putOutside()
	local m, bases = addBuilding(WORLD, centerA, 1)
	place(b.maxX + 0.5, fy + 3, cz)
	frames(60)
	check("0.5 outside the wall, coming from outside: solid", allAt(bases, 0))
	putInside()
	frames(60)
	place(b.maxX + 0.5, fy + 3, cz)
	frames(60)
	check("0.5 outside the wall, coming from inside: still faded (the margin keeps it from flickering)", allAt(bases, 20))
	place(b.maxX + 1.5, fy + 3, cz)
	frames(60)
	check("1.5 outside the wall: solid", allAt(bases, 0))
	check("and coming back to 0.5 outside the wall from there stays solid", (function() place(b.maxX + 0.5, fy + 3, cz) frames(60) return allAt(bases, 0) end)())
end

-- 5. Starting inside, stage changes, no character, two buildings -------------------------------------------------------------
do
	fresh()
	putInside()
	local m, bases = addBuilding(WORLD, centerA, 1)
	check("a building that arrives while you stand inside is already faded (no frame needed, the roof never flashes shut)", allAt(bases, 20))
	-- A new funding stage: the server destroys the old Model and adds the new one
	local old = m
	for i, c in ipairs(WORLD.tagged) do if c == old then table.remove(WORLD.tagged, i) break end end
	WORLD.removed.fire(old)
	old.Parent = nil
	local m2, bases2 = addBuilding(WORLD, centerA, 2)
	check("a new stage replaces the building and is faded at once for someone inside", allAt(bases2, 20))
	frames(30)
	check("and it stays faded", allAt(bases2, 20))
	local writes = WRITES
	local x = old:FindFirstChild("Fade"):FindFirstChild("Roof")
	frames(30)
	check("the removed building is forgotten (nothing is written to it any more)", WRITES == writes)
	-- No character: dead or respawning
	WORLD.players.LocalPlayer.Character = nil
	frames(120)
	check("with no character (dead, respawning) the roof holds its state: still faded", allAt(bases2, 20))
	WORLD.players.LocalPlayer.Character = WORLD.character
	putOutside()
	frames(60)
	check("the new character appears outside: solid again", allAt(bases2, 0))
	WORLD.root.Parent = nil
	putInside()
	frames(60)
	check("a character whose root part was destroyed counts as no character (holds): still solid", allAt(bases2, 0))
	WORLD.root.Parent = {}
	frames(60)
	check("and the root part coming back inside: faded", allAt(bases2, 20))
end
do
	fresh()
	putInside()
	local a, basesA = addBuilding(WORLD, centerA, 1)
	local bm, basesB = addBuilding(WORLD, centerB, 5)
	frames(60)
	check("two buildings 90 studs apart: inside one fades only that one", allAt(basesA, 20) and allAt(basesB, 0))
	place(centerB.X, fy + 3, centerB.Z + 5)
	frames(60)
	check("walking to the next plot: the first goes solid, the second fades", allAt(basesA, 0) and allAt(basesB, 20))
end
do
	-- Buildings already in the world when the script starts (it starts after the server built them)
	WORLD = newWorld()
	putInside()
	local m, bases = addBuilding(WORLD, centerA, 3)
	startClient()
	check("a building that was there before the script started is picked up (faded at once)", allAt(bases, 20))
end

-- 6. Streaming, bad data, hammering -----------------------------------------------------------------------------------------------
do
	fresh()
	putInside()
	local m, bases = addBuilding(WORLD, centerA, 3)
	local late = Instance.new("Part")
	late.Name = "LatePart"
	late.Transparency = 0.2
	late.Parent = m:FindFirstChild("Fade")
	check("a part that streams in late takes the current fade at once (faded)", late.Transparency == 1, late.Transparency)
	putOutside()
	frames(60)
	check("and goes back to its own Transparency (0.2) with the rest", math.abs(late.Transparency - 0.2) < 1e-9 and allAt(bases, 0), late.Transparency)
end
do
	fresh()
	putInside()
	local m = PBV.build(nil, centerA, PlotArt, PlotBuilding, 2)
	m:SetAttribute("MaxX", nil)
	table.insert(WORLD.tagged, m)
	local bases = {}
	for _, d in ipairs(m:FindFirstChild("Fade"):GetDescendants()) do if d:IsA("BasePart") then bases[d] = d.Transparency end end
	WORLD.added.fire(m)
	frames(60)
	check("a building without its numbers (no MaxX) is left alone: no error, nothing faded", allAt(bases, 0))
	local m2 = PBV.build(nil, centerA, PlotArt, PlotBuilding, 2)
	m2:SetAttribute("MinZ", 0 / 0)
	local bases2 = {}
	for _, d in ipairs(m2:FindFirstChild("Fade"):GetDescendants()) do if d:IsA("BasePart") then bases2[d] = d.Transparency end end
	table.insert(WORLD.tagged, m2)
	WORLD.added.fire(m2)
	frames(60)
	check("a building with a NaN number is left alone too", allAt(bases2, 0))
end
do
	fresh()
	local m, bases = addBuilding(WORLD, centerA, 5)
	local seed = 99
	local function rand() seed = (seed * 1664525 + 1013904223) % 4294967296 return seed / 4294967296 end
	local bad = nil
	local specials = { 0, 1e-9, -1, 5, 1e9, 0 / 0, math.huge, -math.huge, 1 / 60, 1 / 30 }
	for i = 1, 3000 do
		local roll = rand()
		if roll < 0.4 then putInside() elseif roll < 0.8 then putOutside() else place(cx + (rand() - 0.5) * 80, fy + (rand() - 0.2) * 30, cz + (rand() - 0.5) * 80) end
		if rand() < 0.1 then place(specials[math.floor(rand() * #specials) + 1], fy + 3, cz) end
		local dt = rand() < 0.3 and specials[math.floor(rand() * #specials) + 1] or rand() * 0.2
		WORLD.heartbeat.fire(dt)
		for part, base in pairs(bases) do
			local v = part.Transparency
			if not (v >= 0 and v <= 1) or v ~= v or v < base - 1e-9 then bad = bad or (i .. ": " .. tostring(v)) end
		end
	end
	check("3,000 frames of random positions (NaN and infinity too) and frame times (zero, negative, NaN, huge): Transparency is always a number from its base to 1", bad == nil, bad)
	putOutside()
	frames(60)
	check("after all that the building still answers: back outside it is solid again (nothing crashed or was dropped)", allAt(bases, 0))
end

-- 7. Heartbeat is the only thing the client listens to, and it never changes how anything plays ------------------------------------------
do
	fresh()
	check("the script listens to Heartbeat, the tag added and the tag removed (and nothing else)", #WORLD.heartbeat.handlers == 1 and #WORLD.added.handlers == 1 and #WORLD.removed.handlers == 1)
end

print_real(string.format("%d passed, %d failed", passed, failed))
"""


def read(name):
    with open(os.path.join(ROOT, name), encoding="utf-8") as f:
        return f.read()


CLIENT_FILE = os.path.join("docs", "studio_scripts", "BuildingClient.lua")


def run_luau(luau, source):
    with tempfile.NamedTemporaryFile("w", suffix=".luau", delete=False, encoding="utf-8") as f:
        f.write(source)
        path = f.name
    try:
        result = subprocess.run([luau, path], capture_output=True, text=True)
    finally:
        os.remove(path)
    return result


def visuals_expected_lua():
    """The layout map read from the real scripts, as a Luau table (PlotArt.Layout must match it). Same reading as tools/daily_test.py."""
    import re

    def num(text):
        return float(text) if "." in text else int(text)

    def spots(text, name):
        block = text[text.index("local %s = {" % name):]
        block = block[:block.index("\n}")]
        return [(num(x), num(z)) for x, z in re.findall(r"Vector3\.new\((-?[\d.]+), 0, (-?[\d.]+)\)", block)]

    core = read("TycoonCore.lua")
    upgrades_block = core[core.index("local UPGRADES = {"):]
    upgrades_block = upgrades_block[:upgrades_block.index("\n}")]
    upgrades = re.findall(r'name = "([^"]+)"', upgrades_block)
    item = re.search(r"local function itemOffset\(i\)\s*local col = \(i - 1\) // 3\s*local row = \(i - 1\) % 3\s*return Vector3\.new\((-?[\d.]+) \+ col \* (-?[\d.]+), 0, (-?[\d.]+) \+ row \* (-?[\d.]+)\)", core)
    if not item:
        raise SystemExit("itemOffset changed in TycoonCore.lua: PlotArt.Layout and this test must be updated together")
    x0, dx, z0, dz = (num(item.group(k)) for k in (1, 2, 3, 4))
    slots = [(x0 + ((i - 1) // 3) * dx, z0 + ((i - 1) % 3) * dz) for i in range(1, len(upgrades) + 1)]
    spawn = re.search(r"local spawnPos = plotCenter\(slot\) \+ Vector3\.new\((-?[\d.]+), 4, (-?[\d.]+)\)", core)
    floor = re.search(r'makePart\(folder, "Floor", Vector3\.new\((\d+), (\d+), (\d+)\), plotCenter\(slot\)', core)
    buy = re.search(r"local SIGN_OFFSET = Vector3\.new\((-?[\d.]+), 0\.5, (-?[\d.]+)\)", core)
    ipo = re.search(r"local SIGN_OFFSET = Vector3\.new\((-?[\d.]+), 0\.5, (-?[\d.]+)\)", read("IpoServer.lua"))
    employee = read("EmployeeServer.lua")
    if not all((buy, spawn, floor, ipo)):
        raise SystemExit("A sign, the spawn or the Floor moved in the scripts: PlotArt.Layout and this test must be updated together")
    floor_top = float(floor.group(2)) / 2  # the Floor is centered on plotCenter

    def pairs(points):
        return "{ " + ", ".join("{ %s, %s }" % p for p in points) + " }"

    return ("{ upgrades = { %s }, slots = %s, spots = %s, incubators = %s, floor = { %s, %s, %s }, floorTop = %s, "
            "signs = { BuySign = { %s, %s }, IpoSign = { %s, %s } }, spawn = { %s, %s } }") % (
        ", ".join('"%s"' % u for u in upgrades), pairs(slots), pairs(spots(employee, "EMPLOYEE_SPOTS")),
        pairs(spots(employee, "INCUBATOR_SPOTS")), floor.group(1), floor.group(2), floor.group(3), floor_top,
        buy.group(1), buy.group(2), ipo.group(1), ipo.group(2), spawn.group(1), spawn.group(2))


def building_source(module_text=None):
    """The module tests with the real files. module_text replaces PlotBuildingVisuals.lua (for a mutation run)."""
    return (PRELUDE + MODULE_GAME + BUILDING_TESTS.replace("__MATH_A__", MATH_A).replace("__MATH_B__", MATH_B).replace("__PLOTART__", read("PlotArt.lua")).replace("__PLOTVISUALS__", read("PlotVisuals.lua"))
            .replace("__PLOTBUILDING__", read("PlotBuilding.lua")).replace("__PLOTBUILDINGVISUALS__", module_text or read("PlotBuildingVisuals.lua"))
            .replace("__IPOCONFIG__", read("IpoConfig.lua")).replace("__EXPECTED__", visuals_expected_lua()))


def client_source(client_text=None):
    """The client tests with the real files. client_text replaces BuildingClient.lua (for a mutation run); the module stays as it is."""
    return (PRELUDE + CLIENT_TESTS.replace("__MATH_A__", MATH_A).replace("__MATH_B__", MATH_B).replace("__PLOTART__", read("PlotArt.lua")).replace("__PLOTBUILDING__", read("PlotBuilding.lua"))
            .replace("__PLOTBUILDINGVISUALS__", read("PlotBuildingVisuals.lua")).replace("__CLIENT__", client_text or read(CLIENT_FILE)))


def math_block(text):
    start = text.index("-- BUILDINGMATH-START")
    return text[start:text.index("-- BUILDINGMATH-END") + len("-- BUILDINGMATH-END")]


def code_only(text):
    """Lua source without comments (so a word in a comment is not a use)."""
    import re
    out = []
    for line in text.splitlines():
        out.append(re.sub(r"--.*$", "", line))
    return "\n".join(out)


# Mutations: each breaks one rule of the inside check or the fade, in the BUILDINGMATH block (the same text lives in
# PlotBuildingVisuals.lua and in BuildingClient.lua, so each is run in both). The tests must notice (a test that can't fail proves nothing).
INSIDE_MUTATIONS = [
    ("edges count as inside (a strict > on the back wall)", ("z >= b.minZ - m and", "z > b.minZ - m and")),
    ("edges count as inside (a strict < on the right wall)", ("x <= b.maxX + m then", "x < b.maxX + m then")),
    ("the roof ceiling (above the roof is outside)", ("y > b.maxY + m", "false")),
    ("the floor limit (far below the map is outside)", ("y < b.minY - m or ", "")),
    ("the door apron", ("return z > b.maxZ and z <= b.maxZ + b.doorDepth + m and x >= b.doorMinX - m and x <= b.doorMaxX + m", "return false")),
    ("the apron depth", ("z <= b.maxZ + b.doorDepth + m", "z <= b.maxZ + 100")),
    ("the apron width (the door's x range)", (" and x >= b.doorMinX - m and x <= b.doorMaxX + m", "")),
    ("the hysteresis (the margin once inside)", ("local m = wasInside and b.margin or 0", "local m = 0")),
    ("the hysteresis for outsiders (the margin always on)", ("local m = wasInside and b.margin or 0", "local m = b.margin")),
    ("the apron's side (it is at the front, +Z)", ("return z > b.maxZ and", "return z < b.minZ and")),
    ("the bad-number guard (NaN or infinity is never inside)", ("if not (finite(x) and finite(y) and finite(z)) then", "if false then")),
    ("x and z mixed up in the room's box", ("x >= b.minX - m and x <= b.maxX + m then", "z >= b.minX - m and z <= b.maxX + m then")),
]
FADE_MUTATIONS = [
    ("the fade overshoots its target upward", ("return clamp01(math.min(fade + step, target))", "return fade + step")),
    ("the fade overshoots its target downward", ("return clamp01(math.max(fade - step, target))", "return fade - step")),
    ("the fade speed (dt times seconds instead of dt over seconds)", ("local step = dt / seconds", "local step = dt * seconds")),
    ("the frame-time guard (zero, negative or NaN dt)", ("if not (dt > 0) then\n\t\treturn fade\n\tend", "")),
    ("the zero-seconds guard", ("if not (seconds > 0) then\n\t\treturn target\n\tend", "")),
    ("the 0..1 clamp (an upper limit of 2)", ("elseif n > 1 then", "elseif n > 2 then")),
    ("the NaN guard of the clamp", ("if n ~= n then\n\t\treturn 0\n\tend", "")),
    ("the step rounding (rounds up, so dust writes a step)", ("math.floor(clamp01(fade) * n + 0.5)", "math.ceil(clamp01(fade) * n)")),
    ("the base transparency (glass would fade from 0)", ("b + (1 - b) * clamp01(level / n)", "(1 - b) * clamp01(level / n)")),
    ("the step limit of the transparency (a step below 0)", ("clamp01(level / n)", "(level / n)")),
    ("the number of steps (a fixed 20)", ("local n = math.max(1, math.floor(levels + 0.5))\n\treturn math.floor", "local n = 20\n\treturn math.floor")),
]
# Mutations of the client's own wiring (only the client program is run)
CLIENT_MUTATIONS = [
    ("the direction (opaque when inside)", ("local target = state.inside and 1 or 0", "local target = state.inside and 0 or 1")),
    ("only the Fade group fades (Static would fade too)", ('local fade = model:FindFirstChild("Fade")\n\tfor _, item in ipairs(fade:GetDescendants()) do', 'local fade = model\n\tfor _, item in ipairs(fade:GetDescendants()) do')),
    ("the SurfaceGui switch (text would float on a gone roof)", ("gui.Enabled = level < levels", "gui.Enabled = true")),
    ("the base Transparency (glass would be lost)", ("part.Transparency = transparencyAt(base, level, levels)", "part.Transparency = level / levels")),
    ("holding the state with no character", ("if root then -- no character (dead, respawning): hold the last state", "if true then")),
    ("the first state of a new building (it would fade in)", ("fade = inside and 1 or 0, inside = inside", "fade = 0, inside = inside")),
    ("the hysteresis wiring (the last state is passed on)", ("isInside(state.bounds, p.X, p.Y, p.Z, state.inside)", "isInside(state.bounds, p.X, p.Y, p.Z, false)")),
    ("parts that arrive late", ("table.insert(state.connections, fade.DescendantAdded:Connect(function(item)\n\t\tremember(state, item)\n\tend))", "")),
    ("the frame time (a fixed 1 second)", ("fadeStep(state.fade, target, dt, state.seconds)", "fadeStep(state.fade, target, 1, state.seconds)")),
    ("only writing when the step changes", ("if level ~= state.level then", "if true then")),
    ("the building's own fade time", ("fade = inside and 1 or 0, inside = inside,", "fade = inside and 1 or 0, inside = inside, seconds = 5,")),
]


def apply_mutation(text, mutation, what):
    old, new = mutation
    if old not in text:
        raise SystemExit("mutation target not found in %s: %r" % (what, old))
    return text.replace(old, new, 1)


def static_checks():
    """Source checks on the new files: looks only, no services or remotes, the two math copies identical, no existing file edited."""
    import re
    passed, failed = 0, 0

    def check(name, cond, extra=None):
        nonlocal passed, failed
        if cond:
            passed += 1
        else:
            failed += 1
            print("FAIL: " + name + (" -- " + str(extra) if extra else ""))

    data, builder, client = read("PlotBuilding.lua"), read("PlotBuildingVisuals.lua"), read(CLIENT_FILE)
    check("the roof-fade maths is the same text in PlotBuildingVisuals.lua and in BuildingClient.lua", math_block(builder) == math_block(client))
    check("the maths block is pure: no service, Instance, Vector3 or task in it", not any(w in math_block(builder) for w in ("game", "Instance", "Vector3", "task.", "workspace", "Enum")))
    check("BuildingClient is a paste-ready script: it is in docs/studio_scripts, not at the repo root (not in the game tree)",
          os.path.exists(os.path.join(ROOT, CLIENT_FILE)) and not os.path.exists(os.path.join(ROOT, "BuildingClient.lua")))
    cc = code_only(client)
    for word in ("FireServer", "InvokeServer", "OnClientEvent", "RemoteEvent", "RemoteFunction", "DataStore", "SetAttribute", "CanCollide", "CanTouch", "CanQuery",
                 "Anchored", "CFrame", "Position =", ".Size", "Destroy", "math.random", "HttpService", "MarketplaceService", "Touched"):
        check("BuildingClient never uses %s (it only changes Transparency, TextTransparency and SurfaceGui.Enabled)" % word, word not in cc)
    check("BuildingClient reads only what it needs: three services (CollectionService, Players, RunService)", sorted(re.findall(r'GetService\("(\w+)"\)', cc)) == ["CollectionService", "Players", "RunService"])
    writes = sorted(set(re.findall(r"\b(\w+)\.(Transparency|TextTransparency|Enabled)\s*=[^=]", cc)))
    check("BuildingClient writes only Transparency, TextTransparency and Enabled", all(w[1] in ("Transparency", "TextTransparency", "Enabled") for w in writes), writes)
    check("BuildingClient has no Transparency write outside apply() and remember()", len(re.findall(r"\.Transparency\s*=[^=]", cc)) == 2 and len(re.findall(r"\.TextTransparency\s*=[^=]", cc)) == 2, writes)
    check("BuildingClient finds buildings by the tag PlotBuilding and the server tags with the same word", 'local TAG = "PlotBuilding"' in client and 'TAG = "PlotBuilding"' in builder)
    for name, text in (("PlotBuilding.lua", data), ("PlotBuildingVisuals.lua", builder)):
        code = code_only(text)
        for word in ("RemoteEvent", "RemoteFunction", "DataStore", "SetAsync", "addEarnings", "math.random", "Random", "rbxasset", "http", "Texture =", "MeshId", "Decal",
                     "PointLight", "SpotLight", "ParticleEmitter", "Touched", "CanCollide = true", "collide = true"):
            if name == "PlotBuildingVisuals.lua" and word in ("PointLight", "SpotLight", "ParticleEmitter"):
                continue  # the checker looks for them, to forbid them
            check("%s never uses %s (pure looks: no remotes, saves, assets, randomness, lights or solid parts)" % (name, word), word not in code)
        size = len(text.encode("utf-8"))
        check("%s stays under 120 KB (%d bytes)" % (name, size), size < 120 * 1024)
    check("PlotBuilding.lua is pure data: no GetService, no require, no Instance.new", not any(w in code_only(data) for w in ("GetService", "require(", "Instance.new")))
    check("PlotBuildingVisuals.lua asks for one service only, CollectionService (to tag the Model)", re.findall(r'GetService\("(\w+)"\)', code_only(builder)) == ["CollectionService"])
    check("PlotBuildingVisuals.lua requires nothing (PlotBuilding and the art are passed in, so a failing module can't take another down)", "require(" not in code_only(builder))

    # No existing file is edited. The base is the commit the branch was made from; only CONTRIBUTING.md (the claim rows) may differ,
    # and TycoonCore.lua only when it is exactly the base plus docs/building_pass_integration.patch (the approved integration).
    base = "7f5c141"
    try:
        have = subprocess.run(["git", "cat-file", "-e", base + "^{commit}"], cwd=ROOT, capture_output=True).returncode == 0
    except OSError:
        have = False
    if not have:
        print("note: git or the base commit %s is not available here, so the 'no existing file edited' check is skipped" % base)
    else:
        diff = subprocess.run(["git", "diff", "--name-only", "--diff-filter=MDRT", base, "--"], cwd=ROOT, capture_output=True, text=True).stdout.split()
        changed = sorted(set(diff))
        allowed = {"CONTRIBUTING.md"}
        extra = [n for n in changed if n not in allowed]
        if "TycoonCore.lua" in extra:
            with tempfile.TemporaryDirectory() as tmp:
                original = subprocess.run(["git", "show", base + ":TycoonCore.lua"], cwd=ROOT, capture_output=True).stdout
                with open(os.path.join(tmp, "TycoonCore.lua"), "wb") as f:
                    f.write(original)
                applied = subprocess.run(["git", "apply", os.path.join(ROOT, "docs", "building_pass_integration.patch")], cwd=tmp, capture_output=True)
                if applied.returncode == 0 and open(os.path.join(tmp, "TycoonCore.lua"), "rb").read() == open(os.path.join(ROOT, "TycoonCore.lua"), "rb").read():
                    extra.remove("TycoonCore.lua")
        check("no existing file is edited: against %s only CONTRIBUTING.md differs (TycoonCore.lua only as the approved patch)" % base, not extra, extra)
        if os.path.exists(os.path.join(ROOT, "tools", "daily_test.py")):
            same = subprocess.run(["git", "diff", "--quiet", base, "--", "tools/daily_test.py"], cwd=ROOT).returncode == 0
            check("tools/daily_test.py (another session's file) is untouched", same)
    return passed, failed


def integration_check(luau):
    """Optional (--integration): apply the integration patch to a scratch copy of the repo and run both test suites there."""
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
        subprocess.run(["git", "show", "7f5c141:TycoonCore.lua"], cwd=ROOT, stdout=open(os.path.join(tmp, "TycoonCore.lua"), "wb"))
        for name in ("PlotBuilding.lua", "PlotBuildingVisuals.lua"):
            shutil.copy(os.path.join(ROOT, name), os.path.join(tmp, name))
        applied = subprocess.run(["git", "apply", os.path.join(ROOT, "docs", "building_pass_integration.patch")], cwd=tmp, capture_output=True, text=True)
        if applied.returncode != 0:
            print("FAIL: the integration patch does not apply to the base TycoonCore.lua: " + applied.stderr.strip())
            return False
        env = dict(os.environ, LUAU=luau)
        ok = True
        for script in ("tools/daily_test.py", "tools/building_test.py"):
            result = subprocess.run([sys.executable, os.path.join(tmp, script)], cwd=tmp, capture_output=True, text=True, env=env)
            bad = [l for l in result.stdout.splitlines() if "FAIL" in l or (" failed" in l and " 0 failed" not in l)]
            print("  with the patch, %s: %s" % (script, "all pass" if result.returncode == 0 and not bad else "FAILS " + "; ".join(bad[:3])))
            ok = ok and result.returncode == 0 and not bad
        return ok


def main():
    luau = os.environ.get("LUAU") or shutil.which("luau")
    if not luau:
        print("Luau not found. Download it from https://github.com/luau-lang/luau/releases and set LUAU=/path/to/luau")
        return 2
    code = 0
    total = 0

    def counted(stdout):
        nonlocal total
        for line in stdout.splitlines():
            parts = line.split()
            if len(parts) >= 4 and parts[1] == "passed," and parts[0].isdigit():
                total += int(parts[0])

    result = run_luau(luau, building_source())
    print("Building data, builder, inside check, fade maths and untouched rooms: " + (result.stdout.strip() or result.stderr.strip()))
    counted(result.stdout)
    if result.returncode != 0 or " 0 failed" not in result.stdout:
        code = 1
    result = run_luau(luau, client_source())
    print("BuildingClient roof fade (the real script in a fake world): " + (result.stdout.strip() or result.stderr.strip()))
    counted(result.stdout)
    if result.returncode != 0 or " 0 failed" not in result.stdout:
        code = 1
    static_passed, static_failed = static_checks()
    print("Building source checks: %d passed, %d failed" % (static_passed, static_failed))
    total += static_passed
    if static_failed:
        code = 1

    # Mutation runs: break one rule at a time; the tests must run to the end and report failures (a crash would not count)
    builder_text, client_text = read("PlotBuildingVisuals.lua"), read(CLIENT_FILE)
    runs = caught = 0
    for group, mutations in (("inside check", INSIDE_MUTATIONS), ("fade", FADE_MUTATIONS)):
        for label, mutation in mutations:
            for where, runner in (("module", lambda m: building_source(apply_mutation(builder_text, m, "PlotBuildingVisuals.lua"))),
                                  ("client", lambda m: client_source(apply_mutation(client_text, m, "BuildingClient.lua")))):
                runs += 1
                mutant = run_luau(luau, runner(mutation))
                if "passed," in mutant.stdout and " 0 failed" not in mutant.stdout:
                    caught += 1
                else:
                    print("FAIL: mutation not caught by the %s tests: a broken %s (%s)" % (where, group, label))
                    code = 1
    for label, mutation in CLIENT_MUTATIONS:
        runs += 1
        mutant = run_luau(luau, client_source(apply_mutation(client_text, mutation, "BuildingClient.lua")))
        if "passed," in mutant.stdout and " 0 failed" not in mutant.stdout:
            caught += 1
        else:
            print("FAIL: mutation not caught by the client tests: a broken " + label)
            code = 1
    print("Building mutations: %d of %d broken rules caught (%d inside-check, %d fade, each run on the module and on the client; %d client wiring)" % (
        caught, runs, len(INSIDE_MUTATIONS), len(FADE_MUTATIONS), len(CLIENT_MUTATIONS)))
    if "--integration" in sys.argv:
        print("Integration patch on a scratch copy:")
        if not integration_check(luau):
            code = 1
    print("building_test.py: %d checks passed, %d mutation runs caught%s" % (total, caught, "" if code == 0 else "  -- SOMETHING FAILED"))
    return code


if __name__ == "__main__":
    sys.exit(main())
