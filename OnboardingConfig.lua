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
-- kind "employees": have `target` employees on your team.
-- kind "stage": reach the funding stage with this key (see IpoConfig.Stages) on your current run.
OnboardingConfig.Goals = {
	{ key = "Hire3", icon = "👥", text = "Hire 3 employees", kind = "employees", target = 3 },
	{ key = "Seed", icon = "🌱", text = "Reach Seed stage", kind = "stage", stage = "Seed" },
}

-- How the arrow looks
OnboardingConfig.Arrow = {
	color = Color3.fromRGB(255, 220, 60),
	beamWidth = 1.2, -- studs
	markerHeight = 9, -- studs above the target where the bouncing arrow floats (above the incubator timer)
}

-- Warn early about mistakes that would break the first minute
do
	local seen = {}
	for _, goal in ipairs(OnboardingConfig.Goals) do
		if seen[goal.key] then
			warn("OnboardingConfig: two goals share the key " .. tostring(goal.key))
		end
		seen[goal.key] = true
		if goal.kind ~= "employees" and goal.kind ~= "stage" then
			warn("OnboardingConfig: goal " .. tostring(goal.key) .. " has an unknown kind " .. tostring(goal.kind))
		end
	end
end

return OnboardingConfig
