# Companies, sectors and the Pokedex (proposal, design only)

Design only (2026-10-04, branch `design-customize`, revised from `47f0fe8`). No script, config or test changed. For the owner and the Claude sessions that will build it. Line numbers are for `47f0fe8`, whose `.lua`/`.py` files equal `visuals-garage` `7f5c141` (`main` has no PlotArt, PlotVisuals or Office tab yet). **(unverified)** = not checked in code; **(estimate)** = not measured; **(owner default)** = the owner may still veto; **(placeholder)** = a number the sims must size.

**Fixed by the owner:** **D-A** a bigger building contains the previous one and moves every object in, same coordinates from a door-side anchor. **D-B** an IPO founds a new company, seeded with some of the old one's money (never items). **D-C** every founding starts with picking a sector. **D-D** a sector is a full package on one engine; Software (today), Fintech, Biotech, Gaming launch together, Software first. **D-E** free placement, phone and PC. **P-1** one Pokedex entry per sector (state, stamp, replays). **P-2** an IPO completes the company and stamps its sector; the old company is a card, never a building. **P-3** all four sectors = the main goal (Hall of Fame); replays earn Gold and Platinum; a leaderboard. **P-4** old companies earn nothing; stamps give a small capped bonus. **P-5** the seed stays, funding only, numbers open.

**Owner defaults (P-6 and earlier):** employees follow the player; creatures keep their bodies, renamed per sector; 5 buildings per sector (building 5 serves Series C+D, Pre-IPO and IPO-ready, section 7); any sector can be picked next; legacy IPOs get no stamp (moot: no legacy saves, 1.2); an unplaced item still earns (section 4); size 78 x 84, re-checked in section 3 (**78 x 82**); hire desks fixed in v1; furniture earns nothing; a free, fixed starter set per building (D9); 45° rotation; part budget open until a phone test.

**New names** (none exists in any `.lua`/`.py`): `CompanyServer` (owns `pokedex`), `CompanyConfig`, `SectorConfig`, `Sector<Name>`, `SectorArt<Name>`, `CompanyClient`, `CompanyRemotes.CompanyAction`, `BoardServer` (no save section), OrderedDataStores `Collection_v1`, `HallOfFame_v1`. They replace the previous `companies` section.

## 1. Companies, sectors and the Pokedex

**1.1 A company** is one run of one sector's ladder: Cash, upgrades, buildings, furniture, layout, eggs in incubators, valuation. **The player** keeps the rest: employees, HR level, passes, boosts, shields, Shares, perks, IPO count and multiplier, `lifetime`/`best`, daily, onboarding, task stats, the Pokedex and its bonus (today's rule: IpoConfig.lua:6-8, 51). Only the active company exists in the world.

**1.2 The `pokedex` save section (new top-level section, rule A10).** The active company's live state stays where it is (`cash`, `owned`, `team`, `ipo.valuation`; TycoonCore.lua:421-433), so older code keeps playing it. The section holds what older code cannot know:

```lua
pokedex = {                  -- CompanyServer.serialize (optional: older saves have none)
  v = 1,                     -- format version
  run = number,              -- ipo.count the active company belongs to (A10 run check)
  active = {                 -- always exactly one
    sector = "Software",     -- SectorConfig key: never renamed or reused
    picked = boolean,        -- false = picker open (new player, run check); PickSector only then
    name = string,           -- from the sector's fixed list: no free text
    foundedAt = os.time(),
    engaged = number,        -- weighted engaged seconds in this company (stamp clock; 0 until LONG_GAME PR 2)
    passSeconds = { [passKey] = n },  -- of those, seconds while each Cash pass was owned (stamp targets)
    building = number,       -- buildings bought, 1 = Garage
    decor = { [objectKey] = n },                                   -- furniture owned
    objects = { { id = "Desk", x = -23, z = -40, r = 0 }, ... },  -- layout, anchor coordinates
  },
  sectors = {                -- the Pokedex; no entry = not started
    [sectorKey] = {
      state = "progress" or "done",  -- "done" never goes back
      stamp = 0 to 3,        -- best: 0 none, 1 Bronze, 2 Gold, 3 Platinum (never goes down)
      replays = number,      -- completions after the first
      firstAt = os.time(),   -- first completion (0 = none)
      bestEngaged = number,  -- fastest completion, engaged seconds (0 = unknown)
      card = { name, ipoNumber, at, engaged, ratio, building, owned = {...}, decor, objects }, -- latest completion
    },
  },
  kept = { [objectKey] = n },  -- earned decor (milestones, Day 7): free in every company (section 7)
  hallAt = number,           -- when all four were first done (Hall of Fame); 0 = not yet
  studio = boolean,          -- a Studio server saved this account: never on the live board (1.6)
}
```

