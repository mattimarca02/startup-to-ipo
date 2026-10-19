#!/usr/bin/env python3
"""Tests for the valuation bar's Cash and Income row (IpoClient.lua), outside Studio.

Run:   python3 tools/hud_test.py
       python3 tools/hud_test.py --no-mutations   (skip the mutation runs)
       python3 tools/hud_test.py --layout-table   (also print, for each size, what the bar touches)

It needs the free Luau command-line tool (https://github.com/luau-lang/luau/releases, the "luau" file from
luau-macos.zip, luau-windows.zip or luau-ubuntu.zip). Put it on your PATH, or point to it:
       LUAU=/path/to/luau python3 tools/hud_test.py

It runs the REAL IpoClient.lua (the whole script, up to its last loop) with a fake Roblox: Instances with parents,
properties, signals and layout (position, size, anchor), a virtual clock that runs task.spawn, task.delay and
task.wait, a leaderstats folder the test fills, and a text measure. It checks the three rows of the bar (Cash and
Income, the progress bar, the stage and the valuation) for many values, their rectangles at five screen sizes with
three top bars each, that nothing overlaps, that the text fits at the narrowest bar, that the rows update on Changed
events and no faster than the minimum interval, that a missing or late leaderstats is safe, that nothing is polled,
and that the progress bar is what it was. Then it breaks IpoClient.lua on purpose (mutation runs): each break must
be caught by a named check, never by a crash.

The fake's text WIDTHS are an estimate (a safe, wide one: digits 0.68 em, capitals 0.74 em, emoji 1.4 em). The
real client asks TextService for the real width, so on the real font it picks by real measurements; only what the
test sees depends on the estimate. Studio is the only way to see the real font (docs/STUDIO_SYNC_HUD.md).

It also runs the REAL ClaimButtonClient.lua (the ux lane's "Claim garage" button for phones) in a fake client
(tools/claim_button_test.luau): what it shows for which prompt (the nearest when two show), the tap that presses the server's own
prompt, its place at seven screen sizes with three top bars, then its own mutation runs.

And it runs the REAL OnboardingClient.lua's Goals card in a fake client (tools/onboarding_client_test.luau): with
ChainEnabled off and on, it draws only the goals the server marks as shown, in list order, in ShowAtOnce rows at most;
then its own mutation runs.

And it runs the REAL hatch reveal block of EmployeeClient.lua (HATCHPANEL, tools/hatch_reveal_test.luau): while the
reveal plays it holds the PlayerGui attribute "OpenPanel" as "Hatch" (so the calls freeze), never takes it from an open
window and gives it back only if it still says "Hatch"; then its own mutation runs.

And it checks every TextButton and ImageButton the clients make with a fixed size in pixels: 40 or more on each side.

It changes nothing in the game or in Studio. It never edits tools/daily_test.py.
"""

import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLIENT = "IpoClient.lua"


def read(name):
    with open(os.path.join(ROOT, name), encoding="utf-8") as f:
        return f.read()


def marked_source(name, filename):
    text = read(filename)
    start = text.index("-- %s-START" % name) + len("-- %s-START" % name)
    return text[start:text.index("-- %s-END" % name)]


def onboarding_goal_count():
    """How many goal rows the Goals card has: math.min(OnboardingConfig.ShowAtOnce, #activeGoals()), the way
    OnboardingClient sizes it (30 + 22 per row + 8 high). activeGoals() is Chain with ChainEnabled on, else Goals."""
    text = read("OnboardingConfig.lua")
    chain = re.search(r"^OnboardingConfig\.ChainEnabled = (true|false)\b", text, re.M).group(1) == "true"
    block = text[text.index("OnboardingConfig.Chain = {" if chain else "OnboardingConfig.Goals = {"):]
    block = block[:block.index("\n}")]
    at_once = int(re.search(r"^OnboardingConfig\.ShowAtOnce = (\d+)\b", text, re.M).group(1))
    return min(at_once, len(re.findall(r"\{\s*key = ", block)))


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


PRELUDE = r"""-- Fake Roblox for the valuation bar: Instances with parents, properties, signals and layout; a virtual clock with
-- task.spawn / delay / defer / wait; services; a text measure. Everything is a local (the Luau CLI's globals are read-only).
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
local W -- the state of the world being tested (newWorld)
local STOP = "__STOP__"
local function warn(...)
	if W then
		local parts = {}
		for i = 1, select("#", ...) do parts[i] = tostring((select(i, ...))) end
		table.insert(W.warns, table.concat(parts, " "))
	end
end
local function print() end

local Vector2 = { new = function(x, y) return { X = x or 0, Y = y or 0 } end }
local UDim = { new = function(s, o) return { Scale = s or 0, Offset = o or 0 } end }
local UDim2 = {
	new = function(xs, xo, ys, yo) return { X = UDim.new(xs, xo), Y = UDim.new(ys, yo) } end,
	fromOffset = function(x, y) return { X = UDim.new(0, x), Y = UDim.new(0, y) } end,
	fromScale = function(x, y) return { X = UDim.new(x, 0), Y = UDim.new(y, 0) } end,
}
local Color3 = {
	fromRGB = function(r, g, b) return { R = r / 255, G = g / 255, B = b / 255 } end,
	new = function(r, g, b) return { R = r, G = g, B = b } end,
}
local TweenInfo = { new = function(...) return { ... } end }
local function enumType(names)
	local t = {}
	for _, n in ipairs(names) do t[n] = { Name = n } end
	return setmetatable(t, { __index = function(_, k) error("not a valid enum item: " .. tostring(k)) end })
end
local Enum = {
	ApplyStrokeMode = enumType({ "Border", "Contextual" }),
	AutomaticSize = enumType({ "None", "X", "Y", "XY" }),
	EasingDirection = enumType({ "In", "Out", "InOut" }),
	EasingStyle = enumType({ "Linear", "Sine", "Quad" }),
	FillDirection = enumType({ "Horizontal", "Vertical" }),
	Font = enumType({ "Gotham", "GothamBold", "GothamBlack", "FredokaOne" }),
	ScrollingDirection = enumType({ "X", "Y", "XY" }),
	SortOrder = enumType({ "LayoutOrder", "Name" }),
	TextTruncate = enumType({ "None", "AtEnd" }),
	TextXAlignment = enumType({ "Left", "Center", "Right" }),
	TextYAlignment = enumType({ "Top", "Center", "Bottom" }),
	ZIndexBehavior = enumType({ "Sibling", "Global" }),
}

-- Signals ---------------------------------------------------------------------------------------------------------
local Signal = {}
Signal.__index = Signal
local function newSignal() return setmetatable({ conns = {} }, Signal) end
function Signal:Connect(fn)
	local conn = { fn = fn, Connected = true }
	function conn:Disconnect() self.Connected = false end
	table.insert(self.conns, conn)
	return conn
end
function Signal:Fire(...)
	for _, c in ipairs(table.clone(self.conns)) do
		if c.Connected then
			local ok, err = pcall(c.fn, ...)
			if not ok then table.insert(W.errors, tostring(err)) end
		end
	end
	local waiting = self.waiting or {}
	self.waiting = {}
	for _, thread in ipairs(waiting) do
		local ok, err = coroutine.resume(thread, ...)
		if not ok and not tostring(err):find(STOP, 1, true) then table.insert(W.errors, tostring(err)) end
	end
end
-- Wait: the running task stops until the next Fire (lobby L3: IpoClient waits for leaderstats with ChildAdded:Wait)
function Signal:Wait()
	if not coroutine.isyieldable() then error(STOP) end
	self.waiting = self.waiting or {}
	table.insert(self.waiting, coroutine.running())
	return coroutine.yield()
end
function Signal:Count()
	local n = 0
	for _, c in ipairs(self.conns) do if c.Connected then n += 1 end end
	return n
end

-- Virtual clock and tasks -----------------------------------------------------------------------------------------
local function schedule(delay, thread)
	W.seq += 1
	table.insert(W.queue, { t = W.clock + delay, seq = W.seq, thread = thread })
end
local function resume(thread, ...)
	local ok, err = coroutine.resume(thread, ...)
	if not ok and not tostring(err):find(STOP, 1, true) then table.insert(W.errors, tostring(err)) end
end
local function advance(dt)
	local target = W.clock + dt
	local guard = 0
	while true do
		local best, bi
		for i, item in ipairs(W.queue) do
			if item.t <= target and (not best or item.t < best.t or (item.t == best.t and item.seq < best.seq)) then best, bi = item, i end
		end
		if not best then break end
		guard += 1
		if guard > 20000 then table.insert(W.errors, "the virtual clock ran away (a loop without a wait)") break end
		table.remove(W.queue, bi)
		if best.t > W.clock then W.clock = best.t end
		resume(best.thread)
	end
	W.clock = target
end
local os = { clock = function() return W.clock end, time = function() return 1700000000 + math.floor(W.clock) end, date = os.date }
local task = {
	spawn = function(fn, ...)
		local co = coroutine.create(fn)
		resume(co, ...)
		return co
	end,
	delay = function(t, fn)
		table.insert(W.delays, t)
		local co = coroutine.create(fn)
		schedule(t, co)
		return co
	end,
	cancel = function(co)
		for i = #W.queue, 1, -1 do
			if W.queue[i].thread == co then
				table.remove(W.queue, i)
				W.cancelled += 1
			end
		end
	end,
	defer = function(fn) schedule(0, coroutine.create(fn)) end,
	wait = function(t)
		t = t or 0
		table.insert(W.waits, { t = t, at = W.clock })
		if not coroutine.isyieldable() then error(STOP) end
		schedule(t, coroutine.running())
		coroutine.yield()
		return t
	end,
}

-- Instances -------------------------------------------------------------------------------------------------------
local CLASSES = {}
for _, c in ipairs({ "Folder", "PlayerGui", "ScreenGui", "Frame", "TextLabel", "TextButton", "TextBox", "ScrollingFrame", "ImageLabel",
	"UICorner", "UIStroke", "UIPadding", "UIListLayout", "UISizeConstraint", "UITextSizeConstraint", "UIGradient", "UIAspectRatioConstraint",
	"IntValue", "NumberValue", "StringValue", "BoolValue", "Player", "ModuleScript", "RemoteEvent", "RemoteFunction" }) do CLASSES[c] = true end
local VALUE = { IntValue = true, NumberValue = true, StringValue = true, BoolValue = true }
local GUI = { Frame = true, TextLabel = true, TextButton = true, TextBox = true, ScrollingFrame = true, ImageLabel = true }
local SIGNALS = { Changed = true, ChildAdded = true, ChildRemoved = true, Activated = true, OnClientEvent = true,
	AttributeChanged = true, Destroying = true, MouseButton1Click = true, OnServerEvent = true }
local ZERO2 = UDim2.new(0, 0, 0, 0)
local DEFAULTS = { Visible = true, Text = "", TextSize = 14, Position = ZERO2, Size = ZERO2, AnchorPoint = Vector2.new(0, 0), TextScaled = false }
local Inst = {}
local MT = {}
local absSize, absPos

local function newInstance(class)
	assert(CLASSES[class], "fake Roblox: unknown class " .. tostring(class))
	local self = setmetatable({ _class = class, _p = { Name = class }, _kids = {}, _sig = {}, _attrs = {}, _writes = {}, _parent = false }, MT)
	if class == "IntValue" or class == "NumberValue" then self._p.Value = 0
	elseif class == "StringValue" then self._p.Value = ""
	elseif class == "BoolValue" then self._p.Value = false end
	table.insert(W.all, self)
	return self
end

absSize = function(inst)
	if inst._class == "ScreenGui" then return W.screen end
	local parent = inst._parent
	if not parent or not GUI[inst._class] then return Vector2.new(0, 0) end
	local ps = absSize(parent)
	local s = inst._p.Size or ZERO2
	return Vector2.new(s.X.Scale * ps.X + s.X.Offset, s.Y.Scale * ps.Y + s.Y.Offset)
end
absPos = function(inst)
	if inst._class == "ScreenGui" then return Vector2.new(0, 0) end
	local parent = inst._parent
	if not parent or not GUI[inst._class] then return Vector2.new(0, 0) end
	local pp, ps, size = absPos(parent), absSize(parent), absSize(inst)
	local pos, anchor = inst._p.Position or ZERO2, inst._p.AnchorPoint or DEFAULTS.AnchorPoint
	return Vector2.new(pp.X + pos.X.Scale * ps.X + pos.X.Offset - anchor.X * size.X, pp.Y + pos.Y.Scale * ps.Y + pos.Y.Offset - anchor.Y * size.Y)
end

MT.__index = function(self, k)
	local m = Inst[k]
	if m ~= nil then return m end
	if k == "ClassName" then return rawget(self, "_class") end
	if k == "Parent" then return rawget(self, "_parent") or nil end
	if SIGNALS[k] then return Inst._signal(self, k) end
	if k == "AbsoluteSize" then return absSize(self) end
	if k == "AbsolutePosition" then return absPos(self) end
	local v = rawget(self, "_p")[k]
	if v ~= nil then return v end
	return DEFAULTS[k]
end
MT.__newindex = function(self, k, v)
	if type(k) == "string" and k:sub(1, 1) == "_" then rawset(self, k, v) return end
	if k == "Parent" then Inst._setParent(self, v) return end
	if k == "Text" and type(v) ~= "string" then error("unable to assign property Text. string expected, got " .. typeof(v)) end
	if k == "TextSize" and type(v) ~= "number" then error("unable to assign property TextSize. number expected, got " .. typeof(v)) end
	if (k == "Position" or k == "Size") and (type(v) ~= "table" or v.X == nil or v.Y == nil) then error("unable to assign property " .. k .. ". UDim2 expected") end
	self._p[k] = v
	self._writes[k] = (self._writes[k] or 0) + 1
	local pc = self._sig["pc:" .. k]
	if pc then pc:Fire() end
	if k == "Value" and VALUE[self._class] then
		local s = self._sig.Changed
		if s then s:Fire(v) end
	end
end
function Inst._signal(self, name)
	local s = self._sig[name]
	if not s then s = newSignal() self._sig[name] = s end
	return s
end
function Inst._setParent(self, p)
	local old = self._parent
	if old == (p or false) then return end
	if old then
		for i, kid in ipairs(old._kids) do if kid == self then table.remove(old._kids, i) break end end
	end
	self._parent = p or false
	if old and old._sig.ChildRemoved then old._sig.ChildRemoved:Fire(self) end
	if p then
		table.insert(p._kids, self)
		if p._sig.ChildAdded then p._sig.ChildAdded:Fire(self) end
	end
end
function Inst:FindFirstChild(name)
	for _, kid in ipairs(self._kids) do if kid._p.Name == name then return kid end end
	return nil
end
function Inst:WaitForChild(name)
	local kid = self:FindFirstChild(name)
	if kid then return kid end
	if not coroutine.isyieldable() then return nil end
	local co = coroutine.running()
	local done = false
	local conn
	conn = self:_signal("ChildAdded"):Connect(function(child)
		if child._p.Name == name and not done then
			done = true
			conn:Disconnect()
			schedule(0, co)
		end
	end)
	coroutine.yield()
	return self:FindFirstChild(name)
end
function Inst:GetChildren() return table.clone(self._kids) end
function Inst:GetDescendants()
	local list = {}
	local function walk(node) for _, kid in ipairs(node._kids) do table.insert(list, kid) walk(kid) end end
	walk(self)
	return list
end
function Inst:IsA(class)
	if class == self._class or class == "Instance" then return true end
	if class == "ValueBase" then return VALUE[self._class] == true end
	if class == "GuiObject" then return GUI[self._class] == true end
	if class == "GuiButton" then return self._class == "TextButton" end
	if class == "GuiBase2d" then return GUI[self._class] == true or self._class == "ScreenGui" end
	return false
end
function Inst:GetAttribute(name) return self._attrs[name] end
function Inst:SetAttribute(name, value)
	if self._attrs[name] == value then return end
	self._attrs[name] = value
	local s = self._sig["attr:" .. name]
	if s then s:Fire() end
	local all = self._sig.AttributeChanged
	if all then all:Fire(name) end
end
function Inst:GetAttributeChangedSignal(name) return self:_signal("attr:" .. name) end
function Inst:GetPropertyChangedSignal(name) return self:_signal("pc:" .. name) end
function Inst:Destroy() self.Parent = nil end
function Inst:ClearAllChildren() for _, kid in ipairs(table.clone(self._kids)) do kid:Destroy() end end
function Inst:InvokeServer(...) table.insert(W.invokes, { ... }) return nil end
function Inst:FireServer(...) table.insert(W.invokes, { ... }) end
local Instance = { new = newInstance }

-- Text measure: a wide estimate of Gotham Bold (em per character). The real client measures the real font.
local function charEm(cp)
	if cp >= 0x30 and cp <= 0x39 then return 0.68 end
	if cp >= 0x41 and cp <= 0x5A then return 0.74 end
	if cp >= 0x61 and cp <= 0x7A then return 0.62 end
	if cp == 0x20 then return 0.30 end
	if cp == 0x2C or cp == 0x2E or cp == 0xB7 or cp == 0x21 then return 0.32 end
	if cp == 0x2F then return 0.42 end
	if cp == 0x24 or cp == 0x2B then return 0.68 end
	if cp == 0x2D then return 0.45 end
	if cp == 0x2192 then return 1.0 end
	if cp == 0xFE0F or cp == 0x200D then return 0 end
	if cp >= 0x1F000 or (cp >= 0x2600 and cp <= 0x27BF) then return 1.4 end
	return 0.7
end
local function modelWidth(text, size)
	local em = 0
	for _, cp in utf8.codes(text) do em += charEm(cp) end
	return em * size
end

-- Services and globals --------------------------------------------------------------------------------------------
local TextService = { GetTextSize = function(_, text, size, font, frame)
	W.measures += 1
	return Vector2.new(modelWidth(text, size) * W.widthScale, size)
end }
local GuiService = { TouchControlsEnabled = true }
local TweenService = { Create = function(_, inst, info, goals) return { Play = function() end, Cancel = function() end } end }
local Players = setmetatable({}, { __index = function(_, k)
	if k == "LocalPlayer" then return W.player end
	if k == "GetPlayers" then return function() return { W.player } end end
	if k == "PlayerAdded" then return W.playerAdded end
	if k == "PlayerRemoving" then return W.playerRemoving end
	return nil
end })
local ALLOWED_SERVICES = { Players = true, ReplicatedStorage = true, GuiService = true, TweenService = true, TextService = true }
local game = { GetService = function(_, name)
	W.services[name] = true
	if name == "Players" then return Players end
	if name == "ReplicatedStorage" then return W.rs end
	if name == "GuiService" then return GuiService end
	if name == "TweenService" then return TweenService end
	if name == "TextService" then return TextService end
	if name == "RunService" then return W.run end
	error("fake Roblox: unknown service " .. tostring(name))
end }
local workspace = { GetServerTimeNow = function() return 1700000000 + W.clock end }
local script = { Parent = { WaitForChild = function() return nil end } }
local MODULES = {}
local function require(inst) return assert(MODULES[inst._p.Name], "no module " .. tostring(inst._p.Name)) end

MODULES.IpoConfig = (function()
__IPOCONFIG__
end)()
MODULES.ShopConfig = (function()
__SHOPCONFIG__
end)()
MODULES.DailyConfig = (function()
__DAILYCONFIG__
end)()
local IpoConfig, ShopConfig, DailyConfig = MODULES.IpoConfig, MODULES.ShopConfig, MODULES.DailyConfig

local function RUN_IPOCLIENT()
__IPOCLIENT__
end

-- The real tray layout (TaskClient.lua, between its TRAY markers)
__TRAY__
"""

