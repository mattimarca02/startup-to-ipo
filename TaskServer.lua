-- TaskServer: the task engine (PR 1: customer calls only).
-- Put this ModuleScript in ServerScriptService, next to TycoonCore.
-- TycoonCore owns player data and saving, and plugs this module in with TaskServer.init, after
-- EmployeeServer and IpoServer and BEFORE DailyServer (which stays last). The rules live in
-- TaskConfig (ReplicatedStorage).
--
-- PR 1 runs only in Studio (TaskConfig.isActive): outside Studio this module builds no remotes,
-- starts no loop, registers no Debug button and never creates a call. It still loads and saves the
-- "tasks" section as it was, so a player's data is never lost. PR 2 (the economy core) turns it on.
--
-- Everything is decided here, from the server clock (os.clock for durations, os.time for the day):
-- when a call arrives, whether an answer came in time, and the reward. The client sends only
-- "answer call N" (TaskRemotes.TaskAction) and never a time, a reward or an amount. A call that is
-- answered and graded here is what makes a player "engaged" for the next 3 minutes; nothing the
-- client says (movement, jumping, chat, Start, Pause) ever does.
--   TaskAction("Answer", id)  -> grade an answer: ok, message, { cash, mult, chain }
--   TaskAction("Skip", id)    -> let a call go for free (the chain stays)
--   TaskAction("Start")       -> "Tap to resume": brings calls back after quiet mode
--   TaskAction("Pause", bool) -> a window is open on the client: waiting calls freeze (at most
--                                TaskConfig.Pause.perTask seconds each)
--   TaskAction("Sync")        -> the current state, once, when the screen starts
--   TaskState (server to client) -> "state" { quiet, chain, mult, tasks = { { id, kind, left, limit } } },
--                                   "handled" count: "Team handled N calls"
--
-- Other systems ask:
--   TaskServer.isEngaged(player)       -> a valid answer was graded in the last 3 minutes
--   TaskServer.engagedSeconds(player)  -> engaged seconds today (the day starts at 08:00 UTC, like the daily calendar)
--   TaskServer.getStats(player)        -> this session's measurement numbers (gate G1)
-- The 3 h per day at full value, then 5%, is PR 2's rule and lives in IpoServer.addEarnings(kind): here
-- we only record the counters.
--
-- Pay path: task Cash goes to data.cash and then through core.addEarnings (TycoonCore's wrapper over
-- IpoServer.addEarnings), the one existing earnings path. That is the only addEarnings call in this
-- file. It runs only while the engine is active (Studio in PR 1).

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")

local TaskConfig = require(ReplicatedStorage:WaitForChild("TaskConfig"))
local IpoConfig = require(ReplicatedStorage:WaitForChild("IpoConfig")) -- the funding stage, for the rung
local DailyConfig = require(ReplicatedStorage:WaitForChild("DailyConfig")) -- dayNumber: the shared 08:00 UTC reset
local ShopConfig = require(ReplicatedStorage:WaitForChild("ShopConfig")) -- money format, DebugInStudio
local IpoServer = require(script.Parent:WaitForChild("IpoServer")) -- isBusy
local ShopServer = require(script.Parent:WaitForChild("ShopServer")) -- for the Studio Debug tab

local TEXTS = TaskConfig.Texts
local DAY_SECONDS = 24 * 60 * 60
local MAX_ID = 2 ^ 31

local TaskServer = {}

local core -- { getData, addEarnings, baseIncome }, given by TycoonCore
local remotes = {}

-- The fields of the saved "tasks" section this version knows. Others were written by newer
-- code: they're kept and saved back unchanged, never deleted.
local KNOWN_FIELDS = { sharesRun = true, done = true, bestChain = true, seen = true, engagedDay = true, engagedSeconds = true }
local COUNT_MAX = { sharesRun = 1e6, done = 1e9, bestChain = 1e6 } -- whole numbers, clamped to this on load
local SEEN_MAX = 50 -- most task keys kept in `seen`

-- Helpers ---------------------------------------------------------------

local function today()
	return DailyConfig.dayNumber(os.time())
end

local function isNumber(value)
	return typeof(value) == "number" and value == value and value > -math.huge and value < math.huge
