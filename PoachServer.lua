-- PoachServer: hiring employees away from other players in the same server ("poaching"),
-- the HR Department defense and the Poach Shield (milestone 3 poaching).
-- Put this ModuleScript in ServerScriptService, next to TycoonCore.
-- TycoonCore owns player data and saving, and plugs this module in with PoachServer.init.
-- Everything is decided here on the server: targets, costs, shields, cooldowns and the random
-- roll. The client only shows the state and asks for actions. The numbers live in
-- CreatureConfig.Poaching; the Headhunter pass and Poach Shield live in ShopConfig.

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local HttpService = game:GetService("HttpService")

local CreatureConfig = require(ReplicatedStorage:WaitForChild("CreatureConfig"))
local ShopConfig = require(ReplicatedStorage:WaitForChild("ShopConfig"))
local ShopServer = require(script.Parent:WaitForChild("ShopServer"))
local EmployeeServer = require(script.Parent:WaitForChild("EmployeeServer"))

local RULES = CreatureConfig.Poaching
local HR_PAD_OFFSET = Vector3.new(-21, 0.6, 24) -- front-left of the plot, next to the green pad
local HR_COLOR = Color3.fromRGB(150, 90, 255)
local WHITE = Color3.new(1, 1, 1)
local LOST_NOTE_SECONDS = 30 * 24 * 60 * 60 -- how long a save remembers who took its employees
local MAX_LOST_NOTES = 50
local SAVE_TRIES = 5
local TARGETS_MIN_INTERVAL = 0.25 -- the Poach window asks for the target list about once a second
local DUMMY_ID = -999 -- the Studio-only test target
local DUMMY_TEAM = { "CoffeeCapybara", "CodingCat", "HustleHamster", "SalesShark", "ServerSloth", "UnicornCEO" }

local PoachServer = {}

local core -- { getData, save, updateIncome, plotCenter, peekSave }, given by TycoonCore
local remotes = {}
local rng = Random.new()
local negotiations = {} -- target user ID -> the negotiation against them (one at a time)
local inTransit = {} -- employee ID -> true while a move between two saves is being written
local lastTargetsCall = {} -- player -> os.clock()
local dummy -- Studio Debug tab only: a fake player to poach from (never saved)

-- Helpers ---------------------------------------------------------------

local function makePart(parent, name, size, position, color, material)
	local p = Instance.new("Part")
	p.Name = name
	p.Size = size
	p.Position = position
	p.Color = color
	p.Material = material or Enum.Material.SmoothPlastic
	p.Anchored = true
	p.TopSurface = Enum.SurfaceType.Smooth
	p.BottomSurface = Enum.SurfaceType.Smooth
	p.Parent = parent
	return p
end

local function percent(chance)
	return math.floor(chance * 100 + 0.5) .. "%"
end

local function getPoach(player)
	local data = core.getData(player)
	return data and data.poach, data
end

-- A target is another player in this server, or the Studio test dummy
local function isDummy(target)
	return target ~= nil and target == dummy
end

local function userIdOf(target)
	return isDummy(target) and DUMMY_ID or target.UserId
end

local function nameOf(target)
	return isDummy(target) and dummy.name or target.DisplayName
end

local function poachOf(target)
	if isDummy(target) then return dummy.poach end
	local data = core.getData(target)
	return data and data.ready and data.poach or nil
end

local function employeesOf(target)
	if isDummy(target) then return dummy.employees end
	local data = core.getData(target)
	return data and data.team and data.team.employees or {}
end

local function findEmployee(target, id)
	for _, employee in ipairs(employeesOf(target)) do
		if employee.id == id then
			return employee
		end
	end
	return nil
end

-- Offline players can never be poached: only players whose data is loaded in this server count
local function isOnline(target)
	return isDummy(target) or (typeof(target) == "Instance" and target.Parent == Players and core.getData(target) ~= nil)
end

local function send(target, kind, info)
	if target and not isDummy(target) and target.Parent then
		remotes.event:FireClient(target, kind, info)
	end
end