- **Fields:** object `id` = an upgrade name or `<objectKey>#<n>`; `x`, `z` studs from the anchor, rounded to 0.5; `r` 0-7; at most 40 per company; an owned item without an entry is in the inventory (section 4). `ratio` = valuation at the IPO / IPO-ready valuation. Only the active sector may be `"progress"`. About 11 KB with four cards **(estimate)**.
- **Loader: the KEEP pattern at every level.** Unknown fields are stored and written back, like onboarding (OnboardingServer.lua:226, 243, 281), daily (DailyServer.lua:244, 261, 290), tasks (TaskServer.lua:712, 766, 800) and fixedHires (EmployeeServer.lua:657, 675, 694), but **at every nesting level**: the section, `active`, each `sectors[k]`, each `card`, each `objects[i]`. Those four keep only top-level fields; shop, team, poach and ipo keep none (no `unknown` table; EmployeeServer.lua:648), and a nested drop loses data on a rollback just like a top-level one (A10).
- **Versioning (new code, its own tests):** `v` rises only when a field changes meaning. No loader does this today: a save with a higher `v` is held as one opaque value, written back unchanged, and the session refuses `GoPublic`, `Place`, `BuyBuilding` and `PickSector`, so an older server never rewrites a newer format. Unknown sector keys are kept; while one exists `BoardServer` writes nothing. *Tests:* `v = 2` comes back deep-equal after a save; each refused action; no board write.
- **Bad values** (type, NaN, infinite, negative, out of range, unknown or duplicate id) are skipped with a warning; `stamp` clamped to 0-3; `"done"` with stamp 0 becomes 1; a `"progress"` entry that isn't active becomes `"done"` if stamped, else is dropped.
- **Wiring:** `KNOWN_SECTIONS` (TycoonCore.lua:84), `buildPayload` (:421-433), save gate (:481); daily_test.py:4269-4271 asserts the exact section list ("no new save section") and changes in the same PR. `CompanyServer.setupPlayer` after `OnboardingServer` (:797), before `TaskServer` (:798); full order with the tutorial in section 7.
- **Publish:** **Shut down all servers** and a PUBLISH_RULES "2d" note. Rollback floor stays `V_launch`: code from M4 keeps unknown sections (TycoonCore.lua:773-777, 434-438).
- **No legacy migration.** The game has not launched: it stays private until launch (PUBLISH_RULES.md:101), M4 was never published (:17), no real saves exist (LONG_GAME_PROPOSAL.md:88); "0 visits" can't be checked offline. **All test accounts are wiped together before launch** (`RemoveAsync` on a written list, PUBLISH_RULES.md:111): it deletes the whole key, so daily, tasks, onboarding and purchase receipts go too, and poach records (`gained`, `lost`) name other accounts, so every test account is in the same wipe. **A missing `pokedex`** = a new founding: `run = ipo.count`, Software, `picked = true` while the picker is off, building 1, no stamps.
- **A10 run check:** `run ~= ipo.count` means an older version ran an IPO (it reset Cash, `owned`, eggs, TycoonCore.lua:549-559, and paid no seed). Every version gates an IPO on valuation (IpoServer.lua:192-195), so the active sector gets `"done"`, Bronze if unstamped and a card (`engaged` 0: no Gold or Platinum); the new active company keeps the sector with `picked = false`, building 1, no seed. Several missed IPOs count as one.

**1.3 Picking a sector, on every founding.** A window (`OpenPanel = "Sector"`), four cards: icon, name, how it makes money, stamp, "New". It opens for a new player before the Garage, in every IPO and after a run check. `CompanyAction("PickSector", key)` only while `picked == false`; purchases wait until then.
- **Next sector (owner default): any enabled sector, the same included; none must be completed first.** Rewards steer instead: Bronze, the biggest bonus step, needs a new sector, and the picker preselects one. A forced order would lock a favourite away for 150+ h.
- `SectorConfig.PickerEnabled = false` until all four exist: everyone is Software.

**1.4 The IPO completes the company.** Today `goPublic` (IpoServer.lua:177-243) checks, then `commitIpo` (TycoonCore.lua:544-588) saves with a transform resetting Cash, `owned` and eggs (IpoConfig.lua:53-58). New:
1. A "Next company" step (the picker) before Confirm; `IpoAction("GoPublic", ipoNumber, sectorKey)` adds an enabled-sector check to today's (`ipoNumber == count + 1`, IpoServer.lua:179).
2. **One transform, one save** (TycoonCore.lua:548-564): the entry becomes `"done"`, `stamp = max(stamp, earned)`, `replays + 1` on a replay, `firstAt`, `bestEngaged`, a new `card`; `hallAt` on the fourth; a new `active` (building 1, empty layout, `picked = true`); the new sector `"progress"` if absent; `run = count + 1`; Cash = `StartingCash` + seed. Today's resets stay.
3. Only after that save works (TycoonCore.lua:565-587): the new sector's Garage, a stamp pop-up, the board write. A failed save changes nothing.

**Resets with the company (frozen in its card):** Cash, upgrades, buildings, furniture, layout, eggs, valuation. **Stays:** 1.1's player list.

**The card** sits in a new **Pokedex** tab of the IPO window (beside "IPO", "Shares Shop", "Leaderboard", IpoClient.lua:354): sector, name, stamp, IPO number, date, engaged hours, ratio, building, and a **top-down map** (one Frame per footprint, from sector data: no Parts). A 3D diorama needs the art on the client, but it lives in ServerScriptService: not in v1. `ResetNames` (IpoConfig.lua:60-65) and the keep list (IpoClient.lua:524-533) add buildings, furniture, stamps.

