# Tutorial proposal: "explain everything"

Design only (2026-10-04, branch `design-tutorial`, from `cb326d8`). No script was changed. The ROADMAP line "Later: Tutorial that explains everything" is the source. Written for the owner and Claude sessions that will build it.

## 1. What exists today, and what is missing

**Exists (M5, OnboardingServer / OnboardingConfig / OnboardingClient):**
- A new save gets one free Garage Egg, already incubating (works while `EggsEnabled = false`).
- A 3D glowing arrow (beam + chevron, client-only) toward a ready egg, the next affordable upgrade sign, or the incubating egg. It ends for good (`arrowDone`) at 1 employee and 2 upgrades.
- A goal card under the valuation bar: "Hire 3 employees", "Reach Seed stage". No reward. Closable (`dismissed`). Old saves are `legacy` (nothing shown).
- All of it is server-driven through player attributes; the only client request is `DismissTracker`.

**Missing:**
- No text explains anything. After "Seed" the player is alone.
- Nothing points at a **UI button**: the arrow is a world object, and since the pads were removed, upgrades live in SHOP > Office (`ShopAction` "Upgrades" / "BuyUpgrade").
- Nothing teaches: the HUD (EGGS, SHOP, TEAM `n/5`, POACH, IPO), customer calls (the tray), the daily CLAIM chip, HR and poaching, or what an IPO resets and keeps.
- No way to replay anything, and old saves (`legacy`) see none of it.

## 2. Proposed steps (9, one screen each)