SCENARIOS = r"""
-- Worlds --------------------------------------------------------------------------------------------------------
local function newWorld(opts)
	opts = opts or {}
	W = { clock = 5000, seq = 0, queue = {}, waits = {}, delays = {}, errors = {}, warns = {}, invokes = {}, all = {}, services = {}, cancelled = 0,
		screen = Vector2.new(opts.w or 667, opts.h or 339), widthScale = opts.widthScale or 1, measures = 0 }
	W.run = { Heartbeat = newSignal(), RenderStepped = newSignal(), Stepped = newSignal() }
	W.playerAdded, W.playerRemoving = newSignal(), newSignal()
	W.player = newInstance("Player")
	W.player.Name = "Tester"
	W.playerGui = newInstance("PlayerGui")
	W.playerGui.Name = "PlayerGui"
	W.playerGui.Parent = W.player
	W.rs = newInstance("Folder")
	for name in pairs(MODULES) do
		local m = newInstance("ModuleScript")
		m.Name = name
		m.Parent = W.rs
	end
	local remotes = newInstance("Folder")
	remotes.Name = "IpoRemotes"
	remotes.Parent = W.rs
	W.ipoAction = newInstance("RemoteFunction")
	W.ipoAction.Name = "IpoAction"
	W.ipoAction.Parent = remotes
	W.ipoEvent = newInstance("RemoteEvent")
	W.ipoEvent.Name = "IpoEvent"
	W.ipoEvent.Parent = remotes
	-- TycoonCore sets Upgrade1..6 (true or false) when a player's save is loaded; opts.loading = true leaves it unset
	if not opts.loading then W.player:SetAttribute("Upgrade1", false) end
	for k, v in pairs(opts.attrs or {}) do W.player:SetAttribute(k, v) end
	return W
end

-- leaderstats like the server makes it (TycoonCore onPlayerAdded): a folder with Cash and Income (IntValues)
local function makeStats(cash, income, parentFirst)
	local folder = newInstance("Folder")
	folder.Name = "leaderstats"
	local c = newInstance("IntValue")
	c.Name = "Cash"
	local i = newInstance("IntValue")
	i.Name = "Income"
	if parentFirst then folder.Parent = W.player end
	if cash ~= nil then c.Value = cash end
	if income ~= nil then i.Value = income end
	c.Parent = folder
	i.Parent = folder
	if not parentFirst then folder.Parent = W.player end
	return folder, c, i
end

local function sortedByY(list)
	table.sort(list, function(a, b) return a._p.Position.Y.Offset < b._p.Position.Y.Offset end)
	return list
end
local function find()
	local E = { W = W }
	E.gui = W.playerGui:FindFirstChild("IpoGui")
	E.front = W.playerGui:FindFirstChild("IpoWindowGui")
	E.bar = E.gui and E.gui:FindFirstChild("ValuationBar")
	E.button = E.gui and E.gui:FindFirstChild("IpoButton")
	if E.bar then
		local labels, frames = {}, {}
		for _, kid in ipairs(E.bar:GetChildren()) do
			if kid._class == "TextLabel" then table.insert(labels, kid) end
			if kid._class == "Frame" then table.insert(frames, kid) end
		end
		sortedByY(labels)
		E.money, E.info = labels[1], labels[#labels]
		E.labels = labels
		E.track = frames[1]
		E.fill = E.track and E.track:GetChildren()[1]
		for _, kid in ipairs(E.track and E.track:GetChildren() or {}) do if kid._class == "Frame" then E.fill = kid end end
	end
	return E
end
-- Runs IpoClient.lua as the game does (a script that ends in its 1 s loop)
local function boot(opts)
	opts = opts or {}
	newWorld(opts)
	if opts.stats then makeStats(opts.stats[1], opts.stats[2], opts.parentFirst) end
	W.client = task.spawn(RUN_IPOCLIENT)
	advance(0)
	return find()
end
local function setScreen(w, h)
	W.screen = Vector2.new(w, h)
	for _, inst in ipairs(W.all) do
		if inst._class == "ScreenGui" and inst._sig["pc:AbsoluteSize"] then inst._sig["pc:AbsoluteSize"]:Fire() end
	end
	advance(0)
end

local function scenario(name, fn)
	local ok, err = pcall(fn)
	if not ok then check(name .. ": the test ran to its end (it stopped: " .. tostring(err) .. ")", false) end
end
local function noErrors(label)
	check(label .. ": no error in the script, its events or its tasks", #W.errors == 0, W.errors[1])
end

local function R(x, y, w, h) return { x = x, y = y, w = w, h = h } end
local function rectOf(inst) local p, s = inst.AbsolutePosition, inst.AbsoluteSize return R(p.X, p.Y, s.X, s.Y) end
local function overlaps(a, b) return a.x < b.x + b.w and b.x < a.x + a.w and a.y < b.y + b.h and b.y < a.y + a.h end
local function inside(a, b) return a.x >= b.x and a.y >= b.y and a.x + a.w <= b.x + b.w and a.y + a.h <= b.y + b.h end
local function has(text, part) return string.find(text, part, 1, true) ~= nil end
local function first(texts, size, room)
	for _, text in ipairs(texts) do
		if modelWidth(text, size) <= room then return text end
	end
	return texts[#texts]
end
local NAN = 0 / 0

-- 0. The script runs as the game runs it ---------------------------------------------------------------------------
scenario("start", function()
	local E = boot({ stats = { 4630, 18 } })
	noErrors("start")
	check("start: the script reaches its last loop and waits 1 s there (the cooldown tick), nothing else waits", #W.waits == 1 and W.waits[1].t == 1, #W.waits)
	check("start: the bar, its three rows and the IPO button exist", E.bar ~= nil and E.money ~= nil and E.track ~= nil and E.fill ~= nil and E.info ~= nil and E.button ~= nil and E.money ~= E.info)
	check("start: the bar is a button 233 x 64 at x 370, y 6 on a 667x339 screen (unchanged)", E.bar.Size.X.Offset == 233 and E.bar.Size.Y.Offset == 64 and E.bar.Position.X.Offset == 370 and E.bar.Position.Y.Offset == 6, E.bar.Size.X.Offset)
	check("start: the bar keeps its name, the daily chip and the Goals card look it up by name", E.bar.Name == "ValuationBar" and E.bar.Parent == E.gui and E.gui.Name == "IpoGui")
	local used = {}
	for name in pairs(W.services) do used[#used + 1] = name end
	table.sort(used)
	local extra = {}
	for _, name in ipairs(used) do if not ALLOWED_SERVICES[name] then extra[#extra + 1] = name end end
	check("start: only the services it used before are used (no RunService, no frame loop)", #extra == 0, table.concat(extra, ","))
	check("start: nothing listens to a frame event", W.run.Heartbeat:Count() == 0 and W.run.RenderStepped:Count() == 0 and W.run.Stepped:Count() == 0)
	check("start: no remote is called at start (no new request)", #W.invokes == 0, #W.invokes)
	check("start: the top row shows the Cash and Income at once", E.money.Text == "$4,630 · +$18/s", E.money.Text)
	advance(5)
	local stats = W.player:FindFirstChild("leaderstats")
	check("start: the bar only reads leaderstats, it never writes Cash or Income", stats:FindFirstChild("Cash")._writes.Value == 1 and stats:FindFirstChild("Income")._writes.Value == 1, stats:FindFirstChild("Cash")._writes.Value)
end)

-- 1. Cash and Income text for many values --------------------------------------------------------------------------
-- wide = the bar at 667x339 (233 px, rows 213 px); narrow = the bar at 320x568 (158 px, rows 138 px)
local VALUES = {
	-- cash, income, the text on a wide bar
	{ 0, 0, "$0 · +$0/s" },
	{ 1, 1, "$1 · +$1/s" },
	{ 999, 999, "$999 · +$999/s" },
	{ 1000, 1000, "$1,000 · +$1,000/s" },
	{ 4630, 18, "$4,630 · +$18/s" },
	{ 12345, 678, "$12,345 · +$678/s" },
	{ 99999, 9999, "$99,999 · +$9,999/s" },
	{ 100000, 10000, "$100K · +$10K/s" },
	{ 123456, 12345, "$123.5K · +$12.3K/s" },
	{ 1500000, 45000, "$1.5M · +$45K/s" },
	{ 999999, 99999, "$1M · +$100K/s" },
	{ 1e9, 5e6, "$1B · +$5M/s" },
	{ 1.5e12, 2e9, "$1.5T · +$2B/s" },
	{ 1e12, 1e12, "$1T · +$1T/s" },
	{ 1e15, 1e15, "$999T · +$999T/s" },
	{ 1e18, 1e18, "$999T · +$999T/s" },
	{ math.huge, math.huge, "$999T · +$999T/s" },
	{ -5, -5, "$0 · +$0/s" },
	{ -math.huge, 18, "$0 · +$18/s" },
	{ 4630.9, 18.7, "$4,630 · +$18/s" },
	{ NAN, NAN, "" },
	{ NAN, 18, "+$18/s" },
	{ 4630, NAN, "$4,630" },
}
local function label(v) return (v ~= v) and "NaN" or tostring(v) end
local function shownOk(text)
	local plain = text:gsub("·", "")
	return string.find(plain, "^[%$%+%d,%.KMBT/s ]*$") ~= nil
end
for _, case in ipairs(VALUES) do
	local cash, income, want = case[1], case[2], case[3]
	scenario("values " .. label(cash) .. "/" .. label(income), function()
		local name = "Cash " .. label(cash) .. " Income " .. label(income)
		local E = boot({ w = 667, h = 339, stats = { cash, income } })
		check("wide bar, " .. name .. ": the top row reads " .. want, E.money.Text == want, E.money.Text)
		check("wide bar, " .. name .. ": nothing but digits, $ + , . K M B T / s and the dot", shownOk(E.money.Text), E.money.Text)
		check("wide bar, " .. name .. ": no nil, nan, inf or minus sign in the text", not has(E.money.Text:lower(), "nil") and not has(E.money.Text:lower(), "nan") and not has(E.money.Text:lower(), "inf") and not has(E.money.Text, "-") and not has(E.money.Text, "e+"), E.money.Text)
		noErrors("wide bar, " .. name)
		for _, size in ipairs({ { 667, 339 }, { 320, 568 }, { 568, 262 }, { 844, 354 } }) do
			local E2 = boot({ w = size[1], h = size[2], stats = { cash, income } })
			local room = E2.bar.Size.X.Offset - 20
			local text = E2.money.Text
			local tag = size[1] .. "x" .. size[2] .. " (" .. room .. " px), " .. name
			check(tag .. ": the top row text fits its row", modelWidth(text, E2.money.TextSize) <= room, modelWidth(text, E2.money.TextSize))
			check(tag .. ": the top row text is 14 or 16 px", E2.money.TextSize == 14 or E2.money.TextSize == 16, E2.money.TextSize)
			check(tag .. ": only digits and the money letters", shownOk(text), text)
			check(tag .. ": empty only when there is nothing to show", (text == "") == (want == ""), text)
			noErrors(tag)
		end
	end)
end

-- 1b. Rounding: every form rounds to the nearest, and nothing says $1000K -----------------------------------------------
-- The shortest form used to round down ("$99K" for 99,999 while the others said "$100K"), and IpoConfig.formatShort
-- turns 999,950 to 999,999 into "$1000K" (IpoConfig is not changed: the bar guards it).
scenario("rounding", function()
	local UNIT = { K = 1e3, M = 1e6, B = 1e9, T = 1e12 }
	-- "$123.5K" -> 123500, 123.5 (the digits), "K"; a plain "$4,630" -> 4630
	local function parse(token)
		local plain = token:gsub("^%+", ""):gsub("/s$", "")
		local digits, unit = plain:match("^%$([%d%.]+)([KMBT])$")
		if digits then return tonumber(digits) * UNIT[unit], digits, unit end
		local exact = plain:match("^%$([%d,]+)$")
		return exact and tonumber((exact:gsub(",", ""))) or nil
	end
	local AMOUNTS = { 999, 1000, 1049, 1050, 1500, 4630, 9950, 9999, 10000, 12345, 99949, 99950, 99999, 100000, 123456, 949999, 999949, 999950,
		999999, 1000000, 1499999, 1500000, 9999999, 99999999, 999949999, 999950000, 999999999, 1e9, 999949999999, 999950000000, 999999999999, 1e12, 999e12 }
	local bad, shown = {}, 0
	for _, amount in ipairs(AMOUNTS) do
		for _, scale in ipairs({ 0.01, 0.6, 0.8, 1, 1.2, 1.5, 2, 3, 10 }) do
			local E = boot({ widthScale = scale, stats = { amount, amount } })
			local text = E.money.Text
			shown += 1
			for token in text:gmatch("%S+") do
				if token ~= "·" then
					local value, digits, unit = parse(token)
					local tol = 0
					if unit then tol = (digits:find(".", 1, true) and 0.05 or 0.5) * UNIT[unit] end
					if value == nil or math.abs(value - amount) > tol + 1e-6 or (unit and tonumber(digits) >= 1000) or (unit == nil and value ~= amount) then
						bad[#bad + 1] = amount .. " at scale " .. scale .. ": " .. text
					end
				end
			end
		end
	end
	check("rounding: " .. shown .. " texts (33 amounts, 9 font widths, all three forms): every number is within half a step of the amount, none says 1000 of a unit (" .. (bad[1] or "ok") .. ")", #bad == 0, bad[1])
	-- the shortest form (a font ten times wider than the estimate forces it): whole numbers, to the nearest
	local WHOLE = { { 999, "$999" }, { 1000, "$1K" }, { 1499, "$1K" }, { 1500, "$2K" }, { 4630, "$5K" }, { 99999, "$100K" }, { 100000, "$100K" }, { 123456, "$123K" },
		{ 999499, "$999K" }, { 999500, "$1M" }, { 999999, "$1M" }, { 1499999, "$1M" }, { 1500000, "$2M" }, { 999499999, "$999M" }, { 999500000, "$1B" },
		{ 999999999, "$1B" }, { 999499999999, "$999B" }, { 999500000000, "$1T" }, { 999e12, "$999T" }, { 1e18, "$999T" } }
	for _, case in ipairs(WHOLE) do
		local E = boot({ widthScale = 10, stats = { case[1], case[1] } })
		check("rounding, shortest form: " .. case[1] .. " is " .. case[2], E.money.Text == case[2] .. " +" .. case[2], E.money.Text)
	end
	local ninetyNine = boot({ widthScale = 10, stats = { 99999, 99999 } })
	local roomy = boot({ widthScale = 0.01, stats = { 123456, 99999 } })
	check("rounding: 99,999 is $100K in the shortest form and in the full form", ninetyNine.money.Text == "$100K +$100K" and roomy.money.Text == "$123.5K · +$100K/s", ninetyNine.money.Text .. " / " .. roomy.money.Text)
	-- IpoConfig.formatShort's $1000K, guarded in the bar (the full form, with room)
	local GUARD = { { 999949, "$999.9K" }, { 999950, "$1M" }, { 999999, "$1M" }, { 999949999, "$999.9M" }, { 999950000, "$1B" }, { 999999999, "$1B" }, { 999950000000, "$1T" }, { 999999999999, "$1T" } }
	for _, case in ipairs(GUARD) do
		local E = boot({ widthScale = 0.01, stats = { case[1], case[1] } })
		check("rounding, the bar's own guard: " .. case[1] .. " is " .. case[2] .. " (never $1000 of a unit)", E.money.Text == case[2] .. " · +" .. case[2] .. "/s", E.money.Text)
	end
	check("rounding: IpoConfig.formatShort still has the $1000K the bar guards against (so the guard is needed, IpoConfig is not changed)", IpoConfig.formatShort(999960) == "$1000K", IpoConfig.formatShort(999960))
	-- the bottom row says the valuation the same way
	local seen, thousand = {}, nil
	for _, scale in ipairs({ 0.2, 0.3, 0.5, 0.7, 0.8, 0.9, 1, 1.2 }) do
		local E = boot({ widthScale = scale, attrs = { IpoValuation = 999960, IpoCount = 0 }, stats = { 5, 5 } })
		seen[E.info.Text] = true
		if has(E.info.Text, "1000") then thousand = E.info.Text end
	end
	local has1M = false
	for text in pairs(seen) do if has(text, "· $1M") then has1M = true end end
	check("rounding: the bottom row never says $1000K for a valuation of 999,960 (and says $1M in at least one form)", thousand == nil and has1M, thousand)
end)

-- The narrowest bar: the fullest text that fits, checked against the estimate
scenario("narrow", function()
	local cases = {
		-- cash, income, the three forms of the text, fullest first (the bar shows the first that fits, at 16 px, then 14)
		{ 4630, 18, { "$4,630 · +$18/s", "$4.6K · +$18/s", "$5K +$18" } },
		{ 123456, 12345, { "$123.5K · +$12.3K/s", "$123.5K · +$12.3K/s", "$123K +$12K" } },
		{ 99999, 9999, { "$99,999 · +$9,999/s", "$100K · +$10K/s", "$100K +$10K" } },
		{ 1e15, 1e15, { "$999T · +$999T/s", "$999T · +$999T/s", "$999T +$999T" } },
	}
	for _, c in ipairs(cases) do
		local E = boot({ w = 320, h = 568, stats = { c[1], c[2] } })
		local room = 138
		check("narrow bar is 158 px wide on 320x568", E.bar.Size.X.Offset == 158, E.bar.Size.X.Offset)
		local want
		for _, text in ipairs(c[3]) do
			if want == nil and modelWidth(text, 16) <= room then want = { text, 16 } end
			if want == nil and modelWidth(text, 14) <= room then want = { text, 14 } end
		end
		want = want or { c[3][#c[3]], 14 }
		check("narrow bar, Cash " .. c[1] .. " Income " .. c[2] .. ": the fullest text that fits, at the biggest size that fits (" .. want[1] .. " at " .. want[2] .. ")",
			E.money.Text == want[1] and E.money.TextSize == want[2], E.money.Text .. " at " .. E.money.TextSize)
	end
	local E = boot({ w = 320, h = 568, stats = { 4630, 18 } })
	check("narrow bar: '$4,630 · +$18/s' is shown whole at 16 px (the doc's example)", E.money.Text == "$4,630 · +$18/s" and E.money.TextSize == 16, E.money.Text .. " " .. E.money.TextSize)
	-- A wider font than the estimate: the bar measures, so it still fits
	for _, scale in ipairs({ 1.15, 1.3 }) do
		local E2 = boot({ w = 320, h = 568, stats = { 123456, 12345 }, widthScale = scale })
		check("narrow bar with a font " .. scale .. "x wider than the estimate: the top row still fits (the bar measures)", modelWidth(E2.money.Text, E2.money.TextSize) * scale <= 138 or E2.money.Text == "$123K +$12K", E2.money.Text)
	end
end)

-- 2. Missing leaderstats, late leaderstats, odd values ---------------------------------------------------------------
scenario("missing", function()
	local E = boot({})
	noErrors("no leaderstats at start")
	check("no leaderstats at start: the top row is empty (no $nil, no $0)", E.money.Text == "", E.money.Text)
	check("no leaderstats at start: the other rows are there", E.info.Text ~= "" and E.fill ~= nil)
	check("no leaderstats at start: nothing waits but the 1 s tick", #W.waits == 1 and W.waits[1].t == 1)
	advance(3)
	check("no leaderstats for 3 s: still empty, still no error", E.money.Text == "" and #W.errors == 0)

	-- the folder first, then Cash, then Income (as the server builds it)
	local folder = newInstance("Folder")
	folder.Name = "leaderstats"
	folder.Parent = W.player
	advance(0.5)
	check("an empty leaderstats folder: still empty", E.money.Text == "")
	local cash = newInstance("IntValue")
	cash.Name = "Cash"
	cash.Value = 250
	cash.Parent = folder
	advance(0.5)
	check("Cash appears first: the top row shows Cash alone", E.money.Text == "$250", E.money.Text)
	local income = newInstance("IntValue")
	income.Name = "Income"
	income.Value = 5
	income.Parent = folder
	advance(0.5)
	check("Income appears next: the top row shows both", E.money.Text == "$250 · +$5/s", E.money.Text)
	cash.Value = 300
	advance(0.5)
	check("a change after that shows", E.money.Text == "$300 · +$5/s", E.money.Text)
	noErrors("leaderstats comes late")

	-- the values first, the folder after
	local E2 = boot({})
	local f2, c2, i2 = makeStats(70, 3, false)
	advance(0.5)
	check("a finished leaderstats parented at once: shown", E2.money.Text == "$70 · +$3/s", E2.money.Text)
	-- the folder goes away
	f2.Parent = nil
	advance(0.5)
	check("leaderstats removed: the top row goes empty", E2.money.Text == "", E2.money.Text)
	local writes = E2.money._writes.Text
	c2.Value = 99
	advance(1)
	check("leaderstats removed: the old Cash no longer redraws the row", E2.money._writes.Text == writes and E2.money.Text == "", E2.money._writes.Text)
	local f3 = makeStats(8, 1, true)
	advance(0.5)
	check("a new leaderstats after that: shown again", E2.money.Text == "$8 · +$1/s", E2.money.Text)
	noErrors("leaderstats removed and back")

	-- values that are not numbers, or not values
	local E3 = boot({})
	local f4 = newInstance("Folder")
	f4.Name = "leaderstats"
	f4.Parent = W.player
	local bad = newInstance("StringValue")
	bad.Name = "Cash"
	bad.Value = "lots"
	bad.Parent = f4
	local notValue = newInstance("Folder")
	notValue.Name = "Income"
	notValue.Parent = f4
	advance(1)
	check("Cash a string and Income not a value: the row is empty, no error", E3.money.Text == "" and #W.errors == 0, E3.money.Text)
end)

-- 3. Changed events and the minimum interval -------------------------------------------------------------------------
scenario("events", function()
	local E = boot({ stats = { 100, 5 } })
	local folder = W.player:FindFirstChild("leaderstats")
	local cash, income = folder:FindFirstChild("Cash"), folder:FindFirstChild("Income")
	check("events: starts with the values", E.money.Text == "$100 · +$5/s", E.money.Text)
	advance(1)
	local w0 = E.money._writes.Text
	cash.Value = 200
	check("events: a change after a quiet second shows at once (no wait)", E.money.Text == "$200 · +$5/s" and E.money._writes.Text == w0 + 1, E.money.Text)
	cash.Value = 300
	cash.Value = 400
	income.Value = 6
	cash.Value = 500
	check("events: more changes in the same instant do not redraw yet", E.money._writes.Text == w0 + 1 and E.money.Text == "$200 · +$5/s", E.money._writes.Text - w0)
	advance(0.1)
	check("events: still waiting after 0.1 s", E.money._writes.Text == w0 + 1)
	advance(0.2)
	check("events: after the interval one redraw shows the latest values", E.money._writes.Text == w0 + 2 and E.money.Text == "$500 · +$6/s", E.money.Text)
	advance(5)
	check("events: nothing changes, nothing redraws (no loop)", E.money._writes.Text == w0 + 2, E.money._writes.Text - w0)
	-- the server's real pattern: Cash and Income every second
	local before = E.money._writes.Text
	for second = 1, 10 do
		cash.Value += 18
		advance(1)
	end
	check("events: one Cash change a second for 10 s shows 10 times", E.money._writes.Text - before == 10 and E.money.Text == "$680 · +$6/s", E.money._writes.Text - before)
	-- a fast ticker: a change every 0.05 s for 10 s
	before = E.money._writes.Text
	for step = 1, 200 do
		cash.Value += 1
		advance(0.05)
	end
	local draws = E.money._writes.Text - before
	check("events: 200 changes in 10 s redraw at most 4 times a second (" .. draws .. " draws)", draws <= 41, draws)
	check("events: and still keep up (at least 3 a second)", draws >= 30, draws)
	advance(1)
	check("events: after the burst the row shows the last value", E.money.Text == "$880 · +$6/s", E.money.Text)
	noErrors("events")

	-- connections do not pile up
	local base = cash:_signal("Changed"):Count()
	for n = 1, 10 do
		local extra = newInstance("IntValue")
		extra.Name = "Extra" .. n
		extra.Parent = folder
		extra.Parent = nil
		-- a leak doubles the listeners on every add and remove (2^20 after 10 rounds, about 3 GB): stop once it is plain
		if cash:_signal("Changed"):Count() > base + 64 then
			break
		end
	end
	advance(1)
	check("events: adding and removing other stats does not add listeners to Cash (" .. base .. " before and after)", cash:_signal("Changed"):Count() == base, cash:_signal("Changed"):Count())
	check("events: Income has one listener from the bar", income:_signal("Changed"):Count() == 1, income:_signal("Changed"):Count())

	-- replacing Cash: the old one stops driving the row
	local old = cash
	old.Parent = nil
	local new = newInstance("IntValue")
	new.Name = "Cash"
	new.Value = 7
	new.Parent = folder
	advance(1)
	check("events: a new Cash value is shown", E.money.Text == "$7 · +$6/s", E.money.Text)
	local w1 = E.money._writes.Text
	old.Value = 123456
	advance(1)
	check("events: the old, removed Cash does not redraw the row", E.money._writes.Text == w1 and E.money.Text == "$7 · +$6/s", E.money._writes.Text - w1)
	check("events: the bar's listener left the old Cash (only the confirm screen's one stays)", old:_signal("Changed"):Count() == 1, old:_signal("Changed"):Count())
	new.Value = 9
	advance(1)
	check("events: the new Cash drives the row", E.money.Text == "$9 · +$6/s", E.money.Text)
	noErrors("events, replaced Cash")
end)

-- 4. Nothing is polled ------------------------------------------------------------------------------------------------
scenario("idle", function()
	local E = boot({ stats = { 100, 5 } })
	local writes, measures, delays = E.money._writes.Text, W.measures, #W.delays
	advance(30)
	check("idle: 30 s without a change: the top row is not redrawn", E.money._writes.Text == writes, E.money._writes.Text - writes)
	check("idle: 30 s without a change: no text is measured and no delay is started", W.measures == measures and #W.delays == delays, W.measures - measures)
	local ones = 0
	for _, w in ipairs(W.waits) do if w.t == 1 then ones += 1 end end
	check("idle: the only loop is the existing 1 s one (about 30 waits, all of 1 s)", ones == #W.waits and #W.waits >= 29 and #W.waits <= 31, #W.waits)
	check("idle: nothing listens to a frame event", W.run.Heartbeat:Count() == 0 and W.run.RenderStepped:Count() == 0 and W.run.Stepped:Count() == 0)
	noErrors("idle")
end)

-- 4b. Loading: the top row stays empty until the server says the save is loaded ---------------------------------------
-- TycoonCore makes leaderstats at join with Cash 0 and Income 0, writes the saved Cash only after the DataStore read
-- (and a 7 s re-read of a fresh save), the income and the offline earnings after that, then sets Upgrade1..6 (true or
-- false), then data.ready. The bar waits for Upgrade1; if it never comes the row shows the real values after 30 s.
local function pendingLong() -- delays still waiting that are longer than the 1 s tick and the 0.25 s redraw: the loading wait
	local n = 0
	for _, item in ipairs(W.queue) do if item.t - W.clock > 10 then n += 1 end end
	return n
end
-- Advances in 0.05 s steps and keeps every text the top row has had
local function watch(E, seconds)
	E.seen = E.seen or {}
	for _ = 1, math.floor(seconds / 0.05 + 0.5) do
		advance(0.05)
		E.seen[E.money.Text] = true
	end
end
local function neverMoney(E)
	for text in pairs(E.seen) do if text ~= "" then return text end end
	return nil
end
local function swapStats(cash, income)
	local old = W.player:FindFirstChild("leaderstats")
	old.Parent = nil
	return makeStats(cash, income, true)
end

scenario("loading", function()
	-- a returning player, step by step like the server
	local E = boot({ loading = true, stats = { 0, 0 } })
	noErrors("loading")
	local stats = W.player:FindFirstChild("leaderstats")
	local cash, income = stats:FindFirstChild("Cash"), stats:FindFirstChild("Income")
	check("loading: the top row is empty when leaderstats are found (Cash 0, Income 0, the save not loaded)", E.money.Text == "", E.money.Text)
	check("loading: the other rows are there while the top row is empty", E.info.Text ~= "" and E.fill ~= nil)
	watch(E, 7) -- the 7 s re-read
	check("loading: still empty after 7 s with Cash 0 and Income 0", E.money.Text == "", E.money.Text)
	W.player:SetAttribute("IpoCount", 2) -- IpoServer.publish: set before the income and the offline earnings, not a loaded signal
	cash.Value = 12345 -- the saved Cash
	watch(E, 1)
	check("loading: the first change above 0 (the saved Cash) does not show the row", E.money.Text == "", E.money.Text)
	income.Value = 18 -- updateIncome
	watch(E, 0.5)
	cash.Value += 4000 -- the offline earnings
	watch(E, 0.5)
	check("loading: Cash and Income both above 0, the save still not marked loaded: still empty", E.money.Text == "", E.money.Text)
	W.player:SetAttribute("Upgrade1", false)
	check("loading: the Upgrade1 attribute shows the real values at once", E.money.Text == "$16,345 · +$18/s", E.money.Text)
	watch(E, 3)
	check("loading: a returning player never saw $0 · +$0/s (nor any text before the real one)", neverMoney(E) == "$16,345 · +$18/s" and E.seen["$0 · +$0/s"] == nil, neverMoney(E))
	check("loading: the wait is cancelled once the row is shown (no delay left)", pendingLong() == 0, pendingLong())
	cash.Value = 20000
	advance(0.3)
	check("loading: after that the row follows Cash", E.money.Text == "$20,000 · +$18/s", E.money.Text)
	-- an IPO: Cash goes to 0 and the row shows the real $0 at once
	local w0 = E.money._writes.Text
	cash.Value = 0
	advance(0.3)
	check("loading: an IPO reset (Cash to 0) shows $0 within the redraw interval", E.money.Text == "$0 · +$18/s", E.money.Text)
	cash.Value, income.Value = 0, 0
	advance(0.3)
	check("loading: Cash 0 and Income 0 after the row is shown reads $0 · +$0/s (it does not hide again)", E.money.Text == "$0 · +$0/s", E.money.Text)
	noErrors("loading, returning player")

	-- a slow load (retries 2 s + 4 s, then the 7 s re-read, then the Roblox checks): still nothing wrong on the bar
	local S = boot({ loading = true, stats = { 0, 0 } })
	watch(S, 20)
	check("loading: after 20 s of loading the row is still empty (not $0 · +$0/s)", S.money.Text == "" and S.seen[""] == true and neverMoney(S) == nil, S.money.Text)
	watch(S, 9.8)
	check("loading: after 29.8 s it is still empty", S.money.Text == "")
	watch(S, 0.4)
	check("loading: the real values show 30 s after leaderstats were found, if the signal never came", S.money.Text == "$0 · +$0/s", S.money.Text)
	check("loading: the 30 s wait ended, none is left", pendingLong() == 0, pendingLong())
	local F = boot({ loading = true, stats = { 500, 4 } })
	watch(F, 29.9)
	check("loading: Cash 500 and Income 4 at 29.9 s: still empty (nothing changed, so nothing shows)", F.money.Text == "", F.money.Text)
	watch(F, 0.2)
	check("loading: and then the real values after 30 s", F.money.Text == "$500 · +$4/s", F.money.Text)

	-- a brand-new player: $0 · +$0/s is the truth, shown when the server says the save is done
	local B = boot({ loading = true, stats = { 0, 0 } })
	watch(B, 2)
	check("loading: a new player sees nothing while loading", B.money.Text == "")
	W.player:SetAttribute("Upgrade1", false)
	check("loading: a new player sees $0 · +$0/s at once when the server is done", B.money.Text == "$0 · +$0/s", B.money.Text)
	watch(B, 0.1)
	check("loading: a new player's row was empty until then, then $0 · +$0/s", B.seen[""] == true and neverMoney(B) == "$0 · +$0/s", neverMoney(B))

	-- the signal can be true too (Upgrade1 owned)
	local T = boot({ loading = true, stats = { 9, 1 } })
	W.player:SetAttribute("Upgrade1", true)
	check("loading: Upgrade1 = true is the signal too", T.money.Text == "$9 · +$1/s", T.money.Text)

	-- a change to 0 before the signal does not show the row, and only a signal that is not cleared does
	local Z = boot({ loading = true, stats = { 50, 2 } })
	local zc = W.player:FindFirstChild("leaderstats"):FindFirstChild("Cash")
	zc.Value = 0
	watch(Z, 1)
	check("loading: a change to 0 does not show the row early", Z.money.Text == "", Z.money.Text)
	zc.Value = 70
	watch(Z, 1)
	check("loading: a change to 70 does not show it either (only the server's signal does)", Z.money.Text == "", Z.money.Text)
	W.player:SetAttribute("Upgrade1", false)
	W.player:SetAttribute("Upgrade1", nil)
	check("loading: the signal is shown once; a later clear does not hide the row", Z.money.Text == "$70 · +$2/s", Z.money.Text)
	noErrors("loading, new and odd players")

	-- the wait counts from the leaderstats, and neither a Changed event nor Cash and Income coming into the folder restart it
	local D = boot({ loading = true })
	local folder = newInstance("Folder")
	folder.Name = "leaderstats"
	folder.Parent = W.player
	advance(10)
	local dc, di = newInstance("IntValue"), newInstance("IntValue")
	dc.Name, di.Name = "Cash", "Income"
	dc.Parent, di.Parent = folder, folder
	for second = 11, 25 do
		dc.Value = second
		di.Value = second % 3
		advance(1)
	end
	check("loading: Cash and Income added to the folder at 10 s and changed every second: still empty at 25 s", D.money.Text == "", D.money.Text)
	advance(4.9)
	check("loading: still empty at 29.9 s", D.money.Text == "")
	advance(0.2)
	check("loading: shown at 30 s after the folder (Changed events and new children did not restart the wait)", D.money.Text == "$25 · +$1/s", D.money.Text)

	-- the signal first, the leaderstats later; the leaderstats first, the signal later
	local L = boot({ loading = true })
	W.player:SetAttribute("Upgrade1", false)
	advance(1)
	check("loading: the signal with no leaderstats shows nothing", L.money.Text == "")
	makeStats(33, 2, false)
	advance(0.5)
	check("loading: leaderstats that come after the signal show at once", L.money.Text == "$33 · +$2/s", L.money.Text)
	noErrors("loading, order")
end)

scenario("loading rebind", function()
	-- a replaced leaderstats starts the rule again
	local E = boot({ loading = true, stats = { 0, 0 } })
	watch(E, 1)
	W.player:SetAttribute("Upgrade1", false)
	check("loading rebind: shown after the signal", E.money.Text == "$0 · +$0/s", E.money.Text)
	swapStats(77, 3)
	advance(0.5)
	check("loading rebind: a new leaderstats while the server is done (the signal is still set) shows at once", E.money.Text == "$77 · +$3/s", E.money.Text)
	check("loading rebind: no wait is started when the signal is already there", pendingLong() == 0, pendingLong())
	W.player:SetAttribute("Upgrade1", nil) -- as if a new load started
	local _, c2 = swapStats(0, 0)
	advance(0.5)
	check("loading rebind: a new leaderstats with the save not loaded hides the row again", E.money.Text == "", E.money.Text)
	check("loading rebind: the wait is started again (one pending)", pendingLong() == 1, pendingLong())
	advance(20)
	swapStats(0, 0)
	check("loading rebind: a second replacement keeps one pending wait (the old one was cancelled)", pendingLong() == 1, pendingLong())
	advance(20) -- 40 s since the first, 20 s since the last
	check("loading rebind: 40 s after the first, 20 s after the last: still empty (the rule restarted)", E.money.Text == "", E.money.Text)
	advance(10.1)
	check("loading rebind: 30 s after the last replacement the real values show", E.money.Text == "$0 · +$0/s", E.money.Text)
	check("loading rebind: and nothing is left waiting", pendingLong() == 0, pendingLong())
	-- the leaderstats go away: empty, no wait; they come back: the rule starts
	W.player:SetAttribute("Upgrade1", nil)
	W.player:FindFirstChild("leaderstats").Parent = nil
	advance(0.5)
	check("loading rebind: leaderstats removed: empty and no wait pending", E.money.Text == "" and pendingLong() == 0, pendingLong())
	local _, c3 = makeStats(8, 1, true)
	advance(0.5)
	check("loading rebind: leaderstats back, save not loaded: empty, one wait", E.money.Text == "" and pendingLong() == 1, pendingLong())
	W.player:SetAttribute("Upgrade1", false)
	check("loading rebind: the signal shows it and cancels the wait", E.money.Text == "$8 · +$1/s" and pendingLong() == 0, pendingLong())
	noErrors("loading rebind")

	-- 100 rebinds: nothing piles up
	local P = boot({ loading = true, stats = { 0, 0 } })
	local before = #W.queue
	local attrListeners = W.player:GetAttributeChangedSignal("Upgrade1"):Count()
	local oldCash
	for n = 1, 100 do
		local old = W.player:FindFirstChild("leaderstats")
		oldCash = old:FindFirstChild("Cash")
		old.Parent = nil
		makeStats(n, 1, n % 2 == 0)
		advance(0.1)
	end
	local latest = W.player:FindFirstChild("leaderstats")
	check("loading rebind: after 100 replacements there is one wait pending, not 100", pendingLong() == 1, pendingLong())
	check("loading rebind: the queue did not grow (" .. before .. " before, " .. #W.queue .. " after)", #W.queue <= before + 2, #W.queue)
	check("loading rebind: the signal has still one listener", W.player:GetAttributeChangedSignal("Upgrade1"):Count() == attrListeners, W.player:GetAttributeChangedSignal("Upgrade1"):Count())
	check("loading rebind: the latest Cash has one listener from the bar (and the confirm screen's)", latest:FindFirstChild("Cash"):_signal("Changed"):Count() <= 2 and latest:FindFirstChild("Income"):_signal("Changed"):Count() == 1, latest:FindFirstChild("Income"):_signal("Changed"):Count())
	check("loading rebind: the old Cash lost the bar's listener", oldCash:_signal("Changed"):Count() <= 1, oldCash:_signal("Changed"):Count())
	check("loading rebind: the row is still empty (never revealed by a rebind)", P.money.Text == "", P.money.Text)
	W.player:SetAttribute("Upgrade1", false)
	check("loading rebind: then the signal shows the latest values and leaves nothing waiting", P.money.Text == "$100 · +$1/s" and pendingLong() == 0, P.money.Text)
	noErrors("loading rebind, 100 times")
end)

-- 5. The progress bar and the bottom row ------------------------------------------------------------------------------
scenario("progress", function()
	local stages = IpoConfig.Stages
	local function progressFor(valuation, count)
		local index = IpoConfig.stageIndex(valuation, count)
		local last = index == #stages
		local from = IpoConfig.stageValuation(index, count)
		local to = last and from or IpoConfig.stageValuation(index + 1, count)
		return last and 1 or math.clamp((valuation - from) / math.max(1, to - from), 0, 1)
	end
	-- overhaul 2's ladder: Seed 30K, Series A 10M, Series B 100M, Series C 300M, IPO-ready 1B (x1.1 per IPO)
	local cases = { { 0, 0 }, { 15000, 0 }, { 30000, 0 }, { 5000000, 0 }, { 9999999, 0 }, { 100000000, 0 }, { 300000000, 0 }, { 2e9, 0 }, { 0, 1 }, { 33000, 1 }, { 40000, 3 } }
	for _, c in ipairs(cases) do
		local E = boot({ attrs = { IpoValuation = c[1], IpoCount = c[2] }, stats = { 123, 4 } })
		local want = progressFor(c[1], c[2])
		check("progress, valuation " .. c[1] .. " after " .. c[2] .. " IPOs: the fill is " .. string.format("%.4f", want) .. " of the track",
			math.abs(E.fill.Size.X.Scale - want) < 1e-9 and E.fill.Size.Y.Scale == 1 and E.fill.Size.X.Offset == 0, E.fill.Size.X.Scale)
		check("progress, " .. c[1] .. "/" .. c[2] .. ": the track is 12 px high, 10 px in from each side, at y 26 (unchanged)",
			E.track.Position.X.Offset == 10 and E.track.Position.Y.Offset == 26 and E.track.Size.X.Offset == -20 and E.track.Size.Y.Offset == 12 and E.track.Size.X.Scale == 1, E.track.Size.Y.Offset)
	end
	local E = boot({ attrs = { IpoValuation = 15000, IpoCount = 0 }, stats = { 123, 4 } })
	check("progress: half way to Seed is 0.5", math.abs(E.fill.Size.X.Scale - 0.5) < 1e-9, E.fill.Size.X.Scale)
	E.W.player:SetAttribute("IpoValuation", 20000)
	advance(0)
	check("progress: it follows the valuation attribute", math.abs(E.fill.Size.X.Scale - 20000 / 30000) < 1e-9, E.fill.Size.X.Scale)
	local ready = boot({ attrs = { IpoValuation = 1200000000 }, stats = { 123, 4 } })
	check("progress: IPO-ready shows a full bar and the IPO button says IPO!", ready.fill.Size.X.Scale == 1 and ready.button.Text == "🔔\nIPO!", ready.button.Text)
	check("progress: the IPO button text is back to normal below IPO-ready", E.button.Text == "📈\nIPO", E.button.Text)
end)

scenario("bottom", function()
	local function room(E) return E.bar.Size.X.Offset - 20 end
	local icon = function(i) return IpoConfig.Stages[i].icon end
	local BELL = "🔔"
	-- wide bar
	local E = boot({ attrs = { IpoValuation = 0 }, stats = { 123, 4 } })
	local tiers = { icon(1) .. " Garage → Seed · $0 / $30K", icon(1) .. " Garage · $0 / $30K", icon(1) .. " $0 / $30K", "$0 / $30K" }
	check("bottom, wide, Garage at 0: the fullest of the stage forms that fits", E.info.Text == first(tiers, 14, room(E)), E.info.Text)
	check("bottom, wide: the multiplier and Shares are not shown at x1 and 0 Shares", not has(E.info.Text, "x1") and not has(E.info.Text, "📜"), E.info.Text)
	E = boot({ attrs = { IpoValuation = 40000 }, stats = { 123, 4 } })
	tiers = { icon(2) .. " Seed → Series A · $40K / $10M", icon(2) .. " Seed · $40K / $10M", icon(2) .. " $40K / $10M", "$40K / $10M" }
	check("bottom, wide, Seed at 40000", E.info.Text == first(tiers, 14, room(E)), E.info.Text)
	-- a font half as wide as the estimate: the whole line fits, so the extras show too
	local roomy = boot({ widthScale = 0.5, attrs = { IpoValuation = 40000, IpoCount = 0, IpoShares = 12 }, stats = { 123, 4 } })
	check("bottom: with room, 12 Shares add ' · 📜 12' to the line", roomy.info.Text == icon(2) .. " Seed → Series A · $40K / $10M · 📜 12", roomy.info.Text)
	local index = IpoConfig.stageIndex(40000, 2)
	local mult = IpoConfig.formatMultiplier(IpoConfig.multiplier(2))
	local want = string.format("%s %s → %s · $40K / %s · %s · 📜 12", icon(index), IpoConfig.Stages[index].name, IpoConfig.Stages[index + 1].name, IpoConfig.formatShort(IpoConfig.stageValuation(index + 1, 2)), mult)
	local two = boot({ widthScale = 0.5, attrs = { IpoValuation = 40000, IpoCount = 2, IpoShares = 12 }, stats = { 123, 4 } })
	check("bottom: after 2 IPOs with 12 Shares and room, the multiplier and the Shares follow the valuation: " .. want, two.info.Text == want, two.info.Text)
	local onlyMult = boot({ widthScale = 0.5, attrs = { IpoValuation = 40000, IpoCount = 2, IpoShares = 0 }, stats = { 123, 4 } })
	check("bottom: after 2 IPOs and 0 Shares only the multiplier is added", has(onlyMult.info.Text, mult) and not has(onlyMult.info.Text, "📜"), onlyMult.info.Text)
	-- narrow bar
	local N = boot({ w = 320, h = 568, attrs = { IpoValuation = 0 }, stats = { 123, 4 } })
	check("bottom, narrow (138 px): fits at 14 px", modelWidth(N.info.Text, N.info.TextSize) <= 138 and N.info.TextSize == 14, N.info.Text)
	check("bottom, narrow: the valuation and its target are both there", has(N.info.Text, "$0 / $30K"), N.info.Text)
	N = boot({ w = 320, h = 568, attrs = { IpoValuation = 2000, IpoCount = 1, IpoShares = 99 }, stats = { 123, 4 } })
	check("bottom, narrow, with a multiplier and 99 Shares: still fits at 14 px", modelWidth(N.info.Text, N.info.TextSize) <= 138, N.info.Text)
	check("bottom, narrow: the valuation is kept (the extras go first)", has(N.info.Text, "$2K / "), N.info.Text)
	-- IPO-ready
	local Rd = boot({ attrs = { IpoValuation = 1200000000 }, stats = { 123, 4 } })
	local rt = { BELL .. " IPO-ready! Tap to go public", BELL .. " IPO-ready! · $1.2B", BELL .. " IPO-ready!", BELL .. " IPO!" }
	check("bottom, wide, IPO-ready: the fullest IPO-ready text that fits", Rd.info.Text == first(rt, 14, room(Rd)), Rd.info.Text)
	Rd = boot({ w = 320, h = 568, attrs = { IpoValuation = 1200000000 }, stats = { 123, 4 } })
	check("bottom, narrow, IPO-ready: fits at 14 px and says IPO", modelWidth(Rd.info.Text, 14) <= 138 and has(Rd.info.Text, "IPO"), Rd.info.Text)
	Rd = boot({ widthScale = 0.5, attrs = { IpoValuation = 1200000000 }, stats = { 123, 4 } })
	check("bottom, IPO-ready with room: 'IPO-ready! Tap to go public' (the text it had before)", Rd.info.Text == BELL .. " IPO-ready! Tap to go public", Rd.info.Text)
	-- odd attribute values do not break the row
	local Odd = boot({ attrs = { IpoValuation = NAN, IpoCount = 0, IpoShares = 0 }, stats = { 123, 4 } })
	check("bottom: a NaN valuation does not put nan on the bar", not has(Odd.info.Text:lower(), "nan") and #W.errors == 0, Odd.info.Text)
	Odd = boot({ attrs = { IpoValuation = 1e30 }, stats = { 123, 4 } })
	check("bottom: a huge valuation is capped, so the row stays short", #W.errors == 0 and modelWidth(Odd.info.Text, Odd.info.TextSize) <= room(Odd), Odd.info.Text)
end)

-- 6. Resizing refits the rows ------------------------------------------------------------------------------------------
scenario("resize", function()
	local E = boot({ w = 667, h = 339, attrs = { IpoValuation = 2000, IpoShares = 5, IpoCount = 1 }, stats = { 123456, 12345 } })
	local wide = E.money.Text
	check("resize: wide at first (233 px bar)", E.bar.Size.X.Offset == 233 and wide == "$123.5K · +$12.3K/s", wide)
	setScreen(320, 568)
	advance(0.5)
	check("resize: 320x568 makes the bar 158 px", E.bar.Size.X.Offset == 158, E.bar.Size.X.Offset)
	check("resize: the top row fits again on the narrow bar", modelWidth(E.money.Text, E.money.TextSize) <= 138, E.money.Text)
	check("resize: the bottom row fits again on the narrow bar", modelWidth(E.info.Text, E.info.TextSize) <= 138, E.info.Text)
	setScreen(667, 339)
	advance(0.5)
	check("resize: back to the wide bar, the fuller text comes back", E.money.Text == wide, E.money.Text)
	noErrors("resize")
end)

-- 7. Rectangles at five sizes with three top bars ---------------------------------------------------------------------------
local GOALS = __GOALCOUNT__
local SIZES = { { 667, 375 }, { 320, 568 }, { 568, 320 }, { 640, 360 }, { 844, 390 } }
local BARS = { 0, 36, 58 }
local LANE_OFFSETS = { 16, 72, 128, 184, 240 }
local function oldBar(w, h) -- where the bar was before the change (IpoClient.lua, placeHud)
	if h < 460 then
		local width = math.clamp(w - 370 - 10 - 54, 0, 250)
		if width >= 180 then return R(370, 6, width, 64) end
		return R(10, 76, math.min(250, w - 20 - 54), 64)
	end
	return R(98, 12, math.clamp(w - 108 - 54, 150, 250), 64)
end
local function hudButtonRect(slot, w, h)
	if h < 460 then return R(10 + slot * 72, 6, 64, 64) end
	return R(12, h * 0.5 + (slot - 2) * 86 - 38, 76, 76)
end
local function lane(w, h, offset)
	local width = math.min(0.6 * w, 520)
	return R((w - width) / 2, h - offset - 48, width, 48)
end
local function others(w, h, bar)
	local list = {}
	for slot, name in ipairs({ "EGGS", "SHOP", "TEAM", "POACH" }) do list[name .. " button"] = hudButtonRect(slot - 1, w, h) end
	local chipX = math.min(bar.x + bar.w + 6, w - 48 - 2)
	list["daily chip"] = R(chipX, bar.y + (64 - 48) / 2, 48, 48)
	list["Goals card"] = R(bar.x, bar.y + 70, bar.w, 30 + 22 * GOALS + 8)
	local tray = trayLayout(w, h)
	list["call tray"] = R(tray.x, tray.y, tray.w, tray.h)
	list["call tray line"] = R(tray.x, tray.infoY, tray.w, tray.infoH)
	for _, offset in ipairs(LANE_OFFSETS) do
		if h >= 460 or offset ~= 240 then list["lane -" .. offset] = lane(w, h, offset) end
	end
	list["thumbstick"] = R(0, h - 170, 170, 170)
	list["jump button"] = R(w - 150, h - 130, 150, 130)
	return list
end
local function touching(rect, list)
	local names = {}
	for name, other in pairs(list) do if overlaps(rect, other) then table.insert(names, name) end end
	table.sort(names)
	return table.concat(names, ", ")
end
-- What the bar touches today and did before this change, per size and top bar. The call tray, the pop-up lanes,
-- the thumbstick and the jump button are not moved by this change; the HUD buttons, the chip and the Goals card
-- must never be touched. (Same overlaps tools/daily_test.py lists as ACCEPTED for the tray at 568x320.)
local TOUCHES = __TOUCHES__
local DUMP = __DUMP__
for _, size in ipairs(SIZES) do
	for _, bar in ipairs(BARS) do
		local dw, dh = size[1], size[2]
		local gw, gh = dw, dh - bar
		local tag = dw .. "x" .. dh .. " top bar " .. bar .. " (screen " .. gw .. "x" .. gh .. ")"
		scenario(tag, function()
			local E = boot({ w = gw, h = gh, attrs = { IpoValuation = 2000, IpoShares = 5, IpoCount = 1 }, stats = { 123456, 12345 } })
			noErrors(tag)
			local barRect, was = rectOf(E.bar), oldBar(gw, gh)
			check(tag .. ": the bar is where it was (x " .. was.x .. ", y " .. was.y .. ", " .. was.w .. " x " .. was.h .. ")",
				barRect.x == was.x and barRect.y == was.y and barRect.w == was.w and barRect.h == was.h, barRect.x .. "," .. barRect.y .. "," .. barRect.w .. "," .. barRect.h)
			local money, track, info = rectOf(E.money), rectOf(E.track), rectOf(E.info)
			check(tag .. ": the three rows are inside the bar", inside(money, barRect) and inside(track, barRect) and inside(info, barRect))
			check(tag .. ": the top row is above the progress bar and the bottom row below it, none overlap", money.y + money.h <= track.y and track.y + track.h <= info.y and money.y < track.y)
			check(tag .. ": the rows keep 10 px from the bar's left and right edges", money.x - barRect.x == 10 and barRect.x + barRect.w - (money.x + money.w) == 10 and info.x - barRect.x == 10 and barRect.x + barRect.w - (info.x + info.w) == 10)
			check(tag .. ": each text row is as high as its text (16 px text in 22, 14 px in 20)", money.h >= E.money.TextSize and info.h >= E.info.TextSize and E.info.TextSize == 14, E.money.TextSize)
			check(tag .. ": the progress bar is where it was (y +26, 12 high, 10 in from the sides)", track.x == barRect.x + 10 and track.y == barRect.y + 26 and track.h == 12 and track.w == barRect.w - 20)
			local ipoButton = rectOf(E.button)
			local list = others(gw, gh, barRect)
			list["IPO button"] = ipoButton
			local hit = touching(barRect, list)
			local strict = {}
			for name, other in pairs(list) do
				if (name:find("button") and not name:find("jump")) or name == "daily chip" or name == "Goals card" then strict[name] = other end
			end
			check(tag .. ": the bar touches no HUD button, no daily chip and no Goals card", touching(barRect, strict) == "", touching(barRect, strict))
			local key = dw .. "x" .. dh .. "/" .. bar
			if DUMP then print_real(key .. " -> " .. hit) end
			check(tag .. ": what the bar touches is what it touched before (" .. (TOUCHES[key] or "nothing") .. ")", hit == (TOUCHES[key] or ""), hit)
			-- the rows' text sizes: every text on the bar is 14 or more
			local smallest = 99
			for _, label in ipairs(E.labels) do
				smallest = math.min(smallest, label.TextSize)
				if label.TextScaled then smallest = 0 end
				for _, kid in ipairs(label:GetChildren()) do
					if kid._class == "UITextSizeConstraint" and (kid._p.MinTextSize or 0) < 14 then smallest = 0 end
				end
			end
			check(tag .. ": every text on the bar is 14 px or more, fixed size, never scaled below it", smallest >= 14, smallest)
			check(tag .. ": a text that is too long is cut with ... (TextTruncate), never drawn over the bar's edge", E.money.TextTruncate == Enum.TextTruncate.AtEnd and E.info.TextTruncate == Enum.TextTruncate.AtEnd)
			-- the longest top row the bar can show fits in the rows
			for _, c in ipairs({ { 123456, 12345 }, { 999999, 99999 }, { 1e15, 1e15 }, { 4630, 18 } }) do
				local F = boot({ w = gw, h = gh, attrs = { IpoValuation = 2000, IpoShares = 5, IpoCount = 1 }, stats = c })
				local width = F.bar.Size.X.Offset - 20
				check(tag .. ", Cash " .. c[1] .. ": the top row fits its row (" .. F.money.Text .. ")", modelWidth(F.money.Text, F.money.TextSize) <= width, F.money.Text)
				check(tag .. ": the bottom row fits its row (" .. F.info.Text .. ")", modelWidth(F.info.Text, F.info.TextSize) <= width, F.info.Text)
			end
		end)
	end
end

-- 8. Words: no odds, chance, luck or random; no emoji in the top row ------------------------------------------------------
scenario("words", function()
	local seen = {}
	local function look(E)
		for _, text in ipairs({ E.money.Text, E.info.Text }) do seen[text] = true end
	end
	for _, v in ipairs(VALUES) do look(boot({ stats = { v[1], v[2] } })) end
	for _, valuation in ipairs({ 0, 2000, 7000, 30000, 81000, 900000 }) do
		for _, count in ipairs({ 0, 1, 5 }) do
			look(boot({ attrs = { IpoValuation = valuation, IpoCount = count, IpoShares = count * 7 }, stats = { 5, 5 } }))
			look(boot({ w = 320, h = 568, attrs = { IpoValuation = valuation, IpoCount = count, IpoShares = count * 7 }, stats = { 5, 5 } }))
		end
	end
	local bad, emoji = nil, nil
	for text in pairs(seen) do
		local low = text:lower()
		if has(low, "odds") or has(low, "chance") or has(low, "luck") or has(low, "random") then bad = text end
	end
	check("words: no text on the bar says odds, chance, luck or random", bad == nil, bad)
	for _, v in ipairs(VALUES) do
		for _, size in ipairs({ { 667, 339 }, { 320, 568 } }) do
			local E = boot({ w = size[1], h = size[2], stats = { v[1], v[2] } })
			for _, cp in utf8.codes(E.money.Text) do
				if cp > 127 and cp ~= 0xB7 then emoji = E.money.Text end
			end
		end
	end
	check("words: the top row has no emoji (letters, digits, $ + , . / and the middle dot only)", emoji == nil, emoji)
end)

print_real(string.format("%d passed, %d failed", passed, failed))
"""


