# Studio sync master list: everything for Studio in one session

> **Out of date (lobby-all, 2026-10-16).** This list is Integration 2's. Since then: `WorldArt` and `WorldVisuals` are no longer PASTE LATER (TycoonCore requires them when `LobbyConfig.ClaimEnabled` is on: lobby L4), and five scripts are new (`LobbyConfig`, `PlotBuilding`, `PlotBuildingVisuals`, `BuildingClient`, `LobbyClient`). Its hash block (section 6) now says `DIFFERENT` for 10 scripts: the 6 that branch `lobby-all` changes (`TycoonCore`, `ShopServer`, `ShopClient`, `IpoClient`, `WorldArt`, `WorldVisuals`) and the 4 that lobby L1 changed on `main` (`EmployeeServer`, `IpoServer`, `PlotVisuals`, `EmployeeClient`). For those scripts use docs/STUDIO_SYNC_LOBBY.md (its L1 section, then section "Lobby all"): its table and hash block are current. The other 23 rows here are still right.

The one list for putting **Integration 2** into Studio in one sitting: Integration 1 (design docs, sims, customize PR 1) plus `hud-cash`, `task-needs-desk`, `world-icons-pass` and `shop-build`. It covers every `.lua` file at the repo root. Written on branch `integration-2` at merge commit `8e41718` (the four merges; this file is the only commit after it). Nothing here touches Roblox by itself: it is what the owner does in Studio, by hand. No Studio and no MCP was used to write it.

**How the numbers were made:** each SHA-256 was computed from the real file on the merged tree three ways: the Luau `sha256` of docs/STUDIO_SYNC.md (run in the `luau` tool), `sha256sum` and Python's `hashlib`. All 33 agree. Every file uses `\n` line endings and ends with one newline. The hash block in section 6 was run in `luau` against the real files with a fake `game` (see "What was checked").

**The order, in short:** (1) create the scripts that are missing (section 2); (2) paste all 29 PASTE NOW scripts, **in any order** (section 3); (3) commit every draft; (4) run the hash block (section 6) until it prints `ALL OK`; (5) only then playtest. The order of pasting does not matter, because game scripts do not run in Edit mode. What matters is that every one of the 29 exists, with the right source and in the right place, **before the first playtest**. Section 4 says what goes wrong if a playtest starts earlier.

**Status:** 33 scripts. **29 PASTE NOW** (wired in the game: something runs or requires them). **4 PASTE LATER**: `IconArt`, `IconVisuals`, `WorldArt`, `WorldVisuals`. No script requires them yet, so they change nothing in the game:

- `IconArt` and `IconVisuals` are wired by shop PR **S3** ("Icons on cards and tabs", docs/SHOP_UX_PROPOSAL.md section 5). S3 makes `ShopClient` require them.
- `WorldArt` and `WorldVisuals` are wired by the TycoonCore edit in `docs/world_pass_integration.patch`, **only after the owner approves it**. On this tree `python3 tools/world_test.py --strict-patch` fails with "patch needs regenerating": the patch was made for `main`'s old TycoonCore (`77ce9c43…`, 34330 bytes), and this tree's TycoonCore is customize PR 1's (`9607262c…`, 36399 bytes). Regenerate it first (`--regen-patch`, on a branch that claims TycoonCore; docs/STUDIO_SYNC_WORLD.md (c) step 7). Applying it changes TycoonCore's hash, so the TycoonCore row below goes stale then.

You may paste the four PASTE LATER modules now if you want the previews (docs/STUDIO_SYNC_WORLD.md): they sit unused. If they are already in Studio from the previews, the hash block shows whether they match.

## 1. Before you start

1. **Pull:** `git fetch`, then use `main` once this pull request is merged, or branch `integration-2` before that. Use a folder no other session is working in (for example `git worktree add ~/Developer/studio-sync origin/integration-2`).
2. **Game Settings > Security > Enable Studio Access to API Services: ON** (CONTRIBUTING.md step 4). Without it saves can't load, and the wipe and read blocks in section 9 can't run.
3. **Optional: run the hash block (section 6) once before pasting anything**, to see what Studio has now. `MISSING` means create the script (section 2). `DIFFERENT` means paste it. `OK` means leave it. This first run only tells you what to do. The run that counts comes after you commit the drafts (section 3).

## 2. Scripts to create by hand first

The Studio MCP can't create a script inside a service, so create these by hand. In the Explorer, hover the parent, click **+**, pick the class, press F2 and type the exact name (capitals included). Then paste the file (section 3).

**New in Integration 1 and 2. Almost certainly missing:**

| Name | Class | Parent |
|---|---|---|
| `SectorConfig` | ModuleScript | ReplicatedStorage |
| `CompanyConfig` | ModuleScript | ReplicatedStorage |
| `ShopLayout` | ModuleScript | ReplicatedStorage |
| `CompanyServer` | ModuleScript | ServerScriptService |

**Made by earlier syncs. Create only if the hash block says `MISSING`:** `PlotArt` and `PlotVisuals` (ModuleScript, ServerScriptService; docs/STUDIO_SYNC.md (c)), `TaskConfig` (ModuleScript, ReplicatedStorage), `TaskServer` (ModuleScript, ServerScriptService), `TaskClient` (LocalScript, StarterPlayer > StarterPlayerScripts; docs/PUBLISH_RULES.md 2b).

**PASTE LATER (only when wired, or now for the previews):** `IconArt`, `IconVisuals` (ModuleScript, ReplicatedStorage), `WorldArt`, `WorldVisuals` (ModuleScript, ServerScriptService). (Out of date: with lobby-all, `WorldArt` and `WorldVisuals` are pasted now, from docs/STUDIO_SYNC_LOBBY.md "Lobby all"; see the note at the top.)

## 3. The list (paste in any order)

Paste each one the same way: open the `.lua` file, select all, copy; in Studio double-click the script, select all, paste. **The order does not matter.** Nothing runs in Edit mode, so paste the 29 PASTE NOW scripts in any order, even bottom to top. The table is only sorted so that the hash block's lines come out in a fixed order (ReplicatedStorage, then the server modules, then `TycoonCore`, then the clients). Do **not** start a playtest (F5, F7 or a Studio test) until the hash block says `ALL OK`: section 4 says why.

