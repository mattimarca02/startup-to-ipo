# Shop UX proposal: a store you want to open

Design only (2026-10-06, branch `world-icons-pass`, from `main` `e3c9e67`). No script was changed. Line numbers are `main` `e3c9e67`. **(estimate)** = not measured from code (text widths depend on the font); every other size below is computed from the code. Written for the owner and the Claude sessions that will build it.

The owner's complaints: the shop is plain, not interactive and not UX driven, and the icons are emoji. (Calls ringing before the Desk is bought is fixed elsewhere.)

## 1. What the shop does today

**Window and tabs (ShopClient.lua)**
- HUD button `ShopButton` (an emoji cart over the word SHOP), 76 x 76, slot 1 of the shared HUD layout: a column on the left, or a 64 x 64 top row when the GUI is under 460 px tall (:80-114).
- Window: 0.92 x 0.92 of the screen, at most 640 x 470, 10 px padding (:133-150); title "Startup Shop" (:152-161), red X 44 px wide (:163-174), a tab bar (:176-187) and the pages under it (:189-194).
- Tabs `Office`, `Passes`, `Boosts`, `Cash`, plus `Debug` in Studio (:196-199). Each tab button is an unnamed `TextButton` of equal width (:201-213); each page an unnamed `ScrollingFrame` with a vertical list (:215-228). The shop opens on Office once at start (:744) and then reopens on the last tab (`setOpen` never calls `showTab`, :717-729).
- `applyLayout` (:298-326): window height under 330 = "short" (header 34, tabs 34, else 40 and 42); width under 480 = "narrow" (button 92 instead of 124, icon 36 instead of 52, cards 96 tall instead of 84).

