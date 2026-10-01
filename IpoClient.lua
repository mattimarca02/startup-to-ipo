-- IpoClient: the IPO button, the valuation bar on the HUD, and the IPO window (milestone 4):
-- going public, the IPO shop (Shares) and the in-server leaderboard.
-- Put this LocalScript in StarterPlayer > StarterPlayerScripts. It builds the screen by itself.
-- It only shows what the server says (player attributes) and asks IpoServer to do things.

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local GuiService = game:GetService("GuiService")
local TweenService = game:GetService("TweenService")

local IpoConfig = require(ReplicatedStorage:WaitForChild("IpoConfig"))
local ShopConfig = require(ReplicatedStorage:WaitForChild("ShopConfig"))
local remotes = ReplicatedStorage:WaitForChild("IpoRemotes")
local ipoAction = remotes:WaitForChild("IpoAction")
local ipoEvent = remotes:WaitForChild("IpoEvent")

local player = Players.LocalPlayer
local playerGui = player:WaitForChild("PlayerGui")
local PANEL_NAME = "Ipo"
local HUD_SLOT = 4 -- EGGS 0, SHOP 1, TEAM 2, POACH 3, IPO 4
local CONFIRM_SECONDS = 15 -- the confirm screen closes itself after this long

local COLORS = {
	panel = Color3.fromRGB(28, 30, 38),
	card = Color3.fromRGB(42, 45, 56),
	tab = Color3.fromRGB(55, 58, 72),
	text = Color3.new(1, 1, 1),
	subtext = Color3.fromRGB(185, 190, 205),
	buy = Color3.fromRGB(0, 200, 90), -- same green as the buy pad
	disabled = Color3.fromRGB(85, 88, 100),
	gold = Color3.fromRGB(255, 200, 60), -- same gold as the IPO pad
	close = Color3.fromRGB(210, 65, 65),
	hud = Color3.fromRGB(225, 150, 20),
	bar = Color3.fromRGB(20, 22, 28),
}

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

-- The IPO state the server puts on the player ----------------------------------

local function attr(name)
	return player:GetAttribute(name) or 0
end

local function ipoCount()
	return attr("IpoCount")
end

local function valuation()
	return attr("IpoValuation")
end

local function sharesPassMultiplier()
	local multiplier = 1
	for _, pass in ipairs(ShopConfig.Passes) do
		if player:GetAttribute("Pass_" .. pass.key) then
			multiplier *= pass.effect.sharesMultiplier or 1
		end
	end
	return multiplier
end

local function stageInfo()
	local count = ipoCount()
	local index = IpoConfig.stageIndex(valuation(), count)
	local stage = IpoConfig.Stages[index]
	local isLast = index == #IpoConfig.Stages
	local from = IpoConfig.stageValuation(index, count)
	local to = isLast and from or IpoConfig.stageValuation(index + 1, count)
	local progress = isLast and 1 or math.clamp((valuation() - from) / math.max(1, to - from), 0, 1)
	return { index = index, stage = stage, ready = isLast, to = to, progress = progress }
end

local function cooldownLeft()
	return attr("IpoCooldownUntil") - workspace:GetServerTimeNow()
end

-- "-10%", "+1", "+2h" for one level of a perk, or for `level` levels
local function perkEffectText(perk, level)
	local value = perk.perLevel * level
	if perk.effect == "hatchTime" or perk.effect == "poachDiscount" then
		return "-" .. math.floor(value * 100 + 0.5) .. "%"
	elseif perk.effect == "luck" then
		return "+" .. math.floor(value * 100 + 0.5) .. "%"
	elseif perk.effect == "offlineSeconds" then
		return "+" .. math.floor(value / 3600 + 0.5) .. "h"
	end
	return "+" .. value
end

-- Screen ----------------------------------------------------------------

-- Two layers, like PoachClient: the HUD button and valuation bar sit under the other windows
-- (DisplayOrder -1), while the IPO window and its messages sit above every HUD button (DisplayOrder 5)
local gui = make("ScreenGui", {
	Name = "IpoGui",
	ResetOnSpawn = false,
	ZIndexBehavior = Enum.ZIndexBehavior.Sibling,
	DisplayOrder = -1,
	Parent = playerGui,
})
local front = make("ScreenGui", {
	Name = "IpoWindowGui",
	ResetOnSpawn = false,
	ZIndexBehavior = Enum.ZIndexBehavior.Sibling,
	DisplayOrder = 5,
	Parent = playerGui,
})

