-- DailyClient: the daily reward gift chip and the 7-day calendar window (milestone 6).
-- Put this LocalScript in StarterPlayer > StarterPlayerScripts. It builds the screen by itself.
-- It only shows what DailyServer puts on the player (attributes) and asks the server to "Claim".
-- It never decides the day, the streak or the reward, and the device clock is never used:
-- the countdown uses the server's time. Everything is a tap: nothing to type in.

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local GuiService = game:GetService("GuiService")

local DailyConfig = require(ReplicatedStorage:WaitForChild("DailyConfig"))
local CreatureConfig = require(ReplicatedStorage:WaitForChild("CreatureConfig")) -- egg names and odds
local ShopConfig = require(ReplicatedStorage:WaitForChild("ShopConfig")) -- money format, Luck Boost
local IpoConfig = require(ReplicatedStorage:WaitForChild("IpoConfig")) -- the luck perk, for the odds
local remotes = ReplicatedStorage:WaitForChild("DailyRemotes")
local teamRemotes = ReplicatedStorage:WaitForChild("EmployeeRemotes") -- the egg card's server data (nextHires)
local dailyAction = remotes:WaitForChild("DailyAction")

local player = Players.LocalPlayer
local playerGui = player:WaitForChild("PlayerGui")
local PANEL_NAME = "Daily"
local TEXTS = DailyConfig.Texts
local DAYS = DailyConfig.Days

local COLORS = {
	panel = Color3.fromRGB(28, 30, 38),
	card = Color3.fromRGB(42, 45, 56),
	cardDone = Color3.fromRGB(36, 52, 44),
	text = Color3.new(1, 1, 1),
	subtext = Color3.fromRGB(185, 190, 205),
	buy = Color3.fromRGB(0, 200, 90), -- same green as the buy pad
	disabled = Color3.fromRGB(85, 88, 100),
	gold = Color3.fromRGB(255, 200, 60),
	close = Color3.fromRGB(210, 65, 65),
	dot = Color3.fromRGB(230, 60, 60),
}

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

local function hex(color)
	return "#" .. color:ToHex()
end

-- The state the server puts on the player -----------------------------------------

local function attr(name, default)
	local value = player:GetAttribute(name)
	if value == nil then
		return default
	end
	return value
end

local function enabled()
	return DailyConfig.Enabled and attr("DailyEnabled", false) == true
end

local function ready()
	return enabled() and attr("DailyReady", false) == true
end

local function waitLeft()
	return attr("DailyNextAt", 0) - workspace:GetServerTimeNow()
end

local function income()
	local stats = player:FindFirstChild("leaderstats")
	local value = stats and stats:FindFirstChild("Income")
	return value and value.Value or 0
end

-- The same luck the Recruiting window shows: the Talent Scouts perk, plus Luck Boost while it runs
local function luckMultiplier()
	local luck = 1 + IpoConfig.perkValue("BaseLuck", attr("IpoPerk_BaseLuck", 0))
	if attr("LuckBoostUntil", 0) > workspace:GetServerTimeNow() then
		for _, product in ipairs(ShopConfig.Products) do
			if product.effect.luckMultiplier then
				return luck * product.effect.luckMultiplier
			end
		end
	end
	return luck
end

-- Players for whom paid random items are restricted see no odds, only the next hire (FR-13, D9 option B).
-- Same rule as the Eggs tab: "RandomRestricted" is set by the server from PolicyService, and not known
-- yet (nil) counts as restricted. nextHires is the server's EmployeeRemotes snapshot (egg key -> creature key).
-- NEXTHIRE-START
-- (tools/daily_test.py runs the code between the NEXTHIRE markers, so keep it free of Roblox calls.)
local function isRestricted(flag)
	return flag ~= false
end

