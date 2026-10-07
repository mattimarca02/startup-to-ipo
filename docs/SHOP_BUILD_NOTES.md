# Shop build (S1 and S2): notes and progress

Branch `shop-build` (from `world-icons-pass` at `6bc827c`), worktree `../shop-build`. Builds PR **S1** and **S2** of docs/SHOP_UX_PROPOSAL.md section 5, nothing else: no S3 (no icons, no IconArt or IconVisuals, ShopClient keeps its emoji), no S4, no S5. No Studio, no MCP: everything was written and tested outside Studio, with the free `luau` command-line tool and fake Roblox objects.

## Progress (the source of truth when this job is resumed)

Each item is one commit, pushed right after (`git push -u origin shop-build`), after `tools/daily_test.py`, `tools/shop_ux_test.py` (once it exists), `tools/icon_test.py` and `tools/world_test.py` all pass. An item is ticked in the same commit that does it.

**Phase 0: set-up**
- [x] 0.1 Claim the files in `CONTRIBUTING.md` (ShopClient, tools/daily_test.py, README.md; new rows ShopLayout, tools/shop_ux_test.py, docs/STUDIO_SYNC_SHOP.md, these notes)
- [x] 0.2 These notes with the checklist

**Phase 1: S1 (layout, accessibility, the Names, help, strip, status line)**
- [x] 1.1 `ShopLayout.lua` (new, pure): `layout(guiW, guiH, topBar, ...)` and the card geometry
- [x] 1.2 `ShopClient.lua` S1: the layout from ShopLayout (landscape rail, portrait row), 44 px header items and tap targets, 16 px minimum text, the Names, `HelpButton` and its card, `TutorialStrip`, the in-window status line
- [x] 1.3 `tools/shop_ux_test.py` (new): the fake Roblox, the S1 checks and the S1 mutants (one commit: the mutants came with the checks)
- [x] 1.4 The toast wraps (two lines at 16 px in its 48 px lane), found when re-reading ShopClient after S2