-- Copies the state the screens show onto the player (the server never reads these back)
local function publish(player)
	local poach = getPoach(player)
	if not poach then return end
	player:SetAttribute("PoachShieldUntil", poach.shieldUntil)
	player:SetAttribute("PoachCooldownUntil", poach.cooldownUntil)
	player:SetAttribute("HRLevel", poach.hrLevel)
end

local function sendCounterOffer(player)
	local poach = getPoach(player)
	local offer = poach and poach.counterOffer
	send(player, "Counter", offer and {
		creature = offer.creature,
		attacker = offer.attackerName,
		price = offer.price,
		expiresAt = offer.expiresAt,
	} or false)
end

-- Rules ---------------------------------------------------------------

-- How many losses still count toward MaxLosses, and when the oldest of them happened
local function recentLosses(poach, now)
	local count, oldest = 0, nil
	for _, at in ipairs(poach.losses) do
		if now - at < RULES.LossWindow then
			count += 1
			oldest = oldest and math.min(oldest, at) or at
		end
	end
	return count, oldest
end

-- Why nobody can poach from this target right now (nil = they can), and until when (os.time)
-- if it ends by itself
local function protection(target, now)
	local poach = poachOf(target)
	if not poach then return "Still loading", nil end
	if poach.shieldUntil > now then
		return "Protected", poach.shieldUntil -- Poach Shield, new player, or just lost an employee
	end
	local count, oldest = recentLosses(poach, now)
	if count >= RULES.MaxLosses then
		return "Protected", oldest + RULES.LossWindow
	end
	if negotiations[userIdOf(target)] then
		return "Busy", nil -- someone is already negotiating with this team
	end
	return nil
end

local function chanceFor(attacker, target, creature)
	local poach = poachOf(target)
	local defense = CreatureConfig.hrDefense(poach and poach.hrLevel or 0)
	return CreatureConfig.poachChance(creature, defense, ShopServer.getPoachBonus(attacker))
end

-- Saving an employee move between two players ----------------------------------

-- Does this save (the table TycoonCore stores) have the employee?
local function saveHas(saved, id)
	local team = typeof(saved) == "table" and saved.team
	if typeof(team) ~= "table" then return false end
	for _, e in ipairs(team.employees or {}) do
		if typeof(e) == "table" and e.id == id then
			return true
		end
	end
	return typeof(team.pending) == "table" and team.pending.id == id
end

-- Saves the player and returns true once their save has (or no longer has) the employee.
-- If they already left, TycoonCore saved them on the way out, so that save is read back instead.
local function confirmSave(player, id, shouldHave)
	for attempt = 1, SAVE_TRIES do
		if core.getData(player) then
			if core.save(player) then
				return true
			end
		else
			local saved, ok = core.peekSave(player.UserId)
			if ok then
				return saveHas(saved, id) == shouldHave
			end
		end
		task.wait(attempt * 2)
	end
	return false
end

-- Moves an employee from one team to another and saves both players in an order that can
-- never duplicate or lose it, even if the server stops halfway:
--   1. `to` gets it, with a "gained" note. `from`'s save still keeps it (outgoing).
--   2. `to` is saved.
--   3. `from` lets it go for good, notes who took it (and gets `payment`). `from` is saved.
--   4. The note on `to` is removed.
-- If step 3 never gets saved, the note makes `to` hand it back (and get `refund`) on their
-- next join: see reconcile(). The Studio dummy is never saved, so moves with it are simple.
local function transfer(from, to, id, refund, payment)
	if not isDummy(to) and not EmployeeServer.hasFreeSlot(to) then return false end
	local employee
	if isDummy(from) then
		for i, e in ipairs(dummy.employees) do
			if e.id == id then
				employee = table.remove(dummy.employees, i)
				break
			end
		end
	else
		employee = EmployeeServer.releaseEmployee(from, id, not isDummy(to))
	end
	if not employee then return false end

	if isDummy(to) then
		table.insert(dummy.employees, { id = employee.id, creature = employee.creature })
		local _, fromData = getPoach(from)
		if payment and fromData then
			fromData.cash.Value += payment
		end
		task.spawn(core.save, from)
		return true
	end
	EmployeeServer.addEmployee(to, employee)
	if isDummy(from) then
		task.spawn(core.save, to)
		return true
	end

	local toPoach, fromPoach = getPoach(to), getPoach(from)
	toPoach.gained[id] = { from = from.UserId, refund = refund or 0 }
	toPoach.lost[id] = nil
	fromPoach.gained[id] = nil
	inTransit[id] = true
	task.spawn(function()
		if confirmSave(to, id, true) then
			local _, fromData = getPoach(from)
			if fromData then
				EmployeeServer.finishRelease(from, id)
				fromPoach.lost[id] = { to = to.UserId, at = os.time() }
				if payment then
					fromData.cash.Value += payment
				end
			end
			if confirmSave(from, id, false) then
				toPoach.gained[id] = nil
			end
		else
			warn("Poaching: couldn't save " .. to.Name .. " after a move; it will be undone on their next join")
		end
		inTransit[id] = nil
	end)
	return true
