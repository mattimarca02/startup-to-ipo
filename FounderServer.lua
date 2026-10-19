-- FounderServer: the founder's activities (overhaul 2 phase 3, the owner's point 14): the coding sprint at the desk,
-- the production bug at the Server Rack, the brainstorm at the blackboard and the investor pitch of each funding round.
-- Put this ModuleScript in ServerScriptService, next to TycoonCore. TycoonCore plugs it in with FounderServer.init after
-- TaskServer (it pays through TaskServer.payReward) and before DailyServer. The rules live in FounderConfig.
--
-- Everything is decided here, from the server's clock (os.clock): what is asked, the right answer (the code lines and
-- the pitch questions live in this file only, never in ReplicatedStorage), the time limits, the grade and the reward.
-- The client sends only "start this activity", "I pressed button N" or "close it" (FounderRemotes.FounderAction):
--   FounderAction("Sync")              -> the state, once, when the screen starts
--   FounderAction("Start", which)      -> "sprint" (at the desk), "bug" (at the rack, while the alarm rings),
--                                         "brainstorm" (at the blackboard), "pitch" (at the desk, while one is offered),
--                                         "dinner" (VIP pass holders, once a day, at the VIP Lounge's table: phase 5)
--   FounderAction("Pick", n)           -> the button pressed in the running activity (1 to 4)
--   FounderAction("Cancel")            -> close it: a sprint or pitch ends with what it has (closed before the first
--                                         answer: nothing happens, no cooldown, the pitch stays offered); a bug can be
--                                         started again while its alarm rings; a brainstorm stays ready
--   FounderState (server to client)    -> "state" { sprint, bug, board, boost, pitch, activity } (see snapshot)
-- Starting at a station needs the character within FounderConfig.Reach of it (measured here from the garage's frame).
-- Rewards: seconds of Income through TaskServer.payReward (the calls' reward bank and daily cap; the pitch is a round
-- bonus outside the bank), times 1 + the office items' effect (OfficeConfig.effect). A failed bug fix costs
-- FounderConfig.Bug.penalty seconds of Income from Cash (never below $0, never the valuation). Nothing is random but
-- which question or line is asked and when the alarm rings (D9: no Cash stake on a random result).
--
-- Saving: the `founder` section (rule A10, a new top-level section, optional on load):
--   { v = 1, run = the IPO count the pitches belong to, pitched = { [stage key] = true }, dinnerDay = day number }
-- A missing section is a new player or a save from before phase 3. Unknown fields are kept and written back; bad values
-- are skipped with a warning. Cooldowns, alarms and boosts are memory only (a rejoin starts them fresh: the sprint and
-- the brainstorm are ready, the next alarm is a normal gap away).

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")

local FounderConfig = require(ReplicatedStorage:WaitForChild("FounderConfig"))
local OfficeConfig = require(ReplicatedStorage:WaitForChild("OfficeConfig")) -- item effects and unlocks
local IpoConfig = require(ReplicatedStorage:WaitForChild("IpoConfig")) -- stage names
local DailyConfig = require(ReplicatedStorage:WaitForChild("DailyConfig")) -- dayNumber: the dinner's day
local ShopConfig = require(ReplicatedStorage:WaitForChild("ShopConfig")) -- money format, DebugInStudio
local IpoServer = require(script.Parent:WaitForChild("IpoServer")) -- isBusy
local TaskServer = require(script.Parent:WaitForChild("TaskServer")) -- payReward, setCallsBoost
local ShopServer = require(script.Parent:WaitForChild("ShopServer")) -- the Studio Debug tab

local TEXTS = FounderConfig.Texts
local FounderServer = {}

local core -- { getData, updateIncome, plotFrame, stageOf, notify }, given by TycoonCore
local remotes = {}

local KNOWN_FIELDS = { v = true, run = true, pitched = true, dinnerDay = true }
local SECTION_VERSION = 1

-- What only the server knows ----------------------------------------------------------------------

-- The coding sprint: each round shows 3 good lines and the broken twin of a 4th; the player taps the broken one
local CODE = {
	{ 'print("Hello, users!")', 'pritn("Hello, users!")' },
	{ "if price > 0 then", "if price > 0 than" },
	{ "local total = a + b", "local total = a + + b" },
	{ "return price * 2", "retrun price * 2" },
	{ "for i = 1, 10 do", "for i = 1, 10 od" },
	{ 'user.name = "Ada"', 'user.name = "Ada' },
	{ "while running do", "while running do do" },
	{ "local list = {}", "local list = {" },
	{ "count += 1", "count =+ 1" },
	{ "save(player)", "save(player" },
	{ "local ok = true", "local ok == true" },
	{ "sendEmail(user)", "sendEmial(user)" },
	{ "if not ready then", "if not ready the" },
	{ "local price = 9.99", "local price = 9..99" },
	{ "table.insert(list, item)", "table.insert(list item)" },
	{ "function launch()", "fuction launch()" },
}

-- The investor pitch: a question, its good answer, then two weak ones (shown in a new order each time)
local PITCH = {
	{ "What does your startup do better than anyone?", "We solve one real problem, fast", "We do everything for everyone", "We haven't decided yet" },
	{ "How will you use the money?", "Hire engineers and grow sales", "Buy a yacht for team meetings", "Keep it in the bank, just in case" },
	{ "Who are your customers?", "Small shops that need simple software", "Everybody on Earth", "We'll find out after launch" },
	{ "How do you make money?", "A monthly subscription", "Ads, someday, maybe", "We don't need money" },
	{ "What is your biggest risk?", "Big companies copying us, so we move fast", "There is no risk", "Running out of coffee" },
	{ "Why now?", "Phones made our product possible this year", "Why not?", "My horoscope said so" },
	{ "What did your first users teach you?", "They wanted it simpler, so we cut features", "Users are always wrong", "We don't talk to users" },
	{ "How big can this get?", "Every city has thousands of shops like our customers", "Infinite!", "Pretty small, honestly" },
	{ "Who is on your team?", "Builders who shipped products before", "Just my cat", "Nobody yet, but trust me" },
	{ "How do customers find you?", "Happy customers tell their friends", "We hope they stumble on us", "We hide, it's more exclusive" },
}

-- Helpers -------------------------------------------------------------------------------------------

local function isNumber(value)
	return typeof(value) == "number" and value == value and value > -math.huge and value < math.huge
end

-- n different whole numbers from 1 to `size`, in a new order
local function pickDistinct(size, n)
	local pool = {}
	for i = 1, size do
		pool[i] = i
	end
	for i = size, 2, -1 do
		local j = math.random(1, i)
		pool[i], pool[j] = pool[j], pool[i]
	end
	local out = {}
	for i = 1, math.min(n, size) do
		out[i] = pool[i]
	end
	return out
end

local function newLive(now)
	return {
		tokens = FounderConfig.RateLimit.burst, tokensAt = now,
		activity = nil, -- the running activity (one at a time)
		sprintReadyAt = now, boardReadyAt = now,
		bugNextAt = nil, alarmUntil = nil, -- the next alarm, and the end of the ringing one
		boost = nil, -- { kind, name, share, untilAt }: the brainstorm idea that runs (one at a time)
		sign = nil, -- what the client last heard about unlocks and offers (a change sends a new state)
		changed = true,
		lastWarnAt = -math.huge,
	}
end

local function warnBad(player, live, now, what)
	if now - live.lastWarnAt >= 10 then
		live.lastWarnAt = now
		warn("Ignored a bad founder request from " .. player.Name .. ": " .. what)
	end
end

local function hiresOf(data)
	return data.team and data.team.employees and #data.team.employees or 0
end

local function ipoCountOf(data)
	return data.ipo and data.ipo.count or 0
end

-- What is unlocked for this player now
local function sprintOn(data)
	return data.owned ~= nil and data.owned[OfficeConfig.FirstItem] == true
end
local function bugOn(data)
	return data.owned ~= nil and OfficeConfig.unlocks(data.owned, "bug")
end
local function boardOn(data)
	return hiresOf(data) >= FounderConfig.Brainstorm.minHires
end

-- The funding stage whose pitch is offered now, or nil (one per round per run, from Seed up)
local function pitchOffered(data)
	local founder = data.founder
	local stage = core.stageOf(data)
	local info = IpoConfig.Stages[stage]
	if not founder or not info or stage < FounderConfig.Pitch.minStage or founder.pitched[info.key] then
		return nil
	end
	return info
end

-- The VIP Investor dinner: a VIP pass holder who has not had today's (phase 5)
local function today()
	return DailyConfig.dayNumber(os.time())
end
local function dinnerReady(player, data)
	return ShopServer.isVip ~= nil and ShopServer.isVip(player) and data.founder ~= nil and data.founder.dinnerDay < today()
end
local function dinnerPosition()
	local at = FounderConfig.Dinner.at
	return Vector3.new(at.x, at.y, at.z)
end

local function effect(data, kind)
	return OfficeConfig.effect(data.owned or {}, kind)
end

-- Where a station stands in the world, and whether the character is close enough to start there
local function stationPosition(data, name)
	local spot = FounderConfig.Stations[name]
	return (core.plotFrame(data.slot) * CFrame.new(spot.x, 0.5, spot.z)).Position
end

local function closeEnough(player, data, name)
	local root = player.Character and player.Character:FindFirstChild("HumanoidRootPart")
	if not root or not data.slot then
		return false
	end
	local offset = root.Position - stationPosition(data, name)
	return Vector3.new(offset.X, 0, offset.Z).Magnitude <= FounderConfig.Reach
end

-- The client's view ----------------------------------------------------------------------------------

local function activityView(activity, now)
	if not activity then
		return nil
	end
	local view = { kind = activity.kind, left = math.max(0, (activity.deadline or now) - now), limit = activity.limit }
	if activity.kind == "sprint" then
		view.round, view.of, view.lines = activity.round, FounderConfig.Sprint.rounds, activity.lines
	elseif activity.kind == "bug" then
		local order = {}
		for i, button in ipairs(activity.order) do
			order[i] = FounderConfig.Bug.buttons[button]
		end
		view.buttons, view.order, view.pos = FounderConfig.Bug.buttons, order, activity.pos
	elseif activity.kind == "brainstorm" then
		view.ideas = activity.ideas
	elseif activity.kind == "pitch" then
		view.stage, view.q, view.of, view.question, view.options = activity.stageName, activity.q, #activity.questions, activity.question, activity.options
	end
	return view
end

local function snapshot(data, live, now)
	local pitch = pitchOffered(data)
	local boost = live.boost
	return {
		sprint = { on = sprintOn(data), readyIn = math.max(0, live.sprintReadyAt - now) },
		bug = { on = bugOn(data), alarm = live.alarmUntil ~= nil, left = live.alarmUntil and math.max(0, live.alarmUntil - now) or 0 },
		board = { on = boardOn(data), readyIn = math.max(0, live.boardReadyAt - now) },
		boost = boost and now < boost.untilAt and { kind = boost.kind, name = boost.name, left = boost.untilAt - now } or nil,
		pitch = pitch and pitch.name or nil,
		dinner = live.vip and { ready = live.dinnerReady == true } or nil, -- VIP only: the table's prompt
		activity = activityView(live.activity, now),
	}
end

local function send(player, kind, payload)
	if remotes.state and player.Parent then
		remotes.state:FireClient(player, kind, payload)
	end
end

local function flush(player, data, live, now)
	if live.changed then
		live.changed = false
		send(player, "state", snapshot(data, live, now))
	end
end

-- Rewards ---------------------------------------------------------------------------------------------

local function money(cash)
	return ShopConfig.formatCash(cash)
end

-- A failed fix: `seconds` of Income from Cash, never below $0 and never the valuation (no addEarnings)
local function charge(data, seconds)
	local cost = math.min(data.cash.Value, math.floor(seconds * data.income.Value))
	if cost > 0 then
		data.cash.Value -= cost
	end
	return math.max(0, cost)
end

local function boostShare(live, kind, now)
	local boost = live.boost
	return boost and boost.kind == kind and now < boost.untilAt and boost.share or 0
end

-- Activities -------------------------------------------------------------------------------------------

local function newSprintRound(activity, now)
	local s = FounderConfig.Sprint
	local picks = pickDistinct(#CODE, 4)
	local answer = math.random(1, 4)
	local lines = {}
	for i, index in ipairs(picks) do
		lines[i] = i == answer and CODE[index][2] or CODE[index][1]
	end
	activity.lines, activity.answer = lines, answer
	activity.openedAt, activity.limit, activity.deadline = now, s.roundSeconds, now + s.roundSeconds
end

local function newPitchQuestion(activity, now)
	local p = FounderConfig.Pitch
	local row = PITCH[activity.questions[activity.q]]
	local order = pickDistinct(3, 3)
	local options = {}
	for i, which in ipairs(order) do
		options[i] = row[which + 1]
		if which == 1 then
			activity.good = i
		end
	end
	activity.question, activity.options = row[1], options
	local seconds = activity.dinner and FounderConfig.Dinner.questionSeconds or p.questionSeconds
	activity.openedAt, activity.limit, activity.deadline = now, seconds, now + seconds
end

local function finishSprint(player, data, live, now)
	local activity = live.activity
	live.activity = nil
	live.sprintReadyAt = now + FounderConfig.Sprint.cooldown
	live.changed = true
	local seconds = FounderConfig.sprintSeconds(activity.hits) * (1 + effect(data, "sprint") + boostShare(live, "sprint", now))
	if seconds <= 0 then
		return true, TEXTS.SprintNone
	end
	local cash = TaskServer.payReward(player, seconds)
	return true, string.format(TEXTS.SprintDone, activity.hits, FounderConfig.Sprint.rounds, money(cash)), { cash = cash, hits = activity.hits }
end

local function finishPitch(player, data, live, now)
	local activity = live.activity
	live.activity = nil
	live.changed = true
	if activity.dinner then -- the VIP dinner: once a day, saved
		data.founder.dinnerDay = today()
		data.founder.dirty = true
		local seconds = activity.hits * FounderConfig.Dinner.reward * (1 + effect(data, "pitch"))
		if seconds <= 0 then
			return true, TEXTS.DinnerNone
		end
		local cash = TaskServer.payReward(player, seconds, "bonus")
		return true, string.format(TEXTS.DinnerDone, activity.hits, #activity.questions, money(cash)), { cash = cash, hits = activity.hits }
	end
	data.founder.pitched[activity.stageKey] = true
	data.founder.dirty = true
	local seconds = activity.hits * FounderConfig.Pitch.reward * (1 + effect(data, "pitch"))
	if seconds <= 0 then
		return true, TEXTS.PitchNone
	end
	local cash = TaskServer.payReward(player, seconds, "bonus")
	return true, string.format(TEXTS.PitchDone, activity.hits, #activity.questions, money(cash)), { cash = cash, hits = activity.hits }
end

local function scheduleBug(live, now)
	local gap = FounderConfig.Bug.gap
	live.bugNextAt = now + gap[1] + (gap[2] - gap[1]) * math.random()
end

local function failBug(player, data, live, now)
	live.activity = nil
	live.alarmUntil = nil
	scheduleBug(live, now)
	live.changed = true
	local cost = charge(data, FounderConfig.Bug.penalty)
	return false, string.format(TEXTS.BugFailed, money(cost)), { cash = -cost }
end

-- One press in the running activity (n = 0: no answer, a round that ran out). Nothing here waits, so a double tap always
-- sees the activity as it was left.
local function pick(player, data, live, n, now)
	local activity = live.activity
	if not activity then
		return false, TEXTS.Off
	end
	if activity.kind == "sprint" then
		local s = FounderConfig.Sprint
		if n < 0 or n > 4 then return false, "Bad request" end -- 0: no answer (the round ran out)
		local reaction = now - activity.openedAt
		if now <= activity.deadline and reaction >= s.minReaction and n == activity.answer then
			activity.hits += 1
		end
		if activity.round >= s.rounds then
			return finishSprint(player, data, live, now)
		end
		activity.round += 1
		newSprintRound(activity, now)
		live.changed = true
		return true
	elseif activity.kind == "bug" then
		if n < 1 or n > #FounderConfig.Bug.buttons then return false, "Bad request" end
		if now > activity.deadline or n ~= activity.order[activity.pos] then
			return failBug(player, data, live, now)
		end
		activity.pos += 1
		live.changed = true
		if activity.pos > #activity.order then
			live.activity = nil
			live.alarmUntil = nil
			scheduleBug(live, now)
			local cash = TaskServer.payReward(player, FounderConfig.Bug.reward * (1 + effect(data, "bug")))
			return true, string.format(TEXTS.BugFixed, money(cash)), { cash = cash }
		end
		return true
	elseif activity.kind == "brainstorm" then
		local idea = FounderConfig.Brainstorm.Ideas[n]
		if not idea then return false, "Bad request" end
		local share = FounderConfig.ideaShare(idea, effect(data, "brainstorm"))
		local old = live.boost
		live.boost = { kind = idea.kind, name = idea.name, share = share, untilAt = now + idea.seconds }
		live.activity = nil
		live.boardReadyAt = now + FounderConfig.Brainstorm.cooldown
		live.changed = true
		TaskServer.setCallsBoost(player, idea.kind == "calls" and share or 0, idea.kind == "calls" and idea.seconds or 0)
		if idea.kind == "sprint" then
			live.sprintReadyAt = now
		end
		if idea.kind == "income" or (old and old.kind == "income") then
			core.updateIncome(player)
		end
		return true, string.format(TEXTS.BoostOn, idea.name, FounderConfig.ideaText(idea, effect(data, "brainstorm")))
	elseif activity.kind == "pitch" then
		if n < 0 or n > 3 then return false, "Bad request" end -- 0: no answer (the question ran out)
		if now <= activity.deadline and n == activity.good then
			activity.hits += 1
		end
		if activity.q >= #activity.questions then
			return finishPitch(player, data, live, now)
		end
		activity.q += 1
		newPitchQuestion(activity, now)
		live.changed = true
		return true
	end
	return false, TEXTS.Off
end

local function start(player, data, live, which, now)
	if live.activity then
		return false, TEXTS.Busy
	end
	if which == "sprint" then
		if not sprintOn(data) then return false, TEXTS.Locked end
		if now < live.sprintReadyAt then return false, string.format(TEXTS.Cooldown, math.ceil(live.sprintReadyAt - now)) end
		if not closeEnough(player, data, "Desk") then return false, TEXTS.TooFar end
		live.activity = { kind = "sprint", round = 1, hits = 0 }
		newSprintRound(live.activity, now)
	elseif which == "bug" then
		if not bugOn(data) or not live.alarmUntil then return false, TEXTS.Locked end
		if not closeEnough(player, data, "Rack") then return false, TEXTS.TooFar end
		local limit = FounderConfig.Bug.limit
		live.activity = { kind = "bug", order = pickDistinct(#FounderConfig.Bug.buttons, #FounderConfig.Bug.buttons), pos = 1, limit = limit, deadline = now + limit }
	elseif which == "brainstorm" then
		if not boardOn(data) then return false, TEXTS.Locked end
		if now < live.boardReadyAt then return false, string.format(TEXTS.Cooldown, math.ceil(live.boardReadyAt - now)) end
		if not closeEnough(player, data, "Board") then return false, TEXTS.TooFar end
		local ideas = {}
		for i, idea in ipairs(FounderConfig.Brainstorm.Ideas) do
			ideas[i] = { icon = idea.icon, name = idea.name, text = FounderConfig.ideaText(idea, effect(data, "brainstorm")) }
		end
		live.activity = { kind = "brainstorm", ideas = ideas, limit = 60, deadline = now + 60 }
	elseif which == "pitch" then
		local stage = pitchOffered(data)
		if not stage then return false, TEXTS.Locked end
		if not closeEnough(player, data, "Desk") then return false, TEXTS.TooFar end
		live.activity = { kind = "pitch", stageKey = stage.key, stageName = stage.name, q = 1, hits = 0,
			questions = pickDistinct(#PITCH, FounderConfig.Pitch.questions) }
		newPitchQuestion(live.activity, now)
	elseif which == "dinner" then
		if not (ShopServer.isVip and ShopServer.isVip(player)) then return false, TEXTS.DinnerVip end
		if data.founder.dinnerDay >= today() then return false, TEXTS.DinnerTomorrow end
		local root = player.Character and player.Character:FindFirstChild("HumanoidRootPart")
		local offset = root and (root.Position - dinnerPosition())
		if not offset or Vector3.new(offset.X, 0, offset.Z).Magnitude > FounderConfig.Dinner.reach then return false, TEXTS.TooFar end
		live.activity = { kind = "pitch", dinner = true, stageKey = "Dinner", stageName = TEXTS.DinnerTitle, q = 1, hits = 0,
			questions = pickDistinct(#PITCH, FounderConfig.Dinner.questions) }
		newPitchQuestion(live.activity, now)
	else
		return false, "Bad request"
	end
	live.changed = true
	return true
end

-- Requests -------------------------------------------------------------------------------------------

local function takeToken(live, now)
	local limit = FounderConfig.RateLimit
	live.tokens = math.min(limit.burst, live.tokens + (now - live.tokensAt) * limit.perSecond)
	live.tokensAt = now
	if live.tokens < 1 then
		return false
	end
	live.tokens -= 1
	return true
end

local function onAction(player, action, arg)
	if not FounderConfig.Enabled then
		return false, TEXTS.Off
	end
	local data = core.getData(player)
	local founder = data and data.founder
	if not founder or not data.ready then
		return false, TEXTS.Loading
	end
	local live = founder.live
	local now = os.clock()
	if typeof(action) ~= "string" then
		warnBad(player, live, now, "the action is not text")
		return false, "Bad request"
	end
	if not takeToken(live, now) then
		return false, TEXTS.Slow
	end
	local ok, message, info
	if action == "Sync" then
		live.changed = true
		ok = true
	elseif action == "Start" then
		if IpoServer.isBusy(data) then
			ok, message = false, TEXTS.Loading
		elseif typeof(arg) ~= "string" then
			warnBad(player, live, now, "Start needs an activity name")
			return false, "Bad request"
		else
			ok, message = start(player, data, live, arg, now)
		end
	elseif action == "Pick" then
		if not (isNumber(arg) and arg % 1 == 0) then
			warnBad(player, live, now, "Pick needs a button number")
			return false, "Bad request"
		end
		ok, message, info = pick(player, data, live, arg, now)
	elseif action == "Cancel" then
		local activity = live.activity
		local untouched = activity and ((activity.kind == "sprint" and activity.round == 1) or (activity.kind == "pitch" and activity.q == 1))
		if untouched then
			live.activity = nil -- closed before the first answer: no cooldown, the pitch stays offered
			live.changed = true
			ok = true
		elseif activity and activity.kind == "sprint" then
			ok, message, info = finishSprint(player, data, live, now)
		elseif activity and activity.kind == "pitch" then
			ok, message, info = finishPitch(player, data, live, now)
		else
			live.activity = nil -- a bug can be started again while its alarm rings; a brainstorm stays ready
			live.changed = true
			ok = true
		end
	else
		warnBad(player, live, now, "unknown action " .. action:sub(1, 20))
		return false, "Unknown action"
	end
	flush(player, data, live, now)
	return ok, message, info
end

-- The tick -----------------------------------------------------------------------------------------------

-- One tick for one player (the loop below calls it; the tests call it with a fake clock)
function FounderServer.step(player, now)
	if not core or not FounderConfig.Enabled then return end
	local data = core.getData(player)
	local founder = data and data.founder
	if not founder or not data.ready then return end
	local live = founder.live

	-- A new run (an IPO): the pitches start again
	if founder.run ~= ipoCountOf(data) then
		founder.run = ipoCountOf(data)
		founder.pitched = {}
		founder.dirty = true
		live.changed = true
	end

	-- A round that runs out: the sprint and the pitch move on (an unanswered round is a miss), a bug fails
	local activity = live.activity
	if activity and activity.deadline and now > activity.deadline then
		if activity.kind == "sprint" or activity.kind == "pitch" then
			local _, text = pick(player, data, live, 0, now)
			if text then
				core.notify(player, text) -- the last round ran out: the result is told like a tap's
			end
		elseif activity.kind == "bug" then
			local _, text = failBug(player, data, live, now)
			core.notify(player, text)
		else
			live.activity = nil
			live.changed = true
		end
	end

	-- The production bug's alarm: a normal gap after the unlock, never while another activity runs or an IPO is filed
	if bugOn(data) then
		if live.alarmUntil then
			if now > live.alarmUntil and not (live.activity and live.activity.kind == "bug") then
				live.alarmUntil = nil
				scheduleBug(live, now)
				live.changed = true
				core.notify(player, TEXTS.BugGone)
			end
		elseif live.bugNextAt == nil then
			scheduleBug(live, now)
		elseif now >= live.bugNextAt then
			if live.activity or IpoServer.isBusy(data) then
				live.bugNextAt = now + 30
			else
				live.alarmUntil = now + FounderConfig.Bug.alarmSeconds
				live.bugNextAt = nil
				live.changed = true
				send(player, "alarm", FounderConfig.Bug.alarmSeconds)
			end
		end
	else
		live.bugNextAt, live.alarmUntil = nil, nil
	end

	-- A boost that ran out (the Income one changes the Income back)
	local boost = live.boost
	if boost and now >= boost.untilAt then
		live.boost = nil
		live.changed = true
		if boost.kind == "income" then
			core.updateIncome(player)
		end
	end

	-- Unlocks, the pitch offer and the VIP dinner: a change sends a new state
	local pitch = pitchOffered(data)
	live.vip = ShopServer.isVip ~= nil and ShopServer.isVip(player) or false
	live.dinnerReady = live.vip and dinnerReady(player, data) or false
	local sign = (sprintOn(data) and "s" or "") .. (bugOn(data) and "b" or "") .. (boardOn(data) and "w" or "") .. (pitch and pitch.key or "")
		.. (live.vip and "v" or "") .. (live.dinnerReady and "d" or "")
	if sign ~= live.sign then
		if pitch and live.sign ~= nil and not string.find(live.sign, pitch.key, 1, true) then
			core.notify(player, string.format(TEXTS.PitchOffer, pitch.name))
		end
		live.sign = sign
		live.changed = true
	end
	flush(player, data, live, now)
end

-- Other systems ------------------------------------------------------------------------------------------

-- The Income multiplier of a running "income" idea (1 when none): TycoonCore's updateIncome multiplies by it
function FounderServer.incomeBoost(player)
	local data = core and core.getData(player)
	local live = data and data.founder and data.founder.live
	local boost = live and live.boost
	if boost and boost.kind == "income" and os.clock() < boost.untilAt then
		return 1 + boost.share
	end
	return 1
end

-- Saving (TycoonCore calls these) --------------------------------------------------------------------------

-- Right after the save loads (after the marked load block, next to the `office` section). saved = the `founder`
-- section or nil. Bad values are skipped with a warning; unknown fields are kept for the save.
function FounderServer.setupPlayer(player, data, saved)
	local founder = { v = SECTION_VERSION, run = ipoCountOf(data), pitched = {}, dinnerDay = 0, extra = {}, dirty = false, live = newLive(os.clock()) }
	if typeof(saved) == "table" then
		founder.dirty = true
		if isNumber(saved.v) and saved.v > founder.v then
			founder.v = saved.v -- written by a newer version: keep its number
		end
		local run = saved.run
		if isNumber(run) and run >= 0 and run % 1 == 0 then
			founder.run = run
		elseif run ~= nil then
			warn("Skipped a bad founder.run in " .. player.Name .. "'s save: " .. tostring(run))
		end
		if typeof(saved.pitched) == "table" then
			for key, value in pairs(saved.pitched) do
				if typeof(key) == "string" and value == true and #key <= 40 then
					founder.pitched[key] = true
				else
					warn("Skipped a bad founder.pitched entry in " .. player.Name .. "'s save: " .. tostring(key))
				end
			end
		elseif saved.pitched ~= nil then
			warn("Skipped a bad founder.pitched in " .. player.Name .. "'s save")
		end
		local day = saved.dinnerDay
		if isNumber(day) and day >= 0 and day % 1 == 0 then
			founder.dinnerDay = day
		elseif day ~= nil then
			warn("Skipped a bad founder.dinnerDay in " .. player.Name .. "'s save: " .. tostring(day))
		end
		for key, value in pairs(saved) do
			if not KNOWN_FIELDS[key] then
				founder.extra[key] = value
			end
		end
	elseif saved ~= nil then
		warn("Skipped a bad founder section in " .. player.Name .. "'s save")
	end
	if founder.run ~= ipoCountOf(data) then -- saved in an older run: those pitches belong to it
		founder.run = ipoCountOf(data)
		founder.pitched = {}
	end
	data.founder = founder
	-- Where the stations are, for the client's prompts and the desk's seat (display only: the server measures itself)
	if core and data.slot and player.SetAttribute then
		local frame = core.plotFrame(data.slot)
		local seat, stand = FounderConfig.DeskSeat, FounderConfig.DeskStand
		player:SetAttribute("FounderSeat", frame * CFrame.new(seat.x, 0.5 + seat.y, seat.z))
		player:SetAttribute("FounderStand", frame * Vector3.new(stand.x, 0.5, stand.z))
		for name in pairs(FounderConfig.Stations) do
			player:SetAttribute("Founder" .. name, stationPosition(data, name))
		end
	end
end

-- The `founder` section as it is saved: nil until there is something to keep (a new player who never pitched)
function FounderServer.serialize(data)
	local founder = data.founder
	if not founder then return nil end
	if not founder.dirty and next(founder.pitched) == nil and founder.dinnerDay == 0 then
		return nil
	end
	local pitched = {}
	for key in pairs(founder.pitched) do
		pitched[key] = true
	end
	local out = { v = founder.v, run = founder.run, pitched = pitched, dinnerDay = founder.dinnerDay }
	for key, value in pairs(founder.extra) do -- written by newer code: kept as it was
		if out[key] == nil then
			out[key] = value
		end
	end
	return out
end

-- Studio Debug tab ------------------------------------------------------------------------------------------
-- Only registered in Studio; ShopServer's Debug remote only exists in Studio with ShopConfig.DebugInStudio on.

local function addDebugActions()
	local function allowed()
		return RunService:IsStudio() and ShopConfig.DebugInStudio
	end
	ShopServer.addDebugAction("FounderBugNow", function(player, data)
		if not allowed() or not data.founder then return "Debug is disabled" end
		if not bugOn(data) then return "Buy the Server Rack first" end
		data.founder.live.bugNextAt = os.clock()
		return "The alarm rings in a moment: run to the Server Rack"
	end)
	ShopServer.addDebugAction("FounderReady", function(player, data)
		if not allowed() or not data.founder then return "Debug is disabled" end
		local live = data.founder.live
		live.sprintReadyAt, live.boardReadyAt = 0, 0
		live.changed = true
		return "Sprint and brainstorm are ready"
	end)
	ShopServer.addDebugAction("FounderDinnerAgain", function(player, data)
		if not allowed() or not data.founder then return "Debug is disabled" end
		data.founder.dinnerDay = 0
		data.founder.dirty = true
		data.founder.live.changed = true
		return "Today's investor dinner is offered again (saved; VIP pass needed)"
	end)
	ShopServer.addDebugAction("FounderPitchAgain", function(player, data)
		if not allowed() or not data.founder then return "Debug is disabled" end
		data.founder.pitched = {}
		data.founder.dirty = true
		data.founder.live.changed = true
		return "This round's pitch is offered again (saved)"
	end)
end

-- Setup ------------------------------------------------------------------------------------------------------

function FounderServer.init(coreApi)
	core = coreApi
	if not FounderConfig.Enabled then
		return
	end
	local folder = Instance.new("Folder")
	folder.Name = "FounderRemotes"
	remotes.action = Instance.new("RemoteFunction")
	remotes.action.Name = "FounderAction"
	remotes.action.OnServerInvoke = onAction
	remotes.action.Parent = folder
	remotes.state = Instance.new("RemoteEvent")
	remotes.state.Name = "FounderState"
	remotes.state.Parent = folder
	folder.Parent = ReplicatedStorage

	if RunService:IsStudio() then
		addDebugActions()
	end

	task.spawn(function()
		while true do
			task.wait(FounderConfig.TickSeconds)
			for _, player in ipairs(Players:GetPlayers()) do
				local ok, err = pcall(FounderServer.step, player, os.clock()) -- one bad player never stops the loop
				if not ok then
					warn("Founder update failed for " .. player.Name .. ": " .. tostring(err))
				end
			end
		end
	end)
end

FounderServer._onAction = onAction -- the tests call the remote's handler directly

return FounderServer
