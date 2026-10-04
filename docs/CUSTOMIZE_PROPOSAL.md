# Companies, sectors and the Pokedex (proposal, design only)

Design only (2026-10-04, branch `design-customize`, revised after two independent reviews and for owner decision D-F; funding rounds moved to docs/FUNDING_ROUNDS_PROPOSAL.md on 2026-10-05). No script, config or test changed. For the owner and the Claude sessions that will build it. Line numbers are for this branch after merging `main` `9798388` (re-checked 2026-10-05). **(unverified)** = not checked in code; **(estimate)** = not measured; **(owner default)** = the owner may still veto; **(placeholder)** = sized by the sims.

**Fixed by the owner:** **D-A** a bigger building contains the previous one; objects move in at the same coordinates from a door-side anchor. **D-B** an IPO founds a new company, seeded with some of the old one's money (never items). **D-C** every founding starts with picking a sector. **D-D** a sector is a full package on one engine; Software (today), Fintech, Biotech, Gaming launch together. **D-E** free placement, phone and PC. **P-1** one Pokedex entry per sector. **P-2** an IPO completes the company and stamps its sector; the old company is a card. **P-3** all four sectors = the main goal (Hall of Fame); replays earn Gold and Platinum; a leaderboard. **P-4** old companies earn nothing; stamps give a small capped bonus. **P-5** the seed stays. **CLAUDE.md:29 exception approved:** `BoardServer` alone may use the leaderboard OrderedDataStores (section 7). **Inventory:** a purchase goes to the inventory, with "Place now". **D-F funding rounds:** reaching a stage by valuation lets the player raise a round of a size they pick; it gives Cash only, costs dilution (fewer IPO Shares), and the room follows the building owned, not the stage (1.7). **Round Cash (decided 2026-10-05):** a gift like the daily calendar, never `addEarnings`. The rounds themselves are in **docs/FUNDING_ROUNDS_PROPOSAL.md** (`FUND` below).

**Owner defaults:** employees follow the player; creatures keep their bodies, renamed per sector; 5 buildings per sector (building 5 serves Series C+D to IPO-ready); any sector can be picked next; an unplaced item still earns; largest size **78 x 82**; hire desks fixed in v1; furniture earns nothing; a free, fixed starter set per building (D9); 45° rotation; part budget open until a phone test.

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
    stored = { [id] = true },           -- in the inventory (section 4)
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
  dust = number,             -- Shares remainder in 1/10000 Share, -5000 to 4999 (FUND 3)
  studio = boolean,          -- saved by a Studio server: never on the live board
}
```

- **Fields:** `id` = an upgrade name or `<objectKey>#<n>`; `x`, `z` from the anchor, step 0.5; `r` 0-7; at most 40. An owned upgrade with no entry stands at its default slot; owned furniture with no entry, and any id in `stored` (at most 40), is in the inventory (section 4). `ratio` = IPO valuation / IPO-ready valuation. About 11 KB **(estimate)**.
- **Loader: KEEP at every level.** Unknown fields are written back, as in onboarding (OnboardingServer.lua:226, 243, 281), daily (DailyServer.lua:244, 261, 290), tasks (TaskServer.lua:712, 766, 800) and fixedHires (EmployeeServer.lua:657, 675, 694), but at **every** level: the section, `active`, `decor`, `passSeconds`, `objects[i]`, `stored`, `told`, `rounds`, `rounds[k]`, `sectors` (an unknown sector key: a newer sector, kept whole), `sectors[k]`, `card`, `card.owned` (unknown upgrade names), `card.decor`, `card.objects[i]`, `card.rounds[k]`, `kept`. In the maps (`decor`, `kept`, `passSeconds`, `card.decor`) an unknown key is kept with its value; a rollback to code without this rule would drop them. Those four keep top-level fields only; shop, team, poach and ipo keep none (EmployeeServer.lua:648).
- **Versioning:** `v` rises only when a field changes meaning; a higher `v` is held as one opaque value, written back unchanged, and the session refuses `GoPublic`, `Place`, `BuyBuilding`, `PickSector`, `Raise`; with an unknown sector key `BoardServer` writes nothing. *Tests:* `v = 2` deep-equal after a save; each refusal.
- **Bad values** (type, NaN, infinite, negative, out of range, unknown or duplicate id) are skipped with a warning; `stamp` clamped; `"done"` with stamp 0 becomes 1. Rounds: FUND 1.
- **Wiring:** `KNOWN_SECTIONS` (TycoonCore.lua:84), `buildPayload` (:421-433), save gate (:481); the daily_test checks of section 6's test impact change in the same PR. Publish with Shut down all servers; rollback floor stays `V_launch` (M4+ code keeps unknown sections, TycoonCore.lua:773-777, 434-438).
- **No legacy migration:** nothing is launched (PUBLISH_RULES.md:17, 101); all test accounts are wiped together before launch (`RemoveAsync` on a written list, :111). **A missing `pokedex`** = a new founding: `run = ipo.count`, Software, `picked = true` while the picker is off, building 1.
- **A10 run check, two cases.** (1) **`run < ipo.count`:** an older version ran an IPO (TycoonCore.lua:549-559; no seed, no dilution, `pokedex` frozen). IPOs need the valuation (IpoServer.lua:192-195), so the sector gets `"done"`, Bronze if unstamped and a card (its `rounds` unchanged); the new company keeps the sector, `picked = false`, building 1, `run = ipo.count`. (2) **`run > ipo.count`:** never an IPO. Only Debug **IpoReset** lowers the count (`count = 0`, IpoServer.lua:426; Studio only, :456); a restored DataStore version brings `pokedex` back with `ipo` (one key, TycoonCore.lua:505). So: `run = ipo.count`, `active` kept as it is (a settled round stays settled), no stamp, card or bonus, `pokedex.studio = true`, a warning. Treating it as an IPO would give a free Bronze and a card, and the shared save key (PUBLISH_RULES.md:46) would carry them to live, where `studio` blocks the board but not the Income bonus (5.2). A damaged `ipo` section read as count 0 lands here too: the board stays off for that account (the safe side). *Tests:* IpoReset then rejoin: no stamp, no card, rounds unchanged, `studio` set; `run` 2 with `count` 3: Bronze and card once.

