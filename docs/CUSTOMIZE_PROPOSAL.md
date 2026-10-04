# Customize your office: buy a building, place what you own (proposal, design only)

Design only (2026-10-04, branch `design-customize`, from `visuals-garage` at `7f5c141`). No script, config or test was changed. Written for the owner and for the Claude sessions that will build it. Line numbers are for `7f5c141`. **(unverified)** marks anything I could not check in code; **(estimate)** marks a number I did not measure.

**Product decision (fixed by the owner).** The Garage stays the starting room. At Seed, Series A, Series B and IPO-ready the Shop sells a new, **empty** building, buyable only once that stage is reached. The player fills it with objects they own: the six upgrades, earlier objects and new objects that unlock per stage. Placement is free (drag anywhere inside, rotate) on phone and PC. The art of PlotArt stages 2-5 becomes the building shells and the object catalog, no longer pre-built rooms.

**Name used below:** `OfficeServer` (ModuleScript, ServerScriptService), `OfficeConfig` (ModuleScript, ReplicatedStorage), `OfficeClient` (LocalScript, StarterPlayerScripts), remotes `OfficeRemotes.OfficeAction`, save section `office`. None of these names exist in the repo today (checked with `grep`).

## 1. Data model

**A new top-level save section `office` (rule A10).** It cannot go in `owned`, `team` or `ipo`: older code drops unknown fields inside a section it knows.

```lua
office = {                       -- OfficeServer.serialize (optional: written only once a building is bought or something moved)
  v = 1,                         -- format version (see below)
  run = number,                  -- ipo.count this ownership belongs to (A10: per-run state is checked on load)
  buildings = { "Seed", ... },   -- buildings bought this run (IpoConfig.Stages keys). "Garage" is always owned, never listed
  active = "Seed",               -- the building shown: "Garage" or one of `buildings`
  decor = { [objectKey] = n },   -- furniture owned (how many of each). Upgrades are NOT here: `owned` already saves them
  layouts = {                    -- per building key, what stands where
    [buildingKey] = { { id = "Desk", x = -23, z = -10, r = 0 }, { id = "Plant#2", x = 8.5, z = 20, r = 3 }, ... },
  },
}
```