# The expected overlaps of the bar (see the comment in SCENARIOS: unchanged by this work). The keys are
# "<device width>x<device height>/<top bar>".
TOUCHES = {
    # 568x320 (a phone held sideways, narrow): the bar sits under the HUD row, over the call tray's spot. The same overlap
    # tools/daily_test.py lists as ACCEPTED for the tray ("valuation bar"); the bar is where it was before, so nothing is new.
    "568x320/0": "call tray, call tray line, lane -184",
    "568x320/36": "call tray, call tray line, lane -128, lane -184, thumbstick",
    "568x320/58": "call tray, call tray line, lane -128, lane -184, thumbstick",
}


def lua_touches():
    items = ", ".join('["%s"] = "%s"' % (k, v) for k, v in sorted(TOUCHES.items()))
    return "{ " + items + " }"


# --- static checks on the source (no Studio, no Lua run) ---------------------------------------------------------
def static_checks(client_text):
    """(name, passed, extra) for what can be checked on the source itself."""
    out = []
    code = code_only(client_text)

    def add(name, cond, extra=None):
        out.append((name, bool(cond), extra))

    add("static: IpoClient.lua has exactly one `while true do` loop (the existing 1 s cooldown tick, no polling loop added)", len(re.findall(r"\bwhile\s+true\s+do\b", code)) == 1, len(re.findall(r"\bwhile\s+true\s+do\b", code)))
    add("static: no RunService, Heartbeat, RenderStepped or Stepped in IpoClient.lua", not re.search(r"RunService|Heartbeat|RenderStepped|\.Stepped", code))
    add("static: no `repeat ... until` loop in IpoClient.lua", not re.search(r"\brepeat\b", code))
    add("static: IpoClient.lua has no Touched handler", "Touched" not in code)
    add("static: IpoClient.lua never calls addEarnings, DataStore or MarketplaceService", not re.search(r"addEarnings|DataStore|MarketplaceService", code))
    add("static: the only remote call is the one IpoAction request function (InvokeServer once, no FireServer)", code.count(":InvokeServer(") == 1 and ":FireServer(" not in code, code.count(":InvokeServer("))
    remotes = sorted(set(re.findall(r'remotes:WaitForChild\("(\w+)"\)', code)))
    add("static: no new remote: IpoClient waits for IpoAction and IpoEvent only", remotes == ["IpoAction", "IpoEvent"] and "Instance.new(\"RemoteEvent\")" not in code and "Instance.new(\"RemoteFunction\")" not in code, remotes)
    sizes = re.search(r"local MONEY_SIZES = \{([^}]*)\}", code)
    info = re.search(r"local INFO_SIZE = (\d+)", code)
    numbers = [int(n) for n in re.findall(r"\d+", sizes.group(1))] if sizes else [0]
    add("static: the top row's text sizes are all 14 or more (MONEY_SIZES = %s)" % (sizes.group(1).strip() if sizes else "missing"), sizes is not None and min(numbers) >= 14, numbers)
    add("static: the bottom row's text size is 14 or more (INFO_SIZE)", info is not None and int(info.group(1)) >= 14, info.group(1) if info else None)
    interval = re.search(r"local MONEY_INTERVAL = ([\d.]+)", code)
    add("static: the top row has a minimum interval of 0.2 s or more between redraws (MONEY_INTERVAL)", interval is not None and float(interval.group(1)) >= 0.2, interval.group(1) if interval else None)
    # D9: the bar's own code (from the text measure to the end of refreshHud's first lines) has no odds words
    start = client_text.find("local function textWidth")
    end = client_text.find("ipoButton.Text = info.ready", start)
    region = client_text[start:end] if start >= 0 and end > start else ""
    add("static: the bar's code is found (text measure to refreshHud)", len(region) > 500, len(region))
    words = [w for w in ("odds", "chance", "luck", "random") if re.search(w, region, re.I)]
    add("static: the bar's code and texts have no odds, chance, luck or random (D9)", not words, words)
    add("static: no new string in the bar's code has an emoji except the ones the bar already had (the stage icons come from IpoConfig, then 🔔 and 📜)",
        all(ch in "🔔📜🏚" or ord(ch) < 0x1F000 for ch in region), None)
    return out