**Cards** (`makeCard`, :232-294): one 84 px row per item. The icon is an emoji in a `TextLabel` (:241-251, from the `ShopConfig` `icon` fields, emoji such as a money bag, a crown and a clover, ShopConfig.lua:38, 47, 130, and from TycoonCore's `UPGRADES` icons, TycoonCore.lua:66-71). Then name (max 20 px), description (max 15 px) and a button on the right. `fitText` lets text shrink down to 8 px (:59-62).

**Buy flow**
- Robux items: `promptPurchase` (:357-389) marks the item pending ("..."), opens Roblox's prompt, unlocks on `PromptGamePassPurchaseFinished` / `PromptProductPurchaseFinished` (:755-771) or after 30 s (:383-388). Nothing is granted on the client.
- Pass states: Owned, "...", Coming soon, "R$ 199" (:452-469). Product states: "...", Coming soon, "R$ n" (:471-494). Cash packs show the Cash they give now (`productText`, :422-427).
- Luck Boost: its card face starts with `luckText` (:399-419): "Odds weight x2 for Rare, Epic, Legendary hires. Unicorn Egg Legendary: 8.00% -> 9.7%" (the numbers come from CreatureConfig and the player's Talent Scouts level), required by Roblox's Paid Random Items policy. It is hidden for restricted players (`changesOdds`, :481; ShopConfig.lua:134, 193-196; D9 option B).
- **The Office tab is built after the server answers.** A `task.spawn` asks `ShopAction` "Upgrades" up to 5 times, 2 s apart (:511-525). On failure the tab shows "The office upgrades aren't available right now." and has no retry (:526-537). Each row has three states (:543-569): owned ("In your garage. Earns +$X every second." and a dark green "Owned"), next ("Buy\n$price" in green, or the gray price when Cash is short) and locked ("Buy X first." and "Locked"). A tap sends only the upgrade number (`buyOffice`, :499-509); the server checks everything (TycoonCore.lua:243-288).
- Feedback is a toast at the bottom center, 3.5 s (:116-131, 336-347): "Bought Laptop" or the server's refusal. The window refreshes every second while open (:783-788).

**Measured at the two reference phones** (the GUI keeps `IgnoreGuiInset = false`, so a 36 px top bar is subtracted; TUTORIAL_PROPOSAL section 3 uses the same numbers):

| | Landscape 667 x 375 (GUI 667 x 339) | Portrait 320 x 568 (GUI 320 x 532) |
|---|---|---|
| HUD | row, 64 px buttons at y 6-70, x 10-362 | column x 12-88, SHOP y 142-218 |
| Window | 614 x 312 at x 27-640, y 14-325 | 294 x 470 (capped) at x 13-307, y 31-501 |
| Content | 594 x 292 | 274 x 450 |
| Header / tabs | short: 34 / 34, tabs 142 x 34 | 40 / 42, tabs 63 x 42 |
| Pages | y 106-315, **210 px** tall | y 137-491, **354 px** tall |
| Cards | 584 x 84: 2 full + 26 px of a third | narrow, 264 x 96: 3 full + 42 px |
| Card text box | 378 px wide | **106 px wide** |
| Toast | 400 x 48 at y 275-323: over the window's bottom 50 px | 192 x 48 at y 468-516: over its bottom 33 px |

Text: descriptions are 15 px at most; on portrait, 106 px wide, a 50-character description shrinks to about 12 px **(estimate)**. The X is 44 x 34 and the tabs 34 px tall in landscape: under the 44 px tap target.

## 2. Why it feels plain

1. **Every tab is the same list.** Four kinds of thing (an upgrade ladder, passes forever, timed boosts, Cash) look identical: emoji, name, gray text, green button.
2. **Emoji.** They render differently on every platform, can show as boxes on older Android, can't take the game's palette or outline, and don't match the 3D props the player buys.
3. **The Office tab hides the goal.** Four of six rows say "Locked". The one that matters shows a gray price with no sense of distance ("$400" when you have $310).
4. **Feedback lands outside the card.** The toast covers the bottom of the window, far from the button that was tapped.
5. **Nothing reacts to a tap except the buy button,** and there is no way to see what a pass does with your own numbers.
6. **Small targets and text** on phones (above).

## 3. The redesign

### 3.1 Structure

- **Tabs stay** `Office`, `Passes`, `Boosts`, `Cash` (and Studio `Debug`), each with a small drawn icon and a label.
- **Landscape gets a tab rail.** On a short window the tabs move to a vertical rail on the left (112 x 44 each), freeing the tab row: pages grow from 210 to **242 px**. Portrait keeps the top row (4 tabs of 64 x 44).
- **Header 44 px everywhere:** title, the "?" `HelpButton` and the X are all 44 x 44.
- **Badges on tabs:** a gold dot on Office when the next upgrade is affordable; a timer pill on Boosts while Luck Boost or Poach Shield runs. Badges are drawn shapes, never emoji.
- **Sorting:** Office keeps purchase order (the order is the rule). Passes: not owned first, in config order (the owner controls it), owned ones below an "Owned" divider. Boosts and Cash: config order, "Coming soon" items last.

### 3.2 The Office ladder

One column of six rungs, top to bottom in purchase order:

| State | Row | Shows |
|---|---|---|
| Owned | compact, 64 px, or folded into one summary row "3 of 6 bought" (tap to unfold) | 56 px icon, name, "+$5/s", a check mark and the word "Owned" |
| Next | the **hero card**, 132 px (landscape) or 168 px (portrait) | 72 px icon (the real prop, see 3.6), name, "+$40 every second", a **progress bar** from 0 to the price filled by your Cash, "$1,234 / $1,500", "about 7 s" (from the leaderstats Income, display only), the Buy button |
| Locked | compact, 64 px | dimmed icon with a padlock shape, "Unlocks after Laptop" |

- **Buy states of the hero:** affordable "Buy $1,500" (green, a soft pulse every 4 s); short "Need $266 more" (gray; a tap shakes the bar and says "about 12 s at your Income", it never sends a request); the free Desk "Get it free"; waiting "..." while the request runs (`officeBusy` stays).
- **Buy feedback in place:** on success the icon pops (scale 1 to 1.08 to 1 in 0.2 s), "+$40/s" floats up from the card, the hero folds into an owned row and the next rung becomes the hero. A refusal shows the server's text inside the card, in red, for 3 s. The toast is not used while the shop is open (the server's `ShopNotify` text goes to the same in-card status line).
- **All six bought:** a gold "Office complete" banner on top with "Your next step: the IPO window" (a hint, no button that opens another window).
- **Loading and errors:** three gray skeleton rungs while "Upgrades" is asked; on failure the existing sentence plus a **Retry** button (44 px) that runs the same 5 tries.
- **No confirmation for Office buys** (recommended): the next upgrade is the only thing the tab sells and always pays back. If the owner wants one, the same two-tap pattern as 3.3 applies above a `ShopConfig` threshold (question 2).

### 3.3 Robux cards (Passes, Boosts, Cash)

- **Card:** 56 px icon slot, name (20 px), one benefit line (16 px, at most about 28 characters on portrait **(estimate)**), price button "R$ 199" (48 px tall). The long description moves to the details sheet.
- **Factual badges only** (no popularity claims without data): `OWNED`; `ACTIVE 12:34` (Luck Boost, Poach Shield, from the attributes the card already reads); `3 LEFT` (Instant Hatch tokens); `BEST VALUE` on the Cash pack with the most income minutes per Robux, computed from `ShopConfig` (today 180/299 beats 45/99 and 10/29: the Vault); `COMING SOON` as a ribbon instead of a disabled button.
- **Tap the card (not the button) = details sheet**, a panel that slides up inside the window: 72 px icon, full description, and the effect in the player's own numbers: 2x Cash "Your Income: $12/s, with it $24/s"; a Cash pack "You get $27,000 now" (today's `cashPackAmount`); Poach Shield "Protected until 18:42". Buy button repeated at the bottom. Close with a 44 px "Back".
- **Confirmation:** Robux buys keep Roblox's own prompt as the only confirmation (a second confirm costs sales and adds nothing). Cash buys above a threshold (future buildings and furniture, CUSTOMIZE section 4) use a **two-tap confirm**: the button turns gold, "Tap again: $5,000", for 3 s.
- **Pending:** the "..." becomes a small spinning ring drawn with a `UIStroke` (no image); the 30 s safety net stays.