end

-- A "gained" note in a save means the server may have stopped before the other player's save
-- recorded the move. Their save decides: if it still has the employee (or says someone else
-- took it), the move never finished, so the employee goes back and the Cash is refunded.
local function reconcile(player, data, notes)
	for id, note in pairs(notes) do
		local other, ok = core.peekSave(note.from)
		if not ok then
			data.poach.gained[id] = note -- couldn't check now: keep the note for next time
		else
			local lostNotes = typeof(other) == "table" and typeof(other.poach) == "table" and other.poach.lost
			local lostNote = typeof(lostNotes) == "table" and lostNotes[id] or nil
			local takenBySomeoneElse = typeof(lostNote) == "table" and lostNote.to ~= player.UserId
			if saveHas(other, id) or takenBySomeoneElse then
				if EmployeeServer.releaseEmployee(player, id, false) then
					data.cash.Value += note.refund
					warn("Poaching: undid an unfinished move of employee " .. id .. " for " .. player.Name)
				end
			end
		end
	end
end

-- Negotiations ------------------------------------------------------------------

-- Stops a negotiation early (the target left, got a shield...) and gives the Cash back
local function cancel(negotiation, reason)
	local attacker = negotiation.attacker
	if negotiations[negotiation.targetId] == negotiation then
		negotiations[negotiation.targetId] = nil
	end
	local poach, data = getPoach(attacker)
	if not poach or poach.negotiation ~= negotiation then return end
	poach.negotiation = nil
	data.cash.Value += negotiation.cost
	send(attacker, "Cancelled", { reason = reason, refund = negotiation.cost })
	send(negotiation.target, "AttackOver", { attacker = attacker.DisplayName, creature = negotiation.creature, result = "cancelled" })
end

-- A successful poach: the employee moves, the victim gets protected and one Counter-Offer
local function poached(attacker, victim, id, creature, cost)
	if not transfer(victim, attacker, id, cost, nil) then return false end
	local now = os.time()
	local victimPoach = poachOf(victim)
	table.insert(victimPoach.losses, now)
	victimPoach.shieldUntil = math.max(victimPoach.shieldUntil, now + RULES.ShieldAfterPoach)
	local price
	if not isDummy(victim) then
		price = math.floor(cost * RULES.CounterOfferPrice)
		victimPoach.counterOffer = {
			employeeId = id,
			creature = creature.key,
			attacker = attacker,
			attackerName = nameOf(attacker),
			price = price,
			expiresAt = now + RULES.CounterOfferSeconds,
		}
		publish(victim)
		sendCounterOffer(victim)
	end
	send(attacker, "Result", { success = true, target = nameOf(victim), creature = creature.key, cost = cost })
	send(victim, "Poached", {
		attacker = nameOf(attacker),
		creature = creature.key,
		shieldUntil = victimPoach.shieldUntil,
		price = price,
		expiresAt = now + RULES.CounterOfferSeconds,
	})
	return true
