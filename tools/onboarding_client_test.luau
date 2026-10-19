-- The real OnboardingClient.lua's Goals card against a fake client (ux lane, request U1 of the gameplay lane).
-- tools/hud_test.py puts two functions in front of the world builder: CONFIG_SOURCE (OnboardingConfig.lua) and CLIENT
-- (the whole client, given the fake services). Each scenario has its own "ran without an error" check, and no other
-- check reads the error: a mutant counts only when a check about what the card shows fails.
local print_real = print
local passed, failed = 0, 0
local function check(name, cond, extra)
	if cond then passed += 1 else failed += 1; print_real("FAIL: " .. name .. (extra ~= nil and (" -- " .. tostring(extra)) or "")) end
end
local function signal()
	local s = { handlers = {} }
	function s.Connect(self, fn) table.insert(self.handlers, fn) return { Disconnect = function() end } end
	function s.Fire(self, ...) for _, fn in ipairs(table.clone(self.handlers)) do fn(...) end end
	return s
end
local function vec2(x, y) return { X = x, Y = y } end
local clock, timers = 0, {}
local Mt = {}
local M = {}
local SIGNALS = { Activated = true, OnClientEvent = true, CharacterAdded = true, AttributeChanged = true, RenderStepped = true }
Mt.__index = function(t, k)
	if k == "Parent" then return rawget(t, "_parent") end
	local p = rawget(t, "_props")
	if p[k] ~= nil then return p[k] end
	if M[k] then return M[k] end
	if SIGNALS[k] then local s = signal() p[k] = s return s end
	for _, c in ipairs(rawget(t, "_children")) do if c.Name == k then return c end end
	return nil
end
Mt.__newindex = function(t, k, v)
	if k == "Parent" then
		local old = rawget(t, "_parent")
		if old then for i, c in ipairs(old._children) do if c == t then table.remove(old._children, i) break end end end
		rawset(t, "_parent", v)
		if v then table.insert(v._children, t) end
		return
	end
	rawget(t, "_props")[k] = v
end
local function new(class)
	local o = setmetatable({ ClassName = class, _children = {}, _attrs = {}, _attrSignals = {}, _propSignals = {}, _props = { Name = class } }, Mt)
	if class == "ScreenGui" then o._props.AbsoluteSize = vec2(390, 800) end
	return o
end
function M.FindFirstChild(t, n) for _, c in ipairs(t._children) do if c.Name == n then return c end end return nil end
function M.WaitForChild(t, n) return t:FindFirstChild(n) end
function M.GetChildren(t) return table.clone(t._children) end
function M.SetAttribute(t, k, v)
	if t._attrs[k] == v then return end
	t._attrs[k] = v
	if t._attrSignals[k] then t._attrSignals[k]:Fire() end
	if t._props.AttributeChanged then t._props.AttributeChanged:Fire(k) end
end
function M.GetAttribute(t, k) return t._attrs[k] end
function M.GetAttributeChangedSignal(t, k) t._attrSignals[k] = t._attrSignals[k] or signal() return t._attrSignals[k] end
function M.GetPropertyChangedSignal(t, k) t._propSignals[k] = t._propSignals[k] or signal() return t._propSignals[k] end
function M.InvokeServer(t, ...) table.insert(t._props.calls, { ... }) return true end
local Instance = { new = new }
local UDim2 = {
	fromOffset = function(x, y) return { X = { Scale = 0, Offset = x }, Y = { Scale = 0, Offset = y } } end,
	fromScale = function(x, y) return { X = { Scale = x, Offset = 0 }, Y = { Scale = y, Offset = 0 } } end,
	new = function(a, b, c, d) return { X = { Scale = a, Offset = b }, Y = { Scale = c, Offset = d } } end,
}
local UDim = { new = function(a, b) return { a, b } end }
local Color3 = { fromRGB = function(r, g, b) return { r, g, b } end, new = function(r, g, b) return { r * 255, g * 255, b * 255 } end }
local Vector3 = { new = function(x, y, z) return { X = x, Y = y, Z = z } end }
local Vector2 = { new = function(x, y) return vec2(x, y) end }
local ColorSequence = { new = function(...) return { ... } end }
local NumberSequence = { new = function(...) return { ... } end }
local Enum = {
	Font = { GothamBold = "GothamBold", GothamBlack = "GothamBlack" },
	ApplyStrokeMode = { Border = "Border" },
	ZIndexBehavior = { Sibling = "Sibling" },
	TextXAlignment = { Left = "Left", Right = "Right" },
}
local task = {
	delay = function(s, fn) table.insert(timers, { at = clock + s, fn = fn }) end,
	wait = function() end,
	spawn = function(fn, ...) fn(...) end,
}
local function quiet() end -- the config's warn
local function advance(W, seconds)
	local target = clock + seconds
	while true do
		local nextIndex, nextAt = nil, math.huge
		for i, tm in ipairs(timers) do if tm.at <= target and tm.at < nextAt then nextIndex, nextAt = i, tm.at end end
		if not nextIndex then break end
		local tm = table.remove(timers, nextIndex)
		clock = tm.at
		local ok, err = pcall(tm.fn)
		if not ok and not W.err then W.err = err end
	end
	clock = target
