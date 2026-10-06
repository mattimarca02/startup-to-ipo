-- ShopLayout: the shop window's sizes, as pure functions (numbers in, tables out). Put this ModuleScript in
-- ReplicatedStorage. ShopClient (StarterPlayerScripts) requires it and only applies what it returns, and
-- tools/shop_ux_test.py checks the same functions outside Studio. No GetService, no require, no Instance, no remote,
-- nothing saved.
--
-- Every rectangle is { x, y, w, h } in GUI pixels: the ShopGui's own space. The ShopGui keeps IgnoreGuiInset = false,
-- so Roblox's top bar is already outside it. Nothing a player must read is smaller than ShopLayout.MIN_TEXT (16 px),
-- and every tap target is at least ShopLayout.TAP (44 px) in both directions.
--   ShopLayout.layout(guiW, guiH, topBar, tabCount, bottomH)  -> the window: header, tabs, pages, bottom slot
--   ShopLayout.cardWidths(cardW)                              -> how wide a card's name and description wrap
--   ShopLayout.card(cardW, nameH, descH)                      -> the pieces of one Robux or Debug card
--   ShopLayout.helpCard(w, h, lineHeights)                    -> the "How the shop works" card (HelpButton)

local ShopLayout = {}

ShopLayout.MIN_TEXT = 16 -- the smallest text a player must read (docs/SHOP_UX_PROPOSAL.md 3.9)
ShopLayout.TAP = 44 -- the smallest tap target, in both directions
ShopLayout.HEADER = 44 -- the title, "?" and X are this tall
ShopLayout.BUTTON_H = 48 -- buy buttons
ShopLayout.PADDING = 10 -- inside the window
ShopLayout.GAP = 6 -- between the header, the tabs, the pages and the bottom slot
ShopLayout.WINDOW_SHARE = 0.92 -- of the GUI, in both directions
ShopLayout.WINDOW_MAX_W = 640
ShopLayout.WINDOW_MAX_H = 470
ShopLayout.SHORT_BELOW = 330 -- a window lower than this is "short": the one-line TutorialStrip
ShopLayout.STRIP_SHORT = 32 -- the TutorialStrip's height on a short window (one line)
ShopLayout.STRIP_TALL = 48 -- and on a taller one (two lines)
ShopLayout.RAIL_W = 112 -- the landscape tab rail's width (its tabs are 112 x 44)
ShopLayout.RAIL_GAP_MIN = 2 -- the rail's tabs move closer together on a low window, down to this
ShopLayout.HELP_RIGHT = 50 -- "?" ends this far from the right edge: left of the X, 6 px apart
ShopLayout.TITLE_RIGHT = 106 -- the title ends this far from the right edge (X, "?" and two gaps)
ShopLayout.WIDE_CARD = 420 -- a card at least this wide keeps its text between the icon and the button
ShopLayout.SCROLLBAR_ROOM = 10 -- the pages' right padding, where the scrollbar goes
ShopLayout.TOAST_MAX_W = 520 -- the pop-up message at the bottom center (only while the shop is closed)

local function finite(value, default)
	value = tonumber(value)
	if value == nil or value ~= value or value == math.huge or value == -math.huge then
		return default
	end
	return value
end

local function rect(x, y, w, h)
	return { x = x, y = y, w = math.max(0, w), h = math.max(0, h) }
end
ShopLayout.rect = rect