# docs/STUDIO_SYNC_HUD.md is history: it was last brought up to date with IpoClient.lua at SYNC_COMMIT (lobby L3, which
# changed both), and later Studio steps go to docs/STUDIO_SYNC_BATCH.md. So its hash and size are checked against
# IpoClient.lua as it was at that commit (read with git show), never today's file: a later edit of IpoClient never fails
# this suite (ux backlog item 5, like tools/lobby_test.py's L1_COMMIT and ALL_COMMIT).
SYNC_COMMIT = "645393a"
def git_show(rev, path):
    """The bytes of path at rev, or None if git or the commit is missing (a copy without the history, a shallow clone)."""
    try:
        got = subprocess.run(["git", "show", "%s:%s" % (rev, path)], cwd=ROOT, capture_output=True)
    except OSError:
        return None
    return got.stdout if got.returncode == 0 else None


def doc_checks():
    """The hash and size in docs/STUDIO_SYNC_HUD.md are those of IpoClient.lua at SYNC_COMMIT (the doc is history)."""
    raw = git_show(SYNC_COMMIT, CLIENT)
    if raw is None:
        return [("doc: IpoClient.lua at %s can be read (git show; a copy without the git history or a shallow clone lacks it)" % SYNC_COMMIT,
                 False, SYNC_COMMIT)]
    digest = hashlib.sha256(raw).hexdigest()
    doc = read("docs/STUDIO_SYNC_HUD.md")
    return [
        ("doc: docs/STUDIO_SYNC_HUD.md has the SHA-256 of IpoClient.lua at %s (%s)" % (SYNC_COMMIT, digest[:12]), doc.count(digest) >= 2, digest),
        ("doc: docs/STUDIO_SYNC_HUD.md has the size of IpoClient.lua at %s (%d bytes)" % (SYNC_COMMIT, len(raw)), "| %d |" % len(raw) in doc and ", %d }" % len(raw) in doc, len(raw)),
        ("doc: docs/STUDIO_SYNC_HUD.md has the section \"What this rule depends on\" (the coupling, the 30 s delay, the test, the owner defaults)",
         "## (h) What this rule depends on" in doc and "tools/hud_test.py" in doc.split("## (h) What this rule depends on")[1] and "MONEY_WAIT" in doc.split("## (h) What this rule depends on")[1]
         and "OWNER DEFAULTS" in doc.split("## (h) What this rule depends on")[1], None),
        ("doc: docs/STUDIO_SYNC_HUD.md has the Follow-ups line about IpoConfig.formatShort ($1000K)",
         "## (i) Follow-ups" in doc and "IpoConfig.formatShort" in doc.split("## (i) Follow-ups")[1] and "$1000K" in doc.split("## (i) Follow-ups")[1], None),
    ]