Each step is one short card (title, 1-2 lines, one button "Got it" or no button when the player's own action completes it). The **server** decides completion from its own data; the client only displays. Rewards are Cash gifts in the Daily style: minutes of Income, floor `DailyConfig.MinCash`, never through `addEarnings`, so they never raise the IPO valuation. Values live in a new `TutorialConfig`; the whole tour is worth less than Day 1 of the calendar (5 min of Income).

| # | Step | Player does | Completes when (server) | Reward |
|---|------|-------------|-------------------------|--------|
| 1 | Your office | Open SHOP > Office, buy Desk (free) | `owned` contains Desk | none (the Desk pays) |
| 2 | Hire | Hatch the free egg (existing arrow; the card also outlines the EGGS button, which is always there) | employees >= 1 | 1 min Income |
| 3 | Team slots | Open TEAM, see `1/5` and what a hire earns | team window opened once | none |
| 4 | Keep growing | Buy the next Office upgrade | owned >= 2 | 1 min Income |
| 5 | Customer call | Tap a call chip in the tray | one call graded by `TaskServer` | 1 min Income |
| 6 | Daily gift | Tap CLAIM on the chip | `daily.claims >= 1` | the Daily reward itself |
| 7 | Poaching | Open POACH: HR level, shield, "needs another player in your server" | window opened once (never needs a second player) | none |
| 8 | Funding | Open the IPO window: valuation bar, stages | window opened once | none |
| 9 | Going public | Read what an IPO **resets** (Cash, upgrades, eggs in incubators, valuation) and **keeps** (employees, HR, passes, boosts and shields, Shares, perks and IPO count); sources in the notes | "Got it" (never forces an IPO) | none |

Notes:
- **Eggs:** the EGGS button is never hidden. `ShopConfig.EggsEnabled` (false now) is read in one place, `ShopConfig.isOnSale` (line 194): it only stops shop items marked `needsEggs` (Robux egg items) from being sold. EmployeeClient builds `EggsButton` (HUD slot 0) unconditionally (line 175), and Cash eggs and the free Garage Egg work with the flag off (OnboardingConfig line 19). So step 2 always outlines EGGS; the only thing `EggsEnabled` changes for the tour is that no card may point at a Robux egg item (it never does, section 5).
- **Step 9's list, and where each item really comes from.** Only part of it is config. `IpoConfig.Resets` (lines 53-58) has four keys: `Cash`, `Upgrades`, `Eggs` (true: reset) and `HRDepartment` (false: kept). TycoonCore's `commitIpo` (lines 544-587) applies exactly those four. The rest is hardcoded text in IpoClient, true because of what the server code doesn't touch:
  - **Resets, from `IpoConfig.Resets`:** Cash, garage upgrades, eggs in incubators (names from `IpoConfig.ResetNames`, read through `IpoConfig.resetItems(true)`).
  - **Resets, hardcoded:** "your valuation (for the next IPO)" (IpoClient line 519). The server side is IpoServer building the new `ipo` section with the valuation at 0.
  - **Keeps, from `IpoConfig.Resets`:** HR Department (`HRDepartment = false`, via `resetItems(false)`).
  - **Keeps, hardcoded in IpoClient (lines 526-531):** "Employees" (`commitIpo` never touches `team.employees`), "game passes" (owned on Roblox, not saved), "Luck Boost, Instant Hatches and shields" (`shop` and `poach` sections, not touched), "your Shares" and "IPO shop perks and your IPO count" (copied into the new `ipo` section by IpoServer).
  - **So** `TutorialConfig` must not claim step 9 reads "from `IpoConfig.Resets`". Either the step 9 card reuses IpoClient's own wording (best: build it from `IpoConfig.resetItems` plus the same fixed list, moved into `IpoConfig` as a `Kept` list both clients read; that is an `IpoConfig` + `IpoClient` claim in PR B), or the text is fixed in `TutorialConfig` with a test that compares it with IpoClient's list.
- **Step 5 is skipped** whenever `TaskConfig.isActive()` is false (today: every live server, PR 1 is Studio only). It becomes live with the task engine; no tutorial change needed.
- Steps 3, 7, 8, 9 are info steps with no reward on purpose: nothing to farm.
- Steps are shown one at a time, in order, but each one is **marked done by its own condition** if the player did it early (a player who already claimed the daily skips step 6, without a second reward unless the step's own reward was never paid).
- Existing arrow and goal card stay. While a tutorial card is up, the goal card hides (the same "one thing at a time" idea as `OpenPanel`).

## 3. Phone, skip, replay

- **Highlight:** for a button, a pulsing `UIStroke` outline and a small chevron on the real HUD button (found by name, `AbsolutePosition`). For a world target, the existing 3D arrow. The outline never changes the button's size or hit area.
- **Card placement:** short text, max 2 lines, width `min(360, screenWidth - 24)`, 16 px text minimum (`fitText` with `MinTextSize = 16` set on the card: the shared helper's minimum is 8). The client picks the screen half **opposite to the target's rectangle**, so the card never covers what it points at. Portrait 320x568: card in the free band above the tray, HUD column on the left stays clear. Landscape 667x375: HUD is a top row, so the card goes bottom center above the task tray, never over the thumbstick or jump button. Pop-ups stay at bottom center, so the card moves up one lane while a toast shows.
- **Windows:** the card hides while any window is open (`OpenPanel` set). Steps 3, 7 and 8 show their text **before** the window opens (the card points at the HUD button) and complete when it opens, so nothing is drawn over the Recruiting, Poaching or IPO windows and their scripts need no change. Only the Shop steps (1 and 4) need text while their window is open; that text goes in the **Shop banner strip** below.
- **Shop banner strip (steps 1 and 4).** Measured from ShopClient.lua. `ShopGui` keeps `IgnoreGuiInset = false`, so on a 667x375 phone with a 36 px top bar the GUI is 667x339. The window is `0.92` of it (lines 133-143, max 640x470): 614x312 at x 27-640, y 14-325 (GUI px). That leaves **only 14 px above and below the window and 27 px at each side**, so a banner outside the window does not fit in landscape (without a top bar it is 15 px). Window height 312 is under 330, so `applyLayout` uses the short header (lines 298-311): with the 10 px padding, title and X at y 24-58, tab bar y 64-98, pages y 106-315 (210 px tall). The banner therefore goes **inside the window, as a strip at its bottom, and the pages get shorter by the strip's height**, so it never covers the header, the "?" or the tab bar, and covers no card (the page scrolls):
  - ShopClient owns it: a `TextLabel` named `TutorialStrip`, shown while the PlayerGui attribute `TutorialBanner` (a string, written by TutorialClient) is set. `applyLayout` subtracts its height from `pages.Size`: **32 px (one line) when `short`**, 48 px (two lines) otherwise, plus a 6 px gap. In the worst case (667x375, 36 px bar) pages keep 172 px: the first Office card (84 px) and most of the second stay visible. Portrait 320x568 with a 36 px bar: GUI 320x532, window 294x470, not short, pages 354 px, minus 54.
  - Text: `fitText` uses `MinTextSize = 8` (line 61), so the strip sets `MinTextSize = 16` itself. One line at 16 px is about 60 characters at 594 px wide (landscape), and two lines of about 28 characters at 274 px (portrait): `TutorialConfig` texts for steps 1 and 4 must fit that.
  - TutorialClient scrolls the target card into view above the strip (`CanvasPosition` on the Office page) before outlining its Buy button.
  - The phone keeps its touch controls hidden while a window is open (`GuiService.TouchControlsEnabled`, line 725) and the tray hides, so neither is a concern inside the window.
- **Names to add in ShopClient** (today the tab buttons, pages, cards and card buttons have none, they are all `TextButton` / `Frame` / `ScrollingFrame`): tab buttons `Tab<name>` (`TabOffice`, `TabPasses`, `TabBoosts`, `TabCash`, `TabDebug`; line 202), pages `<name>Page` (`OfficePage`, ...; line 215), Office cards `Office1` ... `Office6` (an optional name for `makeCard`, line 232; set for the Office cards at line 539) and every card's button `BuyButton` (line 279), the new `HelpButton` ("?") and `TutorialStrip`. TutorialClient finds them by these names under `ShopGui.Window`.
- **The Office cards exist only after the server answers.** They are built in a `task.spawn` after `ShopAction:InvokeServer("Upgrades")` succeeds (up to 5 tries, 2 s apart, lines 511-578); on failure the tab shows "The office upgrades aren't available right now." and no cards. TutorialClient waits for `Office1` (`ChildAdded` on `OfficePage`, with a timeout) and, without it, outlines only `TabOffice` with the same text.
- **The Shop reopens on the last tab.** `setOpen` never calls `showTab` (lines 717-730; `showTab("Office")` runs once at start, line 744). So for steps 1 and 4 TutorialClient first checks `OfficePage.Visible`; if another tab is showing, the outline goes on `TabOffice` and the strip says "Tap Office", and only then on the card's `BuyButton`.
- **Skip:** a "Skip tour" link on every card (a confirm tap, one line). Skipping saves `skipped`. Rewards not yet earned are forgone.
- **Replay:** a small "?" button in the **Shop window header** (not a HUD slot: HUD slots 0-4 are taken and the tray and daily chip already own the bottom/side space). It opens a list of the 9 steps; tapping one replays that card with no reward. Reachable by `legacy` players too, who get the list but no automatic tour.
  - **Size and place:** `HelpButton`, 44 px wide like the X, as tall as the header (40, or 34 when `short`), `AnchorPoint (1, 0)`, `Position UDim2.new(1, -50, 0, 0)` (left of the X with a 6 px gap).
  - **The title gets narrower in both places**, from `UDim2.new(1, -56, ...)` to `UDim2.new(1, -106, ...)`: where it is made (line 153) and in `applyLayout` (line 305). `applyLayout` also sizes the "?" to the header height, next to the X (line 306). At 320x568 the title keeps about 168 px for "Startup Shop", at 667x375 about 488 px.
- **Phone test:** `tools/daily_test.py` already checks tray layout at two phone sizes; add the same style of rectangle test (card vs target rect vs HUD vs tray) at 320x568 and 667x375, **with the Roblox top bar** (0, 36 and 58 px, as `TRAY_TESTS` does) subtracted. For the Shop: the strip vs the title, "?", X and tab bar (no overlap) and the pages' height above the strip (at least one full Office card, 84 px or 96 px when narrow).

## 4. What must be stored

**A new save section is needed: `tutorial`.** The reason is rule A10 in CLAUDE.md, which applies to every feature, whatever the section it could have shared:

> **New saved data gets its own top-level section (rule A10).** Older code keeps unknown *top-level* sections, but it drops unknown *fields inside* a section it knows (`team`, `poach`, `ipo`, ...). So a new feature never adds a field to an existing section: it adds a new section (with its own `serialize`, an entry in `KNOWN_SECTIONS`, optional on load).

So the tutorial's flags do not go into `onboarding`, even though `OnboardingServer` itself would not lose them: since M5 step 1 (`8fe325f`) it copies any field it doesn't know into `onboarding.unknown` and writes it back (`KNOWN_FIELDS`, OnboardingServer.lua lines 34, 241-245, 281-285), and it keeps every finished goal key that is a string, even keys its config doesn't list (lines 233-240). A10 is the project rule, not a gap in onboarding. The section:

```lua
tutorial = {                -- TutorialServer.serialize (optional: older saves have none)
  done = { [stepKey] = true },   -- finished steps; a paid reward is the same flag, set in the same save
  skipped = boolean,             -- the player skipped the tour
}
```

- Add it to `KNOWN_SECTIONS` in TycoonCore; optional on load; unknown keys and bad types skipped with a warning; written only once there is something to keep.
- **Needs "Shut down all servers"** (like `daily`, `onboarding`, `tasks`). The rollback floor stays `V_launch`; a rollback keeps the section frozen and loses nothing. Add a short "2d" note to docs/PUBLISH_RULES.md in the build PR.
- Per-run facts (IPO count, `team`) are not stored here; step conditions read live data, so nothing depends on frozen state.
- Reward and `done[key]` are set **in the same synchronous block**, before the next yield, like the Daily claim; the existing `data.loaded` check and one-save-at-a-time lock apply.
- Existing players (`legacy`, or saves with progress): no automatic tour; steps whose condition is already true are never paid (no back-pay), they only appear in the replay list.

## 5. Exploits and D9

- **Server grades everything it can.** The client sends `"Dismiss"`, `"Skip"`, `"Replay"` with a step *number*, and `"Opened"` with a window name (below), never a reward or a time. The server checks type, range, `data.ready`, and that the step is the current one, and debounces like `DailyConfig.ClaimDebounce` (1 s).
- **The `"Opened"` message is client-reported, and the server cannot check it.** No server tracks window opens today: `OpenPanel` is a PlayerGui attribute written only by the client scripts (ShopClient line 720, EmployeeClient 745, PoachClient 792, IpoClient 896, DailyClient 534), and nothing on the server reads it. So steps 3, 7 and 8 complete on the client's word:
  - **Remote:** `TutorialRemotes.TutorialAction` (RemoteFunction made by `TutorialServer.init`), call `TutorialAction("Opened", windowName)`. No step number: the server maps the window to the step.
  - **Payload:** one string, the window's `OpenPanel` value. Whitelist in `TutorialConfig`: `"Recruiting"` (step 3), `"Poaching"` (step 7), `"Ipo"` (step 8). Anything else (other strings, other types, `"Shop"`, `"Daily"`) is refused without a warning per call.
  - **Checks:** `data.ready`, the window's step is not done yet, and a rate limit of one `"Opened"` per player per second plus at most 10 per minute (spam is refused, like `HR_BUY_MIN_INTERVAL` in PoachServer).
  - **`"Recruiting"` is both tabs.** EmployeeClient opens one window for the EGGS and the TEAM buttons (`PANEL_NAME = "Recruiting"`, `toggle("Eggs")` / `toggle("Team")`, lines 23, 766-769), so the server cannot tell which tab was seen. Step 3 accepts `"Recruiting"` from either button; the card text names the TEAM button. A tab field in the payload would add nothing, because the client could send any tab.
- **This is harmless only while these steps pay nothing.** A cheater can send `"Opened"` without opening anything, and all they gain is a finished info step. **If a client-reported step ever pays Cash** (or Shares, or anything saved besides `done`), it stops being safe: the reward must then move to a step the server can grade from its own data (`owned`, `team.employees`, `daily.claims`, a graded call), or the window opening must become a server request (for example the window asks the server for its contents first, like the Office tab's `"Upgrades"` call, and the server marks the step on that request). A test should fail if a step whose completion is `"Opened"` has a reward above 0.
- **No farming:** each reward is paid once per save (`done`), is small, is Cash-gift only, and the info steps pay nothing.
- **IPO resets do not reset the tutorial** (`done` is not per run), so it can't be re-earned.
- **Nothing random, no Robux:** no egg rolls, no odds text, no product, no pass prompt. Any text about eggs uses neither "chance" nor "odds" (D9, same rule as `TaskConfig`). The only egg is the existing free fixed one. The tour never points at paid items (SHOP > Boosts, passes) and shows no prices in Robux.
- No `Touched` handler, no new `addEarnings` call (so `tools/daily_test.py`'s call-site list stays unchanged).

## 6. Scripts, PR plan, open questions

**New:** `TutorialConfig` (ReplicatedStorage: steps, texts, reward minutes, button names), `TutorialServer` (ModuleScript, `init` / `setupPlayer` / `serialize`), `TutorialClient` (LocalScript, card, outline, replay list). New remotes `TutorialRemotes` / `TutorialAction` (`TutorialState` to the client).

**Module order: `TutorialServer` runs before `DailyServer`, never after.** CLAUDE.md says `DailyServer.setupPlayer` runs last, inside the all-modules-loaded gate (the `pcall` setup block, TycoonCore.lua lines 765-800, with `DailyServer.setupPlayer` at line 799 and `TaskServer.setupPlayer` just before it at line 798; `init` order at lines 672 and 685). So TutorialServer plugs in **between `TaskServer` and `DailyServer`**: `TutorialServer.init` after `TaskServer.init` and before `DailyServer.init`; `TutorialServer.setupPlayer` after `OnboardingServer.setupPlayer` (it needs `data.onboarding.legacy`), `EmployeeServer` and `TaskServer`, and before `DailyServer.setupPlayer`. Consequences:
- At `TutorialServer.setupPlayer` time `data.daily` does not exist yet, so `setupPlayer` only loads the `tutorial` section and never evaluates step conditions. Conditions (step 6's `daily.claims`, and all others) are checked after setup, once `data.ready` is true: in TutorialServer's own 1 s loop, like OnboardingServer's (OnboardingServer.lua line 340).
- `save()` only writes when every module's data is there (the `data.daily and data.tasks)` check in TycoonCore); `data.tutorial` joins that check, and the payload gets `tutorial = TutorialServer.serialize(data)` next to `tasks`.
- CLAUDE.md's module paragraph gets "`TutorialServer` plugs in after `TaskServer` and before `DailyServer`" in the build PR.
**Edited (claims needed first):** `TycoonCore` (require, `KNOWN_SECTIONS`), `ShopClient` ("?" button in the header and narrower title, the `TutorialStrip` and its `applyLayout` lines, the Names listed in section 3), `OnboardingClient` (hide goal card while a tutorial card is up; may also need an `OpenPanel`-style attribute). `README.md`, `CLAUDE.md` (module list, remotes, section shape) and `docs/PUBLISH_RULES.md` get doc lines. This proposal doc was claimed in CONTRIBUTING.md while it was being fixed and released after; the build needs its own claims, after checking the Ownership table for TycoonCore, ShopClient, OnboardingClient and `tools/daily_test.py`.

**PR plan (size):**
1. PR A, **server + config + save** (about 450 lines): `TutorialConfig`, `TutorialServer`, `TycoonCore` plug-in, tests in `tools/daily_test.py` (completion, one-time reward, bad input, old save loads, no valuation change, and the **required ordering test** below). No visible UI. Medium.

   **Required ordering test** (to add in PR A; not added now: `tools/daily_test.py` is owned by the `test-gap-fixes` work). Today the test only checks Task before Daily (`tools/daily_test.py` lines 4048-4051). The new checks, in the same style, on `TycoonCore.lua`:
   - `TutorialServer.init(` comes after `TaskServer.init(` and before `DailyServer.init(`.
   - `TutorialServer.setupPlayer(` comes after `OnboardingServer.setupPlayer(`, `EmployeeServer.setupPlayer(`, `IpoServer.setupPlayer(` and `TaskServer.setupPlayer(`, and **before `DailyServer.setupPlayer(`** (Daily stays last).
   - `tutorial = true` is in `KNOWN_SECTIONS`; the payload has `tutorial = TutorialServer.serialize(data)`; the save gate includes `data.tutorial`.
   - A step whose completion is `"Opened"` has reward 0 (section 5).
2. PR B, **client cards and highlights** (about 500 lines): `TutorialClient`, phone layout tests, Studio phone check. Medium.
3. PR C, **replay "?" + skip + docs** (about 150 lines): `ShopClient`, PUBLISH_RULES 2d. Small.

**Test plan:** the script tests above; Studio F5 as a new player (Debug "Restart onboarding" must also clear `tutorial`) through all 9 steps; early-completion case; skip then replay; rejoin mid-tour; old save (no tour); Test > Device at 320x568 and 667x375 (cards never over the pointed button, thumbstick, jump button or tray); `UserOwnsGamePassAsync` untouched; publish with **Shut down all servers**.

**Open questions for the owner:**
1. Rewards: keep the small Cash gifts (3 minutes of Income in total), or no rewards at all (simplest, and no economy risk)?
2. Should existing players (`legacy`) get the tour once as an opt-in card, or only the "?" replay list?
3. Is the tour one linear sequence, or should steps 6-9 appear the first time the player meets each system (daily chip, first poach window, first stage)?
4. Step 5 (calls) is Studio only today: ship the tutorial without it now, or wait for the task engine's PR 2?
