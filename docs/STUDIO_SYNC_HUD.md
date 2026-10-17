# Studio sync: Cash and Income on the valuation bar (D4)

> **Lobby-all (2026-10-16):** `IpoClient` changed again on branch `lobby-all` (it waits quietly for leaderstats, which now come with a garage). The row and the hash block below give its current file; the full list for that branch is docs/STUDIO_SYNC_LOBBY.md, section "Lobby all".

Branch `hud-cash`. One script changed: **IpoClient**. Nothing else. Written without Studio: nothing here was seen on a screen (see "What only your eyes can judge"). Updated after the independent review of `727c5ef` (the review's blocker, the rounding, the new hash); updated again after the review of `9c15e20` (section (h): what the loading rule depends on, and the test that ties it to TycoonCore).

What changed: the valuation bar (top left, next to the IPO button) now has three rows. **Top:** your Cash and Income, for example `$4,630 · +$18/s`. **Middle:** the progress bar, exactly as before. **Bottom:** the stage and the valuation, for example `🏚️ Garage → Seed · $0 / $1.8K` (a shorter form when the bar is too narrow, see section (d)). While the save loads, the top row stays **empty** (see section (a)), so a returning player never sees `$0 · +$0/s`. Until now the Cash was only in Roblox's player list, which a new player doesn't see. It is the owner's decision D4 (docs/GAMEPLAY_FIRST_HOUR_PROPOSAL.md, sections 0 and 5.1, on the `gameplay-design` branch).

## (a) The script to paste

| Script | Studio type and place | State | sha256 | Bytes |
|---|---|---|---|---|
| `IpoClient` | LocalScript, StarterPlayer > StarterPlayerScripts | changed | `ddc1d9614a203207fbd3fd0bc2d8d493b6289bf18f29ce7c78b765d6bd9c21da` | 42081 |

Exact Explorer path: **StarterPlayer > StarterPlayerScripts > IpoClient**. Hash and size are of the repo file `IpoClient.lua` at commit `c89e57e` (the last commit that touches it; later commits on this branch are only this doc). The block in section (c) was run in Luau on the real file and says `OK`, and the hash matches `shasum -a 256`. The earlier hash (`15de6cd4...`, 38612 bytes) is the file before the review: if your Studio script says `DIFFERENT`, paste the file again. The file uses `\n` line endings and ends with one newline; Studio may drop that last newline, so the block prints both cases as OK.

- **While the save loads, the top row is empty.** TycoonCore makes `leaderstats` at join with Cash 0 and Income 0, and writes the saved Cash only after the DataStore read (and a 7 s re-read when the save is under 75 s old), the income and the offline earnings after that. Showing the folder as it is would show `$0 · +$0/s` to a returning player. So the bar waits for the player attribute **`Upgrade1`**: TycoonCore sets `Upgrade1` to `Upgrade6` (true or false) for every player in `refreshSign` -> `publishUpgrades`, after the saved Cash, the income and the offline earnings are written and right before `data.ready`, and never before. The row then shows the real values (a brand-new player sees `$0 · +$0/s` at that moment). If the attribute never comes (a failed server script), the row shows the real values 30 s after the leaderstats were found. An IPO that resets Cash to 0 shows `$0` at once. This is client-side only: TycoonCore already sets that attribute on `main` (the shop's Office tab uses it), so **nothing on the server changes**.
- **TycoonCore: not needed, not touched.** The bar reads the `leaderstats` folder (Cash and Income) that TycoonCore already makes on `main` (TycoonCore.lua, `onPlayerAdded`). It is claimed by nobody on this branch; the `customize-pr1` branch changes it for other reasons, and this change has nothing to do with that. Nothing else needs pasting: no server script, no config, no remote, no save field.
- **No new Studio objects.** No new remote, no new script.
- **Publishing:** nothing special for this change (client only, no save change, no new remote). Follow docs/PUBLISH_RULES.md as always (**Shut down all servers**, commit every draft in View > Drafts first).
- **Rollback:** restore the old `IpoClient`. The bar goes back to two rows. No save is affected.

## (b) Steps

1. In a terminal in the project folder: `git fetch`, then `git switch hud-cash`, then `git pull`. (Or open the file on GitHub on the `hud-cash` branch.)
2. Open `IpoClient.lua`, select all (Cmd+A), copy (Cmd+C).
3. In Studio: Explorer > StarterPlayer > StarterPlayerScripts > double-click `IpoClient`, select all, paste over everything.
4. Paste the block from section (c) into **View > Command Bar** and press Enter. The line `IpoClient OK 41550 bytes` must appear. `DIFFERENT` means the paste was not complete: paste again.
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
	IpoClient = { "ddc1d9614a203207fbd3fd0bc2d8d493b6289bf18f29ce7c78b765d6bd9c21da", 42081 },
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

1. **At the start, 0 Cash.** Press F5 and look at the bar. Top row: empty for a moment while the save loads, then `$0 · +$0/s`. Middle: the empty progress bar. Bottom: `🏚️ Garage → Seed · $0 / $1.8K`, or a shorter form such as `🏚️ Garage · $0 / $1.8K` or `🏚️ $0 / $1.8K` (see the tables below). Nothing says `nil`, `nan` or a minus sign. (If the top row is still empty after a few seconds, the `Upgrade1` attribute did not arrive: it shows up by itself after 30 s, and tell me.)
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
8. **Rejoin.** Stop and press F5 again. The top row is **empty for a moment** while the save loads (the bar waits for the server: a moment, and about 7 s more if the save is under 75 s old, because the server reads it again after 7 s; I have not timed it in Studio), then shows your **saved Cash** and the Income. It never shows `$0 · +$0/s` on the way. Look at the top row from the first frame, or record the screen.
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
| 999,999, 99,999 | `$1M · +$100K/s` | the same |
| over 999 trillion | `$999T · +$999T/s` | the same |

Every form rounds to the nearest (99,999 is `$100K` in all of them, 4,630 is `$4.6K` and, in the shortest form, `$5K`) and moves to the next unit at 999,500 (`$1M`, never `$1000K`: `IpoConfig.formatShort` has that fault, the bar guards it, `IpoConfig` is not changed). The narrow column is what the tests' (wide) font estimate gives; the real font may show a fuller form. Bottom row, fullest first: stage, next stage, valuation and target, then the multiplier and Shares (only when they are not x1 and 0); when it doesn't fit it drops the multiplier and Shares first, then the next stage's name, then the stage's name, then the icon. The valuation is always kept. With the estimate, `🏚️ Garage · $0 / $1.8K` on the wide bar and `🏚️ $0 / $1.8K` on the narrow one. Text is 16 px where it fits (top row) and 14 px otherwise; never smaller.

## (e) What only your eyes can judge

- **The real font widths.** The tests use an estimate of Gotham Bold (wide on purpose). The game measures the real font (TextService), so it should fit, but only Studio shows it. If the narrow bar often falls back to the short forms (`$123K +$12K`) the estimate was too pessimistic or the bar is too narrow: tell me which numbers you saw.
- **Whether 16 / 14 px reads well** on a phone, and whether the bar feels crowded with three rows in 64 px.
- **Colors:** the top row is white, the bottom row is the old gold, the progress bar is as before. Is the white row too loud next to the gold?
- **The 568x320 phone (held sideways, narrow):** see "Accepted overlaps" in section (f). This change does not move or resize the bar, so it did not make that worse, and it did not fix it.
- **OWNER DEFAULT: losing "Tap to go public" on narrow phones is fine.** **The IPO-ready text.** Before: `🔔 IPO-ready! Tap to go public` on the top row, plus the valuation on the bottom row. Now it is one row: the fullest of `🔔 IPO-ready! Tap to go public`, `🔔 IPO-ready! · $81K`, `🔔 IPO-ready!`, `🔔 IPO!`. On a narrow phone you won't see "Tap to go public". The owner accepted this as the default.
- **OWNER DEFAULT: hiding the multiplier and the Shares while they are x1 and 0 is fine.** They used to be on the bar all the time (`x1 · 📜 0`). The doc says to show them only when they are not x1 and 0; I did that. They are always in the IPO window.
- **OWNER DEFAULT: `$999T` for any amount above 999 trillion is fine.** The bar caps what it shows there (`MONEY_CAP`), so the text stays short.
- **What is not there:** the doc says Cash "counts up between ticks". That needs a loop or a tween; this change has no loop (your rule), so the number simply changes each time the server sets it (about once a second).

## (f) Accepted overlaps

On a 568x320 phone held sideways the bar sits under the HUD row, where it was before this work (the bar is not moved or resized: tools/hud_test.py checks its rectangle at five sizes). There it touches things that are **not new**. They are accepted for now; fixing them means moving the bar or the other element, which is a separate decision. `tools/daily_test.py` lists only the call tray; the rest is listed by `tools/hud_test.py` (the `TOUCHES` table) and was on `main` already.

| 568x320 with a top bar of | the bar touches | on `main` already? |
|---|---|---|
| 0 | the call tray and its text line, the pop-up lane at -184 | yes |
| 36 or 58 | the call tray and its text line, the pop-up lanes at -128 and -184, the thumbstick | yes |

The bar touches no HUD button, no daily gift chip and no Goals card at any of the five sizes (that is checked, and a new overlap fails the test).

## (g) Not tested

I never saw Studio. Tested: the real `IpoClient.lua` runs in a fake Roblox (tools/hud_test.py): the text of the three rows for many Cash and Income values, the rectangles at 5 sizes with 3 top bars each, updates on Changed events and the rate limit, a missing leaderstats at start and a late one, the progress bar, and 69 deliberate breakages, each caught by a named check. The review fixes add the loading rule (empty while the save loads, the real values at the server's signal, the 30 s fallback, a rebind restarts it, nothing leaks over 100 rebinds, an IPO reset shows `$0`) and the rounding. Not tested: the real font and its widths, how the text looks, the real layout engine (the fake computes positions from offsets and scales, like Roblox does for these simple frames), `TextService:GetTextSize` on the real emoji, the real order in which Roblox replicates the Cash change and the `Upgrade1` attribute to the client (the server writes Cash and Income well before it sets the attribute, so the bar relies on Roblox delivering them in that order; the 30 s fallback covers a signal that never comes), how long the real load takes in Studio, touch input, and any other client script running at the same time. The coupling checks (section (h)) read the source text of `TycoonCore.lua`, `IpoServer.lua` and the other scripts; they never run them. They cannot see a change that keeps the same order in the text but changes what happens (an early `return`, a `task.wait` moved around, a function called through another name or a table), and they do not time the DataStore: the 29 s is the review's figure, not mine.

## (h) What this rule depends on

The loading rule (the top row stays empty until the player attribute `Upgrade1` appears, section (a)) is **client-only**, but it is only correct because of three things on the server and one number on the client. Nothing in the game ties them together, so `tools/hud_test.py` does (the "coupling" checks).

1. **TycoonCore sets `Upgrade1` .. `Upgrade6` in exactly one place and at one moment.** `publishUpgrades` does it (`"Upgrade" .. i`, for every entry of `UPGRADES`), and only `refreshSign` calls `publishUpgrades`. In `onPlayerAdded`, `refreshSign(player)` comes **after** `load(player)`, the saved Cash write (`cash.Value = savedCash`), `updateIncome` and the offline earnings (`cash.Value += earned`, `addEarnings`), and **before** `data.ready = true`. If any of that moves, a returning player sees `$0 · +$0/s` again (or, set earlier, never gets the empty row at all) and nothing says so.
2. **`refreshSign` has three call sites, and only these:** the load (`onPlayerAdded`), a purchase (`buyUpgrade`, after `checkUpgradePurchase`'s first test `if not data.ready then return`) and the IPO commit (`commitIpo`, which is only reached from `IpoServer`'s `goPublic`, which only `onAction` calls, after its `not data.ready` refusal). A purchase or an IPO can therefore never publish the attribute before the load is finished. A new call site, a new place that sets an Upgrade attribute (in TycoonCore or in any other script), or a removed guard fails a named check.
3. **The client's attribute is one the server really sets.** `LOADED_ATTRIBUTE` must be `Upgrade1` .. `Upgrade6`. (Not `IpoCount`, which is set earlier.)
4. **The 30 s safety delay (`MONEY_WAIT`).** If the attribute never comes (a failed server script), the row shows the real values 30 s after the leaderstats were found. The delay has to be longer than the longest normal join, or a slow-but-fine join shows `$0` first. What TycoonCore adds to a join by itself, in the worst case: the first read's retries (2 s + 4 s = 6 s, `LOAD_TRIES` = 3), the re-read wait for a fresh save (`REREAD_WAIT_SECONDS` = 7 s) and the second read's retries (6 s): **19 s**. The review of `9c15e20` computed a worst case of **about 29 s** in all, so the rest (about 10 s) is Roblox's own time to answer the reads and the setup calls (pass checks and so on). That 29 s is the review's number: I did not measure it, and I could not see how it was reached. 30 s leaves about 1 s over it. If the delay does run out early, the cost is cosmetic (the row shows the Cash the server has at that moment, possibly `$0` for a returning player until the save arrives); the client saves and sends nothing.

**What the test does** (`python3 tools/hud_test.py`, checks named `coupling: ...`; no Studio, no Luau needed for them): it reads the real `TycoonCore.lua`, `IpoServer.lua` and every other `.lua` in the folder as text, with comments and string contents blanked, so comments, whitespace and indentation do not matter. It checks the order of source positions inside `onPlayerAdded`, the list of allowed call sites of `refreshSign` (`REFRESH_SIGN_SITES` in the test), the single place that sets the attributes, the purchase and IPO guards, that `LOADED_ATTRIBUTE` is an attribute `publishUpgrades` sets, that `MONEY_WAIT` is at least 30 s and covers the server's scripted waits plus 10 s for Roblox (`DATASTORE_ALLOWANCE`). It then breaks the files on purpose (25 mutants: the attribute moved before the Cash write, before the offline earnings, after `data.ready`; a new `refreshSign` call at join, in `PlayerRemoving`, in the income loop; `Upgrade1` set when `leaderstats` is created; `refreshSign` removed from the load; the guards removed; the server's waits made longer; `IpoClient` waiting for another attribute; the 30 s delay changed to 3 s) and each must be caught by a named check; 3 harmless edits (comments and strings that mention the same words, other indentation) must keep every check green. It passed on this branch, on `origin/main` and on `origin/customize-pr1`, each with this branch merged in (a scratch copy, nothing pushed).

**When a coupling check fails:** do not just edit the test. Someone changed when `Upgrade1` appears (or how long a join can take). Re-read `IpoClient.lua` (`LOADED_ATTRIBUTE`, `restartMoneyRule`) and this section, decide whether the bar's rule still holds, then update the rule or the test, and this section.

**OWNER DEFAULTS (recorded):**
- **The 30 s safety delay stays.** The review's worst case is about 29 s; the owner accepted 30 s.
- **Relying on `Upgrade1` as the "loaded" signal is accepted**, with a test that ties it to TycoonCore (above) instead of a new server signal. No server script changes for this.

## (i) Follow-ups

- `IpoConfig.formatShort` (on `main`, not claimed by this change) prints `$1000K` for amounts from 999,950 to 999,999 and `$1000M` just under a billion (the same at `B` just under a trillion) in the **other** windows, because it rounds to one decimal after choosing the unit. The bar guards its own text (`shortAmount`), so it never shows that. Whoever next touches `IpoConfig` should fix it.