**1.5 Stamps, replays, Hall of Fame.**
- **Bronze:** the sector's first completion (any IPO). Bonus +1.5%.
- **Gold:** a replay completed within **1.0 T** engaged hours. +0.5%.
- **Platinum:** a replay within **0.8 T** and gone public at ratio **≥ 1.25**. +0.5%.
- **T** = the loop's reference engaged hours for a regular player (LONG_GAME section 1: 57 / 51.5 / 52 h for loops 1-3); every T and ratio is a **placeholder** for S6. Engaged seconds come only from the server's engaged clock (graded tasks, LONG_GAME section 2): Gold and Platinum wait for LONG_GAME PR 2.
- **Long sessions:** the stamp clock weighs engaged seconds like the valuation (100% for the first 3 engaged hours a day, 5% after, LONG_GAME_PROPOSAL.md:23), so playing past 3 h never makes Gold or Platinum harder.
- **Pass fairness:** 2x Cash makes a run about 15% shorter (48.7 vs 57.1 h, LONG_GAME section 6), so a target shrinks by the measured speed-up times the **share of the run's engaged seconds with the pass** (`passSeconds`; placeholder x0.85 for a whole run with 2x Cash). Passes owned at founding would be an exploit: buy 2x Cash right after founding, keep the full target, run 15% faster.
- **A replay** has the same content, priced by IPO count (`StageScale`), never by sector or stamp. Differences: a stamp clock in the IPO window (engaged hours against both targets), no repeated first-time hints, a stamp never goes down, `replays` counts it.
- **Hall of Fame:** the first time all four are `"done"`: `hallAt`, a title (named in the content bible), a gold Pokedex frame, a board entry. The game goes on: replays, and IPOs keep paying Shares and multiplier.

