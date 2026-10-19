-- CreatureConfig: every creature employee, rarity and recruiting egg in one place (milestone 2).
-- Put this ModuleScript in ReplicatedStorage (the server and the screens both read it).
--
-- Safe to change any time: names, roles, incomes, prices, timers, odds, colors, looks.
-- Never change a "key" once players have that creature or egg: saves store the key.

local CreatureConfig = {}

CreatureConfig.BaseEmployeeSlots = 5 -- the Extra Employee Slots pass adds more (see ShopConfig)
CreatureConfig.Incubators = 3 -- how many eggs can incubate at the same time

-- Rarities from most common to rarest. luckBoosted = Luck Boost multiplies these odds.
CreatureConfig.Rarities = {
	{ key = "Common", color = Color3.fromRGB(190, 195, 205) },
	{ key = "Uncommon", color = Color3.fromRGB(90, 210, 100) },
	{ key = "Rare", color = Color3.fromRGB(70, 150, 255), luckBoosted = true },
	{ key = "Epic", color = Color3.fromRGB(180, 90, 255), luckBoosted = true },
	{ key = "Legendary", color = Color3.fromRGB(255, 195, 40), luckBoosted = true },
}

-- Recruiting eggs, bought with Cash. odds are weights per rarity (they don't have to add up to 100).
-- color, band and spots are the egg's looks (the incubator's egg and the hatch reveal); they never change a roll.
-- The hatch timer keeps running while you're offline.
CreatureConfig.Eggs = {
	{
		key = "Garage",
		name = "Garage Egg",
		price = 800,
		hatchSeconds = 60,
		color = Color3.fromRGB(165, 120, 75),
		band = Color3.fromRGB(240, 222, 180), spots = Color3.fromRGB(105, 70, 42), -- overhaul 2 phase 4: the egg's pattern (looks only)
		odds = { Common = 70, Uncommon = 25, Rare = 5 },
	},
	{
		key = "Startup",
		name = "Startup Egg",
		price = 40000,
		hatchSeconds = 5 * 60,
		color = Color3.fromRGB(60, 150, 255),
		band = Color3.fromRGB(245, 248, 255), spots = Color3.fromRGB(20, 55, 140),
		odds = { Common = 40, Uncommon = 35, Rare = 18, Epic = 6, Legendary = 1 },
	},
	{
		key = "Unicorn",
		name = "Unicorn Egg",
		price = 2000000,
		hatchSeconds = 15 * 60,
		color = Color3.fromRGB(255, 120, 210),
		band = Color3.fromRGB(255, 210, 80), spots = Color3.fromRGB(150, 240, 255),
		odds = { Common = 10, Uncommon = 25, Rare = 35, Epic = 22, Legendary = 8 },
	},
}