# --- coupling to TycoonCore (docs/STUDIO_SYNC_HUD.md, "What this rule depends on") -------------------------------
# The bar keeps Cash and Income empty until the player attribute LOADED_ATTRIBUTE (Upgrade1) appears. That is only a
# "the save is loaded" signal because TycoonCore sets it, in refreshSign -> publishUpgrades, after the saved Cash is
# written, after the income and the offline earnings, and before data.ready. Nothing else ties the two files together,
# so these checks read the REAL TycoonCore.lua (and the other scripts) as text and fail, with a name, if that changes.
# They look at the order of source positions inside onPlayerAdded and at a list of the allowed call sites of
# refreshSign; comments, string contents, whitespace and indentation do not matter.
REVIEW_HINT = "re-review the HUD loading rule (IpoClient LOADED_ATTRIBUTE, docs/STUDIO_SYNC_HUD.md 'What this rule depends on'), then update tools/hud_test.py"
# Where TycoonCore may call refreshSign today: the load (onPlayerAdded, right before data.ready), a purchase (buyUpgrade,
# after checkUpgradePurchase's data.ready guard) and the IPO commit (commitIpo, which only runs from IpoServer's
# data.ready-guarded onAction). A new call site fails the check "refreshSign is called from exactly ...".
REFRESH_SIGN_SITES = ["buyUpgrade", "claimGarage", "commitIpo"]  # lobby L3: the join's load is the claim's (claimGarage)
# MONEY_WAIT must cover the waits the server script adds to a join (a read's retries, the re-read wait, the second read's
# retries) plus this many seconds for Roblox's own DataStore answers: the owner default's worst case is about 29 s, and
# TycoonCore's own waits are 19 s today.
DATASTORE_ALLOWANCE = 10
MIN_MONEY_WAIT = 30  # OWNER DEFAULT: the client's safety delay stays 30 s


def lua_views(text):
    """(comments blanked, comments and string contents blanked). Both have the length of the text, so a position in one is
    the same place in the other. Newlines are kept."""
    def pad(s):
        return re.sub(r"[^\n]", " ", s)

    keep, blank = [], []
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if text.startswith("--", i):
            m = re.match(r"--\[(=*)\[", text[i:i + 40])
            if m:
                close = "]" + m.group(1) + "]"
                j = text.find(close, i + len(m.group(0)))
                j = n if j < 0 else j + len(close)
            else:
                j = text.find("\n", i)
                j = n if j < 0 else j
            keep.append(pad(text[i:j]))
            blank.append(pad(text[i:j]))
            i = j
        elif ch in "\"'":
            j = i + 1
            while j < n and text[j] != ch and text[j] != "\n":
                j += 2 if text[j] == "\\" else 1
            j = min(j + 1, n)
            s = text[i:j]
            keep.append(s)
            blank.append(s[0] + pad(s[1:-1]) + s[-1] if len(s) >= 2 else s)
            i = j
        else:
            m = re.match(r"\[(=*)\[", text[i:i + 40]) if ch == "[" else None
            if m:
                close = "]" + m.group(1) + "]"
                j = text.find(close, i + len(m.group(0)))
                j = n if j < 0 else j + len(close)
                keep.append(text[i:j])
                blank.append(pad(text[i:j]))
                i = j
            else:
                keep.append(ch)
                blank.append(ch)
                i += 1
    return "".join(keep), "".join(blank)


def lua_functions(blank):
    """([(name or None, start, end)], open blocks left, stray ends) for every `function ... end`. `name` is the declared
    name (local function x, function a.b, x = function). Blocks are matched by function/if/do/repeat against end/until
    (while and for open with their `do`); an `if` that is an expression (`x = if a then b else c`) has no `end`."""
    spans, stack, stray = [], [], 0
    for m in re.finditer(r"\b(function|if|do|repeat|end|until)\b", blank):
        word = m.group(1)
        if word in ("end", "until"):
            if not stack:
                stray += 1
                continue
            kind, start, name = stack.pop()
            if kind == "function":
                spans.append((name, start, m.end()))
            continue
        name = None
        if word == "if":
            before = blank[:m.start()].rstrip()
            if re.search(r"(=|\(|,|\{|\+|-|\*|/|%|\^|<|>|~|\.\.)$", before) or re.search(r"\b(return|and|or|not)$", before):
                continue
        if word == "function":
            nm = re.match(r"function\s+([A-Za-z_][\w.:]*)\s*\(", blank[m.start():m.start() + 200])
            if nm:
                name = nm.group(1)
            else:
                pre = re.search(r"([A-Za-z_][\w.:]*)\s*=\s*$", blank[max(0, m.start() - 200):m.start()])
                name = pre.group(1) if pre else None
        stack.append((word, m.start(), name))
    return spans, len(stack), stray


def enclosing_function(spans, pos):
    """The name of the innermost NAMED function around a position (an anonymous function belongs to the named one it is in)."""
    best = None
    for name, start, end in spans:
        if name and start <= pos < end and (best is None or start > best[1]):
            best = (name, start)
    return best[0] if best else None


def function_span(spans, name):
    found = [(s, e) for n, s, e in spans if n == name]
    return found[0] if found else None


def identifier_uses(blank, name):
    """Positions of the bare identifier `name`, except where it is being declared (`function name(`)."""
    out = []
    for m in re.finditer(r"(?<![\w.:])" + re.escape(name) + r"\b", blank):
        if re.search(r"\bfunction\s+$", blank[max(0, m.start() - 20):m.start()]):
            continue
        out.append(m.start())
    return out


def set_attribute_calls(keep, blank):
    """[(position, first argument as written)] for every :SetAttribute( call."""
    out = []
    for m in re.finditer(r"[:.]SetAttribute\s*\(", blank):
        j, depth = m.end(), 0
        while j < len(blank):
            c = blank[j]
            if c in "([{":
                depth += 1
            elif c in ")]}":
                if depth == 0:
                    break
                depth -= 1
            elif c == "," and depth == 0:
                break
            j += 1
        out.append((m.start(), keep[m.end():j].strip()))
    return out


def sets_upgrade_name(arg):
    """True if a SetAttribute's first argument is, or starts as, an Upgrade1 .. UpgradeN name."""
    return bool(re.fullmatch(r"""(["'])Upgrade\d+\1""", arg) or re.match(r"""(["'])Upgrade\1\s*\.\.""", arg))


def coupling_checks(core_text, client_text, others):
    """(name, passed, extra) for the ties between IpoClient's loading rule and the server scripts. `others` maps a file
    name to its text for every script but TycoonCore.lua (a stray Upgrade attribute, and the IPO commit's guard)."""
    out = []

    def add(name, cond, extra=None):
        out.append(("coupling: " + name, bool(cond), extra))

    keep, blank = lua_views(core_text)
    spans, open_blocks, stray = lua_functions(blank)
    need = ["claimGarage", "onPlayerAdded", "refreshSign", "publishUpgrades", "buyUpgrade", "checkUpgradePurchase", "commitIpo", "load"]
    missing = [n for n in need if function_span(spans, n) is None]
    add("TycoonCore.lua has the functions the loading rule is checked on (%s)" % ", ".join(need), not missing, "missing: %s. %s" % (missing, REVIEW_HINT))
    add("TycoonCore.lua's function/if/do/end blocks balance (the checks below read them)", open_blocks == 0 and stray == 0, "%d open, %d stray ends" % (open_blocks, stray))
    if missing:
        return out

    # who calls refreshSign (and so, through it, publishUpgrades, which sets Upgrade1 .. Upgrade6)
    uses = identifier_uses(blank, "refreshSign")
    sites = sorted("%s%s" % (enclosing_function(spans, p) or "(top level)", "" if re.match(r"\s*\(", blank[p + len("refreshSign"):]) else " (not a call)") for p in uses)
    add("refreshSign is called from exactly the load (claimGarage), a purchase (buyUpgrade) and the IPO commit (commitIpo), once each", sites == REFRESH_SIGN_SITES,
        "found %s, allowed %s. A new call site: %s" % (sites, REFRESH_SIGN_SITES, REVIEW_HINT))
    publish_sites = [enclosing_function(spans, p) for p in identifier_uses(blank, "publishUpgrades")]
    add("publishUpgrades is used once, by refreshSign, and nowhere else", publish_sites == ["refreshSign"], "%s. %s" % (publish_sites, REVIEW_HINT))

    # where Upgrade1 .. Upgrade6 are set
    calls = [(a, enclosing_function(spans, p)) for p, a in set_attribute_calls(keep, blank)]
    is_literal = lambda a: re.fullmatch(r"""(["']).*\1""", a) is not None
    stray_sets = [(a, f) for a, f in calls if f != "publishUpgrades" and (sets_upgrade_name(a) or not is_literal(a))]
    inside = [a for a, f in calls if f == "publishUpgrades"]
    ps, pe = function_span(spans, "publishUpgrades")
    add("TycoonCore.lua sets an Upgrade attribute only inside publishUpgrades (nowhere else, not even at join)", not stray_sets, "%s. %s" % (stray_sets, REVIEW_HINT))
    add("publishUpgrades sets exactly one attribute, \"Upgrade\" .. i, for every entry of UPGRADES",
        len(inside) == 1 and re.fullmatch(r"""(["'])Upgrade\1\s*\.\.\s*i""", inside[0]) is not None
        and re.search(r"\bfor\s+i\s*,\s*\w+\s+in\s+ipairs\(\s*UPGRADES\s*\)\s+do\b", blank[ps:pe]) is not None, "%s. %s" % (inside, REVIEW_HINT))
    elsewhere = {}
    for fname, text in sorted(others.items()):
        k, b = lua_views(text)
        hits = [a for p, a in set_attribute_calls(k, b) if sets_upgrade_name(a)]
        if hits:
            elsewhere[fname] = hits
    add("no other script sets Upgrade1 .. UpgradeN", not elsewhere, "%d scripts looked at: %s. %s" % (len(others), elsewhere or "none", REVIEW_HINT))

    # lobby L3: leaderstats (Cash and Income at 0) are made by the claim, right before the load, never at the join
    js, je = function_span(spans, "onPlayerAdded")
    cs, ce = function_span(spans, "claimGarage")
    add("leaderstats are made in claimGarage (the claim, right before the load), not in onPlayerAdded (the join)",
        '"leaderstats"' not in keep[js:je] and keep.count('Name = "leaderstats"') == 1 and 'Name = "leaderstats"' in keep[cs:ce], REVIEW_HINT)

    # the order inside the load (claimGarage): saved Cash, income, offline earnings, THEN refreshSign, THEN data.ready
    s, e = function_span(spans, "claimGarage")
    body = blank[s:e]

    def first(pattern):
        m = re.search(pattern, body)
        return m.start() if m else None

    p_load = first(r"\bload\s*\(\s*player\s*\)")
    p_cash = first(r"\bcash\.Value\s*=(?!=)")
    p_income = first(r"\bupdateIncome\s*\(\s*player\s*\)")
    p_offline = first(r"\bcash\.Value\s*\+=")
    p_earnings = first(r"\baddEarnings\s*\(")
    p_ready = first(r"\bdata\.ready\s*=\s*true\b")
    here = [p - s for p in uses if s <= p < e]
    p_refresh = here[0] if len(here) == 1 else None
    found = {"load(player)": p_load, "the saved Cash write (cash.Value = ...)": p_cash, "updateIncome(player)": p_income,
             "the offline earnings (cash.Value += ...)": p_offline, "addEarnings(player, ...)": p_earnings, "data.ready = true": p_ready,
             "refreshSign(player) (exactly once)": p_refresh}
    absent = sorted(k for k, v in found.items() if v is None)
    add("claimGarage contains load, the saved Cash write, updateIncome, the offline earnings, addEarnings, data.ready = true and one refreshSign", not absent,
        "not found: %s. %s" % (absent, REVIEW_HINT))
    if not absent:
        add("claimGarage: the saved Cash is written after the save is read (load)", p_load < p_cash, REVIEW_HINT)
        add("claimGarage: refreshSign runs after the saved Cash is written", p_cash < p_refresh, REVIEW_HINT)
        add("claimGarage: refreshSign runs after the income is worked out (updateIncome)", p_income < p_refresh, REVIEW_HINT)
        add("claimGarage: refreshSign runs after the offline earnings are added to Cash", p_offline < p_refresh, REVIEW_HINT)
        add("claimGarage: refreshSign runs after the offline earnings are counted (addEarnings)", p_earnings < p_refresh, REVIEW_HINT)
        add("claimGarage: refreshSign runs before data.ready is set", p_refresh < p_ready, REVIEW_HINT)
        add("claimGarage: data.ready is not set before the saved Cash and the offline earnings are written", p_ready > p_cash and p_ready > p_offline, REVIEW_HINT)

    # a purchase: buyUpgrade asks checkUpgradePurchase, returns on a refusal, and only then calls refreshSign
    bs, be = function_span(spans, "buyUpgrade")
    buy = blank[bs:be]
    check, refuse, refresh = (re.search(p, buy) for p in (r"\bcheckUpgradePurchase\s*\(", r"\bif\s+not\s+i\s+then\s+return\b", r"\brefreshSign\s*\("))
    add("buyUpgrade asks checkUpgradePurchase and returns on a refusal before it calls refreshSign",
        bool(check and refuse and refresh) and check.start() < refuse.start() < refresh.start(), REVIEW_HINT)
    # overhaul 2: the ready test moved into checkBuyRequest (shared by every office purchase), which checkUpgradePurchase
    # calls before anything is checked against the catalog (OfficeConfig.checkItem)
    cs, ce = function_span(spans, "checkBuyRequest")
    cbody = blank[cs:ce]
    after_params = cbody[cbody.index(")"):]
    first_if = re.search(r"\bif\b", after_params)
    us, ue = function_span(spans, "checkUpgradePurchase")
    ubody = blank[us:ue]
    req, item = re.search(r"\bcheckBuyRequest\s*\(", ubody), re.search(r"\bOfficeConfig\.checkItem\s*\(", ubody)
    add("checkBuyRequest's first test is `if not data.ready then return`, and checkUpgradePurchase asks it before the catalog check (a purchase never publishes before the load is done)",
        bool(first_if) and re.match(r"if\s+not\s+data\.ready\s+then\s+return\b", after_params[first_if.start():]) is not None
        and bool(req and item) and req.start() < item.start(), REVIEW_HINT)

    # the IPO commit: only IpoServer's goPublic calls it, only onAction calls goPublic, and onAction refuses while not data.ready
    ipo = others.get("IpoServer.lua")
    if ipo is None:
        add("IpoServer.lua is there (the IPO commit's guard is checked on it)", False, REVIEW_HINT)
    else:
        ib = lua_views(ipo)[1]
        ispans = lua_functions(ib)[0]
        callers = []
        for fname, text in sorted(others.items()):
            tb = lua_views(text)[1]
            tspans = lua_functions(tb)[0]
            callers += ["%s:%s" % (fname, enclosing_function(tspans, m.start())) for m in re.finditer(r"\bcommitIpo\s*\(", tb)]
        add("the IPO commit is called from IpoServer's goPublic and from nowhere else", callers == ["IpoServer.lua:goPublic"], "%s. %s" % (callers, REVIEW_HINT))
        add("goPublic is used only by onAction", [enclosing_function(ispans, p) for p in identifier_uses(ib, "goPublic")] == ["onAction"], REVIEW_HINT)
        span = function_span(ispans, "onAction")
        act = ib[span[0]:span[1]] if span else ""
        guard, go = re.search(r"\bif\s+not\s+ipo\s+or\s+not\s+data\.ready\s+then\b", act), re.search(r"\bgoPublic\s*\(", act)
        add("IpoServer's onAction refuses while not data.ready before it reaches goPublic", bool(guard and go) and guard.start() < go.start(), REVIEW_HINT)

    # the client's end of it
    ck = lua_views(client_text)[0]
    attr = re.search(r"""\blocal\s+LOADED_ATTRIBUTE\s*=\s*(["'])(\w+)\1""", ck)
    # overhaul 2: UPGRADES is built from OfficeConfig.Items (publishUpgrades sets Upgrade1 .. Upgrade<items>)
    office = read("OfficeConfig.lua")
    count = len(re.findall(r'\{ key = "[^"]+", icon = ', office)) if "for _, item in ipairs(OfficeConfig.Items) do" in keep else 0
    number = re.fullmatch(r"Upgrade(\d+)", attr.group(2)) if attr else None
    add("IpoClient's LOADED_ATTRIBUTE is one of the attributes publishUpgrades sets (Upgrade1 to the last UPGRADES entry)",
        bool(number) and 1 <= int(number.group(1)) <= count, "%s, TycoonCore sets Upgrade1 .. Upgrade%d. %s" % (attr.group(2) if attr else None, count, REVIEW_HINT))
    wait = re.search(r"\blocal\s+MONEY_WAIT\s*=\s*([\d.]+)", ck)
    money_wait = float(wait.group(1)) if wait else 0
    add("IpoClient's safety delay MONEY_WAIT is at least %d s (OWNER DEFAULT)" % MIN_MONEY_WAIT, money_wait >= MIN_MONEY_WAIT, money_wait)
    tries = re.search(r"\blocal\s+LOAD_TRIES\s*=\s*(\d+)", keep)
    reread = re.search(r"\blocal\s+REREAD_WAIT_SECONDS\s*=\s*([\d.]+)", keep)
    ls, le = function_span(spans, "load")
    retry = re.search(r"\btask\.wait\s*\(\s*attempt\s*\*\s*2\s*\)", blank[ls:le])
    reread_wait = re.search(r"\btask\.wait\s*\(\s*REREAD_WAIT_SECONDS\s*\)", body)
    if tries and reread and retry and reread_wait:
        per_read = sum(2 * a for a in range(1, int(tries.group(1))))
        scripted = 2 * per_read + float(reread.group(1))
        add("IpoClient's MONEY_WAIT covers the worst join: the waits TycoonCore adds (two reads' retries + the re-read wait) + %d s for Roblox" % DATASTORE_ALLOWANCE,
            scripted + DATASTORE_ALLOWANCE <= money_wait,
            "MONEY_WAIT %g s; waits %g s (two reads x %g s of retries + the %g s re-read wait) + %d s. %s" % (money_wait, scripted, per_read, float(reread.group(1)), DATASTORE_ALLOWANCE, REVIEW_HINT))
    else:
        add("the waits TycoonCore adds to a join can be read (LOAD_TRIES, task.wait(attempt * 2) in load, REREAD_WAIT_SECONDS in claimGarage)", False, REVIEW_HINT)
    return out