### 3.4 What is interactive

- Tap an Office icon: the prop turns once (a 1.2 s spin in its ViewportFrame) and the card shows "Stands at the left wall, 3rd station" (from `PlotArt.Layout.itemSlots`). No camera move in the first version.
- Tap any Robux card: the details sheet.
- Tab badges and the hero's progress bar update live (the existing 1 s refresh while open, :783-788).
- Nothing animates by itself except the affordable pulse and the timers; icons only move when tapped (IconVisuals rule).

### 3.5 The "?" button and the tutorial's Names

From TUTORIAL_PROPOSAL section 3, built in the first PR so the tutorial can find them: tab buttons `TabOffice`, `TabPasses`, `TabBoosts`, `TabCash`, `TabDebug`; pages `OfficePage`, `PassesPage`, `BoostsPage`, `CashPage`, `DebugPage`; Office cards `Office1` ... `Office6` (the hero is still `Office<i>`); every card's button `BuyButton`; `HelpButton` ("?", 44 px, left of the X, the title 106 px narrower); `TutorialStrip` (a strip at the bottom of the window, 32 px when short, 48 otherwise, plus a 6 px gap, taken from the pages' height). In landscape the strip leaves 204 px of page with the rail (172 px without it): the hero card (132) stays fully visible. The "?" opens the step list of the tutorial when it exists; until then it opens a one-screen "How the shop works" card (three lines, no reward).

### 3.6 Icons

Icons come from this branch's `IconArt` / `IconVisuals` (phase 3): the six Office props are the PlotArt prop parts shown in a `ViewportFrame` (the same shapes the player sees in the room), passes and products are drawn UI shapes (coin, crown, shield, certificate, clover...). 56 px on cards, 72 px on the hero and the details sheet. An icon is created only when its card scrolls into view, cached, and at most **8 live ViewportFrames** exist (IconVisuals' cap; a UI-shape icon doesn't count). Luck Boost's icon shows no odds and no text. The HUD buttons (EGGS, SHOP, TEAM, POACH, IPO) get drawn icons above their words in a later PR.

