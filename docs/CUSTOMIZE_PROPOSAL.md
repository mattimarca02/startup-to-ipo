# Companies, sectors and the Pokedex (proposal, design only)

Design only (2026-10-04, branch `design-customize`; revised after two reviews and, 2026-10-05, for D-F, funding rounds, docs/FUNDING_ROUNDS_PROPOSAL.md (`FUND`), and D-G, the two launch sectors, docs/SECTORS_PROPOSAL.md (`SECT`)). No script, config or test changed. Line numbers: this branch with `main` `9798388` merged, re-checked 2026-10-05. **(unverified)** = not checked in code; **(estimate)** = not measured; **(placeholder)** = sized by the sims.

**Fixed by the owner:** **D-A** a bigger building contains the previous one; objects move in at the same coordinates from a door-side anchor. **D-B** an IPO founds a new company, seeded with some of the old one's money (never items). **D-C** every founding starts with picking a sector. **D-D** a sector is a full package on one engine. **D-G (2026-10-05): two sectors launch, Software (today) and Gaming,** each with its own gameplay, everything tied to the real field; **Fintech and Biotech are post-launch updates** (section 6). **D-E** free placement, phone and PC. **P-1** one Pokedex entry per sector. **P-2** an IPO completes the company and stamps its sector; the old company becomes a card. **P-3** both launch sectors = the main goal at launch (Hall of Fame); then replays earn Gold and Platinum, and a leaderboard; a later sector adds a goal (1.5). **P-4** old companies earn nothing; stamps give a small capped bonus. **P-5** the seed stays. **CLAUDE.md:29 exception approved:** `BoardServer` alone may use the leaderboard OrderedDataStores (section 7). **Inventory:** a purchase goes to the inventory, with "Place now". **D-F funding rounds:** a stage reached by valuation opens a round of a size the player picks: Cash only (a gift, never `addEarnings`, decided 2026-10-05), paid for with dilution; the room follows the building owned (1.7, section 6).

**Owner defaults** (the owner may veto): employees follow the player; creatures keep bodies, renamed per sector; **P-6** 5 buildings per sector (building 5 serves Series C+D to IPO-ready); any sector can be picked next; an unplaced item still earns; largest size **78 x 82**; hire desks fixed in v1; furniture earns nothing; a free, fixed starter set per building (D9); 45° rotation; part budget open until a phone test.

**New names** (none exists in any `.lua`/`.py`): `CompanyServer` (owns `pokedex`; `raiseRound`), `CompanyConfig` (with `Funding`), `SectorConfig`, `Sector<Name>`, `SectorArt<Name>`, `CompanyClient`, `CompanyRemotes.CompanyAction`, `BoardServer`, OrderedDataStores `Collection_v1`, `HallOfFame_v1`.

## 1. Companies, sectors and the Pokedex

**1.1 A company** is one run of one sector's ladder: Cash, upgrades, buildings, furniture, layout, eggs in incubators, valuation, funding rounds and dilution. **The player** keeps employees, HR level, passes, boosts, shields, Shares, perks, IPO count and multiplier, `lifetime`/`best`, daily, onboarding, task stats, the Pokedex, kept decor (today's rule: IpoConfig.lua:6-8, 51).

