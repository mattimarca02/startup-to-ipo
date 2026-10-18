-- The whole real TycoonCore.lua, run in a fake Roblox with a clock the test moves (lobby L3). Each scenario boots a fresh
-- server: its own players, DataStore (with a read and a write delay, and failures), modules and scheduler. The receipt
-- scenarios (section 7) also run the real ShopServer.lua and ShopConfig.lua, wired to TycoonCore as in the game.
local print_real = print
local passed, failed = 0, 0
local function check(name, cond, extra)
	if cond then passed += 1 else failed += 1; print_real("FAIL: " .. name .. (extra ~= nil and (" -- " .. tostring(extra)) or "")) end
end

-- Vectors and frames (enough of Roblox's for TycoonCore) ----------------------------------------------------------
local V = {}
V.__index = function(t, k) if k == "Magnitude" then return math.sqrt(t.X * t.X + t.Y * t.Y + t.Z * t.Z) end return V[k] end
local function vec(x, y, z) return setmetatable({ X = x, Y = y, Z = z }, V) end
V.__add = function(a, b) return vec(a.X + b.X, a.Y + b.Y, a.Z + b.Z) end
V.__sub = function(a, b) return vec(a.X - b.X, a.Y - b.Y, a.Z - b.Z) end
V.__mul = function(a, b) if type(a) == "number" then return vec(a * b.X, a * b.Y, a * b.Z) end return vec(a.X * b, a.Y * b, a.Z * b) end
local Vector3 = { new = function(x, y, z) return vec(x or 0, y or 0, z or 0) end }
local CF = {}
local function cf(x, y, z, r) return setmetatable({ x = x, y = y, z = z, r = r or { 1, 0, 0, 0, 1, 0, 0, 0, 1 } }, CF) end
local function matmul(a, b)
	local m = {}
	for i = 0, 2 do for j = 0, 2 do m[i * 3 + j + 1] = a[i * 3 + 1] * b[j + 1] + a[i * 3 + 2] * b[j + 4] + a[i * 3 + 3] * b[j + 7] end end
	return m
end
CF.__index = function(t, k)
	if k == "Position" then return vec(t.x, t.y, t.z) end
	if k == "Rotation" then return cf(0, 0, 0, t.r) end
	return CF[k]
end
CF.__mul = function(a, b)
	local r = a.r
	if getmetatable(b) == V then
		return vec(r[1] * b.X + r[2] * b.Y + r[3] * b.Z + a.x, r[4] * b.X + r[5] * b.Y + r[6] * b.Z + a.y, r[7] * b.X + r[8] * b.Y + r[9] * b.Z + a.z)
	end
	return cf(r[1] * b.x + r[2] * b.y + r[3] * b.z + a.x, r[4] * b.x + r[5] * b.y + r[6] * b.z + a.y, r[7] * b.x + r[8] * b.y + r[9] * b.z + a.z, matmul(r, b.r))
end
local CFrame = {
	new = function(x, y, z, ...)
		if type(x) == "table" then return cf(x.X, x.Y, x.Z) end
		if select("#", ...) == 9 then return cf(x, y, z, { ... }) end
		return cf(x or 0, y or 0, z or 0)
	end,
	lookAt = function(at, target) return cf(at.X, at.Y, at.Z) end,
	Angles = function() return cf(0, 0, 0) end,
}
local function typeof(v)
	local mt = getmetatable(v)
	if mt == CF then return "CFrame" elseif mt == V then return "Vector3" end
	if type(v) == "table" and rawget(v, "_children") then return "Instance" end
	return type(v)
end
-- What a DataStore keeps: a full copy (like Roblox's, which serializes), never a table the game still holds
local function deepCopy(v)
	if type(v) ~= "table" then return v end
	local out = {}
	for k, x in pairs(v) do out[deepCopy(k)] = deepCopy(x) end
	return out
end
local function enum(names) local t = {} for _, n in ipairs(names) do t[n] = { Name = n } end return t end
local Enum = { Material = enum({ "SmoothPlastic", "Metal", "Neon", "Plastic", "Marble", "Concrete", "Glass", "Fabric" }), SurfaceType = enum({ "Smooth" }),
	Font = enum({ "GothamBold" }), NormalId = enum({ "Back", "Front" }), ModelStreamingMode = enum({ "Default", "Atomic", "Persistent" }),
	ProductPurchaseDecision = enum({ "PurchaseGranted", "NotProcessedYet" }) }
local GRANTED, NOT_YET = Enum.ProductPurchaseDecision.PurchaseGranted, Enum.ProductPurchaseDecision.NotProcessedYet
local Color3 = { fromRGB = function(r, g, b) return { r, g, b } end, new = function(r, g, b) return { r, g, b } end }
local UDim2 = { fromOffset = function(x, y) return { x, y } end, fromScale = function(x, y) return { x, y } end }

-- One world: a scheduler, Instances, players, a DataStore, the modules -------------------------------------------------
local function newWorld(opts)
	opts = opts or {}
	local W = { NOW = 1000, timers = {}, seq = 0, crashes = {}, warns = {}, kicks = {}, notes = {}, store = opts.save or {}, reads = 0, writes = {},
		readDelay = opts.readDelay or 0.3, writeDelay = opts.writeDelay or 0.3, readFail = false, writeFail = false, players = {} }
	local function schedule(at, co, ...) W.seq += 1 table.insert(W.timers, { at = at, seq = W.seq, co = co, args = table.pack(...) }) end
	local function resume(co, ...)
		local ok, err = coroutine.resume(co, ...)
		if not ok then table.insert(W.crashes, tostring(err)) end
	end
	W.task = {
		wait = function(s) s = math.max(s or 0.03, 0.001) schedule(W.NOW + s, coroutine.running()) coroutine.yield() return s end,
		spawn = function(f, ...) resume(type(f) == "thread" and f or coroutine.create(f), ...) end,
		delay = function(s, f, ...) schedule(W.NOW + s, coroutine.create(f), ...) end,
		defer = function(f, ...) schedule(W.NOW, coroutine.create(f), ...) end,
	}
	W.os = { clock = function() return W.NOW end, time = function() return math.floor(W.NOW) end, date = os.date }
	function W.run(seconds)
		local stop = W.NOW + seconds
		while true do
			table.sort(W.timers, function(a, b) if a.at ~= b.at then return a.at < b.at end return a.seq < b.seq end)
			local t = W.timers[1]
			if not t or t.at > stop then break end
			table.remove(W.timers, 1)
			if t.at > W.NOW then W.NOW = t.at end
			resume(t.co, table.unpack(t.args, 1, t.args.n))
		end
		W.NOW = stop
	end
	W.go = function(f, ...) resume(coroutine.create(f), ...) end
	W.warn = function(...) table.insert(W.warns, table.concat({ ... }, " ")) end

	local function signal()
		local s = { handlers = {}, waiting = {} }
		function s.Connect(self, fn) local c = { fn = fn, on = true } function c.Disconnect() c.on = false end table.insert(self.handlers, c) return c end
		function s.Fire(self, ...)
			for _, c in ipairs(table.clone(self.handlers)) do if c.on then W.go(c.fn, ...) end end
			local waiting = self.waiting
			self.waiting = {}
			for _, co in ipairs(waiting) do resume(co, ...) end
		end
		function s.Wait(self) table.insert(self.waiting, coroutine.running()) return coroutine.yield() end
		return s
	end
	W.signal = signal

	local Mt = {}
	local M = {}
	Mt.__index = function(t, k)
		if k == "Parent" then return rawget(t, "_parent") end
		local p = rawget(t, "_props")
		if k == "Position" and p.CFrame then return p.CFrame.Position end
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
			if v then table.insert(v._children, t) local s = rawget(v, "_childAdded") if s then s:Fire(t) end end
			return
		end
		local p = rawget(t, "_props")
		if k == "Position" then p.CFrame = cf(v.X, v.Y, v.Z) return end
		p[k] = v
	end
	local function new(class)
		local o = setmetatable({ ClassName = class, _children = {}, _attrs = {}, _props = { Name = class } }, Mt)
		if class == "Part" then o._props.CFrame = cf(0, 0, 0) o._props.Transparency = 0 o._props.CanCollide = true end
		if class == "IntValue" then o._props.Value = 0 end
		if class == "ProximityPrompt" then o._props.Triggered = signal() o._props.Enabled = true end
		if class == "BillboardGui" then o._props.Enabled = true end
		if class == "Model" then o._props.ModelStreamingMode = Enum.ModelStreamingMode.Default end
		if class == "RemoteEvent" then -- ShopServer's pop-up messages (the real ShopServer's notify)
			o._props.FireClient = function(_, player, text) table.insert(W.notes, { player = player, text = text }) end
		end
		return o
	end
	W.new = new
	function M.GetChildren(t) return table.clone(t._children) end
	function M.FindFirstChild(t, name) for _, c in ipairs(t._children) do if c.Name == name then return c end end return nil end
	function M.FindFirstChildOfClass(t, class) for _, c in ipairs(t._children) do if c.ClassName == class then return c end end return nil end
	function M.WaitForChild(t, name, timeout)
		local c = t:FindFirstChild(name)
		if c or timeout then return c end
		while not c do t.ChildAdded:Wait() c = t:FindFirstChild(name) end
		return c
	end
	function M.SetAttribute(t, k, v) t._attrs[k] = v end
	function M.GetAttribute(t, k) return t._attrs[k] end
	function M.Destroy(t) t.Parent = nil rawset(t, "destroyed", true) end
	function M.IsA(t, class) return t.ClassName == class or (class == "BasePart" and t.ClassName == "Part") end
	function M.GetDescendants(t) local out = {} local function walk(n) for _, c in ipairs(n._children) do table.insert(out, c) walk(c) end end walk(t) return out end
	local oldIndex = Mt.__index
	local EVENTS = { DescendantAdded = true, Touched = true } -- events nothing here fires (ShopServer connects to them)
	Mt.__index = function(t, k)
		if k == "ChildAdded" then
			local s = rawget(t, "_childAdded")
			if not s then s = signal() rawset(t, "_childAdded", s) end
			return s
		end
		if EVENTS[k] then
			local events = rawget(t, "_events") or {}
			rawset(t, "_events", events)
			events[k] = events[k] or signal()
			return events[k]
		end
		return oldIndex(t, k)
	end

	-- Services
	W.workspace = new("Workspace")
	W.Players = new("Players")
	W.Players._props.PlayerAdded = signal()
	W.Players._props.PlayerRemoving = signal()
	W.Players._props.MaxPlayers = opts.maxPlayers or 6
	W.Players._props.GetPlayers = function() local out = {} for _, p in ipairs(W.players) do if p.Parent == W.Players then table.insert(out, p) end end return out end
	W.Players._props.GetPlayerFromCharacter = function(_, ch) for _, p in ipairs(W.players) do if p.Character == ch then return p end end return nil end
	W.Players._props.GetPlayerByUserId = function(_, id) for _, p in ipairs(W.players) do if p.Parent == W.Players and p.UserId == id then return p end end return nil end
	W.store_api = {
		GetAsync = function(_, key)
			W.reads += 1
			W.task.wait(W.readDelay)
			if W.readFail then error("read failed (test)") end
			return deepCopy(W.store[key])
		end,
		SetAsync = function(_, key, value)
			W.task.wait(W.writeDelay)
			if W.writeFail then error("write failed (test)") end
			W.store[key] = deepCopy(value)
			table.insert(W.writes, { key = key, at = W.NOW, value = value })
		end,
	}
	local DataStoreService = { GetDataStore = function()
		if opts.noStore then error("no API access (test)") end -- Studio with API access off
		return W.store_api
	end }
	local RunService = { IsStudio = function() return opts.studio == true end }
	W.ReplicatedStorage = new("ReplicatedStorage")
	W.ServerScriptService = new("ServerScriptService")
	-- What the real ShopServer asks Roblox: nobody owns a pass, paid random items are allowed, products are the receipts
	-- the test sends to MarketplaceService.ProcessReceipt (set by ShopServer.init)
	W.Marketplace = { PromptGamePassPurchaseFinished = signal(), UserOwnsGamePassAsync = function() return false end, PromptGamePassPurchase = function() end }
	local PolicyService = { GetPolicyInfoForPlayerAsync = function() return { ArePaidRandomItemsRestricted = false } end }
	local PhysicsService = { IsCollisionGroupRegistered = function() return true end, RegisterCollisionGroup = function() end, CollisionGroupSetCollidable = function() end }
	local guids = 0
	local HttpService = { GenerateGUID = function() guids += 1 return "GUID-" .. guids end }
	local services = { Players = W.Players, DataStoreService = DataStoreService, ReplicatedStorage = W.ReplicatedStorage, RunService = RunService,
		ServerScriptService = W.ServerScriptService, Workspace = W.workspace, MarketplaceService = W.Marketplace, PolicyService = PolicyService,
		PhysicsService = PhysicsService, HttpService = HttpService }
	W.game = { GetService = function(_, name) return services[name] or error("no service " .. name) end, BindToClose = function(_, fn) W.closeFn = fn end }

	-- Modules: real IpoConfig and LobbyConfig, fake server modules that fill their save section (opts.realShop: the real
	-- ShopServer and ShopConfig instead of the fake shop; opts.brokenBuilding: a PlotBuildingVisuals whose sync errors)
	local function module(parent, name, value, loader)
		local m = new("ModuleScript")
		m.Name = name
		m._module = value
		m._loader = loader
		m.Parent = parent
	end
	local lobby = (LOBBY_SOURCE)()
	lobby.ClaimEnabled = opts.claim == true
	lobby.Garages = lobby.garages(lobby.ClaimEnabled)
	W.LobbyConfig = lobby
	module(W.ReplicatedStorage, "IpoConfig", (IPOCONFIG_SOURCE)())
	module(W.ReplicatedStorage, "LobbyConfig", lobby)
	local sections = { ShopServer = "shop", EmployeeServer = "team", PoachServer = "poach", IpoServer = "ipo", OnboardingServer = "onboarding",
		DailyServer = "daily", TaskServer = "tasks", CompanyServer = "pokedex" }
	if opts.realShop then
		sections.ShopServer = nil
		W.ShopConfig = (SHOPCONFIG_SOURCE)()
		module(W.ReplicatedStorage, "ShopConfig", W.ShopConfig)
		module(W.ServerScriptService, "ShopServer", nil, function()
			return SHOP_SOURCE(W.game, W.script, W.workspace, W.task, W.os, W.warn, W.require, function(class) return new(class) end,
				Enum, Vector3, CFrame, Color3, UDim2, typeof)
		end)
	end
	if opts.brokenBuilding then
		module(W.ServerScriptService, "PlotBuildingVisuals", { sync = function() error("the building broke (test)") end, unstick = function() return 0 end })
		module(W.ServerScriptService, "PlotBuilding", { KIT_FOLDER = "KitModels" })
	end
	W.mods = {}
	for name, section in pairs(sections) do
		local m = {}
		m.init = function(core) m.core = core end
		m.setupPlayer = function(player, data, saved)
			data[section] = type(saved) == "table" and table.clone(saved) or {}
			if section == "ipo" then
				data.ipo.count = data.ipo.count or 0
				data.ipo.valuation = data.ipo.valuation or 0
			end
			if opts.failSetup and name == "DailyServer" then error("setup failed (test)") end
		end
		m.serialize = function(data) return data[section] end
		setmetatable(m, { __index = function() return function() return nil end end })
		W.mods[name] = m
		module(W.ServerScriptService, name, m)
	end
	if W.mods.ShopServer then
		W.mods.ShopServer.notify = function(player, text) table.insert(W.notes, { player = player, text = text }) end
		W.mods.ShopServer.getCashMultiplier = function() return 1 end
	end
	W.mods.IpoServer.getMultiplier = function() return 1 end
	W.mods.IpoServer.perk = function() return 0 end
	W.mods.EmployeeServer.getIncome = function() return 0 end
	W.mods.EmployeeServer.countEggs = function() return 0 end
	W.require = function(m)
		if not m then error("require of nothing") end
		if m._loader then -- a real module's source: run once, like Roblox's require
			m._module = m._loader()
			m._loader = nil
		end
		return m._module
	end
	W.script = { Parent = W.ServerScriptService }

	-- Players and characters
	function W.character(at)
		local ch = new("Model")
		ch.Name = "Character"
		local root = new("Part")
		root.Name = "HumanoidRootPart"
		root.CFrame = cf(at.X, at.Y, at.Z)
		root.Parent = ch
		return ch, root
	end
	function W.join(name, userId, spawnAt)
		local p = new("Player")
		p.Name, p.DisplayName, p.UserId = name, name, userId
		p.CharacterAdded = signal()
		p.Kick = function(self, msg) W.kicks[self] = msg W.task.defer(function() W.leave(self) end) end
		table.insert(W.players, p)
		p.Parent = W.Players
		W.Players.PlayerAdded:Fire(p)
		if spawnAt then
			local ch = W.character(spawnAt)
			p.Character = ch
			p.CharacterAdded:Fire(ch)
		end
		return p
	end
	function W.leave(p)
		if p.Parent ~= W.Players then return end
		W.Players.PlayerRemoving:Fire(p)
		p.Parent = nil
	end
	function W.boot()
		local ok, hooks = pcall(BOOT_CORE, W.game, W.script, W.workspace, W.task, W.os, W.warn, W.require, function(class) return new(class) end,
			Enum, Vector3, CFrame, Color3, UDim2, typeof)
		if not ok then table.insert(W.crashes, "boot: " .. tostring(hooks)) return nil end
		W.H = hooks
		return hooks
	end
	return W
end

local function noteFor(W, p) local out = {} for _, n in ipairs(W.notes) do if n.player == p then table.insert(out, n.text) end end return out end
local function lastNote(W, p) local n = noteFor(W, p) return n[#n] end
local function garage(W, slot) return W.workspace:FindFirstChild("Garages"):FindFirstChild("Garage" .. slot) end
local function postOf(W, slot) return garage(W, slot):FindFirstChild("ClaimSpot"):FindFirstChild("ClaimPost") end
local function promptOf(W, slot) return postOf(W, slot):FindFirstChildOfClass("ProximityPrompt") end
local function nearPost(W, slot) return postOf(W, slot).Position + Vector3.new(3, 0, 0) end
local function hold(W, p, slot) promptOf(W, slot).Triggered:Fire(p) end
local function stateOf(W, slot) return garage(W, slot):GetAttribute("State") end
local function noCrash(W, label) check(label .. ": no error in the server (" .. #W.crashes .. ")", #W.crashes == 0, W.crashes[1]) end
-- A player's leaderstats value, nil-safe (a broken TycoonCore may make a second, empty leaderstats: the test must not crash)
local function stat(p, name)
	for _, c in ipairs(p:GetChildren()) do
		if c.Name == "leaderstats" and c:FindFirstChild(name) then return c:FindFirstChild(name) end
	end
	return nil
end
local function cashOf(p) local v = stat(p, "Cash") return v and v.Value or -1 end
local function setCash(p, value) local v = stat(p, "Cash") if v then v.Value = value end end
local PLAZA = Vector3.new(0, 4, 175)
-- A player on the plaza walks up to a garage's claim post
local function walkTo(W, p, slot)
	local at = nearPost(W, slot)
	p.Character.HumanoidRootPart.CFrame = CFrame.new(at.X, at.Y, at.Z)
end

-- 1. Claim on: the join only enters the plaza; a near hold claims; the save loads in the claim ---------------------------
do
	local W = newWorld({ claim = true, save = { player_11 = { cash = 500, owned = { "Desk" }, lastSeen = 0 } } })
	W.boot()
	local H = W.H
	check("plaza: the server starts with six Free garages, each with its prompt on", (function()
		for s = 1, 6 do if stateOf(W, s) ~= "Free" or not promptOf(W, s).Enabled then return false end end return true end)())
	check("plaza: each garage's claim post and lamp stand in its ClaimSpot, a Persistent model (with streaming on every client has every post)",
		(function()
			for s = 1, 6 do
				local spot = garage(W, s):FindFirstChild("ClaimSpot")
				if not (spot and spot.ModelStreamingMode == Enum.ModelStreamingMode.Persistent and spot:FindFirstChild("ClaimPost") and spot:FindFirstChild("FreeLamp")) then return false end
				if garage(W, s):FindFirstChild("ClaimPost") or garage(W, s):FindFirstChild("FreeLamp") then return false end
			end
			return true
		end)())
	local ana = W.join("Ana", 11, Vector3.new(-1, 3, -1))
	W.run(0.5)
	check("plaza: a joining player gets no garage, no leaderstats, no data, and nothing is read", H.inPlaza[ana] == true and H.playerData[ana] == nil
		and ana:FindFirstChild("leaderstats") == nil and W.reads == 0 and ana:GetAttribute("Garage") == 0)
	local root = ana.Character:FindFirstChild("HumanoidRootPart")
	check("plaza: a first spawn far from the plaza (the SpawnLocation not moved) is put on the plaza", (root.Position - PLAZA).Magnitude < 0.01, tostring(root.Position.Z))
	-- far from the door: refused with a message, nothing claimed
	hold(W, ana, 3)
	W.run(0.1)
	check("distance: a hold from the plaza (far from the post) is refused and claims nothing", H.playerData[ana] == nil and lastNote(W, ana) == W.LobbyConfig.Texts.Far
		and stateOf(W, 3) == "Free", lastNote(W, ana))
	walkTo(W, ana, 3)
	hold(W, ana, 3)
	W.run(0.1)
	check("rate: a second request within a second is refused (too fast)", H.playerData[ana] == nil and lastNote(W, ana) == W.LobbyConfig.Texts.TooFast, lastNote(W, ana))
	W.run(1.2)
	hold(W, ana, 3)
	W.run(0.05)
	check("claim: a near hold claims: the claim is held by the account, the garage is Moving in, leaderstats made at the claim",
		H.claims[11] ~= nil and H.claims[11].slot == 3 and H.plotOwners[3] == ana and stateOf(W, 3) == "MovingIn" and ana:FindFirstChild("leaderstats") ~= nil
		and ana:GetAttribute("Garage") == 3 and H.inPlaza[ana] == nil)
	check("claim: the prompt goes off at once (no second claim of the garage)", promptOf(W, 3).Enabled == false)
	W.run(2)
	local data = H.playerData[ana]
	check("load: the save is read once in the claim and loaded (Cash 500, the Desk), data.loaded and data.ready set",
		data and data.loaded == true and data.ready == true and data.owned.Desk == true and cashOf(ana) >= 500 and W.reads == 1, W.reads)
	check("load: the garage shows Taken with the owner's name", stateOf(W, 3) == "Taken" and garage(W, 3):GetAttribute("OwnerName") == "Ana")
	check("load: the claim's player lands in their garage on the next spawn", (function()
		local ch, r = W.character(Vector3.new(0, 3, 175))
		ana.Character = ch
		ana.CharacterAdded:Fire(ch)
		W.run(0.5)
		local g = W.LobbyConfig.Garages[3] -- the claim is on: the ring (garage 3 faces -Z, toward the plaza)
		local land = Vector3.new(g.x, 4.5, g.z - 12) -- its landing: (0, 4, 12) in its frame, turned 180
		return (r.Position - land).Magnitude < 0.01
	end)())
	-- a second hold from the same player (on another garage) does nothing: one garage per account
	walkTo(W, ana, 4)
	hold(W, ana, 4)
	W.run(1.5)
	check("one claim: a player with a garage can't claim a second one", H.plotOwners[4] == nil and stateOf(W, 4) == "Free")
	-- leaving: Closing while the save runs, then Free, then the account may claim again
	W.writeDelay = 3
	W.leave(ana)
	W.run(0.5)
	check("leave: the garage shows Closing while the leave save runs, the slot stays taken and the claim held", stateOf(W, 3) == "Closing"
		and H.plotOwners[3] == ana and H.claims[11] ~= nil and H.claims[11].leaving == true)
	W.run(4)
	check("leave: when the save returns the garage is Free again (prompt on, no owner) and the claim released", stateOf(W, 3) == "Free"
		and promptOf(W, 3).Enabled == true and H.plotOwners[3] == nil and H.claims[11] == nil and H.playerData[ana] == nil)
	check("leave: the save was written once, with the session's Cash", #W.writes == 1 and W.store.player_11.cash >= 500, #W.writes)
	noCrash(W, "claim on")
end

-- 2. Two claims at once, distance edge cases, the cap ------------------------------------------------------------------
do
	local W = newWorld({ claim = true })
	W.boot()
	local H = W.H
	local a = W.join("Ana", 21, PLAZA)
	local b = W.join("Ben", 22, PLAZA)
	W.run(0.2)
	walkTo(W, a, 2)
	walkTo(W, b, 2)
	hold(W, a, 2)
	hold(W, b, 2)
	W.run(0.05)
	check("two claims in one moment: the first wins, the second is told who took it", H.plotOwners[2] == a and H.playerData[b] == nil
		and lastNote(W, b) == string.format(W.LobbyConfig.Texts.Taken, "Ana"), lastNote(W, b))
	W.run(1.5)
	-- no character, NaN and infinite positions: refused
	local c = W.join("Cid", 23)
	W.run(0.1)
	hold(W, c, 5)
	W.run(0.05)
	check("distance: no character is refused", H.playerData[c] == nil and lastNote(W, c) == W.LobbyConfig.Texts.Far)
	local ch = W.character(Vector3.new(0 / 0, 0, 0))
	c.Character = ch
	W.run(1.5)
	hold(W, c, 5)
	W.run(0.05)
	check("distance: a NaN position is refused", H.playerData[c] == nil and lastNote(W, c) == W.LobbyConfig.Texts.Far)
	ch.HumanoidRootPart.CFrame = CFrame.new(math.huge, 0, 0)
	W.run(1.5)
	hold(W, c, 5)
	W.run(0.05)
	check("distance: an infinite position is refused", H.playerData[c] == nil and lastNote(W, c) == W.LobbyConfig.Texts.Far)
	-- the cap: a 7th player is kicked, six are not
	for i = 1, 3 do W.join("P" .. i, 30 + i) end
	W.run(0.2)
	check("cap: six players in the server, nobody is kicked", next(W.kicks) == nil)
	local seventh = W.join("Seven", 40)
	W.run(0.2)
	check("cap: a 7th player (more players than garages) is kicked with the old text", W.kicks[seventh] == W.LobbyConfig.Texts.Full and seventh.Parent == nil)
	noCrash(W, "two claims")
end

-- 3. A rejoin while the old garage is Closing: the claim waits for the leave save ----------------------------------------
do
	local W = newWorld({ claim = true, save = { player_51 = { cash = 100, owned = {}, lastSeen = 0 } } })
	W.boot()
	local H = W.H
	local old = W.join("Dee", 51, PLAZA)
	W.run(0.2)
	walkTo(W, old, 1)
	hold(W, old, 1)
	W.run(3)
	setCash(old, 7777)
	W.writeDelay = 12 -- the leave save takes longer than the 7 s re-read
	W.leave(old)
	W.run(0.5)
	local again = W.join("Dee", 51, PLAZA)
	W.run(0.2)
	walkTo(W, again, 2)
	hold(W, again, 2)
	W.run(0.05)
	check("rejoin: while the old visit is still saving, the same account's claim is refused (keyed on the UserId)", H.playerData[again] == nil
		and lastNote(W, again) == W.LobbyConfig.Texts.Saving, lastNote(W, again))
	W.run(13)
	check("rejoin: the leave save returned, the old garage is Free, the account's claim released", stateOf(W, 1) == "Free" and H.claims[51] == nil)
	hold(W, again, 2)
	W.run(12)
	local data = H.playerData[again]
	check("rejoin: now the claim works, and its read sees the leave save (Cash 7777, not the older 100)", data and data.ready and cashOf(again) >= 7777,
		data and cashOf(again))
	noCrash(W, "rejoin")
end

-- 4. Leaving during the load, a failed load, a failed setup ------------------------------------------------------------------
do
	local W = newWorld({ claim = true, readDelay = 2, save = { player_61 = { cash = 3, owned = {}, lastSeen = 0 } } })
	W.boot()
	local H = W.H
	local p = W.join("Eve", 61, PLAZA)
	W.run(0.2)
	walkTo(W, p, 4)
	hold(W, p, 4)
	W.run(1)
	W.leave(p)
	W.run(5)
	check("leave during the load: nothing is saved, the garage is Free again, the claim released", #W.writes == 0 and stateOf(W, 4) == "Free"
		and H.plotOwners[4] == nil and H.claims[61] == nil and H.playerData[p] == nil)
	noCrash(W, "leave during load")
end
do
	local W = newWorld({ claim = true, readDelay = 0.2 })
	W.boot()
	local H = W.H
	W.readFail = true
	local p = W.join("Fay", 71, PLAZA)
	W.run(0.2)
	walkTo(W, p, 5)
	hold(W, p, 5)
	W.run(10)
	check("failed load: after three tries the player is kicked, nothing saved, the garage Free again", W.kicks[p] ~= nil and #W.writes == 0
		and stateOf(W, 5) == "Free" and H.plotOwners[5] == nil and H.claims[71] == nil)
	noCrash(W, "failed load")
end
do
	local W = newWorld({ claim = true, failSetup = true })
	W.boot()
	local H = W.H
	local p = W.join("Gus", 72, PLAZA)
	W.run(0.2)
	walkTo(W, p, 6)
	hold(W, p, 6)
	W.run(3)
	check("failed setup: the player is kicked, nothing saved, the garage Free again", W.kicks[p] ~= nil and #W.writes == 0 and stateOf(W, 6) == "Free"
		and H.claims[72] == nil)
	noCrash(W, "failed setup")
end

-- 5. Claim off (it ships off): today's behaviour through the same claim -------------------------------------------------------
do
	local W = newWorld({ claim = false, save = { player_81 = { cash = 42, owned = {}, lastSeen = 0 } } })
	W.boot()
	local H = W.H
	check("claim off: no prompt is on and no FREE sign shows", (function()
		for s = 1, 6 do if promptOf(W, s).Enabled or postOf(W, s):FindFirstChildOfClass("BillboardGui").Enabled then return false end end return true end)())
	local p = W.join("Hal", 81, Vector3.new(-1, 3, -1))
	W.run(0.05)
	check("claim off: the join claims the first free garage at once (leaderstats at the join, as before)", H.plotOwners[1] == p and p:FindFirstChild("leaderstats") ~= nil
		and H.inPlaza[p] == nil and p:GetAttribute("Garage") == 1)
	W.run(2)
	local root = p.Character:FindFirstChild("HumanoidRootPart")
	check("claim off: the player is sent into their garage (not left on the plaza)", (root.Position - Vector3.new(-225, 4.5, 162)).Magnitude < 0.01, tostring(root.Position.X))
	check("claim off: the save loads as before (Cash 42)", H.playerData[p] and H.playerData[p].ready and cashOf(p) >= 42)
	local others = {}
	for i = 2, 6 do table.insert(others, W.join("O" .. i, 90 + i)) end
	W.run(3)
	check("claim off: six players get the six garages", (function() for s = 1, 6 do if not H.plotOwners[s] then return false end end return true end)())
	-- one leaves with a slow save; someone joins: waits on the plaza, then gets the freed garage
	W.writeDelay = 5
	W.leave(others[2])
	W.run(0.5)
	local late = W.join("Late", 99)
	W.run(0.5)
	check("claim off, all taken (one closing): the joiner waits on the plaza, not kicked", H.inPlaza[late] == true and W.kicks[late] == nil)
	W.run(8)
	check("claim off: when the leave save returns, the joiner gets the freed garage", H.plotOwners[3] == late and W.kicks[late] == nil)
	noCrash(W, "claim off")
end
do
	local W = newWorld({ claim = false })
	W.boot()
	local H = W.H
	local ps = {}
	for i = 1, 6 do table.insert(ps, W.join("Q" .. i, 100 + i)) end
	W.run(2)
	W.writeDelay = 100
	W.leave(ps[1])
	W.run(0.5)
	local late = W.join("Late", 120)
	W.run(30)
	check("claim off: after 30 s with no free garage the joiner still waits", late.Parent ~= nil and W.kicks[late] == nil)
	W.run(32)
	check("claim off: after 60 s with no free garage, the old \"server is full\" kick", W.kicks[late] == W.LobbyConfig.Texts.Full)
	noCrash(W, "60 s kick")
end

-- 6. Joined while the script started: set up once ---------------------------------------------------------------------
do
	local W = newWorld({ claim = false })
	local p = W.new("Player")
	p.Name, p.DisplayName, p.UserId = "Early", "Early", 130
	p.CharacterAdded = W.signal()
	p.Kick = function(self, msg) W.kicks[self] = msg end
	table.insert(W.players, p)
	p.Parent = W.Players
	-- Roblox may fire PlayerAdded for them too, once the script has connected
	W.Players.PlayerAdded.Connect = (function(orig) return function(self, fn) local c = orig(self, fn) W.task.defer(fn, p) return c end end)(W.Players.PlayerAdded.Connect)
	W.boot()
	local H = W.H
	W.run(65)
	local owned = 0
	for s = 1, 6 do if H.plotOwners[s] == p then owned += 1 end end
	check("early joiner: a player already in the server when the script starts is set up once (one garage, one load, never kicked)",
		owned == 1 and W.reads == 1 and W.kicks[p] == nil and p.Parent == W.Players, owned .. " " .. W.reads .. " " .. tostring(W.kicks[p]))
	noCrash(W, "early joiner")
end
check("config: LobbyConfig has one garage per slot (#Garages == MAX_PLOTS == 6), in the row and in the ring",
	#(LOBBY_SOURCE)().Garages == 6 and #(LOBBY_SOURCE)().Row == 6 and #(LOBBY_SOURCE)().Ring == 6)
do
	local L = (LOBBY_SOURCE)()
	check("config: with the claim off the server uses the row, with it on the ring", L.garages(false) == L.Row and L.garages(true) == L.Ring
		and L.Garages == (L.ClaimEnabled and L.Ring or L.Row))
end

-- 7. Robux receipts: the real ShopServer (ProcessReceipt, waitForData, grantProduct) with the real TycoonCore ----------------
-- A receipt runs in its own thread, like Roblox's ProcessReceipt callback; box.decision stays "pending" while it waits.
local function receipt(W, userId, purchaseId)
	local box = { decision = "pending" }
	W.go(function()
		box.decision = W.Marketplace.ProcessReceipt({ PlayerId = userId, ProductId = W.ShopConfig.getProduct("CashSmall").id, PurchaseId = purchaseId })
	end)
	return box
end
local function savedReceipts(W, userId)
	local saved = W.store["player_" .. userId]
	local n = {}
	for _, id in ipairs(saved and saved.shop and saved.shop.receipts or {}) do n[id] = (n[id] or 0) + 1 end
	return n
end
do
	local W = newWorld({ claim = true, realShop = true, save = { player_201 = { cash = 0, owned = {}, lastSeen = 0 } } })
	W.boot()
	local H = W.H
	local pack = W.ShopConfig.cashPackAmount(W.ShopConfig.getProduct("CashSmall"), 0) -- a new company's income is 0: the pack's minimum
	check("receipt: the real ShopServer is wired to the real TycoonCore (ProcessReceipt set, the claim's time hook given)",
		type(W.Marketplace.ProcessReceipt) == "function" and pack > 0)
	local p = W.join("Rae", 201, PLAZA)
	W.run(0.2)
	local first = receipt(W, 201, "P-1")
	W.run(120)
	check("receipt: a player on the plaza with no garage: the receipt keeps waiting (no deadline before the claim)", first.decision == "pending"
		and #W.writes == 0, tostring(first.decision))
	walkTo(W, p, 2)
	hold(W, p, 2)
	W.run(0.05)
	check("receipt: right after the claim, while the save loads, the receipt still waits (it never grants on a save that is not ready)",
		first.decision == "pending", first.decision ~= "pending" and first.decision.Name or nil)
	W.run(5)
	local data = H.playerData[p]
	check("receipt: after the claim, once the save has loaded, it is granted once and saved with its PurchaseId",
		first.decision == GRANTED and data and data.ready and cashOf(p) == pack and savedReceipts(W, 201)["P-1"] == 1
		and W.store.player_201.cash == pack, tostring(first.decision ~= "pending" and first.decision.Name or first.decision) .. " cash " .. tostring(cashOf(p)))
	local again = receipt(W, 201, "P-1")
	W.run(2)
	check("receipt: the same PurchaseId again is not granted twice (granted, the Cash and the saved id only once)",
		again.decision == GRANTED and cashOf(p) == pack and savedReceipts(W, 201)["P-1"] == 1, cashOf(p))
	W.writeFail = true
	local failing = receipt(W, 201, "P-2")
	W.run(2)
	check("receipt: a failed save gets NotProcessedYet (Roblox asks again later)", failing.decision == NOT_YET and savedReceipts(W, 201)["P-2"] == nil,
		tostring(failing.decision ~= "pending" and failing.decision.Name or failing.decision))
	W.writeFail = false
	local retry = receipt(W, 201, "P-2")
	W.run(2)
	check("receipt: Roblox's retry after the failed save is granted, and the reward was given only once", retry.decision == GRANTED
		and cashOf(p) == 2 * pack and savedReceipts(W, 201)["P-2"] == 1, cashOf(p))
	local nobody = receipt(W, 299, "P-3")
	W.run(0.1)
	check("receipt: a receipt for someone not in the server gets NotProcessedYet at once", nobody.decision == NOT_YET)
	noCrash(W, "receipts")
end
do
	local W = newWorld({ claim = true, realShop = true })
	W.boot()
	local p = W.join("Sam", 202, PLAZA)
	W.run(0.2)
	local box = receipt(W, 202, "P-4")
	W.run(10)
	W.leave(p)
	W.run(1)
	check("receipt: a player who leaves before claiming gets NotProcessedYet (nothing granted, nothing saved)", box.decision == NOT_YET and #W.writes == 0,
		tostring(box.decision ~= "pending" and box.decision.Name or box.decision))
	noCrash(W, "receipt, left on the plaza")
end
do
	local W = newWorld({ claim = true, realShop = true, readDelay = 40 })
	W.boot()
	local p = W.join("Tia", 203, PLAZA)
	W.run(0.2)
	local box = receipt(W, 203, "P-5")
	W.run(3)
	walkTo(W, p, 4)
	hold(W, p, 4)
	W.run(29)
	check("receipt: from the claim it waits up to 30 s for the save", box.decision == "pending")
	W.run(2)
	check("receipt: 30 s after the claim with the save still loading, it gives up: NotProcessedYet (Roblox asks again later)", box.decision == NOT_YET,
		tostring(box.decision ~= "pending" and box.decision.Name or box.decision))
	W.run(15)
	check("receipt: nothing was granted by the receipt that gave up (the save loaded later, Cash 0)", W.H.playerData[p] and W.H.playerData[p].ready
		and cashOf(p) == 0)
	noCrash(W, "receipt, slow load")
end
do
	-- Studio with API access off: the game plays unsaved (data.ready, but data.loaded stays false)
	local W = newWorld({ claim = false, realShop = true, studio = true, noStore = true })
	W.boot()
	local p = W.join("Uma", 204, PLAZA)
	W.run(12)
	local data = W.H.playerData[p]
	local box = receipt(W, 204, "P-6")
	W.run(2)
	check("receipt: a session whose save never loaded (Studio, no DataStore) gets NotProcessedYet and is granted nothing",
		data and data.ready and not data.loaded and box.decision == NOT_YET and cashOf(p) == 0 and not data.shop.receiptSet["P-6"],
		data and (tostring(box.decision ~= "pending" and box.decision.Name or box.decision) .. " cash " .. cashOf(p)))
	noCrash(W, "receipt, unsaved Studio session")
end

-- 8. More of the plan's cases --------------------------------------------------------------------------------------------
-- An early joiner with the claim ON: in the server before the script started, set up once, onto the plaza (no claim)
do
	local W = newWorld({ claim = true })
	local p = W.new("Player")
	p.Name, p.DisplayName, p.UserId = "Early", "Early", 140
	p.CharacterAdded = W.signal()
	p.Kick = function(self, msg) W.kicks[self] = msg end
	table.insert(W.players, p)
	p.Parent = W.Players
	local ch = W.character(Vector3.new(-1, 3, -1))
	p.Character = ch
	W.Players.PlayerAdded.Connect = (function(orig) return function(self, fn) local c = orig(self, fn) W.task.defer(fn, p) return c end end)(W.Players.PlayerAdded.Connect)
	W.boot()
	local H = W.H
	W.run(65)
	check("early joiner, claim on: set up once, on the plaza (no garage, nothing read, never kicked, moved onto the plaza)",
		H.inPlaza[p] == true and H.playerData[p] == nil and W.reads == 0 and W.kicks[p] == nil and p:GetAttribute("Garage") == 0
		and (ch.HumanoidRootPart.Position - PLAZA).Magnitude < 0.01)
	walkTo(W, p, 3)
	hold(W, p, 3)
	W.run(3)
	check("early joiner, claim on: their claim works, with one load", H.plotOwners[3] == p and H.playerData[p] and H.playerData[p].ready and W.reads == 1)
	noCrash(W, "early joiner, claim on")
end
-- Claim OFF: the same account rejoins while its old garage is still Closing (the leave save runs)
do
	local W = newWorld({ claim = false, save = { player_150 = { cash = 10, owned = {}, lastSeen = 0 } } })
	W.boot()
	local H = W.H
	local old = W.join("Vic", 150, PLAZA)
	W.run(3)
	setCash(old, 5555)
	W.writeDelay = 8
	W.leave(old)
	W.run(0.5)
	local again = W.join("Vic", 150, PLAZA)
	W.run(3)
	check("claim off, rejoin while Closing: the account waits on the plaza (no garage, nothing read, not kicked) while its leave save runs",
		H.inPlaza[again] == true and H.playerData[again] == nil and W.kicks[again] == nil and W.reads == 1 and stateOf(W, 1) == "Closing")
	W.run(20) -- the leave save returns, the garage is claimed, then the fresh save is read twice (REREAD_WAIT_SECONDS)
	local data = H.playerData[again]
	check("claim off, rejoin while Closing: once the leave save returns it gets a garage and its read sees that save (Cash 5555)",
		data and data.ready and cashOf(again) >= 5555 and W.kicks[again] == nil and W.reads >= 2, data and cashOf(again))
	noCrash(W, "claim off, rejoin while closing")
end
-- One player pressing two prompts in the same moment (both in reach): one garage, one load
do
	local W = newWorld({ claim = true })
	W.boot()
	local H = W.H
	W.LobbyConfig.ClaimDistance = 1e6 -- both posts in reach, so only the claim itself can refuse the second
	local p = W.join("Wes", 160, PLAZA)
	W.run(0.2)
	hold(W, p, 2)
	hold(W, p, 3)
	W.run(3)
	local owned = 0
	for s = 1, 6 do if H.plotOwners[s] == p then owned += 1 end end
	check("two prompts in one moment: the player gets one garage (the first), one load, and the other stays Free with its prompt on",
		owned == 1 and H.plotOwners[2] == p and H.claims[160] ~= nil and H.claims[160].slot == 2 and W.reads == 1 and stateOf(W, 3) == "Free" and promptOf(W, 3).Enabled == true,
		owned .. " " .. W.reads)
	noCrash(W, "two prompts")
end
-- A plaza player who leaves is no longer on the plaza; passive income waits for data.ready
do
	local W = newWorld({ claim = true, save = { player_170 = { cash = 100, owned = { "Desk" }, lastSeen = 0 } } })
	W.boot()
	local H = W.H
	local gone = W.join("Xan", 171, PLAZA)
	W.run(0.5)
	W.leave(gone)
	W.run(0.5)
	check("leave: a player who leaves from the plaza is no longer on the plaza (inPlaza cleared)", H.inPlaza[gone] == nil)
	local p = W.join("Yul", 170, PLAZA)
	W.run(0.2)
	walkTo(W, p, 5)
	hold(W, p, 5)
	W.run(3)
	local data = H.playerData[p]
	local income = (stat(p, "Income") and stat(p, "Income").Value or -1)
	data.ready = false -- what loading or an IPO save does while it runs
	local before = cashOf(p)
	W.run(5)
	local paused = cashOf(p)
	data.ready = true
	W.run(3)
	check("income: while data.ready is off (loading, or an IPO being saved) no Cash is paid; once ready it pays again",
		income >= 1 and paused == before and cashOf(p) >= before + 2 * income, string.format("%d %d %d", before, paused, cashOf(p)))
	noCrash(W, "plaza leave and income")
end
-- A broken building warns once per server, not every second
do
	local W = newWorld({ claim = false, brokenBuilding = true })
	W.boot()
	W.join("Zed", 180, PLAZA)
	W.run(12)
	local n = 0
	for _, w in ipairs(W.warns) do if string.find(w, "the building failed", 1, true) then n += 1 end end
	check("building: a broken building warns once per server (not every second, not once per garage)", n == 1, n)
	noCrash(W, "broken building")
end

-- 9. The welcome-back pop-up (gameplay backlog item 7): what the join load's offline pay gave, said once -------------------------
local function welcomeNotes(W, p)
	local out = {}
	for _, text in ipairs(noteFor(W, p)) do if string.find(text, "Welcome back", 1, true) then table.insert(out, text) end end
	return out
end
do
	-- 1000 s away with the Desk ($1/s): the load pays 50% of 1000 s = $500, and 3 s later one pop-up says so
	local W = newWorld({ claim = false, save = { player_301 = { cash = 10, owned = { "Desk" }, lastSeen = 0 } } })
	W.boot()
	local H = W.H
	local p = W.join("Wen", 301, PLAZA)
	W.run(2)
	local data = H.playerData[p]
	check("welcome back: the offline pay is paid by the load as before (Cash 10 + $500), and no pop-up yet (it waits 3 s)",
		data and data.ready and cashOf(p) >= 510 and #welcomeNotes(W, p) == 0, cashOf(p))
	check("welcome back: the noted offline pay is cleared once said (data.offlineEarned is never kept)", data and data.offlineEarned == nil)
	W.run(3)
	local notes = welcomeNotes(W, p)
	check("welcome back: one pop-up after the load with the Cash and the time away", #notes == 1
		and notes[1] == "Welcome back! You earned $500 while away (16m)", notes[1])
	W.run(10)
	check("welcome back: said once per join (income after the load is never counted as offline pay)", #welcomeNotes(W, p) == 1
		and data.offlineEarned == nil, #welcomeNotes(W, p))
	noCrash(W, "welcome back")
end
do
	-- Away longer than the 8 h cap: the pop-up says the cap was reached; the pay stops at 8 h (4 h of income at $1/s)
	local W = newWorld({ claim = false, save = { player_302 = { cash = 0, owned = { "Desk" }, lastSeen = 1000 - 9 * 3600 } } })
	W.boot()
	local p = W.join("Cap", 302, PLAZA)
	W.run(5)
	local notes = welcomeNotes(W, p)
	check("welcome back: away past the offline cap: the pop-up says \"8h max\" and the pay is the cap's (8 h at 50%: $14.4K)",
		#notes == 1 and notes[1] == "Welcome back! You earned $14.4K while away (8h max)", notes[1])
	noCrash(W, "welcome back, capped")
end
do
	-- Short absence (2 min), a new player (no save), an old save with no upgrades (no income), a leave before the pop-up
	local W = newWorld({ claim = false, save = { player_303 = { cash = 0, owned = { "Desk" }, lastSeen = 1000 - 120 },
		player_305 = { cash = 0, owned = {}, lastSeen = 0 }, player_306 = { cash = 0, owned = { "Desk" }, lastSeen = 0 } } })
	W.boot()
	local short = W.join("Sho", 303, PLAZA)
	local fresh = W.join("New", 304, PLAZA)
	local poor = W.join("Nil", 305, PLAZA)
	local gone = W.join("Bye", 306, PLAZA)
	W.run(1.5)
	W.leave(gone)
	W.run(20)
	check("welcome back: a 2-minute absence still gets its offline pay but no pop-up (under 5 minutes)",
		cashOf(short) >= 60 and #welcomeNotes(W, short) == 0, cashOf(short))
	check("welcome back: a new player (no save) gets no pop-up", #welcomeNotes(W, fresh) == 0)
	check("welcome back: a save that earned nothing offline (no Income) gets no pop-up", #welcomeNotes(W, poor) == 0)
	check("welcome back: a player who leaves before the pop-up is sent nothing", #welcomeNotes(W, gone) == 0)
	noCrash(W, "welcome back, no pop-up")
end

print_real(string.format("%d passed, %d failed", passed, failed))
print_real("DONE")
