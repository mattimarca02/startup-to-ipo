# Studio sync: the shop, S1 and S2

Branch `shop-build` (from `world-icons-pass` at `6bc827c`): PR **S1** and **S2** of docs/SHOP_UX_PROPOSAL.md (section 5). Nothing here touches Roblox by itself: it is the list of what the owner does in Studio, by hand. The SHA-256 and sizes below are the files as they are on the branch (`tools/shop_ux_test.py` fails if this table or the hash block stops matching them).

**What changes in the game:** only the shop window. One new ModuleScript, `ShopLayout` (the window's sizes and the Office ladder, as pure functions), and one changed LocalScript, `ShopClient`. No server script, no config, no remote, no save change. The item icons are still emoji (S3 replaces them later).

## (a) Files to copy

| Script | Studio type and place | State | sha256 | Bytes |
|---|---|---|---|---|
| `ShopLayout` | ModuleScript, ReplicatedStorage | new | `73c4ddd5279025fbd32f2a19029af8d621c84816ffbb51c010ac701e8ed24fdf` | 24458 |
| `ShopClient` | LocalScript, StarterPlayer > StarterPlayerScripts | changed | `ff29fe44e9f7b79a1da40aead7190bb4c7c95ee14bede4998323fe7ed9af883a` | 59330 |

The files use `\n` line endings and end with one newline. Studio may drop that last newline or add one more: the hash check (d) accepts both, and nothing else. Every other script stays exactly as it is.

**The order matters: `ShopLayout` first, then `ShopClient`.** `ShopClient` waits for `ShopLayout` with no time limit, like it waits for `ShopConfig`. If `ShopClient` is pasted first, the SHOP button never appears and the Output says `Infinite yield possible on 'ReplicatedStorage:WaitForChild("ShopLayout")'`. Creating `ShopLayout` fixes it at once.

**The Studio MCP cannot create a script inside a service** (it can only set the Source of a script that already exists). Create the new one by hand, with exactly this name and parent:

- `ShopLayout`: a **ModuleScript** whose parent is **ReplicatedStorage** (next to `ShopConfig`).

## (b) Studio-only settings

Nothing new.

## (c) Steps on the Mac

1. **Put the branch's files in their own folder.** In Terminal, in the project folder:
   ```
   git fetch
   git worktree add ~/Developer/shop-studio origin/shop-build
   ```
   This makes a separate folder, `~/Developer/shop-studio`, with the branch's files; your own folder and branch are not touched. Open it in VS Code (**File > Open Folder...**, pick `shop-studio`). When you are done: `git worktree remove ~/Developer/shop-studio`. (Once the branch is merged, pull `main` instead.)
2. **Create `ShopLayout`:** in the Explorer, hover **ReplicatedStorage**, click the **+** (or right-click > **Insert Object**), pick **ModuleScript**, and rename it `ShopLayout` exactly. Open `ShopLayout.lua`, select all, copy; double-click the new ModuleScript, select all, paste.
3. **Paste `ShopClient`:** double-click **StarterPlayer > StarterPlayerScripts > ShopClient**, select all, and paste the whole `ShopClient.lua`.
4. **Check the hashes:** paste block (d) into **View > Command Bar** and press Enter. Both lines must say `OK`.
5. **View > Drafts:** commit both drafts (an uncommitted draft is not published).
6. **Playtest** with the checklist in (e), then look at the list in (f).
7. **Publish** with **Shut down all servers**, as always (docs/PUBLISH_RULES.md). No save section, no remote, no Max Players change: the rollback floor stays the same.

## (d) Hash check (command bar)

The same SHA-256 code as docs/STUDIO_SYNC.md (run by `tools/shop_ux_test.py` on these two files, and checked there against Python's `hashlib`).

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

-- StarterPlayerScripts sits inside StarterPlayer; the other place is a service
local function folderOf(place)
	if place == "StarterPlayerScripts" then
		return game:GetService("StarterPlayer"):FindFirstChild("StarterPlayerScripts")
	end
	return game:GetService(place)
end
local WANT = {
	ShopLayout = { "73c4ddd5279025fbd32f2a19029af8d621c84816ffbb51c010ac701e8ed24fdf", 24458, "ReplicatedStorage" },
	ShopClient = { "ff29fe44e9f7b79a1da40aead7190bb4c7c95ee14bede4998323fe7ed9af883a", 59330, "StarterPlayerScripts" },
}
for name, want in pairs(WANT) do
	local folder = folderOf(want[3])
	local script = folder and folder:FindFirstChild(name)
	if not script then
		print(name, "MISSING (create it in " .. want[3] .. ")")
	else
		local source = script.Source
		local function matches(text)
			return #text == want[2] and sha256(text) == want[1]
		end
		-- the file as it is, or with its last newline dropped by Studio, or with one newline added by Studio
		local ok = matches(source) or matches(source .. "\n") or (string.sub(source, -2) == "\n\n" and matches(string.sub(source, 1, -2)))
		print(name, ok and "OK" or "DIFFERENT", #source, "bytes")
	end
end
```

## (e) Playtest checklist (F5, then Test > Device)

1. **Start (F5).** The Output shows no red error that names `ShopClient` or `ShopLayout`. The SHOP button is where it was.
2. **Open the shop.** It opens on the Office tab. On a wide window (landscape, and the desktop) the tabs are a column on the left, 112 px wide; on a phone held upright they are a row under the title. Top right: a "?" and the red X.
3. **Each tab:** tap Office, Passes, Boosts, Cash and (Studio only) Debug. The tapped tab turns green. No text is tiny: long descriptions make a card taller instead of shrinking. The Vault of Cash (Cash tab) has a gold **BEST VALUE** badge.
4. **Buy the Desk.** If your save already owns upgrades, the top row says "N of 6 bought" and the hero card is the next one. To see the Desk as the hero again: Debug > **Jump to IPO-ready**, open the IPO window and **Go Public** (an IPO resets the upgrades), then Debug > **Reset IPO progress**. The Desk's button says **Get it free**. Tap it: "..." then **Bought!**, the icon pops and **+$1/s** floats up; a moment later the Desk folds into "1 of 6 bought" and the Coffee Machine becomes the hero card.
5. **Watch the bar.** The Coffee Machine's bar fills with your Cash (for example "$3 / $25") and the time counts down ("about 22 s"; your numbers depend on your Cash and Income). The button says **Need $22 more** (gray). Tap it: the bar shakes, the card says "about 22 s at your Income", and nothing is bought.
6. **Buy the next.** When the bar is full the button turns green, **Buy $25**, with a soft pulse every 4 s. Tap it once (an Office upgrade never asks for a confirmation): bought, folded, and the Laptop is the hero. The locked rungs below are dimmed, with a small padlock on the icon, "Unlocks after <the one before>" and no button.
7. **The summary row:** tap "2 of 6 bought": the owned upgrades show with a green check and "Owned"; tap again to fold them.
8. **All six:** Debug > **Give $1,000,000**, then buy the rest. After the sixth, a gold **Office complete** banner at the top says "Your next step: the IPO window" (no button).
9. **"?":** a "How the shop works" card with three lines covers the pages. **Back** closes it; so does a tab, or "?" again.
10. **Messages:** with the shop open, Debug > **Give: Pile of Cash**. The message shows in a line at the window's bottom for 3.5 s (the pages get shorter meanwhile), never as a pop-up over the window.
11. **Test > Device:** a phone at **320 x 568** (portrait) and one at **667 x 375** (landscape). Nothing is cut off, the hero card and its button are fully visible, and the X and "?" are easy to hit. Then go back to the desktop view.
12. **Debug > Paid random items: restricted on/off:** Luck Boost disappears from the Boosts tab; tap it again and it comes back (it shows "Coming soon" while `EggsEnabled` is off).
13. **The tutorial strip (optional):** while playing, switch the command bar to the client (**Test > Client / Server** toggle) and run `game.Players.LocalPlayer.PlayerGui:SetAttribute("TutorialBanner", "Tap Get it free to buy the Desk.")`. A gold line appears at the window's bottom and the pages get shorter; the Office page does not move (a hero that becomes the hero while the strip is up always shows whole above it). `SetAttribute("TutorialBanner", nil)` removes it. A text longer than 40 characters prints a warning in the Output (Studio only): `ShopClient: TutorialBanner is N characters, ...`.

    **Text limit for TutorialConfig's authors** (`ShopLayout.stripMaxChars`, an average 16 px bold letter of the tests' estimate; the real font is a little narrower). **Every TutorialBanner text must stay within 40 characters** (`ShopLayout.STRIP_TEXT_LIMIT`, the smallest landscape phone; decided by the owner). Per phone and Roblox top bar:

    | Phone | Top bar 0 | Top bar 36 | Top bar 58 |
    |---|---|---|---|
    | 568 x 320 (smallest landscape) | 40 (1 line, 382 px) | 40 (1 line) | 40 (1 line) |
    | 640 x 360 | 94 (2 lines, 448 px) | 47 (1 line) | 47 (1 line) |
    | 667 x 375 | 98 (2 lines, 473 px) | 49 (1 line) | 49 (1 line) |
    | 844 x 390 | 104 (2 lines, 500 px) | 52 (1 line) | 52 (1 line) |
    | 320 x 568 (portrait) | 56 (2 lines, 274 px) | 56 (2 lines) | 56 (2 lines) |

    It is an estimate for ordinary sentences: a text of long capitalised words is wider than its count says (check it at 568 x 320). The strip is one line on a window lower than 330 px, two lines otherwise. While a status message shows (3.5 s) the strip is hidden (the message takes the same slot), and the help card ("?") covers it (ZIndex 5 over the strip's 3). Both differ from docs/TUTORIAL_PROPOSAL.md, which keeps the strip up whenever the shop is open during steps 1 and 4.

The Retry button only appears when the server never answers "Upgrades" (5 tries, 2 s apart); Studio always answers, so it is tested in `tools/shop_ux_test.py` only.

## (f) What to look at in Studio (only your eyes can judge these)

- **Text that may not fit.** The tests estimate Gotham's widths (about 0.56 em a letter); the real font decides. Look at: the tab labels (five in Studio at 320 x 568, about 51 px each), "Need $1,234 more" on the hero's button (two lines are fine), "Unlocks after Coffee Machine" and two-line names on a portrait phone, "Startup Shop" in the 168 px portrait title, the BEST VALUE badge, the help card's three lines (one screen at 667 x 375 and 320 x 568).
- **The drawn check mark and padlock** (UI shapes, no image): do they read at 20 px?
- **The animations:** the pop (0.1 s up and back), the "+$X/s" float (0.8 s), the bar's shake, the pulse every 4 s. Too much, too little?
- **Colors:** the light red of a refusal on a card, the gold banner and badge, the dark gold strip, the gray skeleton rungs, the dimmed locked rungs.
- **568 x 320 under a 58 px top bar, with the tutorial strip:** the hero card fits with one pixel to spare when the strip was up as it became the hero; the summary row is then scrolled out of view above it. A strip that appears later keeps your place and can cover up to 19 px of the hero's bottom until the next buy.
- **Scrolling:** the Office page scrolls by itself only after a buy (the card shows "Bought!" whole) and when a new upgrade becomes the hero (the list arriving, also after Retry, and the fold after a buy); after the sixth it goes back to its top. A message line appearing or going away, the tutorial strip, a tab, closing and reopening the shop and turning the phone never move it: a page that got shorter only stops at its new end.

## (g) Roll back

A version from before this branch keeps working: the old `ShopClient` does not require `ShopLayout`, which then sits unused in ReplicatedStorage. To undo in Studio only, paste `main`'s `ShopClient.lua` back (`git show main:ShopClient.lua`); `ShopLayout` can stay.