| # | Name | Class | Parent | sha256 | Bytes | Status | Note |
|---|---|---|---|---|---|---|---|
| 1 | `SectorConfig` | ModuleScript | ReplicatedStorage | `60629dc4d4368652a4235ba2b6ccb5499836361110c6e7331f7ae46730a0ee6b` | 3194 | PASTE NOW | CompanyConfig waits for it |
| 2 | `IpoConfig` | ModuleScript | ReplicatedStorage | `dfed7f60562224a457c3f3f51e66d91fcd4bacc5b270fb57c9834d79b190359f` | 9645 | PASTE NOW | almost everything waits for it |
| 3 | `CompanyConfig` | ModuleScript | ReplicatedStorage | `bc8745926f2a0c89eaab7881211ffe0618f3171c42947527db69cfb550f1ff7c` | 41284 | PASTE NOW | waits for SectorConfig, IpoConfig |
| 4 | `CreatureConfig` | ModuleScript | ReplicatedStorage | `297adfb35f7f0c4a0d679f2a92943ad673c79a839c9b70f7d777af71b8de3530` | 18398 | PASTE NOW |  |
| 5 | `CreatureModels` | ModuleScript | ReplicatedStorage | `0a12eabb670a81d4a261145fa20b25b4a15a874778699e3e0045788a5dd94d8f` | 8188 | PASTE NOW |  |
| 6 | `ShopConfig` | ModuleScript | ReplicatedStorage | `0f7f7b9f3c2573ff605e976fda9d6299a5c3e84a639fa3b22f6ec5659d30675e` | 7426 | PASTE NOW |  |
| 7 | `ShopLayout` | ModuleScript | ReplicatedStorage | `73c4ddd5279025fbd32f2a19029af8d621c84816ffbb51c010ac701e8ed24fdf` | 24458 | PASTE NOW | ShopClient waits for it |
| 8 | `DailyConfig` | ModuleScript | ReplicatedStorage | `875b7f46db80725c2add6a6bd5e35222d8cf40b3ad6baf5c4d0d3d4e8a2bd5e2` | 6878 | PASTE NOW | reads CreatureConfig (5 s, in pcall) |
| 9 | `OnboardingConfig` | ModuleScript | ReplicatedStorage | `b0ef6396855188016dc548d0bc6660f52ce3c6c2d06604f48c1879d47531b309` | 3277 | PASTE NOW |  |
| 10 | `TaskConfig` | ModuleScript | ReplicatedStorage | `a6ec3663f95bb23c87683416ad7ee2dbee5da2fcde3d28d97eb2f5600590fe06` | 14607 | PASTE NOW | TaskServer and TaskClient wait for it |
| 11 | `ShopServer` | ModuleScript | ServerScriptService | `97e6ec51c10df789d1b0bf2620908e81c1bc883ace6aa71762062139f06fa27d` | 32803 | PASTE NOW |  |
| 12 | `IpoServer` | ModuleScript | ServerScriptService | `96e8f073d2039dd1201cbc23137b5730cc8783644bc0085cdd5e7cd3a29e2e52` | 17377 | PASTE NOW | waits for ShopServer |
| 13 | `EmployeeServer` | ModuleScript | ServerScriptService | `65fefebf56b21d85c87e773a9dc8734754c716e29d693cb1fd15b79381894597` | 31745 | PASTE NOW | waits for ShopServer, IpoServer |
| 14 | `PoachServer` | ModuleScript | ServerScriptService | `bfb9808f82f0545b9915d07b5c2dc1a5fc43711271c0e24bbbf43fb4d8f5fb01` | 36418 | PASTE NOW | waits for ShopServer, EmployeeServer, IpoServer |
| 15 | `OnboardingServer` | ModuleScript | ServerScriptService | `8ba5226541b9fe6d01d488a31b81aa21e207a014174541ece942ac3f38e5a05a` | 14662 | PASTE NOW | waits for EmployeeServer, ShopServer |
| 16 | `CompanyServer` | ModuleScript | ServerScriptService | `826dfba8fac00bee190fd62265024be1c1e4c43d41f4c84d5cf462e20a500a10` | 8268 | PASTE NOW | waits for CompanyConfig |
| 17 | `TaskServer` | ModuleScript | ServerScriptService | `11fe77211926581d9d50e049e78cbabaff1086794d07b64a94d13bf6fef8fc99` | 35513 | PASTE NOW | waits for TaskConfig, IpoServer, ShopServer |
| 18 | `DailyServer` | ModuleScript | ServerScriptService | `1a77d44764591fb6b026e29e18e9b4b6ec67835f64a88135154b8dc246c80de5` | 16035 | PASTE NOW | waits for EmployeeServer, IpoServer, ShopServer |
| 19 | `PlotArt` | ModuleScript | ServerScriptService | `b2a08432fdecfd3ae624d9c938de191348f03877e772562341a4eb94a7f7b0c2` | 60671 | PASTE NOW | TycoonCore waits 5 s, in pcall |
| 20 | `PlotVisuals` | ModuleScript | ServerScriptService | `2e10736f60b86590f0bced98eb3d8d0e9b0264108cdc9cd02f68dd8b5651ba89` | 26508 | PASTE NOW | TycoonCore waits 5 s, in pcall |
| 21 | `TycoonCore` | Script | ServerScriptService | `9607262c64d762cc15644a8ab3d85821cfaba2654879a9018210e1237679def2` | 36399 | PASTE NOW | waits for 8 server modules and IpoConfig |
| 22 | `ShopClient` | LocalScript | StarterPlayer > StarterPlayerScripts | `ff29fe44e9f7b79a1da40aead7190bb4c7c95ee14bede4998323fe7ed9af883a` | 59330 | PASTE NOW | waits for ShopLayout |
| 23 | `EmployeeClient` | LocalScript | StarterPlayer > StarterPlayerScripts | `4aa4faa9cb06f166179a73fe6ee83b11b919c3a650c758dffcb615a98e641152` | 35379 | PASTE NOW |  |
| 24 | `PoachClient` | LocalScript | StarterPlayer > StarterPlayerScripts | `6c32b7fbb9e00ca9d8a3cad5371148a939c6bc0c27ecf5069dea6ab0791f2230` | 39678 | PASTE NOW |  |
| 25 | `IpoClient` | LocalScript | StarterPlayer > StarterPlayerScripts | `e7937d8785ee5451154b6b99e2b80c37dff050e5aaf5a64fc5e64e25a1a09511` | 41550 | PASTE NOW |  |
| 26 | `OnboardingClient` | LocalScript | StarterPlayer > StarterPlayerScripts | `0f7659d70e2c159a88619892d3fb63ceb479b07d0df0e787a47efad079dba7e1` | 13063 | PASTE NOW |  |
| 27 | `DailyClient` | LocalScript | StarterPlayer > StarterPlayerScripts | `0cb4fc716cf4f16b9e8e077b9347318f58ce8680759330e35706c4695e542fea` | 22544 | PASTE NOW |  |
| 28 | `TaskClient` | LocalScript | StarterPlayer > StarterPlayerScripts | `75ac0721e1d603222c7fa1f2efb31724210a500e7615066826d8d33a1c321807` | 18079 | PASTE NOW | waits for TaskConfig |
| 29 | `ChatTags` | LocalScript | StarterPlayer > StarterPlayerScripts | `9a656b9ceabe6d6948b88a7bc12787cd7d3df7008f2b48beeb4f4ed89c2ec5d1` | 843 | PASTE NOW |  |
| 30 | `IconArt` | ModuleScript | ReplicatedStorage | `83a43be6471c597a15a6f2ffcf1f7712fadc3d5e348b3b8a10c067b702236915` | 30741 | **PASTE LATER** | wired by shop PR S3 |
| 31 | `IconVisuals` | ModuleScript | ReplicatedStorage | `f4543a25877c459389553663fc413eadb3bb14170598e3f2e1f3435ee0f491e4` | 55083 | **PASTE LATER** | wired by shop PR S3 |
| 32 | `WorldArt` | ModuleScript | ServerScriptService | `972e799cb429b2b9afee9d446b59b1fe22db36e7cd6f2d030499ed8cb627b5a9` | 13042 | **PASTE LATER** | wired by the world patch (TycoonCore) |
| 33 | `WorldVisuals` | ModuleScript | ServerScriptService | `81adef34a9f769faa060523f2d03719efdc7fab1ee9fae476446fbf48bebd343` | 48782 | **PASTE LATER** | wired by the world patch (TycoonCore) |

