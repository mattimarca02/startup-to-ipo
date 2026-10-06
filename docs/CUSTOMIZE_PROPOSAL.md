# Companies, sectors and the Pokedex (proposal, design only)

Design only (2026-10-04, branch `design-customize`; revised 2026-10-05 for D-F (docs/FUNDING_ROUNDS_PROPOSAL.md, `FUND`), D-G (docs/SECTORS_PROPOSAL.md, `SECT`) and the S1-S10 sims). No script, config or test changed. Line numbers: `main` `9798388` (code unchanged since), re-checked 2026-10-05. **(unverified)** = not checked in code; **(estimate)** = not measured; **(placeholder)** = sized by the sims; **G1** = needs Studio first (5.6).

**Fixed by the owner:** **D-A** a bigger building contains the previous one; objects move in at the same coordinates from a door-side anchor. **D-B** an IPO founds a new company, seeded with some of the old one's money (never items). **D-C** every founding starts with picking a sector. **D-D** a sector is a full package on one engine. **D-G (2026-10-05): two sectors launch, Software (today) and Gaming,** each with its own gameplay tied to the real field; **Fintech and Biotech are post-launch updates** (section 6). **D-E** free placement, phone and PC. **P-1** one Pokedex entry per sector. **P-2** an IPO completes the company and stamps its sector; the old company becomes a card. **P-3** both launch sectors = the launch goal (Hall of Fame); then replays earn Gold and Platinum, and a leaderboard; a later sector adds a goal (1.5). **P-4** old companies earn nothing; stamps give a small capped bonus. **P-5** the seed stays. **CLAUDE.md:29 exception approved:** `BoardServer` alone may use the leaderboard OrderedDataStores (section 7). **Inventory:** a purchase goes to the inventory ("Place now"). **D-F funding rounds:** Cash only (a gift, never `addEarnings`), paid for with dilution; the room follows the building owned (1.7, FUND). **Tiers (2026-10-05):** Platinum is expert only, a rare bragging tier; Gold is the normal goal; a tier must not be reachable by buying passes (1.5).

**Owner defaults** (vetoable): employees follow the player; creatures keep bodies, renamed per sector; **P-6** 5 buildings per sector (building 5 serves Series C+D to IPO-ready); any sector can be picked next; an unplaced item still earns; largest size **78 x 82**; hire desks fixed in v1; furniture earns nothing; a free, fixed starter set per building (D9); 45° rotation; part budget open until a phone test; **the stamp clock stays weighted** (LG:23) and **the board ranks Collection total** (1.6).

**New names** (none exists in code): `CompanyServer` (owns `pokedex`; `raiseRound`), `CompanyConfig` (with `Funding`), `SectorConfig`, `Sector<Name>`, `SectorArt<Name>`, `CompanyClient`, `CompanyRemotes.CompanyAction`, `BoardServer`, OrderedDataStores `Collection_v1`, `HallOfFame_v1`.

## 1. Companies, sectors and the Pokedex

