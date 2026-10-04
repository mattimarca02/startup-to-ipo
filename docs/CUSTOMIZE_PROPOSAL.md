# Companies, sectors and the Pokedex (proposal, design only)

Design only (2026-10-04, branch `design-customize`, revised after an independent review and for owner decision D-F). No script, config or test changed. For the owner and the Claude sessions that will build it. Line numbers are for this branch, whose `.lua`/`.py` files equal `visuals-garage` `7f5c141` (`main` has no PlotArt, PlotVisuals or Office tab; `visuals-garage` `37ea6b9` changed only daily_test.py since, moving its lines). **(unverified)** = not checked in code; **(estimate)** = not measured; **(owner default)** = the owner may still veto; **(placeholder)** = sized by the sims.

**Fixed by the owner:** **D-A** a bigger building contains the previous one; objects move in at the same coordinates from a door-side anchor. **D-B** an IPO founds a new company, seeded with some of the old one's money (never items). **D-C** every founding starts with picking a sector. **D-D** a sector is a full package on one engine; Software (today), Fintech, Biotech, Gaming launch together. **D-E** free placement, phone and PC. **P-1** one Pokedex entry per sector. **P-2** an IPO completes the company and stamps its sector; the old company is a card. **P-3** all four sectors = the main goal (Hall of Fame); replays earn Gold and Platinum; a leaderboard. **P-4** old companies earn nothing; stamps give a small capped bonus. **P-5** the seed stays. **Inventory:** a purchase goes to the inventory, with "Place now". **D-F funding rounds:** reaching a stage by valuation lets the player raise a round of a size they pick; it gives Cash only, costs dilution (fewer IPO Shares), and the room follows the building owned, not the stage (1.7).

**Owner defaults:** employees follow the player; creatures keep their bodies, renamed per sector; 5 buildings per sector (building 5 serves Series C+D to IPO-ready); any sector can be picked next; an unplaced item still earns; largest size **78 x 82**; hire desks fixed in v1; furniture earns nothing; a free, fixed starter set per building (D9); 45° rotation; part budget open until a phone test; the CLAUDE.md DataStore exception (**awaiting owner approval**, section 7).

**New names** (none exists in any `.lua`/`.py`): `CompanyServer` (owns `pokedex`; `raiseRound`), `CompanyConfig` (with `Funding`), `SectorConfig`, `Sector<Name>`, `SectorArt<Name>`, `CompanyClient`, `CompanyRemotes.CompanyAction`, `BoardServer`, OrderedDataStores `Collection_v1`, `HallOfFame_v1`.

## 1. Companies, sectors and the Pokedex

**1.1 A company** is one run of one sector's ladder: Cash, upgrades, buildings, furniture, layout, eggs in incubators, valuation, funding rounds and dilution. **The player** keeps the rest: employees, HR level, passes, boosts, shields, Shares, perks, IPO count and multiplier, `lifetime`/`best`, daily, onboarding, task stats, the Pokedex, kept decor (today's rule: IpoConfig.lua:6-8, 51).

**1.2 The `pokedex` save section (new top-level section, rule A10).** The active company's live state stays where it is (`cash`, `owned`, `team`, `ipo.valuation`; TycoonCore.lua:421-433), so older code keeps playing it. The section holds what older code cannot know:

```lua
pokedex = {                  -- CompanyServer.serialize (optional)
  v = 1,                     -- format version
  run = number,              -- ipo.count the active company belongs to (run check)
  active = {
    sector = "Software",     -- SectorConfig key: never renamed or reused
    picked = boolean,        -- false = picker open; PickSector only then
    name = string,           -- from the sector's fixed list
    foundedAt = os.time(),
    engaged = number,        -- weighted engaged seconds (stamp clock)
    passSeconds = { [passKey] = n },  -- of those, with each Cash pass owned
    building = number,       -- buildings bought, 1 = Garage; decides the room
    decor = { [objectKey] = n },                                   -- furniture owned
    objects = { { id = "Desk", x = -23, z = -40, r = 0 }, ... },  -- placed items
    told = { [stageKey] = true },       -- "you can raise a round" was sent (1.7)
    rounds = { [stageKey] = { s = "raised" or "skipped", c = choice, cash = n, bp = n, at = os.time(), studio = boolean } },
  },
  sectors = {                -- no entry = not started
    [sectorKey] = {
      state = "progress" or "done",  -- "done" never goes back
      stamp = 0 to 3,        -- best: 1 Bronze, 2 Gold, 3 Platinum
      replays = number, firstAt = os.time(), bestEngaged = number,
      card = { name, ipoNumber, at, engaged, ratio, building, owned = {...}, decor, objects, rounds, stake, shares },
    },
  },
  kept = { [objectKey] = n },  -- earned decor: free in every company
  hallAt = number,           -- all four first done (0 = not yet)
  studio = boolean,          -- saved by a Studio server: never on the live board
}
```