**1.2 The `pokedex` save section (new top-level section, A10).** The active company's live state stays where it is (`cash`, `owned`, `team`, `ipo.valuation`; TycoonCore.lua:421-433), so older code keeps playing it; the section holds the rest:

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
    told = { [stageKey] = true },       -- round message sent (FUND 1)
    rounds = { [stageKey] = { s = "raised" or "skipped", c = choice, cash = n, bp = n, at = os.time(), studio = boolean } },
    sx = { ... },            -- the sector's own state (SECT 0; Gaming: SECT 2.2), {} for Software
  },
  sectors = {                -- keys Software, Gaming, Fintech, Biotech known from PR 1; no entry = not started
    [sectorKey] = {
      state = "progress" or "done",  -- "done" never goes back
      stamp = 0 to 3,        -- best: 1 Bronze, 2 Gold, 3 Platinum
      replays = number, firstAt = os.time(), bestEngaged = number,
      card = { name, ipoNumber, at, engaged, ratio, building, owned = {...}, decor, objects, rounds, stake, shares, sx },
    },
  },
  kept = { [objectKey] = n },  -- earned decor: free in every company
  hall = { [goalKey] = os.time() },  -- goals done (1.5): "Launch" = Software and Gaming
  dust = number,             -- Shares remainder in 1/10000 Share, -5000 to 4999 (FUND 3)
  studio = boolean,          -- saved by a Studio server: never on the live board
}
```

- **Fields:** `id` = an upgrade name or `<objectKey>#<n>`; `x`, `z` from the anchor, step 0.5; `r` 0-7; at most 40. An owned upgrade with no entry stands at its default slot; furniture with no entry and ids in `stored` (at most 40) are in the inventory (section 4). `ratio` = IPO valuation / IPO-ready valuation. `sx` is the sector module's (`load` checks it; bad = `{}`, a warning). **Four sector keys from day one:** Fintech and Biotech need no new field later; before their update an entry under them (a Studio test) is kept, never picked, and counts for no goal or board. About 11 KB **(estimate)**.
- **Loader: KEEP unknown fields,** like onboarding (OnboardingServer.lua:226, 243, 281), daily (DailyServer.lua:244, 261, 290), tasks (TaskServer.lua:712, 766, 800), fixedHires (EmployeeServer.lua:657, 675, 694), but at **every** level: the section, `active`, `decor`, `passSeconds`, `objects[i]`, `stored`, `told`, `rounds`, `rounds[k]`, `sectors` (unknown sector keys kept whole), `sectors[k]`, `card`, `card.owned` (unknown upgrade names), `card.decor`, `card.objects[i]`, `card.rounds[k]`, `kept`, `hall`; `sx` and `card.sx` are kept whole. In the maps (`decor`, `kept`, `passSeconds`, `card.decor`, `hall`) an unknown key keeps its value (code without this rule drops them). Those four keep top-level fields only; shop, team, poach, ipo none (EmployeeServer.lua:648).
- **Versioning:** `v` rises only when a field changes meaning; a higher `v` is kept opaque and unchanged; the session refuses `GoPublic`, `Place`, `BuyBuilding`, `PickSector`, `Raise`; with an unknown sector key `BoardServer` writes nothing. *Tests:* `v = 2` deep-equal after a save; each refusal.
- **Bad values** (type, NaN, infinite, negative, out of range, unknown or duplicate id) are skipped with a warning; `stamp` clamped; `"done"` with stamp 0 becomes 1. Rounds: FUND 1.
- **Wiring:** `KNOWN_SECTIONS` (TycoonCore.lua:84), `buildPayload` (:421-433), save gate (:481); section 6's test impact, same PR. Shut down all servers; rollback floor `V_launch` (M4+ code keeps unknown sections, TycoonCore.lua:773-777, 434-438).
- **No legacy migration:** nothing launched (PUBLISH_RULES.md:17, 101); test accounts are wiped first (`RemoveAsync` on a written list, :111). **A missing `pokedex`** = a new founding: `run = ipo.count`, Software, `picked = true` while the picker is off, building 1.
- **A10 run check.** (1) **`run < ipo.count`:** an older version ran an IPO (TycoonCore.lua:549-559; no seed, no dilution, `pokedex` frozen). IPOs need the valuation (IpoServer.lua:192-195): the sector gets `"done"`, Bronze if unstamped and a card (`rounds` unchanged); the new company: same sector, `picked = false`, building 1, `run = ipo.count`. (2) **`run > ipo.count`:** never an IPO. Only Debug **IpoReset** lowers the count (`count = 0`, IpoServer.lua:426; Studio only, :456); a restored DataStore version brings `pokedex` back with `ipo` (one key, TycoonCore.lua:505). So: `run = ipo.count`, `active` kept (settled rounds stay settled), no stamp, card or bonus, `studio = true`, a warning (an IPO here would be a free Bronze, carried to live by the shared save key, PUBLISH_RULES.md:46; `studio` blocks the board, not the bonus, 5.2). A damaged `ipo` read as count 0 lands here too (board off: safe). *Tests:* IpoReset then rejoin: no stamp, no card, rounds unchanged, `studio` set; `run` 2 with `count` 3: Bronze and card once.

**1.3 Picking a sector, on every founding.** A window (`OpenPanel = "Sector"`) with four cards: Software and Gaming (icon, name, how it makes money, stamp, "New"); Fintech and Biotech greyed **"Coming soon"** (not tappable, no date). Shown to new players, in every IPO and after run check case (1). `CompanyAction("PickSector", key)` only while `picked == false`, only an enabled sector (`SectorConfig`), the same included; the picker preselects one not yet done (after both: the lower stamp). `SectorConfig.PickerEnabled = false` until both launch sectors exist.

