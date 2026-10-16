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

Branch `lobby-all` (docs/LOBBY_ALL_PROGRESS.md has the stages). This section is the one Studio list for everything the branch changes; it is finished in L5. Until then the table and the hash block below are kept current at every stage (tools/lobby_test.py checks them against the real files).

### Scripts

| Script | Class, place | State | SHA-256 | Bytes |
|---|---|---|---|---|
| `TycoonCore` | Script, ServerScriptService | changed | `d652849c344623cc26a0b327b24eac1fac17ec087ebc98407d3916dbdf9e2859` | 42494 |
| `ShopClient` | LocalScript, StarterPlayerScripts | changed | `fe613ef07803ce0d9002b3af4c1e99d32fd5ec4594ccb2530721210d73d21124` | 59523 |
| `PlotBuilding` | ModuleScript, ServerScriptService | new | `f4097e603565fa438d63afbcb95928e9c95e3e0c74e84d5110f2aa12fc5deed1` | 34099 |
| `PlotBuildingVisuals` | ModuleScript, ServerScriptService | new | `a9a6c414d4d256b4c3bd14866a5a4c9e42c6a92d9ac3abe843a974ba55beb37a` | 24058 |
| `BuildingClient` | LocalScript, StarterPlayerScripts | new | `450068cb37007a70e0a7ba828a06503690c8f71b896141c79874be3d92ee94ec` | 9408 |

### Steps so far (L2; L5 replaces this with the full list)

1. **ServerScriptService:** create two ModuleScripts named exactly `PlotBuilding` and `PlotBuildingVisuals` and paste the files of the same names. **StarterPlayer > StarterPlayerScripts:** create a LocalScript named exactly `BuildingClient` and paste `BuildingClient.lua` (it moved from docs/studio_scripts to the repo root).
2. Paste `TycoonCore.lua` and `ShopClient.lua` over their scripts. **View > Drafts**: commit every draft. Run the hash block below until it says `ALL OK`.
3. `ReplicatedStorage.KitModels` must already hold the 36 kit models (docs/KIT_MODELS.md). Without it every building is built from Parts (one warning in the Output), which also works.
4. Playtest (F5): your garage stands in a closed building; walk in and out of the door; the shell fades when you are inside; the Debug tab's "Building: next stage" shows the five buildings in turn.

### Hash check (command bar)

Paste the whole block into **View > Command Bar** and press Enter. It changes nothing. It prints `OK`, `DIFFERENT` (paste the file again), `MISSING` (create the script) or `WRONG CLASS` for each script, then `ALL OK` or `NOT YET`. Studio may drop the last newline or add one; both are accepted.

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
	{ "TycoonCore", "Script", "ServerScriptService", "d652849c344623cc26a0b327b24eac1fac17ec087ebc98407d3916dbdf9e2859", 42494 },
	{ "ShopClient", "LocalScript", "StarterPlayerScripts", "fe613ef07803ce0d9002b3af4c1e99d32fd5ec4594ccb2530721210d73d21124", 59523 },
	{ "PlotBuilding", "ModuleScript", "ServerScriptService", "f4097e603565fa438d63afbcb95928e9c95e3e0c74e84d5110f2aa12fc5deed1", 34099 },
	{ "PlotBuildingVisuals", "ModuleScript", "ServerScriptService", "a9a6c414d4d256b4c3bd14866a5a4c9e42c6a92d9ac3abe843a974ba55beb37a", 24058 },
	{ "BuildingClient", "LocalScript", "StarterPlayerScripts", "450068cb37007a70e0a7ba828a06503690c8f71b896141c79874be3d92ee94ec", 9408 },
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
