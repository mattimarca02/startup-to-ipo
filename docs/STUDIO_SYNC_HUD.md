# Studio sync: Cash and Income on the valuation bar (D4)

Branch `hud-cash`. One script changed: **IpoClient**. Nothing else. Written without Studio: nothing here was seen on a screen (see "What only your eyes can judge").

What changed: the valuation bar (top left, next to the IPO button) now has three rows. **Top:** your Cash and Income, for example `$4,630 · +$18/s`. **Middle:** the progress bar, exactly as before. **Bottom:** the stage and the valuation, for example `🏚️ Garage → Seed · $0 / $1.8K` (a shorter form when the bar is too narrow, see section (d)). Until now the Cash was only in Roblox's player list, which a new player doesn't see. It is the owner's decision D4 (docs/GAMEPLAY_FIRST_HOUR_PROPOSAL.md, sections 0 and 5.1, on the `gameplay-design` branch).

## (a) The script to paste

| Script | Studio type and place | State | sha256 | Bytes |
|---|---|---|---|---|
| `IpoClient` | LocalScript, StarterPlayer > StarterPlayerScripts | changed | `15de6cd46fb16ca11d8ec9b8a191f6c1ad7d16a9a2015e7249fb908d2ebe474a` | 38612 |

Exact Explorer path: **StarterPlayer > StarterPlayerScripts > IpoClient**. Hash and size are of the repo file `IpoClient.lua` at commit `7e63187` (the last commit that touches it; later commits on this branch are only the test and this doc). The hash was computed with the block in section (c) run in Luau on the real file, and it matches `shasum -a 256`. The file uses `\n` line endings and ends with one newline; Studio may drop that last newline, so the block prints both cases as OK.

- **TycoonCore: not needed, not touched.** The bar reads the `leaderstats` folder (Cash and Income) that TycoonCore already makes on `main` (TycoonCore.lua, `onPlayerAdded`). It is claimed by nobody on this branch; the `customize-pr1` branch changes it for other reasons, and this change has nothing to do with that. Nothing else needs pasting: no server script, no config, no remote, no save field.
- **No new Studio objects.** No new remote, no new script.
- **Publishing:** nothing special for this change (client only, no save change, no new remote). Follow docs/PUBLISH_RULES.md as always (**Shut down all servers**, commit every draft in View > Drafts first).
- **Rollback:** restore the old `IpoClient`. The bar goes back to two rows. No save is affected.

## (b) Steps

1. In a terminal in the project folder: `git fetch`, then `git switch hud-cash`, then `git pull`. (Or open the file on GitHub on the `hud-cash` branch.)
2. Open `IpoClient.lua`, select all (Cmd+A), copy (Cmd+C).
3. In Studio: Explorer > StarterPlayer > StarterPlayerScripts > double-click `IpoClient`, select all, paste over everything.
4. Paste the block from section (c) into **View > Command Bar** and press Enter. The line `IpoClient OK 38612 bytes` must appear. `DIFFERENT` means the paste was not complete: paste again.
5. View > Drafts: commit the `IpoClient` draft.

## (c) Hash check (command bar)

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