-- Creatures. income = Cash per second while they work for you (game pass bonuses apply on top).
-- look = the placeholder model: shape is "round", "boxy", "tall" or "long";
-- extras are the parts listed in CreatureModels (ears, wings, tie, laptop...).
CreatureConfig.Creatures = {
	-- Common
	{
		key = "CoffeeCapybara", name = "Coffee Capybara", rarity = "Common", role = "Intern", income = 2, emoji = "☕",
		look = { shape = "long", color = Color3.fromRGB(150, 105, 70), accent = Color3.fromRGB(95, 65, 45), extras = { "roundEars", "snout", "coffee" } },
	},
	{
		key = "CodingCat", name = "Coding Cat", rarity = "Common", role = "Junior Engineer", income = 3, emoji = "🐱",
		look = { shape = "round", color = Color3.fromRGB(255, 165, 70), accent = Color3.fromRGB(255, 235, 210), extras = { "catEars", "tail", "laptop" } },
	},
	{
		key = "PixelPigeon", name = "Pixel Pigeon", rarity = "Common", role = "Junior Designer", income = 3, emoji = "🐦",
		look = { shape = "round", scale = 0.9, color = Color3.fromRGB(150, 160, 185), accent = Color3.fromRGB(110, 200, 170), extras = { "wings", "beak" } },
	},
	-- Uncommon
	{
		key = "HustleHamster", name = "Hustle Hamster", rarity = "Uncommon", role = "Sales Rep", income = 7, emoji = "🐹",
		look = { shape = "round", scale = 0.85, color = Color3.fromRGB(235, 190, 120), accent = Color3.fromRGB(255, 245, 225), extras = { "roundEars", "headset" } },
	},
	{
		key = "BugBeetle", name = "Bug Beetle", rarity = "Uncommon", role = "QA Tester", income = 8, emoji = "🐞",
		look = { shape = "boxy", color = Color3.fromRGB(210, 40, 45), accent = Color3.fromRGB(30, 30, 35), extras = { "antennae", "spots" } },
	},
	{
		key = "MemoMole", name = "Memo Mole", rarity = "Uncommon", role = "Office Manager", income = 9, emoji = "📋",
		look = { shape = "tall", color = Color3.fromRGB(85, 70, 75), accent = Color3.fromRGB(255, 160, 180), extras = { "snout", "glasses" } },
	},
	-- Rare
	{
		key = "SalesShark", name = "Sales Shark", rarity = "Rare", role = "Sales Lead", income = 20, emoji = "🦈",
		look = { shape = "long", color = Color3.fromRGB(80, 130, 185), accent = Color3.fromRGB(235, 240, 245), extras = { "fin", "tail", "tie" } },
	},
	{
		key = "PitchParrot", name = "Pitch Parrot", rarity = "Rare", role = "Marketing Lead", income = 24, emoji = "🦜",
		look = { shape = "tall", color = Color3.fromRGB(40, 190, 90), accent = Color3.fromRGB(255, 80, 60), extras = { "wings", "beak", "crest" } },
	},
	-- Epic
	{
		key = "ServerSloth", name = "Server Sloth", rarity = "Epic", role = "Senior Engineer", income = 50, emoji = "🦥",
		look = { shape = "boxy", scale = 1.1, color = Color3.fromRGB(140, 115, 90), accent = Color3.fromRGB(60, 255, 140), extras = { "roundEars", "headset", "laptop" } },
	},
	{
		key = "LedgerLlama", name = "Ledger Llama", rarity = "Epic", role = "CFO", income = 60, emoji = "🦙",
		look = { shape = "tall", scale = 1.1, color = Color3.fromRGB(245, 235, 215), accent = Color3.fromRGB(30, 30, 40), extras = { "longNeck", "longEars", "glasses", "tie" } },
	},
	-- Legendary
	{
		key = "UnicornCEO", name = "Unicorn CEO", rarity = "Legendary", role = "CEO", income = 150, emoji = "🦄",
		look = { shape = "round", scale = 1.2, color = Color3.fromRGB(255, 250, 255), accent = Color3.fromRGB(255, 120, 220), extras = { "horn", "longEars", "tail", "crown" } },
	},
	{
		key = "VentureDragon", name = "Venture Dragon", rarity = "Legendary", role = "Lead Investor", income = 175, emoji = "🐉",
		look = { shape = "long", scale = 1.25, color = Color3.fromRGB(120, 40, 170), accent = Color3.fromRGB(255, 190, 40), extras = { "wings", "spikes", "tail", "horn" } },
	},
}

-- Poaching: hiring employees away from other players in the same server (milestone 3 poaching).
-- Chances go from 0 to 1 (0.4 = 40%). Times are in seconds. Shields and protection only count
-- down while you're playing (offline players can't be poached anyway).
CreatureConfig.Poaching = {
	-- Chance to win the negotiation, by rarity. false = can never be poached.
	BaseChance = { Common = 0.6, Uncommon = 0.5, Rare = 0.4, Epic = 0.3, Legendary = false },
	MinChance = 0.05, -- however strong the HR Department, the chance never drops below this
	MaxChance = 0.9,
	CostIncomeSeconds = 300, -- a poach costs this many seconds of the employee's income...
	MinCost = 500, -- ...but never less than this
	NegotiationSeconds = { 8, 10 }, -- each negotiation takes a random time between these two
	AttackerCooldown = 30, -- wait between two poaching attempts
	ShieldAfterPoach = 10 * 60, -- after losing an employee, nobody can poach you for this long
	CounterOfferSeconds = 5 * 60, -- time to buy the poached employee back (once)
	CounterOfferPrice = 0.5, -- buy-back price, as a share of what the poacher paid; the poacher gets it
	MaxLosses = 1, -- a player loses at most this many employees...
	LossWindow = 10 * 60, -- ...in this much time
	NewPlayerShield = 15 * 60, -- brand-new players are protected for their first minutes of play
	-- HR Department: defense levels bought with Cash on the purple pad in the garage.
	-- defense is taken off every poacher's chance (0.05 = 5% less).
	HRDepartment = {
		{ cost = 5000, defense = 0.05 }, -- overhaul 2: priced along the new ladder (Garage, Seed, Series A, B, C)
		{ cost = 150000, defense = 0.1 },
		{ cost = 3000000, defense = 0.15 },
		{ cost = 40000000, defense = 0.2 },
		{ cost = 200000000, defense = 0.25 },
	},
}

