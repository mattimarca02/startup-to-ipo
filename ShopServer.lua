-- ShopServer: game passes, developer products, VIP perks and the Studio Debug tab (milestone 3).
-- Put this ModuleScript in ServerScriptService, next to TycoonCore.
-- TycoonCore owns player data and saving, and plugs this module in with ShopServer.init.
-- Everything is granted here on the server. The client can only open Roblox's purchase prompts.
--
-- For the egg/employee system (milestone 2), ask this module instead of checking passes yourself:
--   ShopServer.getMaxEmployees(player, baseSlots)  -> baseSlots + Extra Employee Slots
--   ShopServer.hasAutoHatch(player)                -> true if eggs should hatch by themselves
--   ShopServer.getLuckMultiplier(player)           -> 2 while Luck Boost runs, otherwise 1
--   ShopServer.useInstantHatch(player)             -> true if a token was used (skip one egg timer)
-- And for poaching (PoachServer):
--   ShopServer.getPoachBonus(player)               -> extra poach chance from Headhunter (0.1 = +10%)
--   ShopServer.addProductHandler(field, handler)   -> grants product effects that live in another system
-- And for the IPO (IpoServer):
--   ShopServer.getSharesMultiplier(player)         -> 2 with the Shareholder pass, otherwise 1
-- And for Roblox's Paid Random Items policy (FR-13, D9 option B):
--   ShopServer.isRandomRestricted(player)          -> true if they get no random rolls (fixed hire order)
-- And for anyone: ShopServer.notify(player, text)  -> a pop-up message (TycoonCore's saving warning)

local Players = game:GetService("Players")
local MarketplaceService = game:GetService("MarketplaceService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local HttpService = game:GetService("HttpService")
local PhysicsService = game:GetService("PhysicsService")
local PolicyService = game:GetService("PolicyService")

local ShopConfig = require(ReplicatedStorage:WaitForChild("ShopConfig"))

local MAX_RECEIPTS = 100 -- PurchaseIds remembered per player, so a repeated receipt never pays twice
local DATA_WAIT_SECONDS = 30 -- how long a receipt waits for a joining player's save to load
local PASS_RECHECK_SECONDS = 120 -- re-ask Roblox about passes (catches passes bought on the website mid-game)
local PASS_CHECK_TIMEOUT = 10 -- loading waits at most this long for the pass check on join
local LOUNGE_CENTER = Vector3.new(0, 0.5, 70) -- between the spawn and the garage plots
local LOUNGE_SIZE = Vector3.new(36, 1, 24)
local LOUNGE_WALL_HEIGHT = 10
local DOOR_WIDTH = 8
local DOOR_GROUP = "VipDoor"
local VIP_GROUP = "VipPlayers"

local GRANTED = Enum.ProductPurchaseDecision.PurchaseGranted
local NOT_YET = Enum.ProductPurchaseDecision.NotProcessedYet

local ShopServer = {}

local core -- { getData, save, updateIncome, addEarnings }, given by TycoonCore
local notifyEvent
local lastDebugReceipt = {} -- player -> { product, purchaseId } (Studio debug only)
local extraDebugActions = {} -- name -> function(player, data, arg), added by other systems
local productHandlers = {} -- effect field -> function(player, data, effect), added by other systems
local doorCooldown = {} -- player -> os.clock() of the last "VIP only" message
local passCheckPending = {} -- player -> os.clock() when the join-time pass check started, until it has finished

-- Helpers ---------------------------------------------------------------

local function getShop(player)
	local data = core.getData(player)
	return data and data.shop
end

local function owns(shop, key)
	-- ignoreRealPasses: Studio Debug tab only, to test like a player who owns nothing
	-- (the game's creator automatically owns every pass)
	return (shop.passes[key] == true and not shop.ignoreRealPasses) or shop.debugPasses[key] == true
end

-- Effects of every pass the player has (bought, or simulated with the Debug tab)
local function ownedEffects(shop)
	local effects = {}
	for _, pass in ipairs(ShopConfig.Passes) do
		if owns(shop, pass.key) then
			table.insert(effects, pass.effect)
		end
	end
	return effects
end

local function hasEffect(player, field)
	local shop = getShop(player)
	if not shop then return false end
	for _, effect in ipairs(ownedEffects(shop)) do
		if effect[field] then
			return true
		end
	end
	return false
end

local function notify(player, text)
	if notifyEvent and player.Parent then
		notifyEvent:FireClient(player, text)
	end
end

local function makePart(parent, name, size, position, color, material)
	local p = Instance.new("Part")
	p.Name = name
	p.Size = size
	p.Position = position
	p.Color = color
	p.Material = material or Enum.Material.SmoothPlastic
	p.Anchored = true
	p.TopSurface = Enum.SurfaceType.Smooth
	p.BottomSurface = Enum.SurfaceType.Smooth
	p.Parent = parent
	return p
end

-- VIPs get a collision group that walks through the lounge door; everyone else bumps into it
local function setPartGroup(part, vip)
	if not part:IsA("BasePart") then return end
	if vip then
		part.CollisionGroup = VIP_GROUP
	elseif part.CollisionGroup == VIP_GROUP then
		part.CollisionGroup = "Default"
	end
end

local function refreshCharacter(player)
	local character = player.Character
	if not character then return end
	local vip = hasEffect(player, "vipLounge")
	for _, d in ipairs(character:GetDescendants()) do
		setPartGroup(d, vip)
	end
end

-- Copies shop state onto the player as attributes so the shop screen can show it,
-- then re-applies every pass effect right away (no rejoin needed).
-- The client only reads these attributes; the server never trusts them.
local function publish(player)
	local shop = getShop(player)
	if not shop then return end

	local tag, tagColor
	for _, pass in ipairs(ShopConfig.Passes) do
		local owned = owns(shop, pass.key)
		player:SetAttribute("Pass_" .. pass.key, owned)
		if owned and pass.effect.chatTag and not tag then
			tag, tagColor = pass.effect.chatTag, pass.effect.chatTagColor
		end
	end
	player:SetAttribute("ChatTag", tag)
	player:SetAttribute("ChatTagColor", tagColor)
	player:SetAttribute("LuckBoostUntil", shop.luckUntil)
	player:SetAttribute("InstantHatches", shop.instantHatches)
	player:SetAttribute("RandomRestricted", shop.randomRestricted) -- screens: next hire instead of odds

	refreshCharacter(player)
	core.updateIncome(player)
end

-- Effects other systems ask about ---------------------------------------

-- A message in the shop's pop-up, for other systems (TycoonCore: "saving is having trouble")
function ShopServer.notify(player, text)
	notify(player, text)
end

function ShopServer.hasPass(player, key)
	local shop = getShop(player)
	return shop ~= nil and owns(shop, key)
end

-- 2x Cash and VIP multiply together (both = 3x)
function ShopServer.getCashMultiplier(player)
	local multiplier = 1
	local shop = getShop(player)
	if shop then
		for _, effect in ipairs(ownedEffects(shop)) do
			multiplier *= effect.cashMultiplier or 1
		end
	end
	return multiplier
end

function ShopServer.getMaxEmployees(player, baseSlots)
	local slots = baseSlots
	local shop = getShop(player)
	if shop then
		for _, effect in ipairs(ownedEffects(shop)) do
			slots += effect.extraEmployeeSlots or 0
		end
	end
	return slots
end

function ShopServer.hasAutoHatch(player)
	return hasEffect(player, "autoHatch")
end

function ShopServer.getLuckMultiplier(player)
	local shop = getShop(player)
	if not shop or shop.luckUntil <= os.time() then
		return 1
	end
	for _, product in ipairs(ShopConfig.Products) do
		if product.effect.luckMultiplier then
			return product.effect.luckMultiplier
		end
	end
	return 1
end

function ShopServer.useInstantHatch(player)
	local shop = getShop(player)
	if not shop or shop.instantHatches <= 0 then
		return false
	end
	shop.instantHatches -= 1
	publish(player)
	return true
end

-- Headhunter: added to every poaching chance
function ShopServer.getPoachBonus(player)
	local bonus = 0
	local shop = getShop(player)
	if shop then
		for _, effect in ipairs(ownedEffects(shop)) do
			bonus += effect.poachBonus or 0
		end
	end
	return bonus
end

-- Shareholder: multiplies the Shares you get from every IPO
function ShopServer.getSharesMultiplier(player)
	local multiplier = 1
	local shop = getShop(player)
	if shop then
		for _, effect in ipairs(ownedEffects(shop)) do
			multiplier *= effect.sharesMultiplier or 1
		end
	end
	return multiplier
end

-- Paid random items restricted for this player (PolicyService, checked on every join, never saved)?
-- Fail closed: true while the check runs, if it failed or was too slow, and if there is no data.
function ShopServer.isRandomRestricted(player)
	local shop = getShop(player)
	return shop == nil or shop.randomRestricted ~= false
end

-- true while the join-time pass check is still running: the player's passes may not be known yet
function ShopServer.isPassCheckPending(player)
	return passCheckPending[player] ~= nil
end

-- Seconds the join-time pass check has been running, or nil when it isn't running
function ShopServer.passCheckAge(player)
	local startedAt = passCheckPending[player]
	return startedAt and os.clock() - startedAt or nil
end

-- Game passes -----------------------------------------------------------

-- Returns true/false, or nil if Roblox couldn't be reached (we'll try again later)
local function userOwnsPass(player, passId)
	for attempt = 1, 3 do
		local ok, result = pcall(function()
			return MarketplaceService:UserOwnsGamePassAsync(player.UserId, passId)
		end)
		if ok then
			return result
		end
		warn("Pass check failed (attempt " .. attempt .. "): " .. tostring(result))
		task.wait(attempt)
	end
	return nil
end

-- PASSCHECK-START
-- (tools/daily_test.py runs the code between the PASSCHECK markers, so keep it free of Roblox calls except those it fakes.)

-- Asks Roblox about every pass the player doesn't have yet, all at once, and publishes each pass
-- as soon as it is found (a slow pass never holds back the others). Returns true if something changed.
local function checkPasses(player, shop)
	local changed = false
	local waiting = 0
	for _, pass in ipairs(ShopConfig.Passes) do
		if pass.id ~= 0 and not shop.passes[pass.key] then
			waiting += 1
			task.spawn(function()
				local ok, err = pcall(function()
					if userOwnsPass(player, pass.id) then
						shop.passes[pass.key] = true
						changed = true
						publish(player)
					end
				end)
				if not ok then
					warn("Pass check for " .. pass.key .. " failed: " .. tostring(err))
				end
				waiting -= 1
			end)
		end
	end
	while waiting > 0 do
		task.wait(0.1)
	end
	return changed
end

local passConfirming = {} -- player -> { [passKey] = true } while a purchase is being confirmed

-- After a purchase: keep asking Roblox until it confirms the pass, for up to ShopConfig.PassConfirm.GiveUpSeconds.
-- Only a "yes" from Roblox grants the pass, so a client can never talk its way into one.
local function confirmPurchasedPass(player, pass, shop)
	local confirming = passConfirming[player]
	if not confirming then
		confirming = {}
		passConfirming[player] = confirming
	end
	if confirming[pass.key] then return end -- already waiting for this one
	confirming[pass.key] = true

	local settings = ShopConfig.PassConfirm
	local deadline = os.clock() + settings.GiveUpSeconds
	local told = false
	while true do
		if shop.passes[pass.key] or userOwnsPass(player, pass.id) then
			shop.passes[pass.key] = true
			publish(player)
			notify(player, pass.name .. " unlocked!")
			break
		end
		if not player.Parent or getShop(player) ~= shop then break end -- they left
		if os.clock() >= deadline then
			notify(player, "Roblox is slow to confirm " .. pass.name .. ". It will unlock by itself when Roblox answers (or when you rejoin).")
			break
		end
		if not told then
			told = true
			notify(player, "Confirming " .. pass.name .. " with Roblox...")
		end
		task.wait(settings.RetrySeconds)
	end
	confirming[pass.key] = nil
end

-- Fires on the server when a pass prompt closes (bought, cancelled or failed)
local function onPassPromptFinished(player, passId, wasPurchased)
	if not wasPurchased then return end -- cancelled or failed: nothing to grant
	local pass = ShopConfig.getPassById(passId)
	local shop = getShop(player)
	if not pass or not shop then return end

	-- Don't trust the event alone: ask Roblox (its ownership cache refreshes when this event fires)
	confirmPurchasedPass(player, pass, shop)
end
-- PASSCHECK-END

-- Paid random items (Roblox policy, review finding FR-13, decision D9 option B) ------------

-- POLICY-START
-- (tools/daily_test.py runs the code between the POLICY markers, so keep it free of Roblox calls except those it fakes.)

-- Asks Roblox if paid random items are restricted for this player. Returns true or false, or nil
-- if Roblox couldn't answer after every try (ShopConfig.PolicyCheck).
local function askRandomPolicy(player)
	local settings = ShopConfig.PolicyCheck
	for attempt = 1, settings.Attempts do
		local ok, result = pcall(function()
			return PolicyService:GetPolicyInfoForPlayerAsync(player)
		end)
		if ok and typeof(result) == "table" and typeof(result.ArePaidRandomItemsRestricted) == "boolean" then
			return result.ArePaidRandomItemsRestricted
		end
		warn("Policy check failed (attempt " .. attempt .. "): " .. (ok and "no ArePaidRandomItemsRestricted in the answer" or tostring(result)))
		if attempt < settings.Attempts then
			task.wait(settings.RetrySeconds)
		end
	end
	return nil
end

-- Starts the policy check for a joining player, at the same time as the pass check. Fail closed: the
-- player is restricted from the start, and only a clear "not restricted" that comes in time lifts it.
-- Returns the check: state is "checking", then "done", or "late" once loading stopped waiting for it
-- (then the player stays restricted for the whole session, whatever Roblox answers afterwards).
local function startPolicyCheck(player, shop)
	shop.randomRestricted = true
	local check = { state = "checking", startedAt = os.clock() }
	task.spawn(function()
		local ok, restricted = pcall(askRandomPolicy, player)
		if not ok then
			warn("Policy check for " .. player.Name .. " failed: " .. tostring(restricted))
		end
		if check.state ~= "checking" then
			warn("Policy check for " .. player.Name .. " answered after loading went on: restricted for this session")
			return
		end
		check.state = "done"
		shop.randomRestricted = not (ok and restricted == false)
	end)
	return check
end

-- true while loading should still wait for the policy answer (at most ShopConfig.PolicyCheck.TimeoutSeconds)
local function policyCheckWaiting(check)
	return check.state == "checking" and os.clock() - check.startedAt < ShopConfig.PolicyCheck.TimeoutSeconds
end

-- Loading goes on: a check that hasn't answered yet is too late from now on (restricted all session)
local function stopPolicyWait(player, check)
	if check.state == "checking" then
		check.state = "late"
		warn("Policy check for " .. player.Name .. " is slow: paid random items stay restricted this session")
	end
end
-- POLICY-END

-- Saving (TycoonCore calls these) ---------------------------------------

-- Called right after the player's save loads. savedShop is the "shop" part of the save, or nil.
function ShopServer.setupPlayer(player, data, savedShop)
	local shop = {
		passes = {}, -- key -> true when Roblox says you own it (checked on every join, not saved)
		debugPasses = {}, -- key -> true when simulated with the Studio Debug tab (not saved)
		luckUntil = 0, -- os.time() when Luck Boost runs out
		instantHatches = 0, -- unused Instant Hatch tokens
		receipts = {}, -- PurchaseIds already granted, oldest first (saved)
		receiptSet = {}, -- the same PurchaseIds as a quick lookup
		randomRestricted = true, -- paid random items restricted (PolicyService, checked on every join, not saved)
	}
	if typeof(savedShop) == "table" then -- bad values are skipped, never an error
		local luckLeft = tonumber(savedShop.luckLeft) or 0
		if luckLeft > 0 then
			shop.luckUntil = os.time() + luckLeft
		end
		local hatches = tonumber(savedShop.instantHatches) or 0
		shop.instantHatches = hatches == hatches and math.max(0, math.floor(hatches)) or 0 -- no NaN
		for _, purchaseId in ipairs(typeof(savedShop.receipts) == "table" and savedShop.receipts or {}) do
			table.insert(shop.receipts, purchaseId)
			shop.receiptSet[purchaseId] = true
		end
	end
	data.shop = shop

	local function onCharacter(character)
		character.DescendantAdded:Connect(function(d)
			setPartGroup(d, hasEffect(player, "vipLounge"))
		end)
		refreshCharacter(player)
	end
	player.CharacterAdded:Connect(onCharacter)
	if player.Character then
		onCharacter(player.Character)
	end

	-- Ask Roblox which passes they own, but never let a slow answer hold up loading: after
	-- PASS_CHECK_TIMEOUT loading goes on, and the passes apply as soon as Roblox answers.
	-- Passes aren't saved, so a save written before the answer is still complete.
	-- The paid random items check runs at the same time, under its own cap (the same 10 s), so the
	-- join never waits longer than before. It isn't saved either: it's asked again on every join.
	local policyCheck = startPolicyCheck(player, shop)
	local state = "checking"
	passCheckPending[player] = os.clock() -- the VIP lounge and the door wait for the answer
	task.spawn(function()
		local ok, err = pcall(checkPasses, player, shop) -- each pass is published as soon as it is found
		if not ok then
			warn("Pass check for " .. player.Name .. " failed: " .. tostring(err))
		end
		passCheckPending[player] = nil
		state = "done"
	end)
	local deadline = os.clock() + PASS_CHECK_TIMEOUT
	while (state == "checking" and os.clock() < deadline) or policyCheckWaiting(policyCheck) do
		task.wait(0.1)
	end
	if state == "checking" then
		state = "gaveUp"
		warn("Pass check for " .. player.Name .. " is slow: loading goes on, passes apply when Roblox answers")
	end
	stopPolicyWait(player, policyCheck) -- no answer yet: restricted for this session (fail closed)
	publish(player)
end

-- The part of the save file that belongs to the shop
function ShopServer.serialize(data)
	local shop = data.shop
	if not shop then return nil end
	return {
		-- Saved as time left, so Luck Boost only counts down while you're playing
		luckLeft = math.max(0, shop.luckUntil - os.time()),
		instantHatches = shop.instantHatches,
		receipts = shop.receipts,
	}
end

-- Developer products ----------------------------------------------------

local function waitForData(player)
	local deadline = os.clock() + DATA_WAIT_SECONDS
	while player.Parent and os.clock() < deadline do
		local data = core.getData(player)
		if data and data.ready then
			return data
		end
		task.wait(0.25)
	end
	return nil
end

-- Gives the reward. Must not wait/yield, so a save always has both the reward and the PurchaseId, or neither.
local function applyProduct(player, data, product)
	local shop, effect = data.shop, product.effect
	local gained = {}
	for field, handler in pairs(productHandlers) do
		if effect[field] then
			table.insert(gained, handler(player, data, effect)) -- e.g. Poach Shield (PoachServer)
		end
	end
	if effect.incomeMinutes then
		local amount = ShopConfig.cashPackAmount(product, data.income.Value)
		data.cash.Value += amount
		core.addEarnings(player, amount) -- Cash packs count toward the valuation (IPO)
		table.insert(gained, "+" .. ShopConfig.formatCash(amount))
	end
	if effect.luckMinutes then
		shop.luckUntil = math.max(shop.luckUntil, os.time()) + effect.luckMinutes * 60
		table.insert(gained, "+" .. effect.luckMinutes .. " min of Luck Boost")
	end
	if effect.instantHatches then
		shop.instantHatches += effect.instantHatches
		table.insert(gained, "+" .. effect.instantHatches .. " Instant Hatch")
	end
	return table.concat(gained, ", ")
end

local function rememberReceipt(shop, purchaseId)
	table.insert(shop.receipts, purchaseId)
	shop.receiptSet[purchaseId] = true
	while #shop.receipts > MAX_RECEIPTS do
		shop.receiptSet[table.remove(shop.receipts, 1)] = nil
	end
end

-- Grants a product at most once per PurchaseId. Says "granted" only after the reward
-- AND the PurchaseId are saved together; otherwise Roblox asks again later.
local function grantProduct(player, product, purchaseId)
	local data = waitForData(player)
	if not data or not data.loaded then
		return NOT_YET -- they left, or their save couldn't load: Roblox retries when they rejoin
	end

	local shop = data.shop
	if not shop.receiptSet[purchaseId] then
		local gained = applyProduct(player, data, product)
		rememberReceipt(shop, purchaseId)
		publish(player)
		notify(player, product.name .. ": " .. gained)
	end
	-- Already-granted receipts still save first, in case the earlier save failed

	if core.save(player) then
		return GRANTED
	end
	return NOT_YET -- kept in memory, so the retry won't grant it twice
end

local function processReceipt(receipt)
	local product = ShopConfig.getProductById(receipt.ProductId)
	if not product then
		warn("Unknown developer product " .. tostring(receipt.ProductId) .. ": add its ID to ShopConfig")
		return NOT_YET
	end
	local player = Players:GetPlayerByUserId(receipt.PlayerId)
	if not player then
		return NOT_YET -- they left mid-purchase: Roblox sends it again when they rejoin
	end
	local ok, decision = pcall(grantProduct, player, product, tostring(receipt.PurchaseId))
	if not ok then
		warn("ProcessReceipt error: " .. tostring(decision))
		return NOT_YET
	end
	return decision
end

-- VIP Lounge ------------------------------------------------------------

local function findVipPass()
	for _, pass in ipairs(ShopConfig.Passes) do
		if pass.effect.vipLounge then
			return pass
		end
	end
	return nil
end

local function isInsideLounge(position)
	local offset = position - LOUNGE_CENTER
	return math.abs(offset.X) < LOUNGE_SIZE.X / 2
		and math.abs(offset.Z) < LOUNGE_SIZE.Z / 2
		and offset.Y < LOUNGE_WALL_HEIGHT + 5
end

local function buildVipLounge()
	local folder = Instance.new("Folder")
	folder.Name = "VipLounge"
	folder.Parent = workspace

	local gold = Color3.fromRGB(255, 200, 60)
	local glass = Color3.fromRGB(170, 210, 255)
	local c, w, d, h = LOUNGE_CENTER, LOUNGE_SIZE.X, LOUNGE_SIZE.Z, LOUNGE_WALL_HEIGHT
	local wallY = c.Y + 0.5 + h / 2

	makePart(folder, "Floor", LOUNGE_SIZE, c, Color3.fromRGB(70, 55, 30), Enum.Material.Marble)

	local walls = {
		{ "BackWall", Vector3.new(w, h, 1), Vector3.new(c.X, wallY, c.Z - d / 2) },
		{ "LeftWall", Vector3.new(1, h, d), Vector3.new(c.X - w / 2, wallY, c.Z) },
		{ "RightWall", Vector3.new(1, h, d), Vector3.new(c.X + w / 2, wallY, c.Z) },
	}
	-- The front wall has a gap in the middle for the door
	local sideWidth = (w - DOOR_WIDTH) / 2
	table.insert(walls, { "FrontWallLeft", Vector3.new(sideWidth, h, 1), Vector3.new(c.X - (DOOR_WIDTH + sideWidth) / 2, wallY, c.Z + d / 2) })
	table.insert(walls, { "FrontWallRight", Vector3.new(sideWidth, h, 1), Vector3.new(c.X + (DOOR_WIDTH + sideWidth) / 2, wallY, c.Z + d / 2) })
	for _, info in ipairs(walls) do
		local wall = makePart(folder, info[1], info[2], info[3], glass, Enum.Material.Glass)
		wall.Transparency = 0.5
	end
	makePart(folder, "GoldTrim", Vector3.new(w, 0.5, 1.2), Vector3.new(c.X, c.Y + 0.5 + h, c.Z - d / 2), gold, Enum.Material.Neon)

	local door = makePart(folder, "VipDoor", Vector3.new(DOOR_WIDTH, h, 1), Vector3.new(c.X, wallY, c.Z + d / 2), gold, Enum.Material.Neon)
	door.Transparency = 0.55
	door.CollisionGroup = DOOR_GROUP

	local sign = makePart(folder, "Sign", Vector3.new(DOOR_WIDTH + 4, 3, 1), Vector3.new(c.X, c.Y + h + 2.5, c.Z + d / 2), Color3.fromRGB(30, 30, 40))
	local gui = Instance.new("SurfaceGui")
	gui.Face = Enum.NormalId.Back -- faces the plots (+Z)
	gui.Parent = sign
	local label = Instance.new("TextLabel")
	label.Size = UDim2.fromScale(1, 1)
	label.BackgroundTransparency = 1
	label.TextScaled = true
	label.Font = Enum.Font.GothamBold
	label.TextColor3 = gold
	label.Text = "👑 VIP LOUNGE"
	label.Parent = gui

	-- Somewhere comfy to sit
	for i = -1, 1, 2 do
		local seat = Instance.new("Seat")
		seat.Name = "VipSeat"
		seat.Size = Vector3.new(4, 1, 4)
		seat.Position = Vector3.new(c.X + i * 8, c.Y + 1, c.Z - d / 2 + 5)
		seat.Color = gold
		seat.Material = Enum.Material.Fabric
		seat.Anchored = true
		seat.Parent = folder
	end

	-- Touching the door: VIPs walk through; everyone else gets offered the VIP pass
	door.Touched:Connect(function(hit)
		local player = Players:GetPlayerFromCharacter(hit.Parent)
		if not player or hasEffect(player, "vipLounge") or passCheckPending[player] then return end -- still asking Roblox about their passes
		if doorCooldown[player] and os.clock() - doorCooldown[player] < 10 then return end
		doorCooldown[player] = os.clock()
		local vipPass = findVipPass()
		if vipPass and ShopConfig.isForSale(vipPass) then
			MarketplaceService:PromptGamePassPurchase(player, vipPass.id)
		else
			notify(player, "The VIP Lounge is for VIP pass holders only.")
		end
	end)
end

-- Studio Debug tab ------------------------------------------------------

local function handleDebug(player, action, key)
	-- Double-check: this remote is never created on live servers, but refuse anyway
	if not RunService:IsStudio() or not ShopConfig.DebugInStudio then
		return "Debug is disabled"
	end
	if typeof(action) ~= "string" or (key ~= nil and typeof(key) ~= "string") then
		return "Bad request"
	end
	local data = core.getData(player)
	if not data or not data.ready then
		return "Your data is still loading"
	end

	if action == "IgnoreRealPasses" then
		data.shop.ignoreRealPasses = not data.shop.ignoreRealPasses
		player:SetAttribute("DebugIgnoreRealPasses", data.shop.ignoreRealPasses)
		publish(player)
		return data.shop.ignoreRealPasses and "Now ignoring passes you really own (not saved)" or "Your real passes count again"

	elseif action == "TogglePass" then
		local pass = ShopConfig.getPass(key)
		if not pass then return "Unknown pass" end
		data.shop.debugPasses[key] = not data.shop.debugPasses[key]
		publish(player)
		return pass.name .. " is now " .. (owns(data.shop, key) and "ON" or "OFF") .. " (simulated, not saved)"

	elseif action == "GrantProduct" then
		local product = ShopConfig.getProduct(key)
		if not product then return "Unknown product" end
		local purchaseId = "STUDIO-" .. HttpService:GenerateGUID(false)
		lastDebugReceipt[player] = { product = product, purchaseId = purchaseId }
		local decision = grantProduct(player, product, purchaseId)
		return product.name .. " -> " .. decision.Name

	elseif action == "RepeatReceipt" then
		local last = lastDebugReceipt[player]
		if not last then return "Grant a product first" end
		local decision = grantProduct(player, last.product, last.purchaseId)
		return "Same receipt again -> " .. decision.Name .. ". Nothing was granted twice."
	end
	local extra = extraDebugActions[action]
	if extra then
		return extra(player, data, key)
	end
	return "Unknown action"
end

-- Lets other systems (like EmployeeServer) add Studio-only buttons to the Debug tab.
-- They only ever run in Studio: the Debug remote doesn't exist on live servers.
function ShopServer.addDebugAction(name, handler)
	extraDebugActions[name] = handler
end

-- Lets other systems grant product effects they own (PoachServer: Poach Shield).
-- handler(player, data, effect) runs inside ProcessReceipt, so it must not wait/yield,
-- and returns what was gained, like "+60 min of Poach Shield".
function ShopServer.addProductHandler(field, handler)
	productHandlers[field] = handler
end

-- Setup -----------------------------------------------------------------

function ShopServer.init(coreApi)
	core = coreApi

	local remotes = Instance.new("Folder")
	remotes.Name = "ShopRemotes"
	notifyEvent = Instance.new("RemoteEvent")
	notifyEvent.Name = "ShopNotify"
	notifyEvent.Parent = remotes
	if RunService:IsStudio() and ShopConfig.DebugInStudio then
		local debugRemote = Instance.new("RemoteFunction")
		debugRemote.Name = "ShopDebug"
		debugRemote.OnServerInvoke = handleDebug
		debugRemote.Parent = remotes
	end
	remotes.Parent = ReplicatedStorage

	for _, group in ipairs({ DOOR_GROUP, VIP_GROUP }) do
		if not PhysicsService:IsCollisionGroupRegistered(group) then
			PhysicsService:RegisterCollisionGroup(group)
		end
	end
	PhysicsService:CollisionGroupSetCollidable(DOOR_GROUP, VIP_GROUP, false)
	buildVipLounge()

	MarketplaceService.ProcessReceipt = processReceipt
	MarketplaceService.PromptGamePassPurchaseFinished:Connect(onPassPromptFinished)

	Players.PlayerRemoving:Connect(function(player)
		lastDebugReceipt[player] = nil
		doorCooldown[player] = nil
		passCheckPending[player] = nil
		passConfirming[player] = nil
	end)

	-- Anyone who gets into the lounge without VIP (glitch or exploit) is put back outside
	task.spawn(function()
		while true do
			task.wait(0.5)
			for _, player in ipairs(Players:GetPlayers()) do
				local root = player.Character and player.Character:FindFirstChild("HumanoidRootPart")
				if root and isInsideLounge(root.Position) and not hasEffect(player, "vipLounge") and not passCheckPending[player] then
					root.CFrame = CFrame.new(LOUNGE_CENTER + Vector3.new(0, 4, LOUNGE_SIZE.Z / 2 + 6))
					notify(player, "The VIP Lounge is for VIP pass holders only.")
				end
			end
		end
	end)

	-- Passes bought outside the game (e.g. on the website) show up without rejoining
	task.spawn(function()
		while true do
			task.wait(PASS_RECHECK_SECONDS)
			for _, player in ipairs(Players:GetPlayers()) do
				local data = core.getData(player)
				if data and data.ready then
					checkPasses(player, data.shop) -- publishes each pass it finds
				end
			end
		end
	end)
end

return ShopServer
