# Companies, sectors and the Pokedex (proposal, design only)

Design only (2026-10-04, branch `design-customize`, revised from `47f0fe8`). No script, config or test changed. For the owner and the Claude sessions that will build it. Line numbers are for `47f0fe8`, whose `.lua`/`.py` files equal `visuals-garage` `7f5c141` (`main` has no PlotArt, PlotVisuals or Office tab yet). **(unverified)** = not checked in code; **(estimate)** = not measured; **(owner default)** = the owner may still veto; **(placeholder)** = a number the sims must size.

**Fixed by the owner:** **D-A** a new building moves every owned object in by itself, same coordinates; each building contains the previous footprint, positions measured from a fixed anchor on the door side. **D-B** an IPO founds a new company, seeded with a percentage of the old company's money (money only, never items). **D-C** every founding starts with choosing a sector. **D-D** a sector is a full package (tasks, objects, names, building theme, office look, way of making money); one engine; Software/SaaS (today), Fintech, Biotech, Gaming launch together; order: engine, Software end to end, then the other three. **D-E** free placement (drag, rotate), phone and PC. **P-1** the save holds one Pokedex entry per sector (not started / in progress / completed, a stamp tier, a replay count), not a list of companies. **P-2** an IPO completes the active company and stamps its sector entry; the old company is a stamped card, never a building (no held buildings, no 1 + 4 cap, no Portfolio of buildings); the player then picks the next sector. **P-3** completing all four sectors is the main goal (a Hall of Fame entry); the game continues, replays earn Gold and Platinum; a leaderboard ranks players. **P-4** old companies earn nothing; each stamp gives a small, capped, permanent collection bonus. **P-5** the seed stays, funding only; its numbers stay open until the sims pass. **P-6** see the defaults below.

**Owner defaults:** employees follow the player into the new company; creatures keep their bodies with a new name and job per sector; 5 buildings per sector, one per funding stage; working building size 78 x 84, re-checked in section 5 (result: 78 x 82); hire desks fixed in v1; furniture earns nothing; each new building has a free, fixed starter set (never random, D9); 45° rotation steps; the part budget stays open until a phone test with 6 full plots.

**New names** (none exists: `grep` over every `.lua`/`.py`): `CompanyServer` (ServerScriptService, owns the `pokedex` section), `CompanyConfig`, `SectorConfig`, one `Sector<Name>` per sector (ReplicatedStorage), one `SectorArt<Name>` per sector (ServerScriptService), `CompanyClient` (StarterPlayerScripts), `CompanyRemotes.CompanyAction`, `BoardServer` (ServerScriptService, the cross-server board, no save section), save section `pokedex`, OrderedDataStores `Collection_v1` and `HallOfFame_v1`. They replace the previous revision's `companies` section.

## 1. Companies, sectors and the Pokedex

**1.1 A company** is one run of one sector's ladder: its Cash, upgrades, buildings, furniture, layout, eggs in incubators and valuation. **The player** keeps everything else: employees (owner default), HR level, passes, boosts, shields, Shares, perks, IPO count and multiplier, `lifetime`/`best`, daily, onboarding, task stats, the Pokedex and its collection bonus (today's rule: IpoConfig.lua:6-8, 51). Only the active company exists in the world; a completed one is a card.

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

**1.3 Picking a sector, on every founding.** The picker is a window (`OpenPanel = "Sector"`): four cards with icon, name, how it makes money, the stamp (none, Bronze, Gold, Platinum) and "New" on a sector not started; 2 x 2 in portrait, a row in landscape. It opens for a new player before the Garage (the free egg and the arrow start after it), in every IPO (1.4) and after a run check (1.2). `CompanyAction("PickSector", key)` is accepted only while `active.picked == false`; purchases wait until then.
- **Next sector (proposal): any enabled sector, the same one included; none has to be completed first.** The rewards steer instead of a rule: Bronze, the largest bonus step, comes only from a sector not done yet (section 8), and the picker preselects the first sector without a stamp. A forced order would lock a favourite sector away for 150+ h (three loops of 50+ h, LONG_GAME section 1).
- `SectorConfig.PickerEnabled = false` until all four sectors exist (like `TaskConfig.StudioOnly`): everyone is Software and the IPO step is skipped.