**1.4 The IPO completes the company.** Today `goPublic` (IpoServer.lua:177-243) checks, then `commitIpo` (TycoonCore.lua:544-588) saves a transform resetting Cash, `owned` and eggs (IpoConfig.lua:53-58). New:
1. The picker before Confirm; `IpoAction("GoPublic", ipoNumber, sectorKey)` adds a sector check to `ipoNumber == count + 1` (IpoServer.lua:179).
2. **One transform, one save** (TycoonCore.lua:548-564): `"done"`, `stamp = max(stamp, earned)`, `replays`, `firstAt`, `bestEngaged`, the `card`; `hall.Launch` when both launch sectors are done; a new `active` (building 1, no rounds); `run = count + 1`; Cash = `StartingCash` + seed.
3. Only after that save (:565-587): the Garage room, a stamp pop-up, the board write.

**The card**, in a new **Pokedex** tab of the IPO window (IpoClient.lua:354): sector, name, stamp, IPO number, date, engaged hours, ratio, founder stake, a **top-down map** (Frames per footprint). `ResetNames` (IpoConfig.lua:60-65) and the keep list (IpoClient.lua:524-533) add buildings, furniture, stamps, rounds.

**1.5 Stamps, replays, Hall of Fame.**
- **Bronze:** first completion, bonus +1.5%; **no time, ratio or stake condition**. **Gold:** a replay within **1.0 T** engaged hours (ratio ≥ 1, which any IPO has) **and a founder stake of at least 55%**, +0.5%. **Platinum:** within **0.8 T** at ratio **≥ 1.25** **and a stake of at least 70%**, +0.5%. **Stake** = 10,000 bp minus the total dilution at the IPO (decided 2026-10-05; FUND 3, "The founder stake counts for stamps"). **T** = a regular player's loop hours (LONG_GAME section 1: 57 / 51.5 / 52 h, both sectors while parity holds); all **placeholders** (S6, S8). The server's clock, weighted like the valuation (LONG_GAME_PROPOSAL.md:23): Gold and Platinum wait for LONG_GAME PR 2. The tier = the highest whose conditions all hold, graded **once, in the IPO transform** (1.4), from the saved `rounds`' `bp`; the client sends nothing; never regraded. Fast enough for Platinum but under 70% = Gold. FUND's 4,000 bp cap keeps the stake ≥ 60%: Gold's 55% cannot fail today.
- **Pass fairness:** 2x Cash shortens a run about 15% (LONG_GAME section 6): a target shrinks by that times the **share of the run's engaged seconds with the pass** (`passSeconds`), never by passes owned at founding (exploitable). A replay is priced by IPO count only.
- **Hall of Fame, the launch goal:** Software and Gaming `"done"`: `hall.Launch`, a title, a gold frame, a board entry. From IPO 3 on, every IPO is a replay: Gold, Platinum and the board carry the game.
- **When a sector is added later** (Fintech, Biotech): `SectorConfig.Goals` lists each goal's sectors; a shipped list never changes. `hall.Launch` stays earned with its board; a new goal key (say `Four`) brings its own title and frame; the new sector shows "New"; Collection grows by itself. A board per later goal needs another named store (CLAUDE.md:29): recommend none.

**1.6 Leaderboard.** Today in-server only (IpoServer.lua:46-63; IpoClient.lua:750-786); no OrderedDataStore exists (docs/reviews/FULL_REVIEW.md:126).
- **Ranks:** **Collection** = `1000 x stamp points + min(IPO count, 999)` (Bronze 1, Gold 2, Platinum 3); **Hall of Fame** = earliest `hall.Launch`. `BoardServer` writes `Collection_v1`, `HallOfFame_v1` (in `pcall`, key UserId) from the loaded `pokedex` after the stamp's save, repairs a lower value on join, reads the top 50 every 10 minutes. No client sends a score.
- **Studio never reaches the live board.** Studio and live share the save key (PUBLISH_RULES.md:46): every Studio save sets `pokedex.studio = true` (never cleared); a `studio` account is never written, repaired or shown; Studio writes only `_Studio` twins; a deny list (`BoardServer.REMOVED`) is never written or shown. *Test (fake stores):* a `studio` save with two Platinum joins live: no write.
- **Names (FR-11):** `UserService:GetUserInfosByUserIdsAsync` (`pcall`, cached; **limits unverified**); the client escapes `& < > " '` (fixes IpoClient.lua:780).

**1.7 Funding rounds (D-F).** One round per stage per company, saved in `active.told`/`rounds` and on the card (1.2). Rules, economy, dilution, exploits, tests, UI, S8, PR 4b: **FUND**.

## 2. The sector package and content

**Shared engine** (never names a sector; a test fails on a sector key in engine code): `pokedex`, picker, IPO flow, stamps, seed, bonus, funding rounds, board; buildings, placement, inventory; SHOP > Office; tasks; creatures, eggs, odds, `fixedHire` (D9), poaching; daily, onboarding, HUD; the economy clock; the sim. Sector hooks: SECT 0.

