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
--   ShopLayout.card(cardW, nameH, descH, badgeW)              -> the pieces of one Robux or Debug card
--   ShopLayout.helpCard(w, h, lineHeights)                    -> the "How the shop works" card (HelpButton)
-- The Office ladder (docs/SHOP_UX_PROPOSAL.md 3.2):
--   ShopLayout.ladder(upgrades, owned, cash, income, money, bought, busy)  -> what every rung shows (the state)
--   ShopLayout.barFill(cash, price), ShopLayout.timeText(cash, price, income)  -> the hero's bar and its time
--   ShopLayout.officeRow(cardW, kind), ShopLayout.hero(cardW)  -> a rung's pieces (owned, locked, summary, banner, hero)
--   ShopLayout.stack(heights, gap), ShopLayout.revealScroll(y, h, view, total)  -> the Office page, top to bottom
--   ShopLayout.bestValue(products, forSale)  -> the Cash pack with the most minutes of Income per Robux (BEST VALUE)

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
ShopLayout.BADGE_H = 22 -- a factual badge on a card (BEST VALUE)
ShopLayout.HERO_WIDE = 132 -- the Office's next upgrade (the hero card) on a wide page (landscape)
ShopLayout.HERO_NARROW = 202 -- and on a narrow one (portrait): the bar, the time and a full-width button under the name
ShopLayout.ROW_WIDE = 64 -- an owned or locked rung, the summary row and the "Office complete" banner
ShopLayout.ROW_NARROW = 72 -- on a narrow page: room for a second line
ShopLayout.OFFICE_GAP = 6 -- between the Office page's rows

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

	-- The bottom slot (TutorialStrip or a status message) sits under the pages, as wide as they are, and takes its
	-- height from them (never from the rail, so the tabs keep their room)
	local function slotUnder(left, width)
		local bottom = c.y + c.h
		if bottomH > 0 then
			L.bottom = rect(left, c.y + c.h - bottomH, width, bottomH)
			bottom = L.bottom.y - gap
		end
		return bottom
	end

	L.tabs = {}
	if L.rail then
		L.tabBar = rect(c.x, c.y, ShopLayout.RAIL_W, c.h)
		local spare = L.tabBar.h - tabCount * tap
		local tabGap = tabCount > 1 and math.floor(spare / (tabCount - 1)) or 0
		L.tabGap = math.clamp(tabGap, ShopLayout.RAIL_GAP_MIN, gap)
		for i = 1, tabCount do
			L.tabs[i] = rect(c.x, c.y + (i - 1) * (tap + L.tabGap), ShopLayout.RAIL_W, tap)
		end
		L.tabCanvas = tabCount * tap + (tabCount - 1) * L.tabGap
		L.tabScrolls = L.tabCanvas > L.tabBar.h -- only with the Studio Debug tab on the lowest windows
		local left = c.x + ShopLayout.RAIL_W + 8
		L.title = rect(left, c.y, right - ShopLayout.TITLE_RIGHT - left, header)
		local top = c.y + header + gap
		local bottom = slotUnder(left, right - left)
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
		local bottom = slotUnder(c.x, c.w)
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

-- How wide a card's name and description wrap (ShopClient measures both at 16 px at these widths). badgeW: the
-- width of a badge (BEST VALUE) the card shows, 0 for none: on a wide card it sits at the end of the name's row.
function ShopLayout.cardWidths(cardW, badgeW)
	cardW = math.max(0, finite(cardW, 0))
	badgeW = math.max(0, finite(badgeW, 0))
	if cardW < ShopLayout.WIDE_CARD then
		return math.max(0, cardW - 52 - 88), math.max(0, cardW - 16)
	end
	local nameW = cardW - 208
	if badgeW > 0 then
		nameW -= badgeW + 8
	end
	return math.max(0, nameW), math.max(0, cardW - 208)
end

