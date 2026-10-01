-- IpoServer: valuation, funding stages, going public (IPO), Shares and the IPO shop (milestone 4).
-- Put this ModuleScript in ServerScriptService, next to TycoonCore.
-- TycoonCore owns player data and saving, and plugs this module in with IpoServer.init.
-- Everything is decided here on the server: valuation, stages, rewards and perk purchases.
-- The client only shows the state and asks for actions. The numbers live in IpoConfig.
--
-- Other systems ask this module about IPO perks and the multiplier:
--   IpoServer.getMultiplier(player)   -> permanent income multiplier from IPOs (1 = none)
--   IpoServer.perk(data, key)         -> what a perk adds right now (see IpoConfig.Perks)
--   IpoServer.addEarnings(player, n)  -> Cash the startup earned (raises the valuation)
--   IpoServer.isBusy(data)            -> true while an IPO is being saved

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")

local IpoConfig = require(ReplicatedStorage:WaitForChild("IpoConfig"))
local ShopConfig = require(ReplicatedStorage:WaitForChild("ShopConfig"))
local ShopServer = require(script.Parent:WaitForChild("ShopServer"))

local PAD_OFFSET = Vector3.new(21, 0.6, 24) -- front-right of the plot, across from the purple HR pad
local PAD_COLOR = Color3.fromRGB(255, 200, 60)
local WHITE = Color3.new(1, 1, 1)
local PAD_OPEN_COOLDOWN = 3 -- seconds between two "open the IPO window" from the pad
local MAX_DEBUG_AMOUNT = 1e12

local IpoServer = {}

local core -- { getData, save, updateIncome, plotCenter, commitIpo, isPoachBusy, onPerksChanged }, given by TycoonCore
local remotes = {}

-- Helpers ---------------------------------------------------------------

local function getIpo(player)
	local data = core.getData(player)
	return data and data.ipo, data
end

local function send(player, kind, info)
	if player.Parent then
		remotes.event:FireClient(player, kind, info)
	end
end

-- Copies the state the screens show onto the player. Every player can see these, which is
-- how the in-server leaderboard works. The server never reads them back.
local function publish(player)
	local ipo = getIpo(player)
	if not ipo then return end
	player:SetAttribute("IpoCount", ipo.count)
	player:SetAttribute("IpoShares", ipo.shares)
	player:SetAttribute("IpoValuation", ipo.valuation)
	player:SetAttribute("IpoBest", ipo.best)
	player:SetAttribute("IpoMultiplier", IpoConfig.multiplier(ipo.count))
	player:SetAttribute("IpoCooldownUntil", ipo.lastIpoAt + IpoConfig.CooldownSeconds)
	for _, perk in ipairs(IpoConfig.Perks) do
		player:SetAttribute("IpoPerk_" .. perk.key, ipo.perks[perk.key] or 0)
	end
	local stats = player:FindFirstChild("leaderstats")
	local ipos = stats and stats:FindFirstChild("IPOs")
	if ipos then
		ipos.Value = ipo.count
	end
end

-- The garage pad's sign: your stage, or GO PUBLIC when you can
local function padText(ipo)
	local index = IpoConfig.stageIndex(ipo.valuation, ipo.count)
	local stage = IpoConfig.Stages[index]
	if index == #IpoConfig.Stages then
		return "🔔 GO PUBLIC!\nStep here to IPO"
	end
	local nextValuation = IpoConfig.stageValuation(index + 1, ipo.count)
	return string.format("%s %s\n%s / %s", stage.icon, stage.name,
		IpoConfig.formatShort(ipo.valuation), IpoConfig.formatShort(nextValuation))
end

local function refreshPad(ipo)
	if ipo.padLabel then
		local text = padText(ipo)
		if ipo.padLabel.Text ~= text then
			ipo.padLabel.Text = text
		end
	end
end

-- The saved form of the IPO state (also used for the save written during an IPO)
local function toSave(ipo)
	local perks = {}
	for key, level in pairs(ipo.perks) do
		if level > 0 then
			perks[key] = level
		end
	end
	return {
		count = ipo.count,
		shares = ipo.shares,
		valuation = ipo.valuation,
		lifetime = ipo.lifetime,
		best = ipo.best,
		lastIpoAt = ipo.lastIpoAt,
		perks = perks,
	}