- **Fields:** `id` = an upgrade name or `<objectKey>#<n>`; `x`, `z` from the anchor, step 0.5; `r` 0-7; at most 40; owned without an entry = in the inventory. `ratio` = IPO valuation / IPO-ready valuation. About 11 KB **(estimate)**.
- **Loader: KEEP at every level.** Unknown fields are written back, as in onboarding (OnboardingServer.lua:226, 243, 281), daily (DailyServer.lua:244, 261, 290), tasks (TaskServer.lua:712, 766, 800) and fixedHires (EmployeeServer.lua:657, 675, 694), but at **every** level: the section, `active`, `sectors[k]`, `card`, `objects[i]`, `told`, `rounds`, `rounds[k]`, `card.rounds[k]`. Those four keep top-level fields only; shop, team, poach and ipo keep none (EmployeeServer.lua:648).
- **Versioning:** `v` rises only when a field changes meaning; a higher `v` is held as one opaque value, written back unchanged, and the session refuses `GoPublic`, `Place`, `BuyBuilding`, `PickSector`, `Raise`; with an unknown sector key `BoardServer` writes nothing. *Tests:* `v = 2` deep-equal after a save; each refusal.
- **Bad values** (type, NaN, infinite, negative, out of range, unknown or duplicate id) are skipped with a warning; `stamp` clamped; `"done"` with stamp 0 becomes 1. Rounds: 1.7.
- **Wiring:** `KNOWN_SECTIONS` (TycoonCore.lua:84), `buildPayload` (:421-433), save gate (:481); daily_test.py:4269-4271 changes in the same PR. Publish with Shut down all servers; rollback floor stays `V_launch` (M4+ code keeps unknown sections, TycoonCore.lua:773-777, 434-438).
- **No legacy migration:** nothing is launched (PUBLISH_RULES.md:17, 101); all test accounts are wiped together before launch (`RemoveAsync` on a written list, :111). **A missing `pokedex`** = a new founding: `run = ipo.count`, Software, `picked = true` while the picker is off, building 1.
- **A10 run check:** `run ~= ipo.count` means an older version ran an IPO (TycoonCore.lua:549-559; no seed, no dilution). IPOs need the valuation (IpoServer.lua:192-195), so the sector gets `"done"`, Bronze if unstamped and a card (its `rounds` unchanged); the new company keeps the sector, `picked = false`, building 1.

**1.3 Picking a sector, on every founding.** A window (`OpenPanel = "Sector"`): four cards (icon, name, how it makes money, stamp, "New"); for a new player, in every IPO and after a run check. `CompanyAction("PickSector", key)` only while `picked == false`. Any enabled sector, the same included; Bronze needs a new one, and the picker preselects one. `SectorConfig.PickerEnabled = false` until all four exist.

**1.4 The IPO completes the company.** Today `goPublic` (IpoServer.lua:177-243) checks, then `commitIpo` (TycoonCore.lua:544-588) saves with a transform resetting Cash, `owned` and eggs (IpoConfig.lua:53-58). New:
1. The picker before Confirm; `IpoAction("GoPublic", ipoNumber, sectorKey)` adds a sector check to `ipoNumber == count + 1` (IpoServer.lua:179).
2. **One transform, one save** (TycoonCore.lua:548-564): `"done"`, `stamp = max(stamp, earned)`, `replays`, `firstAt`, `bestEngaged`, the `card`; `hallAt` on the fourth; a new `active` (building 1, no rounds); `run = count + 1`; Cash = `StartingCash` + seed.
3. Only after that save works (:565-587): the Garage room, a stamp pop-up, the board write.

**The card** is in a new **Pokedex** tab of the IPO window (IpoClient.lua:354): sector, name, stamp, IPO number, date, engaged hours, ratio, founder stake and a **top-down map** (Frames per footprint). `ResetNames` (IpoConfig.lua:60-65) and the keep list (IpoClient.lua:524-533) add buildings, furniture, stamps, rounds.

**1.5 Stamps, replays, Hall of Fame.**
- **Bronze:** first completion, bonus +1.5%. **Gold:** a replay within **1.0 T** engaged hours, +0.5%. **Platinum:** within **0.8 T** at ratio **≥ 1.25**, +0.5%. **T** = the loop's reference hours for a regular player (LONG_GAME section 1: 57 / 51.5 / 52 h); **placeholders** (S6). The clock is the server's, weighted like the valuation (LONG_GAME_PROPOSAL.md:23): Gold and Platinum wait for LONG_GAME PR 2.
- **Pass fairness:** 2x Cash shortens a run about 15% (LONG_GAME section 6), so a target shrinks by that times the **share of the run's engaged seconds with the pass** (`passSeconds`), never by passes owned at founding (an exploit). A replay is priced by IPO count only. **Hall of Fame:** all four `"done"`: `hallAt`, a title, a gold frame, a board entry.

