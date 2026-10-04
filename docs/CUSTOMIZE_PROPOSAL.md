# Companies, sectors and the Pokedex (proposal, design only)

Design only (2026-10-04, branch `design-customize`, revised after an independent review). No script, config or test changed. For the owner and the Claude sessions that will build it. Line numbers are for this branch, whose `.lua`/`.py` files equal `visuals-garage` `7f5c141` (`main` has no PlotArt, PlotVisuals or Office tab; `visuals-garage` `a4cb486` moved daily_test.py lines by about +209). **(unverified)** = not checked in code; **(estimate)** = not measured; **(owner default)** = the owner may still veto; **(placeholder)** = sized by the sims.

**Fixed by the owner:** **D-A** a bigger building contains the previous one; every object moves in at the same coordinates from a door-side anchor. **D-B** an IPO founds a new company, seeded with some of the old one's money (never items). **D-C** every founding starts with picking a sector. **D-D** a sector is a full package on one engine; Software (today), Fintech, Biotech, Gaming launch together, Software first. **D-E** free placement, phone and PC. **P-1** one Pokedex entry per sector. **P-2** an IPO completes the company and stamps its sector; the old company is a card. **P-3** all four sectors = the main goal (Hall of Fame); replays earn Gold and Platinum; a leaderboard. **P-4** old companies earn nothing; stamps give a small capped bonus. **P-5** the seed stays, numbers open. **Inventory:** a purchase goes to the inventory, with "Place now" (section 4). **D-F funding rounds:** reaching a stage by valuation lets the player raise a round of a size they pick; it gives Cash only, costs dilution (fewer IPO Shares), and the room follows the building owned, not the stage (1.7).

**Owner defaults:** employees follow the player; creatures keep their bodies, renamed per sector; 5 buildings per sector (building 5 serves Series C+D, Pre-IPO and IPO-ready, section 7); any sector can be picked next; legacy IPOs get no stamp (moot, 1.2); an unplaced item still earns; size 78 x 84, re-checked as **78 x 82** (section 3); hire desks fixed in v1; furniture earns nothing; a free, fixed starter set per building (D9); 45° rotation; part budget open until a phone test; the CLAUDE.md DataStore exception (section 7, **awaiting owner approval**).

**New names** (none exists in any `.lua`/`.py`): `CompanyServer` (owns `pokedex`), `CompanyConfig`, `SectorConfig`, `Sector<Name>`, `SectorArt<Name>`, `CompanyClient`, `CompanyRemotes.CompanyAction` (incl. `"Raise"`, `"SkipRound"`), `CompanyConfig.Funding`, `CompanyServer.raiseRound`, `BoardServer`, OrderedDataStores `Collection_v1`, `HallOfFame_v1`.

## 1. Companies, sectors and the Pokedex

**1.1 A company** is one run of one sector's ladder: Cash, upgrades, buildings, furniture, layout, eggs in incubators, valuation, funding rounds and dilution. **The player** keeps the rest: employees, HR level, passes, boosts, shields, Shares, perks, IPO count and multiplier, `lifetime`/`best`, daily, onboarding, task stats, the Pokedex, kept decor (today's rule: IpoConfig.lua:6-8, 51). Only the active company exists in the world.

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
    building = number,       -- buildings bought, 1 = Garage
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

- **Fields:** `id` = an upgrade name or `<objectKey>#<n>`; `x`, `z` studs from the anchor, rounded to 0.5; `r` 0-7; at most 40; an owned item without an entry is in the inventory. `ratio` = valuation at the IPO / IPO-ready valuation. About 11 KB **(estimate)**.
- **Loader: KEEP at every level.** Unknown fields are stored and written back, as in onboarding (OnboardingServer.lua:226, 243, 281), daily (DailyServer.lua:244, 261, 290), tasks (TaskServer.lua:712, 766, 800) and fixedHires (EmployeeServer.lua:657, 675, 694), but at **every** level: the section, `active`, each `sectors[k]`, `card`, `objects[i]`, `told`, `rounds`, each `rounds[k]` (and `card.rounds[k]`). Those four keep top-level fields only; shop, team, poach and ipo keep none (EmployeeServer.lua:648); a nested drop loses data on a rollback too (A10).
- **Versioning (new code, its own tests):** `v` rises only when a field changes meaning. No loader does this today: a higher `v` is held as one opaque value, written back unchanged, and the session refuses `GoPublic`, `Place`, `BuyBuilding`, `PickSector`. Unknown sector keys are kept; while one exists `BoardServer` writes nothing. *Tests:* `v = 2` deep-equal after a save; each refusal; no board write.
- **Bad values** (type, NaN, infinite, negative, out of range, unknown or duplicate id) are skipped with a warning; `stamp` clamped; `"done"` with stamp 0 becomes 1; a non-active `"progress"` becomes `"done"` if stamped, else is dropped.
- **Wiring:** `KNOWN_SECTIONS` (TycoonCore.lua:84), `buildPayload` (:421-433), save gate (:481); daily_test.py:4269-4271 asserts the exact section list and changes in the same PR. Setup order: section 7. **Publish:** Shut down all servers, a PUBLISH_RULES "2d" note; rollback floor stays `V_launch` (M4+ code keeps unknown sections, TycoonCore.lua:773-777, 434-438).
- **No legacy migration.** Not launched: private until launch (PUBLISH_RULES.md:101), M4 never published (:17), no real saves (LONG_GAME_PROPOSAL.md:88); "0 visits" can't be checked offline. **All test accounts are wiped together before launch** (`RemoveAsync` on a written list, PUBLISH_RULES.md:111): the whole key goes, daily, tasks, onboarding and purchase receipts too, and poach records (`gained`, `lost`) name other accounts, so all are in one wipe. **A missing `pokedex`** = a new founding: `run = ipo.count`, Software, `picked = true` while the picker is off, building 1.
- **A10 run check:** `run ~= ipo.count` means an older version ran an IPO (reset Cash, `owned`, eggs, TycoonCore.lua:549-559; no seed). IPOs are gated on valuation (IpoServer.lua:192-195), so the sector gets `"done"`, Bronze if unstamped and a card (`engaged` 0); the new company keeps the sector, `picked = false`, building 1, no seed.

