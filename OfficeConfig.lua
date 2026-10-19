-- OfficeConfig: what the office sells, in one place (overhaul 2, docs/OVERHAUL2_PLAN.md).
-- Put this ModuleScript in ReplicatedStorage (the server and the shop screen both read it).
--
--   Items      the office catalog: 63 things a startup buys on its way to the IPO, by funding stage. The first six keys
--              (Desk, Coffee Machine, Laptop, Server Rack, Whiteboard, Neon Logo) are the old garage upgrades: their names
--              are saved in the `owned` list, so they never change. Every name of an owned item is saved in `owned`
--              (older code loads and writes back any name there), and an IPO clears them, like the old upgrades.
--   Buildings  one per funding stage: reaching the stage unlocks it in the shop, the player buys it (never automatic).
--              The building owned multiplies the income of the items (office) and of the employees (team).
--   Desks      workstations for employees: 1 free, 4 to buy (kept through an IPO: the `office` save section).
--              The Extra Employee Slots pass gives 3 more for free and the Extra Desk IPO perk 1 per level.
--   Hires      employees bought for Cash: a fixed creature for a fixed price (no roll, so FR-13 is untouched), priced so
--              an egg is always the better deal (HireFactor times what an egg pays on average for one of that rarity).
--
-- Every price and number here is the server's: the client only shows them. Prices and incomes come from
-- tools/economy_sim.py --o2 (docs/ECONOMY.md section 10). Never rename a key once players own it.
-- No text here may claim odds or chance (D9).

local OfficeConfig = {}

OfficeConfig.StageNames = { "Garage", "Seed", "Series A", "Series B", "Series C", "IPO-ready" } -- IpoConfig.Stages order