**1.6 Leaderboard.** Today in-server only (IpoServer.lua:46-63; IpoClient.lua:750-786); no OrderedDataStore exists (docs/reviews/FULL_REVIEW.md:126).
- **Ranks:** **Collection** = `1000 x stamp points + min(IPO count, 999)` (Bronze 1, Gold 2, Platinum 3); **Hall of Fame** = earliest `hallAt`. `BoardServer` writes `Collection_v1`, `HallOfFame_v1` (in `pcall`, key UserId) from the loaded `pokedex` after the stamp's save; repairs a lower value on join; reads the top 50 every 10 minutes. No client sends a score.
- **Studio never reaches the live board.** Studio and live share the save key (PUBLISH_RULES.md:46): every Studio save sets `pokedex.studio = true` (never cleared); a `studio` account is never written, repaired or shown; Studio writes only `_Studio` twins; a deny list (`BoardServer.REMOVED`) is never written or shown. *Test (fake stores):* a `studio` save with four Platinum joins live: no write.
- **Names (FR-11):** `UserService:GetUserInfosByUserIdsAsync` (`pcall`, cached; **unverified limits**), "Player" on failure; the client escapes `& < > " '` (fixes IpoClient.lua:780).

**1.7 Funding rounds (D-F, owner decision).** Every number is a **placeholder** for S8; nothing is random (D9).
- **What opens a round:** the **valuation** (never Cash) reaching a stage after the first: Seed, Series A, Series B today (IpoConfig.lua:17-23), plus Series C+D and Pre-IPO with LONG_GAME's 7 stages. IPO-ready has no round: it is the IPO. The stage is `IpoConfig.stageIndex(ipo.valuation, ipo.count)` (IpoConfig.lua:151-159); it never falls during a run (IpoServer.lua:122-135).
- **A round gives Cash and nothing else:** no building move, no Income change. The stage's building is buyable in SHOP > Office once the stage is reached, raised or not; the room follows the building owned (section 6). The Cash buys anything.
- **Flow:** (1) stage reached: one message per stage per company (`told`); the valuation bar reads "Raise a round ›" while a round is open (section 4). (2) The **Funding window**: 3 choices (Small, Medium, Large), each with its Cash, the share given away, the IPO Shares after it and the stake left; a choice over the cap is locked. (3) **Raise** (pick, then confirm "Raise $X for Y%"): Cash at once. **Later** keeps the round open. **Skip this round** (with a confirm) closes it for this company.
- **One round per stage per company,** settled in stage order; an open round stays open at the next stage; all close at IPO-ready (raised Cash could then only feed the seed). **Never raising** is a full path: no dilution, all the Shares, "Bootstrapped: 100% stake" on the card, no extra reward.
- **Amount:** choice i gives `cashPct[i] x IpoConfig.stageValuation(stage, ipo.count)` (IpoConfig.lua:140-143): stage and IPO count only, never Cash, Income, passes or stamps. Placeholders: 10 / 20 / 30% for 3 / 7 / 12% dilution (convex); **total dilution capped at 40%** (`DilutionCap`). Income is untouched. Data: `CompanyConfig.Funding` (shared engine, keyed by `IpoConfig.Stages` keys), `Enabled`, `StudioOnly`.
- **Saved** (`pokedex.active`): `told[stageKey]`; `rounds[stageKey]` = `s`, `c` (choice), `cash`, `bp` (dilution in basis points, whole, 0-10000, **as applied**, never recomputed from a later config), `at`, `studio`. `D = min(DilutionCap, Σ bp) / 10000`, derived on load. A round under an **unknown stage key** is kept and its valid `bp` still counts (a newer version's round dilutes an older version's IPO). A malformed record of a known stage counts as settled with `bp` 0 and a warning, never dropped (that would allow a second raise).
- **The card keeps** `rounds` as they were, `stake` (10000 - D in bp) and `shares` (paid after dilution and pass): "Founder stake 70% · 3 rounds · $X raised" or "Bootstrapped".

## 2. The sector package and content

**Shared engine** (never names a sector; a test fails on a sector key in engine code): `pokedex`, picker, IPO flow, stamps, seed, bonus, funding rounds, board; buildings, placement, inventory; SHOP > Office; tasks; creatures, eggs, odds, `fixedHire` (D9), poaching; daily, onboarding, HUD; the economy clock; the sim.