-- The egg card's wording: "Next hire: Name", then the fixed-order note (kept short for a phone)
local function nextHireLine(egg, creature, colorHex)
	local name = "loading..."
	if creature then
		name = string.format('<font color="%s">%s %s</font>', colorHex, creature.emoji or "", creature.name)
	end
	return egg.name .. " next hire: " .. name .. ". Your hires follow a fixed order, not a random roll."
end

local function eggNote(restricted)
	return restricted and "tap for next hire" or "tap for odds"
end
-- NEXTHIRE-END

local shownEgg = nil -- the egg card whose line is showing, redrawn when the restriction or next hire changes
local nextHires = false -- latest nextHires from the server (false = none yet)

local function restrictedNow()
	return isRestricted(player:GetAttribute("RandomRestricted"))
end

-- Same numbers as the Eggs tab (CreatureConfig.getCreatureOdds: the server's weights, rounded to add up
-- to exactly 100.00%), per rarity; the Eggs tab lists every hire's own odds
local function oddsText(egg)
	if restrictedNow() then
		local nextKey = nextHires and nextHires[egg.key]
		local creature = nextKey and CreatureConfig.getCreature(nextKey)
		local rarity = creature and CreatureConfig.getRarity(creature.rarity)
		return nextHireLine(egg, creature, hex(rarity and rarity.color or COLORS.text))
	end
	local parts = {}
	for _, entry in ipairs(CreatureConfig.rarityOdds(CreatureConfig.getCreatureOdds(egg, luckMultiplier()))) do
		local rarity = CreatureConfig.getRarity(entry.rarity)
		table.insert(parts, string.format('<font color="%s">%s</font> %s', hex(rarity and rarity.color or COLORS.text), entry.rarity, CreatureConfig.formatOdds(entry.units)))
	end
	return egg.name .. " odds: " .. table.concat(parts, " · ") .. " (each hire's odds: Eggs tab)"
end

-- "Garage Egg", "$3,000", "Unicorn Egg\n+3 Shares"
local function rewardText(day)
	local parts = {}
	local cash = DailyConfig.cashFor(day, income())
	if cash > 0 then
		table.insert(parts, ShopConfig.formatCash(cash))
	end
	local egg = day.egg and CreatureConfig.getEgg(day.egg)
	if egg then
		table.insert(parts, egg.name)
	end
	if day.shares then
		table.insert(parts, "+" .. day.shares .. " Shares")
	end
	return table.concat(parts, "\n")
end

-- Screen ----------------------------------------------------------------

-- Two layers, like IpoClient: the chip sits with the HUD under every window (DisplayOrder -1),
-- the Daily window and its messages above the HUD buttons (DisplayOrder 5)
local gui = make("ScreenGui", {
	Name = "DailyGui",
	ResetOnSpawn = false,
	ZIndexBehavior = Enum.ZIndexBehavior.Sibling,
	DisplayOrder = -1,
	Parent = playerGui,
})
local front = make("ScreenGui", {
	Name = "DailyWindowGui",
	ResetOnSpawn = false,
	ZIndexBehavior = Enum.ZIndexBehavior.Sibling,
	DisplayOrder = 5,
	Parent = playerGui,
})