### 3.7 Inventory and "Place now" (CUSTOMIZE PR 3)

CUSTOMIZE section 4: from PR 3 a purchase goes to `stored`, with "Place now"; stored items still earn.
- The hero's success state becomes two buttons: **Place now** (opens edit mode, `OpenPanel = "Office"`, which closes the shop) and **Later** (keeps the shop open).
- A segmented control on top of the Office page: **Upgrades | Storage (n)**. Storage lists stored items as compact rows "Earning +$15/s from storage" with a 44 px **Place** button. Empty: "Nothing in storage. Everything you bought is in your office."
- Buildings and furniture (CUSTOMIZE `"BuyBuilding"`, `"BuyObject"`) become two more segments later; the ladder stays the first.
- The buy itself is unchanged: one charge, the client sends only the number.

### 3.8 Robux items and D9

- **Nothing random is sold for Robux.** Eggs are bought with Cash in the Eggs window; the shop's Robux items are passes, Cash packs, Luck Boost, Instant Hatch and Poach Shield. Luck Boost changes odds, so it keeps today's handling: hidden for restricted players (`changesOdds`, :481), and for everyone else the exact numbers stay on the card face before buying (`luckText`; Roblox's policy wants them visible before the purchase, so they do not move into the details sheet).
- New text added by the redesign never uses the words odds, chance, luck or random; the existing `luckText` line is the one exception and the tests allow exactly it.
- No badge or animation suggests a surprise or a prize (no "mystery", no spinning reels).

### 3.9 Accessibility

- **Text 16 px minimum** for anything a player must read: a `fitText(inst, max, min)` variant with `MinTextSize = 16`; descriptions shortened to one benefit line on cards, the rest in the sheet.
- **44 px tap targets:** X, "?", tabs, Retry, Back, Place; buy buttons stay 48 px tall.
- Color is never the only signal: owned has a check and the word "Owned", locked a padlock and "Unlocks after", the next rung a bar and a price.
- Contrast stays on the current dark panel (white on `(42, 45, 56)`, about 13:1 **(estimate)**); gold is used for highlights only.

### 3.10 Proposed layouts

| | Landscape (GUI 667 x 339) | Portrait (GUI 320 x 532) |
|---|---|---|
| Header | 44: title 494 wide, "?" and X 44 x 44 | 44: title 174 wide, "?", X |
| Tabs | rail x 0-112, four 112 x 44 | row y 50-94, four 64 x 44 |
| Pages | x 120-594, y 50-292: 474 x 242 | y 100-450: 274 x 350 |
| Office | summary 64 + hero 132 = 204 (fits 242) | summary 64 + hero 168 + one locked row 64 = 312 (fits 350) |
| Robux cards | 72 px rows: 3 visible | 88 px rows: 3 visible + 62 px |
| With `TutorialStrip` | 204 px left: summary hidden, hero fits | 296 px left: hero fits |

Content sizes are computed from the window above; how many characters fit a line is an **estimate** until Test > Device.

## 4. Test plan

All new tests go in a new file, `tools/shop_ux_test.py` (the `building_test.py` / `world_test.py` pattern: the real ShopClient code in a fake Roblox, plus named mutation runs), so no branch fights over `tools/daily_test.py`.

- **Rectangle tests** on a pure `layout(guiW, guiH)` function in ShopClient: at 667 x 375 and 320 x 568 with a top bar of 0, 36 and 58 px, and at 568 x 320, 640 x 360, 844 x 390: header items never overlap; the window stays inside the GUI; every tap target at least 44 x 44; no text box whose minimum is under 16 px; the hero card fully visible above `TutorialStrip`; the toast lane never covers a Buy button while the shop is closed, and is unused while it is open.
- **Ladder states:** for every owned prefix (0 to 6) and Cash below, at and above the next price: which rows are owned, next and locked, the button text ("Get it free", "Buy $1,500", "Need $266 more"), the bar fill clamped to 0..1, "about N s" never negative or infinite (Income 0 shows no time).
- **Wiring:** the Office still sends only `"Upgrades"` and `"BuyUpgrade", index` (the same rule `daily_test.py` pins today); "Need more" sends nothing; a Robux button never prompts an item that `isForSale` refuses.
- **D9:** no new string contains odds, chance, luck or random; `luckText` is the only allowed line; Luck Boost hidden while `RandomRestricted` is not false.
- **Badges:** `BEST VALUE` computed from config (a test changes the minutes and the badge moves), never on a Coming soon item; no emoji character anywhere in ShopClient.
- **Names:** every name of section 3.5 exists after the Office list arrives.
- **Mutation runs** (at least 15): wrong next index, bar not clamped, Buy shown when short, a price sent, Luck Boost shown to a restricted player, a 34 px tab, text minimum 8, toast over the hero, and so on; each caught by a named check.

## 5. PR plan

| PR | What | Files (claims) | Size |
|---|---|---|---|
| S1 | Layout and accessibility: tab rail, 44 px header and targets, 16 px text, the Names, `HelpButton` (simple help card), in-window status line | `ShopClient`; new `tools/shop_ux_test.py` | M |
| S2 | Office ladder: states, progress bar, short state, feedback in place, skeleton and Retry | `ShopClient`, `tools/shop_ux_test.py` | M |
| S3 | Icons in the shop: icon slots on cards and tabs, lazy creation, the cap | `ShopClient`; `IconArt`, `IconVisuals` (this branch, merged first) | M |
| S3b | HUD icons on EGGS, SHOP, TEAM, POACH, IPO | `EmployeeClient`, `ShopClient`, `PoachClient`, `IpoClient` | S |
| S4 | Robux cards: badges, details sheet, sorting, Coming soon ribbon | `ShopClient` | M |
| S5 | Two-tap confirm for Cash buys above a threshold | `ShopClient`, `ShopConfig` (`ConfirmCashAbove`) | S |
| S6 | Storage and "Place now" | with CUSTOMIZE PR 3: `ShopClient`, `CompanyClient` | M |

- `TycoonCore` keeps sending `icon` in `upgradeList` (:292-298) so an old client still works; S3 simply stops reading it. No server change in S1-S5, no new remote, no save change: publish with **Shut down all servers** as always (docs/PUBLISH_RULES.md).
- Each PR: claim its files, `python3 tools/daily_test.py` and `tools/shop_ux_test.py` pass, F5 without red errors.

## 6. Studio steps by hand (each PR)

1. Pull the branch. In Studio, open `StarterPlayer > StarterPlayerScripts > ShopClient`, select all, paste the new `ShopClient.lua`. For S3 first create `IconArt` and `IconVisuals` (ModuleScripts) in **ReplicatedStorage** and paste them.
2. View > Drafts: commit the drafts.
3. F5. Open the shop on each tab; buy the Desk, then wait for the Coffee Machine bar to fill; buy it.
4. Test > Device: an iPhone SE (320 x 568) portrait and a 667 x 375 landscape phone. Check: nothing cut off, the hero card and its button visible, the X and "?" easy to hit, text readable at arm's length.
5. Debug tab "Paid random items: restricted on/off": Luck Boost disappears and comes back.
6. Stop, then publish with **Shut down all servers** when the PR is merged.

## 7. Open questions for the owner (most important first)

1. **Landscape tab rail** (recommended: 32 px more page, everything 44 px) or keep the tab row on top?
2. **Confirm Cash buys:** never for Office (recommended), with a two-tap confirm only for future buildings and furniture above a threshold? Which threshold (for example $1,000, or "more than half your Cash")?
3. **Office ladder:** show all six rungs with the locked ones (recommended: the player sees the goal), or only the owned summary and the next one?
4. **Badges:** factual only (OWNED, ACTIVE, LEFT, computed BEST VALUE), or also hand-picked ones like "POPULAR" (needs sales data)?
5. **Icons on phones:** 3D props in ViewportFrames for the Office and the creatures, drawn shapes for the rest (recommended), or drawn shapes everywhere (lighter)?
6. **Details sheet:** a panel that slides up inside the window (recommended: one window at a time) or a separate pop-up?
