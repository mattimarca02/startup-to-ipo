-- ShopClient: the Shop button and shop window (milestone 3).
-- Put this LocalScript in StarterPlayer > StarterPlayerScripts. It builds the screen by itself.
-- It only opens Roblox's purchase prompts. Everything is granted by ShopServer on the server.
-- The Office tab buys the garage upgrades: it sends only the upgrade's number, and the server decides.
-- Every size comes from ShopLayout (a ModuleScript in ReplicatedStorage, pure functions that tools/shop_ux_test.py
-- checks): the tabs in a rail on the left in landscape and in a row in portrait, 44 px header items and tap
-- targets, no text under 16 px. The tutorial finds its targets by name under ShopGui.Window: TabOffice ... TabDebug,
-- OfficePage ... DebugPage, Office1 ... Office6, BuyButton (every card's button), HelpButton and TutorialStrip.

local Players = game:GetService("Players")
local MarketplaceService = game:GetService("MarketplaceService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local GuiService = game:GetService("GuiService")
local TextService = game:GetService("TextService")
local TweenService = game:GetService("TweenService")

local ShopConfig = require(ReplicatedStorage:WaitForChild("ShopConfig"))
local ShopLayout = require(ReplicatedStorage:WaitForChild("ShopLayout")) -- the window's sizes (pure functions)
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
	strip = Color3.fromRGB(70, 58, 24), -- the tutorial's line at the window's bottom
	refusal = Color3.fromRGB(255, 120, 120), -- the server's "no" in the Office card (light, readable on a card)
	lock = Color3.fromRGB(150, 155, 170), -- the padlock on a locked rung
	skeleton = Color3.fromRGB(48, 51, 63), -- the gray rungs while the Office list loads
	bar = Color3.fromRGB(24, 26, 33), -- the hero's progress bar, empty part
}

local MIN_TEXT = ShopLayout.MIN_TEXT -- 16: nothing a player must read is smaller
local HELP_LINES = { -- the "How the shop works" card (HelpButton): three lines, no reward
	"Office: buy the upgrades in order with Cash. Each one adds Cash every second.",
	"The next upgrade's bar fills with your Cash. More Income fills it faster.",
	"Passes, Boosts and Cash cost Robux. Roblox asks you to confirm every purchase.",
}

local pending = {} -- item key -> token while its Roblox purchase prompt is open
local cards = {} -- refresh functions, one per card
local cardParts = {} -- the pieces of every card, laid out by layoutCard from ShopLayout.card
local measured = {} -- labels whose height follows their text (16 px, wrapped): label -> { extra, inset } in pixels
local incomeValue -- leaderstats.Income, used to preview cash pack sizes
local cashValue -- leaderstats.Cash, to show which upgrade you can afford
local cardWidth = 0 -- every card's width in pixels (ShopLayout's cardW for this screen)
local pagesHeight = 0 -- the pages' height in pixels (what a page shows without scrolling)
local layoutHooks = {} -- run at the end of every applyLayout (the Office page places its own rows)

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

-- Text shrinks to fit small phone screens but never grows past maxSize, and never goes under 16 px
local function fitText(inst, maxSize)
	inst.TextScaled = true
	make("UITextSizeConstraint", { MaxTextSize = maxSize, MinTextSize = MIN_TEXT, Parent = inst })
end

-- Text that stays at 16 px and wraps; its box is made as tall as the text (measured below)
local function fixedText(inst)
	inst.TextScaled = false
	inst.TextSize = MIN_TEXT
	inst.TextWrapped = true
end