-- Gift chip: right of the valuation bar (IpoClient leaves room for it). A red dot while a reward
-- is waiting, the countdown once it's claimed.
local CHIP = DailyConfig.ChipSize
local chip = make("TextButton", {
	Name = "DailyChip",
	Size = UDim2.fromOffset(CHIP, CHIP),
	BackgroundColor3 = COLORS.panel,
	BackgroundTransparency = 0.15,
	AutoButtonColor = true,
	Text = "",
	Visible = false,
	Parent = gui,
})
round(chip, 12)
local chipStroke = make("UIStroke", { Thickness = 2, Color = COLORS.gold, Transparency = 0.4, ApplyStrokeMode = Enum.ApplyStrokeMode.Border, Parent = chip })
local chipIcon = make("TextLabel", {
	Size = UDim2.new(1, 0, 0.62, 0),
	BackgroundTransparency = 1,
	Font = Enum.Font.GothamBold,
	Text = "🎁",
	TextColor3 = COLORS.text,
	Parent = chip,
})
fitText(chipIcon, 26)
local chipText = make("TextLabel", {
	Position = UDim2.fromScale(0.05, 0.6),
	Size = UDim2.fromScale(0.9, 0.36),
	BackgroundTransparency = 1,
	Font = Enum.Font.GothamBold,
	Text = "",
	TextColor3 = COLORS.gold,
	Parent = chip,
})
fitText(chipText, 12)
local chipDot = make("Frame", {
	AnchorPoint = Vector2.new(0.5, 0.5),
	Position = UDim2.fromScale(0.9, 0.1),
	Size = UDim2.fromOffset(14, 14),
	BackgroundColor3 = COLORS.dot,
	Visible = false,
	Parent = chip,
})
make("UICorner", { CornerRadius = UDim.new(1, 0), Parent = chipDot })