end

local function finish(negotiation)
	local attacker, target = negotiation.attacker, negotiation.target
	local poach, data = getPoach(attacker)
	if not poach or poach.negotiation ~= negotiation then return end -- cancelled, or the attacker left

	-- Anything that changed while negotiating and isn't the attacker's fault: call it off and refund
	local name = nameOf(target)
	negotiations[negotiation.targetId] = nil -- so protection() doesn't see this negotiation as "Busy"
	local problem
	if not isOnline(target) then
		problem = name .. " left the server"
	elseif not findEmployee(target, negotiation.employeeId) or inTransit[negotiation.employeeId] then
		problem = "the employee isn't on " .. name .. "'s team anymore"
	elseif protection(target, os.time()) then
		problem = name .. " got protected"
	elseif not EmployeeServer.hasFreeSlot(attacker) then
		problem = "your team filled up"
	end
	if problem then
		cancel(negotiation, "Deal called off: " .. problem .. ".")
		return
	end

	poach.negotiation = nil
	poach.cooldownUntil = os.time() + RULES.AttackerCooldown
	publish(attacker)
	local creature = CreatureConfig.getCreature(negotiation.creature)
	local forced = poach.forceResult -- Studio Debug tab only
	poach.forceResult = nil
	local success
	if forced then
		success = forced == "success"
	else
		success = rng:NextNumber() < negotiation.chance -- the roll happens only here, on the server
	end

	if success and poached(attacker, target, negotiation.employeeId, creature, negotiation.cost) then
		return
	end
	send(attacker, "Result", { success = false, target = name, creature = creature.key, cost = negotiation.cost })
	send(target, "AttackOver", { attacker = attacker.DisplayName, creature = creature.key, result = "defended" })
	task.spawn(core.save, attacker) -- the Cash is spent: save it now
end

-- Actions the client can ask for ------------------------------------------------

local function start(player, targetUserId, employeeId)
	local poach, data = getPoach(player)
	local now = os.time()
	if poach.negotiation then return false, "You're already negotiating" end
	if poach.cooldownUntil > now then
		return false, "Your recruiters need a break: try again in " .. CreatureConfig.formatTime(poach.cooldownUntil - now)
	end

	local target = (dummy and targetUserId == DUMMY_ID) and dummy or Players:GetPlayerByUserId(targetUserId)
	if not target or target == player or not isOnline(target) then
		return false, "That player isn't in this server anymore"
	end
	local name = nameOf(target)
	local reason, untilTime = protection(target, now)
	if reason == "Busy" then
		return false, "Someone else is already negotiating with " .. name .. "'s team"
	elseif reason then
		return false, name .. "'s team is protected" .. (untilTime and (" for " .. CreatureConfig.formatTime(untilTime - now)) or "")
	end

	local employee = findEmployee(target, employeeId)
	local creature = employee and CreatureConfig.getCreature(employee.creature)
	if not creature or inTransit[employeeId] then return false, "That employee isn't available" end
	local chance = chanceFor(player, target, creature)
	if not chance then return false, creature.rarity .. " employees can't be poached" end
	if not EmployeeServer.hasFreeSlot(player) then
		return false, "Your team is full: fire someone first" -- checked before paying
	end
	local cost = CreatureConfig.poachCost(creature)
	if data.cash.Value < cost then return false, "Not enough Cash (" .. ShopConfig.formatCash(cost) .. ")" end

	data.cash.Value -= cost -- saved as a refund until the negotiation ends (see serialize)
	local seconds = rng:NextNumber(RULES.NegotiationSeconds[1], RULES.NegotiationSeconds[2])
	local negotiation = {
		attacker = player,
		target = target,
		targetId = userIdOf(target),
		employeeId = employeeId,
		creature = creature.key,
		cost = cost,
		chance = chance, -- fixed now, so the chance you saw is the chance you get
	}
	poach.negotiation = negotiation
	negotiations[negotiation.targetId] = negotiation
	send(player, "Negotiating", { target = name, creature = creature.key, seconds = seconds, chance = chance, cost = cost })
	send(target, "UnderAttack", { attacker = player.DisplayName, creature = creature.key, seconds = seconds })
	task.delay(seconds, finish, negotiation)
	return true, "Negotiating with " .. name .. "'s " .. creature.name .. " (" .. percent(chance) .. " chance)"