-- One Robux or Debug card, cardW wide (ShopLayout.layout(...).cardW). nameH and descH are the measured heights of
-- its name and description at 16 px, wrapped at ShopLayout.cardWidths. badgeW: a badge's width (0: none). Returns
-- height and the rectangles icon, name, desc, button (and badge) in the card's own pixels.
--   Wide (landscape): the name and the description between the icon and the button, like before; the badge at the
--   end of the name's row.
--   Narrow (portrait): the icon, the name and the button on a top row, the description across the whole card under
--   them (the badge first), so a long text stays at 16 px instead of shrinking.
function ShopLayout.card(cardW, nameH, descH, badgeW)
	cardW = math.max(0, finite(cardW, 0))
	nameH = math.max(0, finite(nameH, 0))
	descH = math.max(0, finite(descH, 0))
	badgeW = math.max(0, finite(badgeW, 0))
	local nameW, descW = ShopLayout.cardWidths(cardW, badgeW)
	local buttonH = ShopLayout.BUTTON_H
	local C = { narrow = cardW < ShopLayout.WIDE_CARD }
	if C.narrow then
		local top = math.max(buttonH, nameH)
		C.icon = rect(8, 8 + math.floor((top - 36) / 2), 36, 36)
		C.button = rect(cardW - 8 - 72, 8 + math.floor((top - buttonH) / 2), 72, buttonH)
		C.name = rect(52, 8, nameW, top)
		local y = 8 + top + 4
		if badgeW > 0 then
			C.badge = rect(8, y, math.min(badgeW, descW), ShopLayout.BADGE_H)
			y += ShopLayout.BADGE_H + 4
		end
		C.desc = rect(8, y, descW, descH)
		C.height = C.desc.y + descH + 8
	else
		C.name = rect(68, 8, nameW, math.max(24, nameH))
		if badgeW > 0 then
			C.badge = rect(68 + nameW + 8, 9, badgeW, ShopLayout.BADGE_H)
		end
		C.desc = rect(68, C.name.y + C.name.h + 2, descW, descH)
		C.height = math.max(84, C.desc.y + descH + 8)
		C.icon = rect(8, math.floor((C.height - 52) / 2), 52, 52)
		C.button = rect(cardW - 8 - 124, math.floor((C.height - buttonH) / 2), 124, buttonH)
	end
	return C
end

-- The Cash pack with the most minutes of Income per Robux among the products forSale(product) allows (never one
-- that is "Coming soon"): its key, or nil. Computed from ShopConfig, so it moves when the minutes or prices change.
-- A tie keeps the first in config order.
function ShopLayout.bestValue(products, forSale)
	local best, bestRate
	for _, product in ipairs(products or {}) do
		local minutes = product.effect and finite(product.effect.incomeMinutes, 0) or 0
		local price = finite(product.price, 0)
		if minutes > 0 and price > 0 and forSale(product) then
			local rate = minutes / price
			if bestRate == nil or rate > bestRate then
				best, bestRate = product.key, rate
			end
		end
	end
	return best
end

-- The Office ladder ---------------------------------------------------------------------------------------------

-- The hero's bar: the Cash against the price, from 0 to 1 (a free upgrade is full; nothing gives a NaN)
function ShopLayout.barFill(cash, price)
	cash, price = finite(cash, 0), finite(price, 0)
	if price <= 0 then
		return 1
	end
	return math.clamp(cash / price, 0, 1)
end

-- How long until the Cash reaches the price at this Income: "about 25 s" (minutes from 2 minutes on, hours from 2
-- hours on). nil when the Cash is already there or the Income is 0: never a negative or an infinite time.
function ShopLayout.timeText(cash, price, income)
	cash, price, income = finite(cash, 0), finite(price, 0), finite(income, 0)
	local need = price - cash
	if need <= 0 or income <= 0 then
		return nil
	end
	local seconds = math.ceil(need / income)
	if seconds ~= seconds or seconds == math.huge or seconds < 1 then
		return nil
	end
	if seconds < 120 then
		return "about " .. seconds .. " s"
	end
	local minutes = math.ceil(seconds / 60)
	if minutes < 120 then
		return "about " .. minutes .. " min"
	end
	local hours = math.ceil(minutes / 60)
	if hours > 99999 then
		return nil
	end
	return "about " .. hours .. " h"
end