end

-- Effects other systems ask about ---------------------------------------

function IpoServer.getMultiplier(player)
	local ipo = getIpo(player)
	return ipo and IpoConfig.multiplier(ipo.count) or 1
end

-- data can be nil (before the save loaded): no perks yet
function IpoServer.perk(data, key)
	local ipo = data and data.ipo
	return ipo and IpoConfig.perkValue(key, ipo.perks[key]) or 0
end

function IpoServer.isBusy(data)
	return data ~= nil and data.ipo ~= nil and data.ipo.busy == true
end

-- Cash the startup earned raises the valuation (spending never lowers it)
function IpoServer.addEarnings(player, amount)
	local ipo = getIpo(player)
	if not ipo or ipo.busy or amount <= 0 then return end
	amount = math.floor(amount)
	ipo.valuation += amount
	ipo.lifetime += amount
	ipo.best = math.max(ipo.best, ipo.valuation)
	player:SetAttribute("IpoValuation", ipo.valuation)
	player:SetAttribute("IpoBest", ipo.best)
	refreshPad(ipo)
end

-- Going public -----------------------------------------------------------

-- Everything an IPO would give right now (the IPO window shows the same numbers)
local function preview(player, ipo)
	local passMultiplier = ShopServer.getSharesMultiplier(player)
	return {
		number = ipo.count + 1, -- this would be IPO number N
		shares = IpoConfig.sharesFor(ipo.valuation, ipo.count, passMultiplier),
		multiplierBefore = IpoConfig.multiplier(ipo.count),
		multiplierAfter = IpoConfig.multiplier(ipo.count + 1),
	}
end

-- One safe step: check everything, write the new state to the save, and only change the game
-- once that save worked. If the save fails, nothing changes. ipoNumber is the IPO the player
-- confirmed (count + 1), so a repeated or old request can never go public twice.
local function goPublic(player, ipoNumber)
	local ipo, data = getIpo(player)
	if typeof(ipoNumber) ~= "number" or ipoNumber ~= ipo.count + 1 then
		return false, "That IPO is out of date: reopen the IPO window and try again"
	end
	if ipo.busy then return false, "Your IPO is already being filed" end
	if not data.loaded then return false, "Your save didn't load, so you can't go public this session" end
	local now = os.time()
	local readyAt = ipo.lastIpoAt + IpoConfig.CooldownSeconds
	if now < readyAt then
		return false, "The market needs a moment: try again in " .. (readyAt - now) .. "s"
	end
	local needed = IpoConfig.ipoValuation(ipo.count)
	if ipo.valuation < needed then
		return false, "You need a valuation of " .. ShopConfig.formatCash(needed) .. " to go public"
	end
	if core.isPoachBusy(player) then
		return false, "Finish your poaching deal or Counter-Offer first (or wait until nobody is poaching you)"
	end

	local reward = preview(player, ipo)
	local after = {
		count = ipo.count + 1,
		shares = ipo.shares + reward.shares,
		valuation = 0,
		lifetime = ipo.lifetime,
		best = math.max(ipo.best, ipo.valuation),
		lastIpoAt = now,
		perks = ipo.perks,
	}

	-- Lock: income, pads, eggs, poaching and purchases all wait until the IPO is settled
	ipo.busy = true
	data.ready = false
	local ok = core.commitIpo(player, toSave(after))
	ipo.busy = false
	if core.getData(player) ~= data then
		return ok, ok and "You went public!" or "The IPO couldn't be saved. Nothing changed." -- they left
	end
	data.ready = true
	if not ok then
		return false, "The IPO couldn't be saved. Nothing changed: try again in a moment."
	end

	ipo.count = after.count
	ipo.shares = after.shares
	ipo.valuation = 0
	ipo.best = after.best
	ipo.lastIpoAt = now
	refreshPad(ipo)
	publish(player)
	core.updateIncome(player)
	send(player, "Done", {
		number = after.count,
		shares = reward.shares,
		multiplier = reward.multiplierAfter,
	})
	return true, "You went public! IPO #" .. after.count