**Per sector** (`Sector<Name>`, `SectorArt<Name>`): identity (key, name, icon, palette, 12+ company names); 5 buildings; upgrades (keys never reused; Software keeps today's six, TycoonCore.lua:65-72); furniture; tasks (`TaskConfig.Rows`, TaskConfig.lua:49); creature names and jobs (CreatureConfig.lua:56-104); egg names; one income model; bundles with fixed contents, `id = 0`. Art in PlotArt's `P(...)` format (PlotArt.lua:9-23).

**Income models** (deterministic, capped, engaged only; **placeholders**, S3). Software: steady Income. The others, `Sector<Name>.extra(data, seconds)`, compute Cash from **base Income** (TycoonCore.lua:677-680) and add it to the **existing income-loop call** (:866): **no new call site** (daily_test.py:4327-4334); never in offline pay (:825) or `baseIncome`. **Fintech:** interest on Cash held, capped at H seconds of base Income. **Biotech:** every N engaged minutes (a visible timer, never a roll) P seconds of base Income. **Gaming:** a graded Timing task (paid through TaskServer.lua:257) starts a launch: Income x L for D minutes, then a cooldown. **Parity:** item Incomes are lowered until each sector is within ±5% of Software per engaged hour, every rung and `LONG_PLAYERS` profile (S3), with no bot or hopper gain (S4, S5).

**Content:** the content bible names 168 things for Software (CONTENT_BIBLE.md:300-361); **its decor is earned** (:261, 268, 278, 280; choice 5, :369), **bought here:** an earned piece goes to `kept`. Per new sector about 185 names and 75 art builds **(estimate)**.

## 3. Plot space (re-verified in the code)

- **Code:** `PLOT_SPACING = 90`, `MAX_PLOTS = 6` (TycoonCore.lua:74, 76); `plotCenter` x = -225 + 90 x (slot - 1), z 150 (:123-126); `Floor` 60 x 60 (:736): z 120-180. Front = +Z (signs, TycoonCore.lua:75, IpoServer.lua:21; spawn :698-700). **Anchor = front-center of the floor, z 180.** VIP Lounge z 57.5-82.5 (ShopServer.lua:35-37, 636-650), its door `Touched` (:683) the only one, a non-VIP inside sent to **z 88** (:839); skyline z 101-107 (PlotArt.lua:699-707).
- **Size:** a shell adds 2.3 per side (BUILDING_PASS_PROPOSAL.md section 3): 90 - W - 4.6 ≥ 6 gives **W = 78**; 180.2 - D - 2.3 ≥ 94 gives **D = 82**. Nested **(estimate)** 60 x 60, 64 x 66, 68 x 70, 72 x 76, 78 x 82; no plot moves; **Baseplate 534+ wide (unverified).** The skyline (`BACKDROP_Z`, PlotVisuals.lua:44) goes; 60 x 60 assumptions go per building (PlotArt.lua:31; PlotVisuals.lua:544, 590-592, 643). **Owner, in Studio (read only):** Baseplate, SpawnLocation, anything at z 85-120 or past x ±225, Terrain, StreamingEnabled.

## 4. The office: placement, inventory, checks, budget, phone

- **Fixed:** Floor (the only solid), spawn lane, signs, incubators (EmployeeServer.lua:37-40), hire spots and desks (:31-35). **Movable or stored:** upgrade props (default = today's slot, TycoonCore.lua:131-135, 189) and furniture. **Move-in (D-A):** `objects` stay; building n+1 contains n; the new area gets the starter set.
- **Inventory:** a purchase goes to the **inventory** (owned minus `objects`); **"Place now"** opens edit mode; an item left stored **still earns** (Income reads `owned`, TycoonCore.lua:137-145). In PR 3 `buyUpgrade` (:272-288) drops the pop-in (:285), the join loop (:811-815) draws only placed objects, the Office tab (ShopClient.lua:496-573) gains "Place now" and "In storage". **The buy is unchanged:** one charge after `checkUpgradePurchase` (:243-270); "Place" never charges.
- **Checks** on `CompanyAction` (`"Place", id, x, z, r`; `"Store"`; `"Sync"`; `"PickSector"`): `data.ready` (IpoServer.lua:212-213); `id` a string under 40 chars, finite `x`/`z`, whole `r` 0-7; ownership; inside the building; overlap ≤ 0.1 stud; no reserved zone (`PlotVisuals.zones`, :504-531); budgets; 4 requests/s. **One pure function in `CompanyConfig`:** the client previews, the server decides. Placement never changes Income; **no `Touched` handler** (daily_test.py:4254-4256).
- **Part budget:** `MAX_PARTS = 260`, `MAX_LIGHTS = 3` (PlotVisuals.lua:39-40); rooms use 244-257 (ROADMAP.md:42), props 118 (daily_test.py:3858). **Proposal:** draw only owned desks, 320 per plot, decided at G-S's phone test.
- **Edit mode:** a window (`OpenPanel = "Office"`) from SHOP > Office; top-down camera, about 3.5 px per stud at 78 x 82 on 667 x 339 **(estimate)**; pick strip, pinch zoom, drag, snap 0.5, one `"Place"` on lift; Rotate, Store, Done 56 px; PC: drag, R, Delete.
- **Funding message and window (1.7).** *Measured:* windows are 0.92 of the GUI, max 640 x 470 (ShopClient.lua:133-143, IpoClient.lua:294-301), with 34 px header and tabs under 330 px tall (ShopClient.lua:298-311, IpoClient.lua:789-799); 667 x 375 with a 36 px top bar is a 667 x 339 GUI (ROADMAP "Top-bar review"); every bottom-center lane is taken (-16, -72, -128, -184, -240; daily_test.py:3043).
  - *Message:* one toast in the IPO lane (-16; IpoClient.lua:262-274), no new lane; the valuation bar's top line (`hudStage`, IpoClient.lua:197-207) reads "🌱 Seed · Raise a round ›", and a tap on the bar then opens the Funding window.
  - *Where:* its own window, `OpenPanel = "Funding"` (CompanyClient). One window at a time (ShopClient.lua:713-735), so it never covers the Shop header, design-tutorial's "?" (TUTORIAL_PROPOSAL.md:62) or the tabs. Not a Shop tab (the tutorial strip, TUTORIAL_PROPOSAL.md:53); not a 5th IPO tab (about 49 px wide at 320 **(estimate)**).
  - *Sizes* **(estimates):** 667 x 339: window 614 x 312; header 34, a line 20, three cards side by side about 192 x 120 (Cash, "-7% stake", "IPO: 18 Shares, was 20"), buttons 56 high (Later, Skip, "Raise $X"): 252 of 292 px. Portrait 320 x 532: 294 x 470, cards stacked, 72 high. PC: 640 x 470.
  - *Picking:* tap a whole card, then one confirm naming the amount. **No slider:** none exists in the clients, a drag fights the page scroll and the thumbstick, and the server accepts 3 steps anyway. *Tests* like `TRAY_TESTS` (top bar 0 / 36 / 58): inside the window, ≥ 48 px tall.
- **Shop:** Office gains Buildings and Furniture (`"BuyBuilding", n`, `"BuyObject", n` on `ShopAction`, ShopServer.lua:704-717, 802-805), checked like `checkUpgradePurchase` plus "stage n reached" (valuation, raised or not) and "building n-1 owned". A building costs its LONG_GAME office price; no odds words (daily_test.py:4344).

## 5. Economy: seed, collection bonus, rounds, sims

**5.1 Seed (P-5).** `StartingCash` (0, IpoConfig.lua:44) plus **s% of the old company's Cash, capped at c% of the new first rung's prices** (10 and 25, **placeholders**, S1): a gift (no `addEarnings`), paid once inside the IPO transform.

**5.2 Collection bonus (P-4).** A **Cash multiplier on Income**: +1.5% per Bronze, +0.5% Gold, +0.5% Platinum, **capped at +10%** (**placeholders**, S2), applied with the passes (`updateIncome`, TycoonCore.lua:148-152), **never valuation**, so **0 until LONG_GAME PR 2** (today the income loop, :865-866, and offline pay, :819-827, add the whole Income to it). Never in `baseIncome` (:677-680) or away pay. Stacked: 2x Cash x VIP x 1.10 = x3.3, times the IPO multiplier (no cap, IpoConfig.lua:162-165). **No stamp pays Shares** or changes odds (D9).

**5.3 Risks.** A faster sector becomes the only choice (S3-S5). **Duplicate seed:** paid only in the one transform; `ipoNumber` blocks a repeat (IpoServer.lua:179); a failed save changes nothing (TycoonCore.lua:565-567).

**5.4 Funding rounds: Cash, valuation, Shares.**
- **Not an `addEarnings` call (differs from the brief; owner to confirm).** Every `addEarnings` raises valuation, lifetime and best (IpoServer.lua:123-135, via TycoonCore.lua:591-593), so a round paid through it *is* the loop round → valuation → next round. Recommended: a **Cash grant** like the daily calendar (DailyServer.lua:174-180) in one function, **`CompanyServer.raiseRound`**, with Daily's after-check (valuation and lifetime unchanged, else "BUG", :195-200). Still reviewed: daily_test's `expected` (daily_test.py:4328) gets `"CompanyServer.lua": 0`, and a new check allows exactly one `cash.Value +=` in CompanyServer, inside `raiseRound`.
- **Validation:** `CompanyAction("Raise", round, choice)`: `round` = the stage number the window shows, an anti-replay token like `ipoNumber` (IpoServer.lua:179); `choice` a whole number 1..#choices; no amount is read. No yield between check and write (DailyServer.lua:146-149). Refused unless: funding active (`Enabled` and (`StudioOnly` off or Studio)); `data.ready` (false while loading and while an IPO saves, IpoServer.lua:212-213); `round` = the earliest open round; the choice fits under the cap; 1 Raise per 2 s (like `BUY_MIN_INTERVAL`, TycoonCore.lua:239). Record and Cash change together, then `core.save` (a failed one leaves both for the next save). **One claim per stage** = the record. **No replay:** a stale `round` is refused; a rejoin loads the record; Cash and record share one payload and key (TycoonCore.lua:421-433, 505), so a lost save or a restored version drops or keeps both.
- **Out of the valuation, in code.** Valuation changes only in `IpoServer.addEarnings` (:129), `goPublic` (:231), setup (:356) and Debug (:403, 410, 426). The earners read **Income, not Cash**: the income loop passes `stats.Income.Value` (TycoonCore.lua:865-866), offline pay is `away x income.Value x OFFLINE_RATE` (:819-827), `baseIncome` is `totalIncome x IPO multiplier` (:677-680, from `owned` and employees, :137-145). Raised Cash reaches the valuation only through items that raise Income: the intended time saving, which can't compound because a round's size comes from config and the stage. Same after LONG_GAME PR 2 (base Cash, LG:93).
- **Dilution:** `IpoConfig.sharesFor` (IpoConfig.lua:168-172) gains an optional `stake = 1 - D` (default 1: old calls and tests unchanged): `floor(SharesPerIpo x growth x ratio^0.5 x stake x pass)`, dilution **before** the pass. Callers: `preview` (IpoServer.lua:153-161) and IpoClient (:561, 564, 639, via a `CompanyStake` attribute). LONG_GAME (LG:86) becomes `20 x (1 + 0.25 x IPOs) x min(ratio, 1.5)^0.5 x (1 - D) x pass`: IPO 1 at D = 30% pays 14 (pass 28) instead of 20 (40). The ratio is unchanged.
- **Interactions:** Shareholder (ShopConfig.lua:81-88): x2 after dilution, the same proportional loss. Perks: prices unchanged; fewer Shares only delays them, the one cross-run cost (the IPO multiplier counts IPOs). Daily Shares (`grantShares`, IpoServer.lua:140-148) and pitch Shares (LONG_GAME, undiluted base) are never diluted. Stamps never look at dilution, but rounds save engaged hours, so T is fitted with S8's typical raise (S6).

**5.5 Funding exploits** (server check; test):
- **Always raise the maximum:** a design risk. Convex dilution, the 40% cap; a choice past 4,000 bp is refused; S8.
- **Raise, then reset.** (a) *The IPO:* round Cash spent on what an IPO keeps (employees, HR level, IpoConfig.lua:51-57). Fixed amounts, the dilution paid at that IPO (the record stays in `active` until the transform), LONG_GAME desk caps (R1, LG:108). Test: the transform pays `sharesFor(..., stake)`; S8's "converter" (round Cash on eggs and HR first) gains < 3% in loop 2. (b) *Debug IpoReset* (IpoServer.lua:423-433, Studio only) leaves `pokedex` alone; test: a settled round stays settled. (c) *A version rollback* to pre-funding code pays undiluted Shares at an IPO there: owner-only, inside the floor; noted in PUBLISH_RULES "2d".
- **Raise on a throwaway, then IPO:** Cash never moves between accounts; hires do (poaching), and rounds make an alt's hires cheaper (LONG_GAME section 7). R2 (3 poach-ins per run) and R3 go live first. Test: an alt that raised the maximum feeds 4 hires, the 4th is refused; S8's alt-fed profile.
- **Amount from the client:** only `round` and `choice` are read. Test (mutation): an extra amount is ignored; NaN, 0, 1.5, "1", 4 and a stale `round` are refused; a double tap grants once.
- **Studio and live share the save key** (PUBLISH_RULES.md:46): a Studio raise sets `rounds[k].studio` and `pokedex.studio`; a live server applies saved dilution even with funding off. Test: a Studio-raised save on a fake live server: `Raise` refused, stake applied, no board write.
- **Debug grants:** valuation (IpoServer.lua:400-415) and `GiveCash` (EmployeeServer.lua:787-793) exist only in Studio (IpoServer.lua:456; ShopServer.lua:722-726 refuses on live). New rows "Funding: clear rounds", "Funding: open next round" via `ShopServer.addDebugAction` inside `RunService:IsStudio()`, setting `pokedex.studio`. Test: a source check that they are registered only there.

**5.6 Simulate before any build** (tools/economy_sim.py, new `--pokedex` mode; marks are **placeholders**):
- **S1 seed:** 0 / 10 / 25% cap: ≤ 5% faster per loop; a "decorator" ≤ 5% slower. **S2 bonus:** 0-12 points x pass sets: at the cap ≥ 95% of no-bonus hours. **S3 parity:** every model, profile and rung ±5%. **S4 bots:** no sector faster for a bot. **S5 hopping:** fastest sector vs one, 10 IPOs: < 3%. **S6 tiers:** Gold on ≥ 50% of regular replays, Platinum on ≥ 20% of dedicated ones, pass owners within ±5 points. **S7 board:** new-sector vs replays within 10%; the task-bot never above a dedicated human.
- **S8 round size** (`--rounds`): policies none / Small / Medium / Large-every-round / best-per-stage, per profile, loops 1-10: hours per IPO, Shares, perk timing. Is Large always best? Which dilution curve makes the choice real? Hours saved vs Shares lost. Marks: no one choice best for every profile; Large-every-round saves ≤ 15% of a loop; converter and alt-fed gain < 3% in loop 2; raising the last open round never beats skipping it.
  - *Can:* `--long` (`long_run`, economy_sim.py:1213-1379) has stage entry (:1346-1348), purchases that only fill the current rung (:1320-1339: a grant can't skip one), Shares with the pass (:1350-1352) and one speed perk, the only Shares sink and the only place dilution costs (:1362-1366). `--active` (`report_active`, :967) runs today's 5-stage economy (IPO in minutes): a smoke test only.
  - *Needs:* a grant at stage entry; `(1 - D)` before the pass at :1352; a `rounds` policy and a chooser; the converter profile; Cash left at the IPO and the seed (Cash resets at :1368); an S8 table.

## 6. Build plan

Each PR: claim its scripts, `python3 tools/daily_test.py` passes, F5 without red errors, publish with **Shut down all servers**; create new modules in Studio first (PUBLISH_RULES 2b). **PR 1 ships the whole `pokedex` format.** PR 8-16 need LONG_GAME PR 2.

**What D-F changes in today's code:**
- **Room from the building.** Today `stageOf`/`syncRoom` (TycoonCore.lua:175-186) pick the room from the valuation stage, on join (`newPlot(..., stageOf(data))`, :810) and every second (:867). New: `roomOf(data)` = `pokedex.active.building`; the join builds it; `BuyBuilding` and the IPO (building 1) call `PlotVisuals.setStage`; :867 calls `CompanyServer.onStage` (the round message). The task rung (TaskServer.lua:117) and the IPO sign (IpoServer.lua:66-75) still follow the stage. **PR 2**, with `BuyBuilding` (alone it would freeze every plot in the Garage).
- **PlotArt / PlotVisuals:** no `FundingStages` exists in either (only `PlotArt.Stages`, PlotArt.lua:798, read at PlotVisuals.lua:190, 228, 247). `Stages` keeps its name, order and content; only its meaning becomes "room of building i" (comments PlotArt.lua:5, PlotVisuals.lua:16-17). PR 2.
- **Shop Office tab:** Buildings and `"BuyBuilding"` in PR 2 (Furniture in 5-7). Checks that pin the Office as upgrades-only change on purpose: daily_test.py:4278 (only `buyUpgrade`) and :4286 (only `"Upgrades"`, `"BuyUpgrade"`).
- **Valuation HUD / IpoClient:** `hudStage` and the bar's tap (IpoClient.lua:186-254), the Shares previews with the stake (:561, 564, 639), `sharesFor`'s `stake`, IpoServer's `preview`: **PR 4b**.

**Tests that must hold:** the fingerprints of stage 1, the props and the layout (daily_test.py:3770, 3778, 3790) unchanged; new: building i draws exactly `PlotArt.Stages[i]`; `sharesFor` with `stake` 1 equals today's; the section list (:4269-4271) gains only `pokedex`, `expected` (:4328) only `CompanyServer.lua: 0`.

1. `pokedex` (full format, missing-section default, run check, versioning); `CompanyServer`, `CompanyConfig`, `SectorConfig` (Software, picker off); `"Place"`/`"Store"`/`"Sync"`. *Tests:* round trip; unknown fields kept at every level; `v = 2`; run mismatch; bad values; overlap, zones, rate, ownership.
2. Room from building; nested buildings, move-in, starter set, `"BuyBuilding"`. *Tests:* the fingerprints; nesting; objects unchanged; budgets; a building before its stage is refused.
3. `CompanyClient` edit mode; the inventory; roof hidden in edit mode. *Tests:* both phone sizes; sends only id, x, z, r; one charge; a stored item earns. *Studio:* buy the Laptop, leave it stored, rejoin, place it.
4. The IPO completes the company: Bronze, card, Pokedex tab, seed (Studio only until S1), picker (Studio only). *Tests:* one transform; Bronze once; seed capped and once; run check.
4b. **Funding rounds:** `CompanyConfig.Funding` (`StudioOnly` on), `"Raise"`/`"SkipRound"`, `raiseRound`, the message, the Funding window, `stake`, the card's `rounds`/`stake`/`shares`, Debug rows. *Tests:* 5.4, 5.5, phone sizes. **Live only after** S8, LONG_GAME PR 2 and PR 3 (R2, R3).
5-7. Software: `SectorSoftware`, `SectorArtSoftware` (keys unchanged), buildings 2-5, furniture, kept decor, `"BuyObject"`. *Tests:* no sector key in engine; fingerprints; budgets; D9 words.

**G-S, go / no-go:** (a) 6 plots at building 5, full budgets, low-end phone ≥ 30 fps **(estimate)**; (b) 3+ players pick, build, arrange, raise or skip, IPO into a new sector, find the card, unaided; (c) S1, S3, S5, S8 pass; (d) section 3's Studio checks. **No-go: fix before any other sector.**

8-13. Fintech, Biotech, Gaming. *Tests:* parity ±5%, no new `addEarnings` site, D9 words, `id = 0`.
14. Gold, Platinum, stamp clock, pass-share targets, bonus on, Hall of Fame; needs S2, S4, S6.
15. `BoardServer` (after the CLAUDE.md approval), FR-11; needs S7.
16. Picker and funding on for live servers; PUBLISH_RULES "2d" (with 5.5's rollback note); publish.

## 7. Impact on other docs and branches

**Merge order:** `design-customize` sits on top of `visuals-garage` (40 commits, 19 files ahead of `main` today): merge it only after `visuals-garage` lands.

**docs/LONG_GAME_PROPOSAL.md** (`LG:` = its line):
- **Principle (LG:5)** "Cash can only fill a rung" holds: round Cash only buys the current rung (economy_sim.py:1320). **Pacing (LG:6-18):** the 57 h fit assumes no round; S8 decides whether it uses the typical raise.
- **Section 3 (LG:38, 53-60):** a building costs its office's fitted price; 7 offices on 5 footprints (Glass Tower and Global HQ become shell upgrades of building 5); each building adds hire spots for the 18 desks; R1 caps (LG:108) follow the 7 office purchases; furniture never enters `LONG_K`; S3 recounts the moments (LG:66-79) per sector.
- **Decor (LG:78, 82, 86, 88, 92):** earned pieces are **kept**; bought copies reset; the Boardroom skin is a pass furniture set; the prestige wing stays perks; "industry skin per IPO" becomes "pick a sector".
- **Shares and money (LG:86, 92-94):** Shares `x (1 - D)` before the pass; the base-Cash valuation never counts round Cash; the `addEarnings` list gains "(8) `CompanyServer` never calls it"; sector models ride entry (1). **Section 7 (LG:97-108):** rounds cheapen alt feeding: R2, R3 first. **Section 8 (LG:110-122):** its PR 4 = PR 1-7 here, its PR 7 = PR 8-13; 4b needs its PR 2 and 3.

**Other docs:**
- **`design-tutorial` collides:** both add a section and a module to TycoonCore (`KNOWN_SECTIONS` :84, payload, save gate :481) and daily_test.py:4269-4271. **`setupPlayer` order:** IpoServer (:793), fixedHires, EmployeeServer (:795), PoachServer, OnboardingServer (:797), **CompanyServer**, TaskServer (:798), **TutorialServer** (TUTORIAL_PROPOSAL.md:106), DailyServer (:799, last); `init` alike; BoardServer's repair runs after `data.ready` (TycoonCore.lua:831). **Tutorial PR A merges first**; Pokedex PR 1 rebases onto it.
- **Tutorial steps** (TUTORIAL_PROPOSAL.md): 1 and 4 (:25, 28) become "own your sector's first upgrade" and "own 2 of this company's upgrades" (step 1 waits while `OpenPanel = "Sector"`). **Step 8 "Funding"** (:32, "open the IPO window") becomes: when the first round opens, open the Funding window; Raise, Later or Skip completes it; no reward, never forces a raise. **Step 9** (:33, notes 37-42): resets add buildings, bought furniture, rounds and dilution (a new company starts at 100%); keeps add stamps and kept decor. New step: "Arrange your office". The "?" and the strip (:53, 62) are untouched.
- **`content-bible`:** sections 1-6 = Software's package; "Titles and cosmetics" (243-251) drops the industry skins; decision 9 (373) is answered.
- **`building-pass`: park it.** Its patch and BuildingClient.lua are built for 60 x 60, and its roof would block the edit camera. Reused in PR 2 and 6: shell data, budgets, `BUILDINGMATH`, the `pcall` plug-in.
- **`visuals-garage`, PLOT_VISUALS.md (14, 37), CLAUDE.md "Plot visuals" (32):** "the plot stays 60 x 60", the skyline, "six props identical in every room", "the real Floor is the only solid" and "`PlotArt.Stages[i]` is the room of `IpoConfig.Stages[i]`" change.
- **CLAUDE.md, README, ROADMAP, PUBLISH_RULES:** `pokedex` in the save block, new modules and order, `CompanyRemotes`, round Cash as a gift like daily Cash, PUBLISH_RULES "2d".
- **CLAUDE.md:29 (awaiting owner approval):** new wording: "Never add a second DataStore, save loop or PlayerAdded data owner. One exception: `BoardServer` (ServerScriptService) may use the OrderedDataStores `Collection_v1` and `HallOfFame_v1` (and their `_Studio` twins) for the leaderboard. It writes only values read from the loaded save after that save succeeded, never saves player data, and wraps every call in `pcall`. Every other store stays under this rule." No board code before approval.

## 8. Open questions (unresolved, most important first)

1. **Tier rules:** Gold 1.0 T, Platinum 0.8 T plus ratio 1.25, targets shortened by the run's share with each pass (recommend), or pass-neutral rules?
2. **Collection bonus:** a Cash multiplier, cap 10%, never valuation (recommend), or a cheaper first rung?
3. **Income models:** the mechanics (only if S3-S5 pass) or today's Income with themed text? Fintech's interest rewards holding Cash, against the buy loop: keep it, or a model that pays for spending?
4. **Earned decor:** which counts and milestones unlock which kept piece (content bible choice 5), and what Day 7 gives once its list is all kept?
5. **Leaderboard:** Collection plus Hall of Fame (recommend), or also a fastest-Platinum board per sector?
6. **78 x 82 enough,** or move the plots (`PLOT_SPACING` 112)? Decide at G-S.

## What I did not verify

- The world outside scripts (Baseplate, SpawnLocation, hand-placed parts, Terrain, StreamingEnabled): no Studio or MCP was used.
- "0 visits" and the privacy setting (Creator Hub only); OrderedDataStore and `UserService` limits; camera scale; phone frame rates; why `MAX_PARTS` is 260.
- Every economy number and content estimate: placeholders or estimates.
- Other branches were read with `git show`, not run; LONG_GAME PR 2 doesn't exist; `daily_test.py` was not run (docs only).