-- Helpers used by both the server and the screens -----------------------

local function findBy(list, key)
	for _, item in ipairs(list) do
		if item.key == key then
			return item
		end
	end
	return nil
end

function CreatureConfig.getCreature(key)
	return findBy(CreatureConfig.Creatures, key)
end

function CreatureConfig.getEgg(key)
	return findBy(CreatureConfig.Eggs, key)
end

function CreatureConfig.getRarity(key)
	return findBy(CreatureConfig.Rarities, key)
end

function CreatureConfig.creaturesOfRarity(rarityKey)
	local list = {}
	for _, creature in ipairs(CreatureConfig.Creatures) do
		if creature.rarity == rarityKey then
			table.insert(list, creature)
		end
	end
	return list
end

-- The real chance of each rarity for an egg, as a list from common to rare:
-- { { rarity = "Common", chance = 0.667 }, ... }. Chances always add up to 1.
-- luckMultiplier (2 during Luck Boost) multiplies the weight of luckBoosted rarities,
-- then everything is scaled back down so it adds up to 100% again.
function CreatureConfig.getOdds(egg, luckMultiplier)
	local odds, total = {}, 0
	for _, rarity in ipairs(CreatureConfig.Rarities) do
		local weight = egg.odds[rarity.key] or 0
		if rarity.luckBoosted then
			weight *= luckMultiplier or 1
		end
		if weight > 0 then
			table.insert(odds, { rarity = rarity.key, weight = weight })
			total += weight
		end
	end
	for _, entry in ipairs(odds) do
		entry.chance = entry.weight / total
	end
	return odds
end

-- What the screens show (Roblox's Paid Random Items policy: every possible hire is shown with its own
-- odds before buying, the shown numbers add up to exactly 100%, and they change live with luck).
-- Built from getOdds, the same numbers the server rolls with: the rarity is rolled first, then one
-- creature of that rarity is picked, all of them equally likely.
-- Returns a list, common to rare (config order inside a rarity):
--   { creature = <Creatures entry>, rarity = "Common", chance = 0.1333..., units = 1333 }
-- units are hundredths of a percent (ODDS_UNITS = 100%). They're rounded with the largest-remainder
-- method inside each rarity (rarities first, then the creatures of a rarity), so the rarities add up to
-- exactly ODDS_UNITS, each rarity's creatures add up to that rarity's number, and every possible hire
-- shows at least 0.01%.
CreatureConfig.ODDS_UNITS = 10000

-- Largest-remainder rounding: whole numbers (never negative) that add up to exactly `total`, each one the
-- floor or the floor + 1 of its exact value. Ties go to the earlier entry. `exact` is a list of numbers.
local function largestRemainder(exact, total)
	local result, used, byRemainder = {}, 0, {}
	for i, value in ipairs(exact) do
		result[i] = math.floor(value)
		used += result[i]
		table.insert(byRemainder, { index = i, remainder = value - result[i] })
	end
	table.sort(byRemainder, function(a, b)
		if a.remainder ~= b.remainder then
			return a.remainder > b.remainder
		end
		return a.index < b.index
	end)
	local i = 1
	while used < total and #byRemainder > 0 do
		result[byRemainder[i].index] += 1
		used += 1
		i = i % #byRemainder + 1
	end
	return result
end