-- How tall a 16 px text is when it wraps at this width (Roblox's own measure, so every box fits its text)
local function textHeight(text, font, width)
	if text == "" or width <= 0 then
		return 0
	end
	local ok, size = pcall(function()
		return TextService:GetTextSize(text, MIN_TEXT, font, Vector2.new(width, 10000))
	end)
	return ok and math.ceil(size.Y) or 2 * MIN_TEXT
end

-- How wide a 16 px text is on one line
local function textWidth(text, font)
	local ok, size = pcall(function()
		return TextService:GetTextSize(text, MIN_TEXT, font, Vector2.new(10000, 10000))
	end)
	return ok and math.ceil(size.X) or #text * MIN_TEXT
end

-- Puts inst on rectangle r (GUI pixels, from ShopLayout); origin = the rectangle of its parent
local function place(inst, r, origin)
	inst.Position = UDim2.fromOffset(r.x - (origin and origin.x or 0), r.y - (origin and origin.y or 0))
	inst.Size = UDim2.fromOffset(r.w, r.h)
end

local function setButton(button, text, color, clickable)
	button.Text = text
	button.BackgroundColor3 = color
	button.AutoButtonColor = clickable
end

-- Screen ----------------------------------------------------------------

-- Two layers, like PoachClient and IpoClient: the SHOP button sits with the HUD under every window (DisplayOrder -1),
-- while the shop window and its pop-up sit above every HUD button (DisplayOrder 5), so EGGS or TEAM never draws over
-- a tab (in landscape the HUD row and the tab rail share the top-left corner)
local hudGui = make("ScreenGui", {
	Name = "ShopHudGui",
	ResetOnSpawn = false,
	ZIndexBehavior = Enum.ZIndexBehavior.Sibling,
	DisplayOrder = -1,
	Parent = player:WaitForChild("PlayerGui"),
})
local gui = make("ScreenGui", {
	Name = "ShopGui",
	ResetOnSpawn = false, -- keep the shop as it was when your character respawns
	ZIndexBehavior = Enum.ZIndexBehavior.Sibling,
	DisplayOrder = 5,
	Parent = player:WaitForChild("PlayerGui"),
})
local playerGui = gui.Parent

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
	Parent = hudGui,
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
		if hudGui.AbsoluteSize.Y < 460 then
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
	hudGui:GetPropertyChangedSignal("AbsoluteSize"):Connect(place)
end
placeHudButton(shopButton, 1)

-- The pop-up message at the bottom center, only while the shop is closed (it would cover the window)
local toast = make("TextLabel", {
	Name = "Toast",
	AnchorPoint = Vector2.new(0.5, 1),
	Position = UDim2.new(0.5, 0, 1, -16), -- bottom middle, clear of the HUD buttons
	Size = UDim2.new(0.6, 0, 0, 48),
	BackgroundColor3 = COLORS.panel,
	BackgroundTransparency = 0.1,
	Font = Enum.Font.GothamBold,
	TextColor3 = COLORS.gold,
	TextWrapped = true, -- two lines at 16 px in its 48 px lane, rather than one line too small to read
	Visible = false,
	ZIndex = 10,
	Parent = gui,
})
round(toast, 12)
fitText(toast, 22)
make("UISizeConstraint", { MaxSize = Vector2.new(ShopLayout.TOAST_MAX_W, 48), Parent = toast })
local toastText = "" -- the toast's whole message: its label shows at most TOAST_LINES lines of it
local TOAST_LINES = 2 -- what its 48 px lane holds at 16 px (other pop-ups and the call tray use the lanes above)

-- A 16 px text cut to at most maxLines lines at this width: the text itself when it fits, else its longest start
-- (at a word when it can) followed by "...". The whole text stays for the window's status line.
local function clampLines(text, font, width, maxLines)
	local lineH = textHeight("Ag", font, 10000)
	local function fits(s)
		return textHeight(s, font, width) <= maxLines * lineH
	end
	if width <= 0 or fits(text) then
		return text
	end
	local starts = {}
	for position in utf8.codes(text) do
		table.insert(starts, position)
	end
	local function cut(k) -- the first k characters, without trailing spaces or punctuation, and "..."
		local head = k < #starts and string.sub(text, 1, starts[k + 1] - 1) or text
		return (string.gsub(head, "[%s%.,;:]+$", "")) .. "..."
	end
	local low, high = 0, #starts -- the longest start that fits, by halving (cut(0) is only "...")
	while low < high do
		local mid = math.ceil((low + high) / 2)
		if fits(cut(mid)) then
			low = mid
		else
			high = mid - 1
		end
	end
	local k = low
	local inWord = k > 0 and k < #starts and not string.find(string.sub(text, starts[k + 1], starts[k + 1]), "%s")
	local space = inWord and string.find(string.sub(text, 1, starts[k + 1] - 1), "%s[^%s]*$")
	if space and space > 1 then -- the cut is inside a word: end at the word before it
		local short = (string.gsub(string.sub(text, 1, space - 1), "[%s%.,;:]+$", "")) .. "..."
		if fits(short) then
			return short
		end
	end
	return cut(k)
end

-- The toast's text for its width now (0.6 of the screen, at most TOAST_MAX_W)
local function toastFace()
	return clampLines(toastText, toast.Font, math.min(gui.AbsoluteSize.X * 0.6, ShopLayout.TOAST_MAX_W), TOAST_LINES)
end

-- The window: every piece is placed by applyLayout from ShopLayout.layout
local window = make("Frame", {
	Name = "Window",
	BackgroundColor3 = COLORS.panel,
	Visible = false,
	Parent = gui,
})
round(window, 18)

local title = make("TextLabel", {
	Name = "Title",
	BackgroundTransparency = 1,
	Font = Enum.Font.GothamBold,
	Text = "Startup Shop",
	TextColor3 = COLORS.gold,
	TextXAlignment = Enum.TextXAlignment.Left,
	Parent = window,
})
fitText(title, 28)

-- "?": the "How the shop works" card (the tutorial's step list can take its place once it exists)
local helpButton = make("TextButton", {
	Name = "HelpButton",
	BackgroundColor3 = COLORS.tab,
	Font = Enum.Font.GothamBold,
	Text = "?",
	TextColor3 = COLORS.text,
	Parent = window,
})
round(helpButton, 10)
fitText(helpButton, 24)

local closeButton = make("TextButton", {
	Name = "CloseButton",
	BackgroundColor3 = COLORS.close,
	Font = Enum.Font.GothamBold,
	Text = "X",
	TextColor3 = COLORS.text,
	Parent = window,
})
round(closeButton, 10)
fitText(closeButton, 22)

-- The tabs: a rail in landscape, a row in portrait (it scrolls only on a window too small for them)
local tabBar = make("ScrollingFrame", {
	Name = "TabBar",
	BackgroundTransparency = 1,
	BorderSizePixel = 0,
	CanvasSize = UDim2.new(),
	ScrollBarThickness = 0,
	Parent = window,
})

local pages = make("Frame", {
	Name = "Pages",
	BackgroundTransparency = 1,
	Parent = window,
})

local tabNames = { "Office", "Passes", "Boosts", "Cash" }
if debugRemote then
	table.insert(tabNames, "Debug")
end
local tabButtons, tabPages = {}, {}
for i, name in ipairs(tabNames) do
	local tabButton = make("TextButton", {
		Name = "Tab" .. name,
		LayoutOrder = i,
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
		Name = name .. "Page",
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
	if name == "Office" then
		page.AutomaticCanvasSize = Enum.AutomaticSize.None -- the Office places its own rows (ShopLayout.stack) and canvas
	else
		make("UIListLayout", { Padding = UDim.new(0, 8), SortOrder = Enum.SortOrder.LayoutOrder, Parent = page })
	end
	make("UIPadding", { PaddingRight = UDim.new(0, ShopLayout.SCROLLBAR_ROOM), Parent = page }) -- room for the scrollbar
	tabPages[name] = page
end

-- The bottom slot: the tutorial's line, or a message while the shop is open. Each takes its height from the pages
-- (never covers a card). The tutorial's line shows while PlayerGui's "TutorialBanner" attribute holds a text
-- (TutorialClient writes it); unset, it is hidden and takes no room.
local tutorialStrip = make("TextLabel", {
	Name = "TutorialStrip",
	BackgroundColor3 = COLORS.strip,
	Font = Enum.Font.GothamBold,
	Text = "",
	TextColor3 = COLORS.gold,
	TextWrapped = true,
	Visible = false,
	ZIndex = 3,
	Parent = window,
})
round(tutorialStrip, 10)
fitText(tutorialStrip, 18)

local statusLine = make("TextLabel", {
	Name = "StatusLine",
	BackgroundColor3 = COLORS.card,
	Font = Enum.Font.GothamBold,
	Text = "",
	TextColor3 = COLORS.gold,
	TextTruncate = Enum.TextTruncate.AtEnd,
	Visible = false,
	ZIndex = 4,
	Parent = window,
})
round(statusLine, 10)
fixedText(statusLine)

-- The "How the shop works" card: over the pages (never the header or the tabs), one screen, a Back button
local helpCard = make("ScrollingFrame", {
	Name = "HelpCard",
	BackgroundColor3 = COLORS.card,
	BorderSizePixel = 0,
	CanvasSize = UDim2.new(),
	ScrollingDirection = Enum.ScrollingDirection.Y,
	ScrollBarThickness = 0,
	Visible = false,
	ZIndex = 5,
	Parent = window,
})
round(helpCard, 12)
local helpTitle = make("TextLabel", {
	Name = "HelpTitle",
	BackgroundTransparency = 1,
	Font = Enum.Font.GothamBold,
	Text = "How the shop works",
	TextColor3 = COLORS.gold,
	TextXAlignment = Enum.TextXAlignment.Left,
	Parent = helpCard,
})
fitText(helpTitle, 22)
local helpBack = make("TextButton", {
	Name = "HelpBack",
	BackgroundColor3 = COLORS.tab,
	Font = Enum.Font.GothamBold,
	Text = "Back",
	TextColor3 = COLORS.text,
	Parent = helpCard,
})
round(helpBack, 10)
fitText(helpBack, 20)
local helpLines = {}
for i, line in ipairs(HELP_LINES) do
	local label = make("TextLabel", {
		Name = "HelpLine" .. i,
		BackgroundTransparency = 1,
		Font = Enum.Font.Gotham,
		Text = line,
		TextColor3 = COLORS.text,
		TextXAlignment = Enum.TextXAlignment.Left,
		TextYAlignment = Enum.TextYAlignment.Top,
		Parent = helpCard,
	})
	fixedText(label)
	helpLines[i] = label
end

-- One row in the shop: icon, name, description, and a button on the right (cardName: the card's Name, for the
-- tutorial; the button is always "BuyButton")
local function makeCard(page, order, icon, name, cardName)
	local card = make("Frame", {
		Name = cardName or "Card",
		LayoutOrder = order,
		Size = UDim2.new(1, 0, 0, 84),
		BackgroundColor3 = COLORS.card,
		Parent = page,
	})
	round(card, 12)

	local iconLabel = make("TextLabel", {
		Name = "Icon",
		BackgroundTransparency = 1,
		Font = Enum.Font.GothamBold,
		Text = icon,
		TextColor3 = COLORS.text,
		Parent = card,
	})
	fitText(iconLabel, 40)

	local nameLabel = make("TextLabel", {
		Name = "ItemName",
		BackgroundTransparency = 1,
		Font = Enum.Font.GothamBold,
		Text = name,
		TextColor3 = COLORS.text,
		TextWrapped = true,
		TextXAlignment = Enum.TextXAlignment.Left,
		Parent = card,
	})
	fitText(nameLabel, 20)

	local descLabel = make("TextLabel", {
		Name = "Description",
		BackgroundTransparency = 1,
		Font = Enum.Font.Gotham,
		Text = "",
		TextColor3 = COLORS.subtext,
		TextXAlignment = Enum.TextXAlignment.Left,
		TextYAlignment = Enum.TextYAlignment.Top,
		Parent = card,
	})
	fixedText(descLabel)

	local button = make("TextButton", {
		Name = "BuyButton",
		BackgroundColor3 = COLORS.buy,
		Font = Enum.Font.GothamBold,
		Text = "",
		TextColor3 = COLORS.text,
		TextWrapped = true,
		Parent = card,
	})
	round(button, 10)
	fitText(button, 20)

	local parts = { card = card, icon = iconLabel, name = nameLabel, desc = descLabel, button = button, seen = {} }
	table.insert(cardParts, parts)
	return descLabel, button, parts
end

-- A factual badge on a card, hidden until its refresh shows it (BEST VALUE: computed from ShopConfig)
local function addBadge(parts, text)
	local badge = make("TextLabel", {
		Name = "Badge",
		BackgroundColor3 = COLORS.gold,
		Font = Enum.Font.GothamBold,
		Text = text,
		TextColor3 = COLORS.panel,
		Visible = false,
		Parent = parts.card,
	})
	round(badge, 6)
	fixedText(badge)
	parts.badge = badge
	return badge
end

-- A card's pieces for the current width; its texts are measured again only when they (or the width) changed
local function layoutCard(parts)
	local seen = parts.seen
	local badgeW = 0
	if parts.badge and parts.badge.Visible then
		if seen.badgeText ~= parts.badge.Text then
			seen.badgeText, seen.badgeTextW = parts.badge.Text, textWidth(parts.badge.Text, parts.badge.Font)
		end
		badgeW = seen.badgeTextW + 16
	end
	if seen.name ~= parts.name.Text or seen.desc ~= parts.desc.Text or seen.width ~= cardWidth or seen.badgeW ~= badgeW then
		local nameW, descW = ShopLayout.cardWidths(cardWidth, badgeW)
		seen.name, seen.desc, seen.width, seen.badgeW = parts.name.Text, parts.desc.Text, cardWidth, badgeW
		seen.nameH = textHeight(seen.name, parts.name.Font, nameW)
		seen.descH = textHeight(seen.desc, parts.desc.Font, descW)
	end
	local C = ShopLayout.card(cardWidth, seen.nameH, seen.descH, badgeW)
	parts.card.Size = UDim2.new(1, 0, 0, C.height)
	place(parts.icon, C.icon)
	place(parts.name, C.name)
	place(parts.desc, C.desc)
	place(parts.button, C.button)
	if C.badge then
		place(parts.badge, C.badge)
	end
end

-- A label as tall as its 16 px text, at the page's width (the Debug status, the Office error line)
local function measureLabel(label)
	local m = measured[label]
	if m then
		label.Size = UDim2.new(1, 0, 0, textHeight(label.Text, label.Font, cardWidth - m.inset) + m.extra)
	end
end

local function fitLabel(label, extra, inset)
	fixedText(label)
	measured[label] = { extra = extra or 0, inset = inset or 0 }
	measureLabel(label)
end

-- Layout ----------------------------------------------------------------

local statusText -- the message in the window's status line now (nil: none)
local helpOpen = false

-- PlayerGui's "TutorialBanner": a text the tutorial wants shown, or nil
local function tutorialBanner()
	local value = playerGui:GetAttribute("TutorialBanner")
	if typeof(value) == "string" and value ~= "" then
		return value
	end
	return nil
end

local function guiInset()
	local ok, topLeft = pcall(function()
		return GuiService:GetGuiInset()
	end)
	return ok and typeof(topLeft) == "Vector2" and topLeft.Y or 0
end

-- Every size, from ShopLayout. Runs again whenever the screen size, the tutorial's line or a message changes.
local function applyLayout()
	local size = gui.AbsoluteSize
	local inset = guiInset()
	local L = ShopLayout.layout(size.X, size.Y, inset, #tabNames, 0)
	local banner = tutorialBanner()
	local bottomH = 0
	if banner then
		bottomH = L.stripH
	end
	if statusText then
		bottomH = math.max(bottomH, math.clamp(textHeight(statusText, statusLine.Font, L.pages.w - 16) + 12, L.stripH, 72))
	end
	if bottomH > 0 then
		L = ShopLayout.layout(size.X, size.Y, inset, #tabNames, bottomH)
	end

	local frame = L.window
	place(window, frame)
	place(title, L.title, frame)
	place(helpButton, L.help, frame)
	place(closeButton, L.close, frame)
	place(tabBar, L.tabBar, frame)
	tabBar.ScrollingDirection = L.rail and Enum.ScrollingDirection.Y or Enum.ScrollingDirection.X
	tabBar.CanvasSize = L.rail and UDim2.fromOffset(0, L.tabCanvas) or UDim2.fromOffset(L.tabCanvas, 0)
	tabBar.ScrollBarThickness = L.tabScrolls and 4 or 0
	for i, name in ipairs(tabNames) do
		place(tabButtons[name], L.tabs[i], L.tabBar)
	end
	place(pages, L.pages, frame)

	tutorialStrip.Text = banner or ""
	tutorialStrip.Visible = banner ~= nil and statusText == nil
	statusLine.Text = statusText or ""
	statusLine.Visible = statusText ~= nil
	if L.bottom then
		place(tutorialStrip, L.bottom, frame)
		place(statusLine, L.bottom, frame)
	end

	place(helpCard, L.helpCard, frame)
	local heights = {}
	for i, label in ipairs(helpLines) do
		heights[i] = textHeight(label.Text, label.Font, ShopLayout.helpTextWidth(L.helpCard.w))
	end
	local H = ShopLayout.helpCard(L.helpCard.w, L.helpCard.h, heights)
	place(helpTitle, H.title)
	place(helpBack, H.back)
	for i, label in ipairs(helpLines) do
		place(label, H.lines[i])
	end
	helpCard.CanvasSize = UDim2.fromOffset(0, H.height)
	helpCard.ScrollBarThickness = H.fits and 0 or 6

	cardWidth = L.cardW
	pagesHeight = L.pages.h
	for _, parts in ipairs(cardParts) do
		layoutCard(parts)
	end
	for label in pairs(measured) do
		measureLabel(label)
	end
	for _, hook in ipairs(layoutHooks) do
		hook()
	end
	if toast.Visible then
		toast.Text = toastFace() -- cut again for the new width
	end
end

-- Behaviour -------------------------------------------------------------

local function refreshAll()
	for _, refresh in ipairs(cards) do
		refresh()
	end
	for _, parts in ipairs(cardParts) do
		layoutCard(parts)
	end
end

local toastToken = 0
local function showToast(text)
	toastToken += 1
	local myToken = toastToken
	toastText = text
	toast.Text = toastFace()
	toast.Visible = true
	task.delay(3.5, function()
		if toastToken == myToken then
			toast.Visible = false
		end
	end)
end

-- The window's own status line (3.5 s, like the toast); it takes its room from the pages while it shows
local statusToken = 0
local function showStatus(text)
	statusToken += 1
	local myToken = statusToken
	statusText = text
	applyLayout()
	task.delay(3.5, function()
		if statusToken == myToken then
			statusText = nil
			applyLayout()
		end
	end)
end

-- Every message goes here: in the window while the shop is open, the pop-up at the bottom while it is closed
local function showMessage(text)
	if window.Visible then
		showStatus(text)
	else
		showToast(text)
	end
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
		showMessage("Couldn't open the purchase. Please try again.")
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
	local desc, button = makeCard(tabPages.Passes, i, pass.icon, pass.name, pass.key)
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
		local desc, button, parts = makeCard(page, i, product.icon, product.name, product.key)
		button.Activated:Connect(function()
			promptPurchase(product, false)
		end)
		-- BEST VALUE: the Cash pack with the most minutes of Income per Robux, among the ones on sale (from ShopConfig)
		local bestBadge = product.effect.incomeMinutes and addBadge(parts, "BEST VALUE")
		table.insert(cards, function()
			if bestBadge then
				bestBadge.Visible = ShopLayout.bestValue(ShopConfig.Products, function(item)
					return ShopConfig.isForSale(item, randomRestricted())
				end) == product.key
			end
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

-- Office tab: the six garage upgrades, bought in order (docs/SHOP_UX_PROPOSAL.md 3.2). The list (name, price,
-- income) comes from the server, and a Buy tap sends only the upgrade's number: the server checks the order, the Cash
-- and everything else, and answers with a short message. ShopLayout.ladder decides what every rung shows: the owned
-- ones fold into a summary row, the next one is the hero card with a progress bar, the others are locked ("Unlocks
-- after ..."). Only the hero offers Buy, and only when the Cash is there: "Need $X more" sends nothing. No rung ever
-- asks for a confirmation (decided by the owner). The rows are placed top to bottom by ShopLayout.stack.
local officePage = tabPages.Office -- no UIListLayout: its canvas is set here, so the hero can scroll into view at once
local officeBusy = false
local office = {
	list = nil, -- the server's list ({ name, cost, income, icon }), once it arrived
	failed = false, -- all 5 tries failed: the sentence and the Retry button
	fetching = false,
	rungs = {}, -- Office1 ... Office6: the pieces of each rung
	unfolded = false, -- the owned rungs shown under the summary row (tap the row)
	bought = nil, -- the upgrade just bought: its card stays the hero a moment ("Bought!")
	shownHero = nil, -- the hero on screen now (a new one scrolls into view)
	reveal = false, -- scroll the hero into view at the next placing: only after a buy or a hero change (a Retry is one)
	buying = nil, -- the upgrade whose buy request runs now
	actionRemote = nil,
}

local function officeText(parent, name, font, color, maxSize)
	local label = make("TextLabel", {
		Name = name,
		BackgroundTransparency = 1,
		Font = font,
		Text = "",
		TextColor3 = color,
		TextWrapped = true,
		TextXAlignment = Enum.TextXAlignment.Left,
		Parent = parent,
	})
	fitText(label, maxSize)
	return label
end

-- A check mark (owned) and a padlock (locked), drawn with frames: no emoji, no image
local function makeBadge(parent)
	local badge = make("Frame", { Name = "Badge", BackgroundTransparency = 1, ZIndex = 2, Parent = parent })
	local check = make("Frame", { Name = "Check", Size = UDim2.fromScale(1, 1), BackgroundColor3 = COLORS.buy, ZIndex = 2, Parent = badge })
	round(check, 10)
	for _, stroke in ipairs({ { 0.37, 0.58, 0.32, 45 }, { 0.6, 0.47, 0.55, -45 } }) do
		make("Frame", {
			AnchorPoint = Vector2.new(0.5, 0.5),
			Position = UDim2.fromScale(stroke[1], stroke[2]),
			Size = UDim2.fromScale(stroke[3], 0.14),
			Rotation = stroke[4],
			BackgroundColor3 = COLORS.text,
			BorderSizePixel = 0,
			ZIndex = 3,
			Parent = check,
		})
	end
	local lock = make("Frame", { Name = "Lock", Size = UDim2.fromScale(1, 1), BackgroundTransparency = 1, ZIndex = 2, Parent = badge })
	local shackle = make("Frame", {
		Name = "Shackle",
		AnchorPoint = Vector2.new(0.5, 0),
		Position = UDim2.fromScale(0.5, 0),
		Size = UDim2.fromScale(0.56, 0.6),
		BackgroundTransparency = 1,
		ZIndex = 2,
		Parent = lock,
	})
	round(shackle, 6)
	make("UIStroke", { Thickness = 2, Color = COLORS.lock, Parent = shackle })
	local body = make("Frame", {
		Name = "Body",
		AnchorPoint = Vector2.new(0.5, 1),
		Position = UDim2.fromScale(0.5, 1),
		Size = UDim2.fromScale(0.84, 0.56),
		BackgroundColor3 = COLORS.lock,
		BorderSizePixel = 0,
		ZIndex = 3,
		Parent = lock,
	})
	round(body, 3)
	return badge, check, lock
end

-- While "Upgrades" is asked: three gray rungs
local skeletons = {}
for i = 1, 3 do
	local row = make("Frame", { Name = "OfficeSkeleton" .. i, BackgroundColor3 = COLORS.skeleton, Parent = officePage })
	round(row, 12)
	local dot = make("Frame", { Name = "Dot", Position = UDim2.fromOffset(8, 8), Size = UDim2.fromOffset(48, 48), BackgroundColor3 = COLORS.tab, BorderSizePixel = 0, Parent = row })
	round(dot, 12)
	local line = make("Frame", { Name = "Line", Position = UDim2.fromOffset(64, 18), Size = UDim2.new(0.45, 0, 0, 14), BackgroundColor3 = COLORS.tab, BorderSizePixel = 0, Parent = row })
	round(line, 7)
	skeletons[i] = row
end

-- After 5 failed tries: the sentence and a Retry button (the same 5 tries again)
local officeError = make("TextLabel", {
	Name = "OfficeError",
	BackgroundTransparency = 1,
	Font = Enum.Font.GothamBold,
	Text = "The office upgrades aren't available right now.",
	TextColor3 = COLORS.subtext,
	Visible = false,
	Parent = officePage,
})
fixedText(officeError)
local retryButton = make("TextButton", {
	Name = "RetryButton",
	BackgroundColor3 = COLORS.tab,
	Font = Enum.Font.GothamBold,
	Text = "Retry",
	TextColor3 = COLORS.text,
	Visible = false,
	Parent = officePage,
})
round(retryButton, 10)
fitText(retryButton, 20)

-- The owned rungs, folded into one row: "3 of 6 bought" and what they earn; a tap shows or hides them
local summary = make("TextButton", {
	Name = "OfficeSummary",
	BackgroundColor3 = COLORS.card,
	Text = "",
	TextSize = MIN_TEXT,
	Visible = false,
	Parent = officePage,
})
round(summary, 12)
local summaryBadge, _, summaryLock = makeBadge(summary)
summaryLock.Visible = false
local summaryTitle = officeText(summary, "SummaryTitle", Enum.Font.GothamBold, COLORS.text, 22)
local summaryInfo = officeText(summary, "SummaryInfo", Enum.Font.Gotham, COLORS.subtext, 18)
local summaryToggle = officeText(summary, "SummaryToggle", Enum.Font.GothamBold, COLORS.subtext, 18)
summaryToggle.TextXAlignment = Enum.TextXAlignment.Center

-- All six bought: a gold banner, a hint and no button
local banner = make("Frame", { Name = "OfficeComplete", BackgroundColor3 = COLORS.gold, Visible = false, Parent = officePage })
round(banner, 12)
local bannerTitle = officeText(banner, "BannerTitle", Enum.Font.GothamBold, COLORS.panel, 24)
local bannerInfo = officeText(banner, "BannerInfo", Enum.Font.GothamBold, COLORS.panel, 18)

local function ladderNow()
	local owned = {}
	for i = 1, #office.list do
		owned[i] = player:GetAttribute("Upgrade" .. i) == true
	end
	-- The server may mark the upgrade as owned before its answer arrives: while the request runs, that rung stays the
	-- hero (it says Bought!) instead of folding for a moment and coming back with the answer (the page would jump twice)
	local bought = office.bought
	if bought == nil and officeBusy and office.buying and owned[office.buying] then
		bought = office.buying
	end
	return ShopLayout.ladder(office.list, owned, cashValue and cashValue.Value or 0, incomeValue and incomeValue.Value or 0,
		ShopConfig.formatCash, bought, officeBusy)
end

-- The hero scrolls into view (just enough to show it whole, never past its top). Only after a buy or a hero change:
-- a message line, the tutorial's strip, a tab or a new screen size never move the page (decided by the owner)
local function revealHero()
	if office.shownHero and office.heroY then
		officePage.CanvasPosition = Vector2.new(0, ShopLayout.revealScroll(office.heroY, office.heroH, pagesHeight, office.total or 0))
	end
end

-- One rung as the ladder says: owned (folded), the hero, or locked (dimmed, a padlock, "Unlocks after ...")
local function showRung(parts, row, hero, width)
	local isHero = row.state == "next"
	local locked = row.state == "locked"
	local R = isHero and ShopLayout.hero(width) or ShopLayout.officeRow(width, row.state)
	parts.height = R.height
	place(parts.icon, R.icon)
	place(parts.name, R.name)
	place(parts.info, R.info)
	parts.card.BackgroundTransparency = locked and 0.45 or 0
	parts.icon.TextTransparency = locked and 0.55 or 0
	parts.name.TextColor3 = locked and COLORS.subtext or COLORS.text
	parts.badge.Visible = not isHero
	if not isHero then
		place(parts.badge, R.badge)
		parts.check.Visible = row.state == "owned"
		parts.lock.Visible = locked
	end
	parts.bar.Visible = isHero
	parts.progress.Visible = isHero
	local message = parts.statusText
	if isHero then
		parts.info.Text = hero.info
		place(parts.bar, R.bar)
		parts.fill.Size = UDim2.fromScale(hero.fill, 1)
		parts.progress.Text = hero.progress
		place(parts.progress, R.progress)
		place(parts.time, R.time)
		place(parts.status, R.status)
		parts.time.Text = hero.time or ""
		parts.time.TextXAlignment = R.narrow and Enum.TextXAlignment.Left or Enum.TextXAlignment.Right
		parts.time.TextYAlignment = Enum.TextYAlignment.Top
		parts.time.Visible = hero.time ~= nil and not (message and R.statusSharesTime)
		parts.status.Text = message or ""
		parts.status.TextColor3 = parts.statusColor or COLORS.refusal
		parts.status.TextYAlignment = Enum.TextYAlignment.Top
		parts.status.Visible = message ~= nil
	else
		parts.info.Text = row.info
		parts.time.Visible = false
		parts.status.Visible = false
	end
	local button = parts.button
	if row.state == "owned" then
		setButton(button, "Owned", COLORS.owned, false)
	elseif isHero then
		setButton(button, hero.button, COLORS[hero.color], hero.action == "buy")
	end
	-- A locked rung offers no Buy: only the hero does (and only with the Cash there)
	button.Visible = row.state ~= "locked"
	if button.Visible then
		place(button, R.button)
	end
end

-- Places the Office page: loading rungs, or the error and Retry, or the banner, the summary and the rungs
local function refreshOffice()
	local width = cardWidth
	local rowH = ShopLayout.officeRow(width, "locked").height
	local items = {} -- what shows, top to bottom: { inst = ..., height = ..., width = (fixed, or the page's) }
	local loading = office.list == nil and not office.failed
	for _, row in ipairs(skeletons) do
		row.Visible = loading
		if loading then
			table.insert(items, { inst = row, height = rowH })
		end
	end
	officeError.Visible = office.failed
	retryButton.Visible = office.failed
	if office.failed then
		table.insert(items, { inst = officeError, height = textHeight(officeError.Text, officeError.Font, width) + 8 })
		table.insert(items, { inst = retryButton, height = ShopLayout.BUTTON_H, width = 120 })
	end
	local S = office.list and ladderNow()
	banner.Visible = S ~= nil and S.complete
	summary.Visible = S ~= nil and S.summary ~= nil
	office.heroY = nil
	if S then
		if S.banner then
			local R = ShopLayout.officeRow(width, "banner")
			bannerTitle.Text, bannerInfo.Text = S.banner.title, S.banner.info
			place(bannerTitle, R.name)
			place(bannerInfo, R.info)
			table.insert(items, { inst = banner, height = R.height })
		end
		if S.summary then
			local R = ShopLayout.officeRow(width, "summary")
			summaryTitle.Text, summaryInfo.Text = S.summary.title, S.summary.info
			summaryToggle.Text = office.unfolded and "Hide" or "Show"
			place(summaryBadge, R.icon)
			place(summaryTitle, R.name)
			place(summaryInfo, R.info)
			place(summaryToggle, R.button)
			table.insert(items, { inst = summary, height = R.height })
		end
		for i, parts in ipairs(office.rungs) do
			local row = S.rows[i]
			showRung(parts, row, S.hero, width)
			local shown = row.state ~= "owned" or office.unfolded
			parts.card.Visible = shown
			if shown then
				table.insert(items, { inst = parts.card, height = parts.height, hero = row.state == "next" })
			end
		end
	end
	local heights = {}
	for k, item in ipairs(items) do
		heights[k] = item.height
	end
	local ys, total = ShopLayout.stack(heights, ShopLayout.OFFICE_GAP)
	for k, item in ipairs(items) do
		item.inst.Position = UDim2.fromOffset(0, ys[k])
		item.inst.Size = item.width and UDim2.fromOffset(item.width, item.height) or UDim2.new(1, 0, 0, item.height)
		if item.hero then
			office.heroY, office.heroH = ys[k], item.height
		end
	end
	office.total = total
	officePage.CanvasSize = UDim2.fromOffset(0, total)
	-- a new hero (the list arrived, also after a Retry, or the one before was bought) scrolls into view; once all are
	-- bought the page goes back to its top, where the "Office complete" banner is
	local heroIndex = S and S.nextIndex or nil
	if heroIndex ~= office.shownHero then
		office.shownHero = heroIndex
		office.reveal = heroIndex ~= nil
		if heroIndex == nil then
			officePage.CanvasPosition = Vector2.new(0, 0)
		end
	end
	if office.reveal and office.heroY then
		office.reveal = false
		revealHero()
	elseif officePage.CanvasPosition.Y > math.max(0, total - pagesHeight) then
		-- anything else keeps the player's place, only clamped to the new canvas (a shorter page, a new screen size)
		officePage.CanvasPosition = Vector2.new(0, math.max(0, total - pagesHeight))
	end
end

-- The hero card's line for a refusal (red) or a hint, for 3 s
local function rungStatus(i, text, color)
	local parts = office.rungs[i]
	if not parts then return end
	parts.statusToken += 1
	local myToken = parts.statusToken
	parts.statusText, parts.statusColor = text, color
	refreshAll()
	task.delay(3, function()
		if parts.statusToken == myToken then
			parts.statusText = nil
			refreshAll()
		end
	end)
end

-- Bought: the icon pops and what it earns floats up from the button
local function celebrate(i)
	local parts = office.rungs[i]
	if not parts then return end
	TweenService:Create(parts.pop, TweenInfo.new(0.1, Enum.EasingStyle.Quad, Enum.EasingDirection.Out, 0, true), { Scale = 1.08 }):Play()
	local p = parts.button.Position
	local float = make("TextLabel", {
		Name = "Float",
		Position = p,
		Size = parts.button.Size,
		BackgroundTransparency = 1,
		Font = Enum.Font.GothamBold,
		Text = "+" .. ShopConfig.formatCash(office.list[i].income) .. "/s",
		TextColor3 = COLORS.gold,
		ZIndex = 4,
		Parent = parts.card,
	})
	fitText(float, 24)
	TweenService:Create(float, TweenInfo.new(0.8, Enum.EasingStyle.Quad, Enum.EasingDirection.Out), {
		Position = UDim2.new(p.X.Scale, p.X.Offset, p.Y.Scale, p.Y.Offset - 34),
		TextTransparency = 1,
	}):Play()
	task.delay(0.85, function()
		float:Destroy()
	end)
end

-- Not enough Cash: the bar shakes (nothing is sent)
local function shakeBar(parts)
	local p = parts.bar.Position
	TweenService:Create(parts.bar, TweenInfo.new(0.05, Enum.EasingStyle.Sine, Enum.EasingDirection.InOut, 3, true), {
		Position = UDim2.new(p.X.Scale, p.X.Offset + 6, p.Y.Scale, p.Y.Offset),
	}):Play()
end

-- The one request that buys: only the upgrade's number. The server checks everything and answers.
local function buyOffice(actionRemote, index)
	if officeBusy then return end
	officeBusy, office.buying = true, index
	refreshAll()
	local ok, fine, message = pcall(function()
		return actionRemote:InvokeServer("BuyUpgrade", index)
	end)
	officeBusy, office.buying = false, nil
	if ok and fine == true then
		office.bought = index
		office.reveal = true -- the card says Bought! whole
		celebrate(index)
		refreshAll()
		task.delay(0.8, function()
			if office.bought == index then
				office.bought = nil -- now it folds into the summary row and the next rung is the hero
				refreshAll()
			end
		end)
	else
		local text = ok and typeof(message) == "string" and message ~= "" and message or "Couldn't buy that. Please try again."
		rungStatus(index, text, COLORS.refusal)
	end
end

-- A tap on a rung's button: only the hero's does something
local function tapRung(i)
	if not office.list or not office.actionRemote then return end
	local hero = ladderNow().hero
	if not hero or hero.index ~= i then
		return -- an owned rung says "Owned"; a locked one has no button
	end
	if hero.action == "buy" then
		buyOffice(office.actionRemote, i)
	elseif hero.action == "short" then
		shakeBar(office.rungs[i])
		rungStatus(i, hero.hint, COLORS.subtext)
	end
end

local function makeRung(i, upg)
	local card = make("Frame", { Name = "Office" .. i, BackgroundColor3 = COLORS.card, Parent = officePage })
	round(card, 12)
	local icon = make("TextLabel", {
		Name = "Icon",
		BackgroundTransparency = 1,
		Font = Enum.Font.GothamBold,
		Text = upg.icon or "🏢",
		TextColor3 = COLORS.text,
		Parent = card,
	})
	fitText(icon, 48)
	local parts = { card = card, icon = icon, statusToken = 0 }
	parts.pop = make("UIScale", { Name = "Pop", Parent = icon })
	parts.badge, parts.check, parts.lock = makeBadge(card)
	parts.name = officeText(card, "ItemName", Enum.Font.GothamBold, COLORS.text, 22)
	parts.name.Text = tostring(upg.name)
	parts.info = officeText(card, "Info", Enum.Font.Gotham, COLORS.subtext, 18)
	parts.bar = make("Frame", { Name = "Bar", BackgroundColor3 = COLORS.bar, BorderSizePixel = 0, Parent = card })
	round(parts.bar, 6)
	parts.fill = make("Frame", { Name = "Fill", Size = UDim2.fromScale(0, 1), BackgroundColor3 = COLORS.buy, BorderSizePixel = 0, Parent = parts.bar })
	round(parts.fill, 6)
	parts.progress = officeText(card, "Progress", Enum.Font.Gotham, COLORS.text, 18)
	parts.time = officeText(card, "Time", Enum.Font.Gotham, COLORS.subtext, 18)
	parts.status = officeText(card, "Status", Enum.Font.GothamBold, COLORS.refusal, 18)
	parts.button = make("TextButton", {
		Name = "BuyButton",
		BackgroundColor3 = COLORS.buy,
		Font = Enum.Font.GothamBold,
		Text = "",
		TextColor3 = COLORS.text,
		TextWrapped = true,
		Parent = card,
	})
	round(parts.button, 10)
	fitText(parts.button, 20)
	parts.pulse = make("UIScale", { Name = "Pulse", Parent = parts.button })
	parts.button.Activated:Connect(function()
		tapRung(i)
	end)
	return parts
end

-- Asks for the list (5 tries, 2 s apart); the gray rungs show meanwhile
local function fetchOffice()
	if office.fetching or office.list then return end
	office.fetching, office.failed = true, false
	refreshOffice()
	local actionRemote = remotes:WaitForChild("ShopAction", 10)
	local list
	for _ = 1, 5 do
		if not actionRemote then break end
		local ok, fine, result = pcall(function()
			return actionRemote:InvokeServer("Upgrades")
		end)
		if ok and fine and typeof(result) == "table" then
			list = result
			break
		end
		task.wait(2)
	end
	office.fetching = false
	if list then
		office.list, office.actionRemote = list, actionRemote
		for i, upg in ipairs(list) do
			office.rungs[i] = makeRung(i, upg)
		end
	else
		office.failed = true
	end
	refreshAll()
end

-- A soft pulse on an affordable Buy, every 4 s while the Office shows (the main loop calls this every second)
local pulseTicks = 0
local function pulseHero()
	pulseTicks += 1
	if pulseTicks % 4 ~= 0 or not office.list or not officePage.Visible then return end
	local hero = ladderNow().hero
	if hero and hero.action == "buy" then
		TweenService:Create(office.rungs[hero.index].pulse, TweenInfo.new(0.25, Enum.EasingStyle.Sine, Enum.EasingDirection.InOut, 0, true), { Scale = 1.05 }):Play()
	end
end

summary.Activated:Connect(function()
	office.unfolded = not office.unfolded
	refreshAll()
end)
retryButton.Activated:Connect(function()
	fetchOffice()
end)
table.insert(cards, refreshOffice)
table.insert(layoutHooks, refreshOffice)
task.spawn(fetchOffice)

-- Studio-only Debug tab: pretend to own passes and push fake receipts through the real server code
if debugRemote then
	local page = tabPages.Debug
	local status = make("TextLabel", {
		Name = "DebugStatus",
		LayoutOrder = 0,
		BackgroundColor3 = COLORS.debug,
		Font = Enum.Font.GothamBold,
		Text = "STUDIO ONLY: test without Robux. This tab never exists in live servers.",
		TextColor3 = COLORS.text,
		Parent = page,
	})
	round(status, 12)
	fitLabel(status, 16, 16)

	local busy = false
	local function runDebug(action, key)
		if busy then return end
		busy = true
		status.Text = "Working..."
		measureLabel(status)
		local ok, result = pcall(function()
			return debugRemote:InvokeServer(action, key)
		end)
		busy = false
		status.Text = ok and tostring(result) or ("Debug failed: " .. tostring(result))
		measureLabel(status)
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

	-- Task engine (PR 1, customer calls). The task Debug actions exist only while TaskConfig is active (Studio).
	-- (waits 5 s at most: a Studio place that doesn't have TaskConfig yet must never freeze the rest of this script)
	local taskConfigModule = ReplicatedStorage:WaitForChild("TaskConfig", 5)
	local TaskConfig = taskConfigModule and require(taskConfigModule)
	if TaskConfig and TaskConfig.isActive() then
		debugRow("📞", "Task: spawn a call", "A customer call rings now (the queue still holds at most 3).", "Spawn", "TaskSpawn")
		debugRow("📊", "Task stats", "This session's numbers for gate G1: rung, hires, engaged time, calls, Cash and the measured f. The full line is also in the Output window.", "Show", "TaskStats")
		for rung = 0, TaskConfig.MaxRung do
			debugRow("🪜", "Task rung: " .. TaskConfig.RungNames[rung + 1], "Sets the rung tasks scale with (pace, time limit, reward budget). Hires and Income stay as they are. Not saved.", "Set", "TaskSetRung", tostring(rung))
		end
		debugRow("🔁", "Task rung: your real stage", "Back to the rung your funding stage gives.", "Set", "TaskSetRung", "auto")
	end
end

-- Tabs, opening and closing ---------------------------------------------

-- The help card covers the pages while it is open (the pages hide, so it never sits on a Buy button)
local function setHelp(open)
	helpOpen = open
	helpCard.Visible = open
	pages.Visible = not open
	helpButton.BackgroundColor3 = open and COLORS.buy or COLORS.tab
end

local function showTab(name)
	setHelp(false)
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

helpButton.Activated:Connect(function()
	setHelp(not helpOpen)
end)
helpBack.Activated:Connect(function()
	setHelp(false)
end)

-- A message still in the window's line when the shop closes moves to the pop-up, once (it would go with the window):
-- the line is cleared, and the pop-up shows it in its own lane for its own 3.5 s (decided by the owner)
local function statusToToast()
	if not statusText then return end
	local text = statusText
	statusToken += 1 -- the line's own timer does nothing more
	statusText = nil
	applyLayout()
	showToast(text)
end

-- Only one window is open at a time: each window writes its name into PlayerGui's "OpenPanel"
-- attribute, and closes itself when another one opens
local function setOpen(open)
	setHelp(false) -- the shop opens on its last tab, never on the help card
	local wasOpen = window.Visible
	window.Visible = open
	if wasOpen and not open then
		statusToToast()
	end
	if open then
		playerGui:SetAttribute("OpenPanel", "Shop")
	elseif playerGui:GetAttribute("OpenPanel") == "Shop" then
		playerGui:SetAttribute("OpenPanel", nil)
	end
	-- Hide the phone joystick and jump button while a window is open, so they don't cover buttons
	GuiService.TouchControlsEnabled = playerGui:GetAttribute("OpenPanel") == nil
	if open then
		if toast.Visible then
			-- a message that is still up moves into the window (the pop-up would cover it)
			toastToken += 1
			toast.Visible = false
			showStatus(toastText) -- the whole message (the toast may show it cut)
		end
		refreshAll()
	end
end

playerGui:GetAttributeChangedSignal("OpenPanel"):Connect(function()
	if window.Visible and playerGui:GetAttribute("OpenPanel") ~= "Shop" then
		window.Visible = false
		statusToToast()
	end
end)

shopButton.Activated:Connect(function()
	setOpen(not window.Visible)
end)
closeButton.Activated:Connect(function()
	setOpen(false)
end)

showTab("Office")
refreshAll()
applyLayout()
gui:GetPropertyChangedSignal("AbsoluteSize"):Connect(applyLayout)
playerGui:GetAttributeChangedSignal("TutorialBanner"):Connect(applyLayout)

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

notifyEvent.OnClientEvent:Connect(showMessage)

task.spawn(function()
	local stats = player:WaitForChild("leaderstats")
	incomeValue = stats:WaitForChild("Income")
	cashValue = stats:WaitForChild("Cash")
	refreshAll()
end)

-- Timers, cash pack sizes and the Office bar tick while the shop is open
while true do
	task.wait(1)
	if window.Visible then
		refreshAll()
		pulseHero()
	end
end
