# Companies, sectors and the Pokedex (proposal, design only)

Design only (2026-10-04, branch `design-customize`, revised from `47f0fe8`). No script, config or test changed. For the owner and the Claude sessions that will build it. Line numbers are for `47f0fe8`, whose `.lua`/`.py` files equal `visuals-garage` `7f5c141` (`main` has no PlotArt, PlotVisuals or Office tab yet). **(unverified)** = not checked in code; **(estimate)** = not measured; **(owner default)** = the owner may still veto; **(placeholder)** = a number the sims must size.

**Fixed by the owner:** **D-A** a new building moves every owned object in by itself, same coordinates; each building contains the previous footprint, positions measured from a fixed anchor on the door side. **D-B** an IPO founds a new company, seeded with a percentage of the old company's money (money only, never items). **D-C** every founding starts with choosing a sector. **D-D** a sector is a full package (tasks, objects, names, building theme, office look, way of making money); one engine; Software/SaaS (today), Fintech, Biotech, Gaming launch together; order: engine, Software end to end, then the other three. **D-E** free placement (drag, rotate), phone and PC. **P-1** the save holds one Pokedex entry per sector (not started / in progress / completed, a stamp tier, a replay count), not a list of companies. **P-2** an IPO completes the active company and stamps its sector entry; the old company is a stamped card, never a building (no held buildings, no 1 + 4 cap, no Portfolio of buildings); the player then picks the next sector. **P-3** completing all four sectors is the main goal (a Hall of Fame entry); the game continues, replays earn Gold and Platinum; a leaderboard ranks players. **P-4** old companies earn nothing; each stamp gives a small, capped, permanent collection bonus. **P-5** the seed stays, funding only; its numbers stay open until the sims pass. **P-6** see the defaults below.

**Owner defaults:** employees follow the player into the new company; creatures keep their bodies with a new name and job per sector; 5 buildings per sector, one per funding stage; working building size 78 x 84, re-checked in section 5 (result: 78 x 82); hire desks fixed in v1; furniture earns nothing; each new building has a free, fixed starter set (never random, D9); 45° rotation steps; the part budget stays open until a phone test with 6 full plots.

**New names** (none exists: `grep` over every `.lua`/`.py`): `CompanyServer` (ServerScriptService, owns the `pokedex` section), `CompanyConfig`, `SectorConfig`, one `Sector<Name>` per sector (ReplicatedStorage), one `SectorArt<Name>` per sector (ServerScriptService), `CompanyClient` (StarterPlayerScripts), `CompanyRemotes.CompanyAction`, `BoardServer` (ServerScriptService, the cross-server board, no save section), save section `pokedex`, OrderedDataStores `Collection_v1` and `HallOfFame_v1`. They replace the previous revision's `companies` section.

## 1. Companies and sectors

