-- The real LobbyClient.lua against a fake client (lobby L3): garages with claim posts (in each garage's ClaimSpot model)
-- and State attributes, the player's Garage attribute, a Heartbeat the test fires. It must show the banner and the marker
-- only on the plaza, with the claim on. Each scenario has its own "ran without an error" check, and no other check reads
-- the error: a mutant counts only when a check about what the client shows fails (tools/lobby_test.py).
local print_real = print
local passed, failed = 0, 0
local function check(name, cond, extra)
	if cond then passed += 1 else failed += 1; print_real("FAIL: " .. name .. (extra ~= nil and (" -- " .. tostring(extra)) or "")) end
end
local V = {}
V.__index = function(t, k) if k == "Magnitude" then return math.sqrt(t.X * t.X + t.Y * t.Y + t.Z * t.Z) end return nil end
local function vec(x, y, z) return setmetatable({ X = x, Y = y, Z = z }, V) end
V.__sub = function(a, b) return vec(a.X - b.X, a.Y - b.Y, a.Z - b.Z) end
local Vector3 = { new = function(x, y, z) return vec(x or 0, y or 0, z or 0) end }
local function signal()
	local s = { handlers = {} }
	function s.Connect(self, fn) table.insert(self.handlers, fn) return { Disconnect = function() end } end
	function s.Fire(self, ...) for _, fn in ipairs(self.handlers) do fn(...) end end
	return s
end
local REMOTES = 0
local Mt = {}
local M = {}
Mt.__index = function(t, k)
	if k == "Parent" then return rawget(t, "_parent") end
	local p = rawget(t, "_props")
	if p[k] ~= nil then return p[k] end
	if M[k] then return M[k] end
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
	if class == "RemoteEvent" or class == "RemoteFunction" then REMOTES += 1 end
	local o = setmetatable({ ClassName = class, _children = {}, _attrs = {}, _attrSignals = {}, _props = { Name = class } }, Mt)
	if class == "ScreenGui" then o._props.AbsoluteSize = vec(390, 800) end -- a phone, portrait
	if class == "TextButton" then o._props.Activated = signal() end -- the welcome card's button
	return o
end
function M.FindFirstChild(t, n) for _, c in ipairs(t._children) do if c.Name == n then return c end end return nil end
function M.WaitForChild(t, n) return t:FindFirstChild(n) end
function M.GetChildren(t) return table.clone(t._children) end
function M.SetAttribute(t, k, v) t._attrs[k] = v if t._attrSignals[k] then t._attrSignals[k]:Fire() end end
function M.GetAttribute(t, k) return t._attrs[k] end
function M.GetAttributeChangedSignal(t, k) t._attrSignals[k] = t._attrSignals[k] or signal() return t._attrSignals[k] end
function M.GetPropertyChangedSignal() return signal() end
local Instance = { new = new }
local function udim2(xs, xo, ys, yo) return { X = { Scale = xs, Offset = xo }, Y = { Scale = ys, Offset = yo } } end
local UDim2 = { fromOffset = function(x, y) return udim2(0, x, 0, y) end, fromScale = function(x, y) return udim2(x, 0, y, 0) end, new = udim2 }
local UDim = { new = function(a, b) return { a, b } end }
local Color3 = { fromRGB = function(r, g, b) return { r, g, b } end }
local Vector2 = { new = function(x, y) return { X = x, Y = y } end }
local Enum = { Font = { GothamBold = "GothamBold", Gotham = "Gotham" }, TextXAlignment = { Left = "Left" }, TextYAlignment = { Top = "Top" } }

local function world(claimOn, garageAttr)
	local W = { heartbeat = signal() }
	W.workspace = new("Workspace")
	local garages = new("Folder")
	garages.Name = "Garages"
	garages.Parent = W.workspace
	for slot, spot in ipairs({ { 10, 0 }, { 40, 0 }, { 80, 0 } }) do
		local g = new("Model")
		g.Name = "Garage" .. slot
		g:SetAttribute("State", slot == 1 and "Taken" or "Free")
		local claimSpot = new("Model")
		claimSpot.Name = "ClaimSpot"
		claimSpot.Parent = g
		local post = new("Part")
		post.Name = "ClaimPost"
		post.Position = vec(spot[1], 0, spot[2])
		post.Parent = claimSpot
		-- the server's FREE sign, prompt and lamp, as TycoonCore's setGarageState leaves them for this State
		local free = slot ~= 1
		local sign = new("BillboardGui")
		sign.Enabled = free
		sign.Parent = post
		local prompt = new("ProximityPrompt")
		prompt.Enabled = free
		prompt.Parent = post
		local lamp = new("Part")
		lamp.Name = "FreeLamp"
		lamp.Transparency = free and 0 or 1
		lamp.Parent = claimSpot
		W["sign" .. slot], W["prompt" .. slot], W["lamp" .. slot] = sign, prompt, lamp
		g.Parent = garages
		W["post" .. slot] = post
		W["garage" .. slot] = g
	end
	W.player = new("Player")
	local pg = new("PlayerGui")
	pg.Name = "PlayerGui"
	pg.Parent = W.player
	W.player:SetAttribute("Garage", garageAttr)
	local root = new("Part")
	root.Name = "HumanoidRootPart"
	root.Position = vec(0, 0, 0)
	local ch = new("Model")
	root.Parent = ch
	W.player.Character = ch
	W.root = root
	local rs = new("ReplicatedStorage")
	local lobby = (LOBBY_SOURCE)()
	lobby.ClaimEnabled = claimOn
	local cfg = new("ModuleScript")
	cfg.Name = "LobbyConfig"
	cfg._props.module = lobby
	cfg.Parent = rs
	local services = { Players = { LocalPlayer = W.player }, ReplicatedStorage = rs, RunService = { Heartbeat = W.heartbeat } }
	W.game = { GetService = function(_, n) return services[n] end }
	W.require = function(m) return m.module end
	return W
end
local function start(W)
	local ok, err = pcall(CLIENT, W.game, W.workspace, Instance, W.require, UDim2, UDim, Color3, Enum, Vector3, Vector2)
	W.err = not ok and err or nil
	W.gui = W.player.PlayerGui:FindFirstChild("LobbyGui")
	W.marker = W.player.PlayerGui:FindFirstChild("FreeGarageMarker")
	return W
end
-- A Heartbeat handler that errors is caught here, like Roblox does (the frame goes on, the error is noted)
local function frames(W, n)
	for _ = 1, n do
		local ok, err = pcall(W.heartbeat.Fire, W.heartbeat, 0.1)
		if not ok and not W.err then W.err = err end
	end
end
local function ranClean(W, label) check("client: ran without an error (" .. label .. ")", W.err == nil, W.err) end
local function shown(x) return x ~= nil and x.Enabled == true end

do
	local W = start(world(true, 0))
	frames(W, 6)
	local banner = W.gui and W.gui:FindFirstChild("Banner")
	check("client: on the plaza with the claim on, the banner shows the plaza text", shown(W.gui) and banner ~= nil
		and banner.Text == "Walk to a free garage to start your company")
	check("client: the marker is a BillboardGui straight in PlayerGui (a BillboardGui inside a ScreenGui never shows), kept on respawn",
		W.marker ~= nil and W.marker.ClassName == "BillboardGui" and W.marker.Parent == W.player.PlayerGui and W.marker.ResetOnSpawn == false)
	check("client: the marker is over the nearest FREE garage's post (garage 1 is nearer but Taken)", shown(W.marker) and W.marker.Adornee == W.post2)
	W.root.Position = vec(79, 0, 0)
	frames(W, 6)
	check("client: walking on, the marker moves to the garage now nearest", W.marker ~= nil and W.marker.Adornee == W.post3)
	W.garage3:SetAttribute("State", "MovingIn")
	frames(W, 6)
	check("client: a garage someone is moving into is no longer marked", W.marker ~= nil and W.marker.Adornee == W.post2)
	check("client: on the plaza the other garages' FREE signs, prompts and lamps stay as the server set them",
		W.sign2.Enabled == true and W.prompt2.Enabled == true and W.lamp2.Transparency == 0 and W.sign1.Enabled == false and W.prompt1.Enabled == false and W.lamp1.Transparency == 1)
	local welcome = W.gui and W.gui:FindFirstChild("Welcome")
	check("client: on the plaza the welcome card shows the story under the banner, with a Got it button (overhaul phase 4)",
		welcome ~= nil and welcome.Visible == true and welcome:FindFirstChild("Body") ~= nil and string.find(welcome.Body.Text, "Go public (IPO)", 1, true) ~= nil
		and welcome:FindFirstChild("GotIt") ~= nil and welcome.Position.Y.Offset > W.gui.Banner.Position.Y.Offset)
	welcome.GotIt.Activated:Fire()
	check("client: Got it hides the welcome card for the session", welcome.Visible == false)
	W.player:SetAttribute("Garage", 2)
	check("client: with a garage the banner and the marker go at once", W.gui ~= nil and W.gui.Enabled == false and W.marker ~= nil and W.marker.Enabled == false)
	check("client: with a garage every FREE sign, prompt and lamp is hidden on this client (the server still refuses a second claim)",
		W.sign2.Enabled == false and W.prompt2.Enabled == false and W.lamp2.Transparency == 1 and W.sign3.Enabled == false and W.prompt3.Enabled == false and W.lamp3.Transparency == 1)
	check("client: it makes no remote and sends nothing", REMOTES == 0)
	ranClean(W, "on the plaza, then a garage")
end
do
	local W = start(world(false, 0))
	frames(W, 6)
	check("client: with the claim off it shows nothing (no LobbyGui, no marker)", W.gui == nil and W.marker == nil)
	ranClean(W, "the claim off")
end
do
	local W = start(world(true, 0))
	W.garage2:SetAttribute("State", "Taken")
	W.garage3:SetAttribute("State", "Closing")
	W.sign2.Enabled, W.prompt2.Enabled, W.lamp2.Transparency = false, false, 1 -- as the server sets a Taken garage
	W.prompt3.Enabled, W.lamp3.Transparency = false, 1 -- a Closing garage: the sign stays, saying Closing
	frames(W, 6)
	check("client: no Free garage: the banner stays, no marker", shown(W.gui) and W.marker ~= nil and W.marker.Enabled == false)
	check("client: on the plaza a Closing garage keeps its sign and a Taken one shows nothing (the server's values, untouched)",
		W.sign3.Enabled == true and W.prompt3.Enabled == false and W.lamp3.Transparency == 1 and W.sign2.Enabled == false)
	ranClean(W, "no Free garage")
end
print_real(string.format("%d passed, %d failed", passed, failed))
print_real("DONE")
