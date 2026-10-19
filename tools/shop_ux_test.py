#!/usr/bin/env python3
"""Tests for the shop window (ShopLayout.lua and ShopClient.lua: PR S1 and S2 of docs/SHOP_UX_PROPOSAL.md), outside Studio.

Run:   python3 tools/shop_ux_test.py
       python3 tools/shop_ux_test.py --list-mutants   (also prints the named check that caught each mutation run)

It needs the free Luau command-line tool (https://github.com/luau-lang/luau/releases, the "luau" file from
luau-macos.zip, luau-windows.zip or luau-ubuntu.zip). Put it on your PATH, or point to it:
       LUAU=/path/to/luau python3 tools/shop_ux_test.py

It runs the real ShopLayout and the real ShopClient (with the real ShopConfig, CreatureConfig, IpoConfig and
TaskConfig, and the upgrade list read from TycoonCore.lua) in its own fake Roblox: Instances with classes and
properties (an unknown property errors, like Roblox), a GUI layout engine (UDim2, AnchorPoint, UIPadding, UIListLayout,
UISizeConstraint, ScrollingFrame canvases) for AbsolutePosition and AbsoluteSize, a clock for task.spawn, task.wait and
task.delay, remotes the test answers (or holds), and an estimate of Roblox's text measure. It checks the window's
rectangles at five phones with a top bar of 0, 36 and 58 px (header items never overlap, the window stays inside the
GUI, every tap target is 44 x 44 or more, no text can shrink under 16 px, the bottom slot never covers a Buy button),
the names the tutorial needs, the help card, the TutorialStrip, the in-window status line, what the shop sends to the
server, Luck Boost for restricted players and the odds words (D9). Then it breaks ShopLayout and ShopClient on purpose
(mutation runs): each must be caught by a named check, never by a crash: the named check must fail in a block of checks
that ran to its end with no uncaught error (in ShopLayout, the test or ShopClient). Two harness self-tests make sure a
mutant that fails its named check only next to a crash is reported as not caught.

It changes nothing in the game or in Studio. Text widths are an estimate (Gotham at about 0.56 em a letter): what fits
exactly is for Test > Device in Studio to confirm.
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LAYOUT, CLIENT = "ShopLayout.lua", "ShopClient.lua"


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


def long_string(text):
    """text as a Luau long string literal whose level never appears inside it."""
    level = 1
    while ("]" + "=" * level + "]") in text:
        level += 1
    return "[" + "=" * level + "[\n" + text + "]" + "=" * level + "]"


PRELUDE = r"""-- Fake Roblox for the shop window --------------------------------------------------------------------------------
-- Instances with classes and properties (an unknown property or a wrong type errors, like Roblox), children,
-- attributes and signals; a GUI layout engine for AbsolutePosition and AbsoluteSize; a clock for task.spawn, task.wait
-- and task.delay; remotes that the test answers (or holds); Roblox's text measure as an estimate.
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
local LOG = { warned = {}, errors = {} }
-- A block of checks: an error inside it (a broken ShopLayout, or a test that met something missing) is a named FAIL,
-- and the next block still runs
-- (a SECTION line marks where each block starts, so a mutation run can tell which block a FAIL line came from)
local function section(name, fn)
	print_real("SECTION " .. name)
	local ok, err = pcall(fn)
	check("the checks of \"" .. name .. "\" run to their end (no error in ShopLayout or in the test)", ok, err)
end

-- Types ---------------------------------------------------------------------------------------------------------
local function typeOf(v)
	local mt = getmetatable(v)
	if type(mt) == "table" and rawget(mt, "__type") then
		return mt.__type
	end
	return typeof(v)
end

local V2 = { __type = "Vector2" }
V2.__index = V2
V2.__eq = function(a, b) return a.X == b.X and a.Y == b.Y end
V2.__tostring = function(a) return a.X .. ", " .. a.Y end
local function v2(x, y) return setmetatable({ X = x or 0, Y = y or 0 }, V2) end
local Vector2 = { new = v2, zero = v2(0, 0), one = v2(1, 1) }

local UD = { __type = "UDim" }
UD.__index = UD
UD.__eq = function(a, b) return a.Scale == b.Scale and a.Offset == b.Offset end
local function udim(s, o) return setmetatable({ Scale = s or 0, Offset = o or 0 }, UD) end
local UDim = { new = udim }

local U2 = { __type = "UDim2" }
U2.__index = U2
U2.__eq = function(a, b) return a.X == b.X and a.Y == b.Y end
U2.__tostring = function(a) return string.format("{%g, %g}, {%g, %g}", a.X.Scale, a.X.Offset, a.Y.Scale, a.Y.Offset) end
local function udim2(xs, xo, ys, yo)
	local x, y = udim(xs, xo), udim(ys, yo)
	return setmetatable({ X = x, Y = y, Width = x, Height = y }, U2)
end
local UDim2 = {
	new = function(xs, xo, ys, yo) return udim2(xs or 0, xo or 0, ys or 0, yo or 0) end,
	fromScale = function(x, y) return udim2(x or 0, 0, y or 0, 0) end,
	fromOffset = function(x, y) return udim2(0, x or 0, 0, y or 0) end,
}

local C3 = { __type = "Color3" }
C3.__index = C3
C3.__eq = function(a, b) return math.abs(a.R - b.R) < 1e-6 and math.abs(a.G - b.G) < 1e-6 and math.abs(a.B - b.B) < 1e-6 end
local Color3 = {
	fromRGB = function(r, g, b) return setmetatable({ R = (r or 0) / 255, G = (g or 0) / 255, B = (b or 0) / 255 }, C3) end,
	new = function(r, g, b) return setmetatable({ R = r or 0, G = g or 0, B = b or 0 }, C3) end,
}

local TI = { __type = "TweenInfo" }
local TweenInfo = {
	new = function(time, style, direction, repeats, reverses, delay)
		return setmetatable({ Time = time or 1, EasingStyle = style, EasingDirection = direction, RepeatCount = repeats or 0, Reverses = reverses or false, DelayTime = delay or 0 }, TI)
	end,
}

local function enumType(typeName, names)
	local t = {}
	for _, n in ipairs(names) do
		t[n] = setmetatable({ Name = n, EnumType = typeName }, { __type = "EnumItem", __tostring = function() return "Enum." .. typeName .. "." .. n end })
	end
	return setmetatable(t, { __index = function(_, k) error(tostring(k) .. " is not a valid member of Enum " .. typeName, 2) end })
end
local Enum = setmetatable({
	Font = enumType("Font", { "GothamBold", "Gotham", "GothamMedium", "GothamBlack", "SourceSans", "SourceSansBold", "FredokaOne" }),
	TextXAlignment = enumType("TextXAlignment", { "Left", "Center", "Right" }),
	TextYAlignment = enumType("TextYAlignment", { "Top", "Center", "Bottom" }),
	TextTruncate = enumType("TextTruncate", { "None", "AtEnd" }),
	ZIndexBehavior = enumType("ZIndexBehavior", { "Global", "Sibling" }),
	FillDirection = enumType("FillDirection", { "Horizontal", "Vertical" }),
	SortOrder = enumType("SortOrder", { "LayoutOrder", "Name" }),
	AutomaticSize = enumType("AutomaticSize", { "None", "X", "Y", "XY" }),
	ScrollingDirection = enumType("ScrollingDirection", { "X", "Y", "XY" }),
	ApplyStrokeMode = enumType("ApplyStrokeMode", { "Contextual", "Border" }),
	EasingStyle = enumType("EasingStyle", { "Linear", "Sine", "Quad", "Cubic", "Back", "Bounce", "Elastic", "Quart", "Quint", "Exponential", "Circular" }),
	EasingDirection = enumType("EasingDirection", { "In", "Out", "InOut" }),
	HorizontalAlignment = enumType("HorizontalAlignment", { "Left", "Center", "Right" }),
	VerticalAlignment = enumType("VerticalAlignment", { "Top", "Center", "Bottom" }),
	PlaybackState = enumType("PlaybackState", { "Begin", "Playing", "Paused", "Completed", "Cancelled" }),
}, { __index = function(_, k) error(tostring(k) .. " is not a valid Enum", 2) end })

-- The clock: task.spawn runs at once (like Roblox), task.wait and task.delay wake up when run() reaches them ---------
local SCHED = { now = 0, timers = {}, seq = 0 }
local function resume(co, ...)
	local ok, err = coroutine.resume(co, ...)
	if not ok then
		table.insert(LOG.errors, tostring(err))
	end
end
local function spawnFn(fn, ...)
	local co = type(fn) == "thread" and fn or coroutine.create(fn)
	resume(co, ...)
	return co
end
local function at(time, co, ...)
	SCHED.seq += 1
	table.insert(SCHED.timers, { time = time, seq = SCHED.seq, co = co, args = table.pack(...) })
end
local task = {
	spawn = spawnFn,
	defer = function(fn, ...)
		local co = coroutine.create(fn)
		at(SCHED.now, co, ...)
		return co
	end,
	delay = function(t, fn, ...)
		local co = coroutine.create(fn)
		at(SCHED.now + math.max(0, t or 0), co, ...)
		return co
	end,
	wait = function(t)
		local start = SCHED.now
		at(SCHED.now + math.max(t or 0, 1 / 60), coroutine.running())
		coroutine.yield()
		return SCHED.now - start
	end,
	cancel = function(co)
		for i = #SCHED.timers, 1, -1 do
			if SCHED.timers[i].co == co then
				table.remove(SCHED.timers, i)
			end
		end
	end,
}
local function runUntil(target)
	while true do
		local best, bestI
		for i, tm in ipairs(SCHED.timers) do
			if tm.time <= target and (best == nil or tm.time < best.time or (tm.time == best.time and tm.seq < best.seq)) then
				best, bestI = tm, i
			end
		end
		if not best then
			break
		end
		table.remove(SCHED.timers, bestI)
		SCHED.now = math.max(SCHED.now, best.time)
		if coroutine.status(best.co) == "suspended" then
			resume(best.co, table.unpack(best.args, 1, best.args.n))
		end
	end
	SCHED.now = math.max(SCHED.now, target)
end
local function run(seconds)
	runUntil(SCHED.now + (seconds or 0))
end

-- Signals (a handler runs in its own thread, like Roblox) -----------------------------------------------------------
local Signal = {}
Signal.__index = Signal
local function newSignal()
	return setmetatable({ handlers = {} }, Signal)
end
function Signal:Connect(fn)
	local c = { fn = fn, Connected = true }
	function c:Disconnect() c.Connected = false end
	table.insert(self.handlers, c)
	return c
end
function Signal:Once(fn)
	local c
	c = self:Connect(function(...)
		c:Disconnect()
		fn(...)
	end)
	return c
end
function Signal:Fire(...)
	for _, c in ipairs(table.clone(self.handlers)) do
		if c.Connected then
			spawnFn(c.fn, ...)
		end
	end
end

-- Instances ------------------------------------------------------------------------------------------------------
local GUIOBJ = { Frame = true, TextLabel = true, TextButton = true, ScrollingFrame = true }
local TEXTCLASS = { TextLabel = true, TextButton = true }
local BUTTONCLASS = { TextButton = true }
local IS_A = {
	Frame = { GuiObject = true, GuiBase2d = true }, TextLabel = { GuiObject = true, GuiBase2d = true }, ScrollingFrame = { GuiObject = true, GuiBase2d = true },
	TextButton = { GuiButton = true, GuiObject = true, GuiBase2d = true }, ScreenGui = { LayerCollector = true, GuiBase2d = true },
	IntValue = { ValueBase = true }, NumberValue = { ValueBase = true }, ModuleScript = { LuaSourceContainer = true },
	UICorner = { UIComponent = true }, UIStroke = { UIComponent = true }, UIPadding = { UIComponent = true }, UIListLayout = { UIComponent = true, UIGridStyleLayout = true },
	UITextSizeConstraint = { UIComponent = true, UIConstraint = true }, UISizeConstraint = { UIComponent = true, UIConstraint = true }, UIScale = { UIComponent = true },
	UIGradient = { UIComponent = true },
}
local GEN = 0 -- bumped on every write: the layout cache's key

local function guiProps(w, h)
	return {
		Size = UDim2.fromOffset(w, h), Position = UDim2.new(), AnchorPoint = v2(0, 0), Visible = true, BackgroundColor3 = Color3.fromRGB(163, 162, 165),
		BackgroundTransparency = 0, BorderSizePixel = 1, BorderColor3 = Color3.fromRGB(27, 42, 53), ZIndex = 1, LayoutOrder = 0, Rotation = 0,
		ClipsDescendants = false, Active = false, AutomaticSize = Enum.AutomaticSize.None, Selectable = false,
	}
end
local function textProps(p, text)
	p.Text = text
	p.TextColor3 = Color3.fromRGB(27, 42, 53)
	p.TextSize = 14
	p.TextScaled = false
	p.TextWrapped = false
	p.Font = Enum.Font.SourceSans
	p.TextXAlignment = Enum.TextXAlignment.Center
	p.TextYAlignment = Enum.TextYAlignment.Center
	p.TextTransparency = 0
	p.TextTruncate = Enum.TextTruncate.None
	p.RichText = false
	p.TextStrokeTransparency = 1
	p.LineHeight = 1
	return p
end
local DEFAULTS = {
	Frame = function() return guiProps(100, 100) end,
	TextLabel = function() return textProps(guiProps(200, 50), "Label") end,
	TextButton = function()
		local p = textProps(guiProps(200, 50), "Button")
		p.AutoButtonColor = true
		p.Active = true
		return p
	end,
	ScrollingFrame = function()
		local p = guiProps(100, 100)
		p.CanvasSize = UDim2.new(0, 0, 2, 0)
		p.CanvasPosition = v2(0, 0)
		p.AutomaticCanvasSize = Enum.AutomaticSize.None
		p.ScrollingDirection = Enum.ScrollingDirection.XY
		p.ScrollBarThickness = 12
		p.ScrollingEnabled = true
		p.ClipsDescendants = true
		p.Active = true
		p.ScrollBarImageTransparency = 0
		p.ScrollBarImageColor3 = Color3.new(1, 1, 1)
		return p
	end,
	ScreenGui = function() return { ResetOnSpawn = true, ZIndexBehavior = Enum.ZIndexBehavior.Global, Enabled = true, DisplayOrder = 0, IgnoreGuiInset = false } end,
	UICorner = function() return { CornerRadius = udim(0, 8) } end,
	UIStroke = function() return { Thickness = 1, Transparency = 0, ApplyStrokeMode = Enum.ApplyStrokeMode.Contextual, Color = Color3.new(0, 0, 0), Enabled = true } end,
	UIPadding = function() return { PaddingTop = udim(0, 0), PaddingBottom = udim(0, 0), PaddingLeft = udim(0, 0), PaddingRight = udim(0, 0) } end,
	UIListLayout = function()
		return { Padding = udim(0, 0), SortOrder = Enum.SortOrder.Name, FillDirection = Enum.FillDirection.Vertical,
			HorizontalAlignment = Enum.HorizontalAlignment.Left, VerticalAlignment = Enum.VerticalAlignment.Top }
	end,
	UITextSizeConstraint = function() return { MaxTextSize = 100, MinTextSize = 1 } end,
	UISizeConstraint = function() return { MaxSize = v2(math.huge, math.huge), MinSize = v2(0, 0) } end,
	UIScale = function() return { Scale = 1 } end,
	UIGradient = function() return { Rotation = 0, Offset = v2(0, 0), Enabled = true } end,
	Folder = function() return {} end,
	ModuleScript = function() return {} end,
	RemoteFunction = function() return {} end,
	RemoteEvent = function() return {} end,
	IntValue = function() return { Value = 0 } end,
	NumberValue = function() return { Value = 0 } end,
	Player = function() return { UserId = 1, DisplayName = "Tester" } end,
	PlayerGui = function() return {} end,
	DataModel = function() return {} end,
	Players = function() return {} end,
	ReplicatedStorage = function() return {} end,
	Workspace = function() return {} end,
	RunService = function() return {} end,
	GuiService = function() return { TouchControlsEnabled = true } end,
	TextService = function() return {} end,
	TweenService = function() return {} end,
	MarketplaceService = function() return {} end,
}
local SIGNALS = {
	all = { AttributeChanged = true, ChildAdded = true, ChildRemoved = true, Destroying = true, Changed = true, DescendantAdded = true },
	TextButton = { Activated = true, MouseButton1Click = true },
	RemoteEvent = { OnClientEvent = true },
	MarketplaceService = { PromptGamePassPurchaseFinished = true, PromptProductPurchaseFinished = true },
	RunService = { Heartbeat = true, RenderStepped = true },
}
local READONLY = { AbsoluteSize = true, AbsolutePosition = true, ClassName = true }

local Inst = {}
local Methods = {}
local rectOf -- the layout engine, below

local function signalOf(t, name)
	local signals = rawget(t, "_signals")
	local s = signals[name]
	if not s then
		s = newSignal()
		signals[name] = s
	end
	return s
end

Inst.__type = "Instance"
Inst.__tostring = function(t) return rawget(t, "_name") end
Inst.__index = function(t, k)
	if k == "ClassName" then return rawget(t, "_class") end
	if k == "Name" then return rawget(t, "_name") end
	if k == "Parent" then return rawget(t, "_parent") end
	local own = rawget(t, "_methods")
	if own and own[k] ~= nil then return own[k] end
	local props = rawget(t, "_props")
	local v = props[k]
	if v ~= nil then return v end
	local class = rawget(t, "_class")
	if (k == "AbsoluteSize" or k == "AbsolutePosition") and (GUIOBJ[class] or class == "ScreenGui") then
		local r = rectOf(t)
		return k == "AbsoluteSize" and v2(r.w, r.h) or v2(r.x, r.y)
	end
	if SIGNALS.all[k] or (SIGNALS[class] and SIGNALS[class][k]) then return signalOf(t, k) end
	local m = Methods[k]
	if m then return m end
	for _, c in ipairs(rawget(t, "_children")) do
		if c.Name == k then return c end
	end
	error(tostring(k) .. " is not a valid member of " .. class .. " \"" .. rawget(t, "_name") .. "\"", 2)
end

local function fireChanged(t, k)
	local props = rawget(t, "_propSignals")
	if props and props[k] then props[k]:Fire() end
	local s = rawget(t, "_signals").Changed
	if s then s:Fire(k) end
end

local function setParent(t, parent)
	if rawget(t, "_destroyed") then
		error("The Parent property of " .. rawget(t, "_name") .. " is locked, current parent: NULL", 3)
	end
	local old = rawget(t, "_parent")
	if old == parent then return end
	if old then
		local kids = rawget(old, "_children")
		for i, c in ipairs(kids) do
			if c == t then table.remove(kids, i) break end
		end
	end
	rawset(t, "_parent", parent)
	GEN += 1
	if parent then
		table.insert(rawget(parent, "_children"), t)
		local s = rawget(parent, "_signals").ChildAdded
		if s then s:Fire(t) end
		local node = parent
		while node do
			local d = rawget(node, "_signals").DescendantAdded
			if d then d:Fire(t) end
			node = rawget(node, "_parent")
		end
	end
	fireChanged(t, "Parent")
end

Inst.__newindex = function(t, k, v)
	if k == "Parent" then
		setParent(t, v)
		return
	end
	if k == "Name" then
		rawset(t, "_name", tostring(v))
		GEN += 1
		fireChanged(t, "Name")
		return
	end
	local class = rawget(t, "_class")
	if READONLY[k] then error("Unable to assign property " .. k .. ". Property is read only", 2) end
	local props = rawget(t, "_props")
	local old = props[k]
	if old == nil then error(tostring(k) .. " is not a valid member of " .. class .. " \"" .. rawget(t, "_name") .. "\"", 2) end
	local want, got = typeOf(old), typeOf(v)
	if want == "string" and got == "number" then
		v, got = tostring(v), "string"
	end
	if want ~= got or (want == "EnumItem" and old.EnumType ~= v.EnumType) then
		error("Unable to assign property " .. k .. " of " .. class .. ". " .. want .. " expected, got " .. got, 2)
	end
	if want == "number" and v ~= v then error("Unable to assign property " .. k .. ": NaN", 2) end
	props[k] = v
	GEN += 1
	if old ~= v then fireChanged(t, k) end
end

local function newInst(class)
	local maker = DEFAULTS[class]
	if not maker then error("Unable to create an Instance of type \"" .. tostring(class) .. "\"", 2) end
	local inst = setmetatable({ _class = class, _name = class, _props = maker(), _children = {}, _attrs = {}, _signals = {} }, Inst)
	return inst
end
local Instance = { new = function(class, parent)
	local inst = newInst(class)
	if parent then inst.Parent = parent end
	return inst
end }

function Methods.GetChildren(t) return table.clone(rawget(t, "_children")) end
function Methods.GetDescendants(t)
	local out = {}
	local function walk(n)
		for _, c in ipairs(rawget(n, "_children")) do
			table.insert(out, c)
			walk(c)
		end
	end
	walk(t)
	return out
end
function Methods.FindFirstChild(t, name, recursive)
	for _, c in ipairs(recursive and t:GetDescendants() or rawget(t, "_children")) do
		if c.Name == name then return c end
	end
	return nil
end
function Methods.IsA(t, class)
	local own = rawget(t, "_class")
	return class == "Instance" or own == class or (IS_A[own] ~= nil and IS_A[own][class] == true)
end
function Methods.FindFirstChildWhichIsA(t, class, recursive)
	for _, c in ipairs(recursive and t:GetDescendants() or rawget(t, "_children")) do
		if c:IsA(class) then return c end
	end
	return nil
end
function Methods.FindFirstChildOfClass(t, class)
	for _, c in ipairs(rawget(t, "_children")) do
		if c.ClassName == class then return c end
	end
	return nil
end
function Methods.WaitForChild(t, name, timeout)
	local found = t:FindFirstChild(name)
	if found or timeout then return found end
	-- no timeout: wait like Roblox, at most 60 s on the fake clock (then it is an "infinite yield")
	local waited = 0
	while not found and waited < 60 do
		waited += task.wait(0.1)
		found = t:FindFirstChild(name)
	end
	if not found then error("Infinite yield on " .. rawget(t, "_name") .. ":WaitForChild(\"" .. name .. "\")") end
	return found
end
function Methods.IsDescendantOf(t, ancestor)
	local p = rawget(t, "_parent")
	while p do
		if p == ancestor then return true end
		p = rawget(p, "_parent")
	end
	return false
end
function Methods.SetAttribute(t, k, v)
	local kind = typeOf(v)
	if v ~= nil and kind ~= "string" and kind ~= "number" and kind ~= "boolean" and kind ~= "Vector2" and kind ~= "Color3" and kind ~= "UDim2" then
		error("SetAttribute: " .. kind .. " is not a supported attribute type", 2)
	end
	local old = rawget(t, "_attrs")[k]
	rawget(t, "_attrs")[k] = v
	if old ~= v then
		local s = rawget(t, "_signals").AttributeChanged
		if s then s:Fire(k) end
		local a = rawget(t, "_attrSignals")
		if a and a[k] then a[k]:Fire() end
	end
