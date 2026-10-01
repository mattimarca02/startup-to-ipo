-- IpoConfig: the IPO rebirth rules in one place (milestone 4).
-- Put this ModuleScript in ReplicatedStorage (the server and the IPO screen both read it).
--
-- Valuation = all the Cash your startup earned (income, offline earnings and Cash packs).
-- It climbs through funding stages; at the last one you can go public ("IPO").
-- Going public resets your Cash, garage upgrades and eggs in incubators (see Resets below),
-- and in return gives a permanent income multiplier and Shares to spend on permanent perks.
-- Employees, the HR Department, game passes, boosts, shields, Shares and perks are all kept.
--
-- Safe to change any time: thresholds, rewards, perk prices and effects.
-- Never change a perk "key" once players have bought it: saves store the key.

local IpoConfig = {}

-- Funding stages, from start to IPO. valuation = what you need to reach that stage on your
-- current run (since your last IPO). The last stage is the one that lets you go public.
IpoConfig.Stages = {
	{ key = "Garage", name = "Garage", icon = "🏚️", valuation = 0 },
	{ key = "Seed", name = "Seed", icon = "🌱", valuation = 2500 },
	{ key = "SeriesA", name = "Series A", icon = "💼", valuation = 25000 },
	{ key = "SeriesB", name = "Series B", icon = "🚀", valuation = 250000 },
	{ key = "IpoReady", name = "IPO-ready", icon = "🔔", valuation = 2500000 },
}
-- Every IPO you've done makes the stages of the next run this many times bigger (1 = never grows)
IpoConfig.StageGrowthPerIpo = 1.5

-- Permanent income multiplier: 1 + BonusPerIpo * IPOs ^ BonusExponent.
-- An exponent below 1 makes each IPO add a bit less than the one before (x1.5, x1.84, x2.14...).
-- It stacks with game passes: 2x Cash + x1.5 = x3.
IpoConfig.BonusPerIpo = 0.5
IpoConfig.BonusExponent = 0.75

-- Shares from an IPO: SharesPerIpo * (valuation / IPO-ready valuation) ^ SharesExponent.
-- Going public exactly at IPO-ready gives SharesPerIpo; waiting until 4x gives twice as many.
-- The Shareholder pass multiplies this (see ShopConfig).
IpoConfig.SharesPerIpo = 10
IpoConfig.SharesExponent = 0.5

IpoConfig.StartingCash = 0 -- Cash after an IPO (the first garage upgrade is free)
IpoConfig.CooldownSeconds = 60 -- wait at least this long between two IPOs

