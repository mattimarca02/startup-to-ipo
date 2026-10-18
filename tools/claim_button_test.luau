-- The real ClaimButtonClient.lua against a fake client (ux lane). tools/hud_test.py puts three functions in front of the
-- world builder: LOBBY_SOURCE (LobbyConfig.lua), CLIENT (the whole client, given the fake services) and LAYOUT (the code between its
-- CLAIMBUTTON markers, returning buttonLayout). Each scenario has its own "ran without an error" check, and no other
-- check reads the error: a mutant counts only when a check about what the client shows or does fails.
local print_real = print
local passed, failed = 0, 0
local function check(name, cond, extra)
	if cond then passed += 1 else failed += 1; print_real("FAIL: " .. name .. (extra ~= nil and (" -- " .. tostring(extra)) or "")) end
end
local function signal()
	local s = { handlers = {} }
	function s.Connect(self, fn) table.insert(self.handlers, fn) return { Disconnect = function() end } end
	function s.Fire(self, ...) for _, fn in ipairs(self.handlers) do fn(...) end end
	return s
end
local function vec2(x, y) return { X = x, Y = y } end
local REMOTES = 0
local clock, timers = 0, {} -- a virtual clock: task.delay runs when the test moves the clock past its time
local function NOW() return clock end
local Mt = {}
local M = {}
local SIGNALS = { Activated = true }
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
local SCREEN = vec2(390, 800)
local function new(class)
	if class == "RemoteEvent" or class == "RemoteFunction" or class == "BindableEvent" then REMOTES += 1 end
	local o = setmetatable({ ClassName = class, _children = {}, _attrs = {}, _attrSignals = {}, _propSignals = {}, _props = { Name = class } }, Mt)
	if class == "ScreenGui" then o._props.AbsoluteSize = SCREEN end
	return o
end
function M.FindFirstChild(t, n) for _, c in ipairs(t._children) do if c.Name == n then return c end end return nil end
function M.FindFirstChildOfClass(t, n) for _, c in ipairs(t._children) do if c.ClassName == n then return c end end return nil end
function M.WaitForChild(t, n) return t:FindFirstChild(n) end
function M.GetChildren(t) return table.clone(t._children) end
function M.SetAttribute(t, k, v) t._attrs[k] = v if t._attrSignals[k] then t._attrSignals[k]:Fire() end end
function M.GetAttribute(t, k) return t._attrs[k] end
function M.GetAttributeChangedSignal(t, k) t._attrSignals[k] = t._attrSignals[k] or signal() return t._attrSignals[k] end
function M.GetPropertyChangedSignal(t, k) t._propSignals[k] = t._propSignals[k] or signal() return t._propSignals[k] end
function M.InputHoldBegin(t) t._props.began = (t._props.began or 0) + 1 t._props.heldAt = NOW() end
function M.InputHoldEnd(t) t._props.ended = (t._props.ended or 0) + 1 t._props.heldFor = NOW() - (t._props.heldAt or 0) end
function M.FireServer() REMOTES += 100 end
local Instance = { new = new }
local UDim2 = {
	fromOffset = function(x, y) return { X = { Scale = 0, Offset = x }, Y = { Scale = 0, Offset = y } } end,
	fromScale = function(x, y) return { X = { Scale = x, Offset = 0 }, Y = { Scale = y, Offset = 0 } } end,
	new = function(a, b, c, d) return { X = { Scale = a, Offset = b }, Y = { Scale = c, Offset = d } } end,
}
local UDim = { new = function(a, b) return { a, b } end }
local Color3 = { fromRGB = function(r, g, b) return { r, g, b } end, new = function(r, g, b) return { r * 255, g * 255, b * 255 } end }
local Enum = {
	Font = { GothamBold = "GothamBold" },
	ApplyStrokeMode = { Border = "Border" },
	ProximityPromptInputType = { Touch = "Touch", Keyboard = "Keyboard", Gamepad = "Gamepad" },
}
local task = {
	delay = function(s, fn) table.insert(timers, { at = clock + s, fn = fn }) end,
	wait = function() end,
	spawn = function(fn, ...) fn(...) end,
}
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

