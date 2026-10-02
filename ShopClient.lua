-- ShopClient: the Shop button and shop window (milestone 3).
-- Put this LocalScript in StarterPlayer > StarterPlayerScripts. It builds the screen by itself.
-- It only opens Roblox's purchase prompts. Everything is granted by ShopServer on the server.

local Players = game:GetService("Players")
local MarketplaceService = game:GetService("MarketplaceService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local GuiService = game:GetService("GuiService")

local ShopConfig = require(ReplicatedStorage:WaitForChild("ShopConfig"))
local CreatureConfig = require(ReplicatedStorage:WaitForChild("CreatureConfig")) -- Luck Boost odds, egg Debug buttons
local IpoConfig = require(ReplicatedStorage:WaitForChild("IpoConfig")) -- the Talent Scouts perk, for Luck Boost's odds
local remotes = ReplicatedStorage:WaitForChild("ShopRemotes")
local notifyEvent = remotes:WaitForChild("ShopNotify")
local debugRemote = RunService:IsStudio() and remotes:FindFirstChild("ShopDebug") or nil -- Studio only

local player = Players.LocalPlayer

local COLORS = {
	panel = Color3.fromRGB(28, 30, 38),
	card = Color3.fromRGB(42, 45, 56),
	tab = Color3.fromRGB(55, 58, 72),
	text = Color3.new(1, 1, 1),
	subtext = Color3.fromRGB(185, 190, 205),
	buy = Color3.fromRGB(0, 200, 90), -- same green as the buy pad
	owned = Color3.fromRGB(60, 105, 80),
	disabled = Color3.fromRGB(85, 88, 100),
	gold = Color3.fromRGB(255, 200, 60),
	close = Color3.fromRGB(210, 65, 65),
	debug = Color3.fromRGB(215, 125, 40),
}

local pending = {} -- item key -> token while its Roblox purchase prompt is open
local cards = {} -- refresh functions, one per card
local cardParts = {} -- the pieces of every card, resized by applyLayout on small screens
local incomeValue -- leaderstats.Income, used to preview cash pack sizes

-- UI helpers ------------------------------------------------------------

local function make(className, props)
	local inst = Instance.new(className)
	local parent = props.Parent
	props.Parent = nil
	for key, value in pairs(props) do
		inst[key] = value
	end
	inst.Parent = parent
	return inst
end

local function round(inst, radius)
	make("UICorner", { CornerRadius = UDim.new(0, radius), Parent = inst })
end

-- Text shrinks to fit small phone screens but never grows past maxSize
local function fitText(inst, maxSize)
	inst.TextScaled = true
	make("UITextSizeConstraint", { MaxTextSize = maxSize, MinTextSize = 8, Parent = inst })
end

local function setButton(button, text, color, clickable)
	button.Text = text
	button.BackgroundColor3 = color
	button.AutoButtonColor = clickable
end

-- Screen ----------------------------------------------------------------

local gui = make("ScreenGui", {
	Name = "ShopGui",
	ResetOnSpawn = false, -- keep the shop as it was when your character respawns
	ZIndexBehavior = Enum.ZIndexBehavior.Sibling,
	Parent = player:WaitForChild("PlayerGui"),
})

-- HUD button: left middle of the screen, big enough for thumbs
local shopButton = make("TextButton", {
	Name = "ShopButton",
	AnchorPoint = Vector2.new(0, 0.5),
	Position = UDim2.new(0, 12, 0.5, 0),
	Size = UDim2.fromOffset(76, 76),
	BackgroundColor3 = COLORS.buy,
	Font = Enum.Font.GothamBold,
	Text = "🛒\nSHOP",
	TextColor3 = COLORS.text,
	Parent = gui,
})
round(shopButton, 18)
fitText(shopButton, 22)
make("UIStroke", { Thickness = 3, Transparency = 0.5, ApplyStrokeMode = Enum.ApplyStrokeMode.Border, Parent = shopButton })

-- HUD buttons share one layout (EmployeeClient, PoachClient and IpoClient do the same):
-- EGGS = slot 0, SHOP = 1, TEAM = 2, POACH = 3, IPO = 4.
-- A column centered on the left, or a row at the top-left on short phone screens, where the
-- column would sit under the joystick.
local function placeHudButton(button, slot)
	local function place()
		if gui.AbsoluteSize.Y < 460 then
			button.AnchorPoint = Vector2.new(0, 0)
			button.Size = UDim2.fromOffset(64, 64)
			button.Position = UDim2.fromOffset(10 + slot * 72, 6)
		else
			button.AnchorPoint = Vector2.new(0, 0.5)
			button.Size = UDim2.fromOffset(76, 76)
			button.Position = UDim2.new(0, 12, 0.5, (slot - 2) * 86)
		end
	end
	place()
	gui:GetPropertyChangedSignal("AbsoluteSize"):Connect(place)
end
placeHudButton(shopButton, 1)

local toast = make("TextLabel", {
	Name = "Toast",
	AnchorPoint = Vector2.new(0.5, 1),
	Position = UDim2.new(0.5, 0, 1, -16), -- bottom middle, clear of the HUD buttons
	Size = UDim2.new(0.6, 0, 0, 48),
	BackgroundColor3 = COLORS.panel,
	BackgroundTransparency = 0.1,
	Font = Enum.Font.GothamBold,
	TextColor3 = COLORS.gold,
	Visible = false,
	ZIndex = 10,
	Parent = gui,
})
round(toast, 12)
fitText(toast, 22)
make("UISizeConstraint", { MaxSize = Vector2.new(520, 48), Parent = toast })

local window = make("Frame", {
	Name = "Window",
	AnchorPoint = Vector2.new(0.5, 0.5),
	Position = UDim2.fromScale(0.5, 0.5),
	Size = UDim2.fromScale(0.92, 0.92),
	BackgroundColor3 = COLORS.panel,
	Visible = false,
	Parent = gui,
})
round(window, 18)
make("UISizeConstraint", { MaxSize = Vector2.new(640, 470), Parent = window })
make("UIPadding", {
	PaddingTop = UDim.new(0, 10),
	PaddingBottom = UDim.new(0, 10),
	PaddingLeft = UDim.new(0, 10),
	PaddingRight = UDim.new(0, 10),
	Parent = window,
})

local title = make("TextLabel", {
	Size = UDim2.new(1, -56, 0, 40),
	BackgroundTransparency = 1,
	Font = Enum.Font.GothamBold,
	Text = "Startup Shop",
	TextColor3 = COLORS.gold,
	TextXAlignment = Enum.TextXAlignment.Left,
	Parent = window,
})
fitText(title, 28)

local closeButton = make("TextButton", {
	AnchorPoint = Vector2.new(1, 0),
	Position = UDim2.fromScale(1, 0),
	Size = UDim2.fromOffset(44, 40),
	BackgroundColor3 = COLORS.close,
	Font = Enum.Font.GothamBold,
	Text = "X",
	TextColor3 = COLORS.text,
	Parent = window,
})
round(closeButton, 10)
fitText(closeButton, 22)

local tabBar = make("Frame", {
	Position = UDim2.new(0, 0, 0, 48),
	Size = UDim2.new(1, 0, 0, 42),
	BackgroundTransparency = 1,
	Parent = window,
})
make("UIListLayout", {
	FillDirection = Enum.FillDirection.Horizontal,
	Padding = UDim.new(0, 6),
	SortOrder = Enum.SortOrder.LayoutOrder,
	Parent = tabBar,
})

local pages = make("Frame", {
	Position = UDim2.new(0, 0, 0, 98),
	Size = UDim2.new(1, 0, 1, -98),
	BackgroundTransparency = 1,
	Parent = window,
})

local tabNames = { "Passes", "Boosts", "Cash" }
if debugRemote then
	table.insert(tabNames, "Debug")
end
local tabButtons, tabPages = {}, {}
for i, name in ipairs(tabNames) do
	local tabButton = make("TextButton", {
		LayoutOrder = i,
		Size = UDim2.new(1 / #tabNames, -6, 1, 0),
		BackgroundColor3 = COLORS.tab,
		Font = Enum.Font.GothamBold,
		Text = name,
		TextColor3 = COLORS.text,
		Parent = tabBar,
	})
	round(tabButton, 10)
	fitText(tabButton, 20)
	tabButtons[name] = tabButton

	local page = make("ScrollingFrame", {
		Size = UDim2.fromScale(1, 1),
		BackgroundTransparency = 1,
		BorderSizePixel = 0,
		CanvasSize = UDim2.new(),
		AutomaticCanvasSize = Enum.AutomaticSize.Y,
		ScrollingDirection = Enum.ScrollingDirection.Y,
		ScrollBarThickness = 6,
		Visible = false,
		Parent = pages,
	})
	make("UIListLayout", { Padding = UDim.new(0, 8), SortOrder = Enum.SortOrder.LayoutOrder, Parent = page })
	make("UIPadding", { PaddingRight = UDim.new(0, 10), Parent = page }) -- room for the scrollbar
	tabPages[name] = page
end

-- One row in the shop: icon, name, description, and a button on the right
local function makeCard(page, order, icon, name)
	local card = make("Frame", {
		LayoutOrder = order,
		Size = UDim2.new(1, 0, 0, 84),
		BackgroundColor3 = COLORS.card,
		Parent = page,
	})
	round(card, 12)

	local iconLabel = make("TextLabel", {
		AnchorPoint = Vector2.new(0, 0.5),
		Position = UDim2.new(0, 8, 0.5, 0),
		Size = UDim2.fromOffset(52, 52),
		BackgroundTransparency = 1,
		Font = Enum.Font.GothamBold,
		Text = icon,
		TextColor3 = COLORS.text,
		Parent = card,
	})
	fitText(iconLabel, 40)

	local nameLabel = make("TextLabel", {
		Position = UDim2.new(0, 68, 0, 8),
		Size = UDim2.new(1, -68 - 136, 0, 24),
		BackgroundTransparency = 1,
		Font = Enum.Font.GothamBold,
		Text = name,
		TextColor3 = COLORS.text,
		TextXAlignment = Enum.TextXAlignment.Left,
		Parent = card,
	})
	fitText(nameLabel, 20)

	local descLabel = make("TextLabel", {
		Position = UDim2.new(0, 68, 0, 34),
		Size = UDim2.new(1, -68 - 136, 0, 44),
		BackgroundTransparency = 1,
		Font = Enum.Font.Gotham,
		Text = "",
		TextColor3 = COLORS.subtext,
		TextWrapped = true,
		TextXAlignment = Enum.TextXAlignment.Left,
		TextYAlignment = Enum.TextYAlignment.Top,
		Parent = card,
	})
	fitText(descLabel, 15)

	local button = make("TextButton", {
		AnchorPoint = Vector2.new(1, 0.5),
		Position = UDim2.new(1, -8, 0.5, 0),
		Size = UDim2.fromOffset(124, 52),
		BackgroundColor3 = COLORS.buy,
		Font = Enum.Font.GothamBold,
		Text = "",
		TextColor3 = COLORS.text,
		Parent = card,
	})
	round(button, 10)
	fitText(button, 20)

	table.insert(cardParts, { card = card, icon = iconLabel, name = nameLabel, desc = descLabel, button = button })
	return descLabel, button
end

-- Phones: a shorter header on short screens, narrower buttons on narrow screens,
-- so descriptions stay readable. Runs again whenever the screen size changes.
local function applyLayout()
	local size = window.AbsoluteSize
	local short = size.Y < 330
	local narrow = size.X < 480

	local headerHeight = short and 34 or 40
	local tabHeight = short and 34 or 42
	title.Size = UDim2.new(1, -56, 0, headerHeight)
	closeButton.Size = UDim2.fromOffset(44, headerHeight)
	tabBar.Position = UDim2.new(0, 0, 0, headerHeight + 6)
	tabBar.Size = UDim2.new(1, 0, 0, tabHeight)
	local top = headerHeight + tabHeight + 14
	pages.Position = UDim2.new(0, 0, 0, top)
	pages.Size = UDim2.new(1, 0, 1, -top)

	local buttonWidth = narrow and 92 or 124
	local iconSize = narrow and 36 or 52
	local textX = iconSize + 14
	local textWidth = -textX - buttonWidth - 16
	for _, parts in ipairs(cardParts) do
		parts.card.Size = UDim2.new(1, 0, 0, narrow and 96 or 84)
		parts.icon.Size = UDim2.fromOffset(iconSize, iconSize)
		parts.name.Position = UDim2.new(0, textX, 0, 8)
		parts.name.Size = UDim2.new(1, textWidth, 0, 22)
		parts.desc.Position = UDim2.new(0, textX, 0, 32)
		parts.desc.Size = UDim2.new(1, textWidth, 1, -38)
		parts.button.Size = UDim2.fromOffset(buttonWidth, 48)
	end
end

-- Behaviour -------------------------------------------------------------

local function refreshAll()
	for _, refresh in ipairs(cards) do
		refresh()
	end
end

local toastToken = 0
local function showToast(text)
	toastToken += 1
	local myToken = toastToken
	toast.Text = text
	toast.Visible = true
	task.delay(3.5, function()
		if toastToken == myToken then
			toast.Visible = false
		end
	end)
end

-- Paid random items restricted for this player (the server asks Roblox's PolicyService on join)?
-- Not known yet counts as restricted, like on the server: Luck Boost stays hidden until it's known.
local function randomRestricted()
	return player:GetAttribute("RandomRestricted") ~= false
end

-- Opens Roblox's purchase prompt. Nothing is granted here: the server does that
-- after Roblox confirms the purchase.
local promptToken = 0
local function promptPurchase(item, isPass)
	if pending[item.key] or not ShopConfig.isForSale(item, randomRestricted()) then return end
	if isPass and player:GetAttribute("Pass_" .. item.key) then return end

	promptToken += 1
	local myToken = promptToken
	pending[item.key] = myToken
	refreshAll()

	local ok, err = pcall(function()
		if isPass then
			MarketplaceService:PromptGamePassPurchase(player, item.id)
		else
			MarketplaceService:PromptProductPurchase(player, item.id)
		end
	end)
	if not ok then
		warn("Purchase prompt failed: " .. tostring(err))
		pending[item.key] = nil
		refreshAll()
		showToast("Couldn't open the purchase. Please try again.")
		return
	end

	-- Safety net: if Roblox never tells us the prompt closed, unlock the button again
	task.delay(30, function()
		if pending[item.key] == myToken then
			pending[item.key] = nil
			refreshAll()
		end
	end)
end

local function formatTime(seconds)
	seconds = math.max(0, math.floor(seconds))
	return string.format("%d:%02d", seconds // 60, seconds % 60)
end

-- Luck Boost's effect in numbers, before buying (Roblox's Paid Random Items policy), from the same
-- config and luck the server rolls with (Talent Scouts included): the boosted rarities, and the
-- rarest hire of the last (best) egg without and with the boost.
local function luckText(effect)
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

-- Description text that changes while you play (cash pack size, boost timer, tokens)
local function productText(product)
	local effect = product.effect
	if effect.incomeMinutes then
		local income = incomeValue and incomeValue.Value or 0
		return "Get " .. ShopConfig.formatCash(ShopConfig.cashPackAmount(product, income)) .. " now. " .. product.description
	end
	local text = product.description
	if effect.luckMultiplier then
		text = luckText(effect) .. " " .. text
	end
	if effect.luckMinutes then
		local left = (player:GetAttribute("LuckBoostUntil") or 0) - workspace:GetServerTimeNow()
		if left > 0 then
			text ..= "\nActive: " .. formatTime(left) .. " left"
		end
	end
	if effect.instantHatches then
		text ..= "\nYou have " .. (player:GetAttribute("InstantHatches") or 0)
	end
	if effect.shieldMinutes then
		local left = (player:GetAttribute("PoachShieldUntil") or 0) - workspace:GetServerTimeNow()
		if left > 0 then
			text ..= "\nProtected: " .. formatTime(left) .. " left"
		end
	end
	return text
end

-- Cards -----------------------------------------------------------------

for i, pass in ipairs(ShopConfig.Passes) do
	local desc, button = makeCard(tabPages.Passes, i, pass.icon, pass.name)
	desc.Text = pass.description
	button.Activated:Connect(function()
		promptPurchase(pass, true)
	end)
	table.insert(cards, function()
		if player:GetAttribute("Pass_" .. pass.key) then
			setButton(button, "Owned", COLORS.owned, false)
		elseif pending[pass.key] then
			setButton(button, "...", COLORS.disabled, false)
		elseif not ShopConfig.isForSale(pass) then
			setButton(button, "Coming soon", COLORS.disabled, false)
		else
			setButton(button, "R$ " .. pass.price, COLORS.buy, true)
		end
	end)
end

for i, product in ipairs(ShopConfig.Products) do
	local page = tabPages[product.tab]
	if page then
		local desc, button = makeCard(page, i, product.icon, product.name)
		button.Activated:Connect(function()
			promptPurchase(product, false)
		end)
		table.insert(cards, function()
			-- Luck Boost (changesOdds) is hidden where paid random items are restricted: their hires follow
			-- a fixed order, so it would do nothing. Everything else stays on sale.
			desc.Parent.Visible = not (product.changesOdds and randomRestricted())
			desc.Text = productText(product)
			if pending[product.key] then
				setButton(button, "...", COLORS.disabled, false)
			elseif not ShopConfig.isForSale(product) then
				setButton(button, "Coming soon", COLORS.disabled, false)
			else
				setButton(button, "R$ " .. product.price, COLORS.buy, true)
			end
		end)
	else
		warn("ShopConfig: product " .. product.key .. " has unknown tab " .. tostring(product.tab))
	end
end

-- Studio-only Debug tab: pretend to own passes and push fake receipts through the real server code
if debugRemote then
	local page = tabPages.Debug
	local status = make("TextLabel", {
		LayoutOrder = 0,
		Size = UDim2.new(1, 0, 0, 52),
		BackgroundColor3 = COLORS.debug,
		Font = Enum.Font.GothamBold,
		Text = "STUDIO ONLY: test without Robux. This tab never exists in live servers.",
		TextColor3 = COLORS.text,
		TextWrapped = true,
		Parent = page,
	})
	round(status, 12)
	fitText(status, 16)

	local busy = false
	local function runDebug(action, key)
		if busy then return end
		busy = true
		status.Text = "Working..."
		local ok, result = pcall(function()
			return debugRemote:InvokeServer(action, key)
		end)
		busy = false
		status.Text = ok and tostring(result) or ("Debug failed: " .. tostring(result))
	end

	local order = 1
	local ignoreDesc, ignoreButton = makeCard(page, order, "🙈", "Ignore passes I really own")
	order += 1
	ignoreDesc.Text = "As the creator you own every pass. Turn this on to test like a normal player."
	ignoreButton.Activated:Connect(function()
		runDebug("IgnoreRealPasses")
	end)
	table.insert(cards, function()
		local on = player:GetAttribute("DebugIgnoreRealPasses")
		setButton(ignoreButton, on and "ON" or "OFF", on and COLORS.buy or COLORS.disabled, true)
	end)
	for _, pass in ipairs(ShopConfig.Passes) do
		local desc, button = makeCard(page, order, pass.icon, "Pass: " .. pass.name)
		order += 1
		desc.Text = "Pretend you own this pass (resets when you stop playing)."
		button.Activated:Connect(function()
			runDebug("TogglePass", pass.key)
		end)
		table.insert(cards, function()
			local owned = player:GetAttribute("Pass_" .. pass.key)
			setButton(button, owned and "ON" or "OFF", owned and COLORS.buy or COLORS.disabled, true)
		end)
	end
	for _, product in ipairs(ShopConfig.Products) do
		local desc, button = makeCard(page, order, product.icon, "Give: " .. product.name)
		order += 1
		desc.Text = "Sends a fake receipt through the real purchase code, including saving."
		setButton(button, "Give", COLORS.debug, true)
		button.Activated:Connect(function()
			runDebug("GrantProduct", product.key)
		end)
	end
	local desc, button = makeCard(page, order, "🔁", "Repeat last receipt")
	order += 1
	desc.Text = "Sends the same PurchaseId again. Nothing should be given twice."
	setButton(button, "Repeat", COLORS.debug, true)
	button.Activated:Connect(function()
		runDebug("RepeatReceipt")
	end)

	-- Eggs and employees (milestone 2)
	local function debugRow(icon, name, text, buttonText, action, arg)
		local rowDesc, rowButton = makeCard(page, order, icon, name)
		order += 1
		rowDesc.Text = text
		setButton(rowButton, buttonText, COLORS.debug, true)
		rowButton.Activated:Connect(function()
			runDebug(action, arg)
		end)
	end
	debugRow("💵", "Give $10,000", "Adds Cash right away, for buying eggs.", "Give", "GiveCash", "10000")
	debugRow("🏦", "Give $1,000,000", "Enough for lots of Unicorn Eggs.", "Give", "GiveCash", "1000000")
	for _, rarity in ipairs(CreatureConfig.Rarities) do
		debugRow("🎲", "Next hatch: " .. rarity.key, "The next egg you hatch will be " .. rarity.key .. ".", "Set", "ForceRarity", rarity.key)
	end
	debugRow("⏩", "Skip egg timers", "Every egg in your incubators becomes ready now.", "Skip", "SkipEggTimers")
	debugRow("🌍", "Paid random items: restricted on/off", "Pretends Roblox's policy check said the other thing: fixed hire order and no Luck Boost, or back to random hires. Not saved: a rejoin asks Roblox again.", "Switch", "ToggleRandomRestricted")

	-- Poaching (milestone 3 poaching)
	debugRow("🤖", "Spawn dummy target", "Adds a fake player with 6 employees to the Poach window, to test alone.", "Spawn", "PoachSpawnDummy")
	debugRow("🏢", "Dummy HR level +1", "Raises the dummy's HR Department (after Lv 5 it goes back to 0).", "+1", "PoachDummyHR")
	debugRow("🦹", "Dummy poaches me", "The dummy negotiates for your best employee and always wins, unless you get a Poach Shield first. Tests the warning and the Counter-Offer.", "Poach me", "PoachDummyAttack")
	debugRow("✅", "Next poach: success", "Your next negotiation always works.", "Set", "PoachForce", "success")
	debugRow("❌", "Next poach: failure", "Your next negotiation always fails.", "Set", "PoachForce", "fail")
	debugRow("🧹", "Clear shields and cooldowns", "For everyone in this server: no shields, no loss limit, no waiting.", "Clear", "PoachClearTimers")

	-- IPO (milestone 4)
	debugRow("📈", "Valuation +$100,000", "Raises your valuation (not your Cash), to climb the funding stages.", "Give", "IpoGrantValuation", "100000")
	debugRow("🔔", "Jump to IPO-ready", "Raises your valuation to exactly what going public needs, and skips the IPO cooldown.", "Jump", "IpoJumpReady")
	debugRow("📜", "Give 50 Shares", "Shares to try the IPO shop.", "Give", "IpoGrantShares", "50")
	debugRow("💥", "Next IPO save fails", "The next IPO pretends its save failed. Nothing should change, and you're told.", "Set", "IpoFailNextSave")
	debugRow("♻️", "Reset IPO progress", "0 IPOs, 0 Shares, no perks, valuation 0. Eggs in extra incubators are removed.", "Reset", "IpoReset")

	-- First minute (milestone 5)
	debugRow("🐣", "Restart tutorial", "Gives the free egg again and brings back the arrow and goal tracker, on any save.", "Restart", "OnboardingRestart")
	debugRow("👴", "Act like an old save", "Counts you as a player from before milestone 5: no arrow, no tracker.", "Set", "OnboardingMarkOld")

	-- Daily rewards (milestone 6)
	debugRow("📅", "Daily: next day (fake)", "Pretends one UTC day passed for you. After a claim: once = next day, twice = 1 missed day (place kept), 3 times = 2 missed days (back to Day 1).", "+1 day", "DailyNextDay")
	debugRow("🗓️", "Daily: reset calendar", "Like a save from before milestone 6: next claim is Day 1, no streak.", "Reset", "DailyReset")
end

-- Tabs, opening and closing ---------------------------------------------

local function showTab(name)
	for tabName, page in pairs(tabPages) do
		page.Visible = tabName == name
		tabButtons[tabName].BackgroundColor3 = tabName == name and COLORS.buy or COLORS.tab
	end
end

for name, tabButton in pairs(tabButtons) do
	tabButton.Activated:Connect(function()
		showTab(name)
	end)
end

-- Only one window is open at a time: each window writes its name into PlayerGui's "OpenPanel"
-- attribute, and closes itself when another one opens
local playerGui = gui.Parent

local function setOpen(open)
	window.Visible = open
	if open then
		playerGui:SetAttribute("OpenPanel", "Shop")
	elseif playerGui:GetAttribute("OpenPanel") == "Shop" then
		playerGui:SetAttribute("OpenPanel", nil)
	end
	-- Hide the phone joystick and jump button while a window is open, so they don't cover buttons
	GuiService.TouchControlsEnabled = playerGui:GetAttribute("OpenPanel") == nil
	if open then
		refreshAll()
	end
end

playerGui:GetAttributeChangedSignal("OpenPanel"):Connect(function()
	if window.Visible and playerGui:GetAttribute("OpenPanel") ~= "Shop" then
		window.Visible = false
	end
end)

shopButton.Activated:Connect(function()
	setOpen(not window.Visible)
end)
closeButton.Activated:Connect(function()
	setOpen(false)
end)

showTab("Passes")
refreshAll()
applyLayout()
window:GetPropertyChangedSignal("AbsoluteSize"):Connect(applyLayout)

-- Keeping it up to date -------------------------------------------------

-- The server changes these attributes when you buy something (or use the Debug tab)
player.AttributeChanged:Connect(refreshAll)

-- Prompt closed: unlock the button. If it was bought, the server confirms and the card updates.
MarketplaceService.PromptGamePassPurchaseFinished:Connect(function(who, passId)
	if who ~= player then return end
	local pass = ShopConfig.getPassById(passId)
	if pass then
		pending[pass.key] = nil
	end
	refreshAll()
end)

MarketplaceService.PromptProductPurchaseFinished:Connect(function(userId, productId)
	if userId ~= player.UserId then return end
	local product = ShopConfig.getProductById(productId)
	if product then
		pending[product.key] = nil
	end
	refreshAll()
end)

notifyEvent.OnClientEvent:Connect(showToast)

task.spawn(function()
	incomeValue = player:WaitForChild("leaderstats"):WaitForChild("Income")
	refreshAll()
end)

-- Timers and cash pack sizes tick while the shop is open
while true do
	task.wait(1)
	if window.Visible then
		refreshAll()
	end
end