end
function Methods.GetAttribute(t, k) return rawget(t, "_attrs")[k] end
function Methods.GetAttributes(t) return table.clone(rawget(t, "_attrs")) end
function Methods.GetAttributeChangedSignal(t, k)
	local a = rawget(t, "_attrSignals")
	if not a then
		a = {}
		rawset(t, "_attrSignals", a)
	end
	a[k] = a[k] or newSignal()
	return a[k]
end
function Methods.GetPropertyChangedSignal(t, k)
	local p = rawget(t, "_propSignals")
	if not p then
		p = {}
		rawset(t, "_propSignals", p)
	end
	p[k] = p[k] or newSignal()
	return p[k]
end
function Methods.Destroy(t)
	if rawget(t, "_destroyed") then return end
	for _, c in ipairs(table.clone(rawget(t, "_children"))) do
		c:Destroy()
	end
	local s = rawget(t, "_signals").Destroying
	if s then s:Fire() end
	setParent(t, nil)
	rawset(t, "_destroyed", true)
end
function Methods.ClearAllChildren(t)
	for _, c in ipairs(table.clone(rawget(t, "_children"))) do
		c:Destroy()
	end
end
function Methods.GetFullName(t)
	local p = rawget(t, "_parent")
	if p and rawget(p, "_class") ~= "DataModel" then return p:GetFullName() .. "." .. rawget(t, "_name") end
	return rawget(t, "_name")
end

-- The GUI layout engine ----------------------------------------------------------------------------------------
local GUI = { w = 667, h = 339 } -- the ShopGui's AbsoluteSize: the phone less Roblox's top bar
local CACHE = { gen = -1, rects = {} }

local function childOf(t, class)
	for _, c in ipairs(rawget(t, "_children")) do
		if rawget(c, "_class") == class then return c end
	end
	return nil
end

local function sizeIn(inst, inner)
	local s = inst.Size
	local w = inner.w * s.X.Scale + s.X.Offset
	local h = inner.h * s.Y.Scale + s.Y.Offset
	local limit = childOf(inst, "UISizeConstraint")
	if limit then
		w = math.clamp(w, limit.MinSize.X, limit.MaxSize.X)
		h = math.clamp(h, limit.MinSize.Y, limit.MaxSize.Y)
	end
	return w, h
end

local function padded(parent, area)
	local p = childOf(parent, "UIPadding")
	if not p then return area end
	local l = area.w * p.PaddingLeft.Scale + p.PaddingLeft.Offset
	local r = area.w * p.PaddingRight.Scale + p.PaddingRight.Offset
	local t = area.h * p.PaddingTop.Scale + p.PaddingTop.Offset
	local b = area.h * p.PaddingBottom.Scale + p.PaddingBottom.Offset
	return { x = area.x + l, y = area.y + t, w = area.w - l - r, h = area.h - t - b }
end

-- The visible GuiObject children of a parent in the order its UIListLayout puts them
local function listed(parent)
	local kids = {}
	for i, c in ipairs(rawget(parent, "_children")) do
		if GUIOBJ[rawget(c, "_class")] and c.Visible then
			table.insert(kids, { inst = c, i = i })
		end
	end
	local list = childOf(parent, "UIListLayout")
	table.sort(kids, function(a, b)
		if list.SortOrder == Enum.SortOrder.LayoutOrder and a.inst.LayoutOrder ~= b.inst.LayoutOrder then
			return a.inst.LayoutOrder < b.inst.LayoutOrder
		end
		if list.SortOrder == Enum.SortOrder.Name and a.inst.Name ~= b.inst.Name then
			return a.inst.Name < b.inst.Name
		end
		return a.i < b.i
	end)
	return kids, list
end