end

local function world(chainOn)
	local W = {}
	timers = {}
	W.player = new("Player")
	local pg = new("PlayerGui")
	pg.Name = "PlayerGui"
	pg.Parent = W.player
	W.playerGui = pg
	local rs = new("ReplicatedStorage")
	local cfg = (CONFIG_SOURCE)()
	cfg.ChainEnabled = chainOn
	W.config = cfg
	local function module(name, value)
		local m = new("ModuleScript")
		m.Name = name
		m._props.module = value
		m.Parent = rs
	end
	module("OnboardingConfig", cfg)
	module("IpoConfig", { formatShort = function(n) return "$" .. tostring(n) end })
	local remotes = new("Folder")
	remotes.Name = "OnboardingRemotes"
	remotes.Parent = rs
	W.action = new("RemoteFunction")
	W.action.Name = "OnboardingAction"
	W.action._props.calls = {}
	W.action.Parent = remotes
	W.notify = new("RemoteEvent")
	W.notify.Name = "OnboardingNotify"
	W.notify.Parent = remotes
	local services = { Players = { LocalPlayer = W.player }, ReplicatedStorage = rs, RunService = { RenderStepped = signal() } }
	W.game = { GetService = function(_, n) return services[n] end }
	W.require = function(m) return m.module end
	W.workspace = new("Workspace")
	return W
end
local function start(W)
	local ok, err = pcall(CLIENT, W.game, Instance, W.require, UDim2, UDim, Color3, Enum, task, W.workspace, Vector3, Vector2,
		ColorSequence, NumberSequence, quiet)
	W.err = not ok and err or nil
	W.gui = W.playerGui:FindFirstChild("OnboardingGui")
	W.card = W.gui and W.gui:FindFirstChild("GoalTracker")
	return W
end
local function set(W, name, value)
	local ok, err = pcall(W.player.SetAttribute, W.player, name, value)
	if not ok and not W.err then W.err = err end
end
-- The server's view of one goal: progress (nil = it can't check this goal) and whether it is shown
local function goal(W, key, current, target, shown)
	if current ~= nil then
		set(W, "OnboardingGoal_" .. key, current)
		set(W, "OnboardingGoalTarget_" .. key, target)
	end
	set(W, "OnboardingGoalShown_" .. key, shown)
end
local function ranClean(W, label) check("client: ran without an error (" .. label .. ")", W.err == nil, W.err) end
-- The card's goal rows, top to bottom: the left-aligned labels below the header, in order of their Y
local function rowTexts(W)
	local rows = {}
	if not W.card then return rows end
	for _, c in ipairs(W.card._children) do
		if c.ClassName == "TextLabel" and c.TextXAlignment == "Left" and c.Position.Y.Offset >= 30 then
			table.insert(rows, c)
		end
	end
	table.sort(rows, function(a, b) return a.Position.Y.Offset < b.Position.Y.Offset end)
	local out = {}
	for i, r in ipairs(rows) do out[i] = r.Text end
	return out, #rows
