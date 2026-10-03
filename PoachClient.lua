-- PoachClient: the Poach window, the negotiation mini-screen and poaching alerts (milestone 3 poaching).
-- Put this LocalScript in StarterPlayer > StarterPlayerScripts. It builds the screens by itself.
-- It only shows what the server says and asks PoachServer to do things (poach, counter-offer).

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local GuiService = game:GetService("GuiService")
local TweenService = game:GetService("TweenService")
local MarketplaceService = game:GetService("MarketplaceService")

local CreatureConfig = require(ReplicatedStorage:WaitForChild("CreatureConfig"))
local CreatureModels = require(ReplicatedStorage:WaitForChild("CreatureModels"))
local ShopConfig = require(ReplicatedStorage:WaitForChild("ShopConfig"))
local remotes = ReplicatedStorage:WaitForChild("PoachRemotes")
local poachAction = remotes:WaitForChild("PoachAction")
local poachEvent = remotes:WaitForChild("PoachEvent")

local player = Players.LocalPlayer
local playerGui = player:WaitForChild("PlayerGui")
local PANEL_NAME = "Poaching"
local RULES = CreatureConfig.Poaching

local COLORS = {
	panel = Color3.fromRGB(28, 30, 38),
	card = Color3.fromRGB(42, 45, 56),
	tab = Color3.fromRGB(55, 58, 72),
	text = Color3.new(1, 1, 1),
	subtext = Color3.fromRGB(185, 190, 205),
	buy = Color3.fromRGB(0, 200, 90), -- same green as the buy pad
	disabled = Color3.fromRGB(85, 88, 100),
	gold = Color3.fromRGB(255, 200, 60),
	danger = Color3.fromRGB(210, 65, 65),
	poach = Color3.fromRGB(225, 95, 60),
	hr = Color3.fromRGB(150, 90, 255), -- the HR Department's purple
}

local NEGOTIATION_LINES = {
	"Offering free snacks...",
	"Promising stock options...",
	"Showing off the ping-pong table...",
	"Matching their salary...",
	"Adding a signing bonus...",
	"Mentioning the nap pods...",
	"Talking about remote Fridays...",
}

-- The latest Poach window state from the server
local snapshot = { targets = {}, freeSlot = true, negotiating = false, counterOffer = false }
local targetsById, entriesById = {}, {}
local counterOffer -- { creature, attacker, price, expiresAt } while a buy-back is possible
local refreshers = {} -- functions that redraw parts of the window
local cardParts = {} -- card pieces resized by applyLayout on small screens

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
	make("UICorner", { CornerRadius = radius and UDim.new(0, radius) or UDim.new(0.5, 0), Parent = inst })
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

local function hex(color)
	return "#" .. color:ToHex()
end

-- Player names go into rich text, so < > & must not be read as tags
local function escape(text)
	return (text:gsub("&", "&amp;"):gsub("<", "&lt;"):gsub(">", "&gt;"))
end

local function rarityColor(rarityKey)
	local rarity = CreatureConfig.getRarity(rarityKey)
	return rarity and rarity.color or COLORS.text
end

local function coloredName(creature)
	return string.format('<font color="%s">%s</font>', hex(rarityColor(creature.rarity)), creature.name)
end

local function formatCash(amount)
	return ShopConfig.formatCash(amount)
end

local function formatTime(seconds)
	return CreatureConfig.formatTime(seconds)
end

local function percent(chance)
	return math.floor(chance * 100 + 0.5) .. "%"
end

local function now()
	return workspace:GetServerTimeNow()
end

local function cash()
	local stats = player:FindFirstChild("leaderstats")
	return stats and stats:FindFirstChild("Cash") and stats.Cash.Value or 0
end

local function shieldLeft()
	return (player:GetAttribute("PoachShieldUntil") or 0) - now()
end

local function cooldownLeft()
	return (player:GetAttribute("PoachCooldownUntil") or 0) - now()
end

-- Headhunter and any other pass with a poach bonus
local function poachBonus()
	local bonus = 0
	for _, pass in ipairs(ShopConfig.Passes) do
		if pass.effect.poachBonus and player:GetAttribute("Pass_" .. pass.key) then
			bonus += pass.effect.poachBonus
		end
	end
	return bonus
end

local function shieldProduct()
	for _, product in ipairs(ShopConfig.Products) do
		if product.effect.shieldMinutes then
			return product
		end
	end
	return nil
end

local function employeeLine(creature)
	return string.format('<font color="%s">%s</font> · %s · $%d/s', hex(rarityColor(creature.rarity)), creature.rarity, creature.role, creature.income)
end

-- Screen ----------------------------------------------------------------

-- Two layers: the HUD button sits under the other windows (DisplayOrder -1), while the Poach
-- window, the top banners and messages sit above every HUD button (DisplayOrder 5)
local gui = make("ScreenGui", {
	Name = "PoachGui",
	ResetOnSpawn = false,
	ZIndexBehavior = Enum.ZIndexBehavior.Sibling,
	DisplayOrder = -1,
	Parent = playerGui,
})
local front = make("ScreenGui", {
	Name = "PoachWindowGui",
	ResetOnSpawn = false,
	ZIndexBehavior = Enum.ZIndexBehavior.Sibling,
	DisplayOrder = 5,
	Parent = playerGui,
})

