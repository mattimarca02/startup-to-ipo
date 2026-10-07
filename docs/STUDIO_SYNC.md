# Studio sync: everything that exists only in Studio, now on GitHub

Written at the end of the plot visuals stages 2-5 work (branch `visuals-garage`). Last code commit: `21976f9` (nothing in a `.lua` file changed after it; only docs). Nothing here touches Roblox: it is the list of what the Mac has to do.

**Addendum (e), 2026-10-05, branch `task-needs-desk`:** customer calls now start when the player owns the Desk. Three scripts changed (`TaskConfig`, `TaskServer`, `TaskClient`); their hashes are in section (e) (at the end of this file) and in the hash block below. Section (d) belongs to `customize-pr1`.

## (a) Scripts that differ from `main`

SHA-256 and size in bytes of each `.lua` file as it is in the repo at the last code commit. `PlotArt` and `PlotVisuals` are **new** scripts (create them, they don't exist in Studio yet); the others are changed. Every other script is identical to `main`.

| Script | Studio type and place | State | sha256 | Bytes |
|---|---|---|---|---|
| `TycoonCore` | Script, ServerScriptService | changed | `77ce9c43dcbd03ae5e03e5e112c99b3763af7b92e6527a367e3eeee112e61aa9` | 34330 |
| `ShopServer` | ModuleScript, ServerScriptService | changed | `97e6ec51c10df789d1b0bf2620908e81c1bc883ace6aa71762062139f06fa27d` | 32803 |
| `PoachServer` | ModuleScript, ServerScriptService | changed | `bfb9808f82f0545b9915d07b5c2dc1a5fc43711271c0e24bbbf43fb4d8f5fb01` | 36418 |
| `IpoServer` | ModuleScript, ServerScriptService | changed | `96e8f073d2039dd1201cbc23137b5730cc8783644bc0085cdd5e7cd3a29e2e52` | 17377 |
| `OnboardingServer` | ModuleScript, ServerScriptService | changed | `8ba5226541b9fe6d01d488a31b81aa21e207a014174541ece942ac3f38e5a05a` | 14662 |
| `EmployeeServer` | ModuleScript, ServerScriptService | changed | `65fefebf56b21d85c87e773a9dc8734754c716e29d693cb1fd15b79381894597` | 31745 |
| `PlotArt` | ModuleScript, ServerScriptService | new | `b2a08432fdecfd3ae624d9c938de191348f03877e772562341a4eb94a7f7b0c2` | 60671 |
| `PlotVisuals` | ModuleScript, ServerScriptService | new | `2e10736f60b86590f0bced98eb3d8d0e9b0264108cdc9cd02f68dd8b5651ba89` | 26508 |
| `ShopClient` | LocalScript, StarterPlayer > StarterPlayerScripts | changed | `41c98119430b29b501160ddd42485fc5316e779a5e380f1efe429fd6e98aae11` | 28371 |
| `PoachClient` | LocalScript, StarterPlayer > StarterPlayerScripts | changed | `6c32b7fbb9e00ca9d8a3cad5371148a939c6bc0c27ecf5069dea6ab0791f2230` | 39678 |

The files use `\n` line endings and end with one newline. Studio may add or drop that final newline, so the check below prints both hashes.

## (b) Studio-only settings (not in any script, not in the repo until now)

These live only in the Team Create place. The values come from the visuals-garage owner's notes, and the ColorCorrection values were read from Studio by the owner's sync session; the repo and the ROADMAP had no earlier record of them (searched for ClockTime, ColorCorrection, Atmosphere, Bloom and Baseplate).

| Where | Property | Before | Now |
|---|---|---|---|
| Lighting | `ClockTime` | 14.5 | **14** |
| Lighting | a `ColorCorrection` object | none | **added**, `Enabled` true, `Brightness` 0.03, `Contrast` 0.08, `Saturation` 0.15, `TintColor` 255, 246, 232 (RGB; read from Studio by the owner's sync session) |
| Lighting > Atmosphere | `Haze` | 0 | **1.2** |
| Lighting > Atmosphere | `Glare` | 0 | **0.3** |
| Lighting > Bloom | `Intensity` | 1 | **0.6** |
| Lighting > Bloom | `Size` | 24 | **32** |
| Lighting > Bloom | `Threshold` | 2 | **1.6** |
| Workspace > Baseplate | `Color` | gray (91, 91, 91) | **grass (108, 172, 82)**, and the grid `Texture` removed |

Also Studio-only: `Workspace.PREVIEW_STAGES` (the preview rooms at x = -600). It is **not part of the game**: rebuild it only to look at the rooms, and delete it before publishing (ROADMAP, before-publish item m).

## (c) Steps on the Mac

1. **Pull.** In a terminal in the project folder: `git checkout visuals-garage`, then `git pull origin visuals-garage`. Check `git log --oneline -1` shows the newest commit of this branch.
2. **Set the Source of each changed script from the repo,** in this order (server scripts first, then the clients, as docs/PUBLISH_RULES.md 2c says). For each name in the table: open the `.lua` file, select all, copy; in Studio double-click the script of that name, select all, paste.
   - First **create** the two new ModuleScripts in **ServerScriptService** and name them exactly `PlotArt` and `PlotVisuals`, then paste `PlotArt` and `PlotVisuals`. Create them *before* pasting `TycoonCore` (it waits for them for a few seconds, inside `pcall`, so it never hangs, but the rooms won't build otherwise).
   - Then paste `TycoonCore`, `ShopServer`, `PoachServer`, `IpoServer`, `OnboardingServer`, `EmployeeServer`.
   - Last, the clients in StarterPlayerScripts: `ShopClient`, `PoachClient`.
   - Before Publish: **View > Drafts**, commit every draft (an uncommitted draft is not published).
3. **Verify the hashes.** Paste the block below into Studio's **command bar** (View > Command Bar) and press Enter. Every line must say `OK`. A line that says `DIFFERENT` names the script to paste again. (It computes SHA-256 in Luau; it was checked against `sha256sum` on the real files.)
4. **Rebuild `Workspace.PREVIEW_STAGES`** (only to look at the five rooms; one room per stage, each with its six props and a check): paste the second block into the command bar. It prints `Stage n OK` or the first problem for each stage. Look at them at the default camera and with Test > Device at phone size.
5. **Delete `Workspace.PREVIEW_STAGES` before publishing** (select it in the Explorer and press Delete). Then publish with **Shut down all servers** (docs/PUBLISH_RULES.md).

### Hash check (command bar)

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

local SSS = game:GetService("ServerScriptService")
local SPS = game:GetService("StarterPlayer"):WaitForChild("StarterPlayerScripts")
local RS = game:GetService("ReplicatedStorage")
local WANT = {
	TycoonCore = { "77ce9c43dcbd03ae5e03e5e112c99b3763af7b92e6527a367e3eeee112e61aa9", 34330 },
	ShopServer = { "97e6ec51c10df789d1b0bf2620908e81c1bc883ace6aa71762062139f06fa27d", 32803 },
	PoachServer = { "bfb9808f82f0545b9915d07b5c2dc1a5fc43711271c0e24bbbf43fb4d8f5fb01", 36418 },
	IpoServer = { "96e8f073d2039dd1201cbc23137b5730cc8783644bc0085cdd5e7cd3a29e2e52", 17377 },
	OnboardingServer = { "8ba5226541b9fe6d01d488a31b81aa21e207a014174541ece942ac3f38e5a05a", 14662 },
	EmployeeServer = { "65fefebf56b21d85c87e773a9dc8734754c716e29d693cb1fd15b79381894597", 31745 },
	PlotArt = { "b2a08432fdecfd3ae624d9c938de191348f03877e772562341a4eb94a7f7b0c2", 60671 },
	PlotVisuals = { "2e10736f60b86590f0bced98eb3d8d0e9b0264108cdc9cd02f68dd8b5651ba89", 26508 },
	ShopClient = { "41c98119430b29b501160ddd42485fc5316e779a5e380f1efe429fd6e98aae11", 28371 },
	PoachClient = { "6c32b7fbb9e00ca9d8a3cad5371148a939c6bc0c27ecf5069dea6ab0791f2230", 39678 },
	TaskConfig = { "a6ec3663f95bb23c87683416ad7ee2dbee5da2fcde3d28d97eb2f5600590fe06", 14607 },
	TaskServer = { "11fe77211926581d9d50e049e78cbabaff1086794d07b64a94d13bf6fef8fc99", 35513 },
	TaskClient = { "75ac0721e1d603222c7fa1f2efb31724210a500e7615066826d8d33a1c321807", 18079 },
}
for name, want in pairs(WANT) do
	local script = SSS:FindFirstChild(name) or SPS:FindFirstChild(name) or RS:FindFirstChild(name)
	if not script then
		print(name, "MISSING (create it)")
	else
		local source = script.Source
		local same = sha256(source) == want[1] and #source == want[2]
		local withNewline = sha256(source .. "\n") == want[1] and #source + 1 == want[2]
		print(name, (same or withNewline) and "OK" or "DIFFERENT", #source, "bytes")
	end
end
```

### Rebuild the preview (command bar)

```lua
local SSS = game:GetService("ServerScriptService")
local PlotArt = require(SSS.PlotArt)
local PlotVisuals = require(SSS.PlotVisuals)
local old = workspace:FindFirstChild("PREVIEW_STAGES")
if old then old:Destroy() end
local folder = Instance.new("Folder")
folder.Name = "PREVIEW_STAGES"
folder.Parent = workspace
for stage = 1, #PlotArt.Stages do
	local center = Vector3.new(-600 + (stage - 1) * 70, 0.5, 150)
	local floor = Instance.new("Part")
	floor.Name = "Floor"
	floor.Anchored = true
	floor.Size = Vector3.new(60, 1, 60)
	floor.Position = center
	floor.Parent = folder
	PlotVisuals.styleFloor(floor, PlotArt, stage)
	local room = PlotVisuals.buildRoom(folder, center, PlotArt, stage)
	for _, slot in ipairs(PlotArt.Layout.itemSlots) do
		PlotVisuals.buildProp(room.UpgradeProps, center, PlotArt, slot.name, Vector3.new(slot.x, 0, slot.z))
	end
	local problems = PlotVisuals.check(room, center, PlotArt)
	print("Stage", stage, #problems == 0 and "OK" or problems[1])
end
```

## (d) Addendum: customize PR 1 (branch `customize-pr1`, the `pokedex` save section)

Nothing here touches Roblox: it is the list of what the Mac has to do. **Three new scripts and one changed one.** Every other script is identical to `main`. The `TycoonCore` row here **replaces** the `TycoonCore` row in (a) (that one is the visuals-garage version, already on `main`). **Third review fix (branch `customize-pr1-fix-c`): only `CompanyConfig` changed again** (it tidies `card.owned` and the placed-item lists on load; its hash and size below are new; `SectorConfig`, `CompanyServer` and `TycoonCore` are byte for byte the ones below, so if you already pasted the second-fix version, paste only `CompanyConfig` again, and the hash block says `DIFFERENT` for it otherwise). The rest of this paragraph is how the second review fix (branch `customize-pr1-fix-b`, pushed to `customize-pr1`) differed from the first: since the first review fix `CompanyConfig` changed (`card.owned` keeps the keys outside its list) and `TycoonCore` changed by comments only (the `SAVEFN` and `COMMITIPO` markers the tests read); `CompanyServer` and `SectorConfig` are the same as before. The steps are the same (same scripts, same order, nothing new to create), but if you already pasted the previous version, paste `CompanyConfig` and `TycoonCore` again (the hash block says `DIFFERENT` for them otherwise); only docs and tests changed besides those two.

| Script | Studio type and place | State | sha256 | Bytes |
|---|---|---|---|---|
| `SectorConfig` | ModuleScript, **ReplicatedStorage** | **new** | `60629dc4d4368652a4235ba2b6ccb5499836361110c6e7331f7ae46730a0ee6b` | 3194 |
| `CompanyConfig` | ModuleScript, **ReplicatedStorage** | **new** | `bc8745926f2a0c89eaab7881211ffe0618f3171c42947527db69cfb550f1ff7c` | 41284 |
| `CompanyServer` | ModuleScript, **ServerScriptService** | **new** | `826dfba8fac00bee190fd62265024be1c1e4c43d41f4c84d5cf462e20a500a10` | 8268 |
| `TycoonCore` | Script, ServerScriptService | changed | `9607262c64d762cc15644a8ab3d85821cfaba2654879a9018210e1237679def2` | 36399 |

The Studio MCP cannot create scripts inside services, so the three new ones are made **by hand** (names are exact, capital letters included).

### Steps on the Mac (in this order)

1. **Pull.** In a terminal in the project folder: `git fetch`, `git checkout customize-pr1`, `git pull`. Check `git log --oneline -1` shows the newest commit of this branch.
2. **Create the three ModuleScripts first.** In Studio's Explorer: hover **ReplicatedStorage**, click **+**, choose **ModuleScript**, press F2 and name it exactly `SectorConfig`. Do the same for `CompanyConfig` in **ReplicatedStorage**, and then for `CompanyServer` in **ServerScriptService**.
3. **Paste the sources, in this order:** `SectorConfig.lua` into `SectorConfig`, then `CompanyConfig.lua` into `CompanyConfig`, then `CompanyServer.lua` into `CompanyServer` (open the `.lua` file, select all, copy; in Studio double-click the script, select all, paste). `CompanyConfig` waits for `SectorConfig` and `IpoConfig`, and `CompanyServer` waits for `CompanyConfig`, all with no time limit: so a missing one hangs the server script.
4. **Only then paste `TycoonCore.lua`** into the existing `TycoonCore` Script (ServerScriptService). `TycoonCore` requires `CompanyServer` the same way.
5. **Verify the hashes.** Open the **command bar** (View > Command Bar), paste the first part of the block in (c) step 3 above (the `K` table and the `sha256` function, down to the closing `end` of `sha256`), then paste the block below after it and press Enter. Every line must say `OK`.
6. **Playtest (F5)**, read the Output: no red errors; no "Could not set up", no warnings from `pokedex`. Join, leave and rejoin. Check that nothing looks or plays differently. The Output must **not** say "Keeping a part of ... save this version doesn't know: pokedex" (it is a known section now).
7. Before merging `customize-pr1` (not before pasting): run the DataStore test block of docs/CUSTOMIZE_PR1_NOTES.md in the command bar (it uses a throwaway store and removes its keys) and read its result table; it settles whether `SetAsync` really refuses mixed and holed tables. It was never run in Studio. The Studio steps above are otherwise unchanged by the third fix.
8. Before Publish: **View > Drafts**, commit every draft. Publish with **Shut down all servers** (docs/PUBLISH_RULES.md 2d), never Migrate.

```lua
local SSS = game:GetService("ServerScriptService")
local RS = game:GetService("ReplicatedStorage")
local WANT = {
	SectorConfig = { RS, "60629dc4d4368652a4235ba2b6ccb5499836361110c6e7331f7ae46730a0ee6b", 3194 },
	CompanyConfig = { RS, "bc8745926f2a0c89eaab7881211ffe0618f3171c42947527db69cfb550f1ff7c", 41284 },
	CompanyServer = { SSS, "826dfba8fac00bee190fd62265024be1c1e4c43d41f4c84d5cf462e20a500a10", 8268 },
	TycoonCore = { SSS, "9607262c64d762cc15644a8ab3d85821cfaba2654879a9018210e1237679def2", 36399 },
}
for name, want in pairs(WANT) do
	local script = want[1]:FindFirstChild(name)
	if not script then
		print(name, "MISSING (create it)")
	else
		local source = script.Source
		local same = sha256(source) == want[2] and #source == want[3]
		local withNewline = sha256(source .. "\n") == want[2] and #source + 1 == want[3]
		print(name, (same or withNewline) and "OK" or "DIFFERENT", #source, "bytes")
	end
end
```

## What is not in Studio-only any more

Everything above is now written down. What this file cannot capture: anything changed in Studio by hand that nobody wrote down (the `ColorCorrection` values are in (b)). If something in the place looks different from the repo, the repo's scripts win (CONTRIBUTING.md, "Keeping Studio and the repo in sync").

## (e) Addendum: customer calls start when the player owns the Desk

Last code commit of this change: `7cf891f` (branch `task-needs-desk`, made from `main` at `e3c9e67`; the commits after it change only docs and tests). The first version of this addendum was code commit `5a07c70`; the review fix `7cf891f` changed **`TaskServer` only** (when calls turn on, the missed-call count and the idle clock start again), so if you already pasted the first version, paste `TaskServer` again and nothing else (the hash block says `DIFFERENT` for it otherwise). Nothing here touches Roblox: it is the list of what the Mac has to do. **No new script is created** (all three exist already, from the task engine PR 1), `TycoonCore` and `ShopClient` are **unchanged**, there is no new remote and no save change. This is section (e) because section (d) is the customize PR 1 addendum on branch `customize-pr1` (already in `integration-1`); the two do not overlap.

| Script | Studio type and place | State | sha256 | Bytes |
|---|---|---|---|---|
| `TaskConfig` | ModuleScript, **ReplicatedStorage** | changed | `a6ec3663f95bb23c87683416ad7ee2dbee5da2fcde3d28d97eb2f5600590fe06` | 14607 |
| `TaskServer` | ModuleScript, ServerScriptService | changed | `11fe77211926581d9d50e049e78cbabaff1086794d07b64a94d13bf6fef8fc99` | 35513 |
| `TaskClient` | LocalScript, StarterPlayer > StarterPlayerScripts | changed | `75ac0721e1d603222c7fa1f2efb31724210a500e7615066826d8d33a1c321807` | 18079 |

Since the first version of this addendum only `TaskServer` changed (old hash `7ee9ad23…`, 34933 bytes); `TaskConfig` and `TaskClient` are byte for byte the same. The hash block in (c) was re-run in Luau against the real files of this branch (a fake `game` that serves each `.lua` file as `Source`): all 13 lines say `OK`, also with the final newline dropped, and a one-character change in `TaskServer` says `DIFFERENT` for it alone. It has not been run in Studio's command bar.

**Which scripts differ, per branch** (hashes re-computed from each branch's files; the first 8 characters of each hash identify it):

| Branch | `TycoonCore` | The other nine scripts of (a) | `TaskConfig`, `TaskServer`, `TaskClient` | New scripts |
|---|---|---|---|---|
| `main` | the one in (a) (`77ce9c43`) | the ones in (a) | the task engine PR 1 versions | none |
| `task-needs-desk` (this section) | the one in (a), unchanged | the ones in (a), unchanged | the three rows above | none |
| `customize-pr1` and `integration-1` | the one in (d) (`9607262c`), **not** the one in (a) | the ones in (a), unchanged | the task engine PR 1 versions, unchanged | `SectorConfig`, `CompanyConfig`, `CompanyServer` (section (d)) |

So on this branch alone the ten scripts of (a) are identical to the repo and nothing else needs pasting. Once `customize-pr1`'s `TycoonCore` is pasted (an integration build that has both (d) and (e)), `TycoonCore` is the one of section (d) and the hash block in (c) says `DIFFERENT` for its `TycoonCore` line: that is expected, check `TycoonCore` with the block of (d) instead. Section (e) changes none of `TycoonCore`, `SectorConfig`, `CompanyConfig` or `CompanyServer`, so the two sections can be pasted in either order. The Studio MCP cannot create scripts inside services, which does not matter here: it is only a paste into three existing scripts.

### Steps on the Mac (by hand)

1. **Get the files.** `git fetch`, then open the three `.lua` files from branch `task-needs-desk` (in a folder no other session is using, or on GitHub: Code > branch `task-needs-desk`).
2. **Paste in this order,** each time: open the `.lua` file, select all, copy; in Studio double-click the script of that name, select all, paste.
   1. `TaskConfig` (ReplicatedStorage). It is read by both sides, so it goes first.
   2. `TaskServer` (ServerScriptService). Before the client: the new client waits for the `on` flag that only the new server sends (with the old server it would still show a waiting call, but never "Tap to resume").
   3. `TaskClient` (StarterPlayerScripts).
   - If a Studio place has no `TaskConfig` / `TaskServer` / `TaskClient` at all yet (the task engine PR 1 was never pasted there), follow the PR 1 order in docs/PUBLISH_RULES.md 2c instead.
3. **View > Drafts:** commit every draft (an uncommitted draft is not published).
4. **Verify the hashes.** Paste the hash block above into the command bar (View > Command Bar). It now also checks `TaskConfig`, `TaskServer` and `TaskClient` (it looks in ReplicatedStorage too). The three lines must say `OK`; `DIFFERENT` names the script to paste again.
5. **Playtest in Studio (F5) and read the Output window.** Use a test player whose save has no Desk (Test > Clients and Servers > Local Server with 2 players: Player1 and Player2 should start with an empty save the first time; a player that already bought the Desk keeps it, so use the other one).
   - Stay in the garage for 2 minutes without opening the shop: **no call, no phone tray, no "Tap to resume"** (before this change the first call rang after 20 to 40 s). Debug > "Task stats" shows `offered` 0.
   - Shop > Office > buy the Desk (it costs 0): the first call rings after a **normal gap**, then the tray works as before. Only with **no hires and the Garage rung** is that first call at least 20 s away (20 to 40 s). Later gaps, and the first one with hires or a higher rung, follow the old formula (`TaskConfig.gap`, unchanged): 14 s at best with 5 hires, 10.0 s at best with 13 or more hires at the Garage rung, 9.3 s at best with 13 or more hires at a higher rung, 7.8 s at best after 10 IPOs. So "never under 10 s" is not a rule of this change.
   - With Sales employees, after answering one call, "Team handled N calls" still appears.
   - Debug > "Jump to IPO-ready", Go Public: the upgrades reset (the Desk is gone) but **calls keep coming** and the tray stays.
   - Leave and rejoin with the Desk: calls come back after a normal gap.
   - Debug > "Task: spawn a call" still works before the Desk (it is a Studio tool); that call shows and can be answered.
   - Before the Desk, spawn three calls with that button and let them run out (about 10 s), then buy the Desk: **no "Tap to resume"** (the missed-call count starts at 0 when calls turn on; OWNER DEFAULT).
   - Phone layout (Test > Device): the tray did not move; only when it is visible changed.
6. **Publish** as usual. This change needs no "Shut down all servers" by itself: the task engine is Studio-only in PR 1 and nothing is saved differently.

Never tested in Studio by whoever wrote this (no Studio, no MCP): the steps above are the first real test.
