-- EmployeeClient: the Eggs and Team panels, the hatch reveal and employees walking around (milestone 2).
-- Put this LocalScript in StarterPlayer > StarterPlayerScripts. It builds the screens by itself.
-- It only shows what the server says and asks EmployeeServer to do things (buy, hatch, fire).

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local GuiService = game:GetService("GuiService")
local TweenService = game:GetService("TweenService")
local CollectionService = game:GetService("CollectionService")

local CreatureConfig = require(ReplicatedStorage:WaitForChild("CreatureConfig"))
local CreatureModels = require(ReplicatedStorage:WaitForChild("CreatureModels"))
local ShopConfig = require(ReplicatedStorage:WaitForChild("ShopConfig"))
local IpoConfig = require(ReplicatedStorage:WaitForChild("IpoConfig")) -- IPO perks change eggs and slots
local remotes = ReplicatedStorage:WaitForChild("EmployeeRemotes")
local teamAction = remotes:WaitForChild("TeamAction")
local teamUpdate = remotes:WaitForChild("TeamUpdate")
local eggHatched = remotes:WaitForChild("EggHatched")

local player = Players.LocalPlayer
local playerGui = player:WaitForChild("PlayerGui")
local PANEL_NAME = "Recruiting"

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
	hud = Color3.fromRGB(70, 120, 255),
}

-- The latest team state from the server (nextHires: egg key -> creature key, only for players whose
-- hires follow a fixed order; false for everyone else)
local state = { employees = {}, incubators = {}, pending = false, maxEmployees = CreatureConfig.BaseEmployeeSlots, nextHires = false }
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

local function rarityColor(rarityKey)
	local rarity = CreatureConfig.getRarity(rarityKey)
	return rarity and rarity.color or COLORS.text
end

local function formatCash(amount)
	return ShopConfig.formatCash(amount)
end

-- Things other scripts put on the player: pass ownership, boosts, Cash
local function hasPassEffect(field)
	for _, pass in ipairs(ShopConfig.Passes) do
		if pass.effect[field] and player:GetAttribute("Pass_" .. pass.key) then
			return true
		end
	end
	return false
end

local function cashMultiplier()
	local multiplier = 1
	for _, pass in ipairs(ShopConfig.Passes) do
		if player:GetAttribute("Pass_" .. pass.key) then
			multiplier *= pass.effect.cashMultiplier or 1
		end
	end
	return multiplier * (player:GetAttribute("IpoMultiplier") or 1) -- the IPO multiplier stacks on top
end

-- What one of your IPO perks adds right now (IpoServer puts the levels on the player)
local function perkValue(key)
	return IpoConfig.perkValue(key, player:GetAttribute("IpoPerk_" .. key) or 0)
end

local function luckLeft()
	return (player:GetAttribute("LuckBoostUntil") or 0) - workspace:GetServerTimeNow()
end

local function luckMultiplier()
	local perk = 1 + perkValue("BaseLuck") -- Talent Scouts IPO perk, always on
	if luckLeft() <= 0 then return perk end
	for _, product in ipairs(ShopConfig.Products) do
		if product.effect.luckMultiplier then
			return product.effect.luckMultiplier * perk
		end
	end
	return perk
end

local function cash()
	local stats = player:FindFirstChild("leaderstats")
	return stats and stats:FindFirstChild("Cash") and stats.Cash.Value or 0
end

local function teamIsFull()
	return #state.employees >= state.maxEmployees
end

-- Screen ----------------------------------------------------------------

local gui = make("ScreenGui", {
	Name = "RecruitingGui",
	ResetOnSpawn = false,
	ZIndexBehavior = Enum.ZIndexBehavior.Sibling,
	Parent = playerGui,
})

-- HUD buttons share one layout with the SHOP button (ShopClient):
-- EGGS = slot 0, SHOP = 1, TEAM = 2, POACH = 3, IPO = 4.
-- A column centered on the left, or a row at the top-left on short phone screens, where the
-- column would sit under the joystick.
local function hudButton(name, text, slot)
	local button = make("TextButton", {
		Name = name,
		BackgroundColor3 = COLORS.hud,
		Font = Enum.Font.GothamBold,
		Text = text,
		TextColor3 = COLORS.text,
		Parent = gui,
	})
	round(button, 18)
	fitText(button, 22)
	make("UIStroke", { Thickness = 3, Transparency = 0.5, ApplyStrokeMode = Enum.ApplyStrokeMode.Border, Parent = button })
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
	return button