**1.1 A company** is one run of one sector's ladder: Cash, upgrades, buildings, furniture, layout, eggs in incubators, valuation, funding rounds and dilution. **The player** keeps employees, HR level, passes, boosts, shields, Shares, perks, IPO count, `lifetime`/`best`, daily, onboarding, task stats, Pokedex, kept decor (IpoConfig.lua:6-8, 51).

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
  sectors = {                -- all four keys known from PR 1; no entry = not started
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

- **Fields:** `id` = an upgrade name or `<objectKey>#<n>`; `x`, `z` from the anchor, step 0.5; `r` 0-7; at most 40. No entry: an upgrade stands at its default slot; furniture, like ids in `stored` (at most 40), is in the inventory (section 4). `ratio` = IPO valuation / IPO-ready valuation. `sx` is the sector module's (`load` checks it; bad = `{}`, a warning). **Four sector keys from day one:** an early Fintech or Biotech entry (a Studio test) is kept, never picked, and counts for no goal or board. About 11 KB **(estimate)**.
- **Loader keeps unknown fields,** like onboarding (OnboardingServer.lua:226, 243, 281), daily (DailyServer.lua:244, 261, 290), tasks (TaskServer.lua:712, 766, 800), fixedHires (EmployeeServer.lua:657, 675, 694), but at **every** level: the section, `active`, `decor`, `passSeconds`, `objects[i]`, `stored`, `told`, `rounds`, `rounds[k]`, `sectors` (unknown sector keys kept whole), `sectors[k]`, `card`, `card.owned` (unknown upgrade names), `card.decor`, `card.objects[i]`, `card.rounds[k]`, `kept`, `hall`; `sx` and `card.sx` are kept whole. In the maps (`decor`, `kept`, `passSeconds`, `card.decor`, `hall`) an unknown key keeps its value. Those four keep top-level fields only; shop, team, poach, ipo none (EmployeeServer.lua:648).
- **Versioning:** `v` rises only when a field changes meaning; a higher `v` is kept unchanged; the session refuses `GoPublic`, `Place`, `BuyBuilding`, `PickSector`, `Raise`; `BoardServer` writes nothing for an unknown sector key. *Tests:* `v = 2` deep-equal after a save; each refusal.
- **Bad values** (type, NaN, infinite, negative, out of range, unknown or duplicate id): skipped with a warning; `stamp` clamped; `"done"` with stamp 0 becomes 1. Rounds: FUND 1.
- **Wiring:** `KNOWN_SECTIONS` (TycoonCore.lua:84), `buildPayload` (:421-433), save gate (:481); tests: section 6. Shut down all servers; rollback floor `V_launch` (M4+ code keeps unknown sections, TycoonCore.lua:773-777, 434-438).
- **No legacy migration:** nothing launched (PUBLISH_RULES.md:17, 101); test accounts are wiped first (`RemoveAsync` on a written list, :111). **No `pokedex`** = a new founding: `run = ipo.count`, Software, `picked = true` while the picker is off, building 1.
- **A10 run check.** (1) **`run < ipo.count`:** an older version ran an IPO (TycoonCore.lua:549-559; no seed or dilution, `pokedex` frozen; IPOs need the valuation, IpoServer.lua:192-195): `"done"`, Bronze if unstamped, a card (`rounds` unchanged); the new company: same sector, `picked = false`, building 1, `run = ipo.count`. (2) **`run > ipo.count`:** never an IPO. Only Debug **IpoReset** lowers the count (`count = 0`, IpoServer.lua:426; Studio only, :456); a restored DataStore version brings `pokedex` back with `ipo` (one key, TycoonCore.lua:505). So: `run = ipo.count`, `active` kept (settled rounds stay settled), no stamp, card or bonus, `studio = true`, a warning (else a free Bronze, carried to live by the shared save key, PUBLISH_RULES.md:46; `studio` blocks the board, not the bonus, 5.2). A damaged `ipo` read as count 0 lands here too (safe). *Tests:* IpoReset, rejoin: no stamp or card, rounds unchanged, `studio` set; `run` 2, `count` 3: Bronze and card once.

**1.3 Picking a sector, on every founding.** A window (`OpenPanel = "Sector"`), four cards: Software and Gaming (icon, name, how it earns, stamp, "New"); Fintech and Biotech greyed **"Coming soon"** (not tappable). Shown to new players, in every IPO and after run check (1). `CompanyAction("PickSector", key)` only while `picked == false`, for an enabled sector (the same one included); the picker preselects one not yet done (after both: the lower stamp). `SectorConfig.PickerEnabled = false` until both launch sectors exist.

**1.4 The IPO completes the company.** Today `goPublic` (IpoServer.lua:177-243) checks, then `commitIpo` (TycoonCore.lua:544-588) saves a transform resetting Cash, `owned` and eggs (IpoConfig.lua:53-58). New:
1. The picker before Confirm; `IpoAction("GoPublic", ipoNumber, sectorKey)` adds a sector check to `ipoNumber == count + 1` (IpoServer.lua:179).
2. **One transform, one save** (TycoonCore.lua:548-564): `"done"`, `stamp = max(stamp, earned)`, `replays`, `firstAt`, `bestEngaged`, the `card`; `hall.Launch` when both launch sectors are done; a new `active` (building 1, no rounds); `run = count + 1`; Cash = `StartingCash` + seed.
3. After that save (:565-587): the Garage room, a stamp pop-up, the board write.

**The card**, in a new **Pokedex** tab of the IPO window (IpoClient.lua:354): sector, name, stamp, IPO number, date, hours, ratio, stake, a **top-down map** (Frames). `ResetNames` (IpoConfig.lua:60-65) and the keep list (IpoClient.lua:524-533) add buildings, furniture, stamps, rounds.

**1.5 Stamps, replays, Hall of Fame.**
- **Bronze:** first completion, +1.5%; no time, ratio or stake condition. **Gold (decided by the owner, 2026-10-05):** a replay reaching ratio **≥ 1.20** within **1.30 T** engaged hours (G1), **no stake condition**, +0.5%. **Platinum:** ratio ≥ 1.20 within **1.0 T** (G1), stake ≥ **87.5%** (placeholder, FUND 3; the minimum kept, decided by the owner, 2026-10-05), +0.5%. **Stake** = 10,000 bp minus the total dilution at the IPO (FUND 3). **T** = the regular typical player's loop hours with a typical raise, **55.5 / 50.4 / 51.2 / 51.6 h** for IPO 1-4 (G1; LONG_GAME's 57 / 51.5 / 52 h have no raise), both sectors while parity holds. All **placeholders**.
- **Why (S6, robust to ±20%):** ratio 1.20 at p10 / p50 / p90: 1.01 / 1.09 / 1.20 T (typical), 0.95 / 1.03 / 1.13 T (fast), 1.38 / 1.46 / 1.54 T (slow). Platinum at 1.0 T: fast 33%, typical and slow 0%, typical pass owners 0-6%; the old 0.8 T / 1.25 gave everyone 0% (it needed 1.4x the typical speed; players span about ±7%). **Gold's 1.30 T** lies between the typical p90 and the slow p10: typical players who play on past IPO-ready reach it, slow ones do not; a hunter who misses 1.0 T keeps Gold. A replay under 1.20 earns no new stamp. **Gold's rule is not simulated:** S6 re-runs it.
- The server's stamp clock is weighted like the valuation (owner default, 1.6; LONG_GAME_PROPOSAL.md:23): Gold and Platinum wait for LONG_GAME PR 2. The tier = the highest whose conditions all hold, graded **once, in the IPO transform** (1.4), with the stake (from the saved `rounds`' `bp`), T and targets at the IPO; the client sends nothing; never regraded. Fast enough for Platinum but under 87.5% = Gold.
- **Pass fairness:** 2x Cash shortens a run about **6%** (S6, robust; was 15%): a target shrinks by 6% times the **share of the run's engaged seconds with the pass** (`passSeconds`), never by passes owned at founding (exploitable). The **Shareholder** pass gets the same 6% (an assumption: it only brings speed perks sooner, so it depends on perk timing, G1). A replay is priced by IPO count only.
- **Hall of Fame, the launch goal:** Software and Gaming `"done"`: `hall.Launch`, a title, a gold frame, a board entry. From IPO 3 on, every IPO is a replay.
- **When a sector is added later** (Fintech, Biotech): `SectorConfig.Goals` lists each goal's sectors; a shipped list never changes. `hall.Launch` stays earned; a new goal key (say `Four`) brings its own title and frame; Collection grows by itself.