**1.4 The IPO completes the company.** Today `goPublic` (IpoServer.lua:177-243) checks the IPO number, cooldown, pass check, valuation and poaching, then calls `commitIpo` (TycoonCore.lua:544-588), whose save transform resets Cash, `owned` and eggs (IpoConfig.lua:53-58) and writes the new `ipo`. New:
1. The IPO window adds a "Next company" step before Confirm: the picker's cards.
2. `IpoAction("GoPublic", ipoNumber, sectorKey)`: `sectorKey` a string naming an enabled sector, plus today's checks (`ipoNumber == count + 1` blocks a repeat, IpoServer.lua:179).
3. **One transform, one save** (in `commitIpo`'s transform, TycoonCore.lua:548-564): the active sector's entry becomes `"done"`, `stamp = max(stamp, earned)` (1.5), `replays + 1` if it was already done, `firstAt`, `bestEngaged`, a new `card`; `hallAt` when the fourth sector is first done; a new `active` (the picked sector, a name, `building = 1`, no decor or objects, `engaged = 0`, `picked = true`); the new sector's entry `"progress"` if it had none; `run = count + 1`; Cash = `StartingCash` + seed (section 8). Today's resets stay.
4. Only after that save works (as TycoonCore.lua:565-587): the plot becomes the new sector's Garage, a stamp pop-up shows, and `BoardServer` writes the new score (1.6). A failed save changes nothing, as today.

| Resets with the company (frozen in its card) | Stays with the player |
|---|---|
| Cash (to `StartingCash` + seed), upgrades, buildings, furniture and layout, eggs in incubators, valuation | employees (owner default), HR level, passes, boosts, shields, Shares, perks, IPO count and multiplier, `lifetime`/`best`, daily, onboarding, task stats, stamps and the collection bonus |

**The card** sits in a new **Pokedex** tab of the IPO window (today "IPO", "Shares Shop", "Leaderboard", IpoClient.lua:354): sector, name, stamp, IPO number, date, engaged hours, valuation ratio, building reached, and a **top-down map** of the layout, one Frame per object footprint, drawn from sector data in ReplicatedStorage (cheap: no Parts). A 3D diorama (ViewportFrame) would need the art on the client, but sector art lives in ServerScriptService like PlotArt: not in v1. Only each sector's latest completion is stored (`card`, 1.2). The IPO window's lists (`ResetNames`, IpoConfig.lua:60-65; the keep list, IpoClient.lua:524-533) add "buildings, furniture" and "stamps"; wording: "Your company is complete and gets its stamp. Your next one starts in a garage with $X of funding."

**1.5 Stamps, replays, Hall of Fame.**

| Stamp | Earned by | Bonus (section 8) |
|---|---|---|
| Bronze | the sector's first completion (any IPO) | +1.5% |
| Gold | a replay completed within **T_gold = 1.0 T** engaged hours | +0.5% |
| Platinum | a replay within **T_plat = 0.8 T** and gone public at ratio ≥ **1.25** | +0.5% |

- **T** = the reference engaged hours of that loop for a regular player (LONG_GAME section 1: 57 / 51.5 / 52 h for loops 1-3); every T and ratio is a **placeholder** for sim S6. Engaged seconds come only from the server's engaged clock (graded tasks, LONG_GAME section 2), so Gold and Platinum wait for LONG_GAME PR 2; until then only Bronze exists.
- **Pass fairness:** 2x Cash alone makes a run about 15% shorter (48.7 vs 57.1 h, LONG_GAME section 6). The targets are shortened by the sim's measured speed-up for the passes owned at founding (placeholder x0.85 with 2x Cash), or Gold and Platinum could be bought.
- **A replay** has the same content and items, priced by the IPO count (`StageScale`), never by sector or stamp. It differs from a first run in four things: the IPO window shows a stamp clock (engaged hours so far against the two targets); first-time sector hints don't repeat; a stamp never goes down; `replays` counts it.
- **Hall of Fame:** the first time all four entries are `"done"`, `hallAt` is set: a title (named in the content bible), a gold frame on the Pokedex and a Hall of Fame board entry (1.6). The game goes on: replays chase Gold and Platinum, and IPOs keep paying Shares and the multiplier.

**1.6 Leaderboard.**
- **Today:** in-server only. IpoServer copies `IpoCount` and `IpoBest` onto each player (IpoServer.lua:46-63); IpoClient sorts the server's players by them (IpoClient.lua:750-783). No OrderedDataStore, MemoryStore or cross-server board exists (grep; docs/reviews/FULL_REVIEW.md:126). FR-11 (names not escaped, IpoClient.lua:770) is still open: fix it first.
- **Ranks:** **Collection** = `1000 x stamp points + min(IPO count, 999)`, stamp points per sector Bronze 1, Gold 2, Platinum 3 (max 12); **Hall of Fame** = earliest `hallAt` first.
- **Storage:** `BoardServer` (no save section) writes OrderedDataStores `Collection_v1` and `HallOfFame_v1` (`GetOrderedDataStore` inside `pcall`), key = UserId, a whole number. Only the server writes, from the `pokedex` it loaded, only after the save holding the stamp succeeded; on join it rewrites a stored value lower than the save's (a failed write). It reads the top 50 with `GetSortedAsync` once per 10 minutes per server, cached, shown as a second list in the Leaderboard tab.
- **Anti-cheat:** no client sends a score; values are capped (12,999); tiers use the server's engaged clock; a server that doesn't know every key in the section writes nothing (1.2); Debug "grant stamp" is Studio only. A wiped or banned account is removed by hand (`RemoveAsync` on a written UserId, as PUBLISH_RULES step 13).
- **Studio:** OrderedDataStores need "Enable Studio Access to API Services" like the save (CONTRIBUTING.md:41, TycoonCore.lua:38); without it the list says "not available". Studio uses the live DataStores (PUBLISH_RULES.md:46), so in Studio both names get a `_Studio` suffix (`RunService:IsStudio()`).
- **Limits:** Roblox's request budgets and the `GetSortedAsync` page size **(unverified here)**; one write per stamp and one read per 10 minutes per server is far below them **(estimate)**.

## 2. The sector package

**Shared engine (never names a sector; a test fails on a sector key in engine code):** the `pokedex` section, the picker, IPO-to-new-company, stamps and tiers, seed, collection bonus, the board; nested buildings, move-in, placement check, budgets; SHOP > Office and purchase checks; the task engine and its four action types (Answer, Choose, Timing, Targets); creatures, eggs, odds, `fixedHire` (D9), poaching; daily, onboarding, HUD; the economy clock; the sim.

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

## 4. Plot space (re-verified in the code, recomputed)

**What the code says** (read again for this revision, not copied):
- **Plots:** `PLOT_SPACING = 90`, `MAX_PLOTS = 6` (TycoonCore.lua:74, 76); `plotCenter` = x -225 + 90 x (slot - 1), z 150 (:123-126): x -225, -135, -45, 45, 135, 225. `Floor` 60 x 1 x 60 at the center (:736): x ±30 around each center, z 120-180; 30 studs between floors. `PlotArt.Layout` copies it (`floorSize`, PlotArt.lua:31).
- **Front = +Z:** BuySign at z +24 (TycoonCore.lua:75), IpoSign at (21, +24) (IpoServer.lua:21), spawn at +12 facing the sign (TycoonCore.lua:698-700); the layout map has the incubators at z -25, the hire rows at -10 / 2 / 14, `minAisle = 6`, `laneEnd = 30` (PlotArt.lua:33-69). **Anchor = front-center of the floor: local (0, +30), world z 180.**
- **VIP Lounge:** center (0, 0.5, 70), floor 36 x 24, walls 10 high and 1 thick (ShopServer.lua:35-37, 636-650): outer faces x ±18.5, z 57.5-82.5. Its 8-wide door (:38, 653) is in the +Z wall, facing the plots; the door's `Touched` (:683) is the game's only one. A non-VIP inside is moved to **z 88** (:839). Its comment puts it "between the spawn and the garage plots" (:35), so the spawn is at z < 58 **(position unverified)**.
- **Skyline** (IpoReady room): local z -49 to -43, x within ±29 (PlotArt.lua:699-707): world z 101-107.
- **Nothing else is built by a script.** Parts come only from TycoonCore (`makePart`, :91: Floor, props, sign), PlotVisuals (:92, rooms), IpoServer (:293-300, sign), EmployeeServer (:69, incubators), ShopServer (:97, lounge), CreatureModels (bodies) and OnboardingClient (:60, an invisible client-only arrow target). PoachServer is given `plotCenter` (TycoonCore.lua:650) but never uses it: poaching needs no walk between plots.
- **Building pass** (branch `building-pass`, BUILDING_PASS_PROPOSAL.md section 3): wall inner face 0.2 past the floor edge, wall 0.8, roof 1.5 past the wall: **2.3 per side beyond the inside size**.
- **Not in the repo:** the Baseplate's size and position, the SpawnLocation, hand-placed parts, Terrain (docs/STUDIO_SYNC.md:37 records only the Baseplate's color).

