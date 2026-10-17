# Plot visuals: the garage that grows with the startup

Branch `visuals-garage`. Looks only: nothing here is saved, sent through a remote or read back by the game, and every gameplay position stays where `TycoonCore` and `EmployeeServer` put it. The two scripts:

| Script | Studio location | What it does |
|---|---|---|
| `PlotArt.lua` | ServerScriptService (ModuleScript) | The data: the layout map, one room per funding stage, the hire desks, the six upgrade props, and the furniture kit pieces the rooms use (`PlotArt.Kit`). Built-in Parts plus the 3D kit already in `ReplicatedStorage.KitModels` (no other asset), nothing random. |
| `PlotVisuals.lua` | ServerScriptService (ModuleScript) | The builder (`buildRoom`, `buildProp`, `setStage`, `addProp`, `buildKitPiece`, the stage flash and the prop pop-in) and the checks (`validate`, `check`, `kitBox`). |

`TycoonCore` requires both inside `pcall` and calls the builder through `looks()` (pcall + warn): an art bug can never stop the game. A player's room is rebuilt when `IpoConfig.stageIndex(valuation, ipoCount)` changes (the same rule as the IPO sign), with a short flash. Bought upgrade props move into the new room unchanged.

## The five rooms

`PlotArt.Stages[i]` is the room for `IpoConfig.Stages[i]` (same key). The plot stays 60 x 60: the building grows through the shell and the decor only.

| # | Key | Story | Floor | Parts with the six props | PointLights |
|---|---|---|---|---|---|
| 1 | `Garage` | A poor founder's garage: cracked concrete, rusty sheet walls, a half-open roll-up door, one taped window, a bare bulb (kit `BareBulb`), an old secondhand desk and chair (kit `Desk`, `Chair`) with an old PC and a desk phone, a workbench (kit `Workbench`), a pile of crates (kit `Crate`). Hire desks are crates (kit `Crate`, made low and shallow). | Concrete, gray | 258 with the kit, 260 from Parts | 2 |
| 2 | `Seed` | Garage glow-up: fresh mint paint with dark teal trim, a new four-panel door with a smoked glass band, two clean windows, an OFFICE sign, oak desks with monitors for the hires, string lights, a rug and a coral sofa, plants. | Concrete, light | 244 | 3 |
| 3 | `SeriesA` | Expanded garage-office: red brick walls with black steel trim, a second bay (two roll-up doors) with a glass partition around each outer incubator and amber safety lines, a whiteboard wall over the middle, warm wall lamps, filing cabinets, a charcoal sofa. | Concrete, polished | 254 | 3 |
| 4 | `SeriesB` | Real office: blue-gray carpet tiles, white walls with a ribbon of windows along the back, glass walls along both sides, a glass-walled meeting room (table, chairs, wall screen), big plants, floor lamps. | Fabric, blue-gray | 253 | 3 |
| 5 | `IpoReady` | HQ: polished light floor, four big windows with a simple block skyline behind them, a graphite logo wall with a neon rim ("HQ"), a trophy shelf, an armchair lounge, a reception desk. | SmoothPlastic, white | 257 | 3 |

Every room (2 to 5) also has the founder's desk with the `DeskPhone` (a later step makes it ring) on the front right, and a hire desk for each of the 11 hire spots (white, oak or birch tops on two dark legs and a monitor, screen toward the hire).

The six upgrade props (Desk, Coffee Machine, Laptop, Server Rack, Whiteboard, Neon Logo) are one shared list in `PlotArt.Props`, **identical in all five rooms**. A stage never owns props.

## Furniture from the 3D kit (interiors lane)

The rooms' furniture comes from the 3D kit (`ReplicatedStorage.KitModels`, docs/KIT_MODELS.md), the same models in every room, recolored per stage. No new models. In `PlotArt` a kit piece is `KIT(name, key, x, y, z, roles, extra)` in a room's `decor` or `desk` list, next to the Parts:

- `key` is a model of `PlotArt.Kit` (size, roles and a **Parts version** of each model the rooms use, copied from docs/KIT_MODELS.md; tools/daily_test.py compares them). `roles` gives every role of the model a color and a material (the allowed materials; Neon only when the piece's name says it is a light).
- `turn` (0, 90, 180 or 270: the model's front, +Z in the file, then faces that way) and `scale` (a number, or `{ x, y, z }` of the kit size) place it; `light` puts a PointLight on the part of role `lightRole`.
- `PlotVisuals` copies the model's MeshParts, fits them to the manifest size (`KitSize`), scales and turns them (and by `PlotArt.KIT_FRONT_TURN`, always equal to `PlotBuilding.KIT_FRONT_TURN`), recolors each by its `Role` and turns off collide, touch and query. A piece is built from its Parts version, with one warning per model per server, when the kit or the model is missing, when a MeshPart can't be copied (Archivable off), has a role the piece has no color for, or is turned inside its model while the piece is scaled unevenly. **The game looks right with no kit at all.**
- The kit folder: `newPlot` takes it as an argument, or finds `ReplicatedStorage.KitModels` itself (`PlotVisuals.findKit`, the only service PlotVisuals reads, inside pcall). `buildRoom(parent, center, art, stage, kit)` with no kit builds Parts only.
- Every rule below holds **with the kit and without it**: tools/daily_test.py builds every room from Parts, from a fake kit (each role one MeshPart, as imported), from a fake kit whose every role fills the whole model (the worst case for the zones) and from a fake kit imported turned around with `KIT_FRONT_TURN` 180. Every part of a piece stays inside `PlotVisuals.kitBox` (its kit size times its scale), so the zone checks hold for the real meshes too.
- Hire desks: the desk zone is 3.8 wide, 1.8 deep and 3 high, so a kit desk there is scaled down. There is **no chair at a hire desk**: a chair would stand where the hire stands (the hire zone).

## Rules every room keeps (tools/daily_test.py proves them for each room)

- **Gameplay positions are fixed.** The hire grid (4 x 3, 11 spots), the six upgrade stations, the five incubators, the two signs, the spawn and the 6+ stud aisles are copied into `PlotArt.Layout` and compared with the scripts. Nothing of a room stands in a reserved zone (`PlotVisuals.zones`), nothing blocks the walking lane, and each hire desk and each prop stays inside its own zone.
- **The room stays open; the building around it is closed** (lobby L2). `PlotArt` rooms keep their low walls (6 studs at most on the sides, no wall along the front, 12 at the back) and no roof: checks and fingerprints unchanged. Around each room, `PlotBuilding` builds the closed building of the funding stage (section "The building" below), as its own Model with its own budget.
- **Decor never interferes.** Every part is anchored, `CanCollide`, `CanTouch` and `CanQuery` off. Nothing collides, not even the walls (a solid wall makes the camera zoom in); the real `Floor` Part is the only solid. The floor is only restyled (color, material), never renamed or resized.
- **No floating part.** Everything rests on the floor, the ground or a chain of touching parts.
- **Budgets per room:** at most 260 parts (the six props are 118 of them, so shell + decor + 11 desks have 142), at most 3 PointLights, tiny parts cast no shadow, big glass casts none either. A kit piece counts its MeshParts (one per role) with the kit and its boxes without it: both must fit.
- **Materials:** Concrete, CorrodedMetal, Metal, DiamondPlate, Wood, WoodPlanks, Brick, Fabric, Plastic, SmoothPlastic, Glass, Neon. Neon only for lights and signs, and the part's name must say so (Bulb, Lamp, Light, Screen, LED, Sign, Logo, Neon, Glow).
- **Nothing random, no odds text** (D9): the only room text is OFFICE, HQ and BUILD YOUR STARTUP, the stage 1 notes and the props' own labels.
- **The skyline** (stage 5, parts named `Skyline...`) stands behind the back wall (z -43 or further), on the ground, at most 30 studs high and inside the plot's width, so it never reaches the neighbour (plots are 90 studs apart).
- **Stage 1 is frozen.** The tests keep a fingerprint of its parts, of the six props and of the layout, taken before stages 2 to 5 were added. Stage 1's was taken again on purpose by interiors PR 1 (the Garage's kit furniture); the props' and the layout's are unchanged.

## Adding or changing a room

1. Edit `PlotArt.lua` only (data). Keep the part names unique inside a list, use the `B(name, x, y, z, w, h, d, color, material, extra)` helper and the shared builders (`plant`, `sofaLeft`, `founderDesk`), and `KIT(...)` for furniture from the kit (add the model to `PlotArt.Kit` first, with its Parts version).
2. `python tools/daily_test.py` (needs `luau`, see the README): it builds every room with all six props in a fake Roblox and runs `PlotVisuals.check` (zones, floating parts, wall heights, flags, budgets), plus the per-room story checks and mutation checks (a box in a hire's spot, in the lane, in a station, on a sign, a floating box, a collidable box, four lights, a tall side wall, too many parts must all be caught).
3. Sync the script into Studio (docs/STUDIO_SYNC.md) and look at it in a playtest and at phone size.

## The Studio preview

`Workspace.PREVIEW_STAGES` (the rooms side by side at x = -600) exists only in Studio and **must be deleted before publishing**. docs/STUDIO_SYNC.md has the command-bar snippet that rebuilds it from the scripts.

## The building (lobby L2)

Each garage is permanent (`Workspace.Garages.Garage1..6`: the Floor, the building, the name sign); the owner's folder (room, props, employees, incubators, signs) stands in it while they play. `PlotBuilding` (data and pure layout) and `PlotBuildingVisuals` (the builder and its checks) build one building per funding stage from the 3D kit in `ReplicatedStorage.KitModels` (docs/KIT_MODELS.md), each piece from Parts where its model is missing. `BuildingClient` (a LocalScript) fades the shell for the local player inside. The rules, all checked by `tools/building_test.py` at five stages and four turns:

- **Five buildings:** 1 Garage (one story, brick, roll-up door), 2 Small Office (one story, white), 3 Big Office (two stories), 4 Small Corporate (four stories of blue glass, an open entrance between two pillars), 5 Big Corporate (a marble podium and a five-story dark glass tower, columns, a crown). Footprints from 68 x 66.2 to 82.4 x 74.4: at least building-pass's 62 x 62, inside the lot (82.6 x 86.6). They grow from the floor's front-center: the front face is z 32.2 in the garage's frame at every stage.
- **Solid = invisible boxes.** Seven to ten anchored Parts per building (outer walls, the doorway left open, the roof, the floor of the furniture band) are `CanCollide` on, `CanTouch` off, Transparency 1. Every kit MeshPart and fallback Part is `CanCollide`, `CanTouch` and `CanQuery` off, no shadow. Every box is outside the 60 x 60 floor, except the roof (from 12.5 studs up: a jump reaches about 12.3; a stage change never moves anyone because of it). A stage change moves anyone standing where a new box is to the landing spot.
- **The doorway** is at least 9 wide and 9 high and nothing solid stands in the lane (9 wide, from the room to the end of the 3.5-stud apron); only a stage's door piece (WallGarage at stage 1, the offices' WallDoor, stretched 1.5 times so its 9-wide opening is the lane) may stand in it, never solid. The claim post's spot, the landing and every reserved zone stay clear.
- **The fade:** inside (the doorway and the apron included, as wide as the lane: someone at the claim post is outside), the shell (`Fade`) fades to 1 from each part's own Transparency (kit glass from 0.3). The furniture and the band's floor (`Static`) stay visible; the boxes are already invisible. Only the ground floor is inside: the upper stories are exterior only.
- **Kit use:** only MeshParts of a kit model are used (anything else is left out with one warning), recolored per stage by their `Role` attribute (`PlotBuilding.Styles`: a color and a material per role), placed by the model's `WorldPivot`, turned by `PlotBuilding.KIT_FRONT_TURN`. Only `Wall`, `RoofEdge`, `WallDoor` and `DoorLeaf` (along X) and `Floor` (X and Z) are stretched.
- **Budget:** at most 160 parts per building (kit or Parts, boxes included), no lights. Six garages at the biggest stage plus the plaza stay under 3,000.
- **Furniture** (stages 2 to 5) stands in a band at most 4 deep along the shell's inner faces (Big Corporate's back band: 8), outside the room, the lane and every zone. `PlotBuilding.furnitureFootprints(stage)` lists the boxes for customize PR 2.

Change a building in `PlotBuilding.lua` only, then run `python3 tools/building_test.py`.