**1.3 Picking a sector, on every founding.** A window (`OpenPanel = "Sector"`): four cards (icon, name, how it makes money, stamp, "New"); for a new player, in every IPO and after a run check's case (1). `CompanyAction("PickSector", key)` only while `picked == false`. Any enabled sector, the same included; Bronze needs a new one, and the picker preselects one. `SectorConfig.PickerEnabled = false` until all four exist.

**1.4 The IPO completes the company.** Today `goPublic` (IpoServer.lua:177-243) checks, then `commitIpo` (TycoonCore.lua:544-588) saves with a transform resetting Cash, `owned` and eggs (IpoConfig.lua:53-58). New:
1. The picker before Confirm; `IpoAction("GoPublic", ipoNumber, sectorKey)` adds a sector check to `ipoNumber == count + 1` (IpoServer.lua:179).
2. **One transform, one save** (TycoonCore.lua:548-564): `"done"`, `stamp = max(stamp, earned)`, `replays`, `firstAt`, `bestEngaged`, the `card`; `hallAt` on the fourth; a new `active` (building 1, no rounds); `run = count + 1`; Cash = `StartingCash` + seed.
3. Only after that save works (:565-587): the Garage room, a stamp pop-up, the board write.

**The card** is in a new **Pokedex** tab of the IPO window (IpoClient.lua:354): sector, name, stamp, IPO number, date, engaged hours, ratio, founder stake and a **top-down map** (Frames per footprint). `ResetNames` (IpoConfig.lua:60-65) and the keep list (IpoClient.lua:524-533) add buildings, furniture, stamps, rounds.

**1.5 Stamps, replays, Hall of Fame.**
- **Bronze:** first completion, bonus +1.5%. **Gold:** a replay within **1.0 T** engaged hours, +0.5%. **Platinum:** within **0.8 T** at ratio **≥ 1.25**, +0.5%. **T** = the loop's reference hours for a regular player (LONG_GAME section 1: 57 / 51.5 / 52 h); **placeholders** (S6). The clock is the server's, weighted like the valuation (LONG_GAME_PROPOSAL.md:23): Gold and Platinum wait for LONG_GAME PR 2. If the owner picks FUND 3's option B, Gold and Platinum also need a final stake floor.
- **Pass fairness:** 2x Cash shortens a run about 15% (LONG_GAME section 6), so a target shrinks by that times the **share of the run's engaged seconds with the pass** (`passSeconds`), never by passes owned at founding (an exploit). A replay is priced by IPO count only. **Hall of Fame:** all four `"done"`: `hallAt`, a title, a gold frame, a board entry.