-- The catalog. stage = the funding stage that unlocks it (1 Garage ... 6 IPO-ready), price = Cash, income = Cash per
-- second before the building's office multiplier. effect (optional): calls / sprint / bug / brainstorm / pitch = that
-- activity pays this share more (0.2 = +20%; brainstorm: its boosts are this much stronger), hatch = eggs hatch this
-- share faster, unlock = the founder activity it starts ("bug": the production bug).
OfficeConfig.Items = {
--ITEMS-START
	-- Garage (stage 1)
	{ key = "Desk", icon = "🪑", stage = 1, price = 0, income = 1, text = "Your founder desk: calls and the coding sprint start here." },
	{ key = "Coffee Machine", icon = "☕", stage = 1, price = 120, income = 1, text = "Fuel for long nights." },
	{ key = "Second Monitor", icon = "🖥️", stage = 1, price = 250, income = 0, effect = { sprint = 0.25 }, text = "Coding sprints pay 25% more." },
	{ key = "Laptop", icon = "💻", stage = 1, price = 450, income = 1, text = "Work from anywhere in the garage." },
	{ key = "Router", icon = "📡", stage = 1, price = 700, income = 0, effect = { calls = 0.2 }, text = "Calls pay 20% more." },
	{ key = "Better Chair", icon = "💺", stage = 1, price = 1000, income = 0, effect = { sprint = 0.2 }, text = "Coding sprints pay 20% more." },
	{ key = "Mini Fridge", icon = "🧃", stage = 1, price = 1400, income = 0, effect = { brainstorm = 0.3 }, text = "Snacks for brainstorms: boosts 30% stronger." },
	{ key = "Server Rack", icon = "🗄️", stage = 1, price = 2000, income = 1, effect = { unlock = "bug" }, text = "Your first servers. Production bugs start ringing." },
	{ key = "Whiteboard", icon = "📋", stage = 1, price = 2800, income = 0, effect = { brainstorm = 0.5 }, text = "Brainstorm boosts are 50% stronger." },
	{ key = "Bookshelf", icon = "📚", stage = 1, price = 3800, income = 0, effect = { pitch = 0.2 }, text = "Startup books: pitch bonuses are 20% bigger." },
	{ key = "Neon Logo", icon = "💡", stage = 1, price = 5500, income = 2, text = "Your name in lights." },
	-- Seed (stage 2)
	{ key = "Standing Desks", icon = "🧍", stage = 2, price = 15000, income = 23, text = "Healthier, faster founders." },
	{ key = "Team Table", icon = "🍽️", stage = 2, price = 30000, income = 32, text = "Lunch together, ship together." },
	{ key = "Phone Booth", icon = "📞", stage = 2, price = 50000, income = 0, effect = { calls = 0.25 }, text = "Quiet calls: calls pay 25% more." },
	{ key = "Meeting Corner", icon = "🗣️", stage = 2, price = 80000, income = 45, text = "A real spot for real meetings." },
	{ key = "Plant Wall", icon = "🌿", stage = 2, price = 120000, income = 59, text = "Green and calm." },
	{ key = "Espresso Bar", icon = "☕", stage = 2, price = 200000, income = 77, text = "Better than the old machine." },
	{ key = "Pitch Screen", icon = "📽️", stage = 2, price = 350000, income = 0, effect = { pitch = 0.25 }, text = "Pitch bonuses are 25% bigger." },
	{ key = "Printer Station", icon = "🖨️", stage = 2, price = 550000, income = 113, text = "Contracts, flyers, stickers." },
	{ key = "Wi-Fi Mesh", icon = "📶", stage = 2, price = 900000, income = 147, text = "Fast internet in every corner." },
	{ key = "Dev Kit Shelf", icon = "🧰", stage = 2, price = 1500000, income = 0, effect = { sprint = 0.3 }, text = "Coding sprints pay 30% more." },
	{ key = "Brand Mural", icon = "🎨", stage = 2, price = 2500000, income = 226, text = "Your story on the wall." },
	-- Series A (stage 3)
	{ key = "Meeting Room", icon = "🚪", stage = 3, price = 2500000, income = 46, text = "Glass walls, big table." },
	{ key = "QA Lab", icon = "🧪", stage = 3, price = 3500000, income = 0, effect = { bug = 0.5 }, text = "Production bugs pay 50% more." },
	{ key = "Design Studio", icon = "✏️", stage = 3, price = 4500000, income = 64, text = "Pixel-perfect products." },
	{ key = "Server Row", icon = "🖧", stage = 3, price = 6000000, income = 77, text = "More racks, more uptime." },
	{ key = "Snack Bar", icon = "🍿", stage = 3, price = 7500000, income = 86, text = "Free snacks, happy team." },
	{ key = "Podcast Booth", icon = "🎙️", stage = 3, price = 9000000, income = 0, effect = { calls = 0.3 }, text = "Calls pay 30% more." },
	{ key = "Whiteboard Wall", icon = "🧠", stage = 3, price = 11000000, income = 0, effect = { brainstorm = 0.5 }, text = "Brainstorm boosts are 50% stronger." },
	{ key = "Game Corner", icon = "🎮", stage = 3, price = 14000000, income = 118, text = "Ping-pong after the release." },
	{ key = "Analytics Screens", icon = "📈", stage = 3, price = 17000000, income = 136, text = "Every metric, live." },
	{ key = "Nap Pod", icon = "😴", stage = 3, price = 21000000, income = 0, effect = { hatch = 0.15 }, text = "Recruiting eggs hatch 15% faster." },
	{ key = "Rooftop Sign", icon = "🪧", stage = 3, price = 25000000, income = 181, text = "Seen from the whole plaza." },
	-- Series B (stage 4)
	{ key = "Data Center Room", icon = "🏭", stage = 4, price = 12000000, income = 67, text = "Your own cooled server room." },
	{ key = "Marketing Floor", icon = "📣", stage = 4, price = 15000000, income = 80, text = "Campaigns that bring customers in." },
	{ key = "Recruiting Office", icon = "🤝", stage = 4, price = 19000000, income = 0, effect = { hatch = 0.2 }, text = "Recruiting eggs hatch 20% faster." },
	{ key = "Lounge Sofas", icon = "🛋️", stage = 4, price = 23000000, income = 100, text = "Comfy corners for big ideas." },
	{ key = "Training Room", icon = "🎓", stage = 4, price = 28000000, income = 114, text = "The team levels up." },
	{ key = "Customer Success Desk", icon = "🎧", stage = 4, price = 33000000, income = 0, effect = { calls = 0.35 }, text = "Calls pay 35% more." },
	{ key = "Security Desk", icon = "🛡️", stage = 4, price = 38000000, income = 133, text = "Badges and a friendly guard." },
	{ key = "Mail Room", icon = "📬", stage = 4, price = 44000000, income = 147, text = "Packages for a growing company." },
	{ key = "Library", icon = "📖", stage = 4, price = 50000000, income = 160, text = "A quiet floor for deep work." },
	{ key = "Video Studio", icon = "🎬", stage = 4, price = 55000000, income = 0, effect = { pitch = 0.3 }, text = "Pitch bonuses are 30% bigger." },
	{ key = "Coffee Roastery", icon = "🫘", stage = 4, price = 60000000, income = 187, text = "Your own beans, roasted in house." },
	-- Series C (stage 5)
	{ key = "Cafeteria", icon = "🥗", stage = 5, price = 30000000, income = 94, text = "Lunch for the whole company." },
	{ key = "Gym", icon = "🏋️", stage = 5, price = 40000000, income = 113, text = "Strong team, strong product." },
	{ key = "Rooftop Terrace", icon = "🌇", stage = 5, price = 50000000, income = 132, text = "Sunset demos." },
	{ key = "Legal Office", icon = "⚖️", stage = 5, price = 62000000, income = 0, effect = { bug = 0.5 }, text = "Production bugs pay 50% more." },
	{ key = "Demo Stage", icon = "🎤", stage = 5, price = 75000000, income = 160, text = "Launch events in house." },
	{ key = "Innovation Lab", icon = "🔬", stage = 5, price = 90000000, income = 0, effect = { sprint = 0.4 }, text = "Coding sprints pay 40% more." },
	{ key = "Wellness Room", icon = "🧘", stage = 5, price = 105000000, income = 190, text = "Breathe in, ship out." },
	{ key = "Investor Lounge", icon = "🥂", stage = 5, price = 120000000, income = 0, effect = { pitch = 0.4 }, text = "Pitch bonuses are 40% bigger." },
	{ key = "Auditorium", icon = "🏟️", stage = 5, price = 140000000, income = 228, text = "All-hands for hundreds." },
	{ key = "Green Roof", icon = "🌳", stage = 5, price = 165000000, income = 247, text = "A park on top of the office." },
	{ key = "Art Gallery", icon = "🖼️", stage = 5, price = 190000000, income = 275, text = "Culture for the whole campus." },
	-- IPO-ready (stage 6)
	{ key = "Boardroom", icon = "🪑", stage = 6, price = 150000000, income = 207, text = "Where the big decisions happen." },
	{ key = "Trading Screens", icon = "💹", stage = 6, price = 200000000, income = 248, text = "Watch the market before the bell." },
	{ key = "Press Room", icon = "📰", stage = 6, price = 260000000, income = 0, effect = { pitch = 0.5 }, text = "Pitch bonuses are 50% bigger." },
	{ key = "Executive Floor", icon = "🏢", stage = 6, price = 330000000, income = 310, text = "A floor for the leadership team." },
	{ key = "Trophy Wall", icon = "🏆", stage = 6, price = 420000000, income = 351, text = "Every milestone on display." },
	{ key = "Helipad", icon = "🚁", stage = 6, price = 520000000, income = 413, text = "Arrive in style." },
	{ key = "Shareholder Hall", icon = "🏛️", stage = 6, price = 630000000, income = 455, text = "Room for every shareholder." },
	{ key = "Golden Bell", icon = "🔔", stage = 6, price = 750000000, income = 517, text = "Ready to ring the opening bell." },
--ITEMS-END
}