-- Pop-up messages: bottom middle, above the other windows' own toasts (-16, -72, -128, -184).
-- On short phone screens -240 would be near the top, so it uses the Recruiting window's -72 slot
-- (that window is closed while the Daily window is open).
local toast = make("TextLabel", {
	Name = "Toast",
	AnchorPoint = Vector2.new(0.5, 1),
	Position = UDim2.new(0.5, 0, 1, -240),
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
local function placeToast()
	toast.Position = UDim2.new(0.5, 0, 1, front.AbsoluteSize.Y < 460 and -72 or -240)
end
front:GetPropertyChangedSignal("AbsoluteSize"):Connect(placeToast)
placeToast()

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

-- Window ----------------------------------------------------------------

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
	Text = TEXTS.Title,
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

local function line(color)
	local label = make("TextLabel", {
		Size = UDim2.new(1, 0, 0, 20),
		BackgroundTransparency = 1,
		Font = Enum.Font.GothamBold,
		Text = "",
		RichText = true,
		TextColor3 = color,
		TextWrapped = true,
		TextXAlignment = Enum.TextXAlignment.Left,
		Parent = window,
	})
	fitText(label, 16)
	return label
end

local streakLine = line(COLORS.text)
local noticeLine = line(COLORS.subtext) -- "You missed a day..." in a calm grey, never red
local infoLine = line(COLORS.subtext) -- the rules, or the odds of the egg card you tapped

local grid = make("Frame", {
	BackgroundTransparency = 1,
	Parent = window,
})

local claimButton = make("TextButton", {
	AnchorPoint = Vector2.new(0, 1),
	Position = UDim2.new(0, 0, 1, 0),
	Size = UDim2.new(1, 0, 0, 56),
	BackgroundColor3 = COLORS.buy,
	Font = Enum.Font.GothamBold,
	Text = "",
	TextColor3 = COLORS.text,
	Parent = window,
})
round(claimButton, 12)
fitText(claimButton, 24)

-- One card per calendar day: "Day 3", an icon, the reward, and a note
local cards = {}
for i, day in ipairs(DAYS) do
	local card = make("TextButton", {
		Name = "Day" .. i,
		BackgroundColor3 = COLORS.card,
		AutoButtonColor = false,
		Text = "",
		Parent = grid,
	})
	round(card, 12)
	local stroke = make("UIStroke", { Thickness = 3, Color = COLORS.gold, Transparency = 1, ApplyStrokeMode = Enum.ApplyStrokeMode.Border, Parent = card })
	local function cardLabel(y, height, font, color, maxSize)
		local label = make("TextLabel", {
			Position = UDim2.fromScale(0.06, y),
			Size = UDim2.fromScale(0.88, height),
			BackgroundTransparency = 1,
			Font = font,
			Text = "",
			TextColor3 = color,
			Parent = card,
		})
		fitText(label, maxSize)
		return label
	end
	local parts = {
		card = card,
		stroke = stroke,
		dayLabel = cardLabel(0.04, 0.18, Enum.Font.GothamBold, COLORS.subtext, 16),
		icon = cardLabel(0.22, 0.3, Enum.Font.GothamBold, COLORS.text, 34),
		reward = cardLabel(0.53, 0.27, Enum.Font.GothamBold, COLORS.text, 16),
		note = cardLabel(0.81, 0.15, Enum.Font.Gotham, COLORS.subtext, 12),
	}
	parts.icon.Text = day.icon or "🎁"
	cards[i] = parts

	-- Tapping a card explains it: an egg's odds (design rule: show odds), or what the Cash is
	card.Activated:Connect(function()
		local egg = day.egg and CreatureConfig.getEgg(day.egg)
		shownEgg = egg
		if egg then
			infoLine.Text = oddsText(egg)
		elseif day.cashMinutes then
			infoLine.Text = string.format("Day %d: %d min of your Income when you claim it (%s now).", i,
				math.min(day.cashMinutes, DailyConfig.CashMaxMinutes), ShopConfig.formatCash(DailyConfig.cashFor(day, income())))
		end
	end)
end

-- Phones: 4 cards on top and 3 below on a narrow window, one row of 7 on a wide one.
-- Runs again whenever the screen size changes.
local function applyLayout()
	local size = window.AbsoluteSize
	local width, height = size.X - 20, size.Y - 20 -- inside the padding
	local short = height < 310
	local headerHeight = short and 34 or 40
	local lineHeight = short and 18 or 20
	local buttonHeight = short and 48 or 56
	local infoHeight = short and 30 or 36
	local gap = 6

	title.Size = UDim2.new(1, -56, 0, headerHeight)
	closeButton.Size = UDim2.fromOffset(44, headerHeight)
	local y = headerHeight + 4
	streakLine.Position = UDim2.fromOffset(0, y)
	streakLine.Size = UDim2.new(1, 0, 0, lineHeight)
	y += lineHeight
	noticeLine.Position = UDim2.fromOffset(0, y)
	noticeLine.Size = UDim2.new(1, 0, 0, lineHeight)
	y += lineHeight + gap
	claimButton.Size = UDim2.new(1, 0, 0, buttonHeight)
	local bottom = height - buttonHeight - gap
	infoLine.Position = UDim2.fromOffset(0, bottom - infoHeight)
	infoLine.Size = UDim2.new(1, 0, 0, infoHeight)
	local gridHeight = math.max(0, bottom - infoHeight - gap - y)
	grid.Position = UDim2.fromOffset(0, y)
	grid.Size = UDim2.new(1, 0, 0, gridHeight)

	local perRow = width >= #DAYS * 70 + (#DAYS - 1) * gap and #DAYS or math.ceil(#DAYS / 2)
	local rows = math.ceil(#DAYS / perRow)
	local cardWidth = (width - (perRow - 1) * gap) / perRow
	local cardHeight = math.min((gridHeight - (rows - 1) * gap) / rows, cardWidth * 1.7)
	local top = (gridHeight - (rows * cardHeight + (rows - 1) * gap)) / 2 -- centered in the space
	for i, parts in ipairs(cards) do
		local row = (i - 1) // perRow
		local column = (i - 1) % perRow
		local inRow = math.min(perRow, #DAYS - row * perRow)
		local left = (width - (inRow * cardWidth + (inRow - 1) * gap)) / 2 -- a shorter last row is centered
		parts.card.Position = UDim2.fromOffset(left + column * (cardWidth + gap), top + row * (cardHeight + gap))
		parts.card.Size = UDim2.fromOffset(cardWidth, cardHeight)
	end
end

-- Behaviour -------------------------------------------------------------

local claiming = false -- waiting for the server's answer

local function refreshWindow()
	local day = attr("DailyDay", 1)
	local isReady = ready()
	local streak = attr("DailyStreak", 0)
	streakLine.Text = string.format(TEXTS.Streak, streak, streak == 1 and "day" or "days", attr("DailyBest", 0))

	if isReady and attr("DailyKept", false) then
		noticeLine.Text = string.format(TEXTS.Grace, day)
	elseif isReady and attr("DailyLostDay", 0) > 0 then
		noticeLine.Text = string.format(TEXTS.Reset, attr("DailyMissed", 0), attr("DailyLostDay", 0))
	else
		noticeLine.Text = ""
	end
	if shownEgg then
		infoLine.Text = oddsText(shownEgg)
	elseif infoLine.Text == "" then
		infoLine.Text = TEXTS.Rules
	end

	for i, parts in ipairs(cards) do
		local done = i < day or (i == day and not isReady) -- claimed in this round of the calendar
		local today = i == day
		parts.dayLabel.Text = (done and "✅ " or "") .. (today and isReady and "Today" or ("Day " .. i))
		parts.dayLabel.TextColor3 = today and COLORS.gold or COLORS.subtext
		parts.reward.Text = rewardText(DAYS[i])
		parts.note.Text = DAYS[i].egg and eggNote(restrictedNow()) or (DAYS[i].cashMinutes and (math.min(DAYS[i].cashMinutes, DailyConfig.CashMaxMinutes) .. " min of income")) or ""
		parts.card.BackgroundColor3 = done and COLORS.cardDone or COLORS.card
		parts.card.BackgroundTransparency = (not done and not today) and 0.35 or 0 -- future days are dimmed
		parts.stroke.Transparency = today and 0 or 1
	end

	local blocked = attr("DailyBlocked", "")
	if not enabled() then
		setButton(claimButton, TEXTS.Off, COLORS.disabled, false)
	elseif claiming then
		setButton(claimButton, "Claiming...", COLORS.disabled, false)
	elseif isReady and blocked ~= "" then
		setButton(claimButton, blocked, COLORS.disabled, false)
	elseif isReady then
		setButton(claimButton, string.format(TEXTS.Claim, day), COLORS.buy, true)
	else
		setButton(claimButton, string.format(TEXTS.NextIn, DailyConfig.formatWait(waitLeft())), COLORS.disabled, false)
	end
end

-- The Negotiation and Poach Alert panels (PoachClient) sit at the top of the screen: the chip
-- hides while one of them shows, so it never covers them on narrow phones
local poachPanels = {}
local function poachPanelShowing()
	for _, panel in ipairs(poachPanels) do
		if panel.Visible then
			return true
		end
	end
	return false
end

local function refreshChip()
	chip.Visible = enabled() and not poachPanelShowing()
	local isReady = ready()
	chipDot.Visible = isReady
	chipStroke.Transparency = isReady and 0 or 0.4
	chipText.Text = isReady and "CLAIM" or DailyConfig.formatWait(waitLeft())
	chipText.TextColor3 = isReady and COLORS.gold or COLORS.subtext
end

local function refreshAll()
	refreshChip()
	if window.Visible then
		refreshWindow()
	end
end

-- Only one window at a time (the shop, Recruiting, Poach and IPO windows do the same with "OpenPanel")
local function setOpen(open)
	window.Visible = open
	if open then
		playerGui:SetAttribute("OpenPanel", PANEL_NAME)
		infoLine.Text = ""
		shownEgg = nil
	elseif playerGui:GetAttribute("OpenPanel") == PANEL_NAME then
		playerGui:SetAttribute("OpenPanel", nil)
	end
	-- Hide the phone joystick and jump button while a window is open
	GuiService.TouchControlsEnabled = playerGui:GetAttribute("OpenPanel") == nil
	refreshAll()
end

playerGui:GetAttributeChangedSignal("OpenPanel"):Connect(function()
	if window.Visible and playerGui:GetAttribute("OpenPanel") ~= PANEL_NAME then
		window.Visible = false
	end
end)

chip.Activated:Connect(function()
	setOpen(not window.Visible)
end)
closeButton.Activated:Connect(function()
	setOpen(false)
end)

-- The only request: "Claim". The server answers after the reward is saved.
claimButton.Activated:Connect(function()
	if claiming or not ready() or attr("DailyBlocked", "") ~= "" then return end
	claiming = true
	refreshAll()
	local ok, success, message = pcall(function()
		return dailyAction:InvokeServer("Claim")
	end)
	claiming = false
	if not ok then
		warn("Daily claim failed: " .. tostring(success))
		showToast("Couldn't reach the server. Please try again.")
	elseif message then
		showToast(message)
	end
	refreshAll()
end)

-- Placing the chip -----------------------------------------------------------

-- Right of the valuation bar, vertically centered on it. IpoClient places that bar with offsets
-- in a ScreenGui like this one, so the same numbers line up. Without it, the top-right corner.
local valuationBar
local function placeChip()
	local screen = gui.AbsoluteSize
	if valuationBar and valuationBar.Parent then
		local position, size = valuationBar.Position, valuationBar.Size
		local x = position.X.Offset + size.X.Offset + DailyConfig.ChipGap
		chip.Position = UDim2.fromOffset(math.min(x, screen.X - CHIP - 2), position.Y.Offset + (size.Y.Offset - CHIP) / 2)
	else
		chip.Position = UDim2.fromOffset(screen.X - CHIP - 10, 12)
	end
end
gui:GetPropertyChangedSignal("AbsoluteSize"):Connect(placeChip)
placeChip()
task.spawn(function()
	local ipoGui = playerGui:WaitForChild("IpoGui", 30)
	valuationBar = ipoGui and ipoGui:WaitForChild("ValuationBar", 30)
	if valuationBar then
		valuationBar:GetPropertyChangedSignal("Position"):Connect(placeChip)
		valuationBar:GetPropertyChangedSignal("Size"):Connect(placeChip)
		placeChip()
	end
end)

task.spawn(function()
	local poachFront = playerGui:WaitForChild("PoachWindowGui", 30)
	if not poachFront then return end
	for _, name in ipairs({ "Negotiation", "PoachAlert" }) do
		local panel = poachFront:WaitForChild(name, 10)
		if panel then
			table.insert(poachPanels, panel)
			panel:GetPropertyChangedSignal("Visible"):Connect(refreshChip)
		end
	end
	refreshChip()
end)

applyLayout()
window:GetPropertyChangedSignal("AbsoluteSize"):Connect(applyLayout)
refreshAll()

-- Keeping it up to date -------------------------------------------------

player.AttributeChanged:Connect(function(name)
	if string.sub(name, 1, 5) == "Daily" or name == "RandomRestricted" then
		refreshAll()
	end
end)

-- The next hires come from the same server snapshot as the egg card; ask once in case it was sent
-- before this script started
teamRemotes:WaitForChild("TeamUpdate").OnClientEvent:Connect(function(snapshot)
	nextHires = type(snapshot) == "table" and snapshot.nextHires or false
	refreshAll()
end)
task.spawn(function()
	pcall(function()
		teamRemotes:WaitForChild("TeamAction"):InvokeServer("Sync")
	end)
end)

-- Opens by itself once per join when a reward is waiting: a few seconds in, only after the M5
-- first minute (the server's DailyAutoOpen), and never over another window or a poach panel
task.spawn(function()
	if not DailyConfig.AutoOpen then return end
	local started = os.clock()
	task.wait(DailyConfig.AutoOpenDelay)
	while os.clock() - started < DailyConfig.AutoOpenWithin do
		if ready() and attr("DailyAutoOpen", false) == true
			and playerGui:GetAttribute("OpenPanel") == nil and not poachPanelShowing() then
			setOpen(true)
			return
		end
		task.wait(1)
	end
end)

-- The countdown ticks (chip, and the button while the window is open)
while true do
	task.wait(1)
	refreshAll()
end
