# Five buildings, one per funding stage (proposal, then built on `lobby-all`)

Design first (2026-10-16, branch `lobby-all`, from `main` `f6a546f`), then built on the same branch in stages `lobby-B1` to `lobby-B5` (see section 10). Line numbers are `main` `f6a546f`. **(unverified)** = only Studio or a phone can check it; each one is in docs/STUDIO_SYNC_LOBBY.md's "Not verified" list. The picture of the five buildings side by side is `docs/previews/buildings_plan.svg` (this proposal's numbers) and, once built, `docs/previews/buildings.svg` (drawn from the real data by `tools/render_buildings.py`).

**What this adds:** around each garage's room (PlotArt, unchanged), a real closed building per funding stage (`IpoConfig.Stages`): **1 Garage, 2 Small Office (Seed), 3 Big Office (Series A), 4 Small Corporate (Series B), 5 Big Corporate (IPO-ready)**. Solid outer walls with one doorway, a roof, walls and roof that fade for the local player inside, a complete interior. Built from Parts in PlotArt's palette, nothing random, no odds text. **Every wall, door, window, floor piece and piece of furniture is a model slot** (docs/MODEL_ASSETS_PLAN.md): a ready-made model the owner adds later replaces its Parts version with no code change; with no model, the Parts version is built, so the game works today with none.

**Decisions this proposal takes (each can be changed in one data value):** the front wall's outer face is at **z = 32** in the garage frame for every building (the door side, the anchor); buildings grow **sideways and backward** from it (CUSTOMIZE_PROPOSAL.md D-A); the deepest building stops at **z = -40** because the stage 5 room's skyline stands at z -43 to -49 and `tools/daily_test.py` pins it (section 2.3); the upper storeys of buildings 4 and 5 are seen from outside only (no stairs in v1).

## 1. The owner decisions this must respect

| Decision (where) | What it means here |
|---|---|
| D-A, a bigger building contains the previous one; objects keep their coordinates from a door-side anchor (CUSTOMIZE_PROPOSAL.md:5, 103) | Building n+1 contains building n. All five share the front wall line (z 32) and the room in the front 60 x 60; nothing inside the 60 x 60 moves. |
| Largest size 78 x 82 (CUSTOMIZE_PROPOSAL.md:7, 99), lot 82.6 x 86.6 with 2.3 in front of the anchor (LOBBY_GARAGE_PROPOSAL.md:207) | The largest building is 80 x 72 outside (inside the 82.6-wide lot, 1.3 to spare per side with the eave); 72 deep, not 82, because of the skyline (section 2.3). |
| The player buys the next building when the stage is reached (the task; CUSTOMIZE_PROPOSAL.md:108, FUND 1) | **Blocked on customize PR 2** (`"BuyBuilding"`, `pokedex.active.building`, prices). Until then the building follows the funding stage, exactly like the room does today (`stageOf`, TycoonCore.lua:196). One function, `buildingOf(data)`, decides it; PR 2 changes that one line (section 4). |
| The new building starts empty; objects bought earlier can be placed (the task; CUSTOMIZE_PROPOSAL.md:103-104) | **Blocked on customize PR 3** (placement, inventory). The buildings keep their own fixed furniture **against the outer walls only** and leave the open floor of every new area empty for placement. Owner question 2. |
| Sectors: 5 buildings per sector, Software's are today's (CUSTOMIZE_PROPOSAL.md:7, 88, 161) | These five are Software's. The data is one list, `PlotBuilding.Buildings`, so a sector's art module can bring its own list later. |
| Funding rounds give Cash only, never a building (FUNDING_ROUNDS_PROPOSAL.md section 1) | Nothing here reads rounds. |
| LONG_GAME's 7 stages, 7 offices on 5 footprints (LONG_GAME_PROPOSAL.md:51-58, 88) | A stage past 5 shows building 5 (clamped, like the rooms, PlotVisuals.lua:244). |
| World pass: chunky cartoon, PlotArt's palette, no Wedge (WORLD_PASS_PROPOSAL.md section 4-5) | Blocks, Balls and Cylinders only in the Parts versions; the palette is PlotArt's plus building-pass's. |
| PlotArt rules (PLOT_VISUALS.md, CLAUDE.md:33): rooms untouched, 260 parts and 3 lights per room, fixed gameplay positions | The building is a separate Model with its **own** budget; the rooms, their fingerprints and `PlotVisuals.check` are unchanged. |