local function world(claimOn, garageAttr)
	local W = {}
	W.player = new("Player")
	local pg = new("PlayerGui")
	pg.Name = "PlayerGui"
	pg.Parent = W.player
	W.playerGui = pg
	W.player:SetAttribute("Garage", garageAttr)
	-- Two garages' claim posts (in their ClaimSpot models) with the server's prompt, and the VIP door's prompt
	for slot = 1, 2 do
		local spot = new("Model")
		spot.Name = "ClaimSpot"
		local post = new("Part")
		post.Name = "ClaimPost"
		post.Parent = spot
		local prompt = new("ProximityPrompt")
		prompt.ActionText = "Claim garage"
		prompt.ObjectText = "Garage " .. slot
		prompt.HoldDuration = 0.5
		prompt.Parent = post
		W["prompt" .. slot] = prompt
	end
	local door = new("Part")
	door.Name = "VipDoor"
	local other = new("ProximityPrompt")
	other.ObjectText = "VIP Lounge"
	other.HoldDuration = 0
	other.Parent = door
	W.other = other
	-- A post that is not in a ClaimSpot (a prop someone named ClaimPost)
	local loose = new("Part")
	loose.Name = "ClaimPost"
	local loosePrompt = new("ProximityPrompt")
	loosePrompt.ObjectText = "Loose"
	loosePrompt.HoldDuration = 0
	loosePrompt.Parent = loose
	W.loose = loosePrompt
	local rs = new("ReplicatedStorage")
	local lobby = (LOBBY_SOURCE)()
	lobby.ClaimEnabled = claimOn
	local cfg = new("ModuleScript")
	cfg.Name = "LobbyConfig"
	cfg._props.module = lobby
	cfg.Parent = rs
	W.pps = { PromptShown = signal(), PromptHidden = signal() }
	local services = { Players = { LocalPlayer = W.player }, ReplicatedStorage = rs, ProximityPromptService = W.pps }
	W.game = { GetService = function(_, n) return services[n] end }
	W.require = function(m) return m.module end
	return W
end
local function start(W)
	local ok, err = pcall(CLIENT, W.game, Instance, W.require, UDim2, UDim, Color3, Enum, task)
	W.err = not ok and err or nil
	W.gui = W.playerGui:FindFirstChild("ClaimButtonGui")
	W.button = W.gui and W.gui:FindFirstChild("ClaimButton")
	return W
end
local function fire(W, sig, ...)
	local ok, err = pcall(sig.Fire, sig, ...)
	if not ok and not W.err then W.err = err end
end
local function tap(W) if W.button then fire(W, W.button.Activated) end end
local function ranClean(W, label) check("client: ran without an error (" .. label .. ")", W.err == nil, W.err) end
local function shown(W) return W.gui ~= nil and W.gui.Enabled == true end
local function titleText(W) local t = W.button and W.button:FindFirstChild("Title") return t and t.Text end
local function garageText(W) local t = W.button and W.button:FindFirstChild("Garage") return t and t.Text end

do -- the claim on, on the plaza: the button follows the shown claim prompt
	local W = start(world(true, 0))
	check("client: on the plaza with no prompt shown, there is a button but it is hidden", W.gui ~= nil and W.button ~= nil and not shown(W))
	check("client: the button's gui is kept on respawn", W.gui ~= nil and W.gui.ResetOnSpawn == false)
	fire(W, W.pps.PromptShown, W.prompt2, Enum.ProximityPromptInputType.Touch)
	check("client: a claim prompt shown for touch shows the button, with the prompt's text and garage",
		shown(W) and titleText(W) == "Claim garage" and garageText(W) == "Garage 2", tostring(titleText(W)) .. " / " .. tostring(garageText(W)))
	W.playerGui:SetAttribute("OpenPanel", "Shop")
	check("client: a window open hides the button", not shown(W))
	W.playerGui:SetAttribute("OpenPanel", nil)
	check("client: the window closed, the button is back", shown(W))
	tap(W)
	check("client: the tap presses the shown prompt (InputHoldBegin once)", (W.prompt2.began or 0) == 1 and (W.prompt1.began or 0) == 0, W.prompt2.began)
	check("client: while pressing, the button says so", titleText(W) == "Claiming...", titleText(W))
	tap(W)
	advance(W, 0.2)
	tap(W)
	check("client: a second tap while holding does nothing", (W.prompt2.began or 0) == 1, W.prompt2.began)
	check("client: it does not let go before the prompt's hold time", (W.prompt2.ended or 0) == 0, W.prompt2.ended)
	advance(W, 1)
	check("client: then it lets go (InputHoldEnd once)", (W.prompt2.ended or 0) == 1, W.prompt2.ended)
	check("client: the tap holds the prompt at least its hold time (0.5 s), and not much longer (under 1 s)",
		(W.prompt2.heldFor or 0) >= 0.5 and (W.prompt2.heldFor or 99) < 1, W.prompt2.heldFor)
	check("client: after the hold the button reads the prompt's text again", titleText(W) == "Claim garage", titleText(W))
	fire(W, W.pps.PromptHidden, W.prompt1)
	check("client: another prompt hiding leaves the button", shown(W))
	fire(W, W.pps.PromptHidden, W.prompt2)
	check("client: the shown prompt hidden (walked away, garage taken) hides the button", not shown(W))
	tap(W)
	check("client: a tap with no prompt shown presses nothing", (W.prompt2.began or 0) == 1 and (W.prompt1.began or 0) == 0)
	fire(W, W.pps.PromptShown, W.prompt1, Enum.ProximityPromptInputType.Touch)
	check("client: the next garage's prompt shows the button with that garage", shown(W) and garageText(W) == "Garage 1", garageText(W))
	W.player:SetAttribute("Garage", 1)
	check("client: with a garage the button goes at once", not shown(W))
	tap(W)
	check("client: with a garage a tap presses nothing", (W.prompt1.began or 0) == 0, W.prompt1.began)
	check("client: it makes no remote and sends nothing", REMOTES == 0, REMOTES)
	ranClean(W, "on the plaza, then a garage")