def other_scripts():
    """{file name: text} for every script in the folder but TycoonCore.lua."""
    return {name: read(name) for name in sorted(os.listdir(ROOT)) if name.endswith(".lua") and name != "TycoonCore.lua"}


def build_program(client_text, goal_count, dump=False):
    ipo_config = read("IpoConfig.lua")
    shop_config = read("ShopConfig.lua")
    daily_config = read("DailyConfig.lua")
    prelude = (PRELUDE.replace("__IPOCONFIG__", ipo_config).replace("__SHOPCONFIG__", shop_config)
               .replace("__DAILYCONFIG__", daily_config).replace("__IPOCLIENT__", client_text)
               .replace("__TRAY__", marked_source("TRAY", "TaskClient.lua")))
    scenarios = (SCENARIOS.replace("__GOALCOUNT__", str(goal_count)).replace("__TOUCHES__", lua_touches())
                 .replace("__DUMP__", "true" if dump else "false"))
    return prelude + scenarios


def run_all(luau, client_text, goal_count, dump=False, core_text=None, others=None):
    """(passed, failed, failure lines, crashed text or None, raw stdout). core_text and others are TycoonCore.lua and the
    other scripts for the coupling checks (default: the files in the folder)."""
    result = run_luau(luau, build_program(client_text, goal_count, dump))
    out = result.stdout.strip().split("\n") if result.stdout.strip() else []
    fails = [line for line in out if line.startswith("FAIL: ")]
    summary = [line for line in out if re.match(r"^\d+ passed, \d+ failed$", line)]
    crashed = None
    if result.returncode != 0 or not summary:
        crashed = (result.stderr.strip() or result.stdout.strip() or "no output")[:600]
    passed = failed = 0
    if summary:
        m = re.match(r"^(\d+) passed, (\d+) failed$", summary[-1])
        passed, failed = int(m.group(1)), int(m.group(2))
    static = static_checks(client_text) + coupling_checks(read("TycoonCore.lua") if core_text is None else core_text, client_text,
                                                          other_scripts() if others is None else others)
    for name, ok, extra in static:
        if ok:
            passed += 1
        else:
            failed += 1
            fails.append("FAIL: " + name + ((" -- " + str(extra)) if extra is not None else ""))
    return passed, failed, fails, crashed, out


# --- mutation runs: break IpoClient.lua on purpose; every break must be caught by a named check ---------------------
MUTATIONS = [
    ("wrong format: Cash without thousands commas", 'return ShopConfig.formatCash(amount)\n\telseif tier == 2', 'return "$" .. amount\n\telseif tier == 2'),
    ("wrong format: Income shown without its /s", '(tier < 3 and "/s" or "")', '""'),
    ("wrong format: the Income sign + dropped", 'table.insert(parts, "+" .. moneyText(income, tier, 10000)', 'table.insert(parts, moneyText(income, tier, 10000)'),
    ("wrong format: short form uses the wrong function (no K, M)", 'return shortAmount(amount)\nend\n\n-- "$4,630', 'return ShopConfig.formatCash(amount)\nend\n\n-- "$4,630'),
    ("Cash and Income swapped in the read", 'return read("Cash"), read("Income")', 'return read("Income"), read("Cash")'),
    ("Cash and Income swapped in the text (Income first)", '''		if cash then
			table.insert(parts, moneyText(cash, tier, 100000))
		end
		if income then
			table.insert(parts, "+" .. moneyText(income, tier, 10000) .. (tier < 3 and "/s" or ""))
		end''', '''		if income then
			table.insert(parts, "+" .. moneyText(income, tier, 10000) .. (tier < 3 and "/s" or ""))
		end
		if cash then
			table.insert(parts, moneyText(cash, tier, 100000))
		end'''),
    ("the progress bar is inverted", 'hudFill.Size = UDim2.fromScale(info.progress, 1)', 'hudFill.Size = UDim2.fromScale(1 - info.progress, 1)'),
    ("the progress track is thinner", 'Size = UDim2.new(1, -20, 0, 12),\n\tBackgroundColor3 = COLORS.bar,', 'Size = UDim2.new(1, -20, 0, 6),\n\tBackgroundColor3 = COLORS.bar,'),
    ("the progress track moved down", 'Position = UDim2.fromOffset(10, 26),\n\tSize = UDim2.new(1, -20, 0, 12),', 'Position = UDim2.fromOffset(10, 30),\n\tSize = UDim2.new(1, -20, 0, 12),'),
    ("a polling loop added (while true, 0.1 s)", '-- Cash and Income on the bar: listens to leaderstats, no loop\nbindMoney()', '-- Cash and Income on the bar: listens to leaderstats, no loop\nbindMoney()\ntask.spawn(function()\n\twhile true do\n\t\ttask.wait(0.1)\n\t\trequestMoney()\n\tend\nend)'),
    ("a polling loop added on every frame (Heartbeat)", '-- Cash and Income on the bar: listens to leaderstats, no loop\nbindMoney()', '-- Cash and Income on the bar: listens to leaderstats, no loop\nbindMoney()\ngame:GetService("RunService").Heartbeat:Connect(function() drawMoney() end)'),
    ("text min 8 (top row sizes 16 and 8)", 'local MONEY_SIZES = { 16, 14 }', 'local MONEY_SIZES = { 16, 8 }'),
    ("text min 8 (bottom row size 8)", 'local INFO_SIZE = 14', 'local INFO_SIZE = 8'),
    ("the top row is scaled text with min 8", 'TextSize = MONEY_SIZES[1],\n\tTextTruncate', 'TextSize = MONEY_SIZES[1],\n\tTextScaled = true,\n\tTextTruncate'),
    ("row overlap: the top row sits on the progress bar", 'Position = UDim2.fromOffset(10, 2),', 'Position = UDim2.fromOffset(10, 20),'),
    ("row overlap: the bottom row sits on the progress bar", 'Position = UDim2.fromOffset(10, 40),\n\tSize = UDim2.new(1, -BAR_PADDING, 0, 20),', 'Position = UDim2.fromOffset(10, 30),\n\tSize = UDim2.new(1, -BAR_PADDING, 0, 20),'),
    ("the bottom row falls out of the bar", 'Position = UDim2.fromOffset(10, 40),\n\tSize = UDim2.new(1, -BAR_PADDING, 0, 20),', 'Position = UDim2.fromOffset(10, 52),\n\tSize = UDim2.new(1, -BAR_PADDING, 0, 20),'),
    ("nil not handled: a missing Cash value is read without a check", 'return moneyValue(value and value:IsA("ValueBase") and value.Value)', 'return moneyValue(value.Value)'),
    ("nil not handled: NaN is let through", 'if type(value) ~= "number" or value ~= value then', 'if type(value) ~= "number" then'),
    ("nil not handled: a missing leaderstats still draws $0", 'hudMoney.Text = "" -- no leaderstats (yet): the top row stays empty\n\t\treturn', 'hudMoney.Text = "$0"\n\t\treturn'),
    ("negative not clamped", 'return math.clamp(math.floor(value), 0, MONEY_CAP)', 'return math.clamp(math.floor(value), -MONEY_CAP, MONEY_CAP)'),
    ("no cap: a huge number overflows", 'local MONEY_CAP = 999e12', 'local MONEY_CAP = 1e300'),
    ("event not disconnected", '\tfor _, connection in ipairs(moneyConnections) do\n\t\tconnection:Disconnect()\n\tend\n', ''),
    ("rate limit removed", 'local MONEY_INTERVAL = 0.25', 'local MONEY_INTERVAL = 0'),
    ("rate limit loses the last value", '''		moneyPending = true
		task.delay(wait, function()
			moneyPending = false
			drawMoney()
		end)''', '''		moneyPending = true
		task.delay(wait, function()
			moneyPending = false
		end)'''),
    ("the fitting is off: always the fullest text at 16", 'local function pickText(texts, sizes, room)\n', 'local function pickText(texts, sizes, room)\n\tif true then return texts[1], sizes[1] end\n'),
    ("the measure always says 0 wide", 'return ok and bounds.X or #text * size * 0.6', 'return 0'),
    ("the room is the whole bar (no padding taken off)", 'return hudBar.Size.X.Offset - BAR_PADDING', 'return hudBar.Size.X.Offset'),
    ("the bottom row is not fitted", 'hudInfo.Text = pickText(infoTexts(info), { INFO_SIZE }, barRoom())', 'hudInfo.Text = infoTexts(info)[1]'),
    ("a resize does not refit the rows", '\tplaceHud()\n\trefreshHud() -- the bar may have a new width: its rows fit again\n\trequestMoney()\n', '\tplaceHud()\n'),
    ("a leaderstats that comes late is not noticed", '''player.ChildAdded:Connect(function(child)
	if child.Name == "leaderstats" then
		bindMoney()
	end
end)''', ''),
    ("a leaderstats that goes away is not noticed", '''player.ChildRemoved:Connect(function(child)
	if child.Name == "leaderstats" then
		bindMoney()
	end
end)''', ''),
    ("a Cash added to the folder later is not noticed", 'table.insert(moneyConnections, stats.ChildAdded:Connect(bindMoney))', ''),
    ("the bar is taller (the daily chip and Goals card would move)", 'hudBar.Size = UDim2.fromOffset(math.clamp(gui.AbsoluteSize.X - 108 - CHIP_ROOM, 150, 250), 64)', 'hudBar.Size = UDim2.fromOffset(math.clamp(gui.AbsoluteSize.X - 108 - CHIP_ROOM, 150, 250), 78)'),
    ("the bar forgets the room for the daily chip", 'local CHIP_ROOM = DailyConfig and DailyConfig.Enabled and (DailyConfig.ChipSize + DailyConfig.ChipGap) or 0', 'local CHIP_ROOM = 0'),
    ("the IPO button moves onto the POACH slot", 'local HUD_SLOT = 4', 'local HUD_SLOT = 3'),
    ("the bar ignores attribute changes (progress frozen)", 'player.AttributeChanged:Connect(refreshAll)', ''),
    ("the client writes to leaderstats", 'return moneyValue(value and value:IsA("ValueBase") and value.Value)', 'if value and value:IsA("ValueBase") then value.Value = value.Value end\n\t\treturn moneyValue(value and value:IsA("ValueBase") and value.Value)'),
    ("a Touched handler on the bar", '-- Cash and Income on the bar: listens to leaderstats, no loop\nbindMoney()', '-- Cash and Income on the bar: listens to leaderstats, no loop\nbindMoney()\nhudBar.Touched:Connect(function() end)'),
    ("the bar is narrower on short screens", 'hudBar.Size = UDim2.fromOffset(width, 64)', 'hudBar.Size = UDim2.fromOffset(width - 20, 64)'),
    ("the bar moved down", 'hudBar.Position = UDim2.fromOffset(98, 12)', 'hudBar.Position = UDim2.fromOffset(98, 20)'),
    ("an emoji in the top row", 'table.insert(texts, table.concat(parts, tier < 3 and " · " or " "))', 'table.insert(texts, "💰 " .. table.concat(parts, tier < 3 and " · " or " "))'),
    ("odds wording in a bar text", '"🔔 IPO!" }', '"🔔 Lucky IPO!" }'),
    ("a new remote call at start", '-- Cash and Income on the bar: listens to leaderstats, no loop\nbindMoney()', '-- Cash and Income on the bar: listens to leaderstats, no loop\nbindMoney()\nipoAction:InvokeServer("Cash")'),
    ("the top row has no truncate safety net", 'TextSize = MONEY_SIZES[1],\n\tTextTruncate = Enum.TextTruncate.AtEnd,\n', 'TextSize = MONEY_SIZES[1],\n'),
    # the loading rule (the top row stays empty until the server says the save is loaded)
    ("loading: the row is shown as soon as leaderstats are found (no rule)", '\tmoneyStats = stats\n\tmoneyShown = false\n', '\tmoneyStats = stats\n\tmoneyShown = true\n'),
    ("loading: the first change above 0 shows the row", 'table.insert(moneyConnections, value.Changed:Connect(requestMoney))', 'table.insert(moneyConnections, value.Changed:Connect(function()\n\t\t\t\t\tif value.Value > 0 then\n\t\t\t\t\t\tshowMoney()\n\t\t\t\t\tend\n\t\t\t\t\trequestMoney()\n\t\t\t\tend))'),
    ("loading: any change (also to 0) shows the row", 'table.insert(moneyConnections, value.Changed:Connect(requestMoney))', 'table.insert(moneyConnections, value.Changed:Connect(function()\n\t\t\t\t\tshowMoney()\n\t\t\t\t\trequestMoney()\n\t\t\t\tend))'),
    ("loading: the server's signal is not listened to", 'player:GetAttributeChangedSignal(LOADED_ATTRIBUTE):Connect(function()', 'player:GetAttributeChangedSignal("NotTheSignal"):Connect(function()'),
    ("loading: the signal is IpoCount (set before the income)", 'local LOADED_ATTRIBUTE = "Upgrade1"', 'local LOADED_ATTRIBUTE = "IpoCount"'),
    ("loading: no fallback wait (the row never shows if the signal never comes)", 'moneyWait = task.delay(MONEY_WAIT, function()\n\t\t\tmoneyWait = nil\n\t\t\tshowMoney()\n\t\tend)', 'moneyWait = nil'),
    ("loading: the fallback wait is 10 s", 'local MONEY_WAIT = 30', 'local MONEY_WAIT = 10'),
    ("loading: the wait is not cancelled when the row is shown", 'local function showMoney()\n\tcancelMoneyWait()\n', 'local function showMoney()\n'),
    ("loading: the wait is not cancelled when the bar rebinds", 'moneyShown = false\n\tcancelMoneyWait()\n\tif not stats then', 'moneyShown = false\n\tif not stats then'),
    ("loading: a Changed event starts the wait again", 'table.insert(moneyConnections, value.Changed:Connect(requestMoney))', 'table.insert(moneyConnections, value.Changed:Connect(function()\n\t\t\t\t\tif moneyWait then\n\t\t\t\t\t\tcancelMoneyWait()\n\t\t\t\t\t\tmoneyWait = task.delay(MONEY_WAIT, function()\n\t\t\t\t\t\t\tmoneyWait = nil\n\t\t\t\t\t\t\tshowMoney()\n\t\t\t\t\t\tend)\n\t\t\t\t\tend\n\t\t\t\t\trequestMoney()\n\t\t\t\tend))'),
    ("loading: Cash or Income coming into the same folder restarts the rule", 'if stats == moneyStats then\n\t\treturn\n\tend\n\tmoneyStats = stats', 'moneyStats = stats'),
    ("loading: a new leaderstats does not hide the row again", 'moneyStats = stats\n\tmoneyShown = false\n', 'moneyStats = stats\n'),
    ("loading: a new leaderstats waits even when the server is done", 'if player:GetAttribute(LOADED_ATTRIBUTE) ~= nil then\n\t\tmoneyShown = true -- bindMoney draws it', 'if false then\n\t\tmoneyShown = true -- bindMoney draws it'),
    ("loading: a Cash of 0 hides the row (an IPO reset and a new player never see $0)", 'if not moneyShown then\n\t\thudMoney.Text = "" -- the save is still loading', 'if not moneyShown or (readMoney()) == 0 then\n\t\thudMoney.Text = "" -- the save is still loading'),
    ("loading: the row is shown at the signal but not drawn (waits for the next change)", 'if not moneyShown then\n\t\tmoneyShown = true\n\t\tdrawMoney()\n\tend', 'if not moneyShown then\n\t\tmoneyShown = true\n\tend'),
    ("loading: a signal listener added on every rebind (leak)", 'restartMoneyRule(stats)\n\tif stats then', 'restartMoneyRule(stats)\n\tplayer:GetAttributeChangedSignal(LOADED_ATTRIBUTE):Connect(function() end)\n\tif stats then'),
    ("loading: a polling loop waits for the signal", 'moneyWait = task.delay(MONEY_WAIT, function()', 'task.spawn(function()\n\t\t\twhile player:GetAttribute(LOADED_ATTRIBUTE) == nil do\n\t\t\t\ttask.wait(0.5)\n\t\t\tend\n\t\t\tshowMoney()\n\t\tend)\n\t\tmoneyWait = task.delay(MONEY_WAIT, function()'),
    # rounding of the shortest form and the $1000K guard
    ("rounding: the shortest form rounds down again", 'local whole = math.floor(amount / unit[1] + 0.5)', 'local whole = math.floor(amount / unit[1])'),
    ("rounding: the shortest form rounds .5 down", 'local whole = math.floor(amount / unit[1] + 0.5)', 'local whole = math.floor(amount / unit[1] + 0.4)'),
    ("rounding: the shortest form says $1000K", 'if whole >= 1000 and units[i + 1] then', 'if false then'),
    ("rounding: the shortest form promotes to the wrong unit", 'return "$1" .. units[i + 1][2]', 'return "$1" .. unit[2]'),
    ("rounding: the guard is gone (the bar says $1000K)", 'if unit then\n\t\treturn "$1" .. promoted[unit]', 'if false then\n\t\treturn "$1" .. promoted[unit]'),
    ("rounding: the guard promotes to the wrong unit", 'local promoted = { K = "M", M = "B", B = "T" }', 'local promoted = { K = "M", M = "M", B = "T" }'),
    ("rounding: the bottom row is not guarded", 'local now = shortAmount(moneyValue(valuation()) or 0)', 'local now = IpoConfig.formatShort(moneyValue(valuation()) or 0)'),
]


# --- mutation runs on the coupling: break TycoonCore, IpoServer or IpoClient on purpose; each break must be caught by a
# NAMED coupling check (never by a crash), and harmless edits (comments, strings, indentation) must stay green ----------
READY_LINE = "\tdata.ready = true -- the shop waits for this before granting purchases\n"
REFRESH_THEN_READY = "\trefreshSign(player)\n" + READY_LINE
BEFORE_SETUP = "\tlocal lastSeen = nil\n\tlocal setupOk, setupError = pcall(function()\n"
BEFORE_OFFLINE = "\t-- Offline earnings: the startup keeps making money while you're away\n\tif lastSeen then\n"
AFTER_PLAYERDATA = "\tplayerData[player] = data\n\n\tlocal floor = "
AFTER_LEADERSTATS = "\tincome.Name = \"Income\"\n\tincome.Parent = leaderstats\n"
READY_GUARD = "\tif not data.ready then\n\t\treturn nil, \"Still loading, try again in a moment\" -- loading, or an IPO is being saved\n\tend\n"
BUY_CHECK = "\tlocal i, reason = checkUpgradePurchase(UPGRADES, data, data.cash.Value, id, os.clock())\n"
CORE, CLIENT_FILE, IPO_SERVER = "TycoonCore.lua", "IpoClient.lua", "IpoServer.lua"