-- What going public resets (true) or keeps (false). The IPO screen lists them from here.
-- Always kept: employees, game passes, boosts, shields, Shares, perks and the IPO count.
-- Always reset: the valuation (it's what the next IPO is measured on).
IpoConfig.Resets = {
	Cash = true, -- back to StartingCash
	Upgrades = true, -- garage upgrades and the green pad
	Eggs = true, -- eggs in incubators
	HRDepartment = false, -- ROADMAP M4: the HR level is kept
}
-- How the IPO screen names each one, in this order
IpoConfig.ResetNames = {
	{ key = "Cash", name = "Cash" },
	{ key = "Upgrades", name = "garage upgrades" },
	{ key = "Eggs", name = "eggs in incubators" },
	{ key = "HRDepartment", name = "HR Department" },
}

-- IPO shop: permanent perks bought with Shares. Each level adds perLevel (see "effect" for
-- what that number means). costs[n] = Shares for level n, so #costs is the max level.
IpoConfig.Perks = {
	{
		key = "FasterEggs", name = "Faster Recruiting", icon = "⏱️",
		description = "Eggs hatch faster.", perLevel = 0.1, effect = "hatchTime", -- -10% hatch time per level
		costs = { 5, 10, 20, 35, 50 },
	},
	{
		key = "ExtraIncubator", name = "Extra Incubator", icon = "🥚",
		description = "One more egg can incubate at the same time.", perLevel = 1, effect = "incubators",
		costs = { 15, 40 },
	},
	{
		key = "ExtraSlot", name = "Extra Desk", icon = "🪑",
		description = "One more employee on your team.", perLevel = 1, effect = "employeeSlots",
		costs = { 10, 25, 50 },
	},
	{
		key = "OfflineCap", name = "Night Shift", icon = "🌙",
		description = "Offline earnings keep going for longer.", perLevel = 2 * 60 * 60, effect = "offlineSeconds", -- +2 hours per level
		costs = { 5, 10, 20, 35 },
	},
	{
		key = "BaseLuck", name = "Talent Scouts", icon = "🍀",
		description = "Better odds for Rare, Epic and Legendary hires.", perLevel = 0.1, effect = "luck", -- +10% luck per level
		costs = { 5, 10, 20, 35, 50 },
	},
	{
		key = "CheaperPoach", name = "Recruiter Network", icon = "🤝",
		description = "Poaching costs less.", perLevel = 0.05, effect = "poachDiscount", -- -5% poach cost per level
		costs = { 5, 10, 15, 20, 25 },
	},
}

-- Helpers used by both the server and the IPO screen ----------------------

function IpoConfig.getPerk(key)
	for _, perk in ipairs(IpoConfig.Perks) do
		if perk.key == key then
			return perk
		end
	end
	return nil
end

-- The ResetNames entries an IPO resets (reset = true) or keeps (reset = false)
function IpoConfig.resetItems(reset)
	local items = {}
	for _, item in ipairs(IpoConfig.ResetNames) do
		if (IpoConfig.Resets[item.key] == true) == reset then
			table.insert(items, item)
		end
	end
	return items
end

-- What a perk adds at this level (0 when you don't have it)
function IpoConfig.perkValue(key, level)
	local perk = IpoConfig.getPerk(key)
	if not perk then return 0 end
	return perk.perLevel * math.clamp(level or 0, 0, #perk.costs)
end

-- Valuation needed for stage `index` on a run after `ipoCount` IPOs
function IpoConfig.stageValuation(index, ipoCount)
	local stage = IpoConfig.Stages[index]
	return math.floor(stage.valuation * IpoConfig.StageGrowthPerIpo ^ (ipoCount or 0))
end

-- Valuation needed to go public on a run after `ipoCount` IPOs
function IpoConfig.ipoValuation(ipoCount)
	return IpoConfig.stageValuation(#IpoConfig.Stages, ipoCount)
end

-- The stage you're at (index into Stages) for this valuation
function IpoConfig.stageIndex(valuation, ipoCount)
	local index = 1
	for i = 1, #IpoConfig.Stages do
		if valuation >= IpoConfig.stageValuation(i, ipoCount) then
			index = i
		end
	end
	return index
end

-- The permanent income multiplier after `count` IPOs (0 IPOs = x1)
function IpoConfig.multiplier(count)
	if count <= 0 then return 1 end
	return 1 + IpoConfig.BonusPerIpo * count ^ IpoConfig.BonusExponent
end

-- Shares for going public now. passMultiplier = 2 with the Shareholder pass.
function IpoConfig.sharesFor(valuation, ipoCount, passMultiplier)
	local ratio = math.max(0, valuation / IpoConfig.ipoValuation(ipoCount))
	return math.floor(IpoConfig.SharesPerIpo * ratio ^ IpoConfig.SharesExponent * (passMultiplier or 1))
end

-- 1.5 -> "x1.5", 2 -> "x2"
function IpoConfig.formatMultiplier(multiplier)
	local text = string.format("%.2f", multiplier):gsub("0+$", ""):gsub("%.$", "")
	return "x" .. text
end

-- 1234 -> "$1.2K", 2500000 -> "$2.5M" (short, for the HUD and signs)
function IpoConfig.formatShort(amount)
	local units = { { 1e12, "T" }, { 1e9, "B" }, { 1e6, "M" }, { 1e3, "K" } }
	for _, unit in ipairs(units) do
		if amount >= unit[1] then
			local text = string.format("%.1f", amount / unit[1]):gsub("%.0$", "")
			return "$" .. text .. unit[2]
		end
	end
	return "$" .. math.floor(amount)
end

-- Warn early about numbers that would break the IPO
do
	local last = -1
	for i, stage in ipairs(IpoConfig.Stages) do
		if stage.valuation <= last then
			warn("IpoConfig: stage " .. stage.key .. " must need more valuation than the one before it")
		end
		last = stage.valuation
		if i == 1 and stage.valuation ~= 0 then
			warn("IpoConfig: the first stage must start at 0")
		end
	end
	if IpoConfig.StageGrowthPerIpo < 1 then
		warn("IpoConfig: StageGrowthPerIpo below 1 would make every IPO easier than the last")
	end
	if IpoConfig.BonusPerIpo <= 0 then
		warn("IpoConfig: BonusPerIpo must be more than 0, or an IPO gives no multiplier")
	end
	local seen = {}
	for _, perk in ipairs(IpoConfig.Perks) do
		if seen[perk.key] then
			warn("IpoConfig: duplicate perk key " .. perk.key)
		end
		seen[perk.key] = true
		if #perk.costs == 0 then
			warn("IpoConfig: perk " .. perk.key .. " needs at least one cost")
		end
	end
end

return IpoConfig