-- The first item is free and must be bought first (it is the founder's desk: calls and the coding sprint start there)
OfficeConfig.FirstItem = "Desk"

-- One building per funding stage (stage n unlocks building n). office / team = income multipliers of the items and of
-- the employees while this building is the one owned. The Garage is free and every company starts in it.
OfficeConfig.Buildings = {
--BUILDINGS-START
	{ stage = 1, name = "Garage", price = 0, office = 1, team = 0.1 },
	{ stage = 2, name = "Small Office", price = 12000, office = 2, team = 0.8 },
	{ stage = 3, name = "Big Office", price = 3000000, office = 3, team = 5.1 },
	{ stage = 4, name = "Small Corporate", price = 25000000, office = 3.3, team = 9.2 },
	{ stage = 5, name = "Big Corporate", price = 70000000, office = 3.8, team = 15.8 },
	{ stage = 6, name = "HQ Tower", price = 250000000, office = 4.4, team = 20 },
--BUILDINGS-END
}

-- Workstations (a desk, a chair and a computer at a hire spot). Free = what every company has; Bought[i] = the price of
-- the (Free + i)-th, buyable once that funding stage is reached. Free + #Bought = 5, the old base slots.
OfficeConfig.FreeDesks = 1
OfficeConfig.Bought = {
--DESKS-START
	{ price = 2500, stage = 1 },
	{ price = 5000, stage = 1 },
	{ price = 60000, stage = 2 },
	{ price = 1500000, stage = 3 },
--DESKS-END
}
OfficeConfig.MaxWorkstations = 11 -- the hire spots in the room (pass and perk included)

-- Direct hires: these rarities can be bought for Cash, each creature of them at HireFactor x the average Cash an egg
-- spends for one hire of that rarity (the cheapest egg that has the rarity).
OfficeConfig.HireRarities = { "Common", "Uncommon" }
OfficeConfig.HireFactor = 4

-- Offline Cash and Cash packs still pay in full, but only this share counts toward the valuation, so a long absence
-- or a purchase can't skip a funding stage (the owner's D-C decision: offline pay stays as it is)
OfficeConfig.GiftValuationShare = 0.1

