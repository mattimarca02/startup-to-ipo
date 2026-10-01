-- ShopConfig: every game pass and developer product in the game, in one place (milestone 3).
-- Put this ModuleScript in ReplicatedStorage (the server and the shop screen both read it).
--
-- How to use:
--   1. Create each item in Creator Hub (your experience > Monetization > Passes / Developer Products).
--   2. Paste its ID into the matching "id" below. id = 0 means "not created yet":
--      the shop shows it as "Coming soon" and it can't be bought.
--   3. Keep "price" the same as the price you set in Creator Hub. Roblox always charges
--      the Creator Hub price; this number is only what the shop displays.
-- No IDs or prices are written anywhere else in the game.

local ShopConfig = {}

-- Sells the egg items (needsEggs = true). While false they show "Coming soon" in the shop.
-- After turning it on, run sync_monetization so Roblox puts them on sale too.
ShopConfig.EggsEnabled = false

-- Studio-only Debug tab for testing without Robux. It never works in live servers.
ShopConfig.DebugInStudio = true

-- Game passes: bought once, owned forever. Cash multipliers stack (2x Cash + VIP = 3x).
ShopConfig.Passes = {
	{
		key = "DoubleCash",
		name = "2x Cash",
		description = "Double all the Cash your startup earns, forever.",
		icon = "💰",
		price = 199,
		id = 1998261947,
		effect = { cashMultiplier = 2 },
	},
	{
		key = "VIP",
		name = "VIP",
		description = "+50% Cash, a gold [VIP] chat tag and entry to the VIP Lounge.",
		icon = "👑",
		price = 249,
		id = 2002622694,
		effect = { cashMultiplier = 1.5, chatTag = "VIP", chatTagColor = "#FFD24A", vipLounge = true },
	},
	{
		key = "ExtraSlots",
		name = "Extra Employee Slots",
		description = "Hire 3 more creature employees at the same time.",
		icon = "🪑",
		price = 149,
		id = 1998075790,
		needsEggs = true,
		effect = { extraEmployeeSlots = 3 },
	},
	{
		key = "AutoHatch",
		name = "Auto-Hatch",
		description = "Recruiting eggs hatch by themselves. No clicking needed.",
		icon = "🥚",
		price = 199,
		id = 2002694731,
		needsEggs = true,
		effect = { autoHatch = true },
	},
	{
		key = "Headhunter",
		name = "Headhunter",
		description = "+10% success chance every time you poach an employee.",
		icon = "🎯",
		price = 149,
		id = 1998465892,
		effect = { poachBonus = 0.1 },
	},
	{
		key = "Shareholder",
		name = "Shareholder",
		description = "Get 2x Shares every time you go public (IPO).",
		icon = "📜",
		price = 199,
		id = 2001728902,
		effect = { sharesMultiplier = 2 },
	},
}

-- Developer products: can be bought again and again. tab = which shop tab shows it.
ShopConfig.Products = {
	{
		key = "CashSmall",
		tab = "Cash",
		name = "Pile of Cash",
		description = "10 minutes of your income, instantly.",
		icon = "💵",
		price = 29,
		id = 3715692111,
		effect = { incomeMinutes = 10, minCash = 250 },
	},
	{
		key = "CashMedium",
		tab = "Cash",
		name = "Bag of Cash",
		description = "45 minutes of your income, instantly.",
		icon = "💰",
		price = 99,
		id = 3715692112,
		effect = { incomeMinutes = 45, minCash = 2500 },
	},
	{
		key = "CashLarge",
		tab = "Cash",
		name = "Vault of Cash",
		description = "3 hours of your income, instantly.",
		icon = "🏦",
		price = 299,
		id = 3715692113,
		effect = { incomeMinutes = 180, minCash = 15000 },
	},
	{
		key = "LuckBoost",
		tab = "Boosts",
		name = "Luck Boost",
		description = "Legendary chance 8.0% -> 9.7% (Unicorn Egg) for 15 min. Buy again to add time.",
		icon = "🍀",
		price = 49,
		id = 3715692114,
		needsEggs = true,
		effect = { luckMinutes = 15, luckMultiplier = 2 },
	},
	{
		key = "InstantHatch",
		tab = "Boosts",
		name = "Instant Hatch",
		description = "Skip the timer on one recruiting egg.",
		icon = "⚡",
		price = 25,
		id = 3715692116,
		needsEggs = true,
		effect = { instantHatches = 1 },
	},
	{
		key = "PoachShield",
		tab = "Boosts",
		name = "Poach Shield",
		description = "Nobody can poach your employees for 1 hour. Buy again to add time.",
		icon = "🛡️",
		price = 49,
		id = 3715702908,
		effect = { shieldMinutes = 60 },
	},
}

-- Helpers used by both the server and the shop screen -------------------

local function findBy(list, field, value)
	for _, item in ipairs(list) do
		if item[field] == value then
			return item
		end
	end
	return nil
end

function ShopConfig.getPass(key)
	return findBy(ShopConfig.Passes, "key", key)
end

function ShopConfig.getProduct(key)
	return findBy(ShopConfig.Products, "key", key)
end

-- id 0 is only a placeholder, so it never matches a real purchase
function ShopConfig.getPassById(id)
	if id == 0 then return nil end
	return findBy(ShopConfig.Passes, "id", id)
end

function ShopConfig.getProductById(id)
	if id == 0 then return nil end
	return findBy(ShopConfig.Products, "id", id)
end

-- Can this item be bought right now?
function ShopConfig.isForSale(item)
	return item.id ~= 0 and (not item.needsEggs or ShopConfig.EggsEnabled)
end

-- Cash packs scale with what you earn: X minutes of your current income per second,
-- but never less than minCash, so brand-new players still get something useful.
function ShopConfig.cashPackAmount(product, incomePerSecond)
	local effect = product.effect
	return math.max(effect.minCash or 0, math.floor(incomePerSecond * 60 * effect.incomeMinutes))
end

-- 1234567 -> "$1,234,567"
function ShopConfig.formatCash(amount)
	local digits = tostring(math.floor(amount))
	local withCommas = digits:reverse():gsub("(%d%d%d)", "%1,"):reverse():gsub("^,", "")
	return "$" .. withCommas
end

-- Warn early if two items accidentally share a key or an ID
do
	local seenKeys, seenIds = {}, {}
	for _, list in ipairs({ ShopConfig.Passes, ShopConfig.Products }) do
		for _, item in ipairs(list) do
			if seenKeys[item.key] then
				warn("ShopConfig: duplicate key " .. item.key)
			end
			seenKeys[item.key] = true
			if item.id ~= 0 then
				if seenIds[item.id] then
					warn("ShopConfig: " .. item.name .. " has the same ID as " .. seenIds[item.id])
				end
				seenIds[item.id] = item.name
			end
		end
	end
end

return ShopConfig