end

-- Buy back the employee that was just poached from you (once, within CounterOfferSeconds)
local function counterOffer(player)
	local poach, data = getPoach(player)
	local offer = poach.counterOffer
	if not offer then return false, "There's no Counter-Offer to make" end
	local function drop(message)
		poach.counterOffer = nil
		sendCounterOffer(player)
		return false, message
	end
	if os.time() > offer.expiresAt then return drop("Too late: the Counter-Offer expired") end
	local attacker = offer.attacker
	if not isOnline(attacker) then return drop(offer.attackerName .. " left the server with them") end
	if not findEmployee(attacker, offer.employeeId) then return drop(offer.attackerName .. " doesn't have them anymore") end
	if inTransit[offer.employeeId] then return false, "The paperwork isn't done yet, try again in a moment" end
	if not EmployeeServer.hasFreeSlot(player) then return false, "Your team is full: make room first" end
	if data.cash.Value < offer.price then return false, "Not enough Cash (" .. ShopConfig.formatCash(offer.price) .. ")" end

	data.cash.Value -= offer.price
	poach.counterOffer = nil
	if not transfer(attacker, player, offer.employeeId, offer.price, offer.price) then
		data.cash.Value += offer.price
		return drop("The Counter-Offer didn't work out")
	end
	sendCounterOffer(player)
	local creature = CreatureConfig.getCreature(offer.creature)
	send(attacker, "Notice", {
		text = player.DisplayName .. " made a Counter-Offer: " .. creature.name .. " went back. You got "
			.. ShopConfig.formatCash(offer.price) .. ".",
	})
	return true, creature.name .. " is back on your team!"
end

-- What the Poach window shows: everyone else in this server and their employees
local function targetsFor(player)
	local poach = getPoach(player)
	local now = os.time()
	local targets = {}
	local function add(target)
		local targetPoach = poachOf(target)
		if not targetPoach then return end
		local reason, untilTime = protection(target, now)
		local entry = {
			userId = userIdOf(target),
			name = nameOf(target),
			hrLevel = targetPoach.hrLevel,
			blocked = reason or false,
			blockedUntil = untilTime or false,
			mine = poach.negotiation ~= nil and poach.negotiation.target == target, -- we're the ones negotiating
			employees = {},
		}
		for _, employee in ipairs(employeesOf(target)) do
			local creature = CreatureConfig.getCreature(employee.creature)
			if creature and not inTransit[employee.id] then
				table.insert(entry.employees, {
					id = employee.id,
					creature = creature.key,
					chance = chanceFor(player, target, creature) or false, -- false = can't be poached
					cost = CreatureConfig.poachCost(creature),
				})
			end
		end
		table.insert(targets, entry)
	end
	for _, other in ipairs(Players:GetPlayers()) do
		if other ~= player then
			add(other)
		end
	end
	if dummy then
		add(dummy)
	end
	local offer = poach.counterOffer
	return {
		targets = targets,
		freeSlot = EmployeeServer.hasFreeSlot(player),
		negotiating = poach.negotiation ~= nil,
		counterOffer = offer and {
			creature = offer.creature,
			attacker = offer.attackerName,
			price = offer.price,
			expiresAt = offer.expiresAt,
		} or false,
	}
end

local function onAction(player, action, a, b)
	if typeof(action) ~= "string" then return false, "Bad request" end
	local poach, data = getPoach(player)
	if not poach or not data.ready then return false, "Still loading, try again in a moment" end

	if action == "Targets" then
		local last = lastTargetsCall[player]
		if last and os.clock() - last < TARGETS_MIN_INTERVAL then return false, "Too fast" end
		lastTargetsCall[player] = os.clock()
		return true, targetsFor(player)
	elseif action == "Start" then
		if typeof(a) ~= "number" or typeof(b) ~= "string" or #b > 64 then return false, "Bad request" end
		return start(player, a, b)
	elseif action == "CounterOffer" then
		return counterOffer(player)
	end
	return false, "Unknown action"