-- How far the children of a ScrollingFrame reach (for AutomaticCanvasSize), in the frame's own pixels
local function contentExtent(sf, window)
	local inner = padded(sf, { x = 0, y = 0, w = window.w, h = window.h })
	local p = childOf(sf, "UIPadding")
	local bottomPad = p and (window.h * p.PaddingBottom.Scale + p.PaddingBottom.Offset) or 0
	local rightPad = p and (window.w * p.PaddingRight.Scale + p.PaddingRight.Offset) or 0
	local maxX, maxY = 0, 0
	local list = childOf(sf, "UIListLayout")
	if list then
		local kids = listed(sf)
		local pos = 0
		for n, k in ipairs(kids) do
			local w, h = sizeIn(k.inst, inner)
			if list.FillDirection == Enum.FillDirection.Vertical then
				maxY = inner.y + pos + h
				maxX = math.max(maxX, inner.x + w)
				pos += h + (n < #kids and list.Padding.Offset or 0)
			else
				maxX = inner.x + pos + w
				maxY = math.max(maxY, inner.y + h)
				pos += w + (n < #kids and list.Padding.Offset or 0)
			end
		end
	else
		for _, c in ipairs(rawget(sf, "_children")) do
			if GUIOBJ[rawget(c, "_class")] and c.Visible then
				local w, h = sizeIn(c, inner)
				maxX = math.max(maxX, inner.x + c.Position.X.Offset + inner.w * c.Position.X.Scale - c.AnchorPoint.X * w + w)
				maxY = math.max(maxY, inner.y + c.Position.Y.Offset + inner.h * c.Position.Y.Scale - c.AnchorPoint.Y * h + h)
			end
		end
	end
	return maxX + rightPad, maxY + bottomPad
end

-- A ScrollingFrame's canvas: where its children are laid out (moved by CanvasPosition), in GUI pixels
local function canvasOf(sf)
	local r = rectOf(sf)
	local cs = sf.CanvasSize
	local cw = math.max(r.w, r.w * cs.X.Scale + cs.X.Offset)
	local ch = math.max(r.h, r.h * cs.Y.Scale + cs.Y.Offset)
	local auto = sf.AutomaticCanvasSize
	if auto ~= Enum.AutomaticSize.None then
		local ex, ey = contentExtent(sf, r)
		if auto == Enum.AutomaticSize.Y or auto == Enum.AutomaticSize.XY then ch = math.max(ch, ey) end
		if auto == Enum.AutomaticSize.X or auto == Enum.AutomaticSize.XY then cw = math.max(cw, ex) end
	end
	local px = math.clamp(sf.CanvasPosition.X, 0, math.max(0, cw - r.w))
	local py = math.clamp(sf.CanvasPosition.Y, 0, math.max(0, ch - r.h))
	return { x = r.x - px, y = r.y - py, w = cw, h = ch, scrollX = px, scrollY = py }
end

rectOf = function(inst)
	if CACHE.gen ~= GEN then
		CACHE.gen, CACHE.rects = GEN, {}
	end
	local hit = CACHE.rects[inst]
	if hit then return hit end
	local result
	local class = rawget(inst, "_class")
	if class == "ScreenGui" then
		result = { x = 0, y = 0, w = GUI.w, h = GUI.h }
	else
		local parent = rawget(inst, "_parent")
		local pclass = parent and rawget(parent, "_class")
		if not parent or not (GUIOBJ[pclass] or pclass == "ScreenGui") then
			result = { x = 0, y = 0, w = 0, h = 0 }
		else
			local area = pclass == "ScrollingFrame" and canvasOf(parent) or rectOf(parent)
			local inner = padded(parent, area)
			local w, h = sizeIn(inst, inner)
			local list = childOf(parent, "UIListLayout")
			local x, y
			if list then
				local kids = listed(parent)
				local pos = 0
				x, y = inner.x, inner.y
				for _, k in ipairs(kids) do
					local kw, kh = sizeIn(k.inst, inner)
					if k.inst == inst then
						if list.FillDirection == Enum.FillDirection.Vertical then y = inner.y + pos else x = inner.x + pos end
						break
					end
					pos += (list.FillDirection == Enum.FillDirection.Vertical and kh or kw) + list.Padding.Offset
				end
			else
				local p = inst.Position
				x = inner.x + inner.w * p.X.Scale + p.X.Offset - inst.AnchorPoint.X * w
				y = inner.y + inner.h * p.Y.Scale + p.Y.Offset - inst.AnchorPoint.Y * h
			end
			result = { x = x, y = y, w = w, h = h }
		end
	end
	CACHE.rects[inst] = result
	return result
end

local function overlaps(a, b)
	return a.w > 0 and a.h > 0 and b.w > 0 and b.h > 0 and a.x < b.x + b.w and b.x < a.x + a.w and a.y < b.y + b.h and b.y < a.y + a.h
end
local function inside(a, b, slack)
	slack = slack or 0
	return a.x >= b.x - slack and a.y >= b.y - slack and a.x + a.w <= b.x + b.w + slack and a.y + a.h <= b.y + b.h + slack
end
local function intersect(a, b)
	local x, y = math.max(a.x, b.x), math.max(a.y, b.y)
	local x2, y2 = math.min(a.x + a.w, b.x + b.w), math.min(a.y + a.h, b.y + b.h)
	return { x = x, y = y, w = math.max(0, x2 - x), h = math.max(0, y2 - y) }
end
local function rectText(r) return string.format("%g,%g %gx%g", r.x, r.y, r.w, r.h) end

-- Shown: the instance and every GuiObject above it Visible, under an enabled ScreenGui that is in a PlayerGui
local function shown(inst)
	local node = inst
	while node do
		local class = rawget(node, "_class")
		if class == "ScreenGui" then
			return node.Enabled and rawget(node, "_parent") ~= nil
		end
		if GUIOBJ[class] and not node.Visible then return false end
		node = rawget(node, "_parent")
	end
	return false
end

-- The part of it that can be seen: clipped by every ScrollingFrame (and ClipsDescendants frame) above it
local function visibleRect(inst)
	local r = rectOf(inst)
	local node = rawget(inst, "_parent")
	while node and rawget(node, "_class") ~= "ScreenGui" do
		if rawget(node, "_class") == "ScrollingFrame" or (GUIOBJ[rawget(node, "_class")] and node.ClipsDescendants) then
			r = intersect(r, rectOf(node))
		end
		node = rawget(node, "_parent")
	end
	return r
end

-- Roblox's text measure, estimated: Gotham at about 0.56 em a lowercase letter (bold 6 % wider), greedy word wrap,
-- 1.25 lines. Wider than the real font on purpose, so a box made from it has room to spare.
local function charWidth(ch, size, bold)
	local em
	if ch:match("^%u$") then em = 0.70
	elseif ch:match("^%l$") then em = 0.56
	elseif ch:match("^%d$") then em = 0.62
	elseif ch == " " then em = 0.28
	elseif ch:match("^[%.,:;'!|il]$") then em = 0.30
	elseif #ch > 1 then em = 1.0
	else em = 0.62 end
	return em * size * (bold and 1.06 or 1)
end
local function wordWidth(word, size, bold)
	local w = 0
	for _, cp in utf8.codes(word) do
		w += charWidth(utf8.char(cp), size, bold)
	end
	return w
end
local function measure(text, size, font, maxW)
	local bold = font == Enum.Font.GothamBold or font == Enum.Font.GothamBlack or font == Enum.Font.SourceSansBold
	local lineH = math.ceil(size * 1.25)
	local lines, widest = 0, 0
	for paragraph in (text .. "\n"):gmatch("(.-)\n") do
		lines += 1
		local lineW = 0
		for word in paragraph:gmatch("%S+") do
			local ww = wordWidth(word, size, bold)
			local space = lineW > 0 and charWidth(" ", size, bold) or 0
			if lineW > 0 and lineW + space + ww > maxW then
				lines += 1
				widest = math.max(widest, lineW)
				lineW = ww
			else
				lineW += space + ww
			end
		end
		widest = math.max(widest, lineW)
	end
	return v2(math.ceil(widest), lines * lineH)
end
-- One line of text at size: does it fit in width w (no wrap)?
local function lineFits(text, size, font, w)
	return measure(text, size, font, math.huge).X <= w
end
"""

WORLD = r"""-- The place: services, the local player with leaderstats and attributes, the shop's remotes, the real modules ------
local UPGRADES = __UPGRADES__ -- TycoonCore's UPGRADES (name, cost, income, icon): the real list the server sends
local MODULE_SOURCES = __MODULES__
local CLIENT_SOURCE = __CLIENT__
local W -- the world of the scenario that runs now

local function newWorld(opts)
	opts = opts or {}
	SCHED.timers, SCHED.now = {}, 0
	LOG.warned, LOG.errors = {}, {}
	GEN += 1
	local bar = opts.bar or 0
	GUI.w, GUI.h = opts.w or 667, (opts.h or 375) - bar
	local w = { opts = opts, studio = opts.studio == true, bar = bar, invokes = {}, prompts = {}, held = {}, modules = {}, tweens = {},
		latency = opts.latency or 0.05 }
	W = w
	local game = newInst("DataModel")
	game.Name = "Game"
	local services = {}
	local function service(class)
		local s = newInst(class)
		s.Name = class
		s.Parent = game
		services[class] = s
		return s
	end
	local players, rs, ws = service("Players"), service("ReplicatedStorage"), service("Workspace")
	local runService, guiService, textService = service("RunService"), service("GuiService"), service("TextService")
	local tweenService, market = service("TweenService"), service("MarketplaceService")
	w.game, w.rs, w.guiService, w.market = game, rs, guiService, market
	rawset(game, "_methods", { GetService = function(_, name)
		local s = services[name]
		if not s then error("no service " .. tostring(name), 2) end
		return s
	end })
	rawset(runService, "_methods", { IsStudio = function() return w.studio end, IsClient = function() return true end, IsServer = function() return false end })
	rawset(guiService, "_methods", { GetGuiInset = function() return v2(0, w.bar), v2(0, 0) end })
	rawset(textService, "_methods", { GetTextSize = function(_, text, size, font, frame)
		w.measured = (w.measured or 0) + 1
		return measure(text, size, font, frame.X)
	end })
	rawset(ws, "_methods", { GetServerTimeNow = function() return 1.8e9 + SCHED.now end })
	rawset(tweenService, "_methods", { Create = function(_, inst, info, goals)
		local tween = { Instance = inst, goals = goals, Completed = newSignal(), PlaybackState = Enum.PlaybackState.Begin }
		function tween.Play(self)
			table.insert(w.tweens, { inst = inst, goals = goals, info = info, at = SCHED.now })
			self.PlaybackState = Enum.PlaybackState.Playing
			task.delay((info.Time or 0) * (info.Reverses and 2 or 1), function()
				if self.PlaybackState ~= Enum.PlaybackState.Playing then return end
				if not info.Reverses then
					for k, v in pairs(goals) do
						inst[k] = v
					end
				end
				self.PlaybackState = Enum.PlaybackState.Completed
				self.Completed:Fire(Enum.PlaybackState.Completed)
			end)
		end
		function tween.Cancel(self) self.PlaybackState = Enum.PlaybackState.Cancelled end
		function tween.Pause(self) self.PlaybackState = Enum.PlaybackState.Paused end
		return tween
	end })
	rawset(market, "_methods", {
		PromptGamePassPurchase = function(_, who, id) table.insert(w.prompts, { kind = "pass", id = id, who = who }) end,
		PromptProductPurchase = function(_, who, id) table.insert(w.prompts, { kind = "product", id = id, who = who }) end,
	})

	local player = newInst("Player")
	player.Name = "Tester"
	player.Parent = players
	rawset(players, "_methods", { LocalPlayer = player })
	local playerGui = newInst("PlayerGui")
	playerGui.Name = "PlayerGui"
	playerGui.Parent = player
	w.player, w.playerGui = player, playerGui
	if opts.restricted == nil then
		player:SetAttribute("RandomRestricted", false)
	elseif opts.restricted ~= "unknown" then
		player:SetAttribute("RandomRestricted", opts.restricted)
	end
	for i = 1, #UPGRADES do
		player:SetAttribute("Upgrade" .. i, i <= (opts.owned or 0))
	end
	for k, v in pairs(opts.attrs or {}) do
		player:SetAttribute(k, v)
	end
	function w.addStats()
		local stats = newInst("Folder")
		stats.Name = "leaderstats"
		local cash, income = newInst("IntValue"), newInst("IntValue")
		cash.Name, income.Name = "Cash", "Income"
		cash.Value, income.Value = opts.cash or 0, opts.income or 0
		cash.Parent, income.Parent = stats, stats
		stats.Parent = player
		w.cash, w.income = cash, income
	end
	if not opts.noStats then
		w.addStats()
	end

	local folder = newInst("Folder")
	folder.Name = "ShopRemotes"
	folder.Parent = rs
	local notify = newInst("RemoteEvent")
	notify.Name = "ShopNotify"
	notify.Parent = folder
	w.notify = notify
	function w.invoke(remote, ...)
		local args = table.pack(...)
		table.insert(w.invokes, { remote = remote, args = args, at = SCHED.now })
		task.wait(w.latency)
		if w.hold then
			table.insert(w.held, coroutine.running())
			return coroutine.yield()
		end
		return w.handlers[remote](table.unpack(args, 1, args.n))
	end
	function w.release(...)
		local held = w.held
		w.held = {}
		for _, co in ipairs(held) do
			resume(co, ...)
		end
	end
	if not opts.noAction then
		local action = newInst("RemoteFunction")
		action.Name = "ShopAction"
		action.Parent = folder
		rawset(action, "_methods", { InvokeServer = function(_, ...) return w.invoke("ShopAction", ...) end })
	end
	if w.studio then
		local debugRemote = newInst("RemoteFunction")
		debugRemote.Name = "ShopDebug"
		debugRemote.Parent = folder
		rawset(debugRemote, "_methods", { InvokeServer = function(_, ...) return w.invoke("ShopDebug", ...) end })
	end
	-- A fake server for the Office and Hire tabs (overhaul 2): the same rules and messages as TycoonCore's buyUpgrade,
	-- buyBuilding, buyDesk and hireDirect (OfficeConfig's checks), and the "Office" answer
	local OCS = assert(loadstring(MODULE_SOURCES.OfficeConfig, "=OfficeConfig"))()
	local function stageNow()
		local IC = assert(loadstring(MODULE_SOURCES.IpoConfig, "=IpoConfig"))()
		return IC.stageIndex(player:GetAttribute("IpoValuation") or 0, player:GetAttribute("IpoCount") or 0)
	end
	local function ownedSet()
		local owned = {}
		for i, u in ipairs(UPGRADES) do if player:GetAttribute("Upgrade" .. i) then owned[u.name] = true end end
		return owned
	end
	w.desks, w.team = 0, 0
	w.handlers = {
		ShopAction = function(action, id)
			if action == "Upgrades" then
				local list = {}
				for _, u in ipairs(UPGRADES) do
					table.insert(list, { name = u.name, cost = u.cost, income = u.income, icon = u.icon })
				end
				return true, list
			elseif action == "Office" then
				if w.failUpgrades then return false, "not ready" end
				return true, { stage = stageNow(), building = player:GetAttribute("Building") or 1, desks = w.desks,
					capacity = OCS.workstations(w.desks, 0), team = w.team, owned = {}, hires = {} }
			elseif action == "BuyUpgrade" or action == "Hire" then
				if typeof(id) ~= "number" then return false, "Bad request" end
				if w.refuseWith then return false, w.refuseWith end
				if action == "Hire" then
					w.team += 1
					return true, "Hired"
				end
				local item, why = OCS.checkItem(id, stageNow(), ownedSet(), w.cash.Value)
				if not item then return false, why end
				w.cash.Value -= item.price
				w.income.Value += item.income
				player:SetAttribute("Upgrade" .. id, true)
				return true, "Bought " .. item.key
			elseif action == "BuyBuilding" then
				local building, n = OCS.checkBuilding(player:GetAttribute("Building") or 1, stageNow(), w.cash.Value)
				if not building then return false, n end
				w.cash.Value -= building.price
				player:SetAttribute("Building", n)
				return true, "Your new " .. building.name
			elseif action == "BuyDesk" then
				local desk, why = OCS.checkDesk(w.desks, stageNow(), w.cash.Value, OCS.workstations(w.desks, 0))
				if not desk then return false, why end
				w.cash.Value -= desk.price
				w.desks += 1
				return true, "New desk"
			end
			return false, "Unknown action"
		end,
		ShopDebug = function(action, key) return "Debug " .. tostring(action) .. " done" end,
	}

	for name, source in pairs(MODULE_SOURCES) do
		if not (opts.without and opts.without[name]) then
			local m = newInst("ModuleScript")
			m.Name = name
			rawset(m, "_source", source)
			m.Parent = rs
		end
	end
	function w.require(m)
		local cached = w.modules[m]
		if cached ~= nil then return cached end
		local fn, err = loadstring(rawget(m, "_source"), "=" .. m.Name)
		if not fn then error(m.Name .. " does not compile: " .. tostring(err)) end
		setfenv(fn, w.env)
		local value = fn()
		w.modules[m] = value
		return value
	end
	function w.module(name) return w.require(rs:FindFirstChild(name)) end
	w.env = {
		game = game, workspace = ws, Instance = Instance, UDim2 = UDim2, UDim = UDim, Vector2 = Vector2, Color3 = Color3, Enum = Enum,
		TweenInfo = TweenInfo, task = task, typeof = typeOf, require = function(m) return w.require(m) end,
		warn = function(...)
			local parts = {}
			for i = 1, select("#", ...) do parts[i] = tostring((select(i, ...))) end
			table.insert(LOG.warned, table.concat(parts, " "))
		end,
		print = function() end, pcall = pcall, xpcall = xpcall, error = error, assert = assert, tostring = tostring, tonumber = tonumber,
		type = type, select = select, next = next, pairs = pairs, ipairs = ipairs, math = math, string = string, table = table, utf8 = utf8,
		coroutine = coroutine, setmetatable = setmetatable, getmetatable = getmetatable, rawget = rawget, rawset = rawset, rawequal = rawequal,
		unpack = table.unpack, os = { time = function() return math.floor(1.8e9 + SCHED.now) end, clock = function() return SCHED.now end },
		tick = function() return 1.8e9 + SCHED.now end,
	}
	function w.start(source)
		local fn, err = loadstring(source or CLIENT_SOURCE, "=ShopClient")
		if not fn then
			table.insert(LOG.errors, "ShopClient does not compile: " .. tostring(err))
			return
		end
		setfenv(fn, w.env)
		w.thread = spawnFn(fn)
		run(0)
	end
	-- The phone turns or changes: a new GUI size (and top bar), like Roblox's AbsoluteSize change
	function w.resize(sw, sh, newBar)
		w.bar = newBar or w.bar
		GUI.w, GUI.h = sw, sh - w.bar
		GEN += 1
		for _, g in ipairs(playerGui:GetChildren()) do
			local p = rawget(g, "_propSignals")
			if p and p.AbsoluteSize then p.AbsoluteSize:Fire() end
		end
		run(0)
	end
	return w
end

-- Helpers for the scenarios -------------------------------------------------------------------------------------
local function find(root, name) return root and root:FindFirstChild(name, true) end
local function kid(inst, name) return inst and inst:FindFirstChild(name) end -- nil when either is missing (never an error)
local function prop(inst, key, default)
	if inst == nil then return default end
	return inst[key]
end
local function rectOrEmpty(inst) return inst and rectOf(inst) or { x = 0, y = 0, w = 0, h = 0 } end
local function tap(button, label)
	if not button then
		check(label .. ": the button exists", false)
		return false
	end
	local vr = visibleRect(button)
	if not shown(button) or vr.w < 1 or vr.h < 1 then
		check(label .. ": the button can be tapped (shown, not scrolled away)", false, button:GetFullName())
		return false
	end
	local s = rawget(button, "_signals").Activated
	if s then s:Fire() end
	run(0)
	return true
end
local function textOf(inst) return inst and inst.Text or "" end
-- Scrolls the page a card is on so the whole card shows (like a player's thumb would)
local function scrollTo(card)
	local page = card and card.Parent
	if not (page and page.ClassName == "ScrollingFrame") then return end
	local canvas, view = canvasOf(page), rectOf(page)
	local r = rectOf(card)
	page.CanvasPosition = v2(0, math.max(0, (r.y - canvas.y) - 4))
	run(0)
end
local function lower(s) return string.lower(s or "") end
local D9_WORDS = { "odds", "chance", "luck", "random" }
local function d9Word(text)
	for _, word in ipairs(D9_WORDS) do
		if string.find(lower(text), word, 1, true) then return word end
	end
	return nil
end
"""

LAYOUT_TESTS = r"""-- Tests: ShopLayout's pure functions (rectangles in GUI pixels) ---------------------------------------------------
local ShopLayout = (function()
	local fn, err = loadstring(MODULE_SOURCES.ShopLayout, "=ShopLayout")
	if not fn then
		check("ShopLayout.lua compiles", false, err)
		return {}
	end
	local ok, module = pcall(fn)
	check("ShopLayout.lua loads without an error and returns its table", ok and type(module) == "table", module)
	return ok and type(module) == "table" and module or {}
end)()
local SIZES = { { 667, 375 }, { 320, 568 }, { 568, 320 }, { 640, 360 }, { 844, 390 } }
local BARS = { 0, 36, 58 }
-- With the Studio Debug tab (5 tabs) the rail needs a scroll on the lowest window (568x320 under a 58 px top bar); the
-- 4 tabs of a live game never do. The bottom slot never takes room from the rail.
local RAIL_SCROLLS = { ["568x320/58"] = true }

local function headerItems(L) return { title = L.title, help = L.help, close = L.close } end
-- The window's rectangles at every phone, top bar, tab count and bottom slot -----------------------------------------
for _, size in ipairs(SIZES) do
	for _, bar in ipairs(BARS) do
		local key0 = size[1] .. "x" .. size[2] .. "/" .. bar
		for _, tabs in ipairs({ 4, 5 }) do
			local base = ShopLayout.layout(size[1], size[2] - bar, bar, tabs, 0)
			for _, slot in ipairs({ "none", "strip", "long message" }) do
				local bottomH = slot == "strip" and base.stripH or (slot == "long message" and 72 or 0)
				local L = ShopLayout.layout(size[1], size[2] - bar, bar, tabs, bottomH)
				local label = "layout " .. key0 .. " (" .. tabs .. " tabs, " .. slot .. ")"
				local c = L.content
				check(label .. ": the window stays inside the GUI", L.window.w > 0 and L.window.h > 0 and inside(L.window, L.gui), rectText(L.window))
				check(label .. ": the device is the GUI plus the top bar (it moves nothing)", L.device.w == size[1] and L.device.h == size[2] and L.window.y >= 0)
				check(label .. ": header items are 44 px tall, \"?\" and X 44 x 44",
					L.title.h == 44 and L.help.w == 44 and L.help.h == 44 and L.close.w == 44 and L.close.h == 44, rectText(L.help))
				local bad
				local items = headerItems(L)
				for a, ra in pairs(items) do
					if not inside(ra, c) then bad = a .. " outside the window" end
					for b, rb in pairs(items) do
						if a < b and overlaps(ra, rb) then bad = a .. " on " .. b end
					end
				end
				check(label .. ": header items never overlap and stay inside the window", bad == nil, bad)
				check(label .. ": \"?\" is left of the X with a 6 px gap", L.help.x + L.help.w + 6 == L.close.x and L.help.y == L.close.y)
				bad = nil
				for i, t in ipairs(L.tabs) do
					if t.w < 44 or t.h < 44 then bad = "tab " .. i .. " is " .. t.w .. " x " .. t.h end
				end
				check(label .. ": every tab is at least 44 x 44", bad == nil and #L.tabs == tabs, bad)
				bad = nil
				for i, t in ipairs(L.tabs) do
					for j, u in ipairs(L.tabs) do
						if i < j and overlaps(t, u) then bad = "tab " .. i .. " on tab " .. j end
					end
					for name, r in pairs(items) do
						if overlaps(t, r) then bad = "tab " .. i .. " on the " .. name end
					end
					if overlaps(t, L.pages) then bad = "tab " .. i .. " on the pages" end
					if L.bottom and overlaps(t, L.bottom) then bad = "tab " .. i .. " on the bottom slot" end
				end
				check(label .. ": tabs never overlap each other, the header, the pages or the bottom slot", bad == nil, bad)
				local landscape = size[1] > size[2]
				check(label .. ": landscape has the tab rail on the left (112 wide), portrait the row under the header (decided by the owner)",
					L.rail == landscape and (landscape and L.tabBar.w == 112 and L.tabBar.x == c.x and L.tabs[1].w == 112
						or not landscape and L.tabBar.y == c.y + 50 and L.tabs[1].y == c.y + 50 and L.tabBar.w == c.w))
				local scrollKey = key0
				local mayScroll = tabs == 5 and RAIL_SCROLLS[scrollKey] == true
				local allIn = true
				for _, t in ipairs(L.tabs) do
					if not inside(t, L.tabBar) then allIn = false end
				end
				check(label .. ": the tabs fit without a scroll (a live game has 4 tabs; the listed Studio cases scroll)",
					(not L.tabScrolls and allIn) or (mayScroll and L.tabScrolls), scrollKey)
				check(label .. ": the pages sit under the header, beside or under the tabs, inside the window",
					inside(L.pages, c) and L.pages.y >= L.title.y + 44 and not overlaps(L.pages, L.tabBar) and L.pages.h > 0, rectText(L.pages))
				if bottomH > 0 then
					check(label .. ": the bottom slot is as tall as asked, under the pages and as wide (never over them or the rail)",
						L.bottom.h == bottomH and L.bottom.y >= L.pages.y + L.pages.h + 6 and inside(L.bottom, c) and not overlaps(L.bottom, L.pages)
							and L.bottom.x == L.pages.x and L.bottom.w == L.pages.w and not overlaps(L.bottom, L.tabBar), rectText(L.bottom))
				else
					check(label .. ": no bottom slot: the pages reach the window's bottom", L.bottom == nil and L.pages.y + L.pages.h == c.y + c.h)
				end
				check(label .. ": the help card covers the pages and the bottom slot, never the header or the tabs",
					inside(L.pages, L.helpCard) and (L.bottom == nil or inside(L.bottom, intersect(L.bottom, L.helpCard)) and L.helpCard.y + L.helpCard.h == c.y + c.h)
						and not overlaps(L.helpCard, L.title) and not overlaps(L.helpCard, L.help) and not overlaps(L.helpCard, L.close)
						and not overlaps(L.helpCard, L.tabBar), rectText(L.helpCard))
				check(label .. ": cards are as wide as the pages less the scrollbar room", L.cardW == L.pages.w - ShopLayout.SCROLLBAR_ROOM)
				if slot == "strip" then
					check(label .. ": with the TutorialStrip the pages keep room for the Office hero card (132 px)", L.pages.h >= 132, L.pages.h)
					check(label .. ": the strip is 32 px on a short window, 48 otherwise", L.bottom.h == (L.window.h < 330 and 32 or 48))
				end
				check(label .. ": the toast is at the bottom center, 48 tall, at most 520 wide, inside the GUI",
					L.toast.h == 48 and L.toast.w <= 520 and inside(L.toast, L.gui) and L.toast.y + L.toast.h == L.gui.h - 16
						and math.abs((L.toast.x + L.toast.w / 2) - L.gui.w / 2) <= 1)
			end
		end
	end
end

-- The tab labels (measured at 16 px): a portrait row fits every label, sharing the row evenly when it can, scrolling
-- sideways only when even the labels' own widths are too wide (Studio's five tabs on a 320 px phone) --------------
for _, size in ipairs(SIZES) do
	for _, bar in ipairs(BARS) do
		for _, tabs in ipairs({ 4, 5 }) do
			local labels = {}
			for i = 1, tabs do labels[i] = measure(({ "Office", "Passes", "Boosts", "Cash", "Debug" })[i], 16, Enum.Font.GothamBold, math.huge).X end
			local L = ShopLayout.layout(size[1], size[2] - bar, bar, tabs, 0, labels)
			local label = "tab labels " .. size[1] .. "x" .. size[2] .. "/" .. bar .. " (" .. tabs .. " tabs)"
			local narrow, bad
			for i, r in ipairs(L.tabs) do
				if r.w < labels[i] + 2 * ShopLayout.TAB_TEXT_PAD or r.w < 44 or r.h < 44 then narrow = "tab " .. i .. " " .. r.w .. " for " .. labels[i] end
				for j, u in ipairs(L.tabs) do
					if i < j and overlaps(r, u) then bad = "tab " .. i .. " on tab " .. j end
				end
				if L.rail and not inside(r, L.tabBar) and not L.tabScrolls then bad = "tab " .. i .. " outside the rail" end
			end
			check(label .. ": every tab is as wide as its label at 16 px (and 44 x 44 or more)", narrow == nil, narrow)
			check(label .. ": tabs never overlap", bad == nil, bad)
			local last = L.tabs[tabs]
			local reach = L.rail and (last.y + last.h - L.tabBar.y) or (last.x + last.w - L.tabBar.x)
			check(label .. ": the row's canvas reaches the last tab, and it scrolls exactly when the tabs are longer than the bar",
				L.tabCanvas == reach and L.tabScrolls == (L.tabCanvas > (L.rail and L.tabBar.h or L.tabBar.w)), L.tabCanvas .. " / " .. reach)
			if not L.rail then
				local even = true
				for i = 2, tabs do if L.tabs[i].w ~= L.tabs[1].w then even = false end end
				check(label .. ": a live game's four tabs share the portrait row evenly and never scroll", tabs == 5 or (even and not L.tabScrolls))
				check(label .. ": a row that scrolls has room for its bar under the tabs, and the pages start under it",
					L.tabBar.h == 44 + (L.tabScrolls and ShopLayout.TAB_SCROLLBAR or 0) and L.pages.y >= L.tabBar.y + L.tabBar.h + 6, L.tabBar.h)
				if size[1] == 320 and tabs == 5 then
					check(label .. ": Studio's five tabs scroll sideways at 320 px (their labels need more than the row)", L.tabScrolls)
				end
			end
		end
	end
end

-- The tutorial strip's text limit (TutorialConfig's authors): characters per phone, from the tests' own estimate ------
do
	local SAMPLE = "Tap Get it free to buy your first Desk. Each upgrade adds Cash every second, so buy the next one as soon as its bar is full and watch your Income grow."
	local wrong, loose, flagged
	for _, size in ipairs(SIZES) do
		for _, bar in ipairs(BARS) do
			local key = size[1] .. "x" .. size[2] .. "/" .. bar
			local limit = ShopLayout.stripMaxChars(size[1], size[2] - bar, bar)
			local L = ShopLayout.layout(size[1], size[2] - bar, bar, 4, 0)
			local strip = ShopLayout.layout(size[1], size[2] - bar, bar, 4, L.stripH).bottom
			local lines = L.short and 1 or 2
			-- a real sentence of exactly the limit fits the strip by the estimate (16 px bold, greedy word wrap)
			local text = string.sub(SAMPLE, 1, limit)
			if measure(text, 16, Enum.Font.GothamBold, strip.w).Y > lines * math.ceil(16 * 1.25) then loose = key .. ": " .. limit .. " characters need more than " .. lines .. " lines" end
			-- and the limit is not far under what fits: a sentence 14 characters longer no longer fits
			local longer = string.sub(SAMPLE, 1, limit + 14)
			if measure(longer, 16, Enum.Font.GothamBold, strip.w).Y <= lines * math.ceil(16 * 1.25) then wrong = key .. ": " .. (limit + 14) .. " characters still fit " .. lines .. " lines" end
			local ok1, n1 = ShopLayout.stripFits(string.rep("a", limit), size[1], size[2] - bar, bar)
			local ok2, n2, max2 = ShopLayout.stripFits(string.rep("a", limit + 1), size[1], size[2] - bar, bar)
			if not ok1 or ok2 or n1 ~= limit or n2 ~= limit + 1 or max2 ~= limit then flagged = key end
		end
	end
	check("strip limit: a sentence as long as stripMaxChars fits the strip on every phone and top bar (the tests' text estimate)", loose == nil, loose)
	check("strip limit: the limit is close to what fits (14 more characters do not)", wrong == nil, wrong)
	check("strip limit: stripFits flags a text one character over the limit and accepts one at the limit", flagged == nil, flagged)
	check("strip limit: the smallest landscape phone (568 x 320, 382 px strip) gives about 40 characters, STRIP_TEXT_LIMIT, at every top bar",
		ShopLayout.STRIP_TEXT_LIMIT == 40 and ShopLayout.stripMaxChars(568, 320, 0) == 40 and ShopLayout.stripMaxChars(568, 284, 36) == 40
			and ShopLayout.stripMaxChars(568, 262, 58) == 40 and ShopLayout.layout(568, 262, 58, 4, 32).bottom.w == 382, ShopLayout.STRIP_TEXT_LIMIT)
	local smallest = math.huge
	for _, size in ipairs(SIZES) do
		for _, bar in ipairs(BARS) do smallest = math.min(smallest, ShopLayout.stripMaxChars(size[1], size[2] - bar, bar)) end
	end
	check("strip limit: STRIP_TEXT_LIMIT is the smallest of every phone's limit (one text fits them all)", smallest == ShopLayout.STRIP_TEXT_LIMIT, smallest)
	check("strip limit: stripFits counts characters, not bytes (an accented letter is one)", select(2, ShopLayout.stripFits("Café", 568, 320, 0)) == 4)
end

-- The reference phones of docs/SHOP_UX_PROPOSAL.md 3.10 (a 36 px top bar)
do
	local L = ShopLayout.layout(667, 339, 36, 4, 0)
	local c = L.content
	check("layout 667x375/36: the window is 613 x 311 (the proposal's 614 x 312, rounded down), 10 px of padding",
		L.window.w == 613 and L.window.h == 311 and c.w == 593 and c.h == 291, rectText(L.window))
	check("layout 667x375/36: the rail is x 0-112 of the window's inside, tabs 112 x 44, 6 apart, from its top",
		L.tabs[1].x - c.x == 0 and L.tabs[1].y == c.y and L.tabs[2].y - L.tabs[1].y == 50 and L.tabs[4].w == 112)
	check("layout 667x375/36: the pages are x 120 to the right edge, y 50 to the bottom (473 x 241)",
		L.pages.x - c.x == 120 and L.pages.y - c.y == 50 and L.pages.w == 473 and L.pages.h == 241, rectText(L.pages))
	check("layout 667x375/36: the title is 367 wide, right of the rail (the proposal's 488 was a full-width header)", L.title.w == 367 and L.title.x == c.x + 120)
	local P = ShopLayout.layout(320, 532, 36, 4, 0)
	local pc = P.content
	check("layout 320x568/36: four tabs of 64 x 44 at y 50-94, pages 274 x 350 at y 100, title 168 wide",
		P.tabs[1].w == 64 and P.tabs[1].h == 44 and P.tabs[1].y - pc.y == 50 and P.pages.y - pc.y == 100 and P.pages.w == 274 and P.pages.h == 350 and P.title.w == 168,
		rectText(P.pages))
	check("layout 320x568/36: with the strip (48 + 6 px) the pages keep 296 px", ShopLayout.layout(320, 532, 36, 4, 48).pages.h == 296)
	check("layout 667x375/36: with the strip (32 + 6 px) the pages keep 203 px", ShopLayout.layout(667, 339, 36, 4, 32).pages.h == 203)
end

-- Bad sizes never give a negative or broken rectangle
do
	local ok = true
	for _, args in ipairs({ { 0, 0 }, { -50, 200 }, { 0 / 0, 100 }, { math.huge, 300 }, { 100, 40 } }) do
		local L = ShopLayout.layout(args[1], args[2], 0, 4, 0)
		for _, r in ipairs({ L.window, L.content, L.title, L.help, L.close, L.pages, L.tabBar, L.helpCard }) do
			if r.w < 0 or r.h < 0 or r.w ~= r.w or r.h ~= r.h or r.x ~= r.x then ok = false end
		end
	end
	check("layout: a zero, negative, NaN or huge GUI never gives a negative or NaN rectangle", ok)
end

-- Cards: one Robux or Debug card's pieces, every width from 200 to 640, every measured text height
do
	local problems = {}
	for cardW = 200, 640, 8 do
		local nameW, descW = ShopLayout.cardWidths(cardW)
		for _, nameH in ipairs({ 0, 20, 40, 60 }) do
			for _, descH in ipairs({ 0, 20, 40, 100, 220 }) do
				local C = ShopLayout.card(cardW, nameH, descH)
				local card = { x = 0, y = 0, w = cardW, h = C.height }
				local pieces = { icon = C.icon, name = C.name, desc = C.desc, button = C.button }
				for n, r in pairs(pieces) do
					if not inside(r, card) then table.insert(problems, cardW .. ": " .. n .. " outside the card") end
					for m, s in pairs(pieces) do
						if n < m and overlaps(r, s) then table.insert(problems, cardW .. ": " .. n .. " on " .. m) end
					end
				end
				if C.button.w < 44 or C.button.h ~= 48 then table.insert(problems, cardW .. ": button " .. C.button.w .. " x " .. C.button.h) end
				if C.name.h < nameH or C.desc.h < descH then table.insert(problems, cardW .. ": a text box shorter than its text") end
				if C.name.w ~= nameW or C.desc.w ~= descW then table.insert(problems, cardW .. ": wraps at another width than cardWidths") end
				if C.narrow ~= (cardW < ShopLayout.WIDE_CARD) then table.insert(problems, cardW .. ": narrow is wrong") end
				if C.narrow and C.desc.y < C.button.y + C.button.h then table.insert(problems, cardW .. ": narrow description beside the button") end
			end
		end
	end
	check("cards: every piece inside its card, none on another, a 48 px button at least 44 wide, boxes as tall as their texts", #problems == 0, problems[1])
	check("cards: the wide layout keeps today's 84 px card for two lines", ShopLayout.card(463, 0, 40).height == 84)
end

-- The help card: a title row with a 44 px Back button, then its lines, one under the other
do
	local H = ShopLayout.helpCard(473, 241, { 38, 38, 38 })
	local card = { x = 0, y = 0, w = 473, h = 241 }
	local ok = H.back.w >= 44 and H.back.h >= 44 and inside(H.title, card) and inside(H.back, card) and not overlaps(H.title, H.back) and #H.lines == 3
	for i, r in ipairs(H.lines) do
		if overlaps(r, H.back) or overlaps(r, H.title) or (i > 1 and overlaps(r, H.lines[i - 1])) or r.h ~= 38 then ok = false end
	end
	check("help card: the Back button is a 44 px tap target, the title and the lines never overlap", ok)
	check("help card: fits says whether the lines need a scroll", H.fits == (H.height <= 241) and ShopLayout.helpCard(473, 100, { 38, 38, 38 }).fits == false)
end
"""

LADDER_TESTS = r"""-- Tests: the Office ladder's pure functions (ShopLayout.ladder, barFill, timeText, officeRow, hero, stack) ---------
-- Overhaul 2: the Office tab is the catalog by stage now (OFFICE_TESTS); the ladder's pure functions stay in ShopLayout and
-- are still checked here on the six garage upgrades as they were (name, price, income), their own fixed list.
local UPGRADES = { { name = "Desk", cost = 0, income = 1, icon = "🪑" }, { name = "Coffee Machine", cost = 25, income = 2, icon = "☕" },
	{ name = "Laptop", cost = 100, income = 5, icon = "💻" }, { name = "Server Rack", cost = 400, income = 15, icon = "🗄️" },
	{ name = "Whiteboard", cost = 1500, income = 40, icon = "📋" }, { name = "Neon Logo", cost = 5000, income = 120, icon = "💡" } }
do
	local ShopConfigPure = (function()
		local fn = assert(loadstring(MODULE_SOURCES.ShopConfig, "=ShopConfig"))
		setfenv(fn, setmetatable({ warn = function() end }, { __index = _G }))
		return fn()
	end)()
	local money = ShopConfigPure.formatCash
	local N = #UPGRADES
	check("ladder: the fixed list is the six garage upgrades", N == 6 and UPGRADES[1].name == "Desk" and UPGRADES[1].cost == 0)
	local function ownedPrefix(k)
		local owned = {}
		for i = 1, N do owned[i] = i <= k end
		return owned
	end
	for k = 0, N do
		local nextUpg = UPGRADES[k + 1]
		local cashes = nextUpg and { math.max(0, nextUpg.cost - 1), nextUpg.cost, nextUpg.cost + 100 } or { 0, 1e6 }
		for _, cash in ipairs(cashes) do
			for _, income in ipairs({ 0, 3 }) do
				local S = ShopLayout.ladder(UPGRADES, ownedPrefix(k), cash, income, money)
				local label = "ladder: " .. k .. " owned, $" .. cash .. ", $" .. income .. "/s"
				check(label .. ": the next rung is the first not owned (k + 1)", S.nextIndex == (k < N and k + 1 or nil) and S.owned == k, S.nextIndex)
				local earned = 0
				for i = 1, k do earned += UPGRADES[i].income end
				if k == 0 then
					check(label .. ": no summary row while nothing is owned", S.summary == nil)
				else
					check(label .. ": the summary says k of 6 bought and what they earn",
						S.summary and S.summary.title == k .. " of 6 bought" and S.summary.info == "+" .. money(earned) .. "/s" and S.incomeOwned == earned,
						S.summary and S.summary.title)
				end
				local rowsOk = true
				for i = 1, N do
					local row = S.rows[i]
					if i <= k then
						if row.state ~= "owned" or row.button ~= "Owned" or row.info ~= "+" .. money(UPGRADES[i].income) .. "/s" then rowsOk = false end
					elseif i == k + 1 then
						if row.state ~= "next" then rowsOk = false end
					else
						if row.state ~= "locked" or row.button ~= nil or row.info ~= "Unlocks after " .. UPGRADES[i - 1].name then rowsOk = false end
					end
				end
				check(label .. ": owned rungs say Owned, locked rungs say Unlocks after <the one before> and offer no button", rowsOk)
				if k == N then
					check(label .. ": all six bought: the Office complete banner, no hero",
						S.complete and S.hero == nil and S.banner and S.banner.title == "Office complete" and S.banner.info == "Your next step: the IPO window")
				else
					local H = S.hero
					local cost = nextUpg.cost
					local wantButton = cost == 0 and "Get it free" or (cash >= cost and ("Buy " .. money(cost)) or ("Need " .. money(cost - cash) .. " more"))
					check(label .. ": the hero's button (Get it free, Buy $X, or Need $X more when the Cash is short)", H and H.button == wantButton, H and H.button)
					check(label .. ": only a free or affordable hero offers a buy; short is action short (nothing sent)",
						H and H.action == ((cost == 0 or cash >= cost) and "buy" or "short") and H.color == ((cost == 0 or cash >= cost) and "buy" or "disabled"))
					check(label .. ": the bar fill is the Cash against the price, clamped to 0..1",
						H and H.fill >= 0 and H.fill <= 1 and H.fill == (cost == 0 and 1 or math.min(cash / cost, 1)), H and H.fill)
					check(label .. ": the bar text is $Cash / $price (the Cash shown up to the price), Free for the Desk",
						H and H.progress == (cost == 0 and "Free" or (money(math.min(cash, cost)) .. " / " .. money(cost))), H and H.progress)
					local wantTime = (cash < cost and income > 0) and ("about " .. math.ceil((cost - cash) / income) .. " s") or nil
					check(label .. ": the time is about N s from the Income, none when the Cash is there or the Income is 0", H and H.time == wantTime, H and H.time)
					check(label .. ": the hero says what it earns every second", H and H.info == "+" .. money(nextUpg.income) .. " every second" and H.index == k + 1)
					check(label .. ": and has the short form for a narrow box (+$X/s)", H and H.infoShort == "+" .. money(nextUpg.income) .. "/s", H and H.infoShort)
					check(label .. ": not complete while a rung is left", not S.complete and S.banner == nil)
				end
			end
		end
	end
	-- busy and just bought
	local busy = ShopLayout.ladder(UPGRADES, ownedPrefix(1), 999, 1, money, nil, true)
	check("ladder: while the request runs the hero says ... and sends nothing more", busy.hero.button == "..." and busy.hero.action == "wait")
	local bought = ShopLayout.ladder(UPGRADES, ownedPrefix(2), 0, 1, money, 2)
	check("ladder: the upgrade just bought stays the hero a moment: Bought!, a full bar, no buy",
		bought.nextIndex == 2 and bought.hero.button == "Bought!" and bought.hero.action == "wait" and bought.hero.fill == 1 and bought.owned == 1)
	-- owned is not a prefix (never in the game, but never a crash): the first not owned is the hero
	local holes = ShopLayout.ladder(UPGRADES, { true, false, true, false, false, false }, 0, 0, money)
	check("ladder: with a hole in the owned list the first not owned is the hero", holes.nextIndex == 2 and holes.rows[3].state == "owned" and holes.rows[4].info == "Unlocks after Laptop")
	check("ladder: an empty list is neither complete nor broken", ShopLayout.ladder({}, {}, 0, 0, money).complete == false)

	-- barFill and timeText never give a broken number
	local values = { -5, 0, 0.5, 1, 7, 25, 1e9, 0 / 0, math.huge, -math.huge }
	local fillOk, timeOk, bad = true, true, nil
	for _, a in ipairs(values) do
		for _, b in ipairs(values) do
			local f = ShopLayout.barFill(a, b)
			if not (f >= 0 and f <= 1) then fillOk, bad = false, a .. "/" .. b end
			for _, c in ipairs(values) do
				local text = ShopLayout.timeText(a, b, c)
				if text ~= nil then
					local n, unit = string.match(text, "^about (%d+) ([smh]i?n?)$")
					if not n or tonumber(n) < 1 or tonumber(n) > 99999 then timeOk, bad = false, text end
				end
			end
		end
	end
	check("barFill stays in 0..1 for every Cash and price (negative, NaN, huge, a free price)", fillOk, bad)
	check("timeText is never negative, zero, NaN or infinite (nil, or about N s, min or h)", timeOk, bad)
	check("barFill: a free upgrade is full, $12 of $25 is 0.48", ShopLayout.barFill(0, 0) == 1 and ShopLayout.barFill(12, 25) == 0.48 and ShopLayout.barFill(50, 25) == 1)
	check("timeText: $25 at $1/s is about 25 s, at $2/s about 13 s (rounded up)", ShopLayout.timeText(0, 25, 1) == "about 25 s" and ShopLayout.timeText(0, 25, 2) == "about 13 s")
	check("timeText: 5,000 s reads about 84 min, a million about 278 h", ShopLayout.timeText(0, 5000, 1) == "about 84 min" and ShopLayout.timeText(0, 1e6, 1) == "about 278 h")
	check("timeText: none when the Cash is there or the Income is 0", ShopLayout.timeText(25, 25, 1) == nil and ShopLayout.timeText(0, 25, 0) == nil and ShopLayout.timeText(30, 25, 0) == nil)

	-- BEST VALUE: computed from ShopConfig, never on an item that is not for sale
	local function all() return true end
	local products = ShopConfigPure.Products
	check("BEST VALUE is the Vault (180 minutes for R$ 299 beat 45 for 99 and 10 for 29)", ShopLayout.bestValue(products, all) == "CashLarge")
	local function find(key) for _, p in ipairs(products) do if p.key == key then return p end end end
	local medium = find("CashMedium")
	local saved = medium.effect.incomeMinutes
	medium.effect.incomeMinutes = 400
	check("BEST VALUE moves when the config's minutes change (Bag of Cash at 400 minutes)", ShopLayout.bestValue(products, all) == "CashMedium")
	medium.effect.incomeMinutes = saved
	check("BEST VALUE is never on a Coming soon item (the Vault not on sale: the Bag)",
		ShopLayout.bestValue(products, function(p) return p.key ~= "CashLarge" end) == "CashMedium"
			and ShopLayout.bestValue(products, function() return false end) == nil)
	check("BEST VALUE only looks at Cash packs (Luck Boost, Instant Hatch and Poach Shield have no minutes of Income)",
		ShopLayout.bestValue({ find("LuckBoost"), find("PoachShield") }, all) == nil)

	-- The Office rows and the hero: every piece inside, nothing on another (the badge sits on the icon's corner)
	local problems = {}
	for width = 200, 640, 8 do
		for _, kind in ipairs({ "owned", "locked", "summary", "banner" }) do
			local R = ShopLayout.officeRow(width, kind)
			local box = { x = 0, y = 0, w = width, h = R.height }
			local pieces = { icon = R.icon, badge = R.badge, name = R.name, info = R.info, button = R.button }
			for a, ra in pairs(pieces) do
				if not inside(ra, box) then table.insert(problems, kind .. " " .. width .. ": " .. a .. " outside") end
				for b, rb in pairs(pieces) do
					if a < b and overlaps(ra, rb) and not ((a == "badge" and b == "icon") or (a == "icon" and b == "badge")) then
						table.insert(problems, kind .. " " .. width .. ": " .. a .. " on " .. b)
					end
				end
			end
			if R.height ~= (width < ShopLayout.OFFICE_WIDE and 72 or 64) then table.insert(problems, kind .. " " .. width .. ": height " .. R.height) end
			if R.button and (R.button.h ~= 48 or R.button.w < 44) then table.insert(problems, kind .. " " .. width .. ": button") end
			if (kind == "owned" or kind == "summary") ~= (R.button ~= nil) then table.insert(problems, kind .. " " .. width .. ": button or not") end
			if R.name.h < 20 or R.info.h < 20 then table.insert(problems, kind .. " " .. width .. ": a text box under 20 px") end
		end
		local H = ShopLayout.hero(width)
		local box = { x = 0, y = 0, w = width, h = H.height }
		local pieces = { icon = H.icon, name = H.name, info = H.info, bar = H.bar, progress = H.progress, time = H.time, status = H.status, button = H.button }
		for a, ra in pairs(pieces) do
			if not inside(ra, box) then table.insert(problems, "hero " .. width .. ": " .. a .. " outside") end
			for b, rb in pairs(pieces) do
				local shared = H.statusSharesTime and ((a == "status" and b == "time") or (a == "time" and b == "status"))
				if a < b and overlaps(ra, rb) and not shared then table.insert(problems, "hero " .. width .. ": " .. a .. " on " .. b) end
			end
		end
		if H.button.h ~= 48 or H.button.w < 120 then table.insert(problems, "hero " .. width .. ": button " .. H.button.w) end
		if H.height ~= (width < ShopLayout.OFFICE_WIDE and 202 or 132) then table.insert(problems, "hero " .. width .. ": height") end
		if H.icon.w ~= 72 or H.icon.h ~= 72 then table.insert(problems, "hero " .. width .. ": the icon is not 72 px") end
	end
	check("office rows and the hero: every piece inside, none on another, 48 px buttons, 64 or 72 px rows, a 132 or 202 px hero", #problems == 0, problems[1])

	-- The Office page top to bottom, and the scroll that shows the hero
	local ys, total = ShopLayout.stack({ 64, 132, 64, 64 }, 6)
	check("stack: rows top to bottom with the gap between them", ys[1] == 0 and ys[2] == 70 and ys[3] == 208 and ys[4] == 278 and total == 342)
	check("revealScroll: a hero that fits is shown whole with the least scroll", ShopLayout.revealScroll(70, 132, 241, 342) == 0 and ShopLayout.revealScroll(70, 132, 133, 342) == 69)
	check("revealScroll: never past the hero's top, never past the canvas", ShopLayout.revealScroll(70, 132, 100, 342) == 70 and ShopLayout.revealScroll(300, 132, 241, 342) == 101)
	-- The hero fits above the TutorialStrip on every phone
	local tight
	for _, size in ipairs(SIZES) do
		for _, bar in ipairs(BARS) do
			local L = ShopLayout.layout(size[1], size[2] - bar, bar, 4, 0)
			local withStrip = ShopLayout.layout(size[1], size[2] - bar, bar, 4, L.stripH)
			if ShopLayout.hero(withStrip.cardW).height > withStrip.pages.h then tight = size[1] .. "x" .. size[2] .. "/" .. bar end
		end
	end
	check("the hero card fits above the TutorialStrip on every phone (its height under the pages' height)", tight == nil, tight)
end
"""


CLIENT_TESTS = r"""-- Tests: the real ShopClient in the fake place --------------------------------------------------------------------
local function shopGui(w) return w.playerGui:FindFirstChild("ShopGui") end
local function win(w) return shopGui(w) and shopGui(w):FindFirstChild("Window") end
local function startShop(opts)
	local w = newWorld(opts)
	w.start(opts.source)
	run(opts.wait or 0.3) -- the Office list arrives (0.05 s of latency)
	return w
end
-- The SHOP button: in its own HUD ScreenGui (ShopHudGui), under every window
local function shopButtonOf(w) return w.playerGui:FindFirstChild("ShopButton", true) end
local function openShop(w, label)
	if not (shopGui(w) and shopButtonOf(w)) then
		check(label .. ": the SHOP button exists", false)
		return
	end
	if not prop(win(w), "Visible", false) then
		tap(shopButtonOf(w), label .. ": open the shop")
	end
end
local function noErrors(label)
	check(label .. ": ShopClient runs without an error", #LOG.errors == 0, LOG.errors[1])
end
local TAB_NAMES = { "Office", "Passes", "Boosts", "Cash", "Debug" }
-- The tab labels' widths on one line at 16 px (what ShopClient measures with TextService)
local function tabLabels(count)
	local list = {}
	for i = 1, count do list[i] = measure(TAB_NAMES[i], 16, Enum.Font.GothamBold, math.huge).X end
	return list
end
local function layoutNow(w)
	local tabs = w.studio and 5 or 4
	local labels = tabLabels(tabs)
	local L = ShopLayout.layout(GUI.w, GUI.h, w.bar, tabs, 0, labels)
	local strip, status = find(win(w), "TutorialStrip"), find(win(w), "StatusLine")
	local bottomH = 0
	if strip and strip.Visible then bottomH = L.stripH end
	if status and status.Visible then bottomH = math.max(bottomH, rectOf(status).h) end
	if bottomH > 0 then L = ShopLayout.layout(GUI.w, GUI.h, w.bar, tabs, bottomH, labels) end
	return L
end
local function sameRect(inst, r)
	if not inst then return false end
	local a = rectOf(inst)
	return math.abs(a.x - r.x) < 0.5 and math.abs(a.y - r.y) < 0.5 and math.abs(a.w - r.w) < 0.5 and math.abs(a.h - r.h) < 0.5
end
-- The cards: every Frame right under a page that has a name label
local function cardsOf(w)
	local list = {}
	for _, name in ipairs(TAB_NAMES) do
		local page = find(win(w), name .. "Page")
		if page then
			for _, c in ipairs(page:GetChildren()) do
				if c.ClassName == "Frame" and c:FindFirstChild("ItemName") then
					table.insert(list, c)
				end
			end
		end
	end
	return list
end

-- The five HUD buttons. The other scripts' four come from their sources (tools/shop_ux_test.py reads the slot, the
-- ScreenGui and its DisplayOrder) and are placed with the shared HUD layout (a 64 px row at the top on a GUI under 460
-- px tall, else a 76 px column centered on the left); the SHOP button is the real one, in its real ScreenGui.
local HUD_OTHERS = __HUD__
local function hudRect(slot)
	if GUI.h < 460 then
		return { x = 10 + slot * 72, y = 6, w = 64, h = 64 }
	end
	return { x = 12, y = GUI.h / 2 + (slot - 2) * 86 - 38, w = 76, h = 76 }
end
local function screenGuiOf(inst)
	local node = inst
	while node and rawget(node, "_class") ~= "ScreenGui" do node = rawget(node, "_parent") end
	return node
end
local function hudButtons(w)
	local list = {}
	for _, hud in ipairs(HUD_OTHERS) do
		table.insert(list, { name = hud.name, gui = hud.gui, order = hud.order, rect = hudRect(hud.slot) })
	end
	local button = shopButtonOf(w)
	local sg = screenGuiOf(button)
	if button and sg then
		table.insert(list, { name = "ShopButton", gui = sg.Name, order = sg == shopGui(w) and math.huge or sg.DisplayOrder, rect = rectOf(button) })
	end
	return list
end

-- What every screen must give, whatever is open (label: the phone and the case)
local function screenChecks(w, label)
	local g, window = shopGui(w), win(w)
	if not (g and window) then
		check(label .. ": the ShopGui and its Window exist", false)
		return
	end
	-- no text can shrink under 16 px
	local small
	for _, d in ipairs(g:GetDescendants()) do
		if TEXTCLASS[d.ClassName] then
			if d.TextScaled then
				local c = d:FindFirstChildOfClass("UITextSizeConstraint")
				if not c or c.MinTextSize < 16 then small = d:GetFullName() .. " (min " .. tostring(c and c.MinTextSize or 1) .. ")" end
			elseif d.TextSize < 16 then
				small = d:GetFullName() .. " (" .. d.TextSize .. " px)"
			end
		end
	end
	check(label .. ": no text box with a minimum under 16 px", small == nil, small)
	-- every tap target at least 44 x 44 (the window's and the SHOP button)
	local tiny
	local targets = g:GetDescendants()
	table.insert(targets, shopButtonOf(w))
	for _, d in ipairs(targets) do
		if BUTTONCLASS[d.ClassName] and shown(d) then
			local r = rectOf(d)
			if r.w < 44 or r.h < 44 then tiny = d:GetFullName() .. " " .. rectText(r) end
		end
	end
	check(label .. ": every tap target at least 44 x 44", tiny == nil, tiny)
	if not window.Visible then return end
	-- the header: 44 px items that never overlap
	local title, help, close = window:FindFirstChild("Title"), window:FindFirstChild("HelpButton"), window:FindFirstChild("CloseButton")
	local headerOk = title and help and close and rectOf(title).h == 44 and rectOf(help).w == 44 and rectOf(help).h == 44
		and rectOf(close).w == 44 and rectOf(close).h == 44
		and not overlaps(rectOf(title), rectOf(help)) and not overlaps(rectOf(help), rectOf(close)) and not overlaps(rectOf(title), rectOf(close))
	check(label .. ": header items are 44 px and never overlap", headerOk == true)
	-- the window inside the GUI, everything shown inside the window
	local wr = rectOf(window)
	check(label .. ": the window stays inside the GUI", inside(wr, { x = 0, y = 0, w = GUI.w, h = GUI.h }), rectText(wr))
	local outside
	for _, d in ipairs(window:GetDescendants()) do
		if GUIOBJ[d.ClassName] and shown(d) then
			local vr = visibleRect(d)
			if vr.w > 0 and vr.h > 0 and not inside(vr, wr, 0.5) then outside = d:GetFullName() .. " " .. rectText(vr) end
		end
	end
	check(label .. ": everything shown stays inside the window", outside == nil, outside)
	-- the window's pieces where ShopLayout puts them
	local L = layoutNow(w)
	local placed = sameRect(window, L.window) and sameRect(title, L.title) and sameRect(help, L.help) and sameRect(close, L.close)
		and sameRect(window:FindFirstChild("Pages"), L.pages) and sameRect(window:FindFirstChild("TabBar"), L.tabBar)
	local tabBar = window:FindFirstChild("TabBar")
	local tabsPlaced = true
	for i = 1, (w.studio and 5 or 4) do
		local t = window:FindFirstChild("Tab" .. TAB_NAMES[i], true)
		local want = L.tabs[i]
		if not (t and tabBar) then
			tabsPlaced = false
		else
			local canvas = canvasOf(tabBar)
			local r = rectOf(t)
			if math.abs((r.x - canvas.x) - (want.x - L.tabBar.x)) > 0.5 or math.abs((r.y - canvas.y) - (want.y - L.tabBar.y)) > 0.5 or r.w ~= want.w or r.h ~= want.h then
				tabsPlaced = false
			end
		end
	end
	check(label .. ": the window, header, tabs and pages are where ShopLayout.layout puts them", placed and tabsPlaced, rectText(rectOf(window)) .. " vs " .. rectText(L.window))
	local squeezed
	for i = 1, (w.studio and 5 or 4) do
		local t = window:FindFirstChild("Tab" .. TAB_NAMES[i], true)
		if t and measure(t.Text, 16, t.Font, math.huge).X + 2 * ShopLayout.TAB_TEXT_PAD > rectOf(t).w then
			squeezed = squeezed or t.Name .. " '" .. t.Text .. "' needs " .. measure(t.Text, 16, t.Font, math.huge).X .. " px in " .. rectOf(t).w
		end
	end
	check(label .. ": every tab's label fits its tab on one line at 16 px", squeezed == nil, squeezed)
	-- nothing covers a Buy button: header items, tabs, the strip, the status line, the help card, the toast
	local covers = { title, help, close, window:FindFirstChild("TutorialStrip"), window:FindFirstChild("StatusLine"), window:FindFirstChild("HelpCard"), g:FindFirstChild("Toast") }
	for _, name in ipairs(TAB_NAMES) do
		table.insert(covers, window:FindFirstChild("Tab" .. name, true))
	end
	local covered
	for _, d in ipairs(window:GetDescendants()) do
		if d.Name == "BuyButton" and shown(d) then
			local vr = visibleRect(d)
			if vr.w > 0 and vr.h > 0 then
				for _, other in ipairs(covers) do
					if other and shown(other) and overlaps(vr, visibleRect(other)) then covered = d.Parent.Name .. "'s BuyButton under " .. other.Name end
				end
			end
		end
	end
	check(label .. ": nothing covers a Buy button (header, tabs, strip, status line, help card, toast)", covered == nil, covered)
	-- the HUD buttons (EGGS, SHOP, TEAM, POACH, IPO): one that may draw above the window (its ScreenGui's DisplayOrder at
	-- or above ShopGui's: a tie is undefined) must never cover a tab or any part of the window
	local onTab, onWindow = {}, {}
	for _, hud in ipairs(hudButtons(w)) do
		if hud.order >= g.DisplayOrder then
			local who = hud.name .. " (" .. hud.gui .. ", DisplayOrder " .. (hud.order == math.huge and "the same ScreenGui" or hud.order) .. ")"
			for i = 1, (w.studio and 5 or 4) do
				local t = window:FindFirstChild("Tab" .. TAB_NAMES[i], true)
				if t and shown(t) and overlaps(visibleRect(t), hud.rect) then
					table.insert(onTab, who .. " over Tab" .. TAB_NAMES[i] .. " at " .. rectText(intersect(visibleRect(t), hud.rect)))
				end
			end
			if overlaps(wr, hud.rect) then table.insert(onWindow, who .. " at " .. rectText(hud.rect)) end
		end
	end
	check(label .. ": no HUD button that may draw above the shop (DisplayOrder at or above ShopGui's) covers a tab", #onTab == 0, table.concat(onTab, "; "))
	check(label .. ": the shop window draws above every HUD button it overlaps (DisplayOrder)", #onWindow == 0, table.concat(onWindow, "; "))
	check(label .. ": no toast while the shop is open", not prop(kid(g, "Toast"), "Visible", false))
end

-- Every phone, every top bar, live and Studio --------------------------------------------------------------------
for _, size in ipairs(SIZES) do
	for _, bar in ipairs(BARS) do
		for _, studio in ipairs({ false, true }) do
			local label = size[1] .. "x" .. size[2] .. "/" .. bar .. (studio and " Studio" or " live")
			local w = startShop({ w = size[1], h = size[2], bar = bar, studio = studio, cash = 50, income = 3, owned = 1 })
			openShop(w, label)
			run(1.2)
			noErrors(label)
			check(label .. ": the SHOP button is where the shared HUD layout puts it (the model of the other HUD buttons)", sameRect(shopButtonOf(w), hudRect(1)),
				rectText(rectOrEmpty(shopButtonOf(w))))
			local window = win(w) or newInst("Frame") -- a missing window fails the checks below, never crashes them
			-- the names the tutorial finds under ShopGui.Window
			local missing = {}
			local tabs = studio and 5 or 4
			for i = 1, tabs do
				local name = TAB_NAMES[i]
				local tabButton, page = window:FindFirstChild("Tab" .. name, true), window:FindFirstChild(name .. "Page", true)
				if not (tabButton and tabButton.ClassName == "TextButton") then table.insert(missing, "Tab" .. name) end
				if not (page and page.ClassName == "ScrollingFrame") then table.insert(missing, name .. "Page") end
			end
			if not studio and (window:FindFirstChild("TabDebug", true) or window:FindFirstChild("DebugPage", true)) then
				table.insert(missing, "a Debug tab outside Studio")
			end
			for _, name in ipairs({ "HelpButton", "TutorialStrip" }) do
				if not window:FindFirstChild(name, true) then table.insert(missing, name) end
			end
			local office = window:FindFirstChild("OfficePage", true)
			for i = 1, #UPGRADES do
				local card = office and office:FindFirstChild("Office" .. i)
				if not card then table.insert(missing, "OfficePage.Office" .. i) end
			end
			check(label .. ": every Name exists after the Office list arrives (Tab*, *Page, Office1-6, HelpButton, TutorialStrip)", #missing == 0, table.concat(missing, ", "))
			local noBuy
			for _, card in ipairs(cardsOf(w)) do
				local b = card:FindFirstChild("BuyButton")
				if not (b and b.ClassName == "TextButton") then noBuy = card:GetFullName() end
			end
			check(label .. ": every card's button is named BuyButton", noBuy == nil and #cardsOf(w) > 10, noBuy)
			for _, name in ipairs({ "Office", "Passes", "Boosts", "Cash" }) do
				tap(window:FindFirstChild("Tab" .. name, true), label .. ": the " .. name .. " tab")
				check(label .. ": the " .. name .. " tab shows its page",
					prop(find(window, name .. "Page"), "Visible", false) and prop(find(window, "Tab" .. name), "BackgroundColor3") == Color3.fromRGB(0, 200, 90))
				screenChecks(w, label .. " " .. name)
			end
			if studio then
				local bar5 = window:FindFirstChild("TabBar")
				local debugTab = window:FindFirstChild("TabDebug", true)
				if bar5 and debugTab and visibleRect(debugTab).w < rectOf(debugTab).w then
					-- the row scrolls sideways (320 px wide): the player swipes it to its end
					bar5.CanvasPosition = v2(math.max(0, bar5.CanvasSize.X.Offset - rectOf(bar5).w), 0)
					run(0)
					check(label .. ": the tab row scrolls sideways to the Debug tab (shown whole, a scroll bar)",
						visibleRect(debugTab).w == rectOf(debugTab).w and bar5.ScrollBarThickness > 0, rectText(visibleRect(debugTab)))
				end
				tap(debugTab, label .. ": the Debug tab")
				screenChecks(w, label .. " Debug")
			end
			tap(window:FindFirstChild("TabOffice", true), label .. ": back to Office")
			noErrors(label .. " after the tabs")
		end
	end
end

-- TutorialStrip: shown while PlayerGui's TutorialBanner holds a text, inert while it is unset ------------------------
for _, size in ipairs(SIZES) do
	for _, bar in ipairs(BARS) do
		local label = size[1] .. "x" .. size[2] .. "/" .. bar .. " strip"
		local w = startShop({ w = size[1], h = size[2], bar = bar, cash = 10, income = 1 })
		openShop(w, label)
		local window = win(w)
		local strip = window:FindFirstChild("TutorialStrip")
		local pagesFrame = window:FindFirstChild("Pages")
		local function pagesH() return rectOrEmpty(pagesFrame).h end
		local full = pagesH()
		check(label .. ": TutorialStrip is inert while TutorialBanner is unset (hidden, the pages keep their height)",
			strip ~= nil and not strip.Visible and full == ShopLayout.layout(GUI.w, GUI.h, bar, 4, 0).pages.h)
		w.playerGui:SetAttribute("TutorialBanner", "Tap the Desk's button: it is free.")
		run(0)
		local L = ShopLayout.layout(GUI.w, GUI.h, bar, 4, 0)
		local withStrip = ShopLayout.layout(GUI.w, GUI.h, bar, 4, L.stripH)
		check(label .. ": TutorialStrip shows the banner's text at the window's bottom, as tall as ShopLayout says",
			prop(strip, "Visible", false) and prop(strip, "Text") == "Tap the Desk's button: it is free." and sameRect(strip, withStrip.bottom), rectText(rectOrEmpty(strip)))
		check(label .. ": the strip takes its height from the pages (they shrink by the strip and a 6 px gap)",
			pagesH() == full - L.stripH - 6 and sameRect(pagesFrame, withStrip.pages), pagesH())
		check(label .. ": with the strip the pages keep room for the Office hero card (132 px)", pagesH() >= 132, pagesH())
		screenChecks(w, label .. " shown")
		w.playerGui:SetAttribute("TutorialBanner", nil)
		run(0)
		check(label .. ": TutorialStrip is inert again once TutorialBanner is unset", not prop(strip, "Visible", false) and pagesH() == full)
		for _, value in ipairs({ 5, "", true }) do
			w.playerGui:SetAttribute("TutorialBanner", value)
			run(0)
			check(label .. ": TutorialStrip is inert for a banner that is not a text (" .. tostring(value) .. ")", not prop(strip, "Visible", false) and pagesH() == full)
		end
		w.playerGui:SetAttribute("TutorialBanner", nil)
		noErrors(label)
	end
end

-- A TutorialBanner longer than STRIP_TEXT_LIMIT is flagged in Studio's Output, once (never on a live server) ---------
for _, studio in ipairs({ true, false }) do
	local label = "strip limit warning (" .. (studio and "Studio" or "live") .. ")"
	local w = startShop({ w = 667, h = 375, bar = 36, studio = studio })
	local function warned()
		local n = 0
		for _, line in ipairs(LOG.warned) do
			if string.find(line, "TutorialBanner is", 1, true) then n += 1 end
		end
		return n
	end
	w.playerGui:SetAttribute("TutorialBanner", string.rep("a", ShopLayout.STRIP_TEXT_LIMIT))
	run(0)
	check(label .. ": a banner at the limit is not flagged", warned() == 0)
	local long = string.rep("b", ShopLayout.STRIP_TEXT_LIMIT + 1)
	w.playerGui:SetAttribute("TutorialBanner", long)
	run(0)
	check(label .. ": a banner one character over the limit is flagged in Studio's Output (never live)", warned() == (studio and 1 or 0), warned())
	w.playerGui:SetAttribute("TutorialBanner", nil)
	run(0)
	w.playerGui:SetAttribute("TutorialBanner", long)
	run(0)
	check(label .. ": the same text is flagged once", warned() == (studio and 1 or 0), warned())
	noErrors(label)
end

-- The status line: messages while the shop is open go into the window, the toast only while it is closed ----------
do
	local label = "status line"
	local w = startShop({ w = 667, h = 375, bar = 36, cash = 10, income = 1 })
	local g = shopGui(w)
	local toast = kid(g, "Toast")
	w.notify.OnClientEvent:Fire("Saving works again: your progress is safe.")
	run(0)
	check(label .. ": with the shop closed a message is the toast at the bottom",
		prop(toast, "Visible", false) and prop(toast, "Text") == "Saving works again: your progress is safe.")
	check(label .. ": the toast wraps (two lines at 16 px in its 48 px lane, the bottom-center pop-up lanes)",
		prop(toast, "TextWrapped", false) and rectOrEmpty(toast).h == 48 and rectOrEmpty(toast).w <= 520)
	openShop(w, label)
	local window = win(w)
	local status, pagesFrame = kid(window, "StatusLine"), kid(window, "Pages")
	check(label .. ": opening the shop moves a toast that is still up into the window's status line",
		not prop(toast, "Visible", false) and prop(status, "Visible", false) and prop(status, "Text") == "Saving works again: your progress is safe.")
	run(4)
	check(label .. ": the status line goes away after 3.5 s", not prop(status, "Visible", false))
	local full = rectOrEmpty(pagesFrame).h
	w.notify.OnClientEvent:Fire("2x Cash unlocked!")
	run(0)
	check(label .. ": with the shop open a message goes to the status line, never the toast",
		prop(status, "Visible", false) and prop(status, "Text") == "2x Cash unlocked!" and not prop(toast, "Visible", false))
	check(label .. ": the status line takes its room from the pages, never covers them",
		rectOrEmpty(pagesFrame).h < full and not overlaps(rectOrEmpty(status), rectOrEmpty(pagesFrame)))
	screenChecks(w, label .. " short message")
	w.notify.OnClientEvent:Fire("Saving is having trouble right now. Keep playing: your progress is saved as soon as it works again.")
	run(0)
	local sr = rectOrEmpty(status)
	check(label .. ": a long message gets up to 3 lines (at most 72 px), still never over the pages",
		sr.h > 40 and sr.h <= 72 and not overlaps(sr, rectOrEmpty(pagesFrame)), sr.h)
	screenChecks(w, label .. " long message")
	run(4)
	check(label .. ": the pages get their height back once the message is gone", rectOrEmpty(pagesFrame).h == full and not prop(status, "Visible", false))
	tap(kid(window, "CloseButton"), label .. ": close")
	w.notify.OnClientEvent:Fire("Bought Laptop")
	run(0)
	check(label .. ": after closing, messages are the toast again", prop(toast, "Visible", false) and not prop(status, "Visible", false))
	noErrors(label)
end

-- The toast: every text the server can send it, cut to its 2 lines with ... (the window's line keeps the whole) -------
local TOAST_TEXTS = __TOAST_TEXTS__
local TOAST_REPORT = __TOAST_REPORT__
for _, size in ipairs({ { 320, 568 }, { 667, 375 } }) do
	for _, bar in ipairs(BARS) do
		local label = "toast " .. size[1] .. "x" .. size[2] .. "/" .. bar
		local w = startShop({ w = size[1], h = size[2], bar = bar, cash = 10, income = 1 })
		local toast = kid(shopGui(w), "Toast")
		local font = prop(toast, "Font", Enum.Font.GothamBold)
		local width = math.min(GUI.w * 0.6, 520)
		local lineH = math.ceil(16 * 1.25)
		local tall, whole, cut, longest
		for _, item in ipairs(TOAST_TEXTS) do
			w.notify.OnClientEvent:Fire(item.text)
			run(0)
			local face = prop(toast, "Text", "")
			local h = measure(face, 16, font, width).Y
			if not (prop(toast, "Visible", false) and h <= 2 * lineH and h <= rectOrEmpty(toast).h) then
				tall = item.where .. " (" .. #item.text .. " characters, " .. h .. " px): " .. face
			end
			local lines = measure(item.text, 16, font, width).Y / lineH
			if lines <= 2 then
				if face ~= item.text then whole = item.where .. ": " .. face end
			else
				local head = string.match(face, "^(.-)%.%.%.$")
				if not head or head == "" or string.sub(item.text, 1, #head) ~= head then cut = item.where .. ": " .. face end
				if not longest or #item.text > #longest then longest = item.text end
			end
			if TOAST_REPORT and bar == 0 then
				print_real(string.format("TOAST %s %dx%d %d lines %d chars: %s", item.where, size[1], size[2], lines, #item.text, item.text))
			end
		end
		check(label .. ": every server text fits the toast's 2 lines at 16 px in its 48 px lane", tall == nil, tall)
		check(label .. ": a text that fits is shown whole; a longer one is its start and ends with ...", whole == nil and cut == nil, whole or cut)
		local tr = rectOrEmpty(toast)
		check(label .. ": the toast keeps its 48 px lane (bottom center, 16 px up, at most 520 wide)",
			tr.h == 48 and math.abs(tr.w - width) < 0.01 and tr.y + tr.h == GUI.h - 16 and math.abs(tr.x + tr.w / 2 - GUI.w / 2) < 0.01, rectText(tr))
		if longest then
			w.notify.OnClientEvent:Fire(longest)
			run(0)
			if size[1] == 667 then
				w.resize(320, 568, bar)
				local face = prop(toast, "Text", "")
				check(label .. ": a new screen size cuts the toast again for its new width",
					measure(face, 16, font, math.min(GUI.w * 0.6, 520)).Y <= 2 * lineH and string.sub(face, -3) == "...", face)
			end
			openShop(w, label)
			check(label .. ": opening the shop shows the whole message in the window's line, never the cut one",
				prop(kid(win(w), "StatusLine"), "Text") == longest, prop(kid(win(w), "StatusLine"), "Text"))
		end
		noErrors(label)
	end
end

-- A message still in the window's line when the shop closes moves to the toast, once (decided by the owner) ---------
for _, case in ipairs({ { 667, 375, 36, "the X" }, { 320, 568, 36, "the SHOP button" }, { 568, 320, 58, "another window opening" } }) do
	local label = "message at close " .. case[1] .. "x" .. case[2] .. "/" .. case[3] .. " (" .. case[4] .. ")"
	local w = startShop({ w = case[1], h = case[2], bar = case[3], cash = 10, income = 1 })
	openShop(w, label)
	local g, window = shopGui(w), win(w)
	local toast, status = kid(g, "Toast"), kid(window, "StatusLine")
	local text = "Saving works again: your progress is safe."
	w.notify.OnClientEvent:Fire(text)
	run(1)
	check(label .. ": the message shows in the window's line first", prop(status, "Visible", false) and prop(status, "Text") == text and not prop(toast, "Visible", true))
	if case[4] == "the X" then
		tap(kid(window, "CloseButton"), label .. ": close")
	elseif case[4] == "the SHOP button" then
		tap(shopButtonOf(w), label .. ": close")
	else
		w.playerGui:SetAttribute("OpenPanel", "Ipo")
		run(0)
	end
	check(label .. ": closing the shop moves a message still in its line to the toast",
		not prop(window, "Visible", true) and prop(toast, "Visible", false) and prop(toast, "Text") == text, prop(toast, "Text"))
	check(label .. ": once: the window's line is cleared (the message is in one place)", not prop(status, "Visible", true) and prop(status, "Text") == "")
	local tr, laneW = rectOrEmpty(toast), math.min(GUI.w * 0.6, 520)
	check(label .. ": the moved message keeps the toast's lane (bottom center, 48 px, 16 px up, at most 520 wide)",
		tr.h == 48 and math.abs(tr.w - laneW) < 0.01 and math.abs(tr.x + tr.w / 2 - GUI.w / 2) < 0.01 and tr.y + tr.h == GUI.h - 16, rectText(tr))
	run(3.4)
	check(label .. ": the toast shows it for its own 3.5 s", prop(toast, "Visible", false))
	run(0.2)
	check(label .. ": then it is gone, and it never comes back (the line's old timer does nothing)", not prop(toast, "Visible", true) and not prop(status, "Visible", true))
	run(4)
	check(label .. ": still gone later", not prop(toast, "Visible", true) and prop(status, "Text") == "")
	w.playerGui:SetAttribute("OpenPanel", nil)
	tap(shopButtonOf(w), label .. ": open again")
	tap(kid(window, "CloseButton"), label .. ": close with no message")
	check(label .. ": closing with no message in the line shows no toast", not prop(toast, "Visible", true))
	noErrors(label)
end

-- The help card: "?" opens a one-screen "How the shop works" card over the pages ----------------------------------
for _, size in ipairs(SIZES) do
	for _, bar in ipairs(BARS) do
		local label = size[1] .. "x" .. size[2] .. "/" .. bar .. " help"
		local w = startShop({ w = size[1], h = size[2], bar = bar, cash = 10, income = 1 })
		openShop(w, label)
		local window = win(w)
		local help, card = window:FindFirstChild("HelpButton"), window:FindFirstChild("HelpCard")
		tap(help, label .. ": tap ?")
		local L = layoutNow(w)
		local pagesFrame = kid(window, "Pages")
		local descendants = card and card:GetDescendants() or {}
		local lines = {}
		for _, d in ipairs(descendants) do
			if string.match(d.Name, "^HelpLine%d$") then table.insert(lines, d) end
		end
		check(label .. ": \"?\" opens the How the shop works card over the pages (never the header or the tabs)",
			prop(card, "Visible", false) and prop(find(card, "HelpTitle"), "Text") == "How the shop works" and #lines == 3 and sameRect(card, L.helpCard),
			rectText(rectOrEmpty(card)))
		check(label .. ": the pages hide while the help card is open (it never sits on a Buy button)", not prop(pagesFrame, "Visible", true))
		local buttons = 0
		for _, d in ipairs(descendants) do
			if d.ClassName == "TextButton" then buttons += 1 end
		end
		check(label .. ": the help card has no reward and one button, Back", buttons == 1 and find(card, "HelpBack") ~= nil)
		local reference = (size[1] == 667 and size[2] == 375) or (size[1] == 320 and size[2] == 568)
		local cs = card and card.CanvasSize.Y.Offset or math.huge
		if reference or not (size[1] == 568) then
			check(label .. ": the help card fits on one screen (no scroll)", cs <= rectOrEmpty(card).h, cs .. " > " .. rectOrEmpty(card).h)
		else
			check(label .. ": the help card scrolls only when it must (this low window)", cs <= rectOrEmpty(card).h or prop(card, "ScrollBarThickness", 0) > 0)
		end
		local word
		for _, d in ipairs(descendants) do
			if TEXTCLASS[d.ClassName] and d9Word(d.Text) then word = d.Text end
		end
		check(label .. ": the help card never uses the words odds, chance, luck or random (D9)", word == nil, word)
		screenChecks(w, label .. " open")
		tap(find(card, "HelpBack"), label .. ": Back")
		check(label .. ": Back closes the help card and shows the pages again", not prop(card, "Visible", true) and prop(pagesFrame, "Visible", false))
		tap(help, label .. ": ? again")
		tap(help, label .. ": ? a third time")
		check(label .. ": \"?\" toggles the help card", not prop(card, "Visible", true))
		tap(help, label .. ": ? then a tab")
		tap(window:FindFirstChild("TabCash", true), label .. ": the Cash tab with the help open")
		check(label .. ": a tab closes the help card and shows its page",
			not prop(card, "Visible", true) and prop(pagesFrame, "Visible", false) and prop(find(window, "CashPage"), "Visible", false))
		tap(help, label .. ": ? then close")
		tap(kid(window, "CloseButton"), label .. ": close with the help open")
		tap(shopButtonOf(w), label .. ": reopen")
		check(label .. ": the shop reopens on its tab, never on the help card", not prop(card, "Visible", true) and prop(pagesFrame, "Visible", false))
		noErrors(label)
	end
end

-- Wiring: what the shop sends to the server, and the Robux prompts it opens ----------------------------------------
do
	local label = "wiring"
	local w = startShop({ w = 667, h = 375, bar = 36, cash = 0, income = 0 })
	openShop(w, label)
	local window = win(w)
	local only = #w.invokes >= 1 and w.invokes[1].remote == "ShopAction" and w.invokes[1].args.n == 1 and w.invokes[1].args[1] == "Office"
	check(label .. ": opening the shop asks the server for \"Office\" (the building, the desks), nothing else", only, #w.invokes)
	local desk = find(window, "Office1")
	tap(desk and desk:FindFirstChild("BuyButton"), label .. ": buy the Desk")
	run(0.2)
	local last
	for k = #w.invokes, 1, -1 do if w.invokes[k].args[1] == "BuyUpgrade" then last = w.invokes[k] break end end
	check(label .. ": a Buy tap sends only \"BuyUpgrade\" and the item's number (no price, no Cash)",
		last and last.args.n == 2 and last.args[2] == 1 and typeOf(last.args[2]) == "number", last and last.args.n)
	check(label .. ": the server's answer reaches the player (the Desk is bought)", w.player:GetAttribute("Upgrade1") == true)
	local seen = {}
	for _, call in ipairs(w.invokes) do
		if call.remote == "ShopAction" then
			seen[tostring(call.args[1]) .. "/" .. call.args.n] = true
		end
	end
	local others
	for key in pairs(seen) do
		if key ~= "Office/1" and key ~= "BuyUpgrade/2" then others = key end
	end
	check(label .. ": the Office only ever sends \"Office\" and \"BuyUpgrade\", index here", others == nil, others)
	noErrors(label)
end

-- Robux buttons never prompt an item isForSale refuses (or one already owned or pending) ---------------------------
do
	local label = "Robux prompts"
	local w = startShop({ w = 667, h = 375, bar = 36, cash = 0, income = 0 })
	local ShopConfig = w.module("ShopConfig")
	openShop(w, label)
	local window = win(w)
	tap(window:FindFirstChild("TabPasses", true), label .. ": Passes")
	local double = find(window, "DoubleCash")
	local doubleBuy = kid(double, "BuyButton")
	tap(doubleBuy, label .. ": 2x Cash")
	check(label .. ": a pass for sale opens Roblox's own prompt, once, with its ID", #w.prompts == 1 and w.prompts[1].kind == "pass" and w.prompts[1].id == ShopConfig.getPass("DoubleCash").id)
	check(label .. ": the button shows ... while the prompt is open", prop(doubleBuy, "Text") == "...")
	tap(doubleBuy, label .. ": 2x Cash again while pending")
	check(label .. ": a pending item is never prompted twice", #w.prompts == 1)
	w.market.PromptGamePassPurchaseFinished:Fire(w.player, ShopConfig.getPass("DoubleCash").id, false)
	run(0)
	check(label .. ": the prompt closing unlocks the button", prop(doubleBuy, "Text") == "R$ " .. ShopConfig.getPass("DoubleCash").price)
	w.player:SetAttribute("Pass_DoubleCash", true)
	run(0)
	tap(doubleBuy, label .. ": an owned pass")
	check(label .. ": an owned pass is never prompted", #w.prompts == 1 and prop(doubleBuy, "Text") == "Owned")
	local slotsBuy = kid(find(window, "ExtraSlots"), "BuyButton")
	tap(slotsBuy, label .. ": an egg pass while EggsEnabled is off")
	check(label .. ": an item isForSale refuses (an egg item while EggsEnabled is off) is never prompted", #w.prompts == 1 and prop(slotsBuy, "Text") == "Coming soon")
	ShopConfig.getPass("Shareholder").id = 0
	run(1.1)
	local share = find(window, "Shareholder")
	scrollTo(share)
	tap(kid(share, "BuyButton"), label .. ": a pass with id 0")
	check(label .. ": an item with id 0 (not created yet) is never prompted", #w.prompts == 1 and prop(kid(share, "BuyButton"), "Text") == "Coming soon")
	tap(window:FindFirstChild("TabCash", true), label .. ": Cash")
	tap(kid(find(window, "CashSmall"), "BuyButton"), label .. ": a Cash pack")
	check(label .. ": a product for sale opens Roblox's product prompt", #w.prompts == 2 and w.prompts[2].kind == "product" and w.prompts[2].id == ShopConfig.getProduct("CashSmall").id)
	noErrors(label)
end

-- Lobby L3: on the plaza with no garage yet (attribute Garage = 0) the Robux buttons wait for the garage ---------------
do
	local label = "No garage yet"
	local w = startShop({ w = 667, h = 375, bar = 36, attrs = { Garage = 0 } })
	local ShopConfig = w.module("ShopConfig")
	openShop(w, label)
	run(1.1)
	local window = win(w)
	tap(window:FindFirstChild("TabPasses", true), label .. ": Passes")
	local doubleBuy = kid(find(window, "DoubleCash"), "BuyButton")
	tap(doubleBuy, label .. ": 2x Cash")
	check(label .. ": a pass is never prompted before a garage, its button says Claim garage", #w.prompts == 0 and prop(doubleBuy, "Text") == "Claim garage", prop(doubleBuy, "Text"))
	tap(window:FindFirstChild("TabCash", true), label .. ": Cash")
	local packBuy = kid(find(window, "CashSmall"), "BuyButton")
	tap(packBuy, label .. ": a Cash pack")
	check(label .. ": a product is never prompted before a garage, its button says Claim garage", #w.prompts == 0 and prop(packBuy, "Text") == "Claim garage", prop(packBuy, "Text"))
	w.player:SetAttribute("Garage", 3)
	run(1.1)
	check(label .. ": with a garage the buttons are for sale again", prop(packBuy, "Text") == "R$ " .. ShopConfig.getProduct("CashSmall").price, prop(packBuy, "Text"))
	tap(packBuy, label .. ": a Cash pack with a garage")
	check(label .. ": with a garage a product is prompted", #w.prompts == 1 and w.prompts[1].id == ShopConfig.getProduct("CashSmall").id)
	noErrors(label)
end

-- Luck Boost: hidden while RandomRestricted is not false (D9 option B), its luckText line on the card face -----------
for _, case in ipairs({ { "unknown", false }, { true, false }, { false, true } }) do
	local restricted, visible = case[1], case[2]
	local label = "Luck Boost (RandomRestricted " .. tostring(restricted) .. ")"
	local w = startShop({ w = 667, h = 375, bar = 36, restricted = restricted })
	local ShopConfig = w.module("ShopConfig")
	ShopConfig.EggsEnabled = true -- on sale for everyone who may buy it
	openShop(w, label)
	run(1.1)
	local window = win(w)
	tap(window:FindFirstChild("TabBoosts", true), label .. ": Boosts")
	local card = find(window, "LuckBoost")
	check(label .. ": Luck Boost hidden while RandomRestricted is not false, shown when it is false", card ~= nil and card.Visible == visible, prop(card, "Visible"))
	if visible then
		local text = prop(kid(card, "Description"), "Text", "")
		local prefix = "Odds weight x2 for Rare, Epic, Legendary hires. "
		check(label .. ": its card face starts with luckText's numbers, exactly as before", string.sub(text, 1, #prefix) == prefix and string.find(text, " -> ", 1, true) ~= nil, text)
		scrollTo(card)
		tap(kid(card, "BuyButton"), label .. ": buy")
		check(label .. ": a player who may buy it gets Roblox's prompt", #w.prompts == 1)
	else
		local buy = kid(card, "BuyButton")
		local s = buy and rawget(buy, "_signals").Activated
		if s then s:Fire() end
		run(0)
		check(label .. ": even a tap on the hidden card never prompts (isForSale refuses it)", #w.prompts == 0)
	end
	screenChecks(w, label)
	noErrors(label)
end

-- D9: no text the shop writes itself (header, tabs, Office, help) uses odds, chance, luck or random --------------------
do
	local label = "D9 texts"
	local w = startShop({ w = 320, h = 568, bar = 36, cash = 120, income = 5, owned = 2 })
	openShop(w, label)
	local window = win(w)
	local word
	local function scan(root)
		for _, d in ipairs(root:GetDescendants()) do
			if TEXTCLASS[d.ClassName] and d9Word(d.Text) then word = d:GetFullName() .. ": " .. d.Text end
		end
	end
	for _, name in ipairs({ "Title", "HelpButton", "CloseButton", "TabBar", "OfficePage", "HelpCard", "TutorialStrip", "StatusLine" }) do
		local inst = window:FindFirstChild(name, true)
		if inst then
			scan(inst)
			if TEXTCLASS[inst.ClassName] and d9Word(inst.Text) then word = inst.Text end
		end
	end
	check(label .. ": no text the shop writes itself uses the words odds, chance, luck or random", word == nil, word)
	noErrors(label)
end

-- The phone turns: everything is placed again for the new size -------------------------------------------------------
do
	local label = "turning the phone"
	local w = startShop({ w = 667, h = 375, bar = 36, cash = 10, income = 1 })
	openShop(w, label)
	w.resize(375, 667, 36)
	screenChecks(w, label .. " to portrait")
	check(label .. ": portrait puts the tabs in a row", rectOrEmpty(find(win(w), "TabOffice")).w ~= 112)
	w.resize(667, 375, 58)
	screenChecks(w, label .. " back to landscape with a 58 px bar")
	check(label .. ": landscape puts them back in the rail", rectOrEmpty(find(win(w), "TabOffice")).w == 112)
	noErrors(label)
end
"""

OFFICE_TESTS = r"""-- Tests: the Office and Hire tabs in the real ShopClient (overhaul 2: the catalog by funding stage) ---------------
local OC = assert(loadstring(MODULE_SOURCES.OfficeConfig, "=OfficeConfig"))()
local function officeOf(w) return find(win(w), "OfficePage") end
local function hireOf(w) return find(win(w), "OfficePage") end -- the Hire chip's cards are on the Office page
local function card(w, i) return kid(officeOf(w), "Office" .. i) end
local function startOffice(opts)
	local w = startShop(opts)
	openShop(w, "office")
	tap(find(win(w), "TabOffice"), "the Office tab")
	run(0.3) -- the "Office" answer
	return w
end
-- Every request the shop's Office and Hire tabs sent: "Office", "BuyBuilding", "BuyDesk", or "BuyUpgrade" / "Hire" with a whole number
local function officeWiring(w, label)
	local bad
	for _, call in ipairs(w.invokes) do
		if call.remote == "ShopAction" then
			local a = call.args
			local fine = (a.n == 1 and (a[1] == "Office" or a[1] == "BuyBuilding" or a[1] == "BuyDesk"))
				or (a.n == 2 and (a[1] == "BuyUpgrade" or a[1] == "Hire") and typeOf(a[2]) == "number" and a[2] % 1 == 0)
			if not fine then bad = tostring(a[1]) .. " with " .. a.n .. " values" end
		end
	end
	check(label .. ": the Office and Hire tabs only send Office, BuyBuilding, BuyDesk, BuyUpgrade index, Hire index (never a price)", bad == nil, bad)
end
local function lastCall(w, action)
	for k = #w.invokes, 1, -1 do
		local call = w.invokes[k]
		if call.remote == "ShopAction" and call.args[1] == action then return call end
	end
	return nil
end
-- Scrolls the Office page so this card shows whole at its top (a player scrolls the list the same way)
local function scrollTo(w, c)
	local page = officeOf(w)
	if page and c then
		page.CanvasPosition = Vector2.new(0, 0)
		run(0.05)
		page.CanvasPosition = Vector2.new(0, math.max(0, rectOf(c).y - rectOf(page).y))
		run(0.05)
	end
end
local function calls(w, action)
	local n = 0
	for _, call in ipairs(w.invokes) do
		if call.remote == "ShopAction" and call.args[1] == action then n += 1 end
	end
	return n
end
local function d9Office(w, label)
	local word
	for _, page in ipairs({ officeOf(w), hireOf(w) }) do
		for _, d in ipairs(page and page:GetDescendants() or {}) do
			if TEXTCLASS[d.ClassName] and d9Word(d.Text) then word = d:GetFullName() .. ": " .. d.Text end
		end
	end
	check(label .. ": no Office or Hire text uses the words odds, chance, luck or random", word == nil, word)
end
local STAGE_AT = { 0, 30000, 10000000, 100000000, 300000000, 1000000000 }

-- Every stage reached, in landscape and portrait: the stage shown, the cards of that stage only, locked and owned states ---
for _, size in ipairs({ { 667, 375, 36 }, { 320, 568, 36 } }) do
	for stage = 1, 6 do
		local label = "office " .. size[1] .. "x" .. size[2] .. ", stage " .. stage
		local w = startOffice({ w = size[1], h = size[2], bar = size[3], owned = 1, cash = 1e12, income = 3,
			attrs = { IpoValuation = STAGE_AT[stage], IpoCount = 0, Building = 1 } })
		noErrors(label)
		local visibleOk, why = true, nil
		for i, item in ipairs(OC.Items) do
			local c = card(w, i)
			if not c then visibleOk, why = false, "no card Office" .. i break end
			if prop(c, "Visible", false) ~= (item.stage == stage) then visibleOk, why = false, "Office" .. i .. " visible = " .. tostring(prop(c, "Visible")) end
		end
		check(label .. ": the shop opens on the stage reached, and shows that stage's items only", visibleOk, why)
		local chip = find(officeOf(w), "Stage" .. stage)
		check(label .. ": its stage chip is the green one", chip ~= nil and chip.BackgroundColor3 == Color3.fromRGB(0, 200, 90))
		local priceOk, pwhy = true, nil
		for i, item in ipairs(OC.Items) do
			if item.stage == stage and i ~= 1 then
				local text = prop(kid(card(w, i), "BuyButton"), "Text")
				if text ~= OC.money(item.price) then priceOk, pwhy = false, "Office" .. i .. ": " .. tostring(text) end
			end
		end
		check(label .. ": every item of the stage shows its price from OfficeConfig", priceOk, pwhy)
		local building = kid(officeOf(w), "OfficeBuilding")
		local bText = prop(kid(building, "BuyButton"), "Text")
		if stage == 1 then
			check(label .. ": the Garage is yours", bText == "Yours", bText)
		elseif stage == 2 then
			check(label .. ": the Small Office can be bought at its price", bText == OC.money(OC.Buildings[2].price), bText)
		else
			check(label .. ": a building two steps ahead waits (Later)", bText == "Later", bText)
		end
		screenChecks(w, label)
		officeWiring(w, label)
		d9Office(w, label)
	end
end

-- A stage not reached: its chip shows its items greyed and Locked ------------------------------------------------------
do
	local label = "office locked stage"
	local w = startOffice({ w = 667, h = 375, bar = 36, owned = 1, cash = 1e12, income = 3, attrs = { IpoValuation = 0, IpoCount = 0, Building = 1 } })
	tap(find(officeOf(w), "Stage3"), label .. ": the Series A chip")
	local locked, why = true, nil
	for i, item in ipairs(OC.Items) do
		if item.stage == 3 then
			local c = card(w, i)
			if not prop(c, "Visible", false) or prop(kid(c, "BuyButton"), "Text") ~= "Locked" then locked, why = false, "Office" .. i end
			if not string.find(prop(kid(c, "Description"), "Text", ""), "Unlocks at Series A", 1, true) then locked, why = false, "Office" .. i .. " says no Unlocks at Series A" end
		end
	end
	check(label .. ": Series A's items are shown, Locked, with Unlocks at Series A", locked, why)
	local before = calls(w, "BuyUpgrade")
	for i, item in ipairs(OC.Items) do
		if item.stage == 3 then tap(kid(card(w, i), "BuyButton"), label .. ": a locked Buy") break end
	end
	run(0.3)
	check(label .. ": a locked item's button sends nothing", calls(w, "BuyUpgrade") == before)
	check(label .. ": the Big Office says Locked", prop(kid(kid(officeOf(w), "OfficeBuilding"), "BuyButton"), "Text") == "Locked")
	noErrors(label)
end

-- Buying: an item sends only its number; the building sends only BuyBuilding -------------------------------------------
do
	local label = "office buy"
	local w = startOffice({ w = 667, h = 375, bar = 36, owned = 0, cash = 100000, income = 3, attrs = { IpoValuation = 30000, IpoCount = 0, Building = 1 } })
	tap(find(officeOf(w), "Stage1"), label .. ": the Garage chip")
	tap(kid(card(w, 1), "BuyButton"), label .. ": the free Desk")
	run(0.3)
	local last = lastCall(w, "BuyUpgrade")
	check(label .. ": the Desk's Buy sends BuyUpgrade, 1 (no price)", last and last.args[2] == 1 and last.args.n == 2, last and last.args.n)
	check(label .. ": the server's answer reaches the player (the Desk is bought)", w.player:GetAttribute("Upgrade1") == true)
	check(label .. ": the Desk now says Owned", prop(kid(card(w, 1), "BuyButton"), "Text") == "Owned")
	local before = calls(w, "BuyUpgrade")
	scrollTo(w, card(w, 2))
	tap(kid(card(w, 2), "BuyButton"), label .. ": Coffee Machine")
	tap(kid(card(w, 2), "BuyButton"), label .. ": Coffee Machine again, at once")
	run(0.3)
	check(label .. ": a second tap while the request runs sends nothing", calls(w, "BuyUpgrade") == before + 1, calls(w, "BuyUpgrade") - before)
	scrollTo(w, find(officeOf(w), "StageChips"))
	tap(find(officeOf(w), "Stage2"), label .. ": the Seed chip")
	tap(kid(kid(officeOf(w), "OfficeBuilding"), "BuyButton"), label .. ": buy the Small Office")
	run(0.3)
	local b = lastCall(w, "BuyBuilding")
	check(label .. ": the building's Buy sends BuyBuilding only", b and b.args.n == 1)
	check(label .. ": after the purchase the Small Office says Yours", prop(kid(kid(officeOf(w), "OfficeBuilding"), "BuyButton"), "Text") == "Yours")
	officeWiring(w, label)
	noErrors(label)
end

-- Hire tab: the desk card and the direct hires ------------------------------------------------------------------------
for _, size in ipairs({ { 667, 375, 36 }, { 320, 568, 36 } }) do
	local label = "hire " .. size[1] .. "x" .. size[2]
	local w = startOffice({ w = size[1], h = size[2], bar = size[3], owned = 1, cash = 1e9, income = 3, attrs = { IpoValuation = 0, IpoCount = 0, Building = 1 } })
	tap(find(officeOf(w), "StageHire"), label .. ": the Hire chip")
	run(0.2)
	local page = hireOf(w)
	local desk = kid(page, "HireDesk")
	check(label .. ": the desk card offers desk 2 at its price", prop(kid(desk, "BuyButton"), "Text") == OC.money(OC.Bought[1].price), prop(kid(desk, "BuyButton"), "Text"))
	local list = OC.hireList(w.module("CreatureConfig"))
	local hiresOk, why = #list > 0, nil
	for i, offer in ipairs(list) do
		local c = kid(page, "Hire" .. i)
		if not c or prop(kid(c, "BuyButton"), "Text") ~= OC.money(offer.price) then hiresOk, why = false, "Hire" .. i .. ": " .. tostring(prop(kid(c, "BuyButton"), "Text")) end
		if c and not string.find(prop(kid(c, "Description"), "Text", ""), OC.money(offer.eggAverage), 1, true) then hiresOk, why = false, "Hire" .. i .. " shows no egg comparison" end
	end
	check(label .. ": every direct hire shows its price and what an egg pays on average for the same rarity", hiresOk, why)
	check(label .. ": the Hire chip shows no item and no building", not prop(card(w, 1), "Visible", true) and not prop(kid(page, "OfficeBuilding"), "Visible", true))
	scrollTo(w, desk)
	tap(kid(desk, "BuyButton"), label .. ": buy a desk")
	run(0.3)
	local d = lastCall(w, "BuyDesk")
	check(label .. ": a desk's Buy sends BuyDesk only", d and d.args.n == 1)
	scrollTo(w, kid(page, "Hire1"))
	tap(kid(kid(page, "Hire1"), "BuyButton"), label .. ": hire the first")
	run(0.3)
	local h = lastCall(w, "Hire")
	check(label .. ": a hire's Buy sends Hire and its number only", h and h.args[2] == 1 and h.args.n == 2)
	screenChecks(w, label)
	officeWiring(w, label)
	d9Office(w, label)
	noErrors(label)
end

-- The server says no: the message shows, nothing is pretended ---------------------------------------------------------
do
	local label = "office refused"
	local w = startOffice({ w = 667, h = 375, bar = 36, owned = 1, cash = 0, income = 3, attrs = { IpoValuation = 0, IpoCount = 0, Building = 1 } })
	w.refuseWith = "You need $120 for Coffee Machine"
	tap(find(officeOf(w), "Stage1"), label .. ": the Garage chip")
	scrollTo(w, card(w, 2))
	tap(kid(card(w, 2), "BuyButton"), label .. ": a Buy the server refuses")
	run(0.3)
	check(label .. ": the server's reason shows in the window", prop(find(win(w), "StatusLine"), "Text") == "You need $120 for Coffee Machine", prop(find(win(w), "StatusLine"), "Text"))
	check(label .. ": nothing is bought", w.player:GetAttribute("Upgrade2") ~= true)
	noErrors(label)
end
"""



def upgrades_lua():
    """The office catalog (overhaul 2: OfficeConfig.Items, what TycoonCore's UPGRADES is built from) as a Luau table."""
    text = read("OfficeConfig.lua")
    block = text[text.index("--ITEMS-START"):text.index("--ITEMS-END")]
    rows = re.findall(r'key = "([^"]+)", icon = "([^"]*)", stage = (\d), price = (\d+), income = (\d+)', block)
    if len(rows) < 60:
        raise SystemExit("shop_ux_test: OfficeConfig.Items changed (%d rows found): the Office tests must be checked again" % len(rows))
    return "{ " + ", ".join('{ name = "%s", icon = "%s", stage = %s, cost = %s, income = %s }' % r for r in rows) + " }"


MODULES = ("ShopConfig", "CreatureConfig", "IpoConfig", "TaskConfig", "OfficeConfig")


def screen_guis(client=None):
    """Every ScreenGui the client scripts make: name -> {file, var, order (DisplayOrder, 0 when unset), inset}.
    client replaces ShopClient.lua's text."""
    found = {}
    for name in sorted(os.listdir(ROOT)):
        if not name.endswith("Client.lua"):
            continue
        text = code_only(client if (name == CLIENT and client is not None) else read(name))
        for var, body in re.findall(r'local (\w+) = make\("ScreenGui", \{(.*?)\n\}\)', text, re.S):
            gui = re.search(r'Name = "(\w+)"', body)
            order = re.search(r"DisplayOrder = (-?\d+)", body)
            found[gui.group(1) if gui else var] = {"file": name, "var": var, "order": int(order.group(1)) if order else 0,
                                                   "inset": "IgnoreGuiInset = true" in body}
    return found


def hud_buttons(client=None):
    """The five HUD buttons: name -> {slot, gui (the ScreenGui's name), order}, read from the four client scripts. Each must
    still use the shared HUD layout (64 px row under 460 px, 76 px column), or the shop's HUD checks must be redone."""
    guis = screen_guis(client)
    by_var = {(g["file"], g["var"]): name for name, g in guis.items()}
    texts = {f: code_only(client if (f == CLIENT and client is not None) else read(f))
             for f in ("EmployeeClient.lua", "ShopClient.lua", "PoachClient.lua", "IpoClient.lua")}
    found = {}

    def parent_of(f, pattern):
        m = re.search(pattern + r'.*?Parent = (\w+),', texts[f], re.S)
        return by_var.get((f, m.group(1))) if m else None

    employee_gui = parent_of("EmployeeClient.lua", r"local function hudButton\(")
    for name, slot in re.findall(r'hudButton\("(\w+Button)", "[^"]*", (\d)\)', texts["EmployeeClient.lua"]):
        found[name] = {"slot": int(slot), "gui": employee_gui}
    found["ShopButton"] = {"slot": 1 if "placeHudButton(shopButton, 1)" in texts["ShopClient.lua"] else None,
                           "gui": parent_of("ShopClient.lua", r"local shopButton = make\(\"TextButton\", \{")}
    for f, var, name in (("PoachClient.lua", "poachButton", "PoachButton"), ("IpoClient.lua", "ipoButton", "IpoButton")):
        slot = re.search(r"local HUD_SLOT = (\d)", texts[f])
        found[name] = {"slot": int(slot.group(1)) if slot else None, "gui": parent_of(f, r"local %s = make\(\"TextButton\", \{" % var)}
    shared = all(("10 + slot * 72, 6" in s or "10 + HUD_SLOT * 72, 6" in s) and ("(slot - 2) * 86" in s or "(HUD_SLOT - 2) * 86" in s)
                 and "AbsoluteSize.Y < 460" in s for s in texts.values())
    slots = sorted(b["slot"] for b in found.values() if b["slot"] is not None)
    if not shared or slots != [0, 1, 2, 3, 4] or any(b["gui"] is None for b in found.values()):
        raise SystemExit("shop_ux_test: the HUD buttons changed (%r): the shop's HUD layer checks must be checked again" % found)
    for b in found.values():
        b["order"] = guis[b["gui"]]["order"]
    return found


def lua_quote(text):
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def toast_texts():
    """Every text the shop's toast can be given, built from the sources: what ShopServer.lua and TycoonCore.lua send
    through ShopNotify (with ShopConfig's names and effects, and the shortest and a very long Cash amount), the client's
    own, and the Office refusals (they show in the hero card, never the toast, but get the same test). Returns
    (rows, problems): rows are (where, text), problems the ShopNotify calls this list does not know (a named check)."""
    server, core, poach, cfg = read("ShopServer.lua"), read("TycoonCore.lua"), read("PoachServer.lua"), read("ShopConfig.lua")
    client = read(CLIENT)
    problems = []

    def at(name, text, fragment):
        i = text.find(fragment)
        if i < 0:
            problems.append("%s no longer has %s" % (name, fragment))
            return name + ":?"
        return "%s:%d" % (name, text.count("\n", 0, i) + 1)

    passes = cfg[cfg.index("ShopConfig.Passes = {"):cfg.index("ShopConfig.Products = {")]
    products = cfg[cfg.index("ShopConfig.Products = {"):]
    pass_names = re.findall(r'^\t\tname = "([^"]+)",', passes, re.M)
    rows = []
    for fragment, make in (('notify(player, pass.name .. " unlocked!")', lambda n: n + " unlocked!"),
                           ('notify(player, "Roblox is slow to confirm " .. pass.name .. ". It will unlock by itself when Roblox answers (or when you rejoin).")',
                            lambda n: "Roblox is slow to confirm " + n + ". It will unlock by itself when Roblox answers (or when you rejoin)."),
                           ('notify(player, "Confirming " .. pass.name .. " with Roblox...")', lambda n: "Confirming " + n + " with Roblox...")):
        where = at("ShopServer.lua", server, fragment)
        rows += [(where, make(n)) for n in pass_names]
    where = at("ShopServer.lua", server, 'notify(player, product.name .. ": " .. gained)')
    money = lambda n: "$" + "{:,}".format(n)
    for key, name, effect in re.findall(r'key = "(\w+)",.*?name = "([^"]+)",.*?effect = \{([^}]*)\}', products, re.S):
        number = lambda field: int(re.search(field + r" = (\d+)", effect).group(1))
        if "incomeMinutes" in effect:
            at("ShopServer.lua", server, 'table.insert(gained, "+" .. ShopConfig.formatCash(amount))')
            rows += [(where, name + ": +" + money(number("minCash"))), (where, name + ": +" + money(999999999999))]
        if "luckMinutes" in effect:
            at("ShopServer.lua", server, '"+" .. effect.luckMinutes .. " min of Luck Boost, kept for later (your hires follow a fixed order)"')
            at("ShopServer.lua", server, '"+" .. effect.luckMinutes .. " min of Luck Boost"')
            rows += [(where, "%s: +%d min of Luck Boost" % (name, number("luckMinutes"))),
                     (where, "%s: +%d min of Luck Boost, kept for later (your hires follow a fixed order)" % (name, number("luckMinutes")))]
        if "instantHatches" in effect:
            at("ShopServer.lua", server, '"+" .. effect.instantHatches .. " Instant Hatch"')
            rows.append((where, "%s: +%d Instant Hatch" % (name, number("instantHatches"))))
        if "shieldMinutes" in effect:
            at("PoachServer.lua", poach, '"+" .. effect.shieldMinutes .. " min of Poach Shield"')
            rows.append((where, "%s: +%d min of Poach Shield" % (name, number("shieldMinutes"))))
    vip = 'notify(player, "The VIP Lounge is for VIP pass holders only.")'
    rows.append((at("ShopServer.lua", server, vip), "The VIP Lounge is for VIP pass holders only."))
    # lobby L3: the lounge door for a player with no garage yet, and the claim's refusals (TycoonCore sends LobbyConfig's)
    door = 'notify(player, "Claim a garage first: your passes load with your company")'
    rows.append((at("ShopServer.lua", server, door), "Claim a garage first: your passes load with your company"))
    lobby = read("LobbyConfig.lua")
    where = at("TycoonCore.lua", core, "ShopServer.notify(player, reason)")
    for key in ("Off", "Unknown", "Mine", "Saving", "Taken", "ClosingNow", "Far", "TooFast"):
        m = re.search(r'^\t%s = "([^"]*)",' % key, lobby, re.M)
        if not m:
            problems.append("LobbyConfig.lua no longer has Texts.%s" % key)
            continue
        rows.append((where, m.group(1).replace("%s", "W" * 20)))  # a display name is at most 20 characters
    for const in ("SAVE_TROUBLE_TEXT", "SAVE_BACK_TEXT"):
        m = re.search(r'^local %s = "([^"]*)"' % const, core, re.M)
        if not m:
            problems.append("TycoonCore.lua no longer has " + const)
            continue
        rows.append(("TycoonCore.lua:%d" % (core.count("\n", 0, m.start()) + 1), m.group(1)))
        at("TycoonCore.lua", core, "ShopServer.notify(player, %s)" % const)
    # overhaul 2: the funding-round toast (TycoonCore stageUpToast): "<icon> <stage> reached! The <building> is in SHOP > Office",
    # and " · tap IPO to go public" on the last stage; the stage names from IpoConfig, the buildings' from OfficeConfig
    ipo, office = read("IpoConfig.lua"), read("OfficeConfig.lua")
    stages = re.findall(r'\{ key = "(\w+)", name = "([^"]+)", icon = "([^"]+)", valuation = \d+ \}', ipo)
    buildings = re.findall(r'\{ stage = \d, name = "([^"]+)", price = \d+', office)
    where = at("TycoonCore.lua", core, "ShopServer.notify(player, text)")
    if len(stages) < 2 or len(buildings) != len(stages):
        problems.append("the stage-up toast rows need IpoConfig's stages and OfficeConfig's buildings (%d, %d)" % (len(stages), len(buildings)))
    for i in range(1, len(stages)):
        text = "%s %s reached!" % (stages[i][2], stages[i][1])
        if i < len(buildings):
            text += " The %s is in SHOP > Office" % buildings[i]
        if i == len(stages) - 1:
            text += " · tap IPO to go public"
        rows.append((where, text))
    for text in ("Couldn't open the purchase. Please try again.", "Couldn't buy that. Please try again."):
        rows.append((at(CLIENT, client, '"%s"' % text), text))
    # the Office refusals (overhaul 2): TycoonCore's request checks, and OfficeConfig.checkItem's (names and prices from the catalog)
    items = re.findall(r'key = "([^"]+)", icon = "[^"]*", stage = (\d), price = (\d+)', office)
    stage_names = re.findall(r'"([^"]+)"', office[office.index("OfficeConfig.StageNames = {"):office.index("}", office.index("OfficeConfig.StageNames = {"))])

    def money(amount):
        for limit, suffix in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
            if amount >= limit:
                return "$" + ("%.1f" % (amount / limit)).replace(".0", "") + suffix
        return "$%d" % amount
    for fragment, texts in (('"Still loading, try again in a moment"', ["Still loading, try again in a moment"]),
                            ('"Unknown upgrade"', ["Unknown upgrade"]), ('"Too fast"', ["Too fast"])):
        where = at("TycoonCore.lua", core, fragment)
        rows += [(where, x) for x in texts]
    for fragment, texts in (('item.key .. " is already yours"', [k + " is already yours" for k, _, _ in items]),
                            ('"Buy the " .. OfficeConfig.FirstItem .. " first"', ["Buy the Desk first"]),
                            ('"Unlocks at " .. (OfficeConfig.StageNames[stage] or "?")', ["Unlocks at " + n for n in stage_names]),
                            ('"You need " .. money(item.price) .. " for " .. item.key', ["You need " + money(int(p)) + " for " + k for k, _, p in items])):
        where = at("OfficeConfig.lua", office, fragment)
        rows += [(where, x) for x in texts]
    for text in ("Bad request", "Unknown action"):
        rows.append((at("ShopServer.lua", server, '"%s"' % text), text))
    # every ShopNotify call is one of the above
    known = server.count('notify(player, pass.name .. " unlocked!")') + server.count('notify(player, "Roblox is slow to confirm ')
    known += server.count('notify(player, "Confirming ') + server.count('notify(player, product.name .. ": " .. gained)') + server.count(vip)
    known += server.count(door)
    calls = len(re.findall(r"^\s*notify\(player,", code_only(server), re.M))
    calls -= len(re.findall(r"^function ShopServer\.notify\(player, text\)\n\tnotify\(player, text\)\nend", server, re.M))
    if calls != known:
        problems.append("ShopServer.lua has %d notify(player, ...) calls, the toast tests know %d" % (calls, known))
    outside = sorted(set(re.findall(r"(?<!function )ShopServer\.notify\(player, (\w+)\)", "".join(code_only(read(f)) for f in sorted(os.listdir(ROOT)) if f.endswith(".lua")))))
    if outside != ["SAVE_BACK_TEXT", "SAVE_TROUBLE_TEXT", "reason", "text"]:  # text: TycoonCore's stage-up toast (the rows above)
        problems.append("ShopServer.notify is called with %r" % outside)
    return rows, problems


def toast_lua():
    rows, _ = toast_texts()
    return "{ " + ", ".join("{ where = %s, text = %s }" % (lua_quote(w), lua_quote(x)) for w, x in rows) + " }"


def hud_lua():
    """The other scripts' four HUD buttons as a Luau list (the SHOP button is checked on the real instance)."""
    rows = sorted((b["slot"], name, b["gui"], b["order"]) for name, b in hud_buttons().items() if name != "ShopButton")
    return "{ " + ", ".join('{ name = "%s", slot = %d, gui = "%s", order = %d }' % (n, s, g, o) for s, n, g, o in rows) + " }"


def sectionize(text):
    """Wraps every top-level block of checks (a `do` or `for` block at column 0) in section(name, function() ... end),
    named after the comment line above it. Helpers (local functions and values at column 0) stay outside."""
    out, name = [], "checks"
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("-- "):
            name = line[3:].split(" ---")[0].strip().replace("\\", "").replace('"', "'")
        if line == "do" or line.startswith("for "):
            j = i + 1
            while not (lines[j] == "end" or lines[j].startswith("end ")):
                j += 1
            out.append('section("%s", function()' % name)
            out.extend(lines[i:j + 1])
            out.append("end)")
            i = j + 1
            continue
        out.append(line)
        i += 1
    return "\n".join(out)


def program(layout=None, client=None):
    """The whole Luau program: the fake, the real modules and the scenarios. layout and client replace the files' text."""
    sources = {name: read(name + ".lua") for name in MODULES}
    sources["ShopLayout"] = layout if layout is not None else read(LAYOUT)
    modules = "{ " + ", ".join("%s = %s" % (name, long_string(text)) for name, text in sorted(sources.items())) + " }"
    world = (WORLD.replace("__UPGRADES__", upgrades_lua())
             .replace("__CLIENT__", long_string(client if client is not None else read(CLIENT)))
             .replace("__MODULES__", modules))
    client_tests = (CLIENT_TESTS.replace("__HUD__", hud_lua()).replace("__TOAST_TEXTS__", toast_lua())
                    .replace("__TOAST_REPORT__", "true" if "--toast-report" in sys.argv else "false"))
    tests = "".join(sectionize(block) for block in (LAYOUT_TESTS, LADDER_TESTS, client_tests, OFFICE_TESTS))
    return PRELUDE + world + tests + 'print_real(string.format("%d passed, %d failed", passed, failed))\n'


# String literals of ShopClient.lua (as it was before S1, world-icons-pass 6bc827c) that use one of the four D9 words.
# They stay as they are: Luck Boost's luckText line, the attribute and perk names and the Studio Debug rows. Every other
# literal, old or new, in ShopClient.lua and ShopLayout.lua must be free of them.
D9_WORDS = ("odds", "chance", "luck", "random")
D9_ALLOWED = {
    "BaseLuck", "IpoPerk_BaseLuck", "LuckBoostUntil", "Odds weight x%s for %s hires.", "Paid random items: restricted on/off",
    "Pretends Roblox's policy check said the other thing: fixed hire order and no Luck Boost, or back to random hires. "
    "Not saved: a rejoin asks Roblox again.",
    "RandomRestricted", "ToggleRandomRestricted",
}
# luckText as it was: Luck Boost's numbers on its card face, before buying (Roblox's Paid Random Items policy)
LUCK_TEXT = """local function luckText(effect)
	local names = {}
	for _, rarity in ipairs(CreatureConfig.Rarities) do
		if rarity.luckBoosted then
			table.insert(names, rarity.key)
		end
	end
	local text = string.format("Odds weight x%s for %s hires.", tostring(effect.luckMultiplier), table.concat(names, ", "))
	local egg = CreatureConfig.Eggs[#CreatureConfig.Eggs]
	if egg then
		local perk = 1 + IpoConfig.perkValue("BaseLuck", player:GetAttribute("IpoPerk_BaseLuck") or 0)
		local before = CreatureConfig.rarityOdds(CreatureConfig.getCreatureOdds(egg, perk))
		local after = CreatureConfig.rarityOdds(CreatureConfig.getCreatureOdds(egg, perk * effect.luckMultiplier))
		local rarest, boosted = before[#before], after[#after]
		if rarest and boosted then
			text ..= string.format(" %s %s: %s -> %s.", egg.name, rarest.rarity,
				CreatureConfig.formatOdds(rarest.units), CreatureConfig.formatOdds(boosted.units))
		end
	end
	return text
end
"""


def static_checks(layout=None, client=None, out=None):
    """Checks on the source text of ShopLayout.lua and ShopClient.lua (layout and client replace the files' text).
    A FAIL line is printed, or added to the list out (the mutation runs: several run at once, in threads, so they never
    redirect sys.stdout)."""
    layout = layout if layout is not None else read(LAYOUT)
    client = client if client is not None else read(CLIENT)
    passed, failed = 0, 0

    def check(name, cond, extra=None):
        nonlocal passed, failed
        if cond:
            passed += 1
        else:
            failed += 1
            line = "FAIL: " + name + (" -- " + str(extra) if extra else "")
            if out is None:
                print(line)
            else:
                out.append(line)

    lay, cli = code_only(layout), code_only(client)
    check("ShopLayout.lua is pure: no GetService, require, Instance, game, workspace, task or remote",
          not any(w in lay for w in ("GetService", "require(", "Instance", "game", "workspace", "task.", "Remote", "player")))
    for name, code in ((LAYOUT, lay), (CLIENT, cli)):
        for word in ('Instance.new("Remote', ".Touched", "math.random", "Random.new", "DataStore", "SetAsync", "UpdateAsync", "addEarnings",
                     "FireServer", "loadstring", "PromptPurchase(", "TeleportService"):
            check("%s never uses %s (no new remote, no save, nothing random, no Touched handler, no earnings)" % (name, word), word not in code)
        offending = sorted(set(s for s in lua_strings(code) if any(w in s.lower() for w in D9_WORDS) and not (name == CLIENT and s in D9_ALLOWED)))
        check("%s: every string with odds, chance, luck or random was already there (luckText, Debug rows, attribute names; D9)" % name,
              not offending, offending[:3])
    invokes = re.findall(r"actionRemote:InvokeServer\(([^)]*)\)", cli)
    check("ShopClient.lua: the Office sends only \"Office\", an action alone (BuyBuilding, BuyDesk) or an action and a number (never a price)",
          sorted(invokes) == ['"Office"', 'action', 'action, index'], invokes)
    others = [a for a in re.findall(r"(\w+):InvokeServer\(([^)]*)\)", cli) if a[0] != "actionRemote"]
    check("ShopClient.lua: the only other request is the Studio Debug tab's (debugRemote, action and key)", others == [("debugRemote", "action, key")], others)
    names = sorted(set(re.findall(r'remotes:(?:WaitForChild|FindFirstChild)\("(\w+)"', cli)))
    check("ShopClient.lua: it uses only the server's existing remotes (ShopNotify, ShopAction, ShopDebug)", names == ["ShopAction", "ShopDebug", "ShopNotify"], names)
    check("ShopClient.lua: luckText is the function it was (Luck Boost's numbers on its card face)", LUCK_TEXT in client)
    check("ShopClient.lua: Luck Boost's card face still starts with luckText", 'text = luckText(effect) .. " " .. text' in cli)
    check("ShopClient.lua: the HUD button and its slot stay (EmployeeClient, PoachClient, IpoClient and the icon tests use them)",
          'Name = "ShopButton"' in cli and "placeHudButton(shopButton, 1)" in cli and "buy = Color3.fromRGB(0, 200, 90)" in cli)
    check("ShopClient.lua: it requires ShopLayout from ReplicatedStorage", 'require(ReplicatedStorage:WaitForChild("ShopLayout"))' in cli)

    # The layers (ScreenGui DisplayOrder) of every client script: the call tray under the HUD, the HUD under every
    # window, the shop window with the Poach, IPO and Daily windows, the hatch reveal and the poach result above all
    guis = screen_guis(client)
    huds = hud_buttons(client)
    order = lambda name: guis[name]["order"] if name in guis else None
    hud_orders = [b["order"] for b in huds.values()]
    shop = order("ShopGui")
    check("layers: the shop window (ShopGui) draws above every HUD button's ScreenGui (DisplayOrder)",
          shop is not None and all(o < shop for o in hud_orders), {n: (b["gui"], b["order"]) for n, b in huds.items()})
    check("layers: the shop window is on the windows' layer, with the Poach, IPO and Daily windows (DisplayOrder 5)",
          shop == order("PoachWindowGui") == order("IpoWindowGui") == order("DailyWindowGui") == 5, shop)
    check("layers: the SHOP button sits with the HUD (its own ScreenGui, under every window, like POACH and IPO)",
          huds["ShopButton"]["gui"] != "ShopGui" and huds["ShopButton"]["order"] == order("PoachGui") == order("IpoGui") == -1, huds["ShopButton"])
    check("layers: the call tray (TaskGui) draws under every HUD button and under the shop's toast (it never hides a pop-up)",
          order("TaskGui") is not None and all(order("TaskGui") < o for o in hud_orders) and shop is not None and order("TaskGui") < shop)
    check("layers: the hatch reveal and the poach result still draw above the shop window",
          shop is not None and order("HatchRevealGui") > shop and order("PoachResultGui") > shop)
    toast = re.search(r'local toast = make\("TextLabel", \{.*?Parent = (\w+),', cli, re.S)
    check("layers: the shop's toast is in ShopGui, with the window (shown only while the window is closed)",
          toast is not None and guis.get("ShopGui", {}).get("var") == toast.group(1) and guis["ShopGui"]["file"] == CLIENT)
    _, toast_problems = toast_texts()
    check("toast: every ShopNotify text of ShopServer.lua and TycoonCore.lua (and the refusals) is in the toast tests",
          not toast_problems, toast_problems[:2])
    check("layers: the shop's ScreenGuis keep Roblox's top bar outside them (IgnoreGuiInset off, the same GUI space as the HUD)",
          not guis.get("ShopGui", {"inset": True})["inset"] and not guis[huds["ShopButton"]["gui"]]["inset"])
    return passed, failed


def apply_mutation(text, old, new, what):
    """One change (old, new), or several at once when old and new are tuples (a rule held in two places)."""
    if isinstance(old, tuple):
        for o, n in zip(old, new):
            text = apply_mutation(text, o, n, what)
        return text
    if text.count(old) < 1:
        raise SystemExit("mutation target not found in %s: %r" % (what, old))
    return text.replace(old, new, 1)


L, C = LAYOUT, CLIENT
# Each breaks one rule of ShopLayout or ShopClient: the named check (a part of a FAIL line) must catch it, and the run
# must still finish with its summary (a crash does not count).
MUTANTS = [
    ("the header 34 px tall", L, "ShopLayout.HEADER = 44", "ShopLayout.HEADER = 34", "header items are 44 px tall"),
    ("a 34 px tab", L, "ShopLayout.TAP = 44", "ShopLayout.TAP = 34", "every tab is at least 44 x 44"),
    ("text minimum 8 in ShopLayout", L, "ShopLayout.MIN_TEXT = 16", "ShopLayout.MIN_TEXT = 8", "no text box with a minimum under 16 px"),
    ("fitText back to a minimum of 8", C, "MinTextSize = MIN_TEXT", "MinTextSize = 8", "no text box with a minimum under 16 px"),
    ("descriptions at 14 px", C, "\tinst.TextSize = MIN_TEXT\n", "\tinst.TextSize = 14\n", "no text box with a minimum under 16 px"),
    ("no rail: landscape keeps the row", L, "L.rail = guiW > guiH", "L.rail = false", "landscape has the tab rail"),
    ("the bottom slot over the pages (they keep their height)", L, "\t\t\tbottom = L.bottom.y - gap\n", "",
     "the bottom slot is as tall as asked, under the pages"),
    ("the window bigger than the GUI", L, "ShopLayout.WINDOW_SHARE = 0.92", "ShopLayout.WINDOW_SHARE = 1.05", "the window stays inside the GUI"),
    ("\"?\" on top of the X", L, "ShopLayout.HELP_RIGHT = 50", "ShopLayout.HELP_RIGHT = 30", "header items never overlap"),
    ("rail tabs closer than their height", L, "L.tabs[i] = rect(c.x, c.y + (i - 1) * (tap + L.tabGap), ShopLayout.RAIL_W, tap)",
     "L.tabs[i] = rect(c.x, c.y + (i - 1) * (tap - 4 + L.tabGap), ShopLayout.RAIL_W, tap)", "tabs never overlap each other"),
    ("tab buttons without the Tab prefix", C, 'Name = "Tab" .. name,', "Name = name,", "every Name exists after the Office list arrives"),
    ("pages without their names", C, 'Name = name .. "Page",', "Name = name,", "every Name exists after the Office list arrives"),
    ("cards' buttons not named BuyButton", C, 'Name = "BuyButton",', 'Name = "Button",', "every card's button is named BuyButton"),
    ("Office cards without their names", C, 'item.key, "Office" .. i)', 'item.key, "Card" .. i)', "every Name exists after the Office list arrives"),
    ("the help button without its name", C, 'Name = "HelpButton",', 'Name = "Help",', "every Name exists after the Office list arrives"),
    ("TutorialStrip shown with no banner", C, "tutorialStrip.Visible = banner ~= nil and statusText == nil", "tutorialStrip.Visible = statusText == nil",
     "TutorialStrip is inert while TutorialBanner is unset"),
    ("TutorialStrip takes no room from the pages", C, "\tif banner then\n\t\tbottomH = L.stripH\n\tend\n", "",
     "TutorialStrip shows the banner's text at the window's bottom"),
    ("messages always as the toast", C, "\tif window.Visible then\n\t\tshowStatus(text)\n\telse\n\t\tshowToast(text)\n\tend", "\tshowToast(text)",
     "a message goes to the status line, never the toast"),
    ("the status line over the pages", C, "\tif statusText then\n\t\tbottomH = math.max(", "\tif false then\n\t\tbottomH = math.max(",
     "the status line takes its room from the pages"),
    ("a toast that stays up when the shop opens", C, "\t\tif toast.Visible then\n", "\t\tif false then\n",
     "opening the shop moves a toast that is still up into the window's status line"),
    ("the help card leaves the pages showing under it", C, "\tpages.Visible = not open\n", "", "the pages hide while the help card is open"),
    ("the help card's Back button 30 px tall", L, "back = rect(w - 10 - backW, 10, backW, ShopLayout.TAP),", "back = rect(w - 10 - backW, 10, backW, 30),",
     "every tap target at least 44 x 44"),
    ("a 40 px Buy button", L, "ShopLayout.BUTTON_H = 48", "ShopLayout.BUTTON_H = 40", "every tap target at least 44 x 44"),
    ("narrow cards' button 40 wide", L, "C.button = rect(cardW - 8 - 72, 8 + math.floor((top - buttonH) / 2), 72, buttonH)",
     "C.button = rect(cardW - 8 - 72, 8 + math.floor((top - buttonH) / 2), 40, buttonH)", "every tap target at least 44 x 44"),
    ("wide cards' description under the button", L, "return math.max(0, nameW), math.max(0, cardW - 208)",
     "return math.max(0, nameW), math.max(0, cardW - 68)", "every piece inside its card, none on another"),
    ("prompts without the isForSale check", C, "if pending[item.key] or noGarage() or not ShopConfig.isForSale(item, randomRestricted()) then return end",
     "if pending[item.key] or noGarage() then return end", "is never prompted"),
    ("Luck Boost shown to a restricted player", C, "desc.Parent.Visible = not (product.changesOdds and randomRestricted())",
     "desc.Parent.Visible = true", "Luck Boost hidden while RandomRestricted is not false"),
    ("lobby L3: a Robux purchase prompted before the player has a garage", C, "\tif pending[item.key] or noGarage() or not ShopConfig.isForSale(item, randomRestricted()) then return end",
     "\tif pending[item.key] or not ShopConfig.isForSale(item, randomRestricted()) then return end", "No garage yet: a pass is never prompted before a garage"),
    ("lobby L3: a product's button shows its price before the player has a garage", C, "\t\t\telseif noGarage() then\n\t\t\t\tsetButton(button, \"Claim garage\", COLORS.disabled, false)\n\t\t\telseif not ShopConfig.isForSale(product) then",
     "\t\t\telseif not ShopConfig.isForSale(product) then", "No garage yet: a product is never prompted before a garage"),
    ("an unknown RandomRestricted counted as not restricted", C, 'return player:GetAttribute("RandomRestricted") ~= false',
     'return player:GetAttribute("RandomRestricted") == true', "Luck Boost hidden while RandomRestricted is not false"),
    ("a price sent from the client", C, 'return office.actionRemote:InvokeServer(action, index)\n', 'return office.actionRemote:InvokeServer(action, index, 25)\n',
     "a Buy tap sends only \"BuyUpgrade\" and the item's number"),
    ("a new text with the word chance", C, 'Text = "How the shop works",', 'Text = "How the shop works (chance)",',
     "ShopClient.lua: every string with odds, chance, luck or random was already there"),
    ("luckText reworded", C, 'string.format("Odds weight x%s for %s hires."', 'string.format("Weight x%s for %s hires."',
     "ShopClient.lua: luckText is the function it was"),
    ("the strip 20 px tall on a short window", L, "ShopLayout.STRIP_SHORT = 32", "ShopLayout.STRIP_SHORT = 20", "the strip is 32 px on a short window"),
    # S2: the Office ladder
    ("a wrong next index (the rung after the first not owned)", L, "\t\t\tS.nextIndex = i\n", "\t\t\tS.nextIndex = i + 1\n",
     "the next rung is the first not owned"),
    ("the bar not clamped", L, "return math.clamp(cash / price, 0, 1)", "return cash / price", "barFill stays in 0..1"),
    ("Buy shown when the Cash is short", L, "\t\telseif cash >= cost then\n", "\t\telseif true then\n",
     "the hero's button (Get it free, Buy $X, or Need $X more"),
    ("minutes shown as seconds", L, "\tif seconds < 120 then\n", "\tif seconds < 1e9 then\n", "timeText: 5,000 s reads about 84 min"),
    ("the time rounded down", L, "local seconds = math.ceil(need / income)", "local seconds = math.floor(need / income)",
     "timeText: $25 at $1/s is about 25 s, at $2/s about 13 s"),
    ("locked rungs name themselves", L, '"Unlocks after " .. tostring(before and before.name or "the one before")', '"Unlocks after " .. tostring(upg.name)',
     "Unlocks after <the one before>"),
    ("the summary counts one too many", L, 'S.summary = { title = S.owned .. " of "', 'S.summary = { title = (S.owned + 1) .. " of "',
     "the summary says k of 6 bought"),
    ("no Office complete banner", L, "S.complete = S.count > 0 and S.nextIndex == nil", "S.complete = false", "the Office complete banner"),
    ("the bought rung folds at once (no Bought!)", L, "local mine = owned[i] == true and i ~= bought", "local mine = owned[i] == true",
     "ladder: the upgrade just bought stays the hero a moment"),
    ("the free Desk says Buy $0", L, '"Get it free", "buy", "buy"', '"Buy $0", "buy", "buy"', "ladder: 0 owned, $0, $0/s: the hero's button"),
    ("Buy offered while the request runs", L, "\t\telseif busy then\n", "\t\telseif false then\n", "while the request runs the hero says ..."),
    ("no busy state: a second tap sends again", C, "\tif office.busy or not office.actionRemote then return end", "\tif not office.actionRemote then return end",
     "a second tap while the request runs sends nothing"),
    ("narrow rows too short for two lines", L, "ShopLayout.ROW_NARROW = 72", "ShopLayout.ROW_NARROW = 56", "office rows and the hero: every piece inside"),
    ("the reveal scrolls past the hero's top", L, "local want = math.min(math.max(0, y + h - view), y)", "local want = math.max(0, y + h - view)",
     "revealScroll: never past the hero's top"),
    ("BEST VALUE on a Coming soon item", L, "if minutes > 0 and price > 0 and forSale(product) then", "if minutes > 0 and price > 0 then",
     "never on a Coming soon item"),
    ("BEST VALUE on the worst pack", L, "if bestRate == nil or rate > bestRate then", "if bestRate == nil or rate < bestRate then", "BEST VALUE is the Vault"),
    # Review fixes (shop-fix)
    ("ShopGui back at DisplayOrder 0 (EGGS and TEAM over the tab rail)", C, "\tDisplayOrder = 5,\n", "",
     "no HUD button that may draw above the shop (DisplayOrder at or above ShopGui's) covers a tab"),
    ("the SHOP button back in the window's ScreenGui", C, "\tParent = hudGui,\n})\nround(shopButton, 18)", "\tParent = gui,\n})\nround(shopButton, 18)",
     "no HUD button that may draw above the shop (DisplayOrder at or above ShopGui's) covers a tab"),
    ("the SHOP button's ScreenGui on the windows' layer (5)", C, "\tDisplayOrder = -1,\n", "\tDisplayOrder = 5,\n",
     "no HUD button that may draw above the shop (DisplayOrder at or above ShopGui's) covers a tab"),
    ("ShopGui under the other windows' layer (3)", C, "\tDisplayOrder = 5,\n", "\tDisplayOrder = 3,\n",
     "layers: the shop window is on the windows' layer, with the Poach, IPO and Daily windows"),
    ("closing the shop drops a message still in its line", C, "\tif wasOpen and not open then\n\t\tstatusToToast()\n\tend\n", "",
     "closing the shop moves a message still in its line to the toast"),
    ("another window opening drops the shop's message", C, "\t\twindow.Visible = false\n\t\tstatusToToast()\n", "\t\twindow.Visible = false\n",
     "closing the shop moves a message still in its line to the toast"),
    ("the moved message stays in the window's line too", C, "\tstatusToken += 1 -- the line's own timer does nothing more\n\tstatusText = nil\n", "",
     "once: the window's line is cleared"),
    ("the toast never cut (a long text overflows its lane)", C, "\treturn clampLines(toastText, toast.Font,", "\treturn toastText or clampLines(toastText, toast.Font,",
     "every server text fits the toast's 2 lines"),
    ("the toast cut to 3 lines", C, "local TOAST_LINES = 2", "local TOAST_LINES = 3", "every server text fits the toast's 2 lines"),
    ("a cut toast without its ...", C, ('return (string.gsub(head, "[%s%.,;:]+$", "")) .. "..."', 'local short = (string.gsub(string.sub(text, 1, space - 1), "[%s%.,;:]+$", "")) .. "..."'),
     ('return (string.gsub(head, "[%s%.,;:]+$", ""))', 'local short = (string.gsub(string.sub(text, 1, space - 1), "[%s%.,;:]+$", ""))'),
     "a longer one is its start and ends with ..."),
    ("a short text cut anyway", C, "\tif width <= 0 or fits(text) then\n", "\tif width <= 0 then\n", "a text that fits is shown whole"),
    ("the window's line gets the cut toast", C, "showStatus(toastText) -- the whole message", "showStatus(toast.Text) -- the whole message",
     "opening the shop shows the whole message in the window's line"),
    ("the toast not cut again on a new width", C, "\tif toast.Visible then\n\t\ttoast.Text = toastFace() -- cut again for the new width\n\tend\n", "",
     "a new screen size cuts the toast again for its new width"),
    ("the short form as long as the long one", L, 'infoShort = earns .. "/s" }', 'infoShort = earns .. " every second" }',
     "ladder: 0 owned, $0, $0/s: and has the short form"),
    ("the portrait tabs ignore their labels (Passes in 51 px)", L, "local labelW = math.max(0, finite(tabLabelW and tabLabelW[i], 0))", "local labelW = 0",
     "every tab's label fits its tab on one line at 16 px"),
    ("a portrait row too long for the bar squeezed to even tabs", L, "local tabW = allFit and even or need[i] + extra", "local tabW = even",
     "every tab is as wide as its label at 16 px"),
    ("a portrait row that scrolls has no room for its bar", L, "tap + (L.tabScrolls and ShopLayout.TAB_SCROLLBAR or 0))", "tap)",
     "a row that scrolls has room for its bar under the tabs"),
    ("the tab row never shows its scroll bar", C, "tabBar.ScrollBarThickness = L.tabScrolls and ShopLayout.TAB_SCROLLBAR or 0", "tabBar.ScrollBarThickness = 0",
     "the tab row scrolls sideways to the Debug tab"),
    ("ShopClient never passes the tab labels", C, "\tlocal L = ShopLayout.layout(size.X, size.Y, inset, #tabNames, 0, tabLabelW)", "\tlocal L = ShopLayout.layout(size.X, size.Y, inset, #tabNames, 0)",
     "every tab's label fits its tab on one line at 16 px"),
    ("the strip's letter estimate too narrow (a longer limit)", L, "ShopLayout.CHAR_W = 16 * 0.56 * 1.06", "ShopLayout.CHAR_W = 16 * 0.45 * 1.06",
     "a sentence as long as stripMaxChars fits the strip"),
    ("the strip's letter estimate too wide (a limit far under what fits)", L, "ShopLayout.CHAR_W = 16 * 0.56 * 1.06", "ShopLayout.CHAR_W = 16 * 0.75 * 1.06",
     "the limit is close to what fits"),
    ("stripFits lets one character over through", L, "\treturn count <= limit, count, limit\n", "\treturn count <= limit + 1, count, limit\n",
     "stripFits flags a text one character over the limit"),
    ("the two-line strip counted as one line", L, "\treturn L.short and perLine or 2 * perLine\n", "\treturn perLine\n",
     "the limit is close to what fits"),
    ("a one-line strip counted as two lines", L, "\treturn L.short and perLine or 2 * perLine\n", "\treturn 2 * perLine\n",
     "a sentence as long as stripMaxChars fits the strip"),
    ("a long TutorialBanner never flagged", C, "\tif count > ShopLayout.STRIP_TEXT_LIMIT then\n", "\tif false then\n",
     "a banner one character over the limit is flagged"),
    # overhaul 2: the Office catalog by stage and its Hire chip
    ("a locked item offers its price", C, '\t\telseif stageNow() < item.stage then\n\t\t\tsetButton(button, "Locked", COLORS.disabled, false)',
     '\t\telseif false then\n\t\t\tsetButton(button, "Locked", COLORS.disabled, false)', "Series A's items are shown, Locked"),
    ("the shop opens on the Garage, not the stage reached", C, "\toffice.shown = stageNow()\n\ttask.spawn(fetchOfficeState)", "\toffice.shown = 1\n\ttask.spawn(fetchOfficeState)",
     "the shop opens on the stage reached"),
    ("a locked item's button still sends", C, "\t\tif ownsItem(i) or stageNow() < item.stage then return end", "\t\tif ownsItem(i) then return end",
     "a locked item's button sends nothing"),
    ("the building's Buy sends a number", C, '\t\tofficeRequest("BuyBuilding")', '\t\tofficeRequest("BuyBuilding", 2)', "the building's Buy sends BuyBuilding only"),
    ("the hires without the egg comparison", C, 'offer.rarity, OfficeConfig.money(offer.eggAverage))', 'offer.rarity, "")',
     "every direct hire shows its price and what an egg pays on average"),
]


CRASH_MARKS = ("run to their end (no error in ShopLayout or in the test)", "ShopClient runs without an error")


def sections_of(stdout, static):
    """The FAIL lines of a run, block by block: [(name, lines)]. The source checks are one block of their own."""
    blocks = [("(before the first block)", [])]
    for line in stdout.split("\n"):
        if line.startswith("SECTION "):
            blocks.append((line[8:], []))
        elif line.startswith("FAIL: "):
            blocks[-1][1].append(line)
    blocks.append(("the source checks", [line for line in static if line.startswith("FAIL: ")]))
    return blocks


# The harness checks itself: these break a rule AND raise an uncaught error in the block that checks it (the two old
# forms of mutants 32 and 47, before ShopLayout.ladder and ShopClient.showRung were guarded). Each must be reported as
# not caught: a named check that fails only next to a crash never counts.
HARNESS_SELF_TESTS = [
    ("a wrong next index that also crashes (no guard in the ladder)", L,
     ("\t\t\tS.nextIndex = i\n", "\tif S.nextIndex and not upgrades[S.nextIndex] then\n\t\tS.nextIndex = nil -- never a hero without its upgrade\n\tend\n"),
     ("\t\t\tS.nextIndex = i + 1\n", ""), "the next rung is the first not owned"),
]


def run_mutants(luau, mutants=None):
    """Each mutant counts as caught only when its named check fails in a block of checks that ran to its end with no
    uncaught error: no crash of the block (ShopLayout or the test) and no error inside ShopClient in that block. A
    named check that only fails next to a crash does not count."""
    from concurrent.futures import ThreadPoolExecutor
    texts = {LAYOUT: read(LAYOUT), CLIENT: read(CLIENT)}

    def one(mutant):
        label, filename, old, new, expected = mutant
        changed = dict(texts)
        changed[filename] = apply_mutation(texts[filename], old, new, filename)
        result = run_luau(luau, program(layout=changed[LAYOUT], client=changed[CLIENT]))
        finished = re.search(r"^\d+ passed, \d+ failed$", result.stdout, re.M) is not None
        static = []
        static_checks(layout=changed[LAYOUT], client=changed[CLIENT], out=static)
        blocks = sections_of(result.stdout, static)
        lines = [line for _, block in blocks for line in block]
        crashed = [next((line for line in block if any(mark in line for mark in CRASH_MARKS)), None) for _, block in blocks]
        named = [(i, line) for i, (_, block) in enumerate(blocks) for line in block if expected in line]
        clean = [(i, line) for i, line in named if crashed[i] is None]
        if finished and clean:
            if "--list-mutants" in sys.argv:
                print("caught: %s -- by FAIL: %s" % (label, clean[0][1][6:160]))
            return None
        if not finished:
            why = "it crashed: " + (result.stderr.strip().split("\n")[0] if result.stderr.strip() else "no summary")
        elif named:
            i = named[0][0]
            why = "its named check failed only next to an uncaught error in the block \"%s\": %s" % (blocks[i][0][:60], crashed[i][6:200])
        else:
            why = "the check '%s' did not fail (failed instead: %s)" % (expected, lines[0][6:90] if lines else "nothing")
        return "FAIL: mutation %s: not caught by its named check (%s)" % (label, why)

    mutants = MUTANTS if mutants is None else mutants
    with ThreadPoolExecutor(max_workers=4) as pool:
        outcomes = list(pool.map(one, mutants))
    problems = [o for o in outcomes if o]
    return len(mutants) - len(problems), problems


HASH_TESTS = r"""-- Tests: the hash block of docs/STUDIO_SYNC_SHOP.md, run as it is, on the real files in a tiny fake place ----------
local print_real = print
local passed, failed = 0, 0
local function check(name, cond, extra)
	if cond then passed += 1 else failed += 1; print_real("FAIL: " .. name .. (extra ~= nil and (" -- " .. tostring(extra)) or "")) end
end
local PRINTED = {}
local function print(...)
	local parts = {}
	for i = 1, select("#", ...) do parts[i] = tostring((select(i, ...))) end
	table.insert(PRINTED, table.concat(parts, " "))
end
local SOURCES = __SOURCES__
local function folder(children)
	return { FindFirstChild = function(_, name) return children[name] end }
end
local scripts = { ShopLayout = { Source = SOURCES.ShopLayout }, ShopClient = { Source = SOURCES.ShopClient } }
local services = {
	ReplicatedStorage = folder({ ShopLayout = scripts.ShopLayout }),
	StarterPlayer = folder({ StarterPlayerScripts = folder({ ShopClient = scripts.ShopClient }) }),
}
local game = { GetService = function(_, name) return services[name] end }
local function runBlock()
	table.clear(PRINTED)
	local ok, err = pcall(function()
__HASHBLOCK__
	end)
	local said = {}
	for _, line in ipairs(PRINTED) do
		local name, verdict = string.match(line, "^(%w+) (%u+)")
		if name then said[name] = verdict end
	end
	return ok, err, said
end
local ok, err, said = runBlock()
check("hash block: it runs without an error", ok, err)
check("hash block: ShopLayout prints OK (Luau's SHA-256 of the real file is the one in the table)", said.ShopLayout == "OK", said.ShopLayout)
check("hash block: ShopClient prints OK (Luau's SHA-256 of the real file is the one in the table)", said.ShopClient == "OK", said.ShopClient)
local function runWith(change)
	for name, s in pairs(scripts) do s.Source = change(SOURCES[name]) end
	local _, _, verdicts = runBlock()
	for name, s in pairs(scripts) do s.Source = SOURCES[name] end
	return verdicts
end
local v = runWith(function(source) return string.sub(source, 1, -2) end)
check("hash block: a script whose last newline Studio dropped prints OK (both)", v.ShopLayout == "OK" and v.ShopClient == "OK")
v = runWith(function(source) return source .. "\n" end)
check("hash block: one newline added at the end prints OK (both)", v.ShopLayout == "OK" and v.ShopClient == "OK")
v = runWith(function(source) return source .. "\n\n" end)
check("hash block: two newlines added is DIFFERENT (both)", v.ShopLayout == "DIFFERENT" and v.ShopClient == "DIFFERENT")
v = runWith(function(source) return "x" .. string.sub(source, 2) end)
check("hash block: one character changed (same size) prints DIFFERENT (both)", v.ShopLayout == "DIFFERENT" and v.ShopClient == "DIFFERENT")
services.ReplicatedStorage = folder({})
local _, _, missing = runBlock()
check("hash block: a ShopLayout not created yet prints MISSING", missing.ShopLayout == "MISSING")
print_real(string.format("%d passed, %d failed", passed, failed))
"""


# docs/STUDIO_SYNC_SHOP.md is history: it was last brought up to date with ShopClient.lua and ShopLayout.lua at
# SYNC_COMMIT (lobby L3, which changed all three), and later Studio steps go to docs/STUDIO_SYNC_BATCH.md. So its table
# and hash block are checked against the two files as they were at that commit (read with git show), never today's
# files: a later edit of ShopClient or ShopLayout never fails this suite (ux backlog item 5, like tools/lobby_test.py).
SYNC_COMMIT = "645393a"
def git_show(rev, path):
    """The bytes of path at rev, or None if git or the commit is missing (a copy without the history, a shallow clone)."""
    try:
        got = subprocess.run(["git", "show", "%s:%s" % (rev, path)], cwd=ROOT, capture_output=True)
    except OSError:
        return None
    return got.stdout if got.returncode == 0 else None


def synced(path):
    """path's text at SYNC_COMMIT, or None."""
    raw = git_show(SYNC_COMMIT, path)
    return raw.decode("utf-8") if raw is not None else None


def hash_source():
    doc = read("docs/STUDIO_SYNC_SHOP.md")
    start = doc.index("```lua\n", doc.index("## (d) Hash check (command bar)")) + len("```lua\n")
    block = doc[start:doc.index("```", start)]
    layout, client = synced(LAYOUT), synced(CLIENT)
    if layout is None or client is None:
        return 'print("FAIL: hash block: ShopLayout.lua and ShopClient.lua at %s can be read (git show)")\nprint("0 passed, 1 failed")\n' % SYNC_COMMIT
    sources = "{ ShopLayout = %s, ShopClient = %s }" % (long_string(layout), long_string(client))
    return HASH_TESTS.replace("__SOURCES__", sources).replace("__HASHBLOCK__", block)


def sync_table_checks():
    """docs/STUDIO_SYNC_SHOP.md's table and hash block give each file's SHA-256 and size at SYNC_COMMIT (Python's hashlib);
    today's files must still use \n line endings."""
    import hashlib
    passed, failed = 0, 0

    def check(name, cond, extra=None):
        nonlocal passed, failed
        if cond:
            passed += 1
        else:
            failed += 1
            print("FAIL: " + name + (" -- " + str(extra) if extra else ""))

    doc = read("docs/STUDIO_SYNC_SHOP.md")
    for name, kind, place, state, where in (("ShopLayout", "ModuleScript", "ReplicatedStorage", "new", "ReplicatedStorage"),
                                            ("ShopClient", "LocalScript", "StarterPlayer > StarterPlayerScripts", "changed", "StarterPlayerScripts")):
        raw = open(os.path.join(ROOT, name + ".lua"), "rb").read()
        old = git_show(SYNC_COMMIT, name + ".lua")
        check("STUDIO_SYNC_SHOP.md: %s.lua at %s can be read (git show; a copy without the git history lacks it)" % (name, SYNC_COMMIT), old is not None)
        old = old or b""
        h = hashlib.sha256(old).hexdigest()
        row = "| `%s` | %s, %s | %s | `%s` | %d |" % (name, kind, place, state, h, len(old))
        check("STUDIO_SYNC_SHOP.md: the table row of %s has its SHA-256 and size at %s" % (name, SYNC_COMMIT), row in doc, "%s %d" % (h, len(old)))
        check("STUDIO_SYNC_SHOP.md: the hash block expects %s's SHA-256 and size at %s" % (name, SYNC_COMMIT), ('%s = { "%s", %d, "%s" },' % (name, h, len(old), where)) in doc)
        check("%s.lua uses \\n line endings and ends with one newline" % name, b"\r" not in raw and raw.endswith(b"\n") and not raw.endswith(b"\n\n"))
    check("STUDIO_SYNC_SHOP.md: ShopLayout is created before ShopClient is pasted",
          doc.index("**Create `ShopLayout`:**") < doc.index("**Paste `ShopClient`:**"))
    return passed, failed


def main():
    luau = os.environ.get("LUAU") or shutil.which("luau")
    if not luau:
        print("Luau not found. Download it from https://github.com/luau-lang/luau/releases and set LUAU=/path/to/luau")
        return 2
    code, total = 0, 0
    result = run_luau(luau, program())
    shown = "\n".join(line for line in result.stdout.split("\n") if not line.startswith("SECTION ")).strip()
    print("Shop layout and the real ShopClient in a fake place: " + (shown or result.stderr.strip()))
    m = re.search(r"^(\d+) passed, (\d+) failed$", result.stdout, re.M)
    if not m or m.group(2) != "0" or result.returncode != 0:
        code = 1
        if result.stderr.strip():
            print(result.stderr.strip())
    total += int(m.group(1)) if m else 0
    static_passed, static_failed = static_checks()
    print("Shop source checks: %d passed, %d failed" % (static_passed, static_failed))
    total += static_passed
    if static_failed:
        code = 1
    result = run_luau(luau, hash_source())
    print("Hash block (docs/STUDIO_SYNC_SHOP.md) on the files at %s: " % SYNC_COMMIT + (result.stdout.strip() or result.stderr.strip()))
    m = re.search(r"^(\d+) passed, (\d+) failed$", result.stdout, re.M)
    if not m or m.group(2) != "0":
        code = 1
    total += int(m.group(1)) if m else 0
    sync_passed, sync_failed = sync_table_checks()
    print("Studio sync table (docs/STUDIO_SYNC_SHOP.md): %d passed, %d failed" % (sync_passed, sync_failed))
    total += sync_passed
    if sync_failed:
        code = 1
    self_caught, self_problems = run_mutants(luau, HARNESS_SELF_TESTS)
    reported = sum(1 for line in self_problems if "failed only next to an uncaught error" in line)
    print("Harness self-test (a named check next to a crash never counts): %d of %d reported as not caught" % (reported, len(HARNESS_SELF_TESTS)))
    if reported != len(HARNESS_SELF_TESTS) or self_caught:
        print("FAIL: the mutation harness counted a mutant that crashed its block as caught")
        code = 1
    else:
        total += reported
    caught, problems = run_mutants(luau)
    for line in problems:
        print(line)
    if problems:
        code = 1
    print("Shop mutations: %d of %d caught, each by its named check" % (caught, len(MUTANTS)))
    print("shop_ux_test.py: %d checks passed, %d of %d mutation runs caught%s" % (total, caught, len(MUTANTS), "" if code == 0 else "  -- SOMETHING FAILED"))
    return code


if __name__ == "__main__":
    sys.exit(main())
