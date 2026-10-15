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

### (d) Other sync docs whose TycoonCore row is now stale

docs/STUDIO_SYNC_MASTER.md (section 3's table row 21 and the `TycoonCore` line of its section 6 block) and docs/STUDIO_SYNC.md still give `main`'s old TycoonCore (`9607262c…`, 36399 bytes). After L0 their block says `DIFFERENT` for TycoonCore on a synced Studio. Use (c) for TycoonCore. L0 does not edit those docs.

### (e) What was checked, and what wasn't

- `python3 tools/lobby_test.py` checks the markers, the block against `99eed7b`, the rest of the file, this table and this block (run in Luau against a fake Studio). `tools/daily_test.py`, `hud_test.py`, `world_test.py`, `icon_test.py` and `shop_ux_test.py` pass unchanged.
- **Not done:** the paste, the hash block in real Studio and the playtest (steps 3 to 6). Nobody has run them for L0 yet.