**1.1 A company** is one sector plus one run of the ladder: its building, placed objects, furniture, upgrades and Cash. **The player** keeps what is prestige or account-wide: IPO count and multiplier, Shares, perks, `lifetime`/`best`, passes, boosts, shields, daily streak, onboarding, task stats and employees (today's rule, IpoConfig.lua:8, 51; open question 1). Only the **active** company is played and built on the plot. Held companies are not built (part budget): a **Portfolio** tab in the IPO window (beside "IPO" and "Shares Shop", IpoClient.lua:879-943) shows a card each: name, sector, building, IPO number, valuation at the IPO, dividend.

**1.2 The `pokedex` save section (new top-level section, rule A10).** The active company's live state stays where it is: `cash`, `owned`, `team`, `ipo.valuation` (TycoonCore.lua:421-433), so older code keeps playing it. The section holds what older code cannot know:

```lua
pokedex = {                  -- CompanyServer.serialize (optional: older saves have none)
  v = 1,                     -- format version
  run = number,              -- ipo.count the active company belongs to (A10 run check)
  active = {                 -- the company being played: always exactly one
    sector = "Software",     -- SectorConfig key: saved, never renamed or reused
    picked = boolean,        -- false = the picker is open (new player, run check); PickSector allowed only then
    name = string,           -- from the sector's fixed name list: no free text, no filtering
    foundedAt = os.time(),
    engaged = number,        -- engaged seconds in this company (stamp timing; 0 until LONG_GAME PR 2)
    building = number,       -- buildings bought, 1 = Garage (D-A: the biggest is used)
    decor = { [objectKey] = n },                                   -- furniture owned (upgrades stay in `owned`)
    objects = { { id = "Desk", x = -23, z = -40, r = 0 }, ... },  -- the layout, anchor coordinates (section 4)
  },
  sectors = {                -- the Pokedex: one entry per sector key; no entry = not started
    [sectorKey] = {
      state = "progress" or "done",  -- "done" never goes back, a replay keeps it
      stamp = 0 to 3,        -- best stamp: 0 none, 1 Bronze, 2 Gold, 3 Platinum (never goes down)
      replays = number,      -- completions after the first
      firstAt = os.time(),   -- first completion (0 = none)
      bestEngaged = number,  -- fastest completion in engaged seconds (0 = unknown)
      card = { name, ipoNumber, at, engaged, ratio, building, owned = {...}, decor, objects }, -- latest completion, frozen
    },
  },
  hallAt = number,           -- os.time() all four were first completed (Hall of Fame); 0 = not yet
}
```

- **Fields:** an object `id` is an upgrade name or `<objectKey>#<n>`; `x`, `z` studs from the anchor, rounded to 0.5; `r` 0-7; no `y`; at most 40 per company. An upgrade without an entry stands at its default spot. `ratio` = valuation at the IPO / IPO-ready valuation. Only the active sector may be `"progress"`. Size: active + 4 cards about 11 KB **(estimate)**.
- **Versioning:** `v` rises only when a field changes meaning. A save with a higher `v` is written back unchanged, the session plays the active sector's look if known (Software if not), and `GoPublic`, `Place`, `BuyBuilding` and `PickSector` are refused with a message, so an older server never rewrites a newer format. An unknown sector key in `sectors` is kept and written back; while one exists, `BoardServer` writes nothing (section 1.6).
- **Bad values** (type, NaN, infinite, negative, out of range, unknown or duplicate id) are skipped with a warning; `stamp` is clamped to 0-3; `"done"` with stamp 0 becomes 1; a `"progress"` entry that is not the active sector becomes `"done"` if it has a stamp, else is dropped.
- **Wiring:** `KNOWN_SECTIONS` (TycoonCore.lua:84), `buildPayload` (:421-433), save gate (:481); tools/daily_test.py:4268-4270 asserts the section list and changes in the same PR. `CompanyServer.setupPlayer` runs after `IpoServer` (:793, it needs `ipo.count`) and `EmployeeServer` (:795), before `TaskServer` (:798, tasks read the sector) and `DailyServer` (:799, last).
- **Publish:** new section, so **Shut down all servers** (PUBLISH_RULES section 3) and a "2d" note there. Rollback floor stays `V_launch`: code from M4 keeps a section it doesn't know (TycoonCore.lua:773-777, 434-438), so `pokedex` stays frozen and works again going forward.
- **Existing saves** (no `pokedex`; only dev saves exist, LONG_GAME section 5): built on first load, written by the next save. `active` = Software, `picked = true` (never asked), `building` = today's funding stage (they keep the room they see, TycoonCore.lua:810), the layout empty (default spots). `sectors.Software = "progress"`, stamp 0. **IPOs done before the Pokedex stay prestige** (multiplier, Shares, perks, `StageScale`) and **give no stamp**: they were 10-15 minute runs (IpoConfig.lua:25-26), not sector completions.
- **A10 run check:** `run ~= ipo.count` on load means an older version ran an IPO; it reset Cash, `owned` and eggs (TycoonCore.lua:549-559) and paid no seed. That IPO was valuation-gated in every version (IpoServer.lua:192-195), so the active sector gets what an IPO gives here: `"done"`, Bronze if it had none, a card from what the section knew (`engaged` 0: no Gold or Platinum). The new active company is in the same sector with `picked = false` (the picker opens on join), building 1, no decor or objects; no seed; `run = ipo.count`. Several missed IPOs count as one completion.

**1.3 Cap and cost.** **At most 1 active + 4 held (owner default proposal).** At the cap the IPO window asks which held company to retire (oldest preselected); it moves to `archive` (a name card: no building, no dividend). Why 4: save size, one phone screen of cards, and the dividend is capped anyway. **Founding costs nothing extra:** the price is the IPO (the new company starts at the Garage, D-B); multiplier and Shares stay as today. **Seed (owner default proposal): 10% of the old company's Cash at the IPO, capped at 25% of the new company's first-rung prices** (today's six upgrades cost $7,025, TycoonCore.lua:65-72: cap $1,756; LONG_GAME's Garage items about $131K: cap about $33K **(estimate)**). A gift: never `addEarnings`, never valuation, paid once inside the IPO save.

**1.4 Dividend from held companies (owner default).** Each pays **1% of its base Income at the IPO** (no passes, no multiplier) to the active company, **only per engaged second** (LONG_GAME section 2: a graded task in the last 180 s); never offline or away. **All together capped at 10% of the active company's base Income.** Gift Cash, never valuation: it buys items sooner but never moves the valuation clock ("Cash can only fill a rung, never skip it"). **Why so small:** a company at LONG_GAME's top rung earns up to 8,614/s, a whole new Garage tops out at 194/s (LONG_GAME section 3): 1% is already 86/s. The cap ties it to the new company (0.1/s at the start). Its upper bound acts like Income x1.1; LONG_GAME's table has x1.25 at 46 h against 57 h, so roughly 2-4 h less per run **(estimate; sims S1-S2)**. Dividends are 0 until LONG_GAME PR 2 (the engaged clock).

**1.5 The IPO now (replaces the old reset).** Today `goPublic` (IpoServer.lua:177-243) calls `commitIpo` (TycoonCore.lua:544-588), whose save transform resets Cash, `owned` and incubator eggs (IpoConfig.lua:53-58). New:
1. The IPO window adds a step before Confirm: the next sector (any enabled one, the same included) and, at the cap, the company to retire.
2. `IpoAction("GoPublic", ipoNumber, sectorKey, retireId)`: types, sector enabled, `retireId` a held id exactly at the cap, plus today's checks (`ipoNumber == count + 1` blocks repeats, IpoServer.lua:179).
3. **One transform, one save:** the active company becomes a `held` record (owned, decor, objects, building, valuation, base Income, dividend); a new `active` (new id, sector, name, `building = 1`); `run = count + 1`; Cash = `StartingCash` + seed. Today's resets stay: they are the old company's, kept in its record.
4. Only after that save works does the game change (as TycoonCore.lua:565-587): the plot becomes the new sector's Garage. `ResetNames` (IpoConfig.lua:60-65) wording: "Your company goes to your Portfolio. Your new one starts in a garage with $X of funding."

**A10 run check:** `companies.run ~= ipo.count` on load means an older version ran an IPO (and reset `owned`, TycoonCore.lua:552-554). The stale `active` becomes a held record with what it knew (dividend 0), and a new `active` of the same sector starts at the Garage. Nothing is lost that the old code had not reset; no seed is paid.

**1.6 Picking a sector.** A new player's first screen is the picker (`OpenPanel = "Sector"`, four cards: icon, name, how it makes money). The Garage is built in that sector's look afterwards; onboarding (free egg, arrow) starts then. `CompanyAction("PickSector", key)` only while `active.sector` is unset; later only through an IPO. Saves without `companies` (all dev saves) are Software, never asked. Until all four sectors exist, `SectorConfig.PickerEnabled = false` (like `TaskConfig.StudioOnly`).

## 2. The sector package

**Shared engine (never names a sector; a test fails on a sector key in engine code):** `companies`, IPO-to-new-company, seed, dividends; nested buildings, move-in, placement check, budgets; SHOP > Office and purchase checks; the task engine and its four action types (Answer, Choose, Timing, Targets); creatures, eggs, odds, `fixedHire` (D9), poaching; daily, onboarding, HUD; the economy clock; the sim.

**Per sector:**

| What | Module | Content | Tests |
|---|---|---|---|
| Identity | `Sector<Name>` | `key` (saved, never renamed), name, pitch, icon, UI palette, 12+ company names | unique keys and names |
| Buildings | both | per stage: inner size (section 4), shell, hire-desk skin, starter set (fixed list and spots) | nested; spots valid; budget |
| Upgrades | `Sector<Name>` | per stage: key (saved in `owned`, never reused), name, joke, price, Income, footprint, default spot. Software keeps today's six (TycoonCore.lua:65-72) | footprint covers art |
| Furniture | both | key, name, joke, stage, price, footprint, parts, lights | footprint, parts, lights |
| Tasks | `Sector<Name>` | `TaskConfig.Rows` format (TaskConfig.lua:49): engine action type, texts, reward; caller lines, events, board requests | engine types only; no D9 words |
| Creatures, eggs | `Sector<Name>` | per shared creature key: name, job (today's `role`, CreatureConfig.lua:56-104), joke; egg names | every key covered |
| Making money | `Sector<Name>` | one engine income model and its numbers | sim parity (section 8) |
| Art | `SectorArt<Name>` | shells, props, furniture, desks in PlotArt's `P(...)` format (PlotArt.lua:9-23) | PlotVisuals checks, fingerprints |
| Shop, registration | `ShopConfig`, `SectorConfig` | bundles with fixed contents, `id = 0`; the sector list, `Enabled`, `PickerEnabled` | D9; modules exist |

**Income models** (deterministic, D9; capped as a share of base Income; engaged time only; fitted to Software's hours per rung ±5%): **Software** steady Income per second (today). **Fintech** lower Income plus interest on Cash held. **Biotech** lower Income plus a fixed research payout every N engaged minutes (a visible timer, never a roll). **Gaming** Income plus a launch: a graded Timing task that doubles Income for a few minutes, then a cooldown.

## 3. Content volume

Baseline: docs/CONTENT_BIBLE.md (`content-bible`), **168 names** for Software: upgrades 42, decor 22, hires 18, desks 18, events 12, titles 9, skins 9, board requests 8, offices 7, products 6, eggs 6, caller groups 6 (8 lines each), hats 4, tag 1. Skins, hats and the tag (14) are shared; its 5 "industry skins" are replaced by sectors. It names no tasks; LONG_GAME section 4 plans 20.

| Kind | In code today | Software (bible) | Per new sector **(est.)** | 3 new sectors **(est.)** |
|---|---|---|---|---|
| Upgrades (name + prop) | 6 | 42 | 42 | 126 |
| Buildings (name + shell) | 5 rooms | 7 names | 5-7 | 15-21 |
| Furniture | stage decor, not pieces | 22 | 22 | 66 |
| Hire desks | 1 skin per room | 18 names | 18 names, 5-7 skins | 54, 15-21 |
| Creature texts | 12 (CreatureConfig.lua:53-104) | 18 | 18 (shared bodies) | 54 |
| Eggs | 3 (CreatureConfig.lua:23-41) | 6 | 6 | 18 |
| Tasks | 1 (`Call`, TaskConfig.lua:49) | 20 | 20 (~16 re-texted, ~4 own) | 60 |
| Caller lines / events / board / titles | none | 48 / 12 / 8 / 9 | same | 144 / 36 / 24 / 27 |
| Bundles / company names | none | 5 / 12 | 5 / 12 | 15 / 36 |
| **Names** | | **153 + 20 tasks + 12 = 185** | **~185 + 48 lines** | **~555 + 144 lines** |
| **Art builds** | 6 props, 5 rooms | +36 props, ~22 furniture, 0-2 shells | ~75 | ~225 |

**New:** Software's names exist (to approve) and part of its art (6 props of 17-24 parts, PlotArt.lua:806-949; 5 rooms to cut). The other three need everything from zero: about 3x Software's names and 4x its remaining art **(estimate)**. Mechanics are reused (no new action type, no new creature body).

## 4. Plot space (checked in the code)

- **Plots:** centers x = -225, -135, -45, 45, 135, 225, z = 150 (`plotCenter`, TycoonCore.lua:123-126; `PLOT_SPACING = 90`, `MAX_PLOTS = 6`, :74, :76). `Floor` 60 x 60 (:736): z 120-180, 30 studs between neighbors.
- **Front = +Z:** signs at +24 (TycoonCore.lua:75, IpoServer.lua:21), spawn at +12 facing them (TycoonCore.lua:697-700), the building-pass door in the front wall (x -4.5 to 4.5; BUILDING_PASS_PROPOSAL section 3). **Anchor = front-center of the floor: local (0, +30), world z 180.** The Garage's roll-up door is back-wall decor (PlotArt.lua:221-235).
- **VIP Lounge:** x -18 to 18, z 58-82, door in its +Z wall facing the plots (ShopServer.lua:35-36, 643-657); leaving puts you at z 88 (:839).
- **Skyline** (stage 5): world z 101-107 (PlotArt.lua:699-707).
- No other script builds in the world (every `Instance.new("Part")` checked). Baseplate size, SpawnLocation and hand-placed parts **(unverified)**; docs/STUDIO_SYNC.md:37 has only the Baseplate's color.

**Limits** (growing sideways, centered, and backward from the anchor; the building pass adds 2.3 per side: wall 0.8, overhang 1.5):
- **Width:** roof gap = 90 - width - 4.6; with a 6-stud walking gap **(estimate)**, **width ≤ 79.4 → 78**.
- **Depth:** at width 78, plots 3 and 4 reach x -6 / 6, behind the lounge. Keeping the roof 10 studs from the lounge door (z 82) **(estimate)**: depth ≤ 180 - 92 - 2.3 = 85.7 → **84**. One rule for all plots (one set of art).

**Largest building: 78 x 84 inside (area x1.8), no plot moved.** Nested sizes **(estimate)**: Garage 60 x 60, Seed 64 x 66, Series A 68 x 72, Series B 74 x 78, IPO-ready 78 x 84 (back walls at world z 120 / 114 / 108 / 102 / 96). With 7 rungs: widths 60-78 in steps of 3, depths 60-84 in steps of 4.

**Changes:** (1) the skyline sits inside buildings 4-5 with no room behind: it goes, or becomes a back-wall picture. (2) The solid floor grows: up to three flush `FloorExtension` strips per building (CLAUDE.md's "the real Floor is the only solid" changes; `PlotVisuals.check` already lets `Floor` parts collide, PlotVisuals.lua:590-592). (3) 60 x 60 assumptions go per building: `PlotArt.Layout.floorSize` (PlotArt.lua:31), the floating check (PlotVisuals.lua:643), the building pass's "65 studs" and "25 apart" (now 7.4). (4) Gameplay positions don't move: incubators (EmployeeServer.lua:37-40) end up mid-building.

**Bigger than 78 wide** needs `PLOT_SPACING` ≥ width + 10.6 (100 wide → **112**). One constant: every system takes `plotCenter` (TycoonCore.lua:601, 639, 650). The row becomes about 670 studs (fits a 2048 Baseplate, **size unverified**), walks and the onboarding arrow get longer, Max Players stays 6. Deeper than 84 also means moving the plots toward +Z (the `150`, TycoonCore.lua:125), depending on what stands past z 180 **(unverified)**.

## 5. The office: what stands where, what the server checks

Coordinates from the anchor: `z_anchor = z_center - 30` (same world spot).

| Thing | Source | Rule |
|---|---|---|
| Floor, extensions (only solids) | TycoonCore.lua:736 | grow per building |
| Spawn, lane; BuySign, IpoSign | TycoonCore.lua:698, 75; IpoServer.lua:21; PlotArt.lua:37, 66-68 | fixed, reserved |
| 5 incubators, Hatch prompt | EmployeeServer.lua:37-40, 531-544 | fixed, reserved with their front |
| 11 hire spots and desks | EmployeeServer.lua:31-35; PlotVisuals.lua:199-203 | fixed in v1 (owner default), skin per building and sector |
| Six upgrade props | `itemOffset` TycoonCore.lua:131-135, `spawnItem` :189-201 | movable; default = today's slot |
| Furniture | PlotArt decor, cut into pieces | movable, bought |

Employees don't sit: the server sets `Home` (EmployeeServer.lua:185, 199), the client wanders 3 studs (EmployeeClient.lua:984-999); desks are fixed, so nothing changes. **Move-in (D-A):** `objects` stay exactly as they are; building n+1 contains n and the zones don't move, so no check can fail. The new area holds only the **starter set** (owner default: hire-desk skin + one furniture piece at fixed, tested spots); with a full budget a starter piece goes to the inventory, never lost.

**Checks** on `CompanyAction` (`"Place", id, x, z, r` · `"Store", id` · `"Sync"` · `"PickSector", key`): `data.ready` (false while loading or during the IPO save, IpoServer.lua:211-213); `id` a string under 40 chars, `x`/`z` finite (rounded to 0.5), `r` whole 0-7; ownership (`owned`, or `decor.Plant >= 2` for `Plant#2`); footprint (rotated rectangle) inside the building; overlaps ≤ 0.1 stud (floor marks ≤ 0.2 high may lie under, PlotVisuals.lua:38); no reserved zone (`PlotVisuals.zones`, PlotVisuals.lua:504-531; the six slot zones stop being reserved); height ≤ 12 (:42); budgets counted by the server; 4 requests/s, burst 8, 120/min. **One pure function in `CompanyConfig`**: the client previews red/green, the server decides. Footprints are sector data; a test proves each covers its art (`PlotVisuals.boxOf`, :65-72).

Placement never changes Income (`totalIncome` reads no position, TycoonCore.lua:137-145); buildings and furniture have none (economy_sim.py:1063). Buying spends Cash only: **no new `addEarnings` call** (daily_test.py:4327-4334). **No `Touched` handler:** the drag is a screen ray onto the floor plane, and decor has `CanQuery` off (PlotVisuals.lua:105), so taps are tested against footprints (daily_test.py:4254-4256 unchanged).

## 6. Part budget

`MAX_PARTS = 260` per room with props, `MAX_LIGHTS = 3` per plot (PlotVisuals.lua:39-40); rooms use 256 / 244 / 254 / 253 / 257 (PLOT_VISUALS.md). No written reason (220 in `1fba576`, raised per ROADMAP.md:41); likely **(inferred)** because every plot replicates to every player, 6 plots per server. The six props cost 118 parts (Desk 24, Coffee Machine 17, Laptop 17, Server Rack 24, Whiteboard 19, Neon Logo 17; PlotArt.lua:806-949); hire desks 2-6, sofa 5, plant 2. Shell **(≤ 60, estimate)** + 11 desks (≤ 66) + 118 leaves 16 parts: about 3 furniture pieces. **Proposal:** draw only owned hire desks (5-11); 320 per plot (shell ≤ 60, desks ≤ 66, objects ≤ 194: the six + 8-15 pieces); 3 lights per plot; a budget bar. Bigger buildings cost no more (a wall is one Part at any length). Server: 1,920 (today ≤ 1,542), 2,304 with the building pass. **Unresolved (owner default):** no change before the 6-plot phone test (gate G-S); if it fails, stay at 260 with 2-part desks.

## 7. Phone and PC, the Shop, the Portfolio

- **Edit mode** is a window (`OpenPanel = "Office"`): other windows close, the task tray and the thumbstick hide (TaskClient.lua:28; ShopClient.lua:725). Entry: "Arrange your office" on SHOP > Office; no new HUD slot (ShopClient.lua:101-104).
- **Camera:** scripted top-down. At 78 x 84 that is about 3.5 px per stud at 667 x 339 **(estimate)**: a Laptop is 10 x 7 px, so objects can also be picked from the inventory strip, and pinch zooms.
- **Touch:** select, then drag anywhere (moves by the finger's offset), snap 0.5, red when refused, lift = one `"Place"`. Rotate (45°), Store, Done: 56 x 56 px **(estimate)**. **PC:** mouse drag, R, Delete, Esc or E.
- **Layout:** the strip along the bottom, buttons at the right (landscape) or above the strip (portrait), clear of the HUD; the first draft's pixel rectangles stand **(estimate)** and are checked with Test > Device and top bars 0 / 36 / 58, like `TRAY_TESTS`.
- **Shop, no new tab** (ShopClient.lua:133-150, 204): SHOP > Office gets **Buildings** (next one: Locked or Buy), **Upgrades**, **Furniture**. `"Buildings"`, `"BuyBuilding", n`, `"Objects"`, `"BuyObject", n` on `ShopAction` (ShopServer.lua:701-715, 802-805), checked like `checkUpgradePurchase` (TycoonCore.lua:243-270) plus "stage reached" (IpoConfig.lua:151) and "building n-1 owned". Draft price: 50% of the stage threshold (900 / 3,150 / 11,700 / 40,500 at IPO 0, IpoConfig.lua:19-22, x2.5 per IPO); furniture 10-25%. Cash only in v1; later Robux bundles have fixed contents; no odds words (daily_test.py:4344).
- **Picker:** 2 x 2 (portrait) or a row of 4. **Portfolio:** scrolling cards.

## 8. Economy risks and anti-exploit

- **IPO pace is unchanged:** an IPO still needs earned valuation (IpoServer.lua:123-135, 192-195); Shares and the multiplier still come from it (IpoConfig.lua:162-172). Companies add two gift sources that never touch valuation, seed (1.3) and dividends (1.4): they only shorten the buying part of a rung.
- **Four sectors are four economies.** A faster sector, or one kinder to idle or casual players, becomes the only choice and the others dead content. Each must hit every rung within ±5% of Software for every LONG_GAME player profile.
- **Income models are the main risk:** Fintech interest rewards hoarding and idling, Biotech payouts are lumpy, Gaming launches stack with passes and the multiplier. All capped, engaged-only, no random outcome.
- **Prices follow the player's IPO count**, never the sector (`StageScale`, LONG_GAME section 5): a new sector restarts nothing.
- **Hopping:** only an IPO founds a company (IPO-ready valuation, 60 s cooldown at IpoConfig.lua:45, 50+ h by design); no "refound"; retiring pays nothing.
- **Duplicate funding:** the seed lives inside the one IPO transform; `ipoNumber` blocks a repeat (IpoServer.lua:179); held Cash is frozen (no transfer, no second IPO); the run check never pays a seed.
- **Dividend farming:** engaged seconds only (server-graded), capped by the active Income, base Income only. **Alts:** companies can't be given, traded or poached; LONG_GAME's R1-R3 stand. **Rollback:** older code keeps `companies` frozen and pays no seed.

**Simulate before any build** (tools/economy_sim.py has `--long`, `--active`, `--ipo`, `--daily`, :1682-1688; a new `--companies` mode adds seed, dividends, per-sector ladders and models):

| Sim | Question | Pass |
|---|---|---|
| S1 seed | `--long` with seed 0 / 10% / 25% cap: hours to IPO 1 and loop 2 | ≤ 5% faster per loop |
| S2 dividends | 0, 1, 4 held companies: hours per loop, loops 2-10 | ≤ 10% faster at IPO 10 |
| S3 parity | each model fitted to Software, dedicated / regular / casual (`LONG_PLAYERS`, :1183) | every rung ±5% |
| S4 bots | LONG_GAME section 2's macro and task-bot, per sector | no sector faster for a bot |
| S5 hopping | always the fastest sector vs one fixed sector, 10 IPOs | < 3% apart |

## 9. Build plan

Each PR: claim its scripts, `python3 tools/daily_test.py` passes (fake Roblox), F5 with no red errors, publish with **Shut down all servers**. Create new modules in Studio **before** pasting the script that requires them (`WaitForChild` without a timeout hangs, PUBLISH_RULES 2b). PR 1-8 don't need LONG_GAME; PR 9-14 need its economy core (PR 2), since dividends and income models are measured on the engaged clock.

| PR | Content | Tests | Studio by hand |
|---|---|---|---|
| **Engine** | | | |
| 1 | `companies` save: `CompanyServer`, `CompanyConfig` (the check), `SectorConfig` (Software, picker off); run check, anchor coordinates, `spawnItem` reads the layout; `"Place"`/`"Store"`/`"Sync"`; Debug "move Desk", "reset layout" | round trip; no section = today; `v = 2` and unknown sector kept; run mismatch; types, NaN, bounds, overlap, zones, rate, ownership; `addEarnings` count; section list | Create the 3 modules, then paste TycoonCore, ShopServer. Debug, rejoin: the Desk stayed moved |
| 2 | Nested buildings (section 4 sizes), floor strips, move-in, starter set, `"BuyBuilding"`, Buildings section; Software shells cut from PlotArt 2-5 | nested; spots; objects unchanged on move-in; locked by stage; Cash; budgets; stage 1 fingerprints | Paste PlotArt, PlotVisuals, CompanyConfig, CompanyServer, TycoonCore, ShopServer, ShopClient. Buy Seed: the Desk didn't move, the new floor is walkable |
| 3 | `CompanyClient` edit mode: drag, rotate, store, camera, pinch, strip, budget bar | rectangles at 320x568 / 667x375, top bars 0/36/58; sends only id, x, z, r | Create `CompanyClient`; Test > Device both sizes, touch and mouse |
| 4 | IPO to a new company: `held`, seed, retire, Portfolio, `"GoPublic"` + sector (Software), wording; dividends at 0 | atomic transform; seed cap; repeat refused; retire; frozen records; run check; `addEarnings` count | Paste IpoConfig, IpoServer, CompanyServer, TycoonCore, IpoClient. IPO twice: 2 cards; rejoin |
| **Sector format** | | | |
| 5 | `SectorSoftware` + `SectorArtSoftware` (today's content, keys unchanged); engine reads only `SectorConfig`; per-sector task rows and creature texts; income-model hook | no sector key in engine; fingerprints unchanged; every creature covered | Create both, paste the rest. F5: looks and earns as before |
| 6 | Picker for the first founding, `"PickSector"`, `PickerEnabled` in Studio only; a 2nd sector only as a test fixture | only while unset; unknown/disabled refused; old saves never asked | Debug "Reset company", picker on: pick at phone size |
| **Software slice** | | | |
| 7 | Software buildings 2-5 at section 4 sizes, desk skins, starter sets, skyline handled | shell checks per building | Walk buildings 1-5 |
| 8 | Software furniture (PlotArt + bible decor), `"BuyObject"`, light cap | footprints; budget and light refusals; D9 words | Buy, place, hit the budget, rejoin |
| **G-S** | **Go / no-go.** (a) 6 accounts, every plot at building 5 with a full budget, on a real low-end phone: ≥ 30 fps **(estimate)**; pick 260 or 320. (b) Every building in budget. (c) 3+ players: found, buy 2 buildings, arrange on a phone unaided, IPO into a new company, rejoin. (d) Sims S1-S5 pass. **No-go: fix and repeat before any other sector** | | |
| **Sectors** | | | |
| 9-10 | Fintech: `SectorFintech` (texts, tasks, interest), then `SectorArtFintech` | parity ±5%, footprints, D9 words, `id = 0` | Found a Fintech company; walk 1-5 |
| 11-12 / 13-14 | Biotech (research payout), Gaming (launch): the same | same | same |
| 15 | Picker on for live servers; PUBLISH_RULES "2d" note | all four in the picker | Publish; pick each sector on a phone |

## 10. Impact on other docs and branches

**docs/LONG_GAME_PROPOSAL.md (must change):**

| Section | Change |
|---|---|
| Header, 1 Pacing (lines 3, 18) | "50+ h, every loop 50+ h" stays (a loop = a company); `StageScale` follows the IPO count, not the sector; add a seed + dividend sensitivity row |
| 2 Clock (line 24) | Seed and dividends join the gifts that never count |
| 3 Ladder (36-60) | "Offices" = these buildings; 7 rungs but two C+D offices: one per rung or 8; the 97 items become per-sector data; 18 desks vs 11 hire spots (EmployeeServer.lua:31-35) and the budget |
| 4 Content (62-82) | "Loops 2+ replay the ladder (an industry skin per IPO)" (82) is replaced by the sector pick; content x4 (section 3) |
| 5 Shares (84-88) | Formula unchanged; new `ResetNames` wording; Day 7's decor piece per sector or shared |
| 6 Money (90-95) | Boardroom skin per sector or neutral; seed and dividends make no `addEarnings` call; income models pay inside the income-loop call (TycoonCore.lua:866) or TaskServer's, or each new site is reviewed (daily_test.py:4327-4334) |
| 7 Exploits (97-108) | R1-R3 stand if employees follow the player (question 1) |
| 8 PR plan (110-122) | PR 4 "Office framework" → this doc's PR 1-8; PR 7 "industry skin 1" → PR 9-14; `CompanyServer` before `TaskServer` |
| 9 Decisions (128) | All stand; the 50+ h first IPO is unchanged; the picker adds a choice before play (section 8) |

| Doc / branch | Change |
|---|---|
| `design-tutorial` (TUTORIAL_PROPOSAL.md section 2) | Step 1 comes after the picker (find `Office1` under "Upgrades" and scroll); step 9's text (IpoClient 519, 526-531) becomes "your company goes to the Portfolio"; new "Arrange your office" step; TutorialClient waits while `OpenPanel = "Sector"`. Small |
| `building-pass` (BUILDING_PASS_PROPOSAL.md D-2, section 3, E2) | One 62 x 62 footprint → per-building sizes; "65 studs", "25 apart" → 7.4; `sync(..., stageOf(data))` → the active company's building, keyed by sector; 64 parts still fit, but 4 shell sets. Must change |
| `visuals-garage` (PlotArt, PlotVisuals, PLOT_VISUALS.md, CLAUDE.md "Plot visuals") | "The plot stays 60 x 60" (PLOT_VISUALS.md:14) → nested buildings; skyline rule (:37) goes for buildings 4-5; "six props identical in every room" and "Floor the only solid" → per-sector movable props, Floor + extensions; `newPlot`/`setStage` (PlotVisuals.lua:235-269) per building and sector; `buildProp` takes position and rotation; PlotArt becomes Software's art (stage 1 fingerprint stays). Must change |
| `content-bible` | Rungs 1-6 = the Software package; the 5 industry skins dropped (answers its decision 9); "Office" names = buildings; locked names stay Software keys; minute 0 of "The first 5 hours" is the pick; three more bibles. Must change |
| CLAUDE.md, README, ROADMAP, PUBLISH_RULES | Save block (`companies`), modules and order, configs, remotes; file list; a "2d" note |
| Onboarding | The arrow targets (OnboardingServer.lua:103-121) don't move; it starts after the pick |

## 11. Open questions (unresolved, most important first)

1. **Employees at an IPO: follow the player (today, IpoConfig.lua:8) or stay with the old company?** Recommend follow: D-B's "never items" then covers upgrades, buildings and furniture. Otherwise every company rehires from zero and LONG_GAME's kept-hire refill and R1-R3 change.
2. **Creatures: same bodies with per-sector name, job and joke, or new types per sector?** Recommend same bodies. New types mean 18 models, keys, odds tables and `fixedHire` orders per sector (D9 tests x4) and harder cross-sector poaching.
3. **Buildings per sector: 5 (today's stages) or one per LONG_GAME rung (7, or 8 with both C+D offices)?** Decides shells (x4) and section 4's sizes. Recommend 7.
4. **Is 78 x 84 big enough, or move the plots (`PLOT_SPACING` 112)?** Recommend 78 x 84, judged at G-S.
5. **Seed 10% capped at 25% of rung 1; dividend 1% each, capped at 10%:** confirm before sims S1-S2.
6. **Fintech, Biotech, Gaming income models:** approve the mechanics, or today's Income per second with themed text? Recommend the mechanics only if S3-S4 pass.
7. **Cap 1 active + 4 held, the player picking which to retire?**
8. **Held companies: cards only, or visit an old building on the plot later?** Recommend cards in v1 (a visit rebuilds a second building and needs its budget).

## What I did not verify

- The world outside scripts (Baseplate size, SpawnLocation, hand-placed parts); no Studio or MCP was used. The 6-stud gap and 10-stud lounge clearance are my estimates.
- No `luau` here: no shell, building or footprint was built or measured.
- UI sizes not cited from code; Roblox's top-bar height; camera scale; pinch vs drag.
- Why `MAX_PARTS` is 260; phone frame rates; StreamingEnabled.
- Every economy number in 1.3, 1.4 and 8 until the sims run; no income model is simulated.
- Section 3's per-sector counts (estimates from the bible); the 4 MB DataStore key limit (Roblox docs).
- Other branches (building-pass, design-tutorial, content-bible) were read with `git show`, not run.