-- HUD button: slot 3 of the shared layout (EGGS = 0, SHOP = 1, TEAM = 2, POACH = 3).
-- A column on the left middle, or a row at the top-left on short phone screens.
local poachButton = make("TextButton", {
	Name = "PoachButton",
	BackgroundColor3 = COLORS.poach,
	Font = Enum.Font.GothamBold,
	Text = "🤝\nPOACH",
	TextColor3 = COLORS.text,
	Parent = gui,
})
round(poachButton, 18)
fitText(poachButton, 22)
make("UIStroke", { Thickness = 3, Transparency = 0.5, ApplyStrokeMode = Enum.ApplyStrokeMode.Border, Parent = poachButton })
local HUD_SLOT = 3
local function placeHudButton()
	if gui.AbsoluteSize.Y < 460 then
		poachButton.AnchorPoint = Vector2.new(0, 0)
		poachButton.Size = UDim2.fromOffset(64, 64)
		poachButton.Position = UDim2.fromOffset(10 + HUD_SLOT * 72, 6)
	else
		poachButton.AnchorPoint = Vector2.new(0, 0.5)
		poachButton.Size = UDim2.fromOffset(76, 76)
		poachButton.Position = UDim2.new(0, 12, 0.5, (HUD_SLOT - 2) * 86)
	end
end
placeHudButton()

-- A red dot on the button while a Counter-Offer is waiting
local badge = make("TextLabel", {
	AnchorPoint = Vector2.new(0.5, 0.5),
	Position = UDim2.fromScale(0.92, 0.08),
	Size = UDim2.fromOffset(24, 24),
	BackgroundColor3 = COLORS.danger,
	Font = Enum.Font.GothamBold,
	Text = "!",
	TextColor3 = COLORS.text,
	Visible = false,
	Parent = poachButton,
})
round(badge)
fitText(badge, 18)

local toast = make("TextLabel", {
	Name = "Toast",
	AnchorPoint = Vector2.new(0.5, 1),
	Position = UDim2.new(0.5, 0, 1, -128), -- bottom middle, above the egg and shop messages
	Size = UDim2.new(0.6, 0, 0, 48),
	BackgroundColor3 = COLORS.panel,
	BackgroundTransparency = 0.1,
	Font = Enum.Font.GothamBold,
	TextColor3 = COLORS.gold,
	Visible = false,
	ZIndex = 10,
	Parent = front,
})
round(toast, 12)
fitText(toast, 22)
make("UISizeConstraint", { MaxSize = Vector2.new(520, 48), Parent = toast })

local toastToken = 0
local function showToast(text)
	toastToken += 1
	local myToken = toastToken
	toast.Text = text
	toast.Visible = true
	task.delay(4, function()
		if toastToken == myToken then
			toast.Visible = false
		end
	end)
end

local window = make("Frame", {
	Name = "Window",
	AnchorPoint = Vector2.new(0.5, 0.5),
	Position = UDim2.fromScale(0.5, 0.5),
	Size = UDim2.fromScale(0.92, 0.92),
	BackgroundColor3 = COLORS.panel,
	Visible = false,
	Parent = front,
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
	Text = "Poaching",
	TextColor3 = COLORS.gold,
	TextXAlignment = Enum.TextXAlignment.Left,
	Parent = window,
})
fitText(title, 28)