local SPS = game:GetService("StarterPlayer"):WaitForChild("StarterPlayerScripts")
local WANT = {
	IpoClient = { "15de6cd46fb16ca11d8ec9b8a191f6c1ad7d16a9a2015e7249fb908d2ebe474a", 38612 },
}
for name, want in pairs(WANT) do
	local script = SPS:FindFirstChild(name)
	if not script then
		print(name, "MISSING (it should be in StarterPlayerScripts)")
	else
		local source = script.Source
		local same = sha256(source) == want[1] and #source == want[2]
		local withNewline = sha256(source .. "\n") == want[1] and #source + 1 == want[2]
		print(name, (same or withNewline) and "OK" or "DIFFERENT", #source, "bytes")
	end
end
```

## (d) Playtest checklist (Studio, F5; read the Output window the whole time: no red text)

You need a **new** save for the first two, or use Shop > Debug > **Reset IPO progress** and start a fresh Studio save. Passes don't matter here.

1. **At the start, 0 Cash.** Press F5 and look at the bar. Top row: `$0 · +$0/s`. Middle: the empty progress bar. Bottom: `🏚️ Garage → Seed · $0 / $1.8K`, or a shorter form such as `🏚️ Garage · $0 / $1.8K` or `🏚️ $0 / $1.8K` (see the tables below). Nothing says `nil`, `nan` or a minus sign, and there is no flash of an empty top row longer than a moment.
2. **After the Desk.** Shop > **Office** tab > buy the Desk (free). Top row becomes `$0 · +$1/s`, then the Cash counts up: `$1`, `$2`, ... about once a second.
3. **While income ticks.** Leave it 30 seconds. The top row moves about once a second and the text never shakes or jumps in size. Open the Output window: nothing is printed by the bar.
4. **Buying something.** Shop > Debug > **Give $10,000**. The top row shows `$10,000 ...` within a quarter of a second. Give $1,000,000 twice: `$1M`, then `$2M` (no `e+`, no stray letters).
5. **Progress bar unchanged.** Shop > Debug > **Valuation +$100,000**: the middle bar fills and the bottom row names the next stage. **Jump to IPO-ready**: the bottom row says `🔔 IPO-ready! ...`, the IPO button glows and says `IPO!`. Tap the bar: the IPO window opens as before.
6. **The phone sizes.** Test > Device (the device emulator), pick each of these and repeat steps 1, 2 and 4:
   - **320x568** (the narrow one: the bar is 158 px wide). The text must fit inside the bar, nothing cut off with `...`, nothing drawn past the bar's edge, and nothing under the HUD buttons on the left.
   - **667x375** (the bar is 233 px wide, in the HUD row, with the gift chip right of it).
   - Also try 568x320 and 844x390 once.
   - Look at the three rows: no row touches another, and the progress bar is where it was.
7. **Windows.** Open the Shop, the Team and the IPO window and close them. The bar stays on the left and nothing overlaps the buttons. The call tray (calls only ring in Studio) and the gift chip stay clear of the bar.
8. **Rejoin.** Stop and press F5 again: the top row shows your saved Cash at once, not `$0`.
9. **Output window.** At the end there are no red lines and no new warnings from `IpoClient`.

### What you should see (the text forms)

The bar shows the fullest text that fits, measured on the real font (so the exact form may differ from this table on your screen). Top row, fullest first:

| Cash, Income | wide bar (233 px) | narrow bar (158 px), likely |
|---|---|---|
| 0, 0 | `$0 · +$0/s` | the same |
| 4,630, 18 | `$4,630 · +$18/s` | the same |
| 99,999, 9,999 | `$99,999 · +$9,999/s` | `$100K · +$10K/s` (14 px) |
| 123,456, 12,345 | `$123.5K · +$12.3K/s` | `$123K +$12K` |
| 1.5M, 45,000 | `$1.5M · +$45K/s` | the same |
| over 999 trillion | `$999T · +$999T/s` | the same |

The narrow column is what the tests' (wide) font estimate gives; the real font may show a fuller form. Bottom row, fullest first: stage, next stage, valuation and target, then the multiplier and Shares (only when they are not x1 and 0); when it doesn't fit it drops the multiplier and Shares first, then the next stage's name, then the stage's name, then the icon. The valuation is always kept. With the estimate, `🏚️ Garage · $0 / $1.8K` on the wide bar and `🏚️ $0 / $1.8K` on the narrow one. Text is 16 px where it fits (top row) and 14 px otherwise; never smaller.

## (e) What only your eyes can judge

- **The real font widths.** The tests use an estimate of Gotham Bold (wide on purpose). The game measures the real font (TextService), so it should fit, but only Studio shows it. If the narrow bar often falls back to the short forms (`$123K +$12K`) the estimate was too pessimistic or the bar is too narrow: tell me which numbers you saw.
- **Whether 16 / 14 px reads well** on a phone, and whether the bar feels crowded with three rows in 64 px.
- **Colors:** the top row is white, the bottom row is the old gold, the progress bar is as before. Is the white row too loud next to the gold?
- **The 568x320 phone (held sideways, narrow):** the bar sits under the HUD row there and already touched the call tray, a few pop-up lanes and the thumbstick before this change (the same overlaps tools/daily_test.py lists as accepted). This change does not move or resize the bar, so it did not make that worse, and it did not fix it. If it looks bad in Studio, fixing it means moving the bar or the tray: a separate decision.
- **The IPO-ready text.** Before: `🔔 IPO-ready! Tap to go public` on the top row, plus the valuation on the bottom row. Now it is one row: the fullest of `🔔 IPO-ready! Tap to go public`, `🔔 IPO-ready! · $81K`, `🔔 IPO-ready!`, `🔔 IPO!`. On a narrow phone you won't see "Tap to go public". Say if you want it back.
- **The multiplier and Shares.** They used to be on the bar all the time (`x1 · 📜 0`). The doc says to show them only when they are not x1 and 0; I did that. They are always in the IPO window.
- **What is not there:** the doc says Cash "counts up between ticks". That needs a loop or a tween; this change has no loop (your rule), so the number simply changes each time the server sets it (about once a second).

## (f) Not tested

I never saw Studio. Tested: the real `IpoClient.lua` runs in a fake Roblox (tools/hud_test.py): the text of the three rows for many Cash and Income values, the rectangles at 5 sizes with 3 top bars each, updates on Changed events and the rate limit, a missing leaderstats at start and a late one, the progress bar, and 45 deliberate breakages, each caught by a named check. Not tested: the real font and its widths, how the text looks, the real layout engine (the fake computes positions from offsets and scales, like Roblox does for these simple frames), `TextService:GetTextSize` on the real emoji, the real leaderstats replication timing, touch input, and any other client script running at the same time.