end
local function hasText(text, piece) return type(text) == "string" and string.find(text, piece, 1, true) ~= nil end
local function shown(W) return W.card ~= nil and W.card.Visible == true end
local function height(W) return W.card and W.card.Size.Y.Offset end
local function dump(t) return table.concat(t, " | ") end

do -- today's two goals (ChainEnabled off), with today's server
	local W = start(world(false))
	local _, n = rowTexts(W)
	check("card: with Goals (2) and ShowAtOnce 2 the card has 2 rows and is 30 + 22 x 2 + 8 high", n == 2 and height(W) == 82, tostring(n) .. " rows, " .. tostring(height(W)))
	goal(W, "Hire3", 1, 3, true)
	goal(W, "Seed", 100, 5000, true)
	set(W, "OnboardingTracker", true)
	local t = rowTexts(W)
	check("goals off: the two shown goals are drawn in list order", hasText(t[1], "Hire 3 employees") and hasText(t[2], "Reach Seed stage"), dump(t))
	check("goals off: the tracker shows", shown(W))
	W.playerGui:SetAttribute("OpenPanel", "Shop")
	check("goals off: a window open hides the card", not shown(W))
	W.playerGui:SetAttribute("OpenPanel", nil)
	check("goals off: the window closed, the card is back", shown(W))
	ranClean(W, "goals off")
end

do -- the chain on: 8 goals, 2 rows; the server says which
	local W = start(world(true))
	local _, n = rowTexts(W)
	check("card: with the Chain (8 goals) the card still has ShowAtOnce (2) rows and the same height (82)",
		n == 2 and height(W) == 82, tostring(n) .. " rows, " .. tostring(height(W)))
	-- Outside Studio the call goals can't be checked: no progress, never shown. The server shows Own3 and Hire3.
	-- Set in reverse list order: the card must still follow the list's order.
	goal(W, "FirstIpo", 0, 1, false)
	goal(W, "SeriesA", 0, 50000, false)
	goal(W, "Seed", 0, 5000, false)
	goal(W, "ServerRack", 0, 1, false)
	goal(W, "Calls10Row", nil, nil, false)
	goal(W, "Hire3", 1, 3, true)
	goal(W, "Own3", 2, 3, true)
	goal(W, "Calls3", nil, nil, false)
	set(W, "OnboardingTracker", true)
	local t = rowTexts(W)
	check("chain: the card draws the goals the server shows (Own 3 office items, Hire 3 employees), in list order",
		hasText(t[1], "Own 3 office items") and hasText(t[2], "Hire 3 employees"), dump(t))
	check("chain: a goal the server does not show is not drawn (Answer 3 calls, Reach Seed stage)",
		not hasText(dump(t), "Answer 3 calls") and not hasText(dump(t), "Reach Seed stage"), dump(t))
	-- Own3 finished: the server keeps it shown with its tick for a moment
	goal(W, "Own3", 3, 3, true)
	t = rowTexts(W)
	check("chain: a shown goal just finished keeps its row, with a tick", hasText(t[1], "✅") and hasText(t[1], "Own 3 office items"), dump(t))
	-- Then the server moves on: Own3 hidden, ServerRack shown after Hire3
	goal(W, "Own3", 3, 3, false)
	goal(W, "ServerRack", 0, 1, true)
	t = rowTexts(W)
	check("chain: the next goal takes the free row (Hire 3 employees, then Buy the Server Rack)",
		hasText(t[1], "Hire 3 employees") and hasText(t[2], "Buy the Server Rack"), dump(t))
	-- Only one goal shown: the other row is empty, not the old text
	goal(W, "ServerRack", 1, 1, false)
	t = rowTexts(W)
	check("chain: with one goal shown the second row is empty", hasText(t[1], "Hire 3 employees") and t[2] == "", dump(t))
	check("chain: the tracker still shows", shown(W))
	ranClean(W, "chain")
end

