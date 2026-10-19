-- ShopClient: the Shop button and shop window (milestone 3).
-- Put this LocalScript in StarterPlayer > StarterPlayerScripts. It builds the screen by itself.
-- It only opens Roblox's purchase prompts. Everything is granted by ShopServer on the server.
-- The Office tab buys the office catalog by funding stage and the next building, and (its Hire chip) desks and direct hires
-- (overhaul 2, the Office tab's seventh chip): it sends only an item's or a hire's number, and the server decides.
-- Every size comes from ShopLayout (a ModuleScript in ReplicatedStorage, pure functions that tools/shop_ux_test.py
-- checks): the tabs in a rail on the left in landscape and in a row in portrait, 44 px header items and tap
-- targets, no text under 16 px. The tutorial finds its targets by name under ShopGui.Window: TabOffice ... TabDebug,
-- OfficePage ... DebugPage, Office1 ... Office63 (the catalog's cards), OfficeBuilding, HireDesk, BuyButton (every card's
-- button), HelpButton and TutorialStrip.

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
local OfficeConfig = require(ReplicatedStorage:WaitForChild("OfficeConfig")) -- the office catalog, buildings, desks, hires (overhaul 2)
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
	"Office: each funding stage unlocks its building and new items. Buy them with Cash.",
	"Office > Hire: a desk for each employee, and employees you choose (eggs cost less).",
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
local tabLabelW = {} -- each tab label's width on one line at 16 px: a portrait row makes room for it (ShopLayout)
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
	tabLabelW[i] = textWidth(name, tabButton.Font)

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
	make("UIListLayout", { Padding = UDim.new(0, 8), SortOrder = Enum.SortOrder.LayoutOrder, Parent = page })
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

-- In Studio, a TutorialBanner text longer than the strip shows on the smallest landscape phone is flagged once in the
-- Output (ShopLayout.STRIP_TEXT_LIMIT, about 40 characters: TutorialConfig's texts must stay under it)
local flaggedBanner
local function flagLongBanner()
	local text = tutorialBanner()
	if not (text and RunService:IsStudio()) or text == flaggedBanner then return end
	local count = utf8.len(text) or #text
	if count > ShopLayout.STRIP_TEXT_LIMIT then
		flaggedBanner = text
		warn(string.format("ShopClient: TutorialBanner is %d characters, the tutorial strip shows about %d on the smallest phone: %s",
			count, ShopLayout.STRIP_TEXT_LIMIT, text))
	end
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
	local L = ShopLayout.layout(size.X, size.Y, inset, #tabNames, 0, tabLabelW)
	local banner = tutorialBanner()
	local bottomH = 0
	if banner then
		bottomH = L.stripH
	end
	if statusText then
		bottomH = math.max(bottomH, math.clamp(textHeight(statusText, statusLine.Font, L.pages.w - 16) + 12, L.stripH, 72))
	end
	if bottomH > 0 then
		L = ShopLayout.layout(size.X, size.Y, inset, #tabNames, bottomH, tabLabelW)
	end

	local frame = L.window
	place(window, frame)
	place(title, L.title, frame)
	place(helpButton, L.help, frame)
	place(closeButton, L.close, frame)
	place(tabBar, L.tabBar, frame)
	tabBar.ScrollingDirection = L.rail and Enum.ScrollingDirection.Y or Enum.ScrollingDirection.X
	tabBar.CanvasSize = L.rail and UDim2.fromOffset(0, L.tabCanvas) or UDim2.fromOffset(L.tabCanvas, 0)
	tabBar.ScrollBarThickness = L.tabScrolls and ShopLayout.TAB_SCROLLBAR or 0
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

-- On the plaza with no garage yet (lobby L3: attribute Garage = 0)? Robux buttons wait for the garage: the save, the
-- passes and every purchase load with the company.
local function noGarage()
	return player:GetAttribute("Garage") == 0
end

-- Opens Roblox's purchase prompt. Nothing is granted here: the server does that
-- after Roblox confirms the purchase.
local promptToken = 0
local function promptPurchase(item, isPass)
	if pending[item.key] or noGarage() or not ShopConfig.isForSale(item, randomRestricted()) then return end
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
		elseif noGarage() then
			setButton(button, "Claim garage", COLORS.disabled, false)
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
			elseif noGarage() then
				setButton(button, "Claim garage", COLORS.disabled, false)
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

-- Office tab (overhaul 2, docs/OVERHAUL2_PLAN.md 1.2): the office catalog by funding stage. A row of six stage chips
-- picks the stage shown (the stage reached, when the shop opens); each stage shows its building first, then its items.
-- A stage not reached yet is shown greyed ("Unlocks at Series A"). Names, prices and effects come from OfficeConfig
-- (display only); a Buy tap sends only the item's number ("BuyUpgrade") or "BuyBuilding", and the server checks
-- everything and answers with a short message. Owned items come from the server's Upgrade<i> attributes; the building,
-- the desks and the hires from the "Office" request (asked when the shop opens and after every purchase).
-- The seventh chip, "Hire", shows the next desk (a workstation for one more employee) and the direct hires, with what an
-- egg pays on average for the same rarity (eggs stay the better deal: OfficeConfig.HireFactor).
local officePage = tabPages.Office
local hirePage = officePage -- the Hire chip's cards live on the Office page (a phone has no room for a fifth tab)
local office = { state = nil, shown = nil, busy = false, actionRemote = nil, fetching = false }
local SHORT_STAGE = { "Garage", "Seed", "Series A", "Series B", "Series C", "IPO" }
local HIRE = 7 -- office.shown for the Hire chip

-- The stage the valuation reached (the server's attributes; the server decides every purchase anyway)
local function stageNow()
	local valuation = player:GetAttribute("IpoValuation") or 0
	local count = player:GetAttribute("IpoCount") or 0
	return IpoConfig.stageIndex(valuation, count)
end

local function ownsItem(i)
	return player:GetAttribute("Upgrade" .. i) == true
end

local function cashNow()
	return cashValue and cashValue.Value or 0
end

-- The building the player owns this run (the server's Building attribute, display only)
local function buildingNow()
	return player:GetAttribute("Building") or (office.state and office.state.building) or 1
end

-- The six stage chips and the Hire chip, in two rows of four (every chip shows on the narrowest phone, nothing to scroll)
local chipRow = make("Frame", {
	Name = "StageChips",
	LayoutOrder = 0,
	Size = UDim2.new(1, 0, 0, 94),
	BackgroundTransparency = 1,
	Parent = officePage,
})
-- chip k's place in the two rows of four
local function chipPlace(chip, k)
	local row, col = (k - 1) // 4, (k - 1) % 4
	chip.Position = UDim2.new(col * 0.25, 3, 0, row * 50)
	chip.Size = UDim2.new(0.25, -6, 0, 44)
end
local chips = {}
for stage, label in ipairs(SHORT_STAGE) do
	local chip = make("TextButton", {
		Name = "Stage" .. stage,
		LayoutOrder = stage,
		BackgroundColor3 = COLORS.tab,
		Font = Enum.Font.GothamBold,
		Text = label,
		TextColor3 = COLORS.text,
		Parent = chipRow,
	})
	round(chip, 10)
	fitText(chip, 18)
	chipPlace(chip, stage)
	chips[stage] = chip
	chip.Activated:Connect(function()
		office.shown = stage
		refreshAll()
	end)
end
local hireChip = make("TextButton", {
	Name = "StageHire",
	LayoutOrder = HIRE,
	BackgroundColor3 = COLORS.tab,
	Font = Enum.Font.GothamBold,
	Text = "Hire",
	TextColor3 = COLORS.text,
	Parent = chipRow,
})
round(hireChip, 10)
fitText(hireChip, 18)
chipPlace(hireChip, HIRE)
chips[HIRE] = hireChip
hireChip.Activated:Connect(function()
	office.shown = HIRE
	refreshAll()
end)

-- One purchase request; the answer goes to the status line, then the office is asked again
local fetchOfficeState -- below
local function officeRequest(action, index)
	if office.busy or not office.actionRemote then return end
	office.busy = true
	refreshAll()
	local ok, fine, message = pcall(function()
		if index == nil then
			return office.actionRemote:InvokeServer(action) -- BuyBuilding, BuyDesk: nothing but the request
		end
		return office.actionRemote:InvokeServer(action, index)
	end)
	office.busy = false
	local text = ok and typeof(message) == "string" and message ~= "" and message or "Couldn't buy that. Please try again."
	showMessage(text)
	if ok and fine == true then
		task.spawn(fetchOfficeState)
	end
	refreshAll()
end

-- The building card of the stage shown: owned, the next one to buy, or locked
local buildingDesc, buildingButton, buildingParts = makeCard(officePage, 1, "🏢", "Building", "OfficeBuilding")
buildingButton.Activated:Connect(function()
	local shown = office.shown or stageNow()
	if shown ~= HIRE and shown == buildingNow() + 1 and stageNow() >= shown then
		officeRequest("BuyBuilding")
	end
end)
table.insert(cards, function()
	local shown = office.shown or stageNow()
	buildingParts.card.Visible = shown ~= HIRE
	if shown == HIRE then return end
	local building = OfficeConfig.Buildings[shown]
	buildingParts.name.Text = building.name
	buildingParts.icon.Text = ({ "🏚️", "🏢", "🏬", "🏙️", "🏦", "🗼" })[shown] or "🏢"
	local effect = string.format("Items earn x%s, employees x%s.", tostring(building.office), tostring(building.team))
	local have = buildingNow()
	if shown <= have then
		buildingDesc.Text = effect .. (shown == have and " Your office now." or "")
		setButton(buildingButton, shown == have and "Yours" or "Moved on", COLORS.owned, false)
	elseif stageNow() < shown then
		buildingDesc.Text = effect .. " " .. OfficeConfig.unlockText(shown) .. "."
		setButton(buildingButton, "Locked", COLORS.disabled, false)
	elseif shown > have + 1 then
		buildingDesc.Text = effect .. " Buy the " .. OfficeConfig.Buildings[have + 1].name .. " first."
		setButton(buildingButton, "Later", COLORS.disabled, false)
	elseif office.busy then
		buildingDesc.Text = effect
		setButton(buildingButton, "...", COLORS.disabled, false)
	else
		buildingDesc.Text = effect .. " The room and the building change at once."
		setButton(buildingButton, OfficeConfig.money(building.price), cashNow() >= building.price and COLORS.buy or COLORS.disabled, true)
	end
end)

-- What an item does, in one line under its name
local function itemText(item, shown)
	local text = item.text
	if item.income > 0 then
		local office = OfficeConfig.Buildings[math.max(buildingNow(), 1)].office
		text = string.format("+%s/s. %s", OfficeConfig.money(item.income * office), text)
	end
	if stageNow() < item.stage then
		text ..= " " .. OfficeConfig.unlockText(item.stage) .. "."
	end
	return text
end

-- One card per item, shown only on its stage's page
for i, item in ipairs(OfficeConfig.Items) do
	local desc, button, parts = makeCard(officePage, 10 + i, item.icon, item.key, "Office" .. i)
	button.Activated:Connect(function()
		if ownsItem(i) or stageNow() < item.stage then return end
		officeRequest("BuyUpgrade", i)
	end)
	table.insert(cards, function()
		local shown = office.shown or stageNow()
		parts.card.Visible = item.stage == shown
		if not parts.card.Visible then return end
		desc.Text = itemText(item, shown)
		if ownsItem(i) then
			setButton(button, "Owned", COLORS.owned, false)
		elseif stageNow() < item.stage then
			setButton(button, "Locked", COLORS.disabled, false)
		elseif i ~= 1 and not ownsItem(1) then
			setButton(button, OfficeConfig.FirstItem .. " first", COLORS.disabled, false)
		elseif office.busy then
			setButton(button, "...", COLORS.disabled, false)
		else
			setButton(button, item.price == 0 and "Free" or OfficeConfig.money(item.price), cashNow() >= item.price and COLORS.buy or COLORS.disabled, true)
		end
	end)
end

-- The chips: the stage shown is green, a stage not reached yet is darker
table.insert(cards, function()
	local shown = office.shown or stageNow()
	local reached = stageNow()
	for stage, chip in pairs(chips) do
		local open = stage <= reached or stage == HIRE
		chip.BackgroundColor3 = stage == shown and COLORS.buy or (open and COLORS.tab or COLORS.panel)
		chip.TextColor3 = open and COLORS.text or COLORS.lock
	end
end)

-- The Hire chip: the desks card
local deskDesc, deskButton, deskParts = makeCard(hirePage, 200, "🪑", "A new desk", "HireDesk")
deskButton.Activated:Connect(function()
	officeRequest("BuyDesk")
end)
table.insert(cards, function()
	deskParts.card.Visible = office.shown == HIRE
	local state = office.state
	if not state then
		deskDesc.Text = "Loading your office..."
		setButton(deskButton, "...", COLORS.disabled, false)
		return
	end
	local nextDesk = OfficeConfig.Bought[state.desks + 1]
	local line = string.format("Desks: %d (team %d). Every employee needs a desk.", state.capacity, state.team)
	if not nextDesk or state.capacity >= OfficeConfig.MaxWorkstations then
		deskDesc.Text = line .. " Every desk you can buy is bought (Extra Employee Slots and the Extra Desk perk add more for free)."
		setButton(deskButton, "All bought", COLORS.owned, false)
	elseif stageNow() < nextDesk.stage then
		deskDesc.Text = line .. " The next desk: " .. OfficeConfig.unlockText(nextDesk.stage) .. "."
		setButton(deskButton, "Locked", COLORS.disabled, false)
	elseif office.busy then
		deskDesc.Text = line
		setButton(deskButton, "...", COLORS.disabled, false)
	else
		deskDesc.Text = line .. " A desk, a chair and a computer, kept after an IPO."
		setButton(deskButton, OfficeConfig.money(nextDesk.price), cashNow() >= nextDesk.price and COLORS.buy or COLORS.disabled, true)
	end
end)

-- Why eggs are better: one line over the hires
local hireNote = make("TextLabel", {
	Name = "HireNote",
	LayoutOrder = 201,
	BackgroundTransparency = 1,
	Font = Enum.Font.Gotham,
	Text = string.format("Hire someone you choose, no surprise. Eggs are the better deal: a hire here costs %dx what an egg pays on average for the same rarity.", OfficeConfig.HireFactor),
	TextColor3 = COLORS.subtext,
	TextXAlignment = Enum.TextXAlignment.Left,
	Parent = hirePage,
})
fitLabel(hireNote, 4)
table.insert(cards, function()
	hireNote.Visible = office.shown == HIRE
end)

-- One card per direct hire (the list is OfficeConfig's, the same the server checks)
for i, offer in ipairs(OfficeConfig.hireList(CreatureConfig)) do
	local creature = CreatureConfig.getCreature(offer.creature)
	local egg = CreatureConfig.getEgg(offer.egg)
	local desc, button, parts = makeCard(hirePage, 210 + i, creature.emoji or "👤", string.format("%s (%s)", creature.name, offer.rarity), "Hire" .. i)
	button.Activated:Connect(function()
		officeRequest("Hire", i)
	end)
	table.insert(cards, function()
		parts.card.Visible = office.shown == HIRE
		if not parts.card.Visible then return end
		local team = OfficeConfig.Buildings[buildingNow()].team
		desc.Text = string.format("%s, earns %s/s here. A %s gives a %s for about %s on average.", creature.role,
			OfficeConfig.money(creature.income * team), egg and egg.name or "egg", offer.rarity, OfficeConfig.money(offer.eggAverage))
		local state = office.state
		if office.busy or not state then
			setButton(button, "...", COLORS.disabled, false)
		elseif state.team >= state.capacity then
			setButton(button, "No free desk", COLORS.disabled, false)
		else
			setButton(button, OfficeConfig.money(offer.price), cashNow() >= offer.price and COLORS.buy or COLORS.disabled, true)
		end
	end)
end

-- Asks the server for the office (the building, the desks, the team); 5 tries, 2 s apart, on the first call
fetchOfficeState = function()
	if office.fetching then return end
	office.fetching = true
	office.actionRemote = office.actionRemote or remotes:WaitForChild("ShopAction", 10)
	for _ = 1, 5 do
		if not office.actionRemote then break end
		local ok, fine, result = pcall(function()
			return office.actionRemote:InvokeServer("Office")
		end)
		if ok and fine and typeof(result) == "table" then
			office.state = result
			break
		end
		task.wait(2)
	end
	office.fetching = false
	refreshAll()
end

-- The Office tab opens on the stage reached; the office is asked again every time the shop opens
local function onShopOpened()
	office.shown = stageNow()
	task.spawn(fetchOfficeState)
end

-- A soft pulse on the building's Buy when it can be bought (the main loop calls this every second)
local pulseTicks = 0
local buildingPulse = make("UIScale", { Name = "Pulse", Parent = buildingButton })
local function pulseHero()
	pulseTicks += 1
	if pulseTicks % 4 ~= 0 or not officePage.Visible then return end
	local shown = office.shown or stageNow()
	local building = shown ~= HIRE and OfficeConfig.Buildings[shown]
	if building and shown == buildingNow() + 1 and stageNow() >= shown and cashNow() >= building.price then
		TweenService:Create(buildingPulse, TweenInfo.new(0.25, Enum.EasingStyle.Sine, Enum.EasingDirection.InOut, 0, true), { Scale = 1.05 }):Play()
	end
end
player:GetAttributeChangedSignal("Garage"):Connect(function()
	task.spawn(fetchOfficeState)
end)

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
	-- Reset my save (overhaul 2, the owner's request): Studio play writes the real save, so this makes it a new player's
	-- again. Two taps (Reset, then "Yes, erase it" within 15 s), and the server asks for both steps too.
	local resetDesc, resetButton = makeCard(page, order, "🧨", "Reset my save")
	order += 1
	resetDesc.Text = "Erases YOUR real save (the same one live servers use): Cash, team, eggs, IPOs, office, daily streak, everything. You come back as a brand-new player. Studio only."
	local resetArmedUntil = 0
	local function showReset()
		local armed = os.clock() < resetArmedUntil
		setButton(resetButton, armed and "Yes, erase it" or "Reset", armed and COLORS.close or COLORS.debug, true)
	end
	showReset()
	resetButton.Activated:Connect(function()
		if os.clock() < resetArmedUntil then
			resetArmedUntil = 0
			showReset()
			runDebug("ResetSaveConfirm")
		else
			resetArmedUntil = os.clock() + 15
			showReset()
			runDebug("ResetSaveArm")
			task.delay(15.1, showReset)
		end
	end)
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
	debugRow("🏗️", "Building: next stage", "Shows the next funding stage's room and building, to walk every doorway. Not saved: a rejoin shows your real stage.", "Next", "BuildingNextStage")

	-- First minute (milestone 5)
	debugRow("🐣", "Restart tutorial", "Gives the free egg again and brings back the arrow and goal tracker, on any save.", "Restart", "OnboardingRestart")
	debugRow("👴", "Act like an old save", "Counts you as a player from before milestone 5: no arrow, no tracker.", "Set", "OnboardingMarkOld")

	-- Daily rewards (milestone 6)
	debugRow("📅", "Daily: next day (fake)", "Pretends one UTC day passed for you. After a claim: once = next day, twice = 1 missed day (place kept), 3 times = 2 missed days (back to Day 1).", "+1 day", "DailyNextDay")
	debugRow("🗓️", "Daily: reset calendar", "Like a save from before milestone 6: next claim is Day 1, no streak.", "Reset", "DailyReset")

	-- Task engine (customer calls). The task Debug actions exist only while TaskConfig is active.
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

	-- Founder activities (overhaul 2 phase 3)
	debugRow("🚨", "Founder: production bug now", "The Server Rack's alarm rings in a moment (needs the Server Rack).", "Ring", "FounderBugNow")
	debugRow("⏱️", "Founder: sprint and brainstorm ready", "Skips the coding sprint's and the brainstorm's wait.", "Ready", "FounderReady")
	debugRow("💼", "Founder: pitch again", "Offers this funding round's investor pitch again (saved, like a real pitch).", "Offer", "FounderPitchAgain")
	debugRow("🍽️", "Founder: dinner again", "Offers today's VIP investor dinner again (saved; needs the VIP pass).", "Offer", "FounderDinnerAgain")
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
		onShopOpened() -- the Office tab on the stage reached, the office asked again (overhaul 2)
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
playerGui:GetAttributeChangedSignal("TutorialBanner"):Connect(function()
	flagLongBanner()
	applyLayout()
end)
flagLongBanner()

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

player:GetAttributeChangedSignal("Garage"):Connect(refreshAll) -- the Robux buttons wake up with the garage

task.spawn(function()
	-- leaderstats come only with a garage (lobby L3: a player can stand on the plaza for minutes): no WaitForChild, so
	-- no "infinite yield" warning
	local stats = player:FindFirstChild("leaderstats")
	while not stats do
		player.ChildAdded:Wait()
		stats = player:FindFirstChild("leaderstats")
	end
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