-- What every Office rung shows. upgrades = the server's list ({ name, cost, income }) in buying order, owned[i] =
-- true for an upgrade the player owns (the Upgrade<i> attributes), cash and income = leaderstats, money = the Cash
-- format (ShopConfig.formatCash), bought = the upgrade just bought (its card stays the hero a moment, "Bought!"),
-- busy = a buy request is running ("..."). Returns:
--   count, owned (how many), incomeOwned (what they earn), nextIndex (nil once all are bought), complete,
--   summary = { title = "3 of 6 bought", info = "+$8/s" } (nil while none is owned),
--   banner = { title = "Office complete", info = ... } (only when complete),
--   rows[i] = { state = "owned" | "next" | "locked", info, button (nil: no button), color = "owned" | "buy" | "disabled" },
--   hero = { index, name, info, fill, progress, time, button, color, action, hint } for the next upgrade, where action
--   is "buy" (the only state that sends a request), "short" (not enough Cash: nothing is sent) or "wait"
function ShopLayout.ladder(upgrades, owned, cash, income, money, bought, busy)
	upgrades = upgrades or {}
	owned = owned or {}
	cash = math.max(0, finite(cash, 0))
	income = math.max(0, finite(income, 0))
	money = money or function(amount)
		return "$" .. tostring(math.floor(amount))
	end
	local S = { count = #upgrades, owned = 0, incomeOwned = 0, rows = {} }
	for i, upg in ipairs(upgrades) do
		local mine = owned[i] == true and i ~= bought
		if mine then
			S.owned += 1
			S.incomeOwned += math.max(0, finite(upg.income, 0))
			S.rows[i] = { state = "owned", info = "+" .. money(finite(upg.income, 0)) .. "/s", button = "Owned", color = "owned" }
		elseif S.nextIndex == nil then
			S.nextIndex = i
			S.rows[i] = { state = "next" }
		else
			local before = upgrades[i - 1]
			S.rows[i] = { state = "locked", info = "Unlocks after " .. tostring(before and before.name or "the one before"), color = "disabled" }
		end
	end
	S.complete = S.count > 0 and S.nextIndex == nil
	if S.owned > 0 then
		S.summary = { title = S.owned .. " of " .. S.count .. " bought", info = "+" .. money(S.incomeOwned) .. "/s" }
	end
	if S.complete then
		S.banner = { title = "Office complete", info = "Your next step: the IPO window" }
	end
	local i = S.nextIndex
	if i then
		local upg = upgrades[i]
		local cost = math.max(0, finite(upg.cost, 0))
		local H = { index = i, name = tostring(upg.name), info = "+" .. money(finite(upg.income, 0)) .. " every second" }
		H.fill = ShopLayout.barFill(cash, cost)
		H.progress = cost == 0 and "Free" or (money(math.min(cash, cost)) .. " / " .. money(cost))
		H.time = ShopLayout.timeText(cash, cost, income)
		if bought == i then
			H.button, H.color, H.action = "Bought!", "buy", "wait"
			H.fill, H.time = 1, nil
			H.progress = cost == 0 and "Free" or (money(cost) .. " / " .. money(cost))
		elseif busy then
			H.button, H.color, H.action = "...", "disabled", "wait"
		elseif cost == 0 then
			H.button, H.color, H.action = "Get it free", "buy", "buy"
		elseif cash >= cost then
			H.button, H.color, H.action = "Buy " .. money(cost), "buy", "buy"
		else
			H.button, H.color, H.action = "Need " .. money(math.ceil(cost - cash)) .. " more", "disabled", "short"
		end
		H.hint = H.time and (H.time .. " at your Income") or ("Your Income is " .. money(0) .. " a second right now")
		S.hero = H
		S.rows[i].button, S.rows[i].color = H.button, H.color
	end
	return S
end

-- One Office row that is not the hero, cardW wide: kind = "owned" (with its "Owned" button), "locked" (no button),
-- "summary" (the owned rungs folded: "Show"/"Hide" where the button would be) or "banner" ("Office complete").
-- Returns height and the rectangles icon, badge (a check or a padlock over the icon's corner, on purpose), name,
-- info and button (owned and summary only).
function ShopLayout.officeRow(cardW, kind)
	cardW = math.max(0, finite(cardW, 0))
	local narrow = cardW < ShopLayout.WIDE_CARD
	local h = narrow and ShopLayout.ROW_NARROW or ShopLayout.ROW_WIDE
	local R = { height = h, narrow = narrow }
	if kind == "banner" then
		R.name = rect(12, 6, cardW - 24, 26)
		R.info = narrow and rect(12, 32, cardW - 24, 36) or rect(12, 34, cardW - 24, 22)
		return R
	end
	R.icon = rect(8, math.floor((h - 48) / 2), 48, 48)
	R.badge = rect(R.icon.x + 30, R.icon.y + 30, 20, 20)
	local right = cardW - 8
	if kind == "owned" or kind == "summary" then
		local buttonW = narrow and 72 or 124
		R.button = rect(right - buttonW, math.floor((h - ShopLayout.BUTTON_H) / 2), buttonW, ShopLayout.BUTTON_H)
		right = R.button.x - 8
	end
	local textW = right - 64
	if narrow and R.button then -- the name may take two lines beside the button
		R.name = rect(64, 6, textW, 38)
		R.info = rect(64, 46, textW, 20)
	elseif narrow then -- "Unlocks after ..." may take two lines
		R.name = rect(64, 6, textW, 22)
		R.info = rect(64, 30, textW, 38)
	else
		R.name = rect(64, 8, textW, 24)
		R.info = rect(64, 34, textW, 22)
	end
	return R
end

-- The hero card (the next upgrade), cardW wide: height and the rectangles icon, name, info (what it earns), bar,
-- progress ("$12 / $25"), time ("about 7 s"), status (a refusal or a hint) and button. On a narrow card the status
-- takes the time's place (statusSharesTime) for its 3 s.
function ShopLayout.hero(cardW)
	cardW = math.max(0, finite(cardW, 0))
	local H = { narrow = cardW < ShopLayout.WIDE_CARD }
	if H.narrow then
		local textW = cardW - 96
		H.height = ShopLayout.HERO_NARROW
		H.icon = rect(8, 8, 72, 72)
		H.name = rect(88, 8, textW, 24)
		H.info = rect(88, 34, textW, 20)
		H.progress = rect(88, 56, textW, 20)
		H.bar = rect(8, 88, cardW - 16, 12)
		H.time = rect(8, 104, cardW - 16, 38)
		H.status = H.time
		H.button = rect(8, 146, cardW - 16, ShopLayout.BUTTON_H)
	else
		local buttonW = math.clamp(math.floor(cardW * 0.3), 120, 160)
		local textW = cardW - 92 - buttonW - 20
		local half = math.floor((cardW - 102) / 2)
		H.height = ShopLayout.HERO_WIDE
		H.icon = rect(10, 10, 72, 72)
		H.button = rect(cardW - 10 - buttonW, 10, buttonW, ShopLayout.BUTTON_H)
		H.name = rect(92, 10, textW, 24)
		H.info = rect(92, 36, textW, 20)
		H.bar = rect(92, 64, cardW - 102, 12)
		H.progress = rect(92, 80, half, 20)
		H.time = rect(92 + half, 80, cardW - 102 - half, 20)
		H.status = rect(10, 104, cardW - 20, 20)
	end
	H.statusSharesTime = H.narrow
	return H
end

-- The Office page from its top: the heights of the pieces shown, in order, and the gap between them. Returns the y
-- of each (same order) and the total height (the page's canvas).
function ShopLayout.stack(heights, gap)
	gap = math.max(0, finite(gap, 0))
	local ys, y = {}, 0
	for i, h in ipairs(heights or {}) do
		if i > 1 then
			y += gap
		end
		ys[i] = y
		y += math.max(0, finite(h, 0))
	end
	return ys, y
end

-- How far to scroll a page that shows view pixels so a piece at y, h tall, shows whole: the least scroll that shows
-- its bottom, never past its top, never past the end of the canvas (total)
function ShopLayout.revealScroll(y, h, view, total)
	y, h, view, total = finite(y, 0), finite(h, 0), finite(view, 0), finite(total, 0)
	local want = math.min(math.max(0, y + h - view), y)
	return math.clamp(want, 0, math.max(0, total - view))
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
