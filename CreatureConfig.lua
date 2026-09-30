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
-- The hatch timer keeps running while you're offline.
CreatureConfig.Eggs = {
	{
		key = "Garage",
		name = "Garage Egg",
		price = 250,
		hatchSeconds = 60,
		color = Color3.fromRGB(165, 120, 75),
		odds = { Common = 70, Uncommon = 25, Rare = 5 },
	},
	{
		key = "Startup",
		name = "Startup Egg",
		price = 2500,
		hatchSeconds = 5 * 60,
		color = Color3.fromRGB(60, 150, 255),
		odds = { Common = 40, Uncommon = 35, Rare = 18, Epic = 6, Legendary = 1 },
	},
	{
		key = "Unicorn",
		name = "Unicorn Egg",
		price = 25000,
		hatchSeconds = 15 * 60,
		color = Color3.fromRGB(255, 120, 210),
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

-- 75 -> "1:15", 3725 -> "1:02:05"
function CreatureConfig.formatTime(seconds)
	seconds = math.max(0, math.ceil(seconds))
	local h, m, s = seconds // 3600, (seconds // 60) % 60, seconds % 60
	if h > 0 then
		return string.format("%d:%02d:%02d", h, m, s)
	end
	return string.format("%d:%02d", m, s)
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
end

return CreatureConfig