**Phase 2: S2 (the Office ladder)**
- [x] 2.1 `ShopLayout.lua`: ladder state, bar fill, time text, best value, row and hero geometry
- [x] 2.2 `ShopClient.lua` S2: the Office ladder (pushed together with 2.3: alone it fails daily_test's old "Locked" check)
- [x] 2.3 `tools/daily_test.py`: "daily_test: Locked check follows the new ladder" (the one edit there)
- [x] 2.4 `ShopClient.lua`: the BEST VALUE badge on the Cash pack `ShopLayout.bestValue` picks (added after 2.2: the task asks ShopClient to use it)
- [x] 2.5 `tools/shop_ux_test.py`: the S2 checks (and ShopLayout.OFFICE_WIDE: the Office keeps its landscape layout down to 360 px, so the hero fits above the strip at 568x320)
- [x] 2.6 S2 mutants: 35 (67 in all with S1's 32), each caught by its named check; every block of checks now runs in a protected section, so a broken ShopLayout is a named FAIL, never a crash

**Phase 3: Studio sync and wrap-up**
- [x] 3.1 README rows for `ShopLayout.lua` and `tools/shop_ux_test.py`, and the ShopClient row (moved here from phase 1: written once, for S1 and S2)
- [x] 3.2 `docs/STUDIO_SYNC_SHOP.md` (paste order, SHA-256 and sizes, the hash block, the playtest checklist, what to look at); `tools/shop_ux_test.py` runs its hash block on the real files and compares its table with `hashlib`
- [x] 3.3 These notes complete (deviations, questions, what was not tested, results)
- [x] 3.4 Release the claims (the 7 rows stay, set to free)

**Phase 4: the review fixes** (branch `shop-fix` in the worktree `../shop-fix`, pushed to `shop-build` with `git push origin shop-fix:shop-build` after every commit, after the four suites)

An independent review of `shop-build` at `372e998` found no confirmed blocker and ten items. Each was checked first; the section "Review fixes" below says applied or rejected, with the evidence. One commit per item.

- [x] 4.0 Claim the five files in `CONTRIBUTING.md` (rows only: ShopClient, ShopLayout, tools/shop_ux_test.py, docs/STUDIO_SYNC_SHOP.md, these notes; free on this branch and on `customize-pr1`, `task-needs-desk`, `hud-cash`, `world-icons-pass`, `integration-1`), then this checklist
- [x] 4.1 Item 0, base: a plain merge of `origin/world-icons-pass` at `4c052c7` (no rebase, no conflict), the four suites after it: daily_test 1,780 + 20 of 20, shop_ux_test 5,092 + 67 of 67, icon_test 371 + 68 of 68, world_test 353 + 82 of 82 (the `--review` modes of world_test and icon_test fail by design on this branch, only on "no existing file is edited but CONTRIBUTING.md" and "tools/daily_test.py ... is untouched")
- [x] 4.2 Item 1, HUD overlap: the shop window draws above the HUD buttons (DisplayOrder); shop_ux_test models the HUD buttons
- [x] 4.3 Item 2, scroll jump: the Office jumps to the hero only after a buy, a hero change or a Retry; a resize keeps the player's place
- [x] 4.4 Item 3, message at close: a status message still showing moves to the toast when the shop closes
- [ ] 4.5 Item 4, toast overflow: the toast holds at most 2 lines and ends with an ellipsis, in its 48 px lane; every server text tested
- [ ] 4.6 Item 5, the hero's info line at 568 x 320: a shorter "+$40/s" when its box is narrow
- [ ] 4.7 Item 6, Studio's fifth tab in portrait: the tab labels fit
- [ ] 4.8 Item 7, the tutorial strip's text limit: `ShopLayout.stripMaxChars`, the limits in docs/STUDIO_SYNC_SHOP.md, the doc's wrong sentence
- [ ] 4.9 Item 8, daily_test's "Locked" check: which shop_ux_test mutants cover it
- [ ] 4.10 Item 9, the two mutants that also raised a runtime error
- [ ] 4.11 Item 10, docs/STUDIO_SYNC_SHOP.md (hashes, sizes, checklist, what changed) and these notes' results
- [ ] 4.12 Release the claims (rows kept, set to free)

**OWNER DEFAULTS** (given with the review; applied as they are):
1. OWNER DEFAULT: the shop window draws above the HUD.
2. OWNER DEFAULT: the tutorial text limit follows the smallest landscape phone (about 40 characters).
3. OWNER DEFAULT: the client truncates long messages with an ellipsis after 2 lines; the long server texts get shortened at the next server change (not edited now).
4. OWNER DEFAULT: a message still showing when the shop closes moves to the toast.
5. OWNER DEFAULT: the Office page jumps to the hero only after a buy, a hero change or a Retry, never on a message line.

## Preconditions (checked 2026-10-06, before any change)

1. `docs/SHOP_UX_PROPOSAL.md` on `origin/world-icons-pass` (`6bc827c`) records the six owner decisions as **DECIDED BY THE OWNER**: the landscape tab rail (3.1), all six Office rungs with the summary row, hero card and "Unlocks after X" (3.2), Office upgrades never ask for a confirmation and the two-tap confirm only for buildings and furniture above half the player's Cash (3.2, 3.3), factual badges only (3.3), the details sheet sliding up inside the shop window (3.3), 3D icons only for the Office upgrades and the creatures, drawn shapes for the rest (3.6). **Holds.**
2. On this branch the claim rows of `docs/SHOP_UX_PROPOSAL.md`, `docs/WORLD_ICONS_NOTES.md` and `ShopClient` were free. **Holds.**
3. `ShopClient` is free in the `CONTRIBUTING.md` of `origin/customize-pr1` (`3c548ec`), `origin/task-needs-desk` (`c825b14`) and `origin/hud-cash` (`9c15e20`); none of the three has any claimed row at all. Stale rows seen on older branches (they do not count): `ShopClient` on `claude/m6-review`, `claude/pr14-review`, `claude/pr14-rereview` (milestone-6-daily-rewards, 2026-10-01) and `docs-contributing-stale-claim` (milestone-5-onboarding); `tools/daily_test.py` on those three review branches, `building-pass` (visuals-garage, 2026-10-03) and `sims-two-sectors` (customize-pr1, 2026-10-05). **Holds.**
4. (Informational) `IconVisuals.lua` has the global ViewportFrame cap: one registry for the whole client (IconVisuals.lua:499), `allocate` reads `art.Style.viewportCap` (:599, IconArt.lua:48 = 8), and both `build()` (:665-679) and the caches' `show()` go through it. **Holds.** This job does not touch IconArt or IconVisuals.

## Tools

The container had no `luau`: the official release `luau-ubuntu.zip` (github.com/luau-lang/luau, latest) was downloaded into the session's scratch folder and used through `LUAU=/path/to/luau`. Nothing was installed in the repo.

## Results before any change (this branch at `6bc827c`)

| Suite | Checks | Mutation runs |
|---|---|---|
| `tools/daily_test.py` | 1,772 pass, 0 failed | 20 of 20 |
| `tools/world_test.py` | 298 pass | 65 of 65 |
| `tools/icon_test.py` | 199 pass | 51 of 51 |

## What S1 changed

- **`ShopLayout.lua` (new ModuleScript, ReplicatedStorage):** pure functions, no GetService, require or Instance. `layout(guiW, guiH, topBar, tabCount, bottomH)` gives every rectangle of the window in GUI pixels: the window (92 % of the GUI, at most 640 x 470), a 44 px header (title, "?" and X 44 x 44, the "?" 6 px left of the X), the tabs in a 112 px rail on the left in landscape (tabs 112 x 44, 6 px apart, closer on a low window) or a row of 44 px tabs in portrait, the pages, the bottom slot (TutorialStrip or a status message, under the pages), the help card and the toast. `card(cardW, nameH, descH, badgeW)` lays out a Robux or Debug card from the measured heights of its 16 px texts; `helpCard()` the help card.
- **`ShopClient.lua`:** every size comes from ShopLayout (`applyLayout` on every GUI size change, banner change and message). `fitText`'s minimum is 16 px (was 8); descriptions, the status line, the help lines and long labels stay at 16 px and their boxes are measured with `TextService:GetTextSize`, so cards grow instead of shrinking their text. Narrow cards (portrait) put the description under the icon, name and button.
- **Names for the tutorial** (TUTORIAL_PROPOSAL section 3): `TabOffice` ... `TabDebug`, `OfficePage` ... `DebugPage`, `Office1` ... `Office6` (direct children of `OfficePage`), `BuyButton` on every card, `HelpButton`, `TutorialStrip`; also `Title`, `CloseButton`, `TabBar`, `Pages`, `StatusLine`, `HelpCard`, and each Robux card named by its config key.
- **`HelpButton`** opens a one-screen "How the shop works" card (three lines, no reward) over the pages, with a 44 px Back button; a tab, Back or "?" closes it, and the shop always reopens without it.
- **`TutorialStrip`** shows PlayerGui's `TutorialBanner` text at the window's bottom (32 px on a short window, 48 otherwise, plus 6 px, taken from the pages' height); unset, empty or not a string, it is hidden and takes no room.
- **The status line:** while the shop is open every message (ShopNotify, a failed prompt) shows in a line at the window's bottom for 3.5 s instead of the toast, taking its height (1 to 3 lines, at most 72 px) from the pages; a toast still up when the shop opens moves into it. The toast is only for a closed shop, and now wraps to two lines at 16 px in its 48 px lane.

## What S2 changed

- **ShopLayout:** `ladder(upgrades, owned, cash, income, money, bought, busy)` says what every Office rung shows (see its comment); `barFill` (clamped 0..1, a free upgrade is full), `timeText` ("about N s", minutes from 2 min, hours from 2 h; nil when the Cash is there or the Income is 0), `officeRow`, `hero`, `stack`, `revealScroll`, `bestValue`.
- **ShopClient's Office tab:** the owned rungs fold into one summary row ("3 of 6 bought", "+$8/s"; a tap shows them with a drawn check and "Owned", another folds them); the next upgrade is the hero card (72 px icon box, "+$2 every second", the bar, "$12 / $25", "about 13 s", the button); the others are dimmed with a drawn padlock and "Unlocks after <the one before>", and no button. Buy states: "Get it free", "Buy $25" (a soft pulse every 4 s), "Need $13 more" (a tap shakes the bar and says "about 13 s at your Income", nothing is sent), "..." while the request runs. On success the icon pops, "+$2/s" floats up and the card says "Bought!" for 0.8 s before it folds and the next one becomes the hero (it scrolls into view). A refusal (or a failed call) shows in the card, in light red, for 3 s. Three gray skeleton rungs while "Upgrades" is asked; after the 5 tries the old sentence and a Retry button (the same 5 tries); a gold "Office complete" banner with "Your next step: the IPO window" at the top once all six are bought. Never a confirmation. Still only "Upgrades" and "BuyUpgrade", index.
- **BEST VALUE:** a gold badge on the Cash pack with the most minutes of Income per Robux among the ones on sale (today the Vault), computed from ShopConfig on every refresh.
- **`tools/daily_test.py`:** the one edit (its own commit, "daily_test: Locked check follows the new ladder"): the check "Buy is only offered for the next upgrade when the Cash is there" now looks for `button.Visible = row.state ~= "locked"` instead of `setButton(button, "Locked", COLORS.disabled, false)`. Nothing else there changed.

## Review fixes (phase 4): each item checked first, then applied or rejected

### Item 1: the HUD overlap (applied)

**Checked:** true. In landscape the HUD buttons are a 64 px row at the top-left (y 6-70) and the tab rail starts at the window's top-left, and `ShopGui` and `RecruitingGui` (EGGS and TEAM) both had DisplayOrder 0, so which one draws on top was undefined. Measured by the new check on the old ShopClient: at 667 x 375 (no top bar) EGGS covers TabOffice at x 37-74, y 25-69 (37 of its 112 px); at 844 x 390 TEAM covers it at x 154-218 (64 of 112 px), the review's numbers. The SHOP button itself (in the same ScreenGui as the window) also sat on TabOffice (x 82-146).

**Fix (ShopClient only):** the same two layers as PoachClient and IpoClient. `ShopGui` (the window and its toast) now has DisplayOrder **5**, the windows' layer (PoachWindowGui, IpoWindowGui, DailyWindowGui); the SHOP button moved to its own ScreenGui `ShopHudGui` with DisplayOrder **-1**, the HUD's layer (PoachGui, IpoGui). Giving the whole ShopGui 5 instead would have tied the SHOP button with the Poach, IPO and Daily windows (it could draw over them; before, it was always under them). `ShopGui.Window` and every Name the tutorial needs are unchanged; the button keeps its name `ShopButton`, its slot and its code (the tutorial finds HUD buttons by name, anywhere in PlayerGui).

**Every ScreenGui (read from the client scripts by `tools/shop_ux_test.py`, `screen_guis()`):**

| ScreenGui | Script | Holds | Before | After |
|---|---|---|---|---|
| TaskGui | TaskClient | the call tray | -2 | -2 |
| DailyGui | DailyClient | the daily gift chip | -1 | -1 |
| IpoGui | IpoClient | the IPO button, the valuation bar | -1 | -1 |
| PoachGui | PoachClient | the POACH button | -1 | -1 |
| ShopHudGui | ShopClient | the SHOP button | (new; the button was in ShopGui at 0) | **-1** |
| RecruitingGui | EmployeeClient | EGGS, TEAM, the Recruiting window, its messages | 0 | 0 |
| OnboardingGui | OnboardingClient | the goal tracker, its pop-up | 0 | 0 |
| ShopGui | ShopClient | the shop window, the shop's toast (and the SHOP button before) | 0 | **5** |
| DailyWindowGui | DailyClient | the Daily window, its pop-up | 5 | 5 |
| IpoWindowGui | IpoClient | the IPO window, its messages | 5 | 5 |
| PoachWindowGui | PoachClient | the Poach window, the top banners, its messages | 5 | 5 |
| TaskFrontGui | TaskClient | the tray's own message | 5 | 5 |
| HatchRevealGui | EmployeeClient | the hatch reveal (IgnoreGuiInset) | 50 | 50 |
| PoachResultGui | PoachClient | the poach result (IgnoreGuiInset) | 51 | 51 |

**Still layered right:** the call tray (-2) stays under every HUD button and every pop-up, the shop's toast included (it hides while a window is open anyway); the shop's toast keeps its lane (bottom center, -16, 48 px) and now sits on the pop-ups' layer (5) like the IPO, Poach, Daily and tray messages; one window at a time (`OpenPanel`) is unchanged; the hatch reveal and the poach result still draw above the shop. **What changes:** a Recruiting or Onboarding pop-up (layer 0) that appears while the shop is open is now drawn under the shop window instead of an undefined order, the same as it already was under the Poach, IPO and Daily windows; a message from another window's layer 5 ties with the shop window, as it already tied with those windows.

**Tests:** `screen_guis()` and `hud_buttons()` read every client's ScreenGuis and the five HUD buttons (slot, ScreenGui, DisplayOrder; the run stops if a HUD button stops using the shared layout). At every phone, top bar, tab and in Studio and live, two new checks: "no HUD button that may draw above the shop (DisplayOrder at or above ShopGui's) covers a tab" and "the shop window draws above every HUD button it overlaps (DisplayOrder)" (a tie, or the same ScreenGui, counts as "may draw above"); "the SHOP button is where the shared HUD layout puts it" proves the model on the real button. Seven static "layers:" checks hold the table above (the tray under the HUD, the HUD under the shop window, the shop window on the windows' layer 5, the SHOP button on the HUD's layer, the reveal and the poach result above, the toast in ShopGui, IgnoreGuiInset off). On the old ShopClient the new checks fail 558 times (every landscape phone); now 0. **Mutants (4):** ShopGui back at DisplayOrder 0, the SHOP button back in the window's ScreenGui, the SHOP button's ScreenGui at 5 (each caught by "no HUD button that may draw above the shop ... covers a tab"), ShopGui at 3 (caught by "layers: the shop window is on the windows' layer").

**A harness bug found on the way (fixed in the same commit):** the mutation runs (4 threads) captured `static_checks`' FAIL lines with `contextlib.redirect_stdout`, which swaps the process-wide `sys.stdout`; two threads doing it at once can leave `sys.stdout` pointing at another thread's buffer. With the new layer checks (they read every client script, so `static_checks` takes longer) it happened on both of the first two full runs: the run ended with exit code 0 but without its "Shop mutations" and summary lines, and a mutant's static FAIL lines could be counted for another mutant. `static_checks` now returns its FAIL lines in a list (`out=`) in the mutation runs and never redirects `sys.stdout`.

### Item 2: the scroll jump (applied)

**Checked:** true. The Office's layout hook ran `refreshOffice()` and then `revealHero()` on every `applyLayout`: a message line appearing and going away 3.5 s later, a TutorialBanner change, a new screen size; `showTab("Office")` and opening the shop revealed it too. On the old ShopClient the new checks measure it: a player scrolled to the bottom of the Office (the locked rungs) is sent back to the hero (`0 of 209` at 667 x 375 / 36 when a message line appears; `241 -> 0` on a new screen size at 568 x 320 / 58; at 568 x 320 / 58 a tab tap, the message going away, the strip going away and reopening the shop all moved a page scrolled to the top back to 31).

**Fix (ShopClient only; ShopLayout.revealScroll is unchanged, it is only called less):** `office.reveal` is set by a hero change (the list arriving, also after a Retry, and the fold after a buy) and by a successful buy ("Bought!" shows whole); `refreshOffice` reveals once when it is set, and otherwise only clamps the player's own scroll to the new canvas (`min(y, canvas - view)`). The layout hook, `showTab` and `setOpen` no longer reveal. OWNER DEFAULT 5. A Retry needs no flag of its own: after a failed load there is no hero, so the list arriving is a hero change.

**Found on the way, fixed in the same commit:** TycoonCore sets the `Upgrade<i>` attribute before it answers, so for the moment between the two the client saw the upgrade as owned: it folded, the next rung became the hero (the page scrolled to it), then the answer made the bought rung the hero again ("Bought!", the page scrolled back), and 0.8 s later it folded for real: the page could jump twice right after a buy. While the request runs, a rung the attribute already shows as owned now stays the hero and says "Bought!" (`ladderNow`, `office.buying`). Tested in both orders (the attribute first, the answer first).

**What it means for the tutorial strip:** the hero is still fully visible above the strip when the strip is up as the hero becomes the hero (the old check, now with the banner set before the list arrives, on every phone and top bar, 0, 1, 3 and 5 owned). A strip that appears later keeps the player's place: with no upgrade owned the hero is at the page's top and always shows whole; with some owned, on the lowest landscape windows (568 x 320 and 667 x 375 under a 58 px bar) the strip can cover up to 19 px of the hero's bottom until the next buy. TutorialClient (not written yet) should set `TutorialBanner` when its step starts, before the player opens the shop, or accept that.

**Tests:** "office scroll" at 667 x 375 / 36, 320 x 568 / 36 and 568 x 320 / 58: a message line appearing and going away, the TutorialStrip appearing and going away, a tab tap, closing and reopening and the refresh every second never move the page; a new screen size keeps the place, clamped. "office buy reveal" (both orders): the rung never flips to the next one while the request runs, the card says Bought! whole after a buy that started partly scrolled away, the next hero shows whole. "office retry reveal" (568 x 320 / 58, 3 owned): after a Retry the hero shows whole. **Mutants (7):** the hero revealed on every placing again, a tab tap reveals it, opening the shop reveals it, a new screen size never clamps, a buy does not show the card whole, the rung folds while its request runs, a hero change does not reveal (each caught by its named check: see the list below). Mutant 57's target moved with `ladderNow` (same rule: `busy` passed as false).

### Item 3: a message at close (applied)

**Checked:** true. `setOpen(false)` hid the window and left `statusText` set: the message went away with the window and nobody saw it (on the old ShopClient the new check finds no toast, its text still the default `Label`). The same happened when another window opened (the `OpenPanel` handler hides the shop without `setOpen`).

**Fix (ShopClient only), OWNER DEFAULT 4:** `statusToToast()` runs on both ways the shop closes (its X or the SHOP button through `setOpen(false)`, and another window opening): the window's line is cleared (its own timer is cancelled with `statusToken`) and the text goes to `showToast`, in the toast's own lane (bottom center, 16 px up, 48 px, at most 520 wide) for its own 3.5 s. Once: it is in one place at a time; reopening the shop moves a toast that is still up into the line again, as before. No message, no toast.

**Tests:** "message at close" at 667 x 375 / 36 (the X), 320 x 568 / 36 (the SHOP button) and 568 x 320 / 58 (another window opening): the message moves to the toast, the line is cleared, the lane, 3.5 s, then gone for good, no toast when there was no message. **Mutants (3):** closing the shop drops the message, another window opening drops it, the moved message stays in the window's line too.

## Deviations from docs/SHOP_UX_PROPOSAL.md (and why)

1. **The rail starts at the window's top, beside the header** (3.10 drew it under a full-width header, title 488 px). Under the header, 5 tabs (Studio's Debug) did not fit at the reference 667 x 375 with a 58 px top bar, nor 4 tabs at 568 x 320 with 58 px. Now the title is right of the rail (367 px at 667 x 375 / 36), and the pages are the proposal's (x 120 to the right edge, y 50 to the bottom: 473 x 241, the proposal's 474 x 242 rounded down, like the window, 613 x 311 instead of 614 x 312). The rail never scrolls with the live game's 4 tabs; with Studio's 5 it scrolls only at 568 x 320 under a 58 px bar.
2. **The bottom slot (TutorialStrip, status line) is under the pages only**, never under the rail (so the rail keeps its height). In landscape it is the pages' width: 473 px at the reference, about 50 characters on one line at 16 px, not the 60 that TUTORIAL_PROPOSAL section 3 estimated at 594 px. **TutorialConfig's texts for steps 1 and 4 must fit about 50 characters on one line in landscape.**
3. **The status line shares the bottom slot with the TutorialStrip** (one hides the other for 3.5 s) and pushes the pages up while it shows. Office results go in the hero card's own line (3.2); everything else (passes, products, the save warnings) uses the window's line.
4. **The help card has a Back button** and covers the pages and the bottom slot (not the tabs). At 568 x 320 under a top bar its three lines need a scroll; at the two reference phones they fit on one screen.
5. **The portrait hero is 202 px, not 168:** it holds the bar, a two-line time or message row (16 px) and a full-width 48 px button under the name; 168 had no room for a two-line message. Portrait then shows summary + hero (280 px) above the strip (296), and without the strip the first locked rung shows 64 of its 72 px.
6. **Office rows are 72 px on a portrait page** (64 in landscape): a second 16 px line for a long name or "Unlocks after Coffee Machine". Their icon box is 48 px (the proposal said 56): S2 keeps the emoji (S3 brings the icons).
7. **"about N s" becomes "about N min" from 2 minutes and "about N h" from 2 hours**, so a long wait never reads "about 5000 s". Never negative or infinite, none at Income 0.
8. **With the strip up the summary row stays** (the proposal hid it): the Office page scrolls just enough to show the hero whole (`revealScroll`); at 667 x 375 / 36 both fit (64 + 6 + 132 = 202 of 203 px). The Office page places its rows itself (`ShopLayout.stack`, 6 px apart, no UIListLayout) so the hero's position is known at once.
9. **The "Office complete" banner sits at the top of the page**, above the summary (the proposal does not say where), and the page scrolls back to it after the last buy.
10. **"Need more" at Income 0** says "Your Income is $0 a second right now" (the proposal only gave the time hint).
11. **BEST VALUE (an S4 item) is built here** because the task lists the best-value badge among ShopLayout's functions that ShopClient uses. The other S4 badges stay today's states (the "Owned" and "Coming soon" buttons, the "Active: 12:34 left" and "You have N" lines); no ribbon, no details sheet, no sorting.
12. **Not built (other PRs):** tab badges (3.1's gold dot and timer pill), drawn tab icons (S3), the Office prop turning on a tap (3.4, needs S3's 3D icons), the tutorial's step list behind "?" (TutorialClient does not exist yet: the card is the proposal's fallback), the pending ring (S4), the confirm (S5).
13. **The Office keeps its landscape layout down to 360 px wide** (`ShopLayout.OFFICE_WIDE`), Robux cards switch at 420 (`WIDE_CARD`): at 568 x 320 the page is 372 px and the 202 px portrait hero would not fit above the strip.
14. **Robux cards keep their whole description on the card** (the sheet is S4): at 16 px they are taller than before. Measured in the fake (text widths estimated): 108 to 188 px on a 320 x 568 phone (Luck Boost 188, was 96), 84 to 162 px at 667 x 375; on 568 x 320 under a 58 px bar with the tutorial strip, Luck Boost's 148 px card is taller than the 133 px page and needs a scroll.