# (name, file, [(old, new), ...]): each old must be in the file exactly once
COUPLING_MUTATIONS = [
    ("refreshSign moved before the saved Cash is written", CORE, [(REFRESH_THEN_READY, READY_LINE), (BEFORE_SETUP, "\trefreshSign(player)\n" + BEFORE_SETUP)]),
    ("refreshSign moved before the offline earnings", CORE, [(REFRESH_THEN_READY, READY_LINE), (BEFORE_OFFLINE, "\trefreshSign(player)\n" + BEFORE_OFFLINE)]),
    ("refreshSign moved after data.ready", CORE, [(REFRESH_THEN_READY, READY_LINE + "\trefreshSign(player)\n")]),
    ("a new refreshSign call at player join, before the load", CORE, [(AFTER_PLAYERDATA, "\trefreshSign(player)\n\n\tlocal floor = ")]),
    ("the Upgrade1 attribute set when leaderstats are created", CORE, [(AFTER_LEADERSTATS, AFTER_LEADERSTATS + "\tplayer:SetAttribute(\"Upgrade1\", false)\n")]),
    ("the Upgrade attribute built by concatenation at join", CORE, [(AFTER_LEADERSTATS, AFTER_LEADERSTATS + "\tplayer:SetAttribute(\"Upgrade\" .. 1, false)\n")]),
    ("refreshSign removed from the load path", CORE, [(REFRESH_THEN_READY, READY_LINE)]),
    ("publishUpgrades called directly before the saved Cash is written", CORE, [(BEFORE_SETUP, "\tpublishUpgrades(player)\n" + BEFORE_SETUP)]),
    ("publishUpgrades called directly before the offline earnings", CORE, [(BEFORE_OFFLINE, "\tpublishUpgrades(player)\n" + BEFORE_OFFLINE)]),
    ("publishUpgrades called directly after data.ready", CORE, [(REFRESH_THEN_READY, REFRESH_THEN_READY + "\tpublishUpgrades(player)\n")]),
    ("data.ready set at the start of the join, before the saved Cash", CORE, [(AFTER_PLAYERDATA, "\tdata.ready = true\n\n\tlocal floor = ")]),
    ("refreshSign called from the PlayerRemoving handler", CORE, [("\tsaveOnLeave(player)\n\tif data then\n", "\tsaveOnLeave(player)\n\trefreshSign(player)\n\tif data then\n")]),
    ("leaderstats made at the join (lobby L3: before the claim)", CORE, [("\tinPlaza[player] = true\n", "\tinPlaza[player] = true\n\tlocal early = Instance.new(\"Folder\")\n\tearly.Name = \"leaderstats\"\n\tearly.Parent = player\n")]),
    ("refreshSign called from the income loop", CORE, [("\t\t\t\tsyncRoom(data)\n", "\t\t\t\tsyncRoom(data)\n\t\t\t\trefreshSign(player)\n")]),
    ("refreshSign handed to a module through core", CORE, [("OnboardingServer.init({\n", "OnboardingServer.init({\n\trefreshSign = refreshSign,\n")]),
    ("checkUpgradePurchase's data.ready guard removed (a purchase could publish before the load)", CORE, [(READY_GUARD, "")]),
    ("buyUpgrade calls refreshSign before it asks checkUpgradePurchase", CORE, [(BUY_CHECK, "\trefreshSign(player)\n" + BUY_CHECK)]),
    ("the server waits 30 s for the second read (longer than the client's delay)", CORE, [("local REREAD_WAIT_SECONDS = 7\n", "local REREAD_WAIT_SECONDS = 30\n")]),
    ("the server tries the read 5 times instead of 3", CORE, [("local LOAD_TRIES = 3 --", "local LOAD_TRIES = 5 --")]),
    ("another script sets Upgrade1 (IpoServer.setupPlayer)", IPO_SERVER, [("function IpoServer.setupPlayer(player, data, savedIpo, legacyValuation)\n", "function IpoServer.setupPlayer(player, data, savedIpo, legacyValuation)\n\tplayer:SetAttribute(\"Upgrade1\", false)\n")]),
    ("IpoServer's onAction no longer refuses while not data.ready", IPO_SERVER, [("if not ipo or not data.ready then", "if not ipo then")]),
    ("goPublic (the IPO commit) called from a second place in IpoServer", IPO_SERVER, [("\tipo.shares -= cost\n\tipo.perks[perk.key] = level + 1\n", "\tgoPublic(player, ipo.count + 1)\n\tipo.shares -= cost\n\tipo.perks[perk.key] = level + 1\n")]),
    ("IpoClient waits for a different attribute (IpoCount)", CLIENT_FILE, [('local LOADED_ATTRIBUTE = "Upgrade1"', 'local LOADED_ATTRIBUTE = "IpoCount"')]),
    ("IpoClient waits for an Upgrade attribute the server never sets (Upgrade99: overhaul 2 has 63 items)", CLIENT_FILE, [('local LOADED_ATTRIBUTE = "Upgrade1"', 'local LOADED_ATTRIBUTE = "Upgrade99"')]),
    ("IpoClient's 30 s safety delay changed to 3 s", CLIENT_FILE, [("local MONEY_WAIT = 30", "local MONEY_WAIT = 3")]),
    ("IpoClient's 30 s safety delay changed to 25 s", CLIENT_FILE, [("local MONEY_WAIT = 30", "local MONEY_WAIT = 25")]),
]

# Harmless edits: every coupling check must stay green. (name, function from the TycoonCore text to the new text)
COUPLING_CONTROLS = [
    ("comments, a block comment and a string that all mention refreshSign, data.ready and Upgrade1, before the Cash write", lambda t: t.replace(
        BEFORE_SETUP, "\t-- refreshSign(player) data.ready = true cash.Value = 0 player:SetAttribute(\"Upgrade1\", true)\n\t--[[ refreshSign(player)\n\tdata.ready = true ]]\n"
        "\tlocal note = \"refreshSign(player) end data.ready = true player:SetAttribute('Upgrade1', true)\"\n" + BEFORE_SETUP)),
    ("two spaces instead of a tab on every line, and an empty line after every line", lambda t: t.replace("\t", "  ").replace("\n", "\n\n")),
    ("spaces inside the calls: refreshSign (player) and a spaced declaration", lambda t: t.replace("refreshSign(player)", "refreshSign (player)").replace("local function refreshSign(player)", "local function  refreshSign  (player)")),
]


def coupling_mutation_runs(client_text, detail=False):
    """Run COUPLING_MUTATIONS and COUPLING_CONTROLS. Returns the exit code part (0 or 1)."""
    code = 0
    texts = dict(other_scripts())
    texts[CORE] = read(CORE)
    texts[CLIENT_FILE] = client_text

    def checks(files):
        """The coupling checks on a set of files: TycoonCore, IpoClient and the other scripts."""
        return coupling_checks(files[CORE], files[CLIENT_FILE], {k: v for k, v in files.items() if k not in (CORE, CLIENT_FILE)})

    caught = 0
    for name, target, pairs in COUPLING_MUTATIONS:
        mutated = dict(texts)
        applied = True
        for old, new in pairs:
            if mutated[target].count(old) != 1:
                print("MUTATION NOT APPLIED (%d matches in %s): %s" % (mutated[target].count(old), target, name))
                applied = False
                code = 1
                break
            mutated[target] = mutated[target].replace(old, new)
        if not applied:
            continue
        try:
            result = checks(mutated)
        except Exception as error:  # a crash is never a catch
            print("MUTATION CRASHED (not a named check): %s: %r" % (name, error))
            code = 1
            continue
        failed = [n for n, ok, x in result if not ok]
        if not failed:
            print("MUTATION NOT CAUGHT: " + name)
            code = 1
            continue
        caught += 1
        print("caught: %s\n        by: %s%s" % (name, failed[0], " (+%d more)" % (len(failed) - 1) if len(failed) > 1 else ""))
        if detail:
            for n in failed[1:]:
                print("            %s" % n)
    print("Coupling mutations: %d of %d broken rules caught by a named check" % (caught, len(COUPLING_MUTATIONS)))
    if caught != len(COUPLING_MUTATIONS):
        code = 1
    green = 0
    for name, edit in COUPLING_CONTROLS:
        edited = dict(texts)
        edited[CORE] = edit(texts[CORE])
        if edited[CORE] == texts[CORE]:
            print("CONTROL NOT APPLIED: " + name)
            code = 1
            continue
        try:
            result = checks(edited)
        except Exception as error:
            print("CONTROL CRASHED: %s: %r" % (name, error))
            code = 1
            continue
        failed = [n for n, ok, x in result if not ok]
        if failed:
            print("CONTROL TURNED RED (a harmless edit must not): %s\n        by: %s" % (name, failed[0]))
            code = 1
        else:
            green += 1
            print("green: " + name)
    print("Coupling controls: %d of %d harmless edits kept every check green" % (green, len(COUPLING_CONTROLS)))
    if green != len(COUPLING_CONTROLS):
        code = 1
    return code


# --- the "Claim garage" button (ClaimButtonClient.lua, ux lane) -----------------------------------------------------
# tools/claim_button_test.luau runs the REAL ClaimButtonClient.lua in a fake client (the prompts Roblox shows, the
# player's Garage attribute, OpenPanel, a virtual clock for the hold) and its CLAIMBUTTON layout at seven screen sizes
# with three top bars. Then each break below must fail its named check; a client that errored never counts.
CLAIM_CLIENT = "ClaimButtonClient.lua"
CLAIM_TEST = os.path.join("tools", "claim_button_test.luau")
CLAIM_CLEAN = "client: ran without an error"
CLAIM_DONE = "claim button: the program ran to the end"


def claim_checks(luau, client_text=None):
    """[(name, ok, extra)] of the real ClaimButtonClient.lua in the fake client."""
    client = client_text if client_text is not None else read(CLAIM_CLIENT)
    start = client.find("-- CLAIMBUTTON-START")
    end = client.find("-- CLAIMBUTTON-END")
    layout = client[start:end] if 0 <= start < end else "local function buttonLayout() return { x = -1, y = -1, w = 0, h = 0 } end\n"
    head = ("local LOBBY_SOURCE = function()\n" + read("LobbyConfig.lua") + "\nend\n"
            "local CLIENT = function(game, Instance, require, UDim2, UDim, Color3, Enum, task)\n" + client + "\nend\n"
            "local LAYOUT = function()\n" + layout + "\nreturn buttonLayout\nend\n")
    body = read(CLAIM_TEST)
    at = body.index("local function world(")
    result = run_luau(luau, body[:at] + head + body[at:])
    out = []
    for line in result.stdout.splitlines():
        if line.startswith("FAIL: "):
            name, _, extra = line[len("FAIL: "):].partition(" -- ")
            out.append((name, False, extra or None))
    m = re.search(r"(\d+) passed, (\d+) failed", result.stdout)
    out += [("claim button", True, None)] * (int(m.group(1)) if m else 0)
    if result.returncode != 0 or "DONE" not in result.stdout.splitlines():
        out.append((CLAIM_DONE + " (it crashed: a crash is never a catch)", False, (result.stderr or result.stdout)[-300:]))
    return out


def claim_static_checks(text):
    code = code_only(text)
    return [
        ("claim button static: it fires no remote (no FireServer, InvokeServer or RemoteEvent)",
         all(w not in code for w in ("FireServer", "InvokeServer", "RemoteEvent", "RemoteFunction")), None),
        ("claim button static: it has no Touched handler and no input of its own besides the button (only the server's prompt claims)",
         "Touched" not in code and "UserInputService" not in code, None),
        ("claim button static: it stops at once with LobbyConfig.ClaimEnabled off, before building anything",
         code.find("if not LobbyConfig.ClaimEnabled then") >= 0 and code.find("if not LobbyConfig.ClaimEnabled then") < code.find("make(\"ScreenGui\""), None),
    ]


CLAIM_MUTANTS = [
    ("the button built with the claim off", "if not LobbyConfig.ClaimEnabled then\n\treturn -- the claim is off", "if false then\n\treturn -- the claim is off",
     "client: with the claim off"),
    ("a keyboard prompt shows the button too", "if inputType == Enum.ProximityPromptInputType.Touch and isClaimPrompt(prompt) then",
     "if isClaimPrompt(prompt) then", "client: a claim prompt shown for keyboard"),
    ("any prompt counts as a claim prompt", "return post ~= nil and post.Name == \"ClaimPost\" and post.Parent ~= nil and post.Parent.Name == \"ClaimSpot\"",
     "return post ~= nil", "client: another prompt (the VIP door)"),
    ("a ClaimPost outside a ClaimSpot counts", "return post ~= nil and post.Name == \"ClaimPost\" and post.Parent ~= nil and post.Parent.Name == \"ClaimSpot\"",
     "return post ~= nil and post.Name == \"ClaimPost\"", "client: a ClaimPost outside a ClaimSpot"),
    ("the button stays while a window is open", " and playerGui:GetAttribute(\"OpenPanel\") == nil\n", "\n", "client: a window open hides"),
    ("the button stays with a garage", "local show = prompt ~= nil and player:GetAttribute(\"Garage\") == 0 and",
     "local show = prompt ~= nil and", "client: with a garage the button goes"),
    ("a tap with a garage still presses", "if pressing or not prompt or player:GetAttribute(\"Garage\") ~= 0 then return end",
     "if pressing or not prompt then return end", "client: with a garage a tap presses nothing"),
    ("a second tap presses again", "if pressing or not prompt or", "if not prompt or", "client: a second tap while holding"),
    ("the hold is shorter than the prompt's hold time", "task.delay(prompt.HoldDuration + 0.15, function()", "task.delay(0.1, function()",
     "client: it does not let go before"),
    ("the hold never ends", "\t\tpcall(function()\n\t\t\tprompt:InputHoldEnd()\n\t\tend)\n", "", "client: then it lets go"),
    ("the shown prompt hidden keeps the button", "\tif shownPrompts[prompt] then\n\t\tshownPrompts[prompt] = nil", "\tif false then\n\t\tshownPrompts[prompt] = nil",
     "client: the shown prompt hidden"),
    ("any prompt hiding hides the button", "\tif shownPrompts[prompt] then\n\t\tshownPrompts[prompt] = nil", "\tif true then\n\t\ttable.clear(shownPrompts)",
     "client: another prompt hiding leaves"),
    ("the garage line not updated", "\t\tsubtitle.Text = prompt.ObjectText\n", "", "client: a claim prompt shown for touch"),
    # two prompts at once (quality's follow-up on PR #35)
    ("one slot again: a new prompt forgets the others", "\t\tshownCount += 1\n", "\t\tshownCount += 1\n\t\ttable.clear(shownPrompts)\n",
     "client: two prompts: the newer one hiding first"),
    ("the newest wins over the nearest", "local d = (from and entry.pos) and distance(from, entry.pos) or math.huge", "local d = math.huge",
     "client: two prompts: the button names the nearest"),
    ("the farthest wins", "if d < bestDist or (d == bestDist", "if d > bestDist or bestKey == nil or (d == bestDist",
     "client: two prompts: the button names the nearest"),
    ("the oldest wins a tie", "(d == bestDist and entry.order > bestOrder)", "(d == bestDist and entry.order < bestOrder)",
     "client: two prompts with no character: the button names the newest"),
    ("no new look while walking", "\t\trefresh()\n\t\trecheck()\n\tend\nend)", "\t\trefresh()\n\tend\nend)",
     "client: two prompts: walking to the other garage"),
    ("the looks never stop", "if rechecking or count < 2 then return end", "if rechecking then return end",
     "client: two prompts: no look is left pending"),
    ("a prompt gone from its post is never forgotten", "\t\telse\n\t\t\tshownPrompts[prompt] = nil\n\t\tend", "\t\tend",
     "client: two prompts: and the looks stop"),
    ("the busy text never shows", "title.Text = pressing and PRESSING_TEXT or LobbyConfig.Texts.Prompt", "title.Text = LobbyConfig.Texts.Prompt",
     "client: while pressing"),
    ("the button never moves with the screen", "gui:GetPropertyChangedSignal(\"AbsoluteSize\"):Connect(place)\n", "", "client: a new screen size"),
    ("short screens: the button down in the Shop's pop-up lane", "local SHORT_BOTTOM = 72", "local SHORT_BOTTOM = 40",
     "layout: clear of the Shop's pop-up lane"),
    ("short screens: the button over the thumbstick", "left, right, bottom = THUMBSTICK_RIGHT + 8,", "left, right, bottom = 100,",
     "layout: clear of the thumbstick"),
    ("tall screens: the button down on the thumbstick", "local TALL_BOTTOM = 176", "local TALL_BOTTOM = 120", "layout: clear of the thumbstick"),
    ("a small button (40 high)", "local BUTTON_HEIGHT = 60", "local BUTTON_HEIGHT = 40", "layout: the button is a big touch target"),
    ("the gui wiped on respawn", "\tResetOnSpawn = false,\n\tDisplayOrder = 0,", "\tResetOnSpawn = true,\n\tDisplayOrder = 0,",
     "client: the button's gui is kept on respawn"),
    ("the client makes a remote", "local player = Players.LocalPlayer\n", "local player = Players.LocalPlayer\nInstance.new(\"RemoteEvent\")\n",
     "client: it makes no remote"),
]
# Must be reported as NOT caught: the client errors on every tap, so checks about the tap fail too, but an error is
# never a catch (its "ran without an error" check fails).
CLAIM_SELF_TEST = ("a client that errors on every tap", "\tlocal prompt = nearestPrompt()\n\tif pressing", "\terror(\"crash (test)\")\n\tlocal prompt = nearestPrompt()\n\tif pressing",
                   "client: the tap presses")


def claim_mutant(luau, source, old, new, want):
    """(caught, why) for one mutant of ClaimButtonClient.lua."""
    if source.count(old) != 1:
        return False, "not applied (%d matches)" % source.count(old)
    failed = [n for n, ok, _ in claim_checks(luau, source.replace(old, new)) if not ok]
    if any(n.startswith(CLAIM_CLEAN) or n.startswith(CLAIM_DONE) for n in failed):
        return False, "the client errored: an error is never a catch"
    if any(n.startswith(want) for n in failed):
        return True, None
    return False, "no failing check starts with \"%s\" (failed: %s)" % (want, failed[:3])


def claim_main(luau, mutations=True):
    """Runs the claim button's checks and mutants; returns 0 or 1."""
    code = 0
    source = read(CLAIM_CLIENT)
    results = claim_checks(luau) + claim_static_checks(source)
    bad = [(n, e) for n, ok, e in results if not ok]
    for n, e in bad:
        print("FAIL: " + n + (" -- " + str(e) if e is not None else ""))
    print("Claim garage button (ClaimButtonClient) in a fake client: %d passed, %d failed" % (len(results) - len(bad), len(bad)))
    if bad:
        code = 1
    if not mutations:
        return code
    caught = 0
    for label, old, new, want in CLAIM_MUTANTS:
        ok, why = claim_mutant(luau, source, old, new, want)
        if ok:
            caught += 1
        else:
            print("NOT CAUGHT: %s -- %s" % (label, why))
    print("Claim button mutations: %d of %d caught, each by its named check (never by an error)" % (caught, len(CLAIM_MUTANTS)))
    if caught != len(CLAIM_MUTANTS):
        code = 1
    label, old, new, want = CLAIM_SELF_TEST
    self_ok, why = claim_mutant(luau, source, old, new, want)
    good = (not self_ok) and why is not None and "errored" in why
    print("Claim button harness self-test (a client that errors never counts): %d of 1 reported as not caught" % (1 if good else 0))
    if not good:
        print("FAIL: the claim button harness counted an erroring client as caught (%s)" % why)
        code = 1
    return code


# --- the Goals card (OnboardingClient.lua, ux lane; request U1 of the gameplay lane, the goal chain) ----------------
# tools/onboarding_client_test.luau runs the REAL OnboardingClient.lua in a fake client: the server's goal attributes
# (OnboardingGoal_, OnboardingGoalTarget_, OnboardingGoalShown_), OnboardingTracker, OpenPanel, a virtual clock for the
# "All goals done!" moment, with ChainEnabled off (Goals) and on (Chain). Then each break below must fail its named
# check; a client that errored never counts.
GOALS_CLIENT = "OnboardingClient.lua"
GOALS_TEST = os.path.join("tools", "onboarding_client_test.luau")
GOALS_CLEAN = "client: ran without an error"
GOALS_DONE = "goals card: the program ran to the end"


def goals_card_checks(luau, client_text=None):
    """[(name, ok, extra)] of the real OnboardingClient.lua's Goals card in the fake client."""
    client = client_text if client_text is not None else read(GOALS_CLIENT)
    head = ("local warn = function() end\n"
            "local CONFIG_SOURCE = function()\n" + read("OnboardingConfig.lua") + "\nend\n"
            "local CLIENT = function(game, Instance, require, UDim2, UDim, Color3, Enum, task, workspace, Vector3, Vector2,"
            " ColorSequence, NumberSequence, warn)\n" + client + "\nend\n")
    body = read(GOALS_TEST)
    at = body.index("local function world(")
    result = run_luau(luau, body[:at] + head + body[at:])
    out = []
    for line in result.stdout.splitlines():
        if line.startswith("FAIL: "):
            name, _, extra = line[len("FAIL: "):].partition(" -- ")
            out.append((name, False, extra or None))
    m = re.search(r"(\d+) passed, (\d+) failed", result.stdout)
    out += [("goals card", True, None)] * (int(m.group(1)) if m else 0)
    if result.returncode != 0 or "DONE" not in result.stdout.splitlines():
        out.append((GOALS_DONE + " (it crashed: a crash is never a catch)", False, (result.stderr or result.stdout)[-300:]))
    return out


