-- FounderConfig: the founder's own activities, in one place (overhaul 2 phase 3, the owner's point 14).
-- Put this ModuleScript in ReplicatedStorage (FounderServer and FounderClient both read it).
--
-- Four things the founder does in the office, besides answering calls (TaskServer):
--   sprint      a coding sprint at the founder desk: 5 rounds, spot the line with the bug among 4. Unlocks with the Desk.
--   bug         a production bug: an alarm rings at the Server Rack; run there and press the 4 fixes in the order
--               shown before the time runs out. Unlocks with an item that says so (OfficeConfig effect unlock = "bug").
--   brainstorm  at the blackboard by the entrance: pick 1 of 3 ideas, each a short boost. Unlocks with the first hire.
--   pitch       once per funding round (Seed and up), at the founder desk: 3 questions from investors; each good answer adds a round bonus.
--               It never blocks the round: the round is reached by the valuation, the pitch only adds Cash.
-- Everything is the server's: what is asked, the right answers (they live in FounderServer, never here), the clock,
-- the grade and the reward. The client only shows what the server sends and says which button was pressed.
-- Rewards are seconds of the player's Income, paid through TaskServer.payReward (the calls' reward budget and daily cap),
-- times (1 + the office items' effect for that activity, OfficeConfig.effect). No reward is a random amount (D9): only
-- skill and time decide it. No text here may claim odds or chance.
-- Safe to change any number or text. Never rename an activity key once it has shipped (saves use the pitch's stage keys).

local FounderConfig = {}

FounderConfig.Enabled = true

-- Where each activity happens, in the garage's frame (offsets from the floor-top center; tools/founder_test.py checks
-- them against TycoonCore's itemOffset and SIGN_OFFSET). sit/stand: the founder desk's chair and the spot next to it.
FounderConfig.Stations = {
	Desk = { x = -23, z = -10 }, -- the Desk station (TycoonCore itemOffset(1))
	Rack = { x = 23, z = -10 }, -- the Server Rack station (itemOffset(4))
	Board = { x = 0, z = 24 }, -- the blackboard (TycoonCore SIGN_OFFSET, where the old entrance sign stood)
}
FounderConfig.DeskSeat = { x = -23, y = 2.34, z = -12.6 } -- the desk prop's chair seat top (PlotArt desk, scale 1.3)
FounderConfig.DeskStand = { x = -18, z = -12.6 } -- where the founder walks to before sitting (clear of the desk's solid box)
FounderConfig.Reach = 16 -- studs from a station's center the founder must be within to start there (checked by the server)

FounderConfig.Sprint = {
	rounds = 5,
	roundSeconds = 7, -- to pick the line with the bug
	minReaction = 0.4, -- a pick faster than this is a script: it counts as wrong
	base = 20, perHit = 3, -- seconds of Income: 20 + 3 per right line (5 right = 35); 0 right pays nothing
	cooldown = 180, -- seconds after a sprint before the next
}

FounderConfig.Bug = {
	gap = { 240, 420 }, -- seconds between two alarms (the server picks inside this range)
	alarmSeconds = 60, -- how long the alarm rings: start the fix in this time, or it stops by itself (no cost)
	limit = 20, -- seconds to press the 4 fixes once started
	reward = 25, -- seconds of Income for a fix
	penalty = 10, -- seconds of Income a wrong press or the time running out costs (never below $0, never the valuation)
	buttons = { "Restart", "Rollback", "Patch", "Deploy" }, -- the 4 fixes; each alarm asks all 4 in a new order
}

FounderConfig.Brainstorm = {
	cooldown = 300, -- seconds after picking an idea before the next brainstorm
	minHires = 1,
	-- The three ideas on the board. kind: calls = calls pay `share` more; income = Income `share` more; sprint = the
	-- sprint is ready at once and pays `share` more. seconds = how long. The office items' "brainstorm" effect makes
	-- the share bigger (x (1 + effect)). One boost at a time: a new idea replaces the old one.
	Ideas = {
		{ kind = "calls", icon = "📣", name = "Referral program", text = "Calls pay %d%% more for %d min", share = 0.20, seconds = 180 },
		{ kind = "income", icon = "💎", name = "Premium plan", text = "Income +%d%% for %d min", share = 0.15, seconds = 120 },
		{ kind = "sprint", icon = "⚡", name = "Hackathon", text = "Sprint ready now, pays %d%% more for %d min", share = 0.25, seconds = 180 },
	},
}

FounderConfig.Pitch = {
	questions = 3, -- per pitch
	questionSeconds = 25, -- to answer each
	reward = 40, -- seconds of Income per good answer (a round bonus: outside the reward bank, inside the daily cap)
	minStage = 2, -- Seed: every funding round from here offers one pitch per run
}

-- The VIP Investor dinner (overhaul 2 phase 5, the owner's point 18): VIP pass holders, once a day (the daily calendar's
-- day, 08:00 UTC: saved as founder.dinnerDay), at the table in the VIP Lounge (world position: ShopServer LOUNGE_CENTER +
-- DINNER_OFFSET, checked by tools/founder_test.py). A short pitch: `questions` questions; each good answer pays `reward`
-- seconds of Income (a bonus outside the reward bank, inside the daily cap).
FounderConfig.Dinner = { at = { x = -6, y = 1, z = 74 }, reach = 12, questions = 2, reward = 60, questionSeconds = 25 }

-- The state the server sends at most this often while nothing changes (seconds)
FounderConfig.TickSeconds = 0.5
FounderConfig.RateLimit = { burst = 6, perSecond = 4 }

FounderConfig.Texts = {
	SprintPrompt = "Coding sprint",
	BugPrompt = "Fix the bug",
	BoardPrompt = "Brainstorm",
	SprintTitle = "Coding sprint",
	SprintHelp = "Tap the line with the bug",
	BugTitle = "Production bug!",
	BugHelp = "Press the fixes in this order",
	BugAlarm = "🚨 Production bug! Run to the Server Rack",
	BugGone = "The alarm stopped. Next time, run!",
	BoardTitle = "Brainstorm",
	BoardHelp = "Pick one idea",
	PitchTitle = "Investor pitch",
	DinnerTitle = "Investor dinner",
	DinnerPrompt = "Investor dinner",
	DinnerDone = "Dinner done: %d/%d good answers · +%s",
	DinnerNone = "Dinner done: the investors enjoyed the food",
	DinnerVip = "The investor dinner is for VIP pass holders",
	DinnerTomorrow = "The investors come back tomorrow",
	PitchOffer = "💼 Investors want your %s pitch! Go to your desk",
	PitchPrompt = "Investor pitch",
	PitchButton = "Pitch now",
	Cooldown = "Ready in %d s",
	TooFar = "Walk closer first",
	Busy = "Finish what you're doing first",
	Locked = "Not unlocked yet",
	Loading = "Still loading, try again in a moment",
	Off = "Not available right now",
	Slow = "One moment...",
	SprintDone = "Sprint done: %d/%d lines · +%s",
	SprintNone = "Sprint done: no bug found this time",
	BugFixed = "Bug fixed! +%s",
	BugFailed = "The fix failed: -%s",
	BoostOn = "%s: %s",
	PitchDone = "Pitch done: %d/%d good answers · +%s",
	PitchNone = "Pitch done: the investors will think about it",
}

-- Helpers used by the server, the screen and the tests ---------------------------------------------

-- Seconds of Income a sprint with `hits` right lines pays (before the items' effect): 0 for none
function FounderConfig.sprintSeconds(hits)
	local s = FounderConfig.Sprint
	if typeof(hits) ~= "number" or hits < 1 then
		return 0
	end
	return s.base + s.perHit * math.min(hits, s.rounds)
end

-- An idea's share after the office items' brainstorm effect (0.5 = +50% stronger)
function FounderConfig.ideaShare(idea, brainstormEffect)
	return idea.share * (1 + math.max(0, brainstormEffect or 0))
end

-- The text of an idea for the board: "Calls pay 30% more for 3 min"
function FounderConfig.ideaText(idea, brainstormEffect)
	return string.format(idea.text, math.floor(FounderConfig.ideaShare(idea, brainstormEffect) * 100 + 0.5), math.floor(idea.seconds / 60 + 0.5))
end

-- Warn early about mistakes that would break the activities
do
	local function number(value, minimum)
		return typeof(value) == "number" and value == value and value < math.huge and value >= minimum
	end
	local s, b, p = FounderConfig.Sprint, FounderConfig.Bug, FounderConfig.Pitch
	if not (number(s.rounds, 1) and number(s.roundSeconds, 1) and number(s.base, 0) and number(s.perHit, 0) and number(s.cooldown, 0)) then
		warn("FounderConfig: Sprint needs rounds >= 1, roundSeconds >= 1 and base, perHit, cooldown >= 0")
	end
	if not (number(b.gap[1], 30) and number(b.gap[2], b.gap[1] or 30) and number(b.limit, 5) and #b.buttons == 4) then
		warn("FounderConfig: Bug needs gap { low >= 30, high >= low }, limit >= 5 and 4 buttons")
	end
	if not (number(p.questions, 1) and number(p.reward, 0) and number(p.minStage, 2)) then
		warn("FounderConfig: Pitch needs questions >= 1, reward >= 0, minStage >= 2")
	end
	for i, idea in ipairs(FounderConfig.Brainstorm.Ideas) do
		if not (idea.kind == "calls" or idea.kind == "income" or idea.kind == "sprint") or not number(idea.share, 0) or not number(idea.seconds, 1) then
			warn("FounderConfig: brainstorm idea " .. i .. " needs kind calls/income/sprint, share >= 0, seconds >= 1")
		end
	end
	for _, text in pairs(FounderConfig.Texts) do
		local lower = string.lower(text)
		for _, word in ipairs({ "odds", "chance", "luck", "random" }) do
			if string.find(lower, word, 1, true) then
				warn("FounderConfig: a text talks about " .. word .. " (D9): " .. text)
			end
		end
	end
end

return FounderConfig