**Per sector** (`Sector<Name>`, `SectorArt<Name>`): key, name, icon, palette, 12+ company names; 5 buildings; upgrades (keys never reused; Software keeps today's six, TycoonCore.lua:65-72); furniture; tasks (`TaskConfig.Rows`, TaskConfig.lua:49); creature names and jobs (CreatureConfig.lua:53-104); egg names; an income model; fixed-content bundles, `id = 0`; art in PlotArt's `P(...)` format (PlotArt.lua:9-23).

**Income** (deterministic, capped, engaged only; **placeholders**; SECT 1.3, 2.4). **Software:** steady Income, `extra` = 0. **Gaming:** base Income plus a launched game's revenue, `SectorGaming.extra(data, seconds)`, from **base Income** (TycoonCore.lua:677-680), added to the **existing income-loop call** (:866): **no new call site** (daily_test.py:4536-4543); never in offline pay (:825) or `baseIncome`. The launch tier is a visible score, never a roll (SECT 2.3). **Parity:** Gaming's upgrade Incomes are lowered to within ±5% of Software per engaged hour, every rung and `LONG_PLAYERS` profile (S3), with no bot or hopper gain (S4, S5).

**Content.** The content bible names 168 things (CONTENT_BIBLE.md:300-361): 154 Software's own, 14 shared cosmetics (4 hats, 9 skins, 1 tag); **its decor is earned** (:261, 268, 278, 280; choice 5, :369), **bought here:** an earned piece goes to `kept`.

| | Software | Gaming | Shared | Launch |
|---|---|---|---|---|
| Names | 165 (153 + 12 company names) | ~214 **(estimate)** | 10 (9 cosmetics, the 5 industry skins go; Night Guard) | **~389** |
| Art builds | ~75 **(estimate)** | ~75 **(estimate)** | | **~150** |
| Task rows | 18 (+28 tiers, LG:74) | 7 (+ tiers) **(estimate)** | | 25 |

Gaming's ~214 = Software's 153 kinds + 6 genres, 36 game names, 7 task names, 12 company names (SECT 5). Adding Fintech and Biotech later: ~723 names (168 + 3 x 185), ~300 builds (4 x 75).

## 3. Plot space (re-verified in the code)

- **Code:** `PLOT_SPACING = 90`, `MAX_PLOTS = 6` (TycoonCore.lua:74, 76); `plotCenter` x = -225 + 90 x (slot - 1), z 150 (:123-126); `Floor` 60 x 60 (:736): z 120-180. Front = +Z (TycoonCore.lua:75, IpoServer.lua:21; spawn :698-700). **Anchor = floor front-center, z 180.** VIP Lounge z 57.5-82.5 (ShopServer.lua:35-37, 636-650), its door `Touched` (:683) the only one, a non-VIP sent to **z 88** (:839); skyline z 101-107 (PlotArt.lua:699-707).
- **Size:** a shell adds 2.3 per side (BUILDING_PASS_PROPOSAL.md section 3): 90 - W - 4.6 ≥ 6 gives **W = 78**; 180.2 - D - 2.3 ≥ 94 gives **D = 82**. Nested **(estimate)** 60 x 60, 64 x 66, 68 x 70, 72 x 76, 78 x 82; no plot moves; **Baseplate 534+ wide (unverified).** The skyline (`BACKDROP_Z`, PlotVisuals.lua:44) and 60 x 60 assumptions (PlotArt.lua:31; PlotVisuals.lua:544, 590-592, 643) go. **Owner checks in Studio (read only):** Baseplate, SpawnLocation, anything at z 85-120 or past x ±225, Terrain, StreamingEnabled.

## 4. The office: placement, inventory, checks, budget, phone

- **Fixed:** Floor (the only solid), spawn lane, signs, incubators (EmployeeServer.lua:37-40), hire spots and desks (:31-35). **Movable or stored:** upgrade props, furniture. An owned upgrade with no `objects` entry, not in `stored`, stands at its **default slot** (today's `itemOffset`, TycoonCore.lua:131-135, 189), as older code shows it (it buys without writing `stored`): nothing disappears when PR 3 ships or after a rollback. Furniture has none. **Move-in (D-A):** `objects` stay; building n+1 contains n; the new area gets the starter set.
- **Inventory** = ids in `active.stored` plus owned furniture with no entry. A purchase (PR 3 on) adds its id to `stored`, with **"Place now"** (edit mode); `"Store"` adds an id, `"Place"` removes it and writes `objects`. Stored items **still earn** (Income reads `owned`, TycoonCore.lua:137-145). In PR 3 `buyUpgrade` (:272-288) drops the pop-in (:285) and writes `stored`; the join loop (:811-815) draws every owned upgrade not stored, at its `objects` position or default slot; the Office tab (ShopClient.lua:496-573) gains "Place now" and "In storage". **The buy is unchanged:** one charge after `checkUpgradePurchase` (:243-270); "Place" is free.
- **Checks** on `CompanyAction` (`"Place", id, x, z, r`; `"Store"`; `"Sync"`; `"PickSector"`): `data.ready` (IpoServer.lua:212-213); `id` a string under 40 chars, finite `x`/`z`, whole `r` 0-7; ownership; inside the building; overlap ≤ 0.1 stud; no reserved zone (`PlotVisuals.zones`, :504-531); budgets; 4 requests/s. **One pure function in `CompanyConfig`:** the client previews, the server decides. Placement never changes Income; **no `Touched` handler** (daily_test.py:4463-4465).
- **Part budget:** `MAX_PARTS = 260`, `MAX_LIGHTS = 3` (PlotVisuals.lua:39-40); rooms use 244-257 (ROADMAP.md:42), props 118 (daily_test.py:3858). **Proposal:** draw only owned desks, 320 per plot, decided at G-S.
- **Edit mode:** a window (`OpenPanel = "Office"`) from SHOP > Office: top-down camera, about 3.5 px per stud at 78 x 82 on 667 x 339 **(estimate)**; pick strip, pinch zoom, drag, snap 0.5, one `"Place"` on lift; Rotate, Store, Done 56 px; PC: drag, R, Delete. Funding window: FUND 5.
- **Shop:** Office gains Buildings and Furniture (`"BuyBuilding", n`, `"BuyObject", n` on `ShopAction`, ShopServer.lua:704-717, 802-805), checked like `checkUpgradePurchase` plus "stage n reached" (raised or not) and "building n-1 owned". **Prices:** until LONG_GAME PR 2, a placeholder in `CompanyConfig.Buildings`: `floor(IpoConfig.stageValuation(n, ipo.count) x priceBp / 10000)`, `priceBp` 2,500 (450 / 1,575 / 5,850 / 20,250 at IPO 0; looks and a Cash sink only); then its office price (LG:53-58). No odds words (daily_test.py:4553-4560).

## 5. Economy: seed, collection bonus, sims

**5.1 Seed (P-5).** `StartingCash` (0, IpoConfig.lua:44) plus **s% of the old company's Cash, capped at c% of the new first rung's prices** (10 and 25, **placeholders**, S1): a gift (no `addEarnings`), paid once in the IPO transform.

**5.2 Collection bonus (P-4).** A **Cash multiplier on Income**: +1.5% per Bronze, +0.5% Gold, +0.5% Platinum, **capped at +10%** (two sectors reach +5%; the cap is for later ones; **placeholders**, S2), applied with the passes (`updateIncome`, TycoonCore.lua:148-152), **never valuation**, so **0 until LONG_GAME PR 2** (today the income loop, :865-866, and offline pay, :819-827, add all Income to it). Never in `baseIncome` (:677-680) or away pay. Stacked: 2x Cash x VIP x 1.10 = x3.3, times the IPO multiplier (no cap, IpoConfig.lua:162-165). **No stamp pays Shares** or changes odds (D9).

**5.3 Risks.** A faster sector becomes the only choice (S3-S5). **Duplicate seed:** paid only in the one transform; `ipoNumber` blocks a repeat (IpoServer.lua:179); a failed save changes nothing (TycoonCore.lua:565-567). **5.4 Funding rounds:** FUND 2-4.

**5.5 Simulate before any build** (tools/economy_sim.py, new `--pokedex` mode; marks are **placeholders**):
- **S1 seed:** 0 / 10 / 25% cap: ≤ 5% faster per loop; a "decorator" ≤ 5% slower. **S2 bonus:** 0-12 points x pass sets: at the cap ≥ 95% of no-bonus hours. **S3 parity:** Software and Gaming, every profile and rung ±5%. **S4 bots:** no sector faster for a bot. **S5 hopping:** alternating vs one sector, 10 IPOs: < 3%. **S6 tiers:** (time, ratio and stake) Gold on ≥ 50% of regular replays, Platinum on ≥ 20% of dedicated ones, pass owners within ±5 points. **S7 board:** new-sector vs replays within 10%; the task-bot never above a dedicated human. **S9 launch policy, S10 cadence:** SECT 4.
- **S8 round size:** FUND 6 (both sectors; also speed versus tier lost on stake).

## 6. Build plan

Each PR: claim its scripts, `python3 tools/daily_test.py` passes, F5 without red errors, publish with **Shut down all servers**; new modules created in Studio first (PUBLISH_RULES 2b). **PR 1 ships the whole `pokedex` format.** PR 2 doesn't wait for LONG_GAME PR 2, but its buildings stay Studio only until it; PR 4b and 8-14 need it.

**What D-F changes in today's code:**
- **Room from the building (PR 2).** Today `stageOf`/`syncRoom` (TycoonCore.lua:175-186) pick the room from the valuation stage, on join (:810) and every second (:867). New: `roomOf(data)` = `pokedex.active.building` while buildings are active (`CompanyConfig.Buildings.Enabled` and (`StudioOnly` off or Studio), like `TaskConfig.isActive`), else `stageOf(data)`: a live plot never freezes in the Garage. `BuyBuilding` and the IPO (building 1) call `PlotVisuals.setStage`; :867 calls `CompanyServer.onStage` (the round message). The task rung (TaskServer.lua:117) and the IPO sign (IpoServer.lua:66-75) still follow the stage.
- **PlotArt / PlotVisuals (PR 2):** `PlotArt.Stages` (PlotArt.lua:798, read at PlotVisuals.lua:190, 228, 247; no `FundingStages` exists) keeps name, order and content, now meaning "room of building i" (comments PlotArt.lua:5, PlotVisuals.lua:16-17).
- **Valuation HUD / IpoClient:** FUND 7 (PR 4b).
- **Notes from the PR 1 review fix (docs/CUSTOMIZE_PR1_NOTES.md, "Review fix notes"):** PR 2 must key `zonesCache` in `CompanyServer` by building (it is computed once from the 60 x 60 layout, so a bigger building would still be checked against the first room's zones). PR 3 must decide what to do with saved layouts over the part budget (PR 1 saves up to 40 items and measures no parts). PR 4 must accept a saved company name that isn't in `SectorConfig`'s list (PR 1 gives every company "Garage Labs", the first placeholder) and must stop "run follows the IPO count" being the rule once its IPO transform exists (stamps, cards).

**Test impact** (daily_test.py lines on `main` `9798388`):
- **Must hold:** the fingerprints of stage 1, props and layout (:3770, 3778, 3790; upgrade stations stay the default slots); one `Touched` handler (:4463-4465); new: building i draws exactly `PlotArt.Stages[i]`.
- **PR 1:** the section list (:4478-4480) gains only `pokedex`; "pokedex is a known section" joins :4531 and :664 / :673 (BUILDSAVE, via `known_sections_line`, :4700-4705); :659 gains `payload.pokedex`. **The save gate** (TycoonCore.lua:481) gains `data.pokedex`; :4533 matches the exact text `"data.daily and data.tasks)"`, which appending `and data.pokedex` breaks, so it is rewritten to check both names.
- **PR 2:** :4667-4668 (the income loop's `syncRoom`, the room from `IpoConfig.stageIndex`) are rewritten on purpose to pin `roomOf(data)` (the fallback may still match: never pass by accident). The Office checks :4487-4488 (the handler only calls `core.buyUpgrade`) and :4494-4495 (ShopClient sends only `"Upgrades"`, `"BuyUpgrade"`) gain `"BuyBuilding"`.
- **PR 3:** :4669 (`spawnItem(data, i, upg, true)`, a purchase pops in) breaks: purchases go to storage.
- **PR 4b:** the `addEarnings` checks (:4536-4543) cover every `.lua` file and aliases (FUND 2).
- **PR 5-11:** the D9 word check (:4553-4560) adds CompanyClient, CompanyServer and the sector modules; the TycoonCore `addEarnings` count (:4537) stays 3 (Gaming rides :866).

**Engine (PR 1-3)**
1. `pokedex` (full format with all sector keys, `sx`, `hall`; missing-section default, run check, versioning); `CompanyServer`, `CompanyConfig`, `SectorConfig` (Software enabled; Gaming, Fintech, Biotech listed, not enabled; picker off); `"Place"`/`"Store"`/`"Sync"`. *Tests:* round trip; unknown fields kept at every level; `v = 2`; both run check cases; bad values; overlap, zones, rate, ownership.
2. **The building engine:** `roomOf` and the `Buildings` switch (`StudioOnly` on), `"BuyBuilding"` with placeholder prices, nesting, move-in, the starter set. Buildings 1-5 are today's five 60 x 60 rooms (`PlotArt.Stages`): nesting is trivial. *Tests:* the fingerprints; switch off = today's room; nesting; objects unchanged; budgets; a building before its stage is refused.
3. `CompanyClient` edit mode; the inventory; roof hidden in edit mode. *Tests:* both phone sizes; sends only id, x, z, r; one charge; a stored item earns; an upgrade bought by older code stands at its default slot. *Studio:* buy the Laptop, leave it stored, rejoin, place it.

**Pokedex and picker (PR 4, 4b)**
4. The IPO completes the company: Bronze, card, Pokedex tab, seed (Studio only until S1), picker (Studio only; Software selectable, the rest "Coming soon"). *Tests:* one transform; Bronze once; seed capped and once; run check; a disabled sector's `PickSector` refused.
4b. **Funding rounds:** FUND 7; **live only after** S8, LONG_GAME PR 2 and 3 (R2, R3).

**Software vertical slice (PR 5-7)**
5-7. `SectorSoftware`, `SectorArtSoftware` (keys unchanged), Software's own buildings 2-5 on PR 2's engine (64 x 66 to 78 x 82, section 3, and their art), furniture, kept decor, `"BuyObject"`. *Tests:* no sector key in engine; fingerprints; budgets; D9 words.

**G-S, go / no-go after the Software slice:** (a) 6 plots at building 5, full budgets, low-end phone ≥ 30 fps **(estimate)**; (b) 3+ players build, arrange, raise or skip, IPO, replay, find the card, unaided; (c) S1, S5, S8 pass for Software, S3 within ±5% of LONG_GAME's hours; (d) section 3's Studio checks. **No-go: fix before Gaming work.**

**Gaming (PR 8-11)**
8. **Sector hooks and a Gaming greybox** (Studio only, SECT 0, 2): `extra` on the :866 call, `sx`, `CompanyAction("Sector", ...)`, `onTask`, Gaming's task rows, a plain Project window, placeholder names and art. *Tests:* TycoonCore still has 3 `addEarnings` calls; extra only while engaged; the Forecast equals the server's score; verbs never set engaged; D9 words.

**G-G, go / no-go before Gaming content:** (a) S3 (Gaming within ±5%), S9 and S10 pass on fitted numbers (SECT 4); (b) a Studio playtest: 3+ players each finish two titles unaided, say the tier before launching, and choose between shipping and polishing; (c) the Project window fits 667 x 339 and 320 x 532; (d) Gaming's content bible approved (SECT 5). **No-go: refit or redesign the cycle first.**

9-11. `SectorGaming`, `SectorArtGaming`: 5 buildings, upgrades, desks, furniture, decor, names, bundles (`id = 0`); the picker shows Gaming. *Tests:* parity ±5%, no new `addEarnings` site, no sector key in engine, budgets, D9 words, `id = 0`.

**Tiers and the leaderboard (PR 12-13), then launch (PR 14)**
12. Gold, Platinum, stamp clock, pass-share targets, stake minimums, bonus on, Hall of Fame (`hall.Launch`); needs S2, S4, S6, S8 for both sectors. *Tests:* a run at the time target but under the stake minimum misses the tier; the tier uses the stake at the IPO, never a later one (config change, Debug, rejoin); Bronze never requires a stake; exactly 7,000 bp keeps Platinum, 6,999 does not (FUND 3).
13. `BoardServer` (exception approved, section 7), FR-11; needs S7.
14. Picker (two sectors) and funding on for live servers; PUBLISH_RULES "2d" (with FUND 4's rollback note); publish.

**Post-launch: Fintech and Biotech**, each a sector update in its own PRs: the same package, **no new save field** (keys in `pokedex.sectors` from PR 1), `SectorConfig` enables it, a new goal key (1.5), S3-S5 rerun, its content bible, D9 words, `id = 0`; publish with Shut down all servers as always. Income sketches (deterministic, capped, engaged only, on the :866 call): **Fintech:** interest on Cash held, capped at H seconds of base Income (rewards holding Cash, against the buy loop: revisit). **Biotech:** every N engaged minutes (a visible timer, never a roll) P seconds of base Income.

## 7. Impact on other docs and branches

**Merge order:** this branch changes only the proposals and CONTRIBUTING.md.

**docs/LONG_GAME_PROPOSAL.md** (`LG:` = its line):
- **Principle (LG:5)** "Cash can only fill a rung" holds for every grant (seed; rounds: FUND 8).
- **Section 3 (LG:38, 53-60):** a building costs its office's fitted price; 7 offices on 5 footprints (Glass Tower, Global HQ: shell upgrades of building 5); buildings add hire spots for 18 desks; R1 caps (LG:108) follow the office purchases; furniture never enters `LONG_K`; S3 recounts the moments (LG:66-79) per sector.
- **Decor (LG:78, 82, 86, 88, 92):** earned pieces are **kept**; bought copies reset; the Boardroom skin is a pass furniture set; the prestige wing stays perks.
- **Money (LG:86, 92-94):** the `addEarnings` list gains "(8) `CompanyServer` never calls it"; Gaming rides entry (1); rounds: FUND 8. **Section 8 (LG:110-122):** its PR 4 = PR 1-7 here, its PR 7 = PR 8-11; 4b needs its PR 2 and 3. Hours and stamps per sector: SECT 5.

**Other docs:**
- **`design-tutorial` collides:** both add a section and a module to TycoonCore (`KNOWN_SECTIONS` :84, payload, save gate :481) and daily_test.py:4478-4480, 4533. **`setupPlayer` order:** IpoServer (:793), fixedHires, EmployeeServer (:795), PoachServer, OnboardingServer (:797), **CompanyServer**, TaskServer (:798), **TutorialServer** (TUTORIAL_PROPOSAL.md:106), DailyServer (:799, last); `init` alike; BoardServer's repair runs after `data.ready` (TycoonCore.lua:831). **Tutorial PR A merges first**; Pokedex PR 1 rebases.
- **Tutorial steps** (TUTORIAL_PROPOSAL.md) 1 and 4 (:25, 28) become "own your sector's first upgrade" and "own 2 of this company's upgrades" (step 1 waits while `OpenPanel = "Sector"`). **Step 8:** FUND 8. **Step 9** (:33, :37-42): resets add buildings, bought furniture, rounds and dilution; keeps add stamps and kept decor. New step: "Arrange your office". The "?" and the strip (:53, 62) are untouched. Step 5 and Gaming's two steps: SECT 5.
- **`content-bible`:** sections 1-6 = Software's package; its industry skins (247) go; Gaming's lists (about 214 names): SECT 5.
- **`building-pass`: park it.** Its patch and BuildingClient.lua assume 60 x 60, and its roof would block the edit camera; its shell data and `pcall` plug-in are reused.
- **`visuals-garage`, PLOT_VISUALS.md (14, 37), CLAUDE.md "Plot visuals" (32):** "the plot stays 60 x 60", the skyline, "six props identical in every room", "the real Floor is the only solid" and "`PlotArt.Stages[i]` is the room of `IpoConfig.Stages[i]`" change.
- **CLAUDE.md, README, ROADMAP, PUBLISH_RULES:** `pokedex`, new modules and order, `CompanyRemotes`, "2d" (FUND 8).
- **CLAUDE.md:29 (approved by the owner):** the build PR changes it to exactly: "Never add a second DataStore, save loop or PlayerAdded data owner. One exception: `BoardServer` (ServerScriptService) may use the OrderedDataStores `Collection_v1` and `HallOfFame_v1` (and their `_Studio` twins) for the leaderboard. It writes only values read from the loaded save after that save succeeded, never saves player data, and wraps every call in `pcall`. Every other store stays under this rule."

## 8. Open questions (unresolved, most important first)

1. **Tier rules:** Gold 1.0 T plus stake 55%, Platinum 0.8 T plus ratio 1.25 plus stake 70% (stake decided, numbers S8's), targets shortened by the run's share with each pass and fitted with a typical raise (recommend), or pass-neutral rules?
2. **Collection bonus:** a Cash multiplier, never valuation, capped at 10% (two sectors reach half; recommend), or a cheaper first rung?
3. **Leaderboard:** Collection plus the launch Hall of Fame (recommend), or also a fastest-Platinum board per sector, or a board per later goal (each a new named store, 1.5)?
4. **Earned decor:** which milestones unlock which kept piece (content bible choice 5), and what Day 7 gives once its list is all kept?
5. **78 x 82 enough,** or move the plots (`PLOT_SPACING` 112)? Decide at G-S.
6. **Gaming's own questions** (fallback if G-G fails, Project window, words): SECT 6.

## What I did not verify

- The world outside scripts (section 3's Studio checks, hand-placed parts): no Studio or MCP was used. "0 visits" and the privacy setting (Creator Hub only); OrderedDataStore and `UserService` limits; camera scale; phone frame rates; why `MAX_PARTS` is 260; Roblox's real top bar height.
- No sim was run: every economy number, the stake minimums (FUND 3, 6), the content counts and Gaming's numbers (SECT) are placeholders or estimates; no tier or Gaming code exists.
- Other branches were read with `git show`, not run; LONG_GAME PR 2 doesn't exist; `daily_test.py` was not run (docs only).