end

-- HR Department pad ----------------------------------------------------------

local function hrLabelText(level)
	local nextLevel = RULES.HRDepartment[level + 1]
	if not nextLevel then
		return "HR Department MAX\n-" .. percent(CreatureConfig.hrDefense(level)) .. " poach chance"
	end
	return string.format("HR Department Lv %d\nLv %d: %s (-%s poach chance)", level, level + 1,
		ShopConfig.formatCash(nextLevel.cost), percent(nextLevel.defense))
end

-- A purple pad next to the green one. Step on it to buy the next level (like the green pad).
local function buildHrPad(player, data)
	local pad = makePart(data.folder, "HRPad", Vector3.new(8, 0.2, 8), core.plotCenter(data.slot) + HR_PAD_OFFSET, HR_COLOR, Enum.Material.Neon)
	local gui = Instance.new("BillboardGui")
	gui.Size = UDim2.fromScale(10, 2.6) -- in studs, like the incubator labels
	gui.StudsOffset = Vector3.new(0, 4, 0)
	gui.AlwaysOnTop = true
	gui.MaxDistance = 90
	gui.Parent = pad
	local label = Instance.new("TextLabel")
	label.Size = UDim2.fromScale(1, 1)
	label.BackgroundTransparency = 1
	label.TextScaled = true
	label.Font = Enum.Font.GothamBold
	label.TextColor3 = WHITE
	label.TextStrokeTransparency = 0
	label.Text = hrLabelText(data.poach.hrLevel)
	label.Parent = gui

	local lastTouch = 0
	pad.Touched:Connect(function(hit)
		if Players:GetPlayerFromCharacter(hit.Parent) ~= player or not data.ready then return end
		if os.clock() - lastTouch < 2 then return end
		local poach = data.poach
		local nextLevel = RULES.HRDepartment[poach.hrLevel + 1]
		if not nextLevel then return end
		lastTouch = os.clock()
		if data.cash.Value < nextLevel.cost then
			send(player, "Notice", { text = "HR Department Lv " .. (poach.hrLevel + 1) .. " costs " .. ShopConfig.formatCash(nextLevel.cost) })
			return
		end
		data.cash.Value -= nextLevel.cost
		poach.hrLevel += 1
		label.Text = hrLabelText(poach.hrLevel)
		publish(player)
		send(player, "Notice", { text = "HR Department Lv " .. poach.hrLevel .. ": poachers get -" .. percent(nextLevel.defense) .. " chance" })
	end)
end

-- Saving (TycoonCore calls these) ----------------------------------------------

