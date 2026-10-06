# Shop UX proposal: a store you want to open

Design only (2026-10-06, branch `world-icons-pass`, from `main` `e3c9e67`). No script was changed. Line numbers are `main` `e3c9e67`. **(estimate)** = not measured from code (text widths depend on the font); every other size below is computed from the code. Written for the owner and the Claude sessions that will build it. The owner's six decisions of 2026-10-06 are marked **DECIDED BY THE OWNER**.

The owner's complaints: the shop is plain, not interactive and not UX driven, and the icons are emoji.

## 1. What the shop does today

**Window and tabs (ShopClient.lua)**
- HUD button `ShopButton` (an emoji cart over the word SHOP), 76 x 76, slot 1 of the shared HUD layout: a column on the left, or a 64 x 64 top row when the GUI is under 460 px tall (:80-114).
- Window: 0.92 x 0.92 of the screen, at most 640 x 470, 10 px padding (:133-150); title "Startup Shop" (:152-161), red X 44 px wide (:163-174), a tab bar (:176-187) and the pages under it (:189-194).
- Tabs `Office`, `Passes`, `Boosts`, `Cash`, plus `Debug` in Studio (:196-199): unnamed equal-width `TextButton`s (:201-213) over unnamed `ScrollingFrame` pages with a vertical list (:215-228). The shop opens on Office once at start (:744), then reopens on the last tab (`setOpen` never calls `showTab`, :717-729).
- `applyLayout` (:298-326): window height under 330 = "short" (header 34, tabs 34, else 40 and 42); width under 480 = "narrow" (button 92 instead of 124, icon 36 instead of 52, cards 96 tall instead of 84).

**Cards** (`makeCard`, :232-294): one 84 px row per item. The icon is an emoji in a `TextLabel` (:241-251) from the `ShopConfig` `icon` fields (a money bag, a crown, a clover: ShopConfig.lua:38, 47, 130) and TycoonCore's `UPGRADES` (TycoonCore.lua:66-71). Then name (max 20 px), description (max 15 px) and a button on the right. `fitText` lets text shrink down to 8 px (:59-62).