end

local function newStats()
	return {
		online = 0, engaged = 0, -- seconds
		arrivals = 0, offered = 0, dropped = 0, -- calls that arrived / were shown / found the queue full
		answered = 0, autoResolved = 0, missed = 0, skipped = 0, early = 0, flagged = 0,
		cash = 0, teamCash = 0, rewardSeconds = 0, overBudget = 0, -- Cash paid, seconds of Income paid, seconds paid at the reduced share
		engagedIncome = 0, engagedBase = 0, -- Income and base Income summed over the engaged seconds
	}
end

local function newRun(now)
	return {
		open = {}, order = {}, nextId = 1, -- waiting tasks by id, and in arrival order
		chain = 0, misses = 0, quiet = false,
		lastGradedAt = nil, -- os.clock() of the last valid graded answer: the only thing that makes a player engaged
		lastActionAt = now, -- the last graded answer or resume (quiet mode: 90 s without one)
		nextAt = {}, lastAnswerAt = {}, -- by task key
		bucketTokens = TaskConfig.RateLimit.burst, bucketAt = now,
		answers = {}, reactions = {}, flags = {}, -- os.clock() of graded answers (last minute), last reaction times, flags (last hour)
		paused = false, settledAt = now,
		-- PR 2 (economy core): a rejoin gives a full bank and an empty flag list again, because `run` is not
		-- saved. Fix it there (save the bank and the flags' cool-down, or start a rejoin with an empty bank).
		bank = TaskConfig.BudgetBank, -- reward budget, in seconds of Income
		handled = 0, handledAt = now, -- calls the team took, not yet told to the player
		rungOverride = nil, -- Studio Debug "Set rung" (not saved)
		lastWarnAt = -math.huge,
		logAt = now + TaskConfig.LogSeconds,
		changed = false, -- the client needs a new "state"
		stats = newStats(),
	}
end

-- What the engine needs to know about a player's startup ---------------------------

local function rungOf(data)
	local override = data.tasks.run.rungOverride
	if override then
		return override
	end
	local ipo = data.ipo
	if not ipo then
		return 0
	end
	local stage = IpoConfig.Stages[IpoConfig.stageIndex(ipo.valuation, ipo.count)]
	return stage and TaskConfig.rungForStage(stage.key) or 0
end

local function ipoCountOf(data)
	return data.ipo and data.ipo.count or 0
end

local function levelOf(data)
	return TaskConfig.level(rungOf(data), ipoCountOf(data))
end

local function hiresOf(data)
	local team = data.team
	return team and team.employees and #team.employees or 0
end

local function roleCount(data, role)
	local team = data.team
	local count = 0
	if team and team.employees then
		for _, employee in ipairs(team.employees) do
			if TaskConfig.roleOf(employee.creature) == role then
				count += 1
			end
		end
	end
	return count
end

local function isEngagedRun(run, now)
	return run.lastGradedAt ~= nil and now - run.lastGradedAt <= TaskConfig.EngagedSeconds
end

-- A new day starts the counter again (stale days are ignored): the day is the daily calendar's
local function rollDay(tasks)
	local day = today()
	if tasks.engagedDay < day then
		tasks.engagedDay = day
		tasks.engagedSeconds = 0
	end
end

local function prune(list, olderThan)
	while #list > 0 and list[1] < olderThan do
		table.remove(list, 1)
	end
end

-- Bad input is ignored with a warning, but a flood of it never floods the log
local function warnBad(player, run, now, what)
	if now - run.lastWarnAt >= 10 then
		run.lastWarnAt = now
		warn("Ignored a bad task request from " .. player.Name .. ": " .. what)
	end
end

-- The client's view ------------------------------------------------------------------

local function snapshot(run, now)
	local list = {}
	for _, id in ipairs(run.order) do
		local call = run.open[id]
		table.insert(list, { id = call.id, kind = call.kind, left = math.max(0, call.deadline - now), limit = call.limit })
	end
	local row = TaskConfig.Rows[1]
	return {
		quiet = run.quiet,
		paused = run.paused, -- so the client can see when the server's freeze and its own window disagree
		chain = run.chain,
		mult = row and TaskConfig.chainMultiplier(row, run.chain) or 1,
		tasks = list,
	}
end

local function send(player, kind, payload)
	if remotes.state and player.Parent then
		remotes.state:FireClient(player, kind, payload)
	end
end

local function flush(player, run, now)
	if run.changed then
		run.changed = false
		send(player, "state", snapshot(run, now))
	end
end

-- Time, budget and pay -----------------------------------------------------------------

-- Moves the player's clocks up to `now`: online and engaged time, the reward budget, and the freeze
-- while a window is open. Called at the start of every tick and every request.
local function settle(player, data, run, now)
	local dt = math.clamp(now - run.settledAt, 0, TaskConfig.MaxStep)
	run.settledAt = now
	if dt <= 0 then
		return
	end
	local tasks = data.tasks
	local stats = run.stats
	stats.online += dt
	run.bank = math.min(TaskConfig.BudgetBank, run.bank + TaskConfig.budgetFor(rungOf(data)) * dt)

	if run.paused then
		for _, id in ipairs(run.order) do
			local call = run.open[id]
			local shift = math.min(dt, math.max(0, TaskConfig.Pause.perTask - call.pausedFor))
			if shift > 0 then
				call.deadline += shift
				call.pausedFor += shift
			end
		end
		for key, at in pairs(run.nextAt) do
			run.nextAt[key] = at + dt -- no new calls while a window is open
		end
		run.lastActionAt += dt -- and a window never counts as time away
	end

	if isEngagedRun(run, now) then
		rollDay(tasks)
		tasks.engagedSeconds = math.min(DAY_SECONDS, tasks.engagedSeconds + dt)
		tasks.dirty = true
		stats.engaged += dt
		stats.engagedIncome += data.income.Value * dt
		stats.engagedBase += core.baseIncome(player) * dt
	end
end

-- Pays `seconds` of the player's current Income. The reward budget is the autoclicker wall: up to the
-- banked seconds it pays in full, the rest pays TaskConfig.OverBudgetShare. Returns the Cash and the
-- seconds really paid.
local function pay(player, data, run, seconds)
	local full = math.min(seconds, run.bank)
	run.bank -= full
	local over = seconds - full
	local paid = full + over * TaskConfig.OverBudgetShare
	local cash = math.floor(paid * data.income.Value + 1e-6) -- the + keeps 7 x 1.3 x 10 from landing on 90.99999
	if cash > 0 then
		data.cash.Value += cash
		core.addEarnings(player, cash) -- the one existing earnings path (Studio only in PR 1)
	end
	local stats = run.stats
	stats.cash += cash
	stats.rewardSeconds += paid
	stats.overBudget += over
	return cash, paid
end

-- Tasks ---------------------------------------------------------------------------------

local function closeTask(run, id)
	run.open[id] = nil
	for i, otherId in ipairs(run.order) do
		if otherId == id then
			table.remove(run.order, i)
			break
		end
	end
end

local function openCount(run, key)
	local count = 0
	for _, call in pairs(run.open) do
		if call.kind == key then
			count += 1
		end
	end
	return count
end

local function scheduleNext(data, run, row, now)
	run.nextAt[row.key] = now + TaskConfig.gap(row, hiresOf(data), levelOf(data), math.random())
end

-- Back from quiet mode: calls come again, on a fresh timer
local function leaveQuiet(data, run, now)
	run.quiet = false
	run.misses = 0
	run.lastActionAt = now
	for _, row in ipairs(TaskConfig.Rows) do
		scheduleNext(data, run, row, now)
	end
	run.changed = true
end

-- Opens a call for the player. Returns the task, or nil when the queue is full.
local function openTask(data, run, row, now)
	if openCount(run, row.key) >= row.queue then
		run.stats.dropped += 1
		return nil
	end
	local limit = TaskConfig.limitFor(row, levelOf(data))
	local id = run.nextId
	run.nextId += 1
	run.open[id] = { id = id, kind = row.key, openedAt = now, deadline = now + limit, limit = limit, pausedFor = 0 }
	table.insert(run.order, id)
	run.stats.offered += 1
	local tasks = data.tasks
	if not tasks.seen[row.key] then
		tasks.seen[row.key] = true
		tasks.dirty = true
	end
	run.changed = true
	return run.open[id]
end

-- A task arrives. If the player is present, the team may take it (routine tasks only): it pays
-- teamPays of the reward, with no chain, and is not graded, so it never makes anyone engaged.
local function arrive(player, data, run, row, now)
	run.stats.arrivals += 1
	if row.routine and isEngagedRun(run, now) then
		local share = TaskConfig.autoShare(row, roleCount(data, row.role))
		if share > 0 and math.random() < share then
			local cash = pay(player, data, run, row.reward.seconds * row.teamPays)
			run.stats.teamCash += cash
			run.stats.autoResolved += 1
			run.handled += 1
			return
		end
	end
	openTask(data, run, row, now)
end

-- A call ran out: the chain breaks, and a few in a row start quiet mode
local function expire(run, call)
	closeTask(run, call.id)
	run.chain = 0
	run.misses += 1
	run.stats.missed += 1
	run.changed = true
end

-- Flags and grading ----------------------------------------------------------------------

local function isFlagged(run, now)
	local flags = TaskConfig.Flags
	prune(run.flags, now - 3600)
	if #run.flags >= flags.perHour then
		return true
	end
	if #run.reactions >= flags.constantAnswers then
		local sum = 0
		for _, reaction in ipairs(run.reactions) do
			sum += reaction
		end
		local mean = sum / #run.reactions
		local squares = 0
		for _, reaction in ipairs(run.reactions) do
			squares += (reaction - mean) ^ 2
		end
		return math.sqrt(squares / #run.reactions) < flags.constantDeviation
	end
	return false
end

local function validId(value)
	if typeof(value) == "number" and value == value and value % 1 == 0 and value >= 1 and value <= MAX_ID then
		return value
	end
	return nil
end

-- One safe step: nothing between "is it open and in time?" and "it is closed and paid" waits, so a
-- second request for the same call (double tap, a second invoke) always sees it gone.
local function answerTask(player, data, run, id, now)
	local call = run.open[id]
	if not call then
		return false, TEXTS.Gone
	end
	local row = TaskConfig.getRow(call.kind)
	if not row then
		closeTask(run, id)
		return false, TEXTS.Gone
	end
	if IpoServer.isBusy(data) then
		return false, TEXTS.IpoBusy
	end

	-- Limits that leave the call waiting
	prune(run.answers, now - 60)
	if #run.answers >= TaskConfig.RateLimit.answersPerMinute then
		return false, TEXTS.Slow
	end
	local last = run.lastAnswerAt[row.key]
	if row.cooldown > 0 and last and now - last < row.cooldown then
		return false, TEXTS.Slow
	end

	-- Too late: it ran out before this answer
	if now > call.deadline then
		expire(run, call)
		return false, TEXTS.TooLate
	end

	-- Too early: faster than a hand can react. It pays 0, is not graded and does not count as engaged.
	local reaction = now - call.openedAt - call.pausedFor
	if reaction < TaskConfig.MinReaction then
		closeTask(run, id)
		run.misses = 0
		run.stats.early += 1
		table.insert(run.flags, now)
		run.changed = true
		return false, TEXTS.TooEarly
	end

	-- A flagged player (many early answers, or the same reaction time every time) is paid nothing
	table.insert(run.reactions, reaction)
	if #run.reactions > TaskConfig.Flags.constantAnswers then
		table.remove(run.reactions, 1)
	end
	closeTask(run, id)
	run.changed = true
	if isFlagged(run, now) then
		run.stats.flagged += 1
		return true, nil, { cash = 0, mult = 1, chain = run.chain }
	end

	-- Graded: this is what makes the player engaged
	local tasks = data.tasks
	table.insert(run.answers, now)
	run.lastAnswerAt[row.key] = now
	run.lastGradedAt = now
	run.lastActionAt = now
	run.misses = 0
	if run.quiet then
		leaveQuiet(data, run, now)
	end
	local mult = TaskConfig.chainMultiplier(row, run.chain)
	local cash = pay(player, data, run, row.reward.seconds * mult)
	run.chain += 1
	tasks.done += 1
	tasks.bestChain = math.max(tasks.bestChain, run.chain)
	tasks.dirty = true
	run.stats.answered += 1

	local text = string.format(TEXTS.Reward, ShopConfig.formatCash(cash))
	if mult > 1 then
		text = string.format(TEXTS.Chain, text, mult)
	end
	return true, text, { cash = cash, mult = mult, chain = run.chain }
end

-- Requests -----------------------------------------------------------------------------

local function takeToken(run, now)
	local limit = TaskConfig.RateLimit
	run.bucketTokens = math.min(limit.burst, run.bucketTokens + (now - run.bucketAt) * limit.perSecond)
	run.bucketAt = now
	if run.bucketTokens < 1 then
		return false
	end
	run.bucketTokens -= 1
	return true
end

local function onAction(player, action, arg)
	if not TaskConfig.isActive() then
		return false, TEXTS.Off
	end
	local data = core.getData(player)
	local tasks = data and data.tasks
	if not tasks or not data.ready then
		return false, TEXTS.Loading
	end
	local run = tasks.run
	local now = os.clock()
	if typeof(action) ~= "string" then
		warnBad(player, run, now, "the action is not text")
		return false, "Bad request"
	end
	-- Closing a window ("Pause", false) is never refused for rate: a refused resume would leave the
	-- server frozen with no calls coming. It costs nothing (it sends a state only if it changes something).
	if not (action == "Pause" and arg == false) and not takeToken(run, now) then
		warnBad(player, run, now, "too many requests")
		return false, TEXTS.Slow
	end
	settle(player, data, run, now)

	local ok, message, info
	if action == "Answer" or action == "Skip" then
		local id = validId(arg)
		if not id then
			warnBad(player, run, now, action .. " needs a call number")
			return false, "Bad request"
		end
		if action == "Answer" then
			ok, message, info = answerTask(player, data, run, id, now)
		else
			local call = run.open[id]
			local row = call and TaskConfig.getRow(call.kind)
			if not call or not row then
				ok, message = false, TEXTS.Gone
			elseif not row.skip then
				ok, message = false, "That can't be skipped"
			else
				closeTask(run, id) -- free, and the chain stays
				run.misses = 0
				run.stats.skipped += 1
				run.changed = true
				ok = true
			end
		end

	elseif action == "Start" then
		-- "Tap to resume": after quiet mode, a call comes at once (and is the one to answer)
		ok = true
		if run.quiet and not IpoServer.isBusy(data) then
			leaveQuiet(data, run, now)
			local row = TaskConfig.Rows[1]
			if row and TaskConfig.isUnlocked(row, rungOf(data), ipoCountOf(data)) then
				openTask(data, run, row, now)
			end
		end

	elseif action == "Pause" then
		if typeof(arg) ~= "boolean" then
			warnBad(player, run, now, "Pause needs true or false")
			return false, "Bad request"
		end
		if run.paused ~= arg then
			run.paused = arg
			run.changed = true -- a fresh state, so the countdown the player sees on closing the window is exact
		end
		ok = true

	elseif action == "Sync" then
		run.changed = true -- the state carries `paused`: the client compares it with its own window
		ok = true

	else
		warnBad(player, run, now, "unknown action " .. action:sub(1, 20))
		return false, "Unknown action"
	end

	flush(player, run, now)
	return ok, message, info
end

-- The tick -----------------------------------------------------------------------------

-- The measurement numbers for gate G1 (docs/LONG_GAME_PROPOSAL.md section 8):
--   fSecs = seconds of Income paid per engaged second. THIS IS THE G1 f: it does not depend on the
--           player's Income, so a Cash x2 pass (or any multiplier) cannot move it.
--   fCash = task Cash per engaged second / base Income per second (base = no passes, with the IPO
--           multiplier). Information only, NOT the G1 number: the Cash paid already contains the
--           pass multipliers and the base does not, so passes inflate it.
local function statsNumbers(data)
	local run = data.tasks.run
	local stats = run.stats
	return {
		rung = rungOf(data), hires = hiresOf(data),
		online = stats.online, engaged = stats.engaged,
		arrivals = stats.arrivals, offered = stats.offered, answered = stats.answered, missed = stats.missed, autoResolved = stats.autoResolved,
		skipped = stats.skipped, dropped = stats.dropped, early = stats.early, flagged = stats.flagged,
		cash = stats.cash, teamCash = stats.teamCash, rewardSeconds = stats.rewardSeconds, overBudget = stats.overBudget,
		fSecs = stats.engaged > 0 and stats.rewardSeconds / stats.engaged or 0, -- the G1 f
		fCash = stats.engagedBase > 0 and stats.cash / stats.engagedBase or 0, -- information only (passes inflate it)
		engagedToday = data.tasks.engagedSeconds,
		bestChain = data.tasks.bestChain,
	}
end

local function statsLine(player, data)
	local n = statsNumbers(data)
	return string.format(
		"[TaskStats] %s rung=%d (%s) hires=%d online=%ds engaged=%ds offered=%d answered=%d missed=%d team=%d skipped=%d dropped=%d early=%d flagged=%d cash=%d (team %d) rewardSec=%.1f overBudgetSec=%.1f fSecs=%.3f (G1 f) fCash=%.3f (info, passes inflate it) engagedToday=%ds bestChain=%d",
		player.Name, n.rung, TaskConfig.RungNames[n.rung + 1] or "?", n.hires, n.online, n.engaged, n.offered, n.answered, n.missed,
		n.autoResolved, n.skipped, n.dropped, n.early, n.flagged, n.cash, n.teamCash, n.rewardSeconds, n.overBudget,
		n.fSecs, n.fCash, n.engagedToday, n.bestChain)
end

-- A short line for the Studio Debug tab (the log line above is too long for its label)
local function statsSummary(data)
	local n = statsNumbers(data)
	return string.format("Rung %d · hires %d · engaged %ds · %d answered, %d missed, %d team · cash %d · G1 f = %.2f (Income-seconds per engaged second) · fCash %.2f (info only, passes inflate it)",
		n.rung, n.hires, n.engaged, n.answered, n.missed, n.autoResolved, n.cash, n.fSecs, n.fCash)
end

-- One tick for one player (the loop below calls it; the tests call it with a fake clock)
function TaskServer.step(player, now)
	if not core or not TaskConfig.isActive() then return end -- off (live server in PR 1, or Enabled = false): never creates or pays anything
	local data = core.getData(player)
	local tasks = data and data.tasks
	if not tasks then return end
	local run = tasks.run
	if not data.ready then
		run.settledAt = now -- loading is not play time
		run.lastActionAt = now
		return
	end
	settle(player, data, run, now)

	for _, id in ipairs(table.clone(run.order)) do
		local call = run.open[id]
		if call and now > call.deadline then
			expire(run, call)
		end
	end

	if not run.quiet and not run.paused
		and (run.misses >= TaskConfig.Quiet.misses or now - run.lastActionAt > TaskConfig.Quiet.idleSeconds) then
		run.quiet = true
		run.changed = true
	end

	if not run.quiet and not IpoServer.isBusy(data) then
		local rung, ipoCount = rungOf(data), ipoCountOf(data)
		for _, row in ipairs(TaskConfig.Rows) do
			if TaskConfig.isUnlocked(row, rung, ipoCount) then
				local at = run.nextAt[row.key]
				if at == nil then
					scheduleNext(data, run, row, now)
				elseif now >= at and not run.paused then
					scheduleNext(data, run, row, now)
					arrive(player, data, run, row, now)
				end
			end
		end
	end

	if run.handled > 0 and now - run.handledAt >= TaskConfig.HandledNoteSeconds then
		send(player, "handled", run.handled)
		run.handled = 0
		run.handledAt = now
	end
	flush(player, run, now)

	if now >= run.logAt then
		run.logAt = now + TaskConfig.LogSeconds
		print(statsLine(player, data))
	end
end

-- Other systems --------------------------------------------------------------------------

function TaskServer.isEngaged(player)
	if not core or not TaskConfig.isActive() then
		return false
	end
	local data = core.getData(player)
	local tasks = data and data.tasks
	return tasks ~= nil and isEngagedRun(tasks.run, os.clock())
end

-- Engaged seconds today (0 if the saved day is an older one)
function TaskServer.engagedSeconds(player)
	local data = core and core.getData(player)
	local tasks = data and data.tasks
	if not tasks then
		return 0
	end
	return tasks.engagedDay >= today() and math.floor(tasks.engagedSeconds) or 0
end

function TaskServer.getStats(player)
	local data = core and core.getData(player)
	return data and data.tasks and statsNumbers(data) or nil
end

-- Saving (TycoonCore calls these) ----------------------------------------------------------

-- Called right after the player's save loads, after EmployeeServer and before DailyServer. savedTasks is
-- the "tasks" part of the save, or nil (every save from before this version, and players who never had
-- tasks). Nothing is created or paid here. Bad values are skipped (or clamped) with a warning, never an
-- error, and only this section is touched.
function TaskServer.setupPlayer(player, data, savedTasks)
	local tasks = {
		sharesRun = 0, -- the IPO count a pitch's Shares reward was last used for (later PRs; saved)
		done = 0, -- calls answered and graded, ever (saved)
		bestChain = 0, -- longest chain of answered calls (saved)
		seen = {}, -- task keys the player has met (saved)
		engagedDay = 0, -- DailyConfig.dayNumber the engaged counter belongs to (saved)
		engagedSeconds = 0, -- engaged seconds on that day (saved)
		unknown = {}, -- fields of the saved section this version doesn't know (saved back as they were)
		dirty = false, -- true once there is something to save: a loaded section, or any change
		run = newRun(os.clock()),
	}
	if typeof(savedTasks) == "table" then
		tasks.dirty = true
		for field, maximum in pairs(COUNT_MAX) do
			local value = savedTasks[field]
			if value ~= nil then
				if isNumber(value) and value >= 0 and value % 1 == 0 then
					tasks[field] = math.min(value, maximum)
					if value > maximum then
						warn(string.format("Clamped tasks.%s in %s's save: %s -> %d", field, player.Name, tostring(value), maximum))
					end
				else
					warn("Skipped a bad tasks." .. field .. " in " .. player.Name .. "'s save: " .. tostring(value))
				end
			end
		end
		local day = savedTasks.engagedDay
		if day ~= nil then
			if isNumber(day) and day >= 0 and day % 1 == 0 then
				tasks.engagedDay = day
			else
				warn("Skipped a bad tasks.engagedDay in " .. player.Name .. "'s save: " .. tostring(day))
			end
		end
		local seconds = savedTasks.engagedSeconds
		if seconds ~= nil then
			if isNumber(seconds) and seconds >= 0 then
				tasks.engagedSeconds = math.min(DAY_SECONDS, math.floor(seconds))
				if seconds > DAY_SECONDS then
					warn(string.format("Clamped tasks.engagedSeconds in %s's save: %s -> %d", player.Name, tostring(seconds), DAY_SECONDS))
				end
			else
				warn("Skipped a bad tasks.engagedSeconds in " .. player.Name .. "'s save: " .. tostring(seconds))
			end
		end
		local seen = savedTasks.seen
		if typeof(seen) == "table" then
			local kept = 0
			for key, value in pairs(seen) do
				if typeof(key) == "string" and value == true and kept < SEEN_MAX then
					tasks.seen[key] = true
					kept += 1
				else
					warn("Skipped a bad tasks.seen entry in " .. player.Name .. "'s save: " .. tostring(key))
				end
			end
		elseif seen ~= nil then
			warn("Skipped a bad tasks.seen in " .. player.Name .. "'s save")
		end
		for key, value in pairs(savedTasks) do
			if not KNOWN_FIELDS[key] then
				tasks.unknown[key] = value
			end
		end
		-- A counter dated after today is bad data (or a clock that was wrong): the engaged counters of this
		-- section start again (day and seconds); the other fields and every other section stay as they are
		if tasks.engagedDay > today() then
			warn(string.format("%s's engaged day is in the future (day %d, today is %d): the engaged seconds start again", player.Name, tasks.engagedDay, today()))
			tasks.engagedDay = 0
			tasks.engagedSeconds = 0
		end
		rollDay(tasks) -- an older day's seconds are ignored
	elseif savedTasks ~= nil then
		warn("Skipped a bad tasks section in " .. player.Name .. "'s save")
	end
	data.tasks = tasks
end

-- The part of the save file that belongs to the task engine. nil (no section) until there is something
-- to keep: players who never had tasks (everyone outside Studio in PR 1) get no new section.
function TaskServer.serialize(data)
	local tasks = data.tasks
	if not tasks or not tasks.dirty then return nil end
	local seen = {}
	for key in pairs(tasks.seen) do
		seen[key] = true
	end
	local section = {
		sharesRun = tasks.sharesRun,
		done = tasks.done,
		bestChain = tasks.bestChain,
		seen = seen,
		engagedDay = tasks.engagedDay,
		engagedSeconds = math.floor(tasks.engagedSeconds),
	}
	for key, value in pairs(tasks.unknown) do -- written by newer code: kept as it was
		if section[key] == nil then
			section[key] = value
		end
	end
	return section
end

-- Studio Debug tab -------------------------------------------------------------------------
-- Only registered in Studio, and ShopServer's Debug remote only exists in Studio with
-- ShopConfig.DebugInStudio on. Each handler checks both again. Live servers never run these.

local function debugAllowed()
	if not RunService:IsStudio() or not ShopConfig.DebugInStudio then
		return "Debug is disabled"
	end
	if not TaskConfig.isActive() then
		return TEXTS.Off
	end
	return nil
end

local function addDebugActions()
	-- "Set rung": the rung is the ladder position tasks scale with (hires and Income stay as they are).
	-- Text "0".."4" sets it, "auto" goes back to the real funding stage. Not saved.
	ShopServer.addDebugAction("TaskSetRung", function(player, data, text)
		local refused = debugAllowed()
		if refused then return refused end
		local run = data.tasks.run
		if text == "auto" then
			run.rungOverride = nil
			run.nextAt = {}
			return "Rung back to your funding stage: " .. (TaskConfig.RungNames[rungOf(data) + 1] or "?")
		end
		local rung = tonumber(text)
		if not rung or rung % 1 ~= 0 or rung < 0 or rung > TaskConfig.MaxRung then
			return "Bad rung"
		end
		run.rungOverride = rung
		run.nextAt = {}
		return "Rung set to " .. rung .. " (" .. (TaskConfig.RungNames[rung + 1] or "?") .. "), not saved"
	end)
	ShopServer.addDebugAction("TaskStats", function(player, data)
		local refused = debugAllowed()
		if refused then return refused end
		print(statsLine(player, data))
		return statsSummary(data)
	end)
	ShopServer.addDebugAction("TaskSpawn", function(player, data)
		local refused = debugAllowed()
		if refused then return refused end
		local run = data.tasks.run
		local row = TaskConfig.Rows[1]
		local now = os.clock()
		if not row or not openTask(data, run, row, now) then
			return "The queue is full"
		end
		flush(player, run, now)
		return "A call is waiting"
	end)
end

-- Setup -----------------------------------------------------------------------------------

function TaskServer.init(coreApi)
	core = coreApi
	if not TaskConfig.isActive() then
		return -- outside Studio in PR 1: no remotes, no loop, no Debug buttons
	end

	local folder = Instance.new("Folder")
	folder.Name = "TaskRemotes"
	remotes.action = Instance.new("RemoteFunction")
	remotes.action.Name = "TaskAction"
	remotes.action.OnServerInvoke = onAction
	remotes.action.Parent = folder
	remotes.state = Instance.new("RemoteEvent")
	remotes.state.Name = "TaskState"
	remotes.state.Parent = folder
	folder.Parent = ReplicatedStorage

	if RunService:IsStudio() then
		addDebugActions()
	end

	Players.PlayerRemoving:Connect(function(player)
		local data = core.getData(player)
		if data and data.tasks and data.tasks.run.stats.offered > 0 then
			print(statsLine(player, data))
		end
	end)

	task.spawn(function()
		while true do
			task.wait(TaskConfig.TickSeconds)
			for _, player in ipairs(Players:GetPlayers()) do
				local ok, err = pcall(TaskServer.step, player, os.clock()) -- one bad player never stops the loop
				if not ok then
					warn("Task update failed for " .. player.Name .. ": " .. tostring(err))
				end
			end
		end
	end)
end

return TaskServer