-- The whole window for a GUI of guiW x guiH pixels (the ShopGui's AbsoluteSize).
--   topBar   Roblox's top bar above the GUI (GuiService:GetGuiInset()); it moves nothing (it is outside the GUI),
--            it only gives L.device, the phone's screen, so a check can name the phone it is about
--   tabCount 4, or 5 with the Studio Debug tab
--   bottomH  the bottom slot's height: 0 while neither the TutorialStrip nor a status message shows
-- Landscape (wider than tall) puts the tabs in a rail on the left, from the top of the window; portrait keeps them
-- in a row under the header. Returns:
--   window, content (the window less its padding), title, help, close, tabBar, tabs[i], pages, helpCard, toast,
--   bottom (only when bottomH > 0), rail, short, stripH, tabGap, tabCanvas, tabScrolls, cardW, device
function ShopLayout.layout(guiW, guiH, topBar, tabCount, bottomH)
	guiW = math.max(0, finite(guiW, 0))
	guiH = math.max(0, finite(guiH, 0))
	topBar = math.max(0, finite(topBar, 0))
	tabCount = math.max(1, math.floor(finite(tabCount, 4)))
	bottomH = math.max(0, math.floor(finite(bottomH, 0)))

	local L = { gui = rect(0, 0, guiW, guiH), topBar = topBar, tabCount = tabCount, device = { w = guiW, h = guiH + topBar } }
	local w = math.floor(math.min(guiW * ShopLayout.WINDOW_SHARE, ShopLayout.WINDOW_MAX_W))
	local h = math.floor(math.min(guiH * ShopLayout.WINDOW_SHARE, ShopLayout.WINDOW_MAX_H))
	L.window = rect(math.floor((guiW - w) / 2), math.floor((guiH - h) / 2), w, h)
	local pad = ShopLayout.PADDING
	local c = rect(L.window.x + pad, L.window.y + pad, w - 2 * pad, h - 2 * pad)
	L.content = c
	L.rail = guiW > guiH
	L.short = h < ShopLayout.SHORT_BELOW
	L.stripH = L.short and ShopLayout.STRIP_SHORT or ShopLayout.STRIP_TALL

	local tap, header, gap = ShopLayout.TAP, ShopLayout.HEADER, ShopLayout.GAP
	local right = c.x + c.w
	L.close = rect(right - tap, c.y, tap, header)
	L.help = rect(right - ShopLayout.HELP_RIGHT - tap, c.y, tap, header)

	-- The bottom slot (TutorialStrip or a status message) takes its height from the tabs and the pages
	local bottom = c.y + c.h
	if bottomH > 0 then
		L.bottom = rect(c.x, c.y + c.h - bottomH, c.w, bottomH)
		bottom = L.bottom.y - gap
	end

	L.tabs = {}
	if L.rail then
		L.tabBar = rect(c.x, c.y, ShopLayout.RAIL_W, bottom - c.y)
		local spare = L.tabBar.h - tabCount * tap
		local tabGap = tabCount > 1 and math.floor(spare / (tabCount - 1)) or 0
		L.tabGap = math.clamp(tabGap, ShopLayout.RAIL_GAP_MIN, gap)
		for i = 1, tabCount do
			L.tabs[i] = rect(c.x, c.y + (i - 1) * (tap + L.tabGap), ShopLayout.RAIL_W, tap)
		end
		L.tabCanvas = tabCount * tap + (tabCount - 1) * L.tabGap
		L.tabScrolls = L.tabCanvas > L.tabBar.h -- only on very low windows (or with the Studio Debug tab)
		local left = c.x + ShopLayout.RAIL_W + 8
		L.title = rect(left, c.y, right - ShopLayout.TITLE_RIGHT - left, header)
		local top = c.y + header + gap
		L.pages = rect(left, top, right - left, bottom - top)
	else
		local top = c.y + header + gap
		L.tabBar = rect(c.x, top, c.w, tap)
		L.tabGap = tabCount >= 5 and 4 or gap
		local tabW = math.max(tap, math.floor((c.w - (tabCount - 1) * L.tabGap) / tabCount))
		for i = 1, tabCount do
			L.tabs[i] = rect(c.x + (i - 1) * (tabW + L.tabGap), top, tabW, tap)
		end
		L.tabCanvas = tabCount * tabW + (tabCount - 1) * L.tabGap
		L.tabScrolls = L.tabCanvas > L.tabBar.w -- a phone narrower than any we know
		L.title = rect(c.x, c.y, c.w - ShopLayout.TITLE_RIGHT, header)
		local pagesTop = top + tap + gap
		L.pages = rect(c.x, pagesTop, c.w, bottom - pagesTop)
	end

	-- The help card covers the pages and the bottom slot (never the header or the tabs)
	L.helpCard = rect(L.pages.x, L.pages.y, L.pages.w, c.y + c.h - L.pages.y)
	L.cardW = math.max(0, L.pages.w - ShopLayout.SCROLLBAR_ROOM)
	local toastW = math.floor(math.min(guiW * 0.6, ShopLayout.TOAST_MAX_W))
	L.toast = rect(math.floor((guiW - toastW) / 2), guiH - 16 - 48, toastW, 48)
	return L
end

-- Cards -------------------------------------------------------------------------------------------------------

-- How wide a card's name and description wrap (ShopClient measures both at 16 px at these widths)
function ShopLayout.cardWidths(cardW)
	cardW = math.max(0, finite(cardW, 0))
	if cardW < ShopLayout.WIDE_CARD then
		return math.max(0, cardW - 52 - 88), math.max(0, cardW - 16)
	end
	return math.max(0, cardW - 208), math.max(0, cardW - 208)
end

-- One Robux or Debug card, cardW wide (ShopLayout.layout(...).cardW). nameH and descH are the measured heights of
-- its name and description at 16 px, wrapped at ShopLayout.cardWidths. Returns height and the rectangles icon, name,
-- desc and button in the card's own pixels.
--   Wide (landscape): the name and the description between the icon and the button, like before.
--   Narrow (portrait): the icon, the name and the button on a top row, the description across the whole card under
--   them, so a long text stays at 16 px instead of shrinking.
function ShopLayout.card(cardW, nameH, descH)
	cardW = math.max(0, finite(cardW, 0))
	nameH = math.max(0, finite(nameH, 0))
	descH = math.max(0, finite(descH, 0))
	local nameW, descW = ShopLayout.cardWidths(cardW)
	local buttonH = ShopLayout.BUTTON_H
	local C = { narrow = cardW < ShopLayout.WIDE_CARD }
	if C.narrow then
		local top = math.max(buttonH, nameH)
		C.icon = rect(8, 8 + math.floor((top - 36) / 2), 36, 36)
		C.button = rect(cardW - 8 - 72, 8 + math.floor((top - buttonH) / 2), 72, buttonH)
		C.name = rect(52, 8, nameW, top)
		C.desc = rect(8, 8 + top + 4, descW, descH)
		C.height = C.desc.y + descH + 8
	else
		C.name = rect(68, 8, nameW, math.max(24, nameH))
		C.desc = rect(68, C.name.y + C.name.h + 2, descW, descH)
		C.height = math.max(84, C.desc.y + descH + 8)
		C.icon = rect(8, math.floor((C.height - 52) / 2), 52, 52)
		C.button = rect(cardW - 8 - 124, math.floor((C.height - buttonH) / 2), 124, buttonH)
	end
	return C
end

-- The help card ------------------------------------------------------------------------------------------------

-- How wide the help card's lines wrap (measured at 16 px)
function ShopLayout.helpTextWidth(w)
	return math.max(0, finite(w, 0) - 20)
end

-- The "How the shop works" card, w x h (ShopLayout.layout(...).helpCard): a title row with a 44 px Back button,
-- then one rectangle per line (lineHeights = their measured heights). fits = false when they need a scroll.
function ShopLayout.helpCard(w, h, lineHeights)
	w = math.max(0, finite(w, 0))
	h = math.max(0, finite(h, 0))
	local backW = 88
	local H = {
		title = rect(10, 10, w - 20 - backW - 8, ShopLayout.TAP),
		back = rect(w - 10 - backW, 10, backW, ShopLayout.TAP),
		lines = {},
	}
	local y = 10 + ShopLayout.TAP + 8
	for i, lineH in ipairs(lineHeights or {}) do
		lineH = math.max(0, finite(lineH, 0))
		H.lines[i] = rect(10, y, ShopLayout.helpTextWidth(w), lineH)
		y += lineH + 6
	end
	H.height = y - 6 + 10
	H.fits = H.height <= h
	return H
end

return ShopLayout