**1.6 Leaderboard.**
- **Today:** in-server only: IpoServer copies `IpoCount` and `IpoBest` onto players (IpoServer.lua:46-63), IpoClient sorts them (IpoClient.lua:750-786). No OrderedDataStore or cross-server board exists (grep; docs/reviews/FULL_REVIEW.md:126).
- **Ranks:** **Collection** = `1000 x stamp points + min(IPO count, 999)`, per sector Bronze 1, Gold 2, Platinum 3; **Hall of Fame** = earliest `hallAt`.
- **Storage:** `BoardServer` writes OrderedDataStores `Collection_v1`, `HallOfFame_v1` (in `pcall`), key UserId, from the loaded `pokedex` only, after the stamp's save succeeded; on join it repairs a lower stored value. It reads the top 50 every 10 minutes per server, as a second list in the Leaderboard tab.
- **Anti-cheat:** no client sends a score; capped at 12,999; tiers use the server's clock; no write with unknown keys.
- **Studio never reaches the live board.** Studio and live servers share the save key (PUBLISH_RULES.md:46), so Debug valuation grants (`IpoGrantValuation`, `IpoJumpReady`, IpoServer.lua:400-411), a Debug stamp or a Studio pick are saved like real play, and the join repair would copy them to the live board. Rules, all in `BoardServer` on the server, from the loaded save only: (a) every save made by a Studio server (`RunService:IsStudio()`) sets `pokedex.studio = true`, and nothing clears it; (b) an account with `studio` is never written, repaired or shown; (c) in Studio, BoardServer touches only `Collection_v1_Studio` and `HallOfFame_v1_Studio`; (d) a deny list (`BoardServer.REMOVED`, UserIds, server only) is never written, repaired or shown: a removal is list + `RemoveAsync` on both boards + publish, otherwise the join repair re-adds the account. Per account, not per stamp: a per-stamp flag leaks the IPO-count tie-break and `hallAt`. Dev accounts (the owner's too) stay off the board. *Test (daily_test, fake stores):* a `studio` save with four Platinum joins live: no write; a Studio session saves `studio = true` and writes only `_Studio`; a listed UserId: no write, no repair, not in the top 50; only BoardServer calls `GetOrderedDataStore`.
- **Names (FR-11):** the top 50 holds UserIds; the server looks names up (`UserService:GetUserInfosByUserIdsAsync`, in `pcall`, cached, with the 10-minute read; **unverified limits**), "Player" on failure; the client escapes `& < > " '` before rich text with one helper for both lists, which also fixes IpoClient.lua:780.
- **Studio** also needs "Enable Studio Access to API Services" (CONTRIBUTING.md:41). Roblox's request budgets **(unverified)**; one write per stamp and one read per 10 minutes is far below them **(estimate)**.

## 2. The sector package and content

**Shared engine** (never names a sector; a test fails on a sector key in engine code): `pokedex`, picker, IPO flow, stamps, seed, bonus, board; buildings, move-in, placement, budgets; SHOP > Office; the task engine and its four action types; creatures, eggs, odds, `fixedHire` (D9), poaching; daily, onboarding, HUD; the economy clock; the sim.

**Per sector** (`Sector<Name>` data, `SectorArt<Name>` art): identity (`key`, name, icon, palette, 12+ company names); 5 buildings (size, shell, desk skin, starter set); upgrades (key saved in `owned`, never reused; name, joke, price, Income, footprint, default spot; Software keeps today's six, TycoonCore.lua:65-72); furniture; tasks in `TaskConfig.Rows` format (TaskConfig.lua:49); per creature key a name, job (today's `role`, CreatureConfig.lua:56-104) and joke; egg names; one income model; bundles with fixed contents and `id = 0`. Art uses PlotArt's `P(...)` format (PlotArt.lua:9-23) and passes PlotVisuals' checks.

**Income models** (deterministic, capped, engaged time only; every number a **placeholder** for S3). **Software:** steady Income (today). The other three are `Sector<Name>.extra(data, seconds)`, Cash computed from **base Income** (`baseIncome`, TycoonCore.lua:677-680: no passes or bonus), added to the amount of the **existing income-loop call** (TycoonCore.lua:866; from LONG_GAME PR 2 `kind = "engaged"`, so the 3 h/day weight applies) and only while engaged. **No new call site:** daily_test.py:4327-4334 counts calls per file and fails on a new one until reviewed. Never in offline pay (:825), the away bank or `baseIncome` itself (task rewards would double too).
- **Fintech:** interest r per minute on Cash held, on at most H seconds of base Income (hoarding past H earns nothing).
- **Biotech:** every N engaged minutes (a visible timer that pauses when not engaged, never a roll) P seconds of base Income, in that second's amount.
- **Gaming:** a graded Timing task (a `TaskConfig` row; its own pay goes through TaskServer.lua:257 like every task) starts a launch: base Income x L for D minutes, then C minutes of cooldown; the extra (L - 1) rides the income loop.
- **Parity:** each sector's item Incomes are lowered until item Income plus the model's average extra per engaged hour is within ±5% of Software on every rung for every `LONG_PLAYERS` profile (S3), with no bot or hopper gain (S4, S5). Passes multiply Cash afterwards, the same for all four. Whether a model ships at all, and whether Fintech may reward holding Cash, is the owner's (section 8).

**Content:** the content bible (`content-bible`) names 168 things for Software (upgrades 42, decor 22, hires 18, desks 18, events 12, titles 9, skins 9, board requests 8, offices 7, products 6, eggs 6, caller groups 6). Per new sector **(estimate)**: about 185 names plus 48 caller lines and about 75 art builds (42 props, 22 furniture, 5 shells, desk skins); three sectors about 555 names and 225 builds. In code today: 6 props (118 parts, PLOT_VISUALS.md:34), 5 rooms, 12 creatures, 3 eggs (CreatureConfig.lua:23-41), 1 task (`Call`). Mechanics are reused: no new action type, no new body.

## 3. Plot space (re-verified in the code, recomputed)

**What the code says** (read again, not copied):
- **Plots:** `PLOT_SPACING = 90`, `MAX_PLOTS = 6` (TycoonCore.lua:74, 76); `plotCenter` x = -225 + 90 x (slot - 1), z 150 (:123-126). `Floor` 60 x 1 x 60 on the center (:736): z 120-180, 30 studs between floors (`floorSize`, PlotArt.lua:31).
- **Front = +Z:** BuySign z +24 (TycoonCore.lua:75), IpoSign (21, +24) (IpoServer.lua:21), spawn +12 facing it (TycoonCore.lua:698-700); incubators z -25, hire rows -10 / 2 / 14, `minAisle = 6` (PlotArt.lua:33-69). **Anchor = front-center of the floor, world z 180.**
- **VIP Lounge:** center (0, 0.5, 70), 36 x 24, walls 10 high, 1 thick (ShopServer.lua:35-37, 636-650): outer faces x ±18.5, z 57.5-82.5; the 8-wide door (:38, 653) in the +Z wall faces the plots; its `Touched` (:683) is the game's only one; a non-VIP inside is moved to **z 88** (:839). "Between the spawn and the garage plots" (:35): spawn at z < 58 **(unverified)**.
- **Skyline** (IpoReady): local z -49 to -43, x ±29 (PlotArt.lua:699-707): world z 101-107.
- **Nothing else is scripted in the world.** Parts come only from TycoonCore (:91), PlotVisuals (:92), IpoServer (:293-300, sign), EmployeeServer (:69, incubators), ShopServer (:97, lounge), CreatureModels (bodies), OnboardingClient (:60, invisible, client only). PoachServer gets `plotCenter` (TycoonCore.lua:650) and never uses it: no walk between plots.
- **Building pass** (BUILDING_PASS_PROPOSAL.md section 3, branch `building-pass`): inner face 0.2 past the floor, wall 0.8, roof 1.5 past it: **2.3 per side beyond the inside size**.
- **Not in the repo:** Baseplate size and position, SpawnLocation, hand-placed parts, Terrain (docs/STUDIO_SYNC.md:37 has only the Baseplate's color).

**Recomputed** (sideways centered, backward from the anchor):
- **Width W:** roof gap = 90 - W - 4.6; with the game's own aisle minimum (6, PlotArt.lua:68) as the gap, W ≤ 79.4: **78**.
- **Depth D:** past W = 48.4, plots 3 and 4 stand behind the lounge (at 78 they span x ∓84 to ∓6). Back roof edge = 180.2 - D - 2.3; keeping the kick-out spot (z 88) plus a 6-stud aisle clear: edge ≥ 94, D ≤ 83.9: **82**. One rule for all plots, one set of art.

**Largest building: 78 x 82 inside (1.78x the area), no plot moved.** **Versus the earlier 78 x 84:** same width; 2 studs less depth, because the clearance now comes from code (kick-out z 88, ShopServer.lua:839; `minAisle`, PlotArt.lua:68) instead of an estimated 10 studs from the door. Outer roofs reach x ±266.3 (floors today ±255): **the Baseplate must be 534+ wide (unverified)**. Nested sizes **(estimate)**: 60 x 60, 64 x 66, 68 x 70, 72 x 76, 78 x 82 (back walls at world z 120 / 114 / 110 / 104 / 98).

**Changes:** the skyline sits inside buildings 4-5 (`BACKDROP_Z`, PlotVisuals.lua:44): it goes or becomes a picture; flush `FloorExtension` strips (`Floor` parts may collide, PlotVisuals.lua:590-592); 60 x 60 assumptions go per building (PlotArt.lua:31; PlotVisuals.lua:544, 643). **Bigger** needs `PLOT_SPACING` ≥ W + 10.6 (100 wide: 112; read through `plotCenter`, TycoonCore.lua:601, 639, 650).

**Studio by hand (owner, read only):** (1) Workspace > Baseplate: Size and Position; needed x -267 to 267, z 95 to 182, or more. (2) Workspace's other children (not Terrain, Camera, `<name>_Startup`, `VipLounge`, `OnboardingArrow`, `PREVIEW_STAGES`): name, Position, Size; especially the SpawnLocation and anything at z 85-120 or past x ±225. (3) Terrain near the plots. (4) Workspace > StreamingEnabled.

## 4. The office: placement, checks, budget, phone

- **Fixed:** Floor and extensions (the only solids), spawn and lane, both signs, 5 incubators and the Hatch prompt (EmployeeServer.lua:37-40, 531), 11 hire spots and desks (EmployeeServer.lua:31-35; PlotVisuals.lua:199-203). **Movable or stored:** the upgrade props (default = today's slot, `itemOffset`/`spawnItem`, TycoonCore.lua:131-135, 189) and furniture. Employees wander around a server-set `Home` (EmployeeServer.lua:178-199; EmployeeClient.lua:960): nothing changes.
- **Move-in (D-A):** `objects` stay as they are; building n+1 contains n and no zone moves, so no check can fail. The new area gets only the starter set; with a full budget a starter piece goes to the inventory.
- **Checks** on `CompanyAction` (`"Place", id, x, z, r`; `"Store", id`; `"Sync"`; `"PickSector", key`): `data.ready` (false during load and the IPO save, IpoServer.lua:212-213); `id` a string under 40 chars, finite `x`/`z`, whole `r` 0-7; ownership; the rotated footprint inside the building; overlap ≤ 0.1 stud (floor marks may lie under, PlotVisuals.lua:38); no reserved zone (`PlotVisuals.zones`, :504-531); budgets; 4 requests/s, 120/min. **One pure function in `CompanyConfig`:** the client previews, the server decides; a test proves each footprint covers its art (`boxOf`, :65).
- Placement never changes Income (`totalIncome` reads no position, TycoonCore.lua:137-145); buildings and furniture have none (economy_sim.py:1063); no new `addEarnings` call (daily_test.py:4327-4334); **no `Touched` handler** (taps hit footprints; decor has `CanQuery` off, PlotVisuals.lua:105; daily_test.py:4254-4256).
- **Part budget:** `MAX_PARTS = 260` per room, `MAX_LIGHTS = 3` (PlotVisuals.lua:39-40), raised from 220 with no written reason (ROADMAP.md:41); rooms use 256 / 244 / 254 / 253 / 257 (ROADMAP.md:42); the props take 118 (daily_test.py:3858), leaving about 3 furniture pieces. **Proposal:** draw only owned desks, 320 per plot, a budget bar; bigger walls cost no parts. **No change before gate G-S's 6-plot phone test** (owner default); if it fails, 260 with 2-part desks.
- **Phone and PC:** edit mode is a window (`OpenPanel = "Office"`): the tray and thumbstick hide (TaskClient.lua:28; ShopClient.lua:725); entry "Arrange your office" in SHOP > Office (tabs, ShopClient.lua:196; Office tab :496-541), no new HUD slot. Top-down camera, about 3.5 px per stud at 78 x 82 on 667 x 339 **(estimate)**, so objects can also be picked from a strip; pinch zooms; drag, snap 0.5, red when refused, one `"Place"` on lift; Rotate, Store, Done 56 px **(estimate)**; PC: drag, R, Delete, E. Checked with Test > Device and top bars 0 / 36 / 58, like `TRAY_TESTS`.
- **Inventory (owner decision).** Buying an upgrade or a furniture piece sends it to the company's **inventory** (owned minus `objects`); right after the purchase a **"Place now"** button (on the Office card and the pop-up) opens edit mode with the item at its default spot; ignoring it leaves the item stored. Placing is free placement with rotation. **An unplaced item still earns (owner default):** Income reads `owned` only (TycoonCore.lua:137-145); placing is looks only. **Changes, in PR 3** (a stored item needs edit mode to come out): `buyUpgrade` (TycoonCore.lua:272-288) stops the pop-in at the fixed slot (`spawnItem(data, i, upg, true)`, :285) and the join loop (:811-815) draws only placed objects; ShopClient's Office tab (:496-573) gains "Place now" and an "In storage" mark. Until PR 3 a purchase pops in at its default spot, written as an `objects` entry. **The buy stays as it is:** one charge in `buyUpgrade` after `checkUpgradePurchase` (ready, number, owned, order, Cash, 0.4 s; :243-270), "already yours" refuses a second buy, `handleShopAction` (ShopServer.lua:704-717) unchanged; "Place now" sends only `"Place"`, which never charges.
- **Shop:** SHOP > Office gains Buildings and Furniture; `"BuyBuilding", n` and `"BuyObject", n` on `ShopAction` (ShopServer.lua:701-715, 803-804), checked like `checkUpgradePurchase` (TycoonCore.lua:243) plus "stage reached" and "building n-1 owned". A building costs its LONG_GAME office price (section 7). Cash only in v1; no odds words (daily_test.py:4343).

## 5. Economy: seed, collection bonus, risks, sims

**5.1 Seed (P-5).** The new company starts with `StartingCash` (0, IpoConfig.lua:44) plus **s% of the old company's Cash at the IPO, capped at c% of the new first rung's prices**; s = 10, c = 25 are **open placeholders** until S1 passes (today's six upgrades cost $7,025, TycoonCore.lua:65-72: cap $1,756; LONG_GAME's Garage items about $131K: about $33K). Cash only; a gift (no `addEarnings`); paid once, inside the IPO transform. **The dividend is removed:** it was passive income from held companies, which P-4 forbids and P-2 removes.

**5.2 Collection bonus (P-4).** Proposal: a **Cash multiplier on Income**, +1.5% per Bronze, +0.5% for Gold, +0.5% for Platinum: 2.5% per sector, **capped at +10%** **(placeholders, S2)**. Applied with the passes (`updateIncome`, TycoonCore.lua:148-152), **never valuation**: from LONG_GAME PR 2 valuation counts base Income only (LONG_GAME section 6), so the bonus buys sooner and never moves the clock. **It stays 0 until PR 2**: today two paths add the whole Income, passes included, to the valuation: the income loop (TycoonCore.lua:865-866) and **offline earnings** (:819-827, `income.Value` through `addEarnings` at :825). Rule: the bonus never enters `baseIncome` (:677-680), offline or away pay, or the valuation. Size: a tenth of 2x Cash, which saves about 15%, so about 1-2% per run **(estimate)**. **Fallback** if S2 fails: a cheaper first rung (the Garage is 1.5 of 57 h), which multiplies nothing.

**Interactions:**
- **2x Cash (ShopConfig.lua:41), VIP (:50), IPO multiplier (IpoConfig.lua:162-165):** all multiply (x3.3 at most with the bonus); Cash only, so the stack never shortens the clock after PR 2.
- **Shareholder (2x Shares, ShopConfig.lua:88; `sharesFor`, IpoConfig.lua:168-172):** nothing to double. **Rule: no stamp ever pays Shares**, or the pass doubles a permanent reward every replay.
- **Cash packs (ShopServer.lua:537-541), daily Cash (DailyServer.lua:177), task rewards:** sized from Income, so up to +10%; fixed contents (D9 safe); gifts after PR 2.
- **Away bank, Night Shift** (base Income, LONG_GAME section 2): excluded. **Seed:** bounded by its cap.
- **Extra Slots, Auto-Hatch, Headhunter, Instant Hatch, Poach Shield, Luck Boost (`changesOdds`, ShopConfig.lua:134); all six perks:** none. **D9:** stamps never change odds; stamps and bonus are earned only, never sold, never random.

**5.3 Risks.**
- **IPO pace is unchanged:** an IPO needs earned valuation (IpoServer.lua:123-135, 192-195). Seed and bonus never touch it.
- **Compounding:** the bonus multiplies with both Cash passes; switched on before PR 2 it would shorten every IPO, most for pass owners. Without pass-adjusted targets, Gold and Platinum are about 15% easier with 2x Cash.
- **Four economies:** a faster or idle-friendly sector becomes the only choice; each must hit every rung within ±5% of Software for every LONG_GAME profile. Income models are the main risk (interest rewards hoarding, launches stack with passes). Prices follow the IPO count, never sector or stamps.
- **Hopping and farming the first rung:** only an IPO founds a company (IPO-ready valuation, cooldown, IpoConfig.lua:45; 50+ h). A stamp needs a whole ladder; a founding's gifts (seed, starter set) are capped and bounded by the IPO rate.
- **Duplicate seed:** paid only inside the one transform; `ipoNumber` blocks a repeat (IpoServer.lua:179); a failed save changes nothing (TycoonCore.lua:565-567); the run check pays none.
- **Alts:** stamps can't be given, traded or poached; LONG_GAME's R1-R3 stand. **Rollback:** older code keeps `pokedex` frozen.

**5.4 Simulate before any build** (tools/economy_sim.py: `--long`, `--active`, `--ipo`, `--daily`, :1684-1687; a new `--pokedex` mode). Pass marks are **placeholders**:
- **S1 seed:** `--long` with 0 / 10% / 25% cap. Pass: ≤ 5% faster per loop.
- **S2 bonus:** 0 / 1 / 4 / 8 / 12 points x passes none / 2x Cash / VIP / both, loops 2-12. Pass: at the cap ≥ 95% of no-bonus hours for every pass set; both passes gain ≤ 2 points more than none.
- **S3 parity:** each model fitted to Software, dedicated / regular / casual (`LONG_PLAYERS`, :1183). Pass: every rung ±5%.
- **S4 bots:** LONG_GAME's macro and task-bot per sector. Pass: no sector faster for a bot.
- **S5 sector hopping:** always the fastest sector vs one sector, 10 IPOs. Pass: < 3% apart.
- **S6 tier targets:** replay hours per profile and pass set against T, 0.8 T, ratio 1.25. Pass: Gold on ≥ 50% of regular replays, Platinum on ≥ 20% of dedicated ones, pass owners within ±5 points.
- **S7 board exploits:** stamp points per 100 engaged hours for (a) always a new sector vs replays, (b) IPO at IPO-ready vs waiting for 1.25, (c) the task-bot. Pass: (a), (b) within 10% of normal play; (c) never above the dedicated human.
- **Duplicate seed** is a test: a retried failed IPO save, a repeated `GoPublic` and a run mismatch pay the seed exactly once.

## 6. Build plan

Each PR: claim its scripts, `python3 tools/daily_test.py` passes, F5 with no red errors, publish with **Shut down all servers**; create new modules in Studio before pasting the scripts that require them (`WaitForChild` without a timeout hangs, PUBLISH_RULES 2b). **PR 1 ships the whole `pokedex` format** (every field of 1.2 loaded, checked and written back while unused): code that knows a section drops fields it doesn't know (A10), so a later field would be lost on a rollback. PR 1-7 don't need LONG_GAME; PR 8-14 need its PR 2 (engaged clock, base valuation).

**Engine**
1. `pokedex` save (full format, missing-section default, run check, versioning); `CompanyServer`, `CompanyConfig`, `SectorConfig` (Software, picker off); layout-driven `spawnItem`, `"Place"`/`"Store"`/`"Sync"`. *Tests:* round trip; unknown fields kept at each of the five levels; no section = a new founding; `v = 2` and unknown sector kept; run mismatch; types, NaN, bounds, overlap, zones, rate, ownership. *Studio:* create the 3 modules, paste TycoonCore, ShopServer; move the Desk, rejoin.
2. Nested buildings, floor strips, move-in, starter set, `"BuyBuilding"`. *Tests:* nesting, objects unchanged on move-in, budgets, stage 1 fingerprints. *Studio:* buy Seed; the Desk stayed.
3. `CompanyClient` edit mode; the inventory: buy to storage, "Place now" (TycoonCore `buyUpgrade` and join loop, ShopClient Office tab). *Tests:* 320 x 568 and 667 x 375, top bars 0/36/58; sends only id, x, z, r; a buy charges once and lands in storage; a stored item earns; "Place" never charges. *Studio:* Test > Device; buy the Laptop, leave it stored, rejoin, place it.

**Pokedex**
4. The IPO completes the company: Bronze, card, Pokedex tab, seed (Studio only until S1), `"GoPublic"` with a sector; the picker on every founding, `PickerEnabled` in Studio only, a second sector as a test fixture. *Tests:* one transform; Bronze once; seed capped and paid once; repeat refused; run check; picker only while unpicked. *Studio:* paste IpoConfig, IpoServer, CompanyServer, TycoonCore, IpoClient, CompanyClient; IPO twice; rejoin.

**Software slice**
5. `SectorSoftware` + `SectorArtSoftware` (today's content, keys unchanged). *Tests:* no sector key in engine; fingerprints unchanged.
6. Software buildings 2-5, desk skins, starter sets, skyline handled. *Studio:* walk buildings 1-5.
7. Software furniture, `"BuyObject"`. *Tests:* footprints, budget and light refusals, D9 words.

**G-S, go / no-go:** (a) 6 accounts, every plot at building 5 with a full budget, a real low-end phone ≥ 30 fps **(estimate)**: pick 260 or 320; (b) 3+ players pick, build, arrange on a phone unaided, IPO into a new sector, find the card, rejoin; (c) S1, S3, S5 pass; (d) section 3's Studio checks done. **No-go: fix and repeat before any other sector.**

**Sectors** (after LONG_GAME PR 2)
8-9. Fintech: `SectorFintech` (texts, tasks, interest), then `SectorArtFintech`. *Tests:* parity ±5%, D9 words, `id = 0`.
10-13. Biotech (research payout), Gaming (launch): the same.

**Tiers and board**
14. Gold and Platinum, stamp clock, bonus on, Hall of Fame title; needs S2, S4, S6. *Tests:* tier edges, bonus cap, bonus never in valuation, no Shares from stamps.
15. `BoardServer`, second Leaderboard list, FR-11 fixed; needs S7. *Tests:* value from the save only, after the save, capped. *Studio:* API Services on, earn a stamp, see the `_Studio` board.
16. Picker on for live servers; PUBLISH_RULES "2d"; publish.

## 7. Impact on other docs and branches

**Clashes with docs/LONG_GAME_PROPOSAL.md** (`LG:` = its line):

| Clash | LONG_GAME | This doc / code | Resolution | Sims |
|---|---|---|---|---|
| Building price | office = 0.7 x fit (LG:38), prices LG:53-58 | was "50% of the stage threshold" (section 4; IpoConfig.lua:19-22) | LONG_GAME wins: a building costs its office's fitted price | S1-S3: none (`LONG_ITEMS` as is) |
| Office count | 7 offices, two in C+D (LG:53-58) | 5 buildings, one per stage (owner default) | 5 footprints, 7 purchases: Glass Tower and Global HQ become shell upgrades of building 5 (same price and order, no new size) | none: same items; S3 keeps 7 per sector |
| Desks, caps | 18 desks (LG:60), R1 cap by office (LG:108) | 11 fixed spots (EmployeeServer.lua:31-35) | each building lists hire spots in the area it adds; building 5 holds 18 + 3 (Extra Slots) + Extra Desk levels; R1 caps follow the 7 office purchases | none (counts unchanged); G-S counts 21+ desks |
| Earned decor | milestones (LG:78), Daily Day 7 piece (LG:88, 128), Boardroom skin (LG:92), prestige wing (LG:86) | furniture resets with the company (1.4) | earned pieces are **kept** (`pokedex.kept`): free in every new company's inventory; bought copies reset; Boardroom = a pass furniture set, not saved (pass re-checked on join); prestige wing = perks, kept in `ipo.perks` | S1: kept pieces free; a "decorator" (10% of Cash on furniture) ≤ 5% slower |
| `addEarnings` list | 7 entries, none for sector models (LG:94) | 3 income models (section 2) | no new call site: models ride entry (1), the income loop | S3 fits each model |
| Moments | per-rung table (LG:66-74) | sectors, bought furniture | per sector the same columns; furniture never enters `LONG_K` (LG:38) or thresholds | S3 recounts moments per sector; longest gap ≤ 45 min (LG:79) |

Also: "the IPO is the last thing" (LG:1-3) holds per company; +5% per loop (LG:18) follows the IPO count only; seed, bonus and kept decor are gifts that never count (LG:22-34); LG:82 "an industry skin per IPO" becomes "loops 2+ pick a sector, replays chase stamps"; the Shares formula (LG:86) and the Shareholder's exact 2x (LG:92) are unchanged, stamps add no Shares; LONG_GAME PR 4 "Office framework" (LG:118) = this doc's PR 1-7, its PR 7 "industry skin 1" (LG:120) = PR 8-13.

**Other docs:**
- **`design-tutorial` collides:** both add a save section and a server module to TycoonCore (`KNOWN_SECTIONS` :84, payload, save gate :481) and to daily_test.py:4269-4271. **Combined `setupPlayer` order:** IpoServer (:793), fixedHires, EmployeeServer (:795), PoachServer, OnboardingServer (:797), **CompanyServer**, TaskServer (:798), **TutorialServer** (after Task, before Daily, its own rule: TUTORIAL_PROPOSAL.md:106), DailyServer (:799, last); `init` in the same order. BoardServer has no section and is not in the chain: its join repair runs after `data.ready = true` (TycoonCore.lua:831). **Tutorial PR A merges first** (smaller, no Pokedex dependency); Pokedex PR 1 rebases and adds `pokedex` to the same lines.
- **Tutorial steps 1 and 4** (TUTORIAL_PROPOSAL.md:25, 28: own the Desk; own 2 upgrades) only work for Software. Per sector: step 1 = "own your sector's first upgrade" (`Sector<Name>` upgrade 1, free in every sector), step 4 = "own 2 of this company's upgrades"; texts from the sector package; buying completes them (placing is optional, section 4); step 1 waits while `OpenPanel = "Sector"`. A new "Arrange your office" step.
- **Step 9 "Going public"** (line 33, notes 37-42): an IPO now *completes this company*: a stamp, a Pokedex card, then the next sector. Resets: Cash, upgrades, buildings, bought furniture, eggs, valuation. Keeps: employees, HR, passes, boosts and shields, Shares, perks, IPO count, stamps, kept decor.
- **`content-bible`, CONTENT_BIBLE.md:** sections 1-6 = Software's package; "Titles and cosmetics" (243-247) drops the five industry skins and adds stamp names, the Hall of Fame title and company names; decision 9 "Loop skins" (373) is answered; "The first 5 hours" (253) starts with the pick; three more bibles.
- **`building-pass`, BUILDING_PASS_PROPOSAL.md D-2 and section 3:** per-building sizes up to 78 x 82; "25 apart" becomes 7.4; four shell sets.
- **`visuals-garage`, PLOT_VISUALS.md (14, 37) and CLAUDE.md "Plot visuals" (32):** "the plot stays 60 x 60", the skyline rule, "six props identical in every room" and "the real Floor is the only solid" change; `newPlot`/`setStage` (PlotVisuals.lua:235-269) per building and sector.
- **CLAUDE.md, README, ROADMAP, PUBLISH_RULES:** `pokedex` in the save block, the new modules and their order, configs, `CompanyRemotes`, the file list, PUBLISH_RULES "2d".
- **CLAUDE.md:29, the DataStore rule (owner default, awaiting owner approval):** the board's OrderedDataStores break "Never add a second DataStore". New wording: "Never add a second DataStore, save loop or PlayerAdded data owner. One exception: `BoardServer` (ServerScriptService) may use the OrderedDataStores `Collection_v1` and `HallOfFame_v1` (and their `_Studio` twins) for the leaderboard. It writes only values read from the loaded save after that save succeeded, never saves player data, and wraps every call in `pcall`. Every other store stays under this rule." No board code before approval.
- **ShopConfig.lua:52 (Shareholder text):** unchanged; the IPO window says stamps aren't doubled.

## 8. Open questions (unresolved, most important first)

1. **Tier rules:** Gold 1.0 T, Platinum 0.8 T plus ratio 1.25, targets shortened for pass owners (recommend), or pass-neutral rules instead?
2. **Collection bonus:** a Cash multiplier, +1.5 / +0.5 / +0.5% per sector, cap 10%, never valuation (recommend), or a cheaper first rung?
3. **Leaderboard:** Collection plus Hall of Fame (recommend), or also a fastest-Platinum board per sector?
4. **Fintech, Biotech, Gaming income models:** the mechanics (only if S3-S5 pass) or today's Income with themed text? Fintech's interest rewards holding Cash, against the buy loop: keep it, or a model that pays for spending?
5. **78 x 82 enough,** or move the plots (`PLOT_SPACING` 112)? Decide at G-S, after the Studio checks.

## What I did not verify

- The world outside scripts (Baseplate, SpawnLocation, hand-placed parts, Terrain, StreamingEnabled): no Studio or MCP was used; section 3 lists the checks.
- Roblox's OrderedDataStore budgets and limits; ViewportFrame cost; a fourth IPO-window tab at phone width; camera scale.
- Why `MAX_PARTS` is 260; phone frame rates.
- Every economy number (seed, bonus, T, ratio, pass factor, sim pass marks) and the content counts: placeholders or estimates.
- Other branches were read with `git show`, not run; LONG_GAME PR 2 doesn't exist yet; `daily_test.py` was not run (docs only).