After pasting all 29: **View > Drafts**, commit every draft. An uncommitted draft is not published. **Commit first, then run the hash block (section 6).** Whether the command bar's `Source` shows a draft that is not committed yet is **unverified** (nobody has checked it in Studio), so a run before the commit may report a script as `DIFFERENT` or as `OK` for the wrong reason. A line you trust comes from a run after the commit.

## 4. Why a half-pasted playtest hangs (background: the order of pasting does not matter)

You do not need this section to paste. It explains why section 3 says "no playtest before `ALL OK`". Each line below is a `WaitForChild` with **no time limit** (a `require` of a module that must exist). If the module is missing when the game runs, the waiting script hangs on "Infinite yield possible" for good. If that script is `TycoonCore`, nobody can load a save. Checked in every root `.lua` file (comments skipped): **63 pairs**. In Edit mode none of this runs, so the order in which you paste is free.

**What happens if a module exists but still holds Studio's default template** (a ModuleScript that returns an empty table), when a playtest starts anyway:

- **`CompanyServer`:** `TycoonCore` errors at `CompanyServer.init` (`TycoonCore.lua` ~687: a call of a nil value) **before** it connects `PlayerAdded` (~872). No plot, no save, no load for anyone, and a red error in the Output.
- **`ShopLayout`:** `ShopClient` errors at about line 200 (`ShopLayout.TOAST_MAX_W` is nil, so `Vector2.new` gets no number). The shop never builds: no shop window. (Not run in Studio; read from the code.)
- **`PlotArt` / `PlotVisuals`:** every call goes through `pcall` (`looks()`, `TycoonCore.lua` ~166). The game runs with the plain upgrade blocks and no rooms, with a `Plot visuals: ... failed` warning per call. If the two are missing altogether, `TycoonCore` waits 5 s for each and warns `Plot visuals are off`.

The hash block catches every one of these as `DIFFERENT` (a template has a different size and hash), and a script that does not exist as `MISSING`.

The pairs, as background:

- `CompanyConfig` waits for `SectorConfig`, `IpoConfig`
- `ShopServer` waits for `ShopConfig`
- `IpoServer` waits for `IpoConfig`, `ShopConfig`, `ShopServer`
- `EmployeeServer` waits for `CreatureConfig`, `CreatureModels`, `ShopServer`, `IpoServer`
- `PoachServer` waits for `CreatureConfig`, `ShopConfig`, `ShopServer`, `EmployeeServer`, `IpoServer`
- `OnboardingServer` waits for `OnboardingConfig`, `IpoConfig`, `CreatureConfig`, `EmployeeServer`, `ShopServer`
- `CompanyServer` waits for `CompanyConfig`
- `TaskServer` waits for `TaskConfig`, `IpoConfig`, `DailyConfig`, `ShopConfig`, `IpoServer`, `ShopServer`
- `DailyServer` waits for `DailyConfig`, `OnboardingConfig`, `CreatureConfig`, `ShopConfig`, `EmployeeServer`, `IpoServer`, `ShopServer`
- `TycoonCore` waits for `IpoConfig`, `ShopServer`, `IpoServer`, `EmployeeServer`, `PoachServer`, `OnboardingServer`, `CompanyServer`, `TaskServer`, `DailyServer`
- `ShopClient` waits for `ShopConfig`, `ShopLayout`, `CreatureConfig`, `IpoConfig`
- `EmployeeClient` waits for `CreatureConfig`, `CreatureModels`, `ShopConfig`, `IpoConfig`
- `PoachClient` waits for `CreatureConfig`, `CreatureModels`, `ShopConfig`
- `IpoClient` waits for `IpoConfig`, `ShopConfig`
- `OnboardingClient` waits for `OnboardingConfig`, `IpoConfig`
- `DailyClient` waits for `DailyConfig`, `CreatureConfig`, `ShopConfig`, `IpoConfig`
- `TaskClient` waits for `TaskConfig`

The pairs the brief named are in the list: `TycoonCore` waits for `CompanyServer`, `CompanyServer` for `CompanyConfig`, `CompanyConfig` for `SectorConfig`; `ShopClient` waits for `ShopLayout`; `TaskServer` and `TaskClient` wait for `TaskConfig`, and `TycoonCore` waits for `TaskServer`. If all 29 are in place, none of these waits can hang.