-- Called after the player's save loads (and after EmployeeServer.setupPlayer). savedPoach is
-- the "poach" part of the save, or nil (older saves). isNew = this player has never played before.
function PoachServer.setupPlayer(player, data, savedPoach, isNew)
	local now = os.time()
	local poach = {
		hrLevel = 0, -- HR Department level (saved)
		shieldUntil = 0, -- os.time() when protection ends (saved as time left, so it pauses offline)
		cooldownUntil = 0, -- os.time() when this player may poach again (saved)
		losses = {}, -- os.time() of employees lost recently (saved)
		gained = {}, -- employee ID -> { from, refund }: moves the other save hasn't confirmed yet (saved)
		lost = {}, -- employee ID -> { to, at }: who took our employees (saved, for their checks)
		negotiation = nil, -- our running attempt; its cost is saved as a refund in case the server stops
		counterOffer = nil, -- { employeeId, creature, attacker, attackerName, price, expiresAt }
		forceResult = nil, -- Studio Debug tab only
	}
	local notes = {}
	if typeof(savedPoach) == "table" then
		poach.hrLevel = math.clamp(math.floor(tonumber(savedPoach.hrLevel) or 0), 0, #RULES.HRDepartment)
		poach.shieldUntil = now + math.max(0, tonumber(savedPoach.shieldLeft) or 0)
		poach.cooldownUntil = tonumber(savedPoach.cooldownUntil) or 0
		for _, at in ipairs(typeof(savedPoach.losses) == "table" and savedPoach.losses or {}) do
			if typeof(at) == "number" and now - at < RULES.LossWindow then
				table.insert(poach.losses, at)
			end
		end
		if typeof(savedPoach.lost) == "table" then
			for id, note in pairs(savedPoach.lost) do
				if typeof(id) == "string" and typeof(note) == "table" and typeof(note.to) == "number" then
					poach.lost[id] = { to = note.to, at = tonumber(note.at) or now }
				end
			end
		end
		if typeof(savedPoach.gained) == "table" then
			for id, note in pairs(savedPoach.gained) do
				if typeof(id) == "string" and typeof(note) == "table" and typeof(note.from) == "number" then
					notes[id] = { from = note.from, refund = tonumber(note.refund) or 0 }
				end
			end
		end
		local refund = tonumber(savedPoach.refund) -- the server stopped during a negotiation
		if refund and refund > 0 then
			data.cash.Value += math.floor(refund)
			print(player.Name .. " got " .. ShopConfig.formatCash(refund) .. " back from an unfinished poaching attempt")
		end
	end
	if isNew then
		poach.shieldUntil = math.max(poach.shieldUntil, now + RULES.NewPlayerShield)
	end
	data.poach = poach
	reconcile(player, data, notes)
	buildHrPad(player, data)
	publish(player)
end

-- The part of the save file that belongs to poaching
function PoachServer.serialize(data)
	local poach = data.poach
	if not poach then return nil end
	local now = os.time()
	local losses = {}
	for _, at in ipairs(poach.losses) do
		if now - at < RULES.LossWindow then
			table.insert(losses, at)
		end
	end
	-- Keep who took our employees for a while (their next join may need to check), newest first
	local ids = {}
	for id, note in pairs(poach.lost) do
		if now - note.at < LOST_NOTE_SECONDS then
			table.insert(ids, id)
		else
			poach.lost[id] = nil
		end
	end
	table.sort(ids, function(x, y)
		return poach.lost[x].at > poach.lost[y].at
	end)
	local lost = {}
	for i = 1, math.min(#ids, MAX_LOST_NOTES) do
		lost[ids[i]] = poach.lost[ids[i]]
	end
	return {
		hrLevel = poach.hrLevel,
		shieldLeft = math.max(0, poach.shieldUntil - now),
		cooldownUntil = poach.cooldownUntil,
		losses = losses,
		gained = poach.gained,
		lost = lost,
		refund = poach.negotiation and poach.negotiation.cost or nil,
	}
end

-- Studio Debug tab -------------------------------------------------------------

local function spawnDummy()
	if dummy and negotiations[DUMMY_ID] then
		cancel(negotiations[DUMMY_ID], "Deal called off: the dummy was reset.")
	end
	dummy = {
		name = "Dummy Startup 🤖",
		employees = {},
		poach = { hrLevel = 0, shieldUntil = 0, cooldownUntil = 0, losses = {} },
	}
	for _, key in ipairs(DUMMY_TEAM) do
		table.insert(dummy.employees, { id = HttpService:GenerateGUID(false), creature = key })
	end
end

local function addDebugActions()
	ShopServer.addDebugAction("PoachSpawnDummy", function()
		spawnDummy()
		return "Dummy Startup is in the Poach window with " .. #dummy.employees .. " employees"
	end)
	ShopServer.addDebugAction("PoachDummyHR", function()
		if not dummy then spawnDummy() end
		dummy.poach.hrLevel = (dummy.poach.hrLevel + 1) % (#RULES.HRDepartment + 1)
		return "Dummy's HR Department is now Lv " .. dummy.poach.hrLevel
			.. " (-" .. percent(CreatureConfig.hrDefense(dummy.poach.hrLevel)) .. " chance)"
	end)
	ShopServer.addDebugAction("PoachDummyAttack", function(player, data)
		if not dummy then spawnDummy() end
		local best, bestCreature
		for _, employee in ipairs(data.team.employees) do
			local creature = CreatureConfig.getCreature(employee.creature)
			if creature and RULES.BaseChance[creature.rarity] and not inTransit[employee.id]
				and (not bestCreature or creature.income > bestCreature.income) then
				best, bestCreature = employee, creature
			end
		end
		if not best then return "You have no employee the dummy could poach (Legendaries are safe)" end
		poached(dummy, player, best.id, bestCreature, CreatureConfig.poachCost(bestCreature)) -- ignores your shields
		return "The dummy poached your " .. bestCreature.name .. " (your shields were ignored)"
	end)
	ShopServer.addDebugAction("PoachForce", function(_, data, result)
		if result ~= "success" and result ~= "fail" then return "Bad result" end
		data.poach.forceResult = result
		return "Your next poach will " .. (result == "success" and "succeed" or "fail")
	end)
	ShopServer.addDebugAction("PoachClearTimers", function()
		for _, other in ipairs(Players:GetPlayers()) do
			local poach = getPoach(other)
			if poach then
				poach.shieldUntil = 0
				poach.cooldownUntil = 0
				table.clear(poach.losses)
				publish(other)
			end
		end
		if dummy then
			dummy.poach.shieldUntil = 0
			table.clear(dummy.poach.losses)
		end
		return "Shields, loss limits and cooldowns cleared for everyone in this server"
	end)
end

-- Setup -----------------------------------------------------------------

function PoachServer.init(coreApi)
	core = coreApi

	local folder = Instance.new("Folder")
	folder.Name = "PoachRemotes"
	remotes.action = Instance.new("RemoteFunction")
	remotes.action.Name = "PoachAction"
	remotes.action.OnServerInvoke = onAction
	remotes.action.Parent = folder
	remotes.event = Instance.new("RemoteEvent")
	remotes.event.Name = "PoachEvent"
	remotes.event.Parent = folder
	folder.Parent = ReplicatedStorage

	-- Poach Shield (developer product): adds protection time, and stops anyone negotiating right now
	ShopServer.addProductHandler("shieldMinutes", function(player, data, effect)
		local poach = data.poach
		poach.shieldUntil = math.max(poach.shieldUntil, os.time()) + effect.shieldMinutes * 60
		publish(player)
		local negotiation = negotiations[player.UserId]
		if negotiation then
			cancel(negotiation, "Deal called off: " .. player.DisplayName .. " got a Poach Shield.")
		end
		return "+" .. effect.shieldMinutes .. " min of Poach Shield"
	end)

	if RunService:IsStudio() then
		addDebugActions()
	end

	Players.PlayerRemoving:Connect(function(player)
		for _, negotiation in pairs(negotiations) do
			if negotiation.attacker == player then
				-- If their save was already written, its "refund" gives the Cash back next time
				cancel(negotiation, "You left")
			elseif negotiation.target == player then
				cancel(negotiation, "Deal called off: " .. player.DisplayName .. " left the server.")
			end
		end
		-- Counter-Offers for employees this player took can't happen anymore
		for _, other in ipairs(Players:GetPlayers()) do
			local poach = getPoach(other)
			if poach and poach.counterOffer and poach.counterOffer.attacker == player then
				poach.counterOffer = nil
				sendCounterOffer(other)
				send(other, "Notice", { text = player.DisplayName .. " left: the Counter-Offer is off" })
			end
		end
		lastTargetsCall[player] = nil
	end)

	-- Every second: expire Counter-Offers
	task.spawn(function()
		while true do
			task.wait(1)
			local now = os.time()
			for _, player in ipairs(Players:GetPlayers()) do
				local poach = getPoach(player)
				if poach and poach.counterOffer and now > poach.counterOffer.expiresAt then
					poach.counterOffer = nil
					sendCounterOffer(player)
				end
			end
		end
	end)
end

return PoachServer