## 2. Footprints

### 2.1 The frame

Numbers are studs in the garage's own frame (TycoonCore `plotFrame`, L1): origin at the middle of the Floor's top face, +X right, +Z the front (the door, the plaza), y 0 = the floor top, y -1 = the ground (the Baseplate's top). The Floor stays 60 x 60 (x and z -30 to 30). The front wall's outer face is z **32**, its inner face z **31**; corner posts are 2 x 2; walls are 1 thick.

### 2.2 The five buildings

| # | Building | Stage | Outside (W x D) | x | z | Wall height (ground floor) | Roof top | Door opening (W x H above floor) | Inside, around the room |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Garage | Garage | **68 x 68** | -34 to 34 | -36 to 32 | 16 (ceiling 15) | 16.5 | 16 x 11 (a double roll-up door) | a 3-stud dirt margin (no floor added) |
| 2 | Small Office | Seed | **72 x 72** | -36 to 36 | -40 to 32 | 20 (ceiling 19) | 23 (parapet) | 12 x 11 | U band: sides 5 wide, back 9 deep |
| 3 | Big Office | Series A | **76 x 72** | -38 to 38 | -40 to 32 | 20 (ceiling 19) | 23 | 16 x 11 | U band: sides 7, back 9 |
| 4 | Small Corporate | Series B | **80 x 72** | -40 to 40 | -40 to 32 | 20, then a 16-high storey | 39 | 20 x 11 | U band: sides 9, back 9 |
| 5 | Big Corporate | IPO-ready | **80 x 72** + tower | -40 to 40 | -40 to 32 | 20, then two 16-high storeys, a tower over the middle | about 60 | 20 x 11 | U band: sides 9, back 9 |

- **Nested (D-A):** each footprint contains the one before (68 x 68 inside 72 x 72 inside 76 x 72 inside 80 x 72); building 5 is building 4's footprint, taller and richer. Floor areas inside: 4,356 / 4,900 / 5,180 / 5,460 / 5,460 square studs on the ground floor.
- **The 4-stud grid** (docs/MODEL_ASSETS_PLAN.md): every width and depth above is a multiple of 4, every wall run between corner posts is a multiple of 4 (8-wide panels plus at most one 4-wide), every door opening is a multiple of 4 wide. Thicknesses (walls 1, corner posts 2) are not on the grid: the band between the room's own walls (x, z ±30.15) and the stage 1 weeds (to ±31.8) leaves no room for more.
- **Why the Garage is 68, not building-pass's 62:** the stage 1 room's weeds stand at x ±31.0 to ±31.8 and z -31.2 to -31.8 (measured with the real PlotArt in the fake world). A wall band there would swallow them. At 68 they grow in the garage's dirt margin, inside.

### 2.3 Against the plot spacing, the lot and the skyline

- **Row (today, `ClaimEnabled` off): plots 90 apart** (TycoonCore.lua:76). The widest building is 80 (82 with the roof's eave): **8 studs** between two neighbours at building 4 or 5, 22 at the Garage. The 6-stud rule (CUSTOMIZE_PROPOSAL.md:99) holds. Plot centers sit at z 150 (TycoonCore.lua:135): fronts at z 182, backs at z 110 at the deepest; the VIP Lounge (z 57.5 to 82.5) and its drop spot (0, 88) stay 27+ studs away.
- **Ring (PR L4, `ClaimEnabled` on):** each lot is 82.6 x 86.6 with 2.3 in front of the anchor (the floor's front edge, z 30) and 84.3 behind (LOBBY_GARAGE_PROPOSAL.md:207). The buildings use 2 in front (z 32), 70 behind (z -40) and 41 to each side with the eave (41.3 allowed).
- **The 78 x 82 idea:** width 80 (the lot allows 82.6 with the shell); depth **72, not 82**: the stage 5 room's skyline (PlotArt `Skyline1-9`, z -43 to -49, up to 28 above the floor) must stay behind the back wall, and daily_test.py:4335 and :4403 pin it. Building 4 must fit inside building 5 (D-A), so both stop at z -40. If customize PR 2 removes the skyline (CUSTOMIZE_PROPOSAL.md:99), building 5 can grow to 82 deep by changing two numbers (owner question 3).
- **Reach of the rooms, measured:** stage 1 reaches x ±35.5 (dirt) and z -37.5 to 36.2 (dirt), all flat marks on the ground (they pass under the walls); stages 2 to 4 stay inside x, z ±30.15; stage 5's skyline as above. `tools/building_test.py` builds every room inside every building and fails on any room part inside a building part, except flat ground marks under a wall.

## 3. Part budget against the phone budget

Today's budget: **260 parts and 3 PointLights per room** (PlotVisuals.lua:39-40); rooms use 256 / 244 / 254 / 253 / 257 with all six props. The building is its own Model with its own budget (building-pass's call D-1: the rooms leave 3 to 16 parts, not enough for any shell).

| # | Building | Part budget | Built (Parts versions) | Room + building, worst case | Lights | Triangle budget (models) |
|---|---|---|---|---|---|---|
| 1 | Garage | 80 | see docs/STUDIO_SYNC_LOBBY.md (filled when built) | 336 | 0 | 8,000 |
| 2 | Small Office | 110 | | 354 | 0 | 12,000 |
| 3 | Big Office | 140 | | 394 | 0 | 16,000 |
| 4 | Small Corporate | 180 | | 433 | 0 | 22,000 |
| 5 | Big Corporate | 210 | | 467 | 0 | 28,000 |

- **Per garage at most 470 parts** (room 260 + building 210). Six garages all at building 5: **about 2,800**, plus the world pass (268 for the row; the ring's own count is in PR L4) and the lounge (about 20): **about 3,100 anchored parts server-wide**. The lobby proposal's estimate was 1,880 (LOBBY_GARAGE_PROPOSAL.md:173) with 56-part shells; customize planned 320 per room (CUSTOMIZE_PROPOSAL.md:106). Six garages at stage 5 at the same time is rare.
- **Why it is phone-safe enough to ship behind a Studio check:** every building part is anchored, has no light, no emitter, no shadow on parts under 2 studs, and nothing per frame on the server; with StreamingEnabled (on, WORLD_PASS_PROPOSAL.md:34) a phone keeps only what is near (64 studs minimum radius, **unverified**), about 2 garages around its own. **The gate (Studio, Test > Device, MicroProfiler):** a low-end phone keeps 30 fps or more standing in a building 5 with two neighbours at building 5. If it does not, lower `PlotBuilding.Budget` and drop furniture first (data only).
- **Lights:** a building has **0 PointLights** (the room keeps its 3). Lamps are Neon parts.
- **The budget is a test, not a warning:** `tools/building_test.py` builds each building with the real builder in the fake world, with no model and with a model in every slot, and fails above the budget (parts, colliders included) or above the triangle budget.

## 4. How a stage change swaps the building

- **Which building:** `buildingOf(data)` in TycoonCore = `stageOf(data)` today (the room's own rule, TycoonCore.lua:196), clamped to 1..5. When customize PR 2 lands, it becomes `pokedex.active.building` while buildings are on (CUSTOMIZE_PROPOSAL.md:138): one line.
- **When:** `syncRoom` (TycoonCore.lua:202, every second from the income loop :920) already swaps the room; it calls `syncBuilding(garage, buildingOf(data))` after it. `PlotBuildingVisuals.sync` does nothing when the building already shows that index (one attribute read), else builds the new Model, then destroys the old one (no gap).
- **On join, on leave, for a Free garage:** the garage is permanent (PR L2): `buildGarages` builds building 1 for every garage at server start; the join builds the player's building; the reset after the leave save goes back to building 1.
- **Nobody is trapped:** every solid part of every building stays outside the Floor (the 60 x 60), and the doorway lane stays clear at every building and every turn (test). A player standing exactly where a new wall appears (outside the old building, by its wall) is moved by the server to the landing outside the door (`unstick`, after each swap; tested at all five buildings, four turns). Going back to the Garage after an IPO, a player on building 5's extra floor drops 1 stud to the ground: harmless.
- **The client:** the new Model is tagged; `BuildingClient` starts it at the right fade at once (a player inside never sees the roof come back), as building-pass did.

## 5. The doorway lane, the camera and the fade

- **The lane:** PlotArt's walking lane is x -2.5 to 2.5 from the aisles to z 30 (`PlotVisuals.zones`); the doorway lane of the lobby plan is **9 wide, 9 high, from the apron to the room** (x -4.5 to 4.5, y 0 to 9, z 30 to 35.5: from the Floor's front edge through the door to the end of the apron; inside the room the lane is PlotArt's own reserved zone). Every door opening is wider (12 to 20) and 11 high above the floor. No solid part, and no slot whose model could stand in it, is placed in the lane: door leaves stand beside the opening, lintels start at y 11. Tested at every building and turn; mutant: a door jamb in the lane.
- **Solid parts:** exactly the outer walls (panels, corner posts, windows' glass, lintels), the roof and the added floor strips are `CanCollide` on (with `CanQuery` on, which Roblox needs for collision); every building part has `CanTouch` off; everything else (trim, signs, furniture, ground pieces) has all three off. Model parts are never solid: each solid slot keeps its collider (the Parts version's solid pieces, made invisible) under the model (docs/MODEL_ASSETS_PLAN.md section 3).
- **Closed:** the walls leave no gap a player fits through, except the doorway: tested by sampling the wall lines every half stud from the ground to the ceiling.
- **Inside (the fade):** the box inside the walls from 3 below the floor top to the ground floor's ceiling, plus the doorway and an apron 3.5 deep in front of the door, plus a 1-stud margin once inside (building-pass's maths, unchanged, now measured in the garage frame so a turned garage works). Inside: the whole shell (walls, roof, upper storeys, sign) fades to fully transparent in 0.4 s, 20 steps. The camera script ignores parts that are 0.25 transparent or more **(unverified)**: the fade passes 0.25 about 0.1 s after the player reaches the apron.
- **Outside:** walls act like any building's; a camera swung behind a garage pulls in (accepted, LOBBY_GARAGE_PROPOSAL.md:156).
- **The fade writes only Transparency** (and text and decal transparency, so a decal on a model never floats), never collision or position.

## 6. Where everything goes (the same in every building)

Every gameplay position is in the front 60 x 60, at the same garage-frame coordinates in all five buildings, and none of it moves (PlotArt.Layout, compared with the scripts by daily_test.py):

| What | Where (garage frame) | Source |
|---|---|---|
| Spawn landing | (0, 4, 12), looking at (0, 4, 24) | TycoonCore.lua:747-749 |
| Walking lane | x ±2.5 to z 30, then the door | PlotArt.Layout.reserve.laneEnd |
| 11 hire spots and their desks, the employees | 4 x 3 grid, x ±4.5 / ±13.5, z -10 / 2 / 14, desks 3.3 in front | EmployeeServer.lua:32-37 |
| 5 incubators | z -25, x 0 / ±12 / ±24 | EmployeeServer.lua:38-41 |
| 6 upgrade stations (props) | x ±23, z -10 / 2 / 14 | TycoonCore.lua:151-155 |
| Next-upgrade sign, IPO sign | (0, z 24), (21, z 24) | TycoonCore.lua:77, IpoServer.lua:21 |
| Garage sign (owner name, FREE) | on the facade over the door, part of the building's shell | new (PR L2) |
| Claim post and lamp (PR L3) | (7, 0, 35), outside the door, beside the lane | LOBBY_GARAGE_PROPOSAL.md:151 |

The building's own furniture stands only in the new area around the room (|x| > 30.2 or z < -30.2), against the outer walls, never in a reserved zone or the lane.

## 7. What each building is (Parts versions; every piece is a slot)

**1. Garage (rust, tin and a blue tarp).** Corrugated rust walls (8-wide panels, darker ribs), dark corner posts, a flat tin roof with ribs, a blue repair tarp, a stove pipe; a **double roll-up door** pulled up (drum over the opening, two slats hanging, guide rails); one taped dusty window on the left; a crooked "BUILD YOUR STARTUP" board on the roof; the garage sign over the door. Inside: the stage 1 room as today, with a dirt margin around the slab: an oil drum, a stack of tires, a shelf with paint cans against the back wall. Outside: a cracked concrete path, a tire.

**2. Small Office (mint paint, teal trim, coral).** Mint walls with a teal base band, white window frames, flat roof with a teal parapet, a satellite dish and a vent; a glass double door with sidelights under a coral awning; two windows per side, two at the back; "OFFICE" over the door. Inside the U band (floor added): bike rack and coat rack by the door, a water cooler, two plants, lockers and a bookshelf along the back. Outside: path, welcome mat, two planters.

**3. Big Office (red brick, black steel, amber).** Brick walls with black steel bands, steel-framed glass bays, a black parapet with skylight boxes and two vents, an amber stripe; a wide sliding steel door (open) with two closed roll-up bays painted on the front panels; "OFFICE" on a steel plate. Inside: a lounge in the left band (two beanbags, a low table, a rug), a kitchenette in the right band (counter, fridge, coffee bar), shelves and a printer at the back. Outside: path, two bollards, two planters.

**4. Small Corporate (white panels, navy, cobalt glass), two storeys.** White ground floor with a ribbon of cobalt windows, navy columns, a second storey of white and glass panels (seen from outside), parapet with HVAC boxes; a glass entrance under a navy canopy; "OFFICE" on the canopy. Inside: **reception** in the front-left band (a desk, a logo panel, two waiting chairs), a **glass meeting room** in the right band (table, four chairs, a wall screen), an **open floor** in the back band (two rows of desks with screens, a printer, plants). Outside: wide path, a bench, two planters.

**5. Big Corporate (polished white, graphite, gold), three storeys and a tower.** Glass curtain walls with graphite columns and gold trim, two upper storeys, a tower over the middle with the "HQ" sign in a neon rim and an antenna, a deep lobby canopy on two columns. Inside: a **grand reception** with a logo wall (front left), **two meeting rooms** (right band, front and back), an **executive lounge** (back left: sofa, armchair, a plant), an **open floor** along the back band. Outside: wide path, two flag poles, two planters. The back wall is glass, so the stage 5 room's skyline still shows behind it.

Cartoon and chunky: big simple blocks, thick trim, one accent color per building, no tiny detail. Nothing random. Text only: OFFICE, HQ, BUILD YOUR STARTUP and the garage sign (the owner's display name, FREE, Moving in..., Closing...). No odds words (D9).

## 8. Data and code

- **`PlotBuilding`** (ModuleScript, ServerScriptService, data): `Buildings[1..5]` with key, name, size, heights, door, bounds, budget, palette and a list of **slot placements** (slot name, position, quarter turn, size, group `Shell`/`Interior`/`Static`, solid or not, and the Parts version). Helpers make wall runs, windows and floors from the numbers above.
- **`ModelSlots`** (ModuleScript, ServerScriptService): finds a model for a slot in `ReplicatedStorage.BuildingModels.<Building>.<Slot>`, checks it, cleans it, scales it, or says why not (docs/MODEL_ASSETS_PLAN.md section 3).
- **`PlotBuildingVisuals`** (ModuleScript, ServerScriptService): `build`, `sync`, `bounds`, `validate`, `check`, `slotReport`, the solid-wall and lane checks, `unstick`'s maths, and the pure inside and fade maths (copied into `BuildingClient`, compared by the test).
- **`BuildingClient`** (LocalScript, StarterPlayerScripts, at the repo root as CLAUDE.md wants): the fade, in the garage frame.
- **TycoonCore:** `buildGarages`, `buildingOf`, `syncBuilding`, the reset (PR L2). The CLAIMLOAD block is never edited.
- **Debug (Studio only, shop's Debug tab):** "Buildings: jump to stage 2..5" (raises the valuation like "Jump to IPO-ready" does), and "Building model slots" (which slots use a model, which the Parts version and why).

## 9. Cost in Studio steps

| Stage | Create | Paste | Other |
|---|---|---|---|
| L2 (permanent garage + building 1) | `PlotBuilding`, `PlotBuildingVisuals`, `ModelSlots` (ModuleScripts, ServerScriptService), `BuildingClient` (LocalScript, StarterPlayerScripts) | `TycoonCore` | the hash block; F5: walk in and out, solid walls, Test > Device |
| B2 to B5 (one building each) | none | `PlotBuilding` (and `ShopClient` once, for the Debug rows) | the hash block; Debug "jump to stage n", walk through |
| Models (any time later) | `ReplicatedStorage.BuildingModels.<Building>` folders | none | docs/MODEL_ASSETS_PLAN.md section 4; Debug "Building model slots" |

## 10. Build order on `lobby-all`

`lobby-B0` this doc, docs/MODEL_ASSETS_PLAN.md and the sketch; `lobby-B1` the model-slot system, the data and builder with the Garage, `tools/building_test.py` (new files, not wired); `lobby-L2` the permanent closed building in TycoonCore; `lobby-L3` the claim; `lobby-L4` the ring; `lobby-B2` to `lobby-B5` one building each; `lobby-L5` docs and the one Studio list.

## 11. Blocked (depends on something not built or not decided)

1. **Buying the next building** (customize PR 2: `"BuyBuilding"`, prices, `pokedex.active.building`): not built. The building follows the stage until then (section 4).
2. **"The new building starts empty; earlier objects can be placed"** (customize PR 3: placement, inventory, edit mode with the roof hidden): not built. The buildings leave their new floor open for it; their fixed furniture is against the walls only.
3. **Building 5 at 82 deep:** blocked by the stage 5 skyline pinned in daily_test.py (section 2.3).
4. **Walkable upper storeys and stairs:** not in v1 (the kit names a `Stairs` slot for later; no slot is placed).

## 12. Owner questions

1. Garage at 68 x 68 (around the stage 1 weeds), not 62: fine?
2. Each building's own furniture stands against the outer walls of the new area. Keep it, or leave every new area fully empty for customize's placement?
3. Building 5 at 80 x 72 (skyline kept) or 80 x 82 (skyline removed in PlotArt, a daily_test change)?
4. Upper storeys seen from outside only (no stairs) in v1: fine?

## 13. Not verified (Studio, phone or Creator Hub only)

The look (colors, proportions, text sides), the camera near solid walls, the 0.25 transparency rule of the camera, `ModelStreamingMode` set from a script, StreamingEnabled radii, frame rate on a low-end phone with six buildings at stage 5, `Glass` and `Neon` on phones, that a MeshPart's `Transparency` fades a model with a SurfaceAppearance, that `Model:GetBoundingBox` follows the pivot's orientation, and how the Parts versions read from the default camera at phone size.
