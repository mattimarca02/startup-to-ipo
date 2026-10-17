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

## Batch 1 (open: #38, #35, #36 merged; #37, #40, #43 still open)

Opened 2026-10-17 by the quality lane. **Merged so far** (the hashes below are from `main` at `57ef19a`, 2026-10-17 22:45 UTC): PR #38 (gameplay: `tools/lobby_test.py` only, nothing for Studio), PR #35 (ux: `ClaimButtonClient`, new) and PR #36 (building: `PlotBuilding` and `PlotBuildingVisuals`, changed). The rows marked **open** are what the still-open PRs will bring, with the SHA-256 their lane files give for the PR heads (checked by the quality lane; provisional until merged: the quality lane rewrites the row and the hash block from `main` after each merge). **Never paste a row that says open.**

| PR | Lane | Script | Class, place | State | SHA-256 | Bytes | Merged? |
|---|---|---|---|---|---|---|---|
| #38 | gameplay | (none: `tools/lobby_test.py` only) | | | | | merged |
| #35 | ux | `ClaimButtonClient` | LocalScript, StarterPlayer > StarterPlayerScripts | new | `494d14bdd2843e49606a7a339793e9b4c7840ea0cc08f967f5f7c3863bed2b00` | 7525 | merged |
| #36 | building | `PlotBuilding` | ModuleScript, ServerScriptService | changed | `f04e3b89486a4b8a3656633029412c1e666df84432c9760639e89c9361ea5788` | 42603 | merged |
| #36 | building | `PlotBuildingVisuals` | ModuleScript, ServerScriptService | changed | `2e956d553b0b5bd3ef51bf8db4b643634b86cca83111bdbe9fa7fec8405e5043` | 27493 | merged |
| #37 | world | `WorldArt` | ModuleScript, ServerScriptService | changed | `7c24e992b60c6319f309dbd7dfda2cafa201566afece96ddc5678e9d87c57d8f` | 17648 | open |
| #37 | world | `WorldVisuals` | ModuleScript, ServerScriptService | changed | `3547afbbecd30e01f65285b1c483932da30751db9fa328119a267126c7563a90` | 59866 | open |
| #40 | interiors | `PlotArt` | ModuleScript, ServerScriptService | changed | `e1d3f7e0e6dd789c3d4a7135a474e8dc92eacdfb23d9c65fcc0599ea9dd2b0c6` | 63975 | open |
| #40 | interiors | `PlotVisuals` | ModuleScript, ServerScriptService | changed | `8eefee60866bb2ef0a31cbeda361e5f4bd145844d27644dd054e9e5951d8fcca` | 41197 | open |
| #43 | gameplay | `OnboardingServer` | ModuleScript, ServerScriptService | changed | (from `main` when merged) | | open |
| #43 | gameplay | `OnboardingConfig` | ModuleScript, ReplicatedStorage | changed | (from `main` when merged) | | open |

### 1. Before you start

The playtests 9 (a), (b) and (c) of docs/STUDIO_SYNC_LOBBY.md (the lobby-all sync of 2026-10-17 did everything but them). Do them before pasting anything new, so a problem is lobby-all's or the batch's, never a mix.

### 2. Scripts to create by hand first

| Name | Class | Parent | From PR |
|---|---|---|---|
| `ClaimButtonClient` | LocalScript | StarterPlayer > StarterPlayerScripts | #35 |

### 3. The list (paste in any order)

Paste each one the same way: open the `.lua` file on `main`, select all, copy; in Studio double-click the script, select all, paste (or write the file's text with the MCP's script tool). Team Create: commit the drafts before the hash block.

| Script | Class, place | State | SHA-256 | Bytes |
|---|---|---|---|---|
| `ClaimButtonClient` | LocalScript, StarterPlayerScripts | new | `494d14bdd2843e49606a7a339793e9b4c7840ea0cc08f967f5f7c3863bed2b00` | 7525 |
| `PlotBuilding` | ModuleScript, ServerScriptService | changed | `f04e3b89486a4b8a3656633029412c1e666df84432c9760639e89c9361ea5788` | 42603 |
| `PlotBuildingVisuals` | ModuleScript, ServerScriptService | changed | `2e956d553b0b5bd3ef51bf8db4b643634b86cca83111bdbe9fa7fec8405e5043` | 27493 |

Nothing else changes in Studio for these three PRs: no new remote, no new object besides the LocalScript, no config change (`LobbyConfig.ClaimEnabled` stays `false`).

### 4. Hash check (command bar)