local function isShort()
	return gui.AbsoluteSize.Y < 460 -- same switch as the other HUD buttons
end

-- HUD button, in the shared layout with EGGS, SHOP, TEAM and POACH
local ipoButton = make("TextButton", {
	Name = "IpoButton",
	BackgroundColor3 = COLORS.hud,
	Font = Enum.Font.GothamBold,
	Text = "📈\nIPO",
	TextColor3 = COLORS.text,
	Parent = gui,
})
round(ipoButton, 18)
fitText(ipoButton, 22)
local buttonStroke = make("UIStroke", { Thickness = 3, Transparency = 0.5, ApplyStrokeMode = Enum.ApplyStrokeMode.Border, Parent = ipoButton })

-- Valuation bar: stage, progress to the next stage, multiplier and Shares. Top-left, right of
-- the button column on big screens; next to the HUD row on short phone screens (or under it
-- if the screen is narrow).
local hudBar = make("TextButton", {
	Name = "ValuationBar",
	Size = UDim2.fromOffset(250, 64),
	BackgroundColor3 = COLORS.panel,
	BackgroundTransparency = 0.15,
	AutoButtonColor = true,
	Text = "",
	Parent = gui,
})
round(hudBar, 12)
make("UIStroke", { Thickness = 2, Color = COLORS.gold, Transparency = 0.4, ApplyStrokeMode = Enum.ApplyStrokeMode.Border, Parent = hudBar })
local hudStage = make("TextLabel", {
	Position = UDim2.fromOffset(10, 4),
	Size = UDim2.new(1, -20, 0, 20),
	BackgroundTransparency = 1,
	Font = Enum.Font.GothamBold,
	Text = "",
	TextColor3 = COLORS.gold,
	TextXAlignment = Enum.TextXAlignment.Left,
	Parent = hudBar,
})
fitText(hudStage, 16)
local hudTrack = make("Frame", {
	Position = UDim2.fromOffset(10, 26),
	Size = UDim2.new(1, -20, 0, 12),
	BackgroundColor3 = COLORS.bar,
	Parent = hudBar,
})
round(hudTrack, 6)
local hudFill = make("Frame", {
	Size = UDim2.fromScale(0, 1),
	BackgroundColor3 = COLORS.gold,
	Parent = hudTrack,
})
round(hudFill, 6)
local hudInfo = make("TextLabel", {
	Position = UDim2.fromOffset(10, 40),
	Size = UDim2.new(1, -20, 0, 20),
	BackgroundTransparency = 1,
	Font = Enum.Font.GothamBold,
	Text = "",
	TextColor3 = COLORS.subtext,
	TextXAlignment = Enum.TextXAlignment.Left,
	Parent = hudBar,
})
fitText(hudInfo, 15)

local function placeHud()
	if isShort() then
		ipoButton.AnchorPoint = Vector2.new(0, 0)
		ipoButton.Size = UDim2.fromOffset(64, 64)
		ipoButton.Position = UDim2.fromOffset(10 + HUD_SLOT * 72, 6)
		local rowEnd = 10 + (HUD_SLOT + 1) * 72
		local width = math.clamp(gui.AbsoluteSize.X - rowEnd - 10, 0, 250)
		if width >= 180 then
			hudBar.Position = UDim2.fromOffset(rowEnd, 6)
			hudBar.Size = UDim2.fromOffset(width, 64)
		else
			hudBar.Position = UDim2.fromOffset(10, 76)
			hudBar.Size = UDim2.fromOffset(math.min(250, gui.AbsoluteSize.X - 20), 64)
		end
	else
		ipoButton.AnchorPoint = Vector2.new(0, 0.5)
		ipoButton.Size = UDim2.fromOffset(76, 76)
		ipoButton.Position = UDim2.new(0, 12, 0.5, (HUD_SLOT - 2) * 86)
		-- Right of the button column, so it never covers a HUD button
		hudBar.Position = UDim2.fromOffset(98, 12)
		hudBar.Size = UDim2.fromOffset(math.clamp(gui.AbsoluteSize.X - 108, 180, 250), 64)
	end
end
placeHud()