**Recomputed** (the building grows sideways, centered, and backward from the anchor, D-A):
- **Width W:** the gap between two roofs = 90 - W - 4.6. Using the game's own aisle minimum (6 studs, PlotArt.lua:68) as the walking gap: W ≤ 79.4, **78** (even, so half-widths stay whole).
- **Depth D:** once W > 48.4, plots 3 and 4 (x ∓45) stand behind the lounge (x ±18.5): at W = 78 they span x -84 to -6 and 6 to 84. Back roof edge = 180.2 - D - 2.3. Keeping the kick-out spot (z 88) plus the same 6-stud aisle clear: edge ≥ 94, so D ≤ 83.9, **82** (even). Plots 1, 2, 5, 6 could go deeper, but one rule keeps one set of art.

**Largest building: 78 x 82 inside (1.78x the area), no plot moved.** **Difference from the earlier 78 x 84:** same width; 2 studs less depth, because the clearance now comes from two code numbers (kick-out z 88, ShopServer.lua:839; `minAisle` 6, PlotArt.lua:68) instead of an estimated 10 studs from the door. The outer roofs reach x ±266.3, past today's floors at ±255: **the Baseplate must be at least 534 wide (unverified)**. Nested sizes **(estimate)**: Garage 60 x 60, Seed 64 x 66, Series A 68 x 70, Series B 72 x 76, IPO-ready 78 x 82 (back walls at world z 120 / 114 / 110 / 104 / 98).

