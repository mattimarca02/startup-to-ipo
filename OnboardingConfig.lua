-- OnboardingConfig: the first minute for brand-new players, in one place (milestone 5).
-- Put this ModuleScript in ReplicatedStorage (OnboardingServer and the goal tracker both read it).
--
-- A brand-new player (no save yet) gets one free egg, already incubating, a glowing arrow that
-- shows them where to go next, and a small goal tracker. Players who already had a save before
-- milestone 5 count as already onboarded: no free egg, no arrow, no tracker.
-- Nothing here gives Cash, Shares or anything else: finishing the goals has no reward.
--
-- Safe to change any time: texts, icons, colors and the numbers below.
-- Never change a goal "key" once it has shipped: saves store the keys of finished goals.

local OnboardingConfig = {}

-- Turns the whole first-minute flow off (no free egg, arrow or tracker). Saves are kept as they are.
OnboardingConfig.Enabled = true

-- The egg a new player finds in their first incubator (a key in CreatureConfig.Eggs).
-- It's free and given once, by the server. Its timer is the egg's normal hatchSeconds.
-- This works while ShopConfig.EggsEnabled is false: that flag only controls Robux items.
OnboardingConfig.FreeEgg = "Garage"

-- The pop-up OnboardingClient shows when the free egg is granted. "%s" becomes the egg's name
-- (from CreatureConfig), filled in by OnboardingServer.
OnboardingConfig.FreeEggMessage = "You got a free %s Egg! It's hatching in the incubator."

-- The glowing arrow ends (for good) once the player has this many employees and garage upgrades
OnboardingConfig.ArrowEndsAt = { employees = 1, upgrades = 2 }

-- The goal tracker appears once the player has this many employees (the free egg has hatched)
OnboardingConfig.TrackerAfterEmployees = 1

-- Goals, in the order the tracker shows them. Each finished goal is saved and stays finished.
-- A goal finishes whether or not the tracker shows it right now (every goal is checked every second).
-- kind "employees": have `target` employees on your team.
-- kind "stage": reach the funding stage with this key (see IpoConfig.Stages) on your current run.
-- kind "upgrades": own `target` office upgrades on your current run (an IPO resets them).
-- kind "owns": own the office upgrade named `upgrade` (a name in TycoonCore's UPGRADES list).
-- kind "calls": answer `target` customer calls, ever (TaskServer's saved count). Only while calls run
--               (TaskConfig.isActive: Studio only until the economy core); otherwise skipped, never blocking.
-- kind "chain": answer `target` calls in a row (TaskServer's saved best chain). Same rule as "calls".
-- kind "ipos": go public `target` times.
-- A goal this version can't check is skipped: it is never shown and never blocks the tracker.

-- The two goals the tracker has shown since milestone 5. Today's screen (OnboardingClient) draws one row
-- per goal of this list, so this stays the list in use until the screen draws only the goals the server
-- marks as shown (OnboardingGoalShown_<key>): see ChainEnabled below.
OnboardingConfig.Goals = {
	{ key = "Hire3", icon = "👥", text = "Hire 3 employees", kind = "employees", target = 3 },
	{ key = "Seed", icon = "🌱", text = "Reach Seed stage", kind = "stage", stage = "Seed" },
}

-- The goal chain (docs/GAMEPLAY_FIRST_HOUR_PROPOSAL.md section 4, build item 7): new goals keep coming
-- through the first hour, ShowAtOnce at a time. Hire3 and Seed are the same goals as above (a player who
-- finished them keeps them). The proposal's milestone goals come with the milestones (build item 10).
OnboardingConfig.Chain = {
	{ key = "Calls3", icon = "📞", text = "Answer 3 calls", kind = "calls", target = 3 },
	{ key = "Own3", icon = "🛒", text = "Own 3 upgrades", kind = "upgrades", target = 3 },
	{ key = "Hire3", icon = "👥", text = "Hire 3 employees", kind = "employees", target = 3 },
	{ key = "Calls10Row", icon = "🔥", text = "Answer 10 calls in a row", kind = "chain", target = 10 },
	{ key = "ServerRack", icon = "🗄️", text = "Buy the Server Rack", kind = "owns", upgrade = "Server Rack" },
	{ key = "Seed", icon = "🌱", text = "Reach Seed stage", kind = "stage", stage = "Seed" },
	{ key = "SeriesA", icon = "💼", text = "Reach Series A", kind = "stage", stage = "SeriesA" },
	{ key = "FirstIpo", icon = "🔔", text = "Go public (your first IPO)", kind = "ipos", target = 1 },
}

-- Off: the tracker uses Goals (today's two goals). On: it uses Chain. Turn it on only after OnboardingClient
-- draws just the goals the server marks as shown, at most ShowAtOnce rows (the request to the ux lane in
-- docs/lanes/gameplay.md). Turning it on or off never loses a finished goal: both lists save the same way.
OnboardingConfig.ChainEnabled = false

-- How many goals the tracker shows at a time: the first unfinished ones, in list order
OnboardingConfig.ShowAtOnce = 2

-- A shown goal that was just finished stays shown (with its tick) this many seconds before the next goal
-- takes its place
OnboardingConfig.DoneShowSeconds = 3

-- The list of goals in use (the server and the screen both ask this)
function OnboardingConfig.activeGoals()
	if OnboardingConfig.ChainEnabled == true then
		return OnboardingConfig.Chain
	end
	return OnboardingConfig.Goals
end

-- How the arrow looks
OnboardingConfig.Arrow = {
	color = Color3.fromRGB(255, 220, 60),
	beamWidthNear = 0.3, -- studs, at the player (tapered so it reads as a direction, not a wall)
	beamWidthFar = 0.9, -- studs, at the target
	markerHeight = 9, -- studs above the target where the bouncing chevron floats (above the incubator timer)
	markerSize = 3.2, -- studs across, the chevron's billboard
	bobAmplitude = 0.45, -- studs, how far the chevron bobs up and down
	bobSpeed = 2.4, -- how fast it bobs (radians/sec in the sine wave)
	pulseAmount = 0.14, -- how much the chevron grows and shrinks as it bobs
}

-- Warn early about mistakes that would break the first minute
do
	local KINDS = { employees = true, stage = true, upgrades = true, owns = true, calls = true, chain = true, ipos = true }
	local byKey = {}
	for _, list in ipairs({ OnboardingConfig.Goals, OnboardingConfig.Chain }) do
		local seen = {}
		for _, goal in ipairs(list) do
			if seen[goal.key] then
				warn("OnboardingConfig: two goals share the key " .. tostring(goal.key))
			end
			seen[goal.key] = true
			if not KINDS[goal.kind] then
				warn("OnboardingConfig: goal " .. tostring(goal.key) .. " has an unknown kind " .. tostring(goal.kind))
			end
			-- A key in both lists must be the same goal: saves keep only the key
			local other = byKey[goal.key]
			if other and (other.kind ~= goal.kind or other.target ~= goal.target or other.stage ~= goal.stage
				or other.upgrade ~= goal.upgrade) then
				warn("OnboardingConfig: goal " .. tostring(goal.key) .. " means two different things in Goals and Chain")
			end
			byKey[goal.key] = goal
		end
	end
end

return OnboardingConfig
