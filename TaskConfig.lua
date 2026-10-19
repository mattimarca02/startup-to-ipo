-- TaskConfig: the task engine's rules in one place (PR 1: customer calls only).
-- Put this ModuleScript in ReplicatedStorage (TaskServer and TaskClient both read it).
--
-- A task is something the player does while playing: in PR 1 only the customer call (a phone
-- rings, tap Answer within a few seconds). TaskServer decides everything from its own clock:
-- when a call arrives, whether an answer came in time, and the reward. The client only asks
-- "answer call N". One row below = one kind of task.
--
-- WHEN CALLS START: not before the player OWNS THE DESK (the first upgrade: the phone rings on the desk).
-- A row's `unlock` says it: { rung = the ladder position it starts at, owns = the upgrade the player must own }.
-- After the first IPO every task stays on without it, because an IPO resets the upgrades (the Desk costs 0
-- but is gone until it is bought again) and calls must not stop in the middle of a run. So a row is on when
-- (IPOs >= 1) or (rung reached and the upgrade owned): TaskConfig.isUnlocked, used by TaskServer and the tests.
-- Employees still take routine calls for the player as designed (teamPays, auto), once calls are on.
-- Before that no call is scheduled or arrives, and the screen shows nothing about calls.
--
-- PR 1 runs ONLY in Studio (isActive: Enabled and (StudioOnly is off or this is Studio), like ShopConfig.DebugInStudio): outside
-- Studio the engine builds no remotes, starts no loop and shows nothing. The reason: task Cash
-- must not count 100% toward the IPO valuation before the economy core (PR 2: addEarnings(kind),
-- the 3 h/day full-value cap). PR 2 sets StudioOnly = false.
--
-- Numbers are starting values from docs/ACTIVE_LOOPS_PROPOSAL.md and docs/LONG_GAME_PROPOSAL.md,
-- to be measured in Studio (gate G1). Safe to change any time. Never rename or reuse a row "key"
-- once it has shipped: saves refer to it.
-- No text here may claim odds or randomness (D9): chance only picks which task arrives, and no
-- task stakes Cash, Shares, eggs or products on a random result.

local RunService = game:GetService("RunService")

local TaskConfig = {}

TaskConfig.Enabled = true
TaskConfig.StudioOnly = true -- PR 2 turns this off, when tasks can pay through addEarnings(kind)

-- True when the engine runs in this server (and when the client may build its screen)
function TaskConfig.isActive()
	return TaskConfig.Enabled == true and (TaskConfig.StudioOnly ~= true or RunService:IsStudio())
end

