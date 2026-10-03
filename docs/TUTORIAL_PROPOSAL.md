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
| 2 | Hire | Hatch the free egg (existing arrow) | employees >= 1 | 1 min Income |
| 3 | Team slots | Open TEAM, see `1/5` and what a hire earns | team window opened once | none |
| 4 | Keep growing | Buy the next Office upgrade | owned >= 2 | 1 min Income |
| 5 | Customer call | Tap a call chip in the tray | one call graded by `TaskServer` | 1 min Income |
| 6 | Daily gift | Tap CLAIM on the chip | `daily.claims >= 1` | the Daily reward itself |
| 7 | Poaching | Open POACH: HR level, shield, "needs another player in your server" | window opened once (never needs a second player) | none |
| 8 | Funding | Open the IPO window: valuation bar, stages | window opened once | none |
| 9 | Going public | Read what an IPO **resets** (Cash, upgrades, eggs in incubators) and **keeps** (employees, passes, HR, Shares, perks), from `IpoConfig.Resets` | "Got it" (never forces an IPO) | none |

Notes:
- **Eggs:** a card for the EGGS button is added to step 2 only while `ShopConfig.EggsEnabled` is true (it is false now), so no card points at a hidden button.
- **Step 5 is skipped** whenever `TaskConfig.isActive()` is false (today: every live server, PR 1 is Studio only). It becomes live with the task engine; no tutorial change needed.
- Steps 3, 7, 8, 9 are info steps with no reward on purpose: nothing to farm.
- Steps are shown one at a time, in order, but each one is **marked done by its own condition** if the player did it early (a player who already claimed the daily skips step 6, without a second reward unless the step's own reward was never paid).
- Existing arrow and goal card stay. While a tutorial card is up, the goal card hides (the same "one thing at a time" idea as `OpenPanel`).

## 3. Phone, skip, replay

- **Highlight:** for a button, a pulsing `UIStroke` outline and a small chevron on the real HUD button (found by name, `AbsolutePosition`). For a world target, the existing 3D arrow. The outline never changes the button's size or hit area.
- **Card placement:** short text, max 2 lines, width `min(360, screenWidth - 24)`, 16 px text minimum shrink via `fitText`. The client picks the screen half **opposite to the target's rectangle**, so the card never covers what it points at. Portrait 320x568: card in the free band above the tray, HUD column on the left stays clear. Landscape 667x375: HUD is a top row, so the card goes bottom center above the task tray, never over the thumbstick or jump button. Pop-ups stay at bottom center, so the card moves up one lane while a toast shows.
- **Windows:** the card hides while a window is open unless the step is about that window (then it docks to the window's top edge as a one-line banner).
- **Skip:** a "Skip tour" link on every card (a confirm tap, one line). Skipping saves `skipped`. Rewards not yet earned are forgone.
- **Replay:** a small "?" button in the **Shop window header** (not a HUD slot: HUD slots 0-4 are taken and the tray and daily chip already own the bottom/side space). It opens a list of the 9 steps; tapping one replays that card with no reward. Reachable by `legacy` players too, who get the list but no automatic tour.
- **Phone test:** `tools/daily_test.py` already checks tray layout at two phone sizes; add the same style of rectangle test (card vs target rect vs HUD vs tray) at 320x568 and 667x375, **with the Roblox top bar** subtracted as the top-bar review did.

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

**New:** `TutorialConfig` (ReplicatedStorage: steps, texts, reward minutes, button names), `TutorialServer` (ModuleScript, `init` / `setupPlayer` / `serialize`, plugged in after `DailyServer`, inside the all-modules-loaded gate), `TutorialClient` (LocalScript, card, outline, replay list). New remotes `TutorialRemotes` / `TutorialAction` (`TutorialState` to the client).
**Edited (claims needed first):** `TycoonCore` (require, `KNOWN_SECTIONS`), `ShopClient` ("?" button in the header), `OnboardingClient` (hide goal card while a tutorial card is up; may also need an `OpenPanel`-style attribute). `README.md`, `CLAUDE.md` (module list, remotes, section shape) and `docs/PUBLISH_RULES.md` get doc lines. **The CONTRIBUTING claim was skipped on purpose** (other sessions own that file); it must be added when the build starts, and the Ownership table checked for TycoonCore, ShopClient and OnboardingClient.

**PR plan (size):**
1. PR A, **server + config + save** (about 450 lines): `TutorialConfig`, `TutorialServer`, `TycoonCore` plug-in, tests in `tools/daily_test.py` (completion, one-time reward, bad input, old save loads, no valuation change). No visible UI. Medium.
2. PR B, **client cards and highlights** (about 500 lines): `TutorialClient`, phone layout tests, Studio phone check. Medium.
3. PR C, **replay "?" + skip + docs** (about 150 lines): `ShopClient`, PUBLISH_RULES 2d. Small.

**Test plan:** the script tests above; Studio F5 as a new player (Debug "Restart onboarding" must also clear `tutorial`) through all 9 steps; early-completion case; skip then replay; rejoin mid-tour; old save (no tour); Test > Device at 320x568 and 667x375 (cards never over the pointed button, thumbstick, jump button or tray); `UserOwnsGamePassAsync` untouched; publish with **Shut down all servers**.

**Open questions for the owner:**
1. Rewards: keep the small Cash gifts (3 minutes of Income in total), or no rewards at all (simplest, and no economy risk)?
2. Should existing players (`legacy`) get the tour once as an opt-in card, or only the "?" replay list?
3. Is the tour one linear sequence, or should steps 6-9 appear the first time the player meets each system (daily chip, first poach window, first stage)?
4. Step 5 (calls) is Studio only today: ship the tutorial without it now, or wait for the task engine's PR 2?