**1.6 Leaderboard.** Today in-server only (IpoServer.lua:46-63; IpoClient.lua:750-786); no OrderedDataStore exists (docs/reviews/FULL_REVIEW.md:126).
- **Ranks:** **Collection** = `1000 x stamp points + min(IPO count, 999)` (Bronze 1, Gold 2, Platinum 3); **Hall of Fame** = earliest `hallAt`. `BoardServer` writes `Collection_v1`, `HallOfFame_v1` (in `pcall`, key UserId) from the loaded `pokedex` after the stamp's save; repairs a lower value on join; reads the top 50 every 10 minutes. No client sends a score.
- **Studio never reaches the live board.** Studio and live share the save key (PUBLISH_RULES.md:46): every Studio save sets `pokedex.studio = true` (never cleared); a `studio` account is never written, repaired or shown; Studio writes only `_Studio` twins; a deny list (`BoardServer.REMOVED`) is never written or shown. *Test (fake stores):* a `studio` save with four Platinum joins live: no write.
- **Names (FR-11):** `UserService:GetUserInfosByUserIdsAsync` (`pcall`, cached; **unverified limits**); the client escapes `& < > " '` (fixes IpoClient.lua:780).

**1.7 Funding rounds (D-F).** One round per stage per company, opened by the valuation, Cash only (a gift), paid for with dilution of the IPO Shares; saved in `active.told`/`rounds` and on the card (1.2). Rules, economy, dilution curve, exploits, tests, UI, S8 and PR 4b: **FUND**.

## 2. The sector package and content

**Shared engine** (never names a sector; a test fails on a sector key in engine code): `pokedex`, picker, IPO flow, stamps, seed, bonus, funding rounds, board; buildings, placement, inventory; SHOP > Office; tasks; creatures, eggs, odds, `fixedHire` (D9), poaching; daily, onboarding, HUD; the economy clock; the sim.