Paste the whole block into **View > Command Bar** and press Enter (with the MCP: `execute_luau`). It changes nothing. It prints `OK`, `DIFFERENT`, `MISSING` or `WRONG CLASS` per script, then `ALL OK` or `NOT YET`. Studio may drop the file's last newline or add one; both are accepted. The `WANT` table is the batch's list (section 3): the quality lane fills it from `main` after each merge, one row per script, `{ name, class, place, sha256, bytes }`. Today it checks the three scripts of #35 and #36 and prints `ALL OK: 3 scripts match the repo (batch 1)`.

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
	{ "ClaimButtonClient", "LocalScript", "StarterPlayerScripts", "494d14bdd2843e49606a7a339793e9b4c7840ea0cc08f967f5f7c3863bed2b00", 7525 },
	{ "PlotBuilding", "ModuleScript", "ServerScriptService", "f04e3b89486a4b8a3656633029412c1e666df84432c9760639e89c9361ea5788", 42603 },
	{ "PlotBuildingVisuals", "ModuleScript", "ServerScriptService", "2e956d553b0b5bd3ef51bf8db4b643634b86cca83111bdbe9fa7fec8405e5043", 27493 },
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

1. **The kit is still right (#36 changes nothing in it):** the KitModels check of docs/STUDIO_SYNC_LOBBY.md section 5, pasted as it is, must still print `KIT OK: 36 models` (it reads `PlotBuilding.KitManifest`, which #36 did not change; the Blocks never look in the kit).
2. **Nothing new in the Output at start:** after the paste, press F5 once and stop: no red error, and no new warning that starts with `Plot buildings:` (one such warning only if KitModels is missing or a model is wrong, as before).

Expected from the open PRs, each a step once its PR is merged: #37, nothing (the garden is drawn only with the claim on); #40, the command-bar preview in docs/lanes/interiors.md ("Studio steps"): stage 1 prints `OK` with 39 kit MeshParts, then delete `Workspace.PREVIEW_STAGES`; #43, nothing (`ChainEnabled` is off, the tracker is unchanged).

### 6. Playtests

**(a) #36, the Garage's roof and sign (claim off, as it ships).** F5. Your garage's building (a new save: the Garage) has a rusty pitched roof between brick gables stepped front and back, a ridge cap, gutters and four downpipes, a dark sign board with an orange growth-chart emblem over the roll-up door (no text), two front windows with sills and a concrete plinth. Walk in through the door: the whole shell fades, roof and sign included, and the camera never pulls in; walk out: it comes back. Open the shop's Debug tab, press "Building: next stage" through the five stages and back: only the Garage has the roof; the other four are as before. No new warning in the Output.

**(b) #35, the claim button (nothing with the claim off).** F5 with the claim off: nothing new shows anywhere, and the Output has no error. Then, **in Studio only, never saved:** set `ReplicatedStorage > LobbyConfig` `ClaimEnabled = true` (docs/STUDIO_SYNC_LOBBY.md section 9 b says how, and how to undo it), **Test > Device**, a phone in portrait and then in landscape: on the plaza, walk to a free garage's claim post; when Roblox shows its "Claim garage" prompt, a big green button "Claim garage / Garage N" sits at the bottom of the screen (portrait: centered above the thumbstick; landscape: between the thumbstick and the jump button), clear of the thumbstick and the jump button. Tap it: it says "Claiming..." for half a second, then the garage is yours and the button is gone. Walk away from a post before tapping: the button hides with the prompt. Open the shop while the button shows: it hides, and comes back when the shop closes. Afterwards **revert `LobbyConfig`** (View > Drafts, discard; or paste `LobbyConfig.lua` again) and check it reads `ClaimEnabled = false`.

**(c) Phone sizes, claim off.** Test > Device with a phone: the HUD, the valuation bar and the shop as before; the Garage's roof reads well from the plaza side.

Expected from the open PRs, once merged: #37 (claim on in Studio only: the paved square, four spokes, the promenade, the lawn beds, the fountain, benches and lamps; no red error and no `World` warning; Test > Device; revert `LobbyConfig`); #40 (F5: kit crates as hire desks, the old desk and chair with the PC, the workbench, the crates in the back-right corner, the glowing bulb; no `Plot visuals:` warning); #43 (F5: the Goals card is exactly as before, two goals, because `ChainEnabled` is off).

### 7. Saving

Delete every preview or check object the batch made. `LobbyConfig` is the repo's file (`ClaimEnabled = false`) and every draft is committed. Run the hash block (section 4) again: `ALL OK: 3 scripts`. **File > Save to Roblox.** Write "Run on <date>: <result>" below.

Run on: (not yet)

## How the quality lane fills a batch

After a merge, on `main`, for each script the merged PR changed or created (its lane file's "Studio steps" says which): `sha256sum <Name>.lua` and `wc -c <Name>.lua` give the row and the `WANT` line (the hash is of the file's bytes as they are in the repo, LF line endings, trailing newline kept). A hash in the lane file that differs from `main`'s is the lane file's mistake: `main` wins, and the quality lane tells the lane in docs/lanes/quality.md. When the owner has run the batch and written "Run on", the next merge opens Batch 2 below this one; a batch is never rewritten after it was run.