end

-- IPO shop -----------------------------------------------------------------

local function buyPerk(player, key)
	local ipo, data = getIpo(player)
	local perk = typeof(key) == "string" and IpoConfig.getPerk(key)
	if not perk then return false, "Unknown perk" end
	if ipo.busy then return false, "Your IPO is being filed" end
	local level = ipo.perks[perk.key] or 0
	local cost = perk.costs[level + 1]
	if not cost then return false, perk.name .. " is already at the max level" end
	if ipo.shares < cost then return false, "Not enough Shares (" .. cost .. ")" end

	ipo.shares -= cost
	ipo.perks[perk.key] = level + 1
	publish(player)
	core.onPerksChanged(player) -- more incubators or desks show up right away
	task.spawn(core.save, player) -- Shares are spent: save it now
	return true, perk.name .. " is now level " .. (level + 1)
end

local function onAction(player, action, arg)
	if typeof(action) ~= "string" then return false, "Bad request" end
	local ipo, data = getIpo(player)
	if not ipo or not data.ready then return false, "Still loading, try again in a moment" end

	if action == "GoPublic" then
		return goPublic(player, arg)
	elseif action == "BuyPerk" then
		return buyPerk(player, arg)
	end
	return false, "Unknown action"
end

-- Garage pad ----------------------------------------------------------------

-- A gold pad next to the green one. Stepping on it opens the IPO window (the window has the
-- button: going public always needs the two-step confirm there).
local function buildPad(player, data)
	local center = core.plotCenter(data.slot)
	local pad = Instance.new("Part")
	pad.Name = "IpoPad"
	pad.Size = Vector3.new(8, 0.2, 8)
	pad.Position = center + PAD_OFFSET
	pad.Color = PAD_COLOR
	pad.Material = Enum.Material.Neon
	pad.Anchored = true
	pad.TopSurface = Enum.SurfaceType.Smooth
	pad.BottomSurface = Enum.SurfaceType.Smooth
	pad.Parent = data.folder

	local gui = Instance.new("BillboardGui")
	gui.Size = UDim2.fromScale(10, 2.6) -- in studs, like the HR pad label
	gui.StudsOffset = Vector3.new(0, 4, 0)
	gui.AlwaysOnTop = true
	gui.MaxDistance = 90
	gui.Parent = pad
	local label = Instance.new("TextLabel")
	label.Size = UDim2.fromScale(1, 1)
	label.BackgroundTransparency = 1
	label.TextScaled = true
	label.Font = Enum.Font.GothamBold
	label.TextColor3 = WHITE
	label.TextStrokeTransparency = 0
	label.Text = ""
	label.Parent = gui
	data.ipo.padLabel = label
	refreshPad(data.ipo)

	local lastTouch = 0
	pad.Touched:Connect(function(hit)
		if Players:GetPlayerFromCharacter(hit.Parent) ~= player or not data.ready then return end
		if os.clock() - lastTouch < PAD_OPEN_COOLDOWN then return end
		lastTouch = os.clock()
		send(player, "Open")
	end)
end

-- Saving (TycoonCore calls these) ----------------------------------------------

