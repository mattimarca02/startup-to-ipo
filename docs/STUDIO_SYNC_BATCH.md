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

Opened 2026-10-17 by the quality lane. **Merged so far, in this order:** #38 (gameplay, `tools/lobby_test.py` only: nothing for Studio), #36 (building: the Garage's roof and sign), #35 (ux: the phone's "Claim garage" button), #41 (quality: this doc, README, CLAUDE.md, ROADMAP: nothing for Studio), #37 (world: the ring plaza garden), #43 (gameplay: the goal chain, off), #45 (quality: docs only), #40 (interiors: the rooms' furniture from the 3D kit), #46 (quality: docs only), #47 (quality: docs only), #44 (ux: the claim button names and presses the nearest prompt; it replaces #35's `ClaimButtonClient` bytes) and #48 (ux: `tools/hud_test.py` and `tools/shop_ux_test.py` only: nothing for Studio). **No PR is open: this batch is final.** Every row below was recomputed from `main` by the quality lane (`sha256sum` and `wc -c` of the file; the five of 2026-10-17 at `853eaa3`, #43's two at `f666726` and #40's two at `cac89d9` on 2026-10-18, #44's `ClaimButtonClient` at `0fec09b`, all equal to the hashes the lane files give; on 2026-10-18 09:15 UTC all nine were recomputed again from `main` at `2c3a415`: unchanged but for `ClaimButtonClient`). Run the batch at `2c3a415` or any later `main` whose nine files still match (the hash block says).

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
| #48 | ux | (none: `tools/hud_test.py`, `tools/shop_ux_test.py` only) | | | | | merged 2026-10-18 09:18 UTC |

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

Nothing is expected later in this batch: no lane PR is open. The next merge with Studio steps opens Batch 2 once this one has been run.

### 6. Playtests

In this order, each written down as done, skipped or failed:

1. **#36, claim off (as Studio has it):** F5. Your garage (a new save: the Garage stage) shows the pitched roof between the stepped gables, the sign board over the roll-up door (an orange growth-chart emblem, no text), two front windows with sills, the plinth, gutters and downpipes. Walk in through the door: the whole shell fades, the roof included; walk out: it comes back. Reset inside and outside: never stuck. The other four stages (Debug > "Building: next stage", Studio only) look as before. No new warning in the Output.
2. **#40, claim off:** in the same F5, inside your Garage: kit crates stand as the hire desks, the old desk and chair with the PC, the workbench, crates in the back-right corner and the glowing bulb; walk the aisles (no kit piece blocks you: every kit part has collision off); Debug > "Building: next stage" shows the four other rooms unchanged. The Output has no `Plot visuals:` warning (one would name a kit model built from Parts instead).
3. **#43, claim off, a new save (Debug > "Restart tutorial" or a fresh test account):** the goal tracker looks and behaves as before: Hire 3 employees, then Reach Seed stage, one row each; finishing one shows its tick; no new row, no `OnboardingConfig` warning in the Output (`ChainEnabled` is false, so the chain is not in use).
4. **#35 and #44, claim off:** still in the same F5 (or a new one): nothing new shows on the screen, the HUD is as before, no error in the Output. Test > Device, a phone in portrait and landscape: still nothing new (the button needs the claim on).
5. **#37, claim off:** the row world is unchanged: the street, the lounge, the hills as before.
6. **Claim on, Studio only, never saved (#35, #44 and #37):** set `ClaimEnabled = true` in `ReplicatedStorage > LobbyConfig` for the playtest only (docs/STUDIO_SYNC_LOBBY.md section 9 b says how and how to revert). F5: the garages stand in the ring; the plaza shows the paved square around the spawn pad, four spokes, the promenade along the garages' fronts, four lawn beds with kerbs, trees and bushes, the fountain on the north spoke, benches and lamps along the spokes; every garage walk ends on the promenade; no red error and no `The plaza is off` warning. Then Test > Device, a phone, portrait and landscape: walk to a free garage's post; the big green "Claim garage" button appears at the bottom center while the prompt shows, above the pop-ups, clear of the thumbstick and the jump button; tap it once: the garage is claimed exactly as the prompt would (the prompt and the button go away, the garage is yours). #44: in a second F5 (or Test > Clients and Servers, 2 players, so a garage stays free), stand between two free garages' posts so both prompts show: the button stays up, and moving toward one post makes the button press that one (the nearest); walk away from one post only: the button stays while the other prompt still shows. Open a window (SHOP): the button hides; close it: it is back only while a prompt shows. The plaza stays smooth on the phone (336 world parts, 4 lights).
7. **Revert the switch, don't retype it** (docs/STUDIO_SYNC_LOBBY.md 9 b, step 8): in View > Drafts, right-click `LobbyConfig` and revert the draft (without Team Create, paste `LobbyConfig.lua` from the repo over the whole script). `LobbyConfig` is not in this batch's hash block, so open it and read `ClaimEnabled = false` by eye before saving.

### 7. Saving

Delete every preview or check object the batch made. Run the hash block (section 4) again: `ALL OK`. **File > Save to Roblox.** Write "Run on <date>: <result>" below.

Run on: (not yet)

## How the quality lane fills a batch

After a merge, on `main`, for each script the merged PR changed or created (its lane file's "Studio steps" says which): `sha256sum <Name>.lua` and `wc -c <Name>.lua` give the row and the `WANT` line (the hash is of the file's bytes as they are in the repo, LF line endings, trailing newline kept). A hash in the lane file that differs from `main`'s is the lane file's mistake: `main` wins, and the quality lane tells the lane in docs/lanes/quality.md. When the owner has run the batch and written "Run on", the next merge opens Batch 2 below this one; a batch is never rewritten after it was run.