end
local eggsButton = hudButton("EggsButton", "🥚\nEGGS", 0)
local teamButton = hudButton("TeamButton", "👥\n0/5", 2)

local toast = make("TextLabel", {
	Name = "Toast",
	AnchorPoint = Vector2.new(0.5, 1),
	Position = UDim2.new(0.5, 0, 1, -72), -- bottom middle, just above the shop's messages
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
	Text = "Recruiting",
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

local tabNames = { "Eggs", "Team" }
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

-- One row: round icon, name, description, and a button on the right
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
		BackgroundColor3 = COLORS.buy,
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
local function request(action, arg)
	if busy then return end
	busy = true
	local ok, success, message = pcall(function()
		return teamAction:InvokeServer(action, arg)
	end)
	busy = false
	if not ok then
		showToast("Something went wrong. Please try again.")
	elseif message and not (success and (action == "Hatch" or action == "InstantHatch")) then
		showToast(message) -- hatching shows the reveal instead
	end
end

-- Eggs tab --------------------------------------------------------------

local eggsPage = tabPages.Eggs
local eggsStatus = makeLine(eggsPage, 0)

-- Odds come from CreatureConfig.getCreatureOdds, built from the same weights and luck the server
-- rolls with. They're rounded so the shown numbers always add up to exactly 100.00%, and they're
-- redrawn while the window is open, so Luck Boost and Talent Scouts show up live (Roblox's Paid
-- Random Items policy: every possible hire's own odds, before buying).

-- The card's short line: the odds per rarity (sums of the per-hire odds below)
local function oddsText(creatureOdds)
	local parts = {}
	for _, entry in ipairs(CreatureConfig.rarityOdds(creatureOdds)) do
		table.insert(parts, string.format('<font color="%s">%s</font> %s', hex(rarityColor(entry.rarity)), entry.rarity, CreatureConfig.formatOdds(entry.units)))
	end
	return (luckLeft() > 0 and "🍀 " or "") .. table.concat(parts, " · ")
end

-- The full list under each egg: every possible hire and its own odds
local function creatureOddsText(egg, creatureOdds)
	local parts = {}
	for _, entry in ipairs(creatureOdds) do
		table.insert(parts, string.format('<font color="%s">%s</font> %s', hex(rarityColor(entry.rarity)), entry.creature.name, CreatureConfig.formatOdds(entry.units)))
	end
	return string.format("<b>%s odds for each hire</b>%s (rounded, total exactly 100.00%%): %s", egg.name,
		luckLeft() > 0 and " with 🍀 Luck Boost" or "", table.concat(parts, " · "))
end

-- Players for whom paid random items are restricted (Roblox's PolicyService, asked by the server on
-- join; not known yet counts as restricted) get no random roll: each egg hires in a fixed order, and
-- the server sends the next hire of every egg. They see that hire instead of odds (FR-13, D9 option B).
local function randomRestricted()
	return player:GetAttribute("RandomRestricted") ~= false
end

local function nextHireName(creature)
	if not creature then
		return "loading..."
	end
	return string.format('<font color="%s">%s %s</font>', hex(rarityColor(creature.rarity)), creature.emoji or "", creature.name)
end

-- What a creature earns per second in the player's building now (overhaul 2: the building's team multiplier, the
-- server's TeamMultiplier attribute; passes and IPOs come on top), as "$2" or "$0.3"
local function earns(creature)
	local value = creature.income * (player:GetAttribute("TeamMultiplier") or 1)
	if value >= 1000 then
		return IpoConfig.formatShort(value)
	end
	return "$" .. (value < 10 and (string.format("%.1f", value):gsub("%.0$", "")) or tostring(math.floor(value)))
end

-- The full line under the egg card (full width, so it stays readable on a phone)
local function nextHireText(egg, creature)
	local text = "<b>Next hire from this egg: " .. nextHireName(creature) .. "</b>"
	if creature then
		text ..= string.format(" (%s · %s · %s/s)", creature.rarity, creature.role, earns(creature))
	end
	return text .. ". Your hires follow a fixed order, not a random roll: the next " .. egg.name .. " that hatches brings this hire."
end

for i, egg in ipairs(CreatureConfig.Eggs) do
	local parts = makeCard(eggsPage, i * 2 - 1)
	local oddsLabel = make("TextLabel", {
		LayoutOrder = i * 2,
		Size = UDim2.new(1, 0, 0, 0),
		AutomaticSize = Enum.AutomaticSize.Y, -- grows to fit the whole list, on any screen width
		BackgroundTransparency = 1,
		Font = Enum.Font.Gotham,
		Text = "",
		RichText = true,
		TextSize = 13,
		TextColor3 = COLORS.subtext,
		TextWrapped = true,
		TextXAlignment = Enum.TextXAlignment.Left,
		Parent = eggsPage,
	})
	parts.icon.Text = "🥚"
	parts.icon.BackgroundColor3 = egg.color
	parts.name.Text = egg.name
	parts.button.Activated:Connect(function()
		request("BuyEgg", egg.key)
	end)
	table.insert(refreshers, function()
		local seconds = math.ceil(egg.hatchSeconds * math.max(0, 1 - perkValue("FasterEggs")))
		if randomRestricted() then
			local nextKey = state.nextHires and state.nextHires[egg.key]
			local creature = nextKey and CreatureConfig.getCreature(nextKey)
			parts.desc.Text = "Hatches in " .. CreatureConfig.formatTime(seconds) .. "\nNext hire: " .. nextHireName(creature)
			oddsLabel.Text = nextHireText(egg, creature)
		else
			local creatureOdds = CreatureConfig.getCreatureOdds(egg, luckMultiplier())
			parts.desc.Text = "Hatches in " .. CreatureConfig.formatTime(seconds) .. "\n" .. oddsText(creatureOdds)
			oddsLabel.Text = creatureOddsText(egg, creatureOdds)
		end
		local freeIncubator = false
		for index = 1, #state.incubators do
			if not state.incubators[index] then
				freeIncubator = true
			end
		end
		if not freeIncubator then
			setButton(parts.button, "Incubators full", COLORS.disabled, false)
		else
			local price = formatCash(egg.price)
			setButton(parts.button, price, cash() >= egg.price and COLORS.buy or COLORS.disabled, true)
		end
	end)
end

makeLine(eggsPage, 100, COLORS.gold).Text = "Incubators" -- after the eggs and their odds (orders 1 to 2 x eggs)

-- Cards for the most incubators anyone can have (Extra Incubator IPO perk); unused ones hide
local extraIncubatorPerk = IpoConfig.getPerk("ExtraIncubator")
local maxIncubators = CreatureConfig.Incubators + (extraIncubatorPerk and IpoConfig.perkValue("ExtraIncubator", #extraIncubatorPerk.costs) or 0)
for index = 1, maxIncubators do
	local parts = makeCard(eggsPage, 100 + index)
	parts.button.Activated:Connect(function()
		local slot = state.incubators[index]
		if not slot or state.pending then return end
		if slot.hatchAt <= workspace:GetServerTimeNow() then
			request("Hatch", index)
		elseif (player:GetAttribute("InstantHatches") or 0) > 0 then
			request("InstantHatch", index)
		end
	end)
	table.insert(refreshers, function()
		parts.card.Visible = index <= #state.incubators
		local slot = state.incubators[index]
		local egg = slot and CreatureConfig.getEgg(slot.egg)
		if not egg then
			parts.icon.Text = ""
			parts.icon.BackgroundColor3 = COLORS.tab
			parts.name.Text = "Incubator " .. index
			parts.desc.Text = "Empty. Buy an egg above."
			setButton(parts.button, "Empty", COLORS.disabled, false)
			return
		end
		parts.icon.Text = "🥚"
		parts.icon.BackgroundColor3 = egg.color
		parts.name.Text = egg.name
		local left = slot.hatchAt - workspace:GetServerTimeNow()
		local tokens = player:GetAttribute("InstantHatches") or 0
		if state.pending then
			parts.desc.Text = left > 0 and ("Hatching in " .. CreatureConfig.formatTime(left)) or "Ready!"
			parts.desc.Text ..= "\nFirst decide about your waiting new hire (Team tab)."
			setButton(parts.button, "Waiting", COLORS.disabled, false)
		elseif left <= 0 then
			parts.desc.Text = "Ready to hatch!"
			if teamIsFull() then
				parts.desc.Text ..= "\nTeam full: you'll choose who to replace."
			elseif hasPassEffect("autoHatch") then
				parts.desc.Text ..= "\nAuto-Hatch is opening it..."
			end
			setButton(parts.button, "Hatch!", COLORS.gold, true)
		else
			parts.desc.Text = "Hatching in " .. CreatureConfig.formatTime(left)
			if hasPassEffect("autoHatch") then
				parts.desc.Text ..= "\nAuto-Hatch will open it for you."
			end
			if tokens > 0 then
				setButton(parts.button, "⚡ Skip (" .. tokens .. ")", COLORS.gold, true)
			else
				setButton(parts.button, CreatureConfig.formatTime(left), COLORS.disabled, false)
			end
		end
	end)
end

table.insert(refreshers, function()
	local used = 0
	for index = 1, #state.incubators do
		if state.incubators[index] then
			used += 1
		end
	end
	local bits = { "Team " .. #state.employees .. "/" .. state.maxEmployees, "Incubators " .. used .. "/" .. #state.incubators }
	if luckLeft() > 0 then
		table.insert(bits, "🍀 Luck " .. CreatureConfig.formatTime(luckLeft()))
	end
	if hasPassEffect("autoHatch") then
		table.insert(bits, "Auto-Hatch ON")
	end
	if state.pending then
		table.insert(bits, '<font color="#FFC83C">New hire waiting!</font>')
	end
	eggsStatus.Text = table.concat(bits, " · ")
end)

-- Team tab --------------------------------------------------------------

local teamPage = tabPages.Team
local teamStatus = makeLine(teamPage, 0)
local pendingCard = makeCard(teamPage, 1)
local emptyLine = makeLine(teamPage, 1000)
emptyLine.Text = "No employees yet. Buy a recruiting egg in the Eggs tab!"
local employeeCards = {} -- rebuilt whenever the team changes
local fireConfirm = {} -- employee ID -> time the Fire button was first tapped

pendingCard.button.Activated:Connect(function()
	if not state.pending then return end
	request("ResolvePending", teamIsFull() and "letgo" or "hire")
end)

local function employeeLine(creature)
	return string.format('<font color="%s">%s</font> · %s · %s/s', hex(rarityColor(creature.rarity)), creature.rarity, creature.role, earns(creature))
end

local function rebuildTeamCards()
	for _, parts in ipairs(employeeCards) do
		parts.card:Destroy()
	end
	table.clear(employeeCards)
	for i = #cardParts, 1, -1 do
		if not cardParts[i].card.Parent then
			table.remove(cardParts, i)
		end
	end

	local list = {}
	for _, employee in ipairs(state.employees) do
		local creature = CreatureConfig.getCreature(employee.creature)
		if creature then
			table.insert(list, { id = employee.id, creature = creature })
		end
	end
	table.sort(list, function(a, b)
		if a.creature.income ~= b.creature.income then
			return a.creature.income > b.creature.income
		end
		return a.creature.name < b.creature.name
	end)

	for i, entry in ipairs(list) do
		local creature = entry.creature
		local parts = makeCard(teamPage, 10 + i)
		parts.icon.Text = creature.emoji
		parts.icon.BackgroundColor3 = rarityColor(creature.rarity)
		parts.name.Text = string.format('<font color="%s">%s</font>', hex(rarityColor(creature.rarity)), creature.name)
		parts.desc.Text = employeeLine(creature)
		parts.id = entry.id
		parts.button.Activated:Connect(function()
			if state.pending then
				request("ResolvePending", entry.id) -- replace this employee with the new hire
			elseif fireConfirm[entry.id] and os.clock() - fireConfirm[entry.id] < 4 then
				fireConfirm[entry.id] = nil
				request("Fire", entry.id)
			else
				fireConfirm[entry.id] = os.clock() -- tap again to confirm
				setButton(parts.button, "Sure?", COLORS.danger, true)
			end
		end)
		table.insert(employeeCards, parts)
	end
	applyLayout()
end

table.insert(refreshers, function()
	local base, bonus = 0, cashMultiplier()
	for _, employee in ipairs(state.employees) do
		local creature = CreatureConfig.getCreature(employee.creature)
		base += creature and creature.income or 0
	end
	base *= player:GetAttribute("TeamMultiplier") or 1 -- overhaul 2: the building's team multiplier
	teamStatus.Text = string.format("Team %d/%d · earns $%d/s", #state.employees, state.maxEmployees, math.floor(base))
		.. (bonus > 1 and string.format(" (%s with passes and IPOs = $%d/s)", IpoConfig.formatMultiplier(bonus), math.floor(base * bonus)) or "")
	emptyLine.Visible = #state.employees == 0

	local pending = state.pending and CreatureConfig.getCreature(state.pending.creature) or nil -- state.pending is false when nobody waits
	pendingCard.card.Visible = pending ~= nil
	if pending then
		pendingCard.icon.Text = pending.emoji
		pendingCard.icon.BackgroundColor3 = rarityColor(pending.rarity)
		pendingCard.name.Text = string.format('New hire: <font color="%s">%s</font>', hex(rarityColor(pending.rarity)), pending.name)
		if teamIsFull() then
			pendingCard.desc.Text = employeeLine(pending) .. "\nTeam full: tap Replace on someone below, or let them go."
			setButton(pendingCard.button, "Let go", COLORS.danger, true)
		else
			pendingCard.desc.Text = employeeLine(pending) .. "\nThere's a free desk now!"
			setButton(pendingCard.button, "Hire", COLORS.buy, true)
		end
	end

	for _, parts in ipairs(employeeCards) do
		if state.pending then
			setButton(parts.button, "Replace", COLORS.gold, true)
		elseif fireConfirm[parts.id] and os.clock() - fireConfirm[parts.id] < 4 then
			setButton(parts.button, "Sure?", COLORS.danger, true)
		else
			setButton(parts.button, "Fire", COLORS.danger, true)
		end
	end
end)

-- Window: tabs, opening and closing -------------------------------------

local function refreshAll()
	teamButton.Text = "👥\n" .. #state.employees .. "/" .. state.maxEmployees
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

-- Only one window at a time (the shop does the same with the "OpenPanel" attribute)
local function setOpen(open, tab)
	window.Visible = open
	if open then
		playerGui:SetAttribute("OpenPanel", PANEL_NAME)
		showTab(tab or "Eggs")
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

local function toggle(tab)
	local showing = window.Visible and tabPages[tab].Visible
	setOpen(not showing, tab)
end

eggsButton.Activated:Connect(function()
	toggle("Eggs")
end)
teamButton.Activated:Connect(function()
	toggle("Team")
end)
closeButton.Activated:Connect(function()
	setOpen(false)
end)

-- Hatch reveal ------------------------------------------------------------

local revealGui = make("ScreenGui", {
	Name = "HatchRevealGui",
	ResetOnSpawn = false,
	IgnoreGuiInset = true,
	DisplayOrder = 50,
	Enabled = false,
	Parent = playerGui,
})
local overlay = make("TextButton", { -- a button, so tapping anywhere can close the reveal
	Size = UDim2.fromScale(1, 1),
	BackgroundColor3 = Color3.new(0, 0, 0),
	BackgroundTransparency = 0.35,
	Text = "",
	AutoButtonColor = false,
	Parent = revealGui,
})
local eggShape = make("Frame", {
	AnchorPoint = Vector2.new(0.5, 0.5),
	Position = UDim2.fromScale(0.5, 0.5),
	Size = UDim2.fromOffset(150, 190),
	Parent = overlay,
})
round(eggShape)
make("UIStroke", { Thickness = 4, Color = Color3.new(1, 1, 1), Parent = eggShape })
local flash = make("Frame", {
	Size = UDim2.fromScale(1, 1),
	BackgroundColor3 = Color3.new(1, 1, 1),
	BackgroundTransparency = 1,
	Parent = overlay,
})
local revealCard = make("Frame", {
	AnchorPoint = Vector2.new(0.5, 0.5),
	Position = UDim2.fromScale(0.5, 0.5),
	Size = UDim2.new(0.9, 0, 0.9, 0),
	BackgroundColor3 = COLORS.panel,
	Visible = false,
	Parent = overlay,
})
round(revealCard, 18)
make("UISizeConstraint", { MaxSize = Vector2.new(320, 400), Parent = revealCard })
local revealStroke = make("UIStroke", { Thickness = 5, Parent = revealCard })
local viewport = make("ViewportFrame", {
	Position = UDim2.fromScale(0.05, 0.03),
	Size = UDim2.fromScale(0.9, 0.5),
	BackgroundTransparency = 1,
	Ambient = Color3.fromRGB(190, 190, 200),
	LightColor = Color3.new(1, 1, 1),
	LightDirection = Vector3.new(-1, -1, 1),
	Parent = revealCard,
})
local viewportCamera = make("Camera", { Parent = viewport })
viewport.CurrentCamera = viewportCamera

local function revealLabel(y, height, font, maxSize)
	local label = make("TextLabel", {
		Position = UDim2.fromScale(0.05, y),
		Size = UDim2.fromScale(0.9, height),
		BackgroundTransparency = 1,
		Font = font,
		Text = "",
		RichText = true,
		TextColor3 = COLORS.text,
		TextWrapped = true,
		Parent = revealCard,
	})
	fitText(label, maxSize)
	return label
end
local rarityLabel = revealLabel(0.53, 0.07, Enum.Font.GothamBold, 20)
local nameLabel = revealLabel(0.6, 0.1, Enum.Font.GothamBold, 30)
local roleLabel = revealLabel(0.7, 0.07, Enum.Font.Gotham, 18)
local statusLabel = revealLabel(0.77, 0.07, Enum.Font.Gotham, 16)
local okButton = make("TextButton", {
	AnchorPoint = Vector2.new(0.5, 0),
	Position = UDim2.fromScale(0.5, 0.86),
	Size = UDim2.fromScale(0.6, 0.11),
	BackgroundColor3 = COLORS.buy,
	Font = Enum.Font.GothamBold,
	Text = "Nice!",
	TextColor3 = COLORS.text,
	Parent = revealCard,
})
round(okButton, 10)
fitText(okButton, 22)

local revealQueue = {}
local revealing = false
local closeReveal -- set while a reveal card is showing

-- While a reveal plays it counts as a window (request U2, A15): it holds the PlayerGui attribute "OpenPanel" as
-- "Hatch", so TaskClient asks the server to freeze waiting calls (none rings or runs out behind the reveal) and
-- the Daily window and the building's look wait. It takes "OpenPanel" only when no window has it (an open Eggs
-- window stays open), takes it again if that window closes during the reveal, and gives it back at the end only
-- if it still says "Hatch" (a window opened since keeps it). tools/hatch_reveal_test.luau runs this block.
-- HATCHPANEL-START
local REVEAL_PANEL = "Hatch"
local revealShowing = false
local function holdRevealPanel()
	if revealShowing and playerGui:GetAttribute("OpenPanel") == nil then
		playerGui:SetAttribute("OpenPanel", REVEAL_PANEL)
	end
end
local function setRevealShowing(showing)
	revealShowing = showing
	if showing then
		holdRevealPanel()
	elseif playerGui:GetAttribute("OpenPanel") == REVEAL_PANEL then
		playerGui:SetAttribute("OpenPanel", nil)
	end
end
playerGui:GetAttributeChangedSignal("OpenPanel"):Connect(holdRevealPanel)
-- HATCHPANEL-END

local function playReveal(info)
	local creature = CreatureConfig.getCreature(info.creature)
	local egg = CreatureConfig.getEgg(info.egg)
	if not creature then return end
	local color = rarityColor(creature.rarity)

	setRevealShowing(true)
	revealGui.Enabled = true
	GuiService.TouchControlsEnabled = false
	revealCard.Visible = false
	eggShape.Visible = true
	eggShape.Rotation = 0
	eggShape.Size = UDim2.fromOffset(150, 190)
	eggShape.BackgroundTransparency = 0
	eggShape.BackgroundColor3 = egg and egg.color or COLORS.gold

	-- The egg wobbles harder and harder, then pops in a flash
	for i = 1, 8 do
		local angle = (i % 2 == 0 and 1 or -1) * (4 + i * 2)
		TweenService:Create(eggShape, TweenInfo.new(0.09), { Rotation = angle }):Play()
		task.wait(0.1)
	end
	TweenService:Create(eggShape, TweenInfo.new(0.2), { Size = UDim2.fromOffset(210, 260), BackgroundTransparency = 1 }):Play()
	flash.BackgroundTransparency = 0
	TweenService:Create(flash, TweenInfo.new(0.5), { BackgroundTransparency = 1 }):Play()
	task.wait(0.15)
	eggShape.Visible = false

	-- The creature card, in its rarity color
	viewport:ClearAllChildren()
	viewportCamera = make("Camera", { Parent = viewport })
	viewport.CurrentCamera = viewportCamera
	local model = CreatureModels.build(creature)
	model.Parent = viewport
	local size = model:GetExtentsSize()
	-- Far enough back that the whole creature fits, with a little space around it
	local distance = math.max(size.Y * 1.45, size.X * 1.1, size.Z * 0.9) + 1
	viewportCamera.FieldOfView = 50
	viewportCamera.CFrame = CFrame.lookAt(Vector3.new(0, size.Y * 0.55, -distance), Vector3.new(0, size.Y * 0.5, 0))

	revealStroke.Color = color
	rarityLabel.Text = string.upper(creature.rarity) .. (creature.rarity == "Legendary" and " ✨" or "")
	rarityLabel.TextColor3 = color
	nameLabel.Text = creature.name
	nameLabel.TextColor3 = color
	roleLabel.Text = creature.role .. " · " .. earns(creature) .. "/s"
	if info.hired then
		statusLabel.Text = (info.auto and "Auto-Hatch: " or "") .. "Joined your team!"
		okButton.Text = "Nice!"
	else
		statusLabel.Text = "Your team is full. Choose who to replace."
		okButton.Text = "Choose"
	end
	revealCard.Visible = true
	revealCard.Size = UDim2.fromScale(0.5, 0.5)
	TweenService:Create(revealCard, TweenInfo.new(0.25, Enum.EasingStyle.Back), { Size = UDim2.fromScale(0.9, 0.9) }):Play()

	local spin = RunService.RenderStepped:Connect(function()
		model:PivotTo(CFrame.new(0, 0.5, 0) * CFrame.Angles(0, os.clock() * 1.2, 0)) -- pivot sits 0.5 above the feet
	end)
	local done = false
	closeReveal = function()
		done = true
	end
	local shownAt = os.clock()
	while not done and not (info.auto and info.hired and os.clock() - shownAt > 4) do
		task.wait(0.05)
	end
	closeReveal = nil
	spin:Disconnect()
	revealGui.Enabled = false
	setRevealShowing(false)
	GuiService.TouchControlsEnabled = playerGui:GetAttribute("OpenPanel") == nil
	if not info.hired then
		setOpen(true, "Team")
	end
end

local function onClickReveal()
	if closeReveal then
		closeReveal()
	end
end
okButton.Activated:Connect(onClickReveal)
overlay.Activated:Connect(onClickReveal)

eggHatched.OnClientEvent:Connect(function(info)
	table.insert(revealQueue, info)
	if revealing then return end
	revealing = true
	while #revealQueue > 0 do
		local ok, err = pcall(playReveal, table.remove(revealQueue, 1))
		if not ok then -- a reveal that breaks never keeps the screen covered or the calls frozen
			warn("EmployeeClient: hatch reveal failed: " .. tostring(err))
			closeReveal = nil
			revealGui.Enabled = false
			setRevealShowing(false)
			GuiService.TouchControlsEnabled = playerGui:GetAttribute("OpenPanel") == nil
		end
	end
	revealing = false
end)

-- Employees at work in the garage ----------------------------------------------
-- Overhaul 2 (the owner's point 8): a hire with a workstation sits on its chair ("Seat", a world position) facing its
-- desk (the server's "Facing", turned with the garage) and types: a small bob and lean, no wandering. A new hire first
-- walks in along the server's path ("Way1".."WayCount", world positions, from "ArriveAt" in server time at
-- "WalkSpeed"), then sits. A hire past the workstations stands at "Home". Only this screen moves them.

local workers = {} -- model -> { phase }

local function track(model)
	if model:IsA("Model") then
		workers[model] = { phase = math.random() * 10 }
	end
end
for _, model in ipairs(CollectionService:GetTagged("Employee")) do
	track(model)
end
CollectionService:GetInstanceAddedSignal("Employee"):Connect(track)
CollectionService:GetInstanceRemovedSignal("Employee"):Connect(function(model)
	workers[model] = nil
end)

-- WALK-START
-- (tools/office_test.py runs the code between the WALK markers: plain math only.)
-- Where a walker is `walked` studs along its path (a list of points), and the direction it faces there; nil once done
local function alongPath(way, walked)
	for i = 2, #way do
		local step = way[i] - way[i - 1]
		local length = step.Magnitude
		if walked <= length and length > 0 then
			return way[i - 1] + step * (walked / length), step
		end
		walked -= length
	end
	return nil
end
-- WALK-END

local function pathOf(model)
	local count = model:GetAttribute("WayCount")
	if type(count) ~= "number" or count < 2 then
		return nil
	end
	local way = {}
	for i = 1, count do
		local point = model:GetAttribute("Way" .. i)
		if typeof(point) ~= "Vector3" then
			return nil
		end
		way[i] = point
	end
	return way
end

RunService.Heartbeat:Connect(function(dt)
	local camera = workspace.CurrentCamera
	if not camera then return end
	local cameraPosition = camera.CFrame.Position
	local serverNow = workspace:GetServerTimeNow()
	for model, w in pairs(workers) do
		local home = model:GetAttribute("Home")
		if typeof(home) == "Vector3" and model.PrimaryPart and (home - cameraPosition).Magnitude < 160 then
			local facing = model:GetAttribute("Facing")
			facing = type(facing) == "number" and facing or math.pi
			local seat = model:GetAttribute("Seat")
			local arriveAt, speed = model:GetAttribute("ArriveAt"), model:GetAttribute("WalkSpeed")
			local at, step
			if type(arriveAt) == "number" and type(speed) == "number" and serverNow - arriveAt < 60 then
				local way = pathOf(model)
				if way then
					at, step = alongPath(way, math.max(0, serverNow - arriveAt) * speed)
				end
			end
			if at then -- walking in
				w.phase += dt * 12
				local yaw = step.Magnitude > 0.01 and math.atan2(-step.X, -step.Z) or facing -- models face -Z
				model:PivotTo(CFrame.new(at + Vector3.new(0, math.abs(math.sin(w.phase)) * 0.35, 0)) * CFrame.Angles(0, yaw, 0))
			elseif typeof(seat) == "Vector3" then -- at work: typing, with a small lean toward the desk now and then
				w.phase += dt * 9
				local typing = math.sin(w.phase * 0.13) > -0.3
				local bob = typing and math.abs(math.sin(w.phase)) * 0.05 or 0
				local lean = typing and math.rad(6) or 0
				model:PivotTo(CFrame.new(seat + Vector3.new(0, bob, 0)) * CFrame.Angles(0, facing, 0) * CFrame.Angles(-lean, 0, 0))
			else -- no workstation: standing at its spot, breathing
				w.phase += dt * 2.5
				model:PivotTo(CFrame.new(home + Vector3.new(0, math.sin(w.phase) * 0.06, 0)) * CFrame.Angles(0, facing, 0))
			end
		end
	end
end)

-- Other players' incubator prompts are hidden on this screen
local function hideForeignPrompt(prompt)
	if prompt:GetAttribute("OwnerUserId") ~= player.UserId then
		prompt.MaxActivationDistance = 0
	end
end
for _, prompt in ipairs(CollectionService:GetTagged("IncubatorPrompt")) do
	hideForeignPrompt(prompt)
end
CollectionService:GetInstanceAddedSignal("IncubatorPrompt"):Connect(hideForeignPrompt)

-- Keeping it up to date -------------------------------------------------

teamUpdate.OnClientEvent:Connect(function(snapshot)
	state = snapshot
	rebuildTeamCards()
	refreshAll()
end)

-- Pass or boost changes: slots may change, so ask for fresh numbers; redraw the rest
player:GetAttributeChangedSignal("Pass_ExtraSlots"):Connect(function()
	task.spawn(request, "Sync")
end)
player.AttributeChanged:Connect(refreshAll)

showTab("Eggs")
applyLayout()
window:GetPropertyChangedSignal("AbsoluteSize"):Connect(applyLayout)

-- Ask for the team (and any reveals from eggs that hatched while this screen was loading)
task.spawn(function()
	for _ = 1, 20 do
		local ok, success = pcall(function()
			return teamAction:InvokeServer("Sync")
		end)
		if ok and success then
			break
		end
		task.wait(1) -- the server is still loading this player's save
	end
end)

-- Timers tick while the window is open
while true do
	task.wait(0.5)
	refreshAll()
end