-- Called right after the player's save loads, before EmployeeServer (perks change slots and
-- incubators). savedIpo is the "ipo" part of the save, or nil (saves from before milestone 4).
-- legacyValuation: for those older saves, a fair guess of what they already earned.
function IpoServer.setupPlayer(player, data, savedIpo, legacyValuation)
	local ipo = {
		count = 0, -- IPOs done (saved)
		shares = 0, -- unspent Shares (saved)
		valuation = 0, -- Cash earned since the last IPO: decides the stage (saved)
		lifetime = 0, -- Cash earned ever, never reset (saved)
		best = 0, -- highest valuation reached on any run, for the leaderboard (saved)
		lastIpoAt = 0, -- os.time() of the last IPO, for the cooldown (saved)
		perks = {}, -- perk key -> level (saved)
		busy = false, -- true while an IPO is being saved
		padLabel = nil,
	}
	local function number(value)
		value = tonumber(value)
		return (value and value == value and value >= 0) and math.floor(value) or 0 -- no NaN or negatives
	end
	if typeof(savedIpo) == "table" then
		ipo.count = number(savedIpo.count)
		ipo.shares = number(savedIpo.shares)
		ipo.valuation = number(savedIpo.valuation)
		ipo.lifetime = math.max(number(savedIpo.lifetime), ipo.valuation)
		ipo.best = math.max(number(savedIpo.best), ipo.valuation)
		ipo.lastIpoAt = number(savedIpo.lastIpoAt)
		if typeof(savedIpo.perks) == "table" then
			for key, level in pairs(savedIpo.perks) do
				local perk = typeof(key) == "string" and IpoConfig.getPerk(key)
				if perk then
					ipo.perks[key] = math.clamp(number(level), 0, #perk.costs)
				else
					warn("Skipped an unknown IPO perk in a save: " .. tostring(key))
				end
			end
		end
	else
		local guess = number(legacyValuation)
		ipo.valuation, ipo.lifetime, ipo.best = guess, guess, guess
	end
	data.ipo = ipo

	local stats = player:FindFirstChild("leaderstats")
	if stats and not stats:FindFirstChild("IPOs") then
		local ipos = Instance.new("IntValue")
		ipos.Name = "IPOs"
		ipos.Parent = stats
	end
	buildPad(player, data)
	publish(player)
end

-- The part of the save file that belongs to the IPO
function IpoServer.serialize(data)
	return data.ipo and toSave(data.ipo) or nil
end

-- Studio Debug tab -------------------------------------------------------------

local function debugAmount(text)
	local amount = tonumber(text)
	if not amount or amount ~= amount or amount <= 0 or amount > MAX_DEBUG_AMOUNT then return nil end
	return math.floor(amount)
end

local function addDebugActions()
	ShopServer.addDebugAction("IpoGrantValuation", function(player, _, text)
		local amount = debugAmount(text)
		if not amount then return "Bad amount" end
		IpoServer.addEarnings(player, amount)
		return "Valuation +" .. ShopConfig.formatCash(amount)
	end)
	ShopServer.addDebugAction("IpoJumpReady", function(player, data)
		local ipo = data.ipo
		local missing = IpoConfig.ipoValuation(ipo.count) - ipo.valuation
		if missing > 0 then
			IpoServer.addEarnings(player, missing)
		end
		ipo.lastIpoAt = 0 -- skip the cooldown too
		publish(player)
		return "You're IPO-ready (valuation " .. ShopConfig.formatCash(ipo.valuation) .. ")"
	end)
	ShopServer.addDebugAction("IpoGrantShares", function(player, data, text)
		local amount = debugAmount(text)
		if not amount then return "Bad amount" end
		data.ipo.shares += amount
		publish(player)
		return "+" .. amount .. " Shares"
	end)
	ShopServer.addDebugAction("IpoReset", function(player, data)
		local ipo = data.ipo
		if ipo.busy then return "An IPO is being filed" end
		ipo.count, ipo.shares, ipo.valuation, ipo.best, ipo.lastIpoAt = 0, 0, 0, 0, 0
		table.clear(ipo.perks)
		refreshPad(ipo)
		publish(player)
		core.onPerksChanged(player)
		core.updateIncome(player)
		return "IPO progress reset: 0 IPOs, 0 Shares, no perks, valuation 0 (saved at the next save)"
	end)
	ShopServer.addDebugAction("IpoFailNextSave", function(_, data)
		data.debugFailIpoSave = true
		return "Your next IPO's save will fail on purpose. Nothing should change."
	end)
end

-- Setup -----------------------------------------------------------------

function IpoServer.init(coreApi)
	core = coreApi

	local folder = Instance.new("Folder")
	folder.Name = "IpoRemotes"
	remotes.action = Instance.new("RemoteFunction")
	remotes.action.Name = "IpoAction"
	remotes.action.OnServerInvoke = onAction
	remotes.action.Parent = folder
	remotes.event = Instance.new("RemoteEvent")
	remotes.event.Name = "IpoEvent"
	remotes.event.Parent = folder
	folder.Parent = ReplicatedStorage

	if RunService:IsStudio() then
		addDebugActions()
	end
end

return IpoServer
