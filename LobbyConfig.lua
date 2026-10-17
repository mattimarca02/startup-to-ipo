-- LobbyConfig: the lobby and the garages (docs/LOBBY_GARAGE_PROPOSAL.md). Put this ModuleScript in ReplicatedStorage.
-- TycoonCore (the claim), ShopServer and LobbyClient read it. Data and one pure rule (canClaim), no services, so
-- tools/lobby_test.py runs it outside Studio. Nothing here is saved: the garage a player claims is never written to
-- the save (the company lives in the save, not the garage).
--
-- ClaimEnabled (owner decision 9: it ships OFF):
--   false  as before: every joining player gets the first free garage and is sent into it; no prompt, no banner.
--   true   a joining player stays on the plaza and walks to a free garage to claim it (a "Claim garage" prompt by its
--          door); the garages stand in a ring around the plaza (PR L4).
-- It is not live: a ModuleScript is read when a server starts. Turning it on is a Studio edit plus a publish with
-- "Shut down all servers" (docs/STUDIO_SYNC_LOBBY.md says how, and how to test it in Studio first).

local LobbyConfig = {}

LobbyConfig.ClaimEnabled = false

-- The garages, one per slot: the center of the Floor (x, z; y is 0.5) and its turn in degrees (quarter turns: the
-- front, +Z in the garage's frame, turned like TycoonCore's plotFrame: 90 faces world +X). Row = today's six plots
-- (TycoonCore PLOT_SPACING 90, z 150, facing +Z): used while ClaimEnabled is off, so nothing moves for live players.
-- With the claim on, Ring (below): TycoonCore's plotCenter and the garages' turns come from it.
LobbyConfig.Row = {
	{ x = -225, z = 150, turn = 0 }, { x = -135, z = 150, turn = 0 }, { x = -45, z = 150, turn = 0 },
	{ x = 45, z = 150, turn = 0 }, { x = 135, z = 150, turn = 0 }, { x = 225, z = 150, turn = 0 },
}
-- The ring (lobby L4, while ClaimEnabled is on): six garages in a horseshoe around a 180 x 180 plaza in front of the VIP
-- Lounge's door, each turned to face the plaza (docs/LOBBY_GARAGE_PROPOSAL.md 4.2). Each floor's front-center is 95
-- studs from the plaza's center; each lot (82.6 x 86.6) is 6.4 or more from the next.
LobbyConfig.Ring = {
	{ x = -125, z = 130, turn = 90 }, { x = -125, z = 220, turn = 90 }, -- west: the doors face +X
	{ x = -45, z = 300, turn = 180 }, { x = 45, z = 300, turn = 180 }, -- north: the doors face -Z
	{ x = 125, z = 220, turn = 270 }, { x = 125, z = 130, turn = 270 }, -- east: the doors face -X
}
-- The garages the server uses: the ring with the claim on, the row with it off (nothing moves for live players)
function LobbyConfig.garages(claimEnabled)
	return claimEnabled and LobbyConfig.Ring or LobbyConfig.Row
end
LobbyConfig.Garages = LobbyConfig.garages(LobbyConfig.ClaimEnabled)

-- The plaza: where a new player stands until they claim. A first spawn further than PlazaRadius from PlazaCenter is
-- moved to PlazaSpawn (the SpawnLocation is moved there by hand; this catches a missed move). Only with the claim on.
LobbyConfig.PlazaCenter = { x = 0, z = 175 }
LobbyConfig.PlazaSpawn = { x = 0, y = 4, z = 175 }
LobbyConfig.PlazaRadius = 100

-- The claim post: beside each garage's door, 3 studs in front of the front wall, at x +7 (in the garage's frame; the
-- front wall's outer face is z 32.2, PlotBuilding.FRONT_OUT). The "Claim garage" prompt is on it.
LobbyConfig.Post = { x = 7, z = 35.2 }
LobbyConfig.PromptDistance = 10 -- the prompt's own reach (studs)
LobbyConfig.HoldSeconds = 0.5
LobbyConfig.ClaimDistance = 14 -- the server checks the player's root part is this close to the post (the prompt's 10, plus slack)
LobbyConfig.ClaimInterval = 1 -- seconds between two claim requests from one player
LobbyConfig.AutoClaimWait = 60 -- claim off: a joiner who finds no free garage waits this long (one is closing), then is kicked
LobbyConfig.ReceiptWait = 30 -- a Robux purchase waits this long for the save, counted from the claim

LobbyConfig.Texts = {
	Banner = "Walk to a free garage to start your company",
	Prompt = "Claim garage",
	Free = "FREE",
	MovingIn = "Moving in...",
	Closing = "Closing...",
	Off = "Claiming garages is off",
	Unknown = "Unknown garage",
	Mine = "You already have a garage",
	Saving = "Your last visit is still saving, try again in a few seconds",
	Taken = "Taken by %s, try another",
	ClosingNow = "This garage is closing, try another in a few seconds",
	Far = "Walk up to the garage's door first",
	TooFast = "Too fast",
	Full = "This server is full, please join another one.",
}

local function finite(n)
	return type(n) == "number" and n == n and n ~= math.huge and n ~= -math.huge
end

-- The one rule for a claim, pure (TycoonCore asks it with no yield before it writes the claim).
-- state = {
--   enabled = ClaimEnabled,
--   count = the number of garages,
--   owners = { [slot] = { name = owner's name, closing = true while their leave save runs } },
--   claims = { [userId] = { slot, leaving = true while that account's leave save runs } },
--   lastAsk = { [userId] = time of the last request },
-- }
-- request = { userId, slot, distance (studs from the root part to the post, or nil: no character), now, auto }
-- auto = the server's own claim while ClaimEnabled is off: no prompt, so no distance, rate or switch check.
-- Returns true, or false and the text to show.
function LobbyConfig.canClaim(state, request)
	local texts = LobbyConfig.Texts
	if not request.auto then
		if not state.enabled then
			return false, texts.Off
		end
		local last = state.lastAsk[request.userId]
		if last and finite(request.now) and request.now - last < LobbyConfig.ClaimInterval then
			return false, texts.TooFast
		end
	end
	local held = state.claims[request.userId]
	if held then
		return false, held.leaving and texts.Saving or texts.Mine
	end
	local slot = request.slot
	if type(slot) ~= "number" or slot ~= slot or slot % 1 ~= 0 or slot < 1 or slot > state.count then
		return false, texts.Unknown
	end
	local owner = state.owners[slot]
	if owner then
		if owner.closing then
			return false, texts.ClosingNow
		end
		return false, string.format(texts.Taken, tostring(owner.name))
	end
	if not request.auto then
		local d = request.distance
		if not finite(d) or d < 0 or d > LobbyConfig.ClaimDistance then
			return false, texts.Far
		end
	end
	return true
end

return LobbyConfig
