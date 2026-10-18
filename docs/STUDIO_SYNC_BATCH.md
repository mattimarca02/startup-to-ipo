# Studio sync: the lanes' batch

The one Studio list for the work of the six lanes (docs/LANES.md). No lane touches Studio. When the owner merges a lane's pull request, the quality lane copies that PR's "Studio steps" (from the lane's file, `docs/lanes/<lane>.md`) into the open batch below: the scripts to paste with their SHA-256 and size, one hash block that prints `ALL OK` for the whole batch, the checks and the playtests. The owner runs a batch in one VS Code session of Claude Code with the **Roblox Studio MCP** on the **published place** (File > Open from Roblox > *Build your Startup!*, PlaceId `86395856666175`), then **File > Save to Roblox**, never Publish. Publishing is the owner's separate decision (docs/PUBLISH_RULES.md).

The older sync docs (docs/STUDIO_SYNC_MASTER.md, docs/STUDIO_SYNC_LOBBY.md, docs/STUDIO_SYNC_WORLD.md, docs/STUDIO_SYNC_HUD.md, docs/STUDIO_SYNC_SHOP.md, docs/STUDIO_SYNC_BUILDING.md) are **history**: their tables and hash blocks describe the files as they were when each was written, and the tests check them against those commits (`tools/lobby_test.py` `L1_COMMIT` and `ALL_COMMIT`, `tools/world_test.py` `SYNC_HISTORY`). New Studio steps go here only.

**The starting point.** Studio matches `main` at `fb8c057` (lobby-all, PR #32, plus the kit front turn, PR #34): the Studio sync of 2026-10-17 in docs/LOBBY_ALL_PROGRESS.md (hash block `ALL OK: the 15 scripts match the repo (lobby-all)`, `KIT OK: 36 models`, `KIT_FRONT_TURN = 180`). Its playtests 9 (a), (b) and (c) of docs/STUDIO_SYNC_LOBBY.md are **still to do** and come first in every batch below until they are done.

## How a batch is run

1. **Pull:** `git fetch`, then `main` at the commit the batch names, in a folder no other session uses (`git worktree add ../studio-batch <commit>`).
2. **Studio:** File > Open from Roblox > *Build your Startup!*; Game Settings > Security > Enable Studio Access to API Services: ON. The MCP's `get_studio_state` says Edit mode. Team Create: **View > Drafts**, commit every draft before any hash block.
3. **Create** the new scripts by hand (the MCP can't create a script inside a service): hover the parent in the Explorer, **+**, the class, **F2**, the exact name.
4. **Paste** every script of the batch's table (open the `.lua`, select all, copy; in Studio double-click the script, select all, paste; or write the file's text with the MCP's script tool).
5. **Hash block** (the batch's section) in **View > Command Bar**: it must print `ALL OK`. `DIFFERENT`: paste that file again. `MISSING`: step 3.
6. **Checks** and **playtests** of the batch, in order. Anything the batch tells you to delete (a preview folder, a check model) is deleted before saving.
7. **Run the hash block again**, then **File > Save to Roblox**. Write the date and the result at the end of the batch ("Run on ..."); a playtest that was skipped or showed an error is written down as such, never as done.

## Batch 1 (final: nine scripts from PRs #35 and #44, #36, #37, #43 and #40; `main` at `2c3a415`)

Opened 2026-10-17 by the quality lane. **Merged so far, in this order:** #38 (gameplay, `tools/lobby_test.py` only: nothing for Studio), #36 (building: the Garage's roof and sign), #35 (ux: the phone's "Claim garage" button), #41 (quality: this doc, README, CLAUDE.md, ROADMAP: nothing for Studio), #37 (world: the ring plaza garden), #43 (gameplay: the goal chain, off), #45 (quality: docs only), #40 (interiors: the rooms' furniture from the 3D kit), #46 (quality: docs only), #47 (quality: docs only) and #44 (ux: the claim button names and presses the nearest prompt; it replaces #35's `ClaimButtonClient` bytes). **No PR is open: this batch is final.** Every row below was recomputed from `main` by the quality lane (`sha256sum` and `wc -c` of the file; the five of 2026-10-17 at `853eaa3`, #43's two at `f666726` and #40's two at `cac89d9` on 2026-10-18, #44's `ClaimButtonClient` at `0fec09b`, all equal to the hashes the lane files give; on 2026-10-18 09:15 UTC all nine were recomputed again from `main` at `2c3a415`: unchanged but for `ClaimButtonClient`). Run the batch at `2c3a415` or any later `main` whose nine files still match (the hash block says).

**What the owner sees after this batch:** with `ClaimEnabled` off (as it ships and as Studio has it), only PR #36 shows: the Garage has a pitched roof, stepped gables and a sign board over the door. The claim button (#35, #44) and the garden (#37) show only with the claim on, which stays a Studio-only test (section 6); the goal chain (#43) shows nothing while `OnboardingConfig.ChainEnabled` is false (the tracker keeps Hire 3 and Seed). PR #40 shows inside the Garage: kit crates as hire desks, the desk and chair with the PC, the workbench, crates in the back-right corner, the glowing bulb (the four other rooms are unchanged). Nothing changes the save format; nothing needs a publish.

| PR | Lane | Script | Class, place | State | SHA-256 (`main` at `2c3a415`) | Bytes | Merged? |
|---|---|---|---|---|---|---|---|
| #38 | gameplay | (none: `tools/lobby_test.py` only) | | | | | merged 22:15 UTC |
| #36 | building | `PlotBuilding` | ModuleScript, ServerScriptService | changed | `f04e3b89486a4b8a3656633029412c1e666df84432c9760639e89c9361ea5788` | 42603 | merged 22:19 UTC |
| #36 | building | `PlotBuildingVisuals` | ModuleScript, ServerScriptService | changed | `2e956d553b0b5bd3ef51bf8db4b643634b86cca83111bdbe9fa7fec8405e5043` | 27493 | merged 22:19 UTC |
| #35 | ux | `ClaimButtonClient` | LocalScript, StarterPlayer > StarterPlayerScripts | new | (replaced by #44's bytes, below: never paste #35's) | | merged 22:24 UTC |
| #41 | quality | (none: docs only) | | | | | merged 22:42 UTC |
| #37 | world | `WorldArt` | ModuleScript, ServerScriptService | changed | `7c24e992b60c6319f309dbd7dfda2cafa201566afece96ddc5678e9d87c57d8f` | 17648 | merged 22:43 UTC |
| #37 | world | `WorldVisuals` | ModuleScript, ServerScriptService | changed | `3547afbbecd30e01f65285b1c483932da30751db9fa328119a267126c7563a90` | 59866 | merged 22:43 UTC |
| #43 | gameplay | `OnboardingServer` | ModuleScript, ServerScriptService | changed | `a77c805d733252ad7d4c90232092212fe872212686c74b96de6fa22ef9c0b2d7` | 16509 | merged 2026-10-18 08:19 UTC |
| #43 | gameplay | `OnboardingConfig` | ModuleScript, ReplicatedStorage | changed | `7406818ffa279b69487e73334ca1fb5dfe99e343912d1ab10301df753904f7f4` | 6883 | merged 2026-10-18 08:19 UTC |
| #45 | quality | (none: docs only) | | | | | merged 2026-10-18 08:22 UTC |
| #40 | interiors | `PlotArt` | ModuleScript, ServerScriptService | changed | `e1d3f7e0e6dd789c3d4a7135a474e8dc92eacdfb23d9c65fcc0599ea9dd2b0c6` | 63975 | merged 2026-10-18 08:27 UTC |
| #40 | interiors | `PlotVisuals` | ModuleScript, ServerScriptService | changed | `8eefee60866bb2ef0a31cbeda361e5f4bd145844d27644dd054e9e5951d8fcca` | 41197 | merged 2026-10-18 08:27 UTC |
| #46 | quality | (none: docs only) | | | | | merged 2026-10-18 08:29 UTC |
| #47 | quality | (none: docs only) | | | | | merged 2026-10-18 08:49 UTC |
| #44 | ux | `ClaimButtonClient` | LocalScript, StarterPlayer > StarterPlayerScripts | new (Studio never had #35's) | `b00fcd8637d378eca02d3e6b4b856ee9fea8d184ea3086a2031d0eee124817c4` | 10261 | merged 2026-10-18 (0fec09b) |

### 1. Before you start

The playtests 9 (a), (b) and (c) of docs/STUDIO_SYNC_LOBBY.md (the lobby-all sync of 2026-10-17 did everything but them). Do them before pasting anything new, so a problem is lobby-all's or the batch's, never a mix. Then: `git fetch`, `git worktree add ../studio-batch 2c3a415` (or a later `main`), and in Studio commit every Team Create draft (View > Drafts).

### 2. Scripts to create by hand first

| Name | Class | Parent | From PR |
|---|---|---|---|
| `ClaimButtonClient` | LocalScript | StarterPlayer > StarterPlayerScripts | #35 (bytes of #44) |

Hover **StarterPlayer > StarterPlayerScripts** in the Explorer, **+**, choose **LocalScript**, press **F2** and name it exactly `ClaimButtonClient`. (The MCP can't create a script inside a service.)

### 3. The list (paste in any order)

Open each `.lua` in the worktree, select all, copy; in Studio double-click the script, select all, paste (or write the file's text with the MCP's script tool). The nine rows are the same as in the table above, in the shape `tools/world_test.py` reads:

| Script | Studio | State | sha256 | bytes |
|---|---|---|---|---|
| `PlotBuilding` | ModuleScript, ServerScriptService | changed | `f04e3b89486a4b8a3656633029412c1e666df84432c9760639e89c9361ea5788` | 42603 |
| `PlotBuildingVisuals` | ModuleScript, ServerScriptService | changed | `2e956d553b0b5bd3ef51bf8db4b643634b86cca83111bdbe9fa7fec8405e5043` | 27493 |
| `ClaimButtonClient` | LocalScript, StarterPlayer > StarterPlayerScripts | new | `b00fcd8637d378eca02d3e6b4b856ee9fea8d184ea3086a2031d0eee124817c4` | 10261 |
| `WorldArt` | ModuleScript, ServerScriptService | changed | `7c24e992b60c6319f309dbd7dfda2cafa201566afece96ddc5678e9d87c57d8f` | 17648 |
| `WorldVisuals` | ModuleScript, ServerScriptService | changed | `3547afbbecd30e01f65285b1c483932da30751db9fa328119a267126c7563a90` | 59866 |
| `OnboardingServer` | ModuleScript, ServerScriptService | changed | `a77c805d733252ad7d4c90232092212fe872212686c74b96de6fa22ef9c0b2d7` | 16509 |
| `OnboardingConfig` | ModuleScript, ReplicatedStorage | changed | `7406818ffa279b69487e73334ca1fb5dfe99e343912d1ab10301df753904f7f4` | 6883 |
| `PlotArt` | ModuleScript, ServerScriptService | changed | `e1d3f7e0e6dd789c3d4a7135a474e8dc92eacdfb23d9c65fcc0599ea9dd2b0c6` | 63975 |
| `PlotVisuals` | ModuleScript, ServerScriptService | changed | `8eefee60866bb2ef0a31cbeda361e5f4bd145844d27644dd054e9e5951d8fcca` | 41197 |

`OnboardingServer` now requires `TaskConfig` (ReplicatedStorage), which exists since the task engine's sync. No other script changes: `PlotBuilding.KIT_FRONT_TURN` stays 180 (PR #34), `LobbyConfig` stays as it is (`ClaimEnabled = false`), TycoonCore is untouched by these PRs.

### 4. Hash check (command bar)

Paste the whole block into **View > Command Bar** and press Enter (with the MCP: `execute_luau`). It changes nothing. It prints `OK`, `DIFFERENT`, `MISSING` or `WRONG CLASS` per script, then `ALL OK` or `NOT YET`. Studio may drop the file's last newline or add one; both are accepted. The `WANT` table is the batch's list (section 3), one row per script, `{ name, class, place, sha256, bytes }`, filled from `main` at `2c3a415`; it must print `ALL OK: 9 scripts match the repo (batch 1)`. (The quality lane ran this block in Luau 0.742 against the nine files on `main`, in a fake place: `ALL OK`; with one byte changed: `DIFFERENT`; with the LocalScript missing: `MISSING`.)

```lua
local K = {
	0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
	0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
	0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
	0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
	0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
	0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
	0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
	0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
}
local function sha256(msg)
	local h = { 0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19 }
	local len = #msg
	msg ..= "\128" .. string.rep("\0", (55 - len) % 64) .. string.pack(">I8", len * 8)
	local w = {}
	for chunk = 1, #msg, 64 do
		for i = 0, 15 do w[i] = string.unpack(">I4", msg, chunk + i * 4) end
		for i = 16, 63 do
			local a, b = w[i - 15], w[i - 2]
			local s0 = bit32.bxor(bit32.rrotate(a, 7), bit32.rrotate(a, 18), bit32.rshift(a, 3))
			local s1 = bit32.bxor(bit32.rrotate(b, 17), bit32.rrotate(b, 19), bit32.rshift(b, 10))
			w[i] = (w[i - 16] + s0 + w[i - 7] + s1) % 2 ^ 32
		end
		local a, b, c, d, e, f, g, hh = table.unpack(h)
		for i = 0, 63 do
			local S1 = bit32.bxor(bit32.rrotate(e, 6), bit32.rrotate(e, 11), bit32.rrotate(e, 25))
			local ch = bit32.bxor(bit32.band(e, f), bit32.band(bit32.bnot(e), g))
			local t1 = (hh + S1 + ch + K[i + 1] + w[i]) % 2 ^ 32
			local S0 = bit32.bxor(bit32.rrotate(a, 2), bit32.rrotate(a, 13), bit32.rrotate(a, 22))
			local maj = bit32.bxor(bit32.band(a, b), bit32.band(a, c), bit32.band(b, c))
			local t2 = (S0 + maj) % 2 ^ 32
			hh, g, f, e, d, c, b, a = g, f, e, (d + t1) % 2 ^ 32, c, b, a, (t1 + t2) % 2 ^ 32
		end
		local r = { a, b, c, d, e, f, g, hh }
		for i = 1, 8 do h[i] = (h[i] + r[i]) % 2 ^ 32 end
	end
	local out = {}
	for i = 1, 8 do out[i] = string.format("%08x", h[i]) end
	return table.concat(out)
end

-- STUDIO_SYNC_BATCH batch 1 hash check: every script the merged lane PRs create or change. Changes nothing.
local function folderOf(place)
	if place == "StarterPlayerScripts" then
		return game:GetService("StarterPlayer"):FindFirstChild("StarterPlayerScripts")
	end
	return game:GetService(place)
end
local WANT = {
	-- main at 2c3a415 (2026-10-18): { "Name", "Class", "Place", "sha256", bytes }
	{ "PlotBuilding", "ModuleScript", "ServerScriptService", "f04e3b89486a4b8a3656633029412c1e666df84432c9760639e89c9361ea5788", 42603 },
	{ "PlotBuildingVisuals", "ModuleScript", "ServerScriptService", "2e956d553b0b5bd3ef51bf8db4b643634b86cca83111bdbe9fa7fec8405e5043", 27493 },
	{ "ClaimButtonClient", "LocalScript", "StarterPlayerScripts", "b00fcd8637d378eca02d3e6b4b856ee9fea8d184ea3086a2031d0eee124817c4", 10261 },
	{ "WorldArt", "ModuleScript", "ServerScriptService", "7c24e992b60c6319f309dbd7dfda2cafa201566afece96ddc5678e9d87c57d8f", 17648 },
	{ "WorldVisuals", "ModuleScript", "ServerScriptService", "3547afbbecd30e01f65285b1c483932da30751db9fa328119a267126c7563a90", 59866 },
	{ "OnboardingServer", "ModuleScript", "ServerScriptService", "a77c805d733252ad7d4c90232092212fe872212686c74b96de6fa22ef9c0b2d7", 16509 },
	{ "OnboardingConfig", "ModuleScript", "ReplicatedStorage", "7406818ffa279b69487e73334ca1fb5dfe99e343912d1ab10301df753904f7f4", 6883 },
	{ "PlotArt", "ModuleScript", "ServerScriptService", "e1d3f7e0e6dd789c3d4a7135a474e8dc92eacdfb23d9c65fcc0599ea9dd2b0c6", 63975 },
	{ "PlotVisuals", "ModuleScript", "ServerScriptService", "8eefee60866bb2ef0a31cbeda361e5f4bd145844d27644dd054e9e5951d8fcca", 41197 },
}
local problems = {}
for _, w in ipairs(WANT) do
	local name, class, place, hash, bytes = w[1], w[2], w[3], w[4], w[5]
	local folder = folderOf(place)
	local script = folder and folder:FindFirstChild(name)
	local result
	if not script then
		result = "MISSING (create a " .. class .. " in " .. place .. ")"
	elseif script.ClassName ~= class then
		result = "WRONG CLASS (it is a " .. script.ClassName .. ", it must be a " .. class .. ")"
	else
		local source = script.Source
		local function matches(text)
			return #text == bytes and sha256(text) == hash
		end
		-- the file as it is, or with its last newline dropped by Studio, or with one newline added by Studio
		local ok = matches(source) or matches(source .. "\n") or (string.sub(source, -2) == "\n\n" and matches(string.sub(source, 1, -2)))
		result = (ok and "OK" or "DIFFERENT") .. " " .. #source .. " bytes"
	end
	print(name, result)
	if string.sub(result, 1, 2) ~= "OK" then
		table.insert(problems, name)
	end
end
print(#problems == 0 and ("ALL OK: " .. #WANT .. " scripts match the repo (batch 1)") or ("NOT YET: fix " .. table.concat(problems, ", ")))
```

### 5. Checks (after the paste)

1. **The kit (PRs #36 and #40):** run the KitModels check of docs/STUDIO_SYNC_LOBBY.md section 5 again: it must still print `KIT OK: 36 models`. Neither PR changes a model or a manifest row (#36's Blocks are plain Parts; #40's rooms clone the same 36 models). The kit front check of the same section still says `KIT_FRONT_TURN = 180`.
2. **The Output after F5 (all five PRs):** no red error, no `OnboardingConfig` warning (#43: every goal of `Goals` and `Chain` has a known kind and an existing stage) and no warning that starts with `Plot buildings`, `Plot visuals` or `The plaza is off` (a `Plot buildings:` warning about a missing model means the kit folder lacks one: step 1).
3. **No publish and no save change:** none of the five PRs adds a save section or a remote (#43's new config keys are read only by its own scripts; #40 saves nothing and sends nothing); `LobbyConfig` is not in this batch and stays `ClaimEnabled = false` (owner decision 9).

4. **The rooms (PR #40), optional:** paste the preview block of docs/lanes/interiors.md ("Studio steps") into the command bar: it builds the five rooms in `Workspace.PREVIEW_STAGES` far from the garages and prints one line per stage; stage 1 must print `OK` with `kit MeshParts: 39` and `kit found: true`. **Delete `Workspace.PREVIEW_STAGES` before saving.**

Nothing is expected later in this batch. Batch 2 (below, the claim on) comes after it.

### 6. Playtests

In this order, each written down as done, skipped or failed:

1. **#36, claim off (as Studio has it):** F5. Your garage (a new save: the Garage stage) shows the pitched roof between the stepped gables, the sign board over the roll-up door (an orange growth-chart emblem, no text), two front windows with sills, the plinth, gutters and downpipes. Walk in through the door: the whole shell fades, the roof included; walk out: it comes back. Reset inside and outside: never stuck. The other four stages (Debug > "Building: next stage", Studio only) look as before. No new warning in the Output.
2. **#40, claim off:** in the same F5, inside your Garage: kit crates stand as the hire desks, the old desk and chair with the PC, the workbench, crates in the back-right corner and the glowing bulb; walk the aisles (no kit piece blocks you: every kit part has collision off); Debug > "Building: next stage" shows the four other rooms unchanged. The Output has no `Plot visuals:` warning (one would name a kit model built from Parts instead).
3. **#43, claim off, a new save (Debug > "Restart tutorial" or a fresh test account):** the goal tracker looks and behaves as before: Hire 3 employees, then Reach Seed stage, one row each; finishing one shows its tick; no new row, no `OnboardingConfig` warning in the Output (`ChainEnabled` is false, so the chain is not in use).
4. **#35 and #44, claim off:** still in the same F5 (or a new one): nothing new shows on the screen, the HUD is as before, no error in the Output. Test > Device, a phone in portrait and landscape: still nothing new (the button needs the claim on).
5. **#37, claim off:** the row world is unchanged: the street, the lounge, the hills as before.
6. **Claim on, Studio only, never saved (#35, #44 and #37):** set `ClaimEnabled = true` in `ReplicatedStorage > LobbyConfig` for the playtest only (docs/STUDIO_SYNC_LOBBY.md section 9 b says how and how to revert). F5: the garages stand in the ring; the plaza shows the paved square around the spawn pad, four spokes, the promenade along the garages' fronts, four lawn beds with kerbs, trees and bushes, the fountain on the north spoke, benches and lamps along the spokes; every garage walk ends on the promenade; no red error and no `The plaza is off` warning. Then Test > Device, a phone, portrait and landscape: walk to a free garage's post; the big green "Claim garage" button appears at the bottom center while the prompt shows, above the pop-ups, clear of the thumbstick and the jump button; tap it once: the garage is claimed exactly as the prompt would (the prompt and the button go away, the garage is yours). #44: in a second F5 (or Test > Clients and Servers, 2 players, so a garage stays free), stand between two free garages' posts so both prompts show: the button stays up, and moving toward one post makes the button press that one (the nearest); walk away from one post only: the button stays while the other prompt still shows. Open a window (SHOP): the button hides; close it: it is back only while a prompt shows. The plaza stays smooth on the phone (336 world parts, 4 lights).
7. **Revert the switch, don't retype it** (docs/STUDIO_SYNC_LOBBY.md 9 b, step 8): in View > Drafts, right-click `LobbyConfig` and revert the draft (without Team Create, paste `LobbyConfig.lua` from the batch's worktree at `2c3a415` over the whole script: a `main` with Batch 2 has `ClaimEnabled = true`). `LobbyConfig` is not in this batch's hash block, so open it and read `ClaimEnabled = false` by eye before saving.

### 7. Saving

Delete every preview or check object the batch made. Run the hash block (section 4) again: `ALL OK`. **File > Save to Roblox.** Write "Run on <date>: <result>" below.

Run on 2026-10-18 (written down by the owner session, docs/OVERHAUL_PLAN.md A1): the hash check of every script in Studio found the nine scripts of this batch in place, `ClaimEnabled = true` and the SpawnLocation on the plaza, so the batch had been run before the owner's playtest of 2026-10-18 (claim on, 2 players). Its playtests 1 to 7 were not written down as done or skipped; the owner session's own 1-player playtest (Batch 3) covers 1, 2 and 6 in part. Not run: the Test > Device steps and the 2-player step of 6.

## Batch 2 (the claim on: `LobbyConfig` only, the owner's request of 2026-10-18)

Opened 2026-10-18 by the quality lane, for the owner's written OK in docs/lanes/owner.md ("quality: turn the claim on", owner decision 9 revised). **Run Batch 1 first** (in the same session is fine): Batch 2 assumes Batch 1's nine scripts are in Studio, its playtests done and `LobbyConfig` reverted to `ClaimEnabled = false` (Batch 1, section 6, step 7: if you paste it, paste it from `git show 2c3a415:LobbyConfig.lua`, not from a later `main`, which has `true`). Run this batch at the `main` commit that merges PR `quality-claim-on`, or any later `main` whose `LobbyConfig.lua` still matches (the hash block says).

**What the owner sees after this batch:** players no longer land in a garage. They spawn on the plaza, with the banner "Walk to a free garage to start your company" and a green FREE marker over the nearest free garage; they walk to a garage and hold its "Claim garage" prompt (on a phone: the big green button). The six garages stand in the ring around the plaza (west, north, east), with the plaza's garden (#37). The save loads at the claim. Nothing else changes: no save change, no new remote, no other script.

**Not tested yet, said plainly:** playtest 9 (b) of docs/STUDIO_SYNC_LOBBY.md (the claim on with 2 and then 3 players) **has never been run**. Section 3 below is that test; until it passes, do not publish.

### 1. The list (paste)

| Script | Studio | State | sha256 | bytes |
|---|---|---|---|---|
| `LobbyConfig` | ModuleScript, ReplicatedStorage | changed | `c97ccf91a787f103ad4d3fcd766141510c84e9a7d579db67f4b34694befa1ffe` | 6327 |

The only change is `LobbyConfig.ClaimEnabled = true` and its comment (before: `3d8890c670d89f9829a469866f75d6aa9e765880168c81e6364271fe1725789e`, 6184 bytes, the file Studio has since the sync of 2026-10-17). TycoonCore, LobbyClient, ClaimButtonClient, WorldArt and WorldVisuals already read the switch; none of them changes.

Then **move the SpawnLocation** to the plaza (docs/STUDIO_SYNC_LOBBY.md section 7): Explorer > **Workspace > SpawnLocation**, Properties > **Position** `0, 0.5, 175` (size stays 12 x 1 x 12). Run that section's spawn check in the command bar: it must print `ON THE PLAZA (right for ClaimEnabled = true)`.

### 2. Hash check (command bar)

The same block as Batch 1's, with one `WANT` row. It must print `ALL OK: 1 scripts match the repo (batch 2)`. (Batch 1's block still prints `ALL OK: 9` after this batch: `LobbyConfig` is not in it.)

```lua
local K = {
	0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
	0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
	0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
	0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
	0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
	0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
	0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
	0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
}
local function sha256(msg)
	local h = { 0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19 }
	local len = #msg
	msg ..= "\128" .. string.rep("\0", (55 - len) % 64) .. string.pack(">I8", len * 8)
	local w = {}
	for chunk = 1, #msg, 64 do
		for i = 0, 15 do w[i] = string.unpack(">I4", msg, chunk + i * 4) end
		for i = 16, 63 do
			local a, b = w[i - 15], w[i - 2]
			local s0 = bit32.bxor(bit32.rrotate(a, 7), bit32.rrotate(a, 18), bit32.rshift(a, 3))
			local s1 = bit32.bxor(bit32.rrotate(b, 17), bit32.rrotate(b, 19), bit32.rshift(b, 10))
			w[i] = (w[i - 16] + s0 + w[i - 7] + s1) % 2 ^ 32
		end
		local a, b, c, d, e, f, g, hh = table.unpack(h)
		for i = 0, 63 do
			local S1 = bit32.bxor(bit32.rrotate(e, 6), bit32.rrotate(e, 11), bit32.rrotate(e, 25))
			local ch = bit32.bxor(bit32.band(e, f), bit32.band(bit32.bnot(e), g))
			local t1 = (hh + S1 + ch + K[i + 1] + w[i]) % 2 ^ 32
			local S0 = bit32.bxor(bit32.rrotate(a, 2), bit32.rrotate(a, 13), bit32.rrotate(a, 22))
			local maj = bit32.bxor(bit32.band(a, b), bit32.band(a, c), bit32.band(b, c))
			local t2 = (S0 + maj) % 2 ^ 32
			hh, g, f, e, d, c, b, a = g, f, e, (d + t1) % 2 ^ 32, c, b, a, (t1 + t2) % 2 ^ 32
		end
		local r = { a, b, c, d, e, f, g, hh }
		for i = 1, 8 do h[i] = (h[i] + r[i]) % 2 ^ 32 end
	end
	local out = {}
	for i = 1, 8 do out[i] = string.format("%08x", h[i]) end
	return table.concat(out)
end

-- STUDIO_SYNC_BATCH batch 2 hash check: LobbyConfig with ClaimEnabled = true. Changes nothing.
local function folderOf(place)
	if place == "StarterPlayerScripts" then
		return game:GetService("StarterPlayer"):FindFirstChild("StarterPlayerScripts")
	end
	return game:GetService(place)
end
local WANT = {
	-- main with PR quality-claim-on (2026-10-18): { "Name", "Class", "Place", "sha256", bytes }
	{ "LobbyConfig", "ModuleScript", "ReplicatedStorage", "c97ccf91a787f103ad4d3fcd766141510c84e9a7d579db67f4b34694befa1ffe", 6327 },
}
local problems = {}
for _, w in ipairs(WANT) do
	local name, class, place, hash, bytes = w[1], w[2], w[3], w[4], w[5]
	local folder = folderOf(place)
	local script = folder and folder:FindFirstChild(name)
	local result
	if not script then
		result = "MISSING (create a " .. class .. " in " .. place .. ")"
	elseif script.ClassName ~= class then
		result = "WRONG CLASS (it is a " .. script.ClassName .. ", it must be a " .. class .. ")"
	else
		local source = script.Source
		local function matches(text)
			return #text == bytes and sha256(text) == hash
		end
		-- the file as it is, or with its last newline dropped by Studio, or with one newline added by Studio
		local ok = matches(source) or matches(source .. "\n") or (string.sub(source, -2) == "\n\n" and matches(string.sub(source, 1, -2)))
		result = (ok and "OK" or "DIFFERENT") .. " " .. #source .. " bytes"
	end
	print(name, result)
	if string.sub(result, 1, 2) ~= "OK" then
		table.insert(problems, name)
	end
end
print(#problems == 0 and ("ALL OK: " .. #WANT .. " scripts match the repo (batch 2)") or ("NOT YET: fix " .. table.concat(problems, ", ")))
```

### 3. Playtests (Test > Local Server, 2 players)

Each written down as done, skipped or failed. **Test > Clients and Servers** (Local Server), **2** players, Start:

1. **Both players spawn on the plaza**, never inside a garage. Each sees the banner and a green "▼ FREE" marker over the nearest free garage's claim post. No red error and no `Infinite yield` warning in the server's or either client's Output; no `The plaza is off` warning.
2. **Each player gets a prompt:** player 1 walks to a garage's claim post: "Claim garage" shows. Player 2 at another garage: it shows there too.
3. **Each claims a different garage:** player 1 holds it (0.5 s): "Moving in...", then their name; the banner goes; the save loads (Cash, upgrades). Player 2 walks to player 1's garage: no prompt (a taken garage has none). Player 2 claims another one. The shop's Robux buttons said "Claim garage" before the claim and show prices after.
4. **The phone button shows:** in one client, Test > Device, a phone (portrait, then landscape), with that player still without a garage (or in a new Local Server): walk to a free post: the big green "Claim garage" button shows at the bottom center, clear of the thumbstick and the jump button; tap it once: the garage is claimed as with the prompt.
5. **One player leaves and the garage frees up:** close player 1's window: their garage shows "Closing..." while the leave save runs, then the Free room, the FREE sign and the prompt come back; player 2 (or a new player) can claim it.
6. **Then 3 players** (docs/STUDIO_SYNC_LOBBY.md 9 b, step 5): a third joins while a garage is closing; everyone gets a garage; the garages face the plaza. Walk the doorway of a west, a north and an east garage with Debug > "Building: next stage".

### 4. Saving

Commit the `LobbyConfig` draft (Team Create: View > Drafts); this time it **is** saved with `ClaimEnabled = true`. Run the spawn check (`ON THE PLAZA`) and the hash block (`ALL OK: 1`) again. **File > Save to Roblox.** Never Publish in this session: publishing with **Shut down all servers** (old servers keep the old flow until they restart, docs/PUBLISH_RULES.md, and Max Players stays 6) is the owner's separate decision after these playtests. To turn the claim off again: docs/STUDIO_SYNC_LOBBY.md section 10, step 4 (`false`, and the SpawnLocation back to (-1, 0.5, -1)).

Run on 2026-10-18 (written down by the owner session): `LobbyConfig` with `ClaimEnabled = true` was in Studio and the SpawnLocation at (0, 0.5, 175) before the owner's 2-player playtest of 2026-10-18 (claim on; the owner's feedback is docs/OVERHAUL_PLAN.md section 1). Playtest 3 (2 players) was played by the owner, not written down step by step; step 6 (3 players) not run.

## Batch 3 (overhaul phase 1: FREE hidden after the claim, the facade sign, the plaza's collision, the four scripts of PRs #51 to #53; branch `overhaul-phase1`)

Opened 2026-10-18 by the owner session (docs/OVERHAUL_PLAN.md phase 1). **The owner session pushes every script through the Studio MCP itself** and runs the hash block; this batch is the record of it, and what to check by hand.

**What the owner sees after this batch:** (1) after claiming a garage, the other garages' FREE signs, green lamps and "Claim garage" prompts are gone for that player (a player still on the plaza sees them as before); (2) every garage has a sign over its door with text: FREE and "Claim this garage" on a free one, "<Name>'s Startup" and the stage's name ("Garage", "Small Office", ...) on a taken one, "Moving in..." / "Closing..." while a save runs; the growth-chart bars moved to the board's left; (3) trees, lamp posts, benches, planters, the number signs' posts, the fountain and the arch's posts are solid on the plaza (bushes and hedges still are not); (4) the Day 1 gift opens at the first pause and the Goals card draws only the goals the server shows (PRs #51 to #53, pasted at last); (5) `Clouds` moved from `Lighting.Sky` to `Workspace.Terrain` (a Studio object: no more "Cloud instance must exist under Terrain" in the Output). No save change, no new remote, no publish.

| Script | Studio | State | sha256 (`overhaul-phase1`) | bytes |
|---|---|---|---|---|
| `TycoonCore` | Script, ServerScriptService | changed | `a9f0e78ef3108ba2d150a77adc79145612ae388fefef849c9c724580ef330d1b` | 54986 |
| `LobbyClient` | LocalScript, StarterPlayer > StarterPlayerScripts | changed | `52af70d7d377fe9a382a9bbf273fa99547bca92fecc09ed09ecaddc4cfced48e` | 6262 |
| `LobbyConfig` | ModuleScript, ReplicatedStorage | changed | `f626f3845e1db493983f86cdb41463546a705c88389aa1d191a36ecaf875c669` | 6429 |
| `PlotBuilding` | ModuleScript, ServerScriptService | changed | `cb93ae6588f05e4aad4086effa9ae48e2cea287c7f797560d4ed375a575c526d` | 44040 |
| `PlotBuildingVisuals` | ModuleScript, ServerScriptService | changed | `ef06d4f6d6e6da486a476cb6ba7793594889bca8f81b6f3a320c75d6ba782d8f` | 29591 |
| `WorldArt` | ModuleScript, ServerScriptService | changed | `0ce4baa6c69e4d50c5f72da819b5aa935c8971c8f1abb03379c108f98fbf4a33` | 19117 |
| `WorldVisuals` | ModuleScript, ServerScriptService | changed | `b769a59be882252ba39eb6281a1f069de454bc857cf9f77668050ba51e06fb7e` | 64360 |
| `DailyConfig` | ModuleScript, ReplicatedStorage | changed (PR #52, never pasted) | `9a7a6820182ab984e36a153e983833b991d2f4a90c1d8088dea15d982a1a8693` | 7290 |
| `DailyServer` | ModuleScript, ServerScriptService | changed (PRs #51, #52, never pasted) | `3527123c3f33bc7f4b43cd89cddd9d9eb08aa3fc026d3a7a99ebad1e308e1ba1` | 17574 |
| `OnboardingClient` | LocalScript, StarterPlayer > StarterPlayerScripts | changed (PR #53, never pasted) | `7c69d99f8c2c02667100c0538b238250e7f6a71c0713cdb090dfc7862cdffdb5` | 14691 |
| `OnboardingServer` | ModuleScript, ServerScriptService | changed (PR #51, never pasted) | `e6ae15bcb7d7b7a6f89ae22102ffab04fb695e31ea548a4e08a7c81bcb58b5af` | 17546 |

The hash block is Batch 1's with these eleven `WANT` rows (`{ "Name", "Class", "Place", "sha256", bytes }` from the table); it must print `ALL OK: 11 scripts match the repo`. Studio objects: `Lighting.Sky.Clouds` moved to `Workspace.Terrain` (done by the owner session through the MCP); **Max Players = 6** is still to set by hand (File > Game Settings > Places > Max Players; and in Creator Hub).

Playtests (each written down as done, skipped or failed): (a) 1 player, F5: spawn on the plaza, every free garage's sign reads "FREE / Claim this garage"; walk into a tree, a lamp, a bench: you stop; walk across every path and spoke: nothing blocks you; claim a garage: the other FREE signs, lamps and prompts disappear, your sign reads "<Name>'s Startup / Garage"; Debug > "Building: next stage": the sign's second line follows ("Small Office", ...). (b) 2 players (Test > Clients and Servers): player 2 still sees the FREE signs of the free garages after player 1's claim, and not player 1's; player 1 leaves: the sign says "Closing...", then "FREE / Claim this garage". (c) Test > Device, a phone: the sign reads on the facade from the walk.

Run on: (see the pull request of `overhaul-phase1`)

## Batch 4 (overhaul phase 2: the occlusion fade, the ceiling light, the stage-up look and toast; branch `overhaul-phase2`, on top of Batch 3)

Opened 2026-10-18 by the owner session (docs/OVERHAUL_PLAN.md phase 2). Pushed through the Studio MCP by the owner session; this batch is the record.

**What the owner sees after this batch:** (1) inside a garage the building is there: walls, the ceiling with its light, the door and the windows around you; only the shell parts between the camera and your character turn see-through (0.8), and come back when they are not in the way; from outside the building is solid and never "blinks" as someone walks up to it; (2) every building has one PointLight under its ceiling (warm in the Garage, white in the offices, cool in the tower, gold-white in the headquarters); (3) when your garage reaches a new funding round, a pop-up says what happened ("🌱 Seed reached! Your Garage becomes a Small Office"), the camera flies to a spot in front of the new facade for about 2.6 seconds and comes back (a tap or key skips it; never while a window is open; never after an IPO), with a short built-in sound. No save change, no new remote, no publish.

| Script | Studio | State | sha256 (`overhaul-phase2`) | bytes |
|---|---|---|---|---|
| `BuildingClient` | LocalScript, StarterPlayer > StarterPlayerScripts | changed (rewritten) | `b0fdbd5ffa351781d575829cc4d17b097b852f01c37eb50d629fca8c9ffa8028` | 15055 |
| `TycoonCore` | Script, ServerScriptService | changed | `c7c52763a51814306e051c56ce1f658e1e03d67cd6e850f5430d9abd7d4120d1` | 56224 |
| `PlotBuilding` | ModuleScript, ServerScriptService | changed | `eae1b73e8ba1ae8a1a7a9d628a77dc1ebcc9d00a3e5be6531c7f68758af93a5f` | 44826 |
| `PlotBuildingVisuals` | ModuleScript, ServerScriptService | changed | `d168aa3080d43c9fe39197da60b1120a7da9be92829a18299f2989c3aca6a4dd` | 31817 |

The hash block is Batch 1's with these four `WANT` rows; it must print `ALL OK: 4 scripts match the repo`.

Playtests (each written down as done, skipped or failed): (a) 1 player, F5, claim a garage: inside, turn the camera around: the walls and the ceiling are there and only what sits between the camera and you goes see-through; walk out and look back: the facade is solid; Debug > "Building: next stage" with every window closed: the pop-up, the camera's look at the facade, the sound; with the Shop open: the pop-up only. (b) 2 players: the other player never sees your camera move, and sees your building swap. (c) Test > Device, a phone: the fade and the look are smooth; a tap skips the look.

Run on: (see the pull request of `overhaul-phase2`)

## Batch 5 (overhaul phase 3: the office grows with the team; branch `overhaul-phase3`, on top of Batch 4)

Opened 2026-10-18 by the owner session (docs/OVERHAUL_PLAN.md phase 3). Pushed through the Studio MCP by the owner session; this batch is the record.

**What the owner sees after this batch:** a room starts with no hire desk: one see-through "next hire" desk marks the first spot; every hire gets a desk at its spot (it pops in) and the see-through one moves to the next spot; a hire that leaves takes its desk away; a free garage shows only the see-through desk. Derived from the team (never saved). No save change, no new remote, no publish.

| Script | Studio | State | sha256 (`overhaul-phase3`) | bytes |
|---|---|---|---|---|
| `TycoonCore` | Script, ServerScriptService | changed | `ba09f0497bed05825b3b5ee74e4370c674174785014af0cd5197baea2e2319dc` | 56770 |
| `EmployeeServer` | ModuleScript, ServerScriptService | changed | `58c3094f755fba997a4c67de7ddd84148d016363391e7e54e380fc188c2788e8` | 32218 |
| `PlotVisuals` | ModuleScript, ServerScriptService | changed | `acd424a2881b219923916203fa95d3ac920899f8df59e47aa182426d5ac33945` | 44592 |

The hash block is Batch 1's with these three `WANT` rows; it must print `ALL OK: 3 scripts match the repo`.

Playtests: (a) 1 player, F5, claim: a free garage shows one see-through desk; your room shows a desk per hire you already have plus the see-through one; Debug > GiveCash, buy a Garage Egg, Debug > Skip egg timers, hatch: a desk pops in at the hire's spot and the see-through desk moves on; TEAM > fire one: its desk goes. (b) a stage change (Debug > Building: next stage) keeps the desks. (c) 2 players: each sees the other's desks grow.

Run on: (see the pull request of `overhaul-phase3`)

## Batch 6 (overhaul phase 4: the story and the goal chain; branch `overhaul-phase4`, on top of Batch 5)

Opened 2026-10-18 by the owner session (docs/OVERHAUL_PLAN.md phase 4). Pushed through the Studio MCP by the owner session; this batch is the record.

**What the owner sees after this batch:** on the plaza, a welcome card under the banner ("You're a founder with an idea and no money" and the story in four lines, "Got it"); the goal card follows the chain (upgrades, hires, the Server Rack, each funding round, the IPO: OnboardingConfig.Chain, ChainEnabled on); every goal that takes a row after the first one comes with a pop-up "New goal: <goal>" and a second line saying what it is for. No save change (the finished goals save as before), no new remote, no publish.

| Script | Studio | State | sha256 (`overhaul-phase4`) | bytes |
|---|---|---|---|---|
| `OnboardingConfig` | ModuleScript, ReplicatedStorage | changed | `e69c3243b8b329dcc8e29ba0400abadea852d2e1ae3da653b541adc09ac7ece0` | 8290 |
| `OnboardingServer` | ModuleScript, ServerScriptService | changed | `22792a3153c3e7ee47abb33648d345447bfdfe60996833a26c8260f0078a59ce` | 18619 |
| `LobbyClient` | LocalScript, StarterPlayerScripts | changed | `d79672179a20b765153b6f037bca8c7f329d30c1ce345707932a8172a16f1c9d` | 9091 |
| `LobbyConfig` | ModuleScript, ReplicatedStorage | changed | `ee96863715d265047b051f8a1c4734b66abe686c80c16b05f8a24841636fcf7c` | 6811 |

The hash block is Batch 1's with these four `WANT` rows; it must print `ALL OK: 4 scripts match the repo`.

Playtests: (a) 1 player, F5: on the plaza the welcome card shows under the banner; "Got it" hides it; claim a garage: the card is gone and the goal card shows the first two chain goals (in Studio "Answer 3 calls" and "Own 3 upgrades"; live, where calls don't run, "Own 3 upgrades" and "Hire 3 employees"). Debug > GiveCash, SHOP > Office, buy three upgrades: "Own 3 upgrades" finishes and a pop-up "New goal: Hire 3 employees / EGGS: every hire earns for you, even while you're away" shows, the card now lists it. (b) an old save (Debug > OnboardingMarkOld) shows no card and no pop-up, as before. (c) 2 players: each sees only their own card and pop-ups.

Run on: (see the pull request of `overhaul-phase4`)

## How the quality lane fills a batch

After a merge, on `main`, for each script the merged PR changed or created (its lane file's "Studio steps" says which): `sha256sum <Name>.lua` and `wc -c <Name>.lua` give the row and the `WANT` line (the hash is of the file's bytes as they are in the repo, LF line endings, trailing newline kept). A hash in the lane file that differs from `main`'s is the lane file's mistake: `main` wins, and the quality lane tells the lane in docs/lanes/quality.md. When the owner has run the batch and written "Run on", the next merge opens Batch 2 below this one; a batch is never rewritten after it was run.