end
do -- two claim prompts shown at once (two free garages side by side)
	local W = start(world(true, 0))
	local touch = Enum.ProximityPromptInputType.Touch
	fire(W, W.pps.PromptShown, W.prompt1, touch)
	fire(W, W.pps.PromptShown, W.prompt2, touch)
	check("client: two prompts with no character: the button names the newest shown", shown(W) and garageText(W) == "Garage 2", garageText(W))
	fire(W, W.pps.PromptHidden, W.prompt2)
	check("client: two prompts: the newer one hiding first leaves the button on the other", shown(W) and garageText(W) == "Garage 1", garageText(W))
	fire(W, W.pps.PromptHidden, W.prompt1)
	check("client: two prompts: the last one hiding hides the button", not shown(W))
	advance(W, 2)
	check("client: two prompts: no look is left pending once fewer than two show", #timers == 0, #timers)
	-- with a character: the nearest garage, not the newest
	local character = new("Model")
	local root = new("Part")
	root.Name = "HumanoidRootPart"
	root.Position = { X = 0, Y = 3, Z = 0 }
	root.Parent = character
	W.player.Character = character
	W.prompt1.Parent.Position = { X = 10, Y = 3, Z = 0 }
	W.prompt2.Parent.Position = { X = 40, Y = 3, Z = 0 }
	fire(W, W.pps.PromptShown, W.prompt1, touch)
	fire(W, W.pps.PromptShown, W.prompt2, touch)
	check("client: two prompts: the button names the nearest garage (not the newest)", shown(W) and garageText(W) == "Garage 1", garageText(W))
	tap(W)
	check("client: two prompts: the tap presses the nearest prompt", (W.prompt1.began or 0) == 1 and (W.prompt2.began or 0) == 0,
		tostring(W.prompt1.began) .. " / " .. tostring(W.prompt2.began))
	advance(W, 1)
	root.Position = { X = 38, Y = 3, Z = 0 } -- walked along the row
	advance(W, 0.6)
	check("client: two prompts: walking to the other garage moves the button to it within a second", shown(W) and garageText(W) == "Garage 2", garageText(W))
	tap(W)
	advance(W, 1)
	check("client: two prompts: then a tap presses that garage's prompt", (W.prompt2.began or 0) == 1 and (W.prompt2.ended or 0) == 1 and (W.prompt1.began or 0) == 1,
		tostring(W.prompt2.began) .. " / " .. tostring(W.prompt1.began))
	-- a garage reset while its prompt shows: the prompt leaves its post without a PromptHidden
	W.prompt2.Parent = nil
	advance(W, 0.6)
	check("client: two prompts: a prompt gone from its post is forgotten, the button goes back to the other", shown(W) and garageText(W) == "Garage 1", garageText(W))
	advance(W, 2)
	check("client: two prompts: and the looks stop (one prompt left)", #timers == 0, #timers)
	check("client: two prompts: it makes no remote", REMOTES == 0, REMOTES)
	ranClean(W, "two prompts")
end
do -- only touch, only claim prompts
	local W = start(world(true, 0))
	fire(W, W.pps.PromptShown, W.prompt1, Enum.ProximityPromptInputType.Keyboard)
	check("client: a claim prompt shown for keyboard (a computer: the E key) shows no button", not shown(W))
	fire(W, W.pps.PromptShown, W.other, Enum.ProximityPromptInputType.Touch)
	check("client: another prompt (the VIP door) shows no button", not shown(W))
	fire(W, W.pps.PromptShown, W.loose, Enum.ProximityPromptInputType.Touch)
	check("client: a ClaimPost outside a ClaimSpot shows no button", not shown(W))
	tap(W)
	check("client: a tap then presses nothing", (W.other.began or 0) == 0 and (W.loose.began or 0) == 0 and (W.prompt1.began or 0) == 0)
	ranClean(W, "keyboard and other prompts")
end
do -- the claim off
	local W = start(world(false, 0))
	fire(W, W.pps.PromptShown, W.prompt1, Enum.ProximityPromptInputType.Touch)
	check("client: with the claim off it builds nothing", W.gui == nil)
	ranClean(W, "the claim off")
end
do -- the button's place on the real screen matches the layout
	local W = start(world(true, 0))
	local r = (LAYOUT)()(390, 800)
	check("client: the button is placed by buttonLayout (390x800)", W.button ~= nil and W.button.Position.X.Offset == r.x and W.button.Position.Y.Offset == r.y
		and W.button.Size.X.Offset == r.w and W.button.Size.Y.Offset == r.h)
	W.gui._props.AbsoluteSize = vec2(667, 339)
	local sig = W.gui._propSignals.AbsoluteSize
	if sig then fire(W, sig) end
	local r2 = (LAYOUT)()(667, 339)
	check("client: a new screen size moves the button (667x339)", W.button ~= nil and W.button.Position.X.Offset == r2.x and W.button.Position.Y.Offset == r2.y
		and W.button.Size.X.Offset == r2.w)
	ranClean(W, "the screen size")
end

-- The layout at the phone sizes the HUD tests use, and two more, with top bars of 0, 36 and 58 px
do
	local layout = (LAYOUT)()
	local sizes = { { 667, 375 }, { 320, 568 }, { 568, 320 }, { 640, 360 }, { 844, 390 }, { 390, 844 }, { 1024, 768 } }
	for _, s in ipairs(sizes) do
		for _, bar in ipairs({ 0, 36, 58 }) do
			local w, h = s[1], s[2] - bar
			local r = layout(w, h)
			local label = string.format("%dx%d, top bar %d", s[1], s[2], bar)
			check("layout: the button is on the screen (" .. label .. ")", r.x >= 0 and r.y >= 0 and r.x + r.w <= w and r.y + r.h <= h, string.format("%d,%d %dx%d", r.x, r.y, r.w, r.h))
			check("layout: the button is a big touch target, at least 200 x 48 (" .. label .. ")", r.w >= 200 and r.h >= 48, string.format("%dx%d", r.w, r.h))
			-- Roblox's touch controls: thumbstick x < 170 and y > H-170; jump x > W-150 and y > H-130
			local inThumb = r.x < 170 and r.y + r.h > h - 170
			local inJump = r.x + r.w > w - 150 and r.y + r.h > h - 130
			check("layout: clear of the thumbstick and the jump button (" .. label .. ")", not inThumb and not inJump, string.format("%d,%d %dx%d", r.x, r.y, r.w, r.h))
			-- The Shop's pop-up lane (the server's "why not" messages): bottom -16, 48 high, centered, up to 300 wide
			local laneTop, laneBottom = h - 64, h - 16
			local lw = math.min(300, w * 0.6)
			local laneLeft, laneRight = (w - lw) / 2, (w + lw) / 2
			local overLane = r.y + r.h > laneTop and r.y < laneBottom and r.x + r.w > laneLeft and r.x < laneRight
			check("layout: clear of the Shop's pop-up lane, so a refusal stays readable (" .. label .. ")", not overLane, string.format("%d,%d %dx%d", r.x, r.y, r.w, r.h))
		end
	end
end
print_real(string.format("%d passed, %d failed", passed, failed))
print_real("DONE")