**Per sector** (`Sector<Name>`, `SectorArt<Name>`): identity (key, name, icon, palette, 12+ company names); 5 buildings; upgrades (keys never reused; Software keeps today's six, TycoonCore.lua:65-72); furniture; tasks (`TaskConfig.Rows`, TaskConfig.lua:49); creature names and jobs (CreatureConfig.lua:56-104); egg names; one income model; bundles with fixed contents, `id = 0`. Art in PlotArt's `P(...)` format (PlotArt.lua:9-23).

**Income models** (deterministic, capped, engaged only; **placeholders**, S3). Software: steady Income. The others, `Sector<Name>.extra(data, seconds)`, compute Cash from **base Income** (TycoonCore.lua:677-680) and add it to the **existing income-loop call** (:866): **no new call site** (daily_test.py:4536-4543); never in offline pay (:825) or `baseIncome`. **Fintech:** interest on Cash held, capped at H seconds of base Income. **Biotech:** every N engaged minutes (a visible timer, never a roll) P seconds of base Income. **Gaming:** a graded Timing task (paid through TaskServer.lua:257) starts a launch: Income x L for D minutes, then a cooldown. **Parity:** item Incomes are lowered until each sector is within ±5% of Software per engaged hour, every rung and `LONG_PLAYERS` profile (S3), with no bot or hopper gain (S4, S5).

**Content:** the content bible names 168 things for Software (CONTENT_BIBLE.md:300-361); **its decor is earned** (:261, 268, 278, 280; choice 5, :369), **bought here:** an earned piece goes to `kept`. Per new sector about 185 names and 75 art builds **(estimate)**.

## 3. Plot space (re-verified in the code)

- **Code:** `PLOT_SPACING = 90`, `MAX_PLOTS = 6` (TycoonCore.lua:74, 76); `plotCenter` x = -225 + 90 x (slot - 1), z 150 (:123-126); `Floor` 60 x 60 (:736): z 120-180. Front = +Z (signs, TycoonCore.lua:75, IpoServer.lua:21; spawn :698-700). **Anchor = front-center of the floor, z 180.** VIP Lounge z 57.5-82.5 (ShopServer.lua:35-37, 636-650), its door `Touched` (:683) the only one, a non-VIP inside sent to **z 88** (:839); skyline z 101-107 (PlotArt.lua:699-707).
- **Size:** a shell adds 2.3 per side (BUILDING_PASS_PROPOSAL.md section 3): 90 - W - 4.6 ≥ 6 gives **W = 78**; 180.2 - D - 2.3 ≥ 94 gives **D = 82**. Nested **(estimate)** 60 x 60, 64 x 66, 68 x 70, 72 x 76, 78 x 82; no plot moves; **Baseplate 534+ wide (unverified).** The skyline (`BACKDROP_Z`, PlotVisuals.lua:44) goes; 60 x 60 assumptions go per building (PlotArt.lua:31; PlotVisuals.lua:544, 590-592, 643). **Owner, in Studio (read only):** Baseplate, SpawnLocation, anything at z 85-120 or past x ±225, Terrain, StreamingEnabled.

## 4. The office: placement, inventory, checks, budget, phone

- **Fixed:** Floor (the only solid), spawn lane, signs, incubators (EmployeeServer.lua:37-40), hire spots and desks (:31-35). **Movable or stored:** upgrade props and furniture. An owned upgrade with no `objects` entry and not in `stored` stands at its **default slot** (today's `itemOffset`, TycoonCore.lua:131-135, 189): what older code shows, so nothing disappears when PR 3 ships or after a rollback (older code buys without writing `stored`). Furniture has no default slot. **Move-in (D-A):** `objects` stay; building n+1 contains n; the new area gets the starter set.
- **Inventory** = the ids in `active.stored` plus owned furniture with no entry. A purchase (PR 3 on) adds its id to `stored`, with **"Place now"** (edit mode); `"Store"` adds an id, `"Place"` removes it and writes `objects`. An item left stored **still earns** (Income reads `owned`, TycoonCore.lua:137-145). In PR 3 `buyUpgrade` (:272-288) drops the pop-in (:285) and writes `stored`; the join loop (:811-815) draws every owned upgrade not in `stored`, at its `objects` position or its default slot; the Office tab (ShopClient.lua:496-573) gains "Place now" and "In storage". **The buy is unchanged:** one charge after `checkUpgradePurchase` (:243-270); "Place" never charges.
- **Checks** on `CompanyAction` (`"Place", id, x, z, r`; `"Store"`; `"Sync"`; `"PickSector"`): `data.ready` (IpoServer.lua:212-213); `id` a string under 40 chars, finite `x`/`z`, whole `r` 0-7; ownership; inside the building; overlap ≤ 0.1 stud; no reserved zone (`PlotVisuals.zones`, :504-531); budgets; 4 requests/s. **One pure function in `CompanyConfig`:** the client previews, the server decides. Placement never changes Income; **no `Touched` handler** (daily_test.py:4463-4465).
- **Part budget:** `MAX_PARTS = 260`, `MAX_LIGHTS = 3` (PlotVisuals.lua:39-40); rooms use 244-257 (ROADMAP.md:42), props 118 (daily_test.py:3858). **Proposal:** draw only owned desks, 320 per plot, decided at G-S's phone test.
- **Edit mode:** a window (`OpenPanel = "Office"`) from SHOP > Office; top-down camera, about 3.5 px per stud at 78 x 82 on 667 x 339 **(estimate)**; pick strip, pinch zoom, drag, snap 0.5, one `"Place"` on lift; Rotate, Store, Done 56 px; PC: drag, R, Delete.
- **Funding message and window:** FUND 5.
- **Shop:** Office gains Buildings and Furniture (`"BuyBuilding", n`, `"BuyObject", n` on `ShopAction`, ShopServer.lua:704-717, 802-805), checked like `checkUpgradePurchase` plus "stage n reached" (valuation, raised or not) and "building n-1 owned". **Prices:** before LONG_GAME PR 2, a placeholder in `CompanyConfig.Buildings`: building n costs `floor(IpoConfig.stageValuation(n, ipo.count) x priceBp / 10000)`, `priceBp` 2,500 (450 / 1,575 / 5,850 / 20,250 at IPO 0; looks and a Cash sink only, no Income). From LONG_GAME PR 2 on, its office price (LG:53-58). No odds words (daily_test.py:4553-4560).

## 5. Economy: seed, collection bonus, sims

**5.1 Seed (P-5).** `StartingCash` (0, IpoConfig.lua:44) plus **s% of the old company's Cash, capped at c% of the new first rung's prices** (10 and 25, **placeholders**, S1): a gift (no `addEarnings`), paid once inside the IPO transform.

**5.2 Collection bonus (P-4).** A **Cash multiplier on Income**: +1.5% per Bronze, +0.5% Gold, +0.5% Platinum, **capped at +10%** (**placeholders**, S2), applied with the passes (`updateIncome`, TycoonCore.lua:148-152), **never valuation**, so **0 until LONG_GAME PR 2** (today the income loop, :865-866, and offline pay, :819-827, add the whole Income to it). Never in `baseIncome` (:677-680) or away pay. Stacked: 2x Cash x VIP x 1.10 = x3.3, times the IPO multiplier (no cap, IpoConfig.lua:162-165). **No stamp pays Shares** or changes odds (D9).

**5.3 Risks.** A faster sector becomes the only choice (S3-S5). **Duplicate seed:** paid only in the one transform; `ipoNumber` blocks a repeat (IpoServer.lua:179); a failed save changes nothing (TycoonCore.lua:565-567).

**5.4 Funding rounds:** Cash, valuation, Shares, dilution and exploits are in FUND 2-4.

**5.5 Simulate before any build** (tools/economy_sim.py, new `--pokedex` mode; marks are **placeholders**):
- **S1 seed:** 0 / 10 / 25% cap: ≤ 5% faster per loop; a "decorator" ≤ 5% slower. **S2 bonus:** 0-12 points x pass sets: at the cap ≥ 95% of no-bonus hours. **S3 parity:** every model, profile and rung ±5%. **S4 bots:** no sector faster for a bot. **S5 hopping:** fastest sector vs one, 10 IPOs: < 3%. **S6 tiers:** Gold on ≥ 50% of regular replays, Platinum on ≥ 20% of dedicated ones, pass owners within ±5 points. **S7 board:** new-sector vs replays within 10%; the task-bot never above a dedicated human.
- **S8 round size:** FUND 6.

## 6. Build plan

Each PR: claim its scripts, `python3 tools/daily_test.py` passes, F5 without red errors, publish with **Shut down all servers**; create new modules in Studio first (PUBLISH_RULES 2b). **PR 1 ships the whole `pokedex` format.** PR 2 does not wait for LONG_GAME PR 2 to be built, but its buildings stay Studio only until it (below); PR 4b and 8-16 need it.

**What D-F changes in today's code:**
- **Room from the building.** Today `stageOf`/`syncRoom` (TycoonCore.lua:175-186) pick the room from the valuation stage, on join (`newPlot(..., stageOf(data))`, :810) and every second (:867). New: `roomOf(data)` = `pokedex.active.building` while buildings are active (`CompanyConfig.Buildings.Enabled` and (`StudioOnly` off or Studio), like `TaskConfig.isActive`), else today's `stageOf(data)`, so a live plot never freezes in the Garage; `StudioOnly` stays on until LONG_GAME PR 2's prices. The join builds it; `BuyBuilding` and the IPO (building 1) call `PlotVisuals.setStage`; :867 calls `CompanyServer.onStage` (the round message). The task rung (TaskServer.lua:117) and the IPO sign (IpoServer.lua:66-75) still follow the stage. **PR 2**, with `BuyBuilding`.
- **PlotArt / PlotVisuals:** no `FundingStages` exists in either (only `PlotArt.Stages`, PlotArt.lua:798, read at PlotVisuals.lua:190, 228, 247). `Stages` keeps its name, order and content; only its meaning becomes "room of building i" (comments PlotArt.lua:5, PlotVisuals.lua:16-17). PR 2.
- **Shop Office tab:** Buildings and `"BuyBuilding"` in PR 2 (Furniture in 5-7). Checks that pin the Office as upgrades-only change on purpose (test impact below).
- **Valuation HUD / IpoClient:** FUND 7 (PR 4b).

**Test impact** (daily_test.py lines on `main` `9798388`):
- **Must hold, unchanged:** the fingerprints of stage 1, the props and the layout (:3770, 3778, 3790; the upgrade stations stay the default slots); one `Touched` handler (:4463-4465); new: building i draws exactly `PlotArt.Stages[i]`.
- **PR 1 (`pokedex`):** the exact section list (:4478-4480) gains only `pokedex`; a "pokedex is a known section" check joins :4531 (source) and :664 / :673 (`KNOWN_SECTIONS.tasks` / `.fixedHires` in the BUILDSAVE run, which reads the real line through `known_sections_line`, :4700-4705); :659 ("every section is there") gains `payload.pokedex`. **The save gate** (TycoonCore.lua:481) gains `data.pokedex`, and :4533 looks for the exact text `"data.daily and data.tasks)"`: appending `and data.pokedex` breaks it, so it is rewritten to check both names in the gate.
- **PR 2 (room from the building):** :4667 (the income loop calls `syncRoom`) and :4668 (the room's stage comes from `IpoConfig.stageIndex`) pin "the room follows the stage". They are rewritten to pin `roomOf(data)`; with buildings off the fallback still reads `stageIndex`, so the old text may still match: rewrite them on purpose, never leave them passing by accident. The Office checks :4487-4488 (the handler only calls `core.buyUpgrade(player, id)`) and :4494-4495 (ShopClient sends only `"Upgrades"` and `"BuyUpgrade"`) gain `"BuyBuilding"`.
- **PR 3 (inventory):** :4669 ("a purchase pops its prop in", `spawnItem(data, i, upg, true)`) breaks: a purchase now goes to storage (section 4).
- **PR 4b:** the `addEarnings` checks (:4536-4543) cover every `.lua` file and aliases (FUND 2).
- **PR 5-13:** the D9 word check (:4553-4560) adds CompanyClient, CompanyServer and the sector modules.

1. `pokedex` (full format, missing-section default, run check, versioning); `CompanyServer`, `CompanyConfig`, `SectorConfig` (Software, picker off); `"Place"`/`"Store"`/`"Sync"`. *Tests:* round trip; unknown fields kept at every level; `v = 2`; both run check cases; bad values; overlap, zones, rate, ownership.
2. **The building engine:** `roomOf` and the `Buildings` switch (`StudioOnly` on), `"BuyBuilding"` with placeholder prices, the nesting and move-in rules, the starter set. Buildings 1-5 are today's five 60 x 60 rooms (`PlotArt.Stages`), so every footprint nests trivially. *Tests:* the fingerprints; switch off = today's room; nesting; objects unchanged; budgets; a building before its stage is refused.
3. `CompanyClient` edit mode; the inventory; roof hidden in edit mode. *Tests:* both phone sizes; sends only id, x, z, r; one charge; a stored item earns; an upgrade bought by older code (no entry, not stored) stands at its default slot. *Studio:* buy the Laptop, leave it stored, rejoin, place it.
4. The IPO completes the company: Bronze, card, Pokedex tab, seed (Studio only until S1), picker (Studio only). *Tests:* one transform; Bronze once; seed capped and once; run check.
4b. **Funding rounds:** FUND 7. **Live only after** S8, LONG_GAME PR 2 and PR 3 (R2, R3).
5-7. Software: `SectorSoftware`, `SectorArtSoftware` (keys unchanged), Software's own buildings 2-5 on PR 2's engine (the bigger footprints 64 x 66 to 78 x 82, section 3, and their art), furniture, kept decor, `"BuyObject"`. *Tests:* no sector key in engine; fingerprints; budgets; D9 words.

**G-S, go / no-go:** (a) 6 plots at building 5, full budgets, low-end phone ≥ 30 fps **(estimate)**; (b) 3+ players pick, build, arrange, raise or skip, IPO into a new sector, find the card, unaided; (c) S1, S3, S5, S8 pass; (d) section 3's Studio checks. **No-go: fix before any other sector.**

8-13. Fintech, Biotech, Gaming. *Tests:* parity ±5%, no new `addEarnings` site, D9 words, `id = 0`.
14. Gold, Platinum, stamp clock, pass-share targets, bonus on, Hall of Fame; needs S2, S4, S6.
15. `BoardServer` (exception approved, section 7), FR-11; needs S7.
16. Picker and funding on for live servers; PUBLISH_RULES "2d" (with FUND 4's rollback note); publish.

## 7. Impact on other docs and branches

**Merge order:** `visuals-garage` is now in `main`; a PR from this branch changes only this doc and CONTRIBUTING.md.

**docs/LONG_GAME_PROPOSAL.md** (`LG:` = its line):
- **Principle (LG:5)** "Cash can only fill a rung" holds for every grant here (seed, rounds: FUND 8).
- **Section 3 (LG:38, 53-60):** a building costs its office's fitted price; 7 offices on 5 footprints (Glass Tower and Global HQ become shell upgrades of building 5); each building adds hire spots for the 18 desks; R1 caps (LG:108) follow the 7 office purchases; furniture never enters `LONG_K`; S3 recounts the moments (LG:66-79) per sector.
- **Decor (LG:78, 82, 86, 88, 92):** earned pieces are **kept**; bought copies reset; the Boardroom skin is a pass furniture set; the prestige wing stays perks.
- **Shares and money (LG:86, 92-94):** the `addEarnings` list gains "(8) `CompanyServer` never calls it"; sector models ride entry (1); dilution, pacing and alt feeding: FUND 8. **Section 8 (LG:110-122):** its PR 4 = PR 1-7 here, its PR 7 = PR 8-13; 4b needs its PR 2 and 3.

**Other docs:**
- **`design-tutorial` collides:** both add a section and a module to TycoonCore (`KNOWN_SECTIONS` :84, payload, save gate :481) and daily_test.py:4478-4480, 4533. **`setupPlayer` order:** IpoServer (:793), fixedHires, EmployeeServer (:795), PoachServer, OnboardingServer (:797), **CompanyServer**, TaskServer (:798), **TutorialServer** (TUTORIAL_PROPOSAL.md:106), DailyServer (:799, last); `init` alike; BoardServer's repair runs after `data.ready` (TycoonCore.lua:831). **Tutorial PR A merges first**; Pokedex PR 1 rebases onto it.
- **Tutorial steps** (TUTORIAL_PROPOSAL.md): 1 and 4 (:25, 28) become "own your sector's first upgrade" and "own 2 of this company's upgrades" (step 1 waits while `OpenPanel = "Sector"`). **Step 8 "Funding":** FUND 8. **Step 9** (:33, notes 37-42): resets add buildings, bought furniture, rounds and dilution (FUND 8); keeps add stamps and kept decor. New step: "Arrange your office". The "?" and the strip (:53, 62) are untouched.
- **`content-bible`:** sections 1-6 = Software's package; its industry skins (243-251) go.
- **`building-pass`: park it.** Its patch and BuildingClient.lua are built for 60 x 60, and its roof would block the edit camera. Its shell data and `pcall` plug-in are reused.
- **`visuals-garage`, PLOT_VISUALS.md (14, 37), CLAUDE.md "Plot visuals" (32):** "the plot stays 60 x 60", the skyline, "six props identical in every room", "the real Floor is the only solid" and "`PlotArt.Stages[i]` is the room of `IpoConfig.Stages[i]`" change.
- **CLAUDE.md, README, ROADMAP, PUBLISH_RULES:** `pokedex`, new modules and order, `CompanyRemotes`, "2d" (FUND 8).
- **CLAUDE.md:29 (approved by the owner):** the build PR changes it to exactly: "Never add a second DataStore, save loop or PlayerAdded data owner. One exception: `BoardServer` (ServerScriptService) may use the OrderedDataStores `Collection_v1` and `HallOfFame_v1` (and their `_Studio` twins) for the leaderboard. It writes only values read from the loaded save after that save succeeded, never saves player data, and wraps every call in `pcall`. Every other store stays under this rule."

## 8. Open questions (unresolved, most important first)

1. **Tier rules:** Gold 1.0 T, Platinum 0.8 T plus ratio 1.25, targets shortened by the run's share with each pass and fitted with a typical raise (recommend), or pass-neutral rules?
2. **Collection bonus:** a Cash multiplier, cap 10%, never valuation (recommend), or a cheaper first rung?
3. **Income models:** the mechanics (only if S3-S5 pass) or today's Income with themed text? Fintech rewards holding Cash, against the buy loop: keep it?
4. **Earned decor:** which milestones unlock which kept piece (content bible choice 5), and what Day 7 gives once its list is all kept?
5. **Leaderboard:** Collection plus Hall of Fame (recommend), or also a fastest-Platinum board per sector?
6. **78 x 82 enough,** or move the plots (`PLOT_SPACING` 112)? Decide at G-S.

## What I did not verify

- The world outside scripts (Baseplate, SpawnLocation, hand-placed parts, Terrain, StreamingEnabled): no Studio or MCP was used.
- "0 visits" and the privacy setting (Creator Hub only); OrderedDataStore and `UserService` limits; camera scale; phone frame rates; why `MAX_PARTS` is 260.
- Every economy number and content estimate: placeholders or estimates; no sim was run. Roblox's real top bar height is not measured.
- Other branches were read with `git show`, not run; LONG_GAME PR 2 doesn't exist; `daily_test.py` was not run (docs only).