**Changes:** (1) the skyline (z 101-107) sits inside buildings 4-5: it goes, or becomes a back-wall picture (`BACKDROP_Z`, PlotVisuals.lua:44). (2) The solid floor grows: flush `FloorExtension` strips (CLAUDE.md's "the real Floor is the only solid" changes; `PlotVisuals.check` already lets `Floor` parts collide, PlotVisuals.lua:590-592). (3) 60 x 60 assumptions go per building: `PlotArt.Layout.floorSize` (PlotArt.lua:31), `PlotVisuals.check`'s half-size and floating check (PlotVisuals.lua:544, 643), the building pass's 65 x 65 roof and "25 apart" (now 7.4). (4) Gameplay positions don't move: the incubators (EmployeeServer.lua:37-40) end up mid-building.

**Bigger** needs `PLOT_SPACING` ≥ W + 10.6 (100 wide: **112**), one constant that every system reads through `plotCenter` (TycoonCore.lua:601, 639, 650); the row grows to about 670 studs. Deeper than 82 means moving the plots toward +Z (the `150`, :125).

**Studio by hand (owner, read only, nothing changed):**
1. Workspace > Baseplate, Properties: **Size** and **Position**. Needed: x from -267 to 267 and z from 95 to 182, or more.
2. Workspace's children: list everything except Baseplate, Terrain, Camera and the script folders (`<name>_Startup`, `VipLounge`, `OnboardingArrow`, `PREVIEW_STAGES`). For each: name, Position, Size. Especially the **SpawnLocation**, and anything at z 85-120 or beyond x ±225.
3. Terrain near the plots (look from above in the editor).
4. Workspace > **StreamingEnabled** (on or off: it changes what each phone loads, section 6).

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

## 8. Economy: seed, collection bonus, risks, sims

**8.1 Seed (P-5): funding only.** The new company starts with `StartingCash` (0, IpoConfig.lua:44) plus a seed of **s% of the old company's Cash at the IPO, capped at c% of the new company's first-rung prices**. s = 10 and c = 25 are **open placeholders** until S1 passes (today's six upgrades cost $7,025, TycoonCore.lua:65-72: cap $1,756; LONG_GAME's Garage items about $131K: about $33K **(estimate)**). Cash only, never an item; a gift (no `addEarnings`, never valuation); paid once, inside the IPO transform (1.4). **The dividend is removed:** it was passive income from held companies, which P-4 forbids and P-2 removes.

**8.2 Collection bonus (P-4).** Proposal: a **Cash multiplier on Income**: +1.5% per Bronze, +0.5% more for Gold, +0.5% more for Platinum, at most 2.5% per sector, **capped at +10% in all** (four Platinum) **(placeholders, S2)**. It is applied with the passes (`updateIncome`, TycoonCore.lua:148-152: Income x pass multipliers x IPO multiplier) but is **never valuation**: from LONG_GAME PR 2 the valuation counts base Income only (LONG_GAME section 6), so the bonus buys sooner and never moves the clock ("Cash can only fill a rung, never skip it"). **It stays 0 until PR 2**: today the income loop adds the whole Income, passes included, to the valuation (TycoonCore.lua:865-866). Size: a tenth of the 2x Cash pass, which saves about 15% of a run (LONG_GAME section 6): roughly 1-2% **(estimate)**. **Fallback** if S2 fails: a cheaper first rung per stamp (the Garage is 1.5 of 57 h, LONG_GAME section 3), which multiplies nothing.

| Pass, product, perk, system | With the bonus | Risk and rule |
|---|---|---|
| 2x Cash x2 (ShopConfig.lua:41), VIP x1.5 (:50) | multiplies: x3.3 at most, then the IPO multiplier (IpoConfig.lua:162-165) | Cash only; valuation at base after PR 2, so the stack never shortens the clock |
| Shareholder 2x Shares (:88; `sharesFor`, IpoConfig.lua:168-172) | none | **No stamp ever pays Shares**: the pass would double a permanent reward on every replay |
| Cash packs (Income minutes, ShopServer.lua:537-541) | up to +10% per pack | fixed contents (D9 safe); a gift once PR 2 deletes its `addEarnings` call |
| Daily Cash (Income minutes, DailyServer.lua:177) | up to +10% | already a gift; daily Shares are never doubled |
| Tasks (seconds of Income, TaskConfig) | up to +10% Cash | valuation at base after PR 2 |
| Away bank, Night Shift (10% of base Income, LONG_GAME section 2) | excluded | |
| Extra Slots, Auto-Hatch, Headhunter, Instant Hatch, Poach Shield; Faster Recruiting, Extra Incubator, Extra Desk, Recruiter Network | none | |
| Luck Boost (`changesOdds`, ShopConfig.lua:134), Talent Scouts (IpoConfig.lua:97-102) | none | **D9:** a stamp never changes odds; stamps and the bonus are earned only, never sold, never random |
| Seed (8.1) | the old company's Cash was raised by it | bounded by the seed cap |

**8.3 Risks.**
- **IPO pace is unchanged:** an IPO still needs earned valuation (IpoServer.lua:123-135, 192-195); Shares and the multiplier come from it (IpoConfig.lua:162-172). Seed and bonus never touch valuation.
- **Compounding:** the bonus multiplies with both Cash passes and the IPO multiplier; the Shareholder pass doubles nothing of it while stamps pay no Shares. A bonus switched on before LONG_GAME PR 2 would shorten every IPO, most for pass owners.
- **Tiers and passes:** without pass-adjusted targets (1.5), Gold and Platinum are about 15% easier with 2x Cash: a paid edge on the board.
- **Four sectors are four economies:** a faster sector, or one kinder to idle players, becomes the only choice. Each must hit every rung within ±5% of Software for every LONG_GAME player profile. **Income models** are the main risk (Fintech interest rewards hoarding, Biotech payouts are lumpy, Gaming launches stack with passes): all capped, engaged only, never random.
- **Prices follow the IPO count**, never the sector or stamps (`StageScale`, LONG_GAME section 5).
- **Hopping and farming the first rung:** only an IPO founds a company (IPO-ready valuation, 60 s cooldown, IpoConfig.lua:45; 50+ h by design). A stamp needs a whole ladder, so the first rung can't be farmed; what a founding gives (seed, starter set) is capped and bounded by the IPO rate.
- **Duplicate seed:** paid only in the one IPO transform; `ipoNumber` blocks a repeat (IpoServer.lua:179); a failed save changes nothing (TycoonCore.lua:565-567); the run check pays none.
- **Alts:** stamps and cards can't be given, traded or poached; LONG_GAME's R1-R3 stand (employees follow the player). **Rollback:** older code keeps `pokedex` frozen and pays no seed (1.2).

**8.4 Simulate before any build** (tools/economy_sim.py has `--long`, `--active`, `--ipo`, `--daily`, :1684-1687; a new `--pokedex` mode adds seed, bonus, tiers, per-sector ladders and models). Pass marks are **placeholders** too:

| Sim | Question | Pass |
|---|---|---|
| S1 seed | `--long`, seed 0 / 10% / 25% cap: hours to IPO 1 and loop 2 | ≤ 5% faster per loop |
| S2 bonus | 0 / 1 / 4 / 8 / 12 stamp points x passes none / 2x Cash / VIP / both, loops 2-12 | at the cap ≥ 95% of the no-bonus hours for every pass set; both passes gain ≤ 2 points more than none |
| S3 parity | each model fitted to Software, dedicated / regular / casual (`LONG_PLAYERS`, :1183) | every rung ±5% |
| S4 bots | LONG_GAME section 2's macro and task-bot, per sector | no sector faster for a bot |
| S5 sector hopping | always the fastest sector vs one fixed sector, 10 IPOs | < 3% apart |
| S6 tier targets | replay hours per profile and pass set against T_gold, T_plat, ratio 1.25 | Gold on ≥ 50% of regular replays, Platinum on ≥ 20% of dedicated ones; pass owners within ±5 points of others |
| S7 board exploits | stamp points per 100 engaged hours: (a) always a new sector vs replays, (b) IPO at IPO-ready vs waiting for 1.25, (c) the task-bot | (a), (b) within 10% of normal play; (c) never above the dedicated human |

Duplicate seed is a test, not a sim: daily_test cases for a failed IPO save retried, a repeated `GoPublic` and a run mismatch pay the seed exactly once.

## 9. Build plan

Each PR: claim its scripts, `python3 tools/daily_test.py` passes (fake Roblox), F5 with no red errors, publish with **Shut down all servers**. Create new modules in Studio **before** pasting the script that requires them (`WaitForChild` without a timeout hangs, PUBLISH_RULES 2b). **PR 1 ships the whole `pokedex` format** (every field of 1.2 loaded, checked and written back even while unused): code that knows a section drops the fields it doesn't know (A10), so a field added later would be lost on a rollback to PR 1-3. PR 1-7 don't need LONG_GAME; PR 8-14 need its economy core (PR 2: the engaged clock, base valuation).

| PR | Content | Tests | Studio by hand |
|---|---|---|---|
| **Engine** | | | |
| 1 | `pokedex` save (full format, legacy conversion, run check, versioning); `CompanyServer`, `CompanyConfig` (the placement check), `SectorConfig` (Software, picker off); anchor coordinates, `spawnItem` reads the layout; `"Place"`/`"Store"`/`"Sync"`; Debug "move Desk", "reset layout" | round trip; no section = today; legacy IPO count gives no stamp; `v = 2` and unknown sector kept, actions refused; run mismatch; types, NaN, bounds, overlap, zones, rate, ownership; `addEarnings` count; section list | Create the 3 modules, then paste TycoonCore, ShopServer. Debug, rejoin: the Desk stayed moved |
| 2 | Nested buildings (section 4 sizes), floor strips, move-in, starter set, `"BuyBuilding"`; Software shells cut from PlotArt 2-5 | nested; spots; objects unchanged on move-in; locked by stage; Cash; budgets; stage 1 fingerprints | Paste PlotArt, PlotVisuals, CompanyConfig, CompanyServer, TycoonCore, ShopServer, ShopClient. Buy Seed: the Desk didn't move, the new floor is walkable |
| 3 | `CompanyClient` edit mode: drag, rotate, store, camera, pinch, strip, budget bar | rectangles at 320x568 / 667x375, top bars 0/36/58; sends only id, x, z, r | Create `CompanyClient`; Test > Device both sizes, touch and mouse |
| **Pokedex** | | | |
| 4 | IPO completes the company: Bronze, card, seed (Studio only until S1), `"GoPublic"` + sector, Pokedex tab, wording; picker on every founding and the first, `"PickSector"`, `picked`; `PickerEnabled` in Studio only, a 2nd sector only as a test fixture | one transform; Bronze once; `"done"` never goes back; seed cap and exactly once; repeat refused; run check; picker only while `picked == false`; `addEarnings` count | Paste IpoConfig, IpoServer, CompanyServer, TycoonCore, IpoClient; create `CompanyClient`'s picker. IPO twice: two stamps or a replay; rejoin |
| **Software slice** | | | |
| 5 | `SectorSoftware` + `SectorArtSoftware` (today's content, keys unchanged); the engine reads only `SectorConfig`; per-sector task rows and creature texts; income-model hook | no sector key in engine; fingerprints unchanged; every creature covered | Create both, paste the rest. F5: looks and earns as before |
| 6 | Software buildings 2-5 at section 4 sizes, desk skins, starter sets, skyline handled | shell checks per building | Walk buildings 1-5 |
| 7 | Software furniture (PlotArt + bible decor), `"BuyObject"`, light cap | footprints; budget and light refusals; D9 words | Buy, place, hit the budget, rejoin |
| **G-S** | **Go / no-go.** (a) 6 accounts, every plot at building 5 with a full budget, on a real low-end phone: ≥ 30 fps **(estimate)**; pick 260 or 320. (b) Every building in budget. (c) 3+ players: pick, buy 2 buildings, arrange on a phone unaided, IPO into a new sector, find the card, rejoin. (d) Sims S1, S3, S5 pass. (e) The section 4 Studio checks are done. **No-go: fix and repeat before any other sector** | | |
| **Sectors** (need LONG_GAME PR 2) | | | |
| 8-9 | Fintech: `SectorFintech` (texts, tasks, interest), then `SectorArtFintech` | parity ±5%, footprints, D9 words, `id = 0` | Pick Fintech; walk buildings 1-5 |
| 10-11 / 12-13 | Biotech (research payout), Gaming (launch): the same | same | same |
| **Tiers and board** | | | |
| 14 | Gold and Platinum (engaged clock, pass-adjusted targets), the stamp clock, the collection bonus switched on, Hall of Fame title. Needs S2, S4, S6 | tiers at the edges; stamp never down; bonus cap; bonus never in valuation; no Shares from a stamp | Debug "finish replay fast/slow"; check stamps and Income |
| 15 | `BoardServer`: `Collection_v1`, `HallOfFame_v1`, `_Studio` names, second list in the Leaderboard tab, FR-11 fixed. Needs S7 | value from the save only; written after the save; capped; no write with unknown keys; Studio names | API Services on: earn a stamp in Studio, see the `_Studio` board |
| 16 | Picker on for live servers; PUBLISH_RULES "2d" note | all four in the picker | Publish; pick each sector on a phone |

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