- **Per object:** `id` (an upgrade name from `TycoonCore` `UPGRADES`, TycoonCore.lua:65-72, or `<objectKey>#<n>` for the n-th copy of a furniture piece), `x`, `z` (studs from the building's floor-top center, rounded to 0.5), `r` (rotation step 0-7, 45° each). No `y`: everything stands on the floor, nothing stacks in v1.
- **An object with no layout entry stands at its default spot.** For an upgrade that is today's slot, `itemOffset(i)` (TycoonCore.lua:131-135). So a save with no `office` section looks exactly like today's Garage, and nothing needs migrating.
- **Limits:** at most **40 objects per building** and the part budget of section 4, whichever comes first. Size **(estimate)**: about 40 bytes per entry in JSON, 5 buildings x 40 = about 8 KB. Roblox's per-key limit (4 MB) is from Roblox's docs, **(unverified here)**.
- **Versioning:** `v = 1`. A save with a higher `v` is treated like an unknown section: loaded as "Garage, default spots" for this session and **written back unchanged** (same rule as `unknownSections`, TycoonCore.lua:434-438). Bad entries (wrong type, NaN, infinite, outside bounds, unknown id, duplicate id) are skipped with a warning, never an error.
- **A10 run check:** if `office.run ~= ipo.count` on load, an older server ran an IPO without knowing this section. Then `buildings` is cleared and `active = "Garage"`; `decor` and `layouts` are kept (section 7).
- **`KNOWN_SECTIONS` impact:** add `office = true` (TycoonCore.lua:84); `office = OfficeServer.serialize(data)` in `buildPayload` (TycoonCore.lua:421-433); `data.office` in the save gate (TycoonCore.lua:481). `tools/daily_test.py:4269-4271` asserts the exact list of sections and **must be updated in the same PR** (it fails on purpose today).
- **Publish:** needs **Shut down all servers** (a new section, like `daily`, `onboarding`, `tasks`; docs/PUBLISH_RULES.md section 3). **Rollback floor stays `V_launch`:** code from M4 on keeps `office` frozen (TycoonCore.lua:773-777); a rollback shows the old stage rooms again and loses nothing. A docs/PUBLISH_RULES.md "2d" note goes in PR 1.
- **Module order:** `OfficeServer.setupPlayer` runs after `IpoServer` (run check) and `EmployeeServer`, before `TaskServer` and `DailyServer` (Daily stays last, TycoonCore.lua:793-799).

## 2. Gameplay positions today, and what may move

| Thing | Where it comes from | Today | Proposal |
|---|---|---|---|
| Floor (60 x 60, the only solid part) | TycoonCore.lua:736 | fixed | **fixed**. Every building is 60 x 60 on it (plots are 90 apart, TycoonCore.lua:74) |
| Spawn (0, 12) and the lane | TycoonCore.lua:698; `PlotArt.Layout.spawn`, `reserve.spawnHalf`, `laneEnd` (PlotArt.lua:37, 66-68) | fixed | **fixed, reserved** (no object may stand there) |
| BuySign (0, 24), IpoSign (21, 24) | TycoonCore.lua:75; IpoServer.lua:21 | fixed | **fixed, reserved** |
| 5 incubators at z -25 | EmployeeServer.lua:37-40, with a Hatch ProximityPrompt (:531-544) | fixed | **fixed, reserved** with the space in front (`incubatorHalf`, `incubatorFront`) |
| 11 hire spots (4 x 3 grid) | EmployeeServer.lua:31-35; `spotFor` (:172-175) | fixed | **fixed in v1** (open question 3) |
| 11 hire desks | decor only: `PlotVisuals.buildRoom` puts one at every spot (PlotVisuals.lua:199-203) | fixed | fixed in v1, skin per building |
| Six upgrade props | `itemOffset` (TycoonCore.lua:131-135), built by `spawnItem` (:189-201) | fixed | **movable** |
| Founder's desk + DeskPhone | decor in rooms 2-5 (docs/PLOT_VISUALS.md line 24) | decor | furniture (nothing else references `DeskPhone`: `grep`) |
| Furniture (sofas, plants, lamps, ...) | `PlotArt` stage decor lists | decor | **movable**, bought per stage |

**Employees and desks: the rule.** Employees do not sit today. The server sets a `Home` point per employee (EmployeeServer.lua:185, 199), and EmployeeClient wanders each model up to 3 studs around it (EmployeeClient.lua:984-999). Nothing uses a `Seat` except the VIP Lounge (ShopServer.lua:672). Proposed rule: **employee i's `Home` stays the seat point of hire desk i.** In v1 the desk does not move, so nothing changes. If hire desks become movable (PR 5), the server sets `Home = desk CFrame * (0, 0, -3.3)` (the inverse of `PlotArt.Layout.desks`, PlotArt.lua:57-60), and the desk's footprint includes a 3-stud circle around that point (the wander radius), so no other object can stand where its hire walks. Only the server writes `Home`; the client keeps animating as now.

## 3. Server validation (anti-exploit)

The client only asks. One remote, `OfficeRemotes.OfficeAction` (RemoteFunction made by `OfficeServer.init`): `"Place", id, x, z, r` · `"Store", id` · `"SetActive", buildingKey` · `"Sync"`. Purchases go through the existing `ShopAction` (section 6). On every request:

- `data.ready` (false while loading and during an IPO save, IpoServer.lua:211-213) and `data.office` exist.
- **Types and ranges:** `id` a string under 40 characters; `x`, `z` finite numbers, rounded to 0.5; `r` a whole number 0-7. Anything else: "Bad request", no warning per call.
- **Ownership:** an upgrade id must be in `data.owned`; a `Plant#2` id needs `decor.Plant >= 2`; `SetActive` needs the building in `buildings` (or "Garage").
- **Bounds:** the object's footprint (a rectangle turned by `r`) stays inside the active building's inner box. Footprints are data in `OfficeConfig` (the client needs them too, and `ReplicatedStorage` cannot require `PlotArt`); a test proves each covers its art's real part boxes (`PlotVisuals.boxOf`, PlotVisuals.lua:65-72).
- **Overlap:** two footprints may not overlap by more than 0.1 stud (2D test on rotated rectangles). Floor marks (rugs: at most `PlotVisuals.FLAT` = 0.2 high, PlotVisuals.lua:38) may lie under anything. No footprint may enter a reserved zone from `PlotVisuals.zones` (PlotVisuals.lua:504-531): signs, spawn and lane, incubators and their front, hire spots and hire desks. The six upgrade slot zones stop being reserved.
- **Height:** an object is at most 12 studs tall (today's back-wall cap, PlotVisuals.lua:42), so it stays under the building-pass roof (underside at 14).
- **Budgets:** parts and PointLights (section 4) are counted by the server from the art, never sent by the client.
- **Rate limit:** dragging happens on the client; only the drop is sent. 4 requests/s with a burst of 8, and 120 per minute (token bucket, like TaskServer's). Spam is refused, not queued.
- **The validation is one pure function in `OfficeConfig`.** The client runs it for the red/green preview; the server runs it again and decides.

**Income:** placement never changes income. `totalIncome` sums owned upgrades and employees (TycoonCore.lua:137-145) and reads no position. Buildings have **no Income**, the same rule as `LONG_ITEMS` in tools/economy_sim.py:1063 ("a desk and an office have no Income"). Furniture has no Income (open question 4). A stored upgrade still earns (open question 4). **No new `addEarnings` call:** buying spends Cash only. tools/daily_test.py:4327-4334 lists every call site and must stay as it is. Spending Cash does not lower the valuation (valuation = Cash earned, IpoConfig.lua:4).

**No `Touched` handler:** the drag is client input (a screen ray onto the floor plane, plain maths). Decor parts have `CanQuery` off (PlotVisuals.lua:105), so the client picks objects by testing the tap point against the footprints, not with a raycast. tools/daily_test.py:4254-4256 still allows only the VIP door.

## 4. Part budget

**What exists:** `PlotVisuals.MAX_PARTS = 260` per room, props included, and `MAX_LIGHTS = 3` per plot (PlotVisuals.lua:39-40). Rooms with the six props use 256 / 244 / 254 / 253 / 257 parts (docs/PLOT_VISUALS.md table).

**Why the limit exists:** the code and docs give the number but **no written reason**. It was 220 in the first commit (`1fba576`) and was raised to 260 (ROADMAP.md line 41). The likely reason **(inferred)**: server-built parts replicate to every player (PlotVisuals.lua:5-6), so each phone draws all 6 plots (`MAX_PLOTS = 6`, TycoonCore.lua:76). The place's StreamingEnabled setting and real frame rates are **(unverified)**.

**Per-object costs (counted in PlotArt.lua):**

| Object | Parts | | Object | Parts |
|---|---|---|---|---|
| Desk (806-832) | 24 | | Hire desk Garage / Seed / A / B / IPO (369, 457, 568, 676, 789) | 2 / 5 / 5 / 5 / 6 |
| Coffee Machine (834-853) | 17 | | Sofa, `sofaLeft` (164-172) | 5 |
| Laptop (855-874) | 17 | | Plant, `plant` (156-161) | 2 |
| Server Rack (876-903) | 24 | | Founder's desk, `founderDesk` (176-190) | 11 |
| Whiteboard (905-927) | 19 | | **Six upgrades together** | **118** |
| Neon Logo (929-949) | 17 | | | |

Shell + decor of today's rooms = total - 118 - 11 desks: **116 / 71 / 81 / 80 / 73**. The split between shell and decor is **not measured**: there is no `luau` on this machine, so I did not build them.

**The problem:** in a 260 budget, a shell **(estimate: 60 parts at most)** + 11 hire desks (up to 66) + the six upgrades (118) leaves **16 parts** for furniture: about 3 pieces. That is not a game.

**Proposal:**
1. **Draw only the hire desks the player has** (`maxEmployees`, 5 to 11): saves up to 36 parts at the start.
2. **`MAX_PARTS` per plot = 320** (shell ≤ 60, hire desks ≤ 66, placed objects ≤ 194: the six upgrades + about 76 parts of furniture, 8-15 pieces). Lights: 3 per plot, counted over shell and objects. Lamps are refused once 3 are placed.
3. **Server total:** 6 x 320 = **1,920 parts** (today at most 6 x 257 = 1,542, +25%). **Gate:** a phone test with 6 full plots before raising it. If it fails, stay at 260 and cut hire-desk skins to 2 parts.
4. **The edit UI shows a budget bar** ("Space: 182 / 194"), so a refusal is never a surprise.

**Building-pass 64-part budget: compatible.** It is a separate sibling Model with its own budget, not counted in the room's (docs/BUILDING_PASS_PROPOSAL.md on `building-pass`, D-1). With it: 384 per plot, 2,304 per server. Its roof underside (14) matches the 12-stud object cap, and its door (x -4.5 to 4.5) is inside the reserved lane. Only its key changes: it builds per building, not per stage (section 8).

## 5. Phone and PC UX

**Edit mode is a window.** It sets `OpenPanel = "Office"`, so every other window closes (e.g. ShopClient.lua:731-735) and the task tray hides (TaskClient.lua:28). Like the Shop, it hides the thumbstick and jump button (`GuiService.TouchControlsEnabled`, ShopClient.lua:725), so the character stands still. **The inventory can never cover the Shop header,** because the two are never open together: opening the Shop ends edit mode. "Get more" in the inventory first closes edit mode, then opens SHOP > Office.

- **Entry:** an "Arrange your office" card at the top of SHOP > Office. **No new HUD slot**: slots 0-4 fill the landscape top row up to x 370 (10 + 5 x 72, ShopClient.lua:101-104), and the valuation bar and gift chip use the rest (IpoClient.lua:238-242).
- **Camera:** a fixed top-down view of the whole 60 x 60 floor while editing (`Scriptable` camera, restored on exit). There is no camera gesture to fight with the drag. About 5 px per stud on a 667 x 339 GUI **(estimate)**.
- **Touch:** tap an object to select it (outline on the client only), then drag **anywhere** on the screen to move it by the finger's offset, so small objects don't need precise taps. It snaps to 0.5 stud and turns red when the shared check (section 3) says no. Lifting the finger sends one `"Place"`; a refusal snaps it back with the reason in a toast.
- **Buttons:** Rotate ⟳ (45°), Store 📦 (back to the inventory; it keeps earning), Done ✓. All 56 x 56 **(estimate, above the 44 px minimum)**.
- **PC:** drag with the mouse, R rotates, Delete stores, Esc or E exits.
- **Layout (GUI px; the GUI is the device minus Roblox's top bar, which `IgnoreGuiInset = false` keeps; the bar's size is not measured, TaskClient.lua:8-11; 36 px assumed below):**

| | 667 x 375 landscape (GUI 667 x 339) | 320 x 568 portrait (GUI 320 x 532) |
|---|---|---|
| Kept clear | HUD row + valuation bar + chip, y 6-70 | HUD column x 12-88 (ShopClient.lua:106-108) and the bar at x 98, y 12-76 |
| Inventory strip | x 10-591, y 257-329, tiles 64 x 64, scrolls sideways | x 98-310, y 450-522, 3 tiles visible |
| Buttons | column x 601-657, y 82-266 | row x 98-310, y 386-442 |
| Budget bar | above the strip, y 233-251 | above the buttons, y 362-380 |

All rows are **(estimate)** until checked in Studio with Test > Device at 320x568 and 667x375, with a top bar of 0, 36 and 58 px, as `TRAY_TESTS` does. Pop-up toasts (bottom center) may cross the strip for a moment; the strip draws below them (DisplayOrder -2, like the tray).

## 6. Shop changes

- **No new tabs.** The window is 614 px wide at 667 x 339 and 294 px at 320 x 532 (0.92 of the GUI, max 640 x 470, 10 px padding: ShopClient.lua:133-150). Tabs share that width (ShopClient.lua:204). In portrait, 5 tabs (with Debug) are about 49 px each; 7 would be about 33 px, too narrow to read. So **SHOP > Office gets three sections** in its scrolling page: **Buildings**, **Upgrades** (the six, unchanged), **Furniture**, plus the "Arrange" card on top.
- **Buildings section:** one card per building: Locked ("Reach Seed"), Buy ($), Owned / Move in / Active. `"Buildings"` and `"BuyBuilding", n` on the existing `ShopAction` (ShopServer.lua:701-715, 802-805), with the number only, like `"BuyUpgrade"`. One server function with the same checks as `checkUpgradePurchase` (TycoonCore.lua:243-270): ready, number, already owned, stage reached (`IpoConfig.stageIndex(valuation, count)`, IpoConfig.lua:151), Cash, 0.4 s rate.
- **Furniture section:** cards unlock at their stage (`"Objects"`, `"BuyObject", n`). Bought furniture goes into the inventory, not straight into the room.
- **Prices (an open table for the owner; the draft scales with the stage thresholds, IpoConfig.lua:19-22, x 2.5 per IPO, :27):**

| Building | Unlocks at | Draft price, IPO 0 (50% of the threshold) | LONG_GAME office for reference |
|---|---|---|---|
| Garage | start | owned | Garage 0 |
| Seed | Seed (1,800) | 900 | Co-working Loft 580K |
| Series A | Series A (6,300) | 3,150 | Downtown Floor 2M |
| Series B | Series B (23,400) | 11,700 | Campus Wing 7.8M |
| IPO-ready | IPO-ready (81,000) | 40,500 | Global HQ 62M |
| Furniture | its stage | 10-25% of its stage's threshold each | decor (LONG_GAME section 4) |

  Fit with `tools/economy_sim.py` before PR 2. LONG_GAME's numbers belong to its future economy, not today's.
- **D9:** in v1, buildings and furniture are sold for **Cash only**. Anything sold for Robux later (LONG_GAME section 6 "decor bundles") has fixed, listed contents: never a random box, crate or "mystery" item. `OfficeConfig` text may not say odds, chance, luck or random (the same word test as TaskConfig, tools/daily_test.py:4344).

## 7. Existing saves, IPO resets, the old rooms

- **Existing saves:** no `office` section means the Garage, each owned upgrade at its old slot, no furniture. A dev save at Seed or higher sees the Garage until it buys the Seed building (the game is not launched: docs/PUBLISH_RULES.md section 2, so there are no player saves to migrate).
- **IPO (recommended, open question 2):**
  - **Resets:** Cash, upgrades, eggs (today, IpoConfig.lua:53-58), and **the buildings bought**. That is a new key `Buildings = true` in `IpoConfig.Resets`, plus a `ResetNames` entry "office buildings", so the IPO screen lists it by itself (`resetItems`, IpoConfig.lua:122-130). `commitIpo`'s transform (TycoonCore.lua:548-564) also sets `payload.office.buildings = {}`, `active = "Garage"` and `run = new count` in the same save, so the change is atomic.
  - **Kept:** furniture owned and **every layout**. Rebuying a building next run puts everything back where it was, and the upgrades go back to their saved spots as they are rebought. The ladder replays, as LONG_GAME section 4 says ("Loops 2+ replay the ladder"), without making the player redo the layout.
- **Old pre-built rooms:**
  - Stage 1 Garage stays as it is: shell, decor, fingerprint test.
  - Stages 2-5: `Shell` is already a separate group (PlotVisuals.lua:196) and becomes the building. Each `decor` list is cut into catalog objects (sofa, plants, lamps, meeting table, trophy shelf, ...), and each `desk` list becomes that building's hire-desk skin.
  - `syncRoom` (TycoonCore.lua:182-186) stops swapping rooms by stage. The flash plays on "Move in" instead.

## 8. Impact on other branches and docs

| Branch / doc | What changes | Status |
|---|---|---|
| `visuals-garage` (PlotArt, PlotVisuals, docs/PLOT_VISUALS.md, CLAUDE.md "Plot visuals") | `newPlot`/`setStage` (PlotVisuals.lua:235-269) become per building; `buildProp` takes a position and a rotation instead of a slot; the stage 2-5 story tests and the rule "the six upgrade props are identical in every room and never move" are rewritten; stage 1, props and layout fingerprints stay | **must change** (base of this work) |
| `building-pass` (PlotBuilding, PlotBuildingVisuals, BuildingClient, integration patch E2) | `sync(..., stageOf(data))` becomes the active building; per-stage keys stay valid as building keys; budget and fade unchanged | **small change**, not obsolete |
| `design-tutorial` (docs/TUTORIAL_PROPOSAL.md) | Steps 1 and 4 stay valid (a bought upgrade appears at its default spot); the Office cards move down under "Buildings", so TutorialClient must find `Office1` by name and scroll to it (its plan already does); step 9's list gains "office buildings"; a later "Arrange your office" step | **must change** (small) |
| docs/LONG_GAME_PROPOSAL.md | Its "Offices" (section 3) **are** these buildings (0 Income, economy_sim.py:1063); its 7 offices vs 5 stages (Series C+D has two) needs one rule; its "decor 20" is the Furniture catalog; its 18 priced desks fight the 11 spots and the part budget; PR 4 "Office framework" is replaced by this plan | **must change** |
| `PlotArt` pre-built rooms 2-5 as rooms | replaced by shells + catalog | **obsolete** as rooms |
| Onboarding arrow | points at incubators and the BuySign (OnboardingServer.lua:103-121), both fixed | unaffected |

## 9. Build plan (each PR small, tested in the fake Roblox of `tools/daily_test.py`)

| PR | Content | Tests | By hand in Studio |
|---|---|---|---|
| 1 | `OfficeConfig` (5 buildings mapped to `PlotArt.Stages`, the six upgrades with footprints, the shared check), `OfficeServer` (`office` section, run check, `"Place"`/`"Store"`/`"Sync"`), TycoonCore plug-in (KNOWN_SECTIONS, payload, gate, `spawnItem` reads the layout, the IPO transform), Debug rows "Office: move Desk", "Office: reset layout". No visible UI | validation (bounds, overlap, zones, NaN/inf, types, rate, ownership), save round trip, old save = today's look, `v = 2` kept unchanged, run mismatch, IPO transform, addEarnings count unchanged, KNOWN_SECTIONS list updated | Create `OfficeConfig` (ReplicatedStorage) and `OfficeServer` (ServerScriptService) **before** pasting TycoonCore (a `WaitForChild` with no timeout hangs, like PR 1 tasks: PUBLISH_RULES 2b). Paste TycoonCore, ShopServer. F5, use the Debug rows, rejoin, check the Desk stayed moved. |
| 2 | Buildings: shells from PlotArt 2-5, `"Buildings"`/`"BuyBuilding"`, Buildings section in SHOP > Office, `SetActive`/"Move in", `IpoConfig.Resets.Buildings` | locked below the stage, price, Cash, IPO reset, shell budgets, fingerprints of stage 1 | Paste PlotArt, PlotVisuals, IpoConfig, TycoonCore, ShopServer, then ShopClient. Debug: grant valuation, buy Seed, Move in, IPO, check the Garage comes back. |
| 3 | `OfficeClient` edit mode: touch and mouse drag, rotate, store, done, top-down camera, budget bar | layout rectangles at 320x568 and 667x375, top bar 0/36/58; the client sends only id/x/z/r | Create LocalScript `OfficeClient` in StarterPlayerScripts. Test > Device at both sizes; drag, rotate, store on touch and mouse. |
| 4 | Furniture: stage 2-5 decor cut into catalog objects, `"Objects"`/`"BuyObject"`, unlock per stage, light cap | every piece fits its footprint, no odds words, budget and light refusals | Paste PlotArt, OfficeConfig, ShopServer, ShopClient. Buy, place, hit the budget, rejoin. |
| 5 (optional) | Hire desks movable; employee `Home` follows its desk | Home = seat point, wander circle reserved | Paste EmployeeServer, OfficeServer; check hires walk at their moved desks. |

Each PR: claim the scripts first, `python3 tools/daily_test.py` passes, publish with **Shut down all servers** (PR 1 adds the section).

## 10. Open questions for the owner (most important first, with my recommendation)

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
- Every UI size in section 5 except the ones cited from code; Roblox's top-bar height; the 5 px/stud camera estimate.
- Why `MAX_PARTS` is 260 (no written reason); phone frame rate with 1,920 parts; the place's StreamingEnabled setting.
- Whether `TouchControlsEnabled = false` still allows the default touch camera (moot with the scripted camera, but not tested).
- The 4 MB DataStore key limit (Roblox's docs, not checked here).
- The building-pass and design-tutorial details come from their branch docs (`git show`), not from running their code.