function CreatureConfig.getCreatureOdds(egg, luckMultiplier)
	-- Rounding is done inside each rarity: first the rarities (largest remainder, so a 70% rarity shows
	-- 70.00%, not 69.99%), then the creatures of that rarity share their rarity's units. Display only:
	-- the server rolls with getOdds, never with these units.
	local rarities = CreatureConfig.getOdds(egg, luckMultiplier)
	local exactRarity = {}
	for i, entry in ipairs(rarities) do
		exactRarity[i] = entry.chance * CreatureConfig.ODDS_UNITS
	end
	local rarityUnits = largestRemainder(exactRarity, CreatureConfig.ODDS_UNITS)

	local list = {}
	for r, entry in ipairs(rarities) do
		local creatures = CreatureConfig.creaturesOfRarity(entry.rarity)
		local exactCreature = {}
		for c = 1, #creatures do
			exactCreature[c] = rarityUnits[r] / #creatures
		end
		local creatureUnits = largestRemainder(exactCreature, rarityUnits[r])
		for c, creature in ipairs(creatures) do
			table.insert(list, { creature = creature, rarity = entry.rarity, chance = entry.chance / #creatures, units = creatureUnits[c] })
		end
	end
	-- A possible hire never shows 0.00%: it gets 0.01%, taken from the most likely one
	for _, item in ipairs(list) do
		if item.units == 0 then
			local largest = list[1]
			for _, other in ipairs(list) do
				if other.units > largest.units then
					largest = other
				end
			end
			largest.units -= 1
			item.units = 1
		end
	end
	return list
end

-- The same odds added up per rarity (common to rare): { { rarity = "Common", units = 4000 }, ... }.
-- They're sums of the rounded per-creature units, which are rounded inside each rarity, so they are the
-- rounded rarity chances and add up to exactly 100%.
function CreatureConfig.rarityOdds(creatureOdds)
	local summary, byRarity = {}, {}
	for _, item in ipairs(creatureOdds) do
		local entry = byRarity[item.rarity]
		if not entry then
			entry = { rarity = item.rarity, units = 0 }
			byRarity[item.rarity] = entry
			table.insert(summary, entry)
		end
		entry.units += item.units
	end
	return summary
end

-- Fixed hire order (Roblox's Paid Random Items policy, review finding FR-13, decision D9 option B).
-- A player for whom paid random items are restricted (PolicyService, asked on every join) gets no
-- random roll: each egg hires in a fixed order, known before buying, that follows the same odds.
-- The order goes in rounds of FIXED_ORDER_LENGTH hires. In every round each rarity comes up its share
-- of the 100 (getOdds, the numbers the server rolls with, rounded with the largest-remainder method so
-- they add up to exactly 100), spread out evenly, most common first. Inside a rarity the creatures take
-- turns, so after a few rounds every creature has come up exactly as often as its own odds say.
-- Same egg, luck and count: always the same hire, on the server and on every screen.
CreatureConfig.FIXED_ORDER_LENGTH = 100

-- The rarities of one round, in order: { "Common", "Uncommon", "Common", ... } (FIXED_ORDER_LENGTH long)
function CreatureConfig.fixedOrder(egg, luckMultiplier)
	local length = CreatureConfig.FIXED_ORDER_LENGTH
	local odds = CreatureConfig.getOdds(egg, luckMultiplier)
	if #odds == 0 then return {} end

	-- Places per rarity: round down, then the biggest remainders get one more (ties: the more common)
	local total, byRemainder = 0, {}
	for i, entry in ipairs(odds) do
		local exact = entry.chance * length
		entry.places = math.floor(exact)
		total += entry.places
		table.insert(byRemainder, { entry = entry, remainder = exact - entry.places, order = i })
	end
	table.sort(byRemainder, function(a, b)
		if a.remainder ~= b.remainder then
			return a.remainder > b.remainder
		end
		return a.order < b.order
	end)
	local i = 1
	while total < length do
		byRemainder[i].entry.places += 1
		total += 1
		i = i % #byRemainder + 1
	end
	-- A possible rarity always gets at least one place, taken from the one with the most
	for _, entry in ipairs(odds) do
		if entry.places == 0 then
			local largest = odds[1]
			for _, other in ipairs(odds) do
				if other.places > largest.places then
					largest = other
				end
			end
			largest.places -= 1
			entry.places = 1
		end
	end

	-- Spread them out (smooth weighted round-robin): at every step each rarity earns its places, the
	-- one with the most credit goes next and pays back a whole round. Ties: the more common rarity.
	-- After the round every rarity has come up exactly its number of places.
	local order, credit = {}, {}
	for _ = 1, length do
		local best
		for j, entry in ipairs(odds) do
			credit[j] = (credit[j] or 0) + entry.places
			if not best or credit[j] > credit[best] then
				best = j
			end
		end
		credit[best] -= length
		table.insert(order, odds[best].rarity)
	end
	return order
end

-- The creature of the next fixed hire from this egg. count = fixed hires already made from it
-- (EmployeeServer saves it per egg in the fixedHires section). Returns a Creatures entry.
function CreatureConfig.fixedHire(egg, luckMultiplier, count)
	local order = CreatureConfig.fixedOrder(egg, luckMultiplier)
	if #order == 0 then return nil end
	local round, place = count // #order, count % #order + 1
	local rarity = order[place]
	-- Whose turn it is inside the rarity: its places in the earlier rounds, plus the ones before this one
	local before, perRound = 0, 0
	for i, other in ipairs(order) do
		if other == rarity then
			perRound += 1
			if i < place then
				before += 1
			end
		end
	end
	local creatures = CreatureConfig.creaturesOfRarity(rarity)
	return creatures[(round * perRound + before) % #creatures + 1]
end

-- 1333 -> "13.33%", 10000 -> "100.00%"
function CreatureConfig.formatOdds(units)
	return string.format("%d.%02d%%", units // 100, units % 100)
end

-- 75 -> "1:15", 3725 -> "1:02:05"
function CreatureConfig.formatTime(seconds)
	seconds = math.max(0, math.ceil(seconds))
	local h, m, s = seconds // 3600, (seconds // 60) % 60, seconds % 60
	if h > 0 then
		return string.format("%d:%02d:%02d", h, m, s)
	end
	return string.format("%d:%02d", m, s)
end

-- What poaching this creature costs (the poacher pays it before the negotiation starts)
function CreatureConfig.poachCost(creature)
	local rules = CreatureConfig.Poaching
	return math.max(rules.MinCost, math.floor(creature.income * rules.CostIncomeSeconds))
end

-- How much an HR Department level takes off poaching chances (level 0 = no HR Department)
function CreatureConfig.hrDefense(level)
	local info = CreatureConfig.Poaching.HRDepartment[level]
	return info and info.defense or 0
end

-- Chance (0 to 1) that poaching this creature works, or nil if it can never be poached.
-- defense = the target's HR Department, bonus = the poacher's Headhunter pass.
-- Only the server's number counts; screens use this to show it.
function CreatureConfig.poachChance(creature, defense, bonus)
	local rules = CreatureConfig.Poaching
	local base = rules.BaseChance[creature.rarity]
	if not base then
		return nil
	end
	return math.clamp(base - (defense or 0) + (bonus or 0), rules.MinChance, rules.MaxChance)
end

-- Warn early about mistakes in the lists above
do
	local seen = {}
	for _, list in ipairs({ CreatureConfig.Creatures, CreatureConfig.Eggs }) do
		for _, item in ipairs(list) do
			if seen[item.key] then
				warn("CreatureConfig: duplicate key " .. item.key)
			end
			seen[item.key] = true
		end
	end
	for _, creature in ipairs(CreatureConfig.Creatures) do
		if not CreatureConfig.getRarity(creature.rarity) then
			warn("CreatureConfig: " .. creature.name .. " has unknown rarity " .. tostring(creature.rarity))
		end
	end
	for _, egg in ipairs(CreatureConfig.Eggs) do
		for rarityKey, weight in pairs(egg.odds) do
			if weight > 0 and #CreatureConfig.creaturesOfRarity(rarityKey) == 0 then
				warn("CreatureConfig: " .. egg.name .. " can roll " .. rarityKey .. " but no creature has that rarity")
			end
		end
	end
	for _, rarity in ipairs(CreatureConfig.Rarities) do
		if CreatureConfig.Poaching.BaseChance[rarity.key] == nil then
			warn("CreatureConfig: Poaching.BaseChance needs " .. rarity.key .. " (a chance, or false)")
		end
	end
end

return CreatureConfig