do -- more goals marked shown than rows: the first ones in list order, never a third row
	local W = start(world(true))
	goal(W, "Calls3", 0, 3, true)
	goal(W, "Own3", 0, 3, true)
	goal(W, "Hire3", 0, 3, true)
	set(W, "OnboardingTracker", true)
	local t, n = rowTexts(W)
	check("chain: three goals marked shown still draw 2 rows, the first two of the list", n == 2 and hasText(t[1], "Answer 3 calls") and hasText(t[2], "Own 3 office items"), dump(t))
	ranClean(W, "too many shown")
end

do -- a server from before the goal chain marks nothing: the first goals of the list, as before
	local W = start(world(false))
	goal(W, "Hire3", 2, 3, nil)
	goal(W, "Seed", 100, 5000, nil)
	set(W, "OnboardingTracker", true)
	local t = rowTexts(W)
	check("old server: with no OnboardingGoalShown_ attribute at all, the card draws the first goals of the list",
		hasText(t[1], "Hire 3 employees") and hasText(t[2], "Reach Seed stage"), dump(t))
	ranClean(W, "old server")
end

do -- the last goal finished with the chain on, outside Studio (the call goals have no progress)
	local W = start(world(true))
	for _, key in ipairs({ "Own3", "Hire3", "ServerRack", "Seed", "SeriesA" }) do goal(W, key, 1, 1, false) end
	goal(W, "Calls3", nil, nil, false)
	goal(W, "Calls10Row", nil, nil, false)
	goal(W, "FirstIpo", 0, 1, true)
	set(W, "OnboardingTracker", true)
	check("all done: the card shows before the last goal", shown(W))
	goal(W, "FirstIpo", 1, 1, true)
	set(W, "OnboardingTracker", false) -- the server: every goal it can check is finished
	local title
	for _, c in ipairs(W.card and W.card._children or {}) do if c.ClassName == "TextLabel" and c.Position.Y.Offset < 30 then title = c.Text end end
	check("all done: a goal the server can't check (the calls) does not stop the \"All goals done!\" card", shown(W) and hasText(title, "All goals done"), tostring(title))
	advance(W, 3.5)
	check("all done: then the card goes", not shown(W))
	ranClean(W, "all done")
end

do -- the X still closes the card and asks the server to keep it closed
	local W = start(world(true))
	goal(W, "Own3", 0, 3, true)
	set(W, "OnboardingTracker", true)
	local close = W.card and W.card:FindFirstChild("Close")
	-- ux backlog item 4: the X's tap area is 40 or more on each side; the X you see stays 30 x 26, 4 from the card's
	-- top and right; the tap area never reaches above the 6 px gap over the valuation bar (it opens the IPO window)
	local mark = close and close:FindFirstChild("Mark")
	local cardW = W.card and W.card.Size.X.Offset or 0
	if close and mark then
		local s, p = close.Size, close.Position
		local left = p.X.Scale * cardW + p.X.Offset - close.AnchorPoint.X * s.X.Offset
		local top = p.Y.Offset
		check("close: the X's tap area is 40 or more on each side", s.X.Offset >= 40 and s.Y.Offset >= 40, s.X.Offset .. "x" .. s.Y.Offset)
		check("close: the tap area stays below the valuation bar (6 px gap) and in the first row's top margin", top >= -6 and top + s.Y.Offset <= 30 + 4, top)
		check("close: the X you see is still 30 x 26 at 4 from the card's top and right",
			mark.Size.X.Offset == 30 and mark.Size.Y.Offset == 26 and left + mark.Position.X.Offset == cardW - 34 and top + mark.Position.Y.Offset == 4,
			tostring(left + mark.Position.X.Offset) .. "," .. tostring(top + mark.Position.Y.Offset))
	else
		check("close: the X's tap area is 40 or more on each side", false, "no Close button with a Mark")
	end
	if close then
		local ok, err = pcall(close.Activated.Fire, close.Activated)
		if not ok and not W.err then W.err = err end
	end
	check("close: the X hides the card and sends DismissTracker", not shown(W) and #W.action.calls == 1 and W.action.calls[1][1] == "DismissTracker")
	ranClean(W, "close")
end

print_real(string.format("%d passed, %d failed", passed, failed))
print_real("DONE")