local closeButton = make("TextButton", {
	AnchorPoint = Vector2.new(1, 0),
	Position = UDim2.fromScale(1, 0),
	Size = UDim2.fromOffset(44, 40),
	BackgroundColor3 = COLORS.danger,
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

local tabNames = { "Poach", "Defense" }
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
	make("UIPadding", { PaddingRight = UDim.new(0, 10), Parent = page })
	tabPages[name] = page
end

-- A line of text across the page (status lines and section titles)
local function makeLine(page, order, textColor)
	local label = make("TextLabel", {
		LayoutOrder = order,
		Size = UDim2.new(1, 0, 0, 30),
		BackgroundTransparency = 1,
		Font = Enum.Font.GothamBold,
		Text = "",
		RichText = true,
		TextColor3 = textColor or COLORS.subtext,
		TextXAlignment = Enum.TextXAlignment.Left,
		Parent = page,
	})
	fitText(label, 17)
	return label
end

-- One row: round icon, name, description, and a button on the right (same cards as the Team tab)
local function makeCard(page, order)
	local card = make("Frame", {
		LayoutOrder = order,
		Size = UDim2.new(1, 0, 0, 84),
		BackgroundColor3 = COLORS.card,
		Parent = page,
	})
	round(card, 12)
	local icon = make("TextLabel", {
		AnchorPoint = Vector2.new(0, 0.5),
		Position = UDim2.new(0, 8, 0.5, 0),
		Size = UDim2.fromOffset(52, 52),
		BackgroundColor3 = COLORS.tab,
		Font = Enum.Font.GothamBold,
		Text = "",
		TextColor3 = COLORS.text,
		Parent = card,
	})
	round(icon)
	fitText(icon, 34)
	local name = make("TextLabel", {
		Position = UDim2.new(0, 68, 0, 8),
		Size = UDim2.new(1, -204, 0, 24),
		BackgroundTransparency = 1,
		Font = Enum.Font.GothamBold,
		Text = "",
		RichText = true,
		TextColor3 = COLORS.text,
		TextXAlignment = Enum.TextXAlignment.Left,
		Parent = card,
	})
	fitText(name, 20)
	local desc = make("TextLabel", {
		Position = UDim2.new(0, 68, 0, 34),
		Size = UDim2.new(1, -204, 0, 44),
		BackgroundTransparency = 1,
		Font = Enum.Font.Gotham,
		Text = "",
		RichText = true,
		TextColor3 = COLORS.subtext,
		TextWrapped = true,
		TextXAlignment = Enum.TextXAlignment.Left,
		TextYAlignment = Enum.TextYAlignment.Top,
		Parent = card,
	})
	fitText(desc, 15)
	local button = make("TextButton", {
		AnchorPoint = Vector2.new(1, 0.5),
		Position = UDim2.new(1, -8, 0.5, 0),
		Size = UDim2.fromOffset(124, 52),
		BackgroundColor3 = COLORS.poach,
		Font = Enum.Font.GothamBold,
		Text = "",
		TextColor3 = COLORS.text,
		Parent = card,
	})
	round(button, 10)
	fitText(button, 20)
	local parts = { card = card, icon = icon, name = name, desc = desc, button = button }
	table.insert(cardParts, parts)
	return parts
end

-- Phones: shorter header on short screens, narrower buttons on narrow ones (same as the shop)
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
		if parts.card.Parent then
			parts.card.Size = UDim2.new(1, 0, 0, narrow and 96 or 84)
			parts.icon.Size = UDim2.fromOffset(iconSize, iconSize)
			parts.name.Position = UDim2.new(0, textX, 0, 8)
			parts.name.Size = UDim2.new(1, textWidth, 0, 22)
			parts.desc.Position = UDim2.new(0, textX, 0, 32)
			parts.desc.Size = UDim2.new(1, textWidth, 1, -38)
			parts.button.Size = UDim2.fromOffset(buttonWidth, 48)
		end
	end
end

-- Talking to the server -------------------------------------------------

local busy = false
local function request(action, a, b)
	if busy then return false end
	busy = true
	local ok, success, message = pcall(function()
		return poachAction:InvokeServer(action, a, b)
	end)
	busy = false
	if not ok then
		showToast("Something went wrong. Please try again.")
		return false
	end
	return success, message
end

local refreshAll, setOpen -- defined below

local function setSnapshot(new)
	snapshot = new
	counterOffer = new.counterOffer or nil
	targetsById, entriesById = {}, {}
	for _, target in ipairs(new.targets) do
		targetsById[target.userId] = target
		for _, entry in ipairs(target.employees) do
			entriesById[target.userId .. "/" .. entry.id] = entry
		end
	end
end

local polling = false
local rebuildTargets -- defined below
local function poll()
	if polling then return end
	polling = true
	local ok, success, result = pcall(function()
		return poachAction:InvokeServer("Targets")
	end)
	polling = false
	if ok and success and typeof(result) == "table" then
		setSnapshot(result)
		rebuildTargets()
		refreshAll()
	end
end

-- Poach tab -------------------------------------------------------------

local poachPage = tabPages.Poach
local poachStatus = makeLine(poachPage, 0)
local nobodyLine = makeLine(poachPage, 1)
nobodyLine.Text = "Nobody else is in this server yet. You can only poach from players in the same server."
	.. (RunService:IsStudio() and " (Studio: Shop > Debug > Spawn dummy target)" or "")
local targetWidgets = {} -- rebuilt whenever the list of targets or their employees changes
local headerLines, employeeCards = {}, {}
local layoutKey = ""

local function poachButtonState(target, entry)
	if not entry.chance then
		return "Never", COLORS.disabled, false
	elseif target.mine then
		return "Negotiating", COLORS.gold, false
	elseif target.blocked == "Protected" then
		return "🛡 " .. (target.blockedUntil and formatTime(target.blockedUntil - now()) or "Safe"), COLORS.disabled, false
	elseif target.blocked or snapshot.negotiating then
		return "Busy", COLORS.disabled, false
	elseif cooldownLeft() > 0 then
		return "Wait " .. formatTime(cooldownLeft()), COLORS.disabled, false
	elseif not snapshot.freeSlot then
		return "Team full", COLORS.disabled, false
	end
	return "Poach\n" .. formatCash(entry.cost), cash() >= entry.cost and COLORS.poach or COLORS.disabled, true
end

local function targetHeader(target)
	local bits = { "🏢 " .. escape(target.name), "HR Lv " .. target.hrLevel }
	if target.mine then
		table.insert(bits, "🤝 You're negotiating")
	elseif target.blocked == "Protected" then
		table.insert(bits, "🛡 Protected" .. (target.blockedUntil and (" " .. formatTime(target.blockedUntil - now())) or ""))
	elseif target.blocked == "Busy" then
		table.insert(bits, "🤝 Someone is negotiating")
	elseif target.blocked then
		table.insert(bits, target.blocked)
	end
	if #target.employees == 0 then
		table.insert(bits, "no employees yet")
	end
	return table.concat(bits, " · ")
end

local function onPoachClicked(userId, employeeId)
	local success, message = request("Start", userId, employeeId)
	if success then
		setOpen(false) -- out of the way, so you can watch the negotiation
	elseif message then
		showToast(message)
	end
	task.spawn(poll)
end

function rebuildTargets()
	local keyParts = {}
	for _, target in ipairs(snapshot.targets) do
		table.insert(keyParts, tostring(target.userId))
		for _, entry in ipairs(target.employees) do
			table.insert(keyParts, entry.id)
		end
	end
	local key = table.concat(keyParts, ",")
	if key == layoutKey then return end
	layoutKey = key

	for _, widget in ipairs(targetWidgets) do
		widget:Destroy()
	end
	table.clear(targetWidgets)
	table.clear(headerLines)
	table.clear(employeeCards)
	for i = #cardParts, 1, -1 do
		if not cardParts[i].card.Parent then
			table.remove(cardParts, i)
		end
	end

	local order = 10
	for _, target in ipairs(snapshot.targets) do
		local header = makeLine(poachPage, order, COLORS.gold)
		order += 1
		table.insert(targetWidgets, header)
		table.insert(headerLines, { label = header, userId = target.userId })

		local list = {}
		for _, entry in ipairs(target.employees) do
			local creature = CreatureConfig.getCreature(entry.creature)
			if creature then
				table.insert(list, { entry = entry, creature = creature })
			end
		end
		table.sort(list, function(x, y)
			if x.creature.income ~= y.creature.income then
				return x.creature.income > y.creature.income
			end
			return x.creature.name < y.creature.name
		end)
		for _, item in ipairs(list) do
			local parts = makeCard(poachPage, order)
			order += 1
			parts.userId, parts.employeeId = target.userId, item.entry.id
			parts.icon.Text = item.creature.emoji
			parts.icon.BackgroundColor3 = rarityColor(item.creature.rarity)
			parts.name.Text = coloredName(item.creature)
			parts.button.Activated:Connect(function()
				local current = targetsById[parts.userId]
				local entry = entriesById[parts.userId .. "/" .. parts.employeeId]
				if current and entry and select(3, poachButtonState(current, entry)) then
					onPoachClicked(parts.userId, parts.employeeId)
				end
			end)
			table.insert(targetWidgets, parts.card)
			table.insert(employeeCards, parts)
		end
	end
	applyLayout()
end

table.insert(refreshers, function()
	local bits = {}
	if snapshot.negotiating then
		table.insert(bits, "🤝 Negotiating...")
	elseif cooldownLeft() > 0 then
		table.insert(bits, "Next poach in " .. formatTime(cooldownLeft()))
	else
		table.insert(bits, "Ready to poach")
	end
	if not snapshot.freeSlot then
		table.insert(bits, '<font color="#FF6B6B">Team full: make room first</font>')
	end
	if poachBonus() > 0 then
		table.insert(bits, "🎯 Headhunter +" .. percent(poachBonus()))
	end
	poachStatus.Text = table.concat(bits, " · ")
	nobodyLine.Visible = #snapshot.targets == 0

	for _, line in ipairs(headerLines) do
		local target = targetsById[line.userId]
		if target then
			line.label.Text = targetHeader(target)
		end
	end
	for _, parts in ipairs(employeeCards) do
		local target = targetsById[parts.userId]
		local entry = entriesById[parts.userId .. "/" .. parts.employeeId]
		local creature = entry and CreatureConfig.getCreature(entry.creature)
		if target and creature then
			local chanceText = entry.chance
				and string.format("Chance <b>%s</b> · costs %s", percent(entry.chance), formatCash(entry.cost))
				or "Legendary employees can't be poached"
			parts.desc.Text = employeeLine(creature) .. "\n" .. chanceText
			setButton(parts.button, poachButtonState(target, entry))
		end
	end
end)

-- Defense tab -----------------------------------------------------------

local defensePage = tabPages.Defense
local defenseStatus = makeLine(defensePage, 0)
local counterCard = makeCard(defensePage, 1)
local hrCard = makeCard(defensePage, 2)
local shieldCard = makeCard(defensePage, 3)

local rules = make("TextLabel", {
	LayoutOrder = 10,
	Size = UDim2.new(1, 0, 0, 100),
	BackgroundTransparency = 1,
	Font = Enum.Font.Gotham,
	Text = string.format(
		"How poaching works: pay Cash to negotiate for another player's employee (%d-%d seconds). "
			.. "If they say no, the Cash is gone. Legendary employees can never be poached. "
			.. "After losing an employee you're protected for %d min and can buy them back once, within %d min. "
			.. "New players are protected for their first %d min, and offline players are always safe.",
		RULES.NegotiationSeconds[1], RULES.NegotiationSeconds[2], RULES.ShieldAfterPoach // 60,
		RULES.CounterOfferSeconds // 60, RULES.NewPlayerShield // 60),
	TextColor3 = COLORS.subtext,
	TextWrapped = true,
	TextXAlignment = Enum.TextXAlignment.Left,
	TextYAlignment = Enum.TextYAlignment.Top,
	Parent = defensePage,
})
fitText(rules, 15)

counterCard.button.Activated:Connect(function()
	if not counterOffer then return end
	local success, message = request("CounterOffer")
	if message then
		showToast(message)
	end
	if success then
		counterOffer = nil
	end
	refreshAll()
end)

hrCard.button.Activated:Connect(function()
	local _, message = request("BuyHr") -- only the action: the server knows the level and the price
	if message then
		showToast(message)
	end
	refreshAll()
end)

local shield = shieldProduct()
shieldCard.button.Activated:Connect(function()
	if shield and ShopConfig.isForSale(shield) then
		MarketplaceService:PromptProductPurchase(player, shield.id)
	end
end)
hrCard.icon.Text = "🏢"
hrCard.icon.BackgroundColor3 = COLORS.hr
shieldCard.icon.Text = shield and shield.icon or "🛡️"
shieldCard.card.Visible = shield ~= nil

table.insert(refreshers, function()
	local left = shieldLeft()
	defenseStatus.Text = left > 0 and ("🛡 Protected for " .. formatTime(left) .. ": nobody can poach you")
		or '<font color="#FF6B6B">Not protected:</font> players in this server can poach your employees'

	-- Counter-Offer: buy back the employee that was just poached
	local offerLeft = counterOffer and counterOffer.expiresAt - now() or 0
	local creature = counterOffer and CreatureConfig.getCreature(counterOffer.creature)
	counterCard.card.Visible = creature ~= nil and offerLeft > 0
	if counterCard.card.Visible then
		counterCard.icon.Text = creature.emoji
		counterCard.icon.BackgroundColor3 = rarityColor(creature.rarity)
		counterCard.name.Text = "Counter-Offer: " .. coloredName(creature)
		counterCard.desc.Text = "Buy them back from " .. escape(counterOffer.attacker) .. " for " .. formatCash(counterOffer.price)
			.. ".\n" .. formatTime(offerLeft) .. " left, only once."
		setButton(counterCard.button, "Buy back\n" .. formatCash(counterOffer.price), cash() >= counterOffer.price and COLORS.gold or COLORS.disabled, true)
	end

	-- HR Department: bought here with Cash (the server checks the level and the Cash)
	local level = player:GetAttribute("HRLevel") or 0
	local maxLevel = #RULES.HRDepartment
	local nextLevel = RULES.HRDepartment[level + 1]
	hrCard.name.Text = "HR Department Lv " .. level .. "/" .. maxLevel
	hrCard.desc.Text = (level > 0 and ("Poachers get -" .. percent(CreatureConfig.hrDefense(level)) .. " chance.") or "No defense yet.")
		.. (nextLevel and string.format("\nNext: Lv %d for %s (-%s).", level + 1, formatCash(nextLevel.cost), percent(nextLevel.defense))
			or "\nFully upgraded!")
	if not nextLevel then
		setButton(hrCard.button, "MAX", COLORS.hr, false)
	elseif cash() >= nextLevel.cost then
		setButton(hrCard.button, "Buy\n" .. formatCash(nextLevel.cost), COLORS.hr, true)
	else
		setButton(hrCard.button, formatCash(nextLevel.cost), COLORS.disabled, false)
	end

	-- Poach Shield (developer product)
	if shield then
		shieldCard.name.Text = shield.name
		shieldCard.desc.Text = shield.description .. (left > 0 and ("\nProtected: " .. formatTime(left) .. " left") or "")
		if ShopConfig.isForSale(shield) then
			setButton(shieldCard.button, "R$ " .. shield.price, COLORS.buy, true)
		else
			setButton(shieldCard.button, "Coming soon", COLORS.disabled, false)
		end
	end
end)

-- Window: tabs, opening and closing -------------------------------------

function refreshAll()
	badge.Visible = counterOffer ~= nil and counterOffer.expiresAt > now()
	if window.Visible then
		for _, refresh in ipairs(refreshers) do
			refresh()
		end
	end
end

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

-- Only one window at a time (the shop and the Recruiting window do the same with "OpenPanel")
function setOpen(open, tab)
	window.Visible = open
	if open then
		playerGui:SetAttribute("OpenPanel", PANEL_NAME)
		showTab(tab or "Poach")
		task.spawn(poll)
	elseif playerGui:GetAttribute("OpenPanel") == PANEL_NAME then
		playerGui:SetAttribute("OpenPanel", nil)
	end
	GuiService.TouchControlsEnabled = playerGui:GetAttribute("OpenPanel") == nil
	refreshAll()
end

playerGui:GetAttributeChangedSignal("OpenPanel"):Connect(function()
	if window.Visible and playerGui:GetAttribute("OpenPanel") ~= PANEL_NAME then
		window.Visible = false
	end
end)

poachButton.Activated:Connect(function()
	local tab = badge.Visible and "Defense" or "Poach" -- a waiting Counter-Offer opens the Defense tab
	setOpen(not (window.Visible and tabPages[tab].Visible), tab)
end)
closeButton.Activated:Connect(function()
	setOpen(false)
end)

-- Negotiation mini-screen and the "someone is poaching you" warning (top middle) --------

local function topPanel(name, color, withButton)
	local frame = make("Frame", {
		Name = name,
		AnchorPoint = Vector2.new(0.5, 0),
		Size = UDim2.new(0.7, 0, 0, 92),
		BackgroundColor3 = COLORS.panel,
		BackgroundTransparency = 0.05,
		Visible = false,
		ZIndex = 5,
		Parent = front,
	})
	round(frame, 14)
	make("UISizeConstraint", { MaxSize = Vector2.new(460, 92), Parent = frame })
	make("UIStroke", { Thickness = 3, Color = color, Parent = frame })
	local right = withButton and -124 or -24
	local heading = make("TextLabel", {
		Position = UDim2.new(0, 12, 0, 8),
		Size = UDim2.new(1, right, 0, 26),
		BackgroundTransparency = 1,
		Font = Enum.Font.GothamBold,
		Text = "",
		RichText = true,
		TextColor3 = COLORS.text,
		TextXAlignment = Enum.TextXAlignment.Left,
		ZIndex = 5,
		Parent = frame,
	})
	fitText(heading, 19)
	local line = make("TextLabel", {
		Position = UDim2.new(0, 12, 0, 36),
		Size = UDim2.new(1, right, 0, 20),
		BackgroundTransparency = 1,
		Font = Enum.Font.Gotham,
		Text = "",
		TextColor3 = COLORS.subtext,
		TextXAlignment = Enum.TextXAlignment.Left,
		ZIndex = 5,
		Parent = frame,
	})
	fitText(line, 16)
	local bar = make("Frame", {
		Position = UDim2.new(0, 12, 1, -24),
		Size = UDim2.new(1, right, 0, 12),
		BackgroundColor3 = COLORS.tab,
		ZIndex = 5,
		Parent = frame,
	})
	round(bar, 6)
	local fill = make("Frame", { Size = UDim2.fromScale(0, 1), BackgroundColor3 = color, ZIndex = 5, Parent = bar })
	round(fill, 6)
	local button
	if withButton then
		button = make("TextButton", {
			AnchorPoint = Vector2.new(1, 0.5),
			Position = UDim2.new(1, -10, 0.5, 0),
			Size = UDim2.fromOffset(100, 56),
			BackgroundColor3 = COLORS.buy,
			Font = Enum.Font.GothamBold,
			Text = "",
			TextColor3 = COLORS.text,
			ZIndex = 5,
			Parent = frame,
		})
		round(button, 10)
		fitText(button, 18)
	end
	return { frame = frame, heading = heading, line = line, fill = fill, button = button, token = 0 }
end

local negotiationPanel = topPanel("Negotiation", COLORS.gold, false)
local alertPanel = topPanel("PoachAlert", COLORS.danger, true)

-- Below the HUD row on short phone screens; the warning goes under the negotiation if both show
local function placeTopPanels()
	local top = gui.AbsoluteSize.Y < 460 and 76 or 12
	negotiationPanel.frame.Position = UDim2.new(0.5, 0, 0, top)
	alertPanel.frame.Position = UDim2.new(0.5, 0, 0, top + (negotiationPanel.frame.Visible and 100 or 0))
end
placeTopPanels()
gui:GetPropertyChangedSignal("AbsoluteSize"):Connect(function()
	placeHudButton()
	placeTopPanels()
end)

local function runBar(panel, seconds)
	panel.fill.Size = UDim2.fromScale(0, 1)
	TweenService:Create(panel.fill, TweenInfo.new(seconds, Enum.EasingStyle.Linear), { Size = UDim2.fromScale(1, 1) }):Play()
end

local function hidePanel(panel)
	panel.token += 1
	panel.frame.Visible = false
	placeTopPanels()
end

local function showNegotiation(info)
	local creature = CreatureConfig.getCreature(info.creature)
	if not creature then return end
	local panel = negotiationPanel
	panel.token += 1
	local token = panel.token
	panel.heading.Text = "🤝 Negotiating for " .. escape(info.target) .. "'s " .. coloredName(creature)
	panel.frame.Visible = true
	placeTopPanels()
	runBar(panel, info.seconds)
	task.spawn(function()
		local i = math.random(#NEGOTIATION_LINES)
		while panel.token == token do
			panel.line.Text = NEGOTIATION_LINES[i] .. "  (" .. percent(info.chance) .. " chance)"
			i = i % #NEGOTIATION_LINES + 1
			task.wait(1.6)
		end
	end)
	task.delay(info.seconds + 5, function() -- in case the result never arrives
		if panel.token == token then
			hidePanel(panel)
		end
	end)
end

local function showAlert(info)
	local creature = CreatureConfig.getCreature(info.creature)
	if not creature then return end
	local panel = alertPanel
	panel.token += 1
	local token = panel.token
	panel.heading.Text = "⚠ " .. escape(info.attacker) .. " is poaching your " .. coloredName(creature) .. "!"
	local canShield = shield ~= nil and ShopConfig.isForSale(shield)
	panel.line.Text = canShield and "A Poach Shield stops them right now." or "Negotiating... fingers crossed!"
	panel.button.Visible = canShield
	if canShield then
		setButton(panel.button, "🛡 Shield\nR$ " .. shield.price, COLORS.buy, true)
	end
	panel.frame.Visible = true
	placeTopPanels()
	runBar(panel, info.seconds)
	task.delay(info.seconds + 5, function()
		if panel.token == token then
			hidePanel(panel)
		end
	end)
end

alertPanel.button.Activated:Connect(function()
	if shield and ShopConfig.isForSale(shield) then
		MarketplaceService:PromptProductPurchase(player, shield.id)
	end
end)

-- Result cards (the poacher's result, and "you got poached!") ----------------------

local resultGui = make("ScreenGui", {
	Name = "PoachResultGui",
	ResetOnSpawn = false,
	IgnoreGuiInset = true,
	DisplayOrder = 51, -- just above the hatch reveal
	Enabled = false,
	Parent = playerGui,
})
local overlay = make("TextButton", {
	Name = "Overlay",
	Size = UDim2.fromScale(1, 1),
	BackgroundColor3 = Color3.new(0, 0, 0),
	BackgroundTransparency = 0.35,
	Text = "",
	AutoButtonColor = false,
	Parent = resultGui,
})
local resultCard = make("Frame", {
	Name = "Card",
	AnchorPoint = Vector2.new(0.5, 0.5),
	Position = UDim2.fromScale(0.5, 0.5),
	Size = UDim2.fromScale(0.9, 0.9),
	BackgroundColor3 = COLORS.panel,
	Parent = overlay,
})
round(resultCard, 18)
make("UISizeConstraint", { MaxSize = Vector2.new(320, 420), Parent = resultCard })
local resultStroke = make("UIStroke", { Thickness = 5, Parent = resultCard })
local viewport = make("ViewportFrame", {
	Position = UDim2.fromScale(0.05, 0.03),
	Size = UDim2.fromScale(0.9, 0.42),
	BackgroundTransparency = 1,
	Ambient = Color3.fromRGB(190, 190, 200),
	LightColor = Color3.new(1, 1, 1),
	LightDirection = Vector3.new(-1, -1, 1),
	Parent = resultCard,
})

local function resultLabel(y, height, font, maxSize)
	local label = make("TextLabel", {
		Position = UDim2.fromScale(0.05, y),
		Size = UDim2.fromScale(0.9, height),
		BackgroundTransparency = 1,
		Font = font,
		Text = "",
		RichText = true,
		TextColor3 = COLORS.text,
		TextWrapped = true,
		Parent = resultCard,
	})
	fitText(label, maxSize)
	return label
end
local headlineLabel = resultLabel(0.46, 0.07, Enum.Font.GothamBold, 22)
local nameLabel = resultLabel(0.53, 0.09, Enum.Font.GothamBold, 28)
local roleLabel = resultLabel(0.62, 0.06, Enum.Font.Gotham, 17)
local statusLabel = resultLabel(0.69, 0.14, Enum.Font.Gotham, 16)

local function resultButton(name)
	local button = make("TextButton", {
		Name = name,
		Position = UDim2.fromScale(0.05, 0.85),
		Size = UDim2.fromScale(0.9, 0.11),
		BackgroundColor3 = COLORS.buy,
		Font = Enum.Font.GothamBold,
		Text = "",
		TextColor3 = COLORS.text,
		Parent = resultCard,
	})
	round(button, 10)
	fitText(button, 20)
	return button
end
local primaryButton = resultButton("PrimaryButton")
local secondaryButton = resultButton("SecondaryButton")

local cardQueue = {}
local showingCard = false
local cardDone -- set while a card is showing: call it to close the card
local primaryAction -- what the big button does for the current card (returns true to close)

-- opts: { creature, headline, headlineColor, stroke, status, primary = { text, color, action }, secondary = text }
local function playCard(opts)
	local creature = CreatureConfig.getCreature(opts.creature)
	if not creature then return end
	resultGui.Enabled = true
	GuiService.TouchControlsEnabled = false

	viewport:ClearAllChildren()
	local camera = make("Camera", { Parent = viewport })
	viewport.CurrentCamera = camera
	local model = CreatureModels.build(creature)
	model.Parent = viewport
	local size = model:GetExtentsSize()
	-- Far enough back that the whole creature fits (same framing as the hatch reveal)
	local distance = math.max(size.Y * 1.45, size.X * 1.1, size.Z * 0.9) + 1
	camera.FieldOfView = 50
	camera.CFrame = CFrame.lookAt(Vector3.new(0, size.Y * 0.55, -distance), Vector3.new(0, size.Y * 0.5, 0))

	resultStroke.Color = opts.stroke
	headlineLabel.Text = opts.headline
	headlineLabel.TextColor3 = opts.headlineColor
	nameLabel.Text = creature.name
	nameLabel.TextColor3 = rarityColor(creature.rarity)
	roleLabel.Text = creature.rarity .. " · " .. creature.role .. " · $" .. creature.income .. "/s"
	statusLabel.Text = opts.status
	setButton(primaryButton, opts.primary.text, opts.primary.color, true)
	primaryAction = opts.primary.action
	if opts.secondary then
		primaryButton.Size = UDim2.fromScale(0.56, 0.11)
		secondaryButton.Visible = true
		secondaryButton.Position = UDim2.fromScale(0.64, 0.85)
		secondaryButton.Size = UDim2.fromScale(0.31, 0.11)
		setButton(secondaryButton, opts.secondary, COLORS.disabled, true)
	else
		primaryButton.Size = UDim2.fromScale(0.9, 0.11)
		secondaryButton.Visible = false
	end
	resultCard.Size = UDim2.fromScale(0.5, 0.5)
	TweenService:Create(resultCard, TweenInfo.new(0.25, Enum.EasingStyle.Back), { Size = UDim2.fromScale(0.9, 0.9) }):Play()

	local spin = RunService.RenderStepped:Connect(function()
		model:PivotTo(CFrame.new(0, 0.5, 0) * CFrame.Angles(0, os.clock() * 1.2, 0)) -- pivot sits 0.5 above the feet
	end)
	local done = false
	cardDone = function()
		done = true
	end
	while not done do
		task.wait(0.05)
	end
	cardDone = nil
	primaryAction = nil
	spin:Disconnect()
	resultGui.Enabled = false
	GuiService.TouchControlsEnabled = playerGui:GetAttribute("OpenPanel") == nil
end

local function queueCard(opts)
	table.insert(cardQueue, opts)
	if showingCard then return end
	showingCard = true
	while #cardQueue > 0 do
		playCard(table.remove(cardQueue, 1))
	end
	showingCard = false
end

primaryButton.Activated:Connect(function()
	if not cardDone then return end
	if not primaryAction or primaryAction() then
		cardDone()
	end
end)
secondaryButton.Activated:Connect(function()
	if cardDone then
		cardDone()
	end
end)

-- Messages from the server ------------------------------------------------

local function onEvent(kind, info)
	if kind == "Negotiating" then
		showNegotiation(info)

	elseif kind == "Result" then
		hidePanel(negotiationPanel)
		local creature = CreatureConfig.getCreature(info.creature)
		if not creature then return end
		if info.success then
			task.spawn(queueCard, {
				creature = info.creature,
				headline = "HIRED! ✨",
				headlineColor = COLORS.buy,
				stroke = rarityColor(creature.rarity),
				status = "Poached from " .. escape(info.target) .. " for " .. formatCash(info.cost) .. ".\nNow working for you: +$" .. creature.income .. "/s",
				primary = { text = "Nice!", color = COLORS.buy },
			})
		else
			task.spawn(queueCard, {
				creature = info.creature,
				headline = "DEAL FELL THROUGH",
				headlineColor = COLORS.danger,
				stroke = COLORS.danger,
				status = creature.name .. " turned down your offer and stayed with " .. escape(info.target) .. ".\nThe " .. formatCash(info.cost) .. " is gone.",
				primary = { text = "OK", color = COLORS.disabled },
			})
		end

	elseif kind == "Cancelled" then
		hidePanel(negotiationPanel)
		showToast(info.reason .. " You got your " .. formatCash(info.refund) .. " back.")

	elseif kind == "UnderAttack" then
		showAlert(info)

	elseif kind == "AttackOver" then
		hidePanel(alertPanel)
		local creature = CreatureConfig.getCreature(info.creature)
		local name = creature and creature.name or "Your employee"
		if info.result == "defended" then
			showToast("💪 " .. name .. " turned down " .. info.attacker .. "'s offer!")
		else
			showToast(info.attacker .. " stopped trying to poach " .. name)
		end

	elseif kind == "Poached" then
		hidePanel(alertPanel)
		local creature = CreatureConfig.getCreature(info.creature)
		if not creature then return end
		if info.price then
			counterOffer = { creature = info.creature, attacker = info.attacker, price = info.price, expiresAt = info.expiresAt }
		end
		local status = escape(info.attacker) .. " poached your " .. creature.role .. ", " .. creature.name .. "!"
			.. "\nNobody can poach you for " .. formatTime(info.shieldUntil - now()) .. "."
		local primary = { text = "OK", color = COLORS.disabled }
		local secondary
		if info.price then
			status ..= " Buy them back?"
			secondary = "Not now"
			primary = {
				text = "Counter-Offer " .. formatCash(info.price),
				color = COLORS.gold,
				action = function()
					local success, message = request("CounterOffer")
					if success then
						counterOffer = nil
						showToast(message)
						return true
					end
					statusLabel.Text = message or "Couldn't make the Counter-Offer"
					return false
				end,
			}
		end
		task.spawn(queueCard, {
			creature = info.creature,
			headline = "POACHED!",
			headlineColor = COLORS.danger,
			stroke = COLORS.danger,
			status = status,
			primary = primary,
			secondary = secondary,
		})

	elseif kind == "Counter" then
		counterOffer = info or nil

	elseif kind == "Notice" then
		showToast(info.text)
	end
	refreshAll()
	if window.Visible then
		task.spawn(poll)
	end
end

poachEvent.OnClientEvent:Connect(function(kind, info)
	-- Result cards wait for each other, so handle each message in its own thread
	task.spawn(onEvent, kind, info)
end)

player.AttributeChanged:Connect(refreshAll)

showTab("Poach")
applyLayout()
window:GetPropertyChangedSignal("AbsoluteSize"):Connect(applyLayout)

-- The target list updates about once a second while the window is open
task.spawn(function()
	while true do
		if window.Visible then
			poll()
		end
		task.wait(1)
	end
end)

-- Timers tick while the window is open
while true do
	task.wait(0.5)
	refreshAll()
end