## Questions for the owner

1. The portrait hero card is 202 px tall (the proposal said 168). Keep it, or make it shorter with a one-line message?
2. Long waits read "about N min" or "about N h" instead of only seconds. All right?
3. Messages while the shop is open use a line at the window's bottom (shared with the tutorial strip). All right, or somewhere else?
4. BEST VALUE shows now (it was planned for S4). Keep it, or wait for S4?
5. The help card's three lines are mine (ShopClient.lua `HELP_LINES`): change the wording?
6. The tab rail starts at the window's top, the title right of it (367 px at 667 x 375). All right?
7. CLAUDE.md does not list `ShopLayout` yet (it was not claimed). Add a line in a later docs PR?
8. A long pop-up (only while the shop is closed) may be cut on a narrow phone: it keeps its 48 px lane, which TaskClient's tray tests rely on. Grow it (a lane change, TaskClient's tests), or keep the server's long messages shorter?
9. The proposal's two open questions (section 7: the cap of 8 ViewportFrames, "where it stands") are untouched: they belong to S3.

## Judgment calls

- **One commit per sub-step**, with two exceptions said in the checklist: 2.2 and 2.3 were pushed together (2.2 alone fails daily_test's old check), and the S1 checks and mutants went in one commit.
- **The fake Roblox is strict:** setting an unknown property or one of the wrong type errors like Roblox, `Destroy` locks the Parent, and the Office and the tabs are checked against ShopLayout's rectangles through a small layout engine (UDim2, AnchorPoint, UIPadding, UIListLayout, UISizeConstraint, ScrollingFrame canvases and scrolling).
- **Text measure:** the client asks `TextService:GetTextSize` (Roblox's own font metrics), so a box is as tall as its real text; the fake estimates Gotham at 0.56 em a lowercase letter, 0.70 a capital, bold 6 % wider, 1.25 lines: on purpose a little wider than the real font.
- **D9:** the source scan allows only the eight string literals with the four words that ShopClient already had (luckText's line, two Debug row texts, one Debug action name, four attribute and perk names); ShopLayout has none; a runtime scan reads every text the shop writes itself (header, tabs, Office, help, strip, status). `luckText` is checked to be exactly the old function, and Luck Boost's card face still starts with it.
- **Luck Boost** stays hidden while `RandomRestricted` is not `false` (unknown or true), and its tap never prompts there.
- **`layout()`'s topBar** moves nothing (with IgnoreGuiInset = false the GUI is already below Roblox's top bar); it only fills `L.device`, so a check can name the phone. The tests run every phone with a 0, 36 and 58 px bar.
- **No server file changed:** ShopServer, TycoonCore, the configs, every save and remote are untouched; `tools/daily_test.py`'s 20 Office purchase mutants still pass on TycoonCore's real code.

## Blocked

Nothing was blocked. Every precondition held, no file this job needed was claimed by someone else, and the push to `shop-build` worked.

## Risks

1. **Text widths.** Fixed boxes (tab labels, buttons, the header, the badge, the hero's lines) can still cut a text the estimate said would fit; descriptions and the help lines are measured by Roblox and cannot be cut. Test > Device decides (docs/STUDIO_SYNC_SHOP.md (f)).
2. **Scrolling right after a change.** The Office page sets its canvas size and then its scroll in the same step; if Roblox clamps CanvasPosition against an older canvas size, the hero could stay partly out of view until the next buy or tab change. The page has no UIListLayout, which avoids the usual one-frame delay, but this was not seen in Studio.
3. **The rail is a ScrollingFrame:** on a touch screen a tap that starts a small drag may scroll instead of pressing a tab. It only scrolls at all with Studio's 5 tabs on the lowest phone (ScrollBarThickness 0 otherwise).
4. **Rotated frames (the check mark) and UIStroke (the padlock's shackle)** are drawn shapes whose look the fake cannot judge.
5. **The pages shrink while a message shows** (3.5 s): a card may move under the player's thumb for that time. Nothing covers a button.

## What was not tested (no Studio, no device)

- Nothing ran in Roblox Studio, in a live server or on a phone; the Studio MCP was not used.
- How anything looks: colors, contrast, the drawn check and padlock, the gold banner and badge, the emoji icons in their new boxes, the animations (the fake applies a tween's end state at once and never draws the in-between), the pulse.
- Real text sizes (TextScaled, MinTextSize, wrapping and clipping in Roblox) and real font metrics.
- Touch: taps and drags on the rail and the pages, ScrollingFrame scrolling and its elastic edge, the 44 px targets under a real thumb.
- Roblox's real AbsoluteSize events on rotation, GuiService:GetGuiInset on real phones (36 or 58 px), CanvasPosition clamping.
- Roblox's purchase prompts and the server's answers (both faked: the prompts are recorded, the Office server mirrors TycoonCore.buyUpgrade's order, Cash and messages).
- The Debug tab's server actions (ShopDebug is answered by a fake), and the strip with a real TutorialClient (it does not exist yet).
- Only the owner's eyes can judge: whether the shop now feels less plain, the hero card's weight on the page, whether "Need $X more" and the shake read as "not yet", whether the portrait cards are too tall now that their text stays at 16 px.

## Results (final)

| Suite | Before (`6bc827c`) | After |
|---|---|---|
| `tools/daily_test.py` | 1,772 pass, 20 of 20 mutation runs | 1,780 pass, 20 of 20 (8 new checks: its pad-word scan of every `.lua` file now also reads `ShopLayout.lua`) |
| `tools/shop_ux_test.py` | (new) | 5,092 pass (5,043 in the fake place, 34 source, 8 hash block, 7 sync table), 67 of 67 mutation runs |
| `tools/world_test.py` | 298 pass, 65 of 65 | 298 pass, 65 of 65 |
| `tools/icon_test.py` | 199 pass, 51 of 51 | 199 pass, 51 of 51 |

`world_test.py --review` and `icon_test.py --review` (the world-icons-pass review: "no existing file edited but CONTRIBUTING.md", "daily_test.py untouched") fail on this branch by design, since S1 and S2 edit ShopClient and daily_test; the default runs above are the ones the task asks for.

**Files:** `ShopLayout.lua` 21,113 bytes, `ShopClient.lua` 53,889 bytes (SHA-256 in docs/STUDIO_SYNC_SHOP.md, checked by `tools/shop_ux_test.py`).

## Mutation runs (67), and the named check that catches each

`python3 tools/shop_ux_test.py --list-mutants` prints the same list from the code. The 32 S1 runs break ShopLayout's layout or ShopClient's window; the 35 S2 runs break the Office ladder.

1. the header 34 px tall (S1): `layout 667x375/0 (4 tabs, none): header items are 44 px tall, "?" and X 44 x 44`
2. a 34 px tab (S1): `layout 667x375/0 (4 tabs, none): every tab is at least 44 x 44`
3. text minimum 8 in ShopLayout (S1): `667x375/0 live Office: no text box with a minimum under 16 px`
4. fitText back to a minimum of 8 (S1): `667x375/0 live Office: no text box with a minimum under 16 px`
5. descriptions at 14 px (S1): `667x375/0 live Office: no text box with a minimum under 16 px`
6. no rail: landscape keeps the row (S1): `layout 667x375/0 (4 tabs, none): landscape has the tab rail on the left (112 wide), portrait the row under the header (decided by the owner)`
7. the bottom slot over the pages (they keep their height) (S1): `layout 667x375/0 (4 tabs, strip): the bottom slot is as tall as asked, under the pages and as wide (never over them or the rail)`
8. the window bigger than the GUI (S1): `layout 667x375/0 (4 tabs, none): the window stays inside the GUI`
9. "?" on top of the X (S1): `layout 667x375/0 (4 tabs, none): header items never overlap and stay inside the window`
10. rail tabs closer than their height (S1): `layout 568x320/58 (5 tabs, none): tabs never overlap each other, the header, the pages or the bottom slot`
11. tab buttons without the Tab prefix (S1): `667x375/0 live: every Name exists after the Office list arrives (Tab*, *Page, Office1-6, HelpButton, TutorialStrip)`
12. pages without their names (S1): `667x375/0 live: every Name exists after the Office list arrives (Tab*, *Page, Office1-6, HelpButton, TutorialStrip)`
13. cards' buttons not named BuyButton (S1): `667x375/0 live: every card's button is named BuyButton`
14. Office cards without their names (S1): `667x375/0 live: every Name exists after the Office list arrives (Tab*, *Page, Office1-6, HelpButton, TutorialStrip)`
15. the help button without its name (S1): `667x375/0 live: every Name exists after the Office list arrives (Tab*, *Page, Office1-6, HelpButton, TutorialStrip)`
16. TutorialStrip shown with no banner (S1): `667x375/0 strip: TutorialStrip is inert while TutorialBanner is unset (hidden, the pages keep their height)`
17. TutorialStrip takes no room from the pages (S1): `667x375/0 strip: TutorialStrip shows the banner's text at the window's bottom, as tall as ShopLayout says`
18. messages always as the toast (S1): `status line: with the shop open a message goes to the status line, never the toast`
19. the status line over the pages (S1): `status line: the status line takes its room from the pages, never covers them`
20. a toast that stays up when the shop opens (S1): `status line: opening the shop moves a toast that is still up into the window's status line`
21. the help card leaves the pages showing under it (S1): `667x375/0 help: the pages hide while the help card is open (it never sits on a Buy button)`
22. the help card's Back button 30 px tall (S1): `667x375/0 help open: every tap target at least 44 x 44`
23. a 40 px Buy button (S1): `667x375/0 live Office: every tap target at least 44 x 44`
24. narrow cards' button 40 wide (S1): `320x568/0 live Passes: every tap target at least 44 x 44`
25. wide cards' description under the button (S1): `cards: every piece inside its card, none on another, a 48 px button at least 44 wide, boxes as tall as their texts`
26. prompts without the isForSale check (S1): `Robux prompts: an item isForSale refuses (an egg item while EggsEnabled is off) is never prompted`
27. Luck Boost shown to a restricted player (S1): `Luck Boost (RandomRestricted unknown): Luck Boost hidden while RandomRestricted is not false, shown when it is false`
28. an unknown RandomRestricted counted as not restricted (S1): `Luck Boost (RandomRestricted unknown): Luck Boost hidden while RandomRestricted is not false, shown when it is false`
29. a price sent from the client (S1): `wiring: a Buy tap sends only "BuyUpgrade" and the upgrade's number (no price, no Cash)`
30. a new text with the word chance (S1): `ShopClient.lua: every string with odds, chance, luck or random was already there (luckText, Debug rows, attribute names; D9)`
31. luckText reworded (S1): `ShopClient.lua: luckText is the function it was (Luck Boost's numbers on its card face)`
32. the strip 20 px tall on a short window (S1): `layout 667x375/36 (4 tabs, strip): the strip is 32 px on a short window, 48 otherwise`
33. a wrong next index (the rung after the first not owned) (S2): `ladder: 0 owned, $0, $0/s: the next rung is the first not owned (k + 1)`
34. the bar not clamped (S2): `barFill stays in 0..1 for every Cash and price (negative, NaN, huge, a free price)`
35. Buy shown when the Cash is short (S2): `ladder: 1 owned, $24, $0/s: the hero's button (Get it free, Buy $X, or Need $X more when the Cash is short)`
36. Need more sends the buy anyway (S2): `office need more (Income $3): Need more sends nothing`
37. the strip over the hero (a hero too tall for the page) (S2): `office strip 667x375/58, 0 owned: the hero is fully visible above TutorialStrip`
38. the hero never scrolled into view (S2): `office strip 667x375/58, 1 owned: the hero is fully visible above TutorialStrip`
39. a missing Retry (S2): `office retry: after the 5 tries: the sentence and a Retry button (44 px or more)`
40. Retry does nothing (S2): `office retry: Retry shows the gray rungs again while it asks`
41. only one try before the error (S2): `office retry: the Office asks 5 times, 2 s apart, before it gives up`
42. no skeleton rungs while loading (S2): `office skeleton: three gray skeleton rungs while Upgrades is asked (no rung, no error yet)`
43. the skeleton rungs stay after the list arrives (S2): `office skeleton: the skeleton rungs go away once the list arrives, and the six rungs exist`
44. minutes shown as seconds (S2): `timeText: 5,000 s reads about 84 min, a million about 278 h`
45. the time rounded down (S2): `timeText: $25 at $1/s is about 25 s, at $2/s about 13 s (rounded up)`
46. locked rungs name themselves (S2): `ladder: 0 owned, $0, $0/s: owned rungs say Owned, locked rungs say Unlocks after <the one before> and offer no button`
47. the summary counts one too many (S2): `ladder: 1 owned, $24, $0/s: the summary says k of 6 bought and what they earn`
48. a locked rung offers a button (S2): `office 667x375, 0 owned, $0: owned rungs fold into the summary row; locked rungs are shown, a padlock, Unlocks after <the one before>, no button`
49. owned rungs never fold (S2): `office 667x375, 1 owned, $24: owned rungs fold into the summary row; locked rungs are shown, a padlock, Unlocks after <the one before>, no button`
50. no Office complete banner (S2): `ladder: 6 owned, $0, $0/s: all six bought: the Office complete banner, no hero`
51. the complete banner left scrolled away (S2): `office complete after the last buy: the Office complete banner shows at the top (the page scrolled back up)`
52. a refusal not shown in the card (S2): `office refusal (Too fast): the card shows the answer in red`
53. no pop and no float on success (S2): `office buy: on success the icon pops (1 to 1.08 and back) and +$2/s floats up from the button`
54. the bought rung folds at once (no Bought!) (S2): `office buy: the server said yes: the card says Bought! a moment`
55. the free Desk says Buy $0 (S2): `office desk: the free Desk says Get it free, its bar full, Free`
56. Buy offered while the request runs (S2): `ladder: while the request runs the hero says ... and sends nothing more`
57. no busy state: a second tap sends again (S2): `office buy: a second tap while the request runs sends nothing`
58. an Office buy asks for a second tap (a confirmation) (S2): `office buy: one tap sends the buy at once: an Office upgrade never asks for a confirmation`
59. the bar's fill never set (S2): `office 667x375, 0 owned, $0: the bar's fill is the ladder's, clamped to 0..1`
60. no shake on Need more (S2): `office need more (Income $3): the bar shakes and the card says about 5 s at your Income`
61. the hint without the time (S2): `office need more (Income $3): the bar shakes and the card says about 5 s at your Income`
62. a pulse on Need more (S2): `office pulse ($10): a soft pulse every 4 s on an affordable Buy, none on Need more`
63. the pulse every second (S2): `office pulse ($30): a soft pulse every 4 s on an affordable Buy, none on Need more`
64. narrow rows too short for two lines (S2): `office rows and the hero: every piece inside, none on another, 48 px buttons, 64 or 72 px rows, a 132 or 202 px hero`
65. the reveal scrolls past the hero's top (S2): `revealScroll: never past the hero's top, never past the canvas`
66. BEST VALUE on a Coming soon item (S2): `BEST VALUE is never on a Coming soon item (the Vault not on sale: the Bag)`
67. BEST VALUE on the worst pack (S2): `BEST VALUE is the Vault (180 minutes for R$ 299 beat 45 for 99 and 10 for 29)`