def goals_card_static_checks(text):
    code = code_only(text)
    return [
        ("goals card static: the card reads the goals in use (OnboardingConfig.activeGoals()), never OnboardingConfig.Goals directly",
         "OnboardingConfig.activeGoals()" in code and "OnboardingConfig.Goals" not in code, None),
        ("goals card static: the card is sized for math.min(OnboardingConfig.ShowAtOnce, #GOALS) rows (tools/hud_test.py and"
         " tools/daily_test.py count its rows that way: onboarding_goal_count)",
         "local SLOTS = math.min(OnboardingConfig.ShowAtOnce, #GOALS)" in code and "HEADER_HEIGHT + ROW_HEIGHT * SLOTS + 8" in code, None),
        ("goals card static: its only request is closing the tracker (one InvokeServer, DismissTracker; no FireServer)",
         code.count("InvokeServer") == 1 and "InvokeServer(\"DismissTracker\")" in code and "FireServer" not in code, None),
    ]


GOALS_MUTANTS = [
    ("the card reads Goals, not the goals in use", "local GOALS = OnboardingConfig.activeGoals()", "local GOALS = OnboardingConfig.Goals",
     "chain: the card draws the goals the server shows"),
    ("one row per goal of the list (the card grows with the chain)", "local SLOTS = math.min(OnboardingConfig.ShowAtOnce, #GOALS)",
     "local SLOTS = #GOALS", "card: with the Chain"),
    ("the shown mark is ignored (every goal drawn)", "\t\tif shown == true then\n", "\t\tif true then\n",
     "chain: the card draws the goals the server shows"),
    ("a goal marked not shown counts as shown", "\t\tif shown == true then\n", "\t\tif shown ~= nil then\n",
     "chain: the card draws the goals the server shows"),
    ("no fallback for a server from before the chain", "\tif not marked then\n", "\tif false then\n", "old server:"),
    ("the fallback always on (the server's choice ignored)", "\tif not marked then\n", "\tif true then\n", "chain:"),
    ("an empty row keeps its old goal", " or \"\" -- an empty slot stays empty", " or row.name.Text -- an empty slot stays empty",
     "chain: with one goal shown the second row is empty"),
    ("a goal with no progress counts as not done (the calls block \"All goals done!\")",
     "\t\t\tallDone = allDone and current >= target\n\t\tend\n",
     "\t\t\tallDone = allDone and current >= target\n\t\telse\n\t\t\tallDone = false\n\t\tend\n", "all done: a goal the server can't check"),
    ("the tick is never drawn", "(done and \"✅\" or goal.icon)", "(goal.icon)", "chain: a shown goal just finished keeps its row"),
    ("the X you see moves with the bigger tap area", "\tPosition = UDim2.fromOffset(7, 4 + GAP),", "\tPosition = UDim2.fromOffset(0, 0),",
     "close: the X you see is still 30 x 26"),
    ("the tap area reaches onto the valuation bar", "\tPosition = UDim2.new(1, 3, 0, -GAP),", "\tPosition = UDim2.new(1, 3, 0, -GAP - 8),",
     "close: the tap area stays below the valuation bar"),
]
# Must be reported as NOT caught: the client errors on every refresh, so the row checks fail too, but an error is
# never a catch (its "ran without an error" check fails).
GOALS_SELF_TEST = ("a client that errors on every refresh", "\tlocal list = shownGoals()\n", "\terror(\"crash (test)\")\n\tlocal list = shownGoals()\n",
                   "chain: the card draws the goals the server shows")


def goals_card_mutant(luau, source, old, new, want):
    """(caught, why) for one mutant of OnboardingClient.lua."""
    if source.count(old) != 1:
        return False, "not applied (%d matches)" % source.count(old)
    failed = [n for n, ok, _ in goals_card_checks(luau, source.replace(old, new)) if not ok]
    if any(n.startswith(GOALS_CLEAN) or n.startswith(GOALS_DONE) for n in failed):
        return False, "the client errored: an error is never a catch"
    if any(n.startswith(want) for n in failed):
        return True, None
    return False, "no failing check starts with \"%s\" (failed: %s)" % (want, failed[:3])


def goals_card_main(luau, mutations=True):
    """Runs the Goals card's checks and mutants; returns 0 or 1."""
    code = 0
    source = read(GOALS_CLIENT)
    results = goals_card_checks(luau) + goals_card_static_checks(source)
    bad = [(n, e) for n, ok, e in results if not ok]
    for n, e in bad:
        print("FAIL: " + n + (" -- " + str(e) if e is not None else ""))
    print("Goals card (OnboardingClient) in a fake client: %d passed, %d failed" % (len(results) - len(bad), len(bad)))
    if bad:
        code = 1
    if not mutations:
        return code
    caught = 0
    for label, old, new, want in GOALS_MUTANTS:
        ok, why = goals_card_mutant(luau, source, old, new, want)
        if ok:
            caught += 1
        else:
            print("NOT CAUGHT: %s -- %s" % (label, why))
    print("Goals card mutations: %d of %d caught, each by its named check (never by an error)" % (caught, len(GOALS_MUTANTS)))
    if caught != len(GOALS_MUTANTS):
        code = 1
    label, old, new, want = GOALS_SELF_TEST
    self_ok, why = goals_card_mutant(luau, source, old, new, want)
    good = (not self_ok) and why is not None and "errored" in why
    print("Goals card harness self-test (a client that errors never counts): %d of 1 reported as not caught" % (1 if good else 0))
    if not good:
        print("FAIL: the Goals card harness counted an erroring client as caught (%s)" % why)
        code = 1
    return code



# tools/hatch_reveal_test.luau runs the REAL HATCHPANEL block of EmployeeClient.lua (request U2 of the gameplay lane:
# the hatch reveal holds the PlayerGui attribute "OpenPanel" as "Hatch", so TaskClient freezes the calls) against a fake
# PlayerGui; static checks pin where playReveal calls it. Then each break below must fail its named check; a block
# that errored never counts.
HATCH_CLIENT = "EmployeeClient.lua"
HATCH_TEST = os.path.join("tools", "hatch_reveal_test.luau")
HATCH_CLEAN = "block: ran without an error"
HATCH_DONE = "hatch reveal: the program ran to the end"


def hatch_checks(luau, client_text=None):
    """[(name, ok, extra)] of the real HATCHPANEL block against a fake PlayerGui."""
    client = client_text if client_text is not None else read(HATCH_CLIENT)
    start = client.find("-- HATCHPANEL-START")
    end = client.find("-- HATCHPANEL-END")
    if start < 0 or end < start:
        return [(HATCH_DONE + " (EmployeeClient.lua has no HATCHPANEL-START / HATCHPANEL-END block)", False, None)]
    head = "local BLOCK = function(playerGui)\n" + client[start:end] + "\nreturn setRevealShowing\nend\n"
    body = read(HATCH_TEST)
    at = body.index("local function start(")
    result = run_luau(luau, body[:at] + head + body[at:])
    out = []
    for line in result.stdout.splitlines():
        if line.startswith("FAIL: "):
            name, _, extra = line[len("FAIL: "):].partition(" -- ")
            out.append((name, False, extra or None))
    m = re.search(r"(\d+) passed, (\d+) failed", result.stdout)
    out += [("hatch reveal", True, None)] * (int(m.group(1)) if m else 0)
    if result.returncode != 0 or "DONE" not in result.stdout.splitlines():
        out.append((HATCH_DONE + " (it crashed: a crash is never a catch)", False, (result.stderr or result.stdout)[-300:]))
    return out


def hatch_static_checks(text):
    code = code_only(text)
    at = code.find("local function playReveal(")
    reveal = code[at:code.find("\nend\n", at)] if at >= 0 else ""
    handler_at = code.find("eggHatched.OnClientEvent:Connect(")
    handler = code[handler_at:code.find("\nend)\n", handler_at)] if handler_at >= 0 else ""
    block = code_only(text[text.find("-- HATCHPANEL-START"):text.find("-- HATCHPANEL-END")]) if "-- HATCHPANEL-END" in text else ""
    first_wait = reveal.find("task.wait(")
    hold = reveal.find("setRevealShowing(true)")
    hidden = reveal.find("revealGui.Enabled = false")
    release = reveal.find("setRevealShowing(false)")
    team = reveal.find("setOpen(true, \"Team\")")
    return [
        ("hatch static: playReveal holds OpenPanel (setRevealShowing(true)) before the egg's first wait",
         0 <= hold < first_wait, None),
        ("hatch static: playReveal gives OpenPanel back (setRevealShowing(false)) once the reveal is hidden, before it"
         " opens the team window for a full team",
         0 <= hidden < release < team, None),
        ("hatch static: a reveal that errors is caught (pcall) and gives OpenPanel back",
         "pcall(playReveal," in handler and "setRevealShowing(false)" in handler[handler.find("pcall(playReveal,"):], None),
        ("hatch static: the block only sets the PlayerGui attribute (no remote, nothing saved)",
         block != "" and "InvokeServer" not in block and "FireServer" not in block, None),
    ]


HATCH_MUTANTS = [
    ("the reveal never takes OpenPanel", "\t\tplayerGui:SetAttribute(\"OpenPanel\", REVEAL_PANEL)\n", "",
     "no window: while the reveal plays"),
    ("the reveal takes OpenPanel from an open window", "\tif revealShowing and playerGui:GetAttribute(\"OpenPanel\") == nil then\n",
     "\tif revealShowing then\n", "window open: the reveal never takes OpenPanel"),
    ("the end of the reveal always clears OpenPanel", "\telseif playerGui:GetAttribute(\"OpenPanel\") == REVEAL_PANEL then\n",
     "\telse\n", "window open: after the reveal"),
    ("the end of the reveal never clears OpenPanel", "== REVEAL_PANEL then\n\t\tplayerGui:SetAttribute(\"OpenPanel\", nil)\n", "== REVEAL_PANEL then\n",
     "no window: after the reveal OpenPanel is nil"),
    ("a window closing during the reveal is not covered", "playerGui:GetAttributeChangedSignal(\"OpenPanel\"):Connect(holdRevealPanel)\n", "",
     "window closed during the reveal"),
    ("the block keeps holding after the reveal", "\tif revealShowing and playerGui:GetAttribute(\"OpenPanel\") == nil then\n",
     "\tif playerGui:GetAttribute(\"OpenPanel\") == nil then\n", "after the reveal:"),
    ("playReveal never holds OpenPanel", "\tsetRevealShowing(true)\n\trevealGui.Enabled = true\n", "\trevealGui.Enabled = true\n",
     "hatch static: playReveal holds OpenPanel"),
    ("playReveal never gives OpenPanel back", "\trevealGui.Enabled = false\n\tsetRevealShowing(false)\n", "\trevealGui.Enabled = false\n",
     "hatch static: playReveal gives OpenPanel back"),
    ("a broken reveal is not caught", "local ok, err = pcall(playReveal, table.remove(revealQueue, 1))",
     "local ok, err = true, playReveal(table.remove(revealQueue, 1))", "hatch static: a reveal that errors"),
]
# Must be reported as NOT caught: the block errors, so the OpenPanel checks fail too, but an error is never a catch.
HATCH_SELF_TEST = ("a block that errors", "local function setRevealShowing(showing)\n",
                   "local function setRevealShowing(showing)\n\terror(\"crash (test)\")\n", "no window: while the reveal plays")


def hatch_mutant(luau, source, old, new, want):
    """(caught, why) for one mutant of EmployeeClient.lua."""
    if source.count(old) != 1:
        return False, "not applied (%d matches)" % source.count(old)
    mutated = source.replace(old, new)
    failed = [n for n, ok, _ in hatch_checks(luau, mutated) + hatch_static_checks(mutated) if not ok]
    if any(n.startswith(HATCH_CLEAN) or n.startswith(HATCH_DONE) for n in failed):
        return False, "the block errored: an error is never a catch"
    if any(n.startswith(want) for n in failed):
        return True, None
    return False, "no failing check starts with \"%s\" (failed: %s)" % (want, failed[:3])


def hatch_main(luau, mutations=True):
    """Runs the hatch reveal's checks and mutants; returns 0 or 1."""
    code = 0
    source = read(HATCH_CLIENT)
    results = hatch_checks(luau) + hatch_static_checks(source)
    bad = [(n, e) for n, ok, e in results if not ok]
    for n, e in bad:
        print("FAIL: " + n + (" -- " + str(e) if e is not None else ""))
    print("Hatch reveal (EmployeeClient's HATCHPANEL block) in a fake PlayerGui: %d passed, %d failed" % (len(results) - len(bad), len(bad)))
    if bad:
        code = 1
    if not mutations:
        return code
    caught = 0
    for label, old, new, want in HATCH_MUTANTS:
        ok, why = hatch_mutant(luau, source, old, new, want)
        if ok:
            caught += 1
        else:
            print("NOT CAUGHT: %s -- %s" % (label, why))
    print("Hatch reveal mutations: %d of %d caught, each by its named check (never by an error)" % (caught, len(HATCH_MUTANTS)))
    if caught != len(HATCH_MUTANTS):
        code = 1
    label, old, new, want = HATCH_SELF_TEST
    self_ok, why = hatch_mutant(luau, source, old, new, want)
    good = (not self_ok) and why is not None and "errored" in why
    print("Hatch reveal harness self-test (a block that errors never counts): %d of 1 reported as not caught" % (1 if good else 0))
    if not good:
        print("FAIL: the hatch reveal harness counted an erroring block as caught (%s)" % why)
        code = 1
    return code


# Tap targets (ux backlog item 4): every TextButton and ImageButton a client makes with a fixed size in pixels is 40 or
# more on each side (a phone finger). Sizes in scale (a share of the screen or window) and sizes from ShopLayout are
# checked by their own suites (tools/shop_ux_test.py, tools/daily_test.py's tray); this check reads the literal ones:
# UDim2.fromOffset(w, h), and the height of UDim2.new(sx, ox, 0, h) (and its width when its X scale is 0).
TAP_MIN = 40
TAP_FILES = ("ClaimButtonClient.lua", "DailyClient.lua", "EmployeeClient.lua", "IpoClient.lua", "LobbyClient.lua",
             "OnboardingClient.lua", "PoachClient.lua", "ShopClient.lua", "TaskClient.lua", "ChatTags.lua")
NUM = r"(-?\d+(?:\.\d+)?)"


def tap_target_sizes(text):
    """[(line, (w or None, h or None))] for each make("TextButton" / "ImageButton", {...}) with a literal size."""
    out = []
    for m in re.finditer(r'make\("(?:TextButton|ImageButton)", \{', text):
        i, depth = m.end(), 1
        while depth and i < len(text):
            depth += (text[i] == "{") - (text[i] == "}")
            i += 1
        body = code_only(text[m.end():i])
        line = text[:m.start()].count("\n") + 1
        s = re.search(r"\n\s*Size = UDim2\.fromOffset\(\s*" + NUM + r"\s*,\s*" + NUM + r"\s*\)", body)
        if s:
            out.append((line, (float(s.group(1)), float(s.group(2)))))
            continue
        s = re.search(r"\n\s*Size = UDim2\.new\(\s*" + NUM + r"\s*,\s*" + NUM + r"\s*,\s*0\s*,\s*" + NUM + r"\s*\)", body)
        if s:
            out.append((line, (float(s.group(2)) if float(s.group(1)) == 0 else None, float(s.group(3)))))
    return out


def tap_target_checks(texts=None):
    results = []
    total = 0
    for name in TAP_FILES:
        text = texts[name] if texts is not None and name in texts else (read(name) if os.path.exists(os.path.join(ROOT, name)) else "")
        for line, (w, h) in tap_target_sizes(text):
            total += 1
            small = [v for v in (w, h) if v is not None and v < TAP_MIN]
            results.append(("tap targets: %s:%d is %s x %s, 40 or more on each side" % (name, line, w if w is not None else "scale", h),
                            not small, None))
    results.append(("tap targets: the check found the fixed-size buttons (10 or more; it reads them, it must not go blind)",
                    total >= 10, total))
    return results


TAP_MUTANTS = [
    ("the Goals card's X back to 30 x 26", "OnboardingClient.lua", "\tSize = UDim2.fromOffset(44, 40),\n\tBackgroundTransparency = 1,\n",
     "\tSize = UDim2.fromOffset(30, 26),\n\tBackgroundTransparency = 1,\n"),
    ("the welcome card's Got it back to 30 high", "LobbyClient.lua", "Size = UDim2.fromOffset(110, 40),", "Size = UDim2.fromOffset(110, 30),"),
    ("a window's close button at 44 x 30", "IpoClient.lua", "Size = UDim2.fromOffset(44, 40),", "Size = UDim2.fromOffset(44, 30),"),
    ("the Daily window's Claim button at 36 high", "DailyClient.lua", "Size = UDim2.new(1, 0, 0, 56),", "Size = UDim2.new(1, 0, 0, 36),"),
]


def tap_main(mutations=True):
    code = 0
    results = tap_target_checks()
    bad = [(n, e) for n, ok, e in results if not ok]
    for n, e in bad:
        print("FAIL: " + n + (" -- " + str(e) if e is not None else ""))
    print("Tap targets (fixed-size buttons in the clients): %d passed, %d failed" % (len(results) - len(bad), len(bad)))
    if bad:
        code = 1
    if not mutations:
        return code
    caught = 0
    for label, name, old, new in TAP_MUTANTS:
        text = read(name)
        if text.count(old) != 1:
            print("NOT CAUGHT: %s -- not applied (%d matches)" % (label, text.count(old)))
            continue
        failed = [n for n, ok, _ in tap_target_checks({name: text.replace(old, new)}) if not ok]
        if any(n.startswith("tap targets: " + name) for n in failed):
            caught += 1
        else:
            print("NOT CAUGHT: %s" % label)
    print("Tap target mutations: %d of %d caught, each by its named check" % (caught, len(TAP_MUTANTS)))
    if caught != len(TAP_MUTANTS):
        code = 1
    return code

def main():
    luau = os.environ.get("LUAU") or shutil.which("luau")
    if not luau:
        print("luau not found. Download it from https://github.com/luau-lang/luau/releases, or set LUAU=/path/to/luau")
        return 2
    goals = onboarding_goal_count()
    client = read(CLIENT)
    passed, failed, fails, crashed, out = run_all(luau, client, goals, dump="--layout-table" in sys.argv)
    for line in out:
        if not line.startswith("FAIL: ") and not re.match(r"^\d+ passed, \d+ failed$", line):
            print(line)
    for name, ok, extra in doc_checks():
        if ok:
            passed += 1
        else:
            failed += 1
            fails.append("FAIL: " + name + " -- " + str(extra))
            print(fails[-1])
    for line in fails:
        if not line.startswith("FAIL: doc:"):
            print(line)
    if crashed:
        print("CRASH: " + crashed)
    print("HUD bar check: %d passed, %d failed" % (passed, failed))
    code = 0 if failed == 0 and not crashed else 1

    if "--no-mutations" not in sys.argv:
        caught = 0
        for name, old, new in MUTATIONS:
            if client.count(old) != 1:
                print("MUTATION NOT APPLIED (%d matches): %s" % (client.count(old), name))
                code = 1
                continue
            p, f, mfails, mcrash, _ = run_all(luau, client.replace(old, new), goals)
            names = [line[len("FAIL: "):].split(" -- ")[0] for line in mfails]
            if mcrash:
                print("MUTATION CRASHED (not a named check): %s: %s" % (name, mcrash.split("\n")[0]))
                code = 1
            elif not names:
                print("MUTATION NOT CAUGHT: " + name)
                code = 1
            else:
                caught += 1
                print("caught: %s\n        by: %s%s" % (name, names[0], " (+%d more)" % (len(names) - 1) if len(names) > 1 else ""))
                if all("the test ran to its end" in n for n in names):
                    print("        (only by a test that stopped, not by a rule: look at it)")
        print("HUD bar mutations: %d of %d broken rules caught by a named check" % (caught, len(MUTATIONS)))
        if caught != len(MUTATIONS):
            code = 1
        if coupling_mutation_runs(client, "--coupling-detail" in sys.argv):
            code = 1
    if claim_main(luau, "--no-mutations" not in sys.argv):
        code = 1
    if goals_card_main(luau, "--no-mutations" not in sys.argv):
        code = 1
    if hatch_main(luau, "--no-mutations" not in sys.argv):
        code = 1
    if tap_main("--no-mutations" not in sys.argv):
        code = 1
    return code


if __name__ == "__main__":
    sys.exit(main())