-- One row per task. Seconds are seconds of the player's current Income (passes and IPO multiplier
-- included), so a reward grows with the startup.
--   wave, role  -> which tasks come first; which employees can take it (a role of CreatureRoles)
--   action      -> click (tap before the limit) | choose | timing | targets. PR 1 has only click.
--   every       -> gap between arrivals, seconds, a random value from this range
--   queue       -> most waiting at once: a full queue drops the arrival
--   limit       -> seconds the player has to act
--   reward      -> seconds x chain: each answered call in a row adds `step`, up to `max`.
--                  An expired call resets the chain; Skip keeps it.
--   miss        -> seconds of Income lost when it expires. Reserved: 0 for calls, not used in PR 1.
--   auto        -> share of arrivals one employee of the role takes (more employees: see autoShare)
--   teamPays    -> what a call the team took pays, as a share of the reward (no chain)
--   demand      -> arrivals speed up by this much per hire (capped, see DemandCap)
--   cooldown    -> seconds between two answers to this kind (0 = none)
--   skip        -> true when the player may skip it for free
--   routine     -> true: the team may take it. Exceptions (pitch, events, crisis) never are.
--   unlock      -> { rung, owns }: the rung where it starts and the upgrade (a name in TycoonCore's UPGRADES)
--                  the player must own. After the first IPO every task is on, with or without the upgrade.
TaskConfig.Rows = {
	{
		key = "Call", name = "Customer call", icon = "📞",
		wave = 1, role = "sales", action = "click",
		every = { 20, 40 }, queue = 3, limit = 8,
		reward = { seconds = 7, chain = { step = 0.1, max = 2 } },
		miss = 0, auto = 0.20, teamPays = 0.5, demand = 0.08, cooldown = 0,
		skip = true, routine = true,
		unlock = { rung = 0, owns = "Desk" }, -- the first upgrade (cost 0): calls start when it is bought
	},
}

-- Demand: gap = U(every) / (D x R). D = min(DemandCap, 1 + demand x hires).
TaskConfig.DemandCap = 2.0
-- The team takes an arrival with A = min(AutoCap, 1 - (1 - auto)^employees of the role): the founder
-- always keeps at least 1 - AutoCap of the calls.
TaskConfig.AutoCap = 0.75

-- Difficulty: level = rung + min(IPOs, ipoLevels). R = min(gapMax, 1 + gapPerLevel x level) speeds
-- arrivals up; limits shrink to at least limitMin.
TaskConfig.Difficulty = { gapPerLevel = 0.02, gapMax = 1.4, limitPerLevel = 0.03, limitMin = 0.65, ipoLevels = 10 }

-- Rungs: the ladder position the tasks care about. The game has 5 funding stages until PR 2 adds
-- SeriesCD and PreIpo, so IPO-ready counts as rung 4 (the Series C+D budget and difficulty).
-- Keys are IpoConfig.Stages keys. PR 2 swaps in the 7-stage mapping.
TaskConfig.RungNames = { "Garage", "Seed", "Series A", "Series B", "Series C", "IPO-ready" } -- rung 0 first
TaskConfig.StageToRung = { Garage = 0, Seed = 1, SeriesA = 2, SeriesB = 3, SeriesC = 4, IpoReady = 5 } -- overhaul 2: six stages
TaskConfig.MaxRung = 5 -- the highest rung the stages reach (Debug "Set rung" stops here)

-- Reward budget (the autoclicker wall): per online second the player is paid at most Budget[rung]
-- seconds of Income at full value. Unused budget banks up to BudgetBank seconds; beyond it a reward
-- pays only OverBudgetShare of the rest. Index = rung + 1.
TaskConfig.Budget = { 0.85, 0.85, 0.95, 1.05, 1.15, 1.25 }
TaskConfig.BudgetBank = 60
TaskConfig.OverBudgetShare = 0.20

-- Engaged: the server graded a valid answer in the last EngagedSeconds. Only a graded answer sets it
-- (not a skip, a team-taken call, movement or anything the client says).
TaskConfig.EngagedSeconds = 180
TaskConfig.MinReaction = 0.25 -- seconds. A faster answer pays 0, is not graded and does not count as engaged

-- Quiet mode: after this many expired calls in a row, or this long without a graded answer, no new
-- task arrives until the player taps "Tap to resume" or answers a waiting one.
TaskConfig.Quiet = { misses = 3, idleSeconds = 90 }

-- A player is flagged (answers pay 0 and are not engaged) when too many answers came in under
-- MinReaction in the last hour, or when their last `constantAnswers` reactions are all nearly the same
-- (a standard deviation under constantDeviation seconds: a script, not a hand).
TaskConfig.Flags = { perHour = 20, constantAnswers = 30, constantDeviation = 0.025 }

-- Remote limits per player: a token bucket for every request, and a cap on graded answers
TaskConfig.RateLimit = { burst = 8, perSecond = 8, answersPerMinute = 40 }

-- A window open on the client freezes the waiting calls (the client tells the server). Each call can
-- be frozen this long at most, so a lying client gains little.
TaskConfig.Pause = { perTask = 30 }

TaskConfig.TickSeconds = 0.5 -- how often the server checks arrivals and expiries
TaskConfig.MaxStep = 2 -- the longest step the clock counts at once (a server hiccup never pays a burst)
TaskConfig.LogSeconds = 600 -- a stats line in the server log every 10 minutes per player (gate G1)
TaskConfig.HandledNoteSeconds = 10 -- "Team handled N calls" is sent at most this often, as one line

-- Which task role each creature takes (CreatureConfig has only free-text job titles).
-- Roles: sales, eng (engineering), ops, mkt (marketing), fin (finance). The CEO and the investor
-- dragon take none. PR 1 only reads "sales".
TaskConfig.CreatureRoles = {
	HustleHamster = "sales", SalesShark = "sales",
	CodingCat = "eng", BugBeetle = "eng", ServerSloth = "eng",
	CoffeeCapybara = "ops", MemoMole = "ops",
	PixelPigeon = "mkt", PitchParrot = "mkt",
	LedgerLlama = "fin",
}

-- Texts. Calm and factual: nothing about odds, chance or luck (D9).
TaskConfig.Texts = {
	Answer = "Answer",
	Resume = "📞 Tap to resume",
	Handled = "Team handled %d %s", -- count, "call"/"calls"
	Reward = "+%s", -- the Cash
	Chain = "%s · x%.1f chain", -- reward text, chain multiplier
	Missed = "Missed call",
	Off = "Tasks are off right now",
	Loading = "Still loading, try again in a moment",
	IpoBusy = "Your IPO is being filed, try again in a moment",
	Gone = "That call is gone",
	TooLate = "Too late: the call ended",
	TooEarly = "Too early: wait for the call",
	Slow = "One moment...",
}

-- Helpers used by the server, the screen and the tests -----------------------------

function TaskConfig.getRow(key)
	for _, row in ipairs(TaskConfig.Rows) do
		if row.key == key then
			return row
		end
	end
	return nil
end

-- level = rung + the IPOs done (at most Difficulty.ipoLevels)
function TaskConfig.level(rung, ipoCount)
	return math.max(0, rung) + math.min(math.max(0, ipoCount), TaskConfig.Difficulty.ipoLevels)
end

-- D: how much faster calls come with this many hires, never more than DemandCap
function TaskConfig.demandFactor(row, hires)
	return math.min(TaskConfig.DemandCap, 1 + row.demand * math.max(0, hires))
end

-- R: how much faster they come at this level
function TaskConfig.paceFactor(level)
	local d = TaskConfig.Difficulty
	return math.min(d.gapMax, 1 + d.gapPerLevel * math.max(0, level))
end

-- Seconds until the next arrival; roll is a number from 0 to 1 that picks inside `every`
function TaskConfig.gap(row, hires, level, roll)
	local low, high = row.every[1], row.every[2]
	return (low + (high - low) * roll) / (TaskConfig.demandFactor(row, hires) * TaskConfig.paceFactor(level))
end

-- Seconds the player has to act at this level
function TaskConfig.limitFor(row, level)
	local d = TaskConfig.Difficulty
	return row.limit * math.max(d.limitMin, 1 - d.limitPerLevel * math.max(0, level))
end

-- Share of arrivals the team takes with `count` employees of the row's role (0 when none)
function TaskConfig.autoShare(row, count)
	if count <= 0 or row.auto <= 0 then
		return 0
	end
	return math.min(TaskConfig.AutoCap, 1 - (1 - row.auto) ^ count)
end

-- The reward multiplier for an answer after `chain` answered calls in a row (1 when the chain is 0)
function TaskConfig.chainMultiplier(row, chain)
	local c = row.reward.chain
	return math.min(c.max, 1 + c.step * math.max(0, chain))
end

-- Seconds of Income an answer is worth (before the budget) after `chain` answers in a row
function TaskConfig.rewardSeconds(row, chain)
	return row.reward.seconds * TaskConfig.chainMultiplier(row, chain)
end

-- The reward budget at a rung (seconds of Income per online second)
function TaskConfig.budgetFor(rung)
	return TaskConfig.Budget[math.clamp(math.floor(rung) + 1, 1, #TaskConfig.Budget)]
end

-- A task is on from its rung once the player owns the upgrade it needs, and every task is on after the
-- first IPO (the IPO resets the upgrades, see the header). `owned` is the player's set of upgrade names,
-- { [name] = true } (data.owned); without it a row that needs an upgrade is off.
function TaskConfig.isUnlocked(row, rung, ipoCount, owned)
	if ipoCount >= 1 then
		return true
	end
	if rung < row.unlock.rung then
		return false
	end
	local needs = row.unlock.owns
	return needs == nil or (owned ~= nil and owned[needs] == true)
end

-- Rung of a funding stage key (nil for a stage this table doesn't know)
function TaskConfig.rungForStage(stageKey)
	return TaskConfig.StageToRung[stageKey]
end

-- The task role of a creature key, or nil
function TaskConfig.roleOf(creatureKey)
	return TaskConfig.CreatureRoles[creatureKey]
end

-- Warn early about mistakes that would break the engine
do
	local seen = {}
	local actions = { click = true, choose = true, timing = true, targets = true }
	local function number(value, minimum)
		return typeof(value) == "number" and value == value and value < math.huge and value >= minimum
	end
	for i, row in ipairs(TaskConfig.Rows) do
		local name = tostring(row.key or ("row " .. i))
		if typeof(row.key) ~= "string" or seen[row.key] then
			warn("TaskConfig: row " .. i .. " needs its own key (got " .. tostring(row.key) .. ")")
		end
		seen[row.key or i] = true
		if not actions[row.action] then
			warn("TaskConfig: " .. name .. " has an unknown action: " .. tostring(row.action))
		end
		if typeof(row.every) ~= "table" or not number(row.every[1], 1) or not number(row.every[2], row.every[1] or 1) then
			warn("TaskConfig: " .. name .. " every must be { low, high } with 1 <= low <= high")
		end
		if not number(row.limit, 1) then
			warn("TaskConfig: " .. name .. " limit must be at least 1 second")
		end
		if not number(row.queue, 1) or row.queue % 1 ~= 0 then
			warn("TaskConfig: " .. name .. " queue must be a whole number, 1 or more")
		end
		local reward = row.reward
		if typeof(reward) ~= "table" or not number(reward.seconds, 0) or typeof(reward.chain) ~= "table"
			or not number(reward.chain.step, 0) or not number(reward.chain.max, 1) then
			warn("TaskConfig: " .. name .. " reward must be { seconds, chain = { step, max >= 1 } }")
		end
		if not number(row.auto, 0) or row.auto >= 1 then
			warn("TaskConfig: " .. name .. " auto must be from 0 up to (not including) 1")
		end
		if not number(row.teamPays, 0) or row.teamPays > 1 then
			warn("TaskConfig: " .. name .. " teamPays must be from 0 to 1")
		end
		if not number(row.demand, 0) then
			warn("TaskConfig: " .. name .. " demand must be 0 or more")
		end
		if not number(row.cooldown, 0) then
			warn("TaskConfig: " .. name .. " cooldown must be 0 or more")
		end
		if row.miss ~= 0 then
			warn("TaskConfig: " .. name .. " miss is reserved (0) in PR 1")
		end
		if typeof(row.unlock) ~= "table" or not number(row.unlock.rung, 0) then
			warn("TaskConfig: " .. name .. " needs unlock = { rung = number }")
		end
		if typeof(row.unlock) == "table" and row.unlock.owns ~= nil and typeof(row.unlock.owns) ~= "string" then
			warn("TaskConfig: " .. name .. " unlock.owns must be an upgrade name (text)")
		end
	end
	if #TaskConfig.Rows == 0 then
		warn("TaskConfig: no task rows")
	end
	if #TaskConfig.Budget ~= #TaskConfig.RungNames then
		warn("TaskConfig: Budget and RungNames need one entry per rung")
	end
	for stageKey, rung in pairs(TaskConfig.StageToRung) do
		if typeof(rung) ~= "number" or rung < 0 or rung > TaskConfig.MaxRung then
			warn("TaskConfig: StageToRung." .. tostring(stageKey) .. " is not a rung from 0 to MaxRung")
		end
	end
end

return TaskConfig