**Buy flow**
- Robux items: `promptPurchase` (:357-389) marks the item pending ("..."), opens Roblox's prompt, unlocks on `PromptGamePassPurchaseFinished` / `PromptProductPurchaseFinished` (:755-771) or after 30 s (:383-388). Nothing is granted on the client.
- Pass states: Owned, "...", Coming soon, "R$ 199" (:452-469). Product states: "...", Coming soon, "R$ n" (:471-494). Cash packs show the Cash they give now (`productText`, :422-427).
- Luck Boost: its card face starts with `luckText` (:399-419): "Odds weight x2 for Rare, Epic, Legendary hires. Unicorn Egg Legendary: 8.00% -> 9.70%" (numbers from CreatureConfig and the player's Talent Scouts level), required by Roblox's Paid Random Items policy. Hidden for restricted players (`changesOdds`, :481; ShopConfig.lua:134, 193-196; D9 option B).
- **The Office tab is built after the server answers:** a `task.spawn` asks `ShopAction` "Upgrades" up to 5 times, 2 s apart (:511-525); on failure it shows "The office upgrades aren't available right now." with no retry (:526-537). Rows have three states (:543-569): owned ("In your garage. Earns +$X every second.", dark green "Owned"), next ("Buy\n$price", green, or gray when Cash is short) and locked ("Buy X first.", "Locked"). A tap sends only the upgrade number (`buyOffice`, :499-509); the server checks everything (TycoonCore.lua:243-288).
- Feedback is a 3.5 s toast at the bottom center (:116-131, 336-347): "Bought Laptop" or the server's refusal. The window refreshes every second while open (:783-788).

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

Descriptions are 15 px at most (about 12 px for 50 characters on portrait **(estimate)**); the X is 44 x 34 and the landscape tabs 34 px tall, under the 44 px tap target.

## 2. Why it feels plain

1. **Every tab is the same list** (upgrade ladder, passes, timed boosts, Cash): emoji, name, gray text, green button.
2. **Emoji** render differently per platform (boxes on older Android), can't take the game's palette, and don't match the 3D props.
3. **The Office tab hides the goal.** Four of six rows say "Locked"; the one that matters shows a gray price with no sense of distance ("$400" when you have $310).
4. **Feedback lands outside the card:** the toast covers the window's bottom, far from the tapped button.
5. **Nothing else reacts to a tap,** and nothing shows what a pass does with your numbers.
6. **Small targets and text** on phones (above).

## 3. The redesign

### 3.1 Structure

- **Tabs stay** `Office`, `Passes`, `Boosts`, `Cash` (and Studio `Debug`), each with a drawn icon and a label.
- **Landscape gets a tab rail** (**DECIDED BY THE OWNER**). On a short window the tabs move to a vertical rail on the left (112 x 44 buttons), freeing the tab row: pages grow from 210 to **242 px**. Portrait keeps the top row (4 tabs of 64 x 44).
- **Header 44 px everywhere** (today 40, or 34): the X and the "?" are 44 wide and as tall as the header (3.5).
- **Badges on tabs:** a gold dot on Office when the next upgrade is affordable; a timer pill on Boosts while Luck Boost or Poach Shield runs. Drawn shapes, never emoji.
- **Sorting:** Office in purchase order. Passes: not owned first, owned below an "Owned" divider. Boosts and Cash: config order, "Coming soon" last.

### 3.2 The Office ladder

**DECIDED BY THE OWNER:** all six rungs are shown, owned ones folded into a summary row, the next upgrade as the hero card with a progress bar, locked ones dimmed with "Unlocks after X". Top to bottom in purchase order:

| State | Row | Shows |
|---|---|---|
| Owned | one summary row, 64 px: "3 of 6 bought", the Income they add; tap to unfold compact rows | 56 px icon, name, "+$5/s", a check mark and "Owned" |
| Next | the **hero card**, 132 px (landscape) or 168 px (portrait) | 72 px icon (the real prop, see 3.6), name, "+$40 every second", a **progress bar** from 0 to the price filled by your Cash, "$1,234 / $1,500", "about 7 s" (from the leaderstats Income, display only), the Buy button |
| Locked | compact, 64 px | dimmed icon with a padlock shape, "Unlocks after Laptop" |

- **Buy states of the hero:** affordable "Buy $1,500" (green, a soft pulse every 4 s); short "Need $266 more" (gray; a tap shakes the bar and says "about 12 s at your Income", no request); the free Desk "Get it free"; "..." while the request runs (`officeBusy` stays).
- **Buy feedback in place:** on success the icon pops (1 to 1.08 to 1 in 0.2 s), "+$40/s" floats up, the hero folds into the summary row (its count goes up) and the next rung becomes the hero. A refusal shows the server's text in the card, in red, for 3 s. No toast while the shop is open (`ShopNotify` goes to the in-card status line).
- **All six bought:** a gold "Office complete" banner with "Your next step: the IPO window" (a hint, no button).
- **Loading and errors:** three gray skeleton rungs while "Upgrades" is asked; on failure the existing sentence plus a 44 px **Retry** (the same 5 tries).
- **Office upgrades never ask for a confirmation** (**DECIDED BY THE OWNER**), whatever the price: the next upgrade always pays back, and 3.3's two-tap confirm never applies to the ladder.

### 3.3 Robux cards (Passes, Boosts, Cash)

- **Card:** 56 px icon slot, name (20 px), one benefit line (16 px, at most about 28 characters on portrait **(estimate)**), price button "R$ 199" (48 px tall). The long description moves to the sheet.
- **Factual badges only** (**DECIDED BY THE OWNER**; hand-picked tags such as "POPULAR" can be added later, when real sales data exists): `OWNED`; `ACTIVE 12:34` (Luck Boost, Poach Shield, from the attributes the card already reads); `3 LEFT` (Instant Hatch tokens); `BEST VALUE` on the Cash pack with the most income minutes per Robux, computed from `ShopConfig` (today 180/299 beats 45/99 and 10/29: the Vault); `COMING SOON` as a ribbon instead of a disabled button.
- **Tap the card (not the button) = details sheet**, a panel sliding up inside the shop window, never a separate pop-up (**DECIDED BY THE OWNER**): 72 px icon, full description, the effect in the player's numbers (2x Cash "Your Income: $12/s, with it $24/s"; a Cash pack "You get $27,000 now"; Poach Shield "Protected until 18:42"), the Buy button, a 44 px "Back".
- **Confirmation** (**DECIDED BY THE OWNER**): Robux buys keep Roblox's own prompt as the only confirmation. Office upgrades never ask. A **two-tap confirm** (the button turns gold, "Tap again: $5,000", for 3 s; a second tap inside the 3 s buys) applies only to buildings and furniture (CUSTOMIZE PR 2 and PR 3, section 4) whose price is more than half the player's current Cash. The share is `ShopConfig.ConfirmCashAboveShare = 0.5`. It has no effect until those items exist.
- **Pending:** a spinning `UIStroke` ring replaces the "..."; the 30 s safety net stays.

### 3.4 What is interactive

- Tap an Office icon: the prop turns once (1.2 s). No camera move and **no "where it stands" text** in S1-S5: the slots (`PlotArt.Layout.itemSlots`, TycoonCore's `itemOffset` :131-135) are server-only (question 2).
- Tap any Robux card: the details sheet. Badges and the bar update live (:783-788).
- Nothing animates by itself except the affordable pulse and the timers.

### 3.5 The "?" button and the tutorial's Names

From TUTORIAL_PROPOSAL section 3 (branch `design-tutorial`), built in S1 so the tutorial can find them: tab buttons `TabOffice`, `TabPasses`, `TabBoosts`, `TabCash`, `TabDebug`; pages `OfficePage`, `PassesPage`, `BoostsPage`, `CashPage`, `DebugPage`; Office cards `Office1` ... `Office6` (the hero is still `Office<i>`); every card's button `BuyButton`; `HelpButton` ("?", 44 x 44 like the X, `AnchorPoint (1, 0)` at `UDim2.new(1, -50, 0, 0)`, left of the X with a 6 px gap), so the title gets **50 px narrower**: `UDim2.new(1, -56, ...)` becomes `UDim2.new(1, -106, ...)` at ShopClient.lua:153 and in `applyLayout` (:305); `TutorialStrip` (a `TextLabel` at the window's bottom, shown while the PlayerGui attribute **`TutorialBanner`**, a string written by TutorialClient, is set; 32 px when short, 48 otherwise, plus a 6 px gap, taken from the pages' height). In landscape the strip leaves 204 px of page beside the rail: the hero card (132) stays visible. The "?" opens the tutorial's step list when it exists; until then a one-screen "How the shop works" card (three lines, no reward).

### 3.6 Icons

Icons come from this branch's `IconArt` / `IconVisuals` (phase 3). **DECIDED BY THE OWNER:** 3D icons (a `ViewportFrame`) only for the Office upgrades and the creatures; everything else is a drawn UI shape (passes, products, eggs, tabs, HUD: coin, crown, shield, certificate, clover...). The shop shows only the six Office props in 3D (the PlotArt prop parts the player sees in the room); the creatures are 3D in their own windows. 56 px on cards, 72 px on the hero and the details sheet. An icon is built when its card scrolls into view, then cached. At most **8 ViewportFrames exist at once on the whole client** (every window, hero card, details sheet and creature icon together: global, not per window), enforced by IconVisuals' one registry (IconVisuals.lua:599), which `show` and `build` both go through; UI-shape icons don't count. The 8 is a guess for low-end phones, with no measurement behind it: a Test > Device check on a weak phone decides, and `Style.viewportCap` (IconArt.lua:48) is the one number to change. Past 8, a 3D icon shows a drawn fallback (outlined shapes on its plate, never an empty slot) until one frees up; hidden or destroyed cards free theirs. Luck Boost's icon shows no odds and no text. The HUD buttons get drawn icons above their words in S3b.

### 3.7 Inventory and "Place now" (CUSTOMIZE PR 3)

CUSTOMIZE section 4: from PR 3 a purchase goes to `stored` (still earning), with "Place now".
- The hero's success state becomes **Place now** (opens edit mode, `OpenPanel = "Office"`, which closes the shop) and **Later**.
- A segmented control atop the Office page: **Upgrades | Storage (n)**; storage rows say "Earning +$15/s from storage" with a 44 px **Place** button; empty: "Nothing in storage. Everything you bought is in your office." Buildings and furniture (`"BuyBuilding"`, `"BuyObject"`) become two more segments later. The buy is unchanged: one charge, the client sends only the number.

### 3.8 Robux items and D9

- **Nothing random is sold for Robux.** Eggs are bought with Cash in the Eggs window; the shop's Robux items are passes, Cash packs, Luck Boost, Instant Hatch and Poach Shield. Luck Boost changes odds, so it keeps today's handling: hidden for restricted players (`changesOdds`, :481), and its `luckText` numbers stay on the card face before buying (Roblox's policy; they do not move into the details sheet).
- New text never uses the words odds, chance, luck or random (`luckText` is the one exception); no badge or animation suggests a surprise or a prize.

### 3.9 Accessibility

- **Text 16 px minimum** for anything a player must read: a `fitText(inst, max, min)` variant with `MinTextSize = 16`; cards keep one benefit line, the rest is in the sheet.
- **44 px tap targets:** X, "?", tabs, Retry, Back, Place; buy buttons stay 48 px tall.
- Color is never the only signal: a check and "Owned", a padlock and "Unlocks after", a bar and a price.
- Contrast stays: white text on `(42, 45, 56)` cards over the `(28, 30, 38)` panel (ShopClient.lua:22-23), about 13:1 **(estimate)**; gold for highlights only.

### 3.10 Proposed layouts

| | Landscape (GUI 667 x 339) | Portrait (GUI 320 x 532) |
|---|---|---|
| Header | 44: title 488 wide, "?" and X 44 x 44 | 44: title 168 wide, "?", X |
| Tabs | rail x 0-112, four 112 x 44 | row y 50-94, four 64 x 44 |
| Pages | x 120-594, y 50-292: 474 x 242 | y 100-450: 274 x 350 |
| Office | summary 64 + hero 132 = 204 (fits 242), the locked rungs scroll | summary 64 + hero 168 + one locked row 64 = 312 (fits 350), the rest scroll |
| Robux cards | 72 px rows: 3 visible | 88 px rows: 3 visible + 62 px |
| With `TutorialStrip` | 204 px left: summary hidden, hero fits | 296 px left: hero fits |

Characters per line are an **estimate** until Test > Device.

## 4. Test plan

New tests go in a new `tools/shop_ux_test.py` (the `world_test.py` pattern: the real ShopClient code in a fake Roblox, plus named mutation runs). The only `tools/daily_test.py` edit is S2's "Locked" check (section 5).

- **Rectangles** of a pure `layout(guiW, guiH)` at 667 x 375, 320 x 568 (top bar 0, 36, 58 px), 568 x 320, 640 x 360, 844 x 390: no header overlap; the window inside the GUI; tap targets 44 x 44 or more; no text under 16 px; the hero above `TutorialStrip`; the toast never over a Buy button.
- **Ladder states** for every owned prefix (0 to 6) and Cash below, at and above the price: the summary count, the next and locked rows ("Unlocks after <previous>"), the button text, the bar clamped to 0..1, "about N s" never negative or infinite (Income 0: no time).
- **Wiring:** the Office sends only `"Upgrades"` and `"BuyUpgrade", index`; "Need more" sends nothing; no prompt for an item `isForSale` refuses.
- **D9:** no new string contains odds, chance, luck or random; `luckText` is the only allowed line; Luck Boost hidden while `RandomRestricted` is not false.
- **Badges and icons:** `BEST VALUE` computed from config (a test changes the minutes and the badge moves), never on a Coming soon item; no badge text outside OWNED, ACTIVE, LEFT, BEST VALUE, COMING SOON; no emoji character anywhere in ShopClient; the 3D icons in the shop are exactly the Office props.
- **Confirm:** a pure `needsConfirm(kind, price, cash)` is true only for a building or furniture priced above `ConfirmCashAboveShare` of the Cash (below, at and above; the share changed in config; the 3 s expiry), never for an Office upgrade or a Robux item.
- **Names:** every name of section 3.5 exists after the Office list arrives.
- **Mutation runs** (at least 15): wrong next index, bar not clamped, Buy shown when short, a price sent, Luck Boost shown to a restricted player, a 34 px tab, text minimum 8, toast over the hero, an Office upgrade that asks to confirm; each caught by a named check.

## 5. PR plan and order

One PR at a time owns `ShopClient` (claim, merge, release). Order (owner default: S1 first, the tutorial builds on its Names, CUSTOMIZE PR 2 and PR 3 after S1):

| # | PR | What | Claims | Size |
|---|---|---|---|---|
| 1 | **S1** | Layout (landscape tab rail), accessibility, the Names, `HelpButton`, `TutorialStrip` / `TutorialBanner`, status line | `ShopClient`; new `tools/shop_ux_test.py` | M |
| 2 | Tutorial PR A | TUTORIAL_PROPOSAL on S1's Names | its own list | |
| 3 | **S2** | Office ladder (all six rungs, summary row, hero, "Unlocks after X") | `ShopClient`, `tools/shop_ux_test.py`, **`tools/daily_test.py`** | M |
| 4 | CUSTOMIZE PR 2 | building engine, `"BuyBuilding"` | its own list (`ShopClient`, `daily_test.py` too) | |
| 5 | **S3** | Icons on cards and tabs | `ShopClient`, `tools/shop_ux_test.py` (`IconArt` / `IconVisuals` merged first) | M |
| 6 | CUSTOMIZE PR 3 + **S6** | edit mode, storage, "Place now" (3.7) | `CompanyClient`, `ShopClient`, `TycoonCore`, `tools/daily_test.py` | M |
| 7 | **S3b** | HUD icons | `EmployeeClient`, `ShopClient`, `PoachClient`, `IpoClient` | S |
| 8 | **S4** | Robux cards: factual badges, details sheet (inside the window), sorting, ribbon | `ShopClient` | M |
| 9 | **S5** | Two-tap confirm for buildings and furniture (never Office) | `ShopClient`, `ShopConfig` (`ConfirmCashAboveShare`) | S |

- **S5 is gated on CUSTOMIZE PR 2 and PR 3:** it has nothing to confirm before buildings and furniture exist. S2 comes before them: PR 3 builds "Place now" on the ladder.
- **S2 and `tools/daily_test.py`:** S2 drops the "Locked" button text ("Unlocks after Laptop"), but `daily_test.py` :4498-4499 (the same check on `customize-pr1`) requires `setButton(button, "Locked", COLORS.disabled, false)`. S2 claims `tools/daily_test.py` and updates that check in the same PR (owner default): only the next rung offers Buy.
- `TycoonCore` keeps sending `icon` in `upgradeList` (:292-298) so an old client still works; S3 stops reading it. No server change, no new remote, no save change: publish with **Shut down all servers** (docs/PUBLISH_RULES.md).
- Each PR: `python3 tools/daily_test.py` and `tools/shop_ux_test.py` pass, F5 without red errors.

## 6. Studio steps by hand (each PR)

1. Pull the branch; paste `ShopClient.lua` over `StarterPlayerScripts > ShopClient` (for S3, first paste `IconArt` and `IconVisuals` into **ReplicatedStorage**). View > Drafts: commit.
2. F5. Open every tab; buy the Desk, wait for the Coffee Machine bar to fill, buy it.
3. Test > Device at 320 x 568 and 667 x 375: nothing cut off, the hero and its button visible, X and "?" easy to hit.
4. Debug "Paid random items: restricted on/off": Luck Boost disappears and comes back.
5. Once merged, publish with **Shut down all servers**.

## 7. Open questions for the owner (most important first)

The six earlier questions are answered (**DECIDED BY THE OWNER**, sections 3.1, 3.2, 3.3 and 3.6). Still unresolved:

1. **The cap of 8 ViewportFrames:** is it right for a weak phone? A Test > Device check decides (3.6); lower `Style.viewportCap` if it stutters.
2. **"Where it stands" on an Office icon:** no text in S1-S5 (3.4). Does the owner want it later? It needs a server change (a `station` field in `upgradeList`, a TycoonCore claim).
