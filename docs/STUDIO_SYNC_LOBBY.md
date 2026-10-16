# Studio sync: lobby and garages

The Studio steps of the lobby and garages PRs (docs/LOBBY_GARAGE_PROPOSAL.md section 5), one section per PR. The repo is the official copy; Studio must match it (CONTRIBUTING.md, "Keeping Studio and the repo in sync").

## L0. Markers (no change)

**What changed:** `TycoonCore.lua` only, and only comments. Three comment lines in `onPlayerAdded`: a note, then `-- CLAIMLOAD-START` just above `local saved, ok = load(player)`, and `-- CLAIMLOAD-END` just below `data.ready = true`. The code between them (lines 774-863 on `main` at `99eed7b`) is unchanged, byte for byte; PR L3 moves it into `claimGarage`. Nothing a player sees or saves changes. `tools/lobby_test.py` checks all of it.

### (a) The script to paste

| Script | Class, place | State | SHA-256 | Bytes |
|---|---|---|---|---|
| `TycoonCore` | Script, ServerScriptService | changed | `58a3cb9d2c994afec2eabea0791d5bdb01950290362b16cdcef02c265d97695e` | 36551 |

Before L0, `main` (`99eed7b`) had `9607262c64d762cc15644a8ab3d85821cfaba2654879a9018210e1237679def2`, 36399 bytes.

### (b) Steps

1. Open the place in Studio (Team Create). Make sure nobody else has claimed `TycoonCore` (CONTRIBUTING.md, Ownership).
2. In the repo, open `TycoonCore.lua`, select all (**Cmd+A**, **Ctrl+A** on Windows) and copy.
3. In Studio's Explorer, double-click **ServerScriptService > TycoonCore**, select all and paste over it.
4. **View > Drafts**: commit the TycoonCore draft.
5. Run the hash block (c) in **View > Command Bar**. The last line must say `ALL OK`.
6. Playtest (**F5**). Your save loads as before: same Cash, upgrades, employees and room, and no red errors in the Output. Stop the playtest.

### (c) Hash check (command bar)

Paste the whole block into **View > Command Bar** and press Enter. It changes nothing. It prints `OK` or `DIFFERENT` (paste the file again), `MISSING` or `WRONG CLASS`, then `ALL OK` or `NOT YET`. Studio may drop the last newline or add one; both are accepted (the same rule as docs/STUDIO_SYNC_MASTER.md section 6, whose `sha256` this block copies).

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

