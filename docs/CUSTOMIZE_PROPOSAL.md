# Companies, sectors and your office (proposal, design only)

Design only (2026-10-04, branch `design-customize`, revised from `2d91efd`). No script, config or test was changed. Written for the owner and for the Claude sessions that will build it. Line numbers are for `2d91efd`, whose `.lua` and `.py` files are identical to `7f5c141` (`git diff` is empty). **(unverified)** = not checked in code; **(estimate)** = a number I did not measure; **(owner default)** = a default the owner may still veto.

**Fixed by the owner (not re-opened here):**
- **D-A Moving in.** Buying a new building moves every owned object in by itself, at the same coordinates. Each building is bigger than the last and contains its whole footprint. Positions are measured from a fixed anchor on the door side, so every position stays valid and the extra space is empty.
- **D-B IPO = a new company.** The player keeps the old company (building, objects) and founds a new one, seeded with a percentage of the old company's money. The seed is money only, never items. A player can hold several companies.
- **D-C Sector first.** Founding a company (the first one, and each one after an IPO) starts with choosing a sector, before the garage. After an IPO the sector may change.
- **D-D Sector packages.** A sector brings its own tasks, objects, names, building theme, office look and way of making money, all drawn from the real field. The shared engine (buildings, placement, saves, shop, task engine) is built once. Launch sectors: Software/SaaS (today's game), Fintech, Biotech, Gaming, all four together. Build order: engine, then Software end to end, then the other three.
- **D-E Free placement** (drag anywhere, rotate) on phone and PC.

**Owner defaults:** held companies earn a small passive amount (1.4); hire desks are not movable in v1; furniture earns nothing and a stored upgrade keeps earning; each new building comes with a free, fixed starter set (never random, D9); rotation in 45° steps; the part budget stays open until a phone test with 6 full plots (section 6).

**New names (none exist in the repo: `grep` over every `.lua` and `.py`):** `CompanyServer` (ModuleScript, ServerScriptService), `CompanyConfig` and `SectorConfig` (ModuleScripts, ReplicatedStorage), one `Sector<Name>` data module per sector (ReplicatedStorage) and one `SectorArt<Name>` (ServerScriptService), `CompanyClient` (LocalScript, StarterPlayerScripts), remote `CompanyRemotes.CompanyAction`, save section `companies`. They replace the first draft's `OfficeServer` / `office`.

## 1. Companies and sectors

### 1.1 What a company is

A company is one sector plus one run of the ladder: its building, its placed objects and furniture, its upgrades and its Cash. **The player** keeps everything that is prestige or account-wide: IPO count and multiplier, Shares, perks, `lifetime` and `best`, passes, boosts and shields, the daily streak, onboarding and task stats, and employees (today's rule, IpoConfig.lua:8 and 51; open question 1).

Only the **active** company is played and built on the plot. Held companies are not built in the world (part budget, section 6): a **Portfolio** tab in the IPO window (next to "IPO" and "Shares Shop", IpoClient.lua:879-943) shows each one as a card: name, sector, building, IPO number, valuation at the IPO, dividend.

### 1.2 Data model: a new top-level section `companies` (rule A10)

The active company's live state stays where it is today: `cash`, `owned`, `team` and `ipo.valuation` (TycoonCore.lua:421-433), so older code keeps playing it unchanged. The new section holds only what older code cannot know: the sector, the building and layout, and the held companies.

```lua
companies = {                  -- CompanyServer.serialize (optional: written once a sector is chosen or anything is placed)
  v = 1,                       -- format version; a higher one is kept unchanged and played as Software for the session
  run = number,                -- ipo.count the active record belongs to (A10 check, 1.5)
  nextId = number,             -- company ids 1, 2, 3 ... per player, never reused
  active = {
    id = number, sector = "Software", name = string, -- name: from the sector's fixed list (no free text, no filtering)
    foundedAt = os.time(),
    building = number,         -- buildings bought: 1 (Garage) .. #buildings of the sector (always the biggest one, D-A)
    decor = { [objectKey] = n },                         -- furniture owned (upgrades stay in `owned`)
    objects = { { id = "Desk", x = -23, z = -40, r = 0 }, ... }, -- one layout, anchor coordinates (section 4)
  },
  held = {                     -- older companies, newest first, at most 4 (1.3), frozen at their IPO
    { id, sector, name, foundedAt, ipoAt = os.time(), ipoNumber = number,
      building = number, owned = { upgrade names }, decor = {...}, objects = {...},
      valuationAtIpo = number, baseIncomeAtIpo = number, dividend = number }, -- dividend: Cash per engaged second (1.4)
  },
  archive = { { sector, name, ipoNumber, valuationAtIpo }, ... }, -- retired companies (1.3), at most 50
}
```

- **Per object:** `id` (an upgrade name, or `<objectKey>#<n>` for the n-th copy of a furniture piece), `x`, `z` (studs from the anchor, rounded to 0.5), `r` (0-7, 45° steps). No `y`: nothing stacks in v1. At most 40 objects per company. An upgrade with no entry stands at its default spot, so a save without `companies` looks exactly like today.
- **Size (estimate):** about 40 bytes per object in JSON; active + 4 held at 40 objects is about 9 KB.
- **Bad values** (wrong type, NaN, infinite, outside the building, unknown id, duplicate id) are skipped with a warning. An **unknown sector** (newer save, or a sector removed) keeps the record unchanged and plays Software for that session, writing the record back as it was (like `unknownSections`, TycoonCore.lua:434-438).
- **Wiring:** `companies = true` in `KNOWN_SECTIONS` (TycoonCore.lua:84), a `companies = CompanyServer.serialize(data)` line in `buildPayload` (:421-433), `data.companies` in the save gate (:481). tools/daily_test.py:4269-4271 asserts the exact section list and changes in the same PR. `CompanyServer.setupPlayer` runs after `IpoServer` (run check) and `EmployeeServer`, before `TaskServer` (tasks read the sector) and `DailyServer` (last, TycoonCore.lua:793-799).
- **Publish:** Shut down all servers (a new section, docs/PUBLISH_RULES.md section 3). The rollback floor stays `V_launch`: code from M4 on keeps `companies` frozen (TycoonCore.lua:773-777).

### 1.3 Cap and cost (proposal)

- **At most 5 companies: 1 active + 4 held (owner default proposal).** When an IPO would make a fifth held company, the IPO window asks which one to retire (preselected: the oldest). A retired company moves to `archive`: a name card with no building, no layout and no dividend. Why 4: save size, the Portfolio fits one phone screen, and the total dividend is capped anyway (1.4).
- **Founding costs nothing extra.** The price is the IPO itself: the new company starts at the Garage with no upgrades, buildings or furniture (D-B). The IPO reward (multiplier, Shares) stays as today.
- **Seed (owner default proposal):** **10% of the old company's Cash at the IPO, capped at 25% of the price of everything in the new company's first rung.** Today that rung is the six upgrades, $7,025 (TycoonCore.lua:65-72), so the cap is about $1,756; on the LONG_GAME ladder the Garage items total about $131K, so the cap is about $33K **(estimate, from LONG_GAME section 3)**. The seed is a gift: never through `addEarnings`, never valuation (like daily Cash). It is paid once, inside the IPO save (1.5).

### 1.4 Held companies pay a small dividend (owner default)

- Each held company pays **1% of its base Income at the IPO** (no passes, no IPO multiplier) into the active company, **only per engaged second** (LONG_GAME section 2: a graded task in the last 180 s). Never offline, never away.
- **All dividends together are capped at 10% of the active company's base Income** at that moment.
- Gift Cash: not through `addEarnings`, never valuation. It can only buy items a little sooner inside a rung; it never moves the valuation clock (LONG_GAME principle: "Cash can only fill a rung, never skip it").
- **Why this small:** a company that went public near the top of the LONG_GAME ladder earns up to 8,614/s, while a whole new Garage tops out at 194/s (LONG_GAME section 3). Even 1% is 86/s, half a Garage; two such companies uncapped would pay most of the first rung. The 10% cap ties the dividend to the new company: at the start (1/s) it is 0.1/s, a token, and it grows with the new company. Its upper bound acts like item Income x1.1; LONG_GAME's sensitivity table has x1.25 at 46 h against 57 h, so the effect is roughly 2-4 h less on a run **(estimate, interpolated; section 8 says what to simulate)**.
- Until the engaged clock exists (LONG_GAME PR 2), dividends are 0.

### 1.5 What an IPO does now (replaces the old reset)

Today `goPublic` (IpoServer.lua:177-243) calls `commitIpo` (TycoonCore.lua:544-588), whose save transform resets Cash, `owned` and incubator eggs (`IpoConfig.Resets`, IpoConfig.lua:53-58) and writes the new `ipo` section. The new IPO:

1. **The IPO window gets a step before Confirm:** pick the next company's sector (D-C: any enabled sector, the current one included) and, at the cap, the held company to retire.
2. **Request:** `IpoAction("GoPublic", ipoNumber, sectorKey, retireId)`. The server checks the types, that the sector is enabled, that `retireId` is a held id exactly when the cap is reached, plus every check it makes today (`ipoNumber == count + 1` already makes a repeat impossible, IpoServer.lua:179).
3. **One save, one transform (atomic):** snapshot the active company into `held` (owned list, decor, objects, building, valuation, base Income, dividend); write the new `active` (new id, the chosen sector, a name, `foundedAt`, `building = 1`, no decor, no objects); `companies.run = count + 1`; Cash = `StartingCash` + seed. Today's resets stay (Cash, `owned`, incubator eggs): they now mean "the old company's" and live on in its held record.
4. **Only if that save worked** does the game change, as today (TycoonCore.lua:565-587): the plot rebuilds as the new sector's Garage, and the Office tab and tasks switch sector.

`IpoConfig.ResetNames` (IpoConfig.lua:60-65) and the IPO window's lists change wording: "Your company goes to your Portfolio. Your new company starts in a garage with $X of funding."

**A10 run check:** if `companies.run ~= ipo.count` on load, an older version ran an IPO without knowing this section (and reset `owned`, TycoonCore.lua:552-554). The stale `active` then becomes a held entry with what it knew (sector, name, building, objects; dividend 0, its Income is unknown), and a new `active` of the same sector starts at the Garage with `run = ipo.count`. Nothing is lost that the older code had not already reset, and no seed is paid twice (only the new IPO pays one).

### 1.6 Choosing a sector (D-C)

- **First founding:** a new player's first screen is the sector picker (window `OpenPanel = "Sector"`, four cards: icon, name, one line on how it makes money, then Confirm). The Garage is built in that sector's look after the pick; onboarding (free egg, arrow) starts then. `CompanyAction("PickSector", key)` is accepted only while `active.sector` is not set; after that the sector changes only through an IPO.
- **Existing saves** (no `companies` section, every dev save) are Software, never asked.
- **Until all four sectors exist** the picker is off and every company is Software (`SectorConfig.PickerEnabled = false`, the same pattern as `TaskConfig.StudioOnly`).

## 2. The sector package

**Shared engine (built once, never names a sector):** the `companies` section, the IPO-to-new-company flow, seed and dividends; nested buildings, moving in, placement and its check, budgets; the Shop's Office tab and every purchase check; the task engine and its four action types (Answer, Choose, Timing, Targets: the content bible's "What each rung adds"); creatures, eggs, odds, `fixedHire` (D9) and poaching; daily, onboarding, HUD; the economy clock (engaged, away, caps); the sim. A test fails if a sector key appears in an engine `.lua` file.

**Per sector: two modules and some config rows.**

| What | Where | Content | Checked by tests |
|---|---|---|---|
| Identity | `Sector<Name>` (ReplicatedStorage) | `key` (saved: never renamed), name, one-line pitch, icon, UI palette, 12+ company names | key unique; names unique |
| Buildings | `Sector<Name>` + `SectorArt<Name>` | one per stage: inner size (within section 4), shell art key, hire-desk skin, starter set (fixed list and spots) | nested sizes; starter spots valid; shell budget |
| Upgrades | `Sector<Name>` | per stage: key (saved in `owned`, never renamed or reused), display name, joke, price, Income, footprint, prop art key, default spot. Software keeps today's six (TycoonCore.lua:65-72) | footprint covers the art; prices rise |
| Furniture | `Sector<Name>` + `SectorArt<Name>` | key, name, joke, stage, price, footprint, parts, lights | footprint covers the art; parts and lights counted |
| Tasks | `Sector<Name>` | rows in `TaskConfig.Rows` format (TaskConfig.lua:49): the engine's action type, texts, reward in seconds of Income, stage; caller lines (8 per stage), surprise events, board requests | only engine action types; no D9 words |
| Creatures and eggs | `Sector<Name>` | display name, job title (today's `role`, CreatureConfig.lua:56-104) and joke per shared creature key; egg display names | every key of `CreatureConfig` covered |
| Way of making money | `Sector<Name>` | one of the engine's income models plus its numbers (below) | sim parity (section 8) |
| Art | `SectorArt<Name>` (ServerScriptService) | shells, props, furniture, hire desks: the `P(...)` part format of PlotArt.lua:9-23 | the PlotVisuals checks and fingerprints |
| Shop | `ShopConfig` | furniture bundles (fixed contents) with `id = 0`; the owner runs the sync | D9; `id = 0` |
| Registration | `SectorConfig` | the list of sectors, `Enabled`, `PickerEnabled` | every listed module exists |

**Ways of making money (engine models, sector numbers).** Every model pays through `core.addEarnings`, has no random outcome (D9) and is fitted so the hours per rung match Software within 5% (section 8):
- **Software (today):** steady Income per second.
- **Fintech (proposal):** lower Income per second, plus interest on the Cash held, paid per engaged second and capped at a share of base Income, so a full bank cannot outrun the ladder.
- **Biotech (proposal):** lower Income per second, plus a fixed research payout every N engaged minutes (a trial phase on a visible timer, never a dice roll).
- **Gaming (proposal):** Income per second, plus a launch: a graded Timing task that doubles Income for a few minutes, followed by a cooldown.

## 3. Content volume

The baseline is the content bible (`docs/CONTENT_BIBLE.md` on `content-bible`): **168 names** for Software over the LONG_GAME ladder, counted by type code: upgrades 42, decor 22, hires 18, desks 18, events 12, titles 9, skins 9, board requests 8, offices 7, products 6, eggs 6, caller groups 6 (8 lines each), hats 4, tag 1. Of these, skins, hats and the tag (14) are shared by every sector, and the 5 "industry skins" for IPO 2-6 are replaced by the sectors. The bible names no tasks; LONG_GAME section 4 plans 20.

| Kind | In code today | Software target (bible) | Each new sector **(estimate)** | 3 new sectors **(estimate)** |
|---|---|---|---|---|
| Upgrades (name + prop art) | 6 (TycoonCore.lua:65-72) | 42 (30, and 12 with two levels) | 42 | 126 |
| Buildings (name + shell) | 5 rooms (PlotArt.Stages) | 7 names (5 shells with today's stages) | 5-7 | 15-21 |
| Furniture | stage decor, not cut into pieces | 22 | 22 | 66 |
| Hire desks | 1 skin per room | 18 names | 18 names, 5-7 skins | 54 names, 15-21 skins |
| Creatures (name, job, joke) | 12 (CreatureConfig.lua:53-104) | 18 (6 new) | 18 sets of texts, shared bodies | 54 |
| Eggs | 3 (CreatureConfig.lua:23-41) | 6 | 6 names | 18 |
| Tasks | 1 row (`Call`, TaskConfig.lua:49) | 20 | 20 rows: ~16 re-texted engine tasks + ~4 sector-only | 60 |
| Caller lines | none | 48 | 48 | 144 |
| Events / board requests / titles | none | 12 / 8 / 9 | 12 / 8 / 9 | 36 / 24 / 27 |
| Products (fixed bundles) | none | 5 bundles + Night Guard | 5 bundles | 15 |
| Company names | none | 12 (new) | 12 | 36 |
| **Names** | | **153 + 20 tasks + 12 companies = 185** | **about 185 + 48 lines** | **about 555 + 144 lines** |
| **Art builds** (props, furniture, shells, desk skins) | 6 props, 5 rooms | 36 props + about 22 furniture + 0-2 shells to add | about 75 | about 225 |

**What is new.** For Software the names exist (bible, still to approve) and the art is partly done: 6 props of 17-24 parts each (PlotArt.lua:806-949) and 5 rooms to cut into shells and furniture. Fintech, Biotech and Gaming need everything sector-flavored from zero: about 3 times Software's names and about 4 times its remaining art **(estimate)**. Mechanics are reused (no new task action type, no new creature body), which is what keeps this possible.

## 4. Plot space (checked in the code)

**What is there:**
- **Plots:** centers at x = -225, -135, -45, 45, 135, 225 and z = 150 (`plotCenter`, TycoonCore.lua:123-126, with `PLOT_SPACING = 90` and `MAX_PLOTS = 6` at :74 and :76). Each `Floor` is 60 x 60 (TycoonCore.lua:736), so it spans z 120-180 and leaves 30 studs between neighbors.
- **Front = +Z:** the signs stand at +24 (TycoonCore.lua:75, IpoServer.lua:21) and the player spawns at +12 facing them (TycoonCore.lua:697-700). The building pass puts its door in the front wall (z 30.2-31, x -4.5 to 4.5; docs/BUILDING_PASS_PROPOSAL.md section 3 on `building-pass`). **So the anchor is the front-center of the floor: local (0, +30), world z 180.** The Garage's roll-up door is decor on the back wall (PlotArt.lua:221-235), not the anchor.
- **VIP Lounge:** center (0, 70), 36 x 24, so x -18 to 18 and z 58-82, with its door in the +Z wall facing the plots (ShopServer.lua:35-36, 643-657). Players leaving it appear at z 88 (ShopServer.lua:839).
- **Stage 5 skyline:** behind the back wall at local z -49 to -43, world z 101-107 (PlotArt.lua:699-707).
- **Nothing else** is built in the world by a script (every `Instance.new("Part")` checked). The Baseplate's size, the SpawnLocation and any part placed by hand in Studio are **(unverified)**; docs/STUDIO_SYNC.md:37 records only the Baseplate's color.

**How big a building can get.** It grows sideways (centered) and backward from the anchor. Each side adds the building pass's wall (0.8) and roof overhang (1.5), 2.3 studs.
- **Width:** neighbors are 90 apart, so the gap between two roofs is 90 - width - 4.6. Keeping at least 6 studs to walk between plots **(estimate)** gives **width ≤ 79.4, so 78**.
- **Depth:** at width 78, plots 3 and 4 span x -84 to -6 and 6 to 84, behind the lounge (x -18 to 18). Their roof must stay at least 10 studs from the lounge door at z 82 **(estimate)**: roof back ≥ z 92, so depth ≤ 180 - 92 - 2.3 = 85.7, so **84**. Plots 1, 2, 5 and 6 could go deeper, but one rule for every plot keeps one set of sector art.
- **Height:** nothing in the code limits it; the building-pass roof underside is at 14.

**So the largest building is 78 x 84 inside (today 60 x 60, area x1.8), with no plot moved.** Proposed nested sizes **(estimate)**:

| Building | 1 Garage | 2 Seed | 3 Series A | 4 Series B | 5 IPO-ready |
|---|---|---|---|---|---|
| Inner width x depth | 60 x 60 | 64 x 66 | 68 x 72 | 74 x 78 | 78 x 84 |
| Back wall, world z | 120 | 114 | 108 | 102 | 96 |

With LONG_GAME's 7 rungs: widths 60 / 63 / 66 / 69 / 72 / 75 / 78 and depths 60 / 64 / 68 / 72 / 76 / 80 / 84.

**What this changes:**
1. **The skyline** (world z 101-107) ends up inside buildings 4 and 5, with no room left behind them before the lounge. It goes, or becomes a picture on the back wall.
2. **The solid floor grows:** today one 60 x 60 `Floor` is the only solid part (TycoonCore.lua:736; CLAUDE.md). Each bigger building adds up to three flush `FloorExtension` strips (back, left, right); `PlotVisuals.check` already lets parts named `Floor` collide (PlotVisuals.lua:590-592).
3. **The 60 x 60 assumptions go per building:** `PlotArt.Layout.floorSize` (PlotArt.lua:31), the floating check (PlotVisuals.lua:643), and the building pass's "inside 65 studs of the plot center" with roofs 25 studs apart (BUILDING_PASS_PROPOSAL section 3; it becomes 7.4).
4. **Gameplay positions don't move** (D-A): the incubators at local z -25 (EmployeeServer.lua:37-40) end up in the middle of building 5, and their reserved zones stay.

**If the owner wants a bigger last building** (for example 100 wide), `PLOT_SPACING` (TycoonCore.lua:74) must go to at least 100 + 4.6 + 6 = 110.6, so **112**. Every system takes positions from `plotCenter` (passed to IpoServer, EmployeeServer and PoachServer at TycoonCore.lua:601, 639, 650), so it is one constant. The row then spans about 670 studs, which fits a 2048-stud Baseplate **(Baseplate size unverified)**; the lounge at x 0 stays clear because the gap between plots 3 and 4 grows; walks and the onboarding arrow get longer; Max Players stays 6 (PUBLISH_RULES section 1). Going deeper than 84 also needs the plots moved toward +Z (the `150` in TycoonCore.lua:125), away from the lounge, which depends on what stands beyond z 180 **(unverified)**.

## 5. The office: what stands where, and what the server checks

Coordinates are measured from the **anchor**, the front-center of the floor (section 4): `x` to the right, `z` negative toward the back. Today's plot-center offsets convert with `z_anchor = z - 30`; the world position stays the same.

| Thing | Source | Rule |
|---|---|---|
| Floor (60 x 60, today the only solid part) | TycoonCore.lua:736 | grows with the building (section 4) |
| Spawn (0, 12) and the walking lane | TycoonCore.lua:698; PlotArt.lua:37, 66-68 | fixed, reserved |
| BuySign (0, 24), IpoSign (21, 24) | TycoonCore.lua:75; IpoServer.lua:21 | fixed, reserved |
| 5 incubators at z -25, Hatch prompt | EmployeeServer.lua:37-40, 531-544 | fixed, reserved with the space in front |
| 11 hire spots and hire desks | EmployeeServer.lua:31-35, 172-175; PlotVisuals.lua:199-203 | fixed in v1 (owner default), a skin per building and sector |
| Six upgrade props (Software) | `itemOffset` TycoonCore.lua:131-135, `spawnItem` :189-201 | movable; default spot = today's slot |
| Furniture | PlotArt stage decor, cut into pieces | movable, bought |

**Employees** do not sit: the server sets a `Home` point per hire (EmployeeServer.lua:185, 199) and the client wanders 3 studs around it (EmployeeClient.lua:984-999). Hire desks don't move in v1, so nothing changes.

**Moving in (D-A):** buying building n+1 keeps `objects` exactly as they are. Building n+1 contains building n and every reserved zone is the same, so every placed object stays valid without a check that could fail. The new area is empty except the building's **free starter set** (owner default): a fixed list in the sector data (its hire-desk skin and one furniture piece) at fixed spots in the new area, checked by the tests. If the budget is full, a starter piece goes to the inventory instead: never refused, never lost.

**Server checks.** One remote, `CompanyRemotes.CompanyAction` (a RemoteFunction made by `CompanyServer.init`): `"Place", id, x, z, r` · `"Store", id` · `"Sync"` · `"PickSector", key`. Purchases use the existing `ShopAction` (section 7). On every request:
- `data.ready` (false while loading and during the IPO save, IpoServer.lua:211-213) and `data.companies` exist.
- **Types:** `id` a string under 40 characters; `x`, `z` finite numbers, rounded to 0.5; `r` a whole number 0-7. Anything else: "Bad request".
- **Ownership:** an upgrade id must be in `data.owned`; `Plant#2` needs `decor.Plant >= 2`.
- **Bounds:** the footprint (a rectangle turned by `r`) stays inside the active building's inner box (section 4).
- **Overlap:** footprints may not overlap by more than 0.1 stud; floor marks (at most `PlotVisuals.FLAT` = 0.2 high, PlotVisuals.lua:38) may lie under anything. No footprint enters a reserved zone of `PlotVisuals.zones` (PlotVisuals.lua:504-531); the six upgrade slot zones stop being reserved.
- **Height:** at most 12 studs (PlotVisuals.lua:42), under the building-pass roof (underside 14).
- **Budgets** (section 6) are counted by the server from the art, never sent by the client.
- **Rate:** only the drop is sent; 4 per second, burst 8, 120 per minute. Spam is refused, not queued.
- **One pure function in `CompanyConfig`** does the check: the client runs it for the red/green preview, the server runs it again and decides. Footprints are data in the sector module; a test proves each covers its art's part boxes (`PlotVisuals.boxOf`, PlotVisuals.lua:65-72).

**Income:** placement never changes it (`totalIncome` reads no position, TycoonCore.lua:137-145). Buildings and furniture have no Income (as `LONG_ITEMS`, tools/economy_sim.py:1063); a stored upgrade keeps earning (owner default). Buying spends Cash only: **no new `addEarnings` call** (tools/daily_test.py:4327-4334). **No `Touched` handler:** the drag is a screen ray onto the floor plane, and since decor has `CanQuery` off (PlotVisuals.lua:105) the client picks objects by testing the tap point against footprints (tools/daily_test.py:4254-4256 still allows only the VIP door).

## 6. Part budget

- **Today:** `MAX_PARTS = 260` per room (props included) and `MAX_LIGHTS = 3` per plot (PlotVisuals.lua:39-40); rooms use 256 / 244 / 254 / 253 / 257 (docs/PLOT_VISUALS.md). No written reason for 260 (it was 220 in `1fba576`, raised per ROADMAP.md:41). Likely reason **(inferred)**: server-built parts replicate to every player, and a server has 6 plots (TycoonCore.lua:76). StreamingEnabled and real frame rates are **(unverified)**.
- **Costs (PlotArt.lua):** Desk 24 (806-832), Coffee Machine 17, Laptop 17, Server Rack 24, Whiteboard 19, Neon Logo 17: **118 for the six**. Hire desk 2 / 5 / 5 / 5 / 6 by stage; sofa 5 (164-172), plant 2 (156-161), founder's desk 11 (176-190).
- **The problem:** shell **(estimate ≤ 60)** + 11 hire desks (≤ 66) + the six upgrades (118) leaves 16 of 260 parts for furniture: about 3 pieces.
- **Proposal:** draw only the hire desks the player has (`maxEmployees`, 5 to 11, saves up to 36); `MAX_PARTS` per plot **320** (shell ≤ 60, hire desks ≤ 66, placed objects ≤ 194, enough for the six upgrades plus 8-15 furniture pieces); 3 lights per plot over everything; a budget bar in edit mode. A bigger building does not need more parts: a wall is one Part whatever its length. Server total 6 x 320 = 1,920 (today at most 1,542), 2,304 with the building pass's 64.
- **Unresolved (owner default):** no budget change until the phone test with 6 full plots at the largest building (gate G-S, section 9). If it fails, stay at 260 and thin the hire desks to 2 parts.

## 7. Phone and PC, the Shop, the Portfolio

- **Edit mode is a window** (`OpenPanel = "Office"`): every other window closes, the task tray hides (TaskClient.lua:28) and the thumbstick and jump button hide (`GuiService.TouchControlsEnabled`, ShopClient.lua:725). Entry: an "Arrange your office" card at the top of SHOP > Office; no new HUD slot (slots 0-4 fill the landscape row to x 370, ShopClient.lua:101-104).
- **Camera:** a scripted top-down view of the whole building. At 78 x 84 studs (section 4) that is about 3.5 px per stud on a 667 x 339 GUI **(estimate)**, so a Laptop (3 x 2 studs) is about 10 x 7 px: objects are also selected from the inventory strip, and two-finger pinch zooms.
- **Touch:** tap or pick from the strip to select, then drag anywhere on the screen to move by the finger's offset; snap 0.5 stud; red when the shared check says no; lifting the finger sends one `"Place"`. Buttons Rotate (45°), Store, Done, 56 x 56 px **(estimate)**. **PC:** mouse drag, R rotates, Delete stores, Esc or E exits.
- **Layout (estimate, GUI px):** landscape 667 x 339: strip x 10-591, y 257-329; buttons x 601-657, y 82-266; budget bar y 233-251. Portrait 320 x 532: strip x 98-310, y 450-522; buttons y 386-442; bar y 362-380. Checked in Studio with Test > Device and top bars of 0, 36 and 58 px, like `TRAY_TESTS`.
- **Shop: no new tabs** (tabs share the window width, ShopClient.lua:133-150, 204). SHOP > Office gets three sections: **Buildings** (the next one: Locked "Reach Seed" or Buy; bought ones listed), **Upgrades** (the sector's six), **Furniture**. Requests `"Buildings"`, `"BuyBuilding", n`, `"Objects"`, `"BuyObject", n` on `ShopAction` (ShopServer.lua:701-715, 802-805), with the same checks as `checkUpgradePurchase` (TycoonCore.lua:243-270): ready, a number, not owned, stage reached (`IpoConfig.stageIndex`, IpoConfig.lua:151), building n-1 owned, Cash, 0.4 s rate.
- **Draft prices:** a building costs 50% of its stage's threshold (Seed 900, Series A 3,150, Series B 11,700, IPO-ready 40,500 at IPO 0; IpoConfig.lua:19-22, x2.5 per IPO :27); furniture 10-25% of its stage's threshold. Fit with tools/economy_sim.py before the shop PR.
- **D9:** buildings and furniture are sold for Cash only in v1; anything sold for Robux later has fixed, listed contents. Sector text may not say odds, chance, luck or random (the TaskConfig word test, tools/daily_test.py:4344).
- **Sector picker and Portfolio:** the picker is a 2 x 2 grid (portrait) or a row of 4 (landscape); the Portfolio is a scrolling list of cards in the IPO window.

## 8. Economy risks and anti-exploit

**What changes for balance:**
- **IPO pace stays the same.** An IPO still needs the run's valuation, earned Cash only (IpoServer.lua:123-135, 192-195), and Shares and the multiplier still come from it (IpoConfig.lua:162-172). Companies add exactly two new Cash sources, both gifts that never touch the valuation: the **seed** (once per IPO, capped, 1.3) and **dividends** (capped at 10% of base Income, engaged seconds only, 1.4). They can only shorten the item-buying part of a rung.
- **Four sectors are four economies.** A sector that is faster (or kinder to a casual or idle player) becomes the only choice, and the others become dead content. Every sector must reach each rung in the same engaged hours within 5%, for every LONG_GAME player profile.
- **Income models are the riskiest part.** Fintech interest grows with Cash held (it rewards hoarding and idling), Biotech payouts are lumpy (long waits), Gaming launches multiply Income (passes and the IPO multiplier stack on top). Each is capped as a share of base Income, pays only while engaged, and has no random outcome (D9).
- **Prices scale with the player's IPO count**, never per sector (`StageScale`, LONG_GAME section 5), so changing sector restarts nothing.

**Anti-exploit:**
- **Company hopping:** the only way to found a company is an IPO (IPO-ready valuation, the 60 s cooldown at IpoConfig.lua:45, 50+ h by LONG_GAME's design). There is no "start over" or "refound" action; a retired company pays nothing.
- **Duplicate funding:** the seed is computed and written inside the IPO's one save transform (1.5); `ipoNumber == count + 1` refuses a repeat (IpoServer.lua:179); a held company's Cash is frozen (no transfer, no withdrawal, no second IPO); the A10 run check never pays a seed (1.5).
- **Dividend farming:** paid only per engaged second (a server-graded task, LONG_GAME section 2), so macros and idling earn nothing; capped by the active company's own Income; base Income only (no passes), like away pay.
- **Alt accounts:** companies cannot be given, traded or poached; poaching stays per employee with LONG_GAME's R1-R3.
- **Rollback:** older code keeps `companies` frozen; its IPO pays no seed, and the run check repairs the record (1.5).

**Simulate before any build (tools/economy_sim.py; the modes today are `--long`, `--active`, `--ipo`, `--daily`, :1682-1688). A new `--companies` mode adds the seed, dividends and per-sector ladders and income models:**

| Sim | Question | Pass |
|---|---|---|
| S1 seed | `--long` with seed 0, 10% and the 25% cap: hours to IPO 1 and loop 2 | each loop at most 5% faster |
| S2 dividends | 0, 1 and 4 held companies, cap 10%: hours per loop for loops 2-10 | at most 10% faster at IPO 10 |
| S3 sector parity | each income model fitted to Software's hours per rung, for dedicated, regular and casual players (`LONG_PLAYERS`, :1183) | every rung within ±5% |
| S4 bots | the macro and task-bot rows of LONG_GAME section 2, per sector | no sector faster for a bot |
| S5 hopping | always picking the fastest sector against one fixed sector, 10 IPOs | under 3% apart |

## 9. Build plan: engine, sector format, Software slice, gate, three sectors

Every PR: claim its scripts in CONTRIBUTING.md first, `python3 tools/daily_test.py` passes in the fake Roblox, a Studio playtest (F5) with no red errors, publish with **Shut down all servers**. Create new modules in Studio **before** pasting a script that requires them (a `WaitForChild` without a timeout hangs, PUBLISH_RULES 2b). PR 1-8 do not need LONG_GAME; PR 9-14 need its economy core (LONG_GAME PR 2: the engaged clock, `addEarnings(kind)`), because dividends and the sector income models are measured on it.

| PR | Content | Tests (fake Roblox) | By hand in Studio |
|---|---|---|---|
| **Engine** | | | |
| 1 | `companies` section: `CompanyServer`, `CompanyConfig` (the shared check), `SectorConfig` (Software only, `PickerEnabled = false`); active record, run check, anchor coordinates, `spawnItem` reads the layout; `"Place"`/`"Store"`/`"Sync"`; Debug rows "Company: move Desk", "Company: reset layout". No UI | save round trip; no section = today's look; `v = 2` and unknown sector kept unchanged; run mismatch; types, NaN, bounds, overlap, zones, rate, ownership; `addEarnings` count unchanged; KNOWN_SECTIONS list | Create `CompanyConfig`, `SectorConfig` (ReplicatedStorage) and `CompanyServer` (ServerScriptService), then paste TycoonCore and ShopServer. F5, press the Debug rows, rejoin: the Desk stayed moved |
| 2 | Nested buildings: sizes from section 4, `FloorExtension` strips, move-in, starter set, `"Buildings"`/`"BuyBuilding"`, the Buildings section in SHOP > Office; Software shells cut from PlotArt rooms 2-5 for now | nested sizes; starter spots valid; objects unchanged after a move-in; locked below the stage; Cash; rate; shell budgets; stage 1 fingerprints | Paste PlotArt, PlotVisuals, CompanyConfig, CompanyServer, TycoonCore, ShopServer, then ShopClient. Debug: grant valuation, buy Seed; the Desk has not moved and you can walk on the new floor |
| 3 | `CompanyClient` edit mode: drag, rotate, store, done, camera, pinch, inventory strip, budget bar | layout rectangles at 320x568 and 667x375 with top bars 0 / 36 / 58; the client sends only id, x, z, r | Create the LocalScript `CompanyClient`. Test > Device at both sizes: drag, rotate, store with touch and mouse |
| 4 | IPO to a new company: snapshot into `held`, seed, retire at the cap, Portfolio tab, `"GoPublic"` with a sector (Software only), new reset wording, dividends coded at 0 | one atomic transform; seed cap; no seed on a repeated or old `ipoNumber`; retire; held records frozen; run check after an old-code IPO; `addEarnings` count unchanged | Paste IpoConfig, IpoServer, CompanyServer, TycoonCore, then IpoClient. Debug: grant valuation, IPO twice; the Portfolio shows 2 cards; rejoin |
| **Sector format** | | | |
| 5 | `SectorSoftware` and `SectorArtSoftware`: today's content moved in, upgrade keys unchanged; the engine reads only through `SectorConfig`; task rows and creature texts per sector; income-model hook (Software = today) | no sector key in engine files; fingerprints unchanged (nothing looks different); every creature key covered | Create both modules, paste the changed scripts. F5: everything looks and earns as before |
| 6 | Sector picker for the first founding, `"PickSector"`, behind `PickerEnabled` (Studio only); a second sector exists only as a test fixture | picker only while no sector is set; refuses an unknown or disabled key; existing saves never asked | Paste CompanyServer, CompanyClient. Debug "Reset company", turn `PickerEnabled` on in Studio: pick Software on a phone size |
| **Software vertical slice** | | | |
| 7 | Software buildings 2-5 at the section 4 sizes, hire-desk skins, starter sets; the skyline removed or moved | shell budgets and checks per building; story checks rewritten | Paste SectorArtSoftware, SectorSoftware. Debug: walk through buildings 1-5 |
| 8 | Software furniture: PlotArt decor and bible decor as pieces, `"Objects"`/`"BuyObject"`, light cap, the Furniture section | every footprint covers its art; budget and light refusals; no D9 words | Paste SectorSoftware, SectorArtSoftware, ShopServer, ShopClient. Buy, place, hit the budget, rejoin |
| **G-S** | **Go / no-go.** (a) Phone: 6 accounts, every plot at building 5 with a full budget, on a real low-end phone (Test > Device does not measure speed): at least 30 fps **(estimate threshold)**; decide 260 or 320 parts. (b) Every building at its maximum stays in budget. (c) Playtest, 3+ players: found a company, buy 2 buildings, arrange on a phone without help, go public into a new company, rejoin. (d) The section 8 sims pass. **No-go: fix, then repeat G-S before any other sector.** | | |
| **Three sectors** (each: data, tasks and income model first, then the art) | | | |
| 9-10 | Fintech: `SectorFintech` (texts, tasks, the interest model), then `SectorArtFintech` | sim parity ±5%; footprints; D9 words; `id = 0` bundles | Create the modules; Debug: found a Fintech company; walk buildings 1-5 |
| 11-12 | Biotech: the same, with the research-payout model | same | same |
| 13-14 | Gaming: the same, with the launch model | same | same |
| 15 | Launch: `PickerEnabled` on for live servers, all four sectors; PUBLISH_RULES gets a "2d" note for `companies` | all four in the picker; the full suite | Publish with Shut down all servers; join on a phone and pick each sector once |

## 10. Impact on other docs and branches

**docs/LONG_GAME_PROPOSAL.md (must change; line numbers on `2d91efd`):**

| Section | What changes |
|---|---|
| Header (line 3) and 1 Pacing (line 18) | "50+ h to the first IPO, every later loop 50+ h" stays: a loop is now one company. `StageScale` (+5% per loop) follows the player's IPO count, never the sector, so a new sector never restarts the prices. The sensitivity table needs a seed + dividend row |
| 2 Clock rules (line 24) | Seed and dividends join "Cash packs and daily Cash never count": gifts, never valuation; dividends only per engaged second |
| 3 Ladder (lines 36-60) | The "Offices" column is these buildings (0 Income, tools/economy_sim.py:1063). 7 rungs, but Series C+D has two offices (Tech Campus, Glass Tower): one building per rung, or 8 buildings. The 97-item ladder becomes per-sector data, each refitted to the same hours. Its 18 desks fight the 11 hire spots (EmployeeServer.lua:31-35) and the part budget |
| 4 Content (lines 62-82) | "Loops 2+ replay the ladder (an industry skin per IPO)" (line 82) is replaced by the sector pick. The content table is per sector (x4: section 3 here); "decor 20" is one sector's furniture |
| 5 Shares and shop (lines 84-88) | The Shares formula is unchanged (computed on the run's valuation). New `ResetNames` wording (1.5). Day 7's decor piece must exist in every sector, or be a shared piece |
| 6 Money and passes (lines 90-95) | The Shareholder pass's Boardroom skin: one per sector, or one neutral skin. The `addEarnings` list gains: seed and dividends make **no** call; the sector income models must pay inside the existing income-loop call (TycoonCore.lua:866) or TaskServer's, or each new call site is reviewed in tools/daily_test.py:4327-4334 |
| 7 Exploits (lines 97-108) | R1-R3 stand if employees follow the player (open question 1). Companies cannot be traded or poached |
| 8 PR plan (lines 110-122) | PR 4 "Office framework, Seed, Daily decor piece" is replaced by this doc's PR 1-8; PR 7 "industry skin 1" by PR 9-14. Load order gains `CompanyServer` before `TaskServer` |
| 9 Decisions (line 128) | All stand. The 50+ h first-IPO gate is unchanged for the first company; the picker puts one choice before the first minute of play (risk, section 8) |

**Other docs and branches:**

| Doc / branch | What changes |
|---|---|
| `design-tutorial` (docs/TUTORIAL_PROPOSAL.md) | Section 2: step 1 (SHOP > Office, buy the Desk) comes after the picker, and the upgrade cards sit under "Upgrades" (find `Office1` by name and scroll); step 9's resets and keeps text (it cites IpoClient lines 519 and 526-531) becomes "your company goes to the Portfolio, the new one starts in a garage with funding"; a new "Arrange your office" step after building 2. The picker is its own screen, not a card: TutorialClient waits while `OpenPanel = "Sector"`. **Small change** |
| `building-pass` (docs/BUILDING_PASS_PROPOSAL.md) | D-2 and section 3 "same footprint for all five (62 x 62)", "inside 65 studs", roofs 25 apart: per-building sizes from section 4 here, roofs 7.4 apart at the largest. E2's `sync(..., stageOf(data))` becomes the active company's building, keyed by sector and building. The 64-part budget holds (a wall is one Part at any length), but there are 4 sets of shells. **Must change** |
| `visuals-garage` (PlotArt, PlotVisuals, docs/PLOT_VISUALS.md, CLAUDE.md "Plot visuals") | "The plot stays 60 x 60" (PLOT_VISUALS.md:14) becomes nested buildings; the skyline rule (PLOT_VISUALS.md:37) goes for buildings 4-5; CLAUDE.md's "the six upgrade props ... identical in every room" and "the real Floor is the only solid" become per-sector, movable props and Floor + `FloorExtension`; `newPlot`/`setStage` (PlotVisuals.lua:235-269) become per building and sector; `buildProp` takes a position and a rotation; PlotArt becomes Software's art (stage 1 fingerprint stays). **Must change** (base of this work) |
| `content-bible` (docs/CONTENT_BIBLE.md) | Rungs 1-6 become the Software package as written. The 5 industry skins for IPO 2-6 (Snack Space ... Moon Zoo) are dropped: sectors replace them (this answers its decision 9). "Office" names are building names. The locked names (its decision 1) stay Software keys. "The first 5 hours" starts with the sector pick at minute 0. Three more bibles are needed (section 3). **Must change** |
| CLAUDE.md, README.md, ROADMAP.md, docs/PUBLISH_RULES.md | Save format block (`companies`), feature module list and order, configs, remotes; README file list; a PUBLISH_RULES "2d" note (PR 1 and PR 15) |
| Onboarding | The arrow points at incubators and the BuySign (OnboardingServer.lua:103-121), which don't move; it starts after the pick |

## 11. Open questions for the owner (most important first, with my recommendation)

1. **When you buy a new building, do owned objects move in by themselves, or does the player re-place them?** Recommend: by themselves, copying the current layout where it is valid in the new shell and using the default spot otherwise. The player can rearrange.
2. **Does an IPO take the buildings away (rebuy each run) or keep them?** Recommend: take them away and keep the layouts (section 7).
3. **Are hire desks placeable?** Recommend: not in v1 (fixed grid, skin per building); PR 5 later.
4. **Do furniture items affect income, and does a stored upgrade still earn?** Recommend: furniture 0 Income; a stored upgrade keeps earning, so nobody loses income by tapping the wrong button on a phone.
5. **Is there a free starter set in each new building?** Recommend: yes, its hire-desk skin plus one furniture piece of that stage, free and fixed (no random).
6. **Can the player switch back to an older building they own?** Recommend: yes, "Move in" on any owned building card.
7. **Raise the part budget to 320 per plot** (after a phone test), or stay at 260 with thinner hire desks?
8. **Rotation: 45° steps, or free?** Recommend 45° (easy on touch, simple to check and save).

## What I did not verify

- No `luau` on this machine: I built no room. Shell-only part counts, the 60-part shell cap and every footprint are **not measured**.
- Every UI size in section 7 except the ones cited from code; Roblox's top-bar height; the camera scale.
- Why `MAX_PARTS` is 260 (no written reason); phone frame rate with 1,920 parts; the place's StreamingEnabled setting.
- Whether `TouchControlsEnabled = false` still allows the default touch camera (moot with the scripted camera, but not tested).
- The 4 MB DataStore key limit (Roblox's docs, not checked here).
- The building-pass and design-tutorial details come from their branch docs (`git show`), not from running their code.