**1.3 Picking a sector, on every founding.** A window (`OpenPanel = "Sector"`), four cards: icon, name, how it makes money, stamp, "New". It opens for a new player, in every IPO and after a run check. `CompanyAction("PickSector", key)` only while `picked == false`; purchases wait.
- **Next sector (owner default): any enabled sector, the same included.** Rewards steer: Bronze, the biggest bonus step, needs a new sector; the picker preselects one.
- `SectorConfig.PickerEnabled = false` until all four exist.

**1.4 The IPO completes the company.** Today `goPublic` (IpoServer.lua:177-243) checks, then `commitIpo` (TycoonCore.lua:544-588) saves with a transform resetting Cash, `owned` and eggs (IpoConfig.lua:53-58). New:
1. The picker before Confirm; `IpoAction("GoPublic", ipoNumber, sectorKey)` adds a sector check to today's (`ipoNumber == count + 1`, IpoServer.lua:179).
2. **One transform, one save** (TycoonCore.lua:548-564): `"done"`, `stamp = max(stamp, earned)`, `replays`, `firstAt`, `bestEngaged`, a new `card`; `hallAt` on the fourth; a new `active` (building 1, kept decor in the inventory); `run = count + 1`; Cash = `StartingCash` + seed. Today's resets stay.
3. Only after that save works (:565-587): the new Garage, a stamp pop-up, the board write.

**The card** is in a new **Pokedex** tab of the IPO window (IpoClient.lua:354): sector, name, stamp, IPO number, date, engaged hours, ratio and a **top-down map** (Frames per footprint; no 3D diorama in v1). `ResetNames` (IpoConfig.lua:60-65) and the keep list (IpoClient.lua:524-533) add buildings, furniture, stamps.

**1.5 Stamps, replays, Hall of Fame.**
- **Bronze:** first completion (any IPO), bonus +1.5%. **Gold:** a replay within **1.0 T** engaged hours, +0.5%. **Platinum:** within **0.8 T** at ratio **≥ 1.25**, +0.5%. **T** = the loop's reference hours for a regular player (LONG_GAME section 1: 57 / 51.5 / 52 h); T and ratio are **placeholders** (S6). Engaged time comes only from the server's clock: Gold and Platinum wait for LONG_GAME PR 2.
- **Long sessions:** the stamp clock weighs engaged seconds like the valuation (100% for 3 engaged hours a day, 5% after, LONG_GAME_PROPOSAL.md:23), so playing past 3 h never hurts a stamp.
- **Pass fairness:** 2x Cash shortens a run about 15% (48.7 vs 57.1 h, LONG_GAME section 6), so a target shrinks by that speed-up times the **share of the run's engaged seconds with the pass** (`passSeconds`; placeholder x0.85 for a whole run). Keyed on passes owned at founding, it is an exploit: buy 2x Cash right after founding, keep the full target.
- **A replay** has the same content, priced by IPO count (`StageScale`), never by sector or stamp; a stamp clock in the IPO window.
- **Hall of Fame:** all four `"done"`: `hallAt`, a title, a gold frame, a board entry. The game goes on.

**1.6 Leaderboard.**
- **Today:** in-server only (IpoServer.lua:46-63; IpoClient.lua:750-786); no OrderedDataStore exists (docs/reviews/FULL_REVIEW.md:126).
- **Ranks:** **Collection** = `1000 x stamp points + min(IPO count, 999)` (Bronze 1, Gold 2, Platinum 3 per sector), capped at 12,999; **Hall of Fame** = earliest `hallAt`.
- **Storage:** `BoardServer` writes `Collection_v1`, `HallOfFame_v1` (in `pcall`), key UserId, from the loaded `pokedex` after the stamp's save succeeded; on join it repairs a lower value; top 50 read every 10 minutes. No client sends a score.
- **Studio never reaches the live board.** Studio and live share the save key (PUBLISH_RULES.md:46), so Debug valuation grants (`IpoGrantValuation`, `IpoJumpReady`, IpoServer.lua:400-411), a Debug stamp or a Studio pick are saved like real play, and the join repair would copy them live. Rules, in `BoardServer`, from the loaded save: (a) every save by a Studio server (`RunService:IsStudio()`) sets `pokedex.studio = true`, never cleared; (b) a `studio` account is never written, repaired or shown; (c) Studio uses only `Collection_v1_Studio`, `HallOfFame_v1_Studio`; (d) a deny list (`BoardServer.REMOVED`, UserIds) is never written, repaired or shown: removal = list + `RemoveAsync` on both boards + publish, or the repair re-adds it. Per account: a per-stamp flag leaks the IPO-count tie-break and `hallAt`. Dev accounts stay off. *Test (fake stores):* a `studio` save with four Platinum joins live: no write; a Studio session saves `studio` and writes only `_Studio`; a listed UserId: no write, repair or row; only BoardServer calls `GetOrderedDataStore`.
- **Names (FR-11):** the server looks UserIds up (`UserService:GetUserInfosByUserIdsAsync`, `pcall`, cached; **unverified limits**), "Player" on failure; the client escapes `& < > " '` before rich text, one helper for both lists (fixes IpoClient.lua:780). Studio needs API Services on (CONTRIBUTING.md:41).