**Waits with a time limit (they never hang):** `TycoonCore` waits 5 s for `PlotVisuals` and `PlotArt` inside `pcall` (without them it builds no rooms). `ShopClient` waits 5 s for `TaskConfig` (without it there are no Task Debug rows). `IpoClient` waits 5 s for `DailyConfig`. `DailyConfig` waits 5 s for `CreatureConfig` inside `pcall`. The four PASTE LATER modules and `ShopLayout`, `PlotArt`, `PlotVisuals`, `CreatureModels`, `SectorConfig`, `TaskConfig` and `ChatTags` wait for no other script.

## 5. Studio settings that are not scripts

Already written down. Nothing here is new; check them, don't change them:

- **Lighting, Atmosphere, Bloom, ColorCorrection and the Baseplate:** docs/STUDIO_SYNC.md (b). In short: Lighting `ClockTime` 14. A `ColorCorrection` in Lighting: `Enabled` true, `Brightness` 0.03, `Contrast` 0.08, `Saturation` 0.15, `TintColor` 255, 246, 232. Atmosphere `Haze` 1.2, `Glare` 0.3. Bloom `Intensity` 0.6, `Size` 32, `Threshold` 1.6. `Workspace.Baseplate` color grass (108, 172, 82), with the grid `Texture` removed.
- **Studio facts the world pass reads** (don't change them): `Workspace.Baseplate` 2048 x 16 x 2048 at (0, -8, 0); `Workspace.SpawnLocation` 12 x 1 x 12 at (-1, 0.5, -1). `StreamingEnabled` stays as it is. See docs/STUDIO_SYNC_WORLD.md (b).
- **Enable Studio Access to API Services: ON** (section 1).
- **Max Players: 6** (a place setting, docs/PUBLISH_RULES.md section 1). Check it after every publish.

## 6. Hash check (command bar): all 33 scripts (run it after you commit the drafts)

> **Out of date (lobby-all):** on a place synced to branch `lobby-all` this block prints `DIFFERENT` for 10 scripts (see the note at the top). That is expected: check those with docs/STUDIO_SYNC_LOBBY.md's hash blocks instead.

Paste the whole block into **View > Command Bar** and press Enter. It changes nothing. It prints one line per script, in the table's order: `OK`, `DIFFERENT` (paste the file again), `MISSING` (create it, section 2) or `WRONG CLASS` (delete it and create it again with the right class). The last line must say `ALL OK: 29 of 29 PASTE NOW scripts match the repo`. The four PASTE LATER lines may say `MISSING (PASTE LATER: not needed yet)`. Studio may drop a script's last newline or add one more, and the block accepts both cases (the same rule as docs/STUDIO_SYNC_SHOP.md (d)).

Run it **after** you commit the drafts (section 3). Whether the command bar's `Source` shows an uncommitted draft is **unverified**.

**Two cases the block does not flag:**

- **A script in the wrong parent** (for example `ShopLayout` in `StarterPlayerScripts`) shows as `MISSING`, because the block only looks in the right parent. **Do not create a second copy.** Drag the script into the right parent, or delete it and create it there.
- **A duplicate name** (two scripts called `TycoonCore` in the same parent) is **not detected**: the block looks at one of them (`FindFirstChild` returns one) and may print `OK` for it while the other one runs or is the stale copy. Look in the Explorer for double names, and delete the extra one by hand.

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

-- STUDIO_SYNC_MASTER hash check: every script of docs/STUDIO_SYNC_MASTER.md, in the table's order. Changes nothing.
local function folderOf(place)
	if place == "StarterPlayerScripts" then
		return game:GetService("StarterPlayer"):FindFirstChild("StarterPlayerScripts")
	end
	return game:GetService(place)
end
local WANT = {
	{ "SectorConfig", "ModuleScript", "ReplicatedStorage", "60629dc4d4368652a4235ba2b6ccb5499836361110c6e7331f7ae46730a0ee6b", 3194, "now" },
	{ "IpoConfig", "ModuleScript", "ReplicatedStorage", "dfed7f60562224a457c3f3f51e66d91fcd4bacc5b270fb57c9834d79b190359f", 9645, "now" },
	{ "CompanyConfig", "ModuleScript", "ReplicatedStorage", "bc8745926f2a0c89eaab7881211ffe0618f3171c42947527db69cfb550f1ff7c", 41284, "now" },
	{ "CreatureConfig", "ModuleScript", "ReplicatedStorage", "297adfb35f7f0c4a0d679f2a92943ad673c79a839c9b70f7d777af71b8de3530", 18398, "now" },
	{ "CreatureModels", "ModuleScript", "ReplicatedStorage", "0a12eabb670a81d4a261145fa20b25b4a15a874778699e3e0045788a5dd94d8f", 8188, "now" },
	{ "ShopConfig", "ModuleScript", "ReplicatedStorage", "0f7f7b9f3c2573ff605e976fda9d6299a5c3e84a639fa3b22f6ec5659d30675e", 7426, "now" },
	{ "ShopLayout", "ModuleScript", "ReplicatedStorage", "73c4ddd5279025fbd32f2a19029af8d621c84816ffbb51c010ac701e8ed24fdf", 24458, "now" },
	{ "DailyConfig", "ModuleScript", "ReplicatedStorage", "875b7f46db80725c2add6a6bd5e35222d8cf40b3ad6baf5c4d0d3d4e8a2bd5e2", 6878, "now" },
	{ "OnboardingConfig", "ModuleScript", "ReplicatedStorage", "b0ef6396855188016dc548d0bc6660f52ce3c6c2d06604f48c1879d47531b309", 3277, "now" },
	{ "TaskConfig", "ModuleScript", "ReplicatedStorage", "a6ec3663f95bb23c87683416ad7ee2dbee5da2fcde3d28d97eb2f5600590fe06", 14607, "now" },
	{ "ShopServer", "ModuleScript", "ServerScriptService", "97e6ec51c10df789d1b0bf2620908e81c1bc883ace6aa71762062139f06fa27d", 32803, "now" },
	{ "IpoServer", "ModuleScript", "ServerScriptService", "96e8f073d2039dd1201cbc23137b5730cc8783644bc0085cdd5e7cd3a29e2e52", 17377, "now" },
	{ "EmployeeServer", "ModuleScript", "ServerScriptService", "65fefebf56b21d85c87e773a9dc8734754c716e29d693cb1fd15b79381894597", 31745, "now" },
	{ "PoachServer", "ModuleScript", "ServerScriptService", "bfb9808f82f0545b9915d07b5c2dc1a5fc43711271c0e24bbbf43fb4d8f5fb01", 36418, "now" },
	{ "OnboardingServer", "ModuleScript", "ServerScriptService", "8ba5226541b9fe6d01d488a31b81aa21e207a014174541ece942ac3f38e5a05a", 14662, "now" },
	{ "CompanyServer", "ModuleScript", "ServerScriptService", "826dfba8fac00bee190fd62265024be1c1e4c43d41f4c84d5cf462e20a500a10", 8268, "now" },
	{ "TaskServer", "ModuleScript", "ServerScriptService", "11fe77211926581d9d50e049e78cbabaff1086794d07b64a94d13bf6fef8fc99", 35513, "now" },
	{ "DailyServer", "ModuleScript", "ServerScriptService", "1a77d44764591fb6b026e29e18e9b4b6ec67835f64a88135154b8dc246c80de5", 16035, "now" },
	{ "PlotArt", "ModuleScript", "ServerScriptService", "b2a08432fdecfd3ae624d9c938de191348f03877e772562341a4eb94a7f7b0c2", 60671, "now" },
	{ "PlotVisuals", "ModuleScript", "ServerScriptService", "2e10736f60b86590f0bced98eb3d8d0e9b0264108cdc9cd02f68dd8b5651ba89", 26508, "now" },
	{ "TycoonCore", "Script", "ServerScriptService", "9607262c64d762cc15644a8ab3d85821cfaba2654879a9018210e1237679def2", 36399, "now" },
	{ "ShopClient", "LocalScript", "StarterPlayerScripts", "ff29fe44e9f7b79a1da40aead7190bb4c7c95ee14bede4998323fe7ed9af883a", 59330, "now" },
	{ "EmployeeClient", "LocalScript", "StarterPlayerScripts", "4aa4faa9cb06f166179a73fe6ee83b11b919c3a650c758dffcb615a98e641152", 35379, "now" },
	{ "PoachClient", "LocalScript", "StarterPlayerScripts", "6c32b7fbb9e00ca9d8a3cad5371148a939c6bc0c27ecf5069dea6ab0791f2230", 39678, "now" },
	{ "IpoClient", "LocalScript", "StarterPlayerScripts", "e7937d8785ee5451154b6b99e2b80c37dff050e5aaf5a64fc5e64e25a1a09511", 41550, "now" },
	{ "OnboardingClient", "LocalScript", "StarterPlayerScripts", "0f7659d70e2c159a88619892d3fb63ceb479b07d0df0e787a47efad079dba7e1", 13063, "now" },
	{ "DailyClient", "LocalScript", "StarterPlayerScripts", "0cb4fc716cf4f16b9e8e077b9347318f58ce8680759330e35706c4695e542fea", 22544, "now" },
	{ "TaskClient", "LocalScript", "StarterPlayerScripts", "75ac0721e1d603222c7fa1f2efb31724210a500e7615066826d8d33a1c321807", 18079, "now" },
	{ "ChatTags", "LocalScript", "StarterPlayerScripts", "9a656b9ceabe6d6948b88a7bc12787cd7d3df7008f2b48beeb4f4ed89c2ec5d1", 843, "now" },
	{ "IconArt", "ModuleScript", "ReplicatedStorage", "83a43be6471c597a15a6f2ffcf1f7712fadc3d5e348b3b8a10c067b702236915", 30741, "later" },
	{ "IconVisuals", "ModuleScript", "ReplicatedStorage", "f4543a25877c459389553663fc413eadb3bb14170598e3f2e1f3435ee0f491e4", 55083, "later" },
	{ "WorldArt", "ModuleScript", "ServerScriptService", "972e799cb429b2b9afee9d446b59b1fe22db36e7cd6f2d030499ed8cb627b5a9", 13042, "later" },
	{ "WorldVisuals", "ModuleScript", "ServerScriptService", "81adef34a9f769faa060523f2d03719efdc7fab1ee9fae476446fbf48bebd343", 48782, "later" },
}
local nowOk, nowTotal, problems = 0, 0, {}
for _, w in ipairs(WANT) do
	local name, class, place, hash, bytes, when = w[1], w[2], w[3], w[4], w[5], w[6]
	local later = when == "later"
	if not later then
		nowTotal += 1
	end
	local folder = folderOf(place)
	local script = folder and folder:FindFirstChild(name)
	local result
	if not script then
		result = later and "MISSING (PASTE LATER: not needed yet)" or ("MISSING (create a " .. class .. " in " .. place .. ")")
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
		if ok and not later then
			nowOk += 1
		end
	end
	print(name, result, later and "(PASTE LATER)" or "")
	if not later and string.sub(result, 1, 2) ~= "OK" then
		table.insert(problems, name)
	end
end
print(#problems == 0 and ("ALL OK: " .. nowOk .. " of " .. nowTotal .. " PASTE NOW scripts match the repo")
	or ("NOT YET: " .. nowOk .. " of " .. nowTotal .. " PASTE NOW scripts match; fix " .. table.concat(problems, ", ")))
```

## 7. Delete before any playtest and before publishing

| Object | Why | How |
|---|---|---|
| `Workspace.PREVIEW_STAGES` | the plot rooms' preview (docs/STUDIO_SYNC.md (c) step 5); not part of the game | the cleanup block of docs/STUDIO_SYNC_WORLD.md (e) |
| `Workspace.PREVIEW_WORLD` | the world preview; it lies where the wired-in world will be built | the same cleanup block |
| `StarterGui.PREVIEW_ICONS` | the icon sheet and the light test; everything in StarterGui is copied onto every player's screen | the same cleanup block |
| `StarterGui.PREVIEW_LIGHT`, if it is there | left by an older light test (docs/STUDIO_SYNC_WORLD.md (e)) | by hand: select it, press Delete |
| the stray empty **SurfaceGui** directly in **Workspace** | not part of the game: every SurfaceGui the scripts use (signs, the VIP door, rooms, the world) is made by a script while the game runs, and no script looks for one saved in the place | by hand: select it, check in the Explorer that it has nothing inside, press Delete |

Then paste the **check block** of docs/STUDIO_SYNC_WORLD.md (e): it must print `OK`. The cleanup block deletes exactly the three `PREVIEW_` objects by name and only reports any other `PREVIEW_` object, so delete those by hand.

## 8. Before the playtest

- Sections 2 and 3 are done (all 29 PASTE NOW scripts exist and are pasted, in any order), the drafts are committed, and the hash block (section 6, run after the commit) prints `ALL OK`.
- Section 7 is done and the check block prints `OK`.
- The Output window is open (View > Output). Read it the whole time: no red text.

## 9. Combined playtest checklist

These are the steps of every addendum, in one order: docs/STUDIO_SYNC_HUD.md (d) (the Cash bar), docs/STUDIO_SYNC.md (e) step 5 (calls start with the Desk), docs/STUDIO_SYNC_SHOP.md (e) (the shop), docs/STUDIO_SYNC.md (d) steps 6 and 7 (the `pokedex` section). The addenda list the exact texts to expect. Here the steps are only ordered so that one fresh save covers all of them: the Desk check needs a save with no Desk and **no IPO** (an IPO turns calls on without the Desk).

**A. Wipe the two test keys.** Studio's test players are Player1 (UserId -1) and Player2 (UserId -2), so their saves are the keys `player_-1` and `player_-2`. These are the only keys this block touches: a written list, never a loop over keys (docs/PUBLISH_RULES.md step 13). Paste it into the command bar in edit mode. Both lines must say `OK`.

```lua
-- Wipe the saves of Studio's two test players, and nothing else: Player1 is UserId -1, Player2 is UserId -2.
local okStore, store = pcall(function()
	return game:GetService("DataStoreService"):GetDataStore("StartupTycoon_v1")
end)
if not okStore then
	print("FAIL no DataStore (turn on Enable Studio Access to API Services): " .. tostring(store))
else
	for _, key in ipairs({ "player_-1", "player_-2" }) do
		local ok, err = pcall(function()
			store:RemoveAsync(key)
		end)
		print(key, ok and "OK removed (or it was already empty)" or ("FAIL not removed: " .. tostring(err)))
	end
end
```

**B. Start the 2-player test (F7).** Use **Test > Clients and Servers**, **Local Server** with **2 Players**, then **Start**. Both players start with an empty save. Watch the server's Output: no red text, no `Infinite yield possible`, no `Could not set up`, no `Keeping a part of ... save this version doesn't know` (`pokedex` and `tasks` are known sections), no error naming `ShopClient` or `ShopLayout`.

**C. Player1: the Cash bar while loading, then no calls before the Desk.**
1. Cash bar (HUD (d) 1): the top row is empty for a moment, then shows `$0 · +$0/s`. The bottom row shows the Garage stage at `$0 / $1.8K`, or a shorter form. Nothing says `nil`, `nan` or a minus sign.
2. Stay **2 minutes** without opening the shop: no call, no phone tray, no "Tap to resume" (Desk (e) 5). Then Shop > Debug > "Task stats". The Debug message says `... 0 answered, 0 missed, 0 team ...`: the word `offered` is **not** in it. `offered=0` is only in the long `[TaskStats]` line that the same button prints in the Output window (TaskServer `statsLine`; the server also prints that line by itself every 10 minutes, `TaskConfig.LogSeconds`). (Opening the shop to read it is fine; just don't buy.)

**D. Player2: missed calls before the Desk don't start quiet mode.** Shop > Debug > "Task: spawn a call" three times (the queue holds three). **The calls only show after you close the shop**: the tray hides while any window is open, and the server freezes each call's clock meanwhile (at most 30 s per call, `TaskConfig.Pause.perTask`), so **close the shop within 30 s of the last Spawn**. After the close the three calls show and can be answered (a Studio tool); each one runs out about **8 s** later (`limit = 8` in `TaskConfig`'s Call row; there is no hire and no IPO, so no scaling). Let them run out, then open the shop, Office > buy the Desk, and close the shop again: **no "Tap to resume"** (Desk (e) 5, OWNER DEFAULT). Player2 is done for now.

**E. Player1: buy the Desk.** Shop: it opens on the **Office** tab; the tabs are a column on the left on a wide window (shop (e) 1-2). The Desk's button says **Get it free**. Tap it: "..." then **Bought!**, the icon pops, **+$1/s** floats up, and the Desk folds into "1 of 6 bought" (shop (e) 4). The bar's top row becomes `$0 · +$1/s` and counts up about once a second (HUD (d) 2). The **first call rings 20 to 40 s after you close the shop, not after the buy**: calls are frozen while any window is open (TaskServer, the paused branch of the step), so the gap only starts counting once the shop is closed. (That is 20 to 40 s with no hires at the Garage rung. If Player1 has Auto-Hatch, the free egg hatches by itself after its 60 s timer and makes one hire, and the gap becomes `U(20, 40) / 1.08`: about **18.5 to 37 s**.) Then the tray works as before (Desk (e) 5).

**F. Player1: the shop and the bar.** The Cash bar texts depend on how much Cash Player1 has, and the shop steps spend it, so do them **in this order** (right after E, Cash is a few dollars; nothing in the Debug tab *sets* Cash, it only adds):
1. Shop (e) 3: each tab, the BEST VALUE badge.
2. Shop (e) 5 and 6: the next card's bar and "Need $N more" only show while Cash is under its price. The Coffee Machine costs $25 and Cash grows by $1/s, so it says "Need" for only about 25 s after the Desk: if it already says **Buy**, buy it (e) 6 and read the same thing on the Laptop's card instead ($100, Cash about $0, +$3/s: about 33 s). Then shop (e) 7: the summary row. Cash is now small, about $0 to $100.
3. HUD (d) 3: leave it 30 s; the top row moves about once a second without shaking.
4. HUD (d) 4, with that small Cash: Debug > **Give $10,000**: the top row shows about `$10,1xx · +$3/s` (10,000 plus the little you had, about $100 after step 3; the full figure shows below $100,000). Then **Give $1,000,000**: `$1M` (it shows `$1M` for any Cash from $1,000,000 up to $1,049,999). Then **Give $1,000,000** again: `$2M`. No `e+`. (If you Give a third time, `$3M`; a Cash of $1,050,000 would read `$1.1M`.)
5. Shop (e) 6, with the $2M you now have: buy the next upgrades one by one (Laptop, Server Rack, Whiteboard, Neon Logo), then (e) 8: all six bought and the gold **Office complete** banner. (The step's own "Give $1,000,000" is not needed: step 4 gave it.)
6. Shop (e) 9 (the "?" card) and 10 (the message line); answer a few calls too, so the save gets a `tasks` section. Also shop (e) 12 (restricted on and off) and, if you like, (e) 13 (the tutorial strip).

Cash is about $2,000,000 at the end of F.

**G. Player1: employees, then the IPO.** With Sales employees, after you answer one call, "Team handled N calls" still appears (Desk (e) 5). Then Debug > **Valuation +$100,000**. The amount is fixed in the button and a valuation is never negative, so this always passes IPO-ready (`IpoConfig.Stages`: $81,000): the bar is full and the bottom row **already says IPO-ready** (the button does not stop at a middle stage). "Names the next stage" (HUD (d) 5) is therefore not testable with it: you saw `Garage → Seed` in C.1 and the stages change by themselves as the valuation grows (Seed $1,800, Series A $6,300, Series B $23,400); there is no Debug button for a middle amount. Then **Jump to IPO-ready** (it also skips the IPO cooldown): the bottom row says `🔔 IPO-ready! ...` and the IPO button says `IPO!`. Tap the bar: the IPO window opens (HUD (d) 5). **Go Public**: the upgrades reset (the Desk is gone) but **calls keep coming** and the tray stays (Desk (e) 5). Then Debug > **Reset IPO progress**: the Desk is the hero card again with **Get it free** (shop (e) 4). **Buy it again**, so that step I has the Desk. An IPO sets Cash back to $0 (`IpoConfig.StartingCash`), so Cash is about $0 again here.

**H. Phones (Test > Device).** First set the state the checks need: after G only the Desk is owned and Cash is about $0. **Debug > Give $10,000**, then buy the **Coffee Machine, Laptop and Server Rack**, so that **4 of 6 are owned (Desk, Coffee Machine, Laptop, Server Rack)** and the **Whiteboard** is the next card. Cash is then about $9,500 and Income `+$23/s`, so the bar's top row reads about `$9,5xx · +$23/s`. Then, at **320 x 568** and **667 x 375**, and once at 568 x 320 and 844 x 390:
- The Cash bar text fits inside the bar (HUD (d) 6).
- The windows don't overlap the buttons (HUD (d) 7).
- The shop: nothing cut off, the left edge of the Office tab at 667 x 375 and the middle at 844 x 390 keep the shop open, the long pop-up at 320 x 568, the portrait tab row with Debug, and at 568 x 320 the Whiteboard card says "+$40/s" (the shorter form; shop (e) 11). With 3 owned it would say "+$15/s" (Server Rack), with 5 owned "+$120/s" (Neon Logo); with only the Desk owned the next card is the Coffee Machine, "+$2", which is not the check.
- The call tray did not move (Desk (e) 5).

**The four sizes may not be in Studio's device list.** Whether the Device emulator has 320 x 568, 667 x 375, 568 x 320 and 844 x 390 as named devices is **unverified**, and so is how to add one. Look in the Device dropdown for an add or custom entry that takes a width and a height. If there is none, take the nearest phone in the list, write down its real size in your notes, and do not mark the missing size as tested.

Then go back to the desktop view.

**I. Leave and rejoin: the save round trip.**
1. Stop the test (Shift+F5, or the Stop button) and start it again (step B, **no wipe**).
2. Player1's bar: the top row is **empty for a moment** (about 7 s more if the save is under 75 s old), then shows the **saved Cash**. It never shows `$0 · +$0/s` on the way (HUD (d) 8).
3. Calls come back after a normal gap (Desk (e) 5).
4. Because step G used **Reset IPO progress**, the server's Output may show one **expected** warning for Player1: `Player1's pokedex is from IPO 1 but their IPO count is 0 (an IPO reset in Studio, or a restored save): no stamp, the company stays`. That is the run check doing its job (docs/PUBLISH_RULES.md 2d).
5. It must **not** say `Keeping a part of ... save this version doesn't know: pokedex` or `Keeping Player1's pokedex as it is`.
6. Leave again: stop the test.

**J. Read the saved `pokedex` section back (command bar, edit mode).** It changes nothing. For each test player who joined, the first line must start with `OK`: `v` 1, `run` equal to `ipo.count`, sector `Software`, `studio` true (every Studio save sets it, PUBLISH_RULES 2d). `CHECK` with `run` above `ipo.count` means step I's rejoin was skipped after the IPO reset: do step I again. `tasks` shows the calls Player1 answered.

```lua
-- Read only: the pokedex and tasks sections of the two test saves. Changes nothing.
local okStore, store = pcall(function()
	return game:GetService("DataStoreService"):GetDataStore("StartupTycoon_v1")
end)
if not okStore then
	print("FAIL no DataStore (turn on Enable Studio Access to API Services): " .. tostring(store))
else
	for _, key in ipairs({ "player_-1", "player_-2" }) do
		local ok, save = pcall(function()
			return store:GetAsync(key)
		end)
		if not ok then
			print(key, "FAIL could not read: " .. tostring(save))
		elseif type(save) ~= "table" then
			print(key, "no save (this test player never joined)")
		else
			local p, ipo = save.pokedex, save.ipo
			local count = type(ipo) == "table" and ipo.count or nil
			if type(p) ~= "table" then
				print(key, "FAIL the save has no pokedex section")
			else
				local sector = type(p.active) == "table" and p.active.sector or nil
				local good = p.v == 1 and count ~= nil and p.run == count and sector == "Software" and p.studio == true
				print(key, good and "OK" or "CHECK", "pokedex v", p.v, "run", p.run, "ipo.count", count, "sector", sector, "studio", p.studio)
			end
			local tasks = save.tasks
			print(key, "tasks", type(tasks) == "table" and ("done " .. tostring(tasks.done) .. ", best chain " .. tostring(tasks.bestChain)) or "none (fine: it is written only once there is something to keep)")
		end
	end
end
```

**K. Output at the end.** No red lines; no new warnings from `IpoClient`, `ShopClient`, `ShopLayout`, `TaskServer`, `TaskClient`, `CompanyServer` or `pokedex`, except the expected run-check line of step I.4. Optional, from docs/STUDIO_SYNC.md (d) step 7: run the DataStore test block of docs/CUSTOMIZE_PR1_NOTES.md (a throwaway store; it removes its own keys). It was never run in Studio.

## 10. Before publishing

1. Paste the check block of docs/STUDIO_SYNC_WORLD.md (e): it must print `OK` (section 7).
2. Paste the hash block (section 6): `ALL OK`.
3. **View > Drafts:** commit every draft.
4. Publish with **Shut down all servers**, never Migrate. This release adds the `pokedex` save section (docs/PUBLISH_RULES.md 2d and section 3).
5. Check **Max Players = 6** afterwards (PUBLISH_RULES section 1).

## 11. Hash tables in the other sync docs that are now stale

These were not edited (each belongs to its own branch's record). Use this file's hashes instead. A later branch changed the same file:

| Doc and section | Stale lines | Was | Now (this file) | Changed by |
|---|---|---|---|---|
| docs/STUDIO_SYNC.md (a), the table | `TycoonCore` | `77ce9c43…`, 34330 | `9607262c…`, 36399 | customize PR 1 (the (d) row) |
| docs/STUDIO_SYNC.md (a), the table | `ShopClient` | `41c98119…`, 28371 | `ff29fe44…`, 59330 | shop-build (docs/STUDIO_SYNC_SHOP.md) |
| docs/STUDIO_SYNC.md (c), the hash block | the `TycoonCore` and `ShopClient` lines | the same two old hashes | as above | as above (this block says `DIFFERENT` for both on a synced Studio) |
| docs/STUDIO_SYNC.md (e), the "Which scripts differ, per branch" table | row `main`: "the one in (a) (`77ce9c43`)" | `main` before Integration 1 | `main` is now Integration 1, with the (d) TycoonCore | Integration 1 |
| docs/STUDIO_SYNC_WORLD.md (a), the table | `TycoonCore` (only after approval): `5a984905…`, 35508 | the patched TycoonCore of `main` at `e3c9e67` | needs `--regen-patch` first: the patch is made for the old TycoonCore | customize PR 1 (TycoonCore changed) |
| docs/STUDIO_SYNC_WORLD.md (a), the line under the table | "TycoonCore on `main` is `77ce9c43...61aa9`, 34330 bytes" | as quoted | `9607262c…`, 36399 | customize PR 1 |

Still correct on this tree: docs/STUDIO_SYNC.md (a) and (c) for the other eight scripts; docs/STUDIO_SYNC.md (d) (all four) and (e) (all three); docs/STUDIO_SYNC_HUD.md (a) and (c) (`IpoClient`); docs/STUDIO_SYNC_SHOP.md (a) and (d) (`ShopLayout`, `ShopClient`); docs/STUDIO_SYNC_WORLD.md (a) and (d) for `WorldArt`, `WorldVisuals`, `IconArt` and `IconVisuals`. (The superseded hashes these docs quote on purpose, such as HUD's `15de6cd4…` and (e)'s `7ee9ad23…`, are labelled as old there.)

## 12. What was checked, and what wasn't

- **Checked (in the `luau` tool, not in Studio):**
  - The hash block of section 6 ran against the real files of this tree with a fake `game` that serves each file as `Source`. Results: all 33 `OK` and `ALL OK: 29 of 29` (also with every last newline dropped, and with one newline added); a one-character change in `TycoonCore` gives `DIFFERENT` for it alone; `CompanyServer` removed gives `MISSING (create a ModuleScript in ServerScriptService)`; `WorldArt` removed gives `MISSING (PASTE LATER: not needed yet)`; `ShopLayout` as a LocalScript gives `WRONG CLASS`; two extra newlines give `DIFFERENT`.
  - The wipe block (A) and the read block (J) ran against a fake DataStore. The wipe removes only `player_-1` and `player_-2` and reports a refusal as `FAIL`. The read prints `OK` for a good section, `CHECK` for `run` above the count, and `FAIL` for a missing section or a refused read.
  - **Run again after the review fixes** (blocks extracted from this very file, real files of `main` at `dbf900b`, `luau` command-line tool): the hash block, all 33 `OK` and `ALL OK: 29 of 29`, also with every last newline dropped and with one added; `TycoonCore` with one character changed: `DIFFERENT` for it alone; `CompanyServer` removed: `MISSING (create a ModuleScript in ServerScriptService)`; `WorldArt` removed: `MISSING (PASTE LATER: not needed yet)` and still `ALL OK`; `ShopLayout` as a LocalScript: `WRONG CLASS`; two extra newlines: `DIFFERENT`; `CompanyServer` holding Studio's default template (an empty table): `DIFFERENT`; `ShopLayout` in the wrong parent: `MISSING` (not flagged as a wrong parent); two scripts of the same name: not detectable (the block asks `FindFirstChild` for one). The table's 33 hashes and sizes against `sha256sum` and `wc -c`, and against Python's `hashlib`: 33 of 33 equal, and equal to the hash block's rows. The wipe block against a fake DataStore holding `player_-1`, `player_-2`, `player_-3`, `player_123456` and `other`: it touched only the store `StartupTycoon_v1` and the keys `player_-1` and `player_-2` (`player_-3`, `player_123456` and `other` stayed), reported a refused `RemoveAsync` as `FAIL` and a missing DataStore as `FAIL`. The read block touched only `GetAsync("player_-1")` and `GetAsync("player_-2")`: `OK` for a good section, `CHECK` for `run` 1 against `ipo.count` 0, `FAIL` for a save without `pokedex`, `FAIL` for a refused read, `no save` for an absent key, and the `tasks` line for both a section and none.
- **Not checked:** anything in Studio. No command-bar run, no playtest, no MCP; the Studio Explorer was never seen, so which scripts already exist there is unknown (hence step 1.3). Whether `RemoveAsync` and `GetAsync` work from the command bar in edit mode was not tested here (docs/CUSTOMIZE_PR1_NOTES.md's block relies on the same).
- **Counted:** the Ownership table in `CONTRIBUTING.md` has **68 rows** on `main` at `dbf900b` (lines 91 to 158, no duplicate script). That is exactly the union of the rows of `integration-1`, `hud-cash`, `task-needs-desk`, `world-icons-pass` and `shop-build`. With this doc's own claim row it has 69 while this branch is open. A review said 67: that count does not match the files.

## 13. Follow-ups (found while checking this doc; not done here)

Both files belong to other claims and this change was docs-only, so neither was edited:

1. **`README.md`, the file table** has no rows for `WorldArt.lua`, `WorldVisuals.lua`, `IconArt.lua` and `IconVisuals.lua` (the four PASTE LATER modules), nor for `tools/hud_test.py`, `tools/world_test.py` and `tools/icon_test.py`. (It has `tools/economy_sim.py`, `tools/daily_test.py` and `tools/shop_ux_test.py`.) Claim `README.md`, add the rows.
2. **`docs/STUDIO_SYNC.md` line 238** says to follow "the PR 1 order in docs/PUBLISH_RULES.md 2c". The PR 1 sync order is under **2b** (`docs/PUBLISH_RULES.md` line 50, "Studio sync order for PR 1", inside `## 2b`); 2c is the plot visuals follow-up. Claim `docs/STUDIO_SYNC.md`, change `2c` to `2b`.