-- STUDIO_SYNC_LOBBY L0 hash check: TycoonCore with the CLAIMLOAD markers. Changes nothing.
local WANT = {
	{ "TycoonCore", "Script", "ServerScriptService", "58a3cb9d2c994afec2eabea0791d5bdb01950290362b16cdcef02c265d97695e", 36551 },
}
local problems = {}
for _, w in ipairs(WANT) do
	local name, class, place, hash, bytes = w[1], w[2], w[3], w[4], w[5]
	local folder = game:GetService(place)
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
print(#problems == 0 and "ALL OK: TycoonCore matches the repo (lobby L0)" or ("NOT YET: fix " .. table.concat(problems, ", ")))
```

After PR L1, TycoonCore changed again: this block then says `DIFFERENT` for it. Use the L1 section's block (c) below.

### (d) Other sync docs whose TycoonCore row is now stale

docs/STUDIO_SYNC_MASTER.md (section 3's table row 21 and the `TycoonCore` line of its section 6 block) and docs/STUDIO_SYNC.md still give `main`'s old TycoonCore (`9607262c…`, 36399 bytes). After L0 their block says `DIFFERENT` for TycoonCore on a synced Studio. Use (c) for TycoonCore. L0 does not edit those docs.

### (e) What was checked, and what wasn't

- `python3 tools/lobby_test.py` checks the markers, the block against `99eed7b`, the rest of the file, this table and this block (run in Luau against a fake Studio). `tools/daily_test.py`, `hud_test.py`, `world_test.py`, `icon_test.py` and `shop_ux_test.py` pass unchanged.
- **Not done:** the paste, the hash block in real Studio and the playtest (steps 3 to 6). Nobody has run them for L0 yet.

## L1. Plot frame (nothing visible)

**What changed:** five scripts, and nothing a player can see, save or earn. Every place that put something at "plot center + offset" now puts it through `plotFrame(slot)`, the garage's center turned by its quarter turn, and every turn is 0 for now (`GARAGE_TURNS = { 0, 0, 0, 0, 0, 0 }` in TycoonCore). So every Floor, room, prop, plain block, sign, hire spot, incubator, employee and spawn landing is exactly where it was on `main`. PR L4 sets real turns for the ring. In detail:

- **TycoonCore:** `GARAGE_TURNS` next to `MAX_PLOTS`; `plotFrame` right after `plotCenter` (which is unchanged); `makePart` places a part by CFrame when given one; the plain upgrade block, the next-upgrade sign, the spawn landing and the `Floor` use the frame; IpoServer and EmployeeServer get `plotFrame` in their `core` instead of `plotCenter`. The code between the CLAIMLOAD markers is unchanged (the room line keeps `plotCenter(slot)`).
- **PlotVisuals:** the room takes the garage's turn from the `Floor`'s CFrame (`newPlot`), and `check` measures every part in the garage's frame.
- **EmployeeServer:** hire spots, the facing and the incubators use the frame; each employee model gets a `Facing` attribute (math.pi at turn 0, as before).
- **IpoServer:** the IPO sign uses the frame.
- **EmployeeClient:** a walker starts at the model's `Facing` (math.pi when it is missing, as before); the wander stays in world axes.

### (a) The scripts to paste

| Script | Class, place | State | SHA-256 | Bytes |
|---|---|---|---|---|
| `TycoonCore` | Script, ServerScriptService | changed | `0a9adf5fc6403d2fa93142853515e2317b48e352e3b2243d1cdc1189ca437956` | 37869 |
| `EmployeeServer` | ModuleScript, ServerScriptService | changed | `a617be83f5f10990ff258207b293a60fcff4361a60ea2907ac34481bc64eceb2` | 32067 |
| `IpoServer` | ModuleScript, ServerScriptService | changed | `536db7c6d0c3ddc54d9d502cb12cbebe18dd0eadf727f65fa0dde3d8cecd4135` | 17405 |
| `PlotVisuals` | ModuleScript, ServerScriptService | changed | `c0a636a694e1a3d8ce140c6346557b5839e70f9d3fd19a08b54874e0e4ba96e0` | 27218 |
| `EmployeeClient` | LocalScript, StarterPlayerScripts | changed | `46e43c8bbf887f1e5ed4490ed4331d81d72fdefba08dd89da7a7c22ed3bd9c08` | 35728 |

Before L1, `main` (`c943196`) had: `TycoonCore` `58a3cb9d2c994afec2eabea0791d5bdb01950290362b16cdcef02c265d97695e`, 36551 bytes; `EmployeeServer` `65fefebf56b21d85c87e773a9dc8734754c716e29d693cb1fd15b79381894597`, 31745 bytes; `IpoServer` `96e8f073d2039dd1201cbc23137b5730cc8783644bc0085cdd5e7cd3a29e2e52`, 17377 bytes; `PlotVisuals` `2e10736f60b86590f0bced98eb3d8d0e9b0264108cdc9cd02f68dd8b5651ba89`, 26508 bytes; `EmployeeClient` `4aa4faa9cb06f166179a73fe6ee83b11b919c3a650c758dffcb615a98e641152`, 35379 bytes.

### (b) Steps

1. Open the place in Studio (Team Create). Make sure nobody else has claimed these five scripts (CONTRIBUTING.md, Ownership).
2. For each script in (a): in the repo, open the `.lua` file, select all (**Cmd+A**, **Ctrl+A** on Windows) and copy; in Studio's Explorer, double-click the script with the same name (`TycoonCore`, `EmployeeServer`, `IpoServer` and `PlotVisuals` in **ServerScriptService**; `EmployeeClient` in **StarterPlayer > StarterPlayerScripts**), select all and paste over it.
3. **View > Drafts**: commit the five drafts.
4. Run the hash block (c) in **View > Command Bar**. The last line must say `ALL OK`.
5. Playtest (**F5**): **nothing moved.** You land in the middle of your garage facing the front signs; the room, the props, the green next-upgrade sign, the gold IPO sign, the incubators and your employees (facing the front, then wandering) are where they were; same Cash and upgrades; no red errors in the Output. Stop the playtest.

### (c) Hash check (command bar)

Paste the whole block into **View > Command Bar** and press Enter. It changes nothing. It prints `OK` or `DIFFERENT` (paste the file again), `MISSING` or `WRONG CLASS` for each script, then `ALL OK` or `NOT YET`. Studio may drop the last newline or add one; both are accepted (the same rule as docs/STUDIO_SYNC_MASTER.md section 6, whose `sha256` this block copies).

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

-- STUDIO_SYNC_LOBBY L1 hash check: the five scripts of the plot frame. Changes nothing.
local function folderOf(place)
	if place == "StarterPlayerScripts" then
		return game:GetService("StarterPlayer"):FindFirstChild("StarterPlayerScripts")
	end
	return game:GetService(place)
end
local WANT = {
	{ "TycoonCore", "Script", "ServerScriptService", "0a9adf5fc6403d2fa93142853515e2317b48e352e3b2243d1cdc1189ca437956", 37869 },
	{ "EmployeeServer", "ModuleScript", "ServerScriptService", "a617be83f5f10990ff258207b293a60fcff4361a60ea2907ac34481bc64eceb2", 32067 },
	{ "IpoServer", "ModuleScript", "ServerScriptService", "536db7c6d0c3ddc54d9d502cb12cbebe18dd0eadf727f65fa0dde3d8cecd4135", 17405 },
	{ "PlotVisuals", "ModuleScript", "ServerScriptService", "c0a636a694e1a3d8ce140c6346557b5839e70f9d3fd19a08b54874e0e4ba96e0", 27218 },
	{ "EmployeeClient", "LocalScript", "StarterPlayerScripts", "46e43c8bbf887f1e5ed4490ed4331d81d72fdefba08dd89da7a7c22ed3bd9c08", 35728 },
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
print(#problems == 0 and "ALL OK: the five scripts match the repo (lobby L1)" or ("NOT YET: fix " .. table.concat(problems, ", ")))
```

### (d) Other sync docs whose rows are now stale

docs/STUDIO_SYNC_MASTER.md (section 3's table and section 6's block) and docs/STUDIO_SYNC.md still give `main`'s older files for these five scripts, and L0's block (c) above gives L0's TycoonCore. After L1 they say `DIFFERENT` for them on a synced Studio. Use (c) of this section for the five scripts. L1 does not edit those docs.

### (e) What was checked, and what wasn't

- `python3 tools/daily_test.py` runs the real code of the five scripts (and PlotArt, CompanyConfig) in a fake Roblox with real rotations: at 0 degrees every position is `main`'s, exactly (Floor, the five rooms with the six props, plain blocks, both signs, 13 hires and their facing, five incubators, the landing); at 90, 180 and 270 degrees each is the 0-degree build turned, and `PlotVisuals.check` finds no problem in the turned rooms; `plotZones` and `CompanyConfig.checkPlacement` give the same answers at every turn. Source pins list every place a garage position is computed, and the employees' wander stays in world axes. 28 mutants, each caught by its named check.
- `python3 tools/lobby_test.py` checks that the CLAIMLOAD block is still `99eed7b`'s byte for byte, that TycoonCore outside it is `99eed7b`'s plus L1's ten listed edits, and this table and block (run in Luau against a fake Studio).
- **Not done:** the paste, the hash block in real Studio and the playtest (steps 2 to 5). No garage was turned in Studio: a real turn at 90, 180 or 270 degrees is only tested in the fake.

## Lobby all (L2 to L5)

The one Studio list for branch `lobby-all`: the permanent garages and their five kit buildings (L2), the claim behind `LobbyConfig.ClaimEnabled` (L3), the ring around the plaza (L4). Written on branch `lobby-all` (docs/LOBBY_ALL_PROGRESS.md has what each stage built). Nothing here touches Roblox by itself.

**Who does it, and where.** A local VS Code session of Claude Code with the **Roblox Studio MCP** connected, together with the owner, on the **published place**: in Studio, **File > Open from Roblox** > *Build your Startup!* (PlaceId **86395856666175**). Never a local `.rbxl` file. Save with **File > Save to Roblox**, **never Publish**: publishing is the owner's own step, later (section 10 and docs/PUBLISH_RULES.md).

**What ships:** `LobbyConfig.ClaimEnabled = false` (owner decision 9). With it off nothing moves for live players: every joining player is sent into the first free garage of today's row, as before; what is new is the closed building around each garage (the five kit buildings, from the Garage to Big Corporate), the furniture inside, and a Free garage showing today's new-player room. The claim, the plaza, the ring and the banner appear only when the switch is turned on (section 10).

**No save change.** No new save section, no DataStore change, no new remote. The rollback floor (docs/PUBLISH_RULES.md section 2) is unchanged.

### 1. Before you start

1. **Pull:** `git fetch`, then branch `lobby-all` (or `main` once its pull request is merged), in a folder no other session uses (`git worktree add ../studio-lobby origin/lobby-all`).
2. **Studio:** File > Open from Roblox > *Build your Startup!*. **Game Settings > Security > Enable Studio Access to API Services: ON** (without it saves can't load in a playtest).
3. **MCP:** `get_studio_state` says the place is open in **Edit** mode (not a playtest); `list_roblox_studios` shows one Studio. If two are open, close the other one.
4. **Everything else first:** this section covers only what `lobby-all` changes. Every other script must already match `main` (docs/STUDIO_SYNC_MASTER.md, then this file's L0 and L1 sections). The hash block (section 4) also checks the four L1 scripts, so one run tells you.

### 2. Scripts to create by hand first

The Studio MCP can't create a script inside a service (docs/STUDIO_SYNC_MASTER.md section 2), so create these by hand: in the Explorer, hover the parent, click **+**, pick the class, press **F2** and type the exact name (capitals included). **`LobbyConfig` first:** TycoonCore and LobbyClient wait for it with no time limit (a playtest without it hangs the server script).

| Name | Class | Parent |
|---|---|---|
| `LobbyConfig` | ModuleScript | ReplicatedStorage |
| `PlotBuilding` | ModuleScript | ServerScriptService |
| `PlotBuildingVisuals` | ModuleScript | ServerScriptService |
| `BuildingClient` | LocalScript | StarterPlayer > StarterPlayerScripts |
| `LobbyClient` | LocalScript | StarterPlayer > StarterPlayerScripts |

`WorldArt` and `WorldVisuals` (ModuleScript, ServerScriptService) may already exist from the world preview (docs/STUDIO_SYNC_WORLD.md): create them only if the hash block says `MISSING`. TycoonCore uses them only with the claim on, inside pcall.

The 36 kit models must already be in **ReplicatedStorage > KitModels** (docs/KIT_MODELS.md; section 5 checks them). Without them every building is built from Parts, with one warning in the Output: the game works either way.

### 3. The list (paste in any order)

Paste each one the same way: open the `.lua` file, select all, copy; in Studio double-click the script, select all, paste (or, with the MCP, write the file's text into the script with its script editing tool). Game scripts don't run in Edit mode, so the order of pasting doesn't matter; what matters is that every script exists, with the right source, before the first playtest.

| Script | Class, place | State | SHA-256 | Bytes |
|---|---|---|---|---|
| `TycoonCore` | Script, ServerScriptService | changed | `3874158c053e0a54ec49c6c82cb453001800122504a9a40c5da61b210111e400` | 52831 |
| `ShopClient` | LocalScript, StarterPlayerScripts | changed | `14561889351652525f07050b9ee4c7101ec9bccd296b1be7498b8fae81028cf8` | 60314 |
| `PlotBuilding` | ModuleScript, ServerScriptService | new | `f4097e603565fa438d63afbcb95928e9c95e3e0c74e84d5110f2aa12fc5deed1` | 34099 |
| `PlotBuildingVisuals` | ModuleScript, ServerScriptService | new | `0f24751a37a961e682a1475957162db3661337ac130cc472ca0c647605b8eedd` | 25169 |
| `BuildingClient` | LocalScript, StarterPlayerScripts | new | `450068cb37007a70e0a7ba828a06503690c8f71b896141c79874be3d92ee94ec` | 9408 |
| `LobbyConfig` | ModuleScript, ReplicatedStorage | new | `3d8890c670d89f9829a469866f75d6aa9e765880168c81e6364271fe1725789e` | 6184 |
| `LobbyClient` | LocalScript, StarterPlayerScripts | new | `4e96b6650a686c6dfc1ae9670f5c51ef36512e32e2f8a7459305c069830a2c6a` | 4391 |
| `ShopServer` | ModuleScript, ServerScriptService | changed | `c254a6894e187b0bcbae3a1d5621ba02264e2ad28b1e7b3e4715bfdab74f3a48` | 33640 |
| `IpoClient` | LocalScript, StarterPlayerScripts | changed | `ddc1d9614a203207fbd3fd0bc2d8d493b6289bf18f29ce7c78b765d6bd9c21da` | 42081 |
| `WorldArt` | ModuleScript, ServerScriptService | changed | `0a9690736ed8a7e60cc4824f12d6d78a04e686b633f976e17a22517c2fc8f558` | 15266 |
| `WorldVisuals` | ModuleScript, ServerScriptService | changed | `0d2fb53941e4eaf30db7b43e3b66d55f23e5977aad8c91f077e012b12518cd05` | 55999 |
| `EmployeeServer` | ModuleScript, ServerScriptService | as on main | `a617be83f5f10990ff258207b293a60fcff4361a60ea2907ac34481bc64eceb2` | 32067 |
| `IpoServer` | ModuleScript, ServerScriptService | as on main | `536db7c6d0c3ddc54d9d502cb12cbebe18dd0eadf727f65fa0dde3d8cecd4135` | 17405 |
| `PlotVisuals` | ModuleScript, ServerScriptService | as on main | `c0a636a694e1a3d8ce140c6346557b5839e70f9d3fd19a08b54874e0e4ba96e0` | 27218 |
| `EmployeeClient` | LocalScript, StarterPlayerScripts | as on main | `46e43c8bbf887f1e5ed4490ed4331d81d72fdefba08dd89da7a7c22ed3bd9c08` | 35728 |

"as on main" = unchanged since lobby L1; if the hash block says `DIFFERENT` for one of them, paste `main`'s file (docs/STUDIO_SYNC_LOBBY.md section L1).

If the place uses Team Create: **View > Drafts**, commit every draft before the hash block (an uncommitted draft is not saved). Never commit a draft of `LobbyConfig` with `ClaimEnabled = true` (section 9 b).

### 4. Hash check (command bar)

Paste the whole block into **View > Command Bar** and press Enter (with the MCP: run it with `execute_luau`). It changes nothing. It prints `OK`, `DIFFERENT` (paste the file again), `MISSING` (create the script, section 2) or `WRONG CLASS` for each script, then `ALL OK` or `NOT YET`. Studio may drop the last newline or add one; both are accepted (the `sha256` is docs/STUDIO_SYNC_MASTER.md section 6's, character for character).

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

-- STUDIO_SYNC_LOBBY Lobby all hash check: every script lobby-all creates or changes. Changes nothing.
local function folderOf(place)
	if place == "StarterPlayerScripts" then
		return game:GetService("StarterPlayer"):FindFirstChild("StarterPlayerScripts")
	end
	return game:GetService(place)
end
local WANT = {
	{ "TycoonCore", "Script", "ServerScriptService", "3874158c053e0a54ec49c6c82cb453001800122504a9a40c5da61b210111e400", 52831 },
	{ "ShopClient", "LocalScript", "StarterPlayerScripts", "14561889351652525f07050b9ee4c7101ec9bccd296b1be7498b8fae81028cf8", 60314 },
	{ "PlotBuilding", "ModuleScript", "ServerScriptService", "f4097e603565fa438d63afbcb95928e9c95e3e0c74e84d5110f2aa12fc5deed1", 34099 },
	{ "PlotBuildingVisuals", "ModuleScript", "ServerScriptService", "0f24751a37a961e682a1475957162db3661337ac130cc472ca0c647605b8eedd", 25169 },
	{ "BuildingClient", "LocalScript", "StarterPlayerScripts", "450068cb37007a70e0a7ba828a06503690c8f71b896141c79874be3d92ee94ec", 9408 },
	{ "LobbyConfig", "ModuleScript", "ReplicatedStorage", "3d8890c670d89f9829a469866f75d6aa9e765880168c81e6364271fe1725789e", 6184 },
	{ "LobbyClient", "LocalScript", "StarterPlayerScripts", "4e96b6650a686c6dfc1ae9670f5c51ef36512e32e2f8a7459305c069830a2c6a", 4391 },
	{ "ShopServer", "ModuleScript", "ServerScriptService", "c254a6894e187b0bcbae3a1d5621ba02264e2ad28b1e7b3e4715bfdab74f3a48", 33640 },
	{ "IpoClient", "LocalScript", "StarterPlayerScripts", "ddc1d9614a203207fbd3fd0bc2d8d493b6289bf18f29ce7c78b765d6bd9c21da", 42081 },
	{ "WorldArt", "ModuleScript", "ServerScriptService", "0a9690736ed8a7e60cc4824f12d6d78a04e686b633f976e17a22517c2fc8f558", 15266 },
	{ "WorldVisuals", "ModuleScript", "ServerScriptService", "0d2fb53941e4eaf30db7b43e3b66d55f23e5977aad8c91f077e012b12518cd05", 55999 },
	{ "EmployeeServer", "ModuleScript", "ServerScriptService", "a617be83f5f10990ff258207b293a60fcff4361a60ea2907ac34481bc64eceb2", 32067 },
	{ "IpoServer", "ModuleScript", "ServerScriptService", "536db7c6d0c3ddc54d9d502cb12cbebe18dd0eadf727f65fa0dde3d8cecd4135", 17405 },
	{ "PlotVisuals", "ModuleScript", "ServerScriptService", "c0a636a694e1a3d8ce140c6346557b5839e70f9d3fd19a08b54874e0e4ba96e0", 27218 },
	{ "EmployeeClient", "LocalScript", "StarterPlayerScripts", "46e43c8bbf887f1e5ed4490ed4331d81d72fdefba08dd89da7a7c22ed3bd9c08", 35728 },
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
print(#problems == 0 and ("ALL OK: the " .. #WANT .. " scripts match the repo (lobby-all)") or ("NOT YET: fix " .. table.concat(problems, ", ")))
```

### 5. KitModels check (command bar)

Checks **ReplicatedStorage.KitModels** against the manifest in `PlotBuilding` (copied from docs/KIT_MODELS.md): the 36 keys, each a Model, its `KitSize` within 0.05 of the manifest's size, its MeshParts' `Role` attributes exactly the manifest's roles, nothing but MeshParts inside. Paste PlotBuilding and PlotBuildingVisuals first. It changes nothing.

```lua
-- STUDIO_SYNC_LOBBY kit check: ReplicatedStorage.KitModels against PlotBuilding.KitManifest. Changes nothing.
local SSS = game:GetService("ServerScriptService")
local pbScript, pbvScript = SSS:FindFirstChild("PlotBuilding"), SSS:FindFirstChild("PlotBuildingVisuals")
local ok1, PB = pcall(function() return require(pbScript:Clone()) end)
local ok2, PBV = pcall(function() return require(pbvScript:Clone()) end)
if not (ok1 and ok2) then
	print("NOT YET: paste PlotBuilding and PlotBuildingVisuals first (" .. tostring(ok1 and PBV or PB) .. ")")
else
	local problems = PBV.checkKit(game:GetService("ReplicatedStorage"):FindFirstChild("KitModels"), PB.KitManifest)
	local count = 0
	for _ in pairs(PB.KitManifest) do count += 1 end
	for _, text in ipairs(problems) do
		print("WRONG: " .. text)
	end
	print(#problems == 0 and ("KIT OK: " .. count .. " models, sizes within 0.05, roles as in docs/KIT_MODELS.md")
		or ("KIT NOT OK: " .. #problems .. " problem(s) above"))
end
```

`KIT OK` is what you want. `KIT NOT OK`: re-import the kit (docs/KIT_MODELS.md, "Re-importing"), run this again. A key that stays wrong is built from Parts in the game (one warning in the Output), so nothing breaks.

### 6. Kit front check (command bar)

The kit's files face +Z; whether Studio's importer kept that is **not verified**, so one constant, `PlotBuilding.KIT_FRONT_TURN` (0 or 180), turns every kit model the right way. This block builds a **Chair** and a **Computer** from the kit with the game's own builder, at x 0, z -80 (an empty spot south of the VIP Lounge), facing +Z, and a red **STAND HERE** pad 7 studs in front of them, where a player would sit or read the screen. It changes nothing else.

```lua
-- STUDIO_SYNC_LOBBY kit front check: a Chair and a Computer from KitModels, facing a red STAND HERE pad. Delete KIT_FRONT_CHECK after.
local SSS = game:GetService("ServerScriptService")
local PB = require(SSS:FindFirstChild("PlotBuilding"):Clone())
local PBV = require(SSS:FindFirstChild("PlotBuildingVisuals"):Clone())
local kit = game:GetService("ReplicatedStorage"):FindFirstChild("KitModels")
local old = workspace:FindFirstChild("KIT_FRONT_CHECK")
if old then old:Destroy() end
local folder = Instance.new("Model")
folder.Name = "KIT_FRONT_CHECK"
local frame = CFrame.new(0, 0.5, -80) -- like a garage's center: the pieces stand on the ground in front of it
local _, chairKit = PBV.buildPiece(folder, frame, PB, 2, { name = "FrontChair", key = "Chair", x = -4, y = -1, z = 0, turn = 0 }, kit)
local _, computerKit = PBV.buildPiece(folder, frame, PB, 2, { name = "FrontComputer", key = "Computer", x = 4, y = -1, z = 0, turn = 0 }, kit)
local pad = Instance.new("Part")
pad.Name = "STAND_HERE"
pad.Size = Vector3.new(4, 0.2, 4)
pad.CFrame = frame * CFrame.new(0, -0.4, 7) -- on the ground (the Baseplate's top is y 0)
pad.Color = Color3.fromRGB(220, 40, 40)
pad.Anchored, pad.CanCollide = true, false
pad.Parent = folder
folder.Parent = workspace
print(string.format("Built KIT_FRONT_CHECK (Chair from the kit: %s, Computer from the kit: %s), KIT_FRONT_TURN = %d.",
	tostring(chairKit), tostring(computerKit), PB.KIT_FRONT_TURN))
print("Look from the red STAND HERE pad: the Chair's seat and the Computer's screen must face you. Then delete Workspace.KIT_FRONT_CHECK.")
```

- **Both face the pad:** `KIT_FRONT_TURN` is right. Write "kit front: checked, KIT_FRONT_TURN = 0" in docs/LOBBY_ALL_PROGRESS.md.
- **Both face away:** the importer turned the models around. In the repo, on a branch, set `PlotBuilding.KIT_FRONT_TURN = 180` (tools/building_test.py tests both values), paste PlotBuilding, run the hash block and this check again.
- **"from the kit: false":** the kit is missing (section 5); this check then only shows the Parts versions, which always face the right way.
- **Delete `Workspace.KIT_FRONT_CHECK`** afterwards (select it, Delete), before any save.

### 7. The SpawnLocation (moved by hand, only with the claim on)

With the claim on, players spawn on the plaza: the SpawnLocation must stand at its center, **(0, 0.5, 175)** (docs/LOBBY_GARAGE_PROPOSAL.md L4). **Move it only when you turn the claim on (section 10), not now:** with the claim off the garages stand in today's row, and (0, 175) is between garages 3 and 4, inside their biggest buildings. If it is not moved, the claim's plaza fallback puts every first spawn on the plaza anyway (it is only a safety net). To move it: Explorer > **Workspace > SpawnLocation**, Properties > **Position** `0, 0.5, 175` (the size stays 12 x 1 x 12). This prints where it is:

```lua
-- STUDIO_SYNC_LOBBY spawn check: where the SpawnLocation stands. Changes nothing.
local spawn = workspace:FindFirstChild("SpawnLocation")
if not spawn then
	print("NO SpawnLocation in the Workspace")
else
	local p = spawn.Position
	local plaza = math.abs(p.X - 0) < 0.01 and math.abs(p.Y - 0.5) < 0.01 and math.abs(p.Z - 175) < 0.01
	local row = math.abs(p.X + 1) < 0.01 and math.abs(p.Y - 0.5) < 0.01 and math.abs(p.Z + 1) < 0.01
	print(string.format("SpawnLocation at %.2f, %.2f, %.2f: %s", p.X, p.Y, p.Z,
		plaza and "ON THE PLAZA (right for ClaimEnabled = true)" or row and "WHERE IT ALWAYS WAS (right for ClaimEnabled = false)" or "SOMEWHERE ELSE: put it back"))
end
```

### 8. Before the playtest

1. The hash block (section 4) says `ALL OK`. 2. The kit check (section 5) says `KIT OK` (or you know the buildings will be Parts). 3. `Workspace.KIT_FRONT_CHECK` is deleted. 4. `LobbyConfig.ClaimEnabled` is `false` in Studio.

### 9. Playtests

**(a) One player, the claim off (as it ships).** Press **F5**.
1. The Output shows no red error. At most one warning that starts with `Plot buildings:` (only if KitModels is missing or a model is wrong).
2. You land in your garage, as before, inside the closed building of your funding stage (a new save: the Garage, brick with the orange roll-up door overhead). Same Cash, upgrades, employees and room as before.
3. **Walk every doorway at every stage:** open the shop's **Debug** tab, press **"Building: next stage"** (Studio only, never saved): the room and the building change to the next stage. For each of the five: walk out through the door to the plaza side and back in; the shell fades when you step on the 3.5-stud apron in front of the door and comes back outside; the doorway never blocks you (the solid opening is at least 9 x 9); walk around the furniture band (stages 2 to 5) and see the furniture while inside.
4. **The camera never pulls in:** with the default camera, stand inside facing each wall, and outside close to each wall, and walk in and out of the door. If the camera jumps in front of you anywhere, stop and note where (the solid walls are invisible and should never stop it).
5. **Reset** (Esc > Reset Character) inside and outside the building: you respawn in your garage (OWNER DEFAULT), never stuck in a wall.
6. Leave the playtest. In a second F5 the building is your real stage again (the Debug stage is not saved).

**(b) The claim on, in Studio only, with 2 and then 3 players.** In Studio, open **ReplicatedStorage > LobbyConfig**, set `LobbyConfig.ClaimEnabled = true` (do **not** commit this draft and do not save the place with it). Then **Test > Clients and Servers**, **2** players, Start:
1. Each player spawns on the plaza (the fallback moves them there if the SpawnLocation was not moved): a banner says "Walk to a free garage to start your company", a green "▼ FREE" marker floats over the nearest free garage's claim post. No `Infinite yield` warning in either client's Output.
2. Player 1 walks to a garage's claim post and holds **Claim garage** (0.5 s): the garage shows "Moving in...", then their name; the banner goes; their save loads (Cash, upgrades). The Robux buttons in the shop said "Claim garage" before and now show prices.
3. Player 2 holds the same garage's prompt: no prompt (it is off for a taken garage). Player 2 claims another garage.
4. Close player 1's window (they leave): their garage shows "Closing..." while their save runs, then the Free room and the FREE sign come back. (Studio's test players can't rejoin as the same account; that case, "Your last visit is still saving", is tested by tools/lobby_test.py.)
5. Again with **3** players: a third joins while a garage is closing; everyone gets a garage; the garages around the plaza face it (west, north and east).
6. Walk every doorway of a west, a north and an east garage with "Building: next stage" (turned garages exist only with the claim on).
7. **Test > Device**, a phone (for example iPhone SE, then a landscape phone): the banner sits under the HUD and the valuation bar, readable, not covering a button.
8. Stop. Set `ClaimEnabled` back to **false**, then run the hash block: `LobbyConfig` must say `OK` again.

**(c) Phone sizes.** Test > Device with the claim off: the HUD, the valuation bar and the shop as before.

### 10. Turning the claim on later (a publish, by the owner)

`LobbyConfig` is a ModuleScript: servers read it when they start, so the switch is not live. When the owner decides:
1. On a branch: set `LobbyConfig.ClaimEnabled = true` in `LobbyConfig.lua`; run `tools/lobby_test.py`, `world_test.py` and `building_test.py`; pull request, merge.
2. In Studio: paste `LobbyConfig`, run the hash block; **move the SpawnLocation** to (0, 0.5, 175) (section 7, the check says ON THE PLAZA); playtest 9 (b).
3. File > Save to Roblox; then publish with **Shut down all servers** (docs/PUBLISH_RULES.md): old servers keep the old flow until they restart.
4. To turn it off again: the same with `false`, and the SpawnLocation back to (-1, 0.5, -1).

### 11. Creator Hub: Max Players = 6

docs/PUBLISH_RULES.md section 1. Nothing in the code reads Max Players; a server above 6 kicks the 7th player, and TycoonCore warns at startup ("Max Players is N but there are 6 garages"). After **every** publish:
1. Creator Hub > the experience > **Places** > the start place > **Access** tab: **Max Visitor Count = 6** (Studio: Game Settings > Places).
2. Same tab, **Social Slots**: Roblox optimized (ROADMAP's before-publish list (e)); if live servers log cap kicks, switch to the option that fills to the maximum.
3. Other places in the universe: list them; each one players can reach gets the same value.
4. Reopen the setting after the publish and check it reads 6.

### 12. Saving

Delete `Workspace.KIT_FRONT_CHECK` if it is still there. Commit every draft (Team Create). **File > Save to Roblox.** Never Publish in this session.

### 13. What was checked, and what wasn't

- **Checked outside Studio** (Luau 0.742, the real files in fake Roblox): every suite (docs/LOBBY_ALL_PROGRESS.md has the counts): the five buildings at four turns with the kit, with the kit imported turned around and with no kit; the real BuildingClient; the whole real TycoonCore with the claim on and off (joins, claims, leaves, rejoins during a save, failed loads, the cap, receipts); the real LobbyClient; the ring world. This section's hash block, kit check and kit front check were run in Luau against fakes (tools/lobby_test.py and tools/building_test.py).
- **Not checked (Studio only):** anything on a screen; the kit's real front direction (section 6); that MeshParts stretch as computed; Roblox's camera with invisible solid walls; ProximityPrompt's own distance check; StreamingEnabled and `Persistent` from a script; whether Roblox limits a `ProcessReceipt` that waits for a claim; frame rate on a phone; Max Players in Creator Hub.