**1.6 Leaderboard.** Today in-server only (IpoServer.lua:46-63; IpoClient.lua:750-786); no OrderedDataStore exists (docs/reviews/FULL_REVIEW.md:126).
- **Ranks:** **Collection** = `1000 x stamp points + min(IPO count, 999)` (Bronze 1, Gold 2, Platinum 3), the ranking metric; **Hall of Fame** = earliest `hall.Launch`. `BoardServer` writes `Collection_v1`, `HallOfFame_v1` (`pcall`, key UserId) from the loaded `pokedex` after the stamp's save, repairs a lower value on join, reads the top 50 every 10 minutes. No client sends a score; no board ranks speed or points per hour.
- **Heavy players' edge (S7), accepted (decided by the owner, 2026-10-05):** on Collection total the task-bot ties the human median; anyone above 3 engaged hours a day gains per hour (past 3 h only the valuation is weighted), but the board ranks a total capped at 3 stamp points per sector plus IPOs, so the edge buys stamps sooner, never a higher ceiling (a raw clock gives heavy humans 0% Gold; a per-day limit is not clean).
- **Studio never reaches the live board.** Both share the save key (PUBLISH_RULES.md:46): every Studio save sets `pokedex.studio = true` (never cleared); a `studio` account or one on the deny list (`BoardServer.REMOVED`) is never written or shown; Studio writes only `_Studio` twins. *Test (fake stores):* a `studio` save with two Platinum joins live: no write.
- **Names (FR-11):** `UserService:GetUserInfosByUserIdsAsync` (`pcall`, cached; limits unverified); the client escapes `& < > " '` (IpoClient.lua:780).

**1.7 Funding rounds (D-F):** one per stage per company, saved in `active.told`/`rounds` and the card (1.2); the rest: **FUND**.

## 2. The sector package and content