-- What a save from before overhaul 2 had: its building followed the old stage of its valuation (old thresholds, grown
-- by 2.5 per IPO). Frozen here so the first load under overhaul 2 gives the building they saw (docs/OVERHAUL2_PLAN.md 1.3).
OfficeConfig.LegacyStages = { 0, 1800, 6300, 23400, 81000 }
OfficeConfig.LegacyGrowth = 2.5
OfficeConfig.LegacyDesks = 4 -- the old 5 base slots = 1 free + 4 bought

-- Helpers used by both the server and the shop screen -------------------------------------------------------------

local itemIndex = {}
for i, item in ipairs(OfficeConfig.Items) do
	itemIndex[item.key] = i
end

function OfficeConfig.getItem(key)
	local i = itemIndex[key]
	return i and OfficeConfig.Items[i], i
end

-- The building owned, read safely: 1 (the Garage) for anything that is not a known building number
function OfficeConfig.building(number)
	if type(number) ~= "number" or number ~= number then
		return OfficeConfig.Buildings[1], 1
	end
	local n = math.clamp(math.floor(number), 1, #OfficeConfig.Buildings)
	return OfficeConfig.Buildings[n], n
end

-- Base income of the owned items (owned = { [key] = true }) before the building's multiplier
function OfficeConfig.itemIncome(owned)
	local sum = 0
	for _, item in ipairs(OfficeConfig.Items) do
		if owned[item.key] then
			sum += item.income
		end
	end
	return sum
end

-- The sum of an effect over the owned items (0 when none has it): "calls", "sprint", "bug", "brainstorm", "pitch", "hatch"
function OfficeConfig.effect(owned, kind)
	local sum = 0
	for _, item in ipairs(OfficeConfig.Items) do
		local value = owned[item.key] and item.effect and item.effect[kind]
		if type(value) == "number" then
			sum += value
		end
	end
	return sum
end

-- True when an owned item starts this founder activity ("bug")
function OfficeConfig.unlocks(owned, activity)
	for _, item in ipairs(OfficeConfig.Items) do
		if owned[item.key] and item.effect and item.effect.unlock == activity then
			return true
		end
	end
	return false
end

local function money(amount)
	local units = { { 1e9, "B" }, { 1e6, "M" }, { 1e3, "K" } }
	for _, unit in ipairs(units) do
		if amount >= unit[1] then
			return "$" .. (string.format("%.1f", amount / unit[1]):gsub("%.0$", "")) .. unit[2]
		end
	end
	return "$" .. math.floor(amount)
end
OfficeConfig.money = money

-- "Unlocks at Series A"
function OfficeConfig.unlockText(stage)
	return "Unlocks at " .. (OfficeConfig.StageNames[stage] or "?")
end

-- CHECKS-START
-- (tools/office_test.py runs these with fakes.) Pure: numbers and tables in, (true) or (nil, reason) out. The server
-- calls them with its own state; the reason is shown to the player.

-- An item from the catalog: index = its number in Items, stage = the player's funding stage now, owned = { [key] = true }
function OfficeConfig.checkItem(index, stage, owned, cash)
	if type(index) ~= "number" or index ~= index or index % 1 ~= 0 or index < 1 or index > #OfficeConfig.Items then
		return nil, "Unknown item"
	end
	local item = OfficeConfig.Items[index]
	if owned[item.key] then
		return nil, item.key .. " is already yours"
	end
	if item.key ~= OfficeConfig.FirstItem and not owned[OfficeConfig.FirstItem] then
		return nil, "Buy the " .. OfficeConfig.FirstItem .. " first"
	end
	if stage < item.stage then
		return nil, OfficeConfig.unlockText(item.stage)
	end
	if cash < item.price then
		return nil, "You need " .. money(item.price) .. " for " .. item.key
	end
	return item
end

-- The next building: current = the building owned now, stage = the funding stage reached
function OfficeConfig.checkBuilding(current, stage, cash)
	local nextNumber = current + 1
	local building = OfficeConfig.Buildings[nextNumber]
	if not building then
		return nil, "You have the biggest building"
	end
	if stage < nextNumber then
		return nil, building.name .. ": " .. OfficeConfig.unlockText(nextNumber)
	end
	if cash < building.price then
		return nil, "You need " .. money(building.price) .. " for the " .. building.name
	end
	return building, nextNumber
end

-- The next workstation: bought = desks bought so far, stage = the funding stage reached, capacity = workstations now
function OfficeConfig.checkDesk(bought, stage, cash, capacity)
	local desk = OfficeConfig.Bought[bought + 1]
	if not desk then
		return nil, "Every desk is bought"
	end
	if capacity >= OfficeConfig.MaxWorkstations then
		return nil, "The office is full of desks"
	end
	if stage < desk.stage then
		return nil, "Desk " .. (OfficeConfig.FreeDesks + bought + 1) .. ": " .. OfficeConfig.unlockText(desk.stage)
	end
	if cash < desk.price then
		return nil, "You need " .. money(desk.price) .. " for a desk"
	end
	return desk
end
-- CHECKS-END

-- Workstations: free + bought + the pass's extra + the perk's extra, at most MaxWorkstations
function OfficeConfig.workstations(bought, extra)
	return math.min(OfficeConfig.MaxWorkstations, OfficeConfig.FreeDesks + math.clamp(bought or 0, 0, #OfficeConfig.Bought) + (extra or 0))
end

-- The funding stage a save showed before overhaul 2 (its building then), from its valuation and IPO count
function OfficeConfig.legacyStage(valuation, ipoCount)
	local stage = 1
	for i, threshold in ipairs(OfficeConfig.LegacyStages) do
		if (valuation or 0) >= math.floor(threshold * OfficeConfig.LegacyGrowth ^ (ipoCount or 0)) then
			stage = i
		end
	end
	return stage
end

-- Direct hires (needs CreatureConfig): { { creature = key, price = Cash, eggAverage = Cash, egg = egg key }, ... }
function OfficeConfig.hireList(CreatureConfig)
	local list = {}
	for _, rarity in ipairs(OfficeConfig.HireRarities) do
		local best, bestEgg
		for _, egg in ipairs(CreatureConfig.Eggs) do
			local total, weight = 0, egg.odds[rarity] or 0
			for _, w in pairs(egg.odds) do
				total += w
			end
			if weight > 0 then
				local average = egg.price * total / weight -- Cash an egg spends, on average, for one hire of this rarity
				if not best or average < best then
					best, bestEgg = average, egg.key
				end
			end
		end
		if best then
			for _, creature in ipairs(CreatureConfig.Creatures) do
				if creature.rarity == rarity then
					local price = OfficeConfig.HireFactor * best
					local step = 10 ^ math.max(0, math.floor(math.log10(price)) - 1) -- two significant digits
					table.insert(list, {
						creature = creature.key, rarity = rarity, egg = bestEgg,
						price = math.ceil(price / step) * step, eggAverage = math.floor(best),
					})
				end
			end
		end
	end
	return list
end

-- Warn early about numbers that would break the shop
do
	local seen = {}
	for i, item in ipairs(OfficeConfig.Items) do
		if seen[item.key] then
			warn("OfficeConfig: duplicate item key " .. item.key)
		end
		seen[item.key] = true
		if type(item.stage) ~= "number" or item.stage < 1 or item.stage > #OfficeConfig.StageNames then
			warn("OfficeConfig: item " .. item.key .. " has a bad stage")
		end
		if type(item.price) ~= "number" or item.price < 0 or type(item.income) ~= "number" or item.income < 0 then
			warn("OfficeConfig: item " .. item.key .. " needs a price and an income of 0 or more")
		end
		if i > 1 and item.stage < OfficeConfig.Items[i - 1].stage then
			warn("OfficeConfig: items must be listed stage by stage")
		end
	end
	if OfficeConfig.Items[1] and OfficeConfig.Items[1].key ~= OfficeConfig.FirstItem then
		warn("OfficeConfig: the first item must be " .. OfficeConfig.FirstItem)
	end
	if #OfficeConfig.Buildings ~= #OfficeConfig.StageNames then
		warn("OfficeConfig: one building per funding stage")
	end
	if OfficeConfig.FreeDesks + #OfficeConfig.Bought ~= 5 then
		warn("OfficeConfig: free + bought desks must stay 5 (the old base slots; the pass adds 3 on top)")
	end
end

return OfficeConfig