**1.7 Funding rounds (D-F, owner decision).** Every number is a **placeholder** for S8 (5.4); nothing is random (D9).
- **What opens a round:** the **valuation** (never Cash) reaching a stage after the first: Seed, Series A, Series B today (IpoConfig.lua:17-23), plus Series C+D and Pre-IPO with LONG_GAME's 7 stages. IPO-ready has no round: it is the IPO. The stage is `IpoConfig.stageIndex(ipo.valuation, ipo.count)` (IpoConfig.lua:151-159); it never falls during a run (spending never lowers the valuation, IpoServer.lua:122-135).
- **A round gives Cash and nothing else.** No building move, no Income change. The stage's building becomes buyable in SHOP > Office once the stage is reached, raised or not (`"BuyBuilding"`, section 4); the room follows the building owned (section 6). The Cash buys anything.
- **Flow:** (1) stage reached: one message per stage per company (`told`), "🌱 Seed reached: you can raise a round", and the valuation bar reads "Raise a round ›" while one is open (UI: section 4). (2) The **Funding window**: 3 choices (Small, Medium, Large), each with its Cash, the share given away, the IPO Shares after it and the stake left; a choice that would pass the cap is locked. (3) **Raise** (pick, then confirm "Raise $X for Y%"): Cash at once. **Later** closes the window; the round stays open. **Skip this round** (with a confirm) closes it for this company.
- **One round per stage per company.** Open rounds are settled in stage order (the window shows the earliest); one still open at the next stage stays open; all close at IPO-ready (Cash raised then could only feed the seed, 5.1).
- **Never raising** is a full path: no dilution, all the Shares, buildings bought with earned Cash; the card says "Bootstrapped: 100% stake". No extra reward.
- **Amount:** choice i gives `cashPct[i] x IpoConfig.stageValuation(stage, ipo.count)` (IpoConfig.lua:140-143): the stage and IPO count only, never Cash, Income, passes or stamps. Placeholders: 10 / 20 / 30% for 3 / 7 / 12% dilution (convex: each extra dollar costs more); **total dilution capped at 40%** (`DilutionCap`): the founder keeps at least 60%. Income during the run is untouched. Data in `CompanyConfig.Funding` (shared engine, keyed by `IpoConfig.Stages` keys, never renamed), with `Enabled` and `StudioOnly`.
- **Saved (`pokedex.active`, schema in 1.2):** `told[stageKey]`; `rounds[stageKey]` = `s` ("raised"/"skipped"), `c` (choice), `cash`, `bp` (dilution in basis points, whole, 0-10000, **as applied**: never recomputed from a later config), `at`, `studio` (raised on a Studio server). Total dilution `D = min(DilutionCap, Σ bp) / 10000`, derived on load. **Loader:** KEEP at every level (1.2). A round under an **unknown stage key** is kept and its valid `bp` still counts, so a newer version's round dilutes an older version's IPO. A malformed record of a known stage counts as settled (no second round) with `bp` 0 and a warning, never dropped (a dropped record would allow a second raise).
- **The card keeps** (written in 1.4's one transform): `rounds` as they were, `stake` (10000 - D in bp) and `shares` (what the IPO paid after dilution and pass). It shows "Founder stake 70% · 3 rounds · $X raised" or "Bootstrapped". The new `active` starts with empty `told` and `rounds`. **Run check (1.2):** rounds of a company closed by older code go to its card unchanged.

## 2. The sector package and content

**Shared engine** (never names a sector; a test fails on a sector key in engine code): `pokedex`, picker, IPO flow, stamps, seed, bonus, board; buildings, placement, inventory; SHOP > Office; tasks; creatures, eggs, odds, `fixedHire` (D9), poaching; daily, onboarding, HUD; the economy clock; the sim.

**Per sector** (`Sector<Name>` data, `SectorArt<Name>` art): identity (key, name, icon, palette, 12+ company names); 5 buildings; upgrades (key in `owned`, never reused; Software keeps today's six, TycoonCore.lua:65-72); furniture; tasks (`TaskConfig.Rows` format, TaskConfig.lua:49); creature names and jobs (`role`, CreatureConfig.lua:56-104); egg names; one income model; bundles with fixed contents, `id = 0`. Art in PlotArt's `P(...)` format (PlotArt.lua:9-23), passing PlotVisuals' checks.

**Income models** (deterministic, capped, engaged only; every number a **placeholder** for S3). **Software:** steady Income. The other three are `Sector<Name>.extra(data, seconds)`: Cash computed from **base Income** (`baseIncome`, TycoonCore.lua:677-680: no passes or bonus), added to the amount of the **existing income-loop call** (TycoonCore.lua:866; from LONG_GAME PR 2 `kind = "engaged"`, so the 3 h/day weight applies). **No new call site:** daily_test.py:4327-4334 fails on one until reviewed. Never in offline pay (:825), the away bank or `baseIncome` itself (task rewards would grow).
- **Fintech:** interest r per minute on Cash held, on at most H seconds of base Income.
- **Biotech:** every N engaged minutes (a visible timer, paused when not engaged, never a roll) P seconds of base Income.
- **Gaming:** a graded Timing task (paid through TaskServer.lua:257 like every task) starts a launch: base Income x L for D minutes, then C minutes of cooldown; the extra (L - 1) rides the income loop.
- **Parity:** a sector's item Incomes are lowered until item Income plus the model's average extra is within ±5% of Software per engaged hour, on every rung, for every `LONG_PLAYERS` profile (S3), with no bot or hopper gain (S4, S5). Passes multiply afterwards, alike for all four. Whether a model ships is the owner's (section 8).

**Content:** the content bible (`content-bible`) names 168 things for Software (upgrades 42, decor 22, hires 18, desks 18, events 12, titles 9, skins 9, board requests 8, offices 7, products 6, eggs 6, caller groups 6, hats 4, chat tag 1; CONTENT_BIBLE.md:300-361). **Its decor is earned** (counts and milestones: :261, 268, 278, 280; choice 5, :369), **bought here.** Reconciled: an earned piece goes to `kept`, free in every company; more copies are bought. Per new sector about 185 names and 75 art builds **(estimate)**. In code: 6 props (118 parts), 5 rooms, 12 creatures, 3 eggs (CreatureConfig.lua:23-48), 1 task.

## 3. Plot space (re-verified in the code)

- **Code:** `PLOT_SPACING = 90`, `MAX_PLOTS = 6` (TycoonCore.lua:74, 76); `plotCenter` x = -225 + 90 x (slot - 1), z 150 (:123-126); `Floor` 60 x 60 (:736): z 120-180. Front = +Z (signs z +24, TycoonCore.lua:75, IpoServer.lua:21; spawn +12, TycoonCore.lua:698-700); `minAisle = 6` (PlotArt.lua:68). **Anchor = front-center of the floor, z 180.**
- **VIP Lounge:** center (0, 0.5, 70), 36 x 24 (ShopServer.lua:35-37, 636-650): z 57.5-82.5; its door `Touched` (:683) is the only one; a non-VIP inside goes to **z 88** (:839). Skyline: z 101-107 (PlotArt.lua:699-707). Nothing else is scripted in the world; Baseplate, SpawnLocation, hand-placed parts and Terrain are not in the repo.
- **Width:** a building-pass shell adds 2.3 per side (BUILDING_PASS_PROPOSAL.md section 3); gap 90 - W - 4.6 ≥ 6: **W = 78**. **Depth:** back roof edge 180.2 - D - 2.3 ≥ 94 (z 88 plus 6): **D = 82**.
- **Largest building 78 x 82 (1.78x the area), no plot moved;** nested **(estimate)** 60 x 60, 64 x 66, 68 x 70, 72 x 76, 78 x 82. Outer roofs reach x ±266.3: **Baseplate 534+ wide (unverified)**.
- **Changes:** the skyline (`BACKDROP_Z`, PlotVisuals.lua:44) goes or becomes a picture; flush `FloorExtension` strips (PlotVisuals.lua:590-592); 60 x 60 assumptions go per building (PlotArt.lua:31; PlotVisuals.lua:544, 643). Bigger needs `PLOT_SPACING` ≥ W + 10.6.
- **Studio by hand (owner, read only):** Baseplate Size and Position (x ±267, z 95-182); other Workspace children, especially the SpawnLocation and anything at z 85-120 or past x ±225; Terrain; StreamingEnabled.

## 4. The office: placement, inventory, checks, budget, phone

- **Fixed:** Floor (the only solid), spawn lane, signs, incubators (EmployeeServer.lua:37-40), hire spots and desks (EmployeeServer.lua:31-35). **Movable or stored:** upgrade props (default = today's slot, `itemOffset`/`spawnItem`, TycoonCore.lua:131-135, 189) and furniture. Employees: unchanged.
- **Move-in (D-A):** `objects` stay; building n+1 contains n and no zone moves, so no check can fail. The new area gets the starter set (full budget: to the inventory).
- **Inventory (owner decision).** A purchase (upgrade or furniture) goes to the **inventory** (owned minus `objects`); right after it, **"Place now"** (Office card and pop-up) opens edit mode with the item at its default spot; ignored, it stays stored. **An unplaced item still earns (owner default):** Income reads `owned` only (TycoonCore.lua:137-145). **In PR 3** (a stored item needs edit mode): `buyUpgrade` (TycoonCore.lua:272-288) drops the pop-in at the fixed slot (`spawnItem(data, i, upg, true)`, :285), the join loop (:811-815) draws only placed objects, ShopClient's Office tab (:496-573) gains "Place now" and "In storage". Until then a purchase pops in at its default spot, written to `objects`. **The buy is unchanged:** one charge after `checkUpgradePurchase` (ready, number, owned, order, Cash, 0.4 s; :243-270); "already yours" refuses a second buy; `handleShopAction` (ShopServer.lua:704-717) unchanged; "Place" never charges.
- **Checks** on `CompanyAction` (`"Place", id, x, z, r`; `"Store", id`; `"Sync"`; `"PickSector", key`): `data.ready` (IpoServer.lua:212-213); `id` a string under 40 chars, finite `x`/`z`, whole `r` 0-7; ownership; footprint inside the building; overlap ≤ 0.1 stud; no reserved zone (`PlotVisuals.zones`, :504-531); budgets; 4 requests/s. **One pure function in `CompanyConfig`:** the client previews, the server decides.
- Placement never changes Income; **no `Touched` handler** (taps hit footprints; daily_test.py:4254-4256).
- **Part budget:** `MAX_PARTS = 260`, `MAX_LIGHTS = 3` (PlotVisuals.lua:39-40); rooms use 244-257 (ROADMAP.md:42), props 118 (daily_test.py:3858): about 3 furniture pieces left. **Proposal:** draw only owned desks, 320 per plot. **No change before G-S's phone test** (owner default).
- **Phone and PC:** edit mode is a window (`OpenPanel = "Office"`; tray and thumbstick hide), from SHOP > Office, no new HUD slot. Top-down camera, about 3.5 px per stud at 78 x 82 on 667 x 339 **(estimate)**, a pick strip, pinch zoom, drag, snap 0.5, one `"Place"` on lift; Rotate, Store, Done 56 px; PC: drag, R, Delete. Tested at top bars 0 / 36 / 58 like `TRAY_TESTS`.
- **Shop:** Office gains Buildings and Furniture: `"BuyBuilding", n`, `"BuyObject", n` on `ShopAction` (ShopServer.lua:704-717, 802-805), checked like `checkUpgradePurchase` plus "stage reached", "building n-1 owned". A building costs its LONG_GAME office price. Cash only; no odds words (daily_test.py:4344).

## 5. Economy: seed, collection bonus, risks, sims

**5.1 Seed (P-5).** The new company starts with `StartingCash` (0, IpoConfig.lua:44) plus **s% of the old company's Cash, capped at c% of the new first rung's prices**; s = 10, c = 25 are **placeholders** (S1). A gift (no `addEarnings`), paid once inside the IPO transform. No dividend (P-4).

**5.2 Collection bonus (P-4).** A **Cash multiplier on Income**: +1.5% per Bronze, +0.5% Gold, +0.5% Platinum, **capped at +10%** **(placeholders, S2)**, applied with the passes (`updateIncome`, TycoonCore.lua:148-152), **never valuation**: from LONG_GAME PR 2 valuation counts base Income only. **It stays 0 until PR 2**: today two paths add the whole Income, passes included, to the valuation: the income loop (TycoonCore.lua:865-866) and **offline earnings** (:819-827, `income.Value` through `addEarnings` at :825). Rule: the bonus never enters `baseIncome` (:677-680), offline or away pay, or the valuation. **Fallback** if S2 fails: a cheaper first rung.

**Interactions:**
- **2x Cash (ShopConfig.lua:41), VIP (:50), IPO multiplier (IpoConfig.lua:162-165):** 2 x 1.5 x 1.10 = x3.3 with the bonus cap, times the IPO multiplier, which has no cap (x3.81 at 10 IPOs: x12.6 in all). Cash only after PR 2.
- **Shareholder (ShopConfig.lua:81-88; `sharesFor`, IpoConfig.lua:168-172):** **no stamp ever pays Shares.**
- **Cash packs (ShopServer.lua:537-541), daily Cash (DailyServer.lua:177), task rewards:** sized from Income, up to +10%; gifts after PR 2. **D9:** stamps never change odds; never sold, never random.

**5.3 Risks.** IPO pace is unchanged: an IPO needs earned valuation (IpoServer.lua:123-135, 192-195). Switched on before PR 2, the bonus would shorten every IPO. A faster sector becomes the only choice (S3-S5). Only an IPO founds a company (cooldown, IpoConfig.lua:45). **Duplicate seed:** paid only inside the one transform; `ipoNumber` blocks a repeat (IpoServer.lua:179); a failed save changes nothing (TycoonCore.lua:565-567); the run check pays none. Stamps can't be traded or poached; older code keeps `pokedex` frozen.

**5.4 Simulate before any build** (tools/economy_sim.py, new `--pokedex` mode; pass marks are **placeholders**):
- **S1 seed:** 0 / 10 / 25% cap: ≤ 5% faster per loop; a "decorator" (10% of Cash on furniture): ≤ 5% slower.
- **S2 bonus:** 0-12 points x pass sets, loops 2-12: at the cap ≥ 95% of no-bonus hours; both passes gain ≤ 2 points more.
- **S3 parity:** each model per `LONG_PLAYERS` profile: every rung ±5%; moments recounted. **S4 bots:** no sector faster for a bot. **S5 hopping:** fastest sector vs one, 10 IPOs: < 3%.
- **S6 tiers:** Gold on ≥ 50% of regular replays, Platinum on ≥ 20% of dedicated ones, pass owners within ±5 points. **S7 board:** new-sector vs replays, IPO-ready vs 1.25: within 10%; the task-bot never above a dedicated human.
- **Duplicate seed** test: a retried save, a repeated `GoPublic` and a run mismatch pay it once.

**5.5 Funding rounds: Cash, valuation, Shares.**
- **Not an `addEarnings` call (differs from the brief; owner to confirm).** Every `addEarnings` raises valuation, lifetime and best (IpoServer.lua:123-135, via TycoonCore.lua:591-593), so a round paid through it *is* the loop round → valuation → next round. Recommended: a **Cash grant** like the daily calendar (DailyServer.lua:174-180): `data.cash.Value += amount` in one function, **`CompanyServer.raiseRound`**, with Daily's after-check (valuation and lifetime unchanged, else a "BUG" warning, :195-200). The review stays in daily_test: `expected` (daily_test.py:4328) gets `"CompanyServer.lua": 0`, and a new check allows exactly one `cash.Value +=` in CompanyServer, inside `raiseRound`. (After LONG_GAME PR 2 a weight-0 `addEarnings(..., "funding")` would also work, but adds a call site that changes nothing.)
- **Validation:** `CompanyAction("Raise", round, choice)`: `round` = the stage number the window shows, an anti-replay token like GoPublic's `ipoNumber` (IpoServer.lua:179); `choice` a whole number 1..#choices. No amount is read: the server derives it (1.7). No yield between check and write (DailyServer.lua:146-149). Refused unless: funding active (`Enabled` and (`StudioOnly` off or Studio)); `data.ready` (false while loading and while an IPO saves, IpoServer.lua:212-213); `round` = the earliest open round (reached, below IPO-ready, no record); the choice fits under the cap; 1 Raise per 2 s (like `BUY_MIN_INTERVAL`, TycoonCore.lua:239). Then the record and the Cash change together and `core.save` runs at once; a failed save leaves both for the next save (Daily's rule). **One claim per stage** = the record. **No replay:** a repeated or stale `round` is refused; a rejoin loads the record; Cash and record share one payload and key (TycoonCore.lua:421-433, 505), so a lost save or a restored DataStore version drops or keeps both.
- **Out of the valuation, in code.** Valuation changes only in `IpoServer.addEarnings` (:129), `goPublic` (:231), setup (:356) and Debug (:403, 410, 426); the grant calls none. The earners read **Income, not Cash**: the income loop passes `stats.Income.Value` (TycoonCore.lua:865-866), offline pay is `away x income.Value x OFFLINE_RATE` (:819-827), `baseIncome` is `totalIncome x IPO multiplier` (:677-680, from `owned` and employees, :137-145). Raised Cash reaches the valuation only through items that raise Income: the intended time saving, and it can't compound because the next round's size comes from config and the stage, never from Cash or Income. Same after LONG_GAME PR 2 (valuation at base Cash, LG:93).
- **Dilution in the Shares formula.** `IpoConfig.sharesFor` (IpoConfig.lua:168-172) gains an optional `stake = 1 - D` (default 1: old calls and tests unchanged): `floor(SharesPerIpo x growth x ratio^0.5 x stake x pass)`, dilution **before** the pass, one floor. Callers: `preview` (IpoServer.lua:153-161) and IpoClient (:561, 564, 639, reading a `CompanyStake` attribute, display only). LONG_GAME (LG:86) becomes `20 x (1 + 0.25 x IPOs) x min(ratio, 1.5)^0.5 x (1 - D) x pass`: IPO 1 at D = 30% pays 14 (pass 28) instead of 20 (40). The ratio is unchanged (raised Cash is not valuation).
- **Interactions:** Shareholder (ShopConfig.lua:81-88): x2 after dilution, the same proportional loss. Perks: prices unchanged; fewer Shares only delays them: the one cross-run cost (the IPO multiplier counts IPOs, IpoConfig.lua:162-165). Daily Shares (`grantShares`, IpoServer.lua:140-148) and pitch Shares (LONG_GAME, from the undiluted base) are never diluted. Stamps pay no Shares (5.2) and never look at dilution, but rounds save engaged hours, so the tier targets T are fitted with S8's typical raise (S6). Seed (5.1): rounds close at IPO-ready, and its cap bounds leftover raised Cash.

**5.6 Funding exploits** (server check; the test that proves it):
- **Always raise the maximum:** a design risk, not a hole. Check: convex dilution, the 40% cap. Test: a choice that would pass 4,000 bp is refused; S8 shows "max every round" is not best for every profile.
- **Raise, then reset.** (a) *The IPO:* round Cash spent on what an IPO keeps (employees, HR level, IpoConfig.lua:51-57) outlives the run. Check: the amount is fixed per stage; the dilution is paid at that IPO (the record stays in `active` until the transform); LONG_GAME desk caps (R1, LG:108) cap kept hires. Test: the transform pays `sharesFor(..., stake)`; S8's "converter" (round Cash on eggs and HR first) gains < 3% in loop 2. (b) *Debug IpoReset* (IpoServer.lua:423-433, Studio only) leaves `pokedex` alone. Test: a settled round stays settled after it. (c) *A version rollback* to pre-funding code pays undiluted Shares at an IPO there: owner-only, inside the floor; accepted and written in PUBLISH_RULES "2d".
- **Raise on a throwaway, then IPO:** Cash never moves between accounts; hires do (poaching), and rounds make an alt's hires cheaper (LONG_GAME section 7). Check: LONG_GAME R2 (3 poach-ins per run) and R3 (account age, engaged hours) are live before rounds; the amount ignores Cash, Income and passes. Test: an alt that raised the maximum feeds 4 hires; the 4th is refused; S8's alt-fed profile.
- **Amount from the client:** the server reads only `round` and `choice` (5.5). Test (mutation, like the Office buy's): an extra amount or price is ignored; NaN, 0, 1.5, "1", 4 and a stale `round` are refused; a double tap grants once.
- **Studio and live share the save key** (PUBLISH_RULES.md:46), so a Studio raise is saved like real play. Check: a Studio raise sets `rounds[k].studio` and `pokedex.studio` (1.6 (a)); a live server applies saved dilution even with funding off; the board ignores `studio` accounts. Test: a Studio-raised save on a fake live server: `Raise` refused, stake applied in the preview and at the IPO, no board write.
- **Debug grants:** valuation (IpoServer.lua:400-415) and Cash (`GiveCash`, EmployeeServer.lua:787-793) exist only in Studio (IpoServer.lua:456; ShopServer.lua:722-726 refuses on live). New rows "Funding: clear rounds" and "Funding: open next round" go through `ShopServer.addDebugAction` inside `RunService:IsStudio()` and set `pokedex.studio`. Test: a source check that they are registered only in that block; on a fake live server the Debug remote doesn't exist.

## 6. Build plan

Each PR: claim its scripts, `python3 tools/daily_test.py` passes, F5 without red errors, publish with **Shut down all servers**; create new modules in Studio first (PUBLISH_RULES 2b). **PR 1 ships the whole `pokedex` format.** PR 8-16 need LONG_GAME PR 2.

1. `pokedex` (full format, missing-section default, run check, versioning); `CompanyServer`, `CompanyConfig`, `SectorConfig` (Software, picker off); `"Place"`/`"Store"`/`"Sync"`. *Tests:* round trip; unknown fields kept at all five levels; `v = 2`; run mismatch; types, NaN, bounds, overlap, zones, rate, ownership. *Studio:* create the 3 modules first; move the Desk, rejoin.
2. Nested buildings, move-in, starter set, `"BuyBuilding"`. *Tests:* nesting, objects unchanged, budgets, fingerprints.
3. `CompanyClient` edit mode; the inventory (`buyUpgrade`, join loop, ShopClient Office tab); roof hidden in edit mode. *Tests:* 320 x 568 and 667 x 375; sends only id, x, z, r; one charge, lands in storage, a stored item earns, "Place" never charges. *Studio:* buy the Laptop, leave it stored, rejoin, place it.
4. The IPO completes the company: Bronze, card, Pokedex tab, seed (Studio only until S1), picker (Studio only), a test sector. *Tests:* one transform; Bronze once; seed capped and once; repeat refused; run check.
5-7. Software: `SectorSoftware`, `SectorArtSoftware` (keys unchanged), buildings 2-5, furniture, kept decor, `"BuyObject"`. *Tests:* no sector key in engine; fingerprints; budget refusals; D9 words.

**G-S, go / no-go:** (a) 6 plots at building 5 with full budgets on a low-end phone ≥ 30 fps **(estimate)**: 260 or 320; (b) 3+ players pick, build, arrange, IPO into a new sector, find the card, unaided; (c) S1, S3, S5 pass; (d) section 3's Studio checks. **No-go: fix before any other sector.**

8-13. Fintech, Biotech, Gaming (data, then art). *Tests:* parity ±5%, no new `addEarnings` site, D9 words, `id = 0`.
14. Gold, Platinum, weighted stamp clock, pass-share targets, bonus on, Hall of Fame; needs S2, S4, S6. *Tests:* tier edges, bonus cap, bonus never in valuation or offline pay, no Shares from stamps.
15. `BoardServer` (after the CLAUDE.md approval), FR-11; needs S7. *Tests:* 1.6's Studio, deny-list and name tests; value from the save only, after it.
16. Picker on for live servers; PUBLISH_RULES "2d"; publish.

## 7. Impact on other docs and branches

**Merge order:** `design-customize` sits on top of `visuals-garage`: a PR from it to `main` today would carry 40 commits and 19 files. Merge it only after `visuals-garage` lands on `main`.

**Clashes with docs/LONG_GAME_PROPOSAL.md** (`LG:` = its line):

| Clash | LONG_GAME | This doc / code | Resolution | Sims |
|---|---|---|---|---|
| Building price | office = 0.7 x fit (LG:38), prices LG:53-58 | was "50% of the stage threshold" (IpoConfig.lua:19-22) | LONG_GAME wins: a building costs its office's fitted price | S1-S3: none (`LONG_ITEMS` as is) |
| Office count | 7 offices, two in C+D (LG:53-58) | 5 buildings, one per stage (owner default) | 5 footprints, 7 purchases: Glass Tower and Global HQ become shell upgrades of building 5 (same price and order) | none: same items; S3 keeps 7 per sector |
| Desks, caps | 18 desks (LG:60), R1 cap by office (LG:108) | 11 fixed spots (EmployeeServer.lua:31-35) | each building adds hire spots in its new area; building 5 holds 18 + 3 (Extra Slots) + Extra Desk levels; R1 caps follow the 7 office purchases | none (counts unchanged); G-S counts 21+ desks |
| Earned decor | milestones (LG:78), Daily Day 7 piece (LG:88, 128), Boardroom skin (LG:92), prestige wing (LG:86) | furniture resets with the company (1.4) | earned pieces are **kept** (`pokedex.kept`), free in every company; bought copies reset; Boardroom = a pass furniture set, not saved (pass re-checked on join); prestige wing = perks (`ipo.perks`), kept | S1: kept pieces free; decorator profile |
| `addEarnings` list | 7 entries, none for sector models (LG:94) | 3 income models (section 2) | no new call site: models ride entry (1), the income loop | S3 fits each model |
| Moments | per-rung table (LG:66-74) | sectors, bought furniture | the same columns per sector; furniture never enters `LONG_K` (LG:38) or thresholds | S3 recounts per sector; gap ≤ 45 min (LG:79) |

Also: "the IPO is the last thing" (LG:1-3) holds per company; +5% per loop (LG:18) follows the IPO count only; seed, bonus and kept decor never count (LG:22-34); LG:82's "industry skin per IPO" becomes "pick a sector, replays chase stamps"; the Shares formula (LG:86) and the Shareholder's 2x (LG:92) are unchanged; LONG_GAME PR 4 (LG:118) = this doc's PR 1-7, its PR 7 (LG:120) = PR 8-13.

**Other docs:**
- **`design-tutorial` collides:** both add a save section and a module to TycoonCore (`KNOWN_SECTIONS` :84, payload, save gate :481) and daily_test.py:4269-4271. **`setupPlayer` order:** IpoServer (:793), fixedHires, EmployeeServer (:795), PoachServer, OnboardingServer (:797), **CompanyServer**, TaskServer (:798), **TutorialServer** (before Daily, TUTORIAL_PROPOSAL.md:106), DailyServer (:799, last); `init` alike. BoardServer is not in the chain: its join repair runs after `data.ready = true` (TycoonCore.lua:831). **Tutorial PR A merges first** (smaller, independent); Pokedex PR 1 rebases onto it.
- **Tutorial steps 1 and 4** (TUTORIAL_PROPOSAL.md:25, 28: own the Desk; own 2 upgrades) only work for Software. Per sector: step 1 = "own your sector's first upgrade" (free in every sector), step 4 = "own 2 of this company's upgrades"; buying completes them; step 1 waits while `OpenPanel = "Sector"`. New step: "Arrange your office".
- **Step 9** (line 33, notes 37-42): an IPO *completes this company*: a stamp, a card, the next sector. Resets: Cash, upgrades, buildings, bought furniture, eggs, valuation. Keeps: employees, HR, passes, boosts, shields, Shares, perks, IPO count, stamps, kept decor.
- **`content-bible`:** sections 1-6 = Software's package; "Titles and cosmetics" (243-251) drops the industry skins, adds stamp and company names; decision 9 (373) is answered; "The first 5 hours" (253) starts with the pick.
- **`building-pass`: park it (no merge).** docs/building_pass_integration.patch (`PlotBuildingVisuals` in `pcall`, `syncBuilding` in `syncRoom` and on join) and docs/studio_scripts/BuildingClient.lua (fades roof and walls while the character is inside) are built for 60 x 60, and the roof would block the top-down edit camera (the fade follows the character, not the camera). **Reused** in PR 2 and 6: shell data, budgets, `BUILDINGMATH`, the `pcall` plug-in, tools/building_test.py's style; PR 3 hides the roof in edit mode. BUILDING_PASS_PROPOSAL.md D-2 and section 3 change (sizes to 78 x 82, four shell sets).
- **`visuals-garage`, PLOT_VISUALS.md (14, 37), CLAUDE.md "Plot visuals" (32):** "the plot stays 60 x 60", the skyline, "six props identical in every room" and "the real Floor is the only solid" change.
- **CLAUDE.md, README, ROADMAP, PUBLISH_RULES:** `pokedex` in the save block, new modules and order, `CompanyRemotes`, PUBLISH_RULES "2d"; ShopConfig.lua:81-88 unchanged.
- **CLAUDE.md:29 (owner default, awaiting owner approval):** the board's OrderedDataStores break "Never add a second DataStore". New wording: "Never add a second DataStore, save loop or PlayerAdded data owner. One exception: `BoardServer` (ServerScriptService) may use the OrderedDataStores `Collection_v1` and `HallOfFame_v1` (and their `_Studio` twins) for the leaderboard. It writes only values read from the loaded save after that save succeeded, never saves player data, and wraps every call in `pcall`. Every other store stays under this rule." No board code before approval.

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