**Shared engine** (a test fails on a sector key in engine code): `pokedex`, picker, IPO flow, stamps, seed, bonus, rounds, board; buildings, placement, inventory; SHOP > Office; tasks; creatures, eggs, odds, `fixedHire` (D9), poaching; daily, onboarding, HUD; the clock; the sim. Sector hooks: SECT 0.

**Per sector** (`Sector<Name>`, `SectorArt<Name>`): key, name, icon, palette, 12+ company names; 5 buildings; upgrades (keys never reused; Software keeps today's six, TycoonCore.lua:65-72); furniture; tasks (`TaskConfig.Rows`, TaskConfig.lua:49); creature names and jobs (CreatureConfig.lua:53-104); egg names; an income model; fixed-content bundles, `id = 0`; art in PlotArt's `P(...)` format (PlotArt.lua:9-23).

**Income** (deterministic, capped, engaged only; **placeholders**; SECT 1.3, 2.4). **Software:** steady Income, `extra` = 0. **Gaming:** base Income plus a launched game's revenue, `SectorGaming.extra(data, seconds)` from base Income (TycoonCore.lua:677-680), on the **existing income-loop call** (:866), **no new call site** (daily_test.py:4536-4543), never in offline pay (:825); a visible score, never a roll (SECT 2.3). **Parity:** Gaming's upgrade Incomes (G1) are lowered to within ±5% of Software per engaged hour, every rung and `LONG_PLAYERS` profile (S3), with no bot or hopper gain (S4, S5).

**Content.** The content bible names 168 things (CONTENT_BIBLE.md:300-361): 154 Software's, 14 shared cosmetics (4 hats, 9 skins, 1 tag); **its decor is earned** (:261, 268, 278, 280; choice 5, :369), **bought here:** an earned piece goes to `kept`.

**At launch:** names 165 Software (153 + 12 company names), ~214 Gaming **(estimate, SECT 5's list)**, 10 shared (9 cosmetics; Night Guard): **~389**; art builds ~75 each, **~150 (estimate)**; task rows 18 (+28 tiers, LG:74) and 7 (+ tiers): 25. Fintech and Biotech later: ~723 names (168 + 3 x 185), ~300 builds (4 x 75).

## 3. Plot space (re-verified in the code)

- **Code:** `PLOT_SPACING = 90`, `MAX_PLOTS = 6` (TycoonCore.lua:74, 76); `plotCenter` x = -225 + 90 x (slot - 1), z 150 (:123-126); `Floor` 60 x 60 (:736): z 120-180. Front = +Z (TycoonCore.lua:75, IpoServer.lua:21; spawn :698-700). **Anchor = floor front-center, z 180.** VIP Lounge z 57.5-82.5 (ShopServer.lua:35-37, 636-650), its door `Touched` (:683) the only one, a non-VIP sent to **z 88** (:839); skyline z 101-107 (PlotArt.lua:699-707).
- **Size:** a shell adds 2.3 per side (BUILDING_PASS_PROPOSAL.md section 3): 90 - W - 4.6 ≥ 6 gives **W = 78**; 180.2 - D - 2.3 ≥ 94 gives **D = 82**. Nested **(estimate)** 60 x 60, 64 x 66, 68 x 70, 72 x 76, 78 x 82; no plot moves; **Baseplate 534+ wide (unverified).** The skyline (`BACKDROP_Z`, PlotVisuals.lua:44) and 60 x 60 assumptions (PlotArt.lua:31; PlotVisuals.lua:544, 590-592, 643) go. **Owner checks in Studio:** Baseplate, SpawnLocation, anything at z 85-120 or past x ±225, Terrain, StreamingEnabled.

## 4. The office: placement, inventory, checks, budget, phone

- **Fixed:** Floor (the only solid), spawn lane, signs, incubators (EmployeeServer.lua:37-40), hire spots, desks (:31-35). **Movable:** upgrade props, furniture. An owned upgrade with no `objects` entry, not in `stored`, stands at its **default slot** (today's `itemOffset`, TycoonCore.lua:131-135, 189), as older code shows it: nothing disappears after PR 3 or a rollback. Furniture has none. **Move-in (D-A):** `objects` stay; building n+1 contains n; the new area gets the starter set.
- **Inventory** = ids in `active.stored` plus owned furniture with no entry. A purchase (PR 3 on) adds its id to `stored`, with **"Place now"**; `"Store"` adds an id, `"Place"` removes it and writes `objects`. Stored items **still earn** (Income reads `owned`, TycoonCore.lua:137-145). In PR 3 `buyUpgrade` (:272-288) drops the pop-in (:285) and writes `stored`; the join loop (:811-815) draws owned upgrades not stored; the Office tab (ShopClient.lua:496-573) gains "Place now" and "In storage". **The buy is unchanged:** one charge after `checkUpgradePurchase` (:243-270); "Place" is free.
- **Checks** on `CompanyAction` (`"Place", id, x, z, r`; `"Store"`; `"Sync"`; `"PickSector"`): `data.ready` (IpoServer.lua:212-213); `id` a string under 40 chars, finite `x`/`z`, whole `r` 0-7; ownership; inside the building; overlap ≤ 0.1 stud; no reserved zone (`PlotVisuals.zones`, :504-531); budgets; 4 requests/s. **One pure function in `CompanyConfig`:** the client previews, the server decides. Placement never changes Income; **no `Touched` handler** (daily_test.py:4463-4465).
- **Part budget:** `MAX_PARTS = 260`, `MAX_LIGHTS = 3` (PlotVisuals.lua:39-40); rooms use 244-257 (ROADMAP.md:42), props 118 (daily_test.py:3858). **Proposal:** draw only owned desks, 320 per plot, decided at G-S.
- **Edit mode** (`OpenPanel = "Office"`, from SHOP > Office): top-down camera, about 3.5 px per stud at 78 x 82 on 667 x 339 **(estimate)**; pick strip, pinch zoom, drag, snap 0.5, one `"Place"` on lift; Rotate, Store, Done 56 px; PC: drag, R, Delete.
- **Shop:** Office gains Buildings and Furniture (`"BuyBuilding", n`, `"BuyObject", n` on `ShopAction`, ShopServer.lua:704-717, 802-805), checked like `checkUpgradePurchase` plus "stage n reached" (raised or not) and "building n-1 owned". **Prices:** until LONG_GAME PR 2, `CompanyConfig.Buildings`: `floor(IpoConfig.stageValuation(n, ipo.count) x priceBp / 10000)`, `priceBp` 2,500 (450 / 1,575 / 5,850 / 20,250 at IPO 0; a Cash sink only); then its office price (LG:53-58). No odds words (daily_test.py:4553-4560).

## 5. Economy: seed, collection bonus, sims

**5.1 Seed (P-5).** `StartingCash` (0, IpoConfig.lua:44) plus **s% of the old company's Cash, capped at c% of the new first rung's prices** (10 and 25, **placeholders**, S1): a gift (no `addEarnings`), paid once in the IPO transform.

**5.2 Collection bonus (P-4).** A **Cash multiplier on Income**: +1.5% per Bronze, +0.5% Gold, +0.5% Platinum, **capped at +10%** (two sectors reach +5%; **placeholders**, S2), applied with the passes (`updateIncome`, TycoonCore.lua:148-152), **never valuation**, so **0 until LONG_GAME PR 2** (today the income loop, :865-866, and offline pay, :819-827, add all Income to it). Never in `baseIncome` (:677-680) or away pay. Stacked: 2x Cash x VIP x 1.10 = x3.3, times the IPO multiplier (no cap, IpoConfig.lua:162-165). **No stamp pays Shares** or changes odds (D9).

**5.3 Risks.** A faster sector becomes the only choice (S3-S5). **Duplicate seed:** one transform; `ipoNumber` blocks a repeat (IpoServer.lua:179); a failed save changes nothing (TycoonCore.lua:565-567). **5.4 Funding rounds:** FUND 2-4.

**5.5 Simulate before any build** (tools/economy_sim.py, new `--pokedex` mode; marks are **placeholders**):
- **S1 seed:** 0 / 10 / 25% cap: ≤ 5% faster per loop; a "decorator" ≤ 5% slower. **S2 bonus:** 0-12 points x pass sets: at the cap ≥ 95% of no-bonus hours. **S3 parity:** Software and Gaming, every profile and rung ±5%. **S4 bots:** no sector faster for a bot. **S5 hopping:** alternating vs one sector, 10 IPOs: < 3%. **S6 tiers** (re-run on 1.5's rules): Platinum on ≥ 20% of fast replays and ≤ 5% of typical and slow ones; Gold on most typical replays, ≤ 10% of slow ones; pass owners within ±5 points. **S7 board** (Collection total): new-sector vs replays within 10% in hours; the task-bot never above the dedicated human median. **S9 launch policy, S10 cadence:** SECT 4.
- **S8 round size:** FUND 6 (both sectors; also speed versus tier lost on stake).

**5.6 G1: numbers that need Studio first** (placeholders until measured):

| Number (where) | Measure in Studio | Gate |
|---|---|---|
| T (1.5) | task reward per engaged second, then rung hours | LG:115, G-S (c) |
| Gold 1.30 T (not simulated), Platinum 1.0 T (1.5) | players' speed spread (sims: ±7%) | G-S, S6 re-run |
| Shareholder 6% (1.5) | perk timing with and without the pass | G-S |
| Gaming upgrade factors, base 0.77 (SECT 2.4, 2.10) | rung hours against Software's | G-G (a) |
| Scope table (work, half-lives, peaks), `k`, policy hours, 49 titles (SECT 2.4, 2.10) | build times, tiers reached, titles per rung | G-G (b) |
| Sprint Review 12 min, `awayIncome` (SECT 2.2, 2.4) | longest wait (C+D, Pre-IPO); check-in bank | G-G |

## 6. Build plan

Each PR: claim its scripts, `python3 tools/daily_test.py` passes, F5 clean, publish with **Shut down all servers**; new modules created in Studio first (PUBLISH_RULES 2b). **PR 1 ships the whole `pokedex` format.** PR 2 can ship before LONG_GAME PR 2, its buildings Studio only until it; PR 4b and 8-14 need it.

**D-F in today's code:**
- **Room from the building (PR 2).** Today `stageOf`/`syncRoom` (TycoonCore.lua:175-186) pick the room from the stage, on join (:810) and every second (:867). New: `roomOf(data)` = `pokedex.active.building` while buildings are active (like `TaskConfig.isActive`), else `stageOf(data)`. `BuyBuilding` and the IPO (building 1) call `PlotVisuals.setStage`; :867 calls `CompanyServer.onStage` (the round message). Task rung (TaskServer.lua:117) and IPO sign (IpoServer.lua:66-75) still follow the stage.
- **PlotArt / PlotVisuals (PR 2):** `PlotArt.Stages` (PlotArt.lua:798, read at PlotVisuals.lua:190, 228, 247) keeps name, order and content, now "room of building i" (comments PlotArt.lua:5, PlotVisuals.lua:16-17).
- **Valuation HUD / IpoClient:** FUND 7 (PR 4b).
- **PR 1 review-fix follow-ups** (docs/CUSTOMIZE_PR1_NOTES.md, "Review fix notes"): PR 2 keys `zonesCache` in `CompanyServer` by building (computed once from the 60 x 60 layout). PR 3 decides what to do with saved layouts over the part budget (PR 1 saves up to 40 items, measures no parts). PR 4 accepts a saved company name not in `SectorConfig`'s list (PR 1 gives every company "Garage Labs") and ends "run follows the IPO count" as the rule once its IPO transform exists (stamps, cards).

**Test impact** (daily_test.py, `main` `9798388`):
- **Must hold:** fingerprints (stage 1, props, layout: :3770, 3778, 3790; stations stay the default slots); one `Touched` handler (:4463-4465); new: building i draws exactly `PlotArt.Stages[i]`.
- **PR 1:** the section list (:4478-4480) gains only `pokedex`; "pokedex is a known section" joins :4531 and :664 / :673 (BUILDSAVE, `known_sections_line`, :4700-4705); :659 gains `payload.pokedex`. **The save gate** (TycoonCore.lua:481) gains `data.pokedex`; :4533 matches `"data.daily and data.tasks)"` exactly, so it is rewritten to check both names.
- **PR 2:** :4667-4668 (the income loop's `syncRoom`) are rewritten to pin `roomOf(data)` (the fallback may still match: never pass by accident). The Office checks :4487-4488 and :4494-4495 (only `core.buyUpgrade`; only `"Upgrades"`, `"BuyUpgrade"`) gain `"BuyBuilding"`.
- **PR 3:** :4669 (`spawnItem(data, i, upg, true)`, the pop-in) breaks: purchases go to storage.
- **PR 4b:** the `addEarnings` checks (:4536-4543) cover every `.lua` file and aliases (FUND 2).
- **PR 5-11:** the D9 word check (:4553-4560) adds CompanyClient, CompanyServer and the sector modules; the `addEarnings` count (:4537) stays 3 (Gaming rides :866).

**Engine (PR 1-3)**
1. `pokedex` (full format, all sector keys, `sx`, `hall`; default, run check, versioning); `CompanyServer`, `CompanyConfig`, `SectorConfig` (Software enabled; Gaming, Fintech, Biotech listed, not enabled; picker off); `"Place"`/`"Store"`/`"Sync"`. *Tests:* round trip; unknown fields kept at every level; `v = 2`; both run check cases; bad values; overlap, zones, rate, ownership.
2. **The building engine:** `roomOf` and the `Buildings` switch (`StudioOnly` on), `"BuyBuilding"` with placeholder prices, nesting, move-in, the starter set. Buildings 1-5 are today's five rooms (`PlotArt.Stages`). *Tests:* the fingerprints; switch off = today's room; nesting; objects unchanged; budgets; a building before its stage is refused.
3. `CompanyClient` edit mode; the inventory; roof hidden in edit mode. *Tests:* both phone sizes; sends only id, x, z, r; one charge; a stored item earns; an upgrade bought by older code stands at its default slot. *Studio:* buy the Laptop, store it, rejoin, place it.

**Pokedex and picker (PR 4, 4b)**
4. The IPO completes the company: Bronze, card, Pokedex tab, seed (Studio only until S1), picker (Studio only; Software only). *Tests:* one transform; Bronze once; seed capped and once; run check; a disabled sector's `PickSector` refused.
4b. **Funding rounds:** FUND 7; **live only after** S8, LONG_GAME PR 2 and 3 (R2, R3).

**Software vertical slice (PR 5-7)**
5-7. `SectorSoftware`, `SectorArtSoftware` (keys unchanged), Software's buildings 2-5 on PR 2's engine (64 x 66 to 78 x 82, section 3) and art, furniture, kept decor, `"BuyObject"`. *Tests:* no sector key in engine; fingerprints; budgets; D9 words.

**G-S, go / no-go after the Software slice:** (a) 6 plots at building 5, full budgets, low-end phone ≥ 30 fps; (b) 3+ players build, arrange, raise or skip, IPO, replay and find the card unaided; (c) S1, S5, S8 pass for Software, S3 within ±5% of LONG_GAME's hours; (d) section 3's Studio checks. **No-go: fix first.**

**Gaming (PR 8-11)**
8. **Sector hooks and a Gaming greybox** (Studio only, SECT 0, 2): `extra` on the :866 call, `sx`, `CompanyAction("Sector", ...)`, `onTask`, task rows, a plain Project window, placeholder art. *Tests:* TycoonCore still has 3 `addEarnings` calls; extra only while engaged; the Forecast equals the server's score; verbs never set engaged; D9 words.

**G-G, go / no-go before Gaming content:** (a) S3 (Gaming within ±5%), S9 and S10 pass on fitted numbers (SECT 4); (b) in Studio, 3+ players each finish two titles unaided, name the tier before launching and choose ship or polish; (c) the Project window fits 667 x 339 and 320 x 532; (d) Gaming's content bible approved (SECT 5). **No-go: refit or redesign first.**

9-11. `SectorGaming`, `SectorArtGaming`: 5 buildings, upgrades, desks, furniture, decor, names, bundles (`id = 0`); the picker shows Gaming. *Tests:* parity ±5%, no new `addEarnings` site, no sector key in engine, budgets, D9 words, `id = 0`.

**Tiers and the leaderboard (PR 12-13), then launch (PR 14)**
12. Gold, Platinum, stamp clock, pass-share targets, Platinum's stake minimum, bonus, Hall of Fame; needs S2, S4, S6, S8, both sectors. *Tests (FUND 3):* Platinum's time and ratio under 8,750 bp gets Gold; Gold has no stake requirement (a low-stake Gold run still gets Gold); Bronze neither; exactly 8,750 bp keeps Platinum, 8,749 does not; the tier uses the stake, T and targets at the IPO, never later ones (config change, Debug, rejoin); exactly ratio 1.20 and exactly 1.30 T keep Gold, 1.30 T plus 1 s does not; a missed 1.0 T still grades Gold; the 6% shrink at pass share 1.
13. `BoardServer` (exception approved, section 7), FR-11; needs S7.
14. Picker and funding on for live servers; PUBLISH_RULES "2d" (FUND 4's rollback note); publish.

**Post-launch: Fintech and Biotech**, each its own PRs: the same package, **no new save field** (keys from PR 1), `SectorConfig` enables it, a new goal key (1.5), S3-S5 rerun, a content bible, D9 words, `id = 0`. Income sketches (deterministic, capped, engaged only, on the :866 call): **Fintech** interest on Cash held, capped at H seconds of base Income (works against the buy loop: revisit); **Biotech** P seconds of base Income every N engaged minutes (a visible timer).

## 7. Impact on other docs and branches

**docs/LONG_GAME_PROPOSAL.md** (`LG:` = its line):
- **Principle (LG:5)** holds for every grant (seed; rounds: FUND 8).
- **Section 3 (LG:38, 53-60):** a building costs its office's price; 7 offices on 5 footprints (Glass Tower, Global HQ: shell upgrades of building 5); hire spots for 18 desks; R1 caps (LG:108) follow office purchases; furniture never enters `LONG_K`; moments (LG:66-79) recounted per sector.
- **Decor (LG:78, 82, 86, 88, 92):** earned pieces **kept**, bought copies reset; Boardroom skin = a pass furniture set; prestige wing stays perks.
- **Money (LG:86, 92-94):** Gaming rides `addEarnings` entry (1); rounds and entry (8): FUND 8. **Section 8 (LG:110-122):** its PR 4 = PR 1-7 here, its PR 7 = PR 8-11; 4b needs its PR 2 and 3. Hours and stamps per sector: SECT 5.

**Other docs:**
- **`design-tutorial` collides:** both add a section and a module (TycoonCore `KNOWN_SECTIONS` :84, payload, save gate :481; daily_test.py:4478-4480, 4533). **`setupPlayer` order:** IpoServer (:793), fixedHires, EmployeeServer (:795), PoachServer, OnboardingServer (:797), **CompanyServer**, TaskServer (:798), **TutorialServer** (TUTORIAL_PROPOSAL.md:106), DailyServer (:799, last); `init` alike; BoardServer's repair after `data.ready` (TycoonCore.lua:831). Tutorial PR A first.
- **Tutorial steps** (TUTORIAL_PROPOSAL.md) 1 and 4 (:25, 28): "own your sector's first upgrade", "own 2 of this company's upgrades" (step 1 waits while `OpenPanel = "Sector"`). **Step 8:** FUND 8. **Step 9** (:33, :37-42): resets add buildings, bought furniture, rounds, dilution; keeps add stamps, kept decor. New step: "Arrange your office". The "?" and the strip (:53, 62) are untouched. Step 5 and Gaming's steps: SECT 5.
- **`content-bible`:** sections 1-6 = Software's package; industry skins (247) go; Gaming's lists: SECT 5.
- **`building-pass`: park it** (its patch and BuildingClient.lua assume 60 x 60; its roof blocks the edit camera); reuse its shell data and `pcall` plug-in.
- **`visuals-garage`, PLOT_VISUALS.md (14, 37), CLAUDE.md "Plot visuals" (32):** 60 x 60, the skyline, "six props identical in every room", "the only solid" and "room of `IpoConfig.Stages[i]`" change.
- **CLAUDE.md, README, ROADMAP, PUBLISH_RULES:** `pokedex`, modules and order, `CompanyRemotes`, "2d".
- **CLAUDE.md:29 (approved by the owner):** the build PR changes it to exactly: "Never add a second DataStore, save loop or PlayerAdded data owner. One exception: `BoardServer` (ServerScriptService) may use the OrderedDataStores `Collection_v1` and `HallOfFame_v1` (and their `_Studio` twins) for the leaderboard. It writes only values read from the loaded save after that save succeeded, never saves player data, and wraps every call in `pcall`. Every other store stays under this rule."

## 8. Open questions (unresolved, most important first)

1. **78 x 82 enough,** or move the plots (`PLOT_SPACING` 112)? At G-S.
2. **Collection bonus:** a Cash multiplier, never valuation, capped at 10% (two sectors reach half; recommend), or a cheaper first rung?
3. **Gaming's questions** (fallback if G-G fails, Project window, words): SECT 6.
4. **Earned decor:** which milestones unlock which kept piece (content bible choice 5), and what Day 7 gives once its list is all kept?
5. **A board per later goal** (1.5): each needs a new named store (CLAUDE.md:29). Recommend none.

## What I did not verify

- No Studio or MCP was used: section 3's checks, hand-placed parts, "0 visits" and privacy, OrderedDataStore and `UserService` limits, camera scale, frame rates, why `MAX_PARTS` is 260, the top bar height.
- The sims were not re-run here: S1-S10's findings were taken as given. Every economy number and content count stays a placeholder or estimate; no tier, stake or Gaming code exists.
- Other branches were read with `git show`; LONG_GAME PR 2 doesn't exist; `daily_test.py` was not run (docs only).