-- Pop-up messages: bottom middle, like the shop's
local toast = make("TextLabel", {
	Name = "Toast",
	AnchorPoint = Vector2.new(0.5, 1),
	Position = UDim2.new(0.5, 0, 1, -16),
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
	Text = "Go Public (IPO)",
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

local tabNames = { "IPO", "Shares Shop", "Leaderboard" }
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

-- A line of text across the page
local function makeLine(page, order, textColor, height)
	local label = make("TextLabel", {
		LayoutOrder = order,
		Size = UDim2.new(1, 0, 0, height or 30),
		BackgroundTransparency = 1,
		Font = Enum.Font.GothamBold,
		Text = "",
		RichText = true,
		TextColor3 = textColor or COLORS.subtext,
		TextWrapped = true,
		TextXAlignment = Enum.TextXAlignment.Left,
		Parent = page,
	})
	fitText(label, 17)
	return label
end

-- One row: icon, name, description, and a button on the right (button = false: no button)
local function makeCard(page, order, icon, withButton)
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
	local name = make("TextLabel", {
		Position = UDim2.new(0, 68, 0, 8),
		Size = UDim2.new(1, -68 - 136, 0, 24),
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
		Size = UDim2.new(1, -68 - 136, 0, 44),
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
	local button
	if withButton ~= false then
		button = make("TextButton", {
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
	end
	local parts = { card = card, icon = iconLabel, name = name, desc = desc, button = button }
	table.insert(cardParts, parts)
	return parts
end

-- Asks the server and shows its answer
local busy = false
local function request(action, arg)
	if busy then return false end
	busy = true
	local ok, success, message = pcall(function()
		return ipoAction:InvokeServer(action, arg)
	end)
	busy = false
	if not ok then
		showToast("Something went wrong. Please try again.")
		return false
	end
	if message then
		showToast(message)
	end
	return success
end

-- IPO tab ---------------------------------------------------------------

local ipoPage = tabPages.IPO
local stageLine = makeLine(ipoPage, 1, COLORS.gold)

local stageRows = {}
for i, stage in ipairs(IpoConfig.Stages) do
	stageRows[i] = makeLine(ipoPage, 1 + i, COLORS.subtext, 24)
end

local progressTrack = make("Frame", {
	LayoutOrder = 10,
	Size = UDim2.new(1, 0, 0, 16),
	BackgroundColor3 = COLORS.bar,
	Parent = ipoPage,
})
round(progressTrack, 8)
local progressFill = make("Frame", {
	Size = UDim2.fromScale(0, 1),
	BackgroundColor3 = COLORS.gold,
	Parent = progressTrack,
})
round(progressFill, 8)

local rewardCard = makeCard(ipoPage, 20, "🎁", false)
rewardCard.name.Text = "What you get"
local resetCard = makeCard(ipoPage, 21, "🔄", false)
resetCard.name.Text = "What resets"
resetCard.desc.Text = "Cash, garage upgrades and the green pad, eggs in incubators, the HR Department, and your valuation (for the next IPO)."
local keepCard = makeCard(ipoPage, 22, "🔒", false)
keepCard.name.Text = "What you keep"
keepCard.desc.Text = "Employees, game passes, Luck Boost, Instant Hatches and shields, your Shares, IPO shop perks and your IPO count."

-- Right under the progress bar, so it's visible without scrolling (the confirm screen shows the full deal)
local goButton = make("TextButton", {
	LayoutOrder = 11,
	Size = UDim2.new(1, 0, 0, 56),
	BackgroundColor3 = COLORS.disabled,
	Font = Enum.Font.GothamBold,
	Text = "",
	TextColor3 = COLORS.text,
	Parent = ipoPage,
})
round(goButton, 12)
fitText(goButton, 24)

table.insert(refreshers, function()
	local info = stageInfo()
	local count = ipoCount()
	stageLine.Text = string.format("%s %s · Valuation %s", info.stage.icon, info.stage.name, ShopConfig.formatCash(valuation()))
	for i, stage in ipairs(IpoConfig.Stages) do
		local needed = IpoConfig.stageValuation(i, count)
		local mark = i < info.index and "✅" or (i == info.index and "▶️" or "🔒")
		local color = i <= info.index and "#FFC83C" or "#9096A5"
		stageRows[i].Text = string.format('%s <font color="%s">%s %s</font>  %s', mark, color, stage.icon, stage.name, IpoConfig.formatShort(needed))
	end
	progressFill.Size = UDim2.fromScale(info.progress, 1)

	local shares = IpoConfig.sharesFor(valuation(), count, sharesPassMultiplier())
	local before, after = IpoConfig.multiplier(count), IpoConfig.multiplier(count + 1)
	rewardCard.desc.Text = string.format("IPO #%d: 📜 +%d Shares, income multiplier %s → %s (forever).%s",
		count + 1, info.ready and shares or IpoConfig.sharesFor(IpoConfig.ipoValuation(count), count, sharesPassMultiplier()),
		IpoConfig.formatMultiplier(before), IpoConfig.formatMultiplier(after),
		info.ready and "\nWait longer for more Shares: they grow with your valuation." or "")

	if not info.ready then
		setButton(goButton, "Reach IPO-ready (" .. IpoConfig.formatShort(info.to) .. ") to go public", COLORS.disabled, false)
	elseif cooldownLeft() > 0 then
		setButton(goButton, "The market reopens in " .. math.ceil(cooldownLeft()) .. "s", COLORS.disabled, false)
	else
		setButton(goButton, "🔔 GO PUBLIC", COLORS.gold, true)
	end
end)

-- Two-step confirm: the button opens this screen with the exact deal, then "Yes" sends it
local confirm = make("Frame", {
	Name = "Confirm",
	Size = UDim2.fromScale(1, 1),
	BackgroundColor3 = COLORS.panel,
	Visible = false,
	ZIndex = 5,
	Parent = window,
})
round(confirm, 14)
local confirmText = make("TextLabel", {
	Position = UDim2.fromScale(0, 0),
	Size = UDim2.new(1, 0, 1, -70),
	BackgroundTransparency = 1,
	Font = Enum.Font.GothamBold,
	Text = "",
	RichText = true,
	TextColor3 = COLORS.text,
	TextWrapped = true,
	ZIndex = 6,
	Parent = confirm,
})
fitText(confirmText, 22)
local cancelButton = make("TextButton", {
	AnchorPoint = Vector2.new(0, 1),
	Position = UDim2.new(0, 0, 1, 0),
	Size = UDim2.new(0.5, -6, 0, 58),
	BackgroundColor3 = COLORS.disabled,
	Font = Enum.Font.GothamBold,
	Text = "Not yet",
	TextColor3 = COLORS.text,
	ZIndex = 6,
	Parent = confirm,
})
round(cancelButton, 12)
fitText(cancelButton, 22)
local yesButton = make("TextButton", {
	AnchorPoint = Vector2.new(1, 1),
	Position = UDim2.new(1, 0, 1, 0),
	Size = UDim2.new(0.5, -6, 0, 58),
	BackgroundColor3 = COLORS.gold,
	Font = Enum.Font.GothamBold,
	Text = "Yes, go public!",
	TextColor3 = COLORS.panel,
	ZIndex = 6,
	Parent = confirm,
})
round(yesButton, 12)
fitText(yesButton, 22)

local confirmFor -- the IPO number on the confirm screen
local confirmToken = 0
local function closeConfirm()
	confirm.Visible = false
	confirmFor = nil
end

goButton.Activated:Connect(function()
	local info = stageInfo()
	if not info.ready or cooldownLeft() > 0 then return end
	local count = ipoCount()
	confirmFor = count + 1
	local shares = IpoConfig.sharesFor(valuation(), count, sharesPassMultiplier())
	confirmText.Text = string.format(
		'Go public with IPO #%d?\n\n<font color="#FFC83C">You get: 📜 %d Shares and %s income forever</font>\n\n'
			.. '<font color="#FF8C8C">Resets: your %s Cash, garage upgrades, eggs in incubators and HR Department</font>\n\n'
			.. "Employees, passes, boosts, shields and perks stay.",
		confirmFor, shares, IpoConfig.formatMultiplier(IpoConfig.multiplier(count + 1)),
		ShopConfig.formatCash((player:FindFirstChild("leaderstats") and player.leaderstats.Cash.Value) or 0))
	confirm.Visible = true
	confirmToken += 1
	local myToken = confirmToken
	task.delay(CONFIRM_SECONDS, function()
		if confirmToken == myToken then
			closeConfirm()
		end
	end)
end)

cancelButton.Activated:Connect(closeConfirm)

yesButton.Activated:Connect(function()
	local number = confirmFor
	if not number then return end
	closeConfirm()
	request("GoPublic", number)
end)

-- Shares Shop tab -------------------------------------------------------

local sharesPage = tabPages["Shares Shop"]
local sharesLine = makeLine(sharesPage, 0, COLORS.gold)
table.insert(refreshers, function()
	sharesLine.Text = "📜 You have " .. attr("IpoShares") .. " Shares. Perks are permanent: they survive every IPO."
end)

for i, perk in ipairs(IpoConfig.Perks) do
	local parts = makeCard(sharesPage, i, perk.icon)
	parts.button.Activated:Connect(function()
		request("BuyPerk", perk.key)
	end)
	table.insert(refreshers, function()
		local level = attr("IpoPerk_" .. perk.key)
		local maxLevel = #perk.costs
		parts.name.Text = string.format("%s  <font color=\"#B9BECD\">Lv %d/%d</font>", perk.name, level, maxLevel)
		local now = level > 0 and ("Now " .. perkEffectText(perk, level)) or "Not bought yet"
		if level >= maxLevel then
			parts.desc.Text = perk.description .. "\n" .. now .. " (max)"
			setButton(parts.button, "MAX", COLORS.disabled, false)
		else
			parts.desc.Text = perk.description .. "\n" .. now .. " · next level: " .. perkEffectText(perk, level + 1)
			local cost = perk.costs[level + 1]
			setButton(parts.button, "📜 " .. cost, attr("IpoShares") >= cost and COLORS.buy or COLORS.disabled, true)
		end
	end)
end

-- Leaderboard tab -------------------------------------------------------

local boardPage = tabPages.Leaderboard
local boardLine = makeLine(boardPage, 0, COLORS.gold)
boardLine.Text = "Startups in this server: most IPOs first, then the best valuation."
local boardRows = {}

local function rowFor(index)
	local row = boardRows[index]
	if row then return row end
	row = makeLine(boardPage, index, COLORS.text, 34)
	row.BackgroundColor3 = COLORS.card
	row.BackgroundTransparency = 0
	round(row, 10)
	make("UIPadding", { PaddingLeft = UDim.new(0, 10), PaddingRight = UDim.new(0, 10), Parent = row })
	boardRows[index] = row
	return row
end

table.insert(refreshers, function()
	local list = Players:GetPlayers()
	table.sort(list, function(a, b)
		local ca, cb = a:GetAttribute("IpoCount") or 0, b:GetAttribute("IpoCount") or 0
		if ca ~= cb then return ca > cb end
		return (a:GetAttribute("IpoBest") or 0) > (b:GetAttribute("IpoBest") or 0)
	end)
	for i, other in ipairs(list) do
		local row = rowFor(i)
		row.Visible = true
		local you = other == player and ' <font color="#FFC83C">(you)</font>' or ""
		row.Text = string.format("#%d  %s%s  ·  🔔 %d IPOs  ·  best %s", i, other.DisplayName, you,
			other:GetAttribute("IpoCount") or 0, IpoConfig.formatShort(other:GetAttribute("IpoBest") or 0))
	end
	for i = #list + 1, #boardRows do
		boardRows[i].Visible = false
	end
end)

-- Phones: shorter header on short screens, narrower buttons on narrow screens
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
	for _, parts in ipairs(cardParts) do
		local textWidth = parts.button and (-textX - buttonWidth - 16) or (-textX - 8)
		parts.card.Size = UDim2.new(1, 0, 0, narrow and 96 or 84)
		parts.icon.Size = UDim2.fromOffset(iconSize, iconSize)
		parts.name.Position = UDim2.new(0, textX, 0, 8)
		parts.name.Size = UDim2.new(1, textWidth, 0, 22)
		parts.desc.Position = UDim2.new(0, textX, 0, 32)
		parts.desc.Size = UDim2.new(1, textWidth, 1, -38)
		if parts.button then
			parts.button.Size = UDim2.fromOffset(buttonWidth, 48)
		end
	end
end

-- HUD -------------------------------------------------------------------

local pulse -- the IPO button glows while you can go public
local function refreshHud()
	local info = stageInfo()
	if info.ready then
		hudStage.Text = "🔔 IPO-ready! Tap to go public"
	else
		hudStage.Text = string.format("%s %s → %s", info.stage.icon, info.stage.name, IpoConfig.Stages[info.index + 1].name)
	end
	hudFill.Size = UDim2.fromScale(info.progress, 1)
	hudInfo.Text = string.format("%s / %s · %s · 📜 %d", IpoConfig.formatShort(valuation()),
		IpoConfig.formatShort(info.to), IpoConfig.formatMultiplier(IpoConfig.multiplier(ipoCount())), attr("IpoShares"))
	ipoButton.Text = info.ready and "🔔\nIPO!" or "📈\nIPO"
	if info.ready and not pulse then
		pulse = TweenService:Create(buttonStroke, TweenInfo.new(0.6, Enum.EasingStyle.Sine, Enum.EasingDirection.InOut, -1, true),
			{ Color = COLORS.gold, Transparency = 0 })
		pulse:Play()
	elseif not info.ready and pulse then
		pulse:Cancel()
		pulse = nil
		buttonStroke.Color = Color3.new(0, 0, 0)
		buttonStroke.Transparency = 0.5
	end
end

-- Celebration when an IPO goes through
local banner = make("TextLabel", {
	Name = "IpoBanner",
	AnchorPoint = Vector2.new(0.5, 0.5),
	Position = UDim2.fromScale(0.5, 0.35),
	Size = UDim2.new(0.8, 0, 0, 110),
	BackgroundColor3 = COLORS.panel,
	BackgroundTransparency = 0.05,
	Font = Enum.Font.GothamBold,
	RichText = true,
	Text = "",
	TextColor3 = COLORS.gold,
	TextWrapped = true,
	Visible = false,
	ZIndex = 20,
	Parent = front,
})
round(banner, 16)
fitText(banner, 32)
make("UISizeConstraint", { MaxSize = Vector2.new(560, 110), Parent = banner })
make("UIStroke", { Thickness = 3, Color = COLORS.gold, ApplyStrokeMode = Enum.ApplyStrokeMode.Border, Parent = banner })

-- Window: tabs, opening and closing -------------------------------------

local function refreshAll()
	refreshHud()
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

-- Only one window at a time (the shop, Recruiting and Poach windows do the same with "OpenPanel")
local function setOpen(open)
	window.Visible = open
	if open then
		playerGui:SetAttribute("OpenPanel", PANEL_NAME)
	else
		closeConfirm()
		if playerGui:GetAttribute("OpenPanel") == PANEL_NAME then
			playerGui:SetAttribute("OpenPanel", nil)
		end
	end
	-- Hide the phone joystick and jump button while a window is open
	GuiService.TouchControlsEnabled = playerGui:GetAttribute("OpenPanel") == nil
	refreshAll()
end

playerGui:GetAttributeChangedSignal("OpenPanel"):Connect(function()
	if window.Visible and playerGui:GetAttribute("OpenPanel") ~= PANEL_NAME then
		window.Visible = false
		closeConfirm()
	end
end)

ipoButton.Activated:Connect(function()
	setOpen(not window.Visible)
end)
hudBar.Activated:Connect(function()
	showTab("IPO")
	setOpen(true)
end)
closeButton.Activated:Connect(function()
	setOpen(false)
end)

ipoEvent.OnClientEvent:Connect(function(kind, info)
	if kind == "Open" then -- stepped on the gold IPO pad
		if not window.Visible then
			showTab("IPO")
			setOpen(true)
		end
	elseif kind == "Done" and typeof(info) == "table" then
		banner.Text = string.format("🎉 IPO #%d! 🎉\n📜 +%d Shares · %s income forever",
			info.number or 0, info.shares or 0, IpoConfig.formatMultiplier(info.multiplier or 1))
		banner.Visible = true
		task.delay(4, function()
			banner.Visible = false
		end)
		showTab("Shares Shop")
	end
end)

showTab("IPO")
applyLayout()
window:GetPropertyChangedSignal("AbsoluteSize"):Connect(applyLayout)
gui:GetPropertyChangedSignal("AbsoluteSize"):Connect(placeHud)
refreshAll()

-- Keeping it up to date -------------------------------------------------

-- The server changes these attributes (on us, and on other players for the leaderboard)
player.AttributeChanged:Connect(refreshAll)
local function watch(other)
	if other ~= player then
		other.AttributeChanged:Connect(function(name)
			if name == "IpoCount" or name == "IpoBest" then
				refreshAll()
			end
		end)
	end
end
for _, other in ipairs(Players:GetPlayers()) do
	watch(other)
end
Players.PlayerAdded:Connect(function(other)
	watch(other)
	refreshAll()
end)
Players.PlayerRemoving:Connect(function()
	task.defer(refreshAll)
end)

-- Cooldown countdown
while true do
	task.wait(1)
	if window.Visible then
		refreshAll()
	end
end
